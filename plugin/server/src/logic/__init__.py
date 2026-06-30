"""Business logic layer for Artificial-Planeswalker.

This layer contains pure business logic with no database or UI dependencies.
Includes domain rules for deck validation, mana curve analysis, and synergy detection.
"""

from src.logic.deck_validator import (
    ValidationResult,
    get_current_card_count,
    is_basic_land,
    validate_card_addition,
)

__all__ = [
    "ValidationResult",
    "get_current_card_count",
    "is_basic_land",
    "validate_card_addition",
]
