---
title: 'Deck and connection recovery never leave silent stale state'
type: 'bugfix'
ticket: '7'
created: '2026-11-13'
status: done
baseline_revision: '9531ea2f3e2c865aa12a0e9263bd1488f8be7f66'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Four recovery paths in the companion leave the glass stale or blank with no marker. A backend that accepts the socket upgrade and then drops it reconnects every 2 s forever (about six requests a cycle) and the Disconnected panel never shows, because `succeed()` resets the backoff on every open (`M40`). A `deck_changed` frame during an unsettled boot restarts it and discards the in-flight response (`M38`). A refetch's transient refusal is dropped with no later edge, so the agent's edit never reaches the glass (`F2-D1`, path 1). Every agent edit blanks the format-check panel for one round trip, because the effect's cleanup resets the slice (`M39`). Three guards have no test that fails when they are removed (`F2-P3`, `F1-P4`).

**Approach:** Pin the three untested guards first, in their own commit, green on the baseline. Then: the socket resets its failure count, elapsed clock and backoff only when a socket that opened has stayed open a minimum time; a `deck_changed` while the boot is unsettled defers through the existing `redriveOnSettle` flag; a refetch's transient refusal (a `RETRIES_QUIETLY` refusal or an `unreachable`) is routed through the existing CAP-3 one-probe path, and the probe's healthy answer refetches; the format-check slice keeps its report through a reload of the same deck id and clears on an id change, an empty deck or the deck leaving.

**Decisions (from the intent, run straight through):** `F2-D1` is option (a), with no new timer (AD-12). Its path 2 (re-arming the probe once per re-drive under a hard cap) is not built: the ticket's description scopes option (a) to routing the refetch refusal, and the one-probe-per-healthy-episode bound stays as stated (raised for Brad in the report). Emitting `'live'` on every open stays as it is (`F1-P1`'s own fix line). A malformed row on a refetch is not transient and earns no probe.

## Boundaries & Constraints

**Always:** AD-12 (no new deck-recovery timer; the WebSocket is a trigger, REST is the writer). Fake timers and the existing seams (`createAgentSocket`'s `mint`/`open`, `createPoller`'s `read`, `createDeckBoot`'s readers, `App.test.tsx`'s `answering`/`FakeSocket`); no source scanning. A pin of today's behaviour passes on the baseline; a test pinning a bug fails on it. Every new guard proved through `scripts.vitest_probe_harness` (control first, warm), the tree staged before each plant and each revert checked with `git diff --exit-code <file>`. Rebuild `src/companion/app/static/` with `npm run build` and `plugin/` with `scripts.build_plugin`.

**Never:** No change to the socket's constants, its `delay → mint → open` ordering or its two-gate escalation. No pill-announcement change (F7). No render-count work (M11, story 9.6). No re-arm-per-re-drive probe counter. No backend route or model change. No hand-edit of `static/` or `plugin/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Accept-then-drop | every upgrade opens and closes at once | mints at 0, 2, 6, 14, 30, 60 s; `'down'` at 60 s; Disconnected panel shows | keeps retrying at the ceiling |
| Stable socket drops | open for ≥ the minimum, then close | next attempt at `SOCKET_BASE_MS`; clocks reset | none |
| Throwing `onStatus` | consumer throws on a status | a second mint at `SOCKET_BASE_MS` | loop survives |
| `deck_changed` mid-boot | boot unsettled | in-flight response paints, then exactly one full re-drive | none |
| Refetch refused transiently | settled deck, refetch `database_unavailable` or `unreachable`, poll healthy | one poll probe; its healthy answer refetches; deck updates | one probe per healthy episode |
| Refetch refused, poll retrying | poll on a retrying panel | no probe; the poll's recovery edge refetches | none |
| Agent edit | same deck id, new `detail` | old format-check rows stay until the new report lands | refused new read draws nothing |
| Deck switch / empties / leaves | new id, empty boards, or no deck | panel cleared at once; no old report shown | none |

