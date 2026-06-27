"""Pydantic schemas for users."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from models.enums import ProfileType
from schemas.base import OrmSchema


class UserBase(OrmSchema):
    """Shared user fields."""

    email: str | None = Field(default=None, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    profile_type: ProfileType | None = None
    city: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None


class UserCreate(UserBase):
    """User creation schema without password hash exposure."""



class UserRead(UserBase):
    """User read schema."""

    id: UUID | None = None
    created_at: datetime | None = None
