"""Camera capture subsystem for EdgeErgo V3."""

from __future__ import annotations

from edge_ergo.camera.base import CameraSource
from edge_ergo.camera.fake_source import FakeCameraSource
from edge_ergo.camera.opencv_source import OpenCVCameraSource
from edge_ergo.camera.types import (
    CameraError,
    CameraFrame,
    CameraInUseError,
    CameraNotFoundError,
    CameraPermissionError,
    CameraReadError,
    CameraState,
    CameraTimeoutError,
)

__all__ = [
    "CameraError",
    "CameraFrame",
    "CameraInUseError",
    "CameraNotFoundError",
    "CameraPermissionError",
    "CameraReadError",
    "CameraSource",
    "CameraState",
    "CameraTimeoutError",
    "FakeCameraSource",
    "OpenCVCameraSource",
]
