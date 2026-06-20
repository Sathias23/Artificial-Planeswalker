"""Unit tests for Scryfall card transformation logic."""

import json
from pathlib import Path

import pytest

from src.data.importers.transformers import transform_scryfall_card


@pytest.fixture
def sample_cards():
    """Load sample Scryfall JSON data."""
    fixture_path = Path(__file__).parent.parent.parent.parent / "fixtures" / "scryfall_sample.json"
    with fixture_path.open(encoding="utf-8") as f:
        return json.load(f)


def test_transform_complete_card(sample_cards):
    """Test transforming a card with all fields present."""
    lightning_bolt = sample_cards[0]
    card = transform_scryfall_card(lightning_bolt)

    assert card is not None
    assert card.id == "f2b9983e-20d4-4d12-9e2c-ec6d9a345787"
    assert card.name == "Lightning Bolt"
    assert card.oracle_id == "4e887119-67d1-47a7-b5e5-d1c05f6e4c6e"
    assert card.mana_cost == "{R}"
    assert card.cmc == 1.0
    assert card.type_line == "Instant"
    assert "3 damage" in card.oracle_text
    assert card.colors == ["R"]
    assert card.color_identity == ["R"]
    assert card.rarity == "common"
    assert card.set_code == "lea"
    assert card.set_name == "Limited Edition Alpha"
    assert card.collector_number == "161"


def test_transform_card_with_empty_mana_cost(sample_cards):
    """Test transforming a land card with empty mana cost."""
    forest = sample_cards[2]
    card = transform_scryfall_card(forest)

    assert card is not None
    assert card.name == "Forest"
    assert card.mana_cost == ""
    assert card.cmc == 0.0
    assert card.type_line == "Basic Land — Forest"
    assert card.colors == []
    assert card.color_identity == ["G"]


def test_transform_multi_face_card(sample_cards):
    """Test transforming a double-faced card with card_faces."""
    delver = sample_cards[3]
    card = transform_scryfall_card(delver)

    assert card is not None
    assert card.name == "Delver of Secrets // Insectile Aberration"
    assert card.card_faces is not None
    assert len(card.card_faces) == 2
    assert card.card_faces[0]["name"] == "Delver of Secrets"
    assert card.card_faces[1]["name"] == "Insectile Aberration"
    assert card.keywords == ["Transform", "Flying"]


def test_transform_card_with_color_indicator(sample_cards):
    """Test transforming a card with color_indicator field."""
    pact = sample_cards[4]
    card = transform_scryfall_card(pact)

    assert card is not None
    assert card.name == "Pact of Negation"
    assert card.color_indicator == ["U"]
    assert card.colors == ["U"]
    assert card.color_identity == ["U"]


def test_transform_card_missing_required_field(sample_cards):
    """Test transforming a card missing required field returns None."""
    invalid_card = sample_cards[5]
    card = transform_scryfall_card(invalid_card)

    # Should return None and log warning (missing oracle_id)
    assert card is None


def test_transform_card_with_null_keywords():
    """Test transforming a card with null keywords field."""
    card_json = {
        "id": "test-id",
        "name": "Test Card",
        "oracle_id": "test-oracle-id",
        "type_line": "Creature",
        "mana_cost": "{1}{W}",
        "cmc": 2.0,
        "oracle_text": "Test text",
        "colors": ["W"],
        "color_identity": ["W"],
        "keywords": None,  # Explicitly null
        "legalities": {},
        "rarity": "common",
        "set": "tst",
        "set_name": "Test Set",
        "collector_number": "1",
    }

    card = transform_scryfall_card(card_json)

    assert card is not None
    assert card.keywords is None


def test_transform_card_with_defaults():
    """Test transforming a minimal card with default values."""
    card_json = {
        "id": "minimal-id",
        "name": "Minimal Card",
        "oracle_id": "minimal-oracle-id",
        "type_line": "Artifact",
        # Missing many optional fields
    }

    card = transform_scryfall_card(card_json)

    assert card is not None
    assert card.name == "Minimal Card"
    assert card.mana_cost == ""
    assert card.cmc == 0.0
    assert card.oracle_text == ""
    assert card.rarity == "common"
    assert card.colors == []
    assert card.color_identity == []
    assert card.legalities == {}
    assert card.keywords is None
    assert card.card_faces is None


def test_transform_empty_dict():
    """Test transforming an empty dictionary returns None."""
    card = transform_scryfall_card({})
    assert card is None


def test_transform_malformed_data():
    """Test transforming malformed data returns None."""
    card_json = {
        "id": "malformed-id",
        "name": "Malformed Card",
        "oracle_id": "malformed-oracle-id",
        "type_line": "Creature",
        "cmc": "not-a-number",  # Invalid type
    }

    card = transform_scryfall_card(card_json)
    # Should handle ValueError and return None
    assert card is None


def test_transform_card_with_image_uris():
    """Test transforming a card with image_uris extracts the field."""
    card_json = {
        "id": "test-id",
        "name": "Test Card",
        "oracle_id": "test-oracle-id",
        "type_line": "Creature",
        "mana_cost": "{1}{W}",
        "cmc": 2.0,
        "oracle_text": "Test text",
        "colors": ["W"],
        "color_identity": ["W"],
        "legalities": {},
        "rarity": "common",
        "set": "tst",
        "set_name": "Test Set",
        "collector_number": "1",
        "image_uris": {
            "small": "https://cards.scryfall.io/small/front/test.jpg",
            "normal": "https://cards.scryfall.io/normal/front/test.jpg",
            "large": "https://cards.scryfall.io/large/front/test.jpg",
            "png": "https://cards.scryfall.io/png/front/test.png",
            "art_crop": "https://cards.scryfall.io/art_crop/front/test.jpg",
            "border_crop": "https://cards.scryfall.io/border_crop/front/test.jpg",
        },
    }

    card = transform_scryfall_card(card_json)

    assert card is not None
    assert card.image_uris is not None
    assert card.image_uris["normal"] == "https://cards.scryfall.io/normal/front/test.jpg"
    assert card.image_uris["small"] == "https://cards.scryfall.io/small/front/test.jpg"
    assert "art_crop" in card.image_uris


def test_transform_card_without_image_uris():
    """Test transforming a card without image_uris sets field to None."""
    card_json = {
        "id": "test-id",
        "name": "Test Card",
        "oracle_id": "test-oracle-id",
        "type_line": "Creature",
        "mana_cost": "{1}{W}",
        "cmc": 2.0,
        "oracle_text": "Test text",
        "colors": ["W"],
        "color_identity": ["W"],
        "legalities": {},
        "rarity": "common",
        "set": "tst",
        "set_name": "Test Set",
        "collector_number": "1",
        # No image_uris field
    }

    card = transform_scryfall_card(card_json)

    assert card is not None
    assert card.image_uris is None
