"""Filter action callbacks for format and games platform selection.

This module contains Chainlit action callbacks for:
- Format filter selection (Standard, All Formats)
- Games platform filter selection (Arena, Paper, MTGO, All Platforms)
"""

import logging

import chainlit as cl

from legacy.agent.core import _session_manager
from legacy.ui.action_callbacks import action_error_handler, remove_all_actions, validate_session_id

logger = logging.getLogger(__name__)


@cl.action_callback("set_format_filter")
@action_error_handler
async def on_set_format_filter(action: cl.Action) -> None:
    """Handle format filter selection action.

    Updates the session format filter and provides user feedback.

    Args:
        action: The action with payload containing format value
    """
    # Validate session ID
    session_id = validate_session_id()

    # Get format value from action payload
    format_value = action.payload.get("format")

    # Map "all" to None for internal representation
    if format_value == "all":
        format_filter = None
        display_name = "All Formats"
    else:
        format_filter = format_value
        display_name = format_value.title() if format_value else "Unknown"

    # Update session state
    _session_manager.set_format_filter(session_id, format_filter)

    # Remove format selection buttons
    await remove_all_actions("format_selection_message")

    # Send confirmation message
    confirmation = f"✅ Format filter set to **{display_name}**"
    await cl.Message(content=confirmation).send()

    logger.info(f"Format filter set to '{format_filter}' for session {session_id}")


@cl.action_callback("set_games_filter")
@action_error_handler
async def on_set_games_filter(action: cl.Action) -> None:
    """Handle games platform filter selection action.

    Updates the session games filter and provides user feedback.

    Args:
        action: The action with payload containing games platform value
    """
    # Validate session ID
    session_id = validate_session_id()

    # Get games value from action payload
    games_value = action.payload.get("games")

    # Map action value to internal representation
    if games_value == "all":
        games_filter = None
        display_name = "All Platforms"
    else:
        games_filter = [games_value] if games_value else None
        # Map to friendly names
        games_display_names = {
            "arena": "MTG Arena",
            "paper": "Paper",
            "mtgo": "Magic Online",
        }
        display_name = (
            games_display_names.get(games_value, games_value.title()) if games_value else "Unknown"
        )

    # Update session state
    _session_manager.set_games_filter(session_id, games_filter)

    # Remove games selection buttons
    await remove_all_actions("games_selection_message")

    # Send confirmation message
    confirmation = f"✅ Games filter set to **{display_name}**"
    await cl.Message(content=confirmation).send()

    logger.info(f"Games filter set to {games_filter} for session {session_id}")
