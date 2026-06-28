---
project_name: 'Artificial-Planeswalker'
user_name: 'Brad'
date: '2026-06-20'
sections_completed:
  ['technology_stack', 'language_rules', 'framework_rules', 'testing_rules', 'quality_rules', 'workflow_rules', 'anti_patterns']
existing_patterns_found: 14
status: 'complete'
rule_count: 56
optimized_for_llm: true
---

# Project Context for AI Agents

_This file contains critical rules and patterns that AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

> ⚠️ **Project is mid-pivot (as of 2026-06-20).** The codebase on disk is still the
> original **PydanticAI + Chainlit** monolith, but the **design of record** is the
> **MCP-server architecture** (`docs/architecture.md`,
> epics in `_bmad-output/planning-artifacts/epics.md`).
> `planning-artifacts/architecture.md` (Letta-first) and `planning-artifacts/prd.md` are **SUPERSEDED — do not implement from them.**
> Net effect for agents: **build new capability as MCP tools; treat `src/agent` + `src/ui`
> as legacy slated for `legacy/`.**

**Runtime & tooling**
- **Python `>=3.12`** (target `py312`). Package/dependency manager: **`uv`** (use `uv run …`, `uv add …` — never bare `pip`). Build backend: **hatchling**, packaging `src/`.

**Core dependencies (current code)**
- `pydantic-ai>=1.0.17` — agent framework *(legacy-bound)*
- `chainlit>=2.8.3` — conversational UI *(legacy-bound)*
- `sqlalchemy[asyncio]>=2.0.44` + `aiosqlite>=0.21.0` — async SQLite ORM
- `pydantic` (v2) + `pydantic-settings>=2.0.0` — schemas & env config
- `openai>=1.0.0` (OpenRouter) + `anthropic>=0.69.0` (native) — LLM providers
- `logfire>=3.0.0` — observability (optional, no-op when disabled)
- `tenacity>=8.0.0` — retry/backoff · `httpx>=0.28.1` · `ijson>=3.3.0` (streaming Scryfall JSON) · `asyncpg>=0.30.0` (future Postgres)

**Incoming dependencies (Phase-1 MCP pivot — add these for new work)**
- **`mcp` / FastMCP** — MCP server framework (D1, D7; stdio transport, pluggable to HTTP/SSE)
- **`sqlite-vec`** — vector virtual table inside the *same* SQLite file (D2)
- **`fastembed`** — local ONNX embeddings, model **`bge-small-en-v1.5`** (384-dim, no PyTorch) (D2, D6)
- Plan: move `pydantic-ai` + `chainlit` into an optional **`legacy`** dependency group.

**Dev toolchain:** `ruff>=0.14.0`, `mypy>=1.18.2` (strict), `pre-commit>=4.3.0`, `pytest>=8.4.2` + `pytest-asyncio>=1.2.0` + `pytest-cov>=7.0.0`.

**Verified platform envelope (RAG de-risk, GO):** CPython 3.12.13 / SQLite 3.50.4 / Windows / uv 0.11.7 — stdlib `sqlite3.enable_load_extension` is available, `sqlite-vec` v0.1.9 loads with no fallback driver; `fastembed` ~3 ms/query. `apsw` is contingency-only.

## Critical Implementation Rules

### Language-Specific Rules (Python 3.12)

- **`mypy --strict` is enforced** (pre-commit + CI gate). Every function in `src/` needs full
  type hints; `disallow_untyped_defs = true`. Overrides: `tests.*` may be untyped; `src.ui.*`
  relaxes `disallow_untyped_calls`/`disallow_untyped_decorators` (Chainlit lacks stubs).
- **Use modern 3.12 syntax** (ruff `UP` rules auto-enforce): `X | None` not `Optional[X]`,
  `list[str]`/`dict[str, Any]` not `List`/`Dict`, built-in generics.
- **Async everywhere in `src/data` + `src/logic`.** DB access is `async`/`await` on
  `AsyncSession`; never call sync SQLAlchemy APIs. (Exception: MCP tools are **sync `def`** —
  see Framework rules — and embeddings run on CPU synchronously.)
- **Timezone-aware UTC only:** `datetime.now(UTC)` (import `UTC` from `datetime`). Never naive
  `datetime.now()` / `utcnow()`.
- **Logging, not prints, in library code:** module-level `logger = logging.getLogger(__name__)`;
  use `%`-style lazy args (`logger.info("x=%s", val)`), not f-strings, in log calls. (`print()`
  is fine only in `scripts/` and `setup.py` CLI output.)
