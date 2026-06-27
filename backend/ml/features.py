"""Feature extraction utilities for MoneyLeak AI machine learning models."""

from __future__ import annotations

import logging
import math
import pickle
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger("moneyleak-ai.ml.features")
MODEL_DIR = Path(__file__).resolve().parent / "models"
VECTORIZER_PATH = MODEL_DIR / "tfidf_vectorizer.pkl"
TEXT_FEATURE_COUNT = 500
NUMERIC_FEATURE_COUNT = 6
COMBINED_FEATURE_COUNT = TEXT_FEATURE_COUNT + NUMERIC_FEATURE_COUNT
_CACHED_VECTORIZER: TfidfVectorizer | None = None


def normalize_text(value: Any) -> str:
    """Return a safe lowercase text value for feature extraction."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def combine_text(transaction: dict[str, Any]) -> str:
    """Combine description and merchant into one normalized text field."""
    description = normalize_text(transaction.get("description"))
    merchant = normalize_text(transaction.get("merchant"))
    combined = f"{merchant} {description}".strip()
    return combined if combined else "unknown transaction"


def parse_transaction_date(value: Any) -> date | None:
    """Parse a transaction date from common object or string values."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to a finite float with a defensive default."""
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def load_vectorizer() -> TfidfVectorizer | None:
    """Load the saved TF-IDF vectorizer or return None when unavailable."""
    global _CACHED_VECTORIZER
    if _CACHED_VECTORIZER is not None:
        return _CACHED_VECTORIZER
    if not VECTORIZER_PATH.exists():
        logger.warning("TF-IDF vectorizer missing at %s; using zero text features", VECTORIZER_PATH)
        return None
    try:
        with VECTORIZER_PATH.open("rb") as vectorizer_file:
            loaded = pickle.load(vectorizer_file)
    except (OSError, pickle.PickleError, EOFError, AttributeError, ImportError, ValueError) as exc:
        logger.warning("TF-IDF vectorizer load failed: %s", exc.__class__.__name__)
        return None
    if not hasattr(loaded, "transform"):
        logger.warning("TF-IDF vectorizer file did not contain a transformer")
        return None
    _CACHED_VECTORIZER = loaded
    return _CACHED_VECTORIZER


def set_vectorizer_for_process(vectorizer: TfidfVectorizer | None) -> None:
    """Set the in-process vectorizer cache, mainly for training and tests."""
    global _CACHED_VECTORIZER
    _CACHED_VECTORIZER = vectorizer


def make_fixed_text_features(text: str, vectorizer: TfidfVectorizer | None = None) -> np.ndarray:
    """Return a fixed-length TF-IDF feature vector padded or truncated to 500 values."""
    active_vectorizer = vectorizer if vectorizer is not None else load_vectorizer()
    if active_vectorizer is None:
        return np.zeros(TEXT_FEATURE_COUNT, dtype=float)
    try:
        transformed = active_vectorizer.transform([text]).toarray()[0]
    except (AttributeError, ValueError, TypeError) as exc:
        logger.warning("TF-IDF transform failed: %s", exc.__class__.__name__)
        return np.zeros(TEXT_FEATURE_COUNT, dtype=float)
    fixed = np.zeros(TEXT_FEATURE_COUNT, dtype=float)
    usable_length = min(TEXT_FEATURE_COUNT, int(transformed.shape[0]))
    if usable_length > 0:
        fixed[:usable_length] = transformed[:usable_length]
    return fixed


def extract_numeric_features(transaction: dict[str, Any]) -> np.ndarray:
    """Extract numeric and binary features from a transaction dictionary."""
    amount = abs(safe_float(transaction.get("amount"), 0.0))
    transaction_date = parse_transaction_date(transaction.get("transaction_date") or transaction.get("date"))
    day_of_week = float(transaction_date.weekday()) if transaction_date is not None else 0.0
    is_weekend = 1.0 if transaction_date is not None and transaction_date.weekday() >= 5 else 0.0
    amount_bucket = math.log1p(amount)
    is_refund = 1.0 if bool(transaction.get("is_refund", False)) else 0.0
    is_late_night = 1.0 if bool(transaction.get("is_late_night", False)) else 0.0
    return np.array([amount, day_of_week, is_weekend, amount_bucket, is_refund, is_late_night], dtype=float)


def extract_features(transaction: dict[str, Any]) -> np.ndarray:
    """Extract fixed-length text, numeric, and binary ML features from a transaction."""
    if not isinstance(transaction, dict):
        transaction = {}
    text = combine_text(transaction)
    text_features = make_fixed_text_features(text)
    numeric_features = extract_numeric_features(transaction)
    return np.concatenate([text_features, numeric_features]).astype(float)


def extract_feature_matrix(transactions: list[dict[str, Any]], vectorizer: TfidfVectorizer | None = None) -> np.ndarray:
    """Extract a 2D feature matrix from transaction dictionaries with a supplied vectorizer."""
    rows = []
    for transaction in transactions:
        safe_transaction = transaction if isinstance(transaction, dict) else {}
        text = combine_text(safe_transaction)
        text_features = make_fixed_text_features(text, vectorizer=vectorizer)
        numeric_features = extract_numeric_features(safe_transaction)
        rows.append(np.concatenate([text_features, numeric_features]).astype(float))
    if not rows:
        return np.empty((0, COMBINED_FEATURE_COUNT), dtype=float)
    return np.vstack(rows)


def batch_extract_features(transactions: list[dict[str, Any]]) -> np.ndarray:
    """Return a fixed-shape feature matrix for a batch of transactions."""
    return extract_feature_matrix(transactions or [])
