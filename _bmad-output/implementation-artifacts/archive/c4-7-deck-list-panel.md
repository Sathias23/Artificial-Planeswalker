---
epic: c4
story: c4-7
work_branch: feat/companion-c4
story_branch: feat/companion-c4-7-deck-list-panel
depends_on: >-
  c4-6 (merged at `d51b467`, PR #45) — the deck-wide hydration sweep in `App.tsx:213-216`, which
  is the only reason a front-face **cost** is reachable at all, and `faces.ts`, whose flip state
  this story deliberately does not read. c4-5 (merged at `bd72fc0`, PR #44) — the inspection
  slice, whose API was written location-agnostic **for this story by name** (`inspection.ts:41-54`)
  and which this story is the second production consumer of; `CardDetail`, which owns the
  deck-transition clear this story inherits for free; and the c4-5 Q14 ruling that the right
  column renders only for `surface.kind === 'deck'`. c4-4 (merged at `b26e8f4`) — `CardGrid`,
  which draws no group headers, no commander label and **no sideboard**, naming this story the
  owner of all three; and `src/containers/` as the category a component that behaves lands in.
  c4-2 (merged at `2a64231`) — `deckGroups.ts`, whose `TYPE_GROUPS` order exists so *"c4-7's group
  headers … have something deterministic to rest on"*, and `surfaceOf`. c4-1 (merged at
  `2095050`) — `hydrateCard`/`useCardEntry`. Also **c2-7** (`Panel` and `GroupHeader`, the latter
  with **zero consumers since the day it shipped** — this story is its first), **c2-8**
  (`ManaCost`), **c2-6** (`AppShell`'s 452px right column), **c2-4** (the token layer, 68 tokens,
  both pins).
baseline_commit: d51b467
---

# Story C4.7: Deck list panel

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad checking quantities and prices,
I want the deck as a text list grouped by type beside the grid,
so that I can read it as a list without giving up the card art.

**What this story really is.** On its face this is the easiest story left in the epic: a `<ul>` of
rows in a `Panel`, reading a derivation that already exists, wired to an inspection slice that was
written for it by name. Most of it genuinely is that. Three things are not, and none of them is
visible from the acceptance criteria.

1. **One of the four columns has no data behind it, and never can.** The user story's own first
   line says *"checking quantities and **prices**"*. UX-DR19 says *"right-aligned price"*.
   `DESIGN.md:178` reserves a **64px** track for it in `deck-row.columns: '34px 1fr auto 64px'`.
   There is **no price column in the `cards` table, no price field on any schema, and no importer
   path that ever reads Scryfall's `prices` object** — measured, not inferred (§*What the real data
   says*, A). This is not "fetch the detail tier"; the value does not exist anywhere in the system.
   c4-5 hit the identical AC on the detail panel and closed it **by absence**, asserted at the
   type, under a Brad ruling at c3-2 Q4. This story inherits that ruling and must decide what a
   *column* does when its content is structurally absent — which is a different question from what
   a *line of prose* does. That is **Q1**, and it is the only question that changes what ships.

2. **The front-face NAME is free; the front-face COST is not.** AC 5 says a double-faced row shows
   *"the front face's name and cost"*. The name is one `split(' // ')` away from
   `DeckCardSummary.card.name` — 99.0% of the 3,225 faced cards store the combined string there.
   The **cost is not there at all**: 2,830 of those 3,225 (87.8%) carry a **blank top-level
   `mana_cost`**, and the real cost lives only in `card_faces[0].mana_cost`, which `CardSummary`
   does not carry. In live decks that is **24 of 40 distinct DFCs across 38 rows**. A third shape —
   Adventure/Omen cards like `Murderous Rider // Swift End` — stores `'{1}{B}{B} // {1}{B}{B}'` and
   needs *splitting*, not hydration. So one AC clause resolves three different ways depending on
   the card, and unlike c4-5's oracle text the pips are **first-paint content**. That is **Q2**.

3. **This story is the first consumer of two primitives that have never been on a screen.**
   `GroupHeader` shipped at c2-7 and has **zero production consumers** to this day — grep confirms
   it appears only in its own file, its own test, and a comment in `CardGrid.tsx:27`. `Panel`'s
   `level="default"` is in the same position (c4-5 verified only `level="overlay"`). Both carry
   deferrals homed here by name, and `GroupHeader.tsx:15` goes further: it invites this story to
   **home a correction** to UX-DR44's heading levels if the `h2`-inside-`h2` reading is wrong in a
   real screen reader. This is the first story in the epic asked to potentially amend an
   accessibility rule rather than implement one.

Two more things open here, both smaller but both load-bearing:

4. **The live tint's "inset rule" cannot legally be written in a component stylesheet.**
   `DESIGN.md:181` specifies `live-rule: 'inset 2px 0 0 {colors.accent}'`. Stylelint's `box-shadow`
   allowed-list admits `none` or a comma-list of `var(--shadow-*)`/`var(--glow)` **and nothing
   else** (`tokens.css:205-209`). So this is a **token added to the layer** — 68 → 69, with both
   pins moved in the same commit — exactly as c4-4's `--shadow-focus-ring-over-art` and c4-5's
   `--shadow-live-ring`/`--shadow-pinned-ring` were. `tokens.css:269` has already reserved the
   matching reduced-motion row by name: `Deck-row live tint -> instant (c4-7)`.

5. **`App.test.tsx:494` is a red test by design, and it is not the one anybody would guess.**
   `expect(screen.getAllByRole('listitem')).toHaveLength(2)` is queried over the **whole document**,
   not scoped to the grid. Every `<li>` this story renders breaks it, and `:510`'s
   `expect(images).toHaveLength(tiles.length + 1)` cascades off the same wrong count. Bumping the
   number would re-hide the coupling; scoping it is the repair (**Q9**).

---

## Dev Notes

### The seam that already exists (do not rebuild any of it)

Everything below is **shipped and green at `d51b467`**. Read it before writing anything. The single
largest risk in this story is re-deriving something that is already derived once on purpose.

#### `src/state/deckGroups.ts` — the derivation, written for this story

Pure, framework-free, store-free. Called **exactly once**, at store write time
(`deck.ts:365`: `settle({ …, boards: boardsOfDeck(detail.deck) })`). Its module header states the
reason in one sentence (`deckGroups.ts:5-8`): *"so the grid and the list panel cannot disagree."*

```ts
// deckGroups.ts:90-100 — display order AND first-match-wins precedence, one list
export const TYPE_GROUPS = [
  'Creature', 'Planeswalker', 'Battle', 'Instant', 'Sorcery',
  'Artifact', 'Enchantment', 'Land', 'Other',
] as const
export type TypeGroup = (typeof TYPE_GROUPS)[number]        // :102

export const frontFace = (typeLine: string): string =>       // :131
  typeLine.split(/\s*\/\/\s*/)[0].trim()
export const groupOf = (typeLine: string): TypeGroup         // :155-160

export interface CardGroup {                                  // :163-168
  readonly group: TypeGroup
  readonly cards: readonly DeckCardSummary[]
  /** The summed `quantity` of cards — what a group header shows, never `cards.length`. */
  readonly quantity: number
}

export interface DeckBoards {                                 // :182-193
  readonly commander: readonly DeckCardSummary[]
  readonly mainboard: readonly CardGroup[]
  readonly sideboard: readonly DeckCardSummary[]
  readonly commanderQuantity: number
  readonly mainboardQuantity: number
  readonly sideboardQuantity: number
}
export const boardsOf = (cards: readonly DeckCardSummary[]): DeckBoards      // :231
export const boardsOfDeck = (detail: DeckDetail): DeckBoards                 // :255
```

Facts that constrain this story:

- **Empty groups are omitted** (`:241` `.filter((entry) => entry.cards.length > 0)`), so
  `mainboard` is never a list of mostly-empty headers. **The order of what remains is
  `TYPE_GROUPS`'s**, and `deckGroups.test.ts` asserts the order **by value**, not by membership.
- `deckGroups.ts:64-67` says the order exists so *"**c4-7**'s group headers and c4-5's 'the first
  card of the first type group' both have something deterministic to rest on"*.
- `:188` says, verbatim: *"The sideboard, ungrouped — **c4-7 decides whether it draws groups
  there**."* That is **Q4**.
- **Conservation identities** (`:216-221`): `commanderQuantity + mainboardQuantity ===
  detail.mainboard_count` and `sideboardQuantity === detail.sideboard_count`. A row this story
  fails to draw is a number on the screen that stops summing.
- **The `boards` reference identity IS the deck's identity.** `deckMemory.ts:8-9` and
  `CardDetail.tsx:333-336` both depend on that. A `useMemo` over `boards` in this panel would be
  the drift the module exists to prevent; a re-`sort()`/re-`filter()`/re-group is the second
  derivation AD-12 forbids.

#### `src/state/inspection.ts` — addressed to this story by name

`inspection.ts:41-54`, quoted because it is the contract:

> **THE API IS LOCATION-AGNOSTIC, ON PURPOSE (Q8, AC 4).** Nothing below is named for a tile.
> **c4-7's deck rows**, c4-6's flip control (which must touch NONE of this — a flip is not an
> inspection) and c6-5..c6-8's agent-view thumbnails are all consumers, and a `setHoveredTile`
> would have made two of the three read as a misuse of something else's API. The verbs are what
> happens, not where. A consumer attaches `setHovered`/`clearHovered` (pointer),
> `setFocused`/`clearFocused` (keyboard) and `togglePin` to its own interactive element.

State (`:109-128`): `hoveredId`, `focusedId`, `lastTransient: 'hover'|'focus'|null`, `pinnedId`,
`defaultId`. Resolution, one exported expression (`:210-211`):

```ts
export const targetIdOf = (state) => state.pinnedId ?? transientIdOf(state) ?? state.defaultId
// transientIdOf: lastTransient === 'focus' ? (focusedId ?? hoveredId) : (hoveredId ?? focusedId)
```

**Why two transient slots** (`:91-99`) — this is PR #44's P1, found independently by the edge-case
review layer and by Greptile, which is what retired the original dismissal:

> Hover and keyboard focus are concurrent input modalities: a tile can hold visible keyboard focus
> while the pointer sweeps other tiles. With one shared slot, a `mouseleave` erased a still-focused
> tile's target … Two slots let each modality's clear take only its own target; `lastTransient` is
> what resolves them when both hold one.

**Why the clears are keyed by id** — this is the exact race a cursor sweeping down a dense row list
will produce, and it is worse here than on the grid because rows are 24-30px tall rather than 246:

> Leaving one card and reaching the next produces two events, and the losing tile's is free to land
> second: an unkeyed clear on `mouseleave` would erase the hover the tile being MOVED TO has
> already set, and the panel snaps back to the cold-open card in the middle of a sweep.

The per-row subscription is **`useIsLiveTarget(cardId): boolean`** (`:341-342`), and its docstring
names this story: *"It also keeps `CardGrid`'s props at `{ boards }` and **lets c4-7's deck rows
call the identical hook without going through the grid at all**."* A selector returning a new
object each call re-renders forever under zustand v5 — return a primitive or a stored reference.

Refusal lives in the slice, not the consumer (`:182-185`): `setHovered`/`setFocused`/`togglePin`
refuse only an id whose cache entry is `unknown` **with `placeholder === 'unknown-card'`**. An id
never seen (`undefined`) is inspectable; a card whose *picture* failed is inspectable.

#### `src/containers/CardGrid/CardGrid.tsx` — what it deliberately left for this story

`:18-40`, three clauses, all naming c4-7:

> **The mainboard** is flattened in `TYPE_GROUPS` order. Flat rather than headed, because … the
> epic's own c4-4 criteria say nothing about group headers while **c4-7's say a great deal** …
> **The commander goes first, unlabelled.** … a labelled commander section is c4-7's, with the rest
> of the labelling. **The sideboard is NOT rendered here, and its owner is named: c4-7.**

`CardGrid.test.tsx:98` ships that as a test name: *"does NOT render the sideboard — 41 rows across
5 real decks, and c4-7 owns them"*, with `:104` — *"and it is IGNORED rather than lost: the
derivation still carries it, so c4-7 has it."*

The grid renders `<ul className="card-grid">` / `<li className="card-grid-item">` (`:92`, `:98`)
and an **untitled** `Panel` (`:87`). Its flattening — `[...boards.commander,
...boards.mainboard.flatMap(g => g.cards)]` (`:76`) — is the same expression
`coldOpenTargetOf` uses, so grid order and cold-open target already agree.

#### `src/components/Panel/Panel.tsx` and `GroupHeader/GroupHeader.tsx`

