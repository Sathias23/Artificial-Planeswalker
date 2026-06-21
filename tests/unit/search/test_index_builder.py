"""Unit tests for the card embedding index builder (compose/hash + idempotent incremental build).

These run the **real** bundled sqlite-vec C extension via ``ConnectionFactory`` on a ``tmp_path``
DB but inject a **fake embedder** (deterministic one-hot vectors, no model load / no network), so
they are fast unit tests — *not* ``@pytest.mark.integration`` (one optional integration test at the
bottom drives the real fastembed model and is marked accordingly). Mirrors ``test_schema.py``:
``tmp_path`` DB, positional row indexing, ``factory.close()`` teardown.
"""

import json
import sqlite3

import numpy as np
import pytest
import sqlite_vec
from numpy.typing import NDArray

from src.search import (
    ConnectionFactory,
    build_card_embeddings,
    clear_card_embedding_meta,
    compose_card_text,
    content_hash,
    create_card_vec_table,
    drop_card_vec_table,
    get_embedder,
)
from src.search.embedder import EMBEDDING_DIM, reset_embedder
from src.search.schema import (
    CARD_EMBEDDING_META_TABLE,
    CARD_ID_COL,
    CARD_VEC_TABLE,
    COLOR_COLS,
    CONTENT_HASH_COL,
    EMBEDDING_COL,
    MANA_VALUE_COL,
)


class _FakeEmbedder:
    """Deterministic offline stand-in for :class:`~src.search.embedder.Embedder`.

    Maps each *distinct* composite text to a distinct one-hot 384-dim ``float32`` vector (stable
    per instance), so KNN nearest-neighbour assertions are exact and a changed text yields a
    different vector — all without loading the ~80 MB ONNX model.
    """

    def __init__(self) -> None:
        self.dim = EMBEDDING_DIM
        self._assigned: dict[str, int] = {}
        self.total_embedded = 0

    def _vector_for(self, text: str) -> NDArray[np.float32]:
        if text not in self._assigned:
            self._assigned[text] = len(self._assigned) % EMBEDDING_DIM
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        vec[self._assigned[text]] = 1.0
        return vec

    def encode_batch(self, texts: list[str]) -> list[NDArray[np.float32]]:
        self.total_embedded += len(texts)
        return [self._vector_for(t) for t in texts]


