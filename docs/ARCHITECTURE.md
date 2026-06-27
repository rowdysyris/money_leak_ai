# MoneyLeak AI Architecture

MoneyLeak AI is a React and FastAPI application for uploading Indian bank statements, normalizing transactions, detecting spending leaks, and generating reports.

## Runtime Components

- Frontend: React, Vite, Tailwind CSS, Recharts.
- Backend API: FastAPI routers under `/api`.
- Database: PostgreSQL in production, SQLite-compatible tests locally.
- Migrations: Alembic under `backend/alembic`.
- Reports: ReportLab PDF, CSV, and Excel generation.
- Intelligence: deterministic rules first, optional ML and AI-assisted merchant discovery as fallback layers.

## Core Workflow

```mermaid
flowchart LR
  A["User signs up or logs in"] --> B["Upload CSV/XLS/XLSX statement"]
  B --> C["Parser validates type, size, header, bank preset"]
  C --> D["Cleaner normalizes dates, amounts, merchants"]
  D --> E["Categorizer applies user rules, verified rules, fuzzy, ML/AI fallback"]
  E --> F["Dashboard, alerts, budgets, leaks, reports"]
  F --> G["User corrects category"]
  G --> H["User rule memory updates future categorization"]
```

## Ownership Boundary

Every persisted financial record carries `user_id`. API routes resolve `current_user` from a JWT and filter by that user before reading or mutating statements, transactions, budgets, goals, report data, and category rules.

