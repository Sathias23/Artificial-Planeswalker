/**
 * The mana curve panel, rendered.
 *
 * ================= WHAT jsdom CANNOT DECIDE HERE, DECLARED FIRST =======================
 *
 * **jsdom has no layout engine**, so `getBoundingClientRect()` is zeroes and a percentage height
 * never resolves to a pixel. **Every height assertion below is about the CUSTOM PROPERTY**, not
 * about a rendered bar — and that division is sharper in this component than in any before it,
 * because here the height IS the data. The pixels are the eye-check's, over CDP, against a
 * real engine.
 *
 * **`aria-query` maps `<header>` to `banner` unconditionally**, so every titled `Panel` is a
 * phantom `banner` in jsdom and none in a browser — Chrome reports exactly one where jsdom
 * reports one per titled panel. Nothing below queries `getByRole('banner')`.
 */

import { render, screen, within } from '@testing-library/react'
import { fireEvent } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { DeckStatistics } from '../../api/schema'
import { ManaCurve } from './ManaCurve'
import {
  CHART_LABEL,
  COLUMN_CARDS,
  COLUMN_MANA_VALUE,
  MANA_CURVE_TITLE,
  TABLE_CAPTION,
} from './copy'
import { BUCKETS } from './curve'

type Curve = DeckStatistics['curve']

/** A payload's statistics with this curve; the pips are not this panel's to read. */
const statisticsWith = (curve: Curve): DeckStatistics => ({
  land_count: 0,
  spell_count: curve.reduce((sum, count) => sum + count, 0),
  curve,
  colour_pips: [],
})

/** A curve of `[2, 5, 0, 1, 0, 0, 3]` — an empty bucket at both ends of the middle. */
const MIXED: Curve = [2, 5, 0, 1, 0, 0, 3]

const renderCurve = (curve: Curve = MIXED) =>
  render(<ManaCurve statistics={statisticsWith(curve)} />)

/**
 * The verify deck's figures as the agent reports them, from the committed fixture the Python
 * parity test compares `analyze_mana_curve` and `GET /api/deck/{id}` against.
 *
 * `import.meta.glob` with `eager` rather than a plain JSON import, so the fixture is read at the
 * one path both toolchains name and no import list grows a JSON specifier.
 */
interface StatisticsFixture {
  analyze_mana_curve: { distribution: Record<string, number> }
  statistics: DeckStatistics
}
const FIXTURE = Object.values(
  import.meta.glob<StatisticsFixture>('../../test-fixtures/deck-statistics.json', {
    eager: true,
    import: 'default',
  }),
)[0]

describe('the panel and the figure', () => {
  it('renders a titled Panel whose title is the section name', () => {
    renderCurve()
    const panel = screen.getByRole('region', { name: MANA_CURVE_TITLE })
    expect(panel.tagName).toBe('SECTION')
    expect(within(panel).getByRole('heading', { level: 2 }).textContent).toBe(MANA_CURVE_TITLE)
  })

  it('renders a <figure> carrying an accessible name of its own', () => {
    renderCurve()
    const figure = screen.getByRole('figure', { name: CHART_LABEL })
    expect(figure.tagName).toBe('FIGURE')
    // Deliberately a DIFFERENT string from the panel title: one name on two nested elements
    // makes a screen-reader user hear it twice with nothing to tell the region from the graphic.
    expect(CHART_LABEL).not.toBe(MANA_CURVE_TITLE)
  })

  it('is NOT at level="overlay" — a left-column panel sits on the panel surface', () => {
    const { container } = renderCurve()
    expect(container.querySelector('.panel-overlay')).toBeNull()
  })
})

describe('seven bars, in ascending order, with the last one open-ended', () => {
  it('draws exactly seven bars', () => {
    const { container } = renderCurve()
    expect(container.querySelectorAll('.mana-curve-bar')).toHaveLength(7)
  })

  it('labels the axis 1 … 7+ in order', () => {
    const { container } = renderCurve()
    const axis = [...container.querySelectorAll('.mana-curve-axis')].map((n) => n.textContent)
    expect(axis).toEqual(['1', '2', '3', '4', '5', '6', '7+'])
  })

  it('renders a count above every bar, INCLUDING the zeroes', () => {
    // 24 of the 40 real decks have at least one empty bucket, so this is the ordinary case.
    // `{count && …}` would render the bare string `0` and `count ? … : null` would drop it
    // entirely; `Number.isFinite` is the settled idiom.
    const { container } = renderCurve()
    const counts = [...container.querySelectorAll('.mana-curve-count')].map((n) => n.textContent)
    expect(counts).toEqual(['2', '5', '0', '1', '0', '0', '3'])
  })
})

