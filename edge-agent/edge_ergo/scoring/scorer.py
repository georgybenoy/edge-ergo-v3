"""RulaPartialScorer implementation for EdgeErgo V3.

Implements method 'rula_partial' version '1.0.0'.
Authoritative derivation documented in docs/SCORING_METHOD.md.
"""

from __future__ import annotations

from edge_ergo.features.types import PosturalFeatures
from edge_ergo.quality.types import ValidityReport
from edge_ergo.scoring.recommendations import generate_recommendations
from edge_ergo.scoring.tables import (
    lookup_table_a,
    lookup_table_b,
    lookup_table_c,
)
from edge_ergo.scoring.types import (
    ACTION_LEVEL_DESCRIPTIONS,
    ActionLevel,
    RulaScoringResult,
)


class RulaPartialScorer:
    """Versioned RULA upper-body ergonomic screening engine."""

    METHOD_ID = "rula_partial"
    METHOD_VERSION = "1.0.0"

    def score(
        self,
        features: PosturalFeatures | None,
        validity: ValidityReport,
    ) -> RulaScoringResult:
        """Evaluates postural features into a versioned RULA screening indicator.

        FR-014: Produces a score ONLY when all required inputs are valid.
        If validity is insufficient or invalid, returns grand_score=None.
        """
        if not validity.is_valid or features is None:
            return RulaScoringResult(
                scoring_method=self.METHOD_ID,
                scoring_version=self.METHOD_VERSION,
                is_valid=False,
                grand_score=None,
                action_level=None,
                action_level_description=None,
                reason_codes=validity.reason_codes,
            )

        # 1. Upper Arm (Humerus) Score (Table A component)
        # Boundaries: 0-20° -> 1; 20-45° -> 2; 45-90° -> 3; >90° -> 4; +1 shoulder elevated
        arm_deg = features.upper_arm_elevation_deg
        if arm_deg <= 20.0:
            upper_arm = 1
        elif arm_deg <= 45.0:
            upper_arm = 2
        elif arm_deg <= 90.0:
            upper_arm = 3
        else:
            upper_arm = 4

        if features.shoulder_elevation_deg > 10.0:
            upper_arm = min(6, upper_arm + 1)

        # 2. Lower Arm (Forearm) Score (Table A component)
        # Boundaries: 60-100° -> 1; <60° or >100° -> 2
        elbow_deg = features.elbow_angle_deg
        if 60.0 <= elbow_deg <= 100.0:
            lower_arm = 1
        else:
            lower_arm = 2

        # 3. Table A Lookup (with wrist=1, twist=1)
        score_a = lookup_table_a(upper_arm, lower_arm)

        # 4. Neck Posture Score (Table B component)
        # Boundaries: 0-10° -> 1; 10-20° -> 2; >20° -> 3
        neck_deg = features.neck_flexion_deg
        if neck_deg <= 10.0:
            neck = 1
        elif neck_deg <= 20.0:
            neck = 2
        else:
            neck = 3

        # 5. Trunk Posture Score (Table B component)
        # Boundaries: 0-5° -> 1; 5-20° -> 2; 20-60° -> 3; >60° -> 4
        trunk_deg = features.trunk_inclination_deg
        if trunk_deg <= 5.0:
            trunk = 1
        elif trunk_deg <= 20.0:
            trunk = 2
        elif trunk_deg <= 60.0:
            trunk = 3
        else:
            trunk = 4

        # 6. Table B Lookup (with legs=1)
        score_b = lookup_table_b(neck, trunk)

        # 7. Table C Grand Score Lookup
        grand_score = lookup_table_c(score_a, score_b)

        # 8. Action Level Mapping
        if grand_score <= 2:
            action_level = ActionLevel.LEVEL_1
        elif grand_score <= 4:
            action_level = ActionLevel.LEVEL_2
        elif grand_score <= 6:
            action_level = ActionLevel.LEVEL_3
        else:
            action_level = ActionLevel.LEVEL_4

        action_desc = ACTION_LEVEL_DESCRIPTIONS[action_level]

        # 9. Recommendation & Guidance Generation
        guidance_codes, recommendations = generate_recommendations(
            features=features,
            neck_score=neck,
            trunk_score=trunk,
            upper_arm_score=upper_arm,
            lower_arm_score=lower_arm,
        )

        return RulaScoringResult(
            scoring_method=self.METHOD_ID,
            scoring_version=self.METHOD_VERSION,
            is_valid=True,
            grand_score=grand_score,
            action_level=int(action_level),
            action_level_description=action_desc,
            neck_score=neck,
            trunk_score=trunk,
            upper_arm_score=upper_arm,
            lower_arm_score=lower_arm,
            score_a=score_a,
            score_b=score_b,
            guidance_codes=guidance_codes,
            recommendations=recommendations,
            reason_codes=[],
        )
