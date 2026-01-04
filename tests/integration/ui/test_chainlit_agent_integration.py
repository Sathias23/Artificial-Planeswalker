"""Integration tests for Chainlit UI → Agent → Database flow.

These tests verify the complete end-to-end flow from UI initialization
through agent invocation to database queries.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dotenv import load_dotenv

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.ui.app import get_agent_dependencies, initialize_app

# Load environment variables
load_dotenv()

# Skip tests if OPENROUTER_API_KEY not set
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not set - skipping integration tests",
)


# Fixtures


@pytest.fixture
async def in_memory_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await init_database(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def populated_database(in_memory_engine):
    """Create a populated database for testing."""
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
            ),
            CardModel(
                id="counterspell-abc",
                name="Counterspell",
                oracle_id="oracle-counter",
                mana_cost="{U}{U}",
                cmc=2.0,
                type_line="Instant",
                oracle_text="Counter target spell.",
                rarity="common",
                set_code="lea",
                set_name="Limited Edition Alpha",
                collector_number="54",
                colors=["U"],
                color_identity=["U"],
                legalities={"standard": "not_legal", "modern": "not_legal"},
            ),
        ]

        for card in cards:
            session.add(card)
        await session.commit()

    return in_memory_engine, session_factory


# Integration Tests


@pytest.mark.integration
@pytest.mark.asyncio
async def test_initialize_app_creates_engine_and_agent():
    """Test that initialize_app creates database and agent instances."""
    # Reset global state
    import src.ui.app as app_module

    app_module._engine = None
    app_module._session_factory = None
    app_module._agent = None

    # Initialize app
    await initialize_app()

    # Verify engine and agent are created
    assert app_module._engine is not None
    assert app_module._session_factory is not None
    assert app_module._agent is not None

    # Clean up
    await app_module._engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_initialize_app_is_idempotent():
    """Test that initialize_app can be called multiple times safely."""
    import src.ui.app as app_module

    app_module._engine = None
    app_module._session_factory = None
    app_module._agent = None

    # Initialize twice
    await initialize_app()
    first_engine = app_module._engine
    await initialize_app()
    second_engine = app_module._engine

    # Should be the same instance
    assert first_engine is second_engine

    # Clean up
    await app_module._engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_agent_dependencies_creates_repository():
    """Test that get_agent_dependencies creates a card repository."""
    import src.ui.app as app_module

    app_module._engine = None
    app_module._session_factory = None

    # Initialize app first
    await initialize_app()

    # Get dependencies
    async with get_agent_dependencies(session_id="test-session") as deps:
        # Verify repository is created
        assert deps.card_repository is not None
        assert deps.session_id == "test-session"
        assert deps.format_filter is None  # Default

    # Clean up
    await app_module._engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_agent_query_with_ui_context(populated_database):
    """Test complete flow: UI context → Agent → Database query."""
    import src.ui.app as app_module

    engine, session_factory = populated_database

    # Set up app module state
    app_module._engine = engine
    app_module._session_factory = session_factory

    # Create agent
    from src.agent.core import create_agent

    app_module._agent = create_agent()

    # Test agent query using get_agent_dependencies
    async with get_agent_dependencies(session_id="test-session") as deps:
        result = await app_module._agent.run(
            "Tell me about Lightning Bolt",
            deps=deps,
        )

        # Verify response contains card information
        assert "Lightning Bolt" in result.output
        assert "damage" in result.output.lower() or "instant" in result.output.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chainlit_message_handler_integration():
    """Test message handler integration with mocked Chainlit.

    This verifies that the message handler correctly invokes the agent
    and handles streaming responses.
    """
    import src.ui.app as app_module
    from src.ui.app import on_message

    # Reset and initialize
    app_module._engine = None
    app_module._session_factory = None
    app_module._agent = None

    await initialize_app()

    # Mock Chainlit message
    mock_message = MagicMock()
    mock_message.content = "Show me Lightning Bolt"

    # Mock Chainlit Message class for response
    mock_response_message = AsyncMock()
    mock_response_message.send = AsyncMock()
    mock_response_message.stream_token = AsyncMock()
    mock_response_message.update = AsyncMock()

    with patch("src.ui.app.cl.Message") as mock_message_class:
        mock_message_class.return_value = mock_response_message

        # Call message handler
        await on_message(mock_message)

        # Verify Message was constructed
        mock_message_class.assert_called_once_with(content="")

        # Verify response message was sent
        mock_response_message.send.assert_called_once()

        # Verify message was finalized (update called after streaming)
        mock_response_message.update.assert_called()

    # Clean up
    await app_module._engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_error_handling_in_message_handler():
    """Test that message handler handles errors gracefully."""
    import src.ui.app as app_module
    from src.ui.app import on_message

    # Reset state - deliberately don't initialize to trigger error
    app_module._agent = None

    # Mock Chainlit message
    mock_message = MagicMock()
    mock_message.content = "Test query"

    # Mock Chainlit Message class
    mock_response_message = AsyncMock()
    mock_response_message.send = AsyncMock()

    with patch("src.ui.app.cl.Message") as mock_message_class:
        mock_message_class.return_value = mock_response_message

        # Call message handler with uninitialized agent
        await on_message(mock_message)

        # Verify Message was created with error content
        mock_message_class.assert_called_once()
        call_args = mock_message_class.call_args

        # Check the content parameter contains error message
        assert "content" in call_args.kwargs
        content = call_args.kwargs["content"]
        assert "Error" in content or "not initialized" in content

        # Verify error message was sent
        mock_response_message.send.assert_called_once()
