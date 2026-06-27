"""Pydantic schemas for RAG memories."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from schemas.base import OrmSchema


class RagMemoryBase(OrmSchema):
    """Shared RAG memory fields."""

    user_id: UUID | None = None
    memory_type: str | None = Field(default=None, max_length=80)
    content: str | None = None
    metadata: dict[str, object] | None = Field(default=None, validation_alias="metadata_json", serialization_alias="metadata")
    faiss_index_id: int | None = None


class RagMemoryCreate(RagMemoryBase):
    """RAG memory creation schema."""


class RagMemoryRead(RagMemoryBase):
    """RAG memory read schema."""

    id: UUID | None = None
    created_at: datetime | None = None
