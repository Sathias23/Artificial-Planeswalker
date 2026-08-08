---
baseline_commit: 44530acd2d500378484013d6e108ab3b46b976c7
---

# Story c5-7: Connection pill

Status: done

<!-- Ultimate context engine analysis completed - comprehensive developer guide created. -->

## Story

As Brad glancing at the corner of the window,
I want to know whether the app is actually connected and to what,
So that I can tell a quiet app from a dead one.

## The story in one paragraph

c5-6 built the machine; this story builds the gauge. `SystemState.connection`
(`'live' | 'reconnecting' | 'down'`) already exists, written on change only, and three shipped
module headers name this story as its second consumer. The pill is a small, always-visible,
never-animating chrome element — an 8px static dot (positive/caution/negative), micro text that
names the state (the dot never carries it alone), and the active deck's name — bottom-left on
**every** surface, focusable with the standard ring, announcing state changes through the app's
second polite live region. This story also owns two decisions nobody else made: the pill's DOM
position (dw:4597 — three artefacts each assumed someone else fixed it) and the pill's actual
words (specified nowhere; the voice rules are, though). **The hover/focus tooltip with port and
instance id is c10-1's, not this story's** — build the shell so `aria-describedby` can attach
later, but do not read `GET /health` and do not build a tooltip.

## Acceptance Criteria

1. On **every** surface — a loaded deck, every state panel (no-active-deck, DB-not-initialized,
   DB-updating, stalled, disconnected, internal-error), an empty deck, and a cold open — the
   connection pill renders at the bottom-left (FR-15, UX-DR29, EXPERIENCE.md:112).
2. The pill shows an 8px dot: `--positive` when `connection === 'live'`, `--caution` when
   `'reconnecting'`, `--negative` when `'down'` (UX-DR29, DESIGN.md `components.connection-pill`).
3. The dot is `aria-hidden` decoration and **static under every setting** — no animation, no
   transition, no pulse, no loop (UX-DR29, UX-DR42; tokens.css:305-312 names this component as
   the reason the stylelint pulse ban exists).
4. The pill **text names the state** in words for all three states — the dot never carries the
   state alone (UX-DR29).
5. The `'down'` text carries the retrying-quietly note — the last unmirrored clause of
   EXPERIENCE.md's disconnected row ("Retrying-quietly note in the connection pill"), which is
   honest because c5-6's loop genuinely keeps retrying behind the panel forever.
6. When the deck slice holds a loaded deck, the pill also names it — read from the **deck slice**
   (`deck.detail.name`), never from `surfaceOf`'s result, because `surfaceOf` returns a panel
   surface in exactly the `'down'` state, where the deck slice underneath still holds the loaded
   deck even though the pill must not name it there (deck.ts:481-486; **Open Question 3 rules the
   `'down'`-state override: the name is withheld in that one state, not shown** — code-review
   correction, 2026-08-08). When no deck is loaded, or when `'down'`, the name is simply absent —
   no placeholder, no "undefined".
7. The pill coexists with the Disconnected state panel: `connection === 'down'` renders the panel
   in the left column AND the pill with its negative dot, simultaneously (EXPERIENCE.md:119).
8. The pill is focusable via Tab as a real interactive element with a ≥24×24px hit box and the
   standard known-surface focus ring (`--focus-ring-width` / `--focus-ring` /
   `--focus-ring-offset` under `:focus-visible`), never `outline: none`, never `--accent-bright`
   (UX-DR46, UX-DR47).
9. The pill's DOM position is **decided and recorded** (this story owns dw:4597): document order
   places it after both columns and immediately before the footer links — the last Tab stop
   before the footer — while it renders visually bottom-left. UX-DR40's enumeration in
   epics-companion-app.md and EXPERIENCE.md's Tab-order cell are updated from "(connection pill —
   c5-7)" markers to the shipped truth, in this story's commit.
10. Connection-state changes announce via a **polite live region** — the app's second, separate
    from CardDetail's (UX-DR45). The region is empty at rest and transient hover/focus changes
    never announce.
11. `App.test.tsx:2033-2041`'s "exactly one `[aria-live]` in the document" pin is updated to
    assert exactly two, both polite, each named — the pin stays exhaustive rather than being
    deleted.
