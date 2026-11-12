/**
 * The colour distribution panel, rendered.
 *
 * ================= WHAT jsdom CANNOT DECIDE HERE, DECLARED FIRST =======================
 *
 * **jsdom has no layout engine**, so `getBoundingClientRect()` is zeroes and a `flex-grow` factor
 * never resolves to a pixel. **Every width assertion below is about the CUSTOM PROPERTY or the
 * class**, never about a rendered band — and the division is sharper here than for the mana
 * curve, because this panel's widths are not even percentages: the value crossing the style
 * attribute is a raw pip count and the BROWSER does the division. The pixels, the hairline and
 * the thinnest live segment are the eye-check, over CDP, against a real engine.
 *
 * **jsdom applies no stylesheet**, so the hairline, the 14px track, the pill radius and every
 * `--mana-*` fill are read as CSS SOURCE by `tests/token-usage.test.ts` and by eye. Nothing below
 * claims otherwise.
 *
 * **`aria-query` maps `<header>` to `banner` unconditionally**, so every titled `Panel` is a
 * phantom `banner` in jsdom and none in a browser, and this panel adds one more. Nothing below
 * queries `getByRole('banner')`.
 */

import { render, screen, within } from '@testing-library/react'
import { fireEvent } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { DeckStatistics } from '../../api/schema'
import { useCardStore } from '../../state/cards'
import { ColourDistribution } from './ColourDistribution'
import { CHART_LABEL, COLOUR_DISTRIBUTION_TITLE } from './copy'

type WireColour = DeckStatistics['colour_pips'][number]['colour']

/** A payload's statistics with these pip counts; the curve is not this panel's to read. */
const statisticsWith = (counts: Partial<Record<WireColour, number>>): DeckStatistics => ({
  land_count: 0,
  spell_count: 0,
  curve: [0, 0, 0, 0, 0, 0, 0],
  colour_pips: (['W', 'U', 'B', 'R', 'G', 'C'] as const).map((colour) => ({
    colour,
    count: counts[colour] ?? 0,
  })),
})

/**
 * A three-colour deck — 6 black, 3 red, 1 green, ten pips in all, so the percentages are
 * 60 / 30 / 10 and every one of them is a whole number. Deliberately NOT three equal colours:
 * the rounding case has its own test in `colours.test.ts`.
 */
const THREE_COLOURS = statisticsWith({ B: 6, R: 3, G: 1 })

const renderBar = (statistics: DeckStatistics = THREE_COLOURS) =>
  render(<ColourDistribution statistics={statistics} />)

const segmentsIn = (container: HTMLElement) => [
  ...container.querySelectorAll<HTMLElement>('.colour-bar-segment'),
]

/**
 * The verify deck's figures as the agent reports them, from the committed fixture the Python
 * parity test compares `analyze_mana_curve` and `GET /api/deck/{id}` against.
 */
interface StatisticsFixture {
  analyze_mana_curve: { colour_pips: DeckStatistics['colour_pips'] }
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
    renderBar()
    const panel = screen.getByRole('region', { name: COLOUR_DISTRIBUTION_TITLE })
    expect(panel.tagName).toBe('SECTION')
    expect(within(panel).getByRole('heading', { level: 2 }).textContent).toBe(
      COLOUR_DISTRIBUTION_TITLE,
    )
  })

  it('renders a <figure> carrying an accessible name of its own', () => {
    renderBar()
    const figure = screen.getByRole('figure', { name: CHART_LABEL })
    expect(figure.tagName).toBe('FIGURE')
    // Deliberately a DIFFERENT string from the panel title: one name on two nested elements
    // makes a screen-reader user hear it twice with nothing to tell the region from the graphic.
    expect(CHART_LABEL).not.toBe(COLOUR_DISTRIBUTION_TITLE)
  })

  it('is NOT at level="overlay" — a left-column panel sits on the panel surface', () => {
    const { container } = renderBar()
    expect(container.querySelector('.panel-overlay')).toBeNull()
  })
})

