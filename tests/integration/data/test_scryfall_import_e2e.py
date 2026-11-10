"""End-to-end integration tests for the Scryfall import.

Every pipeline test drives the real orchestrator, :func:`import_scryfall_bulk_data`, with only its
two network seams stood in (:mod:`tests.fixtures.scryfall_bulk`), so the stage wiring (pass 1, the
first-run marker, the upsert, the reject sample, the reconcile and its statistics) is what these
tests exercise. ``test_batch_processing`` and ``test_empty_import`` stay on :func:`import_cards`
because they pin its batching, which the orchestrator's fixed batch size cannot reach.
"""

import json
import logging
from functools import partial
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.data.database import create_engine, create_session_factory
from src.data.import_state import is_import_in_progress, mark_import_started
from src.data.importers import scryfall
from src.data.importers.importer import import_cards
from src.data.importers.parser import stream_cards
from src.data.importers.transformers import transform_scryfall_card
from src.data.models.card import CardModel
from src.data.models.deck import DeckModel
from src.data.models.deck_card import DeckCardModel
from src.data.repositories.card import CardRepository
from src.data.schemas.deck import MAX_CARD_QUANTITY
from src.mcp_server.tools.initialize_database import initialize_database
from tests.fixtures.card_data import create_om1_spm_cards
from tests.fixtures.scryfall_bulk import import_through_orchestrator, serve_bulk_file

#: The sample file's Counterspell printings: a same-day ``ja`` printing with the smaller id is
#: listed before the ``en`` one, so only the English-first rank picks the ``en`` printing.
_SAMPLE_COUNTERSPELL_JA_ID = "0c1d2e3f-4a5b-4c6d-8e7f-901a2b3c4d5e"
_SAMPLE_COUNTERSPELL_EN_ID = "8a9b0c1d-2e3f-4a5b-8c6d-7e8f9a0b1c2d"


def _wubrg_ordered(colours: list[str] | None) -> bool:
    """Whether *colours* (``None`` included) lists its WUBRG letters in WUBRG order."""
    if colours is None:
        return True
    ranks = ["WUBRG".index(colour) for colour in colours]
    return ranks == sorted(ranks)


async def test_end_to_end_import(empty_card_db, sample_json_file, monkeypatch, tmp_path):
    """The sample bulk file imports through the orchestrator: seven cards in, one rejected.

    Its Counterspell pair imports as the ``en`` printing (the ``ja`` one is skipped as
    non-canonical), and every stored colour list is WUBRG-ordered although the Transguild
    Courier printing carries Scryfall's alphabetical lists.
    """
    printings = json.loads(sample_json_file.read_text(encoding="utf-8"))

    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, printings, temp_dir=tmp_path
        )

        assert stats.total_processed == 8  # the non-canonical ja printing is skipped, not counted
        assert stats.total_inserted == 7  # 7 valid cards
        assert stats.total_errors == 1  # 1 invalid card

        result = await session.execute(select(CardModel))
        cards = result.scalars().all()
        assert {card.name for card in cards} == {
            "Lightning Bolt",
            "Black Lotus",
            "Forest",
            "Delver of Secrets // Insectile Aberration",
            "Pact of Negation",
            "Transguild Courier",
            "Counterspell",
        }

        unordered = {
            card.name: (card.colors, card.color_identity, card.color_indicator)
            for card in cards
            if not all(
                _wubrg_ordered(colours)
                for colours in (card.colors, card.color_identity, card.color_indicator)
            )
        }
        assert unordered == {}

        counterspell = next(card for card in cards if card.name == "Counterspell")
        assert counterspell.id == _SAMPLE_COUNTERSPELL_EN_ID
        assert counterspell.printed_name is None


def _printing_v1() -> dict[str, Any]:
    """A printing whose every stored column holds a value :func:`_printing_v2` changes."""
    return {
        "id": "upsert-0001",
        "name": "Old Name",
        "printed_name": "Old Printed Name",
        "oracle_id": "oracle-upsert-old",
        "mana_cost": "{1}{W}",
        "cmc": 2.0,
        "type_line": "Creature — Soldier",
        "oracle_text": "Old text.",
        "power": "1",
        "toughness": "1",
        "game_changer": False,
        "rarity": "common",
        "set": "old",
        "set_name": "Old Set",
        "collector_number": "1",
        "colors": ["W"],
        "color_identity": ["W"],
        "color_indicator": ["W"],
        "keywords": ["Flying"],
        "legalities": {"modern": "legal", "standard": "legal"},
        "card_faces": [{"name": "Old Face"}],
        "image_uris": {"normal": "https://cards.scryfall.io/normal/old.jpg"},
        "games": ["paper"],
    }


