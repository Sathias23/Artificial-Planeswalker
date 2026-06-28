"""NFR9 RAG sanity eval: real quantized embedder + production hybrid path + top-K hit-rate guard.

The capstone quality guard for Epic 2 (Story 2.6). It builds a curated MTG card corpus with the
**real** quantized embedder (``bge-small-en-v1.5-onnx-q``) via the production
:func:`~src.search.index_builder.build_card_embeddings`, then runs a fixture of **natural-language**
queries (never a card's name or its ``compose_card_text`` output) through the production
:func:`~src.mcp_server.tools.semantic_search.semantic_search_cards` -> ``hybrid_search`` path, and
asserts the **aggregate top-K hit-rate** against a single tunable :data:`TARGET_HIT_RATE`, naming
every miss so a failure is actionable.

This generalizes the one-query precursor
``test_real_embedder_ranks_relevant_card_first`` into a multi-query, threshold-guarded recall eval.
It loads the ~80 MB model (cached in the central data dir, see ``src.paths``), so it is
``@pytest.mark.integration`` — **part of the active suite** under ``tests/`` (the ``-m "not
integration"`` filter merely scopes the fast offline subset, it does not exclude this from the
active suite). The pure hit-rate helpers are unit-tested offline below.
"""

import json
import sqlite3

import pytest

from src.mcp_server.tools.semantic_search import semantic_search_cards
from src.search import ConnectionFactory, build_card_embeddings, get_embedder
from src.search.embedder import reset_embedder

# --- The single tunable knob (AC3) ----------------------------------------------------------
# Calibrated in Task 0 against the real quantized model on this exact fixture: observed 12/12 = 1.0
# (10 of 12 expected cards rank #1; Sol Ring and Llanowar Elves rank #3 -- both comfortably inside
# top-5). The target sits a notch below the observed 1.0 so one quantization-borderline miss
# (11/12 = 0.917) stays green, while a genuine recall regression (>= 2 misses, <= 10/12 = 0.833)
# trips the assert. The lever for a real miss is the composite-text weighting -- tuned in a
# follow-up (spec section 6/169), not silently in this story.
TARGET_HIT_RATE = 0.9

#: Default top-K per case -- small, so "expected card appears in top-K" is a real signal over a
#: ~20-card corpus (with top-5 covering only a quarter of the pool).
DEFAULT_K = 5

