"""Synergy detection for Magic: The Gathering decks.

This module provides pattern-based synergy detection for decks, identifying:
- Tribal synergies (shared creature types)
- Keyword synergies (keyword-matters cards)
- Mechanic combos (sacrifice outlets, graveyard synergies, etc.)
"""

import logging
import re
from typing import Literal

from pydantic import BaseModel, field_validator

from src.data.schemas.deck import DeckCard

logger = logging.getLogger(__name__)

# Supported keywords for synergy detection
COMMON_KEYWORDS = {
    "flying",
    "lifelink",
    "deathtouch",
    "trample",
    "vigilance",
    "first strike",
    "double strike",
    "menace",
    "reach",
    "haste",
    "hexproof",
    "indestructible",
}


class SynergyPattern(BaseModel):
    """A detected synergy pattern in a deck.

    Attributes:
        pattern_type: Type of synergy (tribal, keyword, or mechanic_combo)
        subtype: Specific name (e.g., "Goblin", "flying", "sacrifice")
        affected_cards: List of card names involved in synergy
        explanation: Human-readable description of the synergy
        strength: Classification based on percentage of deck involved
    """

    pattern_type: Literal["tribal", "keyword", "mechanic_combo"]
    subtype: str
    affected_cards: list[str]
    explanation: str
    strength: Literal["weak", "moderate", "strong"]

    @field_validator("affected_cards")
    @classmethod
    def validate_affected_cards(cls, v: list[str]) -> list[str]:
        """Validate that affected_cards list is not empty."""
        if not v:
            raise ValueError("affected_cards list cannot be empty")
        return v


class SynergyAnalysis(BaseModel):
    """Complete synergy analysis results for a deck.

    Attributes:
        synergies: List of detected synergy patterns
        total_count: Number of synergies detected (computed automatically)
        deck_cohesion: Overall deck synergy assessment
    """

    synergies: list[SynergyPattern]
    deck_cohesion: Literal["low", "moderate", "high"]

    @property
    def total_count(self) -> int:
        """Compute total_count from synergies list length."""
        return len(self.synergies)


def detect_synergies(deck_cards: list[DeckCard]) -> SynergyAnalysis:
    """Detect synergy patterns in a deck.

    Analyzes deck composition to identify tribal synergies, keyword synergies,
    and mechanic combos. Returns comprehensive analysis with explanations.

    Args:
        deck_cards: List of DeckCard instances from the deck

    Returns:
        SynergyAnalysis with detected patterns and deck cohesion assessment
    """
    if not deck_cards:
        return SynergyAnalysis(synergies=[], deck_cohesion="low")

    deck_size = sum(card.quantity for card in deck_cards)
    synergies: list[SynergyPattern] = []

    # Detect tribal synergies
    tribal_synergies = _detect_tribal_synergies(deck_cards, deck_size)
    synergies.extend(tribal_synergies)

    # Detect keyword synergies
    keyword_synergies = _detect_keyword_synergies(deck_cards, deck_size)
    synergies.extend(keyword_synergies)

    # Detect mechanic combos
    mechanic_combos = _detect_mechanic_combos(deck_cards, deck_size)
    synergies.extend(mechanic_combos)

    # Calculate deck cohesion
    cohesion = _calculate_deck_cohesion(synergies, deck_cards, deck_size)

    return SynergyAnalysis(synergies=synergies, deck_cohesion=cohesion)


