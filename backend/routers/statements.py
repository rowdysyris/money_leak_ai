"""Statement upload API routes."""

from __future__ import annotations

import logging
import json
from datetime import date, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from dependencies import get_current_user
from models import Statement, Transaction, User
from models.enums import ProcessingStatus
from schemas.common import error_response, success_response
from services.categorizer import categorize_statement
from services.security import get_upload_file_size, has_path_traversal, sanitize_filename, verify_statement_ownership
from services.bank_presets import supported_bank_presets
from services.statement_parser import get_file_extension, parse_statement
from services.transaction_cleaner import clean_transactions

logger = logging.getLogger("moneyleak-ai.statements")
router = APIRouter(prefix="/api/statements", tags=["statements"])

ERROR_STATUS_CODES = {
    "PDF_NOT_SUPPORTED": status.HTTP_400_BAD_REQUEST,
    "INVALID_FILE_TYPE": status.HTTP_400_BAD_REQUEST,
    "EMPTY_FILE": status.HTTP_400_BAD_REQUEST,
    "EMPTY_TABLE": status.HTTP_400_BAD_REQUEST,
    "FILE_TOO_LARGE": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    "ENCODING_ERROR": status.HTTP_400_BAD_REQUEST,
    "CSV_PARSE_ERROR": status.HTTP_400_BAD_REQUEST,
    "EXCEL_PARSE_ERROR": status.HTTP_400_BAD_REQUEST,
    "MISSING_DATE_COLUMN": status.HTTP_400_BAD_REQUEST,
    "MISSING_DESCRIPTION_COLUMN": status.HTTP_400_BAD_REQUEST,
    "MISSING_AMOUNT_COLUMN": status.HTTP_400_BAD_REQUEST,
    "STATEMENT_PARSE_ERROR": status.HTTP_400_BAD_REQUEST,
    "FILE_CONTENT_MISMATCH": status.HTTP_400_BAD_REQUEST,
    "INVALID_FILENAME": status.HTTP_400_BAD_REQUEST,
}


def parser_error_status(error_payload: dict[str, Any]) -> int:
    """Return an HTTP status code for a parser error payload."""
    error = error_payload.get("error", {}) if isinstance(error_payload, dict) else {}
    code = str(error.get("code", "STATEMENT_PARSE_ERROR")) if isinstance(error, dict) else "STATEMENT_PARSE_ERROR"
    return ERROR_STATUS_CODES.get(code, status.HTTP_400_BAD_REQUEST)


