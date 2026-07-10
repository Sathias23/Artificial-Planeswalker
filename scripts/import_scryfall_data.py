#!/usr/bin/env python3
"""CLI script to import Scryfall bulk data into the database."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from src.data.database import create_engine, create_session_factory, init_database
from src.data.importers.scryfall import import_scryfall_bulk_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


async def main() -> int:
    """Main entry point for Scryfall data import."""
    parser = argparse.ArgumentParser(
        description="Import Scryfall bulk data into the Magic: The Gathering card database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
The importer deduplicates any bulk type to one row per oracle identity and stores
`games` as the union across all printings (so Arena/MTGO availability is never
masked by a paper-only printing). Pre-existing rows from older imports get their
`games` reconciled to the union as a final step.

Examples:
  # Import default cards (default; ~500 MB, all printings -> deduped rows w/ union games)
  uv run scripts/import_scryfall_data.py

  # Import oracle cards (smaller download; dedup/union is a natural no-op)
  uv run scripts/import_scryfall_data.py --type oracle_cards --db-path /tmp/cards.db

  # Import with custom temp directory
  uv run scripts/import_scryfall_data.py --temp-dir /tmp/scryfall
        """,
    )

    parser.add_argument(
        "--type",
        type=str,
        default="default_cards",
        choices=["oracle_cards", "default_cards", "unique_artwork"],
        help=(
            "Bulk data type to import (default: default_cards — all printings, deduplicated "
            "to one row per oracle identity with union-of-printings games)"
        ),
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default="data/cards.db",
        help="Path to SQLite database file (default: data/cards.db)",
    )

    parser.add_argument(
        "--temp-dir",
        type=str,
        default=None,
        help="Directory for temporary download files (default: system temp)",
    )

    args = parser.parse_args()

    try:
        # Construct database URL
        db_path = Path(args.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite+aiosqlite:///{db_path.absolute()}"

        logger.info(f"Database path: {db_path.absolute()}")
        logger.info(f"Bulk data type: {args.type}")

        # Create database engine
        engine = create_engine(database_url)

        # Initialize database schema
        logger.info("Initializing database schema...")
        await init_database(engine)

        # Create session factory
        session_factory = create_session_factory(engine)

        # Parse temp directory
        temp_dir = Path(args.temp_dir) if args.temp_dir else None

        # Import bulk data
        async with session_factory() as session:
            stats = await import_scryfall_bulk_data(
                session=session,
                bulk_type=args.type,
                temp_dir=temp_dir,
            )

        # Print final summary
        print("\n" + "=" * 70)
        print("IMPORT SUMMARY")
        print("=" * 70)
        print(f"Total processed: {stats.total_processed:,} cards")
        print(f"Successfully inserted: {stats.total_inserted:,} cards")
        print(f"Errors: {stats.total_errors}")
        print(f"Elapsed time: {stats.elapsed_time():.1f} seconds")
        print(f"Throughput: {stats.cards_per_second():.1f} cards/second")
        print("=" * 70)

        # Cleanup engine
        await engine.dispose()

        logger.info("Import completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.warning("Import interrupted by user")
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