- **Import side-effect ordering matters:** `src/data/database.py` imports all `*Model` classes
  (with `# noqa: F401`) so `Base.metadata` is fully populated before `create_all`. Keep model
  imports when touching that module.
- **`ruff` `N` (pep8-naming) is on**, but `format` is used as a parameter/field name throughout
  (MTG format) — this shadows the builtin intentionally; keep it for domain clarity.

### Framework-Specific Rules

**Layer architecture & boundaries**
- Strict import direction: **`data` → `logic` → (agent | mcp_server) → ui**. Lower layers never
  import upward. `src/data` and `src/logic` are the **reusable domain core** — keep them
  agent-agnostic and framework-free (no PydanticAI / MCP / Chainlit imports).
- **Repositories return Pydantic schemas, NEVER ORM models.** Methods end with
  `Schema.model_validate(model)` (e.g. return `Deck`, not `DeckModel`). Schemas use
  `from_attributes=True`. Callers outside `src/data` must never receive a `*Model`.

**SQLAlchemy 2.0 (async)**
- Models use **typed `Mapped[...]` + `mapped_column(...)` with dataclass init flags**
  (`init=`, `default_factory=`, `default=`). Match this style; don't hand-write `__init__`.
- Session factory uses **`expire_on_commit=False`** (prevents detached-instance errors after
  commit) with `autoflush=False`, `autocommit=False`. Don't re-enable expiry.
- Eager-load relationships explicitly with `selectinload(...)` (relationships default to
  `lazy="noload"` — lazy access returns empty, it does NOT auto-query).
- **JSON-in-Text columns** (`tags`, `color_identity`): the column is `Text` holding a JSON
  string; always read/write through the paired `*_list` property/setter (`tags_list`,
  `color_identity_list`), which handle `json.loads/dumps` and None. Never assign raw JSON
  strings to the base column.
- **Transaction discipline in write methods:** wrap in try/except, `await session.commit()` +
  `refresh()` on success, and **`await session.rollback()` on `IntegrityError`/`DatabaseError`**
  before re-raising. Repositories raise DB exceptions; the tool/UI layer converts them to
  user-facing messages.
- Use the **`_UNSET` sentinel** (not `None`) to distinguish "argument omitted" from
  "explicitly clear to NULL" in update methods.
- Color codes are always sorted in **WUBRG order** (`["W","U","B","R","G"]`).

**MCP server (Phase-1 target — `src/mcp_server`, FastMCP)**
- **Tools are stateless and self-contained (D5):** `format`/`games` are **tool parameters**;
  "active deck" is a client-supplied **`deck_id`** — no per-session server state. The old
  `set_format_filter` / `set_games_filter` / `toggle_auto_feedback` session tools are dropped.
- **Define tools as sync `def`** — FastMCP runs them in a threadpool. Use **WAL mode** and
  **one SQLite connection per worker thread**; the embedding model is a **process singleton**.
- Tools wrap the existing repositories/validators directly; they **return structured results**
  (not the legacy HTML-blob strings the PydanticAI prompt required).
- Port tool catalog 1:1 from `src/agent/tools` + two new search tools (`semantic_search_cards`,
  `find_similar_cards`). Keep transport pluggable (stdio now → HTTP/SSE later, D7).

**RAG / semantic search (Phase-1 target — `src/search`)**
- Vectors live in a **`sqlite-vec` virtual table `card_vec` in the same DB file**, keyed by
  `card_id` so vectors JOIN to relational rows. Embedded text per card =
  `name + type_line + mana_cost + oracle_text + keywords`.
- Carry the **six de-risk deltas**: (1) a `ConnectionFactory` port that enables
  `load_extension` + calls `sqlite_vec.load`; (2) an `Embedder` port (fastembed singleton);
  (3) pin **`FASTEMBED_CACHE_DIR`** to a persistent path (default is a volatile temp dir);
  (4) `card_vec` metadata cols `mana_value` + `color_{w,u,b,r,g}` for pre-filter, legality/display
  via JOIN; (5) **every KNN query needs `k`/`LIMIT`**, over-fetch `k` then JOIN-filter;
  (6) fastembed ships the **quantized** model — guard recall with a RAG sanity eval.
