---
baseline_commit: 26a9fdf
epic: c2
story: c2-4
work_branch: feat/companion-c2
story_branch: feat/companion-c2-4-voltglass-tokens
---

# Story C2.4: The Voltglass token layer

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer building any surface,
I want every colour, type role, radius, space, motion and elevation value available as a named token,
so that the identity is enforced by construction and a hard-coded literal is a visible defect.

**What this story really is.** It is the *second* gate story of the epic, and its shape is the same
as c2-1's and c2-3's: a small artefact (two or three CSS files) whose entire value is the machinery
that makes deviation impossible. Ten stories (c2-5 … c2-10, then all of c4, c6, c7) write CSS on top
of this layer, and every one of them is a chance to type `#8b93ff`, `18px` or `box-shadow: 0 12px
32px rgba(0,0,0,.5)` by hand. Those three literals are exactly what silently breaks the four
alternate themes and inverts the elevation hierarchy under the shadowless ones.

So the deliverable is **tokens plus the lint rules that make the tokens the only way to write CSS**,
and — per the standing non-vacuity agreement promoted at the C1 retro — **every new rule is proven
firing and not firing from the same invocation**. c2-3's review found that *every* regex/list guard
it shipped had an evasion its own proofs never probed. This story adds four families of value
guards; assume the same, and probe the evasions listed in Gotchas before shipping.

**Six things were measured on this machine at the baseline commit (`26a9fdf` — stylelint 17.14.1,
stylelint-config-standard 40.0.0, prettier 3.9.x, node 24.15.0 local / 20 in CI). Do not
rediscover them:**

1. **DESIGN.md's `rgba()` values cannot be pasted in verbatim — `npm run lint` goes red.**
   `stylelint-config-standard` sets `color-function-alias-notation`, `color-function-notation:
   'modern'` and `alpha-value-notation: 'percentage'`. Measured on a candidate token file carrying
   DESIGN.md's five `rgba(...)` values: **15 errors across 5 declarations** — `Expected "rgba" to be
   "rgb"`, `Expected modern color-function notation`, `Expected "0.75" to be "75%"`. The same colour
   in the repo's own canonical notation is `rgb(8 9 18 / 75%)`. Q2 rules on which side gives way.

2. **Prettier lowercases hex colours.** DESIGN.md frontmatter is uppercase (`#0D0F1A`); measured,
   `prettier` rewrites it to `#0d0f1a`, and `format:check` is a CI gate. So a token-fidelity test
   that string-compares CSS against DESIGN.md **fails on case** unless it normalises. Combined with
   (1): the fidelity test must compare *normalised colour values*, never raw substrings.

3. **`no-unknown-custom-properties` is file-scoped and therefore unusable here.** Measured: a
   component stylesheet using `var(--shadow-rest)`, `var(--radius-lg)` and `var(--text-primary)`
   reports **"Unknown custom property"** for all three, because the tokens are declared in a
   different file and the rule has no cross-file resolution. Do not enable it. (Recorded because it
   is the obvious-looking rule for "you referenced a token that doesn't exist" and it does not work.)

4. **`declaration-property-value-allowed-list` does exactly what this story needs — with a regex
   property key.** Measured, passing and failing halves from one invocation:
   `box-shadow: var(--shadow-rest)` ✓, `box-shadow: var(--shadow-rest), var(--glow)` ✓,
   `box-shadow: 0 12px 32px rgb(0 0 0 / 50%)` ✗, `border-radius: 16px` ✗,
   `padding: var(--space-2) var(--space-3)` ✓, `padding: 18px` ✗, `margin: 14px 9px` ✗, `gap: 7px` ✗.

5. **…and the longhand is the evasion its obvious form misses.** With plain string keys
   (`padding`, `margin`, `gap`, `border-radius`), `padding-left: 18px`, `margin-top: 9px`,
   `column-gap: 7px` and `border-bottom-right-radius: 10px` all pass **silently**. With regex
   property keys (`/^(padding|margin)(-(top|right|bottom|left|block|inline)(-(start|end))?)?$/`,
   `/^(gap|row-gap|column-gap)$/`, `/^border(-(top|bottom)-(left|right))?-radius$/`) all four are
   caught and the clean half stays silent. **Ship the regex keys.** This is the c2-3 review theme
   arriving one story early.

6. **The existing clean CSS fixture violates the rule this story adds.**
   `ui/tests/fixtures/css/clean.css` declares `padding: 4px`, and
   `tests/lint-gates.test.ts` asserts `expect(result.results[0].warnings).toEqual([])` on it —
   an *unfiltered* assertion. Adding the spacing rule turns that existing green test red. The fix is
   to tokenise the fixture (`var(--space-1)`), **not** to loosen the rule or filter the assertion:
   the fixture's job is to be the file that satisfies every gate.

**What this story does not do.** No components (c2-6 builds the shell, c2-7 the primitives), no
font files (c2-5 self-hosts Space Grotesk; this story defines the family token the `@font-face` will
fill), no state panel or copy (c2-9), no layout (c2-6), no Python, no route, no runtime dependency.
It changes `ui/src/index.css` and `ui/src/App.css` only far enough that the placeholder shell obeys
its own new rules — the shell itself stays a placeholder.

## Acceptance Criteria

Epic-derived ACs are marked **[epic]**. The rest are requirements the epic's seven blocks imply but
do not state; each says why it exists. Nothing here is optional — an AC the epic did not write down
is still an AC (standing agreement: a story must leave the system working end to end).

### The token layer

**AC 1 [epic].** **Given** the token stylesheet, **when** its custom properties are compared to
`DESIGN.md` frontmatter, **then** every token name matches the mapping ruled in Q1 with no
free-hand renaming, **and** it defines exactly: **26 colours** (4-step surface ramp
`well → base → panel → overlay`, `scrim`, 2 borders, 4 text tiers, 4 accent tokens, `focus-ring`,
3 semantic, 7 WUBRG data colours), **7 typography roles**, **4 radii plus the card radius**, the
**7-step spacing scale plus gutter and panel-gap**, **4 motion durations**, **3 easings**, the
**focus ring** (colour, width, offset), and **3 elevation tokens**. The full inventory with values
is in Dev Notes → *The token inventory*; it is the contract, not a summary.

**AC 2 [epic].** **Given** the MVP ships Voltglass only as `:root`, **when** the token layer is
authored, **then** it is structured so an alternate `[data-theme="…"]` block can be added later
**without touching component code** — i.e. the selector is `:root, [data-theme="voltglass"]`, every
token is declared in that one block, and no component stylesheet ever *declares* a token, only
consumes one.

**AC 3.** **Given** the type roles, **when** they are authored, **then** `--type-numeric` ships
**with** its paired `font-variant-numeric` token (UX-DR3: the `font` shorthand cannot carry
`font-variant-numeric`), and the family token `--font-sans` resolves to
`'Space Grotesk', system-ui, sans-serif` **now**, so c2-5's `@font-face` makes the family real
without touching a role. *Why: c2-5's AC ("a lint rule or unit test fails on the numeric role being
applied alone") needs both tokens to already exist to point at.*

### The literal bans

**AC 4 [epic].** **Given** any component stylesheet in `ui/`, **when** stylelint inspects it,
**then** a hard-coded hex or `rgb()`/`rgba()`/`hsl()`/`hsla()` literal **fails**, **and** a
hard-coded `box-shadow` or `border-radius` literal **fails** — because a literal *rest* shadow
inverts the hierarchy under shadowless themes, where `shadow-raise` is the live state.

**AC 5 [epic].** **Given** a spacing value anywhere in the UI, **when** it is inspected, **then** it
comes from the 4/8/12/16/24/32/48 scale — the imported mock's 18/14/9/7px values are drift and are
not reproduced. Enforced by lint on `padding`/`margin`/`gap` **and every longhand of each**
(landmine 5), permitting `0` and the `--space-*` / gutter / panel-gap tokens only.

**AC 6.** **Given** the token stylesheet itself legitimately contains hex and `rgb()` values,
**when** the bans are configured, **then** the exemption is a **path-scoped `overrides` entry** in
`.stylelintrc.json` naming the token file(s) — **not** `stylelint-disable` comments, which any
component author can copy into their own file and which no test can see. The exemption is the
**narrowest that works**: only `color-no-hex` and `function-disallowed-list` need relaxing, because
the shadow/radius/spacing bans are keyed on *property names* (`box-shadow`, `border-radius`,
`padding`…) and the token file declares custom properties (`--shadow-rest`, `--radius-card`,
`--space-1`), which those keys do not match. Every `stylelint-config-standard` rule stays live on
the token file. If the exemption ends up wider than two rules, say why in the record.