def _detect_tribal_synergies(deck_cards: list[DeckCard], deck_size: int) -> list[SynergyPattern]:
    """Detect tribal synergies based on creature types.

    Args:
        deck_cards: List of DeckCard instances
        deck_size: Total number of cards in deck

    Returns:
        List of detected tribal SynergyPattern instances
    """
    # Extract creature types from all cards
    creature_types_map: dict[str, list[str]] = {}  # tribe -> card names
    tribal_payoff_map: dict[str, list[str]] = {}  # tribe -> payoff card names

    for deck_card in deck_cards:
        card = deck_card.card
        card_name = card.name

        # Extract creature types from type line
        if "Creature" in card.type_line:
            types = _extract_creature_types(card.type_line)
            for creature_type in types:
                if creature_type not in creature_types_map:
                    creature_types_map[creature_type] = []
                # Add card multiple times for quantity
                creature_types_map[creature_type].extend([card_name] * deck_card.quantity)

        # Check for tribal payoff cards
        if card.oracle_text:
            oracle_lower = card.oracle_text.lower()
            # Pattern matching for tribal payoffs
            for creature_type in creature_types_map.keys():
                type_lower = creature_type.lower()
                # Match patterns like "Goblin creatures", "other Goblins", "Goblin you control"
                patterns = [
                    rf"\b{type_lower} creatures?\b",
                    rf"\bother {type_lower}s?\b",
                    rf"\b{type_lower}s? you control\b",
                ]
                if any(re.search(pattern, oracle_lower) for pattern in patterns):
                    if creature_type not in tribal_payoff_map:
                        tribal_payoff_map[creature_type] = []
                    tribal_payoff_map[creature_type].extend([card_name] * deck_card.quantity)

    # Build synergy patterns
    synergies: list[SynergyPattern] = []

    for tribe, creature_cards in creature_types_map.items():
        # Minimum threshold: 5 creatures of same type
        if len(creature_cards) < 5:
            continue

        payoff_cards = tribal_payoff_map.get(tribe, [])
        total_cards = len(creature_cards) + len(payoff_cards)

        # Skip if too weak (< 10% of deck)
        if total_cards < deck_size * 0.1:
            continue

        # Calculate strength
        percentage = total_cards / deck_size
        strength: Literal["weak", "moderate", "strong"]
        if percentage > 0.3:
            strength = "strong"
        elif percentage > 0.1:
            strength = "moderate"
        else:
            strength = "weak"

        # Create explanation
        affected_card_names = list(set(creature_cards + payoff_cards))
        creature_count = len(creature_cards)
        payoff_count = len(payoff_cards)

        if payoff_count > 0:
            explanation = (
                f"{creature_count} {tribe} creatures synergize with "
                f"{payoff_count} tribal payoff cards"
            )
        else:
            explanation = f"{creature_count} {tribe} creatures create tribal density"

        synergies.append(
            SynergyPattern(
                pattern_type="tribal",
                subtype=tribe,
                affected_cards=affected_card_names,
                explanation=explanation,
                strength=strength,
            )
        )

    return synergies


