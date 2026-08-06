import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Card, CardSummary, DeckCardSummary } from '../../api/schema'
import { resetCardCache, useCardStore } from '../../state/cards'
import { boardsOf } from '../../state/deckGroups'
import {
  clearHovered,
  resetInspection,
  setDefaultTarget,
  setHovered,
  targetIdOf,
  togglePin,
  useInspectionStore,
} from '../../state/inspection'
import { DeckList } from './DeckList'
import { COMMANDER_LABEL, DECK_LIST_TITLE, GROUP_LABELS, SIDEBOARD_LABEL } from './copy'

/**
 * The deck list panel (story c4-7).
 *
 * ================= WHAT THIS SUITE CANNOT CARRY, SAID FIRST ============================
 *
 * An undeclared limit reads as coverage, so what this file provably cannot say comes first:
 *
 *   **EVERY APPEARANCE CLAIM.** jsdom evaluates no CSS. The row grid, the live tint, the inset
 *   rule, the ellipsis, the group-header rule and the ≥24px hit box are all source claims
 *   (`tests/token-usage.test.ts`, `tests/shell.test.ts`, `tests/tokens.test.ts`) plus **Task 7's**
 *   CDP eye-check. `is-live` is asserted here as a CLASS — what that class DRAWS is not.
 *
 *   **THE REDUCED-MOTION FALLBACK.** jsdom does not evaluate media queries into computed style,
 *   so reading a duration here would report the unreduced value and pass for the wrong reason.
 *   It is asserted as CSS source in `tests/token-usage.test.ts`.
 *
 *   **THE HEADING STRUCTURE AS A SCREEN READER WALKS IT (Q15).** `aria-query` maps `<header>` to
 *   `banner` unconditionally where HTML-AAM does not when it sits inside a `<section>`, so every
 *   titled `Panel` is a phantom `banner` in jsdom and none in a browser — measured at c4-5, and
 *   this is the first story to inherit it. Role queries here are scoped through the panel's
 *   region rather than by `getByRole('banner')`, and whether `h2`-inside-`h2` reads correctly is
 *   Chrome's accessibility tree to answer, not this file's.
 */

const CO = 'id-commander'
const CREATURE = 'id-creature'
const LAND_A = 'id-land-a'
const LAND_B = 'id-land-b'
const SIDE = 'id-side'
const DFC = 'id-dfc'

const summary = (id: string, over: Partial<CardSummary> = {}): CardSummary => ({
  id,
  name: 'Llanowar Elves',
  mana_cost: '{G}',
  cmc: 1,
  type_line: 'Creature — Elf Druid',
  oracle_text: '',
  colors: ['G'],
  rarity: 'common',
  set_code: 'tst',
  ...over,
})

const row = (
  id: string,
  over: Partial<CardSummary> = {},
  flags: Partial<Pick<DeckCardSummary, 'quantity' | 'sideboard' | 'commander'>> = {},
): DeckCardSummary => ({
  card_id: id,
  quantity: 1,
  sideboard: false,
  commander: false,
  ...flags,
  card: summary(id, over),
})

const seedHydrated = (id: string, card: Partial<Card>) => {
  useCardStore.setState((state) => ({
    cards: {
      ...state.cards,
      [id]: { status: 'hydrated', card: { ...summary(id), ...card } as Card },
    },
  }))
}

/** All three boards populated — the fixture AC 22's conservation identity needs. */
const THREE_BOARDS = [
  row(
    CO,
    { name: 'Atraxa, Praetors’ Voice', type_line: 'Legendary Creature — Angel' },
    { commander: true },
  ),
  row(CREATURE, { name: 'Llanowar Elves' }, { quantity: 4 }),
  row(
    LAND_A,
    { name: 'Forest', type_line: 'Basic Land — Forest', mana_cost: '' },
    { quantity: 10 },
  ),
  row(LAND_B, { name: 'Swamp', type_line: 'Basic Land — Swamp', mana_cost: '' }, { quantity: 34 }),
  row(SIDE, { name: 'Duress', type_line: 'Sorcery' }, { sideboard: true, quantity: 2 }),
]

