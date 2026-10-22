"""Feature extraction subsystem for EdgeErgo V3."""

from __future__ import annotations

from edge_ergo.features.angles import (
    angle_between_vectors,
    vector_to_horizontal_angle,
    vector_to_vertical_angle,
)
from edge_ergo.features.extractor import extract_postural_features
from edge_ergo.features.posture import (
    calculate_elbow_angle,
    calculate_neck_flexion,
    calculate_shoulder_elevation,
    calculate_trunk_inclination,
    calculate_upper_arm_elevation,
)
from edge_ergo.features.types import PosturalFeatures

__all__ = [
    "PosturalFeatures",
    "angle_between_vectors",
    "calculate_elbow_angle",
    "calculate_neck_flexion",
    "calculate_shoulder_elevation",
    "calculate_trunk_inclination",
    "calculate_upper_arm_elevation",
    "extract_postural_features",
    "vector_to_horizontal_angle",
    "vector_to_vertical_angle",
]
