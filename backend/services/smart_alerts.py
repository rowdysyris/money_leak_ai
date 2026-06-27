"""Smart bill reminders and refund/reversal tracking services."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from services.analytics_utils import (
    debit_amount,
    display_merchant_name,
    empty_result,
    get_category,
    get_field,
    is_credit,
    is_debit,
    is_high_value_or_anomaly,
    normalize_merchant_name,
    parse_date,
    service_result,
    to_float,
    valid_transactions,
)
from services.subscription_detector import detect_subscriptions

BILL_CATEGORIES = {"Bills & Utilities", "Rent & Housing", "EMI & Loans", "Subscriptions"}
BILL_KEYWORDS = {
    "airtel",
    "broadband",
    "credit card",
    "electricity",
    "emi",
    "gas bill",
    "internet",
    "jio",
    "loan",
    "mobile bill",
    "postpaid",
    "rent",
    "utility",
    "wifi",
}
REFUND_KEYWORDS = {
    "refund",
    "reversal",
    "revrsal",
    "chargeback",
    "cashback",
    "failed",
    "fail",
    "auto rev",
    "upi rev",
    "return",
    "reversed",
}
REFUND_CATEGORIES = {"Refund/Cashback"}
REFUND_LOOKAHEAD_DAYS = 14
REMINDER_LOOKAHEAD_DAYS = 45


def reference_date_from_transactions(transactions: list[Any]) -> date:
    """Return the latest transaction date or today's date when unavailable."""
    parsed_dates = [parsed for parsed in (parse_date(get_field(transaction, "transaction_date", None)) for transaction in valid_transactions(transactions)) if parsed]
    if parsed_dates:
        return max(parsed_dates)
    return date.today()


def text_blob(transaction: Any) -> str:
    """Return normalized merchant and description text for keyword checks."""
    merchant = str(get_field(transaction, "merchant", "") or "")
    description = str(get_field(transaction, "description", "") or "")
    return f"{merchant} {description}".lower()


def contains_any_keyword(text: str, keywords: set[str]) -> bool:
    """Return True when the text contains any configured keyword."""
    normalized = text.lower()
    return any(keyword in normalized for keyword in keywords)


def payment_interval_days(frequency: str | None) -> int:
    """Return approximate days for a recurring payment frequency."""
    normalized = str(frequency or "monthly").lower()
    if normalized == "weekly":
        return 7
    if normalized == "biweekly":
        return 14
    if normalized == "quarterly":
        return 90
    if normalized == "yearly":
        return 365
    return 30


def alert_status(days_until_due: int) -> str:
    """Return a bill reminder status label from due distance."""
    if days_until_due < 0:
        return "overdue"
    if days_until_due <= 7:
        return "due_soon"
    if days_until_due <= 30:
        return "upcoming"
    return "watch"


def alert_priority(days_until_due: int, amount: float) -> str:
    """Return high, medium, or low priority for a reminder."""
    if days_until_due < 0 or amount >= 10000:
        return "high"
    if days_until_due <= 7 or amount >= 3000:
        return "medium"
    return "low"


def subscription_reminders(transactions: list[Any], reference_date: date) -> list[dict[str, Any]]:
    """Build reminder rows from detected subscriptions."""
    subscription_result = detect_subscriptions(transactions)
    subscriptions = subscription_result.get("data", []) if isinstance(subscription_result.get("data", []), list) else []
    reminders: list[dict[str, Any]] = []
    for subscription in subscriptions:
        last_date = parse_date(subscription.get("last_charge_date"))
        predicted_date = parse_date(subscription.get("next_predicted_date"))
        if predicted_date is None and last_date is not None:
            predicted_date = last_date + timedelta(days=payment_interval_days(subscription.get("frequency")))
        if predicted_date is None:
            continue
        amount = to_float(subscription.get("monthly_cost") or subscription.get("average_amount"))
        days_until = (predicted_date - reference_date).days
        reminders.append(
            {
                "merchant": display_merchant_name(subscription.get("merchant")),
                "category": "Subscriptions",
                "amount": round(amount, 2),
                "last_paid_date": last_date.isoformat() if last_date else None,
                "predicted_due_date": predicted_date.isoformat(),
                "days_until_due": days_until,
                "status": alert_status(days_until),
                "priority": alert_priority(days_until, amount),
                "source": "subscription_pattern",
                "reason": f"Detected {subscription.get('frequency', 'recurring')} subscription pattern.",
            }
        )
    return reminders


