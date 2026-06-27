"""Security, parser, and analytics hardening regression tests."""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

from config import Settings
from services.analytics_utils import percentage
from services.burn_rate_analyzer import analyze_burn_rate
from services.dashboard_service import get_summary, get_top_merchants
from services.duplicate_detector import detect_duplicates
from services.money_leak_score import calculate_score
from services.security import sanitize_filename, validate_magic_bytes
from services.statement_parser import parse_statement
from services.subscription_detector import detect_subscriptions
from services.transaction_cleaner import clean_transactions


def csv_bytes(body: str) -> bytes:
    """Return UTF-8 encoded CSV bytes."""
    return body.encode("utf-8")


def base_column_map() -> dict[str, str | None]:
    """Return a reusable statement column map for cleaner tests."""
    return {"date": "Date", "description": "Description", "amount": "Amount", "debit": None, "credit": None, "balance": "Balance"}


def make_transaction(amount: float, category: str = "Food & Dining", merchant: str = "Swiggy", tx_date: str = "2024-01-01", tx_type: str = "debit") -> dict[str, object]:
    """Build a minimal transaction dictionary for analytics tests."""
    return {
        "id": f"{merchant}-{tx_date}-{amount}",
        "transaction_date": tx_date,
        "merchant": merchant,
        "description": merchant,
        "amount": -abs(amount) if tx_type == "debit" else abs(amount),
        "transaction_type": tx_type,
        "category": category,
        "need_want_waste_type": "want" if category in {"Food & Dining", "Shopping", "Subscriptions"} else "need",
        "is_refund": False,
        "is_cashback": False,
    }


def test_upload_csv_with_bom_character_parses() -> None:
    """Verify CSV files with UTF-8 BOM are parsed successfully."""
    content = "\ufeffDate,Description,Amount\n01-01-2024,Swiggy,250\n"
    result = parse_statement(content.encode("utf-8"), "statement.csv")
    assert result["success"] is True
    assert result["data"]["total_rows"] == 1


def test_upload_csv_with_pdf_magic_rejected() -> None:
    """Verify a fake CSV containing PDF magic bytes is rejected."""
    result = parse_statement(b"%PDF-1.4 fake", "statement.csv")
    assert result["success"] is False
    assert result["error"]["code"] in {"FILE_CONTENT_MISMATCH", "PDF_NOT_SUPPORTED"}