def _detect_keyword_synergies(deck_cards: list[DeckCard], deck_size: int) -> list[SynergyPattern]:
    """Detect keyword synergies based on keyword abilities.

    Args:
        deck_cards: List of DeckCard instances
        deck_size: Total number of cards in deck

    Returns:
        List of detected keyword SynergyPattern instances
    """
    # Map keyword -> list of card names with that keyword
    keyword_cards_map: dict[str, list[str]] = {}
    # Map keyword -> list of payoff card names
    keyword_payoff_map: dict[str, list[str]] = {}

    for deck_card in deck_cards:
        card = deck_card.card
        card_name = card.name

        # Extract keywords from oracle text
        if card.oracle_text:
            oracle_lower = card.oracle_text.lower()

            # Find keywords in oracle text
            for keyword in COMMON_KEYWORDS:
                # Look for keyword at start of line or after comma
                keyword_pattern = rf"(?:^|,\s*){keyword}(?:\s|,|$)"
                if re.search(keyword_pattern, oracle_lower):
                    if keyword not in keyword_cards_map:
                        keyword_cards_map[keyword] = []
                    keyword_cards_map[keyword].extend([card_name] * deck_card.quantity)

            # Check for keyword-matters payoffs
            for keyword in COMMON_KEYWORDS:
                # Patterns like "with flying", "creatures with [keyword]", "[keyword] you control"
                payoff_patterns = [
                    rf"\bwith {keyword}\b",
                    rf"\bcreatures? with {keyword}\b",
                    rf"\b{keyword} you control\b",
                ]
                if any(re.search(pattern, oracle_lower) for pattern in payoff_patterns):
                    if keyword not in keyword_payoff_map:
                        keyword_payoff_map[keyword] = []
                    if card_name not in keyword_cards_map.get(keyword, []):  # Don't double-count
                        keyword_payoff_map[keyword].extend([card_name] * deck_card.quantity)

    # Build synergy patterns
    synergies: list[SynergyPattern] = []

    for keyword, keyword_card_names in keyword_cards_map.items():
        # Need at least 4 cards with the keyword
        if len(keyword_card_names) < 4:
            continue

        payoff_cards = keyword_payoff_map.get(keyword, [])
        # Need at least 1 payoff card for a meaningful synergy
        if len(payoff_cards) < 1:
            continue

        total_cards = len(keyword_card_names) + len(payoff_cards)

        # Skip if too weak (< 10% of deck)
        if total_cards < deck_size * 0.1:
            continue

        # Calculate strength
        percentage = total_cards / deck_size
        strength: Literal["weak", "moderate", "strong"]
        if percentage > 0.3:
            strength = "strong"
        elif percentage > 0.1:
            strength = "moderate"
        else:
            strength = "weak"

        # Create explanation
        affected_card_names = list(set(keyword_card_names + payoff_cards))
        keyword_count = len(keyword_card_names)
        payoff_count = len(payoff_cards)

        explanation = (
            f"{keyword_count} creatures with {keyword} benefit from "
            f"{payoff_count} {keyword}-matters cards"
        )

        synergies.append(
            SynergyPattern(
                pattern_type="keyword",
                subtype=keyword,
                affected_cards=affected_card_names,
                explanation=explanation,
                strength=strength,
            )
        )

    return synergies


def _detect_mechanic_combos(deck_cards: list[DeckCard], deck_size: int) -> list[SynergyPattern]:
    """Detect mechanic combo synergies (sacrifice, graveyard, card draw).

    Args:
        deck_cards: List of DeckCard instances
        deck_size: Total number of cards in deck

    Returns:
        List of detected mechanic combo SynergyPattern instances
    """
    synergies: list[SynergyPattern] = []

    # Detect sacrifice combos
    sacrifice_synergy = _detect_sacrifice_combo(deck_cards, deck_size)
    if sacrifice_synergy:
        synergies.append(sacrifice_synergy)

    # Detect graveyard synergies
    graveyard_synergy = _detect_graveyard_combo(deck_cards, deck_size)
    if graveyard_synergy:
        synergies.append(graveyard_synergy)

    # Detect card draw/discard synergies
    card_draw_synergy = _detect_card_draw_combo(deck_cards, deck_size)
    if card_draw_synergy:
        synergies.append(card_draw_synergy)

    return synergies


