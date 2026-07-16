"""Integration tests for the deck-management helpers (Story 1.5, Task 5).

Exercises the six helpers (``list_decks`` / ``create_deck`` / ``load_deck`` /
``delete_deck`` / ``add_card_to_deck`` / ``remove_card_from_deck``) directly
against a seeded session: full CRUD, the ``card_id`` vs ``name`` resolution
(exact / partial / ambiguous), graceful error statuses, the FK-off orphan guard,
and the lightweight deck projections. The end-to-end MCP-client wiring is covered
separately in test_mcp_tools.py.

Uses a file-backed engine and a single shared ``session`` fixture: the repo's
``add_card_to_deck`` commits then re-selects on the same session, and a
file-backed DB is the safe mirror of the existing deck-repository tests.
"""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.models.deck_card import DeckCardModel
from src.data.schemas.card import CardSummary
from src.data.schemas.deck import DeckCardSummary
from src.mcp_server.tools.deck_management import (
    add_card_to_deck,
    create_deck,
    delete_deck,
    list_decks,
    load_deck,
    remove_card_from_deck,
)


def _card(
    card_id: str,
    name: str,
    *,
    colors: list[str],
    type_line: str = "Instant",
    cmc: float = 1.0,
) -> CardModel:
    """Build a CardModel with a unique oracle_id (avoids unique-oracle collapsing)."""
    return CardModel(
        id=card_id,
        name=name,
        printed_name=None,
        oracle_id=f"oracle-{card_id}",
        mana_cost="{R}",
        cmc=cmc,
        type_line=type_line,
        oracle_text="Does a thing.",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number="1",
        colors=colors,
        color_identity=colors or [],
        legalities={"standard": "legal", "modern": "legal"},
    )


def _seed_cards() -> list[CardModel]:
    """Two 'bolt'-substring cards (Lightning Bolt, Thunderbolt) for the ambiguous path."""
    return [
        _card("card-bolt", "Lightning Bolt", colors=["R"]),
        _card("card-thunderbolt", "Thunderbolt", colors=["R"], cmc=3.0),
        _card("card-counterspell", "Counterspell", colors=["U"], cmc=2.0),
        _card("card-forest", "Forest", colors=[], type_line="Basic Land — Forest", cmc=0.0),
    ]


@pytest.fixture
async def session(tmp_path: Path):
    """File-backed engine + a single shared session, seeded with cards (no decks)."""
    db_path = tmp_path / "decks.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_database(engine)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        for card in _seed_cards():
            session.add(card)
        await session.commit()
        yield session
    await engine.dispose()


# --- create_deck (AC1) ---


async def test_create_deck_ok(session: AsyncSession) -> None:
    """create_deck returns a DeckDetail with empty cards and zero counts."""
    result = await create_deck(session, name="My Deck")

    assert result.status == "ok"
    assert result.deck is not None
    assert result.deck.name == "My Deck"
    assert result.deck.format == "standard"
    assert result.deck.cards == []
    assert result.deck.mainboard_count == 0
    assert result.deck.distinct_cards == 0
    assert result.deck.id in result.message


async def test_create_deck_with_strategy_and_tags(session: AsyncSession) -> None:
    """create_deck persists strategy and tags."""
    result = await create_deck(session, name="Aggro", strategy="Go fast", tags=["aggro", "burn"])

    assert result.status == "ok"
    assert result.deck is not None
    assert result.deck.strategy == "Go fast"
    assert result.deck.tags == ["aggro", "burn"]


async def test_create_deck_duplicate_name_allowed(session: AsyncSession) -> None:
    """Two decks may share a name; they get distinct ids (name is not unique)."""
    first = await create_deck(session, name="Twins")
    second = await create_deck(session, name="Twins")

    assert first.status == "ok"
    assert second.status == "ok"
    assert first.deck is not None and second.deck is not None
    assert first.deck.id != second.deck.id


async def test_create_deck_blank_name_invalid(session: AsyncSession) -> None:
    """A blank name returns status='invalid' (no raise)."""
    result = await create_deck(session, name="   ")

    assert result.status == "invalid"
    assert result.deck is None


# --- list_decks (AC1, AC5) ---


async def test_list_decks_empty_on_fresh_db(session: AsyncSession) -> None:
    """list_decks returns status='empty' when no decks exist."""
    result = await list_decks(session)

    assert result.status == "empty"
    assert result.decks == []
    assert result.count == 0
    assert result.message


