"""Merchant discovery cache model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Enum as SAEnum

from database import Base
from models.common import generate_uuid, utc_now
from models.enums import MerchantSource, enum_values


class MerchantDiscoveryCache(Base):
    """Cached merchant enrichment result from AI, user corrections, or learned rules."""

    __tablename__ = "merchant_discovery_cache"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    raw_merchant_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_merchant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str] = mapped_column(String(120), nullable=False, default="India")
    discovered_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[MerchantSource] = mapped_column(
        SAEnum(
            MerchantSource,
            name="merchant_source_enum",
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
