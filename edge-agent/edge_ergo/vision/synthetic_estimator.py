"""Synthetic pose estimator producing deterministic postures for testing and simulation."""

from __future__ import annotations

import time

from edge_ergo.camera.types import CameraFrame
from edge_ergo.vision.base import PoseEstimator
from edge_ergo.vision.landmarks import (
    NormalizedLandmark,
    PoseLandmarkIndex,
    RawPoseLandmarks,
)
from edge_ergo.vision.types import PoseEstimationResult, PoseEstimationStatus


def create_neutral_landmarks(visibility: float = 0.95) -> list[NormalizedLandmark]:
    """Generates 33 landmarks representing an ergonomically neutral seated posture."""
    # 33 landmarks initialized to zero
    landmarks = [
        NormalizedLandmark(x=0.5, y=0.5, z=0.0, visibility=visibility, presence=visibility)
        for _ in range(33)
    ]

    # Torso and head geometry (normalized coordinates 0.0 - 1.0)
    # Head & Neck
    landmarks[PoseLandmarkIndex.NOSE] = NormalizedLandmark(0.50, 0.20, 0.0, visibility, visibility)
    landmarks[PoseLandmarkIndex.LEFT_EYE] = NormalizedLandmark(
        0.48, 0.18, 0.0, visibility, visibility
    )
    landmarks[PoseLandmarkIndex.RIGHT_EYE] = NormalizedLandmark(
        0.52, 0.18, 0.0, visibility, visibility
    )
    landmarks[PoseLandmarkIndex.LEFT_EAR] = NormalizedLandmark(
        0.44, 0.19, 0.0, visibility, visibility
    )
    landmarks[PoseLandmarkIndex.RIGHT_EAR] = NormalizedLandmark(
        0.56, 0.19, 0.0, visibility, visibility
    )

    # Shoulders (level across horizontal axis)
    landmarks[PoseLandmarkIndex.LEFT_SHOULDER] = NormalizedLandmark(
        0.40, 0.32, 0.0, visibility, visibility
    )
    landmarks[PoseLandmarkIndex.RIGHT_SHOULDER] = NormalizedLandmark(
        0.60, 0.32, 0.0, visibility, visibility
    )

    # Elbows (at ~90 degree typing posture)
    landmarks[PoseLandmarkIndex.LEFT_ELBOW] = NormalizedLandmark(
        0.40, 0.50, 0.0, visibility, visibility
    )
    landmarks[PoseLandmarkIndex.RIGHT_ELBOW] = NormalizedLandmark(
        0.60, 0.50, 0.0, visibility, visibility
    )

    # Wrists (resting forward near keyboard at elbow height)
    landmarks[PoseLandmarkIndex.LEFT_WRIST] = NormalizedLandmark(
        0.48, 0.50, 0.0, visibility, visibility
    )
    landmarks[PoseLandmarkIndex.RIGHT_WRIST] = NormalizedLandmark(
        0.52, 0.50, 0.0, visibility, visibility
    )

    # Hips (aligned vertically beneath shoulders)
    landmarks[PoseLandmarkIndex.LEFT_HIP] = NormalizedLandmark(
        0.42, 0.70, 0.0, visibility, visibility
    )
    landmarks[PoseLandmarkIndex.RIGHT_HIP] = NormalizedLandmark(
        0.58, 0.70, 0.0, visibility, visibility
    )

    return landmarks


class SyntheticPoseEstimator(PoseEstimator):
    """Produces deterministic pose landmarks for headless tests and simulated runs."""

    def __init__(self, mode: str = "neutral") -> None:
        self.mode = mode
        self._is_open = True

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def estimate(self, frame: CameraFrame) -> PoseEstimationResult:
        start_t = time.monotonic()

        if self.mode == "no_pose":
            return PoseEstimationResult(
                status=PoseEstimationStatus.NO_POSE_DETECTED,
                landmarks=None,
                inference_latency_ms=1.5,
            )

        if self.mode == "error":
            return PoseEstimationResult(
                status=PoseEstimationStatus.MODEL_ERROR,
                landmarks=None,
                inference_latency_ms=1.0,
                error_message="Simulated model failure",
            )

        landmarks = create_neutral_landmarks(visibility=0.95)

        if self.mode == "neck_flexed":
            # Push nose and ears forward/down relative to shoulders
            landmarks[PoseLandmarkIndex.NOSE] = NormalizedLandmark(0.50, 0.28, 0.2, 0.95, 0.95)
            landmarks[PoseLandmarkIndex.LEFT_EAR] = NormalizedLandmark(0.44, 0.26, 0.15, 0.95, 0.95)
            landmarks[PoseLandmarkIndex.RIGHT_EAR] = NormalizedLandmark(
                0.56, 0.26, 0.15, 0.95, 0.95
            )

        elif self.mode == "slouching":
            # Lean shoulders forward relative to hips
            landmarks[PoseLandmarkIndex.LEFT_SHOULDER] = NormalizedLandmark(
                0.40, 0.38, 0.25, 0.95, 0.95
            )
            landmarks[PoseLandmarkIndex.RIGHT_SHOULDER] = NormalizedLandmark(
                0.60, 0.38, 0.25, 0.95, 0.95
            )

        elif self.mode == "shoulder_shrug":
            # Raise shoulders significantly closer to ears
            landmarks[PoseLandmarkIndex.LEFT_SHOULDER] = NormalizedLandmark(
                0.40, 0.23, 0.0, 0.95, 0.95
            )
            landmarks[PoseLandmarkIndex.RIGHT_SHOULDER] = NormalizedLandmark(
                0.60, 0.23, 0.0, 0.95, 0.95
            )

        elif self.mode == "arm_elevated":
            # Elevate elbows high above desk level
            landmarks[PoseLandmarkIndex.LEFT_ELBOW] = NormalizedLandmark(
                0.32, 0.30, 0.0, 0.95, 0.95
            )
            landmarks[PoseLandmarkIndex.RIGHT_ELBOW] = NormalizedLandmark(
                0.68, 0.30, 0.0, 0.95, 0.95
            )

        elif self.mode == "occluded":
            # Right arm occluded with low visibility (< 0.2)
            landmarks[PoseLandmarkIndex.RIGHT_ELBOW] = NormalizedLandmark(
                0.62, 0.50, 0.0, 0.15, 0.15
            )
            landmarks[PoseLandmarkIndex.RIGHT_WRIST] = NormalizedLandmark(
                0.56, 0.58, 0.0, 0.10, 0.10
            )

        latency = (time.monotonic() - start_t) * 1000.0
        return PoseEstimationResult(
            status=PoseEstimationStatus.SUCCESS,
            landmarks=RawPoseLandmarks(landmarks),
            inference_latency_ms=latency + 2.0,
        )

    def close(self) -> None:
        self._is_open = False
