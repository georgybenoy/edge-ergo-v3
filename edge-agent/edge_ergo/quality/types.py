"""Validity reports and reason codes for ergonomic observation quality."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidityStatus(str, Enum):
    """Overall ergonomic validity status of a captured observation."""

    VALID = "valid"
    INSUFFICIENT = "insufficient"
    INVALID = "invalid"


@dataclass(frozen=True)
class ValidityReport:
    """Comprehensive quality evaluation report for a single observation.

    FR-008 Guarantee:
    If any essential landmark is occluded or confidence is low, the status is
    marked INSUFFICIENT or INVALID and score calculation is strictly aborted.
    """

    status: ValidityStatus
    reason_codes: list[str] = field(default_factory=list)
    confidence_score: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return self.status == ValidityStatus.VALID
