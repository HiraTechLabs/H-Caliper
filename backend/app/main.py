"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings, validate_runtime_secrets
from app.core.database import dispose_engine
from app.core.deps import AUTH_COOKIE, CSRF_COOKIE, CSRF_HEADER
from app.core.errors import ApiError
from app.core.logging import configure_logging
from app.services.bootstrap import ensure_bootstrap_admin

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self) -> None:
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int) -> bool:
        now = time.monotonic()
        bucket = self.hits[key]
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


limiter = RateLimiter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    validate_runtime_secrets()
    await ensure_bootstrap_admin()
    logger.info("H-Caliper API started env=%s", settings.ENV)
    yield
    await dispose_engine()


app = FastAPI(
    title="H-Caliper API",
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Request-ID"],
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    client = request.client.host if request.client else "unknown"
    path = request.url.path

    if path.startswith(settings.API_PREFIX) and path not in {
        f"{settings.API_PREFIX}/health",
        f"{settings.API_PREFIX}/health/ready",
    }:
        limit = (
            settings.LOGIN_RATE_LIMIT_PER_MINUTE
            if path.endswith("/auth/login") or path.endswith("/auth/bootstrap")
            else settings.RATE_LIMIT_PER_MINUTE
        )
        if not limiter.allow(f"{client}:{path}", limit):
            return JSONResponse(
                status_code=429,
                content={"detail": {"code": "rate_limited", "message": "Too many requests"}},
                headers={"Retry-After": "60"},
            )

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        cookie_token = request.cookies.get(AUTH_COOKIE)
        header_auth = request.headers.get("authorization", "").lower().startswith("bearer ")
        csrf_exempt = path.endswith("/auth/login") or path.endswith("/auth/bootstrap")
        if cookie_token and not header_auth and not csrf_exempt:
            cookie_csrf = request.cookies.get(CSRF_COOKIE)
            header_csrf = request.headers.get(CSRF_HEADER)
            if not cookie_csrf or not header_csrf or cookie_csrf != header_csrf:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": {
                            "code": "csrf_failed",
                            "message": "Missing or invalid CSRF token",
                        }
                    },
                )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    if path.startswith(settings.API_PREFIX):
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "validation_error",
                "message": "Request validation failed",
                "errors": [
                    {"loc": list(e.get("loc", [])), "msg": e.get("msg", "")} for e in exc.errors()
                ],
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("unhandled error request_id=%s", request.headers.get("x-request-id"))
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "internal_error",
                "message": "An internal error occurred. Reference the server logs with the request ID.",
            }
        },
    )


app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "api": settings.API_PREFIX, "status": "ok"}
