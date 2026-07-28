---
epic: c2
story: c2-6
work_branch: feat/companion-c2
story_branch: feat/companion-c2-6-application-shell
depends_on: none — c2-5 (PR #22) is already merged into the umbrella at 502a646
baseline_commit: 2a22e19
---

# Story C2.6: The two-column application shell

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad snapping the browser beside my terminal,
I want the app laid out as a header, two columns and a pinned footer,
so that the deck and its analysis are both visible at once at the window sizes I actually use.

**What this story really is.** It is **the first story in the feature that writes a component** —
five stories of gates, tokens and a typeface have been built *for* this moment, and every rule
they installed is about to meet its first real consumer. It is also the story that decides three
conventions the next ~35 stories inherit without re-litigating: **where a component's files
live**, **who owns the scroll**, and **what a landmark is called**. Those are worth more care than
the geometry.

The geometry itself is four numbers — 32px gutter, 24px panel-gap, 452px right column, ~1100px
breakpoint — and the honest observation is that **none of the interesting failure modes are in
the numbers.** They are in: a `1fr` track that silently becomes `minmax(auto, 1fr)` and overflows
the window; a missing `box-sizing` reset that adds 64px to a 100dvh element; an overlay that is
`absolute` and therefore sized to the *document* rather than the *window*; and an `overflow-x:
hidden` that makes the no-horizontal-scroll AC true by clipping the content instead of fitting it.
Each of those renders *almost* right, which is this epic's recurring theme in its layout form.

**Twelve things were measured on this machine at `2a22e19` — do not rediscover them:**

1. **There is no `box-sizing` reset anywhere in `ui/`.** `git grep box-sizing -- '*.css' '*.html'`
   returns **nothing**. CSS defaults to `content-box`, so `height: 100dvh` plus
   `padding: var(--space-gutter)` is a **100dvh + 64px** element and the window scrolls — which
   silently defeats "footer pinned to the window bottom" and would be diagnosed as a footer bug.
   The composition reference sets `box-sizing:border-box` **inline on every sized element**, which
   is precisely the thing this codebase's inline-style ban forbids reproducing. The reset is this
   story's to add.

2. **The `max-width` spelling of the breakpoint FAILS lint.** Measured:
   `@media (max-width: 1099px)` → **1 error**, `media-feature-range-notation` — stylelint-config-standard
   requires the **context** form. `@media (width < 1100px)` lints **clean**. This is not a style
   preference you can lose an hour to; it is a gate.

3. **Geometry literals are the ungated family — the c2-4/c2-5 theme in its layout form.**
   Measured, exit **0**, on one probe file: `grid-template-columns: minmax(0, 1fr) 452px`,
   `width: 452px`, `height: 100dvh`, `position: fixed`, `inset: 0`, `z-index: 20` and
   `@media (width < 1100px)` all lint entirely clean. No allowed-list keys `width`, `height`,
   `inset`, `grid-template-*` or `max-width`. AC 18 decides what to do about that, and the answer
   is **not** "add a token" — see landmine 4.

4. **NO TOKEN MAY BE ADDED, and 452px cannot become one.** `tests/token-usage.test.ts:426` asserts
   `declaredTokens.size === 64`, and `tests/tokens.test.ts` asserts every token name **byte-for-byte
   against DESIGN.md's frontmatter**, which contains no layout-width token. So the two constants are
   literals **by necessity**, not by laziness, and the record has to say so or the next reviewer
   reads them as drift.

5. **`tests/token-usage.test.ts:424` pins `src/App.css` into the non-vacuity anchor.**
   `expect(shippedStylesheets).toContain('src/App.css')`. If this story deletes or renames that
   file — which is a reasonable thing for it to do — the anchor turns red for a reason that has
   nothing to do with what broke. Decide it deliberately (AC 19), do not discover it.

6. **`src/App.test.tsx` pins an `h1` named exactly "Artificial Planeswalker" and a `main`
   landmark.** Both are inside this story's blast radius. The h1 assertion is the reason Q3 exists.

7. **Inline `style={{…}}` is an ESLint *error* with no escape hatch, and its comment names this
   story.** `eslint.config.js:71-100`: "c2-6 and c2-7 write the first components; the gate has to
   exist first, or the exception becomes the convention." A dynamic value would have to change that
   rule in the open. **This story needs no dynamic value** — if the implementation reaches for one,
   that is a signal the layout is being done in JS that belongs in CSS.

8. **`react-refresh/only-export-components` is `error` with `allowConstantExport: true`** — read
   from the installed plugin, not assumed. A component module may also export **constants and
   types**; exporting a **helper function** beside the component turns the gate red. Put helpers in
   their own module.

9. **Native CSS nesting is banned, and `&` anywhere in a shipped stylesheet fails** — including a
   bare `&:hover`. Write selectors out in full. A rule inside `@media` is depth 2 and legal; that is
   how the reduced-motion block is written.

10. **`git ls-files`-keyed guards cannot see an untracked file.** `shippedStylesheets` and every
    guard built on it read a new stylesheet only once it is staged. c2-4 and c2-5 *both* lost time
    to this. **`git add` the new files immediately.**

11. **The composition reference is a fixed 1720×1440 slab, and its agent-view overlay is
    `position:absolute; inset:0` of that slab with the root `overflow:hidden`.** In a real browser
    the document is taller than the window, so `absolute` sizes the overlay to the **document** —
    it would scroll away and its 32px inset would land nowhere near the window edge. "Takes the
    whole window" means **`fixed`** (AC 8). Copying the mock's `absolute` here is the single most
    likely way to hand c6-5 a broken foundation.

12. **The mock's own card-grid gap is 18px** — drift, not spec (UX-DR5; DESIGN.md says the grid gap
    is `{spacing.5}` = 24px). The grid is c4-4's anyway; noted so the reference is read with the
    same scepticism c2-4 applied to its spacing.

