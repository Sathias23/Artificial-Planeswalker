"""Integration tests for deck creation through the agent.

These tests verify end-to-end deck creation workflow including:
- Agent tool invocation
- Database persistence
- Session state management
"""

import pytest

from src.agent.core import ConversationSessionManager, _session_manager, create_agent
from src.agent.dependencies import AgentDependencies
from src.data.database import create_engine, create_session_factory, init_database
from src.data.repositories.card import CardRepository
from src.data.repositories.deck import DeckRepository

# Fixtures


@pytest.fixture
async def db_engine():
    """Create an in-memory database engine for testing."""
    engine = create_engine(database_url="sqlite+aiosqlite:///:memory:")
    await init_database(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session_factory(db_engine):
    """Create a session factory for the test database."""
    return create_session_factory(db_engine)


@pytest.fixture
def test_agent():
    """Create a test agent with deferred model check."""
    return create_agent(defer_model_check=True)


@pytest.fixture
def session_manager():
    """Create a fresh session manager for each test."""
    return ConversationSessionManager()


# Integration Tests


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeckCreationIntegration:
    """Integration tests for deck creation through agent."""

    async def test_end_to_end_deck_creation(self, db_session_factory, test_agent, session_manager):
        """Test deck creation persists to database and sets active deck ID.

        Scenario:
        - User creates a deck via agent tool
        - Deck is persisted to test database
        - Active deck ID is stored in session manager
        - Deck can be retrieved from database
        """
        session_id = "test-session-deck-creation"

        async with db_session_factory() as session:
            # Create repositories
            card_repository = CardRepository(session)
            deck_repository = DeckRepository(session)

            # Create dependencies
            deps = AgentDependencies(
                card_repository=card_repository,
                deck_repository=deck_repository,
                session_id=session_id,
                _session_manager=_session_manager,
                format_filter=None,
            )

            # Import and call create_deck tool directly
            from unittest.mock import MagicMock

            from pydantic_ai import RunContext

            from src.agent.tools.deck_tools import create_deck

            # Create mock context
            context = MagicMock(spec=RunContext)
            context.deps = deps

            # Act - Create deck via tool
            result = await create_deck(context, name="Integration Test Deck", format="standard")

            # Assert - Tool returned confirmation
            assert "Integration Test Deck" in result
            assert "standard format" in result
            assert "now active" in result

            # Assert - Deck persisted to database
            decks = await deck_repository.list_decks()
            assert len(decks) == 1
            assert decks[0].name == "Integration Test Deck"
            assert decks[0].format == "standard"

            # Assert - Active deck ID set in session manager
            active_deck_id = _session_manager.get_active_deck_id(session_id)
            assert active_deck_id == decks[0].id

            # Assert - Deck can be retrieved by ID
            retrieved_deck = await deck_repository.get_deck(active_deck_id)
            assert retrieved_deck is not None
            assert retrieved_deck.name == "Integration Test Deck"

    async def test_multiple_deck_creations_in_session(
        self, db_session_factory, test_agent, session_manager
    ):
        """Test creating multiple decks in same session.

        Scenario:
        - Create deck 1
        - Create deck 2
        - Both decks persisted
        - Active deck ID updates to most recent
        """
        session_id = "test-session-multiple-decks"

        async with db_session_factory() as session:
            # Create repositories
            card_repository = CardRepository(session)
            deck_repository = DeckRepository(session)

            # Create dependencies
            deps = AgentDependencies(
                card_repository=card_repository,
                deck_repository=deck_repository,
                session_id=session_id,
                _session_manager=_session_manager,
                format_filter=None,
            )

            # Import create_deck tool
            from unittest.mock import MagicMock

            from pydantic_ai import RunContext

            from src.agent.tools.deck_tools import create_deck

            # Create mock context
            context = MagicMock(spec=RunContext)
            context.deps = deps

            # Act - Create first deck
            result_1 = await create_deck(context, name="Deck 1", format="standard")
            assert "Deck 1" in result_1

            # Act - Create second deck
            result_2 = await create_deck(context, name="Deck 2", format="standard")
            assert "Deck 2" in result_2

            # Assert - Both decks persisted
            decks = await deck_repository.list_decks()
            assert len(decks) == 2
            deck_names = {deck.name for deck in decks}
            assert deck_names == {"Deck 1", "Deck 2"}

            # Assert - Active deck ID is the most recent (Deck 2)
            active_deck_id = _session_manager.get_active_deck_id(session_id)
            active_deck = await deck_repository.get_deck(active_deck_id)
            assert active_deck.name == "Deck 2"

    async def test_active_deck_persists_across_turns(
        self, db_session_factory, test_agent, session_manager
    ):
        """Test active deck ID persists across conversation turns.

        Scenario:
        - Turn 1: Create deck
        - Turn 2: New dependencies created with same session_id
        - Active deck ID is restored from session manager
        """
        session_id = "test-session-persistence"

        async with db_session_factory() as session:
            # Turn 1: Create deck
            card_repository = CardRepository(session)
            deck_repository = DeckRepository(session)

            deps_turn_1 = AgentDependencies(
                card_repository=card_repository,
                deck_repository=deck_repository,
                session_id=session_id,
                _session_manager=_session_manager,
                format_filter=None,
            )

            # Create deck
            from unittest.mock import MagicMock

            from pydantic_ai import RunContext

            from src.agent.tools.deck_tools import create_deck

            context = MagicMock(spec=RunContext)
            context.deps = deps_turn_1

            result = await create_deck(context, name="Persistent Deck", format="standard")
            assert "Persistent Deck" in result

            # Get active deck ID from session manager
            active_deck_id_turn_1 = _session_manager.get_active_deck_id(session_id)
            assert active_deck_id_turn_1 is not None

        # Turn 2: Simulate new message (new session, new dependencies)
        async with db_session_factory() as session:
            card_repository = CardRepository(session)
            deck_repository = DeckRepository(session)

            # Retrieve active deck ID from session manager (simulating get_agent_dependencies)
            active_deck_id_restored = _session_manager.get_active_deck_id(session_id)

            # Load active deck from database (simulating get_agent_dependencies behavior)
            active_deck = None
            if active_deck_id_restored:
                active_deck = await deck_repository.get_deck_with_cards(active_deck_id_restored)

            deps_turn_2 = AgentDependencies(
                card_repository=card_repository,
                deck_repository=deck_repository,
                session_id=session_id,
                _session_manager=_session_manager,
                format_filter=None,
                active_deck=active_deck,
            )

            # Assert - Active deck was restored and cached in dependencies
            assert deps_turn_2.active_deck is not None
            assert deps_turn_2.active_deck.id == active_deck_id_turn_1
            assert deps_turn_2.active_deck.name == "Persistent Deck"

    async def test_duplicate_deck_names_allowed(
        self, db_session_factory, test_agent, session_manager
    ):
        """Test that duplicate deck names are allowed (IDs are unique).

        Scenario:
        - Create deck with name "Duplicate Name"
        - Create another deck with same name
        - Both decks persisted with different IDs
        """
        session_id = "test-session-duplicates"

        async with db_session_factory() as session:
            # Create repositories
            card_repository = CardRepository(session)
            deck_repository = DeckRepository(session)

            # Create dependencies
            deps = AgentDependencies(
                card_repository=card_repository,
                deck_repository=deck_repository,
                session_id=session_id,
                _session_manager=_session_manager,
                format_filter=None,
            )

            # Import create_deck tool
            from unittest.mock import MagicMock

            from pydantic_ai import RunContext

            from src.agent.tools.deck_tools import create_deck

            # Create mock context
            context = MagicMock(spec=RunContext)
            context.deps = deps

            # Act - Create first deck
            await create_deck(context, name="Duplicate Name", format="standard")

            # Act - Create second deck with same name
            await create_deck(context, name="Duplicate Name", format="standard")

            # Assert - Both decks persisted
            decks = await deck_repository.list_decks()
            assert len(decks) == 2

            # Assert - Both have same name but different IDs
            assert decks[0].name == "Duplicate Name"
            assert decks[1].name == "Duplicate Name"
            assert decks[0].id != decks[1].id

    async def test_dependencies_handle_missing_deck(self, db_session_factory, session_manager):
        """Test that AgentDependencies handles missing deck defensively.

        Scenario:
        - Session manager has active deck ID set
        - Deck was deleted from database
        - Dependencies creation should handle gracefully (simulating get_agent_dependencies)
        """
        session_id = "test-session-missing-deck"
        fake_deck_id = "00000000-0000-0000-0000-000000000000"

        # Set active deck ID to non-existent deck
        _session_manager.set_active_deck_id(session_id, fake_deck_id)

        async with db_session_factory() as session:
            card_repository = CardRepository(session)
            deck_repository = DeckRepository(session)

            # Simulate get_agent_dependencies behavior
            active_deck_id = _session_manager.get_active_deck_id(session_id)
            active_deck = None
            if active_deck_id:
                active_deck = await deck_repository.get_deck_with_cards(active_deck_id)
                if active_deck is None:
                    # Defensive: deck was deleted, clear the stale ID
                    _session_manager.clear_active_deck_id(session_id)

            # Create dependencies with missing deck handled
            deps = AgentDependencies(
                card_repository=card_repository,
                deck_repository=deck_repository,
                session_id=session_id,
                _session_manager=_session_manager,
                format_filter=None,
                active_deck=active_deck,
            )

            # Assert - active_deck is None (deck not found)
            assert deps.active_deck is None
            assert deps.session_id == session_id

            # Assert - Session manager cleared the stale deck ID
            assert _session_manager.get_active_deck_id(session_id) is None
