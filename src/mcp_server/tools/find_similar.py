"""Structured find-similar logic for the ``find_similar_cards`` MCP tool (Story 2.5).

The **second sync search tool** and the final Epic-2 search surface. Unlike
``semantic_search_cards`` it **never embeds** — it takes a *seed card* (by ``card_name`` or
``card_id``), resolves it in raw SQL on ``cards`` (the async ``CardRepository`` is unreachable on
the sync sqlite-vec connection), reads that card's **already-stored** vector back via
:func:`~src.search.query.get_card_vector` (a primary-key point lookup, not an ``encode``), and
seeds the Story 2.4 :func:`~src.search.query.hybrid_search` with it. The seed's **whole Oracle
identity** is excluded (``exclude_oracle_id``) so the results are genuine alternatives — never the
seed plus its reprints. Optional relational filters (``format``/``colors``/``mana_value_*``/
``games``) compose into the same hybrid path. Each surviving :class:`~src.search.query.CardHit` is
projected to the shared :class:`~src.mcp_server.tools.semantic_search.SemanticCardHit`.

Like ``semantic_search_cards`` this is **synchronous** over a
:class:`~src.search.connection.ConnectionFactory` connection (the vector index is reachable only on
the sync sqlite-vec connection) and **stateless** (D5): ``format``/``games`` and every filter are
per-call parameters. Seed resolution mirrors ``card_lookup``'s exact-then-partial /
0-1-2..5-6+ disambiguation *shape*, re-implemented as parameterized raw SQL.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

from src.data.schemas.card import CardSummary
from src.mcp_server.tools.semantic_search import SemanticCardHit
from src.search.query import ColorMode, get_card_vector, hybrid_search, index_is_populated

logger = logging.getLogger(__name__)

# Validation vocabularies (replicated from ``semantic_search.py`` so the modules stay decoupled —
# the colour / games codes are stable domain constants, the same precedent Story 2.4 set).
_VALID_COLORS = frozenset({"W", "U", "B", "R", "G"})
_VALID_GAMES = frozenset({"paper", "arena", "mtgo"})

# Upper bound on ``limit``: kept well under ``hybrid_search``'s ``over_fetch_k`` (200) so the
# over-fetch can never be starved by the requested ``limit`` (Pre-Epic-3 Targeted Gate G2). This
# also bounds the seed-printing exclusion, which consumes KNN slots before the limit is filled.
_MAX_LIMIT = 50

# Disambiguation buckets, mirroring ``card_lookup``: at most this many candidate matches, and
# above this many ask the user to refine rather than enumerate.
_MAX_MATCHES = 10
_REFINE_THRESHOLD = 5

# The ``cards`` columns the seed resolver reads — id + oracle_id (the exclusion key) plus the
# lightweight ``CardSummary`` projection fields. Raw column names mirror ``index_builder`` /
# ``card.py`` (there is no ``cards``-schema constants module; only ``card_vec`` has one).
_SEED_COLUMNS = (
    "id, oracle_id, name, mana_cost, cmc, type_line, oracle_text, colors, rarity, set_code"
)


class SimilarCardsResult(BaseModel):
    """Structured result of a find-similar query.

    Attributes:
        status: ``ok`` (``cards`` populated), ``empty`` (seed resolved/indexed but nothing survived
            the filters/exclusion), ``invalid`` (a parameter failed validation), ``not_found`` (the
            seed matched no card, or matched a card that isn't in the semantic index yet), or
            ``ambiguous`` (the name matched multiple distinct Oracle cards — see ``matches``), or
            ``index_unavailable`` (the ``card_vec`` semantic index has not been built yet).
        cards: The ranked alternatives, nearest-first (empty unless ``status == "ok"``).
        total_count: Number of alternatives returned (after oracle de-dup, exclusion, ``limit``).
        seed: The resolved seed card. Echoed back for ``ok`` and ``empty`` (seed found and
            indexed). Also populated for the "found but not yet indexed" ``not_found`` sub-case
            (the card exists in ``cards`` but has no ``card_vec`` row — the caller can use it to
            confirm which card was matched). ``None`` for ``not_found`` when the name/id could not
            be resolved at all, and for ``ambiguous`` (use ``matches`` instead).
        matches: Candidate seed cards when ``status == "ambiguous"`` (one per distinct Oracle id),
            so the caller can re-invoke with a specific ``card_id``.
        message: Human-facing summary — a count of alternatives, an adjust-your-filters hint, the
            disambiguation prompt, or the offending value when invalid.
    """

    status: Literal["ok", "empty", "invalid", "not_found", "ambiguous", "index_unavailable"]
    cards: list[SemanticCardHit] = []
    total_count: int = 0
    seed: CardSummary | None = None
    matches: list[CardSummary] = []
    message: str


@dataclass(frozen=True)
class _SeedResolution:
    """Outcome of resolving a seed identifier to a card (internal to this module)."""

    status: Literal["found", "not_found", "ambiguous"]
    card_id: str | None = None
    oracle_id: str | None = None
    summary: CardSummary | None = None
    matches: list[CardSummary] = field(default_factory=list)
    message: str = ""


def _decode_colors(raw: str | None) -> list[str]:
    """Decode the nullable ``cards.colors`` JSON-text column to a ``list[str]``.

    ``None`` / empty / a JSON ``null`` all coerce to ``[]`` (Story 2.3 lesson).
    """
    if not raw:
        return []
    value: list[str] | None = json.loads(raw)
    return value if value is not None else []


def _summary_from_row(row: Any) -> CardSummary:
    """Build a lightweight :class:`CardSummary` from a :data:`_SEED_COLUMNS` row (positional).

    The default tuple row factory is in use (``ConnectionFactory`` does not set ``row_factory``),
    so columns are indexed positionally. ``CardSummary``'s validators coerce a NULL
    ``mana_cost`` / ``oracle_text`` to ``""``; ``colors`` is decoded from JSON text here.
    """
    return CardSummary(
        id=row[0],
        name=row[2],
        mana_cost=row[3],
        cmc=row[4],
        type_line=row[5],
        oracle_text=row[6],
        colors=_decode_colors(row[7]),
        rarity=row[8],
        set_code=row[9],
    )


def _validation_error(
    *,
    card_name: str | None,
    card_id: str | None,
    colors: list[str] | None,
    games: list[str] | None,
    mana_value_min: float | None,
    mana_value_max: float | None,
    limit: int,
) -> str | None:
    """Return a specific message for the first invalid input, else ``None``.

    Guards the inputs the MCP boundary cannot type-check. ``card_name`` / ``card_id`` are expected
    already normalized (blank → ``None``) by the caller, so the exactly-one rule is a plain
    None-check. The filter checks mirror ``semantic_search``. Keeps failures graceful and
    unit-testable — callers surface the message as ``status="invalid"``.
    """
    has_name = card_name is not None
    has_id = card_id is not None
    if has_name == has_id:
        if has_name and has_id:
            return "Provide exactly one of card_name or card_id, not both."
        return (
            "Provide exactly one of card_name or card_id (the seed card to find alternatives to)."
        )

    if colors:
        for color in colors:
            if color not in _VALID_COLORS:
                return f"Invalid color '{color}'. Valid colors are W, U, B, R, G."

    if games:
        for game in games:
            if game not in _VALID_GAMES:
                return f"Invalid game '{game}'. Valid games are: paper, arena, mtgo."

    if mana_value_min is not None and mana_value_min < 0:
        return f"mana_value_min must be >= 0 (got {mana_value_min})."
    if mana_value_max is not None and mana_value_max < 0:
        return f"mana_value_max must be >= 0 (got {mana_value_max})."
    if (
        mana_value_min is not None
        and mana_value_max is not None
        and mana_value_min > mana_value_max
    ):
        return (
            f"mana_value_min ({mana_value_min}) must not exceed mana_value_max ({mana_value_max})."
        )

    if limit < 1:
        return f"limit must be >= 1 (got {limit})."
    if limit > _MAX_LIMIT:
        return f"limit must be <= {_MAX_LIMIT} (got {limit})."

    return None


def _resolve_seed(
    conn: sqlite3.Connection, card_name: str | None, card_id: str | None
) -> _SeedResolution:
    """Resolve a seed identifier to ``(card_id, oracle_id, CardSummary)`` in raw SQL on ``cards``.

    By ``card_id``: a primary-key point lookup (``not_found`` if absent). By ``card_name``: an exact
    (case-insensitive) match on ``name`` OR ``printed_name`` first (first printing by id), then a
    partial substring fallback collapsed to one candidate per distinct ``oracle_id`` — bucketed
    ``not_found`` (0) / ``found`` (1) / ``ambiguous`` (>1), mirroring ``card_lookup``. Every value
    is bound as a parameter (no f-string interpolation of user input). Assumes the inputs were
    normalized + validated (exactly one of ``card_name`` / ``card_id`` non-``None``).

    Args:
        conn: The sync sqlite-vec ``ConnectionFactory`` connection (also sees ``cards``).
        card_name: The seed name (exact-or-partial), or ``None`` when resolving by id.
        card_id: The seed printing id, or ``None`` when resolving by name.

    Returns:
        A :class:`_SeedResolution` describing the outcome.
    """
    if card_id is not None:
        row = conn.execute(f"SELECT {_SEED_COLUMNS} FROM cards WHERE id = ?", (card_id,)).fetchone()
        if row is None:
            return _SeedResolution(
                status="not_found",
                message=(
                    f"No card found with id '{card_id}'. "
                    "Check the id, or look the card up by name first."
                ),
            )
        return _SeedResolution(
            status="found", card_id=row[0], oracle_id=row[1], summary=_summary_from_row(row)
        )

    # card_name path: exact (name OR printed_name), then partial fallback.
    exact = conn.execute(
        f"SELECT {_SEED_COLUMNS} FROM cards "
        "WHERE lower(name) = lower(?) OR lower(printed_name) = lower(?) "
        "ORDER BY id LIMIT 1",
        (card_name, card_name),
    ).fetchone()
    if exact is not None:
        return _SeedResolution(
            status="found", card_id=exact[0], oracle_id=exact[1], summary=_summary_from_row(exact)
        )

    like = f"%{card_name}%"  # accepted LIKE-wildcard risk, mirroring CardRepository (deferred-work)
    rows = conn.execute(
        f"SELECT {_SEED_COLUMNS} FROM cards "
        "WHERE lower(name) LIKE lower(?) OR lower(printed_name) LIKE lower(?) "
        "ORDER BY id",
        (like, like),
    ).fetchall()

    # Collapse to one candidate per distinct oracle_id (nearest to CardRepository's unique-oracle).
    seen_oracles: set[str] = set()
    distinct: list[Any] = []
    for row in rows:
        if row[1] in seen_oracles:
            continue
        seen_oracles.add(row[1])
        distinct.append(row)

    if not distinct:
        return _SeedResolution(
            status="not_found",
            message=(
                f"No card found matching '{card_name}'. Check the spelling or try a different name."
            ),
        )
    if len(distinct) == 1:
        only = distinct[0]
        return _SeedResolution(
            status="found", card_id=only[0], oracle_id=only[1], summary=_summary_from_row(only)
        )

    shown = distinct[:_MAX_MATCHES]
    if len(distinct) > _REFINE_THRESHOLD:
        if len(shown) < len(distinct):
            message = (
                f"Found {len(distinct)} cards matching '{card_name}'. Please refine your search, "
                f"or re-call with a specific card_id; showing the first {len(shown)}."
            )
        else:
            message = (
                f"Found {len(distinct)} cards matching '{card_name}'. Please refine your search, "
                "or re-call with a specific card_id."
            )
    else:
        message = (
            f"Found {len(distinct)} cards matching '{card_name}'. Which one did you mean? "
            "Re-call with a specific card_id."
        )
    return _SeedResolution(
        status="ambiguous", matches=[_summary_from_row(row) for row in shown], message=message
    )


def find_similar_cards(
    conn: sqlite3.Connection,
    *,
    card_name: str | None = None,
    card_id: str | None = None,
    colors: list[str] | None = None,
    color_mode: ColorMode = "any",
    mana_value_min: float | None = None,
    mana_value_max: float | None = None,
    format: str | None = None,
    games: list[str] | None = None,
    limit: int = 10,
) -> SimilarCardsResult:
    """Find cards similar to a seed card by its **stored** vector, excluding the seed's own oracle.

    Resolves the seed (``card_name`` **or** ``card_id``, exactly one) in raw SQL on ``cards``, reads
    that card's already-stored embedding back via :func:`~src.search.query.get_card_vector` (a
    point lookup — **no embedding happens**), and seeds :func:`~src.search.query.hybrid_search` with
    it while excluding the seed's whole ``oracle_id`` so the results are genuine alternatives. Any
    optional relational filters compose into the same hybrid path. Validates first (returning
    ``status="invalid"`` rather than raising) and never surfaces an exception for a
    missing / ambiguous / unindexed seed. Stateless: every call is self-contained.

    Args:
        conn: A sync ``sqlite3.Connection`` from
            :class:`~src.search.connection.ConnectionFactory` (sqlite-vec loaded; sees both
            ``card_vec`` and ``cards`` in the single DB file).
        card_name: The seed card's name (exact-or-fuzzy) — provide this OR ``card_id``, not both.
        card_id: The seed card's printing id — provide this OR ``card_name``, not both.
        colors: Colour codes (W/U/B/R/G) matched per ``color_mode`` (vec0 metadata pre-filter).
        color_mode: How ``colors`` is matched — ``any`` / ``all`` / ``exact`` / ``at_most``.
        mana_value_min: Inclusive minimum mana value (floored to int in the pre-filter).
        mana_value_max: Inclusive maximum mana value (ceiled to int in the pre-filter).
        format: Restrict alternatives to cards legal in this MTG format (JOIN-side legality
            post-filter); empty/whitespace is normalized to ``None``.
        games: Restrict to platforms (``paper``/``arena``/``mtgo``) — JOIN-side availability filter.
        limit: Maximum number of alternatives to return (default 10).

    Returns:
        A :class:`SimilarCardsResult` with ``status`` of ``ok`` / ``empty`` / ``invalid`` /
        ``not_found`` / ``ambiguous`` / ``index_unavailable`` (the ``card_vec`` index is not built).

    Example:
        >>> from src.search import ConnectionFactory
        >>> conn = ConnectionFactory(db_path="./data/cards.db").get_connection()
        >>> result = find_similar_cards(conn, card_name="Glorybringer", format="standard", limit=5)
        >>> result.status  # doctest: +SKIP
        'ok'
    """
    # Normalize identifiers: blank / whitespace counts as "not provided".
    card_name = card_name.strip() if card_name is not None else None
    card_name = card_name or None
    card_id = card_id.strip() if card_id is not None else None
    card_id = card_id or None
    # Empty/whitespace format would fire a malformed json_extract path — normalize to "no filter".
    if format is not None and not format.strip():
        format = None

    error = _validation_error(
        card_name=card_name,
        card_id=card_id,
        colors=colors,
        games=games,
        mana_value_min=mana_value_min,
        mana_value_max=mana_value_max,
        limit=limit,
    )
    if error is not None:
        return SimilarCardsResult(status="invalid", message=error)

    # Guard the unbuilt/empty index up front: without ``card_vec`` the seed still resolves on the
    # ``cards`` table, but ``get_card_vector`` would then raise a raw OperationalError. Surface a
    # build-the-index hint instead so the skills suite stays graceful (G3).
    if not index_is_populated(conn):
        return SimilarCardsResult(
            status="index_unavailable",
            message=(
                "The semantic search index has not been built yet. Run "
                "`uv run python scripts/build_card_embeddings.py` to build it, then retry."
            ),
        )

    seed = _resolve_seed(conn, card_name, card_id)
    if seed.status == "not_found":
        return SimilarCardsResult(status="not_found", message=seed.message)
    if seed.status == "ambiguous":
        return SimilarCardsResult(status="ambiguous", matches=seed.matches, message=seed.message)

    # seed.status == "found" — all three fields are guaranteed by _resolve_seed, but guard
    # explicitly rather than assert so python -O cannot strip the check.
    if seed.card_id is None or seed.oracle_id is None or seed.summary is None:
        return SimilarCardsResult(
            status="not_found",
            message="Seed resolution returned an inconsistent state. Please try again.",
        )

    vector = get_card_vector(conn, seed.card_id)
    if vector is None:
        return SimilarCardsResult(
            status="not_found",
            seed=seed.summary,
            message=(
                f"Found '{seed.summary.name}' but it isn't in the semantic index yet, so similar "
                "cards can't be computed."
            ),
        )

    hits = hybrid_search(
        conn,
        vector,
        limit=limit,
        colors=colors,
        color_mode=color_mode,
        mana_value_min=mana_value_min,
        mana_value_max=mana_value_max,
        format_legal=format,
        games=games,
        exclude_oracle_id=seed.oracle_id,
    )

    if not hits:
        return SimilarCardsResult(
            status="empty",
            seed=seed.summary,
            total_count=0,
            message=(
                f"Found '{seed.summary.name}' but no other cards survived the filters. Try "
                "relaxing them (widen the mana range, drop a color, or remove the format filter)."
            ),
        )

    cards = [
        SemanticCardHit(
            card=CardSummary(
                id=hit.card_id,
                name=hit.name,
                mana_cost=hit.mana_cost or "",
                cmc=hit.cmc,
                type_line=hit.type_line,
                oracle_text=hit.oracle_text or "",
                colors=hit.colors,
                rarity=hit.rarity,
                set_code=hit.set_code,
            ),
            distance=hit.distance,
        )
        for hit in hits
    ]
    logger.debug("find_similar_cards: seed=%r -> %d alternatives", seed.summary.name, len(cards))
    return SimilarCardsResult(
        status="ok",
        cards=cards,
        total_count=len(cards),
        seed=seed.summary,
        message=f"Found {len(cards)} cards similar to '{seed.summary.name}' (nearest first).",
    )
