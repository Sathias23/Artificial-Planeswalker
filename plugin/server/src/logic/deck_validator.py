"""Deck construction rule validation for Magic: The Gathering Standard format.

This module provides business logic for validating deck construction rules:
- Maximum 4 copies of any card (except basic lands - unlimited)
- Format legality checking
- Clear error messages for rule violations

All functions are pure business logic with no database or UI dependencies.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

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


# --- Whole-deck validation (Story 1.6, additive) ---

# Constructed-format (Standard) construction limits — Phase-1 scope (D-1.6b).
# These apply regardless of the ``format`` string; only the per-card legality
# check is format-aware. Commander/Brawl singleton + 100-card minima are out of
# scope (a documented Phase-1 limitation).
_MIN_MAINBOARD = 60
_MAX_SIDEBOARD = 15
_MAX_COPIES = 4


class DeckViolation(BaseModel):
    """A single deck-construction rule violation.

    Attributes:
        rule: The construction rule that was broken.
        card_name: The offending card's name when the violation is card-specific
            (``copy_limit`` / ``format_legality`` / ``game_availability``);
            ``None`` for whole-deck rules (``min_deck_size`` / ``max_sideboard_size``).
        detail: Human-readable explanation of the violation.
    """

    rule: Literal[
        "min_deck_size",
        "max_sideboard_size",
        "copy_limit",
        "format_legality",
        "game_availability",
    ]
    card_name: str | None = None
    detail: str


class DeckValidationReport(BaseModel):
    """Whole-deck construction-legality report.

    ``is_legal`` is ``True`` if and only if ``violations`` is empty.

    Attributes:
        is_legal: Whether the deck passed every checked rule.
        format: The format the deck was validated against.
        mainboard_count: Total mainboard cards (summed by quantity).
        sideboard_count: Total sideboard cards (summed by quantity).
        violations: Every rule violation found (empty when ``is_legal`` is True).
    """

    is_legal: bool
    format: str
    mainboard_count: int
    sideboard_count: int
    violations: list[DeckViolation] = []


def validate_deck(
    deck: Deck, *, format: str = "standard", games: list[str] | None = None
) -> DeckValidationReport:
    """Validate a deck against constructed (60-card) deck-construction rules.

    Pure business logic (no database or UI). Checks:

    - **Mainboard size:** at least 60 cards (``min_deck_size``).
    - **Sideboard size:** at most 15 cards (``max_sideboard_size``).
    - **Copy limit:** at most 4 copies of any non-basic card, counted across
      mainboard and sideboard combined; basic lands are exempt (``copy_limit``).
    - **Format legality:** each distinct card must be ``legal`` in ``format``
      (``format_legality``).
    - **Game availability:** when ``games`` is provided, each distinct card must
      be available on at least one requested platform (``game_availability``).

    The 60-card / 15-sideboard limits apply regardless of ``format`` (Phase-1
    scope, D-1.6b); only the per-card legality check is format-aware. Commander/
    Brawl singleton and 100-card minima are out of scope.

    Args:
        deck: The deck to validate (mainboard and sideboard via ``deck_cards``).
        format: The MTG format to check legality against (default ``"standard"``).
        games: Optional platforms (``paper``/``arena``/``mtgo``) the deck must be
            playable on; ``None`` skips the availability check.

    Returns:
        A ``DeckValidationReport`` whose ``is_legal`` is ``True`` iff there are no
        violations.
    """
    mainboard_count = sum(dc.quantity for dc in deck.deck_cards if not dc.sideboard)
    sideboard_count = sum(dc.quantity for dc in deck.deck_cards if dc.sideboard)
    violations: list[DeckViolation] = []

    if mainboard_count < _MIN_MAINBOARD:
        violations.append(
            DeckViolation(
                rule="min_deck_size",
                detail=(
                    f"Mainboard has {mainboard_count} cards; "
                    f"{format} requires at least {_MIN_MAINBOARD}."
                ),
            )
        )
    if sideboard_count > _MAX_SIDEBOARD:
        violations.append(
            DeckViolation(
                rule="max_sideboard_size",
                detail=f"Sideboard has {sideboard_count} cards; the maximum is {_MAX_SIDEBOARD}.",
            )
        )

    # Tally each distinct card once: combined copies (both boards) for the copy
    # limit, plus the card itself for the per-distinct-card legality/availability
    # checks. Insertion order follows first appearance, keeping output deterministic.
    combined_counts: dict[str, int] = {}
    card_by_id: dict[str, Card] = {}
    for dc in deck.deck_cards:
        if dc.card is None:
            continue
        combined_counts[dc.card_id] = combined_counts.get(dc.card_id, 0) + dc.quantity
        card_by_id[dc.card_id] = dc.card

    # 4-copy limit — combined across both boards, basic lands exempt.
    for card_id, total in combined_counts.items():
        card = card_by_id[card_id]
        if not is_basic_land(card) and total > _MAX_COPIES:
            violations.append(
                DeckViolation(
                    rule="copy_limit",
                    card_name=card.name,
                    detail=(
                        f"{total} copies of '{card.name}' (max {_MAX_COPIES} for non-basic cards)."
                    ),
                )
            )

    # Per-distinct-card format legality + optional game availability.
    for card in card_by_id.values():
        if card.legalities.get(format) != "legal":
            violations.append(
                DeckViolation(
                    rule="format_legality",
                    card_name=card.name,
                    detail=f"'{card.name}' is not legal in {format}.",
                )
            )
        if games and not (set(card.games) & set(games)):
            violations.append(
                DeckViolation(
                    rule="game_availability",
                    card_name=card.name,
                    detail=f"'{card.name}' is not available on {', '.join(games)}.",
                )
            )

    return DeckValidationReport(
        is_legal=not violations,
        format=format,
        mainboard_count=mainboard_count,
        sideboard_count=sideboard_count,
        violations=violations,
    )
