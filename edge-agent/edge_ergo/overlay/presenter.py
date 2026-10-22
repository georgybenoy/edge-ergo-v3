"""Headless presenter managing overlay state and user interactions."""

from __future__ import annotations

import time
from collections.abc import Callable

from edge_ergo.camera.types import CameraState
from edge_ergo.overlay.types import OverlayState, OverlayViewModel
from edge_ergo.quality.types import ValidityReport, ValidityStatus
from edge_ergo.scoring.types import RulaScoringResult


class OverlayPresenter:
    """Presenter managing overlay view model, cooldowns, and business state transitions.

    Unit-testable without a graphical display server.
    """

    def __init__(
        self,
        initial_vm: OverlayViewModel | None = None,
        on_update: Callable[[OverlayViewModel], None] | None = None,
    ) -> None:
        self._vm = initial_vm or OverlayViewModel()
        self._on_update = on_update
        self._last_recommendation_time: float = 0.0

    @property
    def view_model(self) -> OverlayViewModel:
        return self._vm

    def set_update_callback(self, callback: Callable[[OverlayViewModel], None]) -> None:
        self._on_update = callback

    def _notify(self) -> None:
        if self._on_update:
            self._on_update(self._vm)

    def on_camera_state_changed(self, camera_state: CameraState) -> None:
        """Transitions overlay state based on camera subsystem status."""
        new_state = self._vm.state
        err = self._vm.error_message

        if camera_state == CameraState.PAUSED:
            new_state = OverlayState.PAUSED
        elif camera_state == CameraState.ACTIVE:
            new_state = OverlayState.ACTIVE
        elif camera_state in (
            CameraState.DISCONNECTED,
            CameraState.PERMISSION_DENIED,
            CameraState.IN_USE,
        ):
            new_state = OverlayState.CAMERA_UNAVAILABLE
            err = f"Camera unavailable: {camera_state.value}"
        elif camera_state == CameraState.ERROR:
            new_state = OverlayState.ERROR
            err = "Camera acquisition error"

        self._vm = OverlayViewModel(
            state=new_state,
            score_text=self._vm.score_text,
            category_text=self._vm.category_text,
            recommendation=self._vm.recommendation,
            last_updated_text=self._vm.last_updated_text,
            sync_status_text=self._vm.sync_status_text,
            privacy_indicator_text=self._vm.privacy_indicator_text,
            is_paused=(new_state == OverlayState.PAUSED),
            is_quiet_mode=self._vm.is_quiet_mode,
            sampling_interval_s=self._vm.sampling_interval_s,
            reminder_cooldown_min=self._vm.reminder_cooldown_min,
            error_message=err,
        )
        self._notify()

    def on_assessment_evaluated(
        self,
        result: RulaScoringResult,
        validity: ValidityReport,
    ) -> None:
        """Processes evaluated posture results and updates visual display."""
        now = time.time()
        last_update_str = "Just now"

        if not validity.is_valid or not result.is_valid:
            # Low confidence or insufficient geometry -> NO score displayed
            rec = "Not enough reliable posture information to calculate a score."
            if validity.status == ValidityStatus.INSUFFICIENT and validity.reason_codes:
                first_reason = validity.reason_codes[0].replace("_", " ").title()
                rec = f"Posture partially occluded ({first_reason})."

            self._vm = OverlayViewModel(
                state=OverlayState.LOW_CONFIDENCE,
                score_text="—",
                category_text="—",
                recommendation=rec,
                last_updated_text=last_update_str,
                sync_status_text=self._vm.sync_status_text,
                privacy_indicator_text=self._vm.privacy_indicator_text,
                is_paused=self._vm.is_paused,
                is_quiet_mode=self._vm.is_quiet_mode,
                sampling_interval_s=self._vm.sampling_interval_s,
                reminder_cooldown_min=self._vm.reminder_cooldown_min,
                error_message=None,
            )
            self._notify()
            return

        # Valid observation with a real RULA score
        score_val = result.grand_score
        score_text = f"RULA {score_val}" if score_val is not None else "—"

        cat_text = "—"
        if result.action_level == 1:
            cat_text = "Acceptable Posture"
        elif result.action_level == 2:
            cat_text = "Further Investigation"
        elif result.action_level == 3:
            cat_text = "Changes Recommended Soon"
        elif result.action_level == 4:
            cat_text = "Intervention Required"

        # Check quiet mode and reminder cooldown
        cooldown_s = self._vm.reminder_cooldown_min * 60.0
        time_since_last_rec = now - self._last_recommendation_time

        if self._vm.is_quiet_mode:
            rec = "Quiet mode active — ergonomic monitoring continuing in background."
        elif time_since_last_rec < cooldown_s and self._last_recommendation_time > 0:
            rec = self._vm.recommendation  # Keep previous recommendation during cooldown
        else:
            rec = (
                result.recommendations[0]
                if result.recommendations
                else "Maintain neutral positioning."
            )
            self._last_recommendation_time = now

        self._vm = OverlayViewModel(
            state=OverlayState.ACTIVE,
            score_text=score_text,
            category_text=cat_text,
            recommendation=rec,
            last_updated_text=last_update_str,
            sync_status_text=self._vm.sync_status_text,
            privacy_indicator_text=self._vm.privacy_indicator_text,
            is_paused=False,
            is_quiet_mode=self._vm.is_quiet_mode,
            sampling_interval_s=self._vm.sampling_interval_s,
            reminder_cooldown_min=self._vm.reminder_cooldown_min,
            error_message=None,
        )
        self._notify()

    def on_sync_status_changed(self, status_text: str) -> None:
        """Updates synchronization status text."""
        self.update_sync_status(sync_text=status_text)

    def update_sync_status(
        self,
        sync_text: str,
        queue_depth: int | None = None,
        last_sync_text: str | None = None,
        state: OverlayState | None = None,
        error_message: str | None = None,
    ) -> None:
        """Updates synchronization indicators, queue depth, and status states."""
        new_depth = queue_depth if queue_depth is not None else self._vm.queue_depth
        new_last_sync = last_sync_text or self._vm.last_sync_text
        new_state = state or self._vm.state
        err = error_message if error_message is not None else self._vm.error_message

        self._vm = OverlayViewModel(
            state=new_state,
            score_text=self._vm.score_text,
            category_text=self._vm.category_text,
            recommendation=self._vm.recommendation,
            last_updated_text=self._vm.last_updated_text,
            sync_status_text=sync_text,
            queue_depth=new_depth,
            last_sync_text=new_last_sync,
            privacy_indicator_text=self._vm.privacy_indicator_text,
            is_paused=self._vm.is_paused,
            is_quiet_mode=self._vm.is_quiet_mode,
            sampling_interval_s=self._vm.sampling_interval_s,
            reminder_cooldown_min=self._vm.reminder_cooldown_min,
            error_message=err,
        )
        self._notify()

    def toggle_pause(self) -> bool:
        """Toggles pause state and returns new paused status."""
        new_paused = not self._vm.is_paused
        new_state = OverlayState.PAUSED if new_paused else OverlayState.ACTIVE
        self._vm = OverlayViewModel(
            state=new_state,
            score_text=self._vm.score_text,
            category_text=self._vm.category_text,
            recommendation="Analysis paused by user." if new_paused else self._vm.recommendation,
            last_updated_text=self._vm.last_updated_text,
            sync_status_text=self._vm.sync_status_text,
            privacy_indicator_text=self._vm.privacy_indicator_text,
            is_paused=new_paused,
            is_quiet_mode=self._vm.is_quiet_mode,
            sampling_interval_s=self._vm.sampling_interval_s,
            reminder_cooldown_min=self._vm.reminder_cooldown_min,
            error_message=None,
        )
        self._notify()
        return new_paused

    def toggle_quiet_mode(self) -> bool:
        """Toggles quiet mode state."""
        new_quiet = not self._vm.is_quiet_mode
        self._vm = OverlayViewModel(
            state=self._vm.state,
            score_text=self._vm.score_text,
            category_text=self._vm.category_text,
            recommendation=(
                "Quiet mode active — notifications suppressed."
                if new_quiet
                else "Quiet mode disabled."
            ),
            last_updated_text=self._vm.last_updated_text,
            sync_status_text=self._vm.sync_status_text,
            privacy_indicator_text=self._vm.privacy_indicator_text,
            is_paused=self._vm.is_paused,
            is_quiet_mode=new_quiet,
            sampling_interval_s=self._vm.sampling_interval_s,
            reminder_cooldown_min=self._vm.reminder_cooldown_min,
            error_message=self._vm.error_message,
        )
        self._notify()
        return new_quiet

    def update_settings(
        self,
        sampling_interval_s: float,
        reminder_cooldown_min: int,
        quiet_mode: bool,
    ) -> None:
        """Updates user preferences."""
        self._vm = OverlayViewModel(
            state=self._vm.state,
            score_text=self._vm.score_text,
            category_text=self._vm.category_text,
            recommendation=self._vm.recommendation,
            last_updated_text=self._vm.last_updated_text,
            sync_status_text=self._vm.sync_status_text,
            privacy_indicator_text=self._vm.privacy_indicator_text,
            is_paused=self._vm.is_paused,
            is_quiet_mode=quiet_mode,
            sampling_interval_s=max(1.0, sampling_interval_s),
            reminder_cooldown_min=max(1, reminder_cooldown_min),
            error_message=self._vm.error_message,
        )
        self._notify()
