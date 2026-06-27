"""Shared defensive helpers for MoneyLeak AI analytics services."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

CATEGORY_NEED_WANT_WASTE = {
    "Food & Dining": "want",
    "Groceries": "need",
    "Shopping": "want",
    "Subscriptions": "want",
    "Entertainment": "want",
    "Travel & Transport": "want",
    "Rent & Housing": "need",
    "Bills & Utilities": "need",
    "Education": "need",
    "Health & Medical": "need",
    "Personal Care": "want",
    "EMI & Loans": "need",
    "Investments & Savings": "savings",
    "Bank Charges & Fees": "waste",
    "Transfers": "unknown",
    "Cash Withdrawal": "unknown",
    "Income": "unknown",
    "Refund/Cashback": "unknown",
    "Loan Credit": "unknown",
    "Investment Withdrawal": "savings",
    "Credit": "unknown",
    "Miscellaneous": "unknown",
}

EMPTY_TRANSACTION_WARNING = "No transactions found"
NO_STATEMENT_WARNING = "No statement uploaded yet. Upload a bank statement to see insights."


def service_result(data: Any, warnings: list[str] | None = None) -> dict[str, Any]:
    """Return a consistent analytics service payload."""
    return {"data": data, "warnings": warnings or []}


def empty_result(default_data: Any) -> dict[str, Any]:
    """Return the standard empty transaction analytics payload."""
    return service_result(default_data, [EMPTY_TRANSACTION_WARNING])


def get_field(transaction: Any, field_name: str, default: Any = None) -> Any:
    """Read a field from an ORM object or dictionary without raising on missing attributes."""
    if transaction is None:
        return default
    if isinstance(transaction, dict):
        return transaction.get(field_name, default)
    return getattr(transaction, field_name, default)


def enum_to_string(value: Any, default: str = "") -> str:
    """Convert strings and enum-like values to a safe lowercase string."""
    if value is None:
        return default
    raw_value = getattr(value, "value", value)
    return str(raw_value).strip()


def to_float(value: Any, default: float = 0.0) -> float:
    """Convert numeric-like values to float while protecting against NaN and infinity."""
    if value is None:
        return default
    if isinstance(value, Decimal):
        amount = float(value)
    else:
        raw_value = str(value).strip()
        if raw_value == "":
            return default
        cleaned = raw_value.replace("₹", "").replace(",", "").replace(" ", "")
        cleaned = re.sub(r"(?i)\b(rs\.?|inr)\b", "", cleaned)
        try:
            amount = float(cleaned)
        except (TypeError, ValueError):
            return default
    if math.isnan(amount) or math.isinf(amount):
        return default
    return amount


def parse_date(value: Any) -> date | None:
    """Parse a date-like field into a date object or return None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw_value = str(value).strip()
    if raw_value == "":
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d-%b-%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(raw_value, fmt).date()
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        return parsed.date()
    except ValueError:
        return None


def parse_time(value: Any) -> time | None:
    """Parse a time-like field into a time object or return None."""
    if value is None:
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time().replace(microsecond=0)
    raw_value = str(value).strip()
    if raw_value == "":
        return None
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"):
        try:
            return datetime.strptime(raw_value, fmt).time()
        except ValueError:
            continue
    return None


def normalize_merchant_name(value: Any) -> str:
    """Normalize a merchant name for grouping and comparisons."""
    raw_value = str(value or "").strip().lower()
    raw_value = re.sub(r"[^a-z0-9]+", " ", raw_value)
    return re.sub(r"\s+", " ", raw_value).strip()


def display_merchant_name(value: Any) -> str:
    """Return a human-readable merchant name with a safe fallback."""
    raw_value = str(value or "").strip()
    if raw_value == "" or raw_value.lower() == "none":
        return "Unknown"
    return raw_value


def get_category(transaction: Any) -> str:
    """Return a transaction category with a Miscellaneous fallback."""
    category = str(get_field(transaction, "category", "Miscellaneous") or "Miscellaneous").strip()
    return category if category else "Miscellaneous"


