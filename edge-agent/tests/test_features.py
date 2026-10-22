"""Tests for vector mathematics and postural feature calculations against ground truth."""

from __future__ import annotations

import numpy as np
import pytest

from edge_ergo.features.angles import (
    angle_between_vectors,
    vector_to_horizontal_angle,
    vector_to_vertical_angle,
)
from edge_ergo.features.extractor import extract_postural_features
from edge_ergo.features.posture import (
    calculate_elbow_angle,
    calculate_upper_arm_elevation,
)
from edge_ergo.vision.landmarks import NormalizedLandmark, RawPoseLandmarks
from edge_ergo.vision.synthetic_estimator import create_neutral_landmarks


def test_vector_angle_ground_truth() -> None:
    """Verifies vector angle calculations against exact analytical geometric ground truth."""
    # 1. Orthogonal 2D vectors: 90°
    v1 = np.array([1.0, 0.0])
    v2 = np.array([0.0, 1.0])
    assert pytest.approx(angle_between_vectors(v1, v2), abs=1e-5) == 90.0

    # 2. Collinear identical vectors: 0°
    v_collinear = np.array([2.5, 0.0])
    assert pytest.approx(angle_between_vectors(v1, v_collinear), abs=1e-5) == 0.0

    # 3. Opposite collinear vectors: 180°
    v_opp = np.array([-1.0, 0.0])
    assert pytest.approx(angle_between_vectors(v1, v_opp), abs=1e-5) == 180.0

    # 4. Diagonal 45° vector
    v_diag = np.array([1.0, 1.0])
    assert pytest.approx(angle_between_vectors(v1, v_diag), abs=1e-5) == 45.0

    # 5. 3D Orthogonal vectors
    v3d_x = np.array([1.0, 0.0, 0.0])
    v3d_z = np.array([0.0, 0.0, 1.0])
    assert pytest.approx(angle_between_vectors(v3d_x, v3d_z), abs=1e-5) == 90.0

    # 6. Zero vector edge case returns 0.0 without NaN
    v_zero = np.array([0.0, 0.0])
    assert angle_between_vectors(v1, v_zero) == 0.0


def test_vertical_and_horizontal_tilt_angles() -> None:
    """Verifies angle_to_vertical and angle_to_horizontal conventions in CV space (Y downward)."""
    # Upward vector in image space is [0, -1] -> 0° vertical
    upward = np.array([0.0, -1.0])
    assert pytest.approx(vector_to_vertical_angle(upward), abs=1e-5) == 0.0

    # Downward vector [0, 1] -> 180°
    downward = np.array([0.0, 1.0])
    assert pytest.approx(vector_to_vertical_angle(downward), abs=1e-5) == 180.0

    # 45° forward/tilted vector [1, -1]
    tilted_45 = np.array([1.0, -1.0])
    assert pytest.approx(vector_to_vertical_angle(tilted_45), abs=1e-5) == 45.0

    # Horizontal tilt: [1, 0] -> 0°
    horiz = np.array([1.0, 0.0])
    assert pytest.approx(vector_to_horizontal_angle(horiz), abs=1e-5) == 0.0


def test_elbow_angle_ground_truth() -> None:
    """Verifies elbow joint interior angle at 90° right angle and 180° straight arm."""
    # Right-angle elbow (upper arm vertical [0, 1], forearm horizontal [1, 0])
    sh = NormalizedLandmark(x=0.5, y=0.2, z=0.0, visibility=0.9)
    elbow = NormalizedLandmark(x=0.5, y=0.5, z=0.0, visibility=0.9)
    wrist_90 = NormalizedLandmark(x=0.8, y=0.5, z=0.0, visibility=0.9)

    angle_90 = calculate_elbow_angle(sh, elbow, wrist_90)
    assert pytest.approx(angle_90, abs=1e-2) == 90.0

    # Fully extended straight arm (wrist at [0.5, 0.8])
    wrist_180 = NormalizedLandmark(x=0.5, y=0.8, z=0.0, visibility=0.9)
    angle_180 = calculate_elbow_angle(sh, elbow, wrist_180)
    assert pytest.approx(angle_180, abs=1e-2) == 180.0


def test_upper_arm_elevation_ground_truth() -> None:
    """Verifies upper arm elevation relative to torso."""
    # Arm resting straight along torso: 0°
    hip = NormalizedLandmark(x=0.5, y=0.8, z=0.0, visibility=0.9)
    sh = NormalizedLandmark(x=0.5, y=0.3, z=0.0, visibility=0.9)
    elbow_hanging = NormalizedLandmark(x=0.5, y=0.6, z=0.0, visibility=0.9)

    angle_0 = calculate_upper_arm_elevation(sh, elbow_hanging, hip)
    assert pytest.approx(angle_0, abs=1e-2) == 0.0

    # Arm raised 90° horizontal
    elbow_90 = NormalizedLandmark(x=0.8, y=0.3, z=0.0, visibility=0.9)
    angle_90 = calculate_upper_arm_elevation(sh, elbow_90, hip)
    assert pytest.approx(angle_90, abs=1e-2) == 90.0


def test_extract_postural_features_neutral() -> None:
    """Verifies extraction of PosturalFeatures on standard neutral sitting landmark fixture."""
    lms = RawPoseLandmarks(create_neutral_landmarks(visibility=0.95))
    features = extract_postural_features(lms)

    assert features.neck_flexion_deg >= 0.0
    assert features.trunk_inclination_deg >= 0.0
    assert features.shoulder_elevation_deg <= 5.0  # level shoulders in neutral
    assert 70.0 <= features.elbow_angle_deg <= 110.0  # ~90° typing posture
    assert features.upper_arm_elevation_deg <= 25.0