def _printing_v2() -> dict[str, Any]:
    """The same printing ``id`` with a new value in every column."""
    return {
        "id": "upsert-0001",
        "name": "New Name",
        "printed_name": "New Printed Name",
        "oracle_id": "oracle-upsert-new",
        "mana_cost": "{2}{U}{U}",
        "cmc": 4.0,
        "type_line": "Creature — Wizard",
        "oracle_text": "New text.",
        "power": "3",
        "toughness": "4",
        "game_changer": True,
        "rarity": "mythic",
        "set": "new",
        "set_name": "New Set",
        "collector_number": "99",
        "colors": ["U"],
        "color_identity": ["U"],
        "color_indicator": ["U"],
        "keywords": ["Ward"],
        "legalities": {"modern": "banned", "standard": "not_legal"},
        "card_faces": [{"name": "New Face"}],
        "image_uris": {"normal": "https://cards.scryfall.io/normal/new.jpg"},
        "games": ["arena", "mtgo"],
    }


@pytest.mark.parametrize("entry_point", ["orchestrator", "import_cards"])
async def test_reimport_updates_every_column_of_an_existing_row(
    empty_card_db, monkeypatch, tmp_path, entry_point
):
    """An ``update=true`` refresh rewrites every column of a printing it already holds.

    The upsert's update branch names its columns by hand, so a column left out of it keeps the
    first import's value forever: a new ban or Game Changer flag would never land. Every column
    is compared against what the transformer makes of the new printing, and each must differ
    from the old one, so a column added to the model without a changed value here fails too.

    Run through the orchestrator, the reconcile stage rewrites ``games`` after the upsert and so
    hides a ``games`` column missing from the update branch; a run whose reconcile fails would
    keep it stale. The ``import_cards`` case pins the upsert on its own, ``games`` included.
    """

    async def run(printing: dict[str, Any]) -> None:
        async with empty_card_db() as session:
            if entry_point == "orchestrator":
                stats = await import_through_orchestrator(
                    session, monkeypatch, [printing], temp_dir=tmp_path
                )
            else:
                stats = await import_cards(session, iter([transform_scryfall_card(printing)]))
            assert stats.total_inserted == 1

    await run(_printing_v1())
    await run(_printing_v2())

    old = transform_scryfall_card(_printing_v1())
    new = transform_scryfall_card(_printing_v2())
    assert old is not None and new is not None
    async with empty_card_db() as session:
        assert await session.scalar(select(func.count()).select_from(CardModel)) == 1
        stored = await session.get(CardModel, "upsert-0001")
        assert stored is not None

    columns = [attr.key for attr in CardModel.__mapper__.column_attrs if attr.key != "id"]
    unchanged = [key for key in columns if getattr(old, key) == getattr(new, key)]
    assert unchanged == [], "the fixture must change every column"
    stale = {
        key: getattr(stored, key) for key in columns if getattr(stored, key) != getattr(new, key)
    }
    assert stale == {}, "these columns kept the first import's value"


async def test_batch_processing(empty_card_db, tmp_path):
    """import_cards commits across several batches when the stream outgrows one."""
    cards_data = []
    for i in range(10):
        cards_data.append(
            {
                "id": f"card-{i:04d}",
                "name": f"Test Card {i}",
                "oracle_id": f"oracle-{i:04d}",
                "type_line": "Creature",
                "mana_cost": "{1}",
                "cmc": 1.0,
                "oracle_text": f"Test card number {i}",
                "colors": ["W"],
                "color_identity": ["W"],
                "keywords": [],
                "legalities": {},
                "rarity": "common",
                "set": "tst",
                "set_name": "Test Set",
                "collector_number": str(i),
            }
        )

    test_json = tmp_path / "test_batch.json"
    test_json.write_text(json.dumps(cards_data))

    async with empty_card_db() as session:
        cards_stream = stream_cards(test_json)

        def transform_cards():
            for card_json in cards_stream:
                yield transform_scryfall_card(card_json)

        # Use batch size of 3 to test multiple batches
        stats = await import_cards(session, transform_cards(), batch_size=3)

        assert stats.total_processed == 10
        assert stats.total_inserted == 10
        assert stats.total_errors == 0

        # Verify all cards were inserted
        stmt = select(CardModel)
        result = await session.execute(stmt)
        all_cards = result.scalars().all()
        assert len(all_cards) == 10


# --- Pass-2 dedup/union + reconcile (games-union spec) ----------------------------------

#: The OM1/SPM masking scenario as raw bulk-file printings: same oracle_id, the newer
#: printing paper-only, the older one arena/mtgo — a per-printing row would mask Arena.
_SHARED_ORACLE_ID = "b5b43d01-fce6-4a00-9c19-7a7e2a09d833"


