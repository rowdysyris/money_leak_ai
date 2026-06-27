"""Money leakage detection services for small spends and need/want/waste details."""

from __future__ import annotations

from typing import Any

from services.analytics_utils import (
    debit_amount,
    display_merchant_name,
    empty_result,
    get_category,
    get_field,
    get_need_want_waste_type,
    is_high_value_or_anomaly,
    service_result,
    total_debit_spend,
    valid_transactions,
)

EXCLUDED_SMALL_SPEND_CATEGORIES = {"Transfers", "Cash Withdrawal"}


def bucket_top_merchants(transactions: list[Any], limit: int = 5) -> list[dict[str, Any]]:
    """Return top merchants for a small-spend bucket."""
    grouped: dict[str, dict[str, Any]] = {}
    for transaction in transactions:
        merchant = display_merchant_name(get_field(transaction, "merchant", None))
        amount = debit_amount(transaction)
        if merchant not in grouped:
            grouped[merchant] = {"merchant": merchant, "total": 0.0, "count": 0}
        grouped[merchant]["total"] += amount
        grouped[merchant]["count"] += 1
    result = []
    for item in grouped.values():
        item["total"] = round(float(item.get("total") or 0.0), 2)
        result.append(item)
    result.sort(key=lambda value: float(value.get("total") or 0.0), reverse=True)
    return result[: max(1, int(limit or 5))]


def build_bucket(name: str, transactions: list[Any]) -> dict[str, Any]:
    """Build a leakage bucket summary."""
    total = round(sum(debit_amount(transaction) for transaction in transactions), 2)
    return {
        "bucket": name,
        "count": len(transactions),
        "total": total,
        "top_merchants": bucket_top_merchants(transactions),
    }


def detect_small_spend_leakage(transactions: list[Any]) -> dict[str, Any]:
    """Detect small debit transactions that can become recurring money leaks."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        empty_buckets = {
            "under_100": build_bucket("amount < 100", []),
            "between_100_200": build_bucket("100 <= amount < 200", []),
            "between_200_500": build_bucket("200 <= amount < 500", []),
            "bucket_under_100": build_bucket("amount < 100", []),
            "bucket_100_to_200": build_bucket("100 <= amount < 200", []),
            "bucket_200_to_500": build_bucket("200 <= amount < 500", []),
        }
        return empty_result(
            {
                **empty_buckets,
                "buckets": empty_buckets,
                "total_leakage": 0.0,
                "total_transactions": 0,
                "possible_monthly_saving": 0.0,
                "insight": "No transactions found",
            }
        )

    candidates = [
        transaction
        for transaction in safe_transactions
        if debit_amount(transaction) > 0
        and get_category(transaction) not in EXCLUDED_SMALL_SPEND_CATEGORIES
        and not is_high_value_or_anomaly(transaction)
    ]
    under_100 = [transaction for transaction in candidates if debit_amount(transaction) < 100]
    from_100_to_200 = [transaction for transaction in candidates if 100 <= debit_amount(transaction) < 200]
    from_200_to_500 = [transaction for transaction in candidates if 200 <= debit_amount(transaction) < 500]
    total_leakage = round(sum(debit_amount(transaction) for transaction in under_100 + from_100_to_200 + from_200_to_500), 2)
    count = len(under_100) + len(from_100_to_200) + len(from_200_to_500)
    saving = round(total_leakage * 0.30, 2)
    under_bucket = build_bucket("amount < 100", under_100)
    middle_bucket = build_bucket("100 <= amount < 200", from_100_to_200)
    upper_bucket = build_bucket("200 <= amount < 500", from_200_to_500)
    buckets = {
        "under_100": under_bucket,
        "between_100_200": middle_bucket,
        "between_200_500": upper_bucket,
        "bucket_under_100": under_bucket,
        "bucket_100_to_200": middle_bucket,
        "bucket_200_to_500": upper_bucket,
    }
    data = {
        **buckets,
        "buckets": buckets,
        "total_leakage": total_leakage,
        "total_transactions": count,
        "possible_monthly_saving": saving,
        "insight": f"You spent ₹{total_leakage:.2f} across {count} small transactions. If you reduced these by 30%, you could save ₹{saving:.2f}/month.",
    }
    return service_result(data, [] if count else ["No small-spend leakage detected"])


def serialize_transaction_brief(transaction: Any) -> dict[str, Any]:
    """Serialize a transaction into a compact analytics row."""
    return {
        "transaction_id": None if get_field(transaction, "id", None) is None else str(get_field(transaction, "id")),
        "date": None if get_field(transaction, "transaction_date", None) is None else str(get_field(transaction, "transaction_date")),
        "merchant": display_merchant_name(get_field(transaction, "merchant", None)),
        "category": get_category(transaction),
        "amount": round(debit_amount(transaction, exclude_refunds=False), 2),
        "description": str(get_field(transaction, "description", "") or ""),
    }


def detect_needs_wants_waste_detail(transactions: list[Any]) -> dict[str, Any]:
    """Return detailed want and waste candidates with annualized want impact."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result({"wants": [], "possible_waste": [], "yearly_wants_impact": 0.0})

    wants = [transaction for transaction in safe_transactions if get_need_want_waste_type(transaction) == "want" and debit_amount(transaction) > 0]
    total_spend = total_debit_spend([transaction for transaction in safe_transactions if not is_high_value_or_anomaly(transaction)])
    high_misc_threshold = max(1000.0, total_spend * 0.10)
    possible_waste = []
    for transaction in safe_transactions:
        category = get_category(transaction)
        amount = debit_amount(transaction)
        if amount <= 0 or is_high_value_or_anomaly(transaction):
            continue
        is_duplicate = bool(get_field(transaction, "is_duplicate", False))
        is_bank_charge = category == "Bank Charges & Fees"
        is_high_misc = category == "Miscellaneous" and amount >= high_misc_threshold
        if is_duplicate or is_bank_charge or is_high_misc:
            possible_waste.append(transaction)
    wants_sorted = sorted(wants, key=lambda transaction: debit_amount(transaction), reverse=True)
    waste_sorted = sorted(possible_waste, key=lambda transaction: debit_amount(transaction), reverse=True)
    monthly_wants = round(sum(debit_amount(transaction) for transaction in wants_sorted), 2)
    data = {
        "wants": [serialize_transaction_brief(transaction) for transaction in wants_sorted],
        "possible_waste": [serialize_transaction_brief(transaction) for transaction in waste_sorted],
        "monthly_wants_total": monthly_wants,
        "yearly_wants_impact": round(monthly_wants * 12.0, 2),
    }
    warnings = [] if wants_sorted or waste_sorted else ["No clear want or waste transactions found"]
    return service_result(data, warnings)
