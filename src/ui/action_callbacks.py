"""Action callback utilities for Chainlit interactive actions.

This module provides error handling decorators, session message tracking,
action removal utilities, and payload validation helpers for Chainlit action callbacks.
"""

import functools
import logging
from collections.abc import Callable
from typing import Any

import chainlit as cl

logger = logging.getLogger(__name__)


def action_error_handler[F: Callable[..., Any]](func: F) -> F:
    """Decorator that wraps action callbacks with error handling and logging.

    Logs action invocations at INFO level with action name and session ID.
    Logs action errors at ERROR level with full exception context.
    Sends user-friendly error messages to chat on exceptions.
    Preserves async context.

    Args:
        func: The async action callback function to wrap

    Returns:
        Wrapped function with error handling
    """

    @functools.wraps(func)
    async def wrapper(action: cl.Action) -> Any:
        # Get session ID for logging
        session_id = cl.user_session.get("session_id", "unknown")
        action_name = action.name

        # Log action invocation
        logger.info(
            f"Action invoked: {action_name} | Session: {session_id} | Payload: {action.payload}"
        )

        try:
            # Execute the wrapped callback
            return await func(action)
        except Exception as e:
            # Log error with full context
            logger.error(
                f"Action error: {action_name} | Session: {session_id} | Error: {str(e)}",
                exc_info=True,
            )

            # Send user-friendly error message
            await cl.Message(
                content=f"⚠️ An error occurred while processing your action: {str(e)}\n\n"
                f"Please try again or contact support if the issue persists.",
                author="System",
            ).send()

            # Re-raise to allow caller to handle if needed
            raise

    return wrapper  # type: ignore


# Session message tracking utilities


def store_action_message(key: str, message: cl.Message) -> None:
    """Store a message reference in the user session for later retrieval.

    Args:
        key: Unique key for message storage (e.g., "format_selection_message")
        message: The Chainlit message to store
    """
    cl.user_session.set(key, message)
    logger.debug(f"Stored message with key: {key}")


def get_action_message(key: str) -> cl.Message | None:
    """Retrieve a message reference from the user session.

    Args:
        key: The key used to store the message

    Returns:
        The stored message, or None if key not found
    """
    message: cl.Message | None = cl.user_session.get(key)
    if message is None:
        logger.debug(f"Message not found for key: {key}")
    return message


# Action removal utilities


async def remove_single_action(action: cl.Action) -> None:
    """Remove a single action from the UI.

    Args:
        action: The action to remove
    """
    try:
        await action.remove()
        logger.debug(f"Removed single action: {action.name}")
    except Exception as e:
        logger.warning(f"Failed to remove action {action.name}: {str(e)}")


async def remove_all_actions(message_key: str) -> None:
    """Remove all actions from a stored message.

    Args:
        message_key: The session key for the message containing actions
    """
    message = get_action_message(message_key)

    if message is None:
        logger.warning(f"Cannot remove actions: message not found for key '{message_key}'")
        return

    try:
        await message.remove_actions()
        logger.debug(f"Removed all actions from message with key: {message_key}")
    except Exception as e:
        logger.warning(f"Failed to remove actions from message '{message_key}': {str(e)}")


# Payload validation helpers


def validate_session_id() -> str:
    """Validate and retrieve session ID from user session.

    Chainlit stores the session ID under the "id" key in user_session.

    Returns:
        The session ID string

    Raises:
        ValueError: If session ID is not found in user session
    """
    session_id: str | None = cl.user_session.get("id")

    if session_id is None:
        raise ValueError("Session ID not found. Please refresh your session and try again.")

    return session_id


def validate_required_field(payload: dict[str, Any], field: str) -> Any:
    """Validate that a required field exists in the action payload.

    Args:
        payload: The action payload dictionary
        field: The required field name

    Returns:
        The field value

    Raises:
        ValueError: If the required field is missing
    """
    if field not in payload:
        raise ValueError(f"Missing required field '{field}'. Please try your action again.")

    return payload[field]
