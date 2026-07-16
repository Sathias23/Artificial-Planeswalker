"""Integration tests for DeckRepository."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.models.deck import DeckModel
from src.data.repositories.deck import DeckRepository
from src.data.schemas.deck import Deck, DeckCard


async def _set_created_at(session: AsyncSession, deck_id: str, value: datetime) -> None:
    """Force a deck's created_at to an explicit value (creation timing is wall-clock
    dependent, so tests that assert on ordering must set it deterministically)."""
    model = await session.get(DeckModel, deck_id)
    assert model is not None
    model.created_at = value
    await session.commit()


@pytest.fixture
async def in_memory_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await init_database(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(in_memory_engine):
    """Create a test session."""
    session_factory = create_session_factory(in_memory_engine)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def deck_repo(session: AsyncSession):
    """Create a DeckRepository instance."""
    return DeckRepository(session)


@pytest.fixture
async def test_cards(session: AsyncSession):
    """Create test cards in the database."""
    cards = [
        CardModel(
            id="card-bolt",
            name="Lightning Bolt",
            printed_name=None,
            oracle_id="oracle-bolt",
            mana_cost="{R}",
            cmc=1.0,
            type_line="Instant",
            oracle_text="Deals 3 damage",
            rarity="common",
            set_code="LEA",
            set_name="Alpha",
            collector_number="161",
            colors=["R"],
            color_identity=["R"],
            legalities={"standard": "legal"},
        ),
        CardModel(
            id="card-counterspell",
            name="Counterspell",
            printed_name=None,
            oracle_id="oracle-counter",
            mana_cost="{U}{U}",
            cmc=2.0,
            type_line="Instant",
            oracle_text="Counter target spell",
            rarity="common",
            set_code="LEA",
            set_name="Alpha",
            collector_number="54",
            colors=["U"],
            color_identity=["U"],
            legalities={"standard": "legal"},
        ),
        CardModel(
            id="card-forest",
            name="Forest",
            printed_name=None,
            oracle_id="oracle-forest",
            mana_cost="",
            cmc=0.0,
            type_line="Basic Land — Forest",
            oracle_text="{T}: Add {G}",
            rarity="common",
            set_code="LEA",
            set_name="Alpha",
            collector_number="295",
            colors=[],
            color_identity=["G"],
            legalities={"standard": "legal"},
        ),
    ]
    for card in cards:
        session.add(card)
    await session.commit()
    return cards


# ===== Deck CRUD Tests =====


async def test_create_deck(deck_repo: DeckRepository) -> None:
    """Test creating a new deck."""
    deck = await deck_repo.create_deck(name="Mono Red Aggro", format="standard")

    assert isinstance(deck, Deck)
    assert deck.id is not None
    assert deck.name == "Mono Red Aggro"
    assert deck.format == "standard"
    assert deck.created_at is not None
    assert deck.updated_at is not None
    assert deck.deck_cards == []
    assert deck.strategy is None  # No strategy by default


async def test_create_deck_with_strategy(deck_repo: DeckRepository) -> None:
    """Test creating a new deck with strategy."""
    deck = await deck_repo.create_deck(
        name="Control Deck",
        format="standard",
        strategy="Reactive control with counters and card draw",
    )

    assert isinstance(deck, Deck)
    assert deck.id is not None
    assert deck.name == "Control Deck"
    assert deck.format == "standard"
    assert deck.strategy == "Reactive control with counters and card draw"
    assert deck.created_at is not None
    assert deck.updated_at is not None


async def test_create_deck_strategy_optional(deck_repo: DeckRepository) -> None:
    """Test creating deck without strategy is optional."""
    # Without strategy parameter
    deck1 = await deck_repo.create_deck(name="Deck 1", format="standard")
    assert deck1.strategy is None

    # With strategy=None explicitly
    deck2 = await deck_repo.create_deck(name="Deck 2", format="standard", strategy=None)
    assert deck2.strategy is None

    # With strategy value
    deck3 = await deck_repo.create_deck(name="Deck 3", format="standard", strategy="Aggro")
    assert deck3.strategy == "Aggro"


async def test_get_deck(deck_repo: DeckRepository) -> None:
    """Test retrieving an existing deck."""
    created_deck = await deck_repo.create_deck(name="Test Deck", format="standard")

    retrieved_deck = await deck_repo.get_deck(deck_id=created_deck.id)

    assert retrieved_deck is not None
    assert retrieved_deck.id == created_deck.id
    assert retrieved_deck.name == "Test Deck"
    assert retrieved_deck.format == "standard"


async def test_get_deck_nonexistent(deck_repo: DeckRepository) -> None:
    """Test get_deck returns None for non-existent deck."""
    deck = await deck_repo.get_deck(deck_id="invalid-deck-id")

    assert deck is None


async def test_update_deck_name(deck_repo: DeckRepository) -> None:
    """Test updating a deck's name."""
    deck = await deck_repo.create_deck(name="Old Name", format="standard")
    original_updated_at = deck.updated_at

    updated_deck = await deck_repo.update_deck(deck_id=deck.id, name="New Name")

    assert updated_deck is not None
    assert updated_deck.name == "New Name"
    assert updated_deck.format == "standard"
    # updated_at should change
    assert updated_deck.updated_at > original_updated_at


