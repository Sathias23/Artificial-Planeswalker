"""Unit tests for CardRepository query methods."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.data.models.base import Base
from src.data.repositories.card import CardRepository
from src.data.schemas.card import Card
from tests.fixtures.card_data import (
    create_color_mode_test_cards,
    create_multiface_card,
    create_om1_spm_cards,
    create_sample_cards,
    create_standard_legal_cards,
)


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
async def populated_session(async_session: AsyncSession) -> AsyncSession:
    """Create a session populated with sample card data."""
    # Add all sample cards
    sample_cards = create_sample_cards()
    async_session.add_all(sample_cards)

    # Add multi-face card
    multiface_card = create_multiface_card()
    async_session.add(multiface_card)

    await async_session.commit()

    return async_session


@pytest.fixture
def card_repo(async_session: AsyncSession) -> CardRepository:
    """Create a CardRepository instance for testing."""
    return CardRepository(async_session)


@pytest.fixture
def populated_repo(populated_session: AsyncSession) -> CardRepository:
    """Create a CardRepository with populated data."""
    return CardRepository(populated_session)


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


@pytest.fixture
async def color_mode_session(async_session: AsyncSession) -> AsyncSession:
    """Create a session with cards for testing color mode filtering."""
    # Add color mode test cards
    color_cards = create_color_mode_test_cards()
    async_session.add_all(color_cards)
    await async_session.commit()
    return async_session


@pytest.fixture
def color_mode_repo(color_mode_session: AsyncSession) -> CardRepository:
    """Create a CardRepository with color mode test data."""
    return CardRepository(color_mode_session)


@pytest.fixture
async def om1_spm_session(async_session: AsyncSession) -> AsyncSession:
    """Create a session with OM1/SPM card pairs for testing same Oracle ID with different games."""
    # Add OM1/SPM cards
    om1_spm_cards = create_om1_spm_cards()
    async_session.add_all(om1_spm_cards)
    await async_session.commit()
    return async_session


@pytest.fixture
def om1_spm_repo(om1_spm_session: AsyncSession) -> CardRepository:
    """Create a CardRepository with OM1/SPM test data."""
    return CardRepository(om1_spm_session)


class TestFindByNameExact:
    """Tests for find_by_name_exact method."""

    async def test_find_existing_card(self, populated_repo: CardRepository) -> None:
        """Test finding a card by exact name."""
        card = await populated_repo.find_by_name_exact("Lightning Bolt")

        assert card is not None
        assert card.name == "Lightning Bolt"
        assert card.id == "bolt-001"
        assert isinstance(card, Card)

    async def test_case_insensitive_search(self, populated_repo: CardRepository) -> None:
        """Test exact name search is case-insensitive."""
        # Try lowercase
        card = await populated_repo.find_by_name_exact("lightning bolt")
        assert card is not None
        assert card.name == "Lightning Bolt"

        # Try uppercase
        card = await populated_repo.find_by_name_exact("LIGHTNING BOLT")
        assert card is not None
        assert card.name == "Lightning Bolt"

    async def test_card_not_found(self, populated_repo: CardRepository) -> None:
        """Test returns None when card doesn't exist."""
        card = await populated_repo.find_by_name_exact("Nonexistent Card")

        assert card is None

    async def test_returns_pydantic_schema(self, populated_repo: CardRepository) -> None:
        """Test that returned object is a Pydantic schema."""
        card = await populated_repo.find_by_name_exact("Lightning Bolt")

        assert card is not None
        assert isinstance(card, Card)
        # Should be serializable to JSON
        card_dict = card.model_dump()
        assert card_dict["name"] == "Lightning Bolt"

    async def test_multiple_printings_returns_first(self, async_session: AsyncSession) -> None:
        """Test that when multiple printings exist, returns first by ID."""
        from src.data.models.card import CardModel

        # Create multiple printings of the same card (same name, different sets)
        printings = [
            CardModel(
                id="bolt-alpha",
                name="Lightning Bolt",
                oracle_id="oracle-bolt",
                mana_cost="{R}",
                cmc=1.0,
                type_line="Instant",
                oracle_text="Lightning Bolt deals 3 damage to any target.",
                rarity="common",
                set_code="LEA",
                set_name="Limited Edition Alpha",
                collector_number="161",
                colors=["R"],
                color_identity=["R"],
                legalities={"standard": "not_legal", "modern": "legal"},
                card_faces=None,
            ),
            CardModel(
                id="bolt-m10",
                name="Lightning Bolt",
                oracle_id="oracle-bolt",
                mana_cost="{R}",
                cmc=1.0,
                type_line="Instant",
                oracle_text="Lightning Bolt deals 3 damage to any target.",
                rarity="common",
                set_code="M10",
                set_name="Magic 2010",
                collector_number="146",
                colors=["R"],
                color_identity=["R"],
                legalities={"standard": "not_legal", "modern": "legal"},
                card_faces=None,
            ),
            CardModel(
                id="bolt-m11",
                name="Lightning Bolt",
                oracle_id="oracle-bolt",
                mana_cost="{R}",
                cmc=1.0,
                type_line="Instant",
                oracle_text="Lightning Bolt deals 3 damage to any target.",
                rarity="common",
                set_code="M11",
                set_name="Magic 2011",
                collector_number="149",
                colors=["R"],
                color_identity=["R"],
                legalities={"standard": "not_legal", "modern": "legal"},
                card_faces=None,
            ),
        ]

        async_session.add_all(printings)
        await async_session.commit()

        repo = CardRepository(async_session)
        card = await repo.find_by_name_exact("Lightning Bolt")

        # Should return first printing ordered by ID
        assert card is not None
        assert card.name == "Lightning Bolt"
        assert card.id == "bolt-alpha"  # First alphabetically by ID


