"""Deck construction rule validation for Magic: The Gathering Standard format.

This module provides business logic for validating deck construction rules:
- Maximum 4 copies of any card (except basic lands - unlimited)
- Format legality checking
- Clear error messages for rule violations

All functions are pure business logic with no database or UI dependencies.
"""

from dataclasses import dataclass

from src.data.schemas.card import Card
from src.data.schemas.deck import Deck


@dataclass
class ValidationResult:
    """Result of a deck construction validation operation.

    Attributes:
        is_valid: True if validation passed, False otherwise
        error_message: Human-readable error message if validation failed, None otherwise
    """

    is_valid: bool
    error_message: str | None


def is_basic_land(card: Card) -> bool:
    """Determine whether a card is a basic land.

    Basic lands are exempt from the 4-copy limit and can have unlimited copies in a deck.

    Args:
        card: The card to check

    Returns:
        True if the card's type_line contains "Basic Land" (case-insensitive), False otherwise

    Examples:
        >>> card = Card(type_line="Basic Land — Mountain", ...)
        >>> is_basic_land(card)
        True

        >>> card = Card(type_line="Land — Mountain", ...)  # Shock land, not basic
        >>> is_basic_land(card)
        False

        >>> card = Card(type_line="Creature — Goblin Warrior", ...)
        >>> is_basic_land(card)
        False
    """
    return "basic land" in card.type_line.lower()


def get_current_card_count(deck: Deck, card_id: str) -> int:
    """Calculate how many copies of a specific card are currently in a deck's mainboard.

    Only counts mainboard cards (sideboard is excluded).

    Args:
        deck: The deck to check
        card_id: The card ID to count

    Returns:
        Total quantity of the specified card in the deck's mainboard

    Examples:
        >>> deck = Deck(deck_cards=[
        ...     DeckCard(card_id="shock-id", quantity=3, sideboard=False),
        ...     DeckCard(card_id="negate-id", quantity=2, sideboard=False),
        ...     DeckCard(card_id="shock-id", quantity=1, sideboard=True),  # Sideboard excluded
        ... ])
        >>> get_current_card_count(deck, "shock-id")
        3
    """
    return sum(dc.quantity for dc in deck.deck_cards if dc.card_id == card_id and not dc.sideboard)


def validate_card_addition(deck: Deck, card: Card, quantity: int) -> ValidationResult:
    """Validate whether adding a specified quantity of a card complies with deck construction rules.

    Validates:
    - Maximum 4 copies of any non-basic land card
    - Basic lands (unlimited copies allowed)

    Args:
        deck: The deck to add cards to
        card: The card to add
        quantity: The number of copies to add

    Returns:
        ValidationResult with is_valid=True if addition is allowed, or is_valid=False with an
        error message explaining the rule violation

    Examples:
        >>> # Valid addition under 4-copy limit
        >>> deck = Deck(deck_cards=[DeckCard(card_id="bolt-id", quantity=2, sideboard=False)])
        >>> card = Card(id="bolt-id", name="Lightning Bolt", type_line="Instant", ...)
        >>> result = validate_card_addition(deck, card, 2)
        >>> result.is_valid
        True

        >>> # Invalid: exceeds 4-copy limit
        >>> deck = Deck(deck_cards=[DeckCard(card_id="bolt-id", quantity=3, sideboard=False)])
        >>> result = validate_card_addition(deck, card, 2)
        >>> result.is_valid
        False
        >>> result.error_message
        "Cannot add 2 copies of 'Lightning Bolt'. Deck would have 5 copies
        (max 4 for non-basic lands)."

        >>> # Valid: basic lands are unlimited
        >>> deck = Deck(deck_cards=[DeckCard(card_id="mountain-id", quantity=20, sideboard=False)])
        >>> card = Card(id="mountain-id", name="Mountain", type_line="Basic Land — Mountain", ...)
        >>> result = validate_card_addition(deck, card, 10)
        >>> result.is_valid
        True
    """
    # Basic lands are exempt from the 4-copy limit
    if is_basic_land(card):
        return ValidationResult(is_valid=True, error_message=None)

    # Get current count in mainboard
    current_count = get_current_card_count(deck, card.id)

    # Check if adding would exceed 4-copy limit
    total_after_addition = current_count + quantity
    max_copies = 4

    if total_after_addition > max_copies:
        if current_count >= max_copies:
            # Already at limit
            error = (
                f"Cannot add {quantity} {'copy' if quantity == 1 else 'copies'} "
                f"of '{card.name}'. Deck already has {current_count} copies "
                f"(max {max_copies} for non-basic lands)."
            )
        else:
            # Would exceed limit
            error = (
                f"Cannot add {quantity} {'copy' if quantity == 1 else 'copies'} "
                f"of '{card.name}'. Deck would have {total_after_addition} copies "
                f"(max {max_copies} for non-basic lands)."
            )
        return ValidationResult(is_valid=False, error_message=error)

    return ValidationResult(is_valid=True, error_message=None)
