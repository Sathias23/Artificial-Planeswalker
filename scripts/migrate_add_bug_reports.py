"""Idempotent migration: create the ``bug_reports`` table (Story 1.3).

Builds the async engine from ``CARDS_DATABASE_URL`` and runs ``init_database``,
whose ``create_all`` is idempotent — only the missing ``bug_reports`` table is
created on the existing ``./data/cards.db``; existing tables are left untouched.

Run with:
    uv run python scripts/migrate_add_bug_reports.py
"""

import asyncio
from pathlib import Path

from sqlalchemy.engine import make_url

from src.data.database import DATABASE_URL, create_engine, init_database


async def main() -> None:
    """Create the bug_reports table if it does not already exist."""
    # Ensure the SQLite parent directory exists (e.g. ./data/ on a fresh checkout).
    url = make_url(DATABASE_URL)
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
