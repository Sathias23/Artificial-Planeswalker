---
baseline_commit: 3027109233fbc28c40faef8fc9aa59705aab6e02
---

# Story c5-6: Client reconnection with backoff and a fresh ticket per attempt

Status: done

## Story

As Brad who restarted the backend mid-session,
I want the page to reconnect on its own,
So that a restart is a blip rather than something I have to notice and fix.

## The story in one paragraph

This is the FIRST client-side WebSocket code in the repository — `ui/src` contains zero
`new WebSocket` today (verified at c5-3, c5-4 and again at context time). The backend half of the
channel is complete and merged (c5-2 tickets, c5-3 upgrade, c5-4 broadcast, c5-5 ingest;
`test_ws.py:130` even names this story's loop shape: *"mint, upgrade, mint, upgrade"*). c5-6
builds the browser's whole connect/reconnect loop — first connect on mount, exponential backoff
on drop, a **fresh** single-use ticket per attempt, refetch-on-reconnect, the `disconnected`
panel when retries exhaust — and, because it builds the loop, it also owns **every client event
handler** and the **family of stale-panel defects** the ledger has been accumulating against it
since c3-9 (C3 retro ruling R3: *"c5-6 resolves the family; it should not solve one third of it
and leave the rest"*). The connection pill is **c5-7's**; the real-socket integration test is
**c5-8's**; the four agent-push views are **Epic 6's**.

## Acceptance Criteria

**The loop (epic Story 5.6, verbatim intent — `epics-companion-app.md:2545-2576`)**

1. On App mount, exactly one socket per tab is opened: mint a ticket via `GET /api/session`,
   then open `ws://{window.location.host}/ws?ticket={encodeURIComponent(ticket)}`. The URL is
   built purely relative to `window.location` — the port is never hardcoded and the host
   spelling never switches between page and socket (the backend's `Origin` check is an exact
   match; `security.py:148-175`).
2. When the socket drops (close or error, any code), the client retries with exponential
   backoff (NFR-04): constants mirroring `poller.ts`'s shape (base 2 s, ×2, 30 s ceiling —
   final values per Q2 ruling), each constant carrying its arithmetic in its docstring, growth
   committed after scheduling exactly as `poller.ts:200-204` does.
3. **Every** reconnect attempt mints a fresh ticket from `GET /api/session` first. A ticket is
   never cached, never shared, never reused — including after an upgrade that failed for an
   unrelated reason (AD-5; the `SessionTicket` docstring at `types.d.ts:747-761` states exactly
   this). The backoff delay applies to the whole attempt (mint + upgrade), so a mint-then-wait
   sequence cannot burn the 30 s TTL.
4. The loop carries a generation counter re-checked **after every await** — the mint, the open,
   and each socket event — bumped by both `start()` and `stop()` (the `poller.ts:160-168`
   pattern; `deck.ts:286-302` documents the multi-await extension this loop needs).
5. On reconnect success the client refetches the active deck (NFR-04): `GET /api/active-deck`
   then the deck read, by re-driving the existing `createDeckBoot` (`stop()` then `start()`)
   through a subscription seam — `deck.ts` itself gains no timer, no socket, and never names
   another store (the `subscribeSystemState` precedent; `store-writes.test.ts:185-203` pins).
6. If the backend restarted, the active deck died with it (`ActiveDeckSlot` is in-memory), so
   the refetch answers `{"deck_id": null}` and the app lands on the no-active-deck state
   (FR-07) — no error, no stale deck.
7. While reconnection is in progress, a loaded deck **stays rendered**, possibly stale — the
   view is never torn down to a skeleton (UX-DR35). Pin behaviour across a same-deck refetch
   follows c4-5's accepted cost (a rewritten `boards` reference releases the pin — accepted at
   the c4-5 review; do not re-litigate, declare).
8. When retries are exhausted (definition per Q2 ruling), the `disconnected` StatePanel takes
   the left column with its existing verbatim copy (UX-DR30, UX-DR33 — the copy already ships
   in `STATE_COPY.disconnected`; this story writes NO new user-facing prose). Per
   `RETRIES_QUIETLY.disconnected = true`, the backoff keeps retrying quietly behind the panel —
   the panel is an announcement, not a stop.
9. A reconnect that later succeeds clears the `disconnected` state and re-drives the refetch —
   the page comes back **without a reload**. This is the family's whole point (AC 13).
10. Freshness recovery is "something changed, refetch" — no diffs, no patches, no payload
    reading on the deck path (NFR-04).

