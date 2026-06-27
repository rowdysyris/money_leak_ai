"""Tests for MoneyLeak AI analytics and insight services."""

from __future__ import annotations

from datetime import date, time, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from routers.insights import (
    burn_rate,
    daily_safe_limit,
    duplicates,
    late_night_spending,
    money_leak_score,
    month_end_survival,
    saving_priority_list,
    small_spend_leaks,
    spending_personality,
    subscriptions,
    weekend_vs_weekday,
    yearly_impact,
)
from services.burn_rate_analyzer import analyze_burn_rate
from services.dashboard_service import get_category_breakdown, get_summary
from services.duplicate_detector import detect_duplicates
from services.leakage_detector import detect_small_spend_leakage
from services.money_leak_score import calculate_score
from services.report_summary import classify_personality, generate_saving_priority
from services.subscription_detector import detect_subscriptions


def make_tx(
    merchant: str,
    amount: float,
    transaction_type: str,
    category: str,
    tx_date: date,
    need_want_waste_type: str,
    description: str | None = None,
    transaction_time: time | None = None,
    is_refund: bool = False,
    is_duplicate: bool = False,
) -> SimpleNamespace:
    """Create a minimal transaction-like object for analytics tests."""
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        statement_id=uuid4(),
        merchant=merchant,
        amount=amount,
        transaction_type=transaction_type,
        category=category,
        transaction_date=tx_date,
        transaction_time=transaction_time,
        description=description or merchant,
        need_want_waste_type=need_want_waste_type,
        is_refund=is_refund,
        is_cashback=False,
        is_duplicate=is_duplicate,
        needs_review=category == "Miscellaneous",
    )


@pytest.fixture
def empty_transactions() -> list[SimpleNamespace]:
    """Return an empty transaction fixture."""
    return []


@pytest.fixture
def minimal_transactions() -> list[SimpleNamespace]:
    """Return five transactions covering income, food, bills, shopping, and savings."""
    base = date(2024, 1, 1)
    return [
        make_tx("Salary", 50000, "credit", "Transfers", base, "unknown", "Salary credited"),
        make_tx("Swiggy", -350, "debit", "Food & Dining", base + timedelta(days=1), "want", transaction_time=time(23, 30)),
        make_tx("Airtel", -999, "debit", "Bills & Utilities", base + timedelta(days=2), "need"),
        make_tx("Amazon", -2200, "debit", "Shopping", base + timedelta(days=5), "want"),
        make_tx("Groww", -5000, "debit", "Investments & Savings", base + timedelta(days=7), "savings"),
    ]


@pytest.fixture
def full_transactions() -> list[SimpleNamespace]:
    """Return a larger fixture with subscriptions, duplicates, food spend, and mixed dates."""
    base = date(2024, 1, 1)
    rows: list[SimpleNamespace] = [make_tx("Salary", 60000, "credit", "Transfers", base, "unknown", "Salary credited")]
    for index in range(3):
        rows.append(make_tx("Netflix", -499, "debit", "Subscriptions", base + timedelta(days=index * 30), "want"))
    for index in range(4):
        rows.append(make_tx("MilkBasket", -80, "debit", "Groceries", base + timedelta(days=index * 7), "need"))
    rows.append(make_tx("Dominos", -750, "debit", "Food & Dining", base + timedelta(days=6), "want"))
    rows.append(make_tx("Dominos", -750, "debit", "Food & Dining", base + timedelta(days=6), "want"))
    rows.append(make_tx("ATM", -2000, "debit", "Cash Withdrawal", base + timedelta(days=8), "unknown"))
    rows.append(make_tx("Processing Fee", -250, "debit", "Bank Charges & Fees", base + timedelta(days=10), "waste"))
    categories = [
        ("Swiggy", "Food & Dining", "want", 220),
        ("Zomato", "Food & Dining", "want", 180),
        ("Bigbasket", "Groceries", "need", 900),
        ("Uber", "Travel & Transport", "want", 320),
        ("Airtel", "Bills & Utilities", "need", 999),
        ("Amazon", "Shopping", "want", 1500),
        ("Apollo Pharmacy", "Health & Medical", "need", 600),
        ("Groww", "Investments & Savings", "savings", 3000),
    ]
    day = 11
    while len(rows) < 50:
        merchant, category, label, amount = categories[len(rows) % len(categories)]
        rows.append(
            make_tx(
                merchant,
                -float(amount),
                "debit",
                category,
                base + timedelta(days=day),
                label,
                transaction_time=time(22, 15) if len(rows) % 9 == 0 else None,
            )
        )
        day += 1
    return rows


