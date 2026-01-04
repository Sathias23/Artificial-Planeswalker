"""Unit tests for card lookup tool."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import RunContext

from src.agent.dependencies import AgentDependencies
from src.agent.tools.card_lookup import lookup_card_by_name
from src.data.schemas.card import Card

# Fixtures


@pytest.fixture
def sample_card() -> Card:
    """Create a sample Card for testing."""
    return Card(
        id="test-id-123",
        name="Lightning Bolt",
        oracle_id="oracle-123",
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
def double_faced_card() -> Card:
    """Create a double-faced card for testing (matches Scryfall data structure)."""
    return Card(
        id="test-id-456",
        name="Delver of Secrets // Insectile Aberration",
        oracle_id="oracle-456",
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
        card_faces=[
            {
                "name": "Delver of Secrets",
                "mana_cost": "{U}",
                "type_line": "Creature — Human Wizard",
                "oracle_text": (
                    "At the beginning of your upkeep, look at the top card of your library..."
                ),
            },
            {
                "name": "Insectile Aberration",
                "type_line": "Creature — Human Insect",
                "oracle_text": "Flying",
            },
        ],
    )


@pytest.fixture
def colorless_card() -> Card:
    """Create a colorless card for testing."""
    return Card(
        id="test-id-789",
        name="Sol Ring",
        oracle_id="oracle-789",
        mana_cost="{1}",
        cmc=1.0,
        type_line="Artifact",
        oracle_text="{T}: Add {C}{C}.",
        rarity="uncommon",
        set_code="lea",
        set_name="Limited Edition Alpha",
        collector_number="268",
        colors=[],  # Colorless
        color_identity=[],
        legalities={"standard": "not_legal", "vintage": "restricted"},
    )


@pytest.fixture
def long_oracle_text_card() -> Card:
    """Create a card with very long oracle text for truncation testing."""
    long_text = "This is a very long oracle text. " * 20  # 680 chars
    return Card(
        id="test-id-long",
        name="Wordy Card",
        oracle_id="oracle-long",
        mana_cost="{3}{U}{U}",
        cmc=5.0,
        type_line="Enchantment",
        oracle_text=long_text,
        rarity="rare",
        set_code="test",
        set_name="Test Set",
        collector_number="1",
        colors=["U"],
        color_identity=["U"],
        legalities={"standard": "legal"},
    )


@pytest.fixture
def mock_card_repository():
    """Create a mock CardRepository for testing."""
    repo = MagicMock()
    repo.find_by_name_exact = AsyncMock()
    repo.find_by_name_partial = AsyncMock()
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


# Tests for lookup_card_by_name
# Note: Card formatting is now tested in tests/unit/ui/test_formatters.py


class TestLookupCardByName:
    """Tests for the lookup_card_by_name tool."""

    @pytest.mark.asyncio
    async def test_exact_match_found(self, mock_run_context, sample_card):
        """Test successful exact match returns formatted card."""
        mock_run_context.deps.card_repository.find_by_name_exact.return_value = sample_card

        result = await lookup_card_by_name(mock_run_context, "Lightning Bolt")

        # Verify repository was called correctly
        # Note: format_filter comes from ctx.deps.format_filter (default None)
        mock_run_context.deps.card_repository.find_by_name_exact.assert_called_once_with(
            "Lightning Bolt", format_filter=mock_run_context.deps.format_filter
        )
        # Verify formatted card is returned (new markdown format)
        assert "**Lightning Bolt**" in result
        assert "Mana Cost: {R}" in result
        assert "*Instant*" in result

    @pytest.mark.asyncio
    async def test_partial_match_single_result(
        self, mock_run_context, sample_card, mock_card_repository
    ):
        """Test partial match with single result returns that card."""
        # Exact match fails
        mock_card_repository.find_by_name_exact.return_value = None
        # Partial match finds one card
        mock_card_repository.find_by_name_partial.return_value = [sample_card]

        result = await lookup_card_by_name(mock_run_context, "Lightning")

        # Verify both queries were attempted
        mock_card_repository.find_by_name_exact.assert_called_once_with(
            "Lightning", format_filter=mock_run_context.deps.format_filter
        )
        mock_card_repository.find_by_name_partial.assert_called_once_with(
            "Lightning", format_filter=mock_run_context.deps.format_filter
        )
        # Verify formatted card is returned (new markdown format)
        assert "**Lightning Bolt**" in result

    @pytest.mark.asyncio
    async def test_partial_match_multiple_results(self, mock_run_context, mock_card_repository):
        """Test partial match with 2-10 results returns list."""
        # Create multiple cards
        cards = [
            Card(
                id=f"id-{i}",
                name=f"Bolt Card {i}",
                oracle_id=f"oracle-{i}",
                mana_cost="{R}",
                cmc=1.0,
                type_line="Instant",
                oracle_text="Test text",
                rarity="common",
                set_code="test",
                set_name="Test Set",
                collector_number=str(i),
                colors=["R"],
                color_identity=["R"],
                legalities={},
            )
            for i in range(5)
        ]

        mock_card_repository.find_by_name_exact.return_value = None
        mock_card_repository.find_by_name_partial.return_value = cards

        result = await lookup_card_by_name(mock_run_context, "Bolt")

        assert "I found 5 cards matching 'Bolt'" in result
        assert "Which one did you mean?" in result
        # Verify all card names are listed
        for card in cards:
            assert card.name in result

    @pytest.mark.asyncio
    async def test_partial_match_many_results(self, mock_run_context, mock_card_repository):
        """Test partial match with >10 results returns truncated list."""
        # Create 15 cards
        cards = [
            Card(
                id=f"id-{i}",
                name=f"Bolt Card {i}",
                oracle_id=f"oracle-{i}",
                mana_cost="{R}",
                cmc=1.0,
                type_line="Instant",
                oracle_text="Test text",
                rarity="common",
                set_code="test",
                set_name="Test Set",
                collector_number=str(i),
                colors=["R"],
                color_identity=["R"],
                legalities={},
            )
            for i in range(15)
        ]

        mock_card_repository.find_by_name_exact.return_value = None
        mock_card_repository.find_by_name_partial.return_value = cards

        result = await lookup_card_by_name(mock_run_context, "Bolt")

        assert "I found 15 cards matching 'Bolt'" in result
        # New format uses "...and 5 more results" instead of "Here are the first 10:"
        assert "...and 5 more results" in result
        assert "Which one did you mean?" in result
        # Verify only first 10 card names are listed
        for card in cards[:10]:
            assert card.name in result
        # Verify cards beyond 10 are not listed
        for card in cards[10:]:
            assert card.name not in result

    @pytest.mark.asyncio
    async def test_no_match_found(self, mock_run_context, mock_card_repository):
        """Test no match found returns helpful message."""
        mock_card_repository.find_by_name_exact.return_value = None
        mock_card_repository.find_by_name_partial.return_value = []

        result = await lookup_card_by_name(mock_run_context, "Nonexistent Card")

        assert "I couldn't find a card matching 'Nonexistent Card'" in result
        assert "check the spelling" in result

    @pytest.mark.asyncio
    async def test_handles_double_faced_card(self, mock_run_context, double_faced_card):
        """Test that double-faced cards are formatted correctly with both faces."""
        mock_run_context.deps.card_repository.find_by_name_exact.return_value = double_faced_card

        result = await lookup_card_by_name(mock_run_context, "Delver of Secrets")

        # Verify dual-faced card formatting includes both faces
        assert "**Delver of Secrets" in result  # Card name (may have // back face)
        assert "**Front Face:**" in result
        assert "**Back Face:**" in result
        # Verify oracle text from both faces
        assert "At the beginning of your upkeep" in result
        assert "Flying" in result or "Insectile Aberration" in result

    @pytest.mark.asyncio
    async def test_handles_colorless_card(self, mock_run_context, colorless_card):
        """Test that colorless cards with mana cost don't show Colors line."""
        mock_run_context.deps.card_repository.find_by_name_exact.return_value = colorless_card

        result = await lookup_card_by_name(mock_run_context, "Sol Ring")

        # Colorless cards with mana cost ({1}) don't show a Colors line
        # "Colorless" only appears for cards without mana cost AND no colors (like lands)
        assert "**Sol Ring**" in result
        assert "Mana Cost: {1}" in result
        assert "*Artifact*" in result
        # Should not have "Colors:" line at all for colorless artifacts
        assert "Colors:" not in result or "Colorless" in result

    @pytest.mark.asyncio
    async def test_query_with_special_characters(self, mock_run_context, mock_card_repository):
        """Test that queries with special characters are handled."""
        card = Card(
            id="test-id-jace",
            name="Jace, the Mind Sculptor",
            oracle_id="oracle-jace",
            mana_cost="{2}{U}{U}",
            cmc=4.0,
            type_line="Legendary Planeswalker — Jace",
            oracle_text="[+2]: Look at the top card...",
            rarity="mythic",
            set_code="wwk",
            set_name="Worldwake",
            collector_number="31",
            colors=["U"],
            color_identity=["U"],
            legalities={"modern": "banned"},
        )

        mock_card_repository.find_by_name_exact.return_value = card

        result = await lookup_card_by_name(mock_run_context, "Jace, the Mind Sculptor")

        # New markdown format
        assert "**Jace, the Mind Sculptor**" in result
        assert "*Legendary Planeswalker" in result