**The event handlers (this story builds the browser's only message dispatch)**

11. Incoming frames are parsed and dispatched through **one total switch** over the six-kind
    closed enum (AD-6): `active_deck_changed` → switch-then-refetch (never a refetch of the
    deck being left — the reason the kind exists); `deck_changed` → refetch the active deck;
    the four agent-push kinds (`suggestions | swaps | tier_list | groups`) are received and
    deliberately dropped with a recorded home (Epic 6) — not an error, not a crash.
12. A duplicate `active_deck_changed` (the backend fires on **every** `PUT`, including a no-op
    re-set — `ws.py:409-444`) costs one idempotent refetch, nothing else.
13. A malformed frame — non-JSON, unknown `kind`, wrong shape — is ignored without closing the
    socket and without an unhandled exception. Runtime narrowing follows the `client.ts`
    narrower idiom; no wire shape is re-declared outside `src/api/` (`wire-contract.test.ts`
    bans all six `*Event` schema names there).

**The family (the ledgered defects this story exists to resolve)**

14. First load with no backend reachable eventually shows `disconnected` — the true panel —
    instead of holding "No deck on the glass" with its actionable-and-wrong copy forever
    (dw:3451, confirmed live at Block I and judged *worse than recorded*, dw:4930-4940).
15. A stale system panel is re-driven by the socket: on reconnect success AND on a system-kind
    event arriving, the system poll and deck boot are re-driven per Q5's ruling, so
    `database-updating-stalled` after a successful rebuild (dw:3472/3544) and no-active-deck
    after a late DB death (dw:3463) both recover without a manual refresh.
16. Card-cache recovery per Q6's ruling — the terminal-after-three asymmetry (dw:3652) and the
    orphaned-hydration declaration (dw:3666) are both dispositioned in this story's ledger
    pass, whichever way Q6 rules.
17. `CLIENT_ONLY_STATES` is either consumed at runtime or re-declared type-level with the
    reason written down — this story is named as "the story that says which" (dw:3500).

**The dev loop**

18. `ui/config/devProxy.ts` gains an anchored `/ws` entry with WebSocket proxying enabled;
    `tests/devProxy.test.ts:146` ("does not yet proxy /ws") is updated; the dev-time `Origin`
    mismatch (dw:5221, Medium — `changeOrigin` rewrites `Host` but not `Origin`, so a proxied
    handshake would 403 with no message) is resolved per Q7's ruling and proven by a round-trip
    or equivalent test, not by prose.

**Discipline**

19. Task 0 greps the story's own key (`grep -rn "c5-6" src/ ui/ tests/ scripts/`) and every hit
    is enumerated with a disposition; every prose prediction naming c5-6 is fulfilled-and-
    rewritten or recorded as falsified, in the same commit (C4 action item; c5-5's worked
    example).
20. Every new guard and every timing-sensitive test ships an R2 firing proof: a planted
    violation shown RED through the **full** `npm test` (never a standalone file run) plus one
    line stating what the assertion actually compares. New files are `git add`ed before any
    scan-based guard is trusted green (all five meta-suites read `git ls-files`).
21. Existing App-level arms that drive `disconnected` via `useSystemStore.setState`
    (`App.test.tsx:1272-1278`) are converted to drive it through the real trigger this story
    creates; `copy-tails.test.ts:223-235`'s deliberately-weak disconnected arm is strengthened
    against the shipped mechanism.
22. No new dependencies: no `reconnecting-websocket`, no `socket.io-client`, no second store or
    fetching library (`package-contract.test.ts`); the lockfile is untouched.
23. Suites green and strictly larger on the frontend: Python 2,770 / 1 skipped
    (`-m "not integration"`) unchanged unless backend prose is reconciled (prose-only edits
    allowed, behaviour byte-identical); frontend from 1,706. mypy --strict, ruff, eslint,
    stylelint, `tsc -b`, prettier, pre-commit clean; plugin mirror rebuilt and sha256-verified
    after the last edit if any `src/` or bundle byte changed; `npm run gen:api` verified a
    no-op (this story adds no wire schema).

## Tasks / Subtasks

- [x] **Task 0 — baseline and reconnaissance** (AC: 19, 23): branch
  `feat/companion-c5-6-client-reconnection` off `feat/companion-c5` at `3027109`. Verify:
  Python 2,770 passed / 1 skipped (`uv run pytest -m "not integration"`), frontend 1,706 / 66
  files (`npm test`), `npm run gen:api` a clean no-op. Grep own key; list every hit with its
  disposition. Read the ledger anchors named in Dev Notes. Read `poller.ts` and `deck.ts`
  end-to-end before writing any code.
- [x] **Task 1 — the session reader and the socket door** (AC: 1, 3): `SESSION_PATH` +
  `readSessionTicket` (total outcome union, shared `request()`, `ticketOf` narrower) in
  `src/api/client.ts`; `SessionTicket` alias (and an `AgentEvent` alias reached through
  `paths['/agent/events']['post']['requestBody']`) in `src/api/schema.ts`; socket construction
  homed per Q1's ruling so `posture.test.ts:341`'s door list stays honest.
- [x] **Task 2 — the loop** (AC: 2, 3, 4, 8, 11, 12, 13): new `src/state/socket.ts` —
  framework-free like `poller.ts` (injected `mint` + injected socket factory, no React, no
  store import); backoff constants with arithmetic docstrings; generation counter; fresh mint
  per attempt; exhaustion threshold per Q2; status emission per Q8; the one total kind-switch
  with graceful refusal of malformed frames.
- [x] **Task 3 — wiring** (AC: 5, 6, 7, 9, 15): connection status into the system slice (or the
  seam Q8 rules); the `disconnected` surface arm per Q3; deck-boot re-drive via a new
  subscription seam; the socket hook mounted once in `App.tsx` beside `useSystemState()` —
  **do not reorder the two existing effects** (`App.tsx:245-267` and `:341-359` carry measured
  queue positions and say so); poller re-drive per Q5.
- [x] **Task 4 — the family** (AC: 14, 15, 16, 17): first-load-unreachable → disconnected;
  event-driven re-drive of the stalled panel; card-cache recovery per Q6; consume or
  re-declare `CLIENT_ONLY_STATES`; write each disposition into `deferred-work.md` in the same
  commit.
- [x] **Task 5 — the dev proxy** (AC: 18): anchored `/ws` pattern with ws proxying; the Origin
  fix per Q7; update `devProxy.test.ts` and extend the round-trip coverage.
- [x] **Task 6 — tests and guards** (AC: 20, 21): `socket.test.ts` in the `poller.test.ts`
  idiom (fake timers, `vi.setSystemTime(0)`, absolute-timestamp schedule assertions, injected
  fake socket class, `settle()` for microtask chains); App-level conversion of the
  `disconnected` arm; `copy-tails` strengthening; R2 firing proofs for every new guard,
  through the full `npm test`, with files staged first; probe-harness question per Q9's
  ruling.
- [x] **Task 7 — reconcile, record, stop** (AC: 19, 22, 23): rewrite or falsify every c5-6
  prose prediction (backend prose edits are behaviour-free; plugin mirror rebuilt +
  sha256-verified if anything under `src/` or the bundle changed); ledger dispositions for
  every entry in the Dev Notes list; full suites + all gates; Dev Agent Record (including the
  Dev Notes KB self-check against C4's 41 KB average — R1's success criterion); **set status
  `review` and STOP** — Brad runs the three-layer review and raises the PR.

## Review Findings

Reviewed in chunks (diff exceeded the single-pass line threshold): **Group 1 — UI reconnection
core** (`ui/src/state/{connection,socket,deck,cards,systemState,poller}.ts` + tests) reviewed
2026-08-08 via Blind Hunter + Edge Case Hunter + Acceptance Auditor against this story. Groups 2
(backend Python) and 3 (UI shell/API/dev-proxy) are queued for follow-up runs.

### Group 1 — patch

- [x] [Review][Patch] `fail()`'s reconnect timer is skipped if `onStatus` throws, permanently
  halting the backoff loop [ui/src/state/socket.ts:362-374] — `emit(status)` ran before
  `schedule(next)` with nothing guaranteeing the latter still executes if the former throws (e.g.
  a future React render bug in `App`, which re-renders on every write since the system store is
  subscribed selector-less). **Fixed**: `schedule(next)` now runs in a `finally` around `emit()`.
  `socket.test.ts` (27/27) still green.

### Group 1 — defer

- [x] [Review][Defer] `useAgentConnection`'s socket does not reconcile the shared `connection`
  field on `stop()`/remount [ui/src/state/socket.ts:491-497] — deferred, pre-existing pattern:
  `App` is documented as the sole, permanently-mounted consumer of `useSystemState`,
  `useDeckState` and now `useAgentConnection` alike, and none of the three defends against a
  remount all three explicitly disclaim as unsupported.
- [x] [Review][Defer] Two independent triggers (`redriveDeckBoot()` fired directly on a system
  event, and the pre-existing `subscribeSystemState` edge-trigger in `useDeckState`) can both
  re-drive the same `DeckBoot` instance in quick succession around one event
  [ui/src/state/deck.ts:559-565] — deferred, low impact: idempotent and generation-guarded, costs
  at most one redundant fetch in a narrow timing window.
- [x] [Review][Defer] Whether `restartPollIfStopped`/`restartPoll` actually close dw:3472/3544
  and dw:3463 depends on backend behaviour outside this diff slice (does a DB rebuild or later DB
  death produce a `deck_changed`/`active_deck_changed` frame, or drop the socket?)
  [ui/src/state/systemState.ts:186-216] — deferred to the Group 2 (backend) review pass for
  confirmation.
- [x] [Review][Defer] `connection.ts` — the module wiring `restartPoll → resetCardAttempts →
  redriveDeckBoot` on reconnect and `redriveDeckBoot → restartPollIfStopped` on a system event —
  has no dedicated unit test in this slice, nor does `AgentSocketOptions.initialStatus`
  [ui/src/state/connection.ts] — deferred to the Group 2 review pass to confirm `App.test.tsx`
  actually pins this call order rather than merely observing an eventual refetch.

### Group 2 — backend (`src/companion/app/{spa,state,ws}.py` + tests), 2026-08-08

Light self-review (chose over the full 3-layer pass): every hunk is a comment/docstring update
("c5-6 will…" → "c5-6 has shipped…"), zero executable statements changed. `plugin/server/`
mirror confirmed byte-identical to `src/`, not reviewed separately. Cross-checked each prose claim
against the actual shipped code (no ticket field on the socket closure, one failure handler, 2s
first retry, the `test_ws.py` cross-reference to `socket.test.ts`'s exact test name) — all
accurate. **Clean — 0 findings.**

### Group 3 — UI shell/API/dev-proxy (`App.tsx`, `api/client.ts`, `api/schema.ts`,
`components/StatePanel/states.ts`, `config/devProxy.ts` + tests), 2026-08-08

Full 3-layer review (Blind Hunter + Edge Case Hunter + Acceptance Auditor). 0 `decision-needed`,
0 `patch`, 2 `defer`, 13 dismissed as noise.

**Acceptance Auditor: no confirmed AC violations.** Spot-verified against the actual code rather
than trusting the diff's own comments: AC 1/Q1 (`agentSocketUrl` derives purely from
`window.location`, `new WebSocket` appears exactly once in the whole diff, at `client.ts`);
Task 3 (checked against the real pre-diff `App.tsx` via `git show 3027109:ui/src/App.tsx` —
`useAgentConnection()` is inserted strictly before both measured effect blocks, not between
them, so the ordering claim is true of the hook-call order and not merely asserted); AC 18/Q7
(dev-proxy `/ws` anchoring, `ws:true` + Origin-rewrite scoped correctly, backed by a real Vite
server + raw HTTP upgrade round-trip test); AC 21 (`disconnected` arm converted from a
`STORE_DRIVEN_ARMS` placeholder to a real end-to-end test; `copy-tails.test.ts`'s fourth tail
reads the shipped `socket.ts` constants).

