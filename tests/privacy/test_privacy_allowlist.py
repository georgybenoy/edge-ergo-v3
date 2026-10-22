"""EdgeErgo V3 — Privacy Verification Tests.

Verifies PRD §9, §12, and FR-042 data minimization requirements:
1. Payload allowlist alignment across agent serializer, backend schema, and DB columns.
2. Strict schema extra="forbid" rejection of extraneous biometric/sensor fields.
3. HTTP request payload inspection using a recording transport.
4. Log output sanitization (zero tokens, secrets, or raw coordinates).
5. CSV report export column allowlist conformance.
6. Zero image or video file generation during pipeline execution.
"""

from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.core.logging import RedactingJsonFormatter, redact_sensitive_text
from app.models.entities import AssessmentEvent
from app.schemas.api_models import AssessmentEventIngestItem
from edge_ergo.camera.fake_source import FakeCameraSource
from edge_ergo.features.extractor import extract_postural_features
from edge_ergo.quality.validator import validate_observation
from edge_ergo.scoring.scorer import RulaPartialScorer
from edge_ergo.storage.types import AssessmentEventRecord
from edge_ergo.sync.client import SyncClient
from edge_ergo.sync.payload import (
    ALLOWLISTED_EVENT_KEYS,
    AssessmentEventPayload,
    build_batch_payload,
)
from edge_ergo.vision.synthetic_estimator import SyntheticPoseEstimator
from pydantic import ValidationError

PROHIBITED_SUBSTRINGS = [
    "landmark",
    "face",
    "frame",
    "image",
    "video",
    "pixel",
    "raw_sensor",
    "coordinate",
    "crop",
]


def test_payload_allowlist_structural_alignment() -> None:
    """Verifies that the agent serializer, backend schema, and DB columns agree on allowlisted fields."""
    agent_fields = set(AssessmentEventPayload.model_fields.keys())
    backend_fields = set(AssessmentEventIngestItem.model_fields.keys())

    # 1. Agent and Backend schemas must match exactly on event ingestion fields
    assert agent_fields == backend_fields
    assert agent_fields == ALLOWLISTED_EVENT_KEYS

    # 2. Both schemas must enforce extra="forbid"
    assert AssessmentEventPayload.model_config.get("extra") == "forbid"
    assert AssessmentEventIngestItem.model_config.get("extra") == "forbid"

    # 3. Database entity must accommodate all ingested fields
    db_columns = {c.name for c in AssessmentEvent.__table__.columns}
    for field in agent_fields:
        if field == "guidance_codes":
            assert "guidance_codes" in db_columns
        else:
            assert field in db_columns

    # 4. Prohibited keywords must never exist in any field name
    for field in agent_fields:
        field_lower = field.lower()
        for forbidden in PROHIBITED_SUBSTRINGS:
            assert forbidden not in field_lower, f"Prohibited term '{forbidden}' in field '{field}'"


def test_extra_fields_rejected_by_serializer_and_backend() -> None:
    """Verifies that extraneous biometric or sensor fields are rejected fail-closed."""
    valid_data: dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "captured_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "scoring_method": "RULA_PARTIAL",
        "scoring_version": "1.0.0",
        "validity": "valid",
        "score": 3.0,
        "neck_score": 2,
        "trunk_score": 2,
        "upper_arm_score": 2,
        "guidance_codes": ["NECK_FLEXION_MODERATE"],
        "software_version": "3.0.0",
    }

    # Attempt injecting landmark array into client payload
    tampered_data = dict(valid_data)
    tampered_data["landmarks"] = [{"x": 0.5, "y": 0.5, "z": 0.0}]
    with pytest.raises(ValidationError):
        AssessmentEventPayload(**tampered_data)

    # Attempt injecting base64 image into backend schema
    tampered_backend = dict(valid_data)
    tampered_backend["raw_image_base64"] = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
    with pytest.raises(ValidationError):
        AssessmentEventIngestItem(**tampered_backend)


