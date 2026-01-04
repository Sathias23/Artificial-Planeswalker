"""Unit tests for deck validation business logic.

Tests validate deck construction rule enforcement including:
- 4-copy limit for non-basic lands
- Unlimited basic lands
- Clear error messages
- Type safety
"""

from datetime import UTC, datetime

import pytest

from src.data.schemas.card import Card
from src.data.schemas.deck import Deck, DeckCard
from src.logic.deck_validator import (
    ValidationResult,
    get_current_card_count,
    is_basic_land,
    validate_card_addition,
)


# Test fixtures - sample cards
@pytest.fixture
def lightning_bolt() -> Card:
    """Create a Lightning Bolt card (instant, not basic land)."""
    return Card(
        id="bolt-id",
        name="Lightning Bolt",
        oracle_id="bolt-oracle",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Lightning Bolt deals 3 damage to any target.",
        rarity="uncommon",
        set_code="M11",
        set_name="Magic 2011",
        collector_number="146",
        colors=["R"],
        color_identity=["R"],
        keywords=[],
        legalities={"standard": "legal"},
    )


@pytest.fixture
def mountain() -> Card:
    """Create a Mountain card (basic land)."""
    return Card(
        id="mountain-id",
        name="Mountain",
        oracle_id="mountain-oracle",
        mana_cost="",
        cmc=0.0,
        type_line="Basic Land — Mountain",
        oracle_text="{T}: Add {R}.",
        rarity="common",
        set_code="M21",
        set_name="Core Set 2021",
        collector_number="274",
        colors=[],
        color_identity=["R"],
        keywords=[],
        legalities={"standard": "legal"},
    )


@pytest.fixture
def shock_land() -> Card:
    """Create a Shock Land card (non-basic land)."""
    return Card(
        id="shock-id",
        name="Steam Vents",
        oracle_id="shock-oracle",
        mana_cost="",
        cmc=0.0,
        type_line="Land — Island Mountain",
        oracle_text="As Steam Vents enters, you may pay 2 life. If you don't, it enters tapped.",
        rarity="rare",
        set_code="GRN",
        set_name="Guilds of Ravnica",
        collector_number="257",
        colors=[],
        color_identity=["U", "R"],
        keywords=[],
        legalities={"standard": "legal"},
    )


@pytest.fixture
def empty_deck() -> Deck:
    """Create an empty deck with no cards."""
    return Deck(
        id="deck-empty",
        name="Empty Deck",
        format="standard",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deck_cards=[],
    )


class TestIsBasicLand:
    """Test is_basic_land() helper function."""

    def test_basic_land_mountain(self, mountain: Card) -> None:
        """Test that Mountain is identified as a basic land."""
        assert is_basic_land(mountain) is True

    def test_basic_land_forest(self) -> None:
        """Test that Forest is identified as a basic land."""
        forest = Card(
            id="forest-id",
            name="Forest",
            oracle_id="forest-oracle",
            mana_cost="",
            cmc=0.0,
            type_line="Basic Land — Forest",
            oracle_text="{T}: Add {G}.",
            rarity="common",
            set_code="M21",
            set_name="Core Set 2021",
            collector_number="277",
            colors=[],
            color_identity=["G"],
            keywords=[],
            legalities={"standard": "legal"},
        )
        assert is_basic_land(forest) is True

    def test_non_basic_land(self, shock_land: Card) -> None:
        """Test that non-basic lands are identified correctly."""
        assert is_basic_land(shock_land) is False

    def test_creature_not_basic_land(self) -> None:
        """Test that creature cards are not identified as basic lands."""
        goblin = Card(
            id="goblin-id",
            name="Goblin Warrior",
            oracle_id="goblin-oracle",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Creature — Goblin Warrior",
            oracle_text="",
            rarity="common",
            set_code="M21",
            set_name="Core Set 2021",
            collector_number="148",
            colors=["R"],
            color_identity=["R"],
            keywords=[],
            legalities={"standard": "legal"},
        )
        assert is_basic_land(goblin) is False

    def test_instant_not_basic_land(self, lightning_bolt: Card) -> None:
        """Test that instant cards are not identified as basic lands."""
        assert is_basic_land(lightning_bolt) is False

    def test_case_insensitive_detection(self) -> None:
        """Test that basic land detection is case-insensitive."""
        uppercase_basic = Card(
            id="basic-id",
            name="Plains",
            oracle_id="plains-oracle",
            mana_cost="",
            cmc=0.0,
            type_line="BASIC LAND — Plains",
            oracle_text="{T}: Add {W}.",
            rarity="common",
            set_code="M21",
            set_name="Core Set 2021",
            collector_number="261",
            colors=[],
            color_identity=["W"],
            keywords=[],
            legalities={"standard": "legal"},
        )
        assert is_basic_land(uppercase_basic) is True


