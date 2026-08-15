---
title: 'c7-6: Deck deletion, and agent views during a refetch'
type: 'feature'
created: '2026-08-15'
status: 'done'
review_loop_iteration: 0
baseline_revision: '8165f49c146170713c30d3e3e9bc51a9c80cd74e'
baseline_commit: '8165f49c146170713c30d3e3e9bc51a9c80cd74e'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-c7-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Three of this story's five ACs are already satisfied by shipped code — the 404 clears to `no-active-deck` (`deck.ts:566-569`), the panel lists remaining decks non-clickably (`StatePanel.tsx:133-143`), an open view stays valid when the deck dies behind it (`App.test.tsx:4426`), and the skip link is already withdrawn on every panel surface (`App.tsx:455`). Two are **not**. (1) The announcement fires from behind an open agent view — c7-5 shipped `App.test.tsx:4101` deliberately observing today's behaviour so this story can flip it. (2) When the deck surface unmounts at the 404-clear, a tile, flip control or deck row holding focus drops focus to `<body>` and restarts Tab from the top — the unclosed half of the epic's no-focus-to-body rule, ledgered at `SkipLink.tsx:72-76` with **c7-6 named by hand**. And the deletion walk itself — delete → emit → 404 → panel → *remaining* decks → Tab order — has never been asserted end to end.

**Approach:** Add one primitive selector `useAgentViewIsOpen` (`status === 'open'`) and gate `DeckAnnouncer`'s `speaks` on it, letting `seen` advance so a suppressed settle is **consumed, not deferred**. Add one surface-transition focus rescue in `App.tsx`: when the surface leaves `kind === 'deck'` and focus fell to `<body>`, hand it to `.state-panel-headline ?? h1` via the existing `focusHome` — AgentView ARM 3's exact target and helper, one call site, no new document listener. Everything else this story owes is coverage: the end-to-end deletion walk, the Tab-order walk across the transition it owns, and closing the `SkipLink` ledger prose.

## Boundaries & Constraints

**Always:** Suppression lives at exactly one expression — `DeckAnnouncer.tsx:88`'s `speaks` — and `seen` still advances to `settles` on a suppressed settle, so the announcement is dropped rather than queued to fire on close. The new selector is a **primitive** (`state.status === 'open'` → boolean), not `useOpenAgentView`, which would resubscribe the announcer to the content object and break its own "NARROWED TO PRIMITIVES" discipline (`DeckAnnouncer.tsx:64-66`). Focus rescue fires only on a `deck` → non-`deck` surface transition AND only when `document.activeElement` is `null` or `document.body` — if anything else already holds focus, moving it would override a decision this effect did not make (`SkipLink.tsx:112-116`'s ruling, applied at the surface). Target is `focusHome(document.querySelector('.state-panel-headline') ?? document.querySelector('h1'))`, verbatim from `AgentView.tsx:253`; there is one focus home and this adds a caller, not a copy. `useDeckStore` stays written only by `src/state/deck.ts` — **no store change in this story**. Both App live-region censuses (`App.test.tsx:2130-2148` at rest, `:3581-3589` mid-flight) stay exhaustive at their current shapes. All firing proofs through `scripts/vitest_probe_harness` (warm `--control` first; stage the tree before planting; revert via `git diff --exit-code`). Runtime `ui/` diff → rebuild `src/companion/app/static/` and `plugin/`, commit both.

**Ask First:** If the focus rescue cannot be expressed without a new document-level listener, stop — `keyboard-floor.test.ts:760+` admits exactly two (CardDetail's bubble, AgentView's capture) and a third is a floor change, not a story change.

