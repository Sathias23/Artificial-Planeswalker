<!-- bmad:context -->
<!-- Verified 2026-09-06 against d457a6d51adc32cfc9c1c7871881e8b34dcac56e. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## Artificial-Planeswalker

A local, stateless MCP server that gives an LLM Magic: The Gathering deckbuilding tools over a Scryfall card database, plus a read-only companion web app (FastAPI backend, React/Vite UI) that shows the active deck in a browser. Python 3.12+ run through `uv`, SQLAlchemy async over SQLite, `sqlite-vec` + `fastembed` for semantic search. Design of record is the MCP pivot design in `docs/architecture.md` (its "today" paragraph describes the pre-pivot state; the code is the pivot's result); the companion's `AD-n` decisions are in `_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md`; active specs in `_bmad-output/specs/`; contributor workflow, gate table and generated-artifact table in `CONTRIBUTING.md`.

## Policy

- Code changes branch off `master` and land by PR; only standalone docs and planning artifacts commit straight to `master`.
- Never hand-edit `src/companion/app/static/`, `plugin/`, `ui/src/api/types.d.ts` or `ui/src/api/openapi.json`; regenerate them (`CONTRIBUTING.md`, Generated artifacts) and commit what the tools emit. After any change under `src/`, the five shipped skills, `pyproject.toml`, `uv.lock`, `README.md`, `LICENSE`, `NOTICE` or `scripts/build_plugin.py`, run `uv run python -m scripts.build_plugin` and commit the result; CI fails on drift. A backend route or Pydantic model change needs `npm run gen:api` from `ui/`; `npm run gen:types` alone re-emits types from the committed `ui/src/api/openapi.json`.
- Never bypass pre-commit; fix the underlying issue. A new runtime dependency that mypy must resolve also goes into the mypy `additional_dependencies` list in `.pre-commit-config.yaml`.
- Nothing under `src/companion/` writes to the database: no repository write method, session mutation, DML construct or importer import (AD-2); `src/mcp_server/` is the sole writer. `src/mcp_server/` may import the companion leaf (`contracts`, `discovery`, `client`) but never `src/companion/app/` (AD-3). Both rules are AST-enforced by `tests/unit/companion/test_import_boundary.py`.
- `src/viewer/` and the `view_deck` tool are frozen (AD-15): new display capability goes in the companion app, never there.
- Analysis tools (legality, curve, synergy, assessment) are observational and never mutate a deck as a side effect; deck changes need explicit user intent through the deck-management tools.
- Import direction is data, then logic, then mcp_server; `src/data/` and `src/logic/` stay framework-free.
- Behaviour is tested through real entry points, never by scanning source or documentation text; the AST guards under `tests/unit/companion/` are the sanctioned exception, for architectural invariants only.
- No secrets or API key are required (the server makes no LLM calls); settings come from environment variables documented in `.env.example` (`PLANESWALKER_DATA_DIR` relocates the data directory). Never commit a .env file.

## Where things are

- MCP server entry: `python -m src.mcp_server` (JSON-RPC on stdout, diagnostics on stderr); `src/mcp_server/server.py` registers the tools, one module per tool under `src/mcp_server/tools/`. stdio is the only supported transport; leave `MCP_TRANSPORT` at its default and do not reintroduce an HTTP transport. The `companion` subcommand in `src/mcp_server/__main__.py` runs the backend in `src/companion/app/`.
- Data layer `src/data/` (models, repositories, importers, schemas); search `src/search/` (sqlite-vec index and fastembed embedder); analysis `src/logic/` (validator, curve, synergy, assessment); `src/viewer/` is the frozen one-shot HTML deck render.
- Companion UI source `ui/`; the built bundle is committed at `src/companion/app/static/`. Deep docs: `docs/companion.md`, `docs/plugin-structure.md`.
- The five shipped skills under `.claude/skills/` (magic-deckbuilding, mana-curve-analysis, synergy-discovery, format-legality, companion) enumerate MCP tool names and parameters and nothing gates them; adding, renaming or extending a tool means editing them too, since a past closed-set extension missed them.
- Schema changes: no Alembic; add a hand-written migration script in `scripts/` (named migrate_*.py) alongside the model change. Data repairs to an existing database that need no DDL ride the engine's connect hook in `src/data/database.py` instead, as the NOCASE indexes and the orphan `deck_cards` sweep do.
- `_bmad/`, `.worktrees/` and the bmad-* skills under `.claude/skills/` are untracked dev tooling kept on disk; process artifacts live on the orphan `process` branch.

## Running and verifying

- Python gate before pushing: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, `uv run pytest`. CI runs the `--platform win32` pass as well because `src/companion/app/singleton.py` has a different implementation per platform (`msvcrt` vs `fcntl`); one platform's run misses the other half.
- UI gate, run from `ui/`: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`, `npm run test:gates`, `npm run build`, `npm run gen:types`. `npm run lint` does not include Prettier; run `format:check` before the first push (a formatting slip once reached CI and cost a full review round; a pre-commit hook now covers `ui/`).
- `asyncio_mode = "auto"` is set in `pyproject.toml`: write `async def test_...` directly, no asyncio marker. Mark DB and network tests `integration`; CI's `quality` job runs `-m "not integration"`, and the Windows companion-integration job runs `tests/integration/companion/` by path.
- The card database and the semantic index are build prerequisites, never committed. `python setup.py` (or `uv run python scripts/import_scryfall_data.py`) builds the database, which integration tests and every card tool need; `uv run python scripts/build_card_embeddings.py` (idempotent, incremental) builds the index, and without it the semantic tools answer `status="index_unavailable"` rather than raising.
- Proving a new guard fires goes through the committed harnesses, never a hand-typed command: `uv run python -m scripts.probe_harness --expect-red '<node id>'` (Python) or `uv run python -m scripts.vitest_probe_harness --control` first, then `--expect-total N --expect-red '<substring>'` (frontend, run warm). Paste the harness proof line into the record, never a hand-transcribed count.
- The database URL variable is `CARDS_DATABASE_URL`, not `DATABASE_URL`; pin `FASTEMBED_CACHE_DIR` to a persistent path or the model re-downloads from a temp dir.

## Conventions that differ from defaults

- Repositories return Pydantic schemas (`Deck`), never ORM models (`DeckModel`); write methods commit and refresh on success and roll back on `IntegrityError` / `DatabaseError` before re-raising.
- Update methods take the `_UNSET` sentinel for "argument omitted"; `None` means clear to NULL.
- Read and write the JSON-in-Text columns (`tags`, `color_identity`) through the paired `*_list` properties (`color_identity_list`), never by assigning a raw string to the base column.
- Relationships default to `lazy="noload"` (lazy access reads empty, it does not query) and the session factory sets `expire_on_commit=False`; eager-load with `selectinload`.
- Foreign keys are enforced per connection by the engine's connect hook (`PRAGMA foreign_keys = ON`), so a fixture inserting `deck_cards` seeds the deck and the card first; the repository maintains deck `color_identity` (from card `color_identity`) and `updated_at` on every card mutation, so tools never recompute them.
- Colour codes are always WUBRG-ordered; timestamps are aware UTC (`now(UTC)` from `datetime`), never naive.
- MCP tools are stateless: `format`, `games` and the active `deck_id` are caller-supplied parameters; add no per-session server state.
- Sync sqlite-vec work (semantic search, index build) runs from an `async def` tool inside `await asyncio.to_thread(...)`, acquiring its own SQLite connection inside the worker; every KNN query carries `k` / `LIMIT` (over-fetch, then JOIN-filter; `_MAX_LIMIT` is 50).
- `format` shadows the builtin as a parameter and field name on purpose (the MTG format); keep it.
- Log calls pass values as lazy %-style args (`logger.info("x=%s", v)`), never f-strings; `tests/unit/companion/test_deps.py` asserts that log records carry `args`. An MCP tool docstring is the LLM-facing tool description, so editing one changes caller behaviour.

## Known pitfalls

- A past review patch fixed one of four branches of a repeated pattern and the automated PR reviewer caught the rest; grep for the whole pattern before calling a fix done.
- fastembed ships a quantized model; a semantic-search change needs a small query-to-expected-card sanity eval or recall degrades silently.
- Reverting a planted violation with an unstaged `git checkout` once deleted a whole component; stage the tree before planting and check the revert with `git diff --exit-code <file>`.
- Keep the `# noqa: F401` model imports in `src/data/database.py`; removing one silently drops its table from `create_all`.
- Run `PRAGMA wal_checkpoint(TRUNCATE)` before any file-copy backup of the card database, or the copy misses the WAL.

<!-- /bmad:context -->