**AC 7.** **Given** each new rule, **when** it is proven, **then** it is shown **firing and not
firing from the same invocation**, in `tests/lint-gates.test.ts`, against fixtures under
`tests/fixtures/css/` — the standing non-vacuity pairing agreement. Each ban is asserted by **rule
name and count**, not merely by `result.errored`, so a rule that stops existing fails the test
instead of being covered by a neighbour.

**AC 8.** **Given** the existing gates, **when** this story lands, **then** they are all still green
without being weakened: `tests/fixtures/css/clean.css` is tokenised so its unfiltered
`warnings).toEqual([])` assertion still holds (landmine 6), the existing ten-warning
`declaration-property-value-disallowed-list` outline count is unchanged, and no existing assertion
is filtered or relaxed to accommodate a new rule.

### The two constraints lint alone cannot express

**AC 9 [epic].** **Given** the surface ramp, **when** a component nests inside another, **then** it
steps exactly one level `well → base → panel → overlay`, never skipping two (UX-DR1). Because no
component exists yet and CSS nesting depth is not statically decidable across files, this story
ships the **mechanism plus its proof**, per Q4: the ramp is declared once as ordered data with a
`stepsExactlyOne(from, to)` predicate, unit-tested for both the legal step and the two-level skip,
and c2-6/c2-7 consume it. The story record states plainly which half is mechanical and which half is
review.

**AC 10 [epic].** **Given** `accent-dim` is used, **when** the surface behind it is
`surface-overlay`, **then** the usage fails (UX-DR6 — the pair is 2.70:1 and fails the 3:1 non-text
floor; `accent` is the substitute). Enforced as a real guard over every `ui/src/**/*.css` rule
block: a block that references both `--accent-dim` and `--surface-overlay` fails, with a failure
message that names `accent` as the fix. Proven firing and not firing.

### Motion

**AC 11 [epic].** **Given** the user has `prefers-reduced-motion: reduce` set, **when** any
tokenised transition runs, **then** the shared motion mechanism resolves it to its non-animated
fallback, **and** that mechanism is the **single place** later epics register their own motion
fallbacks — a `@media (prefers-reduced-motion: reduce)` block that zeroes the four duration tokens,
carrying a comment that names it as the registration point and points at UX-DR42's exhaustive
inventory (reproduced in Dev Notes).

**AC 12 [epic].** **Given** any setting, **when** the stylesheets are inspected, **then** **no
element pulses or loops** — enforced by a guard over every `ui/**/*.css` that fails on
`animation-iteration-count` other than `1`, on the `infinite` keyword in an `animation` shorthand,
and on `alternate`/`alternate-reverse` direction. *Why a guard and not a convention: "no pulsing
dot" is stated four separate times across DESIGN.md and EXPERIENCE.md, and the connection pill
(c5-7) is the exact component a future author will be tempted to animate.*

**AC 13.** **Given** the reduced-motion mechanism, **when** it is tested, **then** the test reads
the **CSS source**, not a rendered DOM. *Why: jsdom does not evaluate media queries into computed
style — `matchMedia` is stubbed and `getComputedStyle` will report the unreduced value, so a
DOM-based assertion here is vacuous by construction.*

### Records and boundaries

**AC 14.** **Given** any CSS change, **when** the story is committed, **then** the SPA bundle is
rebuilt (`cd ui && npm run build`) and the **committed bundle and its `plugin/` mirror are both
regenerated and committed** — otherwise c2-2's `SPA bundle in sync with ui/` CI step and the
`plugin/` drift check both go red. The asset content hash changes; `tests/unit/companion/test_spa.py`
discovers asset names rather than hard-coding them, so no Python test needs editing.

**AC 15.** **Given** the four forward-dated sentences that name this story, **when** it lands,
**then** each is repaired in the same commit (C1 retro forward-dated-comment homing rule):
`ui/README.md:108`, `ui/src/index.css:3`, `ui/src/App.css:1`,
`ui/tests/fixtures/css/violation.css:9`. **And** the ~12 `Story 2.4` references under `src/` and
`plugin/` are **not touched** — those are the *Epic-2 RAG* story (`semantic_search_cards`), a
different story with a colliding number.

**AC 16.** **Given** the document baseline, **when** this story lands, **then**
`ui/src/index.css` consumes the tokens (dark-only `color-scheme: dark`, canvas `--surface-base`,
text `--text-primary`, family `--font-sans`) and `ui/src/App.css`'s `padding: 2rem` / `gap: 0.5rem`
literals become tokens — the placeholder shell must obey the rules this story introduces, or the
first file anyone reads teaches the opposite of the gate.

**AC 17.** **Given** the dependency graph, **when** it is inspected, **then** this story adds **no
runtime dependency** on either side. Any devDependency it adds (Q3's YAML reader is the only
candidate) is listed in `devDependencies`, carries a `"//"` note giving its reason, and does not
trip `tests/package-contract.test.ts`.

**AC 18.** **Given** the scope, **when** the diff is inspected, **then** it touches no `.py` file,
no route, no component, and nothing under `src/` except the regenerated
`src/companion/app/static/` bundle and its `plugin/` mirror. `ui/README.md` gains the token-layer
section; `pyproject.toml` and `uv.lock` are untouched.

## Tasks / Subtasks

- [x] **Task 0 — verify the baseline before changing anything** (standing agreement: story-start
      state verification)
  - [x] `cd ui && npm test` → expect **78 passed / 9 files**; `npm run lint`, `npm run format:check`,
        `npm run typecheck`, `npm run build` all green
  - [x] Repo-root: `uv run pytest -m "not integration"` → expect **1,753 passed / 1 skipped /
        45 deselected**
  - [x] `git status --porcelain` clean, and `git status --porcelain -- src/companion/app/static/
        plugin/` clean (so a later drift is provably yours)
  - [x] Record every number in the Dev Agent Record — the diffs, not the absolutes, are the evidence

- [x] **Task 1 — author the token layer** (AC 1, 2, 3)
  - [x] `ui/src/styles/tokens.css` — `:root, [data-theme="voltglass"]` carrying the full inventory
  - [x] Import it **first** from `ui/src/index.css` so every later sheet sees the tokens
  - [x] Header comment: this file is the ONE place a literal is legal, and why (the four alternate
        themes, the shadowless-theme hierarchy inversion)

- [x] **Task 2 — the motion mechanism** (AC 11, 12, 13)
  - [x] `@media (prefers-reduced-motion: reduce)` block zeroing the four duration tokens, with the
        registration-point comment and the UX-DR42 inventory reference
  - [x] Guard test banning looping/pulsing animation across `ui/**/*.css`, proven both ways
  - [x] Reduced-motion assertion reads CSS source (AC 13), with a comment saying why not jsdom

- [x] **Task 3 — the literal bans** (AC 4, 5, 6)
  - [x] `.stylelintrc.json`: `color-no-hex`, `function-disallowed-list`, and
        `declaration-property-value-allowed-list` with **regex property keys** for shadow, radius
        and the spacing family (landmine 5)
  - [x] Path-scoped `overrides` entry exempting the token file(s) from those rules only
  - [x] Run `npm run lint` over the whole of `ui/` and fix what it finds — including `App.css`

- [x] **Task 4 — the fidelity test** (AC 1, per Q3)
  - [x] Test reads `DESIGN.md` frontmatter and asserts names + normalised values + the nine counts
  - [x] **Non-vacuity anchor first**: assert the frontmatter parsed and that the colour map has 26
        entries, so a moved/renamed DESIGN.md fails loudly instead of asserting over `{}`
  - [x] Normalise before comparing: lowercase hex, parse `rgb()`/`rgba()` to a numeric tuple
        (landmines 1 and 2)

- [x] **Task 5 — the two non-lintable constraints** (AC 9, 10)
  - [x] Ramp declared once as ordered data + `stepsExactlyOne` predicate, unit-tested both ways
  - [x] `--accent-dim` × `--surface-overlay` co-occurrence guard over `ui/src/**/*.css`, proven
        both ways, failure message names `accent`

