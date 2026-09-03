---
epic: c4
story: c4-9
work_branch: feat/companion-c4
story_branch: feat/companion-c4-9-colour-distribution-panel
depends_on: >-
  c4-8 (merged at `1ed2e83`, PR #47) — `AnalysisRow`, the row this story gives its **second
  child**, whose narrow-width decision and whose land-only empty-row posture were both flagged to
  this story **by name**; `ManaCurve`, the sibling panel and the shape to match; `curve.ts`, whose
  `isLand` this story reuses and whose split-card pin **this story's parser turns red by design**;
  and the narrowed `no-restricted-syntax` hatch, keyed to the exact channel name
  `--curve-bar-height`, which a second channel joins in the open. c4-7 (merged at `0fdb41b`) —
  `frontFaceCost.ts`, the module that already resolves a front-face cost through three shapes and
  the hydration cache, and `DeckList`, the precedent for reading `useCardEntry` **per row** —
  which is exactly the shape this panel cannot use (§C). c4-2 (merged at `2a64231`) —
  `deckGroups.ts`, whose `frontFace` this story reuses and whose `:199` names **"the curve and
  colour panels"** by function when it excludes the sideboard. Also **c2-8** (`ManaPip`'s opt-in
  `label` prop, written for this legend by name; `parseManaCost`, the total tokeniser this story's
  pip count is built on; and `MANA_DATA_INK`, the allowlist this story is the **first** to join),
  **c2-7** (`Panel`), **c2-6** (`AppShell`'s `left` slot — the **eighth** application of the
  displacement ruling), **c2-4** (the token layer, 69 tokens, both pins).
baseline_commit: 1ed2e83
---

# Story C4.9: Colour distribution panel

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad checking whether my mana base matches my spells,
I want the deck's colour balance shown as one proportional bar with a readable legend,
so that I can see at a glance which colour is carrying the deck.

**What this story really is.** One bar, a handful of segments, and a legend. Three ACs of markup.

And then eight things that are not, six of them invisible from the acceptance criteria, and the
first of them changes what a real deck looks like on a real screen today.

1. **"Proportional to pip count" resolves two ways, and the two disagree on a quarter of the
   decks.** UX-DR18 says *"segmented by `mana-*` proportional to **pip count** across the deck"*
   and stops. A split card's `mana_cost` is `'{3}{B} // {1}{B}'`; an Adventure's is
   `'{1}{B}{B} // {1}{B}{B}'`. Counting the **whole string** counts both halves. Counting the
   **front face** counts what you pay to cast the thing you cast. Measured against the shipped
   database: **10 of 40 real decks change their bar**, and **2 of them change the ORDER of their
   segments**. `Prismatic Dragon` drops from **71 pips to 45 — 37% of its bar** — and re-orders
   from B>U>G>R>W to U>G≈B>R>W. `Abzan Dragons` loses 20% and black falls from 37% of the bar to
   30%. Both readings are defensible; **neither is written down anywhere**; and this is not a
   rounding difference, it is two different pictures of the same deck at first paint. That is
   **Q1**, and it is the only question whose answer is visible to Brad today.

2. **This panel walks back into the hydration window c4-8 was the first in four to escape.**
   c4-8 got its whole derivation free because `cmc` rides on `CardSummary`. Pip count does not:
   **2,830 of 3,225 faced cards (87.75%) carry a blank top-level `mana_cost`** — c4-7's
   measurement, re-confirmed — and their real cost lives in `card_faces[0]`, which only hydration
   supplies. Live, hydration is worth **48 pips across 16 of 40 decks**, and **34 of the 46 live
   blank-cost copies are recoverable**; every one of the 12 that are not is a Pathway MDFC land
   that correctly contributes nothing. So unlike every previous analysis panel, **this panel's
   numbers move after first paint** — and a *percentage* moving is louder than a pip appearing in
   a row. c4-6's accepted no-re-drive window applies and is cited, not re-opened. That is **Q2**.

3. **The obvious reuse is `useCardEntry`, and this component cannot call it.** `DeckList` reads
   the hydration cache with one `useCardEntry(cardId)` per `DeckRow` component — legal, because
   each row is its own component with its own single hook. This panel is **one** component
   aggregating up to 99 rows; a hook in a loop over a list whose length changes with the deck is
   the rules-of-hooks violation React actually breaks on. The alternatives are a whole-map
   subscription (`useCardStore((s) => s.cards)` — a stable reference, but it re-renders the panel
   on every one of ~99 hydrations) and `readCardEntry` (imperative, not reactive, so the bar would
   be **permanently stale** — silently correct-looking and wrong). Nothing in any artefact
   mentions this. **Q3.**

4. **The accessibility shape is the exact INVERSE of c4-8's, and copying the sibling would be
   wrong.** c4-8 gave **every bar** a `role="img"` and an accessible name, and hid the painted
   text. UX-DR18 says the **bar is `aria-hidden`** and *"the legend is the accessible data path"*.
   So the segments get **no names at all**, and the figure's accessible alternative is a **visible**
   legend rather than a hidden table. Whether any visually-hidden block ships here at all is a
   live question — and if one does, it is the **third instance**, which fires c4-8's promotion
   trigger. **Q9.**

5. **The palette cannot separate its own segments, and this is now measured against the shipped
   hexes rather than a superseded review.** Every one of the **21 adjacent `--mana-*` pairs is
   under 3:1**; **10 of 21 are under 1.3:1**; the worst is `--mana-b` against `--mana-colorless` at
   **1.03:1** and the best is `--mana-w` against `--mana-r` at **2.30:1** — slightly *worse* than
   the 2.73:1 the pre-Voltglass `review-accessibility.md` recorded before it was superseded. That
   is the reason UX-DR18 makes the bar `aria-hidden`. But the cheap repair is also measured and
   available: **every segment clears the `--surface-well` track at ≥6.62:1**, so a 1px hairline in
   the track colour separates every pair well above the 3:1 non-text floor. `DESIGN.md:209` gives
   `curve-bar` a `segment-hairline` token for exactly this; **`color-bar`'s frontmatter has none.**
   **Q7.**

6. **Hybrid and Phyrexian pips are live, not theoretical — and nothing says what one contributes.**
   Across the 40 decks: **29 hybrid pip copies and 7 Phyrexian**, in 8 decks, including one
   `{G/W/P}` that is both at once. Does `{W/U}` add one to white and one to blue (total pips >
   symbol count), a half to each, or one **gold** segment? The Python that already answers this
   question for the agent — `compute_pip_signals` — counts **bare pips only**, so `{W/U}`,
   `{2/R}` and `{W/P}` all count for **nobody**. That is a fourth "two surfaces of one product
   answering the same question differently", and it is **Q4**, with **Q16** deciding whether the
   Python moves.

7. **This story gives `AnalysisRow` its second child, and inherits two decisions by name.**
   `AnalysisRow.css:9-14` and `AnalysisRow.tsx:24-30` both say it in shipped source: the
   `flex-wrap` was removed at c4-8's review as unreachable, so **two panels shrink 1:1 at narrow
   widths rather than stacking**, and *"whether c4-9's second panel wants a real stacking
   breakpoint … is that story's decision, flagged to it by name — it owns the first screen with
   two children."* Separately, `App.tsx:250-255` records the land-only empty `.analysis-row` as
   accepted posture and names **c4-9 to revisit it**. **Q11** and **Q10**.

8. **This story is the one c4-8 pinned a deliberately-red test for.** `curve.test.ts:212-236`
   asserts a true split card buckets at the **known-wrong** `[0,0,0,0,0,0,1]`, with the comment
   saying *"c4-9's parser flips it to bucket 4 and goes red"*. If this story writes the numeric
   mana-value parser c4-8 re-homed here by name, **that test must go red and be corrected in the
   same commit**. If it declines, it says so and the pin stays. **Q12.**

Two corrections this story owes to the record, both measured:

9. **`card_faces IS NOT NULL` matches all 38,261 rows.** The column is `NOT NULL`; a non-faced
   card stores the JSON *string* `'null'`. The only correct predicate is
   `json_type(card_faces)='array'` → **3,225**. Any fixture or measurement query using the
   nullable form passes vacuously over the whole corpus — precisely this epic's standing
   coverage-that-reads-as-coverage failure, in the measurement instrument.

10. **c4-8's record states a false reason for a correct ruling.** It says *"all 27 live split-cost
    rows are Adventure/Omen cards"* in one place and *"every one is an Adventure/Omen"* — but the
    sprint ledger and the story's §B both narrate it as **Adventures**. Measured: of the 27 live
    split-cost rows, **8 are Adventures, 18 are Omen, and 1 is neither**
    (`Emeritus of Woe // Demonic Tutor`, a `Creature — Vampire Warlock // Sorcery`). The
    substantive ruling survives — **0 live rows have `cmc` ≠ front-face mana value**, re-verified —
    but **any guard this story writes against `type_line LIKE '%Adventure%'` would mis-handle 19 of
    27 live rows.**

---

## Dev Notes

### The seam that already exists (do not rebuild any of it)

Everything below is **shipped and green at `1ed2e83`**. Read it before writing anything.

#### `src/components/ManaCost/parse.ts` — the pip vocabulary, already total

This is the substrate. **Do not write a second cost scanner.**

```ts
export type ManaColour = 'w' | 'u' | 'b' | 'r' | 'g' | 'c'                    // :36
export const MANA_COLOUR_ORDER: ManaColour[] = ['w','u','b','r','g','c']     // :44  WUBRG, colourless LAST
export interface ManaSymbolToken {                                            // :47-57
  kind: 'symbol'; raw: string
  colours: ManaColour[]      // one or two; EMPTY for generic and {X}
  glyph: string | null       // a generic count, or 'X'
  phyrexian: boolean         // a MODIFIER, never a third colour
}
export interface ManaUnknownToken { kind: 'unknown'; raw: string; glyph: string }   // :60
export interface ManaTextToken    { kind: 'text';    raw: string }                  // :68  — ' // ' arrives here
export const parseManaCost = (cost: string | null | undefined): ManaToken[]         // :164
export const describeManaCost = (tokens: ManaToken[]): string                       // :247
```

Four facts that shape this story:

- **`MANA_COLOUR_ORDER` is exported *because* it is a checkable datum** (`parse.ts:39-43`):
  *"ManaPip canonicalises a hybrid pair against it to pick a class, and the class-coverage guard
  in `ui/tests/token-usage.test.ts` derives all 21 legal colour classes from it. A private copy in
  each of those three places is three ways to disagree."* **A fourth private copy in this story's
  ordering would be the fourth way.** It is six entries — it does **not** contain `gold` (Q8).
- **The tokeniser is total and every character survives** (`ui/README.md:721-739`). A ` // `
  separator comes back as a `text` token, so **the parser already tells you where the face
  boundary is** — Q1 does not need a second string split if it walks tokens.
- **`colours: []` is the generic case**, not an error: `{2}`, `{X}`, `{1000000}`. A pip count that
  filters on `colours.length >= 1` needs no `unknown`-token special case either, because an
  `unknown` token has no `colours` field at all.
- **`{C}` is `colours: ['c']`** — a real colour in this vocabulary, and `--mana-colorless` is a
  real token. **Zero `{C}` symbols appear in any live deck** (§E), so a colourless segment ships
  untested against real data whatever Q4 rules.

#### `src/components/ManaPip/ManaPip.tsx` — the legend's pip, and the prop written for this story

```ts
export interface ManaPipProps {           // :44-63
  colours?: ManaColour[]                  // one or two fills; EMPTY ⇒ colourless
  glyph?: string | null
  label?: string                          // OMITTED ⇒ decorative (aria-hidden). Supplied ⇒ role="img"
}
```

`ManaPip.tsx:35-37`, in shipped source, naming this story:

> **c4-9's legend, which puts a pip beside its own text count, is the case the optional `label`
> exists for** — and it is opt-**IN** because the flooding UX-DR45 warns about is the default
> failure.

`ManaPip.test.tsx:78` is already a passing witness:
`it('becomes a named role="img" when a label is supplied — c4-9's legend case', …)`.

⚠️ **A labelled pip *beside* its own text count double-announces.** The legend entry already reads
its colour, its count and its percentage as text. Q9 must rule whether the pip takes a `label` at
all — the prop exists for this story, which is not the same as this story having to use it.

`ManaPip.css` declares **21 classes** (six colours plus all fifteen unordered pairs), each naming
`var(--mana-*)` directly. It is today the **only** entry in `MANA_DATA_INK`.

#### `src/containers/DeckList/frontFaceCost.ts` — the three shapes, already solved