const panelOf = () => screen.getByRole('region', { name: DECK_LIST_TITLE })

beforeEach(() => {
  resetInspection()
  resetCardCache()
})

describe('the panel, its placement and its semantics (AC 4, AC 5)', () => {
  it('is a titled Panel — an h2 that also names the section (UX-DR44)', () => {
    render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    const panel = panelOf()
    expect(panel).toBeVisible()
    expect(within(panel).getByRole('heading', { level: 2, name: DECK_LIST_TITLE })).toBeVisible()
  })

  it('is at level="default" — the first shipped consumer of that level (AC 33)', () => {
    const { container } = render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    // `panel-overlay` is the class the overlay level adds; its ABSENCE is half the assertion.
    // The other half ties `.panel` to THE deck-list region itself (not just any element in the
    // container), so this cannot pass vacuously if the Panel wrapper were dropped altogether.
    expect(panelOf().classList.contains('panel')).toBe(true)
    expect(container.querySelector('.panel-overlay')).toBeNull()
  })

  it('renders a real ul/li with NO role override (AC 5)', () => {
    const { container } = render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    for (const list of container.querySelectorAll('ul.deck-list-rows')) {
      expect(list.hasAttribute('role')).toBe(false)
    }
    for (const item of container.querySelectorAll('li.deck-list-item')) {
      expect(item.hasAttribute('role')).toBe(false)
    }
    // Five rows in, five rows out — nothing is dropped on the way to the glass.
    expect(within(panelOf()).getAllByRole('listitem')).toHaveLength(5)
  })

  it('adds NO aria-live anywhere — this panel is not a live region (AC 30, UX-DR45)', () => {
    const { container } = render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    expect(container.querySelectorAll('[aria-live]')).toHaveLength(0)
    expect(container.querySelectorAll('[role="status"], [role="alert"]')).toHaveLength(0)
  })
})

describe('the row (AC 6, AC 9, AC 10, AC 11)', () => {
  it('is a REAL button, and nothing carries a tabindex (UX-DR47)', () => {
    const { container } = render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    const rows = container.querySelectorAll('button.deck-row')
    expect(rows).toHaveLength(5)
    for (const button of rows) {
      expect(button.tagName).toBe('BUTTON')
      expect(button.getAttribute('type')).toBe('button')
    }
    // No `tabindex` ANYWHERE in this subtree — a button is already in the Tab order, and adding
    // one is the defect `CardTile.test.tsx:788-797` pins the same choice against.
    expect(container.querySelectorAll('[tabindex]')).toHaveLength(0)
  })

  it('renders the quantity for EVERY row, including 1 — unlike the tile badge (AC 9)', () => {
    render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    const panel = panelOf()
    // 1,620 of 1,999 real rows are quantity 1; a column that vanished on them is not a column.
    expect(within(panel).getByText('×1')).toBeVisible()
    expect(within(panel).getByText('×4')).toBeVisible()
    expect(within(panel).getByText('×10')).toBeVisible()
    // The largest quantity in any real deck — two digits plus the sign, at the track's 34px floor.
    expect(within(panel).getByText('×34')).toBeVisible()
  })

  it('uses U+00D7, never the letter x (AC 9, UX-DR3)', () => {
    render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    const quantities = [...panelOf().querySelectorAll('.deck-row-quantity')]
    expect(quantities).toHaveLength(5)
    for (const cell of quantities) {
      // The CODEPOINT, not the glyph — a letter `x` renders narrower beside a tabular digit and
      // is read aloud as a letter.
      expect(cell.textContent?.charCodeAt(0)).toBe(0x00d7)
      expect(cell.textContent).not.toMatch(/^x/)
    }
  })

  it('renders the cost through ManaCost, as a labelled pip run (AC 11)', () => {
    render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    // `ManaCost` renders `role="img"` with a spoken label; the TWO costless basic lands render
    // nothing, so three of the five rows carry one — every run labelled, not just the first.
    const runs = within(panelOf()).getAllByRole('img')
    expect(runs).toHaveLength(3)
    for (const run of runs) expect(run).toHaveAttribute('aria-label')
  })

  it('renders NO PIPS for a blank cost — the empty cell stays, keeping the grid track (AC 11)', () => {
    const { container } = render(<DeckList boards={boardsOf([row(LAND_A, { mana_cost: '' })])} />)

    // `ManaCost` returns `null`; the `.deck-row-cost` CELL is still rendered on purpose — the
    // row grid needs its third track — so the assertion is "empty cell", not "no cell".
    const cost = container.querySelector('.deck-row-cost')
    expect(cost).not.toBeNull()
    expect(cost?.textContent).toBe('')
    expect(within(panelOf()).queryAllByRole('img')).toHaveLength(0)
  })
})

