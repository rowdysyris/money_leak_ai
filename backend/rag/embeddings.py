"""Optional sentence-transformer embeddings for MoneyLeak AI RAG memory."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


@lru_cache(maxsize=1)
def load_embedding_model() -> Any | None:
    """Load the sentence-transformers model once, or return None when unavailable."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.warning("sentence-transformers is not installed; RAG embeddings are disabled")
        return None
    try:
        return SentenceTransformer(MODEL_NAME, local_files_only=True)
    except (OSError, RuntimeError, ValueError) as exc:
        logger.warning("Embedding model could not be loaded: %s", exc.__class__.__name__)
        return None


def get_embedding(text: str) -> np.ndarray | None:
    """Return a normalized embedding vector for text, or None when embeddings are unavailable."""
    safe_text = str(text or "").strip()
    if safe_text == "":
        logger.warning("Embedding request skipped because text is empty")
        return None
    model = load_embedding_model()
    if model is None:
        return None
    try:
        embedding = model.encode(safe_text, normalize_embeddings=True)
    except (RuntimeError, ValueError, TypeError) as exc:
        logger.warning("Embedding generation failed: %s", exc.__class__.__name__)
        return None
    vector = np.asarray(embedding, dtype="float32")
    if vector.ndim != 1 or vector.size == 0:
        logger.warning("Embedding model returned an invalid vector")
        return None
    return vector
