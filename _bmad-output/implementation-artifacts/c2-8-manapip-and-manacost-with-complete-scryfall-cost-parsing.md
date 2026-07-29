---
epic: c2
story: c2-8
work_branch: feat/companion-c2
story_branch: feat/companion-c2-8-mana-pip-and-cost
depends_on: none — c2-7 (PR #24) is merged into the umbrella at 23f790c
baseline_commit: 1be0c60
---

# Story C2.8: ManaPip and ManaCost with complete Scryfall cost parsing

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad reading a card's cost anywhere in the app,
I want every symbol in a mana cost rendered,
so that a cost is never quietly wrong — and never looks like a Wizards mana symbol.

**What this story really is.** c2-7 wrote the first component library — four primitives whose whole
contract is *render your props*. This is the fifth and sixth primitives, and it is the first one in
the whole feature with a **real algorithm** inside it: a parser over an external string format that
this repo already holds 32,318 examples of. Every other component in Epic C2 can be wrong only in
how it looks. **This one can be wrong in what it says** — and the epic's own AC names the failure
mode: *silent dropping is what makes a cost wrong without looking wrong*.

That failure mode is not hypothetical, because **the composition reference ships it**. The mock's
`ManaCost` is one line:

```js
const parts = String(cost).match(/\d+|[WUBRGC]/gi) || []
```

Measured against this repository's own card database, that line renders `{W/U}` as **two separate
pips**, `{2/R}` as a 2 and an R, `{B/P}` as a black pip with the Phyrexian half silently gone, and
`{X}`, `{S}`, `{L}`, `{D}`, `{Y}`, `{Z}` and `{HW}` as **nothing at all** — a cost that renders,
looks fine, and is wrong. Do not copy it; the epic AC exists because of it.

The second thing this story is: **the first and only consumer the `mana-*` tokens have ever had.**
Measured — `git grep -- '--mana-'` over `ui/` returns **seven hits, all of them the declarations in
`tokens.css`**. UX-DR7's "WUBRG tokens are data ink only, never a button, border, background or an
unstacked curve bar" has been enforced by **nothing** for four stories. This story writes the first
consumer *and* the gate, in the same commit, before c4-8's curve segments and c4-9's colour bar
arrive to test whether the rule was ever real.

**Nineteen things were measured on this machine at `1be0c60` — do not rediscover them.**

### The data (measured against the shipped card database, 38,261 cards)

1. **The real symbol inventory is 61 distinct symbols, not seven letters and some digits.** Queried
   over every non-empty `mana_cost` in `%LOCALAPPDATA%\artificial-planeswalker\cards.db` (32,318
   costs). The full inventory, by frequency:

   | Family | Symbols seen | Notes |
   | --- | --- | --- |
   | Colour | `{W} {U} {B} {R} {G}` | ~8.3k each |
   | Generic | `{0} {1} … {16}`, and **`{1000000}`** | Gleemax. Seven digits. |
   | Colourless | `{C}` (46), `{X}` (612) | |
   | Hybrid, two colours | `{W/U} {U/B} {B/R} {R/G} {G/W} {W/B} {U/R} {B/G} {R/W} {G/U}` | all ten pairs present |
   | Generic hybrid | `{2/W} {2/U} {2/B} {2/R} {2/G}` | |
   | **Colourless hybrid** | `{C/W} {C/U} {C/B} {C/R} {C/G}` | Ulalek, Fused Atrocity |
   | Phyrexian | `{W/P} {U/P} {B/P} {R/P} {G/P}`, **`{C/P}`** | Kozilek, Compleated |
   | **Three-part hybrid Phyrexian** | `{R/W/P} {G/U/P} {G/W/P} {R/G/P}` | Nahiri, the Unforgiving |
   | Snow | `{S}` | Icehide Golem, Arcum's Astrolabe |
   | Un-set / recent | `{HW}` (Little Girl), `{Y}` `{Z}` (The Ultimate Nightmare…), `{L}` (Keeper of the Crown), `{D}` (Boulder Jockey) | |

   **The epic's AC names four cases — braces, hybrid, Phyrexian, `{X}`. The data has nine
   families.** Three-part hybrid Phyrexian and colourless hybrid are both real and both break a
   parser that assumes a `/` splits a symbol into exactly two colours.

2. **338 costs are NOT brace-only — they carry a ` // ` separator**, and up to **five** parts:
   `Who // What // When // Where // Why` is `{X}{W} // {2}{R} // {2}{U} // {3}{B} // {1}{G}`. A
   tokeniser written as `cost.match(/\{[^}]*\}/g)` drops the separator and renders a five-part
   split card as one run-on cost. There is **no other** non-brace content in the whole table —
   measured: every non-brace run in every cost is either whitespace or exactly `//`.

3. **`mana_cost` is never NULL in this database — 5,943 cards carry the empty string** (lands).
   The "absent cost" case AC 4 names arrives as `''`, not `null`, from this repo's own data — but
   the wire type c3-2 will generate may still be nullable, so handle `undefined`, `null` and `''`
   identically rather than picking one.

4. **Every stored cost is uppercase** (measured: zero rows where `mana_cost <> upper(mana_cost)`).
   Match case-insensitively anyway — the parser's input is a string, and a lowercase `{w}` costs
   nothing to accept and is one fewer way to be silently wrong.

5. **The widest inputs:** `{1000000}` is seven glyphs in one symbol, and B.F.M. is **fifteen pips**
   in one cost (`{B}` × 15). A pip whose width is pinned equal to its height cannot hold the first,
   and a `ManaCost` that does not wrap cannot hold the second inside a 452px right column.

### The gates (measured on a probe stylesheet under the real config, then deleted)

6. **`font-size` still has no legal spelling — including a percentage.** Measured: `font-size: 62%`
   is a `declaration-property-value-allowed-list` ERROR. **The mock's pip numeral is
   `fontSize: size * 0.62`**, so the one declaration its geometry is built on is unavailable, in
   exactly the shape c2-7's StatChip hit. `font-weight` is the same family and equally banned, so
   **the mock's `fontWeight: 700` numeral is unavailable too** — 500 (`--type-numeric`,
   `--type-label`) is the heaviest weight the token layer carries.

7. **A custom property declared in a component stylesheet is a GUARD failure**, not a lint one:
   `findTokenDeclarationsOutsideTokenFile` (`tests/token-usage.test.ts:231`) matches any
   `--name:` in any block outside `tokens.css`. So the obvious indirection —
   `.mana-pip-w { --pip: var(--mana-w) }` then `background: var(--pip)` — is banned, and the
   inline escape (`style={{ '--pip': … }}`) is an ESLint error with no hatch. **One class per
   colour, each naming its own token directly.**

8. **`linear-gradient()` and `conic-gradient()` lint CLEAN.** Measured. `function-disallowed-list`
   names colour functions and `drop-shadow` only, so a hard-stop two-colour gradient is available
   for the split hybrid pip and needs no gate change. (This is the opposite of c2-7's `color-mix()`
   situation — check before assuming the ban is wider than it is.)

9. **These all lint clean and carry no px literal:** `width: 1.25em`, `height: 1.25em`,
   `min-width: 1em`, `aspect-ratio: 1`, `line-height: 0`, `text-align: center`, `flex: none`,
   `border-radius: var(--radius-pill)`, `background: var(--mana-w)`, `color: var(--text-inverse)`.
   Measured together in one probe: **zero errors** beyond the deliberate `font-size` case.

10. **DESIGN.md HAS NO `components.mana-pip` ENTRY.** Measured — the frontmatter's `components.*`
    block declares `panel badge stat-chip card-tile dfc-flip quantity-badge deck-row group-header
    curve-bar color-bar card-detail legality-row nav-pill agent-view swap-row tier-row
    suggestion-row connection-pill state-panel card-placeholder skip-link footer-attribution`, and
    no mana anything. The prose (line 366) gives the *shape* — "a plain circle filled with the
    `mana-*` token, `{colors.text-inverse}` numeral inside for generic costs" — and **no size**.
    So the mock's `size = 16`, `size = 14` and `gap: 3` have **nothing truthful to cite**, and
    c2-6's citation gate (`tests/shell.test.ts:835`, live over every `src/components/**/*.css`)
    would demand a citation that cannot honestly be written. This is c2-7's `min-width: 76px`
    situation — except a pip must have a size. **Q1 decides; the recommendation makes the problem
    disappear rather than negotiating with it.**