</frozen-after-approval>

## Code Map

- `ui/src/state/socket.ts:436-446` -- `succeed()` resets `failures`, `failingSince`, `delay` on open. Record the open time instead; in `fail()`, reset the three only when the socket that just closed had been open ≥ a new exported `SOCKET_STABLE_MS` (checked at close, so no timer and nothing for `stop()` to cancel). `reconnected = failures > 0` stays. `:417-434` `fail()`'s `finally` is the pinned guard.
- `ui/src/state/poller.ts:237-246` -- the escalation reset before the `unreachable` early return; pin only, no change.
- `ui/src/state/deck.ts:512-520` -- `driveDeckChanged`: `!boot.settled()` sets `redriveOnSettle = true` and returns; a settled non-`'deck'` still restarts. `:302-336` `refetchSequence`: after the generation guard, an `unreachable` or a non-404 refusal whose `deckPanelFor` panel `RETRIES_QUIETLY` retries calls a new optional `DeckBootOptions.onRefetchRefused()`; a malformed row does not. `:594-675` `useDeckState`: a `refetchOwed` flag set by that callback; the probe arm reused (same `probeSpent`/`pollPanel` gates); any settle clears `refetchOwed`; the listener, on a healthy poll write that is an edge or answers the armed probe, calls `driveDeckChanged(boot, null)` when the slice is `'deck'` and `refetchOwed`. `:613` is the `'none'` re-arm pinned by `F2-P3`. `resetDeckState` also clears `redriveOnSettle`. Module and `useDeckState` docstrings updated.
- `ui/src/state/formatCheck.ts:154-216` -- `loadFormatCheck` keeps a `'report'` on the glass (no `'loading'` write) when the last load was for the same id; `clearFormatCheck` forgets that id. Header "ONE READ PER SETTLED DETAIL" updated.
- `ui/src/App.tsx:85-111` -- split into a clear effect keyed on `[deckId, emptyDeck]` (clears on id change, empty, no deck, unmount) and a load effect keyed on `[detail, emptyDeck]` with no cleanup.
- Tests: `state/socket.test.ts` (`resets to the base after a successful connection` `:198` moves; throwing-constructor `:871` gets the throwing-`onStatus` sibling), `state/poller.test.ts:247` block, `state/deck.test.ts:713` (T1-4-P5 rewrite), `state/formatCheck.test.ts`, `App.test.tsx` (CAP-3 block `:1431-1823` with its `scripted` helper; the CAP-2 in-flight tests `:3177-3275`; `refetch never tears down` `:4155` with `withholdDeckRead`, whose 503-drop test `:4262` moves; the pill walk `:3431`; comments `:651` and `:3641`).

## Tasks & Acceptance

**Execution:**
- [x] Pins (commit 1, green on baseline): `App.test.tsx` refusal → `'none'` → refusal re-probes (`F2-P3`); `socket.test.ts` throwing `onStatus` still mints again at `SOCKET_BASE_MS`; `poller.test.ts` `UNAVAILABLE ×4, UNREACHABLE, UNAVAILABLE…` no stall at 62 s, stall at 92 s (`F1-P4`).
- [x] `ui/src/state/socket.ts` -- minimum open time; tests: open-then-close loop reaches `'down'` with the backoff schedule; a stable socket's drop retries at the base (the moved pin); App-level accept-then-drop shows the Disconnected panel.
- [x] `ui/src/state/deck.ts` -- defer, refetch refusal probe, docstrings; tests: `deck.test.ts:713` rewritten (no restart, in-flight paints); App: a `deck_changed` during boot paints the in-flight response then one re-drive; a refetch refusal then a healthy probe refetches; a refusal while the poll retries is refetched by its edge; a forever-refusing refetch costs one probe; the 503-drop marker test moved.
- [x] `ui/src/state/formatCheck.ts`, `ui/src/App.tsx` -- keep-on-same-id; tests (format-check route withheld): rows kept through an agent edit and through the CAP-2 reconcile; a switch shows no old report; an emptying refetch removes the panel; `formatCheck.test.ts` unit rows; the two stale comments.
- [x] Ripple: UI gate, `npm run build` (commit `static/`), `scripts.build_plugin` (commit `plugin/`), `gen:types` drift check; grep `docs/companion.md` and `.claude/skills/companion/` for reconnect/stale/Disconnected claims; Python gate.
- [x] Probe proofs (Design Notes) recorded in Implementation Notes.