- **The `card_vec` index is a build prerequisite, never committed.** Build it with `uv run python
  scripts/build_card_embeddings.py` (idempotent/incremental); a fresh checkout / CI has no index.
  `semantic_search_cards` / `find_similar_cards` detect a missing/empty index (via
  `query.index_is_populated`) and return a graceful `status="index_unavailable"` build-the-index
  hint — never a raw `OperationalError`. **Checkpoint the WAL before any file-copy backup**
  (`PRAGMA wal_checkpoint(TRUNCATE)`); a model/dimension change means rebuilding `card_vec` (NFR10).
- **`limit` on the semantic tools is capped at 50** (`_MAX_LIMIT`), kept under `hybrid_search`'s
  `over_fetch_k` (200) so the over-fetch can't be starved; `limit > 50` returns `status="invalid"`.

**Legacy layers (`src/agent` PydanticAI, `src/ui` Chainlit)**
- Slated for `legacy/`; modify only for maintenance. The PydanticAI `SYSTEM_PROMPT` forces
  verbatim pass-through of trusted-HTML tool output and "never add cards without explicit user
  intent" — preserve that contract if you touch it. Provider selection: native Anthropic for
  Claude models when `ANTHROPIC_API_KEY` is set, else OpenRouter (`anthropic/` prefix toggled
  by `_normalize_model_name`).

### Testing Rules

- **pytest config is in `pyproject.toml`** (`[tool.pytest.ini_options]`). Key settings:
  `asyncio_mode = "auto"` (write `async def test_...` directly — **no `@pytest.mark.asyncio`
  needed**), `--strict-markers`, `--tb=short`, verbose.
- **Test layout mirrors `src/`:** `tests/unit/<layer>/...` (fast, no I/O) and
  `tests/integration/<layer>/...` (DB, API, Chainlit). New MCP work goes in
  `tests/integration/test_mcp_tools.py` (drive each tool via an in-process MCP client).
- **`integration` marker:** mark integration/network tests so they can be deselected
  (`-m "not integration"`). Tests that need `OPENROUTER_API_KEY` must be marked.
- **Naming:** files `test_*.py`, classes `Test*`, functions `test_*`.
- **Fixtures:** shared agent fixtures in `tests/conftest.py`; Chainlit/UI mocks
  (`mock_user_session`, `mock_action`, `action_message`) in `tests/integration/conftest.py`.
  Reuse these rather than re-mocking `cl.user_session`.
- **`tests.*` is exempt from `mypy --strict`** — but still follow naming/ruff rules.
- **RAG regression guard:** semantic-search work must include a small `query → expected card in
  top-K` sanity eval (the quantized embedding model can silently degrade recall).
- **`legacy/` tests are excluded from the active suite** once the restructure lands — don't add
  new coverage there.
- Coverage available via `uv run pytest --cov=src` (no hard threshold enforced).

### Code Quality & Style Rules

- **Ruff is the linter + formatter** (`line-length = 100`, `target-version = py312`). Lint
  rule sets: `E, F, I, W` (pycodestyle/pyflakes), `I` (isort), `N` (pep8-naming),
  `UP` (pyupgrade). Run `uv run ruff check . --fix` and `uv run ruff format .`.
- **pre-commit gates every commit:** ruff (lint + format), then `mypy --strict
  --ignore-missing-imports` over `^src/`. Install with `uv run pre-commit install`. **Don't
  bypass hooks** — fix the issue. If you add a runtime dep that mypy needs to resolve types,
  also add it to `.pre-commit-config.yaml`'s mypy `additional_dependencies`.
- **Imports:** isort/ruff-ordered (stdlib → third-party → first-party `src.*`); absolute
  imports for cross-package, relative (`.config`, `.errors`) within a package. Real circular
  imports are broken with **function-local imports** (see `create_agent` tool registration) —
  use sparingly and comment why.
- **Naming:** `snake_case` functions/variables/modules, `PascalCase` classes, `UPPER_SNAKE`
  constants. DB tables/columns are `snake_case`. ORM models are suffixed `*Model`
  (`DeckModel`); their Pydantic counterparts are unsuffixed (`Deck`).
- **Docstrings: Google style** (`Args:` / `Returns:` / `Raises:` / `Example:`) on public
  functions, classes, and tools. This is the established convention across the codebase —
  match it; for MCP tools the docstring doubles as the LLM-facing tool description.
- **Module docstrings** required at the top of each `src/` file (one-line summary of purpose).
- Prefer **early returns and guard clauses** over deep nesting (matches existing style).

### Development Workflow Rules