async def test_list_decks_ok_with_summaries(session: AsyncSession) -> None:
    """list_decks returns DeckSummary rows with counts and no nested card list."""
    created = await create_deck(session, name="Listed")
    assert created.deck is not None
    await add_card_to_deck(session, deck_id=created.deck.id, card_id="card-bolt", quantity=4)

    result = await list_decks(session)

    assert result.status == "ok"
    assert result.count == 1
    summary = result.decks[0]
    assert summary.name == "Listed"
    assert summary.mainboard_count == 4
    assert summary.distinct_cards == 1
    # DeckSummary is the lightweight projection — no card list is serialized.
    dumped = summary.model_dump()
    assert "cards" not in dumped
    assert "deck_cards" not in dumped


async def test_list_decks_format_filter_narrows(session: AsyncSession) -> None:
    """list_decks(format=...) returns only decks of that format."""
    standard = await create_deck(session, name="Std", format="standard")
    await create_deck(session, name="Mdn", format="modern")
    assert standard.deck is not None

    result = await list_decks(session, format="standard")

    assert result.status == "ok"
    assert result.count == 1
    assert result.decks[0].id == standard.deck.id


# --- load_deck (AC1, AC5) ---


async def test_load_deck_ok_with_lightweight_cards(session: AsyncSession) -> None:
    """load_deck returns a DeckDetail whose cards are DeckCardSummary + CardSummary."""
    created = await create_deck(session, name="Loaded")
    assert created.deck is not None
    deck_id = created.deck.id
    await add_card_to_deck(session, deck_id=deck_id, card_id="card-bolt", quantity=4)
    await add_card_to_deck(
        session, deck_id=deck_id, card_id="card-counterspell", quantity=2, sideboard=True
    )

    result = await load_deck(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.deck is not None
    assert result.deck.mainboard_count == 4
    assert result.deck.sideboard_count == 2
    assert result.deck.distinct_cards == 2
    assert all(isinstance(dc, DeckCardSummary) for dc in result.deck.cards)
    assert all(isinstance(dc.card, CardSummary) for dc in result.deck.cards)
    # The nested card is the lightweight projection — heavy detail fields are absent.
    dumped_card = result.deck.cards[0].card.model_dump()
    assert "legalities" not in dumped_card
    assert "image_uris" not in dumped_card


async def test_load_deck_not_found(session: AsyncSession) -> None:
    """load_deck on a bogus id returns status='not_found' (graceful)."""
    result = await load_deck(session, deck_id="nope")

    assert result.status == "not_found"
    assert result.deck is None


# --- delete_deck (AC1) ---


async def test_delete_deck_ok_then_load_not_found(session: AsyncSession) -> None:
    """delete_deck removes the deck; a subsequent load returns not_found."""
    created = await create_deck(session, name="Doomed")
    assert created.deck is not None
    deck_id = created.deck.id

    deleted = await delete_deck(session, deck_id=deck_id)
    assert deleted.status == "ok"
    assert deleted.deck_id == deck_id

    assert (await load_deck(session, deck_id=deck_id)).status == "not_found"


async def test_delete_deck_not_found(session: AsyncSession) -> None:
    """delete_deck on a bogus id returns status='not_found' (graceful)."""
    result = await delete_deck(session, deck_id="nope")

    assert result.status == "not_found"


# --- add_card_to_deck (AC2, AC3, AC4) ---


async def test_add_card_with_commander_flag_surfaces_in_load_deck(session: AsyncSession) -> None:
    """add_card_to_deck(commander=True) persists; load_deck's DeckCardSummary shows the flag."""
    created = await create_deck(session, name="Commander Deck", format="commander")
    assert created.deck is not None
    deck_id = created.deck.id

    result = await add_card_to_deck(
        session, deck_id=deck_id, card_id="card-counterspell", quantity=1, commander=True
    )
    assert result.status == "ok"
    await add_card_to_deck(session, deck_id=deck_id, card_id="card-bolt", quantity=4)

    loaded = await load_deck(session, deck_id=deck_id)

    assert loaded.status == "ok"
    assert loaded.deck is not None
    flags = {dc.card_id: dc.commander for dc in loaded.deck.cards}
    assert flags["card-counterspell"] is True
    assert flags["card-bolt"] is False
    commander_row = next(dc for dc in loaded.deck.cards if dc.commander)
    assert commander_row.sideboard is False


async def test_add_card_by_id_persists(session: AsyncSession) -> None:
    """add_card_to_deck by card_id persists the association to SQLite."""
    created = await create_deck(session, name="ById")
    assert created.deck is not None
    deck_id = created.deck.id

    result = await add_card_to_deck(session, deck_id=deck_id, card_id="card-bolt", quantity=4)

    assert result.status == "ok"
    assert result.card_id == "card-bolt"

    # Persisted — re-read via the same session factory's table.
    rows = (
        (await session.execute(select(DeckCardModel).where(DeckCardModel.deck_id == deck_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].card_id == "card-bolt"
    assert rows[0].quantity == 4


async def test_add_card_by_exact_name(session: AsyncSession) -> None:
    """add_card_to_deck by exact name resolves and adds the card."""
    created = await create_deck(session, name="ByName")
    assert created.deck is not None

    result = await add_card_to_deck(session, deck_id=created.deck.id, name="Counterspell")

    assert result.status == "ok"
    assert result.card_id == "card-counterspell"


async def test_add_card_by_partial_name_single(session: AsyncSession) -> None:
    """A partial name hitting exactly one card resolves and adds it."""
    created = await create_deck(session, name="Partial")
    assert created.deck is not None

    result = await add_card_to_deck(session, deck_id=created.deck.id, name="counter")

    assert result.status == "ok"
    assert result.card_id == "card-counterspell"


async def test_add_card_by_partial_name_ambiguous(session: AsyncSession) -> None:
    """A partial name hitting multiple cards returns status='ambiguous' with matches."""
    created = await create_deck(session, name="Ambig")
    assert created.deck is not None

    result = await add_card_to_deck(session, deck_id=created.deck.id, name="bolt")

    assert result.status == "ambiguous"
    assert all(isinstance(m, CardSummary) for m in result.matches)
    assert {m.name for m in result.matches} == {"Lightning Bolt", "Thunderbolt"}


async def test_add_card_not_found_bogus_id(session: AsyncSession) -> None:
    """A bogus card_id returns status='card_not_found'."""
    created = await create_deck(session, name="BadCard")
    assert created.deck is not None

    result = await add_card_to_deck(session, deck_id=created.deck.id, card_id="nope")

    assert result.status == "card_not_found"


async def test_add_card_not_found_unknown_name(session: AsyncSession) -> None:
    """An unknown name returns status='card_not_found'."""
    created = await create_deck(session, name="BadName")
    assert created.deck is not None

    result = await add_card_to_deck(session, deck_id=created.deck.id, name="Nonexistent")

    assert result.status == "card_not_found"


async def test_add_card_deck_not_found_writes_no_orphan(session: AsyncSession) -> None:
    """A bogus deck_id returns deck_not_found and writes NO deck_cards row (FK-off guard)."""
    result = await add_card_to_deck(session, deck_id="bogus-deck", card_id="card-counterspell")

    assert result.status == "deck_not_found"
    # The orphan guard: nothing was inserted into deck_cards.
    rows = (await session.execute(select(DeckCardModel))).scalars().all()
    assert rows == []


async def test_add_card_duplicate_returns_exists(session: AsyncSession) -> None:
    """Adding a card already in that location returns status='exists' (no upsert)."""
    created = await create_deck(session, name="Dupe")
    assert created.deck is not None
    deck_id = created.deck.id
    await add_card_to_deck(session, deck_id=deck_id, card_id="card-bolt", quantity=4)

    result = await add_card_to_deck(session, deck_id=deck_id, card_id="card-bolt", quantity=1)

    assert result.status == "exists"
    # Quantity is unchanged (no silent merge).
    rows = (
        (await session.execute(select(DeckCardModel).where(DeckCardModel.deck_id == deck_id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].quantity == 4


async def test_add_card_sideboard_path(session: AsyncSession) -> None:
    """add_card_to_deck with sideboard=True records the card in the sideboard."""
    created = await create_deck(session, name="Side")
    assert created.deck is not None
    deck_id = created.deck.id

    result = await add_card_to_deck(
        session, deck_id=deck_id, card_id="card-bolt", quantity=2, sideboard=True
    )

    assert result.status == "ok"
    loaded = await load_deck(session, deck_id=deck_id)
    assert loaded.deck is not None
    assert loaded.deck.sideboard_count == 2
    assert loaded.deck.mainboard_count == 0


async def test_add_card_invalid_both_selectors(session: AsyncSession) -> None:
    """Providing both card_id and name returns status='invalid'."""
    created = await create_deck(session, name="Both")
    assert created.deck is not None

    result = await add_card_to_deck(
        session, deck_id=created.deck.id, card_id="card-bolt", name="Lightning Bolt"
    )

    assert result.status == "invalid"


async def test_add_card_invalid_neither_selector(session: AsyncSession) -> None:
    """Providing neither card_id nor name returns status='invalid'."""
    created = await create_deck(session, name="Neither")
    assert created.deck is not None

    result = await add_card_to_deck(session, deck_id=created.deck.id)

    assert result.status == "invalid"


async def test_add_card_invalid_quantity(session: AsyncSession) -> None:
    """quantity < 1 returns status='invalid'."""
    created = await create_deck(session, name="Qty")
    assert created.deck is not None

    result = await add_card_to_deck(
        session, deck_id=created.deck.id, card_id="card-bolt", quantity=0
    )

    assert result.status == "invalid"


# --- remove_card_from_deck (AC2, AC4) ---


async def test_remove_card_by_id(session: AsyncSession) -> None:
    """remove_card_from_deck by card_id removes the association."""
    created = await create_deck(session, name="Rem")
    assert created.deck is not None
    deck_id = created.deck.id
    await add_card_to_deck(session, deck_id=deck_id, card_id="card-bolt", quantity=4)

    result = await remove_card_from_deck(session, deck_id=deck_id, card_id="card-bolt")

    assert result.status == "ok"
    rows = (
        (await session.execute(select(DeckCardModel).where(DeckCardModel.deck_id == deck_id)))
        .scalars()
        .all()
    )
    assert rows == []


async def test_remove_card_by_name(session: AsyncSession) -> None:
    """remove_card_from_deck by name removes the association."""
    created = await create_deck(session, name="RemName")
    assert created.deck is not None
    deck_id = created.deck.id
    await add_card_to_deck(session, deck_id=deck_id, card_id="card-counterspell")

    result = await remove_card_from_deck(session, deck_id=deck_id, name="Counterspell")

    assert result.status == "ok"
    assert result.card_id == "card-counterspell"


async def test_remove_card_not_in_deck(session: AsyncSession) -> None:
    """Removing a card never added returns status='not_in_deck'."""
    created = await create_deck(session, name="Absent")
    assert created.deck is not None

    result = await remove_card_from_deck(session, deck_id=created.deck.id, card_id="card-bolt")

    assert result.status == "not_in_deck"


async def test_remove_card_deck_not_found(session: AsyncSession) -> None:
    """Removing from a bogus deck returns status='deck_not_found'."""
    result = await remove_card_from_deck(session, deck_id="nope", card_id="card-bolt")

    assert result.status == "deck_not_found"


async def test_remove_card_not_found(session: AsyncSession) -> None:
    """Removing a card with a bogus id returns status='card_not_found'."""
    created = await create_deck(session, name="RemBad")
    assert created.deck is not None

    result = await remove_card_from_deck(session, deck_id=created.deck.id, card_id="nope")

    assert result.status == "card_not_found"


async def test_remove_card_ambiguous(session: AsyncSession) -> None:
    """Removing by a partial name hitting multiple cards returns status='ambiguous'."""
    created = await create_deck(session, name="RemAmbig")
    assert created.deck is not None

    result = await remove_card_from_deck(session, deck_id=created.deck.id, name="bolt")

    assert result.status == "ambiguous"
    assert {m.name for m in result.matches} == {"Lightning Bolt", "Thunderbolt"}


async def test_remove_card_invalid_neither(session: AsyncSession) -> None:
    """Removing with neither card_id nor name returns status='invalid'."""
    created = await create_deck(session, name="RemNeither")
    assert created.deck is not None

    result = await remove_card_from_deck(session, deck_id=created.deck.id)

    assert result.status == "invalid"


async def test_remove_card_invalid_both(session: AsyncSession) -> None:
    """Removing with both card_id and name returns status='invalid'."""
    created = await create_deck(session, name="RemBoth")
    assert created.deck is not None

    result = await remove_card_from_deck(
        session, deck_id=created.deck.id, card_id="card-bolt", name="Lightning Bolt"
    )

    assert result.status == "invalid"
