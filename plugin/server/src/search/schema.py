"""``card_vec`` ``vec0`` schema: create/drop the sqlite-vec virtual table keyed to ``cards``."""

import logging
import sqlite3

from src.search.embedder import EMBEDDING_DIM

logger = logging.getLogger(__name__)

# --- Schema identifiers (single source of truth for Stories 2.3-2.5) -----------------------
# The index builder (2.3) and search tools (2.4-2.5) import these rather than hardcoding the
# table/column names; the vector dimension comes from EMBEDDING_DIM (Story 2.1) — never 384.
CARD_VEC_TABLE = "card_vec"
CARD_ID_COL = "card_id"
EMBEDDING_COL = "embedding"
MANA_VALUE_COL = "mana_value"
COLOR_COLS = ("color_w", "color_u", "color_b", "color_r", "color_g")
#: All filterable in-``vec0`` metadata columns, in declaration order (mana value + 5 colors).
#: These are the ONLY columns usable in a KNN ``WHERE`` pre-filter; everything else
#: (legality, name, type_line, oracle_text, image_uris, …) resolves via JOIN to ``cards``.
METADATA_COLS = (MANA_VALUE_COL, *COLOR_COLS)

# --- Companion content-hash table (Story 2.3) ----------------------------------------------
# ``card_embedding_meta`` is an *ordinary relational* table (no ``vec0``, no extension needed),
# but it belongs to the **search index**, so it is created on the same sync ``ConnectionFactory``
# connection as ``card_vec`` — keeping the whole index pipeline on one connection/script. The
# index builder (2.3) stores ``sha256(compose_card_text(...))`` per ``card_id`` here so a re-run
# re-embeds only cards whose composite text changed. It is deliberately NOT on ``Base.metadata``
# / ``init_database`` (that is the async relational engine's domain — see project-context.md's
# sync-vs-async boundary).
CARD_EMBEDDING_META_TABLE = "card_embedding_meta"
#: The content-hash table reuses :data:`CARD_ID_COL` for its primary key (1:1 with ``card_vec``).
CONTENT_HASH_COL = "content_hash"


def _build_create_ddl() -> str:
    """Assemble the ``CREATE VIRTUAL TABLE … USING vec0(…)`` DDL from the schema constants.

    The vector dimension is interpolated from :data:`~src.search.embedder.EMBEDDING_DIM`
    because ``float[N]`` has no SQL bind-parameter form — the dim must be a literal in the DDL
    string. All metadata columns are declared ``integer`` (``mana_value`` is ``int(cmc)`` and
    the colours are 0/1 flags), so a uniform builder over :data:`METADATA_COLS` suffices.

    Returns:
        The full DDL string (no trailing semicolon).
    """
    metadata_ddl = ",\n    ".join(f"{col} integer" for col in METADATA_COLS)
    return (
        f"CREATE VIRTUAL TABLE IF NOT EXISTS {CARD_VEC_TABLE} USING vec0(\n"
        f"    {CARD_ID_COL} TEXT PRIMARY KEY,\n"
        f"    {EMBEDDING_COL} float[{EMBEDDING_DIM}],\n"
        f"    {metadata_ddl}\n"
        ")"
    )


def create_card_vec_table(conn: sqlite3.Connection) -> None:
    """Create the ``card_vec`` ``vec0`` virtual table if it does not already exist.

    Declares a ``vec0`` table keyed by a **TEXT** ``card_id`` (the Scryfall UUID from
    ``cards.id`` — *not* an integer rowid; a SQLite rowid cannot hold a UUID), a
    ``float[EMBEDDING_DIM]`` ``embedding`` column, and six filterable metadata columns
    (``mana_value`` + ``color_w/u/b/r/g``) for KNN pre-filtering. Format-legality and all
    display fields resolve via JOIN on ``card_vec.card_id = cards.id`` — they are deliberately
    NOT metadata columns. The default L2 distance metric is kept (ranking-equivalent to cosine
    for the L2-normalized bge vectors).

    The statement uses ``IF NOT EXISTS``, so calling this repeatedly is idempotent and leaves a
    single table. This story creates an **empty** table; Story 2.3's index builder populates the
    embedding and metadata values.

    Args:
        conn: A ``sqlite3.Connection`` obtained from
            :class:`~src.search.connection.ConnectionFactory` — i.e. with the ``sqlite-vec``
            extension already loaded. A plain connection (e.g. the async SQLAlchemy engine,
            which does not load the extension) raises ``no such module: vec0``.

    Returns:
        None.

    Raises:
        sqlite3.OperationalError: If ``conn`` has not loaded the sqlite-vec extension
            (``no such module: vec0``), or on any other DDL failure.

    Example:
        >>> from src.search import ConnectionFactory
        >>> factory = ConnectionFactory(db_path="./data/cards.db")
        >>> create_card_vec_table(factory.get_connection())
    """
    ddl = _build_create_ddl()
    conn.execute(ddl)
    conn.commit()
    logger.info("Ensured %s vec0 table exists (dim=%s)", CARD_VEC_TABLE, EMBEDDING_DIM)