`Panel` (`:33-67`): `title?: string` (rendered as `<h2 className="panel-title">` **and** the
`<section>`'s `aria-label`), `count?: number` (`0` is real content), `badges?: ReactNode`,
`level?: 'default' | 'overlay'`, `children`. **No `className` prop** — c4-5 needed a wrapper `<div>`
for its pinned ring because of this. No state, no hook, not even `useId` (`:9-14`).
`Panel.css` is `overflow: hidden` with `var(--space-3)` (12px) body padding, so a child's
`--shadow-rest` clips at the panel edge. **A consumer may not restyle it.**

`GroupHeader` (`:25-38`): `label: ReactNode` (uppercased **by CSS**, not the caller),
`count?: number` (`Number.isFinite`, so `0` renders `"0"`). Renders
`<div class="group-header"><h2 class="group-header-label">…</h2><span class="group-header-count">…</span></div>`.
`GroupHeader.css:13-15` — **no horizontal padding, deliberately**: *"a group header aligns with the
rows it divides, and whatever container holds them owns that inset."* So the row's own horizontal
inset must be applied to the header's container, not to the header.

#### `src/components/ManaCost/ManaCost.tsx`

**One prop, no size option**: `cost?: string | null` (`:39-55`). `undefined`, `null`, `''` and
whitespace all render **nothing** (`:65`). Renders `<span role="img" aria-label={describeManaCost(tokens)}>`
with decorative pips inside. A `//` in the string is kept as a `text` token and rendered literally
(`:75-80`). Pip size is fixed at 16.25px in `em` off `--type-numeric` — deliberately
(`ManaPip.css:21-31`), so a row cannot ask for smaller pips. `ManaCost.css:25-30` wraps
(`flex-wrap: wrap`, `gap: var(--space-1)`).

#### `src/components/AppShell/AppShell.tsx` — where this panel mounts

```tsx
// AppShell.tsx:66
/** The 452px column: card detail (c4-5), deck list (c4-7), format check (c4-10). */
right?: ReactNode
```

`.app-shell-column` is `display:flex; flex-direction:column; gap: var(--space-panel-gap)`
(`AppShell.css:151-156`) — **a second child of `right` stacks with a 24px gap and nothing else is
needed**. `.app-shell-columns` is `grid-template-columns: minmax(0, 1fr) 452px` with
`overflow-y: auto`, and `AppShell.css:132` calls it *"the app's ONE legitimate scroll container"*.

**`AppShell.tsx` is not edited.** The placeholder string at `:134` — *"Card detail — c4-5 — the
deck list — c4-7 — and the format check — c4-10 — stack here."* — stays intact, because
`AppShell.test.tsx:161` and `:171` assert `/c4-7/` is present when `right` is empty. This is c2-9's
**displacement, not deletion** ruling, on its sixth application.

#### `src/App.tsx` — the two rulings this story inherits verbatim

`App.tsx:97-116` — the right-column gate:

> Ruled: the detail panel renders only for `kind === 'deck'`. … **c4-7 and c4-10 inherit this
> rather than re-deciding it**, which is what makes it worth writing here instead of in the panel.

`App.tsx:84-87`: *"the grid is handed `surface.boards` … **c4-7's deck list reads the same value,
including the sideboard this grid deliberately does not draw**."*

`App.tsx:211-212` — the hydration sweep covers every `card_id` in the payload *"so it therefore
also covers the sideboard rows c4-7 will draw."*

---

### What the real data says (measured at `d51b467`, read-only, against the shipped database)

DB: `%LOCALAPPDATA%\artificial-planeswalker\cards.db`, resolved by `src/paths.py:47`. 38,261 cards,
40 decks, 2,027 `deck_cards` rows (1,999 join a live deck; 28 orphaned by **deck** id across two
deleted decks, unreachable through the API).

#### A. Price — measured, and the answer is unambiguous

```sql
select sql from sqlite_master where type='table' and name='cards';
-- 23 columns: id, name, printed_name, oracle_id, mana_cost, cmc, type_line, oracle_text,
-- rarity, set_code, set_name, collector_number, colors, color_identity, color_indicator,
-- keywords, legalities, card_faces, image_uris, games, power, toughness, game_changer
```

**No price column.** `CardModel` (`src/data/models/card.py:11`) declares exactly those 23. `Card`
(`src/data/schemas/card.py:112`), `CardSummary` (`:223`) and `CardFace` (`:65`) declare no price
field. A case-insensitive grep for `price|prices|usd|eur|tix` over `src/`, `scripts/` and `tests/`
returns **9 hits, every one of them prose asserting the absence**. `src/data/importers/transformers.py`
is the field-by-field Scryfall→`CardModel` projection and **never reads Scryfall's `prices`
object** — so the data was never imported, not dropped downstream.

The absence is a ratified position with a test defending it:

- `src/companion/app/routes/cards.py:123` — *"``prices`` is absent from this response, not empty:
  the local database holds no price data of any kind."*
- `tests/unit/companion/test_routes_cards.py:136` — *"AC 15: the epic's price AC is satisfied BY
  ABSENCE, and absence is asserted"*, with `assert not [key for key in body if "price" in
  key.lower()]` at `:152`, and a docstring warning the next author **not** to re-run the check as
  a grep.
- `ui/src/api/types.d.ts:325` — *"There is no price data of any kind in this record."*
- `CardDetail.tsx:104-111` — *"**No price, and the AC is satisfied BY ABSENCE** (AC 14) … Brad
  ruled at c3-2 Q4 that the endpoint ships no price rather than a permanently-null one."*

The cost of changing that is on the ledger (`deferred-work.md:1985-2004`): a new column or side
table (Scryfall prices are per-printing and volatile), an importer change, a hand-written migration
(no Alembic), a re-import of 38,261 rows, plus a staleness story. **This story does not raise that
brief.** It rules the column (Q1).

#### B. Double-faced rows — the name is free, the cost is not

The `card_faces` column stores JSON `null` for single-faced cards, so **`card_faces is not null`
matches all 38,261 rows** — a live trap. The correct predicate is `json_type(card_faces)='array'`.

| measurement | count | of 3,225 |
|---|---:|---:|
| cards with `card_faces` | 3,225 | — |
| blank top-level `oracle_text` | 3,225 | **100%** (confirms c4-6) |
| blank top-level `name` | 0 | 0% |
| blank top-level `type_line` | 0 | 0% |
| **blank top-level `mana_cost`** | **2,830** | **87.8%** |
| `name` contains `' // '` | 3,194 | 99.0% |
| `mana_cost` contains `' // '` | 338 | 10.5% |

Three shapes, and AC 5 resolves differently for each:

| shape | top-level `mana_cost` | front-face cost from | example |
|---|---|---|---|
| transform / MDFC / battle | `''` | `card_faces[0].mana_cost` — **hydration** | `Nicol Bolas, the Ravager // …` → `'{1}{U}{B}{R}'` |
| adventure / omen | `'{1}{B}{B} // {1}{B}{B}'` | **split on `' // '`, take `[0]`** | `Murderous Rider // Swift End` |
| genuinely costless | `''` | nothing to draw, correctly | `Clearwater Pathway // Murkwater Pathway` |

**Live decks:** 67 `deck_cards` rows point at a DFC; **40 distinct DFCs across 22 of 40 decks**.
Of those 40, **24 carry a blank top-level `mana_cost` (38 rows)** and 16 carry one, of which
**27 rows carry the `'A // B'` split-cost form**. Rows that would draw an **empty pip cell** today
without a fix: **27 live rows / 19 distinct cards** (18 DFCs plus `Pym Particles`, whose
`type_line` is literally `'Card'`).

#### C. Row layout worst cases — measured, not guessed

- **Quantity: max 34** (`Swamp` in `Ayara Black Devotion v2 (owned)`). Histogram tail:
  1→1,632 · 2→197 · 3→76 · 4→60 · 5→9 · 6→10 · 7→10 · 8→6 · 9→7 · 10→6 · 11→3 · 13→2 · 18→1 ·
  20→2 · 21→1 · 25→1 · 27→1 · 31→1 · 32→1 · **34→1**. **379 of 1,999 live rows (19.0%) exceed 1.**
  The 34px quantity track must hold a two-digit number plus its multiplication sign.
- **Name: 33 chars** front-face worst case in a live deck (`Captain Marvel, Earth's Protector`),
  then `Yellowjacket, Heartless Marauder` and `Nick Fury, Agent of S.H.I.E.L.D.` at 32.
  **Unsplit that worst case is 56** (`Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel`) —
  so the front-face split buys a **41% reduction in the worst measure**, which is a layout argument
  for Q2 independent of the AC. Corpus absolute worst is **141 chars** (the Un-set
  *"Our Market Research Shows That Players Like Really Long Card Names…"*), reachable if ever added.
- **Mana cost: 6 pips / 22 chars** in a live deck (`Murderous Rider // Swift End`, which is 3 pips
  once split); 5 pips is the widest single-faced live cost (`Niv-Mizzet Reborn` `{W}{U}{B}{R}{G}`).
  Corpus worst is 15 pips (`B.F.M.`), already proven to wrap inside a **176px** card at c4-3 — a
  harder case than this 452px column.

#### D. The groups, over real decks

Live rows by group (1,999 rows, all boards), in `TYPE_GROUPS` order:

| group | rows | qty | distinct type lines |
|---|---:|---:|---:|
| Creature | 754 | 953 | 310 |
| Planeswalker | 105 | 110 | 35 |
| **Battle** | **0** | **0** | — **absent from every deck** |
| Instant | 265 | 347 | 3 |
| Sorcery | 135 | 164 | 3 |
| Artifact | 127 | 158 | 9 |
| Enchantment | 122 | 170 | 11 |
| Land | 490 | 1,135 | 34 |
| Other | 1 | 1 | 1 |

- **8 of 9 groups appear in real data.** `Battle` never does (39 corpus cards, 0 in a deck).
- **`Other` has exactly one live row**: `Pym Particles`, `type_line = 'Card'`, quantity 1, in
  `Kotis, the Fangkeeper — 100-card Brawl`. ⚠️ `deckGroups.ts` says *"the two copies of Pym
  Particles"* — **that is stale; it is one copy.** One-line doc correction owed.
- **First-match-wins is load-bearing for 88 live rows** carrying two primary types on the front
  face — `Legendary Enchantment Creature — God` (9), `Artifact Creature — Construct` (6), and one
  `Legendary Artifact Planeswalker — Equipment`, which resolves to **Planeswalker** because it
  precedes Artifact.
- **Group-count range per deck: 1 to 8.** `MSH — The Mad Titan's Gauntlet` renders only **five**
  groups (no Planeswalker, no Sorcery) — the panel must not assume a fixed set.
- **Largest deck** `Atraxa Counter Cabinet v2 (owned)`: 99 rows / 100 quantity, 1 commander,
  0 sideboard, 7 mainboard groups (Creature 28 · Planeswalker 11 · Instant 8 · Sorcery 2 ·
  Artifact 6 · Enchantment 6 · Land 37), 6 DFC rows.
- **Boards:** 16 of 40 decks have a commander (16 rows); **5 of 40 have a sideboard (41 rows)**.
  `MSH — The Mad Titan's Gauntlet` is the richest: 33 mainboard rows / 60 qty plus 9 sideboard rows
  / 15 qty.
- **Zero rows are orphaned by CARD id**, and `DeckDetail.from_deck` (`src/data/schemas/deck.py:264`)
  calls `CardSummary.model_validate(dc.card)` on an eager-loaded relationship — a missing card row
  would raise **inside the response constructor**, not emit a card-less entry. So AC 6's
  unrecognised-id scenario **cannot be produced by the wire at all**; it is only reachable at the
  frontend cache tier. Q11.

#### E. The two land policies — still four cards, still live

`src/viewer/view_model.py:174` splits on `//` and tests the front face; `src/logic/assessment/mana_base.py:80`
and `src/logic/mana_curve.py:74` test the whole string. Re-measured, the disagreement is still
exactly the four cards `deckGroups.ts` names:

| card | `type_line` | front-face group |
|---|---|---|
| `Agadeem's Awakening // Agadeem, the Undercrypt` | `Sorcery // Land` | **Sorcery** |
| `Kazandu Mammoth // Kazandu Valley` | `Creature — Elephant // Land` | **Creature** |
| `Dowsing Dagger // Lost Vale` | `Artifact — Equipment // Land` | **Artifact** |
| `Journey to Eternity // Atzal, Cave of Eternity` | `Legendary Enchantment — Aura // Legendary Land` | **Enchantment** |

**This story is already correct** — it inherits `deckGroups.ts`'s front-face policy, which is
FR-05/UX-DR17's. The exposure is **c4-8's curve**, which reads `mana_curve.py`'s whole-string policy
and will therefore disagree with this panel on these four cards **on the same screen**. Corpus-wide
the disagreement covers **82 cards** — ⚠️ `deckGroups.ts`'s header says 84, a two-card drift since
`2095050`. Both doc corrections belong in this story's diff.

---

### The wire types — what this story may and may not read

`GET /api/deck/{id}` → `DeckDetail` (`src/data/schemas/deck.py:234`), whose `cards` is
`list[DeckCardSummary]` (`:111`):

```ts
// ui/src/api/types.d.ts — read through src/api/schema.ts's aliases, import type ONLY
DeckCardSummary { card_id: string; quantity: number; sideboard: boolean;
                  commander: boolean; card: CardSummary }
CardSummary     { id; name; mana_cost; cmc; type_line; oracle_text;
                  colors; rarity; set_code }          // 9 fields — no card_faces, no price
Card            { …CardSummary + card_faces?: CardFace[]; image_uris?; legalities; … }
CardFace        { name; mana_cost; type_line; oracle_text; image_uris }
```

- **`DeckDetail.cards` order is explicitly not meaningful** (composite-PK ≈ `card_id` UUID order).
  `boardsOf` is what imposes order; the panel must never sort on its own.
- **Never re-declare a wire shape outside `src/api/`** — `wire-contract.test.ts:145` derives its ban
  from `openapi.json`'s `components.schemas` keys, so a local `interface DeckCard` is red.
- **Every `src/api/` import from a container is `import type`**, and the inline-`type` form is
  refused because `verbatimModuleSyntax` still runs the module (c4-5 decision 2).
- `strategy?: string | null` on `DeckSummary` is the asymmetric field re-homed to *"the first story
  that reads `strategy` — c4-7 is the nearest candidate"*. **This story does not read it** (Q13).

---

### Decide-once rulings this story inherits (do not re-derive)

1. **`src/containers/` is where a component that BEHAVES lives** (c4-4 Q1, ruled against its own
   proposal). `src/components/` is a closed set-equality category whose members are banned from
   hooks, `on*` in either position, `ref`, spread, and a value `react` import. A row that hovers,
   focuses and pins needs all of those → **container**. The decisive measurement: `posture.test.ts`
   filters its cross-tree rule on `!target.startsWith('src/components/')`, so containers kept
   inside that directory would have made *a primitive importing a stateful container invisible to
   every guard in the repo*.
2. **Container posture** (`ui/README.md:565-569`): MAY hold state, call hooks of any family, declare
   and attach handlers, hold a `ref`, read the store through `src/state/`, compose primitives. MAY
   NOT reach the network, import a state library directly, write another module's store slice, or
   declare a design token.
3. **Directory-per-component, no barrels, named exports only.** `react-refresh/only-export-components`
   is an ESLint **error**, so a helper exported from a component file breaks fast refresh — it
   becomes its own module and its own `CONTAINERS` entry (`imageUrl.ts`, `deckMemory.ts`,
   `imagedFaces.ts`, `useCardArt.ts` are the four precedents).
4. **`AppShell.tsx` is never edited; placeholders are displaced, not deleted** (c2-9, sixth
   application).
5. **Class names are flat kebab-case prefixed with the component** (`deck-row-name`, never
   `deck-row__name`) — stylelint `selector-class-pattern` is an error.
6. **Every colour, shadow, radius, spacing, duration and type value goes through a token.** No
   inline `style={{…}}`, ever (`no-restricted-syntax`) — *"the one hole through which the entire
   token layer can be bypassed."*
7. **`box-shadow` allowed-list**: `none`, or a comma-list of `var(--shadow-*)`/`var(--glow)`.
   A new composite is **a token added to the layer** (`ui/README.md:301`), never inlined, never
   declared in the component's own file (`token-usage.test.ts:1098` forbids that outright).
8. **`px` literals in `src/containers/` need a `DESIGN.md:NNN` citation within 60 characters, in the
   same block comment** (`shell.test.ts:1002-1032`). `--space-2` *is* 8px, so "inside 8px" is a
   token, not a literal.
9. **Bare `1fr` and `minmax(auto, 1fr)` grid tracks are banned** (`shell.test.ts:960`); grid items
   need `min-width: 0`. ⚠️ **`DESIGN.md`'s `deck-row.columns: '34px 1fr auto 64px'` is therefore
   not writable verbatim** — the `1fr` becomes `minmax(0, 1fr)`.
10. **`:focus-visible`, never `:focus`; `outline: none` is banned in all four spellings.**
11. **`--accent-dim` on `--surface-overlay` is banned (2.70:1)**; the guard is same-block only.
    Live/selected markers on overlay-backed surfaces use `--accent`. `deck-row.live-rule` already
    specifies `{colors.accent}`, so this story inherits the **precedent and the ban**, not the
    defect — c4-5 fixed the identical family for `card-detail.pinned-ring` and amended DESIGN.md,
    because `tokens.test.ts` asserts token values **byte-for-byte against DESIGN.md's frontmatter**.
