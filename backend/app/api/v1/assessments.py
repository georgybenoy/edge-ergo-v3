"""EdgeErgo V3 — Assessment Events Telemetry Ingestion & Query Endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    AuthenticatedDevice,
    AuthUser,
    get_current_device,
    get_current_user,
)
from app.core.errors import AppException
from app.db.session import get_db
from app.models.entities import AssessmentEvent, Device
from app.schemas.api_models import (
    AssessmentListItem,
    AssessmentListResponse,
    BatchEventResultItem,
    BatchIngestRequest,
    BatchIngestResponse,
)

router = APIRouter(prefix="/assessments", tags=["Assessments"])


@router.post("/batch", response_model=BatchIngestResponse)
async def ingest_assessment_batch(
    body: BatchIngestRequest,
    current_device: AuthenticatedDevice = Depends(get_current_device),
    db: AsyncSession = Depends(get_db),
) -> BatchIngestResponse:
    """Ingests a bounded batch of edge ergonomic assessment records.

    Enforces idempotent ingestion via ON CONFLICT (device_id, event_id) DO NOTHING.
    Individual malformed events are marked as rejected without aborting the batch.
    """
    now = datetime.utcnow()
    min_captured_at = now - timedelta(days=90)
    max_captured_at = now + timedelta(minutes=5)

    results: list[BatchEventResultItem] = []
    valid_candidates: list[dict[str, object]] = []

    for event in body.events:
        # Sanity check: timestamp within acceptable boundary
        event_captured_at = (
            event.captured_at.replace(tzinfo=None)
            if event.captured_at.tzinfo
            else event.captured_at
        )
        if event_captured_at < min_captured_at or event_captured_at > max_captured_at:
            results.append(
                BatchEventResultItem(
                    event_id=event.event_id,
                    status="rejected",
                    reason_code="TIMESTAMP_OUT_OF_RANGE",
                )
            )
            continue

        # Consistency check: valid observations must carry a score
        if event.validity == "valid" and event.score is None:
            results.append(
                BatchEventResultItem(
                    event_id=event.event_id,
                    status="rejected",
                    reason_code="VALID_OBSERVATION_MISSING_SCORE",
                )
            )
            continue

        # Consistency check: non-valid observations must NOT carry a score
        if event.validity in ("insufficient", "invalid") and event.score is not None:
            results.append(
                BatchEventResultItem(
                    event_id=event.event_id,
                    status="rejected",
                    reason_code="INVALID_OBSERVATION_HAS_SCORE",
                )
            )
            continue

        valid_candidates.append(
            {
                "event_id": event.event_id,
                "device_id": current_device.device_id,
                "organization_id": current_device.organization_id,
                "captured_at": event.captured_at,
                "received_at": now,
                "scoring_method": event.scoring_method,
                "scoring_version": event.scoring_version,
                "validity": event.validity,
                "score": event.score,
                "neck_score": event.neck_score,
                "trunk_score": event.trunk_score,
                "upper_arm_score": event.upper_arm_score,
                "guidance_codes": event.guidance_codes,
                "software_version": event.software_version,
            }
        )

    # Ingest valid candidates using PostgreSQL ON CONFLICT DO NOTHING
    accepted_event_ids: set[uuid.UUID] = set()
    if valid_candidates:
        insert_stmt = (
            pg_insert(AssessmentEvent)
            .values(valid_candidates)
            .on_conflict_do_nothing(index_elements=["device_id", "event_id"])
            .returning(AssessmentEvent.event_id)
        )
        exec_res = await db.execute(insert_stmt)
        accepted_rows = exec_res.scalars().all()
        accepted_event_ids = set(accepted_rows)

        # Mark candidate events as accepted or duplicate
        for candidate in valid_candidates:
            cid = uuid.UUID(str(candidate["event_id"]))
            if cid in accepted_event_ids:
                results.append(BatchEventResultItem(event_id=cid, status="accepted"))
            else:
                results.append(
                    BatchEventResultItem(
                        event_id=cid,
                        status="duplicate",
                        reason_code="ALREADY_INGESTED",
                    )
                )

        # Update device synchronization timestamps
        device_stmt = select(Device).where(Device.id == current_device.device_id)
        dev_res = await db.execute(device_stmt)
        dev = dev_res.scalars().first()
        if dev:
            dev.last_sync_at = now
            dev.last_seen_at = now

        await db.commit()

    total_accepted = sum(1 for r in results if r.status == "accepted")
    total_duplicates = sum(1 for r in results if r.status == "duplicate")
    total_rejected = sum(1 for r in results if r.status == "rejected")

    return BatchIngestResponse(
        results=results,
        total_accepted=total_accepted,
        total_duplicates=total_duplicates,
        total_rejected=total_rejected,
    )


@router.get("", response_model=AssessmentListResponse)
async def list_assessments(
    device_id: uuid.UUID | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    validity: str | None = Query(default=None),
    scoring_version: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssessmentListResponse:
    """Lists organization-scoped assessments with bounded filtering and pagination."""
    # Enforce maximum query window of 366 days
    if from_date and to_date:
        if (to_date - from_date).days > 366:
            raise AppException(
                message="Date filter range cannot exceed 366 days",
                code="DATE_RANGE_EXCEEDED",
                status_code=400,
            )

    base_query = select(AssessmentEvent).where(
        AssessmentEvent.organization_id == current_user.organization_id
    )

    if device_id:
        base_query = base_query.where(AssessmentEvent.device_id == device_id)
    if from_date:
        base_query = base_query.where(AssessmentEvent.captured_at >= from_date)
    if to_date:
        base_query = base_query.where(AssessmentEvent.captured_at <= to_date)
    if validity:
        base_query = base_query.where(AssessmentEvent.validity == validity)
    if scoring_version:
        base_query = base_query.where(AssessmentEvent.scoring_version == scoring_version)

    # Count total matching rows
    count_query = select(func.count()).select_from(base_query.subquery())
    total_count = (await db.execute(count_query)).scalar() or 0

    # Paginate rows
    paged_query = (
        base_query.order_by(AssessmentEvent.captured_at.desc()).limit(limit).offset(offset)
    )
    result = await db.execute(paged_query)
    rows = result.scalars().all()

    items = [
        AssessmentListItem(
            event_id=r.event_id,
            device_id=r.device_id,
            captured_at=r.captured_at,
            scoring_method=r.scoring_method,
            scoring_version=r.scoring_version,
            validity=r.validity,
            score=r.score,
            neck_score=r.neck_score,
            trunk_score=r.trunk_score,
            upper_arm_score=r.upper_arm_score,
            guidance_codes=r.guidance_codes,
            software_version=r.software_version,
        )
        for r in rows
    ]

    return AssessmentListResponse(items=items, total=total_count, limit=limit, offset=offset)
