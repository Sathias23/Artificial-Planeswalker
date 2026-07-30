---
epic: c2
story: c2-9
work_branch: feat/companion-c2
story_branch: feat/companion-c2-9-state-panel
depends_on: none — c2-8 (PR #25) is merged into the umbrella at 8b27d46
baseline_commit: 109a7d9
---

# Story C2.9: The shared state panel and every system-state message

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad when something isn't ready,
I want a calm panel that tells me plainly what is happening and exactly what to do next,
so that I am never shown an error page or left guessing at a terminal command.

**What this story really is.** Every story in Epic C2 so far could be wrong in how it *looks*.
c2-8 was the first that could be wrong in what it *says* — about a card. **This one is the first
whose entire deliverable is words the user reads**, and the epic's own AC sets the bar at
`EXPERIENCE.md` **verbatim**. There is a mechanism for exactly that already in the repo:
`tests/tokens.test.ts` asserts the token layer against `DESIGN.md`'s frontmatter *by reading the
artefact itself*, not a copy of it. This story does the same thing to prose.

It is also the story that **finishes what four earlier stories left open**:

- `internal_error` — AD-16's sixth reason token, added by the c1-4 review ruling — **shipped with no
  UI state.** The C1 retro made that an open action item **owned by Brad and homed here** by name
  (`sprint-status.yaml:470`). `ui/src/api/types.d.ts:69` says it out loud: *"its state panel is
  written in Epic 2 (c2-9)"*.
- The **c1-6 corrupt-database ruling** — a durably corrupt `cards.db` answers `database_unavailable`
  on every request forever, which is the quiet-retry "Database updating" panel *with no repair
  path*. `deferred-work.md:716-720` calls it "a UX ruling for c2-9 to make with the state designs
  in hand."
- **`Panel`'s declared hole** — a `live` panel with no title keeps only its elevation change, which
  the graphite and ink themes flatten to nothing. `Panel.tsx:95` names this story as "the first
  consumer that can decide whether a title-less live panel exists."
- **`Panel`'s appearance has never been seen by a human.** `deferred-work.md:1316` homes the eye
  check *here* — which is only true if this story puts something on a screen. Q1.

**And there is no composition reference.** `DESIGN.md:348` states it explicitly: the imported mock
demonstrates sixteen components and **does not demonstrate the State panel**. c2-8 shipped with a
mock to read for arrangement and a drift table of eight values not to copy. This story has
neither — the spec prose is the whole source, and nothing can be checked against a picture.

**Nineteen things were measured on this machine at `109a7d9` — do not rediscover them.** Two of them
(18, 19) are measurements that make a decision *cheaper* than it looks; the rest are hazards.

### The copy and the contract

1. **`EXPERIENCE.md` writes each state in TWO fields; `DESIGN.md` renders THREE slots.** The copy
   table (`EXPERIENCE.md:61-71`) gives `Headline:` and `Body:` and nothing else. The panel spec
   (`DESIGN.md:384`, and the epic's AC 1) wants *headline*, *guidance body*, **and the concrete next
   action on its own line** in `--type-body-strong` `--accent`. **There is no separately-written
   next-action string anywhere in the design artefacts.** So either the copy is not verbatim, or the
   next-action line is carved out of the Body — and only one of those two is compatible with the
   epic's own AC. Q3 rules it, and the recommendation makes "verbatim" a checkable invariant rather
   than an aspiration.

2. **The command chip's source is already in the copy, and there is exactly one.** Measured over the
   four bodies: the only backticked run in any of them is `` `initialize_database` `` in the
   database-not-initialized body. So the monospace chip is **derivable from the copy** (render
   backticked spans as chips) rather than authored per state — which is also what keeps a fifth and
   sixth state's copy from needing a bespoke renderer.

3. **`internal_error` has no copy anywhere.** `EXPERIENCE.md`'s Voice-and-Tone table has nine rows
   and this is not one of them. Writing it is this story's, and it must be written **into
   `EXPERIENCE.md`** — otherwise the verbatim gate has no source for the fifth panel and quietly
   covers four of five. Q4 proposes the wording.

4. **Six reason tokens, five panels, and the two vocabularies are NOT the same set.** Measured
   against `ui/src/api/types.d.ts:56-69` and `schema.test.ts:41`:

   | Reason token | Panel |
   | --- | --- |
   | `deck_not_found` | **No-active-deck** (many-to-one — the SPA clears to it) |
   | `database_not_initialized` | **Card database not set up yet** |
   | `database_unavailable` | **Card database is updating** (quiet retry) |
   | `internal_error` | **the fifth panel** — deterministic, **must not** quietly retry |
   | `invalid_request` | **none, by design** — the SPA never generates one; it means a client bug |
   | `payload_too_large` | **none, by design** — surfaced to the *agent*, not to the glass |
   | *(not a token at all)* | **Disconnected / backend restarted** — a client-side condition |

   So a `Record<ErrorReason, Panel>` is the wrong shape twice over: two tokens must be allowed to
   map to *no* panel, and one panel has no token. The map must still be **total and exhaustive**, so
   that c3-2's seventh token (`card_not_found`) fails to compile rather than silently losing a
   state.

5. **`schema.test.ts:39` already names this story as the thing its assertion protects** — "a token
   dropped on the Python side reddens here instead of quietly deleting a c2-9 state panel". That
   pin exists; this story is what makes it load-bearing.

### The gates (measured under the real config at `109a7d9`)

6. **There is no monospace family, and none can be spelled.** Three measurements, all confirmed:
   `.stylelintrc.json` restricts `font-family` to `/^(var\(--font-[a-z0-9-]+\)|…keywords)$/` — so
   `font-family: monospace` is a lint ERROR; `tokens.css` declares exactly one family token
   (`--font-sans`); and `DESIGN.md`'s frontmatter contains **no mono family at all** (measured — every
   `fontFamily:` in it is the same Space Grotesk string), while `tests/tokens.test.ts:254` pins the
   token names at **64, byte-for-byte against that frontmatter**. **The one property the epic AC
   names by hand has no legal spelling.** This is the c2-7 `min-width: 76px` / c2-8 pip-size family
   for the third time — Q2.

7. **`480px` is citable, and it is the README's own prediction coming true.** `ui/README.md:231`
   already names "c2-9's 480px state-panel max-width" as an inheritor of the geometry-literal rule,
   and `DESIGN.md`'s frontmatter carries `components.state-panel.max-width: 480px` — so unlike the
   pip size, there *is* something truthful to cite. The gate is live over every component stylesheet
   (`tests/shell.test.ts:854`): the literal needs `DESIGN.md` within 60 characters of it, in a
   comment, in the same file. (Note the README's own correction beside it: the same list once named
   c2-7's 17px StatChip and that prediction was **wrong**. This one is right; say so.)

8. **The three roles this panel uses are the free ones.** `--type-heading`, `--type-body` and
   `--type-body-strong` have **no `--tracking-*` sibling** and are not declared uppercase, so
   `findRoleWithoutCompanions` (`tests/token-usage.test.ts:482`) requires nothing beside them —
   unlike `--type-label`/`--type-micro`, and unlike `--type-numeric`, which drags its
   `font-variant-numeric` companion. Nothing in this panel is numeric, so `findUnpairedNumericRole`
   does not fire either.

9. **A `--surface-well` chip inside a `--surface-panel` panel steps DOWN the ramp.**
   `stepsExactlyOne('surface-panel', 'surface-well')` is **false** — the predicate is directional on
   purpose. `DESIGN.md:384` specifies exactly that nesting for the command chip, and **StatChip
   already ships it** (`StatChip.css:32`, a well inside panels). A recess is not a skipped step; it
   is a hole rather than a nearer pane, which is what the ramp comment means. Say so in the
   stylesheet **before** review reads it as a UX-DR1 violation. (Adjacency is review's, not a gate —
   `surfaces.ts:10-16` declares that half honestly.)

10. **The copy gate cannot be repo-wide, and the measurement proves it.** `"something went wrong"`
    already appears **twice inside `ui/src`** — `api/openapi.json:90` and `api/types.d.ts:46` — in
    both cases *quoting the ban itself*, in generated files no author may hand-edit. And `!` is an
    operator in nine of the eleven modules under `src/components/`. **A naive ban on either string
    fails on the day it is written, against the wrong files.** The ban has to be keyed to
    user-facing copy — which means the copy has to live somewhere a guard can point at, *and* the
    guard has to prove no user-facing string escaped that place. That second half is the whole
    lesson of c2-8's data-ink guard (a property half is worthless without a file half).

11. **`PRIMITIVES` is an exact-set equality over `git ls-files`** (`tests/shell.test.ts:1038-1059`):
    every tracked module under `src/components/` must be listed with an **exhaustive** import list
    and a **type-only** `react` import. Hooks are banned **by API family**, and **`useId` is banned
    by name**, on the record, precisely so a primitive reaches for `aria-label` rather than
    `aria-labelledby` (`shell.test.ts:973-975`). So the panel's `role="region"` name comes from
    `aria-label`, exactly as `Panel` does.

12. **`git add` before running the guards.** `shippedStylesheets`, the citation loop and the
    `PRIMITIVES` coverage check are all built from `git ls-files`, so a new file is invisible — and
    passes **vacuously** — until it is staged. **Five stories in a row have lost time to this.**

13. **Baseline, measured at `109a7d9` by running it:** frontend **390 passed / 22 files**; Python
    **1,753** (c2-8's number — Task 0 re-verifies rather than assuming). Working tree clean;
    `feat/companion-c2` at `109a7d9`.

14. **Nothing in `ui/` implements a state panel; seven files forward-reference one.** Measured
    (`git grep -i 'state panel\|state-panel\|c2-9'`): `README.md:231,737,749`,
    `AppShell.css:11`, `AppShell.tsx:55`, `Panel.css:18`, `Panel.tsx:95`, `schema.ts:46`,
    `schema.test.ts:39`, `shell.test.ts:824`, `types.d.ts:68`. **Every one of them is a promise this
    story either keeps or must repair** (C1 retro homing rule). `ManaPip.css:13` also quotes
    `state-panel` — as a member of DESIGN.md's `components.*` list, not a reference; leave it.

18. **Wiring costs nothing in tests — measured.** `src/App.test.tsx` renders `<App />` and asserts
    only "exactly one `main`" and "an `h1` named Artificial Planeswalker"; `AppShell.test.tsx`
    renders `<AppShell />` **with its own props**, so its placeholder-owner sweep (`:105-133`, every
    story id appears in some placeholder) reads the component, not the app. **Q1's wiring therefore
    breaks neither file.** Do not let a fear of the placeholder sweep decide Q1 — it was measured,
    and the answer is that it does not apply.

19. **The deck list is a PROP, and the empty case is real.** `GET /api/decks` is **c3-1**'s; here the
    names arrive as `string[]`. A fresh install has **no decks at all**, so the empty array is the
    common case on day one, not an edge — it must render **nothing extra** (no empty `<ul>`, no
    header over nothing), which is the same emptiness question `filled()` was written for and cost
    c2-6 two review rounds plus a Greptile round to settle. **Reuse `src/components/filled.ts`; do
    not re-derive it.**

### The three rules with teeth

15. **"No error styling" is a *constructive* rule, not a review note.** `--negative` exists, and the
    single most natural thing to write for a 500 is a red panel. The epic bans illustration, icon,
    red fill, exclamation mark and error styling in one breath — and the one of those a machine can
    actually check is **the token**. A guard that fails on `--negative`/`--caution` inside this
    stylesheet is cheap and permanent; leaving it to review is how it arrives in c4-10 instead.

16. **The `internal_error` panel must not retry, and that is a property of the panel, not of the
    fetch layer that does not exist yet.** `types.d.ts:67-69` states it as a wire contract. This
    story ships no polling and no retry (there is no fetch layer until c3-1), so the requirement
    lands as an explicit **declaration** the wiring story is held to — written where c3-9 will read
    it, not only in this record.

17. **`aria-live` is not this panel's business, and adding it would be the defect.** UX-DR45's
    flooding warning and `EXPERIENCE.md:156`'s live-region inventory name three live regions — the
    connection pill, the agent-view heading, and the pin announcement. The state panel is **not**
    among them: it *replaces* the main surface, so a focus/landmark change carries it. A
    `role="region"` that is also `aria-live` would announce the whole panel on every mount.

### What this story does not do

It builds no fetch, no store, no polling, no retry, no reconnect and no route. It does **not**
implement FR-22's self-transition (**c3-9**), the connection pill (**c5-7**), the WebSocket
backoff that produces the disconnected condition (**c5-6**), the deck list the no-active-deck panel
will eventually show real names in (**c3-1**/**c4-2**), the footer (**c2-10**) or the skip-link
withdrawal (**c4-11**). It also does not implement `EXPERIENCE.md:119` — a state panel taking the
left column *while an agent view is open*, and the Tab stops withdrawn with the grid — which needs
the agent view (**c6-5**) and the keyboard floor (**c4-11**) to exist. It adds no dependency and
touches no `.py` file except the regenerated mirror.

**A consequence worth stating before it looks like a mistake:** unlike c2-7 and c2-8, this story
**probably does change the built bundle** — if Q1 is answered as recommended, something is imported
into `App.tsx` for the first time since c2-6, so tree-shaking no longer excludes it. That is a
prediction; AC 23 requires it be **measured**, not assumed, in whichever direction it lands.

## Acceptance Criteria

Epic-derived ACs are marked **[epic]**. The rest are requirements the epic's eight blocks imply but
do not state; each says why it exists. An AC the epic did not write down is still an AC (standing
agreement: a story must leave the system working end to end).

### The panel

**AC 1 [epic].** **Given** the `State panel` component, **when** it renders, **then** it is
**centred**, **max-width 480px**, on `--surface-panel` with a **hairline** border and the **large**
radius, carrying a **heading**, **guidance body copy**, and the **concrete next action on its own
line** in `--type-body-strong` `--accent` (UX-DR30) — **and** a command inside the next action
renders as a monospace-styled **inline chip on `--surface-well`** (Q2 rules how "monospace-styled"
is spelled, since landmine 6 says it currently cannot be).

**AC 2 [epic].** **Given** any system state, **when** its panel renders, **then** there is **no
illustration, no icon, no red fill, no exclamation mark and no error styling** (UX-DR30) — **and**
exactly **one** state panel shows at a time, occupying the **left-column area** while the right
column, header nav and footer remain functional around it. **The "exactly one" half is the
*caller's*, not the component's** — a presentation-only panel cannot know about its siblings — so it
is satisfied here by the shell's single `left` slot and by there being no manager to write, and the
component's doc comment says so rather than leaving the next author to build a state-panel
registry.

**AC 3 [epic].** **Given** the four system states, **when** their copy is inspected, **then** it
matches `EXPERIENCE.md` **verbatim** for no-active-deck, database-not-initialized, database-updating
and disconnected/backend-restarted (UX-DR33).

**AC 4 [epic].** **Given** the `internal_error` (500) reason token — added to AD-16's closed set by
the c1-4 review ruling (Brad, 2026-07-25), whose state panel is homed **here** — **when** the
backend reports an unhandled bug, **then** a **fifth** state panel renders with its own
EXPERIENCE.md-reviewed copy — **deterministic, so it must not quietly retry** the way
database-updating does; the concrete next action is restarting the companion / reporting the bug
(UX-DR30, UX-DR33).

**AC 5 [epic].** **Given** the no-active-deck state, **when** it renders, **then** it lists
available deck names beneath the guidance, **non-clickable** — no `<a>`, no `<button>`, no click
handler; the agent drives (UX-DR33, NG1) — **and** an empty or absent list renders **nothing extra**,
decided by `filled()` rather than by truthiness (landmine 19), because a fresh install has no decks
and an empty `<ul>` under a heading is the common day-one render.

**AC 6 [epic].** **Given** any copy anywhere in the app, **when** it is reviewed, **then** it is
second-person and terminal-literate, names commands and tools without apology, never blames, always
gives a concrete next action, and contains **no exclamation marks, emoji or mascot** (UX-DR33) —
**and** the string **"something went wrong" appears nowhere**. See AC 13 for the mechanism and for
why the check cannot be repo-wide (landmine 10).

**AC 7 [epic].** **Given** the panel is rendered, **when** its semantics are inspected, **then** it
is `role="region"` with its headline as an **`h2`** (UX-DR44) — named by `aria-label`, never
`aria-labelledby`, because `useId` is a banned hook (landmine 11, `Panel`'s precedent) — **and** it
carries **no `aria-live`** (landmine 17).

### Verbatim means checkable

**AC 8.** **Given** `EXPERIENCE.md` is the copy contract, **when** the shipped strings are gated,
**then** a test **reads `EXPERIENCE.md` itself** — the artefact, not a copy of it — and asserts every
state's headline and body **byte-for-byte**, in the shape `tests/tokens.test.ts` established for
`DESIGN.md` (one path constant, a loud named failure if the artefact moves, and a **non-vacuity
anchor** so an unparsed table cannot assert nothing over an empty object). *Why an AC: "matches
verbatim" reviewed by eye is the same claim as "the tokens match DESIGN.md" reviewed by eye, and
this repo already decided that one.*

**AC 9.** **Given** `DESIGN.md` renders three slots and `EXPERIENCE.md` writes two fields (landmine
1), **when** the copy is split, **then** the split is **invariant-preserving**: the guidance and the
next-action line **recombine to the EXPERIENCE.md body exactly**, asserted by the same test, so a
future edit to either half cannot drift from the artefact. *Why: the alternative is a next-action
line nobody wrote, which is the first sentence of user-facing copy in this product with no UX review
behind it.*

**AC 10.** **Given** the `internal_error` copy and (per Q5) any stalled-database copy do not exist
yet, **when** they are authored, **then** they are written **into `EXPERIENCE.md`'s copy table**, in
the same two-field shape, and the gate of AC 8 covers them with no special case. *Why: a fifth panel
whose copy lives only in TypeScript is a fifth panel with no contract — and the C1 retro action item
names EXPERIENCE.md copy specifically.*

**AC 11.** **Given** the command chip, **when** it renders, **then** it is derived from the copy's
own **backtick** markup (landmine 2) rather than authored per state — one mechanism, so the fifth
and sixth states need no bespoke renderer — **and** a copy string containing no backticks renders no
chip, without error.

### The state vocabulary

**AC 12.** **Given** the six reason tokens and the five panels are **not the same set** (landmine
4), **when** the mapping is written, **then** it is **total over `ErrorReason`** — so c3-2's seventh
token fails `npm run typecheck` rather than silently losing a panel — **and** it explicitly permits
"no panel" for `invalid_request` and `payload_too_large`, and carries the disconnected state, which
has no token at all. Exhaustiveness is proved by the **type** (a `satisfies Record<ErrorReason, …>`
or a `never`-checked switch), not by a test that enumerates today's six. *Why an AC:
`schema.test.ts:39` already declares this story the thing it protects.*

### The copy rules become a gate

**AC 13.** **Given** UX-DR33's copy rules (AC 6), **when** they are enforced, **then** a guard covers
**both halves**, each proven **firing and silent**, with a non-vacuity anchor:

- **Where user-facing copy may live** — every rendered string is in one copy module (or an
  enumerated, git-derived set of them), so the guard has something to point at. The other half of
  the c2-8 lesson applies verbatim: a rule half is worthless without a file half.
- **What that copy may not contain** — `!`, emoji, and `"something went wrong"` (case-insensitive),
  keyed by **character family** where possible rather than an enumerated list, because "ban the
  family, never enumerate members" is this epic's standing review finding in **five** consecutive
  stories.

**And** the guard is scoped so that the generated `openapi.json`/`types.d.ts` occurrences (landmine
10) and `!` used as an operator are **out of scope by construction** — not by a special case listing
today's two files. **And** the half that is not statically decidable — whether a sentence is
*second-person and blameless* — is declared **in the guard's own comment as review's**, the way
`surfaces.ts` declares its half.

**AC 14.** **Given** "no error styling" (AC 2), **when** it is enforced, **then** a guard fails on
`--negative` or `--caution` referenced from this component's stylesheet (landmine 15), proven with a
spelling it does not name — and, like every earlier token guard, on **`var(--negative, …)` with a
fallback**, the evasion this repo has been bitten by three times.

### Geometry, roles and the surface ramp

**AC 15.** **Given** `max-width: 480px`, **when** it is written, **then** it carries a **true
`DESIGN.md` citation** within a sentence of it (`components.state-panel.max-width`), satisfying the
live citation gate (landmine 7) — and no *other* px literal ships without one.

**AC 16.** **Given** the command chip sits on `--surface-well` inside a `--surface-panel` panel
(landmine 9), **when** the stylesheet is written, **then** the **downward** step is named in a
comment as a deliberate **recess** with `StatChip.css:32` as its precedent, so review does not read
it as a UX-DR1 violation.

**AC 17.** **Given** the type roles, **when** they are applied, **then** every one comes from a
**role token** — never `font-size`, never `font-weight` — and, per landmine 8, the three roles this
panel uses require **no companions**, which the stylesheet states rather than leaves to be
rediscovered.

### Boundaries, records and proof

**AC 18.** **Given** this panel holds no state in this story, **when** its implementation is
inspected, **then** it calls **no hook of any kind**, imports no store and no fetch helper, and
every new module under `src/components/` is added to `PRIMITIVES` in `tests/shell.test.ts` with an
**exhaustive** import list and a **type-only** `react` import (landmine 11). If Q1's wiring puts it
on screen, `App.tsx` — which is not under `src/components/` — is the only place that changes.

**AC 19.** **Given** the story introduces no motion, **when** the diff is inspected, **then** there
is no `transition` or `animation` in the stylesheet, **and** the record says so — *or*, if one is
added, it registers its fallback in the reduced-motion block in `tokens.css` (Decide-once #3: a
motion with no registered fallback is an incomplete story).

**AC 20.** **Given** the four open promises this story is homed to close (landmine list, item 14),
**when** it lands, **then** each is **closed or explicitly re-homed in the same commit**:
`Panel.tsx:95`'s title-less-live hole (Q6), `deferred-work.md:1316`'s Panel eye check (Q1/Q6),
`deferred-work.md:716-720`'s corrupt-database ruling (Q5), and the C1 retro action item at
`sprint-status.yaml:470` — which is **Brad's**, and is marked resolved only once the copy is in
`EXPERIENCE.md`. **And** `ui/README.md`'s three forward references (`:231`, `:737`, `:749`) are
repaired, along with the *Not here yet* paragraph (C1 retro homing rule).

**AC 21.** **Given** the story's visual half, **when** it is considered, **then** the record states
plainly what is and is **not** dev-verified — jsdom applies no stylesheet and has no layout engine,
so centring, the 480px measure, the chip's material and the accent line are **not** proven by the
suite — and homes each to the epic manual-testing checklist. *This is the sixth story to split an AC
this way (c2-2 AC 17, c2-5 AC 4, c2-6 AC 4/5, c2-7 AC 21, c2-8 AC 21); do not fake it with a
`getComputedStyle` assertion.* **If Q1 is answered as recommended, this story is also the first time
a human sees `Panel`'s and the shell's real appearance** — say what was looked at.

**AC 22.** **Given** the retry contract (landmine 16), **when** the story lands, **then** the
"quietly retries" / "must never retry" split is written **where the wiring story will read it**
(`ui/README.md` and the component's own doc comment), naming **c3-9** as the owner, not only in this
record.

**AC 23.** **Given** any CSS or component change, **when** the story is committed, **then**
`cd ui && npm run build` runs and **both** the committed bundle and its `plugin/` mirror are
regenerated and committed if they change — and the result is **measured** and recorded either way
(the prediction above says it changes this time; prove it).

**AC 24.** **Given** the scope, **when** the diff is inspected, **then** it adds **no dependency,
runtime or dev**, touches no `.py` file (except the regenerated mirror), no route, no store, no
fetch layer, and none of the components owned by c2-10, c3-*, c4-*, c5-*, c6-*. `pyproject.toml`,
`uv.lock` and `package.json` are untouched. The Python suite is **re-run** to prove it stayed at
**1,753**, not assumed. *(Q2 may add exactly one token and one DESIGN.md frontmatter entry; if so
that is a **ruled** change with its own assertions updated in the open — 64 → 65 in
`tests/tokens.test.ts:254` and `declaredTokens.size` in `tests/token-usage.test.ts` — and nothing
else about this AC relaxes.)*

**AC 25.** **Given** every new guard and every copy branch, **when** the story claims done, **then**
each has been **probed with an input it does not enumerate** — an emoji the ban never lists, a
`--negative` spent through a property the guard did not name, a copy string edited in
`EXPERIENCE.md` to prove the verbatim gate fires, a seventh reason token added to prove the map is
total — with the mutation **verified on disk before the verdict is believed** (c2-4's lesson,
c2-6's probe 10, c2-7's probe 10, all three of which found a real hole; c2-8 ran nine and caught
nine, which is the bar).

## Tasks / Subtasks

- [x] **Task 0 — verify the baseline before changing anything** (standing agreement)
  - [x] Branch off `feat/companion-c2` as `feat/companion-c2-9-state-panel`; confirm
        `baseline_commit` is `109a7d9`
  - [x] `cd ui && npm test` → expect **390 passed / 22 files**; `npm run lint`,
        `npm run format:check`, `npm run typecheck`, `npm run build` all exit 0
  - [x] Repo root: `uv run pytest -m "not integration"` → expect **1,753 passed / 1 skipped /
        45 deselected**. *If `test_list_decks_with_strategy_field` fails, it is the known
        `created_at`-tie flake — re-run before investigating.*
  - [x] `git status --porcelain -- src/companion/app/static/ plugin/` clean **after** a build, so a
        later drift is provably yours
  - [x] Record every number in the Dev Agent Record

- [x] **Task 1 — settle the decisions before writing anything** (Q1–Q6)
  - [x] Confirm Brad's answers to Q1–Q6 are in hand; if any is "not as proposed", re-read the ACs it
        touches before starting
  - [x] **The copy edits land first** (AC 10): the `internal_error` row, and Q5's row if ruled, go
        into `EXPERIENCE.md`'s copy table before any test reads it
  - [x] Write one probe stylesheet exercising the chosen chip spelling (Q2), the panel shell and the
        accent action line; `npm run lint` it; **delete it**. Measure before committing to a shape.

- [x] **Task 2 — the copy module and its verbatim gate, first, because it is the deliverable**
      (AC 3, 4, 8, 9, 10, 11)
  - [x] The copy module under `src/components/StatePanel/` (or as Q6 rules); `git add` immediately
        (landmine 12)
  - [x] `ui/tests/copy.test.ts` (node project) reads `EXPERIENCE.md` by one path constant, parses the
        Voice-and-Tone table, and asserts headline + body **byte-for-byte** per state
  - [x] **Non-vacuity anchor first**: assert the table parsed and yielded the expected number of
        rows, so a stale path or a changed table heading fails loudly rather than asserting nothing
  - [x] The concatenation invariant (AC 9), asserted per state
  - [x] The backtick → chip derivation and the no-backtick case (AC 11)

- [x] **Task 3 — the state map** (AC 12)
  - [x] Total over `ErrorReason`, with "no panel" as a real, named answer for `invalid_request` and
        `payload_too_large`, and the disconnected state carried outside the token vocabulary
  - [x] Exhaustiveness proved by the **type**; add the compile-time proof to `schema.test.ts`'s
        neighbourhood or beside the map, whichever keeps `typecheck` the gate (a runtime test here
        proves nothing — `schema.test.ts:4` says so in bold)

- [x] **Task 4 — the panel** (AC 1, 2, 5, 7, 15, 16, 17, 18, 19)
  - [x] `src/components/StatePanel/{StatePanel.tsx, StatePanel.css, StatePanel.test.tsx}`;
        `git add` immediately
  - [x] `role="region"` + `aria-label`, `h2` headline, no `aria-live`
  - [x] The deck list: non-clickable, asserted by **role** (no `link`, no `button` in the subtree),
        not by class name
  - [x] `npm run lint` after **every** block

- [x] **Task 5 — the two guards** (AC 13, 14)
  - [x] Non-vacuity anchor first: prove the guard reads real files and that the copy module has real
        strings in it, so an empty result cannot pass for silence
  - [x] The copy guard, both halves, with the review half declared in the guard's own comment
  - [x] The no-error-styling guard, keyed by family, proven against a fallback spelling
  - [x] Cases into `tests/fixtures/` (a new fixture if the file half needs one, as
        `accent-dim-cross-block.css` did); assert counts **per fixture file**, never in aggregate
        — *record correction (review 2026-07-29): no fixture FILE shipped; both guards probe via
        injected readers/inline source instead, a decision documented in the guards' own comments
        ("the thing being proven is a token reference, which needs no valid stylesheet around
        it"). The checkbox stands for the probes existing, not for files that do not.*

- [x] **Task 6 — registration and, if Q1 says so, the screen** (AC 18)
  - [x] Add every new module to `PRIMITIVES` with exhaustive import lists; run `tests/shell.test.ts`
        and confirm the git-derived coverage check is **green because the list is complete**, not
        because the files are untracked
  - [x] If Q1 is "wire it": `App.tsx` passes the panel into the shell's `left` slot, and the shell's
        left-column placeholder line is handled deliberately, not deleted in passing

- [x] **Task 7 — records** (AC 20, 21, 22)
  - [x] `ui/README.md`: the copy contract and how a later state joins it; the retry split naming
        c3-9; the two new ban-table rows; repair `:231`, `:737`, `:749` and the *Not here yet*
        paragraph
  - [x] `Panel.tsx:95`'s hole closed per Q6, in `Panel.tsx` and the README, not only here
  - [x] `deferred-work.md`: close/repair the Panel eye-check entry (`:1316`) and the corrupt-database
        entry (`:716`); add this story's own visual entries
  - [x] `sprint-status.yaml:470` — the C1 retro action item, marked with what actually closed it

- [x] **Task 8 — rebuild, mirror, prove** (AC 23, 24)
  - [x] `npm run build`; `uv run python -m scripts.build_plugin`; **measure** whether either tree
        changed and record the answer either way
  - [x] Re-run all five frontend gates and the Python suite (expect **1,753**, unchanged)
  - [x] Scope proof: `git diff --stat` shows no `.py` outside the mirror, no `pyproject.toml`, no
        `uv.lock`, no `package.json`
  - [x] `git status --porcelain` clean

- [x] **Task 9 — probe the evasions before claiming done** (AC 25)
  - [x] For each new guard, plant the evasion, confirm it is caught, revert, paste the output
  - [x] **Verify the mutation landed before believing the verdict**, and **read what landed on disk**
  - [x] Probe at least: a one-character edit to a body string in `EXPERIENCE.md` (the verbatim gate);
        an emoji and a full-width exclamation mark the copy ban never lists; `--negative` through a
        property the styling guard does not name, and `var(--negative, transparent)`; a seventh
        `ErrorReason` token added to `types.d.ts` (the map's totality — must fail `typecheck`, not
        `test`); a user-facing string added **outside** the copy module (the file half); a new
        tracked module under `src/components/` missing from `PRIMITIVES`
  - [x] **Ban the family, never enumerate members** — prove each guard with a spelling it does not
        list

### Review Findings (code review 2026-07-29 — Blind Hunter + Edge Case Hunter + Acceptance Auditor)

- [x] [Review][Decision] **AC 21's closing clause — no human eye-check recorded.** **RULED (Brad,
      2026-07-29): the look is deferred to the epic manual-testing checklist, as a ruling.** Q1's
      wiring stands and makes the check possible at any time (`artificial-planeswalker companion`,
      look at the no-active-deck panel); the epic checklist entry is the AC 21 record, not a
      drift from it. Written into the Dev Agent Record below.
- [x] [Review][Decision] **`COPY_MODULES` waives `AppShell.tsx` and `ManaCost/parse.ts` as whole
      files.** **RULED (Brad, 2026-07-29): accepted as-is.** The entries carry documented reasons;
      tightening (extracting AppShell's placeholder strings into a copy module) can ride along
      when c4-2 first edits AppShell's copy. [ui/tests/copy-rules.test.ts:94-112]

- [x] [Review][Patch] **Calm-surface allowlist admits `--accent-dim` through the open `--accent`
      prefix** — `--accent-dim` is documented at 2.70:1 (fails the 3:1 floor, `tokens.css:105` and
      `StatePanel.css`'s own comment) yet passes the AC 14 gate; make `--accent` an exact match and
      probe `--accent-dim` [ui/tests/token-usage.test.ts:774]
- [x] [Review][Patch] **Letterless JSX text escapes both copy-guard halves** — `<p>🎉</p>` /
      `<p>!</p>` fail the `/[A-Za-z]/` gate on `JsxText` and are yielded to neither half, even in
      `includeEverything` mode; collect letterless JSX text for the content half and probe it
      [ui/tests/copy-rules.test.ts:187-189]
- [x] [Review][Patch] **Q1's wiring has no test — reverting the `left` prop keeps all 487 green**;
      add an assertion to `App.test.tsx` that the no-active-deck region renders
      [ui/src/App.tsx:45]
- [x] [Review][Patch] **A mixed deck array renders blank `<li>`s** — `['', 'Boros Aggro']` passes
      `filled()` yet emits an empty announced list item; filter blank names per element and test
      the mixed case [ui/src/components/StatePanel/StatePanel.tsx:115-119]
- [x] [Review][Patch] **Duplicate deck names collide as React keys** — `key={deck}` with nothing
      forbidding duplicates in the prop contract; index keys are safe for this static list
      [ui/src/components/StatePanel/StatePanel.tsx:118]
- [x] [Review][Patch] **The artefact parser silently keeps only the last of two same-labelled
      rows** — `rows.set` overwrites, `size === 6` still passes; fail loudly on a duplicate label,
      and declare the `[^"]*` no-inner-quote ceiling the way copy-rules declares its residues
      [ui/tests/copy.test.ts:74-79]
- [x] [Review][Patch] **The per-state `h2` assertion is a substring match** — `toHaveTextContent`
      tolerates appended text for five of six states; make it exact
      [ui/src/components/StatePanel/StatePanel.test.tsx:69]
- [x] [Review][Patch] **Stale comment falsified by this commit** — `shell.test.ts` still says
      "`declaredTokens.size === 64` is pinned … so adding one is not available" after the ruled
      64 → 65 [ui/tests/shell.test.ts:822]
- [x] [Review][Patch] **`PANEL_FOR_REASON` / `RETRIES_QUIETLY` values are policed by nothing** —
      totality is typed but flipping `internal-error` to `true` (the load-bearing `false`) or
      swapping two panels keeps 487 + typecheck green; pin the semantic anchors in a small test
      [ui/src/components/StatePanel/states.ts:98-112]
- [x] [Review][Patch] **`EveryPanelHasASource` proves at-least-one source, not disjointness** — a
      state in both `PANEL_FOR_REASON` values and `CLIENT_ONLY_STATES` compiles clean; add a
      no-overlap type assert [ui/src/components/StatePanel/states.ts:127]
- [x] [Review][Patch] **The headline slot bypasses the chip mechanism with no gate** — a future
      backticked headline renders literal backticks on screen and into `aria-label`; assert no
      backtick in any headline in `copy.test.ts` [ui/src/components/StatePanel/StatePanel.tsx:97-98]
- [x] [Review][Patch] **`USER_FACING_ATTRIBUTE` enumerates members of a family** — `aria-valuetext`,
      `aria-braillelabel`, `aria-brailleroledescription` are absent; add them, and declare the
      remaining undeclared residues (Latin-only `PROSE`, single-word JSX expression children) in the
      header beside the three that are declared [ui/tests/copy-rules.test.ts:115-123]
- [x] [Review][Patch] **`copy.test.ts` misdescribes its own scope** — the comment says it parses
      "the Voice-and-Tone table" but the code scans every line of `EXPERIENCE.md`; a
      Headline+Body-shaped line anywhere else enters the map and breaks the size-6 pin with a
      misleading message; scope or re-describe [ui/tests/copy.test.ts:59-83]
- [x] [Review][Patch] **Q6(b)'s ruling is comments-only — `{ live: true }` with no `title` still
      compiles** and silently renders the absent-signal panel the ruling says does not exist;
      encode `live` requires `title` in `PanelProps` (no consumers exist yet, so the change is
      free) [ui/src/components/Panel/Panel.tsx:54-60]
- [x] [Review][Patch] **Record accuracy** — Task 5's fixture subtask is checked but no
      `tests/fixtures/` case shipped (the injected-reader decision is documented only in a code
      comment), and probe 1's "only that state's concatenation assertion fired" is imprecise;
      annotate the record [story file, Task 5 / probe table]
- [x] [Review][Defer] **A runtime-unknown `state` key crashes the panel** — `STATE_COPY[state]`
      has no fallback; TypeScript guards it today and no runtime caller exists, but c3-9's wiring
      must validate wire values before they reach this prop
      [ui/src/components/StatePanel/StatePanel.tsx:92] — deferred, c3-9 owns runtime validation
- [x] [Review][Defer] **The un-quoted tails of EXPERIENCE.md rows are contract nobody gates** —
      the deck-list clause and both retry clauses live outside the `Headline:`/`Body:` captures
      and can drift from `RETRIES_QUIETLY` with every gate green — deferred, extending the gate
      is new scope; candidate for c3-9 alongside the wiring it constrains

## Dev Notes

### Decide-once rulings this story sets (c2-10, c3-9, c4-3, c4-10, c4-12, c6-6 inherit)

1. **Where user-facing copy lives and how it is gated** (AC 8, 13, Q3) — every later story with a
   sentence in it (c2-10's attribution, c4-3's "Unknown card", c4-12's empty-deck line, c6-6's empty
   push) joins this mechanism instead of inventing one.
2. **How a specified property with no legal spelling is resolved** (AC 1, Q2) — the third member of
   the family after c2-6's cited geometry literals, c2-7's uncitable `min-width: 76px` and c2-8's
   pip size. The answer here is different from all three, because this time the value **is** in the
   design contract's prose and only the token is missing.
3. **How a closed wire vocabulary maps to a UI vocabulary that is not the same set** (AC 12) —
   c3-2's `card_not_found` and c5-1's envelope union meet the identical shape.
4. **Whether a title-less `live` Panel exists** (Q6) — `Panel.tsx:95`'s declared hole, closed by its
   first consumer as that comment intended.

### The five things this story inherits and must not break

- **The token layer is complete and closed** — 64 tokens, asserted by count *and* byte-for-byte
  against DESIGN.md. Q2 is the one place this story may change that, and only by Brad's ruling, in
  the open, with both assertions updated.
- **The typography ban is total** — `font`, every `font-*` longhand, `line-height`,
  `letter-spacing`, `word-spacing` and `text-indent` accept only the role/family/tracking tokens
  (plus `0` and the CSS-wide keywords).
- **c2-6's citation gate runs over every component stylesheet** — every `\d+px` needs `DESIGN.md`
  within 60 characters of it, in a comment, in the same file. This story's one literal **is**
  citable (landmine 7).
- **The presentation-only posture is a gate, not a convention** — exhaustive imports, type-only
  react, hooks banned by family, `useId` banned by name.
- **The gates are cheap.** `npm run lint` is ESLint **and** stylelint in one script. Run it after
  every block.

### There is no composition reference for this component

`DESIGN.md:348` lists what the imported mock demonstrates and what it does not, and the **State
panel is on the second list** — with the DFC flip control, the suggestion row, the connection pill,
the card placeholder, the skip link and the footer attribution. So there is no arrangement to read
and no drift table to write. `DESIGN.md:384` and `EXPERIENCE.md:61-71,96` are the whole source. Do
not go looking for a mock implementation to adapt; there isn't one, and the nearest-looking thing in
`_ds_bundle.js` is a different component.

### Previous story intelligence (c2-8, PR #25, Greptile **5/5 at round 1** — the epic's second in a row)

- **The review theme, six stories running: a guard proven only against the spellings it lists.**
  c2-8's shipped property *allowlist* (fill properties only) beat the family *ban* it was specced as,
  and probe 3 proved it: `box-shadow`, `outline-color` and `caret-color` all pass a ban list and all
  fail an allowlist. **This story's equivalent is AC 13's character-family ban** — an emoji is not a
  code point you can enumerate.
- **The headline defect of c2-8's review was one layer above the thing that was tested**: the parser
  was proven exhaustively, and `ManaCost` never proved it *forwarded* what the parser returned —
  every colour could be dropped and 383 tests stayed green. **This story's identical exposure**: a
  copy module proven byte-for-byte against EXPERIENCE.md, and a panel that renders the wrong field
  in the wrong slot, or drops the action line entirely, with the copy test still green. AC 9's
  invariant and the component tests have to meet in the middle.
- **A probe that passes is information, not a formality.** c2-8 ran nine and caught nine; c2-4,
  c2-6 and c2-7 each had one pass and each one found a real hole.
- **Brad has answered "as proposed" on every open question for seven stories running.** Q1–Q6 below
  are written to be answerable in one pass for the same reason — but Q2, Q4 and Q5 change artefacts
  Brad owns (`DESIGN.md`, `EXPERIENCE.md`), so they are genuine decisions rather than confirmations.

### Git intelligence

`feat/companion-c2` is at `109a7d9`, working tree clean — **this story is not blocked**. The house
shape of the last five merges: implementation → review patches (the commit message names the theme)
→ PR round → merge → records. Conventional Commits, scope `companion`. The story PR targets the
**umbrella** with a Greptile pass; the per-epic integration PR gets none (standing rule). Epic C2 is
**8 of 10** — this story and c2-10 close it, and the retro follows.

### Source tree — what exists, what this story adds

```
_bmad-output/planning-artifacts/ux-designs/ux-…-2026-07-22/
  EXPERIENCE.md                  UPDATE  the internal_error row (AC 10) + Q5's row if ruled
  DESIGN.md                      UPDATE  ONLY if Q2 adds a family token (frontmatter + prose)
ui/
  README.md                      UPDATE  copy contract + how a later state joins it; the retry
                                         split naming c3-9; two ban-table rows; repair :231, :737,
                                         :749 and the Not-here-yet paragraph
  src/
    App.tsx                      UPDATE  only if Q1 says wire it
    components/
      StatePanel/{StatePanel.tsx,.css,.test.tsx}   NEW
      StatePanel/copy.ts                            NEW  the copy, and the only place it lives
      StatePanel/states.ts                          NEW  the ErrorReason → panel map (AC 12)
      Panel/Panel.tsx            UPDATE  close the title-less-live hole (Q6)
  tests/
    copy.test.ts                 NEW     the EXPERIENCE.md verbatim gate (AC 8, 9)
    shell.test.ts                UPDATE  PRIMITIVES gains the new modules (AC 18)
    token-usage.test.ts          UPDATE  the no-error-styling guard (AC 14)
    tokens.test.ts               UPDATE  ONLY if Q2 adds a token (64 → 65)
    fixtures/…                   UPDATE  its cases
src/companion/app/static/        REGENERATED (probably CHANGED this time — measure)
plugin/…/static/                 REGENERATED
_bmad-output/implementation-artifacts/deferred-work.md   UPDATE (AC 20, 21)
_bmad-output/implementation-artifacts/sprint-status.yaml UPDATE (AC 20 — the C1 retro item)
```

Nothing else. No `.py` logic, no route, no store, no fetch.

### Gotchas specific to this story

1. **A `Record<ErrorReason, Panel>` is the wrong shape.** Two tokens must map to *no* panel and one
   panel has no token (landmine 4). Total, yes; one-to-one, no.
2. **"Verbatim" that is asserted against a string literal in the test file is not verbatim.** Read
   the artefact (AC 8), as `tokens.test.ts` reads DESIGN.md.
3. **`!` and "something went wrong" already exist in `ui/src`** (landmine 10). Any ban written
   before reading that measurement fails on the day it is written.
4. **`--surface-well` inside `--surface-panel` is a recess, not a skipped step** (landmine 9).
5. **`useId` is banned by name**, so the region name is `aria-label` (landmine 11).
6. **`git add` before running the guards** (landmine 12). Five stories running.
7. **jsdom renders no styles.** Every centring, measure, colour and material claim reads CSS
   **source** in the node project, or goes on the manual checklist (AC 21).
8. **Component tests assert by ROLE and by TEXT**, not by class name — and the non-clickable deck
   list is asserted by the **absence** of `link`/`button` roles, which is the only assertion that
   actually says what AC 5 means.
9. **Do not add an `aria-live` to this panel** (landmine 17), and do not add a spinner, an icon, or
   a `<img>` — the ban on illustration is a ban on the element, not only on the styling.
10. **`filled()` already exists** at `src/components/filled.ts` for every "is this empty" decision —
    the deck list, the optional action line, an absent headline. It cost c2-6 two review rounds plus
    a Greptile round over five shapes (`<></>`, `[]`, `' '`, `false`, one-shot iterables) that all
    render nothing while looking filled. **Do not re-derive it**, and note what it does *not* answer:
    emptiness of a **string** is a different question (c2-8's AC 4 lesson).
11. **Do not build a state-panel manager or registry.** "Exactly one at a time" is the caller's
    (AC 2); there is exactly one `left` slot and no store until c4-1.
12. **The retry contract has no implementation here and must not grow one.** No `setTimeout`, no
    polling, no `useEffect` — there is no hook allowed anyway (AC 18). It is a declaration c3-9
    honours.

### Testing standards

- vitest, two projects. **Component tests are `.tsx` and live in `src/`** (the `dom` project); a
  pure-TS `.test.ts` beside its module in `src/` is collected by the same project. Node-project gate
  and guard tests live in `ui/tests/`.
- Component assertions go through `@testing-library/react` **by role and text**, not by class name
  or test id.
- **Every new guard gets a proven pair** from one invocation, asserted by rule name and count where
  stylelint is involved, **per fixture file** (never in aggregate).
- **Non-vacuity anchor first** in any test that filters a list or parses an artefact.
- **`npm run typecheck` is the gate for AC 12**, not `npm test` — `schema.test.ts:4` explains why in
  bold, with a measured example.
- Fixtures live in `tests/fixtures/`, are excluded from `npm run lint`, and are meant to stay broken.
- Python side: no new tests; re-run the suite to prove nothing moved.

### Architecture rules this story implements

- **UX-DR30** — the shared state-panel shell, and the ban on error styling.
- **UX-DR33** — the verbatim copy for every system state, and the voice rules as a gate.
- **UX-DR44** — `role="region"` with an `h2` headline; and the live-region inventory this panel
  stays out of (UX-DR45).
- **UX-DR1 / UX-DR5** — the surface ramp (and its documented recess), every spacing value from the
  scale.
- **FR-22** — the state-panel *surface and copy*; the wiring and the self-transition are Epic 3's
  (`epics-companion-app.md:676`).
- **AD-16** — the closed reason-token set, and the two tokens with no panel by design.
- **NFR-07** — the frontend gates are the enforcement mechanism.

### References

- [epics-companion-app.md#Story-2.9](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  eight AC blocks (lines 1467-1504)
- [epics-companion-app.md#UX-DR30](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  state panel (line 500); UX-DR33's copy rule (line 520); UX-DR44 (line 590); the FR-22 split
  (line 676); c3-9's wiring ACs (lines 1805-1836)
- [EXPERIENCE.md](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md)
  — the copy table (lines 61-71), the State panel row (line 96), the state patterns (lines 110-119),
  the live-region inventory (line 156)
- [DESIGN.md](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md)
  — the State panel spec (line 384), the `components.state-panel` frontmatter (lines 231-235), the
  "no mock for this component" list (line 348), the one-family typography rule (line 300)
- [c2-8 story record](_bmad-output/implementation-artifacts/c2-8-manapip-and-manacost-with-complete-scryfall-cost-parsing.md)
  — the four decide-once rulings, the nine-probe bar, the "one layer above the tested thing" defect
- [ui/src/api/types.d.ts](ui/src/api/types.d.ts) — what each reason token means on the glass
  (lines 54-69, the `internal_error` homing at 67-69)
- [ui/src/api/schema.test.ts](ui/src/api/schema.test.ts) — the six-token pin (41-50) and why
  `typecheck` is the gate (4-13)
- [ui/tests/shell.test.ts](ui/tests/shell.test.ts) — the citation gate (820-871), `PRIMITIVES` and
  its git-derived coverage check (963-1059)
- [ui/tests/tokens.test.ts](ui/tests/tokens.test.ts) — the artefact-reading pattern AC 8 copies
  (1-80, the 64-token pin at 254)
- [ui/README.md](ui/README.md) — the ban table (194-217), the geometry-literal non-ban and its
  correction (219-249), _Not here yet_ (728-762)
- [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md) — the corrupt-database
  ruling (716-720), the Panel eye check (1310-1322)

## Open questions for Brad — answer before `dev-story`

Each carries a recommendation; "as proposed" on all six is a complete answer. **Q2, Q4 and Q5 change
artefacts you own** (`DESIGN.md`, `EXPERIENCE.md`) rather than merely confirming an implementation
choice, so they are the ones worth reading closely. Q1, Q2 and Q6 are decide-once rulings later
stories inherit.

**Q1 — does this story put a state panel on the actual screen, or ship it unwired?**
*Recommendation:* **wire it.** `App.tsx` renders the no-active-deck panel into the shell's `left`
slot. Three reasons, in order: the epic's own framing says "the system-state surfaces are the
finished article", and an article nobody can look at is the same claim c2-7 and c2-8 both had to
downgrade to "not dev-verified"; `deferred-work.md:1316` homes **`Panel`'s first eye check here**,
which is only true if a screen exists; and it is **honest** — there genuinely is no active deck,
because there is no fetch layer until c3-1 and no store until c4-1, so "No deck on the glass" with
an empty deck list is the app's true state rather than a mock. The consequence to accept: the
shell's left-column placeholder line naming c4-4/c4-8 is displaced, so it moves into the panel's
record and c4-2/c4-4 replace the static choice with the real one. The alternative — ship the
component with no consumer, as c2-7 and c2-8 did — is declined because this is the third story in a
row that would be unable to verify its own appearance, and because it would leave `Panel` unlooked-at
into Epic 4.

**Q2 — "a monospace-styled inline chip" has no legal spelling. Which way out?**
*Recommendation:* **add one family token, `--font-mono`, as a system-generic stack, and amend
`DESIGN.md`'s frontmatter to declare it.** Concretely: `--font-mono: ui-monospace, SFMono-Regular,
Menlo, Consolas, monospace` — **no `@font-face`, no download, no new asset**, so c2-5's offline
parity (NFR-06) and the one-`@font-face` guard are untouched; the second family exists only inside a
command chip, which is *data* (a literal string the user will type), never chrome or display type,
so UX-DR2's "hierarchy never comes from a second family" is not what this contradicts. The cost is
stated plainly: `tests/tokens.test.ts:254`'s **64 becomes 65**, `declaredTokens.size` with it, and
`DESIGN.md` gains a frontmatter entry — all three in the open, in this commit, which is exactly the
c2-4 precedent (*a partly-tokenised value fails; later stories add a token rather than inline one*).
The alternative — a chip carried by material alone (`--surface-well`, `--radius-sm`, no family
change) — is genuinely cheaper and is what I would ship if you decline the token; it is declined as
the recommendation because "monospace-styled" is written in **both** `DESIGN.md:384` and the epic's
own AC, and silently dropping a specified property is this epic's named failure mode wearing a
different hat. **Watch item for the dev agent either way:** `tests/tokens.test.ts` types
`typography.*` as a full `TypeRole` (family/size/weight/line-height), so a bare family entry does not
fit that reader — the token belongs beside `--font-sans`'s source in the frontmatter, and the
reader's shape may need widening. Measure it in Task 1 rather than discovering it in Task 8.

**Q3 — how does the two-field copy fill three slots without stopping being verbatim?**
*Recommendation:* **split the Body at a sentence boundary, and gate the split by concatenation.**
The copy module holds `headline`, `guidance` and `action` per state; `tests/copy.test.ts` asserts
`headline` byte-equals EXPERIENCE.md's Headline and `[guidance, action].join(' ')` byte-equals its
Body. Nothing is written that EXPERIENCE.md did not write; the panel just knows which sentence is
the action. The proposed splits, per state:

| State | guidance | action (accent line) |
| --- | --- | --- |
| No-active-deck | *(empty)* | "Ask your agent to set an active deck — it will appear here the moment it does." |
| Database not initialized | "First build takes a few minutes — this page will come alive on its own when it's ready." *(order: see below)* | "In your agent session, ask it to initialize the database (`initialize_database`)." |
| Database updating | "Reads will resume automatically — nothing to do here." | *(none — there is no action, and inventing one would be the lie)* |
| Disconnected | "Check your terminal. If it moved ports, this tab can't follow it automatically." | "If the backend restarted, it printed a fresh URL — open that." |

Two consequences to accept, both deliberate: the action line is **optional** (database-updating has
none, and a panel with no action is a real state, not a defect); and for two states the action is not
the last sentence, so the rendered order differs from EXPERIENCE.md's reading order while the
**concatenation invariant is checked against the source order**. If you would rather the invariant be
literal — action always last, rendered in source order — say so and the disconnected and
not-initialized splits change; the mechanism does not.

**Q4 — the `internal_error` copy (the C1 retro action item, yours).** *Recommendation:* add this row
to `EXPERIENCE.md`'s copy table, in the same two-field shape:

> | Internal error | Headline: "The companion hit a bug." Body: "Restart the companion in your
> terminal (`artificial-planeswalker companion`). The traceback is in that terminal — it's what a
> bug report needs." |

Checked against UX-DR33 line by line: second-person, terminal-literate, names the command without
apology, **never blames** (the companion hit it, not you and not "something"), gives a concrete next
action, no exclamation mark, no emoji. And it is deliberately **not** a retry: "restart" is a
manual, deterministic action, which is the distinction `types.d.ts:67-69` draws between this token
and `database_unavailable`. The chip mechanism (AC 11) picks up the backticked command for free.

**Q5 — the corrupt-database ruling you owe from c1-6.** *Recommendation:* **add a sixth state — a
stalled variant of database-updating — and home its implementation to c3-9.** The backend genuinely
cannot tell 200 ms of mid-import from a month of garbage (that is why decide-once #4 ruled it
transient), so the distinguisher is **elapsed time on the client**, and the client is this UI. The
copy, for the same table:

> | Database updating, stalled | Headline: "Card database still updating." Body: "Reads haven't
> resumed for a while. Check your agent session — if no import is running, ask it to rebuild the
> database (`initialize_database`)." |

This story ships **only the copy and the panel**; the "for a while" threshold and the switch belong
to **c3-9**, which owns the polling. The alternative — leave it transient with no escalation — is
declined for the reason the deferred entry gives: "Reads will resume automatically — nothing to do
here" is, for a durably corrupt file, **false**, and this is the one story in the feature whose whole
subject is whether the words are true. If you would rather not grow the state set, say so and the
ruling becomes "accepted permanently, recorded in EXPERIENCE.md as a known limitation" — which is a
legitimate answer, but it should be a written one.

**Q6 — is the state panel a `Panel`, and does a title-less `live` panel exist?**
*Recommendation:* **not a `Panel`, and no.** Two parts:

(a) `DESIGN.md` declares a **separate** `components.state-panel.*` block, and the two differ where it
matters: a `Panel`'s title is `--type-label` (11px, uppercase, tracked) and a state panel's headline
is `--type-heading` (17px, sentence case); a state panel has no count, no badges, no `live` and no
header row. Rendering one through the other would mean threading a second title role through
`Panel`, which is how a primitive stops being one. It is its own shell, sharing tokens rather than
code. **The consequence is a records action, not a free one:** `deferred-work.md:1316` homes
`Panel`'s eye check here on the assumption the state panel *is* a Panel. Under this ruling it must be
**re-homed** — to **c4-5** (card detail, the first real `Panel` at `level="overlay"`) and **c4-7**
(the deck list) — in the same commit. That is AC 20.

(b) `Panel.tsx:95`'s declared hole: a `live` panel with **no title** keeps only its elevation change,
which graphite and ink flatten to nothing. Rule that **it does not exist** — `live` requires a title
— and say so in `Panel.tsx` and the README rather than leaving a second consumer to rediscover it.
The state panel is not the component that answers this by using it; it is the first story with
standing to close it, which is what that comment asked for.

## Dev Agent Record

### Baseline (Task 0, measured by running it at `109a7d9`)

| Gate | Result |
| --- | --- |
| `npm test` | **390 passed / 22 files** — matches the story |
| `npm run lint` / `format:check` / `typecheck` / `build` | all exit **0** |
| `uv run pytest -m "not integration"` | **1,753 passed / 1 skipped / 45 deselected** |
| mirror clean after a build | yes (`git status --porcelain` on both static trees empty) |

Branch `feat/companion-c2-9-state-panel` off `feat/companion-c2`; `baseline_commit` confirmed
`109a7d9`. No flake — `test_list_decks_with_strategy_field` passed first run.

### The six rulings (Brad, 2026-07-29 — "as proposed" on all six, the eighth story running)

**Q1 wire it · Q2 add `--font-mono` · Q3 source-order concatenation · Q4 the internal_error copy
as drafted · Q5 add the stalled sixth state · Q6 not a `Panel`, and no title-less `live` panel.**

Two things were measured differently from the recommendations and are **recorded rather than
quietly applied**:

1. **The mono stack needed a fourth measurement nobody had made.** Q2 predicted three costs
   (tokens 64 → 65, `declaredTokens.size`, a DESIGN.md frontmatter entry) and all three were
   paid. The fourth was found by running lint: unquoted, `ui-monospace, SFMono-Regular, Menlo,
   Consolas, monospace` produces **three `value-keyword-case` errors** demanding
   `sfmono-regular` / `menlo` / `consolas` — names that match nothing. Lowercasing would have
   been the wrong repair. The shipped token quotes the three **branded** names and leaves the
   two **generic keywords bare** (quoting `monospace` would stop it being the CSS generic), and
   DESIGN.md's frontmatter carries the identical string because `tokens.test.ts` compares them
   as strings. Both halves are written into `tokens.css` and the frontmatter.
2. **Q2's "watch item" landed exactly where it predicted, and the fix is a sibling section, not
   a widened reader.** `tokens.test.ts` types `typography.*` as a complete `TypeRole`, so a bare
   family does not fit — and putting one there would additionally have broken the 7-role loop
   *and* the `families.size === 1` assertion that is what MAKES `--font-sans` single. So
   DESIGN.md gained a top-level `fonts:` section rather than an eighth role. That is also the
   honest shape: a mono family with a `fontSize` would be claiming a hierarchy it does not have.

### What shipped

**The copy, and its verbatim gate.** `src/components/StatePanel/copy.ts` holds all six states;
`ui/tests/copy.test.ts` reads `EXPERIENCE.md` **itself** — one path constant, a loud named
failure if the artefact moves, a non-vacuity anchor pinning **6 parsed rows** — and asserts
every headline and body **byte-for-byte**. Rows are selected by STRUCTURE (a row that writes
both a quoted `Headline:` and a quoted `Body:`), not by line range, so the four non-panel rows
in the same table are excluded without a skip list and an eleventh row cannot rot the parse.

**The two-into-three split (Q3), gated by concatenation.** The Body is a LIST OF PARTS, each
tagged `guidance` or `action`, in source order. `bodyOf()` re-joins them and must byte-equal the
artefact. The list shape (rather than two strings) is what makes the invariant hold for
`disconnected`, which reads guidance / action / guidance in the artefact and renders
guidance-then-action on screen. Two consequences are asserted as REAL STATES rather than
tolerated: `database-updating` has **no action line** (it retries quietly — inventing an action
would be the lie), and `no-active-deck` has **no guidance** (its single sentence *is* the
action).

**The two states this story wrote, into `EXPERIENCE.md`.** `Internal error` (Q4) and
`Database updating, stalled` (Q5). Both are in the artefact's copy table, both are covered by
the verbatim gate with no special case, and the C1 retro action item is closed on that basis.

**The command chip is derived from the copy's own backticks** (AC 11) — one mechanism, so the
two new states needed no bespoke renderer, proved with `artificial-planeswalker companion` (a
two-word, hyphenated command) as well as `initialize_database`. No backticks → no chip, no
error, and no backtick ever reaches the reader.

**The state vocabulary (AC 12).** `states.ts` is total over `ErrorReason` via `satisfies`, with
`null` as a NAMED answer for `invalid_request` and `payload_too_large`, `CLIENT_ONLY_STATES` for
the two panels with no token, and `RETRIES_QUIETLY` total over `StateKey` — the retry contract
written where **c3-9** will read it rather than only in this record. A type-level
`EveryPanelHasASource` proof means a panel with neither a token nor a client-side home fails to
compile. **`npm run typecheck` is the gate here, not `npm test`** — probe 4 measured exactly
that.

**The panel.** `role="region"` (explicit, not the conditional implicit one) named by
`aria-label` — `useId` is a banned hook — with the headline as an `h2` and **no `aria-live`**.
Deck list non-clickable, asserted by the ABSENCE of `link`/`button` roles; emptiness decided by
`filled()`, which also covers the array-of-blank-strings case.

**Two new guards, both halves each, both proven firing and silent.**
`tests/copy-rules.test.ts` (new) enforces UX-DR33 on the **TypeScript AST** — which is what puts
the generated `types.d.ts`'s JSDoc quotation of the banned phrase and the `!` operator in nine
component modules out of scope *by construction* rather than by a special case. The **file
half** confines prose to `COPY_MODULES`; the **content half** bans `!`, emoji and the banned
blame phrase in **every** string in `src/`, keyed by character family: the
`Extended_Pictographic` Unicode property for emoji, and NFKC normalisation so Unicode's own
decompositions enumerate the full-width, small-form, double and interrobang spellings.
`findAlarmingTokenInCalmStylesheet` (in `token-usage.test.ts`) holds `StatePanel.css` to an
**allowlist** of calm token families — the strongest form of AC 14, and c2-8's ruling applied.

**Wired (Q1).** `App.tsx` renders the no-active-deck panel into the shell's `left` slot. Honest,
not a demo: with no fetch layer and no store there genuinely is no active deck. The shell's
left-column placeholder is **displaced, not deleted**, and c4-2 / c4-4 / c3-9 ownership is
written into `App.tsx` and the README.

### Three things measured, that would otherwise have been guessed wrong

1. **The bundle DID change, and it was measured rather than assumed (AC 23).** The story
   predicted it; `index-Dtvm20jX.js` / `index-yCpmQea7.css` became `index-DcQsus82.js` /
   `index-C-cdYYMS.css`, in both the committed bundle and the `plugin/` mirror. This is the
   first bundle change since c2-6, and the cause is exactly the predicted one: `App.tsx` imports
   a component for the first time, so tree-shaking no longer excludes it.
2. **A `className` template reads as prose to any prose detector — measured, not anticipated.**
   The first draft of the copy guard flagged the `badge`, `mana-pip` and `stat-chip-delta` class
   templates as user-facing copy: two space-separated class tokens look exactly like two words.
   Sniffing the string instead ("is it all kebab-case?") would wave through a lowercase sentence
   like `'ask your agent'`, so the fix is POSITIONAL — the `className` attribute subtree is
   skipped for the file half, and class names have their own gate (`selector-class-pattern`)
   anyway. The content half still reads them.
3. **Gating the ban behind the prose detector was a real hole, found by a probe that failed.**
   A one-word string plus a pictograph matches no prose pattern, so the first draft's content
   half never saw it. Repaired by giving the content half its own **total** extractor over every
   string node, then re-probed and caught. This is the story's own instance of the epic's
   standing finding, found inside its own guard.

### Definition-of-done evidence

| Gate | Before | After |
| --- | --- | --- |
| `npm test` | 390 / 22 files | **487 passed / 25 files** |
| `npm run lint` | 0 | **0** |
| `npm run format:check` | 0 | **0** |
| `npm run typecheck` | 0 | **0** |
| `npm run build` | 0 | **0** |
| `uv run pytest -m "not integration"` | 1,753 / 1 skipped / 45 deselected | **1,753 / 1 skipped / 45 deselected** (re-run, unchanged) |
| declared tokens | 64 | **65** (`--font-mono`, ruled, both pins moved in the open) |

Scope (AC 24): no `.py` touched at all; no route, store or fetch layer; `pyproject.toml`,
`uv.lock` and `package.json` **untouched** — the copy guard uses `typescript`, which is already
a direct devDependency (it *is* `npm run typecheck`). No component owned by c2-10 or
c3-* / c4-* / c5-* / c6-* was touched.

### Ten evasion probes, all ten caught (AC 25)

Every mutation was **verified on disk before the verdict was believed**, and every revert was
verified too (`git diff --quiet`).

| # | Probe | Verdict |
| --- | --- | --- |
| 1 | one comma added to a Body string in `EXPERIENCE.md` | **CAUGHT** — that state's concatenation assertion fired (and, when the edit lands inside a part, its substring assertion with it — "only that assertion" was the review-corrected over-claim; per-state isolation held, per-assertion did not) |
| 2 | a full-width exclamation mark and an emoji in the real copy module — two spellings the ban never lists | **CAUGHT** — both bans; the message names NFKC and the Unicode property |
| 3 | `--negative` through `caret-color`, a property no ban list names | **CAUGHT** — the allowlist's whole argument |
| 3b | `var(--negative, transparent)` — the fallback evasion, three times bitten | **CAUGHT** |
| 4 | a **seventh** `ErrorReason` token added to `types.d.ts` | **CAUGHT by `typecheck` in 4 places while `npm test` stayed GREEN (56 passed)** — including `EveryPanelHasASource` collapsing to `false`. Exactly what `schema.test.ts:4` warns about, measured. |
| 5 | a user-facing sentence added to `Panel.tsx`, outside any copy module | **CAUGHT** — message names `COPY_MODULES` and the three current owners |
| 6 | a new tracked module under `src/components/` missing from `PRIMITIVES` | **CAUGHT** by the git-derived coverage check |
| 7 | `disconnected` removed from `CLIENT_ONLY_STATES`, leaving a panel with no source | **487 tests GREEN, `typecheck` exit 2** |
| 8 | the `DESIGN.md` citation beside `480px` reworded away | **CAUGHT** by the live citation gate |
| 9 | **the c2-8 defect, reproduced**: the panel forwards `actionOf` into the guidance slot and vice versa | **`copy.test.ts` stayed GREEN at 25 passed; the component test caught it in 5 places.** The exposure the story named is real and is closed. |
| 10 | a "helpful" `aria-live="polite"` on the action line | **CAUGHT** — the subtree assertion, not just the root |

Probe 9 is the load-bearing one. It reproduces c2-8's headline review defect in this story's own
shape — a copy module gated byte-for-byte while the component renders the wrong field in the
wrong slot — and confirms the two halves genuinely meet in the middle rather than testing the
same thing twice.

### AC 21 — what is and is NOT dev-verified

**Dev-verified:** every semantic and structural claim (roles, heading level, the absence of
`aria-live`, the absence of `img`/`svg`, non-clickability by role, the slot-per-state
forwarding, the chip derivation, the empty-deck-list render), every static CSS claim (the token
families spent, no alarm token, no `transition`/`animation`, the DESIGN.md citation), and the
byte-for-byte copy.

**NOT dev-verified, and not faked:** centring, the 480px measure, the hairline border, the large
radius, the chip's recessed `--surface-well` material and mono family, and the accent colour and
weight of the next-action line. jsdom applies no stylesheet and has no layout engine, so there
is **no `getComputedStyle` assertion in this story** — one would report the defaults back and
pass over a stylesheet that was never linked. Sixth story to split an AC this way. Homed on the
epic manual-testing checklist, with the five unwired states homed at **c3-9**. Full entries in
`deferred-work.md`.

**Q1 means a human can look for the first time in this epic** — but note what that check covers
and does not: it shows the **shell** and the **state panel** on a real screen. It does **not**
show `Panel`, whose first consumer is now **c4-5** / **c4-7** after Q6 ruled the state panel is
not a `Panel` (re-homed in `deferred-work.md` and the README in this same commit).

### Four open promises closed or re-homed in this commit (AC 20)

| Promise | Outcome |
| --- | --- |
| `Panel.tsx`'s title-less-`live` hole | **CLOSED** — it does not exist; `live` requires a title. Written in `Panel.tsx` (both the dot comment and the prop doc) and the README, with the graphite/ink elevation flattening as the reason. |
| `deferred-work.md`'s `Panel` eye check | **RE-HOMED** to c4-5 and c4-7 — the entry assumed the state panel *is* a `Panel`, and Q6 ruled it is not. |
| `deferred-work.md`'s corrupt-database ruling | **RULED and half-shipped** — copy + panel here, threshold and switch homed at c3-9. |
| `sprint-status.yaml`'s C1 retro action item (Brad's) | **DONE** — both rows are in `EXPERIENCE.md`, which is what the item asked for, and both are gated byte-for-byte. |

`ui/README.md`'s three forward references and the *Not here yet* paragraph are repaired,
including recording that the 480px prediction was **right** — beside the standing correction
noting the 17px StatChip prediction was wrong.

### Four decide-once rulings later stories inherit

1. **Where user-facing copy lives and how it is gated** — c2-10, c4-3, c4-12 and c6-6 add an
   entry to `COPY_MODULES` with their reason rather than inventing a mechanism.
2. **A specified property with no legal spelling gets a TOKEN, not a silent drop** — the third
   of its family, and the answer differs from c2-7's and c2-8's because this time the value
   *was* in the design contract and only the token was missing.
3. **A closed wire vocabulary maps to a UI vocabulary that is not the same set** — `null` is a
   named answer, totality is proved by the type, and c3-2's `card_not_found` and c5-1's envelope
   union meet the identical shape.
4. **A title-less `live` `Panel` does not exist.**

### Review round (2026-07-29 — three layers, same-day, before the PR)

Blind Hunter + Edge Case Hunter + Acceptance Auditor over the full staged diff. ~30 raw findings
triaged to **2 decisions, 15 patches, 2 defers, 5 dismissed**; all 15 patches applied same-day.
The round's theme, for the record: **the story's own standing findings, applied one level up** —
a guard proven only against spellings it lists (`--accent-dim` through the open `--accent`
prefix; letterless JSX text through the `/[A-Za-z]/` gate), and a thing proven exhaustively one
layer below the thing that ships (the wiring itself untested; the state maps total but their
values unpinned).

**The 15 patches:** `--accent` exact-match in the calm allowlist + the `--accent-dim` probe;
letterless JSX text into the content half + probes; the `App.test.tsx` wiring assertion; per-name
blank filtering in the deck list (removing the `as` cast) + the mixed-case test; index keys +
the duplicate-names test; the artefact parser fails loudly on duplicate labels + declares its
no-inner-quote ceiling + honest scope description; exact (`toBe`) headline assertions; the stale
"64 is pinned" comment in `shell.test.ts` repaired; `states.test.ts` pinning the maps' semantic
anchors (the load-bearing falses, the designed nulls); `PanelSourcesAreDisjoint`; the
headline-no-backtick gate in `copy.test.ts`; three missing read-aloud ARIA attributes + residues
4 and 5 declared in `copy-rules.test.ts`; `live` requires `title` **in the type**
(`PanelProps` union, with `@ts-expect-error` proofs and the runtime guard kept as the JS floor);
and the two record corrections above (Task 5's fixture note, probe 1's wording).

**The two rulings (Brad, 2026-07-29):** AC 21's eye-check is **deferred to the epic
manual-testing checklist as a ruling** — Q1's wiring makes the look possible at any time, and
the checklist entry is the AC 21 record; and the `COPY_MODULES` whole-file waivers are
**accepted as-is**, with tightening riding along when c4-2 first edits AppShell's copy.

**The two defers** (in `deferred-work.md` under this review's heading): runtime validation of an
unknown `state` key (c3-9, with the wiring), and the un-quoted EXPERIENCE.md row tails as
ungated contract (c3-9, beside the clauses it constrains).

**Gates after patches:** `npm test` **502 passed / 26 files** (was 487/25 — `states.test.ts` is
new, plus the added cases); lint / format:check / typecheck / build all exit 0; bundle **changed
again and was measured** (`index-DcQsus82.js` → `index-D_x1yvrv.js`, CSS hash unchanged — no
stylesheet was touched) and the `plugin/` mirror regenerated with it. The Python suite was not
re-run: no `.py` or non-static input changed in this round (the story's own 1,753 run stands).

## File List

**New**

- `ui/src/components/StatePanel/copy.ts`
- `ui/src/components/StatePanel/states.ts`
- `ui/src/components/StatePanel/StatePanel.tsx`
- `ui/src/components/StatePanel/StatePanel.css`
- `ui/src/components/StatePanel/StatePanel.test.tsx`
- `ui/tests/copy.test.ts`
- `ui/tests/copy-rules.test.ts`

**Modified**

- `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md`
- `_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md`
- `ui/src/App.tsx`
- `ui/src/components/Panel/Panel.tsx`
- `ui/src/styles/tokens.css`
- `ui/tests/tokens.test.ts`
- `ui/tests/token-usage.test.ts`
- `ui/tests/shell.test.ts`
- `ui/README.md`
- `_bmad-output/implementation-artifacts/deferred-work.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/implementation-artifacts/c2-9-the-shared-state-panel-and-every-system-state-message.md`

**Regenerated (bundle CHANGED — measured, as predicted)**

- `src/companion/app/static/` (`index.html` + the two hashed assets)
- `plugin/server/src/companion/app/static/` (the same three)

## Change Log

| Date | Change |
| --- | --- |
| 2026-07-30 | Greptile round on PR #26: 4/5, one P2 — `decks` was accepted for every `StateKey` while the renderer showed any non-empty list regardless of state, so future wiring could put deck names under `database`/`disconnected`/`internal_error` copy. Ruled by Brad: **type-only constraint** — `StatePanelProps` becomes a discriminated union (`decks` on the `no-active-deck` arm alone, `decks?: never` elsewhere); the renderer is untouched, so the caller-owned posture stands and the prose contract became a compile-time one. Firing half proven by `@ts-expect-error` (an unused directive fails `tsc -b`, so the proof is self-checking); the silent half asserts the runtime stays dumb. The copy-rules `it.each` no longer passes `decks` to every state (now a type error — the gate working); no-active-deck's list path covered separately. Suites 502 → **504**; five gates green; bundle + mirror re-measured **byte-identical** (types erase). |
| 2026-07-29 | Code review (three layers, same-day): 15 patches applied — two guard holes closed with probes (`--accent-dim`, letterless JSX text), the wiring asserted, `states.test.ts` pins the map semantics, `live` requires `title` in the type; 2 rulings (AC 21 look → epic checklist; COPY_MODULES waivers accepted); 2 defers to c3-9. Suites 487 → **502**; bundle re-measured changed (`index-D_x1yvrv.js`); mirror regenerated. Status → done. |
| 2026-07-29 | Story c2-9 implemented off `109a7d9`. Q1–Q6 all as proposed. `EXPERIENCE.md` gains the `Internal error` and `Database updating, stalled` rows; `DESIGN.md` gains `fonts.mono` and its Typography exception; `--font-mono` added (declared tokens 64 → 65, both pins moved in the open). New `StatePanel` (copy module + total state map + panel), the `EXPERIENCE.md` verbatim gate, and two new guards (the UX-DR33 copy rules on the TypeScript AST; the calm-surface token allowlist). Wired into `App.tsx`. Suites 390 → 487 frontend; Python 1,753 re-run unchanged; five gates green; bundle + mirror regenerated and **measured changed**. Ten evasion probes, all ten caught. Four open promises closed or re-homed. |
