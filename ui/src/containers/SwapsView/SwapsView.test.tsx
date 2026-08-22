import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Card, CardSummary } from '../../api/schema'
import { resetCardCache, useCardStore } from '../../state/cards'
import { resetFaces } from '../../state/faces'
import { resetInspection, useInspectionStore } from '../../state/inspection'
import { SwapsView } from './SwapsView'
import { emptyPushLine } from '../SuggestionsView/copy'

/**
 * The swaps view's body (story 16.1) — `SuggestionsView.test.tsx`'s harness, on the second
 * view kind. The same disclaimers apply: jsdom evaluates no stylesheet (the tints, the arrow's
 * colour and the micro role are read as SOURCE by `token-usage.test.ts`) and loads no images
 * (art states are driven manually). What this file proves is the BRANCH and the WIRING — which
 * element renders for which input, which handler reaches which store verb, and that one
 * malformed entry costs exactly one slot of one row.
 */

const TRADE = {
  out_card_id: 'c-out',
  in_card_id: 'c-in',
  rationale: 'Same role, one turn earlier.',
  out_qty: 2,
  in_qty: 2,
}
const OTHER = {
  out_card_id: 'c-out-2',
  in_card_id: 'c-in-2',
  rationale: 'Survives the format’s commonest removal spell.',
  out_qty: 4,
  in_qty: 4,
}

const summary = (id: string, over: Partial<CardSummary> = {}): CardSummary => ({
  id,
  name: `Card ${id}`,
  mana_cost: '{1}{G}',
  cmc: 2,
  type_line: 'Creature — Elf',
  oracle_text: '',
  colors: ['G'],
  rarity: 'common',
  set_code: 'tst',
  ...over,
})

const card = (id: string, over: Partial<Card> = {}): Card =>
  ({
    ...summary(id),
    oracle_id: `oracle-${id}`,
    set_name: 'Test Set',
    collector_number: '1',
    color_identity: ['G'],
    legalities: {},
    ...over,
  }) as Card

const seedHydrated = (id: string, over: Partial<Card> = {}) => {
  useCardStore.setState((state) => ({
    cards: { ...state.cards, [id]: { status: 'hydrated', card: card(id, over) } },
  }))
}

const seedUnknown = (id: string) => {
  useCardStore.setState((state) => ({
    cards: {
      ...state.cards,
      [id]: {
        status: 'unknown',
        reason: 'card_not_found',
        placeholder: 'unknown-card',
        summary: null,
        retryable: false,
      },
    },
  }))
}

const seedBoth = () => {
  for (const id of ['c-out', 'c-in', 'c-out-2', 'c-in-2']) seedHydrated(id)
}

const rows = (container: HTMLElement) => [...container.querySelectorAll<HTMLElement>('.swap-row')]

const rowAt = (container: HTMLElement, index: number) => {
  const found = rows(container)[index]
  expect(found, `no row at index ${index}`).toBeDefined()
  return found
}

const tilesOf = (row: HTMLElement) => [...row.querySelectorAll<HTMLButtonElement>('.swap-tile')]

