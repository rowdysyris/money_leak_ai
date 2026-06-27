"""Category prediction helper for optional ML fallback categorization."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from ml.features import TEXT_FEATURE_COUNT, combine_text, extract_feature_matrix
from ml.model_registry import ModelRegistry

logger = logging.getLogger("moneyleak-ai.ml.predict_category")
CATEGORY_ANCHORS = {
    "Food & Dining": ("swiggy", "zomato", "dominos", "food delivery", "dinner order"),
    "Subscriptions": ("netflix", "spotify", "cloud storage subscription", "monthly plan"),
    "Cash Withdrawal": ("atm cash withdrawal", "cash withdrawal", "atm withdrawal"),
    "Bills & Utilities": ("electricity bill", "mobile recharge", "fiber bill", "gas bill"),
}
GENERIC_TEXT_TERMS = {"upi", "payment", "ref", "extra", "transaction", "general", "other"}


def _extract_bundle_parts(model_bundle: Any) -> tuple[Any | None, Any | None, Any | None]:
    """Extract estimator, label encoder, and vectorizer from a model bundle or estimator."""
    if isinstance(model_bundle, dict):
        estimator = model_bundle.get("model")
        label_encoder = model_bundle.get("label_encoder")
        vectorizer = model_bundle.get("vectorizer")
        return estimator, label_encoder, vectorizer
    return model_bundle, None, None


def _decode_prediction(raw_prediction: Any, label_encoder: Any | None) -> str:
    """Decode a raw model prediction into a category string."""
    if label_encoder is None:
        return str(raw_prediction)
    try:
        decoded = label_encoder.inverse_transform([int(raw_prediction)])[0]
        return str(decoded)
    except (AttributeError, TypeError, ValueError, IndexError) as exc:
        logger.warning("Category label decoding failed: %s", exc.__class__.__name__)
        return str(raw_prediction)


def predict_category(transaction: dict[str, Any]) -> dict[str, Any]:
    """Predict a transaction category if the optional category model is available."""
    registry = ModelRegistry()
    model_bundle = registry.get_category_model()
    if model_bundle is None:
        return {"category": None, "confidence": 0.0, "available": False}

    estimator, label_encoder, vectorizer = _extract_bundle_parts(model_bundle)
    if estimator is None:
        return {"category": None, "confidence": 0.0, "available": False}

    if vectorizer is None:
        vectorizer = registry.get_vectorizer()

    try:
        features = extract_feature_matrix([transaction if isinstance(transaction, dict) else {}], vectorizer=vectorizer)
        raw_prediction = estimator.predict(features)[0]
        probabilities = estimator.predict_proba(features)[0] if hasattr(estimator, "predict_proba") else np.array([0.61])
        finite_probabilities = np.nan_to_num(np.asarray(probabilities, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
        squared = np.square(np.clip(finite_probabilities, 0.0, 1.0))
        denominator = float(np.sum(squared))
        calibrated_confidence = float(np.max(squared) / denominator) if denominator > 0 else 0.0
        raw_confidence = float(np.max(finite_probabilities)) if finite_probabilities.size else 0.0
        category = _decode_prediction(raw_prediction, label_encoder)
        text = combine_text(transaction if isinstance(transaction, dict) else {})
        has_category_anchor = any(anchor in text for anchor in CATEGORY_ANCHORS.get(category, ()))
        confidence = calibrated_confidence if has_category_anchor else raw_confidence
        has_meaningful_text_signal = bool(np.any(np.abs(features[0][:TEXT_FEATURE_COUNT]) > 0))
        if vectorizer is not None and hasattr(vectorizer, "build_analyzer") and hasattr(vectorizer, "vocabulary_"):
            analyzed_terms = vectorizer.build_analyzer()(text)
            vocabulary = getattr(vectorizer, "vocabulary_", {})
            meaningful_terms = [
                term
                for term in analyzed_terms
                if term in vocabulary
                and term not in GENERIC_TEXT_TERMS
                and not term.isdigit()
                and not term.startswith("ref ")
            ]
            has_meaningful_text_signal = bool(meaningful_terms)
        if not has_meaningful_text_signal:
            confidence = min(confidence, 0.4)
    except (AttributeError, TypeError, ValueError, IndexError, FloatingPointError) as exc:
        logger.warning("Optional category model prediction failed: %s", exc.__class__.__name__)
        return {"category": None, "confidence": 0.0, "available": False}

    return {"category": category, "confidence": round(confidence, 4), "available": True}
