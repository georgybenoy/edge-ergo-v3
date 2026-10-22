"""EdgeErgo V3 — Tests for Dashboard Analytics, CSV Reports, and Audit Trail."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AssessmentEvent, Device, Organization, OrganizationMember
from app.services.audit import record_audit_event

if TYPE_CHECKING:
    from tests.conftest import TestJWTSigner

ORG_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ORG_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

USER_ADMIN_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ADMIN_B = uuid.UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
async def seeded_analytics_db(async_test_session: AsyncSession) -> AsyncSession:
    """Seeds test organizations, workstation devices, and assessment records."""
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

    now = datetime.utcnow()

    # Active workstation with formula-like label to test CSV injection defense
    dev1 = Device(
        id=uuid.UUID("d1111111-1111-1111-1111-111111111111"),
        organization_id=ORG_A_ID,
        label="=SUM(1+1)",  # Malicious formula name
        status="active",
        public_id="pub_inj_01",
        credential_hash="dummy_hash_01",
        last_seen_at=now,
    )
    async_test_session.add(dev1)
    await async_test_session.flush()

    # Assessment events: 2 valid (scores 3.0 and 5.0) -> expected avg 4.0
    ev1 = AssessmentEvent(
        device_id=dev1.id,
        event_id=uuid.uuid4(),
        organization_id=ORG_A_ID,
        captured_at=now,
        scoring_method="rula_v1_screening",
        scoring_version="1.0.0",
        validity="valid",
        score=3.0,
        neck_score=2,
        trunk_score=3,
        upper_arm_score=2,
        guidance_codes=["FORWARD_HEAD"],
        software_version="3.0.0",
    )
    ev2 = AssessmentEvent(
        device_id=dev1.id,
        event_id=uuid.uuid4(),
        organization_id=ORG_A_ID,
        captured_at=now - timedelta(minutes=10),
        scoring_method="rula_v1_screening",
        scoring_version="1.0.0",
        validity="valid",
        score=5.0,
        neck_score=3,
        trunk_score=4,
        upper_arm_score=3,
        guidance_codes=["TRUNK_TWIST"],
        software_version="3.0.0",
    )
    ev3 = AssessmentEvent(
        device_id=dev1.id,
        event_id=uuid.uuid4(),
        organization_id=ORG_A_ID,
        captured_at=now - timedelta(minutes=20),
        scoring_method="rula_v1_screening",
        scoring_version="1.0.0",
        validity="insufficient",
        score=None,
        software_version="3.0.0",
    )
    async_test_session.add_all([ev1, ev2, ev3])

    # Record sample audit event
    await record_audit_event(
        session=async_test_session,
        organization_id=ORG_A_ID,
        action="test.action",
        target_type="test",
        target_id="1",
        actor_user_id=USER_ADMIN_A,
        metadata={"info": "safe_data", "password": "should_be_omitted"},
    )

    await async_test_session.commit()
    return async_test_session


@pytest.mark.asyncio
async def test_dashboard_summary_indicators(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_analytics_db: AsyncSession,
) -> None:
    """Verifies aggregated metrics and average RULA calculation."""
    admin_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_A))

    res = await async_client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_assessments"] == 3
    assert data["valid_count"] == 2
    assert data["insufficient_count"] == 1
    assert data["active_devices_count"] == 1
    assert data["online_devices_count"] == 1

    # Mean of 3.0 and 5.0 is 4.0
    rula_metric = data["average_rula_score"]
    assert rula_metric["value"] == 4.0
    assert rula_metric["sample_count"] == 2
    assert rula_metric["reason"] is None


@pytest.mark.asyncio
async def test_dashboard_summary_with_zero_valid_observations(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_analytics_db: AsyncSession,
) -> None:
    """Verifies average RULA returns explicit null and reason when no valid data exists."""
    admin_b_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_B))

    res = await async_client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {admin_b_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["valid_count"] == 0
    rula_metric = data["average_rula_score"]
    assert rula_metric["value"] is None
    assert rula_metric["sample_count"] == 0
    assert rula_metric["reason"] is not None


@pytest.mark.asyncio
async def test_csv_export_injection_escaping_and_headers(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_analytics_db: AsyncSession,
) -> None:
    """Verifies CSV export streams valid CSV and escapes cells starting with formula characters."""
    admin_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_A))

    res = await async_client.get(
        "/api/v1/reports/assessments.csv",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]

    csv_text = res.text
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    # 1. Header row verification
    header = rows[0]
    assert "score_rula_1_to_7" in header
    assert "captured_at_utc" in header

    # 2. Formula injection escaping verification
    # Find dev_label column
    label_idx = header.index("device_label")
    for r in rows[1:]:
        # Must be escaped with leading single quote: '=SUM(1+1)
        assert r[label_idx] == "'=SUM(1+1)"


@pytest.mark.asyncio
async def test_audit_events_endpoint_and_secret_scrubbing(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_analytics_db: AsyncSession,
) -> None:
    """Verifies audit events query returns logs without prohibited secret keys."""
    admin_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_A))

    res = await async_client.get(
        "/api/v1/audit-events",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    item = data["items"][0]
    assert item["action"] == "test.action"
    # Prohibited key 'password' was scrubbed by record_audit_event
    assert "password" not in item["metadata"]
    assert item["metadata"]["info"] == "safe_data"