class TestGetById:
    """Tests for get_by_id method (Story 1.5 — card pre-validation under FK-off)."""

    async def test_found_returns_card(self, populated_repo: CardRepository) -> None:
        """A known card id returns the corresponding Card schema."""
        card = await populated_repo.get_by_id("bolt-001")

        assert card is not None
        assert isinstance(card, Card)
        assert card.id == "bolt-001"
        assert card.name == "Lightning Bolt"

    async def test_bogus_id_returns_none(self, populated_repo: CardRepository) -> None:
        """An unknown card id returns None (graceful, no raise)."""
        card = await populated_repo.get_by_id("does-not-exist")

        assert card is None


class TestFindByNamePartial:
    """Tests for find_by_name_partial method."""

    async def test_find_multiple_matches(self, populated_repo: CardRepository) -> None:
        """Test partial name search returns multiple matches."""
        cards = await populated_repo.find_by_name_partial("lightning")

        # Lightning Bolt, Lightning Strike, Chain Lightning, Lightning Helix
        assert len(cards) == 4
        card_names = {card.name for card in cards}
        assert "Lightning Bolt" in card_names
        assert "Lightning Strike" in card_names
        assert "Chain Lightning" in card_names
        assert "Lightning Helix" in card_names

    async def test_single_match(self, populated_repo: CardRepository) -> None:
        """Test partial name search with single result."""
        cards = await populated_repo.find_by_name_partial("counterspell")

        assert len(cards) == 1
        assert cards[0].name == "Counterspell"

    async def test_no_matches(self, populated_repo: CardRepository) -> None:
        """Test partial name search returns empty list when no matches."""
        cards = await populated_repo.find_by_name_partial("nonexistent")

        assert cards == []
        assert isinstance(cards, list)

    async def test_case_insensitive_partial(self, populated_repo: CardRepository) -> None:
        """Test partial name search is case-insensitive."""
        # Uppercase
        cards = await populated_repo.find_by_name_partial("COUNTER")
        assert len(cards) == 1
        assert cards[0].name == "Counterspell"

        # Mixed case
        cards = await populated_repo.find_by_name_partial("LlAnOwAr")
        assert len(cards) == 1
        assert cards[0].name == "Llanowar Elves"

    async def test_substring_match(self, populated_repo: CardRepository) -> None:
        """Test partial name search matches substrings anywhere."""
        # Match at end
        cards = await populated_repo.find_by_name_partial("bolt")
        assert len(cards) == 1
        assert cards[0].name == "Lightning Bolt"

        # Match in middle
        cards = await populated_repo.find_by_name_partial("ring")
        assert len(cards) == 1
        assert cards[0].name == "Sol Ring"

    async def test_returns_pydantic_schemas(self, populated_repo: CardRepository) -> None:
        """Test that all returned objects are Pydantic schemas."""
        cards = await populated_repo.find_by_name_partial("lightning")

        assert len(cards) > 0
        for card in cards:
            assert isinstance(card, Card)
            # Should be serializable
            card_dict = card.model_dump()
            assert "name" in card_dict


class TestFindByColors:
    """Tests for find_by_colors method."""

    async def test_find_single_color(self, populated_repo: CardRepository) -> None:
        """Test finding cards by single color."""
        # Find red cards
        red_cards = await populated_repo.find_by_colors("R")

        # Should include Lightning Bolt, Lightning Strike, Chain Lightning,
        # Shivan Dragon, and multi-color cards with red
        assert len(red_cards) >= 3
        red_card_names = {card.name for card in red_cards}
        assert "Lightning Bolt" in red_card_names
        assert "Lightning Strike" in red_card_names
        assert "Chain Lightning" in red_card_names

    async def test_find_multi_color_cards(self, populated_repo: CardRepository) -> None:
        """Test that multi-color cards are found when searching for one of their colors."""
        # Find red cards (should include Niv-Mizzet which is U/R)
        red_cards = await populated_repo.find_by_colors("R")
        red_card_names = {card.name for card in red_cards}
        assert "Niv-Mizzet, Parun" in red_card_names

        # Find blue cards (should include Niv-Mizzet)
        blue_cards = await populated_repo.find_by_colors("U")
        blue_card_names = {card.name for card in blue_cards}
        assert "Niv-Mizzet, Parun" in blue_card_names

    async def test_find_colorless(self, populated_repo: CardRepository) -> None:
        """Test finding colorless cards with empty string."""
        colorless_cards = await populated_repo.find_by_colors("")

        assert len(colorless_cards) == 1
        assert colorless_cards[0].name == "Sol Ring"
        assert colorless_cards[0].colors == []

    async def test_color_not_found(self, populated_repo: CardRepository) -> None:
        """Test returns empty list when color not found."""
        # No black cards in sample data
        black_cards = await populated_repo.find_by_colors("B")

        assert black_cards == []
        assert isinstance(black_cards, list)

    async def test_returns_pydantic_schemas(self, populated_repo: CardRepository) -> None:
        """Test that all returned objects are Pydantic schemas."""
        cards = await populated_repo.find_by_colors("R")

        assert len(cards) > 0
        for card in cards:
            assert isinstance(card, Card)


