import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Card, CardSummary, TierItem } from '../../api/schema'
import { resetCardCache, useCardStore } from '../../state/cards'
import { resetFaces, useFaceStore } from '../../state/faces'
import { resetInspection, useInspectionStore } from '../../state/inspection'
import { TierListView } from './TierListView'
import { emptyPushLine } from '../SuggestionsView/copy'

/**
 * The tier-list view's body (story 16.2) — `SwapsView.test.tsx`'s harness, on the third view
 * kind. The same disclaimers apply: jsdom evaluates no stylesheet (the letter ramp, the chip
 * surface and the micro role are read as SOURCE by `token-usage.test.ts` and the shell guards)
 * and loads no images (art states are driven manually). What this file proves is the BRANCH and
 * the WIRING — which element renders for which input, which handler reaches which store verb,
 * that an empty or malformed tier is skipped while its neighbours render, and that one bad card
 * id costs exactly one thumbnail of one tier.
 */

// Typed through the ALIAS (`schema.ts` is the one home for a wire-derived shape — declaring a
// local `TierItem` is what `tests/wire-contract.test.ts` bans), so a fixture that drifted from
// the generated model would fail to compile rather than silently testing a shape of its own.
const TIER: TierItem = {
  letter: 'S',
  name: 'Auto-include',
  note: 'Never leaves the deck.',
  card_ids: ['c-tier-1', 'c-tier-2'],
}

const OTHER: TierItem = {
  letter: 'A',
  name: 'Strong',
  card_ids: ['c-tier-3'],
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

const seedAll = () => {
  for (const id of ['c-tier-1', 'c-tier-2', 'c-tier-3']) seedHydrated(id)
}

const rows = (container: HTMLElement) => [...container.querySelectorAll<HTMLElement>('.tier-row')]

const rowAt = (container: HTMLElement, index: number) => {
  const found = rows(container)[index]
  expect(found, `no row at index ${index}`).toBeDefined()
  return found
}

const tilesOf = (row: HTMLElement) => [...row.querySelectorAll<HTMLButtonElement>('.tier-tile')]

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
  it('renders the one template with the kind’s display noun — no second sentence authored', () => {
    render(<TierListView kind="tier_list" items={[]} />)

    expect(screen.getByText(emptyPushLine('tier_list'))).toBeInTheDocument()
    // The epic-16 retro item-4 repair, asserted at THIS kind because it was the defect's worst
    // data point: the glass shows the display noun, never the wire literal's underscore.
    expect(document.body.textContent).toContain('tier list')
    expect(document.body.textContent).not.toContain('tier_list')
    expect(document.body.textContent).not.toContain('{noun}')
  })

  it('is a bare paragraph REPLACING the list, exactly as both siblings’ empty states are', () => {
    const { container } = render(<TierListView kind="tier_list" items={[]} />)

    const line = container.querySelector('.tier-list-view-empty')
    expect(line?.tagName).toBe('P')
    expect(line).not.toHaveAttribute('aria-live')
    expect(screen.queryByRole('list')).toBeNull()
  })

  it('takes the kind from its PROP rather than assuming one', () => {
    render(<TierListView kind="groups" items={[]} />)

    expect(screen.getByText(emptyPushLine('groups'))).toBeInTheDocument()
  })
})

