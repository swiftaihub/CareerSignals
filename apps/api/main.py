"""CareerSignals FastAPI application composition.

Connectors and dbt are deliberately absent from this web-process module.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import re
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from apps.api.config import limiter
from apps.api.dependencies.models import APIError
from apps.api.dependencies.repositories import get_repository  # compatibility/test override seam
from apps.api.routers import (
    admin_audit,
    admin_connector_runs,
    admin_metrics,
    admin_users,
    auth,
    configs,
    data_freshness,
    deprecated,
    exports,
    health,
    jobs,
    me,
    pipeline_runs,
    preferences,
)
from packages.careersignal_core.repositories.errors import NotFoundError, RepositoryError
from packages.careersignal_core.settings import get_settings
from packages.careersignal_core.storage.motherduck import MotherDuckConfigurationError
from packages.careersignal_core.storage.postgres_pool import close_postgres_pool
from src.config.loader import ConfigLoadError

LOGGER = logging.getLogger("careersignals.api")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.require_api_configuration()
    yield
    close_postgres_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    application = FastAPI(
        title="CareerSignals API",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.limiter = limiter
    application.add_middleware(SlowAPIMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Content-Disposition", "Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            LOGGER.info(
                "request_complete request_id=%s method=%s path=%s duration_ms=%s",
                request_id,
                request.method,
                request.url.path,
                elapsed_ms,
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @application.exception_handler(APIError)
    async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error_code": exc.error_code},
            headers=exc.headers,
        )

    @application.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later.", "error_code": "RATE_LIMITED"},
            headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
        )

    @application.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc), "error_code": exc.error_code})

    @application.exception_handler(RepositoryError)
    async def repository_error_handler(_: Request, exc: RepositoryError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc), "error_code": exc.error_code})

    @application.exception_handler(ConfigLoadError)
    async def config_error_handler(_: Request, exc: ConfigLoadError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": "Configuration validation failed.", "error_code": "INVALID_CONFIGURATION"},
        )

    @application.exception_handler(MotherDuckConfigurationError)
    async def motherduck_error_handler(_: Request, __: MotherDuckConfigurationError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "The analytics service is temporarily unavailable.",
                "error_code": "ANALYTICS_UNAVAILABLE",
            },
        )

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(me.router)
    application.include_router(jobs.router)
    application.include_router(configs.router)
    application.include_router(pipeline_runs.router)
    application.include_router(preferences.router)
    application.include_router(data_freshness.router)
    application.include_router(exports.router)
    application.include_router(admin_metrics.router)
    application.include_router(admin_connector_runs.router)
    application.include_router(admin_users.router)
    application.include_router(admin_audit.router)
    application.include_router(deprecated.router)
    return application


app = create_app()
