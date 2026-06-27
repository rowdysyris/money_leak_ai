"""Merchant, yearly-impact, weekend, and late-night spending analytics."""

from __future__ import annotations

from typing import Any

from services.analytics_utils import (
    CATEGORY_NEED_WANT_WASTE,
    actionable_transactions,
    debit_amount,
    display_merchant_name,
    empty_result,
    get_category,
    get_field,
    parse_date,
    parse_time,
    percentage,
    service_result,
    total_debit_spend,
    valid_transactions,
)




def dominant_year_dates(dates: list[Any]) -> list[Any]:
    """Return dates from the most common year to remove isolated date outliers."""
    if not dates:
        return []
    year_counts: dict[int, int] = {}
    for item in dates:
        year_counts[item.year] = year_counts.get(item.year, 0) + 1
    dominant_year = max(year_counts.items(), key=lambda item: item[1])[0]
    filtered = [item for item in dates if item.year == dominant_year]
    return filtered or dates


def analyze_merchants(transactions: list[Any], limit: int = 10) -> dict[str, Any]:
    """Return merchant-level spend totals and counts."""
    from services.dashboard_service import get_top_merchants

    return get_top_merchants(transactions, limit=limit)


def get_yearly_impact(transactions: list[Any]) -> dict[str, Any]:
    """Return category spending annualized from the uploaded statement period."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result([])

    warnings: list[str] = []
    normal_transactions = actionable_transactions(safe_transactions)
    dates = dominant_year_dates([parsed for parsed in (parse_date(get_field(transaction, "transaction_date")) for transaction in normal_transactions) if parsed])
    if len(dates) >= 2:
        period_days = max(1, (max(dates) - min(dates)).days + 1)
        annual_multiplier = 365.0 / period_days
    else:
        period_days = 30
        annual_multiplier = 12.0
        warnings.append("Not enough date data; yearly impact assumes one month of spending.")

    grouped: dict[str, float] = {}
    for transaction in normal_transactions:
        amount = debit_amount(transaction)
        if amount <= 0:
            continue
        category = get_category(transaction)
        grouped[category] = grouped.get(category, 0.0) + amount
    result = []
    for category, amount in grouped.items():
        result.append(
            {
                "category": category,
                "period_amount": round(amount, 2),
                "annualized_amount": round(amount * annual_multiplier, 2),
                "need_want_waste_type": CATEGORY_NEED_WANT_WASTE.get(category, "unknown"),
                "period_days": period_days,
            }
        )
    result.sort(key=lambda item: float(item.get("annualized_amount") or 0.0), reverse=True)
    return service_result(result, warnings if result else ["No category spending found"])


def compare_weekend_vs_weekday(transactions: list[Any]) -> dict[str, Any]:
    """Compare weekend spending against weekday spending."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result(
            {
                "weekend_total": 0.0,
                "weekday_total": 0.0,
                "weekend_daily_average": 0.0,
                "weekday_daily_average": 0.0,
                "weekend_vs_weekday_ratio": 0.0,
                "insight": "No transactions found",
            }
        )

    warnings: list[str] = []
    weekend_total = 0.0
    weekday_total = 0.0
    weekend_dates: set[str] = set()
    weekday_dates: set[str] = set()
    missing_dates = 0
    missing_times = 0
    normal_transactions = actionable_transactions(safe_transactions)
    for transaction in normal_transactions:
        amount = debit_amount(transaction)
        if amount <= 0:
            continue
        if parse_time(get_field(transaction, "transaction_time", None)) is None:
            missing_times += 1
        parsed_date = parse_date(get_field(transaction, "transaction_date", None))
        if parsed_date is None:
            missing_dates += 1
            continue
        if parsed_date.weekday() >= 5:
            weekend_total += amount
            weekend_dates.add(parsed_date.isoformat())
        else:
            weekday_total += amount
            weekday_dates.add(parsed_date.isoformat())
    if missing_dates:
        warnings.append("Some transactions were skipped because transaction dates are missing.")
    if missing_times:
        warnings.append("Some transaction_time values are missing; weekend comparison uses dates only.")
    weekend_daily_average = round(weekend_total / len(weekend_dates), 2) if weekend_dates else 0.0
    weekday_daily_average = round(weekday_total / len(weekday_dates), 2) if weekday_dates else 0.0
    ratio = round(weekend_daily_average / weekday_daily_average, 2) if weekday_daily_average > 0 else 0.0
    insight = "Weekend spending is under control."
    if ratio > 2:
        insight = "Weekend spending is more than 2x weekday daily average."
    data = {
        "weekend_total": round(weekend_total, 2),
        "weekday_total": round(weekday_total, 2),
        "weekend_daily_average": weekend_daily_average,
        "weekday_daily_average": weekday_daily_average,
        "weekend_vs_weekday_ratio": ratio,
        "insight": insight,
    }
    return service_result(data, warnings)


def analyze_late_night_spending(transactions: list[Any]) -> dict[str, Any]:
    """Analyze debit spending between 22:00 and 02:59, warning when time data is missing."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result(
            {
                "late_night_total": 0.0,
                "late_night_count": 0,
                "percentage_of_total_spend": 0.0,
                "top_merchants": [],
            }
        )

    warnings: list[str] = []
    normal_transactions = actionable_transactions(safe_transactions)
    total_spend = total_debit_spend(normal_transactions)
    missing_time = 0
    late_transactions = []
    for transaction in normal_transactions:
        amount = debit_amount(transaction)
        if amount <= 0:
            continue
        parsed_time = parse_time(get_field(transaction, "transaction_time", None))
        if parsed_time is None:
            missing_time += 1
            continue
        if parsed_time.hour >= 22 or parsed_time.hour <= 2:
            late_transactions.append(transaction)
    if missing_time:
        warnings.append("Some transaction_time values are missing, so late-night spending may be incomplete.")
    merchant_totals: dict[str, float] = {}
    for transaction in late_transactions:
        merchant = display_merchant_name(get_field(transaction, "merchant", None))
        merchant_totals[merchant] = merchant_totals.get(merchant, 0.0) + debit_amount(transaction)
    top_merchants = [
        {"merchant": merchant, "total": round(total, 2)}
        for merchant, total in sorted(merchant_totals.items(), key=lambda item: item[1], reverse=True)[:5]
    ]
    late_total = round(sum(debit_amount(transaction) for transaction in late_transactions), 2)
    data = {
        "late_night_total": late_total,
        "late_night_count": len(late_transactions),
        "percentage_of_total_spend": percentage(late_total, total_spend),
        "top_merchants": top_merchants,
    }
    return service_result(data, warnings)
