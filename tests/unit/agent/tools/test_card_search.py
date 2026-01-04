"""Unit tests for advanced card search tool."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import RunContext

from src.agent.dependencies import AgentDependencies
from src.agent.tools.card_search import (
    CardSearchFilters,
    _format_search_results_paginated,
    search_cards_advanced,
)
from src.data.schemas.card import Card
from src.data.schemas.pagination import PaginatedResult

# Fixtures


@pytest.fixture
def sample_creature() -> Card:
    """Create a sample creature card for testing."""
    return Card(
        id="goblin-001",
        name="Goblin Guide",
        oracle_id="oracle-goblin",
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
        keywords=["Haste"],
        card_faces=[
            {
                "name": "Goblin Guide",
                "power": "2",
                "toughness": "2",
            }
        ],
    )


@pytest.fixture
def sample_instant() -> Card:
    """Create a sample instant card for testing."""
    return Card(
        id="bolt-001",
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
def double_faced_creature() -> Card:
    """Create a double-faced creature card for testing."""
    return Card(
        id="delver-001",
        name="Delver of Secrets",
        oracle_id="oracle-delver",
        mana_cost="{U}",
        cmc=1.0,
        type_line="Creature — Human Wizard",
        oracle_text="At the beginning of your upkeep...",
        rarity="common",
        set_code="isd",
        set_name="Innistrad",
        collector_number="51",
        colors=["U"],
        color_identity=["U"],
        legalities={"standard": "not_legal", "modern": "legal"},
        card_faces=[
            {
                "name": "Delver of Secrets",
                "power": "1",
                "toughness": "1",
            },
            {
                "name": "Insectile Aberration",
                "power": "3",
                "toughness": "2",
            },
        ],
    )


@pytest.fixture
def mock_card_repository():
    """Create a mock CardRepository for testing."""
    repo = MagicMock()
    repo.search_advanced = AsyncMock()
    return repo


@pytest.fixture
def mock_dependencies(mock_card_repository, mock_session_manager):
    """Create mock AgentDependencies for testing."""
    mock_deck_repository = MagicMock()
    return AgentDependencies(
        card_repository=mock_card_repository,
        deck_repository=mock_deck_repository,
        session_id="test-session",
        _session_manager=mock_session_manager,
    )


@pytest.fixture
def mock_run_context(mock_dependencies):
    """Create a mock RunContext for testing."""
    ctx = MagicMock(spec=RunContext)
    ctx.deps = mock_dependencies
    return ctx


# Tests for CardSearchFilters


class TestCardSearchFilters:
    """Tests for the CardSearchFilters model."""

    def test_filters_all_fields(self):
        """Test creating filters with all fields populated."""
        filters = CardSearchFilters(
            colors=["R", "G"],
            types=["Creature", "Dragon"],
            keywords=["flying", "haste"],
            mana_value_min=2.0,
            mana_value_max=5.0,
            rarity=["rare", "mythic"],
            max_results=10,
        )

        assert filters.colors == ["R", "G"]
        assert filters.types == ["Creature", "Dragon"]
        assert filters.keywords == ["flying", "haste"]
        assert filters.mana_value_min == 2.0
        assert filters.mana_value_max == 5.0
        assert filters.rarity == ["rare", "mythic"]
        assert filters.max_results == 10

    def test_filters_defaults(self):
        """Test filters with default values."""
        filters = CardSearchFilters()

        assert filters.colors is None
        assert filters.types is None
        assert filters.keywords is None
        assert filters.mana_value_min is None
        assert filters.mana_value_max is None
        assert filters.rarity is None
        assert filters.max_results is None
        assert filters.page == 1
        assert filters.page_size == 20  # Default

    def test_filters_with_single_rarity(self):
        """Test creating filters with single rarity value."""
        filters = CardSearchFilters(rarity="rare")

        assert filters.rarity == "rare"

    def test_filters_with_multiple_rarities(self):
        """Test creating filters with multiple rarity values."""
        filters = CardSearchFilters(rarity=["rare", "mythic"])

        assert filters.rarity == ["rare", "mythic"]


# Tests for _format_search_results_paginated
# Note: Card list formatting is now tested in tests/unit/ui/test_formatters.py


class TestFormatSearchResults:
    """Tests for the _format_search_results_paginated helper function."""

    def test_format_empty_results(self):
        """Test formatting with no results provides suggestions."""
        filters = CardSearchFilters(colors=["R"], mana_value_max=1.0)
        paginated = PaginatedResult(items=[], total_count=0, page=1, page_size=20, total_pages=0)
        result = _format_search_results_paginated(paginated, filters)

        assert "couldn't find any cards" in result.lower()
        assert "try" in result.lower() or "relax" in result.lower()

    def test_format_single_result(self, sample_creature):
        """Test formatting a single result."""
        filters = CardSearchFilters(colors=["R"])
        paginated = PaginatedResult(
            items=[sample_creature], total_count=1, page=1, page_size=20, total_pages=1
        )
        result = _format_search_results_paginated(paginated, filters)

        assert "Found 1 card" in result
        assert "Goblin Guide" in result
        assert "1." in result  # Numbered list

    def test_format_multiple_results(self, sample_creature, sample_instant):
        """Test formatting multiple results."""
        cards = [sample_creature, sample_instant]
        filters = CardSearchFilters(colors=["R"])
        paginated = PaginatedResult(items=cards, total_count=2, page=1, page_size=20, total_pages=1)
        result = _format_search_results_paginated(paginated, filters)

        assert "Found 2 cards" in result
        assert "Goblin Guide" in result
        assert "Lightning Bolt" in result
        assert "1." in result
        assert "2." in result

    def test_format_paginated_results(self, sample_creature):
        """Test formatting with pagination (page 1 of 3)."""
        cards = [sample_creature] * 20
        filters = CardSearchFilters(page=1, page_size=20)
        paginated = PaginatedResult(
            items=cards, total_count=52, page=1, page_size=20, total_pages=3
        )
        result = _format_search_results_paginated(paginated, filters)

        assert "Found 52 cards" in result
        assert "Page 1 of 3" in result
        assert "showing 1-20" in result
        assert "32 more results" in result
        assert "next page" in result.lower() or "show me more" in result.lower()

    def test_format_with_filter_summary(self, sample_creature):
        """Test that filter summary is included for complex searches."""
        cards = [sample_creature] * 6  # More than 5 to trigger summary
        filters = CardSearchFilters(
            colors=["R"],
            types=["Creature"],
            keywords=["haste"],
            mana_value_max=3.0,
        )
        paginated = PaginatedResult(items=cards, total_count=6, page=1, page_size=20, total_pages=1)
        result = _format_search_results_paginated(paginated, filters)

        assert "Filters:" in result
        assert "red" in result.lower()
        assert "creature" in result.lower()
        assert "haste" in result


# Tests for search_cards_advanced


class TestSearchCardsAdvanced:
    """Tests for the search_cards_advanced tool."""

    @pytest.mark.asyncio
    async def test_search_with_color_filter(self, mock_run_context, sample_creature):
        """Test search with color filter only."""
        mock_run_context.deps.card_repository.search_advanced.return_value = PaginatedResult(
            items=[sample_creature], total_count=1, page=1, page_size=20, total_pages=1
        )

        filters = CardSearchFilters(colors=["R"])
        result = await search_cards_advanced(mock_run_context, filters)

        # Verify repository was called correctly
        mock_run_context.deps.card_repository.search_advanced.assert_called_once_with(
            colors=["R"],
            types=None,
            keywords=None,
            mana_value_min=None,
            mana_value_max=None,
            rarity=None,
            oracle_text_phrases=None,
            page=1,
            page_size=20,
            format_filter=mock_run_context.deps.format_filter,
            color_mode="any",
        )

        assert "Found 1 card" in result
        assert "Goblin Guide" in result

    @pytest.mark.asyncio
    async def test_search_with_all_filters(self, mock_run_context, sample_creature, sample_instant):
        """Test search with all filter types."""
        cards = [sample_creature, sample_instant]
        mock_run_context.deps.card_repository.search_advanced.return_value = PaginatedResult(
            items=cards, total_count=len(cards), page=1, page_size=20, total_pages=1
        )

        filters = CardSearchFilters(
            colors=["R"],
            types=["Creature"],
            keywords=["haste"],
            mana_value_min=1.0,
            mana_value_max=3.0,
            max_results=10,
        )
        result = await search_cards_advanced(mock_run_context, filters)

        # Verify all filters passed to repository
        mock_run_context.deps.card_repository.search_advanced.assert_called_once()
        call_kwargs = mock_run_context.deps.card_repository.search_advanced.call_args.kwargs
        assert call_kwargs["colors"] == ["R"]
        assert call_kwargs["types"] == ["Creature"]
        assert call_kwargs["keywords"] == ["haste"]
        assert call_kwargs["mana_value_min"] == 1.0
        assert call_kwargs["mana_value_max"] == 3.0
        assert call_kwargs["page"] == 1
        assert call_kwargs["page_size"] == 10

        assert "Found 2 cards" in result

    @pytest.mark.asyncio
    async def test_search_no_results(self, mock_run_context):
        """Test search that returns no results provides suggestions."""
        mock_run_context.deps.card_repository.search_advanced.return_value = PaginatedResult(
            items=[], total_count=0, page=1, page_size=20, total_pages=0
        )

        filters = CardSearchFilters(
            colors=["B"],
            types=["Creature"],
            mana_value_max=1.0,
        )
        result = await search_cards_advanced(mock_run_context, filters)

        assert "couldn't find" in result.lower()
        assert "try" in result.lower() or "relax" in result.lower()

    @pytest.mark.asyncio
    async def test_search_respects_max_results(self, mock_run_context, sample_creature):
        """Test that max_results limits the output correctly."""
        # Create 25 cards (more than default limit of 20)
        many_cards = [sample_creature] * 25
        mock_run_context.deps.card_repository.search_advanced.return_value = PaginatedResult(
            items=many_cards[:20], total_count=25, page=1, page_size=20, total_pages=2
        )

        filters = CardSearchFilters(max_results=20)
        result = await search_cards_advanced(mock_run_context, filters)

        # Should show 20 cards with note about more results
        assert "Found 25 cards" in result
        assert "showing 1-20" in result
        assert "5 more results" or "next page" or "show me more" in result

    @pytest.mark.asyncio
    async def test_search_handles_double_faced_cards(self, mock_run_context, double_faced_creature):
        """Test that double-faced cards are formatted correctly."""
        mock_run_context.deps.card_repository.search_advanced.return_value = PaginatedResult(
            items=[double_faced_creature], total_count=1, page=1, page_size=20, total_pages=1
        )

        filters = CardSearchFilters(colors=["U"])
        result = await search_cards_advanced(mock_run_context, filters)

        # New HTML format uses <strong> instead of **
        assert "Delver of Secrets" in result
        assert "*Creature" in result or "Creature" in result

    @pytest.mark.asyncio
    async def test_search_with_custom_max_results(self, mock_run_context, sample_creature):
        """Test search with custom max_results value (deprecated, now uses page_size)."""
        cards = [sample_creature] * 3
        mock_run_context.deps.card_repository.search_advanced.return_value = PaginatedResult(
            items=cards, total_count=len(cards), page=1, page_size=20, total_pages=1
        )

        filters = CardSearchFilters(max_results=5)
        result = await search_cards_advanced(mock_run_context, filters)

        # Verify page_size passed correctly (max_results is deprecated but still works)
        call_kwargs = mock_run_context.deps.card_repository.search_advanced.call_args.kwargs
        assert call_kwargs["page_size"] == 5
        assert call_kwargs["page"] == 1

        assert "Found 3 cards" in result

    @pytest.mark.asyncio
    async def test_search_empty_filters(self, mock_run_context, sample_creature):
        """Test search with no filters returns all cards (limited)."""
        cards = [sample_creature] * 5
        mock_run_context.deps.card_repository.search_advanced.return_value = PaginatedResult(
            items=cards, total_count=len(cards), page=1, page_size=20, total_pages=1
        )

        filters = CardSearchFilters()  # All defaults
        result = await search_cards_advanced(mock_run_context, filters)

        # Verify all filter parameters are None
        call_kwargs = mock_run_context.deps.card_repository.search_advanced.call_args.kwargs
        assert call_kwargs["colors"] is None
        assert call_kwargs["types"] is None
        assert call_kwargs["keywords"] is None
        assert call_kwargs["mana_value_min"] is None
        assert call_kwargs["mana_value_max"] is None
        assert call_kwargs["rarity"] is None

        assert "Found 5 cards" in result

    @pytest.mark.asyncio
    async def test_search_with_single_rarity(self, mock_run_context, sample_creature):
        """Test search with single rarity filter."""
        mock_run_context.deps.card_repository.search_advanced.return_value = PaginatedResult(
            items=[sample_creature], total_count=1, page=1, page_size=20, total_pages=1
        )

        filters = CardSearchFilters(rarity="rare")
        result = await search_cards_advanced(mock_run_context, filters)

        # Verify repository was called with rarity parameter
        call_kwargs = mock_run_context.deps.card_repository.search_advanced.call_args.kwargs
        assert call_kwargs["rarity"] == "rare"

        assert "Found 1 card" in result
        assert "Goblin Guide" in result

    @pytest.mark.asyncio
    async def test_search_with_multiple_rarities(
        self, mock_run_context, sample_creature, sample_instant
    ):
        """Test search with multiple rarity values (OR logic)."""
        cards = [sample_creature, sample_instant]
        mock_run_context.deps.card_repository.search_advanced.return_value = PaginatedResult(
            items=cards, total_count=len(cards), page=1, page_size=20, total_pages=1
        )

        filters = CardSearchFilters(rarity=["rare", "common"])
        result = await search_cards_advanced(mock_run_context, filters)

        # Verify repository was called with list of rarities
        call_kwargs = mock_run_context.deps.card_repository.search_advanced.call_args.kwargs
        assert call_kwargs["rarity"] == ["rare", "common"]

        assert "Found 2 cards" in result

    @pytest.mark.asyncio
    async def test_search_rarity_with_other_filters(self, mock_run_context, sample_creature):
        """Test search combining rarity with other filters."""
        mock_run_context.deps.card_repository.search_advanced.return_value = PaginatedResult(
            items=[sample_creature], total_count=1, page=1, page_size=20, total_pages=1
        )

        filters = CardSearchFilters(
            colors=["R"],
            types=["Creature"],
            rarity="rare",
        )
        result = await search_cards_advanced(mock_run_context, filters)

        # Verify all filters passed to repository
        call_kwargs = mock_run_context.deps.card_repository.search_advanced.call_args.kwargs
        assert call_kwargs["colors"] == ["R"]
        assert call_kwargs["types"] == ["Creature"]
        assert call_kwargs["rarity"] == "rare"

        assert "Found 1 card" in result

    @pytest.mark.asyncio
    async def test_format_with_rarity_filter_summary(self, mock_run_context, sample_creature):
        """Test that rarity appears in filter summary."""
        cards = [sample_creature] * 6  # More than 5 to trigger summary
        mock_run_context.deps.card_repository.search_advanced.return_value = PaginatedResult(
            items=cards, total_count=len(cards), page=1, page_size=20, total_pages=1
        )

        filters = CardSearchFilters(
            colors=["R"],
            types=["Creature"],
            rarity="rare",
        )
        result = await search_cards_advanced(mock_run_context, filters)

        # Filter summary should include rarity
        assert "Filters:" in result
        assert "rare rarity" in result.lower()
