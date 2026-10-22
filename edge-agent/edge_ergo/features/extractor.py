"""Feature extraction orchestrator mapping raw pose landmarks to PosturalFeatures.

CRITICAL ARCHITECTURAL BOUNDARY:
This module has zero knowledge of ergonomic scoring algorithms (RULA/REBA).
It maps spatial landmarks to strictly physical angular features.
"""

from __future__ import annotations

from edge_ergo.features.posture import (
    calculate_elbow_angle,
    calculate_neck_flexion,
    calculate_shoulder_elevation,
    calculate_trunk_inclination,
    calculate_upper_arm_elevation,
)
from edge_ergo.features.types import PosturalFeatures
from edge_ergo.vision.landmarks import PoseLandmarkIndex, RawPoseLandmarks


def extract_postural_features(landmarks: RawPoseLandmarks) -> PosturalFeatures:
    """Extracts approved angular posture features from raw pose landmarks."""
    nose = landmarks.get(PoseLandmarkIndex.NOSE)
    l_ear = landmarks.get(PoseLandmarkIndex.LEFT_EAR)
    r_ear = landmarks.get(PoseLandmarkIndex.RIGHT_EAR)
    l_sh = landmarks.get(PoseLandmarkIndex.LEFT_SHOULDER)
    r_sh = landmarks.get(PoseLandmarkIndex.RIGHT_SHOULDER)
    l_hip = landmarks.get(PoseLandmarkIndex.LEFT_HIP)
    r_hip = landmarks.get(PoseLandmarkIndex.RIGHT_HIP)

    if nose is None or l_sh is None or r_sh is None or l_hip is None or r_hip is None:
        raise ValueError("Missing essential torso/head landmarks for feature extraction")

    # Axial angles (neck & trunk)
    neck_flexion = calculate_neck_flexion(nose, l_ear, r_ear, l_sh, r_sh)
    trunk_inclination = calculate_trunk_inclination(l_sh, r_sh, l_hip, r_hip)
    shoulder_elevation = calculate_shoulder_elevation(l_sh, r_sh, l_ear, r_ear)

    # Upper limbs (left & right sides)
    l_el = landmarks.get(PoseLandmarkIndex.LEFT_ELBOW)
    r_el = landmarks.get(PoseLandmarkIndex.RIGHT_ELBOW)
    l_wr = landmarks.get(PoseLandmarkIndex.LEFT_WRIST)
    r_wr = landmarks.get(PoseLandmarkIndex.RIGHT_WRIST)

    l_arm_elev = calculate_upper_arm_elevation(l_sh, l_el, l_hip) if l_el is not None else 0.0
    r_arm_elev = calculate_upper_arm_elevation(r_sh, r_el, r_hip) if r_el is not None else 0.0

    l_elbow_angle = (
        calculate_elbow_angle(l_sh, l_el, l_wr) if (l_el is not None and l_wr is not None) else 90.0
    )
    r_elbow_angle = (
        calculate_elbow_angle(r_sh, r_el, r_wr) if (r_el is not None and r_wr is not None) else 90.0
    )

    # For bilateral screening, take the most loaded / higher elevation arm
    primary_arm_elev = max(l_arm_elev, r_arm_elev)

    # Representative elbow angle on the side with higher upper-arm engagement
    if r_arm_elev > l_arm_elev:
        primary_elbow = r_elbow_angle
    else:
        primary_elbow = l_elbow_angle

    return PosturalFeatures(
        neck_flexion_deg=neck_flexion,
        trunk_inclination_deg=trunk_inclination,
        shoulder_elevation_deg=shoulder_elevation,
        upper_arm_elevation_deg=primary_arm_elev,
        elbow_angle_deg=primary_elbow,
        left_upper_arm_deg=l_arm_elev,
        right_upper_arm_deg=r_arm_elev,
        left_elbow_deg=l_elbow_angle,
        right_elbow_deg=r_elbow_angle,
    )
