"""Integration tests for filter action callbacks.

Tests verify that filters set via actions persist across conversational messages
and correctly restrict card query results.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dotenv import load_dotenv

from src.agent.core import ConversationSessionManager
from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.ui.actions.filter_actions import on_set_format_filter, on_set_games_filter

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
    """Create a populated database with Standard and non-Standard cards."""
    session_factory = create_session_factory(in_memory_engine)
    async with session_factory() as session:
        # Create sample cards for testing
        cards = [
            CardModel(
                id="bolt-123",
                name="Lightning Bolt",
                oracle_id="oracle-bolt",
                mana_cost="{R}",
                cmc=1.0,
                type_line="Instant",
                oracle_text="Lightning Bolt deals 3 damage to any target.",
                rarity="common",
                set_code="lea",
                set_name="Limited Edition Alpha",
                collector_number="161",
                colors=["R"],
                color_identity=["R"],
                legalities={"standard": "not_legal", "modern": "legal"},
                games=["paper", "mtgo"],  # Not on Arena
            ),
            CardModel(
                id="shock-456",
                name="Shock",
                oracle_id="oracle-shock",
                mana_cost="{R}",
                cmc=1.0,
                type_line="Instant",
                oracle_text="Shock deals 2 damage to any target.",
                rarity="common",
                set_code="m21",
                set_name="Core Set 2021",
                collector_number="159",
                colors=["R"],
                color_identity=["R"],
                legalities={"standard": "legal", "modern": "legal"},
                games=["paper", "arena", "mtgo"],  # On all platforms
            ),
            CardModel(
                id="opt-789",
                name="Opt",
                oracle_id="oracle-opt",
                mana_cost="{U}",
                cmc=1.0,
                type_line="Instant",
                oracle_text="Scry 1, then draw a card.",
                rarity="common",
                set_code="xln",
                set_name="Ixalan",
                collector_number="65",
                colors=["U"],
                color_identity=["U"],
                legalities={"standard": "legal", "modern": "legal"},
                games=["paper", "arena", "mtgo"],
            ),
        ]

        for card in cards:
            session.add(card)
        await session.commit()

    return in_memory_engine, session_factory


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

    # Patch both the main module and src.ui.action_callbacks module
    with patch("chainlit.user_session") as mock_session:
        mock_session.get = mock_get
        mock_session.set = mock_set
        with patch("src.ui.action_callbacks.cl.user_session") as mock_session2:
            mock_session2.get = mock_get
            mock_session2.set = mock_set
            yield session_storage


@pytest.fixture
def session_manager():
    """Create a fresh session manager for each test."""
    return ConversationSessionManager()


class TestFormatFilterActions:
    """Tests for format filter action callbacks."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_set_format_filter_to_standard(
        self, mock_chainlit_action, mock_chainlit_session, session_manager
    ):
        """Test setting format filter to Standard via action."""
        # Create action
        action = mock_chainlit_action("set_format_filter", {"format": "standard"})

        # Mock remove_all_actions and cl.Message
        with patch("src.ui.action_callbacks.remove_all_actions", new_callable=AsyncMock):
            with patch("src.ui.app.cl.Message") as mock_message_class:
                mock_message = AsyncMock()
                mock_message_class.return_value = mock_message

                # Set session manager globally
                with patch("src.ui.actions.filter_actions._session_manager", session_manager):
                    # Call action callback
                    await on_set_format_filter(action)

        # Verify filter was set
        session_id = mock_chainlit_session["id"]
        assert session_manager.get_format_filter(session_id) == "standard"

        # Verify confirmation message was sent
        mock_message.send.assert_called_once()
        call_args = mock_message_class.call_args
        assert "Standard" in call_args.kwargs["content"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_set_format_filter_to_all(
        self, mock_chainlit_action, mock_chainlit_session, session_manager
    ):
        """Test setting format filter to All Formats via action."""
        # Set initial filter to test override
        session_id = mock_chainlit_session["id"]
        session_manager.set_format_filter(session_id, "standard")

        # Create action
        action = mock_chainlit_action("set_format_filter", {"format": "all"})

        # Mock remove_all_actions and cl.Message
        with patch("src.ui.action_callbacks.remove_all_actions", new_callable=AsyncMock):
            with patch("src.ui.app.cl.Message") as mock_message_class:
                mock_message = AsyncMock()
                mock_message_class.return_value = mock_message

                # Set session manager globally
                with patch("src.ui.actions.filter_actions._session_manager", session_manager):
                    # Call action callback
                    await on_set_format_filter(action)

        # Verify filter was cleared (None = all formats)
        assert session_manager.get_format_filter(session_id) is None

        # Verify confirmation message
        call_args = mock_message_class.call_args
        assert "All Formats" in call_args.kwargs["content"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_format_filter_persists_across_queries(
        self, populated_database, mock_chainlit_session, session_manager
    ):
        """Test that format filter set via action persists for card queries."""
        engine, session_factory = populated_database
        session_id = mock_chainlit_session["id"]

        # Set format filter via session manager (simulating action callback)
        session_manager.set_format_filter(session_id, "standard")

        # Query cards with filter applied
        from src.data.repositories.card import CardRepository

        async with session_factory() as session:
            card_repo = CardRepository(session)
            results = await card_repo.search_advanced(
                colors=["R"],
                format_filter="standard",
            )

        # Verify only Standard-legal cards returned
        card_names = [card.name for card in results.items]
        assert "Shock" in card_names  # Standard-legal
        assert "Lightning Bolt" not in card_names  # Not Standard-legal

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_conversational_filter_overrides_action_filter(
        self, populated_database, mock_chainlit_session, session_manager
    ):
        """Test that conversational filter commands can override action-set filters."""
        engine, session_factory = populated_database
        session_id = mock_chainlit_session["id"]

        # Set Standard filter via action
        session_manager.set_format_filter(session_id, "standard")
        assert session_manager.get_format_filter(session_id) == "standard"

        # Override with conversational command (set to None)
        session_manager.set_format_filter(session_id, None)
        assert session_manager.get_format_filter(session_id) is None


class TestGamesFilterActions:
    """Tests for games platform filter action callbacks."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_set_games_filter_to_arena(
        self, mock_chainlit_action, mock_chainlit_session, session_manager
    ):
        """Test setting games filter to Arena via action."""
        action = mock_chainlit_action("set_games_filter", {"games": "arena"})

        with patch("src.ui.action_callbacks.remove_all_actions", new_callable=AsyncMock):
            with patch("src.ui.app.cl.Message") as mock_message_class:
                mock_message = AsyncMock()
                mock_message_class.return_value = mock_message

                with patch("src.ui.actions.filter_actions._session_manager", session_manager):
                    await on_set_games_filter(action)

        # Verify filter was set to Arena
        session_id = mock_chainlit_session["id"]
        assert session_manager.get_games_filter(session_id) == ["arena"]

        # Verify confirmation message
        call_args = mock_message_class.call_args
        assert "MTG Arena" in call_args.kwargs["content"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_set_games_filter_to_all(
        self, mock_chainlit_action, mock_chainlit_session, session_manager
    ):
        """Test setting games filter to All Platforms via action."""
        # Set initial filter
        session_id = mock_chainlit_session["id"]
        session_manager.set_games_filter(session_id, ["arena"])

        action = mock_chainlit_action("set_games_filter", {"games": "all"})

        with patch("src.ui.action_callbacks.remove_all_actions", new_callable=AsyncMock):
            with patch("src.ui.app.cl.Message") as mock_message_class:
                mock_message = AsyncMock()
                mock_message_class.return_value = mock_message

                with patch("src.ui.actions.filter_actions._session_manager", session_manager):
                    await on_set_games_filter(action)

        # Verify filter was cleared
        assert session_manager.get_games_filter(session_id) is None

        # Verify confirmation message
        call_args = mock_message_class.call_args
        assert "All Platforms" in call_args.kwargs["content"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_games_filter_persists_across_queries(
        self, populated_database, mock_chainlit_session, session_manager
    ):
        """Test that games filter set via action persists for card queries."""
        engine, session_factory = populated_database
        session_id = mock_chainlit_session["id"]

        # Set Arena filter (simulating action callback)
        session_manager.set_games_filter(session_id, ["arena"])

        # Query cards with games filter
        from src.data.repositories.card import CardRepository

        async with session_factory() as session:
            card_repo = CardRepository(session)
            results = await card_repo.search_advanced(
                colors=["R"],
                games=["arena"],
            )

        # Verify only Arena cards returned
        card_names = [card.name for card in results.items]
        assert "Shock" in card_names  # On Arena
        assert "Lightning Bolt" not in card_names  # Not on Arena


class TestCombinedFilters:
    """Tests for combined format and games filters."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_both_filters_applied_together(
        self, populated_database, mock_chainlit_session, session_manager
    ):
        """Test that both format and games filters can be applied simultaneously."""
        engine, session_factory = populated_database
        session_id = mock_chainlit_session["id"]

        # Set both filters
        session_manager.set_format_filter(session_id, "standard")
        session_manager.set_games_filter(session_id, ["arena"])

        # Query with both filters
        from src.data.repositories.card import CardRepository

        async with session_factory() as session:
            card_repo = CardRepository(session)
            results = await card_repo.search_advanced(
                colors=["R"],
                format_filter="standard",
                games=["arena"],
            )

        # Verify only cards matching both filters
        card_names = [card.name for card in results.items]
        assert "Shock" in card_names  # Standard-legal AND on Arena
        assert "Lightning Bolt" not in card_names  # Not Standard-legal
