"""Integration tests for agent with card lookup tool.

These tests verify end-to-end functionality of the agent using the
card lookup tool with a real in-memory database.
"""

import os

import pytest
from dotenv import load_dotenv
from pydantic_ai.models.test import TestModel

from legacy.agent.core import create_agent
from legacy.agent.dependencies import AgentDependencies
from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.repositories.card import CardRepository

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
    """Create a session with sample card data."""
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
            ),
            CardModel(
                id="bolt-bend-789",
                name="Bolt Bend",
                oracle_id="oracle-bolt-bend",
                mana_cost="{3}{R}",
                cmc=4.0,
                type_line="Instant",
                oracle_text="Change the target of target spell or ability with a single target.",
                rarity="uncommon",
                set_code="war",
                set_name="War of the Spark",
                collector_number="115",
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
            CardModel(
                id="delver-def",
                name="Delver of Secrets // Insectile Aberration",
                oracle_id="oracle-delver",
                mana_cost="",  # Dual-faced cards have empty root mana_cost
                cmc=1.0,
                type_line="Creature — Human Wizard // Creature — Human Insect",
                oracle_text="",  # Dual-faced cards have empty root oracle_text
                rarity="common",
                set_code="isd",
                set_name="Innistrad",
                collector_number="51",
                colors=["U"],
                color_identity=["U"],
                legalities={"standard": "not_legal", "modern": "legal"},
                image_uris=None,  # Dual-faced cards have images in card_faces
                card_faces=[
                    {
                        "name": "Delver of Secrets",
                        "mana_cost": "{U}",
                        "type_line": "Creature — Human Wizard",
                        "oracle_text": (
                            "At the beginning of your upkeep, look at the top card of "
                            "your library. You may reveal that card. If an instant or "
                            "sorcery card is revealed this way, transform Delver of Secrets."
                        ),
                        "power": "1",
                        "toughness": "1",
                        "image_uris": {
                            "small": "https://cards.scryfall.io/small/front/delver-front.jpg",
                            "normal": "https://cards.scryfall.io/normal/front/delver-front.jpg",
                            "large": "https://cards.scryfall.io/large/front/delver-front.jpg",
                        },
                    },
                    {
                        "name": "Insectile Aberration",
                        "type_line": "Creature — Human Insect",
                        "oracle_text": "Flying",
                        "power": "3",
                        "toughness": "2",
                        "image_uris": {
                            "small": "https://cards.scryfall.io/small/back/delver-back.jpg",
                            "normal": "https://cards.scryfall.io/normal/back/delver-back.jpg",
                            "large": "https://cards.scryfall.io/large/back/delver-back.jpg",
                        },
                    },
                ],
            ),
        ]

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


@pytest.fixture
def test_agent():
    """Create an agent with TestModel for controlled testing."""
    from pydantic_ai import Agent

    from legacy.agent.dependencies import AgentDependencies

    agent = Agent(
        model=TestModel(),
        deps_type=AgentDependencies,
    )

    # Register the tool manually
    from legacy.agent.tools.card_lookup import lookup_card_by_name

    agent.tool(lookup_card_by_name)

    return agent


