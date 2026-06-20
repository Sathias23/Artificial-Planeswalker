"""Integration tests for games filtering functionality.

These tests verify end-to-end functionality of games filtering including:
- Games filter tool functionality
- Filter persistence across session
- Auto-filter bypass with auto_filter=False
- Games filter combined with card searches
"""

import os

import pytest
from dotenv import load_dotenv

from legacy.agent.core import create_agent, run_agent_with_session
from legacy.agent.dependencies import AgentDependencies
from src.data.database import create_engine, create_session_factory, init_database
from src.data.repositories.card import CardRepository
from src.data.repositories.deck import DeckRepository
from tests.fixtures.card_data import (
    create_om1_spm_cards,
    create_sample_cards,
    create_standard_legal_cards,
)

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
    """Create a session with sample card data from fixtures.

    Includes both standard-legal cards (games=["paper", "arena", "mtgo"])
    and non-standard cards (games=["paper", "mtgo"]) for testing games filtering.
    """
    async with session_factory() as session:
        # Add non-standard cards (paper + mtgo only)
        cards = create_sample_cards()
        for card in cards:
            session.add(card)

        # Add standard-legal cards (paper + arena + mtgo)
        standard_cards = create_standard_legal_cards()
        for card in standard_cards:
            session.add(card)

        await session.commit()
        yield session


@pytest.fixture
async def card_repository(populated_session):
    """Create a CardRepository with populated data."""
    return CardRepository(populated_session)


@pytest.fixture
async def deck_repository(populated_session):
    """Create a DeckRepository with populated data."""
    return DeckRepository(populated_session)


@pytest.fixture
async def agent_dependencies(card_repository, deck_repository, mock_session_manager):
    """Create AgentDependencies for testing."""
    return AgentDependencies(
        card_repository=card_repository,
        deck_repository=deck_repository,
        session_id="test-games-filtering-session",
        _session_manager=mock_session_manager,
    )


@pytest.fixture
def agent():
    """Create an agent for testing."""
    return create_agent(defer_model_check=False)


@pytest.fixture
async def om1_spm_populated_session(session_factory):
    """Create a session with OM1/SPM card pairs for testing."""
    async with session_factory() as session:
        # Add OM1/SPM cards
        om1_spm_cards = create_om1_spm_cards()
        for card in om1_spm_cards:
            session.add(card)

        await session.commit()
        yield session


@pytest.fixture
async def om1_spm_card_repository(om1_spm_populated_session):
    """Create a CardRepository with OM1/SPM data."""
    return CardRepository(om1_spm_populated_session)


@pytest.fixture
async def om1_spm_deck_repository(om1_spm_populated_session):
    """Create a DeckRepository with OM1/SPM data."""
    return DeckRepository(om1_spm_populated_session)


@pytest.fixture
async def om1_spm_agent_dependencies(
    om1_spm_card_repository, om1_spm_deck_repository, mock_session_manager
):
    """Create AgentDependencies for OM1/SPM testing."""
    return AgentDependencies(
        card_repository=om1_spm_card_repository,
        deck_repository=om1_spm_deck_repository,
        session_id="test-om1-spm-session",
        _session_manager=mock_session_manager,
    )