describe('the price column that does not exist (AC 12, Q1)', () => {
  /**
   * THE ABSENCE, ASSERTED AT THE TYPE — c4-5's AC 14 pattern, one story on.
   *
   * `CardSummary` is generated from `openapi.json`, so this fails `npx tsc -b --force` the day a
   * price field appears on the wire — which is the only way this story's ruling could quietly
   * stop being true. A grep would not do: `tests/unit/companion/test_routes_cards.py:136` warns
   * the next author off exactly that, and a grep cannot see a field that arrives under a name
   * nobody predicted.
   */
  type Assert<T extends true> = T
  type NoPriceOnTheWire = Assert<
    [Extract<keyof CardSummary, 'price' | 'prices'>] extends [never] ? true : false
  >
  // Referenced so the alias is not dead code; the assertion is the type itself.
  const _noPrice: NoPriceOnTheWire = true

  it('has no price field on the wire type', () => {
    expect(_noPrice).toBe(true)
  })

  it('puts no currency on the glass (AC 12)', () => {
    render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    // The rendered half of the same claim: no `$`, and no empty fourth cell pretending to hold
    // one. A dead 64px gutter would read as a loading failure rather than an absent feature.
    expect(panelOf().textContent).not.toContain('$')
    for (const button of panelOf().querySelectorAll('button.deck-row')) {
      expect(button.children).toHaveLength(3)
    }
  })
})

