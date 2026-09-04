"""Integration tests for bulk Arena deck import."""

from pathlib import Path

import pytest
from sqlalchemy.exc import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.data.database import create_engine, create_session_factory, init_database
from src.data.models.card import CardModel
from src.data.repositories.card import CardRepository
from src.data.repositories.deck import DeckRepository
from src.mcp_server.tools.deck_import import import_decklist
from src.mcp_server.tools.deck_management import add_card_to_deck, create_deck, load_deck


async def _create_saved_deck(
    session_factory: async_sessionmaker[AsyncSession], *, name: str = "Import Target"
) -> str:
    """Create a saved deck and return its id."""
    async with session_factory() as session:
        created = await create_deck(session, name=name)
    assert created.status == "ok"
    assert created.deck is not None
    return created.deck.id


def _bulk_card(index: int) -> CardModel:
    return CardModel(
        id=f"bulk-{index:03d}",
        name=f"Bulk Card {index:03d}",
        printed_name=None,
        oracle_id=f"oracle-bulk-{index:03d}",
        mana_cost="{1}",
        cmc=1.0,
        type_line="Artifact",
        oracle_text="",
        rarity="common",
        set_code="TST",
        set_name="Test Set",
        collector_number=str(index),
        colors=[],
        color_identity=[],
        legalities={"commander": "legal"},
    )


async def _seed_bulk_cards(session_factory: async_sessionmaker[AsyncSession], count: int) -> None:
    async with session_factory() as session:
        session.add_all(_bulk_card(i) for i in range(count))
        await session.commit()


def _hundred_line_export(*, unknown_last: bool = False) -> str:
    """A Commander list: one commander line plus 99 deck lines (the last optionally unknown)."""
    lines = ["Commander", "1 Bulk Card 000 (TST) 0", "", "Deck"]
    lines += [f"1 Bulk Card {i:03d} (TST) {i}" for i in range(1, 99)]
    lines.append("1 No Such Card (TST) 99" if unknown_last else "1 Bulk Card 099 (TST) 99")
    return "\n".join(lines)


class _WriteSpy:
    """Counts commits, rollbacks, deck loads and bulk writes across one import call."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.deck_loads = 0
        self.bulk_writes = 0
        spy = self
        original_commit = AsyncSession.commit
        original_rollback = AsyncSession.rollback
        original_load = DeckRepository.get_deck_with_cards
        original_bulk = DeckRepository.add_cards_to_deck

        async def commit(session: AsyncSession) -> None:
            spy.commits += 1
            await original_commit(session)

        async def rollback(session: AsyncSession) -> None:
            spy.rollbacks += 1
            await original_rollback(session)

        async def load(repo: DeckRepository, deck_id: str):
            spy.deck_loads += 1
            return await original_load(repo, deck_id)

        async def bulk(repo: DeckRepository, deck_id: str, entries):
            spy.bulk_writes += 1
            return await original_bulk(repo, deck_id, entries)

        monkeypatch.setattr(AsyncSession, "commit", commit)
        monkeypatch.setattr(AsyncSession, "rollback", rollback)
        monkeypatch.setattr(DeckRepository, "get_deck_with_cards", load)
        monkeypatch.setattr(DeckRepository, "add_cards_to_deck", bulk)


async def test_import_decklist_hundred_lines_is_one_commit_and_one_reload(
    seeded_card_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """100 resolvable lines: ``ok``, one commit, one deck load, one bulk write, 100 rows."""
    await _seed_bulk_cards(seeded_card_db, 100)
    deck_id = await _create_saved_deck(seeded_card_db)
    spy = _WriteSpy(monkeypatch)

    async with seeded_card_db() as session:
        result = await import_decklist(
            session, deck_id=deck_id, arena_export=_hundred_line_export()
        )
        counts = (spy.commits, spy.deck_loads, spy.bulk_writes)
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.imported_lines == 100
    assert result.imported_copies == 100
    assert counts == (1, 1, 1)
    assert loaded.deck is not None
    assert len(loaded.deck.cards) == 100
    assert sum(1 for entry in loaded.deck.cards if entry.commander) == 1


async def test_import_decklist_same_card_twice_in_one_board_is_exists_on_the_second_line(
    seeded_card_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """In-memory duplicate detection reproduces the per-line ``exists`` of a sequential import."""
    deck_id = await _create_saved_deck(seeded_card_db)
    spy = _WriteSpy(monkeypatch)
    arena_export = "Deck\n1 Lightning Bolt (M11) 149\n2 Lightning Bolt (M11) 149\n"

    async with seeded_card_db() as session:
        result = await import_decklist(session, deck_id=deck_id, arena_export=arena_export)
        commits = spy.commits
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "partial"
    assert [line.status for line in result.results] == ["ok", "exists"]
    assert "already in the mainboard" in result.results[1].message
    assert commits == 1
    assert loaded.deck is not None
    assert [(entry.card.name, entry.quantity) for entry in loaded.deck.cards] == [
        ("Lightning Bolt", 1)
    ]


async def test_import_decklist_one_unresolvable_line_commits_the_other_ninety_nine(
    seeded_card_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _seed_bulk_cards(seeded_card_db, 100)
    deck_id = await _create_saved_deck(seeded_card_db)
    spy = _WriteSpy(monkeypatch)

    async with seeded_card_db() as session:
        result = await import_decklist(
            session, deck_id=deck_id, arena_export=_hundred_line_export(unknown_last=True)
        )
        commits = spy.commits
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "partial"
    assert result.imported_lines == 99
    assert result.results[-1].status == "not_found"
    assert result.results[-1].name == "No Such Card"
    assert commits == 1
    assert loaded.deck is not None
    assert len(loaded.deck.cards) == 99


async def test_import_decklist_one_line_failing_to_resolve_is_error_and_the_rest_commit(
    seeded_card_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``DatabaseError`` while resolving one line marks that line ``error`` only."""
    deck_id = await _create_saved_deck(seeded_card_db)
    spy = _WriteSpy(monkeypatch)
    real_exact = CardRepository.find_by_name_exact

    async def flaky_exact(self, name, format_filter=None, games=None):
        if name == "Counterspell":
            raise DatabaseError("SELECT cards", {}, Exception("disk I/O error"))
        return await real_exact(self, name, format_filter, games)

    monkeypatch.setattr(CardRepository, "find_by_name_exact", flaky_exact)
    arena_export = (
        "Deck\n4 Lightning Bolt (M11) 149\n1 Counterspell (DMR) 50\n2 Thunderbolt (WTH) 117\n"
    )

    async with seeded_card_db() as session:
        result = await import_decklist(session, deck_id=deck_id, arena_export=arena_export)
        commits = spy.commits
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "partial"
    assert [line.status for line in result.results] == ["ok", "error", "ok"]
    assert result.results[1].message == "Line 3: a database error occurred."
    assert result.imported_lines == 2
    assert commits == 1
    assert loaded.deck is not None
    assert {entry.card.name for entry in loaded.deck.cards} == {"Lightning Bolt", "Thunderbolt"}


