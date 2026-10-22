"""EdgeErgo V3 — FastAPI Application Entrypoint & Factory."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.core.middleware import (
    RequestBodyLimitMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("app.main")


def create_app() -> FastAPI:
    """FastAPI application factory with logging, middlewares, and routers."""
    setup_logging(settings.LOG_LEVEL)

    # OpenAPI docs enabled only if explicitly configured
    docs_url = "/docs" if settings.ENABLE_API_DOCS else None
    redoc_url = "/redoc" if settings.ENABLE_API_DOCS else None
    openapi_url = "/openapi.json" if settings.ENABLE_API_DOCS else None

    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # Register standardized error handlers
    register_error_handlers(application)

    # Middlewares (order: request-id first, then body limit, then security headers, then CORS)
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=settings.MAX_REQUEST_BODY_SIZE_BYTES,
    )
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Health Probes
    @application.get("/health/live", tags=["Health"])
    async def health_live() -> dict[str, Any]:
        """Liveness probe indicating process is running."""
        return {"status": "ok"}

    @application.get("/health/ready", tags=["Health"])
    async def health_ready() -> JSONResponse:
        """Readiness probe checking database connectivity without leaking connection secrets."""
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1;"))
            return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready"})
        except Exception as exc:
            logger.error(f"Readiness probe failed database check: {exc}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "unavailable",
                    "error": {
                        "code": "DATABASE_UNAVAILABLE",
                        "message": "Database connection verification failed.",
                    },
                },
            )

    # Include V1 API Routes
    application.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return application


# ASGI instance for Uvicorn
app = create_app()
