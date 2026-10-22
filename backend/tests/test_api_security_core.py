"""EdgeErgo V3 — Tests for Production Settings Fail-Closed, Redaction, and Contract."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.logging import redact_sensitive_text
from app.main import app


def test_production_settings_fail_closed() -> None:
    """Verifies that APP_ENV=production fails closed when placeholder values exist."""
    with pytest.raises(ValueError, match="Production configuration failed closed"):
        Settings(
            APP_ENV="production",
            SUPABASE_URL="https://placeholder.supabase.co",
            SUPABASE_JWT_ISSUER="https://placeholder.supabase.co/auth/v1",
            SUPABASE_JWKS_URL="https://placeholder.supabase.co/auth/v1/.well-known/jwks.json",
            DATABASE_URL="postgresql+asyncpg://edgeergo_api:password@localhost:5432/postgres",
            FRONTEND_ORIGIN="*",
            ENABLE_API_DOCS=True,
        )

    # Valid production settings pass cleanly
    valid_prod = Settings(
        APP_ENV="production",
        SUPABASE_URL="https://prod-app.supabase.co",
        SUPABASE_JWT_ISSUER="https://prod-app.supabase.co/auth/v1",
        SUPABASE_JWKS_URL="https://prod-app.supabase.co/auth/v1/.well-known/jwks.json",
        DATABASE_URL="postgresql+asyncpg://edgeergo_api:secure_pass@db.prod.internal:5432/postgres",
        FRONTEND_ORIGIN="https://dashboard.edgeergo.com",
        ENABLE_API_DOCS=False,
    )
    assert valid_prod.APP_ENV == "production"


def test_logging_redacts_tokens_and_connection_strings() -> None:
    """Verifies that logger redacts Bearer JWTs, device secrets, and database passwords."""
    raw_sample = (
        "Error in connection "
        "postgresql+asyncpg://edgeergo_api:MySuperSecretPass123@db.supabase.com:5432/postgres "
        "with header Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abc123secret "
        "and credential eed_pub1.secret99 and token eet_singleuse123"
    )
    redacted = redact_sensitive_text(raw_sample)

    assert "MySuperSecretPass123" not in redacted
    assert "abc123secret" not in redacted
    assert "secret99" not in redacted
    assert "singleuse123" not in redacted

    assert "Bearer [REDACTED]" in redacted
    assert "eed_[REDACTED]" in redacted
    assert "eet_[REDACTED]" in redacted
    assert "postgresql+asyncpg://edgeergo_api:[REDACTED]@db.supabase.com" in redacted


@pytest.mark.asyncio
async def test_security_headers_and_request_id(async_client: AsyncClient) -> None:
    """Verifies that responses include security headers and X-Request-ID."""
    # 1. Custom incoming request ID is propagated
    res = await async_client.get(
        "/health/live",
        headers={"X-Request-ID": "custom-trace-uuid-1234"},
    )
    assert res.status_code == 200
    assert res.headers["X-Request-ID"] == "custom-trace-uuid-1234"

    # Security headers
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in res.headers["Content-Security-Policy"]

    # 2. Auto-generated request ID when absent
    res_auto = await async_client.get("/health/live")
    assert "X-Request-ID" in res_auto.headers
    assert len(res_auto.headers["X-Request-ID"]) > 10


@pytest.mark.asyncio
async def test_request_body_size_limit_rejection(async_client: AsyncClient) -> None:
    """Verifies request payloads exceeding MAX_REQUEST_BODY_SIZE_BYTES are rejected with 413."""
    # 3MB content-length header
    res = await async_client.post(
        "/api/v1/devices/enroll",
        headers={"Content-Length": str(3 * 1024 * 1024)},
        content=b"x" * 100,
    )
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "REQUEST_TOO_LARGE"


@pytest.mark.asyncio
async def test_readiness_probe_database_failure() -> None:
    """Verifies /health/ready returns 503 DATABASE_UNAVAILABLE when database check fails."""

    # Mock AsyncSessionLocal to raise an exception
    with patch("app.main.AsyncSessionLocal") as mock_session_local:
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Connection refused to DB host")
        mock_session_local.return_value.__aenter__.return_value = mock_session

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            res = await client.get("/health/ready")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "unavailable"
            assert data["error"]["code"] == "DATABASE_UNAVAILABLE"
            # Ensure raw exception details / credentials are NOT leaked to client
            assert "Connection refused" not in data["error"]["message"]


def test_openapi_snapshot_matches_committed_contract() -> None:
    """Contract test verifying app.openapi() strictly matches committed docs/openapi.json."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    snapshot_path = repo_root / "docs" / "openapi.json"
    assert snapshot_path.exists(), "Committed docs/openapi.json must exist"

    committed_spec = json.loads(snapshot_path.read_text(encoding="utf-8"))
    live_spec = app.openapi()

    assert live_spec == committed_spec, (
        "Live OpenAPI schema does not match committed docs/openapi.json. "
        "Update the snapshot by running python scripts or regenerating openapi.json."
    )
