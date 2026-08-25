---
title: 'Tier lists — tool and view'
type: 'feature'
created: '2026-08-21'
status: 'done'
baseline_revision: '77f2f0f1195f3a646f40b7933b702a1f6d988b4d'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: [oversized]
deferred:
  - 'Empty-push copy grammar (the c6-6 ledger item, now with THREE data points): the shared template renders "The agent sent an empty suggestions." (c6-6), "…an empty swaps." (16.1) and "…an empty tier_list." (16.2) — the third is the first with a raw underscore on the glass. Recommendation: amend EXPERIENCE.md''s Voice-and-Tone cell to take a display noun, then substitute lowercased AGENT_VIEW_LABELS[kind] ("tier list") in emptyPushLine; the template is artefact-gated byte-for-byte, so the artefact moves first.'
---

<intent-contract>

## Intent

**Problem:** The agent cannot push tier lists to the companion Glass: the `tier_list` wire contract exists end-to-end, but no MCP tool mints a `TierListEvent`, and the SPA's dispatch switch silently drops `tier_list` frames. Meanwhile `companion.py` carries two structurally identical push trios; a third verbatim clone was explicitly deferred out of 16.1 as a 16.2-planning decision.

**Approach:** Consolidate the push-tool internals first (shared push executor + noun-parameterized failure-message builder, keeping the three field-identical result classes and distinct wire-visible docstrings), then add `companion_show_tier_list(payload)` on the shared path and a `TierListView` container rendering tier rows per the Voltglass tier-row spec, wired through the existing socket dispatch, agent-view store, and App render switch. No contract change; no backend route change.

## Boundaries & Constraints

**Always:**
- Tool is `async def`, never raises, posts a self-built `TierListEvent` through the existing leaf client (`push_event`), and returns exactly one of `displayed | app_not_running | no_clients_connected | payload_rejected | backend_error` plus client count; compact result (<400 chars), no payload echo. `items_pushed` counts **tiers** (`len(payload.items)`), never cards — docstring says so, and a test pins it (the swaps "pairs, not cards" precedent).
- Consolidation must leave suggestions/swaps result wording **byte-identical** — every existing push-tool test stays green untouched. Result classes stay three distinct field-identical models (docstrings are wire-visible); the tool must NOT inject a default title (`DEFAULT_TITLE_BY_KIND` gives the reader "Tier list").
- Registered docstring states: Scryfall printing UUIDs (a name will not render), every cap in plain numbers (≤12 tiers, ≤60 card ids/tier, name ≤40 non-blank, note ≤200, title ≤80), letter enum closed at S/A/B/C/D with `name` carrying the MTG meaning, repeated letters legal, empty `items` legitimate, "send here **and** give your normal answer", app-must-be-running.
- View: letter colors ramp `--accent-bright`(S) `--accent`(A) `--text-primary`(B) `--text-secondary`(C) `--text-tertiary`(D); the letter is always accompanied by its name in micro `--text-tertiary` (color never sole carrier of rank); tiers render in payload order; **empty tiers are skipped, not rendered as shells**; one malformed item degrades that tier only; thumbnails use `alt=""`; every value from the token scale except `132px`/`44px`/weight `500`, which ship as literals with inline DESIGN.md:331-338 citations (px-citation guard).
- Store `count` = `items.length` (payload tiers, raw — matches both prior kinds); the view's empty-tier skipping is render-only. Hydration effect keyed on `items`; standard inspection contract on every thumbnail.
- After UI changes: rebuild SPA into `src/companion/app/static/` AND rerun `scripts.build_plugin`; commit both mirrors (README also mirrors into `plugin/server/`).

