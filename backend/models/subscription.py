"""Detected recurring payment model."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Enum as SAEnum

from database import Base
from models.common import generate_uuid, utc_now
from models.enums import CancellationPriority, SubscriptionFrequency, enum_values


class Subscription(Base):
    """Detected recurring merchant payment with estimated recurring cost."""

    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    statement_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("statements.id"), nullable=False, index=True)
    merchant: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[SubscriptionFrequency] = mapped_column(
        SAEnum(
            SubscriptionFrequency,
            name="subscription_frequency_enum",
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    average_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monthly_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    yearly_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    last_charge_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_predicted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancellation_priority: Mapped[CancellationPriority] = mapped_column(
        SAEnum(
            CancellationPriority,
            name="cancellation_priority_enum",
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
