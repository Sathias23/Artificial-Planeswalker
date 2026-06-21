"""Unit tests for the card_vec vec0 schema (create/drop, shape, metadata-filtered KNN, JOIN).

These use the **real** bundled sqlite-vec C extension via ``ConnectionFactory`` on a ``tmp_path``
DB — no network and no model load — so they are fast unit tests (not ``@pytest.mark.integration``,
unlike the Embedder's real-model test). ``sqlite_vec.serialize_float32`` is used to insert vectors;
serializing in a *test* is correct here (production serialization is Story 2.3's index builder).
"""

import sqlite3

import pytest
import sqlite_vec

from src.search import ConnectionFactory, create_card_vec_table, drop_card_vec_table
from src.search.embedder import EMBEDDING_DIM
from src.search.schema import (
    CARD_ID_COL,
    CARD_VEC_TABLE,
    COLOR_COLS,
    EMBEDDING_COL,
    MANA_VALUE_COL,
    METADATA_COLS,
)

_INSERT_SQL = (
    f"INSERT INTO {CARD_VEC_TABLE} "
    f"({CARD_ID_COL}, {EMBEDDING_COL}, {MANA_VALUE_COL}, {', '.join(COLOR_COLS)})"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)


def _basis_vector(index: int) -> list[float]:
    """A deterministic, well-separated 384-dim vector: a one-hot at ``index``.

    Two distinct basis vectors are L2-distance ``sqrt(2)`` apart and a query equal to one of
    them has distance 0 to it, so nearest-neighbour assertions are stable.
    """
    vec = [0.0] * EMBEDDING_DIM
    vec[index] = 1.0
    return vec


def _insert_card(
    conn: sqlite3.Connection,
    card_id: str,
    vector: list[float],
    *,
    mana_value: int,
    color_w: int = 0,
    color_u: int = 0,
    color_b: int = 0,
    color_r: int = 0,
    color_g: int = 0,
) -> None:
    """Insert one synthetic card vector + metadata via ``serialize_float32``."""
    conn.execute(
        _INSERT_SQL,
        (
            card_id,
            sqlite_vec.serialize_float32(vector),
            mana_value,
            color_w,
            color_u,
            color_b,
            color_r,
            color_g,
        ),
    )
    conn.commit()


def _knn(
    conn: sqlite3.Connection, query: list[float], k: int, *, where: str = ""
) -> list[tuple[str, float]]:
    """Run a KNN query (``k`` mandatory on vec0), optionally with a metadata pre-filter.

    Returns ``(card_id, distance)`` tuples ordered nearest-first. Connections from
    ``ConnectionFactory`` use the default tuple row factory, so callers index positionally.
    """
    sql = (
        f"SELECT {CARD_ID_COL}, distance FROM {CARD_VEC_TABLE} "
        f"WHERE {EMBEDDING_COL} MATCH ? AND k = ? {where} ORDER BY distance"
    )
    return conn.execute(sql, (sqlite_vec.serialize_float32(query), k)).fetchall()


def test_create_card_vec_table_is_idempotent(tmp_path) -> None:
    """AC1/AC4: calling create twice raises nothing and leaves exactly one card_vec table."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()

    create_card_vec_table(conn)
    create_card_vec_table(conn)  # second call must be a no-op (IF NOT EXISTS)

    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (CARD_VEC_TABLE,),
    ).fetchall()
    assert len(rows) == 1

    factory.close()


def test_table_shape_has_text_key_and_metadata_columns(tmp_path) -> None:
    """AC1/AC2/AC3: card_id TEXT PK + embedding + all six metadata columns with correct types."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()
    create_card_vec_table(conn)

    # Verify every declared column is accessible on the empty table (raises if any is missing).
    cols = ", ".join((CARD_ID_COL, EMBEDDING_COL, *METADATA_COLS))
    conn.execute(f"SELECT {cols} FROM {CARD_VEC_TABLE} LIMIT 0")

    # PRAGMA table_info returns empty type strings for all vec0 columns (a vec0 quirk), so
    # verify declared types via the stored DDL in sqlite_master — the authoritative record.
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (CARD_VEC_TABLE,),
    ).fetchone()
    assert row is not None, f"{CARD_VEC_TABLE} not found in sqlite_master"
    ddl = row[0]
    assert f"{CARD_ID_COL} TEXT PRIMARY KEY" in ddl, "card_id should be TEXT PRIMARY KEY"
    for col in METADATA_COLS:
        assert f"{col} integer" in ddl, f"{col} should be declared integer in DDL"

    factory.close()


