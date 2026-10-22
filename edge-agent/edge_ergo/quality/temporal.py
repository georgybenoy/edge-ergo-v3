"""Temporal quality smoothing filter for EdgeErgo V3.

FR-008 Guarantee:
Temporal smoothing requires consecutive valid observations to confirm stability,
but NEVER imputes, interpolates, or synthesizes missing or occluded landmark data.
"""

from __future__ import annotations

import threading

from edge_ergo.quality.types import ValidityReport, ValidityStatus


class TemporalQualityFilter:
    """Enforces temporal continuity without data fabrication."""

    def __init__(self, min_consecutive_valid: int = 2) -> None:
        self._min_consecutive = max(1, min_consecutive_valid)
        self._consecutive_valid_count = 0
        self._lock = threading.Lock()

    def process(self, instant_report: ValidityReport) -> ValidityReport:
        """Processes an instantaneous validity report against temporal continuity rules."""
        with self._lock:
            if not instant_report.is_valid:
                # Reset consecutive count upon any invalid or insufficient frame
                self._consecutive_valid_count = 0
                return instant_report

            self._consecutive_valid_count += 1

            if self._consecutive_valid_count < self._min_consecutive:
                # Posture is stabilizing; hold until minimum consecutive threshold is reached
                reasons = list(instant_report.reason_codes) + ["TEMPORAL_STABILIZING"]
                return ValidityReport(
                    status=ValidityStatus.INSUFFICIENT,
                    reason_codes=reasons,
                    confidence_score=instant_report.confidence_score,
                    details={
                        **instant_report.details,
                        "consecutive_valid": self._consecutive_valid_count,
                        "required_consecutive": self._min_consecutive,
                    },
                )

            return instant_report

    def reset(self) -> None:
        """Resets the temporal tracking state."""
        with self._lock:
            self._consecutive_valid_count = 0
