"""Pydantic schemas for master categories."""

from models.enums import NeedWantWasteType
from schemas.base import OrmSchema


class CategoryBase(OrmSchema):
    """Shared category fields."""

    name: str | None = None
    need_want_waste_type: NeedWantWasteType | None = None
    is_active: bool | None = None


class CategoryCreate(CategoryBase):
    """Category creation schema."""


class CategoryRead(CategoryBase):
    """Category read schema."""

    id: int | None = None
