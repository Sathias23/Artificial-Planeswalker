"""Unit tests for the hybrid query infra (``src/search/query.py::hybrid_search``).

Drive ``hybrid_search`` directly on a ``tmp_path`` ``card_vec`` populated through the **real**
bundled sqlite-vec extension (via ``ConnectionFactory``) but with a **fake one-hot embedder** —
no model download, no network — so these are fast unit tests (not ``@pytest.mark.integration``),
mirroring ``test_schema.py`` / ``test_index_builder.py``. Covers: mandatory ``k`` / over-fetch
bounding, the ``mana_value`` + colour metadata pre-filter, the JOIN-side legality/games
post-filter, oracle-id de-dup across duplicate printings, ``limit`` capping, and the empty result.
"""

import json
import sqlite3

import numpy as np
import pytest
from numpy.typing import NDArray

from src.search import ConnectionFactory, build_card_embeddings, compose_card_text
from src.search.embedder import EMBEDDING_DIM
from src.search.query import CardHit, get_card_vector, hybrid_search


class _FakeEmbedder:
    """Deterministic offline embedder: each distinct composite text -> a distinct one-hot vector.

    Identical text yields the identical vector (distance 0 to itself and to a duplicate printing
    with the same text), so KNN nearest-neighbour assertions are exact without loading the model.
    """

    def __init__(self) -> None:
        self.dim = EMBEDDING_DIM
        self._assigned: dict[str, int] = {}

    def _vector_for(self, text: str) -> NDArray[np.float32]:
        if text not in self._assigned:
            self._assigned[text] = len(self._assigned) % EMBEDDING_DIM
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        vec[self._assigned[text]] = 1.0
        return vec

    def encode(self, text: str) -> NDArray[np.float32]:
        return self._vector_for(text)

    def encode_batch(self, texts: list[str]) -> list[NDArray[np.float32]]:
        return [self._vector_for(t) for t in texts]


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
    fake: _FakeEmbedder,
    *,
    name: str,
    type_line: str = "Creature — Test",
    mana_cost: str = "{1}",
    oracle_text: str = "Does a thing.",
    keywords: list[str] | None = None,
) -> NDArray[np.float32]:
    """The exact vector a seeded card embeds to (same compose recipe the builder used)."""
    return fake.encode(compose_card_text(name, type_line, mana_cost, oracle_text, keywords or []))


# --- Plain query: nearest-first, every CardHit field populated ------------------------------


def test_returns_card_hits_nearest_first(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
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
    fake = _FakeEmbedder()
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
    fake = _FakeEmbedder()
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
    fake = _FakeEmbedder()
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
    fake = _FakeEmbedder()
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
    fake = _FakeEmbedder()
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
    fake = _FakeEmbedder()
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
    fake = _FakeEmbedder()
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


def test_over_fetch_k_bounds_candidate_pool(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    for i in range(5):
        _seed_card(conn, f"id-{i}", name=f"Card {i}", oracle_text=f"Text {i}", cmc=float(i))
    build_card_embeddings(conn, fake)

    # k=2 means the KNN returns at most 2 candidates regardless of the higher limit.
    hits = hybrid_search(
        conn, _qvec(fake, name="Card 0", oracle_text="Text 0"), over_fetch_k=2, limit=10
    )
    assert len(hits) <= 2
    factory.close()


def test_limit_caps_unique_results(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    for i in range(5):
        _seed_card(conn, f"id-{i}", name=f"Card {i}", oracle_text=f"Text {i}", cmc=float(i))
    build_card_embeddings(conn, fake)

    hits = hybrid_search(
        conn, _qvec(fake, name="Card 0", oracle_text="Text 0"), over_fetch_k=200, limit=2
    )
    assert len(hits) == 2
    factory.close()


# --- Empty result ---------------------------------------------------------------------------


def test_no_surviving_match_returns_empty_list(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
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
    fake = _FakeEmbedder()
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
    fake = _FakeEmbedder()
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
    fake = _FakeEmbedder()
    _seed_card(conn, "id-r", name="Red Card", oracle_text="Burn.", colors=["R"], cmc=3.0)
    build_card_embeddings(conn, fake)

    assert get_card_vector(conn, "no-such-card") is None
    factory.close()


# --- hybrid_search(exclude_oracle_id=...): drop the whole seed oracle (Story 2.5) -----------


def test_exclude_oracle_id_drops_every_printing_of_that_oracle(tmp_path) -> None:
    """Excluding an oracle removes ALL its printings while still returning `limit` other hits."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
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
    fake = _FakeEmbedder()
    _seed_card(conn, "id-r", name="Red Card", oracle_text="Burn.", colors=["R"], cmc=3.0)
    _seed_card(conn, "id-u", name="Blue Card", oracle_text="Draw.", colors=["U"], cmc=2.0)
    build_card_embeddings(conn, fake)

    q = _qvec(fake, name="Red Card", oracle_text="Burn.")
    assert {h.card_id for h in hybrid_search(conn, q)} == {
        h.card_id for h in hybrid_search(conn, q, exclude_oracle_id=None)
    }
    factory.close()
