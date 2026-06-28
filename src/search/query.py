"""Reusable sync hybrid query over ``card_vec`` (KNN + metadata pre-filter) JOIN ``cards``.

The serve-time read path for the semantic index. A single hybrid query (research §A):

* **Pattern 1 — metadata pre-filter (inside the KNN):** ``mana_value`` and the five
  ``color_{w,u,b,r,g}`` flags are ``vec0`` metadata columns, so they go in the ``MATCH``/``k``
  ``WHERE`` and sqlite-vec applies a KNN-aware bitmap *before* computing distance.
* **Pattern 2 — relational post-filter (outside the KNN):** format legality and games
  availability resolve via a JOIN to ``cards`` (``json_extract`` / ``cast … LIKE``), which is
  why the KNN **over-fetches** ``k`` — the JOIN-side trim and the oracle-id de-dup happen after
  the vector scan and must not starve the requested ``limit``.

The index is keyed by *printing* (``card_id``), so many printings of one card share near-identical
vectors; results are **de-duplicated by ``oracle_id``** (nearest printing kept) before trimming to
``limit`` — mirroring the relational ``search_cards`` unique-oracle behaviour.

This function is **embed-agnostic**: it takes a *vector*, not a query string, so both
``semantic_search_cards`` (Story 2.4, the embedded NL query) and ``find_similar_cards`` (Story 2.5,
a seed card's stored vector) reuse it. It is pure sync and framework-free (no Pydantic) — the MCP
tool layer projects :class:`CardHit` to its Pydantic result.
"""

import json
import logging
import math
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import sqlite_vec
from numpy.typing import NDArray

from src.search.schema import (
    CARD_ID_COL,
    CARD_VEC_TABLE,
    COLOR_COLS,
    EMBEDDING_COL,
    MANA_VALUE_COL,
)

logger = logging.getLogger(__name__)

#: Colour-match semantics over the five ``color_*`` flag columns (mirrors ``search_cards``).
ColorMode = Literal["any", "all", "exact", "at_most"]

#: Map a WUBRG colour letter to its ``card_vec`` flag column, derived from :data:`COLOR_COLS`
#: so the mapping can never drift from the schema's declared column order.
_COLOR_LETTER_TO_COL: dict[str, str] = {col.rsplit("_", 1)[1].upper(): col for col in COLOR_COLS}


@dataclass(frozen=True)
class CardHit:
    """One semantic-search hit: card identity, the vec0 ``distance``, and ``CardSummary`` columns.

    Framework-free (no Pydantic) so ``src/search`` stays a reusable, agent-agnostic domain core;
    the MCP tool layer projects this to its Pydantic ``SemanticCardHit`` / ``CardSummary``.
    ``distance`` is the **raw** vec0 L2 distance (nearer = more similar — not converted to cosine);
    ``colors`` is already decoded from the ``cards.colors`` JSON-text column (``NULL`` → ``[]``).

    Attributes:
        card_id: The Scryfall printing UUID (``cards.id`` = ``card_vec.card_id``).
        oracle_id: The Oracle identity shared across printings (the de-dup key).
        distance: Raw vec0 L2 distance from the query vector (nearest-first ordering).
        name: Card name.
        mana_cost: Mana-cost string (e.g. ``"{3}{R}{R}"``); ``None`` for lands and tokens.
        cmc: Converted mana cost (mana value) as a float.
        type_line: The type line.
        oracle_text: Oracle rules text; ``None`` for some split/token cards.
        colors: Decoded colour letters (a subset of W/U/B/R/G; ``[]`` if none/NULL).
        rarity: Card rarity.
        set_code: The set code of this printing.

    Example:
        >>> hit = CardHit(
        ...     card_id="a1", oracle_id="o1", distance=0.12, name="Glorybringer",
        ...     mana_cost="{3}{R}{R}", cmc=5.0, type_line="Creature — Dragon",
        ...     oracle_text="Flying, haste", colors=["R"], rarity="mythic", set_code="AKH",
        ... )
        >>> hit.name, hit.colors
        ('Glorybringer', ['R'])
    """

    card_id: str
    oracle_id: str
    distance: float
    name: str
    mana_cost: str | None
    cmc: float
    type_line: str
    oracle_text: str | None
    colors: list[str]
    rarity: str
    set_code: str


def _coerce_json_list(raw: str | None) -> list[str]:
    """Decode a nullable JSON-text list column (``cards.colors``) into a ``list[str]``.

    The column is JSON stored as text over raw ``sqlite3`` (e.g. ``'["R"]'``, ``'[]'``, ``NULL``,
    or ``'null'``), so ``None`` / empty / a JSON ``null`` all coerce to ``[]`` (Story 2.3 lesson).

    Args:
        raw: The raw column value (JSON text, or ``None``).

    Returns:
        The decoded list of colour letters (``[]`` for absent/null).
    """
    if not raw:
        return []
    value: list[str] | None = json.loads(raw)
    return value if value is not None else []


