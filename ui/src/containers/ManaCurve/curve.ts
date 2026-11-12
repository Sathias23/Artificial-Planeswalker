import type { DeckStatistics } from '../../api/schema'

/**
 * The mana curve's bars, drawn from the deck payload's `statistics.curve` (FR-05, UX-DR17).
 *
 * Its own module rather than a helper inside `ManaCurve.tsx`, for the settled reason:
 * `react-refresh/only-export-components` is an ESLint **error**, so a function exported beside a
 * component turns the gate red. `imageUrl.ts`, `deckMemory.ts`, `imagedFaces.ts`, `useCardArt.ts`
 * and `frontFaceCost.ts` are the precedents.
 *
 * ================= THE COUNTS ARE THE SERVER'S, NOT THIS FILE'S =========================
 *
 * This file decides **no** card rule. Which cards are lands, which bucket a mana value falls in,
 * and which boards count are all decided once, in Python, by `src/logic/card_statistics.py`, and
 * arrive as `DeckStatistics.curve` on `GET /api/deck/{deck_id}`. The agent's
 * `analyze_mana_curve` reports its `distribution` from the same function, so the panel and the
 * tool give the same seven numbers for the same deck. That is tested rather than claimed:
 * `tests/integration/mcp_server/test_card_statistics_parity.py` compares the tool, the payload and
 * the committed `src/test-fixtures/deck-statistics.json`, and `ManaCurve.test.tsx` renders that
 * same file and reads the bars back.
 *
 * In short, as the server applies them: a card is a land when its FRONT face's type half names
 * `Land`; mana values round half up, `0` and `1` share the first bar, and the last bar is `7` or
 * more; the commander counts and the sideboard does not. A true split card's `cmc` is Scryfall's
 * sum of both halves, so it buckets by that sum on both sides alike.
 *
 * What is left here is presentation: pairing each count with its bucket, and the scale the bar
 * heights are drawn against.
 */

/**
 * The buckets, in ascending order — UX-DR17 and `DESIGN.md:407`, verbatim: *"Buckets are 1 … 7+"*.
 *
 * A `readonly` tuple rather than a number: the seven-entry shape is closed, and the server's
 * `DeckStatistics['curve']` is a seven-tuple of the same length. `curve.test.ts` ties the two
 * together in the type and at runtime, so an eighth bucket on one side goes red on the other.
 */
export const BUCKETS = [1, 2, 3, 4, 5, 6, 7] as const

export type Bucket = (typeof BUCKETS)[number]

/** The open-ended bucket: the server folds every mana value at or above it into this bar. */
export const LAST_BUCKET: Bucket = 7

/** One bar's worth of the answer. */
export interface CurveBucket {
  /** The mana value this bar stands for. The last one means "this or more". */
  readonly bucket: Bucket
  /** The SUMMED QUANTITY in this bucket, never a row count. */
  readonly count: number
  /**
   * {@link count} as a fraction of the TALLEST bucket, in `0…1` — the number the bar's height
   * is drawn from. Scaled to the tallest bar rather than to the deck size, which is the one
   * thing the composition reference supplies that no artefact does; `0` when the curve is empty,
   * never `NaN`.
   */
  readonly share: number
}

/** The whole curve: seven bars, their total, and the scale they were drawn against. */
export interface CurveBuckets {
  readonly buckets: readonly [
    CurveBucket,
    CurveBucket,
    CurveBucket,
    CurveBucket,
    CurveBucket,
    CurveBucket,
    CurveBucket,
  ]
  /** Every bucket summed — the number the panel's hide condition tests. */
  readonly total: number
  /** The tallest bucket's count, floored at 1 so nothing divides by zero. */
  readonly tallest: number
}

/** A position in the seven-tuple: what lets each bar be built without widening to `number[]`. */
type BucketIndex = 0 | 1 | 2 | 3 | 4 | 5 | 6

/**
 * The bars for a deck's curve.
 *
 * Called in render with no `useMemo`: it is seven additions and a `Math.max`, and the memo's
 * dependency would be a payload object whose identity the deck slice owns.
 *
 * The seven bars are built position by position, so the result is the seven-tuple
 * {@link CurveBuckets} declares with no cast. That {@link BUCKETS} and the server's tuple have the
 * same length is `curve.test.ts`'s job, in the type and at runtime.
 *
 * Args:
 *   curve: `statistics.curve` from the deck payload, verbatim — the count per bucket, in
 *     {@link BUCKETS} order.
 *
 * Returns:
 *   Seven buckets in ascending order, with the total and the scale.
 */
export const curveOf = (curve: DeckStatistics['curve']): CurveBuckets => {
  const total = curve.reduce((sum, count) => sum + count, 0)
  // `Math.max(1, …)` is the divide-by-zero guard: a land-only deck is an all-zero curve with
  // cards in it.
  const tallest = Math.max(1, ...curve)
  const bar = (index: BucketIndex): CurveBucket => ({
    bucket: BUCKETS[index],
    count: curve[index],
    // Guarded on `total` rather than on `tallest`: with `tallest` floored at 1 an empty curve
    // would otherwise produce seven honest-looking `0`s from a scale that describes nothing.
    share: total === 0 ? 0 : curve[index] / tallest,
  })

  return { buckets: [bar(0), bar(1), bar(2), bar(3), bar(4), bar(5), bar(6)], total, tallest }
}
