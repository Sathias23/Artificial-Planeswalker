"""Unit tests for Pydantic card schemas."""

import pytest
from pydantic import ValidationError

from src.data.schemas.card import Card, CardSummary


def test_card_schema_validation() -> None:
    """Test Card schema validation with valid data."""
    card_data = {
        "id": "test-id-123",
        "name": "Lightning Bolt",
        "oracle_id": "oracle-123",
        "mana_cost": "{R}",
        "cmc": 1.0,
        "type_line": "Instant",
        "oracle_text": "Lightning Bolt deals 3 damage to any target.",
        "rarity": "common",
        "set_code": "LEA",
        "set_name": "Limited Edition Alpha",
        "collector_number": "161",
        "colors": ["R"],
        "color_identity": ["R"],
        "legalities": {"standard": "not_legal", "modern": "legal"},
    }

    card = Card(**card_data)

    assert card.id == "test-id-123"
    assert card.name == "Lightning Bolt"
    assert card.mana_cost == "{R}"
    assert card.cmc == 1.0
    assert card.colors == ["R"]
    assert card.color_identity == ["R"]
    assert card.legalities == {"standard": "not_legal", "modern": "legal"}


def test_card_schema_with_optional_fields() -> None:
    """Test Card schema with optional fields."""
    card_data = {
        "id": "test-id-456",
        "name": "Counterspell",
        "oracle_id": "oracle-456",
        "mana_cost": "{U}{U}",
        "cmc": 2.0,
        "type_line": "Instant",
        "oracle_text": "Counter target spell.",
        "rarity": "common",
        "set_code": "LEA",
        "set_name": "Limited Edition Alpha",
        "collector_number": "54",
        "colors": ["U"],
        "color_identity": ["U"],
        "legalities": {"standard": "not_legal", "modern": "legal"},
        "color_indicator": ["U"],
        "keywords": ["Counter"],
        "card_faces": None,
    }

    card = Card(**card_data)

    assert card.color_indicator == ["U"]
    assert card.keywords == ["Counter"]
    assert card.card_faces is None


def test_card_schema_optional_fields_omitted() -> None:
    """Test Card schema when optional fields are omitted."""
    card_data = {
        "id": "test-id-789",
        "name": "Forest",
        "oracle_id": "oracle-789",
        "mana_cost": "",
        "cmc": 0.0,
        "type_line": "Basic Land — Forest",
        "oracle_text": "{T}: Add {G}.",
        "rarity": "common",
        "set_code": "LEA",
        "set_name": "Limited Edition Alpha",
        "collector_number": "295",
        "colors": [],
        "color_identity": ["G"],
        "legalities": {"standard": "legal", "modern": "legal"},
    }

    card = Card(**card_data)

    assert card.color_indicator is None
    assert card.keywords is None
    assert card.card_faces is None


def test_card_schema_validation_error_invalid_type() -> None:
    """Test Card schema raises ValidationError on invalid types."""
    card_data = {
        "id": "test-id-invalid",
        "name": "Test Card",
        "oracle_id": "oracle-invalid",
        "mana_cost": "{1}",
        "cmc": "one",  # Should be float, not string
        "type_line": "Artifact",
        "oracle_text": "Test card",
        "rarity": "common",
        "set_code": "TST",
        "set_name": "Test Set",
        "collector_number": "1",
        "colors": [],
        "color_identity": [],
        "legalities": {},
    }

    with pytest.raises(ValidationError) as exc_info:
        Card(**card_data)

    assert "cmc" in str(exc_info.value)


def test_card_schema_validation_error_missing_field() -> None:
    """Test Card schema raises ValidationError on missing required field."""
    card_data = {
        "id": "test-id-missing",
        "name": "Test Card",
        # Missing oracle_id
        "mana_cost": "{1}",
        "cmc": 1.0,
        "type_line": "Artifact",
        "oracle_text": "Test card",
        "rarity": "common",
        "set_code": "TST",
        "set_name": "Test Set",
        "collector_number": "1",
        "colors": [],
        "color_identity": [],
        "legalities": {},
    }

    with pytest.raises(ValidationError) as exc_info:
        Card(**card_data)

    assert "oracle_id" in str(exc_info.value)


def test_card_schema_multiface_card() -> None:
    """Test Card schema with multi-face card data."""
    card_faces_data = [
        {
            "name": "Delver of Secrets",
            "mana_cost": "{U}",
            "type_line": "Creature — Human Wizard",
            "oracle_text": "At the beginning of your upkeep, look at the top card of your library.",
        },
        {
            "name": "Insectile Aberration",
            "mana_cost": "",
            "type_line": "Creature — Human Insect",
            "oracle_text": "Flying",
        },
    ]

    card_data = {
        "id": "test-id-dfc",
        "name": "Delver of Secrets // Insectile Aberration",
        "oracle_id": "oracle-dfc",
        "mana_cost": "{U}",
        "cmc": 1.0,
        "type_line": "Creature — Human Wizard // Creature — Human Insect",
        "oracle_text": "",
        "rarity": "common",
        "set_code": "ISD",
        "set_name": "Innistrad",
        "collector_number": "51",
        "colors": ["U"],
        "color_identity": ["U"],
        "legalities": {"standard": "not_legal", "modern": "legal"},
        "card_faces": card_faces_data,
    }

    card = Card(**card_data)

    assert card.card_faces is not None
    assert len(card.card_faces) == 2
    assert card.card_faces[0]["name"] == "Delver of Secrets"


def test_card_summary_from_full_card() -> None:
    """CardSummary.model_validate(<a full Card>) keeps the projected fields and types."""
    card = Card(
        id="card-bolt",
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
        legalities={"standard": "legal", "modern": "legal"},
        image_uris={"normal": "https://example.test/bolt.png"},
    )

    summary = CardSummary.model_validate(card)

    assert summary.id == "card-bolt"
    assert summary.name == "Lightning Bolt"
    assert summary.mana_cost == "{R}"
    assert summary.cmc == 1.0
    assert summary.type_line == "Instant"
    assert summary.oracle_text == "Lightning Bolt deals 3 damage to any target."
    assert summary.colors == ["R"]
    assert summary.rarity == "common"
    assert summary.set_code == "LEA"


def test_card_summary_projects_only_lightweight_fields() -> None:
    """CardSummary drops the heavy detail fields (legalities/image_uris/card_faces)."""
    summary_fields = set(CardSummary.model_fields)

    assert summary_fields == {
        "id",
        "name",
        "mana_cost",
        "cmc",
        "type_line",
        "oracle_text",
        "colors",
        "rarity",
        "set_code",
    }
    assert "legalities" not in summary_fields
    assert "image_uris" not in summary_fields
    assert "card_faces" not in summary_fields
