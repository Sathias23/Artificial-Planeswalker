"""Integration test: the real fastembed Embedder loads and yields stable 384-dim float32 vectors.

Marked ``integration`` because the first run downloads the bge-small-en-v1.5 model (~80 MB) into
the persistent cache dir; subsequent runs load from cache and are fully offline. Deselect with
``-m "not integration"``.
"""

import numpy as np
import pytest

from src.paths import fastembed_cache_dir
from src.search import EMBEDDING_DIM, Embedder
from src.search.embedder import reset_embedder

# Persistent central cache (src.paths.fastembed_cache_dir()) so the ~80 MB model is downloaded
# once and shared with the running server, rather than re-fetched into a throwaway tmp_path.
_CACHE_DIR = fastembed_cache_dir()


@pytest.fixture
def real_embedder():
    """Build the real Embedder against the persistent cache; reset singleton before and after."""
    reset_embedder()  # ensure clean singleton state going in
    embedder = Embedder(cache_dir=str(_CACHE_DIR))
    yield embedder
    reset_embedder()


@pytest.mark.integration
def test_real_model_encodes_stable_384_float32(real_embedder) -> None:
    """AC5: the real model loads and produces a stable 384-dim float32 vector (single + batch)."""
    first = real_embedder.encode("Lightning Bolt")
    assert isinstance(first, np.ndarray)
    assert first.shape == (EMBEDDING_DIM,)
    assert first.dtype == np.float32

    # Stability: the same input yields the identical vector across two calls (deterministic).
    second = real_embedder.encode("Lightning Bolt")
    assert np.array_equal(first, second)

    # Batch: one 384-dim float32 vector per input, in input order.
    batch = real_embedder.encode_batch(["Lightning Bolt", "Counterspell"])
    assert len(batch) == 2
    for vec in batch:
        assert vec.shape == (EMBEDDING_DIM,)
        assert vec.dtype == np.float32