async def test_import_decklist_failed_commit_is_error_with_nothing_added(
    seeded_card_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``DatabaseError`` on the single write: ``error``, zero rows, session rolled back."""
    deck_id = await _create_saved_deck(seeded_card_db)
    spy = _WriteSpy(monkeypatch)

    async def failing_commit(session: AsyncSession) -> None:
        raise DatabaseError("INSERT INTO deck_cards", {}, Exception("disk I/O error"))

    monkeypatch.setattr(AsyncSession, "commit", failing_commit)
    arena_export = "Deck\n4 Lightning Bolt (M11) 149\n1 Counterspell (DMR) 50\n"

    async with seeded_card_db() as session:
        result = await import_decklist(session, deck_id=deck_id, arena_export=arena_export)
        rollbacks = spy.rollbacks
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "error"
    assert result.imported_lines == 0
    assert result.imported_copies == 0
    assert [line.status for line in result.results] == ["error", "error"]
    assert "nothing was added" in result.message
    assert rollbacks >= 1
    assert loaded.deck is not None
    assert loaded.deck.cards == []


async def test_import_decklist_maps_all_sections_and_quantities(seeded_card_db) -> None:
    """Commander/Deck become mainboard and Sideboard stays sideboard."""
    deck_id = await _create_saved_deck(seeded_card_db)
    arena_export = """Commander
1 Counterspell (DMR) 50

Deck
4 Lightning Bolt (M11) 149

Sideboard
2 Thunderbolt (WTH) 117
"""

    async with seeded_card_db() as session:
        result = await import_decklist(session, deck_id=deck_id, arena_export=arena_export)
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.total_lines == 3
    assert result.imported_lines == 3
    assert result.imported_copies == 7
    assert [line.status for line in result.results] == ["ok", "ok", "ok"]
    assert [line.line_number for line in result.results] == [2, 5, 8]
    assert [(line.set_code, line.collector_number) for line in result.results] == [
        ("DMR", "50"),
        ("M11", "149"),
        ("WTH", "117"),
    ]

    assert loaded.deck is not None
    cards = {(entry.card.name, entry.sideboard): entry.quantity for entry in loaded.deck.cards}
    assert cards == {
        ("Counterspell", False): 1,
        ("Lightning Bolt", False): 4,
        ("Thunderbolt", True): 2,
    }


async def test_import_decklist_commander_section_sets_commander_flag(seeded_card_db) -> None:
    """Exactly the Commander-section card is flagged; it stays mainboard; others are False."""
    deck_id = await _create_saved_deck(seeded_card_db)
    arena_export = """Commander
1 Counterspell (DMR) 50

Deck
4 Lightning Bolt (M11) 149

Sideboard
2 Thunderbolt (WTH) 117
"""

    async with seeded_card_db() as session:
        result = await import_decklist(session, deck_id=deck_id, arena_export=arena_export)
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "ok"
    assert [line.commander for line in result.results] == [True, False, False]

    assert loaded.deck is not None
    rows = {entry.card.name: entry for entry in loaded.deck.cards}
    assert rows["Counterspell"].commander is True
    assert rows["Counterspell"].sideboard is False
    assert rows["Lightning Bolt"].commander is False
    assert rows["Thunderbolt"].commander is False


async def test_import_decklist_reports_mixed_failures_and_keeps_successes(
    seeded_card_db,
) -> None:
    """Ambiguous, missing, and malformed lines do not undo a valid line."""
    deck_id = await _create_saved_deck(seeded_card_db)
    arena_export = """Deck
4 Lightning Bolt (M11) 149
1 bolt (TST) 1
1 Missing Card (TST) 2
this line is malformed
"""

    async with seeded_card_db() as session:
        result = await import_decklist(session, deck_id=deck_id, arena_export=arena_export)
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "partial"
    assert result.total_lines == 4
    assert result.imported_lines == 1
    assert result.imported_copies == 4
    assert [line.status for line in result.results] == [
        "ok",
        "ambiguous",
        "not_found",
        "invalid",
    ]
    assert {match.name for match in result.results[1].matches} == {
        "Lightning Bolt",
        "Thunderbolt",
    }
    assert all(f"Line {line.line_number}:" in line.message for line in result.results)

    assert loaded.deck is not None
    assert len(loaded.deck.cards) == 1
    assert loaded.deck.cards[0].card.name == "Lightning Bolt"
    assert loaded.deck.cards[0].quantity == 4


async def test_import_decklist_unknown_header_clears_previous_section(seeded_card_db) -> None:
    """A misspelled section cannot route following cards into the stale location."""
    deck_id = await _create_saved_deck(seeded_card_db)
    arena_export = """Deck
1 Lightning Bolt (M11) 149
Sidebord
1 Counterspell (DMR) 50
"""

    async with seeded_card_db() as session:
        result = await import_decklist(session, deck_id=deck_id, arena_export=arena_export)
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "partial"
    assert [line.status for line in result.results] == ["ok", "invalid", "invalid"]
    assert loaded.deck is not None
    assert [entry.card.name for entry in loaded.deck.cards] == ["Lightning Bolt"]


async def test_import_decklist_skips_about_metadata_block(seeded_card_db) -> None:
    """The Arena ``About`` / ``Name`` metadata block does not poison a valid import."""
    deck_id = await _create_saved_deck(seeded_card_db)
    arena_export = """About
Name My Burn Deck

Deck
4 Lightning Bolt (M11) 149
"""

    async with seeded_card_db() as session:
        result = await import_decklist(session, deck_id=deck_id, arena_export=arena_export)
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.total_lines == 1
    assert result.imported_lines == 1
    assert result.results[0].line_number == 5
    assert loaded.deck is not None
    assert [entry.card.name for entry in loaded.deck.cards] == ["Lightning Bolt"]


async def test_import_decklist_card_line_under_about_is_invalid(seeded_card_db) -> None:
    """A card-shaped line inside the About block fails closed, never lands in a deck."""
    deck_id = await _create_saved_deck(seeded_card_db)
    arena_export = """About
1 Lightning Bolt (M11) 149
"""

    async with seeded_card_db() as session:
        result = await import_decklist(session, deck_id=deck_id, arena_export=arena_export)
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "invalid"
    assert [line.status for line in result.results] == ["invalid"]
    assert loaded.deck is not None
    assert loaded.deck.cards == []


async def test_import_decklist_maps_companion_to_sideboard(seeded_card_db) -> None:
    """A ``Companion`` section is recognized and its card lands in the sideboard."""
    deck_id = await _create_saved_deck(seeded_card_db)
    arena_export = """Companion
1 Counterspell (DMR) 50

Deck
4 Lightning Bolt (M11) 149
"""

    async with seeded_card_db() as session:
        result = await import_decklist(session, deck_id=deck_id, arena_export=arena_export)
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "ok"
    assert result.imported_lines == 2
    assert result.results[0].section == "companion"
    assert result.results[0].sideboard is True
    assert loaded.deck is not None
    cards = {(entry.card.name, entry.sideboard): entry.quantity for entry in loaded.deck.cards}
    assert cards == {("Counterspell", True): 1, ("Lightning Bolt", False): 4}


async def test_import_decklist_existing_card_does_not_merge_quantity(seeded_card_db) -> None:
    """Re-importing a card reports exists and preserves the stored quantity."""
    deck_id = await _create_saved_deck(seeded_card_db)
    async with seeded_card_db() as session:
        added = await add_card_to_deck(session, deck_id=deck_id, name="Lightning Bolt", quantity=4)
        assert added.status == "ok"

        result = await import_decklist(
            session,
            deck_id=deck_id,
            arena_export="Deck\n1 Lightning Bolt (M11) 149",
        )
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "partial"
    assert result.imported_lines == 0
    assert result.imported_copies == 0
    assert result.results[0].status == "exists"
    assert loaded.deck is not None
    assert loaded.deck.cards[0].quantity == 4


async def test_import_decklist_rejects_blank_request_fields(seeded_card_db) -> None:
    """Blank deck id or export text returns invalid before any write."""
    async with seeded_card_db() as session:
        blank_deck = await import_decklist(
            session, deck_id="   ", arena_export="Deck\n1 Counterspell (DMR) 50"
        )
        blank_export = await import_decklist(session, deck_id="some-deck", arena_export="  \n")

    assert blank_deck.status == "invalid"
    assert blank_export.status == "invalid"


async def test_import_decklist_rejects_empty_name_as_unparseable(seeded_card_db) -> None:
    """A syntactically shaped line with only whitespace for a name is invalid."""
    async with seeded_card_db() as session:
        result = await import_decklist(
            session, deck_id="some-deck", arena_export="Deck\n1   (M11) 149"
        )

    assert result.status == "invalid"
    assert result.results[0].status == "invalid"
    assert "name" in result.results[0].message


async def test_import_decklist_rejects_oversized_quantity_without_raising(
    seeded_card_db,
) -> None:
    """Huge integer text becomes a structured invalid line, never a raw ValueError."""
    huge_quantity = "9" * 5_000
    async with seeded_card_db() as session:
        result = await import_decklist(
            session,
            deck_id="some-deck",
            arena_export=f"Deck\n{huge_quantity} Lightning Bolt (M11) 149",
        )

    assert result.status == "invalid"
    assert result.results[0].status == "invalid"
    assert "between 1 and 250" in result.results[0].message


async def test_import_decklist_rejects_oversized_blob_and_result_count(seeded_card_db) -> None:
    """Character and per-line caps bound parser work and MCP response size."""
    too_many_lines = "Deck\n" + "\n".join("1 Lightning Bolt (M11) 149" for _ in range(251))
    async with seeded_card_db() as session:
        oversized_blob = await import_decklist(
            session, deck_id="some-deck", arena_export="x" * 50_001
        )
        oversized_result = await import_decklist(
            session, deck_id="some-deck", arena_export=too_many_lines
        )

    assert oversized_blob.status == "invalid"
    assert "50000 characters" in oversized_blob.message
    assert oversized_result.status == "invalid"
    assert "250 card lines" in oversized_result.message
    assert oversized_result.results == []


async def test_import_decklist_rejects_export_without_card_lines(seeded_card_db) -> None:
    """Headers without a parseable card entry return invalid and write nothing."""
    deck_id = await _create_saved_deck(seeded_card_db)

    async with seeded_card_db() as session:
        result = await import_decklist(
            session, deck_id=deck_id, arena_export="Commander\n\nDeck\n\nSideboard"
        )
        loaded = await load_deck(session, deck_id=deck_id)

    assert result.status == "invalid"
    assert result.total_lines == 0
    assert loaded.deck is not None
    assert loaded.deck.cards == []


async def test_import_decklist_missing_deck_stops_before_lines(seeded_card_db) -> None:
    """A missing target deck returns a top-level status and no line results."""
    async with seeded_card_db() as session:
        result = await import_decklist(
            session,
            deck_id="missing-deck",
            arena_export="Deck\n1 Counterspell (DMR) 50",
        )

    assert result.status == "deck_not_found"
    assert result.results == []
    assert result.total_lines == 0


async def test_import_decklist_guards_uninitialized_database(tmp_path: Path) -> None:
    """An empty card table returns database_not_initialized before deck lookup."""
    db_path = tmp_path / "empty-import.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    await init_database(engine)
    session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            result = await import_decklist(
                session,
                deck_id="missing-deck",
                arena_export="Deck\n1 Counterspell (DMR) 50",
            )
    finally:
        await engine.dispose()

    assert result.status == "database_not_initialized"
    assert result.results == []
