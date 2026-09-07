---
title: 'Clone deck tool'
type: 'feature'
created: '2026-09-07'
status: 'done'
baseline_revision: '598b2fcb4fd89ca27cf1afb7c99ba2c7c618d5e7'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** Agents cannot preserve a deck before experimenting without re-importing it (quick-wins CAP-3).

**Approach:** Expose `clone_deck(deck_id, name=None)` as a stateless MCP tool that creates an independent deck and all its card rows in one transaction, returning the existing `DeckResult` shape.

## Boundaries & Constraints

**Always:** Preserve format, strategy, tags, colour identity and every card's id, quantity, board and commander flag. Generate a new deck id and fresh timestamps; leave source metadata, timestamps and rows untouched. Default name is exactly `<source name> (copy)`; explicit names follow existing nonblank/100-character validation. Generated names retain the exact suffix even when exceeding that explicit-input bound. Emit `deck_changed` once for the new id on success after session exit. Roll back any precommit database failure; a read failure after commit still returns the committed snapshot and emits success. Return Pydantic schemas; use paired list properties for JSON fields. Update shipped documentation and regenerate plugin. Tests exercise actual MCP calls and persisted state.

**Never:** Compose committing repository writers for the copy; change merge behaviour; change source cards; add format/legality validation; introduce database migrations, companion writes, UI changes, viewer changes, or other quick-wins capabilities.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Full copy | Source with mainboard, sideboard, commanders and metadata | `ok`, faithful independent clone, exact default name | No error expected |
| Named copy | Explicit valid name | `ok`, requested name | No error expected |
| Empty source | No card rows, optional metadata empty | `ok`, empty clone | No error expected |
| Long default | Source name of 100 characters | `ok`, exact source plus suffix | No truncation |
| Invalid name | Blank or over 100 characters explicitly supplied | `invalid`, no write or notification | Existing validation vocabulary |
| Missing source | Unknown deck id | `not_found`, no write or notification | Graceful result |
| No DB | Uninitialized database | `database_not_initialized` | No notification |
| Mid-copy failure | Database error after staged deck/cards, before commit | `error`, no partial clone; source unchanged | Rollback and lazy-argument logging |
| Postcommit read failure | Clone committed, refresh fails | `ok`, complete snapshot and one notification | Log warning; no retry invitation |

</intent-contract>

## Code Map

- `src/data/repositories/deck.py`: `get_deck_with_cards` supplies eager-loaded schemas; implement beside `merge_decks`, whose per-card commits cannot provide atomicity. `_reload_committed` and `_reload_after_commit` distinguish failed writes from failed reporting. Models generate fresh UUID/timestamps; `DeckCard.model_copy` can rebind schema rows to the clone for a complete snapshot.
- `src/data/models/deck.py`, `src/data/models/deck_card.py`: `tags_list`, `color_identity_list`, composite association key and commander field. No model changes needed.
- `src/mcp_server/tools/deck_management.py`: `DeckResult`, `DeckDetail.from_deck`, existing validation constants and create helper error vocabulary.
- `src/mcp_server/server.py`: `create_deck` wrapper emits returned deck id after session exit; actual LLM-facing `compare_deck_power` description currently recommends export/create/import.
- `tests/integration/test_mcp_tools.py`: in-process client and `ROUND_TRIPPED` registry guard. `tests/integration/test_build_plugin.py` pins registered names.
- `tests/integration/mcp_server/test_deck_changed_wiring.py`: notifier fixture and real client cover emit-once, silent failures and postcommit fault injection.
- `tests/unit/companion/test_import_boundary.py`: add repository method to `_REPO_WRITE_METHODS` for existing architectural guard.
- `.claude/skills/`: five shipped skills; inspect each and document clone where workflow applies. `README.md`, `docs/architecture.md`, `docs/plugin-structure.md`, `CHANGELOG.md` enumerate capabilities; `scripts/build_plugin.py` generates mirror.

## Tasks & Acceptance

