/**
 * The colour bar's segments, built from the server's per-colour pip counts.
 *
 * The card RULES — which face's cost counts, what a hybrid, Phyrexian or generic-hybrid symbol
 * credits, that lands and the sideboard are excluded and the commander included — moved to Python
 * with the counts themselves: `tests/unit/logic/test_card_statistics.py` holds every case this
 * file used to (the Omen dragons, the Pathway lands, `{G/W/P}`, `{2/W}`, `{C}`, `{S}`, the
 * Landers). What is left to test here is presentation: which colours become segments, their
 * order, and the rounded percentage each one prints.
 *
 * A `.ts`, not a `.tsx`: no JSX below. The rendered half lives in `ColourDistribution.test.tsx`.
 */

import { describe, expect, it } from 'vitest'

import type { DeckStatistics } from '../../api/schema'
import { segmentsOf } from './colours'

type Pips = DeckStatistics['colour_pips']
type WireColour = Pips[number]['colour']

/** Six `{colour, count}` entries in the wire's order, zeros kept, as the server sends them. */
const pips = (counts: Partial<Record<WireColour, number>>): Pips =>
  (['W', 'U', 'B', 'R', 'G', 'C'] as const).map((colour) => ({
    colour,
    count: counts[colour] ?? 0,
  }))

describe('segments are the non-empty colours, in WUBRG order with colourless last', () => {
  it('maps the wire letters onto the parser vocabulary', () => {
    const { segments } = segmentsOf(pips({ W: 1, U: 1, B: 1, R: 1, G: 1, C: 1 }))
    expect(segments.map((s) => s.colour)).toEqual(['w', 'u', 'b', 'r', 'g', 'c'])
  })

  it('orders by colour, never by count', () => {
    const { segments } = segmentsOf(pips({ W: 1, B: 30, G: 4 }))
    expect(segments.map((s) => [s.colour, s.count])).toEqual([
      ['w', 1],
      ['b', 30],
      ['g', 4],
    ])
  })

  it('reads each entry by its colour, so the wire order is not relied on', () => {
    const shuffled: Pips = [
      { colour: 'G', count: 2 },
      { colour: 'W', count: 3 },
    ]
    expect(segmentsOf(shuffled).segments.map((s) => s.colour)).toEqual(['w', 'g'])
  })

  it('never emits a segment with a zero count', () => {
    // A colour with no pips has no entry at all — the legend is a list of what the deck HAS,
    // not six rows of which four say nothing.
    const { segments } = segmentsOf(pips({ B: 2 }))
    expect(segments).toHaveLength(1)
    expect(segments.every((s) => s.count > 0)).toBe(true)
  })

  it('draws a colourless segment when the server counts `{C}`', () => {
    expect(segmentsOf(pips({ C: 2 })).segments).toEqual([{ colour: 'c', count: 2, percent: 100 }])
  })
})

describe('the displayed percentage is rounded and NEED NOT sum to 100', () => {
  it('prints 33% · 33% · 33% for three equal colours, and says 99 rather than inventing 100', () => {
    const percents = segmentsOf(pips({ B: 1, R: 1, G: 1 })).segments.map((s) => s.percent)
    expect(percents).toEqual([33, 33, 33])
    expect(percents.reduce((a, b) => a + b, 0)).toBe(99)
  })

  it('prints 100% for a mono-colour deck', () => {
    const { segments, total } = segmentsOf(pips({ B: 4 }))
    expect(segments).toHaveLength(1)
    expect(segments[0].percent).toBe(100)
    expect(total).toBe(4)
  })

  it('prints a rounded 0% honestly rather than flooring a non-zero count to 1%', () => {
    // The count beside it is the un-rounded truth, and a floor would make the printed
    // percentage disagree with its own arithmetic in the one case anyone would check.
    const segments = segmentsOf(pips({ B: 300, R: 1 })).segments
    expect(segments.map((s) => [s.colour, s.count, s.percent])).toEqual([
      ['b', 300, 100],
      ['r', 1, 0],
    ])
  })

  it('takes the percentages of the TOTAL, which hybrids can push past the symbol count', () => {
    // A `{G/W}` credits both colours server-side, so two hybrid pips arrive as G 2 + W 2.
    const { segments, total } = segmentsOf(pips({ W: 2, G: 2 }))
    expect(total).toBe(4)
    expect(segments.map((s) => s.percent)).toEqual([50, 50])
  })
})

describe('the zero-pip case', () => {
  it('is EMPTY, not a bar of zeroes, when every count is zero', () => {
    // The server reports a land-only, generic-only or empty deck as six zeroes.
    const { segments, total } = segmentsOf(pips({}))
    expect(segments).toEqual([])
    expect(total).toBe(0)
  })

  it('is empty for an empty list too', () => {
    expect(segmentsOf([])).toEqual({ segments: [], total: 0 })
  })
})

describe('the derivation is pure', () => {
  it('returns the same answer twice and mutates nothing it was handed', () => {
    const input = pips({ W: 5, G: 10 })
    const before = JSON.stringify(input)
    const first = segmentsOf(input)
    expect(segmentsOf(input)).toEqual(first)
    expect(JSON.stringify(input)).toBe(before)
  })
})
