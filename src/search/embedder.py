"""Process-lifetime fastembed embedder: bge-small-en-v1.5 -> 384-dim float32, persistent cache."""

import logging
import os
import threading
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Single source of truth for downstream stories (2.2 schema / 2.3 builder import these — never
# hardcode the dimension or model name elsewhere).
MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
_DEFAULT_CACHE_DIR = "./data/fastembed_cache"


def _resolve_cache_dir(cache_dir: str | None) -> str:
    """Resolve the persistent directory fastembed should cache its ONNX model in.

    Mirrors ``connection.py::_resolve_db_path``. Resolution order:

    1. An explicit ``cache_dir`` argument (tests pass ``tmp_path``).
    2. The ``FASTEMBED_CACHE_DIR`` env var (operator override; empty value is treated as unset).
    3. The ``./data/fastembed_cache`` default — beside ``cards.db`` under the gitignored
       ``./data/`` tree, so the ~80 MB model stays out of git.

    The result is **always** a concrete project path; it never falls through to fastembed's
    volatile ``%TEMP%\\fastembed_cache`` default (the operational gotcha the RAG de-risk spike
    surfaced), forcing a re-download on every reboot/Temp cleanup.

    Args:
        cache_dir: Explicit cache directory, or ``None`` to derive from the environment.

    Returns:
        A filesystem path string suitable for ``TextEmbedding(cache_dir=...)``.
    """
    if cache_dir is not None:
        return cache_dir

    env_dir = os.getenv("FASTEMBED_CACHE_DIR")
    if env_dir:
        return env_dir
    return _DEFAULT_CACHE_DIR


class Embedder:
    """Thin synchronous embedding port over a fastembed ``TextEmbedding`` (bge-small-en-v1.5).

    Turns a string into a 384-dim ``float32`` numpy vector. This is the sibling of Story 1.2's
    :class:`~src.search.connection.ConnectionFactory`, but with the **opposite** sharing model:
    a ``sqlite3`` connection is per-thread, whereas the ONNX model is thread-safe and read-only
    at inference (ONNX Runtime releases the GIL during native inference), so it is loaded **once
    per process** and shared across every thread. Loading is expensive (~3.6 s incl. first-run
    download); each subsequent embed is ~3 ms.

    Construct via :func:`get_embedder`, **never** directly in application code — direct
    construction reloads the model and defeats the singleton (the whole point of this story).
    Tests may construct it directly to pin a ``cache_dir``.

    The returned vector is the **raw** model output: fastembed already L2-normalizes bge
    embeddings, so it is *not* re-normalized here. Vectors are numpy arrays (not ``list[float]``)
    because Story 2.3 serializes them via the buffer protocol (``sqlite_vec.serialize_float32``).

    Args:
        cache_dir: Explicit persistent cache directory. If ``None``, derived from the
            ``FASTEMBED_CACHE_DIR`` env var or the ``./data/fastembed_cache`` default
            (never fastembed's volatile Temp default).

    Example:
        >>> emb = get_embedder()
        >>> vec = emb.encode("Lightning Bolt")
        >>> vec.shape, vec.dtype
        ((384,), dtype('float32'))
    """

    def __init__(self, cache_dir: str | None = None) -> None:
        self._cache_dir = _resolve_cache_dir(cache_dir)
        # The model lazily downloads into this dir on first use; create it if absent.
        Path(self._cache_dir).mkdir(parents=True, exist_ok=True)
        logger.info("Loading fastembed model %s (cache_dir=%s)", MODEL_NAME, self._cache_dir)
        # This is the expensive one-time load (the "lazy boundary"): import is free, the model
        # materializes here, on the first get_embedder() call.
        self._model = TextEmbedding(model_name=MODEL_NAME, cache_dir=self._cache_dir)

    @property
    def dim(self) -> int:
        """Embedding dimensionality (384 for bge-small-en-v1.5)."""
        return EMBEDDING_DIM

    @property
    def model_name(self) -> str:
        """The fastembed model identifier this port loads."""
        return MODEL_NAME

    @property
    def cache_dir(self) -> str:
        """The resolved persistent cache directory the model loads from."""
        return self._cache_dir

    def encode(self, text: str) -> NDArray[np.float32]:
        """Embed a single string into a 384-dim ``float32`` vector.

        Args:
            text: The text to embed (for a card this is composed upstream in Story 2.3 as
                ``name + type_line + mana_cost + oracle_text + keywords``).

        Returns:
            A ``numpy.ndarray`` of shape ``(384,)`` and dtype ``float32`` — the raw, already
            L2-normalized bge embedding (do not re-normalize).
        """
        # embed() is a generator yielding one ndarray per input; pass [text] and take the first.
        result = list(self._model.embed([text]))
        # asarray(dtype=float32) is a safety-net coercion that also gives mypy a concrete
        # NDArray return type (fastembed is stub-less, so .embed() is typed Any).
        vector: NDArray[np.float32] = np.asarray(result[0], dtype=np.float32)
        return vector

    def encode_batch(self, texts: Sequence[str]) -> list[NDArray[np.float32]]:
        """Embed a batch of strings in a single fastembed pass, preserving input order.

        Used by the Story 2.3 index builder to embed ~60k cards efficiently.

        Args:
            texts: The texts to embed, in the order results should be returned.

        Returns:
            One ``(384,)`` ``float32`` vector per input string, in input order.
        """
        vectors: list[NDArray[np.float32]] = [
            np.asarray(vec, dtype=np.float32) for vec in self._model.embed(texts)
        ]
        return vectors


# --- Process-lifetime singleton (AC2) ------------------------------------------------------
# The model is shared across the whole process and all of FastMCP's threadpool workers. This is
# the ONLY supported way to obtain an Embedder for build-time (Story 2.3) and serve-time
# (Stories 2.4-2.5).
_embedder: Embedder | None = None
_lock = threading.Lock()


def get_embedder() -> Embedder:
    """Return the process-wide :class:`Embedder`, building it exactly once on first use.

    Uses double-checked locking so that concurrent first-use calls from FastMCP's threadpool
    cannot race two model loads. After the model is built, the fast path returns the cached
    instance without taking the lock. ``_embedder`` is assigned only after a successful build,
    so a failed construction never leaves a half-built singleton behind.

    Returns:
        The shared ``Embedder`` instance.
    """
    global _embedder
    if _embedder is None:  # fast path, no lock once built
        with _lock:
            if _embedder is None:  # re-check under lock
                _embedder = Embedder()
    return _embedder


def reset_embedder() -> None:
    """Clear the process-wide embedder singleton (test teardown / worker shutdown only).

    Analogous to :meth:`ConnectionFactory.close`. After this call the next :func:`get_embedder`
    rebuilds a fresh instance. Intended for test hygiene — a leaked singleton makes
    "constructed exactly once" assertions order-dependent and can carry a fake model into another
    test.
    """
    global _embedder
    with _lock:
        _embedder = None
