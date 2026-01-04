"""Unit tests for ConversationSessionManager and conversation history features."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    UserPromptPart,
)

from src.agent.core import ConversationSessionManager, keep_recent_messages, run_agent_with_session
from src.agent.dependencies import AgentDependencies


class TestConversationSessionManager:
    """Tests for ConversationSessionManager class."""

    def test_session_manager_initialization(self):
        """Test that session manager initializes with empty storage."""
        manager = ConversationSessionManager()
        assert manager._sessions == {}

    def test_get_history_new_session_returns_empty_list(self):
        """Test that get_history returns empty list for new session."""
        manager = ConversationSessionManager()
        history = manager.get_history("session-123")
        assert history == []
        assert isinstance(history, list)

    def test_update_and_retrieve_history(self):
        """Test updating and retrieving conversation history."""
        manager = ConversationSessionManager()
        session_id = "session-123"

        # Create sample messages
        messages = [
            ModelRequest(parts=[UserPromptPart(content="Hello")]),
            ModelResponse(parts=[], timestamp=MagicMock()),
        ]

        # Update history
        manager.update_history(session_id, messages)

        # Retrieve and verify
        retrieved = manager.get_history(session_id)
        assert len(retrieved) == 2
        assert retrieved == messages

    def test_clear_session(self):
        """Test clearing session history."""
        manager = ConversationSessionManager()
        session_id = "session-123"

        # Add some messages
        messages = [ModelRequest(parts=[UserPromptPart(content="Hello")])]
        manager.update_history(session_id, messages)

        # Clear session
        manager.clear_session(session_id)

        # Verify session is cleared
        history = manager.get_history(session_id)
        assert history == []

    def test_clear_nonexistent_session_no_error(self):
        """Test that clearing non-existent session doesn't raise error."""
        manager = ConversationSessionManager()
        # Should not raise exception
        manager.clear_session("nonexistent-session")

    def test_session_isolation(self):
        """Test that multiple sessions are stored independently."""
        manager = ConversationSessionManager()

        # Create messages for different sessions
        session_a_messages = [ModelRequest(parts=[UserPromptPart(content="Session A")])]
        session_b_messages = [ModelRequest(parts=[UserPromptPart(content="Session B")])]

        # Update different sessions
        manager.update_history("session-a", session_a_messages)
        manager.update_history("session-b", session_b_messages)

        # Verify isolation
        history_a = manager.get_history("session-a")
        history_b = manager.get_history("session-b")

        assert len(history_a) == 1
        assert len(history_b) == 1
        assert history_a != history_b
        assert history_a[0].parts[0].content == "Session A"  # type: ignore[attr-defined]
        assert history_b[0].parts[0].content == "Session B"  # type: ignore[attr-defined]

    def test_update_replaces_entire_history(self):
        """Test that update_history replaces entire message list."""
        manager = ConversationSessionManager()
        session_id = "session-123"

        # Initial messages
        messages_v1 = [ModelRequest(parts=[UserPromptPart(content="Version 1")])]
        manager.update_history(session_id, messages_v1)

        # Replace with new messages
        messages_v2 = [
            ModelRequest(parts=[UserPromptPart(content="Version 2a")]),
            ModelRequest(parts=[UserPromptPart(content="Version 2b")]),
        ]
        manager.update_history(session_id, messages_v2)

        # Verify complete replacement
        history = manager.get_history(session_id)
        assert len(history) == 2
        assert history == messages_v2

    def test_format_filter_storage_and_retrieval(self):
        """Test storing and retrieving format filter preferences."""
        manager = ConversationSessionManager()
        session_id = "session-123"

        # Set format filter
        manager.set_format_filter(session_id, "standard")

        # Retrieve and verify
        filter_value = manager.get_format_filter(session_id)
        assert filter_value == "standard"

    def test_format_filter_default_none(self):
        """Test that get_format_filter returns None for new sessions."""
        manager = ConversationSessionManager()
        session_id = "new-session"

        # Get filter for new session (should be None)
        filter_value = manager.get_format_filter(session_id)
        assert filter_value is None

    def test_format_filter_isolation(self):
        """Test that format filters are isolated between sessions."""
        manager = ConversationSessionManager()

        # Set different filters for different sessions
        manager.set_format_filter("session-a", "standard")
        # session-b has no filter set

        # Verify isolation
        filter_a = manager.get_format_filter("session-a")
        filter_b = manager.get_format_filter("session-b")

        assert filter_a == "standard"
        assert filter_b is None

    def test_clear_session_removes_format_filter(self):
        """Test that clear_session removes both history and format filter."""
        manager = ConversationSessionManager()
        session_id = "session-123"

        # Add history and format filter
        messages = [ModelRequest(parts=[UserPromptPart(content="Hello")])]
        manager.update_history(session_id, messages)
        manager.set_format_filter(session_id, "standard")

        # Verify both are set
        assert manager.get_history(session_id) != []
        assert manager.get_format_filter(session_id) == "standard"

        # Clear session
        manager.clear_session(session_id)

        # Verify both are cleared
        assert manager.get_history(session_id) == []
        assert manager.get_format_filter(session_id) is None

    def test_set_format_filter_none_removes_filter(self):
        """Test that setting format filter to None removes it."""
        manager = ConversationSessionManager()
        session_id = "session-123"

        # Set filter
        manager.set_format_filter(session_id, "standard")
        assert manager.get_format_filter(session_id) == "standard"

        # Clear filter by setting to None
        manager.set_format_filter(session_id, None)
        assert manager.get_format_filter(session_id) is None

    def test_clear_format_filter(self):
        """Test clear_format_filter method removes filter without affecting history."""
        manager = ConversationSessionManager()
        session_id = "session-123"

        # Add history and format filter
        messages = [ModelRequest(parts=[UserPromptPart(content="Hello")])]
        manager.update_history(session_id, messages)
        manager.set_format_filter(session_id, "standard")

        # Clear format filter only
        manager.clear_format_filter(session_id)

        # Verify filter is cleared but history remains
        assert manager.get_format_filter(session_id) is None
        assert manager.get_history(session_id) == messages

    def test_clear_format_filter_nonexistent_session_no_error(self):
        """Test that clearing format filter for non-existent session doesn't raise error."""
        manager = ConversationSessionManager()
        # Should not raise exception
        manager.clear_format_filter("nonexistent-session")


