"""Signal handler functions for agent tool signals.

This module contains handlers that process signals returned by agent tools
and create corresponding Chainlit action UIs (buttons, confirmations, etc.).

Pattern:
    Agent tools return dict signals → Signal handlers create Chainlit actions

Signal Types:
    - Confirmation: Deck deletion confirmation prompts
    - Pagination: Page navigation for search results
    - Synergy: Quick-add buttons for synergy card suggestions (detect_deck_synergies)
    - Suggestion: Quick-add buttons for LLM-curated suggestions (suggest_synergy_cards)
    - Deck List: Quick-load buttons for deck selection
    - Disambiguation: Card selection buttons for ambiguous queries
"""

import logging
from typing import Any

import chainlit as cl

from legacy.ui.action_callbacks import store_action_message
from legacy.ui.formatters import get_display_name

logger = logging.getLogger(__name__)


async def handle_confirmation_signal(signal: dict[str, Any]) -> None:
    """Create deck deletion confirmation action buttons.

    Displays a confirmation prompt with "Confirm Delete" and "Cancel" buttons
    when the delete_deck tool requires user confirmation.

    Args:
        signal: Dict with keys:
            - needs_confirmation (bool): True if confirmation required
            - deck_id (str): UUID of deck to delete
            - deck_name (str): Name of deck to delete

    UI Elements Created:
        - Warning message with deck name
        - "Confirm Delete" action button
        - "Cancel" action button

    Example:
        >>> signal = {
        ...     "needs_confirmation": True,
        ...     "deck_id": "123e4567-e89b-12d3-a456-426614174000",
        ...     "deck_name": "My Deck"
        ... }
        >>> await handle_confirmation_signal(signal)
        # User sees: "⚠️ Are you sure you want to delete 'My Deck'?"
    """
    deck_id = signal.get("deck_id")
    deck_name = signal.get("deck_name")

    confirmation_content = (
        f"⚠️ **Are you sure you want to delete '{deck_name}'?**\n\n"
        f"This action cannot be undone. All cards in this deck will be removed."
    )

    confirmation_actions = [
        cl.Action(
            name="confirm_delete_deck",
            payload={"deck_id": deck_id, "deck_name": deck_name},
            label="🗑️ Confirm Delete",
            tooltip="Permanently delete this deck",
        ),
        cl.Action(
            name="cancel_delete_deck",
            payload={},
            label="❌ Cancel",
            tooltip="Keep the deck",
        ),
    ]

    confirmation_message = cl.Message(content=confirmation_content, actions=confirmation_actions)
    await confirmation_message.send()

    # Store confirmation message for later removal
    store_action_message("delete_confirmation_message", confirmation_message)

    logger.info(f"Displayed deletion confirmation for deck: {deck_name}")


async def handle_pagination_signal(signal: dict[str, Any]) -> None:
    """Create pagination navigation buttons for search results.

    Displays "Previous" and/or "Next" buttons when search results span multiple
    pages. Buttons are shown only when applicable (e.g., no "Previous" on page 1).

    Args:
        signal: Dict with keys:
            - has_pagination (bool): True if pagination required
            - page (int): Current page number (1-indexed)
            - total_pages (int): Total number of pages

    UI Elements Created:
        - "Previous" action button (if page > 1)
        - "Next" action button (if page < total_pages)

    Example:
        >>> signal = {"has_pagination": True, "page": 2, "total_pages": 5}
        >>> await handle_pagination_signal(signal)
        # User sees: [< Previous] [Next >] buttons
    """
    from legacy.ui.formatters import create_pagination_actions

    page = signal.get("page", 1)
    total_pages = signal.get("total_pages", 1)

    # Create pagination actions
    pagination_actions = create_pagination_actions(page, total_pages)

    if pagination_actions:
        # Create a message with just pagination buttons (agent already sent results)
        pagination_message = cl.Message(content="", actions=pagination_actions)
        await pagination_message.send()

        # Store pagination message for later removal
        store_action_message("pagination_message", pagination_message)

        logger.info(f"Displayed pagination buttons for page {page} of {total_pages}")