# --- Task 1: curated corpus -----------------------------------------------------------------
# ~20 distinctive cards across clearly-separated archetypes, with real, well-known oracle text so
# the honest embedder ranks on genuine meaning. Deliberate near-duplicates (Shock vs Lightning
# Bolt, Negate vs Counterspell) and shared flyers (Air Elemental vs Serra Angel / Skyfire Dragon)
# force real discrimination rather than a trivially-separable pool.
# Each tuple: (card_id, name, type_line, mana_cost, oracle_text, colors, cmc, keywords).
_CORPUS: list[tuple[str, str, str, str, str, list[str], float, list[str]]] = [
    (
        "c01",
        "Lightning Bolt",
        "Instant",
        "{R}",
        "Lightning Bolt deals 3 damage to any target.",
        ["R"],
        1.0,
        [],
    ),
    ("c02", "Shock", "Instant", "{R}", "Shock deals 2 damage to any target.", ["R"], 1.0, []),
    ("c03", "Counterspell", "Instant", "{U}{U}", "Counter target spell.", ["U"], 2.0, []),
    ("c04", "Negate", "Instant", "{1}{U}", "Counter target noncreature spell.", ["U"], 2.0, []),
    ("c05", "Llanowar Elves", "Creature — Elf Druid", "{G}", "{T}: Add {G}.", ["G"], 1.0, []),
    (
        "c06",
        "Birds of Paradise",
        "Creature — Bird",
        "{G}",
        "Flying\n{T}: Add one mana of any color.",
        ["G"],
        1.0,
        ["Flying"],
    ),
    (
        "c07",
        "Wrath of God",
        "Sorcery",
        "{2}{W}{W}",
        "Destroy all creatures. They can't be regenerated.",
        ["W"],
        4.0,
        [],
    ),
    ("c08", "Murder", "Instant", "{1}{B}{B}", "Destroy target creature.", ["B"], 3.0, []),
    (
        "c09",
        "Serra Angel",
        "Creature — Angel",
        "{3}{W}{W}",
        "Flying, vigilance",
        ["W"],
        5.0,
        ["Flying", "Vigilance"],
    ),
    (
        "c10",
        "Skyfire Dragon",
        "Creature — Dragon",
        "{3}{R}{R}",
        "Flying\nWhenever Skyfire Dragon attacks, it deals 4 damage to any target.",
        ["R"],
        5.0,
        ["Flying"],
    ),
    (
        "c11",
        "Giant Growth",
        "Instant",
        "{G}",
        "Target creature gets +3/+3 until end of turn.",
        ["G"],
        1.0,
        [],
    ),
    ("c12", "Divination", "Sorcery", "{2}{U}", "Draw two cards.", ["U"], 3.0, []),
    ("c13", "Sol Ring", "Artifact", "{1}", "{T}: Add {C}{C}.", [], 1.0, []),
    ("c14", "Healing Salve", "Instant", "{W}", "You gain 3 life.", ["W"], 1.0, []),
    (
        "c15",
        "Mind Sculpt",
        "Sorcery",
        "{1}{U}",
        "Target player puts the top seven cards of their library into their graveyard.",
        ["U"],
        2.0,
        [],
    ),
    (
        "c16",
        "Muster the Troops",
        "Sorcery",
        "{1}{W}{W}",
        "Create three 1/1 white Soldier creature tokens.",
        ["W"],
        3.0,
        [],
    ),
    (
        "c17",
        "Raise Dead",
        "Sorcery",
        "{B}",
        "Return target creature card from your graveyard to your hand.",
        ["B"],
        1.0,
        [],
    ),
    (
        "c18",
        "Pacifism",
        "Enchantment — Aura",
        "{1}{W}",
        "Enchant creature\nEnchanted creature can't attack or block.",
        ["W"],
        2.0,
        [],
    ),
    (
        "c19",
        "Rampant Growth",
        "Sorcery",
        "{1}{G}",
        "Search your library for a basic land card and put it onto the battlefield tapped.",
        ["G"],
        2.0,
        [],
    ),
    ("c20", "Air Elemental", "Creature — Elemental", "{3}{U}{U}", "Flying", ["U"], 5.0, ["Flying"]),
]

# --- Task 1: query fixture ------------------------------------------------------------------
# (natural_language_query, expected_card_name, k). Each query DESCRIBES an effect as a player would
# ask -- it never names the card and is never a card's compose_card_text output -- so the eval
# measures genuine meaning -> card retrieval. The expected card is the unambiguous best match within
# the corpus. Discriminating pairs: green-mana dork (Llanowar adds G) vs any-color dork (Birds);
# 3-damage burn (Bolt) amid 2-damage burn (Shock); "counter target spell" (Counterspell) vs Negate.
_QUERY_FIXTURE: list[tuple[str, str, int]] = [
    ("deal three damage to any target for one red mana", "Lightning Bolt", DEFAULT_K),
    ("counter target spell", "Counterspell", DEFAULT_K),
    ("a one-mana green creature that taps to add G", "Llanowar Elves", DEFAULT_K),
    ("destroy all creatures on the battlefield", "Wrath of God", DEFAULT_K),
    ("flying red dragon that deals damage when it attacks", "Skyfire Dragon", DEFAULT_K),
    ("destroy a single target creature", "Murder", DEFAULT_K),
    ("draw cards", "Divination", DEFAULT_K),
    ("tap a creature for mana of any color", "Birds of Paradise", DEFAULT_K),
    ("give a creature +3/+3 until end of turn", "Giant Growth", DEFAULT_K),
    ("cheap artifact that makes colorless mana", "Sol Ring", DEFAULT_K),
    ("a flying angel", "Serra Angel", DEFAULT_K),
    ("make a bunch of small creature tokens", "Muster the Troops", DEFAULT_K),
]

#: One evaluated case: ``(query, expected_card_name, ranked_top_k_names)``.
CaseResult = tuple[str, str, list[str]]