def _make_factory(tmp_path) -> ConnectionFactory:
    """Build a ConnectionFactory on a tmp DB and create a minimal ``cards`` read-table on it."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()
    conn.execute(
        "CREATE TABLE cards ("
        "id TEXT PRIMARY KEY, name TEXT NOT NULL, type_line TEXT, mana_cost TEXT, "
        "oracle_text TEXT, keywords TEXT, colors TEXT, cmc REAL)"
    )
    conn.commit()
    return factory


def _seed_card(
    conn: sqlite3.Connection,
    card_id: str,
    *,
    name: str,
    type_line: str = "Creature — Test",
    mana_cost: str = "{1}",
    oracle_text: str = "Does a thing.",
    keywords: list[str] | None = None,
    colors: list[str] | None = None,
    cmc: float = 1.0,
) -> None:
    """Insert one synthetic card. ``keywords``/``colors`` stored as JSON text (``None`` → NULL)."""
    conn.execute(
        "INSERT INTO cards (id, name, type_line, mana_cost, oracle_text, keywords, colors, cmc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            card_id,
            name,
            type_line,
            mana_cost,
            oracle_text,
            json.dumps(keywords) if keywords is not None else None,
            json.dumps(colors) if colors is not None else None,
            cmc,
        ),
    )
    conn.commit()


def _vec_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {CARD_VEC_TABLE}").fetchone()[0])


def _knn(
    conn: sqlite3.Connection, query: NDArray[np.float32], k: int, *, where: str = ""
) -> list[tuple[str, float]]:
    """KNN over card_vec (``k`` mandatory on vec0), optionally with a metadata pre-filter."""
    sql = (
        f"SELECT {CARD_ID_COL}, distance FROM {CARD_VEC_TABLE} "
        f"WHERE {EMBEDDING_COL} MATCH ? AND k = ? {where} ORDER BY distance"
    )
    return conn.execute(sql, (sqlite_vec.serialize_float32(query), k)).fetchall()


def _metadata_row(conn: sqlite3.Connection, card_id: str) -> tuple[int, ...]:
    """Return ``(mana_value, color_w, color_u, color_b, color_r, color_g)`` for a card_vec row."""
    cols = f"{MANA_VALUE_COL}, {', '.join(COLOR_COLS)}"
    return conn.execute(
        f"SELECT {cols} FROM {CARD_VEC_TABLE} WHERE {CARD_ID_COL} = ?", (card_id,)
    ).fetchone()


# --- compose_card_text / content_hash: pure & stable --------------------------------------


def test_compose_card_text_is_stable_and_never_empty() -> None:
    """compose_card_text is deterministic, order-stable, and never empty (name is NOT NULL)."""
    a = compose_card_text("Bolt", "Instant", "{R}", "Deal 3 damage.", ["Flash"])
    b = compose_card_text("Bolt", "Instant", "{R}", "Deal 3 damage.", ["Flash"])
    assert a == b
    # Even with every other field empty, the name keeps the composite non-empty.
    assert compose_card_text("Onlyname", "", "", "", []).strip() != ""


def test_content_hash_is_pure_and_field_sensitive() -> None:
    """Same composite text → same hash; any field change → different hash."""
    base = compose_card_text("Bolt", "Instant", "{R}", "Deal 3 damage.", [])
    assert content_hash(base) == content_hash(base)
    changed_text = compose_card_text("Bolt", "Instant", "{R}", "Deal 4 damage.", [])
    assert content_hash(base) != content_hash(changed_text)
    changed_kw = compose_card_text("Bolt", "Instant", "{R}", "Deal 3 damage.", ["Flash"])
    assert content_hash(base) != content_hash(changed_kw)


# --- AC1: first build inserts vectors + populates metadata ----------------------------------


def test_first_build_inserts_and_populates_metadata(tmp_path) -> None:
    """AC1: first build embeds every card, writes one card_vec row each, populates metadata."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    _seed_card(conn, "id-r", name="Red Card", colors=["R"], cmc=3.0)
    _seed_card(conn, "id-wu", name="Azorius Card", colors=["W", "U"], cmc=4.0)
    _seed_card(conn, "id-colorless", name="Artifact Card", colors=[], cmc=2.0)

    stats = build_card_embeddings(conn, _FakeEmbedder())

    assert stats.processed == 3
    assert stats.embedded_new == 3
    assert stats.embedded_changed == 0
    assert stats.skipped == 0
    assert _vec_count(conn) == 3

    # mana_value = int(cmc); colours map from cards.colors in COLOR_COLS order (W,U,B,R,G).
    assert _metadata_row(conn, "id-r") == (3, 0, 0, 0, 1, 0)  # color_r set
    assert _metadata_row(conn, "id-wu") == (4, 1, 1, 0, 0, 0)  # color_w + color_u set
    assert _metadata_row(conn, "id-colorless") == (2, 0, 0, 0, 0, 0)

    factory.close()


