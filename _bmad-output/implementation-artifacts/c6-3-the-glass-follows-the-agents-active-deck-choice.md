---
epic: c6
story: c6-3
work_branch: feat/companion-c6
story_branch: feat/companion-c6-3-glass-follows-choice
depends_on: [c6-2, c5-6, c5-4, c4-2, c4-5]
baseline_commit: 5a2cd39
---

# Story c6-3: The glass follows the agent's active-deck choice

Status: done

<!-- Ultimate context engine analysis completed 2026-08-09 — comprehensive developer guide created.
     Sources: epics-companion-app.md Story 6.3 + Stories 5.1/5.4/3.4/4.5/7.3/7.4, ARCHITECTURE-SPINE
     2026-07-25 (AD-6/AD-16 + Consistency Conventions + residuals), PRD 2026-07-22 (FR-07/11/12,
     NFR-04/05), EXPERIENCE.md/DESIGN.md (UX-DR20/30/31/35/37/42/43/45), shipped code on
     feat/companion-c6 @ 5a2cd39 (ui/src state layer read end to end), c6-2 + c5-6 story records,
     C5 retro (J2, R5), deferred-work ledger (dw:3756, dw:5115/R5, agentEventOf entry). -->

## Story

As Brad watching the browser,
I want the deck view to switch when my agent switches decks,
So that I never have to refresh or click to keep up with the conversation.

## The story in one paragraph

**Most of this story's runtime behaviour already shipped, and the C5 retro says so in writing**
(retro item J2: *"C5's `connection.ts` already re-drives the deck boot on `active_deck_changed`"*).
The socket dispatches the kind (`socket.ts:407`), `connection.ts:96` re-drives the deck boot on
every system event, the boot asks `GET /api/active-deck` **first** — so "never refetch the deck you
are leaving" is satisfied structurally, with no branch and no payload read — a 404 already clears
to `{status:'none'}` (`deck.ts` via AD-16's `deck_not_found` token), and `CardDetail`'s
`deckMemory` effect already releases a pin when a different deck's boards arrive. `App.test.tsx:2424`
is literally titled *"switches decks on active_deck_changed"* and passes. What this story owes is
**proof, not plumbing**: AC-numbered App-level tests for the gaps the shipped suite leaves open —
the deck A → deck B switch (the existing test covers only none → deck), the pin release asserted
*across* that switch, the 404-after-switch path driven from an envelope rather than
`setState`, and one honestly-documented latent state (a pin surviving invisibly across a
deck → no-active-deck interlude). New runtime code lands **only if a test exposes a defect or Brad
rules Q2's fix in**. The two-tab eyes-on observation rides the Epic C6 manual checklist (Block J,
carried by ruling). Expect a tests-only diff; if `ui/src` runtime code does change, the committed
SPA (`npm run build` → `src/companion/app/static/`) and the plugin mirror must be rebuilt.

## Acceptance Criteria

*(Verbatim from `epics-companion-app.md` Story 6.3, lines 2748-2774; annotations in italics.)*

1. **Given** the app is showing the no-active-deck state **When** an `active_deck_changed` envelope
   arrives **Then** the app fetches that deck and renders the deck view (FR-07, AD-6). *(Shipped and
   pinned: `App.test.tsx:2424`. This story re-cites that test against this AC; no new work unless
   review of it finds a hole.)*