class TestFindByType:
    """Tests for find_by_type method."""

    async def test_find_by_type(self, populated_repo: CardRepository) -> None:
        """Test finding cards by type."""
        # Find Instant cards
        instants = await populated_repo.find_by_type("Instant")

        instant_names = {card.name for card in instants}
        assert "Lightning Bolt" in instant_names
        assert "Lightning Strike" in instant_names
        assert "Counterspell" in instant_names
        assert "Lightning Helix" in instant_names

    async def test_find_by_subtype(self, populated_repo: CardRepository) -> None:
        """Test finding cards by subtype."""
        # Find Dragon creatures
        dragons = await populated_repo.find_by_type("Dragon")

        dragon_names = {card.name for card in dragons}
        assert "Niv-Mizzet, Parun" in dragon_names
        assert "Shivan Dragon" in dragon_names

    async def test_case_insensitive_type(self, populated_repo: CardRepository) -> None:
        """Test type search is case-insensitive."""
        # Lowercase
        artifacts = await populated_repo.find_by_type("artifact")
        assert len(artifacts) >= 1
        assert artifacts[0].name == "Sol Ring"

        # Uppercase
        instants = await populated_repo.find_by_type("INSTANT")
        assert len(instants) >= 4

    async def test_type_not_found(self, populated_repo: CardRepository) -> None:
        """Test returns empty list when type not found."""
        # No Planeswalker cards in sample data
        planeswalkers = await populated_repo.find_by_type("Planeswalker")

        assert planeswalkers == []
        assert isinstance(planeswalkers, list)

    async def test_find_legendary(self, populated_repo: CardRepository) -> None:
        """Test finding cards by Legendary supertype."""
        legendary = await populated_repo.find_by_type("Legendary")

        assert len(legendary) >= 1
        legendary_names = {card.name for card in legendary}
        assert "Niv-Mizzet, Parun" in legendary_names

    async def test_returns_pydantic_schemas(self, populated_repo: CardRepository) -> None:
        """Test that all returned objects are Pydantic schemas."""
        cards = await populated_repo.find_by_type("Instant")

        assert len(cards) > 0
        for card in cards:
            assert isinstance(card, Card)


class TestSearchByKeywords:
    """Tests for search_by_keywords method."""

    async def test_find_cards_by_keyword(self, populated_repo: CardRepository) -> None:
        """Test finding cards by keyword in keywords array."""
        # Find cards with haste
        haste_cards = await populated_repo.search_by_keywords("haste")

        assert len(haste_cards) >= 2
        card_names = {card.name for card in haste_cards}
        assert "Goblin Guide" in card_names
        assert "Monastery Swiftspear" in card_names

    async def test_find_by_oracle_text(self, populated_repo: CardRepository) -> None:
        """Test finding cards by keyword in oracle text."""
        # Find cards with "flying" (should find multiple)
        flying_cards = await populated_repo.search_by_keywords("flying")

        assert len(flying_cards) >= 3
        card_names = {card.name for card in flying_cards}
        assert "Niv-Mizzet, Parun" in card_names
        assert "Shivan Dragon" in card_names
        assert "Serra Angel" in card_names

    async def test_keyword_case_insensitive(self, populated_repo: CardRepository) -> None:
        """Test keyword search is case-insensitive."""
        # Uppercase
        cards_upper = await populated_repo.search_by_keywords("HASTE")
        # Lowercase
        cards_lower = await populated_repo.search_by_keywords("haste")
        # Mixed case
        cards_mixed = await populated_repo.search_by_keywords("HaStE")

        assert len(cards_upper) >= 2
        assert len(cards_lower) >= 2
        assert len(cards_mixed) >= 2

    async def test_keyword_not_found(self, populated_repo: CardRepository) -> None:
        """Test returns empty list when keyword not found."""
        # No cards with "double strike" in sample data
        cards = await populated_repo.search_by_keywords("double strike")

        assert cards == []
        assert isinstance(cards, list)

    async def test_returns_pydantic_schemas(self, populated_repo: CardRepository) -> None:
        """Test that all returned objects are Pydantic schemas."""
        cards = await populated_repo.search_by_keywords("flying")

        assert len(cards) > 0
        for card in cards:
            assert isinstance(card, Card)


