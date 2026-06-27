"""Pydantic schemas for user category rules."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from schemas.base import OrmSchema


class UserCategoryRuleBase(OrmSchema):
    """Shared user category rule fields."""

    user_id: UUID | None = None
    merchant_normalized: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=120)


class UserCategoryRuleCreate(UserCategoryRuleBase):
    """User category rule creation schema."""


class UserCategoryRuleRead(UserCategoryRuleBase):
    """User category rule read schema."""

    id: UUID | None = None
    created_at: datetime | None = None
