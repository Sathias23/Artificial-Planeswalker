"""Unit tests for the hybrid query infra (``src/search/query.py::hybrid_search``).

Drive ``hybrid_search`` directly on a ``tmp_path`` ``card_vec`` populated through the **real**
bundled sqlite-vec extension (via ``ConnectionFactory``) but with a **fake one-hot embedder** —
no model download, no network — so these are fast unit tests (not ``@pytest.mark.integration``),
mirroring ``test_schema.py`` / ``test_index_builder.py``. Covers: mandatory ``k`` / over-fetch
bounding, the ``mana_value`` + colour metadata pre-filter, the JOIN-side legality/games
post-filter, oracle-id de-dup across duplicate printings, ``limit`` capping, and the empty result.

The window-widening tests build their database through ``init_database`` (the real ``cards``
schema) and rank thousands of cards with :class:`~tests.fixtures.embedder.RankedEmbedder`, counting
the KNN statements each search issues through ``conn.set_trace_callback``.
"""

import asyncio
import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from src.data.database import create_engine, init_database
from src.search import (
    ConnectionFactory,
    build_card_embeddings,
    compose_card_text,
    create_card_vec_table,
)
from src.search.embedder import EMBEDDING_DIM
from src.search.query import (
    _MAX_OVER_FETCH_K,
    CardHit,
    get_card_vector,
    hybrid_search,
    index_is_populated,
)
from tests.fixtures.embedder import FakeEmbedder, seed_ranked_cards


def _make_factory(tmp_path) -> ConnectionFactory:
    """ConnectionFactory on a tmp DB with a ``cards`` table holding both the builder-read columns
    and the JOIN/display columns ``hybrid_search`` resolves (oracle_id, rarity, set_code, …)."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()
    conn.execute(
        "CREATE TABLE cards ("
        "id TEXT PRIMARY KEY, oracle_id TEXT NOT NULL, name TEXT NOT NULL, type_line TEXT, "
        "mana_cost TEXT, oracle_text TEXT, keywords TEXT, colors TEXT, cmc REAL, "
        "rarity TEXT, set_code TEXT, legalities TEXT, games TEXT)"
    )
    conn.commit()
    return factory


def _seed_card(
    conn: sqlite3.Connection,
    card_id: str,
    *,
    name: str,
    oracle_id: str | None = None,
    type_line: str = "Creature — Test",
    mana_cost: str = "{1}",
    oracle_text: str = "Does a thing.",
    keywords: list[str] | None = None,
    colors: list[str] | None = None,
    cmc: float = 1.0,
    rarity: str = "common",
    set_code: str = "TST",
    legalities: dict[str, str] | None = None,
    games: list[str] | None = None,
) -> None:
    """Insert one synthetic card; JSON columns stored as text (``None`` → NULL)."""
    conn.execute(
        "INSERT INTO cards (id, oracle_id, name, type_line, mana_cost, oracle_text, keywords, "
        "colors, cmc, rarity, set_code, legalities, games) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            card_id,
            oracle_id if oracle_id is not None else f"oracle-{card_id}",
            name,
            type_line,
            mana_cost,
            oracle_text,
            json.dumps(keywords) if keywords is not None else None,
            json.dumps(colors) if colors is not None else None,
            cmc,
            rarity,
            set_code,
            json.dumps(legalities) if legalities is not None else None,
            json.dumps(games) if games is not None else None,
        ),
    )
    conn.commit()


def _qvec(
    fake: FakeEmbedder,
    *,
    name: str,
    type_line: str = "Creature — Test",
    mana_cost: str = "{1}",
    oracle_text: str = "Does a thing.",
    keywords: list[str] | None = None,
) -> NDArray[np.float32]:
    """The exact vector a seeded card embeds to (same compose recipe the builder used)."""
    return fake.encode(compose_card_text(name, type_line, mana_cost, oracle_text, keywords or []))


def _real_schema_factory(tmp_path: Path) -> ConnectionFactory:
    """A ConnectionFactory on a ``tmp_path`` database whose schema ``init_database`` built."""
    db_path = tmp_path / "real.db"

    async def _init() -> None:
        engine = create_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
        try:
            await init_database(engine)
        finally:
            await engine.dispose()

    asyncio.run(_init())
    return ConnectionFactory(db_path=str(db_path))


_KNN_K = re.compile(r"\bk = (\d+)")


@contextmanager
def _knn_ks(conn: sqlite3.Connection) -> Iterator[list[int]]:
    """Collect the ``k`` every KNN statement on ``conn`` binds, in order, while the block runs."""
    ks: list[int] = []

    def _trace(sql: str) -> None:
        if "MATCH" in sql:
            ks.extend(int(k) for k in _KNN_K.findall(sql))

    conn.set_trace_callback(_trace)
    try:
        yield ks
    finally:
        conn.set_trace_callback(None)


# --- index_is_populated: the G3 "is the semantic index usable?" probe -----------------------


def test_index_is_populated_false_when_table_missing(tmp_path) -> None:
    """A fresh DB with no ``card_vec`` table reads as not-populated (no OperationalError)."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    assert index_is_populated(conn) is False
    factory.close()


