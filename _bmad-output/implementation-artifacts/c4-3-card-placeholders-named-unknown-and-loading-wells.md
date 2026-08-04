---
epic: c4
story: c4-3
work_branch: feat/companion-c4
story_branch: feat/companion-c4-3-card-placeholders
depends_on: >-
  c4-1 (merged at `2095050`) — `CardEntry.unknown.placeholder` already carries a
  `PlaceholderKey | null` computed from the token, and `useCardEntry` is the selector this story is
  the **first consumer** of. c4-2 (merged at `2a64231`) — `DeckBadges` is the precedent for a new
  listed component, and `frontFace()` in `deckGroups.ts` is the ` // ` split already in the repo.
  Also **c3-2** (`card_not_found` → `unknown-card`), **c3-5** (`no_image_data` /
  `image_fetch_failed` → `named-card`, and the typed `CardFace`), **c2-7** (`Badge`, the
  presentation-only posture), **c2-8** (`ManaCost`/`ManaPip`, which get their **first consumer**
  here) and **c2-4** (the token layer, which holds `--radius-card` with **zero** consumers today).
baseline_commit: 2a64231
---

# Story C4.3: Card placeholders — named, unknown, and loading wells

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad looking at a card whose art hasn't arrived or doesn't exist,
I want a deliberately designed card-shaped stand-in,
so that a gap in the data never reads as a broken app.

**What this story really is.** It is the story where the **card shape itself** enters the codebase.
Everything downstream — c4-4's tile, c4-5's detail art, c4-6's flipped face, c6-4's push thumbnails
— is the same 63:88 rectangle at the same exclusive radius, and this is the first module that draws
one. Six facts were measured at `2a64231` and four of them change the design:

1. **The named placeholder's only PERMANENT population renders with no pips, a useless type line
   and a doubled name.** Measured against the shipped database: of 38,261 cards, **79 carry no
   image data anywhere** (neither top-level `image_uris` nor any per-face one) — c3-5's number,
   re-verified here. What c3-5 did not measure is *what those 79 look like*: **all 79 are
   `'Card // Card'` reversible printings**, **all 79 have `mana_cost = ''`**, and every one of their
   names is the same words twice (`Memory Lapse // Memory Lapse`, up to **66 chars**). So
   UX-DR22's three-part composition — *"name centred in body-strong, mana pips above, type line in
   micro"* — degrades, **measured**, to a name and nothing else for every card that permanently
   needs it. That is not a reason to change the design; it is a reason the layout must be correct
   when two of its three parts are empty, and it is where the fixtures come from.

2. **`--type-micro` is UPPERCASE by contract, and on the truncated id that is a defect rather than
   a style.** DESIGN.md's `micro` role carries `textTransform: uppercase`, and
   `token-usage.test.ts`'s `findRoleWithoutCompanions` **requires** `text-transform: uppercase`
   *and* `letter-spacing: var(--tracking-micro)` in the same rule block as `font:
   var(--type-micro)` — derived from the artefact, not enumerated, so it cannot be dodged. Now read
   `cards.py:67`: `_CARD_ID_PATTERN = r"^[0-9a-f]{8}-…$"` — **lowercase-only, deliberately**
   (*"Nothing is reachable by normalising an uppercase id"*). A truncated uuid rendered in the micro
   role therefore shows the reader an id **the backend would refuse if it were typed back**, and it
   is the one identifying thing the unknown variant has. Decide the id's type role before writing
   the CSS (Q4).

3. **The card geometry CANNOT be a token, so it is a shared class or it is drift.**
   `tokens.test.ts:265` asserts set equality against an inventory derived from DESIGN.md's
   `colors` / `typography` / `rounded` / `spacing` / `motion` / `focus` / `elevation` blocks and pins
   the count at **65** — `components.card-tile.aspect` is in none of those, so **`--card-aspect`
   cannot be added without failing that gate.** Meanwhile `--radius-card` exists and has **zero
   consumers**: measured across `ui/`, its only occurrences are its own declaration in `tokens.css`,
   one line in `tests/fixtures/css/clean.css` and the two `tokens.test.ts` assertions that it is a
   percentage. This story is its first real consumer, and therefore the story that decides where the
   `63 / 88` + `var(--radius-card)` pair lives so that four later stories cannot each write their
   own (Q2).

4. **UX-DR4's exclusivity half has no gate at all.** *"Nothing else in the UI borrows the card
   radius, and no card borrows a chrome radius"* is currently true only because nothing uses either
   on a card. The moment this story spends `--radius-card`, that sentence becomes a live constraint
   with nothing enforcing it — and it is the same shape as the `--mana-*` data-ink guard
   (`token-usage.test.ts:967`), which is an allowlist of files that may spend a token family. This
   story can build it in the idiom that already exists (AC 12).

5. **The loading well is a deliberate HOLE in the surface ramp — declare it, do not "fix" it.**
   DESIGN.md gives `card-placeholder.background: {colors.surface-overlay}` (the **top** of the ramp)
   and the well `{colors.surface-well}` (the **bottom**). `surfaces.ts::stepsExactlyOne` is
   directional and says a nested pane that gets darker than its parent *"reads as a hole rather than
   a pane"* — which is exactly what a well **is**. `stepsExactlyOne('surface-panel', 'surface-well')`
   is `false` and will stay false. The adjacency rule is review's, not a gate (that module says so
   itself), so the risk here is a reviewer reading a correct well as a violation.

6. **The ledger's instruction on `states.ts`'s classification is conditional, and this story is the
   condition.** `deferred-work.md:2014-2025`: *"the CLASSIFICATION half — `PLACEHOLDER_FOR_REASON`,
   `NO_UI_RESPONSE` and the three type-level asserts — is still consumed by nothing, and **stays
   c4-3's** … **If c4-3 does not consume the classification, delete it.**"* c4-1 already did the
   routing work: `CardEntry.unknown.placeholder` is a `PlaceholderKey | null` computed once, so
   *"that distinction is what lets c4-3 draw the right thing without re-deriving it from tokens"*
   (`cards.ts:151`). Consuming it is cheap and it is an AC (AC 8); not consuming it means deleting a
   structure two stories argued for, in this commit.

**Everything numeric in this story was measured on this machine at `2a64231`, read-only, against
the live database at `%LOCALAPPDATA%\artificial-planeswalker\cards.db`, the committed
`openapi.json`, `DESIGN.md`'s frontmatter and the installed toolchain. Do not rediscover it.**

### The seam that already exists (do not rebuild any of it)

1. **The variant vocabulary is already written, typed and gated — it is `PlaceholderKey`.**
   `states.ts:144` is `export type PlaceholderKey = 'unknown-card' | 'named-card'`, with
   `PLACEHOLDER_FOR_REASON` mapping `card_not_found → 'unknown-card'` and both image tokens →
   `'named-card'`, and four type-level asserts holding the classification total and disjoint. A
   third vocabulary invented in this story ("`missing` / `absent` / `pending`") is the failure c3-2
   built that file to prevent. **Take the variant type FROM `states.ts`** so a third key added there
   is a `tsc` failure here (AC 8).

2. **The decision "which placeholder does this card get" is already computed, once, per entry.**
   `entryFor` in `cards.ts:391` writes `placeholder: reason === null ? null : (placeholders[reason]
   ?? null)`, where `null` means *"the read did not land and whatever `summary` exists still
   stands"* — explicitly **not** "unknown card". Nothing in this story re-derives a placeholder from
   a token; a `switch (entry.reason)` anywhere in a component is a red review.

3. **`ManaCost` is total and takes a plain string — it needs no wrapper.** `cost?: string | null`,
   and *"`undefined`, `null`, `''` and a whitespace-only string all render NOTHING, without
   error"*. That is exactly the shape all 79 no-image cards arrive in. It builds its own
   `role="img"` accessible name from `describeManaCost`, so the placeholder does **not** add a
   second announcement for the cost. `ManaCost.tsx`'s own header names this story: *"APPEARANCE IS
   NOT DEV-VERIFIED IN THIS STORY … The look is checked at c4-3 / c4-7 / c4-9."*

4. **`DeckBadges` is the exact precedent for adding a component, and it costs three list edits.**
   A new module under `src/components/` is a **red `shell.test.ts` gate by design**
   (`:1232-1253`, git-derived): the commit must add it to `PRIMITIVES` with an **exhaustive** import
   list, bump `toHaveLength(15)`, and accept the presentation-only bans that come with membership —
   no hook of any family, no `fetch`, no `ref`, no `on*` prop, **no spread**, and a **type-only**
   `react` import. If it carries authored words it also joins `copy-rules.test.ts`'s `COPY_MODULES`
   (5 today). Discovering this after writing the component is the expensive order.

5. **`useCardEntry` is a pure selector that starts nothing, and this story is its first consumer.**
   `cards.ts:537`. Its deferral (`deferred-work.md:3295`) is homed here — and c4-2 already corrected
   the stated reason: `@testing-library/react@^16.3.2` **ships** and is used by `App.test.tsx` and
   `DeckBadges.test.tsx`. There is no dependency argument to make; the hook can be tested for real.

6. **`frontFace()` already exists and is already the repo's ` // ` split.** `deckGroups.ts:131`:
   `typeLine.split(/\s*\/\/\s*/)[0].trim()`. It is named for type lines but the operation is
   generic. Whether a placeholder splits the **name** the same way is Q5 — and c4-2's probe (b)
   is the warning attached to it: *the obvious fixtures do not discriminate the rule they appear to
   test.*

7. **Two `ui/tests/` guards already point at this story by name and describe what they do NOT
   gate.** `unknown-card-copy.test.ts:27-34`: *"The rendered placeholder. **c4-3 owns it**, along
   with the `"Unknown card"` string as a copy module … The day c4-3 lands, its copy module joins
   `COPY_MODULES` and the byte-for-byte assertion moves there."* And `named-card-copy.test.ts:33`:
   *"**c4-3 owns it** (the component) and **c4-4** the tile that fetches an image into it."* Both
   already assert the artefact half; this story owes the render half and the copy-module half.

8. **The two vitest projects and the `tsc -b` trap, unchanged.** `src/**/*.test.{ts,tsx}` → jsdom;
   `tests/**/*.test.{ts,tsx}` → node, and `gate-geometry.test.ts` forbids `.tsx` under `tests/`.
   Component tests are `.tsx` and live beside the component. `npx tsc -b --force` is what makes a
   cross-project import failure deterministic — `npm test` stays green through it.

### What the real data says (measured at `2a64231`, read-only)

**The three populations this story draws, and they are not the same size.**

| Variant | Reached by | Corpus population | Live-deck population |
| --- | --- | --- | --- |
| **named-card** (permanent) | `no_image_data` — the printing has no artwork at all | **79 of 38,261** | **0 of 2,027 rows** |
| **named-card** (transient) | `image_fetch_failed` — CDN timeout / non-2xx / not-an-image | any card | any card |
| **unknown-card** | `card_not_found`, and (c4-1 Q5) `invalid_request` on a card read | — | **0** dangling card refs |
| **loading well** | an `<img>` in flight — **c4-4 mounts it**, this story ships it | every card, first paint | every card |