def _color_predicates(colors: Sequence[str], color_mode: ColorMode) -> list[str]:
    """Build the colour metadata-flag SQL fragments for the KNN pre-filter.

    Operates over the constant :data:`COLOR_COLS` columns only — the requested letters select
    *which* fixed columns to test, so no user value is ever interpolated into SQL. Each returned
    fragment is a complete boolean expression to be ANDed into the KNN ``WHERE``.

    Args:
        colors: Requested colour letters (already validated to W/U/B/R/G by the caller).
        color_mode: ``any`` (has any), ``all`` (has all), ``exact`` (exactly these),
            ``at_most`` (a subset of these — no other colours).

    Returns:
        A list of SQL fragments (no bind parameters; column names are schema constants).
    """
    requested = [_COLOR_LETTER_TO_COL[c] for c in colors]
    others = [col for col in COLOR_COLS if col not in requested]

    if color_mode == "any":
        return ["(" + " OR ".join(f"{col} = 1" for col in requested) + ")"]
    if color_mode == "all":
        return [f"{col} = 1" for col in requested]
    if color_mode == "exact":
        return [f"{col} = 1" for col in requested] + [f"{col} = 0" for col in others]
    # at_most: the requested colours are optional, but no *other* colour may be present.
    return [f"{col} = 0" for col in others]


def get_card_vector(conn: sqlite3.Connection, card_id: str) -> NDArray[np.float32] | None:
    """Read a card's **stored** embedding back out of ``card_vec`` by primary key (Story 2.5).

    A **point lookup** by the TEXT primary key — *not* a KNN: ``SELECT embedding FROM card_vec
    WHERE card_id = ?`` (no ``MATCH`` / ``k``). On sqlite-vec v0.1.9 the ``embedding`` column comes
    back as the compact ``float32`` BLOB :func:`sqlite_vec.serialize_float32` wrote at index time
    (Story 2.3), which :func:`numpy.frombuffer` deserializes straight into a
    :data:`~src.search.embedder.EMBEDDING_DIM`-length ``float32`` array. The vector is byte-for-byte
    the one the card was indexed under, so feeding it back into :func:`hybrid_search` ranks the card
    at distance ≈ 0 (round-trip safe — both ends use the same encoding). This is how
    ``find_similar_cards`` seeds the KNN from a card it already has, **without re-embedding**.

    The seed value is bound as a parameter; the table/column identifiers are schema constants
    (never string literals). The default tuple row factory is used — the single column is read
    positionally.

    Args:
        conn: A ``sqlite3.Connection`` from
            :class:`~src.search.connection.ConnectionFactory` (sqlite-vec loaded).
        card_id: The Scryfall printing UUID (``cards.id`` = ``card_vec.card_id``) to read.

    Returns:
        The stored 384-dim ``float32`` embedding, or ``None`` if the ``card_id`` has no row in
        ``card_vec`` (i.e. the card is not in the semantic index yet — the "not indexed" signal
        ``find_similar_cards`` surfaces as a graceful result).

    Raises:
        sqlite3.OperationalError: If ``conn`` lacks the sqlite-vec extension, or on a SQL error.

    Example:
        >>> from src.search import ConnectionFactory
        >>> conn = ConnectionFactory(db_path="./data/cards.db").get_connection()
        >>> vec = get_card_vector(conn, "a1b2c3d4-...")  # doctest: +SKIP
        >>> vec.shape  # doctest: +SKIP
        (384,)
    """
    row = conn.execute(
        f"SELECT {EMBEDDING_COL} FROM {CARD_VEC_TABLE} WHERE {CARD_ID_COL} = ?",
        (card_id,),
    ).fetchone()
    if row is None:
        return None
    return np.frombuffer(row[0], dtype=np.float32)


def index_is_populated(conn: sqlite3.Connection) -> bool:
    """Return whether the ``card_vec`` semantic index exists **and** holds at least one vector.

    A fresh checkout / CI clone has no ``card_vec`` table (it is built by
    ``scripts/build_card_embeddings.py`` and never committed), and a half-built index can exist but
    be empty. Both cases must be distinguished from a genuine no-match so the search tools can
    return a graceful "build the index first" status instead of letting a raw
    ``sqlite3.OperationalError`` (*no such table*) escape — or silently reporting ``empty`` (the
    Pre-Epic-3 Targeted Gate G3 guard the skills suite sits on top of).

    The existence probe reads ``sqlite_master`` so the missing-table case returns ``False`` rather
    than raising; the table name is a schema constant (never interpolated user input).

    Args:
        conn: A ``sqlite3.Connection`` from
            :class:`~src.search.connection.ConnectionFactory` (sqlite-vec loaded).

    Returns:
        ``True`` if ``card_vec`` exists and contains at least one row, else ``False``.
    """
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (CARD_VEC_TABLE,),
    ).fetchone()
    if table is None:
        return False
    populated = conn.execute(f"SELECT EXISTS(SELECT 1 FROM {CARD_VEC_TABLE})").fetchone()
    return bool(populated[0])