class TestKeepRecentMessages:
    """Tests for keep_recent_messages history processor."""

    def test_returns_all_messages_when_under_limit(self):
        """Test that all messages are returned when count is under limit."""
        messages = [ModelRequest(parts=[UserPromptPart(content=f"Message {i}")]) for i in range(5)]

        result = keep_recent_messages(messages)

        assert len(result) == 5
        assert result == messages

    def test_truncates_to_last_10_messages(self):
        """Test that messages are truncated to last 10 when over limit."""
        # Create 15 messages
        messages = [ModelRequest(parts=[UserPromptPart(content=f"Message {i}")]) for i in range(15)]

        result = keep_recent_messages(messages)

        # Should keep last 10
        assert len(result) == 10
        # Check that we got the last 10 messages (5-14)
        assert result[0].parts[0].content == "Message 5"  # type: ignore[attr-defined]
        assert result[-1].parts[0].content == "Message 14"  # type: ignore[attr-defined]

    def test_preserves_system_messages(self):
        """Test that system messages are preserved when truncating."""
        # Create a mix of system and user messages
        messages = [
            ModelRequest(parts=[SystemPromptPart(content="System")]),
            *[ModelRequest(parts=[UserPromptPart(content=f"User {i}")]) for i in range(15)],
        ]

        result = keep_recent_messages(messages)

        # Should have system message + last 10 user messages = 11 total
        assert len(result) == 11
        # System message should be first
        assert result[0].parts[0].content == "System"  # type: ignore[attr-defined]
        # Followed by recent user messages
        assert result[1].parts[0].content == "User 5"  # type: ignore[attr-defined]

    def test_handles_empty_message_list(self):
        """Test that empty message list is handled gracefully."""
        result = keep_recent_messages([])
        assert result == []


