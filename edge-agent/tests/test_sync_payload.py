"""Tests verifying telemetry payload serialization, allowlist conformance, and privacy boundary."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from edge_ergo.storage.types import AssessmentEventRecord
from edge_ergo.sync.payload import (
    ALLOWLISTED_EVENT_KEYS,
    AssessmentEventPayload,
    build_batch_payload,
    serialize_event_record,
)


def test_payload_keys_strictly_equal_allowlist() -> None:
    """Verifies that the serialized payload contains exactly and only the allowlisted keys."""
    event_id = str(uuid.uuid4())
    record = AssessmentEventRecord(
        event_id=event_id,
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

    data = serialize_event_record(record)
    assert set(data.keys()) == ALLOWLISTED_EVENT_KEYS

    expected_backend_keys = {
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
    assert set(data.keys()) == expected_backend_keys


def test_extra_fields_strictly_forbidden() -> None:
    """Privacy Invariant: Prohibits passing landmarks, image pixels, or biometric fields."""
    valid_base: dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "captured_at": "2026-10-20T12:00:00Z",
        "scoring_method": "rula_partial",
        "scoring_version": "1.0.0",
        "validity": "valid",
        "software_version": "3.0.0",
    }

    # 1. Attaching landmark coordinates must fail validation
    with pytest.raises(ValidationError):
        AssessmentEventPayload(
            **valid_base,
            landmarks=[{"x": 0.5, "y": 0.5, "z": 0.0}],  # type: ignore[call-arg]
        )

    # 2. Attaching raw frames must fail validation
    with pytest.raises(ValidationError):
        AssessmentEventPayload(
            **valid_base,
            frame_buffer=b"\x00\x01\x02",  # type: ignore[call-arg]
        )

    # 3. Attaching arbitrary extra fields must fail validation
    with pytest.raises(ValidationError):
        AssessmentEventPayload(
            **valid_base,
            face_features={"eyes": "open"},  # type: ignore[call-arg]
        )


def test_invalid_uuid_rejected() -> None:
    """Verifies that non-UUID event_id is rejected."""
    with pytest.raises(ValidationError):
        AssessmentEventPayload(
            event_id="not-a-valid-uuid",
            captured_at="2026-10-20T12:00:00Z",
            scoring_method="rula_partial",
            scoring_version="1.0.0",
            validity="valid",
            software_version="3.0.0",
        )


def test_batch_payload_builder() -> None:
    """Verifies batch payload aggregation."""
    rec1 = AssessmentEventRecord(
        event_id=str(uuid.uuid4()),
        captured_at="2026-10-20T12:00:00Z",
        scoring_method="rula_partial",
        scoring_version="1.0.0",
        validity="valid",
        score=1.0,
        neck_score=1,
        trunk_score=1,
        upper_arm_score=1,
        postural_features=None,
        guidance_codes=[],
        software_version="3.0.0",
        created_at="2026-10-20T12:00:00Z",
    )
    batch = build_batch_payload([rec1])
    assert "events" in batch
    assert len(batch["events"]) == 1
    assert batch["events"][0]["event_id"] == rec1.event_id