2. **Given** the app is showing one deck **When** an `active_deck_changed` envelope arrives for a
   different deck **Then** the app switches to the new deck, and any pinned inspection from the
   previous deck is released. *(The gap: no App-level deck → deck test exists. The release mechanism
   is shipped — `CardDetail.tsx:346-352` clears pin + transients and retargets to the new deck's
   cold-open card when `replacesRememberedDeck(boards)` — but it has never been asserted from an
   envelope. "Released" lands on the new deck's first-card default target, per UX-DR20's "never
   empty while a deck is loaded".)*

3. **Given** an `active_deck_changed` envelope arrives **When** the app handles it **Then** it does
   **not** treat it as `deck_changed` — the distinction is what stops the app refetching the deck it
   is leaving (AD-6). *(Satisfied structurally, not by a branch: the re-drive asks
   `GET /api/active-deck` before any deck fetch, so the old deck's id is never requested. The test
   is a request-log assertion: exactly one `/api/active-deck` call plus one `/api/deck/{new}` call,
   and zero `/api/deck/{old}` calls, per envelope.)*

4. **Given** a `GET /api/deck/{id}` that 404s after the switch **When** the app handles it **Then**
   it clears to the no-active-deck state (FR-11, AD-16). *(Unit-covered in `deck.test.ts:260`; not
   covered end-to-end from a mounted App receiving an envelope. The 404 arrives as
   `{kind:'error', reason:'deck_not_found'}` — status codes are never read, only tokens —
   and maps through `PANEL_FOR_REASON` → `'no-active-deck'` → `{status:'none'}`.)*

5. **Given** several tabs are open **When** the envelope is broadcast **Then** every tab switches
   (UX-DR37). *(All-tabs delivery is backend fan-out, shipped and tested at c5-4 — Story 5.4's AC
   pins "every tab receives it". Client-side there is nothing per-tab to build: each tab runs the
   identical handler this story's tests pin. Satisfaction = c5-4's broadcast test + this story's
   per-client tests, recorded in the Dev Agent Record; the literal two-tab observation is on the
   Epic C6 manual checklist (retro J2, carried by ruling — "open two tabs, ask the agent to switch
   decks").)*

## Tasks / Subtasks

- [x] **Task 0 — Verify the baseline and grep your own key** (AC: all)
  - [x] Confirm branch `feat/companion-c6` at/after `5a2cd39`; cut story branch from it.
  - [x] `uv run pytest -m "not integration"` → expect **2,874 passed / 1 skipped / 55 deselected**
        (2,875 collected — the c6-2 merge baseline). This story should not move these numbers.
  - [x] `cd ui && npm test` → expect **1,868 passed / 69 files** (the c6-2 baseline). Run from an
        **uppercase drive letter** (`C:\…`) — see Landmine 9.
  - [x] `grep -rn "c6-3" src/ ui/src/ tests/ scripts/ _bmad-output/implementation-artifacts/deferred-work.md`
        — expect **zero code hits** (verified at story creation); records
        (retro J2, c6-2 story file, sprint-status) are records, not code. Reconcile any new hit.
  - [x] Read end to end before writing anything: `ui/src/state/connection.ts` (113 lines — the
        composition seam), `ui/src/state/socket.ts` dispatch (`receive`, :402-430),
        `ui/src/state/deck.ts` (`createDeckBoot`, `redriveDeckBoot`, `surfaceOf`),
        `ui/src/state/inspection.ts`, `ui/src/containers/CardDetail/deckMemory.ts` +
        `CardDetail.tsx:346-352`, `ui/src/App.test.tsx` harness (:34-417) and the active-deck
        block (:2399-2533).
- [x] **Task 1 — The deck → deck switch, with the pin released** (AC: 2)
  - [x] New App-level test beside `App.test.tsx:2424`'s block: boot into deck A (use the
        established `booting(activeDeck(A), deckDetail(...))` + `answering(...)` harness), push
        `active_deck_changed` via the `push(kind, payload)` helper, answer the re-drive with
        active-deck = B and deck B's detail; assert the grid now shows B's cards and the request
        log shows the switch asked `/api/active-deck` then `/api/deck/B`.
  - [x] Pin a card in deck A first (click a tile — the real interaction, not
        `useInspectionStore.setState`), then switch. Assert the detail panel targets **B's
        cold-open card** (first card of the first type group), not A's pinned card — the release
        made visible. (Mechanism: `CardDetail`'s `[boards]` effect fires `clearPin()` +
        `clearTransientTargets()` + `setDefaultTarget(coldOpenTargetOf(B))`; the one-frame stale
        render before the effect is the shipped, accepted behaviour — assert the settled state,
        do not fight the frame.)
  - [x] The none-interlude sequence (Q2's documentation half, if ruled as recommended): pin in
        deck A → envelope whose re-drive 404s (A deleted) → no-active-deck panel → second envelope
        lands deck B → assert the target is B's cold-open card, never A's pin. This pins the latent
        stale-pin state as self-healing rather than fixing it.
- [x] **Task 2 — The distinction made mechanical** (AC: 3)
  - [x] Request-log assertion on the Task 1 switch test (or its own test if clearer): per envelope,
        exactly one `/api/active-deck` read, exactly one `/api/deck/{B}` read, **zero**
        `/api/deck/{A}` reads. Account for the format-check call the `deckId` change legitimately
        fires (Landmine 4) — exclude it from the deck-read count rather than loosening the assert.
  - [x] Confirm (do not duplicate) the duplicate-frame idempotence pin at `App.test.tsx:2445`
        (three same-id frames → three cheap re-drives, one socket) still covers the "fires on every
        set" contract; cite it in the Dev Agent Record against AC 3.
- [x] **Task 3 — 404 after the switch, end to end** (AC: 4)
  - [x] App-level: showing deck A → envelope → active-deck read answers B → `/api/deck/B` answers
        `{kind:'error', reason:'deck_not_found'}` → assert the left column is the
        `no-active-deck` StatePanel listing available decks (`system.decks`), the right-column
        deck panels are gone, and the skip link is withdrawn (UX-DR31 — assert its absence, the
        cheap half; full keyboard-floor coverage stays Epic 4's).
  - [x] Assert no retry storm: the boot lands `'none'` and stops (`RETRIES_QUIETLY['no-active-deck']`
        is `false` — recovery is the agent's next set, not a poll).
- [x] **Task 4 — Multi-tab: record, don't build** (AC: 5)
  - [x] No client code: write the AC-5 satisfaction note in the Dev Agent Record — c5-4's
        broadcast fan-out test (backend, every registered connection) + this story's per-client
        pins + spine residual "divergence between tabs is accepted" (`ARCHITECTURE-SPINE.md:496`).
  - [x] Add the two-tab observation line to the Epic C6 manual checklist entry if one is being
        accumulated in `sprint-status.yaml` (retro J2 wording: "open two tabs, ask the agent to
        switch decks"); otherwise record where it lives.
- [x] **Task 5 — Planted red, run the c5-7 way** (AC: 1-4; R5 per Q3's ruling)
  - [x] Plant: neuter the system-event action in `connection.ts` (make `onSystemEvent` a no-op —
        the exact regression dw:3756 described: "an `active_deck_changed` arrives on the wire and
        nothing listens"). Expected reds: this story's new switch tests AND the shipped
        `App.test.tsx:2424`/`:2445`/`:2509` block — confined to the path.
  - [x] Run the **full** `npm test` by hand from an uppercase drive, check the collected count
        (1,868 + this story's additions) before scoring the run, paste the red list into the Dev
        Agent Record, revert. Record what the guard compares (the surface the user sees after an
        envelope) and what it cannot see (the real WebSocket; `FakeSocket` is not the wire — c5-8's
        one real-socket test owns that, and it is push-shaped, untouched here per AD-10).
- [x] **Task 6 — Prose/ledger reconciliation, gates, mirror**
  - [x] `deferred-work.md`: annotate the `agentEventOf` kind-only-validation entry (c5-6 Group 3,
        ledger ~:109) **not triggered by c6-3** — this story reads no payload fields, by ruling;
        the entry stays open for the first story that does (c6-4+). Do not close it.
  - [x] Verify dw:3756 (already ✅ CLOSED by c5-6, named at `systemState.ts:231`) needs no edit;
        this story's tests are its firing proof — add one line to its entry only if the ledger
        convention asks for it.
  - [x] No forward-looking cross-module prose (R2): nothing in test names or comments about c6-4+
        views or c7-3's refetch beyond what already exists.
  - [x] Gates: `cd ui && npm run lint && npm run typecheck && npm test && npm run format:check`;
        frontend suite strictly larger than 1,868. Python suite untouched at 2,874 (run it once to
        prove it). Governance suites must stay green untouched: `tests/store-writes.test.ts` (one
        writer per store), `tests/posture.test.ts` (network door = `client.ts` only),
        `ui/tests/shell.test.ts` (no fetch/zustand/setState in containers).
  - [x] **Only if any `ui/src` runtime file changed** (Q1/Q2 rulings may keep this at zero):
        `npm run build` (vite writes `src/companion/app/static/` with new hashed bundle names,
        `emptyOutDir` — never hand-edit), commit the regenerated static artifact, then
        `uv run python scripts/build_plugin.py` and sha256-verify the mirrors. Tests-only diff →
        no rebuild, and say so in the record. **N/A — tests-only diff, confirmed by
        `git diff --stat`: no `ui/src` runtime file changed, so neither artifact moved.**
  - [x] Record the Dev Notes KB self-check in the Dev Agent Record (target band: 10-20 KB).
  - [x] Set story status to `review` and **STOP** — Brad runs the three-layer review and raises
        the PR.

### Review Findings

Three-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor) of the
uncommitted `ui/src/App.test.tsx` + ledger diff, 2026-08-09. 0 decision-needed, 0 patch, 2 defer,
13 dismissed as noise (pre-existing conventions, already-ruled scope boundaries Q1–Q5, or cosmetic
documentation nits that don't affect what the tests actually assert). Acceptance Auditor found zero
AC violations and independently verified every code-mechanism claim in the diff and Dev Agent Record
against the live source (`deck.ts`, `connection.ts`, `states.ts`, `deckGroups.ts`, `deckMemory.ts`,
`CardTile.tsx`) — all confirmed true.

- [x] [Review][Defer] AC 4's new test covers only the `deck_not_found` refusal reason; a mid-session
      `active_deck_changed` re-drive that 404s with a *different* reason (e.g.
      `database_not_initialized`, whose `RETRIES_QUIETLY` is `true` — the opposite of
      `no-active-deck`'s `false`) is untested from a mounted App — only at the store/mapping level
      (`deck.test.ts:311`, `states.ts:262-272`). [ui/src/App.test.tsx:2921-2976] — deferred,
      pre-existing (out of AC 4's literal scope, which is the 404/`deck_not_found` case; this gap
      predates c6-3 and isn't claimed closed by it).
- [x] [Review][Defer] The Q2 none-interlude test (pin-outlives-a-clear) asserts pin release and
      healing but, unlike Task 1's switch test, includes no request-log sweep for stray fetches of
      the abandoned deck during the interlude — the story's own "sweep every request, not just the
      cited path" discipline (the c6-2 Greptile lesson) is applied asymmetrically across the three
      new tests. [ui/src/App.test.tsx:2978-3030] — deferred, pre-existing pattern (not required by
      AC 2's wording, which Task 1's test already proves; optional hardening only).

## Dev Notes

### What is already shipped (verified at story creation — modify only where a ruling says so)

The entire event path exists and is tested. Read it as the thing you are *pinning*, not building:

- **`ui/src/state/socket.ts`** — framework-free socket core, effects injected. `receive()`
  (:402-430) is the one kind-switch: `active_deck_changed` and `deck_changed` both call
  `onSystemEvent(event.kind)` and return; the four view kinds are dropped unread; `default` is a
  `never` (a 7th kind is a compile error). Unreadable frames → `null` → ignored, socket stays open.
  Every callback is generation-guarded. `SystemEventKind` (:179) is a compiler-checked subset of
  the generated union. The docstring at :200-208 keeps the two kinds reported **separately** "so
  the day one of them needs a different action there is a parameter here to switch on" — **this
  story is not that day** (see Ruled #2).
- **`ui/src/state/connection.ts`** — the composition point and the only file that would change if
  a defect were found. `useAgentConnection()` (App is the sole consumer): `onStatus:
  applyConnection`; `onReconnected: restartPoll + resetCardAttempts + redriveDeckBoot`;
  `onSystemEvent: () => { redriveDeckBoot(); restartPollIfStopped() }` (:96-108). The kind
  parameter is **deliberately unread** and the payload's `deck_id` is **deliberately never read**
  (:49-57) — the re-drive asks `GET /api/active-deck` first, so the server's slot is the single
  source of truth and AC 3 is structural.
- **`ui/src/state/deck.ts`** — zustand slice (`{ deck: DeckState }`, wrapped deliberately —
  zustand merges). `DeckState = booting | none | deck{detail, boards} | refused{reason, panel}`.
  `createDeckBoot` run(): `readActive()` → unreachable ⇒ `'none'`; error ⇒ refusal panel; null/blank
  id ⇒ `'none'` (no second request); else `readDeck(id)` → unreachable ⇒ `'none'`, error ⇒
  `deckRefusalState(reason)` — and `PANEL_FOR_REASON.deck_not_found === 'no-active-deck'` with
  `stateForPanel('no-active-deck')` ⇒ `{status:'none'}`, which is AC 4's whole mechanism; else
  `seedCardSummaries` + settle `{status:'deck'}`. `redriveDeckBoot()` (:515-519) is the
  cross-module "the active deck may have changed" verb: `stop()` (generation bump — an in-flight
  old fetch is discarded, latest-wins) then `start()`. `surfaceOf(deck, system)` picks the left
  column: down-panel → deck → refusal → system panel.
- **`ui/src/state/inspection.ts`** — flat zustand store. `targetIdOf = pinnedId ?? transient ??
  defaultId`. Release = `clearPin()` + `clearTransientTargets()`; retarget = `setDefaultTarget
  (coldOpenTargetOf(boards))` (first card of first type group).
- **`ui/src/containers/CardDetail/deckMemory.ts`** + **`CardDetail.tsx:346-352`** — the shipped
  release: a `[boards]` effect fires `replacesRememberedDeck(boards)` (true iff a *different*
  non-null boards reference was remembered) → `clearPin(); clearTransientTargets()`, then always
  `setDefaultTarget(coldOpenTargetOf(boards))`. Boards identity is the **reference** minted once
  per completed boot (`boardsOfDeck`), so any completed re-boot releases — including a same-deck
  re-set (accepted cost, documented in `deckMemory.ts:9-11`; `CardDetail.test.tsx:646-670` pins
  A→B, `:672` pins same-deck remount clears nothing at the memory level).
- **`ui/src/api/client.ts`** — the one network door. `agentEventOf` (:701-716) validates **only**
  the `kind` discriminant against `AGENT_EVENT_KINDS` (:662-669, `satisfies Record<AgentEventKind,
  true>`); payloads are never touched. `readDeck` 404 arrives as `{kind:'error',
  reason:'deck_not_found'}` — tokens, never status codes (AD-16). `readActiveDeck` /
  `readDeck` / `readFormatCheck` / `readSessionTicket` are all total.
- **`ui/src/App.tsx`** — `useSystemState()` (owns poll) → `surfaceOf(useDeckState(), system)` →
  `useAgentConnection()` (owns socket); declaration order documented load-bearing (:168-185).
  A switch changes `deckId`, so the format-check effect (`[deckId, emptyDeck]` dep, :381) already
  refetches for the new deck — that is the dep's declared "forward contract" (:349) working, not a
  c7-3 encroachment.

### Ruled — settled, do not re-derive

1. **The payload's `deck_id` is never read** (`connection.ts:49-57`, shipped ruling). The re-drive
   asks the server which deck is active. Reading `payload.deck_id` and fetching it directly would
   reintroduce the conflation the contract warns about (`types.d.ts:377-386`) and make the nullable
   payload (`deck_id?: string | null`, the cleared case — unreachable today, no clear verb exists,
   dw "no way to clear" entry) a live branch. Structural handling covers null for free.
2. **No kind branch in `connection.ts`.** Both system kinds map to the same action today and AC 3
   is satisfied by *request order*, not by a branch. The seam (the unread `kind` parameter) is for
   c7-3, whose `deck_changed` refetch genuinely differs (refetch-in-place, shimmer, coalescing —
   UX-DR35). Adding the branch now would be building c7-3's story.
3. **Duplicates are expected and stay idempotent — no dedupe.** The broadcast fires on **every**
   set including a same-id rewrite (Q10, Brad 2026-08-07, `contracts.py:958-962`); a duplicate
   costs one idempotent re-drive. `App.test.tsx:2445` pins three-for-three.
4. **`deck_changed` behaviour is Epic 7's** — refetch (c7-3), teardown rules/shimmer (c7-4),
   announcements (c7-5), deletion mid-view (c7-6). This story adds **no announcement** on a switch:
   UX-DR45's "Deck updated — N cards" is defined for coalesced *refetches*; no artefact legislates
   a switch announcement (requirements-extraction flag #4). The connection pill's deck-name change
   is whatever c5-7 shipped — observe, don't touch.
5. **AD-16's token mapping is the 404 mechanism** — `deck_not_found` → no-active-deck is a 1:1
   token→state rule; status codes are never read client-side. The backend still reporting a dead id
   after the clear (the client will not PUT to fix it) is recorded, accepted residue
   (`deck.ts:251-258`): the next boot asks and clears again.
6. **AD-6's spine text omits `active_deck_changed`** — the enum text still says system signals =
   `(deck_changed)`. Story 5.1 (:2397-2398) and the epics addendum ledger (:3312) are the contract
   sources; the spine amendment is homed at Epic 8 (C5 retro ruling). Cite 5.1, don't "fix" the
   spine.
7. **Cross-tab divergence is accepted, not solved** (`ARCHITECTURE-SPINE.md:496-497`); all-tabs
   delivery is `ws.py` fan-out, c5-4's tested AC. Nothing per-tab exists to build.
8. **One writer per store / one network door / no store access in containers** — enforced by
   `tests/store-writes.test.ts:77` (the `STORES` table), `tests/posture.test.ts`,
   `ui/tests/shell.test.ts`. A test-only story cannot red these; a Q2 fix placed wrong could.
9. **App is the sole, permanently-mounted consumer** of `useSystemState`/`useDeckState`/
   `useAgentConnection`; remount is disclaimed unsupported (dw c5-6 Group 1). Don't write a
   remount test and call its failure a bug.
10. **Merge ≠ release**: story PR targets the `feat/companion-c6` umbrella (Greptile per story);
    no tag/CHANGELOG until c8-4.

### The gaps this story closes (from the shipped-code survey)

| # | Gap | Where it is half-covered today |
|---|---|---|
| 1 | Deck A → deck B switch at App level | `App.test.tsx:2424` covers none → deck only |
| 2 | Pin release asserted across an envelope-driven switch | `CardDetail.test.tsx:646` drives boards props directly, no envelope, no App |
| 3 | 404-after-switch from a mounted App | `deck.test.ts:260` drives the boot readers directly |
| 4 | The none-interlude stale pin, pinned as self-healing | Nothing — found at story creation (see Q2) |
| 5 | AC-numbered citations tying the shipped tests to this story's ACs | Tests exist but predate the ACs |

### Landmines specific to this story

1. **The `answering()` fetch-mock's `/format-check` branch must stay first** (`App.test.tsx:342`)
   — path routing is ordered; `/api/deck/` is a prefix of the format-check path's shape.
2. **`push(kind, payload)` (`App.test.tsx:119-124`) is the envelope helper** — it serialises
   `{kind, id, ts, payload}` into `onmessage`. Use it; don't hand-roll frames per test.
3. **Fake timers everywhere in `App.test.tsx`** (`vi.useFakeTimers()` in `beforeEach`, `settle()`
   = `advanceTimersByTimeAsync(0)`); `beforeEach` resets **all** stores + fixtures +
   `sockets.length = 0` + `vi.stubGlobal('WebSocket', FakeSocket)`. Copy the block's discipline;
   a missing store reset bleeds state across tests silently (module-level zustand).
4. **A switch legitimately fires a format-check fetch** — the `[deckId]` dep. Your request-log
   assertions must count `/api/deck/{id}` reads and `/api/active-deck` reads *specifically*, not
   "total fetches", or the assert is flaky against an unrelated, correct call.
5. **Card hydration fires on `[detail]`** (App effect :289) — deck B's cards get a hydration
   sweep. Same discipline as Landmine 4: assert by path, not by count of everything.
6. **The pin release runs in an effect after first render** — one frame of the old target on the
   new deck is shipped, accepted behaviour (`CardDetail.test.tsx:646` precedent). Assert the
   settled state (`vi.waitFor` / after `settle()`), never the interim frame.
7. **What the screen shows *during* the re-drive is unlegislated** (requirements flag #2:
   UX-DR35's no-teardown rule governs same-deck refetch only, and it is c7-4's story). Observe
   what the shipped boot does across a switch — whether the old deck holds until B's state lands
   or a `booting` interim shows — **record it in the Dev Agent Record, change nothing** (Q4).
8. **Vitest globals are OFF** — import `describe/it/expect/vi` in every new file (existing suites
   show the shape). `ui/src/test-setup.ts` is 13 lines and deliberately holds no shared helpers —
   suites roll their own; don't widen it.
9. **Windows false-red**: a subprocess/manual `npm test` from a **lowercase** drive letter
   (`c:\…`) resolves no vitest config and reports ~67 failed suites / "no tests" (recorded at
   c5-7, carried in dw:5115's region). Uppercase drive, and validate the **collected count**, not
   the exit code, before scoring any run — especially the Task 5 planted red.
10. **`src/companion/app/static/` and `plugin/**` are build artifacts** — vite `emptyOutDir` eats
    hand edits; `scripts/build_plugin.py` mirrors. Tests-only diff → neither moves; runtime diff →
    both rebuilt, sha256-verified (Task 6).
11. **`resetDeckState()` is tests-only by its own docstring** (`deck.ts:182` — "Not a production
    `deck_changed` handler"). If a Q2 fix is ruled in, it goes through the store's own writer
    module (`deck.ts` owns `deck`; `inspection.ts` owns inspection actions), never through a
    container calling `setState` (governance suites red it).
12. **The `agentEventOf` kind-only-validation ledger entry is NOT yours to close** — it "becomes
    actionable when Epic 6 builds the agent views and reads those fields". This story deliberately
    reads no fields; annotate not-triggered (Task 6) and leave it for c6-4+.

### Testing requirements

- All new tests are App-level in `App.test.tsx` (the established home for envelope-driven surface
  tests — the harness at :34-417 is the reuse; a new file would duplicate `FakeSocket`,
  `answering`, `booting` wholesale for no isolation gain). Store-level additions only if an App
  assert genuinely can't reach a branch.
- Every request-log assertion pairs the surface assert with a *why* message naming the AC (house
  style from c6-1/c6-2's request-count discipline, translated to fetch logs: `callsTo(path)` /
  `deckDetailCalls()` helpers exist).
- Planted red: Task 5's shape — full run, collected count validated, reds listed, reverted. The
  vitest probe harness (R5) does not exist; Q3 rules how this story runs without it.
- Suite arithmetic recorded before/after: frontend baseline **1,868 passed / 69 files** — must
  grow; Python baseline **2,874 passed / 1 skipped / 55 deselected (2,875 collected)** — must not
  move.
- Do not touch: `test_live_backend.py` (AD-10's exactly-one real-socket test, push-shaped),
  `socket.test.ts`'s dispatch block (already pins kind separation at :599-675 — cite, don't
  duplicate), the governance suites.

### Previous-story intelligence (c6-2, merged 2026-08-09 via PR #64)

- **The Greptile lesson is now a standing memory: grep for the whole pattern, not the cited
  line.** c6-2's review patched an unbounded echo on one branch; Greptile found the same defect on
  the other three post-merge. For this story: any assert you write about "the old deck is never
  refetched" should sweep *every* fetch path (`callsTo` on the full log), not just the one the AC
  names.
- **Prose-ripple honesty**: c6-2's wire extension falsified three shipped docstrings it had to
  rewrite. This story's analogue is smaller — new tests citing ACs — but if you touch
  `connection.ts` prose at all, its :49-57 "deliberately unread" block must stay truthful.
- **The ripple sweep found 5 claim sites where the story predicted 2** (R1 lesson, twice now).
  This story's countable claim is the frontend suite size; grep any place that states it if the
  number appears outside the story records (none known at creation).
- Dev Notes 16.8 KB landed in-band; keep this story's there too.
- c6-2's record explicitly scoped `ui/src` out with "(the glass following the choice is c6-3)" —
  this story is that promise's redemption; its own record should close the loop by citing c6-2's
  line.

### Project structure notes

- **Expected diff: `ui/src/App.test.tsx` only** (plus records: this story file,
  `deferred-work.md` annotation, `sprint-status.yaml`). No new files anticipated.
- Possible additions if rulings go the other way: `ui/src/state/deck.test.ts` (a store-level row),
  a Q2 fix in `inspection.ts`/`CardDetail.tsx` + rebuilt `src/companion/app/static/` + `plugin/`
  mirrors.
- Never: `src/**` Python (no backend change in this story), `ui/src/api/**` (generated),
  `test-setup.ts` widening, hand edits under `static/` or `plugin/`.

### References

- Story + epic: `_bmad-output/planning-artifacts/epics-companion-app.md` — Story 6.3 (2748-2774),
  Epic 6 header (2664-2669, 891-903), Story 5.1 (2397-2398), Story 5.4 (2509-2519), Story 3.4
  (1714-1746), FR-07 (64-66), FR-11 (78-81), FR-12 (83-87), NFR-04 (153-155), NFR-05 (157-160),
  coverage map (737, 741-742), AD-6 entry (226-229), AD-16 entry (257-267), addendum ledger (3312),
  UX-DR20 (442-448), UX-DR30 (500-504), UX-DR31 (506-523), UX-DR33 (543-547), UX-DR35 (557-562),
  UX-DR37 (570-574), UX-DR42 (653-660), UX-DR43 (662-664), UX-DR45 (673-677).
- Architecture: `…/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md` — AD-6
  (159-171), AD-16 (329-352), state conventions (360), capability map row E (472), cross-tab
  residual (496-497).
- UX: `…/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md` — no-active-deck copy (63), pill
  deck-name (74), pin semantics (87), refetch rules (104), State Patterns rows (112-132),
  announcements (153-159), latency contract (165-169).
- Shipped code (all `ui/src`): `state/socket.ts` (:179, :200-208, :402-430), `state/connection.ts`
  (:49-57, :84-113), `state/deck.ts` (:118-150, :234-273, :317-400, :481-486, :513-519),
  `state/inspection.ts` (:210, :263-287, :317), `state/systemState.ts` (:231, :243),
  `containers/CardDetail/deckMemory.ts` + `CardDetail.tsx` (:346-352), `api/client.ts` (:662-669,
  :701-716, :865-906), `api/types.d.ts` (:358-391), `App.tsx` (:166-186, :289-292, :319, :349,
  :381-388, :475-489), `App.test.tsx` (:34-417 harness, :2399-2533 active-deck block),
  `CardDetail.test.tsx` (:646-672), `state/deck.test.ts` (:260-354), `state/socket.test.ts`
  (:599-675).
- Records: `c6-2-…md` (esp. :37-39, :426, :596), `c5-6-…md`, `epic-c5-retro-2026-08-09.md` (J2 at
  :123, R5 at :80/:98-99), `deferred-work.md` (dw:3756 region at `systemState.ts:231`; the
  `agentEventOf` entry ~:109; R5/dw:5115 at :96-99 and :5225-5235; the no-clear-verb entry
  :2804-2816).

## Open questions for Brad (recommendations first — rule before code)

1. **Confirm the scope: this is a test-and-pin story.** The runtime behaviour shipped at
   c5-6/c4-2/c4-5 and the retro records it; the value left on the table is proof (the four gaps in
   the table above) and honest documentation. **Recommend: yes — tests-only diff, no runtime code
   unless a test exposes a real defect**, which keeps the SPA static artifact and plugin mirrors
   unmoved. *Alternative:* treat any gap as a defect requiring code, which would be building past
   the ACs.
2. **The none-interlude stale pin: accept-and-pin, or fix?** Found at story creation: the pin
   release lives in `CardDetail`'s effect, which only runs while a deck surface is mounted. Path
   deck A (pinned) → 404 clears to no-active-deck → `CardDetail` unmounts *without* clearing → the
   store keeps A's `pinnedId` invisibly (right column is gone) until any next deck's boards arrive,
   when the shipped release fires before anything stale is settled-visible (one accepted interim
   frame, same as every switch). **Recommend: accept + pin with Task 1's none-interlude test** —
   the state is invisible while it exists and self-heals at the exact moment it could matter; a
   fix would need a second release site (a panel-fall effect) for zero user-visible gain.
   *Alternative:* clear the pin when the surface falls to a panel — small, but it adds a writer
   path the governance suites scrutinise and buys nothing visible.
3. **R5 (the vitest probe harness) is owed "before Epic 6's first frontend story" — this is that
   story.** The ledger's own value case: c5-7 ran fifteen frontend plants by hand; three of the
   five recorded harness lies are frontend-specific. But this story needs roughly **one** plant,
   not fifteen. **Recommend: run Task 5's single plant the manual c5-7 way (full run, collected
   count checked, uppercase drive) and leave R5 open, unowned by this story** — building the
   harness inside a tests-only feature story is the "tool change riding a feature diff" c5-6
   declined. *Alternative:* build R5 first as its own change; say so and it precedes this branch.
4. **The switch-transition surface is unlegislated — observe and record, or specify?** No artefact
   says what shows during the one-fetch gap of a deck→deck switch (UX-DR35's no-teardown rule
   covers same-deck refetch, homed c7-4). **Recommend: the dev agent observes what the shipped
   boot actually does across a switch, records it in the Dev Agent Record, and changes nothing**
   — c7-4 is where teardown/shimmer rules get built, and a switch to different content has no
   stale-content honesty problem. *Alternative:* legislate now (e.g. old deck holds until B
   lands), which risks pre-building c7-4.
5. **AC-5's satisfaction shape.** All-tabs switching is backend fan-out (c5-4, tested) plus
   identical per-tab handling (this story's tests); the literal two-tab observation rides the Epic
   C6 manual checklist per your Block-J ruling. **Recommend: record that chain in the Dev Agent
   Record as AC-5's evidence and add the J2 line to the checklist accumulator** — no new
   client code, no new backend test. *Alternative:* a jsdom two-instance test, which would fake
   the fan-out it claims to prove.

## Dev Agent Record

### Agent Model Used

`claude-opus-5` (Claude Opus 5), via the `bmad-dev-story` skill, 2026-08-09.

### Rulings received before code (all five, as recommended)

Brad ruled all five open questions **as recommended** on 2026-08-09, before any file was written:

| Q | Ruling | Consequence for the diff |
|---|--------|--------------------------|
| Q1 | Tests-only diff | No `ui/src` runtime file changed → SPA static artifact and plugin mirrors unmoved |
| Q2 | Accept + pin the none-interlude stale pin | The third test documents it; no second release site built |
| Q3 | Manual plant the c5-7 way, R5 stays open | One plant, full run, collected count validated; R5 unowned by this story |
| Q4 | Observe and record, change nothing | Recorded below; no transition behaviour legislated (stays c7-4's) |
| Q5 | Record the AC-5 evidence chain | No jsdom two-instance test; no client or backend code |

### Debug Log References

**Baselines, both confirmed before writing anything (Task 0).** Python **2,874 passed / 1 skipped /
55 deselected** in 206 s. Frontend **1,868 passed / 69 files**. `grep -rn "c6-3"` over `src/`,
`ui/src/`, `tests/`, `scripts/` and `deferred-work.md`: **zero hits**, exactly as story creation
predicted. Branch `feat/companion-c6` at `5a2cd39`, matching the story's `baseline_commit`.

**The frontend baseline's first run was a RED, and it was the known flake rather than a regression.**
The cold run reported **1 failed / 1,867 passed** in `ui/tests/lint-gates.test.ts`
(`lintBothFixtures`) with a setup phase of **125.50 s**. That is the same failure c6-2's record
already documents ("a cold-start timeout in a test that shells out to eslint"), and it reproduced
c6-2's diagnosis exactly: the file alone is **27 passed / 27**, and the warm full run is
**1,868 / 69** with setup at **10.95 s** — a 11× setup difference on identical code. Recorded here
rather than silently re-run, because that is now twice this flake has cost a baseline run and the
second sighting is what makes it a pattern instead of an anecdote.

**Task 5 — the planted red.** Plant: `onSystemEvent` in `ui/src/state/connection.ts` reduced to a
no-op body, which is dw:3756's regression verbatim — *"an `active_deck_changed` arrives on the wire
and nothing listens."* Full `npm test`, uppercase drive (`C:\…`), **collected count validated at
1,871 before the run was scored** (Landmine 9's discipline: a lowercase-drive false red reports
"no tests", not a real count). Result — **7 failed / 1,864 passed (1,871)**, 1 file:

```
× switches decks on active_deck_changed — the event that had no listener (AC 11)          [shipped :2424]
× costs one idempotent refetch per duplicate active_deck_changed (AC 12)                  [shipped :2445]
× refetches on deck_changed, and ignores the four agent-view kinds (AC 11)                [shipped]
× recovers the stalled panel when the socket says something moved (AC 15)                 [shipped :2509]
× switches deck → deck, releases the old deck’s pin, and never asks for the deck it left  [NEW, AC 2+3]
× clears to the no-active-deck state when the deck the agent chose 404s                   [NEW, AC 4]
× heals a pin that outlived a no-active-deck interlude …                                  [NEW, AC 2, Q2]
```

All three new tests fired, and so did the four shipped tests on the same path — the story predicted
three of those four (`:2424`, `:2445`, `:2509`); the fourth (`deck_changed` / agent-view kinds) is
consistent, since `deck_changed` routes through the same neutered callback. Nothing outside the
event path moved: 68 of 69 files stayed green. Plant reverted and verified with
`git diff --exit-code ui/src/state/connection.ts` → clean.

**What the guard compares:** the surface a human sees after an envelope arrives — rendered deck
heading, grid tiles, detail-panel target, state panel, skip link — plus the request log the switch
produced. **What it cannot see:** the real WebSocket. `FakeSocket` is the transport stub, so a frame
that never arrives on a real wire is invisible here; c5-8's single real-socket test owns that per
AD-10 and is push-shaped and untouched. It also cannot see rendered pixels (jsdom evaluates no
stylesheet) or genuine cross-tab delivery.

**Q4 — the switch-transition surface, observed and recorded, not legislated.** The answer came from
the code rather than from a test, and it is stronger for it: `redriveDeckBoot()` is
`mounted.stop(); mounted.start()` (`deck.ts:515-519`), and **neither of those writes the store** —
`start()` only sets `live`, bumps the generation and calls `run()`. The new state is written by
`settle()` once *both* awaited reads have returned. So across a deck→deck switch **the old deck
holds on the glass until deck B's state lands, atomically; there is no `'booting'` interim and no
teardown to a skeleton** — and that is true regardless of network latency, not an artifact of a fast
fixture. A throwaway probe corroborated it (no `.state-panel` ever present mid-switch) and was
deleted rather than committed, because pinning unlegislated behaviour is how c7-4's story gets
pre-built. **Changed nothing.**

### Completion Notes List

**This story is proof, not plumbing, and the diff says so: `ui/src/App.test.tsx` only.** Q1's ruling
held all the way through — no test exposed a defect, so no runtime code was written, and therefore
neither `src/companion/app/static/` nor `plugin/**` was rebuilt. c6-2's record scoped `ui/src` out
with *"(the glass following the choice is c6-3)"*; this closes that promise.

**Three new tests, closing four of the five gaps in the story's table.** All in a new
`describe('the glass follows the agent's active-deck choice (c6-3, …)')` at the end of
`App.test.tsx`, placed there to keep the file's story-chronological order (c3-9 → c4-* → c5-6 →
c5-7 → c6-3) rather than interleaved with c5-6's block.

1. **`switches deck → deck, releases the old deck's pin, and never asks for the deck it left`**
   (AC 2 + AC 3). Gap 1 and gap 2. Boots deck A, pins a card by **clicking its tile** (the real
   c4-5 gesture, not a `setState`), pushes `active_deck_changed`, and asserts the settled surface is
   deck B with the pin released onto B's own cold-open card.
2. **`clears to the no-active-deck state when the deck the agent chose 404s`** (AC 4). Gap 3, walked
   from a mounted App instead of from `deck.test.ts:260`'s direct reader drive.
3. **`heals a pin that outlived a no-active-deck interlude …`** (AC 2, Q2). Gap 4 — the state found
   while writing this story, ruled accepted and now documented.

**The pin test's one real design decision: pin the SECOND tile, not the first.** `Llanowar Elves` is
already deck A's cold-open target, so a pin on it agrees with the default target — and after the
switch no assertion could tell a *released* pin from a *surviving* one. `Forest` disagrees with the
default, so it can only still be showing if the release failed. Without that choice the whole test
is vacuous while looking identical.

**AC 3 is asserted as a request log, because it is structural rather than branched.** Per envelope:
exactly one `/api/active-deck` read, exactly one `/api/deck/{B}`, and **zero** `/api/deck/{A}`.
Deck reads are counted by **exact path equality**, not prefix — a switch legitimately fires
`/api/deck/{B}/format-check` (`App.tsx`'s `[deckId, emptyDeck]` effect, Landmine 4), and a prefix
count would fold the two together and make the assert flaky against a correct call.

**c6-2's Greptile lesson applied rather than quoted.** That review patched an unbounded echo on the
one branch the finding cited and left three siblings open, which Greptile found post-merge. The
analogue here: the AC names the *deck read*, so asserting only that path would repeat the mistake in
miniature — the format check and the hydration sweep are deck-scoped requests too. So the test
sweeps **every** request made since the envelope for deck A's id
(`expect(switchPaths.filter((p) => p.includes(ATRAXA_DECK_ID))).toEqual([])`), not just the one path
the AC mentions.

**Two non-vacuity guards were added deliberately.** (a) The "no retry storm" claim is two zeroes,
and *a torn-down app also makes zero requests* — so the test additionally asserts the panel is still
visible and the socket still open and unclosed. Quiet because settled, not quiet because gone.
(b) The `toEqual([])` sweep is non-vacuous by construction: its sibling asserts
`detailReadsOf(switchPaths, ARABELLA_DECK_ID) === 1`, which proves the log is non-empty.

**Found while writing: the file's `beforeEach` resets four stores and misses two.** It resets the
system, deck, card and format-check stores, but **not** the inspection slice and **not**
`deckMemory`'s module-scope `lastBoards`. Every existing test survives that because a completed boot
releases a stale pin on its way in — which is precisely the mechanism these three tests exist to
observe, so inheriting it would have made them assert their own premise. Fixed with a **nested**
`beforeEach` calling `resetInspection()` + `resetDeckMemory()`, scoped to this describe rather than
widened into the shared block: this is the only block that needs a genuine cold open, and
re-baselining 69 files for one story's benefit is the wrong trade. Both verbs are exported
"for tests" by their own docstrings.

**Deck B is real, and it had to be.** Every fixture in this file until now was one deck
(`ATRAXA_DECK_ID`), which is exactly why "switches to the new deck" and "does not refetch the old
one" were unassertable. Deck B is ✅ **VERIFIED REAL** against the live database at story time —
`Arabella Mobilize (Boros) v2 - owned`, id `45d80726-0f7b-460a-97fc-d0b457215d6d`, `standard`,
60 mainboard / 18 distinct — and its two fixture cards (`Arabella, Abandoned Doll`,
`{R}{W}` cmc 2, and `Mountain`) are real rows of that real deck at their real quantities. Built
through `deckDetail`'s existing overrides rather than as a second literal body, so exactly one place
still knows the shape of a deck-detail response. Its cold-open target is `Arabella, Abandoned Doll`
because `Legendary Artifact Creature — Toy` groups as **Creature**, which leads `TYPE_GROUPS` —
`Artifact` never gets a look in (verified in `deckGroups.ts`, whose own docstring records the
first-match-wins precedence).

**AC-by-AC satisfaction.**

- **AC 1** (none → deck) — **shipped and cited, not rewritten.** `App.test.tsx`'s
  `switches decks on active_deck_changed — the event that had no listener (AC 11)` is literally this
  AC; it passes, and Task 5's plant proves it is load-bearing rather than incidental. Per Q1 no new
  test was added for it.
- **AC 2** (switch + pin released) — new tests 1 and 3.
- **AC 3** (not treated as `deck_changed`) — new test 1's request log, **plus** the shipped
  duplicate-frame idempotence pin at `:2445` (three same-id frames → three cheap re-drives, one
  socket), confirmed still green and cited here rather than duplicated. There is deliberately no
  kind branch to test: `connection.ts:96-108` reads neither the kind nor `payload.deck_id`, and
  adding a branch now would be building c7-3.
- **AC 4** (404 clears) — new test 2, end to end.
- **AC 5** (several tabs, every tab switches) — **recorded, per Q5.** The evidence chain is: c5-4's
  backend broadcast fan-out test (every registered connection receives the envelope) + this story's
  per-client pins (each tab runs the identical handler these three tests exercise) + the spine
  residual that *"divergence between tabs is accepted"* (`ARCHITECTURE-SPINE.md:496-497`). A jsdom
  two-instance mount would fake the very fan-out it claimed to prove. The literal two-tab
  observation **already exists** in the Epic C6 manual checklist and needed no line added: retro
  item **J2** is worded *"open two tabs, ask the agent to switch decks"* and is explicitly re-homed
  to c6-2/c6-3 manual testing, carried wholesale by action item **R11** (c8-6 as terminal backstop).
  Recorded where it lives rather than duplicated — there is no separate C6 accumulator in
  `sprint-status.yaml`.

**Ledger reconciliation (Task 6).** The `agentEventOf` kind-only-validation entry (c5-6 Group 3) is
annotated **NOT TRIGGERED by c6-3** and left **open**: this is Epic 6's first frontend story, but it
reads no payload field at all by ruling, so the entry belongs to c6-4+ when the agent views land.
dw:3756 is already ✅ CLOSED and needed no status change; one line was added recording that its
closure — previously asserted from the code — is now **measured** by this story's plant.

**Gates, all green.** `npm run lint` clean (eslint + stylelint), `npm run typecheck` clean (`tsc -b`),
`npm run format:check` clean, `npm test` **1,871 passed / 69 files** (1,868 → 1,871, +3, strictly
larger as required). Governance suites green and untouched: `store-writes`, `posture`,
`shell` — **348 passed / 3 files**. Python **2,874 passed / 1 skipped / 55 deselected**, unmoved as
required. No `npm run build`, no `build_plugin.py`: tests-only diff, confirmed by `git diff --stat`.

**Dev Notes KB self-check: 16.0 KB** (lines 174–385), inside the 10–20 KB target band and in line
with c6-2's 16.8 KB. R1's trigger-gating continues to hold.

**Nothing carried forward, and one thing worth Brad's eye.** No new deferred work. The one judgement
call a reviewer should check is the **nested `beforeEach`**: it is the only change that touches
shared-harness behaviour, it is deliberately scoped to this describe, and the argument for not
widening it into the file's own `beforeEach` is in the comment beside it.

### File List

- `ui/src/App.test.tsx` — **modified.** Two imports added (`resetDeckMemory`,
  `resetInspection` + `useInspectionStore`); one new `describe` block of 3 tests with its own
  nested `beforeEach`, deck-B fixture and four local helpers. +288 lines. **The only code file in
  this story's diff.**
- `_bmad-output/implementation-artifacts/deferred-work.md` — **modified.** `agentEventOf` entry
  annotated not-triggered-by-c6-3 (stays open); dw:3756's closed entry gained a firing-proof line.
- `_bmad-output/implementation-artifacts/c6-3-the-glass-follows-the-agents-active-deck-choice.md` —
  **modified.** Task checkboxes, Dev Agent Record, File List, Change Log, Status.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — **modified.** Story status
  `ready-for-dev` → `review`; `last_updated` refreshed.

**Reverted, and listed so its absence is deliberate rather than accidental:**
`ui/src/state/connection.ts` — Task 5's planted no-op, reverted and verified clean with
`git diff --exit-code`. It is **not** part of this story's diff.

## Change Log

- 2026-08-09 — Story context created (create-story). 5 open questions await Brad's pre-code ruling.
  Key finding recorded: the runtime path shipped at c5-6/c4-2/c4-5 (retro J2 concurs); this story
  is scoped as proof + gap coverage, pending Q1.
- 2026-08-09 — All 5 open questions **ruled as recommended** by Brad before any code was written
  (Q1 tests-only, Q2 accept-and-pin, Q3 manual plant with R5 left open, Q4 observe-and-record,
  Q5 record the AC-5 chain).
- 2026-08-09 — Story IMPLEMENTED → `review`. **Tests-only diff, as Q1 ruled**: `ui/src/App.test.tsx`
  is the only code file touched (+288 lines: one new `describe` of 3 tests, a real second deck
  fixture, four local helpers, and a nested `beforeEach` that resets the two module-scope stores the
  file's own `beforeEach` misses — the inspection slice and `deckMemory`'s `lastBoards`). No `ui/src`
  runtime file changed, so `src/companion/app/static/` and `plugin/**` were **not** rebuilt.
  Frontend suite 1,868 → **1,871 passed / 69 files**; Python **2,874 / 1 skipped / 55 deselected**,
  unmoved; lint, `tsc -b` and `format:check` clean; governance suites **348 passed**, untouched.
  Task 5's plant (`onSystemEvent` → no-op, dw:3756's regression verbatim) reddened **7 tests** —
  all 3 new ones plus the 4 shipped socket-event tests — with the collected count validated at 1,871
  first, then reverted and verified clean. Q4 answered from `deck.ts:515-519` rather than from a
  test: `redriveDeckBoot()` writes no store state, so the old deck holds until deck B lands
  atomically — no `'booting'` interim, at any latency; recorded, nothing changed. Baseline's first
  frontend run was the known `lintBothFixtures` cold-start flake (second sighting, documented, not
  hidden). Ledger: `agentEventOf` annotated not-triggered and left open for c6-4+; dw:3756 gained a
  firing-proof line. AC 5 recorded via the c5-4 + per-client + spine-residual chain; the two-tab
  observation already lives in retro item J2, carried by R11 — no line needed.
- 2026-08-09 — Story CODE-REVIEWED → `done`: three-layer adversarial review (Blind Hunter, Edge Case
  Hunter, Acceptance Auditor) caught 0 decision-needed, 0 patch, 2 defer, 13 dismissed as noise.
  Acceptance Auditor independently re-verified every code-mechanism claim in the diff and Dev Agent
  Record against live source and found zero AC violations. Deferred (both pre-existing, out of this
  story's bounds, homed in `deferred-work.md`): (1) the AC-4 test covers only the `deck_not_found`
  refusal reason, not a mid-session refusal with different retry semantics (e.g.
  `database_not_initialized`); (2) the Q2 none-interlude test omits the request-log sweep Task 1's
  switch test applies. No code changed; suite counts unmoved from the IMPLEMENTED entry above.
- 2026-08-09 — Story MERGED via PR #65 into `feat/companion-c6` at `fa5f963`. No Greptile findings
  surfaced post-merge (unlike c6-2, which had a 4-branch echo gap Greptile caught). Next: c6-4
  (`companion_show_suggestions`, the agent's first push).