describe('the rows, and their anatomy (DESIGN.md tier-row)', () => {
  it('renders a real ul/li — one li per tier, in payload order, never re-sorted (UX-DR44)', () => {
    seedAll()
    // `A` before `S`, deliberately: payload order is render order, and a view that sorted by
    // letter would pass an in-order fixture while silently rewriting the agent's argument.
    const { container } = render(<TierListView kind="tier_list" items={[OTHER, TIER]} />)

    const list = screen.getByRole('list')
    expect(list.tagName).toBe('UL')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(rowAt(container, 0).querySelector('.tier-chip-letter')).toHaveTextContent('A')
    expect(rowAt(container, 1).querySelector('.tier-chip-letter')).toHaveTextContent('S')
    expect(container.querySelector('.tier-list-view-empty')).toBeNull()
  })

  it('renders every slot the artefact names: ramped letter, name beneath, note, thumbnails', () => {
    seedAll()
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    const row = rowAt(container, 0)

    // The letter carries its ramp hook (`data-letter` — the colours themselves are the
    // stylesheet's, invisible to jsdom) and is presentational: the NAME beside it is the
    // accessible carrier of rank, so colour and glyph are never the sole signal.
    const letter = row.querySelector('.tier-chip-letter')
    expect(letter).toHaveTextContent('S')
    expect(letter).toHaveAttribute('data-letter', 'S')
    expect(letter).toHaveAttribute('aria-hidden', 'true')
    expect(row.querySelector('.tier-chip-name')).toHaveTextContent(TIER.name)

    expect(row.querySelector('.tier-row-note')).toHaveTextContent(TIER.note!)
    expect(tilesOf(row)).toHaveLength(2)
  })

  it('renders NO note element when the note is absent — optional by design, not malformed', () => {
    seedAll()
    const { container } = render(<TierListView kind="tier_list" items={[OTHER]} />)

    expect(rowAt(container, 0).querySelector('.tier-row-note')).toBeNull()
    // …and the rest of the row is whole: chip, name, thumbnail.
    expect(rowAt(container, 0).querySelector('.tier-chip-name')).toHaveTextContent(OTHER.name)
    expect(tilesOf(rowAt(container, 0))).toHaveLength(1)
  })

  it('renders NO note element for a whitespace-only note — blank is wire-reachable here', () => {
    // Unlike `name`, `contracts.py` blank-checks `note` not at all (length cap only), so a
    // blank note is a LEGAL payload rather than a malformed one — and an empty element would
    // spend the body column's gap on a blank line. The tier itself is untouched.
    seedAll()
    const { container } = render(
      <TierListView kind="tier_list" items={[{ ...TIER, note: '   ' }]} />,
    )

    expect(rowAt(container, 0).querySelector('.tier-row-note')).toBeNull()
    expect(rowAt(container, 0).querySelector('.tier-chip-name')).toHaveTextContent(TIER.name)
    expect(tilesOf(rowAt(container, 0))).toHaveLength(2)
  })

  it('renders two tiers sharing a LETTER under different names — repetition is legal', () => {
    seedAll()
    const { container } = render(
      <TierListView
        kind="tier_list"
        items={[TIER, { letter: 'S', name: 'Also essential', card_ids: ['c-tier-3'] }]}
      />,
    )

    expect(rows(container)).toHaveLength(2)
    expect(rowAt(container, 1).querySelector('.tier-chip-name')).toHaveTextContent('Also essential')
  })

  it('draws every thumbnail from the backend proxy with alt="" exactly (AD-11, UX-DR48)', () => {
    seedAll()
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)

    const images = [...rowAt(container, 0).querySelectorAll('.tier-tile-image')]
    expect(images.map((i) => i.getAttribute('src'))).toEqual([
      '/api/card-image/c-tier-1',
      '/api/card-image/c-tier-2',
    ])
    for (const image of images) {
      expect(image).toHaveAttribute('alt', '')
      expect(image).toHaveClass('card-shape')
      expect(image).not.toHaveAttribute('style')
      expect(image.getAttribute('src')).not.toContain('size=')
    }
  })
})

