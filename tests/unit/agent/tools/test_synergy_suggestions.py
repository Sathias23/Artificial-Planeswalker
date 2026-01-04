"""Unit tests for synergy_suggestions tool."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import RunContext

from src.agent.dependencies import AgentDependencies
from src.agent.tools.synergy_suggestions import (
    CardSuggestions,
    CuratedCard,
    DeckAnalysis,
    DeckNeedAnalysis,
    _build_deck_context,
    _format_candidates,
    _format_suggestions_output,
    _search_candidates,
    suggest_synergy_cards,
)
from src.data.schemas.card import Card
from src.data.schemas.deck import Deck, DeckCard

# Fixtures


@pytest.fixture
def sample_card() -> Card:
    """Create a sample Card for testing."""
    return Card(
        id="test-card-id-1",
        name="Goblin Guide",
        oracle_id="oracle-1",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Creature — Goblin Scout",
        oracle_text="Haste. Whenever Goblin Guide attacks, defending player reveals...",
        rarity="rare",
        set_code="zen",
        set_name="Zendikar",
        collector_number="126",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "not_legal", "modern": "legal"},
        image_uris={"normal": "https://example.com/goblin_guide.jpg"},
    )


@pytest.fixture
def sample_creature_card() -> Card:
    """Create a creature card for deck testing."""
    return Card(
        id="test-creature-id",
        name="Lightning Dragon",
        oracle_id="oracle-dragon",
        mana_cost="{2}{R}{R}",
        cmc=4.0,
        type_line="Creature — Dragon",
        oracle_text="Flying, haste. {R}: Lightning Dragon gets +1/+0 until end of turn.",
        rarity="rare",
        set_code="test",
        set_name="Test Set",
        collector_number="1",
        colors=["R"],
        color_identity=["R"],
        legalities={"standard": "legal"},
    )


@pytest.fixture
def sample_spell_card() -> Card:
    """Create a spell card for deck testing."""
    return Card(
        id="test-spell-id",
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
    )


@pytest.fixture
def sample_land_card() -> Card:
    """Create a land card for deck testing."""
    return Card(
        id="test-land-id",
        name="Mountain",
        oracle_id="oracle-mountain",
        mana_cost="",
        cmc=0.0,
        type_line="Basic Land — Mountain",
        oracle_text="{T}: Add {R}.",
        rarity="common",
        set_code="lea",
        set_name="Limited Edition Alpha",
        collector_number="293",
        colors=[],
        color_identity=["R"],
        legalities={"standard": "legal"},
    )


@pytest.fixture
def sample_deck_cards(sample_creature_card, sample_spell_card, sample_land_card) -> list[DeckCard]:
    """Create a list of DeckCards for a simple red deck."""
    return [
        DeckCard(
            deck_id="test-deck-id",
            card_id=sample_creature_card.id,
            quantity=4,
            sideboard=False,
            card=sample_creature_card,
        ),
        DeckCard(
            deck_id="test-deck-id",
            card_id=sample_spell_card.id,
            quantity=4,
            sideboard=False,
            card=sample_spell_card,
        ),
        DeckCard(
            deck_id="test-deck-id",
            card_id=sample_land_card.id,
            quantity=20,
            sideboard=False,
            card=sample_land_card,
        ),
    ]


@pytest.fixture
def sample_deck(sample_deck_cards) -> Deck:
    """Create a sample Deck for testing."""
    return Deck(
        id="test-deck-id",
        name="Mono Red Aggro",
        format="standard",
        strategy="Fast aggressive deck",
        color_identity=["R"],
        tags=["aggro", "red"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        deck_cards=sample_deck_cards,
    )


@pytest.fixture
def empty_deck() -> Deck:
    """Create an empty Deck for testing."""
    return Deck(
        id="empty-deck-id",
        name="Empty Deck",
        format="standard",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        deck_cards=[],
    )


@pytest.fixture
def mock_card_repository():
    """Create a mock CardRepository for testing."""
    repo = MagicMock()
    repo.search_advanced = AsyncMock()
    return repo


@pytest.fixture
def mock_deck_repository():
    """Create a mock DeckRepository for testing."""
    repo = MagicMock()
    repo.get_deck_with_cards = AsyncMock()
    return repo


@pytest.fixture
def mock_dependencies(mock_card_repository, mock_deck_repository, mock_session_manager):
    """Create mock AgentDependencies for testing."""
    deps = AgentDependencies(
        card_repository=mock_card_repository,
        deck_repository=mock_deck_repository,
        session_id="test-session",
        _session_manager=mock_session_manager,
    )
    return deps


@pytest.fixture
def mock_run_context(mock_dependencies):
    """Create a mock RunContext for testing."""
    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_dependencies
    return ctx


# Tests for Pydantic Models


class TestPydanticModels:
    """Tests for the Pydantic models used in synergy suggestions."""

    def test_deck_need_analysis_creation(self):
        """Test DeckNeedAnalysis model creation."""
        need = DeckNeedAnalysis(
            need_type="creature",
            description="lacks early creatures",
            search_keywords=["haste", "trample"],
            search_types=["Creature"],
            max_cmc=3,
        )
        assert need.need_type == "creature"
        assert need.description == "lacks early creatures"
        assert need.search_keywords == ["haste", "trample"]
        assert need.max_cmc == 3

    def test_deck_need_analysis_defaults(self):
        """Test DeckNeedAnalysis model with default values."""
        need = DeckNeedAnalysis(
            need_type="removal",
            description="needs more removal",
        )
        assert need.search_keywords == []
        assert need.search_types == []
        assert need.max_cmc is None

    def test_deck_analysis_creation(self):
        """Test DeckAnalysis model creation."""
        analysis = DeckAnalysis(
            primary_synergy="Goblin tribal",
            search_criteria=[
                DeckNeedAnalysis(need_type="creature", description="need goblins"),
                DeckNeedAnalysis(need_type="creature", description="more goblins"),
                DeckNeedAnalysis(need_type="removal", description="need removal"),
            ],
            reasoning="Deck needs more goblin creatures and removal spells.",
        )
        assert analysis.primary_synergy == "Goblin tribal"
        assert len(analysis.search_criteria) == 3
        assert "goblin" in analysis.reasoning.lower()

    def test_deck_analysis_validates_min_criteria(self):
        """Test DeckAnalysis validates minimum 3 search criteria."""
        with pytest.raises(ValueError):
            DeckAnalysis(
                primary_synergy="Test",
                search_criteria=[
                    DeckNeedAnalysis(need_type="creature", description="one"),
                    DeckNeedAnalysis(need_type="creature", description="two"),
                ],
                reasoning="Not enough criteria",
            )

    def test_curated_card_creation(self):
        """Test CuratedCard model creation."""
        card = CuratedCard(
            card_name="Goblin Guide",
            synergy_fit="Triggers death effects while providing card advantage",
            priority=1,
        )
        assert card.card_name == "Goblin Guide"
        assert card.priority == 1
        assert "death effects" in card.synergy_fit

    def test_curated_card_validates_priority_range(self):
        """Test CuratedCard validates priority is 1-5."""
        with pytest.raises(ValueError):
            CuratedCard(
                card_name="Test Card",
                synergy_fit="Test fit",
                priority=6,
            )

    def test_card_suggestions_creation(self):
        """Test CardSuggestions model creation."""
        suggestions = CardSuggestions(
            top_picks=[
                CuratedCard(card_name=f"Card {i}", synergy_fit=f"Fit {i}", priority=i)
                for i in range(1, 6)
            ],
            overall_strategy="These additions strengthen the sacrifice subtheme",
        )
        assert len(suggestions.top_picks) == 5
        assert "sacrifice" in suggestions.overall_strategy

    def test_card_suggestions_validates_min_picks(self):
        """Test CardSuggestions validates minimum 5 top picks."""
        with pytest.raises(ValueError):
            CardSuggestions(
                top_picks=[
                    CuratedCard(card_name=f"Card {i}", synergy_fit=f"Fit {i}", priority=i)
                    for i in range(1, 4)
                ],
                overall_strategy="Not enough picks",
            )


# Tests for Helper Functions


class TestBuildDeckContext:
    """Tests for _build_deck_context helper function."""

    def test_builds_context_for_deck(self, sample_deck):
        """Test _build_deck_context generates comprehensive context."""
        context = _build_deck_context(sample_deck)

        # Verify deck metadata is included
        assert "Mono Red Aggro" in context
        assert "standard" in context.lower()
        assert "R" in context  # Color identity

        # Verify mana curve section exists
        assert "Mana Curve" in context
        assert "Average CMC" in context

        # Verify cards section exists
        assert "Cards by Type" in context or "Creatures" in context

    def test_builds_context_for_empty_deck(self, empty_deck):
        """Test _build_deck_context handles empty deck."""
        context = _build_deck_context(empty_deck)

        # Should still generate context without crashing
        assert "Empty Deck" in context
        assert "0" in context or "empty" in context.lower()

    def test_includes_synergy_analysis(self, sample_deck):
        """Test _build_deck_context includes synergy analysis."""
        context = _build_deck_context(sample_deck)

        # Synergy section should exist
        assert "Synergies" in context or "synergy" in context.lower()


class TestFormatCandidates:
    """Tests for _format_candidates helper function."""

    def test_formats_single_card(self, sample_card):
        """Test _format_candidates formats a single card correctly."""
        result = _format_candidates([sample_card])

        # Should include card name, cost, type, and oracle text
        assert "Goblin Guide" in result
        assert "{R}" in result
        assert "Creature" in result
        assert "Haste" in result

    def test_formats_multiple_cards(self, sample_card, sample_creature_card, sample_spell_card):
        """Test _format_candidates formats multiple cards."""
        cards = [sample_card, sample_creature_card, sample_spell_card]
        result = _format_candidates(cards)

        # All cards should be in output
        assert "Goblin Guide" in result
        assert "Lightning Dragon" in result
        assert "Lightning Bolt" in result

    def test_truncates_long_oracle_text(self):
        """Test _format_candidates truncates very long oracle text."""
        long_text_card = Card(
            id="long-text-id",
            name="Wordy Card",
            oracle_id="oracle-wordy",
            mana_cost="{3}{U}{U}",
            cmc=5.0,
            type_line="Enchantment",
            oracle_text="This is very long text. " * 20,  # ~500 chars
            rarity="rare",
            set_code="test",
            set_name="Test Set",
            collector_number="1",
            colors=["U"],
            color_identity=["U"],
            legalities={},
        )
        result = _format_candidates([long_text_card])

        # Oracle text should be truncated
        assert "..." in result
        # But card name should be present
        assert "Wordy Card" in result

    def test_handles_empty_list(self):
        """Test _format_candidates handles empty card list."""
        result = _format_candidates([])
        assert result == ""


class TestSearchCandidates:
    """Tests for _search_candidates helper function."""

    @pytest.fixture
    def mock_paginated_result(self, sample_card, sample_creature_card):
        """Create a mock PaginatedResult for testing."""
        mock_result = MagicMock()
        mock_result.items = [sample_card, sample_creature_card]
        return mock_result

    @pytest.mark.asyncio
    async def test_executes_parallel_searches(
        self, mock_card_repository, mock_dependencies, sample_deck
    ):
        """Test _search_candidates executes searches in parallel."""
        # Setup mock to return empty results
        mock_result = MagicMock()
        mock_result.items = []
        mock_card_repository.search_advanced = AsyncMock(return_value=mock_result)

        analysis = DeckAnalysis(
            primary_synergy="Test",
            search_criteria=[
                DeckNeedAnalysis(need_type="creature", description="need creatures"),
                DeckNeedAnalysis(need_type="removal", description="need removal"),
                DeckNeedAnalysis(need_type="card_draw", description="need draw"),
            ],
            reasoning="Test reasoning",
        )

        await _search_candidates(
            analysis=analysis,
            card_repo=mock_card_repository,
            deps=mock_dependencies,
            deck=sample_deck,
        )

        # Should have called search_advanced 3 times (one per criteria)
        assert mock_card_repository.search_advanced.call_count == 3

    @pytest.mark.asyncio
    async def test_deduplicates_results_by_name(
        self, mock_card_repository, mock_dependencies, sample_deck
    ):
        """Test _search_candidates removes duplicate cards by name."""
        # Create two cards with same name
        card1 = Card(
            id="card-1",
            name="Duplicate Card",
            oracle_id="oracle-1",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Instant",
            oracle_text="Test",
            rarity="common",
            set_code="set1",
            set_name="Set 1",
            collector_number="1",
            colors=["R"],
            color_identity=["R"],
            legalities={},
        )
        card2 = Card(
            id="card-2",  # Different ID
            name="Duplicate Card",  # Same name
            oracle_id="oracle-1",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Instant",
            oracle_text="Test",
            rarity="common",
            set_code="set2",
            set_name="Set 2",
            collector_number="1",
            colors=["R"],
            color_identity=["R"],
            legalities={},
        )

        mock_result = MagicMock()
        mock_result.items = [card1, card2]
        mock_card_repository.search_advanced = AsyncMock(return_value=mock_result)

        analysis = DeckAnalysis(
            primary_synergy="Test",
            search_criteria=[
                DeckNeedAnalysis(need_type="creature", description="need creatures"),
                DeckNeedAnalysis(need_type="removal", description="need removal"),
                DeckNeedAnalysis(need_type="card_draw", description="need draw"),
            ],
            reasoning="Test reasoning",
        )

        result = await _search_candidates(
            analysis=analysis,
            card_repo=mock_card_repository,
            deps=mock_dependencies,
            deck=sample_deck,
        )

        # Should only have one card despite duplicates across searches
        assert len([c for c in result if c.name == "Duplicate Card"]) == 1

    @pytest.mark.asyncio
    async def test_excludes_cards_already_in_deck(
        self, mock_card_repository, mock_dependencies, sample_deck, sample_creature_card
    ):
        """Test _search_candidates excludes cards already in deck."""
        # Return the creature card that's already in the deck
        mock_result = MagicMock()
        mock_result.items = [sample_creature_card]
        mock_card_repository.search_advanced = AsyncMock(return_value=mock_result)

        analysis = DeckAnalysis(
            primary_synergy="Test",
            search_criteria=[
                DeckNeedAnalysis(need_type="creature", description="need creatures"),
                DeckNeedAnalysis(need_type="removal", description="need removal"),
                DeckNeedAnalysis(need_type="card_draw", description="need draw"),
            ],
            reasoning="Test reasoning",
        )

        result = await _search_candidates(
            analysis=analysis,
            card_repo=mock_card_repository,
            deps=mock_dependencies,
            deck=sample_deck,
        )

        # sample_creature_card is in sample_deck, so should be excluded
        assert sample_creature_card.id not in [c.id for c in result]

    @pytest.mark.asyncio
    async def test_applies_color_identity_filter(
        self, mock_card_repository, mock_dependencies, sample_deck
    ):
        """Test _search_candidates passes color identity to search."""
        mock_result = MagicMock()
        mock_result.items = []
        mock_card_repository.search_advanced = AsyncMock(return_value=mock_result)

        analysis = DeckAnalysis(
            primary_synergy="Test",
            search_criteria=[
                DeckNeedAnalysis(need_type="creature", description="need creatures"),
                DeckNeedAnalysis(need_type="removal", description="need removal"),
                DeckNeedAnalysis(need_type="card_draw", description="need draw"),
            ],
            reasoning="Test reasoning",
        )

        await _search_candidates(
            analysis=analysis,
            card_repo=mock_card_repository,
            deps=mock_dependencies,
            deck=sample_deck,
        )

        # Check that color filter was passed correctly
        call_args = mock_card_repository.search_advanced.call_args_list[0]
        assert call_args.kwargs.get("colors") == ["R"]
        assert call_args.kwargs.get("color_mode") == "at_most"

    @pytest.mark.asyncio
    async def test_passes_types_as_list(self, mock_card_repository, mock_dependencies, sample_deck):
        """Test _search_candidates passes types as list, not string."""
        mock_result = MagicMock()
        mock_result.items = []
        mock_card_repository.search_advanced = AsyncMock(return_value=mock_result)

        analysis = DeckAnalysis(
            primary_synergy="Test",
            search_criteria=[
                DeckNeedAnalysis(
                    need_type="creature",
                    description="need creatures",
                    search_types=["Creature", "Goblin"],
                ),
                DeckNeedAnalysis(need_type="removal", description="need removal"),
                DeckNeedAnalysis(need_type="card_draw", description="need draw"),
            ],
            reasoning="Test reasoning",
        )

        await _search_candidates(
            analysis=analysis,
            card_repo=mock_card_repository,
            deps=mock_dependencies,
            deck=sample_deck,
        )

        # Check that types was passed as list (not string)
        call_args = mock_card_repository.search_advanced.call_args_list[0]
        types_arg = call_args.kwargs.get("types")
        assert isinstance(types_arg, list), f"Expected list, got {type(types_arg)}"
        assert types_arg == ["Creature", "Goblin"]

    @pytest.mark.asyncio
    async def test_passes_keywords_as_list(
        self, mock_card_repository, mock_dependencies, sample_deck
    ):
        """Test _search_candidates passes keywords as list, not string."""
        mock_result = MagicMock()
        mock_result.items = []
        mock_card_repository.search_advanced = AsyncMock(return_value=mock_result)

        analysis = DeckAnalysis(
            primary_synergy="Test",
            search_criteria=[
                DeckNeedAnalysis(
                    need_type="creature",
                    description="need creatures",
                    search_keywords=["haste", "trample"],
                ),
                DeckNeedAnalysis(need_type="removal", description="need removal"),
                DeckNeedAnalysis(need_type="card_draw", description="need draw"),
            ],
            reasoning="Test reasoning",
        )

        await _search_candidates(
            analysis=analysis,
            card_repo=mock_card_repository,
            deps=mock_dependencies,
            deck=sample_deck,
        )

        # Check that keywords was passed as list (not string)
        call_args = mock_card_repository.search_advanced.call_args_list[0]
        keywords_arg = call_args.kwargs.get("keywords")
        assert isinstance(keywords_arg, list), f"Expected list, got {type(keywords_arg)}"
        assert keywords_arg == ["haste", "trample"]

    @pytest.mark.asyncio
    async def test_handles_search_exceptions(
        self, mock_card_repository, mock_dependencies, sample_deck
    ):
        """Test _search_candidates handles individual search failures gracefully."""
        # First search succeeds, second fails, third succeeds
        good_card = Card(
            id="good-card",
            name="Good Card",
            oracle_id="oracle-good",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Instant",
            oracle_text="Test",
            rarity="common",
            set_code="test",
            set_name="Test",
            collector_number="1",
            colors=["R"],
            color_identity=["R"],
            legalities={},
        )
        mock_result = MagicMock()
        mock_result.items = [good_card]

        # Simulate one search failing
        mock_card_repository.search_advanced = AsyncMock(
            side_effect=[mock_result, Exception("Search failed"), mock_result]
        )

        analysis = DeckAnalysis(
            primary_synergy="Test",
            search_criteria=[
                DeckNeedAnalysis(need_type="creature", description="need creatures"),
                DeckNeedAnalysis(need_type="removal", description="need removal"),
                DeckNeedAnalysis(need_type="card_draw", description="need draw"),
            ],
            reasoning="Test reasoning",
        )

        # Should not raise, should return results from successful searches
        result = await _search_candidates(
            analysis=analysis,
            card_repo=mock_card_repository,
            deps=mock_dependencies,
            deck=sample_deck,
        )

        # Should have the card from successful searches (deduplicated)
        assert len(result) == 1
        assert result[0].name == "Good Card"


class TestFormatSuggestionsOutput:
    """Tests for _format_suggestions_output helper function."""

    def test_formats_suggestions_with_cards(self, sample_card, sample_creature_card):
        """Test _format_suggestions_output formats suggestions correctly."""
        suggestions = CardSuggestions(
            top_picks=[
                CuratedCard(
                    card_name="Goblin Guide",
                    synergy_fit="Great for aggro strategy",
                    priority=1,
                ),
                CuratedCard(
                    card_name="Lightning Dragon",
                    synergy_fit="Finisher for the deck",
                    priority=2,
                ),
                CuratedCard(card_name="Card 3", synergy_fit="Fit 3", priority=3),
                CuratedCard(card_name="Card 4", synergy_fit="Fit 4", priority=4),
                CuratedCard(card_name="Card 5", synergy_fit="Fit 5", priority=5),
            ],
            overall_strategy="Strengthen the aggro theme",
        )
        candidate_map = {
            "Goblin Guide": sample_card,
            "Lightning Dragon": sample_creature_card,
        }

        result = _format_suggestions_output(suggestions, candidate_map)

        # Should contain section header
        assert "## Card Suggestions for Your Deck" in result

        # Should contain card names
        assert "Goblin Guide" in result
        assert "Lightning Dragon" in result

        # Should contain synergy explanations
        assert "Great for aggro strategy" in result
        assert "Finisher for the deck" in result

        # Should contain overall strategy
        assert "Strengthen the aggro theme" in result

    def test_priority_stars_inverted(self, sample_card):
        """Test that priority 1 shows 5 stars and priority 5 shows 1 star."""
        suggestions = CardSuggestions(
            top_picks=[
                CuratedCard(
                    card_name="Goblin Guide",
                    synergy_fit="High priority",
                    priority=1,  # Highest priority
                ),
                CuratedCard(card_name="Card 2", synergy_fit="Fit 2", priority=2),
                CuratedCard(card_name="Card 3", synergy_fit="Fit 3", priority=3),
                CuratedCard(card_name="Card 4", synergy_fit="Fit 4", priority=4),
                CuratedCard(
                    card_name="Card 5",
                    synergy_fit="Low priority",
                    priority=5,  # Lowest priority
                ),
            ],
            overall_strategy="Test strategy",
        )
        candidate_map = {"Goblin Guide": sample_card}

        result = _format_suggestions_output(suggestions, candidate_map)

        # Priority 1 should show 5 stars (6 - 1 = 5)
        assert "⭐⭐⭐⭐⭐" in result

        # Priority 5 should show 1 star (6 - 5 = 1)
        # Find the line with Card 5 and check it has only 1 star
        lines = result.split("\n")
        card5_line = [line for line in lines if "Card 5" in line][0]
        # Count stars in that specific line
        star_count = card5_line.count("⭐")
        assert star_count == 1, f"Expected 1 star for priority 5, got {star_count}"

    def test_handles_missing_cards_in_map(self):
        """Test _format_suggestions_output handles cards not in candidate map."""
        suggestions = CardSuggestions(
            top_picks=[
                CuratedCard(
                    card_name="Missing Card",
                    synergy_fit="Test fit",
                    priority=1,
                ),
                CuratedCard(card_name="Card 2", synergy_fit="Fit 2", priority=2),
                CuratedCard(card_name="Card 3", synergy_fit="Fit 3", priority=3),
                CuratedCard(card_name="Card 4", synergy_fit="Fit 4", priority=4),
                CuratedCard(card_name="Card 5", synergy_fit="Fit 5", priority=5),
            ],
            overall_strategy="Test strategy",
        )
        candidate_map = {}  # Empty map

        result = _format_suggestions_output(suggestions, candidate_map)

        # Should still include card name (fallback path)
        assert "Missing Card" in result
        assert "Test fit" in result


# Tests for Main Tool Function


class TestSuggestSynergyCardsUserRequest:
    """Tests for the user_request parameter in suggest_synergy_cards."""

    @pytest.fixture
    def larger_deck(self) -> Deck:
        """Create a deck with 6 unique cards (more than minimum 5)."""
        cards = [
            Card(
                id=f"card-{i}",
                name=f"Test Card {i}",
                oracle_id=f"oracle-{i}",
                mana_cost="{R}",
                cmc=float(i),
                type_line="Instant",
                oracle_text="Test",
                rarity="common",
                set_code="test",
                set_name="Test",
                collector_number=str(i),
                colors=["R"],
                color_identity=["R"],
                legalities={},
            )
            for i in range(1, 7)
        ]
        deck_cards = [
            DeckCard(
                deck_id="test-deck",
                card_id=card.id,
                quantity=1,
                sideboard=False,
                card=card,
            )
            for card in cards
        ]
        return Deck(
            id="test-deck",
            name="Test Deck",
            format="standard",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            deck_cards=deck_cards,
            color_identity=["R"],
        )

    @pytest.mark.asyncio
    async def test_user_request_none_does_not_modify_prompt(self, mock_run_context, larger_deck):
        """Test user_request=None excludes USER REQUEST section from prompt (AC1)."""
        mock_run_context.deps.active_deck = larger_deck

        # Mock the agents to capture the prompts
        mock_analysis_result = MagicMock()
        mock_analysis_result.output = DeckAnalysis(
            primary_synergy="Test synergy",
            search_criteria=[
                DeckNeedAnalysis(need_type="creature", description="need creatures"),
                DeckNeedAnalysis(need_type="removal", description="need removal"),
                DeckNeedAnalysis(need_type="card_draw", description="need draw"),
            ],
            reasoning="Test reasoning",
        )
        mock_analysis_agent = MagicMock()
        mock_analysis_agent.run = AsyncMock(return_value=mock_analysis_result)

        mock_curation_result = MagicMock()
        mock_curation_result.output = CardSuggestions(
            top_picks=[
                CuratedCard(card_name=f"Card {i}", synergy_fit=f"Fit {i}", priority=i)
                for i in range(1, 6)
            ],
            overall_strategy="Test strategy",
        )
        mock_curation_agent = MagicMock()
        mock_curation_agent.run = AsyncMock(return_value=mock_curation_result)

        # Mock search to return some candidates
        mock_result = MagicMock()
        mock_result.items = [
            Card(
                id=f"candidate-{i}",
                name=f"Card {i}",
                oracle_id=f"oracle-candidate-{i}",
                mana_cost="{R}",
                cmc=float(i),
                type_line="Instant",
                oracle_text="Test",
                rarity="common",
                set_code="test",
                set_name="Test",
                collector_number=str(i),
                colors=["R"],
                color_identity=["R"],
                legalities={},
            )
            for i in range(1, 6)
        ]
        mock_run_context.deps.card_repository.search_advanced = AsyncMock(return_value=mock_result)

        with patch(
            "src.agent.tools.synergy_suggestions._create_suggestion_agents",
            return_value=(mock_analysis_agent, mock_curation_agent),
        ):
            await suggest_synergy_cards(mock_run_context, user_request=None)

        # Verify analysis prompt does NOT contain USER REQUEST
        analysis_call_args = mock_analysis_agent.run.call_args
        analysis_prompt = analysis_call_args[0][0]
        assert "USER REQUEST" not in analysis_prompt

        # Verify curation prompt does NOT contain USER PRIORITY
        curation_call_args = mock_curation_agent.run.call_args
        curation_prompt = curation_call_args[0][0]
        assert "USER PRIORITY" not in curation_prompt

    @pytest.mark.asyncio
    async def test_user_request_provided_modifies_both_prompts(self, mock_run_context, larger_deck):
        """Test user_request is passed to both analysis and curation prompts (AC3)."""
        mock_run_context.deps.active_deck = larger_deck

        # Mock the agents to capture the prompts
        mock_analysis_result = MagicMock()
        mock_analysis_result.output = DeckAnalysis(
            primary_synergy="Test synergy",
            search_criteria=[
                DeckNeedAnalysis(need_type="removal", description="need removal"),
                DeckNeedAnalysis(need_type="removal", description="more removal"),
                DeckNeedAnalysis(need_type="removal", description="even more removal"),
            ],
            reasoning="Test reasoning",
        )
        mock_analysis_agent = MagicMock()
        mock_analysis_agent.run = AsyncMock(return_value=mock_analysis_result)

        mock_curation_result = MagicMock()
        mock_curation_result.output = CardSuggestions(
            top_picks=[
                CuratedCard(card_name=f"Card {i}", synergy_fit=f"Removal fit {i}", priority=i)
                for i in range(1, 6)
            ],
            overall_strategy="Removal strategy",
        )
        mock_curation_agent = MagicMock()
        mock_curation_agent.run = AsyncMock(return_value=mock_curation_result)

        # Mock search to return some candidates
        mock_result = MagicMock()
        mock_result.items = [
            Card(
                id=f"candidate-{i}",
                name=f"Card {i}",
                oracle_id=f"oracle-candidate-{i}",
                mana_cost="{R}",
                cmc=float(i),
                type_line="Instant",
                oracle_text="Destroy target creature",
                rarity="common",
                set_code="test",
                set_name="Test",
                collector_number=str(i),
                colors=["R"],
                color_identity=["R"],
                legalities={},
            )
            for i in range(1, 6)
        ]
        mock_run_context.deps.card_repository.search_advanced = AsyncMock(return_value=mock_result)

        with patch(
            "src.agent.tools.synergy_suggestions._create_suggestion_agents",
            return_value=(mock_analysis_agent, mock_curation_agent),
        ):
            await suggest_synergy_cards(mock_run_context, user_request="removal")

        # Verify analysis prompt contains USER REQUEST with the user's request
        analysis_call_args = mock_analysis_agent.run.call_args
        analysis_prompt = analysis_call_args[0][0]
        assert "USER REQUEST: removal" in analysis_prompt
        assert "Focus your search criteria" in analysis_prompt

        # Verify curation prompt contains USER PRIORITY with the user's request
        curation_call_args = mock_curation_agent.run.call_args
        curation_prompt = curation_call_args[0][0]
        assert "USER PRIORITY: removal" in curation_prompt
        assert "prioritize cards that best address" in curation_prompt

    @pytest.mark.asyncio
    async def test_empty_string_user_request_treated_as_none(self, mock_run_context, larger_deck):
        """Test empty string user_request is normalized to None (AC5)."""
        mock_run_context.deps.active_deck = larger_deck

        # Mock the agents to capture the prompts
        mock_analysis_result = MagicMock()
        mock_analysis_result.output = DeckAnalysis(
            primary_synergy="Test synergy",
            search_criteria=[
                DeckNeedAnalysis(need_type="creature", description="need creatures"),
                DeckNeedAnalysis(need_type="removal", description="need removal"),
                DeckNeedAnalysis(need_type="card_draw", description="need draw"),
            ],
            reasoning="Test reasoning",
        )
        mock_analysis_agent = MagicMock()
        mock_analysis_agent.run = AsyncMock(return_value=mock_analysis_result)

        mock_curation_result = MagicMock()
        mock_curation_result.output = CardSuggestions(
            top_picks=[
                CuratedCard(card_name=f"Card {i}", synergy_fit=f"Fit {i}", priority=i)
                for i in range(1, 6)
            ],
            overall_strategy="Test strategy",
        )
        mock_curation_agent = MagicMock()
        mock_curation_agent.run = AsyncMock(return_value=mock_curation_result)

        # Mock search to return some candidates
        mock_result = MagicMock()
        mock_result.items = [
            Card(
                id=f"candidate-{i}",
                name=f"Card {i}",
                oracle_id=f"oracle-candidate-{i}",
                mana_cost="{R}",
                cmc=float(i),
                type_line="Instant",
                oracle_text="Test",
                rarity="common",
                set_code="test",
                set_name="Test",
                collector_number=str(i),
                colors=["R"],
                color_identity=["R"],
                legalities={},
            )
            for i in range(1, 6)
        ]
        mock_run_context.deps.card_repository.search_advanced = AsyncMock(return_value=mock_result)

        with patch(
            "src.agent.tools.synergy_suggestions._create_suggestion_agents",
            return_value=(mock_analysis_agent, mock_curation_agent),
        ):
            # Test with empty string
            await suggest_synergy_cards(mock_run_context, user_request="")

        # Verify prompts do NOT contain USER REQUEST/PRIORITY (empty string treated as None)
        analysis_call_args = mock_analysis_agent.run.call_args
        analysis_prompt = analysis_call_args[0][0]
        assert "USER REQUEST" not in analysis_prompt

        curation_call_args = mock_curation_agent.run.call_args
        curation_prompt = curation_call_args[0][0]
        assert "USER PRIORITY" not in curation_prompt

    @pytest.mark.asyncio
    async def test_whitespace_only_user_request_treated_as_none(
        self, mock_run_context, larger_deck
    ):
        """Test whitespace-only user_request is normalized to None (AC5)."""
        mock_run_context.deps.active_deck = larger_deck

        # Mock the agents to capture the prompts
        mock_analysis_result = MagicMock()
        mock_analysis_result.output = DeckAnalysis(
            primary_synergy="Test synergy",
            search_criteria=[
                DeckNeedAnalysis(need_type="creature", description="need creatures"),
                DeckNeedAnalysis(need_type="removal", description="need removal"),
                DeckNeedAnalysis(need_type="card_draw", description="need draw"),
            ],
            reasoning="Test reasoning",
        )
        mock_analysis_agent = MagicMock()
        mock_analysis_agent.run = AsyncMock(return_value=mock_analysis_result)

        mock_curation_result = MagicMock()
        mock_curation_result.output = CardSuggestions(
            top_picks=[
                CuratedCard(card_name=f"Card {i}", synergy_fit=f"Fit {i}", priority=i)
                for i in range(1, 6)
            ],
            overall_strategy="Test strategy",
        )
        mock_curation_agent = MagicMock()
        mock_curation_agent.run = AsyncMock(return_value=mock_curation_result)

        # Mock search to return some candidates
        mock_result = MagicMock()
        mock_result.items = [
            Card(
                id=f"candidate-{i}",
                name=f"Card {i}",
                oracle_id=f"oracle-candidate-{i}",
                mana_cost="{R}",
                cmc=float(i),
                type_line="Instant",
                oracle_text="Test",
                rarity="common",
                set_code="test",
                set_name="Test",
                collector_number=str(i),
                colors=["R"],
                color_identity=["R"],
                legalities={},
            )
            for i in range(1, 6)
        ]
        mock_run_context.deps.card_repository.search_advanced = AsyncMock(return_value=mock_result)

        with patch(
            "src.agent.tools.synergy_suggestions._create_suggestion_agents",
            return_value=(mock_analysis_agent, mock_curation_agent),
        ):
            # Test with whitespace only
            await suggest_synergy_cards(mock_run_context, user_request="   ")

        # Verify prompts do NOT contain USER REQUEST/PRIORITY
        analysis_call_args = mock_analysis_agent.run.call_args
        analysis_prompt = analysis_call_args[0][0]
        assert "USER REQUEST" not in analysis_prompt

        curation_call_args = mock_curation_agent.run.call_args
        curation_prompt = curation_call_args[0][0]
        assert "USER PRIORITY" not in curation_prompt


class TestSuggestSynergyCards:
    """Tests for the suggest_synergy_cards tool."""

    @pytest.mark.asyncio
    async def test_returns_error_when_no_active_deck(self, mock_run_context):
        """Test returns error message when no active deck."""
        mock_run_context.deps.active_deck = None

        result = await suggest_synergy_cards(mock_run_context)

        assert isinstance(result, str)
        assert "No active deck" in result

    @pytest.mark.asyncio
    async def test_returns_error_for_empty_deck(self, mock_run_context, empty_deck):
        """Test returns error message for empty deck."""
        mock_run_context.deps.active_deck = empty_deck

        result = await suggest_synergy_cards(mock_run_context)

        assert isinstance(result, str)
        assert "empty" in result.lower()

    @pytest.mark.asyncio
    async def test_returns_error_for_small_deck(self, mock_run_context):
        """Test returns error message when deck has < 5 cards."""
        small_deck = Deck(
            id="small-deck-id",
            name="Small Deck",
            format="standard",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            deck_cards=[
                DeckCard(
                    deck_id="small-deck-id",
                    card_id="card-1",
                    quantity=1,
                    sideboard=False,
                    card=Card(
                        id="card-1",
                        name="Test Card",
                        oracle_id="oracle-1",
                        mana_cost="{R}",
                        cmc=1.0,
                        type_line="Instant",
                        oracle_text="Test",
                        rarity="common",
                        set_code="test",
                        set_name="Test",
                        collector_number="1",
                        colors=["R"],
                        color_identity=["R"],
                        legalities={},
                    ),
                ),
            ],
        )
        mock_run_context.deps.active_deck = small_deck

        result = await suggest_synergy_cards(mock_run_context)

        assert isinstance(result, str)
        assert "at least 5" in result.lower() or "1 cards" in result

    @pytest.mark.asyncio
    async def test_handles_agent_errors_gracefully(self, mock_run_context):
        """Test gracefully handles errors during suggestion process."""
        # Create a deck with 6 unique cards (more than minimum 5)
        cards = [
            Card(
                id=f"card-{i}",
                name=f"Test Card {i}",
                oracle_id=f"oracle-{i}",
                mana_cost="{R}",
                cmc=float(i),
                type_line="Instant",
                oracle_text="Test",
                rarity="common",
                set_code="test",
                set_name="Test",
                collector_number=str(i),
                colors=["R"],
                color_identity=["R"],
                legalities={},
            )
            for i in range(1, 7)
        ]
        deck_cards = [
            DeckCard(
                deck_id="test-deck",
                card_id=card.id,
                quantity=1,
                sideboard=False,
                card=card,
            )
            for card in cards
        ]
        larger_deck = Deck(
            id="test-deck",
            name="Test Deck",
            format="standard",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            deck_cards=deck_cards,
            color_identity=["R"],
        )
        mock_run_context.deps.active_deck = larger_deck

        # Mock the agent creation to raise an error
        with patch(
            "src.agent.tools.synergy_suggestions._create_suggestion_agents",
            side_effect=Exception("Test error"),
        ):
            result = await suggest_synergy_cards(mock_run_context)

        assert isinstance(result, str)
        assert "Unable to generate suggestions" in result or "Test error" in result
