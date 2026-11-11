"""Shared deterministic fake embedder for unit and integration tests.

A single offline stand-in for :class:`~src.search.embedder.Embedder`, consolidating the per-file
copies that previously lived in ``test_query.py``, ``test_index_builder.py``,
``test_semantic_search_tool.py``, ``test_find_similar_tool.py``, and ``integration/conftest.py``
(Pre-Epic-3 Targeted Gate G1). Each *distinct* composite text maps to a distinct one-hot 384-dim
``float32`` vector (stable per instance), so KNN nearest-neighbour assertions are exact and a
changed text yields a different vector — all without loading the ~80 MB ONNX model or any network.
One instance holds at most 384 distinct texts; the 385th raises ``ValueError`` rather than
silently reusing a vector.

:class:`RankedEmbedder` is the other stand-in, for tests that need thousands of cards in a strict
nearest-first order (one-hot vectors are all equidistant from each other, so they tie).
"""

import json
import math
import sqlite3
from collections.abc import Collection, Mapping

import numpy as np
from numpy.typing import NDArray

from src.search.embedder import EMBEDDING_DIM
from src.search.index_builder import compose_card_text


class FakeEmbedder:
    """Deterministic offline embedder: each distinct text -> a distinct one-hot vector.

    Identical text yields the identical vector (distance 0 to itself and to a duplicate printing
    with the same text), so KNN nearest-neighbour assertions are exact without loading the model.
    Implements the full :class:`~src.search.embedder.Embedder` surface used by tests — ``dim``,
    ``encode``, and ``encode_batch`` — and tracks ``total_embedded`` (consumed by the index-builder
    tests; harmlessly unused elsewhere).
    """

    def __init__(self) -> None:
        self.dim = EMBEDDING_DIM
        self._assigned: dict[str, int] = {}
        self.total_embedded = 0

    def _vector_for(self, text: str) -> NDArray[np.float32]:
        if text not in self._assigned:
            if len(self._assigned) == EMBEDDING_DIM:
                # A wrapped index would hand this text another text's vector, and every KNN
                # assertion past that point would be measuring a collision instead of a ranking.
                raise ValueError(
                    f"FakeEmbedder has only {EMBEDDING_DIM} one-hot vectors and all are assigned; "
                    "a further distinct text would reuse one. Use a fresh instance or fewer texts."
                )
            self._assigned[text] = len(self._assigned)
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        vec[self._assigned[text]] = 1.0
        return vec

    def encode(self, text: str) -> NDArray[np.float32]:
        return self._vector_for(text)

    def encode_batch(self, texts: list[str]) -> list[NDArray[np.float32]]:
        self.total_embedded += len(texts)
        return [self._vector_for(t) for t in texts]


class RankedEmbedder:
    """Deterministic offline embedder that puts each text at a chosen rank from one query vector.

    Rank ``r`` maps to the unit vector ``cos(r * step) * e0 + sin(r * step) * e1``, so its L2
    distance from :attr:`query_vector` (``e0``, rank 0) is ``2 * sin(r * step / 2)``, strictly
    increasing in ``r``. A KNN from ``query_vector`` therefore returns cards in rank order with no
    ties, which is what a window-size test needs. ``query_text`` encodes to ``e0`` too, so the
    semantic tool's embedded query lands on the same point; a card ranked 0 sits exactly there,
    which makes it the seed for ``find_similar_cards``.

    Args:
        ranks: Composite card text -> rank (``0 <= rank <= slots``). Encoding any other text
            raises ``KeyError`` so a typo cannot silently tie two cards.
        query_text: The text that encodes to rank 0 (the query vector itself).
        slots: The number of ranks spread over a quarter turn; the default leaves room for
            more than the 4,096-vector cap.
    """

    def __init__(
        self, ranks: Mapping[str, int], *, query_text: str = "query", slots: int = 8192
    ) -> None:
        self.dim = EMBEDDING_DIM
        self.total_embedded = 0
        self._ranks = dict(ranks)
        self._ranks.setdefault(query_text, 0)
        self._step = (math.pi / 2) / slots
        out_of_range = [rank for rank in self._ranks.values() if not 0 <= rank <= slots]
        if out_of_range:
            raise ValueError(f"ranks must lie in 0..{slots}; got {sorted(out_of_range)[:5]}")

    @property
    def query_vector(self) -> NDArray[np.float32]:
        """The rank-0 vector every rank is measured from."""
        return self._vector_at(0)

    def _vector_at(self, rank: int) -> NDArray[np.float32]:
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        angle = rank * self._step
        vec[0] = math.cos(angle)
        vec[1] = math.sin(angle)
        return vec

    def encode(self, text: str) -> NDArray[np.float32]:
        return self._vector_at(self._ranks[text])

    def encode_batch(self, texts: list[str]) -> list[NDArray[np.float32]]:
        self.total_embedded += len(texts)
        return [self.encode(t) for t in texts]


def seed_ranked_cards(
    conn: sqlite3.Connection,
    ranks: Mapping[str, int],
    *,
    standard_legal: Collection[str] = (),
    colors: Mapping[str, list[str]] | None = None,
) -> RankedEmbedder:
    """Insert one card per ``ranks`` entry into the real ``cards`` schema; return its embedder.

    Every card is its own oracle, named ``Ranked <card_id>``, paper-only, and ``standard``-legal
    only when its id is in ``standard_legal`` (``not_legal`` otherwise). Pass the returned
    :class:`RankedEmbedder` to ``build_card_embeddings`` and each card lands at its rank from
    ``embedder.query_vector``.

    Args:
        conn: A connection on a database built by ``init_database``.
        ranks: Card id -> rank from the query vector.
        standard_legal: The ids that are legal in ``standard``.
        colors: Card id -> colour letters (default colourless).

    Returns:
        A :class:`RankedEmbedder` keyed by each card's composed text.
    """
    colors = colors or {}
    legal = set(standard_legal)
    rows = []
    texts: dict[str, int] = {}
    for card_id, rank in ranks.items():
        name = f"Ranked {card_id}"
        oracle_text = f"Rank {rank}."
        card_colors = colors.get(card_id, [])
        texts[compose_card_text(name, "Instant", "{1}", oracle_text, [])] = rank
        rows.append(
            (
                card_id,
                name,
                f"oracle-{card_id}",
                "{1}",
                1.0,
                "Instant",
                oracle_text,
                "common",
                "TST",
                "Test Set",
                str(rank),
                json.dumps(card_colors),
                json.dumps(card_colors),
                json.dumps([]),
                json.dumps({"standard": "legal" if card_id in legal else "not_legal"}),
                json.dumps(["paper"]),
            )
        )
    conn.executemany(
        "INSERT INTO cards (id, name, oracle_id, mana_cost, cmc, type_line, oracle_text, "
        "rarity, set_code, set_name, collector_number, colors, color_identity, keywords, "
        "legalities, games) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    return RankedEmbedder(texts)
