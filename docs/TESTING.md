# Testing Guide

The final repository audit completed with 208 backend tests and 16 frontend tests passing. The Vite production build, Python compilation, dependency consistency, Docker image builds, Compose startup, migrations, and live HTTP smoke checks also passed.

## Backend

```bash
cd backend
pytest tests -q
python -m compileall -q -x ".venv" .
```

Coverage areas include auth, user isolation, parser hardening, bank presets, budget, category correction memory, reports, dashboard analytics, agents/RAG fallbacks, and empty-data behavior.

The ML suite also verifies model registry loading, batch feature extraction, category confidence behavior, anomaly detection, forecasts, spending personality, merchant risk, AI discovery caching, graph resilience, and ML/API integration.

## Frontend

```bash
cd frontend
npm install
npm test
npm run build
```

Frontend tests cover protected routes, loading and empty states, upload size and mapping confirmation behavior, category correction, controlled API failures, and null-safe formatting helpers.

## Quality checks

```bash
cd backend
python -m compileall -q -x ".venv" .
python -m pip check

cd ../frontend
npm run build
```

## Docker smoke

```bash
docker compose up --build
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl -I http://localhost:5173
```

Compose applies Alembic migrations automatically before starting Uvicorn.

## E2E Smoke Checklist

1. Register a user.
2. Log in.
3. Upload a CSV sample.
4. Confirm dashboard loads.
5. Open transactions and correct a category.
6. Confirm Money Leaks, Subscriptions, Month Comparison, Goal Planner, and Reports pages render.
7. Download a report.
8. Log out.