- [x] **Task 6 — non-vacuity pairing for every new rule** (AC 7, 8)
  - [x] Extend `tests/fixtures/css/{clean,violation}.css` and `tests/lint-gates.test.ts`
  - [x] Tokenise `clean.css`'s `padding: 4px` (landmine 6); confirm the outline count is still 10
  - [x] Assert each new ban by **rule name and count**

- [x] **Task 7 — baseline shell + records** (AC 15, 16, 18)
  - [x] `index.css` / `App.css` onto tokens; repair the four forward-dated sentences; leave the
        `Story 2.4` RAG references alone
  - [x] `ui/README.md`: token-layer section, the one exemption, the reduced-motion registration
        point, and the "Not here yet" update

- [x] **Task 8 — rebuild, mirror, prove** (AC 14, 17, 18)
  - [x] `cd ui && npm run build`; repo root `uv run python -m scripts.build_plugin`; commit both
  - [x] Re-run all five frontend gates and the Python suite; both drift checks clean locally
  - [x] Scope proof: `git diff --stat` shows no `.py`, no `pyproject.toml`, no `uv.lock`

- [x] **Task 9 — probe the evasions before claiming done** (Gotchas 1–6)
  - [x] For each new guard, plant the evasion, confirm it is caught, revert, and paste the output
  - [x] **Verify the mutation landed before believing the check's verdict** (c2-3's near-miss: a
        `$`-anchored PowerShell regex against a CRLF tree never mutated anything and the check
        reported a vacuous pass)

### Review Findings

Adversarial review 2026-07-27 (Blind Hunter + Edge Case Hunter + Acceptance Auditor, branch diff
vs `feat/companion-c2`). All three layers converged on the headline: the story's own review theme
— an evasion the guard's proofs never probed — recurs in the animation ban.

- [x] [Review][Patch] **[Medium] Literal durations bypass the reduced-motion mechanism**
      [ui/.stylelintrc.json] — nothing constrains `transition`/`animation` durations to
      `var(--motion-*)`; `transition: opacity 300ms` plays in full under
      `prefers-reduced-motion: reduce` and no gate notices. **Brad's ruling 2026-07-27: add the
      ban family now** — literal `<time>` values disallowed in `transition`/`animation` +
      longhands, `0s` permitted, proven fixture pair (same shape as the four shipped families).
- [x] [Review][Patch] **[Medium] Native CSS nesting blinds the shared block parser**
      [ui/tests/token-usage.test.ts:74] — `blocksIn` matches innermost brace pairs only;
      declarations in a nesting parent (`.row { background: …; &:hover { … } }`) are never in any
      `body`, so all three guards silently miss them. **Brad's ruling 2026-07-27: ban nesting in
      shipped CSS** — a guard failing on `&`/nested braces in `ui/src` stylesheets, proven both
      ways, keeping the minimal parser's blind spot unreachable.
- [x] [Review][Patch] **[Medium] TSX inline `style={{…}}` bypasses the entire token layer**
      [ui/eslint.config.js] — every gate stops at `*.css`; `style={{ padding: '18px' }}` in a
      c2-6/c2-7 component trips nothing. **Brad's ruling 2026-07-27: add the ESLint ban now**
      (`no-restricted-syntax` on the style attribute or `react/forbid-dom-props`), with a fixture
      pair in the a11y-gate style, so the gate exists before the first component is written.

- [x] [Review][Patch] **[High] Comma-separated animation lists evade BOTH enforcement layers**
      [ui/.stylelintrc.json:45-49, ui/tests/token-usage.test.ts:177-196] — every keyword/number
      regex anchors on `(?:\s|$)`, and in a multi-animation list (`animation: pulse 2s infinite,
      fade 1s`; `animation: pulse 2s 3, fade 1s`; `animation-direction: alternate, normal`) a
      comma follows the token, so nothing fires — verified by execution in two review layers.
      Scientific-notation counts (`1e2`) evade the bare-number regex the same way. Fix: comma-aware
      matching in both layers (per-segment parsing in the guard) + comma-list cases in
      `motion-violation.css` + a legal multi-animation case in the clean half.
- [x] [Review][Patch] **[Medium] The allowed-lists admit ANY token, not the category —
      `padding: var(--radius-pill)` lints clean** [ui/.stylelintrc.json:24-33] — AC 5's letter is
      "the `--space-*` / gutter / panel-gap tokens only", and the rule's own message promises
      `var(--shadow-…|--radius-…|--space-…)`, but the shipped regex is `var\(--[a-z0-9-]+\)`.
      A wrong-family var is invalid CSS that renders as nothing, and the unknown-token guard
      cannot catch it because the token exists. Fix: category-prefix value regexes
      (`--space-*`; `--radius-*`; `--shadow-*`/`--glow`) + wrong-family cases in the violation
      fixture + record the change.
- [x] [Review][Patch] **[Medium] `text-shadow` and `filter: drop-shadow()` sit outside the
      elevation ban** [ui/.stylelintrc.json:24] — the ban is keyed `/^box-shadow$/i` only, so
      hard-coded shadow geometry ships through a fourth and fifth property, and the shadowless
      themes (`graphite`, `ink`) cannot switch it off — the exact hierarchy inversion the gate
      exists to prevent. Fix: add `/^text-shadow$/i` to the allowed-list and `drop-shadow` to
      `function-disallowed-list`, as a flagged widening with a proven fixture pair.
- [x] [Review][Patch] **[Medium] The contrast guard's same-block blind spot is undocumented**
      [ui/tests/token-usage.test.ts:95-107] — `findAccentDimOnOverlay` requires both tokens in one
      rule block; parent-sets-background/child-sets-border (the *normal* shape in c6-7/c9-1 rows)
      escapes. `surfaces.ts` is scrupulously honest about its review-owned half; this guard is
      presented as "a real guard" with no mention of its equally real limit. Fix: the same honesty
      — comment + README line stating review owns the cross-block half.
- [x] [Review][Patch] **[Low] `readTokens()` breaks on the file's own documented extension path**
      [ui/tests/tokens.test.ts:93-94] — first-`{`/last-`}` slicing before the first `@media`
      assumes one block; the sibling `[data-theme='gilt']` block the header comment instructs
      would either pollute the parsed inventory or be invisible to the suite. Fix: anchor
      extraction to the `:root, [data-theme='voltglass']` selector's block.
- [x] [Review][Patch] **[Low] The reduced-motion extraction regex is greedy to the last `}` in
      the file** [ui/tests/token-usage.test.ts:378] — `\{([\s\S]*)\}` works only because the media
      block ends the file today; any rule appended after it joins the "reduced" body and the four
      zeroing assertions can be satisfied from outside the media query. Fix: brace-aware
      extraction.
- [x] [Review][Patch] **[Low] `stepsExactlyOne`/`nextSurface` answer wrongly for out-of-ramp
      names** [ui/src/styles/surfaces.ts:46,56] — `indexOf === -1` makes
      `stepsExactlyOne('bogus', 'surface-well')` true (`0 − (−1) === 1`) and
      `nextSurface(unknown)` return `'surface-well'`. Type-level protection stops at any
      `as`-cast/JS boundary. Fix: guard the −1 case (false/null) + two unit tests.
- [x] [Review][Patch] **[Low] Doc/guard mismatch on what may declare tokens**
      [ui/src/styles/tokens.css:25, ui/tests/token-usage.test.ts:9] — both say "no stylesheet
      outside src/styles may declare", but the guard enforces `!== 'src/styles/tokens.css'`
      (file-level, stricter, correct). Fix: align the two comments to the file-level truth.
- [x] [Review][Patch] **[Low] The tokens.css override has no paired vitest proof**
      [ui/.stylelintrc.json:52-60] — every rule ships a firing/silent pair except the one
      *override*; `lint-gates.test.ts` never lints the real `tokens.css`. `npm run lint` covers
      the firing half in CI only. Fix: a lint-gates test linting the real `tokens.css` clean under
      the real config.
- [x] [Review][Patch] **[Low] `yaml`'s "nothing in src/ may import it" is convention beside two
      test-enforced siblings** [ui/package.json:33] — `tests/package-contract.test.ts` never
      mentions `yaml`. Fix: the one-line assertions (devDependencies-only, no `src/` import),
      matching the sibling notes' pattern.
- [x] [Review][Patch] **[Low] The `auto` spacing widening is unflagged in the record**
      [_bmad-output/implementation-artifacts/c2-4-the-voltglass-token-layer.md] — the shipped
      padding/margin regex admits `auto` (justified in `clean.css`), but the record's "six
      deliberate widenings, none silent" list omits it, contradicting the convention it invokes.
      Fix: add it to the record's widening list.

