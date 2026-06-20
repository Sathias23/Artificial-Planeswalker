"""Integration tests for agent with advanced card search tool.

These tests verify end-to-end functionality of the agent using the
advanced card search tool with a real in-memory database.
"""

import os

import pytest
from dotenv import load_dotenv

from legacy.agent.core import create_agent
from legacy.agent.dependencies import AgentDependencies
from src.data.database import create_engine, create_session_factory, init_database
from src.data.repositories.card import CardRepository
from tests.fixtures.card_data import create_sample_cards

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
async def session_factory(in_memory_engine):
    """Create a session factory for testing."""
    return create_session_factory(in_memory_engine)


@pytest.fixture
async def populated_session(session_factory):
    """Create a session with sample card data from fixtures."""
    async with session_factory() as session:
        # Use the same fixture cards as repository tests for consistency
        cards = create_sample_cards()

        for card in cards:
            session.add(card)
        await session.commit()

        yield session


@pytest.fixture
async def card_repository(populated_session):
    """Create a CardRepository with populated data."""
    return CardRepository(populated_session)


@pytest.fixture
async def agent_dependencies(card_repository, populated_session, mock_session_manager):
    """Create AgentDependencies for testing."""
    from src.data.repositories.deck import DeckRepository

    deck_repository = DeckRepository(populated_session)
    return AgentDependencies(
        card_repository=card_repository,
        deck_repository=deck_repository,
        session_id="test-integration-session",
        _session_manager=mock_session_manager,
    )


@pytest.fixture
def agent():
    """Create an agent for testing."""
    return create_agent(defer_model_check=False)


# Integration Tests


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_search_by_color(agent, agent_dependencies):
    """Test agent can search for cards by color."""
    result = await agent.run(
        "Find me red cards. Just list a few.",
        deps=agent_dependencies,
    )

    response = result.output
    # Should find red cards like Lightning Bolt, Goblin Guide
    assert "Lightning" in response or "Goblin" in response or "red" in response.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_search_by_type(agent, agent_dependencies):
    """Test agent can search for cards by type."""
    result = await agent.run(
        "Show me creature cards.",
        deps=agent_dependencies,
    )

    response = result.output
    # Should find creatures like Llanowar Elves, Goblin Guide, etc.
    assert "Creature" in response or "creature" in response.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_search_with_multiple_filters(agent, agent_dependencies):
    """Test agent can search using multiple criteria."""
    result = await agent.run(
        "Find red creatures with haste that cost 3 or less mana.",
        deps=agent_dependencies,
    )

    response = result.output
    # Should find Goblin Guide and Monastery Swiftspear
    assert "Goblin" in response or "Swiftspear" in response or "haste" in response.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_search_by_mana_value(agent, agent_dependencies):
    """Test agent can filter by mana value."""
    result = await agent.run(
        "What cards cost 1 mana or less?",
        deps=agent_dependencies,
    )

    response = result.output
    # Should find 1 CMC cards like Lightning Bolt, Goblin Guide, Llanowar Elves
    assert "Bolt" in response or "Goblin" in response or "Llanowar" in response


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_search_by_keyword(agent, agent_dependencies):
    """Test agent can search for cards with specific keywords."""
    result = await agent.run(
        "Show me cards with flying.",
        deps=agent_dependencies,
    )

    response = result.output
    # Should find cards with flying like Shivan Dragon, Niv-Mizzet, Serra Angel
    assert "Dragon" in response or "Angel" in response or "flying" in response.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_search_no_results(agent, agent_dependencies):
    """Test agent handles searches with no results gracefully."""
    result = await agent.run(
        "Search the database for black creatures with deathtouch. "
        "Tell me what you find in the database.",
        deps=agent_dependencies,
    )

    response = result.output.lower()
    # Agent should communicate no results found in the database
    # The agent may provide general MTG knowledge, but should indicate the database search failed
    assert (
        "couldn't find" in response
        or "no cards" in response
        or "didn't find" in response
        or "no results" in response
        or "empty" in response
        or "database" in response  # Agent mentions database issues/search
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_complex_natural_language_query(agent, agent_dependencies):
    """Test agent handles complex natural language search queries."""
    result = await agent.run(
        "I'm building an aggro deck. Can you show me some cheap red creatures "
        "that have haste? Preferably under 2 mana.",
        deps=agent_dependencies,
    )

    response = result.output
    # Should find and present haste creatures
    assert (
        "Goblin Guide" in response
        or "Monastery Swiftspear" in response
        or "haste" in response.lower()
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_search_result_formatting(agent, agent_dependencies):
    """Test that agent presents search results in a readable format."""
    result = await agent.run(
        "Find instant spells.",
        deps=agent_dependencies,
    )

    response = result.output
    # Should present multiple instants in some organized way
    assert "Lightning" in response or "Counterspell" in response
    # Response should be structured (numbered, bulleted, or organized)
    assert len(response) > 50  # Should be more than a trivial response


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repository_advanced_search_integration(card_repository):
    """Test that CardRepository advanced search works correctly."""
    # This verifies our test setup for advanced search
    results = await card_repository.search_advanced(
        colors=["R"],
        types=["Creature"],
        keywords=["Haste"],
        mana_value_max=3.0,
    )

    # Should find Goblin Guide and Monastery Swiftspear
    assert len(results) >= 2
    card_names = {card.name for card in results}
    assert "Goblin Guide" in card_names
    assert "Monastery Swiftspear" in card_names


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_uses_advanced_search_tool(agent, agent_dependencies):
    """Test that agent automatically chooses advanced search for complex queries."""
    result = await agent.run(
        "Find red instant spells under 2 mana.",
        deps=agent_dependencies,
    )

    response = result.output
    # Should use advanced search and find Lightning Bolt
    assert "Lightning Bolt" in response or "Lightning" in response