def get_need_want_waste_type(transaction: Any) -> str:
    """Return a transaction need/want/waste label using transaction value first and category fallback second."""
    explicit_value = enum_to_string(get_field(transaction, "need_want_waste_type", None), "").lower()
    if explicit_value in {"need", "want", "waste", "savings"}:
        return explicit_value
    return CATEGORY_NEED_WANT_WASTE.get(get_category(transaction), "unknown")


def is_refund(transaction: Any) -> bool:
    """Return True when a transaction is marked as refund or cashback."""
    return bool(get_field(transaction, "is_refund", False) or get_field(transaction, "is_cashback", False))


def is_debit(transaction: Any) -> bool:
    """Return True when a transaction should be treated as spending."""
    transaction_type = enum_to_string(get_field(transaction, "transaction_type", ""), "").lower()
    amount = to_float(get_field(transaction, "amount", 0.0))
    if transaction_type == "debit":
        return True
    if transaction_type == "credit":
        return False
    return amount < 0


def is_credit(transaction: Any) -> bool:
    """Return True when a transaction should be treated as received money."""
    transaction_type = enum_to_string(get_field(transaction, "transaction_type", ""), "").lower()
    amount = to_float(get_field(transaction, "amount", 0.0))
    if transaction_type == "credit":
        return True
    if transaction_type == "debit":
        return False
    return amount > 0


def debit_amount(transaction: Any, exclude_refunds: bool = True) -> float:
    """Return the absolute spending amount for debit transactions."""
    if exclude_refunds and is_refund(transaction):
        return 0.0
    if not is_debit(transaction):
        return 0.0
    return abs(to_float(get_field(transaction, "amount", 0.0)))


def credit_amount(transaction: Any) -> float:
    """Return the absolute received amount for credit transactions."""
    if not is_credit(transaction):
        return 0.0
    return abs(to_float(get_field(transaction, "amount", 0.0)))


def transaction_id(transaction: Any) -> str | None:
    """Return a transaction identifier string when available."""
    value = get_field(transaction, "id", None)
    return None if value is None else str(value)


def valid_transactions(transactions: list[Any] | None) -> list[Any]:
    """Return a safe list from any optional transaction input."""
    if transactions is None:
        return []
    if isinstance(transactions, list):
        return transactions
    return list(transactions)


def total_debit_spend(transactions: list[Any]) -> float:
    """Return total debit spending excluding refunds."""
    return round(sum(debit_amount(transaction) for transaction in valid_transactions(transactions)), 2)


def total_credit_received(transactions: list[Any]) -> float:
    """Return total credit received."""
    return round(sum(credit_amount(transaction) for transaction in valid_transactions(transactions)), 2)


def date_range(transactions: list[Any]) -> tuple[date | None, date | None]:
    """Return minimum and maximum transaction dates when present."""
    dates = [parsed for parsed in (parse_date(get_field(transaction, "transaction_date")) for transaction in valid_transactions(transactions)) if parsed]
    if not dates:
        return None, None
    return min(dates), max(dates)


def estimate_income(transactions: list[Any]) -> float:
    """Estimate income as the largest credit or recurring similar credit amount."""
    credits = [credit_amount(transaction) for transaction in valid_transactions(transactions) if credit_amount(transaction) > 0]
    if not credits:
        return 0.0
    rounded_counts: dict[int, int] = {}
    for value in credits:
        rounded_bucket = int(round(value / 500.0) * 500) if value >= 500 else int(round(value))
        rounded_counts[rounded_bucket] = rounded_counts.get(rounded_bucket, 0) + 1
    recurring_buckets = [bucket for bucket, count in rounded_counts.items() if count >= 2 and bucket > 0]
    if recurring_buckets:
        return float(max(recurring_buckets))
    return float(max(credits))


def percentage(numerator: float, denominator: float) -> float:
    """Return a rounded percentage capped to 0-100 while avoiding division by zero."""
    if denominator <= 0:
        return 0.0
    value = (numerator / denominator) * 100.0
    return round(max(0.0, min(100.0, value)), 2)

