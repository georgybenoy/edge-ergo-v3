"""Typed scoring results and Action Level enumerations for EdgeErgo V3."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class ActionLevel(IntEnum):
    """RULA Action Levels (McAtamney & Corlett, 1993)."""

    LEVEL_1 = 1  # Scores 1-2: Acceptable
    LEVEL_2 = 2  # Scores 3-4: Further investigation needed
    LEVEL_3 = 3  # Scores 5-6: Investigate and change soon
    LEVEL_4 = 4  # Score 7: Investigate and change immediately


ACTION_LEVEL_DESCRIPTIONS = {
    ActionLevel.LEVEL_1: "Posture is currently acceptable; maintain neutral positioning.",
    ActionLevel.LEVEL_2: (
        "Further investigation may be beneficial; minor workstation adjustments recommended."
    ),
    ActionLevel.LEVEL_3: "Investigation and workstation ergonomic changes recommended soon.",
    ActionLevel.LEVEL_4: "Immediate workstation ergonomic intervention and adjustment required.",
}


@dataclass(frozen=True)
class RulaScoringResult:
    """Comprehensive ergonomic screening result produced by RulaPartialScorer.

    Guarantees:
    - grand_score is strictly None whenever is_valid is False.
    - Every result contains explicit scoring_method and scoring_version strings.
    - Transparently declares assessed vs. unassessed components.
    """

    scoring_method: str = "rula_partial"
    scoring_version: str = "1.0.0"
    is_valid: bool = False
    grand_score: int | None = None
    action_level: int | None = None
    action_level_description: str | None = None
    neck_score: int | None = None
    trunk_score: int | None = None
    upper_arm_score: int | None = None
    lower_arm_score: int | None = None
    score_a: int | None = None
    score_b: int | None = None
    guidance_codes: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    assessed_components: list[str] = field(
        default_factory=lambda: ["neck", "trunk", "upper_arm", "lower_arm"]
    )
    unassessed_components: list[str] = field(
        default_factory=lambda: ["wrist_twist", "muscle_use", "force_load", "legs"]
    )