12. **Nothing pulses, loops or alternates at any setting**; `animation-iteration-count` may only be `1`.
13. **`Panel` is a primitive a consumer may not restyle.**
14. **`.app-shell-columns` is the app's single scroll container.** `shell.test.ts:421-423`/`:1768`
    exempt **only `CardDetail`'s panel** from the `overflow: hidden|clip` ban. A deck-list panel
    that wants an internal scroller must argue for its own exemption (Q7).
15. **Any authored user-facing string lives in a `copy.ts` beside its component** and is registered
    in `COPY_MODULES`. **Card data is not copy.** The attribute half collects *every* literal
    reaching nine read-aloud attributes **whatever its shape** — a one-word `aria-label` is caught.
    Bans across all of `src/`: `!`, emoji, "something went wrong".
16. **Emptiness is `filled()` / `typeof` + `trim()`, never truthiness; a number is
    `Number.isFinite`, never `count && …`** — `{quantity && <Badge/>}` renders the bare string `0`.
    `given()` is the shared string-narrowing spelling and returns the **trimmed** value.
17. **Props are a discriminated union where the variants are closed**, coupled to their source type
    in both directions by type-level asserts so a new key *and* a widening to `string` both fail
    `tsc` (c4-3 Q8's `CardPlaceholder` is the pattern).
18. **`fireEvent` is the suite's only DOM-event idiom** — `fireEvent.mouseEnter/mouseLeave` plus
    `.focus()`/`.blur()`, no `userEvent`, no new dependency (c4-5 Q9).
19. **`npx tsc -b --force`, never `tsc -b`** — the incremental cache hides `TS2835` cascades.
20. **Guards are proven through the full `npm test`, never a standalone file run** — the standalone
    `token-usage.test.ts` runner crash is ledgered and confirmed live at c4-3 and c4-5.
21. **The `:where()` cascade repair** (c4-6 Q2) is the sanctioned idiom for adding a wrapper without
    disturbing specificity: `:where(.wrapper):hover .thing` is byte-identical in specificity to
    `.thing:hover`. Hover and focus states must sit at **equal specificity** so the later rule wins
    by order (`no-descending-specificity`).

---

### Latest technical specifics

- **React 19.2 / TypeScript 5.9 / zustand 5 / Vite 7 / Vitest 3** — unchanged; this story adds no
  dependency. `package-contract.test.ts` pins the dependency list, so adding one is a decision with
  a diff.
- **zustand v5 has no equality argument on `create`.** A selector returning a new object or array
  each call re-renders forever. Per-row subscriptions must return a **primitive** (`useIsLiveTarget`)
  or a **stored reference** (`useCardEntry`). `useShallow` only when two values are genuinely needed.
- **Two vitest projects**: `src/**/*.test.{ts,tsx}` → jsdom (`dom`, with `src/test-setup.ts`);
  `ui/tests/**/*.test.ts` → node. `gate-geometry.test.ts:53` forbids `.tsx` under `tests/` — this
  story's component test **must** be `src/containers/DeckList/DeckList.test.tsx`.
- **`aria-query` maps `<header>` to `banner` unconditionally**, where HTML-AAM does not when the
  `<header>` sits inside a `<section>`. Measured at c4-5 with a two-header probe. `Panel` renders
  `<section aria-label>` containing a `<header>`, so **every titled `Panel` is a phantom `banner`
  in jsdom and none in a browser**. c4-5 recorded this as *"a new blind spot for the epic: every
  later titled `Panel` inherits it"* — and **this story is the first to inherit it**, taking the
  jsdom count from two to three. The mitigation c4-5 applied is to scope role queries **through the
  `h1`** rather than by `getByRole('banner')`.
- **Windows line endings**: `pathlib.write_text` translates LF→CRLF; `ui/.gitattributes` forces LF,
  so `format:check` goes red across files a probe merely *restored*. Restore with byte-preserving
  writes.
- **A vitest worker crash** (`Error: Worker exited unexpectedly` with no failing assertion) is a
  known flake — re-run before investigating.

---

### The eighteen things this story must not break

1. **`AppShell.tsx` — not edited.** `AppShell.test.tsx:118/:161/:171` must pass unchanged, including
   the `/c4-7/` placeholder assertions.
2. **`CardGrid`'s visual order and its `boards`-only prop** — no second flattening, no re-sort, no
   re-group. AD-12.
3. **`deckGroups.ts`'s conservation identities** — `commanderQuantity + mainboardQuantity ===
   mainboard_count`, `sideboardQuantity === sideboard_count`. Every row lands somewhere.
4. **The `boards` reference identity is the deck's identity** — `deckMemory.ts` and `CardDetail`'s
   effect both depend on it. No `useMemo` over `boards`, no derived copy held in a ref.
5. **The inspection slice's five values and eleven verbs are read and written, never reshaped.**
   `useIsLiveTarget`'s boolean-primitive contract is untouched; clears stay keyed by id.
6. **`CardDetail` owns the deck-transition clear.** This story adds **no** second `deckMemory` —
   `replacesRememberedDeck` is a module-scope singleton and a second caller would race it so that
   one consumer never sees the transition.
7. **`useCardEntry`'s "starts nothing" contract** — do not add an effect or a fetch to it.
8. **`hydrateCard`'s attempt cap (`MAX_ATTEMPTS_PER_CARD = 3`), in-flight dedupe and never-rejects
   posture.**
9. **`CardTile`'s accessible name — exactly once** (`Black Lotus ×4`, ID order, **with a space**,
   pinned by c4-4's review).
10. **`CardDetail` is not a live region**, and this story adds no second one. A row list sweeping
    under a cursor is precisely the flood UX-DR45 and the H4/C1 gate finding exist to prevent.
11. **`Panel` is a primitive a consumer may not restyle** — `overflow: hidden`, 12px body padding.
12. **`.app-shell-columns` is the single scroll container**; the `overflow` exemption is
    `CardDetail`'s only.
13. **The one network door stays `['src/api/client.ts']`** (`posture.test.ts:339`). The scan is
    keyed on the **identifier**, so even the bare word `fetch` in stripped code fails.
14. **`store-writes.test.ts`'s `STORES` table** — five entries; **no component calls `setState`**.
    The writer scan is a name-presence heuristic, which is why `readCardEntry` exists.
15. **`wire-contract.test.ts`** — no wire shape re-declared outside `src/api/`.
16. **The token inventory and its two pins** (`tokens.test.ts:306`, `token-usage.test.ts:1086`) —
    **both move together or the pair is wrong**, and the story says why.
17. **`CARD_SHAPED`'s four entries and both directions**; the reduced-motion registration block is
    extended, never bypassed, and the enumerated shipped-motion pin (`token-usage.test.ts:2305`,
    now **4**) moves in the same commit if a transform ships.
18. **Python is untouched.** `uv run pytest` stays at **2,501 passed / 1 skipped**. (c4-5's
    don't-break list said 2,447/1/54 and was corrected in-record as stale — do not repeat it.)

---

### Source tree — what exists, what this story touches

```
ui/src/
  containers/
    DeckList/                     NEW   the panel, the groups, the rows
      DeckList.tsx                NEW   container: reads boards + inspection, composes Panel/GroupHeader
      DeckList.css                NEW   the row grid, the live tint, the group inset
      DeckList.test.tsx           NEW   jsdom project
      copy.ts                     NEW?  group/board labels — Q4/Q5 decide whether it is needed
      frontFaceCost.ts            NEW?  the three-shape cost resolution — Q2 decides
    CardDetail/…                  READ  the panel above this one; its effect owns the deck clear
    CardGrid/…                    READ  the flattening this panel must agree with
  state/
    deckGroups.ts                 EDIT  doc corrections only (82 not 84; one Pym Particles not two)
    inspection.ts                 READ  the contract; unchanged
    cards.ts                      READ  useCardEntry for the DFC cost — Q2
  components/{Panel,GroupHeader,ManaCost}/…   READ  first real consumer of two of the three
  styles/tokens.css               EDIT  + the live-rule composite (Q6), + the reduced-motion row
  App.tsx                         EDIT  mount the panel as the second child of `right`
  App.test.tsx                    EDIT  scope the listitem count (Q9); displacement assertion
ui/tests/
  shell.test.ts                   EDIT  CONTAINERS entry/entries + the 10 → N pin
  copy-rules.test.ts              EDIT? COPY_MODULES entry with a >40-char reason
  tokens.test.ts                  EDIT  expectedNames + 68 → 69
  token-usage.test.ts             EDIT  declaredTokens.size 68 → 69
src/companion/app/static/         BUILD committed bundle, must change (JS and CSS)
plugin/server/src/companion/app/static/   BUILD ⚠️ hand-copied mirror, nothing checks it
```

**⚠️ The plugin mirror is an unguarded gap.** `src/companion/app/static/` is enforced in sync with
`ui/` by CI (`.github/workflows/ci.yml:154-167`, which errors with *"src/companion/app/static/ is
stale"*). The byte-identical second copy at `plugin/server/src/companion/app/static/assets/` is
checked by **nothing** — no test, no workflow, no script. It must be updated by hand or the plugin
ships a stale SPA. Raise it as a ledger entry with a named home if it is not fixed here.

**Baselines to measure against** (verified on disk at `d51b467`):

| baseline | value |
|---|---|
| frontend tests | **1,255 passed / 50 files** |
| Python tests | **2,501 passed / 1 skipped** |
| tokens | **68** (two pins) |
| containers | **10** (`shell.test.ts:1652`) |
| primitives | **17** (`shell.test.ts:1268`) |
| stores | **5** |
| copy modules | **8** |
| `CARD_SHAPED` | **4** |
| shipped-motion pin | **4** (`token-usage.test.ts:2305`) |
| bundle JS | `index-DmtAq_d6.js` **215,832 B** |
| bundle CSS | `index-DjIbf6Qz.css` **15,323 B** |
| font | `space-grotesk-latin-wght-normal-BhU9QXUp.woff2` 22,288 B |

**Both bundle assets must change.** This story mounts a new component and ships new CSS; c4-5's
phrasing applies — *"a byte-identical JS bundle here means it did not ship"*. Note c4-6's precedent
that a **byte count can be unchanged while the hash changes**; report both.

---

### The inherited deferrals — give each a disposition (AC 38)

C2 retro **ruling R2**: inherited deferrals are ACs at context time, and *"not mentioned" is a
failure of the AC*. There are **nine**. Each needs a written disposition — resolved, declined with
a reason, or re-homed by name.

1. **`Panel` (default level) and `GroupHeader` appearance are not dev-verified**
   (`deferred-work.md:1331-1355`, re-confirmed `:3448-3452`). c4-5 closed the `Panel`
   `level="overlay"` half by eye-check; the **default level** and **`GroupHeader`** halves are
   homed here. Severity **Medium** — *"the failure mode is a solid blank pill with invisible text,
   which reads as a content bug rather than a CSS one. Check it first."* Extended 2026-07-29: the
   **tone-over-wash contrast is also unmeasured**.
2. **The ` // ` split-card separator is spoken as literal characters** (`deferred-work.md:1429-1445`).
   `describeManaCost('{2}{B} // {B}')` → *"2 generic, black // black"*, so a screen reader says
   "slash slash". c4-3 confirmed it live and **re-homed it here unchanged**: *"The decision belongs
   where a cost is read aloud in prose: **c4-7's deck rows**."* ⚠️ Note the interaction with Q2 — if
   the front-face split lands, a `' // '` **never reaches `ManaCost` on a row**, and the deferral is
   closed *by construction* on this surface while remaining live wherever a combined cost renders.
   Say which it is; do not let it fall silently.
3. **`ManaPip`/`ManaCost` appearance** (`deferred-work.md:1400-1419`). c4-3 **discharged this
   story's inheritance explicitly**: *"c4-7 and c4-9 inherit nothing from this entry; what remains
   for them is **composition**"* — pips in a `34px minmax(0,1fr) auto` row grid rather than in a
   176px card. Do not re-run the five claims; check the composition.
4. **The `'Card // Card'` grouping fix** (`deferred-work.md:3515-3520`), **re-homed here by name by
   c4-6** with its blocker removed: the hydration sweep now makes `card_faces[0].type_line`
   available. ⚠️ But see **Q10** — taking it means re-deriving `boards` *after* hydration, which
   breaks the reference-identity contract `deckMemory.ts` depends on. 2,274 corpus rows, **0 in any
   live deck**.
5. **`strategy?: string | null` wire asymmetry** (`deferred-work.md:3411-3421`) — re-homed to
   *"the first story that reads `strategy` — c4-7 is the nearest candidate"*. Q13.
6. **`DeckRepository.list_decks` ties on `created_at`** (`deferred-work.md:1668-1699`, escalated to
   **Medium-High** and recommended as a standalone chore). Named home: *"any UI that promises
   newest first (**c4-7's deck-list panel**)"* — but that entry means the **list of decks**, and
   this story renders the **cards of one deck**. Almost certainly "not triggered, re-home
   unchanged", but it must be *mentioned*.
7. **UX-DR44's heading-level collision** (`GroupHeader.tsx:11-16`) — *"c4-7 … may home a correction
   if it reads wrong in a real screen reader."* Q15.
8. **F1: story-key-shaped strings on the rendered view** (`deferred-work.md:3456-3464`, `:3736-3739`).
   Five remain; mounting this panel displaces `c4-7`. **Record the new count.** The gate itself
   stays c8-5's.
9. **Panel-stacking vertical budget** (`c4-5:1052-1058`, advisory): *"at a 1100px viewport … a 452px
   column renders the card art about 630px tall … **c4-7 and c4-10 stack beneath this panel** and
   should know the art already spends a screenful."* Feeds Q7.

**Triggered "whoever ships the next X" residues** — each also needs a line:

- **The next motion** — `tokens.css:269` reserves `Deck-row live tint -> instant (c4-7)`. If any
  `transform`/`scale`/`rotate`/`translate` ships, the derived guard requires `none !important` on
  the **matching selector text** and the shipped-motion pin moves.
- **The next cross-file card-shape collision** — `deferred-work.md:3587-3596` names `.deck-row`
  **by name** as its illustrative case: *"a card-shaped element given a chrome radius by a rule in a
  NON-card-shaped file (`.deck-row .card-shape { … }`) is in neither half."*
- **The next flippable-fixture toucher** — `deferred-work.md:3809-3812`: three hand-rolled copies of
  the flippable wire fixture, *"home: any later c4 story that touches these suites"*. This story's
  DFC row tests would be the fourth copy, or the shared helper.
- **The next story that renders an identifier** — `deferred-work.md:3598-3609`: *"nothing checks that
  the RIGHT type role was chosen for the content"*, measured by a probe that **passed**. A row's
  count in `--type-numeric` is the same family of question.
- **`StatChip`'s first surface** — not triggered; DESIGN.md's row anatomy calls for no chip. Say so.
- **The hydration sweep's no-re-drive window** (c4-6 review ruling 1, accepted as documented
  posture with the fix written down). Its epic-level form names this story: *any story that fetches
  per-row data **after** a successful deck load inherits the same window*. Q2's cost resolution is
  exactly that. **Cite it; do not re-open it.**

---

### Open questions — answer these before writing code

Sixteen. Q1 and Q2 change what ships; the rest close holes that would otherwise be found at review.

**Q1 — The price column has no data source. What does the fourth column do?**
Measured in §A: no column, no field, no importer path, and a Python test asserting the absence on
purpose. c4-5 closed the identical *prose* AC by absence. This is a *column* with a reserved 64px
track, and the epic's user story names prices in its first line.
*Proposal:* **collapse the grid to `34px minmax(0, 1fr) auto`** and **amend `DESIGN.md`'s
`deck-row.columns` in the same commit with the reason inline** — the precedent is exact (c4-5 Q2
amended `card-detail.pinned-ring` because `tokens.test.ts` reads DESIGN.md's frontmatter
byte-for-byte, so shipping against an unamended artefact is a red test). Copy c4-5's absence
assertions: a **type-level** `Extract<keyof CardSummary, 'prices' | 'price'>` must be `never`, plus
a rendered check that **no `$` reaches the glass**. Do **not** raise the price-import brief — its
cost is already on the ledger and nothing in this epic needs it. A dead 64px gutter is the
alternative, and it is worse: it is a visible empty column that reads as a loading failure.

**Q2 — How does a double-faced row get its front-face cost?**
Three shapes (§B). The name splits from the summary; the cost does not exist there for 24 of the 40
live DFCs.
*Proposal:* a small pure module `frontFaceCost.ts` (its own `CONTAINERS` entry, per ruling 3) taking
`(summary, entry)` and returning `string | null`: if the summary's `mana_cost` contains `' // '`,
split and take `[0]`; else if it is non-blank, use it verbatim; else if the cache entry is
`hydrated` and carries `card_faces`, use `card_faces[0].mana_cost`; else `null`, which `ManaCost`
already renders as nothing. Rows subscribe with `useCardEntry(cardId)` **unconditionally** (hooks
rule) and use it only on the blank branch — the entry is a stored reference, so the subscription is
cheap and re-renders exactly the row whose hydration landed. State the first-paint consequence
plainly: those 38 rows draw **no pips until the sweep reaches them**, and the sweep's measured tail
is ~1.2 s on the 99-card deck (c4-6). If that is unacceptable, the alternative is a derived field on
`CardSummary`, which is an MCP-visible schema change — the same blast radius c4-6's Q1 rejected.

⚠️ **Cite c4-6's accepted posture, do not re-derive it.** c4-6's review ruled that the hydration
sweep has **no re-drive after a mid-sweep backend blip while deck state is already `deck`** —
c4-2's edge-triggered recovery only re-boots from `refused`/`none`, and reload is the documented
recovery (`cards.ts:100-108`). The epic-level form of that ruling names this story: *any story that
fetches per-row data **after** a successful deck load inherits the same no-re-drive window*. For
c4-7 the concrete consequence is that a blip during the sweep leaves those 38 DFC rows **permanently
pip-less until a reload**, with no error state to explain it — while their neighbours look fine,
because a single-faced row never needed the fetch. Cite the c4-6 ruling; do not re-open it, and do
not paper over it with a retry this story does not own.

**Q3 — Is the three-spelling divergence on one screen acceptable?**
UX-DR19 requires the row to show the **front** face's name. c4-6 kept the tile caption **combined**.
c4-5's pin announcement speaks the **combined** name. So one card renders as `Clearwater Pathway`
(row), `Clearwater Pathway // Murkwater Pathway` (tile caption), and is *announced* as the combined
name — three spellings, one screen. *Proposal:* follow UX-DR19 as written, and record this as a new
named residue on the **epic manual-testing checklist**, beside the existing MDFC announcement entry
(`deferred-work.md:3788-3794`). Raised, not discovered.

**Q4 — Commander and sideboard: what sections, in what order?**
Specified in **no artefact**; `deckGroups.ts:188` hands the sideboard question here by name, and
c4-4's Q5 handed the commander label here. 16 decks have a commander (16 rows), 5 have a sideboard
(41 rows), and the conservation identities mean both must land somewhere.
*Proposal:* **Commander** as a labelled group first (`GroupHeader label="Commander"
count={commanderQuantity}`), then the mainboard groups in `TYPE_GROUPS` order, then **Sideboard**
as a single ungrouped labelled section (`count={sideboardQuantity}`). Ungrouped because a 9-row
sideboard split across five type groups is five headers for nine rows, and because the grid's
commander-first order is thereby matched exactly. Both labels are authored words → `copy.ts`.

**Q5 — Group header labels: `TYPE_GROUPS`'s singular strings, or DESIGN.md's plural?**
DESIGN.md's only example is `"CREATURES"`; `TYPE_GROUPS` is singular; the design mock uses four
plural groups that conflate instants/sorceries/artifacts into `"Spells"` and is **not** authoritative
(`DESIGN.md:372`).
*Proposal:* a `Record<TypeGroup, string>` label map in `copy.ts`, pluralised to match DESIGN.md's
example, **coupled to `TypeGroup` in both directions by type-level asserts** so a tenth group and a
widening to `string` are both `tsc` failures (c4-3 Q8's pattern). Uppercasing stays in CSS.
Rejected alternative: rendering `TYPE_GROUPS` strings raw — it would put the store's internal
vocabulary on the glass and make DESIGN.md's one worked example wrong.

**Q6 — The live-rule composite token: what is it called and how do the pins move?**
`inset 2px 0 0 var(--accent)` cannot be written in a component stylesheet.
*Proposal:* `--shadow-deck-row-live`, declared in `tokens.css` beside `--shadow-live-ring` and
`--shadow-pinned-ring`, with both pins moved 68 → 69 in the same commit. Check **how
`tokens.test.ts` derives `expectedNames`** before writing — the three existing composites are the
precedent for whether a `components.*` frontmatter key or the hand list is the source.

**Q7 — Does the panel scroll internally?**
99 rows plus 8 headers is tall, and c4-5 measured that this column's card art already spends a
screenful at 1100px. But `.app-shell-columns` is the single scroll container and the `overflow`
exemption is `CardDetail`'s alone.
*Proposal:* **no internal scroller.** Let the page scroll. The reason is not tidiness: an internal
scroller with no focusable content is exactly the WCAG 2.1.1 defect `deferred-work.md:3778-3786`
already carries for the oracle block, and creating a second instance while the first is still open
is the wrong direction. Rows here **are** focusable, so Tab reaches every one and the browser
scrolls it into view — the property the oracle scroller lacks. Measure and record the rendered panel
height on the 99-card deck. The design mock's `max-height: 640px` is drift (640 is on no scale).

**Q8 — What element is a row?**
ESLint's a11y gate narrows the interactive-handler list to six names and errors on `onClick` on an
`<li>`; UX-DR47 requires *"a real `<button>` or `<a>`, never a `<div>` with a click handler"* and a
≥24×24px hit box.
*Proposal:* `<li>` → `<button type="button">` carrying the four-column grid, exactly as `CardTile`
and `FlipControl` do (`CardTile.test.tsx:788-797`: *"A REAL `<button>` … not a `tabIndex` on a
div"*). Handlers on the button; **no `tabindex` anywhere**. Confirm the resulting hit box by
measurement, since 13px numeric on a tight row can fall under 24px without deliberate padding.

**Q9 — How is `App.test.tsx:494` repaired?**
`expect(screen.getAllByRole('listitem')).toHaveLength(2)` is document-wide, and `:510` cascades off it.
*Proposal:* **scope, don't bump.** Wrap the grid query in `within(...)` on the grid's own region and
add a separate deck-list-scoped count. Bumping `2` to `2 + rowCount` would preserve exactly the
coupling that made this red and hand the same trap to c4-10. Re-spell the image arithmetic rather
than loosening it to `>=` — `App.test.tsx:506-508` refuses that loosening in writing.

**Q10 — Take the `'Card // Card'` grouping fix, or decline it?**
c4-6 re-homed it here saying the blocker is removed. It is removed *for the data*, but the mechanism
is the problem: `boardsOf` runs **once, at store write time, before hydration completes**, and the
resulting reference identity is what `deckMemory.ts` uses to detect a deck replacement. Re-deriving
after hydration would produce a new `boards` reference on the same deck and **fire a spurious
deck-transition clear, releasing the user's pin mid-session**.
*Proposal:* **DECLINE, and re-home with that reason recorded** — 2,274 corpus rows, **0 in any live
deck**, against a mechanism change that breaks a shipped contract. The honest home is a story that
owns the derivation's timing (a hydration-aware second pass, or the `CardSummary` field c4-6's Q1
priced). Do not quietly take it because a previous story said the blocker was gone.

**Q11 — AC 6's unrecognised-id row cannot be produced by the wire. What is it tested against?**
Zero rows are orphaned by card id, and `DeckDetail.from_deck` would raise inside the response
constructor rather than emit a card-less entry (§D).
*Proposal:* state that the AC's scenario is reachable **only at the frontend cache tier** — a card
whose *hydration* fails — and test it there. The row still renders name, quantity and cost from the
summary, because the summary is what the deck payload carries and it is never absent. Note the
inspection slice **refuses** an `unknown-card` id, so such a row must not become an inspection
target — and confirm which of the two the row is.

**Q12 — Name colour at rest.**
`DESIGN.md:391` gives the live case (`body-strong` `{colors.text-primary}`) and the rest *role*
(`{typography.body}`) but **no rest colour**. `DESIGN.md:295` would suggest `text-primary` ("for
names"); the mock uses `--text-secondary`.
*Proposal:* `--text-secondary` at rest. The parenthetical in `DESIGN.md:391` attaches `text-primary`
to the live case specifically, which only reads as a distinction if rest is something else; and a
row that changes both weight and tier on becoming live is the clearer signal. Record it as a reading
of an underspecified line, not as a fact.

**Q13 — Does this story read `strategy`?**
*Proposal:* **no** — the deck list renders cards, and `strategy` is deck-level prose with no place
in a row. Re-home deferral 5 unchanged, and say the candidate was checked rather than assumed.

**Q14 — What does a group-header count mean?**
`deckGroups.ts:166-167` already rules it: *"the summed `quantity` … **never `cards.length`**"*.
UX-DR16 and UX-DR43 make it **accessibility-load-bearing** — it is the non-motion signal that a deck
changed. But no artefact defines it.
*Proposal:* summed quantity, as shipped, and say so in the panel's module header so the next reader
does not have to derive it. Note the consequence: `Land 37` rows renders `38`.

**Q15 — Does the `h2`-inside-`h2` heading structure survive a real screen reader?**
`GroupHeader.tsx:15` invites a correction. Taking UX-DR44 as written makes the panel's title and
every group divider siblings at `h2`.
*Proposal:* **ship as written**, then check it in the eye-check against **Chrome's own accessibility
tree** (c4-6's method), not jsdom — jsdom cannot see the difference, and the phantom-`banner` blind
spot proves that. Home a correction only if it measurably reads wrong; record the measurement either
way. Do not "correct" it to `h3` on taste.

**Q16 — What does this panel do for a deck with zero cards?**
`EXPERIENCE.md:70` and `:113`, and Story 4.12's own AC (`epics-companion-app.md:2276-2278`), name
exactly three panels to hide until a deck has cards: *"the mana curve, colour distribution and
format check panels are hidden"*. **The deck list is not among them, and no artefact says whether it
hides or renders empty.** UX-DR33's nine copy states include "Empty active deck" with an *in-grid*
line only. c4-12 owns the empty-deck state and ships **after** this story, so this panel will be on
the glass for a 0-card deck before its owner exists.
*Proposal:* render the panel with its title and **no rows** — not hidden, and with no invented
empty-state sentence, because inventing copy here would pre-empt c4-12's own copy AC and put
unsourced words on the glass. `boardsOf` on an empty deck yields empty `commander`/`sideboard` and a
`mainboard` of zero groups, so this falls out of the existing derivation with no special case. Flag
it to **c4-12 by name** as the story that decides whether the panel hides, and note that the three
named panels being listed without this one is itself an artefact gap worth recording.

---

## Acceptance Criteria

### The panel — presence, placement and semantics

1. A `DeckList` container renders in `AppShell`'s `right` slot as the **second** child, directly
   beneath `CardDetail`, stacking on `.app-shell-column`'s existing `var(--space-panel-gap)` —
   with **no edit to `AppShell.tsx`** (FR-05, UX-DR8, UX-DR19).
2. It renders **only** when `surfaceOf` returns `kind === 'deck'`, inheriting the c4-5 Q14 ruling
   at `App.tsx:97-116` rather than re-deciding it. Behind any state panel the right column shows
   the shell's own placeholder line, and a test asserts the deck list is absent (UX-DR30).
3. It is **permanently present alongside the grid, never a toggled alternate view** (FR-05,
   UX-DR19). No toggle, no collapse control, no view-mode state.
4. It is a `Panel` with `title` set from `copy.ts`, so the title renders as an `<h2>` and names the
   `<section>` (UX-DR44). `level` is **default**, not `overlay` — this is the first shipped consumer
   of the default level (AC 33).
5. The rows are a `ul`/`li` structure (UX-DR44). The `<ul>` carries no `role` override.

### The row — anatomy, type roles and the live state

6. Each row is a **real `<button type="button">`** inside its `<li>`, never a `<div>` or an `<li>`
   with a click handler, and **nothing carries a `tabindex`** (UX-DR47, and the `CardTile`
   precedent at `CardTile.test.tsx:788-797`).
7. The row's hit box is **≥ 24×24px, measured**, not asserted (UX-DR47).
8. The row is a grid whose template is Q1's ruling, written with **`minmax(0, 1fr)` and never a
   bare `1fr`** (`shell.test.ts:960`), with every `px` literal carrying a `DESIGN.md:NNN` citation
   within 60 characters in the same block comment (`shell.test.ts:1021`).
9. **Quantity** renders in `--type-numeric` **with `--type-numeric-features` in the same rule
   block** and `--text-tertiary` (UX-DR3, UX-DR19). It uses the same U+00D7 multiplication sign the
   quantity badge does, spelled as an escape. It renders for **every** row, including quantity 1 —
   unlike the tile badge, which suppresses `×1` — because a list column that disappears on 1,620 of
   1,999 rows is not a column.
10. **Name** renders in `--type-body` at `--text-secondary` at rest and `--type-body-strong` at
    `--text-primary` when live (UX-DR19, Q12), single-line with ellipsis, in a track with
    `min-width: 0`.
11. **Mana cost** renders through the shipped `ManaCost` component, unmodified and unresized.
12. **The fourth column** follows Q1's ruling. If the price column is dropped, `DESIGN.md`'s
    `deck-row.columns` is amended in the same commit with the reason inline, and the absence is
    asserted at the **type** plus by a rendered check that no `$` reaches the glass (c4-5's AC 14
    pattern).
13. A **live** row carries the tint `--accent-glow` and the inset rule, both through tokens; the
    inset rule is a **new `box-shadow` composite token** (Q6), never inlined (`tokens.css:205-209`).
14. The row radius is `--radius-sm` (`DESIGN.md:179`). **No `--radius-card` appears anywhere in
    this story's CSS or markup**, and `DeckList.css` does **not** join `CARD_SHAPED` — the list is
    text-first and draws no card face (UX-DR4, both directions).
15. A card with no image data or an unrecognised id renders **identically to any other row**,
    because the list is text-first (UX-DR19, FR-13). Per Q11, the scenario is exercised at the
    cache tier, and the story records that the wire cannot produce it.

### The groups — headers, order, and the two boards nobody specified

16. Type-group headers render through the shipped **`GroupHeader`** primitive — its **first
    production consumer** — with the label in `--type-label` carrying **both** mandatory companions
    (`--tracking-label` and `text-transform: uppercase`) and the count right-aligned in the numeric
    role over a hairline rule (UX-DR12).
17. The group **order is `TYPE_GROUPS`'s**, read from `boards.mainboard` and **never re-sorted,
    re-filtered or re-grouped** in this component (AD-12, FR-05). Empty groups do not render,
    because `boardsOf` already omits them.
18. Group **counts are summed quantities, not row counts** (Q14, `deckGroups.ts:166-167`), and the
    panel's module header says so.
19. Group labels come from a `copy.ts` label map keyed on `TypeGroup`, **coupled in both directions
    by type-level asserts** so a tenth group and a widening to `string` are both `tsc` failures
    (Q5).
20. The **commander** renders first, in its own labelled section (Q4) — 16 of 40 real decks.
21. The **sideboard** renders, in its own labelled section (Q4) — 41 rows across 5 real decks that
    the grid deliberately drops. `CardGrid.test.tsx:98`'s *"c4-7 owns them"* is thereby discharged.
22. **The conservation identities hold on screen**: the drawn quantities sum to
    `mainboard_count` and `sideboard_count`. A test asserts it over a real fixture with all three
    boards populated.
23. A double-faced row shows the **front face's name** (split from the summary) **and the front
    face's cost** (Q2's three-shape resolution) (UX-DR19). All three shapes are covered by named
    tests, including the Adventure split-cost form and a card with a blank cost that stays blank.
24. A deck with **five** groups and a deck with **eight** render correctly; nothing assumes a fixed
    group set, and `Battle` — which appears in zero real decks — is not special-cased.

### Inspection — the second consumer

25. Each row attaches `setHovered`/`clearHovered` (pointer), `setFocused`/`clearFocused` (keyboard)
    and `togglePin` (click and Enter/Space, via the button) to its own interactive element, and
    reads its live state through **`useIsLiveTarget(cardId)`** — the identical verbs a tile uses,
    proving the slice's location-agnostic claim (UX-DR19, UX-DR39, FR-17).
26. **The clears stay keyed by id.** A test drives a sweep across three adjacent rows and asserts
    the target never falls back to the cold-open card mid-sweep — the race `inspection.ts:239-241`
    describes, which is tighter here than on the grid because rows are an order of magnitude
    shorter than tiles.
27. **Mixed input is covered in both directions**: a row holding keyboard focus while the pointer
    sweeps other rows, and the reverse; `lastTransient` resolves, and neither clear rewrites
    recency (PR #44's P1).
28. **The panel re-derives nothing.** It calls no `targetIdOf` of its own, holds no local "current
    card", and adds no second `deckMemory` — the deck-transition clear is inherited from
    `CardDetail`'s effect, and the story records that a same-deck edit releasing a pin is the
    **accepted, ruled** cost.
29. Rows sit in the Tab order **after the card grid and every flip control, before the connection
    pill and footer links** (UX-DR40). The story records the resulting order explicitly, including
    that c4-5's unpin control is an unenumerated stop immediately above these rows.
30. **The panel is not a live region and adds no `aria-live`.** Transient hover and focus announce
    nothing; the only pin announcement remains `CardDetail`'s single polite region (UX-DR44,
    UX-DR45, the H4/C1 gate finding).

### Motion, focus and the accessibility floor

31. The live tint's transition is registered in `tokens.css`'s `prefers-reduced-motion` block on the
    **row reserved for it by name** (`tokens.css:269`). If any `transform` ships, the derived guard
    is satisfied on the **matching selector text** with `!important`, and the shipped-motion pin
    (`token-usage.test.ts:2305`, now 4) moves in the same commit.
32. Focus uses `:focus-visible` with the standard ring; `outline: none` appears in none of its four
    spellings. Hover and focus rules sit at **equal specificity** so the later wins by order.
33. `Panel` at `level="default"` and `GroupHeader` are **verified by eye against a real engine**
    (deferral 1), including the tone-over-wash contrast numbers. This closes an entry open since
    c2-7.
34. `ManaCost`'s **composition in a row** is checked by eye (deferral 3) — the wrap behaviour in the
    row's `auto` track, which no harness can show.

### The record, the gates and the ledger

35. `CONTAINERS` in `shell.test.ts:1457` gains one entry per new module, each with a sorted
    exhaustive import list and a prose reason, and the pin at `:1652` moves from **10** in the same
    commit.
36. If any authored word ships, `src/containers/DeckList/copy.ts` exists with **no relative imports
    of its own** (so `ui/tests/` can import it across the tsconfig boundary) and is registered in
    `COPY_MODULES` with a **>40-character** reason.
37. Both token pins move together if a token is added (`tokens.test.ts:306`,
    `token-usage.test.ts:1086`), and the story says why.
38. **Every one of the nine inherited deferrals gets a written disposition** — resolved, declined
    with a reason, or re-homed by name (C2 retro R2). The **six** triggered "next X" residues get a
    line each, including c4-6's no-re-drive window, which Q2's cost resolution sits directly inside.
39. **Evasion probes are run against every new guard through the full `npm test`**, never a
    standalone file run. The minimum list is enumerated by letter before implementation and includes
    at least: (a) a new container module absent from `CONTAINERS`; (b) a chrome radius in a
    `CARD_SHAPED` file and `--radius-card` in `DeckList.css`; (c) a row grouped by its **back** face;
    (d) a card dropped from every section, breaking conservation; (e) the panel re-`sort()`s instead
    of reading `boardsOf`; (f) an unkeyed `clearHovered`; (g) a `setState` call from the component;
    (h) the reduced-motion registration deleted; (i) a numeric role without
    `font-variant-numeric`; (j) `aria-live` added to the panel; (k) an authored word smuggled out of
    `copy.ts` or into an `aria-label`; (l) the live-rule composite inlined instead of tokenised;
    (m) a bare `1fr` in the row grid; (n) a wire shape re-declared outside `src/api/`. **Plus two
    do-nothing negative controls whose silence is what makes the rest mean anything.** A probe that
    **passes is recorded, not quietly fixed**.
40. **An eye-check is performed in a real browser over CDP against the running backend**, not
    described. It must cover: a deck with all three boards (`MSH — The Mad Titan's Gauntlet`), the
    99-card deck, a deck with the six MDFC Pathways (`Atraxa Counter Cabinet v2`), and both motion
    settings. It reports measured numbers — row hit box, the live row count (`.is-live` must be
    **exactly 1**), the rendered panel height, the group-header contrast, and the heading structure
    read from **Chrome's own accessibility tree** (Q15).
41. The record states the **frontend and Python test counts, the file count, every registry that
    moved, and both bundle asset names with byte sizes**, against the `d51b467` baselines. **Both
    bundle assets must change**; report the hash even where a byte count does not move.
42. The **plugin mirror** at `plugin/server/src/companion/app/static/` is updated by hand, and the
    fact that **nothing checks it** is either fixed or ledgered with a named home.
43. The two measured doc corrections land in this diff: `deckGroups.ts`'s *"84 cards"* → **82**, and
    its *"two copies of Pym Particles"* → **one**.
44. Python is untouched: `uv run pytest` stays at **2,501 passed / 1 skipped**.

---

## Tasks / Subtasks

- [x] **Task 0 — Answer the sixteen open questions before writing code** (AC 12, 23, 38)
  - [x] Re-verify §A's price measurement read-only at `d51b467` and rule Q1
  - [x] Re-verify §B's three cost shapes and rule Q2
  - [x] Rule Q3–Q16, each with its reason recorded in the Debug Log
  - [x] Confirm how `tokens.test.ts` derives `expectedNames` before adding a token (Q6)
- [x] **Task 1 — The label and title copy** (AC 4, 19, 20, 21, 36)
  - [x] `src/containers/DeckList/copy.ts`, no relative imports
  - [x] The `Record<TypeGroup, string>` label map with both type-level asserts
  - [x] Register in `COPY_MODULES` with a >40-char reason
- [x] **Task 2 — The front-face cost resolution** (AC 23, Q2)
  - [x] `frontFaceCost.ts` as its own module, three shapes, total over `null`
  - [x] Named tests for transform/MDFC, Adventure split-cost, and genuinely-costless
- [x] **Task 3 — The row** (AC 6–15, 25–27)
  - [x] `<li>` → `<button>`, the **three**-column grid (Q1), `minmax(0, 1fr)`, `min-width: 0`
  - [x] The five inspection verbs plus `useIsLiveTarget`
  - [x] The live tint token in `tokens.css`, both pins moved (AC 37)
  - [x] The reduced-motion registration on the reserved row (AC 31) — **mechanical**, stated
- [x] **Task 4 — The groups and the two boards** (AC 16–24)
  - [x] `GroupHeader` as first consumer; the container owns the horizontal inset
  - [x] Commander first, mainboard in `TYPE_GROUPS` order, sideboard last
  - [x] The conservation test over a three-board fixture
- [x] **Task 5 — Mount it** (AC 1–3)
  - [x] `App.tsx`'s `right` becomes a Fragment; `AppShell.tsx` untouched
  - [x] `App.test.tsx`: scope the listitem count and re-spell the image arithmetic (Q9)
  - [x] Add the `c4-7` displacement assertion; record the new F1 count (deferral 8)
- [x] **Task 6 — Registries, guards and probes** (AC 35–39)
  - [x] `CONTAINERS` entries + the `10 → 13` pin
  - [x] Run the fourteen lettered probes plus two negative controls, through full `npm test`
  - [x] Record every probe that passed, with the named test that closes it
- [x] **Task 7 — The eye-check, the gates and the record** (AC 33, 34, 40–44)
  - [x] CDP eye-check over three named decks and both motion settings
  - [x] Ten gates: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test`,
        `npm run build`; `uv run pytest`, `ruff check .`, `ruff format --check .`, `mypy src/`,
        `mypy src/ --platform win32`
  - [x] Rebuild the bundle, commit it, **hand-copy the plugin mirror**
  - [x] The two `deckGroups.ts` doc corrections
  - [x] Write the nine deferral dispositions and the five residue lines
- [x] Set status to `review` and **STOP** — Brad runs the three-layer review and raises the PR

### Review Findings

<!-- Three-layer review 2026-08-06 (Blind Hunter / Edge Case Hunter / Acceptance Auditor). 22 raw findings → 1 decision, 17 patches, 2 defers, 3 dismissed. -->

- [x] [Review][Decision] **Quantity column: the 34px track is sized to yesterday's maximum with no overflow posture** — `DeckList.css:63` fixes the track at `34px` on the strength of "the largest quantity in any real deck is 34", but unlimited-copy cards (Relentless Rats, Persistent Petitioners, Seven Dwarves) make `×100`+ one `import_decklist` away, and neither the span nor the track states what happens then (clip, paint-over, or shove). The corpus measurement is a fact about the data, not a bound. Options: (a) accept the measured bound as documented posture and ledger it; (b) `minmax(34px, max-content)` + a one-line DESIGN.md track amendment — which deviates from the design artefact's stated `34px` and is therefore Brad's call, not a patch.
- [x] [Review][Patch] **HIGH — The diff repoints both `index.html`s at bundle assets it never adds** [`src/companion/app/static/index.html`, `plugin/server/src/companion/app/static/index.html`] — old assets deleted, 4 references to `index-Bd1UijdF.js`/`index-CWp3yHqM.css`, 0 additions; all four new files are `??` untracked (verified live; mirror byte-identical, sizes match the record). Committed as-is, both SPAs 404 their only script and stylesheet. Exact repeat of the c4-3 High — in the very story whose headline discovery is that the guards are blind to untracked files. Fix: `git add` the four assets.
- [x] [Review][Patch] **HIGH — AC 9 violated and the record's claim is false: `MULTIPLICATION_SIGN` ships the literal character, not an escape** [`ui/src/containers/DeckList/DeckList.tsx:138`] — byte-verified raw UTF-8 `×`, no `×` in the file; the comment above claims "written as a genuine escape" and new ledger entry #3 mocks `CardTile.tsx` for this identical defect while asserting this story's constant is clean. Fix: `'×'`.
- [x] [Review][Patch] **AC 2's required test does not exist: nothing asserts the deck list is absent behind a state panel** [`ui/src/App.test.tsx`] — the only right-column absence assertion is `:656`'s `Card detail`; zero `queryByRole('region', { name: 'Deck list' })` absence checks anywhere. The behaviour holds via the shared `kind === 'deck'` gate, but the AC names the test — the exact failure family the c4-5 review flagged.
- [x] [Review][Patch] **No `deferred-work.md` edit anywhere in the diff — every ledger obligation exists only inside the story file** [`_bmad-output/implementation-artifacts/deferred-work.md`] — AC 38's nine dispositions, AC 42's named-home entry for the unguarded plugin mirror, Q3's residue, Q10's declined re-homing, deferral 2's re-homed surfaces, and the record's three new ledger entries all live solely in the Dev Agent Record; c4-4/5/6 each wrote the ledger in their story commit. Fix: write the entries.
- [x] [Review][Patch] **AC 39 probe (h) silently substituted; probe (b) half-run** — the enumerated "(h) reduced-motion registration deleted" was replaced by "an unregistered `transform` on the row" with no note; (b)'s CARD_SHAPED chrome-radius half was never run though a residue line claims "both directions". Fix: run the enumerated probes, record honestly.
- [x] [Review][Patch] **`tokens.css` misstates which surface a deck row sits on, contradicting `DeckList.css`'s numbers for the same rule** [`ui/src/styles/tokens.css:272-273`] — claims rows sit on `--surface-overlay` (5.5:1 / 2.70:1); rows sit on `--surface-panel` and this diff's own `DeckList.css:123-124` computes 6.21:1 / 3.05:1 there. One of the two comments is false — in a repo whose review history treats a false comment as a defect.
- [x] [Review][Patch] **The registry-guard false-green shipped with its lying comments intact and unledgered at the guard** [`ui/tests/copy-rules.test.ts:88`, `ui/tests/token-usage.test.ts:47`, `ui/tests/posture.test.ts:52`] — all three walk `git ls-files`, so an un-added module is invisible; the discovery lives only in a sprint-status YAML narrative. Fix: correct the three guard comments to declare the limit (per `wire-contract.test.ts:106` precedent) + ledger entry.
- [x] [Review][Patch] **DESIGN.md is now self-contradictory about price** [`_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md`] — the deck-row amendment declares "There is no price data anywhere in this system" while the Card detail panel prose lines below still specify "price right-aligned in `{typography.numeric}`". This story's whole thesis is that absences must be written down so they aren't corrected back; the sibling line invites exactly that.
- [x] [Review][Patch] **Test comment contradicts its assertion: "four of the five rows carry one" above `toHaveLength(3)`** [`ui/src/containers/DeckList/DeckList.test.tsx` (ManaCost test)] — the fixture has two costless lands; the assertion is right, the arithmetic in the prose is wrong, and the next fixture edit will "correct" the wrong one.
- [x] [Review][Patch] **`frontFaceName` can return `''`, violating its own "Never empty" contract** [`ui/src/containers/DeckList/frontFaceCost.ts:81-83`] — a name beginning `' // '` yields an empty string after slice+trim. Fix: fall back to the raw name when the front segment is empty + test.
- [x] [Review][Patch] **`frontFaceCost` branch 3 returns `card_faces[0].mana_cost` verbatim with no `' // '` re-check** [`ui/src/containers/DeckList/frontFaceCost.ts:150-152`] — branches 1–2 guard the separator; the hydrated branch does not, and `card_faces` is untyped on the wire, so a face-level cost carrying a separator would reopen the spoken-separator deferral this module claims closed by construction. Fix: route branch 3 through the same split + test.
- [x] [Review][Patch] **`aria-label` asserted on exactly one pip run** [`ui/src/containers/DeckList/DeckList.test.tsx`] — `getAllByRole('img')[0]` only; loop over all runs.
- [x] [Review][Patch] **Two structural tests assert by absence only** [`ui/src/containers/DeckList/DeckList.test.tsx`] — the `level="default"` test proves only `.panel-overlay` missing (passes if Panel weren't levelled at all); the empty-groups test asserts two labels absent instead of comparing the full heading list, so a wrongly-present header passes. Fix: assert the rendered heading list in full.
- [x] [Review][Patch] **Blank-cost test title overstates: "renders NOTHING" while the empty `.deck-row-cost` cell still ships** [`ui/src/containers/DeckList/DeckList.test.tsx`] — `ManaCost` returns `null`, the wrapping cell does not (and AC 12's children-count pin proves it). Behaviour fine; retitle to match the DOM.
- [x] [Review][Patch] **AC 26's tail assertion is vacuous** [`ui/src/App.test.tsx`] — `expect(targetIdOf(...)).not.toBe(null)` immediately after asserting equality with LAND_B, which is also the cold-open default, so the closing step can't distinguish "hover won" from "fell back". Strengthen or drop.
- [x] [Review][Patch] **Nothing asserts the right column's stacking order** [`ui/src/App.test.tsx:177-185`] — detail panel and deck list are both asserted present, never that detail is above the list; swapping the Fragment children passes every test while placement is what AC 1–3 are about. One `compareDocumentPosition` assertion.
- [x] [Review][Patch] **AC 19's both-direction asserts relocated from `copy.ts` to `DeckList.tsx` without the record noting the deviation** [`_bmad-output/implementation-artifacts/c4-7-deck-list-panel.md` Dev Agent Record] — the move is well-reasoned (import-free `copy.ts`, TS2835) and functionally equivalent, but the record says "Q3–Q16 — all AS PROPOSED". One honest line.
- [x] [Review][Defer] **`frontFaceCost` shape 2's correctness rests on a point-in-time corpus measurement** [`ui/src/containers/DeckList/frontFaceCost.ts`] — a faced card with a non-blank, non-split top-level cost is returned verbatim, never cross-checked against `card_faces[0]` even when hydration disagrees (test-pinned). The invariant was measured at `d51b467`, not schema-guaranteed; a future import that populates top-level costs differently renders wrong pips silently — deferred, the guard belongs to the importer/canary layer (c3-retro weekly live-contract precedent), not this panel.
- [x] [Review][Defer] **Registry guards are structurally blind to untracked modules** [`ui/tests/copy-rules.test.ts`, `token-usage.test.ts`, `posture.test.ts`] — the underlying `git ls-files` walk (the false-green mechanism) is real but pre-dates this story; the comment corrections + ledger entry are patched above, the walk redesign is deferred.

- Epic story text — `_bmad-output/planning-artifacts/epics-companion-app.md:2084-2121`
- UX-DR19 (deck row) — `epics-companion-app.md:437-440` · UX-DR12 (group header) — `:392-393`
- UX-DR3 (tabular numerals) — `:346-349` · UX-DR40 (Tab order) — `:566-570`
- UX-DR44 (semantics) — `:590-595` · UX-DR45 (announcements) — `:597-601` · UX-DR47 (hit box) — `:608-609`
- FR-05 — `:55-58` · FR-17 — `:105-107`
- `DESIGN.md:177-185` (`deck-row` + `group-header` frontmatter) · `:391-392` (anatomy prose)
- `DESIGN.md:294`, `:305`, `:317-318`, `:331`, `:333`, `:343-352`, `:360`, `:372`
- `EXPERIENCE.md:36` (panel), `:87` (row), `:112`, `:138`, `:141`, `:144`, `:152`, `:154-155`
- Derivation — `ui/src/state/deckGroups.ts:5-8, 60-67, 90-100, 163-193, 216-221, 228-241`
- Inspection — `ui/src/state/inspection.ts:41-54, 91-99, 109-128, 182-185, 210-211, 239-241, 338-342`
- Deck-transition memory — `ui/src/containers/CardDetail/deckMemory.ts:29-38`
- Grid's handover — `ui/src/containers/CardGrid/CardGrid.tsx:18-40`; `CardGrid.test.tsx:98-104`
- Primitives — `Panel.tsx:9-67`, `Panel.css:19`; `GroupHeader.tsx:11-38`, `GroupHeader.css:8-15`
- Mana — `ManaCost.tsx:19-84`, `ManaPip.css:21-49`
- Shell — `AppShell.tsx:66, 134`, `AppShell.css:132-172`; `AppShell.test.tsx:118, 161, 171`
- App rulings — `App.tsx:56, 84-87, 97-116, 211-212`; `App.test.tsx:473-515`
- Tokens — `ui/src/styles/tokens.css:99-133, 142-152, 160-178, 194-249, 252-270`
- Guards — `shell.test.ts:960, 1002-1032, 1268, 1457, 1652`; `token-usage.test.ts:813, 1086, 1098,
  1110, 1142, 2305`; `tokens.test.ts:306`; `copy-rules.test.ts:103, 481`; `posture.test.ts:339`;
  `store-writes.test.ts:77`; `wire-contract.test.ts:145`; `gate-geometry.test.ts:53`
- Wire — `src/data/schemas/deck.py:111, 234, 264`; `src/data/schemas/card.py:65, 112, 223`;
  `src/companion/app/routes/cards.py:123`; `ui/src/api/types.d.ts:325, 430-449`
- Price absence — `deferred-work.md:1985-2004`; `tests/unit/companion/test_routes_cards.py:136, 152`;
  `CardDetail.tsx:104-111`
- Ledger, this story's entries — `deferred-work.md:1331-1362, 1400-1419, 1429-1445, 1668-1699,
  3411-3421, 3448-3452, 3456-3464, 3515-3520`
- Ledger, live traps — `deferred-work.md:3587-3596, 3598-3609, 3611-3621, 3736-3739, 3750-3752,
  3778-3794, 3809-3812`
- Prior records — `c4-5:...:239-319, 360-386, 435-439, 656-658, 788-792, 837-850, 975-977,
  1017-1023, 1052-1058, 1097-1103, 1105-1118, 1169-1176`; `c4-6:...:309-355, 382-421, 1232-1235,
  1280-1284, 1336-1343, 1364-1375`
- CI bundle sync — `.github/workflows/ci.yml:114-167`

---

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`.

### Debug Log References

#### Task 0 — the sixteen rulings, and what re-measurement changed

Every measurement in the story reproduced **exactly** against the shipped database at `d51b467`
(38,261 cards / 40 decks / 2,027 `deck_cards`, 1,999 live): 23 columns with no price; 3,225 faced
cards; 3,225 blank top-level `oracle_text` (100%); **2,830 blank `mana_cost` (87.8%)**; 3,194 names
carrying `' // '` (99.0%); 338 split costs (10.5%); 67 live DFC rows / 40 distinct; **38 rows / 24
cards** with a blank cost, of which **26 rows / 18 cards** have a real `card_faces[0].mana_cost` and
12 rows / 6 cards are genuinely costless — 26 + `Pym Particles` = the story's **27 rows / 19 cards**
that would draw an empty pip cell. §D's group table reproduced row-for-row.

**Q1 — ruled AS PROPOSED (Brad, 2026-08-06).** The grid collapses to `34px minmax(0, 1fr) auto`.
`DESIGN.md`'s `components.deck-row.columns` frontmatter **and** its `:405` prose amended in this
commit with the reason inline (the c4-5 `pinned-ring` precedent). The absence is asserted at the
**type** (`Extract<keyof CardSummary, 'price' | 'prices'>` is `never`, which fails `tsc` the day a
price field reaches the wire — a grep could not, and `test_routes_cards.py:136` warns the next
author off exactly that) and by a **rendered** check that no `$` reaches the glass and that every
row has exactly three cells. The price-import brief was **not** raised.

**Q2 — ruled AS PROPOSED.** `frontFaceCost.ts`, three shapes, total over `null`. Split-first
ordering is load-bearing and is tested as such. c4-6's no-re-drive window is **cited, not
re-opened**, and its concrete consequence written into the module: a blip during the sweep leaves
those 26 rows permanently pip-less until a reload.

**Q3–Q16 — all AS PROPOSED, with ONE stated relocation the first writing of this line omitted
(added at review 2026-08-06):** Q5/AC 19's both-direction type-level asserts live in
`DeckList.tsx`, not `copy.ts` where the proposal put them — `copy.ts` is import-free by its own
contract and a `Record<TypeGroup, string>` annotation there would need the type import (TS2835);
the CardPlaceholder precedent holds the asserts beside the consumer instead. Functionally
equivalent, both directions verified. Reasons for the rest recorded in the shipped source rather
than only here.
Q6 was checked before writing, as the task demanded: `expectedNames` is a **hand list** for
per-component composites (three precedents, all filed under a `components.*` key rather than
`components.elevation`), so `--shadow-deck-row-live` joins it and is asserted byte-for-byte against
the artefact. Q15 was ruled **by measurement** — see the eye-check.

**AC 43 — the two doc corrections, written with the decomposition Brad chose over the literal.**
Both numbers in `deckGroups.ts` were wrong in a way that would have gone wrong again:

- *"84 corpus cards"* → **82**, and the line now says **which** disagreement it counts.
  `groupOf` and the whole-string policy disagree on **116** cards in total: **82** through the
  front-face `//` split (what the clause is about) and a further **34** single-faced cards that
  disagree through *first-match-wins precedence* — `Artifact Land` (25 of them) groups as
  **Artifact**, `Land Creature — Island Fish` as **Creature**. A bare "82" is what let this drift
  twice; the corrected line carries the re-measurement recipe.
- *"the two copies of Pym Particles"* → **one**, with the trap kept. There genuinely **are** two
  live rows named `Pym Particles`, but they are two different **printings** in two different decks:
  `msh` #70 is an ordinary `Sorcery` and groups as one; only `fmsc` #28 (`type_line = 'Card'`) lands
  in `Other`. Counting by NAME finds two, counting by GROUP finds one, and the bucket is about the
  group. The story's own *"it is one copy"* was imprecise in the other direction.

#### A live trap found while writing Task 2, which changed the implementation

`deckGroups.ts:131`'s exported `frontFace` splits on a **loose** pattern and argues at length that
loose is *"the strictly-safer reading of the two"*. **That argument is correct for a type line and
it inverts for a name**, so this story does not reuse it:

- For a type line, an unsplit `'Sorcery//Land'` matches no group and lands in `Other` — loose fails
  toward the right answer.
- For a NAME there is no matching step to fail; a loose split simply truncates, and the truncated
  string is rendered. Measured: **exactly one card in 38,261 carries an unspaced `//` in its
  `name`** — `'SP//dr, Piloted by Peni'`, a **single**-faced Legendary Artifact Creature — and the
  loose pattern renders it as **`'SP'`**.

`frontFaceName` therefore splits on the **literal** `' // '`. It is in no live deck today and is one
`add_card_to_deck` away; the literal costs nothing, because all 3,194 faced names and all 338 split
costs use the spaced form and **no single-faced card carries `' // '` in either field**. Pinned by a
named test.

#### A contrast defect found by measurement, fixed, and the artefact amended

DESIGN.md's Colors table asserts that all three text tiers clear 4.5:1 *"on all four surfaces"*. **A
live row is a fifth surface that table does not cover**: `--accent-glow` is `rgba(139,147,255,0.22)`,
which composites over `--surface-panel` to `#32365A`. Against that, `--text-tertiary` — which
`DESIGN.md:405` specifies for the quantity — measures **3.73:1**, and `--type-numeric` is 13px, so
the 4.5:1 small-text floor applies and **the quantity fails AA in the live state alone**, while
measuring a comfortable 5.43:1 at rest, which is why nothing catches it. `--text-secondary` on the
same composite is **5.89:1**.

This is the M4/C3 family arriving a third time — and in a new shape: the first two were a *marker
over a surface*, this is a *text tier over a tint*. Fixed (`.deck-row.is-live .deck-row-quantity`),
artefact amended in the same commit, and **verified live**: the running page measures the live
quantity at `rgb(179, 184, 207)`. `findAccentDimOnOverlay` cannot see this class of defect — it is
same-block only, and this is a parent's background composited with a child's colour.

#### The registry guards are blind to an UNTRACKED file — a false green worth knowing about

The first full `npm test` after writing every new module came back **1274/1274 green with no
`CONTAINERS` and no `COPY_MODULES` entry written**. `shell.test.ts` walks `git ls-files`, so a new
module that has not been `git add`ed is not merely un-listed, it is **invisible**, and the coverage
guard passes over a file it cannot see. Staging the files turned up the three expected reds at once.

That guard's own comment reads *"git, not readdir, so an untracked module cannot pass vacuously
either"* — which is the opposite of what happens. Not repaired here (it is a guard this story does
not own and the fix is a decision about whether `readdir`/`git ls-files --others` should join the
walk), but it is a real hole with a live demonstration, and it is raised as a ledger entry below.

#### Probes (AC 39) — sixteen, fourteen behaved, and BOTH exceptions were real

Run through the **full `npm test`** every time, never a standalone file run, each applied to the
working tree and reverted from the index.

| # | probe | verdict | caught by |
|---|---|---|---|
| a | a new container module absent from `CONTAINERS` | CAUGHT | `shell.test.ts` |
| b | `--radius-card` in the text-first `DeckList.css` | CAUGHT | `token-usage.test.ts` |
| c | the row named from its **back** face | CAUGHT | `frontFaceCost.test.ts` + `DeckList.test.tsx` |
| d | the sideboard silently dropped (conservation) | CAUGHT | `DeckList.test.tsx` |
| e | the panel re-`sort()`s the rows itself | **PASSED — a real hole** | now `DeckList.test.tsx` |
| f | `clearHovered` replaced by an unkeyed clear | CAUGHT | `DeckList.test.tsx` |
| g | the component writes a store directly | CAUGHT | `store-writes.test.ts` + 3 more |
| h | an **unregistered** `transform` on the row | CAUGHT | `token-usage.test.ts` |
| h′ | the reduced-motion registration deleted (`--motion-pulse: 0ms` removed) | CAUGHT | `token-usage.test.ts` *"zeroes all four duration tokens"* |
| b′ | a **chrome** radius (`--radius-md`) added to a CARD_SHAPED file | CAUGHT | `token-usage.test.ts` — 3 tests red, headline *"never gives a card-shaped file a CHROME radius"* |
| i | `--type-numeric` without `font-variant-numeric` | CAUGHT | `token-usage.test.ts` |
| j | `aria-live` added to the panel | CAUGHT | `DeckList.test.tsx` |
| k | an authored word inlined instead of from `copy.ts` | CAUGHT | `copy-rules.test.ts` |
| l | the live rule inlined rather than tokenised | CAUGHT | `shell.test.ts` |
| m | a bare `1fr` in the row grid | CAUGHT | `shell.test.ts` |
| n | a wire shape re-declared outside `src/api/` | CAUGHT | `wire-contract.test.ts` |
| o | **negative control** — a comment in `DeckList.tsx` | stayed green | — |
| p | **negative control** — a comment in `DeckList.css` | red once, **green on re-run** | — |

**(e) PASSED, and it was my own test that was weak — recorded, not quietly fixed.** Inserting a
`.sort()` over `section.cards` left the whole suite green, because **every fixture happened to put
one card in each type group**, so a sort *inside* a section had nothing to reorder. The assertion
was measuring **between**-group order — which `boardsOf` guarantees regardless of what this
component does — and calling it proof of **within**-group order, which nothing checked. Closed by a
named test (*"preserves the store's order WITHIN a group, not just between groups (probe e)"*) with
three creatures given in non-alphabetical order; probe (e) re-applied against it goes red.

**(p) was the ledgered vitest worker-crash flake, confirmed live.** The negative control reported a
non-zero exit **with no failing assertion** — and, unlike every genuine catch above, produced no
`FAIL` lines at all. Re-run manually per the story's own instruction: 1323/1323 green. The control
holds. Worth noting that this is the second story to hit it and that the tell (red exit, zero
failing assertions) is what distinguishes it from a real red.

**(h′) and (b′) were run at the review (2026-08-06), because the first pass deviated without
saying so.** AC 39's enumerated (h) is *"the reduced-motion registration deleted"*; the table's
original (h) ran a different probe (an unregistered `transform`) and recorded no substitution.
Similarly the enumerated (b) is two-part — a chrome radius in a CARD_SHAPED file **and**
`--radius-card` in `DeckList.css` — and only the second half had been run, though a residue line
claimed both directions. Both enumerated probes have now been executed live: deleting the
`--motion-pulse: 0ms` zeroing turned *"zeroes all four duration tokens"* red; appending a
`--radius-md` rule to `CardPlaceholder.css` (a CARD_SHAPED file) turned three tests red. Both
files byte-restored; `token-usage.test.ts` 72/72 green after restore.

#### The eye-check (AC 33, AC 34, AC 40, Q7, Q15) — headless Chrome over CDP, against the running backend

Chrome 151 headless at 1440×1100 against the live companion on `127.0.0.1:8765`, three decks, both
motion settings. Numbers are measured off the running page, not described.

| measurement | `Atraxa Counter Cabinet v2` | `MSH — The Mad Titan's Gauntlet` | `Prismatic Dragon` |
|---|---|---|---|
| rows drawn | **99** | **42** (33 main + 9 sideboard) | **38** |
| sections | 8 (Commander + 7 groups) | 7 (6 groups + **Sideboard**) | 5 |
| rendered panel height | **3,198 px** | 1,474 px | 1,288 px |
| internal scrollers | **0** | 0 | 0 |
| `<img>` in the panel | **0** | 0 | 0 |
| live rows | **exactly 1** | 1 | 1 |
| row hit box | **410 × 29 px** | 29 px, uniform | 29 px, uniform |
| grid template | **`34px 279px 77px`** — three tracks | — | — |
| names overflowing their track | 0 | 0 | 0 |
| a `//` spoken or visible anywhere | **no** | **no** | **no** |

- **AC 7 — the hit box is 410 × 29 px**, uniform across every row of all three decks, clear of the
  24×24 floor. It comes from padding, not a `min-height` literal needing its own citation.
- **AC 31 — the reduced-motion fallback is MEASURED, not asserted**: `transition-duration` reads
  `0.1s, 0.1s` at `no-preference` and **`0s, 0s`** under `prefers-reduced-motion: reduce`. The
  mechanical claim holds — no `transform` ships, so zeroing the duration leaves nothing moving, and
  the enumerated shipped-motion pin correctly did not move.
- **AC 13 — the live row**: background `rgba(139, 147, 255, 0.22)` (`--accent-glow`), box-shadow
  `rgb(139, 147, 255) 2px 0px 0px 0px inset` (the new token), name `rgb(233,235,245)` at weight
  **700**, quantity `rgb(179,184,207)` — the contrast fix, live. At rest: quantity
  `rgb(139,145,173)` (`--text-tertiary`), name `rgb(179,184,207)` (`--text-secondary`, Q12).
  Sampled from a row that is **not** the cold-open target, since row 0 is legitimately live on load.
- **AC 33 — `Panel` at `level="default"` and `GroupHeader` verified by eye, closing deferral 1 (open
  since c2-7).** Panel background `rgb(25,28,43)` = `--surface-panel`, the default level. Header
  label `rgb(179,184,207)` **uppercased by CSS** with `letter-spacing: 1.1px`, count in tabular
  numerals, over a `1px solid rgb(44,48,72)` hairline. **The tone-over-wash contrast the deferral
  said was unmeasured, now measured**: label **8.59:1**, count **5.43:1** — both clear of 4.5:1; the
  rule is 1.31:1 and is decorative, with no floor. The failure mode the ledger warned to check first
  — *"a solid blank pill with invisible text"* — does not occur.
- **AC 34 — `ManaCost`'s composition in a row (deferral 3)**: pips render in the `auto` track at
  their fixed size; **no row wrapped to a second line** in any of the three decks (every row height
  is 29 px), and no name overflowed its `minmax(0, 1fr)` track. Spoken labels read
  `"3 generic, white, black, green"`.
- **Q7 — no internal scroller, confirmed.** The 99-card panel renders **3,198 px** tall and the page
  scrolls; zero descendants have `overflow-y: auto|scroll`, so `CardDetail`'s exemption remains the
  only one and no second WCAG 2.1.1 scroller was created.
- **Q15 — ruled by measurement: SHIP AS WRITTEN, no correction homed.** Chrome's own accessibility
  tree reports `heading level=1` (the deck name), then `region: Card detail`, `region: Deck list`,
  and **every** panel title and group divider flat at `heading level=2` — exactly what UX-DR44 says.
  It does not read wrong: the two `region`s carry the grouping a heading level would otherwise have
  to, and every heading is reachable. No `h3` correction on taste. **The same tree confirms the
  phantom-`banner` blind spot from the other side**: Chrome reports **exactly one** `banner` (the
  shell's own header), where jsdom would now report three.

#### A correction to AC 40's own premise

AC 40 asks for *"a deck with all three boards (`MSH — The Mad Titan's Gauntlet`)"*. **MSH has no
commander**, and more than that: **no deck in the corpus has both a commander and a sideboard —
zero of 40.** All 16 commander decks have 0 sideboard rows; all 5 sideboard decks (all MSH
Standard-style) have 0 commander rows. The three-board render is therefore **not producible from
live data at all** and exists only in a constructed fixture — which is what AC 22's conservation
test uses, and it is the honest reading of *"a real fixture with all three boards populated"*. The
eye-check covers the two halves separately and on real data: commander-plus-groups on Atraxa,
groups-plus-sideboard on MSH.

### Completion Notes List

**What shipped.** The deck list panel: a titled `Panel` at `level="default"` in `AppShell`'s `right`
slot beneath `CardDetail`, holding commander → mainboard type groups in `TYPE_GROUPS` order →
sideboard, each a `GroupHeader` over a `ul`/`li` of `<button>` rows carrying quantity, front-face
name and front-face cost, wired to the inspection slice with the identical five verbs a tile uses.

**The three things the story said were not simple, and how each landed.**

1. **The price column is gone**, on Brad's Q1 ruling, with `DESIGN.md` amended in both its
   frontmatter and its prose in the same commit, and the absence asserted at the type and on the
   glass. Shipped as `34px minmax(0, 1fr) auto` — measured live as `34px 279px 77px` — then the
   quantity track widened to `minmax(34px, max-content)` at the review (Brad's ruling): 34 is the
   corpus maximum, which is a measurement and not a bound, and an unlimited-copy import (×100
   Relentless Rats) must widen the track rather than clip. DESIGN.md carries the second amendment.
2. **The front-face cost resolves three ways**, in `frontFaceCost.ts`, split-first. The name half is
   free and correct at first paint; the cost half depends on the hydration sweep for 26 live rows
   and inherits c4-6's no-re-drive window, cited in the module.
3. **`GroupHeader` has its first production consumer** after zero since c2-7, and `Panel`'s default
   level its first — both verified against a real engine with contrast numbers, closing deferral 1.

**One AC clause resolved differently from the story's expectation** — AC 40's three-board deck does
not exist in the corpus (see above). Everything else landed as written.

#### The nine inherited deferrals — a disposition each (AC 38, C2 retro R2)

1. **`Panel` (default level) + `GroupHeader` appearance — RESOLVED.** Eye-checked against Chrome
   with numbers (AC 33 above), including the tone-over-wash contrast the 2026-07-29 extension said
   was unmeasured: 8.59:1 label, 5.43:1 count. The warned-of failure mode does not occur.
2. **The ` // ` separator spoken as literal characters — CLOSED BY CONSTRUCTION on this surface,
   and it is the split that closes it.** Because `frontFaceCost` splits before rendering, a `' // '`
   never reaches `ManaCost` from a deck row; measured live across three decks,
   `anySeparatorSpoken: false` and `anySeparatorVisible: false`. **Still live wherever a COMBINED
   cost renders** — `CardDetail` and `CardPlaceholder` both still pass an unsplit cost — so the
   ledger entry stays open for those, re-homed unchanged. Not closed globally.
3. **`ManaPip`/`ManaCost` appearance — RESOLVED as composition only**, which is what c4-3 said this
   story inherits. Checked in the row's `auto` track: no wrap, no overflow, fixed pip size.
4. **The `'Card // Card'` grouping fix — DECLINED, and re-homed with the reason (Q10).** The data
   blocker is gone; the **mechanism** one is not. `boardsOf` runs once at store-write time and the
   resulting reference identity is what `deckMemory.ts` and `CardDetail`'s effect use to detect a
   deck replacement, so re-deriving after hydration would produce a new `boards` for the same deck
   and fire a spurious deck-transition clear, **releasing the user's pin mid-session**. 2,274 corpus
   rows, **0 in any live deck**, against a mechanism change that breaks a shipped contract. Honest
   home: a story that owns the derivation's timing (a hydration-aware second pass, or the
   `CardSummary` field c4-6's Q1 priced). *"The blocker is removed" was a claim about the data and
   needed re-checking against the mechanism.*
5. **`strategy` wire asymmetry — NOT TRIGGERED, re-homed unchanged (Q13).** The candidate was
   checked rather than assumed: this panel renders cards, and `strategy` is deck-level prose with no
   row to sit in. Still awaiting its first reader.
6. **`DeckRepository.list_decks` ties on `created_at` — NOT TRIGGERED, re-homed unchanged.** The
   ledger's named home says *"any UI that promises newest first (c4-7's deck-list panel)"*, but that
   entry means the **list of decks** and this story renders the **cards of one deck**. It calls
   `GET /api/decks` not at all. Mentioned rather than silently skipped, as R2 requires.
7. **UX-DR44's heading-level collision — MEASURED, NO CORRECTION HOMED (Q15).** See the eye-check:
   Chrome reports a flat list of `level=2` headings and the two `region`s carry the grouping. It
   does not measurably read wrong, so `GroupHeader.tsx:11-16`'s invitation is declined on evidence
   rather than on taste, and the measurement is recorded either way.
8. **F1: story-key-shaped strings on the rendered view — COUNT RECORDED.** `c4-7` was already off
   the glass, because c4-5 displaced all three keys at once (they shared one placeholder string);
   what changes here is that it is displaced by **its own** panel. Both halves are now asserted in
   `App.test.tsx`. **Remaining F1 keys on a rendered deck view: 5**, unchanged by this story — the
   gate itself stays c8-5's.
9. **Panel-stacking vertical budget — FED INTO Q7 AND MEASURED.** The advisory was right and the
   number is now known: this panel adds **3,198 px** beneath a card-detail panel that already spends
   a screenful. No internal scroller (Q7); the page scrolls and every row is a Tab stop that the
   browser scrolls into view, which is the property the oracle scroller lacks.

#### The six triggered "next X" residues — a line each (AC 38)

- **The next motion** (`tokens.css:269`, reserved by name) — **filled, mechanically.** The tint
  transitions `background-color` and `box-shadow` over `--motion-pulse` and nothing else, so zeroing
  the duration is the whole fallback; measured `0s, 0s` under reduce. **No `transform` ships**, so
  the derived guard needs no `!important` rule and the enumerated shipped-motion pin stays at **4**.
  A later story that gives a deck row a transform inherits both halves, and that is written down.
- **The next cross-file card-shape collision** (`deferred-work.md:3587-3596`, which names `.deck-row`
  by name) — **not triggered, and deliberately kept that way.** `DeckList.css` styles only its own
  `.deck-*` classes and never reaches into a `.card-shape` descendant, so the illustrative case
  stays hypothetical. Probe (b) confirms the file is held out of `CARD_SHAPED` in both directions.
- **The next flippable-fixture toucher** (`deferred-work.md:3809-3812`) — **not triggered.** This
  story's DFC tests construct `card_faces` inline in `DeckList.test.tsx` for the hydrated tier only
  and do not copy the flippable **wire** fixture, so there is still no fourth copy and no shared
  helper is owed by this diff. Re-homed unchanged.
- **The next story that renders an identifier** (`deferred-work.md:3598-3609`) — **triggered and
  answered, though nothing checks it.** The row's count is `--type-numeric`, which is the right role
  for a quantity; the residue's point stands that *nothing verifies the right type role was chosen
  for the content*, and this story adds no such guard. Re-homed unchanged.
- **`StatChip`'s first surface — NOT triggered.** DESIGN.md's deck-row anatomy calls for no chip and
  none ships. Said explicitly, as the story asked.
- **The hydration sweep's no-re-drive window** (c4-6 review ruling 1) — **cited, not re-opened.**
  Q2's cost resolution sits directly inside it: a blip during the sweep leaves 26 DFC rows
  permanently pip-less until a reload, with no error state, while their single-faced neighbours look
  fine. Written into `frontFaceCost.ts` rather than papered over with a retry this story does not
  own.

#### New ledger entries this story raises

1. **The `CONTAINERS` coverage guard is blind to untracked modules** — demonstrated live (see the
   Debug Log). A new container that has not been `git add`ed passes every registry gate, and the
   guard's own comment claims the opposite. Home: whoever next touches `shell.test.ts`'s file walk;
   candidate fix is `git ls-files --others --exclude-standard` joining the walk.
2. **The plugin bundle mirror is still checked by nothing** (AC 42). Updated **by hand** this story
   and verified byte-identical for all four files. `src/companion/app/static/` is CI-enforced
   (`ci.yml:154-167`); `plugin/server/src/companion/app/static/assets/` has no test, no workflow and
   no script. Not fixed here — it is a CI change outside this story's surface — and raised with a
   named home: **the C4 retro**, as a one-line workflow addition.
3. **`CardTile.tsx:178` says its constant is *"written as an escape"* and ships the literal
   character.** Same codepoint, nothing renders differently, no test moves — but the comment is not
   true of the line beneath it. Not edited here: it is a file on the don't-break list and the
   change is cosmetic. **Corrected at review (2026-08-06): this story's own constant had the
   IDENTICAL defect when this entry was first written** — `DeckList.tsx:138` shipped the literal
   character under a comment claiming a genuine escape, while this very entry mocked `CardTile`
   for it. The escape is real now (byte-verified `\u00D7`), and it is real because the
   Acceptance Auditor checked the bytes rather than the comment.

### File List

**New**

- `ui/src/containers/DeckList/DeckList.tsx`
- `ui/src/containers/DeckList/DeckList.css`
- `ui/src/containers/DeckList/DeckList.test.tsx`
- `ui/src/containers/DeckList/copy.ts`
- `ui/src/containers/DeckList/frontFaceCost.ts`
- `ui/src/containers/DeckList/frontFaceCost.test.ts`

**Modified**

- `ui/src/App.tsx` — mounts `DeckList` as the second child of `right`; `AppShell.tsx` untouched
- `ui/src/App.test.tsx` — Q9's scope-don't-bump repair, the `c4-7` displacement assertion
- `ui/src/state/deckGroups.ts` — AC 43's two doc corrections (comments only; no behaviour change)
- `ui/src/styles/tokens.css` — `--shadow-deck-row-live`; the c4-7 reduced-motion statement
- `ui/tests/tokens.test.ts` — `expectedNames` + pin 68 → 69; the `deck-row` frontmatter type; the
  live-rule value assertion; the price-track assertion
- `ui/tests/token-usage.test.ts` — `declaredTokens.size` 68 → 69
- `ui/tests/shell.test.ts` — three `CONTAINERS` entries; the pin 10 → 13
- `ui/tests/copy-rules.test.ts` — the `COPY_MODULES` entry
- `_bmad-output/planning-artifacts/ux-designs/.../DESIGN.md` — `deck-row.columns` amended (Q1,
  frontmatter + prose); the live-state quantity tier added as a contrast correction
- `src/companion/app/static/` — rebuilt bundle (`index.html` + both assets)
- `plugin/server/src/companion/app/static/` — the hand-copied mirror (AC 42)

**Python: untouched** (AC 44).

#### The measured record against the `d51b467` baselines (AC 41)

| baseline | at `d51b467` | now | note |
|---|---|---|---|
| frontend tests | 1,255 / 50 files | **1,326 / 52 files** | +71 tests, +2 files (1,324 at dev; +2 review guards in `frontFaceCost.test.ts`) |
| Python tests | 2,501 passed / 1 skipped | **2,501 passed / 1 skipped** | unchanged (AC 44) |
| tokens | 68 (two pins) | **69** (both pins moved together) | `--shadow-deck-row-live` |
| containers | 10 | **13** | `DeckList.tsx`, `copy.ts`, `frontFaceCost.ts` |
| primitives | 17 | **17** | none added |
| stores | 5 | **5** | no new slice, no `setState` from a component |
| copy modules | 8 | **9** | `DeckList/copy.ts` |
| `CARD_SHAPED` | 4 | **4** | the list is text-first and does not join |
| shipped-motion pin | 4 | **4** | no `transform` ships (AC 31) |
| bundle JS | `index-DmtAq_d6.js` 215,832 B | **`index-Ddi5V_oI.js` 218,040 B** | changed, +2,208 B (dev build was `index-Bd1UijdF.js` 217,931 B; re-hashed at review — the escape + the review guards) |
| bundle CSS | `index-DjIbf6Qz.css` 15,323 B | **`index-CqSzkms6.css` 17,083 B** | changed, +1,760 B (dev build was `index-CWp3yHqM.css` 17,063 B; re-hashed at review — the quantity-track `minmax`) |
| font | 22,288 B | 22,288 B | untouched |
| plugin mirror | — | **byte-identical, hand-copied** | verified per file (AC 42) |

**Both bundle assets changed, hash and byte count.** c4-5's phrasing applies — a byte-identical JS
bundle here would have meant it did not ship.

**Ten gates, all green:** `npm run lint`, `npm run format:check`, `npx tsc -b --force` (never
`tsc -b`), `npm test`, `npm run build`; `uv run pytest`, `ruff check .`, `ruff format --check .`,
`mypy src/`, `mypy src/ --platform win32`.

#### Tab order (AC 29), recorded explicitly

Header nav → the card grid's tiles, each followed immediately by its own flip control where one
exists (c4-6) → `CardDetail`'s **unpin control**, an unenumerated stop that appears only while a
card is pinned (c4-5) → **these deck rows, one Tab stop each, in rendered order: commander,
then the mainboard's type groups in `TYPE_GROUPS` order, then the sideboard** → connection pill →
footer links. Nothing in this story carries a `tabindex`; the order is document order, and every
row is a real `<button>` so the browser scrolls each into view — which is what makes Q7's
"no internal scroller" ruling safe on a 3,198 px panel.

### Change Log

| Date | Change |
|---|---|
| 2026-08-06 | Story contexted off `d51b467` → `ready-for-dev`. 44 ACs, 16 open questions, 9 inherited deferrals, 6 triggered residues, 18 don't-breaks. |
| 2026-08-06 | Task 0: all sixteen questions ruled — Q1, Q2 and AC 43's wording by Brad, the rest as proposed. Every story measurement reproduced exactly; two doc numbers corrected with their decomposition. |
| 2026-08-06 | Tasks 1–5 implemented: `copy.ts`, `frontFaceCost.ts`, the row, the groups and both boards, mounted in `App.tsx`. Token layer 68 → 69, both pins. `DESIGN.md` amended twice (Q1's dropped price column; the live-state quantity contrast fix). |
| 2026-08-06 | Task 6: registries (`CONTAINERS` 10 → 13, one `COPY_MODULES` entry) and sixteen probes. 14 caught; probe (e) exposed a real hole in this story's own order test and is closed by a named test; negative control (p) was the ledgered vitest worker-crash flake, green on re-run. |
| 2026-08-06 | Task 7: ten gates green; CDP eye-check over three decks and both motion settings, closing deferral 1 with measured contrast and ruling Q15 by Chrome's accessibility tree. Bundle rebuilt (both assets changed), plugin mirror hand-copied. Status → `review`. |
| 2026-08-06 | Three-layer review: 22 findings → 1 decision + 18 patches applied, 2 defers, 3 dismissed. Two Highs: the rebuilt bundle assets were UNTRACKED (the c4-3 finding class, now staged — and the exact blindness the story's own registry-guard discovery describes) and `MULTIPLICATION_SIGN` shipped the literal character under a comment claiming an escape while ledger entry 3 mocked `CardTile` for the identical defect (now a real escape, byte-verified). Brad's ruling: quantity track → `minmax(34px, max-content)` + DESIGN.md amendment. Also: AC 2's missing absence test written; the deferred-work.md ledger written (it was record-only); enumerated probes (h) and (b)'s CARD_SHAPED half run red; the three registry-guard comments now declare the untracked-file limit; `tokens.css`'s wrong-surface contrast claim corrected; DESIGN.md's card-detail price line amended; `frontFaceName` empty guard + branch-3 separator re-split (+2 tests); five test hardenings. Bundle re-hashed (`index-Ddi5V_oI.js` / `index-CqSzkms6.css`), mirror re-copied byte-identical. 1,326/1,326 green; lint, format, tsc clean. Status → `done`. |

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

2026-08-06: CODE-REVIEWED -> done. Three-layer review (Blind Hunter + Edge Case Hunter + Acceptance Auditor): 22 raw findings -> 1 decision + 18 patches applied, 2 defers, 3 dismissed. TWO HIGHS, both record-vs-reality: (1) the rebuilt bundle assets were UNTRACKED -- the diff repointed both index.html files at assets it never added, the exact c4-3 finding class, in the story whose own headline discovery is that the guards are blind to untracked files (now staged; assets re-hashed at review to index-Ddi5V_oI.js 218,040 B / index-CqSzkms6.css 17,083 B, mirror re-copied byte-identical); (2) MULTIPLICATION_SIGN shipped the LITERAL character under a comment claiming a genuine escape, while ledger entry 3 mocked CardTile.tsx for the identical defect -- now a real backslash-u escape, byte-verified. BRAD'S RULING: quantity track 34px -> minmax(34px, max-content) + DESIGN.md amendment (34 is a corpus measurement, not a bound; x100 unlimited-copy imports are legal). ALSO PATCHED: AC 2's required deck-list-absence test written (the c4-5 checkbox-without-test family); the deferred-work.md ledger WRITTEN (all nine dispositions + new entries lived only in the story record); enumerated probes (h) and (b)'s CARD_SHAPED half RUN red then restored (the first pass had silently substituted (h)); the three registry-guard comments now DECLARE the untracked-file limit instead of claiming the opposite; tokens.css's wrong-surface contrast claim corrected (rows sit on surface-panel 6.21:1/3.05:1, not overlay 5.5:1/2.70:1); DESIGN.md's card-detail line no longer specifies a price; frontFaceName empty-string guard + branch-3 separator re-split (+2 tests); five test hardenings (full heading-list compare, all pip runs labelled, AC 26's vacuous tail replaced by a distinguishable default, panel class tied to THE region, blank-cost test retitled honestly). DEFERRED: frontFaceCost shape-2's summary-wins invariant is a point-in-time corpus measurement (home: importer/canary); the registry guards' ls-files walk redesign (home: first story touching a registry test). 1,326 frontend / 52 files green; lint, format, tsc clean; Python untouched. Next: commit + PR into feat/companion-c4. Previously -- IMPLEMENTED -> review. The deck list panel. Q1 and Q2 ruled by Brad as proposed; AC 43's wording ruled to carry the decomposition. THE PRICE COLUMN IS GONE: grid collapses to `34px minmax(0, 1fr) auto` (measured live as `34px 279px 77px`), DESIGN.md amended in BOTH its frontmatter and its prose, absence asserted at the TYPE (fails tsc the day a price reaches the wire) and on the glass. A LIVE TRAP FOUND AND IT CHANGED THE IMPLEMENTATION: deckGroups.ts's exported `frontFace` splits on a LOOSE pattern and argues loose is safer -- true for a type line, INVERTED for a name, because a loose split truncates `SP//dr, Piloted by Peni` (a SINGLE-faced card, 1 of 38,261) to `SP` with no matching step to fail toward; the name split uses the literal ' // '. A CONTRAST DEFECT FOUND BY MEASUREMENT AND FIXED: a live row is a FIFTH surface DESIGN.md's Colors table does not cover -- accent-glow composites over surface-panel to #32365A, where --text-tertiary on a 13px numeral is 3.73:1 and fails AA in the live state ALONE while measuring 5.43:1 at rest; lifted to --text-secondary (5.89:1), artefact amended, verified live. The M4/C3 family a third time and in a NEW shape -- a text tier over a tint, not a marker over a surface. Sixteen probes: 14 caught, and BOTH exceptions real -- probe (e) PASSED because every fixture put ONE card per group so a within-section sort had nothing to reorder (the test measured BETWEEN-group order and called it proof of within-group order; closed by a named test), and negative control (p) was the ledgered vitest worker-crash flake, green on re-run (tell: red exit, ZERO failing assertions). FALSE GREEN WORTH KNOWING: the registry guards walk `git ls-files`, so a new module that is not `git add`ed is INVISIBLE and passes -- the first full run came back 1274/1274 green with no CONTAINERS or COPY_MODULES entry written; the guard's own comment claims the opposite. Eye-check RAN in headless Chrome over CDP across three decks and both motion settings: hit box 410x29px uniform, live rows exactly 1, panel 3,198px on the 99-card deck with ZERO internal scrollers, transition 0.1s -> 0s under reduce (the mechanical fallback MEASURED), and no ' // ' spoken or visible anywhere. Deferral 1 CLOSED (open since c2-7) with the tone-over-wash numbers it said were unmeasured: label 8.59:1, count 5.43:1. Q15 ruled BY MEASUREMENT -- Chrome's own a11y tree shows a flat list of level-2 headings with the two regions carrying the grouping, so UX-DR44 ships as written and NO correction is homed; the same tree confirms the phantom-banner blind spot from the other side (Chrome: exactly ONE banner; jsdom would now say three). A CORRECTION TO AC 40's OWN PREMISE: no deck in the corpus has both a commander and a sideboard -- ZERO of 40 -- so the three-board render is unreachable from live data and exists only in a constructed fixture. Deferral 4 (the 'Card // Card' fix) DECLINED with the mechanism reason recorded. 1,324 frontend / 52 files; Python 2,501 passed / 1 skipped UNCHANGED; tokens 68 -> 69 both pins, containers 10 -> 13, copy modules 8 -> 9, CARD_SHAPED 4, shipped-motion pin 4; bundle JS 215,832 -> 217,931 B and CSS 15,323 -> 17,063 B, BOTH changed; plugin mirror hand-copied byte-identical. Next: three-layer code review.