**Baseline, measured at `2a22e19`:** frontend **173 passed / 13 files**; Python **1,753 passed**
(c2-5's final number); working tree clean, branch level with `origin/feat/companion-c2`.

**What this story does not do.** No primitives — Panel, Badge, StatChip and Group header are
**c2-7**. No state panel and none of its copy (**c2-9**). No footer *text* (**c2-10**) — only the
element that will carry it. No skip link and no Tab-order work (**c4-11**). No card grid
(**c4-4**), no nav pills (**c6-8**), no connection pill (**c5-7**), no agent view (**c6-5**) —
only the slot it drops into. No store, no fetch, no route, no Python.

**One boundary worth homing explicitly, because UX-DR8 states it and this story does not build
it:** the left column's *"mana-curve and colour-distribution panels below the grid as a 1:1 pair"*
is a two-up row **inside** the left column, and it is **c4-8's** to introduce — it cannot be
composed before either panel exists, and a `1fr 1fr` sub-grid shipped empty here would be a second
piece of geometry with nothing to hold it honest. The shell gives the left column a vertical flow
at the panel-gap; c4-8 nests the pair into it. Said here so it reads as a decision rather than an
omission.

## Acceptance Criteria

Epic-derived ACs are marked **[epic]**. The rest are requirements the epic's five blocks imply but
do not state; each says why it exists. An AC the epic did not write down is still an AC (standing
agreement: a story must leave the system working end to end).

### The composition

**AC 1 [epic].** **Given** a viewport between ~1100px and ~2560px, **when** the app renders,
**then** it composes a full-width header, a fluid left column, a **452px** fixed right column and a
full-width footer pinned to the window bottom (UX-DR8), **and** panels float with visible canvas
between them at the panel-gap, framed by the 32px gutter — mechanically: the gutter is
`var(--space-gutter)`, the inter-region and inter-column separation is `var(--space-panel-gap)`,
and neither is a literal.

**AC 2.** **Given** the two-column track definition, **when** it is written, **then** the fluid
track is **`minmax(0, 1fr)`**, never bare `1fr`. *Why: `1fr` is shorthand for
`minmax(auto, 1fr)`, and `auto` floors at **min-content** — so one unbreakable child (a long card
name, a wide table, a `<pre>`) pushes the track past its share and the whole grid overflows the
window. That is AC 5's defect, arriving through the one spelling that looks correct.* Asserted by a
test that reads the shell stylesheet, and proven by planting the bare `1fr`.

**AC 3 [epic].** **Given** a viewport narrower than ~1100px, **when** the app renders, **then** the
right column drops beneath the left rather than compressing (UX-DR8) — written as
`@media (width < 1100px)`, the **context** range form, because the `max-width` spelling is a lint
error (landmine 2).

**AC 4 [epic].** **Given** the reference width of 1720px, **when** the layout is compared against
the composition reference, **then** proportions match the design intent.

> **This AC has a machine-verifiable half and a human half, and the record must say which is
> which** (the c2-2 AC 17 / c2-5 AC 4 precedent — this is the third time, and it is now a pattern
> rather than an exception). *Mechanical:* the four numbers that define the composition — gutter
> 32px via token, panel-gap 24px via token, right column exactly 452px, breakpoint exactly 1100px —
> are pinned by a test reading the shell stylesheet, so a later edit that "tidies" one of them
> fails. *Human:* **that it looks like the reference at 1720px.** jsdom has no layout engine: it
> computes no grid tracks, resolves no media queries and returns no box geometry, so any
> `getComputedStyle` assertion about widths here is vacuous by construction. **Do not fake it.**
> Put "open at 1720px and compare against the composition reference" on the epic manual-testing
> checklist and say so plainly in the Completion Notes.

**AC 5 [epic].** **Given** the page renders at any supported width, **when** the body is inspected,
**then** it never scrolls horizontally.

**AC 6.** **Given** AC 5's cheapest evasion, **when** the shell is written, **then**
`overflow-x: hidden` / `overflow: hidden` on `html`, `body` or the shell root is **banned** — by a
guard, proven firing and not firing. *Why: it makes AC 5 true by **clipping** the overflowing
content rather than fitting it, so the bug survives, invisible, and the AC reports success. This is
the epic's standing theme in its layout form: a value that lints clean and renders as nothing
wrong.* The legitimate `overflow` — the content region's own `auto` (AC 11) — is unaffected, and
the guard must be narrow enough to say so.

### The overlay slot

**AC 7 [epic].** **Given** an agent view will later overlay the window, **when** the shell is
built, **then** it reserves a full-window overlay slot inset by 32px, so Epic 6 adds the view
without restructuring the shell (UX-DR8) — and the inset is `var(--space-6)`, not a literal.

**AC 8.** **Given** the slot, **when** it is positioned, **then** it is **`position: fixed`**, not
`absolute`. *Why: landmine 11 — the reference mock is a fixed-height slab where the two coincide;
a real document is taller than the window, and an absolute overlay would be sized to the document,
scroll away with it, and put its 32px inset nowhere near the window edge.* Record the reasoning
where c6-5 will read it.

**AC 9.** **Given** no agent view is open, **when** the shell renders, **then** the slot renders
**nothing** and intercepts **nothing** — no always-present transparent element over the page.
*Why: an invisible full-window div is a click-swallower that presents as "the app stopped
responding to clicks", and it is the default outcome of "reserve a slot" read literally.*

**AC 10.** **Given** UX-DR38 ("the overlay stack is exactly one level deep"), **when** the slot
ships, **then** a guard confines the full-window fixed overlay to the shell's own stylesheet, over
every `ui/src/**/*.css`. *Why this is not covered by anything existing: a second component
declaring its own `position: fixed; inset: 0` layer is how "one level deep" quietly stops being
true, and no value-level rule objects — it is the same shape as c2-5's `@font-face` confinement
guard, and it fails the same way for the same reason.* Proven firing and not firing.

### Scroll, and the pinned footer

**AC 11.** **Given** the footer carries the Scryfall and Fan Content notices and is a **release
condition** (UX-DR32, NFR-08), **when** the shell is composed, **then** the footer is visible
without scrolling at every supported viewport height — per Q2's ruling, and whichever shape it
lands on, the mechanism is asserted rather than left to inspection.

**AC 12.** **Given** the scrolling content region, **when** it is written, **then** it carries
`min-height: 0`. *Why: a flex or grid child defaults to `min-height: auto`, which refuses to shrink
below its content — so the region never becomes smaller than what it holds, its `overflow` never
engages, and the **page** scrolls instead. The footer then leaves the window and AC 11 fails
silently on exactly the long decks it exists for. This is a one-line omission with a symptom that
points somewhere else entirely.*

**AC 13.** **Given** the global `box-sizing` default, **when** the shell sizes itself, **then** a
`box-sizing: border-box` reset ships (landmine 1), so padding is inside the declared height rather
than added to it. *Why here: this is the first sized, padded element in the app; every component
from c2-7 onwards inherits the same hazard, and the reference mock's answer to it (inline
`box-sizing` on every element) is banned by the inline-style rule.*

### Structure and semantics

**AC 14.** **Given** the shell renders, **when** its landmarks are inspected, **then** there is
exactly one `<header>` (banner), one `<main>` containing **both** columns, and one `<footer>`
(contentinfo) — per Q4. The right column is a plain container, **not** `<aside>`.

**AC 15 [epic, implied by UX-DR44].** **Given** the header, **when** it renders, **then** it
carries the product kicker and the `h1`, per Q3 — and the `h1` is the shell's, so c4-2 replaces its
**content** with the deck name without restructuring the header.

**AC 15b.** **Given** UX-DR8 describes the header as "kicker + deck name left; format/size badges +
agent-view nav right", **when** the header is composed, **then** it reserves both right-hand slots
— badges and nav — as empty, prop-fed regions with the correct alignment. *Why: the same argument
as AC 7's overlay slot. c2-7 supplies Badge and c6-8 supplies the nav pills; if the header does not
already have somewhere to put them, each of those stories restructures the header instead of
filling it, and the alignment gets re-derived twice.*

**AC 16.** **Given** the shell is presentation-only, **when** its implementation is inspected,
**then** it holds no state, fetches nothing, imports no store, subscribes to nothing, and takes all
content through props — the same posture c2-7 restates for the primitives. Deliberate and recorded,
not an omission.

### Conventions this story sets

**AC 17.** **Given** this is the first component in the codebase, **when** its files are placed,
**then** they follow Q1's layout, and that layout is **recorded in `ui/README.md` as the convention
c2-7 … c7 inherit**. *Why an AC: thirty-five later stories add components; a convention discovered
per story is thirty-five chances to diverge.*

**AC 18.** **Given** geometry literals are ungated and cannot become tokens (landmines 3 and 4),
**when** this story introduces the first two, **then** each carries a comment giving the value's
source in DESIGN.md and the reason it is not a token, is pinned by test, and the **family** is
recorded in `ui/README.md`'s ban table as a **named non-ban with its reason** — so c2-7 (the 17px
StatChip value), c2-9 (the 480px state-panel max-width) and c4-4 (the 176px grid minimum) inherit a
stated rule rather than a habit. *Why not simply ban them: there is no token family to point at,
and adding one breaks two pinned assertions and DESIGN.md's byte-for-byte contract. An
unenforceable ban is worse than a documented exception.*

**AC 19.** **Given** `tests/token-usage.test.ts`'s non-vacuity anchor names `src/App.css`
(landmine 5), **when** this story changes what stylesheets exist, **then** the anchor is
re-pointed at files whose existence is **structural** rather than incidental, and stays
non-vacuous. *Why: the anchor's job is to fail when the guards read nothing; an anchor that fails
because a file was legitimately renamed teaches people to weaken it.*

### Records and boundaries

**AC 20.** **Given** the forward-dated sentences that name this story, **when** it lands, **then**
each is repaired in the same commit (C1 retro homing rule): `ui/README.md:355-358`,
`ui/eslint.config.js:78-79`, `ui/src/App.tsx:6-9`, `ui/src/App.css:1-3`. **And**
`ui/tests/fixtures/tsx/clean.tsx:4` ("This is what c2-6 and c2-7 write") is **judged, not swept**:
it describes the fixture's purpose rather than asserting a future state, so it stays — say so in the
record rather than leaving the omission to look like an oversight.

**AC 21.** **Given** every region the shell reserves is empty until a later story fills it, **when**
placeholder copy is written, **then** each line names the story that replaces it, so the repair is
mechanical rather than archaeological — the same discipline AC 20 is enforcing on this story's own
inheritance.

**AC 22.** **Given** any CSS or component change, **when** the story is committed, **then** the SPA
bundle is rebuilt (`cd ui && npm run build`) and the **committed bundle and its `plugin/` mirror
are both regenerated and committed** — otherwise c2-2's sync check and the `plugin/` drift check
both go red.

**AC 23.** **Given** the dependency graph, **when** it is inspected, **then** this story adds **no
dependency, runtime or dev**, and **no token** — `tests/tokens.test.ts` and the
`declaredTokens.size === 64` assertion are untouched (landmine 4).

**AC 24.** **Given** the scope, **when** the diff is inspected, **then** it touches no `.py` file
(except the regenerated bundle and mirror), no route, no store, no fetch layer, and none of the
components owned by c2-7, c2-9, c2-10, c4-11, c4-4, c5-7, c6-5 or c6-8. `pyproject.toml` and
`uv.lock` are untouched. The Python suite is re-run to prove it stayed at **1,753**, not assumed.

## Tasks / Subtasks

- [x] **Task 0 — verify the baseline before changing anything** (standing agreement)
  - [x] Branch off `feat/companion-c2` as `feat/companion-c2-6-application-shell`; confirm
        `baseline_commit` is `2a22e19`
  - [x] `cd ui && npm test` → expect **173 passed / 13 files**; `npm run lint`,
        `npm run format:check`, `npm run typecheck`, `npm run build` all exit 0
  - [x] Repo root: `uv run pytest -m "not integration"` → expect **1,753 passed / 1 skipped /
        45 deselected**. *If `test_list_decks_with_strategy_field` fails, it is the known
        `created_at`-tie flake — re-run before investigating.*
  - [x] `git status --porcelain -- src/companion/app/static/ plugin/` clean **after** a build, so a
        later drift is provably yours
  - [x] Record every number in the Dev Agent Record

