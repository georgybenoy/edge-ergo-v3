"""EdgeErgo V3 Main Application Orchestrator.

Wires:
CameraSource -> PoseEstimator -> QualityValidator -> FeatureExtractor
  -> Scoring -> Storage & Sync -> OverlayPresenter
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timezone

from edge_ergo.camera.base import CameraSource
from edge_ergo.camera.fake_source import FakeCameraSource
from edge_ergo.camera.opencv_source import OpenCVCameraSource
from edge_ergo.camera.types import CameraError, CameraFrame, CameraState
from edge_ergo.features.extractor import extract_postural_features
from edge_ergo.features.types import PosturalFeatures
from edge_ergo.overlay.presenter import OverlayPresenter
from edge_ergo.overlay.types import OverlayViewModel
from edge_ergo.quality.temporal import TemporalQualityFilter
from edge_ergo.quality.types import ValidityReport, ValidityStatus
from edge_ergo.quality.validator import validate_observation
from edge_ergo.scoring.scorer import RulaPartialScorer
from edge_ergo.scoring.types import RulaScoringResult
from edge_ergo.storage.database import Database
from edge_ergo.storage.migrations import apply_migrations
from edge_ergo.storage.repository import StorageRepository
from edge_ergo.storage.types import AssessmentEventRecord
from edge_ergo.sync.worker import SyncWorker
from edge_ergo.vision.base import PoseEstimator
from edge_ergo.vision.mediapipe_estimator import MediaPipePoseEstimator
from edge_ergo.vision.synthetic_estimator import SyntheticPoseEstimator
from edge_ergo.vision.types import PoseEstimationStatus

logger = logging.getLogger(__name__)


class EdgeErgoApp:
    """Core on-device application orchestrator for camera, posture analysis, storage, and sync."""

    def __init__(
        self,
        camera: CameraSource | None = None,
        vision: PoseEstimator | None = None,
        repository: StorageRepository | None = None,
        sync_worker: SyncWorker | None = None,
        sampling_interval_s: float = 5.0,
        fake_camera: bool = False,
        synthetic_posture: str = "neutral",
        enable_sync: bool = True,
        on_assessment_hook: Callable[
            [RulaScoringResult, ValidityReport, PosturalFeatures | None], None
        ]
        | None = None,
    ) -> None:
        self.sampling_interval_s = max(0.05, sampling_interval_s)
        self.fake_camera = fake_camera
        self.synthetic_posture = synthetic_posture
        self.on_assessment_hook = on_assessment_hook
        self.enable_sync = enable_sync

        # Initialize storage subsystem
        if repository is not None:
            self.repository = repository
        else:
            db = Database()
            apply_migrations(db)
            self.repository = StorageRepository(db)

        # Initialize camera subsystem
        if camera is not None:
            self.camera = camera
        elif fake_camera:
            logger.info("Initializing FakeCameraSource for simulation mode.")
            self.camera = FakeCameraSource()
        else:
            self.camera = OpenCVCameraSource()

        # Initialize vision subsystem
        if vision is not None:
            self.vision = vision
        elif fake_camera:
            logger.info(
                "Initializing SyntheticPoseEstimator (%s) for simulation mode.", synthetic_posture
            )
            self.vision = SyntheticPoseEstimator(mode=synthetic_posture)
        else:
            self.vision = MediaPipePoseEstimator()

        self.temporal_filter = TemporalQualityFilter(min_consecutive_valid=2)
        self.scorer = RulaPartialScorer()

        # Initialize overlay presenter with current queue depth
        queue_depth = self.repository.get_queue_depth()
        initial_vm = OverlayViewModel(
            sampling_interval_s=self.sampling_interval_s,
            sync_status_text="Simulation Mode" if fake_camera else "Local Telemetry Active",
            queue_depth=queue_depth,
        )
        self.overlay_presenter = OverlayPresenter(initial_vm=initial_vm)

        # Initialize sync worker
        self.sync_worker: SyncWorker | None
        if sync_worker is not None:
            self.sync_worker = sync_worker
        elif self.enable_sync and not self.fake_camera:
            self.sync_worker = SyncWorker(
                repository=self.repository,
                overlay_presenter=self.overlay_presenter,
            )
        else:
            self.sync_worker = None

        # Worker thread control
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Telemetry metrics
        self.frames_captured = 0
        self.frames_dropped = 0
        self.assessments_completed = 0

    def start(self) -> bool:
        """Starts the camera hardware and begins background assessment and sync worker threads."""
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return True

            logger.info(
                "Starting EdgeErgoApp (fake_camera=%s, interval=%.1fs)...",
                self.fake_camera,
                self.sampling_interval_s,
            )
            self._stop_event.clear()

            try:
                opened = self.camera.open()
                if not opened:
                    logger.warning("Camera open returned False; entering degraded mode.")
                    self.overlay_presenter.on_camera_state_changed(CameraState.DISCONNECTED)
            except CameraError as exc:
                logger.error("Camera open failed: %s", exc)
                self.overlay_presenter.on_camera_state_changed(CameraState.ERROR)

            # Start sync worker if present
            if self.sync_worker is not None:
                self.sync_worker.start()

            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="EdgeErgoWorkerThread",
                daemon=True,
            )
            self._worker_thread.start()
            logger.info("EdgeErgo worker thread launched.")
            return True

    def stop(self, timeout_s: float = 3.0) -> None:
        """Stops background assessment worker and releases camera/model resources."""
        logger.info("Stopping EdgeErgoApp...")
        self._stop_event.set()

        if self.sync_worker is not None:
            self.sync_worker.stop(timeout_s=timeout_s)

        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout_s)
            self._worker_thread = None

        try:
            self.camera.close()
        except Exception as exc:
            logger.debug("Error closing camera: %s", exc)

        try:
            self.vision.close()
        except Exception as exc:
            logger.debug("Error closing vision: %s", exc)

        logger.info(
            "EdgeErgoApp shutdown complete. (Captured: %d, Dropped: %d, Assessed: %d)",
            self.frames_captured,
            self.frames_dropped,
            self.assessments_completed,
        )

    def is_running(self) -> bool:
        return (
            self._worker_thread is not None
            and self._worker_thread.is_alive()
            and not self._stop_event.is_set()
        )

    def pause(self) -> None:
        """Pauses camera and posture monitoring."""
        self.camera.pause()
        self.overlay_presenter.on_camera_state_changed(CameraState.PAUSED)

    def resume(self) -> None:
        """Resumes active monitoring."""
        self.camera.resume()
        self.overlay_presenter.on_camera_state_changed(CameraState.ACTIVE)

    def _worker_loop(self) -> None:
        """Periodic background evaluation pipeline."""
        while not self._stop_event.is_set():
            loop_start = time.monotonic()

            try:
                self._run_pipeline_iteration()
            except Exception as exc:
                logger.error("Unexpected error in pipeline loop: %s", exc, exc_info=True)
                self.frames_dropped += 1

            # Sleep remaining sampling interval
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0.01, self.sampling_interval_s - elapsed)

            # Interruptible sleep
            if self._stop_event.wait(timeout=sleep_time):
                break

    def _run_pipeline_iteration(self) -> None:
        """Executes a single end-to-end evaluation pass."""
        camera_state = self.camera.get_state()
        if camera_state != CameraState.ACTIVE:
            self.overlay_presenter.on_camera_state_changed(camera_state)
            return

        # 1. Capture Camera Frame (in RAM)
        frame: CameraFrame | None = self.camera.read_frame()
        if frame is None:
            self.frames_dropped += 1
            return

        self.frames_captured += 1

        # 2. Vision Inference
        estimation = self.vision.estimate(frame)

        # Discard in-memory camera frame immediately after inference
        del frame

        # Check vision status
        if estimation.status != PoseEstimationStatus.SUCCESS or estimation.landmarks is None:
            invalid_rep = ValidityReport(
                status=ValidityStatus.INVALID,
                reason_codes=[
                    "NO_POSE_DETECTED"
                    if estimation.status == PoseEstimationStatus.NO_POSE_DETECTED
                    else "MODEL_INFERENCE_ERROR"
                ],
                confidence_score=0.0,
            )
            filtered_rep = self.temporal_filter.process(invalid_rep)
            result = self.scorer.score(None, filtered_rep)
            self._record_telemetry(result, filtered_rep, None)
            self.overlay_presenter.on_assessment_evaluated(result, filtered_rep)
            if self.on_assessment_hook:
                self.on_assessment_hook(result, filtered_rep, None)
            return

        raw_landmarks = estimation.landmarks

        # 3. Quality Validation
        instant_validity = validate_observation(raw_landmarks)
        filtered_validity = self.temporal_filter.process(instant_validity)

        # 4. Feature Extraction & 5. Scoring
        features: PosturalFeatures | None = None
        if filtered_validity.is_valid:
            features = extract_postural_features(raw_landmarks)
            scoring_result = self.scorer.score(features, filtered_validity)
            self.assessments_completed += 1
        else:
            scoring_result = self.scorer.score(None, filtered_validity)

        # 6. Record Telemetry to local SQLite queue
        self._record_telemetry(scoring_result, filtered_validity, features)

        # 7. Update Overlay Presenter
        self.overlay_presenter.on_assessment_evaluated(scoring_result, filtered_validity)

        # Optional assessment hook
        if self.on_assessment_hook:
            self.on_assessment_hook(scoring_result, filtered_validity, features)

    def _record_telemetry(
        self,
        result: RulaScoringResult,
        validity: ValidityReport,
        features: PosturalFeatures | None,
    ) -> None:
        """Persists observation into local SQLite storage queue."""
        if not self.repository:
            return

        now_utc = datetime.now(timezone.utc).isoformat()
        val_str = (
            "valid"
            if validity.is_valid
            else ("insufficient" if validity.status == ValidityStatus.INSUFFICIENT else "invalid")
        )

        record = AssessmentEventRecord(
            event_id=str(uuid.uuid4()),
            captured_at=now_utc,
            scoring_method=result.scoring_method,
            scoring_version=result.scoring_version,
            validity=val_str,
            score=float(result.grand_score) if result.grand_score is not None else None,
            neck_score=result.neck_score,
            trunk_score=result.trunk_score,
            upper_arm_score=result.upper_arm_score,
            postural_features=json.dumps(asdict(features)) if features else None,
            guidance_codes=result.guidance_codes,
            software_version="3.0.0",
            created_at=now_utc,
        )

        try:
            self.repository.enqueue_assessment_event(record)
        except Exception as exc:
            logger.error("Failed to enqueue assessment event to SQLite: %s", exc)
