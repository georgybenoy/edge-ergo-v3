#!/usr/bin/env python3
# ruff: noqa: BLE001, S110
"""EdgeErgo V3 — On-Device Edge Pipeline Performance Benchmark.

Measures per-frame pipeline latency, CPU time, process memory footprint,
and dropped frames across N iterations. Records results to a local JSON report
with system hardware and library environment metadata.

Usage:
    python scripts/benchmark_edge.py --iterations 50 --fake-camera --output benchmark_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Add edge-agent to pythonpath
agent_root = Path(__file__).resolve().parent.parent / "edge-agent"
if str(agent_root) not in sys.path:
    sys.path.insert(0, str(agent_root))

from edge_ergo.camera.fake_source import FakeCameraSource
from edge_ergo.camera.opencv_source import OpenCVCameraSource
from edge_ergo.features.extractor import extract_postural_features
from edge_ergo.quality.temporal import TemporalQualityFilter
from edge_ergo.quality.validator import validate_observation
from edge_ergo.scoring.scorer import RulaPartialScorer
from edge_ergo.vision.mediapipe_estimator import MediaPipePoseEstimator
from edge_ergo.vision.synthetic_estimator import SyntheticPoseEstimator


def get_memory_rss_mb() -> float:
    """Returns resident set size memory in megabytes."""
    try:
        import psutil
        return round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 2)
    except ImportError:
        # Fallback approximation for Windows using ctypes
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                return round(pmc.WorkingSetSize / (1024 * 1024), 2)
        except Exception:
            pass
        return 0.0


def get_power_mode() -> str:
    """Detects AC power or battery status on Windows."""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is not None:
            return "AC Power (Plugged In)" if battery.power_plugged else f"Battery ({battery.percent}% remaining)"
    except Exception:
        pass

    try:
        import ctypes
        from ctypes import wintypes

        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", wintypes.BYTE),
                ("BatteryFlag", wintypes.BYTE),
                ("BatteryLifePercent", wintypes.BYTE),
                ("SystemStatusFlag", wintypes.BYTE),
                ("BatteryLifeTime", wintypes.DWORD),
                ("BatteryFullLifeTime", wintypes.DWORD),
            ]

        sps = SYSTEM_POWER_STATUS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
            if sps.ACLineStatus == 1:
                return "AC Power (Mains Connected)"
            elif sps.ACLineStatus == 0:
                return f"Battery ({sps.BatteryLifePercent}%)"
    except Exception:
        pass
    return "AC Power / Unspecified"


def run_benchmark(
    iterations: int = 50,
    duration: float | None = None,
    fake_camera: bool = True,
    device_index: int = 0,
    output_path: str | Path | None = None,
) -> dict[str, object]:
    """Runs N-frame or time-bounded edge inference benchmark and generates performance metrics."""
    mode_desc = f"duration={duration}s" if duration and duration > 0 else f"iterations={iterations}"
    print(f"Initializing Edge Pipeline Benchmark ({mode_desc}, fake_camera={fake_camera})...")

    # Hardware & environment metadata
    hw_info = {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "power_mode": get_power_mode(),
        "python_version": platform.python_version(),
    }

    try:
        import cv2
        hw_info["opencv_version"] = cv2.__version__
    except ImportError:
        hw_info["opencv_version"] = "unavailable"

    try:
        import mediapipe
        hw_info["mediapipe_version"] = mediapipe.__version__
    except ImportError:
        hw_info["mediapipe_version"] = "unavailable"

    try:
        import numpy
        hw_info["numpy_version"] = numpy.__version__
    except ImportError:
        hw_info["numpy_version"] = "unavailable"

    # Startup benchmark: time component instantiation & camera open
    t_startup_0 = time.perf_counter()
    if fake_camera:
        camera = FakeCameraSource()
        vision = SyntheticPoseEstimator(mode="neutral")
    else:
        camera = OpenCVCameraSource(device_index=device_index)
        vision = MediaPipePoseEstimator()

    temporal_filter = TemporalQualityFilter(min_consecutive_valid=1)
    scorer = RulaPartialScorer()
    camera.open()
    startup_time_ms = round((time.perf_counter() - t_startup_0) * 1000.0, 2)
    print(f"Pipeline Startup Time: {startup_time_ms} ms")

    frame_read_times: list[float] = []
    vision_times: list[float] = []
    features_times: list[float] = []
    scoring_times: list[float] = []
    total_iteration_times: list[float] = []
    dropped_frames = 0
    valid_scores = 0

    initial_rss = get_memory_rss_mb()
    print(f"Baseline Process Memory (RSS): {initial_rss} MB")

    bench_start = time.perf_counter()
    cpu_start = time.process_time()
    cycle_count = 0

    try:
        while True:
            # Check termination criteria
            if duration and duration > 0:
                if (time.perf_counter() - bench_start) >= duration:
                    break
            else:
                if cycle_count >= iterations:
                    break

            cycle_count += 1
            iter_start = time.perf_counter()

            # 1. Camera Frame Read
            t0 = time.perf_counter()
            frame = camera.read_frame()
            t_read = (time.perf_counter() - t0) * 1000.0
            frame_read_times.append(t_read)

            if frame is None:
                dropped_frames += 1
                continue

            # 2. Vision Inference
            t1 = time.perf_counter()
            estimation = vision.estimate(frame)
            t_vision = (time.perf_counter() - t1) * 1000.0
            vision_times.append(t_vision)

            # 3. Quality & Feature Extraction
            t2 = time.perf_counter()
            if estimation.landmarks is not None:
                instant_validity = validate_observation(estimation.landmarks)
                filtered_validity = temporal_filter.process(instant_validity)
                features = extract_postural_features(estimation.landmarks)
            else:
                instant_validity = None
                features = None
            t_feat = (time.perf_counter() - t2) * 1000.0
            features_times.append(t_feat)

            # 4. Scoring
            t3 = time.perf_counter()
            if instant_validity is not None and features is not None:
                score_res = scorer.score(features, filtered_validity)
                if score_res.is_valid:
                    valid_scores += 1
            t_score = (time.perf_counter() - t3) * 1000.0
            scoring_times.append(t_score)

            iter_elapsed = (time.perf_counter() - iter_start) * 1000.0
            total_iteration_times.append(iter_elapsed)

            if cycle_count % 10 == 0:
                print(f"  [{cycle_count} cycles] Mean Iteration Latency: {sum(total_iteration_times) / len(total_iteration_times):.2f} ms")

    finally:
        camera.close()
        vision.close()

    total_wall_time = time.perf_counter() - bench_start
    total_cpu_time = time.process_time() - cpu_start
    final_rss = get_memory_rss_mb()

    import numpy as np
    results = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "hardware_environment": hw_info,
        "benchmark_config": {
            "iterations": iterations if not duration else None,
            "duration_s": duration,
            "fake_camera": fake_camera,
            "device_index": device_index,
        },
        "performance_summary": {
            "startup_time_ms": startup_time_ms,
            "total_wall_time_s": round(total_wall_time, 3),
            "total_cpu_time_s": round(total_cpu_time, 3),
            "average_cpu_utilization_pct": round((total_cpu_time / max(1e-6, total_wall_time)) * 100.0, 1),
            "initial_memory_rss_mb": initial_rss,
            "final_memory_rss_mb": final_rss,
            "memory_delta_mb": round(final_rss - initial_rss, 2),
            "frames_processed": len(total_iteration_times),
            "frames_dropped": dropped_frames,
            "valid_scores_computed": valid_scores,
        },
        "latency_percentiles_ms": {
            "total_iteration": {
                "mean": round(float(np.mean(total_iteration_times)), 2) if total_iteration_times else 0.0,
                "p50": round(float(np.percentile(total_iteration_times, 50)), 2) if total_iteration_times else 0.0,
                "p95": round(float(np.percentile(total_iteration_times, 95)), 2) if total_iteration_times else 0.0,
                "p99": round(float(np.percentile(total_iteration_times, 99)), 2) if total_iteration_times else 0.0,
                "min": round(float(np.min(total_iteration_times)), 2) if total_iteration_times else 0.0,
                "max": round(float(np.max(total_iteration_times)), 2) if total_iteration_times else 0.0,
            },
            "vision_inference": {
                "mean": round(float(np.mean(vision_times)), 2) if vision_times else 0.0,
                "p50": round(float(np.percentile(vision_times, 50)), 2) if vision_times else 0.0,
                "p95": round(float(np.percentile(vision_times, 95)), 2) if vision_times else 0.0,
            },
            "feature_extraction": {
                "mean": round(float(np.mean(features_times)), 2) if features_times else 0.0,
            },
            "scoring": {
                "mean": round(float(np.mean(scoring_times)), 2) if scoring_times else 0.0,
            },
        },
    }

    if output_path is None:
        output_path = Path("benchmark_results.json")
    else:
        output_path = Path(output_path)

    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n[OK] Benchmark completed ({len(total_iteration_times)} frames in {total_wall_time:.2f}s). Results saved to: {output_path.resolve()}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="EdgeErgo V3 Edge Performance Benchmark")
    parser.add_argument("--iterations", type=int, default=50, help="Number of benchmark cycles (default: 50)")
    parser.add_argument("--duration", type=float, default=None, help="Benchmark run time in seconds (overrides iterations)")
    parser.add_argument("--fake-camera", action="store_true", default=True, help="Use synthetic frames and pose estimator (default: True)")
    parser.add_argument("--real-camera", dest="fake_camera", action="store_false", help="Use real webcam hardware")
    parser.add_argument("--device-index", type=int, default=0, help="Camera index for real webcam (default: 0)")
    parser.add_argument("--output", default="benchmark_results.json", help="Output JSON results path")

    args = parser.parse_args()
    run_benchmark(
        iterations=args.iterations,
        duration=args.duration,
        fake_camera=args.fake_camera,
        device_index=args.device_index,
        output_path=args.output,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
