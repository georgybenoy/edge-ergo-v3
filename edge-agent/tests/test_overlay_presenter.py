"""Headless unit tests for OverlayPresenter and view-model state transitions."""

from __future__ import annotations

from edge_ergo.camera.types import CameraState
from edge_ergo.overlay.presenter import OverlayPresenter
from edge_ergo.overlay.types import OverlayState
from edge_ergo.quality.types import ValidityReport, ValidityStatus
from edge_ergo.scoring.types import ActionLevel, RulaScoringResult


def test_overlay_presenter_initial_state() -> None:
    """Verifies default initial view model state."""
    presenter = OverlayPresenter()
    vm = presenter.view_model

    assert vm.state == OverlayState.READY
    assert vm.score_text == "—"
    assert vm.category_text == "—"
    assert not vm.is_paused
    assert not vm.is_quiet_mode
    assert vm.sampling_interval_s == 5.0
    assert vm.reminder_cooldown_min == 15


def test_overlay_camera_state_transitions() -> None:
    """Verifies overlay reactions to camera lifecycle events."""
    presenter = OverlayPresenter()

    # Active
    presenter.on_camera_state_changed(CameraState.ACTIVE)
    vm_active = presenter.view_model
    assert vm_active.state == OverlayState.ACTIVE

    # Paused
    presenter.on_camera_state_changed(CameraState.PAUSED)
    vm_paused = presenter.view_model
    assert vm_paused.state == OverlayState.PAUSED
    assert vm_paused.is_paused is True

    # Camera unavailable
    presenter.on_camera_state_changed(CameraState.DISCONNECTED)
    vm_disc = presenter.view_model
    assert vm_disc.state == OverlayState.CAMERA_UNAVAILABLE
    assert "Camera unavailable" in str(vm_disc.error_message)

    # Permission denied
    presenter.on_camera_state_changed(CameraState.PERMISSION_DENIED)
    vm_perm = presenter.view_model
    assert vm_perm.state == OverlayState.CAMERA_UNAVAILABLE

    # Error
    presenter.on_camera_state_changed(CameraState.ERROR)
    vm_err = presenter.view_model
    assert vm_err.state == OverlayState.ERROR


def test_overlay_valid_posture_evaluation() -> None:
    """Verifies that a valid RULA score updates metric labels and guidance."""
    presenter = OverlayPresenter()
    validity = ValidityReport(status=ValidityStatus.VALID)
    result = RulaScoringResult(
        is_valid=True,
        grand_score=3,
        action_level=int(ActionLevel.LEVEL_2),
        recommendations=["Try adjusting monitor height."],
        guidance_codes=["GUID_NECK_FLEX_01"],
    )

    presenter.on_assessment_evaluated(result, validity)
    vm = presenter.view_model

    assert vm.state == OverlayState.ACTIVE
    assert vm.score_text == "RULA 3"
    assert vm.category_text == "Further Investigation"
    assert vm.recommendation == "Try adjusting monitor height."


def test_overlay_low_confidence_hides_score() -> None:
    """Critical UI Invariant: Low confidence / occluded observations MUST NOT display a score."""
    presenter = OverlayPresenter()
    validity = ValidityReport(
        status=ValidityStatus.INSUFFICIENT,
        reason_codes=["OCCLUSION_ARMS"],
    )
    result = RulaScoringResult(is_valid=False, grand_score=None)

    presenter.on_assessment_evaluated(result, validity)
    vm = presenter.view_model

    assert vm.state == OverlayState.LOW_CONFIDENCE
    assert vm.score_text == "—"
    assert vm.category_text == "—"
    assert "Occlusion Arms" in vm.recommendation


def test_overlay_pause_and_quiet_mode_toggles() -> None:
    """Verifies user pause and quiet mode toggle behaviors."""
    presenter = OverlayPresenter()

    # Toggle pause
    assert presenter.toggle_pause() is True
    assert presenter.view_model.is_paused is True
    assert presenter.view_model.state == OverlayState.PAUSED

    assert presenter.toggle_pause() is False
    assert presenter.view_model.is_paused is False
    assert presenter.view_model.state == OverlayState.ACTIVE

    # Toggle quiet mode
    assert presenter.toggle_quiet_mode() is True
    assert presenter.view_model.is_quiet_mode is True
    assert "Quiet mode active" in presenter.view_model.recommendation

    assert presenter.toggle_quiet_mode() is False
    assert presenter.view_model.is_quiet_mode is False


def test_overlay_settings_update() -> None:
    """Verifies updating user preferences via presenter."""
    presenter = OverlayPresenter()

    presenter.update_settings(
        sampling_interval_s=10.0,
        reminder_cooldown_min=30,
        quiet_mode=True,
    )

    vm = presenter.view_model
    assert vm.sampling_interval_s == 10.0
    assert vm.reminder_cooldown_min == 30
    assert vm.is_quiet_mode is True