- [x] [Review][Defer] **[Low] Typography literals are the ungated family**
      [ui/.stylelintrc.json] — no rule keys `font`/`font-size`/`font-weight`/`line-height`/
      `letter-spacing`, so components can hard-code type off the seven roles — deferred, c2-5
      owns type-role enforcement (the numeric-pairing lint); widening it to a full font-literal
      ban is c2-5's scope decision.

### Review patches applied (2026-07-27, same session)

**All 14 applied. Frontend suite 124 → 140 (12 files); Python unchanged at 1,753 passed /
1 skipped / 45 deselected; all five gates green; bundle and mirror regenerated.** The three
new gate families Brad ruled in are live, and every one of the fourteen is proven both ways
from the same invocation, like the four that shipped at implementation.

**The High finding was real and the fix is bigger than the report.** Closing the comma
evasion in the config alone would have left the guard open, so both layers now split values
into per-animation segments before testing anything, and the guard parses counts as NUMBERS
rather than string-comparing to `"1"` — which closes `1e2` in the same move.

**One of my own proofs was invalidated by another patch, and had to be replaced rather than
re-asserted.** The story record claimed stylelint is silent on `animation: pulse 2s 3`. That
was true when written; adding the duration ban made stylelint fire on it — for the `2s`, not
the count. The claim would have kept passing for the wrong reason. Two new fixture blocks
(`.loops-by-count-with-tokenised-duration`, `.loops-by-scientific-count-with-tokenised-duration`)
tokenise the duration so the count is the only fault, and `lint-gates.test.ts` now asserts
stylelint is silent on exactly those two and nothing else.

**Six mutation probes, each verified landed before its verdict was believed, all reverted:**

- **P1 — nesting ban.** First attempt planted `}` + a sibling selector, which is flat CSS, not
  nesting; the guard stayed silent and was **right to**. Redone with a genuinely nested rule
  → `× uses no CSS nesting`, naming `.nested` inside `.app-shell`. *The probe was wrong, not
  the guard — which is the whole reason to read what landed on disk rather than trust the
  intent of the edit.*
- **P2 — the `&` form** → caught, two findings (the nested brace pair and the `&`).
- **P3 — comma-list `infinite`** in a real stylesheet → `× never pulses or loops (AC 12)`.
- **P4 — removing the `-1` guard** from `stepsExactlyOne` → `× refuses an out-of-ramp name`.
- **P5 — all five evasions at once** in `src/App.css`: comma-list `infinite`,
  `transition: opacity 300ms`, `padding: var(--radius-pill)`, a literal `text-shadow` and a
  `drop-shadow()` → **8 stylelint errors**, each naming its fix.
- **P6 — inline `style={{ padding: '18px' }}`** in the real `src/App.tsx` → the ESLint ban
  fires with the message pointing at the README. (First attempt did not land — the harness
  refused rather than reporting a vacuous pass.)

**One finding not in the review, found while patching:** `tests/fixtures/tsx/` needed adding
to `tsconfig.app.json`'s `include`, or ESLint's `projectService` errors on a `.tsx` outside
any tsconfig. Listed individually rather than as a blanket `tests/fixtures`, because
`tsconfig.node.json` already includes every `.ts` under `tests` and a blanket entry would put
future `.ts` fixtures in both projects at once.

**A seventh widening for the record** (bringing the flagged list to eight, see below): the
`(transition|animation)` duration family, `text-shadow`, `drop-shadow()`, the category-prefix
requirement, the nesting ban and the inline-style ban all go beyond the ACs' letter. Each was
ruled or reported by review rather than chosen unilaterally.

**Also corrected here:** the record's "six deliberate widenings, none silent" list omitted the
`auto` allowance in the padding/margin regex (justified in `clean.css`, unflagged in the
record) — it is item 7 in that list now, and the review families are item 8. A list that
invokes the no-silent-widenings convention has to be complete or it is not doing its job.

Dismissed as noise (4): AC 7 "same invocation" (substance met — every `lintAll()` lints all four
fixtures in ONE `stylelint.lint()` call; assertions are merely spread across `it` blocks);
`parseColour` ignoring non-hex/rgb notations (degrades to a loud false-failure, never a silent
pass, and Q2 confines the notation); the hand-duplicated 64 in two suites (both sides fail loud);
CSS system colours (`Canvas`, `Highlight`) evading the colour bans (near-zero probability, and
under forced-colors the UA repaints regardless).

## Dev Notes

### Decide-once rulings (c2-5 … c2-10, c4, c6 and c7 inherit these)

1. **The token file is the only place a literal is legal, and the exemption is path-scoped.**
   Every other stylesheet in `ui/` reaches colour, radius, shadow and space through `var(--…)`.
   The exemption is an `overrides` entry keyed on path, never a `stylelint-disable` comment.
2. **The four alternate themes are the reason, not a hypothetical.** `gilt`, `graphite`,
   `verdigris` and `ink` exist in the imported design system; `graphite` and `ink` declare
   themselves **shadowless** (both elevation tokens `none`). A hard-coded *rest* shadow does not
   merely look wrong under those themes — it inverts the hierarchy, because `shadow-raise` is the
   *live* state.
3. **Motion fallbacks register in one block.** Any story adding a motion adds its fallback to the
   `prefers-reduced-motion` block in `motion`'s section of the token layer, and to UX-DR42's
   inventory. A motion with no registered fallback is an incomplete story.
4. **Nothing pulses or loops, ever, under any setting.** This is a guard, not a guideline.
5. **`accent-dim` never sits on `surface-overlay`.** The substitute is `accent` (5.5:1). This
   applies to suggestion rows, swap rows and tier rows specifically (c6-7, c9-1, c9-2).
6. **`text-tertiary` on `surface-overlay` is 4.8:1 with zero headroom.** Do not darken it, and
   **do not introduce a fifth surface above `surface-overlay`** — the ramp is closed at four.

### The token inventory (the contract for AC 1)

Source: `DESIGN.md` frontmatter. Names follow the Q1 mapping; where the imported
`_ds/tokens/theme-voltglass.css` already ships a name, it is reused verbatim.

**Colours (26)** — `--surface-well` `#0d0f1a` · `--surface-base` `#12141f` · `--surface-panel`
`#191c2b` · `--surface-overlay` `#222639` · `--scrim` `rgba(8,9,18,0.75)` · `--border-hairline`
`#2c3048` · `--border-strong` `#3d4266` · `--text-primary` `#e9ebf5` · `--text-secondary` `#b3b8cf`
· `--text-tertiary` `#8b91ad` · `--text-inverse` `#10121c` · `--accent` `#8b93ff` ·
`--accent-bright` `#b3baff` · `--accent-dim` `#575fbe` · `--accent-glow` `rgba(139,147,255,0.22)` ·
`--focus-ring` `#b3baff` · `--positive` `#5fd4a0` · `--negative` `#ff7a86` · `--caution` `#ffc266` ·
`--mana-w` `#e8e6d6` · `--mana-u` `#5cb2f0` · `--mana-b` `#ab93cf` · `--mana-r` `#f0716b` ·
`--mana-g` `#5ec98a` · `--mana-gold` `#e0b95e` · `--mana-colorless` `#9aa0b5`

**Typography (7 roles)** — as `font` shorthands over `--font-sans`, plus the tracking and numeric
companions:

| Token | Value | Companion |
| --- | --- | --- |
| `--type-display` | `500 30px/1.1` | `letter-spacing: -0.02em` |
| `--type-heading` | `500 17px/1.3` | — |
| `--type-body` | `400 14px/1.5` | — |
| `--type-body-strong` | `700 14px/1.5` | — |
| `--type-label` | `500 11px/1.3` | `--tracking-label: 0.1em`, uppercase |
| `--type-micro` | `400 10px/1.3` | `--tracking-micro: 0.08em`, uppercase |
| `--type-numeric` | `500 13px/1.4` | `--type-numeric-features: tabular-nums` |

> **The imported `_ds/tokens/typography.css` DRIFTS from DESIGN.md on three roles** and DESIGN.md
> wins: body line-height `1.55` → **1.5**; body-strong weight `600` → **700**; micro `500 10.5px`
> → **400 10px**. It also names durations `--dur-1..4`. Read values from DESIGN.md frontmatter,
> never from the import.

