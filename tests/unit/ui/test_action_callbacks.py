"""Unit tests for action callback utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

import chainlit as cl
import pytest

from src.ui.action_callbacks import (
    action_error_handler,
    get_action_message,
    remove_all_actions,
    remove_single_action,
    store_action_message,
    validate_required_field,
    validate_session_id,
)


@pytest.fixture
def mock_user_session():
    """Mock cl.user_session for testing."""
    session_storage = {"id": "test-session-123"}

    def mock_get(key, default=None):
        return session_storage.get(key, default)

    def mock_set(key, value):
        session_storage[key] = value

    with patch("chainlit.user_session") as mock_session:
        mock_session.get = mock_get
        mock_session.set = mock_set
        yield session_storage


class TestActionErrorHandler:
    """Tests for action_error_handler decorator."""

    @pytest.mark.asyncio
    async def test_successful_execution(self, mock_user_session):
        """Test that decorator allows successful function execution."""

        @action_error_handler
        async def test_callback(action: cl.Action) -> str:
            return "success"

        mock_action = MagicMock(spec=cl.Action)
        mock_action.name = "test_action"
        mock_action.payload = {"test": "data"}

        result = await test_callback(mock_action)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_user_session):
        """Test that decorator catches exceptions and sends user-friendly messages."""

        @action_error_handler
        async def failing_callback(action: cl.Action) -> str:
            raise ValueError("Test error")

        mock_action = MagicMock(spec=cl.Action)
        mock_action.name = "test_action"
        mock_action.payload = {}

        with patch("chainlit.Message") as mock_message_class:
            mock_message = AsyncMock()
            mock_message_class.return_value = mock_message

            with pytest.raises(ValueError):
                await failing_callback(mock_action)

            # Verify error message was sent
            mock_message_class.assert_called_once()
            call_args = mock_message_class.call_args
            assert "error occurred" in call_args.kwargs["content"].lower()
            mock_message.send.assert_called_once()


class TestSessionMessageTracking:
    """Tests for session message tracking utilities."""

    def test_store_and_retrieve_message(self, mock_user_session):
        """Test storing and retrieving message references."""
        mock_message = MagicMock(spec=cl.Message)
        mock_message.content = "Test message"

        # Store message
        store_action_message("test_key", mock_message)

        # Retrieve message
        retrieved = get_action_message("test_key")
        assert retrieved == mock_message
        assert retrieved.content == "Test message"

    def test_retrieve_missing_key(self, mock_user_session):
        """Test that retrieving missing key returns None gracefully."""
        result = get_action_message("nonexistent_key")
        assert result is None


class TestActionRemoval:
    """Tests for action removal utilities."""

    @pytest.mark.asyncio
    async def test_remove_single_action(self):
        """Test removing a single action."""
        mock_action = MagicMock(spec=cl.Action)
        mock_action.name = "test_action"
        mock_action.remove = AsyncMock()

        await remove_single_action(mock_action)
        mock_action.remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_all_actions_success(self, mock_user_session):
        """Test removing all actions from a stored message."""
        mock_message = MagicMock(spec=cl.Message)
        mock_message.remove_actions = AsyncMock()

        # Store message
        store_action_message("test_message", mock_message)

        # Remove all actions
        await remove_all_actions("test_message")
        mock_message.remove_actions.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_all_actions_missing_message(self, mock_user_session):
        """Test that removing actions from missing message doesn't crash."""
        # Should not raise exception
        await remove_all_actions("nonexistent_message")


class TestPayloadValidation:
    """Tests for payload validation helpers."""

    def test_validate_session_id_success(self, mock_user_session):
        """Test successful session ID validation."""
        session_id = validate_session_id()
        assert session_id == "test-session-123"

    def test_validate_session_id_missing(self):
        """Test that missing session ID raises ValueError."""
        with patch("src.ui.action_callbacks.cl.user_session") as mock_session:
            mock_session.get = MagicMock(return_value=None)
            with pytest.raises(ValueError, match="Session ID not found"):
                validate_session_id()

    def test_validate_required_field_success(self):
        """Test successful required field validation."""
        payload = {"format": "standard", "other": "data"}
        result = validate_required_field(payload, "format")
        assert result == "standard"

    def test_validate_required_field_missing(self):
        """Test that missing required field raises ValueError."""
        payload = {"other": "data"}
        with pytest.raises(ValueError, match="Missing required field"):
            validate_required_field(payload, "format")