`frontFaceCost(summary, entry)` resolves a front-face cost through four branches in a
load-bearing order: **split first** (an Adventure's cost is non-blank, so "non-blank means use it
verbatim" placed first would render both halves), then a real top-level cost, then
`entry.card.card_faces[0].mana_cost` when `status === 'hydrated'`, then `null`.

Its header carries the measurement this story inherits (`:98-100`):

> Of the 3,225 cards carrying `card_faces`, **2,830 (87.8%) have a BLANK top-level `mana_cost`**
> whose real value lives only in `card_faces[0].mana_cost` — which `CardSummary` does not carry.

**Reusing it is Q2's proposal and the cross-container import is the wrinkle**: it lives under
`src/containers/DeckList/`, and a second container importing from a sibling container's directory
has no precedent in this repo. Promoting it is an option; so is calling it where it sits. Rule it
in the open, because a silent cross-tree import is the shape `shell.test.ts`'s exhaustive import
lists exist to make visible.

#### `src/state/cards.ts` — and why the obvious read does not work here

```ts
export const useCardEntry  = (cardId: string): CardEntry | undefined =>      // :578
  useCardStore((state) => state.cards[cardId])
export const readCardEntry = (cardId: string): CardEntry | undefined =>      // :603
  useCardStore.getState().cards[cardId]
```

`DeckList.tsx:193-196` calls `useCardEntry` inside **`DeckRow`**, one component per row — a single
unconditional hook each. This panel has no per-row component. See Q3; do not discover this at
implementation time by writing a loop.

#### `src/containers/ManaCurve/curve.ts` — reuse `isLand`, and read the pin

```ts
export const isLand = (typeLine: string): boolean =>                          // :122-123
  frontFace(typeLine).split('—')[0].split(/\s+/).includes('Land')
```

Whole-**word**, on the **front face**, after stripping at the em-dash — c4-8's Q4 deviated onto
this shape on a measurement, because the substring form its own story proposed calls `Lander
Rizzi` and the `Lander` token lands. There are now **three** land policies in the repo
(`curve.ts:74-123` documents all three); this is the third and it is the one a colour panel should
reuse if it excludes lands at all (Q4b).

`curve.ts:36-40` re-homes this story's parser by name:

> the fix is a numeric mana-value parser; `ui/` has none … **Re-homed to c4-9**, which must parse
> costs anyway.

And `curve.test.ts:212-236` is the red-in-waiting: `it('IS KNOWINGLY WRONG for a true split card,
and this pins the wrongness (Q2)')`, asserting `[0,0,0,0,0,0,1]`. **Q12 decides whether this diff
turns it red.**

#### `src/components/AnalysisRow/` — the row that has been waiting for this panel

```css
.analysis-row     { display: flex; gap: var(--space-panel-gap); }   /* AnalysisRow.css:15-18 */
.analysis-row > * { flex: 1 1 0; min-width: 0; }                    /* :40-42 */
```

One child fills the width; **two are exactly 1:1**. `AnalysisRow.tsx:22`: *"nothing for c4-9 to
change: that story lands by adding a sibling."* So the mount is one line in `App.tsx:256-263`:

```tsx
<AnalysisRow>
  <ManaCurve boards={surface.boards} />
  {/* c4-9's panel joins here — and nothing else in this file moves */}
</AnalysisRow>
```

⚠️ **`App.test.tsx:556` currently pins `expect(analysisRow!.children).toHaveLength(1)`.** This is
the story that makes it 2. `App.test.tsx:581` pins the land-only empty row.

#### `src/components/Panel/Panel.tsx`

`title?: string` (rendered as `<h2 className="panel-title">` **and** the `<section>`'s
`aria-label`), `count?`, `badges?`, `level?`, `children`. **No `className` prop; a consumer may not
restyle it.** `Panel.css` is `overflow: hidden` with `var(--space-3)` (12px) body padding.

#### `src/containers/ManaCurve/ManaCurve.tsx` — the shape to match, and the two places not to

Match: `boards` as the only prop; the derivation in a pure sibling module called **in render with
no `useMemo`**; `copy.ts` with zero imports; a **named** `<figure>`; the panel's single branch
(`if (curve.total === 0) return null`).

Do **not** match: the per-element `role="img"` naming (§4 above — UX-DR18 inverts it), and the
visually-hidden `<table>` (this panel's alternative is the visible legend).

---

### What the real data says (measured at `1ed2e83`, read-only, against the shipped database)

DB: `%LOCALAPPDATA%\artificial-planeswalker\cards.db` (`src/paths.py:48`). **38,261 cards, 40
decks, 2,027 `deck_cards` rows.** Two decks share the name `Graveyard Gravy`, so every count below
is keyed on **deck id**, not name — a distinction c4-8's tables did not make and which changes
nothing here but would have.

#### A. The headline — whole-string versus front-face pip counting

Counted quantity-weighted over every deck row, hybrid symbols crediting **both** their colours
(Q4's most generous reading, chosen so the comparison isolates Q1):

| policy | total live pips |
|---|---:|
| whole `mana_cost` string (both halves of a `//`) | **2,608** |
| front face only | **2,547** |
| front face, after hydration fills the blanks | **2,595** |

| measurement | result |
|---|---:|
| decks whose pip total changes between the two policies | **10 of 40** |
| decks whose segment **order** changes | **2** — `Prismatic Dragon`, `Temur Dragonstorm` |
| worst single deck | `Prismatic Dragon` **71 → 45**, a **37%** loss |
| second | `Abzan Dragons` **71 → 57** (20%); black falls from 37% of the bar to 30% |
| third | `Temur Dragonstorm v2` **48 → 41** (15%) |

`Prismatic Dragon`, in full — this is the picture Q1 chooses between:

| policy | W | U | B | R | G | total | reading |
|---|--:|--:|--:|--:|--:|--:|---|
| whole string | 8 | 17 | **20** | 11 | 15 | 71 | B > U > G > R > W |
| front face | 6 | **12** | 10 | 7 | 10 | 45 | U > G ≈ B > R > W |

The cause is the **TDM Omen dragon cycle** — `Sagu Wildling // Roost Seek`, `Bloomvine Regent //
Claim Territory`, `Marang River Regent // Coil and Catch` and nine more — whose back halves are
full spells with their own coloured costs. This is not an exotic corner: it is a current-Standard
mechanic sitting in four live decks.

#### B. The split-card population, and the correction c4-8's record owes

338 corpus cards carry `//` in `mana_cost`. Classified by whether `cmc` equals the front half's
mana value or the sum of both:

| | `cmc` = front | `cmc` = SUM |
|---|---:|---:|
| `type_line` contains `Adventure` | **135** | 0 |
| it does not | **66** (Omen, plus a handful) | **137** |

So **`Adventure` is not the discriminator.** Live: **27 rows / 53 copies** carry a split cost —
**8 Adventure, 18 Omen, 1 neither** (`Emeritus of Woe // Demonic Tutor`, `'{3}{B} // {1}{B}'`,
`cmc 4`). c4-8's ruling survives intact — re-verified, **0 live rows have `cmc` ≠ front-face mana
value** — but its stated reason does not, and a guard keyed on `Adventure` would miss 19 of 27.

#### C. Hydration — what it is worth, and to whom

| measurement | result |
|---|---:|
| faced cards with a blank top-level `mana_cost` | **2,830** (87.75% of 3,225) |
| …of those, some face carries a cost (recoverable) | **487** |
| …no face cost but a non-empty `color_identity` | 49 |
| …**unpippable by any route** (2,284 art-series `Card // Card` + 10 tokens) | **2,294** |
| **live** deck rows that are faced with a blank top-level cost | **38 rows / 46 copies** |
| …of which the front face **does** carry a cost | **34 copies** |
| …of which it does not | **12 copies — every one a Pathway MDFC land** |
| pips hydration adds, live | **+48** (B 23, G 10, U 6, R 5, W 4) across **16 of 40 decks** |

The 12 unrecoverable copies are `Branchloft // Boulderloft` and its five Pathway siblings, which
are lands and correctly contribute nothing — so **on live data, hydration is complete**: after the
sweep there is no card in any real deck whose pips are unknown.

The sharpest single row is `Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel`: the **only**
blank-cost card in a 20-card deck, and the deck's namesake commander. Unhydrated the bar reads
24 B; hydrated, 25 B. Visually invisible — and the AC "the commander contributes its pips" is
either true or false, with no third state.

#### D. Per-deck shape — what the bar actually has to draw

| measurement | result |
|---|---:|
| decks with **zero** pips (an empty bar) | **0 of 40** |
| smallest bar in the corpus | **2 pips**, `Iron Man, Modern Marvel — reminder` (a **one-card** deck) |
| second smallest | **6 pips**, `Graveyard Gravy` (3 cards) |
| **mono-colour decks** (one segment, 100%) | **9 of 40** (22.5%) |
| five-colour decks | `Infinite Guideline Station` / `v2`, `Aanging Loose`, `Prismatic Dragon` |
| largest bar | **114 pips**, `Ayara Black Devotion` — all black |
| decks with **no lands at all** | 1 — `Sephiroth … Standard Brawl` |

**A one-segment bar at 100% is the second most common shape in the corpus.** The epic's
*"colourless or single-colour deck … renders correctly rather than dividing by zero or showing an
empty bar"* AC is therefore **not** an edge case for single-colour (9 real decks exercise it) and
**is entirely synthetic for zero-pip** (no real deck produces it) — which is exactly the fixture
shape that produced c4-8's High. Assert the zero case against the **derivation**, not a
hand-built deck.

#### E. The symbol census — what the pip counter must survive

61 distinct symbol tokens corpus-wide. Every one parses; stripping all `{…}` leaves a residue in
exactly **338** cards and in every one of them the residue is the literal `//`. So the grammar is
closed: `{…}` tokens plus a `//` rule.

| class | corpus occurrences | **live copies** | tokens |
|---|---:|---:|---|
| coloured pip | 41,799 | 2,544 | `W U B R G` |
| generic | 27,648 | — | `{0}`…`{16}`, `{1000000}` |
| **hybrid colour/colour** | 982 | **29** | `{W/U}` `{B/G}` … (10 pairs) |
| `{X}` | 612 | 37 | |
| monocolour hybrid `{2/C}` | 62 | **0** | `{2/W}` … |
| colourless `{C}` | 46 | **0** | |
| **Phyrexian** | 43 | **7** | `{W/P}` … |
| hybrid Phyrexian | 4 | **1** — `{G/W/P}` | |
| snow `{S}` | 3 | **0** | |
| un-modelled singletons | 6 | 0 | `{C/P}`, `{D}`, `{L}` |
| X-like / half | 3 | 0 | `{Y}` `{Z}` `{HW}` |

Live hybrid and Phyrexian sit in **8 decks** — `Astonishing Ant-Man` (10 hybrid copies),
`Atraxa Counter Cabinet` (3 Phyrexian), `Aanging Loose`, both `Dragon-God Superfriends`, both
`Infinite Guideline Station`, `Ezuri Proliferate Poison`. **Q4 is a live question, not a
hypothetical one**, and `{G/W/P}` — hybrid *and* Phyrexian in one symbol — is in a real deck.

`{C}` and `{S}` are **zero live**. Whatever Q4 rules about a colourless segment ships untested
against real data and must say so.

#### F. `colors` versus `mana_cost` — why UX-DR18 said "pip count"

| measurement | count | of 3,225 faced |
|---|---:|---:|
| faced cards with an **empty** top-level `colors` | **2,842** | **88.12%** |
| …whose `card_faces[0]` carries `colors` | 495 | — |
| faced cards with an empty `color_identity` | 2,319 | 71.9% |

`colors` is stored as a JSON array of single letters, alphabetically sorted; there is no NULL and
no empty-string variant, only `'[]'` (8,232 corpus rows). **`color_identity` is not a substitute**:
it is a *set*, so `Ayara Black Devotion`'s 114 black pips collapse to a single `B`, and it is empty
for 71.9% of the faced population anyway. c4-8 declined to stack its curve on precisely this
measurement; **UX-DR18's "pip count" is the reading that does not depend on either field**, and
that is the quiet reason this panel is specified the way it is.

#### G. The palette cannot separate its own segments — measured against the shipped hexes

WCAG 2.x contrast over `tokens.css:127-133`. The only prior measurement lives in
`review-accessibility.md`, which carries a **"⚠ SUPERSEDED — do not action"** banner and predates
the Voltglass palette.

| measurement | result |
|---|---:|
| adjacent `--mana-*` pairs under the **3:1** non-text floor | **21 of 21** |
| pairs under 1.3:1 | **10 of 21** |
| worst pair | `--mana-b` vs `--mana-colorless` — **1.03:1** |
| best pair | `--mana-w` vs `--mana-r` — **2.30:1** (the superseded doc said 2.73:1) |
| **every segment vs the `--surface-well` track** | **6.62:1 – 15.20:1, all PASS** |

Read the last row twice: a **1px `--surface-well` hairline** between segments separates every
adjacent pair at **≥6.62:1**, turning 21 failures into 21 passes with one declaration and no new
token. `DESIGN.md:209` already gives `curve-bar` a `segment-hairline: '1px {colors.surface-well}'`
for exactly this; c4-8 shipped without needing it (`ManaCurve.css` records *"`segment-hairline` is
unused — Q8 declines stacking"*). **`color-bar`'s frontmatter (`DESIGN.md:210-213`) has no such
key**, so if the hairline ships here it is either an artefact amendment or a cited derivation.
**Q7.**

⚠️ This does **not** make the bar accessible on its own — `deferred-work.md:1447-1471` is open at
**Medium** on exactly the distinction: *"this measures **distinguishability** (telling two pips
apart) rather than **identifiability** (knowing WHICH colour a pip is)"*. The legend is UX-DR18's
answer to identifiability and the hairline is an answer to distinguishability. They are different
problems and the story should not claim one closes the other.

#### H. The fourth policy — `compute_pip_signals`, already shipped in Python

`src/logic/assessment/mana_base.py:343-390` computes per-colour pip counts for the power
assessment. Its policy:

```python
_MANA_SYMBOL_RE = re.compile(r"\{([^}]+)\}")                    # :230
symbols = _MANA_SYMBOL_RE.findall(_pip_cost(card))              # :370
pips = sum(1 for symbol in symbols if symbol == color)          # :372  — BARE pips only
```

- **Bare pips only.** `{W/U}`, `{2/R}` and `{W/P}` match no colour and count for nobody.
- **Lands excluded**, by the whole-string `'land' in type_line.lower()` test (`:80`) — policy A,
  the one c4-8 declined to fix.
- **Front-face fallback already implemented**: `_pip_cost` (`:305-317`) returns
  `card_faces[0].mana_cost` when the top level is blank — the Python has *no* hydration problem
  because it reads the database directly.
- **Sideboard included** by default (`:349-350`: *"Sideboard rows are included — filter first if
  unwanted"*).

So the agent and the glass will answer *"how much black is this deck"* differently unless this
story rules on it. **Q16 decides whether Python moves; the default, as at c4-8, is no** —
`compute_pip_signals` feeds `assess_deck_power`'s frozen benchmark set.

#### I. There is no colour endpoint, and there is no refetch

`src/companion/app/routes/` holds `active_deck.py`, `cards.py`, `decks.py`, `health.py`. **No
colour endpoint exists and this story adds none.** UX-DR18's derivation is a frontend read of data
already in the store plus the hydration cache. And per `deferred-work.md:3528-3531` there is still
**no re-drive after boot** until Epic 5's `deck_changed` — so *"recomputes on deck change"*
(`epics:3028`) has, today, exactly one trigger: the boot.

---

### The wire types — what this story may and may not read

```ts
// ui/src/api/types.d.ts — read through src/api/schema.ts's aliases, import type ONLY
DeckCardSummary { card_id: string; quantity: number; sideboard: boolean;
                  commander: boolean; card: CardSummary }
CardSummary     { id; name; mana_cost: string; cmc: number; type_line: string;
                  oracle_text: string; colors: string[]; rarity; set_code }
// CardEntry (src/state/cards.ts:122) — the discriminated union; `card_faces` exists
// ONLY on status === 'hydrated'.
```

- **`mana_cost: string` is non-optional and never NULL** (c3-2 measured it; 5,943 lands carry
  `''`). No `?? ''`. `parseManaCost` accepts `string | null | undefined` for callers the wire does
  not constrain, which is not licence to widen the type at the call site.
- **`colors: string[]` is non-optional too** — and §F is why this story does not read it.
- **Never re-declare a wire shape outside `src/api/`** (`wire-contract.test.ts:145`).
- **Every `src/api/` import from a container is `import type`**; the inline-`type` form is refused
  because `verbatimModuleSyntax` still runs the module (c4-5 decision 2).

---

### Decide-once rulings this story inherits (do not re-derive)

1. **`src/containers/` is where a component that BEHAVES lives** (c4-4 Q1); `src/components/` is a
   closed set-equality category banned from hooks, `on*`, `ref`, spread and a value `react`
   import. A panel that reads the store is a **container**.
2. **Container posture** (`ui/README.md:565-569`): MAY hold state, call hooks, attach handlers,
   read the store through `src/state/`, compose primitives. MAY NOT reach the network, import a
   state library directly, write another module's slice, or declare a design token.
3. **Directory-per-component, no barrels, named exports only.** `react-refresh/only-export-components`
   is an ESLint **error**, so every pure helper is its own module and its own `CONTAINERS` entry
   (`imageUrl.ts`, `deckMemory.ts`, `imagedFaces.ts`, `useCardArt.ts`, `frontFaceCost.ts`,
   `curve.ts` are the six precedents).
4. **`AppShell.tsx` is never edited; placeholders are displaced, not deleted** (c2-9) — this is the
   **eighth** application.
5. **Class names are flat kebab-case prefixed with the component** (`colour-bar-segment`, never
   `colour-bar__segment`); stylelint `selector-class-pattern` is an error.
6. **Every colour, shadow, radius, spacing, duration and type value goes through a token.** No
   inline `style={{…}}` except through a **named** declared runtime channel (ruling 22 below).
7. **`box-shadow` allowed-list**: `none`, or a comma-list of `var(--shadow-*)`/`var(--glow)`.
8. **`px` literals in `src/components/` and `src/containers/` need a `DESIGN.md:NNN` citation
   within 60 characters, in the same block comment** (`shell.test.ts:1002-1032`). ⚠️ **Unlike
   c4-8, this story HAS a citable line**: `DESIGN.md:212` gives `color-bar.height: 14px`. And
   **14px is not on the 4/8/12/16/24/32/48 spacing scale**, so it cannot be composed from tokens
   the way c4-8's 72px track was — the citation is the mechanism. The 2026-07-25 validation report
   (`:75`) already flags `color-bar.height` as over-tokenised in DESIGN.md, so **do not add token
   #70 for it.**
9. **Bare `1fr` and `minmax(auto, 1fr)` grid tracks are banned** (`shell.test.ts:960`); grid items
   need `min-width: 0`.
10. **`:focus-visible`, never `:focus`; `outline: none` banned in all four spellings.** Not
    expected to bite — the bar and legend are display-only.
11. **`--accent-dim` on `--surface-overlay` is banned (2.70:1)**; the guard is same-block only.
12. **Nothing pulses, loops or alternates at any setting**; `animation-iteration-count` may only
    be `1`.
13. **`Panel` is a primitive a consumer may not restyle.**
14. **`.app-shell-columns` is the app's single scroll container.**
15. **Any authored user-facing string lives in a `copy.ts` beside its component**, registered in
    `COPY_MODULES` with a **>40-character** reason. **Card data is not copy.** The attribute half
    collects *every* literal reaching nine read-aloud attributes **whatever its shape**;
    `copy-rules.test.ts:62` calls out `aria-label={describe(x)}` explicitly. ⚠️ A percentage is
    data; the `%` sign and the word in `"12 pips"` are authored.
16. **Emptiness is `filled()` / `typeof` + `trim()`, never truthiness; a number is
    `Number.isFinite`, never `count && …`.**
17. **Props are a discriminated union where the variants are closed**, coupled to their source type
    in both directions by type-level asserts.
18. **`fireEvent` is the suite's only DOM-event idiom** (c4-5 Q9). Not expected to bite.
19. **`npx tsc -b --force`, never `tsc -b`.**
20. **Guards are proven through the full `npm test`, never a standalone file run** — the
    standalone `token-usage.test.ts` runner crash is ledgered (`deferred-work.md:3639-3649`) and
    has made a probe harness lie once already.
21. **The `:where()` cascade repair** (c4-6 Q2) is the sanctioned idiom for adding a wrapper
    without disturbing specificity.
22. **The `--mana-*` allowlists** (`token-usage.test.ts`): a **file** allowlist (`MANA_DATA_INK`,
    `:682`, today `ManaPip.css` alone), a **property** allowlist (`background`,
    `background-color`, `background-image`, `fill`, `stop-color` — nothing else, `:691`), and a
    **markup** half that allows **none** anywhere outside CSS (`:709-730`). **Joining is how a
    story declares itself data ink, and this story is the first that must.**
23. **A runtime custom property is a NAMED channel in two places.** `eslint.config.js:208-217`
    matches the **exact string** `--curve-bar-height`, not `/^--/` — because a `--`-prefixed key
    can inline-override a real design token for every descendant. `RUNTIME_CUSTOM_PROPERTIES`
    (`token-usage.test.ts:584`) is the congruent allowlist, scoped to the one consuming file.
    Brad's ruling 2026-08-06: **a story adding a channel adds it in both places, in the open, or
    one of the two gates goes red.**
24. **`role="img"` + `aria-label` on the wrapper, coloured parts inside decorative** (c2-8 Q4,
    ratified at c4-8's review) — *"an `aria-label` on a bare `<span>` is name-prohibited on
    `role="generic"`, and screen readers are permitted to ignore it"*. ⚠️ **UX-DR18 inverts where
    this applies**: the bar is `aria-hidden`, so the wrapper being named here is the **legend**, if
    anything is (Q9).

---

### Latest technical specifics

- **React 19.2 / TypeScript 5.9 / zustand 5 / Vite 7 / Vitest 3** — unchanged; this story adds no
  dependency, and in particular **no charting library**: a flex row of divs with percentage widths
  is the whole visual.
- **React's `CSSProperties` has no `--`-prefixed index signature.** c4-8 measured it with
  `npx tsc -b --force`: a custom-property key in a style literal is `TS2353`, and `as CSSProperties`
  at the one call site is the price. If Q13 needs a runtime channel, budget the cast.
- **zustand v5 has no equality argument on `create`.** A selector returning a **new** object or
  array each call re-renders forever. `useCardStore((s) => s.cards)` returns the **stored map
  reference** and is safe; `useCardStore((s) => Object.values(s.cards))` is not. Q3 turns on this.
- **Two vitest projects**: `src/**/*.test.{ts,tsx}` → jsdom (`dom`); `ui/tests/**/*.test.ts` →
  node. `gate-geometry.test.ts:53` forbids `.tsx` under `tests/`. A pure derivation test with no
  JSX is a **`.ts`** — c4-8's review renamed `curve.test.tsx` for exactly this and rejected an
  incoherent stated reason for the deviation.
- **jsdom has no layout**: `getBoundingClientRect()` is zeroes and a percentage width is not
  resolved. **Every segment-width assertion in jsdom is an assertion about the style attribute or
  the class, never a rendered pixel.** The rendered geometry is the eye-check's job.
- **`aria-query` maps `<header>` to `banner` unconditionally**, so every titled `Panel` is a
  phantom `banner` in jsdom and none in a browser. c4-8 measured **jsdom 4 / Chrome 1**; **this
  panel takes jsdom to 5.** Scope role queries through the `h1`, never `getByRole('banner')`.
- **`<figure>` maps to role `figure` reliably only when it has an accessible name** — verify
  against Chrome's own accessibility tree, not jsdom's.
- **Windows line endings**: `pathlib.write_text` translates LF→CRLF; `ui/.gitattributes` forces
  LF, so `format:check` goes red across files a probe merely *restored*. Restore with
  byte-preserving writes.
- **A vitest worker crash** (`Error: Worker exited unexpectedly` with **zero** failing assertions)
  is a known flake. Re-run before investigating.
- **The registry guards walk `git ls-files`**, so **an un-`git add`ed module is invisible and
  passes vacuously**. c4-7 demonstrated it live at 1,274/1,274 green with no `CONTAINERS` entry
  written. `git add` before believing a green run — and check the **bundle assets** are tracked
  before committing: untracked bundle assets have been a **High** finding in two of the last six
  stories (c4-3, c4-7).

---

### The nineteen things this story must not break

1. **`AppShell.tsx` — not edited.** `AppShell.test.tsx:116`'s `'c4-9'` placeholder assertion must
   pass **against the component's own props**, unchanged. This is the eighth application of the
   c2-9 displacement ruling.
2. **`App.test.tsx:507`'s `not.toContain('c4-9')`** — already green because c4-8 displaced the
   left placeholder; this story makes it green **by its own panel**. Record the F1 count.
3. **`AnalysisRow`'s 1:1 contract** — `flex: 1 1 0; min-width: 0`, no `flex-wrap`, no `px`. If Q11
   adds a breakpoint it is a **derived and cited** flex-basis, not a re-instated dead `wrap`.
4. **`ManaCurve` renders exactly as it does today** — same buckets, same names, same heights. A
   second child in the row must not change the first, and the eye-check measures both.
5. **The `boards` reference identity is the deck's identity** — `deckMemory.ts` and `CardDetail`'s
   effect depend on it. **No derived copy of `boards`, and no re-derivation after hydration** —
   that is the exact mechanism c4-7's Q10 declined the `'Card // Card'` fix over.
6. **`deckGroups.ts`'s `frontFace` and `groupOf` are read, never reshaped**, and `curve.ts`'s
   `isLand` likewise.
7. **`parseManaCost` is reused, never forked.** A second cost scanner in `ui/` is the failure
   `ui/README.md:721-739` was written to prevent, and `MANA_COLOUR_ORDER` is not copied.
8. **The inspection slice is not touched.** The bar and legend are **display-only**: no
   `setHovered`, no `togglePin`, no `useIsLiveTarget`, no click handler, no `tabindex`.
9. **`CardDetail` is not a live region's second instance** — this panel adds **no** `aria-live`.
   A percentage that announced on every hydration would be the flood UX-DR45 exists to prevent,
   and this panel's numbers *do* move during the sweep (§C).
10. **`useCardEntry`'s "starts nothing" contract and `hydrateCard`'s caps** — this panel **reads**
    the cache and must not trigger a fetch. `hydrateDeckCards` stays `App.tsx`'s alone.
11. **`Panel` is a primitive a consumer may not restyle** — `overflow: hidden`, 12px body padding.
12. **The one network door stays `['src/api/client.ts']`** (`posture.test.ts:339`). The scan is
    keyed on the **identifier**, so even the bare word `fetch` in stripped code fails.
13. **`store-writes.test.ts`'s `STORES` table (`:77`)** — five entries; **no component calls
    `setState`.** This story adds no slice.
14. **`wire-contract.test.ts`** — no wire shape re-declared outside `src/api/`.
15. **The token inventory and its two pins** (`tokens.test.ts:321`, `token-usage.test.ts:1142`) —
    **69 today**; both move together or the pair is wrong, and the story says why. `color-bar`'s
    three frontmatter values resolve to `--surface-well`, a `14px` literal and `--radius-pill`, so
    **69 is expected to hold** (ruling 8).
16. **`CARD_SHAPED`'s four entries (`token-usage.test.ts:868`) and both directions.** This panel
    draws no card: its stylesheet must **not** join, and `--radius-card` must appear nowhere in it.
17. **`MANA_DATA_INK`'s markup half** — segments take a **class**, never a `fill=` attribute,
    never an inline `var(--mana-…)`, and never a token name built at runtime.
18. **The reduced-motion inventory (`tokens.css:285-317`) and the enumerated shipped-motion pin**
    (`token-usage.test.ts`, now **4**) — extended, never bypassed. ⚠️ **UX-DR42's inventory has no
    row for a colour bar**; if one animates, the row is added here **and** UX-DR42 is amended.
19. **Python is untouched.** `uv run pytest` stays at **2,501 passed / 1 skipped**. ⚠️ Q16 is
    explicitly the question of whether to break this one, and the default answer is no.

---

### Source tree — what exists, what this story touches

```
ui/src/
  containers/
    ColourDistribution/           NEW   the panel, the figure, the bar, the legend
      ColourDistribution.tsx      NEW   container: reads boards + the card cache, composes Panel
      ColourDistribution.css      NEW   the track, the segments, the legend grid — MANA_DATA_INK
      ColourDistribution.test.tsx NEW   jsdom project
      colours.ts                  NEW   the pure derivation — pip counting, ordering, percentages
      colours.test.ts             NEW   pure tests, co-located, `.ts` (no JSX)
      copy.ts                     NEW   panel title, figure name, legend labels, the "%" and "pips"
    ManaCurve/…                   READ  the sibling shape; curve.ts's isLand is reused
                                  EDIT? curve.test.ts's split-card pin, IF Q12 takes the parser
    DeckList/frontFaceCost.ts     READ  or MOVE — Q2/Q3 decide whether it is reused in place
  components/
    ManaPip/…                     READ  the legend's pip; the `label` prop written for this story
    ManaCost/parse.ts             READ  parseManaCost, MANA_COLOUR_ORDER — never forked
    AnalysisRow/…                 EDIT? only if Q11 adds a stacking breakpoint
    Panel/…                       READ  level="default"
  state/
    deckGroups.ts                 READ  frontFace, DeckBoards
    cards.ts                      READ  the cache; Q3 decides which reader
  styles/tokens.css               EDIT? only if Q14 registers a motion; no token expected (69 holds)
  App.tsx                         EDIT  one sibling inside <AnalysisRow>; Q10 may gate the row
  App.test.tsx                    EDIT  children 1 → 2, order, absence behind every state panel
  eslint.config.js                EDIT? only if Q13 needs a second named runtime channel
ui/tests/
  shell.test.ts                   EDIT  CONTAINERS (:1515) + the pin at :1795 (16 → N)
  copy-rules.test.ts              EDIT  COPY_MODULES (:107) + a >40-char reason (10 → 11)
  token-usage.test.ts             EDIT  MANA_DATA_INK (:682) — THE FIRST JOINER; RUNTIME_CUSTOM_
                                        PROPERTIES (:584) if Q13; the 6 → 7 spent-token count if Q8
  tokens.test.ts                  EDIT? only if a token moves — it should not
  lint-gates.test.ts              EDIT? only if Q13 amends the ESLint hatch
_bmad-output/implementation-artifacts/
  deferred-work.md                EDIT  this story's dispositions — IN THIS COMMIT (AC 41)
src/companion/app/static/         BUILD committed bundle, must change (JS and CSS)
plugin/server/src/companion/app/static/   BUILD ⚠️ hand-copied mirror, checked by NOTHING
```

**⚠️ Two unguarded gaps, both demonstrated live in earlier stories.** (a) The plugin mirror is
enforced by no test, no workflow and no script — c4-7 raised it with **the C4 retro** as its named
home; update it by hand and verify sha256 per file. (b) The registry guards cannot see an
untracked file.

**⚠️ A third, and this story is its named home.** `deferred-work.md:3869-3877` records that the
registry guards' blindness to untracked modules is deferred to *"the guard suite, first story that
touches any registry test"*. **This story touches three.** Q15 does not cover it; give it a
disposition.

**Baselines to measure against** (verified on disk at `1ed2e83`):

| baseline | value |
|---|---|
| frontend tests | **1,408 passed / 55 files** |
| Python tests | **2,501 passed / 1 skipped** |
| tokens | **69** (`tokens.test.ts:321`, `token-usage.test.ts:1142`) |
| containers | **16** (`shell.test.ts:1795`) |
| primitives | **18** (`shell.test.ts:1326`) |
| stores | **5** (`store-writes.test.ts:77`) |
| copy modules | **10** (`copy-rules.test.ts:107`) |
| `CARD_SHAPED` | **4** (`token-usage.test.ts:868`) |
| `MANA_DATA_INK` | **1** — `ManaPip.css` (`token-usage.test.ts:682`) |
| `RUNTIME_CUSTOM_PROPERTIES` | **1** — `--curve-bar-height` (`token-usage.test.ts:584`) |
| shipped-motion pin | **4** |
| `--mana-*` spent-token count | **6 of 7** (`--mana-gold` unconsumed) |
| bundle JS | `index-CQ4JkkIp.js` **220,130 B** |
| bundle CSS | `index-BE0Fvpcl.css` **18,138 B** |
| font | `space-grotesk-latin-wght-normal-BhU9QXUp.woff2` 22,288 B |
| jsdom phantom `banner` count | **4** (Chrome: 1) |
| curve panel height | **168 px**; `.analysis-row` width **870 px**, one child |

**Both bundle assets must change.** c4-5's phrasing applies — *"a byte-identical JS bundle here
means it did not ship"* — and c4-6/c4-8's precedent is that a byte count can be unchanged while
the hash changes: **report both**.

---

### The inherited deferrals — give each a disposition (AC 40)

C2 retro **ruling R2**: inherited deferrals are ACs at context time, and *"not mentioned" is a
failure of the AC*. There are **nine**.

1. **`ManaPip`/`ManaCost` appearance** (`deferred-work.md:1400-1419`) — the five visual claims were
   **RESOLVED at c4-3**, and that entry explicitly says *"c4-7 and c4-9 inherit nothing from this
   entry; what remains for them is **composition**, which a harness cannot show."* **This story is
   the last of the three homes** and the first caller of the `label` prop. The disposition is a
   composition verdict from the eye-check, not a re-run of the five claims.
2. **CVD — "colour is the sole carrier"** (`deferred-work.md:1447-1471`, **Medium, still OPEN**,
   awaiting Brad's acceptance). This is the most on-point deferral this epic has: a segmented
   colour bar is a graphic whose only channel is hue. §G is a new measurement against it. State
   whether the legend closes *identifiability* and the hairline (if any) closes
   *distinguishability*, and do not claim one closes the other.
3. **The two Python land policies disagree with FR-05/UX-DR17** (`deferred-work.md:3536-3572`) —
   **DECLINED and re-homed at c4-8**, with the divergence upgraded to observable. Q16 is the same
   question one axis over (pips, not lands); say whether this story re-opens it. Default: no.
4. **The `'Card // Card'` grouping fix** (`deferred-work.md:3515-3520`) — DECLINED at c4-7 on the
   mechanism, not the data: re-deriving `boards` after hydration fires a spurious deck-transition
   clear. ⚠️ **This story reads hydration results and must not re-derive `boards`** — the same
   mechanism, one story later. Note that all 2,284 of those rows are also §C's "unpippable by any
   route" population.
5. **F1: story-key-shaped strings on the rendered view** (`deferred-work.md:3456-3464`, `:3765`) —
   c4-8 recorded `c4-8` and `c4-9` both asserted absent, leaving `c4-10` and `c4-11`. Record the
   new count; the gate itself stays **c8-5's**.
6. **Panel-stacking vertical budget** (`c4-5:1052-1058`, advisory) — c4-7 measured 3,198 px, c4-8
   measured **+168 px**. ⚠️ This story adds height to the **same row**, not beneath it: if the
   legend is taller than the curve, the row grows and **both** panels grow with it. Measure the
   row's height before and after.
7. **The 21em oracle scroller is keyboard-unreachable** (`deferred-work.md:3806-3814`, **c4-11's**)
   — expected not-triggered, but say *why*: this panel has no scroller and adds zero Tab stops.
8. **`DeckRepository.list_decks` ties on `created_at`** (`deferred-work.md:1668-1699`,
   Medium-High) — checked and re-homed unchanged at c4-7 and c4-8. Almost certainly the same here.
9. **The registry guards are blind to untracked modules** (`deferred-work.md:3869-3877`) — homed to
   *"the first story that touches any registry test"*. **This story touches three.** Either take
   it or decline it with a reason; silence is the one thing R2 forbids.

**Triggered "whoever ships the next X" residues** — each also needs a line:

- **The `MANA_DATA_INK` invitation** — `ui/README.md:678-681` names c4-8 and c4-9. c4-8 declined
  with a reason and wrote *"c4-9 remains invited."* **This story cannot decline**: its bar is
  `mana-*` ink by UX-DR18.
- **`--mana-gold`'s first consumer** — `ui/README.md:706-710` predicts c4-9 and says the spent
  token count moves **6 → 7 in the open, not silently**. ⚠️ It predicts a *colour-identity* bar;
  UX-DR18 specifies a *pip count*, and gold is not a cost colour. **Q8 must rule, and if gold does
  not ship, the README's prediction is corrected in this diff.**
- **The visually-hidden idiom's third instance** — c4-8 recorded a **third-instance trigger**:
  whoever writes the third block promotes it to `src/styles/`. Q9 decides whether there is a third.
- **The split-card `cmc` divergence, re-homed here by name** — `curve.ts:39`, `curve.test.ts:219`.
  Q12.
- **The next story that renders an identifier / picks a type role**
  (`deferred-work.md:3626-3637`) — *"nothing checks that the RIGHT type role was chosen"*. This
  story renders **two** numeric values (a count and a percentage). DESIGN.md's colour-distribution
  anatomy does not specify their roles; the composition reference uses `--type-numeric` for the
  count and `--type-micro` for the percentage. Say which ships and on what authority.
- **`StatChip`'s first surface** — ⚠️ **triggered for the first time.** The composition reference's
  colour panel ends with three `StatChip`s: `Sources R 19`, `Sources W 16`, `Deck value {total}`.
  **`Deck value` is a price, and there is no price anywhere in this system** — c4-7 measured it out
  of existence and amended `DESIGN.md:410`/`:412` to say so twice. **"Sources"** appears in no
  UX-DR, no DESIGN.md line and no AC — it exists only in `EXPERIENCE.md:34`'s IA row
  (*"Pip distribution, source counts, deck value"*). Rule explicitly that neither ships, and home
  the `EXPERIENCE.md:34` / `:173` corrections.
- **The cross-file card-shape collision** (`deferred-work.md:3587-3596`) — not expected; say so.
- **The hydration sweep's no-re-drive window** (c4-6 review ruling 1) — ⚠️ **TRIGGERED, and this
  story ends the one-story reprieve c4-8 opened.** §C is the exposure.

---

### Open questions — answer these before writing code

Sixteen. **Q1 changes what a real deck looks like today**; Q2, Q3, Q4 and Q7 change what ships;
Q13 may change a **guard**; Q16 decides whether Python moves; the rest close holes that would
otherwise be found at review.

**Q1 — Whole `mana_cost` string, or the front face only?**
UX-DR18 says *"proportional to pip count across the deck"* and stops. §A: **10 of 40 decks
change**, **2 re-order**, `Prismatic Dragon` loses **37%** of its bar. The cause is live-Standard
Omen cards, not a corner case.
*Proposal:* **front face only**, reusing the `' // '` boundary `parseManaCost` already reports as a
`text` token. Three reasons, in order of weight: (a) it is the same reading every other surface in
the epic already uses — `deckGroups.ts` groups by front face, `curve.ts` buckets by front face,
`frontFaceCost.ts` draws the front face's pips in the deck row, and UX-DR17/FR-05 say "front face"
in writing; a bar that counted both halves would be **the only surface in the app that does not**;
(b) the panel's question is *"does my mana base match my spells"* — you cast the front face, and
the back half of an Omen is a cost you pay separately or never; (c) it is what the deck row
already shows, so the bar and the list agree by construction — the one-layer-out form of the
epic's *"the grid and the list panel cannot disagree"*. **Pin `Prismatic Dragon`'s real shape with
a named test asserting both totals**, so the next reader finds the 71-vs-45 measurement rather
than re-deriving it. And state the cost plainly in the module header: **the back half of an Omen
is invisible on this panel.**

**Q2 — Does the panel depend on hydration, and what does the user see while it lands?**
§C: **+48 pips across 16 of 40 decks**, and on live data hydration is *complete* — after the sweep
no real deck has an unknown pip.
*Proposal:* **yes, depend on it, via `frontFaceCost`'s existing three-shape resolution**, and say
out loud that this panel is the epic's first whose **percentages move after first paint**. The
alternative — counting only what `CardSummary` carries — is not "simpler", it is **wrong for 16 of
40 decks** and wrong in a way nothing on screen would reveal. Two things follow and both must be
written down: (i) **c4-6's no-re-drive window applies** — a backend blip during the sweep leaves
those pips permanently missing with no error state, and this story cites that accepted posture
rather than papering it with a retry it does not own; (ii) **no `aria-live`** — a percentage that
re-announced 99 times during a sweep is the exact flood UX-DR45 bans (don't-break 9).

**Q3 — How does one component read up to 99 cache entries?**
`useCardEntry` is one hook per card and `DeckList` gets away with it only because each row is its
own component. A hook in a loop over `boards` breaks the moment the deck changes length.
*Proposal:* **subscribe to the map once — `useCardStore((state) => state.cards)` — and pass it
into the pure derivation as an argument.** It returns the stored reference, so zustand v5's
no-equality-argument hazard does not arise (a selector building an array or object would re-render
forever). The costs are real and stated: the panel re-renders on **every** hydration during the
sweep — ~99 renders on the 99-card deck — each running a derivation over ~99 rows, so **Q5's
measurement is not optional**. Reject `readCardEntry`: it is not reactive, so the bar would settle
on its pre-hydration numbers and never correct — silently plausible and wrong, the worst of the
three. ⚠️ **A new reader of `cards.ts` from a container needs its `CONTAINERS` import list to say
so**, and `store-writes.test.ts`'s name-presence heuristic means the module must **read** only.

**Q4 — What does a hybrid, Phyrexian or generic-hybrid pip contribute — and is a land a source of
pips?**
§E: **29 hybrid + 7 Phyrexian pip copies live, in 8 decks**, including one `{G/W/P}`. `{C}` and
`{S}` are zero live. Python's `compute_pip_signals` counts **bare pips only**, so all of these
count for nobody there.
*Proposal (a) — hybrid:* **one pip credits every colour it can be paid with**, so `{W/U}` adds one
to white and one to blue. The bar is a *proportional* graphic, not a conservation identity: a
`{W/U}` card genuinely demands white **or** blue sources, and crediting neither (Python's answer)
under-reports a real demand while crediting a half invents a precision the data does not have.
**State that the total therefore exceeds the symbol count**, and that the legend's percentages are
of that total — otherwise a reader adds the counts, gets more than the pip total, and files a bug.
*Proposal (b) — Phyrexian:* `{W/P}` counts as **white**; `phyrexian` is a modifier on the token,
never a third colour (`parse.ts:55`), and life is not a colour.
*Proposal (c) — generic-hybrid:* `{2/R}` counts as **red** only; the generic half is not a colour,
which is exactly what `parse.ts` already encodes by putting `2` in `glyph` and `r` in `colours`.
*Proposal (d) — generic and `{X}`:* **not counted.** `colours: []` is the test, and no
"colourless" segment is invented for them — `{C}` is colourless, `{2}` is nothing.
*Proposal (e) — lands:* **lands are excluded**, reusing `curve.ts`'s `isLand`. UX-DR18 has no land
clause, but the panel's stated question is *"does my mana base match my **spells**"*, and a land
that taps for mana is a *source*, not a demand. In practice this is nearly free — a land's
`mana_cost` is almost always `''` — but "nearly free" is not a reason to leave the policy
unstated, and there are lands with costs. **Pin every one of (a)–(e) with a named test over a real
corpus card**, and name the live deck each is exercised by.

**Q5 — Where does the derivation live, and is it memoised?**
UX-DR18 gives no recompute clause; `epics:3028` says the colour distribution recomputes on deck
change.
*Proposal:* a pure module `src/containers/ColourDistribution/colours.ts` (its own `CONTAINERS`
entry, ruling 3) exporting one total function over `(boards, cards)`, called **in render with no
`useMemo`** — the same shape as `curveOf`. But note the difference honestly: c4-8's derivation ran
once per deck change; **this one runs once per hydration too** (Q3), and it parses ~99 cost strings
rather than reducing ~99 numbers. c4-8's `curveOf` measured **~24 µs** on a 99-row board. **Measure
this one and put the number in the record** — if it is materially worse, a `useMemo` keyed on the
cache map becomes a real question rather than a premature one, and the answer belongs in this
story rather than in a later performance bug.

**Q6 — Which boards?**
Already half-ruled, and the shipped sentence names this panel **by function**
(`deckGroups.ts:197`): *"the sideboard is not part of the deck **the curve and colour panels**
describe"*.
*Proposal:* **commander + mainboard, sideboard excluded** — identical to c4-8's Q5 ruling and to
`deck_analysis.py:171-173`. Note the divergence from `compute_pip_signals`, which includes the
sideboard by default (§H), and carry it into Q16.

**Q7 — Do the segments get a hairline?**
§G: **21 of 21 adjacent pairs under 3:1**, worst **1.03:1**; **every segment clears the track at
≥6.62:1**. `curve-bar` has a `segment-hairline` token; `color-bar` does not.
*Proposal:* **yes — a 1px `--surface-well` separator between segments**, cited to `DESIGN.md:209`
as the pattern and recorded as an amendment DESIGN.md's `color-bar` frontmatter should carry. It
costs one declaration, no token and no new colour; it turns 21 sub-3:1 boundaries into 21
≥6.62:1 boundaries; and the panel already sits on that exact surface, so the hairline reads as the
track showing through rather than as a drawn line. ⚠️ Two things to get right: the outermost edges
must **not** gain a hairline (the pill's ends are the track already), and a hairline is a
meaningful fraction of a narrow segment — at the ~423px half-width the row will have with two
children, a 1-pip segment of a 114-pip deck is under 4px. **Measure the thinnest live segment in
the eye-check** and say whether the hairline eats it. If it does, that is a finding, not a reason
to skip the measurement.

**Q8 — Does `--mana-gold` ship?**
`ui/README.md:706-710` predicts this story as its first consumer and moves the spent count 6 → 7.
But it predicts a **colour-identity** bar, and UX-DR18 specifies a **pip count**.
*Proposal:* **no — gold does not ship, and the README's prediction is corrected in this diff.**
Gold is a card-level property (UX-DR17 uses it for a *multicolour card* contributing one segment
to a stacked curve); a **pip** is never gold — `{W/U}` is a white-or-blue pip and `ManaPip` already
draws it as a two-stop gradient across two real tokens. `MANA_COLOUR_ORDER` excludes gold *for
this reason*, in writing. So the spent-token count stays **6 of 7**, `--mana-gold` remains
consumerless, and the story says where its first consumer actually is (a stacked curve, or a
colour-identity dot — neither of which is in Phase 1). **Assert the absence**, c4-5's AC-14
pattern: `--mana-gold` appears nowhere in this story's CSS, and a test says so.

**Q9 — The accessible shape: what is named, what is hidden, and is there a hidden block at all?**
UX-DR18 and the epic AC are unambiguous — **the bar is `aria-hidden`, the legend is the accessible
data path**, and the panel is a `figure` whose accessible alternative **is that legend**. This is
the inverse of c4-8, where every bar carried a name.
*Proposal:* (i) the `<figure>` carries an `aria-label` from `copy.ts`, **distinct from the panel
title** — c4-8's reason applies verbatim: two nested named things sharing one name makes a screen
reader say it twice with nothing to distinguish them; (ii) the bar wrapper and every segment are
`aria-hidden`, carry **no** `role` and **no** name; (iii) the legend is **visible text** and needs
no visually-hidden block at all — so the third-instance promotion trigger **does not fire**, and
that is stated rather than left as an absence; (iv) **the `ManaPip` in each legend entry stays
decorative** (no `label`), because the entry's own text already says the colour, the count and the
percentage, and a labelled pip beside it is the doubled announcement `ManaPip.tsx:35-37` warns
about. ⚠️ **(iv) contradicts the surface reading of `ManaPip`'s docstring** — the prop was written
"for c4-9's legend" — so if it ships unlabelled, **say so and correct the docstring**, rather than
leaving a shipped comment that predicts a caller that never arrived. The colour name must then
reach the user as *text* in the legend entry, which is the real content of "the legend is the
accessible data path".

**Q10 — What does the panel do for a colourless, zero-pip or empty deck — and does the row still
render?**
The epic AC names it: *"renders correctly rather than dividing by zero or showing an empty bar"*.
§D: **no real deck has zero pips**, 9 are mono-colour, the smallest bar is 2 pips in a one-card
deck. Story 4.12 hides this panel on an empty deck by name, and c4-12 ships after this story.
c4-8 hid `ManaCurve` when the curve total was zero, which leaves an empty `.analysis-row` and a
phantom 24px gap — accepted posture, with **c4-9 named to revisit**.
*Proposal:* **render nothing when the pip total is zero** (matching c4-8's condition-on-the-data
ruling, not on the deck's card count), **and gate the `<AnalysisRow>` itself on both children
being absent**, which is the revisit c4-8 asked for and is now cheap: with two children the
question changes from "a second derivation for a state no deck can produce" to "the row has a
child or it does not". ⚠️ Do the gate **without** re-deriving either panel's data in `App.tsx` —
the honest shape is for each panel to own its own emptiness and the row to render only when the
deck has cards, which is c4-12's clause arriving early and should be **flagged to c4-12 by name**.
Also rule the **mono-colour** case explicitly: one segment at 100%, one legend entry, and the
percentage reads `100%` not `100.0%` — 9 real decks see this and it is the second most common
shape in the corpus.

**Q11 — Does the two-child row get a stacking breakpoint?**
`AnalysisRow.css:9-14` flags it to this story by name: *"whether c4-9's second panel wants a real
stacking breakpoint (a non-zero flex-basis, which needs a derived and cited value) is that story's
decision — it owns the first screen with two children."*
*Proposal:* **decide it on the eye-check, not in advance.** The measurable facts today: the row is
**870px** wide at 1440, so two children are **~423px** each; UX-DR8 says the app targets
~1100px→~2560px and that **below ~1100px the right column drops beneath the left** — which *widens*
the left column rather than narrowing it, so the squeeze case is narrower than the app's own stated
floor. The proposal is therefore **no breakpoint**, with the eye-check measuring the legend at
423px and at the 1100px floor and **reporting the number**, because a legend of up to five entries
each carrying a pip, a count and a percentage is the thing that wraps first. If it wraps badly, the
answer is a legend that wraps *gracefully* (it already would — the composition reference wraps),
not a flex-basis. **Whatever is ruled, `AnalysisRow.css`'s comment is updated** so it no longer
describes an open decision.

**Q12 — Does this story write the numeric mana-value parser c4-8 re-homed here?**
`curve.ts:39` and `curve.test.ts:219` both name c4-9, and `curve.test.ts:212-236` is pinned red-in-
waiting: a true split card buckets at `[0,0,0,0,0,0,1]` and *"c4-9's parser flips it to bucket 4"*.
*Proposal:* **decline, and re-home with the reason.** This story needs to count *pips*, not to
compute a *mana value*: a pip counter walks `ManaSymbolToken.colours` and never adds a generic
cost, so **nothing this story writes converts a cost to a number**. Writing one anyway — to fix a
divergence with **0 live exposure**, in the panel that has 16 open questions of its own — is scope
this story cannot justify. **The honest home is a story that needs a mana value**, and there is
none in Phase 1; record it as such. ⚠️ **Then `curve.test.ts`'s comment is false** — it promises
c4-9's parser flips it — so the comment is corrected in this diff to name the real condition
("whoever writes a numeric mana-value parser"), which is the epic's standing "a false comment is a
defect" rule applied to a comment this story is the first to read.

**Q13 — How are segment widths expressed, given the inline-style rule?**
Widths are data. `eslint.config.js:208-217` errors on any `style` attribute whose object literal
has a key that is not the **exact string** `--curve-bar-height`.
*Proposal:* **avoid the runtime channel entirely — use `flex-grow`.** A segment's width is its
share of the bar, which is exactly what `flex: <count> 0 0` on a `display: flex` track computes,
with the browser doing the division. That removes the divide-by-zero the epic AC names (there is
no division to do), removes the rounding question from the *geometry* (Q14 still owns the
*displayed* percentage), and needs no ESLint amendment, no `RUNTIME_CUSTOM_PROPERTIES` entry and
no `as CSSProperties` cast. ⚠️ **`flex-grow` still needs a number in the markup**, and a
`style={{ flexGrow: n }}` is exactly what the rule bans — so this proposal is only real if the
number rides a **custom property consumed by `flex-grow` in CSS**, which puts us back at a named
channel. **Rule between the two explicitly**: (a) a named channel `--colour-bar-share` added to
**both** `eslint.config.js`'s exact-name set **and** `RUNTIME_CUSTOM_PROPERTIES`, in the open, per
ruling 23 — with `inline-style-violation.tsx` held at **exactly 2** messages and a firing case
added to `custom-property-violation.tsx`; or (b) a bounded set of pre-declared percentage classes,
which is not viable (percentages are continuous). **(a) is the realistic answer**; the value of
writing (b) down is that the next reader does not re-propose it. Whichever ships, note c4-8's
measured trap: **the object literal must be inline at the JSX call site** — a helper returning it
is precisely the evasion the first selector closes, and it caught c4-8's own author.

**Q14 — Rounding: what do the percentages say, and do the widths agree with them?**
Unspecified everywhere. The composition reference does `Math.round(n / total * 100) + '%'` and
uses the **same string** as the segment width, so three colours at 33.3% paint 99% of the bar.
c4-8's precedent (`Math.round`) was re-homed to this story by name.
*Proposal:* **separate the two.** The **geometry** is exact (Q13's share, unrounded), so the
segments always fill the bar. The **displayed** percentage is `Math.round` to a whole number, which
is what a legend is for, with the consequence stated in the module header: **the displayed
percentages need not sum to 100** (three equal colours read 33% · 33% · 33%). That is honest and
visible; a "largest remainder" correction that makes them sum to 100 makes one colour's printed
number disagree with its own count, which is worse. **Pin a real three-colour deck** and assert the
printed set. Also rule the degenerate: a colour with a non-zero count that rounds to `0%` — the
thinnest live case is 1 pip of 114 (`Ayara Black Devotion`), which rounds to **1%**; a 1-of-200
would round to 0% and print `0%` beside a count of 1. Decide whether that floors to `1%` or prints
`0%` honestly, and say which, because the count beside it is the un-rounded truth either way.

**Q15 — What is authored copy here, and what is data?**
The panel title, the figure's accessible name, the word in `"12 pips"`, the `%` sign, and each
colour's **name** (Q9(iv) makes the colour name the accessible carrier) are authored. The counts
and the percentages are data.
*Proposal:* `copy.ts` (import-free, `COPY_MODULES` **10 → 11**) owns all of them. ⚠️ **Colour names
already exist and are unreachable**: `parse.ts:208` declares `COLOUR_NAMES` (`w → white`, …) as a
**module-private `const`, not an export** — `describeManaCost` is its only consumer. So the choice
is not "import or re-declare"; it is **re-declare, or export a second consumer's worth of parser
internals**. The proposal is to **re-declare in `copy.ts`** (which must stay import-free anyway
under the TS project-boundary rule) with a **type-level assert coupling the labels to
`ManaColour`** in both directions, so a colour added to the parser fails *this* module rather than
silently rendering an unlabelled segment — ruling 17's shape. **Note the divergence risk out
loud**: two lists now spell the six colour names, and `describeManaCost`'s copy is the one a
screen reader hears on a card's cost. If they should be one list, exporting `COLOUR_NAMES` is the
change — rule which, rather than leaving two silently. Also confirm singular/plural for
`"1 pips"`, and if pluralisation is invented, **say that it is invented**, as c4-8 was made to.

**Q16 — Does this story change `compute_pip_signals`?**
§H: the Python counts bare pips only, excludes lands by the whole-string test, includes the
sideboard, and already falls back to the front face. Under Q1/Q4/Q6's proposals the glass will
differ from it on **hybrids, Phyrexian, generic-hybrids, the sideboard and split cards** — five
axes at once.
*Proposal:* **DECLINE, as c4-8 declined the land policy, and record the divergence with a named
home.** `compute_pip_signals` feeds `_mana_efficiency_score` through `dimensions.py:667-702`, which
feeds `assess_deck_power`, whose calibration benchmark set is Epic 5's frozen artefact — changing
pip counting would require re-validating it, which is not work that belongs inside a colour bar.
**But the divergence is upgraded from latent to observable in this story**, exactly as c4-8's was:
the agent and the glass will now answer *"how much white is this deck"* differently for the 8 decks
carrying hybrid or Phyrexian pips. **Write the ledger entry with all five axes named and the deck
count beside each**, because c4-8's lesson is on the record: *"a bare number in a ledger entry is
not checkable when three tests all sound like the same policy."*

---

## Acceptance Criteria

### The panel — presence, placement and semantics

1. A `ColourDistribution` container renders inside `AnalysisRow` **beside `ManaCurve`**, in
   `AppShell`'s `left` slot, with **no edit to `AppShell.tsx`** (FR-05, UX-DR8, UX-DR18) — the
   **eighth** application of the c2-9 displacement ruling. `AppShell.test.tsx:116`'s `'c4-9'`
   assertion still passes against the component's own props.
2. The row renders **two children at exactly 1:1**, and `App.test.tsx:556`'s
   `toHaveLength(1)` becomes **2** with a document-order assertion (curve first). The 1:1 contract
   is read from the stylesheet, not assumed.
3. It renders **only** when `surfaceOf` returns `kind === 'deck'`, inheriting the existing
   left-slot arm. A test asserts the panel is **absent behind every state panel arm** — all of
   them, parametrized, not one (c4-8's review finding, not repeated).
4. It is a `Panel` with `title` from `copy.ts` (an `<h2>` naming the `<section>`, UX-DR44) at
   `level="default"`.
5. The graphic is a **`<figure>` with an accessible name distinct from the panel title**, and the
   figure's accessible alternative is the **visible legend** (UX-DR18, UX-DR44, Q9). The name is
   verified against **Chrome's own accessibility tree**, not jsdom.

### The derivation — which cost, which pips, which cards

6. **Pips are counted from the FRONT FACE only** (Q1), using `parseManaCost`'s own token stream —
   `parseManaCost` is **reused, never forked**, and `MANA_COLOUR_ORDER` is **not copied**. A named
   test pins `Prismatic Dragon`'s real rows and asserts **both** totals (whole-string **71**,
   front-face **45**) so the measurement survives in the suite rather than only in this file.
7. **The panel reads the hydration cache** so the 2,830 blank-cost faced cards contribute their
   real pips (Q2), reusing `frontFaceCost`'s three-shape resolution. The record states that
   hydration is worth **+48 pips across 16 of 40 decks**, that **34 of the 46 live blank-cost
   copies** are recoverable, and that the remaining 12 are Pathway lands that correctly contribute
   nothing.
8. **The cache is read through ONE subscription to the map** (Q3), never a hook per card and never
   `readCardEntry`. The panel **starts no fetch**: `hydrateCard`/`hydrateDeckCards` are not called
   here (don't-break 10).
9. **Hybrid, Phyrexian, generic-hybrid, generic, `{X}` and `{C}` each follow Q4's ruling**, and
   **each is pinned by a named test over a real corpus card**, with the live deck that exercises it
   named. The record states the live exposure: **29 hybrid and 7 Phyrexian pip copies across 8
   decks**, including one `{G/W/P}`; **`{C}` and `{S}` are zero live**, so a colourless segment
   ships untested against real data and the story says so.
10. **Lands are excluded per Q4(e)**, reusing `curve.ts`'s `isLand` — the whole-word front-face
    test, **not** `groupOf(t) === 'Land'` and **not** the Python whole-string policy. A named test
    pins the divergence.
11. **The board policy is commander + mainboard, sideboard excluded** (Q6), matching
    `deckGroups.ts:197` — the shipped sentence that names *"the curve and colour panels"* by
    function — and `deck_analysis.py:171-173`.
12. **Counts are summed quantities, never row counts.** A test over a ×4 row proves it.
13. **The derivation is a pure total function in its own module, called in render with no
    `useMemo`** (Q5), with **no store write and no second derivation of `boards`** (AD-12,
    don't-break 5). **Its measured cost on the 99-card deck is in the record**, alongside c4-8's
    ~24 µs for comparison, and the record states how many times it runs during a cold-open sweep.
14. **No fixture asserts against `card_faces IS NOT NULL`** or any predicate that matches all
    38,261 rows; every corpus measurement in this story uses `json_type(card_faces)='array'`. Every
    fixture card is a **real corpus card with its real `name`, `mana_cost`, `type_line` and
    `colors`**, re-measured read-only at `1ed2e83` (the c4-8 High, not repeated).

### The bar and the legend — ink, geometry and type

15. **The bar is a single `14px` pill-radius bar on the `--surface-well` track**, segmented by
    `--mana-*` tokens (UX-DR18, `DESIGN.md:210-213`, `:408`). The `14px` carries a
    **`DESIGN.md:212` citation within 60 characters in the same block comment** (ruling 8), and
    **no token is added for it** — the 2026-07-25 validation report already flags it as
    over-tokenised.
16. **`ColourDistribution.css` joins `MANA_DATA_INK`** (`token-usage.test.ts:682`) with its reason
    — **the first joiner since c2-8 declared the allowlist**, and the entry says why this file is
    data ink. Tokens are spent only through the property allowlist (`background`,
    `background-color`, `background-image`, `fill`, `stop-color`), the segments take a **class**,
    and **no `--mana-*` appears in markup anywhere** (the markup half allows none).
17. **`--mana-gold` does not ship** (Q8), the spent-token count stays **6 of 7**, the absence is
    **asserted by a test** (c4-5's AC-14 pattern), and `ui/README.md:706-710`'s prediction that
    c4-9 would be its first consumer is **corrected in this diff** with the reason (a pip is never
    gold; `MANA_COLOUR_ORDER` excludes it deliberately).
18. **Segment separation follows Q7's ruling.** The record carries the measurement either way:
    **21 of 21 adjacent `--mana-*` pairs are under 3:1**, worst **1.03:1**
    (`--mana-b`/`--mana-colorless`), best **2.30:1**; **every segment clears the track at
    ≥6.62:1**. If a hairline ships it is cited to `DESIGN.md:209`'s `curve-bar.segment-hairline`
    pattern and recorded as an amendment `color-bar`'s frontmatter should carry; the outer edges
    do not gain one; and **the eye-check measures the thinnest live segment against it.**
19. **Segment widths are exact and always fill the bar** — no division by zero is possible because
    Q13's mechanism does no division at the call site. If a runtime channel ships, it is a **named**
    property added to **both** `eslint.config.js`'s exact-name set and
    `RUNTIME_CUSTOM_PROPERTIES`, in the open (ruling 23), with `inline-style-violation.tsx` held at
    **exactly 2** messages, a firing case added to `custom-property-violation.tsx`, and the literal
    **inline at its JSX call site**.
20. **Each legend entry shows a `ManaPip`, a count and a percentage** (UX-DR18). Every numeric
    value carries `font-variant-numeric: var(--type-numeric-features)` **in the same rule block**
    as its `font: var(--type-numeric)` (`findUnpairedNumericRole`), and a `--type-micro` value
    carries `var(--tracking-micro)` and its `text-transform`.
21. **Displayed percentages follow Q14's ruling**, with the consequence written in the module
    header (they need not sum to 100), a real three-colour deck pinned, and the round-to-zero case
    ruled. `{count && …}` appears nowhere; a zero renders through `Number.isFinite` (ruling 16).
22. The panel draws **no card**: its stylesheet does **not** join `CARD_SHAPED` and
    `--radius-card` appears nowhere in it (UX-DR4, both directions).

### Accessibility — where the meaning actually lives

23. **The bar is `aria-hidden` and carries no `role` and no accessible name**; the legend is the
    accessible data path (UX-DR18, UX-DR44). A test asserts the segments contribute **no**
    accessible name at all — the inverse of c4-8's per-bar naming, asserted rather than assumed.
24. **Every legend entry is asserted, not just the first** (c4-7's one-pip-run finding, not
    repeated), and each entry's **colour reaches the user as text**, so colour is never the sole
    carrier.
25. **The `ManaPip` in the legend follows Q9(iv)'s ruling.** If it ships decorative,
    `ManaPip.tsx:35-37`'s docstring — which predicts this story as the `label` prop's first caller
    — is **corrected in this diff**, because a shipped comment predicting a caller that never
    arrived is the epic's "a false comment is a defect" rule.
26. **The panel is not a live region and adds no `aria-live`** (UX-DR44, UX-DR45) — load-bearing
    here, because this panel's numbers change during the hydration sweep (AC 7).
27. **The panel adds zero Tab stops** and nothing in it is focusable or clickable (UX-DR40,
    UX-DR47). A test asserts a click changes nothing observable.
28. **The jsdom phantom-`banner` count moves from four to five** and is recorded, measured on both
    sides (jsdom and Chrome); role queries are scoped through the `h1`, never
    `getByRole('banner')`.
29. **No visually-hidden block ships** (Q9(iii)) — so the third-instance promotion trigger does
    **not** fire, and the story says so explicitly rather than leaving it as an absence. If Q9 is
    ruled otherwise, the promotion to `src/styles/` happens in this commit.

### Motion, emptiness and the row

30. **If a segment width animates, its row is added to `tokens.css:285-317`'s inventory in this
    story AND UX-DR42 is amended** — the spec's own instruction (*"Any motion added later must be
    added to this list with a fallback"*) and the block's own (*"A motion with no registered
    fallback is an incomplete story"*). There is **no colour-bar row today**. The reduced-motion
    fallback is **measured** against a real engine, not asserted.
31. **Nothing pulses, loops or alternates** at any setting.
32. **The zero-pip and mono-colour behaviours follow Q10's ruling**, with the triggering condition
    stated. The record states that **no deck in the corpus has zero pips** (so that state is not
    producible from live data and is asserted against the **derivation**, not a hand-built deck),
    that **9 of 40 decks are mono-colour**, and that the smallest real bar is **2 pips in a
    one-card deck**.
33. **The `<AnalysisRow>` gating question c4-8 flagged to this story is answered** (Q10), the
    land-only empty-row posture is either closed or re-affirmed with a reason, `App.tsx`'s comment
    is corrected to match whatever ships, and the early arrival of c4-12's hide clause is
    **flagged to c4-12 by name**.
34. **Q11's narrow-width decision is ruled on the eye-check**, and `AnalysisRow.css:9-14`'s comment
    is updated so it no longer describes an open decision.

### The record, the gates and the ledger

35. `CONTAINERS` (`shell.test.ts:1515`) gains one entry per new module with a sorted exhaustive
    import list and a prose reason, and the pin at `:1795` moves from **16**. If `frontFaceCost.ts`
    moves (Q2), both its old and new entries are correct in the same commit.
36. `copy.ts` exists with **no relative imports** and is registered in `COPY_MODULES`
    (`copy-rules.test.ts:107`) with a **>40-character** reason (**10 → 11**).
37. **Both token pins hold at 69** (`tokens.test.ts:321`, `token-usage.test.ts:1142`) and the story
    states plainly why: `color-bar`'s three frontmatter values resolve to `--surface-well`, a cited
    `14px` literal and `--radius-pill`. If a token is added, both pins move together and the story
    says why.
38. **An eye-check is performed in a real browser over CDP against the running backend**, not
    described. It must cover: the 99-card deck (`Atraxa Counter Cabinet v2 (owned)`), the
    five-colour extreme (`Infinite Guideline Station v2 (owned)`), a **mono-colour** deck
    (`Ayara Black Devotion` — 114 pips, one segment), the **one-card** deck (`Iron Man, Modern
    Marvel — reminder` — 2 pips), a deck with **live hybrid pips** (`Astonishing Ant-Man` — 10
    copies) and one with **Phyrexian** (`Atraxa Counter Cabinet`), a **Q1-sensitive** deck
    (`Prismatic Dragon`), and **both motion settings**. It reports measured numbers: segment widths
    in pixels, the thinnest segment, the hairline's effect on it, the track and segment colours,
    the legend's layout at the **~423px half-width** and at the **1100px** column floor, both type
    roles, the row's height before and after this panel, the panel's contribution to left-column
    height, and the figure/legend structure read from **Chrome's own accessibility tree**.
39. **Evasion probes are run against every new guard through the full `npm test`**, never a
    standalone file run. Enumerated **by letter before implementation**, including at least:
    (a) a new module absent from `CONTAINERS`; (b) `--radius-card` in this story's CSS **and** a
    chrome radius in a `CARD_SHAPED` file (both halves); (c) the pip source switched to the whole
    `mana_cost` string; (d) the hydration branch removed so blank-cost cards contribute nothing;
    (e) the sideboard included; (f) the commander excluded; (g) lands included; (h) a `--mana-*`
    token spent through a banned property; (i) the same token as a `fill=` markup attribute;
    (j) a `--mana-*` in markup or a token name built at runtime; (k) `--mana-gold` referenced;
    (l) `--type-numeric` without `font-variant-numeric`; (m) `aria-live` added; (n) an accessible
    name put back on a segment; (o) an authored word smuggled out of `copy.ts` or into an
    `aria-label`; (p) a `px` literal with no `DESIGN.md` citation; (q) a hybrid pip credited to one
    colour instead of both (or per Q4's ruling); (r) if Q13 ships a channel, a plain
    `style={{ width: … }}` must **still** error and the named one must pass with
    `inline-style-violation.tsx` held at exactly 2. **Plus two do-nothing negative controls whose
    silence is what makes the rest mean anything.** A probe that **passes is recorded, not quietly
    fixed**, and any substitution for an enumerated probe is **declared**.
40. **Every one of the nine inherited deferrals gets a written disposition** — resolved, declined
    with a reason, or re-homed by name (C2 retro R2) — and the **eight** triggered residues get a
    line each, including the `MANA_DATA_INK` join, `--mana-gold`'s decline, `StatChip`'s
    first-triggered-and-declined surface, and the no-re-drive window this story re-enters.
41. **The ledger entries are written into `deferred-work.md` in this commit**, not only into this
    story file. c4-7's review raised this as a finding and c4-8 wrote **one** disposition block
    (`deferred-work.md:3546-3572`) while eight others lived only in its record. New entries owed:
    Q16's five-axis Python divergence, Q12's re-homed mana-value parser, and Q7's `color-bar`
    frontmatter amendment if a hairline ships.
42. **The measured doc corrections land in this diff**: `ui/README.md:706-710`'s `--mana-gold`
    prediction (AC 17); `ManaPip.tsx:35-37`'s `label`-prop prediction if Q9(iv) ships decorative
    (AC 25); `curve.test.ts:212-236`'s comment naming c4-9's parser if Q12 declines (AC —, Q12);
    `AnalysisRow.css:9-14`'s open-decision comment (AC 34); `App.tsx:250-255`'s empty-row comment
    (AC 33); and **c4-8's record's "all live split-cost rows are Adventures"**, which is measurably
    **8 Adventure / 18 Omen / 1 neither** — corrected where it appears in `sprint-status.yaml`,
    with c4-8's substantive ruling (0 live `cmc` divergences) re-verified and left standing.
43. The record states the **frontend and Python test counts, the file count, every registry that
    moved, and both bundle asset names with byte sizes**, against the `1ed2e83` baselines. **Both
    bundle assets must change**; report the hash even where a byte count does not move.
44. **The bundle assets and every new module are `git add`ed before the record claims a green
    run** — the registry guards are blind to untracked files, and untracked bundle assets have been
    a **High** finding in two of the last six stories.
45. The **plugin mirror** at `plugin/server/src/companion/app/static/` is updated by hand and
    verified **sha256-identical per file**; the standing fact that **nothing checks it** is
    re-stated with its named home (the C4 retro).
46. Python is untouched: `uv run pytest` stays at **2,501 passed / 1 skipped**. Q16's decline is
    what makes this true, and the record says so rather than leaving it as an absence.

---

## Tasks / Subtasks

- [x] **Task 0 — Answer the sixteen open questions before writing code** (AC 6–14, 16–19, 40)
  - [x] Re-verify §A–§H read-only against the shipped database at `1ed2e83`, using
        `json_type(card_faces)='array'` and keying every per-deck count on **deck id**
  - [x] **Read `eslint.config.js:139-222` and `token-usage.test.ts:584-730` before designing the
        segment widths and the CSS** — the two allowlists this story must join or avoid
  - [x] Rule Q1–Q16, each with its reason recorded in the Debug Log
  - [x] Confirm `tokens.test.ts` needs no `components.color-bar` frontmatter entry and 69 holds
- [x] **Task 1 — The pure derivation** (AC 6–14)
  - [x] `colours.ts` — one total function over `(boards, cards)`; front-face pips; the Q4 rules;
        `isLand` reused; commander + mainboard
  - [x] Named tests over **real** corpus cards: `Prismatic Dragon`'s 71-vs-45, a hybrid card, a
        Phyrexian card, `{G/W/P}`, a generic-hybrid, `{X}`, a ×4 row, the sideboard, the commander,
        a land with a cost, and the zero-pip case asserted **against the derivation**
  - [x] Measure the derivation cost on the 99-card deck; record it beside c4-8's ~24 µs
- [x] **Task 2 — The copy** (AC 20, 24, 36)
  - [x] `copy.ts`, no relative imports; title, figure name, colour labels, the pip word, the `%`
  - [x] The type-level assert coupling the colour labels to `ManaColour` in both directions
  - [x] Register in `COPY_MODULES` with a >40-char reason (10 → 11)
- [x] **Task 3 — The bar** (AC 4, 5, 15–19, 22)
  - [x] `ColourDistribution.css` joins `MANA_DATA_INK` with its reason — the first joiner
  - [x] The track, the segments, Q7's hairline, Q13's width mechanism, the `DESIGN.md:212` citation
  - [x] If Q13 needs a channel: both allowlists, both fixtures, the pin held at 2
- [x] **Task 4 — The legend and the accessible shape** (AC 20, 21, 23–29)
  - [x] The legend grid, both numeric roles with their companions, Q14's rounding
  - [x] `aria-hidden` on the bar; every legend entry asserted; the pip's `label` per Q9(iv)
- [x] **Task 5 — The mount and the row** (AC 1–3, 32–34)
  - [x] One sibling inside `<AnalysisRow>`; `AppShell.tsx` untouched
  - [x] `App.test.tsx`: children 1 → 2, document order, absence parametrized over **every** state
        arm, the land-only row per Q10
  - [x] Q11's narrow-width ruling and the `AnalysisRow.css` comment update
- [x] **Task 6 — Registries, guards and probes** (AC 35–37, 39)
  - [x] `CONTAINERS` 16 → N + the pin; `COPY_MODULES` 10 → 11; `MANA_DATA_INK` 1 → 2
  - [x] Run the eighteen lettered probes plus two negative controls, through full `npm test`
  - [x] Record every probe with the named test that closes it; declare every substitution
- [x] **Task 7 — The eye-check, the gates and the record** (AC 38, 40–46)
  - [x] CDP eye-check over the seven named decks and both motion settings
  - [x] Ten gates: `npm run lint`, `format:check`, **`npx tsc -b --force`**, `npm test`,
        `npm run build`; `uv run pytest`, `ruff check .`, `ruff format --check .`, `mypy src/`,
        `mypy src/ --platform win32`
  - [x] `git add` everything, rebuild the bundle, stage it, **hand-copy the plugin mirror**
  - [x] **Write the `deferred-work.md` entries in this commit** (AC 41) and land the six doc
        corrections (AC 42)
- [x] Set status to `review` and **STOP** — Brad runs the three-layer review and raises the PR

### References

- Epic story text — `_bmad-output/planning-artifacts/epics-companion-app.md:2160-2187`
- UX-DR18 — `:433-435` · UX-DR7 — `:364-368` · UX-DR8 — `:372-378` · UX-DR13 — `:395-398`
- UX-DR17 — `:426-431` · UX-DR42 — `:577-584` · UX-DR44 — `:590-595` · UX-DR45 · UX-DR47 — `:608-609`
- Story 4.12's hide clause — `:2276-2278` · deck-change recompute — `:3026-3028` · NFR-05 — `:157`
- `DESIGN.md:210-213` (`components.color-bar`) · `:408` (anatomy) · `:209` (`curve-bar.segment-hairline`)
- `DESIGN.md:312`, `:316`, `:360`, `:364-367`, `:391`, `:435` · `validation-report-2026-07-25.md:73, 75`
- `EXPERIENCE.md:34`, `:70`, `:95`, `:111`, `:113`, `:154`, `:173`, `:183`, `:190`
- Superseded contrast finding — `review-accessibility.md:1-7` (banner), `:26`
- Composition reference — `…/imports/claude-design/Planeswalker Companion.dc.html:73-92`,
  `:340-346`; `_ds/_ds_bundle.js` (`ManaPip.jsx`, `ManaCost.jsx`)
- Parser to reuse — `ui/src/components/ManaCost/parse.ts:30-73, 164, 203-219, 247`
- Pip primitive — `ManaPip.tsx:22, 35-41, 44-93`; `ManaPip.css`; `ManaPip.test.tsx:78`
- Front-face cost — `ui/src/containers/DeckList/frontFaceCost.ts:28-51, 93-169`
- Cache — `ui/src/state/cards.ts:110, 122, 245-261, 557, 578, 603`; `DeckList.tsx:182-196`
- Derivation to reuse — `ui/src/state/deckGroups.ts:152, 176-181, 197, 203-214, 252-276`;
  `ui/src/containers/ManaCurve/curve.ts:36-40, 74-123, 158-162, 223-254`; `curve.test.ts:212-236`
- Sibling shape — `ManaCurve.tsx:82-85, 107-130, 144-146, 168-179, 193-209`; `ManaCurve.css:23-31,
  35-37, 87, 122-128, 141-179`; `copy.ts:35-48`
- The row — `AnalysisRow.tsx:9-30, 46-53`; `AnalysisRow.css:9-14, 15-42`;
  `AppShell.tsx:64, 121-137`; `AppShell.css:139, 151-156`; `AppShell.test.tsx:111-116`
- Mount and rulings — `App.tsx:239-263`; `App.test.tsx:323, 502-507, 550-556, 581, 761`
- Primitives — `Panel.tsx:31-67, 94-97`; `StatChip.tsx:26-49`; `GroupHeader.tsx:25-38`
- Tokens — `ui/src/styles/tokens.css:125-133, 160-178, 285-317`
- Guards — `shell.test.ts:960, 1002-1032, 1195, 1326, 1515, 1795`; `token-usage.test.ts:234-243,
  415-442, 484-553, 584-598, 682-730, 760-791, 868-905, 1142`; `tokens.test.ts:321`;
  `copy-rules.test.ts:62, 107`; `posture.test.ts:339`; `store-writes.test.ts:77`;
  `wire-contract.test.ts:145`; `gate-geometry.test.ts:53`
- The inline-style rule — `ui/eslint.config.js:139-222`; `ui/tests/lint-gates.test.ts:133-172`;
  `fixtures/tsx/{inline-style-violation,custom-property-violation,clean}.tsx`
- `ui/README.md:668-719` (the data-ink allowlists), `:721-739` (parser totality), `:741-758`
  (naming a colour-only graphic)
- Wire — `ui/src/api/types.d.ts:430-472`; `ui/src/api/schema.ts:77, 87, 100`
- Python pip policy — `src/logic/assessment/mana_base.py:33, 80, 230, 305-317, 343-390`;
  `src/logic/assessment/dimensions.py:667-702`; `src/mcp_server/tools/deck_analysis.py:171-173`
- Ledger — `deferred-work.md:1400-1419, 1447-1471, 1668-1699, 3456-3464, 3515-3520, 3528-3531,
  3536-3572, 3626-3637, 3639-3649, 3765-3767, 3806-3814, 3869-3877, 3920-3923`
- Prior records — `c4-8:...:78-83, 344-359, 422-486, 507-526, 648-700, 1129-1247, 1540-1670`;
  `c4-7:...:532-568, 631-694`; `c2-8:...:465-470, 679-690`
- CI bundle sync — `.github/workflows/ci.yml:114-171`; `scripts/build_plugin.py:190-215`

### Review Findings

Three-layer review 2026-08-06 (Blind Hunter / Edge Case Hunter / Acceptance Auditor), 25 raw findings → 22 after merges. Auditor AC tally: 42 implemented / 4 partial (AC 6, 14, 18, 21) / 0 missing. Mirror sha256-verified; all fixture-fabrication claims re-verified read-only against the shipped DB during triage.

- [x] [Review][Decision] **The `groupOf` land-policy guard is vacuous, with a comment asserting the opposite of its own expect** — `colours.test.ts:418-427`. `Seat of the Synod` (`mana_cost: ''`) and `Gilded Lotus` (`{5}`) both contribute zero pips under EITHER land policy, so the test stays green if `coloursOf` used the exact `groupOf(t) === 'Land'` defect it names; and ":424's "one that genuinely IS an artifact still counts" is followed by `toEqual({})`. The only fixture with teeth is a coloured-cost Artifact Land, and **no corpus card has that shape** — so the fix requires a declared-synthetic fixture, deviating from AC 14's every-fixture-is-real rule. **RULED (Brad, 2026-08-06): synthetic-declared fixture** — `Synthetic Artifact Land (no corpus card has this shape)` with `{G}`, the file's only deliberate AC 14 deviation, declared in place; the "genuinely an artifact still counts" half re-fixtured to `Esper Sentinel` (`{W}`, real) so both halves bite.
- [x] [Review][Decision] **The deck-level measurements rest partly on constants and hand-built decks (AC 6 + AC 21)** — `colours.test.ts:239-247` adds the literal `OTHER_ROWS = 19` to both sides, so 45/71 can only fail through the ten pinned Omen rows; the 28 remaining rows' identical-under-both-readings premise is a claim in a constant. And AC 21/Q14's "pin a real three-colour deck" is satisfied by hand-assembled card sets (`evenThree`, `THREE_COLOURS`), not a corpus deck. **RULED (Brad, 2026-08-06): ratify with provenance declared** — `OTHER_ROWS = 19` stays, its comment now states it is a recorded measurement the suite cannot re-derive (the ten-row 26-vs-52 policy probe is what genuinely survives); `evenThree` declared a hand-assembled set, with AC 38's eye-check named as where corpus decks render.
- [x] [Review][Patch] `Lander Rizzi` carries an invented `mana_cost`/`colors`/`cmc` — real row is `'{X}{G}{G}'`, `["G"]`, cmc 2 (AC 14; the c4-8 fabrication class inside a file whose header claims verbatim fixtures) [ui/src/containers/ColourDistribution/colours.test.ts:412]
- [x] [Review][Patch] `Exude Toxin` is not a corpus card (it is a face name; the standalone row is invented) — swap the `{X}`-drop pin to a real `{X}{B}{B}` card, e.g. `Black Sun's Zenith` (verified in DB) [ui/src/containers/ColourDistribution/colours.test.ts:370]
- [x] [Review][Patch] Sephiroth's hydrated back-face cost is invented (real faces are `['{2}{B}', '']`) — pin the front-face-only rule on a real both-faces-costed MDFC, e.g. `Birgi, God of Storytelling // Harnfel, Horn of Bounty` (verified: front `{2}{R}`, blank top-level) [ui/src/containers/ColourDistribution/colours.test.ts:285-296]
- [x] [Review][Patch] `Pond Prophet` type line invented — DB says `Creature — Frog Advisor`, not `Frog Cleric` (AC 14 letter) [ui/src/containers/ColourDistribution/colours.test.ts:462]
- [x] [Review][Patch] Rendered-test fixture helper hardcodes `colors: []` for every card, the Atraxa fixture omits its real `["B","G","U","W"]`, and Atraxa's name uses a curly apostrophe where the DB stores a straight one (AC 14's enumerated `colors` field) [ui/src/containers/ColourDistribution/ColourDistribution.test.tsx:40-50; colours.test.ts:436-441]
- [x] [Review][Patch] The reactivity witness's `setState(... as never)` erases all type checking — narrow the cast the way `colours.test.ts:79-90` deliberately does, so `CardEntry` drift is caught [ui/src/containers/ColourDistribution/ColourDistribution.test.tsx:313]
- [x] [Review][Patch] `{S}` snow contributes nothing via the `unknown`-token path and has no pinned test — a snow pip renders in the deck row but is silently absent from the bar; add the fixture pinning current behaviour [ui/src/containers/ColourDistribution/colours.test.ts]
- [x] [Review][Patch] True split cards (both halves first-class casts) are the one `' // '` subclass with no fixture, and the front-face rationale (b) doesn't cover them — add a pin, e.g. `Heaven // Earth` (`'{X}{G} // {X}{R}{R}'`, verified in DB) [ui/src/containers/ColourDistribution/colours.test.ts]
- [x] [Review][Defer] The inline-style channel allowlist is global and value-unconstrained — either declared channel is admitted in any file (`--curve-bar-height` writable from `ColourDistribution.tsx` and vice versa) and no gate constrains the value; `RUNTIME_CUSTOM_PROPERTIES` already records the owning file, the ESLint half ignores it [ui/eslint.config.js:230] — deferred, guard-hardening beyond this story's scope
- [x] [Review][Defer] A segment below ~0.24% share paints only its own track-coloured hairline (border-box eats its width) — bar shows N−1 colours while the legend lists N; unreachable live (thinnest live segment 15.35px) [ui/src/containers/ColourDistribution/ColourDistribution.css:116-118] — deferred, cosmetic at Commander-plus scale only
- [x] [Review][Defer] An all-blank-cost deck at cold cache conflates "genuinely colourless" with "not yet hydrated": the panel materializes mid-sweep and snaps the curve from full to half width, unannounced by design — no corpus deck reaches it [ui/src/containers/ColourDistribution/ColourDistribution.tsx:147] — deferred, consequence of the ruled Q10 total-gate inside the accepted c4-6 window

Dismissed (9): hybrid sum-exceeds-symbols visibility (Q4a ruled the comment posture in the spec Brad approved); per-write re-derivation (Q5 ruled, measured 4.8 ms); "1 pip · 0%" (Q14 ruled, not producible live); `?? 0` fallbacks (required by `Map.get`'s type under strict TS); `wholeStringPips` re-implementation (independence is what makes the differential test non-circular); non-spaced `//` separators (exact-literal choice measured and ruled in `frontFaceCost.ts:55-67`, corpus clean); negative/zero quantity (upstream wire invariant, identical posture in `curve.ts:242`); loading/unknown under-reporting (the documented-accepted c4-6 ruling 1, cited in-module); AC 18 computed-vs-measured thinnest segment (both numbers honestly attributed in the record).

---

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`

### Debug Log References

#### Task 0 — the sixteen rulings, and what the database actually says

Every §A–§H figure below was re-measured read-only at `1ed2e83` against
`%LOCALAPPDATA%\artificial-planeswalker\cards.db` with a Python mirror of `parse.ts`'s
tokeniser, `deckGroups.ts`'s `frontFace` and `curve.ts`'s `isLand`, using
`json_type(card_faces)='array'` throughout and keying every per-deck count on **deck id**.

**Five corrections the record owes, all measured.**

1. **§A's three totals are a DIFFERENT POPULATION from the one that ships.** 2,608 / 2,547 /
   2,595 reproduce exactly — over **every deck row, sideboard and lands included**, which §A
   says in its own preamble. The population this panel actually draws (Q6 excludes the
   sideboard, Q4(e) excludes lands) is **2,521 whole-string / 2,460 front-face / 2,508
   front-face-after-hydration**. Both are right; only the second describes the bar. Every
   per-deck figure §A quotes is unaffected and re-verified: **10 of 40 decks change**, **2
   re-order** (`Prismatic Dragon`, `Temur Dragonstorm`), `Prismatic Dragon` **71 → 45** with the
   order moving B>U>G>R>W → U>B>G>R>W, `Abzan Dragons` **71 → 57**, `Temur Dragonstorm v2`
   **48 → 41**.
2. **`--mana-gold` is inside §G's "21 of 21".** Six colours give **C(6,2) = 15** adjacent pairs,
   not 21; the 21 is the seven-colour set. Under Q8 gold does not ship, so the number that
   describes this panel is **15 of 15 pairs under 3:1, 8 of 15 under 1.3:1** — same worst
   (`--mana-b`/`--mana-colorless`, **1.03:1**) and same best (`--mana-w`/`--mana-r`, **2.30:1**).
   The track measurement is exact as recorded: every segment clears `--surface-well` (`#0d0f1a`)
   at **6.62:1** (`--mana-r`) to **15.20:1** (`--mana-w`).
3. **The largest live bar is 116 pips, not 114**, and five-colour decks are **5, not 4**. 114 is
   the whole-string reading of `Ayara Black Devotion`; under the shipping policy hydration adds
   the deck's own namesake (`Ayara, Widow of the Realm // Ayara, Furnace Queen`, blank top-level
   cost, `{1}{B}{B}` on its front face) and the bar reads **116, still one segment**. The fifth
   five-colour deck §D missed is `MSH — The Mad Titan's Gauntlet — Five-Color Power-Up Snap`.
   §D's other figures re-verify: **0 of 40 decks have zero pips**, smallest **2** (`Iron Man,
   Modern Marvel — reminder`), second **6** (`Graveyard Gravy`), **9 of 40 mono-colour**.
4. **Hybrid and Phyrexian pips are live in 10 decks, not 8.** The copy counts are exactly right
   — **29 hybrid, 7 Phyrexian, 1 `{G/W/P}`** — and identical under all four populations, but
   they sit in `Aanging Loose`, both `Astonishing Ant-Man`… (one deck), both `Atraxa Counter
   Cabinet`, both `Dragon-God Superfriends`, both `Ezuri Proliferate Poison` and both `Infinite
   Guideline Station`: **ten deck ids**.
5. **A THIRD measurement-instrument defect, in the same family as §9's `card_faces IS NOT
   NULL`.** `deck_cards` holds **2,027** rows, but **28 of them (89 copies, across 2 deck ids)
   have no `decks` row at all** — orphans from deleted decks. Only **1,999** rows belong to a
   live deck, which is the number `deckGroups.ts:230` already quotes. Any measurement over
   `deck_cards` that does not join `decks` over-counts by 28 rows / 89 copies. It changes
   nothing that ships (the frontend only ever sees one deck's payload) and it is why §A's
   totals reproduce only when the join is present.

**Confirmed exactly as written**: §9's correction (`card_faces IS NOT NULL` matches all
**38,261**; `json_type(...)='array'` is **3,225**; 35,036 rows store the JSON *string* `'null'`).
§10's correction (**27 live split-cost rows / 53 copies = 8 Adventure, 18 Omen, 1 neither**, the
one being `Emeritus of Woe // Demonic Tutor`; **0 live rows where `cmc` ≠ the front face's mana
value**, re-verified). §B's corpus table (338 split costs; not-Adventure **66 front / 137 sum**)
— with one refinement: the Adventure row is **134 front + 1 neither** rather than 135, the odd
one being `Keeper of the Crown // Coronation of the Wilds`, whose `{2}{L}` carries a symbol
`parse.ts` does not model. §C entirely (**2,830 of 3,225 = 87.75%** blank; **487** recoverable;
**38 live rows / 46 copies**, **34** recoverable, **12** unrecoverable and every one a Pathway
MDFC land; **+48 pips across 16 of 40 decks**, B 23 · G 10 · U 6 · R 5 · W 4). §F entirely
(**2,842 = 88.12%**; 495 with a face-level `colors`). §E's corpus census (61 distinct tokens;
41,799 coloured / 27,648 generic / 612 `{X}`; **`{C}` 46, `{S}` 3, `{2/C}` 62 — all ZERO live**).

**One measurement §A does not make, and it decides Q4(e) at no cost:** live pip totals are
**identical with and without the land filter** (2,608 either way). No land in any of the 40 real
decks carries a coloured pip, so excluding lands is free today — which is a reason to write the
policy down, not a reason to leave it unstated.

**Geometry, measured for Q7 and Q11:** at the ~423px half-width (399px inside `Panel`'s 12px
padding) the **thinnest live segment is 15.35px** — `MSH — Ultron's Forge`, 1 black pip of 26 —
followed by 17.73px, 21.22px, 23.20px. A 1px hairline costs the thinnest live segment ~6.5% of
its width. **The most legend entries any live deck needs is 5.**

---

**Q1 — front face only.** As proposed, and the reuse is stronger than the story assumed: this
panel never has to walk for the `' // '` boundary itself, because `frontFaceCost` already
resolves it (branch 1 splits, branch 3 splits the hydrated face too). Pinned with
`Prismatic Dragon`'s ten real Omen rows asserting **both** totals.

**Q2 — yes, depend on hydration, through `frontFaceCost`** — and **the module is PROMOTED to
`src/containers/frontFaceCost.ts`** rather than imported across container directories. This is
not a new precedent, it is the shipped one: `src/containers/imagedFaces.ts` and
`src/containers/useCardArt.ts` both sit at the root of this tree for exactly this reason, and
`src/components/filled.ts`'s header states the rule in words — *"a helper shared by two
components does not live inside one of them"*. `imageUrl.ts` stays inside `CardTile/` because it
has one consumer; `frontFaceCost.ts` is about to have two. Both `CONTAINERS` entries move in this
commit. c4-6's accepted no-re-drive window applies and is cited, not re-opened; **no `aria-live`**.

**Q3 — one subscription to the map**, `useCardStore((state) => state.cards)`, passed into the
pure derivation as an argument. `readCardEntry` rejected (not reactive → permanently stale).

**Q4 — (a)** a hybrid pip credits **every colour it can be paid with**, so the total exceeds the
symbol count and the legend says so; **(b)** Phyrexian counts as its colour (`phyrexian` is a
modifier, `parse.ts:55`); **(c)** `{2/R}` counts as red only; **(d)** generic and `{X}` count for
nobody (`colours: []`), and no colourless segment is invented for them; **(e)** **lands are
excluded** via `curve.ts`'s `isLand`. Each pinned by a named test over a real corpus card.

**Q5 — `colours.ts`**, one total function over `(boards, cards)`, called in render with no
`useMemo`. Cost measured and recorded below.

**Q6 — commander + mainboard, sideboard excluded.**

**Q7 — the hairline ships.** A 1px `--surface-well` separator as `border-inline-start` on
**adjacent siblings only**, so the pill's outer edges never gain one. Cited to `DESIGN.md:209`'s
`curve-bar.segment-hairline` and recorded as an amendment `color-bar`'s frontmatter should carry.
It closes **distinguishability** and says nothing about **identifiability**, which is the legend's
job — `deferred-work.md:1447-1471` stays open at Medium and this story does not claim otherwise.

**Q8 — gold does not ship.** A pip is never gold; `MANA_COLOUR_ORDER` excludes it deliberately.
Spent-token count stays **6 of 7**, absence asserted by a test, `ui/README.md:706-710` corrected.

**Q9 — (i)** the `<figure>` takes an `aria-label` distinct from the panel title; **(ii)** the bar
and every segment are `aria-hidden` with no role and no name; **(iii)** **no visually-hidden block
ships**, so c4-8's third-instance promotion trigger **does not fire**; **(iv)** the legend's
`ManaPip` stays **decorative**, and `ManaPip.tsx:35-37`'s docstring — which predicts this story as
the `label` prop's first caller — is corrected in this diff.

**Q10 — the panel renders nothing at zero pips, and the empty row is closed WITHOUT a second
derivation**: `.analysis-row:empty { display: none }`. That is the revisit c4-8 asked for, and it
needs no `App.tsx` gate, no curve total and no re-derivation of anything — the row owns its own
emptiness, which is what c4-8's finding actually asked for. Flagged to **c4-12** by name.
Mono-colour reads one segment, one entry, `100%`.

**Q11 — no stacking breakpoint.** The legend wraps gracefully instead; `AnalysisRow.css:9-14`'s
comment is updated so it no longer describes an open decision. Measured on the eye-check.

**Q12 — declined, and re-homed with the reason.** A pip counter walks
`ManaSymbolToken.colours` and never adds a generic cost, so nothing this story writes converts a
cost to a number. `curve.test.ts:212-236`'s comment naming *"c4-9's parser"* is false and is
corrected in this diff to name the real condition.

**Q13 — option (a): a named channel `--colour-bar-share`**, added to **both**
`eslint.config.js`'s exact-name set and `RUNTIME_CUSTOM_PROPERTIES`, per ruling 23. `flex-grow`
consumes it, so the browser does the division and no division happens at the call site — the
divide-by-zero the epic AC names cannot occur. `inline-style-violation.tsx` held at exactly 2;
`custom-property-violation.tsx` gains a firing case; the literal is inline at its JSX call site.
Option (b) — pre-declared percentage classes — is written down as declined: percentages are
continuous.

**Q14 — the geometry is exact and the printed percentage is `Math.round`.** They are separate on
purpose, and the consequence is in the module header: **the displayed percentages need not sum to
100**. The round-to-zero case prints `0%` honestly rather than flooring to `1%`, because the count
beside it is the un-rounded truth and a floor would make the printed number disagree with its own
arithmetic in the one case anybody would check. Not producible live — the thinnest live share is
1/26 = 3.8%.

**Q15 — `copy.ts` re-declares the colour labels**, with a type-level assert coupling them to
`ManaColour` in both directions. Exporting `parse.ts`'s `COLOUR_NAMES` would not help: `copy.ts`
must stay import-free under the `TS2835` project-boundary rule. The two lists are also different
registers — `describeManaCost` speaks lowercase words inside a sentence, the legend prints
standalone capitalised labels — and the divergence is stated rather than left silent.
Pluralisation (`1 pip` / `12 pips`) is **invented**, and this says so.

**Q16 — declined.** `compute_pip_signals` feeds `assess_deck_power`'s frozen benchmark set. The
divergence is upgraded from latent to observable and ledgered with all five axes and a deck count
beside each: hybrids (29 copies / 10 decks), Phyrexian (7 / 10), generic-hybrids (0 live),
the sideboard (87 pips / 5 decks), and split cards (27 rows / 53 copies).

### Completion Notes List

**All sixteen questions were answered before any code was written** (the rulings and their reasons
are in the Debug Log above). **Thirteen shipped as proposed.** Three deviated, each on a
measurement, and each is stated rather than smoothed over:

1. **Q2's cross-tree import: the module MOVED rather than being imported in place — and the
   story's stated reason for the question is measurably false.** The context says a container
   importing from a sibling container's directory *"has no precedent in this repo"*. It has one:
   `CardTile.tsx` imports `'../FlipControl/FlipControl'`, and `shell.test.ts`'s permitted-roots
   check admits `../X` outright. So the promotion of `frontFaceCost.ts` to
   `src/containers/frontFaceCost.ts` was chosen on the SHARED-HELPER rule (`filled.ts`: *"a helper
   shared by two components does not live inside one of them"*, with `imagedFaces.ts` and
   `useCardArt.ts` as the precedents) rather than on the absence of a precedent that exists.
   `isLand` is deliberately NOT given the same treatment, and the asymmetry is written into both
   registry entries: moving a whole module whose every export is shared costs one `git mv`, while
   splitting one export out of `curve.ts` would separate `isLand` from the three-land-policies
   argument its own docstring makes about it.

2. **Q10's row gate ships as CSS, not as an `App.tsx` condition.** The proposal was to *"gate the
   `<AnalysisRow>` itself on both children being absent"* while warning against re-deriving either
   panel's data in `App.tsx`. Those two are hard to satisfy together in TSX; they are free in CSS.
   **`.analysis-row:empty { display: none }`** closes c4-8's accepted empty-row posture with no
   gate in `App.tsx`, no total, no re-derivation of anything, and no edit to `AnalysisRow.tsx` at
   all — the row owns its own emptiness, which is what c4-8's finding actually asked for. Flagged
   to c4-12 by name in three places.

3. **Q13's channel carries a RAW PIP COUNT, not a percentage, which makes it narrower than c4-8's
   rather than wider.** `flex-grow: var(--colour-bar-share, 0)` puts the division in the browser,
   so AC 19's *"no division by zero is possible"* is true because **there is no division at the
   call site at all** — and the geometry cannot drift from the printed percentages, because it
   never reads them. Measured live: the segments sum to the bar width to within 0.01px on every
   one of the seven decks.

---

#### The headline, confirmed on a real screen

**`Prismatic Dragon` renders W 6 · U 12 · B 10 · R 7 · G 10 = 45 pips, ordered U > B ≈ G > R > W.**
The whole-string reading would have painted 71 pips led by black. Q1's measurement is not a table
in a story file any more; it is what the deck looks like.

#### Five corrections the record owed, all re-measured read-only at `1ed2e83`

1. **§A's three totals are a different population from the one that ships.** 2,608 / 2,547 / 2,595
   reproduce **exactly** — over *every deck row of the 40 real decks*, sideboard and lands
   included, which §A's own preamble says. What the bar draws (sideboard excluded per Q6, lands
   per Q4(e)) is **2,521 / 2,460 / 2,508**. Every per-deck figure §A quotes is unaffected and
   re-verified: 10 of 40 change, 2 re-order, `Prismatic Dragon` 71→45, `Abzan Dragons` 71→57,
   `Temur Dragonstorm v2` 48→41.
2. **§G's "21 of 21" counts `--mana-gold`, which does not ship.** Six colours give **15** adjacent
   pairs: **15 of 15 under 3:1, 8 under 1.3:1**, same worst (1.03:1) and best (2.30:1). The track
   measurement is exact as recorded — **6.62:1 to 15.20:1**.
3. **The largest live bar is 116 pips, not 114, and there are 5 five-colour decks, not 4.** 114 is
   the whole-string reading of `Ayara Black Devotion`; hydration adds the deck's own namesake and
   it renders **116, in one segment, at 100%** — verified live. The missed fifth deck is
   `MSH — The Mad Titan's Gauntlet — Five-Color Power-Up Snap`.
4. **Hybrid and Phyrexian pips are live in 10 decks, not 8.** The copy counts are exactly right
   (29 hybrid, 7 Phyrexian, 1 `{G/W/P}`) and identical under all four populations.
5. **A THIRD measurement-instrument defect, in the same family as §9's.** `deck_cards` holds 2,027
   rows but **28 of them (89 copies, 2 dead deck ids) have no `decks` row at all**. Only **1,999**
   belong to a live deck — the number `deckGroups.ts:230` already quotes. This is why §A's totals
   reproduce only with the join present.

**Confirmed exactly as written**: §9's `card_faces` correction (38,261 vs **3,225**; 35,036 rows
store the JSON *string* `'null'`); §10's (**27 live split-cost rows / 53 copies = 8 Adventure, 18
Omen, 1 neither**; **0 live rows where `cmc` ≠ the front face's mana value**); §C entirely (2,830 /
87.75%, 487 recoverable, 38 rows / 46 copies live, 34 recoverable, 12 Pathway lands, **+48 pips
across 16 of 40 decks**); §F entirely; §E's corpus census. One refinement to §B: the Adventure row
is **134 front + 1 neither**, not 135 — the odd card is `Keeper of the Crown // Coronation of the
Wilds`, whose `{2}{L}` carries a symbol `parse.ts` does not model.

**One measurement §A does not make, and it decides Q4(e) for free:** live pip totals are
**identical with and without the land filter** (2,608 either way). No land in any real deck carries
a coloured pip. That is a reason to write the policy down, not to leave it unstated — pinned with
two real corpus cards (`Glade of the Pump Spells`, and `Midgar, City of Mako // Reactor Raid`,
whose top-level cost is its Adventure half's `{2}{B}`).

#### The probe harness lied, and its own negative controls caught it — TWICE

**This is the sharpest thing in the story and it is a process finding, not a code one.** The first
harness reported all 19 mutations "CAUGHT" and both do-nothing negative controls RED. The controls
were not wrong: every one of the 57 test files was failing with `TypeError: Cannot read properties
of undefined (reading 'config')` and *"Vitest failed to find the current suite"* — **zero
assertions executed**, exit 1, `Tests  no tests`. Under that, every probe reads "caught" for free.

The rebuilt harness validated each run (a real `Tests N passed` line, no crash signature) and then
refused to score **20 of 21** probes. Diagnosed by bisecting the invocation rather than the guards:
**passing vitest a forward-slash `cwd` with a lowercase drive letter breaks its project-config
resolution.** Measured side by side in one command — `'c:/Users/…/ui'` exits 1 with zero tests,
`'C:\Users\…\ui'` runs 1,474 and exits 0.

With the native path, **19 of 19 mutations caught and both negative controls silent**, each named
by real tests:

| probe | what it plants | caught by |
|---|---|---|
| (a) | a container module missing from `CONTAINERS` | the coverage guard + the 19-entry pin |
| (b1) | `--radius-card` in this story's CSS | `CARD_SHAPED` half one |
| (b2) | a chrome radius in a `CARD_SHAPED` file | `CARD_SHAPED` half two (4 tests) |
| (c) | pips from the WHOLE `mana_cost` string | Q1's `Prismatic Dragon` pins (5 tests) |
| (d) | the hydration read removed | Q2's three hydration tests |
| (e) | the sideboard included | the board-policy test (6 tests) |
| (f) | the commander excluded | the board-policy test (4 tests) |
| (g) | lands included | Q4(e)'s two land pins + the empty case (6 tests) |
| (h) | a `--mana-*` through `border-color` | the FILL-property allowlist |
| (i) | a `--mana-*` from markup | the markup half + this panel's own test |
| (j) | a `--mana-*` token name built at runtime | the same pair |
| (k) | `--mana-gold` referenced | the new *"still has NO consumer"* assertion |
| (l) | `--type-numeric` without its companion | `findUnpairedNumericRole` |
| (m) | `aria-live` added | AC 26's test |
| (n) | an accessible name back on a segment | the `aria-hidden` test + the zero-roles test |
| (o) | an authored word outside `copy.ts` | the copy gate's file half (3 tests) |
| (p) | a `px` literal with no citation | the DESIGN.md citation guard |
| (q) | a hybrid credited to ONE colour | Q4(a)'s two pins + the ×4 quantity test |
| (r) | a plain `style={{ width }}` beside the new channel | `no-restricted-syntax`, per attribute |

`inline-style-violation.tsx` holds at exactly **2**; `custom-property-violation.tsx` moves **9 →
10**, and the tenth case is the new channel beside a plain `width` — the `MixedProperties` argument
restated against a second allowlist entry, which is when someone re-tests whether the negation
still applies per-property.

#### The eye-check — headless Chrome over CDP, against the live backend

Seven decks × two widths × both motion settings. Every number below is from a real layout engine.

| measurement | at 1440px | at UX-DR8's 1100px floor |
|---|---|---|
| the row | **870 × 168.48 px**, 2 children, `display: flex` | 530 px wide |
| each panel | **423 px** — exactly 1:1 with the curve | 253 px |
| the bar | **397 × 14 px**, `border-radius: 999px`, track `rgb(13,15,26)` = `--surface-well`, `overflow: hidden` | 227 × 14 px |
| segments vs bar | sum to the bar width **to within 0.01 px**, every deck | exact |
| **thinnest live segment** | **21.95 px** (`Atraxa Counter Cabinet`, 5 black of 94) | **12.92 px** |
| the hairline on it | **4.6 %** of its width | **7.7 %** |
| the legend | wraps to **2 rows** (4 colours) / **3 rows** (5) | **4** / **5** rows |
| row height when the legend wraps further | unchanged at 168.48 px in all seven decks | grows to **179.3–204.3 px**, and the curve grows with it |
| horizontal overflow | **none** (scrollWidth = clientWidth) | none |

**The hairline works exactly as designed and the adjacent-sibling selector is doing its job**: the
FIRST segment measures `border-left: 0px` and every subsequent one `1px rgb(13,15,26)` — the
pill's ends are the track, and they gain no notch.

**The three type roles, read live**: count `13px/500/18.2px` with `font-variant-numeric:
tabular-nums` at `--text-tertiary`; percentage `10px/400/13px` with `letter-spacing: 0.8px` and
`text-transform: uppercase` at `--text-tertiary`; colour name `14px/400/21px` at
`--text-secondary`. The legend pip renders **16.25 × 16.25 px**, filled, `aria-hidden="true"`.
*(The computed `font` SHORTHAND serialises to `""` on the count element — that is CSS refusing to
represent a non-initial `font-variant-numeric` in the shorthand, not a missing declaration, and
c4-8's shipped `.mana-curve-count` reads the same way. Measured both ways rather than assumed.)*

**Chrome's own accessibility tree**, on the 99-card deck: **exactly ONE banner** where jsdom
reports **five** (both measured, AC 28); two figures named `Mana curve chart` and **`Color
distribution chart`**; four regions (`Mana curve`, `Color distribution`, `Card detail`, `Deck
list`); and the legend exposed as `White · 19 pips · 22% · Blue · 23 pips · 26% · …` — the
accessible data path being literally the visible text.

**Zero Tab stops, zero roles, zero `aria-live`, and no `--mana-` anywhere in the markup**, on every
deck at both widths. **Reduced motion**: transition durations `0s`, animations `none`, and the
geometry byte-identical — because this panel ships no motion at all, so UX-DR42's inventory needs
no new row (AC 30).

#### Two honest limits on what shipped

- **Q14's non-summing percentages are not visible in any real deck.** All seven measured decks sum
  to exactly 100 %. The rounding case is real and pinned in `colours.test.ts` (three equal colours
  print `33 · 33 · 33`), but it is a derivation fact, not something the eye-check saw.
- **`{C}` and `{S}` are zero-live**, so the colourless segment and its `Colorless` label ship
  **untested against real data**. `colours.test.ts` is their only witness, and the module says so.

#### Registries, gates and the numbers

| | baseline `1ed2e83` | shipped |
|---|---:|---:|
| frontend tests / files | 1,408 / 55 | **1,474 / 57** |
| Python | 2,501 passed / 1 skipped | **2,501 / 1 — untouched** (Q16's decline) |
| tokens (both pins) | 69 | **69** — `color-bar`'s values resolve to `--surface-well`, a cited `14px` and `--radius-pill` |
| containers | 16 | **19** (+3; `frontFaceCost.ts` moved, not added) |
| primitives | 18 | **18** |
| copy modules | 10 | **11** |
| `MANA_DATA_INK` | 1 | **2 — the first joiner since c2-8** |
| `RUNTIME_CUSTOM_PROPERTIES` | 1 | **2** (`--colour-bar-share`, in both places per ruling 23) |
| `--mana-*` spent | 6 of 7 | **6 of 7** — gold declined, and now asserted |
| `CARD_SHAPED` | 4 | **4** |
| shipped-motion pin | 4 | **4** |
| bundle JS | `index-CQ4JkkIp.js` 220,130 B | **`index-D6NJThYj.js` 221,585 B** |
| bundle CSS | `index-BE0Fvpcl.css` 18,138 B | **`index-BqIKsEIE.css` 19,294 B** |
| font | 22,288 B | 22,288 B (unchanged) |
| jsdom phantom `banner` | 4 | **5** (Chrome: 1) |

**Both bundle assets changed, in bytes and in hash.** Everything — new modules, both rebuilt
assets, the hand-copied mirror — was `git add`ed **before** this record claimed a green run, because
the registry guards cannot see an untracked file (AC 44). The plugin mirror at
`plugin/server/src/companion/app/static/` was hand-copied and verified **sha256-identical per
file** across all four (AC 45); nothing checks it, and its named home stays the C4 retro.

**Ten gates green**: `npm run lint`, `format:check`, `npx tsc -b --force`, `npm test`,
`npm run build`; `uv run pytest`, `ruff check .`, `ruff format --check .`, `mypy src/`,
`mypy src/ --platform win32`.

#### A guard this story had to widen, found by moving a file

`shell.test.ts`'s type-only `src/api/` check filtered specifiers with `/(^|\/)\.\.\/\.\.\/api\//`
— **exactly two levels up**, which was true of every container while every container lived one
directory deep. Promoting `frontFaceCost.ts` to `src/containers/` makes its wire import
`'../api/schema'`, which that pattern does not match at all: the rule would have gone on running
over an **empty list** and passing by looking at nothing. Now depth-independent, with the predicate
shared by the guard and its probe and both spellings asserted. **A guard that quietly narrows when
a file MOVES is this epic's standing failure wearing a new costume.**

### File List

**New**

- `ui/src/containers/ColourDistribution/ColourDistribution.tsx`
- `ui/src/containers/ColourDistribution/ColourDistribution.css`
- `ui/src/containers/ColourDistribution/ColourDistribution.test.tsx`
- `ui/src/containers/ColourDistribution/colours.ts`
- `ui/src/containers/ColourDistribution/colours.test.ts`
- `ui/src/containers/ColourDistribution/copy.ts`

**Moved**

- `ui/src/containers/DeckList/frontFaceCost.ts` → `ui/src/containers/frontFaceCost.ts`
- `ui/src/containers/DeckList/frontFaceCost.test.ts` → `ui/src/containers/frontFaceCost.test.ts`

**Modified**

- `ui/src/App.tsx` · `ui/src/App.test.tsx`
- `ui/src/components/AnalysisRow/AnalysisRow.css` · `ui/src/components/AnalysisRow/AnalysisRow.tsx`
- `ui/src/components/ManaPip/ManaPip.tsx` (the `label`-prop prediction, corrected)
- `ui/src/containers/DeckList/DeckList.tsx` (the moved import)
- `ui/src/containers/ManaCurve/curve.ts` · `ui/src/containers/ManaCurve/curve.test.ts` (the
  re-homed parser, corrected)
- `ui/eslint.config.js` (the second named runtime channel)
- `ui/tests/shell.test.ts` · `ui/tests/copy-rules.test.ts` · `ui/tests/token-usage.test.ts` ·
  `ui/tests/lint-gates.test.ts`
- `ui/tests/fixtures/tsx/clean.tsx` · `ui/tests/fixtures/tsx/custom-property-violation.tsx`
- `ui/README.md`
- `_bmad-output/planning-artifacts/ux-designs/…/DESIGN.md` (the hairline + the front-face ruling)
- `_bmad-output/implementation-artifacts/deferred-work.md` (this story's dispositions)
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

**Built (committed)**

- `src/companion/app/static/index.html` + `assets/index-D6NJThYj.js` + `assets/index-BqIKsEIE.css`
- `plugin/server/src/companion/app/static/…` (the hand-copied mirror, sha256-verified per file)

### Change Log

| Date | Change |
|---|---|
| 2026-08-06 | Story contexted off `1ed2e83` → `ready-for-dev`. 46 ACs, 16 open questions, 9 inherited deferrals, 8 triggered residues, 19 don't-breaks. |
| 2026-08-06 | REVIEWED → `done`. Three-layer review, 25 raw → 22 triaged findings: 2 decisions (both ruled: the vacuous `groupOf` guard gets the file's only declared-synthetic fixture — no corpus Artifact Land carries a cost, so a real fixture cannot bite; AC 6/21's deck-level provenance ratified with the constants declared as recorded measurements), 10 patches applied same day (headline: the guard test this story designed was VACUOUS — both fixtures contribute zero pips under either land policy, with a comment asserting the opposite of its own `toEqual({})`; plus four AC 14 fabrications — `Lander Rizzi`'s invented cost, `Exude Toxin` existing in no corpus row, Sephiroth's invented back-face cost, `Pond Prophet`'s type line — each re-fixtured to verified-real rows: `Black Sun's Zenith`, `Birgi // Harnfel`, `Esper Sentinel`, `Heaven // Earth`; two new pins for `{S}` snow and the true-split subclass; the reactivity witness's `as never` narrowed to the card alone), 3 defers ledgered (global value-unconstrained channel allowlist; sub-hairline invisible segment; zero-total conflating colourless with unhydrated), 9 dismissed. Gates re-run green: 1,476 frontend / 57 files (+2 tests); patches test-only, bundle and mirror untouched. |
| 2026-08-06 | IMPLEMENTED → `review` on `feat/companion-c4-9-colour-distribution-panel`. All 16 questions ruled before any code; 13 as proposed, 3 stated deviations. `frontFaceCost.ts` PROMOTED to the containers root (two consumers); `.analysis-row:empty` closes c4-8's empty row with no `App.tsx` derivation; `--colour-bar-share` joins both allowlists carrying a RAW PIP COUNT, so `flex-grow` divides and no call site can. Five record corrections measured (§A's population, §G's 21-vs-15 pairs, the 116-pip largest bar, 10-not-8 hybrid decks, and 28 orphan `deck_cards` rows). Probe harness caught lying TWICE by its own negative controls — root cause: a forward-slash `cwd` breaks vitest's config resolution; rebuilt, then 19/19 caught and both controls silent. CDP eye-check over 7 decks × 2 widths × both motion settings. Ten gates green: 1,474 frontend / 57 files; Python 2,501/1 unchanged; tokens 69, containers 19, copy modules 11, `MANA_DATA_INK` 2, `RUNTIME_CUSTOM_PROPERTIES` 2, `--mana-*` 6 of 7. Bundle JS 221,585 B / CSS 19,294 B, both changed; mirror sha256-identical. |

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

2026-08-06: CODE-REVIEWED -> done. Three-layer review (Blind Hunter + Edge Case Hunter + Acceptance Auditor): 25 raw findings -> 22 triaged = 2 decisions (both RULED same day: the vacuous groupOf guard gets the file's ONLY declared-synthetic fixture -- all 25 corpus Artifact Lands are costless, so a real fixture contributes zero pips under EITHER policy and the guard shipped green through the exact defect it names, the c4-8 vacuous-pin class in this story's own designed guard; AC 6/21's deck-level provenance RATIFIED with the constants declared as recorded measurements the suite cannot re-derive) + 10 patches applied (FOUR AC 14 FABRICATIONS in the file whose header claims verbatim fixtures: Lander Rizzi's invented {2}{R} cost -- real row {X}{G}{G}/cmc 2/["G"]; Exude Toxin, a face name spelled as a standalone card existing in no corpus row -> Black Sun's Zenith; Sephiroth's invented {4}{B}{B} back face -- the real card's back is COSTLESS, so the front-face-only-when-back-costed scenario existed nowhere -> Birgi // Harnfel, verified both faces costed; Pond Prophet's Frog Cleric -> Frog Advisor; plus Atraxa's curly apostrophe + missing colors, the rendered helper's hardcoded colors: [] given a real-values param, the reactivity witness's as-never narrowed to the card alone so CardEntry drift fails tsc, and TWO NEW PINS: {S} snow through the unknown-token path, and Heaven // Earth pinning the front-face rule on the TRUE-split subclass every other ' // ' fixture missed) + 3 defers ledgered (the channel allowlist is global and value-unconstrained across files; a sub-0.24%-share segment paints only its own hairline; total===0 conflates genuinely-colourless with not-yet-hydrated and the panel materializes mid-sweep) + 9 dismissed. Auditor AC tally 42/46 implemented, 4 partial, 0 missing; mirror sha256-verified. Gates re-run green: 1,476 frontend / 57 files (+2 tests); patches TEST-ONLY, bundle and mirror untouched. Next: commit + PR into feat/companion-c4. Previously -- IMPLEMENTED -> review, on feat/companion-c4-9-colour-distribution-panel off 1ed2e83. The colour distribution panel: one bar, its segments and a legend, as the SECOND child of the row c4-8 built and left waiting. All 16 questions ruled before any code; 13 AS PROPOSED, 3 STATED DEVIATIONS. THE HEADLINE IS CONFIRMED ON A REAL SCREEN: Prismatic Dragon renders W 6 / U 12 / B 10 / R 7 / G 10 = 45 pips ordered U > B ~ G > R > W, where the whole-string reading would have painted 71 led by black. DEVIATION 1 -- Q2's cross-tree import MOVED the module instead: frontFaceCost.ts is promoted to src/containers/ on the shared-helper rule (filled.ts: "a helper shared by two components does not live inside one of them"), and the story's stated reason for asking is MEASURABLY FALSE -- CardTile.tsx already imports ../FlipControl/FlipControl and the roots guard admits ../X outright. isLand deliberately does NOT move: splitting one export out of curve.ts would separate it from the three-land-policies argument its own docstring makes. DEVIATION 2 -- Q10's row gate ships as CSS: `.analysis-row:empty { display: none }` closes c4-8's accepted empty row with NO gate in App.tsx, no total and no re-derivation of anything, which is what that finding actually asked for; flagged to c4-12 by name. DEVIATION 3 -- Q13's channel carries a RAW PIP COUNT, not a percentage, so flex-grow divides in the browser and AC 19's "no division by zero is possible" is true because there is NO DIVISION AT THE CALL SITE; measured live, segments sum to the bar width within 0.01px on all seven decks. THE PROBE HARNESS LIED AND ITS OWN NEGATIVE CONTROLS CAUGHT IT TWICE -- the first run reported 19/19 caught and both do-nothing controls RED; the controls were right, because all 57 files were dying with "Cannot read properties of undefined (reading 'config')" and ZERO assertions, under which every probe reads caught for free. Root cause bisected to the INVOCATION, not the guards: passing vitest a forward-slash cwd with a lowercase drive letter breaks its project-config resolution (measured side by side: 'c:/...' exits 1 with no tests, 'C:\...' runs 1,474 and exits 0). Rebuilt with per-run validation; then 19/19 caught, both controls silent, each named by real tests. Third instance in this epic of a harness caught by its controls -- ledgered, home the C4 retro. FIVE RECORD CORRECTIONS, all re-measured: (1) SS A's 2,608/2,547/2,595 reproduce EXACTLY but over every deck row incl. sideboard and lands -- what the bar draws is 2,521/2,460/2,508; (2) SS G's "21 of 21 pairs" counts --mana-gold, which does not ship -- six colours give 15 of 15 under 3:1 and 8 under 1.3:1, same worst 1.03:1 and best 2.30:1, track 6.62:1-15.20:1 exact; (3) the largest live bar is 116 pips not 114 (hydration adds Ayara's own namesake) and there are 5 five-colour decks not 4; (4) hybrid and Phyrexian pips are live in 10 decks not 8 (29+7 copies exact); (5) A THIRD MEASUREMENT-INSTRUMENT DEFECT beside the card_faces one -- deck_cards holds 2,027 rows but 28 (89 copies, 2 dead deck ids) have NO decks row, so only 1,999 are live, which is why SS A only reproduces with the join. Confirmed exactly as written: card_faces IS NOT NULL matches all 38,261 (json_type array = 3,225); 27 live split-cost rows = 8 Adventure / 18 Omen / 1 neither with 0 cmc divergences; hydration +48 pips across 16 of 40 decks. Q4(e) is FREE on live data -- pip totals identical with and without the land filter -- pinned anyway with two real corpus cards. FIRST MANA_DATA_INK JOINER SINCE c2-8 (both invitations now answered, opposite ways); --mana-gold DECLINED with the absence ASSERTED and ui/README.md's prediction corrected; ManaPip's label prop ships with NO caller and its docstring corrected; curve.ts and curve.test.ts corrected to stop naming c4-9 for a parser it declined. A GUARD WIDENED BY THE FILE MOVE: shell.test.ts's type-only src/api/ filter matched exactly two levels up, so the promoted module would have run the rule over an EMPTY list -- now depth-independent, predicate shared with its probe. EYE-CHECK over CDP, 7 decks x 2 widths x both motion settings: row 870x168.48px with two 423px panels exactly 1:1, bar 397x14px at radius 999px on surface-well, segments summing to the bar within 0.01px, hairline 0px on the FIRST segment and 1px surface-well on every other, thinnest live segment 21.95px at 1440 and 12.92px at the 1100 floor (hairline 4.6%/7.7% of it), legend wrapping 2-3 rows at 423px and 4-5 at 253px with the row growing 168->179-204px there and the curve growing with it, zero Tab stops / roles / aria-live, no --mana- in markup, reduced motion 0s with identical geometry, and Chrome's OWN tree reporting EXACTLY ONE banner where jsdom says FIVE, two named figures and the legend exposed as its visible text. Two honest limits: no real deck exercises Q14's non-summing percentages (all seven sum to 100), and {C}/{S} are zero-live so the colourless segment ships untested against real data. 1,474 frontend / 57 files; Python 2,501/1 UNCHANGED (Q16 declined, five-axis divergence ledgered with a deck count beside each axis); tokens 69 (neither pin moved), containers 16 -> 19, copy modules 10 -> 11, MANA_DATA_INK 1 -> 2, RUNTIME_CUSTOM_PROPERTIES 1 -> 2, --mana-* 6 of 7, CARD_SHAPED 4, shipped-motion pin 4. Bundle JS 220,130 -> 221,585 B and CSS 18,138 -> 19,294 B, BOTH changed; mirror hand-copied sha256-identical per file. deferred-work.md written IN THIS COMMIT: all 9 inherited deferrals, all 8 triggered residues, 4 new entries. Ten gates green. Next: three-layer code review. Previously -- contexted 2026-08-06 off 1ed2e83; the colour distribution panel, and the second child of the row c4-8 built and left waiting. HEADLINE is a measurement that changes a real deck today: "proportional to pip count" (UX-DR18) resolves two ways and nothing says which — counting the WHOLE mana_cost string counts both halves of a split/Adventure/Omen cost, counting the FRONT FACE counts what you pay for what you cast. 10 OF 40 DECKS CHANGE, 2 CHANGE SEGMENT ORDER; Prismatic Dragon falls 71 -> 45 pips (37%) and re-orders, Abzan Dragons loses 20% with black falling 37% -> 30% of the bar. The cause is the current-Standard TDM Omen cycle. Second: this panel WALKS BACK INTO THE HYDRATION WINDOW c4-8 was the first in four to escape — 87.75% of faced cards have a blank top-level mana_cost, hydration is worth +48 pips across 16 of 40 decks, and 34 of the 46 live blank-cost copies are recoverable (the other 12 are Pathway lands that correctly contribute nothing), so this is the epic's first panel whose PERCENTAGES MOVE AFTER FIRST PAINT and "no aria-live" becomes load-bearing. Third, invisible from the ACs: the obvious reuse does not compile — DeckList reads the cache with one useCardEntry per ROW COMPONENT, and one component aggregating 99 rows cannot; readCardEntry is not reactive and would leave the bar silently stale. Fourth: the accessibility shape INVERTS c4-8's — the bar is aria-hidden and the LEGEND is the data path, so no visually-hidden block ships and the third-instance promotion trigger does not fire. Fifth, measured against the shipped hexes for the first time (the only prior measurement is in a SUPERSEDED pre-Voltglass review): ALL 21 adjacent --mana-* pairs are under 3:1, worst 1.03:1, best 2.30:1 — but every segment clears the --surface-well track at >=6.62:1, so a 1px track-coloured hairline turns 21 failures into 21 passes with one declaration and no new token. Sixth: hybrid and Phyrexian pips are LIVE (29 + 7 copies across 8 decks, including one {G/W/P}) and Python's compute_pip_signals counts BARE PIPS ONLY — a fourth two-surfaces divergence, across five axes. First MANA_DATA_INK joiner since c2-8. Two corrections owed: `card_faces IS NOT NULL` matches all 38,261 rows (the coverage-that-reads-as-coverage failure, in the measurement instrument), and c4-8's "all 27 live split-cost rows are Adventures" is really 8 Adventure / 18 Omen / 1 neither — its ruling survives, its reason does not. 46 ACs, 16 open questions, 9 inherited deferrals, 8 triggered residues, 19 don't-breaks.