So: **in a deck view, the named placeholder is only ever reached transiently**, and the unknown
variant is only ever reached by an id that did not come from a deck payload (Epic 6's agent pushes,
a stale id after a database refresh). Both are real; neither is reachable by opening a deck today,
and the story record should say so rather than implying the deck view exercises them.

**The 79, in detail — the fixtures come from here.**

| Property of the 79 no-image cards | Measured |
| --- | --- |
| `type_line` literally `'Card // Card'` | **79 of 79** |
| `mana_cost` blank (`''`) | **79 of 79** |
| Name is the same words twice (`X // X`) | **79 of 79** |
| Longest such name | **66 chars** (`Zabaz, the Glimmerwasp // Zabaz, the Glimmerwasp`-class) |
| Longest `type_line` among them | **12 chars** (`Card // Card`) |

**The layout extremes a placeholder must survive** (a 176px-minimum tile is the grid's floor,
UX-DR4):

| Property | Corpus | In live decks |
| --- | --- | --- |
| Longest card name | **141** (`Our Market Research Shows…Elemental`) | **56** (`Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel`) |
| Longest `type_line` | **91** (`Legendary Creature — Human Noble Warrior // Legendary Enchantment Creature — Saga Elemental`) | **88** |
| Most pips in one cost | **15** (B.F.M.) | **6** (`{1}{B}{B} // {1}{B}{B}`) |
| Longest cost string | **46** (`{X}{W} // {2}{R} // {2}{U} // {3}{B} // {1}{G}`) | 22 |
| Names containing ` // ` | **3,194** — of which **2,246** are `X // X` | 39 distinct cards / 65 rows |

**The truncation length is decided by a measurement, not by taste.**

| Prefix of the Scryfall printing uuid | Distinct values over all 38,261 ids | Collisions |
| --- | --- | --- |
| first **6** chars | 38,216 | **45** |
| first **8** chars | **38,261** | **0** |
| first 12 chars | 38,261 | 0 |

Eight is the shortest prefix that is unique across the whole shipped corpus, and it is also the
uuid's own first group — a boundary a reader can match against a log line without counting
characters. (The id is 36 chars; the full thing does not fit a 176px tile at any legible size.)

**The token layer, as committed.**

| Fact | Measured |
| --- | --- |
| `--radius-card` | `4.75% / 3.4%`, **zero consumers** in `ui/src` |
| Token inventory | **65**, pinned by set equality in `tokens.test.ts:265` — `--card-aspect` cannot join |
| `--type-micro` | `400 10px/1.3`, `--tracking-micro: 0.08em`, **`textTransform: uppercase`** in DESIGN.md |
| `--type-body-strong` | `700 14px/1.5`, **no** tracking sibling, **no** uppercase |
| `--surface-overlay` / `--surface-well` | `card-placeholder.background` / the well's background |
| `--text-tertiary` on `--surface-overlay` | **4.8:1 — zero headroom** (UX-DR41). The type line and the id are `text-secondary`, and DESIGN.md says why: *"the ID is the only identifying information — load-bearing, so never a de-emphasized tier."* |
| `--accent-dim` on `--surface-overlay` | **BANNED** (2.70:1). A stylesheet that references `--surface-overlay` **anywhere** may not reference `--accent-dim` at all (c2-7 AC 14, same-file scope) |

**The frontend gate baseline (verify it yourself in Task 0; do not trust this table).**

| Gate | Measured at `2a64231` |
| --- | --- |
| `npm test` | **970 passed, 41 files**, 6.0 s |
| `npm run lint` / `format:check` / `npx tsc -b --force` / `npm run build` | expected green |
| `uv run pytest -m "not integration"` | **2,447 passed, 1 skipped, 54 deselected** (c4-2's measurement; re-measure) |
| `PRIMITIVES` in `shell.test.ts` | **15** · `COPY_MODULES` in `copy-rules.test.ts` | **5** |
| Aliases exported by `src/api/schema.ts` | **9** |

> **One measurement artefact, carried forward so it is not diagnosed twice.** A `npm test` run on
> this machine has once reported `Error: Worker exited unexpectedly` with **no failing assertion**;
> the immediate re-run was green. It is a vitest worker crash, not a test failure. Re-run before
> investigating.

## Acceptance Criteria

### The shape — geometry that four later stories inherit

1. **Every placeholder is card-shaped: `63 / 88` aspect at `var(--radius-card)`** (FR-19, UX-DR4,
   UX-DR22, epic AC). Not approximately, and not a chrome radius. `--radius-card` gets its first
   consumer in this commit and it carries **no unit** — anything computing from it must not assume
   `px` (`tokens.css:158`).

2. **The geometry is written ONCE and shared, not repeated per variant** (Q2). The epic's own
   criterion is *"it occupies exactly the same footprint [as a real card face], so layout never
   reflows when art arrives"* (UX-DR36) — a claim about **two** things being identical, made in a
   story that ships only one of them. Three copies of `aspect-ratio` and `border-radius` is three
   places for c4-4's tile to drift from c4-3's well. Whatever the mechanism, **c4-4, c4-5 and c4-6
   must be able to consume it without copying it**, and the record must say how.

3. **No `--card-aspect` token.** `tokens.test.ts:265` is a set equality with a pinned count of 65
   derived from DESIGN.md's frontmatter blocks; `components.*` is not one of them. If this story
   believes the aspect belongs in the token layer, that is a DESIGN.md amendment plus a moved pin,
   argued — not a token added quietly.

4. **Layout never reflows when art arrives** (UX-DR36, epic AC). The placeholder and the well
   occupy the slot at full size **before** any image exists. The proof available in this story is
   **two instruments, and neither is `getComputedStyle`**: (a) a source read of the stylesheet in
   the `ui/tests/` node project, the idiom every guard in this repo already uses, asserting that the
   geometry declarations exist exactly where AC 2 says; and (b) a jsdom assertion that the rendered
   element **carries the class** that carries them. jsdom has no layout engine, so a
   `getComputedStyle(el).aspectRatio` there returns the empty string and **passes for the wrong
   reason** — the sixth time this epic has recorded that trap (c2-2 AC 17, c2-5 AC 4, c2-6 AC 4/5,
   c2-7 AC 21, c2-8 AC 21). Say which claim each instrument does and does not carry.

### The three variants

5. **The named variant renders the card name centred in `--type-body-strong`, the mana cost as pips
   above it, and the type line in `--type-micro` `--text-secondary`** (FR-19, UX-DR22, epic AC).
   The pips come from `ManaCost` — its **first consumer** — not from a second parser.

6. **It is never a broken-image glyph, a grey rectangle, a 1×1 pixel or a generic card back**
   (UX-DR22, AD-11, epic AC). The backend is already held to this in
   `test_routes_card_image.py`; this is the client half.

7. **The named variant is correct when two of its three parts are EMPTY, and TOTAL when a prop is
   absent.** All 79 permanent-population cards have `mana_cost = ''` and a 12-character
   `'Card // Card'` type line, so the name-only rendering is not an edge case — it is the *only*
   permanent case. No empty wrapper, no collapsed box, no stray gap: `ManaCost` already returns
   `null` for a blank cost, so the placeholder must not wrap it in an element that survives its
   absence. **And the totality is a measured lesson, not belt-and-braces**: c4-2's review found
   `DeckBadges` calling `format.trim()` behind a `!== null` check and throwing `Cannot read
   properties of undefined` on a partial deck — *"a presentation primitive that crashes the whole
   app on one absent prop is the FR-13 posture inverted, and totality here costs one keyword."*
   `typeof x === 'string'`, in the same spelling, for every string prop. Emptiness uses `filled()`
   or a `typeof`+`trim()` string check as appropriate — **not truthiness** (`AppShell` uses
   `filled()` on `deckName` precisely because a default fires only on `undefined`), and not a second
   emptiness helper.

8. **The unknown variant's name slot reads `"Unknown card"` with the truncated id in
   `--text-secondary`, and the variant vocabulary is `states.ts`'s** (UX-DR22, UX-DR33, epic AC;
   `deferred-work.md:2014`). The component's variant type is derived **from `PlaceholderKey`**, so
   a third key added to `states.ts` is a `tsc` failure here. This is the consumption that ledger
   entry makes conditional — *"if c4-3 does not consume the classification, delete it"* — and the
   record must state which of the two happened.

9. **The truncated id is 8 characters, and the number carries its measurement** (AC data table).
   Eight is the shortest prefix unique across all 38,261 ids (six collides 45 times) and it is the
   uuid's own first group. A bare number in this codebase is a defect; this one travels with its
   arithmetic.

10. **The loading well uses the same card shape on `--surface-well`, with NO text and NO spinner**
    (UX-DR22, UX-DR36, epic AC; `EXPERIENCE.md:72` — *"No copy. Wells stay silent."*). Silent means
    silent in the accessibility tree too: an empty well with an accessible name is a screen reader
    announcing a rectangle. And it is a **deliberate hole in the surface ramp** — declare that
    beside the rule (`surfaces.ts::stepsExactlyOne` is directional and correctly says `false` here),
    so a reviewer does not read a correct well as a UX-DR1 violation.

### Copy, announcement and inspectability

