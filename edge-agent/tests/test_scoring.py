"""Reference cases and boundary condition tests for RULA ergonomic scoring.

Authoritative Source Derivations:
McAtamney, L., & Corlett, E. N. (1993). RULA: a survey method for the
investigation of work-related upper limb disorders. Applied Ergonomics, 24(2), 91-99.
"""

from __future__ import annotations

from edge_ergo.features.types import PosturalFeatures
from edge_ergo.quality.types import ValidityReport, ValidityStatus
from edge_ergo.scoring.scorer import RulaPartialScorer
from edge_ergo.scoring.types import ActionLevel


def make_features(
    neck: float = 5.0,
    trunk: float = 3.0,
    shoulder: float = 2.0,
    upper_arm: float = 15.0,
    elbow: float = 90.0,
) -> PosturalFeatures:
    """Helper creating PosturalFeatures instance with customizable angles."""
    return PosturalFeatures(
        neck_flexion_deg=neck,
        trunk_inclination_deg=trunk,
        shoulder_elevation_deg=shoulder,
        upper_arm_elevation_deg=upper_arm,
        elbow_angle_deg=elbow,
        left_upper_arm_deg=upper_arm,
        right_upper_arm_deg=upper_arm,
        left_elbow_deg=elbow,
        right_elbow_deg=elbow,
    )


# ---------------------------------------------------------------------------
# Hand-Calculated Reference Cases (Documented Derivations)
# ---------------------------------------------------------------------------


def test_reference_case_1_ideal_neutral() -> None:
    """Reference Case 1 (Ideal Ergonomic Neutral Posture):

    Derivation:
    - Upper arm = 15° (<= 20°) -> Upper arm score = 1
    - Shoulder elevation = 2° (<= 10°) -> Adjustment = +0 -> Upper arm final = 1
    - Elbow angle = 90° (60-100°) -> Lower arm score = 1
    - Table A[1, 1] with wrist=1, twist=1 -> Score A = 1
    - Neck flexion = 5° (<= 10°) -> Neck score = 1
    - Trunk inclination = 3° (<= 5°) -> Trunk score = 1
    - Table B[1, 1] with legs=1 -> Score B = 1
    - Table C[Score A=1, Score B=1] -> Grand Score = 1
    - Action Level: Level 1 (Acceptable)
    """
    scorer = RulaPartialScorer()
    features = make_features(neck=5.0, trunk=3.0, shoulder=2.0, upper_arm=15.0, elbow=90.0)
    validity = ValidityReport(status=ValidityStatus.VALID)

    res = scorer.score(features, validity)
    assert res.is_valid is True
    assert res.grand_score == 1
    assert res.action_level == ActionLevel.LEVEL_1
    assert res.neck_score == 1
    assert res.trunk_score == 1
    assert res.upper_arm_score == 1
    assert res.lower_arm_score == 1
    assert res.score_a == 1
    assert res.score_b == 1
    assert "GENERAL_GOOD_POSTURE" in res.guidance_codes


def test_reference_case_2_typical_slouch_and_forward_head() -> None:
    """Reference Case 2 (Typical Forward Slouch & Reaching):

    Derivation:
    - Upper arm = 30° (20-45°) -> Upper arm score = 2
    - Shoulder elevation = 5° (<= 10°) -> Adjustment = +0 -> Upper arm final = 2
    - Elbow angle = 80° (60-100°) -> Lower arm score = 1
    - Table A[2, 1] -> Score A = 2
    - Neck flexion = 25° (> 20°) -> Neck score = 3
    - Trunk inclination = 25° (20-60°) -> Trunk score = 3
    - Table B[3, 3] -> Score B = 5
    - Table C[Score A=2, Score B=5] -> Grand Score = 4
    - Action Level: Level 2 (Further Investigation)
    """
    scorer = RulaPartialScorer()
    features = make_features(neck=25.0, trunk=25.0, shoulder=5.0, upper_arm=30.0, elbow=80.0)
    validity = ValidityReport(status=ValidityStatus.VALID)

    res = scorer.score(features, validity)
    assert res.is_valid is True
    assert res.grand_score == 4
    assert res.action_level == ActionLevel.LEVEL_2
    assert res.neck_score == 3
    assert res.trunk_score == 3
    assert res.upper_arm_score == 2
    assert res.lower_arm_score == 1
    assert res.score_a == 2
    assert res.score_b == 5
    assert "GUID_NECK_FLEX_01" in res.guidance_codes
    assert "GUID_TRUNK_INCL_01" in res.guidance_codes


