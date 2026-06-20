"""Integration tests for deck deletion action callbacks.

Tests verify that deck deletion via actions works correctly and maintains
backward compatibility with conversational confirmation.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from legacy.agent.core import ConversationSessionManager
from src.data.database import create_engine, create_session_factory, init_database
from legacy.ui.actions.deck_actions import on_cancel_delete_deck, on_confirm_delete_deck

# Load environment variables
load_dotenv()

# Skip tests if OPENROUTER_API_KEY not set
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set - skipping integration tests",
)


@pytest.fixture
async def in_memory_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await init_database(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def populated_database(in_memory_engine):
    """Create a populated database with test decks."""
    session_factory = create_session_factory(in_memory_engine)
    async with session_factory() as session:
        from src.data.repositories.deck import DeckRepository

        deck_repo = DeckRepository(session)

        # Create test deck
        deck = await deck_repo.create_deck(
            name="Test Deck", format="standard", strategy="Aggro test deck"
        )

        await session.commit()

    return in_memory_engine, session_factory, str(deck.id), deck.name


@pytest.fixture
def mock_chainlit_action():
    """Create a mock Chainlit action."""

    def _create_action(name: str, payload: dict[str, str]) -> MagicMock:
        action = MagicMock()
        action.name = name
        action.payload = payload
        return action

    return _create_action


@pytest.fixture
def mock_chainlit_session():
    """Mock Chainlit user session."""
    session_storage = {"id": "test-session-123"}

    def mock_get(key, default=None):
        return session_storage.get(key, default)

    def mock_set(key, value):
        session_storage[key] = value

    # Patch both modules that use cl.user_session
    with patch("chainlit.user_session") as mock_session:
        mock_session.get = mock_get
        mock_session.set = mock_set
        with patch("legacy.ui.action_callbacks.cl.user_session") as mock_session2:
            mock_session2.get = mock_get
            mock_session2.set = mock_set
            yield session_storage


@pytest.fixture
def session_manager():
    """Create a fresh session manager for each test."""
    return ConversationSessionManager()


class TestDeckDeletionConfirmation:
    """Tests for deck deletion confirmation via actions."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_confirm_delete_deck_removes_deck(
        self,
        populated_database,
        mock_chainlit_action,
        mock_chainlit_session,
        session_manager,
    ):
        """Test that confirming deletion removes deck from database."""
        engine, session_factory, deck_id, deck_name = populated_database

        # Create confirm action
        action = mock_chainlit_action(
            "confirm_delete_deck", {"deck_id": deck_id, "deck_name": deck_name}
        )

        # Mock UI dependencies
        with patch("legacy.ui.app._session_factory", session_factory):
            with patch("legacy.ui.actions.deck_actions._session_manager", session_manager):
                with patch("legacy.ui.action_callbacks.remove_all_actions", new_callable=AsyncMock):
                    with patch("legacy.ui.app.cl.Message") as mock_message_class:
                        mock_message = AsyncMock()
                        mock_message_class.return_value = mock_message

                        with patch(
                            "legacy.ui.components.sidebar.update_deck_sidebar", new_callable=AsyncMock
                        ):
                            # Call confirmation callback
                            await on_confirm_delete_deck(action)

        # Verify deck was deleted
        async with session_factory() as session:
            from src.data.repositories.deck import DeckRepository

            deck_repo = DeckRepository(session)
            deck = await deck_repo.get_deck(deck_id)
            assert deck is None  # Deck should be deleted

        # Verify success message sent
        assert mock_message.send.call_count == 1
        call_args = mock_message_class.call_args
        assert deck_name in call_args.kwargs["content"]
        assert "Deleted" in call_args.kwargs["content"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_cancel_delete_deck_preserves_deck(
        self,
        populated_database,
        mock_chainlit_action,
        mock_chainlit_session,
    ):
        """Test that cancelling deletion preserves deck in database."""
        engine, session_factory, deck_id, deck_name = populated_database

        # Create cancel action
        action = mock_chainlit_action("cancel_delete_deck", {})

        # Mock UI dependencies
        with patch("legacy.ui.action_callbacks.remove_all_actions", new_callable=AsyncMock):
            with patch("legacy.ui.app.cl.Message") as mock_message_class:
                mock_message = AsyncMock()
                mock_message_class.return_value = mock_message

                # Call cancellation callback
                await on_cancel_delete_deck(action)

        # Verify deck still exists
        async with session_factory() as session:
            from src.data.repositories.deck import DeckRepository

            deck_repo = DeckRepository(session)
            deck = await deck_repo.get_deck(deck_id)
            assert deck is not None  # Deck should still exist
            assert deck.name == deck_name

        # Verify cancellation message sent
        assert mock_message.send.call_count == 1
        call_args = mock_message_class.call_args
        assert "cancelled" in call_args.kwargs["content"].lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_confirm_delete_clears_active_deck(
        self,
        populated_database,
        mock_chainlit_action,
        mock_chainlit_session,
        session_manager,
    ):
        """Test that deleting active deck clears active deck state."""
        engine, session_factory, deck_id, deck_name = populated_database
        session_id = mock_chainlit_session["id"]

        # Set deck as active
        session_manager.set_active_deck_id(session_id, deck_id)
        assert session_manager.get_active_deck_id(session_id) == deck_id

        # Create confirm action
        action = mock_chainlit_action(
            "confirm_delete_deck", {"deck_id": deck_id, "deck_name": deck_name}
        )

        # Mock UI dependencies
        with patch("legacy.ui.app._session_factory", session_factory):
            with patch("legacy.ui.actions.deck_actions._session_manager", session_manager):
                with patch("legacy.ui.action_callbacks.remove_all_actions", new_callable=AsyncMock):
                    with patch("legacy.ui.app.cl.Message") as mock_message_class:
                        mock_message = AsyncMock()
                        mock_message_class.return_value = mock_message
                        with patch(
                            "legacy.ui.components.sidebar.update_deck_sidebar", new_callable=AsyncMock
                        ):
                            # Call confirmation callback
                            await on_confirm_delete_deck(action)

        # Verify active deck was cleared
        assert session_manager.get_active_deck_id(session_id) is None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_confirm_delete_with_missing_deck_id(
        self,
        mock_chainlit_action,
        mock_chainlit_session,
    ):
        """Test error handling when deck_id is missing from payload."""
        # Create action with missing deck_id
        action = mock_chainlit_action("confirm_delete_deck", {"deck_name": "Test Deck"})

        with patch("legacy.ui.app.cl.Message") as mock_message_class:
            mock_message = AsyncMock()
            mock_message_class.return_value = mock_message

            # Call confirmation callback
            await on_confirm_delete_deck(action)

        # Verify error message sent
        assert mock_message.send.call_count == 1
        call_args = mock_message_class.call_args
        assert "Error" in call_args.kwargs["content"]
        assert "Missing deck information" in call_args.kwargs["content"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_confirm_delete_with_nonexistent_deck(
        self,
        populated_database,
        mock_chainlit_action,
        mock_chainlit_session,
        session_manager,
    ):
        """Test error handling when trying to delete nonexistent deck."""
        engine, session_factory, _, _ = populated_database
        fake_deck_id = str(uuid4())

        # Create action with nonexistent deck
        action = mock_chainlit_action(
            "confirm_delete_deck", {"deck_id": fake_deck_id, "deck_name": "Nonexistent Deck"}
        )

        with patch("legacy.ui.app._session_factory", session_factory):
            with patch("legacy.ui.actions.deck_actions._session_manager", session_manager):
                with patch("legacy.ui.action_callbacks.remove_all_actions", new_callable=AsyncMock):
                    with patch("legacy.ui.app.cl.Message") as mock_message_class:
                        mock_message = AsyncMock()
                        mock_message_class.return_value = mock_message

                        # Call confirmation callback
                        await on_confirm_delete_deck(action)

        # Verify failure message sent
        assert mock_message.send.call_count == 1
        call_args = mock_message_class.call_args
        assert "Failed to delete" in call_args.kwargs["content"]


class TestBackwardCompatibility:
    """Tests for backward compatibility with conversational confirmation."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_delete_deck_tool_returns_confirmation_signal(
        self, populated_database, session_manager
    ):
        """Test that delete_deck tool returns structured confirmation signal."""
        from unittest.mock import MagicMock

        from legacy.agent.dependencies import AgentDependencies
        from legacy.agent.tools.deck_tools import delete_deck

        engine, session_factory, deck_id, deck_name = populated_database

        # Create mock context
        async with session_factory() as session:
            from src.data.repositories.card import CardRepository
            from src.data.repositories.deck import DeckRepository

            card_repo = CardRepository(session)
            deck_repo = DeckRepository(session)

            deps = AgentDependencies(
                card_repository=card_repo,
                deck_repository=deck_repo,
                session_id="test-session",
                _session_manager=session_manager,
            )

            # Create mock run context
            ctx = MagicMock()
            ctx.deps = deps

            # Call delete_deck with confirmed=False
            result = await delete_deck(ctx, name=deck_name, confirmed=False)

            # Verify structured result
            assert isinstance(result, dict)
            assert result.get("needs_confirmation") is True
            assert result.get("deck_id") == deck_id
            assert result.get("deck_name") == deck_name

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_delete_deck_tool_proceeds_with_confirmation(
        self, populated_database, session_manager
    ):
        """Test that delete_deck tool proceeds with deletion when confirmed=True."""
        from unittest.mock import MagicMock

        from legacy.agent.dependencies import AgentDependencies
        from legacy.agent.tools.deck_tools import delete_deck

        engine, session_factory, deck_id, deck_name = populated_database

        # Create mock context
        async with session_factory() as session:
            from src.data.repositories.card import CardRepository
            from src.data.repositories.deck import DeckRepository

            card_repo = CardRepository(session)
            deck_repo = DeckRepository(session)

            # Load the deck first to populate active_deck
            deck = await deck_repo.get_deck(deck_id)

            deps = AgentDependencies(
                card_repository=card_repo,
                deck_repository=deck_repo,
                session_id="test-session",
                _session_manager=session_manager,
                active_deck=deck,
            )

            # Create mock run context
            ctx = MagicMock()
            ctx.deps = deps

            # Call delete_deck with confirmed=True
            result = await delete_deck(ctx, name=deck_name, confirmed=True)

            # Verify success message
            assert isinstance(result, str)
            assert "Deleted" in result
            assert deck_name in result

        # Verify deck was actually deleted
        async with session_factory() as session:
            from src.data.repositories.deck import DeckRepository

            deck_repo = DeckRepository(session)
            deck = await deck_repo.get_deck(deck_id)
            assert deck is None