**Radii (4 + card)** — `--radius-sm` `6px` · `--radius-md` `10px` · `--radius-lg` `16px` ·
`--radius-pill` `999px` · `--radius-card` `4.75% / 3.4%` (the real printed-card corner ratio; UX-DR4
makes it exclusive to card faces, thumbnails, placeholders and detail art)

**Spacing (7 + 2)** — `--space-1` `4px` · `--space-2` `8px` · `--space-3` `12px` · `--space-4`
`16px` · `--space-5` `24px` · `--space-6` `32px` · `--space-7` `48px` · `--space-gutter` `32px` ·
`--space-panel-gap` `24px`

**Motion (4 durations + 3 easings)** — `--motion-pulse` `100ms` · `--motion-glide` `240ms` ·
`--motion-bloom` `480ms` · `--motion-aurora` `900ms` · `--ease-out`
`cubic-bezier(0.25,0.1,0.25,1)` · `--ease-glide` `cubic-bezier(0.4,0,0.2,1)` · `--ease-snap`
`cubic-bezier(0.2,0,0,1)`

**Focus ring** — `--focus-ring` (above) · `--focus-ring-width` `2px` · `--focus-ring-offset` `2px`

**Elevation (3)** — `--shadow-raise` `0 0 0 1px rgba(139,147,255,0.14), 0 12px 32px rgba(0,0,0,0.5)`
· `--shadow-rest` `0 12px 32px rgba(0,0,0,0.5)` · `--glow` `0 0 16px var(--accent-glow)`

**Family** — `--font-sans: 'Space Grotesk', system-ui, sans-serif` (c2-5 adds the `@font-face`)

### UX-DR42's exhaustive reduced-motion inventory (reproduce as the registration comment)

Each motion with its named fallback, owned by the story that builds it:

| Motion | Fallback | Owner |
| --- | --- | --- |
| Agent-view bloom (fade + 8px rise) | appears in place | c6-5 |
| Push-replace crossfade | instant content swap | c6-6 |
| Card-tile hover pop | no scale, shadow only | c4-4 |
| Image fade-in | instant appearance | c4-4 |
| Curve-bar height | instant jump | c4-8 |
| Deck-row live tint | instant | c4-7 |
| Accent glow fade | glow omitted — count text + live region carry the signal | c7-5 |
| Refetch header shimmer | static "Updating…" in `--type-micro` `--text-secondary` | c7-5 |
| DFC flip 3D Y-rotation | instant face swap | c4-6 |
| Detail-panel content swap | instant, no crossfade (it changes on every hover) | c4-5 |

