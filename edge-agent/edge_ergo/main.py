"""EdgeErgo V3 — Windows Desktop Agent Entrypoint."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

from edge_ergo.app import EdgeErgoApp
from edge_ergo.storage.database import Database
from edge_ergo.storage.migrations import apply_migrations
from edge_ergo.storage.repository import StorageRepository
from edge_ergo.sync.enrollment import enroll_device, forget_device


def setup_logging(level: str = "INFO") -> None:
    """Configures structured, sanitized logging."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_agent_status() -> dict[str, str]:
    """Returns local agent status metadata."""
    return {
        "status": "ready",
        "version": "3.0.0",
        "platform": "windows",
    }


def run_selftest() -> int:
    """Executes offline verification of critical imports, SQLite migrations,
    and posture scoring pipeline.
    """
    print("=" * 60)
    print("EdgeErgo V3 — On-Device Agent Offline Selftest")
    print("=" * 60)

    # 1. Critical Library Imports
    print("[1/3] Testing critical library imports...")
    try:
        import sqlite3

        import cv2
        import keyring
        import mediapipe
        import numpy
        import PySide6

        print(f"  [OK] OpenCV ({cv2.__version__})")
        print(f"  [OK] MediaPipe ({mediapipe.__version__})")
        print(f"  [OK] NumPy ({numpy.__version__})")
        print(f"  [OK] PySide6 ({PySide6.__version__})")
        try:
            import importlib.metadata

            keyring_ver = importlib.metadata.version("keyring")
        except Exception:
            keyring_ver = getattr(keyring, "__version__", "available")
        print(f"  [OK] Keyring ({keyring_ver})")
        print(f"  [OK] SQLite3 ({sqlite3.sqlite_version})")
    except Exception as exc:
        print(f"  [FAIL] Import failed: {exc}", file=sys.stderr)
        return 1

    # 2. SQLite Schema & Migration in Temp Directory
    print("[2/3] Testing SQLite schema initialization & migrations in temp dir...")
    import tempfile
    from pathlib import Path

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_db_path = Path(tmp_dir) / "selftest_edge_ergo.db"
            test_db = Database(db_path=temp_db_path)
            apply_migrations(test_db)

            # Check tables
            conn = test_db.connect()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
                )
                tables = {row[0] for row in cursor.fetchall()}
                expected_tables = {
                    "schema_migrations",
                    "settings",
                    "assessment_events",
                    "sync_queue",
                    "sync_state",
                    "device_identity",
                }
                missing = expected_tables - tables
                if missing:
                    print(f"  [FAIL] Missing expected tables: {missing}", file=sys.stderr)
                    return 1
            finally:
                conn.close()
            print("  [OK] Local database schema created and verified cleanly.")
    except Exception as exc:
        print(f"  [FAIL] Database test failed: {exc}", file=sys.stderr)
        return 1

    # 3. Offline Pipeline Execution (No Network)
    print("[3/3] Testing synthetic camera pipeline & feature extraction (zero network)...")
    try:
        from edge_ergo.camera.fake_source import FakeCameraSource
        from edge_ergo.features.extractor import extract_postural_features
        from edge_ergo.quality.validator import validate_observation
        from edge_ergo.scoring.scorer import RulaPartialScorer
        from edge_ergo.vision.synthetic_estimator import SyntheticPoseEstimator

        cam = FakeCameraSource()
        cam.open()
        frame = cam.read_frame()
        cam.close()
        if frame is None:
            print("  [FAIL] FakeCameraSource failed to return a frame", file=sys.stderr)
            return 1

        estimator = SyntheticPoseEstimator(mode="neutral")
        estimation = estimator.estimate(frame)
        estimator.close()
        if estimation.landmarks is None:
            print("  [FAIL] Pose estimator returned None landmarks", file=sys.stderr)
            return 1

        validity = validate_observation(estimation.landmarks)
        if not validity.is_valid:
            print(
                f"  [FAIL] Neutral observation failed quality check: {validity.rejection_reasons}",
                file=sys.stderr,
            )
            return 1

        features = extract_postural_features(estimation.landmarks)
        scorer = RulaPartialScorer()
        score_res = scorer.score(features, validity)
        if not score_res.is_valid or score_res.grand_score is None:
            print(
                "  [FAIL] Scorer failed to compute grand score for valid observation",
                file=sys.stderr,
            )
            return 1

        print(
            f"  [OK] Pipeline computed valid score: grand_score={score_res.grand_score}, "
            f"action_level='{score_res.action_level}'"
        )
    except Exception as exc:
        print(f"  [FAIL] Pipeline test failed: {exc}", file=sys.stderr)
        return 1

    print("=" * 60)
    print("[PASS] Selftest completed successfully! Edge agent core is functional.")
    print("=" * 60)
    return 0


