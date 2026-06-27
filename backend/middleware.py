"""Production middleware for request tracing and lightweight rate limits."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from config import get_settings
from schemas.common import error_response

logger = logging.getLogger("moneyleak-ai.middleware")
RateBucket = deque[float]
RATE_BUCKETS: dict[tuple[str, str], RateBucket] = defaultdict(deque)


def client_key(request: Request) -> str:
    """Return a stable client key without trusting spoofable headers by default."""
    return request.client.host if request.client else "unknown"


def rate_limit_for_path(path: str) -> int | None:
    """Return the configured per-minute limit for protected hot paths."""
    settings = get_settings()
    if path.startswith("/api/auth/"):
        return settings.RATE_LIMIT_AUTH_PER_MINUTE
    if path.startswith("/api/statements/upload"):
        return settings.RATE_LIMIT_UPLOADS_PER_MINUTE
    return None


def rate_limited(request: Request, now: float) -> bool:
    """Return True when the request exceeds its simple in-memory rate limit."""
    limit = rate_limit_for_path(request.url.path)
    if limit is None:
        return False
    bucket_key = (client_key(request), request.url.path)
    bucket = RATE_BUCKETS[bucket_key]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= limit:
        return True
    bucket.append(now)
    return False


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Attach request IDs, structured access logs, and local rate limiting."""
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    start_time = time.perf_counter()

    if rate_limited(request, time.time()):
        response = JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=error_response("RATE_LIMITED", "Too many requests. Please try again shortly.", {}),
        )
        response.headers["X-Request-ID"] = request_id
        return response

    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_complete",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response
