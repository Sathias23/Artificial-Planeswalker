"""Deck management action callbacks.

This module contains Chainlit action callbacks for:
- Deck deletion confirmation and cancellation
- Quick deck loading from deck list
"""

import logging

import chainlit as cl

from legacy.agent.core import _session_manager
from legacy.ui.action_callbacks import action_error_handler, remove_all_actions, validate_session_id

logger = logging.getLogger(__name__)


@cl.action_callback("confirm_delete_deck")
@action_error_handler
async def on_confirm_delete_deck(action: cl.Action) -> None:
    """Handle deck deletion confirmation action.

    Deletes the deck from the database and updates the UI.

    Args:
        action: The action with payload containing deck_id and deck_name
    """
    # Import here to avoid circular dependency at module load time
    from legacy.ui.app import get_agent_dependencies, update_deck_sidebar_wrapper

    # Validate session ID
    session_id = validate_session_id()

    # Get deck info from payload
    deck_id = action.payload.get("deck_id")
    deck_name = action.payload.get("deck_name")

    if not deck_id or not deck_name:
        await cl.Message(content="❌ Error: Missing deck information. Please try again.").send()
        return

    # Get agent dependencies to access deck repository
    async with get_agent_dependencies(session_id) as deps:
        # Delete the deck
        success = await deps.deck_repository.delete_deck(deck_id)

        if not success:
            error_message = (
                f"❌ Failed to delete deck '{deck_name}'. The deck may have already been deleted."
            )
            await cl.Message(content=error_message).send()
            return

        # Clear active deck if this was the active deck
        if deps.active_deck and str(deps.active_deck.id) == deck_id:
            _session_manager.clear_active_deck_id(session_id)

        # Remove confirmation buttons
        await remove_all_actions("delete_confirmation_message")

        # Send success message
        success_message = f"✅ Deleted deck **'{deck_name}'** successfully."
        await cl.Message(content=success_message).send()

        # Update sidebar to clear deck (if it was active)
        await update_deck_sidebar_wrapper(session_id)

        logger.info(f"Deck '{deck_name}' (ID: {deck_id}) deleted by user confirmation")


@cl.action_callback("cancel_delete_deck")
@action_error_handler
async def on_cancel_delete_deck(action: cl.Action) -> None:
    """Handle deck deletion cancellation action.

    Removes the confirmation buttons and informs the user.

    Args:
        action: The action (payload not used)
    """
    # Remove confirmation buttons
    await remove_all_actions("delete_confirmation_message")

    # Send cancellation message
    cancellation_message = "Deck deletion cancelled. Your deck is safe."
    await cl.Message(content=cancellation_message).send()

    logger.info("Deck deletion cancelled by user")


@cl.action_callback("quick_load_deck")
@action_error_handler
async def on_quick_load_deck(action: cl.Action) -> None:
    """Handle quick deck loading from deck list.

    Loads the specified deck, sets it as active, syncs format filter to deck format,
    updates sidebar, and removes all quick-load buttons.

    Args:
        action: The action with payload containing deck_id, deck_name, and deck_format
    """
    # Import here to avoid circular dependency at module load time
    from legacy.ui.app import get_agent_dependencies, update_deck_sidebar_wrapper

    # Validate session ID
    session_id = validate_session_id()

    # Extract deck info from payload
    deck_id = action.payload.get("deck_id")
    deck_name = action.payload.get("deck_name")
    deck_format = action.payload.get("deck_format")

    if not deck_id or not deck_name or not deck_format:
        await cl.Message(content="❌ Error: Missing deck information. Please try again.").send()
        await remove_all_actions("deck_list_message")
        return

    # Get agent dependencies to access repositories
    async with get_agent_dependencies(session_id) as deps:
        try:
            # Load deck from repository
            deck = await deps.deck_repository.get_deck_with_cards(deck_id)

            if deck is None:
                error_message = f"❌ Deck **'{deck_name}'** not found. It may have been deleted."
                await cl.Message(content=error_message).send()
                await remove_all_actions("deck_list_message")
                logger.warning(
                    f"Quick-load failed: deck '{deck_name}' (ID: {deck_id}) not found | "
                    f"Session: {session_id}"
                )
                return

            # Set active deck ID in session
            _session_manager.set_active_deck_id(session_id, deck_id)

            # Sync format filter to deck format
            if deck_format in ("all", ""):
                # Clear format filter for "all formats" decks
                _session_manager.set_format_filter(session_id, None)
                format_sync_msg = "(filter cleared for all-formats deck)"
            else:
                # Set filter to match deck format
                _session_manager.set_format_filter(session_id, deck_format)
                format_sync_msg = f"({deck_format} filter synced)"

            # Mark sidebar for update
            deps.sidebar_needs_update = True

            # Remove all quick-load buttons
            await remove_all_actions("deck_list_message")

            # Send confirmation message
            success_message = f"✅ Loaded deck **'{deck_name}'** {format_sync_msg}"
            await cl.Message(content=success_message).send()

            # Update sidebar to show loaded deck
            await update_deck_sidebar_wrapper(session_id)

            logger.info(
                f"Quick-loaded deck '{deck_name}' (ID: {deck_id}, format: {deck_format}) | "
                f"Session: {session_id}"
            )

        except Exception as e:
            # Unexpected error - log and notify user
            logger.error(
                f"Unexpected error quick-loading deck '{deck_name}' (ID: {deck_id}): {str(e)} | "
                f"Session: {session_id}",
                exc_info=True,
            )
            error_message = f"❌ Failed to load **{deck_name}**. Please try again."
            await cl.Message(content=error_message).send()
            await remove_all_actions("deck_list_message")
