"""Forecast artifact and fallback behavior tests."""

from datetime import date, timedelta
from pathlib import Path

from ml.forecast_model import forecast_monthly_spend, train_forecast_model
from ml.model_registry import ModelRegistry


def daily_rows(count: int, amount: float = 100.0) -> list[dict[str, object]]:
    return [{"date": (date(2024, 1, 1) + timedelta(days=index)).isoformat(), "amount": amount} for index in range(count)]


def test_forecast_training_and_data_threshold(tmp_path: Path) -> None:
    result = train_forecast_model(tmp_path)
    assert Path(result["model_path"]).exists()
    registry = ModelRegistry()
    registry.paths["forecast"] = Path(result["model_path"])
    registry.reset()
    insufficient = forecast_monthly_spend(daily_rows(6))
    assert insufficient["forecast"] is None
    assert insufficient["warning"] == "Not enough data for forecast"
    for count in (7, 30):
        forecast = forecast_monthly_spend(daily_rows(count))
        assert forecast["projected_total"] > 0
        assert forecast["confidence"] in {"low", "medium", "high"}
        assert forecast["method"] in {"xgboost", "linear_regression", "average_based"}


def test_forecast_missing_model_and_zero_spend_are_safe(tmp_path: Path) -> None:
    registry = ModelRegistry()
    registry.paths["forecast"] = tmp_path / "missing.pkl"
    registry.reset()
    fallback = forecast_monthly_spend(daily_rows(7))
    assert fallback["method"] == "linear_regression"
    assert forecast_monthly_spend(daily_rows(7, 0))["projected_total"] == 0
