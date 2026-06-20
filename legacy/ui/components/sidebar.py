"""Deck information sidebar component.

This module provides the sidebar component that displays active deck information
and card list in the Chainlit interface.
"""

import logging
import time

import chainlit as cl
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from legacy.agent.core import _session_manager
from src.data.repositories.deck import DeckRepository
from legacy.ui.formatters import get_display_name, wrap_card_name_with_hover

logger = logging.getLogger(__name__)


async def update_deck_sidebar(
    session_id: str, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Update the deck information sidebar with active deck details and card list.

    Displays active deck information (name, ID, format, colors, card count) and
    a complete card list grouped by type in the Chainlit sidebar. Closes sidebar
    when no active deck is loaded.

    This function is called:
    - On session start to initialize sidebar state
    - After deck operations (create, load, add card, delete) via deps.sidebar_needs_update flag

    Args:
        session_id: Current session ID for retrieving active deck
        session_factory: SQLAlchemy async session factory for database access

    Sidebar Content:
        - Deck Info: Name, ID (truncated), format, color identity, total cards
        - Card List: Grouped by type (Creatures, Spells, Lands), sorted by CMC
        - Format: "4x Lightning Bolt" style quantity display

    Notes:
        - Uses simple text-based formatting with markdown (MVP approach)
        - Two cl.Text elements with unique timestamped names to prevent caching
        - Clear-then-set pattern for forced refresh (Chainlit caching workaround)
        - Clears sidebar (empty elements array) when no active deck
        - Extracts deck color identity from all mainboard cards
        - Sidebar persists across messages in the same session
    """
    try:
        # Get active deck ID from session manager
        active_deck_id = _session_manager.get_active_deck_id(session_id)

        # Close sidebar if no active deck
        if active_deck_id is None:
            await cl.ElementSidebar.set_elements([])
            await cl.ElementSidebar.set_title("")
            return

        # Retrieve deck with cards
        if session_factory is None:
            logger.warning("Session factory not initialized, cannot update sidebar")
            return

        async with session_factory() as session:
            deck_repository = DeckRepository(session)
            deck = await deck_repository.get_deck_with_cards(active_deck_id)

        # Handle deck not found (should not happen, but defensive)
        if deck is None:
            logger.warning(f"Active deck {active_deck_id} not found, clearing sidebar")
            await cl.ElementSidebar.set_elements([])
            await cl.ElementSidebar.set_title("")
            return

        # Calculate card counts
        mainboard_count = sum(dc.quantity for dc in deck.deck_cards if not dc.sideboard)

        # Extract color identity from all cards in deck
        colors_set = set()
        for deck_card in deck.deck_cards:
            if not deck_card.sideboard:  # Only mainboard cards contribute to color identity
                colors_set.update(deck_card.card.color_identity)

        # Sort colors in WUBRG order (standard MTG color ordering)
        color_order = {"W": 0, "U": 1, "B": 2, "R": 3, "G": 4}
        sorted_colors = sorted(colors_set, key=lambda c: color_order.get(c, 999))
        color_display = "".join(sorted_colors) if sorted_colors else "Colorless"

        # Get active filters from session
        format_filter = _session_manager.get_format_filter(session_id)
        games_filter = _session_manager.get_games_filter(session_id)

        # Format deck information as markdown
        deck_info_parts = []

        # Show active filters at top if any are set
        if format_filter or games_filter:
            deck_info_parts.append("**Active Filters:**")
            if format_filter:
                deck_info_parts.append(f"  • Format: {format_filter.title()}")
            if games_filter:
                games_display = ", ".join(g.capitalize() for g in games_filter)
                deck_info_parts.append(f"  • Games: {games_display}")
            deck_info_parts.append("")  # Blank line separator

        deck_info_parts.extend(
            [
                f"**{deck.name}**",
                "",
                f"**ID:** `{deck.id[:8]}...`",
                f"**Format:** {deck.format.title() if deck.format else 'None'}",
            ]
        )

        # Add strategy if set (with truncation)
        if deck.strategy:
            strategy_display = deck.strategy
            if len(strategy_display) > 200:
                strategy_display = strategy_display[:197] + "..."
            deck_info_parts.append(f"**Strategy:** {strategy_display}")

        deck_info_parts.extend(
            [
                f"**Colors:** {color_display}",
                f"**Cards:** {mainboard_count}",
            ]
        )

        deck_info = "\n".join(deck_info_parts)

        # Format card list grouped by type
        mainboard_cards = [dc for dc in deck.deck_cards if not dc.sideboard]

        if mainboard_cards:
            # Group cards by type category
            creatures = []
            spells = []
            lands = []

            for deck_card in mainboard_cards:
                card = deck_card.card
                type_line = card.type_line.lower()
                # Use printed_name if available (e.g., OM1 cards)
                display_name = get_display_name(card)

                if "creature" in type_line:
                    creatures.append((deck_card.quantity, display_name, card.cmc, card))
                elif "land" in type_line:
                    lands.append((deck_card.quantity, display_name, card.cmc, card))
                else:
                    spells.append((deck_card.quantity, display_name, card.cmc, card))

            # Sort each group by CMC, then name
            creatures.sort(key=lambda x: (x[2], x[1]))
            spells.sort(key=lambda x: (x[2], x[1]))
            lands.sort(key=lambda x: (x[2], x[1]))

            # Build card list markdown
            card_list_parts = []

            if creatures:
                card_list_parts.append(f"**Creatures ({sum(q for q, _, _, _ in creatures)})**")
                for qty, name, _, card in creatures:
                    wrapped_name = wrap_card_name_with_hover(name, card)
                    card_list_parts.append(f"{qty}x {wrapped_name}")

            if spells:
                card_list_parts.append(f"\n**Spells ({sum(q for q, _, _, _ in spells)})**")
                for qty, name, _, card in spells:
                    wrapped_name = wrap_card_name_with_hover(name, card)
                    card_list_parts.append(f"{qty}x {wrapped_name}")

            if lands:
                card_list_parts.append(f"\n**Lands ({sum(q for q, _, _, _ in lands)})**")
                for qty, name, _, card in lands:
                    wrapped_name = wrap_card_name_with_hover(name, card)
                    card_list_parts.append(f"{qty}x {wrapped_name}")

            card_list = "\n".join(card_list_parts)
        else:
            card_list = "*No cards in deck*"

        # Create elements for sidebar
        # Use unique names with timestamp to avoid Chainlit element caching by name
        timestamp = int(time.time() * 1000)

        deck_info_element = cl.Text(name=f"deck_info_{timestamp}", content=deck_info)

        card_list_element = cl.Text(name=f"card_list_{timestamp}", content=card_list)

        # Force sidebar refresh by clearing first, then setting new content
        # This works around Chainlit caching issues with ElementSidebar updates
        await cl.ElementSidebar.set_elements([])
        await cl.ElementSidebar.set_title("Active Deck")
        await cl.ElementSidebar.set_elements([deck_info_element, card_list_element])

        logger.debug(f"Updated sidebar for deck: {deck.name}")

    except Exception as e:
        logger.exception(f"Failed to update deck sidebar: {e}")
        # Don't fail the request if sidebar update fails - just log the error
