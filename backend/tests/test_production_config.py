"""Production Environment Configuration & Security Verification Tests.

Verifies:
1. Fail-closed validation stops service startup when production requirements are violated
2. OpenAPI documentation endpoints (/docs, /redoc, /openapi.json) are disabled in production
3. CORS strictly permits only the configured FRONTEND_ORIGIN and rejects rogue origins
4. Structured JSON logging redacts tokens, credentials, and connection secrets
"""

from __future__ import annotations

import io
import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.logging import RedactingJsonFormatter
from app.main import create_app


def make_valid_prod_settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "APP_ENV": "production",
        "FRONTEND_ORIGIN": "https://dashboard.edgeergo.com",
        "SUPABASE_URL": "https://real-org.supabase.co",
        "SUPABASE_JWT_ISSUER": "https://real-org.supabase.co/auth/v1",
        "SUPABASE_JWKS_URL": "https://real-org.supabase.co/auth/v1/.well-known/jwks.json",
        "DATABASE_URL": "postgresql+asyncpg://edgeergo_api:prod_secret_vault@db.prod.internal:6543/postgres",
        "ENABLE_API_DOCS": False,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_valid_production_settings_instantiates() -> None:
    """Verifies that fully populated production settings pass validation."""
    s = make_valid_prod_settings()
    assert s.APP_ENV == "production"
    assert s.ENABLE_API_DOCS is False
    assert s.FRONTEND_ORIGIN == "https://dashboard.edgeergo.com"


@pytest.mark.parametrize(
    "bad_override,expected_err",
    [
        (
            {"DATABASE_URL": "postgresql+asyncpg://postgres:password@localhost:5432/postgres"},
            "DATABASE_URL must be set to a production database connection",
        ),
        (
            {"SUPABASE_URL": "https://placeholder.supabase.co"},
            "SUPABASE_URL must be set to a valid URL in production",
        ),
        (
            {"SUPABASE_JWT_ISSUER": "https://placeholder.supabase.co/auth/v1"},
            "SUPABASE_JWT_ISSUER must be set to a valid issuer in production",
        ),
        (
            {"SUPABASE_JWKS_URL": "https://placeholder.supabase.co/auth/v1/.well-known/jwks.json"},
            "SUPABASE_JWKS_URL must be set to a valid JWKS endpoint in production",
        ),
        (
            {"FRONTEND_ORIGIN": "*"},
            "FRONTEND_ORIGIN must be explicitly set to a production origin (no wildcards)",
        ),
        (
            {"FRONTEND_ORIGIN": "http://localhost:5173"},
            "FRONTEND_ORIGIN must be explicitly set to a production origin (no wildcards)",
        ),
        (
            {"ENABLE_API_DOCS": True},
            "ENABLE_API_DOCS must be set to False in production",
        ),
    ],
)
def test_production_fails_closed_on_misconfiguration(
    bad_override: dict[str, Any], expected_err: str
) -> None:
    """Security Guard: Service refuses to boot if any security parameter is missing or unsafe."""
    with pytest.raises(ValueError) as exc_info:
        make_valid_prod_settings(**bad_override)
    assert expected_err in str(exc_info.value)
    assert "Production configuration failed closed" in str(exc_info.value)


def test_production_docs_endpoints_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies /docs, /redoc, and /openapi.json return 404 when ENABLE_API_DOCS is False."""
    prod_settings = make_valid_prod_settings()
    monkeypatch.setattr("app.core.config.settings", prod_settings)
    monkeypatch.setattr("app.main.settings", prod_settings)

    app = create_app()
    client = TestClient(app)

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_production_cors_origin_enforcement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that only the configured FRONTEND_ORIGIN is allowed in CORS preflight."""
    prod_settings = make_valid_prod_settings()
    monkeypatch.setattr("app.core.config.settings", prod_settings)
    monkeypatch.setattr("app.main.settings", prod_settings)

    app = create_app()
    client = TestClient(app)

    # 1. Allowed origin preflight returns 200 with Allow-Origin header
    res_allowed = client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": "https://dashboard.edgeergo.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_allowed.status_code == 200
    assert (
        res_allowed.headers.get("access-control-allow-origin") == "https://dashboard.edgeergo.com"
    )

    # 2. Rogue origin preflight does NOT return matching allow header
    res_rogue = client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": "https://rogue-origin.evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_rogue.headers.get("access-control-allow-origin") != "https://rogue-origin.evil.com"


def test_production_logging_redaction() -> None:
    """Verifies that secrets, bearer tokens, and device credentials are redacted from logs."""
    formatter = RedactingJsonFormatter()
    raw_token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.do_not_leak_signature"
    )
    raw_secret = "eed_edp_prod_01.test_secret_token_12345"

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(formatter)
    test_logger = logging.getLogger("test_redact_prod")
    test_logger.handlers = [handler]
    test_logger.setLevel(logging.INFO)

    test_logger.info("Incoming request headers: Bearer %s and Device %s", raw_token, raw_secret)
    log_content = log_stream.getvalue()

    assert raw_token not in log_content
    assert raw_secret not in log_content
    assert "[REDACTED]" in log_content
