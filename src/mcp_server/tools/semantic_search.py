"""Structured semantic-search logic for the ``semantic_search_cards`` MCP tool (Story 2.4).

The **first sync tool helper**: it validates inputs gracefully (mirroring ``card_search.py``'s
``ok``/``empty``/``invalid`` contract), embeds the natural-language query via the Story 2.1
:class:`~src.search.embedder.Embedder` (symmetric plain ``encode`` — *not* a query-specific
embedding), runs the Story 2.4 :func:`~src.search.query.hybrid_search` (KNN + ``vec0`` metadata
pre-filter + JOIN-to-``cards`` legality/games + oracle de-dup), and projects each
:class:`~src.search.query.CardHit` to a lightweight ``CardSummary`` wrapped with its vec0
``distance``. Unlike the Epic-1 tools this is **synchronous** over a
:class:`~src.search.connection.ConnectionFactory` connection (the vector index is reachable only on
the sync sqlite-vec connection), not ``async`` over an ``AsyncSession``. Stateless (D5):
``format``/``games`` and every filter are per-call parameters; nothing is retained between calls.
"""

import logging
import sqlite3
from typing import Literal

from pydantic import BaseModel

from src.data.schemas.card import CardSummary
from src.search.embedder import Embedder
from src.search.query import ColorMode, hybrid_search

logger = logging.getLogger(__name__)

# Validation vocabularies (mirror ``card_search.py`` so the modules stay decoupled — the colour /
# games codes are stable domain constants, deliberately replicated rather than importing a private
# name from the async card-search module).
_VALID_COLORS = frozenset({"W", "U", "B", "R", "G"})
_VALID_GAMES = frozenset({"paper", "arena", "mtgo"})


class SemanticCardHit(BaseModel):
    """One ranked semantic hit: a lightweight ``CardSummary`` plus its vec0 ``distance``.

    Wraps a ``CardSummary`` (like ``DeckCardSummary`` does) so the projection stays lightweight —
    omitting ``legalities`` / ``image_uris`` / ``card_faces`` — while still carrying the raw vec0
    L2 ``distance`` as a relevance signal (nearer = more similar). Callers needing full card detail
    follow up with ``lookup_card_by_name``.

    Attributes:
        card: The lightweight card projection.
        distance: Raw vec0 L2 distance from the query embedding (smaller = more similar).
    """

    card: CardSummary
    distance: float


class SemanticSearchResult(BaseModel):
    """Structured result of a semantic (hybrid) card search.

    Attributes:
        status: ``ok`` (``cards`` populated), ``empty`` (a valid query/filters with no surviving
            matches), or ``invalid`` (a query/filter value failed validation).
        cards: The ranked hits, nearest-first (empty unless ``status == "ok"``).
        total_count: Number of hits returned (after oracle de-dup and ``limit``).
        query: The natural-language query reflected back to the caller.
        message: Human-facing summary — a nearest-first count, an adjust-your-query hint when
            empty, or the offending value when invalid.
    """

    status: Literal["ok", "empty", "invalid"]
    cards: list[SemanticCardHit] = []
    total_count: int = 0
    query: str
    message: str


def _validation_error(
    *,
    query: str,
    colors: list[str] | None,
    games: list[str] | None,
    mana_value_min: float | None,
    mana_value_max: float | None,
    limit: int,
) -> str | None:
    """Return a specific message for the first invalid input, else ``None``.

    Guards the inputs the MCP boundary cannot type-check (``color_mode`` is a ``Literal`` validated
    by FastMCP). Crucially, the **empty/whitespace query** is caught here so the embedder's
    ``encode`` is never called with ``""`` (which raises ``ValueError`` per the Story 2.1
    hardening). Keeps failures graceful and unit-testable — callers surface the message as
    ``status="invalid"``.
    """
    if not query or not query.strip():
        return "query must be a non-empty string describing what to search for."

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

    return None


def semantic_search_cards(
    conn: sqlite3.Connection,
    embedder: Embedder,
    query: str,
    *,
    colors: list[str] | None = None,
    color_mode: ColorMode = "any",
    mana_value_min: float | None = None,
    mana_value_max: float | None = None,
    format: str | None = None,
    games: list[str] | None = None,
    limit: int = 10,
) -> SemanticSearchResult:
    """Embed a natural-language query and return ranked, hybrid-filtered card hits.

    Validates first (returning ``status="invalid"`` rather than raising), embeds the query via
    :meth:`~src.search.embedder.Embedder.encode` (symmetric plain embedding — the same path the
    index builder used for card text), then delegates to :func:`~src.search.query.hybrid_search`
    and projects each :class:`~src.search.query.CardHit` to a :class:`SemanticCardHit`. Stateless:
    every call is self-contained (``format``/``games`` are per-call parameters).

    Args:
        conn: A sync ``sqlite3.Connection`` from
            :class:`~src.search.connection.ConnectionFactory` (sqlite-vec loaded; sees both
            ``card_vec`` and ``cards`` in the single DB file).
        embedder: The Story 2.1 :class:`~src.search.embedder.Embedder` used to embed ``query``.
        query: The natural-language search query (must be non-empty / non-whitespace).
        colors: Colour codes (W/U/B/R/G) matched per ``color_mode`` (vec0 metadata pre-filter).
        color_mode: How ``colors`` is matched — ``any`` / ``all`` / ``exact`` / ``at_most``.
        mana_value_min: Inclusive minimum mana value (floored to int in the pre-filter).
        mana_value_max: Inclusive maximum mana value (ceiled to int in the pre-filter).
        format: Restrict to cards legal in this MTG format (JOIN-side legality post-filter);
            empty/whitespace is normalized to ``None``.
        games: Restrict to platforms (``paper``/``arena``/``mtgo``) — JOIN-side availability filter.
        limit: Maximum number of de-duplicated hits to return (default 10).

    Returns:
        A :class:`SemanticSearchResult` with ``status`` of ``ok`` / ``empty`` / ``invalid``.

    Example:
        >>> from src.search import ConnectionFactory, get_embedder
        >>> conn = ConnectionFactory(db_path="./data/cards.db").get_connection()
        >>> result = semantic_search_cards(
        ...     conn, get_embedder(), "flying red dragon that deals damage",
        ...     colors=["R"], format="standard", limit=5,
        ... )
        >>> result.status  # doctest: +SKIP
        'ok'
    """
    # Empty/whitespace format would fire a malformed json_extract path — normalize to "no filter".
    if format is not None and not format.strip():
        format = None

    error = _validation_error(
        query=query,
        colors=colors,
        games=games,
        mana_value_min=mana_value_min,
        mana_value_max=mana_value_max,
        limit=limit,
    )
    if error is not None:
        return SemanticSearchResult(status="invalid", query=query, message=error)

    query_vector = embedder.encode(query)
    hits = hybrid_search(
        conn,
        query_vector,
        limit=limit,
        colors=colors,
        color_mode=color_mode,
        mana_value_min=mana_value_min,
        mana_value_max=mana_value_max,
        format_legal=format,
        games=games,
    )

    if not hits:
        return SemanticSearchResult(
            status="empty",
            query=query,
            total_count=0,
            message=(
                "No cards matched the query and filters. Try a broader description or relax the "
                "filters (e.g. widen the mana range, drop a color, or remove the format filter)."
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
    logger.debug("semantic_search_cards: query=%r -> %d hits", query, len(cards))
    return SemanticSearchResult(
        status="ok",
        cards=cards,
        total_count=len(cards),
        query=query,
        message=f"Found {len(cards)} cards semantically matching the query (nearest first).",
    )
