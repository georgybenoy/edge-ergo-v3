"""Payload serialization and validation for EdgeErgo telemetry synchronization.

Security & Privacy Boundary:
- Only allowlisted scalar and categorical metrics are serialized.
- Extra fields are strictly forbidden (extra="forbid").
- Landmark, face mesh, coordinate matrices, and image buffers cannot enter this schema.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from edge_ergo.storage.types import AssessmentEventRecord

# Canonical set of allowlisted keys for telemetry ingest
ALLOWLISTED_EVENT_KEYS = frozenset(
    {
        "event_id",
        "captured_at",
        "scoring_method",
        "scoring_version",
        "validity",
        "score",
        "neck_score",
        "trunk_score",
        "upper_arm_score",
        "guidance_codes",
        "software_version",
    }
)


class AssessmentEventPayload(BaseModel):
    """Client-side strict schema mirroring backend AssessmentEventIngestItem."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    captured_at: str
    scoring_method: str = Field(..., max_length=50)
    scoring_version: str = Field(..., max_length=20)
    validity: Literal["valid", "insufficient", "invalid"]
    score: float | None = Field(default=None, ge=1.0, le=15.0)
    neck_score: int | None = Field(default=None, ge=1, le=6)
    trunk_score: int | None = Field(default=None, ge=1, le=6)
    upper_arm_score: int | None = Field(default=None, ge=1, le=6)
    guidance_codes: list[str] = Field(default_factory=list)
    software_version: str = Field(..., max_length=32)

    def model_post_init(self, __context: Any) -> None:
        # Validate event_id is a valid UUID
        uuid.UUID(self.event_id)


class BatchIngestPayload(BaseModel):
    """Client-side batch payload matching backend BatchIngestRequest."""

    model_config = ConfigDict(extra="forbid")

    events: list[AssessmentEventPayload] = Field(..., max_length=100)


def serialize_event_record(record: AssessmentEventRecord) -> dict[str, Any]:
    """Serializes an AssessmentEventRecord into a strictly validated ingestion dictionary."""
    payload = AssessmentEventPayload(
        event_id=record.event_id,
        captured_at=record.captured_at,
        scoring_method=record.scoring_method,
        scoring_version=record.scoring_version,
        validity=record.validity,  # type: ignore[arg-type]
        score=record.score,
        neck_score=record.neck_score,
        trunk_score=record.trunk_score,
        upper_arm_score=record.upper_arm_score,
        guidance_codes=record.guidance_codes,
        software_version=record.software_version,
    )

    data = payload.model_dump()
    # Invariant: Output keys must strictly match ALLOWLISTED_EVENT_KEYS
    if set(data.keys()) != ALLOWLISTED_EVENT_KEYS:
        raise ValueError(f"Serialized event keys deviate from allowlist: {set(data.keys())}")

    return data


def build_batch_payload(records: list[AssessmentEventRecord]) -> dict[str, Any]:
    """Constructs a validated batch ingestion dictionary."""
    items = [serialize_event_record(r) for r in records]
    batch = BatchIngestPayload(events=[AssessmentEventPayload(**item) for item in items])
    return batch.model_dump()