async def test_update_deck_nonexistent(deck_repo: DeckRepository) -> None:
    """Test update_deck returns None for non-existent deck."""
    result = await deck_repo.update_deck(deck_id="invalid-id", name="New Name")

    assert result is None


async def test_update_deck_strategy(deck_repo: DeckRepository) -> None:
    """Test updating a deck's strategy."""
    deck = await deck_repo.create_deck(name="Test Deck", format="standard", strategy="Old strategy")
    original_updated_at = deck.updated_at

    updated_deck = await deck_repo.update_deck(deck_id=deck.id, strategy="New control strategy")

    assert updated_deck is not None
    assert updated_deck.name == "Test Deck"  # Name unchanged
    assert updated_deck.strategy == "New control strategy"
    # updated_at should change
    assert updated_deck.updated_at > original_updated_at


async def test_update_deck_clear_strategy(deck_repo: DeckRepository) -> None:
    """Test clearing a deck's strategy by setting to None."""
    deck = await deck_repo.create_deck(
        name="Test Deck", format="standard", strategy="Initial strategy"
    )

    updated_deck = await deck_repo.update_deck(deck_id=deck.id, strategy=None)

    assert updated_deck is not None
    assert updated_deck.strategy is None


async def test_update_deck_name_and_strategy(deck_repo: DeckRepository) -> None:
    """Test updating both name and strategy at once."""
    deck = await deck_repo.create_deck(name="Old Name", format="standard", strategy="Old strategy")

    updated_deck = await deck_repo.update_deck(
        deck_id=deck.id, name="New Name", strategy="New strategy"
    )

    assert updated_deck is not None
    assert updated_deck.name == "New Name"
    assert updated_deck.strategy == "New strategy"


async def test_delete_deck(deck_repo: DeckRepository) -> None:
    """Test deleting a deck."""
    deck = await deck_repo.create_deck(name="Delete Me", format="standard")

    success = await deck_repo.delete_deck(deck_id=deck.id)

    assert success is True

    # Verify deck no longer exists
    retrieved = await deck_repo.get_deck(deck_id=deck.id)
    assert retrieved is None


async def test_delete_deck_nonexistent(deck_repo: DeckRepository) -> None:
    """Test delete_deck returns False for non-existent deck."""
    success = await deck_repo.delete_deck(deck_id="invalid-id")

    assert success is False


async def test_list_decks_empty(deck_repo: DeckRepository) -> None:
    """Test list_decks returns empty list when no decks exist."""
    decks = await deck_repo.list_decks()

    assert decks == []


