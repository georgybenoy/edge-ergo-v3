"""PoseEstimator abstract base interface for EdgeErgo V3."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from edge_ergo.camera.types import CameraFrame
from edge_ergo.vision.types import PoseEstimationResult


class PoseEstimator(ABC):
    """Abstract interface defining local on-device pose estimation inference."""

    @abstractmethod
    def estimate(self, frame: CameraFrame) -> PoseEstimationResult:
        """Performs pose estimation on an in-memory CameraFrame."""

    @abstractmethod
    def close(self) -> None:
        """Releases underlying model resources and accelerators."""

    def __enter__(self) -> PoseEstimator:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
