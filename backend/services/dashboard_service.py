"""Dashboard analytics service for MoneyLeak AI."""

from __future__ import annotations

from typing import Any

from services.analytics_utils import (
    CATEGORY_NEED_WANT_WASTE,
    actionable_transactions,
    credit_amount,
    date_range,
    debit_amount,
    display_merchant_name,
    empty_result,
    get_category,
    get_field,
    get_need_want_waste_type,
    high_value_review_transactions,
    is_high_value_or_anomaly,
    parse_date,
    percentage,
    service_result,
    controllable_spend_total,
    total_actionable_spend,
    total_credit_received,
    total_debit_spend,
    valid_transactions,
)


def anomaly_warning(review_rows: list[dict[str, Any]]) -> list[str]:
    """Return warnings for high-value review rows."""
    if not review_rows:
        return []
    total = round(sum(float(row.get("amount") or 0.0) for row in review_rows), 2)
    return [f"{len(review_rows)} high-value transaction(s) totaling ₹{total:.2f} were excluded from actionable dashboard analytics and need review."]


def get_summary(transactions: list[Any], user_budget: Any = None) -> dict[str, Any]:
    """Return headline dashboard metrics for a user's transaction list."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result(
            {
                "total_spent": 0.0,
                "total_spent_raw": 0.0,
                "total_spent_actionable": 0.0,
                "actionable_spend": 0.0,
                "total_received": 0.0,
                "net_balance_change": 0.0,
                "total_transactions": 0,
                "top_spending_category": None,
                "uncategorized_transactions": 0,
                "money_leak_score": None,
                "possible_monthly_savings": 0.0,
                "possible_yearly_savings": 0.0,
                "high_value_review_transactions": [],
                "statement_period": {"start": None, "end": None},
            }
        )

    warnings: list[str] = []
    review_rows = high_value_review_transactions(safe_transactions)
    warnings.extend(anomaly_warning(review_rows))
    normal_transactions = actionable_transactions(safe_transactions)
    total_spent_raw = total_debit_spend(safe_transactions)
    total_spent_actionable = total_actionable_spend(safe_transactions)
    total_received = total_credit_received(safe_transactions)
    category_totals: dict[str, float] = {}
    for transaction in normal_transactions:
        amount = debit_amount(transaction)
        if amount <= 0:
            continue
        category = get_category(transaction)
        category_totals[category] = category_totals.get(category, 0.0) + amount
    top_category = max(category_totals.items(), key=lambda item: item[1])[0] if category_totals else None
    start_date, end_date = date_range(safe_transactions)
    if start_date is None or end_date is None:
        warnings.append("Could not determine full statement period because transaction dates are missing.")

    try:
        from services.duplicate_detector import detect_duplicates
        from services.money_leak_score import calculate_score
        from services.report_summary import generate_saving_priority
        from services.subscription_detector import detect_subscriptions

        subscriptions_result = detect_subscriptions(safe_transactions)
        duplicates_result = detect_duplicates(safe_transactions)
        subscriptions = subscriptions_result.get("data", [])
        duplicates = duplicates_result.get("data", [])
        score_result = calculate_score(safe_transactions, subscriptions, duplicates, user_budget)
        priority_result = generate_saving_priority(safe_transactions, subscriptions, duplicates)
        saving_items = priority_result.get("data", [])
        possible_monthly_savings = round(sum(float(item.get("possible_monthly_saving") or 0.0) for item in saving_items), 2)
        possible_monthly_savings = min(possible_monthly_savings, controllable_spend_total(safe_transactions))
        money_leak_score = score_result.get("data")
        warnings.extend(score_result.get("warnings", []))
        warnings.extend(priority_result.get("warnings", []))
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        warnings.append(f"Savings and score could not be fully calculated: {exc.__class__.__name__}")
        possible_monthly_savings = 0.0
        money_leak_score = None

    data = {
        "total_spent": round(total_spent_raw, 2),
        "total_spent_raw": round(total_spent_raw, 2),
        "total_spent_actionable": round(total_spent_actionable, 2),
        "actionable_spend": round(total_spent_actionable, 2),
        "total_received": round(total_received, 2),
        "net_balance_change": round(total_received - total_spent_raw, 2),
        "net_actionable_balance_change": round(total_received - total_spent_actionable, 2),
        "total_transactions": len(safe_transactions),
        "top_spending_category": top_category,
        "uncategorized_transactions": sum(1 for transaction in safe_transactions if bool(get_field(transaction, "needs_review", False))),
        "money_leak_score": money_leak_score,
        "possible_monthly_savings": round(possible_monthly_savings, 2),
        "possible_yearly_savings": round(possible_monthly_savings * 12.0, 2),
        "high_value_review_transactions": review_rows,
        "statement_period": {
            "start": start_date.isoformat() if start_date else None,
            "end": end_date.isoformat() if end_date else None,
        },
    }
    return service_result(data, list(dict.fromkeys(warnings)))


def get_category_breakdown(transactions: list[Any]) -> dict[str, Any]:
    """Return actionable debit spending grouped by category with percentages and averages."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result([])

    normal_transactions = actionable_transactions(safe_transactions)
    total_spend = total_debit_spend(normal_transactions)
    grouped: dict[str, dict[str, Any]] = {}
    for transaction in normal_transactions:
        amount = debit_amount(transaction)
        if amount <= 0:
            continue
        category = get_category(transaction)
        if category not in grouped:
            grouped[category] = {
                "category": category,
                "total_amount": 0.0,
                "transaction_count": 0,
                "percentage_of_total_spend": 0.0,
                "average_transaction_amount": 0.0,
                "need_want_waste_type": get_need_want_waste_type(transaction),
            }
        grouped[category]["total_amount"] += amount
        grouped[category]["transaction_count"] += 1

    breakdown = []
    for item in grouped.values():
        count = int(item["transaction_count"] or 0)
        total_amount = float(item["total_amount"] or 0.0)
        item["total_amount"] = round(total_amount, 2)
        item["percentage_of_total_spend"] = percentage(total_amount, total_spend)
        item["average_transaction_amount"] = round(total_amount / count, 2) if count > 0 else 0.0
        breakdown.append(item)
    breakdown.sort(key=lambda value: float(value.get("total_amount") or 0.0), reverse=True)
    warnings = [] if total_spend > 0 else ["No actionable debit spending found"]
    review_rows = high_value_review_transactions(safe_transactions)
    warnings.extend(anomaly_warning(review_rows))
    return service_result(breakdown, list(dict.fromkeys(warnings)))


