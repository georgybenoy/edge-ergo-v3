"""CameraSource abstract base class interface for EdgeErgo V3."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from edge_ergo.camera.types import CameraFrame, CameraState


class CameraSource(ABC):
    """Abstract interface defining camera hardware capture and lifecycle."""

    @abstractmethod
    def open(self) -> bool:
        """Initializes and opens the camera device."""

    @abstractmethod
    def close(self) -> None:
        """Closes the camera device and releases all hardware resources."""

    @abstractmethod
    def is_open(self) -> bool:
        """Returns True if the camera device is currently open and accessible."""

    @abstractmethod
    def read_frame(self) -> CameraFrame | None:
        """Reads the next available frame in RGB format, or returns None if paused/empty."""

    @abstractmethod
    def get_state(self) -> CameraState:
        """Returns the current state of the camera source."""

    @abstractmethod
    def pause(self) -> None:
        """Temporarily suspends frame acquisition without closing hardware handles."""

    @abstractmethod
    def resume(self) -> None:
        """Resumes frame acquisition following a pause."""

    def __enter__(self) -> CameraSource:
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
