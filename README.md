# MoneyLeak AI

MoneyLeak AI is a full-stack personal finance intelligence platform for Indian bank statements. It accepts CSV, XLS, and XLSX uploads, cleans and categorizes transactions, detects recurring charges and spending leaks, and turns the results into dashboards, alerts, savings plans, and downloadable reports.

## Verified status

| Area | Result |
|---|---|
| Backend tests | 208 passed |
| Frontend tests | 16 passed |
| Frontend production build | Passed |
| Python compile and dependency checks | Passed |
| Docker images and live Compose stack | Passed |
| Live health, readiness, auth, migrations, and frontend smoke | Passed |

The verified local stack is available at:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- Readiness: `http://localhost:8000/ready`

## Features

- JWT registration, login, current-user lookup, ownership checks, request IDs, and rate limits.
- Defensive CSV/XLS/XLSX uploads with extension, size, magic-byte, filename, and parser validation.
- Automatic SBI, HDFC, ICICI, Axis, Kotak, Canara, Union Bank, and Paytm Payments Bank presets.
- Low-confidence column detection that pauses before persistence and asks the user to confirm a manual mapping.
- Multi-statement ingestion, monthly merging, and duplicate-row removal.
- Rule-first categorization with correction memory, user merchant rules, trained TF-IDF classification, and safe low-confidence review behavior.
- Trained category, anomaly, and spending forecast artifacts with deterministic fallbacks.
- Subscription, duplicate payment, hidden fee, small-spend, unusual-spend, merchant-risk, and late-night-spend analysis.
- Dashboard, transaction review, category rules, budgets, smart alerts, month comparison, financial health, and goal planning.
- Explainable saving priorities, spending personality, optional AI merchant discovery, agent workflow, and RAG memory.
- PDF, CSV, and multi-sheet Excel reports.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.11+, SQLAlchemy, Alembic |
| Database | PostgreSQL; SQLite is supported for local tests |
| Data and ML | Pandas, NumPy, scikit-learn, XGBoost, openpyxl, xlrd |
| Agents and RAG | LangGraph, LangChain, FAISS with deterministic fallbacks |
| Reports | ReportLab, CSV, openpyxl |
| Frontend | React 18, Vite, Tailwind CSS, Recharts |
| Runtime | Docker Compose, nginx |

## Repository structure

```text
moneyleak-ai/
|-- backend/
|   |-- agents/
|   |-- alembic/
|   |-- ml/
|   |-- models/
|   |-- rag/
|   |-- routers/
|   |-- schemas/
|   |-- services/
|   |-- tests/
|   |-- Dockerfile
|   `-- requirements.txt
|-- frontend/
|   |-- src/
|   |-- Dockerfile
|   |-- nginx.conf
|   `-- package.json
|-- docs/
|-- docker-compose.yml
|-- render.yaml
|-- .env.example
`-- README.md
```

## Quick start with Docker

Create `.env` from the checked-in example and replace every development credential:

```bash
cp .env.example .env
docker compose up --build
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The backend container runs `alembic upgrade head` before Uvicorn starts. A separate migration command is not required for Compose.

## Local development

Backend on Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd frontend
npm ci
npm run dev
```

## Tests

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m compileall -q -x ".venv" .
.\.venv\Scripts\python.exe -m pip check
```

Frontend:

```powershell
cd frontend
npm test
npm run build
```

See [Testing](docs/TESTING.md) for the smoke checklist and coverage details.

## Environment variables

| Variable | Required | Purpose |
|---|---:|---|
| `DATABASE_URL` | Yes | SQLAlchemy database URL. |
| `SECRET_KEY` | Yes | Long random JWT signing secret. |
| `ALGORITHM` | Yes | JWT algorithm; defaults to `HS256`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | JWT lifetime. |
| `ALLOWED_ORIGINS` | Yes | Comma-separated exact frontend origins. |
| `MAX_UPLOAD_SIZE_MB` | Yes | Upload limit; defaults to 10 MB. |
| `RATE_LIMIT_AUTH_PER_MINUTE` | Yes | Per-IP auth request limit. |
| `RATE_LIMIT_UPLOADS_PER_MINUTE` | Yes | Per-IP upload request limit. |
| `ENVIRONMENT` | Yes | `development` or `production`. |
| `ANTHROPIC_API_KEY` | Optional | Enables Anthropic merchant discovery. |
| `OPENAI_API_KEY` | Optional | Enables OpenAI merchant discovery. |
| `AI_REQUEST_TIMEOUT_SECONDS` | Optional | External AI timeout from 0 to 30 seconds. |
| `VITE_API_URL` | Frontend | Backend base URL used at frontend build time. |

`POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` are also required by the local Compose stack.

## Important endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Process and database health. |
| GET | `/ready` | Deployment readiness. |
| POST | `/api/statements/upload` | Upload one statement, optionally with a confirmed column map. |
| POST | `/api/statements/upload-multiple` | Upload and merge statements. |
| GET | `/api/statements` | List the current user's statement jobs. |
| GET | `/api/statements/{id}` | Read statement processing status. |
| GET | `/api/transactions` | Search and filter transactions. |
| PATCH | `/api/transactions/{id}/category` | Correct a category and save feedback. |
| GET | `/api/insights/merchant-addiction` | Merchant concentration and repeat-spend risk. |
| GET | `/api/insights/smart-alerts` | Combined bill and refund/reversal alerts. |
| POST | `/api/goals/plan` | Build a goal-based savings plan. |
| POST | `/api/agents/analyze` | Run the resilient analysis workflow. |
| POST | `/api/rag/query` | Query user-scoped financial memory. |
| GET | `/api/reports/download/{pdf|csv|excel}` | Download reports. |

All business endpoints use a consistent success/error envelope. See [API](docs/API.md) for details.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API](docs/API.md)
- [Bank presets](docs/BANK_PRESETS.md)
- [Deployment](docs/DEPLOYMENT.md)
- [ML and AI behavior](docs/ML_AI_BEHAVIOR.md)
- [Security](docs/SECURITY.md)
- [Testing](docs/TESTING.md)

## Security and limitations

- Never commit `.env`, database files, local virtual environments, `node_modules`, test caches, or FAISS user data.
- Production CORS requires explicit non-local origins and a unique secret.
- Uploaded bank data is sensitive; deploy only to infrastructure appropriate for financial data.
- PDF statements are intentionally rejected. Export CSV, XLS, or XLSX instead.
- Optional AI providers and RAG dependencies fail closed to deterministic local behavior.
- Financial insights are guidance and depend on statement completeness and parsing quality.

## GitHub checklist

```powershell
git status
git add moneyleak-ai
git commit -m "Finalize MoneyLeak AI production-ready build"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

The current parent repository has no commit yet, so review `git status` before the first commit.

## License

MIT License.
