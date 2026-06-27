"""Tests for optional agent workflow and RAG memory infrastructure."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

import numpy as np

from agents.graph import run_agent_workflow, sequential_workflow
from routers.agents import optional_ai_recommendations
from sqlalchemy.orm import Session

from database import engine
from models import User
from models.enums import ProfileType
from rag import embeddings
from rag import vector_store


def sample_transactions() -> list[dict]:
    """Return deterministic transaction fixtures for agent workflow tests."""
    return [
        {
            "transaction_date": date(2024, 1, 1),
            "merchant": "Salary",
            "description": "January salary credited",
            "amount": 40000,
            "transaction_type": "credit",
            "category": "Transfers",
            "need_want_waste_type": "unknown",
        },
        {
            "transaction_date": date(2024, 1, 2),
            "merchant": "Swiggy",
            "description": "Food order",
            "amount": -450,
            "transaction_type": "debit",
            "category": "Food & Dining",
            "need_want_waste_type": "want",
        },
        {
            "transaction_date": date(2024, 1, 3),
            "merchant": "Netflix",
            "description": "Netflix monthly subscription",
            "amount": -649,
            "transaction_type": "debit",
            "category": "Subscriptions",
            "need_want_waste_type": "want",
        },
    ]


def create_rag_user() -> User:
    """Create a persisted user for RAG foreign-key tests."""
    with Session(engine) as db_session:
        user = User(
            email=f"rag-{uuid4()}@example.com",
            hashed_password="hashed-password",
            full_name="RAG Test User",
            profile_type=ProfileType.STUDENT,
            city="Bhopal",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        db_session.expunge(user)
        return user


def test_agent_workflow_completes_successfully(monkeypatch):
    """Workflow completes with deterministic analytics and no API key."""
    monkeypatch.setattr("agents.graph.settings.ANTHROPIC_API_KEY", "")
    result = run_agent_workflow(
        {
            "statement_id": str(uuid4()),
            "user_id": str(uuid4()),
            "transactions": sample_transactions(),
            "warnings": [],
            "errors": [],
        }
    )
    assert result["current_step"] == "completed"
    assert result["output_summary"]["ai_enhanced"] is False
    assert "analytics" in result["output_summary"]


def test_agent_workflow_with_empty_transactions(monkeypatch):
    """Workflow returns a graceful warning for empty transaction lists."""
    monkeypatch.setattr("agents.graph.settings.ANTHROPIC_API_KEY", "")
    result = run_agent_workflow({"statement_id": str(uuid4()), "user_id": str(uuid4()), "transactions": []})
    assert result["current_step"] == "completed"
    assert "No transactions found" in result["warnings"]


def test_agent_node_failure_does_not_crash_workflow(monkeypatch):
    """A failing node is captured in state errors and later nodes still execute."""
    def failing_node(state):
        """Raise a deterministic failure for workflow resilience testing."""
        raise RuntimeError("forced failure")

    monkeypatch.setattr("agents.graph.analytics_node", failing_node)
    result = sequential_workflow({"statement_id": str(uuid4()), "user_id": str(uuid4()), "transactions": sample_transactions()})
    assert result["current_step"] == "completed"
    assert any("failing_node failed" in error for error in result["errors"])


def test_agents_return_rule_based_when_no_api_key(monkeypatch):
    """Recommendation helper returns deterministic output when Anthropic is not configured."""
    monkeypatch.setattr("routers.agents.settings.ANTHROPIC_API_KEY", "")
    result = optional_ai_recommendations({"recommendations": [{"action": "Cancel duplicate"}], "warnings": []}, [], None)
    assert result["ai_enhanced"] is False
    assert result["reason"] == "api_key_not_configured"
    assert result["recommendations"]


def test_rag_query_with_no_memories(monkeypatch):
    """Memory search returns an empty list when an index has no vectors."""
    class EmptyIndex:
        """Minimal empty index fixture."""

        ntotal = 0

    monkeypatch.setattr(vector_store, "get_embedding", lambda text: np.ones(384, dtype="float32"))
    monkeypatch.setattr(vector_store, "initialize_index", lambda user_id: EmptyIndex())
    assert vector_store.search_memory(uuid4(), "food", top_k=5) == []


def test_rag_add_and_retrieve_memory(monkeypatch, tmp_path):
    """Memory can be added and retrieved when embeddings and FAISS are available."""
    user = create_rag_user()
    monkeypatch.setattr(vector_store, "INDEX_ROOT", Path(tmp_path))
    monkeypatch.setattr(vector_store, "get_embedding", lambda text: np.ones(384, dtype="float32"))
    add_result = vector_store.add_memory(user.id, "Badastoor is Food & Dining in Bhopal", {"memory_type": "merchant_note"})
    assert add_result["success"] is True
    results = vector_store.search_memory(user.id, "Badastoor category", top_k=1)
    assert results
    assert "Badastoor" in results[0]


def test_faiss_missing_index_creates_new(monkeypatch, tmp_path):
    """Initializing a user index creates a new empty index file when possible."""
    monkeypatch.setattr(vector_store, "INDEX_ROOT", Path(tmp_path))
    index = vector_store.initialize_index(uuid4())
    if index is not None:
        assert int(getattr(index, "ntotal", 0)) == 0
        assert list(Path(tmp_path).glob("*.index"))


def test_embedding_model_unavailable_graceful(monkeypatch):
    """Embedding helper returns None if the model loader cannot provide a model."""
    monkeypatch.setattr(embeddings, "load_embedding_model", lambda: None)
    assert embeddings.get_embedding("test memory") is None
