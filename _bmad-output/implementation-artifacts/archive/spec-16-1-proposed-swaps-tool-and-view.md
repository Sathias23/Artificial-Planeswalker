---
title: 'Proposed swaps — tool and view'
type: 'feature'
created: '2026-08-21'
status: 'done'
baseline_revision: 'b3798a5e4762f8911a0b3818fa0b5a229b2cef15'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: [oversized]
deferred:
  - summary: >-
      The push-tool result/messages trio (ShowSwapsResult, _SWAPS_PUSH_MESSAGES, show_swaps) is a
      near-verbatim clone of the suggestions trio; stories 16.2 and 16.3 will add a third and fourth
      copy unless a noun-parameterized message table and shared push-result helper are factored out first.
    evidence: |-
      src/mcp_server/tools/companion.py now carries two structurally identical result models,
      message tables, and helper bodies differing only in nouns; the epic ships two more push kinds.
      Raised by blind-hunter review of the 16.1 diff; consolidation is a 16.2-planning decision,
      not this story's, since the spec directed the clone shape for pattern consistency.
    location: >-
      src/mcp_server/tools/companion.py
    severity: low
---

<intent-contract>

## Intent

**Problem:** The agent has no way to push proposed card swaps to the companion Glass: the `swaps` wire contract exists end-to-end, but no MCP tool mints a `SwapsEvent`, and the SPA's dispatch switch silently drops `swaps` frames — a push kind that would arrive unrenderable.

**Approach:** Add the `companion_show_swaps(payload)` MCP push tool as a structural clone of `companion_show_suggestions` (helper + registration + docstring), and a `SwapsView` container rendering out/in card pairs per the Voltglass swap-row spec, wired through the existing socket dispatch, agent-view store, and App render switch. No contract change; no backend route change.

## Boundaries & Constraints

**Always:**
- Tool is `async def`, never raises, posts a self-built `SwapsEvent` through the existing leaf client (`push_event`), and returns exactly one of `displayed | app_not_running | no_clients_connected | payload_rejected | backend_error` plus the client count; result JSON stays under the ~400-char compactness bound; no payload echo.
- The agent-facing docstring on the registered tool must state Scryfall printing UUIDs (not names), payload field caps, empty-list legitimacy, and "send here **and** give your normal answer" — mirroring `companion_show_suggestions`.
- View: tints (`--negative`/`--positive`) on the "Out · N copies"/"In · N copies" micro labels only, never on art; arrow glyph uses `var(--accent)` (accent-dim fails 3:1 on surface-overlay); thumbnails use `alt=""`; every value from the token scale; payload order preserved; one malformed item degrades that row only.
- Standard inspection contract on both tiles (hover/focus set detail target, click pins); hydration effect keyed on `items`, not mount.
- After UI changes: rebuild SPA into `src/companion/app/static/` AND rerun `scripts.build_plugin`; commit both mirrors.