11. **The label/micro companion guard applies the moment you use those roles.**
    `findRoleWithoutCompanions` requires `letter-spacing: var(--tracking-*)` **and**
    `text-transform: uppercase` in the same block for `--type-label` and `--type-micro`.
    `--type-numeric` has **no `--tracking-numeric` sibling**, so it requires only
    `font-variant-numeric: var(--type-numeric-features)` — the one role that can carry a single
    centred glyph without also carrying trailing tracking. Q2.

12. **The presentation-only suite is git-derived and will find your new modules automatically.**
    `tests/shell.test.ts:1017` asserts `git ls-files 'src/components/*.ts' 'src/components/*.tsx'`
    (minus test files) **equals** the `PRIMITIVES` list plus the shell — an exact-set equality, so
    every new module (`ManaPip.tsx`, `ManaCost.tsx`, the parser) **must** be added to `PRIMITIVES`
    with an **exhaustive** import list, and its `react` import must be **type-only**
    (`filled.ts` is the one named exemption). A parser module imports nothing and is listed
    `imports: []`, exactly as `Badge/tones.ts` is.

13. **`src/**/*.test.ts` runs in the dom project.** A pure-TS parser test at
    `src/components/ManaCost/parse.test.ts` is collected and type-checked; a `.test.tsx` under
    `tests/` is banned by `gate-geometry.test.ts`, and a test file outside `src/` and `tests/` is
    collected by neither project. The parser test belongs beside the parser.

14. **`git add` before running the guards.** `shippedStylesheets` and the `PRIMITIVES` coverage
    check are both built from `git ls-files`, so a new file is invisible — and passes vacuously —
    until it is staged. **Four stories in a row have lost time to this.**