**Acceptance Criteria:**
- Given the pins commit checked out over the baseline `src`, when `npm test` runs, then every pin passes.
- Given the finished branch, when the UI gate and the Python gate run, then all are green and `npm run build`, `scripts.build_plugin` and `gen:types` leave no drift.
- Given each plant, when the harness runs with `--expect-red`, then it exits 0 naming the planted test, and `git diff --exit-code` on the planted file is clean afterwards.

## Implementation Notes

Implemented in the planning session rather than through a fresh implementation subagent: the investigation was already in context, and a fresh agent would have had to re-read about 10k lines of test harness to reach the same place. The plan stayed the source of truth.

Commits on `fix/quality-9-7-recovery-no-silent-stale-state` over baseline `9531ea2`: `9b333ed` (the three pins, each run green on the baseline `src`; the `'none'` pin was also checked red against a hand-planted removal before committing), then the fix commit (code, tests, `ui/README.md`, `static/`, `plugin/`, this plan).

What was built:
- `socket.ts`: `SOCKET_STABLE_MS = 5_000`. `succeed()` records `openedAt` and resets nothing. `fail()` resets `failures`, `failingSince` and `delay` only when the socket that just closed had been open at least that long, then counts the failure. `start()` clears `openedAt`. `reconnected = failures > 0` is unchanged, so every reopen in an accept-then-drop run fires `onReconnected`. The `DISCONNECTED_AFTER_MS` docstring says a short open does not break the run.
- `deck.ts`: `driveDeckChanged` defers (`redriveOnSettle = true`) whenever `!boot.settled()`, before reading the slice. `DeckBootOptions.onRefetchRefused` (optional) is called after the generation guard for an `unreachable` refetch and for a non-404 refusal whose `deckPanelFor` panel `RETRIES_QUIETLY` retries; never for a malformed row, the 404-clear, or a superseded or stopped run. In `useDeckState`, `probeOnce()` holds the old CAP-3 gates (`probeSpent`, the poll still retrying). `onUpdate` clears `refetchOwed` on every settle. `onRefetchRefused` sets `refetchOwed` and calls `probeOnce()`. On a healthy poll write that is an edge or answers the armed probe, the listener's `'deck'` arm pays an owed refetch with `driveDeckChanged(boot, null)`, but only if the boot is settled (see triage #2). `resetDeckState` clears `redriveOnSettle`. The module header, the `driveDeckChanged`, `redriveOnSettle` and `useDeckState` docstrings, and `connection.ts`'s header all say what is now true.
- `formatCheck.ts`: `loadedFor` records the id of the last load and is cleared by `clearFormatCheck`. `loadFormatCheck` skips the `'loading'` write when it is re-asking about the same id and the slice holds a `'report'`. The generation guard is unchanged.
- `App.tsx`: two effects. The clear is keyed on `[deckId, emptyDeck]` and declared first, so on a deck switch its cleanup runs before the new load. The load is keyed on `[detail, emptyDeck]` and has no cleanup.
- `ui/README.md`: the socket bullet and the boot-recovery paragraph. `docs/companion.md` and `.claude/skills/companion/SKILL.md` make no reconnect, stale or Disconnected claim that this changes (grepped).
- Not built: F2-D1 path 2, the re-arm of the probe once per re-drive under a hard cap (Intent, Decisions). The one-probe-per-healthy-episode bound is stated in `useDeckState`'s docstring.