**Block If:** the change appears to require editing `src/companion/contracts.py`, `src/companion/client.py`, or any backend route (red flag against the epic's "no contract change" premise); or the CONTAINERS/tokens guard tests cannot pass without weakening an existing pin other than the ones listed in Tasks.

**Never:** no generic `companion_display`; no per-session server state; no card-ID validation at ingest or in the tool; no new design primitive (build a container); no price/curve StatChips (wire carries no price by ruling — `ui/src/api/types.d.ts:1124-1138`; render confidence only); no re-declaring backend type names outside `ui/src/api/`; no edits to skills (no skill enumerates companion tools); no hand-edits under `plugin/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy push | valid `SwapsPayload`, app open, ≥1 client | `status="displayed"`, `clients=N`, `items_pushed=len(items)`; Glass swaps view opens/replaces in place | No error |
| App closed | no discovery file | `status="app_not_running"`, tool returns text result, never raises | Degradation ladder |
| No listeners | app up, 0 WS clients | `status="no_clients_connected"`, message says push not re-sent | No error |
| Over-cap payload | >60 items / rationale >600 | FastMCP/pydantic rejects at tool boundary; endpoint 413 → `payload_rejected` if it gets that far | Never truncated |
| Empty payload | `items=[]` | Pushed anyway; view renders `emptyPushLine('swaps')` empty state, count 0 | No error |
| Unknown card id | UUID not in DB | Tile degrades to unknown-card placeholder; row still renders its text; id not inspectable | Per-row degradation |
| `in_qty=0` | zero-copy "in" card | Renders normally reading "In · 0 copies" | No error |
| Auth rejected once | 403 on push | Leaf client re-reads discovery, retries exactly once (existing behavior — do not re-prove wire) | Existing |

</intent-contract>

## Code Map

**Backend (pattern source → clone target):**
- `src/mcp_server/tools/companion.py` — add `ShowSwapsResult` + `async def show_swaps` mirroring `ShowSuggestionsResult` (:209-247) and `show_suggestions` (:279-334); reuse `_PUSH_MESSAGES` (:250-276); add `SwapsEvent, SwapsPayload` to the contracts import (:39-41). Push tools echo nothing.
- `src/mcp_server/server.py` — register `@mcp.tool() async def companion_show_swaps(payload: SwapsPayload) -> ShowSwapsResult`, one-line delegation, agent-facing docstring; pattern at :512-557; imports at :49, :60-62. Place beside the other companion tools.
- `src/companion/contracts.py` — READ-ONLY. `SwapItem` :671-729 (`out_card_id, in_card_id, rationale≤600, out_qty≥0, in_qty≥0, confidence?`), `SwapsPayload` :858-876 (`title?≤80`, `items≤60`), `SwapsEvent` :1064-1108, already in `AgentEvent` union :1285 and `EventKind` :554.
- `src/companion/client.py` — READ-ONLY. `push_event` :528 takes a built envelope; `PushOutcome`/five tokens :144-194.
- `src/companion/app/routes/agent_events.py` — READ-ONLY; relay is kind-agnostic (:64-104), no backend branch needed.

**Frontend (ui/):**
- `ui/src/containers/SuggestionsView/SuggestionsView.tsx` + `.css` — the model: `UntrustedItem` field gates (:100-166), module-local row component with per-card hooks (:234-354), placeholder ladder unknown/failed/loading (:305-354), hydration effect (:422-425), empty state (:459-467).
- `ui/src/containers/SwapsView/` — NEW container (`SwapsView.tsx`, `SwapsView.css`, tests). Reuse `emptyPushLine` from `../SuggestionsView/copy.ts` (template is kind-generic; do not author a second sentence — `ui/tests/empty-push-copy.test.ts` pins the copy).
- `ui/src/state/agentView.ts` — `AGENT_VIEW_LABELS` already has `swaps` (:100); add `swapsViewOf`/`openSwapsPush` beside :395/:423; **structural change**: `AgentViewContent.items` (:176, `readonly SuggestionItem[]`) must become a per-kind discriminated union — ripples into `SuggestionsViewProps` and App switch.
- `ui/src/state/socket.ts` — dispatch switch :433-466 currently drops `swaps` (:454-457); add `onSwaps` handler (type at :234, destructure at :326).
- `ui/src/state/connection.ts` :158 — wire `onSwaps: openSwapsPush`.
- `ui/src/App.tsx` :774-776 — the render kind switch; add the `swaps` arm.
- `ui/src/api/schema.ts` — add `SwapsEvent`/`SwapItem` aliases following :309/:367; generated `SwapItem`/`SwapsPayload` already exist in `ui/src/api/types.d.ts` :1139-1203 (no type regen needed).
- Primitives: `CardPlaceholder` (three variants), `ManaCost`, `Badge`; tokens in `ui/src/styles/tokens.css` (`--surface-overlay`, `--negative` :123, `--positive` :121, `--type-micro` :148, `--radius-md`); swap-row artefact spec `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md` :324-330, :589. Prefer zero new tokens (tokens gates pin count at 70); crossfade + reduced-motion come free via `.agent-view-body`.

**Guard tests that must move (complete list):**
- `tests/integration/test_build_plugin.py` :256 set-equality over tool names (add `companion_show_swaps`); sibling of :294-320 asserting `SwapItem` schema publication.
- `ui/src/state/socket.test.ts` :675 pins that `swaps` is dropped — flip it.
- `ui/tests/shell.test.ts` :1568 CONTAINERS table + :2209 length pin 36→37 — add `SwapsView` entry with exact import allow-list.
- Test patterns: `tests/integration/mcp_server/test_companion_tool.py` (`_PushStub` :148, push-tool classes :475-680), `tests/integration/mcp_server/test_companion_degradation.py` :119-190, `ui/src/containers/SuggestionsView/SuggestionsView.test.tsx` (real stores reset per test, no mocks).

## Tasks & Acceptance

**Execution:**
1. `src/mcp_server/tools/companion.py` — add `ShowSwapsResult` + `show_swaps` helper — push-tool clone, never raises, compact result.
2. `src/mcp_server/server.py` — register `companion_show_swaps` with full agent-facing docstring — the docstring is the LLM tool description.
3. `tests/integration/mcp_server/test_companion_tool.py` — mirror the four push-tool test classes for swaps (delegation/passthrough, five-outcome vocabulary, empty payload pushed, compact result <400 chars) — same `_PushStub` harness.
4. `tests/integration/mcp_server/test_companion_degradation.py` — add closed-app case calling `"companion_show_swaps"` by name over a real MCP session — AC1 token-in-text.
5. `tests/integration/test_build_plugin.py` — add tool name to the set-equality list + a `SwapItem` payload-shape publication test — hard gates.
6. `ui/src/state/agentView.ts` + `ui/src/state/socket.ts` + `ui/src/state/connection.ts` + `ui/src/App.tsx` + `ui/src/api/schema.ts` — wire the `swaps` kind end-to-end (union widening, `openSwapsPush`, dispatch arm, render arm, type aliases) — tightly coupled, one coherent change.
7. `ui/src/containers/SwapsView/` — build the view: out/in tiles joined by accent arrow on `surface-overlay`, tinted micro labels above tiles, rationale right of the pair in body `text-secondary`, confidence beneath, placeholder ladder, inspection verbs, empty state via shared copy — per DESIGN.md swap-row.
8. `ui/src/containers/SwapsView/SwapsView.test.tsx` + update `ui/src/state/socket.test.ts` :675, `ui/src/state/agentView.test.ts`, `ui/tests/shell.test.ts` CONTAINERS — cover rendering, degradation, labels/tints, alt="", empty state, dispatch flip.
9. Rebuild: `cd ui && npm run build`, then `uv run python -m scripts.build_plugin`; update `README.md` :28/:252 catalog row+prose — commit committed-artifact mirrors.

**Acceptance Criteria:**
- Given the app closed, when the agent calls `companion_show_swaps`, then the tool returns a text result containing `app_not_running` and does not raise (proven over a real in-memory MCP session).
- Given a connected Glass and a valid swaps payload, when the tool is called, then the swaps view opens (or replaces in place on repeat push), the nav "Swaps" pill activates with unread behavior, and rows render out/in tiles with tinted labels, arrow, rationale, and confidence in payload order.
- Given a payload item whose card id is unknown, when the row renders, then the tile shows the unknown-card placeholder while the row's text still renders.
- Given `items=[]`, when pushed, then `status="displayed"` and the view shows the shared empty-push line for swaps.
- Given the full verification suite, when run, then the tool-name set-equality test, socket dispatch pin, CONTAINERS pin, token gates, and both committed-artifact drift checks all pass.

## Spec Change Log

## Review Triage Log

### 2026-08-21 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 4: (high 1, medium 1, low 2)
- defer: 1: (high 0, medium 0, low 1)
- reject: 12
- addressed_findings:
  - `[high]` `[patch]` No wire-driven App-level test: the App.tsx swaps render arm, connection.ts `onSwaps` wiring, and pill-activation AC were only proven as separate seams (reverting the render arm left the suite green). Fixed: new "a swaps push opens its view, end to end (16.1)" describe in ui/src/App.test.tsx drives `push('swaps', …)` through the fake socket and asserts dialog title, `.swap-row` rationale, out/in labels, pill activation, and hydration; empty-push sibling asserts the fallback title and shared empty line; AC-5 store-seam test now asserts `.swaps-view-empty` so its comment no longer overstates coverage. Mutation-proved (reverting the render arm reddens both tests).
  - `[medium]` `[patch]` Story AC names StatChips beneath the rationale but confidence rendered as a plain micro span. Fixed: confidence now renders as `<StatChip label="Confidence" value={…}/>` (no delta); price/curve remain struck per the frozen-contract ruling; CONTAINERS allow-list, COPY_MODULES, CSS, and SwapsView tests updated.
  - `[low]` `[patch]` `payload_rejected` described inconsistently ("the swaps themselves" vs "the envelope itself") and docstring omitted the non-blank rationale rule. Fixed: both surfaces now say the companion refused the envelope at the shape-validation boundary; rationale documented as required, non-blank, ≤600 chars.
  - `[low]` `[patch]` CHANGELOG `[Unreleased]` names the other companion tools but omitted this one. Fixed: `companion_show_swaps` bullet added in the existing style (CHANGELOG is not mirrored into plugin/, verified).

## Design Notes

- `AgentViewContent` union widening is the one real structural change; keep each view's props derived from the store type (`AgentViewContent & {kind:'swaps'}`-style narrowing), never from wire types — `wire-contract.test.ts` bans backend names outside `src/api/`.
- Each swap row renders two card tiles → hooks per card: use a module-local `SwapTile` component (per-card `useCardEntry`/`useCardArt`/inspection), composed twice inside a module-local `SwapRow`.
- No new motion: crossfade lives on `.agent-view-body`; image fade-in/live-tint fallbacks are already registered in the tokens.css reduced-motion inventory.
- Reuse `_PUSH_MESSAGES` if its wording is kind-neutral; clone with adjusted nouns only if not. `items_pushed` counts swap pairs.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check .` -- expected: clean
- `uv run mypy src/` -- expected: clean (strict)
- `uv run pytest` -- expected: all pass, including the moved guard tests
- `cd ui && npm run lint && npm run format:check && npm run typecheck` -- expected: clean
- `cd ui && npm test` -- expected: all pass (shell/tokens/wire-contract/copy gates included)
- `cd ui && npm run build && cd .. && uv run python -m scripts.build_plugin` -- expected: succeeds; `git status` shows only intended files; plugin tree byte-matches

## Auto Run Result

Status: done

**Summary:** Story 16.1 shipped: `companion_show_swaps(payload)` MCP push tool (async, never raises, closed five-token outcome + client count, compact result) and the SwapsView container (out/in tiles joined by an accent arrow on surface-overlay, negative/positive tints on the micro labels only, rationale in body text-secondary with a Confidence StatChip beneath, placeholder ladder, full inspection contract, shared empty-push line), wired through socket dispatch → `openSwapsPush` → the App render switch. `AgentViewContent` became a per-kind discriminated union. No changes to `contracts.py`, `client.py`, or any backend route — the epic's "no contract change" premise held.

**Files changed:**
- `src/mcp_server/tools/companion.py` — `ShowSwapsResult`, `_SWAPS_PUSH_MESSAGES`, `show_swaps` helper (push-tool clone of suggestions).
- `src/mcp_server/server.py` — registers `companion_show_swaps` with the full agent-facing docstring (Scryfall UUIDs, caps, non-blank rationale, empty-list legitimacy).
- `ui/src/containers/SwapsView/{SwapsView.tsx,SwapsView.css,SwapsView.test.tsx}` — new container + tests.
- `ui/src/state/{agentView.ts,socket.ts,connection.ts}`, `ui/src/App.tsx`, `ui/src/api/schema.ts` — swaps kind wired end-to-end; content union widened.
- `ui/src/containers/SuggestionsView/SuggestionsView.tsx` — props re-derived from its own union arm.
- Tests/guards moved: `tests/integration/test_build_plugin.py` (tool-name set + SwapItem schema publication), `tests/integration/mcp_server/test_companion_tool.py` (four mirrored push classes), `test_companion_degradation.py` (closed-app by name), `ui/src/App.test.tsx` (wire-driven end-to-end describe + AC-5 assertion), `ui/src/state/socket.test.ts` (drop-pin flipped), `ui/src/state/agentView.test.ts`, `ui/tests/{shell,copy-rules,keyboard-floor,token-usage}.test.ts`.
- Docs/artifacts: `README.md` + `CHANGELOG.md`; committed SPA bundle in `src/companion/app/static/` and the `plugin/` mirror rebuilt (byte-matching).

**Review findings:** 4 patches applied (1 high, 1 medium, 2 low — see Review Triage Log), 1 deferred (push-tool result/message duplication ahead of 16.2/16.3), 12 rejected.

**Follow-up review recommendation:** true — a high-severity finding was patched this pass (patched counts: high 1, medium 1, low 2; score 3×1 + 1×2 = 5, and the high alone forces true).

**Verification:** ruff check + format clean; mypy src/ clean (strict); pytest 3260 passed / 1 skipped; ui eslint/stylelint, prettier, tsc clean; vitest 2347 passed; `npm run build` + `scripts.build_plugin` green with mirrors byte-matching and only intended files in `git status`. Matrix audit: every I/O row covered by a test that ran and passed.

**Residual risks:** swap-tile thumbnail height uses a `6lh` derivation with no DESIGN.md pixel authority (flag for manual visual check); no live/hover tint on swap tiles (DESIGN.md's swap-row specifies none — focus ring + detail panel are the feedback); count labels use the contract's fixed "N copies" wording, so "1 copies" appears for a singular count (no singular form is specified anywhere); narrow-viewport squeeze of the rationale column is untreated (desktop-posture app, no responsive spec for the row).
