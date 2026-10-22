#!/usr/bin/env python3
# ruff: noqa: BLE001
"""EdgeErgo V3 — Developer Script: Send Real Test Telemetry Events.

Sends realistic ergonomic telemetry batches to a running EdgeErgo hosted API
instance using either:
1. An existing enrolled device credential (eed_<public_id>.<secret>), OR
2. A single-use enrollment token (eet_...) to enroll on the fly and send events.

Strictly adheres to real API contracts with zero raw landmark/image ingestion.

Usage:
    python scripts/dev_send_test_event.py --credential "eed_<pub>.<secret>" --api-url "http://localhost:8000" --count 5
    python scripts/dev_send_test_event.py --token "eet_<token>" --api-url "http://localhost:8000" --count 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Add edge-agent to sys.path
agent_root = Path(__file__).resolve().parent.parent / "edge-agent"
if str(agent_root) not in sys.path:
    sys.path.insert(0, str(agent_root))

from edge_ergo.storage.types import AssessmentEventRecord
from edge_ergo.sync.client import validate_api_base_url
from edge_ergo.sync.payload import serialize_event_record


def enroll_with_token(api_url: str, token: str) -> str:
    """Enrolls device on the fly and returns the issued credential string."""
    clean_url = validate_api_base_url(api_url)
    url = f"{clean_url}/api/v1/devices/enroll"
    payload = {
        "token": token.strip(),
        "label": "Dev Script Workstation",
        "agent_version": "3.0.0-dev",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "EdgeErgo-DevTest/3.0.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            cred = str(body["credential"])
            print(f"[OK] Enrolled test device: public_id={body.get('public_id')}")
            return cred
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8")
        print(f"[ERROR] Enrollment failed ({exc.code}): {err_body}", file=sys.stderr)
        raise


def send_heartbeat(api_url: str, credential: str) -> None:
    """Sends a device heartbeat to mark the device active and report queue depth."""
    clean_url = validate_api_base_url(api_url)
    url = f"{clean_url}/api/v1/devices/heartbeat"
    payload = {
        "agent_version": "3.0.0-dev",
        "queue_depth": 0,
        "state": "active_monitoring",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {credential}",
            "Content-Type": "application/json",
            "User-Agent": "EdgeErgo-DevTest/3.0.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            print(f"[OK] Device Heartbeat sent successfully: {body}")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8")
        print(f"[ERROR] Heartbeat failed ({exc.code}): {err_body}", file=sys.stderr)
        raise


def build_events(count: int, mode: str) -> list[dict[str, object]]:
    """Builds valid, schema-compliant telemetry observation payloads using real serialization."""
    events: list[dict[str, object]] = []
    now = datetime.now(UTC)

    for i in range(count):
        event_id = str(uuid.uuid4())
        # Alternate or select validity
        if mode == "mixed":
            validity = "valid" if i % 3 != 2 else ("insufficient" if i % 2 == 0 else "invalid")
        else:
            validity = mode

        if validity == "valid":
            score = 3.0 + (i % 3)
            neck = 2 + (i % 2)
            trunk = 2 + (i % 3)
            arm = 2 + (i % 2)
            guidance = ["GUID_NECK_FLEX_01", "GUID_TRUNK_INCL_01"] if score > 3 else ["GENERAL_GOOD_POSTURE"]
        else:
            # PRD & API contract rule: invalid or insufficient rows NEVER carry a score
            score = None
            neck = None
            trunk = None
            arm = None
            guidance = ["OCCLUSION_TORSO_BLOCKED"] if validity == "insufficient" else ["POOR_LIGHTING_CONTRAST"]

        rec = AssessmentEventRecord(
            event_id=event_id,
            captured_at=now.isoformat(),
            scoring_method="rula_partial",
            scoring_version="1.0.0",
            validity=validity,
            score=score,
            neck_score=neck,
            trunk_score=trunk,
            upper_arm_score=arm,
            postural_features=None,
            guidance_codes=guidance,
            software_version="3.0.0-dev",
            created_at=now.isoformat(),
        )
        events.append(serialize_event_record(rec))

    return events


def send_batch(api_url: str, credential: str, events: list[dict[str, object]]) -> dict[str, object]:
    """Ingests a telemetry batch via POST /api/v1/assessments/batch."""
    clean_url = validate_api_base_url(api_url)
    url = f"{clean_url}/api/v1/assessments/batch"
    payload = {"events": events}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {credential}",
            "Content-Type": "application/json",
            "User-Agent": "EdgeErgo-DevTest/3.0.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body: dict[str, object] = json.loads(resp.read().decode("utf-8"))
            return body
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8")
        print(f"[ERROR] Batch ingestion failed ({exc.code}): {err_body}", file=sys.stderr)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send real telemetry events using a genuine enrolled EdgeErgo workstation credential or token."
    )
    parser.add_argument(
        "--credential",
        default=os.environ.get("DEVICE_CREDENTIAL"),
        help="Device credential in format eed_<public_id>.<secret>. Can also be set via DEVICE_CREDENTIAL env.",
    )
    parser.add_argument(
        "--token",
        "--enroll-token",
        dest="token",
        help="Single-use enrollment token (eet_...) to enroll a new test device before sending telemetry.",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("API_URL", "http://localhost:8000"),
        help="Base URL of the EdgeErgo hosted backend API (default: http://localhost:8000).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of assessment events to generate and send in the batch (default: 5).",
    )
    parser.add_argument(
        "--validity",
        choices=["valid", "invalid", "insufficient", "mixed"],
        default="mixed",
        help="Validity mode of generated events (default: mixed).",
    )
    parser.add_argument(
        "--skip-heartbeat",
        action="store_true",
        help="Skip sending device heartbeat before telemetry batch.",
    )

    args = parser.parse_args()

    credential = args.credential
    if not credential and args.token:
        try:
            credential = enroll_with_token(args.api_url, args.token)
        except Exception:
            return 1

    if not credential:
        print("=" * 70, file=sys.stderr)
        print("ERROR: Missing --credential or --token argument.", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print("To send telemetry, provide either an existing credential or an enrollment token:", file=sys.stderr)
        print("  Option A: python scripts/dev_send_test_event.py --token 'eet_...'", file=sys.stderr)
        print("  Option B: python scripts/dev_send_test_event.py --credential 'eed_<pub>.<secret>'", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1

    if not credential.startswith("eed_") or "." not in credential:
        print("ERROR: Credential format must be eed_<public_id>.<secret>.", file=sys.stderr)
        return 1

    print(f"Connecting to EdgeErgo API at: {args.api_url}")

    # 1. Send Heartbeat
    if not args.skip_heartbeat:
        try:
            send_heartbeat(args.api_url, credential)
        except Exception:
            return 1

    # 2. Build & Send Batch
    events = build_events(args.count, args.validity)
    print(f"Submitting batch of {len(events)} telemetry events...")
    try:
        resp = send_batch(args.api_url, credential, events)
        print("[OK] Ingestion batch response:")
        print(json.dumps(resp, indent=2))
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
