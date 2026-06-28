"""Helper-level tests for ``find_similar_cards`` (``src/mcp_server/tools/find_similar.py``).

Drive the sync helper directly — ``find_similar_cards(conn, card_name=…, …)`` — against a
``tmp_path`` ``card_vec`` populated through the **real** sqlite-vec extension but a **fake one-hot
embedder** (no model download), mirroring ``test_semantic_search_tool.py`` / ``test_query.py``.

Find-similar **never embeds**: it resolves a seed in raw SQL on ``cards``, reads that seed's stored
vector back (``get_card_vector``), and seeds ``hybrid_search`` with the seed's own oracle excluded.
With one-hot vectors every distinct card is orthonormal — the seed sits at distance 0 and all other
cards tie — so assertions are on **oracle absence / membership**, never a specific runner-up.

The local ``_make_factory`` adds a ``printed_name`` column (set ``None`` on every card) because the
seed resolver matches ``name`` OR ``printed_name``; everything else mirrors the shared shape.
Covers: ok (nearest *other* card, seed oracle absent), self-exclusion across duplicate printings,
filter composition, not_found (unknown / unindexed), ambiguous, and the invalid contract.
"""

import json
import sqlite3

from src.mcp_server.tools.find_similar import SimilarCardsResult, find_similar_cards
from src.search import ConnectionFactory, build_card_embeddings, create_card_vec_table
from tests.fixtures.embedder import FakeEmbedder


