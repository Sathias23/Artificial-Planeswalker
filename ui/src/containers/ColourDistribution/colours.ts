import { MANA_COLOUR_ORDER, parseManaCost } from '../../components/ManaCost/parse'
import type { ManaColour } from '../../components/ManaCost/parse'
import type { CardEntry } from '../../state/cards'
import type { DeckBoards } from '../../state/deckGroups'
import { isLand } from '../ManaCurve/curve'
import { frontFaceCost } from '../frontFaceCost'

/**
 * The deck's colour balance, as pip counts (FR-05, UX-DR18).
 *
 * Its own module rather than a helper inside `ColourDistribution.tsx`:
 * `react-refresh/only-export-components` is an ESLint **error**, so a function exported beside a
 * component turns the gate red. `imageUrl.ts`, `deckMemory.ts`, `imagedFaces.ts`, `useCardArt.ts`,
 * `frontFaceCost.ts` and `curve.ts` have the same shape for the same reason.
 *
 * ================= "PROPORTIONAL TO PIP COUNT" RESOLVES TWO WAYS =======================
 *
 * UX-DR18 says *"segmented by `mana-*` proportional to **pip count** across the deck"* and stops.
 * A split, Adventure or Omen card's `mana_cost` is `'{3}{B} // {1}{B}'`: counting the **whole
 * string** counts both halves, counting the **front face** counts what you pay to cast the thing
 * you cast. Neither reading is written down anywhere, and they are not a rounding apart.
 *
 * Measured against the shipped database, keyed on deck **id**:
 *
 *   | measurement                                   | result                                 |
 *   |-----------------------------------------------|----------------------------------------|
 *   | decks whose pip total changes                 | **10 of 40**                           |
 *   | decks whose segment ORDER changes             | **2** — `Prismatic Dragon`, `Temur Dragonstorm` |
 *   | worst deck                                    | `Prismatic Dragon` **71 → 45** (−37%)  |
 *   | second                                        | `Abzan Dragons` **71 → 57**; black falls 37% → 30% of the bar |
 *
 * **The front face is deliberate.** Three reasons, in order of weight. (a) It is the reading
 * every other surface in the app already uses — `deckGroups.ts` groups by front face, `curve.ts`
 * buckets by front face, `frontFaceCost.ts` draws the front face's pips in the deck row, and
 * UX-DR17/FR-05 say "front face" in writing; a bar counting both halves would be **the only
 * surface in the app that does not**. (b) The panel's question is *"does my mana base match my
 * spells"*, and the back half of an Omen is a cost you pay separately or never. (c) The bar and
 * the deck list then agree BY CONSTRUCTION — the same *"the grid and the list panel cannot
 * disagree"* rule, one layer out. The cause is the current-Standard **TDM Omen dragon cycle**,
 * sitting in four live decks.
 *
 * **The cost, stated plainly: the back half of an Omen is invisible on this panel.**
 *
 * The boundary is not re-found here. {@link frontFaceCost} already splits on `' // '` in both the
 * declared and the hydrated branch, so the string this module tokenises never contains one.
 *
 * ================= AND THAT MEANS THIS PANEL DEPENDS ON HYDRATION ======================
 *
 * `cmc` rides on `CardSummary`, which is why the mana curve needs nothing from the sweep. A pip
 * count does not: **2,830 of 3,225 faced cards (87.75%) carry a blank top-level
 * `mana_cost`** whose real value lives only in `card_faces[0]`. Live that is **38 rows / 46
 * copies**, of which **34 copies are recoverable** and the other **12 are Pathway MDFC lands that
 * correctly contribute nothing** — so on real data hydration is *complete*: after the sweep no
 * deck has an unknown pip. It is worth **+48 pips across 16 of 40 decks** (B 23 · G 10 · U 6 ·
 * R 5 · W 4).
 *
 * So **this panel's PERCENTAGES MOVE AFTER FIRST PAINT**, and two things follow:
 *
 *   1. **The sweep is not re-driven from here.** The edge-triggered hydration recovery only
 *      re-boots from `refused`/`none`, so a backend blip *during* the sweep leaves those pips
 *      permanently missing with no error state. That is the deliberate posture, not a hole this
 *      panel papers over with a retry it does not own.
 *   2. **No `aria-live`, anywhere.** A percentage that re-announced through ~99 hydrations is the
 *      exact flood UX-DR45 bans, and it is louder than a pip appearing in a deck row.
 *
 * ================= WHAT ONE SYMBOL CONTRIBUTES ========================================
 *
 * Live exposure, measured: **29 hybrid pip copies and 7 Phyrexian across 10 decks**, including
 * one `{G/W/P}` that is both at once. `{C}`, `{S}` and the generic-hybrid `{2/C}` are **zero
 * live**. Python's `compute_pip_signals` counts **bare pips only**, so every one of these counts
 * for nobody there — see the note on the Python divergence below.
 *
 *   - **A hybrid credits EVERY colour it can be paid with.** `{W/U}` adds one white *and* one
 *     blue. The bar is a proportional graphic, not a conservation identity: a `{W/U}` card
 *     genuinely demands white **or** blue sources, so crediting neither under-reports a real
 *     demand and crediting a half invents a precision the data does not have. ⚠️ **The total
 *     therefore EXCEEDS the symbol count**, and the legend's percentages are of that total —
 *     stated here because a reader who adds the counts and gets more than the symbols would
 *     otherwise file a bug.
 *   - **Phyrexian is a modifier, never a third colour** (`parse.ts:55`). `{U/P}` is one blue pip;
 *     life is not a colour.
 *   - **A generic-hybrid credits its colour only.** `{2/R}` is red, and `parse.ts` already
 *     encodes that by putting `2` in `glyph` and `r` in `colours`.
 *   - **Generic and `{X}` count for nobody.** `colours: []` is the whole test, and no
 *     "colourless" segment is invented for them — `{C}` is colourless, `{2}` is nothing. An
 *     `unknown` token needs no special case either: it has no `colours` field at all.
 *   - **`{C}` IS a colour here**, and `--mana-colorless` is a real token. ⚠️ Zero `{C}` symbols
 *     appear in any of the 40 real decks, so a colourless segment ships **untested against real
 *     data** and `colours.test.ts` is its only witness.
 *
 * ================= LANDS ARE EXCLUDED, AND THE POLICY IS THE THIRD ONE =================
 *
 * UX-DR18 has no land clause. The panel's stated question is *"does my mana base match my
 * **spells**"*, and a land that taps for mana is a **source**, not a demand — so lands are
 * excluded, reusing {@link isLand}: the whole-**word** test on the **front face**, after
 * stripping at the em-dash. Not `groupOf(t) === 'Land'`, which files `Artifact Land` under
 * Artifact and would count 25 corpus lands as spells; not Python's whole-string
 * `'land' in type_line.lower()`, which is policy A. `curve.ts:74-123` documents all three.
 *
 * **Measured: live pip totals are IDENTICAL with and without the land filter** — 2,608 either way
 * over every row of the 40 real decks. No land in any real deck carries a coloured pip, so this
 * costs nothing today. That is a reason to write the policy down, not a reason to leave it
 * unstated: `Glade of the Pump Spells` (`{2}{G}`, type line `Land`) is one `add_card_to_deck`
 * away, and `Midgar, City of Mako // Reactor Raid` is a `Land — Town` whose top-level cost is its
 * Adventure half's `{2}{B}`.
 *
 * ================= WHICH BOARDS ======================================================
 *
 * **Commander + mainboard; the sideboard is excluded** — the same partition the mana curve uses,
 * and the sideboard half is already written in shipped source: `deckGroups.ts:197` says *"the
 * sideboard is not part of the deck **the curve and colour panels** describe"*, naming this panel
 * by function. `src/mcp_server/tools/deck_analysis.py:171-173` makes the same partition, so the
 * panel and the MCP tool cannot answer the same question differently. The policy is expressed by
 * WHICH BOARDS THIS READS rather than by a second `filter` over `sideboard` (AD-12). Live cost of
 * the sideboard half: **87 pips across 5 decks** that do not reach the bar.
 *
 * ================= WHAT THIS DELIBERATELY DOES NOT DO =================================
 *
 * **No numeric mana-value parser.** A pip counter walks {@link ManaColour} lists and **never adds
 * a generic cost**, so nothing in this file converts a cost string to a number. Writing one
 * anyway — to fix a `cmc` divergence with **0 live exposure** — is scope this panel cannot
 * justify; the honest home is whatever surface first needs a mana value.
 *
 * **No second cost scanner.** `parseManaCost` is reused verbatim and `MANA_COLOUR_ORDER` is not
 * copied — it is exported *because* it is a checkable datum (`parse.ts:39-43`), and a fourth
 * private copy would be the fourth way for the ordering to disagree.
 *
 * **The Python is not changed, and the divergence is known.** `compute_pip_signals`
 * (`mana_base.py:343-390`) feeds `_mana_efficiency_score` and thence `assess_deck_power`, whose
 * calibration benchmark set is a frozen artefact. It differs from this file on **five axes at
 * once**: hybrids (29 live copies / 10 decks), Phyrexian (7 / 10), generic-hybrids (0 live), the
 * sideboard (87 pips / 5 decks, included there) and split cards (27 rows / 53 copies). A deck
 * count sits beside each because a bare number is not checkable when three tests all sound like
 * the same policy.
 */

