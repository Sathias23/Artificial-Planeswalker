"""``build_search_index`` MCP tool: in-client, one-time semantic embedding index build.

The companion to ``initialize_database``: once the card data is imported, this builds the
``card_vec`` embedding index that powers ``semantic_search_cards`` / ``find_similar_cards``. It is a
separate, explicit step because it is heavier — it downloads a small (~80 MB) embedding model on
first run and embeds every card. Like the relational tools it guards an un-imported database
gracefully (``database_not_initialized``); the build itself is idempotent/incremental (unchanged
cards are skipped via a content hash), so re-running is cheap.
"""

import logging
from typing import Literal

from pydantic import BaseModel

from src.mcp_server.tools.messages import DATABASE_NOT_INITIALIZED_MESSAGE
from src.search import (
    ConnectionFactory,
    Embedder,
    build_card_embeddings,
    clear_card_embedding_meta,
    create_card_embedding_meta_table,
    drop_card_vec_table,
    get_embedder,
)
from src.search.query import is_database_initialized

logger = logging.getLogger(__name__)


class BuildSearchIndexResult(BaseModel):
    """Structured result of ``build_search_index``.

    Attributes:
        status: ``ok`` (index built/updated), ``database_not_initialized`` (no cards yet — run
            ``initialize_database`` first), or ``error`` (the build failed; ``message`` explains).
        cards_indexed: Cards embedded on this run (new + changed); ``0`` if everything was current.
        cards_skipped: Cards left unchanged (already current in the index).
        message: Human-facing summary.
    """

    status: Literal["ok", "database_not_initialized", "error"]
    cards_indexed: int = 0
    cards_skipped: int = 0
    message: str


def build_search_index(
    connection_factory: ConnectionFactory,
    *,
    embedder: Embedder | None = None,
    limit: int | None = None,
    rebuild: bool = False,
    prune: bool = False,
) -> BuildSearchIndexResult:
    """Build (or incrementally update) the semantic search index from the imported cards.

    Args:
        connection_factory: The sync sqlite-vec :class:`~src.search.connection.ConnectionFactory`
            (reuses the server's; resolves the same DB file as the relational tools).
        embedder: Test seam; defaults to the process-lifetime
            :func:`~src.search.embedder.get_embedder` singleton (loads the model on first call).
        limit: If set, only embed the first ``limit`` cards (fast dev/test runs).
        rebuild: Drop the existing index and re-embed every card (needed after a model change).
        prune: Remove index rows for cards no longer present after the build.

    Returns:
        A :class:`BuildSearchIndexResult`. A missing card database returns
        ``database_not_initialized`` (not an error); build failures are caught as
        ``status="error"`` rather than raised to the MCP client.
    """
    conn = connection_factory.get_connection()
    if not is_database_initialized(conn):
        return BuildSearchIndexResult(
            status="database_not_initialized", message=DATABASE_NOT_INITIALIZED_MESSAGE
        )

    try:
        # Resolve the embedder BEFORE any destructive rebuild: ``get_embedder`` downloads the
        # ~80 MB model on first run, and that download must not be able to fail *after* the existing
        # index has been dropped — otherwise a rebuild could destroy a working index and leave
        # nothing in its place.
        active_embedder = embedder if embedder is not None else get_embedder()
        if rebuild:
            # Drop the vectors and clear the hash table so every card re-embeds;
            # build_card_embeddings re-creates both tables on entry.
            drop_card_vec_table(conn)
            create_card_embedding_meta_table(conn)
            clear_card_embedding_meta(conn)
        stats = build_card_embeddings(conn, active_embedder, limit=limit, prune=prune)
    except Exception as exc:
        logger.exception("build_search_index failed")
        return BuildSearchIndexResult(
            status="error", message=f"Index build failed: {exc}. Try again."
        )

    embedded = stats.embedded_new + stats.embedded_changed
    return BuildSearchIndexResult(
        status="ok",
        cards_indexed=embedded,
        cards_skipped=stats.skipped,
        message=(
            f"Semantic search index built: {embedded:,} cards embedded, "
            f"{stats.skipped:,} already current. Semantic search is ready."
        ),
    )
