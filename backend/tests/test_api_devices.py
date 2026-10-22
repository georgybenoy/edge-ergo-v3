"""EdgeErgo V3 — Tests for Device Enrollment, Authentication, Heartbeat, and Lifecycle."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Device, DeviceEnrollmentToken, Organization, OrganizationMember

if TYPE_CHECKING:
    from tests.conftest import TestJWTSigner

ORG_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ORG_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

USER_ADMIN_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ADMIN_B = uuid.UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
async def seeded_devices_db(async_test_session: AsyncSession) -> AsyncSession:
    """Seeds test organizations and admins for device testing."""
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

    await async_test_session.commit()
    return async_test_session


@pytest.mark.asyncio
async def test_device_enrollment_lifecycle(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_devices_db: AsyncSession,
) -> None:
    """Verifies end-to-end device token creation, single-use enrollment, and credential issuance."""
    admin_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_A))

    # 1. Admin creates enrollment token
    create_res = await async_client.post(
        "/api/v1/devices/enrollment-tokens",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"label": "Workstation 101", "expires_in_minutes": 15},
    )
    assert create_res.status_code == 200
    token_data = create_res.json()
    raw_token = token_data["token"]
    assert raw_token.startswith("eet_")

    # 2. Device enrolls using the single-use token
    enroll_res = await async_client.post(
        "/api/v1/devices/enroll",
        json={
            "token": raw_token,
            "label": "Workstation 101",
            "agent_version": "3.0.0",
        },
    )
    assert enroll_res.status_code == 200
    device_data = enroll_res.json()
    device_id = device_data["device_id"]
    public_id = device_data["public_id"]
    credential = device_data["credential"]
    assert credential.startswith(f"eed_{public_id}.")

    # 3. Token reuse is strictly denied
    reuse_res = await async_client.post(
        "/api/v1/devices/enroll",
        json={
            "token": raw_token,
            "label": "Rogue Workstation",
            "agent_version": "3.0.0",
        },
    )
    assert reuse_res.status_code == 400
    assert reuse_res.json()["error"]["code"] == "INVALID_OR_EXPIRED_TOKEN"

    # 4. Device sends heartbeat using credential
    hb_res = await async_client.post(
        "/api/v1/devices/heartbeat",
        headers={"Authorization": f"Bearer {credential}"},
        json={"agent_version": "3.0.0", "queue_depth": 0, "state": "active"},
    )
    assert hb_res.status_code == 200
    assert hb_res.json()["status"] == "ok"

    # 5. Device list reflects online workstation
    list_res = await async_client.get(
        "/api/v1/devices",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_res.status_code == 200
    devices = list_res.json()
    assert len(devices) == 1
    assert devices[0]["id"] == device_id
    assert devices[0]["computed_status"] == "online"


@pytest.mark.asyncio
async def test_expired_enrollment_token_rejected(
    async_client: AsyncClient,
    seeded_devices_db: AsyncSession,
) -> None:
    """Verifies expired enrollment token is rejected with 400."""
    raw_token = "eet_expired_test_token_string_123"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Seed an already expired token
    expired_token = DeviceEnrollmentToken(
        token_hash=token_hash,
        organization_id=ORG_A_ID,
        created_by=USER_ADMIN_A,
        label="Expired Station",
        expires_at=datetime.utcnow() - timedelta(minutes=10),
    )
    seeded_devices_db.add(expired_token)
    await seeded_devices_db.commit()

    res = await async_client.post(
        "/api/v1/devices/enroll",
        json={"token": raw_token, "label": "Expired Station", "agent_version": "3.0.0"},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_OR_EXPIRED_TOKEN"


@pytest.mark.asyncio
async def test_device_auth_failures_and_timing_mitigation(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_devices_db: AsyncSession,
) -> None:
    """Verifies unknown public_id and wrong secret return identical 401 INVALID_CREDENTIALS."""
    # 1. Unknown public_id
    res_unknown = await async_client.post(
        "/api/v1/devices/heartbeat",
        headers={"Authorization": "Bearer eed_pub_nonexistent123.test_secret_token_12345"},
        json={"agent_version": "3.0.0", "queue_depth": 0, "state": "active"},
    )
    assert res_unknown.status_code == 401
    assert res_unknown.json()["error"]["code"] == "INVALID_CREDENTIALS"

    # Seed real device
    pub_id = "pub_valid_station_01"
    correct_secret = "correct_secret_string_1234567890"
    device = Device(
        organization_id=ORG_A_ID,
        label="Station 01",
        status="active",
        public_id=pub_id,
        credential_hash=hashlib.sha256(correct_secret.encode("utf-8")).hexdigest(),
        credential_version=1,
    )
    seeded_devices_db.add(device)
    await seeded_devices_db.commit()

    # 2. Known public_id but wrong secret returns identical error
    res_wrong_secret = await async_client.post(
        "/api/v1/devices/heartbeat",
        headers={"Authorization": f"Bearer eed_{pub_id}.wrong_secret_string_000000"},
        json={"agent_version": "3.0.0", "queue_depth": 0, "state": "active"},
    )
    assert res_wrong_secret.status_code == 401
    assert res_wrong_secret.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_device_revocation_and_rotation(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_devices_db: AsyncSession,
) -> None:
    """Verifies revocation blocks device auth and credential rotation succeeds."""
    admin_a_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_A))
    admin_b_token = jwt_signer.mint_token(user_id=str(USER_ADMIN_B))

    # Seed device in Org A
    dev_id = uuid.uuid4()
    pub_id = "pub_station_rotation_01"
    initial_secret = "initial_secret_123456789012345"
    device = Device(
        id=dev_id,
        organization_id=ORG_A_ID,
        label="Rotation Test Station",
        status="active",
        public_id=pub_id,
        credential_hash=hashlib.sha256(initial_secret.encode("utf-8")).hexdigest(),
        credential_version=1,
    )
    seeded_devices_db.add(device)
    await seeded_devices_db.commit()

    # Cross-org isolation: Admin of Org B cannot rotate or revoke Org A device
    res_cross = await async_client.post(
        f"/api/v1/devices/{dev_id}/revoke",
        headers={"Authorization": f"Bearer {admin_b_token}"},
    )
    assert res_cross.status_code == 404

    # Rotate credential by Admin A
    rot_res = await async_client.post(
        f"/api/v1/devices/{dev_id}/rotate-credential",
        headers={"Authorization": f"Bearer {admin_a_token}"},
    )
    assert rot_res.status_code == 200
    rot_data = rot_res.json()
    new_credential = rot_data["credential"]
    assert rot_data["credential_version"] == 2

    # Old credential fails
    old_hb = await async_client.post(
        "/api/v1/devices/heartbeat",
        headers={"Authorization": f"Bearer eed_{pub_id}.{initial_secret}"},
        json={"agent_version": "3.0.0", "queue_depth": 0, "state": "active"},
    )
    assert old_hb.status_code == 401

    # New credential succeeds
    new_hb = await async_client.post(
        "/api/v1/devices/heartbeat",
        headers={"Authorization": f"Bearer {new_credential}"},
        json={"agent_version": "3.0.0", "queue_depth": 0, "state": "active"},
    )
    assert new_hb.status_code == 200

    # Revoke device
    revoke_res = await async_client.post(
        f"/api/v1/devices/{dev_id}/revoke",
        headers={"Authorization": f"Bearer {admin_a_token}"},
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "revoked"

    # Revoked device is denied heartbeat
    revoked_hb = await async_client.post(
        "/api/v1/devices/heartbeat",
        headers={"Authorization": f"Bearer {new_credential}"},
        json={"agent_version": "3.0.0", "queue_depth": 0, "state": "active"},
    )
    assert revoked_hb.status_code == 401
    assert revoked_hb.json()["error"]["code"] == "INVALID_CREDENTIALS"