describe('empty and malformed tiers are skipped; neighbours render (DESIGN.md:590, FR-13/AD-7)', () => {
  it('skips an EMPTY tier entirely — no shell, no chip, no empty strip', () => {
    seedAll()
    const { container } = render(
      <TierListView
        kind="tier_list"
        items={[TIER, { letter: 'D', name: 'Cut', card_ids: [] }, OTHER]}
      />,
    )

    // Two rendered rows, and neither is the empty one — the skip is by anatomy, not by index.
    expect(rows(container)).toHaveLength(2)
    expect(container.textContent).not.toContain('Cut')
    expect(rowAt(container, 0).querySelector('.tier-chip-name')).toHaveTextContent(TIER.name)
    expect(rowAt(container, 1).querySelector('.tier-chip-name')).toHaveTextContent(OTHER.name)
  })

  it('degrades a tier with a letter outside S/A/B/C/D — the ramp has no sixth stop', () => {
    seedAll()
    const malformed = { letter: 'F', name: 'Trash', card_ids: ['c-tier-3'] }
    const { container } = render(
      <TierListView kind="tier_list" items={[malformed, TIER] as unknown as (typeof TIER)[]} />,
    )

    expect(rows(container)).toHaveLength(1)
    expect(container.textContent).not.toContain('Trash')
    expect(rowAt(container, 0).querySelector('.tier-chip-name')).toHaveTextContent(TIER.name)
  })

  it('degrades a tier whose name is missing or blank — the letter never stands alone', () => {
    seedAll()
    const malformed = [
      { letter: 'A', card_ids: ['c-tier-3'] },
      { letter: 'B', name: '   ', card_ids: ['c-tier-3'] },
      TIER,
    ] as unknown as (typeof TIER)[]

    const { container } = render(<TierListView kind="tier_list" items={malformed} />)

    // Only the healthy tier renders: a chip with a colour-ramped letter and no accessible name
    // beneath it is exactly the colour-as-sole-carrier state the wire's non-blank rule forbids.
    expect(rows(container)).toHaveLength(1)
    expect(rowAt(container, 0).querySelector('.tier-chip-name')).toHaveTextContent(TIER.name)
  })

  it('renders a bare null array element and a non-array card_ids as skips, never a crash', () => {
    seedAll()
    const malformed = [
      null,
      { letter: 'C', name: 'Filler', card_ids: 'c-tier-3' },
      TIER,
    ] as unknown as (typeof TIER)[]

    const { container } = render(<TierListView kind="tier_list" items={malformed} />)

    expect(rows(container)).toHaveLength(1)
    expect(rowAt(container, 0).querySelector('.tier-chip-name')).toHaveTextContent(TIER.name)
  })

  it('degrades an unknown card id to the placeholder while the tier’s text still renders', () => {
    seedUnknown('c-tier-1')
    seedHydrated('c-tier-2')
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    const [deadTile, liveTile] = tilesOf(rowAt(container, 0))

    expect(deadTile.querySelector('.card-placeholder')).toHaveTextContent('Unknown card')
    expect(deadTile.querySelector('.tier-tile-image')).toBeNull()
    // The sibling tile and the tier's words are untouched: one dead id, one dead thumbnail.
    expect(liveTile.querySelector('.tier-tile-image')).toHaveAttribute(
      'src',
      '/api/card-image/c-tier-2',
    )
    expect(rowAt(container, 0).querySelector('.tier-chip-name')).toHaveTextContent(TIER.name)
    expect(rowAt(container, 0).querySelector('.tier-row-note')).toHaveTextContent(TIER.note!)
  })

  it('filters a NON-STRING id inside a tier — the good neighbour renders alone, no crash', () => {
    // E16-91: `cardIdsOf` now FILTERS per id (GroupsView's gate) rather than coercing to `''`,
    // so a number never spends a permanently-dead placeholder slot — the tier renders exactly
    // the ids the app could ever render.
    seedAll()
    const withBadId = {
      letter: 'B',
      name: 'Playable',
      card_ids: [42, 'c-tier-3'],
    } as unknown as typeof TIER

    const { container } = render(<TierListView kind="tier_list" items={[withBadId]} />)

    // The tier still counts as non-empty (one valid id survived), the bad slot is dropped.
    expect(rows(container)).toHaveLength(1)
    const tiles = tilesOf(rowAt(container, 0))
    expect(tiles).toHaveLength(1)
    expect(tiles[0].querySelector('img')).toHaveAttribute('src', '/api/card-image/c-tier-3')
  })

  it('filters an empty or whitespace-only id — it never renders, never counts, never hydrates', () => {
    // E16-91, `GroupsView.test.tsx`'s pin cloned: a blank id names nothing the app could ever
    // render, and a whitespace-only one would even commit a real `/api/card-image/%20` request
    // before hydration settled. `cardIdsOf` drops both, so the strip and the hydration effect
    // read the same one-entry list.
    seedAll()
    const withBlankIds = {
      letter: 'B',
      name: 'Mostly blank',
      card_ids: ['', '  ', 'c-tier-3'],
    } as unknown as typeof TIER

    const { container } = render(<TierListView kind="tier_list" items={[withBlankIds]} />)

    expect(rows(container)).toHaveLength(1)
    const tiles = tilesOf(rowAt(container, 0))
    expect(tiles).toHaveLength(1)
    expect(tiles[0].querySelector('img')).toHaveAttribute('src', '/api/card-image/c-tier-3')
  })

  it('renders the shared line when EVERY tier is skipped — never an empty list shell', () => {
    const { container } = render(
      <TierListView kind="tier_list" items={[{ letter: 'S', name: 'Empty rank', card_ids: [] }]} />,
    )

    // An empty `<ul>` would announce "list, 0 items" with nothing to explain why; the one
    // shared sentence replaces it, and no second sentence is authored for this state.
    expect(screen.queryByRole('list')).toBeNull()
    expect(container.querySelector('.tier-list-view-empty')).toHaveTextContent(
      emptyPushLine('tier_list'),
    )
  })
})