# --- Pure hit-rate logic (no model) -- shared by the eval and the offline unit guard (Task 3) -


def evaluate_hit_rate(case_results: list[CaseResult]) -> tuple[float, list[CaseResult]]:
    """Compute the aggregate top-K hit-rate and collect the misses.

    A pure function (no model, no DB) so the assert-and-name logic is unit-testable offline.

    Args:
        case_results: One ``(query, expected_card_name, ranked_top_k_names)`` per query.

    Returns:
        ``(hit_rate, misses)`` where ``hit_rate`` is hits / total (``0.0`` for an empty input) and
        ``misses`` is the subset whose expected card is absent from its top-K.
    """
    if not case_results:
        return 0.0, []
    misses = [case for case in case_results if case[1] not in case[2]]
    hit_rate = (len(case_results) - len(misses)) / len(case_results)
    return hit_rate, misses


def format_failure(hit_rate: float, misses: list[CaseResult]) -> str:
    """Build the actionable assertion message naming every miss and what ranked instead (AC3).

    Args:
        hit_rate: The observed aggregate hit-rate.
        misses: The cases whose expected card fell outside top-K.

    Returns:
        A multi-line message: the rate vs target, every missed query + its expected card + the
        names that ranked in its place, and the composite-text-weighting tuning lever.
    """
    lines = [
        f"RAG top-K hit-rate {hit_rate:.3f} < target {TARGET_HIT_RATE:.3f} "
        f"({len(misses)} miss(es)):"
    ]
    for query, expected, ranked in misses:
        ranked_str = ", ".join(ranked) if ranked else "(no hits)"
        lines.append(
            f"  - query={query!r}: expected {expected!r} NOT in top-K; ranked instead: {ranked_str}"
        )
    lines.append(
        "Lever (follow-up, not this story): tune the composite-text weighting "
        "(name + type_line + mana_cost + oracle_text + keywords)."
    )
    return "\n".join(lines)


def _seed_card(
    conn: sqlite3.Connection,
    card_id: str,
    *,
    name: str,
    type_line: str,
    mana_cost: str,
    oracle_text: str,
    colors: list[str],
    cmc: float,
    keywords: list[str],
) -> None:
    """Insert one corpus card into the raw-SQL ``cards`` table (the ``_make_factory`` shape).

    ``keywords``/``colors``/``legalities``/``games`` are JSON-text columns; ``[]`` (not ``None``)
    is used for "no keywords/colors" because the frozen builder's ``_coerce_json_list`` turns a
    JSON ``null`` into ``None`` -> ``TypeError`` (the Story 2.4 fixture gotcha). Every card is
    seeded standard-legal on paper+arena so a stray legality/games default never silently filters
    the corpus.
    """
    conn.execute(
        "INSERT INTO cards (id, oracle_id, name, type_line, mana_cost, oracle_text, keywords, "
        "colors, cmc, rarity, set_code, legalities, games) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            card_id,
            f"oracle-{card_id}",
            name,
            type_line,
            mana_cost,
            oracle_text,
            json.dumps(keywords),
            json.dumps(colors),
            cmc,
            "common",
            "TST",
            json.dumps({"standard": "legal"}),
            json.dumps(["paper", "arena"]),
        ),
    )


@pytest.fixture(scope="module")
def rag_eval_index(tmp_path_factory):
    """Build the curated corpus once with the real quantized model (module scope -> one load).

    Uses ``tmp_path_factory`` (not the function-scoped ``tmp_path``) for module scope: ``reset`` the
    embedder singleton, open a hermetic ``tmp_path`` DB via the production ``ConnectionFactory``,
    create + seed the raw-SQL ``cards`` table, then populate ``card_vec`` with the production
    ``build_card_embeddings(conn, get_embedder())`` -- the exact build recipe production uses.
    Yields ``(connection_factory, embedder)``; teardown closes the connection and resets the
    singleton so no real model leaks into another test.
    """
    reset_embedder()
    db_path = tmp_path_factory.mktemp("rag_eval") / "rag.db"
    factory = ConnectionFactory(db_path=str(db_path))
    conn = factory.get_connection()
    conn.execute(
        "CREATE TABLE cards ("
        "id TEXT PRIMARY KEY, oracle_id TEXT NOT NULL, name TEXT NOT NULL, type_line TEXT, "
        "mana_cost TEXT, oracle_text TEXT, keywords TEXT, colors TEXT, cmc REAL, "
        "rarity TEXT, set_code TEXT, legalities TEXT, games TEXT)"
    )
    conn.commit()
    for card_id, name, type_line, mana_cost, oracle_text, colors, cmc, keywords in _CORPUS:
        _seed_card(
            conn,
            card_id,
            name=name,
            type_line=type_line,
            mana_cost=mana_cost,
            oracle_text=oracle_text,
            colors=colors,
            cmc=cmc,
            keywords=keywords,
        )
    conn.commit()

    embedder = get_embedder()
    build_card_embeddings(conn, embedder)
    yield factory, embedder

    factory.close()
    reset_embedder()


