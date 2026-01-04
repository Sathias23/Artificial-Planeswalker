"""Shared test fixtures for all test modules."""

import pytest

from src.agent.core import ConversationSessionManager


@pytest.fixture
def mock_session_manager():
    """Create a ConversationSessionManager for testing.

    This fixture provides a fresh session manager instance for each test,
    ensuring clean session state and preventing test contamination.

    Returns:
        ConversationSessionManager instance for testing
    """
    return ConversationSessionManager()
