"""SQLAlchemy model tests for MoneyLeak AI."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from database import engine
from models import Category, MerchantDiscoveryCache, Statement, Transaction, User
from models.category import DEFAULT_CATEGORIES

EXPECTED_TABLES = {
    "users",
    "statements",
    "transactions",
    "categories",
    "subscriptions",
    "duplicate_payments",
    "merchant_discovery_cache",
    "user_category_rules",
    "learned_merchant_rules",
    "user_budgets",
    "agent_runs",
    "rag_memories",
    "savings_recommendations",
    "transaction_category_feedback",
}


def unique_email(prefix: str = "model-user") -> str:
    """Return a unique email address for model tests."""
    return f"{prefix}-{uuid4().hex}@example.com"


def enum_value(value: object) -> object:
    """Return the raw enum value when an ORM field is represented as an enum."""
    return getattr(value, "value", value)


def test_all_tables_created() -> None:
    """Verify all requested MoneyLeak AI tables exist."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    assert EXPECTED_TABLES.issubset(table_names)


def test_categories_seeded() -> None:
    """Verify the default 17 MoneyLeak AI categories are seeded."""
    expected_mapping = {item["name"]: item["need_want_waste_type"] for item in DEFAULT_CATEGORIES}
    with Session(engine) as db:
        categories = db.query(Category).all()
        actual_mapping = {category.name: enum_value(category.need_want_waste_type) for category in categories}
    assert len(categories) == 17
    assert actual_mapping == expected_mapping


def test_user_model() -> None:
    """Create and read a user model record."""
    email = unique_email()
    with Session(engine) as db:
        user = User(
            email=email,
            hashed_password="hashed-password",
            full_name="Model User",
            profile_type="Student",
            city="Bhopal",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        read_user = db.query(User).filter(User.email == email).one()
    assert read_user.email == email
    assert read_user.full_name == "Model User"
    assert enum_value(read_user.profile_type) == "Student"
    assert read_user.is_active is True


def test_transaction_model() -> None:
    """Create a transaction with minimum required fields and verify defaults."""
    with Session(engine) as db:
        user = User(
            email=unique_email("transaction-user"),
            hashed_password="hashed-password",
            full_name="Transaction User",
            profile_type="Fresher",
        )
        db.add(user)
        db.flush()
        statement = Statement(
            user_id=user.id,
            original_filename="statement.csv",
            file_format="csv",
            total_rows=1,
            processed_rows=1,
            skipped_rows=0,
            processing_status="completed",
        )
        db.add(statement)
        db.flush()
        transaction = Transaction(
            user_id=user.id,
            statement_id=statement.id,
            transaction_date=date.today(),
            amount=Decimal("125.50"),
            transaction_type="debit",
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        read_transaction = db.query(Transaction).filter(Transaction.id == transaction.id).one()
    assert read_transaction.amount == Decimal("125.50")
    assert read_transaction.category == "Miscellaneous"
    assert read_transaction.category_confidence == 0.0
    assert read_transaction.is_subscription is False
    assert read_transaction.is_duplicate is False
    assert read_transaction.needs_review is False
    assert enum_value(read_transaction.need_want_waste_type) == "unknown"


def test_merchant_cache_model() -> None:
    """Create and read a merchant discovery cache record."""
    with Session(engine) as db:
        cache_entry = MerchantDiscoveryCache(
            raw_merchant_name="BADASTOOR BHOPAL",
            normalized_merchant_name="badastoor bhopal",
            city="Bhopal",
            state="Madhya Pradesh",
            discovered_name="Ba-Dastoor",
            business_type="Restaurant",
            category="Food & Dining",
            source="ai_discovery",
            confidence_score=0.91,
        )
        db.add(cache_entry)
        db.commit()
        db.refresh(cache_entry)
        read_entry = db.query(MerchantDiscoveryCache).filter(MerchantDiscoveryCache.id == cache_entry.id).one()
    assert read_entry.raw_merchant_name == "BADASTOOR BHOPAL"
    assert read_entry.country == "India"
    assert read_entry.use_count == 1
    assert enum_value(read_entry.source) == "ai_discovery"
