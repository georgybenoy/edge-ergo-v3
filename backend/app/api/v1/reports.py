"""EdgeErgo V3 — CSV Reporting & Telemetry Export Endpoints."""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, get_current_user
from app.core.config import settings
from app.core.errors import AppException
from app.db.session import get_db
from app.models.entities import AssessmentEvent, Device
from app.schemas.api_models import ReportScopePreviewResponse

router = APIRouter(prefix="/reports", tags=["Reports"])

CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

CSV_REPORT_HEADERS: list[str] = [
    "event_id",
    "device_id",
    "device_label",
    "captured_at_utc",
    "scoring_method",
    "scoring_version",
    "validity",
    "score_rula_1_to_7",
    "neck_score_1_to_6",
    "trunk_score_1_to_6",
    "upper_arm_score_1_to_6",
    "guidance_codes",
    "software_version",
]


def escape_csv_cell(value: object) -> str:
    """Escapes string cells starting with formula characters to mitigate CSV injection."""
    if value is None:
        return ""
    val_str = str(value)
    if val_str.startswith(CSV_INJECTION_PREFIXES):
        return f"'{val_str}"
    return val_str


@router.get("/preview", response_model=ReportScopePreviewResponse)
async def preview_report_scope(
    device_id: uuid.UUID | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    validity: str | None = Query(default=None),
    scoring_version: str | None = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportScopePreviewResponse:
    """Provides a fast, server-calculated preview of exportable report scope.

    Computes matching row count, valid vs invalid breakdown, and time boundaries.
    """
    if from_date and to_date and (to_date - from_date).days > 366:
        raise AppException(
            message="Date filter range cannot exceed 366 days",
            code="DATE_RANGE_EXCEEDED",
            status_code=400,
        )

    base_query = select(
        func.count(AssessmentEvent.event_id).label("total"),
        func.count(case((AssessmentEvent.validity == "valid", AssessmentEvent.event_id))).label(
            "valid_count"
        ),
        func.count(
            case((AssessmentEvent.validity == "insufficient", AssessmentEvent.event_id))
        ).label("insufficient_count"),
        func.count(case((AssessmentEvent.validity == "invalid", AssessmentEvent.event_id))).label(
            "invalid_count"
        ),
        func.min(AssessmentEvent.captured_at).label("earliest_at"),
        func.max(AssessmentEvent.captured_at).label("latest_at"),
    ).where(AssessmentEvent.organization_id == current_user.organization_id)

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

    res = (await db.execute(base_query)).first()
    total = res.total if res else 0
    valid_count = res.valid_count if res else 0
    insufficient_count = res.insufficient_count if res else 0
    invalid_count = res.invalid_count if res else 0
    earliest = res.earliest_at if res else None
    latest = res.latest_at if res else None

    return ReportScopePreviewResponse(
        total_matching=total,
        capped_count=min(total, settings.MAX_EXPORT_ROWS),
        max_export_limit=settings.MAX_EXPORT_ROWS,
        valid_count=valid_count,
        insufficient_count=insufficient_count,
        invalid_count=invalid_count,
        earliest_captured_at=earliest,
        latest_captured_at=latest,
    )


@router.get("/assessments.csv")
async def export_assessments_csv(
    device_id: uuid.UUID | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    validity: str | None = Query(default=None),
    scoring_version: str | None = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Streams organization-scoped ergonomic assessments as CSV with injection safeguards.

    Filters are bounded to a maximum window of 366 days and exports up to MAX_EXPORT_ROWS.
    Cells starting with formula indicators are safely escaped.
    """
    if from_date and to_date and (to_date - from_date).days > 366:
        raise AppException(
            message="Date filter range cannot exceed 366 days",
            code="DATE_RANGE_EXCEEDED",
            status_code=400,
        )

    # Base query joined with devices to fetch human-readable workstation label
    query = (
        select(AssessmentEvent, Device.label)
        .join(Device, AssessmentEvent.device_id == Device.id)
        .where(AssessmentEvent.organization_id == current_user.organization_id)
    )

    if device_id:
        query = query.where(AssessmentEvent.device_id == device_id)
    if from_date:
        query = query.where(AssessmentEvent.captured_at >= from_date)
    if to_date:
        query = query.where(AssessmentEvent.captured_at <= to_date)
    if validity:
        query = query.where(AssessmentEvent.validity == validity)
    if scoring_version:
        query = query.where(AssessmentEvent.scoring_version == scoring_version)

    query = query.order_by(AssessmentEvent.captured_at.desc()).limit(settings.MAX_EXPORT_ROWS)
    result = await db.execute(query)
    rows = result.all()

    async def csv_generator() -> AsyncGenerator[str, None]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        # Header with explicit units
        writer.writerow(CSV_REPORT_HEADERS)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        for event, dev_label in rows:
            row_data = [
                escape_csv_cell(event.event_id),
                escape_csv_cell(event.device_id),
                escape_csv_cell(dev_label),
                escape_csv_cell(event.captured_at.isoformat() if event.captured_at else ""),
                escape_csv_cell(event.scoring_method),
                escape_csv_cell(event.scoring_version),
                escape_csv_cell(event.validity),
                escape_csv_cell(event.score if event.validity == "valid" else ""),
                escape_csv_cell(event.neck_score if event.validity == "valid" else ""),
                escape_csv_cell(event.trunk_score if event.validity == "valid" else ""),
                escape_csv_cell(event.upper_arm_score if event.validity == "valid" else ""),
                escape_csv_cell(";".join(event.guidance_codes) if event.guidance_codes else ""),
                escape_csv_cell(event.software_version),
            ]
            writer.writerow(row_data)
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M")
    filename = f"assessments_{current_user.organization_slug}_{timestamp}.csv"
    return StreamingResponse(
        csv_generator(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