def test_excel_with_merged_metadata_header_parses() -> None:
    """Verify Excel files with merged metadata cells before the table header parse."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.merge_cells("A1:C1")
    sheet["A1"] = "Account statement metadata"
    sheet.append(["Date", "Description", "Amount"])
    sheet.append(["01-01-2024", "Netflix", "499"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    result = parse_statement(buffer.getvalue(), "statement.xlsx")
    assert result["success"] is True
    assert result["data"]["total_rows"] == 1


def test_file_with_only_header_row_returns_empty_table() -> None:
    """Verify header-only statements return a controlled empty-table error."""
    result = parse_statement(csv_bytes("Date,Description,Amount\n"), "statement.csv")
    assert result["success"] is False
    assert result["error"]["code"] == "EMPTY_TABLE"


def test_all_refunds_or_credits_do_not_crash() -> None:
    """Verify all-credit statements clean without requiring debit rows."""
    df = pd.DataFrame([
        {"Date": "01-01-2024", "Description": "Salary credited", "Amount": "50000"},
        {"Date": "02-01-2024", "Description": "REFUND Amazon", "Amount": "999"},
    ])
    result = clean_transactions(df, base_column_map())
    assert len(result["transactions"]) == 2
    assert all(transaction["transaction_type"] == "credit" for transaction in result["transactions"])


def test_file_with_only_one_transaction_cleans() -> None:
    """Verify a single transaction is enough for parser/cleaner success."""
    df = pd.DataFrame([{"Date": "01-01-2024", "Description": "Swiggy", "Amount": "250"}])
    result = clean_transactions(df, base_column_map())
    assert len(result["transactions"]) == 1


def test_amount_zero_skipped_without_crash() -> None:
    """Verify zero-value rows are skipped safely."""
    df = pd.DataFrame([{"Date": "01-01-2024", "Description": "Zero amount", "Amount": "0"}])
    result = clean_transactions(df, base_column_map())
    assert result["transactions"] == []
    assert result["skipped_rows"]


def test_very_large_amount_flagged_for_review() -> None:
    """Verify amounts above one crore are retained but flagged for review."""
    df = pd.DataFrame([{"Date": "01-01-2024", "Description": "Property payment", "Amount": "10000001"}])
    result = clean_transactions(df, base_column_map())
    assert result["transactions"][0]["needs_review"] is True
    assert any("Very large" in warning for warning in result["warnings"])


def test_negative_balance_column_does_not_block_cleaning() -> None:
    """Verify negative balance values do not affect transaction cleaning."""
    df = pd.DataFrame([{"Date": "01-01-2024", "Description": "Swiggy", "Amount": "250", "Balance": "-100"}])
    result = clean_transactions(df, base_column_map())
    assert len(result["transactions"]) == 1


def test_future_date_flagged_for_review() -> None:
    """Verify future transaction dates are not allowed to distort analytics silently."""
    future_year = date.today().year + 1
    df = pd.DataFrame([{"Date": f"01-01-{future_year}", "Description": "Future payment", "Amount": "250"}])
    result = clean_transactions(df, base_column_map())
    assert result["transactions"][0]["needs_review"] is True
    assert any("future" in warning.lower() for warning in result["warnings"])


def test_date_before_year_2000_flagged_for_review() -> None:
    """Verify very old transaction dates are flagged for review."""
    df = pd.DataFrame([{"Date": "01-01-1999", "Description": "Old payment", "Amount": "250"}])
    result = clean_transactions(df, base_column_map())
    assert result["transactions"][0]["needs_review"] is True
    assert any("before year 2000" in warning for warning in result["warnings"])


def test_special_character_description_is_safe() -> None:
    """Verify descriptions with special characters do not break cleaning."""
    df = pd.DataFrame([{"Date": "01-01-2024", "Description": "/\\|\"'<>&", "Amount": "250"}])
    result = clean_transactions(df, base_column_map())
    assert len(result["transactions"]) == 1


def test_whitespace_description_needs_review() -> None:
    """Verify whitespace-only descriptions produce Unknown merchant and review flag."""
    df = pd.DataFrame([{"Date": "01-01-2024", "Description": "   ", "Amount": "250"}])
    result = clean_transactions(df, base_column_map())
    assert result["transactions"][0]["merchant"] == "Unknown"
    assert result["transactions"][0]["needs_review"] is True


def test_numeric_only_merchant_needs_review() -> None:
    """Verify numeric-only merchant descriptions are treated as review-needed."""
    df = pd.DataFrame([{"Date": "01-01-2024", "Description": "9034567890", "Amount": "250"}])
    result = clean_transactions(df, base_column_map())
    assert result["transactions"][0]["merchant"] == "Unknown"
    assert result["transactions"][0]["needs_review"] is True


def test_single_positive_amount_defaults_to_debit_unless_credit_keywords() -> None:
    """Verify all-positive single amount columns infer debits unless description implies credit."""
    df = pd.DataFrame([
        {"Date": "01-01-2024", "Description": "Swiggy", "Amount": "250"},
        {"Date": "02-01-2024", "Description": "Salary credited", "Amount": "50000"},
    ])
    result = clean_transactions(df, base_column_map())
    by_description = {transaction["description"]: transaction["transaction_type"] for transaction in result["transactions"]}
    assert by_description["Swiggy"] == "debit"
    assert by_description["Salary credited"] == "credit"


def test_all_transactions_same_date_burn_rate_safe() -> None:
    """Verify same-day transaction periods do not divide by zero."""
    transactions = [make_transaction(100, tx_date="2024-01-01"), make_transaction(200, tx_date="2024-01-01")]
    result = analyze_burn_rate(transactions, current_balance=Decimal("1000"))
    assert result["data"]["days_in_period"] == 1
    assert result["data"]["daily_burn_rate"] == 300


def test_all_transactions_same_merchant_concentration_safe() -> None:
    """Verify all-same-merchant concentration analysis produces bounded risk output."""
    transactions = [make_transaction(100, merchant="Swiggy", tx_date=f"2024-01-0{i}") for i in range(1, 4)]
    result = get_top_merchants(transactions)
    assert result["data"][0]["merchant"] == "Swiggy"
    assert result["data"][0]["risk_level"] == "high"


def test_percentage_calculations_capped_and_floored() -> None:
    """Verify percentage helper never goes below 0 or above 100."""
    assert percentage(150, 100) == 100.0
    assert percentage(-10, 100) == 0.0
    assert percentage(1, 0) == 0.0


def test_money_leak_score_with_zero_transactions_safe() -> None:
    """Verify empty score calculation returns a healthy default instead of crashing."""
    result = calculate_score([], [], [])
    assert result["data"]["score"] == 0.0
    assert result["warnings"]


def test_subscription_detection_one_occurrence_each_safe() -> None:
    """Verify one-off merchants are not incorrectly detected as subscriptions."""
    transactions = [make_transaction(499, merchant="Netflix"), make_transaction(199, merchant="Spotify", tx_date="2024-01-02")]
    result = detect_subscriptions(transactions)
    assert result["data"] == []


def test_duplicate_detection_zero_transactions_safe() -> None:
    """Verify duplicate detection handles empty input safely."""
    result = detect_duplicates([])
    assert result["data"] == []
    assert result["warnings"]


def test_burn_rate_current_balance_zero_safe() -> None:
    """Verify burn-rate survival handles zero balance safely."""
    transactions = [make_transaction(100, tx_date="2024-01-01"), make_transaction(200, tx_date="2024-01-02")]
    result = analyze_burn_rate(transactions, current_balance=0)
    assert result["data"]["days_until_empty"] == 0


def test_burn_rate_current_balance_none_warns() -> None:
    """Verify missing current balance returns partial burn-rate result with warning."""
    result = analyze_burn_rate([make_transaction(100)], current_balance=None)
    assert result["data"]["daily_safe_limit"] is None
    assert any("Current balance" in warning for warning in result["warnings"])


def test_summary_no_debits_all_credits_safe() -> None:
    """Verify summary handles statements with no spending."""
    result = get_summary([make_transaction(50000, category="Salary", merchant="Salary", tx_type="credit")])
    assert result["data"]["total_spent"] == 0.0
    assert result["data"]["total_received"] == 50000.0


def test_filename_sanitization_blocks_path_traversal_and_script_chars() -> None:
    """Verify filenames cannot carry paths or script-injection characters."""
    sanitized = sanitize_filename("../../<script>alert(1)</script>.csv")
    assert ".." not in sanitized
    assert "<" not in sanitized and ">" not in sanitized
    assert sanitized.endswith(".csv")


def test_magic_byte_helper_rejects_mismatched_content() -> None:
    """Verify magic-byte validation rejects content-extension mismatches."""
    result = validate_magic_bytes(b"%PDF-1.7", "statement.csv")
    assert result is not None
    assert result["code"] in {"FILE_CONTENT_MISMATCH", "PDF_NOT_SUPPORTED"}


def test_env_files_are_gitignored() -> None:
    """Verify .env files are ignored by Git."""
    gitignore = Path("../.gitignore").read_text()
    assert ".env" in gitignore
    assert "backend/.env" in gitignore


def test_no_hardcoded_jwt_or_api_secrets_in_code() -> None:
    """Verify code does not contain obvious hardcoded API secrets."""
    backend = Path(".")
    forbidden_markers = ["sk-" + "ant-", "sk-" + "proj-", "BEGIN " + "PRIVATE KEY"]
    for path in backend.rglob("*.py"):
        if ".venv" in path.parts or path.name == "test_security_hardening.py":
            continue
        content = path.read_text(errors="ignore")
        assert not any(marker in content for marker in forbidden_markers), str(path)


def test_no_obvious_raw_sql_interpolation() -> None:
    """Verify no obvious f-string SQL execution is present."""
    for path in Path(".").rglob("*.py"):
        if ".venv" in path.parts or path.name == "test_security_hardening.py":
            continue
        content = path.read_text(errors="ignore")
        assert ".execute" + "(f" not in content
        assert "text" + "(f" not in content


def test_user_schema_does_not_expose_hashed_password() -> None:
    """Verify public user schema definitions do not expose hashed_password."""
    user_schema = Path("schemas/user.py").read_text()
    auth_schema = Path("schemas/auth.py").read_text()
    assert "hashed_password" not in user_schema
    assert "hashed_password" not in auth_schema


def test_production_cors_rejects_wildcard() -> None:
    """Verify wildcard CORS origins are not allowed in production settings."""
    settings = Settings(ENVIRONMENT="production", ALLOWED_ORIGINS="*,https://app.example.com")
    assert settings.cors_origins() == ["https://app.example.com"]

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.budget_service import get_budget_status
from services.security import verify_statement_ownership


class FakeQuery:
    """Minimal query stub for budget and ownership hardening tests."""

    def __init__(self, result: object | None = None, rows: list[object] | None = None) -> None:
        """Store deterministic first/all results."""
        self.result = result
        self.rows = rows or []

    def filter(self, *args: object, **kwargs: object) -> "FakeQuery":
        """Return self for chained filter calls."""
        return self

    def first(self) -> object | None:
        """Return configured first result."""
        return self.result

    def all(self) -> list[object]:
        """Return configured row list."""
        return self.rows


class FakeBudgetDb:
    """Minimal database stub for budget status tests."""

    def __init__(self, budget: object | None) -> None:
        """Store a fake budget object."""
        self.budget = budget

    def query(self, model: object) -> FakeQuery:
        """Return budget for UserBudget queries and no transactions otherwise."""
        model_name = getattr(model, "__name__", "")
        if model_name == "UserBudget":
            return FakeQuery(self.budget)
        return FakeQuery(None, [])


class FakeOwnershipDb:
    """Minimal database stub for statement ownership tests."""

    def __init__(self, statement: object | None) -> None:
        """Store a fake statement object."""
        self.statement = statement

    def query(self, model: object) -> FakeQuery:
        """Return the configured statement regardless of model."""
        return FakeQuery(self.statement)


def test_budget_status_with_no_budget_set_graceful() -> None:
    """Verify budget status returns a warning when no budget exists."""
    result = get_budget_status(FakeBudgetDb(None), uuid4())
    assert result["data"]["budget"] is None
    assert result["warnings"] == ["No budget has been set yet."]


def test_budget_status_with_zero_current_month_transactions() -> None:
    """Verify budget status handles a configured budget with zero monthly transactions."""
    budget = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        total_monthly_limit=Decimal("10000"),
        savings_target=Decimal("1000"),
        food_budget=Decimal("3000"),
        shopping_budget=None,
        subscriptions_budget=None,
        travel_budget=None,
        bills_budget=None,
        custom_budgets={},
        created_at=None,
        updated_at=None,
    )
    result = get_budget_status(FakeBudgetDb(budget), budget.user_id)
    assert result["data"]["total_status"]["spent"] == 0.0
    assert result["data"]["category_status"][0]["remaining"] == 3000.0
    assert "No transactions found for the current month." in result["warnings"]


def test_statement_ownership_mismatch_returns_forbidden() -> None:
    """Verify cross-user statement access raises a 403 error."""
    owner_id = uuid4()
    other_user_id = uuid4()
    statement = SimpleNamespace(id=uuid4(), user_id=owner_id)
    with pytest.raises(HTTPException) as exc_info:
        verify_statement_ownership(FakeOwnershipDb(statement), other_user_id, statement.id)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "FORBIDDEN"
