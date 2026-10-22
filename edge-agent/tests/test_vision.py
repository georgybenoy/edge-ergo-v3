"""Tests for vision subsystem and landmark privacy boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest

from edge_ergo.camera.fake_source import FakeCameraSource
from edge_ergo.vision.landmarks import (
    PoseLandmarkIndex,
    RawPoseLandmarks,
)
from edge_ergo.vision.mediapipe_estimator import (
    MediaPipePoseEstimator,
    resolve_model_path,
)
from edge_ergo.vision.synthetic_estimator import (
    SyntheticPoseEstimator,
    create_neutral_landmarks,
)
from edge_ergo.vision.types import PoseEstimationStatus


def test_raw_landmarks_privacy_redaction() -> None:
    """Critical Privacy Test: Raw landmark coordinates must NEVER be rendered in repr or str."""
    raw_list = create_neutral_landmarks(visibility=0.9)
    landmarks = RawPoseLandmarks(raw_list)

    assert landmarks.count() == 33
    assert len(landmarks) == 33

    rep = repr(landmarks)
    str_rep = str(landmarks)

    assert "coordinates redacted for privacy" in rep
    assert "coordinates redacted for privacy" in str_rep

    # Verify no float coordinates appear in the representation
    for lm in raw_list:
        assert f"{lm.x:.2f}" not in rep
        assert f"{lm.y:.2f}" not in rep
        assert f"{lm.z:.2f}" not in rep

    # Verify accessors
    nose = landmarks.get(PoseLandmarkIndex.NOSE)
    assert nose is not None
    assert nose.visibility >= 0.5
    assert landmarks.is_visible(PoseLandmarkIndex.NOSE, threshold=0.5) is True
    assert landmarks.is_visible(PoseLandmarkIndex.NOSE, threshold=0.99) is False

    # Out of bounds returns None
    assert landmarks.get(999) is None


def test_synthetic_pose_estimator_modes() -> None:
    """Verifies all synthetic posture modes supported by SyntheticPoseEstimator."""
    estimator = SyntheticPoseEstimator(mode="neutral")
    cam = FakeCameraSource()
    cam.open()
    frame = cam.read_frame()
    assert frame is not None

    # 1. Neutral mode
    res_neutral = estimator.estimate(frame)
    assert res_neutral.status == PoseEstimationStatus.SUCCESS
    assert res_neutral.landmarks is not None
    assert res_neutral.inference_latency_ms > 0

    # 2. No pose mode
    estimator.set_mode("no_pose")
    res_nopose = estimator.estimate(frame)
    assert res_nopose.status == PoseEstimationStatus.NO_POSE_DETECTED
    assert res_nopose.landmarks is None

    # 3. Model error mode
    estimator.set_mode("error")
    res_err = estimator.estimate(frame)
    assert res_err.status == PoseEstimationStatus.MODEL_ERROR
    assert res_err.error_message == "Simulated model failure"

    # 4. Posture variation modes
    for m in ("neck_flexed", "slouching", "shoulder_shrug", "arm_elevated", "occluded"):
        estimator.set_mode(m)
        res = estimator.estimate(frame)
        assert res.status == PoseEstimationStatus.SUCCESS
        assert res.landmarks is not None

    cam.close()
    estimator.close()


def test_mediapipe_model_resolution_and_offline_integrity() -> None:
    """Verifies that the MediaPipe model asset is packaged locally and offline."""
    model_path = resolve_model_path()
    assert model_path.is_file()
    assert model_path.suffix == ".task"
    assert model_path.stat().st_size > 1_000_000  # ~5.7 MB

    # Missing model file raises FileNotFoundError with explicit error message
    with pytest.raises(FileNotFoundError, match="strictly prohibits silent runtime downloads"):
        resolve_model_path(custom_path=Path("non_existent_model_dir/missing.task"))


def test_mediapipe_pose_estimator_inference() -> None:
    """Executes live MediaPipePoseEstimator on an in-memory synthetic frame."""
    estimator = MediaPipePoseEstimator()
    cam = FakeCameraSource()
    cam.open()
    frame = cam.read_frame()
    assert frame is not None

    result = estimator.estimate(frame)
    assert isinstance(result.status, PoseEstimationStatus)
    assert result.inference_latency_ms >= 0.0

    cam.close()
    estimator.close()