11. **`"Unknown card"` lands in a declared copy module, and `COPY_MODULES` gains its entry with a
    reason** (`copy-rules.test.ts:99`, decide-once ruling #1 of c2-9). The comment naming *"c4-3's
    'Unknown card'"* becomes a gate in this commit. Everything else this component shows — a card
    name, a type line, an id — is **data**, not copy, and must not be smuggled into the copy module
    to look tidy. Note the guard has **two halves**: the file half collects prose (two
    space-separated words — `"Unknown card"` qualifies), and the **attribute half** collects *every*
    string reaching `aria-label`, `alt`, `title` and six other read-aloud attributes **whatever its
    shape**, so an accessible name written as a literal is caught even when it is one word.

12. **UX-DR4's exclusivity half becomes a gate** (Q3): nothing outside the declared card-shaped
    files may spend `--radius-card`, and no card-shaped file may spend a chrome radius. The idiom
    already exists — `token-usage.test.ts:967`'s `--mana-*` data-ink allowlist, which is an
    allowlist of **files** with a reason per entry, plus the declared limits it cannot see. Build it
    in that shape or decline it with a reason; the sentence is in DESIGN.md either way and today
    nothing checks it.

13. **The named placeholder exposes the card NAME to assistive technology; the well exposes
    nothing** (UX-DR22, `EXPERIENCE.md:157` — *"Placeholders expose the same name to assistive
    tech"*). The cost's announcement is `ManaCost`'s `role="img"` name and must not be duplicated by
    a second label on the wrapper.

14. **Inspectability is DECLARED, and the unknown variant's refusal is structural rather than a
    comment** (UX-DR22, epic AC): *"named placeholders behave as a normal tile under the inspection
    contract; the unknown-card variant **cannot be inspected**, because there is nothing to show."*
    The inspection contract itself is **c4-5's** and the tile is **c4-4's**, so this story cannot
    implement it — but it must not ship a shape that makes the wrong thing easy. A
    presentation-only component takes no handlers at all (`shell.test.ts` bans `on*` outright), so
    the honest form of this AC is: the component's API gives c4-4 no way to make an unknown
    placeholder inspectable by accident, and the record names where the contract lands (Q6).

### Consuming the cache, without re-deriving it

15. **`useCardEntry` gets its first consumer and its first test** (`deferred-work.md:3295`). Whether
    the component subscribes or the caller does is Q7 — but the hook is exercised for real in this
    commit, with `@testing-library/react`, which **already ships** (the c4-2 correction).

16. **Nothing in this story re-derives a placeholder from a wire token.** `entryFor` already
    computed `placeholder`; a `switch (entry.reason)` or a second `PLACEHOLDER_FOR_*` map in a
    component is the drift c4-1 wrote that field to prevent (`cards.ts:151`).

17. **Nothing in this story fetches.** No image bytes, no card read, no deck read.
    `posture.test.ts:328`'s exhaustive door list stays `['src/api/client.ts']` with **no edit**, and
    `shell.test.ts` bans `fetch(`/`WebSocket(` in every listed component. c4-4 owns the `<img>`.

18. **Nothing in this story writes the store** (AD-12). `ui/tests/store-writes.test.ts` (c4-2's
    gate) stays green with no allowance added.

### The typography traps

19. **`font: var(--type-micro)` ships with BOTH companions in the same rule block** —
    `letter-spacing: var(--tracking-micro)` and `text-transform: uppercase` — because
    `findRoleWithoutCompanions` derives the requirement from DESIGN.md's own `textTransform:` key
    and from the existence of the `--tracking-micro` sibling. A split pair is a named failure.

20. **The truncated id's type role is RULED, not defaulted** (Q4). The backend's card-id pattern is
    lowercase-only by design, so `text-transform: uppercase` on a uuid puts an id on screen that the
    route would refuse. Choose a role whose contract does not uppercase (and pair it correctly if it
    has companions), or accept the uppercase with the reason written down. Not deciding is not an
    option.

21. **No numeric role without its features.** If any count or number reaches this component, `font:
    var(--type-numeric)` and `font-variant-numeric: var(--type-numeric-features)` are applied
    **together** (UX-DR3, `findUnpairedNumericRole`). The quantity badge is **c4-4's**, not this
    story's — say so rather than half-building it.

### Boundaries — what this story must not do

22. **No grid, no tile, no `<img>`, no quantity badge, no flip control, no detail panel, no
    inspection, no hover, no focus ring — and NO MOTION.** The grid and the tile are **c4-4**, the
    detail panel **c4-5**, the flip control **c4-6**, the deck list **c4-7**, the keyboard floor
    **c4-11**, the empty-deck state **c4-12**. UX-DR36's *"images fade in over the pulse duration"*
    is about an `<img>` this story does not draw, so a `transition` or `animation` here is
    pre-empting c4-4 — and the guards agree: `animation-iteration-count` may only be `1`, `infinite`
    and `alternate` are banned in every spelling, and a literal duration is a stylelint error. Like
    c4-1's cache and c4-2's derivation, this story ships **declared and unmounted** — that is the
    shape, not a shortfall (and it is what makes Q1 a real question rather than a formality).

23. **`AppShell.tsx`, `App.tsx` and the fifteen listed primitives are untouched as source.**
    `ManaCost` and `ManaPip` gain their first **consumer**, not an edit. If either genuinely needs a
    change to be consumable, that is a finding to record, not a quiet edit — `shell.test.ts` pins
    their exhaustive import lists.

24. **No new dependency, no second state or data-fetching library, no second code generator**
    (AD-12), asserted by `package-contract.test.ts`. `@testing-library/react` already ships.

25. **No wire change.** This story consumes shapes that exist. If nothing under `src/` changes, the
    five Python gates are byte-identical to baseline and the record says so explicitly.

### The gates, the artifacts and the ledger

26. **Every `deferred-work.md` entry homed on `c4-3` is enumerated with a disposition each** (C2
    retro ruling **R2**: inherited deferrals are ACs *at context time*). They are listed in §"The
    inherited deferrals" below. For each: **implement**, **re-home by name**, or **decline with a
    reason**. "Not mentioned" is a failure of this AC.

27. **The SPA bundle and the `plugin/` mirror are rebuilt and their change is MEASURED.**
    `npm run build` writes into `src/companion/app/static/` — **it mutates `src/`** — and
    `scripts/build_plugin.py` regenerates the mirror; CI drift-checks both. Record before/after
    hashes. A new stylesheet means the **CSS changes**; report both halves.

28. **Every AC above has a test, in the project that can see what it asserts.** Component tests are
    `.tsx` beside the component (jsdom); guard tests belong in `ui/tests/` (node) and must respect
    the `tsc -b` cross-project import trap. **State plainly which claims are NOT machine-checkable
    here** (the pixel ones) and where they land instead — an undeclared limit reads as coverage
    (`copy-rules.test.ts:52`).

29. **Evasion probes, in the manner this epic has established.** For each new guard or contract,
    write the probe that *should* defeat it and prove it does not; record every probe **including
    any that passed** — c4-2's probes (b), (d2) and (g) all passed and were the three most valuable
    lines in that record. At minimum: (a) a card radius spent on a chrome element; (b) a chrome
    radius spent on the placeholder; (c) the aspect ratio deleted from one variant only; (d) the
    unknown variant rendered with a card's real name (the copy-paste that type-checks); (e) the well
    given an accessible name; (f) a `--type-micro` block with its tracking but not its
    `text-transform`; (g) the variant union widened to a bare `string`, defeating AC 8's
    `states.ts` coupling.

30. **All five frontend gates and all five Python gates are green at the end, with counts recorded
    before and after.** `npm run lint`, `format:check`, `npx tsc -b --force`, `npm test`,
    `npm run build`; `uv run pytest`, `ruff check`, `ruff format --check`, `mypy src/`,
    `mypy src/ --platform win32`.

## Tasks / Subtasks

- [x] **Task 0 — Baseline, measured not assumed** (AC 30; standing agreement)
  - [x] Confirm `feat/companion-c4` is at **`2a64231`**; cut `feat/companion-c4-3-card-placeholders`
        from it
  - [x] Run and record with **durations**: `uv run pytest -m "not integration"` (expect **2,447
        passed, 1 skipped, 54 deselected**), `ruff check`, `ruff format --check`, `mypy src/`,
        `mypy src/ --platform win32`
  - [x] From `ui/`: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test` (expect
        **970 passed, 41 files**), `npm run build`. On a `Worker exited unexpectedly` with no
        failing assertion, re-run before investigating
  - [x] Record the pre-change SHA-256 of `src/companion/app/static/assets/*`, `index.html` and the
        `plugin/` mirror (AC 27)
  - [x] **Verify §"What the real data says" yourself** — at minimum the 79/79/79 shape of the
        no-image population and the 8-character uniqueness. If either has changed, the fixtures and
        AC 9's number change with it
  - [x] **Read, in this order:** `src/state/cards.ts` end to end (the `CardEntry` union and
        `PLACEHOLDER_FOR_CARD_REFUSAL`), then `src/components/StatePanel/states.ts`, then
        `src/components/DeckBadges/{DeckBadges.tsx,.css,.test.tsx}` as the shape to copy, then
        `src/components/ManaCost/ManaCost.tsx`, then `ui/tests/shell.test.ts:1109-1330` and
        `ui/tests/token-usage.test.ts:443-530` + `:560-700`. They are the specification

- [x] **Task 1 — Decide the geometry's home BEFORE writing a component** (AC 1, 2, 3; Q2)
  - [x] Answer Q2 and write the answer where c4-4's author will read it
  - [x] Prove the aspect and the radius are written once; add the consumer-side note to
        `ui/README.md` so c4-4/c4-5/c4-6 inherit rather than copy
  - [x] Confirm `border-radius: var(--radius-card)` passes stylelint's radius allowlist and that no
        `--card-aspect` token was added (AC 3)

- [x] **Task 2 — The component, in the listed-primitive posture** (AC 5, 6, 7, 8, 9, 10, 13, 14)
  - [x] Decide the component's shape (Q8) and its variant type **from `PlaceholderKey`** (AC 8)
  - [x] Add it to `shell.test.ts`'s `PRIMITIVES` with an exhaustive import list and bump
        `toHaveLength(15)` → 16 **in the same commit as the file** — the guard is git-derived and
        will be red until then *(shipped as 15 → **17**: the component AND its copy module both
        join, per the `DeckBadges`/`Footer` precedent — corrected at code review)*
  - [x] Name slot, pips above, type line below; nothing renders an empty wrapper (AC 7)
  - [x] The well: same shape, `--surface-well`, no text, **nothing in the a11y tree** (AC 10)
  - [x] Declare the surface-ramp hole beside the well's rule (§"What this story really is" item 5)

- [x] **Task 3 — The copy module and the typography rulings** (AC 11, 19, 20, 21)
  - [x] `"Unknown card"` into a declared copy module; add the `COPY_MODULES` entry with its reason
        (5 → 6) and check `unknown-card-copy.test.ts`'s "the day c4-3 lands" note is now true
  - [x] Rule Q4 (the id's type role) and record the ruling **in the CSS**, with the lowercase-only
        route pattern as its reason
  - [x] Every `--type-micro` block carries both companions (AC 19)

- [x] **Task 4 — The exclusivity gate** (AC 12; Q3)
  - [x] Build the UX-DR4 guard in `token-usage.test.ts`'s allowlist idiom, or decline with a reason
  - [x] Prove it FIRING and NOT FIRING (the standing non-vacuity pairing agreement), with fixtures
        under `ui/tests/fixtures/css/`
  - [x] Declare what it cannot see — inline geometry, markup-level spends, cross-file composition

- [x] **Task 5 — Consuming the cache** (AC 15, 16, 17, 18)
  - [x] Answer Q7; give `useCardEntry` its first real test
  - [x] Prove no fetch, no store write, and `posture.test.ts` / `store-writes.test.ts` green with no
        edit

- [x] **Task 6 — The eye-check that four ledger entries are waiting on** (Q1)
  - [x] Answer Q1 and **do whichever half is doable here**, recording the outcome including
        "looks right"
  - [x] The five unverifiable `ManaPip`/`ManaCost` claims by name: the pip being a **circle**, the
        hybrid **hard-stop gradient** reading as a split rather than a blur, the 13px glyph in a
        16.25px circle, the **wide case** (`{1000000}`, `{HW}`) growing rather than clipping, and
        **row wrapping** — check `{1000000}` and `{W/U}` first
  - [x] The **CVD** question (Medium, ledgered): do plain colour circles read as distinguishable to
        a sighted colour-vision-deficient user? Brad's call, against a real screen
  - [x] The **63:88 footprint** claim (AC 4) and the two longest-name cases (141 / 56 chars) at the
        176px grid floor

- [x] **Task 7 — Evasion probes** (AC 29)
  - [x] Probes (a)-(g) at minimum; record every probe and its outcome, **including any that passed**

- [x] **Task 8 — The ledger, the docs and the artifacts** (AC 26, 27, 30)
  - [x] Give each inherited deferral a disposition (AC 26), and state explicitly whether the
        `states.ts` classification was **consumed** or **deleted** (AC 8)
  - [x] Update `ui/README.md`: the *"Not here yet"* seam, the primitives count, the copy-module
        paragraph, the blind-spot table (a new guard's declared limits), and the card-geometry note
        c4-4 will read
  - [x] Rebuild the bundle and the `plugin/` mirror; record before/after hashes (AC 27)
  - [x] Re-run all ten gates; record counts and durations

### Review Findings

Three-layer review 2026-08-04 (Blind Hunter / Edge Case Hunter / Acceptance Auditor). 31 raw
findings, deduplicated to 14; 3 dismissed as noise.

- [x] [Review][Decision] **RULED: ratified as-is (Brad, 2026-08-04).** The copy-rules per-module non-vacuity was WEAKENED, not extended —
      `toBeGreaterThan(3)` → `> 0` per module, compensated by a total `> 20` across all modules.
      Declared and argued (a one-string module fails `> 3` for being correct), but it retires the
      "each table-of-words module stays populated" contract for all six modules, and the `20` is
      tied to nothing. Options: ratify as-is / restore per-module strength via a declared
      expected-minimum map / other. [ui/tests/copy-rules.test.ts:400-426]
- [x] [Review][Decision] **RULED: split to master (Brad, 2026-08-04) — committed there as `2f543ed`; the story branch's `.gitignore` is byte-pristine again.** A stray `.gitignore` hunk (`/graphify-out/` block) rode in the story
      diff and is absent from the Dev Agent Record's File List — unrelated to c4-3. Options:
      commit it separately to master per the standing small-docs convention / keep it here and add
      it to the File List with a sentence. [.gitignore:1-18]
- [x] [Review][Decision] **RULED: ratified (Brad, 2026-08-04)** — a string-narrowing helper, not a competing emptiness idiom. `given()` is arguably the "second emptiness helper" AC 7 bans. The
      docstring pre-argues the distinction (string-narrowing vs `filled()`'s ReactNode boolean)
      and the spelling inside is the sanctioned `typeof`+`trim()`, but the record makes this call
      on the AC's behalf. Options: ratify the argument / inline the check three times.
      [ui/src/components/CardPlaceholder/CardPlaceholder.tsx:142]
- [x] [Review][Patch] HIGH — the patch is not self-contained: both `index.html`s now point at
      `index-CdikAaRP.js` / `index-DGjO7yGD.css`, the old assets are deleted, and the new assets
      are UNTRACKED (`??`). Committed as-is this ships a broken app; `git add` the four new asset
      files before commit. [src/companion/app/static/assets/, plugin/server/src/companion/app/static/assets/]
- [x] [Review][Patch] MEDIUM — the `Tile` exemplar (billed as "what c4-4's real tile will look
      like") falls through to the loading well for any `unknown`-status entry that still holds a
      summary (`database_unavailable` after seed: summary retained, status no longer `'summary'`)
      and for `placeholder === 'named-card'` (both image tokens) — the seeded name vanishes into a
      silent well. The "leaves a summary standing" test hides it by asserting only the label's
      absence, never the name's presence; and `no_image_data` / `image_fetch_failed` are never
      driven through the cache path at all. Fix the exemplar's mapping, assert the name is
      visible, add the image-token cache-path test.
      [ui/src/components/CardPlaceholder/CardPlaceholder.test.tsx:347-366, 424-440]
- [x] [Review][Patch] `given()` validates on `trim()` but returns the UNTRIMMED value, so a
      whitespace-padded id passes the guard and `slice(0, 8)` renders a short prefix (`'  b3a40e'`
      — six real chars), defeating the measured uniqueness. Return `value.trim()`.
      [ui/src/components/CardPlaceholder/CardPlaceholder.tsx:142]
- [x] [Review][Patch] The "exactly once" geometry test scans other blocks for `aspect-ratio`
      only — a CARD_SHAPED file re-declaring `border-radius: var(--radius-card)` passes both
      halves and the exactly-once test. Extend the scan to the radius.
      [ui/tests/token-usage.test.ts:1184-1214]
- [x] [Review][Patch] The silent-half test's first assertion is vacuous:
      `findCardRadiusOutsideCardShape([...CARD_SHAPED.keys()])` filters out every input by
      construction (`!cardShaped.has(file)`), so it passes for any implementation. The real
      coverage lives at the full-tree scan; replace or drop the decorative expect.
      [ui/tests/token-usage.test.ts:2028]
- [x] [Review][Patch] Three real blind spots are missing from the guards' own declared-limits
      prose: (1) a card-shaped file that never joins `CARD_SHAPED` and rounds itself with
      `--radius-md` passes both halves — the likeliest real drift for c4-4/5/6; (2) the uppercase-
      id guard reads only the exact `.card-placeholder-id` block, so `text-transform` inherited
      from an ancestor selector is invisible; (3) `stripComments` handles `/* */` only, so a `//`
      line comment naming `var(--radius-card)` in a shipped `.tsx` fires the markup guard on
      prose. Declare all three. [ui/tests/token-usage.test.ts:1757-1769, 1216-1256, 67]
- [x] [Review][Patch] `findCardRadiusInMarkup` takes no injectable `read` seam (its two siblings
      do), so its file-scan wiring is never proven firing against the function itself — only the
      predicate is tested on inline strings. Add the seam and a firing probe.
      [ui/tests/token-usage.test.ts:859-868]
- [x] [Review][Patch] The radius classifiers are case-insensitive (`/^--radius-card$/i`) but CSS
      custom properties are case-sensitive — `var(--RADIUS-CARD)` (undefined) is classified as
      the card radius and mis-policed in both directions. Drop the `/i`.
      [ui/tests/token-usage.test.ts:816-817]
- [x] [Review][Patch] Dead class hooks: `card-placeholder-named` and `card-placeholder-unknown`
      are matched by no stylesheet rule and no test selector — unexplained residue in a repo that
      deletes what nothing consumes. Remove or justify in place.
      [ui/src/components/CardPlaceholder/CardPlaceholder.tsx:163,188]
- [x] [Review][Patch] Record/docstring accuracy bundle (six small edits): (1)
      `CARD_ID_PREFIX_LENGTH`'s uniqueness is measured over the corpus, but the unknown variant
      renders precisely non-corpus ids — add the caveat sentence; (2) vertical clipping
      (`overflow: hidden` + fixed 63:88 + `justify-content: center` clips a too-tall stack at
      both edges) is undeclared — extend the existing overflow-wrap ledger residue; (3) whether a
      whole view of `aria-hidden` wells may be silent to AT during first paint is a composition
      question nobody owns — home it on c4-4 in the ledger; (4) probe (c) was transformed
      (c1/c2), not run as specified — say so in the record; (5) the ledger's index sentence
      claims all dispositions live "beside their own entry above" but three live only in the new
      section; (6) Task 2's "15 → 16" arithmetic is stale — shipped is 15 → 17.
- [x] [Review][Defer] Running `tests/token-usage.test.ts` standalone crashes the runner
      (cross-project import resolution picks the wrong vitest project), which once made six
      probes report as firing when nothing had asserted — deferred, pre-existing vitest
      project-resolution behaviour, already ledgered with the "prove a guard fires via full
      `npm test`" rule. [ui/tests/token-usage.test.ts]

Dismissed as noise (3): the comment-wording coupling in "reads code, not the prose" (deliberate,
argued in the Dev Agent Record — the alternative is a tautological test); the Q4 gate reading only
the `src/` copy of `cards.py` (the `plugin/` mirror is generated and drift-checked by CI, so
divergence cannot land silently); the "reachable from every token" loop's thin runtime half (the
set-equality assert directly above is what carries the claim).

## Dev Notes

### Decide-once rulings this story inherits (do not re-derive)

1. **FR-13, in the contract's own words** (`contracts.py:161-165`): `card_not_found` is *"the
   **only** token whose destination is not a panel: the view that referenced the card renders
   normally and shows an **'Unknown card'** placeholder in that one slot, with no banner and no
   apology. One unknown card must never fail a whole view or a whole push. **The placeholder is
   built in c4-3.**"*

2. **The two image tokens render IDENTICALLY and are still two tokens** (`states.ts:111-116`,
   `contracts.py`): `no_image_data` is permanent, `image_fetch_failed` is transient and
   negative-cached with backoff (30 s → 300 s since c3-8). *"The pixels are identical … but only
   this one may ever be retried."* This story draws one thing for both, and that is correct.

3. **AD-11 / the backend's own promise:** never a grey rectangle, a 1×1 pixel or a generic card
   back. `test_routes_card_image.py` holds the backend to it; AC 6 is the client half.

4. **c4-1 Q5:** a token's UI destination may be context-dependent, and the way to record that is a
   per-context map **beside the consumer**, with `states.ts` untouched — adding `invalid_request` to
   `PLACEHOLDER_FOR_REASON` would break `ReasonClassificationsAreDisjoint`, *"and rightly."*

5. **c2-9 Q4 / the primitive posture:** presentation-only means no hook of any family (`use()`
   included), no `fetch`, no handler, no `ref`, **no spread**, and a **type-only** `react` import.
   `filled.ts` is the one exemption and it was argued in the open.

6. **UX-DR41 / the ramp is closed at four:** `--text-tertiary` on `--surface-overlay` is 4.8:1 with
   zero headroom. The type line and the truncated id are `--text-secondary` and DESIGN.md gives the
   reason for the id explicitly — *"load-bearing, so never a de-emphasized tier."*

7. **c2-4's literal bans are gates, not preferences:** every colour, shadow, radius, spacing,
   duration and type value goes through a token, enforced by stylelint with a message naming the
   family. `aspect-ratio` has **no** rule and **no** token — which is why AC 2 is about a shared
   class rather than a literal ban.

### The thirteen things this story must not break

1. `shell.test.ts`'s **git-derived coverage guard** (`:1232-1253`) — any new `src/components/`
   module is red until `PRIMITIVES` lists it, with its exhaustive import list and the count bumped
   (15 → 16). This is a gate, not a review note.
2. `shell.test.ts`'s per-primitive bans: hooks by family, `fetch`/`WebSocket`, `on*` props and JSX
   attributes, `ref` in **both** positions, rest/spread, and the non-type `react` import.
3. `posture.test.ts`'s **exhaustive** network-door list (`:308-334`) and its cross-tree
   value-import rule (a component may take a **type** from anywhere, a **value** only from its own
   tree).
4. `copy-rules.test.ts` — the file half (prose only in `COPY_MODULES`), the content half (every
   string literal, prose-shaped or not), and the `!`/emoji/"something went wrong" ban across all of
   `src/`.
5. `token-usage.test.ts`'s `findRoleWithoutCompanions` (tracking **and** uppercase, derived from
   DESIGN.md), `findUnpairedNumericRole`, `findAccentDimInOverlayFile`, the nesting ban, the
   pulse/loop ban and the `--mana-*` data-ink allowlist.
