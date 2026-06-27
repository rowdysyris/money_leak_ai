"""Downloadable report API routes for MoneyLeak AI."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Statement, Transaction, User, UserBudget
from schemas.common import error_response
from services.report_generator import build_csv_export, build_excel_report, build_pdf_report
from services.security import verify_statement_ownership

router = APIRouter(prefix="/api/reports", tags=["Reports"])


def fetch_user_budget(db: Session, user_id: UUID) -> UserBudget | None:
    """Fetch the user's budget when available."""
    return db.query(UserBudget).filter(UserBudget.user_id == user_id).first()


def fetch_report_statement(db: Session, user_id: UUID, statement_id: UUID | None) -> Statement | None:
    """Fetch a requested statement or the latest statement for a user, enforcing ownership."""
    if statement_id is not None:
        statement = verify_statement_ownership(db, user_id, statement_id)
        if statement is None:
            return None
        return statement
    return db.query(Statement).filter(Statement.user_id == user_id).order_by(Statement.created_at.desc()).first()


def fetch_report_transactions(db: Session, user_id: UUID, statement_id: UUID | None) -> tuple[Statement | None, list[Transaction]]:
    """Fetch report statement metadata and transactions for a user."""
    statement = fetch_report_statement(db, user_id, statement_id)
    if statement is None:
        return None, []
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.statement_id == statement.id)
        .order_by(Transaction.transaction_date.asc(), Transaction.created_at.asc())
        .all()
    )
    return statement, transactions


def database_error_response(exc: SQLAlchemyError) -> JSONResponse:
    """Return a structured database error response without exposing stack traces."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response("DATABASE_ERROR", "Database operation failed.", {"error_type": exc.__class__.__name__}),
    )


def report_error_response(exc: Exception) -> JSONResponse:
    """Return a structured report generation error without exposing internals."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response("REPORT_GENERATION_FAILED", "Report could not be generated. Please try again.", {"error_type": exc.__class__.__name__}),
    )


def download_response(content: bytes, media_type: str, filename: str) -> Response:
    """Build a binary download response with a content-disposition header."""
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename={filename}"})


def report_inputs(db: Session, current_user: User, statement_id: UUID | None) -> tuple[Statement | None, list[Transaction], UserBudget | None]:
    """Load all data required to generate a report."""
    statement, transactions = fetch_report_transactions(db, current_user.id, statement_id)
    budget = fetch_user_budget(db, current_user.id)
    return statement, transactions, budget


@router.get("/download/pdf", response_model=None)
def download_pdf_report(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response | JSONResponse:
    """Download the monthly MoneyLeak AI PDF report."""
    try:
        statement, transactions, budget = report_inputs(db, current_user, statement_id)
        pdf_bytes = build_pdf_report(transactions, user=current_user, statement=statement, budget=budget)
        return download_response(pdf_bytes, "application/pdf", "moneyleak-monthly-report.pdf")
    except SQLAlchemyError as exc:
        return database_error_response(exc)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return report_error_response(exc)


@router.get("/download/csv", response_model=None)
def download_csv_report(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response | JSONResponse:
    """Download transactions as a CSV file."""
    try:
        statement, transactions, budget = report_inputs(db, current_user, statement_id)
        csv_bytes = build_csv_export(transactions)
        return download_response(csv_bytes, "text/csv", "moneyleak-transactions.csv")
    except SQLAlchemyError as exc:
        return database_error_response(exc)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return report_error_response(exc)


@router.get("/download/excel", response_model=None)
def download_excel_report(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response | JSONResponse:
    """Download the full multi-sheet Excel report."""
    try:
        statement, transactions, budget = report_inputs(db, current_user, statement_id)
        excel_bytes = build_excel_report(transactions, user=current_user, statement=statement, budget=budget)
        return download_response(excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "moneyleak-full-report.xlsx")
    except SQLAlchemyError as exc:
        return database_error_response(exc)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return report_error_response(exc)


@router.get("/pdf", response_model=None)
def legacy_pdf_report(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response | JSONResponse:
    """Preserve the frontend-compatible PDF endpoint alias."""
    return download_pdf_report(statement_id=statement_id, current_user=current_user, db=db)


@router.get("/transactions.csv", response_model=None)
def legacy_csv_report(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response | JSONResponse:
    """Preserve the frontend-compatible CSV endpoint alias."""
    return download_csv_report(statement_id=statement_id, current_user=current_user, db=db)


@router.get("/excel", response_model=None)
def legacy_excel_report(
    statement_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response | JSONResponse:
    """Preserve the frontend-compatible Excel endpoint alias."""
    return download_excel_report(statement_id=statement_id, current_user=current_user, db=db)
