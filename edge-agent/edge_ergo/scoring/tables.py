"""Authoritative RULA lookup tables (McAtamney & Corlett, 1993).

Source:
McAtamney, L., & Corlett, E. N. (1993). RULA: a survey method for the
investigation of work-related upper limb disorders. Applied Ergonomics, 24(2), 91-99.
"""

from __future__ import annotations

# Table A with wrist = 1 and wrist_twist = 1
# Row index: upper_arm score (1 to 6) -> 0-indexed [0..5]
# Col index: lower_arm score (1 to 2) -> 0-indexed [0..1]
TABLE_A: list[list[int]] = [
    [1, 2],  # upper_arm = 1
    [2, 2],  # upper_arm = 2
    [3, 3],  # upper_arm = 3
    [4, 4],  # upper_arm = 4
    [5, 5],  # upper_arm = 5
    [6, 6],  # upper_arm = 6
]

# Table B with legs = 1 (legs and feet supported seated posture)
# Row index: neck score (1 to 6) -> 0-indexed [0..5]
# Col index: trunk score (1 to 6) -> 0-indexed [0..5]
TABLE_B: list[list[int]] = [
    [1, 2, 3, 5, 6, 7],  # neck = 1
    [2, 3, 4, 6, 7, 7],  # neck = 2
    [3, 4, 5, 6, 7, 8],  # neck = 3
    [5, 5, 6, 7, 8, 8],  # neck = 4
    [6, 6, 7, 8, 8, 8],  # neck = 5
    [7, 7, 8, 8, 8, 8],  # neck = 6
]

# Table C (Grand Score Matrix)
# Row index: Score A (1 to 8+) -> 0-indexed [0..7]
# Col index: Score B (1 to 8+) -> 0-indexed [0..7]
# Returns Grand Score (1 to 7)
TABLE_C: list[list[int]] = [
    [1, 2, 3, 3, 4, 5, 5, 5],  # Score A = 1
    [2, 2, 3, 4, 4, 5, 5, 5],  # Score A = 2
    [3, 3, 3, 4, 4, 5, 6, 6],  # Score A = 3
    [3, 3, 4, 5, 5, 6, 6, 7],  # Score A = 4
    [4, 4, 4, 5, 6, 7, 7, 7],  # Score A = 5
    [4, 4, 5, 6, 6, 7, 7, 7],  # Score A = 6
    [5, 5, 6, 6, 7, 7, 7, 7],  # Score A = 7
    [5, 5, 6, 7, 7, 7, 7, 7],  # Score A = 8+
]


def lookup_table_a(upper_arm: int, lower_arm: int) -> int:
    """Performs Table A lookup with bounded index safety."""
    row = max(0, min(5, upper_arm - 1))
    col = max(0, min(1, lower_arm - 1))
    return TABLE_A[row][col]


def lookup_table_b(neck: int, trunk: int) -> int:
    """Performs Table B lookup with bounded index safety."""
    row = max(0, min(5, neck - 1))
    col = max(0, min(5, trunk - 1))
    return TABLE_B[row][col]


def lookup_table_c(score_a: int, score_b: int) -> int:
    """Performs Table C lookup returning final RULA grand score (1 to 7)."""
    row = max(0, min(7, score_a - 1))
    col = max(0, min(7, score_b - 1))
    return TABLE_C[row][col]
