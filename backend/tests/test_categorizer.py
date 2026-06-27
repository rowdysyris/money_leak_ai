"""Hybrid categorization engine tests for MoneyLeak AI."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import services.ai_merchant_discovery as ai_merchant_discovery
from database import engine
from main import app
from models import Statement, Transaction
from services.categorizer import categorize_transaction


def unique_email(prefix: str = "categorizer") -> str:
    """Return a unique email address for categorizer API tests."""
    return f"{prefix}-{uuid4().hex}@example.com"


def register_test_user(client: TestClient, city: str = "Bhopal") -> dict:
    """Register a test user and return the response data."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": unique_email(),
            "password": "SecurePass123",
            "full_name": "Categorizer User",
            "profile_type": "Student",
            "city": city,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def create_statement_and_transaction(user_id: str, merchant: str, category: str = "Miscellaneous") -> UUID:
    """Create a statement and one transaction for endpoint correction tests."""
    with Session(engine) as db:
        statement = Statement(
            user_id=UUID(user_id),
            original_filename="categorizer.csv",
            file_format="csv",
            total_rows=1,
            processed_rows=1,
            skipped_rows=0,
            processing_status="completed",
        )
        db.add(statement)
        db.flush()
        transaction = Transaction(
            user_id=UUID(user_id),
            statement_id=statement.id,
            transaction_date=date.today(),
            description=f"UPI/{merchant}/TEST",
            merchant=merchant,
            amount=Decimal("250.00"),
            transaction_type="debit",
            category=category,
            category_confidence=0.0,
            category_source="low_confidence",
        )
        db.add(transaction)
        db.commit()
        return transaction.id


def test_swiggy_categorized_food() -> None:
    """Swiggy is categorized as Food & Dining by verified merchant rules."""
    result = categorize_transaction({"merchant": "Swiggy", "description": "UPI/Swiggy"}, str(uuid4()))
    assert result["category"] == "Food & Dining"
    assert result["source"] == "verified_merchant"


def test_netflix_categorized_subscriptions() -> None:
    """Netflix is categorized as Subscriptions by verified merchant rules."""
    result = categorize_transaction({"merchant": "Netflix", "description": "NETFLIX MONTHLY"}, str(uuid4()))
    assert result["category"] == "Subscriptions"


def test_uber_categorized_travel() -> None:
    """Uber is categorized as Travel & Transport by verified merchant rules."""
    result = categorize_transaction({"merchant": "Uber", "description": "UBER TRIP"}, str(uuid4()))
    assert result["category"] == "Travel & Transport"


def test_amazon_ambiguous() -> None:
    """Amazon Pay does not crash and returns an explainable category."""
    result = categorize_transaction({"merchant": "Amazon Pay", "description": "AMAZON PAY UPI"}, str(uuid4()))
    assert result["category"] in {"Shopping", "Miscellaneous"}
    assert result["classification_reason"]


def test_fuzzy_swiggy_variant() -> None:
    """A typo variant of Swiggy fuzzy matches Food & Dining."""
    result = categorize_transaction({"merchant": "Swigyyy", "description": "UPI/Swigyyy"}, str(uuid4()))
    assert result["category"] == "Food & Dining"
    assert result["source"] == "fuzzy_match"


def test_unknown_merchant_low_confidence() -> None:
    """Unknown merchants fall back to Miscellaneous and need review."""
    result = categorize_transaction({"merchant": "XYZPQR", "description": "XYZPQR"}, str(uuid4()))
    assert result["category"] == "Miscellaneous"
    assert result["needs_review"] is True


def test_phone_number_merchant() -> None:
    """Phone-number merchants are treated as low-confidence transfers."""
    result = categorize_transaction({"merchant": "9034567890", "description": "UPI/9034567890"}, str(uuid4()))
    assert result["category"] == "Transfers"
    assert result["confidence"] < 0.5


def test_atm_withdrawal() -> None:
    """ATM withdrawal descriptions map to Cash Withdrawal."""
    result = categorize_transaction({"merchant": "ATM", "description": "ATM CASH WITHDRAWAL"}, str(uuid4()))
    assert result["category"] == "Cash Withdrawal"


def test_user_correction_applied() -> None:
    """After a PATCH correction, the same merchant categorizes from the user rule."""
    client = TestClient(app)
    auth_data = register_test_user(client)
    transaction_id = create_statement_and_transaction(auth_data["user"]["id"], "BADASTOOR")
    response = client.patch(
        f"/api/transactions/{transaction_id}/category",
        json={"category": "Food & Dining"},
        headers={"Authorization": f"Bearer {auth_data['access_token']}"},
    )
    assert response.status_code == 200
    with Session(engine) as db:
        result = categorize_transaction({"merchant": "BADASTOOR", "description": "UPI/BADASTOOR"}, auth_data["user"]["id"], db=db)
    assert result["category"] == "Food & Dining"
    assert result["source"] == "user_rule"


def test_user_rule_priority() -> None:
    """User rules beat verified merchant rules."""
    client = TestClient(app)
    auth_data = register_test_user(client)
    transaction_id = create_statement_and_transaction(auth_data["user"]["id"], "Swiggy")
    response = client.patch(
        f"/api/transactions/{transaction_id}/category",
        json={"category": "Groceries"},
        headers={"Authorization": f"Bearer {auth_data['access_token']}"},
    )
    assert response.status_code == 200
    with Session(engine) as db:
        result = categorize_transaction({"merchant": "Swiggy", "description": "UPI/SWIGGY"}, auth_data["user"]["id"], db=db)
    assert result["category"] == "Groceries"
    assert result["source"] == "user_rule"


def test_missing_ml_model(monkeypatch) -> None:
    """Missing ML model files do not crash and keyword rules still work."""
    monkeypatch.setattr("services.categorizer.MODEL_PATH", __file__ + ".missing")
    result = categorize_transaction({"merchant": "Local Place", "description": "restaurant dinner"}, str(uuid4()))
    assert result["category"] == "Food & Dining"
    assert result["source"] == "keyword_rule"


def test_no_anthropic_key(monkeypatch) -> None:
    """AI merchant discovery returns gracefully when no API key is configured."""
    monkeypatch.setattr(ai_merchant_discovery.settings, "ANTHROPIC_API_KEY", "")
    result = ai_merchant_discovery.discover_merchant("Unknown Shop", "Bhopal")
    assert result["success"] is False
    assert result["reason"] == "no_api_key"


def test_badastoor_unknown() -> None:
    """BADASTOOR is Miscellaneous before user correction."""
    result = categorize_transaction({"merchant": "BADASTOOR", "description": "UPI/BADASTOOR"}, str(uuid4()))
    assert result["category"] == "Miscellaneous"
    assert result["needs_review"] is True


def test_badastoor_after_correction() -> None:
    """BADASTOOR categorizes as Food & Dining after user correction."""
    client = TestClient(app)
    auth_data = register_test_user(client)
    transaction_id = create_statement_and_transaction(auth_data["user"]["id"], "BADASTOOR")
    response = client.patch(
        f"/api/transactions/{transaction_id}/category",
        json={"category": "Food & Dining"},
        headers={"Authorization": f"Bearer {auth_data['access_token']}"},
    )
    assert response.status_code == 200
    with Session(engine) as db:
        result = categorize_transaction({"merchant": "BADASTOOR", "description": "UPI/BADASTOOR"}, auth_data["user"]["id"], db=db)
    assert result["category"] == "Food & Dining"
    assert result["source"] == "user_rule"
