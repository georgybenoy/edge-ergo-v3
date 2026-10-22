"""Typed camera states, frames, and exceptions for EdgeErgo V3.

Privacy Mandate: Camera frames are held strictly in transient memory.
__repr__ implementations redact all pixel matrices to prevent accidental logging.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy.typing as npt


class CameraState(str, Enum):
    """Lifecycle states of the camera input subsystem."""

    UNINITIALIZED = "uninitialized"
    OPENING = "opening"
    ACTIVE = "active"
    PAUSED = "paused"
    PERMISSION_DENIED = "permission_denied"
    DISCONNECTED = "disconnected"
    IN_USE = "in_use"
    ERROR = "error"
    CLOSED = "closed"


class CameraError(Exception):
    """Base class for all camera subsystem failures."""


class CameraPermissionError(CameraError):
    """Camera access was explicitly denied by OS privacy permissions."""


class CameraNotFoundError(CameraError):
    """Requested video device index was not found or has been physically unplugged."""


class CameraInUseError(CameraError):
    """Camera device is locked exclusively by another application (e.g. Teams, Zoom)."""


class CameraTimeoutError(CameraError):
    """Camera frame acquisition timed out without receiving new frames."""


class CameraReadError(CameraError):
    """Low-level error reading frame buffer from camera driver."""


@dataclass(frozen=True)
class CameraFrame:
    """Transient in-memory camera frame representation.

    Pixel buffers are never serialized, logged, or saved to persistent disk.
    """

    data: npt.NDArray[Any]  # Shape: (H, W, 3) in RGB format
    timestamp: float  # Epoch seconds
    frame_id: int
    width: int
    height: int

    def __repr__(self) -> str:
        """Sanitized representation guaranteeing raw image pixels are never logged."""
        return (
            f"<CameraFrame id={self.frame_id} "
            f"dims={self.width}x{self.height} "
            f"ts={self.timestamp:.3f} "
            f"[in-memory only - pixels redacted]>"
        )

    def __str__(self) -> str:
        return self.__repr__()
