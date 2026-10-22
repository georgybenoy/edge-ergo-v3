"""EdgeErgo V3 — Device Management & Telemetry Ingestion Endpoints."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AuthenticatedDevice,
    AuthUser,
    get_current_device,
    get_current_user,
    require_admin,
)
from app.core.config import settings
from app.core.errors import AppException, NotFoundError
from app.core.rate_limit import enforce_enrollment_rate_limit
from app.db.session import get_db
from app.models.entities import Device, DeviceEnrollmentToken, DeviceHeartbeat
from app.schemas.api_models import (
    DeviceEnrollRequest,
    DeviceEnrollResponse,
    DeviceHeartbeatRequest,
    DeviceHeartbeatResponse,
    DeviceListItem,
    DeviceRevokeResponse,
    DeviceRotateCredentialResponse,
    TokenCreateRequest,
    TokenCreateResponse,
)
from app.services.audit import record_audit_event

router = APIRouter(prefix="/devices", tags=["Devices"])


def ensure_utc(dt: datetime) -> datetime:
    """Ensures datetime is timezone-aware in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_device_status(device: Device, now: datetime) -> str:
    """Computes dynamic device status based on last_seen_at and heartbeat window."""
    if device.status == "revoked":
        return "revoked"
    if device.status == "pending":
        return "pending"
    if not device.last_seen_at:
        return "unknown"

    last_seen = ensure_utc(device.last_seen_at)
    now_utc = ensure_utc(now)

    online_threshold = now_utc - timedelta(seconds=settings.DEVICE_ONLINE_WINDOW_SECONDS)
    if last_seen >= online_threshold:
        return "online"

    # If seen recently but offline, check if pending sync
    if device.last_sync_at:
        last_sync = ensure_utc(device.last_sync_at)
        if (now_utc - last_sync) > timedelta(hours=24):
            return "attention_needed"

    return "offline"


@router.post("/enrollment-tokens", response_model=TokenCreateResponse)
async def create_enrollment_token(
    body: TokenCreateRequest,
    current_user: AuthUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TokenCreateResponse:
    """Creates a short-lived single-use enrollment token. Plaintext returned once."""
    raw_token = f"eet_{secrets.token_urlsafe(32)}"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=body.expires_in_minutes)

    token_record = DeviceEnrollmentToken(
        token_hash=token_hash,
        organization_id=current_user.organization_id,
        created_by=current_user.user_id,
        label=body.label,
        expires_at=expires_at,
    )
    db.add(token_record)

    await record_audit_event(
        session=db,
        organization_id=current_user.organization_id,
        action="device_enrollment_token.created",
        target_type="device_enrollment_token",
        target_id=str(token_record.id),
        actor_user_id=current_user.user_id,
        metadata={"label": body.label, "expires_at": expires_at.isoformat()},
    )
    await db.commit()

    return TokenCreateResponse(
        token=raw_token,
        expires_at=expires_at,
        label=body.label,
    )


