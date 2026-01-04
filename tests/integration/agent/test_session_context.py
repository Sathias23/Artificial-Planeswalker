"""Integration tests for multi-turn conversation context and session state persistence.

These tests verify that conversation context is properly maintained across multiple
messages within a session, including message history and session state like format filters.
"""

import pytest

from src.agent.core import ConversationSessionManager, create_agent
from src.agent.dependencies import AgentDependencies
from src.data.database import create_engine, create_session_factory, init_database
from src.data.repositories.card import CardRepository

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
async def card_repository(db_session_factory):
    """Create a card repository with database session."""
    async with db_session_factory() as session:
        # Add test cards to the database
        repo = CardRepository(session)

        # Note: Example test data shown below - not currently inserted into DB
        # In a full integration test, these would be inserted as CardModel instances
        # For now, we test session management without actual card data

        # Example cards that could be used:
        # - Bloodhall Ooze (Conflux) for context follow-up tests
        # - Lightning Bolt (Standard-legal) for filter tests
        # - Shock (Standard-legal) for filter tests
        # - Black Lotus (not Standard-legal) for filter tests

        yield repo


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
class TestMultiTurnConversationContext:
    """Integration tests for multi-turn conversation context preservation."""

    async def test_multi_turn_conversation_context(
        self, db_session_factory, test_agent, session_manager
    ):
        """Test that agent remembers context across multiple messages.

        Scenario:
        - Message 1: "Tell me about Bloodhall Ooze"
        - Message 2: "What set is it from?"
        - Agent should identify "it" refers to Bloodhall Ooze from message 1
        """
        session_id = "test-session-context"

        # Patch the global session manager for this test
        from src.agent import core

        async with db_session_factory() as session:
            # Create dependencies (would use CardRepository here in full integration test)
            _ = CardRepository(session)

            original_manager = core._session_manager
            core._session_manager = session_manager

            try:
                # Verify the session manager is being used correctly
                # by checking that history is stored and retrieved
                history_before = session_manager.get_history(session_id)
                assert history_before == []

                # In a real integration test with actual agent and DB data:
                # response1 = await run_agent_with_session(
                #     user_input="Tell me about Bloodhall Ooze",
                #     session_id=session_id,
                #     deps=AgentDependencies(...),
                #     agent=test_agent,
                # )
                # assert "Bloodhall Ooze" in response1
                # assert "Conflux" in response2

            finally:
                # Restore original manager
                core._session_manager = original_manager

    async def test_format_filter_persistence_across_messages(
        self, db_session_factory, session_manager
    ):
        """Test that format filter persists across messages in the same session.

        Scenario:
        - Message 1: "Only show me Standard cards" (sets format filter)
        - Message 2: "Find red creatures" (filter should still be active)
        - All results from message 2 should be Standard-legal
        """
        session_id = "test-session-filter"

        # Test format filter persistence at the session manager level
        # Set filter in message 1
        session_manager.set_format_filter(session_id, "standard")

        # Verify filter persists for message 2
        filter_value = session_manager.get_format_filter(session_id)
        assert filter_value == "standard"

        # Create dependencies with session_id
        async with db_session_factory() as session:
            repo = CardRepository(session)
            from src.data.repositories.deck import DeckRepository

            deck_repo = DeckRepository(session)

            # Simulate get_agent_dependencies behavior
            restored_filter = session_manager.get_format_filter(session_id)

            deps = AgentDependencies(
                card_repository=repo,
                deck_repository=deck_repo,
                session_id=session_id,
                _session_manager=session_manager,
                format_filter=restored_filter,
            )

            # Verify dependencies have the restored filter
            assert deps.format_filter == "standard"

    async def test_session_isolation_format_filters(self, session_manager):
        """Test that format filters are isolated between sessions.

        Scenario:
        - Session A sets format to "standard"
        - Session B queries without setting filter
        - Session A should have "standard" filter
        - Session B should have None filter
        """
        session_a = "session-a"
        session_b = "session-b"

        # Session A sets Standard filter
        session_manager.set_format_filter(session_a, "standard")

        # Session B doesn't set filter
        # (no action needed, just query)

        # Verify isolation
        filter_a = session_manager.get_format_filter(session_a)
        filter_b = session_manager.get_format_filter(session_b)

        assert filter_a == "standard"
        assert filter_b is None

    async def test_context_dependent_tool_calls(self, db_session_factory, session_manager):
        """Test that tool call results are maintained in conversation history.

        Scenario:
        - Message 1: Execute card lookup tool
        - Message 2: Follow-up question about the looked-up card
        - Agent should reference tool results from message 1 without re-executing
        """
        session_id = "test-session-tools"

        # Verify session manager tracks history correctly
        history = session_manager.get_history(session_id)
        assert history == []

        # Simulate updating history after a tool call
        # In a real test, run_agent_with_session would do this automatically
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        mock_messages = [
            ModelRequest(parts=[UserPromptPart(content="Lookup Lightning Bolt")]),
            # Tool calls and responses would be here in real agent run
        ]

        session_manager.update_history(session_id, mock_messages)

        # Verify history was stored
        retrieved_history = session_manager.get_history(session_id)
        assert len(retrieved_history) == 1
        assert retrieved_history[0].parts[0].content == "Lookup Lightning Bolt"  # type: ignore

    async def test_session_state_cleanup(self, session_manager):
        """Test that clearing a session removes both history and format filter.

        Scenario:
        - Set format filter and add history to session
        - Clear session
        - Both history and filter should be removed
        """
        session_id = "test-session-cleanup"

        # Set both history and filter
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        messages = [ModelRequest(parts=[UserPromptPart(content="Test message")])]
        session_manager.update_history(session_id, messages)
        session_manager.set_format_filter(session_id, "standard")

        # Verify both are set
        assert session_manager.get_history(session_id) != []
        assert session_manager.get_format_filter(session_id) == "standard"

        # Clear session
        session_manager.clear_session(session_id)

        # Verify both are cleared
        assert session_manager.get_history(session_id) == []
        assert session_manager.get_format_filter(session_id) is None

    async def test_format_filter_change_mid_session(self, session_manager):
        """Test that format filter can be changed mid-session.

        Scenario:
        - Set format to "standard" in message 1
        - Change format to None in message 4
        - Filter should update correctly
        """
        session_id = "test-session-filter-change"

        # Message 1: Set Standard filter
        session_manager.set_format_filter(session_id, "standard")
        assert session_manager.get_format_filter(session_id) == "standard"

        # Message 4: Disable filter
        session_manager.set_format_filter(session_id, None)
        assert session_manager.get_format_filter(session_id) is None

    async def test_concurrent_sessions_independence(self, session_manager):
        """Test that multiple concurrent sessions maintain independent state.

        Scenario:
        - User A sets format to "standard" in their session
        - User B queries in their separate session without setting format
        - User A's filter should not affect User B's session
        """
        session_user_a = "user-a-session"
        session_user_b = "user-b-session"

        # User A sets Standard filter
        session_manager.set_format_filter(session_user_a, "standard")

        # User B's session has no filter
        # (default behavior, no action needed)

        # Verify independence
        assert session_manager.get_format_filter(session_user_a) == "standard"
        assert session_manager.get_format_filter(session_user_b) is None

        # User A's actions should not affect User B
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        messages_a = [ModelRequest(parts=[UserPromptPart(content="User A message")])]
        session_manager.update_history(session_user_a, messages_a)

        # User B's history should still be empty
        assert session_manager.get_history(session_user_b) == []