What moved. Each moved test is marked `MOVED in 9.7`, and `git diff 9b333ed -- ui/src` is the record.
- `socket.test.ts` "resets to the base after a successful connection": the socket is now held open `SOCKET_STABLE_MS` before the drop, so the next mint lands at 21 s instead of 16 s.
- `deck.test.ts` "folds a mid-boot event into a fresh FULL re-drive": became "defers a mid-boot event behind the re-drive in flight". There is no third active-deck read, and the in-flight re-drive's answer paints.
- Four App tests pinned "a 503 refetch is read once and dropped": the non-404 refusal test, the 503 behind an open view, the announcer's 503 row, and the marker's 503 drop. The first three now count two deck reads (the refusal, then one re-ask after the probe), bounded over ten idle minutes. The marker drop is now pinned with a 500, which `RETRIES_QUIETLY` says does not retry.
- `deck.test.ts`'s dropped-outcome table gained a `reported` column, and a new row (`database_not_initialized`).

New tests:
- socket: open-then-close reaches `'down'` on 0/2/6/14/30/60 s, then the ceiling; reconnect fires on each reopen; the 4.999 s and 5 s boundaries.
- deck.test: the cold-boot defer row, and nothing is reported for a superseded, stopped or 404 refetch.
- formatCheck.test: five same-id rows.
- App, socket: the accept-then-drop backend reaches the Disconnected panel after six sockets.
- App, mid-boot frames: two `deck_changed` frames mid-boot paint the in-flight read, then one boot; a frame owes the follow-up alone when the socket was already live.
- App, refetch: a refused refetch refetches after the healthy probe; the poll-retrying ordering refetches on the edge; an in-flight boot pays the owed refetch.
- App, format check (four tests, with the format-check route withheld): kept through an agent edit; kept through the CAP-2 reconcile; no old report after a switch; an emptying refetch removes the panel.
- App test comments corrected: "keyed on the deck id" at the no-request test, and `[deckId, emptyDeck]` at `detailReadsOf`.