**Execution:**
- `src/data/repositories/deck.py` -- add atomic clone method with complete snapshot and commit/rollback/readback discipline.
- `src/mcp_server/tools/deck_management.py`, `src/mcp_server/server.py` -- implement and register clone tool, validate explicit name, project complete result, notify new id; update comparison guidance wherever exposed.
- `tests/integration/test_mcp_tools.py`, `tests/integration/mcp_server/test_deck_changed_wiring.py` -- cover matrix through real MCP entry points, inject failures into actual persistence, reload source and clone independently, and check subsequent clone edits do not change source.
- `tests/integration/test_build_plugin.py`, `tests/unit/companion/test_import_boundary.py` -- extend name sets for new tool and writer.
- `.claude/skills/`, `README.md`, `docs/architecture.md`, `docs/plugin-structure.md`, `CHANGELOG.md` -- update applicable catalogs and before/after guidance; regenerate `plugin/`.

**Acceptance Criteria:**
- Given a populated source, when MCP clones it, then reloading both decks proves equal card rows and preserved metadata, distinct id and creation timestamp, and an untouched source; editing the clone leaves the source unchanged.
- Given a database failure during copying, when MCP returns, then no partial deck or rows remain and no change event fires.
- Given a committed clone whose refresh fails, when MCP returns, then it reports the full successful clone and emits exactly once for the clone id.
- Given a built server, when the client lists tools, then clone is registered and comparison guidance recommends it; generated plugin exposes the same tool.

## Spec Change Log

## Review Triage Log

### 2026-09-07 — Review pass
- verdicts: 15 findings — high 0, medium 5, low 1, false 9, maybe-false 0
- findings:
  - `[medium]` `[patch]` Multi-SELECT source loading can mix revisions during a concurrent edit — replaced clone's source load with one joined eager SELECT; a real MCP regression commits an independent writer after the SELECT starts and verifies a consistent old snapshot. Global transaction behavior stays unchanged.
  - `[false]` `[reject]` Discarding the refresh result makes refresh redundant — `_reload_after_commit` also synchronizes the ORM identity map for repository session reuse; retaining the complete response snapshot preserves the established postcommit convention.
  - `[false]` `[reject]` Editing the clone in skill guidance contradicts editing the original in comparison guidance — these describe two valid choices of which deck to experiment on, both retaining the other id for comparison; neither alters tool behavior or silently selects an edit target.
  - `[false]` `[reject]` Invalid-name cases with a missing source cannot catch ignored validation — each requires `invalid`; ignoring validation returns `not_found` and fails the existing assertion. No-write and silent-notifier assertions supplement that status proof.
  - `[medium]` `[patch]` One distinct card cannot catch loss of later cards on a board — populated round trip now includes Thunderbolt plus Lightning Bolt, mixed commander flags and both boards, and compares complete returned/persisted rows.
  - `[medium]` `[patch]` Postcommit fallback coverage checked only counts — test now compares complete returned and freshly loaded clone plus source metadata and every row, including strategy, tags, identity, quantities and commander flags.
  - `[low]` `[reject]` Independence test could also exercise metadata edits and clone deletion — separate deck ids and copied rows are established, and a persisted quantity edit proves isolation; adding unrelated existing mutation/cascade paths adds test complexity for negligible additional everyday risk.
  - `[medium]` `[patch]` Readiness-probe database errors escaped the result boundary — moved the probe into clone's existing DatabaseError handler and added a real MCP structured-error/silent-notifier test.
  - `[medium]` `[patch]` Fresh `updated_at` lacked regression coverage — pin both source timestamps to aware UTC in 2000 and assert both clone timestamps are newer, with complete persisted equality.
  - `[false]` `[reject]` Diff alone does not prove next-story selection or final delivery — the parent read story 1's `done` status before selecting story 2; `in-review` was the required intermediate state when the review diff was generated. Final status is recorded at completion.
  - `[false]` `[reject]` Comparison guidance changed server.py rather than the named helper file — only the registered server docstring contains the obsolete guidance and reaches MCP callers; the list_tools test observes that actual public surface.
  - `[false]` `[reject]` Other skills and OpenAPI/types were not edited — all five skills were inspected; only magic-deckbuilding catalogs this write workflow. The other skills remain accurate. No companion route/model changed, so its generated API artifacts have no changed source.
  - `[false]` `[reject]` No actual before/after power-comparison run — CAP-3 adds a copy and directs the existing comparison tool toward it; clone results/persistence and advertised guidance are exercised, while existing comparison behavior remains covered by its unchanged suite.
  - `[false]` `[reject]` Notifier tests do not observe browser rendering — this story adds a persisted-write notification through the established shared notifier; browser delivery/rendering is unchanged and covered by existing companion integration tests.
  - `[false]` `[reject]` Long generated names and postcommit fallback refine the original intent — exact default suffix follows CAP-3; snapshot fallback follows the current repository's established committed-write semantics. Neither conflicts with the requested behavior.