- **Environment / config:** secrets and settings come from `.env` (created from `.env.example`
  via `setup.py`), loaded by `pydantic-settings`. Never hardcode keys. Required:
  `OPENROUTER_API_KEY`; optional: `ANTHROPIC_API_KEY`, `AGENT_MODEL`, `AGENT_TEMPERATURE`,
  `AGENT_MAX_TOKENS`, Logfire vars.
- **DB URL env var is `CARDS_DATABASE_URL`, NOT `DATABASE_URL`** — the standard name is
  deliberately avoided because **Chainlit hijacks `DATABASE_URL`**. Default
  `sqlite+aiosqlite:///./data/cards.db`. Keep this rename.
- **Data files live in `./data/`** (`cards.db`, decks). The one-time Scryfall import is heavy
  (~60k cards); use `scripts/import_scryfall_data.py` / `setup.py`, don't re-import casually.
- **Schema changes:** no Alembic — migrations are hand-written scripts in `scripts/`
  (`migrate_*.py`); tables are created via `Base.metadata.create_all` in `init_database`. Add a
  migration script for changes to existing tables.
- **Run commands via uv:** app `uv run chainlit run src/ui/app.py [-w]` (legacy);
  tests `uv run pytest`; quality `uv run ruff …` / `uv run mypy src/`.
- **Git:** feature branches off `master` (current: `feat/mcp-server-architecture`).
  Commit messages follow **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`).
  Ensure tests pass and pre-commit hooks succeed before a PR.
- **Planning artifacts are the source of truth** for *what* to build: the design of record in
  `docs/architecture.md`, epics/research in `_bmad-output/planning-artifacts/`. Check the
  latest dated spec — older planning docs may be superseded (see the banner in this file's
  Technology Stack section).

### Critical Don't-Miss Rules (Anti-Patterns & Gotchas)

- **Don't implement from `architecture.md` or `prd.md`** — both are SUPERSEDED. The active
  direction is the MCP-server design spec + `epics.md`. When in doubt, prefer the newest dated
  artifact and ask.
- **Don't leak ORM objects out of `src/data`.** Returning a `*Model` instead of its Pydantic
  schema breaks the layer contract and triggers detached-instance / lazy-load surprises.
- **Don't rely on lazy relationship loading.** `deck_cards` is `lazy="noload"`; without
  `selectinload(...)` it reads as empty rather than querying — leading to silent "0 cards" bugs.
- **Don't assign raw JSON to `tags` / `color_identity`** — go through the `*_list` setters, or
  you'll store a non-JSON string the readers can't parse.
- **Don't commit without rollback-on-error in repo writes** — a failed commit left in a
  transaction contaminates the shared `AsyncSession` for every later operation in that request.
- **Don't reintroduce per-session server state in MCP tools.** Format/games/active-deck are
  caller-supplied parameters (D5); session state belongs to the *client*, not the server.
- **Don't block the event loop / mismatch sync vs async:** `src/data`/`src/logic` are async;
  MCP tools are sync `def` (threadpooled) with their own per-thread SQLite connection + WAL.
  Don't `await` inside a sync tool or share one connection across threads.
- **Don't forget `k`/`LIMIT` on a `sqlite-vec` KNN query** — an unbounded vector scan is a
  performance cliff. Over-fetch `k`, then JOIN-filter on relational predicates.
- **Don't let `FASTEMBED_CACHE_DIR` default** — it points at a volatile temp dir, forcing model
  re-downloads. Pin it to a persistent path.
- **Don't escape/rewrite legacy card-tool HTML output** if working in `src/agent`/`src/ui` —
  the PydanticAI prompt requires verbatim pass-through of the trusted HTML for card rendering.
- **Don't auto-add cards to a deck** in agent flows without explicit user intent — analysis
  (mana curve, synergy) is observational only; this is a hard behavioral contract.
- **Security:** keys only via `.env`; never log full API keys or commit `.env`. `report_bug`
  writes user-supplied content — treat it as untrusted input.

---

## Usage Guidelines

**For AI Agents:**

- Read this file before implementing any code in this repo.
- Follow ALL rules exactly as documented; when in doubt, prefer the more restrictive option.
- This project is mid-pivot — confirm you're building toward the **MCP-server** direction, not
  the superseded Letta/PydanticAI plan, before starting new capability work.
- Propose an update to this file when a new durable pattern emerges.

**For Humans:**

- Keep this file lean and focused on what agents would otherwise miss.
- Update when the technology stack or architecture phase changes (e.g. when the `legacy/`
  restructure lands, or Phase 2/3 begins).
- Review periodically; remove rules that become obvious or stale.

Last Updated: 2026-06-20
