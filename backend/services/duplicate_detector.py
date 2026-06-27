"""Duplicate debit transaction detector."""

from __future__ import annotations

from itertools import combinations
from typing import Any

from services.analytics_utils import debit_amount, display_merchant_name, empty_result, get_category, get_field, is_high_value_or_anomaly, normalize_merchant_name, parse_date, service_result, transaction_id, valid_transactions

SUBSCRIPTION_MERCHANT_KEYWORDS = {
    "netflix",
    "spotify",
    "prime video",
    "hotstar",
    "disney",
    "youtube premium",
    "canva",
    "adobe",
    "google one",
    "icloud",
    "dropbox",
    "notion",
    "slack",
    "zoom",
    "github",
    "chatgpt",
    "openai",
    "anthropic",
    "linkedin premium",
}


def merchant_is_subscription_like(merchant_normalized: str) -> bool:
    """Return True when a merchant should be excluded from duplicate detection as recurring infrastructure."""
    if not merchant_normalized:
        return False
    return any(keyword in merchant_normalized for keyword in SUBSCRIPTION_MERCHANT_KEYWORDS)


def transaction_is_duplicate_candidate(transaction: Any) -> bool:
    """Return True when a transaction can be compared for duplicate detection."""
    if debit_amount(transaction) <= 0:
        return False
    if bool(get_field(transaction, "is_refund", False)) or bool(get_field(transaction, "is_cashback", False)):
        return False
    category = get_category(transaction)
    if category in {"Transfers", "Cash Withdrawal", "Subscriptions"}:
        return False
    if bool(get_field(transaction, "is_subscription", False)):
        return False
    if is_high_value_or_anomaly(transaction):
        return False
    merchant_normalized = normalize_merchant_name(get_field(transaction, "merchant", None))
    if not merchant_normalized:
        return False
    if merchant_is_subscription_like(merchant_normalized):
        return False
    return parse_date(get_field(transaction, "transaction_date", None)) is not None


def build_duplicate_pair(transaction_one: Any, transaction_two: Any, confidence: float, reason: str) -> dict[str, Any]:
    """Build a duplicate pair response row."""
    date_one = parse_date(get_field(transaction_one, "transaction_date", None))
    date_two = parse_date(get_field(transaction_two, "transaction_date", None))
    duplicate_date = min(date_one, date_two).isoformat() if date_one and date_two else None
    return {
        "transaction_id_1": transaction_id(transaction_one),
        "transaction_id_2": transaction_id(transaction_two),
        "merchant": display_merchant_name(get_field(transaction_one, "merchant", None)),
        "amount": round(debit_amount(transaction_one), 2),
        "duplicate_date": duplicate_date,
        "confidence_score": round(float(confidence), 2),
        "reason": reason,
    }


def detect_duplicates(transactions: list[Any]) -> dict[str, Any]:
    """Detect exact and near-duplicate debit transactions without comparing transfers."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result([])

    candidates = [transaction for transaction in safe_transactions if transaction_is_duplicate_candidate(transaction)]
    duplicates: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str | None, str | None]] = set()
    for transaction_one, transaction_two in combinations(candidates, 2):
        merchant_one = normalize_merchant_name(get_field(transaction_one, "merchant", None))
        merchant_two = normalize_merchant_name(get_field(transaction_two, "merchant", None))
        if merchant_one != merchant_two:
            continue
        amount_one = round(debit_amount(transaction_one), 2)
        amount_two = round(debit_amount(transaction_two), 2)
        if amount_one != amount_two:
            continue
        date_one = parse_date(get_field(transaction_one, "transaction_date", None))
        date_two = parse_date(get_field(transaction_two, "transaction_date", None))
        if date_one is None or date_two is None:
            continue
        day_gap = abs((date_one - date_two).days)
        pair_key = tuple(sorted([transaction_id(transaction_one) or str(id(transaction_one)), transaction_id(transaction_two) or str(id(transaction_two))]))
        if pair_key in seen_pairs:
            continue
        if day_gap == 0:
            duplicates.append(build_duplicate_pair(transaction_one, transaction_two, 0.95, "Same merchant, same amount, same date"))
            seen_pairs.add(pair_key)
        elif day_gap <= 2:
            duplicates.append(build_duplicate_pair(transaction_one, transaction_two, 0.75, "Same merchant and amount within 2 days"))
            seen_pairs.add(pair_key)
    duplicates.sort(key=lambda item: float(item.get("confidence_score") or 0.0), reverse=True)
    return service_result(duplicates, [] if duplicates else ["No duplicate payments detected"])
