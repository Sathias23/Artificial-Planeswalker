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
