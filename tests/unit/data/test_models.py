"""Unit tests for SQLAlchemy card models."""

from src.data.models.card import CardModel


def test_card_model_instantiation_with_required_fields() -> None:
    """Test CardModel creation with only required fields."""
    card = CardModel(
        id="test-id-123",
        name="Lightning Bolt",
        oracle_id="oracle-123",
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
    )

    assert card.id == "test-id-123"
    assert card.name == "Lightning Bolt"
    assert card.mana_cost == "{R}"
    assert card.cmc == 1.0
    assert card.type_line == "Instant"
    assert card.colors == ["R"]
    assert card.color_identity == ["R"]
    assert card.legalities == {"standard": "not_legal", "modern": "legal"}


def test_card_model_with_optional_fields_none() -> None:
    """Test CardModel with optional fields set to None."""
    card = CardModel(
        id="test-id-456",
        name="Forest",
        oracle_id="oracle-456",
        mana_cost="",
        cmc=0.0,
        type_line="Basic Land — Forest",
        oracle_text="{T}: Add {G}.",
        rarity="common",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="295",
        colors=[],
        color_identity=["G"],
        legalities={"standard": "legal", "modern": "legal"},
        color_indicator=None,
        keywords=None,
        card_faces=None,
    )

    assert card.color_indicator is None
    assert card.keywords is None
    assert card.card_faces is None


def test_card_model_with_optional_fields_provided() -> None:
    """Test CardModel with optional fields populated."""
    card = CardModel(
        id="test-id-789",
        name="Counterspell",
        oracle_id="oracle-789",
        mana_cost="{U}{U}",
        cmc=2.0,
        type_line="Instant",
        oracle_text="Counter target spell.",
        rarity="common",
        set_code="LEA",
        set_name="Limited Edition Alpha",
        collector_number="54",
        colors=["U"],
        color_identity=["U"],
        legalities={"standard": "not_legal", "modern": "legal"},
        color_indicator=["U"],
        keywords=["Counter"],
        card_faces=None,
    )

    assert card.color_indicator == ["U"]
    assert card.keywords == ["Counter"]


def test_card_model_multiface_card() -> None:
    """Test CardModel with multi-face card data."""
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

    card = CardModel(
        id="test-id-dfc",
        name="Delver of Secrets // Insectile Aberration",
        oracle_id="oracle-dfc",
        mana_cost="{U}",
        cmc=1.0,
        type_line="Creature — Human Wizard // Creature — Human Insect",
        oracle_text="",
        rarity="common",
        set_code="ISD",
        set_name="Innistrad",
        collector_number="51",
        colors=["U"],
        color_identity=["U"],
        legalities={"standard": "not_legal", "modern": "legal"},
        card_faces=card_faces_data,
    )

    assert card.card_faces is not None
    assert len(card.card_faces) == 2
    assert card.card_faces[0]["name"] == "Delver of Secrets"
    assert card.card_faces[1]["name"] == "Insectile Aberration"


def test_card_model_repr() -> None:
    """Test CardModel string representation."""
    card = CardModel(
        id="test-repr",
        name="Test Card",
        oracle_id="oracle-repr",
        mana_cost="{1}",
        cmc=1.0,
        type_line="Artifact",
        oracle_text="Test card",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=[],
        color_identity=[],
        legalities={},
    )

    assert repr(card) == "<CardModel(id='test-repr', name='Test Card')>"
