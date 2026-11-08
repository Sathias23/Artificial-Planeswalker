---
type: review-plan
title: "Full codebase review: code quality, optimisation and architecture"
created: '2026-11-07'
status: draft
reviewer_model: claude-opus-5-5
reviewed_revision: ee0263d652a46f021515860bbc2a19e3dac60eed
context:
  - AGENTS.md
  - CONTRIBUTING.md
  - docs/architecture.md
  - _bmad-output/initiative-artificial-planeswalker/architecture-Artificial-Planeswalker-2026-07-25/architecture-Artificial-Planeswalker-2026-07-25.md
  - docs/quality-review-2026-09-06.md
  - _bmad-output/initiative-artificial-planeswalker/quality-audit-2026-09-03/quality-audit-2026-09-03.md
  - _bmad-output/initiative-artificial-planeswalker/research-codebase-architecture/research-codebase-architecture.md
---

# Full codebase review: code quality, optimisation and architecture

A one-off review of the whole codebase with Claude Opus 5.5, run through BMad skills: an architecture pass, then group-by-group code reviews, then the findings become tickets that `bmad-build` fixes one at a time. This file is both the checklist and the plan handed to every `bmad-code-review` run, so each run reads the intent below and appends its findings to `## Code Review`.

## Intent (what every reviewer is told)

Review the code as it stands on `master`, not a change. Look for:

- **Correctness:** bugs, unhandled failure paths, race conditions, resource leaks, wrong or missing error handling.
- **Code quality:** duplication and near-copies, inconsistent patterns between modules doing the same job, dead code, oversized files or functions, unclear names, comments that no longer match the code.
- **Optimisation:** wasted queries (N+1, missing indexes, unbounded reads), blocking work on the event loop, repeated work that could be cached, needless re-renders and request storms in the UI, bundle weight.
- **Architecture:** drift from `docs/architecture.md` and the AD-n decisions; layer violations (data, then logic, then mcp_server; `src/data` and `src/logic` framework-free); AD-2 (nothing under `src/companion/` writes) and AD-3 (mcp_server never imports `src/companion/app/`); stateless tools; the frozen viewer (AD-15); boundaries that leak.
- **Test design:** behaviour tested through real entry points, gaps on risky paths, slow or brittle tests, tests that assert nothing.

Out of scope: style the linters already enforce (ruff, Prettier, mypy), the generated artifacts (`plugin/`, `src/companion/app/static/`, `ui/src/api/types.d.ts`, `ui/src/api/openapi.json`), and findings already fixed by the 2026-09-03 audit or the 2026-09-06 quality review. Read both first; do not re-raise what they closed.

## Steps

### 0. Prerequisites

