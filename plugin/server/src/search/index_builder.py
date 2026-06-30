"""Card embedding index builder: compose text, batch-embed, write vectors + metadata, hash-track."""

import hashlib
import json
import logging
import sqlite3
import time
from typing import NamedTuple

import sqlite_vec

from src.search.embedder import EMBEDDING_DIM, Embedder
from src.search.schema import (
    CARD_EMBEDDING_META_TABLE,
    CARD_ID_COL,
    CARD_VEC_TABLE,
    COLOR_COLS,
    CONTENT_HASH_COL,
    EMBEDDING_COL,
    METADATA_COLS,
    create_card_embedding_meta_table,
    create_card_vec_table,
)

logger = logging.getLogger(__name__)

# --- Read/write SQL (built from the Story 2.2 schema constants, never string literals) -------
#: The eight columns the builder writes per ``card_vec`` row: PK + vector + the six metadata cols.
_VEC_INSERT_COLS = (CARD_ID_COL, EMBEDDING_COL, *METADATA_COLS)
_VEC_INSERT_SQL = (
    f"INSERT INTO {CARD_VEC_TABLE} ({', '.join(_VEC_INSERT_COLS)}) "
    f"VALUES ({', '.join('?' for _ in _VEC_INSERT_COLS)})"
)
#: ``vec0`` rejects ``INSERT OR REPLACE`` (verified) — a changed card is DELETE-then-INSERTed.
_VEC_DELETE_SQL = f"DELETE FROM {CARD_VEC_TABLE} WHERE {CARD_ID_COL} = ?"
#: The companion hash table is *relational*, so a real UPSERT works (it does not on ``card_vec``).
_META_UPSERT_SQL = (
    f"INSERT INTO {CARD_EMBEDDING_META_TABLE} ({CARD_ID_COL}, {CONTENT_HASH_COL}) VALUES (?, ?) "
    f"ON CONFLICT({CARD_ID_COL}) DO UPDATE SET {CONTENT_HASH_COL} = excluded.{CONTENT_HASH_COL}"
)
_META_DELETE_SQL = f"DELETE FROM {CARD_EMBEDDING_META_TABLE} WHERE {CARD_ID_COL} = ?"
#: Raw read over ``cards`` on the *same* sync connection — not the async ``CardRepository``
#: (which has no bulk/stream read and would pull the async engine + ORM into this sync builder).
_READ_CARDS_SQL = (
    "SELECT id, name, type_line, mana_cost, oracle_text, keywords, colors, cmc FROM cards"
)
#: Colour letters (``W,U,B,R,G``) derived from :data:`COLOR_COLS` so the flag order can never
#: drift from the schema's declared column order.
_COLOR_LETTERS = tuple(col.rsplit("_", 1)[1].upper() for col in COLOR_COLS)


class _PendingCard(NamedTuple):
    """One new/changed card staged for embedding + write within the current chunk."""

    card_id: str
    mana_value: int
    color_flags: tuple[int, ...]
    content_hash: str
    changed: bool  # True → already had a (different) hash → DELETE old vector before INSERT


class BuildStatistics:
    """Track counts + timing across an index build (mirrors ``ImportStatistics``).

    Distinguishes the three classification outcomes the incremental builder produces —
    ``embedded_new`` (no stored hash), ``embedded_changed`` (stored hash differed), and
    ``skipped`` (hash unchanged) — plus ``pruned`` (orphan vectors removed when ``prune=True``).
    ``processed`` is every card read from ``cards`` (= new + changed + skipped).

    Example:
        >>> stats = BuildStatistics()
        >>> stats.processed = 3
        >>> stats.embedded_new = 3
        >>> "3 processed" in stats.summary()
        True
    """

    def __init__(self) -> None:
        self.processed = 0
        self.embedded_new = 0
        self.embedded_changed = 0
        self.skipped = 0
        self.pruned = 0
        self.start_time = time.time()

    def elapsed_time(self) -> float:
        """Return seconds elapsed since this statistics object was created.

        Returns:
            Wall-clock seconds since ``__init__``.
        """
        return time.time() - self.start_time

    def cards_per_second(self) -> float:
        """Return processing throughput in cards per second (0.0 before any time elapses).

        Returns:
            ``processed / elapsed`` cards/sec, or ``0.0`` if no measurable time has passed.
        """
        elapsed = self.elapsed_time()
        return self.processed / elapsed if elapsed > 0 else 0.0

    def summary(self) -> str:
        """Return a one-line human-readable summary of the build.

        Returns:
            A formatted string with processed / new / changed / skipped / pruned counts plus
            elapsed time and throughput.
        """
        return (
            f"Build complete: {self.processed:,} processed, "
            f"{self.embedded_new:,} new, {self.embedded_changed:,} changed, "
            f"{self.skipped:,} skipped, {self.pruned:,} pruned, "
            f"{self.elapsed_time():.1f}s ({self.cards_per_second():.1f} cards/sec)"
        )


