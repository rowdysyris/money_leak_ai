"""Authentication request and response schemas."""

import re
from typing import ClassVar

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_PROFILE_TYPES = {"Student", "Fresher", "Working Professional", "Freelancer"}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RegisterRequest(BaseModel):
    """Registration payload accepted by the auth API."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    profile_type: str = Field(min_length=1, max_length=50)
    city: str | None = Field(default=None, max_length=120)

    allowed_profile_types: ClassVar[set[str]] = ALLOWED_PROFILE_TYPES

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Validate and normalize an email address."""
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("Invalid email format")
        return normalized

    @field_validator("profile_type")
    @classmethod
    def validate_profile_type(cls, value: str) -> str:
        """Validate the user profile type against supported values."""
        normalized = value.strip()
        if normalized not in cls.allowed_profile_types:
            raise ValueError("Invalid profile type")
        return normalized

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        """Validate and normalize a user's full name."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Full name is required")
        return normalized

    @field_validator("city")
    @classmethod
    def validate_city(cls, value: str | None) -> str | None:
        """Normalize an optional city value."""
        if value is None:
            return value
        normalized = value.strip()
        return normalized if normalized else None


class LoginRequest(BaseModel):
    """Login payload accepted by the auth API."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Validate and normalize an email address for login."""
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("Invalid email format")
        return normalized


class TokenPayload(BaseModel):
    """Decoded JWT token payload."""

    sub: str
    exp: int


class UserPublic(BaseModel):
    """Public user fields returned to API clients."""

    id: UUID
    email: str
    full_name: str
    profile_type: str
    city: str | None = None

    model_config = ConfigDict(from_attributes=True)
