---
title: 'c7-3: The glass refetches on deck_changed, coalesced and latest-wins'
type: 'feature'
created: '2026-08-14'
status: 'review'
review_loop_iteration: 0
baseline_revision: 'f068932610bba3bbb0ea81688f4606799c55d2c7'
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-c7-context.md'
warnings: ['oversized']
deferred: []
---

<intent-contract>

## Intent

**Problem:** Today every `deck_changed` frame re-drives the full two-request boot regardless of which deck changed — the payload's `deck_id` is deliberately unread (c6-3 ruling #2 reserved the branch for this story), a burst of edits costs 2N requests with no cancellation, and the format-check panel goes stale forever after any edit (ledgered to c7-3 in `deferred-work.md:4772`).

**Approach:** Widen the socket's `onSystemEvent` seam to carry the event, branch in `connection.ts` on kind, and give the deck slice a single-request coalesced refetch: matching (or deck-agnostic) `deck_changed` on a settled deck refetches only `GET /api/deck/{id}` with abort-on-supersede + generation guard (one in-flight, last response wins); a different deck's event does not touch the active deck; unsettled/none/refused states keep the authoritative full re-drive. The format check re-keys on detail identity so it refreshes with every settled refetch.

## Boundaries & Constraints

**Always:** `connection.ts` keeps zero `setState` and names no store (writer-scan invariant); the deck slice's new verbs live in `ui/src/state/deck.ts` (its pinned writer module). The refetch is the existing boot machinery extended (shared generation, shared settle/refusal mapping, seeds card summaries) — never a second boot implementation. Read `payload.deck_id` totally: missing/null/blank → null → "refetch whatever is active". `restartPollIfStopped()` still runs for every system event (the "deck list may refresh regardless" half). Refetch outcome mapping: `deck_not_found` clears to `{status:'none'}` (UX-DR35: "a 404 clears to no-active-deck"); every other refusal/exception leaves the loaded deck untouched (UX-DR35 never-teardown + accepted staleness). Superseding a refetch aborts its HTTP request (caller `AbortSignal` merged with the existing timeout signal inside `client.ts`'s one door) and its response can never settle (generation). Reconnect refetch already ships (c5-6) — cite, don't rebuild. All firing proofs run through `scripts/vitest_probe_harness` (warm control first). Runtime `ui/` diff → rebuild `src/companion/app/static/` and `plugin/`, commit both.

**Block If:** The mismatch rule needs the client to know the server-side active deck id somewhere other than the settled `detail.id` (would require new state or an extra request — a design change); `AbortSignal.any` is unavailable in the repo's jsdom/node floor and no clean merge fallback fits inside `request()`; the format-check re-key breaks an AC of c4-10 that cannot be honestly amended (beyond the two pinned counts named in the Code Map).

