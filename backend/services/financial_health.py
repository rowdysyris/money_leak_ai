"""Income-aware financial health score service."""

from __future__ import annotations

from typing import Any

from services.analytics_utils import (
    debit_amount,
    empty_result,
    estimate_income,
    get_category,
    get_need_want_waste_type,
    is_high_value_or_anomaly,
    percentage,
    service_result,
    total_credit_received,
    valid_transactions,
)


def detected_income_total(transactions: list[Any]) -> float:
    """Return credits that look like actual income instead of refunds or transfers."""
    total = 0.0
    for transaction in valid_transactions(transactions):
        category = get_category(transaction)
        if category == "Income":
            from services.analytics_utils import credit_amount
            total += credit_amount(transaction)
    return round(total if total > 0 else total_credit_received(transactions), 2)


def spending_totals_by_behavior(transactions: list[Any]) -> dict[str, float]:
    """Return spending totals by need, want, waste, savings, and debt pressure."""
    totals = {"needs": 0.0, "wants": 0.0, "waste": 0.0, "savings": 0.0, "debt": 0.0}
    for transaction in valid_transactions(transactions):
        if is_high_value_or_anomaly(transaction):
            continue
        amount = debit_amount(transaction, exclude_refunds=True)
        if amount <= 0:
            continue
        category = get_category(transaction)
        label = get_need_want_waste_type(transaction)
        if label == "need":
            totals["needs"] += amount
        elif label == "want":
            totals["wants"] += amount
        elif label == "waste":
            totals["waste"] += amount
        elif label == "savings":
            totals["savings"] += amount
        if category == "EMI & Loans":
            totals["debt"] += amount
    return {key: round(value, 2) for key, value in totals.items()}


def calculate_health_score(transactions: list[Any]) -> dict[str, Any]:
    """Return an income-aware financial health score and drivers."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result({"score": 0, "status": "No data", "drivers": []})

    income_total = detected_income_total(safe_transactions)
    income_baseline = estimate_income(safe_transactions)
    totals = spending_totals_by_behavior(safe_transactions)
    denominator = income_total if income_total > 0 else income_baseline
    if denominator <= 0:
        denominator = max(sum(totals.values()), 1.0)

    needs_ratio = percentage(totals["needs"], denominator)
    wants_ratio = percentage(totals["wants"], denominator)
    waste_ratio = percentage(totals["waste"], denominator)
    savings_ratio = percentage(totals["savings"], denominator)
    debt_ratio = percentage(totals["debt"], denominator)

    score = 70.0
    if savings_ratio >= 20:
        score += 15
    elif savings_ratio >= 10:
        score += 8
    else:
        score -= 12
    if wants_ratio > 45:
        score -= 12
    elif wants_ratio > 30:
        score -= 6
    if waste_ratio > 5:
        score -= 10
    elif waste_ratio > 2:
        score -= 5
    if debt_ratio > 40:
        score -= 15
    elif debt_ratio > 25:
        score -= 8
    if needs_ratio > 65:
        score -= 6
    score = int(max(0, min(100, round(score))))

    if score >= 80:
        status = "Strong"
    elif score >= 65:
        status = "Stable"
    elif score >= 45:
        status = "Needs Attention"
    else:
        status = "Risky"

    drivers = []
    drivers.append(f"Savings activity is {savings_ratio:.1f}% of detected income.")
    drivers.append(f"Want-category spend is {wants_ratio:.1f}% of detected income.")
    drivers.append(f"EMI and loan pressure is {debt_ratio:.1f}% of detected income.")
    if waste_ratio > 0:
        drivers.append(f"Waste and bank-charge spend is {waste_ratio:.1f}% of detected income.")

    data = {
        "score": score,
        "status": status,
        "income_total": round(income_total, 2),
        "monthly_income_baseline": round(income_baseline, 2),
        "needs_to_income_pct": needs_ratio,
        "wants_to_income_pct": wants_ratio,
        "waste_to_income_pct": waste_ratio,
        "savings_rate_pct": savings_ratio,
        "debt_pressure_pct": debt_ratio,
        "behavior_totals": totals,
        "drivers": drivers,
    }
    warnings = [] if income_total > 0 else ["Income could not be confidently separated; total credits were used as fallback."]
    return service_result(data, warnings)