describe('the inspection contract on EVERY tile (UX-DR14, UX-DR20, UX-DR22)', () => {
  it('sets the detail target per tile on hover and focus, and pins on click', () => {
    seedAll()
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    const [first, second] = tilesOf(rowAt(container, 0))

    fireEvent.mouseEnter(first)
    expect(useInspectionStore.getState().hoveredId).toBe('c-tier-1')
    fireEvent.mouseLeave(first)
    expect(useInspectionStore.getState().hoveredId).toBeNull()

    fireEvent.focus(second)
    expect(useInspectionStore.getState().focusedId).toBe('c-tier-2')
    fireEvent.blur(second)
    expect(useInspectionStore.getState().focusedId).toBeNull()

    fireEvent.click(second)
    expect(useInspectionStore.getState().pinnedId).toBe('c-tier-2')
    // A second single click releases (UX-DR20) — never a double-click semantic.
    fireEvent.click(second)
    expect(useInspectionStore.getState().pinnedId).toBeNull()
  })

  it('is one real <button> per card, named by the card, with no tabindex (UX-DR39/40/48)', () => {
    seedAll()
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    const tiles = tilesOf(rowAt(container, 0))

    expect(tiles).toHaveLength(2)
    for (const tile of tiles) {
      expect(tile.tagName).toBe('BUTTON')
      expect(tile).toHaveAttribute('type', 'button')
      expect(tile).not.toHaveAttribute('tabindex')
    }
    expect(screen.getAllByRole('button')).toHaveLength(2)
    // The tile's accessible name is the CARD's name (wire data, visually hidden) — the image's
    // alt stays "" and the strip has no label element the way a swap tile does, so without
    // this every tile would be an anonymous Tab stop.
    expect(screen.getByRole('button', { name: 'Card c-tier-1' })).toBe(tiles[0])
  })

  it('REFUSES every verb on an unknown tile through the store, and stays a button (Q3)', () => {
    seedUnknown('c-tier-1')
    seedHydrated('c-tier-2')
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    const [deadTile] = tilesOf(rowAt(container, 0))

    fireEvent.mouseEnter(deadTile)
    fireEvent.focus(deadTile)
    fireEvent.click(deadTile)

    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(useInspectionStore.getState().focusedId).toBeNull()
    expect(useInspectionStore.getState().pinnedId).toBeNull()
    expect(deadTile.tagName).toBe('BUTTON')
    expect(deadTile).not.toBeDisabled()

    // The non-vacuity control (the plant-3 lesson): the same tile, re-armed, proves the
    // handlers were wired all along and the STORE did the refusing.
    act(() => seedHydrated('c-tier-1'))
    fireEvent.mouseEnter(tilesOf(rowAt(container, 0))[0])
    expect(useInspectionStore.getState().hoveredId).toBe('c-tier-1')
  })

  it('releases a stale hover, focus AND pin when an entry settles to unknown (Greptile P1)', () => {
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    const [first] = tilesOf(rowAt(container, 0))

    fireEvent.mouseEnter(first)
    fireEvent.focus(first)
    fireEvent.click(first)
    expect(useInspectionStore.getState().pinnedId).toBe('c-tier-1')

    act(() => seedUnknown('c-tier-1'))

    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(useInspectionStore.getState().focusedId).toBeNull()
    expect(useInspectionStore.getState().pinnedId).toBeNull()
  })

  it('only releases the id that went unknown, never a sibling tile’s target', () => {
    seedHydrated('c-tier-2')
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    const [, second] = tilesOf(rowAt(container, 0))

    fireEvent.click(second)
    expect(useInspectionStore.getState().pinnedId).toBe('c-tier-2')

    act(() => seedUnknown('c-tier-1'))

    expect(useInspectionStore.getState().pinnedId).toBe('c-tier-2')
  })
})

