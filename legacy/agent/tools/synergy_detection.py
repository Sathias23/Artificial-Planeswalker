"""Synergy detection tool for agent."""

import logging
from typing import Any

from pydantic_ai import RunContext

from legacy.agent.dependencies import AgentDependencies
from src.logic.synergy import detect_synergies
from legacy.ui.formatters import format_synergies

logger = logging.getLogger(__name__)


async def detect_deck_synergies(ctx: RunContext[AgentDependencies]) -> str | dict[str, Any]:
    """Detect and analyze card synergies in the currently active deck.

    This tool identifies three types of synergies:
    - Tribal synergies: Shared creature types (e.g., Goblins, Elves)
    - Keyword synergies: Keyword-matters cards (e.g., flying, lifelink)
    - Mechanic combos: Card interactions (e.g., sacrifice outlets + death triggers)

    Returns:
        When synergies detected: dict with keys:
            - has_synergies: bool (True)
            - synergy_cards: list[Card] (top 7 cards participating in synergies)
            - formatted_text: str (formatted synergy analysis report)
        When no synergies: str (error message or "no synergies" message)

    Raises:
        ValueError: If no deck is currently active or deck is empty
    """
    deps = ctx.deps

    # Check for active deck
    if not deps.active_deck:
        return "No active deck to analyze. Use create_deck() or load_deck() first."

    # Use cached active deck (already loaded with cards)
    deck = deps.active_deck

    # Get all mainboard deck_cards (with quantities)
    mainboard_cards = [dc for dc in deck.deck_cards if not dc.sideboard]

    if not mainboard_cards:
        return f"Deck '{deck.name}' is empty. Add cards before analyzing synergies."

    # Perform synergy detection
    try:
        analysis = detect_synergies(mainboard_cards)
    except ValueError as e:
        logger.error(f"Synergy detection failed: {e}")
        return f"Analysis failed: {e}"

    # Format results for display
    formatted_text = format_synergies(analysis, deck.name)

    # If synergies detected, return structured data with top 7 synergy cards
    if analysis.synergies:
        # Collect all unique cards participating in synergies
        synergy_card_names = set()
        for synergy in analysis.synergies:
            synergy_card_names.update(synergy.affected_cards)

        # Get Card objects from deck_cards (limit to 7)
        synergy_cards = []
        for deck_card in mainboard_cards:
            if deck_card.card.name in synergy_card_names:
                synergy_cards.append(deck_card.card)
                if len(synergy_cards) >= 7:
                    break

        return {
            "has_synergies": True,
            "synergy_cards": synergy_cards,
            "formatted_text": formatted_text,
        }

    # No synergies detected - return string (backward compatible)
    return formatted_text
