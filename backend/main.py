"""FastAPI application entrypoint for MoneyLeak AI."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import get_settings
from database import check_database_connection
from middleware import request_context_middleware
from routers import agents_router, auth_router, budget_router, dashboard_router, goals_router, insights_router, rag_router, reports_router, statements_router, transactions_router
from schemas.common import error_response

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("moneyleak-ai")
settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Run lightweight startup checks without preventing degraded startup."""
    logger.info("MoneyLeak AI app started")
    if check_database_connection():
        logger.info("Database connection check passed")
    else:
        logger.warning("Database connection check failed; app will continue running")
    yield


app = FastAPI(title="MoneyLeak AI", lifespan=lifespan)
app.middleware("http")(request_context_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(rag_router)
app.include_router(statements_router)
app.include_router(transactions_router)
app.include_router(dashboard_router)
app.include_router(goals_router)
app.include_router(insights_router)
app.include_router(budget_router)
app.include_router(reports_router)


@app.exception_handler(StarletteHTTPException)
def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Convert HTTPException instances into the standard error envelope."""
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    default_code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    default_message = "Resource not found" if exc.status_code == 404 else "Request failed"
    code = str(detail.get("code", default_code))
    message = str(detail.get("message", default_message))
    details = detail.get("details", {}) if isinstance(detail.get("details", {}), dict) else {}
    return JSONResponse(status_code=exc.status_code, content=error_response(code, message, details))


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert request validation failures into the standard error envelope."""
    validation_errors = []
    for error in exc.errors():
        validation_errors.append(
            {
                "field": ".".join(str(location) for location in error.get("loc", [])),
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "validation_error"),
            }
        )
    return JSONResponse(
        status_code=422,
        content=error_response(
            "VALIDATION_ERROR",
            "Request validation failed",
            {"validation_errors": validation_errors},
        ),
    )


@app.exception_handler(Exception)
def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert unhandled exceptions into a safe generic error envelope."""
    logger.error("Unhandled request failure: %s", exc.__class__.__name__)
    return JSONResponse(
        status_code=500,
        content=error_response("INTERNAL_ERROR", "Something went wrong", {}),
    )


@app.get("/health")
def health_check() -> dict:
    """Return service health status and database reachability."""
    db_status = "connected" if check_database_connection() else "unreachable"
    return {
        "status": "ok",
        "db": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def readiness_check() -> JSONResponse:
    """Return readiness status, including database connectivity."""
    if check_database_connection():
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {"status": "ready", "db": "connected", "timestamp": datetime.now(timezone.utc).isoformat()},
                "warnings": [],
            },
        )
    return JSONResponse(
        status_code=503,
        content=error_response("DATABASE_UNAVAILABLE", "Database is not reachable.", {"db": "unreachable"}),
    )


@app.get("/")
def root() -> dict:
    """Return a simple root response for platform discovery."""
    return {
        "success": True,
        "data": {"name": "MoneyLeak AI", "status": "running"},
        "warnings": [],
    }
