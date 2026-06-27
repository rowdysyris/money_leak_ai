<div align="center">
  <img src="frontend/public/moneyleak-ai-logo.png" alt="MoneyLeak AI logo" width="240" />

  # MoneyLeak AI

  **AI-assisted personal finance intelligence for Indian bank statements**

  Upload statements, normalize transactions, detect recurring payments and financial leakage, and turn raw banking data into explainable saving opportunities.

  [![Live App](https://img.shields.io/badge/Live_App-Open-F04444?style=for-the-badge)](https://money-leak-ai-nine.vercel.app/)
  [![API Docs](https://img.shields.io/badge/API_Docs-Swagger-111217?style=for-the-badge)](https://money-leak-ai-backend.onrender.com/docs)
  [![Backend](https://img.shields.io/badge/Backend-Render-46E3B7?style=for-the-badge)](https://money-leak-ai-backend.onrender.com/health)

  ![React](https://img.shields.io/badge/React-18.2-61DAFB?logo=react&logoColor=111217)
  ![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
  ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white)
  ![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
  ![Tests](https://img.shields.io/badge/Tests-224_Passing-19724A)
</div>

---

## Live Demo

| Service | URL | Purpose |
|---|---|---|
| Web application | [money-leak-ai-nine.vercel.app](https://money-leak-ai-nine.vercel.app/) | Public landing page, registration, login, and application UI |
| Protected dashboard | [Open dashboard](https://money-leak-ai-nine.vercel.app/dashboard) | Authenticated financial analysis workspace |
| API documentation | [Swagger UI](https://money-leak-ai-backend.onrender.com/docs) | Interactive FastAPI endpoint documentation |
| Backend health | [Health endpoint](https://money-leak-ai-backend.onrender.com/health) | Application and database connectivity status |
| Backend readiness | [Readiness endpoint](https://money-leak-ai-backend.onrender.com/ready) | Deployment readiness check |
| Source code | [GitHub repository](https://github.com/rowdysyris/money_leak_ai) | Full frontend, backend, tests, models, and deployment configuration |

> The backend runs on Render's free tier and may need about a minute to wake after inactivity. Use synthetic statements for demonstration; this portfolio deployment is not an audited production service for real financial data.

## Overview

MoneyLeak AI is a full-stack personal finance platform that converts inconsistent CSV and Excel bank statements into structured, explainable financial intelligence. It combines deterministic rules, user corrections, statistical analysis, and optional machine learning to identify spending patterns without making external AI services a requirement.

The application can:

- Parse CSV, XLSX, and XLS statements from multiple Indian banks.
- Detect metadata rows and map inconsistent statement columns.
- Clean dates, descriptions, amounts, debit/credit direction, and merchant names.
- Categorize transactions using a rule-first confidence pipeline.
- Learn user-specific merchant corrections.
- Detect subscriptions, duplicates, small-spend leakage, bank fees, refunds, and unusual transactions.
- Calculate Money Leak Score, Financial Health Score, burn rate, and daily safe spending limits.
- Track budgets, compare months, generate goal plans, and create smart alerts.
- Export PDF, CSV, and multi-sheet Excel reports.
- Optionally enrich recommendations through LangGraph, RAG memory, and an external LLM.

## Product Flow

```mermaid
flowchart LR
    A[Register or Login] --> B[Upload CSV or Excel]
    B --> C[Validate and Map Columns]
    C --> D[Clean and Categorize]
    D --> E[Detect Leaks and Patterns]
    E --> F[Dashboard and Insights]
    F --> G[Budgets, Goals, and Reports]
    G --> H[User Category Corrections]
    H --> D
```

## Architecture

```mermaid
flowchart TB
    U[React 18 Client] -->|HTTPS and Bearer JWT| V[Vercel]
    V -->|Axios API Requests| R[FastAPI on Render]
    R --> S[Domain Services]
    S --> P[(Neon PostgreSQL)]
    S --> M[Optional ML Models]
    S --> A[LangGraph Workflow]
    A --> G[Optional RAG and LLM]
    R --> X[PDF, CSV, and Excel Reports]
```

The backend follows a layered design:

```text
HTTP request
  -> FastAPI router
  -> Pydantic validation and authentication dependency
  -> Domain service
  -> SQLAlchemy model / PostgreSQL
  -> Standard API response envelope
```

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React 18, React Router, Vite, Tailwind CSS, Recharts, Axios, Lucide |
| Backend | FastAPI, Pydantic, Uvicorn, Python 3.11 |
| Database | PostgreSQL, SQLAlchemy 2, Alembic, Neon |
| Data processing | Pandas, NumPy, openpyxl, xlrd, RapidFuzz |
| Machine learning | XGBoost, scikit-learn, TF-IDF, Isolation Forest, linear regression |
| Optional AI | LangGraph, LangChain, sentence-transformers, FAISS, Anthropic API |
| Reports | ReportLab, openpyxl, CSV exports |
| Testing | Pytest, Vitest, React Testing Library |
| Deployment | Docker, Render, Vercel, Neon PostgreSQL, nginx |

## Core Intelligence

### Defensive Statement Parsing

- Validates filename, extension, upload size, and file signatures before parsing.
- Rejects path traversal and extension/content mismatches.
- Supports CSV encoding fallbacks: UTF-8 BOM, UTF-8, Latin-1, and CP1252.
- Scans the first 21 rows to identify the most likely table header.
- Maps date, description, amount, debit, credit, and balance aliases.
- Requires user confirmation when mapping confidence is below `0.70`.
- Skips malformed rows individually and returns controlled warnings.

### Hybrid Transaction Categorization

The categorizer uses the highest-trust available source in this order:

1. High-value safety review.
2. User-specific merchant correction.
3. Exact verified merchant rule.
4. Contains-based verified merchant rule.
5. Investment and transfer rules.
6. Mature learned merchant rule.
7. City-aware merchant cache.
8. ATM, fuzzy, and keyword rules.
9. ML prediction above `0.60` confidence.
10. Optional merchant discovery.
11. `Miscellaneous` with manual review.

This rule-first design keeps routine financial classifications reproducible and explainable. ML remains a fallback rather than an uncontrolled source of truth.

### Subscription Detection

- Filters refunds, anomalies, transfers, cash withdrawals, investments, fees, and duplicates.
- Groups transactions by normalized merchant.
- Clusters amounts within a `+/-15%` tolerance.
- Measures median day intervals and recurrence consistency.
- Recognizes weekly, biweekly, monthly, quarterly, yearly, and irregular patterns.
- Estimates monthly cost, yearly impact, next charge date, confidence, and cancellation priority.

### Duplicate Detection

- Compares eligible debit transactions with the same merchant and exact amount.
- Assigns `0.95` confidence to same-day candidates.
- Assigns `0.75` confidence to candidates within two days.
- Excludes subscriptions and common money-movement categories to reduce false positives.
- Never deletes transactions automatically; results remain reviewable.

### Money Leak Score

The 0-100 risk score combines:

| Component | Weight |
|---|---:|
| Wants ratio | 30% |
| Small-spend ratio | 20% |
| Subscription burden | 15% |
| Duplicate penalty | 15% |
| Miscellaneous ratio | 10% |
| Savings deficit | 10% |

Higher scores indicate greater leakage risk:

```text
0-30    Healthy
31-60   Leaking
61-80   High Risk
81-100  Critical
```

### Additional Analytics

- Income-aware Financial Health Score.
- Needs, wants, waste, and savings analysis.
- Daily burn rate and month-end survival estimate.
- Daily safe spending limit after recurring obligations.
- Monthly comparison and spending-change explanation.
- Spending personality classification.
- Merchant addiction risk.
- Late-night and weekend spending analysis.
- Goal feasibility and savings-gap planning.
- Bill reminders, refund tracking, and smart alerts.

## Application Pages

| Page | Responsibility |
|---|---|
| Dashboard | Spending totals, charts, categories, merchants, and daily trends |
| Upload | Statement validation, bank presets, and column confirmation |
| Transactions | Search, filter, review, and category correction |
| Money Leaks | Leak score, duplicates, small spends, waste, and saving priorities |
| Subscriptions | Recurring payments, annual impact, confidence, and cancellation priority |
| Budget | Monthly limits, category status, suggestions, and savings progress |
| Financial Health | Income-aware score and behavioral drivers |
| Month Comparison | Month-over-month metrics and change explanations |
| Goal Planner | Target, timeline, recommendation coverage, and remaining gap |
| Smart Alerts | Prioritized unusual-spending and financial-risk alerts |
| Reports | PDF, CSV, and Excel downloads |
| AI Insights | Background workflow with deterministic and optional AI recommendations |

## API Design

All protected API routes require:

```http
Authorization: Bearer <access-token>
```

Successful responses use:

```json
{
  "success": true,
  "data": {},
  "warnings": []
}
```

Errors use:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Safe user-facing message",
    "details": {}
  }
}
```

Major endpoint groups:

```text
/api/auth          Registration, login, and current user
/api/statements    Statement upload and processing
/api/transactions  Transaction review and category corrections
/api/dashboard     Summary and chart data
/api/insights      Leak, recurring, health, monthly, and alert analytics
/api/budget        Budget setup, status, update, and suggestions
/api/goals         Goal-based savings plan
/api/reports       PDF, CSV, and Excel exports
/api/agents        Background analysis and recommendations
/api/rag           Authenticated user memory retrieval
```

The complete interactive contract is available in the [Swagger documentation](https://money-leak-ai-backend.onrender.com/docs).

## Security

- PBKDF2-HMAC-SHA256 password hashing with random salts and 310,000 iterations.
- Expiring HS256 JWT access tokens.
- User ownership filtering on statements, transactions, budgets, reports, agent runs, and RAG memory.
- IDOR protection through authenticated user-scoped database queries.
- File-size, file-type, signature, filename, and path-traversal validation.
- Production CORS with explicit permitted origins.
- Rate limiting on authentication and statement-upload routes.
- Request IDs and structured request-duration logging.
- Generic exception responses that avoid exposing internal stack traces.
- Database credentials and API keys supplied only through deployment environment variables.

## Machine Learning and AI Behavior

MoneyLeak AI does not depend on an LLM for core financial analysis.

- The category classifier uses TF-IDF text features plus amount and timing features with XGBoost.
- The anomaly model uses Isolation Forest and a median absolute deviation safety rule.
- The forecast module uses XGBoost when available and linear regression as fallback.
- LangGraph orchestrates deterministic analytics nodes and falls back to sequential execution.
- RAG uses per-user FAISS memory when embeddings are available and deterministic token overlap otherwise.
- Optional LLM enrichment has bounded timeouts and always falls back to rule-based recommendations.

The bundled category model was trained on deterministic synthetic samples. It demonstrates the complete ML pipeline but should not be presented as production accuracy on all real-world banking data.

## Testing and Quality

The audited repository baseline includes:

```text
Backend tests:   208 passing
Frontend tests:   16 passing
Total:           224 passing
```

Additional checks completed:

- Python compilation.
- Dependency consistency.
- Vite production build.
- Docker image builds.
- Docker Compose startup.
- Alembic migrations.
- Live health and readiness checks.
- End-to-end registration, upload, analysis, and report smoke flow.

Run the backend suite:

```bash
cd backend
pytest tests -q
python -m compileall -q -x ".venv" .
```

Run the frontend suite:

```bash
cd frontend
npm install
npm test
npm run build
```

## Local Development

### Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Local services:

```text
Frontend:     http://localhost:5173
Backend:      http://localhost:8000
API docs:     http://localhost:8000/docs
Health:       http://localhost:8000/health
Readiness:    http://localhost:8000/ready
```

### Manual Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000
```

### Manual Frontend

```powershell
cd frontend
npm install
npm run dev -- --port 5173
```

## Environment Configuration

Backend variables:

```dotenv
DATABASE_URL=postgresql://user:password@host/database?sslmode=require
SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALLOWED_ORIGINS=http://localhost:5173
MAX_UPLOAD_SIZE_MB=10
ENVIRONMENT=development
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
AI_REQUEST_TIMEOUT_SECONDS=10
SECURE_COOKIES=false
RATE_LIMIT_AUTH_PER_MINUTE=120
RATE_LIMIT_UPLOADS_PER_MINUTE=30
```

Frontend variable:

```dotenv
VITE_API_URL=http://localhost:8000
```

Never commit a real `.env` file, database password, JWT secret, or external API key.

## Deployment

```mermaid
flowchart LR
    G[GitHub] --> V[Vercel Frontend]
    G --> R[Render Docker Backend]
    V -->|VITE_API_URL| R
    R -->|DATABASE_URL| N[(Neon PostgreSQL)]
```

Production services:

- Vercel builds the `frontend` directory as a Vite application.
- Render builds the backend Docker image with CPU-only PyTorch and runs Alembic before Uvicorn.
- Neon provides persistent PostgreSQL storage.
- `VITE_API_URL` points the frontend to Render.
- `ALLOWED_ORIGINS` permits the exact Vercel production origin.

## Repository Structure

```text
money_leak_ai/
|-- backend/
|   |-- agents/          LangGraph workflow
|   |-- alembic/         Database migrations
|   |-- ml/              Features, models, training, inference
|   |-- models/          SQLAlchemy entities
|   |-- rag/             Embeddings and FAISS memory
|   |-- routers/         FastAPI endpoints
|   |-- schemas/         Pydantic contracts
|   |-- services/        Finance and parsing algorithms
|   `-- tests/           Backend test suite
|-- frontend/
|   |-- public/          Brand assets
|   `-- src/
|       |-- api/         Axios client
|       |-- components/  Shared UI and layout
|       |-- context/     Authentication state
|       |-- hooks/       Data and animation hooks
|       |-- pages/       Product pages
|       `-- tests/       Frontend tests
|-- docs/                Architecture, API, security, and deployment notes
|-- docker-compose.yml
|-- render.yaml
`-- README.md
```

## Limitations

- CSV, XLSX, and XLS are supported; PDF statement extraction is not yet implemented.
- Free Render instances sleep after inactivity and are unsuitable for latency-sensitive production use.
- Local FAISS indexes on an ephemeral free container may be recreated after deployment or restart.
- The current in-memory rate limiter is designed for a single application instance.
- Browser authentication currently stores the bearer token in local storage; HttpOnly cookie auth would be stronger for a hardened production release.
- Financial insights are budgeting guidance, not investment, tax, credit, or regulated financial advice.
- Real financial statements should not be uploaded to this public portfolio deployment.

## Roadmap

- Privacy-safe PDF statement parsing and OCR.
- Consent-based real-world category evaluation dataset.
- Distributed background jobs and retry handling.
- Redis-backed rate limiting and caching.
- Managed vector storage for persistent RAG memory.
- HttpOnly cookie authentication and stronger browser security headers.
- Observability dashboards, audit events, and login history.
- User-confirmed subscription and duplicate feedback loops.

## Author

Built by [rowdysyris](https://github.com/rowdysyris) as a full-stack fintech and applied-AI portfolio project.

## License

No open-source license has been added yet. The source is publicly visible for demonstration and portfolio review; reuse rights are not granted unless a license is added.

MIT License.