**No element pulses or loops under any setting.** Any motion added later is added to this list with
a fallback (Decide-once #3).

### Architecture rules this story implements

- **UX-DR1** — the token set itself, and "every shadow and radius goes through a token".
- **UX-DR5** — the 4/8/12/16/24/32/48 scale; the mock's 18/14/9/7px one-offs are drift.
- **UX-DR6 / UX-DR41** — the two no-headroom contrast constraints (Decide-once #5, #6).
- **UX-DR42** — the reduced-motion mechanism and its inventory.
- **UX-DR46** — the existing outline ban stays exactly as it is; this story adds the focus-ring
  *tokens* the replacement is written against, closing the "whether a replacement is adequate is
  asserted by … c2-4's token work" note in `violation.css`.
- **AD-13** — the build output is a committed artefact; a CSS change is a bundle change (AC 14).
- **NFR-07** — the frontend gates are the enforcement mechanism, in CI from the first commit.
- **FR-20** — the visual identity + token system is this epic's job and this story is its floor.

### Source tree — what exists, what this story adds

```
ui/
  .stylelintrc.json          UPDATE  + color-no-hex, function-disallowed-list,
                                     declaration-property-value-allowed-list (regex keys),
                                     overrides[] exempting the token file
  README.md                  UPDATE  token-layer section; repair line 108; "Not here yet"
  src/
    styles/
      tokens.css             NEW     :root, [data-theme="voltglass"] — the whole inventory
      surfaces.ts            NEW?    ordered ramp + stepsExactlyOne() (AC 9, per Q4)
    index.css                UPDATE  imports tokens; dark-only baseline on tokens; repair line 3
    App.css                  UPDATE  2rem / 0.5rem → tokens; repair line 1
  tests/
    fixtures/css/clean.css       UPDATE  padding: 4px → var(--space-1)  (landmine 6)
    fixtures/css/violation.css   UPDATE  add the new violations; repair line 9
    lint-gates.test.ts           UPDATE  a proven pair per new rule (AC 7)
    tokens.test.ts               NEW     DESIGN.md fidelity + counts (AC 1, Task 4)
    token-usage.test.ts          NEW     accent-dim×overlay, animation loop ban (AC 10, 12)
src/companion/app/static/    REGENERATED  npm run build (AC 14)
plugin/server/src/companion/app/static/  REGENERATED  scripts.build_plugin (AC 14)
```

Nothing else. No `.py`, no route, no component, no `pyproject.toml`, no `uv.lock`.

### Gotchas specific to this story

1. **The longhand evasion (measured, landmine 5).** Plain-string property keys miss
   `padding-left`, `margin-block-start`, `column-gap`, `border-bottom-right-radius`. Use regex
   property keys and **prove each longhand in the violation fixture** — the c2-3 review's finding
   was that every guard's own proofs skipped the case that walked around it.

2. **The `var()`-list evasion, in the other direction.** `box-shadow: var(--shadow-rest),
   var(--glow)` is *legitimate* (DESIGN.md composes glow onto rest). An `^var\(--…\)$`-anchored
   value regex rejects it and the first real component fights the gate. Measured working form:
   `/^(none|var\(--[a-z0-9-]+\)(\s*,\s*var\(--[a-z0-9-]+\))*)$/`. Prove the two-var case in the
   *clean* fixture, or the story ships a rule c4-4 has to fight.

3. **Prettier and stylelint both have opinions about your token values** (landmines 1, 2). Decide
   Q2 before writing the file, not after `format:check` goes red. Note also `color-hex-length:
   'short'` is on — none of the 26 colours is shortenable, so it is inert here, but a future
   `#ffffff` would be rewritten to `#fff` and a byte-comparison test would break.

4. **`--radius-card` is `4.75% / 3.4%` — a two-value percentage radius.** The
   `border-radius` allowed-list must admit `var(--radius-card)` like any other token (it does; the
   value lives in the exempt file), but any test that parses radius values must not assume `px`.

5. **The reduced-motion block is not testable through jsdom** (AC 13). `window.matchMedia` is not
   implemented in jsdom by default and `getComputedStyle` does not apply media queries — a test that
   renders a component and reads a duration will report the *unreduced* value and pass for the wrong
   reason. Read the CSS source.

6. **A CSS change is a bundle change** (AC 14). Forgetting `npm run build` +
   `scripts.build_plugin` reddens two CI checks that have nothing to do with CSS, and the error
   message points at staleness rather than at what you changed. The pre-commit `build-plugin-sync`
   hook fires on `src/` changes and will mirror the bundle for you — but **nothing rebuilds the
   bundle from `ui/`**; that is a manual `npm run build`.

7. **Do not enable `no-unknown-custom-properties`** (landmine 3). It is file-scoped and will report
   every legitimate token reference in every component file.

8. **`Story 2.4` under `src/` is a different story** (AC 15). The Epic-2 RAG story
   (`semantic_search_cards`) shares the number. Repair only the four `c2-4` sentences.

9. **No script or config change is needed to *reach* the new files.** `npm run lint` already globs
   `"**/*.css"` with three `--ignore-pattern`s (`dist/**`, `coverage/**`, `tests/fixtures/**`), so
   `src/styles/tokens.css` is linted the moment it exists; `src/` is already in
   `tsconfig.app.json`'s `include`, so a `.ts` file under `src/styles/` type-checks with no config
   edit. If you find yourself editing `package.json`'s `lint` script, stop and re-read why.

10. **A CSS `@import` must precede every other rule in the file.** `index.css` currently opens with
    a comment then `:root { … }`; the token import goes above the `:root` block, not after it, or
    the browser (and the build) drop it. Importing from `main.tsx` instead is the alternative, but
    it splits the document's styling across two languages for no gain.

### Testing standards

- vitest, two projects (`node` for `tests/**`, `dom` for `src/**`) — new gate/guard tests are
  **node**-project tests under `ui/tests/`, matching `lint-gates.test.ts` and
  `gate-geometry.test.ts`. A `.test.tsx` under `tests/` is banned by `gate-geometry.test.ts`.
- **Every new lint rule gets a proven pair** from one invocation (AC 7). Assert by **rule name and
  count**; `result.errored` alone cannot distinguish which rule fired.
- **Non-vacuity anchor first** in any test that filters a list (the `gate-geometry.test.ts` idiom):
  assert the list is populated before asserting anything is absent from it.
- Fixtures live in `tests/fixtures/`, are excluded from `npm run lint` by CLI `--ignore-pattern`
  (deliberately **not** a `.stylelintignore` — an ignore *file* is also honoured by the Node API and
  would silently neuter the tests that lint them), and are meant to stay broken.
- Python side: no new tests. `tests/unit/companion/test_spa.py` discovers asset names, so the
  rehashed bundle needs no edit — but re-run the suite to prove it.

### Previous story intelligence (c2-3, done 2026-07-27; PR #20 merged into `feat/companion-c2`)

- **The review theme was universal guard vacuity**: *every* regex/list-based guard c2-3 shipped —
  CI `ls-files` non-vacuity, the AC 10 re-declaration ban, the single-reader scan, the codegen ban,
  the docstring-section set — had at least one evasion its own mutation proofs never probed. Three
  mediums came out of it. This story adds four families of value guards; **budget Task 9 for it.**
- **A mutation proof that never mutated**: a PowerShell regex with a `$` anchor against a CRLF
  working tree left the file untouched, and the drift check reported a vacuous "no drift" that was
  one step from being pasted as a finding. `git status --porcelain` on the mutated file caught it.
  **Verify the mutation landed before believing the verdict.**
- **All four open questions were answered before Task 0**, and nothing surfaced mid-story — the
  second story running to hold that discipline. The questions below are written to be answerable in
  one pass for the same reason.
- **Deviations are flagged, never silent** (the c1-9 / c2-1 / c2-2 / c2-3 precedent): where a
  measured fact contradicts the epic's literal wording, ship the working form and record why.
- c2-2 established that **`.gitattributes` and line endings are settled**: `ui/.gitattributes`
  forces LF over all of `ui/`, so new CSS files are byte-deterministic on Windows and ubuntu alike.
  No new attribute is needed for `.css`.

### Git intelligence

Last five commits are all c2-3 (`26a9fdf` merge, `923ae99` review patches, `8ba0313`/`e003031`
records, `57d3dea` + `18fe682` implementation). The shape to copy: **implementation commit, then a
separate records commit, then a review-patch commit** — and the review-patch commit's message names
the *theme*, not the count. Conventional Commits, scope `companion`.

Branch off `feat/companion-c2` as `feat/companion-c2-4-voltglass-tokens`; the story PR targets the
umbrella branch, with a Greptile pass (per-epic integration PR to master at the retro gets none —
standing rule, OSS free-tier budget).

### Latest technical information

- **stylelint 17.14.1 / stylelint-config-standard 40.0.0** — all rules named in this story exist and
  were exercised at the baseline commit: `color-no-hex`, `function-disallowed-list`,
  `declaration-property-value-allowed-list` (regex property keys supported),
  `declaration-property-value-disallowed-list` (already in use), `no-unknown-custom-properties`
  (exists; unusable here — landmine 3). `custom-property-pattern`'s default
  `^([a-z][a-z0-9]*)(-[a-z0-9]+)*$` accepts every name in the inventory, including `--space-1` and
  `--type-body-strong`.
- **Prettier 3.9.x** lowercases CSS hex colours and lowercases property names (the latter is why
  c2-1's uppercase-`OUTLINE` evasion is closed by the format gate rather than by stylelint).
- **Node 24.15.0 local / 20 in CI.** No CSS toolchain in this story is version-sensitive across
  that gap, but the bundle is rebuilt on both — the cross-platform build-determinism risk c2-2
  carried applies unchanged: push early and let CI speak; **do not loosen a drift check that fires.**

### Project Structure Notes

- `ui/src/styles/` is a **new directory inside `src/`**, which is already in `tsconfig.app.json`'s
  `include: ["src"]` — so a `.ts` file there needs no config change (README, *Adding a source
  directory*). A new top-level directory would; this is not one.
- Test files must live under `ui/tests/` or `ui/src/`, `.test.ts` or `.test.tsx`, or
  `gate-geometry.test.ts` fails the build. `.jsx`/`.mjs`/`.cjs` are banned outright.
- The Python layering rules in `project-context.md` do not apply to `ui/` — but the *discipline*
  does: Google-style docs become file-header comments explaining **why**, and every guard carries a
  failure message that names its fix (the c2-2/c2-3 house pattern).

### References

- [epics-companion-app.md#Story-2.4](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  seven AC blocks (lines 1305-1343)
- [epics-companion-app.md#UX-DR1..7](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  token set, self-hosted font, tabular numerals, card geometry, the spacing scale, the two
  no-headroom contrast constraints, the brand hard rules (lines 334-368)
- [epics-companion-app.md#UX-DR41..47](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  accessibility floor, incl. UX-DR42's exhaustive reduced-motion inventory (lines 574-609)
- [DESIGN.md frontmatter](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md)
  — **the token contract** (lines 1-250); the computed-contrast table incl. `accent-dim` 2.70 ✗ on
  `surface-overlay` (lines 277-296); *Elevation & Depth* on why a literal shadow inverts hierarchy
  under the shadowless themes (lines 330-338); *Shapes* on the exclusive card radius (line 344)
- [EXPERIENCE.md#Accessibility-Floor](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md)
  — the `prefers-reduced-motion` inventory verbatim, and "motion is never the sole signal"
- [\_ds/tokens/theme-voltglass.css](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/imports/claude-design/_ds/tokens/theme-voltglass.css)
  — the as-built names Q1 reuses. Its sibling `typography.css` and `motion.css` **drift from
  DESIGN.md on three type roles and all four duration names** — names may be reused, values may not
- [ARCHITECTURE-SPINE.md#AD-13](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md)
  — the committed SPA bundle; the *Visual experience* capability row naming DESIGN.md + EXPERIENCE.md
  as the contract (line 470)
- [c2-1 story record](_bmad-output/implementation-artifacts/c2-1-frontend-scaffold-with-the-full-quality-gate-from-the-first-commit.md)
  — Ruling B1 (stylelint owns the CSS rules, not `@eslint/css`), the fixture `--ignore-pattern`
  reasoning, the gate-geometry rules, the non-vacuity pairing idiom
- [c2-2 story record](_bmad-output/implementation-artifacts/c2-2-the-backend-serves-the-built-spa-as-a-committed-artifact.md)
  — the bundle/mirror drift checks a CSS change must satisfy, and the deviation culture
- [c2-3 story record](_bmad-output/implementation-artifacts/c2-3-typescript-types-generated-from-the-backends-own-openapi-drift-checked-in-ci.md)
  — the guard-vacuity review theme and the mutation-that-never-landed near-miss
- [epic-c1-retro-2026-07-26.md](_bmad-output/implementation-artifacts/epic-c1-retro-2026-07-26.md) —
  the standing team agreements (forward-dated-comment homing, open-question homing, non-vacuity
  pairing, story-start state verification)
- [ui/README.md#The-quality-gate](ui/README.md) — line 108 is the forward-dated sentence this story
  closes ("c2-4 adds four more rules of the same shape")
- [project-context.md](_bmad-output/project-context.md) — repo conventions; note the Python layering
  rules do not govern `ui/`, but the commenting and failure-message discipline does

## Open questions for Brad — answer before `dev-story`

Each carries a recommendation; "as proposed" on all five is a complete answer.

**Q1 — the frontmatter-key → CSS-custom-property mapping.** AC 1 says names match "byte-for-byte",
but the frontmatter keys are nested (`rounded.sm`, `spacing.1`, `components.motion.pulse`) and CSS
custom properties are flat. *Recommendation:* reuse the imported `theme-voltglass.css` names
verbatim where they exist (`--surface-*`, `--radius-*`, `--space-N`, `--ease-*`, `--type-*`,
`--tracking-*`, `--shadow-raise`, `--focus-ring`) and extend the same pattern for the ones it lacks
(`--radius-card`, `--space-gutter`, `--space-panel-gap`, `--shadow-rest`, `--glow`,
`--focus-ring-width`, `--focus-ring-offset`, `--type-numeric-features`). **One deliberate
divergence:** durations ship as `--motion-pulse|glide|bloom|aurora`, **not** the import's
`--dur-1..4` — DESIGN.md's prose references `{components.motion.glide}` throughout, and a numbered
token throws the name away at the point of use.

**Q2 — token value notation.** DESIGN.md's `rgba(8,9,18,0.75)` produces 15 stylelint errors as
written (landmine 1), and prettier lowercases the hex (landmine 2). *Recommendation:* write values
in the repo's canonical CSS notation — lowercase hex, modern `rgb(8 9 18 / 75%)`, percentage alpha —
so **no `stylelint-config-standard` rule is disabled anywhere**, and have the fidelity test compare
*normalised colour values* rather than strings. The alternative (verbatim values + three disabled
rules in the token file) is simpler to test and leaves the one file everyone reads written in a
dialect no other file may use.

**Q3 — how the fidelity test reads DESIGN.md.** *Recommendation:* add `yaml` as a **devDependency**
and read
`../_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md`
through one named path constant, with the non-vacuity anchor from Task 4 so a moved file fails
loudly. The alternative — committing a derived JSON manifest into `ui/` — adds a second copy of the
tokens and a second thing to drift, which is the exact failure mode AD-12 exists to prevent. Note
the path carries a date; if the UX artefacts are ever re-exported the constant is the one edit.

**Q4 — how far AC 9 (surface ramp) can honestly be enforced.** Cross-file CSS nesting depth is not
statically decidable, and no component exists yet. *Recommendation:* ship the ramp as ordered data
plus a `stepsExactlyOne(from, to)` predicate with unit tests for the legal step and the two-level
skip, have c2-6/c2-7 consume it, and state in the story record that the *adjacency* half is
mechanism + review rather than a lint gate. AC 10 (`accent-dim` × `surface-overlay`) **is** a real
guard and ships as one. Say so plainly rather than implying both are lint-enforced.

**Q5 — does c2-4 own the document baseline and the family token?** `index.css` currently carries a
`system-ui` stack and `color-scheme: light dark`, and its own comment assigns the font swap to c2-5.
*Recommendation:* yes — c2-4 defines `--font-sans` (with the `system-ui` fallback still in the
stack) and moves `index.css`/`App.css` onto tokens including `color-scheme: dark`; c2-5 adds only
the `@font-face` rules and the numeric-pairing lint. Otherwise this story ships a gate that the two
files at the root of the app visibly violate.

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (`claude-opus-5[1m]`), via the `bmad-dev-story` workflow.

### Open questions — all five answered BEFORE Task 0

Brad, 2026-07-27, **"as proposed" on all five**. Nothing surfaced mid-story; this is the third
story running to hold that discipline (c2-2, c2-3, c2-4).

- **Q1** — reuse `theme-voltglass.css` names verbatim, extend the pattern for the rest,
  durations as `--motion-pulse|glide|bloom|aurora` (**not** the import's `--dur-1..4`).
- **Q2** — canonical CSS notation (lowercase hex, modern `rgb(8 9 18 / 75%)`, percentage
  alpha) so **no `stylelint-config-standard` rule is disabled anywhere**; the fidelity test
  compares normalised colour values.
- **Q3** — `yaml` devDependency, read `DESIGN.md` directly through one named path constant.
- **Q4** — AC 9 ships as ordered data + `stepsExactlyOne()`, unit-tested both ways, with the
  record stating plainly that the adjacency half is mechanism + review, not a lint gate.
- **Q5** — yes, c2-4 owns `--font-sans` and moves `index.css`/`App.css` onto tokens.

### Debug Log References

**Task 0 baseline at `26a9fdf`, every number as the story predicted:**

| Gate | Baseline | After |
| --- | --- | --- |
| `npm test` | **78 passed / 9 files** | **124 passed / 12 files** |
| `npm run lint` / `format:check` / `typecheck` / `build` | green | green |
| `uv run pytest -m "not integration"` | **1,753 passed / 1 skipped / 45 deselected** | same |
| `git status --porcelain -- src/companion/app/static/ plugin/` | clean | clean after rebuild |

The baseline `npm run build` reproduced the committed bundle **byte-for-byte** (empty drift),
which is what makes the later bundle change provably this story's.

`git status --porcelain` was **not** empty at Task 0: `sprint-status.yaml` was modified and the
story file untracked. Both are the create-story run's own artefacts, not pre-existing drift.

**One pre-existing flake, unrelated and not caused here.** The first post-change Python run
reported `tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field`
failed (1,752 passed). This is the `created_at`-tie order flake logged in c2-1's deferred work.
Proven nondeterministic rather than assumed: run in isolation three times with no code change
between runs it went **FAIL, PASS, PASS**, and the full suite re-run was **1,753 passed / 1
skipped / 45 deselected**. This story touches no `.py` file at all (scope proof below).

**Task 9 — the evasion probes.** Every mutation was applied by a Node harness that refuses to
proceed unless the bytes on disk actually changed, and every verdict was preceded by
`git status --porcelain` on the target — c2-3's near-miss was a mutation that never landed
followed by a vacuous pass. All ten reverted; the harness was deleted.

- **A — the longhand evasion (gotcha 1 / landmine 5), the headline result.** Replacing the
  three regex property keys with the obvious plain-string keys (`border-radius`, `padding`,
  `gap`) drops the catch rate on `literals-violation.css` from **13 to 6**. Still caught:
  `box-shadow`×2, `border-radius`, `padding: 18px`, `gap: 7px`, `padding: 8px`. **Walking
  free: `border-bottom-right-radius`, `border-start-start-radius`, `padding-left`,
  `margin-top`, `margin-block-start`, `margin: 14px 9px`, `column-gap`.** Two of those seven
  (`border-start-start-radius`, `margin-block-start` — the LOGICAL longhands) are axes the
  story's landmine 5 did not list. Restored: 13.
- **B — the var()-list evasion in the other direction (gotcha 2).** Tightening the shadow
  value regex to `^(none|var\(--…\))$` turns the **clean** fixture red on
  `box-shadow: var(--shadow-rest), var(--glow)` — the exact composition DESIGN.md specifies
  for the card-tile live ring and the nav-pill hover glow. Shipped the permissive form.
- **C1** un-zeroing `--motion-glide` in the reduced-motion block → `× zeroes all four duration
  tokens`.
- **C2** changing **one hex digit** (`#0d0f1a` → `#0d0f1b`) → `× ships all 26 colours at
  exactly the DESIGN.md value`. The normalisers are not laundering differences.
- **C3** deleting `--tracking-micro` → `× declares exactly the inventory and nothing else` +
  `× carries the tracking companions…`.
- **C4** planting `--accent-dim` + `--surface-overlay` in the real `src/App.css` →
  `× never puts --accent-dim on --surface-overlay (AC 10, UX-DR6)`.
- **C5** declaring a token in `src/App.css` → `× declares tokens in exactly one file (AC 2)`.
- **C6** `var(--space-sixx)` in `src/App.css` → `× references no token that does not exist`.
- **C7 — the one that justifies two layers.** `animation: spin 2s 3;` in `src/App.css`:
  **stylelint exits 0, completely silent** (a value-level regex cannot separate that bare `3`
  from the bare numbers in a `cubic-bezier(0.4, 0, 0.2, 1)`), while the guard reports
  *"the animation shorthand carries an iteration count of `3`. Nothing pulses or loops, at any
  setting…"*.
- **C8** renaming `--surface-panel` → `× keeps the surface ramp in src/styles/surfaces.ts in
  step with the tokens`, so `stepsExactlyOne` can never reason about a ramp that stopped
  existing.
- **C9 — is the exemption NARROW (AC 6)?** Planting `border-radius: 18px` and `outline: none`
  *inside* the exempt token file still produces four errors:
  `declaration-property-value-allowed-list`, `declaration-property-value-disallowed-list`,
  `declaration-empty-line-before`, `custom-property-empty-line-before`. Only the three colour
  rules are relaxed there; every other `stylelint-config-standard` rule stays live.
- **C10 — does the exemption LEAK?** The same hex, `rgb()` and named colour planted in
  `src/App.css` produce three errors, each naming its fix.
- **C11 — case and `!important`, both directions.** `PADDING-LEFT: 18px` → caught (the `/i`
  property keys work). `padding: 18px !important` → caught. `padding: var(--space-2)
  !important` and `box-shadow: var(--shadow-rest), var(--glow) !important` → **not** flagged;
  PostCSS separates `!important` from the value, so there is no false positive waiting for the
  first component that needs one.

### Completion Notes List

All 18 ACs met. The token layer ships 64 tokens in one themeable block, four families of
literal ban with regex property keys, and five guards — each proven firing and not firing from
the same invocation. Frontend suite **78 → 124** (9 → 12 files); Python untouched at 1,753.

**Three landmines the story did not predict, all found by running things rather than reading
them:**

1. **`@import './styles/tokens.css'` fails `npm run lint`.** `stylelint-config-standard` sets
   `import-notation: 'url'`. The shipped form is `@import url('./styles/tokens.css')`, and the
   built bundle was inspected to confirm Vite still inlines it — all 64 tokens and the
   reduced-motion block are present in the emitted CSS.
2. **`ui/**/*.css` inside a CSS comment terminates the comment early.** The `**/` is a `*/`.
   It produced nine `Cannot parse selector` errors from a comment. Reworded, not escaped.
3. **`hue-degree-notation` is `'angle'`, not `'number'`.** Removing the `deg` from a fixture's
   `hsl()` made things worse (1 → 2 warnings). Both `hsl()` and `oklch()` hues carry `deg`.

**Six deliberate widenings/deviations, none silent** (the c1-9 / c2-1 / c2-2 / c2-3 precedent):

1. **`color-named: "never"` added**, beyond AC 4's letter. `color: white` is a hard-coded
   colour that evades both bans AC 4 names. Proven firing (C10) and not firing (clean fixture).
2. **`function-disallowed-list` widened** past AC 4's `rgb/rgba/hsl/hsla` to
   `hwb|lab|lch|oklab|oklch|color|color-mix|light-dark`. A list naming only the legacy
   functions is a list that gets walked around with `oklch()`; the fixture proves that case.
3. **The exemption is THREE rules, not two.** AC 6 asked for a reason if it exceeded two: the
   third is `color-named`, which exists only because of widening (1). C9 proves it is still
   narrow — every other standard rule, including two formatting rules, stays live on the token
   file.
4. **AC 12 is enforced in BOTH stylelint and the guard**, where the story's source-tree table
   put it only in `token-usage.test.ts`. Neither layer alone is sufficient: stylelint runs on
   every `npm run lint` over every stylesheet but provably cannot see `animation: pulse 2s 3`
   (C7); the guard can, but only runs under vitest. Both ship.
5. **`--tracking-display` is a token.** The story's inventory table showed display's
   `letter-spacing: -0.02em` as a raw declaration rather than a named token, while giving
   `--tracking-label`/`--tracking-micro` names. It comes from the same frontmatter key as its
   two siblings and is asserted by the fidelity test like them; a bare `-0.02em` in c2-6 would
   be drift no rule catches. Token count is therefore 64.
6. **One guard beyond the ACs: unknown token references.** `var(--shadow-rst)` resolves to
   nothing at runtime and passes every rule this story otherwise adds. Landmine 3 records that
   `no-unknown-custom-properties` is the obvious rule and is unusable (file-scoped); the
   cross-file resolution it lacks is ~10 lines in a file the story already creates.
7. **`auto` is allowed in the padding/margin value regex.** AC 5's letter is "the `--space-*`
   / gutter / panel-gap tokens only, permitting `0`". `auto` is the only way to centre a block
   and a token for it would be ceremony, so it ships and is exercised in `clean.css`. *(Added
   to this list at review — it was a real widening that the list's own "none silent"
   convention had quietly skipped.)*
8. **Six more families added by review**, three of them Brad's rulings: the literal-duration
   ban on `transition`/`animation` and their duration/delay longhands; `text-shadow` and
   `drop-shadow()` joining the elevation ban; the category-prefix requirement on every value
   regex; the native-CSS-nesting ban; and the ESLint inline-`style` ban. Each is a gate the
   ACs did not ask for, each closes a hole a component could have walked through, and each is
   proven both ways.

**AC 9 is mechanism + review, and says so.** `stepsExactlyOne()` is unit-tested in both
directions (legal step, two-level skip, three-level skip, standing still, going backwards) and
`token-usage.test.ts` pins the ordered data to the tokens themselves. What is **not**
automated is whether a given component passes its real parent — a component's parent is chosen
in TSX at runtime and cross-file nesting depth is not statically decidable. AC 10 **is** a real
guard. The two are not equally enforced and the code comments say which is which.

**Two decisions later stories inherit.** A partly-tokenised shadow (`0 0 0 1px var(--accent)`)
**fails** — the geometry is still hard-coded and a shadowless theme cannot reach it, which is
the same hierarchy inversion AC 4 exists to prevent. The answer for c4-4's live ring and
c4-5's pinned ring is therefore **add a token to the layer**, never inline it and never declare
it locally (AC 2 forbids the latter outright). This is documented in `ui/README.md` so the
first author to hit it finds the answer rather than the gate.

**Not done, deliberately:** no component, no font file, no route, no Python, no runtime
dependency. `src/App.css` is still a placeholder — a tokenised one.

**Unverified by design:** node 24 locally vs node 20 in CI. Per gotcha 6 and c2-2's precedent,
drift on an unmodified tree is a finding to raise, **not** a reason to loosen a check.

### File List

**New**

- `ui/src/styles/tokens.css` — the 64-token layer + the reduced-motion registration point
- `ui/src/styles/surfaces.ts` — ordered ramp + `stepsExactlyOne` / `nextSurface` / `surfaceVar`
- `ui/src/styles/surfaces.test.ts` — the ramp predicate, both directions
- `ui/tests/tokens.test.ts` — DESIGN.md fidelity, the inventory, and the normalisers themselves
- `ui/tests/token-usage.test.ts` — the four guards stylelint cannot express
- `ui/tests/fixtures/css/literals-violation.css` — the firing half of the literal bans
- `ui/tests/fixtures/css/motion-violation.css` — the firing half of the no-loop ban
- `ui/tests/fixtures/css/token-usage-violation.css` — the firing half of the three guards

**Modified**

- `ui/.stylelintrc.json` — four rule families with regex property keys + the path-scoped override
- `ui/src/index.css` — token import first; dark-only baseline on tokens; forward-dated line repaired
- `ui/src/App.css` — `2rem`/`0.5rem` → tokens; forward-dated line repaired
- `ui/tests/fixtures/css/clean.css` — tokenised, and extended to prove every legal form
- `ui/tests/fixtures/css/violation.css` — forward-dated line 9 repaired (comment only)
- `ui/tests/lint-gates.test.ts` — six new assertions, per fixture, by rule name and count
- `ui/README.md` — *The token layer* section; line 108 repaired; *Not here yet* updated
- `ui/package.json` — `yaml` devDependency + its `"//"` note
- `ui/package-lock.json` — `yaml@^2.9.0`
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status transitions

**Regenerated (AC 14)**

- `src/companion/app/static/` — `index.html`, `assets/index-D4fjNB-l.css`, `assets/index-BgTdKi7o.js`
- `plugin/server/src/companion/app/static/` — the same four files, mirrored

**Scope proof (AC 18):** `git diff --cached --stat HEAD -- "*.py" "pyproject.toml" "uv.lock"`
is **empty**. Nothing under `src/` changed except the regenerated bundle.

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-07-27 | 0.1 | Story contexted from epic + DESIGN.md/EXPERIENCE.md; six landmines measured at `26a9fdf` | Bob (SM) |
| 2026-07-27 | 1.1 | Review patches: 14 of 14 applied, 1 deferred to c2-5. Three new gate families by Brad's ruling (literal durations, CSS nesting, inline `style`), plus category-prefix value regexes, `text-shadow`/`drop-shadow()`, and comma-aware + numeric parsing in both animation layers (the High finding). Six probes, all reverted; one invalidated my own earlier proof and was replaced rather than re-asserted. Suite 124 → 140. | Amelia (Dev) |
| 2026-07-27 | 1.0 | Implemented. 64-token layer + 4 literal-ban families (regex property keys) + 5 guards, each proven both ways. All 5 open questions answered "as proposed" before Task 0. Frontend suite 78 → 124 (9 → 12 files); Python unchanged at 1,753. Eleven evasion probes run and reverted, each verified landed first. Three unpredicted landmines (`import-notation: url`, `*/` inside `ui/**/*.css` closing a CSS comment, `hue-degree-notation: angle`) and six flagged widenings recorded. | Amelia (Dev) |
