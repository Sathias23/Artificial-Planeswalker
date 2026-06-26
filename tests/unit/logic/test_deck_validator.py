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
    DeckValidationReport,
    DeckViolation,
    ValidationResult,
    get_current_card_count,
    is_basic_land,
    validate_card_addition,
    validate_deck,
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


# --- validate_deck (whole-deck legality, Story 1.6) ---


def _vd_card(
    card_id: str,
    name: str,
    *,
    type_line: str = "Creature — Goblin",
    legalities: dict[str, str] | None = None,
    games: list[str] | None = None,
    cmc: float = 1.0,
) -> Card:
    """Build a Card for validate_deck tests (standard-legal, all platforms by default)."""
    return Card(
        id=card_id,
        name=name,
        oracle_id=f"oracle-{card_id}",
        mana_cost="{R}",
        cmc=cmc,
        type_line=type_line,
        oracle_text="",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=["R"],
        color_identity=["R"],
        keywords=[],
        legalities=legalities if legalities is not None else {"standard": "legal"},
        games=games if games is not None else ["paper", "arena", "mtgo"],
    )


def _vd_deck_card(card: Card, quantity: int, *, sideboard: bool = False) -> DeckCard:
    """Build a DeckCard wrapping ``card`` (card_id mirrors card.id for combined counting)."""
    return DeckCard(
        deck_id="deck-vd",
        card_id=card.id,
        quantity=quantity,
        sideboard=sideboard,
        card=card,
    )


def _vd_deck(deck_cards: list[DeckCard]) -> Deck:
    """Build a Deck from a list of DeckCards for validate_deck tests."""
    return Deck(
        id="deck-vd",
        name="VD Deck",
        format="standard",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deck_cards=deck_cards,
    )