class TestRunAgentWithSession:
    """Tests for run_agent_with_session helper function."""

    @pytest.mark.asyncio
    async def test_run_agent_with_session_retrieves_history(self):
        """Test that run_agent_with_session retrieves history from session manager."""
        # Create mocks
        mock_agent = MagicMock()
        mock_result = MagicMock()
        mock_result.output = "Agent response"
        mock_result.all_messages.return_value = [
            ModelRequest(parts=[UserPromptPart(content="Test")]),
        ]
        mock_agent.run = AsyncMock(return_value=mock_result)

        mock_deps = MagicMock(spec=AgentDependencies)
        session_id = "test-session"

        # Run function
        response = await run_agent_with_session(
            user_input="Hello", session_id=session_id, deps=mock_deps, agent=mock_agent
        )

        # Verify agent.run was called with empty history (new session)
        mock_agent.run.assert_called_once()
        call_kwargs = mock_agent.run.call_args.kwargs
        assert call_kwargs["message_history"] == []
        assert response.output == "Agent response"

    @pytest.mark.asyncio
    async def test_run_agent_with_session_updates_history(self):
        """Test that run_agent_with_session updates session manager after run."""
        # Create mocks
        mock_agent = MagicMock()
        mock_messages = [
            ModelRequest(parts=[UserPromptPart(content="User message")]),
            ModelResponse(parts=[], timestamp=MagicMock()),
        ]
        mock_result = MagicMock()
        mock_result.output = "Agent response"
        mock_result.all_messages.return_value = mock_messages
        mock_agent.run = AsyncMock(return_value=mock_result)

        mock_deps = MagicMock(spec=AgentDependencies)
        session_id = "test-session"

        # Import and patch the global session manager
        from src.agent import core

        original_manager = core._session_manager
        test_manager = ConversationSessionManager()
        core._session_manager = test_manager

        try:
            # Run function
            await run_agent_with_session(
                user_input="Hello", session_id=session_id, deps=mock_deps, agent=mock_agent
            )

            # Verify history was updated
            history = test_manager.get_history(session_id)
            assert len(history) == 2
            assert history == mock_messages

        finally:
            # Restore original manager
            core._session_manager = original_manager

    @pytest.mark.asyncio
    async def test_run_agent_with_session_passes_existing_history(self):
        """Test that existing history is passed to subsequent agent calls."""
        # Create mocks
        mock_agent = MagicMock()
        existing_messages = [
            ModelRequest(parts=[UserPromptPart(content="Previous message")]),
        ]
        new_messages = existing_messages + [
            ModelRequest(parts=[UserPromptPart(content="New message")]),
        ]
        mock_result = MagicMock()
        mock_result.output = "Agent response"
        mock_result.all_messages.return_value = new_messages
        mock_agent.run = AsyncMock(return_value=mock_result)

        mock_deps = MagicMock(spec=AgentDependencies)
        session_id = "test-session"

        # Import and patch the global session manager
        from src.agent import core

        original_manager = core._session_manager
        test_manager = ConversationSessionManager()
        test_manager.update_history(session_id, existing_messages)
        core._session_manager = test_manager

        try:
            # Run function
            await run_agent_with_session(
                user_input="Hello", session_id=session_id, deps=mock_deps, agent=mock_agent
            )

            # Verify agent.run was called with existing history
            call_kwargs = mock_agent.run.call_args.kwargs
            assert call_kwargs["message_history"] == existing_messages

        finally:
            # Restore original manager
            core._session_manager = original_manager
