"""Defensive transaction cleaning service for parsed bank statements."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time
from typing import Any

import pandas as pd

from services.merchant_extractor import clean_merchant, merchant_needs_review

DATE_FORMATS = [
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d-%b-%Y",
    "%b %d %Y",
    "%d/%m/%y",
    "%d-%m-%y",
]

REFUND_KEYWORDS = ["refund", "reversal", "reversed", "cashback", "cash back", "chargeback", "returned"]
CREDIT_DESCRIPTION_KEYWORDS = ["credited", "credit", "received", "salary", "deposit", "cashback", "refund", "reversal"]
HIGH_VALUE_TRANSACTION_THRESHOLD = 1_000_000.0


def is_empty_value(value: Any) -> bool:
    """Return True when a value should be treated as empty."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        return False
    return str(value).strip() == ""


def parse_transaction_datetime(value: Any) -> tuple[date | None, time | None]:
    """Parse a transaction date value and preserve time when available."""
    if is_empty_value(value):
        return None, None

    if isinstance(value, pd.Timestamp):
        python_dt = value.to_pydatetime()
        parsed_time = python_dt.time().replace(microsecond=0) if python_dt.time() != time(0, 0) else None
        return python_dt.date(), parsed_time

    if isinstance(value, datetime):
        parsed_time = value.time().replace(microsecond=0) if value.time() != time(0, 0) else None
        return value.date(), parsed_time

    if isinstance(value, date):
        return value, None

    raw_value = str(value).strip()
    for date_format in DATE_FORMATS:
        try:
            parsed = datetime.strptime(raw_value, date_format)
            return parsed.date(), None
        except ValueError:
            continue

    try:
        parsed_timestamp = pd.to_datetime(raw_value, errors="raise", dayfirst=True)
        parsed_datetime = parsed_timestamp.to_pydatetime()
        parsed_time = parsed_datetime.time().replace(microsecond=0) if parsed_datetime.time() != time(0, 0) else None
        return parsed_datetime.date(), parsed_time
    except (ValueError, TypeError, OverflowError):
        return None, None


def parse_amount_value(value: Any) -> float | None:
    """Parse a numeric amount after removing currency symbols, spaces, and separators."""
    if is_empty_value(value):
        return None

    if isinstance(value, int | float):
        amount = float(value)
    else:
        raw_value = str(value).strip()
        if not raw_value:
            return None
        is_parentheses_negative = raw_value.startswith("(") and raw_value.endswith(")")
        cleaned = raw_value.replace("₹", "")
        cleaned = re.sub(r"(?i)\brs\.?", "", cleaned)
        cleaned = re.sub(r"(?i)\binr\b", "", cleaned)
        cleaned = cleaned.replace(",", "").replace(" ", "")
        cleaned = cleaned.replace("Cr", "").replace("CR", "").replace("Dr", "").replace("DR", "")
        cleaned = cleaned.strip("()")
        if cleaned in {"", "-", "+", "."}:
            return None
        try:
            amount = float(cleaned)
        except ValueError:
            return None
        if is_parentheses_negative:
            amount = -abs(amount)

    if math.isnan(amount) or math.isinf(amount):
        return None
    return amount


def description_suggests_credit(description: str) -> bool:
    """Return True when description text suggests the amount is incoming money."""
    lowered_description = str(description or "").lower()
    return any(keyword in lowered_description for keyword in CREDIT_DESCRIPTION_KEYWORDS)


def single_amount_column_all_non_negative(df: pd.DataFrame, column_map: dict[str, Any]) -> bool:
    """Return True when a single amount column contains no negative numeric values."""
    amount_column = column_map.get("amount")
    if not amount_column or column_map.get("debit") or column_map.get("credit") or not isinstance(df, pd.DataFrame):
        return False
    parsed_values = [parse_amount_value(value) for value in df.get(amount_column, [])]
    numeric_values = [value for value in parsed_values if value is not None and abs(value) > 0]
    return bool(numeric_values) and all(value >= 0 for value in numeric_values)


def determine_amount_and_type(row: pd.Series, column_map: dict[str, Any], description: str, infer_positive_direction: bool = False) -> tuple[float | None, str | None]:
    """Determine signed amount and transaction type from debit/credit or single amount columns."""
    debit_column = column_map.get("debit")
    credit_column = column_map.get("credit")
    amount_column = column_map.get("amount")

    debit_amount = parse_amount_value(row.get(debit_column)) if debit_column else None
    credit_amount = parse_amount_value(row.get(credit_column)) if credit_column else None

    if debit_amount is not None and abs(debit_amount) > 0:
        return -abs(debit_amount), "debit"
    if credit_amount is not None and abs(credit_amount) > 0:
        return abs(credit_amount), "credit"

    if amount_column:
        amount = parse_amount_value(row.get(amount_column))
        if amount is None or abs(amount) == 0:
            return None, None
        if amount < 0:
            return amount, "debit"
        if infer_positive_direction and not description_suggests_credit(description):
            return -abs(amount), "debit"
        return abs(amount), "credit"

    return None, None