class TestSearchAdvanced:
    """Tests for search_advanced method with multi-criteria filtering."""

    async def test_search_by_colors_only(self, populated_repo: CardRepository) -> None:
        """Test advanced search with color filter only."""
        # Find red cards
        result = await populated_repo.search_advanced(colors=["R"])

        assert len(result.items) >= 3
        card_names = {card.name for card in result.items}
        assert "Lightning Bolt" in card_names
        assert "Goblin Guide" in card_names

    async def test_search_by_types_only(self, populated_repo: CardRepository) -> None:
        """Test advanced search with type filter only."""
        # Find creatures
        result = await populated_repo.search_advanced(types=["Creature"])

        assert len(result.items) >= 4
        card_names = {card.name for card in result.items}
        assert "Llanowar Elves" in card_names
        assert "Goblin Guide" in card_names
        assert "Serra Angel" in card_names

    async def test_search_by_mana_value_max(self, populated_repo: CardRepository) -> None:
        """Test advanced search with maximum mana value filter."""
        # Find cards with CMC <= 1
        result = await populated_repo.search_advanced(mana_value_max=1.0)

        assert len(result.items) >= 4
        card_names = {card.name for card in result.items}
        assert "Lightning Bolt" in card_names
        assert "Goblin Guide" in card_names
        assert "Sol Ring" in card_names

        # All cards should have CMC <= 1
        for card in result.items:
            assert card.cmc <= 1.0

    async def test_search_by_mana_value_range(self, populated_repo: CardRepository) -> None:
        """Test advanced search with mana value range."""
        # Find cards with CMC between 2 and 3
        result = await populated_repo.search_advanced(mana_value_min=2.0, mana_value_max=3.0)

        # All cards should have CMC >= 2 and <= 3
        for card in result.items:
            assert 2.0 <= card.cmc <= 3.0

    async def test_search_combined_color_and_type(self, populated_repo: CardRepository) -> None:
        """Test advanced search with color AND type filters."""
        # Find red creatures
        result = await populated_repo.search_advanced(colors=["R"], types=["Creature"])

        assert len(result.items) >= 2
        card_names = {card.name for card in result.items}
        assert "Goblin Guide" in card_names
        assert "Monastery Swiftspear" in card_names

        # All cards should be red and creatures
        for card in result.items:
            assert "R" in card.colors
            assert "Creature" in card.type_line

    async def test_search_combined_all_filters(self, populated_repo: CardRepository) -> None:
        """Test advanced search with all filters combined."""
        # Find red creatures with haste under 4 mana (the classic query from the spec!)
        result = await populated_repo.search_advanced(
            colors=["R"],
            types=["Creature"],
            keywords=["haste"],
            mana_value_max=3.0,
        )

        assert len(result.items) >= 2
        card_names = {card.name for card in result.items}
        assert "Goblin Guide" in card_names
        assert "Monastery Swiftspear" in card_names

        # Verify all filters applied
        for card in result.items:
            assert "R" in card.colors
            assert "Creature" in card.type_line
            assert card.cmc <= 3.0
            # Haste in keywords array or oracle text
            has_haste = (card.keywords and "Haste" in card.keywords) or (
                "haste" in card.oracle_text.lower()
            )
            assert has_haste

    async def test_search_with_limit(self, populated_repo: CardRepository) -> None:
        """Test advanced search respects result limit."""
        # Search for all cards with limit=3
        result = await populated_repo.search_advanced(limit=3)

        assert len(result.items) <= 3

    async def test_search_sorted_by_cmc_and_name(self, populated_repo: CardRepository) -> None:
        """Test advanced search results are sorted by CMC then name."""
        result = await populated_repo.search_advanced(colors=["R"], limit=10)

        # Verify sorted by CMC
        for i in range(len(result.items) - 1):
            assert result.items[i].cmc <= result.items[i + 1].cmc

    async def test_search_no_results(self, populated_repo: CardRepository) -> None:
        """Test advanced search returns empty list when no matches."""
        # Search for black creatures (none in sample data)
        result = await populated_repo.search_advanced(colors=["B"], types=["Creature"])

        assert result.items == []
        assert isinstance(result.items, list)

    async def test_search_multiple_types(self, populated_repo: CardRepository) -> None:
        """Test advanced search with multiple type filters (AND logic)."""
        # Find legendary dragons (both must be in type line)
        result = await populated_repo.search_advanced(types=["Legendary", "Dragon"])

        assert len(result.items) >= 1
        assert "Niv-Mizzet, Parun" in {card.name for card in result.items}

        # All results should have both types
        for card in result.items:
            assert "Legendary" in card.type_line
            assert "Dragon" in card.type_line

    async def test_search_multiple_keywords(self, populated_repo: CardRepository) -> None:
        """Test advanced search with multiple keyword filters (AND logic)."""
        # Find cards with both haste and prowess
        result = await populated_repo.search_advanced(keywords=["haste", "prowess"])

        assert len(result.items) >= 1
        assert "Monastery Swiftspear" in {card.name for card in result.items}

    async def test_returns_pydantic_schemas(self, populated_repo: CardRepository) -> None:
        """Test that all returned objects are Pydantic schemas."""
        result = await populated_repo.search_advanced(colors=["R"])

        assert len(result.items) > 0
        for card in result.items:
            assert isinstance(card, Card)

    async def test_search_by_single_rarity(self, populated_repo: CardRepository) -> None:
        """Test advanced search with single rarity filter."""
        # Find rare cards
        result = await populated_repo.search_advanced(rarity="rare")

        assert len(result.items) >= 3
        card_names = {card.name for card in result.items}
        assert "Niv-Mizzet, Parun" in card_names
        assert "Shivan Dragon" in card_names
        assert "Goblin Guide" in card_names

        # All cards should be rare
        for card in result.items:
            assert card.rarity.lower() == "rare"

    async def test_search_by_multiple_rarities(self, populated_repo: CardRepository) -> None:
        """Test advanced search with multiple rarity values (OR logic)."""
        # Find rare or uncommon cards
        result = await populated_repo.search_advanced(rarity=["rare", "uncommon"])

        # Should include both rare and uncommon cards
        card_names = {card.name for card in result.items}
        # Rare cards
        assert "Niv-Mizzet, Parun" in card_names
        assert "Goblin Guide" in card_names
        # Uncommon cards
        assert "Chain Lightning" in card_names
        assert "Sol Ring" in card_names

        # All cards should be rare or uncommon
        for card in result.items:
            assert card.rarity.lower() in ["rare", "uncommon"]

    async def test_search_rarity_case_insensitive(self, populated_repo: CardRepository) -> None:
        """Test rarity filter is case-insensitive."""
        # Uppercase
        rare_upper = await populated_repo.search_advanced(rarity="RARE")
        assert len(rare_upper.items) >= 3

        # Lowercase
        rare_lower = await populated_repo.search_advanced(rarity="rare")
        assert len(rare_lower.items) >= 3

        # Mixed case
        rare_mixed = await populated_repo.search_advanced(rarity="Rare")
        assert len(rare_mixed.items) >= 3

        # Should all return same results
        assert len(rare_upper.items) == len(rare_lower.items) == len(rare_mixed.items)

    async def test_search_rarity_with_color_filter(self, populated_repo: CardRepository) -> None:
        """Test rarity filter combined with color filter."""
        # Find rare red cards
        result = await populated_repo.search_advanced(colors=["R"], rarity="rare")

        assert len(result.items) >= 2
        card_names = {card.name for card in result.items}
        assert "Goblin Guide" in card_names
        assert "Shivan Dragon" in card_names

        # All cards should be red and rare
        for card in result.items:
            assert "R" in card.colors
            assert card.rarity.lower() == "rare"

    async def test_search_rarity_with_type_filter(self, populated_repo: CardRepository) -> None:
        """Test rarity filter combined with type filter."""
        # Find rare creatures
        result = await populated_repo.search_advanced(types=["Creature"], rarity="rare")

        assert len(result.items) >= 3
        card_names = {card.name for card in result.items}
        assert "Goblin Guide" in card_names
        assert "Shivan Dragon" in card_names
        assert "Niv-Mizzet, Parun" in card_names

        # All cards should be creatures and rare
        for card in result.items:
            assert "Creature" in card.type_line
            assert card.rarity.lower() == "rare"

    async def test_search_rarity_with_all_filters(self, populated_repo: CardRepository) -> None:
        """Test rarity filter combined with all other filters."""
        # Find rare red creatures with haste under 4 mana
        result = await populated_repo.search_advanced(
            colors=["R"],
            types=["Creature"],
            keywords=["haste"],
            mana_value_max=3.0,
            rarity="rare",
        )

        assert len(result.items) >= 1
        assert "Goblin Guide" in {card.name for card in result.items}

        # Verify all filters applied
        for card in result.items:
            assert "R" in card.colors
            assert "Creature" in card.type_line
            assert card.cmc <= 3.0
            assert card.rarity.lower() == "rare"
            # Haste in keywords array or oracle text
            has_haste = (card.keywords and "Haste" in card.keywords) or (
                "haste" in card.oracle_text.lower()
            )
            assert has_haste

    async def test_search_no_rarity_returns_all_rarities(
        self, populated_repo: CardRepository
    ) -> None:
        """Test that None rarity parameter returns all rarities."""
        # Search without rarity filter
        result = await populated_repo.search_advanced(colors=["R"], rarity=None)

        # Should include cards of different rarities
        rarities = {card.rarity.lower() for card in result.items}
        assert len(rarities) > 1  # Multiple rarities present

    async def test_search_rarity_empty_result(self, populated_repo: CardRepository) -> None:
        """Test rarity filter returns empty list when no matches."""
        # No mythic cards in sample data
        result = await populated_repo.search_advanced(rarity="mythic")

        assert result.items == []
        assert isinstance(result.items, list)


