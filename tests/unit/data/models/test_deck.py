"""Unit tests for DeckModel SQLAlchemy model."""

from datetime import UTC, datetime

from src.data.models.deck import DeckModel


def test_deck_model_instantiation_with_required_fields() -> None:
    """Test DeckModel creation with only required fields."""
    deck = DeckModel(name="Mono Red Aggro", format="standard")

    assert deck.name == "Mono Red Aggro"
    assert deck.format == "standard"
    # ID should be auto-generated
    assert deck.id is not None
    assert isinstance(deck.id, str)
    assert len(deck.id) > 0
    # Timestamps should be auto-generated
    assert isinstance(deck.created_at, datetime)
    assert isinstance(deck.updated_at, datetime)
    # Timestamps should be in UTC
    assert deck.created_at.tzinfo is not None
    assert deck.updated_at.tzinfo is not None


def test_deck_model_default_values() -> None:
    """Test DeckModel default values for auto-managed fields."""
    deck = DeckModel(name="Control Deck", format="standard")

    # Verify timestamps are recent (within last minute)
    now = datetime.now(UTC)
    time_diff_created = (now - deck.created_at).total_seconds()
    time_diff_updated = (now - deck.updated_at).total_seconds()

    assert 0 <= time_diff_created < 60, "created_at should be recent"
    assert 0 <= time_diff_updated < 60, "updated_at should be recent"
    # Timestamps should be very close (within 1 second)
    assert abs((deck.created_at - deck.updated_at).total_seconds()) < 1


def test_deck_model_repr() -> None:
    """Test DeckModel string representation."""
    deck = DeckModel(name="Test Deck", format="standard")

    repr_str = repr(deck)
    assert "DeckModel" in repr_str
    assert deck.id in repr_str
    assert "Test Deck" in repr_str
    assert "standard" in repr_str


def test_deck_model_relationship_initialization() -> None:
    """Test DeckModel deck_cards relationship is initialized."""
    deck = DeckModel(name="Empty Deck", format="standard")

    # Relationship should be initialized as empty list
    assert deck.deck_cards == []


def test_deck_model_with_strategy() -> None:
    """Test DeckModel creation with strategy field."""
    deck = DeckModel(
        name="Control Deck", format="standard", strategy="Reactive control with counters"
    )

    assert deck.name == "Control Deck"
    assert deck.format == "standard"
    assert deck.strategy == "Reactive control with counters"
    assert deck.id is not None
    assert isinstance(deck.created_at, datetime)


def test_deck_model_without_strategy() -> None:
    """Test DeckModel creation without strategy (defaults to None)."""
    deck = DeckModel(name="Aggro Deck", format="standard")

    assert deck.name == "Aggro Deck"
    assert deck.format == "standard"
    assert deck.strategy is None  # Should default to None
    assert deck.id is not None


def test_deck_model_strategy_optional() -> None:
    """Test DeckModel strategy field is truly optional."""
    # Create deck without strategy explicitly
    deck1 = DeckModel(name="Deck 1", format="standard")
    assert deck1.strategy is None

    # Create deck with strategy=None explicitly
    deck2 = DeckModel(name="Deck 2", format="standard", strategy=None)
    assert deck2.strategy is None

    # Create deck with strategy
    deck3 = DeckModel(name="Deck 3", format="standard", strategy="Midrange")
    assert deck3.strategy == "Midrange"
