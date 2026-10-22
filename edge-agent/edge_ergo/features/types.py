"""Postural features dataclass representing biomechanical joint angles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PosturalFeatures:
    """Approved ergonomic posture features extracted from validated pose landmarks.

    Features are strictly angular quantities (degrees). No raw coordinates,
    no pixel data, and zero personal biometric identifiers are retained.
    """

    neck_flexion_deg: float
    trunk_inclination_deg: float
    shoulder_elevation_deg: float
    upper_arm_elevation_deg: float
    elbow_angle_deg: float
    left_upper_arm_deg: float
    right_upper_arm_deg: float
    left_elbow_deg: float
    right_elbow_deg: float
