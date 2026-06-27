"""Report summary, savings priority, and spending personality services."""

from __future__ import annotations

from typing import Any

from services.analytics_utils import (
    actionable_transactions,
    controllable_spend_total,
    debit_amount,
    empty_result,
    estimate_income,
    get_category,
    get_field,
    get_need_want_waste_type,
    is_high_value_or_anomaly,
    parse_date,
    projection_transactions,
    service_result,
    total_debit_spend,
    valid_transactions,
)
from services.dashboard_service import get_category_breakdown
from services.leakage_detector import detect_small_spend_leakage


def opportunity(rank: int, target: str, reason: str, monthly_saving: float, difficulty: str, action: str) -> dict[str, Any]:
    """Build one savings opportunity row."""
    return {
        "rank": rank,
        "target": target,
        "reason": reason,
        "possible_monthly_saving": round(float(monthly_saving or 0.0), 2),
        "possible_yearly_saving": round(float(monthly_saving or 0.0) * 12.0, 2),
        "difficulty": difficulty,
        "action": action,
    }


def duplicate_monthly_saving(duplicates: list[dict[str, Any]] | None) -> float:
    """Return exact duplicate saving from duplicate detector output."""
    return round(sum(float(item.get("amount") or 0.0) for item in (duplicates or [])), 2)


def high_cost_subscription_saving(subscriptions: list[dict[str, Any]] | None) -> tuple[str | None, float]:
    """Return the highest-cost subscription target and possible monthly saving."""
    subscription_items = subscriptions or []
    if not subscription_items:
        return None, 0.0
    highest = max(subscription_items, key=lambda item: float(item.get("monthly_cost") or 0.0))
    monthly_cost = float(highest.get("monthly_cost") or 0.0)
    if monthly_cost <= 0:
        return None, 0.0
    return str(highest.get("merchant") or "Subscription"), round(monthly_cost, 2)


def top_want_category_saving(transactions: list[Any]) -> tuple[str | None, float, float]:
    """Return top want category when it exceeds thirty percent of controllable projected spend."""
    category_result = get_category_breakdown(projection_transactions(transactions))
    categories = category_result.get("data", [])
    for item in categories:
        if item.get("need_want_waste_type") == "want" and float(item.get("percentage_of_total_spend") or 0.0) > 30.0:
            monthly_saving = float(item.get("total_amount") or 0.0) * 0.20
            return str(item.get("category") or "Want spending"), round(monthly_saving, 2), float(item.get("percentage_of_total_spend") or 0.0)
    return None, 0.0, 0.0


def bank_charge_saving(transactions: list[Any]) -> float:
    """Return total bank charges that may be controllable."""
    return round(
        sum(
            debit_amount(transaction)
            for transaction in valid_transactions(transactions)
            if get_category(transaction) == "Bank Charges & Fees" and not is_high_value_or_anomaly(transaction)
        ),
        2,
    )


def cap_saving_items(items: list[dict[str, Any]], cap_amount: float) -> list[dict[str, Any]]:
    """Cap ranked saving opportunities so total projected savings never exceeds controllable spend."""
    remaining = max(0.0, float(cap_amount or 0.0))
    capped_items: list[dict[str, Any]] = []
    for item in items:
        if remaining <= 0:
            break
        monthly = max(0.0, float(item.get("possible_monthly_saving") or 0.0))
        capped_monthly = min(monthly, remaining)
        if capped_monthly <= 0:
            continue
        item = dict(item)
        item["possible_monthly_saving"] = round(capped_monthly, 2)
        item["possible_yearly_saving"] = round(capped_monthly * 12.0, 2)
        capped_items.append(item)
        remaining -= capped_monthly
    return capped_items


