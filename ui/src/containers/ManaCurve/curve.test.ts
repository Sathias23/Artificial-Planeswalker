/**
 * The curve's bars, built from the server's seven counts.
 *
 * The card RULES — which cards are lands, which bucket a mana value falls in, which boards count —
 * moved to Python with the counts themselves: `tests/unit/logic/test_card_statistics.py` holds
 * every case this file used to (the MDFC lands, the Landers, the 0-drop and the 12-drop, the
 * commander and the sideboard). What is left to test here is presentation: pairing each count
 * with its bucket, the total, the scale, and that the seven-entry shape on this side is the
 * seven-entry shape the server sends.
 */

import { describe, expect, expectTypeOf, it } from 'vitest'

import type { DeckStatistics } from '../../api/schema'
import { BUCKETS, LAST_BUCKET, curveOf } from './curve'

type Curve = DeckStatistics['curve']

const countsOf = (curve: Curve) => curveOf(curve).buckets.map((b) => b.count)

/** The committed verify-deck figures, the file the Python parity test holds the server to. */
const FIXTURE = Object.values(
  import.meta.glob<{ statistics: DeckStatistics }>('../../test-fixtures/deck-statistics.json', {
    eager: true,
    import: 'default',
  }),
)[0]

describe('the buckets are 1 … 7+, and there are seven of them', () => {
  it('names them in ascending order with the last one open-ended', () => {
    expect(BUCKETS).toEqual([1, 2, 3, 4, 5, 6, 7])
    expect(LAST_BUCKET).toBe(7)
  })

  it('has exactly as many buckets as the server sends counts — in the TYPE', () => {
    // Erased at runtime: `npm run typecheck` is the gate for this one (see `schema.test.ts`). An
    // eighth `BUCKETS` entry, or a server tuple that grew without it, is TS2344 here.
    expectTypeOf<Curve['length']>().toEqualTypeOf<(typeof BUCKETS)['length']>()
  })

  it('has exactly as many buckets as the server sends counts — at RUNTIME', () => {
    // The runtime half of the tie, against a real payload's curve rather than the type, so a
    // generated type that fell back to `number[]` would still be caught here.
    expect(FIXTURE).toBeDefined()
    expect(FIXTURE.statistics.curve).toHaveLength(BUCKETS.length)
    expect(curveOf(FIXTURE.statistics.curve).buckets).toHaveLength(BUCKETS.length)
  })
})

describe('each count is paired with its bucket, in order', () => {
  it('pairs the server’s counts with 1 … 7 verbatim', () => {
    const curve = curveOf([2, 5, 0, 1, 0, 0, 3])
    expect(curve.buckets.map((b) => b.bucket)).toEqual([...BUCKETS])
    expect(countsOf([2, 5, 0, 1, 0, 0, 3])).toEqual([2, 5, 0, 1, 0, 0, 3])
  })

  it('keeps every zero — an empty bucket is a bar, not a gap', () => {
    expect(countsOf([0, 0, 0, 4, 0, 0, 0])).toEqual([0, 0, 0, 4, 0, 0, 0])
  })
})

describe('the totals and the scale', () => {
  it('reports the total and the tallest bucket', () => {
    const curve = curveOf([2, 5, 0, 0, 0, 0, 0])
    expect(curve.total).toBe(7)
    expect(curve.tallest).toBe(5)
  })

  it('never reports a tallest below 1, so nothing divides by zero', () => {
    // A deck of nothing but lands is an all-zero curve with cards in it.
    const empty = curveOf([0, 0, 0, 0, 0, 0, 0])
    expect(empty.tallest).toBe(1)
    expect(empty.total).toBe(0)
  })

  it('scales each bucket against the TALLEST bar, not against the deck size', () => {
    // The 39-versus-0 extreme is real data: `Infinite Guideline Station v2 (owned)` puts 39
    // cards in bucket 2 beside two buckets that are empty.
    const curve = curveOf([0, 39, 13, 0, 0, 0, 0])
    expect(curve.buckets.map((b) => b.share)).toEqual([0, 1, 1 / 3, 0, 0, 0, 0])
  })

  it('gives every bucket a zero share when the curve is empty, rather than NaN', () => {
    const curve = curveOf([0, 0, 0, 0, 0, 0, 0])
    expect(curve.buckets.map((b) => b.share)).toEqual([0, 0, 0, 0, 0, 0, 0])
  })
})

describe('the derivation is a pure total function', () => {
  it('mutates nothing it was handed, and gives the same answer twice', () => {
    const counts: Curve = [1, 2, 3, 4, 5, 6, 7]
    const before = JSON.stringify(counts)
    const first = curveOf(counts)
    expect(curveOf(counts)).toEqual(first)
    expect(JSON.stringify(counts)).toBe(before)
  })
})