def is_database_initialized(conn: sqlite3.Connection) -> bool:
    """Return whether the relational ``cards`` table exists **and** holds at least one row.

    A fresh first-run install ships no card data (excluded by design — Scryfall license), so the
    ``cards`` table may be missing or present-but-empty until the one-time ``initialize_database``
    tool runs. Both states return ``False`` **without raising**, so the sync sqlite-vec tools
    (``semantic_search_cards`` / ``find_similar_cards`` / ``build_search_index``) can surface a
    graceful ``database_not_initialized`` status instead of leaking a raw ``OperationalError``.

    This is the sync counterpart of :func:`src.data.database.is_database_initialized` (used by the
    async relational tools); the two never share a call site. Mirrors :func:`index_is_populated`:
    the ``sqlite_master`` probe makes the missing-table case return ``False``; ``cards`` is a schema
    constant, never interpolated input.

    Args:
        conn: A ``sqlite3.Connection`` (e.g. from
            :class:`~src.search.connection.ConnectionFactory`).

    Returns:
        ``True`` if ``cards`` exists and contains at least one row, else ``False``.
    """
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'cards'"
    ).fetchone()
    if table is None:
        return False
    populated = conn.execute("SELECT EXISTS(SELECT 1 FROM cards)").fetchone()
    return bool(populated[0])


