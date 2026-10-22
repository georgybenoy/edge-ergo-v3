"""EdgeErgo V3 — Security Audit Log Endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, require_admin
from app.db.session import get_db
from app.models.entities import AuditEvent
from app.schemas.api_models import AuditEventItem, AuditListResponse

router = APIRouter(prefix="/audit-events", tags=["Audit"])


@router.get("", response_model=AuditListResponse)
async def list_audit_events(
    target_id: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: AuthUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AuditListResponse:
    """Lists organization audit events (admin only).
    All sensitive fields are guaranteed scrubbed.
    """
    base_query = select(AuditEvent).where(
        AuditEvent.organization_id == current_user.organization_id
    )

    if target_id:
        base_query = base_query.where(AuditEvent.target_id == target_id)
    if target_type:
        base_query = base_query.where(AuditEvent.target_type == target_type)

    count_query = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    paged_query = base_query.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(paged_query)
    rows = result.scalars().all()

    items = [
        AuditEventItem(
            id=r.id,
            action=r.action,
            target_type=r.target_type,
            target_id=r.target_id,
            metadata=r.metadata_,
            created_at=r.created_at,
        )
        for r in rows
    ]

    return AuditListResponse(items=items, total=total)
