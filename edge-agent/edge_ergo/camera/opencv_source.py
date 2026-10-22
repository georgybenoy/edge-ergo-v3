"""OpenCV webcam implementation of CameraSource for EdgeErgo V3.

Guarantees:
- Captures frames in volatile RAM, converts BGR to RGB, and passes strictly in-memory.
- ZERO disk writes: no temporary files, no capture folders, no video files.
- Thread-safe lifecycle with explicit open, close, pause, and resume.
- Bounded retry backoff when camera disconnected.
"""

from __future__ import annotations

import logging
import random
import threading
import time

import cv2

from edge_ergo.camera.base import CameraSource
from edge_ergo.camera.types import (
    CameraFrame,
    CameraState,
    CameraTimeoutError,
)

logger = logging.getLogger(__name__)


class OpenCVCameraSource(CameraSource):
    """OpenCV-backed webcam capture source with resilient reconnection."""

    def __init__(
        self,
        device_index: int = 0,
        target_width: int = 640,
        target_height: int = 480,
        target_fps: float = 15.0,
        read_timeout_s: float = 2.0,
        max_reconnect_attempts: int = 5,
        base_backoff_s: float = 0.5,
    ) -> None:
        self._device_index = device_index
        self._target_width = target_width
        self._target_height = target_height
        self._target_fps = target_fps
        self._read_timeout_s = read_timeout_s
        self._max_reconnect_attempts = max_reconnect_attempts
        self._base_backoff_s = base_backoff_s

        self._cap: cv2.VideoCapture | None = None
        self._state = CameraState.UNINITIALIZED
        self._lock = threading.Lock()
        self._frame_count = 0
        self._reconnect_count = 0
        self._last_frame_time = 0.0

    def open(self) -> bool:
        """Initializes and opens the video capture device."""
        with self._lock:
            if (
                self._state in (CameraState.ACTIVE, CameraState.PAUSED)
                and self._cap
                and self._cap.isOpened()
            ):
                return True

            self._state = CameraState.OPENING
            logger.info("Opening webcam at device index %d...", self._device_index)

            # On Windows, cv2.CAP_DSHOW provides fast, reliable initialization without hanging
            try:
                cap = cv2.VideoCapture(self._device_index, cv2.CAP_DSHOW)
            except Exception:
                cap = cv2.VideoCapture(self._device_index)

            if not cap.isOpened():
                cap.release()
                self._state = CameraState.DISCONNECTED
                logger.warning(
                    "Camera at index %d could not be opened (not found or in use)",
                    self._device_index,
                )
                return False

            # Request desired frame properties
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._target_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._target_height)
            cap.set(cv2.CAP_PROP_FPS, self._target_fps)

            # Warm-up grab to confirm readiness
            ret, _ = cap.read()
            if not ret:
                cap.release()
                self._state = CameraState.ERROR
                logger.warning("Camera opened but failed initial frame read probe")
                return False

            self._cap = cap
            self._state = CameraState.ACTIVE
            self._reconnect_count = 0
            logger.info(
                "Webcam opened successfully at index %d (%dx%d)",
                self._device_index,
                self._target_width,
                self._target_height,
            )
            return True

    def close(self) -> None:
        """Releases the camera device and all associated driver resources."""
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception as exc:
                    logger.debug("Exception while releasing cv2.VideoCapture: %s", exc)
                self._cap = None
            self._state = CameraState.CLOSED
            logger.info("Webcam device index %d closed.", self._device_index)

    def is_open(self) -> bool:
        with self._lock:
            return (
                self._state in (CameraState.ACTIVE, CameraState.PAUSED)
                and self._cap is not None
                and self._cap.isOpened()
            )

    def get_state(self) -> CameraState:
        with self._lock:
            return self._state

    def pause(self) -> None:
        """Pauses frame delivery without releasing hardware handle."""
        with self._lock:
            if self._state == CameraState.ACTIVE:
                self._state = CameraState.PAUSED
                logger.info("Camera paused.")

    def resume(self) -> None:
        """Resumes active frame delivery."""
        with self._lock:
            if self._state == CameraState.PAUSED:
                self._state = CameraState.ACTIVE
                logger.info("Camera resumed.")

    def read_frame(self) -> CameraFrame | None:
        """Reads a frame, converts BGR to RGB in memory, and returns CameraFrame.

        Returns None if paused, uninitialized, or transient error.
        Raises typed CameraError on persistent failures.
        """
        with self._lock:
            if self._state == CameraState.PAUSED:
                return None

            if self._state != CameraState.ACTIVE or self._cap is None or not self._cap.isOpened():
                if not self._attempt_reconnect_locked():
                    return None

            cap = self._cap
            if cap is None:
                return None

            start_t = time.monotonic()
            ret, bgr_frame = cap.read()

            if not ret or bgr_frame is None or bgr_frame.size == 0:
                elapsed = time.monotonic() - start_t
                if elapsed > self._read_timeout_s:
                    self._state = CameraState.DISCONNECTED
                    logger.warning("Camera read timed out after %.2fs", elapsed)
                    raise CameraTimeoutError("Webcam frame acquisition timed out")

                # Frame drop or transient read glitch
                logger.debug("Transient frame read failure on device %d", self._device_index)
                return None

            # In-memory color space conversion: BGR -> RGB
            rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            h, w = rgb_frame.shape[:2]

            self._frame_count += 1
            now = time.time()
            self._last_frame_time = now

            # Discard local reference to raw BGR frame immediately
            del bgr_frame

            return CameraFrame(
                data=rgb_frame,
                timestamp=now,
                frame_id=self._frame_count,
                width=w,
                height=h,
            )

    def _attempt_reconnect_locked(self) -> bool:
        """Attempts reconnect with exponential backoff and random jitter."""
        if self._reconnect_count >= self._max_reconnect_attempts:
            self._state = CameraState.DISCONNECTED
            logger.error("Camera reconnect failed after %d attempts", self._max_reconnect_attempts)
            return False

        self._reconnect_count += 1
        delay = self._base_backoff_s * (2 ** (self._reconnect_count - 1)) + random.uniform(
            0.05, 0.2
        )
        logger.info(
            "Attempting camera reconnect #%d after %.2fs delay...", self._reconnect_count, delay
        )
        time.sleep(delay)

        if self._cap is not None:
            self._cap.release()
            self._cap = None

        try:
            cap = cv2.VideoCapture(self._device_index, cv2.CAP_DSHOW)
        except Exception:
            cap = cv2.VideoCapture(self._device_index)

        if cap.isOpened():
            self._cap = cap
            self._state = CameraState.ACTIVE
            self._reconnect_count = 0
            logger.info("Camera reconnected successfully.")
            return True

        cap.release()
        return False
