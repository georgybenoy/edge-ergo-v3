"""EdgeErgo V3 — Tests for Dashboard JWT Authentication and Authorization."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Organization, OrganizationMember

if TYPE_CHECKING:
    from tests.conftest import TestJWTSigner

ORG_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ORG_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

USER_ADMIN_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_REVIEWER_A = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER_ADMIN_B = uuid.UUID("33333333-3333-3333-3333-333333333333")
USER_UNATTACHED = uuid.UUID("44444444-4444-4444-4444-444444444444")


@pytest.fixture
async def seeded_auth_db(async_test_session: AsyncSession) -> AsyncSession:
    """Seeds test organizations, users, and membership roles for auth testing."""
    from sqlalchemy import text

    # Insert into auth.users (which triggers profile creation)
    await async_test_session.execute(
        text(
            """
            INSERT INTO auth.users (id, email) VALUES
                (:u1, 'admin_a@example.com'),
                (:u2, 'reviewer_a@example.com'),
                (:u3, 'admin_b@example.com'),
                (:u4, 'unattached@example.com');
            """
        ),
        {"u1": USER_ADMIN_A, "u2": USER_REVIEWER_A, "u3": USER_ADMIN_B, "u4": USER_UNATTACHED},
    )

    # Create Orgs
    org_a = Organization(id=ORG_A_ID, name="Organization A", slug="org-a")
    org_b = Organization(id=ORG_B_ID, name="Organization B", slug="org-b")
    async_test_session.add_all([org_a, org_b])

    # Create Memberships
    m1 = OrganizationMember(organization_id=ORG_A_ID, user_id=USER_ADMIN_A, role="admin")
    m2 = OrganizationMember(organization_id=ORG_A_ID, user_id=USER_REVIEWER_A, role="reviewer")
    m3 = OrganizationMember(organization_id=ORG_B_ID, user_id=USER_ADMIN_B, role="admin")
    async_test_session.add_all([m1, m2, m3])

    await async_test_session.commit()
    return async_test_session


@pytest.mark.asyncio
async def test_valid_token_resolves_user(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_auth_db: AsyncSession,
) -> None:
    """Verifies valid asymmetric JWT correctly resolves user identity, org, and role."""
    token = jwt_signer.mint_token(
        user_id=str(USER_ADMIN_A),
        email="admin_a@example.com",
    )
    response = await async_client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(USER_ADMIN_A)
    assert data["email"] == "admin_a@example.com"
    assert data["organization_id"] == str(ORG_A_ID)
    assert data["organization_slug"] == "org-a"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_expired_token_rejected(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_auth_db: AsyncSession,
) -> None:
    """Verifies expired JWT is strictly rejected with 401 TOKEN_EXPIRED."""
    expired_token = jwt_signer.mint_token(
        user_id=str(USER_ADMIN_A),
        expires_delta_seconds=-120,  # Expired 2 minutes ago
    )
    response = await async_client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_invalid_signature_rejected(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_auth_db: AsyncSession,
) -> None:
    """Verifies token signed with wrong RSA key is rejected."""
    from cryptography.hazmat.primitives.asymmetric import rsa

    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged_token = jwt_signer.mint_token(
        user_id=str(USER_ADMIN_A),
        signing_key=other_private_key,
    )
    response = await async_client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_SIGNATURE"


@pytest.mark.asyncio
async def test_wrong_issuer_rejected(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_auth_db: AsyncSession,
) -> None:
    """Verifies token with untrusted issuer is rejected."""
    token = jwt_signer.mint_token(
        user_id=str(USER_ADMIN_A),
        issuer="https://malicious-issuer.example.com/auth/v1",
    )
    response = await async_client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_ISSUER"


@pytest.mark.asyncio
async def test_wrong_audience_rejected(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_auth_db: AsyncSession,
) -> None:
    """Verifies token with incorrect audience claim is rejected."""
    token = jwt_signer.mint_token(
        user_id=str(USER_ADMIN_A),
        audience="wrong_audience_name",
    )
    response = await async_client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_AUDIENCE"


@pytest.mark.asyncio
async def test_alg_none_rejected(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_auth_db: AsyncSession,
) -> None:
    """Verifies unsigned tokens (alg=none) are strictly forbidden."""
    token = jwt_signer.mint_token(
        user_id=str(USER_ADMIN_A),
        algorithm="none",
    )
    response = await async_client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INSECURE_ALGORITHM"


@pytest.mark.asyncio
async def test_malformed_token_rejected(
    async_client: AsyncClient,
    seeded_auth_db: AsyncSession,
) -> None:
    """Verifies unparseable garbage token strings return 401 INVALID_TOKEN."""
    response = await async_client.get(
        "/api/v1/me",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_user_without_org_membership_denied(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_auth_db: AsyncSession,
) -> None:
    """Verifies valid authenticated user without organization membership is rejected."""
    token = jwt_signer.mint_token(
        user_id=str(USER_UNATTACHED),
        email="unattached@example.com",
    )
    response = await async_client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "NO_ORGANIZATION_MEMBERSHIP"


@pytest.mark.asyncio
async def test_reviewer_cannot_access_admin_endpoints(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_auth_db: AsyncSession,
) -> None:
    """Verifies reviewer role receives 403 ADMIN_REQUIRED when attempting admin operations."""
    reviewer_token = jwt_signer.mint_token(
        user_id=str(USER_REVIEWER_A),
        email="reviewer_a@example.com",
    )
    response = await async_client.post(
        "/api/v1/devices/enrollment-tokens",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"label": "Attempted Token", "expires_in_minutes": 15},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_explicit_org_header_resolves_correct_org(
    async_client: AsyncClient,
    jwt_signer: TestJWTSigner,
    seeded_auth_db: AsyncSession,
) -> None:
    """Verifies user can specify X-Organization-Id if they are member of multiple orgs."""
    token = jwt_signer.mint_token(
        user_id=str(USER_ADMIN_A),
    )
    # Specifying own org succeeds
    res_ok = await async_client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": str(ORG_A_ID)},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["organization_id"] == str(ORG_A_ID)

    # Specifying another org where user is NOT a member returns 403
    res_denied = await async_client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": str(ORG_B_ID)},
    )
    assert res_denied.status_code == 403
    assert res_denied.json()["error"]["code"] == "NO_ORGANIZATION_MEMBERSHIP"
