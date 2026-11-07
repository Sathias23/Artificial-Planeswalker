---
id: SPEC-quality-audit-p1
companions:
  - batches.md
sources:
  - ../../planning-artifacts/research/quality-audit-2026-09-03.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Quality Audit P1 Fixes

## Why

A **pain to solve** and a **mandate to meet**. The 2026-09-03 audit of the public repo found no
critical defects but three structural costs: the two hottest user actions (exact card lookup, deck
import) run full-table scans; roughly 250 Python tests and most of the `ui/tests/` project assert on
source text and prose instead of behaviour, so refactors fail the suite while bugs pass it; and code
comments carry about three lines of story-and-review history per line of code, which is the first
thing an outside contributor sees. Plus five smaller P1 items: sync MCP tools that block the event
loop, an under-tested import layer, inconsistent version and security metadata, ten megabytes of
process artifacts in the clone, and an unsecured cold-open request pattern in the companion. The
work is batched so it costs three Greptile runs, not eight. Affected: the single operator (latency)
and any outside contributor (signal-to-noise). v0.5.0 is already tagged; everything here is 0.6.0.

## Capabilities

- **CAP-1** — Indexed exact card lookup and single-transaction import
  - **intent:** `lookup_card_by_name`, `add_card_to_deck`, and each line of `import_decklist`
    resolve a card name case-insensitively through an index, and an import commits once.
  - **success:** The query plan for an exact-name lookup shows an index search, not a table scan; a
    lookup takes about 1 ms; a 100-line Commander import completes in under 0.5 s with one commit
    and one reload.

- **CAP-2** — Search, index, and initialise tools run off the event loop
  - **intent:** `semantic_search_cards`, `find_similar_cards`, `build_search_index`, and the
    aggregate and parse passes of `initialize_database` do their CPU and blocking I/O off the
    FastMCP event loop.
  - **success:** A second tool call (or MCP ping) completes while `build_search_index` is running;
    the `server.py` module docstring no longer claims FastMCP threadpools sync tools.

- **CAP-3** — Companion cold-open request diet
  - **intent:** Opening the companion on an active deck fetches the deck list without hydrating
    every deck's card rows, receives the deck's full card objects embedded in the deck-detail
    response rather than one request per card, serves card JSON cacheably, answers image requests
    from the disk cache before touching the database, shows nothing until the active-deck answer
    lands, and ships the hero as a hashed, recompressed asset.
  - **success:** A cold open with an active deck issues one deck-detail request and no per-card
    requests and no hero request; the card route sends a cache header; the committed OpenAPI
    schema and generated types reflect the embedded cards; the `cdp_harness budget` median drops
    by at least 150 ms against the 529 ms baseline in a quiet run.

- **CAP-4** — Provenance out of code comments
  - **intent:** Comments and docstrings in `src/`, `ui/src/`, `ci.yml`, `eslint.config.js`,
    `ui/package.json`, and `ui/README.md` keep the invariant they protect and drop story ids, dates,
    review rounds, reviewer names, and retracted predictions.
  - **success:** A grep of `src/` and `ui/src/` for the maintainer's name, "Greptile", "review
    round", "ruling", and `2026-` dates returns nothing; each of the six files above 65% comment
    share drops below 50%; every retained comment states a why, not a when or who.

- **CAP-5** — Lint-as-tests removed
  - **intent:** Tests that scan source text, assert docstring prose, pin constant values, test the
    scanners themselves, or assert README/PRD wording are deleted or converted into stylelint and
    eslint rules; the three docs-drift suites are deleted.
  - **success:** Only the retained gates named in Constraints read source or CSS text; no test
    asserts on a `__doc__` or a bare constant equality; `test_companion_docs.py`,
    `test_prd_reconciliation.py`, and `test_image_cache_docs.py` are gone, with only the two
    "documented port and filename equal the shipped constant" checks relocated; the Python unit job
    is at least 25% faster; the `ui/tests` node project runs without its 180 s timeout, with
    ESLint-invoking and Vite-booting tests behind a separate script.

- **CAP-6** — Behaviour tests where the audit found holes
  - **intent:** The Spellbook import orchestration, the Scryfall bulk download paths, the combo
    snapshot repository reads, and every registered MCP tool are exercised through their real
    entry points.
  - **success:** `spellbook.py`, `scryfall_api.py`, and `combo_snapshot.py` each reach 85% line
    coverage; every tool registered on the server has one `call_tool` round trip in
    `tests/integration/test_mcp_tools.py`, including the four `companion_show_*` happy paths.

- **CAP-7** — Version and security metadata current
  - **intent:** The package version has one source of truth and the security policy names what is
    actually supported and exposed.
  - **success:** `src.__version__` equals the pyproject version without a literal; `ui/package.json`
    carries the same version; `SECURITY.md` supports the latest 0.x line and describes the companion
    HTTP and WebSocket surface.

