---
baseline_commit: f368d613f890b9080b092402a45527d16210409a
---

# Story 2.1: Embedder Port (fastembed singleton + persistent cache)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want an `Embedder` port backed by a **process-lifetime** fastembed singleton with a **persistent** model cache,
so that build-time (`scripts/build_card_embeddings.py`, Story 2.3) and serve-time (the `semantic_search_cards` / `find_similar_cards` tools, Stories 2.4–2.5) share one fast, offline embedding path that loads the model exactly once per process.

## Acceptance Criteria

> Source: [epics.md#Story-2.1](../planning-artifacts/epics.md) (BDD as authored), with implementation-critical clarifications folded in from analysis. **All five must hold simultaneously.**

**AC1 — `encode(text)` returns a 384-dim float32 vector from `bge-small-en-v1.5`**
- **Given** the `Embedder` port
- **When** `encode(text)` is called with a single string
- **Then** it returns a `numpy.ndarray` of shape `(384,)` and dtype `float32`, produced by `fastembed` using model `BAAI/bge-small-en-v1.5` (FR14).
- **Clarification:** the vector is the **raw model output** (fastembed already L2-normalizes bge embeddings; do **not** re-normalize). Return the numpy array directly — downstream (`sqlite_vec.serialize_float32`, Story 2.3) binds it via the buffer protocol, so a numpy `float32` array is the desired type, not a `list[float]`.

**AC2 — Model is a process-lifetime singleton (one load, reused across calls *and* threads)**
- **Given** the embedding model
- **When** it is first needed
- **Then** it is constructed **once per process**, cached, and reused on every subsequent call — **never re-instantiated per `encode` call** (NFR6).
- **And** the singleton accessor is **thread-safe**: concurrent first-use calls from FastMCP's threadpool must not build two models (double-checked locking).
- **Verifiable:** `get_embedder() is get_embedder()` returns `True`; the underlying `fastembed.TextEmbedding` is constructed exactly once across many `encode` calls and across multiple threads.

**AC3 — `FASTEMBED_CACHE_DIR` pinned to a persistent project path; offline after first download**
- **Given** the model cache
- **When** the `Embedder` is configured
- **Then** the cache directory resolves to a **persistent project path** (default `./data/fastembed_cache`), **never** fastembed's default volatile `%TEMP%\fastembed_cache`. The resolved path is passed explicitly as `cache_dir=` to `TextEmbedding` (so it holds even if the env var is unset).
- **And** an operator may override it via the `FASTEMBED_CACHE_DIR` environment variable (env override wins; falls back to the default — never to Temp).
- **And** after the first download the model loads from that cache with **no network egress** (NFR2). The cache directory is created if it does not exist.

**AC4 — Efficient batch encoding for index building**
- **Given** a batch (sequence) of texts
- **When** `encode_batch(texts)` is called
- **Then** it returns one 384-dim `float32` vector per input, in input order, embedding them efficiently in a single fastembed pass (used by the Story 2.3 index builder over ~60k cards).

**AC5 — Unit/integration tested: stable 384-dim float32 vector**
- **Given** the port
- **When** tested
- **Then** encoding a known string yields a **stable** 384-dim `float32` vector — the same input produces the identical vector across two calls (deterministic for a fixed model), proving the port and the persistent-cache load path work end-to-end.
- **Test split (see Dev Notes → Testing standards):** fast **unit** tests (no network) cover cache-dir resolution, singleton identity/one-load, and the `encode`/`encode_batch` shape+dtype contract via a fake model; a **`@pytest.mark.integration`** test loads the *real* model and asserts the real shape/dtype/stability.

## Tasks / Subtasks

- [x] **Task 1 — Create the `Embedder` port in `src/search/embedder.py`** (AC: 1, 3, 4)
  - [x] Add a one-line module docstring (project convention).
  - [x] Define module constants as the single source of truth (so Stories 2.2/2.3 import, not hardcode): `MODEL_NAME = "BAAI/bge-small-en-v1.5"`, `EMBEDDING_DIM = 384`, `_DEFAULT_CACHE_DIR = "./data/fastembed_cache"`.
  - [x] Implement `_resolve_cache_dir(cache_dir: str | None) -> str` mirroring `connection.py::_resolve_db_path`: explicit arg → `FASTEMBED_CACHE_DIR` env var → `_DEFAULT_CACHE_DIR`. **Never** return None / fall through to fastembed's Temp default.
  - [x] Implement class `Embedder`: in `__init__`, resolve the cache dir, `Path(cache_dir).mkdir(parents=True, exist_ok=True)`, then construct `TextEmbedding(model_name=MODEL_NAME, cache_dir=cache_dir)` and hold it as an instance attribute (this is where the model loads — see Dev Notes "Lazy boundary").
  - [x] `encode(self, text: str) -> NDArray[np.float32]`: call `self._model.embed([text])`, take the single result, coerce with `np.asarray(vec, dtype=np.float32)`, assert/trust shape `(EMBEDDING_DIM,)`, return it.
  - [x] `encode_batch(self, texts: Sequence[str]) -> list[NDArray[np.float32]]`: pass the whole sequence to `self._model.embed(texts)` (one pass), coerce each to `float32`, return a list in input order. (Optional `batch_size: int` passthrough is fine but not required.)
  - [x] Expose `dim` (property returning `EMBEDDING_DIM`) and `model_name` for downstream callers/diagnostics.
  - [x] Full type hints (`mypy --strict`), Google-style docstrings (`Args`/`Returns`/`Example`) on the public class + methods, guard clauses over deep nesting, `logger = logging.getLogger(__name__)` with `%`-style lazy args (log the resolved cache dir + model at load).
- [x] **Task 2 — Process-lifetime singleton accessor** (AC: 2)
  - [x] Module-level `_embedder: Embedder | None = None` and `_lock = threading.Lock()`.
  - [x] `get_embedder() -> Embedder`: double-checked locking — return the cached instance, building it once under the lock on first use. This is the **only** way build-time and serve-time obtain an embedder.
  - [x] `reset_embedder() -> None`: clear the module global under the lock (test teardown / worker shutdown), analogous to `ConnectionFactory.close()`. Document it as test-only.
- [x] **Task 3 — Export the port** (AC: 1, 2)
  - [x] Re-export from `src/search/__init__.py`: add `Embedder`, `get_embedder`, `EMBEDDING_DIM` to the imports and `__all__` (keep `ConnectionFactory`); update the package docstring (the embedder now exists; schema/builder/tools still land in later Epic-2 stories).
- [x] **Task 4 — Dependency & type-checker plumbing** (AC: 1)
  - [x] Add `numpy>=2.0.0` to `[project.dependencies]` in `pyproject.toml` — we now import numpy **directly** (currently only transitive via fastembed→onnxruntime). (`fastembed>=0.7.1` is already present; installed 0.8.0.)
  - [x] Add `numpy>=2.0.0` to `.pre-commit-config.yaml`'s mypy `additional_dependencies` so the isolated pre-commit mypy env resolves `numpy.typing.NDArray` the same as `uv run mypy src/` (the Story 1.1/1.2 rule — see Dev Notes "mypy/pre-commit"). Do **not** add `fastembed` there (stub-less; `ignore_missing_imports` covers it).
- [x] **Task 5 — Unit tests (fast, no network)** in `tests/unit/search/test_embedder.py` (AC: 1, 2, 3, 4)
  - [x] `_resolve_cache_dir`: explicit wins; env var honored; default `./data/fastembed_cache` when both absent; **never** returns a Temp path. (Use `monkeypatch.setenv/delenv`, mirroring `test_connection.py`.)
  - [x] Singleton: `get_embedder() is get_embedder()`; monkeypatch `TextEmbedding` with a fake to assert it is constructed **exactly once** across many `get_embedder()`/`encode` calls; call `reset_embedder()` in teardown so tests don't leak the singleton.
  - [x] `encode`/`encode_batch` contract via a **fake** `TextEmbedding` (monkeypatched) whose `.embed()` yields known numpy arrays → assert returned shape `(384,)`, dtype `float32`, batch length == input length and order preserved. (No real model load → fast, offline.)
- [x] **Task 6 — Integration test (real model, marked)** in `tests/integration/search/test_embedder.py` (AC: 5)
  - [x] Create `tests/integration/search/__init__.py` (mirror `src/` layout).
  - [x] `@pytest.mark.integration` test: build the real `Embedder` (pin `cache_dir` to a `tmp_path` **or** the project `./data/fastembed_cache`), `encode("Lightning Bolt")` → assert shape `(384,)`, dtype `float32`; encode the same string twice → assert `np.array_equal` (stability); `encode_batch(["Lightning Bolt", "Counterspell"])` → assert 2 vectors of dim 384. `reset_embedder()` in teardown.
  - [x] First run downloads the model (~80 MB) into the cache → that is why this test is `integration`-marked (deselectable with `-m "not integration"`); subsequent runs are offline.
- [x] **Task 7 — Document the new env var** (AC: 3)
  - [x] Add a commented `FASTEMBED_CACHE_DIR` entry to `.env.example` (note: defaults to `./data/fastembed_cache`; read by `src/search`; pin to a persistent path so the model survives reboots/Temp cleanup). `.env.example` is already in the working tree's modified set — fold this in.
- [x] **Task 8 — Verify (run the commands, capture output)** (AC: all)
  - [x] `uv run pytest tests/unit/search/ -v` → new unit tests pass (fast, offline).
  - [x] `uv run pytest tests/integration/search/ -v` → integration test passes (first run downloads the model).
  - [x] `uv run pytest tests/ -m "not integration"` → full active unit suite still green (no regressions; baseline 310+ passing).
  - [x] `uv run ruff check .` and `uv run ruff format --check .` → clean.
  - [x] `uv run mypy src/` → clean. Run `uv run pre-commit run mypy --all-files` too, to confirm the isolated env resolves numpy types after Task 4.

## Dev Notes

### What this story IS — and is NOT

- **IS:** a single, thin **infrastructure port** — `Embedder` — that wraps a `fastembed` `TextEmbedding(bge-small-en-v1.5)` as a **process-lifetime singleton** with a **persistent cache dir**, exposing `encode(text)` / `encode_batch(texts)` → 384-dim `float32` numpy vectors, plus its tests. This is research design-delta #2 [Source: [research §6 deltas](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md); [epics.md "Embedder port"](../planning-artifacts/epics.md)]. It is the **sibling** of Story 1.2's `ConnectionFactory` — same package, same "thin port + unit test + scope discipline" shape.
- **IS NOT:** the `card_vec` schema/virtual table (Story 2.2), vector **serialization** or the index builder (Story 2.3), the `semantic_search_cards` / `find_similar_cards` tools (Stories 2.4–2.5), or the RAG sanity eval (Story 2.6). **Do not** call `sqlite_vec.serialize_float32`, create `card_vec`, run a KNN query, compose the per-card embedded text (`name + type_line + …`), or wire an MCP tool here. The composite-text recipe and serialization belong to Story 2.3; this port only turns *a string* into *a vector*. Resist scaffolding ahead — Story 1.2 set this precedent.

### The singleton pattern (this story's defining decision — contrast with ConnectionFactory)

`ConnectionFactory` hands out a **per-thread** resource (a `sqlite3` connection is not thread-shareable). The `Embedder` is the **opposite**: the ONNX model is **thread-safe and read-only at inference** (ONNX Runtime releases the GIL during native inference), so it must be **one instance shared across the whole process and all threads** — loading it is expensive (~3.6 s incl. first-run download; subsequent embeds ~3 ms). [Source: [research §Embedding-Model Lifecycle](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md); [project-context.md](../project-context.md) "the embedding model is a **process singleton**"].

Use a module-level singleton with **double-checked locking**, so FastMCP's threadpool (multiple sync tools firing at once) can't race two model loads on first use:

```python
import threading

_embedder: Embedder | None = None
_lock = threading.Lock()

def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:               # fast path, no lock
        with _lock:
            if _embedder is None:       # re-check under lock
                _embedder = Embedder()
    return _embedder

def reset_embedder() -> None:           # test-only teardown
    global _embedder
    with _lock:
        _embedder = None
```

**Per-process, not cross-process:** build-time (the Story 2.3 script) and serve-time (the MCP server) are *separate processes*, so "shared" means they run the **same port code** and read the **same persistent cache dir** (no re-download) — not literally one in-memory object. Within each process, the singleton guarantees exactly one model load.

### The canonical fastembed call (verified API, fastembed 0.8.0)

```python
from fastembed import TextEmbedding

model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", cache_dir=cache_dir)
# embed() returns a GENERATOR of numpy float32 arrays, one per input text:
vectors = list(model.embed(["Lightning Bolt"]))   # -> [ndarray(shape=(384,), dtype=float32)]
```

- `embed()` is a **generator** — always wrap in `list(...)` (or iterate). For `encode(text)`, pass `[text]` and take `[0]`.
- fastembed emits `float32` already; the `np.asarray(x, dtype=np.float32)` coercion is a safety net and gives mypy a properly-typed return (see `warn_return_any` below).
- The model auto-downloads to `cache_dir` on first use and is **offline thereafter** (NFR2). [Source: [research §Component 3 / §Empirical spike](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md); fastembed README/docs.]
- **Quantized model note:** fastembed ships the **quantized** ONNX variant (`bge-small-en-v1.5-onnx-q`) under the `BAAI/bge-small-en-v1.5` name — confirmed by the spike (`dim: 384`, correct dragon ranking). Recall was good; if Story 2.6's eval shows weakness, that is the lever to revisit — **not** this story. [Source: research §Empirical spike, §10 open-low risk.]

### Query vs. passage embeddings (flag for Story 2.4 — do NOT build here)

`bge-small-en-v1.5` is retrieval-tuned: fastembed offers `query_embed()` (prepends a query instruction) in addition to plain `embed()` (passage/document). The RAG de-risk spike used **plain `embed()` symmetrically** for both stored cards and the query and got correct rankings, so `encode()` = plain `embed()` is the proven Phase-1 default and is correct for **index building** (the immediate consumer, Story 2.3). The query-side choice (`embed` vs `query_embed`) is a **Story 2.4 / 2.6 tuning decision** — surface it there. Keeping `encode()` as the single passage path now is the minimal, scope-disciplined choice; do not add `encode_query()` speculatively.

### Cache-dir resolution (mirror `_resolve_db_path`)

There is **no central settings module** — modules read env vars directly (e.g. `src/data/database.py` reads `CARDS_DATABASE_URL`; `ConnectionFactory` resolves its path inline) [Source: [Story 1.2 Dev Notes](./1-2-sqlite-connectionfactory-with-wal-extension-loading.md); [src/search/connection.py](../../src/search/connection.py)]. Follow that exact shape:
- Accept explicit `cache_dir` (tests pass `tmp_path`).
- Else read `FASTEMBED_CACHE_DIR` env var.
- Else default `./data/fastembed_cache`.
- **Always** pass the resolved value to `TextEmbedding(cache_dir=...)` — never let fastembed fall back to its volatile `%TEMP%\fastembed_cache` default (the operational gotcha the spike surfaced). [Source: research §Implementation "Two operational gotchas".]
- **Why `./data/`:** runtime data lives in `./data/` and the anchored `/data/` `.gitignore` rule keeps the ~80 MB model **out of git** automatically while sitting beside `cards.db`. (`/data/` is anchored so it does *not* match `src/data/` — Story 1.1 fix.) [Source: [.gitignore](../../.gitignore); [project-context.md](../project-context.md) "Data files live in `./data/`".]

### Lazy boundary (when does the model actually load?)

Nothing loads at import. The model loads when **`Embedder.__init__` constructs `TextEmbedding(...)`**, which happens on the **first `get_embedder()` call**. So: import is free; first `get_embedder()` pays the one-time load; everything after is cached. That is the right trade for a stdio server (no startup penalty until the first semantic query) and for the batch builder (loads once, embeds 60k). (fastembed also supports `lazy_load=True` to defer the ONNX session to first `embed()`; not needed for Phase 1 — keep it simple.)

### Typing: numpy, `warn_return_any`, mypy/pre-commit

- Use `from numpy.typing import NDArray` and annotate `-> NDArray[np.float32]`. numpy ships `py.typed`, so `uv run mypy src/` (project venv, numpy installed) type-checks it directly.
- **pre-commit gotcha:** the mypy pre-commit hook runs in an **isolated venv** containing only `additional_dependencies` — numpy is **not** in that list today, so without Task 4 the pre-commit run would treat numpy as `Any` (divergent from `uv run mypy src/`). Add `numpy>=2.0.0` to `additional_dependencies` (Story 1.1/1.2 rule: "if you add a runtime dep mypy needs to resolve types, also add it to `.pre-commit-config.yaml`'s mypy `additional_dependencies`"). [Source: [.pre-commit-config.yaml](../../.pre-commit-config.yaml); [Story 1.2 Dev Notes "mypy / pre-commit"](./1-2-sqlite-connectionfactory-with-wal-extension-loading.md).]
- `warn_return_any = true` is set [Source: [pyproject.toml](../../pyproject.toml)]: `fastembed` is stub-less (`ignore_missing_imports` → its `.embed()` returns `Any`). Returning that `Any` directly from `encode` would warn. The `np.asarray(result, dtype=np.float32)` coercion produces a properly-typed `NDArray`, satisfying the gate. `fastembed` does **not** need to go in `additional_dependencies` (no stubs to resolve).

### Concurrency model (AC2, NFR6)

FastMCP dispatches sync `def` tools to a **threadpool** → multiple tool calls can hit `get_embedder()` concurrently. The double-checked lock makes first-use safe; after that, all threads share one read-only model (ONNX releases the GIL during inference, so threadpooled embedding gets real parallelism). At Phase-1 scale (one Claude Code client) contention is negligible. [Source: [research §Concurrency & Threading Model](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md); [project-context.md](../project-context.md) "MCP server".]

### Testing standards (from project-context.md + repo conventions)

- pytest config in `pyproject.toml`: `asyncio_mode = "auto"`, `--strict-markers`, `--tb=short`, verbose; `testpaths = ["tests"]`. The `Embedder` is **sync** → plain `def test_...` (no `async`, no `@pytest.mark.asyncio`). [Source: [pyproject.toml](../../pyproject.toml); [project-context.md](../project-context.md) "Testing Rules".]
- Layout **mirrors `src/`**: unit → `tests/unit/search/test_embedder.py` (the `tests/unit/search/` package already exists from Story 1.2); integration → **new** `tests/integration/search/` (add `__init__.py`). Naming `test_*.py` / `test_*`. `tests.*` is exempt from `mypy --strict` but still ruff-clean.
- **Unit vs integration split:** a true unit test must not hit the network; the real model's first load can. So: fast **unit** tests use a **monkeypatched fake `TextEmbedding`** (assert wiring, singleton one-load, cache resolution, shape/dtype/order) and stay offline; one **`@pytest.mark.integration`** test loads the real model (network on first run, offline after) and proves the real 384-dim `float32` + stability. This satisfies AC5 ("encoding a known string yields a stable 384-dim float32 vector") while keeping the default suite fast — mark it so `-m "not integration"` skips it. [Source: [project-context.md](../project-context.md) "`integration` marker"; [research §Testing](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md).]
- **Singleton hygiene in tests:** always `reset_embedder()` in teardown (or a fixture) — a leaked process singleton makes "constructed exactly once" assertions order-dependent and can carry a fake model into another test. Follow the sync teardown discipline `ConnectionFactory.close()` established in [test_connection.py](../../tests/unit/search/test_connection.py).

### Anti-patterns (do NOT do these)

- ❌ Instantiate `TextEmbedding` (or call `Embedder()`) per `encode` call — the load is expensive; that defeats the whole story. Always go through `get_embedder()`.
- ❌ Let `FASTEMBED_CACHE_DIR` default to fastembed's `%TEMP%` cache — pin it; pass `cache_dir=` explicitly even when the env var is unset.
- ❌ Re-normalize the vector — bge output from fastembed is already L2-normalized; return it as-is.
- ❌ Return `list[float]` from `encode` — return the numpy `float32` array (Story 2.3 serializes it via the buffer protocol).
- ❌ Build `card_vec`, serialize vectors, compose per-card embedded text, run KNN, or wire an MCP tool here — those are Stories 2.2–2.5.
- ❌ Add `query_embed`/`encode_query` speculatively — defer the query/passage decision to Story 2.4.
- ❌ Make the port `async` — it is the **sync** path (FastMCP threadpools it), like `ConnectionFactory`.
- ❌ `print()` in library code — module-level `logger` with `%`-style lazy args; module docstring required.
- ❌ Commit the downloaded model — it lives under the gitignored `./data/`; never add it to git.

### Previous Story Intelligence (Story 1.2 — done; the direct template)

- Story 1.2 built `ConnectionFactory` in `src/search/connection.py` with: a `_resolve_*` env-fallback helper, a thin documented port class, full strict typing + Google docstrings, a `close()`/teardown seam, and **11 unit tests** in `tests/unit/search/`. **Mirror this structure** for `Embedder` — it is the same author's established pattern. [Source: [1-2-*.md File List & Dev Notes](./1-2-sqlite-connectionfactory-with-wal-extension-loading.md).]
- Story 1.2 code-review surfaced (and fixed) **resource-cleanup-on-error** bugs: `_build_connection` now wraps the load sequence in `try/except: conn.close(); raise`, and `close()` clears the thread-local even if `close()` throws. **Apply the same rigor:** if `TextEmbedding(...)` construction raises, don't leave a half-built singleton — only assign `_embedder` after a successful `Embedder()` build (the double-checked-lock shape above already does this). [Source: [1-2 Review Findings](./1-2-sqlite-connectionfactory-with-wal-extension-loading.md).]
- Review also flagged a **Windows path test bug** (a test used a Unix `/tmp/...` literal). Use `tmp_path` / `os.path`-style values in tests, never hardcoded `/tmp`. [Source: 1-2 Review Findings.]
- Core suite baseline is **green at 310 passed** on the lean install; `legacy/` excluded. Keep it green (NFR7). One known pre-existing flaky `test_list_decks` ordering issue was fixed in the Epic-1 tech-debt gate (commit `f368d61`). [Source: [1-2 Completion Notes](./1-2-sqlite-connectionfactory-with-wal-extension-loading.md); [epic-1-retro-2026-06-21.md](./epic-1-retro-2026-06-21.md).]
- `sqlite-vec` + `fastembed` + `mcp` were added to core deps back in Story 1.1; **`fastembed` is already installed** (0.8.0) — just `from fastembed import TextEmbedding`. The only new dependency action is making **numpy** explicit (Task 4). [Source: [pyproject.toml](../../pyproject.toml); [Story 1.1](./1-1-repository-restructure-dependency-reshape.md).]

### Git Intelligence

- HEAD `f368d61` "chore: clear Epic 1 tech-debt prep gate …" closes Epic 1; this is the **first feature code of Epic 2 (RAG)**. Recent commits (`d2e7d32`→`6b5c836`) built the MCP tool surface on top of `ConnectionFactory`; the pattern to match — thin port, thorough Dev Notes, run-and-capture verification, scope discipline — is well established across Epic 1.
- No `Embedder` exists yet — green field within `src/search` (which currently holds only `connection.py`). [Source: `git log`; [src/search/](../../src/search/).]
- Working tree already shows `.env.example`, `README.md`, `setup.py` as modified (pre-existing) — fold the `FASTEMBED_CACHE_DIR` doc into `.env.example`; leave `README.md`/`setup.py` unless your change needs them.

### Latest Tech / Versions (verified for THIS project, 2026-06-21)

| Item | Value | Source |
|---|---|---|
| `fastembed` | **0.8.0** (core dep `>=0.7.1`; already installed) | [pyproject.toml](../../pyproject.toml); `uv run python -c "import fastembed"` |
| `numpy` | **2.4.6** (transitive today → make explicit, Task 4) | `uv run python -c "import numpy"` |
| Embedding model | `BAAI/bge-small-en-v1.5` → ships **quantized** `bge-small-en-v1.5-onnx-q`, **384-dim**, `float32` | [research §Empirical spike](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md) |
| API | `TextEmbedding(model_name, cache_dir)`; `.embed(texts) -> generator[ndarray]`; `.query_embed()` exists (defer) | fastembed 0.8.0 docs (context7); README |
| Perf envelope | model load ~3.6 s (incl. first download); ~3 ms/query; ~15 ms / 5-card batch | research §Empirical spike (this machine) |
| Python / SQLite | CPython 3.12.13 / SQLite 3.50.4 / Windows / uv | [project-context.md](../project-context.md) "Verified platform envelope" |

### Project Structure Notes

Target additions (everything else unchanged):

```
src/
  search/
    __init__.py        # MODIFIED — also re-export Embedder, get_embedder, EMBEDDING_DIM
    connection.py      # (unchanged, Story 1.2)
    embedder.py        # NEW — Embedder (fastembed singleton) + get_embedder()/reset_embedder() + _resolve_cache_dir; MODEL_NAME/EMBEDDING_DIM consts
tests/
  unit/
    search/
      test_embedder.py     # NEW — fast unit tests (cache resolution, singleton one-load, encode/encode_batch contract via fake)
  integration/
    search/
      __init__.py          # NEW — package marker
      test_embedder.py     # NEW — @pytest.mark.integration real-model encode (shape/dtype/stability)
pyproject.toml         # MODIFIED — add numpy>=2.0.0 to [project.dependencies]
.pre-commit-config.yaml # MODIFIED — add numpy>=2.0.0 to mypy additional_dependencies
.env.example           # MODIFIED — document FASTEMBED_CACHE_DIR
```

- **Alignment:** matches spec §4 (`src/search` = embedding model wrapper + sqlite-vec integration + index builder) and research roadmap step 2 ("Search core — … `Embedder` (singleton + persistent cache) …"). [Source: [design spec §4](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md); [research §8](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md).]
- **Layering check:** `src/search` is a sync infra package consumed *downward* by `src/mcp_server` (Stories 2.4–2.5) and by `scripts/` (Story 2.3) — no upward import, no cycle. ✅

### References

- [epics.md — Epic 2 / Story 2.1](../planning-artifacts/epics.md) — user story, the five BDD ACs, the "Embedder port" additional requirement (fastembed singleton + persistent `FASTEMBED_CACHE_DIR`; `encode(text) -> float32`).
- [research — RAG de-risk](../planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md) — §Component 3 (fastembed on Windows), §Embedding-Model Lifecycle (process singleton), §6 delta #2, §Empirical spike (384-dim float32, ~3 ms, quantized variant, Temp-cache gotcha), §10 open-low recall risk.
- [design spec §4 / §6](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md) — `src/search` restructure; RAG embeddings (`bge-small-en-v1.5` via fastembed, 384-dim, offline).
- [project-context.md](../project-context.md) — RAG/MCP rules ("embedding model is a process singleton", "Don't let `FASTEMBED_CACHE_DIR` default"), async-vs-sync boundary, `./data/` data dir, testing layout, mypy/ruff gates, verified Windows envelope.
- [src/search/connection.py](../../src/search/connection.py) — the sibling port to mirror (`_resolve_*` helper, thin class, teardown seam, strict typing/docstrings).
- [tests/unit/search/test_connection.py](../../tests/unit/search/test_connection.py) — sync test style + env-monkeypatch + teardown pattern to follow.
- [Story 1.2](./1-2-sqlite-connectionfactory-with-wal-extension-loading.md) — port precedent, review findings (cleanup-on-error, Windows path test), deps/baseline.
- [pyproject.toml](../../pyproject.toml) / [.pre-commit-config.yaml](../../.pre-commit-config.yaml) — `fastembed>=0.7.1` present; mypy `additional_dependencies` (add numpy); `warn_return_any`.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.8 (1M context) — `claude-opus-4-8[1m]` — via the BMAD `dev-story` workflow.

### Debug Log References

- `uv run pytest tests/unit/search/test_embedder.py -v` → **14 passed** (0.38s, offline; fake `TextEmbedding`).
- `uv run pytest tests/integration/search/ -v` → **1 passed** (11.65s; first run downloaded `bge-small-en-v1.5-onnx-q` into `./data/fastembed_cache`). Benign HF Windows symlink warning only.
- `uv run pytest tests/ -m "not integration"` → **455 passed, 1 deselected** (19.30s; no regressions — baseline 310+ from Story 1.2 has since grown).
- `uv run mypy src/` → **Success, no issues in 41 source files**.
- `uv run pre-commit run mypy --all-files` → initially **failed** with 12 `Untyped decorator makes function untyped` errors in `src/mcp_server/server.py` (pre-existing: the isolated hook env lacked `mcp`, so `@mcp.tool()` resolved as `Any`). **`embedder.py` was clean** — confirming Task 4's numpy plumbing works. Added `mcp>=1.27.0` to the hook's `additional_dependencies` (same documented rule as the numpy add) → **Passed**.
- `uv run ruff check src/search/ tests/unit/search/test_embedder.py tests/integration/search/` and `ruff format --check` (same scope) → **clean** for all story files.

### Completion Notes List

- Implemented the `Embedder` port (`src/search/embedder.py`) as a thin sync wrapper over `fastembed.TextEmbedding("BAAI/bge-small-en-v1.5")`, mirroring Story 1.2's `ConnectionFactory` shape: a `_resolve_cache_dir` env-fallback helper, a documented port class with full strict typing + Google docstrings, module constants as the single source of truth (`MODEL_NAME`, `EMBEDDING_DIM = 384`, `_DEFAULT_CACHE_DIR`), and a `reset_*` teardown seam.
- **Singleton (AC2):** module-level `get_embedder()` with double-checked locking + `reset_embedder()`; `_embedder` is assigned only after a successful build, so a failed `TextEmbedding(...)` construction never leaves a half-built singleton (the cleanup-on-error rigor Story 1.2's review surfaced). A dedicated 8-thread concurrency test proves exactly-one-load under a `threading.Barrier` race.
- **Cache pinning (AC3):** `cache_dir` is always passed explicitly to `TextEmbedding` — resolution is explicit arg → `FASTEMBED_CACHE_DIR` → `./data/fastembed_cache`, **never** fastembed's volatile `%TEMP%`. Empty env var is treated as unset. Dir is `mkdir(parents=True, exist_ok=True)`. The integration test confirmed offline-after-first-download into the gitignored `./data/` tree.
- **Vector contract (AC1/AC4):** `encode(text) -> NDArray[np.float32]` shape `(384,)`; `encode_batch(texts)` one vector per input in order, single fastembed pass. Returns the raw (already L2-normalized) numpy array — not re-normalized, not `list[float]`. `np.asarray(..., dtype=np.float32)` is the coercion + the typed-return seam that satisfies `warn_return_any` against stub-less fastembed.
- **Scope discipline:** no `card_vec`, no serialization, no per-card text composition, no KNN, no MCP tool, no `query_embed`/`encode_query` — all deferred to Stories 2.2–2.6 exactly as the Dev Notes direct.
- **Out-of-scope pre-existing issues left untouched (NOT introduced by this story):** `uv run ruff check .` / `ruff format --check .` over the whole repo report issues in `_bmad/scripts/resolve_config.py`, `_bmad/scripts/resolve_customization.py`, and `src/mcp_server/tools/card_lookup.py` (committed in Story 1.3 / BMAD tooling). All **story-authored files are ruff-clean**; these unrelated files were deliberately not reformatted to keep the story diff focused. Pre-commit's ruff hook runs per-staged-file, so they won't block commits of this story's files.
- The `mcp>=1.27.0` addition to `.pre-commit-config.yaml` was a one-line fix for a pre-existing isolated-env gap surfaced by Task 8's required `pre-commit --all-files` run; it follows the same documented "add runtime deps mypy needs to `additional_dependencies`" rule that motivated the numpy add, and leaves the gate green for the whole `src/` tree.

### File List

**New:**
- `src/search/embedder.py` — `Embedder` port (fastembed singleton) + `get_embedder()`/`reset_embedder()` + `_resolve_cache_dir`; `MODEL_NAME`/`EMBEDDING_DIM`/`_DEFAULT_CACHE_DIR` constants.
- `tests/unit/search/test_embedder.py` — 14 fast offline unit tests (cache resolution, singleton one-load incl. concurrency, `encode`/`encode_batch` contract via a fake `TextEmbedding`).
- `tests/integration/search/__init__.py` — package marker for the new integration sub-package.
- `tests/integration/search/test_embedder.py` — `@pytest.mark.integration` real-model test (shape/dtype/stability + batch).

**Modified:**
- `src/search/__init__.py` — re-export `Embedder`, `get_embedder`, `EMBEDDING_DIM`; updated package docstring.
- `pyproject.toml` — added `numpy>=2.0.0` to `[project.dependencies]` (now imported directly).
- `.pre-commit-config.yaml` — added `numpy>=2.0.0` (Task 4) and `mcp>=1.27.0` (pre-existing-gap fix) to the mypy hook's `additional_dependencies`.
- `.env.example` — documented the `FASTEMBED_CACHE_DIR` env var (commented; defaults to `./data/fastembed_cache`).
- `uv.lock` — re-resolved so `numpy` is recorded as a direct dependency.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Story 2.1 `ready-for-dev` → `in-progress` → `review`.
- `_bmad-output/implementation-artifacts/2-1-embedder-port-fastembed-singleton-persistent-cache.md` — this story file (task checkboxes, Dev Agent Record, Change Log, Status).

## Change Log

| Date | Version | Description |
|---|---|---|
| 2026-06-21 | 1.0 | Implemented the `Embedder` port — fastembed `bge-small-en-v1.5` process-lifetime singleton (double-checked locking) with persistent `FASTEMBED_CACHE_DIR` pin, `encode`/`encode_batch` → 384-dim `float32` vectors. Added 14 unit tests + 1 integration test; numpy made a direct dep; `mcp` added to pre-commit mypy env. All ACs satisfied; full suite green (455 passed). Status → review. |