describe('the groups, their order and their counts (AC 16, AC 17, AC 18, AC 19, AC 24)', () => {
  it('renders group headers through GroupHeader, the first production consumer (AC 16)', () => {
    const { container } = render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    expect(container.querySelectorAll('.group-header').length).toBeGreaterThan(0)
    expect(container.querySelector('.group-header-label')).not.toBeNull()
    expect(container.querySelector('.group-header-count')).not.toBeNull()
  })

  it('orders sections commander → TYPE_GROUPS → sideboard, and never re-sorts (AC 17, AC 20, AC 21)', () => {
    render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    const headings = within(panelOf())
      .getAllByRole('heading', { level: 2 })
      .map((h) => h.textContent)

    // The panel title is an h2 too (UX-DR44 taken as written — see Q15), so it leads.
    expect(headings).toEqual([
      DECK_LIST_TITLE,
      COMMANDER_LABEL,
      GROUP_LABELS.Creature,
      GROUP_LABELS.Land,
      SIDEBOARD_LABEL,
    ])
  })

  it('counts SUMMED QUANTITIES, never row counts (AC 18, Q14)', () => {
    const { container } = render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    const counts = [...container.querySelectorAll('.group-header-count')].map((c) => c.textContent)
    // Lands: TWO rows, quantity 10 + 34 = 44. A row count would say "2" and would not move when
    // a quantity changed from 3 to 4 — the exact change UX-DR16 makes this the signal for.
    expect(counts).toEqual(['1', '4', '44', '2'])
  })

  it('omits empty groups and assumes no fixed set — 2 groups here, not 9 (AC 24)', () => {
    render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    const headings = within(panelOf())
      .getAllByRole('heading', { level: 2 })
      .map((h) => h.textContent)
    // The FULL list, not two named absences — an absence-only assertion would also pass with a
    // wrongly-present header. `Battle` (zero real decks) and `Instant` are covered by omission:
    // nothing beyond these five renders.
    expect(headings).toEqual([
      DECK_LIST_TITLE,
      COMMANDER_LABEL,
      GROUP_LABELS.Creature,
      GROUP_LABELS.Land,
      SIDEBOARD_LABEL,
    ])
  })

  it('renders a deck whose groups are eight wide, in TYPE_GROUPS order (AC 24)', () => {
    const eight = boardsOf([
      row('c', { type_line: 'Creature — Elf' }),
      row('p', { type_line: 'Legendary Planeswalker — Jace' }),
      row('i', { type_line: 'Instant' }),
      row('s', { type_line: 'Sorcery' }),
      row('a', { type_line: 'Artifact' }),
      row('e', { type_line: 'Enchantment' }),
      row('l', { type_line: 'Basic Land — Forest' }),
      row('o', { type_line: 'Card' }),
    ])
    render(<DeckList boards={eight} />)

    const headings = within(panelOf())
      .getAllByRole('heading', { level: 2 })
      .map((h) => h.textContent)
    expect(headings).toEqual([
      DECK_LIST_TITLE,
      GROUP_LABELS.Creature,
      GROUP_LABELS.Planeswalker,
      GROUP_LABELS.Instant,
      GROUP_LABELS.Sorcery,
      GROUP_LABELS.Artifact,
      GROUP_LABELS.Enchantment,
      GROUP_LABELS.Land,
      GROUP_LABELS.Other,
    ])
  })

  it('draws no commander or sideboard section when those boards are empty (AC 20, AC 21)', () => {
    render(<DeckList boards={boardsOf([row(CREATURE)])} />)

    const headings = within(panelOf())
      .getAllByRole('heading', { level: 2 })
      .map((h) => h.textContent)
    expect(headings).toEqual([DECK_LIST_TITLE, GROUP_LABELS.Creature])
  })

  it('draws the sideboard the GRID deliberately drops (AC 21)', () => {
    render(<DeckList boards={boardsOf(THREE_BOARDS)} />)

    // `CardGrid.test.tsx:98` — "does NOT render the sideboard … and c4-7 owns them". Discharged.
    const headings = within(panelOf()).getAllByRole('heading', { level: 2, name: SIDEBOARD_LABEL })
    expect(headings).toHaveLength(1)
    expect(within(panelOf()).getByRole('button', { name: /Duress/ })).toBeVisible()
  })
})

describe('conservation holds on screen (AC 22)', () => {
  it('every card lands in exactly one section, and the quantities sum', () => {
    const boards = boardsOf(THREE_BOARDS)
    const { container } = render(<DeckList boards={boards} />)

    // Every ROW is drawn exactly once — a card in two sections would double a count silently.
    expect(container.querySelectorAll('li.deck-list-item')).toHaveLength(THREE_BOARDS.length)

    // …and the DRAWN quantities sum to the derivation's own totals, which `deckGroups.ts:216-221`
    // ties to `mainboard_count` / `sideboard_count`. A row this panel failed to draw would be a
    // number in the deck header that stopped summing, with nothing on screen to say why.
    const drawn = [...container.querySelectorAll('.deck-row-quantity')].map((cell) =>
      Number(cell.textContent?.slice(1)),
    )
    const total = drawn.reduce((sum, n) => sum + n, 0)
    expect(total).toBe(
      boards.commanderQuantity + boards.mainboardQuantity + boards.sideboardQuantity,
    )
    expect(total).toBe(THREE_BOARDS.reduce((sum, entry) => sum + entry.quantity, 0))
  })
})

