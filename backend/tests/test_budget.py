"""Budget management and correction memory tests for MoneyLeak AI."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database import engine
from main import app
from models import LearnedMerchantRule, Statement, Transaction, TransactionCategoryFeedback, UserCategoryRule


def unique_email(prefix: str = "budget") -> str:
    """Return a unique email address for budget tests."""
    return f"{prefix}-{uuid4().hex}@example.com"


def register_test_user(client: TestClient, prefix: str = "budget") -> dict:
    """Register a user and return auth response data."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": unique_email(prefix),
            "password": "SecurePass123",
            "full_name": "Budget User",
            "profile_type": "Student",
            "city": "Bhopal",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def auth_headers(auth_data: dict) -> dict[str, str]:
    """Return authorization headers for an authenticated user."""
    return {"Authorization": f"Bearer {auth_data['access_token']}"}


def create_statement(user_id: str) -> UUID:
    """Create a completed statement for test transactions."""
    with Session(engine) as db:
        statement = Statement(
            user_id=UUID(user_id),
            original_filename="budget.csv",
            file_format="csv",
            total_rows=1,
            processed_rows=1,
            skipped_rows=0,
            processing_status="completed",
        )
        db.add(statement)
        db.commit()
        return statement.id


def create_transaction(
    user_id: str,
    statement_id: UUID,
    merchant: str,
    amount: Decimal,
    category: str,
    transaction_type: str = "debit",
) -> UUID:
    """Create one transaction for budget and correction tests."""
    with Session(engine) as db:
        transaction = Transaction(
            user_id=UUID(user_id),
            statement_id=statement_id,
            transaction_date=date.today(),
            description=f"UPI/{merchant}/TEST",
            merchant=merchant,
            amount=amount,
            transaction_type=transaction_type,
            category=category,
            category_confidence=0.0,
            category_source="low_confidence",
        )
        db.add(transaction)
        db.commit()
        return transaction.id


def test_budget_setup_full() -> None:
    """Budget setup stores every budget field when provided."""
    client = TestClient(app)
    auth_data = register_test_user(client, "budget-full")
    response = client.post(
        "/api/budget/setup",
        json={
            "total_monthly_limit": 20000,
            "savings_target": 3000,
            "food_budget": 4000,
            "shopping_budget": 2500,
            "subscriptions_budget": 800,
            "travel_budget": 2000,
            "bills_budget": 3500,
            "custom_budgets": {"Health & Medical": 1000},
        },
        headers=auth_headers(auth_data),
    )
    assert response.status_code == 200
    budget = response.json()["data"]["budget"]
    assert budget["total_monthly_limit"] == 20000.0
    assert budget["food_budget"] == 4000.0
    assert budget["custom_budgets"]["Health & Medical"] == 1000.0


def test_budget_setup_partial_fields() -> None:
    """Budget setup accepts partial payloads with optional fields omitted."""
    client = TestClient(app)
    auth_data = register_test_user(client, "budget-partial")
    response = client.post("/api/budget/setup", json={"food_budget": 2500}, headers=auth_headers(auth_data))
    assert response.status_code == 200
    budget = response.json()["data"]["budget"]
    assert budget["food_budget"] == 2500.0
    assert budget["shopping_budget"] is None


def test_budget_status_shows_correct_remaining() -> None:
    """Budget status calculates spent and remaining values for current-month transactions."""
    client = TestClient(app)
    auth_data = register_test_user(client, "budget-status")
    statement_id = create_statement(auth_data["user"]["id"])
    create_transaction(auth_data["user"]["id"], statement_id, "Swiggy", Decimal("400.00"), "Food & Dining")
    setup_response = client.post("/api/budget/setup", json={"food_budget": 1000}, headers=auth_headers(auth_data))
    assert setup_response.status_code == 200
    response = client.get("/api/budget/status", headers=auth_headers(auth_data))
    assert response.status_code == 200
    category_status = response.json()["data"]["category_status"]
    food_status = next(item for item in category_status if item["category"] == "Food & Dining")
    assert food_status["spent"] == 400.0
    assert food_status["remaining"] == 600.0
    assert food_status["status"] == "ok"


def test_budget_exceeded_status() -> None:
    """Budget status marks categories as exceeded when spending is above the limit."""
    client = TestClient(app)
    auth_data = register_test_user(client, "budget-exceeded")
    statement_id = create_statement(auth_data["user"]["id"])
    create_transaction(auth_data["user"]["id"], statement_id, "Amazon", Decimal("1500.00"), "Shopping")
    client.post("/api/budget/setup", json={"shopping_budget": 1000}, headers=auth_headers(auth_data))
    response = client.get("/api/budget/status", headers=auth_headers(auth_data))
    assert response.status_code == 200
    shopping_status = next(item for item in response.json()["data"]["category_status"] if item["category"] == "Shopping")
    assert shopping_status["status"] == "exceeded"
    assert shopping_status["remaining"] == -500.0


