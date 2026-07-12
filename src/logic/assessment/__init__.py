"""Pure deterministic deck-power scoring core (AD-2).

Everything in this package is a pure function or frozen constant over already-loaded inputs:
no network, no database, no clock. Format-relative scoring constants live in
:mod:`src.logic.assessment.profiles` (AD-3); the scoring math lands in later Epic-5 stories.
"""

from src.logic.assessment.profiles import (
    COMMANDER_PROFILE,
    DIMENSIONS,
    STANDARD_PROFILE,
    DimensionWeights,
    FormatProfile,
)

__all__ = [
    "COMMANDER_PROFILE",
    "DIMENSIONS",
    "STANDARD_PROFILE",
    "DimensionWeights",
    "FormatProfile",
]
