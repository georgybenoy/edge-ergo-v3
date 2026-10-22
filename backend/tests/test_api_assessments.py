"""EdgeErgo V3 — Tests for Assessment Batch Ingestion, Idempotency, and Privacy Scoping."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AssessmentEvent, Device, Organization, OrganizationMember

if TYPE_CHECKING:
    from tests.conftest import TestJWTSigner

ORG_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ORG_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

USER_ADMIN_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ADMIN_B = uuid.UUID("33333333-3333-3333-3333-333333333333")

DEVICE_A_ID = uuid.UUID("d1111111-1111-1111-1111-111111111111")
PUB_ID_A = "pub_workstation_a_ingest"
SECRET_A = "secret_workstation_a_1234567890123"


@pytest.fixture
async def seeded_ingest_db(async_test_session: AsyncSession) -> AsyncSession:
    """Seeds test organizations, users, and an active device in Org A."""
    await async_test_session.execute(
        text(
            """
            INSERT INTO auth.users (id, email) VALUES
                (:u1, 'admin_a@example.com'),
                (:u2, 'admin_b@example.com');
            """
        ),
        {"u1": USER_ADMIN_A, "u2": USER_ADMIN_B},
    )

    org_a = Organization(id=ORG_A_ID, name="Organization A", slug="org-a")
    org_b = Organization(id=ORG_B_ID, name="Organization B", slug="org-b")
    async_test_session.add_all([org_a, org_b])

    m1 = OrganizationMember(organization_id=ORG_A_ID, user_id=USER_ADMIN_A, role="admin")
    m2 = OrganizationMember(organization_id=ORG_B_ID, user_id=USER_ADMIN_B, role="admin")
    async_test_session.add_all([m1, m2])

    device_a = Device(
        id=DEVICE_A_ID,
        organization_id=ORG_A_ID,
        label="Workstation A Ingest",
        status="active",
        public_id=PUB_ID_A,
        credential_hash=hashlib.sha256(SECRET_A.encode("utf-8")).hexdigest(),
        credential_version=1,
    )
    async_test_session.add(device_a)

    await async_test_session.commit()
    return async_test_session


@pytest.mark.asyncio
async def test_idempotent_batch_ingestion(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_ingest_db: AsyncSession,
) -> None:
    """Verifies batch ingestion succeeds and re-sending identical batch reports duplicates."""
    device_cred = f"eed_{PUB_ID_A}.{SECRET_A}"
    now = datetime.utcnow()

    event_1 = {
        "event_id": str(uuid.uuid4()),
        "captured_at": now.isoformat(),
        "scoring_method": "rula_v1_screening",
        "scoring_version": "1.0.0",
        "validity": "valid",
        "score": 3.5,
        "neck_score": 2,
        "trunk_score": 3,
        "upper_arm_score": 2,
        "guidance_codes": ["FORWARD_HEAD"],
        "software_version": "3.0.0",
    }
    event_2 = {
        "event_id": str(uuid.uuid4()),
        "captured_at": (now - timedelta(minutes=5)).isoformat(),
        "scoring_method": "rula_v1_screening",
        "scoring_version": "1.0.0",
        "validity": "insufficient",
        "score": None,
        "neck_score": None,
        "trunk_score": None,
        "upper_arm_score": None,
        "guidance_codes": ["OCCLUDED_SHOULDER"],
        "software_version": "3.0.0",
    }

    # First send -> Both accepted
    res1 = await async_client.post(
        "/api/v1/assessments/batch",
        headers={"Authorization": f"Bearer {device_cred}"},
        json={"events": [event_1, event_2]},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["total_accepted"] == 2
    assert data1["total_duplicates"] == 0
    assert data1["total_rejected"] == 0

    # Verify rows in DB
    db_count1 = (
        await seeded_ingest_db.execute(select(func.count(AssessmentEvent.event_id)))
    ).scalar()
    assert db_count1 == 2

    # Second send with identical batch -> Marked duplicates, no new rows added
    res2 = await async_client.post(
        "/api/v1/assessments/batch",
        headers={"Authorization": f"Bearer {device_cred}"},
        json={"events": [event_1, event_2]},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["total_accepted"] == 0
    assert data2["total_duplicates"] == 2
    assert data2["total_rejected"] == 0

    db_count2 = (
        await seeded_ingest_db.execute(select(func.count(AssessmentEvent.event_id)))
    ).scalar()
    assert db_count2 == 2


@pytest.mark.asyncio
async def test_unknown_field_rejection_forbids_raw_landmarks(
    async_client: AsyncClient,
    seeded_ingest_db: AsyncSession,
) -> None:
    """Verifies that attempting to submit forbidden raw landmarks triggers 422 VALIDATION_ERROR."""
    device_cred = f"eed_{PUB_ID_A}.{SECRET_A}"
    now = datetime.utcnow()

    # Payload includes illegal raw landmark array
    malicious_event = {
        "event_id": str(uuid.uuid4()),
        "captured_at": now.isoformat(),
        "scoring_method": "rula_v1_screening",
        "scoring_version": "1.0.0",
        "validity": "valid",
        "score": 3.0,
        "software_version": "3.0.0",
        "raw_landmarks": [{"x": 0.5, "y": 0.5, "z": 0.1}],  # Strictly forbidden!
    }

    res = await async_client.post(
        "/api/v1/assessments/batch",
        headers={"Authorization": f"Bearer {device_cred}"},
        json={"events": [malicious_event]},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "raw_landmarks" in res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_partial_bad_batch_handling(
    async_client: AsyncClient,
    seeded_ingest_db: AsyncSession,
) -> None:
    """Verifies that a single bad event does not poison the batch; valid events are saved."""
    device_cred = f"eed_{PUB_ID_A}.{SECRET_A}"
    now = datetime.utcnow()

    bad_timestamp_event = {
        "event_id": str(uuid.uuid4()),
        "captured_at": (now - timedelta(days=200)).isoformat(),  # > 90 days in past
        "scoring_method": "rula_v1_screening",
        "scoring_version": "1.0.0",
        "validity": "valid",
        "score": 4.0,
        "software_version": "3.0.0",
    }
    good_event = {
        "event_id": str(uuid.uuid4()),
        "captured_at": now.isoformat(),
        "scoring_method": "rula_v1_screening",
        "scoring_version": "1.0.0",
        "validity": "valid",
        "score": 2.5,
        "software_version": "3.0.0",
    }

    res = await async_client.post(
        "/api/v1/assessments/batch",
        headers={"Authorization": f"Bearer {device_cred}"},
        json={"events": [bad_timestamp_event, good_event]},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_accepted"] == 1
    assert data["total_rejected"] == 1

    # Rejected event includes reason code
    bad_res = next(r for r in data["results"] if r["event_id"] == bad_timestamp_event["event_id"])
    assert bad_res["status"] == "rejected"
    assert bad_res["reason_code"] == "TIMESTAMP_OUT_OF_RANGE"


@pytest.mark.asyncio
async def test_oversize_batch_rejected(
    async_client: AsyncClient,
    seeded_ingest_db: AsyncSession,
) -> None:
    """Verifies batches exceeding MAX_BATCH_SIZE (100) are rejected with 422."""
    device_cred = f"eed_{PUB_ID_A}.{SECRET_A}"
    now = datetime.utcnow()

    oversized_events = [
        {
            "event_id": str(uuid.uuid4()),
            "captured_at": now.isoformat(),
            "scoring_method": "rula_v1_screening",
            "scoring_version": "1.0.0",
            "validity": "valid",
            "score": 2.0,
            "software_version": "3.0.0",
        }
        for _ in range(101)  # 101 > 100
    ]

    res = await async_client.post(
        "/api/v1/assessments/batch",
        headers={"Authorization": f"Bearer {device_cred}"},
        json={"events": oversized_events},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_cross_tenant_assessment_isolation(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_ingest_db: AsyncSession,
) -> None:
    """Verifies that member of Org B cannot see Org A assessments."""
    admin_a_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_A))
    admin_b_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_B))

    # Ingest event into Org A
    now = datetime.utcnow()
    event_id = uuid.uuid4()
    event = AssessmentEvent(
        device_id=DEVICE_A_ID,
        event_id=event_id,
        organization_id=ORG_A_ID,
        captured_at=now,
        scoring_method="rula_v1_screening",
        scoring_version="1.0.0",
        validity="valid",
        score=4.0,
        guidance_codes=["FORWARD_HEAD"],
        software_version="3.0.0",
    )
    seeded_ingest_db.add(event)
    await seeded_ingest_db.commit()

    # Admin A sees the event
    res_a = await async_client.get(
        "/api/v1/assessments",
        headers={"Authorization": f"Bearer {admin_a_token}"},
    )
    assert res_a.status_code == 200
    assert res_a.json()["total"] == 1
    assert res_a.json()["items"][0]["event_id"] == str(event_id)

    # Admin B sees 0 events
    res_b = await async_client.get(
        "/api/v1/assessments",
        headers={"Authorization": f"Bearer {admin_b_token}"},
    )
    assert res_b.status_code == 200
    assert res_b.json()["total"] == 0
    assert res_b.json()["items"] == []
