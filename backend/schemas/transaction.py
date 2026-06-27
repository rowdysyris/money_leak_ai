"""Pydantic schemas for cleaned transactions."""

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from models.enums import NeedWantWasteType, TransactionType
from schemas.base import OrmSchema


class TransactionBase(OrmSchema):
    """Shared transaction fields."""

    user_id: UUID | None = None
    statement_id: UUID | None = None
    transaction_date: date | None = None
    transaction_time: time | None = None
    description: str | None = None
    merchant: str | None = Field(default=None, max_length=255)
    amount: Decimal | None = None
    transaction_type: TransactionType | None = None
    category: str | None = Field(default=None, max_length=120)
    category_confidence: float | None = None
    category_source: str | None = Field(default=None, max_length=80)
    is_subscription: bool | None = None
    is_duplicate: bool | None = None
    is_small_spend: bool | None = None
    is_anomaly: bool | None = None
    is_refund: bool | None = None
    is_cashback: bool | None = None
    is_late_night: bool | None = None
    needs_review: bool | None = None
    need_want_waste_type: NeedWantWasteType | None = None


class TransactionCreate(TransactionBase):
    """Transaction creation schema."""


class TransactionRead(TransactionBase):
    """Transaction read schema."""

    id: UUID | None = None
    created_at: datetime | None = None