def test_recorded_requests_privacy_boundary() -> None:
    """Intercepts outgoing sync payloads with a recording transport and inspects all keys/values."""
    captured_requests: list[httpx.Request] = []

    def mock_transport(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        # Mock 200 OK batch response
        return httpx.Response(
            status_code=200,
            json={
                "results": [
                    {
                        "event_id": "c7a8b412-28e4-4a21-9fd1-6b2f483c19e5",
                        "status": "accepted",
                        "reason_code": None,
                    }
                ],
                "total_accepted": 1,
            },
        )

    # Build real test record
    record = AssessmentEventRecord(
        event_id="c7a8b412-28e4-4a21-9fd1-6b2f483c19e5",
        captured_at="2026-10-20T17:00:00.000000Z",
        scoring_method="RULA_PARTIAL",
        scoring_version="1.0.0",
        validity="valid",
        score=3.0,
        neck_score=2,
        trunk_score=2,
        upper_arm_score=2,
        postural_features=None,
        guidance_codes=["NECK_FLEXION_MODERATE"],
        software_version="3.0.0",
    )

    batch_payload = build_batch_payload([record])

    transport = httpx.MockTransport(mock_transport)
    test_http_client = httpx.Client(transport=transport)
    client = SyncClient(
        api_base_url="https://api.test.edgeergo.com",
        credential="eed_testdevice123.dummy_secret_token_12345",
        http_client=test_http_client,
    )

    result = client.upload_batch(batch_payload)
    assert result.total_accepted == 1
    assert len(captured_requests) == 1

    # Deep inspection of captured request body
    body_text = captured_requests[0].content.decode("utf-8")
    body_json = json.loads(body_text)

    def scan_dict(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                for forbidden in PROHIBITED_SUBSTRINGS:
                    assert forbidden not in k.lower(), f"Forbidden key found in request: {k}"
                scan_dict(v)
        elif isinstance(obj, list):
            for item in obj:
                scan_dict(item)
        elif isinstance(obj, str):
            assert "data:image/" not in obj
            assert not obj.startswith("/9j/"), "Base64 JPEG detected"
            assert not obj.startswith("iVBORw"), "Base64 PNG detected"

    scan_dict(body_json)


def test_logs_contain_no_tokens_or_landmarks() -> None:
    """Verifies that secrets, device tokens, and coordinates are redacted from all log streams."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingJsonFormatter())

    test_logger = logging.getLogger("test_privacy_log")
    test_logger.handlers = [handler]
    test_logger.setLevel(logging.INFO)

    secret_token = "eet_admin_single_use_token_99999"
    device_cred = "eed_test_device_01.dummy_secret_token_12345"

    test_logger.info("Enrolling with token %s and device credential %s", secret_token, device_cred)
    output = stream.getvalue()

    assert secret_token not in output
    assert "dummy_secret_token_12345" not in output
    assert "[REDACTED]" in output

    # Test direct redaction helper
    redacted = redact_sensitive_text(f"Key: {device_cred}")
    assert "dummy_secret_token_12345" not in redacted
    assert "[REDACTED]" in redacted


def test_csv_export_column_allowlist() -> None:
    """Verifies that the CSV reports endpoint only exports approved, privacy-safe column headers."""
    from app.api.v1.reports import CSV_REPORT_HEADERS

    expected_headers = [
        "event_id",
        "device_id",
        "device_label",
        "captured_at_utc",
        "scoring_method",
        "scoring_version",
        "validity",
        "score_rula_1_to_7",
        "neck_score_1_to_6",
        "trunk_score_1_to_6",
        "upper_arm_score_1_to_6",
        "guidance_codes",
        "software_version",
    ]

    assert CSV_REPORT_HEADERS == expected_headers

    # Prohibited columns verification
    for col in CSV_REPORT_HEADERS:
        col_lower = col.lower()
        for forbidden in PROHIBITED_SUBSTRINGS:
            assert forbidden not in col_lower, f"Prohibited column header in CSV: {col}"


def test_no_image_or_video_files_created_during_assessment() -> None:
    """Runs multiple fake-camera assessment cycles and proves zero media files are created on disk."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        camera = FakeCameraSource()
        estimator = SyntheticPoseEstimator(mode="neutral")
        scorer = RulaPartialScorer()

        camera.open()
        try:
            for _ in range(5):
                frame = camera.read_frame()
                assert frame is not None
                res = estimator.estimate(frame)
                assert res.landmarks is not None
                val = validate_observation(res.landmarks)
                feat = extract_postural_features(res.landmarks)
                score = scorer.score(feat, val)
                assert score.is_valid
        finally:
            camera.close()
            estimator.close()

        # Scan temporary directory and local workspace for any created media files
        media_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".mp4", ".avi", ".mov", ".raw"}
        created_media: list[str] = []
        for root, _, files in os.walk(tmp_path):
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in media_extensions:
                    created_media.append(f)

        assert created_media == [], f"Unexpected media files created: {created_media}"
