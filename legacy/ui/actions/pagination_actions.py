"""Pagination action callbacks for search result navigation.

This module contains Chainlit action callbacks for:
- Page navigation (Previous/Next buttons)
"""

import logging

import chainlit as cl

from legacy.agent.core import _session_manager
from legacy.ui.action_callbacks import (
    action_error_handler,
    remove_all_actions,
    store_action_message,
    validate_session_id,
)

logger = logging.getLogger(__name__)


@cl.action_callback("navigate_page")
@action_error_handler
async def on_navigate_page(action: cl.Action) -> None:
    """Handle page navigation action for search results.

    Retrieves stored search context and performs search for requested page.

    Args:
        action: The action with payload containing page number
    """
    # Need to import here to avoid circular dependency
    from legacy.ui.app import get_agent_dependencies

    # Validate session ID
    session_id = validate_session_id()

    # Get page number from payload
    page = action.payload.get("page")
    if not page:
        await cl.Message(content="❌ Error: Page number missing. Please try again.").send()
        return

    # Get stored search context
    search_context = _session_manager.get_search_context(session_id)
    if not search_context:
        await cl.Message(
            content="❌ Error: Search context not found. Please perform a new search."
        ).send()
        return

    # Remove previous pagination buttons
    await remove_all_actions("pagination_message")

    # Get agent dependencies and perform search
    async with get_agent_dependencies(session_id) as deps:
        # Import here to avoid circular dependency
        from legacy.ui.formatters import (
            create_pagination_actions,
            format_card_list,
            format_pagination_info,
        )

        # Perform search with new page number
        result = await deps.card_repository.search_advanced(
            colors=search_context.get("colors"),
            types=search_context.get("types"),
            keywords=search_context.get("keywords"),
            oracle_text_phrases=search_context.get("oracle_text"),
            mana_value_min=search_context.get("mana_value_min"),
            mana_value_max=search_context.get("mana_value_max"),
            rarity=search_context.get("rarity"),
            page=page,
            page_size=search_context.get("page_size", 20),
            color_mode=search_context.get("color_mode", "any"),
            format_filter=search_context.get("format_filter"),
            games=search_context.get("games"),
        )

        # Format pagination info
        pagination_info = format_pagination_info(
            result.page, result.total_pages, result.total_count
        )

        # Format card list
        card_list_text = format_card_list(result.items)

        # Create pagination actions
        pagination_actions = create_pagination_actions(result.page, result.total_pages)

        # Combine content
        content = f"{pagination_info}\n\n{card_list_text}"

        # Create and send message with pagination buttons
        pagination_message = cl.Message(content=content, actions=pagination_actions or [])
        await pagination_message.send()

        # Store new pagination message for later removal
        store_action_message("pagination_message", pagination_message)

        logger.info(f"Navigated to page {page} of search results for session {session_id}")
