"""Authentication and health endpoint tests for MoneyLeak AI."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from database import Base, engine
from main import app


@pytest.fixture(scope="session", autouse=True)
def prepare_database() -> None:
    """Create database tables required by the test suite."""
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def client() -> TestClient:
    """Return a FastAPI test client."""
    return TestClient(app)


def unique_email(prefix: str = "user") -> str:
    """Return a unique test email address."""
    return f"{prefix}-{uuid4().hex}@example.com"


def valid_register_payload(email: str | None = None) -> dict:
    """Return a valid registration payload for tests."""
    return {
        "email": email or unique_email(),
        "password": "SecurePass123",
        "full_name": "Test User",
        "profile_type": "Student",
        "city": "Bhopal",
    }


def register_user(client: TestClient, email: str | None = None) -> dict:
    """Register a user through the API and return the response payload."""
    response = client.post("/api/auth/register", json=valid_register_payload(email))
    assert response.status_code == 201
    return response.json()


def test_health_check(client: TestClient) -> None:
    """GET /health returns service health."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] in {"connected", "unreachable"}
    assert "timestamp" in body


def test_ready_check_uses_standard_envelope(client: TestClient) -> None:
    """GET /ready returns a deployment readiness envelope."""
    response = client.get("/ready")
    assert response.status_code in {200, 503}
    body = response.json()
    assert body["success"] is (response.status_code == 200)
    assert "X-Request-ID" in response.headers


def test_request_id_header_is_preserved(client: TestClient) -> None:
    """Request middleware preserves an incoming request ID."""
    response = client.get("/health", headers={"X-Request-ID": "test-request-id"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"


def test_register_success(client: TestClient) -> None:
    """New user registration returns a bearer token and user object."""
    response = client.post("/api/auth/register", json=valid_register_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["access_token"]
    assert body["data"]["user"]["email"]


def test_register_duplicate_email(client: TestClient) -> None:
    """Duplicate registration returns EMAIL_EXISTS."""
    email = unique_email("duplicate")
    first_response = client.post("/api/auth/register", json=valid_register_payload(email))
    assert first_response.status_code == 201
    second_response = client.post("/api/auth/register", json=valid_register_payload(email))
    assert second_response.status_code == 409
    body = second_response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "EMAIL_EXISTS"


def test_register_invalid_email(client: TestClient) -> None:
    """Invalid email registration returns validation error."""
    payload = valid_register_payload()
    payload["email"] = "invalid-email"
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_register_short_password(client: TestClient) -> None:
    """Short password registration returns validation error."""
    payload = valid_register_payload()
    payload["password"] = "short"
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_register_invalid_profile_type(client: TestClient) -> None:
    """Invalid profile type registration returns validation error."""
    payload = valid_register_payload()
    payload["profile_type"] = "Investor"
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_success(client: TestClient) -> None:
    """Valid login returns a bearer token."""
    email = unique_email("login")
    register_user(client, email)
    response = client.post("/api/auth/login", json={"email": email, "password": "SecurePass123"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["access_token"]


def test_login_wrong_password(client: TestClient) -> None:
    """Wrong password returns INVALID_CREDENTIALS."""
    email = unique_email("wrong-password")
    register_user(client, email)
    response = client.post("/api/auth/login", json={"email": email, "password": "WrongPass123"})
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_nonexistent_email(client: TestClient) -> None:
    """Login with a nonexistent account returns INVALID_CREDENTIALS."""
    response = client.post("/api/auth/login", json={"email": unique_email("missing"), "password": "SecurePass123"})
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_CREDENTIALS"


def test_get_me_authenticated(client: TestClient) -> None:
    """Authenticated users can retrieve their profile."""
    auth_body = register_user(client)
    token = auth_body["data"]["access_token"]
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["user"]["email"] == auth_body["data"]["user"]["email"]


def test_get_me_no_token(client: TestClient) -> None:
    """Missing token returns NOT_AUTHENTICATED."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_AUTHENTICATED"


def test_get_me_invalid_token(client: TestClient) -> None:
    """Invalid token returns INVALID_TOKEN."""
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.value"})
    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_TOKEN"
