"""EdgeErgo V3 — Authentication & Authorization Dependencies."""

from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_supabase_jwt
from app.core.errors import AuthenticationError, AuthorizationError
from app.core.rate_limit import enforce_failed_auth_limit
from app.db.session import get_db
from app.models.entities import Device, Organization, OrganizationMember

DEVICE_AUTH_PATTERN = re.compile(r"^Bearer\s+eed_([A-Za-z0-9_\-]+)\.([A-Za-z0-9_\-]+)$")
DUMMY_CREDENTIAL_HASH = hashlib.sha256(b"dummy_timing_mitigation_secret").hexdigest()


@dataclass
class AuthUser:
    """Represents an authenticated dashboard user scoped to an organization."""

    user_id: uuid.UUID
    email: str | None
    organization_id: uuid.UUID
    organization_slug: str
    role: str


@dataclass
class AuthenticatedDevice:
    """Represents an authenticated edge workstation device scoped to an organization."""

    device_id: uuid.UUID
    organization_id: uuid.UUID
    public_id: str
    label: str


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    x_organization_id: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> AuthUser:
    """Extracts, verifies Supabase JWT, and resolves organization membership from DB."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError("Missing or malformed Authorization header", code="UNAUTHORIZED")

    token = authorization.split("Bearer ", 1)[1].strip()
    payload = await verify_supabase_jwt(token)

    try:
        user_uuid = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError(
            "Invalid user identity in token claims", code="INVALID_IDENTITY"
        ) from exc

    # Query organization memberships in database
    query = (
        select(OrganizationMember, Organization)
        .join(Organization, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user_uuid)
    )

    if x_organization_id:
        try:
            req_org_uuid = uuid.UUID(x_organization_id)
            query = query.where(OrganizationMember.organization_id == req_org_uuid)
        except ValueError as exc:
            raise AuthorizationError(
                "Invalid organization ID format", code="INVALID_ORGANIZATION_ID"
            ) from exc

    result = await db.execute(query)
    member_row = result.first()

    if not member_row:
        raise AuthorizationError(
            "User has no authorized membership in this organization",
            code="NO_ORGANIZATION_MEMBERSHIP",
        )

    membership, org = member_row
    return AuthUser(
        user_id=user_uuid,
        email=payload.get("email"),
        organization_id=org.id,
        organization_slug=org.slug,
        role=membership.role,
    )


async def require_admin(
    current_user: AuthUser = Depends(get_current_user),
) -> AuthUser:
    """Guarantees that the authenticated user possesses admin privileges."""
    if current_user.role != "admin":
        raise AuthorizationError(
            "Administrative privileges required for this action", code="ADMIN_REQUIRED"
        )
    return current_user


async def get_current_device(
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedDevice:
    """Authenticates an edge device via eed_<public_id>.<secret> Bearer credential.

    Timing attacks are mitigated via constant-time hash comparisons and identical
    error responses for unknown, revoked, and incorrect credentials.
    """
    client_ip = request.client.host if request.client else "unknown"

    if not authorization:
        enforce_failed_auth_limit(client_ip)
        raise AuthenticationError(
            "Missing device authorization credentials", code="INVALID_CREDENTIALS"
        )

    match = DEVICE_AUTH_PATTERN.match(authorization.strip())
    if not match:
        enforce_failed_auth_limit(client_ip)
        raise AuthenticationError(
            "Malformed device authorization header", code="INVALID_CREDENTIALS"
        )

    public_id, secret = match.groups()
    computed_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()

    # Query device by public_id
    stmt = select(Device).where(Device.public_id == public_id)
    result = await db.execute(stmt)
    device = result.scalars().first()

    if not device:
        # Perform constant-time dummy comparison to prevent timing leak on existence
        hmac.compare_digest(computed_hash, DUMMY_CREDENTIAL_HASH)
        enforce_failed_auth_limit(client_ip)
        raise AuthenticationError("Invalid device credentials", code="INVALID_CREDENTIALS")

    # Constant-time comparison of secret hash
    is_valid_secret = hmac.compare_digest(computed_hash, device.credential_hash)
    if not is_valid_secret or device.status != "active":
        # Identical error for revoked or wrong secret
        enforce_failed_auth_limit(client_ip)
        raise AuthenticationError("Invalid device credentials", code="INVALID_CREDENTIALS")

    # Update last_seen_at safely
    device.last_seen_at = datetime.now(timezone.utc)
    await db.commit()

    return AuthenticatedDevice(
        device_id=device.id,
        organization_id=device.organization_id,
        public_id=device.public_id,
        label=device.label,
    )
