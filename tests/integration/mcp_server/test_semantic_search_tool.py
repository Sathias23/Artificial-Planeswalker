"""Helper-level tests for ``semantic_search_cards`` (``src/mcp_server/tools/semantic_search.py``).

Drive the sync helper directly — ``semantic_search_cards(conn, fake_embedder, query, …)`` — against
a ``tmp_path`` ``card_vec`` populated through the **real** sqlite-vec extension but a **fake one-hot
embedder** (no model download), so the fast path is offline. The fake maps each distinct composite
text to a distinct one-hot vector, so querying with a card's exact composed text ranks that card at
distance 0 — the offline analogue of semantic similarity. Covers the ok / empty / invalid contract,
filter composition, the lightweight ``CardSummary`` projection, and the per-hit distance.
One ``@pytest.mark.integration`` test drives the **real** embedder for honest semantic ranking.
"""

import json
import sqlite3

import numpy as np
import pytest
from numpy.typing import NDArray

from src.mcp_server.tools.semantic_search import SemanticSearchResult, semantic_search_cards
from src.search import ConnectionFactory, build_card_embeddings, compose_card_text, get_embedder
from src.search.embedder import EMBEDDING_DIM, reset_embedder


class _FakeEmbedder:
    """Deterministic offline embedder: each distinct text -> a distinct one-hot ``float32`` vector.

    Implements both ``encode`` (the query path) and ``encode_batch`` (the index-build path) over the
    same per-instance assignment, so a query whose text equals a card's composed text embeds to that
    card's exact vector (distance 0).
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


def _query_text(
    name: str,
    *,
    type_line: str = "Creature — Test",
    mana_cost: str = "{1}",
    oracle_text: str = "Does a thing.",
    keywords: list[str] | None = None,
) -> str:
    """The composed text a seeded card embeds to — pass as the query to rank that card first."""
    return compose_card_text(name, type_line, mana_cost, oracle_text, keywords or [])


# --- status="ok": ranked hits, distance carried, lightweight projection ---------------------


def test_ok_returns_ranked_hits_with_distance(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    _seed_card(conn, "id-r", name="Red Card", oracle_text="Burn.", colors=["R"], cmc=3.0)
    _seed_card(conn, "id-u", name="Blue Card", oracle_text="Draw.", colors=["U"], cmc=2.0)
    build_card_embeddings(conn, fake)

    result = semantic_search_cards(
        conn, fake, _query_text("Red Card", oracle_text="Burn."), limit=5
    )

    assert isinstance(result, SemanticSearchResult)
    assert result.status == "ok"
    assert result.total_count == len(result.cards)
    assert result.cards[0].card.name == "Red Card"
    assert result.cards[0].distance == pytest.approx(0.0, abs=1e-6)
    # Lightweight CardSummary projection: heavy detail fields are not present.
    dumped = result.cards[0].card.model_dump()
    assert "legalities" not in dumped
    assert "image_uris" not in dumped
    assert "card_faces" not in dumped
    factory.close()


def test_ok_filters_compose_color_mana_format_games(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    # A standard-legal arena red 3-drop, and an off-filter blue card.
    _seed_card(
        conn,
        "id-r",
        name="Red Card",
        oracle_text="Burn.",
        colors=["R"],
        cmc=3.0,
        legalities={"standard": "legal"},
        games=["arena", "paper"],
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

    # Query nearest the blue card, but the composed hybrid filter narrows to the red 3-drop.
    result = semantic_search_cards(
        conn,
        fake,
        _query_text("Blue Card", oracle_text="Draw."),
        colors=["R"],
        mana_value_min=3,
        mana_value_max=4,
        format="standard",
        games=["arena"],
    )
    assert result.status == "ok"
    assert {hit.card.name for hit in result.cards} == {"Red Card"}
    factory.close()


# --- status="empty": valid query/filters, nothing survives ----------------------------------


def test_empty_when_filters_exclude_all(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    _seed_card(conn, "id-r", name="Red Card", oracle_text="Burn.", colors=["R"], cmc=3.0)
    build_card_embeddings(conn, fake)

    result = semantic_search_cards(
        conn, fake, _query_text("Red Card", oracle_text="Burn."), colors=["G"]
    )
    assert result.status == "empty"
    assert result.cards == []
    assert result.total_count == 0
    assert result.message
    factory.close()


# --- status="invalid": graceful, never raises -----------------------------------------------


def test_invalid_empty_query_does_not_call_encode(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    _seed_card(conn, "id-r", name="Red Card", oracle_text="Burn.", colors=["R"], cmc=3.0)
    build_card_embeddings(conn, fake)

    for bad_query in ("", "   "):
        result = semantic_search_cards(conn, fake, bad_query)
        assert result.status == "invalid"
        assert result.cards == []
        assert "query" in result.message.lower()
    factory.close()


def test_invalid_bad_filter_values(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = _FakeEmbedder()
    _seed_card(conn, "id-r", name="Red Card", oracle_text="Burn.", colors=["R"], cmc=3.0)
    build_card_embeddings(conn, fake)
    q = _query_text("Red Card", oracle_text="Burn.")

    bad_color = semantic_search_cards(conn, fake, q, colors=["X"])
    assert bad_color.status == "invalid" and "X" in bad_color.message

    bad_game = semantic_search_cards(conn, fake, q, games=["xbox"])
    assert bad_game.status == "invalid" and "xbox" in bad_game.message

    bad_range = semantic_search_cards(conn, fake, q, mana_value_min=5, mana_value_max=2)
    assert bad_range.status == "invalid"

    bad_limit = semantic_search_cards(conn, fake, q, limit=0)
    assert bad_limit.status == "invalid"
    factory.close()


def test_empty_format_normalized_to_no_filter(tmp_path) -> None:
    """A whitespace ``format`` must not fire a malformed json_extract path — treated as None."""
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
        legalities={"modern": "legal"},  # NOT standard-legal: a real format filter would exclude it
    )
    build_card_embeddings(conn, fake)

    result = semantic_search_cards(
        conn, fake, _query_text("Red Card", oracle_text="Burn."), format="   "
    )
    assert result.status == "ok"  # blank format ignored -> the (non-standard) card still returns
    assert {hit.card.name for hit in result.cards} == {"Red Card"}
    factory.close()


# --- Optional: real fastembed semantic ranking ----------------------------------------------


@pytest.mark.integration
def test_real_embedder_ranks_relevant_card_first(tmp_path) -> None:
    """Integration: the real model ranks a flying red dragon first for a natural-language query."""
    reset_embedder()
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    _seed_card(
        conn,
        "id-dragon",
        name="Inferno Dragon",
        type_line="Creature — Dragon",
        mana_cost="{3}{R}{R}",
        oracle_text="Flying. When this attacks, it deals 3 damage to any target.",
        keywords=["Flying"],
        colors=["R"],
        cmc=5.0,
    )
    _seed_card(
        conn,
        "id-counter",
        name="Dissolve",
        type_line="Instant",
        mana_cost="{U}{U}",
        oracle_text="Counter target spell.",
        colors=["U"],
        cmc=2.0,
    )
    _seed_card(
        conn,
        "id-elf",
        name="Verdant Elf",
        type_line="Creature — Elf Druid",
        mana_cost="{G}",
        oracle_text="{T}: Add {G}.",
        colors=["G"],
        cmc=1.0,
    )

    embedder = get_embedder()
    build_card_embeddings(conn, embedder)

    result = semantic_search_cards(conn, embedder, "flying red dragon that deals damage", limit=3)

    assert result.status == "ok"
    assert result.cards[0].card.name == "Inferno Dragon"  # honest semantic ranking
    factory.close()
    reset_embedder()