6. `tokens.test.ts`'s **set equality** on the 65-token inventory.
7. `lint-gates.test.ts` — the stylelint literal bans and the **focus-ring** ban (no `outline: none`
   in any spelling), plus the ESLint inline-style ban and the a11y gate.
8. `gate-geometry.test.ts` — no `.tsx` test under `tests/`, no test file outside the two roots, no
   `.jsx`/`.mjs`/`.cjs`.
9. `states.ts`'s **six** type-level asserts. Consuming `PlaceholderKey` must not require editing
   that file; if it does, the design is wrong.
10. `unknown-card-copy.test.ts` and `named-card-copy.test.ts` — both already green, both naming this
    story. Neither may be weakened to accommodate the component; the copy-module half is **added**
    beside them.
11. `store-writes.test.ts` (AD-12's "nothing else writes the store"), and `package-contract.test.ts`.
12. `wire-contract.test.ts` — `Card`, `CardSummary`, `CardFace` and every other `components.schemas`
    name is banned outside `src/api/`. A component takes plain props or a **type-only** import from
    `src/api/schema.ts`; a locally-declared `interface Card` is precisely what that gate rejects.
13. The **committed bundle + `plugin/` mirror** drift gates. `npm run build` mutates `src/`.

### Source tree — what exists, what this story touches

```
ui/src/
  components/
    <new>/           ← the placeholder(s) + stylesheet. A new module here is a RED shell.test.ts
                       gate until PRIMITIVES lists it — decide the shape and the home BEFORE
                       writing (Q8), and add the list entry in the same commit
    StatePanel/
      states.ts      ← READ ONLY. `PlaceholderKey` is the variant vocabulary this story consumes;
                       editing this file to make consumption work is a design smell
    ManaCost/        ← first CONSUMER, not an edit. `cost?: string | null`, total, self-announcing
    ManaPip/         ← reached through ManaCost; its five unverifiable claims are Task 6's
    DeckBadges/      ← the shape to copy: three plain props, one stylesheet, one copy-module entry
    AppShell/        ← UNTOUCHED
  state/
    cards.ts         ← READ ONLY. `CardEntry`, `useCardEntry`, `entry.placeholder`
    deckGroups.ts    ← `frontFace()` already exists, if Q5 says the name splits
  styles/
    tokens.css       ← UNTOUCHED. `--radius-card` gets its first consumer; no token is added
  App.tsx            ← UNTOUCHED (AC 22 — nothing mounts this story)
ui/tests/            ← node project. The new UX-DR4 guard lands here with FIRING + NOT-FIRING
                       fixtures under fixtures/css/. Three list edits: shell.test.ts PRIMITIVES
                       (15→17, shipped — component + copy module), copy-rules.test.ts
                       COPY_MODULES (5→6)
```

**Backend: read-only.** Every token, endpoint and contract this story consumes already ships.
Unless a ruling here changes a Pydantic model — none is expected — nothing under `src/` changes
except the built bundle.

### The inherited deferrals (AC 26 — give each a disposition)

Search `deferred-work.md` for `c4-3`. Summarised, with the line where each lives:

1. **`ManaPip` / `ManaCost` APPEARANCE is not dev-verified** (`:1400`, **Medium**) — *"Homed at the
   first consuming stories … **c4-3** (card placeholders — the first render of a cost anywhere)."*
   Five named claims, listed in Task 6. See Q1.
2. **For sighted colour-vision-deficient users, a pip's colour IS its sole carrier** (`:1430`,
   **Medium**) — *"Homed at the **c4-3 eye-check**."* Levers if it fails: a glyph-slot letter (the
   mechanism Phyrexian already uses) or a DESIGN.md amendment. Brad's call.
