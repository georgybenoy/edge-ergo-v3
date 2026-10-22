"""Ergonomic recommendation generator linking specific postural rules to stable guidance codes.

Satisfies FR-015: Recommendations are strictly derived from validated joint angle observations.
Neutral, actionable wording per DESIGN.md §10.
"""

from __future__ import annotations

from edge_ergo.features.types import PosturalFeatures

GUIDANCE_MAPPINGS = {
    "GUID_NECK_FLEX_01": (
        "Your screen may be too low; consider raising your monitor so the top third "
        "is at eye level."
    ),
    "GUID_TRUNK_INCL_01": (
        "Consider adjusting your backrest to support an upright or slightly reclined posture "
        "(100°–110°)."
    ),
    "GUID_SHOULDER_ELEV_01": (
        "Shoulder shrugging observed. Try lowering desk height or armrests to relax upper "
        "trapezius muscles."
    ),
    "GUID_ARM_ELEV_01": (
        "Your keyboard or mouse may be too far forward; try bringing them closer to reduce "
        "forward reach."
    ),
    "GUID_ELBOW_ANGLE_01": (
        "Consider adjusting chair height so forearms rest parallel to the desk surface."
    ),
    "GENERAL_GOOD_POSTURE": "Posture indicators are within recommended neutral ranges.",
}


def generate_recommendations(
    features: PosturalFeatures,
    neck_score: int,
    trunk_score: int,
    upper_arm_score: int,
    lower_arm_score: int,
) -> tuple[list[str], list[str]]:
    """Maps feature observations and subscores to stable guidance codes and user recommendations."""
    guidance_codes: list[str] = []
    recommendations: list[str] = []

    # Rule 1: Neck flexion / forward head posture
    if neck_score >= 3 or features.neck_flexion_deg > 20.0:
        guidance_codes.append("GUID_NECK_FLEX_01")
        recommendations.append(GUIDANCE_MAPPINGS["GUID_NECK_FLEX_01"])

    # Rule 2: Trunk inclination / forward slouching
    if trunk_score >= 3 or features.trunk_inclination_deg > 20.0:
        guidance_codes.append("GUID_TRUNK_INCL_01")
        recommendations.append(GUIDANCE_MAPPINGS["GUID_TRUNK_INCL_01"])

    # Rule 3: Shoulder elevation / shrugging
    if features.shoulder_elevation_deg > 10.0:
        guidance_codes.append("GUID_SHOULDER_ELEV_01")
        recommendations.append(GUIDANCE_MAPPINGS["GUID_SHOULDER_ELEV_01"])

    # Rule 4: Upper arm elevation / forward reaching
    if upper_arm_score >= 3 or features.upper_arm_elevation_deg > 45.0:
        guidance_codes.append("GUID_ARM_ELEV_01")
        recommendations.append(GUIDANCE_MAPPINGS["GUID_ARM_ELEV_01"])

    # Rule 5: Non-neutral elbow angle (< 60° or > 100°)
    if lower_arm_score >= 2 or features.elbow_angle_deg < 60.0 or features.elbow_angle_deg > 100.0:
        guidance_codes.append("GUID_ELBOW_ANGLE_01")
        recommendations.append(GUIDANCE_MAPPINGS["GUID_ELBOW_ANGLE_01"])

    # Neutral fallback when all parameters are good
    if not guidance_codes:
        guidance_codes.append("GENERAL_GOOD_POSTURE")
        recommendations.append(GUIDANCE_MAPPINGS["GENERAL_GOOD_POSTURE"])

    return guidance_codes, recommendations
