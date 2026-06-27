"""Pydantic schemas for learned merchant rules."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from schemas.base import OrmSchema


class LearnedMerchantRuleBase(OrmSchema):
    """Shared learned merchant rule fields."""

    merchant_normalized: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    correction_count: int | None = None
    confidence: float | None = None


class LearnedMerchantRuleCreate(LearnedMerchantRuleBase):
    """Learned merchant rule creation schema."""


class LearnedMerchantRuleRead(LearnedMerchantRuleBase):
    """Learned merchant rule read schema."""

    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
