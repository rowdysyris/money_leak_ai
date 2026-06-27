"""Pydantic schemas for uploaded statements."""

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from models.enums import ProcessingStatus
from schemas.base import OrmSchema


class StatementBase(OrmSchema):
    """Shared statement fields."""

    user_id: UUID | None = None
    original_filename: str | None = Field(default=None, max_length=255)
    file_format: str | None = Field(default=None, max_length=10)
    total_rows: int | None = None
    processed_rows: int | None = None
    skipped_rows: int | None = None
    warnings: list[str] | None = None
    processing_status: ProcessingStatus | None = None
    processing_error: str | None = None
    statement_period_start: date | None = None
    statement_period_end: date | None = None


class StatementCreate(StatementBase):
    """Statement creation schema."""


class StatementRead(StatementBase):
    """Statement read schema."""

    id: UUID | None = None
    created_at: datetime | None = None
