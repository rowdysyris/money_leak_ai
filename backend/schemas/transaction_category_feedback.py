"""Pydantic schemas for transaction category feedback."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from schemas.base import OrmSchema


class TransactionCategoryFeedbackBase(OrmSchema):
    """Shared transaction category feedback fields."""

    transaction_id: UUID | None = None
    user_id: UUID | None = None
    merchant_normalized: str | None = Field(default=None, max_length=255)
    previous_category: str | None = Field(default=None, max_length=120)
    corrected_category: str | None = Field(default=None, max_length=120)


class TransactionCategoryFeedbackCreate(TransactionCategoryFeedbackBase):
    """Transaction category feedback creation schema."""


class TransactionCategoryFeedbackRead(TransactionCategoryFeedbackBase):
    """Transaction category feedback read schema."""

    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
