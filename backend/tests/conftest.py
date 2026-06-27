"""Shared pytest fixtures for MoneyLeak AI backend tests."""

import pytest
from pathlib import Path

import models

_ = models
from database import Base, engine
from ml.features import set_vectorizer_for_process
from ml.model_registry import ModelRegistry


@pytest.fixture(autouse=True)
def reset_optional_model_registry() -> None:
    """Prevent tests that redirect optional model paths from leaking into later tests."""
    registry = ModelRegistry()
    model_dir = Path(__file__).resolve().parents[1] / "ml" / "models"
    default_paths = {
        "category": model_dir / "category_model.pkl",
        "anomaly": model_dir / "anomaly_model.pkl",
        "forecast": model_dir / "forecast_model.pkl",
        "tfidf_vectorizer": model_dir / "tfidf_vectorizer.pkl",
    }
    registry.model_dir = model_dir
    registry.paths = default_paths
    registry.reset()
    set_vectorizer_for_process(None)
    yield
    registry.paths = default_paths
    registry.reset()
    set_vectorizer_for_process(None)


@pytest.fixture(scope="session", autouse=True)
def reset_database_schema() -> None:
    """Reset the test database schema before running backend tests."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