def _masking_printings() -> list[dict]:
    base = {
        "name": "Ultimate Green Goblin",
        "oracle_id": _SHARED_ORACLE_ID,
        "type_line": "Legendary Creature — Goblin Villain",
        "mana_cost": "{4}{R}{G}",
        "cmc": 6.0,
        "oracle_text": "Trample, haste.",
        "colors": ["R", "G"],
        "color_identity": ["R", "G"],
        "legalities": {"modern": "legal"},
        "rarity": "rare",
    }
    return [
        {
            **base,
            "id": "spm-276",
            "set": "spm",
            "set_name": "Marvel's Spider-Man",
            "collector_number": "276",
            "released_at": "2025-09-26",
            "games": ["paper"],
        },
        {
            **base,
            "id": "om1-153",
            "set": "om1",
            "set_name": "Through the Omenpaths",
            "collector_number": "153",
            "released_at": "2025-01-24",
            "games": ["arena", "mtgo"],
        },
    ]


async def test_two_pass_import_dedups_and_unions_games(empty_card_db, monkeypatch, tmp_path):
    """Two printings of one oracle id import as ONE row with games = sorted union."""
    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, _masking_printings(), temp_dir=tmp_path
        )

        assert stats.total_inserted == 1  # non-canonical printing skipped, not errored
        assert stats.total_errors == 0
        assert stats.reconcile.games_updated == 0  # the only row was just written with the union
        assert stats.reconcile.rows_deleted == 0

        result = await session.execute(
            select(CardModel).where(CardModel.oracle_id == _SHARED_ORACLE_ID)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        # Canonical = max released_at (the 2025-09-26 paper printing), games overridden
        # with the union — the paper-only printing no longer masks Arena.
        assert rows[0].id == "spm-276"
        assert rows[0].games == ["arena", "mtgo", "paper"]


async def test_reconcile_dedups_stale_preexisting_row(empty_card_db, monkeypatch, tmp_path):
    """A pre-existing stale row is deleted; only this run's canonical row survives."""
    spm_card = create_om1_spm_cards()[0]  # the paper-only half of the masking pair
    assert spm_card.games == ["paper"]

    # Only the OM1 printing is in this run's file, so this run's canonical id (om1-153)
    # differs from the pre-existing row's id (spm-276) — the reconcile must collapse the
    # identity down to the canonical row.
    printings = [p for p in _masking_printings() if p["id"] == "om1-153"]
    printings[0]["games"] = ["arena", "mtgo", "paper"]  # union as seen across the new file

    async with empty_card_db() as session:
        # Seed the old DB state: the stale paper-only SPM printing (e.g. an older
        # oracle_cards import whose canonical pick differed).
        session.add(spm_card)
        await session.commit()

        stats = await import_through_orchestrator(
            session, monkeypatch, printings, temp_dir=tmp_path
        )

        assert stats.total_inserted == 1
        assert stats.reconcile.rows_deleted == 1  # the stale spm-276 row was collapsed away
        assert stats.reconcile.stale_remaining == 0

        result = await session.execute(
            select(CardModel).where(CardModel.oracle_id == _SHARED_ORACLE_ID)
        )
        rows = {row.id: row for row in result.scalars().all()}
        assert set(rows) == {"om1-153"}  # one row per oracle identity — the canonical
        assert rows["om1-153"].games == ["arena", "mtgo", "paper"]


async def test_two_pass_import_is_noop_for_unique_oracle_ids(empty_card_db, monkeypatch, tmp_path):
    """oracle_cards-style input (one printing per oracle id) imports every card unchanged."""
    cards_data = []
    for i in range(4):
        cards_data.append(
            {
                "id": f"card-{i:04d}",
                "name": f"Test Card {i}",
                "oracle_id": f"oracle-{i:04d}",
                "type_line": "Creature",
                "mana_cost": "{1}",
                "cmc": 1.0,
                "released_at": "2024-01-01",
                "games": ["paper", "arena"],
                "rarity": "common",
                "set": "tst",
                "set_name": "Test Set",
                "collector_number": str(i),
            }
        )

    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, cards_data, temp_dir=tmp_path
        )

        assert stats.total_inserted == 4
        assert stats.reconcile.games_updated == 0
        assert stats.reconcile.rows_deleted == 0

        result = await session.execute(select(CardModel))
        rows = result.scalars().all()
        assert len(rows) == 4
        assert all(row.games == ["arena", "paper"] for row in rows)


# --- Oracle-identity reconcile (pre-Epic-6 importer gate) --------------------------------


def _snapshot_a() -> list[dict]:
    """Snapshot A: only the OM1 printing exists (older Scryfall data, no game_changer)."""
    return [p for p in _masking_printings() if p["id"] == "om1-153"]


def _snapshot_b(game_changer: bool = True) -> list[dict]:
    """Snapshot B: both printings, canonical shifted to spm-276, game_changer populated."""
    return [{**p, "game_changer": game_changer} for p in _masking_printings()]