class TestRepositoryIntegration:
    """Integration tests for repository with real database operations."""

    async def test_empty_database(self, card_repo: CardRepository) -> None:
        """Test queries on empty database return appropriate empty results."""
        # Exact name should return None
        card = await card_repo.find_by_name_exact("Lightning Bolt")
        assert card is None

        # Partial name should return empty list
        cards = await card_repo.find_by_name_partial("lightning")
        assert cards == []

        # Color search should return empty list
        cards = await card_repo.find_by_colors("R")
        assert cards == []

        # Type search should return empty list
        cards = await card_repo.find_by_type("Instant")
        assert cards == []

        # Keyword search should return empty list
        cards = await card_repo.search_by_keywords("flying")
        assert cards == []

        # Advanced search should return empty paginated result
        result = await card_repo.search_advanced(colors=["R"])
        assert result.items == []
        assert result.total_count == 0

    async def test_multiface_card(self, populated_repo: CardRepository) -> None:
        """Test querying multi-face cards."""
        card = await populated_repo.find_by_name_exact("Delver of Secrets")

        assert card is not None
        assert card.name == "Delver of Secrets"
        assert card.card_faces is not None
        assert len(card.card_faces) == 2
        assert card.card_faces[0]["name"] == "Delver of Secrets"
        assert card.card_faces[1]["name"] == "Insectile Aberration"


