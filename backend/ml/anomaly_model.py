"""Optional anomaly detection model for MoneyLeak AI transactions."""

from __future__ import annotations

import logging
import math
import pickle
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest

try:
    from ml.model_registry import ModelRegistry
except ModuleNotFoundError:  # Support direct execution: python ml/anomaly_model.py
    from model_registry import ModelRegistry

logger = logging.getLogger("moneyleak-ai.ml.anomaly_model")
MODEL_DIR = Path(__file__).resolve().parent / "models"
ANOMALY_MODEL_PATH = MODEL_DIR / "anomaly_model.pkl"


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert any value to a finite float with a defensive fallback."""
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
    """Parse a date from common date object or string forms."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def stable_category_code(category: Any) -> float:
    """Return a deterministic numeric code for a category value."""
    text = str(category or "Miscellaneous")
    return float(sum(ord(char) for char in text) % 101)


def normalized_merchant(transaction: dict[str, Any]) -> str:
    """Return a normalized merchant text value for frequency calculations."""
    merchant = str(transaction.get("merchant") or "unknown").strip().lower()
    return merchant if merchant else "unknown"


def merchant_frequency(transaction: dict[str, Any], all_user_transactions: list[Any]) -> float:
    """Count how often the transaction merchant appears in the user's transaction list."""
    merchant = normalized_merchant(transaction)
    if not all_user_transactions:
        return 1.0
    count = 0
    for item in all_user_transactions:
        item_dict = item if isinstance(item, dict) else {
            "merchant": getattr(item, "merchant", None),
        }
        if normalized_merchant(item_dict) == merchant:
            count += 1
    return float(max(count, 1))


def build_anomaly_feature(transaction: dict[str, Any], all_user_transactions: list[Any] | None = None) -> np.ndarray:
    """Build one IsolationForest feature row for a transaction."""
    safe_transaction = transaction if isinstance(transaction, dict) else {}
    amount = abs(safe_float(safe_transaction.get("amount"), 0.0))
    parsed_date = parse_date(safe_transaction.get("transaction_date") or safe_transaction.get("date"))
    day_of_week = float(parsed_date.weekday()) if parsed_date is not None else 0.0
    category_encoded = stable_category_code(safe_transaction.get("category"))
    frequency = merchant_frequency(safe_transaction, all_user_transactions or [])
    return np.array([[amount, day_of_week, category_encoded, frequency]], dtype=float)


def train_anomaly_model(transactions: list[dict[str, Any]], output_dir: str | Path | None = None) -> dict[str, Any]:
    """Train and save an IsolationForest anomaly model from transaction dictionaries."""
    target_dir = Path(output_dir) if output_dir is not None else MODEL_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_transactions = [transaction for transaction in transactions if isinstance(transaction, dict)]
    if not safe_transactions:
        safe_transactions = [
            {"amount": 100.0, "transaction_date": "2024-01-01", "category": "Food & Dining", "merchant": "Swiggy"},
            {"amount": 500.0, "transaction_date": "2024-01-02", "category": "Groceries", "merchant": "Blinkit"},
            {"amount": 1500.0, "transaction_date": "2024-01-03", "category": "Bills & Utilities", "merchant": "Airtel"},
        ]
        logger.warning("No anomaly training transactions supplied; using minimal synthetic fallback")
    feature_rows = [build_anomaly_feature(transaction, safe_transactions)[0] for transaction in safe_transactions]
    feature_matrix = np.vstack(feature_rows)
    model = IsolationForest(n_estimators=80, contamination="auto", random_state=42)
    model.fit(feature_matrix)
    model_path = target_dir / "anomaly_model.pkl"
    with model_path.open("wb") as model_file:
        pickle.dump(model, model_file)
    return {"model_path": str(model_path), "sample_count": len(safe_transactions)}


def detect_anomaly(transaction: dict[str, Any], all_user_transactions: list[Any]) -> dict[str, Any]:
    """Detect whether a transaction is anomalous using the optional IsolationForest model."""
    registry = ModelRegistry()
    model = registry.get_anomaly_model()
    if model is None:
        return {"is_anomaly": False, "anomaly_score": 0.0, "available": False}
    try:
        features = build_anomaly_feature(transaction if isinstance(transaction, dict) else {}, all_user_transactions or [])
        score = float(model.score_samples(features)[0])
        current_amount = float(features[0][0])
        history_amounts = []
        for item in all_user_transactions or []:
            value = item.get("amount") if isinstance(item, dict) else getattr(item, "amount", None)
            amount = abs(safe_float(value, 0.0))
            if amount > 0:
                history_amounts.append(amount)
        robust_outlier = False
        if len(history_amounts) >= 3 and current_amount > 0:
            median = float(np.median(history_amounts))
            deviations = np.abs(np.asarray(history_amounts, dtype=float) - median)
            mad = float(np.median(deviations))
            threshold = max(median * 5.0, median + (6.0 * max(mad, 1.0)))
            robust_outlier = current_amount > threshold
        return {"is_anomaly": bool(robust_outlier or score < -0.65), "anomaly_score": round(score, 4), "available": True}
    except (AttributeError, TypeError, ValueError, IndexError, FloatingPointError) as exc:
        logger.warning("Optional anomaly detection failed: %s", exc.__class__.__name__)
        return {"is_anomaly": False, "anomaly_score": 0.0, "available": False}


def default_training_transactions(sample_count: int = 300) -> list[dict[str, Any]]:
    """Build deterministic normal-spend samples for standalone model training."""
    merchants = ["Swiggy", "Blinkit", "Airtel", "Uber", "Amazon"]
    categories = ["Food & Dining", "Groceries", "Bills & Utilities", "Travel & Transport", "Shopping"]
    return [
        {
            "amount": float(100 + ((index * 37) % 2400)),
            "transaction_date": f"2024-01-{(index % 28) + 1:02d}",
            "category": categories[index % len(categories)],
            "merchant": merchants[index % len(merchants)],
        }
        for index in range(max(20, sample_count))
    ]


def main() -> None:
    """Train the anomaly detector when the module is executed as a script."""
    result = train_anomaly_model(default_training_transactions())
    logger.info("Anomaly model trained with %s samples", result["sample_count"])


if __name__ == "__main__":
    main()