Probe proofs. The tree was staged before every plant. A driver applied each plant alone, ran `uv run python -m scripts.vitest_probe_harness --expect-total N --expect-red '<substring>'`, restored the original bytes, then ran `git diff --exit-code <file>`. Controls, run warm: `vitest: 59 files / 1849 tests, 0 failed, exit 0` (plants 1-8) and `vitest: 59 files / 1850 tests, 0 failed, exit 0` (plant 9, after the review patch's test).

| # | Plant (file) | Proof line | RED | harness exit | `git diff --exit-code` |
|---|---|---|---|---|---|
| 1 | `'none'` re-arm dropped (`deck.ts`) | `vitest: 59 files / 1849 tests, 1 failed, exit 1` | `re-arms the probe on a NONE settle too` | 0 | 0 |
| 2 | `fail()` without `finally` (`socket.ts`) | `vitest: 59 files / 1849 tests, 1 failed, exit 1` | `keeps retrying when the STATUS consumer throws` | 0 | 0 |
| 3 | `unreachable` early return above the guard (`poller.ts`) | `vitest: 59 files / 1849 tests, 1 failed, exit 1` | `resets on a network rejection too` | 0 | 0 |
| 4 | `succeed()` resets the run again (`socket.ts`) | `vitest: 59 files / 1849 tests, 3 failed, exit 1` | `backs off on the normal schedule and reaches down…`, the 5 s boundary test, App `shows the DISCONNECTED panel against a backend that accepts every upgrade and drops it` | 0 | 0 |
| 5 | `driveDeckChanged` restarts while unsettled (`deck.ts`) | `vitest: 59 files / 1849 tests, 4 failed, exit 1` | App `paints the in-flight boot when a deck_changed lands mid-boot…`, App `owes the deferred re-drive to the FRAME alone…`, both `deck.test.ts` defer rows | 0 | 0 |
| 5b | `driveDeckChanged` drops the frame while unsettled (`deck.ts`) | `vitest: 59 files / 1849 tests, 1 failed, exit 1` | App `owes the deferred re-drive to the FRAME alone…` | 0 | 0 |
| 6 | `onRefetchRefused` not wired (`deck.ts`) | `vitest: 59 files / 1849 tests, 5 failed, exit 1` | `refetches after a refusal once the healthy probe answers…`, `refetches through the poll's own recovery edge…`, the three moved 503 rows | 0 | 0 |
| 6b | owed refetch never paid (`deck.ts`) | `vitest: 59 files / 1849 tests, 5 failed, exit 1` | same five as 6 | 0 | 0 |
| 6c | every non-404 refusal reported (`deck.ts`) | `vitest: 59 files / 1849 tests, 3 failed, exit 1` | `DROPS a 500 internal_error…`, `DROPS a 400 invalid_request…`, App marker 500 drop | 0 | 0 |
| 7 | `loadFormatCheck` writes `'loading'` always (`formatCheck.ts`) | `vitest: 59 files / 1849 tests, 3 failed, exit 1` | App `keeps the rows on the glass through an agent edit…`, App `keeps the rows through the CAP-2 reconcile…`, unit `keeps the old report while the same id is re-asked…` | 0 | 0 |
| 7b | the load effect clears in its cleanup again (`App.tsx`) | `vitest: 59 files / 1849 tests, 2 failed, exit 1` | the two App keep-rows tests | 0 | 0 |
| 8 | the keep ignores the id (`formatCheck.ts`) | `vitest: 59 files / 1849 tests, 1 failed, exit 1` | `goes loading at once for a DIFFERENT id…` | 0 | 0 |
| 9 | the owed refetch defers behind an in-flight boot (`deck.ts`, review patch) | `vitest: 59 files / 1850 tests, 1 failed, exit 1` | `lets a boot already in flight pay the owed refetch — no second boot behind it` | 0 | 0 |

Plant 7 lacks an App-level red for a deck switch: the clear effect also guards that case, which is why plant 8 is proved by the unit row. No Python guard was involved, so the Python harness did not run.

Gates on the finished tree:
- UI, from `ui/`:
  - `npm run lint` is clean.
  - `npm run format:check` is clean.
  - `npm run typecheck` is clean.
  - `npm test` gives 1850 passed in 59 files.
  - `npm run test:gates` gives 39 passed.
  - `npm run build` rebuilt `src/companion/app/static/` with a new `index-*.js` and `index.html`.
  - `npm run gen:types` left `types.d.ts` unchanged.
  - No `gen:api`: no backend route or model changed.
- `uv run python -m scripts.build_plugin` mirrored the bundle into `plugin/`. The four manifest files change only in line endings, and staging normalises them away.
- Python:
  - `ruff check .` is clean.
  - `ruff format --check .` is clean.
  - `mypy src/` is clean, and so is `mypy src/ --platform win32` (97 files).
  - `uv run pytest` gives 3698 passed, 2 skipped.

What a companion user will see:
- **Reconnect timing.** A backend that accepts the WebSocket upgrade and drops it at once used to be retried every 2 s forever. It is now retried at 2, 4, 8, 16 and 30 s, and the Disconnected panel shows after 60 s. Behind the panel each reopen still briefly says "live", so once every 30 s the pill and panel flicker for the length of the doomed open. The finding's own fix line keeps `'live'` on open.
- **Reconnects after short sessions.** A socket that drops within 5 s of opening no longer resets the backoff, so back-to-back restarts less than 5 s apart retry at 4 s, then 8 s, not 2 s.
- **Stale decks after an edit.** A `deck_changed` refetch refused `database_unavailable` (or `unreachable`) is asked for again once the poll says the backend is healthy. The agent's edit reaches the glass, and the header's "Updating…" marker shows again during the re-ask. If the deck route keeps refusing beside a healthy poll, it stays stale after one extra read, as before.
- **Agent edits during a cold open.** Edits made while the deck is still loading no longer restart the load: the first answer paints, then one reload follows.
- **The format-check panel.** It no longer disappears for a round trip on each agent edit or on the first connect. It still clears at once on a deck switch, an emptied deck, or any state panel.

## Plan Change Log

## Review Triage Log

Pass 1 (lens `quick`, 2026-11-13): 6 findings. High 0, medium 0, low 5, false 0, maybe-false 0, plus 1 rejected as a plan edit. Five went to **patch**, one was rejected, none were deferred, and there was no loopback. The lens read the diff without `static/`, `plugin/` or the plan file.

| # | Finding | Verdict | Route | Evidence / action |
|---|---------|---------|-------|-------------------|
| 1 | The probe proofs and Implementation Notes were not yet recorded, and the tasks were unticked | — | rejected | The fix is an edit to this build's plan, which triage rejects. They are recorded above as the workflow's next step. |
| 2 | An owed refetch paid while a boot is in flight defers a SECOND full boot (`driveDeckChanged` → `redriveOnSettle`), although the in-flight settle already clears the debt | low | patch | Verified: the scenario is a refusal while the poll retries, then a reconnect or `active_deck_changed` re-drive mid-flight as the poll heals. The extra boot costs two requests. The `'deck'` arm now returns when `!boot.settled()`, leaving `refetchOwed` for that settle to clear. New test `lets a boot already in flight pay the owed refetch`; plant 9 proves it. |
| 3 | `connection.ts:80-83` still said mid-boot "falls back to that same full re-drive" | low | patch | Verified as stale after M38. It now says mid-boot defers behind the boot in flight. |
| 4 | `DISCONNECTED_AFTER_MS`'s "down CONTINUOUSLY" no longer matches a run that includes short opens | low | patch | Verified. The docstring now says an open that drops within `SOCKET_STABLE_MS` does not break the run. |
| 5 | `useDeckState`'s rule paragraph said flatly that a `'deck'` is never re-driven on the poll edge | low | patch | Verified. Qualified with the owed-refetch exception. |
| 6 | Line wraps in the `deck.ts` module header and two edited `App.test.tsx` comments | low | patch | Verified (Prettier does not re-wrap comments). Re-wrapped. |

After the patches:
- UI gate: green, with 1850 tests.
- Bundle and `plugin/`: rebuilt.
- Probe harness: control 1850, plant 9 red.
- Python gate: green, 3698 passed, 2 skipped.

## Design Notes

**Why check stability at close, not with a timer.** The reset only matters at the next failure, so reading `Date.now() - openedAt` there is equivalent and needs no timer for `stop()` to cancel. Wall time is right here: a socket open across a laptop sleep was a healthy connection.

**Why a refetch refusal reuses the probe rather than its own path.** The probe already bounds cost to one poll read per healthy episode, and the poll's own backoff is the retry when the backend really is down, so no new timer appears. A `'deck'` slice still never re-drives on a poll edge unless a refetch is owed, which keeps "boots exactly once".

**Plants** (one guard broken each, reverted): (1) drop `|| state.status === 'none'` (`F2-P3` pin); (2) `fail()` without `finally` (throwing-`onStatus` pin); (3) the `unreachable` early return moved above the escalation guard (poller pin); (4) `succeed()` resets the clocks again (open-then-close tests); (5) `driveDeckChanged` restarts while unsettled (mid-boot frame test); (6) the refetch refusal callback not called (probe-refetch test); (7) `loadFormatCheck` writes `'loading'` unconditionally (keep-rows tests); (8) the keep ignores the id (switch test).

## Verification

**Commands:**
- from `ui/`: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test`, `npm run test:gates`, `npm run build`, `npm run gen:types` -- green, `git status` clean after build and gen:types
- `uv run python -m scripts.build_plugin` -- committed, no drift
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, `uv run pytest` -- green
- `uv run python -m scripts.vitest_probe_harness --control`, then `--expect-total N --expect-red '<substring>'` per plant
