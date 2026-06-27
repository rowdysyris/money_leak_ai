"""Money leak score calculation service."""

from __future__ import annotations

from typing import Any

from services.analytics_utils import actionable_transactions, debit_amount, empty_result, estimate_income, get_category, get_need_want_waste_type, is_high_value_or_anomaly, service_result, total_credit_received, total_debit_spend, valid_transactions


def cap_score(value: float) -> float:
    """Cap a component score to the 0-100 range."""
    return round(max(0.0, min(100.0, float(value or 0.0))), 2)


def severity_for_score(score: float) -> str:
    """Return severity label for a final money leak score."""
    if score <= 30:
        return "Healthy"
    if score <= 60:
        return "Leaking"
    if score <= 80:
        return "High Risk"
    return "Critical"


def diagnose_highest_component(components: dict[str, float], savings_rate: float = 0.0) -> str:
    """Generate a one-line diagnosis using the strongest component and savings context."""
    if not components:
        return "No spending pattern was available to diagnose."
    if savings_rate >= 20.0:
        return "Strong savings activity detected, but discretionary spending still has leakage."
    highest_component = max(components.items(), key=lambda item: item[1])[0]
    diagnoses = {
        "wants_ratio": "Want-category spending is the biggest leak driver.",
        "small_spend_ratio": "Small repeated spends are quietly increasing your leakage.",
        "subscription_burden": "Recurring subscriptions are putting pressure on your budget.",
        "duplicate_penalty": "Duplicate or repeated payments are the clearest savings opportunity.",
        "miscellaneous_ratio": "Too much spending is uncategorized, so review merchant categories.",
        "savings_deficit": "Savings activity is low compared with detected income.",
    }
    return diagnoses.get(highest_component, "Spending leakage is spread across multiple behaviors.")


def subscription_yearly_total(subscriptions: list[dict[str, Any]] | None) -> float:
    """Return the total yearly cost of detected subscriptions."""
    return round(sum(float(subscription.get("yearly_cost") or 0.0) for subscription in (subscriptions or [])), 2)


def calculate_score(transactions: list[Any], subscriptions: list[dict[str, Any]], duplicates: list[dict[str, Any]], budget: Any = None) -> dict[str, Any]:
    """Calculate a 0-100 money leak score from wants, small spends, subscriptions, duplicates, miscellaneous, and savings."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result(
            {
                "score": 0.0,
                "severity": "Healthy",
                "components": {},
                "diagnosis": "No transactions found",
            }
        )

    warnings: list[str] = []
    projected_transactions = actionable_transactions(safe_transactions)
    excluded_count = sum(1 for transaction in safe_transactions if is_high_value_or_anomaly(transaction))
    if excluded_count:
        warnings.append(f"{excluded_count} high-value or anomalous transactions were excluded from money leak score projections.")
    total_spend = total_debit_spend(projected_transactions)
    if total_spend <= 0:
        warnings.append("No debit spending found; score is based on limited data.")
    wants_total = sum(debit_amount(transaction) for transaction in projected_transactions if get_need_want_waste_type(transaction) == "want")
    small_spend_total = sum(debit_amount(transaction) for transaction in projected_transactions if debit_amount(transaction) < 500 and debit_amount(transaction) > 0)
    miscellaneous_total = sum(debit_amount(transaction) for transaction in projected_transactions if get_category(transaction) == "Miscellaneous")
    savings_total = sum(
        debit_amount(transaction, exclude_refunds=False)
        for transaction in safe_transactions
        if get_need_want_waste_type(transaction) == "savings" and not is_high_value_or_anomaly(transaction)
    )
    income = estimate_income(safe_transactions) or total_credit_received(safe_transactions)
    if income <= 0:
        warnings.append("No income detected; subscription burden and savings deficit may be approximate.")

    wants_ratio_score = cap_score((wants_total / total_spend) * 100.0 if total_spend > 0 else 0.0)
    small_spend_ratio_score = cap_score((small_spend_total / total_spend) * 100.0 if total_spend > 0 else 0.0)
    subscription_total = subscription_yearly_total(subscriptions)
    if income <= 0:
        subscription_burden_score = 50.0 if subscription_total > 0 else 20.0
    elif subscription_total > income * 0.20:
        subscription_burden_score = 80.0
    elif subscription_total > income * 0.10:
        subscription_burden_score = 50.0
    else:
        subscription_burden_score = 20.0
    duplicate_penalty_score = cap_score(len(duplicates or []) * 20.0)
    miscellaneous_ratio_score = cap_score((miscellaneous_total / total_spend) * 100.0 if total_spend > 0 else 0.0)
    if income <= 0:
        savings_deficit_score = 100.0 if savings_total <= 0 else 70.0
    elif savings_total <= 0:
        savings_deficit_score = 100.0
    elif savings_total < income * 0.10:
        savings_deficit_score = 70.0
    else:
        savings_deficit_score = 20.0

    components = {
        "wants_ratio": wants_ratio_score,
        "small_spend_ratio": small_spend_ratio_score,
        "subscription_burden": cap_score(subscription_burden_score),
        "duplicate_penalty": duplicate_penalty_score,
        "miscellaneous_ratio": miscellaneous_ratio_score,
        "savings_deficit": cap_score(savings_deficit_score),
    }
    score = round(
        components["wants_ratio"] * 0.30
        + components["small_spend_ratio"] * 0.20
        + components["subscription_burden"] * 0.15
        + components["duplicate_penalty"] * 0.15
        + components["miscellaneous_ratio"] * 0.10
        + components["savings_deficit"] * 0.10,
        2,
    )
    savings_rate = (savings_total / income * 100.0) if income > 0 else 0.0
    data = {
        "score": score,
        "severity": severity_for_score(score),
        "components": components,
        "diagnosis": diagnose_highest_component(components, savings_rate),
        "inputs": {
            "total_spend": round(total_spend, 2),
            "estimated_income": round(income, 2),
            "savings_total": round(savings_total, 2),
            "savings_rate_pct": round(savings_rate, 2),
            "subscriptions_yearly_cost": subscription_total,
            "duplicate_count": len(duplicates or []),
        },
    }
    return service_result(data, warnings)