async def test_list_decks(deck_repo: DeckRepository, session: AsyncSession) -> None:
    """Test list_decks returns all decks ordered by created_at descending.

    created_at is set explicitly here: three rapid create_deck calls can land on the
    same wall-clock tick, in which case the desc ordering is ambiguous (the historical
    flake). Pinning distinct timestamps makes the newest-first intent unambiguous.
    """
    deck1 = await deck_repo.create_deck(name="Deck 1", format="standard")
    deck2 = await deck_repo.create_deck(name="Deck 2", format="standard")
    deck3 = await deck_repo.create_deck(name="Deck 3", format="standard")

    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    await _set_created_at(session, deck1.id, base)
    await _set_created_at(session, deck2.id, base + timedelta(minutes=1))
    await _set_created_at(session, deck3.id, base + timedelta(minutes=2))

    decks = await deck_repo.list_decks()

    assert [d.id for d in decks] == [deck3.id, deck2.id, deck1.id]


async def test_list_decks_orders_deterministically_on_created_at_tie(
    deck_repo: DeckRepository, session: AsyncSession
) -> None:
    """When created_at ties, list_decks must break the tie by id (stable, repeatable).

    Without a secondary sort key, SQLite returns tied rows in insertion order, so the
    newest-first contract silently depends on timing. The id tie-breaker makes the order
    deterministic regardless of how many decks share a timestamp.
    """
    tie = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    created = []
    for i in range(10):
        deck = await deck_repo.create_deck(name=f"Tie Deck {i}", format="standard")
        await _set_created_at(session, deck.id, tie)
        created.append(deck)

    first = [d.id for d in await deck_repo.list_decks()]
    second = [d.id for d in await deck_repo.list_decks()]

    # Tie broken by id ascending, and stable across repeated calls.
    assert first == sorted(d.id for d in created)
    assert first == second


async def test_list_decks_filtered_by_format(deck_repo: DeckRepository) -> None:
    """Test list_decks with format filter."""
    await deck_repo.create_deck(name="Standard Deck", format="standard")

    decks = await deck_repo.list_decks(format_filter="standard")

    assert len(decks) == 1
    assert decks[0].name == "Standard Deck"


async def test_list_decks_with_strategy_field(deck_repo: DeckRepository) -> None:
    """Test list_decks includes strategy field for all decks."""
    # Create decks with and without strategy
    await deck_repo.create_deck(name="Aggro Deck", format="standard", strategy="Fast aggro")
    await deck_repo.create_deck(name="Control Deck", format="standard", strategy="Control")
    await deck_repo.create_deck(name="No Strategy Deck", format="standard")

    decks = await deck_repo.list_decks()

    assert len(decks) == 3
    # Verify strategy field is present in all decks (newest first ordering)
    assert decks[0].strategy is None  # Newest first (No Strategy Deck)
    assert decks[1].strategy == "Control"  # Second newest (Control Deck)
    assert decks[2].strategy == "Fast aggro"  # Oldest (Aggro Deck)


# ===== Card Management Tests =====


