"""Unit tests for format filtering in CardRepository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.data.models.base import Base
from src.data.repositories.card import CardRepository
from tests.fixtures.card_data import create_sample_cards, create_standard_legal_cards


@pytest.fixture
async def async_engine():
    """Create an in-memory SQLite async engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine) -> AsyncSession:
    """Create an async session for testing."""
    async_session_maker = sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture
async def mixed_format_session(async_session: AsyncSession) -> AsyncSession:
    """Create a session with both Standard-legal and non-legal cards."""
    # Add non-Standard cards
    sample_cards = create_sample_cards()
    async_session.add_all(sample_cards)

    # Add Standard-legal cards
    standard_cards = create_standard_legal_cards()
    async_session.add_all(standard_cards)

    await async_session.commit()

    return async_session


@pytest.fixture
def mixed_format_repo(mixed_format_session: AsyncSession) -> CardRepository:
    """Create a CardRepository with mixed format legality data."""
    return CardRepository(mixed_format_session)


class TestFormatFilteringExactName:
    """Tests for format filtering with find_by_name_exact."""

    async def test_exact_name_without_filter(self, mixed_format_repo: CardRepository) -> None:
        """Test exact name search without format filter returns any card."""
        # Lightning Bolt is not Standard-legal
        card = await mixed_format_repo.find_by_name_exact("Lightning Bolt")

        assert card is not None
        assert card.name == "Lightning Bolt"
        assert card.legalities["standard"] == "not_legal"

    async def test_exact_name_with_standard_filter_finds_legal_card(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test exact name search with Standard filter finds Standard-legal card."""
        # Play with Fire is Standard-legal
        card = await mixed_format_repo.find_by_name_exact(
            "Play with Fire", format_filter="standard"
        )

        assert card is not None
        assert card.name == "Play with Fire"
        assert card.legalities["standard"] == "legal"

    async def test_exact_name_with_standard_filter_excludes_illegal_card(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test exact name search with Standard filter excludes non-legal cards."""
        # Lightning Bolt is not Standard-legal
        card = await mixed_format_repo.find_by_name_exact(
            "Lightning Bolt", format_filter="standard"
        )

        assert card is None

    async def test_exact_name_with_none_filter_finds_any_card(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test explicit None filter behaves same as no filter."""
        # Lightning Bolt is not Standard-legal
        card = await mixed_format_repo.find_by_name_exact("Lightning Bolt", format_filter=None)

        assert card is not None
        assert card.name == "Lightning Bolt"


class TestFormatFilteringPartialName:
    """Tests for format filtering with find_by_name_partial."""

    async def test_partial_name_without_filter(self, mixed_format_repo: CardRepository) -> None:
        """Test partial name search without filter returns all matching cards."""
        cards = await mixed_format_repo.find_by_name_partial("Fire")

        # Should include both "Lightning" cards (non-Standard) and "Play with Fire" (Standard)
        assert len(cards) >= 1
        card_names = {card.name for card in cards}
        assert "Play with Fire" in card_names

    async def test_partial_name_with_standard_filter(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test partial name search with Standard filter only returns legal cards."""
        cards = await mixed_format_repo.find_by_name_partial("Fire", format_filter="standard")

        assert len(cards) >= 1
        card_names = {card.name for card in cards}
        assert "Play with Fire" in card_names

        # Verify all returned cards are Standard-legal
        for card in cards:
            assert card.legalities["standard"] == "legal"

    async def test_partial_name_filter_excludes_illegal_cards(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test format filter excludes non-Standard cards from partial search."""
        # Search for "Lightning" - most are not Standard-legal
        cards = await mixed_format_repo.find_by_name_partial("Lightning", format_filter="standard")

        # Should not include Lightning Bolt, Lightning Strike, etc.
        card_names = {card.name for card in cards}
        assert "Lightning Bolt" not in card_names
        assert "Lightning Strike" not in card_names


class TestFormatFilteringByColor:
    """Tests for format filtering with find_by_colors."""

    async def test_color_search_without_filter(self, mixed_format_repo: CardRepository) -> None:
        """Test color search without filter returns all matching cards."""
        red_cards = await mixed_format_repo.find_by_colors("R")

        # Should include both Standard and non-Standard red cards
        assert len(red_cards) >= 5
        card_names = {card.name for card in red_cards}
        assert "Lightning Bolt" in card_names  # not Standard
        assert "Play with Fire" in card_names  # Standard

    async def test_color_search_with_standard_filter(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test color search with Standard filter only returns legal cards."""
        red_cards = await mixed_format_repo.find_by_colors("R", format_filter="standard")

        # Should only include Standard-legal red cards
        assert len(red_cards) >= 1
        card_names = {card.name for card in red_cards}
        assert "Play with Fire" in card_names
        assert "Lightning Bolt" not in card_names

        # Verify all are Standard-legal
        for card in red_cards:
            assert card.legalities["standard"] == "legal"

    async def test_colorless_search_with_standard_filter(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test colorless search with Standard filter."""
        colorless = await mixed_format_repo.find_by_colors("", format_filter="standard")

        # Should only include Standard-legal colorless cards
        card_names = {card.name for card in colorless}
        assert "Meteorite" in card_names  # Standard-legal
        assert "Sol Ring" not in card_names  # not Standard-legal


class TestFormatFilteringByType:
    """Tests for format filtering with find_by_type."""

    async def test_type_search_without_filter(self, mixed_format_repo: CardRepository) -> None:
        """Test type search without filter returns all matching cards."""
        instants = await mixed_format_repo.find_by_type("Instant")

        # Should include both Standard and non-Standard instants
        assert len(instants) >= 5
        card_names = {card.name for card in instants}
        assert "Lightning Bolt" in card_names
        assert "Play with Fire" in card_names
        assert "Consider" in card_names

    async def test_type_search_with_standard_filter(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test type search with Standard filter only returns legal cards."""
        instants = await mixed_format_repo.find_by_type("Instant", format_filter="standard")

        # Should only include Standard-legal instants
        assert len(instants) >= 2
        card_names = {card.name for card in instants}
        assert "Play with Fire" in card_names
        assert "Consider" in card_names
        assert "Lightning Bolt" not in card_names

        # Verify all are Standard-legal
        for card in instants:
            assert card.legalities["standard"] == "legal"


class TestFormatFilteringAdvancedSearch:
    """Tests for format filtering with search_advanced."""

    async def test_advanced_search_without_filter(self, mixed_format_repo: CardRepository) -> None:
        """Test advanced search without filter returns all matching cards."""
        results = await mixed_format_repo.search_advanced(colors=["R"], types=["Instant"])

        # Should include both Standard and non-Standard red instants
        assert len(results.items) >= 3
        card_names = {card.name for card in results.items}
        assert "Lightning Bolt" in card_names
        assert "Play with Fire" in card_names

    async def test_advanced_search_with_standard_filter(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test advanced search with Standard filter only returns legal cards."""
        results = await mixed_format_repo.search_advanced(
            colors=["R"], types=["Instant"], format_filter="standard"
        )

        # Should only include Standard-legal red instants
        assert len(results.items) >= 1
        card_names = {card.name for card in results.items}
        assert "Play with Fire" in card_names
        assert "Lightning Bolt" not in card_names

        # Verify all are Standard-legal
        for card in results.items:
            assert card.legalities["standard"] == "legal"

    async def test_advanced_search_combined_filters(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test advanced search with format filter combined with other filters."""
        results = await mixed_format_repo.search_advanced(
            colors=["U"],
            types=["Instant"],
            mana_value_max=1.0,
            format_filter="standard",
        )

        # Should only include Standard-legal blue instants with CMC <= 1
        card_names = {card.name for card in results.items}
        assert "Consider" in card_names
        assert "Counterspell" not in card_names  # not Standard-legal

        # Verify all meet criteria
        for card in results.items:
            assert card.legalities["standard"] == "legal"
            assert "U" in card.colors
            assert "Instant" in card.type_line
            assert card.cmc <= 1.0

    async def test_advanced_search_no_results_with_filter(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test advanced search with format filter returns empty list when no matches."""
        # Search for black creatures in Standard (none exist in test data)
        results = await mixed_format_repo.search_advanced(
            colors=["B"], types=["Creature"], format_filter="standard"
        )

        assert results.items == []
        assert isinstance(results.items, list)


class TestFormatFilteringKeywordSearch:
    """Tests for format filtering with search_by_keywords."""

    async def test_keyword_search_without_filter(self, mixed_format_repo: CardRepository) -> None:
        """Test keyword search without filter returns all matching cards."""
        flying_cards = await mixed_format_repo.search_by_keywords("flying")

        # Should include both Standard and non-Standard cards with flying
        assert len(flying_cards) >= 3
        card_names = {card.name for card in flying_cards}
        assert "Fearless Fledgling" in card_names  # Standard
        # Non-Standard cards also included

    async def test_keyword_search_with_standard_filter(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test keyword search with Standard filter only returns legal cards."""
        flying_cards = await mixed_format_repo.search_by_keywords(
            "flying", format_filter="standard"
        )

        # Should only include Standard-legal cards with flying
        assert len(flying_cards) >= 1
        card_names = {card.name for card in flying_cards}
        assert "Fearless Fledgling" in card_names

        # Verify all are Standard-legal
        for card in flying_cards:
            assert card.legalities["standard"] == "legal"


class TestFormatFilteringEdgeCases:
    """Tests for edge cases in format filtering."""

    async def test_filter_with_missing_legalities(self, async_session: AsyncSession) -> None:
        """Test format filter handles cards with missing legalities gracefully."""
        from src.data.models.card import CardModel

        # Create card without legalities field
        card_no_legalities = CardModel(
            id="test-001",
            name="Test Card",
            oracle_id="oracle-test",
            mana_cost="{1}",
            cmc=1.0,
            type_line="Instant",
            oracle_text="Test",
            rarity="common",
            set_code="TST",
            set_name="Test Set",
            collector_number="001",
            colors=[],
            color_identity=[],
            color_indicator=None,
            keywords=None,
            legalities={},  # Empty legalities
            card_faces=None,
        )
        async_session.add(card_no_legalities)
        await async_session.commit()

        repo = CardRepository(async_session)

        # Should not find card with Standard filter (missing legality = not legal)
        card = await repo.find_by_name_exact("Test Card", format_filter="standard")
        assert card is None

        # Should find card without filter
        card = await repo.find_by_name_exact("Test Card")
        assert card is not None

    async def test_none_format_filter_same_as_no_filter(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test that None format_filter behaves identically to omitting the parameter."""
        # Without filter
        cards_no_filter = await mixed_format_repo.find_by_name_partial("Lightning")

        # With None filter
        cards_none_filter = await mixed_format_repo.find_by_name_partial(
            "Lightning", format_filter=None
        )

        # Should return same results
        assert len(cards_no_filter) == len(cards_none_filter)
        assert {c.id for c in cards_no_filter} == {c.id for c in cards_none_filter}