**One attempted patch reverted after testing it.** `WEBSOCKET_PATTERNS`'s `readonly string[]`
type (rather than a literal tuple derived from `PROXIED_PATTERNS`'s `as const`) was flagged
independently by both Blind Hunter and the Acceptance Auditor as a precision nit. Applying the
narrower type broke real compilation: `Object.entries(createDevProxy(...))` (used in both
`createDevProxy` and `devProxy.test.ts`'s own assertions) always widens object keys to `string`
per TypeScript's `Object.entries` signature, so `WEBSOCKET_PATTERNS.includes()` must accept a
general `string` at its real call sites. The original typing was a deliberate necessity, not an
oversight — reverted, `tsc -b --force` clean.

- [x] [Review][Defer] `agentEventOf` only validates the `kind` discriminant, not `id`/`ts`/
  `payload` [ui/src/api/client.ts:701-716] — deferred: matches this file's established
  "narrow only what the consumer reads" idiom (see the function's own docstring), and nothing in
  scope today reads those fields (the two system-event kinds are dispatched by `kind` alone in
  `socket.ts`; the four agent-view kinds are dropped unread). Becomes actionable when Epic 6
  builds the agent views and starts reading `id`/`ts`/`payload`.
- [x] [Review][Defer] The equivalence between the agent's outbound `POST /agent/events` body
  shape and the WebSocket frame the browser actually receives is asserted only in a comment
  ("`ws.py` broadcasts the ingested event verbatim") [ui/src/api/schema.ts,
  ui/src/api/client.ts:662-669] — deferred: a cross-language contract test (Python broadcast vs.
  TS `AgentEvent`) is out of scope for this diff and would need to live in the backend or an
  integration suite, not here.

### Group 1 — dismissed as noise (12)

`resetCardAttempts()` clearing the whole attempt budget (intended — "give every id its budget
back" is the documented design, not a bug); `CARD_READ_IS_RETRYABLE` unmapped-reason risk
(map is `satisfies Record<ErrorReason, boolean>`, exhaustive at compile time); no guard against
`useAgentConnection` double-mount (matches the same unenforced convention used by
`useSystemState`/`useDeckState` already); `onReconnected` firing on an ordinary dev-boot race
(explicitly documented as intended); `surfaceOf`'s connection-down arm outranking a fresh deck
refusal (Q3's explicit ruling — not to be relitigated); this diff's inability to verify its own
`App.tsx` integration point (expected consequence of chunking, not a defect); `schedule()`'s
backoff-growth side effect (single call site, no double-call risk demonstrated);
`resetCardAttempts()` wiping an in-flight read's counter (same intended-design root cause as
above); `restartPollIfStopped`'s duplicate-event race (self-correcting, generation-guarded);
**`DISCONNECTED_PANEL` declared independently in `deck.ts` and `socket.ts`** — initially triaged
as a patch, reclassified on closer read: both docstrings explicitly frame this as "the second of
the two places in the app that names a panel produced by a client-side condition... retarget it
at a wire-sourced panel and `npm run typecheck` names it" — two independent hand-typed
declarations are the deliberate mechanism, not an oversight; hoisting to one shared constant
would remove that independence; **the duplicated `mounted`-singleton seam in `systemState.ts` /
`deck.ts`** — same reclassification: `deck.ts`'s docstring calls its slot "the mirror of
`systemState.ts`'s `mounted` poller, and both exist for the same reason" — an intentional
parallel structure the author already considered, not an unnoticed duplication; a generic
extraction was judged not worth touching two heavily-tested state-lifecycle files for a stylistic
gain when the codebase's own comments already justify the mirroring.

## Dev Notes

### The wire contract you are consuming (backend is DONE — do not modify behaviour)

- **Mint**: `GET /api/session` → 200 `{"ticket": "<~43 url-safe chars>"}` always, under a
  running lifespan; `Cache-Control: no-store` (the only 200 in the app with it); no credential,
  no Origin check (ruled at c5-2 Q1). Ticket: **single-presentation** (popped on every consume
  attempt, success or not), **30 s TTL** (`TICKET_TTL_SECONDS`, `state.py:163`), 256-resident
  cap with earliest-expiry eviction — an eviction storm costs the client exactly one failed
  upgrade and one re-mint, which this loop absorbs by design (`state.py:183-190`).
- **Upgrade**: `ws://<host>:<port>/ws?ticket=<t>` — query param `ticket` (`ws.py:97`; a browser
  `WebSocket` cannot set headers, which is why). Order: Host (middleware) → exactly-one-Origin
  → consume. **Every refusal is close code 1008 pre-accept, rendered as HTTP 403, with no body
  and no reason token** — missing/expired/replayed ticket and bad Origin are deliberately
  indistinguishable on the wire (`ws.py:29-40`). 1011 = server fault only. The client cannot
  diagnose *why* an upgrade failed; the loop's answer to every failure is the same: back off,
  re-mint, retry.
- **Frames**: server → client only; each text frame is one `AgentEvent` envelope
  `{kind, id, ts, payload}` serialised by pydantic. Client → server frames are read and
  discarded — chatter never closes the socket. **No server heartbeat exists**; the browser's
  `close`/`error` events are the only drop detectors. `id` is opaque dedupe, never ordering;
  `ts` orders (AD-6).
- **Kinds**: `suggestions | swaps | tier_list | groups | deck_changed | active_deck_changed`.
  `deck_changed` = "the deck you are showing was edited" (`deck_id` may be null = "refetch
  whatever is active"); `active_deck_changed` = "which deck you are looking at changed" —
  conflating them makes the UI refetch the deck it is leaving (`contracts.py:902-905`).
  `active_deck_changed` fires on **every** PUT including a redundant one.
- **Active deck read**: `GET /api/active-deck` → always 200, `{"deck_id": "<id>"}` or
  `{"deck_id": null}`; a non-null id is not a promise the deck exists — the follow-up deck read
  may still answer `deck_not_found`.
- `test_ws.py:129-137` (`test_two_sequential_sockets_each_need_their_own_ticket`) is annotated
  as this story's loop shape. `tests/unit/companion/conftest.py:173-220` holds the hand-rolled
  ASGI websocket driver — backend-side; you will not need it, your socket is faked.

### The guard gauntlet (read BEFORE deciding file layout — these turn green tests red)

1. **`posture.test.ts:322-342`** scans every tracked non-test `src/**/*.ts(x)` (comments
   stripped) for `/\b(?:fetch|XMLHttpRequest|EventSource|WebSocket|navigator\.sendBeacon)\b/`
   and asserts the match list `toEqual(['src/api/client.ts'])` — **the identifier `WebSocket`
   anywhere in a new `src/state/socket.ts` reds it**, and `App.tsx` must match no network
   family (`:344-353`). Q1 exists because of this.
2. **`store-writes.test.ts`**: one writer module per store, table completeness-checked by a
   `create[<(]` scan; a new store slice needs a `STORES` entry with a ≥40-char why. `deck.ts`
   specifically may not contain `fetch(`, `new WebSocket(`, or any timer identifier
   (`:185-203`) — the reconnect timer CANNOT live there.
3. **`wire-contract.test.ts`**: `./types` importable only by `schema.ts`; every
   `components.schemas` name (`SessionTicket`, all six `*Event`s, all payloads) is a banned
   type name outside `src/api/` — name local types something else or alias in `schema.ts`.
4. **`copy-rules.test.ts`**: any module whose string literals reach JSX/`aria-*` with 2+ words
   must be in `COPY_MODULES`. This story should write **no new user-facing prose** (the
   disconnected copy already ships); if a string sneaks in, the gate names it.
5. **`package-contract.test.ts`**: no second codegen/store/fetching lib — hand-roll the loop.
6. **`gate-geometry.test.ts`**: tests live in `src/**` (dom project) or `tests/**` (node
   project), `.ts`/`.tsx` only.
7. **Scan authority**: all five meta-suites read `git ls-files` — an unstaged new module passes
   vacuously. `git add` before trusting green (declared blind spot, every header).
8. **`states.ts` type-level asserts**: `disconnected` must stay OUT of `PANEL_FOR_REASON`
   (`PanelSourcesAreDisjoint`); `RETRIES_QUIETLY` is total and `disconnected: true` is a
   shipped contract this story is held to.
9. **`shell.test.ts` / containers**: containers may not touch `fetch|WebSocket|zustand|
   .setState` — the socket never goes near `src/containers/` or `src/components/`.

### The pattern to copy (this is a solved problem in this codebase — do not invent)

`poller.ts` is the house implementation of "framework-free loop with injected reader, fake-timer
tests, generation counter, backoff with arithmetic-carrying constants":

- Constants: `POLL_BASE_MS = 2_000`, `POLL_MULTIPLIER = 2`, `POLL_CEILING_MS = 30_000`
  (schedule 2, 4, 8, 16, 30, 30… s); `STALLED_AFTER_MS = 60_000` **AND**
  `STALLED_MIN_REFUSALS = 4` — the two-gate escalation (wall clock alone lies across a laptop
  suspend; a throttled background tab lies the other way). Q2 proposes the same two-gate shape
  for "exhausted".
- Scheduling: `setTimeout(...)` then grow — the first retry lands at exactly base.
- Generation: bumped by `start()` AND `stop()`, re-checked after **every** await. Your loop has
  more awaits than the poller's one (mint → open → each event) — `deck.ts:286-302` documents
  exactly this extension.
- Emission: on change only; `unreachable` decides nothing.
- Tests: `vi.useFakeTimers()` + `vi.setSystemTime(0)`; `settle = () =>
  vi.advanceTimersByTimeAsync(0)`; readers that record `Date.now()` per call; schedules
  asserted as absolute timestamp arrays (`poller.test.ts:97-105`); the contract-is-read test
  flips `RETRIES_QUIETLY` in a try/finally and asserts behaviour follows. Your fake socket is
  an injected factory returning a scriptable object with `onopen/onmessage/onclose/onerror`
  and a recorded `close()` — no real network, no new dep.

### Wiring seams that already exist (extend, never replace)

- **Refetch = `createDeckBoot.stop()/start()`** — idempotent, generation-guarded, seeds card
  summaries, settles refusals; `useDeckState` already re-drives it edge-triggered from
  `subscribeSystemState`. Add a sibling seam (e.g. `subscribeConnection` or an exported
  re-drive callback) rather than a second boot implementation. **Do not weaken the existing
  edge-trigger semantics** — a loaded `'deck'` is never re-driven by the *poll* edge; your
  reconnect re-drive is a different, deliberate trigger.
- **`surfaceOf(deck, system)`** (`deck.ts:429-433`) is the three-arm precedence (deck >
  deck-refusal > system panel). A loaded deck currently outranks every system panel — the
  epic's "the Disconnected panel takes the left column" therefore needs a deliberate
  precedence decision (Q3), not an accidental one.
- **`useSystemStore` writes go through `systemState.ts`** (its declared owner); the store is
  subscribed selector-less in `App`, so any write re-renders the whole app — write connection
  state on change only, exactly as the poller emits.
- **`panelFor` / `PANEL_FOR_REASON`** stay untouched: `disconnected` has no wire token by
  design; it is derived from the client-side condition, never from a response.

### The family — ledger anchors this story must disposition (trigger-gated per R1)

Carried IN FULL because this story's surface triggers every one:

1. **dw:3451-3461 + dw:4930-4940** — first load, backend unreachable: "No deck on the glass"
   holds forever, its copy *actionable and wrong* (confirmed live 2026-08-07, severity
   raised). The true panel is `disconnected`. **This story's AC 14.**
2. **dw:3463-3470** — after one 200 the poll stops; a later DB death shows a stale panel until
   reload. The replacement signal is this story's socket. **AC 15.**
3. **dw:3472-3478 + dw:3544-3555 (C3 retro R3)** — `database-updating-stalled` is terminal; a
   user who obeys the panel and succeeds still needs a manual refresh. R3: *"c5-6 resolves the
   family."* **AC 15.** (Felt live at Block I: wire 200, poll count moved by exactly 0 over
   45 s — dw:4968-4972.)
4. **dw:3652-3671 (entries 5 & 6, re-homed ENTIRELY to c5-6 by Brad at c5-4 Q6)** — three
   transient failures make a card id terminal for the tab's life while everything else
   self-heals; plus the orphaned-hydration declare. A blanket `resetCardCache()` is probably
   wrong (the cache is shared with Epic 6's views; a reset throws away hydration both decks
   share). **Q6 rules the shape; AC 16.**
5. **dw:3526-3534** — the backoff-damping question (alternating tokens pin the poller's backoff
   near base), re-homed here because "c5-6 owns the family about that poller's re-drive
   behaviour". **Q4 in the open questions rules it; a written disposition either way.**
6. **dw:3500-3505** — `CLIENT_ONLY_STATES` has no runtime consumer; c5-6 "either consumes it or
   is the story that says it should stay type-level". **AC 17.**
7. **dw:5221-5237** — the Vite dev proxy rewrites `Host` but not `Origin`; a proxied handshake
   403s with no message the moment `/ws` is proxied (Medium — "slow to diagnose from the
   browser side"). Three candidate fixes are already enumerated in the entry. **Q7; AC 18.**
   Also recorded in `ui/README.md:52-61`, which names c5-6 as owner.
8. **dw:1588 (copy-tails fourth tail)** — the disconnected row's connection-pill note was
   "declined and re-homed on c5-6 by name"; `copy-tails.test.ts:223-235` says it is
   deliberately weak until this story ships the mechanism. **AC 21.** (The *pill itself* is
   c5-7's — strengthen only what this story makes checkable: the backoff exists and
   `disconnected` is selected by it.)
9. **dw:5079-5083** — the probe-harness vitest half, homed on "the first C5 story that touches
   `ui/` and plants a frontend guard — realistically c5-6". **Q9 rules it.**
10. **dw:3756-3768** — the no-re-drive-after-boot browser half (`active_deck_changed` arrives
    on the wire, nothing listens) and the 404-clears-then-re-asks residue, both re-homed to
    c5-6 at c5-4 Q6. The first is **AC 11**; the second is dispositioned (the event now
    delivers the correction — say so in the entry).

Not triggered, one line each: broadcast overlap race + slow-client stall (c5-4 accepted
residuals — backend, untouched); `internal-error` first render → **Epic C5 manual checklist**,
not this story's dev job; A4-recovery/A5/A6 manual items ride the checklist with this story's
fix as their subject; prose-sync debt + `dump_openapi.py` changelog → C5 retro; 250 ms
concurrent-push measurement → c10-3.

### Landmines specific to this story

- **The 30 s TTL vs the 30 s backoff ceiling**: mint INSIDE the attempt, after the delay —
  `delay → mint → open` — never `mint → delay → open`. At the ceiling the two windows are
  equal and a pre-delay mint hands the upgrade an expired ticket every time (AC 3 spells the
  ordering).
- **Wall-clock across a suspend**: `Date.now()` elapsed lies after a laptop sleep — the reason
  `STALLED_MIN_REFUSALS` exists (`poller.ts:98-114`). Q2's exhaustion definition should carry
  the same observation floor. A resumed tab also fires a burst of queued timers; the
  generation counter is what keeps that safe.
- **Two writers of `panel` race**: if the socket writes `panel: 'disconnected'` into the same
  field the poller writes, a later poll success (a *change*) overwrites it while the backend's
  HTTP half is up but the WS half is failing (e.g. a proxy misconfiguration). Q3/Q8's
  recommendation derives `disconnected` from connection status in `surfaceOf` instead of
  writing the shared `panel` field — pick deliberately, write the reason down.
- **`no-active-deck` after restart, not an error**: AC 6's refetch lands `{"deck_id": null}` →
  `{status:'none'}`. Do not route it through a refusal arm; `deck.ts:339` already
  short-circuits a null id with no request.
- **Effect ordering in `App.tsx` is measured and load-bearing** (`:245-267`, `:341-359` —
  "DO NOT REORDER EITHER BLOCK WITHOUT RE-MEASURING"). Add the socket effect without moving
  the existing two; note in a comment where the WS upgrade lands in the request queue.
- **jsdom has no `WebSocket`** — another reason the factory is injected. Never construct a real
  socket in a test; `devProxyRoundTrip.test.ts` is the only place a real listener is
  sanctioned, and it runs in the node project.
- **Backend prose reconciliation touches `src/companion`** — prose-only, behaviour
  byte-identical, but it means the plugin mirror must be rebuilt and sha256-verified (the
  pre-commit hook enforces it), and the Python suite count must not move.
- **`answering()` fixture routing**: `/api/deck/{id}/format-check` starts with `/api/deck/` —
  every path-routed fetch fixture must branch on `endsWith('/format-check')` first
  (`App.test.tsx:1170-1176`). Your session path adds a fourth route to those fixtures.

### Previous-story intelligence (c5-5, reviewed 2026-08-08)

- All 7 open questions were ruled by Brad **before any code** — same protocol here: the Open
  Questions below are written for pre-Task-0 ruling, recommendations first.
- c5-5's review theme: **a test that passes under the exact failure it was written to catch**
  (the byte-identical-refusal test survived a planted `raise`; the delivered-vs-connected
  discriminator didn't discriminate until the probe said so). Both were caught by R2 planted
  probes through the full suite — budget for the probes, they changed the diff twice.
- The review's three patches included a real mechanism bug in review-added code
  (`Content-Length: 0`/negative bypassed the body cap) — the standing "review-added mechanisms
  re-enter review" agreement is live for this story too.
- `probe_harness.py` owns a pytest argv and **cannot run vitest** — its own docstring says so.
  Frontend probes must run the full `npm test` by hand until Q9 is ruled.
- A pre-existing intermittent flake exists: `test_list_decks_with_strategy_field` failed once
  in isolation-passing form during c5-5's probe runs — flagged for the C5 retro; if it fires
  in your full-suite runs, record it, do not chase it.
- Baseline after c5-5's merge (PR #57, umbrella at `3027109`): Python **2,770 / 1 skipped**
  (`-m "not integration"`); frontend **1,706 / 66 files**; `gen:api` idempotent.

### Project structure notes

- New: `ui/src/state/socket.ts` + `socket.test.ts` (dom project). Modified: `ui/src/api/client.ts`
  (+`client.test.ts`), `ui/src/api/schema.ts`, `ui/src/state/systemState.ts`, `ui/src/state/deck.ts`
  (seam only), `ui/src/App.tsx` (+`App.test.tsx`), `ui/config/devProxy.ts`,
  `ui/tests/devProxy.test.ts`, `ui/tests/devProxyRoundTrip.test.ts`, `ui/tests/copy-tails.test.ts`,
  `ui/tests/store-writes.test.ts` (STORES entry if Q8 adds a slice), possibly
  `ui/tests/posture.test.ts` (only if Q1 argues the door list open — in the same commit, with the
  reason in the table). Prose-only: `src/companion/app/{state,ws,spa}.py`, `ui/src/state/poller.ts`
  header, `deferred-work.md`, `sprint-status.yaml`, `plugin/` mirror.
- **No Python behaviour change anywhere.** No new wire schema → `gen:api` stays a no-op and
  `openapi.json`/`types.d.ts` are untouched.
- Frontend conventions: strict TS, eslint/stylelint/prettier gates, Google-style docstrings on
  exported functions (house style in `ui/src/state/*`), module docstrings that argue decisions
  (read `poller.ts`'s header for the register).

### References

- Epic: `_bmad-output/planning-artifacts/epics-companion-app.md:2545-2576` (Story 5.6),
  `:856-871` (Epic 5), `:153-155` (NFR-04), `:246-249` (AD-5 two-credentials),
  `:226-253` (AD-6/AD-9 contracts)
- UX: UX-DR29/30 (`:495-504`), UX-DR33 (`:543-547`), UX-DR35 (`:557-562`), UX-DR37 (`:570`)
- Backend: `src/companion/app/routes/session.py`, `ws.py` (esp. `:29-40`, `:97`, `:284`,
  `:409-444`), `state.py` (`:163-190`, `:318`), `security.py:148-175`,
  `contracts.py:872-947, 1227-1235`
- Frontend: `ui/src/state/poller.ts` (whole file), `deck.ts` (`:47-79`, `:286-347`,
  `:429-486`), `systemState.ts`, `components/StatePanel/{states,copy}.ts`,
  `api/client.ts` (`:530-567`), `api/types.d.ts` (`:256-283`, `:747-761`),
  `config/devProxy.ts`, `ui/README.md:52-61`
- Ledger: `deferred-work.md:1588, 3451-3478, 3500-3505, 3526-3555, 3652-3671, 3756-3768,
  4930-4972, 5079-5083, 5221-5237`
- Process: sprint-status `action_items` — C4 R1 (Dev Notes < 41 KB), R2 (firing proofs),
  grep-own-key, probe-harness (open, Brad c5-1), plugin-mirror-from-ui (open, Brad C5)

## Open questions for Brad (recommendations first — rule before code)

1. **Where does `new WebSocket` live?** `posture.test.ts:341` pins the network-door list to
   exactly `['src/api/client.ts']`, and its family regex includes `WebSocket`. Recommend:
   construction stays in `client.ts` (a tiny exported `openAgentSocket(ticket)` that builds the
   relative URL and returns the socket), and `src/state/socket.ts` takes the factory injected —
   the loop module never contains the banned identifier, the door list is untouched, and the
   c4-1 precedent ("one network door", renamed rather than weakened) holds. Alternative —
   arguing the list open to two doors — spends a decide-once ruling for no gain.
2. **What does "retries are exhausted" mean?** The epic says the panel appears when "the client
   gives up", but `RETRIES_QUIETLY.disconnected = true` is a shipped contract saying the state
   keeps retrying. Recommend: the two-gate escalation shape the codebase already uses —
   `DISCONNECTED_AFTER_MS = 60_000` elapsed **AND** `DISCONNECTED_MIN_FAILURES = 4` consecutive
   failed attempts → show the panel; the backoff continues at the 30 s ceiling forever behind
   it. "Exhausted" = the announcement threshold, not a stop — a true stop would recreate the
   exact needs-a-reload defect this story exists to kill (AC 9), and the c5-7 pill needs a
   live "reconnecting" state to announce anyway.
3. **Does the Disconnected panel displace a loaded deck?** The epic AC says it "takes the left
   column" (UX-DR30: one state panel at a time, left column); `surfaceOf` currently ranks a
   loaded deck above every system panel; UX-DR35 says never tear down to a skeleton *during
   reconnection*. Recommend: yes, on exhaustion only — a fourth `surfaceOf` arm where the
   connection status (not the `panel` field) forces the disconnected panel above `'deck'`; the
   deck slice is untouched underneath, so recovery re-renders it instantly. During the
   pre-exhaustion window the deck stays on screen, satisfying both rules.
4. **The poller backoff-damping question (dw:3526), ruled at last.** Recommend: **no damping —
   close the entry with a written reason.** The socket loop has one failure kind, so its
   backoff resets only on a successful connection and the alternating-token scenario cannot
   arise there; the poller's reset-on-flip cost was accepted at Q2/c3-9 and the socket now
   supplies the recovery signal that made the question matter. If ruled the other way, the
   change is one identity function in `poller.ts` (no reset between the two database tokens).
5. **How much re-driving on reconnect?** Recommend: reconnect success re-drives **both** the
   deck boot (stop/start) and the system poller (stop/start — a restart is a fresh poll by
   design, `poller.ts:293-306`); a system-kind event (`deck_changed`/`active_deck_changed`)
   re-drives the deck boot always and the poller only when the current panel is one the poll
   has stopped on (`RETRIES_QUIETLY[panel] === false`). That resolves all three family
   siblings with no heartbeat and no second polling mechanism.
6. **Card-cache recovery shape (dw:3652/3666).** Recommend: on reconnect success, reset the
   per-id **attempt counters only** (new narrow verb in `cards.ts`, e.g.
   `resetCardAttempts()`), never the hydrated entries — terminal ids become retryable, shared
   hydration survives, and the orphaned-return declare stands unchanged. Blanket
   `resetCardCache()` stays test-only.
7. **The dev-proxy Origin fix (dw:5221's three candidates).** Recommend: **(a)** — the proxy
   rewrites `Origin` to the backend target on the `/ws` entry (Vite proxy `headers` /
   `configure`), keeping the backend check strict and shipping no bypass in security code;
   proven in `devProxyRoundTrip.test.ts` or a dedicated config assertion with a firing proof.
   (b) — the dev client dialling the backend port directly — makes dev and prod diverge in the
   client code itself; (c) — an `allowed_origins` widening flag — is the ledger's own "worst
   of the three".
8. **Where does connection status live for c5-7's pill?** Recommend: extend the system slice —
   `SystemState` gains a `connection: 'live' | 'reconnecting' | 'down'` field, written on
   change only, through a function owned by `systemState.ts` (its store, its writer — no new
   `STORES` entry needed); `surfaceOf` reads it for Q3's arm; c5-7 reads it for the pill.
   Alternative (a fourth store) spends a `STORES` entry and a writer module for one field.
9. **The probe-harness vitest half (dw:5079, C4 action item still open).** Recommend: **scoped
   decline here** — this story runs its frontend probes as c4/c5-5 did (full `npm test` by
   hand, collected-count checked, results pasted), and the committed vitest harness lands as
   the standalone process item it already is (owner "Brad (c5-1)", unstarted) rather than
   inside the epic's largest frontend story. If ruled in, it is a `scripts/probe_harness.py`
   extension (vitest argv owner + crash-signature refusal + count validation), not a new tool.

## Dev Agent Record

### Agent Model Used

claude-opus-5[1m] (Claude Opus 5, 1M context), via the `bmad-dev-story` skill.

### The nine open questions, ruled before any code (Brad, 2026-08-08)

**All nine accepted as recommended**, in one ruling, in the manner c5-5 established (all 7 ruled
pre-Task-0). Recorded here rather than only in the section above, because the section above is the
*question* and this is the *answer* — a reader of the diff needs the answer where the record is.

| Q | Ruling |
| --- | --- |
| 1 | `new WebSocket` stays in `client.ts` (`openAgentSocket`); `state/socket.ts` takes the factory injected. `posture.test.ts:341`'s door list is untouched. |
| 2 | Two-gate exhaustion, `poller.ts`'s shape: `DISCONNECTED_AFTER_MS = 60_000` **AND** `DISCONNECTED_MIN_FAILURES = 4`. The panel is an announcement; the backoff keeps retrying at the ceiling forever. |
| 3 | The panel displaces a loaded deck **on exhaustion only**, through a fourth `surfaceOf` arm reading connection status — not the `panel` field. |
| 4 | **No damping.** dw:3526 closed with a written reason. |
| 5 | Reconnect success re-drives deck boot **and** poller; a system-kind event re-drives the boot always and the poller only when `RETRIES_QUIETLY[panel] === false`. |
| 6 | `resetCardAttempts()` — attempt counters only, never hydrated entries. Blanket `resetCardCache()` stays test-only. |
| 7 | Dev proxy rewrites `Origin` to the backend target on the `/ws` entry (candidate (a)). |
| 8 | `SystemState` gains `connection`, written on change only through `systemState.ts`. No new `STORES` entry. |
| 9 | **Scoped decline** — frontend probes run the full `npm test` by hand; the committed vitest harness stays the standalone process item it already is. |

### Task 0 — baseline and reconnaissance

**Branch**: `feat/companion-c5-6-client-reconnection`, off `feat/companion-c5` at `3027109`
(`git rev-parse HEAD` confirmed the umbrella tip is exactly the commit the story names).

**Baselines, measured rather than assumed:**

| Suite | Command | Result |
| --- | --- | --- |
| Python | `uv run pytest -m "not integration"` | **2,770 passed, 1 skipped**, 54 deselected (98.96 s) — matches the story |
| Frontend | `npm test` | **1,706 passed / 66 files** (5.94 s) — matches the story |
| Codegen | `npm run gen:api` | clean no-op — `types.d.ts` unchanged, `git status` shows no `ui/` diff |

**`grep -rn "c5-6" src/ ui/ tests/ scripts/` — 27 text hits (plus 3 `__pycache__` binaries,
ignored). Every one enumerated with its disposition:**

*Backend prose (7 hits, behaviour byte-identical, Task 7 reconciles):*

| Hit | Disposition |
| --- | --- |
| `src/companion/app/spa.py:239` | "c5-6's /ws" as a future path — **fulfilled**, rewrite to present tense |
| `src/companion/app/state.py:173, :183, :190, :318` | four predictions that c5-6 mints a fresh ticket per attempt and absorbs an eviction storm — **all four fulfilled** (AC 3), rewrite |
| `src/companion/app/ws.py:35, :39, :284` | predictions that c5-6 re-mints and retries on 1008 / on a stray close — **fulfilled**, rewrite |

*Frontend prose predicting the mechanism (10 hits, Task 7 reconciles):*

| Hit | Disposition |
| --- | --- |
| `ui/config/devProxy.ts:72` | "`/ws` is deliberately absent: **c5-6** adds it" — **fulfilled by Task 5**, rewrite |
| `ui/README.md:59, :1215, :1256, :1318` | four predictions (proxy entry, the WebSocket, the no-later-edge residue) — **fulfilled**, rewrite |
| `ui/src/api/client.ts:133` | "`disconnected` is c5-6's … this story may not claim it" — **fulfilled**, rewrite |
| `ui/src/components/StatePanel/states.ts:194, :237` | `CLIENT_ONLY_STATES` / `RETRIES_QUIETLY` prose naming c5-6's backoff as the producer — **fulfilled** (AC 17), rewrite |
| `ui/src/state/poller.ts:32, :34` | the ledgered residue against c5-6 — **fulfilled** (AC 14), rewrite |

*Frontend prose that is a re-homing record (5 hits):*

| Hit | Disposition |
| --- | --- |
| `ui/src/state/cards.ts:432` | Q6 re-homed the damping question here — **dispositioned by Q4 (no damping)**, rewrite |
| `ui/src/state/deck.ts:68, :76, :78, :126` | the c5-4 Q6 narrowing and the no-later-edge residue — **fulfilled** (AC 14, 16), rewrite |

*Test-file comments (4 hits, converted or strengthened by Task 6):*

| Hit | Disposition |
| --- | --- |
| `ui/src/App.test.tsx:423, :1163, :1274` | three notes that `disconnected` has no trigger in this repo — **AC 21 converts `:1274`'s store-driven arm**; the other two are rewritten |
| `ui/src/api/client.test.ts:226`, `ui/src/state/deck.test.ts:356`, `ui/src/state/poller.test.ts:384`, `ui/src/state/cards.test.ts:557` | the same "c5-6 owns it" note in four suites — rewritten |
| `ui/tests/copy-tails.test.ts:23, :224, :227, :232` | the deliberately-weak fourth tail — **AC 21 strengthens it** |
| `ui/tests/devProxy.test.ts:146` | "does not yet proxy /ws" — **AC 18 inverts it** |

*Backend tests naming this story's shape (2 hits, no edit needed):*

| Hit | Disposition |
| --- | --- |
| `tests/unit/companion/test_ws.py:130` | "the shape c5-6's reconnect loop will actually perform" — **true and still true**; the loop now performs it. Prose-only rewrite. |
| `tests/unit/companion/test_spa.py:483` | "c5-6's /ws" as a future path — rewrite to present tense |

**Anchors read end-to-end before any code**: `poller.ts` (whole file), `deck.ts` (whole file),
`cards.ts` (whole file), `client.ts` (whole file), `schema.ts`, `systemState.ts`, `states.ts`,
`App.tsx`, `config/devProxy.ts`, plus the five guard suites (`posture.test.ts`,
`store-writes.test.ts`, `copy-tails.test.ts`, `devProxy.test.ts`, `devProxyRoundTrip.test.ts`) and
`poller.test.ts`'s fake-timer idiom.

**Two guard facts measured rather than inherited**, both of which shaped the file layout:

1. `posture.test.ts`'s `codeOf()` strips comments but **keeps string and template literals**
   (`stripComments`, `:75-113`). So the identifier `WebSocket` is safe in a docstring and
   **unsafe in a string** anywhere under `src/`. Q1's injected factory is what keeps
   `src/state/socket.ts` off the door list; this measurement is why the module also carries no
   `'WebSocket'` string.
2. `store-writes.test.ts:112-113` reports a module as a writer of a store if it contains
   `setState` **and** the store's name, in any order — which is why `deck.ts` reaches
   `useSystemStore` only through `subscribeSystemState`. The reconnect seam this story adds
   follows the same shape.

### Debug Log References

No debugger sessions. The three investigations that mattered were measurements, and each is
recorded where it changed a decision rather than in a log: jsdom's `WebSocket`, Node's absent
`Origin` header, and the upgraded-socket teardown that made three green tests report as failures.
See "Two measurements that changed the design" below.

### The R2 firing proofs (AC 20)

**Twelve probes, every one RED through the FULL `npm test`** — never a standalone file run. Each
plants ONE violation in a shipped module, runs the whole suite, and is reverted; the harness lives
in the session scratchpad and each probe records *what the assertion actually compares*, which is
the half AC 20 asks for beyond "it went red".

All new files were `git add`ed first: all five meta-suites read `git ls-files`, so an unstaged
module passes them vacuously.

| # | Planted violation | Full-suite result | What the red assertions actually compare |
| --- | --- | --- | --- |
| a | `socket.ts`: drop the `Math.min(…, SOCKET_CEILING_MS)` clamp | **12 failed** / 1,800 | the recorded mint TIMESTAMPS against an absolute schedule, past the clamp point |
| b | `socket.ts`: mint BEFORE the `setTimeout` (`mint → delay → open`) | **11 failed** / 1,801 | `openedAt − mintedAt` per attempt — zero as shipped, a full ceiling with a pre-delay mint |
| c | `socket.ts`: remove the generation bump inside `fail()` | **2 failed** / 1,810 | the number of mints after ONE drop that fired `error` then `close` |
| d | `socket.ts`: replace `retriesQuietly[DISCONNECTED_PANEL]` with `true` | **1 failed** / 1,811 | mint count after the panel appears, with `RETRIES_QUIETLY.disconnected` flipped `false` |
| e | `socket.ts`: drop the `failures >= DISCONNECTED_MIN_FAILURES` gate | **1 failed** / 1,811 | the emitted status after a clock jump with only ONE observed failure |
| f | `deck.ts`: delete `surfaceOf`'s connection arm | **12 failed** / 1,800 | the rendered region NAME for a down connection, at the root and at the pure-function level |
| g | `cards.ts`: clear the attempt map without re-arming the entries | **4 failed** / 1,808 | whether a re-armed id issues a REQUEST — not whether a flag changed |
| h | `devProxy.ts`: drop `headers: { origin: target }` | **3 failed** / 1,809 | the `Origin` header BYTE a stub backend received through a real Vite upgrade |
| i | `client.ts`: `close()` without detaching the handlers first | **1 failed** / 1,811 | whether `onClose` fired after the CALLER closed the socket itself |
| j | `client.ts`: `kind in AGENT_EVENT_KINDS` instead of `Object.hasOwn` | **2 failed** / 1,810 | `agentEventOf('{"kind":"__proto__"}')` — an inherited key read as a known kind |
| k | `socket.ts`: `const reconnected = true` | **2 failed** / 1,810 | the reconnect-callback count on the FIRST open of a tab |
| l | `devProxy.ts`: `'^/ws'` instead of `'^/ws(?:[/?]|$)'` | **2 failed** / 1,810 | whether `/wsx` reaches the stub backend through a real Vite upgrade |

**One finding came out of the harness rather than out of a probe**, and it is worth carrying: a
subprocess `npm test` launched with a **lowercase drive letter** (`c:\…`) resolves no vitest config
on Windows and reports 67 failed suites / "no tests". Every probe would have read RED for a reason
having nothing to do with the probe — the exact shape of a firing proof that proves nothing. The
harness normalises the drive letter and validates the collected COUNT, and dw carries the note for
whoever builds the committed vitest half (dw:5079).

### Suites, gates and counts

| Gate | Result |
| --- | --- |
| Frontend `npm test` | **1,812 passed / 67 files** — from 1,706 / 66. Strictly larger; +106 tests, +1 file |
| Python `-m "not integration"` | **2,770 passed / 1 skipped** — byte-identical to baseline. No behaviour change |
| `npx tsc -b --force` | clean |
| `eslint .` | clean |
| `stylelint src/**/*.css` | clean (no CSS touched) |
| `prettier --write` | clean |
| `ruff check` / `ruff format` | clean |
| `mypy --strict` | 93 source files, no issues |
| `pre-commit run --all-files` | all hooks Passed, including the plugin-mirror sync |
| `npm run gen:api` | verified a **no-op** — `types.d.ts` unchanged; this story adds no wire schema |
| Plugin mirror | rebuilt; `spa.py` / `state.py` / `ws.py` sha256-verified identical to `src/` |

**The frontend suite was run seven consecutive times** at the end; 1,812/1,812 every time.

### Two measurements that changed the design, recorded rather than smoothed over

1. **jsdom DOES provide `WebSocket`** — the story's Dev Notes state that it does not, and that is a
   **falsified prediction**. Without an explicit `vi.stubGlobal('WebSocket', …)` in
   `App.test.tsx`'s `beforeEach`, all ~70 mounts in that file would attempt a real TCP connection to
   `ws://localhost:3000`, making the retry schedule depend on how fast the OS refuses a connection.
   The Dev Notes' *conclusion* — inject the factory, never construct a real socket in a test —
   survives; only its stated reason was wrong.
2. **Node's global `WebSocket` sends no `Origin` header** (it is not a browsing context). The first
   draft of the dev-proxy round trip used it, and the negative half recorded the forwarded Origin as
   `<absent>` — a negative half that cannot reproduce the header under test is not a negative half.
   The block now drives raw `http.request` upgrades with an explicit `Origin`, which is also what
   `security.py`'s docstring says c5-8's real client will have to do.

A third, smaller one: an upgraded socket is detached from the server's request lifecycle, so
`server.close()` waits for it forever — the round-trip block's first run reported three tests
"failed" with **no failed expectation between them**, the `afterEach` hook having hit its 10 s
timeout. Both ends are destroyed by hand now, and the suite went from 31 s to 1.5 s.

### The pre-existing flake, sighted a second time

`tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field` failed once
during the post-prose Python run (`assert 'Control' is None`) and passed on an immediate clean
re-run at exactly 2,770 / 1 skipped. The Dev Notes named it and instructed *record it, do not chase
it*; that is what happened. It is now a **second** sighting after c5-5's, which is the fact worth
carrying to the C5 retro rather than the individual failure.

**And one intermittent this story made more likely, stated plainly rather than buried.** Twice
during verification a full `npm test` reported 66/67 files (1,807 and then 1,805 of 1,812 tests)
with vitest's "unhandled error" warning and **no failing assertion** — one file lost its collection.
It then did not recur in **26 consecutive runs**, including six that deliberately reproduced the
shape both sightings had and three with a concurrent `git add -A`. Unreproduced, so unfixed.

The honest reading is not "probably nothing": the likeliest cause is
`devProxyRoundTrip.test.ts`'s **declared** probe-then-bind TOCTOU, and **this story tripled the
exposure to it** — four new tests, each starting its own Vite server, taking that file from 5
probe-then-bind windows per run to 9. `deferred-work.md` carries the full entry, the fix shape (bind
port `0` and read the port back, rather than probing and racing) and the warning that must be
respected while fixing it (distinct ports per test are load-bearing for an unrelated undici
keep-alive flake). **Homed on c5-8**, which adds the real-socket integration test in that same file.
It is worth a reviewer's eye on that call: the alternative reading is that it is unrelated
infrastructure noise, and 26 clean runs cannot distinguish the two.

### Dev Notes size self-check (C4 action item R1)

C4's success criterion is Dev Notes **under the 41 KB C4 average**. This story's Dev Notes section
(`### The wire contract you are consuming` through `### References`) is **~14.5 KB** — about a third
of that average, in the epic's largest frontend story. The trigger-gating R1 introduced is what did
it: ten ledger anchors carried IN FULL because the surface triggers every one, and everything else
reduced to one line each.

### Completion Notes List

**What shipped, in one paragraph.** The browser now opens exactly one socket per tab, mints a fresh
single-use ticket for every attempt, backs off 2/4/8/16/30 s against a lost backend, announces
`disconnected` only after sixty seconds AND four observed failures, and keeps retrying behind that
panel forever — so a companion restart is a blip and a recovery needs no reload. It dispatches the
six-kind wire vocabulary through one total switch, re-drives the deck boot and (conditionally) the
system poll on both a reconnect and a system-kind frame, and gives exhausted card ids their attempt
budget back. The dev proxy proxies `/ws` and rewrites `Origin` as well as `Host`.

**Notes on the decisions that were not obvious:**

- **The one-door rule survived intact** (Q1). `posture.test.ts`'s network-door list still reads
  exactly `['src/api/client.ts']`, unedited. `openAgentSocket` lives beside the one `fetch`; the
  loop takes the factory injected and never contains the banned identifier. The door also does the
  DOM→plain-value translation, so `state/socket.ts` sees three callbacks and a `close` and no wire
  parsing at all.
- **`disconnected` is derived, never written into `panel`** (Q3/Q8). Two writers on one field would
  race: with the HTTP half up and the WS half failing, the next poll SUCCESS is a change and would
  overwrite the panel while the socket was still down. `surfaceOf` composes the two opinions
  instead, `PANEL_FOR_REASON` is untouched, and `PanelSourcesAreDisjoint` still holds.
- **"Exhausted" is an announcement, not a stop** (Q2). A true stop would rebuild the
  needs-a-manual-refresh defect three ledger entries record. The loop READS
  `RETRIES_QUIETLY.disconnected` to decide whether to keep scheduling — so the contract is consumed
  rather than paraphrased, and `socket.test.ts` flips the entry in a try/finally and watches the
  behaviour follow.
- **The `delay → mint → open` ordering is structural, not careful.** The ticket TTL and the backoff
  ceiling are both 30 s, so a pre-delay mint hands the upgrade an expired ticket at exactly the
  point in the schedule where there is no slack. There is no code path on which a ticket is minted
  and then waited on: the timer's callback IS the attempt, and the attempt begins with the mint.
  Probe (b) is the proof.
- **`CLIENT_ONLY_STATES` stays type-level, and gained a real reader** (AC 17). The new
  `ClientOnlyState` alias types the `DISCONNECTED_PANEL` constant in both modules that choose a
  panel from a client-side condition, so retargeting either at a wire-sourced panel is a `tsc`
  failure. A runtime membership test was declined because nothing in the app asks that question.
- **Effect ordering in `App.tsx` was not disturbed.** The two measured blocks (`:245-267`,
  `:341-359`, worth ~180 ms of the six-surface layout) keep their relative order; the socket hook is
  a hook call above them, and where the mint lands in the request queue is noted in the comment.

**What this story deliberately did NOT do:** the connection pill (c5-7 — and `copy-tails` asserts
that clause is still unmirrored rather than quietly skipping it), the real-socket integration test
(c5-8), the four agent-view renders (Epic 6), and any coalescing of duplicate `active_deck_changed`
frames (ledgered, low).

### File List

**New**

- `ui/src/state/socket.ts` — the framework-free connect/reconnect loop
- `ui/src/state/socket.test.ts` — 27 tests: schedule, ticket discipline, generations, two gates, dispatch
- `ui/src/state/connection.ts` — the React seam; what each of the loop's three signals means

**Modified — source**

- `ui/src/api/client.ts` — `SESSION_PATH`, `SessionOutcome`, `ticketOf`, `readSessionTicket`, `WS_PATH`, `agentSocketUrl`, `AgentSocketHandlers`, `AgentSocketHandle`, `agentEventOf`, `AGENT_EVENT_KINDS`, `openAgentSocket`; prose reconciliation
- `ui/src/api/schema.ts` — `SessionTicket`, `AgentEvent` (via `paths`), `AgentEventKind`
- `ui/src/state/systemState.ts` — `SystemState.connection`, `applyConnection`, the `mounted` poller slot, `restartPoll`, `restartPollIfStopped`
- `ui/src/state/deck.ts` — `surfaceOf`'s fourth arm, `DISCONNECTED_PANEL`, the `mounted` boot slot, `redriveDeckBoot`; prose reconciliation
- `ui/src/state/cards.ts` — `resetCardAttempts`; prose reconciliation
- `ui/src/components/StatePanel/states.ts` — `ClientOnlyState`, the dw:3500 disposition, the `RETRIES_QUIETLY.disconnected` note
- `ui/src/state/poller.ts` — prose only (the dw:3451 residue closed)
- `ui/src/App.tsx` — `useAgentConnection()` mounted once, with the queue-position note
- `ui/config/devProxy.ts` — `WS_PATTERN`, `WEBSOCKET_PATTERNS`, `ws: true`, the `Origin` rewrite

**Modified — tests**

- `ui/src/api/client.test.ts` — the session reader, the URL builder, the narrower, the socket door
- `ui/src/state/cards.test.ts` — `resetCardAttempts` semantics (8 tests)
- `ui/src/state/deck.test.ts` — the fourth-arm describe; `system()` takes a connection
- `ui/src/state/poller.test.ts` — prose only
- `ui/src/App.test.tsx` — the `/api/session` route in BOTH prefix-routing fixtures, the socket stub, the AC 21 conversion, the family block, two request-count pins
- `ui/tests/devProxy.test.ts` — the `/ws` entry describe (replacing "does not yet proxy /ws")
- `ui/tests/devProxyRoundTrip.test.ts` — real upgrade round trips, both directions
- `ui/tests/copy-tails.test.ts` — the fourth tail paid

**Modified — prose only, behaviour byte-identical**

- `src/companion/app/spa.py`, `src/companion/app/state.py`, `src/companion/app/ws.py`
- `tests/unit/companion/test_spa.py`, `tests/unit/companion/test_ws.py`
- `ui/README.md`
- `plugin/server/src/companion/app/{spa,state,ws}.py` — mirror rebuild, sha256-verified

**Records**

- `_bmad-output/implementation-artifacts/deferred-work.md` — the c5-6 disposition pass
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- this story file

### Change Log

| Date | Change |
| --- | --- |
| 2026-08-08 | All nine open questions ruled by Brad as recommended, before any code |
| 2026-08-08 | Task 0: baselines verified (Python 2,770/1, frontend 1,706/66, `gen:api` a no-op); 27 own-key hits enumerated with dispositions |
| 2026-08-08 | Tasks 1–3: the session reader and socket door, the loop, the wiring |
| 2026-08-08 | Task 4: the family — six ledger entries closed, two closed by ruling, one stands, one re-scoped |
| 2026-08-08 | Task 5: `/ws` proxied with `ws: true` and the `Origin` rewrite; dw:5221 closed |
| 2026-08-08 | Task 6: 106 new tests; twelve R2 firing proofs, all RED through the full suite |
| 2026-08-08 | Task 7: every c5-6 prose prediction fulfilled-and-rewritten or recorded falsified; mirror rebuilt and verified; status → `review` |

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

MERGED via PR #58 into feat/companion-c5 at `eabeb58` (2026-08-08). CI caught one thing local review missed after the fix was pushed: the SPA bundle drift check — src/companion/app/static/ was stale relative to the socket.ts patch (only the plugin mirror had been rebuilt). Fixed in a follow-up commit, CI green, merged. Next: c5-7. PREVIOUSLY — CODE-REVIEWED 2026-08-08 -> done. Chunked review (diff exceeded the single-pass line threshold): Group 1 (UI reconnection core, ui/src/state/{connection,socket,deck,cards,systemState,poller}.ts) got the full three-layer pass (Blind Hunter, Edge Case Hunter, Acceptance Auditor); Group 2 (backend spa/state/ws.py + tests) turned out to be comment/docstring-only — a light self-review cross-checking each prose claim against the shipped code instead, 0 findings; Group 3 (App.tsx, api/client.ts, api/schema.ts, states.ts, devProxy.ts + tests) got the full three-layer pass. Totals across all three: 0 decision-needed, 1 patch applied, 6 deferred, 25 dismissed. HEADLINE, found by Edge Case Hunter in Group 1: socket.ts's fail() ran emit(status) before schedule(next) with nothing guaranteeing the retry timer still got scheduled if the onStatus callback threw — a downstream exception (e.g. a future React render bug, since the system store is subscribed selector-less and re-renders on every write) could permanently and silently halt the reconnect loop, defeating the story's core "never gives up" guarantee. FIXED: schedule(next) now runs in a finally around emit(). Several findings that read as real bugs on first pass turned out to be exact matches for established codebase idioms once checked against surrounding code and were dismissed rather than patched: ticketOf's trim-check-but-return-untrimmed matches namesOf/cardOf/deckOf/activeDeckIdOf identically; the DISCONNECTED_PANEL "duplication" between deck.ts and socket.ts and the mounted-singleton "duplication" between systemState.ts and deck.ts are both explicitly documented in-code as deliberate independent declarations, not oversights. One attempted patch (devProxy.ts's WEBSOCKET_PATTERNS widened to a literal tuple) was reverted after actually testing it broke real compilation — Object.entries() always widens keys to string, so both createDevProxy and devProxy.test.ts's own assertions need the general-string type. 6 deferred to deferred-work.md: a stale connection-status-on-remount edge case (pre-existing pattern, App is documented as the sole permanently-mounted consumer of all three reconnection hooks); a narrow redundant-refetch race between two re-drive triggers; whether the backend actually produces the signals the poll-recovery logic depends on (cross-scope, verified comment-only in Group 2 so not independently confirmed); agentEventOf's unvalidated id/ts/payload fields (latent, becomes actionable when Epic 6 reads them); the agent-event wire-schema equivalence between the POST body and the broadcast frame (cross-language, out of scope here); connection.ts's missing dedicated unit test (coverage depends on App.test.tsx). Verified after the fix: full frontend suite 1,812/1,812 passed (up from Task 0's 1,706 baseline, consistent with new tests), tsc -b --force clean, Python suite 2,770 passed / 1 skipped unchanged from baseline (Group 2 was comment-only, confirmed zero regressions). Next: raise the PR into feat/companion-c5. PREVIOUSLY — DEVVED 2026-08-08 -> review.