def bill_candidate(transaction: Any) -> bool:
    """Return True when a debit transaction looks like a bill or fixed payment."""
    if not is_debit(transaction) or debit_amount(transaction) <= 0:
        return False
    if is_high_value_or_anomaly(transaction):
        return False
    category = get_category(transaction)
    if category in BILL_CATEGORIES:
        return True
    return contains_any_keyword(text_blob(transaction), BILL_KEYWORDS)


def grouped_bill_reminders(transactions: list[Any], reference_date: date) -> list[dict[str, Any]]:
    """Detect recurring bill-like merchants and predict their next due dates."""
    grouped: dict[str, list[Any]] = {}
    display_names: dict[str, str] = {}
    for transaction in valid_transactions(transactions):
        if not bill_candidate(transaction):
            continue
        merchant = display_merchant_name(get_field(transaction, "merchant", None))
        normalized = normalize_merchant_name(merchant)
        if not normalized:
            continue
        grouped.setdefault(normalized, []).append(transaction)
        display_names.setdefault(normalized, merchant)

    reminders: list[dict[str, Any]] = []
    for normalized, rows in grouped.items():
        dated_rows = sorted([row for row in rows if parse_date(get_field(row, "transaction_date", None))], key=lambda row: parse_date(get_field(row, "transaction_date", None)))
        if not dated_rows:
            continue
        last_date = parse_date(get_field(dated_rows[-1], "transaction_date", None))
        if last_date is None:
            continue
        amount_values = [debit_amount(row) for row in dated_rows if debit_amount(row) > 0]
        amount = round(sum(amount_values) / max(len(amount_values), 1), 2)
        if len(dated_rows) >= 2:
            dates = [parse_date(get_field(row, "transaction_date", None)) for row in dated_rows]
            intervals = [(dates[index] - dates[index - 1]).days for index in range(1, len(dates)) if dates[index] and dates[index - 1] and (dates[index] - dates[index - 1]).days > 0]
            interval = int(round(sum(intervals) / len(intervals))) if intervals else 30
        else:
            interval = 30
        interval = min(max(interval, 7), 365)
        predicted_date = last_date + timedelta(days=interval)
        days_until = (predicted_date - reference_date).days
        if days_until > REMINDER_LOOKAHEAD_DAYS:
            continue
        category = get_category(dated_rows[-1])
        reminders.append(
            {
                "merchant": display_names.get(normalized, normalized.title()),
                "category": category,
                "amount": amount,
                "last_paid_date": last_date.isoformat(),
                "predicted_due_date": predicted_date.isoformat(),
                "days_until_due": days_until,
                "status": alert_status(days_until),
                "priority": alert_priority(days_until, amount),
                "source": "bill_pattern",
                "reason": "Detected a recurring bill or fixed-payment merchant.",
            }
        )
    return reminders


def reminder_key(reminder: dict[str, Any]) -> tuple[str, str, str]:
    """Return a stable dedupe key for reminders."""
    return (normalize_merchant_name(reminder.get("merchant")), str(reminder.get("predicted_due_date") or ""), str(reminder.get("category") or ""))