def drop_card_vec_table(conn: sqlite3.Connection) -> None:
    """Drop the ``card_vec`` virtual table if it exists — the NFR10 rebuild seam.

    A ``vec0`` virtual table **cannot** be ``ALTER``-ed to change its vector dimension or add
    columns, so the only supported migration for a model/dimension change is a **rebuild**:
    ``drop_card_vec_table`` → :func:`create_card_vec_table` → re-run the Story 2.3 index builder.
    (Ops note: ``PRAGMA wal_checkpoint(TRUNCATE)`` before any file-copy backup of ``cards.db``,
    or the latest vectors may sit unflushed in the ``-wal`` file.)

    Args:
        conn: A ``sqlite3.Connection`` from
            :class:`~src.search.connection.ConnectionFactory`.

    Returns:
        None.

    Raises:
        sqlite3.OperationalError: On a DDL failure other than the table being absent
            (``DROP TABLE IF EXISTS`` tolerates absence).

    Example:
        >>> from src.search import ConnectionFactory
        >>> factory = ConnectionFactory(db_path="./data/cards.db")
        >>> drop_card_vec_table(factory.get_connection())  # rebuild step 1 of 3
    """
    conn.execute(f"DROP TABLE IF EXISTS {CARD_VEC_TABLE}")
    conn.commit()
    logger.info("Dropped %s vec0 table if it existed", CARD_VEC_TABLE)


def create_card_embedding_meta_table(conn: sqlite3.Connection) -> None:
    """Create the ``card_embedding_meta`` content-hash table if it does not already exist.

    This is an **ordinary relational table** — ``card_id TEXT PRIMARY KEY`` 1:1 with
    ``card_vec``, plus a ``content_hash TEXT NOT NULL`` holding
    ``sha256(compose_card_text(...))`` for each card. The Story 2.3 index builder consults it to
    decide which cards changed since the last build (re-embed) versus stayed identical (skip).
    Unlike ``card_vec`` it is a plain table, so the relational ``UPSERT``
    (``INSERT … ON CONFLICT(card_id) DO UPDATE``) works on it — the builder relies on that.

    The statement uses ``IF NOT EXISTS``, so calling this repeatedly is idempotent. It is created
    through the **same sync ``ConnectionFactory`` connection** as ``card_vec`` so the whole
    search-index pipeline stays on one connection; it does **not** require the sqlite-vec
    extension (it is not a ``vec0`` table).

    Args:
        conn: A ``sqlite3.Connection`` (from
            :class:`~src.search.connection.ConnectionFactory`). The sqlite-vec extension is not
            needed for this plain table, but using the factory connection keeps the index schema
            on a single seam.

    Returns:
        None.

    Raises:
        sqlite3.OperationalError: On a DDL failure.

    Example:
        >>> from src.search import ConnectionFactory
        >>> factory = ConnectionFactory(db_path="./data/cards.db")
        >>> create_card_embedding_meta_table(factory.get_connection())
    """
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {CARD_EMBEDDING_META_TABLE} (\n"
        f"    {CARD_ID_COL} TEXT PRIMARY KEY,\n"
        f"    {CONTENT_HASH_COL} TEXT NOT NULL\n"
        ")"
    )
    conn.commit()
    logger.info("Ensured %s content-hash table exists", CARD_EMBEDDING_META_TABLE)


def clear_card_embedding_meta(conn: sqlite3.Connection) -> None:
    """Delete every stored content hash — the mandatory first step of the ``--rebuild`` path.

    The content hash detects *text* changes only; a model or ``EMBEDDING_DIM`` change leaves
    every card's text (and hash) identical, so without clearing the hashes a post-model-swap
    rebuild would classify every card as "unchanged" and **silently skip them all**. The NFR10
    rebuild therefore runs ``drop_card_vec_table`` → :func:`create_card_vec_table` →
    ``clear_card_embedding_meta`` → full re-embed. Clearing the hashes makes the next build see
    "no stored hash → new → embed" for every card.

    Idempotent and safe on an absent table is **not** guaranteed here (a missing table raises);
    the builder/CLI always ensures the table exists first via
    :func:`create_card_embedding_meta_table`.

    Args:
        conn: A ``sqlite3.Connection`` from
            :class:`~src.search.connection.ConnectionFactory`.

    Returns:
        None.

    Raises:
        sqlite3.OperationalError: If the table does not exist (create it first).

    Example:
        >>> from src.search import ConnectionFactory
        >>> factory = ConnectionFactory(db_path="./data/cards.db")
        >>> conn = factory.get_connection()
        >>> create_card_embedding_meta_table(conn)
        >>> clear_card_embedding_meta(conn)  # rebuild step 3 of 4 (before full re-embed)
    """
    conn.execute(f"DELETE FROM {CARD_EMBEDDING_META_TABLE}")
    conn.commit()
    logger.info("Cleared all rows from %s (rebuild path)", CARD_EMBEDDING_META_TABLE)