class TestColorModeFiltering:
    """Tests for color_mode parameter in search_advanced method."""

    async def test_color_mode_any_default(self, color_mode_repo: CardRepository) -> None:
        """Test 'any' mode (default) - cards must have ANY of the specified colors."""
        # Search for white OR blue
        result = await color_mode_repo.search_advanced(colors=["W", "U"], color_mode="any")

        card_names = {card.name for card in result.items}
        # Should include: mono-W, mono-U, W/U, R/W, U/R, W/U/B
        assert "Path to Exile" in card_names  # Mono-W
        assert "Opt" in card_names  # Mono-U
        assert "Supreme Verdict" in card_names  # W/U
        assert "Boros Charm" in card_names  # R/W
        assert "Electrolyze" in card_names  # U/R
        assert "Esper Charm" in card_names  # W/U/B

        # Should NOT include colorless or mono-R
        assert "Worn Powerstone" not in card_names
        assert "Shock" not in card_names

    async def test_color_mode_all(self, color_mode_repo: CardRepository) -> None:
        """Test 'all' mode - cards must have ALL of the specified colors."""
        # Search for white AND blue
        result = await color_mode_repo.search_advanced(colors=["W", "U"], color_mode="all")

        card_names = {card.name for card in result.items}
        # Should include: W/U, W/U/B (has both W and U)
        assert "Supreme Verdict" in card_names  # W/U
        assert "Esper Charm" in card_names  # W/U/B

        # Should NOT include mono-color or cards missing one of the colors
        assert "Path to Exile" not in card_names  # Mono-W
        assert "Opt" not in card_names  # Mono-U
        assert "Boros Charm" not in card_names  # R/W (missing U)
        assert "Electrolyze" not in card_names  # U/R (missing W)

    async def test_color_mode_exact(self, color_mode_repo: CardRepository) -> None:
        """Test 'exact' mode - cards must have EXACTLY the specified colors."""
        # Search for exactly white AND blue (Azorius)
        result = await color_mode_repo.search_advanced(colors=["W", "U"], color_mode="exact")

        card_names = {card.name for card in result.items}
        # Should include ONLY W/U cards
        assert "Supreme Verdict" in card_names  # W/U

        # Should NOT include mono-color, cards with extra colors, or different two-color
        assert "Path to Exile" not in card_names  # Mono-W
        assert "Opt" not in card_names  # Mono-U
        assert "Boros Charm" not in card_names  # R/W
        assert "Electrolyze" not in card_names  # U/R
        assert "Esper Charm" not in card_names  # W/U/B (has extra color)

    async def test_color_mode_at_most(self, color_mode_repo: CardRepository) -> None:
        """Test 'at_most' mode - cards can have at most the specified colors."""
        # Search for at most white AND blue (color identity)
        result = await color_mode_repo.search_advanced(colors=["W", "U"], color_mode="at_most")

        card_names = {card.name for card in result.items}
        # Should include: colorless, mono-W, mono-U, W/U
        assert "Worn Powerstone" in card_names  # Colorless
        assert "Path to Exile" in card_names  # Mono-W
        assert "Opt" in card_names  # Mono-U
        assert "Supreme Verdict" in card_names  # W/U

        # Should NOT include cards with colors outside the set
        assert "Boros Charm" not in card_names  # R/W (has R)
        assert "Electrolyze" not in card_names  # U/R (has R)
        assert "Esper Charm" not in card_names  # W/U/B (has B)
        assert "Shock" not in card_names  # Mono-R

    async def test_color_mode_exact_single_color(self, color_mode_repo: CardRepository) -> None:
        """Test 'exact' mode with single color - only mono-color cards."""
        result = await color_mode_repo.search_advanced(colors=["W"], color_mode="exact")

        card_names = {card.name for card in result.items}
        # Should include ONLY mono-white
        assert "Path to Exile" in card_names

        # Should NOT include multicolor or other mono-colors
        assert "Supreme Verdict" not in card_names  # W/U
        assert "Boros Charm" not in card_names  # R/W
        assert "Opt" not in card_names  # Mono-U

    async def test_color_mode_exact_empty_colors_colorless(
        self, color_mode_repo: CardRepository
    ) -> None:
        """Test 'exact' mode with empty colors list - colorless cards only."""
        result = await color_mode_repo.search_advanced(colors=[], color_mode="exact")

        card_names = {card.name for card in result.items}
        # Should include ONLY colorless
        assert "Worn Powerstone" in card_names

        # Should NOT include any colored cards
        assert "Path to Exile" not in card_names
        assert "Opt" not in card_names
        assert "Supreme Verdict" not in card_names

    async def test_color_mode_default_backward_compatibility(
        self, color_mode_repo: CardRepository
    ) -> None:
        """Test default color_mode maintains backward compatibility with 'any' mode."""
        # Search without specifying color_mode (should default to "any")
        result_default = await color_mode_repo.search_advanced(colors=["W", "U"])

        # Search explicitly with "any" mode
        result_any = await color_mode_repo.search_advanced(colors=["W", "U"], color_mode="any")

        # Results should be identical
        assert len(result_default.items) == len(result_any.items)
        assert {card.name for card in result_default.items} == {
            card.name for card in result_any.items
        }

    async def test_color_mode_with_other_filters(self, color_mode_repo: CardRepository) -> None:
        """Test color_mode combined with other filters."""
        # Exact W/U cards with CMC <= 4
        result = await color_mode_repo.search_advanced(
            colors=["W", "U"],
            color_mode="exact",
            mana_value_max=4,
        )

        card_names = {card.name for card in result.items}
        # Supreme Verdict has CMC 4
        assert "Supreme Verdict" in card_names
        assert len(result.items) == 1

    async def test_color_mode_at_most_single_color(self, color_mode_repo: CardRepository) -> None:
        """Test 'at_most' mode with single color - colorless and mono-color."""
        result = await color_mode_repo.search_advanced(colors=["U"], color_mode="at_most")

        card_names = {card.name for card in result.items}
        # Should include colorless and mono-blue
        assert "Worn Powerstone" in card_names  # Colorless
        assert "Opt" in card_names  # Mono-U

        # Should NOT include any other colors
        assert "Path to Exile" not in card_names  # Mono-W
        assert "Supreme Verdict" not in card_names  # W/U
        assert "Electrolyze" not in card_names  # U/R

    async def test_color_mode_all_with_three_colors(self, color_mode_repo: CardRepository) -> None:
        """Test 'all' mode with three colors - must have all three."""
        result = await color_mode_repo.search_advanced(colors=["W", "U", "B"], color_mode="all")

        card_names = {card.name for card in result.items}
        # Should include only cards with W, U, AND B
        assert "Esper Charm" in card_names  # W/U/B

        # Should NOT include cards missing any color
        assert "Supreme Verdict" not in card_names  # W/U (missing B)
        assert len(result.items) == 1


