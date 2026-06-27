"""Regression tests for improved subscription detection quality."""

from datetime import date

from services.subscription_detector import detect_subscriptions


def tx(merchant, amount, tx_date, category="Subscriptions", transaction_type="debit", **flags):
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


def test_irregular_subscription_has_no_next_predicted_date():
    """Irregular subscriptions should not expose a confident next predicted charge date."""
    result = detect_subscriptions([
        tx("Canva Pro", 599, date(2026, 6, 1)),
        tx("Canva Pro", 599, date(2026, 6, 19)),
        tx("Canva Pro", 599, date(2026, 9, 7)),
    ])
    subscription = result["data"][0]
    assert subscription["frequency"] == "irregular"
    assert subscription["next_predicted_date"] is None
    assert subscription["confidence_score"] < 0.7


def test_subscription_uses_median_consistent_amount():
    """Subscription cost should use the stable recurring charge cluster, not one-off outlier amounts."""
    result = detect_subscriptions([
        tx("Google One Storage", 130, date(2026, 6, 12)),
        tx("Google One Storage", 130, date(2026, 7, 12)),
        tx("Google One Storage", 130, date(2026, 8, 12)),
        tx("Google One Storage", 999, date(2026, 9, 4)),
    ])
    subscription = result["data"][0]
    assert subscription["frequency"] == "monthly"
    assert subscription["monthly_cost"] == 130
    assert subscription["yearly_cost"] == 1560


def test_subscription_excludes_large_anomaly():
    """Very large anomaly transactions should never inflate subscription projections."""
    result = detect_subscriptions([
        tx("Netflix", 649, date(2026, 6, 7)),
        tx("Netflix", 649, date(2026, 7, 7)),
        tx("Netflix", 12500000, date(2026, 8, 7)),
    ])
    subscription = result["data"][0]
    assert subscription["monthly_cost"] == 649
    assert subscription["yearly_cost"] == 7788


def test_subscription_priority_thresholds():
    """Cancellation priority should use realistic yearly-cost thresholds."""
    result = detect_subscriptions([
        tx("Netflix", 649, date(2026, 6, 7)),
        tx("Netflix", 649, date(2026, 7, 7)),
        tx("Spotify Premium", 119, date(2026, 6, 10)),
        tx("Spotify Premium", 119, date(2026, 7, 10)),
        tx("Small App", 49, date(2026, 6, 1)),
        tx("Small App", 49, date(2026, 7, 1)),
    ])
    by_merchant = {item["merchant"]: item for item in result["data"]}
    assert by_merchant["Netflix"]["cancellation_priority"] == "high"
    assert by_merchant["Spotify Premium"]["cancellation_priority"] == "low"


def test_duplicate_or_refund_rows_excluded_from_subscription_detection():
    """Refund and duplicate rows should not create subscriptions."""
    result = detect_subscriptions([
        tx("Icloud Storage", 199, date(2026, 6, 8), is_duplicate=True),
        tx("Icloud Storage", 199, date(2026, 7, 8), is_duplicate=True),
        tx("Icloud Storage", 199, date(2026, 8, 8), is_refund=True),
    ])
    assert result["data"] == []


def test_non_subscription_recurring_merchant_not_flagged() -> None:
    """Repeated travel or rent-like merchants should not appear on the subscriptions page."""
    transactions = [
        tx("Uber Trip", 799, date(2026, 7, 1), category="Travel & Transport"),
        tx("Uber Trip", 799, date(2026, 7, 8), category="Travel & Transport"),
        tx("Uber Trip", 799, date(2026, 7, 15), category="Travel & Transport"),
    ]
    assert detect_subscriptions(transactions)["data"] == []
