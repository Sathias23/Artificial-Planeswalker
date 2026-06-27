"""Unit tests for the fastembed Embedder port (cache resolution, singleton one-load, contract).

These are fast and fully offline: the real ``TextEmbedding`` is monkeypatched with a fake, so
no model download or ONNX session ever occurs. The real-model load is covered by the
``@pytest.mark.integration`` test in ``tests/integration/search/test_embedder.py``.
"""

import threading
from pathlib import Path

import numpy as np
import pytest

import src.search.embedder as embedder_module
from src.paths import fastembed_cache_dir
from src.search import EMBEDDING_DIM, Embedder, get_embedder
from src.search.embedder import MODEL_NAME, _resolve_cache_dir, reset_embedder


class FakeTextEmbedding:
    """Stand-in for ``fastembed.TextEmbedding``: counts constructions, yields known vectors.

    It deliberately yields ``float64`` arrays (not ``float32``) so the port's
    ``np.asarray(..., dtype=np.float32)`` coercion is genuinely exercised, and encodes each
    input's leading character into every element so order preservation can be asserted.
    """

    construction_count = 0

    def __init__(self, model_name: str, cache_dir: str) -> None:
        FakeTextEmbedding.construction_count += 1
        self.model_name = model_name
        self.cache_dir = cache_dir

    def embed(self, documents, **kwargs):
        for doc in documents:
            # Use 0.0 for empty strings to avoid IndexError on doc[0].
            value = float(ord(doc[0])) if doc else 0.0
            yield np.full(EMBEDDING_DIM, value, dtype=np.float64)


@pytest.fixture
def fake_model(monkeypatch):
    """Patch ``TextEmbedding`` with the fake, reset the singleton + counter, clean up after."""
    FakeTextEmbedding.construction_count = 0
    monkeypatch.setattr(embedder_module, "TextEmbedding", FakeTextEmbedding)
    reset_embedder()
    yield FakeTextEmbedding
    reset_embedder()


# --- _resolve_cache_dir (AC3) --------------------------------------------------------------


def test_resolve_cache_dir_explicit_wins(tmp_path, monkeypatch) -> None:
    """An explicit cache_dir is returned verbatim, ignoring the environment."""
    monkeypatch.setenv("FASTEMBED_CACHE_DIR", str(tmp_path / "env_cache"))
    explicit = str(tmp_path / "explicit_cache")
    assert _resolve_cache_dir(explicit) == explicit


def test_resolve_cache_dir_env_honored(tmp_path, monkeypatch) -> None:
    """With no explicit arg, the FASTEMBED_CACHE_DIR env var is used."""
    env_dir = str(tmp_path / "env_cache")
    monkeypatch.setenv("FASTEMBED_CACHE_DIR", env_dir)
    assert _resolve_cache_dir(None) == env_dir


def test_resolve_cache_dir_defaults_when_absent(tmp_path, monkeypatch) -> None:
    """With no explicit arg and no env var, the central data-dir cache is used (absolute)."""
    monkeypatch.delenv("FASTEMBED_CACHE_DIR", raising=False)
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))
    assert _resolve_cache_dir(None) == str(fastembed_cache_dir())
    assert Path(_resolve_cache_dir(None)).is_absolute()


def test_resolve_cache_dir_empty_env_falls_back_to_default(tmp_path, monkeypatch) -> None:
    """An empty FASTEMBED_CACHE_DIR is treated as unset (never resolves to an empty path)."""
    monkeypatch.setenv("FASTEMBED_CACHE_DIR", "")
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))
    assert _resolve_cache_dir(None) == str(fastembed_cache_dir())


def test_resolve_cache_dir_whitespace_env_falls_back_to_default(tmp_path, monkeypatch) -> None:
    """A whitespace-only FASTEMBED_CACHE_DIR is treated as unset."""
    monkeypatch.setenv("FASTEMBED_CACHE_DIR", "   ")
    monkeypatch.setenv("PLANESWALKER_DATA_DIR", str(tmp_path))
    assert _resolve_cache_dir(None) == str(fastembed_cache_dir())


def test_resolve_cache_dir_never_temp(monkeypatch) -> None:
    """The default resolves to an absolute central path, never fastembed's volatile %TEMP%."""
    monkeypatch.delenv("FASTEMBED_CACHE_DIR", raising=False)
    monkeypatch.delenv("PLANESWALKER_DATA_DIR", raising=False)
    resolved = _resolve_cache_dir(None)
    assert Path(resolved).is_absolute()
    assert "temp" not in resolved.lower()
    assert "fastembed_cache" in resolved