def test_summary_empty_transactions(empty_transactions: list[SimpleNamespace]) -> None:
    """Verify summary returns safe defaults for empty transactions."""
    result = get_summary(empty_transactions)
    assert result["data"]["total_spent"] == 0.0
    assert "No transactions found" in result["warnings"]


def test_summary_with_transactions(minimal_transactions: list[SimpleNamespace]) -> None:
    """Verify summary totals are calculated from transactions."""
    result = get_summary(minimal_transactions)
    assert result["data"]["total_received"] == 50000
    assert result["data"]["total_spent"] == 8549
    assert result["data"]["total_transactions"] == 5


def test_category_breakdown_empty(empty_transactions: list[SimpleNamespace]) -> None:
    """Verify category breakdown handles empty input."""
    result = get_category_breakdown(empty_transactions)
    assert result["data"] == []
    assert result["warnings"]


def test_category_breakdown_correct_percentages(minimal_transactions: list[SimpleNamespace]) -> None:
    """Verify category percentages add up safely for debit spending."""
    result = get_category_breakdown(minimal_transactions)
    total_percentage = round(sum(item["percentage_of_total_spend"] for item in result["data"]), 2)
    assert 99.9 <= total_percentage <= 100.1


def test_subscription_detection_monthly_pattern(full_transactions: list[SimpleNamespace]) -> None:
    """Verify monthly subscription pattern is detected."""
    result = detect_subscriptions(full_transactions)
    netflix = [item for item in result["data"] if item["merchant"] == "Netflix"]
    assert netflix
    assert netflix[0]["frequency"] == "monthly"


def test_subscription_detection_weekly_pattern() -> None:
    """Verify weekly subscription pattern is detected."""
    base = date(2024, 1, 1)
    transactions = [make_tx("Weekly Fit", -199, "debit", "Subscriptions", base + timedelta(days=index * 7), "want") for index in range(4)]
    result = detect_subscriptions(transactions)
    assert result["data"][0]["frequency"] == "weekly"


def test_no_subscriptions(minimal_transactions: list[SimpleNamespace]) -> None:
    """Verify no subscriptions are returned when recurring pattern is absent."""
    result = detect_subscriptions(minimal_transactions)
    assert result["data"] == []


def test_duplicate_detection_same_day(full_transactions: list[SimpleNamespace]) -> None:
    """Verify same-day same-merchant same-amount duplicates are detected."""
    result = detect_duplicates(full_transactions)
    assert any(item["merchant"] == "Dominos" and item["confidence_score"] == 0.95 for item in result["data"])


def test_no_duplicates(minimal_transactions: list[SimpleNamespace]) -> None:
    """Verify no duplicates are returned for unique payments."""
    result = detect_duplicates(minimal_transactions)
    assert result["data"] == []


def test_money_leak_score_healthy() -> None:
    """Verify healthy all-need spending with savings remains below 30."""
    base = date(2024, 1, 1)
    transactions = [
        make_tx("Salary", 50000, "credit", "Transfers", base, "unknown"),
        make_tx("Rent", -10000, "debit", "Rent & Housing", base + timedelta(days=1), "need"),
        make_tx("Airtel", -1000, "debit", "Bills & Utilities", base + timedelta(days=2), "need"),
        make_tx("Groww", -6000, "debit", "Investments & Savings", base + timedelta(days=3), "savings"),
    ]
    result = calculate_score(transactions, [], [])
    assert result["data"]["score"] < 30


def test_money_leak_score_critical() -> None:
    """Verify high wants, duplicates, and no savings produce high risk score."""
    base = date(2024, 1, 1)
    transactions = [make_tx("Salary", 30000, "credit", "Transfers", base, "unknown")]
    for index in range(12):
        transactions.append(make_tx("Cafe", -300, "debit", "Food & Dining", base + timedelta(days=index), "want"))
    duplicates_data = [{"amount": 300}, {"amount": 300}, {"amount": 300}, {"amount": 300}, {"amount": 300}]
    result = calculate_score(transactions, [], duplicates_data)
    assert result["data"]["score"] > 70