def get_top_merchants(transactions: list[Any], limit: int = 10) -> dict[str, Any]:
    """Return top merchants by actionable debit spend."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result([])

    safe_limit = max(1, int(limit or 10))
    normal_transactions = actionable_transactions(safe_transactions)
    total_spend = total_debit_spend(normal_transactions)
    grouped: dict[str, dict[str, Any]] = {}
    for transaction in normal_transactions:
        amount = debit_amount(transaction)
        if amount <= 0:
            continue
        merchant = display_merchant_name(get_field(transaction, "merchant", None))
        if merchant not in grouped:
            grouped[merchant] = {
                "merchant": merchant,
                "category": get_category(transaction),
                "total_spent": 0.0,
                "transaction_count": 0,
                "average_transaction": 0.0,
                "highest_single_transaction": 0.0,
                "risk_level": "low",
            }
        grouped[merchant]["total_spent"] += amount
        grouped[merchant]["transaction_count"] += 1
        grouped[merchant]["highest_single_transaction"] = max(float(grouped[merchant]["highest_single_transaction"]), amount)

    merchants = []
    for item in grouped.values():
        count = int(item["transaction_count"] or 0)
        total = float(item["total_spent"] or 0.0)
        item["total_spent"] = round(total, 2)
        item["average_transaction"] = round(total / count, 2) if count > 0 else 0.0
        item["highest_single_transaction"] = round(float(item["highest_single_transaction"] or 0.0), 2)
        share = percentage(total, total_spend)
        if share > 20:
            item["risk_level"] = "high"
        elif share > 10:
            item["risk_level"] = "medium"
        else:
            item["risk_level"] = "low"
        merchants.append(item)
    merchants.sort(key=lambda value: float(value.get("total_spent") or 0.0), reverse=True)
    warnings = [] if merchants else ["No merchant spending found"]
    review_rows = high_value_review_transactions(safe_transactions)
    warnings.extend(anomaly_warning(review_rows))
    return service_result(merchants[:safe_limit], list(dict.fromkeys(warnings)))


def get_daily_spend(transactions: list[Any]) -> dict[str, Any]:
    """Return actionable daily debit spend sorted by transaction date."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result([])

    grouped: dict[str, float] = {}
    warnings: list[str] = []
    for transaction in actionable_transactions(safe_transactions):
        amount = debit_amount(transaction)
        if amount <= 0:
            continue
        parsed_date = parse_date(get_field(transaction, "transaction_date", None))
        if parsed_date is None:
            warnings.append("Some transactions were skipped because dates are missing.")
            continue
        key = parsed_date.isoformat()
        grouped[key] = grouped.get(key, 0.0) + amount
    daily = [{"date": key, "amount": round(value, 2)} for key, value in sorted(grouped.items())]
    if not daily:
        warnings.append("No dated actionable debit spending found")
    review_rows = high_value_review_transactions(safe_transactions)
    warnings.extend(anomaly_warning(review_rows))
    return service_result(daily, list(dict.fromkeys(warnings)))


