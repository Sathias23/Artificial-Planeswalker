"""The shared ``FakeEmbedder`` never hands two distinct texts the same vector."""

import numpy as np
import pytest

from src.search.embedder import EMBEDDING_DIM
from tests.fixtures.embedder import FakeEmbedder


def test_every_distinct_text_up_to_the_dimension_gets_its_own_vector() -> None:
    embedder = FakeEmbedder()
    vectors = embedder.encode_batch([f"text {n}" for n in range(EMBEDDING_DIM)])

    hot = {int(np.argmax(vector)) for vector in vectors}
    assert len(hot) == EMBEDDING_DIM


def test_a_repeated_text_reuses_its_own_vector_past_the_limit() -> None:
    embedder = FakeEmbedder()
    first = embedder.encode("text 0")
    embedder.encode_batch([f"text {n}" for n in range(EMBEDDING_DIM)])

    assert np.array_equal(embedder.encode("text 0"), first)


def test_one_text_too_many_raises_naming_the_limit() -> None:
    embedder = FakeEmbedder()
    embedder.encode_batch([f"text {n}" for n in range(EMBEDDING_DIM)])

    with pytest.raises(ValueError, match=str(EMBEDDING_DIM)):
        embedder.encode(f"text {EMBEDDING_DIM}")
