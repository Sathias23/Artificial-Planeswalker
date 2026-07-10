# Deferred Work

## Deferred by scope-split: Kotis session plugin-improvement leads (2026-07-10)

> Source: `temp/kotis-fangkeeper-brawl.md` §"Plugin improvement leads" (live Brawl sessions
> 2026-07-05). Brad ran `bmad-quick-dev` on all 8 leads and chose **Split** at the multi-goal
> gate: leads 1 (games union) + 3 (brawl singleton) are the current run; the six below are
> deferred, each an independently shippable quick-dev run. Full observed evidence for each is in
> the source file.

- source_spec: none
  summary: Add a saboteur/combat-damage-trigger pattern to `detect_synergies` (rated the Kotis deck "low cohesion").
  evidence: Split from the 8-lead Kotis improvement intent; isolated synergy-logic change, independent of the validator/import work chosen first.
- source_spec: none
  summary: Bulk deck-import MCP tool accepting an Arena export blob (per-line resolve, per-line ok/ambiguous/not-found report).
  evidence: Split from the 8-lead Kotis improvement intent; a new standalone tool (saving the 60-card deck took ~50 `add_card_to_deck` calls, the 100-card port 75 more).
- source_spec: none
  summary: Import-time legality-snapshot sanity check for pool-superset invariants (e.g. Pym Particles `standardbrawl: legal` but `brawl: not_legal` is impossible).
  evidence: Split from the 8-lead Kotis improvement intent; import-script validation, standalone. Natural pairing with the games-union import work if the import script is revisited.
- source_spec: none
  summary: Strip parenthetical reminder text from oracle text before embedding (menace cards pollute "unblockable" queries, convoke pollutes "ramp"); requires index rebuild.
  evidence: Split from the 8-lead Kotis improvement intent; embedding-pipeline change with a rebuild cost — batch with other re-embed work if possible.
- source_spec: none
  summary: Intersection mode (or rerank/decompose guidance) for compound semantic queries, plus a playability prior on ranking (Llanowar Elves absent from a ramp top-40 Prismite topped).
  evidence: Split from the 8-lead Kotis improvement intent; the largest, most design-heavy lead — benefits from the reminder-text fix landing first. Overlaps the existing "Compound-intent dilution" Epic-3 candidate below.
- source_spec: none
  summary: '`capture_arena_window` tool — screenshot the MTGA window (Win32 `PrintWindow`/`mss`) for board reads; opt-in, graceful `window_not_found`.'
  evidence: Split from the 8-lead Kotis improvement intent; first tool touching the local machine rather than the card DB, so it needs its own opt-in design pass.

## Deferred from: code review of spec-games-union-brawl-singleton (2026-07-10)

- source_spec: `_bmad-output/implementation-artifacts/spec-games-union-brawl-singleton.md`
  summary: Face-keyed aggregation (`card_faces[0].oracle_id` fallback in `src/data/importers/aggregate.py`) is inert — `transform_scryfall_card` hard-requires a top-level `oracle_id`, so reversible-layout cards are still rejected downstream, and `reconcile_games` matches aggregates by `CardModel.oracle_id` only.
  evidence: Blind Hunter traced the pass-2 path — cards grouped by the face/self fallbacks reach the transformer and are error-counted there (pre-existing transformer limitation, parity with the old oracle_cards import). Fix belongs in a transformer pass (accept face-level oracle_id) plus a reconcile lookup keyed the same way as `group_key`.
- source_spec: `_bmad-output/implementation-artifacts/spec-games-union-brawl-singleton.md`
  summary: '`reconcile_games` failure after `import_cards` has committed leaves the DB populated but `initialize_database` reports `status="error"`, and a plain retry short-circuits `already_initialized` with games left stale.'
  evidence: Edge Case Hunter, `src/data/importers/scryfall.py` reconcile stage — the import commits per batch, so a reconcile-stage DatabaseError (lock/disk) can't roll it back. Narrow failure window; remedy is `update=true` (re-runs reconcile). Consider catching reconcile errors as a warning or surfacing a "re-run with update=true" hint in the error message.

## Deferred from: code review of first-run-data-initialization (2026-06-28)

> Surfaced by the 3-reviewer adversarial pass on `spec-first-run-data-initialization.md`. The
> contract gap (uncaught `init_database` failure) and two real robustness items (partial-import
> *exception* path now clears the truncated `cards`; `build_search_index(rebuild=True)` now resolves
> the embedder before the destructive drop) were patched in-branch. The items below are real but
> either pre-existing config or narrow/concurrency edges left for a focused later pass.

- **✅ RESOLVED (0.3.0, 2026-07-11).** No `busy_timeout` → `SQLITE_BUSY` on concurrent writers (Edge Case Hunter, HIGH). Neither the
  async engine (`src/data/database.py::create_engine`) nor the sync `ConnectionFactory`
  (`src/search/connection.py`) sets `busy_timeout`/`connect_args={"timeout": …}`, so SQLite's
  default-0 timeout makes a second writer fail immediately with `database is locked` rather than
  waiting. Pre-existing config, but the new `initialize_database` (bulk write) + `build_search_index`
  (index write) tools make concurrent-writer collisions more likely. Fix project-wide: set
  `PRAGMA busy_timeout=5000` on the sync factory and `connect_args={"timeout": 5}` on the async
  engine (matches the documented WAL topology).
- **✅ RESOLVED (0.3.0, 2026-07-11) — `import_state` in-progress marker.** Process-kill mid-import leaves a partial DB mistaken for complete (Edge Case Hunter, HIGH —
  *exception* half patched). The importer commits per 1000-card batch; the in-branch fix clears the
  partial `cards` when the import raises, so a *failed* import retries cleanly. But a hard process
  kill between batches can't run that cleanup, leaving e.g. 1000 of ~30k cards — which the ≥1-row
  idempotency check then reports as `already_initialized`, permanently. Full fix: write an
  `import_complete` sentinel (meta row) only after the final commit and gate `already_initialized`
  on it, or make the import a single transaction.