async def handle_synergy_signal(signal: dict[str, Any]) -> None:
    """Create synergy card quick-add buttons.

    Displays action buttons for each synergy card suggestion, allowing users to
    quickly add cards to their active deck. Limits display to 7 cards maximum.

    Args:
        signal: Dict with keys:
            - has_synergies (bool): True if synergies detected
            - synergy_cards (list[Card]): List of synergy card suggestions

    UI Elements Created:
        - "Add [Card Name]" action buttons (max 7)

    Example:
        >>> signal = {
        ...     "has_synergies": True,
        ...     "synergy_cards": [Card(name="Lightning Bolt", id=...)]
        ... }
        >>> await handle_synergy_signal(signal)
        # User sees: [Add Lightning Bolt] button
    """
    synergy_cards = signal.get("synergy_cards", [])

    if synergy_cards:
        # Create action buttons for each synergy card (limit 7)
        synergy_actions = []
        for card in synergy_cards[:7]:
            # Use printed_name if available for display (e.g., OM1 cards)
            display_name = get_display_name(card)
            synergy_actions.append(
                cl.Action(
                    name="add_suggested_card",
                    payload={"card_name": card.name, "card_id": str(card.id)},
                    label=f"Add {display_name}",
                    tooltip="Add 1 copy to active deck",
                    icon="plus-circle",
                )
            )

        # Create message with synergy action buttons
        synergy_message = cl.Message(content="", actions=synergy_actions)
        await synergy_message.send()

        # Store synergy message for later removal
        store_action_message("synergy_suggestions_message", synergy_message)

        logger.info(f"Displayed synergy quick-add buttons for {len(synergy_actions)} cards")


async def handle_suggestion_signal(signal: dict[str, Any]) -> None:
    """Create quick-add buttons for LLM-curated card suggestions.

    Displays action buttons for each suggested card from the suggest_synergy_cards
    tool, allowing users to quickly add cards to their active deck.

    Args:
        signal: Dict with keys:
            - has_suggestions (bool): True if suggestions available
            - suggested_cards (list[Card]): List of suggested card objects
            - formatted_text (str): Formatted display text (already shown by agent)

    UI Elements Created:
        - "Add [Card Name]" action buttons (max 7)
        - Buttons reuse existing add_suggested_card callback

    Example:
        >>> signal = {
        ...     "has_suggestions": True,
        ...     "suggested_cards": [Card(name="Goblin Guide", id=...)],
        ...     "formatted_text": "## Card Suggestions..."
        ... }
        >>> await handle_suggestion_signal(signal)
        # User sees: [Add Goblin Guide] button
    """
    suggested_cards = signal.get("suggested_cards", [])

    if suggested_cards:
        # Create action buttons for each suggested card (limit 7)
        suggestion_actions = []
        for card in suggested_cards[:7]:
            # Use printed_name if available for display (e.g., OM1 cards)
            display_name = get_display_name(card)
            suggestion_actions.append(
                cl.Action(
                    name="add_suggested_card",  # Reuses existing callback
                    payload={"card_name": card.name, "card_id": str(card.id)},
                    label=f"Add {display_name}",
                    tooltip="Add 1 copy to active deck",
                    icon="plus-circle",
                )
            )

        # Create message with suggestion action buttons
        suggestion_message = cl.Message(content="", actions=suggestion_actions)
        await suggestion_message.send()

        # Store suggestion message for later removal
        store_action_message("suggestion_message", suggestion_message)

        logger.info(f"Displayed suggestion quick-add buttons for {len(suggestion_actions)} cards")