describe('the double-faced row — three shapes, one AC clause (AC 23, Q2)', () => {
  it('shows the FRONT face name, split from the summary', () => {
    render(
      <DeckList
        boards={boardsOf([
          row(DFC, {
            name: 'Clearwater Pathway // Murkwater Pathway',
            type_line: 'Land // Land',
            mana_cost: '',
          }),
        ])}
      />,
    )

    expect(within(panelOf()).getByText('Clearwater Pathway')).toBeVisible()
    expect(panelOf().textContent).not.toContain('Murkwater')
  })

  it('splits an ADVENTURE cost with no fetch at all — and no separator reaches the reader', () => {
    render(
      <DeckList
        boards={boardsOf([
          row(DFC, { name: 'Murderous Rider // Swift End', mana_cost: '{1}{B}{B} // {1}{B}{B}' }),
        ])}
      />,
    )

    const cost = within(panelOf()).getByRole('img')
    // The deferral at `deferred-work.md:1429-1445` — a `' // '` spoken as "slash slash" — is
    // closed BY CONSTRUCTION on this surface: the separator never reaches `ManaCost` from a row.
    expect(cost.getAttribute('aria-label')).not.toContain('//')
    expect(panelOf().textContent).not.toContain('//')
  })

  it('reads card_faces[0] for a TRANSFORM cost once hydration lands', () => {
    seedHydrated(DFC, {
      mana_cost: '',
      card_faces: [
        { name: 'Agadeem’s Awakening', mana_cost: '{X}{B}{B}{B}', type_line: 'Sorcery' },
        { name: 'Agadeem, the Undercrypt', mana_cost: '', type_line: 'Land' },
      ],
    })

    render(
      <DeckList
        boards={boardsOf([
          row(DFC, {
            name: 'Agadeem’s Awakening // Agadeem, the Undercrypt',
            type_line: 'Sorcery // Land',
            mana_cost: '',
          }),
        ])}
      />,
    )

    expect(within(panelOf()).getByRole('img').getAttribute('aria-label')).toMatch(/black/)
  })

  it('draws no pips at all before the sweep arrives — the stated first-paint cost', () => {
    render(
      <DeckList
        boards={boardsOf([
          row(DFC, { name: 'Agadeem’s Awakening // Agadeem, the Undercrypt', mana_cost: '' }),
        ])}
      />,
    )

    // 26 live rows across 18 cards look like this until the deck-wide sweep reaches them, and
    // c4-6's accepted no-re-drive window means a mid-sweep blip leaves them so until a reload.
    expect(within(panelOf()).queryAllByRole('img')).toHaveLength(0)
    expect(within(panelOf()).getByText('Agadeem’s Awakening')).toBeVisible()
  })

  it('leaves a GENUINELY costless card blank even after hydration', () => {
    seedHydrated(DFC, {
      mana_cost: '',
      card_faces: [
        { name: 'Clearwater Pathway', mana_cost: '', type_line: 'Land' },
        { name: 'Murkwater Pathway', mana_cost: '', type_line: 'Land' },
      ],
    })

    render(
      <DeckList
        boards={boardsOf([
          row(DFC, { name: 'Clearwater Pathway // Murkwater Pathway', mana_cost: '' }),
        ])}
      />,
    )

    expect(within(panelOf()).queryAllByRole('img')).toHaveLength(0)
  })
})

describe('a card with no image data or an unrecognised id (AC 15, Q11)', () => {
  it('renders IDENTICALLY to any other row, because the list is text-first', () => {
    // Q11: the wire CANNOT produce this — `DeckDetail.from_deck` validates a `CardSummary` per row
    // inside the response constructor, so a card-less entry raises rather than arriving. The
    // scenario is reachable only at the frontend CACHE tier, which is where it is exercised.
    useCardStore.setState((state) => ({
      cards: {
        ...state.cards,
        [CREATURE]: {
          status: 'unknown',
          reason: 'card_not_found',
          placeholder: 'unknown-card',
          summary: null,
          retryable: false,
        },
      },
    }))

    const { container } = render(
      <DeckList
        boards={boardsOf([
          row(CREATURE),
          row(LAND_A, { name: 'Forest', type_line: 'Basic Land — Forest' }),
        ])}
      />,
    )

    const rows = container.querySelectorAll('button.deck-row')
    expect(rows).toHaveLength(2)
    // Same three cells, same classes — no placeholder, no broken-image glyph, nothing special.
    for (const button of rows) {
      expect(button.className).toBe('deck-row')
      expect(button.children).toHaveLength(3)
    }
    // The summary is what the deck payload carries and it is never absent, so the row still
    // renders its name and quantity from it.
    expect(within(panelOf()).getByText('Llanowar Elves')).toBeVisible()
  })
})