class TestValidateDeck:
    """Test validate_deck() whole-deck legality logic (D-1.6a/b/c)."""

    def test_legal_60_card_standard_deck(self) -> None:
        """A 60-card mainboard of standard-legal basics has no violations."""
        mountain = _vd_card("mountain", "Mountain", type_line="Basic Land — Mountain", cmc=0.0)
        deck = _vd_deck([_vd_deck_card(mountain, 60)])

        report = validate_deck(deck)

        assert isinstance(report, DeckValidationReport)
        assert report.is_legal is True
        assert report.violations == []
        assert report.format == "standard"
        assert report.mainboard_count == 60
        assert report.sideboard_count == 0

    def test_under_60_mainboard_flags_min_deck_size(self) -> None:
        """A mainboard under 60 cards yields a min_deck_size violation."""
        goblin = _vd_card("goblin", "Goblin Guide")
        deck = _vd_deck([_vd_deck_card(goblin, 4)])

        report = validate_deck(deck)

        assert report.is_legal is False
        assert any(v.rule == "min_deck_size" for v in report.violations)
        assert report.mainboard_count == 4

    def test_oversized_sideboard_flags_max_sideboard_size(self) -> None:
        """A sideboard over 15 cards yields a max_sideboard_size violation."""
        mountain = _vd_card("mountain", "Mountain", type_line="Basic Land — Mountain", cmc=0.0)
        side_basic = _vd_card("forest", "Forest", type_line="Basic Land — Forest", cmc=0.0)
        deck = _vd_deck(
            [
                _vd_deck_card(mountain, 60),
                _vd_deck_card(side_basic, 16, sideboard=True),
            ]
        )

        report = validate_deck(deck)

        assert report.sideboard_count == 16
        assert any(v.rule == "max_sideboard_size" for v in report.violations)
        # Mainboard size is fine; basics are copy-limit exempt.
        assert not any(v.rule == "min_deck_size" for v in report.violations)
        assert not any(v.rule == "copy_limit" for v in report.violations)

    def test_five_copies_non_basic_flags_copy_limit(self) -> None:
        """More than 4 copies of a non-basic card yields a copy_limit violation."""
        goblin = _vd_card("goblin", "Goblin Guide")
        deck = _vd_deck([_vd_deck_card(goblin, 5)])

        report = validate_deck(deck)

        copy_violations = [v for v in report.violations if v.rule == "copy_limit"]
        assert len(copy_violations) == 1
        assert copy_violations[0].card_name == "Goblin Guide"

    def test_twenty_basic_lands_no_copy_limit(self) -> None:
        """Basic lands are exempt from the 4-copy limit."""
        mountain = _vd_card("mountain", "Mountain", type_line="Basic Land — Mountain", cmc=0.0)
        deck = _vd_deck([_vd_deck_card(mountain, 20)])

        report = validate_deck(deck)

        assert not any(v.rule == "copy_limit" for v in report.violations)

    def test_non_standard_legal_card_flags_format_legality(self) -> None:
        """A card not legal in the target format yields a format_legality violation."""
        modern_only = _vd_card("modern-card", "Modern Staple", legalities={"modern": "legal"})
        deck = _vd_deck([_vd_deck_card(modern_only, 4)])

        report = validate_deck(deck)

        legality_violations = [v for v in report.violations if v.rule == "format_legality"]
        assert len(legality_violations) == 1
        assert legality_violations[0].card_name == "Modern Staple"

    def test_null_legalities_and_games_coerce_without_raising(self) -> None:
        """A card whose DB ``legalities``/``games`` were NULL coerces to ``{}``/``[]`` at
        construction, so validate_deck never raises AttributeError/TypeError on
        ``card.legalities.get(...)`` / ``set(card.games)`` and still flags both checks
        (nullability-audit regression — closes the 1-4/1-6 deferred items)."""
        null_card = Card(
            id="null-card",
            name="Null Fields",
            oracle_id="oracle-null-card",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Creature — Goblin",
            oracle_text="",
            rarity="common",
            set_code="TST",
            set_name="Test Set",
            collector_number="1",
            colors=["R"],
            color_identity=["R"],
            keywords=[],
            legalities=None,
            games=None,
        )
        # The schema validators coerced the NULLs at construction time.
        assert null_card.legalities == {}
        assert null_card.games == []

        deck = _vd_deck([_vd_deck_card(null_card, 4)])

        # legalities={} -> not legal in standard; games=[] -> unavailable on arena. Neither raises.
        report = validate_deck(deck, games=["arena"])

        assert any(v.rule == "format_legality" for v in report.violations)
        assert any(v.rule == "game_availability" for v in report.violations)

    def test_format_parameter_changes_legality_check(self) -> None:
        """``format`` is a parameter: a modern-only card is legal when format='modern'."""
        modern_only = _vd_card("modern-card", "Modern Staple", legalities={"modern": "legal"})
        deck = _vd_deck([_vd_deck_card(modern_only, 4)])

        report = validate_deck(deck, format="modern")

        assert report.format == "modern"
        assert not any(v.rule == "format_legality" for v in report.violations)

    def test_combined_mainboard_sideboard_copies_flag_copy_limit(self) -> None:
        """3 mainboard + 2 sideboard copies of one non-basic = 5 combined -> copy_limit."""
        goblin = _vd_card("goblin", "Goblin Guide")
        deck = _vd_deck(
            [
                _vd_deck_card(goblin, 3),
                _vd_deck_card(goblin, 2, sideboard=True),
            ]
        )

        report = validate_deck(deck)

        copy_violations = [v for v in report.violations if v.rule == "copy_limit"]
        assert len(copy_violations) == 1
        assert copy_violations[0].card_name == "Goblin Guide"

    def test_games_filter_flags_unavailable_card(self) -> None:
        """``games=['arena']`` flags a paper-only card with a game_availability violation."""
        paper_only = _vd_card("paper-card", "Paper Promo", games=["paper"])
        deck = _vd_deck([_vd_deck_card(paper_only, 4)])

        report = validate_deck(deck, games=["arena"])

        availability_violations = [v for v in report.violations if v.rule == "game_availability"]
        assert len(availability_violations) == 1
        assert availability_violations[0].card_name == "Paper Promo"

    def test_games_none_skips_availability_check(self) -> None:
        """``games=None`` (default) performs no availability check."""
        paper_only = _vd_card("paper-card", "Paper Promo", games=["paper"])
        deck = _vd_deck([_vd_deck_card(paper_only, 4)])

        report = validate_deck(deck, games=None)

        assert not any(v.rule == "game_availability" for v in report.violations)

    def test_empty_deck_is_illegal_with_min_deck_size(self) -> None:
        """An empty deck is illegal (0/60) with a min_deck_size violation (D-1.6f)."""
        deck = _vd_deck([])

        report = validate_deck(deck)

        assert report.is_legal is False
        assert report.mainboard_count == 0
        assert any(v.rule == "min_deck_size" for v in report.violations)

    def test_violation_is_pydantic_model(self) -> None:
        """DeckViolation is a Pydantic model carrying rule/card_name/detail."""
        violation = DeckViolation(rule="copy_limit", card_name="X", detail="too many")
        assert violation.rule == "copy_limit"
        assert violation.card_name == "X"
        assert violation.detail == "too many"
