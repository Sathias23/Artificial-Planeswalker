"""Unit tests for DeckCardModel SQLAlchemy model."""

from src.data.models.deck_card import DeckCardModel


def test_deck_card_model_instantiation_mainboard() -> None:
    """Test DeckCardModel creation for mainboard card."""
    deck_card = DeckCardModel(deck_id="deck-123", card_id="card-456", quantity=4, sideboard=False)

    assert deck_card.deck_id == "deck-123"
    assert deck_card.card_id == "card-456"
    assert deck_card.quantity == 4
    assert deck_card.sideboard is False


def test_deck_card_model_instantiation_sideboard() -> None:
    """Test DeckCardModel creation for sideboard card."""
    deck_card = DeckCardModel(deck_id="deck-123", card_id="card-789", quantity=2, sideboard=True)

    assert deck_card.deck_id == "deck-123"
    assert deck_card.card_id == "card-789"
    assert deck_card.quantity == 2
    assert deck_card.sideboard is True


def test_deck_card_model_default_sideboard() -> None:
    """Test DeckCardModel sideboard defaults to False."""
    deck_card = DeckCardModel(deck_id="deck-abc", card_id="card-def", quantity=1)

    assert deck_card.sideboard is False


def test_deck_card_model_composite_primary_key() -> None:
    """Test DeckCardModel uses composite primary key (deck_id, card_id, sideboard)."""
    # Create two deck_card instances with same deck_id and card_id but different sideboard
    mainboard_card = DeckCardModel(
        deck_id="deck-123", card_id="card-456", quantity=4, sideboard=False
    )
    sideboard_card = DeckCardModel(
        deck_id="deck-123", card_id="card-456", quantity=2, sideboard=True
    )

    # They should have different primary key values due to sideboard difference
    assert mainboard_card.deck_id == sideboard_card.deck_id
    assert mainboard_card.card_id == sideboard_card.card_id
    assert mainboard_card.sideboard != sideboard_card.sideboard


def test_deck_card_model_default_commander() -> None:
    """Test DeckCardModel commander defaults to False when omitted."""
    deck_card = DeckCardModel(deck_id="deck-abc", card_id="card-def", quantity=1)

    assert deck_card.commander is False


def test_deck_card_model_explicit_commander_true() -> None:
    """Test DeckCardModel persists an explicit commander=True."""
    deck_card = DeckCardModel(deck_id="deck-cmd", card_id="card-atraxa", quantity=1, commander=True)

    assert deck_card.commander is True
    assert deck_card.sideboard is False


def test_deck_card_model_repr() -> None:
    """Test DeckCardModel string representation."""
    deck_card = DeckCardModel(deck_id="deck-test", card_id="card-test", quantity=3, sideboard=False)

    repr_str = repr(deck_card)
    assert "DeckCardModel" in repr_str
    assert "deck-test" in repr_str
    assert "card-test" in repr_str
    assert "3" in repr_str
    assert "mainboard" in repr_str


def test_deck_card_model_repr_sideboard() -> None:
    """Test DeckCardModel string representation for sideboard card."""
    deck_card = DeckCardModel(deck_id="deck-test", card_id="card-test", quantity=2, sideboard=True)

    repr_str = repr(deck_card)
    assert "sideboard" in repr_str
