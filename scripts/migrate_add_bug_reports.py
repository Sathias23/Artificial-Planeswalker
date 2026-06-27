"""Idempotent migration: create the ``bug_reports`` table (Story 1.3).

Builds the async engine for the central data dir (``CARDS_DATABASE_URL`` still wins) and runs
``init_database``, whose ``create_all`` is idempotent — only the missing ``bug_reports`` table
is created on the existing ``cards.db``; existing tables are left untouched.

Run with:
    uv run python scripts/migrate_add_bug_reports.py
"""

import asyncio
from pathlib import Path

from sqlalchemy.engine import make_url

from src.data.database import create_engine, init_database
from src.paths import database_url


async def main() -> None:
    """Create the bug_reports table if it does not already exist."""
    # Ensure the SQLite parent directory exists (e.g. ./data/ on a fresh checkout).
    url = make_url(database_url())
    if url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine()
    try:
        await init_database(engine)
        print("bug_reports table is present (created if it was missing).")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