# --- Singleton: one load, reused across calls and threads (AC2) ----------------------------


def test_get_embedder_returns_same_instance(fake_model) -> None:
    """get_embedder() returns the identical process-wide instance on every call."""
    assert get_embedder() is get_embedder()


def test_model_constructed_exactly_once(fake_model) -> None:
    """The underlying TextEmbedding is built once across many get_embedder()/encode calls."""
    emb = get_embedder()
    for _ in range(5):
        get_embedder().encode("Lightning Bolt")

    assert fake_model.construction_count == 1
    assert get_embedder() is emb


def test_concurrent_first_use_builds_one_model(fake_model) -> None:
    """Double-checked locking: concurrent first-use from many threads builds the model once."""
    barrier = threading.Barrier(8)
    results: list[Embedder] = []
    append_lock = threading.Lock()

    def worker() -> None:
        barrier.wait()  # release all threads together to maximize the first-use race
        emb = get_embedder()
        with append_lock:
            results.append(emb)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert fake_model.construction_count == 1
    assert all(result is results[0] for result in results)


def test_reset_embedder_forces_rebuild(fake_model) -> None:
    """reset_embedder() clears the singleton so the next get_embedder() builds a fresh model."""
    first = get_embedder()
    reset_embedder()
    second = get_embedder()

    assert first is not second
    assert fake_model.construction_count == 2


# --- encode / encode_batch contract (AC1, AC4) ---------------------------------------------


def test_encode_returns_384_float32(fake_model) -> None:
    """encode() returns a (384,) float32 vector, coercing the model's looser dtype."""
    vec = get_embedder().encode("Lightning Bolt")

    assert isinstance(vec, np.ndarray)
    assert vec.shape == (EMBEDDING_DIM,)
    assert vec.dtype == np.float32


def test_encode_raises_on_empty_string(fake_model) -> None:
    """encode("") raises ValueError rather than propagating an opaque error from fastembed."""
    with pytest.raises(ValueError, match="non-empty"):
        get_embedder().encode("")


def test_encode_batch_one_vector_per_input_in_order(fake_model) -> None:
    """encode_batch() returns one (384,) float32 vector per input, preserving input order."""
    texts = ["alpha", "bravo", "charlie"]
    vecs = get_embedder().encode_batch(texts)

    assert len(vecs) == len(texts)
    for text, vec in zip(texts, vecs, strict=True):
        assert vec.shape == (EMBEDDING_DIM,)
        assert vec.dtype == np.float32
        # the fake encodes the leading char into every element -> proves order is preserved
        assert vec[0] == float(ord(text[0]))


def test_encode_batch_empty_returns_empty(fake_model) -> None:
    """encode_batch([]) returns an empty list (no error on an empty batch)."""
    assert get_embedder().encode_batch([]) == []


# --- Wiring / diagnostics ------------------------------------------------------------------


def test_embedder_exposes_dim_and_model_name(fake_model) -> None:
    """dim and model_name expose the module constants for downstream callers."""
    emb = get_embedder()

    assert emb.dim == EMBEDDING_DIM == 384
    assert emb.model_name == MODEL_NAME


def test_embedder_creates_and_uses_resolved_cache_dir(tmp_path, fake_model) -> None:
    """__init__ creates the resolved cache dir and constructs the model with it."""
    cache = tmp_path / "fe_cache"
    emb = Embedder(cache_dir=str(cache))

    assert cache.is_dir()  # __init__ mkdir'd it (parents=True, exist_ok=True)
    assert emb.cache_dir == str(cache)
    # the model was constructed with the resolved cache dir + the pinned model name
    assert emb._model.cache_dir == str(cache)
    assert emb._model.model_name == MODEL_NAME


def test_embedder_raises_when_cache_dir_is_a_file(tmp_path, fake_model) -> None:
    """__init__ raises ValueError with a diagnostic when cache_dir points at a file."""
    file_path = tmp_path / "not_a_dir"
    file_path.write_text("oops")

    with pytest.raises(ValueError, match="exists as a file"):
        Embedder(cache_dir=str(file_path))