async def handle_deck_list_signal(signal: dict[str, Any]) -> None:
    """Create deck quick-load buttons.

    Displays action buttons for each deck in a deck list, allowing users to
    quickly load decks into their session. Limits display to 5 decks maximum.
    Each button shows deck metadata (format, card count, colors) in tooltip.

    Args:
        signal: Dict with keys:
            - has_decks (bool): True if decks available
            - decks (list[Deck]): List of decks to display

    UI Elements Created:
        - "Load [Deck Name]" action buttons (max 5)
        - Tooltips with deck metadata

    Example:
        >>> signal = {
        ...     "has_decks": True,
        ...     "decks": [Deck(name="My Deck", format="standard", ...)]
        ... }
        >>> await handle_deck_list_signal(signal)
        # User sees: [Load My Deck] button with tooltip "Standard • 60 cards • WUBR"
    """
    decks = signal.get("decks", [])

    if decks:
        # Create action buttons for each deck (limit 5)
        deck_actions = []
        for deck in decks[:5]:
            # Calculate card count
            mainboard_count = sum(dc.quantity for dc in deck.deck_cards if not dc.sideboard)

            # Format color identity
            colors = "".join(deck.color_identity) if deck.color_identity else "Colorless"

            # Create tooltip with deck metadata
            tooltip = f"{deck.format.title()} • {mainboard_count} cards • {colors}"

            deck_actions.append(
                cl.Action(
                    name="quick_load_deck",
                    payload={
                        "deck_id": str(deck.id),
                        "deck_name": deck.name,
                        "deck_format": deck.format,
                    },
                    label=f"Load {deck.name}",
                    tooltip=tooltip,
                    icon="folder-open",
                )
            )

        # Create message with deck action buttons
        deck_message = cl.Message(content="", actions=deck_actions)
        await deck_message.send()

        # Store deck message for later removal
        store_action_message("deck_list_message", deck_message)

        logger.info(f"Displayed quick-load buttons for {len(deck_actions)} decks")


async def handle_disambiguation_signal(signal: dict[str, Any], user_message: str) -> None:
    """Create card selection buttons for disambiguation.

    Displays action buttons for each matching card when a query is ambiguous
    (e.g., "Bolt" matches multiple cards). Detects user intent from message
    to show either "Add" or "View" buttons (2-5 cards maximum).

    Args:
        signal: Dict with keys:
            - needs_disambiguation (bool): True if disambiguation required
            - matches (list[Card]): List of matching cards (2-5 cards)
        user_message: Original user message for context detection

    UI Elements Created:
        - Card selection action buttons (2-5 cards)
        - Button label/icon varies by context (add vs view)

    Context Detection:
        - "add" context: User wants to add card (keywords: "add", "include", "put in")
        - "view" context: User wants to view card details (default)

    Example:
        >>> signal = {
        ...     "needs_disambiguation": True,
        ...     "matches": [Card(name="Lightning Bolt"), Card(name="Bolt Bend")]
        ... }
        >>> await handle_disambiguation_signal(signal, "show me bolt")
        # User sees: [Lightning Bolt (Instant)] [Bolt Bend (Instant)] (view icons)

        >>> await handle_disambiguation_signal(signal, "add bolt to deck")
        # User sees: [Add Lightning Bolt] [Add Bolt Bend] (plus icons)
    """
    from legacy.ui.app import detect_disambiguation_context

    matches = signal.get("matches", [])

    if matches:
        # Detect context from user message
        context = detect_disambiguation_context(user_message)

        # Create action buttons for each matching card (2-5 cards)
        disambiguation_actions = []
        for card in matches:
            # Use printed_name if available for display (e.g., OM1 cards)
            display_name = get_display_name(card)

            # Set label based on context
            if context == "add":
                label = f"Add {display_name}"
                tooltip = "Add 1 copy to active deck"
                icon = "plus-circle"
            else:
                label = f"{display_name}"
                if card.type_line:
                    label += f" ({card.type_line.split('—')[0].strip()})"
                tooltip = "View card details"
                icon = "eye"

            disambiguation_actions.append(
                cl.Action(
                    name="select_card",
                    payload={
                        "card_id": str(card.id),
                        "card_name": card.name,
                        "context": context,
                    },
                    label=label,
                    tooltip=tooltip,
                    icon=icon,
                )
            )

        # Create message with disambiguation action buttons
        disambiguation_message = cl.Message(content="", actions=disambiguation_actions)
        await disambiguation_message.send()

        # Store disambiguation message for later removal
        store_action_message("disambiguation_message", disambiguation_message)

        logger.info(
            f"Displayed disambiguation buttons for {len(disambiguation_actions)} cards "
            f"(context: {context})"
        )
