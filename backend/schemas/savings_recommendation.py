"""Pydantic schemas for savings recommendations."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from models.enums import SavingsDifficulty
from schemas.base import OrmSchema


class SavingsRecommendationBase(OrmSchema):
    """Shared savings recommendation fields."""

    user_id: UUID | None = None
    statement_id: UUID | None = None
    rank: int | None = None
    target_category: str | None = Field(default=None, max_length=120)
    reason: str | None = None
    possible_monthly_saving: Decimal | None = None
    possible_yearly_saving: Decimal | None = None
    difficulty: SavingsDifficulty | None = None
    action: str | None = None


class SavingsRecommendationCreate(SavingsRecommendationBase):
    """Savings recommendation creation schema."""


class SavingsRecommendationRead(SavingsRecommendationBase):
    """Savings recommendation read schema."""

    id: UUID | None = None
    created_at: datetime | None = None
