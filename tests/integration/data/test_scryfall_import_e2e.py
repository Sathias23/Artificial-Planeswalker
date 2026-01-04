"""End-to-end integration tests for Scryfall import process."""

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from src.data.database import create_engine, create_session_factory, init_database
from src.data.importers.importer import import_cards
from src.data.importers.parser import stream_cards
from src.data.importers.transformers import transform_scryfall_card
from src.data.models.card import CardModel


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
