"""EdgeErgo V3 — Security & Request Tracking Middlewares."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings
from app.core.errors import build_error_response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assigns or propagates X-Request-ID header across requests and responses."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming_id = request.headers.get("X-Request-ID")
        request_id = incoming_id if incoming_id else str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces standard HTTP security response headers."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        # Add HSTS when running with HTTPS or in production
        if request.url.scheme == "https" or settings.APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        return response


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """Rejects request payloads exceeding MAX_REQUEST_BODY_SIZE_BYTES."""

    def __init__(self, app: ASGIApp, max_bytes: int | None = None) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes or settings.MAX_REQUEST_BODY_SIZE_BYTES

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length_int = int(content_length)
                if length_int > self.max_bytes:
                    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
                    return build_error_response(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        code="REQUEST_TOO_LARGE",
                        message=(
                            f"Request body size exceeds maximum limit of {self.max_bytes} bytes"
                        ),
                        request_id=request_id,
                    )
            except ValueError:
                pass

        return await call_next(request)
