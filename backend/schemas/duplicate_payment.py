"""Pydantic schemas for duplicate payments."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from schemas.base import OrmSchema


class DuplicatePaymentBase(OrmSchema):
    """Shared duplicate payment fields."""

    user_id: UUID | None = None
    statement_id: UUID | None = None
    transaction_id_1: UUID | None = None
    transaction_id_2: UUID | None = None
    merchant: str | None = Field(default=None, max_length=255)
    amount: Decimal | None = None
    duplicate_date: date | None = None
    confidence_score: float | None = None


class DuplicatePaymentCreate(DuplicatePaymentBase):
    """Duplicate payment creation schema."""


class DuplicatePaymentRead(DuplicatePaymentBase):
    """Duplicate payment read schema."""

    id: UUID | None = None
    created_at: datetime | None = None
