#!/usr/bin/env python3
"""Thin sync CLI for the Story 2.3 card embedding index builder.

The **second** ``src/search`` migration-class script (after ``migrate_add_card_vec.py``) that runs
through the synchronous :class:`~src.search.connection.ConnectionFactory` rather than the async
SQLAlchemy + aiosqlite engine — required because only the factory connection loads the sqlite-vec
extension that ``card_vec`` needs. This script is the *composition root*: it wires the real
``ConnectionFactory`` connection + the :func:`~src.search.embedder.get_embedder` singleton into the
testable :func:`~src.search.index_builder.build_card_embeddings` logic in ``src/search``. All real
work lives there; this file only parses args, bootstraps, and prints a summary.

Run with:
    # Incremental build (first run downloads the ~80 MB model once, then embeds all cards):
    uv run python scripts/build_card_embeddings.py

    # Fast dev run over the first 200 cards:
    uv run python scripts/build_card_embeddings.py --limit 200

    # NFR10 model/dimension change — drop+recreate card_vec, clear hashes, full re-embed:
    uv run python scripts/build_card_embeddings.py --rebuild
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

from src.search import (
    ConnectionFactory,
    build_card_embeddings,
    clear_card_embedding_meta,
    create_card_embedding_meta_table,
    create_card_vec_table,
    drop_card_vec_table,
    get_embedder,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def _cards_table_populated(conn: sqlite3.Connection) -> bool:
    """Return whether the relational ``cards`` table exists **and** holds at least one row.

    The embedding build reads ``cards``; on a fresh database that table is absent (the Scryfall
    import has not run), so building would fail deep inside with ``no such table: cards``. This
    upfront probe lets the CLI surface the *real* first step — import the corpus — rather than that
    opaque error (the "bootstrap cliff" found in the semantic-tool live test). Mirrors
    :func:`src.search.query.index_is_populated`; ``cards`` is a fixed identifier (no user input).
    """
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'cards'"
    ).fetchone()
    if table is None:
        return False
    return bool(conn.execute("SELECT EXISTS(SELECT 1 FROM cards)").fetchone()[0])


def main() -> int:
    """Parse args, build (or rebuild) the card embedding index, and print a summary.

    Returns:
        Process exit code: ``0`` on success, ``130`` on Ctrl-C, ``1`` on any other failure.
    """
    parser = argparse.ArgumentParser(
        description="Build the card_vec semantic index from the cards table (idempotent, "
        "incremental). Re-runs re-embed only new/changed cards via a per-card content hash.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Incremental build of the whole cards table
  uv run python scripts/build_card_embeddings.py

  # Fast dev run over the first 200 cards
  uv run python scripts/build_card_embeddings.py --limit 200

  # Model/dimension-change rebuild (drops card_vec, clears hashes, full re-embed)
  uv run python scripts/build_card_embeddings.py --rebuild
        """,
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Cards read + embedded per chunk (default: 1000)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N cards (default: all) — for fast dev/test runs",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="NFR10 migration: drop+recreate card_vec and clear content hashes, then full "
        "re-embed. Required after a model or EMBEDDING_DIM change (the content hash alone "
        "cannot detect those — it would silently skip every card).",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="After building, remove orphan vectors whose card_id is no longer in cards.",
    )
    args = parser.parse_args()

    # Let the factory resolve the path the same way every src/search consumer does — no
    # CWD-relative re-derivation (Story 2.1/2.2 lesson). Only ensure the parent dir exists.
    factory = ConnectionFactory()
    Path(factory.db_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        conn = factory.get_connection()

        # Bootstrap guard: embeddings are built FROM the cards table, so importing the Scryfall
        # corpus is the true first step. Surface that explicitly instead of a deep
        # "no such table: cards" — and before downloading the ~80 MB model for nothing.
        if not _cards_table_populated(conn):
            logger.error(
                "No card data found — the `cards` table is missing or empty. The embedding index "
                "is built FROM the cards table, so import the Scryfall corpus first:\n"
                "    uv run python scripts/import_scryfall_data.py\n"
                "then re-run this build (import -> build embeddings -> search)."
            )
            return 1

        if args.rebuild:
            logger.info("--rebuild: dropping card_vec, recreating, and clearing content hashes")
            drop_card_vec_table(conn)
            create_card_vec_table(conn)
            create_card_embedding_meta_table(conn)  # ensure it exists before clearing
            clear_card_embedding_meta(conn)

        # Composition root: the real process-lifetime embedder singleton (downloads the model
        # once on first use into the persistent FASTEMBED_CACHE_DIR).
        embedder = get_embedder()

        stats = build_card_embeddings(
            conn,
            embedder,
            batch_size=args.batch_size,
            limit=args.limit,
            prune=args.prune,
        )

        print("\n" + "=" * 70)
        print("EMBEDDING INDEX BUILD SUMMARY")
        print("=" * 70)
        print(f"Database:           {factory.db_path}")
        print(f"Total processed:    {stats.processed:,} cards")
        print(f"Embedded (new):     {stats.embedded_new:,}")
        print(f"Embedded (changed): {stats.embedded_changed:,}")
        print(f"Skipped (unchanged):{stats.skipped:,}")
        print(f"Pruned (orphans):   {stats.pruned:,}")
        print(f"Elapsed time:       {stats.elapsed_time():.1f} seconds")
        print(f"Throughput:         {stats.cards_per_second():.1f} cards/second")
        print("=" * 70)

        logger.info("Embedding index build completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.warning("Build interrupted by user")
        return 130  # standard exit code for SIGINT

    except Exception as exc:  # noqa: BLE001 — top-level CLI guard logs + returns non-zero
        logger.error("Build failed: %s", exc, exc_info=True)
        return 1

    finally:
        factory.close()


if __name__ == "__main__":
    sys.exit(main())
