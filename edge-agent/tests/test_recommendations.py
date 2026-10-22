"""Tests for rule-based ergonomic recommendation generation (FR-015)."""

from __future__ import annotations

from edge_ergo.features.types import PosturalFeatures
from edge_ergo.scoring.recommendations import (
    GUIDANCE_MAPPINGS,
    generate_recommendations,
)


def make_features(**kwargs: float) -> PosturalFeatures:
    """Helper to instantiate PosturalFeatures with defaults."""
    defaults = {
        "neck_flexion_deg": 5.0,
        "trunk_inclination_deg": 3.0,
        "shoulder_elevation_deg": 2.0,
        "upper_arm_elevation_deg": 15.0,
        "elbow_angle_deg": 90.0,
        "left_upper_arm_deg": 15.0,
        "right_upper_arm_deg": 15.0,
        "left_elbow_deg": 90.0,
        "right_elbow_deg": 90.0,
    }
    defaults.update(kwargs)
    return PosturalFeatures(**defaults)


def test_neutral_posture_yields_general_guidance() -> None:
    """Neutral posture within all thresholds yields GENERAL_GOOD_POSTURE code."""
    feat = make_features()
    codes, recs = generate_recommendations(
        feat, neck_score=1, trunk_score=1, upper_arm_score=1, lower_arm_score=1
    )

    assert codes == ["GENERAL_GOOD_POSTURE"]
    assert recs == [GUIDANCE_MAPPINGS["GENERAL_GOOD_POSTURE"]]


def test_neck_flexion_rule_mapping() -> None:
    """Neck flexion > 20° or neck_score >= 3 triggers GUID_NECK_FLEX_01."""
    feat = make_features(neck_flexion_deg=25.0)
    codes, recs = generate_recommendations(
        feat, neck_score=3, trunk_score=1, upper_arm_score=1, lower_arm_score=1
    )

    assert "GUID_NECK_FLEX_01" in codes
    assert GUIDANCE_MAPPINGS["GUID_NECK_FLEX_01"] in recs


def test_trunk_inclination_rule_mapping() -> None:
    """Trunk inclination > 20° triggers GUID_TRUNK_INCL_01."""
    feat = make_features(trunk_inclination_deg=22.0)
    codes, recs = generate_recommendations(
        feat, neck_score=1, trunk_score=3, upper_arm_score=1, lower_arm_score=1
    )

    assert "GUID_TRUNK_INCL_01" in codes
    assert GUIDANCE_MAPPINGS["GUID_TRUNK_INCL_01"] in recs


def test_shoulder_elevation_rule_mapping() -> None:
    """Shoulder elevation > 10° triggers GUID_SHOULDER_ELEV_01."""
    feat = make_features(shoulder_elevation_deg=14.0)
    codes, recs = generate_recommendations(
        feat, neck_score=1, trunk_score=1, upper_arm_score=2, lower_arm_score=1
    )

    assert "GUID_SHOULDER_ELEV_01" in codes
    assert GUIDANCE_MAPPINGS["GUID_SHOULDER_ELEV_01"] in recs


def test_upper_arm_elevation_rule_mapping() -> None:
    """Upper arm elevation > 45° triggers GUID_ARM_ELEV_01."""
    feat = make_features(upper_arm_elevation_deg=55.0)
    codes, recs = generate_recommendations(
        feat, neck_score=1, trunk_score=1, upper_arm_score=3, lower_arm_score=1
    )

    assert "GUID_ARM_ELEV_01" in codes
    assert GUIDANCE_MAPPINGS["GUID_ARM_ELEV_01"] in recs


def test_elbow_angle_rule_mapping() -> None:
    """Elbow angle < 60° or > 100° triggers GUID_ELBOW_ANGLE_01."""
    # Acute angle < 60°
    feat_acute = make_features(elbow_angle_deg=45.0)
    codes_acute, _ = generate_recommendations(
        feat_acute, neck_score=1, trunk_score=1, upper_arm_score=1, lower_arm_score=2
    )
    assert "GUID_ELBOW_ANGLE_01" in codes_acute

    # Extended angle > 100°
    feat_ext = make_features(elbow_angle_deg=115.0)
    codes_ext, _ = generate_recommendations(
        feat_ext, neck_score=1, trunk_score=1, upper_arm_score=1, lower_arm_score=2
    )
    assert "GUID_ELBOW_ANGLE_01" in codes_ext
