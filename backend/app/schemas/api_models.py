"""EdgeErgo V3 — Pydantic v2 Request & Response Schemas.

All schemas enforce extra='forbid' to reject unknown, unapproved, or secret fields.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    """Base schema strictly forbidding extra fields and configuring json serializers."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
    )


# --- Dashboard Auth & User Schemas ---
class UserMeResponse(StrictBaseModel):
    user_id: uuid.UUID
    email: str | None
    organization_id: uuid.UUID
    organization_slug: str
    role: str


# --- Device Enrollment & Token Schemas ---
class TokenCreateRequest(StrictBaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    expires_in_minutes: int = Field(default=15, ge=1, le=60)


class TokenCreateResponse(StrictBaseModel):
    token: str
    expires_at: datetime
    label: str


class DeviceEnrollRequest(StrictBaseModel):
    token: str = Field(..., min_length=10, max_length=128)
    label: str = Field(..., min_length=1, max_length=100)
    agent_version: str = Field(..., min_length=1, max_length=32)


class DeviceEnrollResponse(StrictBaseModel):
    device_id: uuid.UUID
    public_id: str
    credential: str
    label: str
    organization_id: uuid.UUID


# --- Device Heartbeat Schemas ---
class DeviceHeartbeatRequest(StrictBaseModel):
    agent_version: str = Field(..., max_length=32)
    queue_depth: int = Field(..., ge=0)
    state: str = Field(..., max_length=50)


class DeviceHeartbeatResponse(StrictBaseModel):
    status: str = "ok"
    received_at: datetime


# --- Telemetry Ingestion Schemas ---
class AssessmentEventIngestItem(StrictBaseModel):
    event_id: uuid.UUID
    captured_at: datetime
    scoring_method: str = Field(..., max_length=50)
    scoring_version: str = Field(..., max_length=20)
    validity: Literal["valid", "insufficient", "invalid"]
    score: Decimal | None = Field(default=None, ge=Decimal("1.0"), le=Decimal("15.0"))
    neck_score: int | None = Field(default=None, ge=1, le=6)
    trunk_score: int | None = Field(default=None, ge=1, le=6)
    upper_arm_score: int | None = Field(default=None, ge=1, le=6)
    guidance_codes: list[str] = Field(default_factory=list)
    software_version: str = Field(..., max_length=32)


class BatchIngestRequest(StrictBaseModel):
    events: list[AssessmentEventIngestItem] = Field(..., max_length=100)


class BatchEventResultItem(StrictBaseModel):
    event_id: uuid.UUID
    status: Literal["accepted", "duplicate", "rejected"]
    reason_code: str | None = None


class BatchIngestResponse(StrictBaseModel):
    results: list[BatchEventResultItem]
    total_accepted: int
    total_duplicates: int
    total_rejected: int


# --- Device Query & Management Schemas ---
class DeviceListItem(StrictBaseModel):
    id: uuid.UUID
    label: str
    public_id: str
    status: str
    computed_status: str
    enrolled_at: datetime | None = None
    last_seen_at: datetime | None = None
    last_sync_at: datetime | None = None
    agent_version: str | None = None
    pending_queue_count: int | None = None


class DeviceRevokeResponse(StrictBaseModel):
    device_id: uuid.UUID
    status: str = "revoked"
    revoked_at: datetime


class DeviceRotateCredentialResponse(StrictBaseModel):
    device_id: uuid.UUID
    public_id: str
    credential: str
    credential_version: int


# --- Assessment Query Schemas ---
class AssessmentListItem(StrictBaseModel):
    event_id: uuid.UUID
    device_id: uuid.UUID
    captured_at: datetime
    scoring_method: str
    scoring_version: str
    validity: str
    score: Decimal | None
    neck_score: int | None
    trunk_score: int | None
    upper_arm_score: int | None
    guidance_codes: list[str]
    software_version: str


class AssessmentListResponse(StrictBaseModel):
    items: list[AssessmentListItem]
    total: int
    limit: int
    offset: int


# --- Reports Scope Preview Schemas ---
class ReportScopePreviewResponse(StrictBaseModel):
    total_matching: int
    capped_count: int
    max_export_limit: int
    valid_count: int
    insufficient_count: int
    invalid_count: int
    earliest_captured_at: datetime | None = None
    latest_captured_at: datetime | None = None


# --- Dashboard Summary Schemas ---
class MetricDefinition(StrictBaseModel):
    name: str
    value: float | None
    sample_count: int
    definition: str
    reason: str | None = None


class DashboardTrendPoint(StrictBaseModel):
    date: str  # YYYY-MM-DD
    valid_count: int
    insufficient_count: int
    invalid_count: int
    average_score: float | None = None


class IndicatorDistribution(StrictBaseModel):
    category: str
    count: int
    percentage: float


class PostureBreakdown(StrictBaseModel):
    neck_distribution: list[IndicatorDistribution]
    trunk_distribution: list[IndicatorDistribution]
    upper_arm_distribution: list[IndicatorDistribution]


class DashboardSummaryResponse(StrictBaseModel):
    total_assessments: int
    valid_count: int
    insufficient_count: int
    invalid_count: int
    active_devices_count: int
    online_devices_count: int
    average_rula_score: MetricDefinition
    scoring_method: str
    scoring_version: str
    daily_trend: list[DashboardTrendPoint] = []
    posture_breakdown: PostureBreakdown | None = None


# --- Audit Log Schemas ---
class AuditEventItem(StrictBaseModel):
    id: uuid.UUID
    action: str
    target_type: str | None
    target_id: str | None
    metadata: dict[str, Any]
    created_at: datetime


class AuditListResponse(StrictBaseModel):
    items: list[AuditEventItem]
    total: int
