"""Explain month-over-month financial changes in plain language."""

from __future__ import annotations

from typing import Any

from services.analytics_utils import debit_amount, display_merchant_name, get_category, get_field, normalize_merchant_name, service_result, valid_transactions
from services.monthly_analysis import calculate_monthly_analysis, split_transactions_by_month
from services.subscription_detector import detect_subscriptions


def money_text(value: float) -> str:
    """Return rupee text with Indian-style comma separators for explanations."""
    sign = "-" if value < 0 else ""
    amount = abs(float(value or 0.0))
    return f"{sign}₹{amount:,.2f}"


def totals_by_category(transactions: list[Any]) -> dict[str, float]:
    """Return debit spending totals grouped by category."""
    totals: dict[str, float] = {}
    for transaction in valid_transactions(transactions):
        amount = debit_amount(transaction)
        if amount <= 0:
            continue
        category = get_category(transaction)
        totals[category] = totals.get(category, 0.0) + amount
    return totals


def totals_by_merchant(transactions: list[Any]) -> dict[str, float]:
    """Return debit spending totals grouped by merchant."""
    totals: dict[str, float] = {}
    for transaction in valid_transactions(transactions):
        amount = debit_amount(transaction)
        if amount <= 0:
            continue
        merchant = display_merchant_name(get_field(transaction, "merchant", None))
        totals[merchant] = totals.get(merchant, 0.0) + amount
    return totals


def row_delta_rows(previous: dict[str, float], current: dict[str, float], row_type: str, limit: int = 5) -> list[dict[str, Any]]:
    """Return sorted spend deltas for categories or merchants."""
    keys = set(previous) | set(current)
    rows = []
    for key in keys:
        previous_value = round(previous.get(key, 0.0), 2)
        current_value = round(current.get(key, 0.0), 2)
        change = round(current_value - previous_value, 2)
        if abs(change) < 1:
            continue
        rows.append(
            {
                "name": key,
                "type": row_type,
                "previous_amount": previous_value,
                "current_amount": current_value,
                "change_amount": change,
                "direction": "increased" if change > 0 else "decreased",
            }
        )
    return sorted(rows, key=lambda item: abs(float(item.get("change_amount", 0.0))), reverse=True)[:limit]


def subscription_names(transactions: list[Any]) -> set[str]:
    """Return normalized names of subscriptions detected in a transaction group."""
    result = detect_subscriptions(transactions)
    rows = result.get("data", []) if isinstance(result.get("data", []), list) else []
    return {normalize_merchant_name(row.get("merchant")) for row in rows if normalize_merchant_name(row.get("merchant"))}


def build_headline(previous_label: str, current_label: str, spend_change: float, income_change: float) -> str:
    """Return the headline explanation for latest month movement."""
    if spend_change > 0:
        return f"{current_label} spending increased by {money_text(spend_change)} versus {previous_label}."
    if spend_change < 0:
        return f"{current_label} spending decreased by {money_text(abs(spend_change))} versus {previous_label}."
    if income_change != 0:
        direction = "increased" if income_change > 0 else "decreased"
        return f"Spending stayed flat, while detected income {direction} by {money_text(abs(income_change))}."
    return f"{current_label} looked almost unchanged compared with {previous_label}."


def build_driver_sentences(category_drivers: list[dict[str, Any]], merchant_drivers: list[dict[str, Any]], new_subscriptions: list[str]) -> list[str]:
    """Return concise explanation bullets for visible month changes."""
    drivers: list[str] = []
    increased_categories = [row for row in category_drivers if row.get("direction") == "increased"]
    decreased_categories = [row for row in category_drivers if row.get("direction") == "decreased"]
    if increased_categories:
        top = increased_categories[0]
        drivers.append(f"Biggest increase: {top['name']} rose by {money_text(abs(float(top['change_amount'])))}.")
    if decreased_categories:
        top = decreased_categories[0]
        drivers.append(f"Biggest improvement: {top['name']} reduced by {money_text(abs(float(top['change_amount'])))}.")
    increased_merchants = [row for row in merchant_drivers if row.get("direction") == "increased"]
    if increased_merchants:
        top = increased_merchants[0]
        drivers.append(f"Merchant impact: {top['name']} increased by {money_text(abs(float(top['change_amount'])))}.")
    if new_subscriptions:
        drivers.append(f"New recurring payment detected: {', '.join(new_subscriptions[:3])}.")
    if not drivers:
        drivers.append("No single category or merchant created a major month-over-month movement.")
    return drivers


def explain_latest_month_change(transactions: list[Any]) -> dict[str, Any]:
    """Explain why the latest month changed versus the previous available month."""
    grouped = split_transactions_by_month(transactions)
    if len(grouped) < 2:
        return service_result(
            {"headline": "At least two months are needed to explain what changed.", "drivers": [], "category_drivers": [], "merchant_drivers": [], "new_subscriptions": []},
            ["Upload at least two months of transactions to explain month-over-month movement."],
        )
    month_keys = list(grouped.keys())
    previous_key = month_keys[-2]
    current_key = month_keys[-1]
    monthly_result = calculate_monthly_analysis(transactions)
    months = monthly_result.get("data", {}).get("months", []) if isinstance(monthly_result.get("data", {}), dict) else []
    previous_month = next((row for row in months if row.get("month") == previous_key), {})
    current_month = next((row for row in months if row.get("month") == current_key), {})
    spend_change = float(current_month.get("actionable_spend", 0.0) or 0.0) - float(previous_month.get("actionable_spend", 0.0) or 0.0)
    income_change = float(current_month.get("total_received", 0.0) or 0.0) - float(previous_month.get("total_received", 0.0) or 0.0)
    category_drivers = row_delta_rows(totals_by_category(grouped[previous_key]), totals_by_category(grouped[current_key]), "category", limit=6)
    merchant_drivers = row_delta_rows(totals_by_merchant(grouped[previous_key]), totals_by_merchant(grouped[current_key]), "merchant", limit=6)
    previous_subscriptions = subscription_names(grouped[previous_key])
    current_subscriptions = subscription_names(grouped[current_key])
    new_subscription_keys = current_subscriptions - previous_subscriptions
    display_lookup = {normalize_merchant_name(get_field(transaction, "merchant", None)): display_merchant_name(get_field(transaction, "merchant", None)) for transaction in grouped[current_key]}
    new_subscriptions = [display_lookup.get(key, key.title()) for key in sorted(new_subscription_keys)]
    headline = build_headline(str(previous_month.get("label", previous_key)), str(current_month.get("label", current_key)), spend_change, income_change)
    drivers = build_driver_sentences(category_drivers, merchant_drivers, new_subscriptions)
    result = {
        "from_month": previous_key,
        "to_month": current_key,
        "from_label": previous_month.get("label", previous_key),
        "to_label": current_month.get("label", current_key),
        "spending_change": round(spend_change, 2),
        "income_change": round(income_change, 2),
        "headline": headline,
        "drivers": drivers,
        "category_drivers": category_drivers,
        "merchant_drivers": merchant_drivers,
        "new_subscriptions": new_subscriptions,
        "improved_categories": [row for row in category_drivers if row.get("direction") == "decreased"],
        "worsened_categories": [row for row in category_drivers if row.get("direction") == "increased"],
    }
    return service_result(result, monthly_result.get("warnings", []))
