#!/usr/bin/env python3
"""CLI script to import the Commander Spellbook combo snapshot into the database.

Operator-initiated, never automatic: no MCP tool calls this script and the assessment
path never triggers it (FR14 — "don't re-import casually"). Upstream regenerates the
bulk export roughly every 2 hours; refresh whenever you want fresher combo data. Like
the semantic-search index, the snapshot is a build prerequisite and is never committed
— a fresh checkout has empty combo tables and assessment degrades gracefully
(``combo_data_unavailable``) until this script runs.

Usage:
    uv run python scripts/import_spellbook_combos.py
    uv run python scripts/import_spellbook_combos.py --db-path /tmp/cards.db
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from src.data.database import create_engine, create_session_factory, init_database
from src.data.importers.spellbook import import_spellbook_snapshot
from src.paths import database_path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


async def main() -> int:
    """Main entry point for the Spellbook combo-snapshot import."""
    parser = argparse.ArgumentParser(
        description="Import the Commander Spellbook bulk combo export into the local database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Downloads the bulk variant export (~26 MB gzip), normalizes each variant into the
canonical ComboRecord shape, and atomically replaces the previous snapshot in one
transaction (a failed run always leaves the previous snapshot intact). Banned-tag,
non-OK-status, and template-requirement variants are skipped and counted.

Examples:
  # Refresh the shared central database (the file the MCP server reads)
  uv run python scripts/import_spellbook_combos.py

  # Import into a throwaway DB with a custom temp directory
  uv run python scripts/import_spellbook_combos.py --db-path /tmp/cards.db --temp-dir /tmp/sb
        """,
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help=(
            "Path to SQLite database file. Defaults to the shared central database "
            "(CARDS_DATABASE_URL / PLANESWALKER_DATA_DIR aware) — the same file the MCP "
            "server uses, so a refresh actually updates the data the tools read."
        ),
    )

    parser.add_argument(
        "--temp-dir",
        type=str,
        default=None,
        help="Directory for the temporary download (default: fresh private per-run dir)",
    )

    args = parser.parse_args()

    engine = None
    try:
        db_path = Path(args.db_path) if args.db_path else database_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite+aiosqlite:///{db_path.absolute().as_posix()}"

        logger.info(f"Database path: {db_path.absolute()}")

        engine = create_engine(database_url)

        # Creates the combo tables additively on any existing DB (create_all only
        # creates missing tables) — this replaces any migration script.
        logger.info("Initializing database schema...")
        await init_database(engine)

        session_factory = create_session_factory(engine)

        temp_dir = Path(args.temp_dir) if args.temp_dir else None

        async with session_factory() as session:
            stats = await import_spellbook_snapshot(session, temp_dir=temp_dir)

        # Print final summary
        print("\n" + "=" * 70)
        print("SPELLBOOK COMBO SNAPSHOT IMPORT SUMMARY")
        print("=" * 70)
        print(f"Variants in export: {stats.total_variants:,}")
        print(f"Imported: {stats.imported:,}")
        skipped_total = stats.skipped_status + stats.skipped_requires + stats.skipped_banned
        print(f"Skipped: {skipped_total:,}")
        print(f"  - non-OK status: {stats.skipped_status:,}")
        print(f"  - template requirement (requires[]): {stats.skipped_requires:,}")
        print(f"  - banned bracket tag: {stats.skipped_banned:,}")
        print(f"Piece rows written: {stats.piece_rows:,}")
        print(f"Export version: {stats.export_version}")
        print(f"Export timestamp: {stats.export_timestamp}")
        print(f"Elapsed time: {stats.elapsed_seconds:.1f} seconds")
        print("=" * 70)

        logger.info("Combo snapshot import completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.warning("Import interrupted by user")
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        return 1

    finally:
        if engine is not None:
            await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