15. **Baseline, measured at `1be0c60`:** frontend **308 passed / 19 files** (verified by running
    it); Python **1,753** (c2-7's number — Task 0 re-verifies rather than assuming). Working tree
    clean; `feat/companion-c2` level with `origin`.

### The two rules with teeth

16. **A Phyrexian Φ glyph is exactly what UX-DR7 bans.** "No symbol lookalikes" is not only about
    the pip's *shape* — reproducing the Phyrexian mana symbol, a tap symbol or a set symbol inside
    the pip is the same trade-dress imitation by another route. Whatever marks a Phyrexian symbol
    must be plain UI, not iconography. Q3.

17. **`aria-label` on a bare `<span>` does nothing.** ARIA prohibits an accessible name on
    `role="generic"`, which is what a `<span>` is; screen readers are permitted to ignore it and
    several do. A cost whose entire meaning is carried by **circle colour** is the exact shape
    UX-DR18 already ruled on for the colour-distribution bar ("colour is never the sole carrier"),
    and the epic's c2-8 block is silent about it. Q4.

18. **`overflow: hidden` on a pip would hide the defect rather than fix it.** A seven-digit
    `{1000000}` or an unknown `{HW}` inside a fixed-diameter circle clips, and clipping is the
    layout-shaped member of "silently wrong". The pip must **grow** — which a pill radius already
    supports, since a circle is a pill whose width equals its height.

19. **Nothing in this story is a c2-6 clip-ban or full-window concern**, and nothing here scrolls,
    is `position: fixed`, or owns the window. It is two spans and a pure function.

**What this story does not do.** It renders no deck, no card, no placeholder and no legend. It adds
no fetch, no store, no route, no endpoint, no Python. It does **not** fill the header badge slot
(c4-2/c4-10 own it), does not touch `AppShell.tsx`'s placeholder copy, and does not build the curve
(c4-8) or the colour bar (c4-9) that will be the `mana-*` tokens' second and third consumers — it
only leaves the gate that will judge them.

**A consequence worth stating before it looks like a mistake:** nothing imports `ManaPip` or
`ManaCost` in this story either, so — exactly as in c2-7 — **`npm run build` is likely to emit a
byte-identical bundle**. That is a prediction; AC 22 requires it be **measured**, not assumed.

## Acceptance Criteria

Epic-derived ACs are marked **[epic]**. The rest are requirements the epic's five blocks imply but
do not state; each says why it exists. An AC the epic did not write down is still an AC (standing
agreement: a story must leave the system working end to end).

### The two components

**AC 1 [epic].** **Given** a `ManaPip`, **when** it renders, **then** it is a **plain filled
circle** in the relevant `mana-*` token with an **inverse-coloured** (`--text-inverse`) numeral for
generic costs (UX-DR13) — **and** it is deliberately **not** a mana-symbol shape and carries no set
or planeswalker-symbol likeness (UX-DR7). No border, no inner ring, no glyph that could read as
WotC iconography (landmine 16).

**AC 2 [epic].** **Given** a Scryfall cost string containing braces, hybrid such as `{W/U}`,
generic-hybrid such as `{2/R}`, Phyrexian, and `{X}`, **when** `ManaCost` parses it, **then**
**every** symbol renders — hybrid as a split or dual-tinted pip (UX-DR13).

**AC 3 [epic].** **Given** a cost string containing a symbol the parser does not recognise,
**when** it renders, **then** the symbol is **surfaced visibly** rather than silently dropped
(UX-DR13) — **and** a unit test asserts this, because silent dropping is the failure mode that
makes a cost wrong without looking wrong.

**AC 4 [epic].** **Given** an empty or absent cost — a land, for instance — **when** `ManaCost`
renders, **then** it renders **nothing**, without error. All three spellings (`undefined`, `null`,
`''`) behave identically (landmine 3), and so does a whitespace-only string.

**AC 5 [epic].** **Given** the `mana-*` tokens, **when** their usage across the codebase is
inspected, **then** they appear **only as data ink** — pips, colour bars, stacked curve segments —
and **never** colour a button, border, background or an unstacked curve bar (UX-DR7). See AC 14 for
the mechanism; this is the AC that becomes a gate.

### The parser — where this story can actually be wrong

**AC 6.** **Given** the measured symbol inventory (landmine 1), **when** the parser is tested,
**then** its corpus covers **every one of the nine families**, named individually: colour, generic
(including `{0}` and `{1000000}`), colourless `{C}`, variable `{X}`, two-colour hybrid,
generic-hybrid `{2/R}`, **colourless hybrid `{C/W}`**, Phyrexian `{B/P}` and `{C/P}`, and
**three-part hybrid Phyrexian `{R/W/P}`**. *Why an AC: the epic names four cases and the data has
nine; a parser proven on the epic's four is proven on less than half of what the repository's own
database will hand it.*

**AC 7.** **Given** a split card's cost (`{2}{B} // {B}`, and up to five parts — landmine 2),
**when** it renders, **then** the ` // ` separator is **surfaced visibly** as a separator, not
dropped, and each part's symbols render in order. *Why: 338 rows in the shipped database look like
this, and AC 3's contract — never silently drop — covers non-brace content as much as braced.*

**AC 8.** **Given** the parser, **when** its shape is inspected, **then** it is a **pure module**
that (a) is **total** — it returns a token list for *every* string, throws for none, including
malformed input such as an unclosed `{W`, an empty `{}` and stray text; (b) tokenises by **scanning
the whole string**, so that anything not consumed as a recognised symbol is emitted as an *unknown*
or *text* token rather than skipped; and (c) is **case-insensitive**. *Why an AC: "never silently
drops" is a property of the tokeniser's structure, not of its symbol list — a `match()` of known
patterns drops the rest by construction, which is exactly the mock's defect. The rule is the
epic's standing one in parser form: **consume the whole input, never enumerate what you accept and
discard the rest**.*

**AC 9.** **Given** the parser's output, **when** a `ManaPip` renders from it, **then** a symbol's
**colours, its glyph slot and its Phyrexian-ness are separate fields** — `{R/W/P}` is two colours
plus a Phyrexian marker, not three colours (landmine 1), and `{C/P}` is one colour plus the marker.
*Why: a `split('/')` that treats every part as a colour renders `{R/W/P}` as a three-way split and
`{2/R}` as a colour named "2". Both are in the real data.*

### What the gates refuse, and what replaces it

**AC 10.** **Given** the pip's geometry, **when** it is written, **then** it introduces **no
uncitable px literal** — DESIGN.md declares no `components.mana-pip` at all (landmine 10), so any
`16px` here would meet c2-6's citation gate with nothing truthful to cite. Any px literal that does
ship carries a citation that is **true**; the recommended route (Q1) carries none at all.

**AC 11.** **Given** the pip's numeral, **when** it is written, **then** it comes from a **role
token plus its companions** — never `font-size`, never `font-weight`, never a new token (landmines
6, 11; the c2-7 decide-once ruling applied a second time, which is what makes it a ruling rather
than a one-off).

**AC 12.** **Given** the pip colours, **when** they are written, **then** each is a **class naming
its `mana-*` token directly** — no custom property declared in a component stylesheet (landmine 7,
a guard failure) and no inline `style` (an ESLint error). A colour the parser did not recognise
falls back to `--mana-colorless`, which is a real token, never to nothing.

**AC 13.** **Given** the mock's off-scale values, **when** the stylesheets are written, **then**
every spacing value comes from `var(--space-*)` (UX-DR5) — the mock's `gap: 3` becomes
`var(--space-1)` — **and** each snapped value carries a comment naming the mock value it replaces,
so a reviewer comparing against the composition reference sees a decision rather than a discrepancy
(the c2-7 precedent).

### The data-ink rule becomes a gate

**AC 14.** **Given** UX-DR7's "data ink only" (AC 5), **when** it is enforced, **then** a **guard**
in `tests/token-usage.test.ts` covers **both halves**, each proven firing **and** silent:

- **Which files may reference `--mana-*` at all** — an allowlist derived from `git ls-files`, whose
  entries each carry the reason they are data ink. Today that is `ManaPip.css` alone (measured:
  the tokens have **no other consumer in the repository** — landmine 13's sibling); c4-8's stacked
  curve segments and c4-9's colour bar join it **in the open**, in their own stories.
- **Which properties may spend one inside those files** — background/fill only. `border*`,
  `outline*`, `box-shadow`, `color` and every chrome property is a failure, **keyed by property
  family** rather than by an enumerated list, because "ban the family, never enumerate members" is
  this epic's standing review finding in four consecutive stories. *(Shipped and accepted at
  review as a stronger form than this AC's letter: a property **allowlist** — fill properties
  only — rather than a family ban; see the Q5 deviation in the Dev Agent Record. A future reader
  must not "restore" the family ban in good faith — the inline probe test exists to catch that.)*

**And** the half that is *not* statically decidable — whether a given curve bar is genuinely
stacked — is **declared in the guard's own comment as review's**, the way `surfaces.ts`'s
`stepsExactlyOne()` declares its half. *Why an AC and not a note: the tokens have existed since
c2-4 with a rule nothing checked. A rule with no consumer and no gate is a sentence.*

### Semantics and accessibility

**AC 15.** **Given** a rendered cost, **when** a screen-reader user reaches it, **then** the cost
carries an **accessible name** and its pips do not each announce themselves (landmine 17,
UX-DR18's precedent, UX-DR44). *Why an AC the epic did not write: the pip's entire meaning is its
fill colour, and "colour is never the sole carrier" is already a ruled requirement elsewhere in
this same design contract. See Q4 for the mechanism and the naming algorithm.*

**AC 16.** **Given** a multi-digit or unknown symbol (`{1000000}`, `{HW}`), **when** it renders,
**then** it is **not clipped** — the pip grows in width and stays pill-shaped rather than hiding
its content (landmine 18) — **and** a test asserts the wide case, because "it fits" is the claim
jsdom cannot check and eyes will not be on this component until c4-3.

**AC 17.** **Given** a long cost (fifteen pips — B.F.M., landmine 5), **when** it renders inside a
narrow container, **then** the row's wrapping behaviour is a **decided** property with a comment
saying which it is and why, not an accident of `display: inline-flex`.

### Boundaries, records and proof

**AC 18.** **Given** these are presentation-only primitives (EXPERIENCE.md line 77 lists
ManaPip/ManaCost among the five), **when** their implementation is inspected, **then** they hold no
state, call **no hook of any kind**, import no store, take no event-handler prop and expose no ref
— **and** every new module under `src/components/` is added to `PRIMITIVES` in `tests/shell.test.ts`
with an **exhaustive** import list and a **type-only** `react` import (landmine 12).

**AC 19.** **Given** the primitives introduce no motion, **when** the diff is inspected, **then**
there is no `transition` or `animation` in either stylesheet, **and** the record says so — *or*, if
one is added, it registers its fallback in the reduced-motion block in `tokens.css` (Decide-once
#3: a motion with no registered fallback is an incomplete story).

**AC 20.** **Given** this story writes the sixth primitive and the first parser, **when** it lands,
**then** `ui/README.md` records what later stories inherit: the data-ink rule and how to join its
allowlist (c4-8, c4-9 read this), the parser's totality contract, the accessible-name ruling, and
the new guard joins the ban table. **And** the one forward-dated sentence that names this story —
`ui/README.md:617` ("The remaining primitives are `ManaPip`/`ManaCost` (**c2-8**) and the nav pill
(**c6-8**)") — is repaired in the same commit, along with the *Not here yet* paragraph above it
(C1 retro homing rule).

**AC 21.** **Given** the components have **no on-screen consumer** in this story, **when** the
visual half is considered, **then** the record states plainly that appearance is **not**
dev-verified — jsdom renders nothing — and homes it: the pip's look is checked at its first
consuming story (**c4-3** card placeholders, **c4-7** deck row, **c4-9** colour-distribution
legend), with the epic manual-testing checklist carrying the entry. *This is the fifth story to
split an AC this way (c2-2 AC 17, c2-5 AC 4, c2-6 AC 4/5, c2-7 AC 21); do not fake it with a
`getComputedStyle` assertion.*

**AC 22.** **Given** any CSS or component change, **when** the story is committed, **then**
`cd ui && npm run build` runs and **both** the committed bundle and its `plugin/` mirror are
regenerated and committed if they change — and if the bundle is byte-identical (the prediction
above), the record says it was **measured**, not assumed.

**AC 23.** **Given** the dependency graph, **when** it is inspected, **then** this story adds **no
dependency, runtime or dev** (no mana-symbol font, no icon package, no parser library), and **no
token** — `tests/tokens.test.ts` and the `declaredTokens.size === 64` assertion are untouched.

**AC 24.** **Given** the scope, **when** the diff is inspected, **then** it touches no `.py` file
(except the regenerated mirror), no route, no store, no fetch layer, and none of the components
owned by c2-9, c2-10, c4-*, c6-8. `AppShell.tsx` is **unchanged**. `pyproject.toml`, `uv.lock` and
`package.json` are untouched. The Python suite is re-run to prove it stayed at **1,753**, not
assumed.

**AC 25.** **Given** every new guard and every parser branch, **when** the story claims done,
**then** each has been **probed with an input it does not enumerate** — a symbol family invented for
the probe, a `--mana-*` spent through a property the ban did not list by name — with the mutation
**verified on disk before the verdict is believed** (c2-4's lesson, c2-6's probe 10, c2-7's probe
10, all three of which found a real hole).

## Tasks / Subtasks

- [x] **Task 0 — verify the baseline before changing anything** (standing agreement)
  - [x] Branch off `feat/companion-c2` as `feat/companion-c2-8-mana-pip-and-cost`; confirm
        `baseline_commit` is `1be0c60`
  - [x] `cd ui && npm test` → expect **308 passed / 19 files**; `npm run lint`,
        `npm run format:check`, `npm run typecheck`, `npm run build` all exit 0
  - [x] Repo root: `uv run pytest -m "not integration"` → expect **1,753 passed / 1 skipped /
        45 deselected**. *If `test_list_decks_with_strategy_field` fails, it is the known
        `created_at`-tie flake — re-run before investigating.*
  - [x] `git status --porcelain -- src/companion/app/static/ plugin/` clean **after** a build, so a
        later drift is provably yours
  - [x] Record every number in the Dev Agent Record

- [x] **Task 1 — settle the decisions before writing anything** (Q1–Q6)
  - [x] Confirm Brad's answers to Q1–Q6 are in hand; if any is "not as proposed", re-read the ACs
        it touches before starting
  - [x] Write one probe stylesheet exercising the chosen pip geometry, the chosen numeral spelling
        and the chosen hybrid mechanism; `npm run lint` it; **delete it**. Measure before
        committing to a shape.

- [x] **Task 2 — the parser first, because it is the part that can be wrong** (AC 6, 8, 9)
  - [x] `src/components/ManaCost/parse.ts` — a total, case-insensitive scanner over the whole
        string; `git add` immediately (landmine 14)
  - [x] Token shape carries colours, glyph and phyrexian as **separate** fields (AC 9)
  - [x] `src/components/ManaCost/parse.test.ts` — the nine families by name (AC 6), the ` // `
        separator up to five parts (AC 7), the malformed cases (`{W`, `{}`, stray text, whitespace
        only, `''`/`null`/`undefined`), lowercase input, and **`{1000000}`**
  - [x] Pin the **exact** mock defect as a regression test: assert `{W/U}` yields **one** token,
        `{X}` yields **one**, `{B/P}` keeps its marker

- [x] **Task 3 — ManaPip** (AC 1, 10, 11, 12, 13, 16, 18)
  - [x] `src/components/ManaPip/{ManaPip.tsx, ManaPip.css, ManaPip.test.tsx}`; `git add`
        immediately
  - [x] One class per colour; pill radius; the glyph slot in the ruled role + companions
  - [x] The wide case (multi-digit, unknown text) grows rather than clips — asserted
  - [x] `npm run lint` after **every** block

- [x] **Task 4 — ManaCost** (AC 2, 3, 4, 7, 15, 17, 18)
  - [x] `src/components/ManaCost/{ManaCost.tsx, ManaCost.css, ManaCost.test.tsx}`
  - [x] Empty/null/undefined/whitespace → renders nothing (AC 4), asserted four ways
  - [x] The accessible name per Q4, with its formatter unit-tested beside the parser
  - [x] Unknown symbols visible (AC 3) — the epic's own named test

- [x] **Task 5 — the data-ink guard** (AC 5, 14)
  - [x] Non-vacuity anchor first: prove the guard is reading real stylesheets and that
        `--mana-*` has at least one real consumer, so an empty result cannot pass for silence
  - [x] Both halves — the file allowlist and the property-family ban — with the review half
        declared in the guard's own comment
  - [x] Cases into `tests/fixtures/css/token-usage-violation.css` (or a dedicated fixture, if the
        cross-file half needs one, as `accent-dim-cross-block.css` did); assert counts **per
        fixture file**, never in aggregate

- [x] **Task 6 — presentation-only registration** (AC 18)
  - [x] Add `ManaPip.tsx`, `ManaCost.tsx` and `parse.ts` to `PRIMITIVES` with exhaustive import
        lists; run `tests/shell.test.ts` and confirm the git-derived coverage check is **green
        because the list is complete**, not because the files are untracked

- [x] **Task 7 — records** (AC 20, 21)
  - [x] `ui/README.md`: the data-ink rule and how c4-8/c4-9 join the allowlist; the parser
        totality contract; the accessible-name ruling; the new ban-table row; repair `:617` and
        the *Not here yet* paragraph
  - [x] Add the visual-verification entry to `deferred-work.md`, homed to c4-3 / c4-7 / c4-9

- [x] **Task 8 — rebuild, mirror, prove** (AC 22, 23, 24)
  - [x] `npm run build`; `uv run python -m scripts.build_plugin`; **measure** whether either tree
        changed and record the answer either way
  - [x] Re-run all five frontend gates and the Python suite (expect **1,753**, unchanged)
  - [x] Scope proof: `git diff --stat` shows no `.py` outside the mirror, no `pyproject.toml`, no
        `uv.lock`, no `package.json`, no change to `AppShell.tsx`
  - [x] `git status --porcelain` clean

- [x] **Task 9 — probe the evasions before claiming done** (AC 25)
  - [x] For each new guard, plant the evasion, confirm it is caught, revert, paste the output
  - [x] **Verify the mutation landed before believing the verdict**, and **read what landed on
        disk**
  - [x] Probe at least: `border: 1px solid var(--mana-r)` inside `ManaPip.css` (the property half);
        `--mana-g` referenced from `Badge.css` (the file half); `box-shadow`/`outline-color` as
        spellings the property ban does **not** list by name; the parser fed an **invented** symbol
        family (`{Q/W/E}`) to prove AC 3 is structural rather than an enumeration; a `ManaCost`
        given `'{W'` to prove totality
  - [x] **Ban the family, never enumerate members** — prove each guard with a spelling it does not
        list

### Review Findings

- [x] [Review][Decision] **RESOLVED — Brad ruled (a), 2026-07-29: solid-plus-glyph IS the ruling; recorded as the third documented deviation.** `{2/R}` generic-hybrid renders as a solid single-colour pip, not the split Q3 grouped it with — Q3's ruled text lists `{2/R}` among the two-colour symbols that get the hard-stop gradient ("a two-colour symbol (`{W/U}`, `{2/R}` — whose '2' is a glyph not a colour, `{C/W}`)"), but shipped `classify()` gives it `colours: ['r'], glyph: '2'` → class `mana-pip-r`, a solid red pip reading "2", pinned by `ManaCost.test.tsx:32`. Scryfall's real symbol is a split (2-half / colour-half). Q3's own sentence is internally ambiguous and the resolution was made silently — the Dev Record documents deviations for Q1 and Q5 only. Decide: (a) solid-plus-glyph IS the ruling → record it as the third documented deviation, or (b) generic-hybrid renders the split gradient with the "2" glyph — needs the five `2/colour` gradient classes.
- [x] [Review][Patch] ManaCost never proves it forwards colours to its pips — change `token.colours` to `[]` at `ui/src/components/ManaCost/ManaCost.tsx:72` and all 383 tests stay green while every cost renders colourless; the exact "wrong without looking wrong" class this story exists to kill, one layer above the parser. Add a covering assertion. [ui/src/components/ManaCost/ManaCost.test.tsx]
- [x] [Review][Patch] False guard claim in a test comment — `ManaPip.test.tsx:51-52` says "the stylesheet answers it with min-width + a pill radius and no `overflow: hidden`, and ui/tests/token-usage.test.ts reads that source"; verified: token-usage.test.ts contains no read of min-width/overflow/geometry. The c2-7 StatChip failure mode (a comment claiming a check that doesn't exist), named twice by this spec. Add the source-read assertion or correct the comment. [ui/src/components/ManaPip/ManaPip.test.tsx:51]
- [x] [Review][Patch] The data-ink guard scans tracked `.css` files only — `fill="var(--mana-r)"` as an SVG presentation attribute in TSX (not an inline style, so not the ESLint ban) or `--mana-*` in index.html meets neither half; c4-8/c4-9 draw charts where SVG fill is the natural spelling. Extend the scan to non-CSS tracked files for `var(--mana-` (note: ManaPip.tsx's doc comment quotes the mock's `'var(--mana-' + color + ')'` and must not trip it) or declare the residual in the guard's limitations comment. [ui/tests/token-usage.test.ts:47]
- [x] [Review][Patch] `classify()` silently canonicalises garbage into plausible symbols — `{W/W}` is accepted (renders as plain white, announces "white or white"), `{P/W}` (marker-first, never written by Scryfall) and `{U/2}` accepted as valid. The module's own `{P/P}` philosophy says not-real-data falls to `unknown`; make duplicate colours unknown and add tests. [ui/src/components/ManaCost/parse.ts:110]
- [x] [Review][Patch] Whitespace edge family — `ManaPip label=" "` passes the decorative check (`label === ''` only) → `role="img"` with a blank name (ManaPip.tsx:80); `{ }` yields a space glyph and a whitespace piece surviving into the accessible name (parse.ts:93, :243). Trim the label and the unknown glyph/pieces. [ui/src/components/ManaPip/ManaPip.tsx:80]
- [x] [Review][Patch] Runtime non-string cost throws — a number from untyped wire JSON reaches `cost.trim()` and throws despite the totality contract. One-line `typeof cost !== 'string'` guard. [ui/src/components/ManaCost/ManaCost.tsx:55]
- [x] [Review][Patch] The split-card ordering assertion proves nothing about order — `expect(container.textContent).toBe('2 // ')`: both `{B}` pips contribute empty text, so dropped/duplicated/reordered colour pips pass. Assert the node sequence. [ui/src/components/ManaCost/ManaCost.test.tsx:65]
- [x] [Review][Patch] Hybrid gradient discards written colour order and the deviation is unrecorded — `{R/W}`/`{G/W}`/`{G/U}` canonicalise to WUBRG classes so the second-written colour paints first, while `describeManaCost` preserves written order ("red or white" over a white-first gradient); Q3's formula named `--mana-a`/`--mana-b` in symbol order. The 15-class economy is defensible — record it as a deviation and fix the parse.test comment advertising an order the renderer discards. [ui/src/components/ManaPip/ManaPip.tsx:72]
- [x] [Review][Patch] Dev Record scope proof says "13 files"; `git diff --stat` vs `1be0c60` is 15 (story record + sprint-status.yaml are the extras). Substantive AC 24 constraints hold; correct the number. [story file, Completion Notes]
- [x] [Review][Patch] Records sweep (5 small items): ManaCost.test.tsx:7 says "never by class name" while `pipText` uses `.mana-pip` selectors — add the carve-out note ManaPip.test.tsx has; the guard's limitations comment doesn't declare the chrome-through-an-allowed-property-in-an-allowlisted-file residual; AC 14's text still mandates the family ban the shipped allowlist superseded — annotate; `--mana-gold` (tokens.css:102) has no class, no consumer, no allowlist future and no mention anywhere — the four-story limbo this story condemns, applied to one-seventh of the family; ManaPip.css's arithmetic header never notes the glyph's 18.2px line box exceeds the 16.25px pip (a vertical-centring hazard with no CSS fix available, since line-height is banned). [multiple]
- [x] [Review][Patch] For sighted colour-vision-deficient users, colour is the sole carrier — a `{W}` and `{G}` pip differ in nothing but fill; the aria-label serves AT users only. DESIGN.md's plain-circle ruling may compel this, but it is unhomed: add it to the deferred-work entry / c4-3 manual eye-check so it is a decision on record, not an omission. [_bmad-output/implementation-artifacts/deferred-work.md]

## Dev Notes

### Decide-once rulings this story sets (c4-3, c4-7, c4-8, c4-9 and c6-8 inherit)

1. **How `mana-*` data ink is policed** (AC 14, Q5) — the allowlist c4-8 and c4-9 will join, and
   the property families they may spend a token through.
2. **How a colour-only graphic is announced** (AC 15, Q4) — the answer c4-8's curve and c4-9's
   colour bar reuse instead of each inventing one.
3. **How a component sizes itself when DESIGN.md gives it no geometry** (AC 10, Q1) — the third
   member of the family after c2-6's cited geometry literals and c2-7's uncitable `min-width: 76px`.
4. **What "never silently drop" means structurally** (AC 8) — scan the whole input; anything not
   recognised becomes a visible token. c3-*'s response handling and c5-*'s envelope parsing meet
   the same shape.

### The four things this story inherits and must not break

- **The token layer is complete and closed.** 64 tokens, asserted by count *and* byte-for-byte
  against DESIGN.md. No new token in this story — not `--mana-pip-size`, not `--type-pip`.
- **The typography ban is total.** `font`, every `font-*` longhand, `line-height`,
  `letter-spacing`, `word-spacing` and `text-indent` accept only the role/family/tracking tokens
  (plus `0` and the CSS-wide keywords).
- **c2-6's citation gate runs over every component stylesheet.** Every `\d+px` needs `DESIGN.md`
  within 60 characters of it, in a comment, in the same file — and for this component there is
  nothing truthful to cite (landmine 10).
- **The gates are cheap.** `npm run lint` is ESLint **and** stylelint in one script. Run it after
  every block.

### The composition reference is a source of arrangement, not of values

`imports/claude-design/_ds/_ds_bundle.js` implements both components. Read it for arrangement;
every value in it has been checked and the following are **drift** — reproduce none of them:

| Mock | Why it is drift | What ships |
| --- | --- | --- |
| `match(/\d+\|[WUBRGC]/gi)` | drops hybrid, Phyrexian, `{X}`, `{S}`, `{C}` variants and `//` — measured against the real DB | AC 8's total scanner |
| `fontSize: size * 0.62` | `font-size` is banned, percentages included (measured) | AC 11's role token |
| `fontWeight: 700` | `font-weight` is banned; 500 is the heaviest token weight | the role's own weight |
| `size = 16` / `size = 14` props | inline-style geometry; and DESIGN.md declares no pip size to cite | Q1's ruling |
| `gap: 3` | off the 4/8/12/16/24/32/48 scale (UX-DR5) | `var(--space-1)` |
| `borderRadius: 999` | literal radius, banned | `var(--radius-pill)` |
| `'var(--mana-' + color + ')'` string-built token | a bad colour name yields an unknown token that renders **nothing** (`findUnknownTokenReferences` cannot see a runtime-built name) | AC 12's one class per colour |
| every value as inline `style={{…}}` | ESLint error | a `.css` file |

### Previous story intelligence (c2-7, PR #24, Greptile **5/5 at round 1** — the epic's first)

- **The review theme, five stories running: a guard proven only against the spellings it lists.**
  c2-7's probe 10 passed — `--accent-dim` on `.badge-accent` with no `--surface-overlay` in the
  *same block* — and the repair was to widen the rule one scope, from same-block to same-file.
  **This story's equivalent is visible in advance**: AC 14's property ban must be keyed on the
  property *family* (`/^border/`, `/^outline/`, `/shadow$/`) and proven with a property it does
  not name.
- **The headline defect of c2-7's review was a declaration that was never written**, behind a
  comment claiming it was: StatChip shipped **no padding at all**. Nothing caught it — it lints
  clean, jsdom is blind, and there was no consumer. **This story has the identical exposure**
  (AC 21). Read your own stylesheets against your own comments before claiming done.
- **A probe that passes is information, not a formality.** Expect one of yours to pass and treat
  it as a finding.
- **`filled()` exists at `src/components/filled.ts`** for empty-node decisions and cost two review
  rounds plus a Greptile round to get right. If `ManaCost`'s empty case needs one, reuse it — and
  note that AC 4's emptiness is a *string* question, which `filled()` does not answer.
- **All six of c2-7's open questions were answered "as proposed" before Task 0** — six stories
  running. Q1–Q6 below are written to be answerable in one pass for the same reason.

### Git intelligence

`feat/companion-c2` is level with `origin` at `1be0c60`, working tree clean — **this story is not
blocked**. The house shape of the last four merges: implementation → review patches (message names
the theme) → PR round → merge → records. Conventional Commits, scope `companion`. The story PR
targets the **umbrella** with a Greptile pass; the per-epic integration PR gets none (standing
rule).

### Source tree — what exists, what this story adds

```
ui/
  README.md                        UPDATE  data-ink rule + allowlist protocol (AC 20); parser
                                           totality; accessible-name ruling; ban-table row;
                                           repair :617 and the Not-here-yet paragraph
  src/
    components/
      ManaPip/{ManaPip.tsx,.css,.test.tsx}       NEW
      ManaCost/{ManaCost.tsx,.css,.test.tsx}     NEW
      ManaCost/parse.ts                          NEW  the pure scanner
      ManaCost/parse.test.ts                     NEW  (dom project — src/**/*.test.ts)
  tests/
    shell.test.ts                  UPDATE  PRIMITIVES gains three modules (AC 18)
    token-usage.test.ts            UPDATE  the data-ink guard, both halves (AC 14)
    fixtures/css/…                 UPDATE  its cases
src/companion/app/static/          REGENERATED (probably byte-identical — measure)
plugin/…/static/                   REGENERATED
_bmad-output/implementation-artifacts/deferred-work.md  UPDATE (AC 21)
```

Nothing else. No `.py` logic, no route, no store, no `AppShell.tsx`.

### Gotchas specific to this story

1. **`cost.match(/\{[^}]*\}/g)` is the same defect one level up.** It keeps the braces and drops
   everything between them — including ` // `. AC 8 wants a scanner, not a matcher.
2. **`split('/')` treats `P` as a colour and `2` as a colour.** Both are in the real data (AC 9).
3. **A runtime-built token name is invisible to the unknown-token guard.** `var(--mana-${c})` in a
   template literal renders nothing for a bad `c` and no test can see it. One class per colour.
4. **`text-transform: uppercase` and tracking are forced onto `--type-label`/`--type-micro`.**
   `--type-numeric` carries no tracking sibling and is the one role that escapes (landmine 11).
5. **`git add` before running the guards** (landmine 14). Four stories running.
6. **jsdom renders no styles.** Every colour, fill and geometry claim reads CSS **source** in the
   node project, or goes on the manual checklist (AC 21).
7. **Component tests assert by ROLE and by TEXT**, not by class name (`getByRole('img', { name })`,
   `getByText('X')`). A class-name assertion proves nothing about what a user perceives.
8. **Do not add a mana-symbol font or icon set.** AC 23, and UX-DR7 bans "icon fonts styled as mana
   symbols" by name.
9. **`overflow: hidden` on a pip hides AC 16's defect.** Let it grow (landmine 18).
10. **The parser is the one place in Epic C2 where a unit test is the primary gate, not a
    secondary one.** Write it first (Task 2), and write it against the *measured* corpus, not
    against the epic's four examples.

### Testing standards

- vitest, two projects. **Component tests are `.tsx` and live in `src/`** (the `dom` project);
  a pure-TS `.test.ts` beside its module in `src/` is collected by the same project (landmine 13).
  Node-project gate and guard tests live in `ui/tests/`.
- Component assertions go through `@testing-library/react` **by role and text**, not by class name
  or test id.
- **Every new guard gets a proven pair** from one invocation, asserted by rule name and count where
  stylelint is involved, **per fixture file** (never in aggregate).
- **Non-vacuity anchor first** in any test that filters a list.
- Fixtures live in `tests/fixtures/`, are excluded from `npm run lint`, and are meant to stay
  broken.
- Python side: no new tests; re-run the suite to prove nothing moved.

### Architecture rules this story implements

- **UX-DR13** — ManaPip / ManaCost, and the complete Scryfall parse.
- **UX-DR7** — the two brand hard rules: no symbol lookalikes (landmine 16), and `mana-*` as data
  ink only (AC 5, AC 14).
- **UX-DR3** — the numeric role never travels alone; its fourth consumer.
- **UX-DR5** — every spacing value from the scale; the mock's `gap: 3` is drift.
- **UX-DR1** — every radius through a token.
- **UX-DR44 / UX-DR18** — colour is never the sole carrier (AC 15).
- **NFR-07** — the frontend gates are the enforcement mechanism.
- **FR-20** — the visual identity; this story ships its data vocabulary.

### References

- [epics-companion-app.md#Story-2.8](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  five AC blocks (lines 1437-1465)
- [epics-companion-app.md#UX-DR13](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  pip/cost spec (line 395); UX-DR7 (line 363); UX-DR18's colour-carrier precedent (line 434);
  UX-DR44 (line 590)
- [DESIGN.md](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md)
  — ManaPip/ManaCost prose (line 366), the WUBRG data-ink rule (line 275), the trade-dress hard
  rule (line 261), the do/don't table (lines 392-393), the `components.*` frontmatter (lines
  103-247 — **no mana-pip key**)
- [EXPERIENCE.md](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md)
  — the five presentation-only primitives (line 77); the colour-distribution accessible path
  (line 93)
- [_ds_bundle.js](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/imports/claude-design/_ds/_ds_bundle.js)
  — the mock's `ManaPip` (lines 310-338) and `ManaCost` (lines 340-364), read for arrangement only
- [c2-7 story record](_bmad-output/implementation-artifacts/c2-7-presentation-only-primitives-panel-badge-statchip-group-header.md)
  — the six decide-once rulings, the probe discipline, the StatChip-padding lesson
- [ui/tests/token-usage.test.ts](ui/tests/token-usage.test.ts) —
  `findTokenDeclarationsOutsideTokenFile` (231), `findRoleWithoutCompanions` (481),
  `findAccentDimInOverlayFile` (214, the file-scope widening this story's allowlist copies)
- [ui/tests/shell.test.ts](ui/tests/shell.test.ts) — the citation gate (819-871), the
  presentation-only suite and its git-derived coverage check (963-1060)
- [ui/README.md](ui/README.md) — the ban table (194-213), _Components_ (380-456), _The
  presentation-only primitives_ (457), _Not here yet_ (594-626, with :617 to repair)

## Open questions for Brad — answer before `dev-story`

Each carries a recommendation; "as proposed" on all six is a complete answer. Q1, Q3, Q4 and Q5 are
**decide-once rulings** later component stories inherit, which is why they are questions rather than
choices made in the implementation.

**Q1 — how big is a pip, given DESIGN.md declares no size and every `px` needs a citation?**
*Recommendation:* **em-relative, sized off the inherited font, with no `px` anywhere** —
`width: 1.25em; height: 1.25em; border-radius: var(--radius-pill)` (all measured lint-clean,
landmine 9). It sidesteps landmine 10 entirely rather than negotiating with it: there is no literal
to cite, so no citation can be untrue. It is also *better* than a fixed size — a cost in a
`--type-body` deck row and the same cost above a `--type-micro` placeholder caption should not be
the same 16px, and with `em` they aren't, for free and with no prop. Consequence to accept: a pip's
size becomes a property of its context, so a caller who wants a different size changes the
container's type role rather than passing a number — which is the presentation-only posture, not a
limitation of it. The alternative — a cited `16px` — is declined because the only honest citation
available is "the mock says 16 and DESIGN.md says nothing", which is precisely the citation c2-7
refused to write for `min-width: 76px`.

**Q2 — which role carries the glyph inside the pip?** *Recommendation:* **`font: var(--type-numeric)`
plus `font-variant-numeric: var(--type-numeric-features)`**, in the same block. Three reasons, in
order: it is the *numeric* role and these are overwhelmingly numbers (UX-DR3); at weight **500** it
is the heaviest the token layer carries, and the mock's `fontWeight: 700` has no legal spelling
(landmine 6), so legibility of a dark glyph on a mid-tone fill argues for the heavier of the two
candidates; and it is the **only** role with no `--tracking-*` sibling, so it does not drag
`letter-spacing` and a no-op `text-transform: uppercase` onto a single centred glyph (landmine 11 —
c2-7 already had to declare that no-op as a guard limitation once). The alternative, `--type-micro`,
reproduces the mock's exact 0.62 glyph-to-pip ratio and is otherwise fine; the tracking it forces
shifts a centred single digit by ~0.4px, which is immaterial, so this is a legibility-and-honesty
call rather than a geometry one. With Q1's `1.25em` pip, a 13px glyph sits in a ~17.5px circle at
body size.

**Q3 — how are hybrid and Phyrexian symbols drawn, without a WotC symbol lookalike?**
*Recommendation:* **a hard-stop two-colour gradient for the split, and the glyph slot for
everything else.** Concretely: a two-colour symbol (`{W/U}`, `{2/R}` — whose "2" is a glyph not a
colour, `{C/W}`) renders one pip with
`background: linear-gradient(135deg, var(--mana-a) 0 50%, var(--mana-b) 50% 100%)` — measured
lint-clean (landmine 8), one element, no colour function, no gate change. Phyrexian is a
**modifier, not a third colour** (AC 9), and is marked by putting **`P` in the same glyph slot the
generic numeral and `{X}` already use** — so `{B/P}` is a black pip reading "P", `{R/W/P}` is a
red/white split pip reading "P", `{S}` reads "S", `{X}` reads "X". This is the whole point of
landmine 16: **the glyph slot is a plain letter in the app's own typeface, and a Phyrexian Φ, a tap
symbol or any drawn iconography is the trade-dress imitation UX-DR7 bans by name.** It also makes
AC 3 fall out for free — an unrecognised `{HW}` is a colourless pip reading "HW", visible by
construction rather than by a special case. The alternative "dual-tinted" reading (a single blended
fill) is declined: blending needs `color-mix()`, which is banned, and a blend of two colours is a
*third* colour that names neither half.

**Q4 — how is a cost announced to a screen reader?** *Recommendation:* **`role="img"` with an
`aria-label` on the `ManaCost` wrapper**, its pips left as unlabelled decoration inside it (a
`role="img"` element's children are presentational, so nothing double-announces; `aria-hidden` on
the pips is belt-and-braces and harmless). This is required rather than stylistic: `aria-label` on
a bare `<span>` is **name-prohibited** on `role="generic"` and may be ignored outright (landmine
17). The label is built from the parsed tokens by a small pure formatter beside the parser and
unit-tested with it — `{2}{W/U}` → *"2 generic, white or blue"*, `{B/P}` → *"Phyrexian black"*,
`{X}` → *"X"*, `{HW}` → *"HW"* (unknown symbols read as their raw text, which is honest rather than
silent). A standalone `ManaPip` renders **decorative by default** (`aria-hidden`) with an optional
label prop, because c4-9's legend puts a pip beside its own text count and a doubled announcement
there is the flooding UX-DR45 warns about. This is UX-DR18's already-ruled "colour is never the
sole carrier", applied to the component that is nothing but colour.

**Q5 — how far does the data-ink guard reach, and how do later stories join it?**
*Recommendation:* **both halves as AC 14 describes, with the allowlist read from `git ls-files` and
each entry carrying its reason in a comment.** Today it is `src/components/ManaPip/ManaPip.css`
alone. c4-8 adds its stacked-segment stylesheet and c4-9 its colour bar, each in their own story
and in the open — which is the same protocol c2-7's `PRIMITIVES` list uses after review made it
git-derived. The property half bans `--mana-*` in any property whose name matches the border,
outline or shadow families plus bare `color`, keyed by family rather than by list. The half the
guard cannot decide — whether a curve bar is genuinely stacked — is declared in its own comment as
review's, the way `surfaces.ts` declares its half. The alternative, leaving UX-DR7 to review, is
declined for the reason the rule's own history gives: it has been review's for four stories and
review has never once had a consumer to look at.

**Q6 — what is the parser's output shape, and where does `//` go?** *Recommendation:* a
discriminated union of three kinds — `symbol` (carrying `colours: string[]`, `glyph: string | null`,
`phyrexian: boolean`, and the `raw` text), `unknown` (carrying `raw`, for a braced symbol whose
inner text matched nothing), and `text` (carrying `raw`, for anything outside braces, which in the
real data is only ` // ` and whitespace). Three kinds rather than two because `unknown` and `text`
render differently — one is a pill, one is inline text — and collapsing them would make the
separator render as a chip. `raw` is on every kind so the accessible-name formatter and any future
tooltip never have to re-derive it. The parser exports the union type and one function; it imports
nothing (`imports: []` in `PRIMITIVES`).

## Dev Agent Record

### Open questions — answered

**All six answered "as proposed", 2026-07-29 — the seventh story running.** What each became:

- **Q1 (pip geometry)** — `min-width: 1.25em; height: 1.25em; border-radius: var(--radius-pill)`,
  no `px` anywhere. **One correction, MEASURED rather than quietly applied:** Q1's rationale said
  the pip would size off the *inherited* font so a cost would be bigger in a body row than above
  a micro caption. `em` on width/height resolves against the **element's own** font-size, and the
  element carries `font: var(--type-numeric)` (13px), so the pip is **16.25px everywhere**. The
  alternative that would have recovered context-relativity — geometry on an unstyled parent, the
  role on an inner span — is *worse, not merely different*: a glyph's size comes from a role
  token and is therefore fixed at 13px, so a `--type-micro` caption would give a 12.5px circle
  around a 13px numeral. **A fixed glyph cannot live in a varying circle.** The mechanism Q1
  ruled (em, no literal, nothing to cite) ships intact; the arithmetic is written into
  `ManaPip.css`'s header and `ui/README.md` rather than left to be rediscovered.
- **Q2 (glyph role)** — `font: var(--type-numeric)` + `font-variant-numeric:
  var(--type-numeric-features)`, in the same block. No tracking companion is forced (the one role
  with no `--tracking-*` sibling), as predicted.
- **Q3 (hybrid / Phyrexian)** — hard-stop `linear-gradient(135deg, …0 50%, …50% 100%)`, one
  element, measured lint-clean. Phyrexian is a plain letter **`P`** in the same glyph slot the
  generic count, `{X}` and every unknown symbol use. No Φ, no icon font, no gate change.
  **Two deviations from Q3's letter, found unrecorded at code review and ruled on 2026-07-29:**
  (1) **`{2/R}` renders as a solid colour pip reading "2", not a split** — Q3's text grouped it
  with the gradient pairs while its own parenthetical ("whose '2' is a glyph not a colour")
  undercut that; **Brad ruled solid-plus-glyph is the intent** (the gradient formula needs two
  *colours*, and a numeral over a half-fill has no ruled contrast story). This is the story's
  **third documented deviation**. (2) The gradient **canonicalises the pair into WUBRG order**
  (15 classes serve 30 spellings), so `{R/W}`/`{G/W}`/`{G/U}` paint their second-written colour
  first while the accessible name keeps written order — Q3's `--mana-a`/`--mana-b` named symbol
  order. Recorded here and in `parse.test.ts`'s order test; the visual half is checked at c4-3
  with everything else.
- **Q4 (accessible name)** — `role="img"` + `aria-label` on the `ManaCost` wrapper; pips
  decorative (`aria-hidden`) by default with an opt-in `label` for c4-9's legend.
- **Q5 (data-ink guard)** — both halves shipped. **One strengthening beyond the recommendation:**
  the property half is an **allowlist** (`background`, `background-color`, `background-image`,
  `fill`, `stop-color`) rather than the family *ban* Q5 described. Rationale in the guard's own
  comment: "ban the family, never enumerate members" has a stronger form than a wider ban — a ban
  keyed on `/^border/`, `/^outline/`, `/shadow$/` is still a list its author thought of, and
  `caret-color`, `accent-color`, `text-decoration-color` and `column-rule-color` are not in it.
  Probe 3 confirms all three of those pass a ban list and fail this one.
- **Q6 (parser shape)** — the three-kind discriminated union as written, `raw` on every kind.

### Agent Model Used

claude-opus-5 (Claude Code, `/bmad-dev-story`)

### Debug Log References

**Task 0 baseline, measured at `1be0c60` by running it:**

- frontend `npm test` → **308 passed / 19 files** (matches the story's prediction)
- `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run build` → all exit 0
- Python `uv run pytest -m "not integration"` → **1,753 passed / 1 skipped / 45 deselected**
- `git status --porcelain -- src/companion/app/static/ plugin/` after a build → **clean**

**Task 1 probe stylesheet** (`src/components/probe.css`, written, linted, deleted): the ruled
geometry (`min-width: 1.25em`, `height: 1.25em`, `padding-inline: var(--space-1)`,
`border-radius: var(--radius-pill)`, `flex: none`), the numeral (`font: var(--type-numeric)` +
its companion), the hybrid mechanism (`linear-gradient(135deg, var(--mana-w) 0 50%,
var(--mana-u) 50% 100%)`) and the row (`flex-wrap: wrap`, `gap: var(--space-1)`,
`white-space: pre`) → **stylelint exit 0, zero errors**. Landmine 8 confirmed: `linear-gradient`
is clean.

**One prediction of my own measured WRONG and corrected in place** (Task 2): the five-part split
card `{X}{W} // {2}{R} // {2}{U} // {3}{B} // {1}{G}` is **ten** symbols, not the nine the test
was first written to expect. The parser was right; the assertion was wrong. Pinned at ten with a
comment saying it was measured, in the house style.

**Final gates** (after the rebuild and every probe reverted): frontend **383 passed / 22 files**,
Python **1,753 passed / 1 skipped / 45 deselected**, lint / format / typecheck / build all 0.

### Completion Notes List

**What shipped.** Two components, one pure parser and one new two-part guard. Frontend suite
**308 → 383** (+75: 33 parser, 11 ManaPip, 13 ManaCost, 18 guard/registration). Python
**1,753 → 1,753**, unchanged and re-run rather than assumed.

**AC 22 — the bundle prediction, MEASURED.** `npm run build` after every change emitted
`index-Dtvm20jX.js` and `index-yCpmQea7.css` — **the same content hashes as the baseline**, so
the bundle and its `plugin/` mirror are **byte-identical**. `git status` on both trees is empty
after a build and a `build_plugin` run. That is measured, not assumed: nothing imports either
component yet, so tree-shaking excludes them from the module graph entirely — the same outcome
c2-7 saw, confirmed rather than inherited.

**AC 21 — appearance is NOT dev-verified, and is not faked.** jsdom applies no stylesheet and has
no layout engine, so nothing here proves the pip is a circle, the gradient reads as a split, the
13px glyph is legible in a 16.25px circle, `{1000000}` grows into a pill rather than clipping, or
that fifteen B.F.M. pips wrap inside a 452px column. Every one of those is either read as **CSS
source** by a guard or homed to **c4-3 / c4-7 / c4-9** in `deferred-work.md` and the epic
manual-testing checklist. **The glyph-to-pip ratio (0.8, against the mock's 0.62) is the single
value most likely to want a nudge by eye** — flagged first in the deferred entry.

**The c2-7 lesson applied.** That story's headline defect was a declaration that was never
written behind a comment claiming it was (StatChip's missing padding). Both stylesheets here were
re-read against their own comments before this record was written; the class-coverage guard exists
precisely because that failure mode's local spelling — a `.mana-pip-uc` that lints clean and
renders a *transparent* circle — is invisible to every other gate.

**Nine evasion probes (AC 25), each planted, VERIFIED ON DISK, run, and reverted. All nine were
caught; none passed.** (c2-6, c2-7 and c2-4 each had one pass, so a clean sweep is itself worth
recording rather than assumed to mean the probes were good.)

| # | Evasion | Caught by |
| --- | --- | --- |
| 1 | `border: 1px solid var(--mana-r)` inside the allowlisted `ManaPip.css` | property half |
| 2 | `background: var(--mana-g)` in `Badge.css` — a **legal property**, so only the file half can see it | file half |
| 3 | `box-shadow`, `outline-color`, `caret-color` — three spellings the guard never names | property half (all three) |
| 4 | one of the 21 colour classes deleted from `ManaPip.css` | class-coverage guard |
| 5 | allowlist entry renamed to a path git does not track | non-vacuity anchor (3 tests) |
| 6 | the mock's own defect planted in `parse.ts` (non-brace runs discarded) | 7 tests across both suites |
| 7 | a new tracked module under `src/components/` missing from `PRIMITIVES` | git-derived coverage check |
| 8 | `useMemo` inside `ManaCost.tsx` | presentation-only hook-family check |
| 9 | `var(--mana-r, transparent)` — the **fallback** evasion this repo has been bitten by three times — through both halves at once | both halves |

Probes 2, 3 and 9 are the load-bearing ones: 2 proves the two halves are genuinely independent
rather than one catching everything; 3 is the whole argument for an allowlist over a ban list; 9
is the recurring evasion, closed because `referencedTokensIn` already anchors on `var(` rather
than on `)`.

**Scope (AC 23, 24), proved by `git diff --stat` against `1be0c60`:** 15 files (the review's
first count said 13 — measured again at 15: the story record and `sprint-status.yaml` are the
two it missed), no `.py`, no
route, no store, no fetch layer, no `AppShell.tsx`, no `pyproject.toml`, no `uv.lock`, no
`package.json`, **no new dependency and no new token** (`declaredTokens.size === 64` untouched).

**AC 19 — no motion.** Neither stylesheet contains a `transition` or an `animation`, so nothing
is owed to the reduced-motion registration point in `tokens.css`.

**Rulings later stories inherit** (all four recorded in `ui/README.md`, not only here): how
`--mana-*` data ink is policed and **how c4-8/c4-9 join the allowlist**; how a colour-only
graphic is announced; how a component sizes itself when DESIGN.md gives it no geometry; and what
"never silently drop" means **structurally** — scan the whole input, never enumerate what you
accept and discard the rest, which c3-*'s response handling and c5-*'s envelope parsing meet
again.

### File List

**New**

- `ui/src/components/ManaCost/parse.ts` — the total, case-insensitive scanner + `displayGlyph` + `describeManaCost`
- `ui/src/components/ManaCost/parse.test.ts` — 33 tests: nine families, ` // ` to five parts, malformed input, the mock's four pinned defects, the name formatter
- `ui/src/components/ManaCost/ManaCost.tsx`
- `ui/src/components/ManaCost/ManaCost.css`
- `ui/src/components/ManaCost/ManaCost.test.tsx` — 13 tests
- `ui/src/components/ManaPip/ManaPip.tsx`
- `ui/src/components/ManaPip/ManaPip.css` — 21 colour classes, no `px` literal
- `ui/src/components/ManaPip/ManaPip.test.tsx` — 11 tests

**Modified**

- `ui/tests/token-usage.test.ts` — the data-ink guard (both halves), the pip class-coverage guard, their non-vacuity anchors and firing halves
- `ui/tests/shell.test.ts` — `PRIMITIVES` gains the three new modules (6 → 9); suite heading widened past c2-7
- `ui/tests/fixtures/css/token-usage-violation.css` — five chrome cases and two legal fill cases
- `ui/README.md` — two ban-table rows; four new rulings sections; the `:617` forward reference and the *Not here yet* paragraph repaired
- `_bmad-output/implementation-artifacts/deferred-work.md` — four c2-8 entries
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status transitions

**Regenerated and measured byte-identical (so committed unchanged):**
`src/companion/app/static/`, `plugin/…/static/`

## Change Log

| Date | Version | Description | Author |
| --- | --- | --- | --- |
| 2026-07-29 | 1.1 | **CODE REVIEW → done.** Adversarial review (Blind Hunter + Edge Case Hunter + Acceptance Auditor): 1 decision + 11 patches + 4 dismissed, all resolved same day. **Brad's ruling:** `{2/R}` solid-plus-glyph is the intent — the third documented deviation (with the WUBRG gradient canonicalisation recorded as its rider). Patches: the colour-forwarding regression test ManaCost had no answer to (an all-grey cost passed the whole suite); the **markup half** of the data-ink guard (SVG `fill=`/`index.html` were invisible to both stylesheet halves — new fixture, firing + silent + non-vacuity proofs); the **grow-not-clip source read** that ManaPip.test.tsx's comment claimed existed and didn't (c2-7's StatChip failure mode, caught in a comment this time); `classify()` rejects duplicated colours (`{W/W}` no longer announces "white or white") while order-insensitivity (`{P/W}`, `{U/2}`) is pinned as deliberate; whitespace-only labels/glyphs trimmed out of the accessibility tree; a `typeof` guard so an untyped wire number cannot throw; the split-card order assertion strengthened to the child sequence; records corrected (13→15 files; AC 14 annotated with the shipped allowlist; `--mana-gold`'s no-consumer status documented; the 18.2px line-box arithmetic written into ManaPip.css; the CVD colour-sole-carrier trade-off homed to c4-3 in deferred-work). Suites **383 → 390** frontend, Python **1,753** re-run unchanged, all five gates green, bundle + mirror measured **byte-identical** again. | Claude (Review) |
| 2026-07-29 | 1.0 | **IMPLEMENTED → review.** Q1–Q6 all answered "as proposed" (seventh story running), with two things measured differently from their recommendations and written down rather than quietly applied: Q1's `em` geometry resolves against the pip's **own** font-size, so the pip is a stable **16.25px** rather than context-relative — and the alternative that would have recovered that is worse, because a fixed-size glyph cannot live in a varying circle; and Q5's property half ships as an **allowlist** (background/background-color/background-image/fill/stop-color) rather than the family ban it described, which is the strongest available form of this epic's own "ban the family, never enumerate members" finding. Shipped: a **total** Scryfall scanner (`parse.ts` — every string yields a list, nothing throws, and every character survives in some token's `raw`, asserted by re-joining), `ManaPip` (21 colour classes, **no px literal anywhere**, `min-width` + pill radius so `{1000000}` grows rather than clips), `ManaCost` (`role="img"` + a formatter-built name, wrapping decided), and the **first gate the `--mana-*` tokens have ever had** — both halves, plus a class-coverage guard that catches the local spelling of c2-7's StatChip-padding defect (a class that lints clean and renders a *transparent* circle). Suites **308 → 383** frontend, Python **1,753 → 1,753** re-run rather than assumed; all five gates green. **AC 22 measured, not assumed: the bundle and its `plugin/` mirror are byte-identical** (same content hashes as the baseline — nothing imports either component, so tree-shaking excludes them). **Nine evasion probes, all nine caught, none passed** — the load-bearing three being a legal-property reference in a non-allowlisted file (proving the two halves are independent), `box-shadow`/`outline-color`/`caret-color` (the whole argument for an allowlist), and the `var(--mana-r, transparent)` fallback this repo has been bitten by three times. One prediction of my own measured wrong and corrected in place: the five-part split card is **ten** symbols, not nine. AC 21 not faked — appearance is homed to c4-3 / c4-7 / c4-9 with the 0.8 glyph-to-pip ratio flagged first. | Amelia (Dev) |
| 2026-07-29 | 0.1 | Story contexted from the epic + DESIGN.md + EXPERIENCE.md + the composition reference — **and from the shipped card database**, which is what makes this story different from its five predecessors: the symbol inventory was **measured over 32,318 real mana costs** rather than taken from the epic's four examples, and it has **nine families, not four**. Three-part hybrid Phyrexian (`{R/W/P}`), colourless hybrid (`{C/W}`), `{S}`, `{HW}`, `{L}`, `{D}`, `{Y}`, `{Z}` and a seven-digit `{1000000}` are all real, and **338 costs carry a ` // ` separator with up to five parts**. The mock's one-line parser was run against that corpus and drops or mangles every one of them — which is the epic AC's stated failure mode shipping in the reference implementation. Nineteen landmines measured at `1be0c60`, four of them on a probe stylesheet under the real config: `font-size` is banned *including percentages* (so the mock's `size * 0.62` numeral has no spelling) and `font-weight` with it (so its bold has none either); a custom property declared in a component stylesheet is a **guard** failure, so the obvious `--pip` indirection is unavailable and each colour needs its own class; `linear-gradient()`/`conic-gradient()` lint **clean**, so the split hybrid pip needs no gate change; and **DESIGN.md has no `components.mana-pip` entry at all**, so every pip `px` literal would face c2-6's citation gate with nothing truthful to cite — c2-7's `min-width: 76px` problem, except a pip must have a size. Also measured: `--mana-*` has had **no consumer in the repository since c2-4**, so UX-DR7's data-ink rule has been enforced by nothing and this story writes both its first consumer and its gate. 25 ACs, 20 beyond the epic's five blocks. Six open questions homed with recommendations, four of them decide-once rulings — pip geometry expressed in `em` so the uncitable literal never exists, the glyph slot as the single answer to generic/`{X}`/Phyrexian/unknown (which is also what keeps a Phyrexian Φ out of a product whose brand rule bans symbol lookalikes), `role="img"` naming because `aria-label` on a bare span is name-prohibited, and the allowlist protocol c4-8 and c4-9 will join. AC 21 splits the visual half off as the fifth story to do so. Baseline measured by running it: frontend **308 passed / 19 files**, Python 1,753. Not blocked — c2-7 is merged at `23f790c`. | Bob (SM) |
