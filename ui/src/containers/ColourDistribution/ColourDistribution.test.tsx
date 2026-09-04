/**
 * The colour distribution panel, rendered (story c4-9, AC 1–5, AC 15–33).
 *
 * ================= WHAT jsdom CANNOT DECIDE HERE, DECLARED FIRST =======================
 *
 * **jsdom has no layout engine**, so `getBoundingClientRect()` is zeroes and a `flex-grow` factor
 * never resolves to a pixel. **Every width assertion below is about the CUSTOM PROPERTY or the
 * class**, never about a rendered band — and the division is sharper here than in c4-8, because
 * this panel's widths are not even percentages: the value crossing the style attribute is a raw
 * pip count and the BROWSER does the division. The pixels, the hairline and the thinnest live
 * segment are AC 38's eye-check, over CDP, against a real engine.
 *
 * **jsdom applies no stylesheet**, so the hairline, the 14px track, the pill radius and every
 * `--mana-*` fill are read as CSS SOURCE by `tests/token-usage.test.ts` and by eye. Nothing below
 * claims otherwise.
 *
 * **`aria-query` maps `<header>` to `banner` unconditionally**, so every titled `Panel` is a
 * phantom `banner` in jsdom and none in a browser — c4-7 measured Chrome reporting exactly one
 * where jsdom said three, c4-8 took jsdom to four, and **this panel takes it to five** (AC 28).
 * Nothing below queries `getByRole('banner')`.
 */

import { act, render, screen, within } from '@testing-library/react'
import { fireEvent } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import type { CardSummary, DeckCardSummary } from '../../api/schema'
import { boardsOf } from '../../state/deckGroups'
import { type CardEntry, resetCardCache, useCardStore } from '../../state/cards'
import { ColourDistribution } from './ColourDistribution'
import { CHART_LABEL, COLOUR_DISTRIBUTION_TITLE } from './copy'

interface RowOptions {
  quantity?: number
  sideboard?: boolean
  commander?: boolean
}

/** A real corpus card, spelled as the wire spells it (AC 14) — `colors` included, verbatim. */
const card = (
  name: string,
  manaCost: string,
  typeLine: string,
  cmc: number,
  colors: string[] = [],
): CardSummary => ({
  id: `id-${name}`,
  name,
  mana_cost: manaCost,
  cmc,
  type_line: typeLine,
  oracle_text: '',
  colors,
  rarity: 'rare',
  set_code: 'tst',
  set_name: 'Test Set',
  collector_number: '1',
  oracle_id: 'oracle-1',
  color_identity: [],
  legalities: {},
  games: [],
})

const row = (summary: CardSummary, options: RowOptions = {}): DeckCardSummary => ({
  card_id: summary.id,
  quantity: options.quantity ?? 1,
  sideboard: options.sideboard ?? false,
  commander: options.commander ?? false,
  card: summary,
})

/**
 * A three-colour deck of real corpus rows — 6 black, 3 red, 1 green, ten pips in all, so the
 * percentages are 60 / 30 / 10 and every one of them is a whole number. Deliberately NOT three
 * equal colours: the rounding case has its own test in `colours.test.ts`.
 */
const THREE_COLOURS = [
  row(card('Doom Blade', '{1}{B}', 'Instant', 2, ['B']), { quantity: 3 }),
  row(card('Ayara, First of Locthwain', '{B}{B}{B}', 'Legendary Creature — Elf Noble', 3, ['B']), {
    commander: true,
  }),
  row(card('Lightning Bolt', '{R}', 'Instant', 1, ['R']), { quantity: 3 }),
  row(card('Giant Growth', '{G}', 'Instant', 1, ['G'])),
  // Excluded, both of them — and both are real: the land carries a coloured cost, and the
  // sideboard row would be a fifth colour if it counted.
  row(card('Glade of the Pump Spells', '{2}{G}', 'Land', 3, ['G']), { quantity: 4 }),
  row(
    card(
      'Sokka, Lateral Strategist',
      '{1}{W/U}{W/U}',
      'Legendary Creature — Human Warrior Ally',
      3,
      ['U', 'W'],
    ),
    {
      sideboard: true,
      quantity: 4,
    },
  ),
]

const renderBar = (rows: DeckCardSummary[] = THREE_COLOURS) =>
  render(<ColourDistribution boards={boardsOf(rows)} />)