def _make_factory(tmp_path) -> ConnectionFactory:
    """ConnectionFactory on a tmp DB with a ``cards`` table; includes ``printed_name`` (the seed
    resolver matches ``name`` OR ``printed_name``) plus the builder-read + JOIN/display columns."""
    factory = ConnectionFactory(db_path=str(tmp_path / "cards.db"))
    conn = factory.get_connection()
    conn.execute(
        "CREATE TABLE cards ("
        "id TEXT PRIMARY KEY, oracle_id TEXT NOT NULL, name TEXT NOT NULL, printed_name TEXT, "
        "type_line TEXT, mana_cost TEXT, oracle_text TEXT, keywords TEXT, colors TEXT, cmc REAL, "
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
    printed_name: str | None = None,
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
        "INSERT INTO cards (id, oracle_id, name, printed_name, type_line, mana_cost, oracle_text, "
        "keywords, colors, cmc, rarity, set_code, legalities, games) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            card_id,
            oracle_id if oracle_id is not None else f"oracle-{card_id}",
            name,
            printed_name,
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


# --- status="ok": nearest *other* card, seed's whole oracle excluded ------------------------


def test_ok_returns_alternatives_with_seed_oracle_excluded(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "seed", name="Seed Dragon", oracle_text="Fly.", colors=["R"], cmc=5.0)
    _seed_card(conn, "alt-1", name="Alt One", oracle_text="A.", colors=["R"], cmc=4.0)
    _seed_card(conn, "alt-2", name="Alt Two", oracle_text="B.", colors=["R"], cmc=3.0)
    build_card_embeddings(conn, fake)

    result = find_similar_cards(conn, card_name="Seed Dragon", limit=10)

    assert isinstance(result, SimilarCardsResult)
    assert result.status == "ok"
    assert result.total_count == len(result.cards)
    assert result.total_count > 0
    assert result.seed is not None
    assert result.seed.name == "Seed Dragon"
    # The seed (its own printing) is absent — these are alternatives.
    result_ids = {hit.card.id for hit in result.cards}
    assert "seed" not in result_ids
    assert {"alt-1", "alt-2"} <= result_ids
    # Hits carry a distance and the lightweight projection (no heavy detail fields).
    assert all(isinstance(hit.distance, float) for hit in result.cards)
    dumped = result.cards[0].card.model_dump()
    assert "legalities" not in dumped and "image_uris" not in dumped
    factory.close()


def test_ok_resolves_seed_by_card_id(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "seed", name="Seed Dragon", oracle_text="Fly.", colors=["R"], cmc=5.0)
    _seed_card(conn, "alt-1", name="Alt One", oracle_text="A.", colors=["R"], cmc=4.0)
    build_card_embeddings(conn, fake)

    result = find_similar_cards(conn, card_id="seed")

    assert result.status == "ok"
    assert result.seed is not None and result.seed.id == "seed"
    assert "seed" not in {hit.card.id for hit in result.cards}
    assert "alt-1" in {hit.card.id for hit in result.cards}
    factory.close()


def test_self_exclusion_drops_every_printing_of_the_seed_oracle(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    # Two printings of ONE oracle (identical text -> identical, nearest vectors).
    _seed_card(conn, "seed-a", oracle_id="oracle-twin", name="Twin Card", oracle_text="Same.")
    _seed_card(conn, "seed-b", oracle_id="oracle-twin", name="Twin Card", oracle_text="Same.")
    _seed_card(conn, "other-1", oracle_id="oracle-one", name="One", oracle_text="A.")
    _seed_card(conn, "other-2", oracle_id="oracle-two", name="Two", oracle_text="B.")
    build_card_embeddings(conn, fake)

    result = find_similar_cards(conn, card_name="Twin Card", limit=10)

    assert result.status == "ok"
    result_ids = {hit.card.id for hit in result.cards}
    # BOTH printings of the seed oracle are gone, not just the resolved one.
    assert "seed-a" not in result_ids
    assert "seed-b" not in result_ids
    assert {"other-1", "other-2"} <= result_ids
    factory.close()


# --- status="ok"/"empty" with composed relational filters -----------------------------------


def test_filters_compose_with_similarity(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(
        conn,
        "seed",
        name="Seed Red",
        oracle_text="Z.",
        colors=["R"],
        cmc=3.0,
        legalities={"standard": "legal"},
    )
    _seed_card(
        conn,
        "std",
        name="Ally Std",
        oracle_text="A.",
        colors=["R"],
        cmc=3.0,
        legalities={"standard": "legal"},
        games=["arena"],
    )
    _seed_card(
        conn,
        "mod",
        name="Ally Mod",
        oracle_text="B.",
        colors=["R"],
        cmc=4.0,
        legalities={"modern": "legal"},
        games=["arena"],  # NOT standard-legal
    )
    _seed_card(
        conn,
        "blue",
        name="Ally Blue",
        oracle_text="C.",
        colors=["U"],
        cmc=3.0,
        legalities={"standard": "legal"},
        games=["paper"],
    )
    build_card_embeddings(conn, fake)

    # format filter (JOIN post-filter): the modern-only card drops out.
    fmt = find_similar_cards(conn, card_name="Seed Red", format="standard")
    assert fmt.status == "ok"
    assert "mod" not in {h.card.id for h in fmt.cards}
    assert "std" in {h.card.id for h in fmt.cards}

    # color pre-filter: only red alternatives survive (blue excluded, seed excluded).
    red = find_similar_cards(conn, card_name="Seed Red", colors=["R"])
    assert red.status == "ok"
    assert {h.card.id for h in red.cards} == {"std", "mod"}

    # mana pre-filter: restrict to mana 4..4 -> only the 4-drop alternative.
    mana = find_similar_cards(conn, card_name="Seed Red", mana_value_min=4, mana_value_max=4)
    assert mana.status == "ok"
    assert {h.card.id for h in mana.cards} == {"mod"}

    # games post-filter: only paper -> the blue paper card.
    paper = find_similar_cards(conn, card_name="Seed Red", games=["paper"])
    assert paper.status == "ok"
    assert {h.card.id for h in paper.cards} == {"blue"}
    factory.close()


def test_empty_when_filters_exclude_all_alternatives(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "seed", name="Seed Red", oracle_text="Z.", colors=["R"], cmc=3.0)
    _seed_card(conn, "alt", name="Alt Red", oracle_text="A.", colors=["R"], cmc=3.0)
    build_card_embeddings(conn, fake)

    # No seeded card is green -> every alternative is filtered out.
    result = find_similar_cards(conn, card_name="Seed Red", colors=["G"])

    assert result.status == "empty"
    assert result.cards == []
    assert result.total_count == 0
    assert result.seed is not None and result.seed.name == "Seed Red"  # seed echoed back
    assert result.message
    factory.close()


# --- status="not_found": unknown name, and present-but-unindexed ----------------------------


def test_not_found_for_unknown_name(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "seed", name="Seed Card", oracle_text="A.")
    build_card_embeddings(conn, fake)

    result = find_similar_cards(conn, card_name="Nonexistent Planeswalker")

    assert result.status == "not_found"
    assert result.cards == []
    assert result.seed is None
    assert result.message
    factory.close()


def test_not_found_for_card_present_but_not_indexed(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "indexed", name="Indexed Card", oracle_text="A.")
    build_card_embeddings(conn, fake)
    # Insert AFTER the build -> the card exists in `cards` but has NO card_vec row.
    _seed_card(conn, "ghost", name="Ghost Card", oracle_text="B.")

    result = find_similar_cards(conn, card_name="Ghost Card")

    assert result.status == "not_found"
    assert result.cards == []
    assert result.seed is not None  # seed was found in cards; only the vector is missing
    assert result.seed.name == "Ghost Card"
    assert "index" in result.message.lower()  # "isn't in the semantic index yet"
    factory.close()


def test_not_found_for_unknown_card_id(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "seed", name="Seed Card", oracle_text="A.")
    build_card_embeddings(conn, fake)

    result = find_similar_cards(conn, card_id="no-such-id")

    assert result.status == "not_found"
    assert result.seed is None
    factory.close()


# --- status="ambiguous": a name substring matching multiple distinct oracles ----------------


def test_ambiguous_returns_distinct_oracle_matches(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "g1", oracle_id="oracle-raider", name="Goblin Raider", oracle_text="A.")
    _seed_card(conn, "g2", oracle_id="oracle-chief", name="Goblin Chief", oracle_text="B.")
    build_card_embeddings(conn, fake)

    # "Goblin" matches neither exactly but is a substring of both distinct oracles.
    result = find_similar_cards(conn, card_name="Goblin")

    assert result.status == "ambiguous"
    assert result.cards == []
    assert result.seed is None
    match_names = {m.name for m in result.matches}
    assert {"Goblin Raider", "Goblin Chief"} <= match_names
    assert result.message
    factory.close()


# --- status="invalid": graceful, never raises -----------------------------------------------


def test_invalid_requires_exactly_one_identifier(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "seed", name="Seed Card", oracle_text="A.")
    build_card_embeddings(conn, fake)

    neither = find_similar_cards(conn)
    assert neither.status == "invalid"
    assert neither.message

    both = find_similar_cards(conn, card_name="Seed Card", card_id="seed")
    assert both.status == "invalid"
    assert both.message
    factory.close()


def test_invalid_bad_filter_values(tmp_path) -> None:
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    fake = FakeEmbedder()
    _seed_card(conn, "seed", name="Seed Card", oracle_text="A.")
    build_card_embeddings(conn, fake)

    bad_color = find_similar_cards(conn, card_name="Seed Card", colors=["X"])
    assert bad_color.status == "invalid" and "X" in bad_color.message

    bad_game = find_similar_cards(conn, card_name="Seed Card", games=["xbox"])
    assert bad_game.status == "invalid" and "xbox" in bad_game.message

    bad_range = find_similar_cards(conn, card_name="Seed Card", mana_value_min=5, mana_value_max=2)
    assert bad_range.status == "invalid"

    bad_limit = find_similar_cards(conn, card_name="Seed Card", limit=0)
    assert bad_limit.status == "invalid"

    # G2: limit above the 50 ceiling is rejected (keeps it under hybrid_search's over_fetch_k).
    high_limit = find_similar_cards(conn, card_name="Seed Card", limit=51)
    assert high_limit.status == "invalid" and "50" in high_limit.message
    factory.close()


# --- status="index_unavailable": G3 graceful "index not built" guard ------------------------


def test_index_unavailable_when_card_vec_missing(tmp_path) -> None:
    """No ``card_vec`` table: the seed resolves on ``cards`` but the vector read would raise — so
    the up-front guard returns a build-the-index hint instead of an OperationalError."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    _seed_card(conn, "seed", name="Seed Card", oracle_text="A.")
    # NB: build_card_embeddings is deliberately NOT called, so ``card_vec`` never exists.

    result = find_similar_cards(conn, card_name="Seed Card")
    assert result.status == "index_unavailable"
    assert result.cards == []
    assert "build_search_index" in result.message
    factory.close()


def test_index_unavailable_when_card_vec_empty(tmp_path) -> None:
    """An existing-but-empty ``card_vec`` is index_unavailable, distinct from a resolved seed."""
    factory = _make_factory(tmp_path)
    conn = factory.get_connection()
    _seed_card(
        conn, "seed", name="Anything"
    )  # cards present, so the DB-not-initialized guard passes
    create_card_vec_table(conn)  # table exists, zero vectors

    result = find_similar_cards(conn, card_name="Anything")
    assert result.status == "index_unavailable"
    factory.close()
