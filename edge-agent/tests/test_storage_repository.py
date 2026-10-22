"""Tests for StorageRepository transactional queries, queue lifecycle, and retention."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from edge_ergo.storage.database import Database
from edge_ergo.storage.migrations import apply_migrations
from edge_ergo.storage.repository import StorageRepository
from edge_ergo.storage.types import (
    AssessmentEventRecord,
    DeviceIdentity,
    SyncQueueState,
)


@pytest.fixture
def repo(tmp_path: Path) -> StorageRepository:
    db = Database(tmp_path / "test_repo.db")
    apply_migrations(db)
    return StorageRepository(db)


def make_record(
    event_id: str | None = None,
    created_at: str | None = None,
    score: float | None = 2.0,
) -> AssessmentEventRecord:
    now_utc = created_at or datetime.now(timezone.utc).isoformat()
    return AssessmentEventRecord(
        event_id=event_id or str(uuid.uuid4()),
        captured_at=now_utc,
        scoring_method="rula_partial",
        scoring_version="1.0.0",
        validity="valid",
        score=score,
        neck_score=2,
        trunk_score=1,
        upper_arm_score=2,
        postural_features=None,
        guidance_codes=["GENERAL_GOOD_POSTURE"],
        software_version="3.0.0",
        created_at=now_utc,
    )


def test_device_identity_lifecycle(repo: StorageRepository) -> None:
    """Verifies atomic save, retrieval, and deletion of device identity."""
    assert repo.get_device_identity() is None

    ident = DeviceIdentity(
        device_id="33333333-3333-3333-3333-333333333333",
        public_id="edp_1234567890abcdef",
        api_base_url="https://api.edgeergo.com",
        label="Lab Desktop 01",
        organization_id="22222222-2222-2222-2222-222222222222",
        enrolled_at="2026-10-20T12:00:00Z",
    )
    repo.save_device_identity(ident)

    loaded = repo.get_device_identity()
    assert loaded is not None
    assert loaded.device_id == ident.device_id
    assert loaded.public_id == ident.public_id
    assert loaded.api_base_url == ident.api_base_url

    # Overwrite / Re-enrollment
    ident_v2 = DeviceIdentity(
        device_id="33333333-3333-3333-3333-333333333333",
        public_id="edp_9999999999abcdef",
        api_base_url="https://api.edgeergo.com",
        label="Lab Desktop 01 - Renamed",
        organization_id="22222222-2222-2222-2222-222222222222",
        enrolled_at="2026-10-20T13:00:00Z",
    )
    repo.save_device_identity(ident_v2)
    loaded_v2 = repo.get_device_identity()
    assert loaded_v2 is not None
    assert loaded_v2.public_id == "edp_9999999999abcdef"

    repo.delete_device_identity()
    assert repo.get_device_identity() is None


def test_enqueue_and_lease_batch(repo: StorageRepository) -> None:
    """Verifies enqueuing assessment records and leasing them in order."""
    rec1 = make_record()
    rec2 = make_record()

    assert repo.get_queue_depth() == 0
    repo.enqueue_assessment_event(rec1)
    repo.enqueue_assessment_event(rec2)
    assert repo.get_queue_depth() == 2

    # Lease up to 1
    batch_1 = repo.lease_batch(max_batch_size=1)
    assert len(batch_1) == 1
    assert batch_1[0][0].event_id == rec1.event_id
    assert batch_1[0][1].state == SyncQueueState.IN_FLIGHT
    assert batch_1[0][1].attempt_count == 1

    # Lease next available
    batch_2 = repo.lease_batch(max_batch_size=10)
    assert len(batch_2) == 1
    assert batch_2[0][0].event_id == rec2.event_id


def test_ack_and_mark_dead(repo: StorageRepository) -> None:
    """Verifies positive acknowledgement and quarantine of permanently rejected items."""
    rec1 = make_record()
    rec2 = make_record()
    repo.enqueue_assessment_event(rec1)
    repo.enqueue_assessment_event(rec2)

    batch = repo.lease_batch(max_batch_size=2)
    assert len(batch) == 2

    # Ack rec1
    repo.ack_events([rec1.event_id])
    assert repo.get_queue_depth() == 1

    # Mark rec2 dead
    repo.mark_dead(rec2.event_id, "VALIDATION_ERROR")
    assert repo.get_queue_depth() == 0

    # Verify neither is returned in next lease
    next_batch = repo.lease_batch(max_batch_size=10)
    assert len(next_batch) == 0


def test_retry_and_backoff_delay(repo: StorageRepository) -> None:
    """Verifies failed items return to pending with next_attempt_at in the future."""
    rec = make_record()
    repo.enqueue_assessment_event(rec)
    batch = repo.lease_batch(max_batch_size=1)
    assert len(batch) == 1

    # Record retry with 60s delay
    repo.record_retry([rec.event_id], "NETWORK_TIMEOUT", retry_delay_seconds=60.0)

    # Immediately leasing again returns empty because next_attempt_at > now
    immediate_lease = repo.lease_batch(max_batch_size=1)
    assert len(immediate_lease) == 0


def test_recover_stale_leases(repo: StorageRepository) -> None:
    """Verifies that abandoned in_flight items are recovered after lease timeout."""
    rec = make_record()
    repo.enqueue_assessment_event(rec)

    # Lease item with short timeout
    batch = repo.lease_batch(max_batch_size=1, lease_timeout_seconds=0.0)
    assert len(batch) == 1

    # Immediately recover with 0s timeout
    recovered = repo.recover_stale_leases(timeout_seconds=0.0)
    assert recovered == 1

    # Item is available for lease again
    re_leased = repo.lease_batch(max_batch_size=1)
    assert len(re_leased) == 1
    assert re_leased[0][0].event_id == rec.event_id
    assert re_leased[0][1].attempt_count == 2  # incremented attempts


def test_retention_never_deletes_unacked_records(repo: StorageRepository) -> None:
    """Critical Invariant: Observations older than 90 days are deleted ONLY if acked."""
    old_ts = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    recent_ts = datetime.now(timezone.utc).isoformat()

    # 1. Old acked event (should be deleted)
    rec_old_acked = make_record(created_at=old_ts)
    repo.enqueue_assessment_event(rec_old_acked)
    repo.lease_batch(max_batch_size=1)
    repo.ack_events([rec_old_acked.event_id])

    # 2. Old unacked/pending event (MUST BE PRESERVED - FR-034/Decision 8)
    rec_old_pending = make_record(created_at=old_ts)
    repo.enqueue_assessment_event(rec_old_pending)

    # 3. Recent pending event (should be preserved)
    rec_recent = make_record(created_at=recent_ts)
    repo.enqueue_assessment_event(rec_recent)

    # Execute purge retention for 90 days
    purged_count = repo.purge_retention(retention_days=90)
    assert purged_count == 1  # Only rec_old_acked is purged

    # Verify rec_old_pending and rec_recent remain in database
    with repo.db.connect() as conn:
        remaining_ids = {
            row[0] for row in conn.execute("SELECT event_id FROM assessment_events;").fetchall()
        }

    assert rec_old_acked.event_id not in remaining_ids
    assert rec_old_pending.event_id in remaining_ids
    assert rec_recent.event_id in remaining_ids
