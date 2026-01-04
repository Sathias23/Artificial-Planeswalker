"""Integration tests for mana curve analysis agent tool."""

import pytest

from src.agent.core import ConversationSessionManager
from src.agent.dependencies import AgentDependencies
from src.data.database import create_engine, create_session_factory, init_database
from src.data.repositories.card import CardRepository
from src.data.repositories.deck import DeckRepository
from src.data.schemas import Card

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
def test_session_manager():
    """Create a fresh session manager for each test."""
    return ConversationSessionManager()


@pytest.fixture
async def sample_cards(db_session_factory) -> list[Card]:
    """Create sample cards for testing and insert them into database."""
    from src.data.models.card import CardModel

    cards_data = [
        {
            "id": "mountain-1",
            "name": "Mountain",
            "oracle_id": "oracle-mountain",
            "cmc": 0.0,
            "type_line": "Basic Land — Mountain",
            "oracle_text": "{T}: Add {R}.",
            "mana_cost": "",
            "colors": [],
            "color_identity": ["R"],
            "keywords": [],
            "legalities": {"standard": "legal"},
            "rarity": "common",
            "set_code": "M21",
            "set_name": "Core Set 2021",
            "collector_number": "274",
            "image_uris": None,
        },
        {
            "id": "bolt-1",
            "name": "Lightning Bolt",
            "oracle_id": "oracle-bolt",
            "cmc": 1.0,
            "type_line": "Instant",
            "oracle_text": "Lightning Bolt deals 3 damage to any target.",
            "mana_cost": "{R}",
            "colors": ["R"],
            "color_identity": ["R"],
            "keywords": [],
            "legalities": {"standard": "legal"},
            "rarity": "common",
            "set_code": "M21",
            "set_name": "Core Set 2021",
            "collector_number": "163",
            "image_uris": None,
        },
        {
            "id": "counterspell-1",
            "name": "Counterspell",
            "oracle_id": "oracle-counterspell",
            "cmc": 2.0,
            "type_line": "Instant",
            "oracle_text": "Counter target spell.",
            "mana_cost": "{U}{U}",
            "colors": ["U"],
            "color_identity": ["U"],
            "keywords": [],
            "legalities": {"standard": "legal"},
            "rarity": "common",
            "set_code": "M21",
            "set_name": "Core Set 2021",
            "collector_number": "46",
            "image_uris": None,
        },
        {
            "id": "murder-1",
            "name": "Murder",
            "oracle_id": "oracle-murder",
            "cmc": 3.0,
            "type_line": "Instant",
            "oracle_text": "Destroy target creature.",
            "mana_cost": "{1}{B}{B}",
            "colors": ["B"],
            "color_identity": ["B"],
            "keywords": [],
            "legalities": {"standard": "legal"},
            "rarity": "common",
            "set_code": "M21",
            "set_name": "Core Set 2021",
            "collector_number": "115",
            "image_uris": None,
        },
    ]

    async with db_session_factory() as session:
        # Insert cards into database
        for card_data in cards_data:
            card_model = CardModel(**card_data)
            session.add(card_model)
        await session.commit()

    # Return Card schemas for use in tests
    return [Card(**card_data) for card_data in cards_data]


