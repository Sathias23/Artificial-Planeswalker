"""Pure deterministic deck-power scoring core (AD-2).

Everything in this package is a pure function or frozen constant over already-loaded inputs:
no network, no database, no clock. Format-relative scoring constants live in
:mod:`src.logic.assessment.profiles` (AD-3); the scoring math lands in later Epic-5 stories.
"""

from src.logic.assessment.classifiers import (
    CARD_DRAW,
    CATEGORIES,
    EXTRA_TURN,
    INTERACTION,
    MASS_LAND_DENIAL,
    RAMP,
    TUTOR,
    WINCON_COMBO_PIECE,
    WINCON_EXPLICIT,
    WINCON_FINISHER,
    CategoryCount,
    HardTriggerFlag,
    classify_card,
    classify_deck,
    detect_extra_turn_cards,
    detect_mass_land_denial,
)
from src.logic.assessment.profiles import (
    COMMANDER_PROFILE,
    DIMENSIONS,
    STANDARD_PROFILE,
    DimensionWeights,
    FormatProfile,
)

__all__ = [
    "CARD_DRAW",
    "CATEGORIES",
    "COMMANDER_PROFILE",
    "DIMENSIONS",
    "EXTRA_TURN",
    "INTERACTION",
    "MASS_LAND_DENIAL",
    "RAMP",
    "STANDARD_PROFILE",
    "TUTOR",
    "WINCON_COMBO_PIECE",
    "WINCON_EXPLICIT",
    "WINCON_FINISHER",
    "CategoryCount",
    "DimensionWeights",
    "FormatProfile",
    "HardTriggerFlag",
    "classify_card",
    "classify_deck",
    "detect_extra_turn_cards",
    "detect_mass_land_denial",
]
