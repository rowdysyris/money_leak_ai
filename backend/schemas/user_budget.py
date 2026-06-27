"""Pydantic schemas for user budgets."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from schemas.base import OrmSchema


class UserBudgetBase(OrmSchema):
    """Shared user budget fields."""

    user_id: UUID | None = None
    total_monthly_limit: Decimal | None = None
    savings_target: Decimal | None = None
    food_budget: Decimal | None = None
    shopping_budget: Decimal | None = None
    subscriptions_budget: Decimal | None = None
    travel_budget: Decimal | None = None
    bills_budget: Decimal | None = None
    custom_budgets: dict[str, float] | None = None


class UserBudgetCreate(UserBudgetBase):
    """User budget creation schema."""


class UserBudgetRead(UserBudgetBase):
    """User budget read schema."""

    id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