def test_reference_case_3_elevated_arm_and_shrug() -> None:
    """Reference Case 3 (Elevated Arm + Trapezius Shrug + Non-neutral Forearm):

    Derivation:
    - Upper arm = 60° (45-90°) -> base = 3
    - Shoulder elevation = 15° (> 10°) -> +1 shrug adjustment -> Upper arm final = 4
    - Elbow angle = 110° (> 100°) -> Lower arm score = 2
    - Table A[4, 2] -> Score A = 4
    - Neck flexion = 15° (10-20°) -> Neck score = 2
    - Trunk inclination = 10° (5-20°) -> Trunk score = 2
    - Table B[2, 2] -> Score B = 3
    - Table C[Score A=4, Score B=3] -> Grand Score = 4
    - Action Level: Level 2
    """
    scorer = RulaPartialScorer()
    features = make_features(neck=15.0, trunk=10.0, shoulder=15.0, upper_arm=60.0, elbow=110.0)
    validity = ValidityReport(status=ValidityStatus.VALID)

    res = scorer.score(features, validity)
    assert res.is_valid is True
    assert res.grand_score == 4
    assert res.action_level == ActionLevel.LEVEL_2
    assert res.upper_arm_score == 4
    assert res.lower_arm_score == 2
    assert res.neck_score == 2
    assert res.trunk_score == 2
    assert res.score_a == 4
    assert res.score_b == 3
    assert "GUID_SHOULDER_ELEV_01" in res.guidance_codes
    assert "GUID_ARM_ELEV_01" in res.guidance_codes
    assert "GUID_ELBOW_ANGLE_01" in res.guidance_codes


def test_reference_case_4_severe_postural_strain() -> None:
    """Reference Case 4 (Severe Overhead Reach & Bent Spine):

    Derivation:
    - Upper arm = 95° (> 90°) -> base 4 + 1 shrug (12°) = 5
    - Elbow angle = 50° (< 60°) -> Lower arm score = 2
    - Table A[5, 2] -> Score A = 5
    - Neck flexion = 35° (> 20°) -> Neck score = 3
    - Trunk inclination = 65° (> 60°) -> Trunk score = 4
    - Table B[3, 4] -> Score B = 6
    - Table C[Score A=5, Score B=6] -> Grand Score = 7
    - Action Level: Level 4 (Immediate Change Required)
    """
    scorer = RulaPartialScorer()
    features = make_features(neck=35.0, trunk=65.0, shoulder=12.0, upper_arm=95.0, elbow=50.0)
    validity = ValidityReport(status=ValidityStatus.VALID)

    res = scorer.score(features, validity)
    assert res.is_valid is True
    assert res.grand_score == 7
    assert res.action_level == ActionLevel.LEVEL_4
    assert res.score_a == 5
    assert res.score_b == 6


# ---------------------------------------------------------------------------
# Boundary Tests (Both Sides of Every Threshold)
# ---------------------------------------------------------------------------


def test_upper_arm_boundaries() -> None:
    """Tests thresholds: 20°, 45°, 90°."""
    scorer = RulaPartialScorer()
    validity = ValidityReport(status=ValidityStatus.VALID)

    # 20.0° -> 1 vs 20.1° -> 2
    res_20_0 = scorer.score(make_features(upper_arm=20.0, shoulder=0.0), validity)
    res_20_1 = scorer.score(make_features(upper_arm=20.1, shoulder=0.0), validity)
    assert res_20_0.upper_arm_score == 1
    assert res_20_1.upper_arm_score == 2

    # 45.0° -> 2 vs 45.1° -> 3
    res_45_0 = scorer.score(make_features(upper_arm=45.0, shoulder=0.0), validity)
    res_45_1 = scorer.score(make_features(upper_arm=45.1, shoulder=0.0), validity)
    assert res_45_0.upper_arm_score == 2
    assert res_45_1.upper_arm_score == 3

    # 90.0° -> 3 vs 90.1° -> 4
    res_90_0 = scorer.score(make_features(upper_arm=90.0, shoulder=0.0), validity)
    res_90_1 = scorer.score(make_features(upper_arm=90.1, shoulder=0.0), validity)
    assert res_90_0.upper_arm_score == 3
    assert res_90_1.upper_arm_score == 4


