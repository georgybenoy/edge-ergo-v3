"""Data types for EdgeErgo V3 SQLite local storage and queue management."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SyncQueueState(str, Enum):
    """Lifecycle states of an observation item in the SQLite sync queue."""

    PENDING = "pending"
    IN_FLIGHT = "in_flight"
    ACKED = "acked"
    DEAD = "dead"


@dataclass(frozen=True)
class DeviceIdentity:
    """Locally persisted device identity metadata.

    Security Guarantee: The secret token is NEVER stored in this struct or in SQLite.
    It is stored exclusively in OS-protected credential storage (Windows Credential Manager).
    """

    device_id: str
    public_id: str
    api_base_url: str
    label: str
    organization_id: str
    enrolled_at: str


@dataclass(frozen=True)
class AssessmentEventRecord:
    """Locally persisted ergonomic assessment event record.

    Matches the backend ingestion allowlist exactly.
    Zero raw video frames, image arrays, or landmark coordinate matrices are stored.
    """

    event_id: str
    captured_at: str
    scoring_method: str
    scoring_version: str
    validity: str
    score: float | None
    neck_score: int | None
    trunk_score: int | None
    upper_arm_score: int | None
    guidance_codes: list[str]
    software_version: str
    postural_features: str | None = None  # JSON string of angle measurements
    created_at: str | None = None


@dataclass(frozen=True)
class SyncQueueItem:
    """Item state within the durable SQLite sync queue."""

    event_id: str
    state: SyncQueueState
    attempt_count: int
    next_attempt_at: str
    last_error_code: str | None = None
    leased_at: str | None = None


@dataclass(frozen=True)
class SyncStateInfo:
    """Cached summary of synchronization subsystem status."""

    last_success_at: str | None
    queue_depth: int
    last_heartbeat_at: str | None