def test_small_spend_leakage_buckets(full_transactions: list[SimpleNamespace]) -> None:
    """Verify small-spend leakage buckets contain expected counts."""
    result = detect_small_spend_leakage(full_transactions)
    assert result["data"]["total_leakage"] > 0
    assert result["data"]["bucket_under_100"]["count"] >= 1


def test_burn_rate_no_income_graceful() -> None:
    """Verify burn-rate analyzer warns gracefully when income is missing."""
    base = date(2024, 1, 1)
    transactions = [make_tx("Swiggy", -200, "debit", "Food & Dining", base + timedelta(days=index), "want") for index in range(10)]
    result = analyze_burn_rate(transactions)
    assert any("Could not detect income" in warning for warning in result["warnings"])


def test_burn_rate_with_income(minimal_transactions: list[SimpleNamespace]) -> None:
    """Verify burn-rate analyzer calculates projection with income."""
    result = analyze_burn_rate(minimal_transactions, current_balance=10000)
    assert result["data"]["estimated_income"] > 0
    assert result["data"]["monthly_projection"] > 0


def test_saving_priority_ranked(full_transactions: list[SimpleNamespace]) -> None:
    """Verify saving priority list is ranked by monthly saving."""
    subscriptions_data = detect_subscriptions(full_transactions)["data"]
    duplicates_data = detect_duplicates(full_transactions)["data"]
    result = generate_saving_priority(full_transactions, subscriptions_data, duplicates_data)
    assert result["data"]
    assert result["data"][0]["rank"] == 1


def test_spending_personality_food_spender() -> None:
    """Verify food-heavy transactions classify as Food Spender."""
    base = date(2024, 1, 1)
    transactions = [make_tx("Salary", 20000, "credit", "Transfers", base, "unknown")]
    for index in range(8):
        transactions.append(make_tx("Swiggy", -500, "debit", "Food & Dining", base + timedelta(days=index), "want"))
    transactions.append(make_tx("Amazon", -500, "debit", "Shopping", base + timedelta(days=9), "want"))
    breakdown = get_category_breakdown(transactions)
    result = classify_personality(transactions, breakdown)
    assert result["data"]["personality_type"] == "Food Spender"


def test_division_by_zero_safety() -> None:
    """Verify single-day data does not cause division-by-zero failures."""
    transaction = make_tx("Swiggy", -100, "debit", "Food & Dining", date(2024, 1, 1), "want")
    assert analyze_burn_rate([transaction])["data"]["daily_burn_rate"] >= 0
    assert get_category_breakdown([transaction])["data"][0]["percentage_of_total_spend"] == 100.0


class EmptyQuery:
    """Fake query object that returns no statements."""

    def filter(self, *args: object, **kwargs: object) -> "EmptyQuery":
        """Return self for chainable fake filtering."""
        return self

    def order_by(self, *args: object, **kwargs: object) -> "EmptyQuery":
        """Return self for chainable fake ordering."""
        return self

    def first(self) -> None:
        """Return no statement."""
        return None


class EmptyDb:
    """Fake DB session that returns no statements."""

    def query(self, *args: object, **kwargs: object) -> EmptyQuery:
        """Return an empty fake query."""
        return EmptyQuery()


def test_all_insights_with_no_statement() -> None:
    """Verify all insight endpoints return graceful no-statement responses."""
    user = SimpleNamespace(id=uuid4())
    db = EmptyDb()
    endpoint_functions = [
        small_spend_leaks,
        subscriptions,
        duplicates,
        money_leak_score,
        saving_priority_list,
        month_end_survival,
        daily_safe_limit,
        spending_personality,
        burn_rate,
        yearly_impact,
        weekend_vs_weekday,
        late_night_spending,
    ]
    for endpoint in endpoint_functions:
        response = endpoint(current_user=user, db=db)
        assert response["success"] is True
        assert response["data"] is None
        assert response["warnings"]
