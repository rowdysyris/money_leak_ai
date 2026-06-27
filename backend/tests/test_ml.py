"""Optional ML layer tests for MoneyLeak AI."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ml.anomaly_model import detect_anomaly
from ml.features import COMBINED_FEATURE_COUNT, extract_features, set_vectorizer_for_process
from ml.forecast_model import forecast_monthly_spend
from ml.model_registry import ModelRegistry
from ml.predict_category import predict_category
from ml.train_category_model import train_category_model


def configure_empty_registry(tmp_path: Path) -> ModelRegistry:
    """Point the singleton model registry to an empty temporary model directory."""
    registry = ModelRegistry()
    registry.model_dir = tmp_path
    registry.paths = {
        "category": tmp_path / "category_model.pkl",
        "anomaly": tmp_path / "anomaly_model.pkl",
        "forecast": tmp_path / "forecast_model.pkl",
        "tfidf_vectorizer": tmp_path / "tfidf_vectorizer.pkl",
    }
    registry.reset()
    set_vectorizer_for_process(None)
    return registry


def sample_transaction() -> dict:
    """Return a representative transaction dictionary for ML tests."""
    return {
        "merchant": "Swiggy",
        "description": "UPI/SWIGGY dinner order",
        "amount": 420.0,
        "transaction_date": "2024-01-15",
        "is_refund": False,
        "is_late_night": False,
        "category": "Food & Dining",
    }


def test_model_registry_handles_missing_files(tmp_path: Path) -> None:
    """The model registry handles missing optional model files without raising."""
    registry = configure_empty_registry(tmp_path)
    registry.load_all_models()
    assert registry.get_category_model() is None
    assert registry.get_anomaly_model() is None
    assert registry.get_forecast_model() is None
    assert registry.is_available("category") is False


def test_predict_category_returns_none_when_no_model(tmp_path: Path) -> None:
    """Category prediction returns a safe unavailable response when no model is saved."""
    configure_empty_registry(tmp_path)
    result = predict_category(sample_transaction())
    assert result == {"category": None, "confidence": 0.0, "available": False}


def test_features_extracted_correctly(tmp_path: Path) -> None:
    """Feature extraction returns a finite fixed-length vector for transaction dictionaries."""
    configure_empty_registry(tmp_path)
    features = extract_features(sample_transaction())
    assert isinstance(features, np.ndarray)
    assert features.shape[0] == COMBINED_FEATURE_COUNT
    assert np.isfinite(features).all()


def test_anomaly_model_handles_missing_model(tmp_path: Path) -> None:
    """Anomaly detection returns a safe unavailable response when the model is missing."""
    configure_empty_registry(tmp_path)
    result = detect_anomaly(sample_transaction(), [sample_transaction()])
    assert result == {"is_anomaly": False, "anomaly_score": 0.0, "available": False}


def test_forecast_insufficient_data_warning() -> None:
    """Forecasting returns a clear warning when fewer than seven days are available."""
    result = forecast_monthly_spend([{"date": "2024-01-01", "amount": 100.0}])
    assert result["forecast"] is None
    assert result["warning"] == "Not enough data for forecast"


def test_training_script_runs_without_error(tmp_path: Path) -> None:
    """The category training function runs and writes model artifacts."""
    result = train_category_model(output_dir=tmp_path, sample_count=170)
    assert Path(result["model_path"]).exists()
    assert Path(result["vectorizer_path"]).exists()
    assert result["sample_count"] == 170
    assert 0.0 <= result["accuracy"] <= 1.0


def test_ml_does_not_crash_app_when_model_missing(tmp_path: Path) -> None:
    """Missing optional ML models do not crash prediction or forecasting helpers."""
    configure_empty_registry(tmp_path)
    prediction = predict_category({"merchant": None, "description": None, "amount": None})
    anomaly = detect_anomaly({"merchant": None, "amount": None}, [])
    forecast = forecast_monthly_spend([])
    assert prediction["available"] is False
    assert anomaly["available"] is False
    assert forecast["forecast"] is None