- **Corrupt/malformed DB file raises out of the "never raises" guards** (Edge Case Hunter, MED). A
  truncated `-wal` / malformed header makes even the `sqlite_master` probe in either
  `is_database_initialized` raise `DatabaseError`/`OperationalError`; because the guard runs *above*
  each tool's `try/except`, that propagates as a raw error instead of a graceful status. Fix: wrap
  the probes in `try/except (OperationalError, DatabaseError): return False`, or add a distinct
  `database_corrupt` status.
- **Concurrent `initialize_database` double-imports** (Edge Case Hunter, MED). The idempotency check
  and the import aren't atomic/locked, so two concurrent invocations both download + import (the
  upsert importer keeps data correct, but wastes a ~3-min download and contends on the write lock —
  near-certain to fail one of them until `busy_timeout` above is set). Fix: an app-level
  `asyncio.Lock` around the tool, or rely on `busy_timeout` so the loser re-checks and returns
  `already_initialized`.

## ✅ Resolved by first-run-data-initialization (2026-06-28)

> Closed by `spec-first-run-data-initialization.md` — the in-client `initialize_database` /
> `build_search_index` tools plus a graceful `database_not_initialized` status across every
> card/deck tool. The items below are closed; they remain listed in their original sections for
> traceability.

- **MCPB bundle has no first-run data bootstrap or guidance** (mcpb-bundle review, High-for-UX). A
  fresh `.mcpb` now bootstraps in-client: the assistant runs `initialize_database` (Scryfall card
  import) and `build_search_index` (embedding index), and every card/deck tool returns
  `database_not_initialized` with a run-`initialize_database` hint instead of the opaque "A database
  error occurred". No prebuilt DB is shipped (license held — build-on-first-run only).
- **`README.md` overclaimed Claude-Desktop first-run + that `setup.py` builds the index**
  (mcpb-bundle review `README.md:68`; licensing-repo-health review `README.md:38`/`:44`). The Quick
  start and Claude Desktop sections now describe the real flow: `setup.py` (or `initialize_database`)
  downloads the cards; the semantic index is a separate `build_search_index` step.