def test_index_is_populated_false_when_table_empty(tmp_path) -> None:
    """An existing but row-less ``card_vec`` reads as not-populated."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    create_card_vec_table(conn)
    assert index_is_populated(conn) is False
    factory.close()


def test_index_is_populated_true_after_build(tmp_path) -> None:
    """Once vectors are built, the probe reads as populated."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    _seed_card(conn, "id-r", name="Red Card", oracle_text="Burn.", colors=["R"], cmc=3.0)
    build_card_embeddings(conn, FakeEmbedder())
    assert index_is_populated(conn) is True
    factory.close()


# --- Plain query: nearest-first, every CardHit field populated ------------------------------


def test_returns_card_hits_nearest_first(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(
        conn,
        "id-r",
        name="Red Card",
        oracle_text="Burn.",
        colors=["R"],
        cmc=3.0,
        rarity="rare",
        set_code="ABC",
        legalities={"standard": "legal"},
        games=["arena"],
    )
    _seed_card(
        conn,
        "id-u",
        name="Blue Card",
        oracle_text="Draw.",
        colors=["U"],
        cmc=2.0,
        legalities={"standard": "legal"},
        games=["arena"],
    )
    build_card_embeddings(conn, fake)

    hits = hybrid_search(conn, _qvec(fake, name="Red Card", oracle_text="Burn."), limit=10)

    assert isinstance(hits[0], CardHit)
    assert hits[0].card_id == "id-r"
    assert hits[0].oracle_id == "oracle-id-r"
    assert hits[0].distance == pytest.approx(0.0, abs=1e-6)
    assert hits[0].name == "Red Card"
    assert hits[0].colors == ["R"]
    assert hits[0].cmc == 3.0
    assert hits[0].rarity == "rare"
    assert hits[0].set_code == "ABC"
    # distances are non-decreasing (nearest-first)
    assert all(hits[i].distance <= hits[i + 1].distance for i in range(len(hits) - 1))
    factory.close()


# --- Metadata pre-filter (inside the KNN): colours + mana range -----------------------------


def test_color_prefilter_excludes_off_color_even_when_nearest(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "id-r", name="Red Card", oracle_text="Burn.", colors=["R"], cmc=3.0)
    _seed_card(conn, "id-u", name="Blue Card", oracle_text="Draw.", colors=["U"], cmc=2.0)
    build_card_embeddings(conn, fake)

    # Query is the blue card's own vector (nearest = blue), but colours=["R"] excludes it.
    hits = hybrid_search(conn, _qvec(fake, name="Blue Card", oracle_text="Draw."), colors=["R"])

    assert {h.card_id for h in hits} == {"id-r"}
    factory.close()


def test_mana_range_prefilter_excludes_out_of_range(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "id-3", name="Three Drop", oracle_text="A.", cmc=3.0)
    _seed_card(conn, "id-5", name="Five Drop", oracle_text="B.", cmc=5.0)
    build_card_embeddings(conn, fake)

    # Query nearest the 5-drop, but restrict to mana 3..4 -> only the 3-drop survives.
    hits = hybrid_search(
        conn,
        _qvec(fake, name="Five Drop", oracle_text="B."),
        mana_value_min=3,
        mana_value_max=4,
    )
    assert {h.card_id for h in hits} == {"id-3"}
    factory.close()


def test_mana_range_floats_floor_min_ceil_max(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "id-4", name="Four Drop", oracle_text="A.", cmc=4.0)
    build_card_embeddings(conn, fake)

    # 3.2 floors to 3, 4.9 ceils to 5 -> the integer mana_value 4 is included.
    hits = hybrid_search(
        conn,
        _qvec(fake, name="Four Drop", oracle_text="A."),
        mana_value_min=3.2,
        mana_value_max=4.9,
    )
    assert {h.card_id for h in hits} == {"id-4"}
    factory.close()


def test_color_mode_all_requires_every_flag(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "id-wu", name="Azorius", oracle_text="WU.", colors=["W", "U"], cmc=2.0)
    _seed_card(conn, "id-w", name="Mono White", oracle_text="W.", colors=["W"], cmc=1.0)
    build_card_embeddings(conn, fake)

    q = _qvec(fake, name="Mono White", oracle_text="W.")
    all_hits = hybrid_search(conn, q, colors=["W", "U"], color_mode="all")
    any_hits = hybrid_search(conn, q, colors=["W", "U"], color_mode="any")

    assert {h.card_id for h in all_hits} == {"id-wu"}  # only the card with BOTH flags
    assert {h.card_id for h in any_hits} == {"id-wu", "id-w"}  # either flag
    factory.close()


# --- JOIN-side post-filter: legality + games ------------------------------------------------


def test_format_legal_excludes_non_legal(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(
        conn,
        "id-std",
        name="Std Card",
        oracle_text="A.",
        cmc=2.0,
        legalities={"standard": "legal", "modern": "legal"},
    )
    _seed_card(
        conn,
        "id-mod",
        name="Mod Card",
        oracle_text="B.",
        cmc=2.0,
        legalities={"modern": "legal"},
    )
    build_card_embeddings(conn, fake)

    # Query nearest the modern-only card, restrict to standard -> only the standard-legal one.
    hits = hybrid_search(
        conn, _qvec(fake, name="Mod Card", oracle_text="B."), format_legal="standard"
    )
    assert {h.card_id for h in hits} == {"id-std"}
    factory.close()


def test_games_filter_excludes_unavailable(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "id-arena", name="Arena Card", oracle_text="A.", cmc=2.0, games=["arena"])
    _seed_card(conn, "id-paper", name="Paper Card", oracle_text="B.", cmc=2.0, games=["paper"])
    build_card_embeddings(conn, fake)

    hits = hybrid_search(conn, _qvec(fake, name="Paper Card", oracle_text="B."), games=["arena"])
    assert {h.card_id for h in hits} == {"id-arena"}
    factory.close()


# --- Over-fetch + oracle de-dup -------------------------------------------------------------


def test_oracle_dedup_keeps_one_hit_per_oracle(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    # Two printings of the SAME card: same oracle_id, identical composite text -> identical vector.
    _seed_card(conn, "print-1", oracle_id="oracle-dragon", name="Dragon", oracle_text="Flies.")
    _seed_card(conn, "print-2", oracle_id="oracle-dragon", name="Dragon", oracle_text="Flies.")
    _seed_card(conn, "other", oracle_id="oracle-other", name="Goblin", oracle_text="Attacks.")
    build_card_embeddings(conn, fake)

    hits = hybrid_search(conn, _qvec(fake, name="Dragon", oracle_text="Flies."), limit=10)

    oracle_ids = [h.oracle_id for h in hits]
    assert oracle_ids.count("oracle-dragon") == 1  # collapsed to a single hit
    dragon = next(h for h in hits if h.oracle_id == "oracle-dragon")
    assert dragon.distance == pytest.approx(0.0, abs=1e-6)  # kept the nearest printing
    factory.close()


def test_over_fetch_k_is_the_first_window_and_a_short_full_one_widens_to_the_cap(
    tmp_path,
) -> None:
    """``over_fetch_k=2`` fills with 2 of 5 cards, short of ``limit``: one retry at the cap."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    for i in range(5):
        _seed_card(conn, f"id-{i}", name=f"Card {i}", oracle_text=f"Text {i}", cmc=float(i))
    build_card_embeddings(conn, fake)

    with _knn_ks(conn) as ks:
        hits = hybrid_search(
            conn, _qvec(fake, name="Card 0", oracle_text="Text 0"), over_fetch_k=2, limit=10
        )

    assert ks == [2, _MAX_OVER_FETCH_K]
    assert len(hits) == 5
    assert hits.cap_reached is False  # the cap query returned 5 rows, not 4,096
    factory.close()


def test_over_fetch_k_above_the_cap_binds_the_cap(tmp_path) -> None:
    """vec0 rejects ``k`` above 4,096, so a larger ``over_fetch_k`` is clamped, not passed on."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "id-0", name="Card 0", oracle_text="Text 0")
    build_card_embeddings(conn, fake)

    with _knn_ks(conn) as ks:
        hits = hybrid_search(
            conn, _qvec(fake, name="Card 0", oracle_text="Text 0"), over_fetch_k=10_000
        )

    assert ks == [_MAX_OVER_FETCH_K]
    assert [h.card_id for h in hits] == ["id-0"]
    factory.close()


def test_limit_caps_unique_results(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    for i in range(5):
        _seed_card(conn, f"id-{i}", name=f"Card {i}", oracle_text=f"Text {i}", cmc=float(i))
    build_card_embeddings(conn, fake)

    hits = hybrid_search(
        conn, _qvec(fake, name="Card 0", oracle_text="Text 0"), over_fetch_k=200, limit=2
    )
    assert len(hits) == 2
    factory.close()


# --- Window widening: a starved filter retries once at the cap ------------------------------


def test_starved_format_filter_widens_once_and_fills_nearest_first(tmp_path) -> None:
    """300 nearer illegal cards push all 10 legal ones past the first 200: the retry finds them."""
    factory = _real_schema_factory(tmp_path)
    conn = factory.get_connection()
    illegal = {f"bad-{r:04d}": r for r in range(1, 301)}
    legal = {f"ok-{r:04d}": r for r in range(301, 311)}
    embedder = seed_ranked_cards(conn, {**illegal, **legal}, standard_legal=legal)
    build_card_embeddings(conn, embedder)

    with _knn_ks(conn) as ks:
        hits = hybrid_search(conn, embedder.query_vector, limit=10, format_legal="standard")

    assert [h.card_id for h in hits] == sorted(legal)  # all ten, nearest (lowest rank) first
    assert ks == [200, _MAX_OVER_FETCH_K]
    assert hits.cap_reached is False
    factory.close()


def test_exhausted_prefilter_runs_one_knn_and_returns_short(tmp_path) -> None:
    """A colour filter leaves 50 vectors (< 200): the KNN ran dry, so no wider window helps."""
    factory = _real_schema_factory(tmp_path)
    conn = factory.get_connection()
    green = {f"g-{r:04d}": r for r in range(1, 51)}
    red = {f"r-{r:04d}": r for r in range(51, 351)}
    legal = {"g-0010", "g-0020", "g-0030"}
    embedder = seed_ranked_cards(
        conn,
        {**green, **red},
        standard_legal=legal,
        colors={**dict.fromkeys(green, ["G"]), **dict.fromkeys(red, ["R"])},
    )
    build_card_embeddings(conn, embedder)

    with _knn_ks(conn) as ks:
        hits = hybrid_search(
            conn, embedder.query_vector, limit=10, colors=["G"], format_legal="standard"
        )

    assert [h.card_id for h in hits] == sorted(legal)
    assert ks == [200]
    assert hits.cap_reached is False
    factory.close()


def test_first_window_that_fills_limit_runs_one_knn(tmp_path) -> None:
    """A format filter the nearest 200 already satisfy: one KNN, exactly as before."""
    factory = _real_schema_factory(tmp_path)
    conn = factory.get_connection()
    ranks = {f"c-{r:04d}": r for r in range(1, 251)}
    legal = set(sorted(ranks)[::2])  # every other card, so 100 of the nearest 200
    embedder = seed_ranked_cards(conn, ranks, standard_legal=legal)
    build_card_embeddings(conn, embedder)

    with _knn_ks(conn) as ks:
        hits = hybrid_search(conn, embedder.query_vector, limit=10, format_legal="standard")

    assert [h.card_id for h in hits] == sorted(legal)[:10]
    assert ks == [200]
    assert hits.cap_reached is False
    factory.close()


def test_orphan_vectors_filling_the_first_window_widen_it(tmp_path) -> None:
    """The nearest 200 vectors' cards were deleted: they still count, so the window widens."""
    factory = _real_schema_factory(tmp_path)
    conn = factory.get_connection()
    ranks = {f"c-{r:04d}": r for r in range(1, 251)}
    embedder = seed_ranked_cards(conn, ranks)
    build_card_embeddings(conn, embedder)
    conn.executemany("DELETE FROM cards WHERE id = ?", [(i,) for i in sorted(ranks)[:200]])
    conn.commit()

    with _knn_ks(conn) as ks:
        hits = hybrid_search(conn, embedder.query_vector, limit=10)

    assert [h.card_id for h in hits] == sorted(ranks)[200:210]
    assert ks == [200, _MAX_OVER_FETCH_K]
    factory.close()


def test_matches_past_the_cap_stop_at_4096_and_report_cap_reached(tmp_path) -> None:
    """4,100 nearer illegal cards: the cap window fills with none legal, so it says so."""
    factory = _real_schema_factory(tmp_path)
    conn = factory.get_connection()
    illegal = {f"bad-{r:04d}": r for r in range(1, 4101)}
    legal = {f"ok-{r:04d}": r for r in range(4101, 4111)}
    embedder = seed_ranked_cards(conn, {**illegal, **legal}, standard_legal=legal)
    build_card_embeddings(conn, embedder)

    with _knn_ks(conn) as ks:
        hits = hybrid_search(conn, embedder.query_vector, limit=10, format_legal="standard")

    assert hits == []
    assert hits.cap_reached is True
    assert ks == [200, _MAX_OVER_FETCH_K]  # one retry, and never a k above the cap
    factory.close()


# --- Empty result ---------------------------------------------------------------------------


def test_no_surviving_match_returns_empty_list(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "id-2", name="Two Drop", oracle_text="A.", cmc=2.0)
    build_card_embeddings(conn, fake)

    # A mana range no card satisfies -> the pre-filter empties the KNN -> [].
    hits = hybrid_search(
        conn,
        _qvec(fake, name="Two Drop", oracle_text="A."),
        mana_value_min=90,
        mana_value_max=99,
    )
    assert hits == []
    factory.close()


def test_null_colors_coerce_to_empty_list(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "id-null", name="Null Colors", oracle_text="A.", colors=None, cmc=2.0)
    build_card_embeddings(conn, fake)

    hits = hybrid_search(conn, _qvec(fake, name="Null Colors", oracle_text="A."))
    assert hits[0].colors == []  # NULL colors JSON -> []
    factory.close()


# --- get_card_vector: point read-back of a stored vector (Story 2.5) ------------------------


def test_get_card_vector_round_trips_to_distance_zero(tmp_path) -> None:
    """The stored vector read back by PK feeds hybrid_search and ranks the seed at distance 0."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "id-r", name="Red Card", oracle_text="Burn.", colors=["R"], cmc=3.0)
    _seed_card(conn, "id-u", name="Blue Card", oracle_text="Draw.", colors=["U"], cmc=2.0)
    build_card_embeddings(conn, fake)

    vec = get_card_vector(conn, "id-r")

    assert vec is not None
    assert vec.dtype == np.float32
    assert vec.shape == (EMBEDDING_DIM,)
    # Read-back fidelity: it equals the exact vector the builder embedded the card under.
    expected = _qvec(fake, name="Red Card", oracle_text="Burn.")
    assert np.array_equal(vec, expected)
    # End-to-end: seeding hybrid_search with the read-back vector returns the seed at distance 0.
    hits = hybrid_search(conn, vec, limit=5)
    assert hits[0].card_id == "id-r"
    assert hits[0].distance == pytest.approx(0.0, abs=1e-6)
    factory.close()


def test_get_card_vector_returns_none_for_unindexed_card(tmp_path) -> None:
    """A card_id with no card_vec row returns None (the AC4 'not indexed' signal)."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "id-r", name="Red Card", oracle_text="Burn.", colors=["R"], cmc=3.0)
    build_card_embeddings(conn, fake)

    assert get_card_vector(conn, "no-such-card") is None
    factory.close()


# --- hybrid_search(exclude_oracle_id=...): drop the whole seed oracle (Story 2.5) -----------


def test_exclude_oracle_id_drops_every_printing_of_that_oracle(tmp_path) -> None:
    """Excluding an oracle removes ALL its printings while still returning `limit` other hits."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    # Two printings of the seed oracle (identical text -> identical, nearest vectors)...
    _seed_card(conn, "seed-a", oracle_id="oracle-seed", name="Seed", oracle_text="Same.")
    _seed_card(conn, "seed-b", oracle_id="oracle-seed", name="Seed", oracle_text="Same.")
    # ...plus two other distinct oracles.
    _seed_card(conn, "other-1", oracle_id="oracle-one", name="One", oracle_text="A.")
    _seed_card(conn, "other-2", oracle_id="oracle-two", name="Two", oracle_text="B.")
    build_card_embeddings(conn, fake)

    seed_vec = get_card_vector(conn, "seed-a")
    assert seed_vec is not None

    excluded = hybrid_search(conn, seed_vec, limit=10, exclude_oracle_id="oracle-seed")
    included = hybrid_search(conn, seed_vec, limit=10)

    # Without exclusion the seed oracle is the nearest hit; with it, no printing survives.
    assert "oracle-seed" in {h.oracle_id for h in included}
    assert all(h.oracle_id != "oracle-seed" for h in excluded)
    assert "seed-a" not in {h.card_id for h in excluded}
    assert "seed-b" not in {h.card_id for h in excluded}
    # The two other oracles still come back (exclusion does not starve the limit).
    assert {h.oracle_id for h in excluded} == {"oracle-one", "oracle-two"}
    factory.close()


def test_exclude_oracle_id_default_none_preserves_behaviour(tmp_path) -> None:
    """Default exclude_oracle_id=None leaves the Story 2.4 path unchanged (nothing dropped)."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "id-r", name="Red Card", oracle_text="Burn.", colors=["R"], cmc=3.0)
    _seed_card(conn, "id-u", name="Blue Card", oracle_text="Draw.", colors=["U"], cmc=2.0)
    build_card_embeddings(conn, fake)

    q = _qvec(fake, name="Red Card", oracle_text="Burn.")
    assert {h.card_id for h in hybrid_search(conn, q)} == {
        h.card_id for h in hybrid_search(conn, q, exclude_oracle_id=None)
    }
    factory.close()