3. **The ` // ` split-card separator is spoken as the literal characters** (`:1421`, Low) —
   `describeManaCost` says *"black // black"*. *"Homed at **c4-3/c4-7**, where a split card first
   renders and the phrasing can be decided against something real."* Note the sharpened data: **all
   79** permanent-placeholder cards are split-named, so this is more live here than the entry knew.
4. **Whether copy is second-person and blameless is REVIEW'S, permanently** (`:1509`, Low) — *"A
   reviewer of c2-10, **c4-3**, c4-12 and c6-6 must READ the copy."* Honour it; it does not close.
5. **79 cards carry no image data anywhere — the placeholder's measured population** (`:2005`,
   Low) — *"**Home: c4-3** … which now knows the unknown-card variant and the no-image variant are
   different populations reached by different routes."* This story adds the shape of those 79.
6. **The `states.ts` classification is gated by the compiler but read by nothing** (`:2014`, Low) —
   *"**stays c4-3's** … **If c4-3 does not consume the classification, delete it.**"* See AC 8; this
   is the entry that most demands an explicit sentence in the record.
7. **A malformed card id from DATA renders nothing at all** (`:2090`) — **RESOLVED at c4-1**, with
   *"**c4-3 renders the placeholder**; the token and the destination are waiting for it."*
   Disposition: read it and confirm the render arrived.
8. **`Card` is banned with no sanctioned alias** (`:2113`) — **RESOLVED at c4-1** (nine aliases
   ship). Disposition: confirm this story needs none, or add one **with a docstring naming its
   consumer**.
9. **`card_faces` is untyped on the wire** (`:2220`) — **RESOLVED by c3-5**; `CardFace` ships with
   `extra="allow"`. *"Home: c3-5 or c4-3, whichever consumes a face first."* Disposition: state
   whether this story consumes a face at all (it should not — DFC faces are **c4-6's**).
10. **`useCardEntry` is untested** (`:3295`) — *"Home: c4-3 (first consumer)."* The stated reason is
    **false** and c4-2 corrected it: the testing library ships. See AC 15.
11. **A `ui/tests/` file may import an app module only if that module has no relative imports**
    (`:2105` region, **Medium**) — re-homed at c4-1 to *"the first story that actually imports a
    real `src/` module into `ui/tests/`"*. If this story's new guard reads source as **text** (the
    idiom every other guard uses), it does not fire — say so, measured, with `npx tsc -b --force`.
12. **C3 retro carried manual-testing items** — the C4 checklist inherits A3–A6 (the four unseen
    state panels). This story adds nothing to that list except its own eye-check outcomes.

### Project structure notes — the conventions a new component inherits

- **Directory per component**: `src/components/X/X.tsx` + `X.css` + `X.test.tsx`. Named exports
  only, no barrels, no default export except `App.tsx`'s.
- **Class names are flat kebab-case prefixed with the component** — `card-placeholder-name`, never
  `card-placeholder__name` (stylelint `selector-class-pattern` is an **error**: 12 of them on one
  stylesheet, measured at c2-6).
- **`verbatimModuleSyntax` is on** — `import type` for types, always. In a listed primitive the
  `react` import must be type-only or absent; **absent is the stronger claim** (`DeckBadges`,
  `Footer` and `ManaPip` all achieve it).
- **Docstrings are Google-style and carry the arithmetic.** *A bare number in this codebase is a
  defect* — the 8-character truncation, the aspect ratio and any spacing choice each travel with
  the reason that produced them.
