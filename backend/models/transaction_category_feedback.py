"""Transaction category feedback model for user corrections and learned rules."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base
from models.common import generate_uuid, utc_now


class TransactionCategoryFeedback(Base):
    """A persisted user correction for a transaction merchant category."""

    __tablename__ = "transaction_category_feedback"
    __table_args__ = (UniqueConstraint("transaction_id", name="uq_transaction_category_feedback_transaction_id"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    transaction_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    merchant_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    previous_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    corrected_category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
