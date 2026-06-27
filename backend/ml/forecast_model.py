"""Simple spend forecasting helpers for MoneyLeak AI."""

from __future__ import annotations

import logging
import math
import pickle
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LinearRegression

try:
    from ml.model_registry import ModelRegistry
except ModuleNotFoundError:  # Support direct execution: python ml/forecast_model.py
    from model_registry import ModelRegistry

logger = logging.getLogger("moneyleak-ai.ml.forecast_model")
MODEL_DIR = Path(__file__).resolve().parent / "models"
FORECAST_MODEL_PATH = MODEL_DIR / "forecast_model.pkl"


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to a finite float for forecasting."""
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def parse_date(value: Any) -> date | None:
    """Parse a date value used in daily spend input rows."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def normalize_daily_spends(daily_spends: list[Any]) -> list[tuple[int, float]]:
    """Normalize daily spend rows into day-of-month and amount tuples."""
    normalized: list[tuple[int, float]] = []
    for index, row in enumerate(daily_spends or [], start=1):
        if isinstance(row, dict):
            amount = safe_float(row.get("amount") or row.get("spend") or row.get("total"), 0.0)
            parsed_date = parse_date(row.get("date"))
            day_number = parsed_date.day if parsed_date is not None else index
        elif isinstance(row, (tuple, list)) and len(row) >= 2:
            parsed_date = parse_date(row[0])
            amount = safe_float(row[1], 0.0)
            day_number = parsed_date.day if parsed_date is not None else index
        else:
            amount = safe_float(row, 0.0)
            day_number = index
        normalized.append((int(day_number), max(amount, 0.0)))
    return normalized


def confidence_from_days(day_count: int) -> str:
    """Return a coarse forecast confidence label from available day count."""
    if day_count >= 21:
        return "high"
    if day_count >= 14:
        return "medium"
    return "low"


def forecast_monthly_spend(daily_spends: list[Any]) -> dict[str, Any]:
    """Forecast month-end spend using linear regression on cumulative daily spend."""
    normalized = normalize_daily_spends(daily_spends)
    if len(normalized) < 7:
        return {"forecast": None, "warning": "Not enough data for forecast", "available": True}

    normalized.sort(key=lambda row: row[0])
    days = np.array([row[0] for row in normalized], dtype=float).reshape(-1, 1)
    cumulative = np.cumsum([row[1] for row in normalized]).astype(float)
    if float(cumulative[-1]) == 0.0:
        return {"projected_total": 0.0, "confidence": confidence_from_days(len(normalized)), "method": "average_based", "available": True}

    registry = ModelRegistry()
    trained_model = registry.get_forecast_model()
    if trained_model is not None and hasattr(trained_model, "predict"):
        try:
            day_count = float(len(normalized))
            current_total = float(cumulative[-1])
            projected_total = float(trained_model.predict(np.array([[day_count, current_total, current_total / day_count]], dtype=float))[0])
            return {
                "projected_total": round(max(projected_total, current_total, 0.0), 2),
                "confidence": confidence_from_days(len(normalized)),
                "method": "xgboost",
                "available": True,
            }
        except (AttributeError, TypeError, ValueError, IndexError, FloatingPointError) as exc:
            logger.warning("Trained spend forecast failed; using linear fallback: %s", exc.__class__.__name__)
    try:
        model = LinearRegression()
        model.fit(days, cumulative)
        projected_total = float(model.predict(np.array([[30.0]]))[0])
    except (ValueError, FloatingPointError) as exc:
        logger.warning("Monthly spend forecast failed: %s", exc.__class__.__name__)
        return {"forecast": None, "warning": "Forecast could not be calculated"}
    return {
        "projected_total": round(max(projected_total, 0.0), 2),
        "confidence": confidence_from_days(len(normalized)),
        "method": "linear_regression",
        "available": True,
    }


def train_forecast_model(output_dir: str | Path | None = None) -> dict[str, Any]:
    """Train and save a compact XGBoost model on deterministic spend trajectories."""
    from xgboost import XGBRegressor

    target_dir = Path(output_dir) if output_dir is not None else MODEL_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    features: list[list[float]] = []
    targets: list[float] = []
    for daily_average in (100.0, 250.0, 500.0, 1000.0, 2500.0):
        for day_count in range(7, 31):
            current_total = daily_average * day_count
            features.append([float(day_count), current_total, daily_average])
            targets.append(daily_average * 30.0)
    model = XGBRegressor(n_estimators=80, max_depth=3, learning_rate=0.1, random_state=42, n_jobs=1)
    model.fit(np.asarray(features, dtype=float), np.asarray(targets, dtype=float))
    model_path = target_dir / "forecast_model.pkl"
    with model_path.open("wb") as model_file:
        pickle.dump(model, model_file)
    return {"model_path": str(model_path), "sample_count": len(features)}


def main() -> None:
    """Train the forecast model when the module is executed as a script."""
    result = train_forecast_model()
    logger.info("Forecast model trained with %s samples", result["sample_count"])


if __name__ == "__main__":
    main()
