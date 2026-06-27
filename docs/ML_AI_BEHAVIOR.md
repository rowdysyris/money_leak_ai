# ML and AI Behavior

MoneyLeak AI is deterministic first.

Categorization order:

1. User category correction rules.
2. Verified merchant rules.
3. Keyword rules for income, refunds, transfers, investments, fees, and common merchants.
4. Learned merchant rules after enough distinct user corrections.
5. Cached merchant discovery.
6. Fuzzy verified merchant matching.
7. Local TF-IDF category model fallback when the text has meaningful model vocabulary.
8. Optional AI-enhanced merchant discovery if `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` is configured.
9. Low-confidence `Miscellaneous` with review flag.

The checked-in model artifacts are loaded lazily from `backend/ml/models`:

- `category_model.pkl`
- `tfidf_vectorizer.pkl`
- `anomaly_model.pkl`
- `forecast_model.pkl`

Unknown or generic merchant text does not receive artificially high ML confidence. Strong known category anchors can receive calibrated confidence, while uncertain output remains reviewable.

Anomaly detection combines a trained IsolationForest artifact with a deterministic robust-outlier guard. Forecasting uses the trained XGBoost artifact when available and a deterministic recent-history fallback otherwise.

Retrain artifacts from `backend`:

```bash
python ml/train_category_model.py
python ml/anomaly_model.py
python ml/forecast_model.py
```

If a model file, optional dependency, or AI key is unavailable, the app continues with deterministic rules and safe fallback responses. External AI calls are bounded by `AI_REQUEST_TIMEOUT_SECONDS` and merchant discoveries use a database cache.
