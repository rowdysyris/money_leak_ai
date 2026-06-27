"""Shared ORM helpers for MoneyLeak AI models."""

from datetime import datetime, timezone
from uuid import UUID, uuid4


def generate_uuid() -> UUID:
    """Return a random UUID4 value for primary keys."""
    return uuid4()


def utc_now() -> datetime:
    """Return the current UTC timestamp with timezone information."""
    return datetime.now(timezone.utc)