- [x] **Task 1 — the conventions, before the code** (AC 17, and Q1/Q2/Q3/Q4 answered)
  - [x] Create the component directory in Q1's shape and put the shell in it
  - [x] `git add` immediately (landmine 10) — the CSS is invisible to every guard until staged
  - [x] Confirm no tsconfig or ESLint change is needed (`src` is already in `tsconfig.app.json`'s
        `include`); if one *is* needed, that is a signal Q1 was answered outside `src/`

- [x] **Task 2 — the shell markup** (AC 14, 15, 16, 21)
  - [x] `<header>` / `<main>` (both columns) / `<footer>`, exactly one of each
  - [x] The header's two right-hand slots — badges and nav — reserved and prop-fed (AC 15b)
  - [x] Content arrives through props; no state, no store, no effects
  - [x] One forward-dated placeholder line per region, each naming its owner story
  - [x] Update `src/App.tsx` to compose the shell, and `src/App.test.tsx` to match (landmine 6)

- [x] **Task 3 — the shell stylesheet** (AC 1, 2, 3, 11, 12, 13)
  - [x] `box-sizing` reset first (landmine 1)
  - [x] `minmax(0, 1fr) 452px`, gutter and panel-gap from tokens, `min-height: 0` on the scroller
  - [x] `@media (width < 1100px)` — the context form only (landmine 2)
  - [x] Every geometry literal carries its DESIGN.md source and its not-a-token reason (AC 18)
  - [x] `npm run lint` after **every** block — the gates are cheap and the feedback is exact

- [x] **Task 4 — the overlay slot** (AC 7, 8, 9, 10)
  - [x] `position: fixed`, inset `var(--space-6)`, renders and intercepts nothing when empty
  - [x] Confinement guard over every `ui/src/**/*.css`, proven both ways
  - [x] A test that mounts the shell **with** overlay content, so the slot is proven to work rather
        than proven to be absent

- [x] **Task 5 — the guards** (AC 2, 6, 10, 18)
  - [x] Non-vacuity anchor first in every guard that filters a list
  - [x] The `overflow: hidden` ban, narrow enough to leave the content region's `auto` alone
  - [x] The `minmax(0, …)` assertion and the four pinned constants
  - [x] Each proven firing and not firing, **by rule name and count** where stylelint is involved

- [x] **Task 6 — records and the forward-dated sentences** (AC 19, 20, 21)
  - [x] Repair all four; judge `clean.tsx:4` explicitly and record the judgement
  - [x] Re-point `tests/token-usage.test.ts`'s anchor if App.css moved (landmine 5)
  - [x] `ui/README.md`: the component convention, the geometry-literal non-ban, the new guards in
        the ban table, and a rewritten *Not here yet*

- [x] **Task 7 — rebuild, mirror, prove** (AC 22, 23, 24)
  - [x] `npm run build`; `uv run python -m scripts.build_plugin`; commit both
  - [x] Re-run all five frontend gates and the Python suite (expect **1,753**, unchanged)
  - [x] Scope proof: `git diff --stat` shows no `.py` outside the mirror, no `pyproject.toml`,
        no `uv.lock`, no `package.json`
  - [x] `git status --porcelain` clean — nothing stray left behind
  - [x] Add "open at 1720px and compare against the composition reference; check no horizontal
        scroll from ~1100px to ~2560px; check the footer stays visible on a long page" to the epic
        manual-testing checklist, and state in Completion Notes that AC 4's and AC 5's render
        halves are **not** dev-verified (the c2-2 / c2-5 precedent, now three deep)

- [x] **Task 8 — probe the evasions before claiming done**
  - [x] For each new guard, plant the evasion, confirm it is caught, revert, paste the output
  - [x] **Verify the mutation landed before believing the verdict**, and **read what landed on
        disk** — c2-4's nesting probe planted the wrong shape and the guard was right to stay silent
  - [x] Probe the four that matter most: bare `1fr`; `overflow-x: hidden` on `body`; a second
        `position: fixed; inset: 0` in another stylesheet; `@media (max-width: 1099px)`
  - [x] **Ban the family, never enumerate members** — see Gotcha 5

### Review Findings

Adversarial review 2026-07-28 (Blind Hunter + Edge Case Hunter + Acceptance Auditor, diff
`2a22e19..bb5c633`). The Auditor's verdict was **accept** — every mechanically checkable AC
implemented and independently re-verified live (frontend 211, Python 1,753, mirrors
byte-identical). The findings below are almost entirely about the *guards'* own family
coverage — the epic's standing theme, this time arriving in the guard suite itself.

- [x] [Review][Decision] **AC 18 guard is shell-only and its pin freezes the mechanism** — `literalsInCode` reads only `AppShell.css`, and `expect(literalsInCode.sort()).toEqual(['1100px','452px'])` means any NEW shell literal fails regardless of documentation, so the "derived, not enumerated" citation check can never actually exercise a new value; meanwhile `ui/README.md` presents the citation rule as binding on c2-7/c2-9/c4-4 with nothing enforcing it there. Widen the guard over every shipped component stylesheet, or narrow the claim? [ui/tests/shell.test.ts:441-471]
- [x] [Review][Decision] **A clip on `.app-shell-columns` — the actual scroll container — is below the guard's floor** — Q5 ruled the overflow ban narrow (root elements only), but `overflow-x: hidden` on the one scroller is exactly where an AC 5-masking clip would land, and nothing objects. Extend the ban to the scroll container (hidden/clip only; its `overflow-y: auto` stays legal), or stand on Q5's ruling and leave it to review? [ui/tests/shell.test.ts:133-135, 197-217]
- [x] [Review][Decision] **The overlay inset is asserted as "the gutter token" but is `--space-6`** — the test title and the CSS comment both say "inset by the gutter"; the declaration and AC 7's letter say `var(--space-6)`; `tokens.css` declares a distinct `--space-gutter` that merely equals 32px today. If the gutter is ever retuned the overlay silently stops aligning with the frame it is documented to align with. Switch to `--space-gutter` (intent), or keep `--space-6` (AC 7's letter) and fix the prose? [ui/tests/shell.test.ts:394-396; ui/src/components/AppShell/AppShell.css]
- [x] [Review][Patch] StatChip attributed to `c7-2` (Story 7.2 is a deck-mutation tool); should be `c2-7` — propagated into two new places by this diff [ui/README.md:462; _bmad-output/implementation-artifacts/deferred-work.md:1190]
- [x] [Review][Patch] `%`-sized full-window fixed layer evades AC 10 (`width/height: 100%` on `position: fixed` resolves against the viewport; `VIEWPORT_UNIT` matches units only), and `html { height: 100% }` evades the competing-height guard the same way [ui/tests/shell.test.ts:127, 241-245, 263-277]
- [x] [Review][Patch] Mixed-axis full-window layer evades AC 10 — `anchored` requires both axes anchored, `viewportSized` both axes unit-sized; `inset-block: 0; width: 100vw` covers the window and satisfies neither disjunct — make coverage per-axis (anchored OR sized) [ui/tests/shell.test.ts:234-247]
- [x] [Review][Patch] `valueOf` reads the FIRST declaration; the cascade uses the LAST — `position: static; position: fixed` evades the overlay guard, `height: 100dvh; height: auto` passes the Q2 pin [ui/tests/shell.test.ts:116-117]
- [x] [Review][Patch] A brace inside a quoted CSS string (`content: "}"`) desynchronises `blocksIn` for the rest of the file — blank string contents before block parsing [ui/tests/shell.test.ts:92-97]
- [x] [Review][Patch] `minmax(max-content, 1fr)` evades AC 2 — `CONTENT_MINIMUM` is `auto|min-content`; `max-content` is a content-derived floor that overflows harder [ui/tests/shell.test.ts:158]
- [x] [Review][Patch] Nested function inside `minmax()` FALSE-FIRES the bare-fr check — `[^()]*` cannot cross inner parens, so `minmax(min(176px, 25%), 1fr)` (a legitimate c4-4 evolution) is unstripped and its `1fr` flagged; make the strip paren-aware and prove the legit shape silent [ui/tests/shell.test.ts:171-180]
- [x] [Review][Patch] `:is(html)` / `:where(body)` / `*` escape `DOCUMENT_ROOT`, and compound `div.app-shell` escapes `SHELL_ROOT` — unenumerated selector spellings of the banned families [ui/tests/shell.test.ts:133-141]
- [x] [Review][Patch] `documented()` matches literals as substrings — a future `52px` would be satisfied by the `52px` inside the existing "452px — DESIGN.md" citation; add non-digit boundaries [ui/tests/shell.test.ts:452-458]
- [x] [Review][Patch] Presentation-only guard gaps: only single-quoted static imports are read (dynamic `import()`/`require` invisible); React 19's lowercase `use()` and an aliased `import { useState as s }` both evade the hook regex — assert the react import is type-only and widen the import matcher [ui/tests/shell.test.ts:481-495]
- [x] [Review][Patch] Anchored-layer detection is value-blind — `inset: auto auto 16px 16px` (a corner pill in shorthand) is false-flagged as full-window; check values, probe the shorthand pill in the fixture [ui/tests/shell.test.ts:234-239]
- [x] [Review][Patch] `slot()` uses `??`, so the idiomatic `left={cond && <X/>}` passes `false` — not nullish, renders nothing, and the AC 21 placeholder silently disappears; same family: `deckName=""`/`null` leaves an empty `h1` (the default fires only on `undefined`) [ui/src/components/AppShell/AppShell.tsx:80-84]
- [x] [Review][Patch] AC 21 owner list omits `c4-9` though the left-column placeholder names it — half the placeholder is deletable without failing anything [ui/src/components/AppShell/AppShell.test.tsx:87]
- [x] [Review][Patch] `App.test.tsx` re-asserts the exact landmark-count triple its own header comment says was moved to AppShell.test.tsx to avoid duplication — slim to a composition proof [ui/src/App.test.tsx:24-27]
- [x] [Review][Patch] Completion Notes say "exactly two literals exist" — `z-index: 20` is a third geometry literal (disclosed in the guard and deferred-work, but the sentence overstates); amend to "two px literals" [story record, Completion Notes]
- [x] [Review][Patch] `var()` indirection (`overflow: var(--clip)`) evades every value-keyed guard and is not in the guard header's declared blind spots — declare it in the same breath as the guards, per the c2-4 ruling [ui/tests/shell.test.ts:35-40]

