"""Integration tests spanning upload, ML fallback, agents, RAG-adjacent memory, and insights."""

from uuid import uuid4

from fastapi.testclient import TestClient

from main import app


def register(client: TestClient) -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "email": f"ml-ai-{uuid4().hex}@example.com",
            "password": "SecurePass123",
            "full_name": "ML AI User",
            "profile_type": "Working Professional",
            "city": "Bhopal",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def headers(auth: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['access_token']}"}


def fake_merchant_csv() -> str:
    rows = ["Date,Description,Debit,Credit"]
    for day in range(1, 9):
        rows.append(f"{day:02d}/06/2026,TESTMERCHANT99 CLOUD STORAGE SUBSCRIPTION,{100 + day * 10},")
    rows.append("09/06/2026,SALARY CREDIT,,30000")
    return "\n".join(rows)


def upload(client: TestClient, auth: dict):
    return client.post(
        "/api/statements/upload",
        headers=headers(auth),
        files={"file": ("unknown_merchant.csv", fake_merchant_csv().encode(), "text/csv")},
    )


def test_complete_upload_ml_agent_insight_flow() -> None:
    client = TestClient(app)
    auth = register(client)
    upload_response = upload(client, auth)
    assert upload_response.status_code == 201
    statement_id = upload_response.json()["data"]["statement_id"]

    transaction_response = client.get(
        "/api/transactions",
        headers=headers(auth),
        params={"statement_id": statement_id},
    )
    transactions = transaction_response.json()["data"]["transactions"]
    assert len(transactions) == 9
    unknown_rows = [row for row in transactions if "TESTMERCHANT99" in str(row["description"])]
    assert unknown_rows
    assert any(row["category_source"] == "ml_fallback" for row in unknown_rows)
    assert all(isinstance(row["is_anomaly"], bool) for row in transactions)

    personality = client.get("/api/insights/spending-personality", headers=headers(auth))
    assert personality.status_code == 200
    assert personality.json()["data"]["personality_type"]
    forecast = client.get("/api/insights/month-end-survival", headers=headers(auth))
    assert forecast.status_code == 200
    assert "monthly_projection" in forecast.json()["data"]
    merchant_risk = client.get("/api/insights/merchant-addiction", headers=headers(auth))
    assert merchant_risk.status_code == 200
    assert merchant_risk.json()["data"]

    analyze = client.post(
        "/api/agents/analyze",
        headers=headers(auth),
        json={"statement_id": statement_id},
    )
    assert analyze.status_code == 200
    run_id = analyze.json()["data"]["run_id"]
    status_response = client.get(f"/api/agents/status/{run_id}", headers=headers(auth))
    assert status_response.status_code == 200
    run = status_response.json()["data"]
    assert run["status"] == "completed"
    assert {"diagnosis", "recommendations", "ai_enhanced"}.issubset(run["output_summary"])


def test_user_correction_is_reused_on_next_upload() -> None:
    client = TestClient(app)
    auth = register(client)
    first_statement = upload(client, auth).json()["data"]["statement_id"]
    first_rows = client.get(
        "/api/transactions",
        headers=headers(auth),
        params={"statement_id": first_statement},
    ).json()["data"]["transactions"]
    target = next(row for row in first_rows if "TESTMERCHANT99" in str(row["description"]))
    correction = client.patch(
        f"/api/transactions/{target['id']}/category",
        headers=headers(auth),
        json={"category": "Food & Dining"},
    )
    assert correction.status_code == 200

    second_statement = upload(client, auth).json()["data"]["statement_id"]
    second_rows = client.get(
        "/api/transactions",
        headers=headers(auth),
        params={"statement_id": second_statement},
    ).json()["data"]["transactions"]
    repeated = [row for row in second_rows if "TESTMERCHANT99" in str(row["description"])]
    assert repeated
    assert all(row["category"] == "Food & Dining" for row in repeated)
    assert all(row["category_source"] == "user_rule" for row in repeated)
