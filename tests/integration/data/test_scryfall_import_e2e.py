"""End-to-end integration tests for Scryfall import process."""

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from src.data.database import create_engine, create_session_factory, init_database
from src.data.importers.aggregate import build_oracle_aggregates
from src.data.importers.importer import import_cards
from src.data.importers.parser import stream_cards
from src.data.importers.scryfall import (
    import_scryfall_bulk_data,
    iter_canonical_models,
    reconcile_oracle_identities,
)
from src.data.importers.transformers import TransformReject, transform_scryfall_card
from src.data.models.card import CardModel
from src.data.models.deck import DeckModel
from src.data.models.deck_card import DeckCardModel
from src.data.repositories.card import CardRepository
from tests.fixtures.card_data import create_om1_spm_cards


@pytest.fixture
async def test_db(tmp_path):
    """Create a temporary test database."""
    db_path = tmp_path / "test_cards.db"
    database_url = f"sqlite+aiosqlite:///{db_path}"

    engine = create_engine(database_url)
    await init_database(engine)

    session_factory = create_session_factory(engine)

    yield session_factory

    await engine.dispose()


@pytest.fixture
def sample_json_file():
    """Return path to sample Scryfall JSON fixture."""
    return Path(__file__).parent.parent.parent / "fixtures" / "scryfall_sample.json"


@pytest.mark.asyncio
async def test_end_to_end_import(test_db, sample_json_file):
    """Test complete import pipeline from JSON to database."""
    async with test_db() as session:
        # Parse JSON and transform cards
        cards_stream = stream_cards(sample_json_file)

        def transform_cards():
            for card_json in cards_stream:
                yield transform_scryfall_card(card_json)

        # Import into database
        stats = await import_cards(session, transform_cards(), batch_size=3)

        # Verify statistics
        assert stats.total_processed == 6
        assert stats.total_inserted == 5  # 5 valid cards
        assert stats.total_errors == 1  # 1 invalid card

        # Verify cards were inserted
        stmt = select(CardModel)
        result = await session.execute(stmt)
        all_cards = result.scalars().all()

        assert len(all_cards) == 5

        # Verify specific cards
        card_names = {card.name for card in all_cards}
        assert "Lightning Bolt" in card_names
        assert "Black Lotus" in card_names
        assert "Forest" in card_names
        assert "Delver of Secrets // Insectile Aberration" in card_names
        assert "Pact of Negation" in card_names


@pytest.mark.asyncio
async def test_upsert_duplicate_cards(test_db, sample_json_file):
    """Test that re-importing cards updates existing records."""
    # First import - use a new session
    async with test_db() as session:
        cards_stream = stream_cards(sample_json_file)

        def transform_cards():
            for card_json in cards_stream:
                yield transform_scryfall_card(card_json)

        stats1 = await import_cards(session, transform_cards(), batch_size=10)
        assert stats1.total_inserted == 5

        # Query Lightning Bolt
        stmt = select(CardModel).where(CardModel.name == "Lightning Bolt")
        result = await session.execute(stmt)
        bolt_v1 = result.scalar_one()
        assert bolt_v1.oracle_text == "Lightning Bolt deals 3 damage to any target."

    # Second import with modified data - use a new session
    async with test_db() as session:
        cards_stream2 = stream_cards(sample_json_file)

        def transform_cards2():
            for card_json in cards_stream2:
                # Modify Lightning Bolt's oracle text
                if card_json.get("name") == "Lightning Bolt":
                    card_json = card_json.copy()
                    card_json["oracle_text"] = "UPDATED TEXT"
                yield transform_scryfall_card(card_json)

        await import_cards(session, transform_cards2(), batch_size=10)

        # Should still only have 5 cards (upsert, not duplicate)
        stmt = select(CardModel)
        result = await session.execute(stmt)
        all_cards = result.scalars().all()
        assert len(all_cards) == 5

        # Verify Lightning Bolt was updated
        stmt = select(CardModel).where(CardModel.name == "Lightning Bolt")
        result = await session.execute(stmt)
        bolt_v2 = result.scalar_one()
        assert bolt_v2.oracle_text == "UPDATED TEXT"