@router.post("/enroll", response_model=DeviceEnrollResponse)
async def enroll_device(
    request: Request,
    body: DeviceEnrollRequest,
    db: AsyncSession = Depends(get_db),
) -> DeviceEnrollResponse:
    """Atomically consumes an enrollment token and registers a new device.

    Returns the device credential once. Rate-limited by IP.
    """
    client_ip = request.client.host if request.client else "unknown"
    enforce_enrollment_rate_limit(client_ip)

    token_hash = hashlib.sha256(body.token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    # Query active, unconsumed token
    stmt = (
        select(DeviceEnrollmentToken)
        .where(
            DeviceEnrollmentToken.token_hash == token_hash,
            DeviceEnrollmentToken.consumed_at.is_(None),
            DeviceEnrollmentToken.expires_at > now,
        )
        .with_for_update()
    )
    result = await db.execute(stmt)
    token_row = result.scalars().first()

    if not token_row:
        raise AppException(
            message="Invalid, expired, or already consumed enrollment token",
            code="INVALID_OR_EXPIRED_TOKEN",
            status_code=400,
        )

    # Generate device credentials
    public_id = f"pub_{uuid.uuid4().hex[:16]}"
    secret = secrets.token_urlsafe(32)
    credential_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()

    device = Device(
        organization_id=token_row.organization_id,
        label=body.label,
        status="active",
        public_id=public_id,
        credential_hash=credential_hash,
        credential_version=1,
        agent_version=body.agent_version,
        enrolled_at=now,
        last_seen_at=now,
    )
    db.add(device)
    await db.flush()  # Populate device.id

    # Mark token consumed
    token_row.consumed_at = now
    token_row.consumed_by_device_id = device.id

    await record_audit_event(
        session=db,
        organization_id=token_row.organization_id,
        action="device.enrolled",
        target_type="device",
        target_id=str(device.id),
        metadata={
            "label": device.label,
            "public_id": public_id,
            "agent_version": body.agent_version,
        },
    )
    await db.commit()

    return DeviceEnrollResponse(
        device_id=device.id,
        public_id=public_id,
        credential=f"eed_{public_id}.{secret}",
        label=device.label,
        organization_id=device.organization_id,
    )


@router.post("/heartbeat", response_model=DeviceHeartbeatResponse)
async def device_heartbeat(
    body: DeviceHeartbeatRequest,
    current_device: AuthenticatedDevice = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> DeviceHeartbeatResponse:
    """Records health telemetry from an authenticated workstation agent."""
    now = datetime.now(timezone.utc)
    heartbeat = DeviceHeartbeat(
        device_id=current_device.device_id,
        organization_id=current_device.organization_id,
        agent_version=body.agent_version,
        queue_depth=body.queue_depth,
        state=body.state,
        received_at=now,
    )
    db.add(heartbeat)

    # Update device last_seen_at and version
    stmt = select(Device).where(Device.id == current_device.device_id)
    result = await db.execute(stmt)
    device = result.scalars().first()
    if device:
        device.last_seen_at = now
        device.agent_version = body.agent_version

    await db.commit()
    return DeviceHeartbeatResponse(status="ok", received_at=now)


@router.get("", response_model=list[DeviceListItem])
async def list_devices(
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DeviceListItem]:
    """Lists all workstation devices for the authenticated organization with safe fields only."""
    latest_hb_subquery = (
        select(DeviceHeartbeat.queue_depth)
        .where(DeviceHeartbeat.device_id == Device.id)
        .order_by(DeviceHeartbeat.received_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    stmt = (
        select(Device, latest_hb_subquery.label("latest_queue_depth"))
        .where(Device.organization_id == current_user.organization_id)
        .order_by(Device.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    now = datetime.now(timezone.utc)

    return [
        DeviceListItem(
            id=d.id,
            label=d.label,
            public_id=d.public_id,
            status=d.status,
            computed_status=compute_device_status(d, now),
            enrolled_at=d.enrolled_at,
            last_seen_at=d.last_seen_at,
            last_sync_at=d.last_sync_at,
            agent_version=d.agent_version,
            pending_queue_count=q_depth,
        )
        for d, q_depth in rows
    ]


@router.post("/{device_id}/revoke", response_model=DeviceRevokeResponse)
async def revoke_device(
    device_id: uuid.UUID,
    current_user: AuthUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DeviceRevokeResponse:
    """Revokes a workstation's credentials, preventing all future telemetry ingestion."""
    stmt = select(Device).where(
        Device.id == device_id,
        Device.organization_id == current_user.organization_id,
    )
    result = await db.execute(stmt)
    device = result.scalars().first()

    if not device:
        raise NotFoundError("Device not found")

    now = datetime.now(timezone.utc)
    device.status = "revoked"
    device.revoked_at = now

    await record_audit_event(
        session=db,
        organization_id=current_user.organization_id,
        action="device.revoked",
        target_type="device",
        target_id=str(device.id),
        actor_user_id=current_user.user_id,
        metadata={"label": device.label, "public_id": device.public_id},
    )
    await db.commit()

    return DeviceRevokeResponse(device_id=device.id, status="revoked", revoked_at=now)


@router.post("/{device_id}/rotate-credential", response_model=DeviceRotateCredentialResponse)
async def rotate_device_credential(
    device_id: uuid.UUID,
    current_user: AuthUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DeviceRotateCredentialResponse:
    """Generates a new secret credential for an active device."""
    stmt = select(Device).where(
        Device.id == device_id,
        Device.organization_id == current_user.organization_id,
    )
    result = await db.execute(stmt)
    device = result.scalars().first()

    if not device or device.status != "active":
        raise NotFoundError("Active device not found")

    secret = secrets.token_urlsafe(32)
    device.credential_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    device.credential_version += 1

    await record_audit_event(
        session=db,
        organization_id=current_user.organization_id,
        action="device.credential_rotated",
        target_type="device",
        target_id=str(device.id),
        actor_user_id=current_user.user_id,
        metadata={"credential_version": device.credential_version},
    )
    await db.commit()

    return DeviceRotateCredentialResponse(
        device_id=device.id,
        public_id=device.public_id,
        credential=f"eed_{device.public_id}.{secret}",
        credential_version=device.credential_version,
    )
