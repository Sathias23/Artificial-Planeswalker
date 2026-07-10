"""End-to-end integration tests for Scryfall import process."""

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from src.data.database import create_engine, create_session_factory, init_database
from src.data.importers.aggregate import build_oracle_aggregates
from src.data.importers.importer import import_cards
from src.data.importers.parser import stream_cards
from src.data.importers.scryfall import iter_canonical_models, reconcile_games
from src.data.importers.transformers import transform_scryfall_card
from src.data.models.card import CardModel
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
    stats = await import_cards(session, iter_canonical_models(file_path, aggregates))
    updated = await reconcile_games(session, aggregates)
    return stats, updated


@pytest.mark.asyncio
async def test_two_pass_import_dedups_and_unions_games(test_db, tmp_path):
    """Two printings of one oracle id import as ONE row with games = sorted union."""
    test_json = tmp_path / "printings.json"
    test_json.write_text(json.dumps(_masking_printings()))

    async with test_db() as session:
        stats, updated = await _run_two_pass_import(session, test_json)

        assert stats.total_inserted == 1  # non-canonical printing skipped, not errored
        assert stats.total_errors == 0
        assert updated == 0  # the only row was just written with the union already

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
async def test_reconcile_updates_stale_preexisting_row(test_db, tmp_path):
    """A pre-existing stale row (paper-only games) gets the union without being re-pointed."""
    spm_card = create_om1_spm_cards()[0]  # the paper-only half of the masking pair
    assert spm_card.games == ["paper"]

    test_json = tmp_path / "printings.json"
    # Only the OM1 printing is in this run's file, so this run's canonical id (om1-153)
    # differs from the pre-existing row's id (spm-276) — the reconcile must fix it.
    printings = [p for p in _masking_printings() if p["id"] == "om1-153"]
    printings[0]["games"] = ["arena", "mtgo", "paper"]  # union as seen across the new file
    test_json.write_text(json.dumps(printings))

    async with test_db() as session:
        # Seed the old DB state: the stale paper-only SPM printing (e.g. an older
        # oracle_cards import whose canonical pick differed), referenced by decks.
        session.add(spm_card)
        await session.commit()

        stats, updated = await _run_two_pass_import(session, test_json)

        assert stats.total_inserted == 1
        assert updated == 1  # the stale spm-276 row was reconciled

        result = await session.execute(
            select(CardModel).where(CardModel.oracle_id == _SHARED_ORACLE_ID)
        )
        rows = {row.id: row for row in result.scalars().all()}
        assert set(rows) == {"spm-276", "om1-153"}  # row kept, nothing deleted
        assert rows["spm-276"].games == ["arena", "mtgo", "paper"]
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
        stats, updated = await _run_two_pass_import(session, test_json)

        assert stats.total_inserted == 4
        assert updated == 0

        result = await session.execute(select(CardModel))
        rows = result.scalars().all()
        assert len(rows) == 4
        assert all(row.games == ["arena", "paper"] for row in rows)


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