describe('inspection — the second consumer, proving the API is location-agnostic (AC 25)', () => {
  it('attaches the five verbs to its own button, exactly as a tile does', () => {
    render(
      <DeckList
        boards={boardsOf([
          row(CREATURE),
          row(LAND_A, { name: 'Forest', type_line: 'Basic Land — Forest' }),
        ])}
      />,
    )

    const first = within(panelOf()).getByRole('button', { name: /Llanowar Elves/ })

    fireEvent.mouseEnter(first)
    expect(targetIdOf(useInspectionStore.getState())).toBe(CREATURE)

    fireEvent.mouseLeave(first)
    expect(useInspectionStore.getState().hoveredId).toBeNull()

    first.focus()
    expect(useInspectionStore.getState().focusedId).toBe(CREATURE)

    first.blur()
    expect(useInspectionStore.getState().focusedId).toBeNull()

    fireEvent.click(first)
    expect(useInspectionStore.getState().pinnedId).toBe(CREATURE)
  })

  it('marks the live row, and EXACTLY one (AC 13)', () => {
    const { container } = render(
      <DeckList
        boards={boardsOf([
          row(CREATURE),
          row(LAND_A, { name: 'Forest', type_line: 'Basic Land — Forest' }),
        ])}
      />,
    )

    fireEvent.mouseEnter(within(panelOf()).getByRole('button', { name: /Llanowar Elves/ }))
    expect(container.querySelectorAll('.deck-row.is-live')).toHaveLength(1)
  })

  it('keeps the clears KEYED BY ID across a three-row sweep (AC 26)', () => {
    // The default is a card the sweep never ENDS on (c4-7 review): with `LAND_B` as the default,
    // the closing assertion could not tell "hover won" from "fell back to the cold-open card" —
    // they were the same id. With `CREATURE` there, every mid- and end-sweep assertion below is
    // distinguishable from the fallback, and a wrongly-erased hover surfaces as `CREATURE`.
    setDefaultTarget(CREATURE)
    render(
      <DeckList
        boards={boardsOf([
          row(CREATURE),
          row(LAND_A, { name: 'Forest', type_line: 'Basic Land — Forest' }),
          row(LAND_B, { name: 'Swamp', type_line: 'Basic Land — Swamp' }),
        ])}
      />,
    )

    const panel = panelOf()
    const rows = [...panel.querySelectorAll('button.deck-row')]

    // The race `inspection.ts:239-241` describes, and it is TIGHTER here than on the grid: rows
    // are 24-30px tall against a tile's 246, so a pointer crosses an order of magnitude more of
    // them per second. Leaving one row and reaching the next produces two events and the LOSING
    // row's is free to land second.
    fireEvent.mouseEnter(rows[0])
    fireEvent.mouseEnter(rows[1])
    fireEvent.mouseLeave(rows[0]) // arrives LATE, and must not erase row 1's hover
    expect(targetIdOf(useInspectionStore.getState())).toBe(LAND_A)

    fireEvent.mouseEnter(rows[2])
    fireEvent.mouseLeave(rows[1])
    expect(targetIdOf(useInspectionStore.getState())).toBe(LAND_B)

    // No closing "not null" assertion: with the default now a DIFFERENT card, the two `toBe`
    // assertions above already prove hover won over the fallback — a tail `not.toBe(null)`
    // after `toBe(LAND_B)` was vacuous and is removed (c4-7 review).
  })

  it('resolves MIXED INPUT in both directions, and neither clear rewrites recency (AC 27)', () => {
    render(
      <DeckList
        boards={boardsOf([
          row(CREATURE),
          row(LAND_A, { name: 'Forest', type_line: 'Basic Land — Forest' }),
        ])}
      />,
    )

    const rows = [...panelOf().querySelectorAll<HTMLElement>('button.deck-row')]

    // Keyboard focus held on row 0 while the pointer sweeps row 1 — PR #44's P1. `lastTransient`
    // is 'hover', so the pointer wins while it is there…
    rows[0].focus()
    fireEvent.mouseEnter(rows[1])
    expect(targetIdOf(useInspectionStore.getState())).toBe(LAND_A)

    // …and when the pointer leaves, the STILL-FOCUSED row is what remains. With one shared slot
    // this `mouseleave` erased it and the panel snapped to the cold-open card.
    fireEvent.mouseLeave(rows[1])
    expect(targetIdOf(useInspectionStore.getState())).toBe(CREATURE)

    // The reverse: pointer first, then a focus lands elsewhere.
    fireEvent.mouseEnter(rows[0])
    rows[1].focus()
    expect(targetIdOf(useInspectionStore.getState())).toBe(LAND_A)
  })

  it('honours a pin over any hover, and releases on a second click', () => {
    render(
      <DeckList
        boards={boardsOf([
          row(CREATURE),
          row(LAND_A, { name: 'Forest', type_line: 'Basic Land — Forest' }),
        ])}
      />,
    )

    const rows = [...panelOf().querySelectorAll<HTMLElement>('button.deck-row')]
    fireEvent.click(rows[0])
    fireEvent.mouseEnter(rows[1])
    expect(targetIdOf(useInspectionStore.getState())).toBe(CREATURE)

    fireEvent.click(rows[0])
    expect(useInspectionStore.getState().pinnedId).toBeNull()
  })

  it('refuses an unknown-card id as an inspection target — the slice decides, not the row', () => {
    useCardStore.setState((state) => ({
      cards: {
        ...state.cards,
        [CREATURE]: {
          status: 'unknown',
          reason: 'card_not_found',
          placeholder: 'unknown-card',
          summary: null,
          retryable: false,
        },
      },
    }))
    render(<DeckList boards={boardsOf([row(CREATURE)])} />)

    fireEvent.mouseEnter(within(panelOf()).getByRole('button', { name: /Llanowar Elves/ }))
    // Refusal lives in the slice (`inspection.ts:182-185`), and the row does not second-guess it.
    expect(useInspectionStore.getState().hoveredId).toBeNull()
  })
})