def parse_iso_date(value: str | None) -> date | None:
    """Convert an ISO date string into a date object for persistence."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None



def parse_iso_time(value: str | None) -> time | None:
    """Convert an ISO time string into a time object for persistence."""
    if value is None:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None

def calculate_statement_period(transactions: list[dict[str, Any]]) -> dict[str, str | None]:
    """Calculate the statement date range from cleaned transactions."""
    parsed_dates = [parse_iso_date(str(transaction.get("transaction_date"))) for transaction in transactions]
    valid_dates = [transaction_date for transaction_date in parsed_dates if transaction_date is not None]
    if not valid_dates:
        return {"start": None, "end": None}
    return {"start": min(valid_dates).isoformat(), "end": max(valid_dates).isoformat()}


def build_statement_record(
    user_id: UUID,
    filename: str,
    file_format: str,
    total_rows: int,
    processed_rows: int,
    skipped_rows: int,
    warnings: list[str],
    statement_period: dict[str, str | None],
) -> Statement:
    """Build a Statement ORM object from upload processing metadata."""
    return Statement(
        user_id=user_id,
        original_filename=filename,
        file_format=file_format,
        total_rows=total_rows,
        processed_rows=processed_rows,
        skipped_rows=skipped_rows,
        warnings=warnings,
        processing_status=ProcessingStatus.PROCESSING,
        statement_period_start=parse_iso_date(statement_period.get("start")),
        statement_period_end=parse_iso_date(statement_period.get("end")),
    )


def build_transaction_record(user_id: UUID, statement_id: UUID, transaction: dict[str, Any]) -> Transaction:
    """Build a Transaction ORM object from a cleaned transaction dictionary."""
    transaction_date = parse_iso_date(str(transaction.get("transaction_date")))
    if transaction_date is None:
        raise ValueError("transaction_date is required for transaction persistence")
    return Transaction(
        user_id=user_id,
        statement_id=statement_id,
        transaction_date=transaction_date,
        transaction_time=parse_iso_time(transaction.get("transaction_time")),
        description=transaction.get("description"),
        merchant=transaction.get("merchant"),
        amount=Decimal(str(transaction.get("amount", "0"))),
        transaction_type=str(transaction.get("transaction_type")),
        category=str(transaction.get("category") or "Miscellaneous"),
        category_confidence=float(transaction.get("category_confidence") or 0.0),
        category_source=transaction.get("category_source"),
        is_subscription=bool(transaction.get("is_subscription", False)),
        is_duplicate=bool(transaction.get("is_duplicate", False)),
        is_small_spend=bool(transaction.get("is_small_spend", False)),
        is_anomaly=bool(transaction.get("is_anomaly", False)),
        is_refund=bool(transaction.get("is_refund", False)),
        is_cashback=bool(transaction.get("is_cashback", False)),
        is_late_night=bool(transaction.get("is_late_night", False)),
        needs_review=bool(transaction.get("needs_review", False)),
        need_want_waste_type=str(transaction.get("need_want_waste_type") or "unknown"),
    )


def serialize_transaction_preview(transaction: dict[str, Any]) -> dict[str, Any]:
    """Serialize a cleaned transaction for upload preview responses."""
    return {
        "transaction_date": transaction.get("transaction_date"),
        "transaction_time": transaction.get("transaction_time"),
        "description": transaction.get("description"),
        "merchant": transaction.get("merchant"),
        "amount": transaction.get("amount"),
        "transaction_type": transaction.get("transaction_type"),
        "category": transaction.get("category"),
        "is_duplicate": transaction.get("is_duplicate"),
        "is_small_spend": transaction.get("is_small_spend"),
        "is_refund": transaction.get("is_refund"),
        "is_cashback": transaction.get("is_cashback"),
        "is_late_night": transaction.get("is_late_night"),
        "needs_review": transaction.get("needs_review"),
    }


def serialize_statement(statement: Statement) -> dict[str, Any]:
    """Serialize statement processing metadata without exposing stored file paths."""
    return {
        "statement_id": str(statement.id),
        "original_filename": statement.original_filename,
        "file_format": statement.file_format,
        "total_rows": int(statement.total_rows or 0),
        "processed_rows": int(statement.processed_rows or 0),
        "skipped_rows": int(statement.skipped_rows or 0),
        "warnings": list(statement.warnings or []),
        "processing_status": getattr(statement.processing_status, "value", str(statement.processing_status)),
        "statement_period_start": statement.statement_period_start.isoformat() if statement.statement_period_start else None,
        "statement_period_end": statement.statement_period_end.isoformat() if statement.statement_period_end else None,
        "created_at": statement.created_at.isoformat() if statement.created_at else None,
    }


def categorize_statement_background(statement_id: UUID, user_id: UUID) -> dict[str, Any]:
    """Run statement categorization in a background-owned database session."""
    db = SessionLocal()
    try:
        return categorize_statement(str(statement_id), str(user_id), db)
    except (SQLAlchemyError, ValueError, TypeError) as exc:
        db.rollback()
        logger.warning("Background categorization failed: %s", exc.__class__.__name__)
        return {"statement_id": str(statement_id), "updated_count": 0, "error_type": exc.__class__.__name__}
    finally:
        db.close()


def duplicate_key_for_clean_transaction(transaction: dict[str, Any]) -> tuple[str, str, str, str]:
    """Return a stable key used to remove duplicates across multiple uploaded files."""
    return (
        str(transaction.get("transaction_date") or ""),
        str(transaction.get("description") or "").strip().lower(),
        str(transaction.get("amount") or "0"),
        str(transaction.get("transaction_type") or ""),
    )


async def parse_uploaded_file_to_transactions(file: UploadFile, bank_preset: str | None = None) -> dict[str, Any]:
    """Read, parse, and clean one uploaded statement file without persisting it."""
    original_filename = file.filename or "statement"
    filename = sanitize_filename(original_filename)
    if has_path_traversal(original_filename):
        return {
            "success": False,
            "filename": filename,
            "error": {"code": "INVALID_FILENAME", "message": "The uploaded filename is not allowed.", "details": {"filename": filename}},
            "status_code": status.HTTP_400_BAD_REQUEST,
        }
    size_bytes = get_upload_file_size(file)
    if size_bytes is not None:
        from config import get_settings
        max_bytes = int(get_settings().MAX_UPLOAD_SIZE_MB) * 1024 * 1024
        if size_bytes > max_bytes:
            return {
                "success": False,
                "filename": filename,
                "error": {"code": "FILE_TOO_LARGE", "message": "The uploaded file exceeds the configured size limit.", "details": {"size_bytes": size_bytes, "max_size_bytes": max_bytes}},
                "status_code": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            }
    try:
        file_bytes = await file.read()
    except OSError as exc:
        return {
            "success": False,
            "filename": filename,
            "error": {"code": "FILE_READ_ERROR", "message": "The uploaded file could not be read.", "details": {"error_type": exc.__class__.__name__}},
            "status_code": status.HTTP_400_BAD_REQUEST,
        }
    parse_result = parse_statement(file_bytes, filename, bank_preset=bank_preset)
    if not parse_result.get("success", False):
        error = parse_result.get("error", {}) if isinstance(parse_result.get("error", {}), dict) else {}
        return {
            "success": False,
            "filename": filename,
            "error": error,
            "warnings": parse_result.get("warnings", []),
            "status_code": parser_error_status(parse_result),
        }
    parse_data = parse_result.get("data", {})
    clean_result = clean_transactions(parse_data.get("dataframe"), parse_data.get("column_map", {}))
    return {
        "success": True,
        "filename": str(parse_data.get("safe_filename") or filename),
        "file_format": str(parse_data.get("file_format") or get_file_extension(filename).lstrip(".")),
        "total_rows": int(parse_data.get("total_rows", 0)),
        "processed_rows": len(clean_result.get("transactions", [])),
        "skipped_rows": len(clean_result.get("skipped_rows", [])),
        "warnings": list(parse_result.get("warnings", [])) + list(clean_result.get("warnings", [])),
        "metadata": parse_data.get("metadata", {}),
        "transactions": clean_result.get("transactions", []),
    }


@router.get("/bank-presets", response_model=None)
def list_bank_presets(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """List supported statement parser presets for the upload UI."""
    return success_response({"presets": supported_bank_presets()}, [])


@router.get("", response_model=None)
def list_statements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """List statement uploads owned by the authenticated user."""
    try:
        statements = (
            db.query(Statement)
            .filter(Statement.user_id == current_user.id)
            .order_by(Statement.created_at.desc())
            .all()
        )
        return success_response({"statements": [serialize_statement(statement) for statement in statements]}, [])
    except SQLAlchemyError as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("DATABASE_ERROR", "Database operation failed.", {"error_type": exc.__class__.__name__}),
        )


@router.get("/{statement_id}", response_model=None)
def statement_status(
    statement_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Return processing metadata for one owned statement."""
    try:
        statement = verify_statement_ownership(db, current_user.id, statement_id)
        if statement is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content=error_response("STATEMENT_NOT_FOUND", "Statement was not found.", {}),
            )
        return success_response({"statement": serialize_statement(statement)}, [])
    except SQLAlchemyError as exc:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("DATABASE_ERROR", "Database operation failed.", {"error_type": exc.__class__.__name__}),
        )


