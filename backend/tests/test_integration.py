"""End-to-end API integration flows for MoneyLeak AI."""

import json
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app


def register(client: TestClient, prefix: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"{prefix}-{uuid4().hex}@example.com",
            "password": "SecurePass123",
            "full_name": "Integration User",
            "profile_type": "Student",
            "city": "Bhopal",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def headers(auth: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['access_token']}"}


def upload_csv(client: TestClient, auth: dict, content: str, filename: str = "sbi_statement.csv"):
    return client.post(
        "/api/statements/upload",
        headers=headers(auth),
        files={"file": (filename, content.encode("utf-8"), "text/csv")},
        data={"bank_preset": "auto"},
    )


def sample_csv() -> str:
    return "\n".join(
        [
            "Txn Date,Description,Debit,Credit",
            "01/06/2026,UPI/SWIGGY/FOOD ORDER,450,",
            "02/06/2026,NETFLIX MONTHLY SUBSCRIPTION,649,",
            "03/06/2026,BLINKIT GROCERY ORDER,1200,",
            "04/06/2026,SALARY CREDIT,,40000",
        ]
    )


def test_complete_happy_path() -> None:
    client = TestClient(app)
    auth = register(client, "happy")
    upload = upload_csv(client, auth, sample_csv())
    assert upload.status_code == 201
    upload_data = upload.json()["data"]
    assert upload_data["processed_rows"] == 4
    statement_id = upload_data["statement_id"]

    status_response = client.get(f"/api/statements/{statement_id}", headers=headers(auth))
    assert status_response.status_code == 200
    assert status_response.json()["data"]["statement"]["processing_status"] == "completed"
    statement_list = client.get("/api/statements", headers=headers(auth)).json()["data"]["statements"]
    assert any(item["statement_id"] == statement_id for item in statement_list)

    summary = client.get("/api/dashboard/summary", headers=headers(auth)).json()["data"]
    required_summary = {
        "total_spent",
        "total_received",
        "net_balance_change",
        "total_transactions",
        "top_spending_category",
        "money_leak_score",
        "possible_monthly_savings",
        "possible_yearly_savings",
        "uncategorized_transactions",
    }
    assert required_summary.issubset(summary)
    assert summary["total_transactions"] == 4
    for endpoint in ("category-breakdown", "needs-wants-waste", "top-merchants"):
        response = client.get(f"/api/dashboard/{endpoint}", headers=headers(auth))
        assert response.status_code == 200
        assert response.json()["success"] is True
    for endpoint in ("money-leak-score", "subscriptions", "saving-priority-list", "small-spend-leaks", "merchant-addiction"):
        response = client.get(f"/api/insights/{endpoint}", headers=headers(auth))
        assert response.status_code == 200

    transactions = client.get("/api/transactions", headers=headers(auth)).json()["data"]["transactions"]
    swiggy = next(item for item in transactions if "SWIGGY" in str(item["description"]).upper())
    corrected = client.patch(
        f"/api/transactions/{swiggy['id']}/category",
        headers=headers(auth),
        json={"category": "Groceries"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["data"]["transaction"]["category"] == "Groceries"
    rules = client.get("/api/transactions/category-rules", headers=headers(auth)).json()["data"]["rules"]
    assert any(rule["category"] == "Groceries" for rule in rules)

    assert client.post("/api/budget/setup", headers=headers(auth), json={"food_budget": 2000}).status_code == 200
    budget = client.get("/api/budget/status", headers=headers(auth)).json()["data"]
    assert "category_status" in budget
    for report_type in ("csv", "excel", "pdf"):
        report = client.get(f"/api/reports/download/{report_type}", headers=headers(auth))
        assert report.status_code == 200
        assert report.content


def test_messy_file_upload_keeps_valid_rows() -> None:
    client = TestClient(app)
    auth = register(client, "messy")
    messy = "\n".join(
        [
            "Account Statement for Customer",
            "Generated,27/06/2026",
            "Date,Description,Debit,Credit",
            '01/06/2026,UPI/CAFE,"₹1,234.50",',
            "2026-06-02,UPI/SHOP,250,",
            "not-a-date,BROKEN ROW,100,",
            ",,,",
        ]
    )
    response = upload_csv(client, auth, messy, "messy.csv")
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["processed_rows"] == 2
    assert data["skipped_rows"] >= 1
    assert data["warnings"]
    assert client.get("/api/dashboard/summary", headers=headers(auth)).status_code == 200


def test_wrong_files_return_controlled_envelopes() -> None:
    client = TestClient(app)
    auth = register(client, "wrong-file")
    cases = [
        ("statement.pdf", b"%PDF-1.7", "PDF_NOT_SUPPORTED"),
        ("renamed.csv", b"%PDF-1.7", "FILE_CONTENT_MISMATCH"),
        ("empty.csv", b"", "EMPTY_FILE"),
        ("missing-date.csv", b"Description,Debit\nCafe,100", "MISSING_DATE_COLUMN"),
    ]
    for filename, content, expected_code in cases:
        response = client.post(
            "/api/statements/upload",
            headers=headers(auth),
            files={"file": (filename, content, "application/octet-stream")},
        )
        assert response.status_code in {400, 413}
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == expected_code


def test_auth_and_cross_user_ownership() -> None:
    client = TestClient(app)
    owner = register(client, "owner")
    other = register(client, "other")
    statement_id = upload_csv(client, owner, sample_csv()).json()["data"]["statement_id"]
    transaction_id = client.get("/api/transactions", headers=headers(owner)).json()["data"]["transactions"][0]["id"]
    assert client.get("/api/dashboard/summary").status_code == 401
    forbidden_statement = client.get(f"/api/statements/{statement_id}", headers=headers(other))
    assert forbidden_statement.status_code == 403
    assert forbidden_statement.json()["error"]["code"] == "FORBIDDEN"
    forbidden_transaction = client.patch(
        f"/api/transactions/{transaction_id}/category",
        headers=headers(other),
        json={"category": "Shopping"},
    )
    assert forbidden_transaction.status_code == 403
    assert forbidden_transaction.json()["error"]["code"] == "FORBIDDEN"


def test_empty_state_endpoints_are_graceful() -> None:
    client = TestClient(app)
    auth = register(client, "empty-state")
    for endpoint in (
        "/api/dashboard/summary",
        "/api/insights/subscriptions",
        "/api/insights/duplicates",
        "/api/budget/status",
        "/api/insights/smart-alerts",
    ):
        response = client.get(endpoint, headers=headers(auth))
        assert response.status_code == 200
        assert response.json()["success"] is True


def test_low_confidence_mapping_requires_confirmation_before_persistence() -> None:
    client = TestClient(app)
    auth = register(client, "mapping")
    content = "Booking Date Field,Transaction Details Extra,Transaction Amount Value\n01/06/2026,UPI/CAFE,250"
    first = upload_csv(client, auth, content, "custom_headers.csv")
    assert first.status_code == 201
    first_data = first.json()["data"]
    assert first_data["requires_column_mapping"] is True
    assert first_data["statement_id"] is None
    assert first_data["parser_metadata"]["mapping_confidence"] < 0.7
    assert first_data["parser_metadata"]["source_columns"] == [
        "Booking Date Field",
        "Transaction Details Extra",
        "Transaction Amount Value",
    ]
    assert client.get("/api/statements", headers=headers(auth)).json()["data"]["statements"] == []

    confirmed = client.post(
        "/api/statements/upload",
        headers=headers(auth),
        files={"file": ("custom_headers.csv", content.encode(), "text/csv")},
        data={
            "bank_preset": "auto",
            "column_mapping": json.dumps(
                {
                    "date": "Booking Date Field",
                    "description": "Transaction Details Extra",
                    "amount": "Transaction Amount Value",
                }
            ),
        },
    )
    assert confirmed.status_code == 201
    confirmed_data = confirmed.json()["data"]
    assert confirmed_data["statement_id"]
    assert confirmed_data["processed_rows"] == 1