async def test_reimport_with_shifted_canonical_collapses_to_one_row(
    empty_card_db, monkeypatch, tmp_path
):
    """Two-snapshot re-import over a persisted DB: one row per oracle id, snapshot-B data wins."""
    # Snapshot A lands the om1-153 row (game_changer unknown back then -> NULL).
    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, _snapshot_a(), temp_dir=tmp_path
        )
        assert stats.total_inserted == 1
        result = await session.execute(select(CardModel))
        rows = result.scalars().all()
        assert [row.id for row in rows] == ["om1-153"]
        assert rows[0].game_changer is None

    # Snapshot B (new session over the SAME persisted DB file) shifts the canonical to
    # spm-276 — the damaged-DB shape a plain re-import must repair.
    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, _snapshot_b(), temp_dir=tmp_path
        )
        assert stats.total_inserted == 1
        assert stats.reconcile.rows_deleted == 1
        assert stats.reconcile.stale_remaining == 0

        result = await session.execute(
            select(CardModel).where(CardModel.oracle_id == _SHARED_ORACLE_ID)
        )
        rows = result.scalars().all()
        assert len(rows) == 1  # exactly one row per oracle identity
        survivor = rows[0]
        assert survivor.id == "spm-276"  # the snapshot-B canonical
        assert survivor.game_changer is True  # snapshot-B data on the survivor, not NULL
        assert survivor.games == ["arena", "mtgo", "paper"]

        # Name resolution lands on the canonical row (no stale printing shadows it).
        found = await CardRepository(session).find_by_name_exact("Ultimate Green Goblin")
        assert found is not None
        assert found.id == "spm-276"

    # Idempotence: an unchanged re-import performs zero deletes/repoints/updates.
    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, _snapshot_b(), temp_dir=tmp_path
        )
        assert stats.reconcile.rows_deleted == 0
        assert stats.reconcile.deck_cards_repointed == 0
        assert stats.reconcile.deck_cards_merged == 0
        assert stats.reconcile.games_updated == 0
        assert stats.reconcile.stale_remaining == 0


async def test_reconcile_repoints_deck_cards_to_canonical(empty_card_db, monkeypatch, tmp_path):
    """A deck referencing the stale printing is repointed before the stale row is deleted."""
    async with empty_card_db() as session:
        # Old DB state: the om1-153 row from an earlier import, referenced by a deck.
        session.add(create_om1_spm_cards()[1])  # om1-153
        deck = DeckModel(name="Goblin Deck", format="modern")
        session.add(deck)
        await session.flush()
        session.add(DeckCardModel(deck_id=deck.id, card_id="om1-153", quantity=4))
        await session.commit()
        deck_id = deck.id

    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, _snapshot_b(), temp_dir=tmp_path
        )
        assert stats.reconcile.rows_deleted == 1
        assert stats.reconcile.deck_cards_repointed == 1
        assert stats.reconcile.deck_cards_merged == 0

        result = await session.execute(
            select(DeckCardModel).where(DeckCardModel.deck_id == deck_id)
        )
        deck_cards = result.scalars().all()
        assert len(deck_cards) == 1
        assert deck_cards[0].card_id == "spm-276"  # repointed, not dangling
        assert deck_cards[0].quantity == 4

        result = await session.execute(
            select(CardModel).where(CardModel.oracle_id == _SHARED_ORACLE_ID)
        )
        assert [row.id for row in result.scalars().all()] == ["spm-276"]


async def test_reconcile_merges_deck_quantities_when_deck_holds_both_printings(
    empty_card_db, monkeypatch, tmp_path
):
    """Composite-PK collision: quantities sum onto the canonical row, stale entry removed."""
    async with empty_card_db() as session:
        spm_card, om1_card = create_om1_spm_cards()[:2]
        session.add(spm_card)
        session.add(om1_card)
        deck = DeckModel(name="Both Printings", format="modern")
        session.add(deck)
        await session.flush()
        # Same deck, same sideboard flag, both printings of one oracle identity.
        session.add(DeckCardModel(deck_id=deck.id, card_id="spm-276", quantity=2))
        session.add(DeckCardModel(deck_id=deck.id, card_id="om1-153", quantity=3))
        await session.commit()
        deck_id = deck.id

    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, _snapshot_b(), temp_dir=tmp_path
        )
        assert stats.reconcile.rows_deleted == 1
        assert stats.reconcile.deck_cards_merged == 1
        assert stats.reconcile.deck_cards_repointed == 0

        result = await session.execute(
            select(DeckCardModel).where(DeckCardModel.deck_id == deck_id)
        )
        deck_cards = result.scalars().all()
        assert len(deck_cards) == 1  # the stale association row is gone
        assert deck_cards[0].card_id == "spm-276"
        assert deck_cards[0].quantity == 5  # 2 + 3 summed onto the canonical row


