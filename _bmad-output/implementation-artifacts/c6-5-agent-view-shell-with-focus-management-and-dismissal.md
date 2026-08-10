---
baseline_commit: bf7bda05018d95ef41ac648c5f80870b09ea215b
---

<!--
  Story context created 2026-08-10 by create-story (ultimate context engine analysis).
  Sources: epics-companion-app.md (Story 6.5 :2808-2848, Epic 6 :2664-2669, UX-DR catalogue
  :327-723), ARCHITECTURE-SPINE 2026-07-25 (AD-6/7/11/12/13), DESIGN.md (:270-278, :451,
  :471), EXPERIENCE.md (:51, :90, :122-123, :141-146, :153-159, :165), shipped ui/ source,
  c6-3 + c6-4 story records, deferred-work.md (dw:1457-1482, dw:4766-4773).
-->

# Story c6-5: Agent view shell with focus management and dismissal

Status: done

## Story

As Brad reading agent content,
I want it presented as a full-window panel I can dismiss with Esc,
So that it commands attention while it's open and gets out of the way when I'm done.

## The story in one paragraph

Four epics of shipped code have been writing letters to this story: `AppShell` reserves an
`overlay` slot that renders nothing until now (`AppShell.tsx:134`), the CSS for that slot is
already built and guarded (`.app-shell-overlay` — `position: fixed; inset: var(--space-gutter);
z-index: 20`), the Esc-layering contract is written in three places verbatim ("the agent view
registers its own `keydown` on `document` in the CAPTURE phase, closes itself, and calls
`stopPropagation()`"), and the reduced-motion inventory holds a line that says `(c6-5)`. This
story finally answers those letters. It builds the **content-agnostic modal shell** every agent
view will live in — scrim + 16px blur, inset 32px, raise-elevated panel, "AGENT VIEW" kicker,
`h2` heading, summary count, "Close · esc" pill — with the app's **first and only focus trap**,
focus-to-heading on open, focus-restore on close, and three dismissal gestures that never clear
content. It does **not** wire pushes (c6-6), render suggestion rows (c6-7), build nav pills
(c6-8), or measure the 250 ms budget (c6-9). It is the repo's first `role="dialog"`, the first
consumer of `--scrim`, and the story that must move four shipped guard pins in the same commits
as the code they exist to catch.

## Acceptance Criteria

*(Verbatim from `epics-companion-app.md:2814-2848`, numbered for citation.)*

1. **Given** an agent view opens **When** it renders **Then** it is a full-window scrim with a
   16px backdrop blur, inset 32px, containing a panel with the raise elevation, carrying an
   "AGENT VIEW" accent kicker, a heading title, a summary count, and a right-aligned
   "Close · esc" pill (UX-DR23) **And** the body scrolls while the shell does not.
2. **Given** the view is open **When** its semantics are inspected **Then** it is
   `role="dialog" aria-modal="true"` labelled by its heading `h2`, and **Tab cycles within it**
   (UX-DR23, UX-DR44).
3. **Given** the view opens **When** focus moves **Then** it moves to the view's heading
   (UX-DR46).
4. **Given** the view is dismissed by the close pill, Esc, or a click on the scrim outside the
   shell **When** it closes **Then** focus returns to the element focused before the view took
   it — never to `document.body` (UX-DR39, UX-DR46).
5. **Given** the view is dismissed **When** its content is considered **Then** dismissal
   **never clears it** — the view remains re-openable for the rest of the session (UX-DR34).
6. **Given** an agent view is open **When** anything else tries to open over it **Then**
   nothing does — the overlay stack is exactly one level deep (UX-DR38).
7. **Given** the view enters **When** the animation runs **Then** it fades and rises 8px over
   the bloom duration, **on top of an already-complete layout** (UX-DR23) **And** under
   `prefers-reduced-motion` it appears in place (UX-DR42).
8. **Given** a card tile inside an agent view **When** its live marker renders **Then** it uses
   `accent`, not `accent-dim`, because tiles here sit on `surface-overlay` where `accent-dim`
   fails the 3:1 floor (UX-DR6).

**Scope boundaries (the epic's own split — build none of these):** auto-open on push and
replace-in-place are **c6-6** (:2858-2866); the state-panel-behind-an-open-view rules are
**c6-6** (:2876-2879); suggestion rows and their inspection contract are **c6-7**; nav pills,
unread markers, re-open and kind switching are **c6-8**; the 250 ms measurement is **c6-9**.

## Tasks / Subtasks

- [x] **Task 0 — Baselines, branch, and grep dispositions** (protects everything)
  - [x] Branch `feat/companion-c6-5-agent-view-shell` cut from `feat/companion-c6` at or after
        `bf7bda0` (c6-4's merge, PR #66). Note: the working tree on the old c6-4 branch carries
        an uncommitted `sprint-status.yaml` merge-record edit — carry it, don't lose it.
  - [x] Frontend baseline: `npm test` from an **uppercase** drive path; expect
        **1,871 passed / 69 files**; validate the collected count before trusting any run.
  - [x] Python baseline: `uv run pytest -m "not integration"` — expect **2,907 passed /
        1 skipped / 55 deselected**; this story must leave it **unmoved** (no backend change).
  - [x] `grep -rn "c6-5"` across `src/`, `ui/src/`, `tests/`, `scripts/`, `docs/`,
        `deferred-work.md`; build the dispositions table (≈28 known sites — most are contract
        prose that this story *fulfils* and must then re-verify for truthfulness, see Task 4).
- [x] **Task 1 — The agent-view store** (AC 5, AC 6)
  - [x] `ui/src/state/agentView.ts` + colocated test: the 7th zustand store, shaped per Q2's
        ruling — an open/closed status plus retained content that `close()` **never clears**;
        exported `resetAgentView()` for tests (docstring: tests-only, the c6-3 precedent).
  - [x] Register it in `ui/tests/store-writes.test.ts`'s `STORES` table (one writer module,
        reason > 40 chars) — **same commit as the store**.
  - [x] Pin AC 6 structurally: the store can hold at most one open view (a scalar, not a
        stack) — the type makes a second overlay level unrepresentable.
- [x] **Task 2 — The shell container** (AC 1, AC 2)
  - [x] `ui/src/containers/AgentView/` — `AgentView.tsx`, `AgentView.css`, `copy.ts`,
        `AgentView.test.tsx`. **Containers, not components** — `src/components/` is closed by
        set-equality guard and `ui/README.md:567-571` homes c6-5..c6-8 here.
  - [x] Chrome per `DESIGN.md:270-278` + `:471`, all through shipped tokens: scrim wrapper
        `background: var(--scrim)` + `backdrop-filter: blur(16px)` (literal — no token exists;
        cite DESIGN.md within a sentence); panel `var(--surface-panel)`, border
        `1px solid var(--border-hairline)`, `var(--radius-lg)`, `box-shadow:
        var(--shadow-raise)` (allowed-list admits only token shadows); header row = kicker in
        `--type-micro`/`--accent` (uppercase, `--tracking-micro`), `h2` title in
        `--type-heading`, summary count in `--type-body`/`--text-tertiary`, close pill
        right-aligned; body is the one scroll container (`overflow-y: auto` on the body, not
        the shell).
  - [x] The close pill is a real `<button>` on the nav-pill spec (`DESIGN.md:260-269`, `:451`):
        `--surface-panel` bg, `1px solid var(--border-strong)`, `--radius-pill`, `--type-label`,
        hover/focus border `--accent-dim` + text `--accent-bright` + `box-shadow: var(--glow)`,
        ≥ 24×24px hit box, known-surface focus ring (`outline: var(--focus-ring-width) solid
        var(--focus-ring); outline-offset: var(--focus-ring-offset)`). Padding per Q4's ruling
        (the spec's `7px 14px` is enumerated drift and a stylelint build failure).
  - [x] Semantics: `role="dialog" aria-modal="true"` with `aria-labelledby` pointing at the
        `h2`; the heading carries `aria-live="polite"` (EXPERIENCE.md:159 — it is one of the
        three live regions; no announcement fires on first open, focus-to-heading is the
        open-time signal — c6-6 owns replacement announcements).
  - [x] Copy `"AGENT VIEW"` and `"Close · esc"` live in `copy.ts`, registered in
        `ui/tests/copy-rules.test.ts`'s `COPY_MODULES` — **same commit**.
  - [x] Props are content-agnostic: `{title, count, children, …}` — the shell must render an
        arbitrary fixture child; nothing in it knows what a suggestion is.
- [x] **Task 3 — Focus management and dismissal** (AC 2, AC 3, AC 4)
  - [x] On open: capture `document.activeElement`, then move focus to the heading via the
        shipped `focusHome()` (`containers/focusHome.ts` — it already does the
        `tabIndex = -1` + once-blur-cleanup dance; SkipLink is the precedent).
  - [x] The focus trap (the app's first — `focusHome.ts:38-46` confirms none exists): a
        `keydown` Tab handler on the dialog root that computes the focusables in document
        order and wraps at both ends. No positive `tabindex` anywhere (keyboard-floor pins
        this); no `@testing-library/user-event` (not installed, deliberately) — assert the
        handler's wrap logic directly with `fireEvent`/`dispatchEvent`.
  - [x] Esc: **document-level `keydown` in the CAPTURE phase**, registered only while open,
        guarding `isComposing`/`defaultPrevented` (mirror `CardDetail.tsx:369-380`), that
        closes the view and calls `stopPropagation()` — the contract written at
        `CardDetail.tsx:89-101` and `inspection.ts:55-67`. **This story finally tests the
        layering half those comments declare untestable**: Esc with a view open and a pin
        active closes the view and leaves the pin (EXPERIENCE.md:141, Flow 1 :188).
  - [x] Amend `ui/tests/keyboard-floor.test.ts:602-632` **in the same commit**: the listener
        set becomes two entries (CardDetail bubble + AgentView capture), and the no-capture
        assertion gains the AgentView exemption it was written to one day admit
        (dw:4766-4773). Keep the non-vacuity anchors honest.
  - [x] Scrim-click dismissal per Q3's ruling (target check so a drag that *ends* on the
        scrim doesn't dismiss); the pill's `click` and Enter/Space (native button) also close.
  - [x] On close: restore focus to the captured element; if it is no longer connected, the
        Q5 fallback. Never `document.body` — three-arm test coverage on the SkipLink
        precedent's shape (`SkipLink.test.tsx:202-272`).
- [x] **Task 4 — Motion, App wiring, and prose-sync** (AC 1, AC 6, AC 7)
  - [x] Entry animation: fade (opacity 0→1) + rise (`translateY(8px)`→0) over
        `var(--motion-bloom) var(--ease-glide)`, on the already-complete layout (the animation
        is presentation on top of the mounted DOM — nothing waits for it). The 8px distance is
        prose-only (`DESIGN.md:471`) — cite it beside the literal.
  - [x] Register the reduced-motion fallback **in `tokens.css`'s single block** (the rise is a
        transform — zeroed durations make it instant, not absent, so it must be registered:
        `transform: none !important` on the shell's selector) and move
        `ui/tests/token-usage.test.ts:2478-2506`'s enumerated shipped-motion pin (currently 4
        entries) **in the same commit**. `ui/README.md:922-923` predicted exactly this.
  - [x] Wire `App.tsx`: pass `overlay={…}` conditionally from the store (per Q1) — absent
        when closed so the slot renders NOTHING (`AppShell.tsx:134-139`'s click-swallower
        warning; `filled()` gates the wrapper). `AppShell.tsx` itself is **not edited** — the
        c2-9 displacement pattern, tenth application.
  - [x] AgentView.css must **not** declare its own full-window fixed layer —
        `.app-shell-overlay` owns `position: fixed; inset: var(--space-gutter); z-index: 20`,
        and `shell.test.ts:952-957` fails a second one. The shell fills the slot (`height:
        100%` against the slot's box), it does not position itself.
  - [x] Prose-sync (R2, applied not quoted): the shipped comments that say "No overlay exists
        yet, so this story cannot test the layering" (`CardDetail.tsx:99-101`,
        `inspection.ts:65-67`, `CardDetail.test.tsx:521-524`) are falsified by this diff —
        update them to record that c6-5 landed the overlay and the layering test now lives in
        AgentView's suite. Their contract half stays verbatim. Likewise `focusHome.ts:65`'s
        "the only DOM id in `ui/src`" once the heading gains its `useId()` id (Landmine 15).
- [x] **Task 5 — Planted red** (per Q6's ruling on harness)
  - [x] Plant: remove the `stopPropagation()` from the capture-phase Esc listener (the exact
        regression dw:4766 was written about — one Esc would close the view AND release the
        pin). Full `npm test`, uppercase drive, **collected count validated before scoring**;
        predict the layering test + the keyboard-floor listener assertions stay green (they
        read source for the listener's existence, not its body — record what fires and what
        can't). Revert; verify `git diff --exit-code` clean on the planted file.
- [x] **Task 6 — Gates, artifacts, ripple, ledger**
  - [x] `npm run lint` (eslint + stylelint), `npm run typecheck`, `npm run format:check`,
        `npm test` strictly > 1,871; Python suite unmoved at 2,907 / 1 / 55.
  - [x] Runtime diff ⇒ rebuild: `npm run build` (lands in `src/companion/app/static/`,
        `emptyOutDir` — never hand-edit) then `uv run python -m scripts.build_plugin`;
        sha256-verify mirrors; rebuild AFTER the last edit including review patches (the
        most-repeated failure mode of the companion epics).
  - [x] Ripple sweep — grep the CLAIM, not the sentence (three-times-learned lesson; predicted
        sites: the four guard pins from Tasks 1-4, the four prose-sync sites, `ui/README.md`'s
        container inventory if it enumerates, `tokens.css`'s inventory comment line for c6-5).
        Build the dispositions table; expect to find more than predicted.
  - [x] Ledger reconciliation: dw:4766-4773 (capture-reservation guard) gains its
        firing-proof/fulfilment line; dw:1457-1471 (shell guards are static readers — "when
        reviewing c6-5's agent view, check the composed result") is **review guidance, stays
        open**, cite it in the PR description; the image-coalescing and `agentEventOf` entries
        are **c6-7's**, annotate NOT TRIGGERED only if the grep drags them in.
  - [x] Dev Notes KB self-check (10–20 KB band); record suite arithmetic before/after.

*(Per the standing workflow: implement Tasks 0–6, set status `review`, STOP — Brad runs the
three-layer review and raises the PR into `feat/companion-c6`.)*

## Dev Notes

### What is already shipped (verified at story creation — the letters this story answers)

- **The mount point exists and is guarded.** `AppShell.tsx:139` takes `overlay?: ReactNode`;
  `:244` renders `filled(overlay) ? <div className="app-shell-overlay">…` — absent ⇒ NOTHING
  (the click-swallower warning at `:134-139`). `AppShell.css:223-271` ships the slot:
  `position: fixed; inset: var(--space-gutter); z-index: 20`, `:empty { display: none }`, with
  c6-5-addressed comments explaining `fixed` (not `absolute`) and `--space-gutter` (not
  `--space-6` — deliberate, stays aligned with the shell frame). Guards at
  `shell.test.ts:912-958`: inset exact, position fixed, `:empty` rule present, and
  `.app-shell-overlay` is **the only full-window fixed layer allowed in the app**.
- **The Esc contract is written in three places, identically** (`CardDetail.tsx:89-101`,
  `inspection.ts:55-68`, EXPERIENCE.md:141/UX-DR39): CardDetail's pin release is a document
  **bubble** `keydown` (`CardDetail.tsx:369-380`, guards `isComposing`/`defaultPrevented`);
  the agent view registers document **capture**, closes itself, `stopPropagation()`. Capture
  at the document beats bubble **for every target** — an element-scoped handler fails when
  focus sits on `<body>` (found at review 2026-08-05). `tests/keyboard-floor.test.ts:507-633`
  currently pins the listener set at exactly CardDetail's one entry and asserts **no capture
  anywhere** — added because a probe once landed a capture listener and nothing went red
  (dw:4766-4773). This story is the one it reserves the exemption for.
- **No modal machinery exists.** No `role="dialog"`, no `aria-modal` (except negative
  assertions in `CardDetail.test.tsx:170-177` — a different component; don't break them), no
  focus trap, no return-focus contract (`focusHome.ts:38-46` says so), no portal. `--scrim` is
  declared (`tokens.css:92`) and consumed nowhere — this story is its first consumer.
- **Focus utilities**: `containers/focusHome.ts` — `focusHome(el)` does the `tabIndex = -1` +
  `{once: true}` blur-cleanup + activeElement-verify dance; `SKIP_TARGET_ID = 'card-detail'`
  is the app's only DOM id. `SkipLink.tsx:107-122` is the never-drop-to-body unmount pattern
  (heldFocus ref → hand to `h1`). `SkipLink.css:97` sets `z-index: 10` deliberately below the
  overlay's 20.
- **Reduced motion has ONE registration point**: `tokens.css:319-434`, one
  `@media (prefers-reduced-motion: reduce)` block; durations zeroed (mechanical), transforms
  registered explicitly with `!important` (measured requirement — tokens.css imports first, so
  source order loses). The inventory comment names this story: *"Agent-view bloom (fade + 8px
  rise) → appears in place (c6-5)"* (`tokens.css:293`). The gate:
  `token-usage.test.ts:2385-2510`, `MOTION_PROPERTIES = ['transform','scale','rotate',
  'translate']`, enumerated shipped-motion pin at `:2478-2506` (4 entries today).
- **The socket deliberately drops the four view kinds** (`socket.ts:402-430`) and
  `AgentSocketOptions` has no view callback — **that stays true through this story**; c6-6
  adds the wiring. The wire kind is `suggestions` (the tool name `show_suggestions` is
  c6-4's MCP-side name, not the envelope kind).
- **Store governance**: six stores, each with exactly one writer module, pinned in
  `store-writes.test.ts:77-107`; containers never call `setState` directly. Types come only
  from `ui/src/api/schema.ts` aliases over generated `types.d.ts` (`SuggestionsEvent`
  `:1080-1094`, union inline at `:1788`) — never hand-written wire shapes.

### Design tokens this story consumes (verbatim, all shipped in `tokens.css`)

`--scrim: rgb(8 9 18 / 75%)` · `--surface-panel` · `--border-hairline` · `--border-strong` ·
`--radius-lg: 16px` · `--radius-pill` · `--space-gutter: 32px` (the slot's inset — already
applied) · `--shadow-raise` · `--glow` · `--motion-bloom: 480ms` · `--ease-glide` ·
`--type-micro`/`--tracking-micro` (kicker) · `--type-heading` (title) · `--type-body` +
`--text-tertiary` (count) · `--type-label` (pill) · `--accent` (kicker colour) ·
`--focus-ring`/`-width`/`-offset`. **The token count is pinned at 69** (`tokens.test.ts` +
`token-usage.test.ts:1172`) — this story should need **no new token**; `blur(16px)` and the
8px rise are cited literals (no token exists for either — `DESIGN.md:271` declares the blur as
a literal string; the rise is prose at `:471`). Stylelint: `box-shadow` admits only
`var(--shadow-…)`/`var(--glow)` lists; durations only `var(--motion-…)`/zero; `infinite`
banned; `outline: none` banned in all four spellings; spacing only from the 4/8/12/16/24/32/48
scale (**the nav-pill spec's `7px 14px` padding is a build failure — Q4**).

### Ruled — settled, do not re-derive

1. **The epic split is the scope** (spine has no story split; `EPIC-SPLIT.md:119` only adds
   "E9 carries the accessibility floor — acceptance criteria, not polish"). Auto-open,
   replace, announcements-on-replace, empty-push copy, state-panel-behind-view: c6-6.
   Rows/inspection/alt-text: c6-7. Pills/unread/switching: c6-8. Budget: c6-9.
2. **The four confirmed UX rulings stand** (2026-07-25): push auto-opens (so this shell's
   open verb will be driven by c6-6, not by a user gesture); inspection is hover+pin with
   focus parity; only the agent view is modal — the detail panel never traps; the overlay
   stack is one level deep, permanently.
3. **Entry animation is never inside any latency budget** (EXPERIENCE.md:165): bloom runs on
   top of complete layout; under reduced motion the two coincide. c6-9 measures; this story
   just must not create a structure where paint waits on animation.
4. **`aria-modal` + heading live region**: dialog labelled by its `h2` (EXPERIENCE.md:155);
   the heading is one of exactly three `aria-live="polite"` regions (`:159`). **No
   announcement fires on first open** — none is specified anywhere; focus-to-heading is the
   open signal. Nothing announces from behind a modal (`:123`) — c6-6's concern, but don't
   ship a shell that would.
5. **z-index 20 is documented-by-prose, not gated** (dw:1473-1482): one stacking level,
   nothing to order against; a second level would demand a `--z-*` token family, and UX-DR38
   says there will never be one. Don't introduce any z-index in AgentView.css.
6. **The static/plugin rebuild rule**: runtime `ui/src` diff ⇒ rebuild `src/companion/app/
   static/` AND `plugin/**`, sha256-verified, after the last edit. CI's drift checks use
   `git status --porcelain` (content-hashed filenames), not `git diff`.
7. **Merge ≠ release**: story PR targets `feat/companion-c6` (Greptile per story); no
   tag/CHANGELOG until c8-4. Dev stops at `review`; Brad reviews and raises the PR.
8. **R2 standing rule**: no forward-looking cross-module prose ("c6-6 will wire this…") in
   docstrings/comments — future needs get a `dw:` line. (The existing c6-5-addressed comments
   being *fulfilled* is the opposite case: update them to stay truthful, Task 4.)

### Landmines specific to this story

1. **Four guard pins move with the code, same commit, or the build is red**: keyboard-floor's
   listener set + capture exemption (Task 3); token-usage's shipped-motion enumeration
   (Task 4); store-writes' `STORES` table (Task 1); copy-rules' `COPY_MODULES` (Task 2).
   Moving a pin without its code — or code without its pin — is exactly what each guard
   exists to catch.
2. **Do not declare a second full-window fixed layer.** `shell.test.ts:952-957`'s
   `findFullWindowFixedLayers` fails the suite if AgentView.css sets `position: fixed` with
   both axes covered. The slot positions; the shell fills.
3. **`src/components/` is CLOSED** (set-equality guard, `shell.test.ts:1257`). AgentView is a
   container. One directory per component, plain CSS (no modules), flat kebab-case
   `agent-view-*` classes (BEM separators are a stylelint error), colocated `.test.tsx`, no
   `index.ts` barrel. Helpers shared later go one level up as their own module
   (`react-refresh/only-export-components` is an error).
4. **Every `px` literal in the stylesheet needs a DESIGN.md citation within a sentence**
   (`shell.test.ts` px-citation guard, widened 2026-07-28). That covers `blur(16px)` and
   `translateY(8px)` — cite `DESIGN.md:271` and `:471` respectively, beside the value.
5. **jsdom evaluates no stylesheet, resolves no media query, has no layout, no sequential
   focus navigation** (P15's lesson; R3 was DECLINED — the hole is open). Visual claims are
   provable only by source-reading guards + Brad's eye; `toHaveClass` proves emission, not
   paint. Focus assertions: `el.focus()` + `document.activeElement` checks; Esc via
   `document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))` inside `act()`
   (`CardDetail.test.tsx:508-525` is the idiom). **Tab-trap tests assert the handler's wrap
   logic, not browser tabbing.**
6. **`@testing-library/user-event` is not installed, deliberately** (c4-11 Q11). `fireEvent`
   and hand-dispatched events only. Vitest globals are OFF — import
   `describe/it/expect/vi` in every new file. `test-setup.ts` stays 13 lines — no shared
   helpers.
7. **The Esc listener must exist only while the view is open** — an always-mounted capture
   listener would swallow Esc for the pin when no view is showing, inverting UX-DR39. Register
   in the open effect, remove on close/unmount. Guard `isComposing`/`defaultPrevented` like
   CardDetail does, so IME composition and preventDefault'd events pass through.
8. **`filled(overlay)` gates the wrapper** — App must pass `undefined` when closed, not
   `false`/`null` inconsistently or an always-mounted invisible element (the AC-9
   click-swallower warning is about exactly this).
9. **Focus-restore has three arms** (SkipLink precedent `SkipLink.test.tsx:202-272`): restored
   when held, untouched when never held, fallback when the remembered element is disconnected
   (Q5). Non-vacuity: render a decoy heading before the real one to prove the labelled-by
   lookup is scoped (`:180-199`'s pattern).
10. **Windows false-red**: `npm test` from a lowercase drive letter resolves no vitest config
    (~67 failed suites / "no tests"). Uppercase drive; validate the **collected count** before
    scoring any run — especially Task 5's plant.
11. **`git ls-files` blind spot**: an un-added file is invisible to every registry guard and
    passes vacuously (`keyboard-floor.test.ts:48-56`). Stage before believing green.
12. **The cold-run flake**: `ui/tests/lint-gates.test.ts` can red once with a ~125 s setup on
    a cold start (recorded twice, c6-2 and c6-3). Re-run warm before diagnosing; record, don't
    hide.
13. **AC 8 has no tile to assert against** — c6-5 renders no card tiles. The repo-wide
    `findAccentDimOnOverlay` guard already bans `accent-dim` on `surface-overlay` in ANY
    stylesheet including the new one; the tile-level assert lands with c6-7's rows (Q7
    disposes this explicitly rather than silently).
14. **Don't compose the shell from `Panel`.** Its header (label + count + right-aligned
    badges) is structurally identical to the shell's, which makes it tempting — but `Panel`
    is presentation-only by guard (`<section aria-label>`, no `role`, no `aria-modal`, no
    refs, no hooks) and bending it breaks its own contract. The shell is its own container;
    visual kinship comes from the same tokens, not shared markup.
15. **`aria-labelledby` needs an `id` on the `h2` — and shipped prose says the app has
    exactly one DOM id** (`focusHome.ts:65`: `SKIP_TARGET_ID = 'card-detail'` is "the only
    DOM id in `ui/src`"). Use React's `useId()` for the heading id, and update that comment
    in the same diff (Task 4's prose-sync) — a claim-grep for "only DOM id" is part of the
    ripple sweep. `aria-label` as a dodge would duplicate the heading text and drift from it;
    the UX contract says *labelled by its heading*.
16. **Don't touch**: `socket.ts`'s kind switch (the four kinds stay dropped — c6-6),
    `AppShell.tsx` (the slot is consumed via props, never edited), the nav placeholder string
    (`'Agent-view nav pills land here — c6-8.'` stays on the glass until c6-8),
    `test_live_backend.py`, generated `types.d.ts`/`openapi.json` (no wire change),
    `test-setup.ts`.

### Testing requirements

- **Component suite** `AgentView.test.tsx` (dom project): chrome/semantics (dialog role,
  aria-modal, labelled-by against a decoy, heading live-region attribute, `ul`-agnostic body
  rendering a fixture child), focus-to-heading on open (tabindex dance + cleanup), trap wrap
  logic both directions, all three dismissal gestures, focus-restore three arms, Esc
  layering with a real pinned inspection (the test the shipped comments promise), close
  leaves store content intact (AC 5).
- **App-level additions** in `App.test.tsx`'s established harness (fake timers, store resets
  in `beforeEach` — copy c6-3's nested-`beforeEach` discipline and reset the new store there
  too): overlay slot filled/emptied from the store, Esc-with-pin end-to-end through the real
  document listeners. Note the shared `beforeEach` resets only some stores — add
  `resetAgentView()` where the block resets the others.
- **Source-reading guard updates** (node project): keyboard-floor (Task 3), token-usage
  motion pin (Task 4), store-writes (Task 1), copy-rules (Task 2). Each keeps its
  non-vacuity anchor true.
- Suite arithmetic recorded before/after; frontend strictly > 1,871; Python unmoved.
- Every behavioural assert pairs with a non-vacuity guard and a *why* message naming the AC
  (house style, c5-8 F5).

### Previous-story intelligence

- **c6-3** (PR #65, tests-only, cleanest review): the harness discipline this story inherits —
  fake timers + full store resets, `push(kind, payload)` envelope helper, request-log asserts
  by exact path; the shared `beforeEach` misses newer stores (it missed inspection/deckMemory
  until c6-3 nested a reset — do the same for agentView). Its Q4 finding: `redriveDeckBoot`
  holds the old deck until the new state lands — no interim teardown for this story to worry
  about behind an open view.
- **c6-4** (PR #66, Greptile 5/5 zero findings): the ripple lesson held a third time — 7 live
  sites against 3 predicted, found only by grepping the CLAIM. Its review patches were all
  wording-honesty (an overlay that "displays" nothing yet); this story's analogue is the
  fulfilled-contract prose in Task 4 — leave no comment claiming the overlay doesn't exist.
- **The C5 retro's standing items**: R2 (prose-sync) applies via Task 4; R5 (vitest probe
  harness) is still open and this is the first story matching its original value case — Q6
  rules it rather than assuming; R1-a/R1-b/R11 don't gate this story. Block J (eyes-on-pixels)
  remains ruled NOT RUN — the shell ships with zero human rendering until the C6 manual
  checklist (c8-6 backstop), which is why dw:1457's "review the composed result" note matters
  in the PR.

### Project structure notes

- **Expected diff**: `ui/src/state/agentView.ts` (+test) NEW · `ui/src/containers/AgentView/`
  (4 files) NEW · `ui/src/App.tsx` (overlay wiring) · `ui/src/App.test.tsx` (new describe) ·
  `ui/src/styles/tokens.css` (reduced-motion registration only — no new tokens) ·
  `ui/tests/keyboard-floor.test.ts` · `ui/tests/token-usage.test.ts` ·
  `ui/tests/store-writes.test.ts` · `ui/tests/copy-rules.test.ts` · prose-sync in
  `CardDetail.tsx`/`inspection.ts`/`CardDetail.test.tsx` comments · rebuilt
  `src/companion/app/static/**` + `plugin/**` · records (this file, `deferred-work.md`,
  `sprint-status.yaml`).
- **Never**: `src/**` Python, `ui/src/api/**` (generated), `AppShell.tsx`, `socket.ts`,
  hand edits under `static/` or `plugin/`.

### References

- Story + epic: `epics-companion-app.md` — Story 6.5 (:2808-2848), Epic 6 header (:2664-2669),
  6.6 boundary (:2850-2883), 6.8 (:2922-2957), 6.9 (:2959-2995); UX-DR6 (:359), UX-DR23
  (:462), UX-DR28 (:488), UX-DR33 (:543), UX-DR34 (:551), UX-DR37 (:570), UX-DR38 (:576),
  UX-DR39 (:581), UX-DR42 (:653), UX-DR44 (:666), UX-DR45 (:673), UX-DR46 (:679), UX-DR47
  (:684); confirmed rulings (:700-718).
- Spine: `ARCHITECTURE-SPINE.md` — AD-6 (:159-171), AD-7 (:173-195), AD-12 (:272-290), AD-13
  (:292-302), capability row G (:474), no-Playwright deferral (:494-495). `EPIC-SPLIT.md:119`
  (accessibility floor = ACs).
- UX: `DESIGN.md` — agent-view tokens (:270-278), nav-pill tokens (:260-269), shell prose
  (:471), close pill = nav pill (:451), surface ramp (:365, :389), elevation (:430-432),
  motion (:121-127, :496), focus/hit floor (:497). `EXPERIENCE.md` — the shell contract row
  (:90), one-level stack (:51), state-panel-behind-view (:122-123), Esc precedence (:141),
  Tab trap (:142), Enter/Space (:145), focus management (:146), reduced motion (:153),
  semantics (:155), hit targets (:156), live regions (:159), budget exclusion (:165),
  Flow 1 pin-survives-Esc (:188).
- Shipped code: `AppShell.tsx` (:133-139, :244), `AppShell.css` (:223-271), `App.tsx`
  (:161-163, :426-583), `CardDetail.tsx` (:79-101, :369-380), `CardDetail.test.tsx`
  (:170-177, :508-549), `inspection.ts` (:32-68), `focusHome.ts` (:38-105), `SkipLink.tsx`
  (:107-147), `SkipLink.test.tsx` (:140-272), `tokens.css` (:88-196, :281-434),
  `socket.ts` (:179, :402-430), `schema.ts` (:253-264), `.stylelintrc.json` (:24-80).
- Guards: `ui/tests/shell.test.ts` (:530-560, :912-958, :1257), `keyboard-floor.test.ts`
  (:48-56, :507-633), `token-usage.test.ts` (:1172, :2385-2510), `store-writes.test.ts`
  (:77-107), `copy-rules.test.ts` (:123-128), `tokens.test.ts`, `buildOutput.test.ts`.
- Records: `c6-3-…md` (harness landmines, Q4 observation), `c6-4-…md` (ripple dispositions,
  review patches), `epic-c5-retro-2026-08-09.md` (P15, R2/R5, Block J),
  `deferred-work.md` (:1457-1482, :4754-4779).

## Open questions for Brad (recommendations first — rule before code)

1. **Scope of the mount: wire `App.tsx`'s `overlay` slot now, reachable only by tests?**
   The shell needs an App-level home to test the Esc layering and slot behaviour the shipped
   comments promise, but nothing writes the store in production until c6-6 — so the running
   app shows zero change while the bundle still changes (static + plugin rebuilt).
   **Recommend: yes — build store + container + App wiring now**; the alternative
   (component-only, wiring deferred to c6-6) leaves the layering test unwritten one more
   story and hands c6-6 two integrations at once.
2. **Store shape: `{view: null | {kind, envelope, …}}`-style scalar with a `close()` that
   flips visibility and never touches content?** A scalar (not a stack) makes AC 6
   unrepresentable-by-type; retained content makes AC 5 a one-line test even before real
   pushes exist (fixture envelope). c6-6/c6-8 extend (unread, per-kind retention) rather than
   reshape. **Recommend: yes — minimal open/closed + retained-content shape, exact fields
   dev's choice.** Alternative: visibility-only store now, content shape deferred — but then
   AC 5 has nothing to pin.
3. **Scrim-click semantics (no artefact specifies the pointer contract).** A bare `click`
   handler dismisses when a drag that *started* inside the panel (text selection) ends on the
   scrim — `click` fires on the common ancestor. **Recommend: dismiss only when the
   `mousedown` target was the scrim itself** (track it; the standard modal guard), recorded
   in the Dev Agent Record as the ruling. Alternative: accept naive `click` and the
   drag-dismiss quirk — cheaper, but it's the kind of paper cut UX-DR49's gate notices.
4. **The close pill's padding: DESIGN.md's nav-pill block says `7px 14px`, which is on the
   file's own enumerated drift list and a stylelint build failure.** **Recommend: `8px 12px`
   via `--space-2`/`--space-3`, recorded as a DESIGN.md amendment beside the nav-pill block**
   (the c4-12/c4-10 amendment pattern — check what c5-7's ConnectionPill snapped to first and
   match it if it faced the same call). Alternative: `8px 16px` (rounder, larger pill).
   Whichever is ruled becomes c6-8's spec too — decide once.
5. **Focus-restore fallback when the remembered element is gone** (docs say only "never
   `document.body`"; the nav-pill case is c6-8's, the state-panel-landing case is c6-6's).
   **Recommend: `focusHome(h1)` — the SkipLink unmount precedent, one shared behaviour for
   every disconnected-restore case until c6-6 refines the state-panel arm.** Alternative:
   focus the skip-link target heading (`card-detail` h2) — but that panel may not exist on a
   state-panel surface, which is exactly the case in question.
6. **Planted reds: manual, the c5-7/c6-3 way, with R5 left open?** This is the first story
   matching R5's original value case (a real frontend feature diff, ~2-3 plants worth), but
   the R3 ruling set the bar for building harness inside feature stories. **Recommend: manual
   plants (Task 5's one primary plant + optionally one focus-restore plant), full runs,
   collected counts validated; R5 stays open, unowned.** Alternative: build the vitest
   probe-harness half first as its own change — say so and it precedes this branch.
7. **AC 8 (tiles use `accent` on overlay) — dispose as structurally-covered?** No tile
   renders in c6-5; the repo-wide `findAccentDimOnOverlay` guard already bans the failure
   mode in every stylesheet including the new one. **Recommend: record AC 8 as satisfied by
   the existing guard + zero `accent-dim` in AgentView.css, with the tile-level assert homed
   on c6-7's rows** — the AC's own subject ("a card tile inside an agent view") first exists
   there. Alternative: build a token-level pin now, which would be testing a component that
   doesn't exist.

### Review Findings

*(bmad-code-review, 2026-08-10 — Blind Hunter, Edge Case Hunter, Acceptance Auditor, run in parallel against the staged `ui/src`/`ui/tests` diff.)*

- [x] [Review][Decision→Patch] Focus trap can be escaped via a mousedown on non-interactive content — `mousedown` on the scrim or any non-control panel content (header text, count, body prose) triggers the browser's default blur-to-`<body>` behaviour (nothing calls `preventDefault()`); the trap's forward-Tab branch only re-engages on `active === last`, so once `document.activeElement` is `<body>` a forward Tab falls through to native tab order instead of re-entering the dialog. Backward Tab has a catch-all (`active === first || !inTrap`); forward Tab does not. **Brad's ruling (2026-08-10): add `event.preventDefault()` to the scrim's `mousedown` handler** — the minimal, standard fix, covering the scrim itself. Residual gap: non-interactive content *inside the panel* (kicker/count text, body prose) can still blur-then-escape; carried forward as a new defer below rather than solved with the heavier `focusin`-recovery pattern. [ui/src/containers/AgentView/AgentView.tsx:294-353]
- [x] [Review][Decision→Patch] `agentView.ts`'s "replace-in-place... for free" claim doesn't hold without a `key` on `<AgentView>` — the store's docstring states "opening while one is already open REPLACES it... c6-6's replace-in-place contract for free," but `App.tsx` renders `<AgentView>` with no `key`, so React reconciles a content replacement as a prop update on the same instance rather than a remount. The focus-to-heading effect and the entry-bloom effect are both mount-only (`useEffect(fn, [])`), so neither re-fires when content is replaced while the view is already open. **Brad's ruling (2026-08-10): correct the docstring only, no behaviour change** — state that the scalar shape enables replace-in-place at the state level, but the component-level remount/focus/animation mechanics are still owed to c6-6. [ui/src/state/agentView.ts:116-125]
- [x] [Review][Patch] Close-pill hover/focus border uses `--accent` instead of `--accent-dim`, citing AC 8/UX-DR6 out of scope — DESIGN.md's surface ramp puts the agent-view shell on `surface-panel` (`:365`), not `surface-overlay`, and explicitly permits `accent-dim` as a border on well/base/panel surfaces (`:390`, `:493`; measured 3.05:1 on panel, passing the 3:1 floor — only the `overlay` column at 2.70:1 fails). AC 8/UX-DR6's ban is scoped to tiles on `surface-overlay` specifically, not this control. The stylesheet's own adjacent comment ("this control sits on `--surface-panel`, not on arbitrary card art") contradicts the hover/focus rule's citation two lines above it. This becomes c6-8's nav-pill spec too if left uncorrected. [ui/src/containers/AgentView/AgentView.css:168-178]
- [x] [Review][Patch] Scrim-dismiss only checks the mousedown target, not the mouseup/click target — a drag that starts with `mousedown` on the scrim and releases over panel content still dismisses the view, because a `click` fires on the nearest common ancestor of the mousedown and mouseup targets (the scrim, since it wraps the whole dialog). This is the mirror of the case Q3's ruling was written to prevent (drag starting on the panel, ending on the scrim). Fix: also record the mouseup target and require both the mousedown AND the click target to be the scrim, symmetric to the existing check. [ui/src/containers/AgentView/AgentView.tsx:335-343]
- [x] [Review][Defer] `FOCUSABLE_SELECTOR` doesn't exclude natively-focusable elements carrying `tabindex="-1"` (the roving-tabindex pattern used by ARIA listbox/menu widgets) — only the catch-all `[tabindex]` branch excludes them. Unreachable today (no such content exists), but c6-7's suggestion rows are a plausible place for it to show up. [ui/src/containers/AgentView/AgentView.tsx:85-92] — deferred, no reachable case in this diff.
- [x] [Review][Defer] The document-capture Esc listener's `stopPropagation()` suppresses Escape for React's own synthetic event delegation app-wide while a view is open (React 17+ delegates at the root container, which sits below `document` in the capture path) — not just for `CardDetail`'s bubble listener, the only consequence the extensive inline documentation calls out. No `onKeyDown`/`onKeyDownCapture` prop exists anywhere in the app today, so there is no live impact, but future content (c6-7/c6-8) should not add an Escape-consuming `onKeyDown` expecting it to fire while a view is open. [ui/src/containers/AgentView/AgentView.tsx:237-252] — deferred, zero current impact, established pattern since c4-5.
- [x] [Review][Defer] `AgentViewContent.title` has no non-empty guard — an empty title would leave the dialog's `aria-labelledby` pointing at empty text, failing the "every dialog needs a discernible name" requirement. Not reachable until c6-6 wires real content. [ui/src/state/agentView.ts:62-71] — deferred, c6-6's concern.
- [x] [Review][Defer] Copy-module "Nth in the app" ordinal comments across c4-8/c4-10/c4-12 already disagree with each other; the new c6-5 entry inherits and self-acknowledges the drift in its own comment without fixing it. [ui/tests/shell.test.ts:1562] — deferred, pre-existing, self-acknowledged in the diff.
- [x] [Review][Defer] Residual focus-trap-escape gap after the scrim `preventDefault()` patch: non-interactive content *inside the panel* (kicker/count text, body prose) has no `mousedown` guard, so clicking it still blurs focus to `<body>` and a forward Tab can still fall through to native tab order. [ui/src/containers/AgentView/AgentView.tsx:294-353] — deferred per Brad's ruling on the scrim-escape decision; the heavier `focusin`-recovery fix was declined for now.

**Dismissed as noise (5):** `scrimPressRef` stuck-true after an unresolved gesture (inert — `onScrimClick`'s `event.target === scrim` check guards it regardless); ARM 3's `focusHome(h1)` fallback coupling to the "exactly one `h1`" invariant (this *is* Brad's Q5 ruling, not a defect); `INITIAL_AGENT_VIEW`'s shared object reference across resets (inert — nothing in the module ever mutates state in place); unguarded Escape key-repeat (self-acknowledged low/no consequence — `closeAgentView` is idempotent); focus-trap's lack of shadow-DOM/iframe awareness (no shadow DOM or iframes exist anywhere in this app).

## Dev Agent Record

### Agent Model Used

claude-opus-5 (Claude Code, `bmad-dev-story`).

### Brad's pre-code rulings (2026-08-10) — all seven adopted as recommended

1. **Q1 — wire `App.tsx`'s overlay slot now.** Store + container + App wiring in this story.
2. **Q2 — scalar open/closed store with retained content.** `close()` writes `status` only.
3. **Q3 — scrim dismissal requires the `mousedown` to have landed on the scrim.**
4. **Q4 — close pill padding is `8px 12px`** (`--space-2`/`--space-3`), recorded as a DESIGN.md
   amendment; this is also c6-8's nav-pill spec. Evidence added at implementation time: c5-7's
   `ConnectionPill` faced the same call and snapped to `var(--space-1) var(--space-3)`, so the
   12px horizontal matches the shipped sibling.
5. **Q5 — disconnected focus-restore falls back to `focusHome(h1)`.**
6. **Q6 — manual planted reds; R5's vitest probe harness stays open and unowned.**
7. **Q7 — AC 8 is satisfied structurally** (repo-wide `findAccentDimOnOverlay` + zero `accent-dim`
   in `AgentView.css`); the tile-level assert is homed on c6-7's rows.

### Debug Log References

**Suite arithmetic.** Frontend **1,871 / 69 files → 1,934 / 71 files** (+63 tests, +2 files).
Python **2,907 passed / 1 skipped / 55 deselected, unmoved** (no backend change), verified after
implementation. Token count unmoved at 69 — this story added none.

**Baseline flake, third occurrence.** The cold-start `lint-gates.test.ts` timeout (Landmine 12,
previously seen at c6-2 and c6-3) fired on the very first baseline run: 1 failed / 1,871 collected,
setup 122.80 s. Re-run warm: 1,871 passed in 6.23 s. Recorded, not hidden; the collected count was
validated before scoring either run.

**A SECOND, NEW flake — recorded in `deferred-work.md`.** Twice in roughly a dozen full runs, the
suite ended with `[vitest-pool]: Worker forks emitted error / Worker exited unexpectedly` and one
test FILE silently dropped (`70 passed (71)` / `1,929 passed (1,934)` — five tests never run and
never reported as failures). Distinct from the cold-start flake, which names a failing test. It did
not reproduce in **seven** consecutive runs afterwards, all 1,934/1,934. It is filed because its
failure mode is a suite that silently gets *smaller*, which is exactly what validating the collected
count exists to catch.

**Planted red (Task 5).** Removed the single `event.stopPropagation()` from the capture-phase Esc
listener — the exact regression `dw:4766-4773` was written about. Collected count validated at
**1,934 before and after the plant**. Result: **5 failed across 3 files**, all the intended ones —
the two layering tests in `AgentView.test.tsx`, the end-to-end pair in `App.test.tsx`, and
`keyboard-floor.test.ts`'s non-vacuity anchor. Reverted; `git diff --exit-code` clean on the file.

> **The story predicted keyboard-floor would stay GREEN under this plant** ("they read source for
> the listener's existence, not its body"). It went red instead, because the rewritten guard's
> non-vacuity anchor now also asserts the capture listener's source contains `stopPropagation()`.
> The prediction was correct about the guard as it was; the guard is stronger than the story
> assumed it would be.

**Two story-context claims found FALSE during implementation** (neither changes the design):

- Dev Notes say *"`--scrim` is declared and consumed nowhere — this story is its first consumer."*
  It is already consumed by `QuantityBadge.css:42` and `FlipControl.css:85`. `AgentView.css` makes
  no first-consumer claim, so nothing shipped is wrong; the Dev Note was.
- Dev Notes say the shell's own `min-width`/`min-height` would satisfy the hit-box guard. It does
  not: `keyboard-floor.test.ts`'s hit-box rule is an enumerated two-group classification, so
  `agent-view-close` had to be added to `DECLARES_MIN` by name.

### Completion Notes List

**What shipped.** The app's first `role="dialog"`, first `aria-modal`, first focus trap and first
return-focus contract, as a content-agnostic shell (`title`, `count`, `children`, `onClose`) plus a
seventh zustand store. AC 1–7 are covered; AC 8 is disposed structurally per Q7.

**Four guard pins moved in the same commits as the code they guard** (Landmine 1), plus a fifth the
story did not predict:

1. `store-writes.test.ts` — `STORES` gains `useAgentViewStore`.
2. `copy-rules.test.ts` — `COPY_MODULES` gains `src/containers/AgentView/copy.ts`.
3. `token-usage.test.ts` — the enumerated shipped-motion pin gains one entry. It sorts **first**
   (stylesheet order), which the guard caught on the first run.
4. `keyboard-floor.test.ts` — the reservation is filled; see below.
5. **`shell.test.ts`'s `CONTAINERS` list — not predicted by the story**, and it failed the build
   until both new modules were registered with their import sets and the length bumped 27 → 29.

**Three decisions a reviewer should look at hardest:**

- **The scrim is the inset box, not the whole window.** AC 1's *"full-window scrim … inset 32px"*
  cannot describe one box. `.app-shell-overlay` has shipped as the 32px-inset layer since c2-1 and
  `shell.test.ts:952-957` fails a second full-window fixed layer, so the slot won: `AgentView.css`
  declares no `position` and no `z-index`, and the outer 32px frame of the window stays unblurred.
  Recorded in the stylesheet header.

- **The bloom is a transition out of `[data-entering='true']`, not a `@keyframes` animation — and
  the reduced-motion GATE chose that.** `token-usage.test.ts`'s CSS reader matches innermost brace
  pairs, so a keyframes block presents as two rules named `from`/`to`; the registration the pin
  would then demand (`from { transform: none !important }`) is ignored inside keyframes by
  specification, i.e. an accessibility override that parses cleanly and does nothing. The attribute
  form gives the pin one honest entry and `tokens.css` one real neutralisation. The flip runs in a
  `requestAnimationFrame` so a real frame separates the two states.

- **⚠️ I NARROWED A SHIPPED ACCESSIBILITY GUARD, and it deserves scrutiny.**
  `keyboard-floor.test.ts`'s *"uses `--focus-ring`, not `--accent-bright`, in every ring"* read the
  whole rule body. DESIGN.md's nav-pill spec (`:451`) gives hover **and focus** the same three
  changes, one of which is text colour `{nav-pill.hover-foreground}` = `accent-bright` — so a
  body-wide ban made the spec unshippable on the first component to use it. The ban is now keyed on
  `outline` / `outline-color` / `box-shadow`, which is what the test's name, message and Q6
  rationale all say ("in every RING"), and I added a firing-half test proving the narrowed guard
  still catches both ring spellings while admitting `color:`. The alternative was a silent,
  unrecorded deviation from DESIGN.md on the pill c6-8 inherits. **If Brad disagrees, the revert is
  small**: restore the body-wide ban and drop `color: var(--accent-bright)` from
  `.agent-view-close:focus-visible`.

**Lint-driven design changes, all made rather than suppressed.** `jsx-a11y` correctly objected to a
`<div>` carrying pointer handlers and to `role="dialog"` carrying a key handler. Neither element is
a control, so rather than suppress the rules or invent a `role="presentation"`/`tabIndex` to quiet
them, the trap and both scrim handlers are native listeners attached through refs. `react-hooks`
likewise forced the `onClose` ref write into an effect and the bloom flip into a frame callback —
the second of which is a genuine correctness improvement, not an accommodation.

**Two test vacuities I found and fixed in my own work**, both of which passed on the first run: the
trap's wrap tests asserted focus landing on the close pill when the pill was the *only* focusable
(so a no-op handler would have passed) — the fixture now carries two focusable children, making the
two ends distinct elements; and the close-pill test claimed Enter/Space coverage it did not have —
it now asserts the element kind and the absence of a key handler, which is where that behaviour
actually lives.

**Ripple sweep: 41 `c6-5` sites against the ≈28 predicted** — the ripple lesson holding a fourth
time. Dispositions: 6 prose sites falsified and repaired (`CardDetail.tsx`, `CardDetail.test.tsx`,
`inspection.ts`, `SkipLink.tsx`, `AppShell.test.tsx`, `App.tsx`); 2 "only DOM id" sites amended to
"only AUTHORED DOM id" (`focusHome.ts`, and **`CardDetail.tsx:424`, which the story did not
predict**); the rest are forward-looking references to c6-7's thumbnails and c6-8's pills, correctly
NOT TRIGGERED. `tokens.css`'s inventory line needed no change — it names the motion, the fallback
and the owner, all still true.

**Ledger.** `dw:4766-4773` (capture reservation) annotated FULFILLED with its firing proof.
`dw:1457-1471` (shell guards are static readers) annotated **STILL OPEN — review guidance**, and it
is the one to carry into the PR description: the composed result has been seen by no human eye,
Block J remains ruled NOT RUN until the C6 manual checklist.

**Runtime rebuild.** `npm run build` → `src/companion/app/static/`, then
`uv run python -m scripts.build_plugin`; both mirrors sha256-verified identical across all 5 files,
rebuilt **after** the last source edit.

**What this story deliberately did not do:** no push wiring (`socket.ts`'s four view kinds are still
dropped — c6-6), no suggestion rows (c6-7), no nav pills (c6-8), no 250 ms measurement (c6-9), no
`AppShell.tsx` edit, no backend change, no new token.

### File List

**New (6)**
- `ui/src/state/agentView.ts`
- `ui/src/state/agentView.test.ts`
- `ui/src/containers/AgentView/AgentView.tsx`
- `ui/src/containers/AgentView/AgentView.css`
- `ui/src/containers/AgentView/AgentView.test.tsx`
- `ui/src/containers/AgentView/copy.ts`

**Modified — runtime (6)**
- `ui/src/App.tsx` (overlay wiring + prose-sync)
- `ui/src/styles/tokens.css` (reduced-motion registration only — no new token)
- `ui/src/containers/CardDetail/CardDetail.tsx` (prose-sync ×2, comments only)
- `ui/src/containers/SkipLink/SkipLink.tsx` (prose-sync, comment only)
- `ui/src/containers/focusHome.ts` (prose-sync ×2, comments only)
- `ui/src/state/inspection.ts` (prose-sync, comment only)

**Modified — tests and guards (8)**
- `ui/src/App.test.tsx` (new c6-5 describe: 6 tests)
- `ui/src/components/AppShell/AppShell.test.tsx` (prose-sync, comment only)
- `ui/src/containers/CardDetail/CardDetail.test.tsx` (prose-sync, comment only)
- `ui/tests/store-writes.test.ts` (`STORES` +1)
- `ui/tests/copy-rules.test.ts` (`COPY_MODULES` +1)
- `ui/tests/token-usage.test.ts` (shipped-motion pin +1)
- `ui/tests/keyboard-floor.test.ts` (listener table, phase rule, ring narrowing, `DECLARES_MIN` +1)
- `ui/tests/shell.test.ts` (`CONTAINERS` +2, length 27 → 29)

**Rebuilt artefacts**
- `src/companion/app/static/**` and `plugin/server/src/companion/app/static/**` (asset hashes
  `index-DxNHPEE-.css`, `index-ph_t9CxW.js`; previous `index-4RSHS1-Y.css` / `index-Bpa6Djub.js`
  deleted)

**Records**
- `_bmad-output/implementation-artifacts/c6-5-agent-view-shell-with-focus-management-and-dismissal.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Change Log

- 2026-08-10 — Story context created (create-story). 7 open questions await Brad's pre-code
  ruling. Key findings: the mount point, Esc-layering contract, and reduced-motion inventory
  line all shipped in earlier epics addressed to this story by name; four guard pins
  (keyboard-floor, token-usage motion, store-writes, copy-rules) must move in the same
  commits as the code they guard; no modal/trap machinery exists anywhere — this story builds
  the app's first.
- 2026-08-10 — Implemented (dev-story). All 7 open questions ruled by Brad as recommended before
  any code. Tasks 0-6 complete; status -> review. Frontend suite 1,871/69 -> 1,934/71; Python
  unmoved at 2,907/1/55; tokens unmoved at 69. Five guard pins moved with their code (the story
  predicted four — `shell.test.ts`'s CONTAINERS list was the unpredicted fifth). Planted red
  removed `stopPropagation()` from the capture-phase Esc listener and turned 5 tests red across 3
  files, collected count validated at 1,934 either side; reverted clean. Ripple sweep found 41
  sites against ~28 predicted. Two guard collisions resolved rather than suppressed: the ring
  guard was narrowed to ring-carrying properties so DESIGN.md's nav-pill focus foreground could
  ship (flagged for review), and three DOM handlers became native listeners so `jsx-a11y` did not
  have to be silenced. Two new deferred-work entries: an intermittent vitest worker-fork crash
  that silently drops a whole test file, and the pre-existing contradictory copy-module ordinals.
