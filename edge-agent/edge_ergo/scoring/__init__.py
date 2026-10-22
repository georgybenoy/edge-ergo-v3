"""Ergonomic scoring subsystem for EdgeErgo V3."""

from __future__ import annotations

from edge_ergo.scoring.recommendations import GUIDANCE_MAPPINGS, generate_recommendations
from edge_ergo.scoring.scorer import RulaPartialScorer
from edge_ergo.scoring.tables import (
    TABLE_A,
    TABLE_B,
    TABLE_C,
    lookup_table_a,
    lookup_table_b,
    lookup_table_c,
)
from edge_ergo.scoring.types import (
    ACTION_LEVEL_DESCRIPTIONS,
    ActionLevel,
    RulaScoringResult,
)

__all__ = [
    "ACTION_LEVEL_DESCRIPTIONS",
    "GUIDANCE_MAPPINGS",
    "TABLE_A",
    "TABLE_B",
    "TABLE_C",
    "ActionLevel",
    "RulaPartialScorer",
    "RulaScoringResult",
    "generate_recommendations",
    "lookup_table_a",
    "lookup_table_b",
    "lookup_table_c",
]
