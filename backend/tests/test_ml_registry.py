"""Focused tests for safe optional model loading."""

from pathlib import Path

from ml.model_registry import ModelRegistry


def test_registry_is_singleton_and_loads_trained_models() -> None:
    registry = ModelRegistry()
    registry.model_dir = Path(__file__).resolve().parents[1] / "ml" / "models"
    registry.paths = {
        "category": registry.model_dir / "category_model.pkl",
        "anomaly": registry.model_dir / "anomaly_model.pkl",
        "forecast": registry.model_dir / "forecast_model.pkl",
        "tfidf_vectorizer": registry.model_dir / "tfidf_vectorizer.pkl",
    }
    registry.reset()
    assert registry is ModelRegistry()
    registry.load_all_models()
    assert registry.is_available("category_model")
    assert registry.is_available("anomaly_model")
    assert registry.is_available("forecast_model")
    assert registry.get_category_model() is not None


def test_registry_missing_files_are_safe(tmp_path: Path, caplog) -> None:
    registry = ModelRegistry()
    original_paths = dict(registry.paths)
    try:
        registry.paths = {name: tmp_path / path.name for name, path in original_paths.items()}
        registry.reset()
        registry.load_all_models()
        registry.load_all_models()
        assert registry.get_category_model() is None
        assert registry.get_anomaly_model() is None
        assert registry.get_forecast_model() is None
        assert registry.is_available("category_model") is False
        assert "missing" in caplog.text.lower()
    finally:
        registry.paths = original_paths
        registry.reset()
