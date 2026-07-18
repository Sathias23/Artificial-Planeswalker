"""Unit tests for Deck and DeckCard Pydantic schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.data.schemas.card import Card
from src.data.schemas.deck import Deck, DeckCard, DeckCardSummary


def test_deck_schema_validation() -> None:
    """Test Deck schema validation with valid data."""
    deck_data = {
        "id": "deck-123",
        "name": "Mono Red Aggro",
        "format": "standard",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "deck_cards": [],
    }

    deck = Deck(**deck_data)

    assert deck.id == "deck-123"
    assert deck.name == "Mono Red Aggro"
    assert deck.format == "standard"
    assert isinstance(deck.created_at, datetime)
    assert isinstance(deck.updated_at, datetime)
    assert deck.deck_cards == []


def test_deck_schema_validation_with_deck_cards() -> None:
    """Test Deck schema with populated deck_cards list."""
    card_data = {
        "id": "card-456",
        "name": "Lightning Bolt",
        "oracle_id": "oracle-123",
        "mana_cost": "{R}",
        "cmc": 1.0,
        "type_line": "Instant",
        "oracle_text": "Deals 3 damage",
        "rarity": "common",
        "set_code": "LEA",
        "set_name": "Alpha",
        "collector_number": "161",
        "colors": ["R"],
        "color_identity": ["R"],
        "legalities": {"standard": "legal"},
    }

    deck_card_data = {
        "deck_id": "deck-123",
        "card_id": "card-456",
        "quantity": 4,
        "sideboard": False,
        "card": card_data,
    }

    deck_data = {
        "id": "deck-123",
        "name": "Red Deck",
        "format": "standard",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "deck_cards": [deck_card_data],
    }

    deck = Deck(**deck_data)

    assert len(deck.deck_cards) == 1
    assert deck.deck_cards[0].card_id == "card-456"
    assert deck.deck_cards[0].quantity == 4


def test_deck_schema_accepts_any_format() -> None:
    """Test Deck schema accepts any format string (no validation)."""
    deck_data = {
        "id": "deck-custom-format",
        "name": "Test Deck",
        "format": "custom_format",  # Any format string is accepted
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "deck_cards": [],
    }

    # Should not raise - format is just a string with no enum validation
    deck = Deck(**deck_data)
    assert deck.format == "custom_format"


def test_deck_schema_missing_required_field() -> None:
    """Test Deck schema raises ValidationError for missing required field."""
    deck_data = {
        "id": "deck-missing",
        # Missing name
        "format": "standard",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }

    with pytest.raises(ValidationError) as exc_info:
        Deck(**deck_data)

    assert "name" in str(exc_info.value).lower()


def test_deck_card_schema_validation_mainboard() -> None:
    """Test DeckCard schema validation for mainboard card."""
    card_data = {
        "id": "card-456",
        "name": "Lightning Bolt",
        "oracle_id": "oracle-123",
        "mana_cost": "{R}",
        "cmc": 1.0,
        "type_line": "Instant",
        "oracle_text": "Deals 3 damage",
        "rarity": "common",
        "set_code": "LEA",
        "set_name": "Alpha",
        "collector_number": "161",
        "colors": ["R"],
        "color_identity": ["R"],
        "legalities": {"standard": "legal"},
    }

    deck_card_data = {
        "deck_id": "deck-123",
        "card_id": "card-456",
        "quantity": 4,
        "sideboard": False,
        "card": card_data,
    }

    deck_card = DeckCard(**deck_card_data)

    assert deck_card.deck_id == "deck-123"
    assert deck_card.card_id == "card-456"
    assert deck_card.quantity == 4
    assert deck_card.sideboard is False
    assert isinstance(deck_card.card, Card)
    assert deck_card.card.name == "Lightning Bolt"


def test_deck_card_schema_validation_sideboard() -> None:
    """Test DeckCard schema validation for sideboard card."""
    card_data = {
        "id": "card-789",
        "name": "Counterspell",
        "oracle_id": "oracle-456",
        "mana_cost": "{U}{U}",
        "cmc": 2.0,
        "type_line": "Instant",
        "oracle_text": "Counter target spell",
        "rarity": "common",
        "set_code": "LEA",
        "set_name": "Alpha",
        "collector_number": "54",
        "colors": ["U"],
        "color_identity": ["U"],
        "legalities": {"standard": "legal"},
    }

    deck_card_data = {
        "deck_id": "deck-123",
        "card_id": "card-789",
        "quantity": 2,
        "sideboard": True,
        "card": card_data,
    }

    deck_card = DeckCard(**deck_card_data)

    assert deck_card.sideboard is True
    assert deck_card.quantity == 2


def test_deck_card_schema_default_commander() -> None:
    """Test DeckCard schema commander defaults to False when omitted."""
    card_data = {
        "id": "card-456",
        "name": "Lightning Bolt",
        "oracle_id": "oracle-123",
        "mana_cost": "{R}",
        "cmc": 1.0,
        "type_line": "Instant",
        "oracle_text": "Deals 3 damage",
        "rarity": "common",
        "set_code": "LEA",
        "set_name": "Alpha",
        "collector_number": "161",
        "colors": ["R"],
        "color_identity": ["R"],
        "legalities": {"standard": "legal"},
    }

    deck_card = DeckCard(
        deck_id="deck-123",
        card_id="card-456",
        quantity=4,
        sideboard=False,
        card=card_data,
    )

    assert deck_card.commander is False


def test_deck_card_schema_commander_from_orm_attributes() -> None:
    """Test DeckCard.model_validate picks commander=True up from an ORM-like object."""

    class _FakeCardRow:
        id = "card-atraxa"
        name = "Atraxa, Praetors' Voice"
        printed_name = None
        oracle_id = "oracle-atraxa"
        mana_cost = "{G}{W}{U}{B}"
        cmc = 4.0
        type_line = "Legendary Creature — Phyrexian Angel Horror"
        oracle_text = "Flying, vigilance, deathtouch, lifelink"
        rarity = "mythic"
        set_code = "2X2"
        set_name = "Double Masters 2022"
        collector_number = "190"
        colors = ["W", "U", "B", "G"]
        color_identity = ["W", "U", "B", "G"]
        legalities = {"commander": "legal"}

    class _FakeDeckCardRow:
        deck_id = "deck-123"
        card_id = "card-atraxa"
        quantity = 1
        sideboard = False
        commander = True
        card = _FakeCardRow()

    deck_card = DeckCard.model_validate(_FakeDeckCardRow())

    assert deck_card.commander is True
    assert deck_card.sideboard is False


def test_deck_card_summary_default_commander() -> None:
    """Test DeckCardSummary commander defaults to False when omitted."""
    summary = DeckCardSummary(
        card_id="card-456",
        quantity=4,
        sideboard=False,
        card={
            "id": "card-456",
            "name": "Lightning Bolt",
            "mana_cost": "{R}",
            "cmc": 1.0,
            "type_line": "Instant",
            "oracle_text": "Deals 3 damage",
            "colors": ["R"],
            "rarity": "common",
            "set_code": "LEA",
        },
    )

    assert summary.commander is False


def test_deck_card_summary_commander_true() -> None:
    """Test DeckCardSummary carries an explicit commander=True."""
    summary = DeckCardSummary(
        card_id="card-atraxa",
        quantity=1,
        sideboard=False,
        commander=True,
        card={
            "id": "card-atraxa",
            "name": "Atraxa, Praetors' Voice",
            "mana_cost": "{G}{W}{U}{B}",
            "cmc": 4.0,
            "type_line": "Legendary Creature — Phyrexian Angel Horror",
            "oracle_text": "Flying, vigilance, deathtouch, lifelink",
            "colors": ["W", "U", "B", "G"],
            "rarity": "mythic",
            "set_code": "2X2",
        },
    )

    assert summary.commander is True


def test_deck_card_schema_invalid_quantity() -> None:
    """Test DeckCard schema raises ValidationError for quantity < 1."""
    card_data = {
        "id": "card-invalid",
        "name": "Test Card",
        "oracle_id": "oracle-test",
        "mana_cost": "{1}",
        "cmc": 1.0,
        "type_line": "Artifact",
        "oracle_text": "Test",
        "rarity": "common",
        "set_code": "TST",
        "set_name": "Test",
        "collector_number": "1",
        "colors": [],
        "color_identity": [],
        "legalities": {},
    }

    deck_card_data = {
        "deck_id": "deck-123",
        "card_id": "card-invalid",
        "quantity": 0,  # Invalid: must be >= 1
        "sideboard": False,
        "card": card_data,
    }

    with pytest.raises(ValidationError) as exc_info:
        DeckCard(**deck_card_data)

    assert "quantity" in str(exc_info.value).lower()


def test_deck_card_schema_nested_card_validation() -> None:
    """Test DeckCard schema validates nested Card schema."""
    deck_card_data = {
        "deck_id": "deck-123",
        "card_id": "card-invalid",
        "quantity": 1,
        "sideboard": False,
        "card": {
            "id": "card-invalid",
            # Missing required fields
            "name": "Incomplete Card",
        },
    }

    with pytest.raises(ValidationError) as exc_info:
        DeckCard(**deck_card_data)

    # Should fail because Card schema requires more fields
    assert "card" in str(exc_info.value).lower() or "oracle_id" in str(exc_info.value).lower()


def test_deck_schema_with_strategy() -> None:
    """Test Deck schema validation with strategy field."""
    deck_data = {
        "id": "deck-strategy",
        "name": "Control Deck",
        "format": "standard",
        "strategy": "Reactive control with counters and card draw",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "deck_cards": [],
    }

    deck = Deck(**deck_data)

    assert deck.id == "deck-strategy"
    assert deck.name == "Control Deck"
    assert deck.format == "standard"
    assert deck.strategy == "Reactive control with counters and card draw"
    assert deck.deck_cards == []


def test_deck_schema_without_strategy() -> None:
    """Test Deck schema validation without strategy field (defaults to None)."""
    deck_data = {
        "id": "deck-no-strategy",
        "name": "Aggro Deck",
        "format": "standard",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "deck_cards": [],
    }

    deck = Deck(**deck_data)

    assert deck.id == "deck-no-strategy"
    assert deck.name == "Aggro Deck"
    assert deck.format == "standard"
    assert deck.strategy is None  # Should default to None
    assert deck.deck_cards == []


def test_deck_schema_strategy_optional() -> None:
    """Test Deck schema strategy field is truly optional."""
    # Without strategy key
    deck1_data = {
        "id": "deck-1",
        "name": "Deck 1",
        "format": "standard",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    deck1 = Deck(**deck1_data)
    assert deck1.strategy is None

    # With strategy=None
    deck2_data = {
        "id": "deck-2",
        "name": "Deck 2",
        "format": "standard",
        "strategy": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    deck2 = Deck(**deck2_data)
    assert deck2.strategy is None

    # With strategy value
    deck3_data = {
        "id": "deck-3",
        "name": "Deck 3",
        "format": "standard",
        "strategy": "Midrange value",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    deck3 = Deck(**deck3_data)
    assert deck3.strategy == "Midrange value"


def test_deck_schema_color_identity_from_json_string() -> None:
    """Test Deck schema parses color_identity from JSON string."""
    deck_data = {
        "id": "deck-colors",
        "name": "Boros Aggro",
        "format": "standard",
        "color_identity": '["W", "R"]',  # JSON string
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }

    deck = Deck(**deck_data)

    assert deck.color_identity == ["W", "R"]
    assert isinstance(deck.color_identity, list)


def test_deck_schema_color_identity_from_list() -> None:
    """Test Deck schema accepts color_identity as list directly."""
    deck_data = {
        "id": "deck-colors-list",
        "name": "Golgari Midrange",
        "format": "standard",
        "color_identity": ["B", "G"],  # Python list
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }

    deck = Deck(**deck_data)

    assert deck.color_identity == ["B", "G"]


def test_deck_schema_color_identity_empty() -> None:
    """Test Deck schema handles empty color_identity."""
    deck_data = {
        "id": "deck-colorless",
        "name": "Colorless Deck",
        "format": "standard",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }

    deck = Deck(**deck_data)

    assert deck.color_identity == []


def test_deck_schema_tags_from_json_string() -> None:
    """Test Deck schema parses tags from JSON string."""
    deck_data = {
        "id": "deck-tags",
        "name": "Burn Deck",
        "format": "standard",
        "tags": '["aggro", "burn", "red-deck-wins"]',  # JSON string
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }

    deck = Deck(**deck_data)

    assert deck.tags == ["aggro", "burn", "red-deck-wins"]
    assert isinstance(deck.tags, list)


def test_deck_schema_tags_from_list() -> None:
    """Test Deck schema accepts tags as list directly."""
    deck_data = {
        "id": "deck-tags-list",
        "name": "Control Deck",
        "format": "standard",
        "tags": ["control", "counter-magic"],  # Python list
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }

    deck = Deck(**deck_data)

    assert deck.tags == ["control", "counter-magic"]


def test_deck_schema_tags_empty() -> None:
    """Test Deck schema handles empty tags."""
    deck_data = {
        "id": "deck-no-tags",
        "name": "Untagged Deck",
        "format": "standard",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }

    deck = Deck(**deck_data)

    assert deck.tags == []


def test_deck_schema_all_new_fields() -> None:
    """Test Deck schema with all new fields (color_identity, tags)."""
    deck_data = {
        "id": "deck-complete",
        "name": "Selesnya Tokens",
        "format": "standard",
        "strategy": "Go wide with token generation",
        "color_identity": ["W", "G"],
        "tags": ["tokens", "aggro", "go-wide"],
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }

    deck = Deck(**deck_data)

    assert deck.id == "deck-complete"
    assert deck.name == "Selesnya Tokens"
    assert deck.format == "standard"
    assert deck.strategy == "Go wide with token generation"
    assert deck.color_identity == ["W", "G"]
    assert deck.tags == ["tokens", "aggro", "go-wide"]