describe('the bar: one segment per colour, in WUBRG order', () => {
  it('draws one segment per colour the deck actually has, and none for the rest', () => {
    const { container } = renderBar()
    expect(segmentsIn(container).map((s) => s.className)).toEqual([
      'colour-bar-segment colour-bar-segment-b',
      'colour-bar-segment colour-bar-segment-r',
      'colour-bar-segment colour-bar-segment-g',
    ])
  })

  it('carries the RAW PIP COUNT on the named channel — not a percentage', () => {
    // The whole of "no division by zero is possible": there is no division at this call site at
    // all. `flex-grow` distributes the track's free space in the browser, so the geometry is
    // exact whatever the printed percentages round to.
    const { container } = renderBar()
    expect(
      segmentsIn(container).map((s) => s.style.getPropertyValue('--colour-bar-share')),
    ).toEqual(['6', '3', '1'])
  })

  it('writes NO other inline property on a segment', () => {
    // The channel is the only thing crossing the style attribute. A `width`, a `background` or a
    // `--mana-*` here would each be a different gate's failure, and this is the one that reads
    // the rendered attribute rather than the source.
    const { container } = renderBar()
    for (const segment of segmentsIn(container)) {
      // `style.length` counts the declarations the element actually carries, so this is an
      // EXHAUSTIVE claim rather than a check for the two or three properties anyone thought of.
      expect(segment.style.length, segment.getAttribute('style') ?? '').toBe(1)
      expect(segment.style.item(0)).toBe('--colour-bar-share')
    }
  })

  it('names no --mana-* token in markup — the class is the only way in', () => {
    const { container } = renderBar()
    expect(container.innerHTML).not.toContain('--mana-')
    expect(container.querySelectorAll('[fill]')).toHaveLength(0)
  })
})

describe('the legend is the accessible data path (UX-DR18)', () => {
  it('hides the BAR from the accessibility tree, and names nothing inside it', () => {
    // THE EXACT INVERSE OF THE MANA CURVE, where every bar carries `role="img"` and a name.
    // UX-DR18 says the bar is `aria-hidden` and the legend is the data path, and the reason is
    // measurable: all 15 adjacent `--mana-*` pairs are under the 3:1 non-text floor, the worst
    // at 1.03:1.
    const { container } = renderBar()
    const bar = container.querySelector('.colour-bar')
    expect(bar).not.toBeNull()
    expect(bar!.getAttribute('aria-hidden')).toBe('true')
    expect(bar!.getAttribute('role')).toBeNull()
    expect(bar!.getAttribute('aria-label')).toBeNull()
    // Asserted rather than assumed: NO segment carries a role or a name of any kind.
    for (const segment of segmentsIn(container)) {
      expect(segment.getAttribute('role')).toBeNull()
      expect(segment.getAttribute('aria-label')).toBeNull()
      expect(segment.getAttribute('title')).toBeNull()
      expect(segment.textContent).toBe('')
    }
  })

  it('reads EVERY entry — colour, count and percentage — not only the first', () => {
    // A loop asserted on `[0]` proves the first element and nothing about the others.
    const { container } = renderBar()
    const entries = [...container.querySelectorAll('.colour-legend-entry')].map((entry) =>
      [...entry.querySelectorAll('span:not(.mana-pip)')].map((n) => n.textContent),
    )
    expect(entries).toEqual([
      ['Black', '6 pips', '60%'],
      ['Red', '3 pips', '30%'],
      ['Green', '1 pip', '10%'],
    ])
  })

  it('puts each colour on screen AS TEXT, so colour is never the sole carrier', () => {
    const { container } = renderBar()
    const names = [...container.querySelectorAll('.colour-legend-name')].map((n) => n.textContent)
    expect(names).toEqual(['Black', 'Red', 'Green'])
    // The list semantics are real, not `role="list"` on a stack of divs.
    const legend = container.querySelector('.colour-legend')
    expect(legend!.tagName).toBe('UL')
    expect(within(container).getAllByRole('listitem')).toHaveLength(3)
  })

  it('keeps the legend PIP decorative — no label, no doubled announcement', () => {
    // `ManaPip`'s `label` prop is not used here: the entry already reads its colour, count and
    // percentage as text, and a labelled pip beside its own text count is the doubled
    // announcement that prop's docstring warns about.
    const { container } = renderBar()
    const pips = [...container.querySelectorAll('.mana-pip')]
    expect(pips).toHaveLength(3)
    for (const pip of pips) {
      expect(pip.getAttribute('aria-hidden')).toBe('true')
      expect(pip.getAttribute('role')).toBeNull()
      expect(pip.getAttribute('aria-label')).toBeNull()
    }
    // …and the pip still carries its colour CLASS, so the picture is right even though the
    // announcement is not doubled.
    expect(pips.map((p) => p.className)).toEqual([
      'mana-pip mana-pip-b',
      'mana-pip mana-pip-r',
      'mana-pip mana-pip-g',
    ])
  })

  it('ships NO visually-hidden block — the third-instance trigger does not fire', () => {
    // The clip-rect idiom carries a third-instance promotion trigger: whoever writes the third
    // visually-hidden block promotes it to `src/styles/`. This panel writes none — the legend is
    // VISIBLE text, which is what UX-DR18's "the legend is the accessible data path" means — so
    // the trigger does not fire, and that is asserted rather than left as an absence.
    const { container } = renderBar()
    expect(container.querySelectorAll('table')).toHaveLength(0)
    expect(container.innerHTML).not.toContain('clip-path')
    expect(container.querySelectorAll('[hidden]')).toHaveLength(0)
  })

  it('is NOT a live region and adds no aria-live anywhere', () => {
    // A bar that announced on every deck change would be a second announcer beside
    // CardDetail's single polite region.
    const { container } = renderBar()
    expect(container.querySelectorAll('[aria-live]')).toHaveLength(0)
    expect(container.querySelectorAll('[role="status"], [role="alert"]')).toHaveLength(0)
  })
})

