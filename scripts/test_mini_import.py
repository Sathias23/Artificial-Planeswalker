#!/usr/bin/env python3
"""Quick test to import sample fixture data."""

import asyncio
import sys
from pathlib import Path

from src.data.database import create_engine, create_session_factory, init_database
from src.data.importers.importer import import_cards
from src.data.importers.parser import stream_cards
from src.data.importers.transformers import transform_scryfall_card


async def main() -> int:
    """Test import with sample fixture data."""
    try:
        print("Testing import with sample fixture data...")

        # Setup test database
        db_path = Path("data/test_import.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite+aiosqlite:///{db_path.absolute()}"

        engine = create_engine(database_url)
        await init_database(engine)
        session_factory = create_session_factory(engine)

        # Import sample data
        fixture_path = Path("tests/fixtures/scryfall_sample.json")
        print(f"Importing from: {fixture_path}")

        async with session_factory() as session:
            cards_stream = stream_cards(fixture_path)

            def transform_cards():
                for card_json in cards_stream:
                    yield transform_scryfall_card(card_json)

            stats = await import_cards(session, transform_cards(), batch_size=10)

        print("\nImport complete!")
        print(f"  Total processed: {stats.total_processed}")
        print(f"  Successfully inserted: {stats.total_inserted}")
        print(f"  Errors: {stats.total_errors}")
        print(f"  Time: {stats.elapsed_time():.2f} seconds")

        await engine.dispose()

        # Cleanup test database
        if db_path.exists():
            db_path.unlink()
            print(f"\nCleaned up test database: {db_path}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