async def test_add_card_to_deck_mainboard(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test adding a card to deck mainboard."""
    deck = await deck_repo.create_deck(name="Test Deck", format="standard")

    deck_card = await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    assert isinstance(deck_card, DeckCard)
    assert deck_card.deck_id == deck.id
    assert deck_card.card_id == "card-bolt"
    assert deck_card.quantity == 4
    assert deck_card.sideboard is False
    assert deck_card.card.name == "Lightning Bolt"


@pytest.mark.parametrize("bad_quantity", [0, -1, -5])
async def test_add_card_to_deck_rejects_quantity_below_one(
    deck_repo: DeckRepository, test_cards: list[CardModel], bad_quantity: int
) -> None:
    """add_card_to_deck must reject quantity < 1 and persist nothing (data-integrity guard)."""
    deck = await deck_repo.create_deck(name="Guard Test", format="standard")

    with pytest.raises(ValueError):
        await deck_repo.add_card_to_deck(
            deck_id=deck.id, card_id="card-bolt", quantity=bad_quantity, sideboard=False
        )

    # No row should have been written.
    loaded = await deck_repo.get_deck_with_cards(deck_id=deck.id)
    assert loaded is not None
    assert loaded.deck_cards == []


@pytest.mark.parametrize("bad_quantity", [0, -1])
async def test_update_card_quantity_rejects_quantity_below_one(
    deck_repo: DeckRepository, test_cards: list[CardModel], bad_quantity: int
) -> None:
    """update_card_quantity must reject quantity < 1 and leave the existing quantity intact."""
    deck = await deck_repo.create_deck(name="Guard Test", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    with pytest.raises(ValueError):
        await deck_repo.update_card_quantity(
            deck_id=deck.id, card_id="card-bolt", quantity=bad_quantity, sideboard=False
        )

    loaded = await deck_repo.get_deck_with_cards(deck_id=deck.id)
    assert loaded is not None
    assert loaded.deck_cards[0].quantity == 4


async def test_add_card_to_deck_sideboard(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test adding a card to deck sideboard."""
    deck = await deck_repo.create_deck(name="Test Deck", format="standard")

    deck_card = await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-counterspell", quantity=2, sideboard=True
    )

    assert deck_card.sideboard is True
    assert deck_card.quantity == 2


async def test_add_card_to_deck_commander_round_trip(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """A commander=True write survives the round-trip back as a Pydantic DeckCard."""
    deck = await deck_repo.create_deck(name="Commander Deck", format="commander")

    deck_card = await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=1, sideboard=False, commander=True
    )

    assert isinstance(deck_card, DeckCard)
    assert deck_card.commander is True
    assert deck_card.sideboard is False

    loaded = await deck_repo.get_deck_with_cards(deck_id=deck.id)
    assert loaded is not None
    assert len(loaded.deck_cards) == 1
    assert loaded.deck_cards[0].commander is True
    assert loaded.deck_cards[0].sideboard is False