@pytest.mark.integration
def test_rag_sanity_eval_top_k_hit_rate(rag_eval_index) -> None:
    """AC1-AC3: the real model's aggregate top-K hit-rate meets the calibrated target.

    Runs every fixture query through the production ``semantic_search_cards`` -> ``hybrid_search``
    path, checks whether each expected card appears among the top-K returned names, aggregates the
    hit-rate, and asserts it ``>= TARGET_HIT_RATE`` -- naming every miss (and what ranked instead)
    so a failure points straight at the composite-text-weighting lever.
    """
    factory, embedder = rag_eval_index
    conn = factory.get_connection()

    case_results: list[CaseResult] = []
    for query, expected, k in _QUERY_FIXTURE:
        result = semantic_search_cards(conn, embedder, query, limit=k)
        assert result.status == "ok", (
            f"query {query!r} returned status={result.status!r}: {result.message}"
        )
        ranked = [hit.card.name for hit in result.cards]
        case_results.append((query, expected, ranked))

    hit_rate, misses = evaluate_hit_rate(case_results)
    assert hit_rate >= TARGET_HIT_RATE, format_failure(hit_rate, misses)


@pytest.mark.integration
def test_known_query_ranks_expected_card_first(rag_eval_index) -> None:
    """Tripwire independent of the aggregate: 'counter target spell' ranks Counterspell first.

    The most unambiguous case in the corpus (exact oracle match, large margin over Negate), as a
    fast nearest-first regression signal that does not depend on the aggregate threshold.
    """
    factory, embedder = rag_eval_index
    conn = factory.get_connection()

    result = semantic_search_cards(conn, embedder, "counter target spell", limit=DEFAULT_K)
    assert result.status == "ok"
    assert result.cards, "Expected at least one result for 'counter target spell'"
    assert result.cards[0].card.name == "Counterspell"


# --- Task 3: offline pure-logic guard (no model -> runs in the `-m "not integration"` subset) -


def test_evaluate_hit_rate_and_failure_message() -> None:
    """The harness computes the hit-rate and names misses correctly -- proven without the model.

    Guards the assert-and-name logic deterministically: an all-hit set scores 1.0 with no misses,
    while a below-target set yields the right rate and a message naming each missed query, its
    expected card, and what ranked in its place.
    """
    all_hit: list[CaseResult] = [
        ("burn", "Lightning Bolt", ["Lightning Bolt", "Shock"]),
        ("counter", "Counterspell", ["Negate", "Counterspell"]),
    ]
    rate, misses = evaluate_hit_rate(all_hit)
    assert rate == 1.0
    assert misses == []

    below_target: list[CaseResult] = [
        ("burn", "Lightning Bolt", ["Lightning Bolt", "Shock"]),
        ("counter", "Counterspell", ["Murder", "Negate"]),  # miss
        ("ramp", "Sol Ring", []),  # miss (no hits at all)
    ]
    rate, misses = evaluate_hit_rate(below_target)
    assert rate == pytest.approx(1 / 3)
    assert len(misses) == 2

    message = format_failure(rate, misses)
    assert "Counterspell" in message  # the expected card of a miss is named
    assert "Murder, Negate" in message  # what ranked instead is shown
    assert "(no hits)" in message  # the empty top-K case is reported, not silently dropped
    assert "composite-text weighting" in message  # points at the AC3 tuning lever
