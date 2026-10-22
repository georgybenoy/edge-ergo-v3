"""Tests for the EdgeErgoApp background worker orchestrator."""

from __future__ import annotations

import time

from edge_ergo.app import EdgeErgoApp
from edge_ergo.camera.types import CameraState
from edge_ergo.features.types import PosturalFeatures
from edge_ergo.quality.types import ValidityReport
from edge_ergo.scoring.types import RulaScoringResult


def test_edge_ergo_app_simulation_lifecycle() -> None:
    """Verifies end-to-end background pipeline execution in simulation mode."""
    results_received: list[RulaScoringResult] = []
    validities_received: list[ValidityReport] = []

    def hook(
        res: RulaScoringResult,
        val: ValidityReport,
        feat: PosturalFeatures | None,
    ) -> None:
        results_received.append(res)
        validities_received.append(val)

    app = EdgeErgoApp(
        sampling_interval_s=0.2,  # Fast loop for tests
        fake_camera=True,
        synthetic_posture="neutral",
        on_assessment_hook=hook,
    )

    assert not app.is_running()
    started = app.start()
    assert started is True
    assert app.is_running()

    # Allow worker thread to run for at least 3 iterations (0.7s)
    time.sleep(0.7)

    # Pause
    app.pause()
    assert app.camera.get_state() == CameraState.PAUSED
    time.sleep(0.3)

    # Resume
    app.resume()
    assert app.camera.get_state() == CameraState.ACTIVE
    time.sleep(0.4)

    # Stop
    app.stop(timeout_s=2.0)
    assert not app.is_running()

    # Assertions on pipeline telemetry
    assert app.frames_captured >= 2
    assert len(results_received) >= 2

    # In neutral posture, once stabilized, result should be RULA 1
    stabilized_results = [r for r in results_received if r.is_valid]
    assert len(stabilized_results) > 0
    assert stabilized_results[0].grand_score == 1
    assert stabilized_results[0].scoring_method == "rula_partial"
    assert stabilized_results[0].scoring_version == "1.0.0"