def test_insert_and_plain_knn_returns_nearest(tmp_path) -> None:
    """AC5: inserting ≥3 distinct 384-dim vectors and a plain KNN returns the nearest card_id."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()
    create_card_vec_table(conn)

    _insert_card(conn, "card-aaa", _basis_vector(0), mana_value=2)
    _insert_card(conn, "card-bbb", _basis_vector(1), mana_value=3)
    _insert_card(conn, "card-ccc", _basis_vector(2), mana_value=4)

    rows = _knn(conn, _basis_vector(1), k=3)

    assert rows[0][0] == "card-bbb"  # query == card-bbb's vector → distance 0
    assert len(rows) == 3

    factory.close()


def test_metadata_filtered_knn_excludes_off_filter_card(tmp_path) -> None:
    """AC2/AC5 (core): a metadata pre-filter excludes the nearest off-filter card from results."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()
    create_card_vec_table(conn)

    # card-aaa is the nearest to the query, but is OFF-filter (mana_value=2, color_r=0).
    _insert_card(conn, "card-aaa", _basis_vector(0), mana_value=2, color_r=0)
    _insert_card(conn, "card-bbb", _basis_vector(1), mana_value=4, color_r=1)
    _insert_card(conn, "card-ccc", _basis_vector(2), mana_value=4, color_r=1)

    rows = _knn(conn, _basis_vector(0), k=3, where="AND mana_value = 4 AND color_r = 1")
    returned = {row[0] for row in rows}

    assert "card-aaa" not in returned  # excluded by the pre-filter despite being nearest
    assert returned == {"card-bbb", "card-ccc"}

    factory.close()


def test_join_to_cards_resolves_display_field(tmp_path) -> None:
    """AC1/AC3: a JOIN on card_vec.card_id = cards.id (TEXT = TEXT) resolves display data."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()
    create_card_vec_table(conn)

    # A minimal relational sibling with a TEXT UUID-style PK, mirroring the real cards.id.
    conn.execute("CREATE TABLE cards (id TEXT PRIMARY KEY, name TEXT)")
    _insert_card(conn, "card-aaa", _basis_vector(0), mana_value=2)
    _insert_card(conn, "card-bbb", _basis_vector(1), mana_value=4)
    conn.executemany(
        "INSERT INTO cards (id, name) VALUES (?, ?)",
        [("card-aaa", "Lightning Bolt"), ("card-bbb", "Counterspell")],
    )
    conn.commit()

    rows = conn.execute(
        f"SELECT c.name, v.distance FROM {CARD_VEC_TABLE} v "
        "JOIN cards c ON c.id = v.card_id "
        f"WHERE v.{EMBEDDING_COL} MATCH ? AND v.k = ? ORDER BY v.distance",
        (sqlite_vec.serialize_float32(_basis_vector(1)), 2),
    ).fetchall()

    assert rows[0][0] == "Counterspell"  # nearest card's display field resolved via JOIN

    factory.close()


def test_drop_card_vec_table_removes_table(tmp_path) -> None:
    """AC4: drop removes the table — a subsequent SELECT raises 'no such table'."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()
    create_card_vec_table(conn)

    drop_card_vec_table(conn)

    with pytest.raises(sqlite3.OperationalError):
        conn.execute(f"SELECT {CARD_ID_COL} FROM {CARD_VEC_TABLE} LIMIT 1")

    factory.close()


def test_drop_card_vec_table_is_idempotent(tmp_path) -> None:
    """AC4: dropping a non-existent card_vec table is a no-op (DROP … IF EXISTS)."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()

    drop_card_vec_table(conn)  # never created — must not raise

    factory.close()