def get_needs_wants_waste(transactions: list[Any]) -> dict[str, Any]:
    """Return actionable spending totals and percentages by need/want/waste/savings labels."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result(
            {
                "needs_total": 0.0,
                "wants_total": 0.0,
                "waste_total": 0.0,
                "savings_total": 0.0,
                "needs_pct": 0.0,
                "wants_pct": 0.0,
                "waste_pct": 0.0,
                "savings_pct": 0.0,
            }
        )

    totals = {"need": 0.0, "want": 0.0, "waste": 0.0}
    for transaction in actionable_transactions(safe_transactions):
        label = get_need_want_waste_type(transaction)
        if label not in totals:
            continue
        amount = debit_amount(transaction)
        totals[label] += amount
    savings_activity = sum(debit_amount(transaction, exclude_refunds=False) for transaction in safe_transactions if get_category(transaction) == "Investments & Savings" and not is_high_value_or_anomaly(transaction))
    detected_income = total_credit_received(safe_transactions)
    total_amount = sum(totals.values())
    data = {
        "needs_total": round(totals["need"], 2),
        "wants_total": round(totals["want"], 2),
        "waste_total": round(totals["waste"], 2),
        "savings_total": round(savings_activity, 2),
        "detected_income": round(detected_income, 2),
        "savings_rate_pct": percentage(savings_activity, detected_income),
        "needs_pct": percentage(totals["need"], total_amount),
        "wants_pct": percentage(totals["want"], total_amount),
        "waste_pct": percentage(totals["waste"], total_amount),
        "savings_pct": percentage(savings_activity, detected_income),
    }
    warnings = [] if total_amount > 0 else ["No classified actionable spending found"]
    review_rows = high_value_review_transactions(safe_transactions)
    warnings.extend(anomaly_warning(review_rows))
    return service_result(data, list(dict.fromkeys(warnings)))


def category_type_for_name(category: str) -> str:
    """Return the default need/want/waste type for a category name."""
    return CATEGORY_NEED_WANT_WASTE.get(category, "unknown")