/** One colour's share of the bar. Emitted only when {@link count} is non-zero. */
export interface ColourSegment {
  /** The colour, from `parse.ts`'s own six-member vocabulary. */
  readonly colour: ManaColour
  /**
   * The SUMMED QUANTITY of pips of this colour, never a row count. A ×4 row of
   * `{G/U}{G/U}` contributes **8** green and **8** blue.
   */
  readonly count: number
  /**
   * {@link count} as a whole-number percentage of {@link ColourDistribution.total}.
   *
   * ⚠️ **THE DISPLAYED PERCENTAGES NEED NOT SUM TO 100**, and that is deliberate rather than an
   * oversight. Three equal colours print `33% · 33% · 33%`. The alternative — a
   * largest-remainder correction that forces 100 — makes one colour's printed number disagree
   * with its own count, which is worse: the count is on screen right beside it.
   *
   * The **geometry** is not this number. A segment's width is its `count` handed to `flex-grow`,
   * so the browser divides and the segments always fill the bar exactly.
   *
   * A non-zero count that rounds to `0` prints `0%` **honestly** rather than flooring to `1%`,
   * for the same reason: the count beside it is the un-rounded truth either way. Not producible
   * from live data — the thinnest live share is 1 of 26 (3.8%).
   */
  readonly percent: number
}

