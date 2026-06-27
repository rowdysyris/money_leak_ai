"""FAISS-backed user memory store for MoneyLeak AI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import SessionLocal
from models import RagMemory
from rag.embeddings import EMBEDDING_DIMENSION, get_embedding

logger = logging.getLogger(__name__)
INDEX_ROOT = Path(__file__).resolve().parents[1] / "data" / "faiss_index"


def import_faiss() -> Any | None:
    """Import FAISS when available, returning None without crashing when unavailable."""
    try:
        import faiss
    except ImportError:
        logger.warning("faiss is not installed; vector memory is disabled")
        return None
    return faiss


def normalize_user_id(user_id: str | UUID) -> str:
    """Return a filesystem-safe user identifier string."""
    safe_value = str(user_id or "").strip()
    if safe_value == "":
        return "unknown"
    return safe_value.replace("/", "_").replace("\\", "_")


def index_path_for_user(user_id: str | UUID) -> Path:
    """Return the FAISS index path for a user."""
    INDEX_ROOT.mkdir(parents=True, exist_ok=True)
    return INDEX_ROOT / f"user_{normalize_user_id(user_id)}.index"


def initialize_index(user_id: str | UUID) -> Any | None:
    """Create or load a user's FAISS index, returning None when FAISS is unavailable."""
    faiss = import_faiss()
    if faiss is None:
        return None
    path = index_path_for_user(user_id)
    if path.exists():
        try:
            return faiss.read_index(str(path))
        except (RuntimeError, OSError, ValueError) as exc:
            logger.warning("Existing FAISS index could not be read and will be recreated: %s", exc.__class__.__name__)
    index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
    try:
        faiss.write_index(index, str(path))
    except (RuntimeError, OSError, ValueError) as exc:
        logger.warning("Empty FAISS index could not be persisted: %s", exc.__class__.__name__)
    return index


def persist_index(user_id: str | UUID, index: Any) -> None:
    """Persist a FAISS index if FAISS is available."""
    faiss = import_faiss()
    if faiss is None or index is None:
        return
    try:
        faiss.write_index(index, str(index_path_for_user(user_id)))
    except (RuntimeError, OSError, ValueError) as exc:
        logger.warning("FAISS index save failed: %s", exc.__class__.__name__)


def safe_uuid(value: str | UUID) -> UUID | None:
    """Convert a value to UUID or return None when invalid."""
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        logger.warning("RAG memory skipped because user_id is invalid")
        return None