const segmentsIn = (container: HTMLElement) => [
  ...container.querySelectorAll<HTMLElement>('.colour-bar-segment'),
]

beforeEach(() => {
  resetCardCache()
})

afterEach(() => {
  resetCardCache()
})

describe('the panel and the figure (AC 4, AC 5)', () => {
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

describe('the bar: one segment per colour, in WUBRG order (AC 15, AC 19)', () => {
  it('draws one segment per colour the deck actually has, and none for the rest', () => {
    const { container } = renderBar()
    expect(segmentsIn(container).map((s) => s.className)).toEqual([
      'colour-bar-segment colour-bar-segment-b',
      'colour-bar-segment colour-bar-segment-r',
      'colour-bar-segment colour-bar-segment-g',
    ])
  })

  it('carries the RAW PIP COUNT on the named channel — not a percentage (Q13, AC 19)', () => {
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

  it('names no --mana-* token in markup — the class is the only way in (AC 16)', () => {
    const { container } = renderBar()
    expect(container.innerHTML).not.toContain('--mana-')
    expect(container.querySelectorAll('[fill]')).toHaveLength(0)
  })
})

describe('the legend is the accessible data path (AC 20, AC 23, AC 24, UX-DR18)', () => {
  it('hides the BAR from the accessibility tree, and names nothing inside it', () => {
    // THE EXACT INVERSE OF c4-8, where every bar carried `role="img"` and a name. UX-DR18 says
    // the bar is `aria-hidden` and the legend is the data path, and the reason is measurable:
    // all 15 adjacent `--mana-*` pairs are under the 3:1 non-text floor, the worst at 1.03:1.
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
    // The c4-7 one-pip-run finding, not repeated: a loop asserted on `[0]` proves the first
    // element and nothing about the others.
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

  it('keeps the legend PIP decorative — no label, no doubled announcement (Q9 iv, AC 25)', () => {
    // `ManaPip`'s `label` prop was written "for c4-9's legend" and this story does not use it:
    // the entry already reads its colour, count and percentage as text, and a labelled pip
    // beside its own text count is the doubled announcement that docstring warns about. The
    // prediction in `ManaPip.tsx` is corrected in this commit rather than left standing.
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

  it('ships NO visually-hidden block — the third-instance trigger does not fire (AC 29)', () => {
    // c4-8 recorded a third-instance promotion trigger for the clip-rect idiom: whoever writes
    // the third block promotes it to `src/styles/`. This story writes none — the legend is
    // VISIBLE text, which is what UX-DR18's "the legend is the accessible data path" means — so
    // the trigger does not fire, and that is asserted rather than left as an absence.
    const { container } = renderBar()
    expect(container.querySelectorAll('table')).toHaveLength(0)
    expect(container.innerHTML).not.toContain('clip-path')
    expect(container.querySelectorAll('[hidden]')).toHaveLength(0)
  })

  it('is NOT a live region and adds no aria-live anywhere (AC 26)', () => {
    // LOAD-BEARING HERE in a way it was not for the curve: this panel's numbers MOVE during the
    // hydration sweep, so a live region would announce a changing percentage ~99 times.
    const { container } = renderBar()
    expect(container.querySelectorAll('[aria-live]')).toHaveLength(0)
    expect(container.querySelectorAll('[role="status"], [role="alert"]')).toHaveLength(0)
  })
})

describe('the panel is display-only (AC 27, UX-DR40, UX-DR47)', () => {
  it('adds ZERO Tab stops and carries no role anywhere', () => {
    const { container } = renderBar()
    expect(container.querySelectorAll('[tabindex]')).toHaveLength(0)
    expect(container.querySelectorAll('button, a, input, select, textarea')).toHaveLength(0)
    // The inverse of c4-8's seven `role="img"` bars: nothing in this subtree carries a role at
    // all, so an eighth — or an interactive one — is loud.
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

describe('the panel reads the hydration cache, and starts nothing (AC 7, AC 8, Q2, Q3)', () => {
  // `Ayara, Widow of the Realm // Ayara, Furnace Queen` — blank at the top level, `{1}{B}{B}` on
  // its front face, and the namesake of the deck with the largest bar in the corpus.
  const AYARA_DFC = card(
    'Ayara, Widow of the Realm // Ayara, Furnace Queen',
    '',
    'Legendary Creature — Elf Noble // Legendary Creature — Phyrexian Elf Noble',
    3,
  )

  it('renders NOTHING before the sweep reaches a deck of only blank-cost cards', () => {
    const { container } = renderBar([row(AYARA_DFC)])
    expect(container.innerHTML).toBe('')
  })

  it('RE-RENDERS with the real pips when the cache fills — the numbers move after first paint', () => {
    // The whole of Q2, and the reason "no `aria-live`" is load-bearing: this panel is the epic's
    // first whose PERCENTAGES change after the deck has painted. Live that is +48 pips across 16
    // of 40 decks.
    const rows = [row(AYARA_DFC), row(card('Lightning Bolt', '{R}', 'Instant', 1, ['R']))]
    const { container } = renderBar(rows)

    // Before: one red pip, 100% red.
    expect(
      [...container.querySelectorAll('.colour-legend-name')].map((n) => n.textContent),
    ).toEqual(['Red'])

    // `act` because the write is a store update outside React's own event handling: without it
    // the subscription fires and the re-render is never flushed, which would make this test pass
    // for the wrong reason if it were asserting an absence.
    act(() => {
      // The cast is on the CARD alone, not the whole state object — `colours.test.ts`'s
      // `hydrated` helper narrows the same way, and for the same reason: `card_faces` is
      // untyped on the wire so the face literal must widen, but `status` and the shape of the
      // `cards` record stay checked against the union, so a `CardEntry` drift fails `tsc` here
      // instead of leaving this fixture writing a state the store could never contain
      // (review 2026-08-06 — the previous spelling was `as never` on everything).
      useCardStore.setState({
        cards: {
          [AYARA_DFC.id]: {
            status: 'hydrated',
            card: { ...AYARA_DFC, card_faces: [{ mana_cost: '{1}{B}{B}' }] } as unknown as Extract<
              CardEntry,
              { status: 'hydrated' }
            >['card'],
          },
        },
      })
    })

    // After: two black and one red, and the subscription is what made it re-render.
    expect(
      [...container.querySelectorAll('.colour-legend-name')].map((n) => n.textContent),
    ).toEqual(['Black', 'Red'])
    expect(
      segmentsIn(container).map((s) => s.style.getPropertyValue('--colour-bar-share')),
    ).toEqual(['2', '1'])
  })

  it('leaves the cache untouched — it reads, and starts no fetch (AC 8, don’t-break 10)', () => {
    // `hydrateCard`/`hydrateDeckCards` are `App.tsx`'s alone. If this panel ever called one, the
    // cache would gain a `loading` entry on render.
    expect(useCardStore.getState().cards).toEqual({})
    renderBar()
    expect(useCardStore.getState().cards).toEqual({})
  })
})

describe('the empty case (AC 32, Q10)', () => {
  it('renders NOTHING when the deck has no cards', () => {
    const { container } = renderBar([])
    expect(container.innerHTML).toBe('')
  })

  it('renders nothing for a land-only deck — cards, but no colour balance to describe', () => {
    // Measured: NO deck in the corpus reaches this state (all 40 have at least 2 pips), so it is
    // not producible from live data and this is its only rendered witness.
    const { container } = renderBar([
      row(card('Forest', '', 'Basic Land — Forest', 0), { quantity: 24 }),
      row(card('Glade of the Pump Spells', '{2}{G}', 'Land', 3), { quantity: 4 }),
    ])
    expect(container.innerHTML).toBe('')
  })

  it('renders nothing for a deck of purely generic costs', () => {
    const { container } = renderBar([row(card('Sol Ring', '{1}', 'Artifact', 1), { quantity: 4 })])
    expect(container.innerHTML).toBe('')
  })

  it('draws ONE segment at 100% for a mono-colour deck — 9 of the 40 real decks', () => {
    const { container } = renderBar([
      row(card('Ayara, First of Locthwain', '{B}{B}{B}', 'Legendary Creature — Elf Noble', 3)),
    ])
    expect(segmentsIn(container)).toHaveLength(1)
    expect(container.querySelector('.colour-legend-percent')!.textContent).toBe('100%')
    expect(container.querySelector('.colour-legend-count')!.textContent).toBe('3 pips')
  })
})

describe('the panel draws no card (AC 22, UX-DR4)', () => {
  it('puts no card-shaped class anywhere in its markup', () => {
    const { container } = renderBar()
    expect(container.querySelectorAll('.card-shape')).toHaveLength(0)
    expect(container.innerHTML).not.toContain('radius-card')
  })
})