def hybrid_search(
    conn: sqlite3.Connection,
    query_vector: NDArray[np.float32] | Sequence[float],
    *,
    limit: int = 10,
    over_fetch_k: int = 200,
    mana_value_min: float | None = None,
    mana_value_max: float | None = None,
    colors: Sequence[str] | None = None,
    color_mode: ColorMode = "any",
    format_legal: str | None = None,
    games: Sequence[str] | None = None,
    exclude_oracle_id: str | None = None,
) -> list[CardHit]:
    """Run the hybrid KNN + JOIN query and return de-duplicated, ranked :class:`CardHit` rows.

    Embeds nothing — the caller supplies ``query_vector`` (the embedded NL query in Story 2.4, or a
    seed card's stored vector in Story 2.5). The query vector and **every** filter value are bound
    as parameters; the only SQL-literal identifiers are schema constants (table/column names and
    the colour flag columns). Over-fetches ``over_fetch_k`` candidates from the KNN so the JOIN-side
    legality/games trim and the oracle-id de-dup can pare the set down to ``limit`` without starving
    it. Results are ordered nearest-first by raw vec0 distance, then collapsed to one hit per
    ``oracle_id`` (the nearest printing wins), then truncated to ``limit``.

    Args:
        conn: A ``sqlite3.Connection`` from
            :class:`~src.search.connection.ConnectionFactory` (sqlite-vec loaded). Must also see
            the ``cards`` table — guaranteed by the single-file topology (``card_vec`` and
            ``cards`` share one DB file).
        query_vector: A 384-dim query embedding (``float32`` ndarray or a float sequence);
            serialized via ``sqlite_vec.serialize_float32``.
        limit: Maximum number of de-duplicated hits to return (default 10).
        over_fetch_k: The mandatory KNN ``k`` (default 200) — over-fetched so JOIN-side filtering
            and oracle de-dup do not starve ``limit``. Never emit an unbounded ``vec0`` scan.
        mana_value_min: Inclusive minimum mana value; **floored** to an int (the column is
            ``int(cmc)``) before binding. ``None`` omits the lower bound.
        mana_value_max: Inclusive maximum mana value; **ceiled** to an int before binding.
            ``None`` omits the upper bound.
        colors: Requested colour letters (W/U/B/R/G), matched per ``color_mode``. Falsy → no
            colour filter.
        color_mode: How ``colors`` is matched (``any`` / ``all`` / ``exact`` / ``at_most``).
        format_legal: Restrict to cards legal in this MTG format via
            ``json_extract(cards.legalities, '$.<format>') = 'legal'``. Falsy → no legality filter.
        games: Restrict to cards available on any of these platforms (``paper`` / ``arena`` /
            ``mtgo``) via ``cast(cards.games AS TEXT) LIKE`` (OR across games). Falsy → no filter.
        exclude_oracle_id: If given, drop **every** hit whose ``oracle_id`` equals it — used by
            ``find_similar_cards`` to remove the seed card (and all its other printings) so results
            are genuine alternatives, not the seed echoed back. The skip happens inside the
            nearest-first de-dup loop *before* a hit consumes a ``limit`` slot, so the over-fetch /
            ``limit`` accounting stays correct. Default ``None`` preserves the Story 2.4 behaviour.

    Returns:
        A list of :class:`CardHit`, nearest-first, one per ``oracle_id``, at most ``limit`` long.
        Empty if nothing survives the filters.

    Raises:
        sqlite3.OperationalError: If ``conn`` lacks the sqlite-vec extension, or on a SQL error.

    Example:
        >>> from src.search import ConnectionFactory, get_embedder
        >>> conn = ConnectionFactory(db_path="./data/cards.db").get_connection()
        >>> vec = get_embedder().encode("semantically like Glorybringer")
        >>> hits = hybrid_search(conn, vec, limit=5, colors=["R"], format_legal="standard")
        >>> [h.name for h in hits]  # doctest: +SKIP
        ['Glorybringer', ...]
    """
    # --- Pattern 1: metadata pre-filters live INSIDE the KNN CTE (KNN-aware bitmap) ---------
    inner_clauses: list[str] = []
    inner_params: list[object] = []
    if mana_value_min is not None:
        inner_clauses.append(f"{MANA_VALUE_COL} >= ?")
        inner_params.append(math.floor(mana_value_min))
    if mana_value_max is not None:
        inner_clauses.append(f"{MANA_VALUE_COL} <= ?")
        inner_params.append(math.ceil(mana_value_max))
    if colors:
        inner_clauses.extend(_color_predicates(colors, color_mode))
    inner_where = "".join(f"\n      AND {clause}" for clause in inner_clauses)

    # --- Pattern 2: relational predicates live OUTSIDE, on the JOIN to cards ----------------
    outer_clauses: list[str] = []
    outer_params: list[object] = []
    if format_legal:
        outer_clauses.append("json_extract(c.legalities, ?) = 'legal'")
        outer_params.append(f"$.{format_legal}")
    if games:
        game_ors = " OR ".join("cast(c.games AS TEXT) LIKE ?" for _ in games)
        outer_clauses.append(f"({game_ors})")
        outer_params.extend(f'%"{game}"%' for game in games)
    outer_where = ("\nWHERE " + "\n  AND ".join(outer_clauses)) if outer_clauses else ""

    qvec_blob = sqlite_vec.serialize_float32(np.asarray(query_vector, dtype=np.float32))
    sql = (
        f"WITH knn AS (\n"
        f"    SELECT {CARD_ID_COL}, distance\n"
        f"    FROM {CARD_VEC_TABLE}\n"
        f"    WHERE {EMBEDDING_COL} MATCH ?\n"
        f"      AND k = ?{inner_where}\n"
        f")\n"
        f"SELECT knn.{CARD_ID_COL}, knn.distance,\n"
        f"       c.oracle_id, c.name, c.mana_cost, c.cmc, c.type_line, c.oracle_text,\n"
        f"       c.colors, c.rarity, c.set_code\n"
        f"FROM knn JOIN cards c ON c.id = knn.{CARD_ID_COL}{outer_where}\n"
        f"ORDER BY knn.distance"
    )
    params: list[object] = [qvec_blob, over_fetch_k, *inner_params, *outer_params]
    rows = conn.execute(sql, params).fetchall()

    # Oracle de-dup: rows are already nearest-first, so the first sighting of an oracle_id is its
    # nearest printing — keep it, drop later duplicates, and stop once `limit` unique hits are in.
    hits: list[CardHit] = []
    seen_oracles: set[str] = set()
    for row in rows:
        oracle_id = row[2]
        # Drop the seed's whole oracle (find_similar) before it can consume a `limit` slot.
        if exclude_oracle_id is not None and oracle_id == exclude_oracle_id:
            continue
        if oracle_id in seen_oracles:
            continue
        seen_oracles.add(oracle_id)
        hits.append(
            CardHit(
                card_id=row[0],
                oracle_id=oracle_id,
                distance=float(row[1]),
                name=row[3],
                mana_cost=row[4],
                cmc=float(row[5]),
                type_line=row[6],
                oracle_text=row[7],
                colors=_coerce_json_list(row[8]),
                rarity=row[9],
                set_code=row[10],
            )
        )
        if len(hits) >= limit:
            break

    logger.debug(
        "hybrid_search: k=%d -> %d rows -> %d unique hits (limit=%d)",
        over_fetch_k,
        len(rows),
        len(hits),
        limit,
    )
    return hits
