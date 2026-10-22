"""Desktop overlay subsystem for EdgeErgo V3."""

from __future__ import annotations

from edge_ergo.overlay.presenter import OverlayPresenter
from edge_ergo.overlay.settings_dialog import SettingsDialog
from edge_ergo.overlay.types import (
    OVERLAY_STATE_LABELS,
    OverlayState,
    OverlayViewModel,
)
from edge_ergo.overlay.widget import CompactOverlayWidget

__all__ = [
    "CompactOverlayWidget",
    "OVERLAY_STATE_LABELS",
    "OverlayPresenter",
    "OverlayState",
    "OverlayViewModel",
    "SettingsDialog",
]
