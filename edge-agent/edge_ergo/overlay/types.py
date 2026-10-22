"""State definitions and view-model structures for the desktop overlay UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OverlayState(str, Enum):
    """Visual states conforming to DESIGN.md §10."""

    READY = "ready"
    ACTIVE = "active"
    PAUSED = "paused"
    CAMERA_UNAVAILABLE = "camera_unavailable"
    LOW_CONFIDENCE = "low_confidence"
    OFFLINE = "offline"
    SYNCING = "syncing"
    AUTH_ERROR = "auth_error"
    ERROR = "error"


OVERLAY_STATE_LABELS = {
    OverlayState.READY: "Ready",
    OverlayState.ACTIVE: "Active",
    OverlayState.PAUSED: "Paused",
    OverlayState.CAMERA_UNAVAILABLE: "Camera unavailable",
    OverlayState.LOW_CONFIDENCE: "Low confidence",
    OverlayState.OFFLINE: "Offline",
    OverlayState.SYNCING: "Syncing",
    OverlayState.AUTH_ERROR: "Auth error",
    OverlayState.ERROR: "Error",
}


@dataclass(frozen=True)
class OverlayViewModel:
    """Pure data representation of the overlay UI state.

    Decoupled from PySide6 widgets to enable headless testing.
    """

    state: OverlayState = OverlayState.READY
    score_text: str = "—"
    category_text: str = "—"
    recommendation: str = "Position yourself naturally in front of your workstation monitor."
    last_updated_text: str = "Not yet updated"
    sync_status_text: str = "Local only"
    queue_depth: int = 0
    last_sync_text: str = "Never"
    privacy_indicator_text: str = "Camera analysis active — processed on this workstation"
    is_paused: bool = False
    is_quiet_mode: bool = False
    sampling_interval_s: float = 5.0
    reminder_cooldown_min: int = 15
    error_message: str | None = None