describe('the panel re-derives nothing (AC 28)', () => {
  it('renders rows in the derivation’s order, not one of its own', () => {
    // A re-`sort()` is the second derivation AD-12 forbids, and it is invisible until someone
    // compares the two columns. The fixture is deliberately given in an order that is NOT the
    // rendered order: the land arrives before the creature, and `boardsOf` is what reorders them.
    const boards = boardsOf([
      row(LAND_A, { name: 'Forest', type_line: 'Basic Land — Forest' }),
      row(CREATURE, { name: 'Llanowar Elves' }),
    ])
    render(<DeckList boards={boards} />)

    const names = [...panelOf().querySelectorAll('.deck-row-name')].map((n) => n.textContent)
    expect(names).toEqual(['Llanowar Elves', 'Forest'])

    // …and it is the STORE's order, read back from the same value the grid receives.
    const expected = boards.mainboard.flatMap((group) => group.cards.map((c) => c.card.name))
    expect(names).toEqual(expected)
  })

  it('preserves the store’s order WITHIN a group, not just between groups (probe e)', () => {
    // THIS TEST EXISTS BECAUSE A PROBE PASSED. Probe (e) inserted a `.sort()` over
    // `section.cards` and the whole suite stayed green: every fixture above happened to put ONE
    // card in each type group, so a sort INSIDE a section had nothing to reorder. The assertion
    // was measuring between-group order — which `boardsOf` guarantees — and calling it proof of
    // within-group order, which nothing checked.
    //
    // Three creatures, deliberately given in an order that is NOT alphabetical, so any re-sort
    // this component performs is visible. `boardsOf` preserves input order within a group
    // (`main.filter(...)`), so the store's order IS the payload's order here.
    const boards = boardsOf([
      row('z', { name: 'Zealous Conscripts' }),
      row('a', { name: 'Avacyn, Angel of Hope' }),
      row('m', { name: 'Murktide Regent' }),
    ])
    render(<DeckList boards={boards} />)

    const names = [...panelOf().querySelectorAll('.deck-row-name')].map((n) => n.textContent)
    expect(names).toEqual(['Zealous Conscripts', 'Avacyn, Angel of Hope', 'Murktide Regent'])
    // Spelled out, so the failure message says which mistake was made: alphabetical is what a
    // well-meaning `.sort()` produces, and it is exactly what must NOT appear.
    expect(names).not.toEqual([...names].sort((x, y) => (x ?? '').localeCompare(y ?? '')))
    expect(names).toEqual(boards.mainboard[0].cards.map((c) => c.card.name))
  })

  it('holds no pin of its own — the slice is the only authority', () => {
    const { container } = render(<DeckList boards={boardsOf([row(CREATURE)])} />)

    // Written through the slice's own verb rather than a click, so the claim is about WHERE the
    // state lives rather than about this component's handler. `act` because the store write is
    // outside React's event system and the re-render must flush before the DOM is read.
    act(() => {
      togglePin(CREATURE)
    })
    expect(container.querySelectorAll('.deck-row.is-live')).toHaveLength(1)

    // …and clearing the slice clears the row, which is what "holds none of its own" means.
    act(() => {
      resetInspection()
    })
    expect(container.querySelectorAll('.deck-row.is-live')).toHaveLength(0)
  })
})