# Integration Tests


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_exact_card_lookup(agent, agent_dependencies):
    """Test agent can look up a card by exact name."""
    result = await agent.run(
        "Show me the card Lightning Bolt. Respond with just the card information.",
        deps=agent_dependencies,
    )

    response = result.output
    assert "Lightning Bolt" in response
    assert "deals 3 damage" in response or "Instant" in response


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_partial_card_lookup(agent, agent_dependencies):
    """Test agent can find cards with partial name match."""
    result = await agent.run(
        "Find cards with 'bolt' in the name. List them.",
        deps=agent_dependencies,
    )

    response = result.output
    # Should mention multiple cards with "bolt" in name
    # We have: Lightning Bolt, Bolt Bend, Shock (doesn't match)
    assert "Lightning Bolt" in response or "Bolt Bend" in response


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_card_not_found(agent, agent_dependencies):
    """Test agent handles card not found gracefully."""
    result = await agent.run(
        "Look up the card 'Nonexistent Card XYZ'. Tell me what you find.",
        deps=agent_dependencies,
    )

    response = result.output.lower()
    # Agent should communicate that card wasn't found
    assert (
        "couldn't find" in response
        or "not found" in response
        or "can't find" in response
        or "don't have" in response
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_handles_ambiguous_query(agent, agent_dependencies):
    """Test agent asks for clarification on ambiguous queries."""
    result = await agent.run(
        "Show me cards matching 'bolt'. Which one should I show?",
        deps=agent_dependencies,
    )

    response = result.output
    # Should mention multiple matches or ask for clarification
    # We have Lightning Bolt and Bolt Bend
    assert "Lightning Bolt" in response or "Bolt Bend" in response or "which" in response.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_uses_tool_automatically(agent, agent_dependencies):
    """Test that agent automatically uses card lookup tool for card queries."""
    result = await agent.run(
        "What does the card Counterspell do?",
        deps=agent_dependencies,
    )

    response = result.output
    # Should contain information from the card
    assert "Counterspell" in response
    # Should mention the card's effect or type
    assert "counter" in response.lower() or "instant" in response.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_double_faced_card(agent, agent_dependencies):
    """Test agent handles double-faced cards correctly.

    This is a regression test for the bug where dual-faced cards did not
    display oracle text. Verifies that oracle text from both faces is
    retrieved and formatted correctly.
    """
    result = await agent.run(
        "Tell me about Delver of Secrets.",
        deps=agent_dependencies,
    )

    response = result.output
    # Verify card name (may be with or without back face name)
    assert "Delver of Secrets" in response

    # Verify oracle text from FRONT face is present
    assert (
        "At the beginning of your upkeep" in response
        or "look at the top card" in response
        or "instant or sorcery" in response
    ), "Front face oracle text should be displayed"

    # Verify oracle text from BACK face is present
    assert "Flying" in response or "Insectile Aberration" in response, (
        "Back face information should be displayed"
    )

    # Verify card shows it's a dual-faced card
    assert "//" in response or "Front Face" in response or "Back Face" in response


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_conversational_card_query(agent, agent_dependencies):
    """Test agent handles conversational card queries naturally."""
    result = await agent.run(
        "Hey, can you help me find information about that red instant that does 2 damage? "
        "I think it's called Shock or something like that.",
        deps=agent_dependencies,
    )

    response = result.output
    # Agent should find and present Shock
    assert "Shock" in response or "2 damage" in response


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tool_called_with_testmodel(test_agent, agent_dependencies):
    """Test tool is properly registered and callable with TestModel."""
    # TestModel lets us control responses
    result = await test_agent.run(
        "Look up Lightning Bolt",
        deps=agent_dependencies,
    )

    # With TestModel, the tool should still be called
    # TestModel returns tool call results directly
    assert result.output is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_consecutive_lookups(agent, agent_dependencies):
    """Test agent can handle multiple card lookups in conversation."""
    # First lookup
    result1 = await agent.run(
        "Tell me about Lightning Bolt.",
        deps=agent_dependencies,
    )
    assert "Lightning Bolt" in result1.output

    # Second lookup (new conversation)
    result2 = await agent.run(
        "Now tell me about Counterspell.",
        deps=agent_dependencies,
    )
    assert "Counterspell" in result2.output


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_provides_card_details(agent, agent_dependencies):
    """Test agent provides comprehensive card information."""
    result = await agent.run(
        "Give me all the details about Shock.",
        deps=agent_dependencies,
    )

    response = result.output
    # Should include key card details
    assert "Shock" in response
    # Should mention mana cost, type, or effect
    assert "{R}" in response or "red" in response.lower() or "instant" in response.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repository_integration(card_repository):
    """Test that CardRepository works correctly with populated data."""
    # This verifies our test setup is correct
    card = await card_repository.find_by_name_exact("Lightning Bolt")
    assert card is not None
    assert card.name == "Lightning Bolt"

    cards = await card_repository.find_by_name_partial("bolt")
    assert len(cards) >= 2  # Lightning Bolt, Bolt Bend