def save_memory_row(user_uuid: UUID, content: str, metadata: dict[str, Any] | None, faiss_index_id: int | None) -> dict[str, Any]:
    """Persist a memory row and return a structured result."""
    db: Session = SessionLocal()
    try:
        memory = RagMemory(
            user_id=user_uuid,
            memory_type=str((metadata or {}).get("memory_type") or "merchant_note"),
            content=content,
            metadata_json=metadata or {},
            faiss_index_id=faiss_index_id,
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        return {"success": True, "memory_id": str(memory.id), "faiss_index_id": faiss_index_id}
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("RAG memory database save failed: %s", exc.__class__.__name__)
        return {"success": False, "reason": "database_error"}
    finally:
        db.close()


def add_memory(user_id: str | UUID, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Embed content, add it to FAISS when available, and persist metadata in rag_memories."""
    safe_content = str(content or "").strip()
    if safe_content == "":
        return {"success": False, "reason": "empty_content"}
    user_uuid = safe_uuid(user_id)
    if user_uuid is None:
        return {"success": False, "reason": "invalid_user_id"}

    embedding = get_embedding(safe_content)
    index = initialize_index(user_uuid) if embedding is not None else None
    if embedding is None or index is None:
        reason = "embedding_unavailable" if embedding is None else "faiss_unavailable"
        logger.warning("RAG vector operation skipped: %s; saving text memory fallback", reason)
        result = save_memory_row(user_uuid, safe_content, metadata, None)
        if result.get("success"):
            result["vector_available"] = False
            result["reason"] = reason
        return result

    vector = np.asarray([embedding], dtype="float32")
    faiss_index_id = int(getattr(index, "ntotal", 0))
    try:
        index.add(vector)
        persist_index(user_uuid, index)
    except (RuntimeError, ValueError, TypeError) as exc:
        logger.warning("FAISS add operation failed: %s; saving text memory fallback", exc.__class__.__name__)
        result = save_memory_row(user_uuid, safe_content, metadata, None)
        if result.get("success"):
            result["vector_available"] = False
            result["reason"] = "faiss_add_failed"
        return result
    result = save_memory_row(user_uuid, safe_content, metadata, faiss_index_id)
    if result.get("success"):
        result["vector_available"] = True
    return result


def get_memory_by_faiss_ids(db: Session, user_id: UUID, faiss_ids: list[int]) -> dict[int, RagMemory]:
    """Return memory rows keyed by FAISS index id."""
    if not faiss_ids:
        return {}
    rows = (
        db.query(RagMemory)
        .filter(RagMemory.user_id == user_id, RagMemory.faiss_index_id.in_(faiss_ids))
        .all()
    )
    return {int(row.faiss_index_id): row for row in rows if row.faiss_index_id is not None}


def text_fallback_search(user_uuid: UUID, query: str, top_k: int) -> list[str]:
    """Return recent memories with simple token overlap when vector search is unavailable."""
    query_tokens = {token.lower() for token in str(query or "").split() if token.strip()}
    db: Session = SessionLocal()
    try:
        rows = db.query(RagMemory).filter(RagMemory.user_id == user_uuid).order_by(RagMemory.created_at.desc()).limit(200).all()
        scored: list[tuple[int, str]] = []
        for row in rows:
            content = str(row.content or "")
            content_tokens = {token.lower() for token in content.split() if token.strip()}
            score = len(query_tokens.intersection(content_tokens)) if query_tokens else 0
            scored.append((score, content))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [content for score, content in scored[: max(1, int(top_k or 5))] if content and (score > 0 or not query_tokens)]
    except SQLAlchemyError as exc:
        logger.warning("RAG text fallback lookup failed: %s", exc.__class__.__name__)
        return []
    finally:
        db.close()


def search_memory(user_id: str | UUID, query: str, top_k: int = 5) -> list[str]:
    """Search a user's FAISS memories, falling back to deterministic text memory lookup."""
    user_uuid = safe_uuid(user_id)
    if user_uuid is None:
        return []
    safe_query = str(query or "").strip()
    if safe_query == "":
        return []
    embedding = get_embedding(safe_query)
    if embedding is None:
        logger.warning("RAG vector search skipped because embedding model is unavailable")
        return text_fallback_search(user_uuid, safe_query, top_k)
    index = initialize_index(user_uuid)
    if index is None or int(getattr(index, "ntotal", 0)) <= 0:
        return text_fallback_search(user_uuid, safe_query, top_k)
    limit = max(1, int(top_k or 5))
    try:
        distances, indices = index.search(np.asarray([embedding], dtype="float32"), limit)
    except (RuntimeError, ValueError, TypeError) as exc:
        logger.warning("FAISS search failed: %s", exc.__class__.__name__)
        return text_fallback_search(user_uuid, safe_query, top_k)
    faiss_ids = [int(value) for value in indices[0].tolist() if int(value) >= 0]
    if not faiss_ids:
        return text_fallback_search(user_uuid, safe_query, top_k)
    db: Session = SessionLocal()
    try:
        rows_by_id = get_memory_by_faiss_ids(db, user_uuid, faiss_ids)
        ordered = []
        for faiss_id in faiss_ids:
            row = rows_by_id.get(faiss_id)
            if row is not None:
                ordered.append(str(row.content or ""))
        return ordered or text_fallback_search(user_uuid, safe_query, top_k)
    except SQLAlchemyError as exc:
        logger.warning("RAG memory lookup failed: %s", exc.__class__.__name__)
        return []
    finally:
        db.close()


def save_merchant_memory(merchant: str, category: str, city: str | None, confidence: float, user_id: str | UUID | None = None) -> dict[str, Any]:
    """Save a merchant/category memory for a user when a user id is provided."""
    safe_merchant = str(merchant or "").strip()
    safe_category = str(category or "Miscellaneous").strip() or "Miscellaneous"
    safe_city = str(city or "India").strip() or "India"
    content = f"Merchant {safe_merchant} in {safe_city} belongs to category {safe_category}."
    metadata = {
        "memory_type": "merchant_note",
        "merchant": safe_merchant,
        "category": safe_category,
        "city": safe_city,
        "confidence": float(confidence or 0.0),
    }
    if user_id is None:
        logger.warning("Merchant memory was not saved because no user_id was provided")
        return {"success": False, "reason": "missing_user_id"}
    return add_memory(user_id, content, metadata)


def save_budget_rule(user_id: str | UUID, category: str, monthly_limit: float) -> dict[str, Any]:
    """Save one user-scoped budget rule as reusable memory."""
    safe_category = str(category or "Miscellaneous").strip() or "Miscellaneous"
    safe_limit = max(float(monthly_limit or 0.0), 0.0)
    content = f"Budget rule: keep {safe_category} spending within INR {safe_limit:.2f} per month."
    return add_memory(
        user_id,
        content,
        {"memory_type": "budget_rule", "category": safe_category, "monthly_limit": safe_limit},
    )


def get_personalized_context(user_id: str | UUID, query: str = "financial preferences", top_k: int = 5) -> str:
    """Return relevant user memories as a compact context string."""
    return "\n".join(search_memory(user_id, query, top_k=top_k))