describe('the in-view preview (DESIGN.md components.tier-preview, added 2026-08-23)', () => {
  // jsdom's usual disclaimers apply one more time: the two-column grid, the 176px/300px tracks,
  // the sticky positioning and the ≤1100px collapse are all stylesheet claims. The load-bearing
  // rules — the thumb's real width, unshrinkable tiles, scroll-not-wrap, the preview's media
  // collapse — are pinned as SOURCE by `shell.test.ts`'s tier-strip rule-reading guard; the
  // rendered geometry (that it all LOOKS right in a real browser) is the manual checklist's.
  // What THIS block proves is the wiring: the preview reads the inspection store's resolution
  // and renders wire data through the tile's own placeholder ladder, silently.
  const previewOf = (container: HTMLElement) =>
    container.querySelector<HTMLElement>('.tier-preview')

  it('renders beside the rows — and NOT for an empty or all-skipped push', () => {
    seedAll()
    const healthy = render(<TierListView kind="tier_list" items={[TIER]} />)
    expect(previewOf(healthy.container)).not.toBeNull()
    healthy.unmount()

    const empty = render(<TierListView kind="tier_list" items={[]} />)
    expect(previewOf(empty.container)).toBeNull()
    empty.unmount()

    const skipped = render(
      <TierListView kind="tier_list" items={[{ letter: 'S', name: 'Bare', card_ids: [] }]} />,
    )
    expect(previewOf(skipped.container)).toBeNull()
    skipped.unmount()
  })

  it('shows the SILENT loading well while nothing is hovered, focused or pinned', () => {
    seedAll()
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    const preview = previewOf(container)!

    expect(preview.querySelector('.card-placeholder-well')).not.toBeNull()
    expect(preview.querySelector('.tier-preview-image')).toBeNull()
    // Wordless: the empty state authors NOTHING — no copy module entry exists to cite. This
    // also pins the SHARED loading variant's silence: `CardPlaceholder`'s well renders no
    // text, visually hidden or otherwise, so a change giving that primitive words fails here
    // knowingly rather than leaking copy into a surface built to be silent.
    expect(preview.textContent).toBe('')
  })

  it('tracks hover: the card’s art, name, cost and type render from the cache', () => {
    seedAll()
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    const [first] = tilesOf(rowAt(container, 0))

    fireEvent.mouseEnter(first)

    const preview = previewOf(container)!
    expect(preview.querySelector('.tier-preview-image')).toHaveAttribute(
      'src',
      '/api/card-image/c-tier-1',
    )
    // Rendition UNSPELLED, so a hover is a warm browser-cache hit for a drawn thumbnail.
    expect(preview.querySelector('.tier-preview-image')!.getAttribute('src')).not.toContain('size=')
    expect(preview.querySelector('.tier-preview-image')).toHaveAttribute('alt', '')
    expect(preview.querySelector('.tier-preview-name')).toHaveTextContent('Card c-tier-1')
    expect(preview.querySelector('.tier-preview-type')).toHaveTextContent('Creature — Elf')
    // The cost as pips — `ManaCost` builds its own accessible name from the parsed string.
    expect(preview.querySelector('.mana-cost')).not.toBeNull()

    // The pointer leaves with nothing pinned: the preview falls back to the silent well.
    fireEvent.mouseLeave(first)
    expect(preview.querySelector('.card-placeholder-well')).not.toBeNull()
    expect(preview.textContent).toBe('')
  })

  it('tracks keyboard focus with full parity (UX-DR14)', () => {
    seedAll()
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    const [, second] = tilesOf(rowAt(container, 0))

    fireEvent.focus(second)
    expect(previewOf(container)!.querySelector('.tier-preview-name')).toHaveTextContent(
      'Card c-tier-2',
    )

    fireEvent.blur(second)
    expect(previewOf(container)!.querySelector('.card-placeholder-well')).not.toBeNull()
  })

  it('keeps a PINNED card after the pointer leaves — the store’s precedence, not its own', () => {
    seedAll()
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    const [first] = tilesOf(rowAt(container, 0))

    fireEvent.mouseEnter(first)
    fireEvent.click(first)
    fireEvent.mouseLeave(first)

    expect(previewOf(container)!.querySelector('.tier-preview-name')).toHaveTextContent(
      'Card c-tier-1',
    )

    // A second single click releases, and the preview lets go with the store.
    fireEvent.click(first)
    expect(previewOf(container)!.querySelector('.card-placeholder-well')).not.toBeNull()
  })

  it('shows the PINNED card over a later hover — the store’s pin-over-transient resolution', () => {
    // `targetIdOf` is `pinnedId ?? transient ?? default` (`inspection.ts`), the same one
    // expression the shell's detail panel reads — asserted HERE because this is the first
    // surface where both a pin and a live hover are visible in one view body, and a preview
    // that tracked the pointer past a pin would contradict what the pin means everywhere else.
    seedAll()
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    const [first, second] = tilesOf(rowAt(container, 0))

    fireEvent.click(first)
    fireEvent.mouseEnter(second)

    // The hover was RECORDED (the pin's release would expose it) — it just does not outrank.
    expect(useInspectionStore.getState().hoveredId).toBe('c-tier-2')
    expect(previewOf(container)!.querySelector('.tier-preview-name')).toHaveTextContent(
      'Card c-tier-1',
    )

    // Releasing the pin hands the preview to the still-live hover, the store's own fallback.
    fireEvent.click(first)
    expect(previewOf(container)!.querySelector('.tier-preview-name')).toHaveTextContent(
      'Card c-tier-2',
    )
  })

  it('draws the target’s SHOWN face — the preview follows the faces store, never face 0', () => {
    // Replacing the preview's `useFaceIndex(cardId)` with a literal `0` passes every other
    // test in this block; this is the pin. The store is seeded directly (`flipCard` is the
    // runtime door and it gates on the hydrated image count, which is not what is under test).
    seedAll()
    act(() => useFaceStore.setState({ faces: { 'c-tier-1': 1 } }))
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)

    fireEvent.mouseEnter(tilesOf(rowAt(container, 0))[0])

    expect(previewOf(container)!.querySelector('.tier-preview-image')).toHaveAttribute(
      'src',
      '/api/card-image/c-tier-1?face=1',
    )
  })

  it('falls back to the NAMED placeholder when the target’s picture fails', () => {
    seedAll()
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    fireEvent.mouseEnter(tilesOf(rowAt(container, 0))[0])

    const preview = previewOf(container)!
    fireEvent.error(preview.querySelector('.tier-preview-image')!)

    // The `<img>` is REMOVED rather than hidden (AD-11 — no broken-image glyph), and the
    // named variant draws what the cache knows: name, cost pips, type line.
    expect(preview.querySelector('.tier-preview-image')).toBeNull()
    expect(preview.querySelector('.card-placeholder')).toHaveTextContent('Card c-tier-1')
  })

  it('falls back to EMPTY when the target settles to unknown — the tile effect releases it', () => {
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    fireEvent.mouseEnter(tilesOf(rowAt(container, 0))[0])

    act(() => seedUnknown('c-tier-1'))

    // The existing per-tile release valve (Greptile P1) cleared the target, so the preview is
    // back on the silent well — it never renders the unknown-card variant of its own.
    expect(useInspectionStore.getState().hoveredId).toBeNull()
    const preview = previewOf(container)!
    expect(preview.querySelector('.card-placeholder-well')).not.toBeNull()
    expect(preview.textContent).toBe('')
  })

  it('releases a TILELESS pin that settles unknown, so tier hover is never outranked forever (Greptile P1, PR #103)', () => {
    seedAll()
    // A pin retained from ANOTHER surface (FR-17's survival) naming a card with NO tile in this
    // push: no per-tile release valve exists for it, so the preview's own must fire.
    act(() => {
      useInspectionStore.setState({ pinnedId: 'c-outside' })
    })
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)

    act(() => seedUnknown('c-outside'))

    // The preview's release valve cleared the stuck pin the moment it settled unknown…
    expect(useInspectionStore.getState().pinnedId).toBeNull()
    // …so a tier hover is the resolved target again, not permanently outranked by a dead id.
    fireEvent.mouseEnter(tilesOf(rowAt(container, 0))[0])
    const preview = previewOf(container)!
    expect(preview.querySelector('.tier-preview-name')!.textContent).toBe('Card c-tier-1')
  })

  it('is silent and wordless: no live region, no landmark, no control, no authored copy', () => {
    seedAll()
    const { container } = render(<TierListView kind="tier_list" items={[TIER]} />)
    fireEvent.mouseEnter(tilesOf(rowAt(container, 0))[0])

    const preview = previewOf(container)!
    // Not a fourth live region (`App.test.tsx` pins the census at three, exhaustively) and not
    // a second CardDetail: no region/heading landmark, no skip-target id, no interactive stop.
    expect(preview.hasAttribute('aria-live')).toBe(false)
    expect(preview.querySelector('[aria-live]')).toBeNull()
    expect(preview.querySelector('#card-detail')).toBeNull()
    expect(preview.querySelector('button')).toBeNull()
    expect(preview.querySelector('h2')).toBeNull()
    // The only role inside is `ManaCost`'s own `role="img"` — the shared primitive's contract,
    // never a region or a live politeness of this component's invention.
    for (const element of preview.querySelectorAll('[role]')) {
      expect(element.getAttribute('role')).toBe('img')
    }
    // Every rendered word is wire data the fixtures put in the cache.
    expect(preview.querySelector('.tier-preview-name')!.textContent).toBe('Card c-tier-1')
    expect(preview.querySelector('.tier-preview-type')!.textContent).toBe('Creature — Elf')
  })
})