**Never:** No backend or wire change — `delete_deck` already emits after commit (`server.py:321-322`) and is already in the enumeration (`test_deck_changed_wiring.py:82-84`, behavioural proof at `:221`); do not re-litigate it. No change to the dangling active-deck slot: a slot holding a deleted id is a **ruled-legitimate state** (`state.py:95-99`) whose answer is the `deck_not_found` path already built. No new StatePanel copy, no new state key, no new reason token. No announcement on close of a view that suppressed one. No format-check announcement — that deferral is **unowned pending a UX ruling** (`deferred-work.md:4782`) and no story may home it here. No `surfaceOf` change (see Design Notes). No new container, no AppShell prop, no landmark change.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Deletion, app open | Agent deletes active deck → `deck_changed` → refetch | 404 `deck_not_found` → `{status:'none'}` → `no-active-deck` panel; deck heading gone | N/A |
| Panel content after deletion | Poll restart answers `GET /api/decks` | Panel lists the **remaining** decks, non-clickable; deleted name absent | N/A |
| Last deck deleted | `GET /api/decks` → `[]` | Headline renders, no list element (`filled()`, `StatePanel.tsx:133`) | N/A |
| Refetch settles behind a view | View open, refetch success | Region stays empty; counter still advances; deck updates behind the view | N/A |
| Next refetch after close | View closed, later refetch settles | Announces normally — no replay of the suppressed one | N/A |
| View open, no refetch | View opened after an announcement stands | Standing text is not re-announced (no DOM mutation) | N/A |
| Deletion behind a view | View open, active deck 404-clears | View untouched and valid; no announcement (404 never announced); on close focus lands on `.state-panel-headline` | N/A |
| Focus on a tile at deletion | `.card-tile` focused, surface → panel | Focus handed to `.state-panel-headline`; never `<body>` | N/A |
| Focus on a deck row at deletion | `.deck-row` focused, surface → panel | Same hand-off (the whole deck surface departs) | N/A |
| Focus elsewhere at deletion | Header/footer/nav pill focused | Focus untouched — rescue declines | N/A |
| Tab order after deletion | Grid gone | Skip link absent; zero `.card-tile` / `.flip-control` stops | N/A |
| Non-404 refetch refusal | 503 behind an open view | Deck stays, view stays, no clear, no announcement (dropped) | N/A |

</frozen-after-approval>

## Code Map