**Never:** No timers anywhere on this path — no debounce, no `requestAnimationFrame` (the supersede-and-restart machinery IS the coalescing; `store-writes.test.ts` bans timers in `deck.ts`). No diffs or patches (NFR-04). No shimmer/updating indicator, pin eviction, or DFC work (c7-4); no announcements (c7-5); no deletion-UX or agent-view interactions beyond preserving today's 404-clear (c7-6). No backend or wire-contract changes (`deck_changed` already carries a nullable `deck_id`). No new store, no second network door, no dedupe of duplicate events (c6-3 ruling #3). Do not weaken the poll edge-trigger semantics or reorder App.tsx's measured effect blocks.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Matching refetch | Settled `'deck'`, event `deck_id == detail.id` | Exactly one `GET /api/deck/{id}`; zero `GET /api/active-deck`; on 200: seed summaries, settle new detail/boards — grid, deck list, group counts, curve, colours all recompute; hydration sweep + format check re-fire off the new detail | N/A |
| Deck-agnostic event | Settled `'deck'`, `deck_id` null/absent/blank | Same as matching (refetch the active deck) | N/A |
| Different deck | Settled `'deck'`, `deck_id != detail.id` | Zero deck/active-deck requests; `restartPollIfStopped()` still called | N/A |
| Burst | 3 matching events in quick succession | Each newer event aborts + restarts: prior fetch's signal aborted, ≤1 in flight, exactly one settle from the last response | N/A |
| Out-of-order | Older response resolves after newer one | Older response discarded by generation; state = newest | N/A |
| Refetch 404s | Deck deleted server-side | Clears to `{status:'none'}` → no-active-deck panel (today's mapping; 7.6 refines) | N/A |
| Refetch fails otherwise | `unreachable` / 5xx / malformed rows | Loaded deck stays on screen unchanged; outcome dropped; recovery via next event, reconnect, or poll edge | Silent drop (staleness accepted) |
| Mid-boot event | Any `deck_changed` while a boot/re-drive sequence is unsettled | Fold into a fresh full re-drive (`stop()`/`start()`) — never a single-deck refetch against a possibly-departing id | N/A |
| No deck loaded | `'none'` / `'refused'` | Full re-drive (today's behavior — recovers the unreachable-blip and 404-residue windows) | N/A |
| Reconnect | Socket reopens after ≥1 failure | Already shipped: `onReconnected` → `redriveDeckBoot()` (c5-6) — unchanged, cited | N/A |

</intent-contract>

## Code Map

- `ui/src/state/socket.ts` -- dispatch switch `receive` :425-459; today `deck_changed`/`active_deck_changed` → `onSystemEvent(event.kind)` :429-433. Widen `AgentSocketOptions.onSystemEvent` :208 to carry the typed event (the docstring :209-215 reserved this seam). `SystemEventKind` :179. Do not touch timing/ticket logic.
- `ui/src/state/connection.ts` -- THE branch site (c6-3 ruling #2 authorizes it now). `onSystemEvent` handler :105-117 currently calls `redriveDeckBoot()` + `restartPollIfStopped()` for both kinds. New: `active_deck_changed` → unchanged; `deck_changed` → new deck.ts verb with the event's folded `deck_id`; `restartPollIfStopped()` stays for both. Holds no `setState`, names no store (:10-19) — preserve. Module header's "payload deliberately never read" doctrine (:57-65, :105-114) must be rewritten for the half this story overturns.
- `ui/src/state/deck.ts` -- sole deck-store writer (`store-writes.test.ts` row :83-87 names this module as `deck_changed`'s home). `createDeckBoot` :317-400: shared `generation` re-checked after both awaits :339/:360, `settle` :327-330, blank-id gate :352, `seedCardSummaries` + settle :381-382, refusal maps `deckRefusalState` :260 / `stateForPanel` :246 (404 → `'none'`). Module slot `mounted` :513, `redriveDeckBoot` :515-519, `useDeckState` :554-577. Add: a refetch capability on the boot (single `readDetail` run sharing generation/settle, own `AbortController`, aborted on any supersede) + an exported entry verb (shape of `redriveDeckBoot`) implementing the matrix decision table, reading current state via `useDeckStore.getState()`. Boot-unsettled detection is implementer's choice (e.g. settled-generation bookkeeping) — behavior in the matrix is what's pinned. Timers banned here (`store-writes.test.ts` :203-215).
- `ui/src/api/client.ts` -- the ONE network door (posture test pins `['src/api/client.ts']`). `request()` :765-802 owns `AbortSignal.timeout(READ_TIMEOUT_MS)` :776 and takes no caller signal; `readDeck` :897-906. Thread an optional `signal` through (merge via `AbortSignal.any`; node 20.3+/current jsdom have it — verify at implement time, else a small manual merge stays inside `request()`). Readers stay total outcome unions — an abort maps to a discarded outcome, never a throw.
- `ui/src/api/schema.ts` -- add `DeckChangedEvent`/system-event aliases via `Extract<AgentEvent, …>` following `SuggestionsEvent` :308 precedent. `agentEventOf` (`client.ts:701-716`) validates only `kind` — the `deck_id` read must survive a payload-less frame (schema.ts :302-307 warns about exactly this).
- `ui/src/App.tsx` -- `deckId` derivation :205-210 (comment rules out `detail`-keying — this story overturns that ruling, ledgered); format-check effect :394-401 keyed `[deckId, emptyDeck]` → re-key on detail identity so every settled refetch re-runs the check; body (empty-deck clear) unchanged. DO NOT reorder the measured effect blocks (:375-393 warning). Hydration sweep :302-305 already keys on `detail` — refetch settles re-fire it for free.
- `ui/src/state/formatCheck.ts` -- module header :26-43 names c7-3 as the refetch owner; `loadFormatCheck`/generation :141-212 pattern unchanged (no timer, no retry). Update the header's "no refetch" ruling text.
- `ui/src/App.test.tsx` -- the home for app-level tests (4081 lines; new envelope-driven tests go here, not a new file). Harness: `FakeSocket`/`push(kind, payload, id)` :143 (never hand-roll frames), `answering()` :354-388 (route order load-bearing: `/format-check` before `/api/deck/`), `booting()` :233, `pathsSince()` :2902, assert-by-path (never total call counts), fake timers + `settle()`/`advance()` :413-415, `beforeEach` reset :417-436 (does NOT reset inspection slice / `deckMemory`). Amend the pinned counts this story intentionally changes: :2538-2559 "refetches on deck_changed…" (full boot → single-request) and the c4-10 "one format-check request per deck id per mount" pin (now: one per settled detail; :2515's duplicate-`active_deck_changed` count grows by its format-check re-asks).
- `ui/src/state/deck.test.ts` -- store-level suite with injected readers (:1-17 explains the split) — right home for refetch sequencing/generation/abort unit coverage; `resetDeckState()` is tests-only.
- `ui/src/state/socket.test.ts` -- dispatch block :599-675 asserts today's `onSystemEvent(kind)` signature — update alongside the widening, don't duplicate its coverage elsewhere.
- `ui/tests/store-writes.test.ts` (:77-138, :203-215), `ui/tests/shell.test.ts` :2071-2086, `ui/tests/posture.test.ts` :321-357 -- guard suites that must pass unchanged (no new writer, no timers in deck.ts, one door, App.tsx off the wire).
- `scripts/vitest_probe_harness.py` -- firing-proof harness: `uv run python -m scripts.vitest_probe_harness --control` warm (one prior `npm test`), then `--expect-total N --expect-red '<substring>'` per plant, revert (`git diff --exit-code`), then `--expect-total N --expect-green`. First story to adopt it in Task 0 (closes the R2 loose end, sprint-status:2).
- `.github/workflows/ci.yml` :100-222 -- frontend gate: lint, format:check, typecheck, test, build, SPA-bundle drift (:164-181), generated-types drift. Build output `src/companion/app/static/` (committed; `emptyOutDir`); pre-commit `build-plugin-sync` watches `^src/` so the static rebuild also rebuilds `plugin/`.

## Tasks & Acceptance

**Execution:**
- [x] Task 0: baseline -- run `cd ui && npm test` (warm) then `uv run python -m scripts.vitest_probe_harness --control`; record the `--expect-total` baseline in this file.
  - Baseline control (pre-implementation, warm): `vitest: 75 files / 2123 tests, 0 failed, exit 0` → `--expect-total 2123`. (The first cold `npm test` hit the recorded C6 R5 eslint-timeout flake; the warm re-run and the control were both clean.)
- [x] `ui/src/api/schema.ts` + `ui/src/api/client.ts` -- add the system-event aliases; thread optional `signal` through `request()` → `readDeck` (merged with the timeout signal), readers stay total. (`AbortSignal.any` verified present on node 24 / jsdom 29 at implement time; it is still `typeof`-guarded with a manual-merge fallback inside `request()`, matching the module's existing `AbortSignal.timeout` browser-floor posture — `any` postdates `timeout` in browsers.)
- [x] `ui/src/state/socket.ts` -- widen `onSystemEvent` to carry the event; keep the exhaustiveness `never` check. (`SystemEventKind` is now derived from the new `SystemEvent` union.)
- [x] `ui/src/state/deck.ts` -- boot refetch capability + exported entry verb per the matrix (shared generation/settle/seeding, abort-on-supersede, 404-clears / otherwise-drop mapping, mid-boot fold, none/refused re-drive). (Entry verb `refetchOnDeckChanged`; the decision table is `driveDeckChanged(boot, deckId)`, exported for the store-level suite; boot-unsettled detection is a `sequenceSettled` flag set inside the shared settle guard.)
- [x] `ui/src/state/connection.ts` -- kind branch wiring + rewrite the overturned doctrine header. (The total `deck_id` fold — absent payload/key, null, non-string, blank → null — lives here, beside the branch.)
- [x] `ui/src/App.tsx` + `ui/src/state/formatCheck.ts` -- re-key the format-check effect on detail identity; update the formatCheck header ruling text.
- [x] `ui/src/state/deck.test.ts` -- unit coverage with injected readers: burst/abort/generation (matrix rows Burst, Out-of-order), refusal mapping rows, mid-boot fold. (10 new tests, including the boot-level refetch-before-settle gate and the mid-boot supersession race won by the folded re-drive.)
- [x] `ui/src/App.test.tsx` -- app-level coverage: matching single-request refetch (zero `/api/active-deck`), deck-agnostic null/absent/blank payload (plus the payload-less frame `agentEventOf` admits), different-deck no-op + stopped-poll restart, derived-state recompute + format-check re-ask after refetch, 404-clear preserved, non-404 keeps deck on screen, none-state re-drive preserved; amended the two intentionally-changed pinned counts; every request-log assertion carries a why-message naming its AC. (Note: the c4-10 recovery-redrive `formatCheckCalls` pin stays 1 on its own fixture — the mount's boot settles `refused`, so only one detail ever settles there; the comment was re-argued in place. Two c6-6 layering tests that reached "panel behind an open view" via a 503 `deck_changed` teardown were amended to the 404-clear, the one teardown c7-3 preserves.)
- [x] `ui/src/state/socket.test.ts` -- update the dispatch block for the widened signature. (The system arm now asserts envelope identity + payload delivery, mirroring the suggestions arm.)
- [x] Firing proofs -- stage the tree; plant (a) the id-mismatch guard removed (every `deck_changed` refetches the active deck), (b) the stale-generation guard removed from the refetch settle (out-of-order response wins); one harness run per plant with `--expect-red`; revert via `git diff --exit-code`; `--expect-green`; paste proof lines here.
  - Finished-tree control: `vitest: 75 files / 2143 tests, 0 failed, exit 0` → `--expect-total 2143`.
  - Plant (a) `driveDeckChanged`'s mismatch guard deleted: `vitest: 75 files / 2143 tests, 2 failed, exit 1` — `RED |dom| src/App.test.tsx > the glass refetches on deck_changed, coalesced and latest-wins (c7-3) > does not touch the active deck for a different deck's event, but still restarts a stopped poll (AC 2)`; `RED |dom| src/state/deck.test.ts > the deck_changed refetch is one request, coalesced, latest-wins (c7-3) > does NOTHING on a different deck's event — not even the refetch`. Reverted; `git diff --exit-code` clean.
  - Plant (b) `refetchRun`'s stale-generation guard removed (ungated settle + post-await check deleted): `vitest: 75 files / 2143 tests, 2 failed, exit 1` — `RED |dom| src/state/deck.test.ts > … > coalesces a burst by supersession: each newer event aborts the prior request`; `RED |dom| src/state/deck.test.ts > … > discards an out-of-order response: the OLDER one resolving later cannot win`. Reverted; `git diff --exit-code` clean.
  - Final: `uv run python -m scripts.vitest_probe_harness --expect-total 2143 --expect-green` → `vitest: 75 files / 2143 tests, 0 failed, exit 0`.
- [x] Artifacts -- `cd ui && npm run build`; commit `src/companion/app/static/` + rebuilt `plugin/` (`uv run python -m scripts.build_plugin`).

**Acceptance Criteria:**
- Given a settled deck and a matching or deck-agnostic `deck_changed`, when it is handled, then exactly one `GET /api/deck/{id}` fires (no `GET /api/active-deck`) and grid, deck list, type-group counts, curve, colours, hydration sweep, and format check all recompute from the new decklist.
- Given a `deck_changed` for a different deck id, when handled on a settled deck, then the active deck is not refetched and the stopped-poll restart path still runs.
- Given a burst of matching events, when they overlap an in-flight refetch, then each newer event aborts and restarts it — at most one in flight, last response wins, out-of-order responses discarded, exactly one settle.
- Given a refetch refusal, when it is `deck_not_found` the glass clears to no-active-deck; when it is anything else the loaded deck stays on screen unchanged.
- Given a `deck_changed` during an unsettled boot/re-drive or in a `'none'`/`'refused'` state, when handled, then the full two-request re-drive runs (server-refereed final state).
- Given the guard suites (store-writes, shell, posture, wire-contract, event-union) and the WS reconnect tests, when the suite runs, then all pass with no allow-list or semantics changes.

## Spec Change Log

## Review Triage Log

## Design Notes

- **Why the mismatch check reads `detail.id` and nothing else:** there is no `activeDeckId` field in any store — the settled `detail.id` is the only client-side truth, and inventing stored id state would add a second source to drift. During any window where that truth is unsettled (boot/re-drive in flight, `'none'`, `'refused'`), the design refuses to adjudicate ids and re-drives the full boot — the server is the referee, the same principle as c6-3 ruling #1. This kills the supersession race where a single-deck refetch of the displayed (departing) deck could beat an in-flight re-drive to a newly-activated deck and strand the glass on the old one.
- **Why failure keeps the deck (new policy, deliberately different from the boot):** the boot maps `unreachable` to `{status:'none'}` — correct at cold open, but on a refetch it would tear a loaded deck down to a panel on a transient blip, which UX-DR35 forbids ("never a blank or a skeleton teardown of a populated view") and 7.4 builds on. Only the legislated 404-clear settles; every other refetch outcome is dropped (staleness accepted, per the epic's degradation doctrine; recovery paths: next event, reconnect re-drive, poll edge).
- **Coalescing is supersession, not a timer:** UX-DR35's "a newer event cancels and restarts" is implemented as abort + generation-bump — no debounce window exists to tune, `deck.ts`'s timer ban stays intact, and c7-5's "the coalescing machinery is the debounce" holds because a burst yields exactly one completed settle. The ledgered timer-coalescing idea (deferred-work:5798) stays where it is (c10-3, `connection.ts`, only if a real push rate demands it).
- **Format-check re-key is an intentional overturn of c4-10's Q7 ruling**, ledgered to this story (deferred-work:4772, named in `formatCheck.ts`'s own header). The old pin ("one request per deck id per mount") was request-thrift before any staleness signal existed; detail identity is now exactly the staleness signal. The amended pin stays a count: one format-check request per settled detail. Side effect: reconnect/duplicate re-drives re-ask the 5 ms route once each — honest under "something changed, refetch".
- The deferred format-check items NOT pulled in: the pass→violation announcement (c7-5, deferred-work:4782) and the hidden-vs-failed panel signal (c8-6, deferred-work:4765/5049).
- Known full-suite flake (Python side, pre-existing): `test_deck_repository.py::test_update_deck_strategy` / `::test_list_decks_with_strategy_field` — not this story's regression. Frontend cold-run eslint timeout: run the harness control warm.
- Branch process: story branch `feat/companion-c7-3-coalesced-refetch` off umbrella `feat/companion-c7`; PR targets the umbrella (Greptile per story). Umbrella is currently ahead of origin by the epic-context docs commit — push together at PR time.

## Verification

**Commands:**
- `cd ui && npm run lint && npm run format:check && npm test` -- RUN 2026-08-14: lint clean (eslint + stylelint), prettier clean, `tsc -b` clean, `75 files / 2143 tests, 0 failed` (2123 baseline + 20 new). Guard suites (store-writes, shell, posture, wire-contract, event-union) pass unchanged — no allow-list or semantics edits anywhere in `ui/tests/`.
- `uv run python -m scripts.vitest_probe_harness --control` then per-plant `--expect-total N --expect-red '<substring>'`, revert, `--expect-green` -- RUN 2026-08-14: proof lines pasted above (both plants caught, both reverts proven clean, final green).
- `cd ui && npm run build && git status --porcelain -- src/companion/app/static/ plugin/` -- RUN 2026-08-14: bundle rebuilt (`assets/index-DJR4YfUb.js`), `plugin/` re-assembled via `scripts.build_plugin` (v0.4.0), both staged for the story commit.
- `uv run pytest -m "not integration"` -- RUN 2026-08-14: `1 failed, 3019 passed, 1 skipped, 55 deselected` — the one failure is `tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field`, the pre-existing flake pair member this spec's Design Notes record as not this story's regression. No backend file was touched by this story.
