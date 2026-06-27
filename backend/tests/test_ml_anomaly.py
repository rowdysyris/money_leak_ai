"""Training, prediction, and scale tests for anomaly detection."""

import math
import time
from pathlib import Path

from ml.anomaly_model import default_training_transactions, detect_anomaly, train_anomaly_model
from ml.model_registry import ModelRegistry


def configure_anomaly(path: Path) -> None:
    registry = ModelRegistry()
    registry.paths["anomaly"] = path / "anomaly_model.pkl"
    registry.reset()


def test_anomaly_training_and_extreme_detection(tmp_path: Path) -> None:
    history = default_training_transactions(300)
    train_anomaly_model(history, tmp_path)
    configure_anomaly(tmp_path)
    normal = detect_anomaly(history[10], history)
    extreme = detect_anomaly({**history[10], "amount": 1_000_000}, history)
    assert normal["available"] is True
    assert normal["is_anomaly"] is False
    assert extreme["is_anomaly"] is True
    assert isinstance(extreme["is_anomaly"], bool)
    assert math.isfinite(extreme["anomaly_score"])


def test_anomaly_edge_cases_complete_quickly(tmp_path: Path) -> None:
    history = [{"merchant": "Same", "amount": 100, "category": "Shopping"} for _ in range(1000)]
    train_anomaly_model(history, tmp_path)
    configure_anomaly(tmp_path)
    started = time.perf_counter()
    result = detect_anomaly({"merchant": None, "amount": None}, history)
    assert time.perf_counter() - started < 5
    assert result["is_anomaly"] is False
