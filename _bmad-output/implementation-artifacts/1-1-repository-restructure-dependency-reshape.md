# Story 1.1: Repository Restructure & Dependency Reshape

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want the repo reorganized around the MCP-server architecture with a lean core dependency set,
so that agent/UI code is archived out of the active build and the new server/search packages have a home.

## Acceptance Criteria

> Source: [epics.md#Story-1.1](../planning-artifacts/epics.md) (BDD as authored), with implementation-critical clarifications folded in from analysis. **All five must hold simultaneously.**

**AC1 — Archive agent + UI to `legacy/`**
- **Given** the current `src/agent` and `src/ui` trees
- **When** the restructure runs
- **Then** they move to `legacy/agent/` and `legacy/ui/` (use `git mv` to preserve history)
- **And** build/test/lint config excludes `legacy/` from the active build, the active pytest run, ruff, and `mypy --strict`.

**AC2 — Dependency reshape in `pyproject.toml`**
- **Given** `pyproject.toml`
- **When** dependencies are reshaped
- **Then** `pydantic-ai` and `chainlit` move out of `[project.dependencies]` into an **optional `legacy` dependency group** (not installed by a default `uv sync`)
- **And** `mcp`, `sqlite-vec`, and `fastembed` are added to core `[project.dependencies]`.

**AC3 — New packages scaffolded**
- **Given** the new architecture
- **When** packages are scaffolded
- **Then** `src/mcp_server/__init__.py` and `src/search/__init__.py` exist (each with a one-line module docstring) and **import cleanly** (`python -c "import src.mcp_server, src.search"` succeeds).

**AC4 — Lean core install + no core regressions (Windows)**
- **Given** a fresh `uv sync` of the **core (default) group** on Windows
- **When** installed
- **Then** it succeeds **without** pulling `pydantic-ai`/`chainlit` (NFR5)
- **And** existing `tests/unit` (and `tests/integration`) for **`data` and `logic` still pass** with that core-only environment (NFR7).

**AC5 (implied, non-negotiable) — Legacy installs on demand**
- **Given** the `legacy` dependency group
- **When** `uv sync --group legacy` runs
- **Then** `pydantic-ai` + `chainlit` install, so the archived code remains runnable for reference.

## Tasks / Subtasks

- [ ] **Task 1 — Archive `src/agent` + `src/ui` → `legacy/`** (AC: 1)
  - [ ] `git mv src/agent legacy/agent` and `git mv src/ui legacy/ui` (preserve history; do **not** delete + recreate).
  - [ ] Rewrite intra-legacy absolute imports so the archived tree stays internally coherent: `src.agent` → `legacy.agent`, `src.ui` → `legacy.ui`. **Leave `from src.data …` and `from src.logic …` imports unchanged** — those packages stay in `src/`. (See Dev Notes → "Import-path rewrite map".)
  - [ ] Do **not** touch `src/data/` or `src/logic/` contents — they are the reusable core and stay put, behavior unchanged.
- [ ] **Task 2 — Reshape `pyproject.toml` dependencies** (AC: 2, 5)
  - [ ] Remove `pydantic-ai` and `chainlit` from `[project.dependencies]`.
  - [ ] Add `mcp`, `sqlite-vec`, `fastembed` to `[project.dependencies]` (recommended floors in Dev Notes → "Latest tech / versions").
  - [ ] Add a PEP 735 `[dependency-groups]` table with `legacy = ["pydantic-ai>=1.0.17", "chainlit>=2.8.3"]`.
  - [ ] Run `uv sync` (regenerates `uv.lock`); then `uv sync --group legacy` to confirm AC5. Commit the updated `uv.lock`.
- [ ] **Task 3 — Scaffold `src/mcp_server/` and `src/search/`** (AC: 3)
  - [ ] Create `src/mcp_server/__init__.py` and `src/search/__init__.py`, each with only a one-line module docstring (no premature code — tools/embedder land in stories 1.3 / 2.1).
  - [ ] Verify `uv run python -c "import src.mcp_server, src.search"` exits 0.
- [ ] **Task 4 — Exclude `legacy/` from build, lint, type-check** (AC: 1, 4)
  - [ ] `[tool.hatch.build.targets.wheel] packages = ["src"]` already excludes `legacy/` — confirm and leave as-is (this is what "excluded from build" means).
  - [ ] Add `legacy` to ruff's excludes (`[tool.ruff] extend-exclude = ["legacy"]`) so archived code isn't linted/auto-fixed.
  - [ ] mypy pre-commit hook uses `files: ^src/` — moving to `legacy/` removes it from scope automatically. Update the stale `[[tool.mypy.overrides]] module = "src.ui.*"` block (the `src.ui` path no longer exists) — remove it (or repoint to `legacy.*` and exclude legacy from mypy).
  - [ ] Optional cleanup: drop `pydantic-ai` from `.pre-commit-config.yaml` mypy `additional_dependencies` (no `src/` code imports it after the move). See Dev Notes.
- [ ] **Task 5 — Relocate/exclude legacy tests + fix shared conftests** (AC: 1, 4) — **highest-risk task; see "Test-collection landmines"**
  - [ ] Fix `tests/conftest.py`: it imports `from src.agent.core import ConversationSessionManager` at module level — this breaks collection of the **entire** suite once agent moves. Remove that import and the `mock_session_manager` fixture (relocate to a legacy conftest).
  - [ ] Fix `tests/integration/conftest.py`: it does `import chainlit as cl` at module level — this breaks collection of **all** `tests/integration/*` (including `tests/integration/data/`) once chainlit leaves core. Remove the chainlit import + its mock fixtures (`mock_user_session`, `mock_action`, `action_message`) and relocate them to a legacy conftest.
  - [ ] Relocate the legacy test trees so the active `tests/` tree holds only core (data/logic/mcp/search) tests: move `tests/unit/agent`, `tests/unit/ui`, `tests/integration/agent`, `tests/integration/ui` → under `legacy/tests/` (mirror the package layout) via `git mv`. Put the relocated agent/UI fixtures in `legacy/tests/conftest.py`. *(Alternative if you prefer keeping them in-tree: add `--ignore` entries / `collect_ignore_glob` — but moving is cleaner and matches "legacy tests excluded from the active suite".)*
  - [ ] Confirm `testpaths = ["tests"]` plus the relocation means `legacy/tests` is never collected by the active run.
- [ ] **Task 6 — Verify (run the commands, capture output)** (AC: 3, 4, 5)
  - [ ] `uv sync` → succeeds; `uv pip list` shows **no** `pydantic-ai`/`chainlit`.
  - [ ] `uv run python -c "import src.mcp_server, src.search"` → exit 0.
  - [ ] `uv run pytest tests/` → core data/logic/setup tests pass; **0 collection errors**.
  - [ ] `uv run ruff check .` and `uv run mypy src/` → clean (legacy excluded).
  - [ ] `uv sync --group legacy` → installs pydantic-ai + chainlit (AC5).
- [ ] **Task 7 — Non-blocking follow-ups (note, don't let them fail the build)** (AC: 1)
  - [ ] `scripts/test_agent.py` and `scripts/manage_bug_reports.py` import the agent — they will have stale imports after the move. They are dev utilities (not in `testpaths`, not in the wheel). Repoint their imports to `legacy.*` if quick, otherwise note them as legacy-bound. They must **not** break `pytest` (they aren't collected) or `uv sync`.
  - [ ] `examples/advanced_search/03_agent_natural_language.py`, `docs/*.md`, `README.md` reference `src.agent`/`src.ui` — documentation/example drift; update opportunistically, out of strict AC scope.

## Dev Notes

### What this story is — and is NOT

- **IS:** a brownfield *move + config* story. Relocate `src/agent`+`src/ui` to `legacy/`, reshape deps, scaffold two empty packages, keep the core data/logic test suite green on a lean install.
- **IS NOT:** building any MCP tool, server entry point, `ConnectionFactory`, embedder, `.mcp.json`, or `sqlite-vec` wiring. Those are stories 1.2, 1.3, and Epic 2. `src/mcp_server/__init__.py` and `src/search/__init__.py` are **empty stubs** (docstring only). Resist scaffolding more — premature code here will collide with later stories.

### Current state of the code being moved (read before editing)

The codebase uses **absolute `src.`-rooted imports everywhere** (the installed package is literally `src` — `[tool.hatch.build.targets.wheel] packages = ["src"]`). Confirmed import topology:

- **`src/data` and `src/logic` import NOTHING from `agent`/`ui`** (verified by grep) — they are clean, agent-agnostic, and stay in `src/`. The "core facade" mentioned in the spec is **not needed for this story** (no agent-specific coupling was found in data/logic). [Source: design spec §4 "extract as we hit coupling, not preemptively"]
- **`src/ui` imports `src/agent`** and **`src/agent/tools` imports `src/ui.formatters`** — agent↔ui are mutually coupled, which is why they move together as one `legacy/` unit. Example: `src/agent/tools/card_lookup.py` → `from src.ui.formatters import …`; `src/ui/app.py` → `from src.agent.core import …`.
- Legacy modules also import the core: `from src.data.repositories.card import FormatFilter, GamesFilter`, etc. **Keep these `src.data`/`src.logic` imports as-is** when you move the files.

### Import-path rewrite map (inside `legacy/` only)

| Found in moved files | Rewrite to | Keep unchanged |
|---|---|---|
| `from src.agent…` / `import src.agent…` | `from legacy.agent…` / `import legacy.agent…` | — |
| `from src.ui…` / `import src.ui…` | `from legacy.ui…` / `import legacy.ui…` | — |
| `from src.data…`, `from src.logic…` | *(no change)* | ✅ stays `src.*` |

> `legacy/` is **reference-only / excluded from the active build & tests** [spec §4, D3]. Rewriting the intra-legacy imports keeps the archive internally coherent (and runnable under `uv sync --group legacy`); it is recommended, not strictly required by an AC. Do **not** add `legacy` to the wheel `packages` list — it must stay out of the built package.

### Test-collection landmines (this is where AC4 is won or lost)

A core-only `uv sync` removes `pydantic_ai` and `chainlit` from the environment. pytest imports every `conftest.py` and every collected test module at collection time, so any **module-level** import of a removed package or a moved module aborts collection — potentially taking the passing data/logic tests down with it. Exhaustively verified module-level offenders:

1. **`tests/conftest.py` (root)** → `from src.agent.core import ConversationSessionManager`. Root conftest loads for the **whole** session → breaks **all** tests. **Fix:** delete the import + `mock_session_manager` fixture (move to `legacy/tests/conftest.py`).
2. **`tests/integration/conftest.py`** → `import chainlit as cl`. Applies to **all** `tests/integration/*`, including `tests/integration/data/` → breaks core integration tests. **Fix:** remove the chainlit import + the three UI mock fixtures; relocate to legacy.
3. **Legacy test trees** (`tests/unit/agent/**`, `tests/unit/ui/**`, `tests/integration/agent/**`, `tests/integration/ui/**`) — all import `chainlit`/`pydantic_ai`/moved modules. **Fix:** relocate under `legacy/tests/` (preferred) or `--ignore` them.

**Core tests that must survive and pass** (no bad imports — verified): `tests/unit/data/**`, `tests/unit/logic/**`, `tests/integration/data/**`, `tests/test_setup.py`, `tests/fixtures/**`.

### Dependency reshape specifics

- **uv mechanism — use PEP 735 `[dependency-groups]`, not extras.** Dependency groups are *invisible to consumers of the package* and exist only for project work, which matches "archived/reference-only legacy." Only the `dev` group is synced by default; a named `legacy` group is **not** installed unless requested → satisfies AC4. Install on demand with `uv sync --group legacy` (AC5). [Source: PEP 735; uv docs — Managing dependencies]
  ```toml
  [dependency-groups]
  legacy = [
      "pydantic-ai>=1.0.17",
      "chainlit>=2.8.3",
  ]
  ```
  *(Alternative: `[project.optional-dependencies] legacy = […]` works too but publishes the extra in package metadata; prefer dependency-groups for a reference-only archive.)*
- **Existing `[tool.uv] dev-dependencies`** is uv's pre-PEP-735 field; uv merges it into the `dev` group, so it coexists fine. Optional: migrate it into `[dependency-groups].dev` for consistency — not required by this story.
- **Scope discipline:** AC2 names exactly `pydantic-ai` + `chainlit` to move. Leave `openai`, `anthropic`, `logfire`, `asyncpg`, etc. in core for this story even though some are agent-bound — moving them is a separate cleanup, out of scope here. Don't expand the blast radius.
- **`sqlite-vec` on Windows:** spec §10 flags Windows extension-loading as an open risk; the project's RAG de-risk already returned **GO** (v0.1.9 loads on CPython 3.12.13 / SQLite 3.50.4 / Windows via stdlib `sqlite3`, no fallback). For *this* story you only need the wheel to **install** under `uv` on Windows — AC4's `uv sync` is exactly that check. Actual extension loading is exercised in Story 1.2. [Source: [project-context.md](../project-context.md) "Verified platform envelope"; design spec §10]
- **`fastembed`** pulls `onnxruntime` (sizable) and downloads the model on first *use* — but story 1.1 only installs it; no model download occurs here. Pinning `FASTEMBED_CACHE_DIR` is a Story 2.1 concern.

### Latest tech / versions (recommended floors)

| Package | Recommended specifier | Notes |
|---|---|---|
| `mcp` | `>=1.27.0` | Official MCP Python SDK; **FastMCP is bundled** — import `from mcp.server.fastmcp import FastMCP`. **Do NOT add the standalone `fastmcp` package** (PrefectHQ, v3.x) — the project decision is the lean bundled FastMCP. [Source: [pypi.org/project/mcp](https://pypi.org/project/mcp/); design spec D1/D7; [project-context.md](../project-context.md)] |
| `sqlite-vec` | `>=0.1.9` | Latest is 0.1.9; this is the exact version validated GO on Windows in the RAG de-risk. [Source: [pypi.org/project/sqlite-vec](https://pypi.org/project/sqlite-vec/)] |
| `fastembed` | `>=0.7.1` | ONNX runtime; default model `BAAI/bge-small-en-v1.5` (384-dim), no PyTorch. [Source: [pypi.org/project/fastembed](https://libraries.io/pypi/fastembed); design spec D2/D6] |

> These are floors; let `uv` resolve exact versions and commit the resulting `uv.lock`. Scaffolds are empty, so no new types are imported yet — you do **not** need to add `mcp`/`sqlite-vec`/`fastembed` to the mypy pre-commit `additional_dependencies` in this story (do that when 1.2/1.3 import them).

### Project conventions to honor (from project-context.md)

- **`uv` only** — `uv run …`, `uv add …`, `uv sync …`; never bare `pip`. Build backend hatchling, `src/` layout.
- Each new `src/` file needs a **module docstring** (one-line summary) — applies to the two new `__init__.py` stubs.
- **pre-commit gates every commit** (ruff lint+format, then `mypy --strict` over `^src/`). Don't bypass hooks; fix issues. Install via `uv run pre-commit install`.
- **Conventional Commits** on feature branch `feat/mcp-server-architecture` (already checked out). Suggested commit: `refactor: archive agent+ui to legacy, reshape deps, scaffold mcp_server+search`.
- `mypy --strict` is enforced; `tests.*` is exempt; the old `src.ui.*` mypy override is now stale (see Task 4).

### Recent git context

Recent commits are all planning/docs (`docs: add MCP-server architecture pivot design`, `feat: complete Letta migration planning`). **No prior implementation commits on this branch** — this story is the first code-touching work of the MCP pivot. There is no prior story to inherit patterns from; establish the clean `src/` (core) vs `legacy/` (archive) split correctly here, since stories 1.2→1.6 build on it.

### Project Structure Notes

Target layout after this story:

```
src/
  data/          # unchanged — reusable core (repositories return Pydantic schemas)
  logic/         # unchanged — mana curve, synergy, deck validator
  mcp_server/    # NEW — __init__.py (docstring only) — FastMCP server lands in 1.3
  search/        # NEW — __init__.py (docstring only) — embedder/sqlite-vec land in Epic 2
legacy/
  agent/         # moved from src/agent (reference only, excluded from build/tests/lint)
  ui/            # moved from src/ui   (reference only, excluded from build/tests/lint)
  tests/         # moved agent/ui test trees + their conftest fixtures
tests/
  unit/data, unit/logic, integration/data, test_setup.py, fixtures/  # active core suite
```

- **Alignment:** matches design spec §4 restructure table exactly (archive agent+ui; keep data+logic; add mcp_server+search). [Source: design spec §4]
- **Variance / decision to record:** `legacy/` is a **top-level sibling of `src/`** (not `src/legacy/`), so it is naturally outside the `packages = ["src"]` wheel and the `^src/` mypy scope. This is intentional and is the mechanism that satisfies "excluded from build/type-check." Relocating the agent/ui *tests* alongside `legacy/` (rather than `--ignore`) is a judgment call made to keep the active `tests/` tree purely core — the alternative (in-tree `--ignore`) is acceptable if you document it.

### References

- [epics.md — Epic 1 / Story 1.1](../planning-artifacts/epics.md) — user story, ACs, FR/NFR coverage (FR1 enabling work; NFR5, NFR7).
- [design spec §4 — Repository Restructure](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md) — archive table, dependency reshape, core facade guidance (D1, D3).
- [design spec §8 — Testing](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md) — data/logic tests stay valid; legacy tests excluded.
- [project-context.md](../project-context.md) — `uv`-only, mypy-strict, layer boundaries, verified Windows RAG envelope, "build toward MCP not the superseded Letta/PydanticAI plan".
- [pyproject.toml](../../pyproject.toml), [.pre-commit-config.yaml](../../.pre-commit-config.yaml), [tests/conftest.py](../../tests/conftest.py), [tests/integration/conftest.py](../../tests/integration/conftest.py) — the files this story edits.
- PEP 735 dependency groups + [uv Managing dependencies](https://docs.astral.sh/uv/concepts/projects/dependencies/) — `[dependency-groups]`, `--group`, default-group semantics.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