def generate_saving_priority(transactions: list[Any], subscriptions: list[dict[str, Any]], duplicates: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank savings opportunities by impact and controllability."""
    safe_transactions = valid_transactions(transactions)
    projected_transactions = projection_transactions(safe_transactions)
    if not safe_transactions and not subscriptions and not duplicates:
        return empty_result([])

    items: list[dict[str, Any]] = []
    duplicate_saving = min(duplicate_monthly_saving(duplicates), controllable_spend_total(projected_transactions))
    if duplicate_saving > 0:
        items.append(
            opportunity(
                0,
                "Duplicate payments",
                "Exact or near-duplicate payments were detected.",
                duplicate_saving,
                "easy",
                "Review and dispute duplicate payments or request merchant reversal.",
            )
        )

    subscription_target, subscription_saving = high_cost_subscription_saving(subscriptions)
    if subscription_target and subscription_saving > 0:
        items.append(
            opportunity(
                0,
                subscription_target,
                "This is the highest recurring subscription cost detected.",
                subscription_saving,
                "easy",
                "Cancel, downgrade, or pause this subscription if it is not actively used.",
            )
        )

    want_category, want_saving, want_percentage = top_want_category_saving(projected_transactions)
    if want_category and want_saving > 0:
        items.append(
            opportunity(
                0,
                want_category,
                f"{want_category} is above 30% of spending at {want_percentage:.2f}%.",
                want_saving,
                "hard",
                "Set a category cap and reduce the top two merchants in this category.",
            )
        )

    small_spend_result = detect_small_spend_leakage(projected_transactions)
    small_spend_data = small_spend_result.get("data", {})
    small_spend_saving = float(small_spend_data.get("possible_monthly_saving") or 0.0) if isinstance(small_spend_data, dict) else 0.0
    if small_spend_saving > 0:
        items.append(
            opportunity(
                0,
                "Small spend leakage",
                "Frequent small debit transactions are adding up.",
                small_spend_saving,
                "medium",
                "Use a weekly UPI/snack cap and review purchases below ₹500.",
            )
        )

    charge_saving = bank_charge_saving(projected_transactions)
    if charge_saving > 0:
        items.append(
            opportunity(
                0,
                "Bank charges",
                "Bank charges and fees are usually controllable with account or payment behavior changes.",
                charge_saving,
                "easy",
                "Avoid failed payments, excess ATM withdrawals, and chargeable account actions.",
            )
        )

    items.sort(key=lambda item: float(item.get("possible_monthly_saving") or 0.0), reverse=True)
    controllable_cap = controllable_spend_total(projected_transactions)
    items = cap_saving_items(items, controllable_cap)
    for index, item in enumerate(items, start=1):
        item["rank"] = index
    warnings = [] if items else ["No clear savings opportunities detected"]
    excluded_count = sum(1 for transaction in safe_transactions if is_high_value_or_anomaly(transaction))
    if excluded_count:
        warnings.append(f"{excluded_count} high-value or anomalous transactions were excluded from savings projections and should be reviewed separately.")
    return service_result(items, warnings)


def category_total(category_breakdown: list[dict[str, Any]], category_name: str) -> float:
    """Return total spend for a category in a category breakdown list."""
    for item in category_breakdown:
        if item.get("category") == category_name:
            return float(item.get("total_amount") or 0.0)
    return 0.0


def classify_personality(transactions: list[Any], category_breakdown: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    """Classify spending personality using deterministic rule priority."""
    safe_transactions = valid_transactions(transactions)
    normal_transactions = actionable_transactions(safe_transactions)
    if not safe_transactions:
        return empty_result(
            {
                "personality_type": "Balanced Spender",
                "description": "There is not enough spending history to identify a dominant pattern.",
                "confidence": 0.0,
                "icon_suggestion": "scale",
            }
        )

    if isinstance(category_breakdown, dict):
        breakdown_items = category_breakdown.get("data", [])
    else:
        breakdown_items = category_breakdown or []
    normal_transactions = actionable_transactions(safe_transactions)
    total_spend = total_debit_spend(normal_transactions)
    wants_total = sum(float(item.get("total_amount") or 0.0) for item in breakdown_items if item.get("need_want_waste_type") == "want")
    food_total = category_total(breakdown_items, "Food & Dining")
    groceries_total = category_total(breakdown_items, "Groceries")
    shopping_total = category_total(breakdown_items, "Shopping")
    subscriptions_total = category_total(breakdown_items, "Subscriptions")
    bills_total = category_total(breakdown_items, "Bills & Utilities")
    emi_total = category_total(breakdown_items, "EMI & Loans")
    needs_total = sum(float(item.get("total_amount") or 0.0) for item in breakdown_items if item.get("need_want_waste_type") == "need")
    savings_total = sum(debit_amount(transaction, exclude_refunds=False) for transaction in valid_transactions(safe_transactions) if get_category(transaction) == "Investments & Savings" and not is_high_value_or_anomaly(transaction))
    income = estimate_income(safe_transactions)
    subscription_count = sum(1 for transaction in normal_transactions if get_category(transaction) == "Subscriptions")
    late_night_count = sum(1 for transaction in normal_transactions if bool(get_field(transaction, "is_late_night", False)))
    small_upi_count = sum(
        1
        for transaction in normal_transactions
        if 0 < debit_amount(transaction) < 500
        and "upi" in str(get_field(transaction, "description", "") or "").lower()
    )

    if wants_total > 0 and (food_total + groceries_total) / wants_total > 0.40:
        return service_result({"personality_type": "Food Spender", "description": "Food and grocery-adjacent spending dominates want spending.", "confidence": 0.9, "icon_suggestion": "utensils"}, [])
    if wants_total > 0 and shopping_total / wants_total > 0.30:
        return service_result({"personality_type": "Shopping Spender", "description": "Shopping is the strongest want-spend category.", "confidence": 0.9, "icon_suggestion": "shopping-bag"}, [])
    if subscription_count >= 5 or (subscriptions_total > 0 and ((income > 0 and subscriptions_total * 12.0 > income * 0.15) or subscriptions_total > total_spend * 0.15)):
        return service_result({"personality_type": "Subscription Leaker", "description": "Recurring digital or service payments are a major spend driver.", "confidence": 0.9, "icon_suggestion": "repeat"}, [])

    if normal_transactions and late_night_count / len(normal_transactions) >= 0.30:
        return service_result({"personality_type": "Late-Night Spender", "description": "A large share of spending happens late at night.", "confidence": 0.82, "icon_suggestion": "moon"}, [])
    if small_upi_count >= 5 and small_upi_count / max(len(normal_transactions), 1) >= 0.40:
        return service_result({"personality_type": "Small UPI Spender", "description": "Frequent small UPI payments are the strongest spending pattern.", "confidence": 0.82, "icon_suggestion": "smartphone"}, [])

    weekend_result = weekend_spend_ratio(safe_transactions)
    if weekend_result > 2.0:
        return service_result({"personality_type": "Weekend Spender", "description": "Weekend daily spending is more than 2x weekday spending.", "confidence": 0.85, "icon_suggestion": "calendar-days"}, [])

    transfer_count = sum(1 for transaction in safe_transactions if get_category(transaction) == "Transfers")
    if len(safe_transactions) > 0 and transfer_count / len(safe_transactions) > 0.30:
        return service_result({"personality_type": "Transfer-Heavy", "description": "A large share of transactions are transfers, so personal merchant review matters.", "confidence": 0.85, "icon_suggestion": "send"}, [])
    if needs_total > 0 and (bills_total + emi_total) / needs_total > 0.50:
        return service_result({"personality_type": "Bill-Heavy", "description": "Bills and EMI dominate need-based spending.", "confidence": 0.85, "icon_suggestion": "receipt"}, [])

    miscellaneous_total = category_total(breakdown_items, "Miscellaneous")
    small_count = sum(1 for transaction in normal_transactions if 0 < debit_amount(transaction) < 500)
    if total_spend > 0 and miscellaneous_total / total_spend > 0.20 and small_count >= 5:
        return service_result({"personality_type": "Impulse Spender", "description": "High miscellaneous spend and many small transactions suggest impulse leakage.", "confidence": 0.8, "icon_suggestion": "zap"}, [])

    largest_want_share = 0.0
    if wants_total > 0:
        largest_want_share = max(
            [float(item.get("total_amount") or 0.0) / wants_total for item in breakdown_items if item.get("need_want_waste_type") == "want"] or [0.0]
        )
    if largest_want_share <= 0.25 and savings_total > 0:
        return service_result({"personality_type": "Balanced Spender", "description": "No single want category dominates and savings activity is present.", "confidence": 0.8, "icon_suggestion": "scale"}, [])

    return service_result({"personality_type": "Balanced Spender", "description": "No dominant spending pattern was strong enough for a specific label.", "confidence": 0.6, "icon_suggestion": "scale"}, [])


def weekend_spend_ratio(transactions: list[Any]) -> float:
    """Return weekend daily average divided by weekday daily average."""
    weekend_total = 0.0
    weekday_total = 0.0
    weekend_dates: set[str] = set()
    weekday_dates: set[str] = set()
    for transaction in valid_transactions(transactions):
        if is_high_value_or_anomaly(transaction):
            continue
        amount = debit_amount(transaction)
        parsed_date = parse_date(get_field(transaction, "transaction_date", None))
        if amount <= 0 or parsed_date is None:
            continue
        if parsed_date.weekday() >= 5:
            weekend_total += amount
            weekend_dates.add(parsed_date.isoformat())
        else:
            weekday_total += amount
            weekday_dates.add(parsed_date.isoformat())
    weekend_average = weekend_total / len(weekend_dates) if weekend_dates else 0.0
    weekday_average = weekday_total / len(weekday_dates) if weekday_dates else 0.0
    if weekday_average <= 0:
        return 0.0
    return weekend_average / weekday_average
