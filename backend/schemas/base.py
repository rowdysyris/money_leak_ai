"""Shared Pydantic schema configuration."""

from pydantic import BaseModel, ConfigDict


class OrmSchema(BaseModel):
    """Base schema configured for SQLAlchemy ORM object serialization."""

    model_config = ConfigDict(from_attributes=True, use_enum_values=True, populate_by_name=True)