HIGH_VALUE_TRANSACTION_THRESHOLD = 1_000_000.0
NON_ACTIONABLE_CATEGORIES = {"Transfers", "Cash Withdrawal", "Investments & Savings"}


def is_high_value_or_anomaly(transaction: Any) -> bool:
    """Return True when a debit transaction should be treated as a separate review item."""
    amount = debit_amount(transaction, exclude_refunds=False)
    if amount > HIGH_VALUE_TRANSACTION_THRESHOLD:
        return True
    if bool(get_field(transaction, "is_anomaly", False)):
        return True
    category_source = str(get_field(transaction, "category_source", "") or "").strip()
    return category_source == "high_value_review"


def high_value_review_reason(transaction: Any) -> str:
    """Return a human-readable reason for separating a transaction from normal analytics."""
    amount = debit_amount(transaction, exclude_refunds=False)
    if amount > HIGH_VALUE_TRANSACTION_THRESHOLD:
        return "Debit amount is above ₹10,00,000 and needs manual review."
    if bool(get_field(transaction, "is_anomaly", False)):
        return "Transaction was marked as anomalous and needs manual review."
    return "Transaction needs manual review before it is used in analytics."


def serialize_high_value_review_transaction(transaction: Any) -> dict[str, Any]:
    """Serialize one high-value/anomaly transaction for dashboard review sections."""
    parsed_date = parse_date(get_field(transaction, "transaction_date", None))
    return {
        "transaction_id": transaction_id(transaction),
        "date": parsed_date.isoformat() if parsed_date else None,
        "merchant": display_merchant_name(get_field(transaction, "merchant", None)),
        "description": str(get_field(transaction, "description", "") or ""),
        "amount": round(debit_amount(transaction, exclude_refunds=False), 2),
        "category": get_category(transaction),
        "reason": high_value_review_reason(transaction),
    }


def high_value_review_transactions(transactions: list[Any]) -> list[dict[str, Any]]:
    """Return serialized anomaly transactions that should be reviewed outside normal analytics."""
    rows = [serialize_high_value_review_transaction(transaction) for transaction in valid_transactions(transactions) if is_high_value_or_anomaly(transaction)]
    rows.sort(key=lambda row: float(row.get("amount") or 0.0), reverse=True)
    return rows


def is_actionable_spend(transaction: Any) -> bool:
    """Return True when a transaction is safe to include in normal spend analytics."""
    amount = debit_amount(transaction)
    if amount <= 0:
        return False
    if is_refund(transaction):
        return False
    if is_high_value_or_anomaly(transaction):
        return False
    category = get_category(transaction)
    return category not in NON_ACTIONABLE_CATEGORIES


def actionable_transactions(transactions: list[Any]) -> list[Any]:
    """Return debit transactions used for normal dashboard analytics and category percentages."""
    return [transaction for transaction in valid_transactions(transactions) if is_actionable_spend(transaction)]


def total_actionable_spend(transactions: list[Any]) -> float:
    """Return debit spend after excluding review-only and non-actionable transaction classes."""
    return round(sum(debit_amount(transaction) for transaction in actionable_transactions(transactions)), 2)


def is_controllable_spend(transaction: Any) -> bool:
    """Return True when a transaction is reasonable to use in user-actionable savings projections."""
    if not is_actionable_spend(transaction):
        return False
    label = get_need_want_waste_type(transaction)
    if label == "need":
        return False
    return True


def controllable_spend_total(transactions: list[Any]) -> float:
    """Return total debit spend that can reasonably be reduced by user action."""
    return round(sum(debit_amount(transaction) for transaction in valid_transactions(transactions) if is_controllable_spend(transaction)), 2)


def projection_transactions(transactions: list[Any]) -> list[Any]:
    """Return transactions safe to include in savings, leakage, and recommendation projections."""
    return [transaction for transaction in valid_transactions(transactions) if not is_high_value_or_anomaly(transaction)]

