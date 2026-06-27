"""Month-wise analysis and month-over-month comparison services."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from services.analytics_utils import (
    actionable_transactions,
    credit_amount,
    date_range,
    debit_amount,
    empty_result,
    get_category,
    is_credit,
    parse_date,
    percentage,
    service_result,
    total_actionable_spend,
    total_credit_received,
    valid_transactions,
)
from services.leakage_detector import detect_small_spend_leakage
from services.money_leak_score import calculate_score
from services.subscription_detector import detect_subscriptions
from services.duplicate_detector import detect_duplicates


def month_key_for_transaction(transaction: Any) -> str | None:
    """Return a YYYY-MM month key for a transaction or None when the date is unavailable."""
    parsed_date = parse_date(getattr(transaction, "transaction_date", None) if not isinstance(transaction, dict) else transaction.get("transaction_date"))
    if parsed_date is None:
        return None
    return parsed_date.strftime("%Y-%m")


def month_label(month_key: str) -> str:
    """Return a readable month label from a YYYY-MM key."""
    try:
        year_text, month_text = month_key.split("-", 1)
        import calendar
        return f"{calendar.month_name[int(month_text)]} {year_text}"
    except (ValueError, IndexError, TypeError):
        return month_key


def split_transactions_by_month(transactions: list[Any]) -> dict[str, list[Any]]:
    """Group transactions by calendar month, ignoring rows without parseable dates."""
    grouped: dict[str, list[Any]] = defaultdict(list)
    for transaction in valid_transactions(transactions):
        key = month_key_for_transaction(transaction)
        if key is not None:
            grouped[key].append(transaction)
    return dict(sorted(grouped.items()))


def month_coverage(transactions: list[Any]) -> tuple[int, bool]:
    """Return covered days and whether the month appears complete."""
    start_date, end_date = date_range(transactions)
    if start_date is None or end_date is None:
        return 0, False
    covered_days = max(1, (end_date - start_date).days + 1)
    try:
        import calendar
        month_days = calendar.monthrange(start_date.year, start_date.month)[1]
        is_full = start_date.day <= 2 and end_date.day >= month_days - 1
    except (ValueError, TypeError):
        is_full = False
    return covered_days, is_full


def month_metrics(transactions: list[Any], month_key: str) -> dict[str, Any]:
    """Calculate one month of actionable spending metrics."""
    safe_transactions = valid_transactions(transactions)
    actionable = actionable_transactions(safe_transactions)
    total_spent = round(sum(debit_amount(transaction, exclude_refunds=True) for transaction in safe_transactions), 2)
    actionable_spend = total_actionable_spend(safe_transactions)
    total_received = total_credit_received(safe_transactions)
    net_savings = round(total_received - total_spent, 2)

    category_totals: dict[str, float] = {}
    need_want_waste = {"need": 0.0, "want": 0.0, "waste": 0.0}
    for transaction in actionable:
        amount = debit_amount(transaction)
        category = get_category(transaction)
        category_totals[category] = category_totals.get(category, 0.0) + amount
        from services.analytics_utils import get_need_want_waste_type
        label = get_need_want_waste_type(transaction)
        if label in need_want_waste:
            need_want_waste[label] += amount

    top_category = max(category_totals.items(), key=lambda item: item[1])[0] if category_totals else "—"
    small_result = detect_small_spend_leakage(safe_transactions).get("data", {})
    subscriptions = detect_subscriptions(safe_transactions).get("data", [])
    duplicates = detect_duplicates(safe_transactions).get("data", [])
    score_data = calculate_score(safe_transactions, subscriptions, duplicates).get("data", {})
    covered_days, is_full_month = month_coverage(safe_transactions)
    total_split = sum(need_want_waste.values())

    return {
        "month": month_key,
        "label": month_label(month_key),
        "total_spent": total_spent,
        "actionable_spend": actionable_spend,
        "total_received": total_received,
        "net_savings": net_savings,
        "top_category": top_category,
        "money_leak_score": score_data.get("score", 0.0) if isinstance(score_data, dict) else 0.0,
        "small_spend_leakage": round(float(small_result.get("total_leakage", 0.0) if isinstance(small_result, dict) else 0.0), 2),
        "subscription_cost": round(sum(float(item.get("monthly_amount", 0.0) or 0.0) for item in subscriptions), 2),
        "duplicate_amount": round(sum(float(item.get("amount", 0.0) or 0.0) for item in duplicates), 2),
        "needs_pct": percentage(need_want_waste["need"], total_split),
        "wants_pct": percentage(need_want_waste["want"], total_split),
        "waste_pct": percentage(need_want_waste["waste"], total_split),
        "days_covered": covered_days,
        "is_full_month": is_full_month,
        "transaction_count": len(safe_transactions),
    }


def calculate_monthly_analysis(transactions: list[Any]) -> dict[str, Any]:
    """Return month-by-month analysis for uploaded transactions."""
    grouped = split_transactions_by_month(transactions)
    if not grouped:
        return empty_result({"months": [], "summary": {}})
    months = [month_metrics(rows, key) for key, rows in grouped.items()]
    summary = {
        "month_count": len(months),
        "latest_month": months[-1]["month"],
        "best_savings_month": max(months, key=lambda row: float(row.get("net_savings", 0.0))).get("month"),
        "highest_spend_month": max(months, key=lambda row: float(row.get("actionable_spend", 0.0))).get("month"),
        "average_actionable_spend": round(sum(float(row.get("actionable_spend", 0.0)) for row in months) / max(len(months), 1), 2),
    }
    warnings = []
    partial = [row["label"] for row in months if not row.get("is_full_month")]
    if partial:
        warnings.append(f"Partial-month data detected for: {', '.join(partial)}.")
    return service_result({"months": months, "summary": summary}, warnings)


def calculate_monthly_comparison(transactions: list[Any]) -> dict[str, Any]:
    """Return adjacent month-over-month comparisons and human-readable insights."""
    monthly = calculate_monthly_analysis(transactions)
    data = monthly.get("data", {}) if isinstance(monthly.get("data", {}), dict) else {}
    months = data.get("months", []) if isinstance(data.get("months", []), list) else []
    if len(months) < 2:
        return service_result({"comparisons": [], "insights": []}, ["At least two months of transactions are needed for comparison."])

    comparisons = []
    insights = []
    for previous, current in zip(months, months[1:]):
        prev_spend = float(previous.get("actionable_spend", 0.0) or 0.0)
        curr_spend = float(current.get("actionable_spend", 0.0) or 0.0)
        prev_income = float(previous.get("total_received", 0.0) or 0.0)
        curr_income = float(current.get("total_received", 0.0) or 0.0)
        prev_score = float(previous.get("money_leak_score", 0.0) or 0.0)
        curr_score = float(current.get("money_leak_score", 0.0) or 0.0)
        spend_change = curr_spend - prev_spend
        income_change = curr_income - prev_income
        score_change = curr_score - prev_score
        comparison = {
            "from_month": previous.get("month"),
            "to_month": current.get("month"),
            "from_label": previous.get("label"),
            "to_label": current.get("label"),
            "spending_change": round(spend_change, 2),
            "spending_change_pct": percentage(abs(spend_change), prev_spend) * (1 if spend_change >= 0 else -1),
            "income_change": round(income_change, 2),
            "income_change_pct": percentage(abs(income_change), prev_income) * (1 if income_change >= 0 else -1),
            "savings_change": round(float(current.get("net_savings", 0.0) or 0.0) - float(previous.get("net_savings", 0.0) or 0.0), 2),
            "money_leak_score_change": round(score_change, 2),
            "top_category_change": {"from": previous.get("top_category"), "to": current.get("top_category")},
        }
        comparisons.append(comparison)
        direction = "increased" if spend_change > 0 else "decreased"
        insights.append(f"{current.get('label')} spending {direction} by ₹{abs(spend_change):,.2f} versus {previous.get('label')}.")
        if score_change < 0:
            insights.append(f"Money Leak Score improved by {abs(score_change):.2f} points in {current.get('label')}.")
        elif score_change > 0:
            insights.append(f"Money Leak Score worsened by {score_change:.2f} points in {current.get('label')}.")
    return service_result({"comparisons": comparisons, "insights": insights, "months": months}, monthly.get("warnings", []))
