"""RAG memory API routes for MoneyLeak AI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from dependencies import get_current_user
from models import User
from rag.vector_store import search_memory
from schemas.common import success_response

router = APIRouter(prefix="/api/rag", tags=["RAG"])


class RagQueryRequest(BaseModel):
    """Request body for querying user memories."""

    query: str = Field(min_length=1)


@router.post("/query", response_model=None)
def query_memory(payload: RagQueryRequest, current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Search the authenticated user's RAG memories."""
    memories = search_memory(current_user.id, payload.query, top_k=5)
    warnings = [] if memories else ["No relevant memories found"]
    return success_response({"memories": memories}, warnings)