async def test_reconcile_merge_keeps_the_stale_rows_commander_flag(
    empty_card_db, monkeypatch, tmp_path
):
    """A merged-away stale row that was the deck's commander leaves the flag on the survivor."""
    async with empty_card_db() as session:
        session.add_all(create_om1_spm_cards()[:2])
        deck = DeckModel(name="Stale Commander", format="commander")
        session.add(deck)
        await session.flush()
        session.add(DeckCardModel(deck_id=deck.id, card_id="om1-153", quantity=1, commander=True))
        session.add(DeckCardModel(deck_id=deck.id, card_id="spm-276", quantity=1))
        await session.commit()
        deck_id = deck.id

    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, _snapshot_b(), temp_dir=tmp_path
        )
        assert stats.reconcile.deck_cards_merged == 1

    async with empty_card_db() as session:
        result = await session.execute(
            select(DeckCardModel.card_id, DeckCardModel.quantity, DeckCardModel.commander).where(
                DeckCardModel.deck_id == deck_id
            )
        )
        assert result.tuples().all() == [("spm-276", 2, True)]


@pytest.mark.parametrize(
    ("held_ids", "stale_ids"),
    [
        pytest.param(("om1-153", "spm-276"), (), id="stale-onto-canonical"),
        pytest.param(("old-a", "old-b"), ("old-a", "old-b"), id="two-stale-printings"),
    ],
)
async def test_reconcile_merge_caps_the_summed_quantity(
    empty_card_db, monkeypatch, tmp_path, caplog, held_ids, stale_ids
):
    """A merge that would pass ``MAX_CARD_QUANTITY`` stores the cap and warns, naming the row.

    Every tool write path holds a deck row at 250 copies, and a reconcile is no user intent to
    exceed it. Two stale printings merging into one row need the running sum across both, not
    the canonical row's stored quantity alone.
    """
    async with empty_card_db() as session:
        if stale_ids:
            session.add_all([_stale_printing(card_id) for card_id in stale_ids])
        else:
            session.add_all(create_om1_spm_cards()[:2])
        deck = DeckModel(name="Over The Cap", format="modern")
        session.add(deck)
        await session.flush()
        for card_id, quantity in zip(held_ids, (200, 100), strict=True):
            session.add(DeckCardModel(deck_id=deck.id, card_id=card_id, quantity=quantity))
        await session.commit()
        deck_id = deck.id

    with caplog.at_level(logging.WARNING, logger="src.data.importers.scryfall"):
        async with empty_card_db() as session:
            stats = await import_through_orchestrator(
                session, monkeypatch, _snapshot_b(), temp_dir=tmp_path
            )
    assert stats.reconcile.failed is False
    assert stats.reconcile.deck_cards_merged == 1

    async with empty_card_db() as session:
        result = await session.execute(
            select(DeckCardModel.card_id, DeckCardModel.quantity).where(
                DeckCardModel.deck_id == deck_id
            )
        )
        assert result.tuples().all() == [("spm-276", MAX_CARD_QUANTITY)]

    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING and record.name == "src.data.importers.scryfall"
    ]
    assert len(warnings) == 1, warnings
    assert deck_id in warnings[0] and "spm-276" in warnings[0]
    assert "50" in warnings[0]  # the copies dropped over the cap


async def _stored_cards(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, dict]:
    """Every ``cards`` row in the database, keyed by id, as a column-name-to-value map."""
    columns = [attr.key for attr in CardModel.__mapper__.column_attrs]
    async with session_factory() as session:
        cards = (await session.execute(select(CardModel))).scalars().all()
    return {card.id: {key: getattr(card, key) for key in columns} for card in cards}


