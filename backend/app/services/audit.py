"""EdgeErgo V3 — Security Audit Logging Service."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AuditEvent

FORBIDDEN_METADATA_KEYS = {"password", "secret", "token", "key", "credential"}


def sanitize_audit_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Ensures metadata strictly forbids sensitive or secret-like keys."""
    sanitized: dict[str, Any] = {}
    for k, v in metadata.items():
        lower_k = k.lower()
        if any(bad_word in lower_k for bad_word in FORBIDDEN_METADATA_KEYS):
            continue  # Omit prohibited secret fields entirely
        sanitized[k] = v
    return sanitized


async def record_audit_event(
    session: AsyncSession,
    organization_id: uuid.UUID,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_device_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """Inserts an immutable security audit event into audit_events table."""
    safe_metadata = sanitize_audit_metadata(metadata or {})
    audit = AuditEvent(
        organization_id=organization_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_user_id=actor_user_id,
        actor_device_id=actor_device_id,
        metadata_=safe_metadata,
    )
    session.add(audit)
    return audit