- The semantic tools' `index_unavailable` message now points at the `build_search_index` **tool**
  rather than the `scripts/build_card_embeddings.py` terminal command (which a GUI client can't run).

> Still open from those reviews (out of this spec's scope): `setup.py:87` prints the stale
> `./data/cards.db` path; `project-context.md`'s "all MCP tools sync `def`" drift; the `report_bug`
> tool is **intentionally not** guarded (it is card-data-independent and already graceful — see the
> spec's Change Log).

## Public-release goals deferred by scope-split (2026-06-27)

> Source: `RELEASE-STRATEGY.md`. Brad ran `bmad-quick-dev` to "execute RELEASE-STRATEGY.md" and
> chose **Split — DB centralization first** at the multi-goal gate. This run (branch
> `feat/central-data-dir`) implements **only §3 (central OS data dir)**. The remaining
> independently-shippable deliverables below are deferred and should each be picked up as their
> own quick-dev run, in roughly the strategy's §7 order. Each links back to the strategy section.
>
> **Two cross-cutting constraints carried forward:**
> 1. **The prune only _untracks_ the workflow's framework + skills** (`_bmad/`, `.claude/skills/bmad-*`)
>    via `git rm --cached` + gitignore — removed from the public repo but kept on disk, so the workflow
>    still runs locally — and **`_bmad-output/` stays tracked** (Brad, 2026-06-28). No mid-run ordering
>    hazard anymore, since nothing bmad-related is hard-deleted from the working tree.
> 2. **Outward-facing / irreversible steps stay manual.** Secret scan, `git tag v0.1.0`, cutting
>    the GitHub Release, and flipping the repo public are Brad's call — automate the prep, stop
>    at that line.

- **Prune legacy + dev tooling (§1, §2).** Three distinct treatments (Brad, 2026-06-28):
  - **Hard delete (`git rm`):** the legacy PydanticAI/Chainlit stack (`legacy/`, `public/`),
    superseded root docs, scratch `scripts/test_*.py`, `examples/`, internal `docs/` files; curate
    `docs/` down to architecture/bug-report/performance.
  - **Untrack but keep on disk (`git rm --cached`) + gitignore:** the BMAD **framework + dev skills**
    (`_bmad/`, `.claude/skills/bmad-*`) — gone from the public repo but kept locally so the workflow
    still runs.
  - **KEEP tracked:** `_bmad-output/` (planning + implementation artifacts = public design record).
  Then edit `.gitignore`: un-ignore `.github/`, add `/_bmad/` + `.claude/skills/bmad-*/`, but **not**
  `/_bmad-output/`. Mechanical; no logic.
- **Trim deps & package metadata (§6).** `pyproject.toml`: drop orphaned `anthropic`/`openai`/
  `asyncpg`, move `logfire` to an optional `observability` group, verify-and-likely-drop
  `tenacity`/`python-dotenv`, add `platformdirs` (already added by the §3 run — reconcile), remove
  the `[dependency-groups] legacy` block, rewrite the "built with PydanticAI" description, set a
  real `authors` email (sathias@slopstudio.net), add `[project.scripts]` console entry points.
  (**`.env.example` cleanup — including deleting the `LEGACY ONLY` section and adding the
  `PLANESWALKER_DATA_DIR` note — was pulled into the `feat/central-data-dir` run at Brad's
  request, so it's done; only the `pyproject.toml` work remains under §6.**)
- **Licensing & repo-health docs (§6).** Add `LICENSE` (MIT, Copyright (c) 2026 Brad Sprigg),
  `NOTICE` (Scryfall/WotC attribution + Fan Content Policy), `SECURITY.md`, `CONTRIBUTING.md`,
  `CHANGELOG.md` (start 0.1.0, record the central-DB migration note), and the README attribution/
  disclaimer block. (README body was already rewritten in commit d1dc5a2.)
- **CI workflow (§6).** `.github/workflows/ci.yml`: `uv sync` → `ruff check` → `ruff format
  --check` → `mypy src/` → `pytest -m "not integration"`, matrix on 3.12/3.13; plus issue/PR
  templates.
- **MCPB bundle for Claude Desktop (§4).** Add `manifest.json` (manifest_version 0.4, `uv`
  runtime, `PLANESWALKER_DATA_DIR` user_config — **depends on the §3 env var**); `npx
  @anthropic-ai/mcpb pack`; smoke-test install. Attach the `.mcpb` to the GitHub Release.
- **Release mechanics (§7.1, §8 — MANUAL).** Run the full-history secret scan
  (`uvx gitleaks detect --source . --log-opts="--all"`), tag `v0.1.0`, cut the GitHub Release with
  the `.mcpb` attached, flip the repo public. Brad executes these.

## Deferred from: code review of licensing-repo-health-docs (2026-06-28)

> Surfaced by the 3-reviewer adversarial pass on the §6 licensing/repo-health docs run
> (`spec-licensing-repo-health-docs.md`). The doc-accuracy issues in the *new* files
> (CONTRIBUTING/CHANGELOG over-claiming that `setup.py` builds the search index; the "all MCP
> tools are sync `def`" overstatement) were patched in-branch. The items below are real but
> pre-existing or outside this run's frozen scope (no README/code edits).

- **README claims `setup.py` builds the search index (it doesn't).** [`README.md:38`](../../README.md#L38)
  (`# installs deps, builds the card DB + index`) and [`README.md:44`](../../README.md#L44)
  ("builds the local search index") both assert the one-time `setup.py` run produces the semantic
  index. Verified false: `setup.py` only runs `initialize_database()` (Scryfall card import) — no
  `build_card_embeddings` / `card_vec` reference anywhere in it. The index must be built separately
  via `uv run python scripts/build_card_embeddings.py`. So a user who follows the README Quick start
  and immediately calls `semantic_search_cards` gets `status="index_unavailable"`. Out of scope here
  (the spec froze "no README edits"); fix in a focused README-accuracy pass — either correct the two
  lines, or have `setup.py` actually build the index after import.
- **`setup.py` post-`.env` message hard-codes the old `./data/cards.db` path.**
  [`setup.py:87`](../../setup.py#L87) prints `Defaults work out of the box (SQLite at ./data/cards.db…)`,
  stale since the central-OS-data-dir change (the engine now resolves via `paths.database_url()` to the
  OS data dir). Cosmetic only — the DB still lands in the central dir — but the printed path misleads.
  Update the string to reference the central dir (or drop the concrete path).
- **`project-context.md` MCP-tool rule ("Define tools as sync `def`") drifted from the shipped code.**
  The Framework rules state MCP tools are sync `def` threadpooled by FastMCP, but the Epic-1 tools
  (`lookup_card_by_name`, `report_bug`, `search_cards`, deck CRUD/analysis) are `async def`; only the
  two Epic-2 semantic tools (`semantic_search_cards`, `find_similar_cards`) are sync `def`. The doc
  describes the Phase-1 *design target*, not the implementation — and it's what led the docs run to
  over-generalize. Reconcile the project-context MCP-tool rule with the actual async/sync split.

## Deferred from: code review of spec-central-os-data-dir (2026-06-27)

> Surfaced by the 3-reviewer adversarial pass on the `feat/central-data-dir` work. The HIGH/MED
> findings (broken `migrate_add_bug_reports.py` import, empty-env sync/async divergence, relative
> `PLANESWALKER_DATA_DIR` not absolute) were patched in-branch; the items below are real but
> pre-existing or exotic, left for a focused later pass.

- **Bare-path `CARDS_DATABASE_URL` (no SQLAlchemy prefix) crashes the async engine** —
  `src/paths.py::database_url` returns the env value verbatim, so `CARDS_DATABASE_URL=/data/cards.db`
  (without `sqlite+aiosqlite:///`) makes `create_async_engine` raise `ArgumentError`, while the sync
  `ConnectionFactory` happily uses the bare path — a half-works/half-crashes split. Pre-existing (the
  old `os.getenv("CARDS_DATABASE_URL", default)` had the same risk) and it fails loudly. Fix later by
  validating/normalising the URL form, or document that the `sqlite+aiosqlite:///` prefix is mandatory.
- **UNC `PLANESWALKER_DATA_DIR` yields a malformed async URL** — for `\\server\share\pw`,
  `database_path().as_posix()` collapses the leading `\\` to a single `/`, so the async URL drops the
  UNC authority while the sync factory keeps the native UNC path → divergence. Exotic (SQLite over a
  network share is discouraged anyway); document "use a local absolute data dir" or reject UNC paths.
- **✅ RESOLVED by the prune (2026-06-28) — Repo-wide `ruff check .` / `ruff format --check .` now clean.**
  The pre-existing drift was in `_bmad/scripts/*` and `src/mcp_server/tools/card_lookup.py`. The prune
  untracked + gitignored `_bmad/` (ruff now skips it) and the pre-commit formatter normalized one
  f-string in `card_lookup.py`. Verified: `ruff format --check .` (120 files) + `ruff check .` both pass.

## Deferred from: code review of trim-deps-package-metadata (2026-06-28)

> Surfaced by the 3-reviewer adversarial pass on the `chore/trim-deps-package-metadata` work
> (§6 deps/metadata cleanup). No HIGH/MED findings against the change itself — every blind-hunter
> "risk-to-confirm" item (entry-point `main` exists, removed deps unreferenced anywhere, mypy hook
> still clean without `logfire`) was verified false. The one real item below is pre-existing.

- **`setup.py` creates a `.env` that nothing actually loads (orphaned onboarding artifact)** —
  `setup.py::setup_environment` writes `.env` from `.env.example`, but no code path loads it: there
  is no `load_dotenv` call and no `pydantic-settings` `BaseSettings(env_file=...)` anywhere — all
  config is read via bare `os.getenv(...)` (`src/paths.py`, `src/search/connection.py`,
  `src/search/embedder.py`, `src/mcp_server/__main__.py`), and `uv run` does not auto-load `.env`.
  So edits to the generated `.env` silently have no effect unless the user exports the vars or the
  MCP client injects them. Pre-existing (predates this chore; confirmed while verifying the
  `python-dotenv` removal). Fix later by either wiring up `.env` loading (a `BaseSettings` config
  object, or `uv run --env-file`) or trimming `setup_environment` + `.env.example` to match the
  "env vars are optional, defaults work out of the box" reality. (Source: Edge Case Hunter; Severity: Low.)

## ✅ Resolved by the Pre-Epic-3 Targeted Gate (2026-06-27)

> Cleared via `spec-pre-epic-3-targeted-gate.md` before starting Epic 3. The items below are closed;
> they remain listed in their original sections for traceability.

- **G1 — `_FakeEmbedder`/`_FakeVecEmbedder` duplication (was 5 copies).** Consolidated into one
  `tests/fixtures/embedder.py::FakeEmbedder` (union of `encode`/`encode_batch`/`total_embedded`);
  all call sites import it. (Closes the 2-4 and 2-5 "`_FakeEmbedder` in N test files" items.)
- **G2 — `limit` upper bound / `limit > over_fetch_k` starvation.** `semantic_search_cards` and
  `find_similar_cards` now reject `limit > 50` (`_MAX_LIMIT`, kept under `over_fetch_k=200`).
  (Closes the 2-4 "`limit > over_fetch_k` silently truncates" and 2-5 "silently starves" /
  "`limit` has no upper bound" items.)
- **G3 — graceful "index not built".** New `src/search/query.py::index_is_populated` gates both
  semantic tools, returning `status="index_unavailable"` (with a build-the-index hint, `isError=False`)
  for a missing **or** empty `card_vec`, instead of a raw `OperationalError`. (Closes the
  "index not built" half of the 2-4 "Unhandled exceptions propagating from sync tool" item; the
  ONNX/`RuntimeError`/`JSONDecodeError` halves remain deferred — infra concerns.)
- **Nullability audit (1-4 / 1-6).** Confirmed the `Card`/`CardSummary` `@field_validator(mode="before")`
  coercions (`None → ""`/`[]`/`{}`) already protect `mana_cost`/`oracle_text`/`colors`/`games`/`legalities`;
  added a `validate_deck` NULL-legalities/NULL-games regression test. Closes the 1-4
  "CardSummary.mana_cost/oracle_text non-nullable" + "colors no None-coercion" items and the 1-6
  "`card.legalities` potentially None" + "`card.games` potentially None" items.

## Epic-3 design candidates (from TOOL_PERFORMANCE_REPORT.md, 2026-06-27)

> Surfaced by Brad's live test of the semantic tools (R1). Not bugs — enhancement candidates to weigh
> during Epic 3.

- **Compound-intent dilution — handle in the orchestrator, not the tools.** "A **and** B" queries
  (e.g. "removal that also reanimates") rank by topical proximity, so cards matching *either* effect
  blend in and can outrank true "both" cards (`Betrayal of Flesh` ranked 14th). Treat the semantic
  tools as **high-recall candidate generators**: over-fetch, then have the Story 3.1 orchestrator /
  LLM filter for the logical intersection and present ranked candidates **with reasons** (confirms
  retro design-input I1). An optional in-tool re-rank rewarding multi-clause matches is a possible
  later refinement.
- **`find_similar_cards` cross-color leakage.** With no `colors` filter, off-color cards surface
  (`src/mcp_server/tools/find_similar.py`). Consider defaulting `colors` to the seed card's colour
  identity (overridable) to cut leakage. Tool already supports the filter; only the default is open.

## Deferred from: code review of 2-6-rag-sanity-eval (2026-06-24)

- **`evaluate_hit_rate([])` produces confusing "0 miss(es)" failure message** — `tests/integration/search/test_rag_eval.py`. If `_QUERY_FIXTURE` is ever emptied (module-level constant; only via code edit), `evaluate_hit_rate([])` returns `(0.0, [])`, which trips the `>= TARGET_HIT_RATE` assert but `format_failure` prints "0 miss(es)" with no per-miss lines — self-contradictory. Add `assert case_results, "Query fixture is empty"` before the hit-rate assert as a defensive guard in a future maintenance pass.
- **`reset_embedder()` teardown ordering hazard across modules** — `tests/integration/search/test_rag_eval.py`. Module-scoped `rag_eval_index` fixture calls `reset_embedder()` in teardown. If another module's session-scoped fixture loaded the embedder, this reset destroys the shared singleton mid-session. Pre-existing pattern in `test_embedder.py` and `test_semantic_search_tool.py`; a session-scoped coordinator would fix it project-wide.
- **Yield-fixture setup failure leaves `ConnectionFactory` unclosed** — `tests/integration/search/test_rag_eval.py:rag_eval_index`. If `get_embedder()` raises during fixture setup (model download failure, ONNX error), pytest does not run the teardown, so `factory.close()` is never called. Tmp files are cleaned by `tmp_path_factory` at session end; no functional impact. Fix with `try/finally` around setup if file-lock issues surface on Windows.

## Deferred from: code review of 2-5-find-similar-cards-tool (2026-06-22)

- **LIKE wildcard injection in `card_name`** — `src/mcp_server/tools/find_similar.py`. Characters `%` and `_` in seed card names are not escaped before the `LIKE lower(?)` partial-match fallback, silently broadening or changing the match set. Acknowledged in code comment as "accepted LIKE-wildcard risk, mirroring CardRepository (deferred-work)". Pre-existing in `card_lookup.py` and `card.py` (1-3 review).
- **`limit > over_fetch_k` silently starves results (find_similar path)** — `src/search/query.py:hybrid_search`. `find_similar_cards` never passes `over_fetch_k`, so callers requesting `limit > 200` receive fewer alternatives than requested with no warning. Also, seed cards with many printings (e.g. Lightning Bolt ~50 printings) consume KNN slots before exclusion, further reducing the effective result count. Related: noted in 2-4 review.
- **`np.frombuffer` returns read-only array in `get_card_vector`** — `src/search/query.py`. The returned `NDArray` is backed by the SQLite buffer object and is read-only; any future caller that attempts in-place mutation will get a `ValueError`. Current code path (via `hybrid_search → serialize_float32`) only reads the array. Guard with `.copy()` if mutating callers are ever added.
- **Empty/corrupted BLOB in `get_card_vector` raises ValueError** — `src/search/query.py`. If the `card_vec` BLOB is zero-length or not a multiple of 4 bytes (data corruption), `np.frombuffer` raises `ValueError` uncaught. Controlled data written by `serialize_float32` always produces 1536 bytes; treat as infrastructure concern.
- **`_FakeEmbedder` now in four test files** — Previously tracked (2-4 review). `test_find_similar_tool.py` adds a fourth copy. Consolidate to `tests/conftest.py` or `tests/fixtures/embedder.py` in a future housekeeping pass.
- **`color_mode` not runtime-validated in `find_similar_cards` helper** — `src/mcp_server/tools/find_similar.py:_validation_error`. Invalid strings reach `hybrid_search._color_predicates` unchecked. FastMCP's `Literal["any", "all", "exact", "at_most"]` annotation rejects invalid values at the wire level; direct helper calls bypass this. Mirrors Story 2.4 pattern.
- **`limit` has no upper bound in `_validation_error`** — `src/mcp_server/tools/find_similar.py`. Only `limit < 1` is rejected. `over_fetch_k=200` provides a natural cap on results. Also noted in 2-4 review.
- **`_resolve_seed` LIKE fallback fetches all matching rows without SQL LIMIT** — `src/mcp_server/tools/find_similar.py`. On 60k cards, a common substring like `"a"` loads thousands of rows into Python memory before `_MAX_MATCHES` capping. Mirrors `CardRepository.find_by_name_partial`'s unbounded fetch. Add `LIMIT _MAX_MATCHES * 20` to the SQL in a future performance pass.
- **`_decode_colors` does not guard against non-list JSON or `JSONDecodeError`** — `src/mcp_server/tools/find_similar.py:_decode_colors`. If `cards.colors` contains valid JSON but not a JSON array (e.g. a string scalar `"R"`), `json.loads` returns a non-list that bypasses the `value is not None` check and reaches `CardSummary(colors=...)` as the wrong type; malformed JSON raises `JSONDecodeError` uncaught. Same pattern as `_coerce_json_list` in `query.py`; Scryfall always writes a valid JSON array — infrastructure concern.
- **Disambiguation "showing first N" message branch is unreachable for 6–10 distinct matches** — `src/mcp_server/tools/find_similar.py:253`. `shown = distinct[:_MAX_MATCHES]` equals `distinct` when `len(distinct) ≤ 10`, so the inner `if len(shown) < len(distinct)` branch (which emits "showing the first N") is dead code for that range. For 6–10 matches, the message says "Please refine" without the count sub-clause, even though all matches are returned in `matches`. Cosmetic phrasing gap; `matches` list is correct.

## Deferred from: code review of 2-4-semantic-search-cards-tool-hybrid-query (2026-06-22)

- **Unhandled exceptions propagating from sync tool** — `src/mcp_server/server.py:440`. `OperationalError` (DB unavailable / index not built), `RuntimeError` (ONNX failure), and `json.JSONDecodeError` (malformed DB column) all propagate uncaught through the sync tool, resulting in `isError=True` FastMCP responses. Matches the existing Epic-1 async tool pattern; a `status="error"` enum extension would be needed to handle these gracefully. Defer until infra errors surface in practice.
- **`_FakeEmbedder` duplicated in three test files** — `tests/unit/search/test_query.py`, `tests/integration/mcp_server/test_semantic_search_tool.py`, and `tests/integration/conftest.py` each define an identical `_FakeEmbedder` / `_FakeVecEmbedder` class. Move to a shared `tests/integration/conftest.py` or a dedicated `tests/fixtures/embedder.py` helper to avoid triple-maintenance on `Embedder` interface changes.
- **`limit > over_fetch_k` silently truncates results** — `src/search/query.py:hybrid_search`. Callers passing `limit > 200` (default `over_fetch_k`) receive fewer results than requested with no indication. Spec says "sane max ~50"; add an upper-bound validation in `_validation_error` (e.g. `limit > 50 → status="invalid"`) in a future polish pass.

## Deferred from: code review of 1-1-repository-restructure-dependency-reshape (2026-06-20)

- **`legacy/tests/conftest.py` module-level chainlit import** — `import chainlit` at the top of `legacy/tests/conftest.py` (line 8) causes `ModuleNotFoundError` if someone runs `pytest legacy/tests/` on a lean env (without `--group legacy`). `testpaths = ["tests"]` protects the default run. Fix: add a note to `legacy/` documentation or add a root-level `conftest.py` `collect_ignore_glob` guard to make the failure message clearer.

- **`mock_user_session` fixture state leak** — `legacy/tests/conftest.py` patches `cl.user_session.get/.set` at fixture setup time with no teardown/restore. If a test using this fixture fails mid-run, subsequent tests in the same session inherit the patched session. Fix: rewrite using pytest's `monkeypatch` fixture or a `yield`-based restore. Applies to the legacy test tree only (excluded from active CI).

- **Legacy tests' `tests.fixtures.card_data` import** — Files like `legacy/tests/integration/agent/test_agent_card_search.py` import `from tests.fixtures.card_data`. This works when pytest sets the project root on `sys.path` (standard `uv run pytest` from root) but may fail in IDEs or when running `pytest legacy/tests/` in isolation. Fix: either copy shared fixtures into `legacy/tests/fixtures/` or add a `conftest.py` `sys.path` adjustment to `legacy/tests/`.

- **`PaginatedResult[T]` missing field validators** — `src/data/schemas/pagination.py` has no validators to enforce `page >= 1`, `page_size >= 1`, or `total_pages` consistency with `total_count`. A caller constructing `PaginatedResult(page=0, ...)` silently passes validation; a caller reading `page=1, total_pages=0` has an impossible state. Fix: add `Field(ge=1)` to `page`, `page_size`, `total_pages` and optionally a `model_validator` for `total_pages` consistency.

- **Task 0 out-of-scope changes** — Story 1.1 also shipped three pre-existing-defect fixes (explicitly approved by user): recreated `src/data/schemas/pagination.py`, fixed `CardModel.printed_name` default, and updated test contract assertions for `PaginatedResult`. These were correctness-restoring fixes needed to unblock AC4 (100 tests were failing at baseline). No follow-up action required; noted here for traceability.

## Deferred from: code review of 1-2-sqlite-connectionfactory-with-wal-extension-loading (2026-06-20)

- **Empty string `CARDS_DATABASE_URL` not guarded** — `_resolve_db_path` returns `""` if the env var is set to an empty string, which `sqlite3.connect("")` will fail on (OperationalError). This is an operator misconfiguration that fails loudly; not worth defensive handling given project rules against unnecessary validation. If it becomes a user-facing pain point, add a guard in `_resolve_db_path` to fall back to the default when the stripped URL is empty.

## Deferred from: code review of 1-3-fastmcp-server-with-card-lookup-bug-report (2026-06-20)

- **`updated_at` onupdate lambda silent in ORM** — `src/data/models/bug_report.py:43-47`. SQLAlchemy `mapped_column(onupdate=callable)` does not fire via the ORM unit-of-work; `updated_at` will always equal `created_at`. Matches the pre-existing `DeckModel` pattern. Only matters when a future story adds an update operation.
- **No CHECK constraint on status column** — `src/data/models/bug_report.py:32-34`. Any raw string can be written to `status` bypassing enum validation; reading it back via `BugReport.model_validate` would raise `ValueError`. Currently only triggered by manual DB manipulation. Address when an update story is implemented.
- **CardLookupResult.matches=[] on found status** — `src/mcp_server/tools/card_lookup.py`. An empty list rather than `None` for `matches` when `status="found"` is ambiguous for callers. Design preference; no functional bug.
- **LIKE wildcard injection in card_name/games** — `src/data/repositories/card.py`. Characters `%` and `_` in the card name or games list are passed un-escaped to SQLite LIKE. Pre-existing issue in `CardRepository`; out of scope for Story 1.3.
- **Non-DatabaseError exceptions skip explicit rollback in BugReportRepository** — `src/data/repositories/bug_report.py:50-69`. Exceptions that aren't `IntegrityError` or `DatabaseError` propagate without explicit `rollback()`. The session context manager handles cleanup on exit; low practical risk in current call paths.
- **migrate_add_bug_reports.py CWD-sensitive** — `scripts/migrate_add_bug_reports.py:20`. Default `DATABASE_URL` uses `./data/cards.db`; if the script is run from a non-root directory it silently targets the wrong file. Convention (run via `uv run` from project root) guards this; a doc comment would help.
- **Transport cast is runtime no-op** — `src/mcp_server/__main__.py:20`. `cast(_Transport, os.getenv(...))` provides no runtime validation. FastMCP raises on an invalid transport string anyway, but an explicit guard would give a clearer error message.

## Deferred from: code review of 1-4-advanced-card-search-tool (2026-06-20)

- **`CardSummary.mana_cost`/`oracle_text` non-nullable** — `src/data/schemas/card.py:84,87`. Both fields are `str` (not `str | None`), matching the pre-existing `Card` schema pattern. Scryfall has null mana_cost for tokens/land faces and null oracle_text for split cards. If the DB stores these as NULL, `CardSummary.model_validate(card)` will raise `ValidationError`. Needs to be addressed as part of a broader Card/CardSummary schema nullability audit; this story explicitly prohibits modifying `Card`.
- **`CardSummary.colors: list[str]` no None-coercion** — `src/data/schemas/card.py:88`. `Card.games` has `@field_validator` coercing `None → []`; `colors` has no equivalent in either `Card` or `CardSummary`. If a `CardModel.colors` is NULL in SQLite, `model_validate` raises `ValidationError`. Pre-existing in `Card`; should be addressed alongside the mana_cost/oracle_text audit.
- **`page_size > 50` silently capped with no caller notification** — `src/data/repositories/card.py`. The repository clamps `page_size = min(page_size, 50)` and reflects the effective value in `CardSearchResult.page_size`. The tool-level `_validation_error` only rejects `page_size < 1`. Consider adding an upper-bound check (return `status="invalid"` for `page_size > 50`) in a future polish pass.
- **`games` validation case-sensitive vs `rarity` case-insensitive inconsistency** — `src/mcp_server/tools/card_search.py:83-86`. `rarity` values are normalised with `.lower()` before checking; `games` are compared directly. Callers passing `"Paper"` or `"MTGO"` get `status="invalid"` with a clear message naming the expected casing. Inconsistent but not harmful; could be unified in a future polish story.
- **`page` beyond `total_pages` gives generic empty message** — `src/mcp_server/tools/card_search.py:178-189`. Requesting `page=999` on a 1-page result set returns `status="empty"` with the standard "try adjusting filters" hint, giving no indication the page number exceeded the range. A future polish pass could detect `page > result.total_pages` after the repo call and return a more specific message.
- **`colors=[]` applies no filter for non-"exact" modes** — `src/data/repositories/card.py`. `search_advanced` treats `colors=[]` (empty list) the same as `colors=None` for `any`/`all`/`at_most` modes because `if colors:` is falsy. A caller expecting "empty list = colorless only" gets "no filter" instead. Pre-existing behavior in `search_advanced`; out of scope for this story.

## Deferred from: code review of 1-5-deck-management-tools (2026-06-20)

- **`DeckSummary.from_attributes=True` footgun** — `src/data/schemas/deck.py`. `DeckSummary.model_validate(deck)` silently gives zero counts because `Deck` has no `mainboard_count` attribute. Docstring warns; helpers always use explicit constructors. Could remove `from_attributes=True` from `DeckSummary`/`DeckDetail` (only `DeckCardSummary` actually needs it) to prevent future misuse.
- **`CardSummary.model_validate(dc.card)` on a Pydantic model** — `deck_management.py:_deck_detail`. Works in Pydantic v2 via attribute inspection on `Card` instances. A more explicit pattern (`CardSummary(**dc.card.model_dump())`) is safer but out of Story 1.5 scope.
- **Non-deterministic card ordering in `_deck_detail`** — `deck_management.py`. Order of `load_deck` card list depends on `DeckRepository.get_deck_with_cards` sort; if non-deterministic, card order in responses is unstable. Address when consistent ordering is required.
- **`not_in_deck` message does not hint card exists in other location** — `deck_management.py:remove_card_from_deck`. Removing from mainboard when card is in sideboard returns "not in the mainboard" with no hint the card is present elsewhere. UX improvement for a future polish story.
- **`_deck_detail` crash risk if `dc.card` is `None`** — `deck_management.py`. FK enforcement is OFF; if a card row is deleted after a `deck_cards` row was inserted, `get_deck_with_cards` may return a `DeckCard` with a null `card`. `CardSummary.model_validate(None)` would raise. Defended by add-path pre-validation (AC4) but not structurally guaranteed.
- **No `format` validation in `create_deck`** — `deck_management.py`. Invalid format strings (e.g., `"potato"`) are stored silently; deferred to Story 1.6 `validate_deck` by D-1.5b.

## Deferred from: dev of 1-2-sqlite-connectionfactory-with-wal-extension-loading (2026-06-20)

- **`test_list_decks` flaky ordering (pre-existing)** — `tests/integration/data/test_deck_repository.py::test_list_decks` asserts three rapidly-created decks come back newest-first, but `DeckRepository.list_decks` orders by `created_at.desc()` with **no secondary tie-breaker** ([`src/data/repositories/deck.py:260`](../../src/data/repositories/deck.py#L260)). When the three `create_deck` calls land on identical `created_at` timestamps (common under full-suite timing), SQLite resolves the tie arbitrarily and the assertion fails non-deterministically. Verified: the test passes 5/5 in isolation but fails intermittently in the full run. Unrelated to Story 1.2 (which only adds `src/search`); left untouched per scope discipline. Fix: add a deterministic secondary sort key to `list_decks` (e.g. `.order_by(DeckModel.created_at.desc(), DeckModel.id)`) **and** make the test's creation-order intent explicit (e.g. distinct/controlled `created_at` values), since UUID `id` is not time-ordered.

## Deferred from: code review of 2-1-embedder-port-fastembed-singleton-persistent-cache (2026-06-21)

- **Double-checked locking portability for non-CPython/free-threaded Python** — `src/search/embedder.py:1038`. The outer `if _embedder is None` read has no lock and relies on CPython's GIL for visibility. Correct on CPython 3.12 (project target), but not portable to free-threaded builds (PEP 703, opt-in in Python 3.13+) or other implementations. Revisit if/when free-threaded Python is targeted.
- **encode_batch large-batch memory ceiling** — `src/search/embedder.py:encode_batch`. No `batch_size` passthrough; a ~60k-item call materializes all output vectors in memory (~88 MB for float32 alone) plus fastembed's internal buffers. Spec explicitly deferred `batch_size` to Story 2.3's index builder.
- **reset_embedder() dual ONNX sessions under concurrent use** — `src/search/embedder.py:reset_embedder`. If called while a thread holds a reference from `get_embedder()` and is mid-encode, the next `get_embedder()` loads a second ONNX session, doubling RAM transiently. Test-only function; production FastMCP never calls it; GC reclaims the old Embedder when callers release their reference. Docstring should note the hazard.
- **test_resolve_cache_dir_never_temp assertion style** — `tests/unit/search/test_embedder.py:1197`. `startswith("./data")` check is correct for the current relative default. If the P1 absolute-path patch is ever applied, this test will need updating to match the resolved absolute path.
- **README.md and setup.py changes bundled in story commit** — Not in the spec File List; spec's Git Intelligence note acknowledges these as pre-existing MCP-pivot cleanup. Noted for traceability.

## Deferred from: code review of 2-2-card-vec-schema-with-metadata-columns (2026-06-21)

- **Tests call `factory.close()` without try/finally** — `tests/unit/search/test_schema.py`. Every test leaves `factory.close()` outside a `try/finally`, so connections are not released on assertion failure. On Windows, leaked WAL connections can cause file-lock errors. Pre-existing pattern mirrored from `test_connection.py`; fix the pattern project-wide when refactoring the test helpers.
- **Migration CWD-relative DB path** — `scripts/migrate_add_card_vec.py`. Default `./data/cards.db` is CWD-relative; running from a non-root directory silently targets the wrong file. Pre-existing `ConnectionFactory` behavior; convention is `uv run` from project root. Same issue exists in `migrate_add_bug_reports.py`.
- **`mana_value integer` column accepts Python float inputs without coercion** — `src/search/schema.py`. SQLite's dynamic typing allows storing a Python `float` in an `integer`-affinity column without error, so `WHERE mana_value = 2` could silently miss cards stored as `2.0`. The `int(cmc)` cast is Story 2.3's responsibility at insert time.

## Deferred from: code review of 1-6-deck-analysis-tools (2026-06-20)

- **`dc.quantity` zero or negative can undercount mainboard cards** — `validate_deck` in `src/logic/deck_validator.py` accumulates `dc.quantity` without clamping. A zero or negative quantity (bypassing the DeckCard schema validator) would undercount the mainboard, potentially letting an illegal deck pass the 60-card check. Fix at insert time in `DeckRepository.add_card_to_deck` with `quantity >= 1` enforcement.
- **`card.legalities` potentially `None` from DB NULL** — `card.legalities.get(format)` in `validate_deck` (`src/logic/deck_validator.py`) raises `AttributeError` if `legalities` is `None`. The `Card` schema types this as `dict[str, str]` (non-nullable), but SQLite does not enforce NOT NULL for JSON columns without a CHECK constraint. Address in a broader Card schema nullability audit (related: deferred in 1-4 review).
- **`card.games` potentially `None` from DB NULL** — `set(card.games)` in `validate_deck` raises `TypeError` if `card.games` is `None`. Same root cause as `legalities`; `Card.games` has a `@field_validator` coercing `None → []` for ORM-loaded instances but not for in-memory `Card` objects constructed directly. Confirm the validator fires for all construction paths.
- **Unexpected exceptions from logic functions propagate unhandled** — `_logic_analyze_mana_curve`, `_logic_detect_synergies`, and `_logic_validate_deck` in `src/mcp_server/tools/deck_analysis.py` are called with only `DatabaseError` caught around the repo load. If any logic function raises an unexpected exception (e.g., a malformed `cmc` field in `analyze_mana_curve`), it propagates to the MCP caller as an unstructured error. Accepted risk for Phase-1; revisit if unexpected failures surface in practice.
- **Quantity expansion OOM for adversarial large `dc.quantity`** — `analyze_mana_curve` in `deck_analysis.py` expands `dc.card` by `range(dc.quantity)` into `all_cards`. A corrupted/adversarial record with `quantity=1_000_000` would allocate a million-element list. Cap at the repository level (or add a defensive `min(dc.quantity, 250)` expansion cap) when productionising.
- **`format` normalization absent from pure `validate_deck` logic** — The tool helper normalises `format.strip() or "standard"`, but the pure function in `src/logic/deck_validator.py` accepts any string, including `""`. Direct callers (e.g., future logic-layer callers) passing an empty format will get all cards flagged as format-illegally. Consider adding the normalization to the pure function as a defensive guard.
- **`seeded_card_db` omits `games` field on seed cards** — The three shared fixture cards (Lightning Bolt, Thunderbolt, Counterspell) default to `games=[]`. The `games` filter path in `validate_deck` is therefore not exercised end-to-end through the MCP harness (`test_mcp_tools.py`). Covered at the helper level in `test_deck_analysis_tool.py`. Acceptable Phase-1 gap; extend the harness test when the fixture is enriched for Epic-2 work.

## Deferred from: code review of story-3.4 (2026-06-27)

- **`validate_deck` skips `dc.card is None` rows from copy/legality checks while still counting them in `mainboard_count`** — `src/logic/deck_validator.py` does `if dc.card is None: continue` before tallying copies/legality, but `mainboard_count` sums quantity unconditionally. A saved deck with an orphaned card join (a `card_id` no longer in the DB) passes copy/legality vacuously while still counting toward the 60-card size — a "legal" result can hide un-validated phantom cards. Pre-existing tool/data edge; obscure. Could add a one-line caveat to the format-legality skill's "what the tool can't see" section. (Source: Edge Case Hunter; Severity: Low.)

## Deferred from: code review of mcpb-bundle (2026-06-28)

> Surfaced by the 3-reviewer adversarial pass on the `chore/mcpb-bundle` work (§4 MCPB bundle).
> The one HIGH that mattered (`.mcpbignore`'s unanchored `data/` also excluding `src/data/`, which
> would have shipped a server unable to import its own data layer) was caught by re-verification and
> patched in-branch by anchoring the rule to `/data/`. Most blind-hunter findings were verified false
> (`server.type: "uv"` IS valid in the MCPB v0.4 schema; blank `data_dir` is handled by
> `paths.py`'s `(getenv() or "").strip()` fallback; `uv run` honours `requires-python`). The two
> real items below are pre-existing or out-of-this-run's-scope-by-design.

- **MCPB bundle has no first-run data bootstrap or guidance.** A freshly-installed `.mcpb` launches
  the server, but the shared OS data dir has no `cards.db` yet — the ~250 MB data set is excluded from
  the bundle **by design** (§3/§4; spec "Never: no DB shipped"). The server never calls
  `init_database`, so the first relational tool call fails (`no such table: cards`); the two semantic
  tools degrade gracefully to `status="index_unavailable"`. Net end-user experience: "every deck/card
  tool errors with no guidance." Out of scope here (the bundle correctly ships data-excluded), but a
  real UX gap. Follow-up: either add a first-run auto-init / friendly "run the one-time data build"
  response, or document the manual bootstrap (`uv run python setup.py`, then
  `scripts/build_card_embeddings.py` — both write to the shared OS data dir the bundle reads) in the
  install docs. (Source: Edge Case Hunter; Severity: High-for-UX.)
- **`README.md:68` overclaims the Claude-Desktop first-run behavior.** The "Claude Desktop
  (one-click)" section says *"(First launch prompts you to run the one-time data build.)"* — but the
  shipped `manifest.json` has no prompt/hook to do that (coupled to the bootstrap-gap item above).
  Out of this run's frozen scope (no README edits). Fix in the focused README-accuracy pass already
  tracked (the `setup.py`-builds-the-index claim) — either implement the prompt or reword to a manual
  build step. (Source: Edge Case Hunter; Severity: Med.)
- **MCPB GUI data-dir override removed (smoke-test fix 2026-06-28).** The optional
  `user_config.data_dir` field was dropped from `manifest.json` because Claude Desktop passes the
  **unsubstituted `${user_config.data_dir}` placeholder** when the optional field is left blank,
  repointing the server at a bogus relative dir → empty DB → `no such table: decks`. The bundle now
  always uses the shared central OS dir (zero-config). If the GUI override is ever re-added, also
  harden `src/paths.py::data_dir` to ignore an override that still contains an unsubstituted `${...}`
  placeholder (defense-in-depth), with a unit test — otherwise the bug returns. (Source: Brad live
  smoke-test; Severity: was High, now fixed.)