class TestGetCurrentCardCount:
    """Test get_current_card_count() helper function."""

    def test_card_not_in_deck(self, empty_deck: Deck) -> None:
        """Test that count is 0 for cards not in the deck."""
        assert get_current_card_count(empty_deck, "nonexistent-id") == 0

    def test_card_in_mainboard(self, lightning_bolt: Card) -> None:
        """Test counting cards in mainboard."""
        deck = Deck(
            id="deck-1",
            name="Test Deck",
            format="standard",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deck_cards=[
                DeckCard(
                    deck_id="deck-1",
                    card_id="bolt-id",
                    quantity=3,
                    sideboard=False,
                    card=lightning_bolt,
                )
            ],
        )
        assert get_current_card_count(deck, "bolt-id") == 3

    def test_card_in_both_mainboard_and_sideboard(self, lightning_bolt: Card) -> None:
        """Test that only mainboard cards are counted (sideboard excluded)."""
        deck = Deck(
            id="deck-1",
            name="Test Deck",
            format="standard",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deck_cards=[
                DeckCard(
                    deck_id="deck-1",
                    card_id="bolt-id",
                    quantity=2,
                    sideboard=False,
                    card=lightning_bolt,
                ),
                DeckCard(
                    deck_id="deck-1",
                    card_id="bolt-id",
                    quantity=1,
                    sideboard=True,
                    card=lightning_bolt,
                ),
            ],
        )
        assert get_current_card_count(deck, "bolt-id") == 2

    def test_card_only_in_sideboard(self, lightning_bolt: Card) -> None:
        """Test that sideboard-only cards return 0."""
        deck = Deck(
            id="deck-1",
            name="Test Deck",
            format="standard",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deck_cards=[
                DeckCard(
                    deck_id="deck-1",
                    card_id="bolt-id",
                    quantity=2,
                    sideboard=True,
                    card=lightning_bolt,
                )
            ],
        )
        assert get_current_card_count(deck, "bolt-id") == 0

    def test_empty_deck_returns_zero(self, empty_deck: Deck) -> None:
        """Test that empty deck returns 0 for any card."""
        assert get_current_card_count(empty_deck, "any-card-id") == 0


class TestValidateCardAddition:
    """Test validate_card_addition() function."""

    def test_valid_addition_under_4_copy_limit(
        self, lightning_bolt: Card, empty_deck: Deck
    ) -> None:
        """Test valid addition when under 4-copy limit."""
        result = validate_card_addition(empty_deck, lightning_bolt, 4)
        assert result.is_valid is True
        assert result.error_message is None

    def test_valid_addition_with_existing_cards(self, lightning_bolt: Card) -> None:
        """Test valid addition when deck has existing cards but won't exceed limit."""
        deck = Deck(
            id="deck-1",
            name="Test Deck",
            format="standard",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deck_cards=[
                DeckCard(
                    deck_id="deck-1",
                    card_id="bolt-id",
                    quantity=2,
                    sideboard=False,
                    card=lightning_bolt,
                )
            ],
        )
        result = validate_card_addition(deck, lightning_bolt, 2)
        assert result.is_valid is True
        assert result.error_message is None

    def test_invalid_exceeding_4_copy_limit(self, lightning_bolt: Card) -> None:
        """Test that adding cards would exceed 4-copy limit."""
        deck = Deck(
            id="deck-1",
            name="Test Deck",
            format="standard",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deck_cards=[
                DeckCard(
                    deck_id="deck-1",
                    card_id="bolt-id",
                    quantity=3,
                    sideboard=False,
                    card=lightning_bolt,
                )
            ],
        )
        result = validate_card_addition(deck, lightning_bolt, 2)
        assert result.is_valid is False
        assert result.error_message is not None
        assert "Cannot add 2 copies" in result.error_message
        assert "Lightning Bolt" in result.error_message
        assert "5 copies" in result.error_message
        assert "max 4" in result.error_message

    def test_invalid_already_at_limit(self, lightning_bolt: Card) -> None:
        """Test adding to deck that already has 4 copies."""
        deck = Deck(
            id="deck-1",
            name="Test Deck",
            format="standard",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deck_cards=[
                DeckCard(
                    deck_id="deck-1",
                    card_id="bolt-id",
                    quantity=4,
                    sideboard=False,
                    card=lightning_bolt,
                )
            ],
        )
        result = validate_card_addition(deck, lightning_bolt, 1)
        assert result.is_valid is False
        assert result.error_message is not None
        assert "Cannot add 1 copy" in result.error_message
        assert "already has 4 copies" in result.error_message

    def test_valid_basic_land_exceeding_4_copies(self, mountain: Card) -> None:
        """Test that basic lands can exceed 4-copy limit."""
        deck = Deck(
            id="deck-1",
            name="Test Deck",
            format="standard",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deck_cards=[
                DeckCard(
                    deck_id="deck-1",
                    card_id="mountain-id",
                    quantity=15,
                    sideboard=False,
                    card=mountain,
                )
            ],
        )
        result = validate_card_addition(deck, mountain, 10)
        assert result.is_valid is True
        assert result.error_message is None

    def test_adding_to_empty_deck(self, lightning_bolt: Card, empty_deck: Deck) -> None:
        """Test adding to an empty deck."""
        result = validate_card_addition(empty_deck, lightning_bolt, 4)
        assert result.is_valid is True
        assert result.error_message is None

    def test_adding_basic_land_to_empty_deck(self, mountain: Card, empty_deck: Deck) -> None:
        """Test adding basic land to empty deck."""
        result = validate_card_addition(empty_deck, mountain, 20)
        assert result.is_valid is True
        assert result.error_message is None


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_valid_result_creation(self) -> None:
        """Test creating a valid ValidationResult."""
        result = ValidationResult(is_valid=True, error_message=None)
        assert result.is_valid is True
        assert result.error_message is None

    def test_invalid_result_creation(self) -> None:
        """Test creating an invalid ValidationResult with error message."""
        result = ValidationResult(is_valid=False, error_message="Exceeds 4-copy limit")
        assert result.is_valid is False
        assert result.error_message == "Exceeds 4-copy limit"

    def test_result_is_dataclass(self) -> None:
        """Test that ValidationResult is a dataclass."""
        from dataclasses import is_dataclass

        assert is_dataclass(ValidationResult)

    def test_result_has_type_hints(self) -> None:
        """Test that ValidationResult has type hints."""
        import typing

        # Get type hints for ValidationResult
        hints = typing.get_type_hints(ValidationResult)
        assert "is_valid" in hints
        assert "error_message" in hints
        assert hints["is_valid"] is bool
        # Check error_message is a union type of str and None
        assert hints["error_message"] == (str | None)