- **CAP-8** — Process artifacts out of master
  - **intent:** Story files, sprint status, retros, and the deferred-work ledger move to an orphan
    `process` branch in the same repo, readable by the bmad skills through a worktree; planning
    artifacts (PRD, architecture, UX, research, specs) remain on master; local machine paths are
    gone and guarded.
  - **success:** `git ls-files _bmad-output/implementation-artifacts` is empty on master and
    non-empty on `process`; `bmad-sprint-planning status` still resolves `sprint-status.yaml`;
    `git grep` for the maintainer's local path returns nothing on master; a pre-commit hook
    rejects it.

- **CAP-9** — Tracked clutter and ignore rules *(rider, audit P2 item 17)*
  - **intent:** No build cache is tracked and no future source directory can be silently ignored.
  - **success:** Nothing under `node_modules/` is tracked; `git check-ignore ui/src/lib/x.ts` reports
    no match; the pending `.gitignore` change is committed.

- **CAP-10** — Bounded MCP inputs and honest tool annotations *(rider, audit P2 item 11)*
  - **intent:** Every LLM-supplied tool argument has a ceiling; the two wipe-and-rebuild tools
    declare themselves destructive; the HTTP MCP transports stop being advertised.
  - **success:** `add_card_to_deck` rejects a quantity above the import cap; deck name, strategy,
    tag length, and tag count are capped; `page` and mana bounds reject non-finite values without
    raising; `initialize_database` and `build_search_index` carry a destructive annotation;
    `.env.example` no longer mentions `sse` or `streamable-http`, the env-var code path is left in
    place, and `SECURITY.md` names stdio as the supported transport.

- **CAP-11** — One round trip per companion push, lazy embedder import *(rider, audit P2 item 18)*
  - **intent:** A companion push reuses one client and skips the health probe; the MCP server does
    not import the embedding stack until a semantic tool runs.
  - **success:** A push makes one HTTP request; a refused connection still yields `app_not_running`;
    `import src.mcp_server.server` does not import `fastembed`.

## Constraints

- Exactly three Greptile-reviewed PRs: tests (CAP-5, CAP-6), MCP latency (CAP-1, CAP-2, CAP-11),
  cold open (CAP-3). Everything else (CAP-4, CAP-7, CAP-8, CAP-9, CAP-10) lands without Greptile.
  Grouping and preflight are in `batches.md`.
- CAP-5 merges before CAP-4 and CAP-3: the prose-asserting and CSS-text tests would otherwise fail
  a comment prune and a Welcome-panel change for no behavioural reason.
- The full local gate runs before the first push of each Greptile PR; a formatting or drift
  fix-up pushed afterwards burns a review.
- Generated artifacts (`plugin/`, `src/companion/app/static/`, `ui/src/api/openapi.json` and
  `types.d.ts`) are rebuilt and committed in the same PR as the change that moves them; CI drift
  checks fail otherwise.
- Retained gates that may read source or CSS text: `test_import_boundary.py` boundary checks,
  `test_viewer_freeze.py` shrunk to about three tests, `test_openapi_contract.py`,
  `ui/tests/tokens.test.ts`, `package-contract.test.ts`, `no-scryfall-hosts.test.ts`.
- Layering (`data → logic → mcp_server`, the companion import boundary, the single port literal)
  and `mypy --strict` on both platforms stay green; no new UI runtime dependency.
- Companion security invariants (loopback bind, exact Host and Origin checks, single-use tickets,
  bearer compare, 64 KB body cap, image-host allow-list) are not touched by CAP-3.
- The comment prune keeps the sentence that states the invariant; `AD-nn` citations may stay where
  they link a live architecture decision.
- The 0.5.0 tag and CHANGELOG entry are not amended; all of this is `[Unreleased]` toward 0.6.0.

## Non-goals

- Renaming the `src` package or moving `setup.py` (audit item 10).
- FTS5 or a shared `json_each` filter helper for `search_cards` (item 12).
- Deduplicating helpers, splitting `images.py`, `cdp_harness.py`, `AgentViewsNav.tsx`, or
  deleting `src/viewer` (items 13, 19).
- Re-scoping test fixtures or replacing real timers (item 14); splitting `App.test.tsx` (item 15).
- UI payload validation, error boundaries (item 9); docs refresh and README restructure (item 20).
- Coverage gates, wider ruff rules, mypy on tests, dependabot, job timeouts, release workflow,
  `npm audit fix` (item 16).
- Rewriting git history to drop the 3.5 MB PNG or the ledger blobs.

## Success signal

Three Greptile-reviewed PRs and the no-Greptile PRs are merged to master with CI green. A 100-line
deck import runs in under half a second, a concurrent tool call answers while the index builds, a
quiet `cdp_harness budget` run reports a median at least 150 ms under 529, the Python unit job is a
quarter faster with the import layer at 85%, and `git grep` for the maintainer's name and local path
across `src/`, `ui/src/`, and the tracked tree comes back empty.

## Assumptions

- The three P2 riders (CAP-9, CAP-10, CAP-11) are in scope because the batching plan folded them in
  as small changes and no objection was raised.
- Non-behavioural PRs (metadata, deletions, comment prune, artifact move) skip Greptile under the
  standing rule that only code changes get adversarial review.
- The bmad skills that read `sprint-status.yaml` can be pointed at a worktree of the `process`
  branch; if a skill hard-codes the master path, that config change is part of CAP-8.
