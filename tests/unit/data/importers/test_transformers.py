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


def test_transform_reversible_card_uses_face_oracle_id():
    """A reversible/multi-face card with no top-level ``oracle_id`` imports using the face-level
    id (matching ``group_key``), instead of being dropped as missing-required-field.

    Regression for the inert ``card_faces[0].oracle_id`` fallback: pass 1 grouped such cards by
    their face oracle id, but the transformer's hard top-level ``oracle_id`` requirement then
    rejected them, so reversible-layout cards never reached the database.
    """
    reversible = {
        "id": "printing-1",
        "name": "Zndrsplt, Eye of Wisdom // Okaun, Eye of Chaos",
        "type_line": "Legendary Creature — Homunculus",
        "card_faces": [
            {"oracle_id": "face-oracle-id", "name": "Zndrsplt"},
            {"name": "Okaun"},
        ],
    }

    card = transform_scryfall_card(reversible)

    assert card is not None
    assert card.oracle_id == "face-oracle-id"


def test_transform_card_with_no_oracle_id_anywhere_returns_none():
    """A card carrying no oracle id at any level (top or face) is still dropped."""
    card_json = {
        "id": "printing-2",
        "name": "No Oracle Anywhere",
        "type_line": "Instant",
        "card_faces": [{"name": "front"}],
    }

    assert transform_scryfall_card(card_json) is None


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


def test_transform_card_with_explicit_null_fields():
    """Explicit JSON nulls on non-nullable fields must coerce to empty defaults, not None.

    Scryfall (and especially tokens/split cards) can send `"field": null`. dict.get(k, d)
    returns the default only for MISSING keys, so a present-but-null value slips through as
    None and would write a NULL into a non-nullable column. Keep NULLs out at the source.
    """
    card_json = {
        "id": "null-fields-id",
        "name": "Null Fields Card",
        "oracle_id": "null-fields-oracle",
        "type_line": "Token Creature",
        "mana_cost": None,
        "oracle_text": None,
        "colors": None,
        "color_identity": None,
        "legalities": None,
        "rarity": "common",
        "set": "tst",
        "set_name": "Test Set",
        "collector_number": "1",
    }

    card = transform_scryfall_card(card_json)

    assert card is not None
    assert card.mana_cost == ""
    assert card.oracle_text == ""
    assert card.colors == []
    assert card.color_identity == []
    assert card.legalities == {}


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


def test_transform_creature_extracts_power_toughness():
    """A creature's power/toughness are captured as Scryfall strings."""
    card_json = {
        "id": "creature-id",
        "name": "Grizzly Bears",
        "oracle_id": "grizzly-oracle-id",
        "type_line": "Creature — Bear",
        "mana_cost": "{1}{G}",
        "cmc": 2.0,
        "oracle_text": "",
        "colors": ["G"],
        "color_identity": ["G"],
        "legalities": {},
        "rarity": "common",
        "set": "tst",
        "set_name": "Test Set",
        "collector_number": "1",
        "power": "2",
        "toughness": "2",
    }

    card = transform_scryfall_card(card_json)

    assert card is not None
    assert card.power == "2"
    assert card.toughness == "2"


def test_transform_noncreature_has_no_power_toughness():
    """Non-creatures (no P/T in the Scryfall JSON) leave the columns None."""
    card_json = {
        "id": "instant-id",
        "name": "Shock",
        "oracle_id": "shock-oracle-id",
        "type_line": "Instant",
        "mana_cost": "{R}",
        "cmc": 1.0,
        "oracle_text": "Shock deals 2 damage to any target.",
        "colors": ["R"],
        "color_identity": ["R"],
        "legalities": {},
        "rarity": "common",
        "set": "tst",
        "set_name": "Test Set",
        "collector_number": "1",
    }

    card = transform_scryfall_card(card_json)

    assert card is not None
    assert card.power is None
    assert card.toughness is None