@pytest.mark.asyncio
async def test_batch_processing(test_db, tmp_path):
    """Test that batch processing works correctly with multiple batches."""
    # Create a JSON file with 10 cards
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

    async with test_db() as session:
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


async def _run_two_pass_import(session, file_path: Path):
    """Run the real pass-1 + pass-2 + reconcile pipeline over *file_path*."""
    aggregates = build_oracle_aggregates(file_path)
    rejects: list[TransformReject] = []
    stats = await import_cards(
        session, iter_canonical_models(file_path, aggregates, rejects), rejects=rejects
    )
    reconcile = await reconcile_oracle_identities(session, aggregates)
    stats.reconcile = reconcile
    return stats, reconcile


@pytest.mark.asyncio
async def test_two_pass_import_dedups_and_unions_games(test_db, tmp_path):
    """Two printings of one oracle id import as ONE row with games = sorted union."""
    test_json = tmp_path / "printings.json"
    test_json.write_text(json.dumps(_masking_printings()))

    async with test_db() as session:
        stats, reconcile = await _run_two_pass_import(session, test_json)

        assert stats.total_inserted == 1  # non-canonical printing skipped, not errored
        assert stats.total_errors == 0
        assert reconcile.games_updated == 0  # the only row was just written with the union
        assert reconcile.rows_deleted == 0

        result = await session.execute(
            select(CardModel).where(CardModel.oracle_id == _SHARED_ORACLE_ID)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        # Canonical = max released_at (the 2025-09-26 paper printing), games overridden
        # with the union — the paper-only printing no longer masks Arena.
        assert rows[0].id == "spm-276"
        assert rows[0].games == ["arena", "mtgo", "paper"]


@pytest.mark.asyncio
async def test_reconcile_dedups_stale_preexisting_row(test_db, tmp_path):
    """A pre-existing stale row is deleted; only this run's canonical row survives."""
    spm_card = create_om1_spm_cards()[0]  # the paper-only half of the masking pair
    assert spm_card.games == ["paper"]

    test_json = tmp_path / "printings.json"
    # Only the OM1 printing is in this run's file, so this run's canonical id (om1-153)
    # differs from the pre-existing row's id (spm-276) — the reconcile must collapse the
    # identity down to the canonical row.
    printings = [p for p in _masking_printings() if p["id"] == "om1-153"]
    printings[0]["games"] = ["arena", "mtgo", "paper"]  # union as seen across the new file
    test_json.write_text(json.dumps(printings))

    async with test_db() as session:
        # Seed the old DB state: the stale paper-only SPM printing (e.g. an older
        # oracle_cards import whose canonical pick differed).
        session.add(spm_card)
        await session.commit()

        stats, reconcile = await _run_two_pass_import(session, test_json)

        assert stats.total_inserted == 1
        assert reconcile.rows_deleted == 1  # the stale spm-276 row was collapsed away
        assert reconcile.stale_remaining == 0

        result = await session.execute(
            select(CardModel).where(CardModel.oracle_id == _SHARED_ORACLE_ID)
        )
        rows = {row.id: row for row in result.scalars().all()}
        assert set(rows) == {"om1-153"}  # one row per oracle identity — the canonical
        assert rows["om1-153"].games == ["arena", "mtgo", "paper"]


@pytest.mark.asyncio
async def test_two_pass_import_is_noop_for_unique_oracle_ids(test_db, tmp_path):
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
    test_json = tmp_path / "oracle_style.json"
    test_json.write_text(json.dumps(cards_data))

    async with test_db() as session:
        stats, reconcile = await _run_two_pass_import(session, test_json)

        assert stats.total_inserted == 4
        assert reconcile.games_updated == 0
        assert reconcile.rows_deleted == 0

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


@pytest.mark.asyncio
async def test_reimport_with_shifted_canonical_collapses_to_one_row(test_db, tmp_path):
    """Two-snapshot re-import over a persisted DB: one row per oracle id, snapshot-B data wins."""
    snapshot_a = tmp_path / "snapshot_a.json"
    snapshot_a.write_text(json.dumps(_snapshot_a()))
    snapshot_b = tmp_path / "snapshot_b.json"
    snapshot_b.write_text(json.dumps(_snapshot_b()))

    # Snapshot A lands the om1-153 row (game_changer unknown back then -> NULL).
    async with test_db() as session:
        stats, _ = await _run_two_pass_import(session, snapshot_a)
        assert stats.total_inserted == 1
        result = await session.execute(select(CardModel))
        rows = result.scalars().all()
        assert [row.id for row in rows] == ["om1-153"]
        assert rows[0].game_changer is None

    # Snapshot B (new session over the SAME persisted DB file) shifts the canonical to
    # spm-276 — the damaged-DB shape a plain re-import must repair.
    async with test_db() as session:
        stats, reconcile = await _run_two_pass_import(session, snapshot_b)
        assert stats.total_inserted == 1
        assert reconcile.rows_deleted == 1
        assert reconcile.stale_remaining == 0

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
    async with test_db() as session:
        _, reconcile = await _run_two_pass_import(session, snapshot_b)
        assert reconcile.rows_deleted == 0
        assert reconcile.deck_cards_repointed == 0
        assert reconcile.deck_cards_merged == 0
        assert reconcile.games_updated == 0
        assert reconcile.stale_remaining == 0


@pytest.mark.asyncio
async def test_reconcile_repoints_deck_cards_to_canonical(test_db, tmp_path):
    """A deck referencing the stale printing is repointed before the stale row is deleted."""
    snapshot_b = tmp_path / "snapshot_b.json"
    snapshot_b.write_text(json.dumps(_snapshot_b()))

    async with test_db() as session:
        # Old DB state: the om1-153 row from an earlier import, referenced by a deck.
        session.add(create_om1_spm_cards()[1])  # om1-153
        deck = DeckModel(name="Goblin Deck", format="modern")
        session.add(deck)
        await session.flush()
        session.add(DeckCardModel(deck_id=deck.id, card_id="om1-153", quantity=4))
        await session.commit()
        deck_id = deck.id

    async with test_db() as session:
        _, reconcile = await _run_two_pass_import(session, snapshot_b)
        assert reconcile.rows_deleted == 1
        assert reconcile.deck_cards_repointed == 1
        assert reconcile.deck_cards_merged == 0

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


@pytest.mark.asyncio
async def test_reconcile_merges_deck_quantities_when_deck_holds_both_printings(test_db, tmp_path):
    """Composite-PK collision: quantities sum onto the canonical row, stale entry removed."""
    snapshot_b = tmp_path / "snapshot_b.json"
    snapshot_b.write_text(json.dumps(_snapshot_b()))

    async with test_db() as session:
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

    async with test_db() as session:
        _, reconcile = await _run_two_pass_import(session, snapshot_b)
        assert reconcile.rows_deleted == 1
        assert reconcile.deck_cards_merged == 1
        assert reconcile.deck_cards_repointed == 0

        result = await session.execute(
            select(DeckCardModel).where(DeckCardModel.deck_id == deck_id)
        )
        deck_cards = result.scalars().all()
        assert len(deck_cards) == 1  # the stale association row is gone
        assert deck_cards[0].card_id == "spm-276"
        assert deck_cards[0].quantity == 5  # 2 + 3 summed onto the canonical row


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


@pytest.mark.asyncio
async def test_reconcile_collapses_two_stale_printings_held_by_one_deck(test_db, tmp_path):
    """TWO stale printings in one deck collapse onto the canonical row with summed quantity.

    Neither pre-existing row is the canonical: the repoint of the first stale entry
    *creates* the canonical ``(deck_id, card_id, sideboard)`` key, and the second stale
    entry must then merge into it rather than collide.
    """
    snapshot_b = tmp_path / "snapshot_b.json"
    snapshot_b.write_text(json.dumps(_snapshot_b()))

    async with test_db() as session:
        session.add(_stale_printing("old-a"))
        session.add(_stale_printing("old-b"))
        deck = DeckModel(name="Two Stale Printings", format="modern")
        session.add(deck)
        await session.flush()
        session.add(DeckCardModel(deck_id=deck.id, card_id="old-a", quantity=2))
        session.add(DeckCardModel(deck_id=deck.id, card_id="old-b", quantity=3))
        await session.commit()
        deck_id = deck.id

    async with test_db() as session:
        _, reconcile = await _run_two_pass_import(session, snapshot_b)
        assert reconcile.rows_deleted == 2  # both stale printings collapsed away
        assert reconcile.deck_cards_repointed == 1  # first stale entry creates the key
        assert reconcile.deck_cards_merged == 1  # second merges into it
        assert reconcile.stale_remaining == 0

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


@pytest.mark.asyncio
async def test_reconcile_failure_is_nonfatal_and_leaves_session_usable(
    test_db, tmp_path, monkeypatch
):
    """A failing reconcile sets ``failed`` without failing the import or the session.

    The failing reconcile poisons the session with a genuine constraint failure (a
    failed flush leaves the session in pending-rollback state), so this also pins the
    stage-6 rollback: without it, the very next session use (``mark_import_finished``)
    raises ``PendingRollbackError`` and escalates the non-fatal stage into a failed
    import. The session must stay usable for follow-up queries.
    """

    async def _fake_fetch_bulk_data_list():
        return [
            {
                "type": "default_cards",
                "download_uri": "https://data.scryfall.io/default_cards.json",
                "size": 1024,
            }
        ]

    async def _fake_download(uri, output_file, max_bytes=0):
        output_file.write_text(json.dumps(_masking_printings()))
        return output_file

    async def _failing_reconcile(session, aggregates):
        # Raise a genuine in-family failure (IntegrityError, a DatabaseError sibling in
        # the stage-6 handler tuple) that leaves the session dirty: the failed flush
        # puts the session in pending-rollback state as the exception propagates.
        session.add(_stale_printing("spm-276"))  # PK collides with the imported canonical
        await session.flush()
        raise AssertionError("unreachable")  # pragma: no cover

    monkeypatch.setattr(
        "src.data.importers.scryfall.fetch_bulk_data_list", _fake_fetch_bulk_data_list
    )
    monkeypatch.setattr("src.data.importers.scryfall.download_bulk_data", _fake_download)
    monkeypatch.setattr(
        "src.data.importers.scryfall.reconcile_oracle_identities", _failing_reconcile
    )

    async with test_db() as session:
        stats = await import_scryfall_bulk_data(
            session, bulk_type="default_cards", temp_dir=tmp_path
        )

        assert stats.total_inserted == 1  # the card import itself succeeded
        assert stats.reconcile.failed is True  # ... but the reconcile did not masquerade as clean
        assert stats.reconcile.rows_deleted == 0

        # The session must remain usable (stage 6 rolled the failure back).
        count = await session.scalar(select(func.count()).select_from(CardModel))
        assert count == 1


@pytest.mark.asyncio
async def test_reconcile_leaves_identity_untouched_when_canonical_rejected(test_db, tmp_path):
    """When the canonical printing is rejected, existing rows survive and get counted."""
    printings = _masking_printings()
    for printing in printings:
        if printing["id"] == "spm-276":  # the canonical pick (max released_at)
            del printing["type_line"]  # required field -> transformer rejects it
    snapshot = tmp_path / "snapshot_rejected_canonical.json"
    snapshot.write_text(json.dumps(printings))

    async with test_db() as session:
        om1_card = create_om1_spm_cards()[1]  # pre-existing row, games ["arena", "mtgo"]
        session.add(om1_card)
        await session.commit()

    async with test_db() as session:
        stats, reconcile = await _run_two_pass_import(session, snapshot)

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


@pytest.mark.asyncio
async def test_import_captures_reject_identity_and_reason(test_db, tmp_path):
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
    snapshot = tmp_path / "with_reject.json"
    snapshot.write_text(json.dumps(cards_data))

    async with test_db() as session:
        stats, _ = await _run_two_pass_import(session, snapshot)

        assert stats.total_inserted == 1
        assert stats.total_errors == 1
        assert len(stats.rejects) == 1
        assert stats.rejects[0].identity == "Bad Card"
        assert "type_line" in stats.rejects[0].reason


@pytest.mark.asyncio
async def test_empty_import(test_db, tmp_path):
    """Test importing an empty JSON array."""
    empty_json = tmp_path / "empty.json"
    empty_json.write_text("[]")

    async with test_db() as session:
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
