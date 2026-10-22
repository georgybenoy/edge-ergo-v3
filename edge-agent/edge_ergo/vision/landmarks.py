"""Landmark indices and privacy-guarded RawPoseLandmarks representation.

CRITICAL PRIVACY DIRECTIVE:
Raw landmarks must NEVER leave the vision -> features boundary.
RawPoseLandmarks has NO __repr__ or __str__ displaying coordinate numbers to
guarantee that landmarks are never leaked into logfiles, traces, or databases.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum


class PoseLandmarkIndex(IntEnum):
    """Standard 33 MediaPipe pose landmark indices."""

    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


@dataclass(frozen=True)
class NormalizedLandmark:
    """Individual normalized pose landmark coordinate with confidence."""

    x: float
    y: float
    z: float
    visibility: float
    presence: float = 1.0


class RawPoseLandmarks:
    """Privacy-guarded container for 33 normalized body landmarks.

    Guarantees:
    - __repr__ and __str__ display ZERO coordinate numbers or vectors.
    - Used strictly as an in-memory ephemeral boundary between vision, quality,
      and feature calculation.
    """

    def __init__(self, landmarks: Sequence[NormalizedLandmark]) -> None:
        self._landmarks = tuple(landmarks)

    def get(self, index: int | PoseLandmarkIndex) -> NormalizedLandmark | None:
        """Retrieves landmark by index, or None if index out of bounds."""
        idx = int(index)
        if 0 <= idx < len(self._landmarks):
            return self._landmarks[idx]
        return None

    def is_visible(self, index: int | PoseLandmarkIndex, threshold: float = 0.5) -> bool:
        """Checks if the landmark at index meets or exceeds visibility threshold."""
        lm = self.get(index)
        return lm is not None and lm.visibility >= threshold

    def count(self) -> int:
        """Returns total landmark count (typically 33)."""
        return len(self._landmarks)

    def __len__(self) -> int:
        return len(self._landmarks)

    def __repr__(self) -> str:
        """Redacts all coordinates to enforce privacy data boundaries."""
        return f"<RawPoseLandmarks count={len(self._landmarks)} [coordinates redacted for privacy]>"

    def __str__(self) -> str:
        return self.__repr__()