@router.post("/upload", status_code=status.HTTP_201_CREATED, response_model=None)
async def upload_statement(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    bank_preset: str | None = Form(default=None),
    column_mapping: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Upload, parse, clean, persist, and preview a CSV or Excel bank statement."""
    original_filename = file.filename or "statement"
    filename = sanitize_filename(original_filename)
    if has_path_traversal(original_filename):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response("INVALID_FILENAME", "The uploaded filename is not allowed.", {"filename": filename}),
        )
    size_bytes = get_upload_file_size(file)
    max_bytes = 10 * 1024 * 1024
    if size_bytes is not None:
        from config import get_settings
        max_bytes = int(get_settings().MAX_UPLOAD_SIZE_MB) * 1024 * 1024
        if size_bytes > max_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content=error_response("FILE_TOO_LARGE", "The uploaded file exceeds the configured size limit.", {"size_bytes": size_bytes, "max_size_bytes": max_bytes}),
            )
    try:
        file_bytes = await file.read()
    except OSError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response("FILE_READ_ERROR", "The uploaded file could not be read.", {"error_type": exc.__class__.__name__}),
        )

    manual_column_map = None
    if column_mapping:
        try:
            manual_column_map = json.loads(column_mapping)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response("INVALID_COLUMN_MAPPING", "Column mapping must be valid JSON.", {}),
            )
        if not isinstance(manual_column_map, dict):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=error_response("INVALID_COLUMN_MAPPING", "Column mapping must be an object.", {}),
            )

    parse_result = parse_statement(file_bytes, filename, bank_preset=bank_preset, manual_column_map=manual_column_map)
    if not parse_result.get("success", False):
        return JSONResponse(status_code=parser_error_status(parse_result), content=parse_result)

    parse_data = parse_result.get("data", {})
    parser_metadata = parse_data.get("metadata", {}) if isinstance(parse_data.get("metadata", {}), dict) else {}
    if parser_metadata.get("manual_mapping_required"):
        mapping_warnings = list(parse_result.get("warnings", [])) + ["Confirm the detected columns before processing this statement."]
        return success_response(
            {
                "statement_id": None,
                "total_rows": int(parse_data.get("total_rows", 0)),
                "processed_rows": 0,
                "skipped_rows": 0,
                "warnings": mapping_warnings,
                "preview": [],
                "statement_period": {"start": None, "end": None},
                "parser_metadata": parser_metadata,
                "requires_column_mapping": True,
            },
            mapping_warnings,
        )
    dataframe = parse_data.get("dataframe")
    column_map = parse_data.get("column_map", {})
    clean_result = clean_transactions(dataframe, column_map)
    cleaned_transactions = clean_result.get("transactions", [])
    skipped_rows = clean_result.get("skipped_rows", [])
    combined_warnings = list(parse_result.get("warnings", [])) + list(clean_result.get("warnings", []))
    statement_period = calculate_statement_period(cleaned_transactions)

    statement = build_statement_record(
        user_id=current_user.id,
        filename=str(parse_data.get("safe_filename") or filename),
        file_format=str(parse_data.get("file_format") or get_file_extension(filename).lstrip(".")),
        total_rows=int(parse_data.get("total_rows", 0)),
        processed_rows=len(cleaned_transactions),
        skipped_rows=len(skipped_rows),
        warnings=combined_warnings,
        statement_period=statement_period,
    )

    try:
        db.add(statement)
        db.flush()
        transaction_records = [build_transaction_record(current_user.id, statement.id, transaction) for transaction in cleaned_transactions]
        if transaction_records:
            db.add_all(transaction_records)
        statement.processing_status = ProcessingStatus.COMPLETED
        db.commit()
        db.refresh(statement)
    except (SQLAlchemyError, ValueError) as exc:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("STATEMENT_SAVE_ERROR", "The statement could not be saved.", {"error_type": exc.__class__.__name__}),
        )

    background_tasks.add_task(categorize_statement_background, statement.id, current_user.id)
    response_data = {
        "statement_id": str(statement.id),
        "total_rows": statement.total_rows,
        "processed_rows": statement.processed_rows,
        "skipped_rows": statement.skipped_rows,
        "warnings": combined_warnings,
        "preview": [serialize_transaction_preview(transaction) for transaction in cleaned_transactions[:20]],
        "statement_period": statement_period,
        "parser_metadata": parse_data.get("metadata", {}),
    }
    return success_response(response_data, combined_warnings)


@router.post("/upload-multiple", status_code=status.HTTP_201_CREATED, response_model=None)
async def upload_multiple_statements(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    bank_preset: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any] | JSONResponse:
    """Upload multiple CSV or Excel statements, merge rows, and create one combined analysis statement."""
    if not files:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response("NO_FILES_UPLOADED", "Upload at least one statement file.", {}),
        )
    file_results: list[dict[str, Any]] = []
    combined_transactions: list[dict[str, Any]] = []
    combined_warnings: list[str] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    duplicate_rows_removed = 0
    total_rows = 0
    total_skipped_rows = 0
    file_format = "mixed"

    for file in files:
        result = await parse_uploaded_file_to_transactions(file, bank_preset=bank_preset)
        file_results.append({key: value for key, value in result.items() if key != "transactions"})
        if not result.get("success", False):
            combined_warnings.append(f"{result.get('filename', 'file')}: {result.get('error', {}).get('message', 'Could not be processed')}.")
            continue
        total_rows += int(result.get("total_rows", 0))
        total_skipped_rows += int(result.get("skipped_rows", 0))
        combined_warnings.extend([f"{result.get('filename')}: {warning}" for warning in result.get("warnings", [])])
        file_format = str(result.get("file_format") or file_format) if file_format == "mixed" else "mixed"
        for transaction in result.get("transactions", []):
            key = duplicate_key_for_clean_transaction(transaction)
            if key in seen_keys:
                duplicate_rows_removed += 1
                continue
            seen_keys.add(key)
            combined_transactions.append(transaction)

    if not combined_transactions:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response("NO_VALID_TRANSACTIONS", "No valid transactions were found across the uploaded files.", {"files": file_results}),
        )

    combined_warnings.append(f"Removed {duplicate_rows_removed} duplicate row(s) across uploaded files.") if duplicate_rows_removed else None
    statement_period = calculate_statement_period(combined_transactions)
    statement = build_statement_record(
        user_id=current_user.id,
        filename=f"combined_{len(files)}_statements",
        file_format=file_format,
        total_rows=total_rows,
        processed_rows=len(combined_transactions),
        skipped_rows=total_skipped_rows + duplicate_rows_removed,
        warnings=combined_warnings,
        statement_period=statement_period,
    )
    try:
        db.add(statement)
        db.flush()
        transaction_records = [build_transaction_record(current_user.id, statement.id, transaction) for transaction in combined_transactions]
        if transaction_records:
            db.add_all(transaction_records)
        statement.processing_status = ProcessingStatus.COMPLETED
        db.commit()
        db.refresh(statement)
    except (SQLAlchemyError, ValueError) as exc:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response("STATEMENT_SAVE_ERROR", "The combined statement could not be saved.", {"error_type": exc.__class__.__name__}),
        )

    background_tasks.add_task(categorize_statement_background, statement.id, current_user.id)
    response_data = {
        "statement_id": str(statement.id),
        "files": file_results,
        "file_count": len(files),
        "processed_files": sum(1 for result in file_results if result.get("success")),
        "failed_files": sum(1 for result in file_results if not result.get("success")),
        "total_rows": total_rows,
        "processed_rows": statement.processed_rows,
        "skipped_rows": statement.skipped_rows,
        "duplicate_rows_removed": duplicate_rows_removed,
        "warnings": combined_warnings,
        "preview": [serialize_transaction_preview(transaction) for transaction in combined_transactions[:20]],
        "statement_period": statement_period,
    }
    return success_response(response_data, combined_warnings)
