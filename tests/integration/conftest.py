"""Shared fixtures for integration tests."""

from typing import Any
from unittest.mock import MagicMock

import chainlit as cl
import pytest


@pytest.fixture
def mock_user_session():
    """Provide a mock user session for testing action callbacks.

    Returns a dictionary that mimics cl.user_session behavior for storing
    and retrieving session data.

    Returns:
        dict: Mock session storage
    """
    session_storage = {"session_id": "test-session-123"}

    # Mock cl.user_session.get and set
    def mock_get(key, default=None):
        return session_storage.get(key, default)

    def mock_set(key, value):
        session_storage[key] = value

    # Patch cl.user_session
    cl.user_session.get = mock_get  # type: ignore
    cl.user_session.set = mock_set  # type: ignore

    return session_storage


@pytest.fixture
def mock_action():
    """Create a mock cl.Action instance with test payloads.

    Returns:
        callable: Factory function that creates mock actions with custom names and payloads
    """

    def _create_action(name: str, payload: dict[str, Any] | None = None) -> cl.Action:
        """Factory to create mock actions.

        Args:
            name: Action name (e.g., "set_format_filter")
            payload: Action payload dictionary

        Returns:
            Mock cl.Action instance
        """
        action = MagicMock(spec=cl.Action)
        action.name = name
        action.payload = payload or {}
        action.remove = MagicMock(return_value=None)
        return action

    return _create_action


@pytest.fixture
def action_message():
    """Create a mock cl.Message with actions for testing.

    Returns:
        callable: Factory function that creates mock messages with actions
    """

    def _create_message(content: str, actions: list[cl.Action] | None = None) -> cl.Message:
        """Factory to create mock messages with actions.

        Args:
            content: Message content text
            actions: List of actions to attach to message

        Returns:
            Mock cl.Message instance
        """
        message = MagicMock(spec=cl.Message)
        message.content = content
        message.actions = actions or []
        message.send = MagicMock(return_value=None)
        message.remove_actions = MagicMock(return_value=None)
        return message

    return _create_message