class TestGamesFiltering:
    """Tests for games parameter filtering in repository methods."""

    async def test_find_by_name_exact_with_games_filter(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test find_by_name_exact respects games filter."""
        # Lightning Bolt exists in sample data with games=["paper", "mtgo"]
        # Should be found when filtering for paper
        card = await mixed_format_repo.find_by_name_exact("Lightning Bolt", games=["paper"])
        assert card is not None
        assert card.name == "Lightning Bolt"

        # Should be found when filtering for mtgo
        card = await mixed_format_repo.find_by_name_exact("Lightning Bolt", games=["mtgo"])
        assert card is not None
        assert card.name == "Lightning Bolt"

        # Should NOT be found when filtering for arena only
        card = await mixed_format_repo.find_by_name_exact("Lightning Bolt", games=["arena"])
        assert card is None

    async def test_find_by_name_exact_arena_cards(self, mixed_format_repo: CardRepository) -> None:
        """Test find_by_name_exact finds Arena-available cards."""
        # Standard-legal cards have games=["paper", "arena", "mtgo"]
        card = await mixed_format_repo.find_by_name_exact("Play with Fire", games=["arena"])
        assert card is not None
        assert card.name == "Play with Fire"
        assert "arena" in card.games

    async def test_find_by_name_partial_with_games_filter(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test find_by_name_partial respects games filter."""
        # Find all cards with "fire" (includes "Play with Fire" which is Arena-available)
        # Filter to Arena-only
        arena_cards = await mixed_format_repo.find_by_name_partial("fire", games=["arena"])

        # Standard-legal cards should be in Arena
        card_names = {card.name for card in arena_cards}
        assert len(arena_cards) >= 1
        assert "Play with Fire" in card_names

        # All returned cards should be available in Arena
        for card in arena_cards:
            assert "arena" in card.games

    async def test_find_by_colors_with_games_filter(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test find_by_colors respects games filter."""
        # Find red cards available in Arena
        arena_red_cards = await mixed_format_repo.find_by_colors("R", games=["arena"])

        # Should return only Arena-available red cards
        assert len(arena_red_cards) >= 1
        for card in arena_red_cards:
            assert "R" in card.colors
            assert "arena" in card.games

    async def test_find_by_type_with_games_filter(self, mixed_format_repo: CardRepository) -> None:
        """Test find_by_type respects games filter."""
        # Find creatures available on MTGO
        mtgo_creatures = await mixed_format_repo.find_by_type("Creature", games=["mtgo"])

        # Should return only MTGO-available creatures
        assert len(mtgo_creatures) >= 1
        for card in mtgo_creatures:
            assert "Creature" in card.type_line
            assert "mtgo" in card.games

    async def test_search_by_keywords_with_games_filter(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test search_by_keywords respects games filter."""
        # Find cards with flying available in paper
        paper_flying = await mixed_format_repo.search_by_keywords("flying", games=["paper"])

        # Should return only paper-available cards with flying
        assert len(paper_flying) >= 1
        for card in paper_flying:
            assert "paper" in card.games

    async def test_search_advanced_with_single_game(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test search_advanced with single game filter."""
        # Find cards available in Arena
        result = await mixed_format_repo.search_advanced(games=["arena"])

        # Should return only Arena-available cards
        assert len(result.items) >= 1
        for card in result.items:
            assert "arena" in card.games

    async def test_search_advanced_with_multiple_games(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test search_advanced with multiple games uses OR logic."""
        # Find cards available in Arena OR Paper
        result = await mixed_format_repo.search_advanced(games=["arena", "paper"])

        # Should return cards available in either Arena or Paper (or both)
        assert len(result.items) >= 1
        for card in result.items:
            assert "arena" in card.games or "paper" in card.games

    async def test_search_advanced_games_with_other_filters(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test games filter combined with other filters."""
        # Find red creatures available in Arena
        result = await mixed_format_repo.search_advanced(
            colors=["R"],
            types=["Creature"],
            games=["arena"],
        )

        # Should return only Arena-available red creatures
        for card in result.items:
            assert "R" in card.colors
            assert "Creature" in card.type_line
            assert "arena" in card.games

    async def test_games_filter_none_returns_all(self, mixed_format_repo: CardRepository) -> None:
        """Test that None games filter returns all cards."""
        # Search without games filter
        result_no_filter = await mixed_format_repo.search_advanced(games=None)

        # Search with no games parameter (default)
        result_default = await mixed_format_repo.search_advanced()

        # Both should return all cards
        assert len(result_no_filter.items) >= 1
        assert len(result_default.items) >= 1
        assert len(result_no_filter.items) == len(result_default.items)

    async def test_games_filter_empty_list_returns_all(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test that empty games list returns all cards."""
        # Search with empty games list
        result = await mixed_format_repo.search_advanced(games=[])

        # Should return all cards (no filtering)
        assert len(result.items) >= 1

    async def test_games_filter_paper_only_excludes_arena(
        self, mixed_format_repo: CardRepository
    ) -> None:
        """Test paper-only filter excludes Arena cards."""
        # Find all cards
        result_all = await mixed_format_repo.search_advanced()

        # Find paper-only cards
        result_paper = await mixed_format_repo.search_advanced(games=["paper"])

        # Paper results should be a superset (all cards are in paper)
        assert len(result_paper.items) >= len(result_all.items)

    async def test_games_filter_mtgo_only(self, mixed_format_repo: CardRepository) -> None:
        """Test MTGO-only filter."""
        # Find MTGO cards
        result = await mixed_format_repo.search_advanced(games=["mtgo"])

        # Should return cards available on MTGO
        assert len(result.items) >= 1
        for card in result.items:
            assert "mtgo" in card.games

    async def test_games_filter_case_insensitive(self, mixed_format_repo: CardRepository) -> None:
        """Test games filter is case-insensitive (stored as lowercase)."""
        # All games should be stored as lowercase in database
        result = await mixed_format_repo.search_advanced(games=["arena"])

        for card in result.items:
            # Games should be lowercase in database
            assert all(g.islower() for g in card.games)


class TestOM1SPMScenario:
    """Tests for OM1/SPM card scenario - same Oracle ID, different games arrays.

    These tests verify the issue described in SPIDER_MAN_INVESTIGATION.md where:
    - SPM (Marvel's Spider-Man) cards are paper-only
    - OM1 (Through the Omenpaths) cards are digital-only (Arena/MTGO)
    - Both printings share the SAME Oracle ID and oracle name
    - Games filtering must return the correct printing for each platform
    """

    async def test_both_printings_exist_in_database(self, om1_spm_repo: CardRepository) -> None:
        """Test that unique cards exist (only one printing per Oracle ID returned)."""
        # Search for all Ultimate Green Goblin cards (no games filter)
        result = await om1_spm_repo.search_advanced(
            oracle_text_phrases=["Ultimate Green Goblin attacks"]
        )

        # Should find only ONE card (unique Oracle ID, not multiple printings)
        assert len(result.items) == 1
        card = result.items[0]
        assert card.name == "Ultimate Green Goblin"

        # Verify the Oracle ID
        assert card.oracle_id == "b5b43d01-fce6-4a00-9c19-7a7e2a09d833"

        # Should return either SPM or OM1 (first one alphabetically by ID)
        assert card.set_code in {"SPM", "OM1"}

    async def test_arena_filter_returns_only_om1_version(
        self, om1_spm_repo: CardRepository
    ) -> None:
        """Test Arena games filter returns only OM1 printing, not SPM."""
        # Search for Ultimate Green Goblin with Arena filter
        result = await om1_spm_repo.search_advanced(
            oracle_text_phrases=["Ultimate Green Goblin attacks"], games=["arena"]
        )

        # Should find only OM1 version (digital)
        assert len(result.items) == 1
        card = result.items[0]
        assert card.name == "Ultimate Green Goblin"
        assert card.set_code == "OM1"
        assert "arena" in card.games
        assert "paper" not in card.games

    async def test_paper_filter_returns_only_spm_version(
        self, om1_spm_repo: CardRepository
    ) -> None:
        """Test Paper games filter returns only SPM printing, not OM1."""
        # Search for Ultimate Green Goblin with Paper filter
        result = await om1_spm_repo.search_advanced(
            oracle_text_phrases=["Ultimate Green Goblin attacks"], games=["paper"]
        )

        # Should find only SPM version (paper)
        assert len(result.items) == 1
        card = result.items[0]
        assert card.name == "Ultimate Green Goblin"
        assert card.set_code == "SPM"
        assert "paper" in card.games
        assert "arena" not in card.games
        assert "mtgo" not in card.games

    async def test_mtgo_filter_returns_only_om1_version(self, om1_spm_repo: CardRepository) -> None:
        """Test MTGO games filter returns only OM1 printing, not SPM."""
        # Search for Ultimate Green Goblin with MTGO filter
        result = await om1_spm_repo.search_advanced(
            oracle_text_phrases=["Ultimate Green Goblin attacks"], games=["mtgo"]
        )

        # Should find only OM1 version (digital)
        assert len(result.items) == 1
        card = result.items[0]
        assert card.name == "Ultimate Green Goblin"
        assert card.set_code == "OM1"
        assert "mtgo" in card.games
        assert "paper" not in card.games

    async def test_find_by_name_exact_with_arena_filter(self, om1_spm_repo: CardRepository) -> None:
        """Test exact name lookup with Arena filter returns OM1 version."""
        # Look up by exact name with Arena filter
        card = await om1_spm_repo.find_by_name_exact("Ultimate Green Goblin", games=["arena"])

        # Should return OM1 version
        assert card is not None
        assert card.name == "Ultimate Green Goblin"
        assert card.set_code == "OM1"
        assert "arena" in card.games

    async def test_find_by_name_exact_with_paper_filter(self, om1_spm_repo: CardRepository) -> None:
        """Test exact name lookup with Paper filter returns SPM version."""
        # Look up by exact name with Paper filter
        card = await om1_spm_repo.find_by_name_exact("Ultimate Green Goblin", games=["paper"])

        # Should return SPM version
        assert card is not None
        assert card.name == "Ultimate Green Goblin"
        assert card.set_code == "SPM"
        assert "paper" in card.games

    async def test_villain_type_search_with_arena_filter(
        self, om1_spm_repo: CardRepository
    ) -> None:
        """Test searching for Villain creatures with Arena filter finds OM1 cards."""
        # Search for Villain creatures with Arena filter
        result = await om1_spm_repo.search_advanced(types=["Villain"], games=["arena"])

        # Should find OM1 villains (Ultimate Green Goblin and Doctor Octopus)
        assert len(result.items) == 2
        set_codes = {card.set_code for card in result.items}
        assert set_codes == {"OM1"}

        # All should be Arena-available
        for card in result.items:
            assert "arena" in card.games
            assert "Villain" in card.type_line

    async def test_villain_type_search_with_paper_filter(
        self, om1_spm_repo: CardRepository
    ) -> None:
        """Test searching for Villain creatures with Paper filter finds SPM cards."""
        # Search for Villain creatures with Paper filter
        result = await om1_spm_repo.search_advanced(types=["Villain"], games=["paper"])

        # Should find SPM villains
        assert len(result.items) == 2
        set_codes = {card.set_code for card in result.items}
        assert set_codes == {"SPM"}

        # All should be Paper-available
        for card in result.items:
            assert "paper" in card.games
            assert "Villain" in card.type_line

    async def test_no_games_filter_returns_unique_cards_only(
        self, om1_spm_repo: CardRepository
    ) -> None:
        """Test searching without games filter returns only unique cards."""
        # Search for Villain creatures without games filter
        result = await om1_spm_repo.search_advanced(types=["Villain"])

        # Should find only 2 unique cards (one per Oracle ID, not multiple printings)
        assert len(result.items) == 2

        # Verify we have unique cards by Oracle ID
        oracle_ids = {card.oracle_id for card in result.items}
        assert len(oracle_ids) == 2  # Two unique cards

        # Verify card names (should be one of each, not duplicates)
        card_names = {card.name for card in result.items}
        assert card_names == {"Ultimate Green Goblin", "Doctor Octopus"}

    async def test_multiple_games_filter_or_logic(self, om1_spm_repo: CardRepository) -> None:
        """Test games filter with multiple values uses OR logic (returns unique cards)."""
        # Search for Villain creatures available in Arena OR Paper
        result = await om1_spm_repo.search_advanced(types=["Villain"], games=["arena", "paper"])

        # Should find only 2 unique cards (one per Oracle ID)
        # Each card has either arena OR paper in their games array
        assert len(result.items) == 2

        # Verify we have unique cards by Oracle ID
        oracle_ids = {card.oracle_id for card in result.items}
        assert len(oracle_ids) == 2

        # Verify each card has at least one of the requested games
        for card in result.items:
            assert "arena" in card.games or "paper" in card.games

    async def test_color_filter_with_games_filter_om1_spm(
        self, om1_spm_repo: CardRepository
    ) -> None:
        """Test combining color filter with games filter on OM1/SPM cards."""
        # Search for red/green cards (Ultimate Green Goblin) in Arena
        result = await om1_spm_repo.search_advanced(
            colors=["R", "G"], color_mode="all", games=["arena"]
        )

        # Should find only OM1 Ultimate Green Goblin
        assert len(result.items) == 1
        card = result.items[0]
        assert card.name == "Ultimate Green Goblin"
        assert card.set_code == "OM1"
        assert "R" in card.colors and "G" in card.colors
        assert "arena" in card.games

    async def test_rarity_filter_with_games_filter_om1_spm(
        self, om1_spm_repo: CardRepository
    ) -> None:
        """Test combining rarity filter with games filter on OM1/SPM cards."""
        # Search for mythic Villain creatures in Arena
        result = await om1_spm_repo.search_advanced(
            types=["Villain"], rarity="mythic", games=["arena"]
        )

        # Should find only OM1 Doctor Octopus
        assert len(result.items) == 1
        card = result.items[0]
        assert card.name == "Doctor Octopus"
        assert card.set_code == "OM1"
        assert card.rarity == "mythic"
        assert "arena" in card.games