class TestErrorMessageClarity:
    """Test error message formatting and clarity."""

    def test_error_message_for_exceeding_limit(self, lightning_bolt: Card) -> None:
        """Test error message format when exceeding limit."""
        deck = Deck(
            id="deck-1",
            name="Test Deck",
            format="standard",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deck_cards=[
                DeckCard(
                    deck_id="deck-1",
                    card_id="bolt-id",
                    quantity=3,
                    sideboard=False,
                    card=lightning_bolt,
                )
            ],
        )
        result = validate_card_addition(deck, lightning_bolt, 2)

        assert result.error_message is not None
        # Error message should include:
        # - Quantity being added (2)
        # - Card name (Lightning Bolt)
        # - Total after addition (5)
        # - Maximum allowed (4)
        assert "2 copies" in result.error_message
        assert "Lightning Bolt" in result.error_message
        assert "5 copies" in result.error_message
        assert "max 4 for non-basic lands" in result.error_message

    def test_error_message_when_already_at_limit(self, lightning_bolt: Card) -> None:
        """Test error message when deck already has 4 copies."""
        deck = Deck(
            id="deck-1",
            name="Test Deck",
            format="standard",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deck_cards=[
                DeckCard(
                    deck_id="deck-1",
                    card_id="bolt-id",
                    quantity=4,
                    sideboard=False,
                    card=lightning_bolt,
                )
            ],
        )
        result = validate_card_addition(deck, lightning_bolt, 1)

        assert result.error_message is not None
        # Error message should clearly state deck already has maximum
        assert "already has 4 copies" in result.error_message
        assert "Lightning Bolt" in result.error_message
        assert "max 4 for non-basic lands" in result.error_message

    def test_singular_copy_in_error_message(self, lightning_bolt: Card) -> None:
        """Test that error message uses 'copy' (singular) when quantity is 1."""
        deck = Deck(
            id="deck-1",
            name="Test Deck",
            format="standard",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deck_cards=[
                DeckCard(
                    deck_id="deck-1",
                    card_id="bolt-id",
                    quantity=4,
                    sideboard=False,
                    card=lightning_bolt,
                )
            ],
        )
        result = validate_card_addition(deck, lightning_bolt, 1)

        assert result.error_message is not None
        assert "1 copy" in result.error_message
        # Should NOT contain "1 copies"
        assert "1 copies" not in result.error_message