## Design Notes

The current repository is newer than story 1's original code map: postcommit reporting failures must not be confused with failed writes. Clone snapshots include rows and counts so no unprotected helper reload is needed. Copy identity as metadata, rather than recomputing or changing the source.

## Verification

**Commands:**
- `uv run ruff check .`, `uv run ruff format --check .` -- clean.
- `uv run mypy src/`, `uv run mypy src/ --platform win32` -- clean.
- `uv run pytest` -- all applicable tests pass, including real MCP clone and fault-injection tests.
- `uv run python -m scripts.build_plugin` -- generated artifacts committed; repeat produces no drift.

## Auto Run Result

Status: done

**Summary:** Added `clone_deck(deck_id, name=None)`. A single joined read captures a consistent source snapshot; one write transaction creates the independent deck and all associations. Format, strategy, tags, colour identity, quantities, boards and commander flags are preserved. The clone gets fresh ids/timestamps and defaults to the exact source name plus ` (copy)`. Explicit names are validated. The source is untouched, precommit failures roll back, and postcommit read failures return the complete successful snapshot. Successful writes notify the companion once with the new id.

**Files changed:**
- `src/data/repositories/deck.py` — atomic clone and consistent source snapshot.
- `src/mcp_server/tools/deck_management.py` — clone validation, readiness/error handling and result projection.
- `src/mcp_server/server.py` — registered tool, new-id notification and comparison guidance.
- `tests/integration/test_mcp_tools.py` — complete copy, independent edit, fresh timestamps and caller-visible guidance.
- `tests/integration/mcp_server/test_deck_changed_wiring.py` — names, empty decks, silent failures, rollback, complete postcommit fallback and concurrent-source regression.
- `tests/integration/test_build_plugin.py`, `tests/unit/companion/test_import_boundary.py` — registered-tool and repository-writer pins.
- `.claude/skills/magic-deckbuilding/SKILL.md` — clone catalog, parameters, results and usage guidance; other four shipped skills inspected and still accurate.
- `README.md`, `docs/architecture.md`, `docs/plugin-structure.md`, `CHANGELOG.md` — capability catalogs and cloning workflow.
- `plugin/server/src/data/repositories/deck.py`, `plugin/server/src/mcp_server/server.py`, `plugin/server/src/mcp_server/tools/deck_management.py`, `plugin/server/README.md`, `plugin/skills/magic-deckbuilding/SKILL.md` — regenerated mirrors.
- This story file — plan, triage and result.

**Review:** Four independent layers; 15 observations triaged individually above. Five medium patches applied (snapshot consistency, multiple-card coverage, complete fallback coverage, readiness error boundary, timestamp coverage); zero deferred; ten rejected with their specific reasons in the triage log. No intent gap or specification repair loop.

**Follow-up review recommendation:** false. Although five medium entries were patched, their concrete risks now have passing regression coverage; no specific unverified risk remains to justify another automatic pass.

**Verification:**
- `uv run ruff check .` — clean.
- `uv run ruff format --check .` — 334 files already formatted.
- `uv run mypy src/` and `uv run mypy src/ --platform win32` — both clean, 94 source files.
- Final `uv run pytest --junitxml=...` — 3307 passed, 1 skipped, 283.29 seconds; recorded in the system temporary directory as `clone-final-20260907.log` and `.xml`.
- Matrix audit: the round-trip test covers populated copies and independence; both `test_clone_empty_and_long_default` parameters cover named/default/empty/long defaults; all three invalid/missing parameters passed; uninitialized silence passed; both atomic-outcome parameters cover rollback and postcommit fallback. Additional readiness-error and concurrent-source tests passed. No matrix case was skipped.
- Plugin regenerated after final formatting; committed source/mirror consistency tests passed. `git diff --check` clean.

**Residual risks:** No known unresolved clone defect. Generated default names can exceed the explicit-name 100-character cap by design to preserve the exact suffix. This run commits locally and does not push, per build-auto finalization.
