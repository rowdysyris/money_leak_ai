"""Dashboard analytics API routes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Statement, Transaction, User, UserBudget
from schemas.common import error_response
from services.analytics_utils import NO_STATEMENT_WARNING
from services.security import verify_statement_ownership
from services.dashboard_service import get_category_breakdown, get_daily_spend, get_needs_wants_waste, get_summary, get_top_merchants

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def success_payload(data: Any, warnings: list[str] | None = None) -> dict[str, Any]:
    """Build an API success envelope that supports null data."""
    return {"success": True, "data": data, "warnings": warnings or []}


def no_statement_payload() -> dict[str, Any]:
    """Return the standard no-statement analytics response."""
    return success_payload(None, [NO_STATEMENT_WARNING])


def fetch_user_budget(db: Session, user_id: UUID) -> UserBudget | None:
    """Fetch a user's budget if one exists."""
    return db.query(UserBudget).filter(UserBudget.user_id == user_id).first()


def fetch_matching_statement(db: Session, user_id: UUID, statement_id: UUID | None) -> Statement | None:
    """Fetch the requested statement or the most recent statement for a user, enforcing ownership."""
    if statement_id is not None:
        statement = verify_statement_ownership(db, user_id, statement_id)
        if statement is None:
            return None
        return statement
    return db.query(Statement).filter(Statement.user_id == user_id).order_by(Statement.created_at.desc()).first()


def fetch_transactions_for_statement(db: Session, user_id: UUID, statement_id: UUID | None) -> tuple[Statement | None, list[Transaction]]:
    """Fetch a statement and its transactions for dashboard analytics."""
    statement = fetch_matching_statement(db, user_id, statement_id)
    if statement is None:
        return None, []
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.statement_id == statement.id)
        .order_by(Transaction.transaction_date.asc(), Transaction.created_at.asc())
        .all()
    )
    return statement, transactions


def service_to_response(result: dict[str, Any]) -> dict[str, Any]:
    """Convert a service payload into an API success envelope."""
    return success_payload(result.get("data"), result.get("warnings", []))


def database_error_response(exc: SQLAlchemyError) -> JSONResponse:
    """Return a structured database error response without stack traces."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response("DATABASE_ERROR", "Database operation failed.", {"error_type": exc.__class__.__name__}),
    )


@router.get("/summary", response_model=None)
def dashboard_summary(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return dashboard summary metrics for the authenticated user."""
    try:
        statement, transactions = fetch_transactions_for_statement(db, current_user.id, statement_id)
        if statement is None:
            return no_statement_payload()
        return service_to_response(get_summary(transactions, fetch_user_budget(db, current_user.id)))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/category-breakdown", response_model=None)
def dashboard_category_breakdown(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return category breakdown metrics for the authenticated user."""
    try:
        statement, transactions = fetch_transactions_for_statement(db, current_user.id, statement_id)
        if statement is None:
            return no_statement_payload()
        return service_to_response(get_category_breakdown(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/top-merchants", response_model=None)
def dashboard_top_merchants(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return top merchant spend metrics for the authenticated user."""
    try:
        statement, transactions = fetch_transactions_for_statement(db, current_user.id, statement_id)
        if statement is None:
            return no_statement_payload()
        return service_to_response(get_top_merchants(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/daily-spend", response_model=None)
def dashboard_daily_spend(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return daily spend line-chart data for the authenticated user."""
    try:
        statement, transactions = fetch_transactions_for_statement(db, current_user.id, statement_id)
        if statement is None:
            return no_statement_payload()
        return service_to_response(get_daily_spend(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)


@router.get("/needs-wants-waste", response_model=None)
def dashboard_needs_wants_waste(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return need/want/waste/savings composition for the authenticated user."""
    try:
        statement, transactions = fetch_transactions_for_statement(db, current_user.id, statement_id)
        if statement is None:
            return no_statement_payload()
        return service_to_response(get_needs_wants_waste(transactions))
    except SQLAlchemyError as exc:
        return database_error_response(exc)
