"""Pure NumPy mathematical functions for vector angle calculations."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def angle_between_vectors(v1: npt.NDArray[np.float64], v2: npt.NDArray[np.float64]) -> float:
    """Calculates the included angle between two vectors in degrees.

    Clips the dot product to [-1.0, 1.0] to safeguard against floating-point precision NaNs.
    Returns 0.0 if either vector has near-zero magnitude.
    """
    norm1 = float(np.linalg.norm(v1))
    norm2 = float(np.linalg.norm(v2))

    if norm1 < 1e-7 or norm2 < 1e-7:
        return 0.0

    unit1 = v1 / norm1
    unit2 = v2 / norm2
    dot_product = float(np.clip(np.dot(unit1, unit2), -1.0, 1.0))
    angle_rad = float(np.arccos(dot_product))
    return float(np.degrees(angle_rad))


def vector_to_vertical_angle(vector: npt.NDArray[np.float64]) -> float:
    """Calculates the angle of a 2D/3D vector relative to the upward vertical axis [0, -1, (0)].

    In standard computer vision image space, Y grows downwards:
    - An upward vector points toward -Y (e.g. [0, -1, 0]).
    - An upright trunk pointing from hip to shoulder has negative Y delta.
    Returns angle in degrees from 0° (perfectly vertical) to 180°.
    """
    if len(vector) == 2:
        upward_vertical = np.array([0.0, -1.0], dtype=np.float64)
    else:
        upward_vertical = np.array([0.0, -1.0, 0.0], dtype=np.float64)

    return angle_between_vectors(vector, upward_vertical)


def vector_to_horizontal_angle(vector: npt.NDArray[np.float64]) -> float:
    """Calculates the tilt angle of a vector relative to the horizontal axis [1, 0].

    Returns angle in degrees from 0° (perfectly horizontal) to 90°.
    """
    if len(vector) == 2:
        horizontal = np.array([1.0, 0.0], dtype=np.float64)
    else:
        horizontal = np.array([1.0, 0.0, 0.0], dtype=np.float64)

    angle = angle_between_vectors(vector, horizontal)
    # Fold across 90° so horizontal tilt is in [0, 90]
    if angle > 90.0:
        angle = 180.0 - angle
    return angle