def detect_refund(description: str) -> bool:
    """Return True when the description indicates refund, reversal, cashback, chargeback, or return."""
    lowered_description = description.lower()
    if any(keyword in lowered_description for keyword in REFUND_KEYWORDS):
        return True
    upper_description = description.upper()
    return bool(re.search(r"\bREV\b", upper_description) or re.search(r"\bR/", upper_description))


def detect_late_night(transaction_time: time | None) -> bool:
    """Return True when a transaction time is between 22:00 and 02:59."""
    if transaction_time is None:
        return False
    return transaction_time.hour >= 22 or transaction_time.hour <= 2


def normalize_duplicate_key(transaction: dict[str, Any]) -> tuple[str, str, float]:
    """Build a stable key used for duplicate transaction detection."""
    normalized_description = re.sub(r"\s+", " ", str(transaction.get("description") or "").strip().lower())
    amount = round(float(transaction.get("amount") or 0.0), 2)
    return str(transaction.get("transaction_date")), normalized_description, amount


def mark_duplicate_transactions(transactions: list[dict[str, Any]]) -> None:
    """Mark duplicate transactions in-place when date, description, and amount match."""
    seen_counts: dict[tuple[str, str, float], int] = {}
    for transaction in transactions:
        key = normalize_duplicate_key(transaction)
        seen_counts[key] = seen_counts.get(key, 0) + 1
    for transaction in transactions:
        key = normalize_duplicate_key(transaction)
        if seen_counts.get(key, 0) > 1:
            transaction["is_duplicate"] = True


def clean_transactions(df: pd.DataFrame, column_map: dict[str, Any]) -> dict[str, Any]:
    """Clean mapped statement rows into normalized transaction dictionaries without crashing on bad rows."""
    transactions: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not isinstance(df, pd.DataFrame):
        return {
            "transactions": [],
            "skipped_rows": [{"row_number": None, "reason": "Input must be a pandas DataFrame."}],
            "warnings": ["Input must be a pandas DataFrame."],
        }

    if df.empty:
        return {"transactions": [], "skipped_rows": [], "warnings": ["No transaction rows were found."]}

    date_column = column_map.get("date")
    description_column = column_map.get("description")

    infer_positive_direction = single_amount_column_all_non_negative(df, column_map)

    for index, row in df.iterrows():
        row_number = int(index) + 2 if isinstance(index, int) else len(transactions) + len(skipped_rows) + 1
        try:
            transaction_date, transaction_time = parse_transaction_datetime(row.get(date_column))
            if transaction_date is None:
                reason = f"Row {row_number}: Invalid date format"
                skipped_rows.append({"row_number": row_number, "reason": reason})
                warnings.append(reason)
                continue

            description = "" if is_empty_value(row.get(description_column)) else str(row.get(description_column)).strip()
            signed_amount, transaction_type = determine_amount_and_type(row, column_map, description, infer_positive_direction)
            if signed_amount is None or transaction_type is None:
                reason = f"Row {row_number}: Amount could not be parsed"
                skipped_rows.append({"row_number": row_number, "reason": reason})
                warnings.append(reason)
                continue

            merchant = clean_merchant(description)
            needs_review = merchant_needs_review(merchant)
            if transaction_date > date.today():
                warnings.append(f"Row {row_number}: Transaction date is in the future and needs review")
                needs_review = True
            if transaction_date.year < 2000:
                warnings.append(f"Row {row_number}: Transaction date is before year 2000 and needs review")
                needs_review = True
            is_high_value_debit = transaction_type == "debit" and abs(float(signed_amount)) > HIGH_VALUE_TRANSACTION_THRESHOLD
            if is_high_value_debit:
                warnings.append(f"Row {row_number}: Very large debit transaction amount needs review and was excluded from normal analytics")
                needs_review = True
            is_refund = detect_refund(description)
            is_cashback = "cashback" in description.lower() or "cash back" in description.lower()
            transaction = {
                "transaction_date": transaction_date.isoformat(),
                "transaction_time": transaction_time.isoformat() if transaction_time else None,
                "description": description,
                "merchant": merchant,
                "amount": round(float(signed_amount), 2),
                "transaction_type": transaction_type,
                "category": "Miscellaneous",
                "category_confidence": 0.1 if is_high_value_debit else 0.0,
                "category_source": "high_value_review" if is_high_value_debit else "low_confidence",
                "is_subscription": False,
                "is_duplicate": False,
                "is_small_spend": transaction_type == "debit" and abs(float(signed_amount)) < 500,
                "is_anomaly": is_high_value_debit,
                "is_refund": is_refund,
                "is_cashback": is_cashback,
                "is_late_night": detect_late_night(transaction_time),
                "needs_review": needs_review,
                "need_want_waste_type": "unknown",
            }
            transactions.append(transaction)
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            reason = f"Row {row_number}: Could not be cleaned"
            skipped_rows.append({"row_number": row_number, "reason": reason, "error_type": exc.__class__.__name__})
            warnings.append(reason)

    mark_duplicate_transactions(transactions)
    return {"transactions": transactions, "skipped_rows": skipped_rows, "warnings": warnings}
