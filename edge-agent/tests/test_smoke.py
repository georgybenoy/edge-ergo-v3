"""Edge agent smoke tests."""

from __future__ import annotations

from edge_ergo.main import get_agent_status


def test_agent_status() -> None:
    status = get_agent_status()
    assert status["status"] == "ready"
    assert status["version"] == "3.0.0"
    assert status["platform"] == "windows"