describe('the panel is display-only (UX-DR40, UX-DR47)', () => {
  it('adds ZERO Tab stops and carries no role anywhere', () => {
    const { container } = renderBar()
    expect(container.querySelectorAll('[tabindex]')).toHaveLength(0)
    expect(container.querySelectorAll('button, a, input, select, textarea')).toHaveLength(0)
    // The inverse of the mana curve's seven `role="img"` bars: nothing in this subtree carries a
    // role at all, so an eighth — or an interactive one — is loud.
    expect(container.querySelectorAll('[role]')).toHaveLength(0)
  })

  it('does nothing observable when a segment or a legend entry is clicked', () => {
    const { container } = renderBar()
    const before = container.innerHTML
    fireEvent.click(segmentsIn(container)[0])
    fireEvent.click(container.querySelector('.colour-legend-entry')!)
    fireEvent.click(container.querySelector('.colour-bar')!)
    expect(container.innerHTML).toBe(before)
  })
})

describe('the panel reads no card cache, and starts nothing', () => {
  it('leaves the cache untouched — the counts are the payload’s, complete at first paint', () => {
    // The pips used to come from the hydration cache and moved as the sweep landed. They now
    // ride on the deck payload, so rendering reads nothing and starts nothing.
    expect(useCardStore.getState().cards).toEqual({})
    renderBar()
    expect(useCardStore.getState().cards).toEqual({})
  })
})

describe('the legend is the figures the agent reports', () => {
  it('draws the committed verify deck with the counts `analyze_mana_curve` reports', () => {
    // `deck-statistics.json` is what the Python parity test holds the tool AND the payload to,
    // so this ties the painted legend to the agent's colour pips through one file.
    expect(FIXTURE).toBeDefined()
    const { container } = renderBar(FIXTURE.statistics)
    const legend = [...container.querySelectorAll('.colour-legend-count')].map((n) => n.textContent)
    const toolCounts = FIXTURE.analyze_mana_curve.colour_pips
      .filter((entry) => entry.count > 0)
      .map((entry) => `${entry.count} pips`)
    expect(legend).toEqual(toolCounts)
    // Non-vacuity: the verify deck's white and green, in WUBRG order.
    expect(legend).toEqual(['5 pips', '10 pips'])
  })
})

describe('the empty case', () => {
  it('renders NOTHING when every count is zero — an empty, land-only or generic-only deck', () => {
    // Measured: NO deck in the corpus reaches this state (all 40 have at least 2 pips), so it is
    // not producible from live data and this is its only rendered witness.
    const { container } = renderBar(statisticsWith({}))
    expect(container.innerHTML).toBe('')
  })

  it('draws ONE segment at 100% for a mono-colour deck — 9 of the 40 real decks', () => {
    const { container } = renderBar(statisticsWith({ B: 3 }))
    expect(segmentsIn(container)).toHaveLength(1)
    expect(container.querySelector('.colour-legend-percent')!.textContent).toBe('100%')
    expect(container.querySelector('.colour-legend-count')!.textContent).toBe('3 pips')
  })
})

describe('the panel draws no card (UX-DR4)', () => {
  it('puts no card-shaped class anywhere in its markup', () => {
    const { container } = renderBar()
    expect(container.querySelectorAll('.card-shape')).toHaveLength(0)
    expect(container.innerHTML).not.toContain('radius-card')
  })
})