async def test_add_card_to_deck_commander_defaults_false(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Omitting commander keeps the existing call shape and persists False."""
    deck = await deck_repo.create_deck(name="Plain Deck", format="standard")

    deck_card = await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    assert deck_card.commander is False

    loaded = await deck_repo.get_deck_with_cards(deck_id=deck.id)
    assert loaded is not None
    assert loaded.deck_cards[0].commander is False


async def test_add_duplicate_card_raises_error(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test adding the same card twice to mainboard raises IntegrityError."""
    deck = await deck_repo.create_deck(name="Test Deck", format="standard")

    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    with pytest.raises(IntegrityError):
        await deck_repo.add_card_to_deck(
            deck_id=deck.id, card_id="card-bolt", quantity=2, sideboard=False
        )


async def test_add_same_card_to_mainboard_and_sideboard(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test same card can be in both mainboard and sideboard."""
    deck = await deck_repo.create_deck(name="Test Deck", format="standard")

    mainboard_card = await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )
    sideboard_card = await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=2, sideboard=True
    )

    assert mainboard_card.sideboard is False
    assert sideboard_card.sideboard is True


async def test_remove_card_from_deck(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test removing a card from deck."""
    deck = await deck_repo.create_deck(name="Test Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    success = await deck_repo.remove_card_from_deck(
        deck_id=deck.id, card_id="card-bolt", sideboard=False
    )

    assert success is True


async def test_remove_card_nonexistent(deck_repo: DeckRepository) -> None:
    """Test remove_card_from_deck returns False for non-existent card."""
    deck = await deck_repo.create_deck(name="Test Deck", format="standard")

    success = await deck_repo.remove_card_from_deck(
        deck_id=deck.id, card_id="invalid-card", sideboard=False
    )

    assert success is False


async def test_update_card_quantity(deck_repo: DeckRepository, test_cards: list[CardModel]) -> None:
    """Test updating card quantity in deck."""
    deck = await deck_repo.create_deck(name="Test Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=2, sideboard=False
    )

    updated_card = await deck_repo.update_card_quantity(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    assert updated_card is not None
    assert updated_card.quantity == 4


async def test_update_card_quantity_nonexistent(deck_repo: DeckRepository) -> None:
    """Test update_card_quantity returns None for non-existent card."""
    deck = await deck_repo.create_deck(name="Test Deck", format="standard")

    result = await deck_repo.update_card_quantity(
        deck_id=deck.id, card_id="invalid-card", quantity=4, sideboard=False
    )

    assert result is None


async def test_get_deck_with_cards(deck_repo: DeckRepository, test_cards: list[CardModel]) -> None:
    """Test get_deck_with_cards returns deck with all cards loaded."""
    deck = await deck_repo.create_deck(name="Full Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-counterspell", quantity=2, sideboard=True
    )
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-forest", quantity=20, sideboard=False
    )

    deck_with_cards = await deck_repo.get_deck_with_cards(deck_id=deck.id)

    assert deck_with_cards is not None
    assert len(deck_with_cards.deck_cards) == 3

    # Verify card details are populated
    for deck_card in deck_with_cards.deck_cards:
        assert deck_card.card.name is not None


async def test_get_deck_with_cards_nonexistent(deck_repo: DeckRepository) -> None:
    """Test get_deck_with_cards returns None for non-existent deck."""
    result = await deck_repo.get_deck_with_cards(deck_id="invalid-id")

    assert result is None


# ===== Cascade Delete Tests =====


async def test_delete_deck_cascades_to_cards(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test deleting a deck also deletes its card associations."""
    deck = await deck_repo.create_deck(name="Test Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    await deck_repo.delete_deck(deck_id=deck.id)

    # Deck should be gone
    retrieved_deck = await deck_repo.get_deck_with_cards(deck_id=deck.id)
    assert retrieved_deck is None


# ===== Transaction Rollback Tests (Bug #2a1c1f29) =====


async def test_integrity_error_rollback_allows_subsequent_operation(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test that IntegrityError rollback doesn't prevent subsequent operations.

    This test verifies that after an IntegrityError (duplicate card add),
    the session is properly rolled back and subsequent write operations
    can execute successfully.
    """
    deck = await deck_repo.create_deck(name="Test Deck", format="standard")

    # Add card successfully
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    # Try to add same card again - should raise IntegrityError
    with pytest.raises(IntegrityError):
        await deck_repo.add_card_to_deck(
            deck_id=deck.id, card_id="card-bolt", quantity=2, sideboard=False
        )

    # Subsequent write operation should succeed (session should be clean)
    deck_card = await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-counterspell", quantity=3, sideboard=False
    )

    assert deck_card.card_id == "card-counterspell"
    assert deck_card.quantity == 3


async def test_sequential_write_operations_after_rollback(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test multiple sequential write operations after IntegrityError rollback.

    This is the core scenario from bug #2a1c1f29: rapid card additions
    where one fails should not prevent subsequent additions.
    """
    deck = await deck_repo.create_deck(name="Sequential Test", format="standard")

    # Operation 1: Successful add
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    # Operation 2: Duplicate add (triggers rollback)
    with pytest.raises(IntegrityError):
        await deck_repo.add_card_to_deck(
            deck_id=deck.id, card_id="card-bolt", quantity=2, sideboard=False
        )

    # Operation 3: Should succeed
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-counterspell", quantity=3, sideboard=False
    )

    # Operation 4: Should also succeed
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-forest", quantity=20, sideboard=False
    )

    # Verify all successful operations persisted
    deck_with_cards = await deck_repo.get_deck_with_cards(deck_id=deck.id)
    assert deck_with_cards is not None
    assert len(deck_with_cards.deck_cards) == 3


async def test_read_operation_after_write_rollback(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test that read operations work correctly after a write operation rollback."""
    deck = await deck_repo.create_deck(name="Read After Rollback", format="standard")

    # Add card successfully
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    # Trigger rollback with duplicate
    with pytest.raises(IntegrityError):
        await deck_repo.add_card_to_deck(
            deck_id=deck.id, card_id="card-bolt", quantity=2, sideboard=False
        )

    # Read operations should work fine
    deck_with_cards = await deck_repo.get_deck_with_cards(deck_id=deck.id)
    assert deck_with_cards is not None
    assert len(deck_with_cards.deck_cards) == 1
    assert deck_with_cards.deck_cards[0].card_id == "card-bolt"


async def test_multiple_integrity_errors_in_sequence(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test that multiple IntegrityErrors in sequence are handled correctly.

    Each IntegrityError should rollback cleanly without affecting subsequent
    operations.
    """
    deck = await deck_repo.create_deck(name="Multiple Errors", format="standard")

    # Add two cards successfully
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-counterspell", quantity=3, sideboard=False
    )

    # First IntegrityError
    with pytest.raises(IntegrityError):
        await deck_repo.add_card_to_deck(
            deck_id=deck.id, card_id="card-bolt", quantity=1, sideboard=False
        )

    # Second IntegrityError (should not fail due to first rollback)
    with pytest.raises(IntegrityError):
        await deck_repo.add_card_to_deck(
            deck_id=deck.id, card_id="card-counterspell", quantity=1, sideboard=False
        )

    # Successful operation after multiple errors
    deck_card = await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-forest", quantity=20, sideboard=False
    )

    assert deck_card.card_id == "card-forest"

    # Verify deck state
    deck_with_cards = await deck_repo.get_deck_with_cards(deck_id=deck.id)
    assert deck_with_cards is not None
    assert len(deck_with_cards.deck_cards) == 3


async def test_update_after_integrity_error(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test that update operations work after IntegrityError rollback."""
    deck = await deck_repo.create_deck(name="Update Test", format="standard")

    # Add card successfully
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=2, sideboard=False
    )

    # Trigger IntegrityError
    with pytest.raises(IntegrityError):
        await deck_repo.add_card_to_deck(
            deck_id=deck.id, card_id="card-bolt", quantity=1, sideboard=False
        )

    # Update operation should succeed
    updated_card = await deck_repo.update_card_quantity(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    assert updated_card is not None
    assert updated_card.quantity == 4


async def test_delete_after_integrity_error(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test that delete operations work after IntegrityError rollback."""
    deck = await deck_repo.create_deck(name="Delete Test", format="standard")

    # Add card successfully
    await deck_repo.add_card_to_deck(
        deck_id=deck.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    # Trigger IntegrityError
    with pytest.raises(IntegrityError):
        await deck_repo.add_card_to_deck(
            deck_id=deck.id, card_id="card-bolt", quantity=1, sideboard=False
        )

    # Delete operation should succeed
    success = await deck_repo.remove_card_from_deck(
        deck_id=deck.id, card_id="card-bolt", sideboard=False
    )

    assert success is True

    # Verify deletion
    deck_with_cards = await deck_repo.get_deck_with_cards(deck_id=deck.id)
    assert deck_with_cards is not None
    assert len(deck_with_cards.deck_cards) == 0


# ===== Deck Merge Tests =====


async def test_merge_decks_combine_strategy(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test merge with COMBINE strategy sums quantities."""
    # Create target deck with 2 Lightning Bolts
    target = await deck_repo.create_deck(name="Target Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=target.id, card_id="card-bolt", quantity=2, sideboard=False
    )

    # Create source deck with 3 Lightning Bolts
    source = await deck_repo.create_deck(name="Source Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-bolt", quantity=3, sideboard=False
    )

    # Merge with COMBINE strategy
    from src.data.repositories.deck import MergeStrategy

    merged = await deck_repo.merge_decks(target.id, source.id, MergeStrategy.COMBINE)

    assert merged is not None
    assert len(merged.deck_cards) == 1
    assert merged.deck_cards[0].card_id == "card-bolt"
    assert merged.deck_cards[0].quantity == 5  # 2 + 3 = 5

    # Verify source deck unchanged
    source_check = await deck_repo.get_deck_with_cards(source.id)
    assert source_check is not None
    assert len(source_check.deck_cards) == 1
    assert source_check.deck_cards[0].quantity == 3  # Still 3


async def test_merge_decks_propagates_commander_flag(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """A flagged source card lands in the target still flagged as commander."""
    target = await deck_repo.create_deck(name="Target Deck", format="commander")
    source = await deck_repo.create_deck(name="Source Deck", format="commander")
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-counterspell", quantity=1, sideboard=False, commander=True
    )
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-bolt", quantity=1, sideboard=False
    )

    merged = await deck_repo.merge_decks(target.id, source.id)

    assert merged is not None
    flags = {dc.card_id: dc.commander for dc in merged.deck_cards}
    assert flags["card-counterspell"] is True
    assert flags["card-bolt"] is False


async def test_merge_decks_existing_card_keeps_target_flag(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """When the card already exists in the target, the merge keeps the target's flag."""
    target = await deck_repo.create_deck(name="Target Deck", format="commander")
    await deck_repo.add_card_to_deck(
        deck_id=target.id, card_id="card-bolt", quantity=1, sideboard=False, commander=False
    )
    source = await deck_repo.create_deck(name="Source Deck", format="commander")
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-bolt", quantity=2, sideboard=False, commander=True
    )

    merged = await deck_repo.merge_decks(target.id, source.id)

    assert merged is not None
    assert len(merged.deck_cards) == 1
    assert merged.deck_cards[0].quantity == 3  # COMBINE: 1 + 2
    assert merged.deck_cards[0].commander is False  # target's flag wins


async def test_merge_decks_maximum_strategy(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test merge with MAXIMUM strategy takes higher quantity."""
    target = await deck_repo.create_deck(name="Target Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=target.id, card_id="card-bolt", quantity=2, sideboard=False
    )

    source = await deck_repo.create_deck(name="Source Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-bolt", quantity=3, sideboard=False
    )

    from src.data.repositories.deck import MergeStrategy

    merged = await deck_repo.merge_decks(target.id, source.id, MergeStrategy.MAXIMUM)

    assert merged is not None
    assert merged.deck_cards[0].quantity == 3  # max(2, 3) = 3


async def test_merge_decks_replace_strategy(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test merge with REPLACE strategy uses source quantity."""
    target = await deck_repo.create_deck(name="Target Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=target.id, card_id="card-bolt", quantity=2, sideboard=False
    )

    source = await deck_repo.create_deck(name="Source Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-bolt", quantity=3, sideboard=False
    )

    from src.data.repositories.deck import MergeStrategy

    merged = await deck_repo.merge_decks(target.id, source.id, MergeStrategy.REPLACE)

    assert merged is not None
    assert merged.deck_cards[0].quantity == 3  # Replaced with source quantity


async def test_merge_decks_disjoint_cards(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test merge with no overlapping cards adds all cards."""
    target = await deck_repo.create_deck(name="Target Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=target.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    source = await deck_repo.create_deck(name="Source Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-counterspell", quantity=3, sideboard=False
    )

    from src.data.repositories.deck import MergeStrategy

    merged = await deck_repo.merge_decks(target.id, source.id, MergeStrategy.COMBINE)

    assert merged is not None
    assert len(merged.deck_cards) == 2

    # Find each card in result
    bolt_card = next((c for c in merged.deck_cards if c.card_id == "card-bolt"), None)
    counter_card = next((c for c in merged.deck_cards if c.card_id == "card-counterspell"), None)

    assert bolt_card is not None
    assert bolt_card.quantity == 4
    assert counter_card is not None
    assert counter_card.quantity == 3


async def test_merge_decks_respects_sideboard_separation(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test merge keeps mainboard and sideboard separate."""
    target = await deck_repo.create_deck(name="Target Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=target.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    source = await deck_repo.create_deck(name="Source Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-bolt", quantity=2, sideboard=True
    )

    from src.data.repositories.deck import MergeStrategy

    merged = await deck_repo.merge_decks(target.id, source.id, MergeStrategy.COMBINE)

    assert merged is not None
    assert len(merged.deck_cards) == 2

    mainboard = next((c for c in merged.deck_cards if not c.sideboard), None)
    sideboard = next((c for c in merged.deck_cards if c.sideboard), None)

    assert mainboard is not None
    assert mainboard.quantity == 4  # Unchanged
    assert sideboard is not None
    assert sideboard.quantity == 2  # Added from source


async def test_merge_updates_color_identity(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test merge updates deck color identity."""
    target = await deck_repo.create_deck(name="Target Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=target.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    source = await deck_repo.create_deck(name="Source Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-counterspell", quantity=3, sideboard=False
    )

    from src.data.repositories.deck import MergeStrategy

    merged = await deck_repo.merge_decks(target.id, source.id, MergeStrategy.COMBINE)

    assert merged is not None
    # Should have both Red and Blue in WUBRG order
    assert merged.color_identity == ["U", "R"]


async def test_merge_with_nonexistent_target(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test merge returns None when target deck doesn't exist."""
    source = await deck_repo.create_deck(name="Source Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-bolt", quantity=3, sideboard=False
    )

    from src.data.repositories.deck import MergeStrategy

    result = await deck_repo.merge_decks("invalid-id", source.id, MergeStrategy.COMBINE)

    assert result is None


async def test_merge_with_nonexistent_source(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test merge returns None when source deck doesn't exist."""
    target = await deck_repo.create_deck(name="Target Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=target.id, card_id="card-bolt", quantity=2, sideboard=False
    )

    from src.data.repositories.deck import MergeStrategy

    result = await deck_repo.merge_decks(target.id, "invalid-id", MergeStrategy.COMBINE)

    assert result is None

    # Verify target unchanged
    target_check = await deck_repo.get_deck_with_cards(target.id)
    assert target_check is not None
    assert len(target_check.deck_cards) == 1


async def test_merge_with_empty_source(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test merge with empty source deck (no-op)."""
    target = await deck_repo.create_deck(name="Target Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=target.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    source = await deck_repo.create_deck(name="Empty Source", format="standard")

    from src.data.repositories.deck import MergeStrategy

    merged = await deck_repo.merge_decks(target.id, source.id, MergeStrategy.COMBINE)

    assert merged is not None
    assert len(merged.deck_cards) == 1
    assert merged.deck_cards[0].quantity == 4  # Unchanged


async def test_merge_with_empty_target(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test merge into empty target deck copies all cards."""
    target = await deck_repo.create_deck(name="Empty Target", format="standard")

    source = await deck_repo.create_deck(name="Source Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-bolt", quantity=4, sideboard=False
    )

    from src.data.repositories.deck import MergeStrategy

    merged = await deck_repo.merge_decks(target.id, source.id, MergeStrategy.COMBINE)

    assert merged is not None
    assert len(merged.deck_cards) == 1
    assert merged.deck_cards[0].quantity == 4


async def test_merge_updates_timestamp(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test merge updates target deck's updated_at timestamp."""
    target = await deck_repo.create_deck(name="Target Deck", format="standard")
    original_updated_at = target.updated_at

    source = await deck_repo.create_deck(name="Source Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-bolt", quantity=3, sideboard=False
    )

    from src.data.repositories.deck import MergeStrategy

    merged = await deck_repo.merge_decks(target.id, source.id, MergeStrategy.COMBINE)

    assert merged is not None
    assert merged.updated_at > original_updated_at


async def test_merge_string_strategy(
    deck_repo: DeckRepository, test_cards: list[CardModel]
) -> None:
    """Test merge accepts string strategy and converts to enum."""
    target = await deck_repo.create_deck(name="Target Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=target.id, card_id="card-bolt", quantity=2, sideboard=False
    )

    source = await deck_repo.create_deck(name="Source Deck", format="standard")
    await deck_repo.add_card_to_deck(
        deck_id=source.id, card_id="card-bolt", quantity=3, sideboard=False
    )

    # Use string strategy
    merged = await deck_repo.merge_decks(target.id, source.id, "COMBINE")

    assert merged is not None
    assert merged.deck_cards[0].quantity == 5  # Combined correctly
