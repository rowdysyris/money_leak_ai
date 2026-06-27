"""Pydantic schemas for merchant discovery cache."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from models.enums import MerchantSource
from schemas.base import OrmSchema


class MerchantDiscoveryCacheBase(OrmSchema):
    """Shared merchant discovery cache fields."""

    raw_merchant_name: str | None = Field(default=None, max_length=255)
    normalized_merchant_name: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    discovered_name: str | None = Field(default=None, max_length=255)
    business_type: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    source: MerchantSource | None = None
    confidence_score: float | None = None
    use_count: int | None = None
    last_verified_at: datetime | None = None


class MerchantDiscoveryCacheCreate(MerchantDiscoveryCacheBase):
    """Merchant discovery cache creation schema."""


class MerchantDiscoveryCacheRead(MerchantDiscoveryCacheBase):
    """Merchant discovery cache read schema."""

    id: UUID | None = None
    created_at: datetime | None = None
