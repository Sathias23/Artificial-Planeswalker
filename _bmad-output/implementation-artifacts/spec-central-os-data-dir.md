---
title: 'Central OS data directory for card DB + embedding cache'
type: 'feature'
created: '2026-06-27'
status: 'done'
baseline_commit: 'e0dafe3a5f691d812831ec9bcc843e23fce84f8c'
context: ['{project-root}/_bmad-output/project-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The SQLite card DB and the fastembed model cache are hard-coded to a project-relative `./data/` in three places (`src/data/database.py`, `src/search/connection.py`, `src/search/embedder.py`). Every clone re-imports ~60k cards and re-downloads the ~80 MB model into its own tree, and multiple MCP clients (Claude Desktop, Claude Code, Cursor…) cannot share one dataset.

**Approach:** Add a tiny leaf module `src/paths.py` (depends on `platformdirs`, imports nothing from `src.*`) that resolves one OS-appropriate data dir, and rewire the three touch points to it. Override precedence is unchanged — only the *default* moves from `./data/` to the central OS dir.

## Boundaries & Constraints

**Always:**
- Preserve resolution precedence: explicit arg (tests) > existing env var (`CARDS_DATABASE_URL` / `FASTEMBED_CACHE_DIR`) > central default. Add `PLANESWALKER_DATA_DIR` to override the whole data dir. Existing env-var setups must keep working byte-identically (keep `connection.py`'s prefix-strip branch).
- The async engine and the sync `ConnectionFactory` must resolve to the **same physical `cards.db`** (sqlite-vec vectors share that file, D2).
- `src/paths.py` is a leaf: zero `src.*` imports (layering `data → logic → mcp_server`).
- Honor repo rules: `mypy --strict`, ruff (line 100), module + Google docstrings, 3.12 typing, logging not prints. Add `platformdirs` to **both** `[project].dependencies` and the pre-commit mypy `additional_dependencies`.

**Ask First:**
- Folding in any deferred sibling goal: the first-run `database_not_initialized` status across all tools, `[project.scripts]` console entry points, or the README/CHANGELOG migration note. Only pull them in if the human asks.

**Never:**
- The all-tools `database_not_initialized` status (separate deferred goal — a fresh clone already has no populated DB, so centralization is no regression).
- Changing tool behaviour, repository/query/validator logic, or the single-file sqlite-vec topology.
- Shipping a prebuilt DB / bundling card data.
- README/LICENSE/CI/packaging or other dep trimming (other release goals).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Behavior | Error Handling |
|----------|--------------|-------------------|----------------|
| No env vars | resolve paths | Central OS dir (Win `%LOCALAPPDATA%\artificial-planeswalker`, mac `~/Library/Application Support/...`, Linux `~/.local/share/...` honouring `XDG_DATA_HOME`), created if missing; `cards.db` under it; URL `sqlite+aiosqlite:///<posix-abs>` | N/A |
| `CARDS_DATABASE_URL` set | env var | `database_url()` returns it verbatim; `_resolve_db_path(None)` strips the SQLAlchemy prefix (unchanged) | N/A |
| `FASTEMBED_CACHE_DIR` set | non-empty env | `_resolve_cache_dir(None)` returns it verbatim | empty/whitespace → unset → central default |
| `PLANESWALKER_DATA_DIR` set | env var | `data_dir()` = that expanded path; db + `fastembed_cache/` nest under it | N/A |
| Explicit arg | `db_path`/`cache_dir` passed | returned verbatim; env ignored | N/A |
| Central dir absent | first resolve | `mkdir(parents=True, exist_ok=True)` | N/A |

</frozen-after-approval>

## Code Map

- `src/paths.py` -- **NEW** leaf: `data_dir()`, `database_path()`, `fastembed_cache_dir()`, `database_url()`.
- `src/data/database.py:27` -- relative `DATABASE_URL` module default (touch point #1, async engine).
- `src/search/connection.py:13,40` -- `_DEFAULT_DB_PATH` + `_resolve_db_path` no-env branch (#2, sync factory).
- `src/search/embedder.py:19,50` -- `_DEFAULT_CACHE_DIR` + `_resolve_cache_dir` no-env branch (#3, model cache).
- `src/mcp_server/server.py:75` -- docstring name-drops `./data/cards.db`; light update.
- `pyproject.toml:10-26` / `.pre-commit-config.yaml:16` -- add `platformdirs`.
- `.env.example` (whole file) -- full cleanup: drop the `LEGACY ONLY` block (lines 34-58), re-document data-path lines, add `PLANESWALKER_DATA_DIR`.
- `tests/unit/test_paths.py` -- **NEW**. `tests/unit/search/test_connection.py:117` + `test_embedder.py:16,68-93` -- default-resolution tests pinning the old paths. `tests/integration/search/test_embedder.py:18` + `test_rag_eval.py:13` -- own project-relative `_CACHE_DIR`. `tests/unit/data/test_database.py:6` -- confirm still green.

## Tasks & Acceptance

**Execution:**
- [x] `src/paths.py` -- create the 4-function leaf module per Design Notes (module + Google docstrings, no `src.*` imports).
- [x] `pyproject.toml` -- add `platformdirs>=4.0.0` to `[project].dependencies` (keep alpha-sorted).
- [x] `.pre-commit-config.yaml` -- add `platformdirs>=4.0.0` to the mypy hook `additional_dependencies` (project rule for strict types).
- [x] `src/data/database.py` -- `from src.paths import database_url as default_database_url`; in `create_engine` use `url = database_url or default_database_url()`; drop the relative module default (lazy → no import-time `mkdir`; alias avoids the param-name clash); fix docstring.
- [x] `src/search/connection.py` -- `from src.paths import database_path`; no-env branch returns `str(database_path())`; delete `_DEFAULT_DB_PATH`; refresh docstrings/Example. Keep the env-set prefix-strip branch identical.
- [x] `src/search/embedder.py` -- `from src.paths import fastembed_cache_dir`; no-env branch returns `str(fastembed_cache_dir())`; delete `_DEFAULT_CACHE_DIR`; refresh docstrings.
- [x] `src/mcp_server/server.py` -- update the line-75 docstring to the central dir.
- [x] `.env.example` -- full cleanup: delete the `LEGACY ONLY` section (lines 34-58: LLM keys, `AGENT_*`, Chainlit toggles, Logfire); re-document the Database + fastembed lines for the central default; add a commented `PLANESWALKER_DATA_DIR`. Result: a lean file with only `CARDS_DATABASE_URL` (commented, central default), `MCP_TRANSPORT`, `FASTEMBED_CACHE_DIR` (commented), `PLANESWALKER_DATA_DIR` (commented), and the Scryfall import note.
- [x] `tests/unit/test_paths.py` -- **NEW**: cover the matrix (override-wins, central default absolute & app-named, db/cache nesting, `database_url` explicit-vs-central) using `PLANESWALKER_DATA_DIR=tmp_path` for hermetic central-path assertions.
- [x] `tests/unit/search/test_connection.py` -- rewrite `test_resolve_db_path_defaults_when_env_absent` to assert `str(database_path())` (via `PLANESWALKER_DATA_DIR=tmp_path`); leave the prefix-strip tests.
- [x] `tests/unit/search/test_embedder.py` -- drop the `_DEFAULT_CACHE_DIR` import; point the three default tests at `fastembed_cache_dir()` (via `PLANESWALKER_DATA_DIR=tmp_path`); keep the never-temp / absolute checks.
- [x] `tests/integration/search/test_embedder.py` + `test_rag_eval.py` -- point `_CACHE_DIR` / docstring at `fastembed_cache_dir()` so the model is shared (no duplicate 80 MB download).
- [x] `tests/unit/data/test_database.py` -- confirm `test_create_engine_default_url` still passes (asserts only `"sqlite" in url`); no change expected.

**Acceptance Criteria:**
- Given no `CARDS_DATABASE_URL` / `PLANESWALKER_DATA_DIR`, when storage is resolved, then the async engine and the sync `ConnectionFactory` open the **same** `cards.db` inside `platformdirs.user_data_dir("artificial-planeswalker", appauthor=False)`, created if missing.
- Given an existing `CARDS_DATABASE_URL` or `FASTEMBED_CACHE_DIR`, when resolving, then the explicit value is used unchanged — proven by the unchanged prefix-strip tests still passing.
- Given `PLANESWALKER_DATA_DIR=<dir>`, when resolving, then `cards.db` and `fastembed_cache/` both nest under `<dir>`.
- Given a fresh checkout, when `uv run python -m setup` then `uv run python scripts/build_card_embeddings.py` run, then card import and the embedding index land in the SAME central `cards.db` (idempotent skip when populated).
- Given the cleaned `.env.example`, then it contains no legacy/LLM-provider settings (no `ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY` / `AGENT_*` / Chainlit / Logfire) and documents only the MCP-server data-path + transport settings.
- Given the change, when `ruff check`, `ruff format --check`, `mypy src/`, and `pytest -m "not integration"` run, then all pass.
- `src/paths.py` imports nothing from `src.*`.

## Spec Change Log

## Design Notes

`src/paths.py` golden form (`PLANESWALKER_DATA_DIR` → platformdirs; `database_url()` still lets `CARDS_DATABASE_URL` win):

```python
_APP = "artificial-planeswalker"

def data_dir() -> Path:
    override = (os.getenv("PLANESWALKER_DATA_DIR") or "").strip()
    base = Path(override).expanduser() if override else Path(user_data_dir(_APP, appauthor=False))
    base.mkdir(parents=True, exist_ok=True)
    return base

def database_path() -> Path:        return data_dir() / "cards.db"
def fastembed_cache_dir() -> Path:  d = data_dir() / "fastembed_cache"; d.mkdir(parents=True, exist_ok=True); return d
def database_url() -> str:
    explicit = (os.getenv("CARDS_DATABASE_URL") or "").strip()
    return explicit or f"sqlite+aiosqlite:///{database_path().as_posix()}"
```

Gotchas: `database.py` resolves lazily *inside* `create_engine` (not a module constant) so import never `mkdir`s the OS dir, and the import is aliased because the param is also `database_url`. `connection.py` consumes `str(database_path())` (native sep, for `sqlite3.connect`); `database.py` uses the `.as_posix()` URL — both resolve to the identical file. Default-path unit tests set `PLANESWALKER_DATA_DIR=tmp_path` to stay hermetic.

## Verification

**Commands:**
- `uv add platformdirs` -- expected: `platformdirs` in `pyproject.toml` + `uv.lock`.
- `uv run python -c "import src.paths as p; print(p.data_dir(), p.database_path(), p.database_url(), p.fastembed_cache_dir())"` -- expected: paths under the OS data dir; no exception.
- `uv run pytest tests/unit/test_paths.py tests/unit/search/test_connection.py tests/unit/search/test_embedder.py tests/unit/data/test_database.py -q` -- expected: all pass.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` -- expected: clean.
- `uv run pytest -m "not integration"` -- expected: green.

## Suggested Review Order

**The central resolver (start here)**

- Entry point: the leaf module that resolves one OS data dir; relative overrides are made absolute.
  [`paths.py:23`](../../src/paths.py#L23)

- Explicit `CARDS_DATABASE_URL` still wins; else a posix-form URL into the central dir (Windows-safe).
  [`paths.py:67`](../../src/paths.py#L67)

**The three rewired touch points (single-file invariant)**

- Async engine resolves the central URL lazily — no import-time `mkdir`, alias dodges the param clash.
  [`database.py:36`](../../src/data/database.py#L36)

- Sync factory treats empty/whitespace `CARDS_DATABASE_URL` as unset, so it can't diverge from async.
  [`connection.py:43`](../../src/search/connection.py#L43)

- fastembed model cache moves to the central dir (shared across clients, never `%TEMP%`).
  [`embedder.py:50`](../../src/search/embedder.py#L50)

**Fallout fix + dependency/config**

- Review fix: migration script no longer imports the removed `DATABASE_URL` constant.
  [`migrate_add_bug_reports.py:23`](../../scripts/migrate_add_bug_reports.py#L23)

- `platformdirs` added to runtime deps and the pre-commit mypy hook (project rule).
  [`pyproject.toml:21`](../../pyproject.toml#L21) · [`.pre-commit-config.yaml:24`](../../.pre-commit-config.yaml#L24)

- `.env.example` full cleanup: central defaults, `PLANESWALKER_DATA_DIR`, legacy block removed.
  [`.env.example:8`](../../.env.example#L8)

**Tests (peripherals)**

- The I/O matrix: override / platformdirs default / blank / relative / nesting / URL forms.
  [`test_paths.py:9`](../../tests/unit/test_paths.py#L9)

- Regression: empty `CARDS_DATABASE_URL` keeps sync and async on the same central file.
  [`test_connection.py:125`](../../tests/unit/search/test_connection.py#L125)