def test_budget_update_partial() -> None:
    """PATCH budget update only changes provided fields."""
    client = TestClient(app)
    auth_data = register_test_user(client, "budget-update")
    client.post("/api/budget/setup", json={"food_budget": 1000, "shopping_budget": 500}, headers=auth_headers(auth_data))
    response = client.patch("/api/budget/update", json={"food_budget": 1500}, headers=auth_headers(auth_data))
    assert response.status_code == 200
    budget = response.json()["data"]["budget"]
    assert budget["food_budget"] == 1500.0
    assert budget["shopping_budget"] == 500.0


def test_budget_with_no_transactions_graceful() -> None:
    """Budget status returns a warning and zero spend when the user has no current transactions."""
    client = TestClient(app)
    auth_data = register_test_user(client, "budget-empty")
    client.post("/api/budget/setup", json={"food_budget": 1000}, headers=auth_headers(auth_data))
    response = client.get("/api/budget/status", headers=auth_headers(auth_data))
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "No transactions found for the current month." in body["warnings"]
    assert body["data"]["category_status"][0]["spent"] == 0.0


def test_correction_saves_user_rule() -> None:
    """Category correction persists a user-specific merchant rule and feedback row."""
    client = TestClient(app)
    auth_data = register_test_user(client, "correction-rule")
    statement_id = create_statement(auth_data["user"]["id"])
    transaction_id = create_transaction(auth_data["user"]["id"], statement_id, "BADASTOOR", Decimal("250.00"), "Miscellaneous")
    response = client.patch(
        f"/api/transactions/{transaction_id}/category",
        json={"category": "Food & Dining"},
        headers=auth_headers(auth_data),
    )
    assert response.status_code == 200
    with Session(engine) as db:
        rule = db.query(UserCategoryRule).filter(UserCategoryRule.user_id == UUID(auth_data["user"]["id"])).first()
        feedback = db.query(TransactionCategoryFeedback).filter(TransactionCategoryFeedback.transaction_id == transaction_id).first()
        assert rule is not None
        assert rule.category == "Food & Dining"
        assert feedback is not None
        assert feedback.corrected_category == "Food & Dining"


def test_category_rule_management_endpoints_are_user_scoped() -> None:
    """Users can manage saved category rules without seeing another user's rules."""
    client = TestClient(app)
    owner = register_test_user(client, "rule-owner")
    other = register_test_user(client, "rule-other")
    statement_id = create_statement(owner["user"]["id"])
    transaction_id = create_transaction(owner["user"]["id"], statement_id, "BADASTOOR", Decimal("250.00"), "Miscellaneous")

    create_response = client.post(
        "/api/transactions/category-rules",
        json={"merchant_normalized": "BADASTOOR", "category": "Food & Dining", "apply_to_existing": True},
        headers=auth_headers(owner),
    )
    assert create_response.status_code == 200
    body = create_response.json()["data"]
    assert body["rule"]["merchant_normalized"] == "badastoor"
    assert body["applied_count"] == 1

    owner_list = client.get("/api/transactions/category-rules", headers=auth_headers(owner))
    other_list = client.get("/api/transactions/category-rules", headers=auth_headers(other))
    assert len(owner_list.json()["data"]["rules"]) == 1
    assert other_list.json()["data"]["rules"] == []

    with Session(engine) as db:
        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        assert transaction.category == "Food & Dining"

    rule_id = body["rule"]["id"]
    delete_response = client.delete(f"/api/transactions/category-rules/{rule_id}", headers=auth_headers(owner))
    assert delete_response.status_code == 200
    assert delete_response.json()["data"]["deleted"] is True


def test_correction_updates_learned_rule_after_threshold() -> None:
    """Three distinct user corrections create a learned merchant rule with threshold confidence."""
    client = TestClient(app)
    transaction_ids: list[UUID] = []
    auth_records: list[dict] = []
    for index in range(3):
        auth_data = register_test_user(client, f"learned-{index}")
        auth_records.append(auth_data)
        statement_id = create_statement(auth_data["user"]["id"])
        transaction_ids.append(create_transaction(auth_data["user"]["id"], statement_id, "BADASTOOR", Decimal("200.00"), "Miscellaneous"))

    for auth_data, transaction_id in zip(auth_records, transaction_ids):
        response = client.patch(
            f"/api/transactions/{transaction_id}/category",
            json={"category": "Food & Dining"},
            headers=auth_headers(auth_data),
        )
        assert response.status_code == 200

    with Session(engine) as db:
        learned_rule = db.query(LearnedMerchantRule).filter(LearnedMerchantRule.merchant_normalized == "badastoor").first()
        assert learned_rule is not None
        assert learned_rule.category == "Food & Dining"
        assert learned_rule.correction_count >= 3
        assert 0.8 <= learned_rule.confidence <= 0.9
