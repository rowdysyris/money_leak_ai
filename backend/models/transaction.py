"""Cleaned transaction model for parsed bank statement rows."""

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Numeric, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SAEnum

from database import Base
from models.common import generate_uuid, utc_now
from models.enums import NeedWantWasteType, TransactionType, enum_values


class Transaction(Base):
    """Cleaned transaction row with derived money-leak indicators."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "category_source IS NULL OR category_source IN ('user_rule', 'verified_merchant', 'learned_rule', 'merchant_cache', 'fuzzy_match', 'keyword_rule', 'ml_fallback', 'low_confidence', 'high_value_review')",
            name="ck_transactions_category_source",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    statement_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("statements.id"), nullable=False, index=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    transaction_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    merchant: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(
        SAEnum(
            TransactionType,
            name="transaction_type_enum",
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(120), nullable=False, default="Miscellaneous", index=True)
    category_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    category_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_subscription: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_small_spend: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_refund: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_cashback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_late_night: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    need_want_waste_type: Mapped[NeedWantWasteType] = mapped_column(
        SAEnum(
            NeedWantWasteType,
            name="transaction_need_want_waste_type_enum",
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=NeedWantWasteType.UNKNOWN,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    user = relationship("User", back_populates="transactions")
    statement = relationship("Statement", back_populates="transactions")