def test_metadata_filtered_knn_returns_expected_card(tmp_path) -> None:
    """AC1: a metadata-filtered KNN over the built index returns the matching card."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    _seed_card(conn, "id-r", name="Red Card", oracle_text="Burn.", colors=["R"], cmc=3.0)
    _seed_card(conn, "id-u", name="Blue Card", oracle_text="Draw.", colors=["U"], cmc=3.0)
    build_card_embeddings(conn, fake)

    # Query with the red card's own embedding, filtered to red cards → it comes back at distance 0.
    red_text = compose_card_text("Red Card", "Creature — Test", "{1}", "Burn.", [])
    rows = _knn(conn, fake.encode_batch([red_text])[0], k=2, where="AND color_r = 1")
    returned = {row[0] for row in rows}
    assert returned == {"id-r"}  # color_u card excluded by the pre-filter
    assert rows[0][1] == pytest.approx(0.0, abs=1e-6)

    factory.close()


# --- AC2: incremental — idempotent skip, changed re-embed, new card ------------------------


def test_rerun_skips_all_unchanged_cards(tmp_path) -> None:
    """AC2: a second build with identical cards re-embeds 0 and leaves the row count stable."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    for i in range(5):
        _seed_card(conn, f"id-{i}", name=f"Card {i}", oracle_text=f"Text {i}", cmc=float(i))
    build_card_embeddings(conn, fake)
    embedded_after_first = fake.total_embedded

    stats = build_card_embeddings(conn, fake)

    assert stats.processed == 5
    assert stats.embedded_new == 0
    assert stats.embedded_changed == 0
    assert stats.skipped == 5
    assert fake.total_embedded == embedded_after_first  # encode_batch not called again
    assert _vec_count(conn) == 5  # no duplicates

    factory.close()


def test_changed_card_reembeds_without_duplicate(tmp_path) -> None:
    """AC2/AC3: mutating one card's text re-embeds only it (DELETE-then-INSERT), no duplicate."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    _seed_card(conn, "id-a", name="Card A", oracle_text="Original.", cmc=1.0)
    _seed_card(conn, "id-b", name="Card B", oracle_text="Stable.", cmc=2.0)
    build_card_embeddings(conn, fake)

    conn.execute("UPDATE cards SET oracle_text = ? WHERE id = ?", ("Mutated text.", "id-a"))
    conn.commit()
    stats = build_card_embeddings(conn, fake)

    assert stats.embedded_changed == 1
    assert stats.embedded_new == 0
    assert stats.skipped == 1
    assert _vec_count(conn) == 2  # still one row per card — DELETE-then-INSERT, not a duplicate

    # The stored hash now matches the NEW composite text, and the NEW vector is what KNN finds.
    new_text = compose_card_text("Card A", "Creature — Test", "{1}", "Mutated text.", [])
    stored_hash = conn.execute(
        f"SELECT {CONTENT_HASH_COL} FROM {CARD_EMBEDDING_META_TABLE} WHERE {CARD_ID_COL} = ?",
        ("id-a",),
    ).fetchone()[0]
    assert stored_hash == content_hash(new_text)
    rows = _knn(conn, fake.encode_batch([new_text])[0], k=1)
    assert rows[0][0] == "id-a"
    assert rows[0][1] == pytest.approx(0.0, abs=1e-6)

    factory.close()


def test_new_card_added_only_it_is_embedded(tmp_path) -> None:
    """AC2: adding a card and re-running embeds only the new one; existing cards are skipped."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    _seed_card(conn, "id-a", name="Card A")
    _seed_card(conn, "id-b", name="Card B")
    build_card_embeddings(conn, fake)

    _seed_card(conn, "id-c", name="Card C")
    stats = build_card_embeddings(conn, fake)

    assert stats.embedded_new == 1
    assert stats.embedded_changed == 0
    assert stats.skipped == 2
    assert _vec_count(conn) == 3

    factory.close()


# --- AC3: convergence across chunk boundaries ----------------------------------------------