describe('hydration is this view’s own, across every tier (AD-12)', () => {
  const cardCalls = () =>
    (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls
      .map(([input]) => String(input))
      .filter((path) => path.startsWith('/api/cards/'))

  it('asks once per UNIQUE id across tiers', () => {
    render(
      <TierListView
        kind="tier_list"
        items={[TIER, { ...OTHER, card_ids: ['c-tier-3', 'c-tier-1'] }]} // `c-tier-1` twice
      />,
    )

    // Two tiers, four id slots, three distinct ids — three reads. The `Set` collapses a card
    // ranked in more than one tier.
    expect(cardCalls()).toHaveLength(3)
    expect(cardCalls()).toContain('/api/cards/c-tier-1')
    expect(cardCalls()).toContain('/api/cards/c-tier-2')
    expect(cardCalls()).toContain('/api/cards/c-tier-3')
  })

  it('hydrates ids from a tier the render gate SKIPS — the skip is render-only', () => {
    // The effect iterates the RAW items, deliberately (see its comment): a duplicate id shared
    // between a skipped tier and a healthy one must find the cache warm either way. Rewriting
    // the effect over the filtered rows passes every other test in this file — this is the pin.
    render(
      <TierListView
        kind="tier_list"
        items={[{ letter: 'F', name: 'Bad', card_ids: ['c-tier-9'] } as unknown as TierItem, TIER]}
      />,
    )

    expect(cardCalls()).toContain('/api/cards/c-tier-9')
    expect(cardCalls()).toHaveLength(3)
  })

  it('re-hydrates when ITEMS change — replace-in-place brings new ids', () => {
    const { rerender } = render(<TierListView kind="tier_list" items={[TIER]} />)
    expect(cardCalls()).toHaveLength(2)

    rerender(<TierListView kind="tier_list" items={[OTHER]} />)

    expect(cardCalls()).toContain('/api/cards/c-tier-3')
    expect(cardCalls()).toHaveLength(3)
  })

  it('asks for nothing on an empty push, and nothing for a malformed id', () => {
    render(
      <TierListView
        kind="tier_list"
        items={[{ ...TIER, card_ids: [null, 'c-tier-2'] } as unknown as typeof TIER]}
      />,
    )

    // The malformed slot cost no request (`cardIdsOf` filters it before the effect ever sees
    // it — E16-91); the good id was still asked for — one bad entry, zero traffic.
    expect(cardCalls()).toEqual(['/api/cards/c-tier-2'])
  })
})
