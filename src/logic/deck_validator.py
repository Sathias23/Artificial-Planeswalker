"""Deck construction rule validation for Magic: The Gathering constructed formats.

This module provides business logic for validating deck construction rules:
- Maximum 4 copies of any card (except basic lands - unlimited); singleton
  formats (brawl, commander, ...) get a 1-copy limit instead
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
# The size limits apply regardless of the ``format`` string; the per-card
# legality check and the copy limit are format-aware (singleton formats get a
# 1-copy limit). Commander/Brawl 100-card minima remain out of scope (a
# documented limitation).
_MIN_MAINBOARD = 60
_MAX_SIDEBOARD = 15
_MAX_COPIES = 4

#: Formats whose copy limit is 1 (basics exempt). Matched against the lowercase
#: Scryfall legality key (``validate_deck`` lowercases ``format`` defensively).
_SINGLETON_FORMATS = frozenset(
    {
        "brawl",
        "commander",
        "competitivebrawl",
        "duel",
        "gladiator",
        "oathbreaker",
        "paupercommander",
        "predh",
        "standardbrawl",
    }
)


class DeckViolation(BaseModel):
    """A single deck-construction rule violation.

    Attributes:
        rule: The construction rule that was broken.
        card_name: The offending card's name when the violation is card-specific
            (``copy_limit`` / ``singleton`` / ``format_legality`` /
            ``game_availability``); ``None`` for whole-deck rules
            (``min_deck_size`` / ``max_sideboard_size``).
        detail: Human-readable explanation of the violation.
    """

    rule: Literal[
        "min_deck_size",
        "max_sideboard_size",
        "copy_limit",
        "singleton",
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
    """Validate a deck against constructed deck-construction rules.

    Pure business logic (no database or UI). Checks:

    - **Mainboard size:** at least 60 cards (``min_deck_size``).
    - **Sideboard size:** at most 15 cards (``max_sideboard_size``).
    - **Copy limit:** at most 4 copies of any non-basic card, counted across
      mainboard and sideboard combined; basic lands are exempt (``copy_limit``).
      In singleton formats (``_SINGLETON_FORMATS`` — brawl, standardbrawl,
      commander, gladiator, etc.) the limit is 1 instead, reported as
      ``singleton``.
    - **Format legality:** each distinct card must be ``legal`` in ``format``
      (``format_legality``).
    - **Game availability:** when ``games`` is provided, each distinct card must
      be available on at least one requested platform (``game_availability``).

    The 60-card / 15-sideboard limits apply regardless of ``format`` (Phase-1
    scope, D-1.6b); the per-card legality check and the copy limit are
    format-aware. Commander/Brawl 100-card minima remain out of scope, as do
    "any number of copies" exemption cards (Seven Dwarves etc.) — the singleton
    rule shares the plain copy limit's blindness there.

    Args:
        deck: The deck to validate (mainboard and sideboard via ``deck_cards``).
        format: The MTG format to check legality against (default ``"standard"``).
            Lowercased and stripped defensively here (Scryfall legality keys and
            the singleton-format set are lowercase), so direct callers get the
            same behavior as the MCP tool layer.
        games: Optional platforms (``paper``/``arena``/``mtgo``) the deck must be
            playable on; ``None`` skips the availability check.

    Returns:
        A ``DeckValidationReport`` whose ``is_legal`` is ``True`` iff there are no
        violations.
    """
    # Defensive normalization: Scryfall legality keys and _SINGLETON_FORMATS are
    # lowercase, and direct library callers bypass the tool layer's lowercasing.
    format = format.strip().lower()
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

    # Copy limit — combined across both boards, basic lands exempt. Singleton
    # formats cap non-basics at 1 copy (rule="singleton"); everything else at 4.
    singleton = format in _SINGLETON_FORMATS
    max_copies = 1 if singleton else _MAX_COPIES
    for card_id, total in combined_counts.items():
        card = card_by_id[card_id]
        if is_basic_land(card) or total <= max_copies:
            continue
        if singleton:
            violations.append(
                DeckViolation(
                    rule="singleton",
                    card_name=card.name,
                    detail=(
                        f"{total} copies of '{card.name}'; {format} is a singleton format "
                        f"(max 1 copy of any non-basic card)."
                    ),
                )
            )
        else:
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