async def test_update_repairs_a_database_imported_before_the_english_first_rank(
    empty_card_db, card_db_path, sample_json_file, monkeypatch, tmp_path
):
    """``initialize_database(update=true)`` repairs a database the old importer built.

    The old state is what the date-only rank and the verbatim colour copy stored for the sample
    file: the ``ja`` Counterspell as the canonical row, Scryfall's alphabetical colour lists, and
    a deck whose commander is that ``ja`` row. After an update its ``cards`` rows equal a fresh
    import's, and the deck row points at the ``en`` printing with its commander flag kept, with
    no connect hook and no migration involved.
    """
    printings = json.loads(sample_json_file.read_text(encoding="utf-8"))
    old_rows = []
    for printing in printings:
        if printing["id"] == _SAMPLE_COUNTERSPELL_EN_ID:
            continue  # the old rank picked the ja printing instead
        card = transform_scryfall_card(printing)
        if card is None:
            continue
        card.colors = printing.get("colors") or []
        card.color_identity = printing.get("color_identity") or []
        card.color_indicator = printing.get("color_indicator")
        old_rows.append(card)

    async with empty_card_db() as session:
        session.add_all(old_rows)
        deck = DeckModel(name="Counterspell Commander", format="commander")
        session.add(deck)
        await session.flush()
        session.add(
            DeckCardModel(
                deck_id=deck.id, card_id=_SAMPLE_COUNTERSPELL_JA_ID, quantity=1, commander=True
            )
        )
        await session.commit()
        deck_id = deck.id

    serve_bulk_file(monkeypatch, printings)
    import_fn = partial(scryfall.import_scryfall_bulk_data, temp_dir=tmp_path)

    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{card_db_path.as_posix()}")
    updated = await initialize_database(import_fn=import_fn, update=True)
    assert updated.status == "updated", updated.message

    fresh_path = tmp_path / "fresh.db"
    monkeypatch.setenv("CARDS_DATABASE_URL", f"sqlite+aiosqlite:///{fresh_path.as_posix()}")
    fresh = await initialize_database(import_fn=import_fn)
    assert fresh.status == "ok", fresh.message

    fresh_engine = create_engine(f"sqlite+aiosqlite:///{fresh_path.as_posix()}")
    try:
        fresh_cards = await _stored_cards(create_session_factory(fresh_engine))
    finally:
        await fresh_engine.dispose()
    repaired_cards = await _stored_cards(empty_card_db)
    assert repaired_cards == fresh_cards
    # Not only equal to a fresh import: the seeded alphabetical lists were rewritten.
    courier = next(row for row in repaired_cards.values() if row["name"] == "Transguild Courier")
    wubrg = ["W", "U", "B", "R", "G"]
    assert (courier["colors"], courier["color_identity"], courier["color_indicator"]) == (
        wubrg,
        wubrg,
        wubrg,
    )

    async with empty_card_db() as session:
        result = await session.execute(
            select(DeckCardModel.card_id, DeckCardModel.quantity, DeckCardModel.commander).where(
                DeckCardModel.deck_id == deck_id
            )
        )
        assert result.tuples().all() == [(_SAMPLE_COUNTERSPELL_EN_ID, 1, True)]


async def test_reconcile_keeps_mainboard_and_sideboard_copies_apart(
    empty_card_db, monkeypatch, tmp_path
):
    """The reconcile keys every deck row on ``(deck, card, sideboard)``, never ``(deck, card)``.

    Three decks, each holding the stale printing (om1-153) and the canonical one (spm-276) in a
    different split of mainboard and sideboard:

    * "Stale main, canonical side": the mainboard copies are repointed, not merged into the
      sideboard row (a key without ``sideboard`` would merge into a mainboard row that does not
      exist and then delete the stale copies).
    * "Both in main, canonical side": the stale mainboard copies merge into the canonical
      mainboard row only (a merge ``WHERE`` without ``sideboard`` would add them to the sideboard
      row too).
    * "Stale in both, canonical side": the stale mainboard row is repointed and the stale sideboard
      row merges (a repoint ``WHERE`` without ``sideboard`` would move both stale rows at once,
      colliding with the canonical sideboard row).
    """
    splits: dict[str, list[tuple[str, bool, int]]] = {
        "Stale main, canonical side": [("om1-153", False, 4), ("spm-276", True, 2)],
        "Both in main, canonical side": [
            ("om1-153", False, 3),
            ("spm-276", False, 1),
            ("spm-276", True, 2),
        ],
        "Stale in both, canonical side": [
            ("om1-153", False, 2),
            ("om1-153", True, 1),
            ("spm-276", True, 3),
        ],
    }
    expected: dict[str, set[tuple[str, bool, int]]] = {
        "Stale main, canonical side": {("spm-276", False, 4), ("spm-276", True, 2)},
        "Both in main, canonical side": {("spm-276", False, 4), ("spm-276", True, 2)},
        "Stale in both, canonical side": {("spm-276", False, 2), ("spm-276", True, 4)},
    }

    deck_ids: dict[str, str] = {}
    async with empty_card_db() as session:
        session.add_all(create_om1_spm_cards()[:2])
        for name, rows in splits.items():
            deck = DeckModel(name=name, format="modern")
            session.add(deck)
            await session.flush()
            deck_ids[name] = deck.id
            for card_id, sideboard, quantity in rows:
                session.add(
                    DeckCardModel(
                        deck_id=deck.id, card_id=card_id, sideboard=sideboard, quantity=quantity
                    )
                )
        await session.commit()

    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, _snapshot_b(), temp_dir=tmp_path
        )
        assert stats.reconcile.failed is False
        assert stats.reconcile.rows_deleted == 1
        assert stats.reconcile.deck_cards_repointed == 2  # first and third decks' mainboards
        assert stats.reconcile.deck_cards_merged == 2  # second deck's main, third deck's side

    async with empty_card_db() as session:
        for name, deck_id in deck_ids.items():
            result = await session.execute(
                select(
                    DeckCardModel.card_id, DeckCardModel.sideboard, DeckCardModel.quantity
                ).where(DeckCardModel.deck_id == deck_id)
            )
            assert set(result.tuples().all()) == expected[name], name