def _detect_sacrifice_combo(deck_cards: list[DeckCard], deck_size: int) -> SynergyPattern | None:
    """Detect sacrifice outlet + death trigger combos."""
    sacrifice_outlets: list[str] = []
    death_triggers: list[str] = []

    for deck_card in deck_cards:
        card = deck_card.card
        if not card.oracle_text:
            continue

        oracle_lower = card.oracle_text.lower()

        # Check for sacrifice outlets
        if re.search(r"sacrifice\s+(?:a|an|another)\s+creature", oracle_lower):
            sacrifice_outlets.extend([card.name] * deck_card.quantity)

        # Check for death triggers
        death_patterns = [
            r"when.*dies",
            r"when.*is put into.*graveyard",
            r"whenever.*dies",
            r"whenever.*is put into.*graveyard",
        ]
        if any(re.search(pattern, oracle_lower) for pattern in death_patterns):
            death_triggers.extend([card.name] * deck_card.quantity)

    # Need minimum 4 cards total (e.g., 2 outlets + 2 triggers OR 1 outlet + 3 triggers)
    total_cards = len(sacrifice_outlets) + len(death_triggers)
    if total_cards < 4:
        return None

    # Skip if too weak (< 10% of deck)
    if total_cards < deck_size * 0.1:
        return None

    # Calculate strength
    percentage = total_cards / deck_size
    strength: Literal["weak", "moderate", "strong"]
    if percentage > 0.3:
        strength = "strong"
    elif percentage > 0.1:
        strength = "moderate"
    else:
        strength = "weak"

    affected_cards = list(set(sacrifice_outlets + death_triggers))
    outlet_count = len(sacrifice_outlets)
    trigger_count = len(death_triggers)

    explanation = (
        f"{outlet_count} sacrifice outlets enable {trigger_count} cards "
        f"with death/sacrifice triggers"
    )

    return SynergyPattern(
        pattern_type="mechanic_combo",
        subtype="sacrifice",
        affected_cards=affected_cards,
        explanation=explanation,
        strength=strength,
    )


def _detect_graveyard_combo(deck_cards: list[DeckCard], deck_size: int) -> SynergyPattern | None:
    """Detect self-mill + graveyard payoff combos."""
    mill_cards: list[str] = []
    graveyard_payoffs: list[str] = []

    for deck_card in deck_cards:
        card = deck_card.card
        if not card.oracle_text:
            continue

        oracle_lower = card.oracle_text.lower()

        # Check for self-mill effects
        mill_patterns = [
            r"\bmill\b",  # Simplified - just look for "mill" as a word
            r"put.*cards?.*from.*library into.*graveyard",
            r"from.*library.*into.*graveyard",
        ]
        if any(re.search(pattern, oracle_lower) for pattern in mill_patterns):
            mill_cards.extend([card.name] * deck_card.quantity)

        # Check for graveyard payoffs
        graveyard_patterns = [
            r"delirium",
            r"threshold",
            r"cards? in.*graveyard",
            r"as long as.*graveyard",
        ]
        if any(re.search(pattern, oracle_lower) for pattern in graveyard_patterns):
            graveyard_payoffs.extend([card.name] * deck_card.quantity)

    # Need minimum 4 cards total
    total_cards = len(mill_cards) + len(graveyard_payoffs)
    if total_cards < 4:
        return None

    # Skip if too weak
    if total_cards < deck_size * 0.1:
        return None

    # Calculate strength
    percentage = total_cards / deck_size
    strength: Literal["weak", "moderate", "strong"]
    if percentage > 0.3:
        strength = "strong"
    elif percentage > 0.1:
        strength = "moderate"
    else:
        strength = "weak"

    affected_cards = list(set(mill_cards + graveyard_payoffs))
    mill_count = len(mill_cards)
    payoff_count = len(graveyard_payoffs)

    explanation = f"{mill_count} self-mill cards enable {payoff_count} graveyard payoffs"

    return SynergyPattern(
        pattern_type="mechanic_combo",
        subtype="graveyard",
        affected_cards=affected_cards,
        explanation=explanation,
        strength=strength,
    )


