"""Deterministic merchant concentration and repeat-spend risk scoring."""

from __future__ import annotations

from typing import Any

from services.analytics_utils import debit_amount, display_merchant_name, get_field, valid_transactions


def calculate_merchant_risk(merchant: str, transactions: list[Any]) -> dict[str, Any]:
    """Return a bounded risk profile for one merchant's debit transactions."""
    normalized = str(merchant or "Unknown").strip().lower()
    matching = [
        item
        for item in valid_transactions(transactions)
        if str(get_field(item, "merchant", "Unknown") or "Unknown").strip().lower() == normalized
        and debit_amount(item) > 0
    ]
    total_spent = round(sum(debit_amount(item) for item in matching), 2)
    count = len(matching)
    frequency_score = min(count / 50.0, 1.0)
    spend_score = min(total_spent / 25000.0, 1.0)
    addiction_score = round(min((frequency_score * 0.7) + (spend_score * 0.3), 1.0), 4)
    risk_level = "high" if count >= 50 or addiction_score >= 0.7 else "medium" if count >= 8 or addiction_score >= 0.35 else "low"
    controllability = "easy" if risk_level == "low" else "moderate" if risk_level == "medium" else "difficult"
    insight = "No repeat-spend pattern was found."
    if matching:
        insight = f"{count} payment(s) total INR {total_spent:.2f}; review frequency before reducing essential spend."
    return {
        "merchant": display_merchant_name(merchant),
        "risk_level": risk_level,
        "addiction_score": addiction_score,
        "total_spent": total_spent,
        "transaction_count": count,
        "controllability": controllability,
        "insight": insight,
    }


def top_merchant_risks(transactions: list[Any], limit: int = 5) -> list[dict[str, Any]]:
    """Return the highest-risk merchant profiles, capped to the requested limit."""
    merchants = {
        str(get_field(item, "merchant", "Unknown") or "Unknown").strip()
        for item in valid_transactions(transactions)
        if debit_amount(item) > 0
    }
    results = [calculate_merchant_risk(merchant, transactions) for merchant in merchants]
    results.sort(key=lambda item: (float(item["addiction_score"]), float(item["total_spent"])), reverse=True)
    return results[: max(0, int(limit))]