@pytest.mark.integration
class TestManaCurveTool:
    """Integration tests for mana curve analysis tool."""

    async def test_analyze_deck_mana_curve_success(
        self,
        db_session_factory,
        test_session_manager,
        sample_cards: list[Card],
    ) -> None:
        """Test successful mana curve analysis of an active deck."""
        session_id = "test-session-mana-curve"

        async with db_session_factory() as session:
            # Create repositories
            card_repository = CardRepository(session)
            deck_repository = DeckRepository(session)

            # Create a deck with known mana curve
            deck = await deck_repository.create_deck(
                name="Test Curve Deck",
                format="standard",
                strategy=None,
            )

            # Add cards to deck
            await deck_repository.add_card_to_deck(
                deck.id, sample_cards[0].id, quantity=24, sideboard=False
            )
            await deck_repository.add_card_to_deck(
                deck.id, sample_cards[1].id, quantity=12, sideboard=False
            )
            await deck_repository.add_card_to_deck(
                deck.id, sample_cards[2].id, quantity=12, sideboard=False
            )
            await deck_repository.add_card_to_deck(
                deck.id, sample_cards[3].id, quantity=12, sideboard=False
            )

            #  Get updated deck with cards
            saved_deck = await deck_repository.get_deck_with_cards(deck.id)
            assert saved_deck is not None

            # Set as active deck
            test_session_manager.set_active_deck_id(session_id, saved_deck.id)

            # Create dependencies
            deps = AgentDependencies(
                card_repository=card_repository,
                deck_repository=deck_repository,
                session_id=session_id,
                _session_manager=test_session_manager,
            )

            # Execute tool directly
            from pydantic_ai import Agent, RunContext

            from src.agent.tools.mana_curve import register_mana_curve_tool

            # Create a minimal agent just for tool testing
            test_agent: Agent[AgentDependencies, str] = Agent(
                "openai:gpt-4",  # Dummy model
                deps_type=AgentDependencies,
                defer_model_check=True,
            )
            register_mana_curve_tool(test_agent)

            # Get the tool function
            tool_func = None
            for tool in test_agent._function_toolset.tools:
                if tool.name == "analyze_deck_mana_curve":
                    tool_func = tool.function
                    break

            assert tool_func is not None, "Mana curve tool not registered"

            # Execute tool
            ctx = RunContext(deps=deps, retry=0, tool_name="analyze_deck_mana_curve")
            result = await tool_func(ctx)

            # Verify result structure
            assert isinstance(result, str)
            assert "Mana Curve Analysis" in result
            assert "Test Curve Deck" in result

            # Verify distribution is shown
            assert "CMC Distribution" in result
            assert "CMC 1:" in result  # Lightning Bolts
            assert "CMC 2:" in result  # Counterspells
            assert "CMC 3:" in result  # Murders

            # Verify metadata
            assert "Total Cards: 60" in result
            assert "48 spells, 24 lands" in result
            assert "Land Ratio: 40.0%" in result

            # Verify playability section
            assert "Playable Cards by Turn" in result

            # Verify recommendations section
            assert "Recommendations" in result

    async def test_analyze_deck_no_active_deck(
        self,
        db_session_factory,
        test_session_manager,
    ) -> None:
        """Test mana curve analysis with no active deck."""
        session_id = "test-session-no-deck"

        async with db_session_factory() as session:
            # Create repositories
            card_repository = CardRepository(session)
            deck_repository = DeckRepository(session)

            # Create dependencies (no active deck set)
            deps = AgentDependencies(
                card_repository=card_repository,
                deck_repository=deck_repository,
                session_id=session_id,
                _session_manager=test_session_manager,
            )

            # Execute tool directly
            from pydantic_ai import Agent, RunContext

            from src.agent.tools.mana_curve import register_mana_curve_tool

            test_agent: Agent[AgentDependencies, str] = Agent(
                "openai:gpt-4",
                deps_type=AgentDependencies,
                defer_model_check=True,
            )
            register_mana_curve_tool(test_agent)

            tool_func = None
            for tool in test_agent._function_toolset.tools:
                if tool.name == "analyze_deck_mana_curve":
                    tool_func = tool.function
                    break

            assert tool_func is not None

            ctx = RunContext(deps=deps, retry=0, tool_name="analyze_deck_mana_curve")
            result = await tool_func(ctx)

            assert "No active deck" in result
            assert "create_deck()" in result or "load_deck()" in result

    async def test_analyze_empty_deck(
        self,
        db_session_factory,
        test_session_manager,
    ) -> None:
        """Test mana curve analysis of an empty deck."""
        session_id = "test-session-empty-deck"

        async with db_session_factory() as session:
            # Create repositories
            card_repository = CardRepository(session)
            deck_repository = DeckRepository(session)

            # Create empty deck
            saved_deck = await deck_repository.create_deck(
                name="Empty Deck",
                format="standard",
                strategy=None,
            )

            # Set as active deck
            test_session_manager.set_active_deck_id(session_id, saved_deck.id)

            # Create dependencies
            deps = AgentDependencies(
                card_repository=card_repository,
                deck_repository=deck_repository,
                session_id=session_id,
                _session_manager=test_session_manager,
            )

            # Execute tool directly
            from pydantic_ai import Agent, RunContext

            from src.agent.tools.mana_curve import register_mana_curve_tool

            test_agent: Agent[AgentDependencies, str] = Agent(
                "openai:gpt-4",
                deps_type=AgentDependencies,
                defer_model_check=True,
            )
            register_mana_curve_tool(test_agent)

            tool_func = None
            for tool in test_agent._function_toolset.tools:
                if tool.name == "analyze_deck_mana_curve":
                    tool_func = tool.function
                    break

            assert tool_func is not None

            ctx = RunContext(deps=deps, retry=0, tool_name="analyze_deck_mana_curve")
            result = await tool_func(ctx)

            assert "Empty Deck" in result
            assert "empty" in result.lower()
            assert "Add cards" in result

    async def test_analyze_deck_detects_issues(
        self,
        db_session_factory,
        test_session_manager,
        sample_cards: list[Card],
    ) -> None:
        """Test that mana curve analysis detects common issues."""
        session_id = "test-session-low-lands"

        async with db_session_factory() as session:
            # Create repositories
            card_repository = CardRepository(session)
            deck_repository = DeckRepository(session)

            # Create deck with mana screw risk (too few lands)
            deck = await deck_repository.create_deck(
                name="Low Land Deck",
                format="standard",
                strategy=None,
            )

            # Add cards
            await deck_repository.add_card_to_deck(
                deck.id,
                sample_cards[0].id,
                quantity=15,
                sideboard=False,  # Only 15 lands
            )
            await deck_repository.add_card_to_deck(
                deck.id,
                sample_cards[1].id,
                quantity=45,
                sideboard=False,  # 45 spells
            )

            # Get updated deck
            saved_deck = await deck_repository.get_deck_with_cards(deck.id)
            assert saved_deck is not None

            # Set as active deck
            test_session_manager.set_active_deck_id(session_id, saved_deck.id)

            # Create dependencies
            deps = AgentDependencies(
                card_repository=card_repository,
                deck_repository=deck_repository,
                session_id=session_id,
                _session_manager=test_session_manager,
            )

            # Execute tool directly
            from pydantic_ai import Agent, RunContext

            from src.agent.tools.mana_curve import register_mana_curve_tool

            test_agent: Agent[AgentDependencies, str] = Agent(
                "openai:gpt-4",
                deps_type=AgentDependencies,
                defer_model_check=True,
            )
            register_mana_curve_tool(test_agent)

            tool_func = None
            for tool in test_agent._function_toolset.tools:
                if tool.name == "analyze_deck_mana_curve":
                    tool_func = tool.function
                    break

            assert tool_func is not None

            ctx = RunContext(deps=deps, retry=0, tool_name="analyze_deck_mana_curve")
            result = await tool_func(ctx)

            # Verify issue detection
            assert "Issues Detected" in result
            assert "Mana screw risk" in result or "screw" in result.lower()

            # Verify recommendations
            assert "Add ~" in result  # Should recommend adding lands
            assert "lands" in result.lower()
