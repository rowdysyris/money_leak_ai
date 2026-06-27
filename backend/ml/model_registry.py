"""Safe lazy model registry for MoneyLeak AI optional ML models."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger("moneyleak-ai.ml.model_registry")


class ModelRegistry:
    """Singleton registry that loads optional models without crashing the app."""

    _instance: "ModelRegistry | None" = None
    _lock = Lock()

    def __new__(cls) -> "ModelRegistry":
        """Return the singleton registry instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize registry paths and in-memory model storage once."""
        if getattr(self, "_initialized", False):
            return
        self.model_dir = Path(__file__).resolve().parent / "models"
        self.paths = {
            "category": self.model_dir / "category_model.pkl",
            "anomaly": self.model_dir / "anomaly_model.pkl",
            "forecast": self.model_dir / "forecast_model.pkl",
            "tfidf_vectorizer": self.model_dir / "tfidf_vectorizer.pkl",
        }
        self.models: dict[str, Any | None] = {key: None for key in self.paths}
        self.loaded = False
        self._initialized = True

    def _load_model_file(self, name: str, path: Path) -> Any | None:
        """Load one pickle file and return None when it is unavailable or invalid."""
        if not path.exists():
            logger.warning("%s model file missing at %s", name, path)
            return None
        try:
            with path.open("rb") as model_file:
                return pickle.load(model_file)
        except (OSError, pickle.PickleError, EOFError, AttributeError, ImportError, ValueError, TypeError) as exc:
            logger.warning("%s model load failed: %s", name, exc.__class__.__name__)
            return None

    def load_all_models(self) -> None:
        """Load all optional models, catching failures for each model independently."""
        for name, path in self.paths.items():
            self.models[name] = self._load_model_file(name, path)
        self.loaded = True

    def _ensure_loaded(self) -> None:
        """Load models once before serving lookup requests."""
        if not self.loaded:
            self.load_all_models()

    def get_category_model(self) -> Any | None:
        """Return the category model bundle or None when unavailable."""
        self._ensure_loaded()
        return self.models.get("category")

    def get_anomaly_model(self) -> Any | None:
        """Return the anomaly model bundle or None when unavailable."""
        self._ensure_loaded()
        return self.models.get("anomaly")

    def get_forecast_model(self) -> Any | None:
        """Return the optional forecast model or None when unavailable."""
        self._ensure_loaded()
        return self.models.get("forecast")

    def get_vectorizer(self) -> Any | None:
        """Return the saved TF-IDF vectorizer or None when unavailable."""
        self._ensure_loaded()
        return self.models.get("tfidf_vectorizer")

    def is_available(self, model_name: str) -> bool:
        """Return whether a named optional model is loaded and available."""
        self._ensure_loaded()
        aliases = {
            "category_model": "category",
            "anomaly_model": "anomaly",
            "forecast_model": "forecast",
            "vectorizer": "tfidf_vectorizer",
        }
        return self.models.get(aliases.get(model_name, model_name)) is not None

    def reset(self) -> None:
        """Clear loaded models so tests or runtime changes can force a reload."""
        self.models = {key: None for key in self.paths}
        self.loaded = False
