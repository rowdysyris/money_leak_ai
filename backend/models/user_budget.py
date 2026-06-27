"""User budget model."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.common import generate_uuid, utc_now


class UserBudget(Base):
    """Single monthly budget configuration for a user."""

    __tablename__ = "user_budgets"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    total_monthly_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    savings_target: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    food_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    shopping_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    subscriptions_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    travel_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    bills_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    custom_budgets: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
