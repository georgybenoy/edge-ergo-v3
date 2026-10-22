"""EdgeErgo V3 — Dashboard Analytics & Summary Indicators."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import AssessmentEvent, Device
from app.schemas.api_models import (
    DashboardSummaryResponse,
    DashboardTrendPoint,
    IndicatorDistribution,
    MetricDefinition,
    PostureBreakdown,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    device_id: uuid.UUID | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    """Calculates aggregated ergonomic indicators, trend progression, and fleet connectivity.

    Every metric explicitly carries its definition and sample count.
    Average score is computed strictly over valid observations for rula_v1_screening.
    """
    org_id = current_user.organization_id
    now = datetime.utcnow()
    online_threshold = now - timedelta(seconds=settings.DEVICE_ONLINE_WINDOW_SECONDS)

    # 1. Device metrics
    dev_query = select(
        func.count(Device.id).label("total_devices"),
        func.count(case((Device.status == "active", Device.id))).label("active_devices"),
        func.count(
            case(
                (
                    (Device.status == "active") & (Device.last_seen_at >= online_threshold),
                    Device.id,
                )
            )
        ).label("online_devices"),
    ).where(Device.organization_id == org_id)
    if device_id:
        dev_query = dev_query.where(Device.id == device_id)
    dev_res = (await db.execute(dev_query)).first()

    active_devices = dev_res.active_devices if dev_res else 0
    online_devices = dev_res.online_devices if dev_res else 0

    # 2. Assessment metrics
    assess_query = select(
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
        func.avg(case((AssessmentEvent.validity == "valid", AssessmentEvent.score))).label(
            "avg_score"
        ),
    ).where(
        AssessmentEvent.organization_id == org_id,
        AssessmentEvent.scoring_method == "rula_v1_screening",
    )
    if device_id:
        assess_query = assess_query.where(AssessmentEvent.device_id == device_id)
    if from_date:
        assess_query = assess_query.where(AssessmentEvent.captured_at >= from_date)
    if to_date:
        assess_query = assess_query.where(AssessmentEvent.captured_at <= to_date)

    assess_res = (await db.execute(assess_query)).first()

    total_assessments = assess_res.total if assess_res else 0
    valid_count = assess_res.valid_count if assess_res else 0
    insufficient_count = assess_res.insufficient_count if assess_res else 0
    invalid_count = assess_res.invalid_count if assess_res else 0

    # Compute average indicator safely
    avg_score_raw = assess_res.avg_score if assess_res else None
    definition_text = "Mean partial RULA screening risk score across valid upper-body observations"
    if valid_count > 0 and avg_score_raw is not None:
        avg_value = round(float(Decimal(str(avg_score_raw))), 2)
        avg_metric = MetricDefinition(
            name="average_rula_score",
            value=avg_value,
            sample_count=valid_count,
            definition=definition_text,
            reason=None,
        )
    else:
        avg_metric = MetricDefinition(
            name="average_rula_score",
            value=None,
            sample_count=valid_count,
            definition=definition_text,
            reason="Insufficient valid observations in organization",
        )

    # 3. Daily trend progression
    date_col = func.date(AssessmentEvent.captured_at).label("day")
    trend_query = (
        select(
            date_col,
            func.count(case((AssessmentEvent.validity == "valid", AssessmentEvent.event_id))).label(
                "valid_count"
            ),
            func.count(
                case((AssessmentEvent.validity == "insufficient", AssessmentEvent.event_id))
            ).label("insufficient_count"),
            func.count(
                case((AssessmentEvent.validity == "invalid", AssessmentEvent.event_id))
            ).label("invalid_count"),
            func.avg(case((AssessmentEvent.validity == "valid", AssessmentEvent.score))).label(
                "avg_score"
            ),
        )
        .where(
            AssessmentEvent.organization_id == org_id,
            AssessmentEvent.scoring_method == "rula_v1_screening",
        )
        .group_by(date_col)
        .order_by(date_col.asc())
    )
    if device_id:
        trend_query = trend_query.where(AssessmentEvent.device_id == device_id)
    if from_date:
        trend_query = trend_query.where(AssessmentEvent.captured_at >= from_date)
    if to_date:
        trend_query = trend_query.where(AssessmentEvent.captured_at <= to_date)

    trend_rows = (await db.execute(trend_query)).all()
    daily_trend = [
        DashboardTrendPoint(
            date=str(row.day),
            valid_count=row.valid_count,
            insufficient_count=row.insufficient_count,
            invalid_count=row.invalid_count,
            average_score=round(float(Decimal(str(row.avg_score))), 2)
            if row.avg_score is not None
            else None,
        )
        for row in trend_rows
    ]

    # 4. Posture indicator breakdown (only when valid observations exist)
    posture_breakdown: PostureBreakdown | None = None
    if valid_count > 0:

        def get_dist(
            c1: int, c2: int, c3: int, total_v: int
        ) -> list[IndicatorDistribution]:
            return [
                IndicatorDistribution(
                    category="Optimal (1-2)",
                    count=c1,
                    percentage=round((c1 / total_v) * 100, 1) if total_v > 0 else 0.0,
                ),
                IndicatorDistribution(
                    category="Moderate (3-4)",
                    count=c2,
                    percentage=round((c2 / total_v) * 100, 1) if total_v > 0 else 0.0,
                ),
                IndicatorDistribution(
                    category="High (5-6)",
                    count=c3,
                    percentage=round((c3 / total_v) * 100, 1) if total_v > 0 else 0.0,
                ),
            ]

        posture_query = select(
            func.count(
                case((AssessmentEvent.neck_score <= 2, AssessmentEvent.event_id))
            ).label("neck_low"),
            func.count(
                case(
                    (
                        (AssessmentEvent.neck_score >= 3) & (AssessmentEvent.neck_score <= 4),
                        AssessmentEvent.event_id,
                    )
                )
            ).label("neck_med"),
            func.count(
                case((AssessmentEvent.neck_score >= 5, AssessmentEvent.event_id))
            ).label("neck_high"),
            func.count(
                case((AssessmentEvent.trunk_score <= 2, AssessmentEvent.event_id))
            ).label("trunk_low"),
            func.count(
                case(
                    (
                        (AssessmentEvent.trunk_score >= 3) & (AssessmentEvent.trunk_score <= 4),
                        AssessmentEvent.event_id,
                    )
                )
            ).label("trunk_med"),
            func.count(
                case((AssessmentEvent.trunk_score >= 5, AssessmentEvent.event_id))
            ).label("trunk_high"),
            func.count(
                case((AssessmentEvent.upper_arm_score <= 2, AssessmentEvent.event_id))
            ).label("arm_low"),
            func.count(
                case(
                    (
                        (AssessmentEvent.upper_arm_score >= 3)
                        & (AssessmentEvent.upper_arm_score <= 4),
                        AssessmentEvent.event_id,
                    )
                )
            ).label("arm_med"),
            func.count(
                case((AssessmentEvent.upper_arm_score >= 5, AssessmentEvent.event_id))
            ).label("arm_high"),
        ).where(
            AssessmentEvent.organization_id == org_id,
            AssessmentEvent.validity == "valid",
        )
        if device_id:
            posture_query = posture_query.where(AssessmentEvent.device_id == device_id)
        if from_date:
            posture_query = posture_query.where(AssessmentEvent.captured_at >= from_date)
        if to_date:
            posture_query = posture_query.where(AssessmentEvent.captured_at <= to_date)

        p_res = (await db.execute(posture_query)).first()
        if p_res:
            posture_breakdown = PostureBreakdown(
                neck_distribution=get_dist(
                    p_res.neck_low, p_res.neck_med, p_res.neck_high, valid_count
                ),
                trunk_distribution=get_dist(
                    p_res.trunk_low, p_res.trunk_med, p_res.trunk_high, valid_count
                ),
                upper_arm_distribution=get_dist(
                    p_res.arm_low, p_res.arm_med, p_res.arm_high, valid_count
                ),
            )

    return DashboardSummaryResponse(
        total_assessments=total_assessments,
        valid_count=valid_count,
        insufficient_count=insufficient_count,
        invalid_count=invalid_count,
        active_devices_count=active_devices,
        online_devices_count=online_devices,
        average_rula_score=avg_metric,
        scoring_method="rula_v1_screening",
        scoring_version="1.0.0",
        daily_trend=daily_trend,
        posture_breakdown=posture_breakdown,
    )
