"""Biomechanical posture feature calculation functions for EdgeErgo V3.

Pure functions operating on normalized landmarks with complete mathematical and
scientific documentation of physical units, ranges, and 2D projection limits.
"""

from __future__ import annotations

import numpy as np

from edge_ergo.features.angles import (
    angle_between_vectors,
    vector_to_horizontal_angle,
    vector_to_vertical_angle,
)
from edge_ergo.vision.landmarks import NormalizedLandmark


def calculate_neck_flexion(
    nose: NormalizedLandmark,
    ear_l: NormalizedLandmark | None,
    ear_r: NormalizedLandmark | None,
    shoulder_l: NormalizedLandmark,
    shoulder_r: NormalizedLandmark,
) -> float:
    """Calculates forward neck flexion / head inclination proxy in degrees.

    Definition:
        Angular deviation of the head center-of-mass vector (midpoint of ears or
        nose relative to mid-shoulder) from the vertical axis.
    Required Landmarks:
        NOSE, LEFT_SHOULDER, RIGHT_SHOULDER, and optionally LEFT_EAR, RIGHT_EAR.
    Units:
        Degrees (0.0° to 90.0°).
    Valid Range:
        0.0° (neutral upright cervical alignment) to ~60.0° (extreme forward flexion).
    Known 2D Projection Limits:
        In front-facing monocular webcams, forward head posture projects primarily as
        foreshortening and vertical descent of the nose relative to the clavicle,
        supplemented by the 3D Z coordinate from pose estimation. In oblique views,
        sagittal angular flexion is directly visible.
    """
    # Mid-shoulder coordinate
    mid_sh = np.array(
        [
            (shoulder_l.x + shoulder_r.x) / 2.0,
            (shoulder_l.y + shoulder_r.y) / 2.0,
            (shoulder_l.z + shoulder_r.z) / 2.0,
        ]
    )

    # Head reference point (mid-ears if both visible, else nose)
    if (
        ear_l is not None
        and ear_r is not None
        and ear_l.visibility > 0.4
        and ear_r.visibility > 0.4
    ):
        head_pt = np.array(
            [
                (ear_l.x + ear_r.x) / 2.0,
                (ear_l.y + ear_r.y) / 2.0,
                (ear_l.z + ear_r.z) / 2.0,
            ]
        )
    else:
        head_pt = np.array([nose.x, nose.y, nose.z])

    # Vector pointing upwards from mid-shoulder to head
    head_vector = head_pt - mid_sh

    # Angle relative to upward vertical
    flexion = vector_to_vertical_angle(head_vector)
    return round(float(np.clip(flexion, 0.0, 90.0)), 2)


def calculate_trunk_inclination(
    shoulder_l: NormalizedLandmark,
    shoulder_r: NormalizedLandmark,
    hip_l: NormalizedLandmark,
    hip_r: NormalizedLandmark,
) -> float:
    """Calculates spinal trunk inclination angle relative to gravitational vertical.

    Definition:
        Angular deviation of the torso spine vector (mid-hip to mid-shoulder)
        from the vertical axis.
    Required Landmarks:
        LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP.
    Units:
        Degrees (0.0° to 90.0°).
    Valid Range:
        0.0° (neutral upright spine) to 60.0°+ (severe forward slouch).
    Known 2D Projection Limits:
        Frontal camera viewpoints capture lateral trunk bending directly. Forward
        slouching toward the monitor causes perspective foreshortening of the
        shoulder-hip distance and forward Z displacement.
    """
    mid_sh = np.array(
        [
            (shoulder_l.x + shoulder_r.x) / 2.0,
            (shoulder_l.y + shoulder_r.y) / 2.0,
            (shoulder_l.z + shoulder_r.z) / 2.0,
        ]
    )
    mid_hip = np.array(
        [
            (hip_l.x + hip_r.x) / 2.0,
            (hip_l.y + hip_r.y) / 2.0,
            (hip_l.z + hip_r.z) / 2.0,
        ]
    )

    # Spine vector pointing upwards from mid-hip to mid-shoulder
    spine_vector = mid_sh - mid_hip

    angle = vector_to_vertical_angle(spine_vector)
    return round(float(np.clip(angle, 0.0, 90.0)), 2)