def _detect_card_draw_combo(deck_cards: list[DeckCard], deck_size: int) -> SynergyPattern | None:
    """Detect card draw + discard payoff combos."""
    draw_engines: list[str] = []
    discard_payoffs: list[str] = []

    for deck_card in deck_cards:
        card = deck_card.card
        if not card.oracle_text:
            continue

        oracle_lower = card.oracle_text.lower()

        # Check for repeated card draw (not one-time effects)
        draw_patterns = [
            r"at the beginning.*draw",
            r"whenever.*draw",
            r"draw.*cards?.*each",
        ]
        if any(re.search(pattern, oracle_lower) for pattern in draw_patterns):
            draw_engines.extend([card.name] * deck_card.quantity)

        # Check for discard payoffs
        discard_patterns = [
            r"when(?:ever)? you discard",
            r"madness",
            r"whenever.*discards?.*card",
        ]
        if any(re.search(pattern, oracle_lower) for pattern in discard_patterns):
            discard_payoffs.extend([card.name] * deck_card.quantity)

    # Need minimum 4 cards total
    total_cards = len(draw_engines) + len(discard_payoffs)
    if total_cards < 4:
        return None

    # Skip if too weak
    if total_cards < deck_size * 0.1:
        return None

    # Calculate strength
    percentage = total_cards / deck_size
    strength: Literal["weak", "moderate", "strong"]
    if percentage > 0.3:
        strength = "strong"
    elif percentage > 0.1:
        strength = "moderate"
    else:
        strength = "weak"

    affected_cards = list(set(draw_engines + discard_payoffs))
    draw_count = len(draw_engines)
    payoff_count = len(discard_payoffs)

    explanation = f"{draw_count} card draw engines enable {payoff_count} discard payoffs"

    return SynergyPattern(
        pattern_type="mechanic_combo",
        subtype="card_draw",
        affected_cards=affected_cards,
        explanation=explanation,
        strength=strength,
    )


def _extract_creature_types(type_line: str) -> list[str]:
    """Extract creature types from a card's type line.

    Args:
        type_line: Card type line (e.g., "Creature — Goblin Scout")

    Returns:
        List of creature types (e.g., ["Goblin", "Scout"])
    """
    # Split on em-dash or regular dash
    parts = re.split(r"[—-]", type_line)
    if len(parts) < 2:
        return []

    # Take everything after the dash (creature types)
    types_part = parts[1].strip()

    # Split on spaces and filter out empty strings
    types = [t.strip() for t in types_part.split() if t.strip()]

    # Filter out generic/class types that don't make good synergy tribes
    # These are too generic and rarely have tribal payoffs
    excluded_types = {
        "Scout",
        "Warrior",
        "Soldier",
        "Wizard",
        "Cleric",
        "Rogue",
        "Shaman",
        "Druid",
        "Knight",
        "Berserker",
        "Archer",
    }

    # Only keep types that aren't in the exclusion list
    # This helps focus on actual tribal synergies (Goblins, Elves, etc.)
    types = [t for t in types if t not in excluded_types]

    return types


def _calculate_deck_cohesion(
    synergies: list[SynergyPattern], deck_cards: list[DeckCard], deck_size: int
) -> Literal["low", "moderate", "high"]:
    """Calculate overall deck cohesion based on detected synergies.

    Args:
        synergies: List of detected synergy patterns
        deck_cards: List of DeckCard instances
        deck_size: Total number of cards in deck

    Returns:
        Cohesion level: "low", "moderate", or "high"
    """
    if not synergies:
        return "low"

    # Calculate coverage by counting unique card names (without considering quantities)
    all_affected_card_names = set()
    for synergy in synergies:
        all_affected_card_names.update(synergy.affected_cards)

    # Calculate unique card names in deck
    unique_deck_card_names = {dc.card.name for dc in deck_cards}
    coverage = (
        len(all_affected_card_names) / len(unique_deck_card_names)
        if len(unique_deck_card_names) > 0
        else 0
    )

    # High cohesion: 3+ synergies OR 2+ synergies covering >40% OR 1 strong synergy >50%
    if len(synergies) >= 3:
        return "high"
    if len(synergies) >= 2 and coverage > 0.4:
        return "high"
    if any(s.strength == "strong" for s in synergies) and coverage > 0.5:
        return "high"

    # Moderate cohesion: 2+ synergies with reasonable coverage OR 1-2 synergies covering 20-40%
    if len(synergies) >= 2 and coverage > 0.2:
        return "moderate"
    if 1 <= len(synergies) <= 2 and 0.2 <= coverage <= 0.4:
        return "moderate"

    # Low cohesion: 0-1 synergies covering <20%
    return "low"
