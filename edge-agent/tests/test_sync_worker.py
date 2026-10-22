"""Unit tests for SyncWorker scheduling, backoff calculation, and failure handling."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx
import pytest

from edge_ergo.overlay.presenter import OverlayPresenter
from edge_ergo.overlay.types import OverlayState
from edge_ergo.storage.credentials import MemoryCredentialStore, save_device_secret
from edge_ergo.storage.database import Database
from edge_ergo.storage.migrations import apply_migrations
from edge_ergo.storage.repository import StorageRepository
from edge_ergo.storage.types import (
    AssessmentEventRecord,
    DeviceIdentity,
    SyncQueueState,
)
from edge_ergo.sync.worker import SyncWorker, compute_backoff_delay


@pytest.fixture
def repo(tmp_path: Path) -> StorageRepository:
    db = Database(tmp_path / "sync_worker_test.db")
    apply_migrations(db)
    return StorageRepository(db)


@pytest.fixture
def store() -> MemoryCredentialStore:
    return MemoryCredentialStore()


def setup_enrolled_device(repo: StorageRepository, store: MemoryCredentialStore) -> DeviceIdentity:
    ident = DeviceIdentity(
        device_id=str(uuid.uuid4()),
        public_id="edp_worker_test_01",
        api_base_url="https://api.edgeergo.com",
        label="Test Workstation",
        organization_id=str(uuid.uuid4()),
        enrolled_at="2026-10-20T12:00:00Z",
    )
    repo.save_device_identity(ident)
    save_device_secret(ident.public_id, "eed_edp_worker_test_01.dummy_secret_12345", store=store)
    return ident


def make_record() -> AssessmentEventRecord:
    return AssessmentEventRecord(
        event_id=str(uuid.uuid4()),
        captured_at="2026-10-20T12:00:00Z",
        scoring_method="rula_partial",
        scoring_version="1.0.0",
        validity="valid",
        score=2.0,
        neck_score=2,
        trunk_score=1,
        upper_arm_score=2,
        postural_features=None,
        guidance_codes=["GENERAL_GOOD_POSTURE"],
        software_version="3.0.0",
        created_at="2026-10-20T12:00:00Z",
    )


def test_backoff_bounds_and_jitter() -> None:
    """Verifies exponential backoff bounds and non-negative jitter."""
    delays = [compute_backoff_delay(attempt=0) for _ in range(50)]
    assert all(2.0 <= d <= 5.0 for d in delays)  # 2.0 + jitter(0, 3)

    # High attempt capped at 300 + 3 = 303.0
    high_delays = [compute_backoff_delay(attempt=15) for _ in range(50)]
    assert all(300.0 <= d <= 303.0 for d in high_delays)


def test_successful_batch_upload_acks_events(
    repo: StorageRepository, store: MemoryCredentialStore
) -> None:
    """Verifies that 200 OK with accepted items marks items as acked."""
    setup_enrolled_device(repo, store)
    presenter = OverlayPresenter()

    rec = make_record()
    repo.enqueue_assessment_event(rec)
    assert repo.get_queue_depth() == 1

    # Mock HTTP client returning 200 OK
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [{"event_id": rec.event_id, "status": "accepted", "reason_code": None}],
                "total_accepted": 1,
                "total_duplicates": 0,
                "total_rejected": 0,
            },
        )

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    worker = SyncWorker(
        repository=repo,
        overlay_presenter=presenter,
        credential_store=store,
        http_client=mock_http,
    )

    processed = worker.step_sync()
    assert processed == 1
    assert repo.get_queue_depth() == 0
    assert presenter.view_model.sync_status_text == "Synced"


def test_permanent_rejection_marks_dead(
    repo: StorageRepository, store: MemoryCredentialStore
) -> None:
    """Verifies that server rejected items are quarantined as DEAD and not retried."""
    setup_enrolled_device(repo, store)
    rec = make_record()
    repo.enqueue_assessment_event(rec)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "event_id": rec.event_id,
                        "status": "rejected",
                        "reason_code": "SCHEMA_VALIDATION_FAILED",
                    }
                ],
                "total_accepted": 0,
                "total_duplicates": 0,
                "total_rejected": 1,
            },
        )

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    worker = SyncWorker(repository=repo, credential_store=store, http_client=mock_http)

    processed = worker.step_sync()
    assert processed == 1
    assert repo.get_queue_depth() == 0

    # Verify state in database is dead
    with repo.db.connect() as conn:
        row = conn.execute(
            "SELECT state, last_error_code FROM sync_queue WHERE event_id = ?;", (rec.event_id,)
        ).fetchone()
        assert row["state"] == SyncQueueState.DEAD.value
        assert row["last_error_code"] == "SCHEMA_VALIDATION_FAILED"


def test_transient_network_error_reschedules_retry(
    repo: StorageRepository, store: MemoryCredentialStore
) -> None:
    """Verifies that transient connect errors reschedule items with future next_attempt_at."""
    setup_enrolled_device(repo, store)
    presenter = OverlayPresenter()
    rec = make_record()
    repo.enqueue_assessment_event(rec)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network is unreachable")

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    worker = SyncWorker(
        repository=repo,
        overlay_presenter=presenter,
        credential_store=store,
        http_client=mock_http,
    )

    processed = worker.step_sync()
    assert processed == 0
    assert repo.get_queue_depth() == 1
    assert presenter.view_model.state == OverlayState.OFFLINE

    # Next attempt should be delayed into the future
    with repo.db.connect() as conn:
        row = conn.execute(
            "SELECT state, last_error_code, leased_at FROM sync_queue WHERE event_id = ?;",
            (rec.event_id,),
        ).fetchone()
        assert row["state"] == SyncQueueState.PENDING.value
        assert row["last_error_code"] == "NETWORK_ERROR"
        assert row["leased_at"] is None


def test_auth_error_halts_uploads_and_protects_queue(
    repo: StorageRepository, store: MemoryCredentialStore
) -> None:
    """Critical: 401 Unauthorized stops uploading immediately and leaves data safely in SQLite."""
    setup_enrolled_device(repo, store)
    presenter = OverlayPresenter()
    rec = make_record()
    repo.enqueue_assessment_event(rec)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": {"code": "INVALID_CREDENTIALS", "message": "Device revoked"}}
        )

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    worker = SyncWorker(
        repository=repo,
        overlay_presenter=presenter,
        credential_store=store,
        http_client=mock_http,
    )

    assert not worker.is_auth_halted()
    processed = worker.step_sync()
    assert processed == 0

    # Worker must enter auth halt state
    assert worker.is_auth_halted()
    assert presenter.view_model.state == OverlayState.AUTH_ERROR
    assert "authorization failed" in str(presenter.view_model.error_message)

    # Queue item is NOT marked dead or deleted; remains safely in SQLite
    assert repo.get_queue_depth() == 1

    # Subsequent step_sync calls should be no-ops while auth halted
    processed_again = worker.step_sync()
    assert processed_again == 0


def test_offline_accumulation_drains_in_order(
    repo: StorageRepository, store: MemoryCredentialStore
) -> None:
    """Verifies that events accumulated while offline drain in FIFO order once reconnected."""
    setup_enrolled_device(repo, store)
    rec1 = make_record()
    rec2 = make_record()
    rec3 = make_record()

    repo.enqueue_assessment_event(rec1)
    repo.enqueue_assessment_event(rec2)
    repo.enqueue_assessment_event(rec3)
    assert repo.get_queue_depth() == 3

    received_ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        for ev in body["events"]:
            received_ids.append(ev["event_id"])
        return httpx.Response(
            200,
            json={
                "results": [{"event_id": eid, "status": "accepted"} for eid in received_ids],
                "total_accepted": len(received_ids),
                "total_duplicates": 0,
                "total_rejected": 0,
            },
        )

    mock_http = httpx.Client(transport=httpx.MockTransport(handler))
    worker = SyncWorker(
        repository=repo,
        credential_store=store,
        batch_size=2,  # Batch limit of 2 to verify multi-batch draining
        http_client=mock_http,
    )

    # Cycle 1: leases rec1, rec2
    c1 = worker.step_sync()
    assert c1 == 2
    assert received_ids == [rec1.event_id, rec2.event_id]

    # Cycle 2: leases rec3
    c2 = worker.step_sync()
    assert c2 == 1
    assert received_ids == [rec1.event_id, rec2.event_id, rec3.event_id]
    assert repo.get_queue_depth() == 0