- [x] PR #116 (v7 migration) merged, so this file and the ticket tree are on `master`.
- [x] Commit this file straight to `master` (planning artifact).
- [x] Record the reviewed revision: `ee0263d` (the PR #116 merge), in the frontmatter. All runs review that same commit.
- [x] Database and semantic index built (`python setup.py`, `uv run python scripts/build_card_embeddings.py`), so reviewers can run integration tests and the search sanity eval if they need evidence. (2026-11-08: refreshed with `scripts/import_scryfall_data.py`, then the incremental embeddings build.)
- [ ] Budget: a thorough `bmad-code-review` run takes 30 minutes or more; the plan below is about 20 runs. Run groups in separate fresh sessions.

### 1. Architecture pass (`bmad-deep-recon`)

Do this first: it frames every group review and catches what no single group can see.

- [x] Run `bmad-deep-recon` in "research the codebase" mode with this question: *"How far has the code drifted from `docs/architecture.md` and the AD-n decisions in the 2026-07-25 architecture spine? Where are the layer boundaries, the AD-2/AD-3 rules and the stateless-tool rule bent or worked around; where do the MCP tools, the companion backend and the UI duplicate logic that should live once; and what are the main performance risks (database access patterns, event-loop blocking, sqlite-vec usage, UI request patterns)?"*
- [x] Its report lands in `research-codebase-architecture/` in the initiative. Approve any ADRs it proposes only when they record a real decision. (2026-11-07: report at `research-codebase-architecture/research-codebase-architecture.md`, findings F1-F10; no ADR proposed.)
- [x] Add the report path to this file's `context:` list so every group review reads it.

### 2. Group reviews (`bmad-code-review`)

One run per group, in a fresh session each. Say: *"run code review, no-code, on the file list for group <id> in `_bmad-output/initiative-artificial-planeswalker/review-codebase-2026-11/review-codebase-2026-11.md`; this file is the plan."*

- **File list, not a diff.** Give the paths below; the review takes whole files.
- **This file is the plan.** It is read in full, its `context:` documents are loaded, and findings are appended to `## Code Review` as a dated block per run.
- **`no-code`.** The audit changes nothing; fixes come in step 5, one ticket at a time.
- **Thorough** (the default): four independent lenses. Use `quick` only for groups marked quick.
- **At triage, choose "leave as action items"** so findings stay in this file rather than being patched.
- Keep each group under about 3,000 lines; the review warns and offers to split above that.

| Id | Group | Paths | Lines | Extra focus | Done |
|---|---|---|---|---|---|
| B1 | Data model and database | `src/data/models/`, `src/data/schemas/`, `src/data/database.py`, `src/data/import_state.py` | ~1,500 | The connect-hook data repairs, JSON-in-Text `*_list` properties, `noload` relationships, the `# noqa: F401` model imports | [ ] |
| B2 | Repositories | `src/data/repositories/` | ~2,000 | `_UNSET` vs `None`, commit/refresh/rollback on every write method, Pydantic schemas out (never ORM models), N+1 loads, `deck.py` (1,184 lines) size | [x] |
| B3 | Importers | `src/data/importers/`, `scripts/import_scryfall_data.py` | ~2,400 | Transaction scope, memory use on bulk data, idempotent re-import, WUBRG order | [ ] |
| B4 | Analysis logic: validator, curve, synergy | `src/logic/__init__.py`, `deck_validator.py`, `mana_curve.py`, `synergy.py` | ~2,000 | Observational only, framework-free, rule coverage | [x] |
| B5 | Power assessment | `src/logic/assessment/` | ~2,850 | Scoring determinism, combo credit, duplication with the validator and synergy | [ ] |
| B6 | Semantic search | `src/search/`, `scripts/build_card_embeddings.py` | ~1,900 | `asyncio.to_thread` with its own connection, every KNN with `k`/`LIMIT` (over-fetch then JOIN-filter, `_MAX_LIMIT` 50), `index_unavailable` path; any suggested change needs a query-to-expected-card recall check | [x] |
| B7 | MCP server core | `src/mcp_server/__init__.py`, `server.py`, `__main__.py`; `tools/messages.py`, `initialize_database.py`, `build_search_index.py`, `view_deck.py` | ~2,000 | Tool registration, stdio-only, stderr diagnostics, no per-session state, `server.py` (1,221 lines) size | [ ] |
| B8 | MCP deck and companion tools | `src/mcp_server/tools/deck_management.py`, `deck_import.py`, `companion.py` | ~2,350 | Status vocabulary consistency, `deck_changed` emitted only on `ok` and after the session closes, push payload bounds, tool docstrings (they are the LLM-facing descriptions) | [ ] |
| B9 | MCP card and analysis tools | `src/mcp_server/tools/assess_deck_power.py`, `compare_deck_power.py`, `deck_analysis.py`, `find_similar.py`, `semantic_search.py`, `card_search.py`, `card_lookup.py` | ~2,700 | Same status vocabulary, observational analysis, the five shipped skills match each tool's real parameters | [ ] |
| B10 | Companion contracts and client | `src/companion/contracts.py`, `client.py`, `discovery.py` | ~2,200 | `contracts.py` (1,361 lines) size, AD-9 staleness window, the import boundary (mcp_server may import only this leaf) | [ ] |
| B11 | Companion backend: routes and wiring | `src/companion/app/routes/`, `__init__.py`, `main.py`, `server.py`, `deps.py`, `state.py`, `spa.py` | ~2,560 | AD-2 read-only, route contracts vs OpenAPI, error responses | [ ] |
| B12 | Companion backend: images, socket, safety | `src/companion/app/images.py`, `errors.py`, `ws.py`, `body_cap.py`, `security.py`, `singleton.py` | ~2,680 | Image fetch and cache bounds, the per-platform `singleton.py` (`msvcrt` vs `fcntl`), lazy `%`-style logging | [x] |
| B13 | Build and maintenance scripts (quick) | `scripts/` except those in B3 and B6 | ~2,700 | `build_plugin.py` correctness, `migrate_*.py` safety, probe harnesses | [ ] |
| F1 | UI API and state, part 1 | `ui/src/api/` (hand-written files only), `ui/src/state/` first half | ~2,700 | Request deduping and cancellation, error states | [ ] |
| F2 | UI state, part 2 | `ui/src/state/` second half (`agentView.ts`, `deck.ts`, `cards.ts`) | ~2,700 | `HISTORY_CAP` retention, revisit semantics, derived-state duplication | [x] |
| F3 | UI components | `ui/src/components/` | ~3,000 (split if over) | Accessibility, duplicated presentational patterns, CSS token use | [ ] |
| F4–F7 | UI containers | `ui/src/containers/`, split into four groups of about 3,000 lines by folder | ~12,100 | Re-render and request storms, cold-open cost (the release-gating budget), data fetching in components | [ ] |
| F8 | UI shell and styles (quick) | `ui/src/App.tsx`, `main.tsx`, `index.css`, `ui/src/styles/` | ~1,200 | Token drift from DESIGN.md, global CSS | [ ] |

Split `ui/src/containers/` into F4–F7 and `ui/src/state/` into F1/F2 by folder when each run starts; record the exact file list in that run's Code Review block.

### 3. Tests and tooling pass

- [ ] **T1, `bmad-code-review` quick, per suite:** `tests/unit/`, `tests/integration/`, `ui/src/**/*.test.*`, `ui/tests/`, focused on test design only: real-entry-point rule, duplicated fixtures, slow tests, assertion-free tests, missing coverage on the risky paths the group reviews found. `ui/src/App.test.tsx` (7,229 lines) deserves its own look.
- [ ] **T2, `bmad-review` on the configuration:** `pyproject.toml`, `.pre-commit-config.yaml`, `.github/workflows/`, `ui/package.json`, `ui/vite.config.*`, `ui/tsconfig*.json`. Look for gate gaps between local and CI, slow CI steps, pinned versions that are stale.

### 4. Consolidate the findings

- [ ] Read every `## Code Review` block. Merge duplicates found by several groups into one finding and keep the strongest evidence.
- [ ] Group the survivors into themes (for example: repository consistency, tool status vocabulary, companion image path, UI request patterns, test suite cost).
- [ ] For each theme: what it costs today, what fixing it buys, and how wide it is. Drop themes whose fix adds more complexity than it removes.
- [ ] Mark each finding **fix**, **defer** (real, not worth it now; goes to `deferred-work.md`) or **decide** (depends on what Brad wants).
- [ ] Walk the **decide** items with Brad and record each answer as a dated Decision in `## Summary`.
- [ ] Write `## Summary`: themes, counts per theme, and the ordered fix list.

### 5. Turn the fix list into tickets (Sofia, `bmad-agent-po`)

- [ ] Ask Sofia: *"write an epic for the codebase quality pass from `review-codebase-2026-11.md`, Summary section, and slice it into stories"*. Expected: `epic-codebase-quality-pass` under the initiative, one story per theme or per independently shippable fix, each covering the findings it resolves.
- [ ] Order stories so test gaps on a path are closed before that path is refactored.
- [ ] Mark stories that change a tool contract, the OpenAPI contract or a schema with `plan_checkpoint = true`.

### 6. Fix (`bmad-build`, one story at a time)

- [ ] One `bmad-build` per story, on its own branch, PR to `master`. Refactors never ride along with feature work.
- [ ] Each PR runs the full gate (`AGENTS.md`, Running and verifying), regenerates what the change touches (`plugin/`, `npm run gen:api`) and gets its Greptile review.
- [ ] Before calling a pattern fix done, grep for every instance of the pattern, not just the cited line.
- [ ] A semantic-search change carries its recall sanity eval.

### 7. Close out

- [ ] `bmad-retrospective` on `epic-codebase-quality-pass` once every story is done or dropped.
- [ ] `bmad-project-context` to add any new repo rule the review produced to `AGENTS.md` (only rules an agent would otherwise get wrong).
- [ ] Set this file's `status: done`.

## Code Review

<!-- Each bmad-code-review run appends a dated block here: group id, exact file list, reviewed revision, findings. -->

### 2026-11-08 — B2 Repositories

**Code review complete.** 7 `decision-needed`, 13 `patch`, 0 `defer`, 13 rejected.

- **Group:** B2. **Reviewed revision:** `ee0263d652a46f021515860bbc2a19e3dac60eed` (no change under `src/data/repositories/` up to `e3b70d9`).
- **Files (1,978 lines):** `src/data/repositories/__init__.py`, `base.py`, `card.py`, `combo_snapshot.py`, `deck.py`.
- **Mode:** no-code, thorough; lenses blind-hunter, edge-case-hunter, verification-gap, intent-alignment (none failed). Triage: leave as action items.
- **Overlap with the architecture report:** F6 is research §7; F8, F10 and F12 are research F10 (F10 also F9); F7 touches the `oracle_id` index point in research F10. Recorded here with the repository-level evidence; merge them in step 4.
- **What holds:** every public method returns Pydantic schemas or plain values (only private helpers return `DeckModel`); every writer rolls back on `IntegrityError` / `DatabaseError` before re-raising and follows the snapshot-first `_reload_committed` discipline; `_UNSET` is used for the nullable `strategy` and `tags` (`name` is NOT NULL, so `None` as "omitted" is right); identity is WUBRG-ordered from `color_identity` on every card mutation; timestamps are aware UTC; imports are SQLAlchemy and `src.data` only. `deck.py`'s 1,184 lines: about 120 are `merge_decks` and the merge strategy, which have no caller (F8, F12); the rest is cohesive writer code.

- [ ] [Review][Decision] `at_most` promises colour identity but filters `colors` — `search_advanced`'s docstring says "Only these colors or fewer (color identity/subset)" and its example says "fit in white-blue color identity", but the predicate tests `CardModel.colors`, so Golgari Signet (`colors=[]`, identity B/G) passes `at_most=["W"]`; a Commander search silently returns off-identity cards. The tool docstrings (`server.py:248`, `:1056`, `:1123`) say only "a subset". [`src/data/repositories/card.py:435`, `:463`, `:517-524`] Options: (a) filter `at_most` on `color_identity` (a tool behaviour change; check the semantic tools' `at_most` matches); (b) keep `colors` and correct the repository docstring and example to say "card colours, not identity". Recommended: (b) now, (a) as its own story if Commander searches need it — (a) changes a tool contract and needs the skills and the semantic tools to agree.
- [ ] [Review][Decision] `find_by_name_partial` is unbounded — no `LIMIT`; `lookup_card` and `_resolve_card` validate every match into `Card` and then slice to `_MAX_MATCHES`, so a two-letter query materialises thousands of rows; `lookup_card`'s message reports the full count. [`src/data/repositories/card.py:246-255`] Options: (a) add a bounded fetch plus a separate count (new parameter, one more query); (b) cap the fetch at `_MAX_MATCHES + 1` and change the message to "more than N"; (c) leave it. Recommended: (b) — one-line bound, and the exact count adds nothing for the caller deciding to refine.
- [ ] [Review][Decision] `search_advanced` evaluates the filter set several times — `_apply_unique_oracle_filter` repeats every predicate in the CTE and the outer query, and the count wraps the whole statement again, over unindexable `%…%` LIKEs and an unindexed `GROUP BY oracle_id`. [`src/data/repositories/card.py:115-124`, `:577`] Options: (a) measure with EXPLAIN QUERY PLAN and timings on the real `cards.db` first, then rewrite (one `ROW_NUMBER() OVER (PARTITION BY oracle_id)` pass, or an `oracle_id` index); (b) leave it. Recommended: (a) — research F10 already says any index needs a measured case.
- [ ] [Review][Decision] `merge_decks` is not atomic — each source row goes through the committing `update_card_quantity` / `add_card_to_deck`, so a failure on row k leaves rows 1..k-1 committed and the outer rollback undoes nothing, despite the docstring. No caller in `src/`. [`src/data/repositories/deck.py:1099-1116`] Options: (a) delete `merge_decks` and `MergeStrategy` with their tests; (b) rewrite it to stage every row and commit once, like `add_cards_to_deck`. Recommended: (a) — no caller, and a future merge tool would be designed against the tool contract anyway.
- [ ] [Review][Decision] `merge_decks` writes unguarded — merging a deck into itself with `COMBINE` doubles every quantity; `COMBINE` can exceed `MAX_CARD_QUANTITY` (250); source commander flags are copied, so the target can end with three or more commanders. [`src/data/repositories/deck.py:1056-1116`] Options: same as the atomicity decision (delete, or add the guards in the rewrite). Recommended: decide together with the item above; deletion closes both.
- [ ] [Review][Decision] `find_deck_by_name` raises on two matches — `scalar_one_or_none()` over `ILIKE '%name%'` raises `MultipleResultsFound` (the docstring's own "mono red" example), though the docstring promises the first match; no order is defined. No caller in `src/`; `scripts/view_deck.py:47` avoids it for this reason. [`src/data/repositories/deck.py:451-453`] Options: (a) delete it; (b) add an order and `.first()`. Recommended: (a) — no caller.
- [ ] [Review][Decision] Unused repository surface — no `src/` caller for `merge_decks`, `MergeStrategy`, `find_deck_by_name`, `update_deck_color_identity`, `ComboSnapshotRepository.snapshot_is_available` / `get_metadata` (the `get_snapshot_state` docstring warns they can disagree) or `search_advanced(limit=…)` ("DEPRECATED"); `find_by_colors`, `find_by_type` and `search_by_keywords` are used only by `scripts/validate_data_layer.py`. [`src/data/repositories/deck.py`, `card.py`, `combo_snapshot.py`] Options: (a) delete all of them (and repoint or drop the script's checks); (b) delete only the ones with latent bugs (merge, `find_deck_by_name`); (c) keep. Recommended: (a) — five-plus fewer public methods and two latent bugs gone; tests that only cover them go too.
- [ ] [Review][Patch] `at_most` with `colors=[]` returns every card — the `if colors:` branch is skipped and the empty special case covers `exact` only, so "at most no colours" applies no colour filter; `search_cards` accepts `[]` [`src/data/repositories/card.py:494-527`]
- [ ] [Review][Patch] `exact` mode miscounts duplicate colours — the length check compares with `len(colors)`, and the tool allows `["W","W"]`, which then returns two-colour white cards [`src/data/repositories/card.py:515`]
- [ ] [Review][Patch] Format key interpolated raw into the JSON path — `f"$.{format_filter}"` with no case folding or quoting: `"Standard"` silently matches nothing, and `lookup_card_by_name` (which, unlike `search_cards`, does not blank-normalise `format`) turns `""` or a quote into a malformed-path `OperationalError` [`src/data/repositories/card.py:66`]
- [ ] [Review][Patch] MCP `list_decks` hydrates every card of every deck to show three counts — switch the tool to `list_deck_summaries` (same `DeckSummary` values, measured 99 → 3 ms on the companion route in #109) [`src/mcp_server/tools/deck_management.py:297`, `src/data/repositories/deck.py:344-372`]
- [ ] [Review][Patch] Printed-name matching is untested — every fixture sets `printed_name=None`, so dropping the `printed_name` term from `find_by_name_exact` or `find_by_name_partial` passes the suite; add a card whose printed name differs and look it up by that name both ways [`src/data/repositories/card.py:196-201`, `:246-248`]
- [ ] [Review][Patch] The post-commit reload tolerates only `DatabaseError` — a row deleted by another server process between commit and reload raises `NoResultFound` (`scalar_one`) or `KeyError` (`by_key[...]`), reporting a landed write as failed [`src/data/repositories/deck.py:570`, `:680`, `:918`]
- [ ] [Review][Patch] LIKE wildcards in user text are not escaped — `%` and `_` act as wildcards in the partial-name, type, keyword, oracle-phrase and deck-name paths [`src/data/repositories/card.py:247`, `:331`, `:371`, `:534-546`; `src/data/repositories/deck.py:451`]
- [ ] [Review][Patch] `create_deck` documents a UNIQUE name constraint that does not exist (`decks.name` is `index=True` only) [`src/data/repositories/deck.py:83`]
- [ ] [Review][Patch] `clone_deck` runs its post-commit reload and then always returns the pre-reload snapshot, unlike every sibling writer [`src/data/repositories/deck.py:194-197`]
- [ ] [Review][Patch] No-op and not-found branches handle the transaction differently — `remove_card_from_deck` and the equal-quantity branch roll back, the not-found branches of `update_card_quantity` and `update_deck` do not; pick one rule and state it [`src/data/repositories/deck.py:725`, `:799`, `:805`]
- [ ] [Review][Patch] `rarity=[]` builds an empty `or_()` (SQLAlchemy 2 deprecation warning; filter silently dropped) [`src/data/repositories/card.py:559-565`]
- [ ] [Review][Patch] Pagination order has no unique tie-break — `ORDER BY cmc, name` with `OFFSET` can repeat or skip tied rows across pages; add `id` [`src/data/repositories/card.py:585`]
- [ ] [Review][Patch] Boilerplate — in-method re-imports of `func`, `or_`, `String`, `cast`, `not_`; `__init__` overrides that only call `super()`; `FormatFilter` / `GamesFilter` aliases that add nothing [`src/data/repositories/card.py:17-37`, `:62`, `:89`, `:192`, `:243`, `:290`, `:368`, `:481`, `:495`; `src/data/repositories/deck.py:51-57`]

**Rejected**

- `false` — `search_advanced` `page_size=0` / negative / `page<1`: the sole caller, `search_cards`, rejects them (`card_search.py:124-127`).
- `false` — a second default clone fails on a UNIQUE name: there is no UNIQUE constraint on `decks.name`.
- `false` — `FlushError` escapes `add_card_to_deck` on an identity-map conflict: SQLAlchemy 2 warns and emits the INSERT; the violation arrives as the caught `IntegrityError`.
- `false` — not-found branches pin a stale WAL read snapshot: pysqlite's legacy mode issues no BEGIN for SELECT (relied on at `deck.py:149-150`), and tool sessions close per call.
- `false` — `update_deck` persists a blank name: the update tool rejects it.
- `false` — combo meta reads raise on several rows: `CHECK (id = 1)` plus the primary key allow one row.
- `false` — `at_most` with lowercase colours: the tools reject anything outside W/U/B/R/G.
- `false` — an invalid `color_mode` silently drops the filter: the MCP boundary validates the `Literal`.
- `false` — an empty partial query matches every card: every caller rejects or blank-normalises empty names; the remaining unbounded-read cost is the `find_by_name_partial` decision above.
- `false` — `update_deck`'s `name` should use `_UNSET`: `decks.name` is NOT NULL, so there is nothing to clear.
- `low` — `AGENTS.md`'s "commit and refresh" is simpler than the snapshot-first reload: the writers do commit then refresh; the sentence simplifies without misleading.

### 2026-11-08 — B4 Analysis logic: validator, curve, synergy

**Code review complete.** 6 `decision-needed`, 18 `patch`, 0 `defer`, 6 rejected.

- **Group:** B4. **Reviewed revision:** `ee0263d652a46f021515860bbc2a19e3dac60eed` (no change under `src/logic/` up to `9d01091`).
- **Files (1,981 lines):** `src/logic/__init__.py`, `deck_validator.py`, `mana_curve.py`, `synergy.py`.
- **Mode:** no-code, thorough; lenses blind-hunter, edge-case-hunter, verification-gap, intent-alignment (none failed). Triage: leave as action items.
- **Evidence gathered read-only from `cards.db`** (39,503 cards, one printing per `oracle_id`): 6 `Basic Snow Land` rows; every sampled card carries exactly the 23 legality keys in `_KNOWN_FORMATS`; multi-face rows such as "Adventurous Eater // Have a Bite" store a zero-length `oracle_text`.
- **Overlap with the architecture report:** F1 is research F2; the MDFC-land decision is research F1 (§6); the dead-validator decision is research F10. Recorded here with the logic-level evidence; merge them in step 4.
- **What holds:** the four modules import only `dataclasses`, `typing`, `logging`, `re`, `pydantic` and `src.data.schemas` (framework-free); every function is pure, and `deck_analysis.py` and the companion `format_check` route only read, so analysis stays observational; `format_check` reimplements no rule and `CHECK_FOR_RULE` is total; the tools pass the mainboard only to the curve and synergy logic (`deck_analysis.py:173`, `:248`); copy limits counted per `card_id` are correct, because the database holds one printing per oracle card.

- [ ] [Review][Decision] Restricted cards are reported as not legal — a card whose legality is `restricted` gets the `format_legality` violation "'X' is not legal in vintage", so one Black Lotus makes a legal Vintage deck read illegal in the tool and on the companion panel. The docstring records this as unmodelled, but the sentence is false. [`src/logic/deck_validator.py:447-453`] Options: (a) model it: a restricted card is legal at 1 copy, and above 1 it is a violation (new wording, perhaps a new rule token, which ripples into `CHECK_FOR_RULE`, the OpenAPI contract and the skills); (b) keep the verdict but say "is restricted in vintage (1 copy allowed); this validator does not count restricted copies"; (c) leave it. Recommended: (a) — `combined_counts` already has the total, so the rule is about five lines; the token decision is the only real cost.
- [ ] [Review][Decision] `analyze_mana_curve` counts an MDFC "Sorcery // Land" as a land — `"Land" in c.type_line` matches either face, so spell-lands lower the spell count and raise the land ratio, and the agent's curve disagrees with the companion's (which reads the front face). [`src/logic/mana_curve.py:74`] Options: (a) front face only, matching the UI now; (b) settle research F1 first (one land definition in `src/logic`, shipped in the deck-detail payload) and fix this as part of it; (c) leave it. Recommended: (b) — fixing one of five land rules in isolation moves the disagreement, it does not remove it.
- [ ] [Review][Decision] Tribal type parsing is ad hoc — payoff patterns are `{type}s?`, so "Other Elves you control" (Imperious Perfect) and Dwarves or Wolves are missed; the type check knows `Tribal` but not `Kindred`, Scryfall's name since 2024; the outer `"Creature" in card.type_line` gate means the `Tribal` branch is dead; `re.split(r"[—-]")` turns "Assembly-Worker" into the tribe "Assembly". [`src/logic/synergy.py:135`, `:150-154`, `:569-573`] Options: (a) narrow fixes: split on the dash with spaces around it, add an irregular-plural map, accept `Kindred` beside `Tribal`, keep the creature gate (and drop the dead branch); (b) as (a), and also let Kindred non-creature spells count as tribe members. Recommended: (a) — (b) changes what "tribal density" means, a call for Brad.
- [ ] [Review][Decision] Deck cohesion is not monotonic in coverage — one non-strong synergy covering more than 40% of the deck, or one strong synergy covering 40-50%, is rated `low`, while the same synergy at 30% is `moderate`. [`src/logic/synergy.py:615-630`] Options: (a) drop the upper bound on the moderate band (`coverage >= 0.2`), so more coverage never rates lower; (b) redesign the thresholds. Recommended: (a) — one-line fix, no new tiers.
- [ ] [Review][Decision] Dead single-card validator surface — `validate_card_addition`, `get_current_card_count` and `ValidationResult` have no `src/` caller, yet they are all `src/logic/__init__.py` exports; the second copy-limit rule counts the mainboard only, hardcodes 4, ignores singleton formats and accepts `quantity <= 0`. [`src/logic/deck_validator.py:28-160`, `src/logic/__init__.py:7-19`] Options: (a) delete them and their tests; make `__init__` export the live API (`validate_deck`, `format_check`, `analyze_mana_curve`, `detect_synergies`) or nothing; (b) rebuild `validate_card_addition` on `validate_deck`'s rule; (c) keep. Recommended: (a) — no caller, and it disagrees with the rule the tools use.
- [ ] [Review][Decision] `generate_contextual_feedback` is about 350 lines of unreachable code with live bugs — the shipped `mana-curve-analysis` skill says no tool reaches it (D-1.6g); inside, the "previous" curve removes every copy of the added card but subtracts one, the `<= 3` early-play threshold fires on every addition so the throttle never throttles, a land is praised as "early-game presence", the neutral range is computed from nothing, the docstring example is wrong, and the `# noqa: E501` is stale. [`src/logic/mana_curve.py:13-31`, `:243-595`] Options: (a) delete it, `CurveFeedback` and the helpers, with their tests; (b) fix it for a future tool. Recommended: (a) — the skill already does this job in the agent's own judgment.
- [ ] [Review][Patch] Snow basics are held to the copy limit — `is_basic_land` tests `"basic land"`, so "Basic Snow Land — Forest" (6 rows in `cards.db`) gets `copy_limit` or `singleton` at 5+ copies; test the `Basic` supertype and `Land` type before the dash [`src/logic/deck_validator.py:65`, `:406`]
- [ ] [Review][Patch] `games` is compared raw — `validate_deck` normalises `format` but not `games`, and the tool validates `game.strip()` then passes the unstripped list, so `games=[" arena"]` flags every card as unavailable [`src/logic/deck_validator.py:455`, `src/mcp_server/tools/deck_analysis.py:315`, `:346`]
- [ ] [Review][Patch] Keyword holders after the first line are missed — `(?:^|,\s*){keyword}` runs without `re.MULTILINE`, so "Flash\nFlying" (Spectral Sailor) has no flying; use `re.MULTILINE` (or the structured `Card.keywords`) [`src/logic/synergy.py:237`]
- [ ] [Review][Patch] Tribal payoffs depend on deck order and lords count twice — payoffs match only tribes already seen in the loop, so a lord ahead of its tribe in `deck_cards` (UUID order) is missed; a creature that is its own tribe's payoff is counted as creature and payoff, inflating `total_cards` and strength; collect tribes in a first pass [`src/logic/synergy.py:130-169`]
- [ ] [Review][Patch] Multi-face cards are invisible to every synergy detector — their rules text lives in `card_faces` and the top-level `oracle_text` is `""` (verified in `cards.db`); reuse the face-joining fallback in `src/logic/assessment/classifiers.py:99-115` [`src/logic/synergy.py:144`, `:231`, `:346`, `:409`, `:474`]
- [ ] [Review][Patch] Mechanic combos accept one half only — each requires `outlets + triggers >= 4` and never both halves, so four death-trigger cards with no outlet report "0 sacrifice outlets enable 4 cards"; a card matching both halves counts twice [`src/logic/synergy.py:365-368`, `:433-436`, `:497-500`]
- [ ] [Review][Patch] Cohesion `high` is never asserted — `test_high_cohesion_multiple_synergies` accepts `moderate` or `high`, and its comment says two synergies where the fixture makes three; assert `high` and cover each `high` branch [`tests/unit/logic/test_synergy.py:594-635`]
- [ ] [Review][Patch] No test asserts a detector returns `strength == "strong"` — every detector assertion expects `moderate`; add a >30% fixture for tribal and the mechanic combos [`tests/unit/logic/test_synergy.py:226`, `:316`, `:414`, `:467`, `:508`]
- [ ] [Review][Patch] `test_lifelink_synergy_detection` asserts `len(...) >= 0` — rewrite it with a lifelink payoff and a keyword after a comma ("Flying, lifelink"), so the `,\s*` branch is pinned [`tests/unit/logic/test_synergy.py:352`]
- [ ] [Review][Patch] Land recommendations are checked as substrings — assert the exact "Add ~4 lands (target: 24 lands)" / "Remove ~6 lands (target: 24 lands)" strings [`tests/unit/logic/test_mana_curve.py:125`, `:136`]
- [ ] [Review][Patch] The "any requested platform" rule is untested with two games — add `["paper", "arena"]` (paper-only card passes) and `["arena", "mtgo"]` (it fails) [`tests/unit/logic/test_deck_validator.py`]
- [ ] [Review][Patch] `_KNOWN_FORMATS` is never checked against real legality keys — the unit pin only checks size 23 and the subset; add an `integration` test that the built database's key set equals it, so a Scryfall rename cannot silently make a format unvalidatable [`tests/unit/logic/test_format_check.py:668-674`]
- [ ] [Review][Patch] Curve thresholds are repeated magic numbers — `_detect_issues` and `_generate_recommendations` each restate 35/45/40/3.5/0.25 and the early-play count; name them once [`src/logic/mana_curve.py:146-234`]
- [ ] [Review][Patch] The strength tiering is copied five times — one helper; note its `weak` arm is reachable only at exactly 10%, and `_calculate_deck_cohesion` ignores its `deck_size` [`src/logic/synergy.py:177-183`, `:278-284`, `:376-382`, `:444-450`, `:508-514`, `:587`]
- [ ] [Review][Patch] Synergy output order varies between processes — `list(set(...))` and iteration over the `COMMON_KEYWORDS` set follow per-process string hashing; keep first-seen or sorted order [`src/logic/synergy.py:20`, `:186`, `:235`, `:287`, `:384`, `:452`, `:516`]
- [ ] [Review][Patch] A tiny deck is told "Add ~0 lands (target: 0 lands)" — `int()` truncates the 40% target to 0 below three cards [`src/logic/mana_curve.py:203-206`]
- [ ] [Review][Patch] Unreachable `if dc.card is None` guard — `DeckCard.card` is required; drop it [`src/logic/deck_validator.py:395`]
- [ ] [Review][Patch] The land/spell split compares Pydantic models pairwise (`c not in lands`) and every `int(x.cmc) if x.cmc is not None else 0` is dead (`cmc: float`); split in one pass with one `_cmc` helper [`src/logic/mana_curve.py:74-88`]

**Rejected**

- `false` — a blank `format` yields the detail "'' is not a recognized format": the tool defaults blank to `standard`, and `format_check` drops the `unknown_format` detail for `_unanswerable` prose.
- `false` — a card missing a legality key is reported "not legal" with certainty: Scryfall emits all 23 keys on every card; key drift is the `_KNOWN_FORMATS` patch above.
- `false` — an all-land deck is wrongly told it has curve gaps and few early plays: both statements are true of it.
- `false` — sideboard cards inflate synergy counts: the tool passes the mainboard only (`deck_analysis.py:248`).
- `not a defect` — the evidence for dead code, test design and observational behaviour lies outside the four files (intent-alignment): descriptive, and the other lenses read the callers and tests.
- `not a defect` — framework-free layering (intent-alignment): a confirmation, recorded under What holds.

### 2026-11-08 — B6 Semantic search

**Code review complete.** 3 `decision-needed`, 16 `patch`, 0 `defer`, 11 rejected.

- **Group:** B6. **Reviewed revision:** `ee0263d652a46f021515860bbc2a19e3dac60eed` (no change under `src/search/` or to `scripts/build_card_embeddings.py` up to `9cf0d9b`).
- **Files (1,756 lines):** `src/search/__init__.py`, `connection.py`, `embedder.py`, `index_builder.py`, `query.py`, `schema.py`; `scripts/build_card_embeddings.py`.
- **Mode:** no-code, thorough; lenses blind-hunter, edge-case-hunter, verification-gap, intent-alignment (none failed). Triage: leave as action items.
- **Evidence gathered read-only from `cards.db`** (stdlib `sqlite3` in `mode=ro` with sqlite-vec loaded; nothing written):
  - 39,503 cards, 39,503 distinct `oracle_id`.
  - `card_vec` and `card_embedding_meta` hold 53,975 rows each, so 14,472 (26.8%) are orphans with no `cards` row. Every card has a hash.
  - For six seed vectors (Lightning Bolt, Llanowar Elves, Counterspell, Glorybringer, Sol Ring, Wrath of God), the k=200 KNN joins only 117–157 rows to `cards`. After the legality filter, 5–24 survive for `standard`, 7–97 for `pauper`, and 41–72 for `arena`.
  - Probes: `fetchmany(0)` returns `[]`. `json_extract(…, '$.Standard')` returns NULL where `'$.standard'` matches.
  - No card stores `keywords` or `colors` as NULL or as JSON `null`.
- **Overlap with the architecture report:** the KNN-starvation decision is research F7, now with measured numbers. The orphan decision extends research F6 (the prune instruction the MCP tool cannot follow) with its measured cost. The format-case patch repeats B2's `card.py:66` patch on the semantic path. The `colors=[]` patch pairs with B2's `at_most` `colors=[]` patch. Merge them in step 4.
- **What holds:**
  - Every tool call into `src/search` runs in `asyncio.to_thread` and takes its connection inside the worker (`server.py:1074-1090`, `:1143-1158`, `:1217`). `ConnectionFactory` hands out one connection per thread.
  - The only KNN, in `hybrid_search`, always binds `k`. Both tools cap `limit` at `_MAX_LIMIT` 50 and use the default k=200.
  - `index_unavailable` is reached through `index_is_populated` after `is_database_initialized`, in both tools.
  - The embedder loads lazily, behind a double-checked lock.
  - Builder writes are one transaction per chunk, and the metadata-refresh path (the 2026-09-06 review's P2 #5) is in place.
  - `src/search` imports only `src.paths` and `src.data.import_state`, with no framework.
  - A recall eval exists (`tests/integration/search/test_rag_eval.py`) for the changes below that touch ranking.

- [ ] [Review][Decision] Fixed k=200 starves filtered semantic results — `hybrid_search` takes the 200 nearest vectors and only then applies the legality and games JOIN filters. Measured on the live index (above): a `standard` filter leaves 5–24 candidates, so `limit=10` can come back short (Sol Ring 5, Llanowar Elves 6) and `limit=50` always does, while hundreds of legal matches exist. Nothing tells the caller the window ran out. [`src/search/query.py:336-360`, `:389`] Options: (a) adaptive over-fetch: when the result is short and the KNN filled `k`, retry with a larger `k` (for example ×4, capped at a few thousand); (b) a larger fixed `k` scaled by filter selectivity; (c) move legality into `vec0` metadata columns, so the filter runs inside the KNN (a schema change and a `--rebuild`); (d) leave it and add an "exhausted" note to the tool's result. Recommended: (a) — one function, no schema change, cost only on short results; it needs the recall eval and a timing check at the cap.
- [ ] [Review][Decision] Orphan vectors are never pruned on the default path — the live index holds 14,472 vectors (26.8%) for cards no longer in `cards`, and they take 43–83 of the 200 KNN slots in every measured query before the JOIN drops them. That makes the starvation above worse. The CLI and the tool both default `prune=False`. `AGENTS.md`'s build command has no `--prune`. The MCP tool has no `prune` parameter, though `initialize_database` tells the agent to pass one (research F6). [`src/search/index_builder.py:253`, `:346-347`; `scripts/build_card_embeddings.py:106-110`; `src/mcp_server/tools/build_search_index.py:58`] Options: (a) always prune (it deletes only rows whose card is gone; the tool already refuses a half-imported database, and the CLI needs the bootstrap patch below first); (b) expose `prune` on the MCP tool and keep it opt-in; (c) prune at the end of `initialize_database`'s reconcile. Recommended: (a) — an orphan is never wanted, and it removes the parameter the agent cannot pass; it is a tool-behaviour change, so the skills and the docstring change with it.
- [ ] [Review][Decision] The index records no model fingerprint — `content_hash` covers the card text only, so a model swap relies on someone remembering `--rebuild`. A swap that keeps 384 dimensions fails nowhere: new query vectors are ranked against old card vectors. [`src/search/index_builder.py:225-244`, `src/search/embedder.py:39-40`] Options: (a) fold `MODEL_NAME` and `EMBEDDING_DIM` into the hashed text, so a swap re-embeds every card on the next build (a dimension change still needs the drop, and the INSERT fails loudly without it); (b) store the fingerprint in a one-row meta table, refuse to build or search on mismatch, and point at `--rebuild`; (c) leave it, as documented. Recommended: (a) — one line, self-healing, and its only cost is one full re-embed, once, when it lands.
- [ ] [Review][Patch] The CLI's `--rebuild` drops the index before loading the model, and the rebuild steps live in two drifted copies — a failed first-run model download leaves no index. The tool resolves the embedder first, and its comment names this exact hazard. Load the embedder before any destructive step, and keep one copy of the sequence in `src/search` [`scripts/build_card_embeddings.py:133-142`, `src/mcp_server/tools/build_search_index.py:83-94`]
- [ ] [Review][Patch] The builder trusts the hash table alone — a card whose hash matches but whose `card_vec` row is missing (an interrupted rebuild between the committed drop and the clear) is classified `skipped` forever. The tool then reports "0 cards embedded, N already current. Semantic search is ready." while search answers `index_unavailable`, and only `rebuild=True` heals it. Treat "hash matches, no stored vector row" as new; `stored_meta` is already loaded [`src/search/index_builder.py:426-432`]
- [ ] [Review][Patch] The CLI's bootstrap check is a copy of `is_database_initialized` without the import-in-progress check — the CLI builds over a half-imported database that the tools treat as not initialized, and with `--prune` it deletes vectors of cards not yet re-imported. Its docstring also names the wrong function (`index_is_populated`). Call `src.search.query.is_database_initialized` [`scripts/build_card_embeddings.py:48-62`, `:124`]
- [ ] [Review][Patch] `colors=[]` means "no colour filter" on the semantic path but "colourless" on `search_cards` (`exact`) — `semantic_search_cards(colors=[], color_mode="exact")` returns cards of every colour, though the module says its colour semantics mirror `search_cards`. Match the relational rule, together with B2's `at_most` `colors=[]` patch [`src/search/query.py:329-330`, `src/data/repositories/card.py:526-529`]
- [ ] [Review][Patch] CLI flags are unvalidated — `--rebuild --limit N` drops the production index and rebuilds N cards; `--batch-size 0` processes nothing and exits 0 (`fetchmany(0)` returns `[]`); a negative `--limit` means "no limit"; `_READ_CARDS_SQL` has no `ORDER BY`, so "the first N" varies between runs [`scripts/build_card_embeddings.py:87-111`, `:133-150`; `src/search/index_builder.py:54-56`, `:326-327`]
- [ ] [Review][Patch] Format is compared case-sensitively on the semantic path — `format="Standard"` builds `$.Standard`, matches nothing, and answers `empty` with no hint; the same raw-key pattern as B2's `card.py:66` patch, so fix every instance together [`src/search/query.py:336-338`, `src/mcp_server/tools/semantic_search.py:186-188`, `src/mcp_server/tools/find_similar.py:358-360`]
- [ ] [Review][Patch] Neither rebuild entry point is tested — `test_rebuild_clears_hashes_and_full_reembeds` types the drop and clear calls by hand, and no test runs CLI `main()` with `--rebuild` or the tool with `rebuild=True`; dropping the clear from either site passes the suite and empties the index while reporting success [`tests/unit/search/test_build_card_embeddings_cli.py`, `tests/integration/mcp_server/test_first_run_data_init.py`]
- [ ] [Review][Patch] "Hash-recorded iff vector written" is untested across a failed build — add an embedder that raises on its second batch, assert that both tables hold the same completed ids, then re-run and assert convergence [`tests/unit/search/test_index_builder.py`, `src/search/index_builder.py:473-484`]
- [ ] [Review][Patch] `exact` and `at_most` are untested on the semantic path — `test_color_mode_all_requires_every_flag` covers `all` and `any` only; swapping or weakening the two other branches passes the suite [`tests/unit/search/test_query.py:229`, `src/search/query.py:139-142`]
- [ ] [Review][Patch] Two `_coerce_json_list` copies disagree — the builder's copy returns `None` for JSON `null` and would crash `" ".join` / `set()`; the `query.py` copy maps it to `[]`. No row holds `null` today. Keep one null-safe helper [`src/search/index_builder.py:353-368`, `src/search/query.py:99-114`]
- [ ] [Review][Patch] `_resolve_db_path` returns any unrecognised URL verbatim as a file path (another driver prefix, a `?query` suffix), though its docstring says it can never diverge from the async engine; raise instead [`src/search/connection.py:46-49`]
- [ ] [Review][Patch] `ConnectionFactory` claims "WAL is always on" but only logs the `journal_mode` result; warn when it is not `wal`, or soften the docstring [`src/search/connection.py:57-58`, `:139-151`]
- [ ] [Review][Patch] `logger.info(stats.summary())` formats eagerly, against the lazy `%`-args rule [`src/search/index_builder.py:349`]
- [ ] [Review][Patch] `BuildStatistics` times the build with `time.time()`; use `time.perf_counter()` [`src/search/index_builder.py:97`, `:105`]
- [ ] [Review][Patch] Stale size and printing comments — "38k hashes" against "~60k cards", and the `query.py` module and `hybrid_search` docstrings say many printings share near-identical vectors, while the database holds one printing per oracle (so the de-dup guards only reprint-bearing data) [`src/search/index_builder.py:310`, `src/search/embedder.py:169`, `src/search/query.py:13-15`]
- [ ] [Review][Patch] `ConnectionFactory()` and the parent `mkdir` run outside the CLI's `try`, so a permission error escapes as a raw traceback instead of the logged exit-1 path [`scripts/build_card_embeddings.py:115-116`]

**Rejected**

- `false` — every printing's identical text is embedded separately: `cards.db` holds one printing per `oracle_id` (39,503 of each).
- `false` — `hybrid_search` accepts `limit <= 0`, `over_fetch_k` out of range, or bad colour letters: both tools reject `limit` outside 1..50 and colours outside W/U/B/R/G, and both use the default k=200.
- `false` — `limit=0` returns one hit: unreachable through the tools (above).
- `false` — `over_fetch_k` above sqlite-vec's 4096 ceiling: no caller passes anything but 200.
- `false` — NaN or infinite mana bounds escape `math.floor`/`math.ceil`: `mana_bounds_error` rejects non-finite values in all three search tools.
- `false` — a format with odd characters raises a malformed-JSON-path error: probed; only `'$.'` errors, and the tools blank-normalise an empty format (the real defect is the case patch above).
- `false` — a whitespace-only query is embedded: the tool rejects a blank query, and composed card text always carries the name.
- `false` — a vector with no hash hits a `vec0` primary-key conflict: no code path clears the hashes without first dropping `card_vec`.
- `false` — `--prune` misses vectors that have no hash: that state is unreachable (above); the live orphans all have hashes and are pruned by `--prune`.
- `false` — the `assert`s in `Embedder.encode` / `encode_batch` vanish under `-O`: they guard a count fastembed never produces.
- `not a defect` — the extra focus lives at the tool layer and the content carries no tests (intent-alignment): descriptive; the tool call sites were read and are recorded under What holds.

### 2026-11-08 — B12 Companion backend: images, socket, safety

**Code review complete.** 0 `decision-needed`, 11 `patch`, 0 `defer`, 13 rejected.

- **Group:** B12. **Reviewed revision:** `ee0263d652a46f021515860bbc2a19e3dac60eed` (no change to the six files up to `4b9c5d0`).
- **Files (2,677 lines):** `src/companion/app/images.py`, `errors.py`, `ws.py`, `body_cap.py`, `security.py`, `singleton.py`.
- **Mode:** no-code, thorough; lenses blind-hunter, edge-case-hunter, verification-gap, intent-alignment (none failed). Triage: leave as action items.
- **Evidence gathered read-only from `cards.db`** (stdlib `sqlite3` in `mode=ro`; nothing written):
  - 3,437 cards carry `card_faces`. One has per-face `image_uris` on some faces only: the `Clue // Clue` token (`7493d2a6-…`), faces `[True, False]`, which resolves correctly (face 1 answers 404). No row has the `[False, True]` shape that would shift the face index.
  - No stored image URL has an explicit or malformed port, so the port patch below guards data, not a live failure.
  - Starlette 0.48.0's `ServerErrorMiddleware` catches `Exception` (so `ClientDisconnect`), tries a 500 and re-raises; CI runs `mypy src/` on Linux plus `--platform win32` (`ci.yml:75`).
- **Overlap with the architecture report:** research F5 (the image route holds a session through the pacer wait) is B11's route and dependency, not these files, and is not repeated here. AD-11's unbounded disk cache is accepted and not raised.
- **What holds:**
  - **Image bounds:** 16 MB body ceiling checked on the declared length and while streaming, a 20 s whole-exchange deadline, `follow_redirects=False`, an `https` host allow-list parsed with `urlsplit` (never a substring test), `Semaphore(4)` plus 0.1 s spacing under one FIFO lock, both released on cancellation through `async with`. The negative cache is capped at 2,048 entries, pruned on every insert, on a monotonic clock. Cache writes are temp + `os.replace` with a lost-race path on Windows.
  - **`singleton.py`:** the `sys.platform` branch lets mypy narrow each half. Windows unlocks before close, `release_instance_lock` never raises, and the lock file is left in place on purpose.
  - **Logging:** every log call in the six files uses lazy `%`-style args. The `f"…"` strings are exception messages only. Attacker-controlled `Host` and `Origin` are truncated at 100 characters.
  - **Security:** exact `Host` match on `http` and `websocket` scopes, `Origin` checked on the upgrade, constant-time byte compare of the bearer token, no token value logged (AD-5). The body cap counts bytes, so a lying `Content-Length` cannot get through.
  - **Layering:** the six files import FastAPI and Starlette, `src.companion` and only `src.data.schemas.card` from the data layer. They make no DB write (AD-2), and `build_app()`-time code has no side effects (AD-10).

- [ ] [Review][Patch] `is_fetchable` reads `parts.port` outside its `try` — `SplitResult.port` raises `ValueError` for `https://cards.scryfall.io:99999/x` or `:abc`. The error escapes `fetch_image` as `500 internal_error`, not `502 image_fetch_failed`, and is never negative-cached, against the docstring's "False … including an unparseable one". Move the read inside the `try` and add both URLs to the refusal list in `TestUrlAllowList` [`src/companion/app/images.py:184`, `tests/unit/companion/test_images.py:200-216`]
- [ ] [Review][Patch] A chunked request body is never tested through the body cap — every body-cap test declares a `Content-Length`, so dropping the `transfer-encoding` branch of `_announces_a_body` passes the suite and lets a chunked body of any size reach FastAPI unbounded. Add an ASGI-level test beside `test_a_lying_content_length_does_not_get_through`: a `transfer-encoding: chunked` scope with no `content-length`, over `_MAX_ENVELOPE_BYTES` across `more_body` chunks, answers `413 payload_too_large` without calling the inner app; pair it with an under-cap chunked body that arrives intact [`src/companion/app/body_cap.py:112-128`, `:141`; `tests/unit/companion/test_routes_agent_events.py:460-540`]
- [ ] [Review][Patch] The 16 MB ceiling counts decoded bytes after the fact — httpx sends `Accept-Encoding: gzip, deflate` by default and `aiter_bytes()` yields decompressed chunks, so one compressed chunk from an allow-listed host can expand far past `_MAX_IMAGE_BYTES` before the running-total check runs. The declared `Content-Length` counts encoded bytes. Ask for `Accept-Encoding: identity` on the image client (images gain nothing from compression), or bound the raw stream [`src/companion/app/images.py:189-212`, `:897-911`]
- [ ] [Review][Patch] `_read_cached` reads the whole file before the ceiling check — an oversized or planted entry under the cache root is buffered in full on every request before it is rejected; check `stat().st_size` (empty and over-ceiling) before `read_bytes()` [`src/companion/app/images.py:376-389`]
- [ ] [Review][Patch] Cache-path containment rests on a type the signatures drop — the `DiskCache` docstring says `path_for` is safe because `size` is the closed `ImageSize` `Literal`, but `_cache_path`, `_read_cached`, `DiskCache.path_for` / `read` / `write` and the `NegativeCache` methods take `size: str`, so a future unvalidated caller type-checks; type `size` as `ImageSize` [`src/companion/app/images.py:335`, `:358`, `:495-546`, `:706-752`]
- [ ] [Review][Patch] Displaced siblings are unlinked before `os.replace` — a replace that fails for a reason other than the Windows race re-raises after deleting the only servable copy under the other extension; unlink them after a successful replace instead, which prevents the shadowing just as well [`src/companion/app/images.py:434-444`]
- [ ] [Review][Patch] `validation_error_handler` logs `exc.errors()` with each error's raw `input` — up to `_MAX_ENVELOPE_BYTES` of caller-chosen text at WARNING, where `Host` and `Origin` are capped at 100 characters and `ws.py` refuses to log the active-deck value; log `loc` and `type` only [`src/companion/app/errors.py:297-299`]
- [ ] [Review][Patch] `ClientDisconnect` is re-raised into `ServerErrorMiddleware` — Starlette 0.48 catches it there, tries a 500 into the dead stream and re-raises, so uvicorn logs an ERROR traceback; the class docstring promises "no false-alarm `ERROR` record or a response into a dead stream". Return instead of raising, and update the test that expects the raise [`src/companion/app/errors.py:487-489`, `:525-530`; `tests/unit/companion/test_errors.py:591-602`]
- [ ] [Review][Patch] The 1011 docstrings overstate it — `_INTERNAL_ERROR` says 1011 is "distinguishable from `_POLICY_VIOLATION` on the wire", but a close before `accept()` is rendered by uvicorn as HTTP 403 whatever the code, so only the post-accept 1011 is distinguishable; `_close_quietly` says it is "used for every pre-accept close" while it also serves post-accept closes and `broadcast` [`src/companion/app/ws.py:138-150`, `:305`]
- [ ] [Review][Patch] The singleton comment names `mypy src/ --platform linux` as the second mandatory pass, while `AGENTS.md` and CI (`ci.yml:75`) run `--platform win32`; say "the other platform's pass" [`src/companion/app/singleton.py:56-59`]
- [ ] [Review][Patch] `body_cap.py`'s module docstring says "Inside the routers"; the middleware runs outside them, before routing, which is the point of its own "Why it cannot be a dependency" paragraph [`src/companion/app/body_cap.py:48`]

**Rejected**

- `false` — a lowercase `allow` header yields two `Allow` headers on a 405 (two lenses): Starlette emits `Allow`, and nothing in the app raises a 405 with its own headers.
- `false` — `require_agent_token` logs "invalid" when no token was minted: under uvicorn the lifespan mints the token before any request is served.
- `false` — `Pacer(limit=0)` blocks forever: only the lifespan builds it, with the defaults.
- `false` — `NegativeCache(base<=0)` never backs off: lifespan defaults only, and the constructor already guards the mis-injection cases that matter.
- `false` — removing the auto-validation components leaves a dangling `$ref`: the committed `openapi.json` mentions `ValidationError` 0 times, and the `gen:types` drift check would catch one.
- `false` — AD-15 is cited for the wrong decision (intent-alignment): AD-15's operational envelope covers the crash and the stale discovery file the code cites it for.
- `low` — mixed per-face `image_uris` can shift the face index: the only mixed row (`Clue // Clue`) resolves correctly and the shifting shape has 0 rows; the fix changes the face contract the UI mirrors.
- `low` — two concurrent failures of one key escalate the backoff twice: rarely visible, and the fix needs in-flight coalescing.
- `low` — `supported_methods` is correct only while every mount is at `/`: documented in its own warning, true today, and the guard is new code.
- `low` — `release_instance_lock` takes a bare `int`, so a second call can close a reused descriptor: one caller, in one `finally`; a handle type adds surface.
- `low` — `Pacer.available_permits` reads `Semaphore._value`: a test-only seam; a hand-kept counter adds code.
- `maybe-false` — the `Host` refusal's `websocket.close` can raise when the peer is already gone: if true, only an error log for a refused request; a uvicorn test that drops the TCP connection before the 403 would settle it.
- `not a defect` — the diff carries module source only, without callers, tests or gates (intent-alignment): descriptive; the callers and tests were read during triage, and the image route's composition is B11's.

### 2026-11-08 — F2 UI state, part 2

**Code review complete.** 1 `decision-needed`, 10 `patch`, 0 `defer`, 20 rejected.

- **Group:** F2. **Reviewed revision:** `ee0263d652a46f021515860bbc2a19e3dac60eed` (no change under `ui/src/state/` up to `6111ea9`).
- **Files (1,434 lines), the F1/F2 split:** `ui/src/state/agentView.ts` (434), `deck.ts` (675), `cards.ts` (325). The colocated suites (`agentView.test.ts`, `deck.test.ts`, `cards.test.ts`) and `App.test.tsx` were read as evidence, not reviewed; T1 covers them.
- **F1 is left with the rest, 3,988 lines — over the ~3,000 guideline:** `ui/src/api/client.ts`, `schema.ts` (1,011) plus `ui/src/state/connection.ts`, `deckGroups.ts`, `faces.ts`, `formatCheck.ts`, `formatCheck.fixtures.ts`, `identity.ts`, `inspection.ts`, `panel.ts`, `poller.ts`, `socket.ts`, `systemState.ts` (2,977). The table's ~2,700 for F2 overcounted the three named files. Split F1 in two when it runs, or accept the size warning.
- **Mode:** no-code, thorough; lenses blind-hunter, edge-case-hunter, verification-gap, intent-alignment (none failed). Triage: leave as action items.
- **Overlap with the architecture report:** the re-render patch is research F8 (`seedDeckCards`), recorded here with the state-level detail. Research §10's "App owns a `hydrateCard` sweep" comment is not in these three files. Merge in step 4.
- **What holds:**
  - **`HISTORY_CAP`:** 20 entries, newest first by `ts`. An unparseable `ts` falls back to arrival position, a push older than all twenty stays shown and retained but out of the list (pinned at `agentView.test.ts:1040-1051`), and same-reference re-opens return the array itself. Push ids are `uuid4` per push (`src/companion/client.py:452`, `src/mcp_server/tools/companion.py:354`, `:440`, `:593`), so the same-id replace arm never fires in production.
  - **Revisit:** a history revisit leaves `retained` alone, and the history popover is reachable only with the view closed (`AgentViewsNav.tsx:62-66`). The defects are in the unread bookkeeping (the patch below).
  - **Derived state:** `boards` is derived once at write time; `Surface` passes the same references; there is one writer per store; the card cache dedupes in flight with an attempt bound; and seeding issues zero requests. `useDeckCardQuantity` re-sums `detail.cards` per tile, but only `GroupsView` uses it (rejected below).
  - **Boot:** generation guards on every await; an `updating` clear on every exit; refetch supersession with abort; the CAP-2 and CAP-3 flags all go through `restartBoot`.

- [ ] [Review][Decision] Edge-only deck recovery leaves two transient-refusal paths with no later edge — (1) a `deck_changed` refetch that answers `database_unavailable` (or `unreachable`, a malformed row) is dropped and `updating` clears, so the agent's edit never reaches the glass and nothing retries: the deck stays stale with no marker until another frame or a reconnect [`ui/src/state/deck.ts:317-321`]; (2) after the CAP-3 probe's healthy answer re-drives the boot, a second transient refusal finds `probeSpent` true and the poll stopped healthy, so "Card database is updating." stays until a reload or a frame [`deck.ts:620-626`]. Both follow from AD-12's "no timer"; the 2026-09-06 review (#3) recommended bounded backoff and CAP-3 chose one probe. Options: (a) route the refetch's transient refusal through the same one-probe path (the poll's healthy answer re-drives), and re-arm the probe once per re-drive rather than once per episode, keeping a hard cap; (b) a bounded backoff retry for transient deck refusals (a timer, reversing AD-12's edge-only rule); (c) leave both as the accepted bound and say so in the module docstring. Recommended: (a) — no timer, and it reuses the CAP-3 machinery; (b) changes an architecture decision.
- [ ] [Review][Patch] Inherited object keys read as card entries — the cache is a plain object indexed with `cards[cardId]`. An agent push can carry any string as a card id (AD-7, `contracts.py:490`), so `"constructor"` or `"toString"` makes `useCardEntry` return `Object.prototype.constructor`. `CardDetail`'s `contentOf` then calls `fromSummary(undefined)` → `summary.name` TypeError, and with no error boundary in `ui/src` that blanks the app. Reasoned, not run. Read through `Object.hasOwn` (the module already does this for reasons), or use a null-prototype map; add a test with a `"constructor"` id [`ui/src/state/cards.ts:251`, `:291`, `:316`, `:325`]
- [ ] [Review][Patch] History revisits are treated as the latest view in the unread bookkeeping. With the view closed and `unread.swaps` set by a displacement, reopening an older swaps entry from the history popover deletes the dot, though the retained (newest) swaps view was never seen. If a push of another kind displaces an open revisit, the revisited kind is marked unread although its retained view was not the one displaced. Clear `unread[kind]` and mark `displaced` only when the content involved is `retained[kind]`, and add both cases to `agentView.test.ts` [`ui/src/state/agentView.ts:213-226`]
- [ ] [Review][Patch] The CAP-3 probe re-arm on a `'none'` settle is untested. Dropping `|| state.status === 'none'` passes every probe test (`App.test.tsx:1496-1771`), because none settles `'none'` between two refusals in one healthy episode. Add the refusal → `'none'` → refusal case beside `:1687` [`ui/src/state/deck.ts:613`]
- [ ] [Review][Patch] The four `*ViewOf` builders are near-copies that differ only in the fallback label ("`suggestionsViewOf`'s defence applies verbatim"), and only `suggestions` has a named title export. A guard change needs four edits, the AGENTS.md repeated-pattern pitfall. Use one generic builder keyed on `AGENT_VIEW_LABELS[kind]` [`ui/src/state/agentView.ts:269-340`, `:46`]
- [ ] [Review][Patch] `seedDeckCards` writes a new `{status: 'hydrated', card}` object for every row and a new map even when nothing changed, so every `useCardEntry` subscriber re-renders on each seed (twice per cold open, once per refetch; research F8). Keep an existing entry whose card is unchanged, and return `state` when no entry changed [`ui/src/state/cards.ts:194-208`]
- [ ] [Review][Patch] `driveDeckChanged` supersedes a boot in flight. While `'booting'`, or during an unsettled re-drive, each `deck_changed` frame calls `restartBoot`, discarding the in-flight sequence, though CAP-2 and CAP-3 both defer through `redriveOnSettle` so that the in-flight response paints. Defer the same way while `!boot.settled()` [`ui/src/state/deck.ts:512-517`]
- [ ] [Review][Patch] The `reopenPush` docstring says "The entry IS the retained reference", which holds only for the newest entry of each kind, while the `revisit` branch exists for every other one [`ui/src/state/agentView.ts:251-254`]
- [ ] [Review][Patch] The `DeckBoot` docstring says "What one settled boot decided", but the interface is the boot's control handle [`ui/src/state/deck.ts:165`]
- [ ] [Review][Patch] `MAX_ATTEMPTS_PER_CARD` and the `attempts` map say "ever, for the life of the tab", but `resetCardAttempts` restores the budget on every reconnect, so 3 × 99 is per connection [`ui/src/state/cards.ts:24`, `:30`, `:118`]
- [ ] [Review][Patch] `AgentViewContentBase.count`'s `null` arm ("a view that counts nothing") is never produced, because all four builders set `items.length`; narrow it to `number` (`AgentView`'s own `number | null` prop can stay) [`ui/src/state/agentView.ts:61-62`]

**Rejected**

- `false` — id-less or non-string-`ts` pushes collapse history or reach the pill time (two lenses, three findings): `_EventEnvelope` requires a non-blank `id` and an `AwareDatetime` `ts` (`contracts.py:961-964`), every push mints `uuid4()` and `now(UTC)`, and the SPA is served by the same backend.
- `false` — a same-id re-push with a new `ts` keeps a stale position, or overwrites `retained` with an older envelope (two lenses): ids are `uuid4` per push and there is no re-push path.
- `false` — a pill reopening a retained view evicted from history evicts a real push: a valid `ts` older than all twenty ranks last and the cap drops it; only a null `ts` front-inserts, which is unreachable (above).
- `false` — `pollPanel` starting from `INITIAL_SYSTEM_STATE.panel` mis-charges the probe: the initial value is the non-retrying one, so the only mismatch charges a probe whose `restartPollIfStopped` is a no-op, and the next non-healthy poll write resets `probeSpent`.
- `false` — the refetch-settle counter is bumped after `onUpdate` started a new boot: `redriveOnSettle` is set only while the boot is unsettled, and a refetch runs only when it is settled.
- `false` — a throwing `onUpdate` is misread as a malformed row, in the boot and the refetch (two findings): the deck store has only React subscribers (no `useDeckStore.subscribe` in `ui/src`), and `restartBoot` and the probe do not throw.
- `false` — a non-number `quantity`, or a seeded `card` missing `id`/`name`: the rows are Pydantic `DeckCardSummary`/`Card`, from the same-origin backend.
- `low` — `retained` is latest by arrival while history is ordered by `ts`: it needs out-of-order arrival from two MCP processes, and the fix ranks `retained` by `ts`, which is new logic.
- `low` — the boot's two reads carry no `AbortSignal`: one superseded request per restart, restarts are rare, and the fix threads a controller through both readers.
- `low` — `useDeckCardQuantity` rescans the deck for every tile on every store write: only `GroupsView` uses it (at most 60 tiles), the scan takes microseconds, and the fix adds a quantity map to `DeckBoards`.
- `low` — a cold-open transient refusal that lands before the poll's first answer restarts the in-flight first poll: it costs one wasted `/api/decks`, the deck read usually lands second, and the fix adds a flag.
- `low` — `resetCardAttempts` re-arms the empty-id refusal: `hydrateCard('')` refuses again with no request, and a separate marker adds state.
- `not a defect` — the tests are not in the diff (blind-hunter), and the test and cross-module surfaces lie outside it (intent-alignment): the colocated suites exist, the verification-gap lens read them, and T1 reviews them.
- `not a defect` — the F2 file list is smaller than the table's ~2,700 (intent-alignment): recorded above as the F1/F2 split note.

## Summary

<!-- Written in step 4. -->
