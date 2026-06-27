"""Application configuration for MoneyLeak AI."""

import secrets
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and optional .env files."""

    DATABASE_URL: str = Field(default="sqlite:///./moneyleak_local.db")
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    ALLOWED_ORIGINS: str = Field(default="http://localhost:5173")
    MAX_UPLOAD_SIZE_MB: int = Field(default=10)
    ENVIRONMENT: str = Field(default="development")
    ANTHROPIC_API_KEY: str = Field(default="")
    OPENAI_API_KEY: str = Field(default="")
    AI_REQUEST_TIMEOUT_SECONDS: float = Field(default=10.0)
    SECURE_COOKIES: bool = Field(default=False)
    DEBUG: bool = Field(default=False)
    RATE_LIMIT_AUTH_PER_MINUTE: int = Field(default=120)
    RATE_LIMIT_UPLOADS_PER_MINUTE: int = Field(default=30)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def validate_access_token_expiry(cls, value: int) -> int:
        """Validate that token expiry is a positive integer."""
        if value <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be greater than zero")
        return value

    @field_validator("MAX_UPLOAD_SIZE_MB")
    @classmethod
    def validate_max_upload_size(cls, value: int) -> int:
        """Validate that upload size is a positive integer."""
        if value <= 0:
            raise ValueError("MAX_UPLOAD_SIZE_MB must be greater than zero")
        return value

    @field_validator("RATE_LIMIT_AUTH_PER_MINUTE", "RATE_LIMIT_UPLOADS_PER_MINUTE")
    @classmethod
    def validate_rate_limit(cls, value: int) -> int:
        """Validate that per-minute rate limits are positive integers."""
        if value <= 0:
            raise ValueError("Rate limits must be greater than zero")
        return value

    @field_validator("AI_REQUEST_TIMEOUT_SECONDS")
    @classmethod
    def validate_ai_timeout(cls, value: float) -> float:
        """Keep optional external AI calls bounded by a positive timeout."""
        if value <= 0 or value > 30:
            raise ValueError("AI_REQUEST_TIMEOUT_SECONDS must be between 0 and 30")
        return value

    def cors_origins(self) -> List[str]:
        """Return allowed CORS origins and reject unsafe production origins."""
        origins = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]
        if self.ENVIRONMENT.strip().lower() == "production":
            unsafe_prefixes = ("http://localhost", "https://localhost", "http://127.0.0.1", "https://127.0.0.1")
            origins = [origin for origin in origins if origin != "*" and not origin.startswith(unsafe_prefixes)]
        if not origins:
            raise ValueError("ALLOWED_ORIGINS must contain at least one explicit origin")
        return origins

    def is_production(self) -> bool:
        """Return whether the app is running in production mode."""
        return self.ENVIRONMENT.strip().lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