describe('the bar heights are a custom property, and the scale is the tallest bar', () => {
  const heightsOf = (container: HTMLElement) =>
    [...container.querySelectorAll<HTMLElement>('.mana-curve-bar')].map((bar) =>
      bar.style.getPropertyValue('--curve-bar-height'),
    )

  it('scales every bar against the tallest bucket, not against the deck size', () => {
    // Tallest is 5, so the 5-bucket is 100% and the 2-bucket is 40% — NOT 2/11 of the deck.
    const { container } = renderCurve()
    expect(heightsOf(container)).toEqual(['40%', '100%', '0%', '20%', '0%', '0%', '60%'])
  })

  it('survives the 39-versus-0 extreme a real deck actually contains', () => {
    // `Infinite Guideline Station v2 (owned)`: 39 cards in one bucket beside two that are empty.
    const { container } = renderCurve([0, 39, 13, 0, 0, 0, 0])
    expect(heightsOf(container)).toEqual(['0%', '100%', '33.33%', '0%', '0%', '0%', '0%'])
  })

  it('draws the one-card deck with six empty bars and no divide-by-zero', () => {
    // `Iron Man, Modern Marvel — reminder` is one card and six empty buckets, and it is the
    // deck that makes `Math.max(1, …)` exercised by data rather than by a fixture.
    const { container } = renderCurve([0, 0, 0, 1, 0, 0, 0])
    expect(heightsOf(container)).toEqual(['0%', '0%', '0%', '100%', '0%', '0%', '0%'])
  })

  it('never writes NaN into a DRAWN curve', () => {
    // An all-zero curve would render null, leaving `container.innerHTML` as `''` and
    // `.not.toContain('NaN')` passing on NOTHING. This one draws, so seven height values
    // genuinely pass through heightPercent first.
    const { container } = renderCurve([1, 3, 0, 0, 0, 0, 0])
    expect(container.querySelectorAll('.mana-curve-bar')).toHaveLength(7)
    expect(container.innerHTML).not.toContain('NaN')
  })
})

describe('the bars are display-only', () => {
  it('adds ZERO Tab stops, and the only roles are the seven img bars', () => {
    const { container } = renderCurve()
    expect(container.querySelectorAll('[tabindex]')).toHaveLength(0)
    expect(container.querySelectorAll('button')).toHaveLength(0)
    // The page's Tab order runs from the grid to the right column; a seven-stop chart between
    // them would be a real cost, so its absence is asserted rather than assumed.
    expect(container.querySelectorAll('a, input, select, textarea')).toHaveLength(0)
    // The bars DO carry `role="img"`, deliberately: an `aria-label` on a bare <div> is not
    // reliably exposed without one, so dropping the role would cost the per-bar names. `img` is
    // non-interactive, so "display-only" (no interactive affordance, no focus, no click) holds
    // in full. This asserts the whole set, so an eighth role — or an interactive one — is loud.
    const withRole = [...container.querySelectorAll('[role]')]
    expect(withRole).toHaveLength(7)
    for (const el of withRole) {
      expect(el.getAttribute('role')).toBe('img')
      expect(el.className).toBe('mana-curve-bar')
    }
  })

  it('does nothing observable when a bar is clicked', () => {
    const { container } = renderCurve()
    const before = container.innerHTML
    const bar = container.querySelector('.mana-curve-bar')
    expect(bar).not.toBeNull()
    fireEvent.click(bar!)
    fireEvent.click(container.querySelector('.mana-curve-track')!)
    expect(container.innerHTML).toBe(before)
  })
})