def compose_card_text(
    name: str,
    type_line: str,
    mana_cost: str,
    oracle_text: str,
    keywords: list[str],
) -> str:
    """Compose the canonical per-card embedding text (FR14).

    Joins the five card fields in a **fixed, documented order** with a newline separator;
    ``keywords`` (a ``list[str]``) is first joined on a single space. The ordering and separators
    are deliberately stable because :func:`content_hash` of this string is the incremental
    builder's change-detection signal — any change here invalidates every stored hash. Story 2.6's
    RAG eval must embed *queries* against vectors built from this exact recipe, so it is the single
    canonical composition.

    The result is **never empty**: ``cards.name`` is ``NOT NULL`` and non-empty, so the embedder
    (whose single-string :meth:`~src.search.embedder.Embedder.encode` raises on empty input) is
    always given content.

    Args:
        name: The card name (``cards.name``; always present).
        type_line: The type line (``cards.type_line``).
        mana_cost: The mana cost string, e.g. ``"{3}{G}"`` (``cards.mana_cost``; ``""`` for lands).
        oracle_text: The oracle rules text (``cards.oracle_text``; may be ``""`` for vanilla cards).
        keywords: The keyword ability list (``cards.keywords``); ``None`` must be coerced to ``[]``
            by the caller before calling this function.

    Returns:
        The composite text, e.g. ``"Lightning Bolt\\nInstant\\n{R}\\nDeal 3 damage…\\n"``.

    Example:
        >>> compose_card_text("Llanowar Elves", "Creature — Elf Druid", "{G}", "{T}: Add {G}.", [])
        'Llanowar Elves\\nCreature — Elf Druid\\n{G}\\n{T}: Add {G}.\\n'
    """
    return "\n".join([name, type_line, mana_cost, oracle_text, " ".join(keywords)])


