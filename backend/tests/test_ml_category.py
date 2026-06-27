"""Training and prediction tests for the category classifier."""

from collections import Counter
from pathlib import Path

from ml.features import set_vectorizer_for_process
from ml.model_registry import ModelRegistry
from ml.predict_category import predict_category
from ml.train_category_model import CATEGORIES, generate_synthetic_training_data, train_category_model


def use_models_at(path: Path) -> None:
    registry = ModelRegistry()
    registry.paths = {
        "category": path / "category_model.pkl",
        "anomaly": path / "anomaly_model.pkl",
        "forecast": path / "forecast_model.pkl",
        "tfidf_vectorizer": path / "tfidf_vectorizer.pkl",
    }
    registry.reset()
    set_vectorizer_for_process(None)


def test_training_data_and_holdout_accuracy(tmp_path: Path) -> None:
    samples = generate_synthetic_training_data(500)
    counts = Counter(sample["category"] for sample in samples)
    assert len(samples) >= 200
    assert set(counts) == set(CATEGORIES)
    assert min(counts.values()) >= 5
    result = train_category_model(tmp_path, sample_count=500)
    assert result["accuracy"] >= 0.70
    assert (tmp_path / "category_model.pkl").exists()
    assert (tmp_path / "tfidf_vectorizer.pkl").exists()


def test_required_category_predictions() -> None:
    model_dir = Path(__file__).resolve().parents[1] / "ml" / "models"
    use_models_at(model_dir)
    cases = {
        "Swiggy food order": "Food & Dining",
        "Netflix subscription": "Subscriptions",
        "ATM cash withdrawal": "Cash Withdrawal",
        "electricity bill payment": "Bills & Utilities",
    }
    for text, expected in cases.items():
        result = predict_category({"merchant": text, "description": text, "amount": 500})
        assert result["available"] is True
        assert result["category"] == expected
        assert 0.6 < result["confidence"] <= 1.0


def test_prediction_missing_model_and_bad_input_are_safe(tmp_path: Path) -> None:
    use_models_at(tmp_path)
    assert predict_category({"merchant": None, "description": "", "amount": None}) == {
        "category": None,
        "confidence": 0.0,
        "available": False,
    }
