"""Shared deterministic fake embedder for unit and integration tests.

A single offline stand-in for :class:`~src.search.embedder.Embedder`, consolidating the per-file
copies that previously lived in ``test_query.py``, ``test_index_builder.py``,
``test_semantic_search_tool.py``, ``test_find_similar_tool.py``, and ``integration/conftest.py``
(Pre-Epic-3 Targeted Gate G1). Each *distinct* composite text maps to a distinct one-hot 384-dim
``float32`` vector (stable per instance), so KNN nearest-neighbour assertions are exact and a
changed text yields a different vector — all without loading the ~80 MB ONNX model or any network.
"""

import numpy as np
from numpy.typing import NDArray

from src.search.embedder import EMBEDDING_DIM


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
            self._assigned[text] = len(self._assigned) % EMBEDDING_DIM
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        vec[self._assigned[text]] = 1.0
        return vec

    def encode(self, text: str) -> NDArray[np.float32]:
        return self._vector_for(text)

    def encode_batch(self, texts: list[str]) -> list[NDArray[np.float32]]:
        self.total_embedded += len(texts)
        return [self._vector_for(t) for t in texts]