def calculate_shoulder_elevation(
    shoulder_l: NormalizedLandmark,
    shoulder_r: NormalizedLandmark,
    ear_l: NormalizedLandmark | None = None,
    ear_r: NormalizedLandmark | None = None,
) -> float:
    """Calculates shoulder elevation and asymmetry angle relative to horizontal.

    Definition:
        Angular deviation of the acromion axis (left shoulder to right shoulder)
        from the horizontal axis.
    Required Landmarks:
        LEFT_SHOULDER, RIGHT_SHOULDER.
    Units:
        Degrees (0.0° to 45.0°).
    Valid Range:
        0.0° (perfectly level shoulders) to 25.0°+ (severe unilateral elevation/shrug).
    Known 2D Projection Limits:
        Tilted webcam placement or off-axis laptop seating can induce artificial
        horizontal tilt. Workstations must aim for level webcam alignment.
    """
    sh_vector = np.array(
        [
            shoulder_r.x - shoulder_l.x,
            shoulder_r.y - shoulder_l.y,
        ]
    )
    tilt_angle = vector_to_horizontal_angle(sh_vector)
    return round(float(np.clip(tilt_angle, 0.0, 45.0)), 2)


def calculate_upper_arm_elevation(
    shoulder: NormalizedLandmark,
    elbow: NormalizedLandmark,
    hip: NormalizedLandmark,
) -> float:
    """Calculates upper arm (humerus) elevation angle relative to the torso axis.

    Definition:
        Angle formed between the upper arm vector (shoulder to elbow) and
        the torso vector (shoulder to hip).
    Required Landmarks:
        SHOULDER, ELBOW, HIP (ipsilateral side).
    Units:
        Degrees (0.0° to 180.0°).
    Valid Range:
        0.0° (arm hanging vertically at side) to 120.0°+ (extended forward reaching).
    Known 2D Projection Limits:
        Reaching straight forward toward the keyboard/mouse causes visual foreshortening
        in frontal views. 3D depth approximations from MediaPipe assist in resolving
        elevation vs. pure lateral abduction.
    """
    upper_arm_v = np.array(
        [
            elbow.x - shoulder.x,
            elbow.y - shoulder.y,
            elbow.z - shoulder.z,
        ]
    )
    torso_v = np.array(
        [
            hip.x - shoulder.x,
            hip.y - shoulder.y,
            hip.z - shoulder.z,
        ]
    )

    angle = angle_between_vectors(upper_arm_v, torso_v)
    return round(float(np.clip(angle, 0.0, 180.0)), 2)


def calculate_elbow_angle(
    shoulder: NormalizedLandmark,
    elbow: NormalizedLandmark,
    wrist: NormalizedLandmark,
) -> float:
    """Calculates the interior elbow flexion angle between upper arm and forearm.

    Definition:
        Interior joint angle formed at the elbow joint between the upper arm
        (elbow to shoulder) and forearm (elbow to wrist) vectors.
    Required Landmarks:
        SHOULDER, ELBOW, WRIST (ipsilateral side).
    Units:
        Degrees (0.0° to 180.0°).
    Valid Range:
        30.0° (acute flexion) to 180.0° (fully extended straight arm).
        Optimal ergonomic keyboarding angle is typically 90.0° to 100.0°.
    Known 2D Projection Limits:
        Wrist or forearm occlusions beneath the desk or behind the laptop keyboard
        can disrupt forearm vector tracking.
    """
    upper_arm_v = np.array(
        [
            shoulder.x - elbow.x,
            shoulder.y - elbow.y,
            shoulder.z - elbow.z,
        ]
    )
    forearm_v = np.array(
        [
            wrist.x - elbow.x,
            wrist.y - elbow.y,
            wrist.z - elbow.z,
        ]
    )

    angle = angle_between_vectors(upper_arm_v, forearm_v)
    return round(float(np.clip(angle, 0.0, 180.0)), 2)