beforeEach(() => {
  resetCardCache()
  resetInspection()
  resetFaces()
  // A read that never settles, so every test keeps the cache tier IT seeded.
  vi.stubGlobal(
    'fetch',
    vi.fn(() => new Promise(() => {})),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('an empty push renders the SHARED artefact line (AD-7, UX-DR33)', () => {
  it('renders the one template with the wire kind substituted — no second sentence authored', () => {
    render(<SwapsView kind="swaps" items={[]} />)

    expect(screen.getByText(emptyPushLine('swaps'))).toBeInTheDocument()
    expect(document.body.textContent).toContain('swaps')
    expect(document.body.textContent).not.toContain('{noun}')
  })

  it('is a bare paragraph REPLACING the list, exactly as the suggestions empty state is', () => {
    const { container } = render(<SwapsView kind="swaps" items={[]} />)

    const line = container.querySelector('.swaps-view-empty')
    expect(line?.tagName).toBe('P')
    expect(line).not.toHaveAttribute('aria-live')
    expect(screen.queryByRole('list')).toBeNull()
  })

  it('takes the kind from its PROP rather than assuming one', () => {
    render(<SwapsView kind="tier_list" items={[]} />)

    expect(screen.getByText(emptyPushLine('tier_list'))).toBeInTheDocument()
  })
})

describe('the rows, and their anatomy (DESIGN.md swap-row)', () => {
  it('renders a real ul/li — one li per trade, in payload order (UX-DR44)', () => {
    seedBoth()
    const { container } = render(<SwapsView kind="swaps" items={[TRADE, OTHER]} />)

    const list = screen.getByRole('list')
    expect(list.tagName).toBe('UL')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(rowAt(container, 0)).toHaveTextContent(TRADE.rationale)
    expect(rowAt(container, 1)).toHaveTextContent(OTHER.rationale)
    expect(container.querySelector('.swaps-view-empty')).toBeNull()
  })

  it('renders every slot the artefact names: tinted labels, arrow, rationale, confidence', () => {
    seedBoth()
    const { container } = render(
      <SwapsView kind="swaps" items={[{ ...TRADE, confidence: 'medium' }]} />,
    )
    const row = rowAt(container, 0)

    // The two labels, with the literal wording `contracts.py` fixes — and the tint CLASSES on
    // the labels only (the colours themselves are the stylesheet's, invisible to jsdom).
    const labels = [...row.querySelectorAll('.swap-tile-label')]
    expect(labels.map((l) => l.textContent)).toEqual(['Out · 2 copies', 'In · 2 copies'])
    expect(labels[0]).toHaveClass('swap-tile-label-out')
    expect(labels[1]).toHaveClass('swap-tile-label-in')
    // Tints never touch the art: no variant class anywhere near an image element.
    expect(row.querySelector('.swap-tile-image')).not.toHaveClass('swap-tile-label-out')

    // The arrow joins the pair and is decorative — the labels already carry the direction.
    const arrow = row.querySelector('.swap-row-arrow')
    expect(arrow).toHaveTextContent('→')
    expect(arrow).toHaveAttribute('aria-hidden', 'true')

    expect(row.querySelector('.swap-row-rationale')).toHaveTextContent(TRADE.rationale)
    // The confidence is a real StatChip beneath the rationale — label authored, value the wire
    // token — and price/curve chips do NOT ship (the wire carries no price by ruling).
    const chip = row.querySelector('.stat-chip')
    expect(chip?.querySelector('.stat-chip-label')).toHaveTextContent('Confidence')
    expect(chip?.querySelector('.stat-chip-value')).toHaveTextContent('medium')
    expect(chip?.querySelector('.stat-chip-delta')).toBeNull()
    expect(row.querySelectorAll('.stat-chip')).toHaveLength(1)
  })

  it('renders "In · 0 copies" for a zero-copy in-card — zero is a designed case, not an error', () => {
    seedBoth()
    const { container } = render(<SwapsView kind="swaps" items={[{ ...TRADE, in_qty: 0 }]} />)

    const labels = [...rowAt(container, 0).querySelectorAll('.swap-tile-label')]
    expect(labels[1]).toHaveTextContent('In · 0 copies')
  })

  it('renders no confidence chip when it is absent, and refuses a non-token value', () => {
    seedBoth()
    const { container } = render(
      <SwapsView
        kind="swaps"
        items={[TRADE, { ...OTHER, confidence: 'certain' } as unknown as typeof OTHER]}
      />,
    )

    expect(rowAt(container, 0).querySelector('.stat-chip')).toBeNull()
    expect(rowAt(container, 1).querySelector('.stat-chip')).toBeNull()
    // The rest of the refused row is untouched — one bad field is not a bad row.
    expect(rowAt(container, 1)).toHaveTextContent(OTHER.rationale)
  })

  it('draws both thumbnails from the backend proxy with alt="" exactly (AD-11, UX-DR48)', () => {
    seedBoth()
    const { container } = render(<SwapsView kind="swaps" items={[TRADE]} />)

    const images = [...rowAt(container, 0).querySelectorAll('.swap-tile-image')]
    expect(images.map((i) => i.getAttribute('src'))).toEqual([
      '/api/card-image/c-out',
      '/api/card-image/c-in',
    ])
    for (const image of images) {
      expect(image).toHaveAttribute('alt', '')
      expect(image).toHaveClass('card-shape')
      expect(image).not.toHaveAttribute('style')
      expect(image.getAttribute('src')).not.toContain('size=')
    }
  })

  it('renders duplicate trades as separate rows, with no key collision', () => {
    seedBoth()
    const { container } = render(
      <SwapsView kind="swaps" items={[TRADE, { ...TRADE, rationale: 'And in the sideboard.' }]} />,
    )

    expect(rows(container)).toHaveLength(2)
    expect(rowAt(container, 1)).toHaveTextContent('And in the sideboard.')
  })
})

describe('one bad entry costs one slot of one row, never the push (FR-13, AD-7)', () => {
  it('degrades an unknown OUT id to the placeholder while the row’s text still renders', () => {
    seedUnknown('c-out')
    seedHydrated('c-in')
    const { container } = render(<SwapsView kind="swaps" items={[TRADE]} />)
    const [outTile, inTile] = tilesOf(rowAt(container, 0))

    expect(outTile.querySelector('.card-placeholder')).toHaveTextContent('Unknown card')
    expect(outTile.querySelector('.swap-tile-image')).toBeNull()
    // The IN tile and the row's words are untouched: one dead id, one dead thumbnail.
    expect(inTile.querySelector('.swap-tile-image')).toHaveAttribute('src', '/api/card-image/c-in')
    expect(rowAt(container, 0)).toHaveTextContent(TRADE.rationale)
  })

  it('renders NON-STRING ids as unknown placeholders and never throws', () => {
    const malformed = [
      { ...TRADE, out_card_id: 42, in_card_id: null },
      { ...OTHER, out_card_id: undefined, in_card_id: { id: 'c-in' } },
    ] as unknown as (typeof TRADE)[]

    const { container } = render(<SwapsView kind="swaps" items={malformed} />)

    expect(rows(container)).toHaveLength(2)
    for (const [index, item] of malformed.entries()) {
      const row = rowAt(container, index)
      expect(row.querySelectorAll('.card-placeholder')).not.toHaveLength(0)
      expect(row).toHaveTextContent(item.rationale)
      expect(row.querySelector('.swap-tile-image')).toBeNull()
    }
  })

  it('renders a missing or non-string rationale as an empty line, row otherwise normal', () => {
    seedBoth()
    const malformed = [
      { ...TRADE, rationale: undefined },
      { ...TRADE, rationale: 7 },
    ] as unknown as (typeof TRADE)[]

    const { container } = render(<SwapsView kind="swaps" items={malformed} />)

    for (const [index] of malformed.entries()) {
      const line = rowAt(container, index).querySelector('.swap-row-rationale')
      // The ELEMENT is present either way — dropping it would silently change the row's height.
      expect(line, `row ${index} lost its rationale line`).not.toBeNull()
      expect(line).toBeEmptyDOMElement()
      expect(rowAt(container, index).querySelectorAll('.swap-tile-image')).toHaveLength(2)
    }
  })

  it('drops the count from a label whose quantity is malformed, fabricating no number', () => {
    seedBoth()
    const { container } = render(
      <SwapsView
        kind="swaps"
        items={[{ ...TRADE, out_qty: 'two', in_qty: -1 } as unknown as typeof TRADE]}
      />,
    )

    const labels = [...rowAt(container, 0).querySelectorAll('.swap-tile-label')]
    expect(labels[0]).toHaveTextContent(/^Out$/)
    expect(labels[1]).toHaveTextContent(/^In$/)
    expect(rowAt(container, 0).textContent).not.toContain('NaN')
  })

  it('renders a bare null array element as a fully degraded row, not a crash', () => {
    const { container } = render(
      <SwapsView kind="swaps" items={[null] as unknown as (typeof TRADE)[]} />,
    )

    expect(rows(container)).toHaveLength(1)
    expect(rowAt(container, 0).querySelectorAll('.card-placeholder')).toHaveLength(2)
  })
})

describe('the inspection contract on BOTH tiles (UX-DR14, UX-DR20, UX-DR22)', () => {
  it('sets the detail target per tile on hover and focus, and pins on click', () => {
    seedBoth()
    const { container } = render(<SwapsView kind="swaps" items={[TRADE]} />)
    const [outTile, inTile] = tilesOf(rowAt(container, 0))

    fireEvent.mouseEnter(outTile)
    expect(useInspectionStore.getState().hoveredId).toBe('c-out')
    fireEvent.mouseLeave(outTile)
    expect(useInspectionStore.getState().hoveredId).toBeNull()

    fireEvent.focus(inTile)
    expect(useInspectionStore.getState().focusedId).toBe('c-in')
    fireEvent.blur(inTile)
    expect(useInspectionStore.getState().focusedId).toBeNull()

    fireEvent.click(inTile)
    expect(useInspectionStore.getState().pinnedId).toBe('c-in')
    // A second single click releases (UX-DR20) — never a double-click semantic.
    fireEvent.click(inTile)
    expect(useInspectionStore.getState().pinnedId).toBeNull()
  })

  it('is two real <button>s per row, with no tabindex and no keydown handler (UX-DR39/40)', () => {
    seedBoth()
    const { container } = render(<SwapsView kind="swaps" items={[TRADE]} />)
    const tiles = tilesOf(rowAt(container, 0))

    expect(tiles).toHaveLength(2)
    for (const tile of tiles) {
      expect(tile.tagName).toBe('BUTTON')
      expect(tile).toHaveAttribute('type', 'button')
      expect(tile).not.toHaveAttribute('tabindex')
    }
    expect(screen.getAllByRole('button')).toHaveLength(2)
    // The tile's accessible name is the label — the reader's handle on which side it holds.
    expect(screen.getByRole('button', { name: /Out · 2 copies/ })).toBe(tiles[0])
  })

  it('REFUSES every verb on an unknown tile through the store, and stays a button (Q3)', () => {
    seedUnknown('c-out')
    seedHydrated('c-in')
    const { container } = render(<SwapsView kind="swaps" items={[TRADE]} />)
    const [outTile] = tilesOf(rowAt(container, 0))

    fireEvent.mouseEnter(outTile)
    fireEvent.focus(outTile)
    fireEvent.click(outTile)

    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(useInspectionStore.getState().focusedId).toBeNull()
    expect(useInspectionStore.getState().pinnedId).toBeNull()
    expect(outTile.tagName).toBe('BUTTON')
    expect(outTile).not.toBeDisabled()

    // The non-vacuity control (the plant-3 lesson): the same tile, re-armed, proves the
    // handlers were wired all along and the STORE did the refusing.
    act(() => seedHydrated('c-out'))
    fireEvent.mouseEnter(tilesOf(rowAt(container, 0))[0])
    expect(useInspectionStore.getState().hoveredId).toBe('c-out')
  })

  it('releases a stale hover, focus AND pin when an entry settles to unknown (Greptile P1)', () => {
    const { container } = render(<SwapsView kind="swaps" items={[TRADE]} />)
    const [outTile] = tilesOf(rowAt(container, 0))

    fireEvent.mouseEnter(outTile)
    fireEvent.focus(outTile)
    fireEvent.click(outTile)
    expect(useInspectionStore.getState().pinnedId).toBe('c-out')

    act(() => seedUnknown('c-out'))

    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(useInspectionStore.getState().focusedId).toBeNull()
    expect(useInspectionStore.getState().pinnedId).toBeNull()
  })

  it('only releases the id that went unknown, never the sibling tile’s target', () => {
    seedHydrated('c-in')
    const { container } = render(<SwapsView kind="swaps" items={[TRADE]} />)
    const [, inTile] = tilesOf(rowAt(container, 0))

    fireEvent.click(inTile)
    expect(useInspectionStore.getState().pinnedId).toBe('c-in')

    act(() => seedUnknown('c-out'))

    expect(useInspectionStore.getState().pinnedId).toBe('c-in')
  })
})

describe('hydration is this view’s own, both sides of every trade (AD-12)', () => {
  const cardCalls = () =>
    (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls
      .map(([input]) => String(input))
      .filter((path) => path.startsWith('/api/cards/'))

  it('asks once per UNIQUE id across sides and rows', () => {
    render(
      <SwapsView
        kind="swaps"
        items={[TRADE, { ...OTHER, in_card_id: 'c-out' }]} // `c-out` appears on both sides
      />,
    )

    // Two trades, four id slots, three distinct ids — three reads. The `Set` collapses a card
    // traded out of one slot and into another.
    expect(cardCalls()).toHaveLength(3)
    expect(cardCalls()).toContain('/api/cards/c-out')
    expect(cardCalls()).toContain('/api/cards/c-in')
    expect(cardCalls()).toContain('/api/cards/c-out-2')
  })

  it('re-hydrates when ITEMS change — replace-in-place brings new ids', () => {
    const { rerender } = render(<SwapsView kind="swaps" items={[TRADE]} />)
    expect(cardCalls()).toHaveLength(2)

    rerender(<SwapsView kind="swaps" items={[OTHER]} />)

    expect(cardCalls()).toContain('/api/cards/c-out-2')
    expect(cardCalls()).toContain('/api/cards/c-in-2')
    expect(cardCalls()).toHaveLength(4)
  })

  it('asks for nothing on an empty push, and nothing for a malformed id', () => {
    render(
      <SwapsView
        kind="swaps"
        items={[{ ...TRADE, out_card_id: null } as unknown as typeof TRADE]}
      />,
    )

    // The malformed slot cost no request (`hydrateCard('')` refuses terminally); the good id
    // was still asked for — one bad field, one silent slot.
    expect(cardCalls()).toEqual(['/api/cards/c-in'])
  })
})
