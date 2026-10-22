"""Smoke tests for FastAPI health endpoints and application factory."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_health_live_endpoint(client: TestClient) -> None:
    """Verifies that /health/live returns HTTP 200 and status ok."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_initialization() -> None:
    """Verifies that settings load with correct defaults."""
    cfg = Settings()
    assert cfg.APP_NAME == "EdgeErgo Hosted API"
    assert cfg.API_V1_PREFIX == "/api/v1"
    assert cfg.ENROLLMENT_TOKEN_TTL_MINUTES == 15
    assert cfg.MAX_BATCH_SIZE == 100
    assert cfg.MAX_EXPORT_ROWS == 10000
    assert cfg.SUPABASE_SERVICE_ROLE_KEY is None
