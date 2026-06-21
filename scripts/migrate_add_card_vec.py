"""Idempotent migration: create the ``card_vec`` vec0 virtual table (Story 2.2).

Unlike the other ``migrate_*`` scripts (which run ``init_database`` over the async
SQLAlchemy + aiosqlite engine), this one goes through the synchronous
:class:`~src.search.connection.ConnectionFactory`. That is deliberate and required: the
async engine never calls ``enable_load_extension`` / ``sqlite_vec.load``, so
``CREATE VIRTUAL TABLE … USING vec0`` would fail there with ``no such module: vec0``.
``card_vec`` lives in the *same* ``./data/cards.db`` file as the relational tables, keyed by
``card_id`` so vectors JOIN to ``cards`` rows.

``CREATE … IF NOT EXISTS`` makes this idempotent — re-running only creates the table if it is
missing. Story 2.3's index builder populates the vectors and metadata afterwards.

Run with:
    uv run python scripts/migrate_add_card_vec.py
"""

from pathlib import Path

from src.search import ConnectionFactory
from src.search.schema import CARD_VEC_TABLE, create_card_vec_table


def main() -> None:
    """Create the ``card_vec`` virtual table if it does not already exist."""
    factory = ConnectionFactory()
    # Ensure the SQLite parent directory exists (e.g. ./data/ on a fresh checkout). The factory
    # resolves the path the same way for every consumer, so reuse it rather than re-deriving.
    Path(factory.db_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        conn = factory.get_connection()
        create_card_vec_table(conn)
        print(
            f"{CARD_VEC_TABLE} table is present (created if it was missing) in {factory.db_path}."
        )
    finally:
        factory.close()


if __name__ == "__main__":
    main()