- **Every stylesheet opens with a comment naming its story and the UX-DR rules it implements**, and
  states what it deliberately does not own (`DeckBadges.css` is the model: *"ONE RULE, and no
  layout"*).
- **Prettier, ESLint and stylelint are gates, not preferences**, and `ui/.gitattributes` forces LF.

### Open questions — answer these before writing code

**Q1 — This story mounts nothing, so where does the eye-check happen?**
*Proposed:* **pay it here on a throwaway harness, and re-home the in-composition check to c4-4 by
name.** Rationale: four ledger entries (two of them **Medium**) are homed on "the c4-3 eye-check",
and every one of them is a claim about **CSS and glyph rendering**, not about composition — the pip
being a circle, the hybrid gradient's hard stop, the 13px-in-16.25px ratio, the wide case, the wrap,
and whether plain colour circles are distinguishable to a CVD reader. All of those are answerable by
rendering the **built stylesheet** against hand-written markup in Edge, screenshotting, and
discarding the harness — which is a **measurement**, not shipped code, and is the same instrument
c4-2 used on `Badge`. What such a harness cannot answer is whether a placeholder sits correctly in a
grid beside a real card face (AC 4's "same footprint"), because there is no grid until **c4-4** —
so that half re-homes, by name, with the two longest-name cases attached. *The alternative* —
re-home everything to c4-4 — is defensible and cheaper, but it moves an eye-check for the **third**
time and lands it in the story with the largest surface in the epic, which is where it will be
skipped. **Whichever way, the answer is recorded and the ledger entries are updated in this commit.**

**Q2 — Where does the card geometry live so that c4-4, c4-5 and c4-6 cannot drift from it?**
*Proposed:* **one shared CSS class in one stylesheet, consumed by class name, with the rule that no
card-shaped element writes `aspect-ratio` or `border-radius` of its own.** Rationale: a token is
banned (AC 3 — the inventory is a pinned set equality); a per-component copy is three copies of the
one value UX-DR4 calls *exact and exclusive*; and the epic's own AC is a claim that two components
are pixel-identical, which is only structurally true if there is one declaration. A shared class
also gives Q3's exclusivity gate something to allowlist — a **file** rather than a growing list of
components. *The alternatives:* a CSS `@property`/custom property defined in the component
stylesheet (still one file, but invisible to the radius allowlist stylelint already enforces), or
each component writing both values (rejected: it is the drift the AC exists to prevent). **Note the
open cost either way:** a shared class means c4-4's tile imports a stylesheet it does not own, which
is a small break from the directory-per-component convention and must be argued in the record rather
than discovered by a reviewer.

**Q3 — Does this story build the UX-DR4 exclusivity gate?**
*Proposed:* **yes, in `token-usage.test.ts`'s existing allowlist idiom**, with a reason per entry
and its limits declared. Rationale: the rule is one sentence in DESIGN.md (*"nothing else borrows
the card radius, and cards never borrow a chrome radius"*), it is checkable exactly the way the
`--mana-*` data-ink rule is checkable, and **this is the commit where it stops being vacuously
true** — before this story nothing spends `--radius-card` at all. Building it later means building
it against four consumers instead of one. *The alternative* — decline and leave it to review — is
what the epic has already found wanting three times ("the wiring is right and nothing asserts the
wiring"). If declined, it must be declined **with a named home** and a ledger entry, not passed
over. **Either way, declare what the guard cannot see**: geometry applied from markup, an inline
style (already banned by ESLint), and cross-file composition.

**Q4 — What type role carries the truncated id, given that `--type-micro` is uppercase?**
*Proposed:* **not micro.** A uuid prefix is data the reader may retype, and the route pattern is
`[0-9a-f]` **lowercase-only by an explicit ruling** — so uppercasing it puts a value on screen that
the backend refuses. `--type-numeric` is the closest honest role (13px, no tracking sibling, no
uppercase) **but it must ship with `font-variant-numeric: var(--type-numeric-features)` in the same
block** (UX-DR3's gate) — which is arguably right anyway for a hex string. `--type-body` is the
alternative if 13px reads too large beside 10px micro. Rationale: this is the same class of finding
as c2-10's *"the legal sentence renders all-caps"* and c4-2's badge-count arithmetic, and it has a
sharper edge because the rendered value is **actionable data**. *The alternative* — keep micro and
accept the uppercase — is defensible (the id is for matching against a log, and browsers copy the
untransformed source text) **only if written down as accepted**, with the lowercase-only route
pattern named. Do not leave it to default.

**Q5 — Does the named placeholder split a `X // Y` NAME to its front face?**
*Proposed:* **no — render the name the payload carries, and record why.** Rationale: `CardSummary`
carries one `name` and no `card_faces`, exactly as c4-2 found for `type_line`; UX-DR19 asks a **deck
row** to show the front face's name and UX-DR22 asks the placeholder for *"the card name"*, which is
what the client holds. Splitting would render `Memory Lapse` for a card the deck list, the detail
panel and the alt text all call `Memory Lapse // Memory Lapse` — four surfaces, two names.
`EXPERIENCE.md:157`'s *"face-specific for DFCs"* is about **alt text on a real image**, which this
story does not draw, and face-specific rendering is **c4-6's** with `CardFace` already typed.
*The alternative* — reuse `frontFace()` (it already exists and is already tested) — is one line and
makes the 79-card population read as `Memory Lapse` instead of the doubled name, which is genuinely
nicer to look at. **c4-2's probe (b) is the warning attached to either answer**: with `X // X`
names, a split and a non-split produce *identical output for 2,246 of the 3,194 split-named cards*,
so the obvious fixtures **cannot discriminate the rule**. If the split is taken, the fixtures must
be `X // Y` cards, named, and a probe must prove they fail without it.

**Q6 — Where does "the unknown variant cannot be inspected" actually land?**
*Proposed:* **state it here as a contract with a named owner (c4-4 for the tile, c4-5 for the
inspection contract), and make the component's API give c4-4 no accidental path to violating it.**
Rationale: a listed primitive takes **no handlers at all** — `shell.test.ts` bans `on*` in both
positions — so this story structurally cannot implement inspectability, and pretending otherwise
would be prose outrunning code (this epic's standing finding, five rounds running). What it *can*
do is make the variant legible at the call site so c4-4's tile branches on a value rather than
re-deriving it. *The alternative* — ship a `inspectable: boolean` prop — is worse: it invites a
caller to pass `true` for an unknown card, which is the exact thing the AC bans, and a prop nobody
may set is not a contract. **Record which story's test will prove it.**

**Q7 — Does the component subscribe to `useCardEntry`, or does its caller?**
*Proposed:* **the caller.** Rationale: `cards.ts`'s own Q3 ruling is that a `useCard(id)` hook which
fetched would turn N tiles into N request owners, and while `useCardEntry` starts nothing, a
**listed primitive may hold no hook of any family** (`shell.test.ts`) — so subscribing inside the
placeholder would take it out of the primitive category, and *that is a signal, not a technicality*:
a component that reads the store is a container, and it belongs in a different list with a different
posture. So the placeholder takes plain props and **this story's test file** is where `useCardEntry`
gets its first real exercise (AC 15), with the production subscription landing in c4-4's tile.
*The alternative* — a `CardPlaceholderFromCache` container beside the primitive — is a real option
if c4-4 would otherwise write the same mapping twice; if taken, it is a **second** module, listed
separately, and it must not be in `PRIMITIVES`.

**Q8 — One component with a variant, or three components?**
*Proposed:* **one component whose variant type is derived from `PlaceholderKey`**, plus the loading
well as a member of that same union (`PlaceholderKey | 'loading'`, built **from** the imported type
so a third key in `states.ts` breaks the build here). Rationale: the epic's own criterion is that
all three occupy *"exactly the same footprint"*, and one component with one geometry is that claim
made structurally rather than asserted three times; it is also the shape that satisfies AC 8's
consumption requirement in the most direct way. *The alternative* — three small components sharing
Q2's geometry class — reads better at the call site (`<CardWell />` says more than
`<CardPlaceholder variant="loading" />`) and keeps the well's "no text, no a11y name" contract
physically separate from the two text variants, which is the contract most likely to be broken by a
later edit. Both are defensible; **decide before writing, because the answer changes how many
entries `PRIMITIVES` gains** (16 vs 18) and whether the well can ever accidentally take a name.

**Q9 — Does the named variant show a type line for a card whose type line is `'Card // Card'`?**
*Proposed:* **yes, unchanged — render what the data says.** Rationale: it is 12 characters, it is
true, and inventing a suppression rule means writing a special case for a string the corpus really
contains (400 cards are literally `'Card'`, and c4-2 already carries the `'Card'` row through its
grouping as `Other` rather than dropping it). Suppressing it would also make the *only* permanent
population of this variant render differently from every other card, which is the opposite of what
a placeholder is for. *The alternative* — hide a type line that carries no information — is a
judgement call about **data**, and this codebase's standing posture on data is that the app does not
edit it. **Note for the record:** with the cost blank and the type line uninformative, the honest
description of the permanent named placeholder is *"a card-shaped box with a doubled name in it"* —
which is still infinitely better than a broken-image glyph, and is exactly what FR-19 asks for.

### References

- Epic story text: [epics-companion-app.md#Story 4.3](_bmad-output/planning-artifacts/epics-companion-app.md#L1911-L1939) · Epic 4 header [#L1837-L1843](_bmad-output/planning-artifacts/epics-companion-app.md#L1837-L1843) · c4-4 (the tile that mounts these) [#L1941-L1991](_bmad-output/planning-artifacts/epics-companion-app.md#L1941-L1991) · c4-5 (the inspection contract) [#L1993-L2034](_bmad-output/planning-artifacts/epics-companion-app.md#L1993-L2034) · c4-6 (faces) [#L2035-L2083](_bmad-output/planning-artifacts/epics-companion-app.md#L2035-L2083)
- **UX-DR22** (the placeholder, verbatim): [epics-companion-app.md#L455-L461](_bmad-output/planning-artifacts/epics-companion-app.md#L455-L461) · **UX-DR4** (card geometry, exact and exclusive) [#L349-L354](_bmad-output/planning-artifacts/epics-companion-app.md#L349-L354) · **UX-DR36** (placeholder-then-fill, no reflow) [#L541-L547](_bmad-output/planning-artifacts/epics-companion-app.md#L541-L547) · **UX-DR33** (copy verbatim, nine states) [#L520-L524](_bmad-output/planning-artifacts/epics-companion-app.md#L520-L524) · **UX-DR3** (tabular numerals) [#L343-L347](_bmad-output/planning-artifacts/epics-companion-app.md#L343-L347) · **UX-DR13** (ManaPip/ManaCost) [#L404-L409](_bmad-output/planning-artifacts/epics-companion-app.md#L404-L409) · **UX-DR7** (brand hard rules) [#L364-L370](_bmad-output/planning-artifacts/epics-companion-app.md#L364-L370) · **FR-13 / FR-19** [#L89-L92](_bmad-output/planning-artifacts/epics-companion-app.md#L89-L92)
- **The visual contract**: [DESIGN.md — Card placeholder](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md#L389) · card geometry, and the mock's corrections [#L362](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md#L362) · *"the mock does NOT demonstrate … Card placeholder"* [#L366](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md#L366) · the `card-placeholder` token block [#L252-L255](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md#L252-L255) · the `card-tile` block (the aspect this story shares) [#L153-L160](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md#L153-L160) · **`micro: textTransform: uppercase`** [#L73-L79](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md#L73-L79)
- **The behaviour contract**: [EXPERIENCE.md — "Unknown card in a view"](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L69) · "Image loading — No copy. Wells stay silent." [#L72](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L72) · the Card-placeholder row and its inspectability clause [#L99](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L99) · placeholder-then-fill [#L105](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L105) · no-image / CDN-failure rows [#L127-L128](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L127-L128) · alt-text rule [#L157](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L157) · skeleton-vs-placeholder policy [#L166](_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md#L166)
- **The vocabulary this story consumes**: [states.ts — `PlaceholderKey`](ui/src/components/StatePanel/states.ts#L144) · `PLACEHOLDER_FOR_REASON` and its c4-3 note [#L146-L170](ui/src/components/StatePanel/states.ts#L146-L170) · the six type-level asserts [#L239-L318](ui/src/components/StatePanel/states.ts#L239-L318) · [cards.ts — `CardEntry.unknown.placeholder`](ui/src/state/cards.ts#L140-L162) · `PLACEHOLDER_FOR_CARD_REFUSAL` [#L213-L242](ui/src/state/cards.ts#L213-L242) · `useCardEntry` [#L523-L538](ui/src/state/cards.ts#L523-L538)
- **The shape to copy**: [DeckBadges.tsx](ui/src/components/DeckBadges/DeckBadges.tsx) · [DeckBadges.css](ui/src/components/DeckBadges/DeckBadges.css) · [ManaCost.tsx](ui/src/components/ManaCost/ManaCost.tsx#L39-L57) · [Badge.tsx](ui/src/components/Badge/Badge.tsx) · [filled.ts](ui/src/components/filled.ts) · [frontFace](ui/src/state/deckGroups.ts#L131)
- **The gates that will fail first**: [shell.test.ts — `PRIMITIVES` and the coverage guard](ui/tests/shell.test.ts#L1131-L1253) · the per-primitive bans [#L1255-L1330](ui/tests/shell.test.ts#L1255-L1330) · [token-usage.test.ts — `findRoleWithoutCompanions`](ui/tests/token-usage.test.ts#L443-L530) · the `--mana-*` allowlist idiom [#L560-L700](ui/tests/token-usage.test.ts#L560-L700) · [tokens.test.ts — the 65-token set equality](ui/tests/tokens.test.ts#L265-L275) and the `--radius-card` percentage pin [#L331-L342](ui/tests/tokens.test.ts#L331-L342) · [copy-rules.test.ts — `COPY_MODULES`](ui/tests/copy-rules.test.ts#L96-L137) and the five declared residues [#L48-L73](ui/tests/copy-rules.test.ts#L48-L73) · [posture.test.ts#L308-L346](ui/tests/posture.test.ts#L308-L346) · [gate-geometry.test.ts](ui/tests/gate-geometry.test.ts) · [unknown-card-copy.test.ts#L25-L34](ui/tests/unknown-card-copy.test.ts#L25-L34) · [named-card-copy.test.ts#L31-L37](ui/tests/named-card-copy.test.ts#L31-L37) · [.stylelintrc.json](ui/.stylelintrc.json)
- **The token layer**: [tokens.css — the radius block](ui/src/styles/tokens.css#L153-L164) · the typography block and its companion argument [#L130-L152](ui/src/styles/tokens.css#L130-L152) · the surface ramp [#L84-L95](ui/src/styles/tokens.css#L84-L95) · [surfaces.ts — `stepsExactlyOne` and the closed ramp](ui/src/styles/surfaces.ts#L1-L57)
- **The backend contracts this story renders**: [contracts.py — the three tokens, and "the placeholder is built in c4-3"](src/companion/contracts.py#L157-L182) · [cards.py — `_CARD_ID_PATTERN`, lowercase-only by ruling](src/companion/app/routes/cards.py#L67-L80)
- **The previous stories**: [c4-1](_bmad-output/implementation-artifacts/c4-1-a-single-card-hydration-cache-with-in-flight-deduping.md) · [c4-2](_bmad-output/implementation-artifacts/c4-2-deck-state-bootstrap-and-the-type-grouped-decklist.md) — its Q9b ruling on where a new component lives, and probe (b)'s "the obvious fixtures do not discriminate the rule"
- **The ledger**: [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md) — search `c4-3` (entries at `:1400`, `:1421`, `:1430`, `:1509`, `:2005`, `:2014`, `:2090`, `:2113`, `:2220`, `:3295`)
- **What C4 inherits, by story**: [epic-c3-retro-2026-08-02.md#L554-L556](_bmad-output/implementation-artifacts/epic-c3-retro-2026-08-02.md#L554-L556)
- Project rules: [project-context.md](_bmad-output/project-context.md) · frontend conventions [ui/README.md](ui/README.md)

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via the `bmad-dev-story` workflow.

### Debug Log References

- **Baseline, measured not assumed** (Task 0). `feat/companion-c4` confirmed at `2a64231`;
  `feat/companion-c4-3-card-placeholders` cut from it. Frontend **970 passed / 41 files** (7.2 s);
  Python **2,447 passed, 1 skipped, 54 deselected** (199 s). Both matched the story's table
  exactly. No `Worker exited unexpectedly` occurred in any run of this story.
- **The story's data table was re-verified read-only against the live DB, and every number held.**
  38,261 rows; **79** with no image data anywhere; **79/79** `type_line = 'Card // Card'`; **79/79**
  blank `mana_cost`; **79/79** doubled `X // X` name. Longest such name **66 chars** — the story
  guessed a `Zabaz…`-class name, the actual longest is
  `Asmoranomardicadaistinaculdacar // Asmoranomardicadaistinaculdacar` (same length). Id prefixes:
  6 chars → 38,216 distinct / **45 collisions**; 8 chars → 38,261 distinct / **0**; 12 → 0. **AC 9's
  number is unchanged and now re-derived on this machine.**
- **Three gate failures during implementation, all of them the guards working**, and each is
  recorded because two of the three were repairs to a GATE rather than to the code:
  1. `copy-rules.test.ts`'s per-copy-module non-vacuity read `toBeGreaterThan(3)` — a threshold
     tuned to modules holding a word table. A copy module with exactly ONE authored string fails it
     **for being correct**, and padding it would have meant moving card names into a module whose
     own header forbids them. Changed to `> 0` per module plus a **total across all declared
     modules** (`> 20`), which keeps the anchor's real job — proving the AST walk still returns
     strings — without punishing a single-label contract.
  2. `shell.test.ts`'s px-literal citation guard (c2-7's decide-once ruling) fired on
     `border: 1px solid var(--border-strong)`. Correct: DESIGN.md writes that border and the `1px`
     is a geometry literal with no token family. Cited in the stylesheet, within a sentence of the
     value, as the guard requires.
  3. My own new "reads code, not the prose about the code" test failed because `CardPlaceholder.css`
     did not actually name a chrome radius in its prose. Fixed by making the header say the true and
     useful thing (`--radius-md` is the value the composition reference ships for tiles), which is
     what makes the non-vacuity real rather than tautological.
- **A line-ending trap, recorded because it cost a gate run.** Several edits were applied with
  Python's `pathlib.write_text`, which on Windows translates LF to CRLF. `ui/.gitattributes` forces
  LF, so `format:check` went red across **nine** files — including two that had only been touched by
  a probe's *restore*. Repaired with `prettier --write` inside `ui/` and an explicit byte-level LF
  pass on the two markdown artefacts outside it. `git diff --stat` then confirmed `Footer.css` and
  `tokens.css` are byte-pristine after the probes.
- **The probe harness lied once, and that is the most useful line in this log.** Running
  `npx vitest run tests/token-usage.test.ts` alone crashes with
  `TypeError: Cannot read properties of undefined (reading 'config')` — that file imports two `src/`
  modules across the project boundary, so resolving it standalone picks the wrong project. The
  crash exits non-zero, so the first probe harness reported **six guards as firing when nothing had
  asserted anything**. All six were re-run against the full `npm test`. Ledgered.

### Completion Notes List

**All nine open questions were answered as proposed** (the eleventh story running), with three
sharpened by measurement rather than merely confirmed.

**Q2 — the card geometry lives in `src/styles/card-geometry.css`, as ONE class, `@import`ed by
`src/index.css`.** The story proposed "one shared CSS class in one stylesheet" and flagged an open
cost: *"a shared class means c4-4's tile imports a stylesheet it does not own"*. **That cost was
avoidable and is not paid.** Putting the file in `src/styles/` beside `tokens.css` and `fonts.css`
means **no component imports it at all** — a consumer writes `className="card-shape"` and inherits
`aspect-ratio: 63 / 88` + `border-radius: var(--radius-card)`. Two arguments settled it, both from
this repo rather than from taste: `src/index.css`'s box-sizing reset already makes exactly this
case in its own words (*"every component from c2-7 onwards inherits the same hazard … which is why
the reset is global"*), and a component importing `../../styles/…` would **fail `posture.test.ts`'s
cross-tree value-import rule** — so the alternative was not merely untidy, it was a red test for
c4-4, c4-5 and c4-6 each. No `--card-aspect` token was added (AC 3).

**Q4 — the truncated id is `--type-numeric`, RULED, and the ruling is now a GATE.** `--type-micro`
is uppercase by DESIGN.md's own `textTransform:` key while `cards.py:67`'s `_CARD_ID_PATTERN` is
`[0-9a-f]` lowercase-only by explicit ruling, so the micro role would put an id on screen **the
route would refuse if it were typed back**. `--type-numeric` is 13px, has no tracking sibling, no
uppercase, and carries tabular figures — right for a hex string compared against a log line — and
it is the only non-uppercase role SMALLER than the 14px name above it. It ships with
`font-variant-numeric: var(--type-numeric-features)` in the same block (AC 21). **Probe (j) proved
the ruling had no gate** and one was built: the test reads `_CARD_ID_PATTERN` **out of `cards.py`**
and fails if the id's block uppercases, so if the backend ever accepts uppercase the guard's own
premise fails loudly instead of enforcing a rule that has quietly stopped being true.

**Q8 — one component, and the props are a DISCRIMINATED UNION**, which is stronger than the
question anticipated. Q8 named the risk of choosing one component over three: *"whether the well can
ever accidentally take a name"*. The union answers it structurally — the `loading` member has
exactly one property, so **there is nothing to say it with** — and it closes probe (d) at compile
time too: `<CardPlaceholder variant="unknown-card" name="Black Lotus" />` **does not compile**. The
epic's own probe list calls that *"the copy-paste that type-checks"*; here it does not. `PRIMITIVES`
grew by 2 (component + copy module), not 3.

**AC 8 / the ledger's conditional — the `states.ts` classification is CONSUMED, not deleted.**
`deferred-work.md:2014` made the delete conditional on this story, so the answer is stated plainly:
`CardPlaceholderVariant = PlaceholderKey | 'loading'`, and the coupling is enforced in **both**
directions by two type-level asserts in the component. `EveryPlaceholderKeyHasProps` fails if a
third key joins `states.ts`; `NoVariantIsUnknownToStates` fails if the union is widened to a bare
`string` — the evasion the first assert alone would pass, because every key would still have a
member. `PLACEHOLDER_FOR_REASON` also gains a **runtime** consumer in the test file, which renders
every variant its values name rather than trusting the type. **`states.ts` was not edited**, which
was the design smell to watch for.

**TWELVE EVASION PROBES, ELEVEN CAUGHT, ONE PASSED — and the one that passed was closed in this
commit.** Probe (j) put the truncated id back into the uppercase micro role, correctly paired with
BOTH companions so `findRoleWithoutCompanions` was satisfied, and **the whole suite stayed green at
1,021 passed**. The finding generalises beyond this story and is ledgered: *every typography guard
in this repo asks whether a role travels with its companions; none asks whether the role suits the
value.* The one instance is now gated; the general rule is review's, because whether a string is
retypeable lives in the product.

| probe | outcome |
| --- | --- |
| (a) card radius spent on a chrome element (`Footer.css`) | **CAUGHT** — the message names the file, the rule and how to join `CARD_SHAPED` |
| (b) chrome radius spent on the placeholder | **CAUGHT** — the converse half, which an allowlist keyed only on `--radius-card` would never look for |
| (c1) `aspect-ratio` deleted from the shared class | **CAUGHT** |
| (c2) a SECOND `aspect-ratio` added for one variant only | **CAUGHT** — "declares its own aspect-ratio" |
| (d) unknown variant given a real card name | **CAUGHT** by `tsc`, `npm test` green — the c4-1 asymmetry |
| (e) the loading well given an accessible name | **CAUGHT** |
| (f) `--type-micro` with tracking but not `text-transform` | **CAUGHT** |
| (g) the variant union widened to a bare `string` | **CAUGHT** by `tsc`, `npm test` green |
| (h) the shipped label drifting from the artefact by one capital | **CAUGHT** |
| (i) the component quietly dropped from `PRIMITIVES` | **CAUGHT** by the git-derived coverage guard |
| (j) the Q4 ruling reversed — the id back in the uppercase micro role | **PASSED (1,021 green), then CLOSED** with a guard derived from `cards.py` |
| (k) the copy smuggled back into the component | **CAUGHT** by the copy file half |

*(Recorded at code review: probe (c) as the AC spells it — "the aspect ratio deleted from one
variant only" — was **impossible against the shared-class design**, because no variant owns an
aspect ratio to delete. (c1)/(c2) are its transformation into the two deletions that ARE possible,
not the probe as specified.)*

**THE EYE-CHECK IS DONE (Q1), and four ledger entries close or move because of it.** Paid here on a
throwaway harness — the **built** stylesheet served to Edge against hand-written markup, the same
instrument c4-2 used for `Badge` — screenshotted at 2× and 6×, harness discarded. All five
`ManaPip`/`ManaCost` claims open since c2-8 **hold, and none needed a nudge**: the pip is a
**circle**; the hybrid gradient's **hard stop reads as a clean 45° split with no blur**; the 13px
glyph sits centred and legible in the 16.25px circle at the 0.8 ratio the ledger flagged as most
likely to want adjusting (`0 2 X T P S` all checked); the wide case **grows into a pill rather than
clipping** (`{1000000}`, `{HW}`, `{100}`); and a 15-pip B.F.M. cost **wraps to a second row inside a
176px card** — narrower than the 452px column the entry worried about, so the harder case is the one
measured. The two cases the ledger said to check first (`{1000000}`, `{W/U}`) were checked first.
**AC 4's footprint claim was also confirmed against a real engine**: the placeholder fills a
176 × 245.9 rule (= 176 × 88 / 63) exactly, and the 141-character corpus name wraps inside the box
without overflowing. What the harness **cannot** answer is composition — a placeholder beside a real
card face in a real grid — and that half is **re-homed to c4-4 by name**.

**THE CVD QUESTION IS MEASURED RATHER THAN GUESSED**, which the ledger asked for as an eye-check and
gets as arithmetic plus Brad's acceptance. The six shipped `--mana-*` colours were pushed through
the Machado severity-1.0 dichromacy matrices in linear RGB and compared pairwise as CIE Lab ΔE.
Worst pair per vision type: **normal B/C 24.5 · protanopia U/B 10.0 · deuteranopia R/G 14.1 ·
tritanopia B/C 10.9**. Every pair stays above ΔE 10 — roughly **4× the just-noticeable difference**
for large flat patches — so the plain circles are **not** indistinguishable and neither reserved
lever (a glyph-slot letter, a DESIGN.md amendment) is called for. Two limits are stated rather than
glossed: a simulation is not a person, and this measures *distinguishability* (telling two pips
apart), not *identifiability* (knowing which colour a pip is) — the latter remains a real gap for a
sighted CVD reader that only a glyph would close. **This is the one item still needing Brad**, and
it is now a decision against numbers rather than a check that has not happened.

**AC 27 — the bundle changed on the CSS side and is BYTE-IDENTICAL on the JS side**, which is the
inverse of c4-1 and worth reading. `index.css` grew a third `@import`, so `.card-shape` ships:
CSS **6.12 → 6.18 kB**, SHA-256 `842D508D…` → `090B6384…`. The JS is **`49A35B61…` before and
after** — the same 202.89 kB, byte for byte — because **nothing imports `CardPlaceholder`**, so the
component *and its stylesheet* are tree-shaken out entirely (`grep card-placeholder` on the built
CSS returns **0**). That is the honest shape of a story that ships declared and unmounted: the
shared geometry four later stories consume is in the bundle; the component that will consume it
first is not, until c4-4 mounts it. `index.html` changed (asset filenames) and the `plugin/` mirror
was regenerated to match, hash for hash.

**AC 25 — no wire change, and the five Python gates are byte-identical to baseline**: 2,447 passed,
1 skipped, 54 deselected (199 s → 141 s, same counts). Nothing under `src/` changed except the built
bundle. `posture.test.ts`'s door list is untouched at `['src/api/client.ts']` (AC 17),
`store-writes.test.ts` needed no allowance (AC 18), and `package-contract.test.ts` is untouched —
`@testing-library/react` already shipped (AC 24).

**Counts.** Frontend **970 → 1,022 tests**, **41 → 42 files**. `PRIMITIVES` **15 → 17**,
`COPY_MODULES` **5 → 6**, `CARD_SHAPED` **new, 2 entries**, token inventory **unchanged at 65**,
schema aliases **unchanged at 9**.

**Two claims this story does NOT make, stated because an undeclared limit reads as coverage.**
Neither instrument for the geometry is a pixel: the source read proves the declarations exist
exactly once, and the jsdom test proves the rendered element carries the class —
`getComputedStyle(el).aspectRatio` in jsdom returns the empty string and would pass for the wrong
reason (the sixth recorded instance of that trap in this epic). And the `CARD_SHAPED` gate reads
stylesheets, so **whether an element carrying `card-shape` is genuinely a card** is markup, and
review's. Both are in `ui/README.md`'s blind-spot table.

**One accepted trade, seen on screen.** `overflow-wrap: anywhere` breaks the 31-character single
word `Asmoranomardicadaistinaculdacar` mid-word at the 176px grid floor. The alternative is a name
that paints through the card edge, because that word has nowhere legal to break at that width.
Accepted here and handed to **c4-4**, which will have a real column width in hand. Ledgered.

### File List

**New — the component and its shape**

- `ui/src/styles/card-geometry.css` — the ONE declaration of `63 / 88` + `var(--radius-card)`
- `ui/src/components/CardPlaceholder/CardPlaceholder.tsx`
- `ui/src/components/CardPlaceholder/CardPlaceholder.css`
- `ui/src/components/CardPlaceholder/CardPlaceholder.test.tsx`
- `ui/src/components/CardPlaceholder/copy.ts` — the declared copy module
- `ui/tests/fixtures/css/card-radius-on-chrome.css` — firing fixture, UX-DR4 clause 1
- `ui/tests/fixtures/css/chrome-radius-on-card.css` — firing fixture, UX-DR4 clause 2

**Modified**

- `ui/src/index.css` — the third `@import`, and why it is global
- `ui/tests/token-usage.test.ts` — the `CARD_SHAPED` allowlist (both halves + markup), the
  written-once geometry read, the Q4 id-role gate, and their firing/silent pairs
- `ui/tests/shell.test.ts` — `PRIMITIVES` 15 → 17
- `ui/tests/copy-rules.test.ts` — `COPY_MODULES` 5 → 6, and the non-vacuity threshold repair
- `ui/tests/unknown-card-copy.test.ts` — the byte-for-byte assertion c3-2 deferred to this story
- `ui/README.md` — the card-shape seam for c4-4/c4-5/c4-6, the copy-module paragraph, the
  primitives count, the CVD measurement, four blind-spot rows
- `_bmad-output/implementation-artifacts/deferred-work.md` — 12 dispositions + 4 new residues
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

**Rebuilt artefacts** (`npm run build` mutates `src/`; `scripts/build_plugin.py` mirrors it)

- `src/companion/app/static/index.html`, `assets/index-DGjO7yGD.css`, `assets/index-CdikAaRP.js`
  (replacing `index-C5wax6IS.css` / `index-Ck76yOVw.js`)
- `plugin/server/src/companion/app/static/` — the same four, hash for hash

### Change Log

| Date | Version | Description |
| --- | --- | --- |
| 2026-08-04 | 1.0 | **IMPLEMENTED off `2a64231` -> review.** All NINE open questions AS PROPOSED (eleventh story running), three of them sharpened by measurement. **Q2 avoided its own stated cost**: the shared `.card-shape` class lives in `src/styles/card-geometry.css` and is @imported by `index.css`, so c4-4, c4-5 and c4-6 consume it BY CLASS NAME with no import at all — and the alternative the story flagged (a component importing another component’s stylesheet) turned out to be a RED `posture.test.ts` test, not merely untidy. **Q8 became a DISCRIMINATED UNION**, which answers its own named risk structurally: the `loading` member has one property, so a well has nothing to say with, and `variant="unknown-card" name="Black Lotus"` DOES NOT COMPILE — probe (d) closed by the type. **The `states.ts` classification is CONSUMED, not deleted** (the ledger made that conditional on this story): the variant union is built FROM `PlaceholderKey` and coupled in BOTH directions by two type-level asserts, so a third key fails `tsc` and so does a union widened to `string`. **TWELVE PROBES, ELEVEN CAUGHT, ONE PASSED — and the one that passed is the most valuable line here**: reversing the Q4 ruling (the truncated id back in the UPPERCASE micro role, correctly paired with both companions) left the whole suite GREEN at 1,021, because every typography guard asks whether a role travels with its companions and NONE asks whether the role suits the value. Closed in this commit with a gate that reads `_CARD_ID_PATTERN` OUT OF `cards.py`, so the premise fails loudly if the backend ever accepts uppercase; the general rule is ledgered as review’s. **UX-DR4’s exclusivity is now a GATE in both directions** (`CARD_SHAPED`, the `MANA_DATA_INK` idiom) — including the converse half an allowlist keyed on `--radius-card` alone would never look for. **THE EYE-CHECK IS DONE (Q1)**: all five `ManaPip`/`ManaCost` claims open since c2-8 HOLD against a real engine (circle; hard-stop split with no blur; 13px glyph legible in the 16.25px circle; `{1000000}` grows into a pill; 15 pips wrap inside a 176px card — narrower than the 452px column the ledger worried about), and AC 4’s footprint was confirmed against a 176 x 245.9 rule. **CVD MEASURED rather than guessed**: worst pairwise CIE Lab dE under simulated dichromacy is 10.0 (protanopia U/B) vs 24.5 normal — every pair above dE 10, so neither reserved lever is needed; Brad’s acceptance is the one item still outstanding. **Bundle: CSS CHANGED, JS BYTE-IDENTICAL** (`49A35B61…` before and after) — nothing imports the component, so it and its stylesheet are tree-shaken out while the shared geometry ships; the inverse of c4-1. 970 -> 1,022 frontend (41 -> 42 files); Python 2,447 / 1 skipped / 54 deselected UNCHANGED. Primitives 15 -> 17, copy modules 5 -> 6, tokens unchanged at 65. Twelve inherited deferrals: 6 resolved/closed, 1 re-homed by name (c4-7), 2 answered "not needed", 1 measured-and-open pending Brad, 1 honoured-permanently, 1 acknowledged; 4 new residues declared. Next: three-layer code review, then PR into feat/companion-c4. |
| 2026-08-03 | 0.1 | **CONTEXTED off `2a64231`** on `feat/companion-c4`. The headline finding is that the named placeholder's **only permanent population is 79 cards that render with no pips and a useless type line** — all 79 are `'Card // Card'` reversible printings with a blank `mana_cost` and a doubled name (up to 66 chars), so UX-DR22's three-part composition degrades, measured, to name-only for every card that permanently needs it; and **0 of 2,027 deck rows** are such a printing, so in a deck view this variant is only ever reached transiently through `image_fetch_failed`. Second finding: **`--type-micro` is uppercase by contract** (DESIGN.md's own `textTransform:` key, which `token-usage.test.ts` derives a hard requirement from) while the card-id route pattern is **lowercase-only by an explicit backend ruling** — so a truncated uuid in the micro role shows an id the backend would refuse, which makes the id's type role a decision (Q4) rather than a default. Third: **the card geometry cannot be a token** — `tokens.test.ts` pins the inventory at 65 by set equality and `components.*` is not in the derivation — while `--radius-card` has **zero consumers** today, so this story is the first and therefore the one that decides where the shared shape lives before c4-4, c4-5 and c4-6 each write their own (Q2). Fourth: **UX-DR4's exclusivity half has no gate at all**, and this is the commit where it stops being vacuously true (Q3). Also measured: the **8-character** id prefix is unique across all 38,261 cards (six collides 45 times), the layout extremes (141-char name in the corpus, 56 in live decks, 15 pips, 91-char type line), and the loading well as a **deliberate hole in the surface ramp**. The ledger's instruction is conditional and this story is the condition: *"if c4-3 does not consume the `states.ts` classification, delete it."* 30 ACs, 9 open questions, 12 inherited deferrals (four of them the ledgered eye-checks, two Medium), 13 named don't-breaks. Baseline **970 frontend / 41 files**. |