def _stale_printing(card_id: str) -> CardModel:
    """A pre-existing stale printing row of the shared oracle identity (older import)."""
    return CardModel(
        id=card_id,
        name="Ultimate Green Goblin",
        oracle_id=_SHARED_ORACLE_ID,
        mana_cost="{4}{R}{G}",
        cmc=6.0,
        type_line="Legendary Creature — Goblin Villain",
        oracle_text="Trample, haste.",
        rarity="rare",
        set_code="OLD",
        set_name="Old Snapshot Set",
        collector_number="1",
        colors=["R", "G"],
        color_identity=["R", "G"],
        color_indicator=None,
        keywords=["Trample", "Haste"],
        legalities={"modern": "legal"},
        card_faces=None,
        games=["paper"],
    )


async def test_reconcile_collapses_two_stale_printings_held_by_one_deck(
    empty_card_db, monkeypatch, tmp_path
):
    """TWO stale printings in one deck collapse onto the canonical row with summed quantity.

    Neither pre-existing row is the canonical: the repoint of the first stale entry
    *creates* the canonical ``(deck_id, card_id, sideboard)`` key, and the second stale
    entry must then merge into it rather than collide.
    """
    async with empty_card_db() as session:
        session.add(_stale_printing("old-a"))
        session.add(_stale_printing("old-b"))
        deck = DeckModel(name="Two Stale Printings", format="modern")
        session.add(deck)
        await session.flush()
        session.add(DeckCardModel(deck_id=deck.id, card_id="old-a", quantity=2))
        session.add(DeckCardModel(deck_id=deck.id, card_id="old-b", quantity=3))
        await session.commit()
        deck_id = deck.id

    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, _snapshot_b(), temp_dir=tmp_path
        )
        assert stats.reconcile.rows_deleted == 2  # both stale printings collapsed away
        assert stats.reconcile.deck_cards_repointed == 1  # first stale entry creates the key
        assert stats.reconcile.deck_cards_merged == 1  # second merges into it
        assert stats.reconcile.stale_remaining == 0

        result = await session.execute(
            select(DeckCardModel).where(DeckCardModel.deck_id == deck_id)
        )
        deck_cards = result.scalars().all()
        assert len(deck_cards) == 1
        assert deck_cards[0].card_id == "spm-276"  # this run's canonical printing
        assert deck_cards[0].quantity == 5  # 2 + 3 summed

        result = await session.execute(
            select(CardModel).where(CardModel.oracle_id == _SHARED_ORACLE_ID)
        )
        assert [row.id for row in result.scalars().all()] == ["spm-276"]


async def test_reconcile_failure_is_nonfatal_and_leaves_session_usable(
    empty_card_db, tmp_path, monkeypatch
):
    """A failing reconcile sets ``failed`` without failing the import or the session.

    The failing reconcile poisons the session with a genuine constraint failure (a
    failed flush leaves the session in pending-rollback state), so this also pins the
    stage-6 rollback: without it, the very next session use (``mark_import_finished``)
    raises ``PendingRollbackError`` and escalates the non-fatal stage into a failed
    import. The session must stay usable for follow-up queries, and the first-run marker
    must still be cleared: the cards are all in, so the database is complete.
    """

    async def _failing_reconcile(session, aggregates):
        # Raise a genuine in-family failure (IntegrityError, a DatabaseError sibling in
        # the stage-6 handler tuple) that leaves the session dirty: the failed flush
        # puts the session in pending-rollback state as the exception propagates.
        session.add(_stale_printing("spm-276"))  # PK collides with the imported canonical
        await session.flush()
        raise AssertionError("unreachable")  # pragma: no cover

    monkeypatch.setattr(scryfall, "reconcile_oracle_identities", _failing_reconcile)

    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, _masking_printings(), temp_dir=tmp_path
        )

        assert stats.total_inserted == 1  # the card import itself succeeded
        assert stats.reconcile.failed is True  # ... but the reconcile did not masquerade as clean
        assert stats.reconcile.rows_deleted == 0

        # The session must remain usable (stage 6 rolled the failure back).
        count = await session.scalar(select(func.count()).select_from(CardModel))
        assert count == 1
        assert await is_import_in_progress(session) is False, "a complete DB left marked partial"


