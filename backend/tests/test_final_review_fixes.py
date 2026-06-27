"""Regression tests for final frontend review fixes."""

from services.categorizer import categorize_transaction
from services.subscription_detector import detect_subscriptions

USER_ID = "00000000-0000-0000-0000-000000000000"


def tx(merchant: str, description: str, amount: float, tx_type: str = "debit", tx_date: str = "2026-07-01", category: str = "Miscellaneous") -> dict:
    """Build a minimal transaction dictionary for analytics tests."""
    return {
        "merchant": merchant,
        "description": description,
        "amount": amount,
        "transaction_type": tx_type,
        "transaction_date": tx_date,
        "category": category,
        "is_refund": False,
        "is_cashback": False,
        "is_duplicate": False,
        "is_anomaly": False,
    }


def test_salary_credit_is_income_without_review():
    """Salary credits should be categorized as income, not Miscellaneous."""
    result = categorize_transaction(tx("Salary Credit Acme Technologies", "SALARY CREDIT ACME TECHNOLOGIES", 45000, "credit"), USER_ID)
    assert result["category"] == "Income"
    assert result["confidence"] >= 0.9
    assert result["needs_review"] is False


def test_upi_imps_neft_patterns_are_transfers():
    """Indian transfer rails should not fall back to Miscellaneous."""
    for description in ["UPI/P2M/1234567890", "IMPS/P2A/9988776655", "NEFT/JOHN DOE"]:
        result = categorize_transaction(tx("Unknown", description, -500), USER_ID)
        assert result["category"] == "Transfers"
        assert result["confidence"] >= 0.7


def test_rent_landlord_is_housing():
    """Landlord rent transfers should be categorized as Rent & Housing."""
    result = categorize_transaction(tx("Rent Landlord", "RENT TRANSFER LANDLORD", -12000), USER_ID)
    assert result["category"] == "Rent & Housing"


def test_negative_balance_marker_is_anomaly():
    """Negative-balance marker rows should be reviewed outside normal analytics."""
    result = categorize_transaction(tx("Negative Balance Test", "NEGATIVE BALANCE TEST", -200000), USER_ID)
    assert result["is_anomaly"] is True
    assert result["needs_review"] is True
    assert result["source"] == "high_value_review"


def test_monthly_subscription_chain_ignores_same_merchant_noise():
    """Subscription detection should pick stable monthly amount clusters instead of noisy same-merchant rows."""
    rows = [
        tx("Google One Storage", "GOOGLE ONE STORAGE", -130, tx_date="2026-06-12", category="Subscriptions"),
        tx("Google One Storage", "GOOGLE ONE STORAGE", -130, tx_date="2026-07-12", category="Subscriptions"),
        tx("Google One Storage", "GOOGLE ONE STORAGE", -130, tx_date="2026-08-12", category="Subscriptions"),
        tx("Google One Storage", "GOOGLE ONE STORAGE", -799, tx_date="2026-07-02", category="Subscriptions"),
        tx("Google One Storage", "GOOGLE ONE STORAGE", -799, tx_date="2026-07-11", category="Subscriptions"),
        tx("Google One Storage", "GOOGLE ONE STORAGE", -799, tx_date="2026-07-23", category="Subscriptions"),
    ]
    result = detect_subscriptions(rows)["data"]
    assert result[0]["merchant"] == "Google One Storage"
    assert result[0]["frequency"] == "monthly"
    assert result[0]["monthly_cost"] == 130.0