describe('a deck with no cards at all (Q16)', () => {
  it('renders the titled panel with no rows and NO invented sentence', () => {
    const { container } = render(<DeckList boards={boardsOf([])} />)

    // Not hidden: `EXPERIENCE.md` names exactly three panels to hide until a deck has cards — the
    // curve, the colour distribution and the format check — and this is not among them. c4-12
    // owns the empty-deck copy and ships AFTER this story, so inventing a line here would
    // pre-empt its copy AC and put unsourced words on the glass.
    expect(panelOf()).toBeVisible()
    expect(container.querySelectorAll('li.deck-list-item')).toHaveLength(0)
    expect(container.querySelectorAll('.group-header')).toHaveLength(0)
    expect(within(panelOf()).getAllByRole('heading', { level: 2 })).toHaveLength(1)
  })
})

describe('the label map is total over TypeGroup (AC 19, Q5)', () => {
  it('has a label for every group, and none it invented', () => {
    // The TYPE-level coupling lives in `DeckList.tsx` (an import-free `copy.ts` cannot carry a
    // `satisfies`); this is its runtime shadow, which also catches a label emptied to ''.
    const labels = Object.entries(GROUP_LABELS)
    expect(labels).toHaveLength(9)
    for (const [group, label] of labels) {
      expect(label.trim(), `${group} has no label`).not.toBe('')
      // Uppercasing is CSS's — a pre-uppercased string here would destroy the readable form for
      // anyone reading the accessible name or copying the text.
      expect(label).not.toBe(label.toUpperCase())
    }
  })

  it('does not put the store’s internal vocabulary on the glass', () => {
    render(<DeckList boards={boardsOf([row(CREATURE)])} />)
    // `TYPE_GROUPS` is singular ("Creature"); a header names a COLLECTION.
    expect(within(panelOf()).getByRole('heading', { level: 2, name: 'Creatures' })).toBeVisible()
  })
})

describe('hover on one row does not disturb another (the dense-list regression)', () => {
  it('leaves the other rows unmarked throughout a sweep', () => {
    const { container } = render(
      <DeckList
        boards={boardsOf([
          row(CREATURE),
          row(LAND_A, { name: 'Forest', type_line: 'Basic Land — Forest' }),
          row(LAND_B, { name: 'Swamp', type_line: 'Basic Land — Swamp' }),
        ])}
      />,
    )
    const rows = [...container.querySelectorAll('button.deck-row')]

    for (const button of rows) {
      fireEvent.mouseEnter(button)
      expect(container.querySelectorAll('.deck-row.is-live')).toHaveLength(1)
      expect(button.className).toContain('is-live')
      fireEvent.mouseLeave(button)
    }

    setHovered(CREATURE)
    clearHovered(CREATURE)
    expect(container.querySelectorAll('.deck-row.is-live')).toHaveLength(0)
  })
})
