"""Vision and pose estimation subsystem for EdgeErgo V3."""

from __future__ import annotations

from edge_ergo.vision.base import PoseEstimator
from edge_ergo.vision.landmarks import (
    NormalizedLandmark,
    PoseLandmarkIndex,
    RawPoseLandmarks,
)
from edge_ergo.vision.mediapipe_estimator import MediaPipePoseEstimator, resolve_model_path
from edge_ergo.vision.synthetic_estimator import SyntheticPoseEstimator, create_neutral_landmarks
from edge_ergo.vision.types import PoseEstimationResult, PoseEstimationStatus

__all__ = [
    "MediaPipePoseEstimator",
    "NormalizedLandmark",
    "PoseEstimationResult",
    "PoseEstimationStatus",
    "PoseEstimator",
    "PoseLandmarkIndex",
    "RawPoseLandmarks",
    "SyntheticPoseEstimator",
    "create_neutral_landmarks",
    "resolve_model_path",
]
