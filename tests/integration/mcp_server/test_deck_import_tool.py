"""Integration tests for bulk Arena deck import."""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.data.database import create_engine, create_session_factory, init_database
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