def test_shoulder_elevation_boundary() -> None:
    """Tests shrug threshold at 10.0°."""
    scorer = RulaPartialScorer()
    validity = ValidityReport(status=ValidityStatus.VALID)

    res_10_0 = scorer.score(make_features(upper_arm=15.0, shoulder=10.0), validity)
    res_10_1 = scorer.score(make_features(upper_arm=15.0, shoulder=10.1), validity)
    assert res_10_0.upper_arm_score == 1  # No shrug adjustment
    assert res_10_1.upper_arm_score == 2  # Shrug adjustment +1 applied


def test_lower_arm_boundaries() -> None:
    """Tests forearm elbow thresholds at 60.0° and 100.0°."""
    scorer = RulaPartialScorer()
    validity = ValidityReport(status=ValidityStatus.VALID)

    # 59.9° -> 2 vs 60.0° -> 1
    assert scorer.score(make_features(elbow=59.9), validity).lower_arm_score == 2
    assert scorer.score(make_features(elbow=60.0), validity).lower_arm_score == 1

    # 100.0° -> 1 vs 100.1° -> 2
    assert scorer.score(make_features(elbow=100.0), validity).lower_arm_score == 1
    assert scorer.score(make_features(elbow=100.1), validity).lower_arm_score == 2


def test_neck_boundaries() -> None:
    """Tests neck flexion thresholds at 10.0° and 20.0°."""
    scorer = RulaPartialScorer()
    validity = ValidityReport(status=ValidityStatus.VALID)

    # 10.0° -> 1 vs 10.1° -> 2
    assert scorer.score(make_features(neck=10.0), validity).neck_score == 1
    assert scorer.score(make_features(neck=10.1), validity).neck_score == 2

    # 20.0° -> 2 vs 20.1° -> 3
    assert scorer.score(make_features(neck=20.0), validity).neck_score == 2
    assert scorer.score(make_features(neck=20.1), validity).neck_score == 3


def test_trunk_boundaries() -> None:
    """Tests trunk inclination thresholds at 5.0°, 20.0°, and 60.0°."""
    scorer = RulaPartialScorer()
    validity = ValidityReport(status=ValidityStatus.VALID)

    # 5.0° -> 1 vs 5.1° -> 2
    assert scorer.score(make_features(trunk=5.0), validity).trunk_score == 1
    assert scorer.score(make_features(trunk=5.1), validity).trunk_score == 2

    # 20.0° -> 2 vs 20.1° -> 3
    assert scorer.score(make_features(trunk=20.0), validity).trunk_score == 2
    assert scorer.score(make_features(trunk=20.1), validity).trunk_score == 3

    # 60.0° -> 3 vs 60.1° -> 4
    assert scorer.score(make_features(trunk=60.0), validity).trunk_score == 3
    assert scorer.score(make_features(trunk=60.1), validity).trunk_score == 4


# ---------------------------------------------------------------------------
# Property & Invariant Tests
# ---------------------------------------------------------------------------


def test_missing_or_invalid_inputs_never_yield_numbers() -> None:
    """Critical Invariant (FR-014):

    Observations with insufficient or invalid status must NEVER yield a numeric
    grand score or action level.
    """
    scorer = RulaPartialScorer()
    features = make_features()

    for status in (ValidityStatus.INSUFFICIENT, ValidityStatus.INVALID):
        bad_rep = ValidityReport(status=status, reason_codes=["OCCLUSION_ARMS"])
        res = scorer.score(features, bad_rep)

        assert res.is_valid is False
        assert res.grand_score is None
        assert res.action_level is None
        assert res.action_level_description is None
        assert "OCCLUSION_ARMS" in res.reason_codes

    # None features input also yields None score
    res_none = scorer.score(None, ValidityReport(status=ValidityStatus.VALID))
    assert res_none.is_valid is False
    assert res_none.grand_score is None


def test_version_string_and_assessed_components_always_present() -> None:
    """Verifies that scoring_method and scoring_version are present on every output."""
    scorer = RulaPartialScorer()

    # On valid output
    res_valid = scorer.score(make_features(), ValidityReport(status=ValidityStatus.VALID))
    assert res_valid.scoring_method == "rula_partial"
    assert res_valid.scoring_version == "1.0.0"
    assert "neck" in res_valid.assessed_components
    assert "wrist_twist" in res_valid.unassessed_components

    # On invalid output
    res_invalid = scorer.score(
        None, ValidityReport(status=ValidityStatus.INVALID, reason_codes=["TEST"])
    )
    assert res_invalid.scoring_method == "rula_partial"
    assert res_invalid.scoring_version == "1.0.0"
    assert "neck" in res_invalid.assessed_components
