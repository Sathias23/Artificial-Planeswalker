---
epic: c2
story: c2-7
work_branch: feat/companion-c2
story_branch: feat/companion-c2-7-presentation-primitives
depends_on: none — c2-6 (PR #23) is merged into the umbrella at a117568
baseline_commit: a5eb071
---

# Story C2.7: Presentation-only primitives — Panel, Badge, StatChip, Group header

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer building every later surface,
I want the four pure container and label primitives available and tokenised,
so that panels, badges, stat chips and group dividers look identical everywhere without being
reimplemented.

**What this story really is.** c2-6 wrote the first component and set five conventions. This story
writes the first **library** — four components that ~20 later stories compose without opening
again — and it is the story where **the design contract and the token layer finally disagree in
public**. Every one of the four primitives is specified in DESIGN.md with at least one value the
shipped gates refuse: a `font-size: 17px` override, an `rgba()` tone tint, a `2px 9px` padding, a
partly-tokenised glow. None of those is a mistake in either document — DESIGN.md's `components.*`
block was lifted from a mock that the same file's own prose (UX-DR5, UX-DR1, "every shadow through
a token") corrects three sections later. **The work is deciding, once, what each of those becomes,
and recording it where the next twenty stories read it.**

The second thing it is: **the first consumer of the gate c2-6's review handed forward.** The
DESIGN.md-citation check now runs over *every* tracked stylesheet under `src/components/`, so the
moment this story stages a `border: 1px solid …` it inherits a gate that did not apply to anything
before it. That is a good thing and it will bite on the first block written.

**Fifteen things were measured on this machine at `a5eb071` — do not rediscover them:**

1. **`font-size: 17px` is a lint ERROR.** Measured, on a probe file under the real config:
   `declaration-property-value-allowed-list`. The `font-*` family entry admits only CSS-wide
   keywords. **The mock's StatChip does exactly this** — `font: var(--type-numeric); fontSize: 17` —
   so the one declaration DESIGN.md's StatChip spec is built around cannot be written. AC 11 and Q1
   decide what replaces it.

2. **`color-mix()` is banned, along with `rgba()`.** Measured: `function-disallowed-list` fires on
   `color-mix(in srgb, var(--positive) 12%, transparent)`. **The mock's Badge tones are
   `rgba(95,212,160,0.12)` backgrounds with `rgba(...,0.35)` borders** — five tones, ten literals,
   every one of them a build failure. AC 12 and Q2 decide the mechanism.

3. **`padding: 2px 9px` is a lint ERROR** (measured). Padding, margin and gap accept only
   `var(--space-*)` or `0`. The mock's `10px 14px` panel header, `12px 14px` panel body, `2px 9px`
   badge and `gap: 2` / `gap: 6` in StatChip are all off the 4/8/12/16/24/32/48 scale — UX-DR5 calls
   these one-offs **drift, not spec**. AC 13 snaps them.

4. **`border: 1px solid var(--border-hairline)` lints CLEAN — and still costs you a comment.**
   Measured: no stylelint rule objects. But `tests/shell.test.ts:835` runs the DESIGN.md-citation
   check over **every** tracked stylesheet under `src/components/`, and `1px` is a px literal. This
   story is the **first inheritor of that gate** (c2-6's review widened it from the shell's own file
   one story ago). Every `1px` and every `6px` needs `DESIGN.md` within 60 characters of the value
   in a comment in the same file.

5. **The live dot's glow cannot be copied from the mock.** `boxShadow: '0 0 8px var(--accent-glow),
   0 0 4px var(--accent)'` is a **partly-tokenised** shadow: the allowed-list admits only values
   built entirely from `var(--shadow-*)` / `var(--glow)`. `var(--glow)` is `0 0 16px
   var(--accent-glow)` and is the whole answer.

6. **NO TOKEN MAY BE ADDED.** `tests/token-usage.test.ts:436` pins `declaredTokens.size === 64` and
   `tests/tokens.test.ts` asserts every name byte-for-byte against DESIGN.md's frontmatter. There is
   no `--positive-glow`, no `--type-stat-value`, and this story does not create one.

7. **`filled()` lives at `src/components/AppShell/filled.ts`, and two assertions pin it there.**
   `tests/shell.test.ts:889` asserts the shell's import list is **exactly**
   `['./AppShell.css', './filled', 'react']`, and `:910` reads the helper by that path. Panel needs
   the same logic for its header slots. Reusing it means moving it and updating both assertions —
   which is the open way to do it. Q3.

8. **The numeric-pairing guard is BLOCK-LOCAL and fires on a split pair.** `font:
   var(--type-numeric)` and `font-variant-numeric: var(--type-numeric-features)` must be in the
   **same rule block**; a correct pair split across two blocks is reported as a failure (measured
   and asserted at `token-usage.test.ts:558`). This story is where that guard gets its first real
   consumers — the panel count and the group-header count.

9. **The mock's `minWidth: 76` (StatChip) and `letterSpacing: '0.04em'` (Badge) have nothing in
   DESIGN.md to cite.** Checked against the frontmatter: `components.stat-chip` declares no
   min-width, and `components.badge.type` is `{typography.label}`, whose tracking token is `0.1em`.
   A 76px literal would fail c2-6's AC 18 citation gate with no truthful citation available. **Drop the
   min-width; use `var(--tracking-label)`.**

10. **BEM class names are a lint error** — measured at 12 errors in c2-6. Flat kebab-case, prefixed
    with the component: `panel-header`, `badge-positive`, `stat-chip-value`, `group-header-count`.

11. **Native CSS nesting is banned and a bare `&` fails**, including `&:hover`. Write selectors out
    in full. A rule inside `@media` is depth 2 and legal.

12. **Inline `style={{…}}` is an ESLint error with no escape hatch.** The mock is written *entirely*
    in inline styles — it is a reference for arrangement and density, never for shape.

13. **jsdom renders nothing.** No `getComputedStyle` claim about colour, elevation or a tint is
    worth anything here. Component tests assert **structure, role and text**; every visual claim
    reads CSS **source** in the node project, or goes on the manual checklist (AC 21).

14. **`git add` before running the guards.** `shippedStylesheets` is built from `git ls-files`, so a
    new stylesheet is invisible to every guard — and passes vacuously — until it is staged. Three
    stories in a row have lost time to this.

15. **Baseline, measured at `a5eb071`:** frontend **230 passed / 15 files**; Python **1,753**
    (c2-6's final number — Task 0 re-verifies rather than assuming). Working tree clean; branch
    level with `origin/feat/companion-c2`.

**What this story does not do.** It does not **fill** anything. The header badge slot stays empty —
`AppShell.tsx:105-113` says so explicitly: *"c2-7 ships Badge without filling this slot"*, and c4-2
and c4-10 are its fillers. No ManaPip/ManaCost (**c2-8**), no state panel (**c2-9**), no footer text
(**c2-10**), no deck row, card tile, curve or colour bar (**c4**), no nav pill (**c6-8**). No store,
no fetch, no route, no Python.

**A consequence worth stating before it looks like a mistake:** because nothing imports the four
primitives, Vite has no reason to include them in the module graph, so **`npm run build` is likely
to emit a byte-identical bundle**. That is a prediction, not a fact — Task 7 measures it. Either way
the build runs and both trees are checked; a byte-identical bundle is the expected outcome, not a
skipped step.

## Acceptance Criteria

Epic-derived ACs are marked **[epic]**. The rest are requirements the epic's six blocks imply but do
not state; each says why it exists. An AC the epic did not write down is still an AC (standing
agreement: a story must leave the system working end to end).

### The four primitives

**AC 1 [epic].** **Given** the `Panel` component, **when** it renders, **then** it supports a
default and an `overlay` level (`--surface-panel` / `--surface-overlay`), an optional header
carrying a label title **plus** an optional numeric count **plus** right-aligned badges, and a
`live` state that swaps the title to `--accent`, adds a 6px accent dot and raises elevation to
`var(--shadow-raise)` (UX-DR9) — **and** its rest elevation is `var(--shadow-rest)`, applied via
token.

**AC 2 [epic].** **Given** the `Badge` component, **when** it renders in each of its five tones —
neutral, accent, positive, negative, caution — **then** each tints background and border from its
own semantic token, **never** from a hard-coded RGB (UX-DR10). See AC 8 for the mechanism, which is
the whole difficulty.

**AC 3 [epic].** **Given** the `StatChip` component, **when** it renders, **then** it shows a micro
label above a 17px numeric value, with an optional delta tinted positive or negative by sign
(UX-DR11). See AC 7 — the 17px cannot be a `font-size`.

**AC 4 [epic].** **Given** the `Group header` component, **when** it renders, **then** it shows an
uppercase label with a right-aligned numeric count over a hairline rule (UX-DR12).

**AC 5 [epic].** **Given** all four primitives, **when** their implementation is inspected, **then**
they hold no state, respond to no interaction, and have no behavioural contract beyond rendering
their props — this is deliberate and recorded, not an omission (UX-DR9–12). **Mechanically:** no
hook of any kind (including `useId` — see Q4), no `fetch`/`WebSocket`/`EventSource`, no store
import, no event handler prop, and an **exhaustive** import list per module, asserted the way
`tests/shell.test.ts:878-905` asserts the shell's.

**AC 6 [epic].** **Given** each primitive, **when** vitest runs, **then** unit tests cover every
documented variant and state: Panel × {default, overlay} × {rest, live} × {no header, title only,
title+count, title+count+badges}; Badge × 5 tones; StatChip × {value only, value+positive delta,
value+negative delta, value+zero delta}; Group header × {label+count}.

### What the gates refuse, and what replaces it

**AC 7.** **Given** the 17px StatChip value, **when** it is written, **then** it comes from a
**role token plus the numeric-features companion** — not a `font-size` literal (landmine 1,
measured) and not a new token (landmine 6). *Why an AC rather than an implementation detail: this is
the single value in the story that has no legal spelling of the obvious form, and the wrong reaction
is to add a stylelint exception.* **And** the three forward-dated sentences that predicted this
value would be a *geometry literal* — `ui/README.md:227`, `ui/tests/shell.test.ts:815`,
`ui/src/components/AppShell/AppShell.css:11` — are **repaired in the same commit**, because a
prediction that was measured wrong is exactly the sentence the next author trusts.

**AC 8.** **Given** the five Badge tones, **when** their background tint is written, **then** the
tint derives from the tone's **own token** with no colour literal and no colour function anywhere
(landmine 2, measured), **and** the mechanism is recorded once in `ui/README.md` because c6-7's
suggestion rows, c9-1's swap rows and c9-2's tier rows will each want the same thing. *Why: the
epic's AC says "tints background and border from its own semantic token"; the only spelling of that
in the mock is banned, so the shape is a decision, not a transcription.* See Q2.

**AC 9.** **Given** the mock's off-scale padding and gap values (landmine 3), **when** the
stylesheets are written, **then** every spacing value comes from `var(--space-*)` (UX-DR5), **and**
each snapped value carries a comment naming the mock value it replaces — so a reviewer comparing
against the composition reference sees a decision rather than a discrepancy.

**AC 10.** **Given** elevation and glow, **when** they are written, **then** every `box-shadow` is
built **entirely** from `var(--shadow-*)` / `var(--glow)` (landmine 5) — the live dot's glow is
`var(--glow)`, never the mock's `0 0 8px var(--accent-glow), 0 0 4px var(--accent)`.

**AC 11.** **Given** the geometry literals these stylesheets do need — the `1px` hairline border and
the `6px` live dot — **when** they are written, **then** each carries a `DESIGN.md` citation within
one sentence of the value (landmine 4: the gate `tests/shell.test.ts:835` already enforces this over
every component stylesheet, and this story is its first inheritor), **and** the mock's uncitable
`min-width: 76px` and `letter-spacing: 0.04em` are **not reproduced** (landmine 9).

### Type, contrast and the pairing rules

**AC 12.** **Given** the numeric role lands for the first time — the panel count, the group-header
count and the StatChip delta — **when** each is written, **then** `font: var(--type-numeric)` and
`font-variant-numeric: var(--type-numeric-features)` appear in the **same rule block** (landmine 8,
UX-DR3). *Why an AC: `deferred-work.md:1190` names this story as the first component that would
apply the role, and the guard that catches it has never had a real consumer.*

**AC 13.** **Given** the `--type-label` and `--type-micro` roles arrive in quantity for the first
time (badge text, panel title, group label, stat-chip label), **when** they are applied, **then**
each carries its tracking companion (`var(--tracking-label)` / `var(--tracking-micro)`) and
`text-transform: uppercase` in the same rule block — **enforced by a guard**, proven firing and not
firing. *Why: the `font` shorthand cannot carry `letter-spacing` or `text-transform`, so a label
applied bare renders at 11px with default tracking and lowercase text — legible, plausible, and
wrong. It is the identical failure shape as the numeric role travelling alone, and it has been
unguarded since c2-4. Same family, same fix.* See Q5.

**AC 14.** **Given** badges appear on `--surface-overlay` inside agent views (suggestion rows, swap
rows, tier rows), **when** the accent tone is written, **then** it uses `--accent`, **never**
`--accent-dim` (UX-DR6 — 2.70:1, below the 3:1 non-text floor). *Why an AC rather than trusting the
guard: `findAccentDimOnOverlay` is same-block only, and a badge whose container supplies the overlay
background is precisely the cross-block case the guard declares it cannot see. The fix is to not
write `--accent-dim` in this component at all.*

### Structure and semantics

**AC 15.** **Given** UX-DR44 ("panel titles and type-group headers `h2`"), **when** Panel renders a
title, **then** the title is an `<h2>` inside a `<section>` that carries an accessible name, so the
panel is exposed as a **named region** — which is the per-panel `role="region"` labelling
`AppShell.tsx:36-37` explicitly deferred to "the panels (c2-7 onwards)". **And** Group header
renders its label as an `<h2>` with the count beside it. **And** a Panel with no title renders a
plain `<section>` with no invented name.

**AC 16.** **Given** the count props (`Panel`'s header count, `Group header`'s count), **when** they
are rendered, **then** `count={0}` renders **"0"** and a header carrying only a count still renders.
*Why: `{count && <span>{count}</span>}` renders the bare string `0` into the DOM, and
`{title || count ? <header/> : null}` drops the header for a zero count. This is the exact family
c2-6 spent two review rounds on — a falsy value that is real content — arriving in numeric props
instead of node props. Asserted per component, not left to inspection.*

**AC 17.** **Given** Panel's header slots take arbitrary nodes, **when** it decides whether to
render its header at all, **then** it uses the **existing** `filled()` helper rather than a new
truthiness check (landmine 7). *Why: `filled()` is the settled answer to `<></>`, `[]`, `' '`,
`false` and one-shot iterables, and it took a Greptile round and two review rounds to get right.
Re-deriving it here would be the reinvention the convention exists to prevent.* See Q3 for where it
lives.

**AC 18.** **Given** the primitives introduce no motion, **when** the diff is inspected, **then**
there is no `transition` or `animation` in any of the four stylesheets, **and** the record says so
— *or*, if one is added, it registers its fallback in the reduced-motion block in `tokens.css`
(Decide-once #3: a motion with no registered fallback is an incomplete story). *Why: the panel's
`live` state is a state change an agent causes, and animating it belongs to **c7-5**, which already
owns "the change is announced once, and motion is never the only signal" — including the accent-glow
fade's registered fallback.*

### Records and boundaries

**AC 19.** **Given** this story writes the first component **library**, **when** it lands, **then**
`ui/README.md`'s *Components* section records what the next ~20 component stories inherit: the
primitive conventions decided here (heading and region semantics, the tone-tint mechanism, where a
shared helper lives, hook-free primitives), and the new guard joins the ban table. *Why an AC: the
same argument c2-6's AC 17 made, one layer up — a library whose rules are re-derived per consumer is
a library that stops being one.*

**AC 20.** **Given** the forward-dated sentences that name this story, **when** it lands, **then**
each is repaired **or explicitly judged and kept**, in the same commit (C1 retro homing rule). The
inventory, measured: `ui/README.md:227` (17px prediction — **wrong, repair**), `:436`
("c2-7's primitives restate the same posture" — tense), `:456-459` (*Not here yet* — the primitives
have landed; the header badges are still c4-2/c4-10's), `:465` ("Nothing applies the numeric role
yet" — **wrong after this story, repair**); `ui/tests/shell.test.ts:815` (17px prediction),
`:585`/`:1130` (`content: "16px"` in "a c2-7 tooltip" — illustrative, judge), `:1115` ("c2-7's
StatChip is a candidate" for the first fractional literal — judge);
`ui/src/components/AppShell/AppShell.css:11` (17px prediction, **repair**), `:87` (c2-7 fills the
header — still forward-dated and still true, keep); `ui/src/index.css:49`,
`ui/tests/fixtures/css/clean.css:112`, `ui/tests/fixtures/tsx/clean.tsx:4` (describe purpose, not a
future state — judge and keep, as c2-6 did); `_bmad-output/implementation-artifacts/deferred-work.md:1190`
(the numeric-role blind spot now has its consumer).

**AC 21.** **Given** the primitives have **no on-screen consumer** in this story, **when** the
visual half is considered, **then** the record states plainly that appearance is **not**
dev-verified — jsdom renders nothing — and homes it: the four primitives' looks are checked at their
**first consuming story** (c2-9's state panel, c4-7's deck list, c4-10's format check), with the
epic manual-testing checklist carrying the entry. *This is the fourth story to split an AC this way
(c2-2 AC 17, c2-5 AC 4, c2-6 AC 4/5); do not fake it with a `getComputedStyle` assertion.*

**AC 22.** **Given** any CSS or component change, **when** the story is committed, **then**
`cd ui && npm run build` runs and **both** the committed bundle and its `plugin/` mirror are
regenerated and committed if they change — and if the bundle is byte-identical (the prediction
above), the record says that it was **measured**, not assumed.

**AC 23.** **Given** the dependency graph, **when** it is inspected, **then** this story adds **no
dependency, runtime or dev**, and **no token** — `tests/tokens.test.ts` and the
`declaredTokens.size === 64` assertion are untouched (landmine 6).

**AC 24.** **Given** the scope, **when** the diff is inspected, **then** it touches no `.py` file
(except the regenerated mirror), no route, no store, no fetch layer, and none of the components
owned by c2-8, c2-9, c2-10, c4-*, c5-7, c6-5 or c6-8. `AppShell.tsx`'s placeholder copy is
**unchanged** — the header badge slot stays empty and keeps naming c4-2/c4-10 as its fillers.
`pyproject.toml` and `uv.lock` are untouched. The Python suite is re-run to prove it stayed at
**1,753**, not assumed.

## Tasks / Subtasks

- [x] **Task 0 — verify the baseline before changing anything** (standing agreement)
  - [x] Branch off `feat/companion-c2` as `feat/companion-c2-7-presentation-primitives`; confirm
        `baseline_commit` is `a5eb071`
  - [x] `cd ui && npm test` → expect **230 passed / 15 files**; `npm run lint`,
        `npm run format:check`, `npm run typecheck`, `npm run build` all exit 0
  - [x] Repo root: `uv run pytest -m "not integration"` → expect **1,753 passed / 1 skipped /
        45 deselected**. *If `test_list_decks_with_strategy_field` fails, it is the known
        `created_at`-tie flake — re-run before investigating.*
  - [x] `git status --porcelain -- src/companion/app/static/ plugin/` clean **after** a build, so a
        later drift is provably yours
  - [x] Record every number in the Dev Agent Record

- [x] **Task 1 — settle the four decisions before writing CSS** (AC 7, 8, 17, and Q1–Q6)
  - [x] Confirm Brad's answers to Q1–Q6 are in hand; if any is "not as proposed", re-read the ACs it
        touches before starting
  - [x] If Q3 is "as proposed": move `filled.ts` to its shared home and update **both** pinned
        assertions in `tests/shell.test.ts` (the exhaustive import list and the helper's path) in
        the same commit — the shell's suite must be green before any primitive is written
  - [x] Write one probe stylesheet exercising the chosen 17px spelling and the chosen tone-tint
        shape; run `npm run lint` on it; **delete it**. Measure before committing to a shape.

- [x] **Task 2 — Panel** (AC 1, 5, 10, 12, 13, 15, 16, 17)
  - [x] `src/components/Panel/{Panel.tsx, Panel.css, Panel.test.tsx}`; `git add` immediately
        (landmine 14)
  - [x] `<section>` + optional `<header>` with `<h2>` title, count, right-aligned badges; `level`
        and `live` props
  - [x] Rest `var(--shadow-rest)`, live `var(--shadow-raise)`, dot glow `var(--glow)`
  - [x] `overflow: hidden` on the section so the header's rule clips inside `--radius-lg` — comment
        that this is a panel, **not** a root, and therefore outside c2-6's clip ban
  - [x] `npm run lint` after **every** block

- [x] **Task 3 — Badge** (AC 2, 5, 8, 13, 14)
  - [x] Five tones, each from its own token; no colour literal, no colour function
  - [x] `--accent`, never `--accent-dim` (AC 14) — with the reason in the file
  - [x] `var(--tracking-label)`, not the mock's `0.04em`

- [x] **Task 4 — StatChip and Group header** (AC 3, 4, 5, 7, 12, 13, 15, 16)
  - [x] StatChip: micro label, the 17px value in its ruled spelling, optional delta tinted by sign;
        **no** `min-width`
  - [x] Group header: `<h2>` label + right-aligned count over a `1px` hairline rule, cited

- [x] **Task 5 — the guards** (AC 5, 11, 13)
  - [x] The label/micro companion guard, **in `tests/token-usage.test.ts` beside its family**
        (`findUnpairedNumericRole`), with its cases added to `tests/fixtures/css/token-usage-violation.css`
  - [x] Non-vacuity anchor first; prove firing **and** silent, on spellings the guard does not
        enumerate
  - [x] The presentation-only assertion for all four primitives, in the shape
        `tests/shell.test.ts:878-905` uses — exhaustive import lists, hooks by family, comments
        stripped so documentation does not read as code

- [x] **Task 6 — records** (AC 19, 20, 21)
  - [x] Repair every sentence in AC 20's inventory; judge and record the ones deliberately kept
  - [x] `ui/README.md`: the primitive conventions, the tone-tint mechanism, the new ban-table row,
        a rewritten *Not here yet*
  - [x] Add the visual-verification entry to `deferred-work.md`, homed to the first consuming story

- [x] **Task 7 — rebuild, mirror, prove** (AC 22, 23, 24)
  - [x] `npm run build`; `uv run python -m scripts.build_plugin`; **measure** whether either tree
        changed and record the answer either way
  - [x] Re-run all five frontend gates and the Python suite (expect **1,753**, unchanged)
  - [x] Scope proof: `git diff --stat` shows no `.py` outside the mirror, no `pyproject.toml`, no
        `uv.lock`, no `package.json`, no change to `AppShell.tsx`'s placeholder copy
  - [x] `git status --porcelain` clean

- [x] **Task 8 — probe the evasions before claiming done**
  - [x] For each new guard, plant the evasion, confirm it is caught, revert, paste the output
  - [x] **Verify the mutation landed before believing the verdict**, and **read what landed on
        disk** (c2-4's lesson; c2-6's probe 10 is the reason this task exists)
  - [x] Probe at least: `font: var(--type-label)` with no tracking; the same with no `uppercase`;
        an uncited `1px` in a new component stylesheet; `--accent-dim` beside `--surface-overlay` in
        one Badge block; a `count={0}` regression (`{count && …}`)
  - [x] **Ban the family, never enumerate members** — prove each guard with a spelling it does not
        list

### Review Findings

Adversarial review 2026-07-29 (Blind Hunter + Edge Case Hunter + Acceptance Auditor; 27 raw
findings, 18 after dedup — the top four were each found by two layers independently).

**All resolved same day: 4 rulings by Brad (each "as recommended"), 16 patches applied, 1
deferred.** The rulings, as shipped: Badge clamps a runtime-unknown tone to `neutral`
(`BADGE_TONES.includes`); the live dot requires `named`, not merely a header, and the
title-less live hole is declared in `Panel.tsx` and homed at c2-9; the `ReactNode` slots are
recorded per-prop (they are never accessible names) with Badge gating empty children through
`filled()` while GroupHeader/StatChip leave emptiness as caller error; the borrowed border
citation is ruled truthful and says so in `Badge.css`. The count pin (patch 12) caught its own
test's prose undercounting the fixture — 8 claimed, 9 measured — the same day it was written.
After patches: **suites 308 frontend (was 301) / 19 files**, five gates green, bundle + plugin
mirror re-measured **byte-identical** (`index-Dtvm20jX.js` unchanged).

- [x] [Review][Decision] **Badge's unknown-tone contract: the test header claims "unknown lands
      on neutral" but `badge-${tone}` interpolates whatever arrives** — only the *missing* prop
      defaults; a runtime-unknown string (server data in c4-10/c9) renders `badge-bogus` with no
      tone styles. Either clamp at runtime (`BADGE_TONES.includes(...)`) or repair the prose to
      say TS owns validity — two defensible answers, and which one is the decide-once ruling.
      [Badge.tsx:33-34, Badge.test.tsx:1-11]
- [x] [Review][Decision] **A live panel without a title has a weak-to-absent live signal** — no
      header: only `box-shadow` changes, which graphite/ink themes declare `none`, so `live`
      renders literally nothing; count-only/badges-only header: the dot mounts beside no title,
      which the code's own comment says "marks nothing" (and the aria-hidden dot is then the only
      visual signal). Require a title for `live`, render the signal elsewhere, or document the
      hole. [Panel.tsx:88-93, Panel.css]
- [x] [Review][Decision] **Content-slot typing and emptiness are asymmetric across the four
      primitives** — Q4 typed Panel's `title` as `string`, but GroupHeader `label` and StatChip
      `label`/`value` are `ReactNode` with no recorded reason, and empty nodes mount empty chrome
      (an empty `<h2>` heading, a bordered empty Badge pill, blank StatChip spans) with `filled()`
      one import away unused. Rule once: what do content slots accept, and does `filled()` gate
      them? [GroupHeader.tsx:27, StatChip.tsx:28-34, Badge.tsx:30]
- [x] [Review][Decision] **Badge's `1px` border citation is borrowed** — DESIGN.md's
      `components.badge` declares no border width at all; the file cites `components.panel.border`
      and "inherits that weight". Honest about the inheritance, but by the story's own
      truthful-citation standard (the one that dropped `min-width: 76px`) this wants an explicit
      ruling rather than silence. [Badge.css:69-71]
- [x] [Review][Patch] **StatChip ships no padding — the comment above the block claims
      `padding: var(--space-2) var(--space-3)` is present, but no `padding` is declared anywhere
      in the file** (label and value sit flush against the hairline border; no gate can see it —
      the exact AC 21 blind spot, with a false comment on top) [StatChip.css:17-32]
- [x] [Review][Patch] **AC 6's Panel matrix is axes-only — `overlay`+`live`, `overlay`×header
      states and `live`+count-only are never rendered in any test** [Panel.test.tsx]
- [x] [Review][Patch] **The presentation-only gate's `PRIMITIVES` list is hand-kept — a fifth
      component under `src/components/` silently escapes it** (derive the file list from
      `git ls-files` the way the stylesheet scan already does) [shell.test.ts:977-990]
- [x] [Review][Patch] **`filled.ts`'s type-only exemption leaves it the one module where an
      aliased hook (`import { useState as s }`) passes every guard** — pin its exact `react`
      import [shell.test.ts:1025-1027]
- [x] [Review][Patch] **The exhaustive-import-list regex misses `export … from` re-exports** — a
      re-export loads an unlisted module the "exhaustive" list never sees [shell.test.ts:1013-1021]
- [x] [Review][Patch] **The "has no min-width" StatChip test is vacuous** — it checks the inline
      `style` attribute, which a `min-width` in StatChip.css would never touch; assert the CSS
      source instead [StatChip.test.tsx]
- [x] [Review][Patch] **The uppercase half of `findRoleWithoutCompanions` is exact-string
      equality while the tracking half tolerates fallbacks** — `uppercase !important` or
      whitespace variance produces a false finding; no decorated-uppercase fixture case exists
      [token-usage.test.ts]
- [x] [Review][Patch] **The AC 13 fixture's total finding count is never pinned** — eight
      `toContain`s but no `toHaveLength`, against the house "counts per fixture file" standard
      [token-usage.test.ts]
- [x] [Review][Patch] **A renamed/missing `typography:` key in DESIGN.md frontmatter throws a
      bare `TypeError` at module scope instead of the promised loud anchor**
      [token-usage.test.ts:581-591]
- [x] [Review][Patch] **`sprint-status.yaml`'s machine-readable `last_updated` key still reads
      the 2026-07-28 CONTEXTED state — only the comment copy was bumped** [sprint-status.yaml:57]
- [x] [Review][Patch] **Badge.css's accent-tone contrast comment states a five-surfaces claim as
      settled with zero measurements behind it** — reword as unmeasured and home the measurement
      on the AC 21 manual checklist [Badge.css]
- [x] [Review][Patch] **Two undeclared guard limits, declare them:** (a) the derived uppercase
      rule forces a no-op `text-transform: uppercase` onto numeric micro content
      (`.stat-chip-delta`) — the first micro-role timestamp/price hits it; (b) the
      presentation-only suite catches `ref=` in JSX but not a `ref?:` prop declaration, and a
      props-spread defeats both the handler and ref shape checks [StatChip.css:81-86,
      shell.test.ts]
- [x] [Review][Patch] **The `{count && …}` lesson has no gate for future consumers** — the
      "single most likely defect" got per-component tests only; record that review owns the
      consumer half [ui/README.md]
- [x] [Review][Defer] **`signed()` renders raw `String(delta)` — a fractional delta shows
      `+0.30000000000000004`, a huge one `+1e+21`** [StatChip.tsx:45] — deferred: Q6 already
      homes delta formatting at the first consumer; this extends that entry to cover
      fractional/huge numbers

## Dev Notes

### Decide-once rulings this story sets (c2-8 … c2-10, c4, c5, c6, c7, c9 inherit)

1. **How a semantic tone tints a surface** (AC 8) — the answer c6-7, c9-1 and c9-2 reuse instead of
   each inventing one.
2. **How a size the token layer does not carry is expressed** (AC 7) — a role token plus a
   companion, never a `font-size`, never a new token.
3. **Panel and group-header semantics** (AC 15) — `<section>` named by its `<h2>` title; group
   headers are `<h2>`; a Panel with no title invents no name.
4. **Primitives are hook-free** (AC 5, Q4) — a component that needs `useId` has stopped being a
   presentation-only primitive, and that is a signal rather than an inconvenience.
5. **Where a shared component helper lives** (AC 17, Q3).
6. **The label/micro roles never travel without their companions** (AC 13) — the third member of the
   pairing family, after the numeric role and the tracking tokens.

### The five things this story inherits and must not break

- **The token layer is complete and closed.** 64 tokens, asserted by count *and* byte-for-byte
  against DESIGN.md. If a value you want has no token, it is either the wrong value, a geometry
  literal with a citation (AC 15), or a role token you have not thought of yet (AC 11). It is never
  a new token in this story.
- **The typography ban is total.** `font`, every `font-*` longhand, `line-height`, `letter-spacing`,
  `word-spacing` and `text-indent` accept only the role/family/tracking tokens (plus `0` and the
  CSS-wide keywords).
- **c2-6's AC 18 citation gate now runs over every component stylesheet.** It arrived one story ago
  and this is the first story it applies to. Every `\d+px` in your CSS needs `DESIGN.md` within 60
  characters of it, in a comment, in the same file.
- **The shell owns the window and the scroll.** A panel that scrolls its own content is fine; a
  second `100dvh` region is not. Nothing here is full-window and nothing here is `position: fixed`.
- **The gates are cheap.** `npm run lint` is ESLint **and** stylelint in one script. Run it after
  every block; do not batch a stylesheet and discover fifteen errors.

### The composition reference is a source of arrangement, not of values

`imports/claude-design/Planeswalker Companion.dc.html` and its `_ds/_ds_bundle.js` demonstrate all
four primitives in composition and are worth reading for **density and arrangement**. Every value in
them has been checked against DESIGN.md's own prose and the shipped gates, and the following are
**drift** — reproduce none of them:

| Mock | Why it is drift | What ships |
| --- | --- | --- |
| `rgba(95,212,160,0.12)` tone backgrounds, `rgba(...,0.35)` borders | colour function, banned | AC 12's mechanism |
| `fontSize: 17` beside `font: var(--type-numeric)` | `font-size` literal, banned | AC 11's spelling |
| `fontVariantNumeric: 'tabular-nums'` | right answer, wrong source | `var(--type-numeric-features)` |
| `padding: '10px 14px'` / `'12px 14px'` / `'2px 9px'` | off the spacing scale (UX-DR5) | `var(--space-*)` |
| `gap: 2` / `gap: 6` in StatChip | off the scale | `var(--space-1)` |
| `boxShadow: '0 12px 32px rgba(0,0,0,0.5)'` (Panel rest) | literal copy of `--shadow-rest` | `var(--shadow-rest)` |
| `boxShadow: '0 0 8px var(--accent-glow), 0 0 4px var(--accent)'` (live dot) | partly tokenised | `var(--glow)` |
| `letterSpacing: '0.04em'` (Badge) | badge type is `{typography.label}` → `0.1em` | `var(--tracking-label)` |
| `minWidth: 76` (StatChip) | not in DESIGN.md; would fail AC 15 uncitably | dropped |
| `borderRadius: 999` (live dot) | literal radius, banned | `var(--radius-pill)` |
| every value written as an inline `style={{…}}` | ESLint error | a `.css` file |

### A tension worth naming before review finds it

DESIGN.md gives the **neutral** Badge a `--surface-overlay` background. In the app header a badge
sits on `--surface-base`, which is **two** steps up the ramp, and UX-DR1 says a nested component
steps exactly one level. Both statements are DESIGN.md's. The resolution: the ramp rule governs
**layered surfaces** — a row inside a panel inside the canvas — and a badge is a chip on a line of
text, not a layer. Ship DESIGN.md's `components.badge` values and **say this in the stylesheet**, so
a later reviewer reading `surfaces.ts`'s `stepsExactlyOne()` finds a decision rather than a
violation. (`surfaces.ts`'s own header already declares that which component renders inside which is
review's half, not a gate's.)

### Previous story intelligence (c2-6, PR #23, Greptile 5/5 at round **3**)

- **The review theme, four stories running: the guards' own family coverage.** Round 1 found guards
  missing family members; round 2 found *the repairs themselves* stopping one member short. **This
  story's equivalent is already visible**: AC 13's new companion guard will be written against
  `--type-label` and `--type-micro`, and `--type-display` has a tracking token too. Write the rule
  as *"any role token that has a `--tracking-*` sibling requires it"*, derived from the token names,
  not from a list of two.
- **A declared blind spot is still a claim, and c2-6's had not been measured.** "Neither pass order
  is safe" was true; "this one fails on the rarer input" was never checked, and it was hiding a
  failure that blinded every guard in the file. If you declare a limit in this story, **measure
  it**.
- **A probe that passes is information, not a formality.** c2-6's probe 10 exposed that its own AC 18
  guard was satisfied by a comment four hundred characters away. Expect one of your probes to pass
  and treat it as a finding.
- **A green CI check is not a green review.** Greptile's check reported *pass* while its score was
  3/5. Read the score.
- **`filled()` cost two review rounds and a Greptile round to get right** — empty Fragment, empty
  `Set`, empty array, whitespace string, one-shot generator. Reuse it (AC 17).
- All of c2-4's, c2-5's and c2-6's open questions were answered "as proposed" before Task 0, and
  nothing surfaced mid-story — five stories running. Q1–Q6 below are written to be answerable in one
  pass for the same reason.

### Git intelligence

The last commits are c2-6 in the house shape: **implementation → review patches (message names the
theme) → PR round → merge → records**. Conventional Commits, scope `companion`. `feat/companion-c2`
is level with `origin` at `a5eb071`, working tree clean — **this story is not blocked**. Branch off
the umbrella now; the story PR targets the umbrella with a Greptile pass (the per-epic integration
PR gets none — standing rule).

### Source tree — what exists, what this story adds

```
ui/
  README.md                       UPDATE  primitive conventions (AC 19); tone-tint mechanism;
                                          ban-table row; repair 227/436/456-459/465 (AC 20)
  src/
    components/
      filled.ts                   MOVED?  per Q3 — from AppShell/, with both pinned assertions
      Panel/{Panel.tsx,.css,.test.tsx}         NEW
      Badge/{Badge.tsx,.css,.test.tsx}         NEW
      StatChip/{StatChip.tsx,.css,.test.tsx}   NEW
      GroupHeader/{GroupHeader.tsx,.css,.test.tsx}  NEW
      AppShell/AppShell.css       UPDATE  comment only — repair the 17px prediction (line 11)
      AppShell/AppShell.tsx       UNCHANGED — the badge slot stays empty (AC 24)
  tests/
    token-usage.test.ts           UPDATE  the label/micro companion guard (AC 13)
    fixtures/css/token-usage-violation.css  UPDATE  its cases
    shell.test.ts                 UPDATE  comment repair (line 815); the two `filled` pins if Q3
src/companion/app/static/         REGENERATED (probably byte-identical — measure)
plugin/…/static/                  REGENERATED
_bmad-output/implementation-artifacts/deferred-work.md  UPDATE (AC 20, AC 21)
```

Nothing else. No `.py` logic, no route, no store.

### Gotchas specific to this story

1. **`{count && <span>{count}</span>}` renders `0`.** The single most likely defect in this story,
   and it renders *something*, so nobody looks. Use `!= null`. Same for "does this header exist" —
   `title || count` is false for a zero-count-only header.
2. **`font-size` has no legal spelling. At all.** If you find yourself wanting one, the answer is a
   different role token (AC 11), not an exception.
3. **`color-mix()` is banned along with `rgba()`.** Measured. The tone tint is a shape decision
   (Q2), not a function call.
4. **Every `1px` needs a citation.** The gate is already live over `src/components/**/*.css`. One
   comment per literal per file, `DESIGN.md` within 60 characters of the value.
5. **`git add` before running the guards** (landmine 14). A guard written against an untracked
   stylesheet passes vacuously. Three stories running.
6. **The numeric role and its companion go in the SAME rule block.** A split pair is reported as a
   failure by design.
7. **Do not fill the header badge slot.** `AppShell.tsx:105-113` and `AppShell.test.tsx:113-123`
   both encode that c4-2 and c4-10 are the fillers; filling it here breaks the placeholder test and
   steals two stories' work.
8. **`overflow: hidden` on Panel is legal** — the c2-6 ban covers roots and `.app-shell-columns`
   only. Say so in the file so the next reader does not "fix" it.
9. **Component tests assert by ROLE.** `getByRole('region', { name: … })`,
   `getByRole('heading', { level: 2 })`. A class-name assertion proves nothing about the semantics
   these ACs are actually about.
10. **jsdom renders no styles.** Every colour, elevation and tint claim is CSS source or the manual
    checklist. Do not write a `getComputedStyle` assertion that passes for the wrong reason.
11. **Four new stylesheets means four new chances for the label/micro pairing to be wrong** — write
    the guard (Task 5) *before* the fourth component, so it catches the earlier three.

### Testing standards

- vitest, two projects. **Component tests are `.tsx` and live in `src/`** (the `dom` project);
  a `.test.tsx` under `tests/` is banned by `gate-geometry.test.ts`. Node-project gate and guard
  tests live in `ui/tests/`.
- Component assertions go through `@testing-library/react` **by role**, not by class name or test id.
- **Every new guard gets a proven pair** from one invocation, asserted by rule name and count where
  stylelint is involved, per fixture file (never in aggregate).
- **Non-vacuity anchor first** in any test that filters a list.
- Fixtures live in `tests/fixtures/`, are excluded from `npm run lint`, and are meant to stay broken.
- Python side: no new tests; re-run the suite to prove nothing moved.

### Architecture rules this story implements

- **UX-DR9–12** — the four primitives, their variants and their states.
- **UX-DR1** — the surface ramp, and the badge tension named above.
- **UX-DR3** — the numeric role never travels alone; its first real consumers.
- **UX-DR5** — every spacing value from the scale; the mock's one-offs are drift.
- **UX-DR6** — `--accent-dim` is never on `--surface-overlay` (AC 14).
- **UX-DR7** — nothing here borrows a card radius or a `mana-*` token; the primitives are chrome.
- **UX-DR41 / UX-DR44** — contrast floors, and the heading/region structure.
- **NFR-07** — the frontend gates are the enforcement mechanism.
- **FR-20** — the visual identity; this story ships its component vocabulary.

### References

- [epics-companion-app.md#Story-2.7](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  six AC blocks (lines 1404-1435)
- [epics-companion-app.md#UX-DR9-12](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  primitives (lines 380-393); UX-DR44 (line 590); UX-DR6 (line 355)
- [DESIGN.md#Containers--chrome](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md)
  — Panel, Badge, StatChip in prose (lines 352-354), Group header (line 368), the `components.*`
  frontmatter (lines 120-135, 166-169), the contrast table (lines 279-296)
- [EXPERIENCE.md](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md)
  — semantic structure, line 152
- [_ds_bundle.js](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/imports/claude-design/_ds/_ds_bundle.js)
  — the mock's Badge, Panel and StatChip implementations, read for arrangement only
- [c2-6 story record](_bmad-output/implementation-artifacts/c2-6-the-two-column-application-shell.md)
  — the five conventions, `filled()`'s history, the probe discipline
- [ui/README.md#The-token-layer](ui/README.md) — the ban table (194-213), the geometry non-ban
  (215-233), *Components* (367-437), *Not here yet* (447-470)
- [ui/tests/token-usage.test.ts](ui/tests/token-usage.test.ts) — `findUnpairedNumericRole`
  (327-394), the fixture pairing tests (512-614)
- [ui/tests/shell.test.ts](ui/tests/shell.test.ts) — c2-6's AC 18 citation gate (811-852), the
  presentation-only shape to copy (854-930)
- [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md) — the numeric-role
  cascade blind spot naming this story (1180-1192)

## Open questions for Brad — answer before `dev-story`

Each carries a recommendation; "as proposed" on all six is a complete answer. Q1–Q4 are
**decide-once rulings the rest of the component work inherits**, which is why they are questions
rather than choices made in the implementation.

**Q1 — how is StatChip's 17px numeric value written, given `font-size` is banned?** *Recommendation:*
**`font: var(--type-heading)` plus `font-variant-numeric: var(--type-numeric-features)`** in the same
block. `--type-heading` is `500 17px/1.3` and `--type-numeric` is `500 13px/1.4` — same weight, the
size DESIGN.md asks for, and the companion restores the tabular digits the heading role does not
carry. Measured legal (both declarations, one probe, exit 0). The alternatives are worse in
different ways: a `font-size: 17px` literal needs a stylelint exception in the one gate family that
has none; a new `--type-stat-value` token breaks `declaredTokens.size === 64` **and** DESIGN.md's
byte-for-byte name contract, which is a UX-artefact change, not a frontend one. Consequence to
accept: the value's line-height becomes 1.3 rather than 1.4 — immaterial on a single-line number,
and the alternative is unavailable rather than merely worse.

**Q2 — how does a Badge tone tint its background, with `rgba()` and `color-mix()` both banned and no
translucent token for positive/negative/caution?** *Recommendation:* **a pseudo-element wash** — the
badge is `position: relative`, and `::before` covers it (`inset: 0`, the tone's own token as
`background`, a low `opacity`, the pill radius), with the text above it. It satisfies the epic's AC
literally ("tints background… from its own semantic token"), introduces no colour literal, needs no
gate change, and works under all four alternate themes because the colour is still the token. It is
also exactly what `rgba(95,212,160,0.12)` *means*, expressed without a colour function. The two
alternatives, both declined: **(b) border and text only**, with `--surface-overlay` behind every
tone — simplest, but it fails the AC's own words and flattens the five tones to one; **(c) narrow the
`color-mix()` ban** to admit calls whose arguments are all `var(--…)` — arguably the cleanest
long-run answer and how most design systems do it, but it changes a shipped gate three stories after
it landed and needs its own guard proving a literal-argument `color-mix` still fails. If you prefer
(c), say so and the story grows a gate-change AC rather than smuggling one in. The border stays the
tone token at full strength either way — the mock's `0.35` alpha has no legal spelling and a hairline
pill border at full strength is what "tints border from its own semantic token" reads as.

**Q3 — where does the shared `filled()` helper live?** *Recommendation:* **move it to
`src/components/filled.ts`** and update the two assertions that pin it
(`tests/shell.test.ts:889`'s exhaustive import list, `:910`'s path). Panel needs the identical logic
for its header slots, and the three alternatives are all worse: re-deriving it in Panel is the
reinvention the convention exists to prevent; importing `../AppShell/filled` makes every primitive
depend on the shell's directory; and a `src/lib/` directory is a new top-level source folder needing
a `tsconfig` include for one file. `src/components/` is where component-shared code belongs and the
move is two mechanical edits in the same commit.

**Q4 — heading and region semantics for Panel and Group header.** *Recommendation:* Panel renders
`<section aria-label={title}>` with the title as an `<h2>`; an untitled Panel is a plain `<section>`
with no name. Group header renders its label as an `<h2>` with the count beside it. `aria-label`
rather than `aria-labelledby` is deliberate: `aria-labelledby` needs a generated id, `useId` is a
hook, and **primitives are hook-free** (AC 5) — the day one of them needs a hook it is no longer a
presentation-only primitive, and that is a signal worth keeping. The consequence to accept is that
`title` is typed `string`, not `ReactNode`; DESIGN.md already says panel titles are short label
strings and that counts go *beside* the label rather than inside it, so nothing is lost. UX-DR44's
literal reading — panel titles **and** type-group headers both `h2` — means a deck-list panel's
title and its "CREATURES" divider are siblings at the same level; that is the spec's choice, taken
as written, and c4-7 may home a correction if it reads wrong in a real screen reader.

**Q5 — is the label/micro companion rule a guard or a review item?** *Recommendation:* **a guard**
(AC 13), in `tests/token-usage.test.ts` beside `findUnpairedNumericRole`, because it is the same
family and the same failure shape: the `font` shorthand cannot carry `letter-spacing` or
`text-transform`, so a bare label role renders 11px lowercase text with default tracking — legible,
plausible, wrong, and invisible in review because it looks like text. Written as a **derived** rule:
any `--type-*` role with a `--tracking-*` sibling requires that sibling in the same block; the
uppercase half applies to `--type-label` and `--type-micro`, which are the two DESIGN.md declares
uppercase. Four new stylesheets in one story is the moment to install it.

**Q6 — StatChip's `delta` contract.** *Recommendation:* `delta?: number`. The chip formats it with
an explicit sign and tints by **numeric sign**, not by a string prefix: `> 0` positive, `< 0`
negative, **`0` neutral** (`--text-tertiary`, no sign — a zero delta is not an improvement), and a
non-finite value renders nothing rather than "NaN". The mock's `String(delta).startsWith('-')` is
wrong for `-0`, for a Unicode minus, and for any pre-formatted string. A formatted delta ("+$1.20")
is a real future need and is deferred to its first consumer, which will add a sibling prop in the
open rather than overloading this one.

## Dev Agent Record

### Open questions — answered

All six answered **"as proposed"** by Brad at contexting time (2026-07-28), before Task 0 — the
sixth story running where nothing was left to surface mid-implementation. The rulings, restated so
the implementation does not have to re-read the recommendations:

- **Q1 — the 17px value** is `font: var(--type-heading)` plus
  `font-variant-numeric: var(--type-numeric-features)` in the same block. No `font-size`, no new
  token, no stylelint exception. Line-height becomes 1.3; accepted.
- **Q2 — the tone tint** is a **pseudo-element wash**: the badge is `position: relative`, a
  `::before` covers it (`inset: 0`, the tone's own token as `background`, low `opacity`, the pill
  radius) behind the text; the border is the tone token at **full strength**. No colour literal, no
  colour function, no gate change. The `color-mix()` ban stays as it is.
- **Q3 — `filled()` moves to `src/components/filled.ts`**, with both pinned assertions in
  `tests/shell.test.ts` (the exhaustive import list at :889, the helper path at :910) updated in the
  same commit. The shell's suite is green before any primitive is written.
- **Q4 — semantics:** `<section aria-label={title}>` with the title as an `<h2>`; an untitled Panel
  is a plain unnamed `<section>`; Group header is an `<h2>` with its count. **Primitives are
  hook-free** — no `useId`, so `title` is typed `string`.
- **Q5 — the label/micro companion rule is a GUARD**, in `tests/token-usage.test.ts` beside
  `findUnpairedNumericRole`, written as a **derived** family rule (any `--type-*` role with a
  `--tracking-*` sibling requires it) rather than a list of two — and the uppercase half applies to
  `--type-label` and `--type-micro`. Both halves gate; neither is left to review.
- **Q6 — `delta?: number`**, tinted by numeric sign: `> 0` positive, `< 0` negative, **`0` neutral**
  (`--text-tertiary`, rendered "0", no sign), non-finite renders nothing. A formatted delta is
  deferred to its first consumer.

### Agent Model Used

claude-opus-5 (Claude Code, `/bmad-dev-story`)

### Debug Log References

**Task 0 — baseline, measured at `a5eb071` (2026-07-29).** Frontend **230 passed / 15 files**.
`npm run lint`, `format:check`, `typecheck`, `build` all exit 0. Python: the first run hit the
documented `created_at`-tie flake (`test_list_decks_with_strategy_field`, 1 failed / 1752
passed); the re-run the story prescribes was clean at **1753 passed / 1 skipped / 45
deselected**. `git status --porcelain -- src/companion/app/static/ plugin/` clean after a build.

**Task 1 — the three landmines re-measured on a probe stylesheet under the real config, then
the probe deleted.** All three confirmed ERRORS: `font-size: 17px`
(`declaration-property-value-allowed-list`), `color-mix(in srgb, var(--positive) 12%,
transparent)` (`function-disallowed-list`), `padding: 2px 9px` (allowed-list). Both ruled
spellings confirmed CLEAN in the same probe: `font: var(--type-heading)` +
`font-variant-numeric: var(--type-numeric-features)`, and the `::before` wash built from
`background: var(--positive)` + `opacity`.

**Two things the story predicted that measured differently — both corrected rather than worked
around:**

1. **`allowConstantExport` does not admit an array.** `ui/README.md` (from c2-6) said a
   component module "may export the component, types and constants". Measured: `export const
   BADGE_TONES = [...] as const` beside the component is a
   `react-refresh/only-export-components` ERROR. `BADGE_TONES` moved to
   `src/components/Badge/tones.ts`, taking the route `filled.ts` already established, and the
   README claim is **corrected in place** rather than deleted — the next author would otherwise
   measure it again.
2. **A gate fired that the story did not anticipate.** `tests/package-contract.test.ts` pins the
   exhaustive list of `yaml` importers under `tests/`, and AC 13's guard added a second one. The
   list was **updated with its reason**, not weakened: the invariant it actually protects —
   `yaml` never imported from `src/` — is untouched and still asserted.

**Task 7 — the byte-identical bundle was MEASURED, not assumed.** `npm run build` then
`git status --porcelain -- src/companion/app/static/ plugin/` gave **both clean**, and the asset
hashes are unchanged from the Task 0 build (`index-Dtvm20jX.js`, `index-yCpmQea7.css`). The
story's prediction held exactly: nothing imports the four primitives, so Vite never puts them
in the module graph. The plugin mirror was regenerated (`uv run python -m scripts.build_plugin`)
and is byte-identical too.

**Task 8 — ten evasion probes. Nine caught, ONE PASSED, and the one that passed is the story's
most valuable finding.** Every mutation was verified on disk before the verdict was believed
(c2-4's lesson), and every one was reverted.

| # | Planted | Verdict |
| --- | --- | --- |
| 1 | `.panel-title` loses `letter-spacing: var(--tracking-label)` | CAUGHT — `findRoleWithoutCompanions` |
| 2 | `.stat-chip-label` loses `text-transform: uppercase` (the **micro** role, a different file) | CAUGHT |
| 3 | the `1px` citation deleted from `GroupHeader.css` — a file the gate had never seen | CAUGHT (and the file still held two *other* `DESIGN.md` mentions, re-proving c2-6's probe-10 repair) |
| 4 | `--accent-dim` beside `--surface-overlay` in `.badge-neutral::before` | CAUGHT — `findAccentDimOnOverlay` |
| 5 | `GroupHeader`'s `Number.isFinite(count)` becomes `Boolean(count)` | CAUGHT — the `count={0}` test |
| 6 | `import { useState as zz } from 'react'` in StatChip — an **alias no name-keyed regex matches** | CAUGHT by the type-only react rule |
| 7 | `import '../../store/subscribe'` in Panel — a **bare side-effect import, no `from` clause** | CAUGHT by the exhaustive import list |
| 8 | an `onDismiss?: () => void` prop on Badge — a name **no blocklist would enumerate** | CAUGHT by the `on[A-Z]` shape rule |
| 9 | Panel's `filled(badges)` becomes `Boolean(badges)` | CAUGHT — the `<></>` / `[]` / `' '` test |
| 10 | `--accent-dim` on `.badge-accent` with **no `--surface-overlay` in the same block** | **PASSED — every gate green** |

**Probe 10 is what the composition reference actually ships** (its accent badge borders with
`--accent-dim`), so it is the single most likely way the drift returns. `.badge-accent` names no
surface, so the block-local guard never looked at it — while `.badge-neutral::before` two rules
away paints `--surface-overlay` under badges of **every** tone. Same file, same component, same
2.70:1 failure, and AC 14's actual claim ("do not write the token in this component at all") had
**nothing enforcing it**.

**The repair: `findAccentDimInOverlayFile`** — the same rule one scope wider, same-FILE rather
than same-block, derived rather than aimed at Badge: *a stylesheet that references
`--surface-overlay` anywhere has declared that its component paints on the overlay surface, so
`--accent-dim` anywhere in that file is a failure waiting for the two rules to meet on one
element.* This is exactly the widening c2-6's review made to the citation gate (one file to every
component stylesheet), one axis over. An outright ban on `--accent-dim` in components was
**declined**: UX-DR6's measured claim is about `--surface-overlay` specifically, and a ban
resting on an unmeasured number is the kind a later story switches off. Proven with a dedicated
cross-block fixture (`tests/fixtures/css/accent-dim-cross-block.css`), with the **block-local
guard asserted SILENT on the same input** so the widening is not passing because the old guard
caught it; probe 10 was then re-run and **CAUGHT**. The remaining cross-FILE limit (a Badge
inside a `level="overlay"` Panel) is declared and stays review's.

**Suite stability.** One run of `npm test` reported `296 passed (301)` with "1 error" immediately
after `prettier --write` rewrote `tests/token-usage.test.ts` in the same shell chain. Re-run
three consecutive times: **301/301 every time**. Recorded rather than hidden; it is a
write-then-read race in that one command, not a test defect.

### Completion Notes List

**Suites: frontend 230 to 301 (19 files); Python 1,753 to 1,753 (unchanged, re-run not assumed).**
Five frontend gates green. Bundle and plugin mirror regenerated and **measured byte-identical**.

**The four primitives.** `Panel` (default/overlay level, rest/live state, optional header
carrying title + count + right-aligned badges), `Badge` (five tones), `StatChip` (micro label,
17px numeric value, sign-tinted delta), `GroupHeader` (`h2` label + right-aligned count over a
hairline rule). All four hold no state, call no hook, import no store, take no handler and
expose no ref — asserted by `tests/shell.test.ts` over an exhaustive import list per module.

**The six decide-once rulings, as shipped.**

1. **Tone tint = a pseudo-element wash** (AC 8, Q2). `::before` at `inset: 0` filled with the
   tone's own token, `z-index: -1` behind the text, `isolation: isolate` confining that negative
   layer. `inset: 0` resolves against the PADDING box, which is what leaves the **border at full
   strength** — the mock's `0.35` alpha has no legal spelling. **The `color-mix()` ban stands
   exactly as it shipped**; this story relaxed no gate.
2. **A size the token layer does not carry = a role token plus its companion** (AC 7, Q1).
   `font: var(--type-heading)` (which *is* `500 17px/1.3`) + `font-variant-numeric:
   var(--type-numeric-features)`. No `font-size`, no new token, no stylelint exception. The
   line-height becomes 1.3; accepted and recorded.
3. **Panel and group-header semantics** (AC 15, Q4). `<section aria-label={title}>` with the
   title as `<h2>`; an untitled Panel is a plain **unnamed** `<section>` and invents no name;
   `GroupHeader` is an `<h2>` with its count **beside** the label.
4. **Primitives are hook-free** (AC 5, Q4) — `useId` included, which is why the region is named
   by `aria-label` and `title` is typed `string`.
5. **`filled()` lives at `src/components/filled.ts`** (AC 17, Q3), moved with **both** pinned
   assertions updated in the same commit; the shell's suite was green before any primitive was
   written.
6. **The label/micro roles never travel without their companions** (AC 13, Q5) — a **guard**,
   and a **derived** one on both halves: the tracking requirement comes from the `--tracking-*`
   TOKEN NAMES, the uppercase requirement from DESIGN.md's own `textTransform:` keys. Nobody
   typed "label and micro", and the rule therefore also covers `--type-display`, which nothing
   in this story uses — asserted explicitly, because that is the member a list of two would have
   missed.

**AC 16's falsy-value family, closed with `Number.isFinite`** in both `Panel` and `GroupHeader`:
`count={0}` renders "0", a header carrying only a zero count still renders, and a `NaN` renders
nothing rather than the text "NaN". `StatChip`'s delta uses `Math.sign` so `-0` lands on
neutral, where a string prefix, a `< 0` test and a `delta ? … : …` each get it wrong in a
different direction.

**AC 20's forward-dated inventory — all repaired or judged, in this commit.**
**Repaired (measured wrong):** `ui/README.md:227`, `ui/tests/shell.test.ts:815` and
`AppShell.css:11` each predicted the 17px StatChip value would be a **geometry literal**. It is
not — the value is spent through `font-size`, which IS gated — and all three now carry the
boundary that mistake found: *a geometry literal is a value with no token family to point at; a
type size has one, and the answer there is a different role token.*
**Repaired (stale):** `README.md:436` (tense), `:456-459` (*Not here yet* rewritten — the
primitives have landed, the header badge slot is still c4-2/c4-10's), `:465` ("Nothing applies
the numeric role yet" — three components now do), `shell.test.ts:1115` (c2-7 was named the
likely first fractional literal; it shipped none, so the invented member stays invented),
`shell.test.ts:585`/`:1130` (the `content: "16px"` illustration no longer attributes a tooltip
to a story that shipped without one), `deferred-work.md:1190` (the numeric-role blind spot now
has real consumers; severity raised Low to Low-Med).
**Judged and KEPT:** `AppShell.css:87` (c2-7 fills the header — still forward-dated and still
true), `src/index.css:49`, `tests/fixtures/css/clean.css:112`, `tests/fixtures/tsx/clean.tsx:4`
and `shell.test.ts:751` — all four say "every component from c2-7 onwards", which describes a
purpose rather than a future state and remains true now that c2-7 has landed.

**AC 21 — the visual half is NOT dev-verified, and the record says so plainly.** The primitives
have **no on-screen consumer** in this story (AC 24 keeps the header badge slot empty), and jsdom
applies no stylesheet, so no `getComputedStyle` assertion was written. Homed in
`deferred-work.md` at each primitive's first consuming story — `Panel` at c2-9, `GroupHeader` at
c4-7, `Badge` at c4-2/c4-10 — and flagged **Medium**, because the pseudo-element wash's stacking
behaviour is the one mechanism in the story with no static proof available and its failure mode
is a **solid blank pill with invisible text**, which reads as a content bug rather than a CSS
one. That is the first thing to check on a real screen.

**AC 18 — no `transition` and no `animation` in any of the four stylesheets**, stated in
`Panel.css` beside the `live` state: animating the change into it is c7-5's, together with the
reduced-motion fallback it must register in `tokens.css`.

**Scope (AC 23, AC 24).** No dependency added, runtime or dev. **No token added** —
`declaredTokens.size === 64` and `tests/tokens.test.ts` untouched. No `.py`, no route, no store,
no fetch, no `pyproject.toml`, no `uv.lock`, no `package.json`. `AppShell.tsx` changed by
**three comment lines and one import path only** — its placeholder copy is verified unchanged
and the header badge slot still names c4-2 and c4-10 as its fillers.

### File List

**New — the four primitives**

- `ui/src/components/Panel/{Panel.tsx, Panel.css, Panel.test.tsx}`
- `ui/src/components/Badge/{Badge.tsx, Badge.css, Badge.test.tsx, tones.ts}`
- `ui/src/components/StatChip/{StatChip.tsx, StatChip.css, StatChip.test.tsx}`
- `ui/src/components/GroupHeader/{GroupHeader.tsx, GroupHeader.css, GroupHeader.test.tsx}`

**New — fixture**

- `ui/tests/fixtures/css/accent-dim-cross-block.css`

**Moved**

- `ui/src/components/AppShell/filled.ts` to `ui/src/components/filled.ts` (Q3)

**Modified**

- `ui/src/components/AppShell/AppShell.tsx` — import path + comment only
- `ui/src/components/AppShell/AppShell.css` — comment only (AC 20's 17px repair)
- `ui/tests/shell.test.ts` — both `filled` pins; the four-primitive presentation-only suite;
  AC 20 comment repairs
- `ui/tests/token-usage.test.ts` — `findRoleWithoutCompanions` (AC 13) and
  `findAccentDimInOverlayFile` (AC 14, from probe 10), with their proven pairs
- `ui/tests/fixtures/css/token-usage-violation.css` — AC 13's seven cases
- `ui/tests/package-contract.test.ts` — the `yaml` importer list, with its reason
- `ui/README.md` — the primitive conventions, the tone-tint mechanism, the size ruling, the
  `--accent-dim` rule, the new ban-table row, the `allowConstantExport` correction, the
  geometry-literal correction, *Not here yet*
- `_bmad-output/implementation-artifacts/deferred-work.md` — AC 21's visual entry; the
  numeric-role blind spot updated; the second DESIGN.md path reader
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

**Regenerated and MEASURED byte-identical** — `src/companion/app/static/`, `plugin/`

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-07-29 | 1.1 | **CODE REVIEW → done** — three-layer bmad-code-review (27 raw findings, 18 after dedup): 4 rulings, 16 patches applied, 1 deferred, 0 dismissed. **Headline: StatChip shipped no padding at all** while the comment above the block claimed `var(--space-2) var(--space-3)` was present — a shipped visual defect invisible to every gate (lints clean, jsdom blind, no consumer: the exact AC 21 gap), found independently by two layers. Rulings: unknown Badge tone clamps to neutral; the live dot requires a title; ReactNode slots recorded + Badge gates empty children via `filled()`; the borrowed border citation is truthful. Guard hardening in the house idiom: PRIMITIVES list now git-derived so a fifth component cannot escape; `filled.ts`'s react import pinned exactly (the one aliased-hook hole); `export … from` re-exports now read as imports; ref banned in BOTH positions plus a spread ban; the AC 13 uppercase half given the tracking half's tolerance; the fixture total pinned — and the pin immediately found the prose undercounting 8 for a measured 9. The vacuous min-width DOM test moved to where CSS source is actually read. Two contrast claims rewritten as unmeasured and homed on the AC 21 checklist; the consumer half of `{count && …}` recorded as review's. Suites 308 frontend / five gates green; bundle + mirror re-measured byte-identical. | Claude (Reviewer) |
| 2026-07-29 | 1.0 | **IMPLEMENTED off `a5eb071`** — the first component *library*: Panel, Badge, StatChip, GroupHeader, plus the two guards AC 13 and AC 5 asked for. Suites **301 frontend** (was 230) / **1,753 Python** (unchanged, re-run not assumed); five gates green; bundle + plugin mirror **measured** byte-identical, which is the prediction the story made and Task 7 confirmed. All six decide-once rulings shipped as ruled — the tone tint is a pseudo-element wash, so **the `color-mix()` ban stands unchanged and no gate was relaxed**. **Ten evasion probes: nine caught, one PASSED** — `--accent-dim` on `.badge-accent` with no `--surface-overlay` in the *same block*, which is exactly what the composition reference ships and had nothing enforcing AC 14. Repaired by widening `findAccentDimOnOverlay` from same-block to **same-file** (derived, with the block-local guard asserted silent on the same input so the widening is not passing for the old guard's reason), then re-probed and caught. Two story predictions measured wrong and corrected in place rather than worked around: `allowConstantExport` does **not** admit an array export (so `BADGE_TONES` moved to its own module), and c2-6's README claim that it did is corrected; and the 17px StatChip value was predicted in three places to be a *geometry literal* — it is not, since `font-size` is itself gated, and all three now carry the boundary that mistake found. One unanticipated gate (the `yaml` importer pin) fired correctly and was updated with its reason, never weakened. AC 21 split as the fourth story to do so: the primitives have **no on-screen consumer**, so appearance is homed at c2-9 / c4-7 / c4-2 / c4-10 and flagged Medium — the wash's stacking is the one mechanism with no static proof and its failure mode is a solid blank pill. | Amelia (Dev) |
| 2026-07-28 | 0.2 | **All six open questions answered "as proposed"** — the sixth story running where nothing was left to surface mid-implementation. The two that mattered: the 17px StatChip value is a role token plus a companion (`--type-heading` + `--type-numeric-features`), and the Badge tone tint is a **pseudo-element wash** of the tone's own token, which means **the `color-mix()` ban stands unchanged** — the story ships no gate relaxation. Also ruled: `filled()` moves to `src/components/`, primitives stay hook-free (so `title` is a `string` and the region is named by `aria-label`), the label/micro companion rule is a derived guard rather than a review item, and `delta` is a number tinted by `Math.sign` with zero neutral. Recorded in the Dev Agent Record. | Bob (SM) |
| 2026-07-28 | 0.1 | Story contexted from the epic + DESIGN.md + EXPERIENCE.md + the composition reference and its design-system bundle. **Fifteen landmines measured at `a5eb071`**, four of them on a probe stylesheet run under the real stylelint config: `font-size: 17px` is a lint error (and the mock's StatChip is built on it), `color-mix()` is banned alongside `rgba()` (and the mock's five Badge tones are rgba tints), `padding: 2px 9px` is a lint error (and four of the mock's paddings are off-scale), and `border: 1px solid var(--border-hairline)` lints clean but inherits c2-6's DESIGN.md-citation gate, which this is the first story to meet. Also measured: the mock's `minWidth: 76` and `letterSpacing: 0.04em` have nothing in DESIGN.md to cite, so a citation for them would be unsatisfiable by construction. 24 ACs, 18 beyond the epic's six blocks; six open questions homed with recommendations, four of them decide-once rulings the rest of the component work inherits. AC 21 splits the visual half off explicitly — the primitives have **no on-screen consumer** in this story, so appearance is verified at the first consuming story rather than faked with a `getComputedStyle` assertion (the fourth story to split an AC this way). Not blocked — c2-6 is merged at `a117568`. | Bob (SM) |
