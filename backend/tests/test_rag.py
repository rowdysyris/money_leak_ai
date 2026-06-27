"""User-scoped FAISS memory persistence and helper tests."""

from pathlib import Path
from uuid import uuid4

import numpy as np
from sqlalchemy.orm import Session

from database import engine
from models import RagMemory, User
from models.enums import ProfileType
from rag import vector_store


def create_user(prefix: str) -> User:
    with Session(engine) as db:
        user = User(
            email=f"{prefix}-{uuid4().hex}@example.com",
            hashed_password="hashed",
            full_name="RAG User",
            profile_type=ProfileType.STUDENT,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


def test_initialize_add_search_and_reload(monkeypatch, tmp_path: Path) -> None:
    user = create_user("rag-persist")
    monkeypatch.setattr(vector_store, "INDEX_ROOT", tmp_path)
    monkeypatch.setattr(vector_store, "get_embedding", lambda _text: np.ones(384, dtype="float32"))
    index = vector_store.initialize_index(user.id)
    assert index is not None
    result = vector_store.add_memory(user.id, "Swiggy belongs to Food & Dining", {"memory_type": "merchant_note"})
    assert result["success"] is True
    assert result["faiss_index_id"] == 0
    assert list(tmp_path.glob("*.index"))
    reloaded = vector_store.initialize_index(user.id)
    assert reloaded.ntotal == 1
    assert "Swiggy" in vector_store.search_memory(user.id, "Swiggy", top_k=1)[0]


def test_embedding_unavailable_stores_database_fallback(monkeypatch, tmp_path: Path) -> None:
    user = create_user("rag-fallback")
    monkeypatch.setattr(vector_store, "INDEX_ROOT", tmp_path)
    monkeypatch.setattr(vector_store, "get_embedding", lambda _text: None)
    result = vector_store.add_memory(user.id, "Budget fallback memory", {"memory_type": "budget_rule"})
    assert result["success"] is True
    assert result["vector_available"] is False
    with Session(engine) as db:
        memory = db.query(RagMemory).filter(RagMemory.user_id == user.id).first()
        assert memory is not None
        assert memory.faiss_index_id is None


def test_memory_is_strictly_user_scoped(monkeypatch, tmp_path: Path) -> None:
    user_a = create_user("rag-a")
    user_b = create_user("rag-b")
    monkeypatch.setattr(vector_store, "INDEX_ROOT", tmp_path)
    monkeypatch.setattr(vector_store, "get_embedding", lambda _text: np.ones(384, dtype="float32"))
    vector_store.add_memory(user_a.id, "Private merchant memory", {"memory_type": "merchant_note"})
    assert vector_store.search_memory(user_b.id, "Private", top_k=5) == []


def test_specialized_helpers_and_empty_inputs(monkeypatch, tmp_path: Path) -> None:
    user = create_user("rag-helper")
    monkeypatch.setattr(vector_store, "INDEX_ROOT", tmp_path)
    monkeypatch.setattr(vector_store, "get_embedding", lambda _text: np.ones(384, dtype="float32"))
    assert vector_store.add_memory(user.id, None)["reason"] == "empty_content"
    assert vector_store.search_memory(user.id, None) == []
    assert vector_store.save_merchant_memory("Cafe", "Food & Dining", "Pune", 0.9, user.id)["success"]
    assert vector_store.save_budget_rule(user.id, "Shopping", 2000)["success"]
    context = vector_store.get_personalized_context(user.id, "Cafe Shopping")
    assert context