def test_small_batch_size_converges_to_complete_index(tmp_path) -> None:
    """AC3/AC4: chunked builds (batch_size < card count) still produce one row per card."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    for i in range(7):
        _seed_card(conn, f"id-{i}", name=f"Card {i}", oracle_text=f"Text {i}")

    stats = build_card_embeddings(conn, fake, batch_size=2)

    assert stats.processed == 7
    assert stats.embedded_new == 7
    assert _vec_count(conn) == 7

    factory.close()


# --- AC5: rebuild path / limit / prune -----------------------------------------------------


def test_rebuild_clears_hashes_and_full_reembeds(tmp_path) -> None:
    """AC5: drop card_vec + clear hashes ⇒ next build treats every card as new (model/dim swap)."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    for i in range(4):
        _seed_card(conn, f"id-{i}", name=f"Card {i}", oracle_text=f"Text {i}")
    build_card_embeddings(conn, fake)

    # Simulate the CLI --rebuild sequence (drop+recreate card_vec, clear content hashes).
    drop_card_vec_table(conn)
    create_card_vec_table(conn)
    clear_card_embedding_meta(conn)

    stats = build_card_embeddings(conn, fake)

    assert stats.embedded_new == 4  # nothing skipped — the silent-skip trap is avoided
    assert stats.skipped == 0
    assert _vec_count(conn) == 4

    factory.close()


def test_limit_processes_only_first_n_cards(tmp_path) -> None:
    """AC5: --limit N processes only the first N cards."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    for i in range(6):
        _seed_card(conn, f"id-{i}", name=f"Card {i}", oracle_text=f"Text {i}")

    stats = build_card_embeddings(conn, _FakeEmbedder(), limit=4)

    assert stats.processed == 4
    assert _vec_count(conn) == 4

    factory.close()


def test_prune_removes_orphan_vectors(tmp_path) -> None:
    """Recommended prune: a card removed from cards leaves no orphan vector/hash after prune."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    _seed_card(conn, "id-keep", name="Keeper")
    _seed_card(conn, "id-drop", name="Doomed")
    build_card_embeddings(conn, fake)
    assert _vec_count(conn) == 2

    conn.execute("DELETE FROM cards WHERE id = ?", ("id-drop",))
    conn.commit()
    stats = build_card_embeddings(conn, fake, prune=True)

    assert stats.pruned == 1
    assert _vec_count(conn) == 1
    meta_ids = {
        row[0]
        for row in conn.execute(f"SELECT {CARD_ID_COL} FROM {CARD_EMBEDDING_META_TABLE}").fetchall()
    }
    assert meta_ids == {"id-keep"}

    factory.close()


# --- JSON None coercion --------------------------------------------------------------------


def test_null_keywords_and_colors_coerce_to_empty(tmp_path) -> None:
    """AC1: a card with NULL keywords/colors builds without error (coerced to [])."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    _seed_card(conn, "id-null", name="Null Card", keywords=None, colors=None, cmc=5.0)

    stats = build_card_embeddings(conn, _FakeEmbedder())

    assert stats.embedded_new == 1
    assert _metadata_row(conn, "id-null") == (5, 0, 0, 0, 0, 0)  # no colour flags set

    factory.close()


# --- Optional: real fastembed end-to-end ---------------------------------------------------


@pytest.mark.integration
def test_real_embedder_end_to_end(tmp_path) -> None:
    """Integration: real fastembed → serialize → KNN finds the embedded card (model download)."""
    reset_embedder()
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    _seed_card(
        conn,
        "id-bolt",
        name="Lightning Bolt",
        type_line="Instant",
        mana_cost="{R}",
        oracle_text="Lightning Bolt deals 3 damage to any target.",
        colors=["R"],
        cmc=1.0,
    )
    _seed_card(
        conn,
        "id-counter",
        name="Counterspell",
        type_line="Instant",
        mana_cost="{U}{U}",
        oracle_text="Counter target spell.",
        colors=["U"],
        cmc=2.0,
    )

    embedder = get_embedder()
    stats = build_card_embeddings(conn, embedder)
    assert stats.embedded_new == 2

    query = embedder.encode(
        compose_card_text(
            "Lightning Bolt",
            "Instant",
            "{R}",
            "Lightning Bolt deals 3 damage to any target.",
            [],
        )
    )
    rows = _knn(conn, query, k=2)
    assert rows[0][0] == "id-bolt"  # its own text embeds nearest to itself

    factory.close()
    reset_embedder()
