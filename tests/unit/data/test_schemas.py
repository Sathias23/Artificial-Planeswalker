"""Unit tests for Pydantic card schemas."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.data.schemas.card import Card, CardSummary


def _valid_card_kwargs(**overrides: object) -> dict[str, object]:
    """Return a minimal-but-complete set of valid Card kwargs, with overrides applied."""
    data: dict[str, object] = {
        "id": "card-1",
        "name": "Test Card",
        "oracle_id": "oracle-1",
        "mana_cost": "{R}",
        "cmc": 1.0,
        "type_line": "Instant",
        "oracle_text": "Some text.",
        "rarity": "common",
        "set_code": "TST",
        "set_name": "Test Set",
        "collector_number": "1",
        "colors": ["R"],
        "color_identity": ["R"],
        "legalities": {"standard": "legal"},
    }
    data.update(overrides)
    return data


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


# ===== Nullability gate (Epic 1 retro action item #1) =====
# Real Scryfall data stores NULL for these fields on tokens / split cards / lands.
# Epic 2's build_card_embeddings.py composes name + type_line + mana_cost + oracle_text
# over the full corpus, so Card/CardSummary must tolerate NULL by coercing to empty
# defaults rather than raising ValidationError.


@pytest.mark.parametrize("field", ["oracle_text", "mana_cost"])
def test_card_coerces_null_text_field_to_empty_string(field: str) -> None:
    """A NULL oracle_text / mana_cost (split cards, lands) coerces to ''."""
    card = Card(**_valid_card_kwargs(**{field: None}))

    assert getattr(card, field) == ""


def test_card_coerces_null_colors_to_empty_list() -> None:
    """A NULL colors value (colorless cards stored as NULL) coerces to []."""
    card = Card(**_valid_card_kwargs(colors=None))

    assert card.colors == []


def test_card_coerces_null_legalities_to_empty_dict() -> None:
    """A NULL legalities value coerces to {}."""
    card = Card(**_valid_card_kwargs(legalities=None))

    assert card.legalities == {}


def test_card_coerces_null_games_to_empty_list() -> None:
    """A NULL games value coerces to [] (pre-existing behavior, locked by the gate)."""
    card = Card(**_valid_card_kwargs(games=None))

    assert card.games == []


def test_card_model_validate_tolerates_nulls_from_attributes() -> None:
    """The Epic-2 read path (model_validate over an ORM row with NULLs) must not raise."""
    row = SimpleNamespace(
        id="card-split",
        name="Fire // Ice",
        printed_name=None,
        oracle_id="oracle-split",
        mana_cost=None,  # split cards carry mana cost on the faces, not the top level
        cmc=2.0,
        type_line="Instant // Instant",
        oracle_text=None,  # top-level oracle_text is NULL for split cards
        rarity="uncommon",
        set_code="APC",
        set_name="Apocalypse",
        collector_number="128",
        colors=None,
        color_identity=["U", "R"],
        color_indicator=None,
        keywords=None,
        legalities=None,
        card_faces=None,
        image_uris=None,
        games=None,
    )

    card = Card.model_validate(row)

    assert card.mana_cost == ""
    assert card.oracle_text == ""
    assert card.colors == []
    assert card.legalities == {}
    assert card.games == []
    # Composing the embedding text must not blow up on the coerced fields.
    embed_text = f"{card.name} {card.type_line} {card.mana_cost} {card.oracle_text}"
    assert embed_text == "Fire // Ice Instant // Instant  "


@pytest.mark.parametrize("field", ["oracle_text", "mana_cost"])
def test_card_summary_coerces_null_text_field_to_empty_string(field: str) -> None:
    """CardSummary tolerates NULL oracle_text / mana_cost the same way Card does."""
    full = Card(**_valid_card_kwargs(**{field: None}))

    summary = CardSummary.model_validate(full)

    assert getattr(summary, field) == ""


def test_card_summary_coerces_null_colors_to_empty_list() -> None:
    """CardSummary tolerates NULL colors."""
    full = Card(**_valid_card_kwargs(colors=None))

    summary = CardSummary.model_validate(full)

    assert summary.colors == []


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