- `ui/src/state/agentView.ts` -- add primitive selector `useAgentViewIsOpen()` beside `useOpenAgentView` :470 (which stays; it is App's content reader). Body: `state.status === 'open'`. `status` is written by `openAgentView` :304, `reopenAgentView` :358, `openSuggestionsPush` :423, `closeAgentView` :446 — `status:'open'` with null `content` is unreachable (both written in one `setState`, :304-322), so the boolean is sound.
- `ui/src/containers/DeckAnnouncer/DeckAnnouncer.tsx` -- subscribe the new selector beside the four existing primitives :62-76; gate the `speaks` expression :88 with `&& !viewOpen`. `seen: settles` on :89 is UNCHANGED — that is what makes it a drop, not a defer. The staleness-clear branch :94-105 is untouched. Amend the docstring :53-56, which currently states this component deliberately does not read agent-view state, to record that c7-6 closed it.
- `ui/src/App.tsx` -- the focus rescue. `surface` is already in hand (:172-173, `surfaceOf(useDeckState(), system)`); add a `useRef` of the previous `surface.kind` plus one `useEffect` keyed on it. **Do not reorder the measured effect blocks :194-198** — append after them. Needs a new import of `focusHome` from `./containers/focusHome` (App.tsx imports :1-26 today do not include it; `shell.test.ts` pins container import lists, not `App.tsx`'s — verify at :1094-2047 before assuming). Grid + analysis row :510-518 and the right column both hang off the same `kind === 'deck'` gate, so ONE transition covers every departing focusable (tile :396, flip control, deck row `DeckList.tsx:200`, oracle `CardDetail.tsx:595`).
- `ui/src/containers/SkipLink/SkipLink.tsx` :62-76 -- prose amendment only: the ledgered half is now closed; rewrite the "half it does not own" paragraph to cite the App-level rescue and drop the "does not claim the epic's AC 9 is fully covered" sentence.
- `ui/src/App.test.tsx` -- **flip `:4101`** (`'announces on a completion behind an open agent view — suppression is c7-6, not here'`) to assert silence, renamed for this story. New c7-6 describe hosted on the c7-3/c7-5 harnesses: `bootedDeck()` :3194-3202, `push('deck_changed', …)`, `decksPolls(paths)` :3195, the region helper :3825, the dialog fixtures :4283+. The deletion walk extends `:3379` (`'clears to no-active-deck when the refetch 404s'`), whose own comment :3383-3384 says c7-6 owes the deck-list assertion it does not make. Tab walk: reuse `focusablesNow()` :1773-1777 and the document-order idiom :1668 — do NOT move the loaded-deck census pins :1815-1830. Existing tests that must keep passing unchanged: `:4426` (view valid when deck lost), `:4450` (close lands on the headline), `:4477` (skip link + Tab stops withdrawn), `:3454` (503 behind a view).
- `ui/src/containers/DeckAnnouncer/DeckAnnouncer.test.tsx` (or the container's existing test home) -- unit half of the gate: suppressed settle leaves text `''` and still advances `seen`; the following settle with the view closed announces.
- `ui/src/state/agentView.test.ts` -- selector unit tests: `false` at rest, `true` after each of the three open writers, `false` after `closeAgentView`.
- `ui/tests/shell.test.ts` -- `DeckAnnouncer`'s pinned import list :2047 area gains `../../state/agentView`; CONTAINERS count is UNCHANGED (no new container).
- `ui/tests/keyboard-floor.test.ts` -- source-derived guards :292-787; the App-level rescue adds a `focusHome` caller, so check the "focus-home tabindex set imperatively in exactly one module" assertion :787 and the per-file focusable census :303-315 still hold.
- `scripts/vitest_probe_harness.py` -- firing proofs: warm `--control` → `--expect-total N --expect-red '<substring>'` per plant → revert → `--expect-green`.
- Read-only evidence (do not change): `src/mcp_server/server.py:307-322` (delete emits after commit), `tests/integration/mcp_server/test_deck_changed_wiring.py:82,221,661` (enumeration + deletion proof), `src/companion/app/routes/decks.py:34,88-90` (list + 404), `src/companion/contracts.py:74-85` (closed reason set), `src/companion/app/state.py:95-99` (dangling slot is ruled behaviour), `ui/src/state/connection.ts:146-150` (refetch then poll restart), `ui/src/state/poller.ts:255-298` (deck names + self-stop).

## Tasks & Acceptance

**Execution:**
- [x] Task 0: baseline -- `cd ui && npm test` warm (78 files / 2228 tests, exit 0), then
      `uv run python -m scripts.vitest_probe_harness --control` →
      `vitest: 78 files / 2228 tests, 0 failed, exit 0` / `CONTROL GREEN — score the planted run
      with: --expect-total 2228`. **Post-story control: `--expect-total 2253`** (79 files, +25
      tests: 6 selector, 8 announcer-unit, 11 App-level).
- [x] `ui/src/state/agentView.ts` + `ui/src/state/agentView.test.ts` -- `useAgentViewIsOpen`
      primitive selector beside `useOpenAgentView`; six unit tests walking `false` at rest, `true`
      after each of the three open writers (direct, socket push, pill re-open), `false` after
      `closeAgentView` **with content and retention still intact**, and the primitive/agreement
      claim against `useOpenAgentView`.
- [x] `ui/src/containers/DeckAnnouncer/DeckAnnouncer.tsx` + `DeckAnnouncer.test.tsx` (new) --
      `&& !viewOpen` is the only change to the expression at `:88`; `seen: settles` untouched.
      Docstring's *"WHAT THIS DELIBERATELY DOES NOT DO"* modal paragraph replaced by the
      **AND NOW IT IS SILENT BEHIND A MODAL (c7-6)** section; the format-check line now records
      the deferral as UNOWNED pending a UX ruling. Eight unit tests, including the
      drop-not-defer pair and three non-vacuity rows (announces with no view; a standing sentence
      survives a view opening; a standing sentence still empties when the deck departs behind one).
- [x] `ui/src/App.tsx` -- `previousSurfaceKind` ref + one focus-rescue `useEffect` **appended
      after** both measured blocks (neither moved); `focusHome` imported beside `SkipLink`. Ref is
      written inside the effect, never during render.
- [x] `ui/src/containers/SkipLink/SkipLink.tsx` -- prose only. The *"half it does not own"*
      paragraph now records the closure and cites the App-level rescue; the *"does not claim the
      epic's AC 9 is fully covered"* sentence is gone; the `heldFocus` sample is explicitly kept
      (its ambiguity is real at the element's scale, absent at the surface's).
- [x] `ui/src/App.test.tsx` -- `:4101` flipped in place to
      `'stays SILENT on a completion behind an open agent view (flipped at c7-6)'`, with
      non-vacuity (counter moved, deck behind the dialog recomputed). New
      `describe('deck deletion, and agent views during a refetch (c7-6)')` with 11 tests covering
      every matrix row: the deletion walk to remaining decks (request counts + non-interactive
      list + deleted name absent document-wide), last-deck-deleted, suppression + resume-after-close
      (MutationObserver proving the close announces nothing), the standing-sentence row, the 503
      row, deletion behind a view (view valid, silent, rescue declines, close lands on the
      headline), tile / deck-row / footer-link / connection-pill focus rows, and the Tab-order walk.
      `:4426`, `:4450`, `:4477`, `:3454` and the corridor pins `:1815-1830` are unmodified.
- [x] `ui/tests/shell.test.ts` -- `DeckAnnouncer.tsx`'s pinned import list gains
      `'../../state/agentView'` (sorted first); `CONTAINERS` stays at 36 (the new
      `DeckAnnouncer.test.tsx` is exempt as a test file and imports from vitest, which that
      guard checks). `ui/tests/keyboard-floor.test.ts` -- **no edit needed and verified so**: the
      rescue adds a `focusHome` CALLER, writes no `.tabIndex` itself, so `:787`'s
      one-module assertion and the per-file focusable census both hold unchanged.
- [x] Firing proofs -- both plants through the harness, both reverted byte-for-byte, final green:

      plant (a) — `&& !viewOpen` removed from `speaks`:
      vitest: 79 files / 2253 tests, 6 failed, exit 1
        RED |dom| src/App.test.tsx > … (c7-5) > stays SILENT on a completion behind an open agent view (flipped at c7-6)
        RED |dom| src/App.test.tsx > … (c7-6) > drops the announcement for a refetch settling behind an open view, and resumes after it closes (AC 1)
        RED |dom| src/containers/DeckAnnouncer/DeckAnnouncer.test.tsx > … > writes no text when the settle lands while a view is showing
        RED |dom| src/containers/DeckAnnouncer/DeckAnnouncer.test.tsx > … > does NOT queue the suppressed sentence to fire when the view closes
        RED |dom| src/containers/DeckAnnouncer/DeckAnnouncer.test.tsx > … > announces the NEXT settle normally once the view is closed — no replay of the dropped one
        RED |dom| src/containers/DeckAnnouncer/DeckAnnouncer.test.tsx > … > suppresses EVERY settle for as long as the view stays open

      plant (b) — the rescue's `focusHome(...)` call removed:
      vitest: 79 files / 2253 tests, 3 failed, exit 1
        RED |dom| src/App.test.tsx > … (c7-6) > hands focus from a TILE to the panel headline when the deck is deleted under it (AC 3)
        RED |dom| src/App.test.tsx > … (c7-6) > hands focus from a DECK ROW the same way — the whole surface departs at once (AC 3)
        RED |dom| src/App.test.tsx > … (c7-6) > withdraws the skip link and every grid stop from the Tab order after the deletion (AC 4)

      final: `--expect-total 2253 --expect-green` → `vitest: 79 files / 2253 tests, 0 failed, exit 0`
- [x] Artifacts -- `cd ui && npm run build` (tsc -b clean, 112 modules, `index-BDj4RNrs.js`) +
      `uv run python -m scripts.build_plugin` (v0.4.0, 4 skills); `src/companion/app/static/` and
      `plugin/server/src/companion/app/static/` both rebuilt and committed, zero residual drift.
      `uv run pytest -m "not integration"` → **3020 passed, 1 skipped, 55 deselected** — the
      unchanged count, and no backend file was touched.

**Acceptance Criteria:**
- Given an agent view is open and a coalesced refetch completes behind it, when the settle lands, then the `deck-announcement` region stays empty, the deck behind the view has updated, and the view's dialog is untouched — and when a later refetch completes with the view closed, it announces normally with no replay of the suppressed one.
- Given the active deck is deleted through the agent, when the emitted `deck_changed` drives the refetch, then the refetch 404s, the app clears to the `no-active-deck` panel, and once the restarted poll answers, the panel lists exactly the remaining decks — non-clickable, with the deleted deck's name absent.
- Given the deck surface is replaced by a state panel while a tile, flip control or deck row held focus, when the transition commits, then focus is on `.state-panel-headline` and never on `<body>` — and given focus was on the header, footer or nav pill instead, then focus is left exactly where it was.
- Given the app has cleared to no-active-deck, when the Tab order is walked, then the skip link is absent and no `.card-tile` or `.flip-control` stop remains, with the loaded-deck corridor pins unmoved.
- Given an agent view is open when the active deck is deleted, when the view is closed, then it stayed open and valid throughout and the reader lands on the no-active-deck panel's headline.
- Given the guard suites (shell, keyboard-floor, store-writes, posture, tokens, token-usage, copy-rules, wire-contract), when the suite runs, then all pass with only the declared import-pin and prose amendments, and both live-region censuses stay at their current shapes.

### Review Findings

- [x] [Review][Patch] Stray `</content>` closing tag committed at the end of this spec file — no opening tag exists; templating leftover, delete the line [spec-c7-6-deletion-and-views-during-refetch.md:179] — APPLIED
- [x] [Review][Patch] AC 3's decline arm names "header … or nav pill" but no test focuses either — only a footer link and the connection pill are exercised; add a c6-8 reopen-pill (and/or header-element) decline row [ui/src/App.test.tsx, c7-6 describe] — APPLIED (nav-pill decline row; plant (c) proof below)
- [x] [Review][Patch] AC 3 names the flip control (and the App.tsx rescue comment claims the oracle scroller + unpin control) but no test focuses any of them across the transition — tile and deck row are the only rescue rows; add a flip-control row [ui/src/App.test.tsx, c7-6 describe] — APPLIED (Pathway-hydration arrangement from the c7-4 back-face test; plant (b) re-proof below)
- [x] [Review][Patch] The AC 4 Tab-order test exercises the rescue only through the accepted-residue path (nothing is ever focused, so the rescue fires via focus-already-on-body), and its `withTabIndex` assertion + plant (b)'s third RED pin that residue — name the coupling in the test comment or focus a tile first [ui/src/App.test.tsx, 'withdraws the skip link…' test] — APPLIED (comment names the coupling and the repair if the residue is ever guarded)
- [x] [Review][Patch] The epic-context Goal rewrite dropped the traceable `SC-2` identifier and shortened "Scryfall printing UUID" to "printing UUID" — restore both hooks [_bmad-output/implementation-artifacts/epic-c7-context.md:6-13,80] — APPLIED
- [x] [Review][Patch] DeckAnnouncer's new docstring claims "the App censuses pin [the region] empty behind a modal" — neither census (at-rest, mid-flight) asserts a behind-a-modal shape; the c7-6 tests do. Reword the citation [ui/src/containers/DeckAnnouncer/DeckAnnouncer.tsx, AND NOW IT IS SILENT section] — APPLIED (comment-only; rebuilt bundle byte-identical, zero drift)
- [x] [Review][Defer] The mirror transition can still drop focus to `<body>`: after the rescue (or AgentView ARM 3) parks focus on `.state-panel-headline`, a panel → deck transition (agent creates/activates a deck; reconnect restores one) unmounts the StatePanel and the focused headline dies with it — the rescue early-returns when the ARRIVING surface is `deck` [ui/src/App.tsx:895] — deferred, pre-existing (reachable via ARM 3 before c7-6; this story widens reachability); same failure class at the opposite edge, ledgered in deferred-work.md the way SkipLink.tsx ledgered this story's half

## Spec Change Log

- **2026-08-15 — implementation, no Intent change.** Everything in the frozen block held; the Code
  Map's predictions were checked rather than assumed and three are worth recording:
  - `App.tsx`'s import list is pinned by NOBODY — `shell.test.ts`'s nine lists do not cover it and
    `posture.test.ts:344-353` only forbids it reaching the network. The `focusHome` import is
    therefore free, as the Code Map suspected; verified before adding it.
  - `keyboard-floor.test.ts` needed **no amendment at all**. `:787` asserts one module writes
    `.tabIndex` imperatively, and the rescue calls `focusHome` rather than writing one; the
    per-file focusable census reads JSX, and `App.tsx` renders no focusable of its own.
  - The `DeckAnnouncer` had no test home, so `DeckAnnouncer.test.tsx` is new. `CONTAINERS` stays at
    36 because `coversExactly` filters `.test.tsx` — and the same guard then requires such a file
    to import from vitest, which it does.
- **2026-08-15 — four-layer code review (blind-hunter, edge-case-hunter, verification-gap,
  acceptance-auditor), no Intent change.** 0 decision-needed, 6 patches (all low, all applied),
  1 defer (medium, ledgered), 15 dismissed. Verification-gap found NO gap; acceptance-auditor's
  verdict: faithful, every Always/Never constraint verified against the repo. The defer — found
  independently by two layers — is the panel → deck MIRROR transition dropping focus to `<body>`
  (the rescue early-returns when the arriving surface is `deck`; pre-existing via AgentView ARM 3,
  reachability widened by this story), ledgered in deferred-work.md. The review patches added two
  tests (flip-control rescue row, nav-pill decline row): **suite is now 79 files / 2255 tests**,
  control re-run green at 2255, and both new tests carry their own firing proofs —
  plant (b) re-run (`focusHome(...)` call removed): 4 failed, the new flip-control row RED beside
  the original three; plant (c), new (decline guard removed, rescue fires unconditionally):
  4 failed — both decline rows, the nav-pill row, and the AC 5 behind-a-view walk all RED.
  Both plants reverted byte-for-byte (`git diff --exit-code`), final `--expect-total 2255
  --expect-green` → 0 failed, exit 0. Rebuilt bundle + plugin: byte-identical, zero drift (the
  one source patch is comment-only). One cold full-suite run errored on the shape of R5's
  ledgered cold-eslint timeout (104 s setup) — a SEVENTH sighting for that item; two warm re-runs
  and the harness control were fully green.
- **2026-08-15 — Greptile round 1 (PR #80), one valid finding, fixed.** *Focus escapes behind
  open modal*: the rescue's body-focus inference assumed an open view always holds focus, but a
  real pointer click on the dialog's NON-focusable content blurs to `<body>` — a browser
  behaviour jsdom does not model, which is why all four review layers and every existing decline
  row missed it — and the rescue would then park keyboard/AT focus on the panel headline BEHIND
  the still-open dialog. Fix: a THIRD guard, `if (agentView !== null) return` (the subscription
  App already held), so with a view open the rescue always declines and ARM 3 owns the close
  landing. New test arranges the blur by hand and asserts decline + no headline residue + close
  still landing on the headline. Suite 2255 → **2256**; plant (d) (view-open guard removed) →
  exactly that test RED through the harness; revert clean; `--expect-total 2256 --expect-green`
  → 0 failed. This is a RUNTIME change: bundle rebuilt (`index-DJ7dGud2.js`), both mirrors
  committed. Note the fix also narrows the accepted residue: focus-never-anywhere + view open at
  the transition now declines rather than moving to the headline — correct, since ARM 3 covers
  the close.
- **Residue found while walking the Tab order (recorded, not fixed).** After the rescue fires, the
  panel headline carries `tabindex="-1"` until it blurs, so the corridor helper's
  `'a[href], button, [tabindex]'` selector counts it — the helper models the MARKUP rather than the
  focus behaviour, which its own docstring already flags as `deferred-work.md:45`'s shape. The
  new Tab-order test asserts the attribute's VALUE (`-1`, therefore not a Tab stop) instead of
  filtering it out, so the day it is written as `0` that test is where it fails.

## Design Notes

- **Why suppression drops rather than defers.** Announcing on close would speak a sentence whose moment has passed — and worse, it would speak *a* count while the user is reading a modal about something else. `seen` advancing to `settles` is what makes the settle consumed; the next real refetch is the next real announcement. This also keeps the region's contract with the census tests: empty at rest, empty mid-flight, empty behind a modal.
- **Why the announcer, not the announcement site.** The alternative — not incrementing `refetchSettles` while a view is open — would put UI-presentation knowledge into the store and break the c7-5 rule that the counter means "a coalesced refetch completed", full stop. The counter stays truthful; the announcer decides whether to speak.
- **Why the rescue is one App-level effect and not the SkipLink idiom repeated.** `SkipLink` samples `heldFocus` on the way in because, at *its* scale, `activeElement === body` in a cleanup is ambiguous. At the **surface** scale it is not: the whole deck surface departs in one commit, so anything outside it that held focus still holds it. `activeElement` falling to `<body>` across a `deck` → panel transition therefore means the focused node was in the departing surface. One effect covers tile, flip control, deck row, oracle scroller and unpin control — five focusables that would otherwise need five copies of the ref idiom.
- **The accepted residue:** if focus was *already* on `<body>` before the transition (nothing had ever been focused), the rescue still moves it to the panel headline. That is the standard SPA answer to replaced content — and AgentView ARM 3 (`:252-255`) already does exactly this — so it is recorded as correct rather than guarded against.
- **The transient stale name is accepted.** `connection.ts:146` refetches before `:150` restarts the poll, and both are async, so the panel can list the just-deleted deck for one round trip before the fresh `GET /api/decks` lands. Blocking the clear on the poll would trade a self-correcting one-round-trip window for a slower teardown; the AC is asserted on the settled end state, and the transient is named here rather than left to be rediscovered.
- **Why `surfaceOf` is not touched.** `stateForPanel` folds `no-active-deck` to `{status:'none'}` and defers to `system.panel`, so a 404-clear arriving during, say, a `database-updating` window renders *that* panel with no `decks` prop. That is deliberate: the system panel is the authority on why there is no deck, and the more urgent system state is the right thing to show. Both are calm no-deck surfaces; changing the precedence is a c4/c7-3 decision, not this story's.
- **Nothing to do on the backend, and that is a finding.** `delete_deck` emits the now-absent id *after* the row is gone (`test_deck_changed_wiring.py:221` asserts `[True, False]`), so a refetch racing the emit cannot resurrect the deck — the 404 is guaranteed, not hoped for.
- Known flake context: frontend cold-run eslint timeout — run the harness control warm.
- Branch process: story branch `feat/companion-c7-6-deletion-and-views` off umbrella `feat/companion-c7`; PR targets the umbrella (Greptile per story).

## Verification

**Commands:**
- `cd ui && npm run lint && npm run format:check && npm test` -- expected: eslint + stylelint clean, prettier clean, `tsc -b` clean, all vitest files green including guard suites with only the declared amendments.
- `uv run python -m scripts.vitest_probe_harness --control` (warm), then per-plant `--expect-total N --expect-red '<substring>'`, revert, `--expect-green` -- expected: both plants RED on named tests, reverts clean, final green; proof lines pasted into Tasks.
- `cd ui && npm run build && uv run python -m scripts.build_plugin && git status --porcelain -- src/companion/app/static/ plugin/` -- expected: rebuilt bundle + `plugin/` mirror committed, zero residual drift.
- `uv run pytest -m "not integration"` -- expected: green, unchanged count (no backend file touched).

**Manual checks (if no CLI):**
- Real screen-reader silence behind an open agent view, and the real focus landing after a deletion, are perceptual residue jsdom cannot prove — add both to the epic's manual-testing checklist.
