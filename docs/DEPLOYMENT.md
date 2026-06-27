# Deployment Guide

## Backend on Render

1. Create a PostgreSQL database on Neon, Supabase, or Render.
2. Create a Render Web Service with root directory `backend`.
3. Build command: `pip install -r requirements.txt`.
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
5. Set environment variables from `.env.example`.
6. Set `ENVIRONMENT=production`.
7. Set `ALLOWED_ORIGINS` to the exact Vercel frontend URL.
8. Run `alembic upgrade head`.
9. Verify `GET /ready` returns HTTP 200.

## Frontend on Vercel

1. Import the GitHub repository.
2. Set project root to `frontend`.
3. Build command: `npm run build`.
4. Output directory: `dist`.
5. Set `VITE_API_URL` to the Render backend URL.

## Docker

Local:

```bash
cp .env.example .env
docker compose build
docker compose up
```

The backend container applies `alembic upgrade head` before starting Uvicorn.

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```
