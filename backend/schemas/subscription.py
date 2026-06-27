"""Pydantic schemas for subscriptions."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from models.enums import CancellationPriority, SubscriptionFrequency
from schemas.base import OrmSchema


class SubscriptionBase(OrmSchema):
    """Shared subscription fields."""

    user_id: UUID | None = None
    statement_id: UUID | None = None
    merchant: str | None = Field(default=None, max_length=255)
    frequency: SubscriptionFrequency | None = None
    average_amount: Decimal | None = None
    monthly_cost: Decimal | None = None
    yearly_cost: Decimal | None = None
    last_charge_date: date | None = None
    next_predicted_date: date | None = None
    cancellation_priority: CancellationPriority | None = None


class SubscriptionCreate(SubscriptionBase):
    """Subscription creation schema."""


class SubscriptionRead(SubscriptionBase):
    """Subscription read schema."""

    id: UUID | None = None
    created_at: datetime | None = None