12. The pill's words live in a `copy.ts` beside the component, registered in `COPY_MODULES`, and
    obey the voice rules: calm, second-person where it addresses at all, no exclamation marks, no
    emoji, never blame (UX-DR33 voice). The chosen strings are written into EXPERIENCE.md's
    connection-pill row in the same commit and gated against it (the c2-9/c3 "copy row ships with
    the component" precedent).
13. `copy-tails.test.ts:284`'s deliberate "leaves the PILL to c5-7" assertion is **converted**:
    the retrying-quietly clause is now mirrored against the shipped pill copy rather than
    asserted-to-be-unasserted.
14. The component lands in `src/containers/` (it reads stores and is focusable —
    shell.test.ts:1946 names c5-7 in this category by name): `CONTAINERS` gains its entry (length
    pin 25 moves), with import roots and the git-derived coverage guard satisfied. Any pure
    presentation split into `src/components/` follows the c2-6 conventions.
15. `keyboard-floor.test.ts` is extended honestly: the pill's host file joins the known-focusable
    anchor list (:303-320) and `DECLARES_MIN` (:432) with explicit `min-width/min-height: 24px`.
16. Styling spends only what DESIGN.md:299-303 specifies — `surface-panel` background, 1px
    `border-hairline`, `--radius-pill`, all three status colours (pre-authorised by
    token-usage.test.ts:1012-1013). The token inventory count (69, pinned in tokens.test.ts:321
    and token-usage.test.ts:1170) stays unchanged unless a `--connection-pill-*` token is added
    with a written reason and both pins moved together.
17. No new store, no new writer, no new dependency, no network access: the pill reads
    `connection` from the system slice and the deck name from the deck slice through hooks the
    state modules export. `store-writes.test.ts`'s tables and `posture.test.ts`'s one-door list
    are untouched. `socket.ts` is untouched (its c5-7 header comments may be reconciled —
    comments are stripped by the gates, but the module must still contain no `pill` outside
    comments).
18. Frontend tests drive the real machinery: a colocated dom test for the container, plus
    App-level tests using the established `FakeSocket` + fake-timer idiom that walk
    live → reconnecting (drop) → down (`await advance(DISCONNECTED_AFTER_MS)` after 4 failures)
    and assert the pill's dot class, text, deck name, and announcement at each step — including
    the pill's presence on a state-panel surface and on cold open.
19. Every new or modified guard ships an R2 firing proof: a planted violation shown RED through
    the FULL `npm test` (never a standalone file run), with one line stating what the assertion
    actually compares. All new files `git add`ed before trusting green (the meta-suites read
    `git ls-files`).
20. Task 0 greps `c5-7` across `ui/ src/ tests/ scripts/` and the story's Dev Agent Record
    enumerates every hit with a disposition — including the two **backend prose claims that the
    pill "wants a live gauge / connected count"** (`src/companion/app/state.py:436, :548`,
    `agent_events.py:40`), which the shipped pill spec contradicts (FR-15 shows state + deck
    name; the count appears nowhere). If those are rewritten, the change is prose-only,
    behaviour byte-identical, Python suite count unchanged (2,770 / 1 skipped), and the plugin
    mirror is rebuilt and sha256-verified.
21. The three c5-7-homed ledger entries are dispositioned in `deferred-work.md`: dw:4597 (DOM
    position — closed by this story's decision), dw:5354's pill clause (paid via AC 13), dw:5430
    (selector granularity — ruled either way with the reason written).
22. The committed SPA bundle in `src/companion/app/static/` is rebuilt (`cd ui && npm run
    build`) **in the same commit** as the source change, and the plugin mirror rebuilt — c5-6's
    CI bundle-drift catch (`6c2426f`) is not repeated. Both JS and CSS assets must change
    (baseline: `index-DjMPYZ-a.js` 227,151 B / `index-B_WnaAKx.css` 20,392 B).
23. Gates all green: `npm test` strictly larger than 1,812/67 files, `npx tsc -b --force`,
    eslint, stylelint, prettier, `npm run gen:api` a no-op (no wire change), ruff/mypy untouched
    or clean, `pre-commit run --all-files` including the mirror sync.

## Tasks / Subtasks

- [x] Task 0 — Baseline and reconnaissance (AC: 20, 23)
  - [x] Branch `feat/companion-c5-7-connection-pill` off `feat/companion-c5` at `44530ac`
  - [x] Verify baselines: frontend 1,812 / 67 files; Python 2,770 / 1 skipped
        (`-m "not integration"`); `npm run gen:api` a no-op; record bundle asset names/sizes
  - [x] `grep -rn "c5-7" ui/src ui/tests src tests scripts` — enumerate every hit with a
        disposition (the list in Dev Notes is the expected starting set)
  - [x] Read end-to-end: `connection.ts`, `systemState.ts`, `deck.ts` (`surfaceOf` + hooks),
        `AppShell.tsx` + `AppShell.css`, `Footer.css` (ring idiom), `CardDetail.tsx:283-320 +
        :583-592` (live-region idiom), `FormatCheck.tsx` (store-reading container precedent),
        and the five guard suites named in Dev Notes
- [x] Task 1 — Apply the pre-ruled decisions (AC: 9; Open Questions 1–6 ruled before code)
  - [x] Implement the ruled mount point and DOM position; update `AppShell` (new slot) and its
        tests if that is the ruling
  - [x] Update UX-DR40's enumeration in `epics-companion-app.md` and EXPERIENCE.md's Tab-order
        cell to the shipped truth
- [x] Task 2 — The container (AC: 1–7, 14, 16, 17)
  - [x] `src/containers/ConnectionPill/ConnectionPill.tsx` + `.css` + `copy.ts` + colocated test
  - [x] Reads `connection` via the system-slice hook and the deck name via the deck-slice hook —
        never through `surfaceOf`
  - [x] Dot (8px, aria-hidden, static) + state text + deck name; DESIGN.md:299-303 material
- [x] Task 3 — Focus and announcement (AC: 8, 10, 11, 15)
  - [x] Real interactive element per the Q2 ruling, ≥24×24 hit box, known-surface focus ring
  - [x] Second polite live region using CardDetail's render-time capture pattern (never
        `set-state-in-effect`); empty at rest; announces state transitions per the Q4 ruling
  - [x] Update the `App.test.tsx` aria-live pin to the exhaustive two-region form
- [x] Task 4 — Move the guards honestly (AC: 12–17, 19)
  - [x] `CONTAINERS` entry + length pin; `COPY_MODULES` entry; keyboard-floor host list +
        `DECLARES_MIN`; copy-tails conversion (AC 13); token count pins only if tokens moved
  - [x] R2 firing proof per touched guard, RED through the full suite, logged with what the
        assertion compares
- [x] Task 5 — Ledger and prose reconciliation (AC: 5, 20, 21)
  - [x] Disposition dw:4597, dw:5354 (pill clause), dw:5430 in `deferred-work.md`
  - [x] Rewrite the fulfilled c5-7 predictions in `socket.ts:160`, `systemState.ts:49`,
        `connection.ts:24`, `tokens.css:311`, `shell.test.ts`/fixture comments as shipped truth
  - [x] Backend prose per the Q6 ruling (`state.py:436/:548`, `agent_events.py:40`) — prose-only,
        mirror rebuilt + sha256-verified, Python count unchanged
- [x] Task 6 — Test sweep, bundle, gates (AC: 18, 22, 23)
  - [x] App-level pill walk: cold open → live → drop → reconnecting → down (real backoff via
        fake timers) → recovery; presence on state-panel and empty-deck surfaces
  - [x] Rebuild `src/companion/app/static/` and the plugin mirror in the same commit
  - [x] Full suites + all gates green; set story status to `review` and STOP (Brad runs the
        three-layer review and raises the PR)

### Review Findings

Chunked review (diff ~2,031 lines across Group A: ConnectionPill component + tests; Group B:
AppShell/App wiring + guard tests; Group C: backend prose-only). Three full layers (Blind Hunter,
Edge Case Hunter, Acceptance Auditor) on Groups A and B; a light self-review confirming the
prose-only claim on Group C. 1 decision-needed, 5 patch, 2 defer, 17 dismissed as noise (several
matched established codebase idioms once checked against surrounding code, or were speculative
concerns about functionality this story explicitly scopes out).

- [x] [Review][Decision] The pill and its live region sit outside all three ARIA landmarks — The
      docstring documents this as deliberate and `AppShell.test.tsx` proves landmark counts don't
      move, but it was never put to Brad as one of the story's six ruled open questions, and it
      runs against the common accessibility-audit expectation that persistent interactive chrome
      lives inside a landmark. **RESOLVED (Brad, 2026-08-08): accept as-is.** Ratified as a written
      decision, matching the c5-4 "accepted documented residual" precedent — no code change. The
      pill's position between `</main>` and `<footer>` (outside `banner`/`main`/`contentinfo`) is
      the deliberate, permanent shape.
      [ui/src/components/AppShell/AppShell.tsx]

- [x] [Review][Patch] Deck-name case-preservation has no source-reading guard, unlike the parallel
      dot-color binding — `.connection-pill-deck` escaping `--type-micro`/`text-transform:
      uppercase` is asserted only by a CSS comment. jsdom evaluates no stylesheet, so no DOM test
      can catch a regression here — this is the exact class of gap P15 found and fixed for the
      dot's color binding (a new `shell.test.ts` source-reading guard), left open for typography. A
      regression reattaching the micro/uppercase role to the deck name would pass the full suite.
      [ui/tests/shell.test.ts (missing); ui/src/containers/ConnectionPill/ConnectionPill.css:161-176]

- [x] [Review][Patch] AC 18's App-level walk is missing the `announcement()` assertion at the
      `reconnecting` step — the walk checks dot class + text + announcement at cold-open, live,
      down and recovery, but the `reconnecting` step (after `backendDown(); await drop()`) only
      checks dot class and text. Per Q4's ruling, live→reconnecting is exactly the kind of
      transition that should announce. Not a known implementation bug (the announcement logic is
      symmetric and should fire correctly), but a real coverage gap in the guard AC 18 requires,
      and the same class of miss the story's own P15 finding warns about.
      [ui/src/App.test.tsx:2638-2644]

- [x] [Review][Patch] AC 6's literal text was never reconciled with the shipped Q3 ruling — AC 6
      says the pill "must still name the deck" in the `'down'` state; Q3 rules the opposite (name
      omitted in `'down'`), and the shipped code follows Q3. Every other falsified/superseded
      artifact claim in this story gets a same-commit correction (c3-9's rule) — AC 6 is the one
      exception. Suggest amending AC 6 with a cross-reference to Q3's override.
      [_bmad-output/implementation-artifacts/c5-7-connection-pill.md (AC 6)]

- [x] [Review][Patch] Backend docstring rewrite introduces a second inaccurate claim — `state.py`'s
      rewrite correctly retracts the falsified "c5-7 wants it" prediction but replaces it with
      "consumed by :mod:`src.companion.app.ws` and by the ingest route's tests", which is itself
      wrong: `ws.py` never calls `.connected_count` (only cross-references it in a docstring), and
      `test_routes_agent_events.py` explicitly asserts the identifier is ABSENT from the route it
      tests. The only real callers are `test_ws.py` and `test_routes_active_deck.py`. Verified by
      grep. Prose-only, zero behavior change either way.
      [src/companion/app/state.py:566-567; tests/unit/companion/test_ws.py:89]

- [x] [Review][Patch] `.connection-pill` sets `cursor: pointer` on a button with no handler,
      undercutting the component's own extensive "NO HANDLER, AND THAT IS THE HONEST SHAPE"
      documentation — a hand cursor signals clickability the component deliberately does not have.
      [ui/src/containers/ConnectionPill/ConnectionPill.css:102]

- [x] [Review][Defer] Empty-string deck name (`''`) not normalized to `null` before reaching the
      pill's render/`pillText` [ui/src/containers/ConnectionPill/ConnectionPill.tsx:77-78;
      ui/src/containers/ConnectionPill/copy.ts:102-105] — deferred, pre-existing: reachable only if
      `deck.detail.name` is blank, which nothing in the deck schema or the header's own deck-name
      display (`.app-shell-deck-name`) guards against either.

- [x] [Review][Defer] No max-width/overflow guard on the deck name inside the fixed-position pill
      for unusually long names [ui/src/containers/ConnectionPill/ConnectionPill.css:76-103] —
      deferred, pre-existing: matches the identical, pre-existing gap in `.app-shell-deck-name`
      (the header's own deck-name display); not unique to this diff.

## Dev Notes

### The state you are consuming (all shipped by c5-6 — do not modify behaviour)

- `ConnectionStatus = 'live' | 'reconnecting' | 'down'` (`ui/src/state/socket.ts:166`).
  **`'down'` is spelled `'down'` in code** while every artefact says "backend gone" /
  "disconnected"; the state-panel key `'disconnected'` is a *different* vocabulary
  (`StatePanel/copy.ts:56-62`). Keep them apart — `socket.ts:150-166` and
  `systemState.ts:53-60` document why conflating `connection` with `panel` puts two writers on
  one field. The pill maps `'down'` → its negative dot + backend-gone words; it never touches
  `panelFor`/`PANEL_FOR_REASON`.
- `useSystemStore` holds `connection` (declared `systemState.ts:64`, initial `'reconnecting'`
  at `:78`), written on change only by `applyConnection` (`:97`). Its only current reader is
  `surfaceOf` (`deck.ts:482`); three module headers (`socket.ts:160`, `systemState.ts:49`,
  `connection.ts:24`) name this story as the second reader.
- Cold open starts at `'reconnecting'` (also the socket loop's `initialStatus` default,
  `socket.ts:301`) — so the pill's first painted state is the caution dot, flipping to positive
  when the first upgrade succeeds. `'down'` requires BOTH gates: ≥60 s elapsed AND ≥4 observed
  failures (`statusAfterFailure()`, `socket.ts:336-341`); the loop keeps retrying behind it
  forever (`keepsRetrying()` reads `RETRIES_QUIETLY.disconnected === true`), which is what makes
  AC 5's retrying-quietly note *true* rather than aspirational.
- Deck name: `deck.detail.name` when `DeckState.status === 'deck'` (`deck.ts:143`); `App.tsx:428`
  already passes `deckName={deck?.detail.name}` into `AppShell` from `useDeckState()`. **Do not
  derive the name from `surfaceOf`**: its fourth arm returns a panel surface when
  `connection === 'down'` (`deck.ts:481-486`) while the deck slice underneath still holds the
  loaded deck — exactly the state where the pill must keep naming it.

### Scope boundary — what this story is NOT

- **No tooltip, no `GET /health` read, no `aria-describedby` target.** UX-DR29's port/instance-id
  tooltip clause is Story 10.1's by the FR coverage map ("Pill shell + reconnect in 5; status
  detail in 10", epics:727) and c10-1's own ACs quote it. Build the pill so a describedby can
  attach later; ship none of it now.
- No client-count display: `connected_count` (ingest response) and `state.py`'s live-gauge
  property are NOT pill inputs — see the grep-own-key dispositions below.
- No cross-tab sync, no animation of any kind, no deck interaction on click.

### The placement ruling this story owns (dw:4597)

Three artefacts each assumed someone else decided the pill's DOM position: old UX-DR40 put it
between the deck rows and the footer; c10-1 calls it "the last stop before the footer";
`DESIGN.md:445`/EXPERIENCE.md:43 place it physically **bottom-left** — the opposite column from
the deck rows. c4-11 declined to decide without the component; **the decision is re-homed here by
name** (epics:608-612).

The resolution the shipped guard layer already anticipates (Open Question 1): a sibling element
between `</main>` and `<footer>` in `AppShell` — document order = last Tab stop before the footer
links, satisfying UX-DR40 and c10-1 — visually pinned to the bottom-left corner.
`ui/tests/fixtures/css/shell-violation.css:256` and `shell.test.ts:484, :2421, :2565` all state
that *"a pill pinned to one corner"* stays silent under the full-window-layer guard **by design**
("a false positive c5-7 has to fight is the worse outcome", review 2026-07-28). Mount mechanics:
a new `AppShell` prop is the honest shape — the `left`-slot Fragment idiom only renders on the
deck arm (`App.tsx:474-488` renders `<StatePanel>` in the other five cases) and AC 1 requires
every surface; the skip link is the precedent for "a real new slot when no slot exists"
(`AppShell.tsx:55-60`). Mind the footer overlap: the footer is a full-width one-line strip
(NFR-08, legally load-bearing) — the pill must not occlude its first link at narrow widths;
reserve space or inset the pill above it.

### The guard gauntlet (read BEFORE writing files — these turn green tests red)

1. **`shell.test.ts` `CONTAINERS`** (:1926+, length pinned **25** at :1994, git-derived coverage
   at :2000): the pill reads stores and takes focus, so it lives in `src/containers/` —
   :1946 names c5-7 in this category by name. Import roots: `react`, `../../components`,
   `../../state`, and `../../api` **type-only** (:2028-2124); no `zustand`, no `.setState`, no
   `fetch` (:2183-2186). Store reads go through hooks the state modules export
   (`FormatCheck.tsx:5, :230` is the precedent).
2. **`keyboard-floor.test.ts`**: exactly one focus treatment per focusable (:332-350) — the pill
   takes the known-surface ring (canonical instance `Footer.css:115-119`); `outline: none` in
   any of four spellings is banned (:354-370); `--accent-bright` in a ring is banned (:371-384);
   real `<button>`/`<a>` only (:400-415); the file must join the known-focusable anchor list
   (:303-320) and `DECLARES_MIN` (:432) — a micro-text pill is under 24px tall without explicit
   mins; no positive tabindex (:626-651).
3. **`App.test.tsx:2033-2041`** asserts exactly ONE `[aria-live]` in the document, polite, named
   `card-detail-announcement`. The pill adds the app's second (UX-DR45 authorises three total:
   pill, agent-view heading, pin). Update the pin to the exhaustive two-region form — do not
   weaken it to `>= 1`.
4. **`copy-rules.test.ts`**: any module whose 2+-word string literals reach JSX/`aria-*` must be
   in `COPY_MODULES` — the pill's `copy.ts` is a new entry (currently 8 modules).
5. **`copy-tails.test.ts:284-289`**: currently asserts the pill is *deliberately unasserted* AND
   `socket.ts` contains no `/pill/i` outside comments. AC 13 converts the first half into a real
   mirror of the retrying-quietly clause against the shipped copy; the second half stands —
   **never add the word "pill" to `socket.ts` outside a comment**.
6. **`token-usage.test.ts`**: the pill's stylesheet is pre-authorised to spend all three status
   colours (:1012-1013) and is NOT in `CALM_STYLESHEETS` — do not add it there. Token count 69
   is pinned twice (tokens.test.ts:321, token-usage.test.ts:1170); DESIGN.md's
   `components.connection-pill` block resolves entirely to existing tokens (`--surface-panel`,
   `--border-hairline`, `--radius-pill`, the three semantics, spacing) — expect the count to
   stay, and owe a written reason plus both pins if it moves (c4-6's `dfc-flip` precedent).
7. **stylelint motion bans** (tokens.css:305-312): `animation-iteration-count` ≠ 1, `infinite`,
   alternate directions are banned repo-wide — *"The connection pill (c5-7) is the component this
   exists to protect."* The dot takes NO transition and NO animation; nothing to register in the
   reduced-motion inventory because no motion ships.
8. **`store-writes.test.ts` / `posture.test.ts`**: no new store, no new writer, no network
   identifier anywhere near the pill. Untouched.
9. **Scan authority**: all meta-suites read `git ls-files` — `git add` new files before trusting
   green (standing blind spot, every header).

### The pattern to copy (solved problems — do not invent)

- **Live region**: `CardDetail.tsx:592` — a `visually-hidden` `<p aria-live="polite">` OUTSIDE
  the labelled region, empty at rest, content captured **during render** via the render-time
  adjustment pattern (`CardDetail.tsx:292-320`; `react-hooks/set-state-in-effect` rejects the
  effect spelling). The pill announces on state *transition* only.
- **Focus ring**: `Footer.css:115-119` — `outline: var(--focus-ring-width) solid
  var(--focus-ring); outline-offset: var(--focus-ring-offset);` under `:focus-visible`.
- **Status dot**: `Panel.tsx:117` + `Panel.css:110-118` — `<span className="…-dot"
  aria-hidden="true" />`, sized/rounded via tokens, `flex-shrink: 0`. The pill's is 8px (not the
  Panel's 6) per DESIGN.md `dot-size`, and carries **no glow** (glows mark agent attention;
  UX-DR29's dot is plain semantic fill).
- **Store-reading container**: `FormatCheck.tsx` — hook exported by the state module, container
  file in `CONTAINERS` with its import-roots entry.
- **Component layout**: `<Name>/{<Name>.tsx,.css,copy.ts,<Name>.test.tsx}` colocated, kebab-case
  class names, stylesheet imported only by its own component (c2-6 conventions).
- **App-level socket driving**: `App.test.tsx:76-118` — `FakeSocket` +
  `vi.stubGlobal('WebSocket', FakeSocket)` in `beforeEach` (:409), `connect()`, `drop()`,
  `advance(ms)`, `settle()`; the disconnected-panel describe at :2224+ (`await
  advance(DISCONNECTED_AFTER_MS)` after driving 4 failures) is exactly the walk AC 18 extends
  to the pill.

### Grep-own-key: the expected c5-7 hits and their dispositions (verify at Task 0)

*Frontend prose predicting this story (rewrite as shipped truth in Task 5):*
`socket.ts:160`, `systemState.ts:49`, `connection.ts:24`, `tokens.css:311`,
`ui/README.md:569`, `StatePanel/states.ts:277`, `copy-tails.test.ts:24/:235/:284` (AC 13
converts), `shell.test.ts:484/:488/:2004/:2421/:2565` (comment updates only where the truth
changes — the corner-pill tolerance becomes "and c5-7 shipped exactly that"),
`ui/tests/fixtures/css/{motion,shell}-violation.css` comments.

*Backend prose making a claim this story's spec contradicts (Q6 rules the rewrite):*

- `src/companion/app/routes/agent_events.py:40` — "`connected_count` remains for the c5-7
  connection pill, which wants the other number."
- `src/companion/app/state.py:436` — "this property waits for c5-7's connection pill, which
  wants a live gauge"; `state.py:548` — "c5-7's connection pill asks the question this property
  actually answers."

The shipped pill consumes **client-side connection status + deck name only** (FR-15, UX-DR29);
no count, no gauge, no backend read. These are falsified predictions in the c5-6 mold ("recorded
as falsified rather than silently worked around") — rewrite them honestly (candidate future
consumer: c10-1's status detail, which reads `/health`, still not a count; or "a future surface").
Prose-only → mirror rebuild + sha256 verification, Python suite count byte-identical.

### Landmines specific to this story

- **The pill must render on surfaces `App.tsx` currently branches away from.** The left slot
  renders `<StatePanel>` in five of six arms — mounting the pill inside the deck-only Fragment
  silently fails AC 1 on every panel surface and on cold open. This is why the mount is a shell
  slot (Q1), and why AC 18 pins presence on a state-panel surface.
- **`'reconnecting'` is the cold-open state.** The pill will show the caution dot before the
  first upgrade ever completes. That is correct (the loop genuinely is establishing), but the
  announcement policy (Q4) decides whether the initial settle to `'live'` announces once —
  don't let the region fire on mount for the *initial* `'reconnecting'` render itself.
- **Selector-less system-store subscription** (dw:5430): `App` re-renders wholesale on every
  system write. The pill as a container should read via a narrow hook rather than adding another
  selector-less subscription; Q5 rules whether `systemState.ts` exports one. Either way the
  entry gets a written disposition.
- **A focusable element that does nothing yet**: UX-DR47 demands a real `<button>`/`<a>` for
  interactive elements, the epic AC demands focusability, and the pill's only *action* (tooltip
  reveal) is c10-1's. Q2 rules the element shape; whatever ships must not lie to a screen
  reader about having an action it doesn't have.
- **`--accent` is not a status colour.** The pill spends `--positive`/`--caution`/`--negative`
  only; accent marks agent attention and the focus ring, nothing else (DESIGN.md:366).
- **Micro typography carries `textTransform: uppercase`** (`--type-micro`, c4-3's lesson: it
  destroys mixed-case names). The deck name must NOT pass through a micro/uppercase role —
  render the state word and the deck name in roles that preserve the name's case, or confirm
  DESIGN.md's "micro text" applies to the state word only. Check `StatChip`/deck-row typography
  for the mixed-case precedent before choosing.
- **The footer is legally load-bearing** (NFR-08): a fixed bottom-left pill must not cover the
  Scryfall/Fan-Content line at any viewport the shell supports.
- **Prose reconciliation touches `src/companion`** → plugin mirror rebuild + sha256 check
  (pre-commit enforces), Python count must not move.
- **Bundle drift is a CI gate**: c5-6's fix commit `6c2426f` exists because the SPA bundle was
  rebuilt only in the plugin mirror, not in `src/companion/app/static/`. Rebuild BOTH in the
  same commit as the source change (AC 22).

### Previous-story intelligence (c5-6, reviewed + merged 2026-08-08)

- All 9 open questions ruled by Brad pre-code, all as recommended — same protocol here: the Open
  Questions below are written for pre-Task-0 ruling, recommendations first.
- c5-6's review found ONE real bug post-implementation: a `fail()`/`schedule()` ordering gap that
  could silently halt the reconnect loop if a status callback threw. **The pill's `onStatus`
  path is exactly such a callback consumer** — keep the pill's store-read side effect-free and
  let React do the throwing-boundary work; never make `applyConnection` do more.
- Review theme two stories running: **defects live in the guard layer, not the components** —
  vacuous firing proofs, false-pass paths in brand-new guards. Feed each new/changed guard its
  actual comparison function (AC 19); the R2 discipline (planted violation RED through the FULL
  suite) is a standing C4 action item with success criteria scored against this epic.
- Windows probe-harness landmine: a subprocess `npm test` from a **lowercase drive letter**
  resolves no vitest config and reports 67 failed suites — normalise `c:` → `C:` before scoring
  any probe run. The committed vitest harness half is still owed (dw:5079, declined into a
  standalone item at c5-6 Q9) — run frontend probes as full `npm test` by hand.
- Known intermittents, sighted and recorded — do not chase: Python
  `test_list_decks_with_strategy_field` (two sightings, C5-retro fact); vitest losing one file's
  collection (~2 in 30 runs, likeliest the `devProxyRoundTrip` probe-then-bind TOCTOU, homed on
  c5-8). If either fires, record and re-run.
- Baseline after c5-6's merge (PR #58, umbrella at `44530ac`): frontend **1,812 / 67 files**,
  Python **2,770 / 1 skipped**, `gen:api` idempotent, bundle `index-DjMPYZ-a.js` 227,151 B /
  `index-B_WnaAKx.css` 20,392 B.

### Project structure notes

- New: `ui/src/containers/ConnectionPill/{ConnectionPill.tsx, ConnectionPill.css, copy.ts,
  ConnectionPill.test.tsx}`.
- Modified: `ui/src/components/AppShell/{AppShell.tsx, AppShell.css, AppShell.test.tsx}` (the
  slot, per Q1), `ui/src/App.tsx` (+`App.test.tsx`), `ui/src/state/systemState.ts` (narrow hook,
  per Q5), `ui/tests/shell.test.ts` (CONTAINERS), `ui/tests/keyboard-floor.test.ts`,
  `ui/tests/copy-tails.test.ts` (AC 13), copy-rules `COPY_MODULES`.
- Prose-only: `socket.ts`/`connection.ts`/`tokens.css`/`states.ts`/`ui/README.md` headers;
  `src/companion/app/{state,routes/agent_events}.py` per Q6 (+ mirror);
  `_bmad-output/planning-artifacts/epics-companion-app.md` (UX-DR40 enumeration) and
  `ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md` (Tab-order cell + pill copy
  row); `deferred-work.md`; `sprint-status.yaml`.
- No Python behaviour change, no wire change (`gen:api` stays a no-op), no new dependency
  (`package-contract.test.ts`).
- Web research: none required — no new library enters; every mechanism (zustand read, live
  region, focus ring, fake-timer socket driving) has a shipped in-repo precedent named above.

### References

- Epic: `epics-companion-app.md:2578-2609` (Story 5.7), `:856-871` (Epic 5), `:99` (FR-15),
  `:727` (FR-15 split with Epic 10), `:3548-3576` (c10-1 — the deferred tooltip),
  `:495-498` (UX-DR29), `:589-628` (UX-DR40 + the re-homing note), `:655-659` (UX-DR45),
  `:661-667` (UX-DR46/47)
- UX: `DESIGN.md:299-303` (connection-pill material), `:366-368` (accent vs semantic),
  `:445` (composition note — pill has no mock precedent); `EXPERIENCE.md:43, :67, :97,
  :112-119` (per-state pill behaviour table), `:138-158` (interaction + live regions)
- Frontend: `ui/src/state/socket.ts:91-166, :336-341`, `systemState.ts:49-97, :150`,
  `connection.ts:83`, `deck.ts:143, :422, :469-486, :554`, `App.tsx:409-488, :566`,
  `AppShell.tsx:51-104, :127-197`, `Footer.css:115-119`, `CardDetail.tsx:292-320, :583-592`,
  `Panel.tsx:117` + `Panel.css:110-118`, `FormatCheck.tsx:5, :230`
- Guards: `shell.test.ts:1222-1353, :1926-2124, :2183-2186`, `keyboard-floor.test.ts:263-461,
  :626-651`, `App.test.tsx:2033-2041, :2224+`, `copy-tails.test.ts:284-289`,
  `token-usage.test.ts:1012-1019, :1170`, `tokens.test.ts:321`, `tokens.css:305-323`
- Ledger: `deferred-work.md:4595-4600, :5349-5355, :5428-5431`
- Process: sprint-status `action_items` — C4 R1 (Dev Notes < 41 KB; this section ≈ 13 KB),
  R2 (firing proofs), grep-own-key, probe-harness (open), plugin-mirror-from-ui (open)

## Open questions for Brad (recommendations first — rule before code)

1. **Where does the pill mount, and what is its DOM position?** (This story owns dw:4597.)
   Recommend: a new `AppShell` prop (the skip-link precedent for "no slot exists"), rendered as
   a sibling **between `</main>` and `<footer>`** — document order makes it the last Tab stop
   before the footer links (satisfying UX-DR40 and c10-1's wording) — visually pinned
   bottom-left, the corner-pill shape `shell.test.ts`'s full-window-layer guard already
   deliberately tolerates (:484, :2421, fixtures:256). Fixed-position corner pinning with an
   inset that clears the footer line; UX-DR40's enumeration and EXPERIENCE.md's Tab-order cell
   updated in the same commit. Alternative — in-flow last child of the left column — puts it
   *before* the entire right column in Tab order, contradicting all three artefacts.
2. **What element is the pill, given its only action (tooltip) is c10-1's?** Recommend: a real
   `<button type="button">` per UX-DR47, ≥24×24, accessible name = the pill's own text,
   activation a documented no-op until c10-1 attaches the describedby reveal — the epic AC
   requires focusability now and c10-1 requires this exact element later; shipping a
   non-focusable `<div>` now means re-doing the element and the Tab-order record in Phase 2.
   Alternative (focusable `<span tabindex="0">`) violates UX-DR47's letter.
3. **The pill's words** (specified nowhere; voice rules apply; AC 12 writes them into
   EXPERIENCE.md). Recommend, state word first, deck name appended when present after an em
   dash, mixed-case preserved: live → `Connected — {deck}` / `Connected`; reconnecting →
   `Reconnecting — {deck}` / `Reconnecting`; down → `Backend gone — retrying quietly` (deck name
   omitted in the down state: the Disconnected panel owns the guidance, the pill owns the
   status, and a stale deck name beside "gone" reads as a claim the app can't honour — though
   the deck content itself stays rendered per UX-DR35). No exclamation marks, no ellipsis
   animation, no "…" suffix that implies motion.
4. **Announcement policy for the live region.** Recommend: announce connection-state
   *transitions* only, with the announced string = the pill's own current text; the initial
   mount render (cold-open `'reconnecting'`) does not announce; deck-name changes alone do not
   announce (the coalesced deck-refetch announcement already owns that channel per UX-DR45's
   flood rule). So a normal cold open announces once ("Connected — …") when the first upgrade
   lands.
5. **Does `systemState.ts` export a narrow `useConnection()` hook?** (dw:5430: "Home: c5-7 if
   the pill wants finer granularity.") Recommend: yes — a one-line selector hook beside
   `useSystemState()`, so the pill subscribes to the `connection` field alone instead of adding
   a second selector-less whole-store subscription; dw:5430 closed with that as the written
   disposition. The store, its writer, and `STORES` are untouched either way.
6. **The backend live-gauge prose** (`state.py:436/:548`, `agent_events.py:40` claim this story
   wants a connected-count). Recommend: rewrite honestly as falsified predictions — the pill
   reads client-side status only; the properties stay (they are consumed by the ingest response
   and tests), the claim about *who wants them* changes to "a future status surface (c10-1 reads
   /health, not this count)". Prose-only, mirror rebuilt, Python count byte-identical.
   Alternative — leaving the stale claim — inverts what the ledger is for (the C4 grep-own-key
   action item's exact rationale).

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context), via Claude Code / BMad `dev-story`.

### Debug Log References

**All six open questions ruled by Brad AS RECOMMENDED, before any code** (2026-08-08) — the
c5-5 / c5-6 protocol repeated a third time.

**Baselines verified at Task 0**, every one matching the story's stated figures: frontend
**1,812 passed / 67 files**; Python **2,770 passed / 1 skipped** (`-m "not integration"`, 54
deselected); `npm run gen:api` a no-op; bundle `index-DjMPYZ-a.js` **227,151 B** /
`index-B_WnaAKx.css` **20,392 B**.

**Grep-own-key (`c5-7` across `ui/src ui/tests src tests scripts` + `ui/README.md`) — every hit
dispositioned:**

| Site | Disposition |
| --- | --- |
| `ui/src/state/socket.ts:160` | Prediction fulfilled → rewritten as shipped truth (comment only; `socket.ts` still contains no `pill` outside comments) |
| `ui/src/state/systemState.ts:49` | Fulfilled → rewritten; the "second consumer" arrived one story later and needed no new store |
| `ui/src/state/connection.ts:24` | Fulfilled → rewritten, naming the `useConnection()` seam |
| `ui/src/styles/tokens.css:311` | Fulfilled → rewritten; the pill shipped with **no** `animation` and **no** `transition`, so nothing was registered in the reduced-motion inventory |
| `ui/src/components/StatePanel/states.ts:277` | Fulfilled → rewritten; the `down` copy is TRUE only while `RETRIES_QUIETLY.disconnected` is `true`, and `copy-tails.test.ts` now holds the two together |
| `ui/README.md:569` | Fulfilled → annotated; c5-7 is the first Epic 5 member of `src/containers/` |
| `ui/tests/copy-tails.test.ts:24 / :235 / :284` | **CONVERTED** per AC 13 — the deliberate non-assertion became a real mirror (see below) |
| `ui/tests/shell.test.ts:484 / :488 / :2421` | Anticipation held byte for byte → rewritten as "c5-7 shipped exactly that shape" |
| `ui/tests/shell.test.ts:2004 / :2565` | Still accurate as written → left unchanged |
| `ui/tests/token-usage.test.ts:1014` | Pre-authorisation exercised → annotated; `ConnectionPill.css` deliberately NOT added to `CALM_STYLESHEETS` |
| `ui/tests/fixtures/css/{motion,shell}-violation.css` | Annotated: both fixtures now describe a component that exists |
| `src/companion/app/state.py:436 / :548` | **FALSIFIED** (Q6) → rewritten. The pill wants no live gauge |
| `src/companion/app/routes/agent_events.py:40` | **FALSIFIED** (Q6) → rewritten |
| `tests/unit/companion/test_ws.py:985 / :990 / :1038` | **NOT IN THE STORY'S EXPECTED SET — found by the grep.** Same falsified live-gauge claim, in a Python test docstring. Rewritten; it is now the second falsified prediction that class docstring records |

Two further prose sites were falsified by this story that no `c5-7` grep could have found:
`SkipLink.tsx:80` and `CardGrid/copy.ts:47` each asserted *"CardDetail's single polite region
stays the only one in the app"*. Both rewritten (plus two copies of the same sentence inside
`copy-rules.test.ts`'s registry reasons).

**R2 firing proofs — 15 planted violations, every one shown RED through the FULL `npm test`**
(never a standalone file run; each probe reverted via `git checkout --` against the staged file).
What each assertion actually compares:

| # | Planted violation | RED | The assertion, and what it compares |
| --- | --- | --- | --- |
| P1 | Delete the pill's `min-width: 24px` | 1 | keyboard-floor's `DECLARES_MIN`: reads every shipped stylesheet mentioning `.connection-pill` and requires BOTH `min-width: 24px` and `min-height: 24px` |
| P2 | Swap the ring's `outline-offset` for `0` | 1 | `treatmentOf('connection-pill')` reclassifies the rule from `KNOWN_SURFACE` to `OVER_ART`; the tier pin compares the derived label set |
| P3 | Draw the ring from `--accent-bright` | 1 | Token IDENTITY inside every `:focus-visible` body — the two tokens carry one hex, so no eye check could see this |
| P4 | Drop `copy.ts` from `CONTAINERS` | 3 | `coversExactly()` compares `git ls-files 'src/containers/*'` (test files excluded) against the declared list, plus the length pin at 27 |
| P5 | Understate the pill's declared imports | 1 | Every `from '…'` specifier parsed out of the comment-stripped source, sorted, compared to the declared array |
| P6 | Unregister the copy module | 2 | `findCopyOutsideACopyModule` walks 2+-word literals reaching JSX/`aria-*` in unregistered files |
| P7 | Soften `down` off "retrying quietly" | 4 | The converted copy-tails mirror (artefact clause vs shipped string), the EXPERIENCE.md quote check, and the DOM assertion |
| P8 | Give "Reconnecting" an ellipsis | 3 | The artefact-verbatim check plus the explicit no-ellipsis assertion — the motion ban expressed in punctuation |
| P9 | Mount the pill in the deck-only Fragment | 4 | The AC 1 surface tests: state-panel, cold open, disconnected, and the walk |
| P10 | Move the slot above `<main>` | 9 | `compareDocumentPosition` in `AppShell.test.tsx` plus every skip-link corridor test — the DOM-position ruling is load-bearing far beyond its own test |
| P11 | Let the region speak on mount | 5 | The empty-at-rest and no-announcement-on-cold-open assertions, at both component and App level |
| P12 | Add an undeclared third live region | 3 | The **exhaustive** two-region pin — a `>= 1` form would have passed |
| P13 | Read the deck name off the surface | 2 | The `'down'`-state test: the slice still holds the deck, so this compares the RULING, not the capability |
| P14 | Give the dot a pulse | 1 | The repo-wide `animation-iteration-count`/`infinite` ban, on the component it was written to protect |
| P15 | Point `is-down` at `--caution` | **0 → 1** | **See below.** |

**⚠️ P15 CAME BACK GREEN — a real hole, found by the probe discipline and not by design.**
Pointing the down-state dot at `--caution` passed the entire 1,866-test suite. The cause is
structural: `ConnectionPill.test.tsx` runs in jsdom, which evaluates no stylesheet, so every DOM
assertion about the dot can only reach the CLASS — it proves `'down'` renders `is-down` and stops.
The one component in the app whose whole job is to signal by colour could have shipped the wrong
colour on the state that matters most. **Closed** by a source-reading guard in `shell.test.ts`
binding all three classes to their tokens AND asserting the dot's complete fill set is exactly the
three semantics (a swap satisfies any per-class "is it a status token" check; a fourth rule
pointing at `--accent` would satisfy all three per-class assertions and still be wrong). P15
re-run: **RED**. The general shape — class→token bindings are invisible to jsdom — is recorded in
the ledger and homed on the C5 retro.

**A measured difference, recorded rather than hidden:** the pill's DOM text is `pillText()` byte
for byte (`Connected — Sultai Midrange`), but the computed accessible name is
`Connected—Sultai Midrange` — the accname algorithm trims each contributing text node before
joining, so the separator's spaces do not survive. Not repaired: the only repair is to give up the
typography split that keeps the deck name mixed-case, and no screen reader voices the difference.
Both forms are pinned.

**The Tab-corridor figures moved and were NOT re-measured.** The pill is an always-present stop
inside the header→footer corridor, so c4-11's 40-deck sweep (206 max / 78 median / 102.0 mean;
105 removed by the skip link, 101 left) gains exactly +1 everywhere. The suite's own pins were
recomputed from the DOM rather than relaxed; the sweep was not re-run. Both artefacts carry the
note; **homed on c8-6**, which already owns the revisit flag for this corridor.

**Voice reading (UX-DR33's undecidable half, discharged by a human-equivalent read as the copy
guard's own header requires):** the three strings carry no exclamation mark, no emoji, no
ellipsis, and no blame — *"Backend gone"* states a fact about a process, and *"retrying quietly"*
is true of the shipped loop rather than reassuring.

**Known intermittents:** neither fired. No vitest collection loss across ~20 full runs; the Python
`test_list_decks_with_strategy_field` flake did not appear.

### Completion Notes List

- **The pill** — `src/containers/ConnectionPill/`: an 8px `aria-hidden` static dot, the word for
  the state, and the active deck's name, bottom-left on **every** surface, as a real
  `<button type="button">` that is the last Tab stop before the footer links.
- **Q1 / dw:4597 CLOSED.** The three artefacts were never in conflict — UX-DR40 and c10-1 describe
  **Tab order**, `DESIGN.md:479` describes the **screen**. A new `AppShell` slot between
  `</main>` and `<footer>` satisfies both, with `position: fixed` bottom-left and a
  `calc(var(--space-gutter) + var(--space-6))` inset clearing the footer strip — **no geometry
  literal**. `shell.test.ts`'s full-window-layer guard had anticipated this exact shape in
  2026-07-28's review; the anticipation held byte for byte.
- **Q5 / dw:5430 CLOSED.** `systemState.ts` grew a one-line `useConnection()` selector hook, so
  the pill subscribes to one field rather than adding a second selector-less whole-store
  subscription. `App`'s own subscription is deliberately unchanged (it reads all three fields).
  No new store, no new writer, `STORES` untouched.
- **AC 13 CONVERTED, not deleted.** `copy-tails.test.ts:284`'s deliberate "leaves the PILL to
  c5-7" became a real two-sided mirror: the artefact's promise against the pill's shipped `down`
  copy AND against `RETRIES_QUIETLY.disconnected`. Softening either end is now red. The half that
  stands unchanged is the other one — `socket.ts` still contains no `pill` outside comments.
- **The typography split is a gate's decision, not taste.** `DESIGN.md` assigns
  `{typography.micro}` to the state word *and* the deck name; micro drags
  `text-transform: uppercase`, and `SULTAI MIDRANGE` destroys the name the pill exists to show.
  The state word keeps micro, the deck name takes `{typography.body}` `{colors.text-secondary}` —
  c4-3's lesson and c4-10's repeat of it, with the shipped precedent one file away
  (`.app-shell-kicker` vs the header's deck name). `DESIGN.md:479` amended in the same commit.
- **The token inventory did not move** (69, both pins untouched): every declaration resolves to an
  existing token. No `--connection-pill-*` token was needed.
- **No motion of any kind ships** — no `animation`, no `transition`, so nothing was owed to the
  reduced-motion inventory.
- **Scope fence honoured**: no tooltip, no `GET /health`, no `aria-describedby`, no client count.
  The element is a real `<button>` so c10-1 can attach its reveal without re-doing the element or
  the Tab-order record, and it claims no `aria-expanded`/`aria-pressed`/`aria-haspopup`/`title` it
  does not have (asserted).
- **Backend changes are prose-only and byte-identical in behaviour**: Python **2,770 passed / 1
  skipped**, unchanged from baseline. Plugin mirror rebuilt and **sha256-verified** on all four
  touched files (`state.py`, `agent_events.py`, and both new bundle assets), with no stale assets
  left in the mirror.
- **Bundle rebuilt in the same commit as the source** (AC 22 — c5-6's CI drift not repeated).
  **Both** assets changed: JS `index-DjMPYZ-a.js` 227,151 B → `index-4i3k0aJS.js` **228,273 B**;
  CSS `index-B_WnaAKx.css` 20,392 B → `index-D0jCbtgu.css` **21,445 B**.
- **Gates all green**: frontend **1,867 passed / 69 files** (from 1,812 / 67);
  Python **2,770 / 1 skipped** (unchanged); `npx tsc -b --force`, eslint, stylelint, prettier,
  `pre-commit run --all-files` (including the mirror sync) all clean; `npm run gen:api` a genuine
  no-op (re-run, zero diff under `ui/src/api`).

### File List

**New**

- `ui/src/containers/ConnectionPill/ConnectionPill.tsx`
- `ui/src/containers/ConnectionPill/ConnectionPill.css`
- `ui/src/containers/ConnectionPill/ConnectionPill.test.tsx`
- `ui/src/containers/ConnectionPill/copy.ts`
- `ui/tests/connection-pill-copy.test.ts`

**Modified — app**

- `ui/src/App.tsx`
- `ui/src/components/AppShell/AppShell.tsx`
- `ui/src/state/systemState.ts`

**Modified — prose only (comments/docstrings)**

- `ui/src/state/socket.ts`
- `ui/src/state/connection.ts`
- `ui/src/components/StatePanel/states.ts`
- `ui/src/containers/SkipLink/SkipLink.tsx`
- `ui/src/containers/CardGrid/copy.ts`
- `ui/src/styles/tokens.css`
- `ui/README.md`
- `src/companion/app/state.py`
- `src/companion/app/routes/agent_events.py`
- `tests/unit/companion/test_ws.py`

**Modified — tests and guards**

- `ui/src/App.test.tsx`
- `ui/src/components/AppShell/AppShell.test.tsx`
- `ui/tests/shell.test.ts`
- `ui/tests/keyboard-floor.test.ts`
- `ui/tests/copy-rules.test.ts`
- `ui/tests/copy-tails.test.ts`
- `ui/tests/token-usage.test.ts`
- `ui/tests/fixtures/css/motion-violation.css`
- `ui/tests/fixtures/css/shell-violation.css`

**Modified — artefacts and tracking**

- `_bmad-output/planning-artifacts/epics-companion-app.md`
- `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md`
- `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/c5-7-connection-pill.md`

**Rebuilt (mechanical)**

- `src/companion/app/static/index.html`
- `src/companion/app/static/assets/index-4i3k0aJS.js` (replaces `index-DjMPYZ-a.js`)
- `src/companion/app/static/assets/index-D0jCbtgu.css` (replaces `index-B_WnaAKx.css`)
- `plugin/**` (mirror, rebuilt by the pre-commit hook and sha256-verified)

## Change Log

| Date | Change |
| --- | --- |
| 2026-08-08 | Story implemented. All 6 open questions ruled as recommended before code. Connection pill shipped: static dot + state words + deck name, bottom-left on every surface, second polite live region, last Tab stop before the footer. dw:4597 closed by decision, dw:5354's pill clause paid, dw:5430 closed. 15 R2 firing proofs, all RED — P15 found and closed a real coverage hole (class→token binding invisible to jsdom). Frontend 1,812 → 1,867; Python unchanged at 2,770. Status → `review`. |