def content_hash(text: str) -> str:
    """Return the SHA-256 hex digest of ``text`` — the per-card change-detection signal (AC2).

    A pure function of the **composite text only** (never the model name or ``EMBEDDING_DIM``):
    it answers "did this card's embeddable text change since the last build?". It therefore does
    **not** detect a model/dimension swap (the text, and so the hash, is unchanged) — that
    migration is the explicit ``--rebuild`` path, which clears the stored hashes. See
    :func:`~src.search.schema.clear_card_embedding_meta`.

    Args:
        text: The composite text from :func:`compose_card_text`.

    Returns:
        A 64-character lowercase hex SHA-256 digest.

    Example:
        >>> content_hash("Lightning Bolt") == content_hash("Lightning Bolt")
        True
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_card_embeddings(
    conn: sqlite3.Connection,
    embedder: Embedder,
    *,
    batch_size: int = 1000,
    limit: int | None = None,
    prune: bool = False,
) -> BuildStatistics:
    """Build (or incrementally update) the ``card_vec`` semantic index from the ``cards`` table.

    Self-bootstrapping (ensures both ``card_vec`` and ``card_embedding_meta`` exist), then streams
    ``cards`` in chunks of ``batch_size``, composing :func:`compose_card_text` per card, hashing
    it (:func:`content_hash`), and classifying each card against the stored hashes as **new**,
    **changed**, or **unchanged**. Only new + changed cards are embedded (so a re-run re-embeds
    nothing if nothing changed — AC2). Each chunk's writes happen in **one transaction** committed
    per chunk: changed cards are DELETE-then-INSERTed (``vec0`` rejects ``INSERT OR REPLACE`` —
    AC3), new cards are plain INSERTs, and every embedded card's hash is UPSERTed into
    ``card_embedding_meta`` — atomically, so a card is hash-recorded iff its current vector is
    written. An interruption between chunks leaves completed chunks durable and the index
    converges with no duplicates or orphan hashes on the next run.

    Both collaborators are **injected** so unit tests can pass a ``tmp_path`` DB connection and a
    fake embedder (no model load / no network); the CLI is the composition root that wires the
    real :class:`~src.search.connection.ConnectionFactory` connection and
    :func:`~src.search.embedder.get_embedder` singleton.

    Args:
        conn: A ``sqlite3.Connection`` from
            :class:`~src.search.connection.ConnectionFactory` (sqlite-vec loaded, WAL on). The
            builder both reads ``cards`` and writes ``card_vec``/``card_embedding_meta`` on it.
        embedder: An :class:`~src.search.embedder.Embedder`; its
            :meth:`~src.search.embedder.Embedder.encode_batch` is called once per chunk on only
            the new/changed subset (this is where the Story 2.1 ``batch_size`` deferral is
            resolved — by chunking the read here, not by modifying ``Embedder``).
        batch_size: Cards read (and upper-bounded per ``encode_batch`` call) per chunk.
        limit: If set, only the first ``limit`` cards are processed (fast dev/test runs).
        prune: If ``True``, after the build remove orphan ``card_vec``/``card_embedding_meta`` rows
            whose ``card_id`` is no longer in ``cards`` (e.g. cards dropped by a later import).

    Returns:
        A :class:`BuildStatistics` with processed / new / changed / skipped / pruned counts and
        timing.

    Raises:
        sqlite3.OperationalError: If ``conn`` lacks the sqlite-vec extension, or on a write error
            (the in-flight chunk is rolled back and the error re-raised).
        ValueError: If the embedder returns a vector whose dimensionality is not
            :data:`~src.search.embedder.EMBEDDING_DIM`.

    Example:
        >>> from src.search import ConnectionFactory, get_embedder
        >>> factory = ConnectionFactory(db_path="./data/cards.db")
        >>> stats = build_card_embeddings(factory.get_connection(), get_embedder(), limit=200)
        >>> stats.processed
        200
    """
    create_card_vec_table(conn)
    create_card_embedding_meta_table(conn)

    # 38k hashes is small — load them all once into memory for O(1) classification per card.
    stored_hashes: dict[str, str] = dict(
        conn.execute(
            f"SELECT {CARD_ID_COL}, {CONTENT_HASH_COL} FROM {CARD_EMBEDDING_META_TABLE}"
        ).fetchall()
    )

    stats = BuildStatistics()
    read_cursor = conn.cursor()  # dedicated read cursor; writes go on conn directly
    if limit is not None:
        read_cursor.execute(f"{_READ_CARDS_SQL} LIMIT ?", (limit,))
    else:
        read_cursor.execute(_READ_CARDS_SQL)

    while True:
        rows = read_cursor.fetchmany(batch_size)
        if not rows:
            break
        _process_chunk(conn, embedder, rows, stored_hashes, stats)
        logger.info(
            "Processed %d cards (new=%d changed=%d skipped=%d) - %.1f cards/sec",
            stats.processed,
            stats.embedded_new,
            stats.embedded_changed,
            stats.skipped,
            stats.cards_per_second(),
        )

    if prune:
        _prune_orphans(conn, stats)

    logger.info(stats.summary())
    return stats


def _coerce_json_list(raw: str | None) -> list[str]:
    """Parse a nullable JSON-text column (``keywords``/``colors``) into a ``list[str]``.

    Both columns are nullable at the DB level and stored as JSON text over raw ``sqlite3``
    (e.g. ``'["R"]'``, ``'[]'``, or ``NULL``), so ``None`` (and the empty string) coerce to ``[]``.

    Args:
        raw: The raw column value (JSON text, or ``None``).

    Returns:
        The decoded list of strings (``[]`` for ``None``/empty).
    """
    if not raw:
        return []
    value: list[str] = json.loads(raw)
    return value


def _color_flags(colors: list[str]) -> tuple[int, ...]:
    """Map a card's ``colors`` array to the 0/1 flags in :data:`COLOR_COLS` order.

    Uses ``cards.colors`` (e.g. ``["R"]`` → ``color_r=1``), matching how ``search_cards`` reads
    "a red card" — deliberately **not** ``color_identity``.

    Args:
        colors: The card's colour letters, a subset of ``W,U,B,R,G``.

    Returns:
        Five ints (one per :data:`COLOR_COLS` entry), each 0 or 1.
    """
    present = set(colors)
    return tuple(1 if letter in present else 0 for letter in _COLOR_LETTERS)


def _process_chunk(
    conn: sqlite3.Connection,
    embedder: Embedder,
    rows: list[tuple[str, str, str, str, str, str | None, str | None, float]],
    stored_hashes: dict[str, str],
    stats: BuildStatistics,
) -> None:
    """Classify one chunk, embed the new/changed subset, and write it in a single transaction.

    Args:
        conn: The shared sync connection (reads + writes).
        embedder: The embedder whose ``encode_batch`` is called on the new/changed texts only.
        rows: One chunk of ``cards`` rows
            (``id, name, type_line, mana_cost, oracle_text, keywords, colors, cmc``).
        stored_hashes: ``{card_id: content_hash}`` loaded once at the start of the build.
        stats: Mutated in place with this chunk's processed / new / changed / skipped counts.
    """
    texts: list[str] = []
    pending: list[_PendingCard] = []
    new_count = 0
    changed_count = 0
    skipped_count = 0

    for card_id, name, type_line, mana_cost, oracle_text, kw_raw, colors_raw, cmc in rows:
        keywords = _coerce_json_list(kw_raw)
        colors = _coerce_json_list(colors_raw)
        text = compose_card_text(name, type_line, mana_cost, oracle_text, keywords)
        chash = content_hash(text)

        prior = stored_hashes.get(card_id)
        if prior == chash:
            skipped_count += 1
            continue

        changed = prior is not None  # had a different hash → changed; else brand new
        if changed:
            changed_count += 1
        else:
            new_count += 1
        texts.append(text)
        pending.append(_PendingCard(card_id, int(cmc), _color_flags(colors), chash, changed))

    stats.processed += len(rows)
    stats.embedded_new += new_count
    stats.embedded_changed += changed_count
    stats.skipped += skipped_count

    if not pending:
        return

    # Bounded by batch_size (default 1000 → ~1.5 MB float32); resolves the Story 2.1 batch_size
    # deferral at the builder, without modifying Embedder.
    vectors = embedder.encode_batch(texts)

    delete_params: list[tuple[str]] = [(p.card_id,) for p in pending if p.changed]
    insert_params: list[tuple[object, ...]] = []
    meta_params: list[tuple[str, str]] = []
    for pending_card, vector in zip(pending, vectors, strict=True):
        if vector.shape != (EMBEDDING_DIM,):
            raise ValueError(
                f"embedder returned a {vector.shape} vector for card {pending_card.card_id!r}; "
                f"expected ({EMBEDDING_DIM},)"
            )
        insert_params.append(
            (
                pending_card.card_id,
                sqlite_vec.serialize_float32(vector),
                pending_card.mana_value,
                *pending_card.color_flags,
            )
        )
        meta_params.append((pending_card.card_id, pending_card.content_hash))

    try:
        if delete_params:
            conn.executemany(_VEC_DELETE_SQL, delete_params)
        conn.executemany(_VEC_INSERT_SQL, insert_params)
        conn.executemany(_META_UPSERT_SQL, meta_params)
        conn.commit()
    except Exception:
        conn.rollback()  # roll the in-flight chunk back; completed chunks stay durable
        raise


def _prune_orphans(conn: sqlite3.Connection, stats: BuildStatistics) -> None:
    """Remove ``card_vec``/``card_embedding_meta`` rows whose card no longer exists in ``cards``.

    Computes the orphan set in Python from the *relational* ``card_embedding_meta`` table (the
    invariant "hash-recorded iff vector written" means its ids equal ``card_vec``'s), then deletes
    by id from both tables — avoiding a ``NOT IN (subquery)`` against the ``vec0`` table.

    Args:
        conn: The shared sync connection.
        stats: Mutated in place with the pruned-row count.
    """
    card_ids = {row[0] for row in conn.execute("SELECT id FROM cards").fetchall()}
    meta_ids = {
        row[0]
        for row in conn.execute(f"SELECT {CARD_ID_COL} FROM {CARD_EMBEDDING_META_TABLE}").fetchall()
    }
    orphans = meta_ids - card_ids
    if not orphans:
        return
    orphan_params = [(card_id,) for card_id in orphans]
    try:
        conn.executemany(_VEC_DELETE_SQL, orphan_params)
        conn.executemany(_META_DELETE_SQL, orphan_params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    stats.pruned += len(orphans)
    logger.info("Pruned %d orphan vectors no longer present in cards", stats.pruned)