**Block If:** the change appears to require editing `src/companion/contracts.py`, `src/companion/client.py`, or any backend route (red flag against the epic's "no contract change" premise); or consolidation cannot keep an existing suggestions/swaps test green without rewording a pinned message; or the CONTAINERS/tokens guards cannot pass without weakening a pin other than those listed in Tasks.

**Never:** no generic `companion_display`; no per-session server state; no card-ID validation at ingest or in the tool; no new design primitive or token (pin stays 70); no `--accent-dim` in the tier stylesheet (fails 3:1 on surface-overlay, DESIGN.md:506); no local type named `TierItem` outside `ui/src/api/` (wire-contract guard — use `PushedTier`/`UntrustedTier`); no new empty-push sentence — reuse `emptyPushLine` verbatim (the copy-grammar ledger item is deferred, not repaired here); no re-sorting/deduping tiers; no hand-edits under `plugin/`; no authored words in the view if avoidable (letter/name/note/count are wire data or shell props — a COPY_MODULES entry is needed only if a word is authored).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy push | valid `TierListPayload`, app open, ≥1 client | `status="displayed"`, `clients=N`, `items_pushed=len(items)` (tiers); Glass tier-list view opens/replaces in place; "Tier list" pill activates | No error |
| App closed | no discovery file | `status="app_not_running"`, text result, never raises | Degradation ladder |
| No listeners | app up, 0 WS clients | `status="no_clients_connected"`, push not re-sent | No error |
| Over-cap payload | >12 tiers / name >40 / note >200 | Pydantic rejects at tool boundary; endpoint 413 → `payload_rejected` if it gets that far | Never truncated |
| Empty payload | `items=[]` | Pushed anyway; view renders shared `emptyPushLine('tier_list')`, count 0 | No error |
| Empty tier | tier with `card_ids=[]` | Tier is skipped entirely — not rendered as an empty shell (DESIGN.md:590); it still counts toward store `count` | Render-only skip |
| Repeated letter | two `A` tiers, different names | Both render, payload order — legal per contract | No error |
| Unknown card id | UUID not in DB | Thumbnail degrades to unknown-card placeholder; row text still renders | Per-card degradation |
| Malformed tier entry | item missing `letter`/`name` | That tier degrades; other tiers render | Per-tier degradation |
| Auth rejected once | 403 on push | Leaf client re-reads discovery, retries exactly once (existing — do not re-prove) | Existing |

</intent-contract>

## Code Map

**Backend (`src/mcp_server/`):**
- `tools/companion.py` — the consolidation site + new trio. Existing: `ShowSuggestionsResult` :215-253, `_PUSH_MESSAGES` :256-282, `show_suggestions` :285-340; `ShowSwapsResult` :343-379, `_SWAPS_PUSH_MESSAGES` :382-409, `show_swaps` :412-463. Result models are **field-identical** (5-token Literal, `clients`, `items_pushed`, `message`); message tables differ only in the noun ("the suggestions"/"the swaps"); helper bodies differ in 5 tokens (event class+kind, payload type, result class, count-noun pluralizer, success sentence). Consolidate: one message-template builder parameterized by noun + one shared executor taking (event, items_pushed, result_cls, success/noun wording); keep thin public `show_suggestions`/`show_swaps`/`show_tier_list` helpers. Contract imports :41-47 (alphabetical; add `TierListEvent, TierListPayload` after `SwapsPayload`). Tier success sentence shape: "The companion is showing {N} {tier|tiers} in {n} {tab|tabs}."
- `server.py` — imports: payloads :49, results :60-64, helper aliases :65-67. Registration blocks: suggestions :517-563, swaps :565-611; new block at :612 (before `analyze_mana_curve`): `@mcp.tool() async def companion_show_tier_list(payload: TierListPayload) -> ShowTierListResult`, one-line delegation, full agent-facing docstring per Boundaries.
- `src/companion/contracts.py` — READ-ONLY. `TierLetter` :587; `TierItem` :733-780 (`letter`, `name` ≤40 non-blank, `note?` ≤200, `card_ids` ≤60 each ≤128); `TierListPayload` :880-902 (`title?` ≤80 non-blank, `items` ≤12); `TierListEvent` :1112-1155; `EventKind` has `tier_list` :557; `AgentEvent` union :1286; `DEFAULT_TITLE_BY_KIND` :1319.
- `src/companion/client.py` — READ-ONLY. `push_event` :528 already accepts `TierListEvent` via `AgentEvent`; `PushOutcomeToken` :144-150.

**Frontend (`ui/`):**
- `src/state/agentView.ts` — `AGENT_VIEW_LABELS` already has `tier_list: 'Tier list'` :107. Union arm :202-206 currently `items: readonly never[]` → widen to `readonly TierItem[]` (alias from `api/schema`). Mirror `swapsViewOf` :459-472 / `openSwapsPush` :498-500 (title = trimmed `payload.title` else `AGENT_VIEW_LABELS.tier_list`; `count: items.length`).
- `src/state/socket.ts` — import :80 add `TierListEvent`; handler type after `onSwaps` :235-245; destructure ~:339; dispatch: add `tier_list` arm beside swaps :460-465 and shrink the drop pin :466-474 to `groups` only.
- `src/state/connection.ts` — add `onTierList: openTierListPush` beside :162; import :83.
- `src/App.tsx` — import beside :11; render switch :775-779: add `tier_list` arm before the trailing `null`.
- `src/api/schema.ts` — add `TierListEvent = Extract<AgentEvent, {kind:'tier_list'}>` and `TierItem = Schemas['TierItem']` following the SwapsEvent :327 / SwapItem :403 shapes. Generated types already exist (`types.d.ts` TierItem :1204-1240, TierListEvent :1241-1279, TierListPayload :1280-1295) — no regen.
- `src/containers/TierListView/` — NEW (`TierListView.tsx`, `.css`, `.test.tsx`; **no copy.ts** — reuse `emptyPushLine` from `../SuggestionsView/copy`). Model: `SwapsView.tsx` (props from store union arm :57-67; untrusted-field ladder :74-128; module-local thumbnail component = `SwapTile` :147-234 pattern with per-card hooks, placeholder ladder, five inspection verbs; hydration effect :271-279; empty state :305). Tier row: 132px chip on `--surface-well` (DESIGN.md:331-338, :481), 44px/500 letter + name in micro `--text-tertiary` beneath, note in body `--text-secondary`, wrapping thumbnail strip (flex-wrap precedents: AgentView.css:106, ColourDistribution.css:173); grid tracks `minmax(0,1fr)`; micro type travels with `--tracking-micro` + uppercase.
- Design authority: `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md` :331-338 (tier-row tokens), :590 (row anatomy + letter ramp + empty-tier skip), :481 (chip surface), :506 (accent-dim ban), :560 (mock shows tier row — no artefact amendment expected).

**Guard tests that must move (complete list):**
- `tests/integration/test_build_plugin.py` :281-283 tool-name set (+`companion_show_tier_list`); add TierItem schema-publication twin of :323 (assert `"TierItem" in schema`, fields letter/name/note/card_ids/title, maxItems, maxLength, "Scryfall" in description).
- `tests/integration/mcp_server/test_companion_tool.py` — mirror the swaps classes :716-885 for tier list (delegation, five outcomes, empty payload pushed, **counts tiers not cards** twin of :840, compact result), same `_PushStub` :180-206.
- `tests/integration/mcp_server/test_companion_degradation.py` — closed-app-by-name case beside :161-197; class docstring :120 says "both companion tools" (stale — fix in passing).
- `ui/src/state/socket.test.ts` :735-752 drop loop shrinks to `['groups']`; add delivered test in the swaps shape :~700-733 (harness needs a `tierPushes` field).
- `ui/src/App.test.tsx` — :2600 drop loop loses `tier_list`; :5856 disabled-pill pin flips; add wire-driven end-to-end describe modeled on :5493-5569 (16.1's pattern: push through fake socket → dialog title, row anatomy, pill activation, empty-push sibling).
- `ui/tests/shell.test.ts` :1568 CONTAINERS + entry (sorted import allow-list, SwapsView entry :1644-1672 is the shape) + length pin :2244 37→38.
- `ui/src/state/agentView.test.ts` — tierListViewOf/openTierListPush coverage beside the swaps tests; :479/:602 tier_list expectations may move.
- `ui/tests/token-usage.test.ts` :1177 pin 70 must NOT move (no new token). `ui/tests/copy-rules.test.ts` COPY_MODULES only if a word is authored (aim: none).

**Docs/mirrors:** `README.md` :28 catalog cell + :253-254 prose; `CHANGELOG.md` bullet modeled on :23-28; `plugin/server/` mirrors rebuilt byte-identical via `scripts.build_plugin`.

## Tasks & Acceptance

**Execution:**
1. `src/mcp_server/tools/companion.py` — consolidate: noun-parameterized failure-message builder + shared push executor; re-express `show_suggestions`/`show_swaps` over it with byte-identical wording; existing tests untouched and green.
2. `src/mcp_server/tools/companion.py` — add `ShowTierListResult` + `show_tier_list` on the shared path; `items_pushed` = tier count.
3. `src/mcp_server/server.py` — register `companion_show_tier_list` with the full agent-facing docstring — the docstring is the LLM tool description.
4. `tests/integration/mcp_server/test_companion_tool.py` — mirrored tier-list push classes incl. counts-tiers-not-cards; `tests/integration/mcp_server/test_companion_degradation.py` — closed-app case by tool name over a real MCP session.
5. `tests/integration/test_build_plugin.py` — tool-name set + TierItem payload-shape publication test — hard gates.
6. `ui/src/api/schema.ts` + `ui/src/state/agentView.ts` + `ui/src/state/socket.ts` + `ui/src/state/connection.ts` + `ui/src/App.tsx` — wire the `tier_list` kind end-to-end (aliases, union widening, `tierListViewOf`/`openTierListPush`, dispatch arm + drop-pin shrink, `onTierList`, render arm) — tightly coupled, one coherent change.
7. `ui/src/containers/TierListView/` — build the view per DESIGN.md tier-row: chip + ramped letter + name, note, wrapping thumbnail strip with placeholder ladder and inspection verbs, payload order, empty-tier skip, shared empty-push line.
8. `ui/src/containers/TierListView/TierListView.test.tsx` + move the guard pins listed in the Code Map (socket drop pin, App drop loop + disabled-pill, CONTAINERS 37→38, agentView tests, App end-to-end describe).
9. Rebuild: `cd ui && npm run build`, then `uv run python -m scripts.build_plugin`; update `README.md` + `CHANGELOG.md` — commit committed-artifact mirrors.

**Acceptance Criteria:**
- Given the app closed, when the agent calls `companion_show_tier_list`, then the tool returns a text result containing `app_not_running` and does not raise (proven over a real in-memory MCP session).
- Given a connected Glass and a valid tier-list payload, when the tool is called, then the tier-list view opens (or replaces in place), the "Tier list" pill activates with unread behavior, and rows render chip, ramped letter with its name, note, and thumbnails in payload order with empty tiers skipped.
- Given the consolidation, when the full suite runs, then every pre-existing suggestions/swaps push test passes unmodified.
- Given a tier whose card id is unknown, when the strip renders, then that thumbnail shows the unknown-card placeholder while the tier's text still renders.
- Given `items=[]`, when pushed, then `status="displayed"` and the view shows the shared empty-push line for `tier_list`.
- Given the full verification suite, when run, then the tool-name set-equality test, socket dispatch pins, CONTAINERS pin (38), token pin (70, unmoved), and both committed-artifact drift checks all pass.

## Spec Change Log

- 2026-08-21 (implementation): **One guard the Code Map's "complete list" did not anticipate had to move — recorded here rather than slipped through.** The spec ships the tier letter as literal `44px`/`500` with DESIGN.md citations and bans a `--type-*` role in its block, but stylelint's `declaration-property-value-allowed-list` bans `font-size`/`font-weight` longhands outright in every component stylesheet ("a lint error no citation could rescue", AppShell.css:19), and no `--type-*` role carries 44px for StatChip's decide-once route to reach. The only sanctioned exemption mechanism is a `.stylelintrc.json` `overrides` entry (tokens.css's header: "by an `overrides` entry, never by a stylelint-disable comment"), so one was added, scoped to `src/containers/TierListView/TierListView.css` and admitting exactly `44px`, `500` and `line-height: 1` beside the CSS-wide keywords. `ui/tests/lint-gates.test.ts`'s overrides pin (2 → 3 entries — the pin whose stated purpose is that "another entry is a decision, not a detail") moved with it, and a new narrowness test pins the widened values byte-for-byte plus every other family byte-identical to the base rule. Token pin (70) and CONTAINERS/tokens guards otherwise unmoved. Also moved, same shape as 16.1's precedents: `keyboard-floor.test.ts` WELL_CLEAR gains `tier-tile` (derived geometry: 6lh ≈ 126px × ≈90px), and `token-usage.test.ts` INVENTORY_CLAIMS gains `.tier-tile-image :: opacity` under the existing "Image fade-in" family row.

## Review Triage Log

### 2026-08-21 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 3: (high 0, medium 1, low 2)
- defer: 0
- reject: 15: (high 0, medium 2, low 13)
- addressed_findings:
  - `[medium]` `[patch]` The consolidation's byte-identity promise was enforced by no test, and two docstrings claimed wording-pin tests that did not exist — cross-wiring `show_tier_list` onto `_SWAPS_PUSH_MESSAGES` with a "suggested cards" subject would have passed the whole suite. Fixed: new `TestEveryPushToolSpeaksItsOwnNoun` class asserts each module table equals `_push_messages(noun)` by name, pins the four suggestions failure sentences byte-for-byte as literals, and per tool asserts the `app_not_running` noun and the full `displayed` success sentence at both counts; the two false docstring claims now point at that class by name.
  - `[low]` `[patch]` The documented deliberate "skipped tiers' ids hydrate too" behavior was unpinned — iterating the filtered rows instead of raw `items` passed every test. Fixed: hydration test pairing a gated-out tier (`letter:'F'`) with a `/api/cards/c-tier-9` fetch assertion.
  - `[low]` `[patch]` A whitespace-only note (wire-legal — `contracts.py` blank-checks `name` but not `note`) rendered an empty `.tier-row-note` element. Fixed: `noteOf` folds whitespace-only to `null`, with a docstring explaining why the fold exists here and not on the swap rationale; whitespace-sibling test added. SwapsView checked — rationale is non-blank on the wire, no change needed.

## Design Notes

- Consolidation shape: the four failure sentences are pure "…the {noun}…" templates → one builder `_push_messages(noun)`; the success sentence and count noun vary per kind → pass them (or a preformatted success string) into the shared executor. `items_pushed` is caller-computed — the one real semantic difference between kinds (tiers vs cards vs pairs).
- Empty-push copy ledger (copy.ts:33-41, copy-rules:433-437): "The agent sent an empty tier_list." ships as-is. The template is artefact-gated byte-for-byte; a per-kind noun is copy no artefact carries and touches all views. Record as deferred with three data points and the recommendation (amend EXPERIENCE.md's Voice-and-Tone cell, substitute lowercased `AGENT_VIEW_LABELS`).
- Local type hygiene: `PushedTier`/`UntrustedTier` aliases (wire-contract guard bans `TierItem` outside `src/api/`). Letter ramp via a data-attribute or per-letter class; unknown letters (untrusted ladder) degrade the tier.
- The 132px/44px/500 literals carry inline `DESIGN.md components.tier-row` citations (shell.test.ts px guard, SwapsView.css:13 shape). No `--type-*` role var in the letter's declaration block (role-companion rule).

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check .` -- expected: clean
- `uv run mypy src/` -- expected: clean (strict)
- `uv run pytest` -- expected: all pass, pre-existing push-tool tests unmodified
- `cd ui && npm run lint && npm run format:check && npm run typecheck` -- expected: clean
- `cd ui && npm test` -- expected: all pass (shell/tokens/wire-contract/copy/socket gates included)
- `cd ui && npm run build && cd .. && uv run python -m scripts.build_plugin` -- expected: succeeds; `git status` shows only intended files; plugin tree byte-matches

## Auto Run Result

Status: done

**Summary:** Story 16.2 shipped: the push-tool internals were consolidated first (a noun-parameterized `_push_messages(noun)` failure-sentence builder and a shared `_execute_push` executor over the three field-identical result classes, with suggestions/swaps wording byte-identical — now pinned by test, discharging 16.1's deferred duplication item), then `companion_show_tier_list(payload)` was added on the shared path (async, never raises, closed five-token outcome + client count, compact result, `items_pushed` counts tiers never cards) together with the TierListView container (132px chip on `--surface-well`, 44px/500 letter with the five-stop S/A/B/C/D color ramp via `data-letter` and the tier name as the accessible carrier of rank, optional note, wrapping thumbnail strip with the full placeholder ladder and inspection contract, payload order, empty/malformed tiers skipped render-only, shared empty-push line), wired through socket dispatch → `openTierListPush` → the App render switch. No changes to `contracts.py`, `client.py`, or any backend route — the epic's "no contract change" premise held.

**Files changed:**
- `src/mcp_server/tools/companion.py` — consolidation (`_push_messages`, `_execute_push`) + `ShowTierListResult`, `_TIER_LIST_PUSH_MESSAGES`, `show_tier_list`; `show_suggestions`/`show_swaps` re-expressed over the shared path.
- `src/mcp_server/server.py` — registers `companion_show_tier_list` with the full agent-facing docstring (Scryfall UUIDs, all caps, closed letters, tiers-not-cards, empty-list legitimacy).
- `ui/src/containers/TierListView/{TierListView.tsx,TierListView.css,TierListView.test.tsx}` — new container + tests (no copy.ts; shared `emptyPushLine`).
- `ui/src/api/schema.ts`, `ui/src/state/{agentView.ts,socket.ts,connection.ts}`, `ui/src/App.tsx` — tier_list kind wired end-to-end; union arm widened from `readonly never[]`.
- `ui/.stylelintrc.json` — narrowly-scoped overrides entry for TierListView.css admitting exactly `44px`/`500`/`line-height: 1` (the sanctioned exemption route; see Spec Change Log).
- Tests/guards moved: `tests/integration/test_build_plugin.py` (tool-name set + TierItem schema publication), `tests/integration/mcp_server/test_companion_tool.py` (mirrored tier-list classes + `TestEveryPushToolSpeaksItsOwnNoun` wording pins), `test_companion_degradation.py` (closed-app by name; stale docstring fixed), `ui/src/App.test.tsx` (wire-driven end-to-end describe; drop loop and disabled-pill pins moved), `ui/src/state/socket.test.ts` (drop list → `['groups']`, delivered test), `ui/src/state/agentView.test.ts`, `ui/tests/{shell,keyboard-floor,token-usage,lint-gates}.test.ts` (CONTAINERS 37→38, WELL_CLEAR `tier-tile`, image-fade inventory row, stylelint overrides pin 2→3 + narrowness test).
- Docs/artifacts: `README.md` + `CHANGELOG.md`; committed SPA bundle in `src/companion/app/static/` and the `plugin/` mirror rebuilt (byte-matching).

**Review findings:** 3 patches applied (0 high, 1 medium, 2 low — see Review Triage Log), 0 deferred from review (the empty-push copy-grammar ledger item in frontmatter `deferred` was recorded at planning, now with three data points), 15 rejected.

**Follow-up review recommendation:** true — patched counts: high 0, medium 1, low 2; score 3×1 + 1×2 = 5, which meets the ≥5 threshold.

**Verification:** ruff check + format clean; mypy src/ clean (strict, 94 files); pytest 3292 passed / 1 skipped; ui eslint/stylelint, prettier, tsc clean; vitest 2392 passed (82 files); `npm run build` + `scripts.build_plugin` green with mirrors byte-matching and only intended files in `git status`. Matrix audit: every I/O row covered by a test that ran and passed (over-cap boundary via pre-existing contract cap tests + the five-outcome `payload_rejected` mapping; auth-retry via pre-existing leaf-client coverage per the matrix's own "do not re-prove").

**Residual risks:** the empty-push line renders the raw wire token ("an empty tier_list", underscore visible) — deliberate, artefact-gated, carried in frontmatter `deferred` with an EXPERIENCE.md-first recommendation; the stylelint overrides entry for the 44px letter is a lint-policy decision the spec's Block-If did not enumerate (documented in the Spec Change Log; the overrides pin and narrowness test make it loud for human review); tier-tile geometry (6lh ≈ 126px wells) has no DESIGN.md pixel authority beyond the chip/letter values — flag for manual visual check, same as 16.1's swap tiles; the "showing 0 tiers in 1 tab" success message for a legitimate empty push is shared pre-existing wording across all three kinds.
