"""Burn-rate and month-end survival analytics service."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from services.analytics_utils import actionable_transactions, empty_result, estimate_income, get_field, high_value_review_transactions, parse_date, service_result, to_float, total_credit_received, total_debit_spend, valid_transactions
from services.subscription_detector import detect_subscriptions


def remaining_days_in_month(reference_date: date | None) -> int:
    """Return remaining calendar days in the month for a date."""
    if reference_date is None:
        return 0
    last_day = calendar.monthrange(reference_date.year, reference_date.month)[1]
    return max(0, last_day - reference_date.day)




def dominant_year_dates(dates: list[date]) -> list[date]:
    """Return dates from the most common year to remove old/future stress-test outliers."""
    if not dates:
        return []
    year_counts: dict[int, int] = {}
    for item in dates:
        year_counts[item.year] = year_counts.get(item.year, 0) + 1
    dominant_year = max(year_counts.items(), key=lambda item: item[1])[0]
    filtered = [item for item in dates if item.year == dominant_year]
    return filtered or dates


def fixed_upcoming_payments(subscriptions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return subscriptions predicted in the next 30 days."""
    upcoming = []
    for subscription in subscriptions:
        monthly_cost = float(subscription.get("monthly_cost") or 0.0)
        if monthly_cost <= 0:
            continue
        upcoming.append(
            {
                "merchant": subscription.get("merchant"),
                "predicted_date": subscription.get("next_predicted_date"),
                "estimated_amount": round(monthly_cost, 2),
                "frequency": subscription.get("frequency"),
            }
        )
    return upcoming


def analyze_burn_rate(transactions: list[Any], current_balance: float | None = None) -> dict[str, Any]:
    """Analyze income, daily burn rate, monthly projection, and survival estimates."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result(
            {
                "estimated_income": 0.0,
                "daily_burn_rate": 0.0,
                "monthly_projection": 0.0,
                "days_until_empty": None,
                "will_survive_month": None,
                "daily_safe_limit": None,
                "upcoming_fixed_payments": [],
            }
        )

    warnings: list[str] = []
    income = estimate_income(safe_transactions)
    if income <= 0:
        income = total_credit_received(safe_transactions)
    if income <= 0:
        warnings.append("Could not detect income. Results may be inaccurate.")

    normal_transactions = actionable_transactions(safe_transactions)
    dates = dominant_year_dates([parsed for parsed in (parse_date(get_field(transaction, "transaction_date")) for transaction in normal_transactions) if parsed])
    if not dates:
        warnings.append("Transaction dates are missing, so burn-rate period could not be calculated.")
        days_in_period = 0
        reference_date = None
    else:
        start_date = min(dates)
        reference_date = max(dates)
        days_in_period = max(1, (reference_date - start_date).days + 1)
        if days_in_period < 7:
            warnings.append("Not enough data")

    review_rows = high_value_review_transactions(safe_transactions)
    if review_rows:
        warnings.append(f"{len(review_rows)} high-value transaction(s) were excluded from burn-rate projection.")
    total_debit = total_debit_spend(normal_transactions)
    daily_burn_rate = round(total_debit / days_in_period, 2) if days_in_period > 0 else 0.0
    monthly_projection = round(daily_burn_rate * 30.0, 2)

    balance_value = to_float(current_balance, 0.0) if current_balance is not None else None
    days_until_empty = None
    will_survive_month = None
    daily_safe_limit = None
    subscription_result = detect_subscriptions(safe_transactions)
    subscriptions = subscription_result.get("data", [])
    upcoming_fixed = fixed_upcoming_payments(subscriptions)
    estimated_fixed_upcoming = round(sum(float(item.get("estimated_amount") or 0.0) for item in upcoming_fixed), 2)
    remaining_days = remaining_days_in_month(reference_date)
    if balance_value is None:
        warnings.append("Current balance was not provided, so month-end survival could not be calculated.")
    elif daily_burn_rate > 0:
        days_until_empty = round(balance_value / daily_burn_rate, 2)
        will_survive_month = days_until_empty > remaining_days if remaining_days > 0 else None
        daily_safe_limit = round(max(0.0, balance_value - estimated_fixed_upcoming) / remaining_days, 2) if remaining_days > 0 else None
    else:
        days_until_empty = None
        will_survive_month = True if balance_value >= 0 else False
        daily_safe_limit = round(balance_value / remaining_days, 2) if remaining_days > 0 else None

    data = {
        "estimated_income": round(income, 2),
        "total_debit": round(total_debit, 2),
        "days_in_period": days_in_period,
        "daily_burn_rate": daily_burn_rate,
        "monthly_projection": monthly_projection,
        "days_until_empty": days_until_empty,
        "will_survive_month": will_survive_month,
        "daily_safe_limit": daily_safe_limit,
        "upcoming_fixed_payments": upcoming_fixed,
        "estimated_fixed_upcoming": estimated_fixed_upcoming,
        "remaining_days_in_month": remaining_days,
    }
    return service_result(data, list(dict.fromkeys(warnings + subscription_result.get("warnings", []))))