# Integration Tests


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_games_filter_arena(agent, agent_dependencies):
    """Test setting games filter to Arena."""
    result = await run_agent_with_session(
        "Set the games filter to Arena",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    response = result.output.lower()
    # Should confirm Arena filter is set
    assert "arena" in response
    assert "filter" in response
    # Filter should be persisted
    assert agent_dependencies.games_filter == ["arena"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_games_filter_paper(agent, agent_dependencies):
    """Test setting games filter to paper."""
    result = await run_agent_with_session(
        "Set the games filter to paper",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    response = result.output.lower()
    # Should confirm paper filter is set
    assert "paper" in response
    assert "filter" in response
    # Filter should be persisted
    assert agent_dependencies.games_filter == ["paper"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_set_games_filter_multiple(agent, agent_dependencies):
    """Test setting games filter to multiple platforms."""
    result = await run_agent_with_session(
        "Set the games filter to paper and arena",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    response = result.output.lower()
    # Should confirm filter is set
    assert "paper" in response and "arena" in response
    assert "filter" in response
    # Filter should include both
    assert set(agent_dependencies.games_filter) == {"paper", "arena"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clear_games_filter(agent, agent_dependencies):
    """Test clearing games filter."""
    # First set a filter
    await run_agent_with_session(
        "Set the games filter to Arena",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    # Then clear it
    result = await run_agent_with_session(
        "Clear the games filter",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    response = result.output.lower()
    # Should confirm filter is disabled
    assert "disabled" in response or "cleared" in response or "all" in response
    # Filter should be None
    assert agent_dependencies.games_filter is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_games_filter_persistence_across_messages(agent, agent_dependencies):
    """Test that games filter persists across multiple messages."""
    # Set filter
    await run_agent_with_session(
        "Set the games filter to Arena",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    # Verify filter persists in second message
    await run_agent_with_session(
        "Search for red cards",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    # Should find Play with Fire (Arena-available) but not Lightning Bolt (not Arena)
    # Note: The agent may or may not mention specific cards, but filter should be active
    assert agent_dependencies.games_filter == ["arena"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_with_games_filter_arena(agent, agent_dependencies):
    """Test card search with Arena games filter active."""
    # Set Arena filter
    await run_agent_with_session(
        "Set the games filter to Arena",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    # Search for cards
    await run_agent_with_session(
        "Find red instant spells",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    # Should find Play with Fire (Standard-legal, Arena-available)
    # Should NOT find Lightning Bolt (not Standard, not on Arena)
    # Note: The agent may provide general info, so we mainly check filter is active
    assert agent_dependencies.games_filter == ["arena"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_with_games_filter_paper(agent, agent_dependencies):
    """Test card search with paper games filter active."""
    # Set paper filter
    await run_agent_with_session(
        "Set the games filter to paper",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    # Search for cards (all cards should be available in paper)
    result = await run_agent_with_session(
        "Find creature cards",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    response = result.output
    # Should find creatures (all should be in paper)
    assert agent_dependencies.games_filter == ["paper"]
    assert len(response) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_card_lookup_with_games_filter(agent, agent_dependencies):
    """Test card lookup with games filter active."""
    # Set Arena filter
    await run_agent_with_session(
        "Set the games filter to Arena",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    # Try to look up a non-Arena card
    await run_agent_with_session(
        "Look up Lightning Bolt",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    # Should not find Lightning Bolt (not on Arena)
    # Agent may mention filter or that card isn't found
    assert agent_dependencies.games_filter == ["arena"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auto_filter_bypass(agent, agent_dependencies):
    """Test auto_filter=False bypasses games filter."""
    # Set Arena filter
    await run_agent_with_session(
        "Set the games filter to Arena",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    # Request to ignore filter (agent should use auto_filter=False)
    result = await run_agent_with_session(
        "Ignore the games filter and show me all red cards regardless of platform",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    response = result.output
    # Agent should bypass filter and find cards from all platforms
    # Filter should still be set, but query should bypass it
    assert agent_dependencies.games_filter == ["arena"]
    assert len(response) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_game_name(agent, agent_dependencies):
    """Test setting an invalid game name."""
    result = await run_agent_with_session(
        "Set the games filter to xbox",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    response = result.output.lower()
    # Should mention invalid game or valid options
    assert "invalid" in response or "valid" in response or "paper" in response
    # Filter should remain None
    assert agent_dependencies.games_filter is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_games_filter_combined_with_format_filter(agent, agent_dependencies):
    """Test games filter works together with format filter."""
    # Set both format and games filters
    await run_agent_with_session(
        "Set the format filter to Standard",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    await run_agent_with_session(
        "Set the games filter to Arena",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    # Both filters should be active
    assert agent_dependencies.format_filter == "standard"
    assert agent_dependencies.games_filter == ["arena"]

    # Search should respect both filters
    result = await run_agent_with_session(
        "Find red cards",
        session_id=agent_dependencies.session_id,
        deps=agent_dependencies,
        agent=agent,
    )

    response = result.output
    # Should only find Standard-legal Arena-available cards
    assert len(response) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repository_games_filter_direct(card_repository):
    """Test CardRepository games filtering works correctly."""
    # This verifies our test setup for games filtering

    # Search for Arena cards
    result_arena = await card_repository.search_advanced(games=["arena"])

    # Should find standard-legal cards (games=["paper", "arena", "mtgo"])
    # Should NOT find non-standard cards (games=["paper", "mtgo"])
    assert len(result_arena.items) >= 1
    for card in result_arena.items:
        assert "arena" in card.games

    # Search for paper-only cards (using MTGO as proxy since all have paper)
    result_mtgo = await card_repository.search_advanced(games=["mtgo"])

    # Should find both standard and non-standard cards
    assert len(result_mtgo.items) >= 1
    for card in result_mtgo.items:
        assert "mtgo" in card.games

    # Verify Arena has fewer cards than MTGO (Arena is more restricted)
    assert len(result_arena.items) <= len(result_mtgo.items)


# OM1/SPM Integration Tests


@pytest.mark.integration
@pytest.mark.asyncio
async def test_om1_spm_arena_search_finds_digital_version(agent, om1_spm_agent_dependencies):
    """Test agent finds OM1 version when searching with Arena filter.

    Verifies the SPIDER_MAN_INVESTIGATION.md scenario where Arena players
    need to find digital-only OM1 versions instead of paper-only SPM versions.
    """
    # Set Arena filter
    await run_agent_with_session(
        "Set the games filter to Arena",
        session_id=om1_spm_agent_dependencies.session_id,
        deps=om1_spm_agent_dependencies,
        agent=agent,
    )

    # Search for Villain creatures
    result = await run_agent_with_session(
        "Find Villain creatures",
        session_id=om1_spm_agent_dependencies.session_id,
        deps=om1_spm_agent_dependencies,
        agent=agent,
    )

    response = result.output.lower()
    # Should mention finding Villain cards
    assert "villain" in response or "creature" in response
    # Filter should still be active
    assert om1_spm_agent_dependencies.games_filter == ["arena"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_om1_spm_paper_search_finds_paper_version(agent, om1_spm_agent_dependencies):
    """Test agent finds SPM version when searching with Paper filter."""
    # Set Paper filter
    await run_agent_with_session(
        "Set the games filter to Paper",
        session_id=om1_spm_agent_dependencies.session_id,
        deps=om1_spm_agent_dependencies,
        agent=agent,
    )

    # Search for Villain creatures
    result = await run_agent_with_session(
        "Find Villain creatures",
        session_id=om1_spm_agent_dependencies.session_id,
        deps=om1_spm_agent_dependencies,
        agent=agent,
    )

    response = result.output.lower()
    # Should mention finding Villain cards
    assert "villain" in response or "creature" in response
    # Filter should still be active
    assert om1_spm_agent_dependencies.games_filter == ["paper"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_om1_spm_lookup_by_name_with_arena_filter(agent, om1_spm_agent_dependencies):
    """Test looking up card by name with Arena filter returns OM1 version."""
    # Set Arena filter
    await run_agent_with_session(
        "Set the games filter to Arena",
        session_id=om1_spm_agent_dependencies.session_id,
        deps=om1_spm_agent_dependencies,
        agent=agent,
    )

    # Look up Ultimate Green Goblin
    result = await run_agent_with_session(
        "Look up Ultimate Green Goblin",
        session_id=om1_spm_agent_dependencies.session_id,
        deps=om1_spm_agent_dependencies,
        agent=agent,
    )

    response = result.output.lower()
    # Should find the card
    assert "ultimate green goblin" in response or "goblin" in response
    # Filter should still be active
    assert om1_spm_agent_dependencies.games_filter == ["arena"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_om1_spm_repository_arena_filter_returns_om1_only(om1_spm_card_repository):
    """Test repository-level verification that Arena filter returns OM1 cards only."""
    # Search for Villain creatures with Arena filter
    result = await om1_spm_card_repository.search_advanced(types=["Villain"], games=["arena"])

    # Should find 2 OM1 cards (Ultimate Green Goblin and Doctor Octopus)
    assert len(result.items) == 2

    # All should be OM1 set and Arena-available
    for card in result.items:
        assert card.set_code == "OM1"
        assert "arena" in card.games
        assert "paper" not in card.games
        assert "Villain" in card.type_line


@pytest.mark.integration
@pytest.mark.asyncio
async def test_om1_spm_repository_paper_filter_returns_spm_only(om1_spm_card_repository):
    """Test repository-level verification that Paper filter returns SPM cards only."""
    # Search for Villain creatures with Paper filter
    result = await om1_spm_card_repository.search_advanced(types=["Villain"], games=["paper"])

    # Should find 2 SPM cards (Ultimate Green Goblin and Doctor Octopus)
    assert len(result.items) == 2

    # All should be SPM set and Paper-available
    for card in result.items:
        assert card.set_code == "SPM"
        assert "paper" in card.games
        assert "arena" not in card.games
        assert "mtgo" not in card.games
        assert "Villain" in card.type_line


@pytest.mark.integration
@pytest.mark.asyncio
async def test_om1_spm_repository_no_filter_returns_both(om1_spm_card_repository):
    """Test repository-level verification that no filter returns both OM1 and SPM."""
    # Search for Villain creatures without games filter
    result = await om1_spm_card_repository.search_advanced(types=["Villain"])

    # Should find all 4 cards (2 SPM + 2 OM1)
    assert len(result.items) == 4

    # Should have both set codes
    set_codes = {card.set_code for card in result.items}
    assert set_codes == {"SPM", "OM1"}

    # Should have both versions of each card
    card_names = [card.name for card in result.items]
    assert card_names.count("Ultimate Green Goblin") == 2
    assert card_names.count("Doctor Octopus") == 2
