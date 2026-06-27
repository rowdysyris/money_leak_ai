"""Regression tests for corrected money leak analytics."""

from datetime import date

from services.duplicate_detector import detect_duplicates
from services.leakage_detector import detect_small_spend_leakage
from services.report_summary import generate_saving_priority
from services.subscription_detector import detect_subscriptions


def tx(merchant, amount, tx_date, category="Food & Dining", transaction_type="debit", **flags):
    """Build a dictionary transaction fixture."""
    return {
        "id": f"{merchant}-{amount}-{tx_date}-{len(flags)}",
        "merchant": merchant,
        "description": merchant,
        "amount": -abs(amount) if transaction_type == "debit" else abs(amount),
        "transaction_type": transaction_type,
        "transaction_date": tx_date,
        "category": category,
        "need_want_waste_type": flags.pop("need_want_waste_type", "want"),
        **flags,
    }


def test_small_spend_buckets_nonzero():
    """Small-spend buckets should expose stable frontend keys with nonzero values."""
    result = detect_small_spend_leakage([
        tx("Tea", 50, date(2026, 7, 1)),
        tx("Snack", 150, date(2026, 7, 2)),
        tx("Cafe", 350, date(2026, 7, 3)),
    ])
    data = result["data"]
    assert data["under_100"]["count"] == 1
    assert data["between_100_200"]["count"] == 1
    assert data["between_200_500"]["count"] == 1
    assert data["total_leakage"] == 550


def test_subscriptions_not_flagged_as_duplicates():
    """Known subscription merchants should not be reported as duplicate payments."""
    transactions = [
        tx("ChatGPT OpenAI", 999, date(2026, 7, 1), category="Subscriptions"),
        tx("ChatGPT OpenAI", 999, date(2026, 7, 2), category="Subscriptions"),
    ]
    assert detect_duplicates(transactions)["data"] == []


def test_large_anomaly_excluded_from_savings_projection():
    """Very large one-off anomalies should not inflate savings recommendations."""
    transactions = [
        tx("Huge", 12500000, date(2026, 7, 1), category="Subscriptions"),
        tx("Swiggy", 300, date(2026, 7, 2)),
        tx("Swiggy", 250, date(2026, 7, 3)),
    ]
    small = detect_small_spend_leakage(transactions)["data"]
    assert small["total_leakage"] == 550
    recommendations = generate_saving_priority(transactions, [], [])["data"]
    assert sum(item["possible_monthly_saving"] for item in recommendations) <= 550


def test_subscription_projection_uses_recurring_only():
    """Subscription detection should ignore inconsistent high-value one-time rows."""
    transactions = [
        tx("Netflix", 649, date(2026, 6, 7), category="Subscriptions"),
        tx("Netflix", 649, date(2026, 7, 7), category="Subscriptions"),
        tx("Netflix", 12500000, date(2026, 8, 7), category="Subscriptions"),
    ]
    subscriptions = detect_subscriptions(transactions)["data"]
    assert len(subscriptions) == 1
    assert subscriptions[0]["monthly_cost"] == 649


def test_estimated_savings_capped():
    """Saving recommendations should be capped by controllable projected spend."""
    transactions = [
        tx("Bank Fee", 100, date(2026, 7, 1), category="Bank Charges & Fees", need_want_waste_type="waste"),
        tx("Huge", 12500000, date(2026, 7, 2), category="Shopping"),
    ]
    result = generate_saving_priority(transactions, [{"merchant": "Canva", "monthly_cost": 599, "yearly_cost": 7188}], [])
    total = sum(item["possible_monthly_saving"] for item in result["data"])
    assert total <= 100
