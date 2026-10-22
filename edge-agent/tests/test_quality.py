"""Tests for ergonomic observation quality evaluation and temporal stability."""

from __future__ import annotations

from edge_ergo.quality.temporal import TemporalQualityFilter
from edge_ergo.quality.types import ValidityReport, ValidityStatus
from edge_ergo.quality.validator import validate_observation
from edge_ergo.vision.landmarks import (
    NormalizedLandmark,
    PoseLandmarkIndex,
    RawPoseLandmarks,
)
from edge_ergo.vision.synthetic_estimator import create_neutral_landmarks


def test_neutral_observation_is_valid() -> None:
    """Verifies that an unoccluded neutral seated posture passes validation."""
    lms = RawPoseLandmarks(create_neutral_landmarks(visibility=0.95))
    rep = validate_observation(lms)

    assert rep.is_valid is True
    assert rep.status == ValidityStatus.VALID
    assert len(rep.reason_codes) == 0
    assert rep.confidence_score >= 0.85
    assert "shoulder_span" in rep.details


def test_occluded_shoulders_triggers_insufficient() -> None:
    """Verifies that occluded shoulder landmarks trigger INSUFFICIENT status (FR-008)."""
    raw = create_neutral_landmarks(visibility=0.95)
    # Occlude left shoulder
    raw[PoseLandmarkIndex.LEFT_SHOULDER] = NormalizedLandmark(0.40, 0.32, 0.0, 0.20, 0.20)
    lms = RawPoseLandmarks(raw)

    rep = validate_observation(lms)
    assert rep.is_valid is False
    assert rep.status == ValidityStatus.INSUFFICIENT
    assert "OCCLUSION_SHOULDERS" in rep.reason_codes


def test_occluded_head_triggers_insufficient() -> None:
    """Verifies that occluded head / neck references trigger INSUFFICIENT status."""
    raw = create_neutral_landmarks(visibility=0.95)
    raw[PoseLandmarkIndex.NOSE] = NormalizedLandmark(0.50, 0.20, 0.0, 0.10, 0.10)
    raw[PoseLandmarkIndex.LEFT_EAR] = NormalizedLandmark(0.44, 0.19, 0.0, 0.10, 0.10)
    raw[PoseLandmarkIndex.RIGHT_EAR] = NormalizedLandmark(0.56, 0.19, 0.0, 0.10, 0.10)
    lms = RawPoseLandmarks(raw)

    rep = validate_observation(lms)
    assert rep.is_valid is False
    assert rep.status == ValidityStatus.INSUFFICIENT
    assert "OCCLUSION_HEAD" in rep.reason_codes


def test_occluded_arm_joints_triggers_reason_code() -> None:
    """Verifies that occluded forearm/wrist joints flag reasons."""
    raw = create_neutral_landmarks(visibility=0.95)
    raw[PoseLandmarkIndex.RIGHT_WRIST] = NormalizedLandmark(0.56, 0.58, 0.0, 0.15, 0.15)
    lms = RawPoseLandmarks(raw)

    rep = validate_observation(lms)
    assert "OCCLUSION_WRISTS" in rep.reason_codes


def test_camera_placement_heuristics() -> None:
    """Verifies distance heuristics: too far and too close."""
    # 1. Camera too far (shoulders tiny)
    raw_far = create_neutral_landmarks(visibility=0.95)
    raw_far[PoseLandmarkIndex.LEFT_SHOULDER] = NormalizedLandmark(0.49, 0.32, 0.0, 0.95, 0.95)
    raw_far[PoseLandmarkIndex.RIGHT_SHOULDER] = NormalizedLandmark(0.51, 0.32, 0.0, 0.95, 0.95)
    rep_far = validate_observation(RawPoseLandmarks(raw_far))
    assert rep_far.status == ValidityStatus.INVALID
    assert "CAMERA_TOO_FAR" in rep_far.reason_codes

    # 2. Camera too close (shoulders span whole width)
    raw_close = create_neutral_landmarks(visibility=0.95)
    raw_close[PoseLandmarkIndex.LEFT_SHOULDER] = NormalizedLandmark(0.04, 0.32, 0.0, 0.95, 0.95)
    raw_close[PoseLandmarkIndex.RIGHT_SHOULDER] = NormalizedLandmark(0.96, 0.32, 0.0, 0.95, 0.95)
    rep_close = validate_observation(RawPoseLandmarks(raw_close))
    assert rep_close.status == ValidityStatus.INVALID
    assert "CAMERA_TOO_CLOSE" in rep_close.reason_codes


def test_anatomical_inversion_rejection() -> None:
    """Verifies rejection of inverted body orientation (e.g. upside down)."""
    raw_inv = create_neutral_landmarks(visibility=0.95)
    # Hips above shoulders
    raw_inv[PoseLandmarkIndex.LEFT_HIP] = NormalizedLandmark(0.42, 0.20, 0.0, 0.95, 0.95)
    raw_inv[PoseLandmarkIndex.RIGHT_HIP] = NormalizedLandmark(0.58, 0.20, 0.0, 0.95, 0.95)
    raw_inv[PoseLandmarkIndex.LEFT_SHOULDER] = NormalizedLandmark(0.40, 0.70, 0.0, 0.95, 0.95)
    raw_inv[PoseLandmarkIndex.RIGHT_SHOULDER] = NormalizedLandmark(0.60, 0.70, 0.0, 0.95, 0.95)

    rep = validate_observation(RawPoseLandmarks(raw_inv))
    assert rep.status == ValidityStatus.INVALID
    assert "INVALID_ANATOMICAL_ORIENTATION" in rep.reason_codes


def test_temporal_quality_filter() -> None:
    """Verifies temporal continuity without data fabrication (FR-008)."""
    filter_engine = TemporalQualityFilter(min_consecutive_valid=2)

    valid_rep = ValidityReport(status=ValidityStatus.VALID, confidence_score=0.95)
    insufficient_rep = ValidityReport(
        status=ValidityStatus.INSUFFICIENT, reason_codes=["OCCLUSION_ARMS"]
    )

    # First valid observation -> held as INSUFFICIENT for stabilization
    step1 = filter_engine.process(valid_rep)
    assert step1.status == ValidityStatus.INSUFFICIENT
    assert "TEMPORAL_STABILIZING" in step1.reason_codes

    # Second valid observation -> confirmed VALID
    step2 = filter_engine.process(valid_rep)
    assert step2.status == ValidityStatus.VALID
    assert step2.is_valid is True

    # Third frame occluded -> immediately drops to INSUFFICIENT and resets counter
    step3 = filter_engine.process(insufficient_rep)
    assert step3.status == ValidityStatus.INSUFFICIENT
    assert "OCCLUSION_ARMS" in step3.reason_codes

    # Subsequent valid frame needs stabilization again
    step4 = filter_engine.process(valid_rep)
    assert step4.status == ValidityStatus.INSUFFICIENT
    assert "TEMPORAL_STABILIZING" in step4.reason_codes
