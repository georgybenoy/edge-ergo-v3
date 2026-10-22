"""MediaPipe PoseLandmarker Tasks API adapter for EdgeErgo V3.

Zero Runtime Download Guarantee:
Loads the bundled Apache-2.0 pose_landmarker_lite.task model asset strictly from
the local package path or PyInstaller bundle directory. If the model file is
missing, it fails fast with a clear exception; it NEVER initiates silent runtime downloads.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from edge_ergo.camera.types import CameraFrame
from edge_ergo.vision.base import PoseEstimator
from edge_ergo.vision.landmarks import NormalizedLandmark, RawPoseLandmarks
from edge_ergo.vision.types import PoseEstimationResult, PoseEstimationStatus

logger = logging.getLogger(__name__)


def resolve_model_path(custom_path: str | Path | None = None) -> Path:
    """Resolves local path to the pose_landmarker_lite.task model asset."""
    if custom_path:
        p = Path(custom_path)
        if p.is_file():
            return p
        raise FileNotFoundError(
            f"MediaPipe pose model asset was not found at specified path '{p}'. "
            "EdgeErgo V3 requires a pre-packaged model file and strictly prohibits silent runtime "
            "downloads."
        )

    # 1. Environment variable override
    env_path = os.environ.get("EDGE_ERGO_POSE_MODEL_PATH")
    if env_path and Path(env_path).is_file():
        return Path(env_path)

    # 2. PyInstaller frozen binary bundle
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_path = (
            Path(sys._MEIPASS) / "edge_ergo" / "vision" / "models" / "pose_landmarker_lite.task"
        )
        if meipass_path.is_file():
            return meipass_path

    # 3. Development package directory
    dev_path = Path(__file__).resolve().parent / "models" / "pose_landmarker_lite.task"
    if dev_path.is_file():
        return dev_path

    raise FileNotFoundError(
        f"MediaPipe pose model asset 'pose_landmarker_lite.task' was not found at {dev_path}. "
        "EdgeErgo V3 requires a pre-packaged model file and strictly prohibits silent runtime "
        "downloads. Ensure the model is placed in edge_ergo/vision/models/pose_landmarker_lite.task"
    )


class MediaPipePoseEstimator(PoseEstimator):
    """Local on-device pose estimation using MediaPipe PoseLandmarker."""

    def __init__(
        self,
        model_path: str | Path | None = None,
        min_pose_detection_confidence: float = 0.5,
        min_pose_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        self._model_path = resolve_model_path(model_path)
        self._min_detection = min_pose_detection_confidence
        self._min_presence = min_pose_presence_confidence
        self._min_tracking = min_tracking_confidence

        self._lock = threading.Lock()
        self._landmarker: vision.PoseLandmarker | None = None
        self._initialize_detector()

    def _initialize_detector(self) -> None:
        """Initializes the MediaPipe PoseLandmarker detector."""
        base_options = mp_python.BaseOptions(model_asset_path=str(self._model_path))
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=self._min_detection,
            min_pose_presence_confidence=self._min_presence,
            min_tracking_confidence=self._min_tracking,
            output_segmentation_masks=False,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        logger.info("Initialized MediaPipe PoseLandmarker from %s", self._model_path.name)

    def estimate(self, frame: CameraFrame) -> PoseEstimationResult:
        """Performs on-device inference on an in-memory CameraFrame."""
        with self._lock:
            if self._landmarker is None:
                return PoseEstimationResult(
                    status=PoseEstimationStatus.MODEL_ERROR,
                    landmarks=None,
                    inference_latency_ms=0.0,
                    error_message="Detector is closed or uninitialized",
                )

            start_t = time.monotonic()
            try:
                # Wrap volatile NumPy RGB array into MediaPipe Image format
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame.data)
                detection_result = self._landmarker.detect(mp_image)
            except Exception as exc:
                latency = (time.monotonic() - start_t) * 1000.0
                logger.error("MediaPipe inference failure: %s", exc, exc_info=True)
                return PoseEstimationResult(
                    status=PoseEstimationStatus.MODEL_ERROR,
                    landmarks=None,
                    inference_latency_ms=latency,
                    error_message=str(exc),
                )

            latency = (time.monotonic() - start_t) * 1000.0

            if not detection_result.pose_landmarks or len(detection_result.pose_landmarks) == 0:
                return PoseEstimationResult(
                    status=PoseEstimationStatus.NO_POSE_DETECTED,
                    landmarks=None,
                    inference_latency_ms=latency,
                )

            # Map the primary detected pose landmarks
            first_pose = detection_result.pose_landmarks[0]
            normalized_list: list[NormalizedLandmark] = []

            for lm in first_pose:
                normalized_list.append(
                    NormalizedLandmark(
                        x=float(lm.x),
                        y=float(lm.y),
                        z=float(lm.z),
                        visibility=float(getattr(lm, "visibility", 1.0) or 0.0),
                        presence=float(getattr(lm, "presence", 1.0) or 0.0),
                    )
                )

            raw_landmarks = RawPoseLandmarks(normalized_list)
            return PoseEstimationResult(
                status=PoseEstimationStatus.SUCCESS,
                landmarks=raw_landmarks,
                inference_latency_ms=latency,
            )

    def close(self) -> None:
        """Closes the underlying detector and frees TFLite runtime memory."""
        with self._lock:
            if self._landmarker is not None:
                try:
                    self._landmarker.close()
                except Exception as exc:
                    logger.debug("Error closing PoseLandmarker: %s", exc)
                self._landmarker = None
                logger.info("Closed MediaPipe PoseLandmarker detector.")