/** The whole bar: its segments in WUBRG order, and the total they are shares of. */
export interface ColourDistribution {
  /**
   * The segments, in {@link MANA_COLOUR_ORDER} — **WUBRG with colourless last**, never sorted by
   * count. A stable order is what lets two decks be compared at a glance, and it is the order
   * `DESIGN.md:407` writes for the curve's hypothetical stacking. Colours with no pips are
   * **omitted entirely**: the legend lists what the deck has, not six rows of which four say
   * nothing.
   */
  readonly segments: readonly ColourSegment[]
  /**
   * Every segment summed — the number the panel's single branch tests, and the denominator the
   * percentages are of. `0` for a deck with no coloured pips, which is the state that renders
   * nothing at all rather than an empty bar.
   */
  readonly total: number
}

/**
 * The colour distribution for a deck.
 *
 * ================= DERIVED IN RENDER, NOT MEMOISED — AND THE PRICE IS DIFFERENT ========
 *
 * Called in render with no `useMemo`, the same shape as `curveOf`, and for the same two reasons:
 * a memo is a cache, and the memo's dependency would be `boards`, whose REFERENCE IDENTITY is the
 * deck's identity for `deckMemory.ts:8-9` and `CardDetail.tsx:333-336`.
 *
 * **But this one runs more often than `curveOf`.** `curveOf` runs once per deck change; this one
 * also runs once per **hydration**, because the panel subscribes to the whole cache map — ~99
 * renders on the 99-card deck during a cold-open sweep — and it parses ~99 cost strings rather
 * than reducing ~99 numbers.
 *
 * **Measured rather than asserted** (mean of 20,000 calls over a 99-row board, V8 warm, both
 * functions in the same run): `coloursOf` **~48 µs/call** against `curveOf`'s **~21 µs** — the
 * ~2.3× the extra tokenising predicts, and within a µs or two of `curveOf`'s previously recorded
 * 24 µs. A single warm call reads ~70 µs. So the **whole cold-open sweep costs ~4.8 ms of
 * derivation in total** (99 renders × 48 µs), which is why there is no `useMemo`: a memo would
 * have to beat that to earn the `boards`-identity hazard, and it cannot.
 *
 * This is a different AXIS over the same partition (colour, rather than board and type), not a
 * second partition, so AD-12's ban on re-deriving what `boardsOf` computed is not engaged:
 * nothing here filters, sorts or regroups cards, and `boards` is read rather than copied.
 *
 * Args:
 *   boards: `surfaceOf`'s answer for a loaded deck, verbatim — the same value `CardGrid`,
 *     `DeckList` and `ManaCurve` receive.
 *   cards: The hydration cache's whole map, from ONE `useCardStore` subscription. Passed as
 *     an argument rather than read here, because this module is pure and a hook in a loop over a
 *     deck whose length changes is the rules-of-hooks violation React actually breaks on. **This
 *     function starts nothing**: it reads what the sweep has already put there.
 *
 * Returns:
 *   The segments in WUBRG order and their total.
 */
