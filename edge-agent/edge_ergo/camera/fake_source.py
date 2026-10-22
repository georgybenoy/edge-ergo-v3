"""FakeCameraSource generating synthetic in-memory frames for tests and dry-run mode."""

from __future__ import annotations

import threading
import time

import numpy as np

from edge_ergo.camera.base import CameraSource
from edge_ergo.camera.types import (
    CameraFrame,
    CameraPermissionError,
    CameraState,
)


class FakeCameraSource(CameraSource):
    """Deterministic, synthetic camera source for unit testing and headless simulation.

    Generates synthetic geometric gradient images in volatile RAM.
    Zero real camera hardware dependency; zero disk persistence.
    """

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        fps: float = 15.0,
        simulate_permission_denied: bool = False,
        simulate_disconnect_after: int | None = None,
    ) -> None:
        self._width = width
        self._height = height
        self._fps = fps
        self._simulate_permission_denied = simulate_permission_denied
        self._simulate_disconnect_after = simulate_disconnect_after

        self._state = CameraState.UNINITIALIZED
        self._lock = threading.Lock()
        self._frame_count = 0
        self._is_open = False

    def open(self) -> bool:
        with self._lock:
            if self._simulate_permission_denied:
                self._state = CameraState.PERMISSION_DENIED
                raise CameraPermissionError("OS camera permission denied (simulated)")

            self._state = CameraState.ACTIVE
            self._is_open = True
            return True

    def close(self) -> None:
        with self._lock:
            self._state = CameraState.CLOSED
            self._is_open = False

    def is_open(self) -> bool:
        with self._lock:
            return self._is_open

    def get_state(self) -> CameraState:
        with self._lock:
            return self._state

    def pause(self) -> None:
        with self._lock:
            if self._state == CameraState.ACTIVE:
                self._state = CameraState.PAUSED

    def resume(self) -> None:
        with self._lock:
            if self._state == CameraState.PAUSED:
                self._state = CameraState.ACTIVE

    def read_frame(self) -> CameraFrame | None:
        with self._lock:
            if not self._is_open or self._state == CameraState.PAUSED:
                return None

            if (
                self._simulate_disconnect_after is not None
                and self._frame_count >= self._simulate_disconnect_after
            ):
                self._state = CameraState.DISCONNECTED
                return None

            self._frame_count += 1
            now = time.time()

            # Create synthetic geometric frame in memory (RGB gradient)
            # Subtle animated gradient based on frame count
            x = np.linspace(0, 255, self._width, dtype=np.uint8)
            y = np.linspace(0, 255, self._height, dtype=np.uint8)
            xx, yy = np.meshgrid(x, y)
            r = ((xx + (self._frame_count * 5)) % 256).astype(np.uint8)
            g = yy
            b = np.full((self._height, self._width), 128, dtype=np.uint8)
            synthetic_rgb = np.stack([r, g, b], axis=-1)

            return CameraFrame(
                data=synthetic_rgb,
                timestamp=now,
                frame_id=self._frame_count,
                width=self._width,
                height=self._height,
            )