Dismissed as noise (3): a bare `auto` grid track (content-sized chrome tracks are a legitimate
family; flagging them is the gate-three-stories-fight outcome the guard's own comments call
worse than the defect); `git ls-files` blindness to untracked stylesheets (declared in the
code, landmine 10, known tradeoff); AC 4/5 human halves not dev-verified (compliance with the
AC's own machine/human split, already on the epic manual-testing checklist).

#### Round 3 — Greptile on PR #23 (2026-07-28)

Greptile scored **3/5, "not yet safe to merge"** — the check reported *pass*, the score did
not, which is worth noting: a green check is not a green review. Two P2 findings, **both
verified reproducible before being acted on** (all three probe cases failed against the shipped
code), **both applied**.

- [x] [Greptile][P2] **Empty React nodes count as filled** — `filled()` returned `true` for an
      empty Fragment and for any non-array iterable. Measured: `overlay={<></>}` mounted
      `<div class="app-shell-overlay">` — a full-window `position: fixed` element containing
      nothing, i.e. **exactly AC 9's click-swallower**, the failure this story wrote an AC to
      prevent; `left={<></>}` silently dropped the c4-4 placeholder; `overlay={new Set()}` did
      the same. A Fragment is a React *element*, so every nullish/boolean/string/array check
      says "filled" while the browser paints nothing, and `Array.isArray` denies a `Set` that
      React accepts as children. **Fixed in two layers**, because the problem has two halves:
      `filled()` now covers every empty shape a CALLER can express (moved to
      `src/components/AppShell/filled.ts`, since deciding Fragment-emptiness needs react VALUE
      imports and this file's react import is pinned type-only — the guard stayed blunt and the
      import list grew by one named entry instead); and `.app-shell-overlay:empty { display:
      none }` closes the residue `filled()` **cannot** decide, since `overlay={<AgentView />}`
      is filled by every static measure and `AgentView` may still `return null`. The limit is
      stated in `filled.ts` rather than left to be discovered.
- [x] [Greptile][P2] **Geometry scan includes CSS strings** — `pxLiteralsIn()` stripped comments
      but not string contents, so `content: "16px"` (a tooltip in c2-7, an axis label in c4-8)
      scanned as an undocumented geometry literal with nothing in DESIGN.md to cite. Measured:
      returned `['16px']`. One-line fix — `blankStrings` already existed three helpers above
      for the parser; the scanner simply was not using it. This is the false-positive class
      this file's own doctrine calls worse than the defect.

Both fixes mutation-tested: reverting the Fragment/iterable handling turns 2 tests red,
reverting the string blanking turns 1 red. Suites **223 → 228 frontend**.

**Re-review: 4/5, "appears safe to merge"**, with two narrower findings. Both applied — and the
second one turned out to invalidate a limit this file had been *declaring* rather than fixing.

- [x] [Greptile][re-review] **A one-shot iterable is exhausted by inspection** — a regression
      introduced by the fix above: `filled()` spread the iterable to test it, and a generator
      returns *itself* from `[Symbol.iterator]()`, so the values were consumed before React ever
      saw them. Measured: `left={views()}` rendered the region **empty and dropped its
      placeholder** — strictly worse than not looking. (React itself warns that iterators are
      unsupported as children, which is context, not an excuse: the shell made it worse.) Fixed
      by identity — a one-shot iterator is *assumed filled* rather than inspected, since
      inspecting it is destroying it, and `:empty` still covers the case where it turns out
      empty.
- [x] [Greptile][re-review] **Comment stripping can swallow executable CSS** — a comment opener
      inside a string. This was a **declared** blind spot, and the declaration argued the
      reverse pass order would be worse. Measuring both orders showed **the declaration was
      half-wrong**: strip-then-blank swallows an entire rule (and `blocksIn` reads the same
      source, so those rules vanish from *every* guard, not just the literal scan), while
      blank-then-strip leaks an unstripped comment's prose into the code. *Neither ordering is
      safe*, so reordering would have traded one rare failure for another. Replaced both passes
      with a single `scan()` that tracks which construct it is inside — the same move the
      nesting ban made in `token-usage.test.ts`, removing the class rather than the instance.
      Both killer inputs are now asserted together, which no ordering can satisfy.

The lesson worth carrying: **a declared blind spot is still a claim, and this one had not been
measured.** "Neither order is safe" was true; "this one fails on the rarer input" was the part
that went unchecked, and it was hiding a failure that blinded every guard in the file rather
than one scan. Suites **228 → 230 frontend**.

#### Round 2 — post-patch state (2026-07-28)

Adversarial review of the working tree vs `feat/companion-c2` (`2a22e19`), i.e. the story
commit **plus** round 1's 16 staged patches. The Auditor's verdict was again **accept** — every
mechanically checkable AC holds, all three round-1 rulings verified in place. The findings are
one layer deeper than round 1's: where round 1 found guards missing family members, round 2
finds the *repairs themselves* stopping one member short — the lookbehind added to one regex
but not its sibling, comments stripped for the CSS half but not the TSX half, `filled()`
value-aware for three empty shapes but not the fourth.

- [x] [Review][Patch] A bare side-effect `import './x'` evades the presentation-only import guard — no `from` clause, no call parens, so a module that subscribes on load walks past the "imports nothing but React types" assertion [ui/tests/shell.test.ts:592-605]
- [x] [Review][Patch] The presentation-only TSX regexes read comments — the media-query assertion strips comments first for exactly this reason ten lines away, but `use[A-Z](`/`use(`/`fetch(` run over raw source, so the first JSDoc sentence quoting a banned API turns the gate red [ui/tests/shell.test.ts:608-615]
- [x] [Review][Patch] `sizedAlong` has no magnitude floor for viewport units while `FULL_PERCENT` requires ≥100 — a fixed drawer at `width: 40vw` is flagged as a second full-window layer while the identical `40%` passes; the false positive a later story fights [ui/tests/shell.test.ts:140, 325-331]
- [x] [Review][Patch] `FULL_PERCENT` lacks the `(?<![\d.])` boundary its sibling `documented()` got in round 1 — `0.100%` matches as `100%` [ui/tests/shell.test.ts:148]
- [x] [Review][Patch] `pxLiteralsIn` (`\b\d+px\b`) tokenises `17.5px` as `5px`, and `documented()`'s own lookbehind then makes a truthful "17.5px — DESIGN.md" citation unsatisfiable — the first fractional geometry literal inherits an impossible gate [ui/tests/shell.test.ts:538]
- [x] [Review][Patch] `contain: paint`/`strict`/`content` and `clip-path` on a root clip AC 5's overflow exactly like `overflow-x: hidden` and appear in neither the AC 6 guard nor its blind-spot list; the native `<dialog>`/popover top layer is likewise absent from AC 10's declared blind spots [ui/tests/shell.test.ts:242-265, 35-45]
- [x] [Review][Patch] `DOCUMENT_ROOT`'s universal alternative matches `*` in descendant position (`.card-tile * { overflow: hidden }` flagged as a clipped root) and treats `:not(html)` — a selector that *excludes* the root — as naming it [ui/tests/shell.test.ts:163]
- [x] [Review][Patch] `blankStrings` cannot parse an escaped quote — `content: "\""` terminates the blank early and desynchronises `blocksIn`, the identical failure the `content: '}'` decoy proved fixed; also declare the `/*`-inside-a-string blind spot [ui/tests/shell.test.ts:101]
- [x] [Review][Patch] `filled()` misses two empty shapes and one slot skipped the treatment — `left={[]}` (an idiomatic empty `.map()`) drops the AC 21 placeholder and renders a blank region, `deckName=" "` renders a whitespace-only `h1` (the state Q3 forbids), and the overlay slot still uses raw truthiness instead of `filled()` one round after `slot()` was patched for exactly this family [ui/src/components/AppShell/AppShell.tsx:79-80, 106, 140]
- [x] [Review][Patch] `max-*` properties count as "sized along" an axis — `max-width: 100%` is a cap, not a size, so a content-sized fixed toast with percentage caps is flagged as a full-window overlay [ui/tests/shell.test.ts:153-154]
- [x] [Review][Patch] `insetShorthandSides` splits on all whitespace including inside functions — `inset: auto var(--x, 8px) auto auto` miscounts the sides [ui/tests/shell.test.ts:293-296]
- [x] [Review][Patch] The `MINMAX` strip crosses one nesting level only — `minmax(max(min(176px, 25%), 8rem), 1fr)` is left unstripped and its `1fr` false-fires the AC 2 guard [ui/tests/shell.test.ts:201]
- [x] [Review][Patch] The collapsed-track assertion identifies the media-query variant by array index (`collapsed[1]`) — nothing ties index 1 to "inside the media query"; tie it to the media block's source position [ui/tests/shell.test.ts:426-430]
- [x] [Review][Patch] `findClippedRoot`'s message says "on a root element" even when firing on `.app-shell-columns`, which the guard's own comment calls "one element below the roots' floor" [ui/tests/shell.test.ts:258]
- [x] [Review][Patch] `ui/README.md`'s ban-table row for the root-height guard omits that it also fires on `height: 100%` — a reader consulting the table would write `html { height: 100% }` in good faith [ui/README.md:213]
- [ ] [Review][Patch] **NOT APPLIED — deliberately, and this is the one open item.** AC 7's sentence still says the inset is `var(--space-6)` while the ruled deviation ships `--space-gutter` — the finding asks for the AC text to be amended. Declined on process grounds, not on substance: `dev-story` may modify only the frontmatter `baseline_commit`, the task checkboxes, the Dev Agent Record, File List, Change Log and Status, and **an implementer silently rewriting an acceptance criterion to match what was built is the exact shape that rule exists to prevent** — even when the deviation was ruled and correct. The deviation is instead recorded in three places a reader will hit first: the v1.1 Change Log entry, an eight-line comment on the assertion in `ui/tests/shell.test.ts`, and the CSS declaration's own comment. **Brad's call whether to amend AC 7 itself.** [story file, AC 7]
- [x] [Review][Patch] The badges placeholder names c2-7 (the primitive's supplier) but its fillers are c4-2/c4-10 per the prop doc and README — the one region whose replacing stories could delete the line without a test noticing [ui/src/components/AppShell/AppShell.tsx:110; ui/src/components/AppShell/AppShell.test.tsx]
- [x] [Review][Patch] `App.test.tsx`'s comment overclaims — "`main` alone is enough to prove App composed the shell" is exactly what a bare `<main/>` impostor disproves; the file's *heading* test is what carries the composition proof, and the comment should say so [ui/src/App.test.tsx:28-29]

Dismissed as noise (3): `documented()` accepting any same-value citation anywhere in the file
(per-value-per-file is the sensible unit — a second `452px` genuinely shares the first's
source); AC 22 not auditable from the diff (generated assets were excluded from review scope
by agreement; the `plugin/` mirror re-verified byte-identical during triage); the AC 18 gate
walking only `src/components/**` while the README's blockquote states the rule generally (the
gate's scope is disclosed explicitly one paragraph below the rule — non-component stylesheets
are review's half).

## Dev Notes

### Decide-once rulings this story sets (c2-7 … c2-10, c4, c5, c6, c7 inherit)

1. **Component file layout** (Q1) — every later component follows it without asking.
2. **Who owns the scroll** (Q2) — the shell does, once; no later component introduces a second
   window-level scroll container.
3. **Landmarks** (Q4) — `header` / `main` / `footer`, both columns inside `main`, no `<aside>`.
4. **Geometry literals are a named, documented non-ban** (AC 18) — not a token, not a lint rule, but
   never unexplained either.
5. **The overlay is `fixed` and there is exactly one** (AC 8, AC 10).

### The three things this story inherits and must not break

- **The token layer is complete and closed.** 64 tokens, asserted by count *and* byte-for-byte
  against DESIGN.md. Every colour, radius, shadow, space, duration and type role you need already
  exists. If a value you want has no token, it is either the wrong value or a geometry literal
  (AC 18) — it is never a new token in this story.
- **The typography ban is total.** `font`, every `font-*` longhand, `line-height`, `letter-spacing`,
  `word-spacing` and `text-indent` accept only the role/family/tracking tokens (plus `0` and the
  CSS-wide keywords). Type comes from `var(--type-*)`, always, including in the header.
- **The gates are the enforcement mechanism, and they are cheap.** `npm run lint` is ESLint **and**
  stylelint in one script. Run it constantly; do not batch a stylesheet and discover eight errors.

### Previous story intelligence (c2-5, PR #22, Greptile 5/5 at round **1** — the epic's first one-round clear)

- **The review theme, three stories running: _the one exempted thing is where the next evasion
  lives_.** c2-5's carve-out property, exempted file and allowed namespace each admitted exactly the
  class they were carved out to manage. **This story's equivalents are already visible**: AC 6's
  `overflow: hidden` ban must exempt the content region's legitimate `overflow: auto`, and that
  exemption is where the next hole will be — write the guard so a `body { overflow: auto }` or an
  `overflow: clip` cannot walk through it.
- **The fix shape that generalises: ban the family, never enumerate members** — and prove it with an
  *invented* member so the test is a family test rather than an enumeration test. c2-4 learned this
  twice (regex property keys, then `calc(` → `min`/`max`/`clamp`); c2-5 learned it a third time.
- **Declare a guard's blind spot in the same breath as the guard.** Every guard in this codebase
  states what it cannot see, and c2-4's review made that a patch when one did not. The shell's
  guards are static CSS readers; the render tree lives in TSX and is chosen at runtime, so the
  cross-file half is review's — say so.
- **A prediction about a blind spot can be wrong in the safe direction.** c2-5 predicted its pairing
  guard's limit and measured the opposite. **Write the assertion the way it measures, not the way it
  was predicted**, and say the prediction was wrong.
- **When a patch invalidates an earlier proof, replace the proof rather than re-assert it.**
- All of c2-4's and c2-5's open questions were answered "as proposed" before Task 0, and nothing
  surfaced mid-story — four stories running. The five below are written to be answerable in one pass
  for the same reason.

### Git intelligence

The last five commits are c2-5 in the house shape: **implementation → records → review patches
(message names the theme) → records → merge → PR-green note**. Conventional Commits, scope
`companion`. `feat/companion-c2` is level with `origin` at `2a22e19`, working tree clean —
**this story is not blocked**, unlike c2-5, which had to wait on PR #21. Branch off the umbrella
now; the story PR targets the umbrella with a Greptile pass (the per-epic integration PR gets
none — standing rule).

### Source tree — what exists, what this story adds

```
ui/
  README.md                    UPDATE  component convention; geometry non-ban; ban-table rows;
                                       rewrite "Not here yet"; repair 355-358
  eslint.config.js             UPDATE  comment only — repair 78-79
  src/
    components/<Q1 shape>      NEW     the shell: .tsx + .css + colocated .test.tsx
    App.tsx                    UPDATE  composes the shell; repair the 6-9 docstring
    App.css                    ?       per Q1/AC 19 — replaced by the shell stylesheet, or
                                       reduced to nothing; either way AC 19 governs the anchor
    App.test.tsx               UPDATE  the h1/main assertions move onto the shell (landmine 6)
    index.css                  UPDATE  the box-sizing reset (AC 13); body/height reconciliation
  tests/
    token-usage.test.ts        UPDATE  the non-vacuity anchor (AC 19); the overlay-confinement
                                       and overflow guards live here or beside them
    shell.test.ts              NEW?    the stylesheet-reading guards, if not folded above
src/companion/app/static/      REGENERATED
plugin/…/static/               REGENERATED
```

Nothing else. No `.py` logic, no route, no store.

### Gotchas specific to this story

1. **`1fr` is `minmax(auto, 1fr)`.** The single highest-value line in this story. Bare `1fr` is the
   spelling everyone writes and it is the one that overflows.

2. **`min-height: 0` on the scroller** (AC 12). The second highest-value line, and the one whose
   symptom points at the footer rather than at itself.

3. **`box-sizing` first** (landmine 1). Add it before sizing anything, or the first height you write
   will be wrong by exactly the padding and you will adjust the wrong number.

4. **`git add` before running the guards** (landmine 10). A guard written against an untracked
   stylesheet passes vacuously. Both prior stories hit this.

5. **Ban the family, not the member.** For AC 6 that means keying on the `overflow` family — `overflow`,
   `overflow-x`, `overflow-y`, and the values `hidden` **and `clip`** — on the root elements, and
   proving it with a spelling the test did not enumerate. For AC 10 it means keying on the
   *shape* (a full-window fixed layer), not on a class name.

6. **Do not copy the mock's `absolute`** (landmine 11), its inline `box-sizing`, its `18px` gap
   (landmine 12), or its `<div onClick>` nav pills — the last is a UX-DR47 lint error and c6-8's
   work regardless.

7. **The header's `h1` is structural, its content is provisional.** c4-2 replaces the text; nothing
   about the element, its level or its position moves. Write it so that is a one-line change.

8. **An empty `<footer>` is a real landmark with no content, and that is fine** — c2-10 fills it.
   What is not fine is omitting the element and having c2-10 restructure the shell to add it.

9. **jsdom has no layout engine.** No grid track resolution, no media-query evaluation, no box
   geometry. Every geometry assertion in this story reads **CSS source**, never a rendered DOM —
   the same rule the reduced-motion block states about itself, and the same trap c2-4's AC 13 named.

10. **`npm run build` is the only thing that regenerates the bundle** — the pre-commit hook mirrors
    `src/` into `plugin/` but never rebuilds from `ui/`.

11. **Two `100vh`s already disagree.** `index.css` sets `body { min-height: 100vh }`. Whatever Q2
    lands on, reconcile that line with it deliberately rather than leaving two height mechanisms
    fighting — and prefer `dvh` if the shell owns the window height.

### Testing standards

- vitest, two projects. **Component tests are `.tsx` and live in `src/`** (the `dom` project);
  a `.test.tsx` under `tests/` is banned by `gate-geometry.test.ts`. Node-project gate/guard tests
  live in `ui/tests/`.
- Component assertions go through `@testing-library/react` **by role**, not by class name or test
  id — that is what makes the landmark ACs real rather than decorative.
- **Every new guard gets a proven pair** from one invocation, asserted by rule name and count where
  stylelint is involved, per fixture file (never in aggregate).
- **Non-vacuity anchor first** in any test that filters a list.
- Fixtures live in `tests/fixtures/`, are excluded from `npm run lint`, and are meant to stay broken.
- Python side: no new tests; re-run the suite to prove nothing moved.

### Architecture rules this story implements

- **UX-DR8** — the two-column composition, its breakpoint, its reference width and the overlay slot.
- **UX-DR38** — the overlay stack is exactly one level deep (AC 10).
- **UX-DR44** — semantic landmark structure (AC 14, AC 15).
- **UX-DR5** — every spacing value from the scale; the mock's one-offs are drift.
- **UX-DR32 / NFR-08** — the footer is a release condition, which is why AC 11 is a mechanism and
  not a preference.
- **AD-13** — the build output is a committed artefact; a component is a bundle change.
- **NFR-07** — the frontend gates are the enforcement mechanism.
- **FR-20** — the visual identity; this story finishes its structural half.

### References

- [epics-companion-app.md#Story-2.6](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  five AC blocks (lines 1375-1402)
- [epics-companion-app.md#UX-DR8](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  composition, breakpoint and overlay inset (lines 372-378); UX-DR38 (line 553)
- [DESIGN.md#Layout--Spacing](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md)
  — the composition in prose, 452px, ~1100px, 1720px, "panels float" (lines 315-328)
- [Planeswalker Companion.dc.html](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/imports/claude-design/Planeswalker%20Companion.dc.html)
  — **the composition reference** (EXPERIENCE.md frontmatter names it as such): the root slab at
  line 31, the `1fr 452px` grid at line 53, the left column's `min-width: 0` at line 55, the
  agent-view overlay at line 151
- [EXPERIENCE.md#Foundation](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md)
  — the target window range and the one-level overlay stack (lines 19, 51)
- [c2-5 story record](_bmad-output/implementation-artifacts/c2-5-self-hosted-space-grotesk-with-offline-parity-and-tabular-numerals.md)
  — the confinement-guard shape, the machine/human AC split, the review theme
- [c2-4 story record](_bmad-output/implementation-artifacts/c2-4-the-voltglass-token-layer.md) —
  the token layer, its guards, "ban the family"
- [ui/README.md#The-token-layer](ui/README.md) — the ban table this story extends (lines 194-208)
  and *Not here yet* (lines 350-358)
- [ui/eslint.config.js](ui/eslint.config.js) — the inline-style ban and the comment naming this
  story (lines 71-100)
- [epic-c1-retro-2026-07-26.md](_bmad-output/implementation-artifacts/epic-c1-retro-2026-07-26.md)
  — forward-dated-comment homing, open-question homing, non-vacuity pairing

## Open questions for Brad — answer before `dev-story`

Each carries a recommendation; "as proposed" on all five is a complete answer. Q1, Q2 and Q4 are
**decide-once rulings that ~35 later stories inherit**, which is why they are questions rather than
choices made in the implementation.

**Q1 — where do component files live?** *Recommendation:*
**`src/components/<Name>/{<Name>.tsx, <Name>.css, <Name>.test.tsx}`** — a directory per component,
no `index.ts` barrels. Reasons: ~25 components are coming (Panel, Badge, StatChip, GroupHeader,
ManaPip, ManaCost, CardTile, DeckRow, …), and flat would be 75+ files in one directory; the
colocated `.test.tsx` lands in the `dom` vitest project automatically and satisfies
`gate-geometry.test.ts`'s "no `.tsx` tests under `tests/`" rule with no thought; `src` is already in
`tsconfig.app.json`'s `include`, so nothing configuration-side changes. Barrels are declined because
each one is a file per component that exists only to re-export, and they make the ESLint
`only-export-components` rule harder to reason about. The shell is the first inhabitant, as
`src/components/AppShell/`.

**Q2 — who owns the scroll, and how is the footer pinned?** *Recommendation:* **a
viewport-height shell** — the shell root is `height: 100dvh` with `box-sizing: border-box`, the
header and footer are static children, and the two-column region between them is the **single
scroll container** (`flex: 1; min-height: 0; overflow-y: auto`). The footer is then *literally*
always in the window, which is what UX-DR32 and NFR-08 require, and the fixed overlay's inset
coincides exactly with the shell's own gutter. The alternative — document flow plus a
`position: fixed` footer — requires reserving bottom padding equal to a footer height that is
content-dependent, and it is the shape that produces "the attribution is behind the last row of
cards" on some window sizes. A third option, `position: sticky; bottom: 0`, is declined: sticky
inside a scrolling document has well-known interactions with `overflow` ancestors that later
stories would keep rediscovering. Consequence to accept: the scrollbar sits at the content
region's edge rather than the window's, which is the normal appearance of an app-shell SPA.

**Q3 — what does the header show before any deck exists?** *Recommendation:* **the kicker plus an
`h1` carrying the product name**, exactly as today — "Artificial Planeswalker" in the kicker's
place per DESIGN.md, with the `h1` holding the product name **provisionally** until c4-2 supplies
the deck name. Keeping an `h1` present means the document is never heading-less, `App.test.tsx`'s
existing assertion survives in a restated form, and c4-2 changes one string. The alternative —
render no `h1` until a deck arrives — leaves the app with no top-level heading in the
no-active-deck state, which is the state a fresh install *starts* in, and it makes c2-9's state
panel (an `h2` by UX-DR44) the highest heading on the page.

**Q4 — landmarks: is the right column an `<aside>`?** *Recommendation:* **no.** `<header>`
(banner), a single `<main>` containing **both** columns, `<footer>` (contentinfo). The right column
holds the card detail panel, the deck list and the format check — the deck list is FR-05's primary
content, satisfied "as a permanent second column rather than a toggled alternate view"
(EXPERIENCE.md), so marking it complementary would demote the very thing the redesign promoted.
The individual panels carry their own `role="region"` labels (UX-DR44), which is where the
per-panel semantics belong.

**Q5 — is `overflow: hidden` banned by a guard, or by review?** *Recommendation:* **a guard**
(AC 6). It is three lines of the same shape as the guards already in `token-usage.test.ts`, and
the thing it prevents is a *correct-looking fix applied to the wrong problem* — the class of
defect this epic's reviews have found in every single round. The narrower alternative (ban it only
on `html`/`body`/the shell root and let review own the rest) is what is recommended; a blanket ban
would fight c4-5's panel and c6-5's overlay, both of which legitimately clip.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (`claude-opus-5[1m]`), via the `bmad-dev-story` workflow.

### Open questions — answered

All five answered **"as proposed"** by Brad before Task 0 (2026-07-28), the fifth story running
where nothing surfaced mid-implementation:

- **Q1** — `src/components/<Name>/{<Name>.tsx, <Name>.css, <Name>.test.tsx}`, no barrels.
- **Q2** — a viewport-height shell; `<main>` is the single scroll container.
- **Q3** — kicker plus an `h1` carrying the product name provisionally.
- **Q4** — `header`/`main`/`footer`, both columns inside `main`, no `<aside>`.
- **Q5** — the `overflow: hidden` ban is a guard, narrow (root elements only).

A **fifth decide-once ruling the story did not anticipate** was forced by a gate and is
recorded with the other four: **class names are flat kebab-case, prefixed with the component**
(`app-shell-header`), never BEM's `__`. stylelint-config-standard's `selector-class-pattern`
makes BEM a lint error — measured, **12 errors**, by swapping `-` for `__` in this stylesheet.
The gate had already picked a convention; loosening it to fit a habit would have been the
wrong repair, and it is now in `ui/README.md` where c2-7 will read it.

### Debug Log References

**Baseline at `2a22e19`** — frontend **173 passed / 13 files**; `lint`, `format:check`,
`typecheck`, `build` all exit 0; Python **1,753 passed / 1 skipped / 45 deselected**;
`src/companion/app/static/` and `plugin/` clean after a build. The Python suite's first run
failed `test_list_decks_with_strategy_field` — exactly the documented `created_at`-tie flake —
and was clean on re-run, as Task 0 predicted.

**Final** — frontend **211 passed / 15 files** (+38 tests, +2 files); all five gates exit 0;
Python **1,753 passed** unchanged.

**Two things measured that the story had not, both caught by an anchor rather than by
inspection:**

1. **`git ls-files 'src/**/*.css'` silently omits `src/index.css`.** git's wildmatch requires
   `**` to consume at least one path component, so the pathspec returned the three *nested*
   stylesheets and dropped the one carrying the box-sizing reset. The new guard's non-vacuity
   anchor failed on its first run — which is what anchors are for. Fixed to `'*.css'` then
   filter, matching `token-usage.test.ts`'s existing shape, and the reason is in the code.
2. **My own AC 18 guard was vacuous, and the probe is what proved it.** It asked whether *some*
   comment mentioned `452px` and *some* part of that comment said `DESIGN.md`. Probe 10 deleted
   the real citation and the guard **stayed green**, because the file-header comment happens to
   contain the phrase "the 452px track" and a reference to DESIGN.md's frontmatter four hundred
   characters away. Rewritten as a **derived family rule**: every `\d+px` literal found in the
   *code* (not a hard-coded list) must have `DESIGN.md` within 60 characters of it in a comment.
   It then fired. This is the epic's standing theme arriving in my own test — a guard satisfied
   by something other than the thing it checks.

**Evasion probes — eleven planted in the REAL tree, each verified on disk before the verdict
was believed, each reverted:**

| # | Evasion planted | Verdict |
| --- | --- | --- |
| 1 | `grid-template-columns: 1fr 452px` in AppShell.css | **2 tests fail** — the pin and the family guard; message names `minmax(0, 1fr)` |
| 2 | `body { overflow-x: hidden }` in index.css | **fails** — "…true by CLIPPING the overflowing content instead of fitting it" |
| 3 | `.rogue-agent-veil { position: fixed; inset: 0 }` in index.css | **fails** — names UX-DR38 and the shell's slot as the fix |
| 4 | `@media (max-width: 1099px)` | **stylelint: 1 error, `media-feature-range-notation`**, plus the value-pinning guard |
| 5 | overlay `position: absolute` | **2 tests fail** — AC 8 directly, and the layer stops being found where it belongs |
| 6 | the `box-sizing` reset deleted | **fails** (AC 13) |
| 7 | `min-height: 0` deleted from the scroller | **fails** (AC 12) |
| 8 | `body { min-height: 100vh }` restored | **fails** — the competing-height guard |
| 9 | a `useState` added to AppShell.tsx | **fails** (AC 16) |
| 10 | the `452px — DESIGN.md` citation deleted | **passed at first — guard rewritten — then failed** (above) |
| 11 | `overflow: clip` on `.app-shell` — a value the test never enumerates | **fails** (AC 6, by family) |

Probe 10 is the one worth carrying into c2-7: **a probe that passes is information, not a
formality.** The fixture's own unenumerated members (`overflow-block`, `grid-auto-rows`, the
two-value `overflow: hidden auto`, a full-window layer built from four physical longhands, and
one built from viewport units alone) are asserted inside `tests/shell.test.ts` as well, so each
guard is proven to be a family test rather than an enumeration test.

### Completion Notes List

**What shipped.** The first component in the codebase: `src/components/AppShell/`, composed by
`App.tsx`, plus a global `box-sizing` reset, a new node-project guard suite
(`ui/tests/shell.test.ts`, 27 tests) and its violation fixture. Frontend suite 173 → **211**.

**The five conventions ~35 later stories inherit** are in `ui/README.md` under a new
*Components* section (AC 17): the file layout, kebab-case class names, the export rule
(`allowConstantExport` admits constants and types, never a helper function), assert-by-role in
component tests, and the shell's ownership of the window and the scroll.

**Geometry literals are now a named, documented non-ban** (AC 18) — in the `ui/README.md` ban
table as an explicit exception with its reason, because there is no token family to point at
and `declaredTokens.size === 64` plus DESIGN.md's byte-for-byte contract make adding one
unavailable. Exactly two **px** literals exist (`452px`, `1100px`), both cited to DESIGN.md
beside the value, both pinned by test — `z-index: 20` is a third geometry literal outside the
guard's px-only scope, documented in prose beside its rule and homed in deferred-work. c2-7's 17px, c2-9's 480px and c4-4's 176px inherit a stated rule.

**AC 19 — the anchor was re-pointed at a shape, not a file.** `token-usage.test.ts` named
`src/App.css` by path, and this story deleted that placeholder. Naming a third file would have
reproduced the same fragility, so the anchor now asserts *at least one stylesheet under
`src/components/`* — structural, because the component-directory convention is a decide-once
ruling and the app cannot render without a shell.

**AC 20 — the forward-dated sentences.** All four repaired in this commit:
`ui/README.md`'s *Not here yet* (rewritten around what the shell actually holds open, each
region naming its owner), `ui/eslint.config.js:78-79` (the inline-style ban's bet is now
settled: the first component, whose whole job is geometry, needed no escape hatch),
`ui/src/App.tsx` (rewritten) and `ui/src/App.css` (deleted with the placeholder).
**`ui/tests/fixtures/tsx/clean.tsx:4` was judged and deliberately KEPT** — "This is what c2-6
and c2-7 write" describes the fixture's *purpose*, not a future state, and it is still true
now that c2-6 has written exactly that. Sweeping it would have removed the sentence that
explains why the fixture exists.

> **AC 4 AND AC 5 EACH HAVE A HUMAN HALF THAT IS *NOT* DEV-VERIFIED.** This is the third time
> (c2-2 AC 17, c2-5 AC 4) and it is now a pattern rather than an exception. **Mechanical, and
> done:** the gutter and panel-gap come from tokens, the right column is exactly 452px, the
> breakpoint is exactly 1100px in the context range form, the fluid track is `minmax(0, 1fr)`,
> and both column and track are floored at zero — all pinned by `tests/shell.test.ts`.
> **Human, and outstanding:** that it *looks like* the composition reference at 1720px, and
> that the body never scrolls horizontally between ~1100px and ~2560px. jsdom has no layout
> engine — no grid-track resolution, no media-query evaluation, no box geometry — so any
> `getComputedStyle` assertion here would be vacuous by construction, and faking it would be
> worse than declaring it. Added to the epic manual-testing checklist:
>
> 1. Open at **1720px** and compare against the composition reference — header, fluid left
>    column, 452px right column, footer, panels floating with visible canvas between them.
> 2. Sweep **~1100px → ~2560px**: no horizontal scrollbar at any width, and the right column
>    drops beneath the left below 1100px rather than compressing.
> 3. On a **long deck**, confirm the footer stays visible without scrolling and that the
>    scrollbar sits at the content region's edge (the intended app-shell appearance, Q2).

**Deliberately not built** (each with a placeholder line naming its owner, AC 21): the
primitives (c2-7), the state panel (c2-9), the footer's text (c2-10), the card grid (c4-4), the
curve/colour pair (c4-8/c4-9), card detail (c4-5), the deck list (c4-7), the format check
(c4-10), the nav pills (c6-8), the agent view (c6-5), the skip link and Tab order (c4-11). No
store, no fetch, no route, no Python. **UX-DR8's 1:1 curve/colour row is c4-8's** — a `1fr 1fr`
sub-grid shipped empty here would be a second piece of geometry with nothing to hold it honest;
the shell gives the left column a vertical flow at the panel-gap and c4-8 nests the pair in.

**One thing a reviewer should look at rather than assume the gate did.** These guards are
static readers of CSS source. A full-window layer composed at runtime from two classes on one
element, a root reached through a class the guard does not recognise as root, or an overflow
set from JavaScript are all invisible — the render tree lives in TSX and is chosen at runtime.
That limit is declared in the guard file's own header, in the same breath as the guards, per
the c2-4 review's ruling.

**A visible oddity that is a decision, not a bug:** the kicker and the `h1` both read
"Artificial Planeswalker" until c4-2 lands. That is Q3's accepted consequence of never leaving
the page heading-less in the no-active-deck state a fresh install starts in, and c4-2 resolves
it with one prop. It is commented where it renders.

### File List

**New**

- `ui/src/components/AppShell/AppShell.tsx`
- `ui/src/components/AppShell/AppShell.css`
- `ui/src/components/AppShell/AppShell.test.tsx`
- `ui/tests/shell.test.ts`
- `ui/tests/fixtures/css/shell-violation.css`

**Modified**

- `ui/src/App.tsx` — composes the shell; docstring repaired (AC 20)
- `ui/src/App.test.tsx` — landmark/heading assertions restated around the shell (landmine 6)
- `ui/src/index.css` — the `box-sizing` reset (AC 13); `body { min-height: 100vh }` removed
- `ui/tests/token-usage.test.ts` — the non-vacuity anchor re-pointed (AC 19)
- `ui/eslint.config.js` — comment only, forward-dated sentence repaired (AC 20)
- `ui/README.md` — *Components* section (AC 17), the geometry-literal non-ban and five new ban
  rows (AC 18), *Not here yet* rewritten (AC 20)

**Deleted**

- `ui/src/App.css` — the placeholder the real shell replaces (AC 19, AC 20)

**Regenerated (AD-13)**

- `src/companion/app/static/` — `index.html` + the content-hashed `.css`/`.js`
- `plugin/server/src/companion/app/static/` — the same, mirrored

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-07-28 | 1.3 | **Greptile round on PR #23 — 2 of 2 P2 findings applied.** Greptile scored **3/5, "not yet safe to merge"** while its CI check reported *pass* — a green check is not a green review, and the score is the signal. Both findings reproduced before being acted on, all three probe cases failing against shipped code. (1) **`filled()` counted empty React nodes as filled**: an empty Fragment is a React *element* and a `Set` is not an array, so `overlay={<></>}` mounted a full-window `position: fixed` div containing nothing — **AC 9's click-swallower, the exact failure this story wrote an AC to prevent** — and `left={<></>}` silently dropped its placeholder. Fixed in two layers because the problem has two: `filled()` moved to `src/components/AppShell/filled.ts` (deciding Fragment-emptiness needs react VALUE imports, and the shell's react import is pinned type-only — the blunt guard stayed blunt, the exhaustive import list grew by one named entry), now covering every empty shape a CALLER can express; and `.app-shell-overlay:empty { display: none }` closes the residue `filled()` **cannot** decide, since a child component may `return null` and that is not statically knowable. The limit is stated in `filled.ts`, not left to be found. (2) **`pxLiteralsIn()` scanned CSS strings**: `content: "16px"` read as an undocumented geometry literal with nothing in DESIGN.md to cite — a false positive on c2-7 and c4-8, which this file's doctrine calls worse than the defect. One line; `blankStrings` already existed three helpers above and the scanner was not using it. Both mutation-tested red-on-revert. Frontend **223 → 228 passed / 15 files**; Python **1,753** unchanged; five gates green; bundle and `plugin/` mirror regenerated. | Amelia (Dev) |
| 2026-07-28 | 1.2 | **Review round 2 — 17 of 18 patches applied, 1 declined on process grounds.** Round 2's theme was one layer deeper than round 1's: where round 1 found guards missing family members, round 2 found *the repairs themselves stopping one member short* — the lookbehind added to `documented()` but not to `FULL_PERCENT`, comments stripped for the CSS half but not the TSX half, `filled()` made value-aware for three empty shapes but not the fourth, the `minmax` matcher taught to cross one nesting level rather than to count. Closed: `contain`/`clip-path` as unenumerated ways to clip a root; `:not()` and descendant-`*` selector spellings (both directions — `:not(html)` now fires, `.card-tile *` now stays silent); a `>= 100` magnitude floor on viewport units so a `40vw` drawer is not an overlay; `max-*` excluded from "spans the axis" so a capped toast is not either; paren-aware splitting for `inset` shorthands and unbounded-depth `minmax`; fractional px literals tokenised whole so a truthful `17.5px — DESIGN.md` citation is satisfiable; bare side-effect imports caught; the media-query assertion tied to the media block's own source rather than `collapsed[1]`; `filled()` extended to empty arrays and whitespace-only strings, and applied to the overlay slot it had skipped; the clip message no longer calls the scroller "a root element". **Two probes were found VACUOUS by mutation and rewritten rather than shipped**: prettier rewrites `content: "\""` into a string with no escape at all, and — measured — a stray brace from a naive blanker only truncates its own block, because the reader resynchronises on the next balanced pair and its character class cannot cross a newline, so no fixture probe can ever prove that repair. It is now asserted directly against `blankStrings`, and the fixture says plainly that it is documentation rather than proof. Every new repair mutation-tested: reverting each turns the suite red. **Declined:** amending AC 7's text to match the ruled `--space-gutter` deviation — an implementer rewriting an acceptance criterion to match what was built is what the permitted-sections rule exists to prevent; the deviation is recorded in three other places and the amendment is Brad's call. Frontend **214 → 223 passed / 15 files**; Python **1,753** unchanged; all five gates exit 0; bundle and `plugin/` mirror regenerated. | Amelia (Dev) |
| 2026-07-28 | 1.1 | **Code review round — 19 patches applied, 0 deferred, 3 dismissed; story → done.** Three-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor); the Auditor accepted outright with all gates re-verified live. The findings were almost entirely the epic's standing theme arriving in the guard suite itself — guards advertising "family, not enumeration" but proven only against their own fixture's spellings. Closed: `%`-sized and mixed-axis full-window layers, the within-block cascade (`valueOf` now last-wins), a `}`-inside-a-string parser desync, `max-content` track floors, nested-`minmax()` false-fires, `:is()/:where()`/universal/compound selector spellings of the root bans, substring-satisfied citations, and the presentation guard's quote/alias/`use()`/dynamic-import holes — each with a new fixture probe, firing and silent. Component fixes: `slot()` and the `h1` fallback are value-aware (`false`/`""` no longer swallow a placeholder or blank the heading), `c4-9` joined the owner list, `App.test.tsx` stopped duplicating the landmark triple. Three Brad rulings, all "as recommended": **the AC 18 citation guard now runs over every component stylesheet** (the rule ~35 stories inherit became a gate, shell pin kept as non-vacuity); **the clip ban extends to `.app-shell-columns`**, the one scroller, values-only so its `auto` stays legal (a deliberate widening of Q5's root-only scope); **the overlay inset is `var(--space-gutter)`**, a recorded deviation from AC 7's literal `--space-6` — same 32px today, but the overlay's contract is alignment with the frame. `c7-2`→`c2-7` StatChip transposition fixed in both new homes; "exactly two literals" corrected to two **px** literals with `z-index: 20` named. Frontend **211 → 214 passed / 15 files**; Python **1,753** unchanged; all five gates exit 0; bundle and `plugin/` mirror regenerated. | Claude Fable (Review) |
| 2026-07-28 | 1.0 | **Implemented.** The first component in the codebase: `src/components/AppShell/` (tsx + css + colocated test), composed by `App.tsx`; a global `box-sizing` reset in `index.css` and `body { min-height: 100vh }` removed with it; a new node-project guard suite `ui/tests/shell.test.ts` (27 tests) with its violation fixture. Frontend **173 → 211 passed / 15 files**; Python **1,753** unchanged; all five gates exit 0; bundle and `plugin/` mirror regenerated. All five open questions answered "as proposed", plus a sixth decide-once ruling the story did not anticipate — **class names are flat kebab-case, not BEM**, because `selector-class-pattern` makes `__` a lint error (measured, 12). Eleven evasions planted in the real tree and all eleven caught — but **probe 10 passed first**, exposing that my own AC 18 documentation guard was satisfied by a comment four hundred characters away from the value; rewritten as a derived family rule (every `\d+px` in the code needs a `DESIGN.md` citation within a sentence) and re-probed. The non-vacuity anchor also caught that `git ls-files 'src/**/*.css'` silently omits `src/index.css`. AC 4's and AC 5's render halves are **not** dev-verified — jsdom has no layout engine — and are on the epic manual-testing checklist in `deferred-work.md`, the third story running to split an AC that way. All four forward-dated sentences repaired; `clean.tsx:4` judged and deliberately kept. | Amelia (Dev) |
| 2026-07-28 | 0.1 | Story contexted from the epic + DESIGN.md + EXPERIENCE.md + the composition reference. Twelve landmines measured at `2a22e19` — notably that **no `box-sizing` reset exists anywhere in `ui/`** (so a padded 100dvh shell silently overflows the window), that the `max-width` spelling of the breakpoint is a **lint error** (the context range form is mandatory), that **geometry literals are the ungated value family** and cannot become tokens without breaking two pinned assertions, that `token-usage.test.ts`'s non-vacuity anchor names `src/App.css` by path, and that the composition reference's `position: absolute` overlay is wrong in a real browser because the document is taller than the window. 25 ACs (numbered 1-24 plus 15b), 20 beyond the epic's five blocks; five open questions homed with recommendations, three of them decide-once rulings ~35 later stories inherit. AC 4 and AC 5 split into machine-verifiable and human halves rather than implied (jsdom has no layout engine — the c2-2 / c2-5 precedent, now three deep). AC 10 added because a second full-window overlay escapes every value-level rule, the same shape as c2-5's `@font-face` confinement guard. Not blocked — c2-5 is merged at `502a646`. | Bob (SM) |