export const coloursOf = (
  boards: DeckBoards,
  cards: Readonly<Record<string, CardEntry>>,
): ColourDistribution => {
  const counts = new Map<ManaColour, number>(MANA_COLOUR_ORDER.map((colour) => [colour, 0]))

  // The commander board and the mainboard's groups; the sideboard is simply not read.
  // `boards.mainboard` is already `TYPE_GROUPS`-ordered and this ignores that order entirely —
  // the bar's axis is colour, and a group is only a container to walk through.
  const rows = [...boards.commander, ...boards.mainboard.flatMap((group) => [...group.cards])]

  for (const entry of rows) {
    if (isLand(entry.card.type_line)) continue
    // The three shapes, already solved: split first, then a real top-level cost, then the
    // hydrated `card_faces[0]`, then `null` — which `parseManaCost` accepts and answers `[]` to,
    // so an unhydrated blank-cost card needs no branch here.
    for (const token of parseManaCost(frontFaceCost(entry.card, cards[entry.card_id]))) {
      if (token.kind !== 'symbol') continue
      // EVERY colour the symbol carries: one for a plain pip, two for a hybrid, and none at all
      // for generic and `{X}`. `+ entry.quantity`, never `+ 1`.
      for (const colour of token.colours) {
        counts.set(colour, (counts.get(colour) ?? 0) + entry.quantity)
      }
    }
  }

  const total = [...counts.values()].reduce((sum, count) => sum + count, 0)

  // Filtered BEFORE the percentage is taken, so the division never runs against a zero total: a
  // deck with no coloured pips emits no segments at all, and the panel's own branch hides it.
  const segments = MANA_COLOUR_ORDER.filter((colour) => (counts.get(colour) ?? 0) > 0).map(
    (colour) => {
      const count = counts.get(colour) ?? 0
      return { colour, count, percent: Math.round((count / total) * 100) }
    },
  )

  return { segments, total }
}