@pytest.mark.parametrize(
    ("starting_state", "marked_during_import"),
    [
        pytest.param("empty", True, id="first-run"),
        pytest.param("killed-mid-import", True, id="resume"),
        pytest.param("complete", False, id="update"),
    ],
)
async def test_the_first_run_marker_spans_the_import_and_is_cleared_after(
    empty_card_db, monkeypatch, tmp_path, starting_state, marked_during_import
):
    """The orchestrator flags a first-run or resumed import in progress, then clears the flag.

    A first run and a resume of a killed import (rows present, flag still set) are marked in
    progress while their batches land, so a kill mid-import leaves a database the tools refuse
    as partial. An update of a complete database is never marked, so it stays usable throughout.
    Every run ends with the flag clear. The flag is read twice through pass-through spies: before
    the first batch writes, through a second session (so only a committed marker counts, as a
    killed process would leave it), and at the reconcile stage, after the upsert has committed.
    The first read is what fails a marker set late, after the batches have already landed.
    """
    async with empty_card_db() as session:
        if starting_state != "empty":
            session.add(create_om1_spm_cards()[1])  # om1-153, a row from an earlier run
            await session.commit()
        if starting_state == "killed-mid-import":
            await mark_import_started(session)

    real_import_cards = scryfall.import_cards
    seen_before_batches: list[bool] = []

    async def spying_import_cards(*args, **kwargs):
        async with empty_card_db() as probe:  # a second session: only a committed marker counts
            seen_before_batches.append(await is_import_in_progress(probe))
        return await real_import_cards(*args, **kwargs)

    monkeypatch.setattr(scryfall, "import_cards", spying_import_cards)

    real_reconcile = scryfall.reconcile_oracle_identities
    seen_in_progress: list[bool] = []

    async def spying_reconcile(session, aggregates):
        seen_in_progress.append(await is_import_in_progress(session))
        return await real_reconcile(session, aggregates)

    monkeypatch.setattr(scryfall, "reconcile_oracle_identities", spying_reconcile)

    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, _snapshot_b(), temp_dir=tmp_path
        )
        assert stats.reconcile.failed is False

    assert seen_before_batches == [marked_during_import]
    assert seen_in_progress == [marked_during_import]
    async with empty_card_db() as session:
        assert await is_import_in_progress(session) is False


async def test_reconcile_leaves_identity_untouched_when_canonical_rejected(
    empty_card_db, monkeypatch, tmp_path
):
    """When the canonical printing is rejected, existing rows survive and get counted."""
    printings = _masking_printings()
    for printing in printings:
        if printing["id"] == "spm-276":  # the canonical pick (max released_at)
            del printing["type_line"]  # required field -> transformer rejects it

    async with empty_card_db() as session:
        om1_card = create_om1_spm_cards()[1]  # pre-existing row, games ["arena", "mtgo"]
        session.add(om1_card)
        await session.commit()

    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, printings, temp_dir=tmp_path
        )
        reconcile = stats.reconcile

        assert stats.total_errors == 1
        assert len(stats.rejects) == 1
        assert stats.rejects[0].identity == "Ultimate Green Goblin"
        assert "type_line" in stats.rejects[0].reason
        assert reconcile.stale_remaining == 1  # the identity is reported, not repaired
        assert reconcile.stale_sample == (_SHARED_ORACLE_ID,)  # sample names the oracle id
        assert reconcile.rows_deleted == 0
        assert reconcile.games_updated == 0  # touch nothing for the skipped identity

        result = await session.execute(
            select(CardModel).where(CardModel.oracle_id == _SHARED_ORACLE_ID)
        )
        rows = result.scalars().all()
        assert [row.id for row in rows] == ["om1-153"]  # existing row untouched
        assert rows[0].games == ["arena", "mtgo"]  # even its games stay as they were


async def test_import_captures_reject_identity_and_reason(empty_card_db, monkeypatch, tmp_path):
    """A transformer reject surfaces its identity + reason on ImportStatistics.rejects."""
    cards_data = [
        {
            "id": "good-0001",
            "name": "Good Card",
            "oracle_id": "oracle-good-0001",
            "type_line": "Instant",
            "released_at": "2024-01-01",
            "games": ["paper"],
        },
        {
            "id": "bad-0001",
            "name": "Bad Card",
            "oracle_id": "oracle-bad-0001",
            # no type_line -> rejected with a missing-field reason
            "released_at": "2024-01-01",
            "games": ["paper"],
        },
    ]

    async with empty_card_db() as session:
        stats = await import_through_orchestrator(
            session, monkeypatch, cards_data, temp_dir=tmp_path
        )

        assert stats.total_inserted == 1
        assert stats.total_errors == 1
        assert len(stats.rejects) == 1
        assert stats.rejects[0].identity == "Bad Card"
        assert "type_line" in stats.rejects[0].reason


async def test_empty_import(empty_card_db, tmp_path):
    """import_cards over an empty JSON array writes nothing and counts nothing."""
    empty_json = tmp_path / "empty.json"
    empty_json.write_text("[]")

    async with empty_card_db() as session:
        cards_stream = stream_cards(empty_json)

        def transform_cards():
            for card_json in cards_stream:
                yield transform_scryfall_card(card_json)

        stats = await import_cards(session, transform_cards())

        assert stats.total_processed == 0
        assert stats.total_inserted == 0
        assert stats.total_errors == 0

        # Verify no cards in database
        stmt = select(CardModel)
        result = await session.execute(stmt)
        all_cards = result.scalars().all()
        assert len(all_cards) == 0