def detect_bill_reminders(transactions: list[Any]) -> dict[str, Any]:
    """Detect upcoming bills, subscription renewals, and fixed payment reminders."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result({"summary": {}, "reminders": []})
    reference_date = reference_date_from_transactions(safe_transactions)
    raw_reminders = subscription_reminders(safe_transactions, reference_date) + grouped_bill_reminders(safe_transactions, reference_date)
    seen: set[tuple[str, str, str]] = set()
    reminders: list[dict[str, Any]] = []
    for reminder in sorted(raw_reminders, key=lambda item: (int(item.get("days_until_due", 999)), -to_float(item.get("amount")))):
        key = reminder_key(reminder)
        if key in seen:
            continue
        seen.add(key)
        reminders.append(reminder)
    summary = {
        "reference_date": reference_date.isoformat(),
        "total_reminders": len(reminders),
        "overdue_count": sum(1 for item in reminders if item.get("status") == "overdue"),
        "due_soon_count": sum(1 for item in reminders if item.get("status") == "due_soon"),
        "upcoming_amount": round(sum(to_float(item.get("amount")) for item in reminders if int(item.get("days_until_due", 999)) <= 30), 2),
    }
    warnings = [] if reminders else ["No upcoming bill reminders detected from the uploaded statement."]
    return service_result({"summary": summary, "reminders": reminders}, warnings)


def refund_like_credit(transaction: Any) -> bool:
    """Return True when a credit transaction is probably refund, reversal, or cashback."""
    if not is_credit(transaction):
        return False
    if bool(get_field(transaction, "is_refund", False) or get_field(transaction, "is_cashback", False)):
        return True
    if get_category(transaction) in REFUND_CATEGORIES:
        return True
    return contains_any_keyword(text_blob(transaction), REFUND_KEYWORDS)


def refund_like_debit(transaction: Any) -> bool:
    """Return True when a debit transaction deserves refund/reversal review."""
    if not is_debit(transaction) or debit_amount(transaction) <= 0:
        return False
    text = text_blob(transaction)
    if contains_any_keyword(text, {"failed", "fail", "chargeback", "refund pending", "reversal pending"}):
        return True
    if bool(get_field(transaction, "is_duplicate", False)):
        return True
    return False


def credit_matches_debit(debit_transaction: Any, credit_transaction: Any) -> bool:
    """Return True when a credit likely offsets a debit transaction."""
    debit_date = parse_date(get_field(debit_transaction, "transaction_date", None))
    credit_date = parse_date(get_field(credit_transaction, "transaction_date", None))
    if debit_date is None or credit_date is None:
        return False
    if credit_date < debit_date or (credit_date - debit_date).days > REFUND_LOOKAHEAD_DAYS:
        return False
    debit_value = debit_amount(debit_transaction)
    credit_value = abs(to_float(get_field(credit_transaction, "amount", 0.0)))
    if debit_value <= 0 or credit_value <= 0:
        return False
    amount_gap = abs(debit_value - credit_value)
    if amount_gap > max(2.0, debit_value * 0.05):
        return False
    debit_merchant = normalize_merchant_name(get_field(debit_transaction, "merchant", None))
    credit_merchant = normalize_merchant_name(get_field(credit_transaction, "merchant", None))
    if debit_merchant and credit_merchant and (debit_merchant in credit_merchant or credit_merchant in debit_merchant):
        return True
    return contains_any_keyword(text_blob(credit_transaction), REFUND_KEYWORDS)


def serialize_refund_transaction(transaction: Any, status: str, reason: str, matched_credit: Any | None = None) -> dict[str, Any]:
    """Serialize a refund/reversal tracking row."""
    debit_date = parse_date(get_field(transaction, "transaction_date", None))
    credit_date = parse_date(get_field(matched_credit, "transaction_date", None)) if matched_credit is not None else None
    return {
        "transaction_id": str(get_field(transaction, "id", "") or ""),
        "merchant": display_merchant_name(get_field(transaction, "merchant", None)),
        "description": str(get_field(transaction, "description", "") or ""),
        "amount": round(debit_amount(transaction), 2),
        "transaction_date": debit_date.isoformat() if debit_date else None,
        "status": status,
        "reason": reason,
        "matched_refund_date": credit_date.isoformat() if credit_date else None,
        "matched_refund_amount": round(abs(to_float(get_field(matched_credit, "amount", 0.0))), 2) if matched_credit is not None else None,
    }


def detect_refund_reversal_tracking(transactions: list[Any]) -> dict[str, Any]:
    """Detect refunds received, reversals, failed payments, and missing refund candidates."""
    safe_transactions = valid_transactions(transactions)
    if not safe_transactions:
        return empty_result({"summary": {}, "refunds_received": [], "review_items": []})
    credits = [transaction for transaction in safe_transactions if refund_like_credit(transaction)]
    debit_reviews = [transaction for transaction in safe_transactions if refund_like_debit(transaction)]
    refunds_received = []
    for credit in credits:
        credit_date = parse_date(get_field(credit, "transaction_date", None))
        refunds_received.append(
            {
                "transaction_id": str(get_field(credit, "id", "") or ""),
                "merchant": display_merchant_name(get_field(credit, "merchant", None)),
                "description": str(get_field(credit, "description", "") or ""),
                "amount": round(abs(to_float(get_field(credit, "amount", 0.0))), 2),
                "transaction_date": credit_date.isoformat() if credit_date else None,
                "reason": "Credit looks like refund, reversal, cashback, or chargeback.",
            }
        )

    review_items = []
    for debit_transaction in debit_reviews:
        matched_credit = next((credit for credit in credits if credit_matches_debit(debit_transaction, credit)), None)
        if matched_credit is not None:
            review_items.append(serialize_refund_transaction(debit_transaction, "resolved", "Matching refund/reversal credit found.", matched_credit))
        else:
            review_items.append(serialize_refund_transaction(debit_transaction, "needs_review", "Debit looks failed/duplicate/refund-related but no matching reversal was found nearby."))

    review_items.sort(key=lambda item: (item.get("status") != "needs_review", item.get("transaction_date") or ""))
    summary = {
        "refunds_received_count": len(refunds_received),
        "refunds_received_amount": round(sum(to_float(item.get("amount")) for item in refunds_received), 2),
        "review_count": len(review_items),
        "missing_refund_count": sum(1 for item in review_items if item.get("status") == "needs_review"),
        "missing_refund_amount": round(sum(to_float(item.get("amount")) for item in review_items if item.get("status") == "needs_review"), 2),
    }
    warnings = [] if refunds_received or review_items else ["No refund, reversal, failed-payment, or chargeback patterns detected."]
    return service_result({"summary": summary, "refunds_received": refunds_received, "review_items": review_items}, warnings)


def detect_smart_alerts(transactions: list[Any]) -> dict[str, Any]:
    """Return combined bill reminder and refund/reversal alerts."""
    reminder_result = detect_bill_reminders(transactions)
    refund_result = detect_refund_reversal_tracking(transactions)
    reminders_data = reminder_result.get("data", {}) if isinstance(reminder_result.get("data", {}), dict) else {}
    refund_data = refund_result.get("data", {}) if isinstance(refund_result.get("data", {}), dict) else {}
    summary = {
        "bill_reminders": reminders_data.get("summary", {}),
        "refund_tracking": refund_data.get("summary", {}),
        "action_required_count": to_float((reminders_data.get("summary", {}) or {}).get("overdue_count"))
        + to_float((reminders_data.get("summary", {}) or {}).get("due_soon_count"))
        + to_float((refund_data.get("summary", {}) or {}).get("missing_refund_count")),
    }
    warnings = list(dict.fromkeys(reminder_result.get("warnings", []) + refund_result.get("warnings", [])))
    return service_result({"summary": summary, "bill_reminders": reminders_data, "refund_tracking": refund_data}, warnings)
