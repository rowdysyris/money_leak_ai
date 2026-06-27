"""Savings recommendation model."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Enum as SAEnum

from database import Base
from models.common import generate_uuid, utc_now
from models.enums import SavingsDifficulty, enum_values


class SavingsRecommendation(Base):
    """Ranked recommendation that estimates possible savings from behavior changes."""

    __tablename__ = "savings_recommendations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    statement_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("statements.id"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    target_category: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    possible_monthly_saving: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    possible_yearly_saving: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    difficulty: Mapped[SavingsDifficulty] = mapped_column(
        SAEnum(
            SavingsDifficulty,
            name="savings_difficulty_enum",
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