def main() -> int:
    """CLI entrypoint for EdgeErgo local agent."""
    parser = argparse.ArgumentParser(
        description="EdgeErgo V3 — On-Device Ergonomic Assessment Agent"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="EdgeErgo Agent v3.0.0",
        help="Display agent version and exit.",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help=(
            "Run offline sanity checks (imports, SQLite temp DB, and fake-camera "
            "pipeline) without network."
        ),
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Agent commands")

    # Command: enroll
    enroll_parser = subparsers.add_parser("enroll", help="Enroll workstation with EdgeErgo API")
    enroll_parser.add_argument(
        "--api", required=True, help="API server URL (e.g. https://api.yourcompany.com)"
    )
    enroll_parser.add_argument(
        "--token", required=True, help="Single-use enrollment token (eet_...)"
    )
    enroll_parser.add_argument("--label", help="Optional workstation display label")

    # Command: forget-device
    subparsers.add_parser(
        "forget-device", help="Forget workstation identity and wipe stored credential"
    )

    # General app arguments
    parser.add_argument(
        "--fake-camera",
        "--dry-run",
        dest="fake_camera",
        action="store_true",
        help="Run in headless/synthetic simulation mode without webcam hardware.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run headless background assessment pipeline without PySide6 desktop overlay.",
    )
    parser.add_argument(
        "--device-index",
        type=int,
        default=0,
        help="Webcam device hardware index (default: 0).",
    )
    parser.add_argument(
        "--sampling-interval",
        type=float,
        default=5.0,
        help="Posture evaluation sampling interval in seconds (default: 5.0).",
    )
    parser.add_argument(
        "--posture",
        choices=[
            "neutral",
            "neck_flexed",
            "slouching",
            "shoulder_shrug",
            "arm_elevated",
            "occluded",
        ],
        default="neutral",
        help="Simulated posture mode when running in --fake-camera mode (default: neutral).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional execution duration in seconds before automated shutdown.",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Disable cloud sync and keep telemetry strictly local.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )

    args = parser.parse_args()

    if args.selftest:
        return run_selftest()

    setup_logging(args.log_level)
    logger = logging.getLogger("edge_ergo")

    # Ensure local database migrations are applied
    db = Database()
    apply_migrations(db)
    repo = StorageRepository(db)

    # Handle subcommand: enroll
    if args.subcommand == "enroll":
        try:
            logger.info("Enrolling workstation with %s...", args.api)
            identity = enroll_device(
                api_base_url=args.api, token=args.token, label=args.label, repo=repo
            )
            print(
                f"[OK] Workstation enrolled successfully: "
                f"public_id={identity.public_id}, label='{identity.label}'"
            )
            return 0
        except Exception as exc:
            logger.error("Enrollment failed: %s", exc)
            print(f"[ERROR] Enrollment failed: {exc}", file=sys.stderr)
            return 1

    # Handle subcommand: forget-device
    if args.subcommand == "forget-device":
        success = forget_device(repo=repo)
        if success:
            print("[OK] Workstation identity forgotten and credential removed.")
        else:
            print("[INFO] Workstation was not enrolled.")
        return 0

    logger.info(
        "Initializing EdgeErgo Agent v3.0.0 (fake_camera=%s, headless=%s)",
        args.fake_camera,
        args.headless,
    )

    app = EdgeErgoApp(
        repository=repo,
        sampling_interval_s=args.sampling_interval,
        fake_camera=args.fake_camera,
        synthetic_posture=args.posture,
        enable_sync=not args.no_sync,
    )

    # Clean OS signal handling
    def sigint_handler(sig: int, frame: object) -> None:
        logger.info("Interrupted by user signal. Shutting down...")
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sigint_handler)

    if not app.start():
        logger.error("Failed to start EdgeErgoApp.")
        return 1

    if args.headless:
        logger.info("Running in headless mode. Press Ctrl+C to exit.")
        start_time = time.time()
        try:
            while True:
                time.sleep(0.5)
                if args.duration and (time.time() - start_time) >= args.duration:
                    logger.info("Duration limit of %.1fs reached.", args.duration)
                    break
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received.")
        finally:
            app.stop()
        return 0

    # Launch PySide6 Desktop Overlay
    try:
        from PySide6.QtWidgets import QApplication

        from edge_ergo.overlay.widget import CompactOverlayWidget

        qt_app = QApplication.instance() or QApplication(sys.argv)
        overlay = CompactOverlayWidget(presenter=app.overlay_presenter)
        overlay.show()
        logger.info("Desktop overlay launched.")

        ret_code = qt_app.exec()
        app.stop()
        return int(ret_code)
    except Exception as exc:
        logger.error("Failed to run desktop overlay: %s", exc)
        app.stop()
        return 1


if __name__ == "__main__":
    sys.exit(main())
