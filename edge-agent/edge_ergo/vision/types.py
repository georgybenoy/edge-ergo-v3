"""Typed results and status enumerations for edge pose estimation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from edge_ergo.vision.landmarks import RawPoseLandmarks


class PoseEstimationStatus(str, Enum):
    """Outcomes of on-device pose estimation inference."""

    SUCCESS = "success"
    NO_POSE_DETECTED = "no_pose_detected"
    LOW_CONFIDENCE = "low_confidence"
    MODEL_ERROR = "model_error"
    INVALID_IMAGE = "invalid_image"


@dataclass(frozen=True)
class PoseEstimationResult:
    """Encapsulates the typed outcome of a pose estimation inference step."""

    status: PoseEstimationStatus
    landmarks: RawPoseLandmarks | None
    inference_latency_ms: float
    error_message: str | None = None

    def __repr__(self) -> str:
        """Sanitized string representation preserving user privacy."""
        has_landmarks = self.landmarks is not None
        return (
            f"<PoseEstimationResult status={self.status.value} "
            f"has_landmarks={has_landmarks} "
            f"latency={self.inference_latency_ms:.1f}ms>"
        )

    def __str__(self) -> str:
        return self.__repr__()
