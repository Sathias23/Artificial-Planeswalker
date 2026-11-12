import { MANA_COLOUR_ORDER } from '../../components/ManaCost/parse'
import type { ManaColour } from '../../components/ManaCost/parse'
import type { DeckStatistics } from '../../api/schema'

/**
 * The colour bar's segments, drawn from the deck payload's `statistics.colour_pips` (FR-05,
 * UX-DR18).
 *
 * Its own module rather than a helper inside `ColourDistribution.tsx`:
 * `react-refresh/only-export-components` is an ESLint **error**, so a function exported beside a
 * component turns the gate red. `imageUrl.ts`, `deckMemory.ts`, `imagedFaces.ts`, `useCardArt.ts`,
 * `frontFaceCost.ts` and `curve.ts` have the same shape for the same reason.
 *
 * ================= THE PIP COUNTS ARE THE SERVER'S, NOT THIS FILE'S =====================
 *
 * This file decides **no** card rule. Which cards are lands, which face's cost is read, what one
 * symbol credits and which boards count are decided once, in Python, by
 * `src/logic/card_statistics.py`, and arrive as `DeckStatistics.colour_pips` on
 * `GET /api/deck/{deck_id}`. The agent's `analyze_mana_curve` reports its `colour_pips` from the
 * same function, so the bar and the tool give the same counts for the same deck. That is tested
 * rather than claimed: `tests/integration/mcp_server/test_card_statistics_parity.py` compares the
 * tool, the payload and the committed `src/test-fixtures/deck-statistics.json`, and
 * `ColourDistribution.test.tsx` renders that same file and reads the legend back.
 *
 * In short, as the server applies them — they are `parse.ts`'s own symbol rules: pips come from
 * the FRONT face's cost (an Omen's or Adventure's back half is a separate cast and is not
 * counted); lands are excluded by the front-face test; a hybrid credits EVERY colour it can be
 * paid with, so ⚠️ **the total can exceed the symbol count** and the legend's percentages are of
 * that total; Phyrexian is a modifier, never a colour; a generic-hybrid `{2/R}` credits its
 * colour; generic and `{X}` credit nothing; `{C}` is colourless, a real segment; the commander
 * counts and the sideboard does not.
 *
 * **Complete at first paint.** The counts ride on the deck payload, so this panel no longer reads
 * the card cache and no longer moves as the hydration sweep lands.
 *
 * What is left here is presentation: dropping the empty colours, ordering the rest, and the
 * rounded percentage each one prints.
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
   * for the same reason: the count beside it is the un-rounded truth either way.
   */
  readonly percent: number
}

/** The whole bar: its segments in WUBRG order, and the total they are shares of. */
export interface ColourDistribution {
  /**
   * The segments, in {@link MANA_COLOUR_ORDER} — **WUBRG with colourless last**, never sorted by
   * count. A stable order is what lets two decks be compared at a glance. Colours with no pips are
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
 * The wire's uppercase colour letters mapped onto `parse.ts`'s lowercase vocabulary.
 *
 * A `Record` over the generated union rather than a `toLowerCase()` cast, so a seventh letter the
 * server added would be a type error here rather than a key no segment is drawn for.
 */
const WIRE_COLOURS: Record<DeckStatistics['colour_pips'][number]['colour'], ManaColour> = {
  W: 'w',
  U: 'u',
  B: 'b',
  R: 'r',
  G: 'g',
  C: 'c',
}

/**
 * The segments for a deck's colour pips.
 *
 * Called in render with no `useMemo`: it is six lookups and a filter, over a payload object whose
 * identity the deck slice owns.
 *
 * Args:
 *   pips: `statistics.colour_pips` from the deck payload, verbatim — one `{colour, count}` per
 *     colour, uppercase (`'W'`), zeros kept. Read by colour, so the wire's order is not relied on.
 *
 * Returns:
 *   The non-empty segments in WUBRG order, colourless last, and their total.
 */
export const segmentsOf = (pips: DeckStatistics['colour_pips']): ColourDistribution => {
  const counts = new Map<ManaColour, number>(MANA_COLOUR_ORDER.map((colour) => [colour, 0]))
  for (const { colour, count } of pips) {
    const key = WIRE_COLOURS[colour]
    counts.set(key, (counts.get(key) ?? 0) + count)
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
