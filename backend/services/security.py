"""Security and hardening helpers for MoneyLeak AI."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

PDF_MAGIC = b"%PDF"
XLSX_MAGIC = b"PK\x03\x04"
XLS_LEGACY_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
MAX_FILENAME_LENGTH = 120


def sanitize_filename(filename: str | None) -> str:
    """Return a safe filename with path traversal, control chars, and script chars removed."""
    raw_name = Path(str(filename or "statement").replace("\\", "/")).name
    raw_name = raw_name.replace("\x00", "")
    safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", raw_name).strip(" ._")
    if not safe_name:
        safe_name = "statement"
    if len(safe_name) > MAX_FILENAME_LENGTH:
        stem = Path(safe_name).stem[:80]
        suffix = Path(safe_name).suffix[:15]
        safe_name = f"{stem}{suffix}"
    return safe_name


def has_path_traversal(filename: str | None) -> bool:
    """Return True if a filename attempts path traversal or absolute paths."""
    raw_name = str(filename or "")
    normalized = raw_name.replace("\\", "/")
    if "../" in normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        return True
    return False


def extension_for(filename: str | None) -> str:
    """Return the lowercase extension for a filename."""
    return Path(str(filename or "")).suffix.lower()


def is_probably_binary(content: bytes) -> bool:
    """Return True when byte content looks binary instead of a text CSV."""
    if not content:
        return False
    sample = content[:2048]
    if b"\x00" in sample:
        return True
    text_like = set(range(32, 127)) | {9, 10, 13, 8, 12}
    non_text = sum(1 for byte in sample if byte not in text_like and byte < 128)
    return (non_text / max(1, len(sample))) > 0.30


def validate_magic_bytes(file_bytes: bytes, filename: str | None) -> dict[str, Any] | None:
    """Validate file bytes against extension-level security expectations."""
    extension = extension_for(filename)
    sample = file_bytes[:8]
    if sample.startswith(PDF_MAGIC):
        return {
            "code": "PDF_NOT_SUPPORTED" if extension == ".pdf" else "FILE_CONTENT_MISMATCH",
            "message": "PDF support is not available yet. Please export your bank statement as CSV or Excel.",
            "details": {"detected_type": "pdf"},
        }
    if extension == ".csv":
        if sample.startswith(XLSX_MAGIC) or sample.startswith(XLS_LEGACY_MAGIC) or is_probably_binary(file_bytes):
            return {
                "code": "FILE_CONTENT_MISMATCH",
                "message": "The uploaded file content does not match a CSV file.",
                "details": {"expected_type": "csv"},
            }
    if extension == ".xlsx" and not sample.startswith(XLSX_MAGIC):
        return {
            "code": "FILE_CONTENT_MISMATCH",
            "message": "The uploaded file content does not match an XLSX workbook.",
            "details": {"expected_type": "xlsx"},
        }
    if extension == ".xls" and not (sample.startswith(XLS_LEGACY_MAGIC) or sample.startswith(XLSX_MAGIC)):
        return {
            "code": "FILE_CONTENT_MISMATCH",
            "message": "The uploaded file content does not match an Excel workbook.",
            "details": {"expected_type": "xls"},
        }
    return None


def get_upload_file_size(upload_file: Any) -> int | None:
    """Return upload size without permanently consuming the stream when the file object is seekable."""
    file_object = getattr(upload_file, "file", None)
    if file_object is None:
        size = getattr(upload_file, "size", None)
        return int(size) if isinstance(size, int) else None
    try:
        current_position = file_object.tell()
        file_object.seek(0, os.SEEK_END)
        size = int(file_object.tell())
        file_object.seek(current_position, os.SEEK_SET)
        return size
    except (AttributeError, OSError, ValueError):
        size = getattr(upload_file, "size", None)
        return int(size) if isinstance(size, int) else None


def verify_statement_ownership(db: Session, user_id: UUID, statement_id: UUID | None) -> object | None:
    """Return an owned statement or raise 403 when the statement belongs to another user."""
    if statement_id is None:
        return None
    from models import Statement

    statement = db.query(Statement).filter(Statement.id == statement_id).first()
    if statement is None:
        return None
    if str(statement.user_id) != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "You do not have access to this statement.", "details": {}},
        )
    return statement