describe('the accessible alternative', () => {
  it('names EVERY bar with its count, not only the first', () => {
    // A loop asserted on `[0]` proves the first element and nothing about the other six.
    const { container } = renderCurve()
    const names = [...container.querySelectorAll('.mana-curve-bar')].map((bar) =>
      bar.getAttribute('aria-label'),
    )
    expect(names).toEqual([
      '1 drop: 2 cards',
      '2 drops: 5 cards',
      '3 drops: 0 cards',
      '4 drops: 1 card',
      '5 drops: 0 cards',
      '6 drops: 0 cards',
      '7+ drops: 3 cards',
    ])
  })

  it('singularises both nouns on one, and keeps the plural on the open-ended bucket', () => {
    // UX-DR17 gives one worked example and no rule, so this pluralisation is INVENTED — see
    // copy.ts. `7+` names a RANGE, so "7+ drop" would be wrong even for a single card.
    const { container } = renderCurve([1, 0, 0, 0, 0, 0, 1])
    const names = [...container.querySelectorAll('.mana-curve-bar')].map((b) =>
      b.getAttribute('aria-label'),
    )
    expect(names[0]).toBe('1 drop: 1 card')
    expect(names[6]).toBe('7+ drops: 1 card')
  })

  it('backs the curve with a real <table>, captioned and with two authored headers', () => {
    renderCurve()
    const table = screen.getByRole('table', { name: TABLE_CAPTION })
    const headers = within(table)
      .getAllByRole('columnheader')
      .map((h) => h.textContent)
    expect(headers).toEqual([COLUMN_MANA_VALUE, COLUMN_CARDS])
    // One row per bucket, plus the header row.
    expect(within(table).getAllByRole('row')).toHaveLength(8)
    const cells = within(table)
      .getAllByRole('cell')
      .map((c) => c.textContent)
    expect(cells).toEqual(['2', '5', '0', '1', '0', '0', '3'])
  })

  it('keeps the table IN the accessibility tree — not display:none, not visibility:hidden', () => {
    // The clip-rect idiom, re-declared from CardDetailChrome.css's precedent. Both of the
    // alternatives REMOVE the element from the tree, so the alternative would exist and never
    // be read — a failure no rendered-output assertion could see.
    const { container } = renderCurve()
    const table = container.querySelector('.mana-curve-table')
    expect(table).not.toBeNull()
    expect(table!.getAttribute('aria-hidden')).toBeNull()
    expect(table!.hasAttribute('hidden')).toBe(false)
  })

  it('hides the painted count and axis text, which the table and the bar names already say', () => {
    // The BAR keeps its name (UX-DR17's own design); the two text nodes beside it
    // are the duplicates. Without this a reader hears each number three times.
    const { container } = renderCurve()
    for (const selector of ['.mana-curve-count', '.mana-curve-axis']) {
      const nodes = [...container.querySelectorAll(selector)]
      expect(nodes).toHaveLength(7)
      for (const node of nodes) {
        expect(node.getAttribute('aria-hidden'), `${selector} is not hidden`).toBe('true')
      }
    }
  })

  it('is NOT a live region and adds no aria-live anywhere', () => {
    // A curve that announced on every deck change would be a second announcer beside
    // CardDetail's single polite region.
    const { container } = renderCurve()
    expect(container.querySelectorAll('[aria-live]')).toHaveLength(0)
    expect(container.querySelectorAll('[role="status"], [role="alert"]')).toHaveLength(0)
  })
})

describe('the empty-curve behaviour', () => {
  it('renders NOTHING for an all-zero curve — an empty deck or one of ONLY LANDS', () => {
    // The subtlety that makes this more than "zero cards": the condition is
    // ZERO CARDS IN THE CURVE, not zero cards in the deck. A land-only deck has cards and
    // nothing for a curve to say, and the server reports it as seven zeroes, which is a worse
    // thing to draw than absence.
    //
    // Measured: NO deck in the corpus reaches this state — all 40 have rows and the smallest
    // curve is 1 — so it is not producible from live data and this test is its only witness.
    const { container } = renderCurve([0, 0, 0, 0, 0, 0, 0])
    expect(container.innerHTML).toBe('')
  })

  it('renders the panel for a deck holding a SINGLE spell', () => {
    renderCurve([0, 0, 0, 1, 0, 0, 0])
    expect(screen.getByRole('region', { name: MANA_CURVE_TITLE })).toBeTruthy()
  })
})

describe('the bars are the figures the agent reports', () => {
  it('draws the committed verify deck with the counts `analyze_mana_curve` reports', () => {
    // `deck-statistics.json` is what the Python parity test holds the tool AND the payload to,
    // so this ties the painted bars to the agent's distribution through one file.
    expect(FIXTURE).toBeDefined()
    const { container } = render(<ManaCurve statistics={FIXTURE.statistics} />)
    const counts = [...container.querySelectorAll('.mana-curve-count')].map((n) => n.textContent)
    const toolCounts = BUCKETS.map((bucket) =>
      String(FIXTURE.analyze_mana_curve.distribution[String(bucket)]),
    )
    expect(counts).toEqual(toolCounts)
    // Non-vacuity: the fixture's curve is not all zeros, so the panel drew rather than hid.
    expect(counts).toEqual(['2', '0', '2', '1', '0', '0', '2'])
  })
})

describe('the panel draws no card (UX-DR4)', () => {
  it('puts no card-shaped class anywhere in its markup', () => {
    const { container } = renderCurve()
    expect(container.querySelectorAll('.card-shape')).toHaveLength(0)
    expect(container.innerHTML).not.toContain('radius-card')
  })
})
