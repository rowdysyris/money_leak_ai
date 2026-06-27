"""Regression tests for dashboard anomaly-aware analytics."""

from datetime import date

import pandas as pd

from services.categorizer import categorize_transaction
from services.dashboard_service import get_category_breakdown, get_summary, get_top_merchants
from services.money_leak_score import calculate_score
from services.report_summary import generate_saving_priority
from services.transaction_cleaner import clean_transactions


def tx(merchant: str, amount: float, tx_date: date, category: str = "Food & Dining", label: str = "want", **flags: object) -> dict[str, object]:
    """Build a dictionary transaction fixture with signed debit amount."""
    return {
        "id": f"{merchant}-{amount}-{tx_date}",
        "merchant": merchant,
        "description": merchant,
        "amount": -abs(amount),
        "transaction_type": "debit",
        "transaction_date": tx_date,
        "category": category,
        "need_want_waste_type": label,
        **flags,
    }


def test_high_value_transaction_marked_anomaly() -> None:
    """Cleaner should flag debit rows above ₹10,00,000 as review-only anomalies."""
    dataframe = pd.DataFrame(
        [
            {
                "Date": "14/07/2026",
                "Narration": "VERY LARGE AMOUNT ABOVE ONE CRORE",
                "Debit": "1,25,00,000.00",
                "Credit": "",
            }
        ]
    )
    result = clean_transactions(dataframe, {"date": "Date", "description": "Narration", "debit": "Debit", "credit": "Credit"})
    cleaned = result["transactions"][0]
    assert cleaned["is_anomaly"] is True
    assert cleaned["needs_review"] is True
    assert cleaned["category"] == "Miscellaneous"
    assert cleaned["category_source"] == "high_value_review"


def test_high_value_transaction_not_categorized_subscription() -> None:
    """Categorizer should bypass merchant and ML rules for high-value debit anomalies."""
    result = categorize_transaction(
        {
            "merchant": "Very Large Amount Above One Crore",
            "description": "VERY LARGE AMOUNT ABOVE ONE CRORE",
            "amount": -12500000.0,
            "transaction_type": "debit",
            "transaction_date": "2026-07-14",
        },
        user_id="00000000-0000-0000-0000-000000000000",
    )
    assert result["category"] == "Miscellaneous"
    assert result["source"] == "high_value_review"
    assert result["is_anomaly"] is True


def test_dashboard_excludes_anomaly_from_top_category() -> None:
    """Dashboard top category should use actionable spending, not review-only anomalies."""
    transactions = [
        tx("Huge", 12500000, date(2026, 7, 1), category="Subscriptions", is_anomaly=True, category_source="high_value_review"),
        tx("Swiggy", 500, date(2026, 7, 2), category="Food & Dining"),
        tx("Amazon", 3000, date(2026, 7, 3), category="Shopping"),
    ]
    summary = get_summary(transactions)["data"]
    assert summary["top_spending_category"] == "Shopping"
    assert summary["total_spent_raw"] == 12503500
    assert summary["total_spent_actionable"] == 3500
    assert summary["high_value_review_transactions"]


def test_category_breakdown_excludes_high_value_anomaly() -> None:
    """Category breakdown should not let high-value anomalies dominate percentages."""
    transactions = [
        tx("Huge", 12500000, date(2026, 7, 1), category="Subscriptions", is_anomaly=True, category_source="high_value_review"),
        tx("Shopping", 1000, date(2026, 7, 2), category="Shopping"),
        tx("Food", 1000, date(2026, 7, 3), category="Food & Dining"),
    ]
    categories = get_category_breakdown(transactions)["data"]
    category_names = {item["category"] for item in categories}
    assert "Subscriptions" not in category_names
    assert sum(item["total_amount"] for item in categories) == 2000


def test_top_merchants_excludes_high_value_anomaly() -> None:
    """Top merchant table should not show review-only anomalies as normal merchants."""
    transactions = [
        tx("Very Large Amount Above One Crore", 12500000, date(2026, 7, 1), category="Subscriptions", is_anomaly=True, category_source="high_value_review"),
        tx("Flipkart", 2000, date(2026, 7, 2), category="Shopping"),
    ]
    merchants = get_top_merchants(transactions)["data"]
    assert len(merchants) == 1
    assert merchants[0]["merchant"] == "Flipkart"


def test_monthly_savings_capped_by_actionable_spend() -> None:
    """Savings recommendations should never exceed controllable/actionable spend."""
    transactions = [
        tx("Huge", 12500000, date(2026, 7, 1), category="Subscriptions", is_anomaly=True, category_source="high_value_review"),
        tx("Bank Fee", 100, date(2026, 7, 2), category="Bank Charges & Fees", label="waste"),
    ]
    result = generate_saving_priority(transactions, [{"merchant": "Canva", "monthly_cost": 599, "yearly_cost": 7188}], [])
    assert sum(item["possible_monthly_saving"] for item in result["data"]) <= 100


def test_money_leak_score_ignores_high_value_anomaly() -> None:
    """Money leak score inputs should use actionable spending after excluding anomalies."""
    transactions = [
        tx("Huge", 12500000, date(2026, 7, 1), category="Subscriptions", is_anomaly=True, category_source="high_value_review"),
        tx("Food", 500, date(2026, 7, 2), category="Food & Dining"),
    ]
    score = calculate_score(transactions, [], [])["data"]
    assert score["inputs"]["total_spend"] == 500
