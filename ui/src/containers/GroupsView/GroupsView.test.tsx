import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Card, CardSummary, DeckCardSummary, DeckDetail, GroupItem } from '../../api/schema'
import { resetCardCache, useCardStore } from '../../state/cards'
import { resetDeckState, useDeckStore } from '../../state/deck'
import { boardsOfDeck } from '../../state/deckGroups'
import { resetFaces } from '../../state/faces'
import { resetInspection, useInspectionStore } from '../../state/inspection'
import { GroupsView } from './GroupsView'
import { emptyPushLine } from '../SuggestionsView/copy'

/**
 * The groups view's body — `TierListView.test.tsx`'s harness, on the fourth and last view
 * kind. The same disclaimers apply: jsdom evaluates no stylesheet (the divider, the measure and
 * the badge chrome are read as SOURCE by `token-usage.test.ts` and the shell guards) and loads
 * no images (art states are driven manually). What this file proves is the BRANCH and the
 * WIRING — which element renders for which input, which handler reaches which store verb, that
 * an empty or malformed group is skipped while its neighbours render, that one bad card id
 * costs exactly one thumbnail of one group, and that the quantity badge obeys EXPERIENCE.md:94's
 * in-deck-only gate.
 */

// Typed through the ALIAS (`schema.ts` is the one home for a wire-derived shape — declaring a
// local `GroupItem` is what `tests/wire-contract.test.ts` bans), so a fixture that drifted from
// the generated model would fail to compile rather than silently testing a shape of its own.
const GROUP: GroupItem = {
  title: 'Ramp',
  rationale: 'These accelerate into the six-drops a turn early.',
  card_ids: ['c-group-1', 'c-group-2'],
}

const OTHER: GroupItem = {
  title: 'Answers',
  rationale: 'The removal the matchup keeps asking for.',
  card_ids: ['c-group-3'],
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
  set_name: 'Test Set',
  collector_number: '1',
  oracle_id: 'oracle-1',
  color_identity: [],
  legalities: {},
  games: [],
  ...over,
})

const card = (id: string, over: Partial<Card> = {}): Card => ({
  ...summary(id),
  oracle_id: `oracle-${id}`,
  color_identity: ['G'],
  ...over,
})

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
  for (const id of ['c-group-1', 'c-group-2', 'c-group-3']) seedHydrated(id)
}

// ==== THE DECK, FOR THE BADGE (EXPERIENCE.md:94) =========================================
// The badge's whole meaning is "copies in THIS deck", so the harness needs a settled deck the
// selector can read. Rows are minimal `DeckCardSummary`s; `boardsOfDeck` derives the boards
// exactly as the production write path does.

const deckRow = (cardId: string, quantity: number, sideboard = false): DeckCardSummary => ({
  card_id: cardId,
  quantity,
  sideboard,
  commander: false,
  card: summary(cardId),
})

const settleDeck = (rows: DeckCardSummary[]) => {
  const detail: DeckDetail = {
    id: 'deck-16-3',
    name: 'Badge fixture deck',
    format: 'commander',
    strategy: null,
    color_identity: [],
    tags: [],
    mainboard_count: rows.length,
    sideboard_count: 0,
    distinct_cards: rows.length,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
    cards: rows,
  }
  useDeckStore.setState({ deck: { status: 'deck', detail, boards: boardsOfDeck(detail) } })
}

const sections = (container: HTMLElement) => [
  ...container.querySelectorAll<HTMLElement>('.group-section'),
]

const sectionAt = (container: HTMLElement, index: number) => {
  const found = sections(container)[index]
  expect(found, `no section at index ${index}`).toBeDefined()
  return found
}

const tilesOf = (section: HTMLElement) => [
  ...section.querySelectorAll<HTMLButtonElement>('.group-tile'),
]

beforeEach(() => {
  resetCardCache()
  resetInspection()
  resetFaces()
  resetDeckState()
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
    render(<GroupsView kind="groups" items={[]} />)

    expect(screen.getByText(emptyPushLine('groups'))).toBeInTheDocument()
    expect(document.body.textContent).toContain('groups')
    expect(document.body.textContent).not.toContain('{noun}')
  })

  it('is a bare paragraph REPLACING the list, exactly as all three siblings’ empty states are', () => {
    const { container } = render(<GroupsView kind="groups" items={[]} />)

    const line = container.querySelector('.groups-view-empty')
    expect(line?.tagName).toBe('P')
    expect(line).not.toHaveAttribute('aria-live')
    expect(screen.queryByRole('list')).toBeNull()
  })

  it('takes the kind from its PROP rather than assuming one', () => {
    render(<GroupsView kind="tier_list" items={[]} />)

    expect(screen.getByText(emptyPushLine('tier_list'))).toBeInTheDocument()
  })
})

describe('the sections, and their anatomy (DESIGN.md group-section)', () => {
  it('renders a real ul/li — one li per group, in payload order, never re-sorted (UX-DR44)', () => {
    seedAll()
    // `Answers` before `Ramp`, deliberately: payload order is render order, and a view that
    // sorted by title would pass an in-order fixture while silently rewriting the argument.
    const { container } = render(<GroupsView kind="groups" items={[OTHER, GROUP]} />)

    const list = screen.getByRole('list')
    expect(list.tagName).toBe('UL')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(sectionAt(container, 0).querySelector('.group-section-title')).toHaveTextContent(
      OTHER.title,
    )
    expect(sectionAt(container, 1).querySelector('.group-section-title')).toHaveTextContent(
      GROUP.title,
    )
    expect(container.querySelector('.groups-view-empty')).toBeNull()
  })

  it('renders every slot the artefact names: title, bare numeral count, rationale, thumbnails', () => {
    seedAll()
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)
    const section = sectionAt(container, 0)

    expect(section.querySelector('.group-section-title')).toHaveTextContent(GROUP.title)
    // The count is a BARE NUMERAL — no authored word beside it (the mock's "N cards" has no
    // copy-cell source), and it is the rendered tile list's own length.
    expect(section.querySelector('.group-section-count')!.textContent).toBe('2')
    expect(section.querySelector('.group-section-rationale')).toHaveTextContent(GROUP.rationale)
    expect(tilesOf(section)).toHaveLength(2)
  })

  it('counts the VALID id list the strip renders — a filtered id moves the numeral too', () => {
    // The count and the tiles read ONE list (the spec's "it never counts tiles that don't
    // appear"): a non-string id is filtered before both, so the numeral says 1, not 2.
    seedAll()
    const withBadId = {
      title: 'Partly broken',
      rationale: 'One slot arrived as a number.',
      card_ids: [42, 'c-group-3'],
    } as unknown as GroupItem

    const { container } = render(<GroupsView kind="groups" items={[withBadId]} />)

    const section = sectionAt(container, 0)
    expect(section.querySelector('.group-section-count')!.textContent).toBe('1')
    expect(tilesOf(section)).toHaveLength(1)
  })

  it('filters an empty or whitespace-only id — it never renders, never counts, never hydrates', () => {
    // A blank id names nothing the app could ever render: keeping it would spend a
    // permanently-dead placeholder slot, and a whitespace-only one would even commit a real
    // `/api/card-image/%20` request before hydration settled. `cardIdsOf` drops both, so the
    // numeral, the strip and the hydration effect all read the same one-entry list.
    seedAll()
    const withBlankIds = {
      title: 'Mostly blank',
      rationale: 'Two slots arrived empty.',
      card_ids: ['', '  ', 'c-group-3'],
    } as unknown as GroupItem

    const { container } = render(<GroupsView kind="groups" items={[withBlankIds]} />)

    const section = sectionAt(container, 0)
    expect(tilesOf(section)).toHaveLength(1)
    expect(section.querySelector('.group-section-count')!.textContent).toBe('1')
  })

  it('renders the same printing TWICE in one group — duplicates are legal, keys stay stable', () => {
    // The `${cardId}:${index}` key's whole reason: nothing constrains an agent against
    // grouping the same printing twice, and a bare-id key would collapse the pair.
    seedHydrated('c-dup')
    const twins = {
      title: 'Twins',
      rationale: 'The same printing, twice.',
      card_ids: ['c-dup', 'c-dup'],
    }

    const { container } = render(<GroupsView kind="groups" items={[twins]} />)

    const section = sectionAt(container, 0)
    expect(tilesOf(section)).toHaveLength(2)
    expect(section.querySelector('.group-section-count')!.textContent).toBe('2')
  })

  it('trims whitespace padding on the group title and rationale — the payload-title symmetry', () => {
    // The store trims the PAYLOAD-level title (`groupsViewOf`, pinned in agentView.test.ts);
    // the group-level fold trims for the same reason, so '  Ramp  ' renders as 'Ramp' at
    // either level rather than only one.
    seedAll()
    const padded = { title: '  Ramp  ', rationale: '  Padded argument.  ', card_ids: ['c-group-3'] }

    const { container } = render(<GroupsView kind="groups" items={[padded]} />)

    const section = sectionAt(container, 0)
    expect(section.querySelector('.group-section-title')!.textContent).toBe('Ramp')
    expect(section.querySelector('.group-section-rationale')!.textContent).toBe('Padded argument.')
  })

  it('draws every thumbnail from the backend proxy with alt="" exactly (AD-11, UX-DR48)', () => {
    seedAll()
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)

    const images = [...sectionAt(container, 0).querySelectorAll('.group-tile-image')]
    expect(images.map((i) => i.getAttribute('src'))).toEqual([
      '/api/card-image/c-group-1',
      '/api/card-image/c-group-2',
    ])
    for (const image of images) {
      expect(image).toHaveAttribute('alt', '')
      expect(image).toHaveClass('card-shape')
      expect(image).not.toHaveAttribute('style')
      expect(image.getAttribute('src')).not.toContain('size=')
    }
  })
})

describe('the quantity badge obeys the in-deck gate (EXPERIENCE.md:94)', () => {
  it('shows ×N for a card the active deck runs, and NOTHING for one it does not', () => {
    seedAll()
    settleDeck([deckRow('c-group-1', 4)])
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)
    const [inDeck, offDeck] = tilesOf(sectionAt(container, 0))

    expect(inDeck.querySelector('.group-tile-quantity')).toHaveTextContent('×4')
    // The off-deck tile renders NORMALLY — thumbnail and all — with no badge: groups routinely
    // name cards the deck does not run, and "×0 would be a lie".
    expect(offDeck.querySelector('.group-tile-quantity')).toBeNull()
    expect(offDeck.querySelector('.group-tile-image')).not.toBeNull()
  })

  it('renders ×1 for an in-deck SINGLETON — the deliberate divergence from CardTile’s > 1 gate', () => {
    // In the deck grid every card is in the deck, so ×1 is noise; here in-deck-ness itself is
    // the signal, so a singleton's badge is informative and truthful.
    seedAll()
    settleDeck([deckRow('c-group-1', 1)])
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)

    expect(
      tilesOf(sectionAt(container, 0))[0].querySelector('.group-tile-quantity'),
    ).toHaveTextContent('×1')
  })

  it('shows NO badge anywhere when no deck is loaded — the selector answers null', () => {
    seedAll()
    // `resetDeckState` in beforeEach left the store on its booting arm: no deck, no fact.
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)

    expect(container.querySelectorAll('.group-tile-quantity')).toHaveLength(0)
    // …and the view is otherwise unaffected: both tiles render.
    expect(tilesOf(sectionAt(container, 0))).toHaveLength(2)
  })

  it('updates LIVE when the deck settles after mount — a subscription, not a mount-time read', () => {
    // The one test that separates `useDeckCardQuantity` (a store subscription) from a
    // `getState()` read frozen at mount: the agent editing the deck while a groups view is
    // open must move the badges on the glass. It also pins the null→number transition — the
    // badge APPEARS, not merely re-renders.
    seedAll()
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)
    expect(container.querySelectorAll('.group-tile-quantity')).toHaveLength(0)

    act(() => settleDeck([deckRow('c-group-1', 3)]))

    expect(
      tilesOf(sectionAt(container, 0))[0].querySelector('.group-tile-quantity'),
    ).toHaveTextContent('×3')
  })

  it('is STATIC — no flash attribute in any state, because pushes replace wholesale', () => {
    seedAll()
    settleDeck([deckRow('c-group-1', 2)])
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)

    const badge = sectionAt(container, 0).querySelector('.group-tile-quantity')!
    expect(badge).not.toHaveAttribute('data-flashed')
  })
})

describe('empty and malformed groups are skipped; neighbours render (EXPERIENCE.md:94, FR-13/AD-7)', () => {
  it('skips an EMPTY group entirely — no shell, no heading, no rationale, no empty strip', () => {
    seedAll()
    const { container } = render(
      <GroupsView
        kind="groups"
        items={[GROUP, { title: 'Cut list', rationale: 'Nothing survived.', card_ids: [] }, OTHER]}
      />,
    )

    // Two rendered sections, and neither is the empty one — the skip is by anatomy, not index,
    // and it takes the group's TITLE AND RATIONALE with it (never an empty shell).
    expect(sections(container)).toHaveLength(2)
    expect(container.textContent).not.toContain('Cut list')
    expect(container.textContent).not.toContain('Nothing survived.')
    expect(sectionAt(container, 0).querySelector('.group-section-title')).toHaveTextContent(
      GROUP.title,
    )
    expect(sectionAt(container, 1).querySelector('.group-section-title')).toHaveTextContent(
      OTHER.title,
    )
  })

  it('degrades a group whose title is missing or blank — the heading is the group’s identity', () => {
    seedAll()
    const malformed = [
      { rationale: 'Headless.', card_ids: ['c-group-3'] },
      { title: '   ', rationale: 'Blank-headed.', card_ids: ['c-group-3'] },
      GROUP,
    ] as unknown as GroupItem[]

    const { container } = render(<GroupsView kind="groups" items={malformed} />)

    expect(sections(container)).toHaveLength(1)
    expect(container.textContent).not.toContain('Headless.')
    expect(sectionAt(container, 0).querySelector('.group-section-title')).toHaveTextContent(
      GROUP.title,
    )
  })

  it('degrades a group whose rationale is missing or blank — the wire non-blank-validates it', () => {
    seedAll()
    const malformed = [
      { title: 'No argument', card_ids: ['c-group-3'] },
      { title: 'Blank argument', rationale: '   ', card_ids: ['c-group-3'] },
      GROUP,
    ] as unknown as GroupItem[]

    const { container } = render(<GroupsView kind="groups" items={malformed} />)

    expect(sections(container)).toHaveLength(1)
    expect(container.textContent).not.toContain('No argument')
    expect(container.textContent).not.toContain('Blank argument')
  })

  it('skips a group whose EVERY id fails the ladder — non-strings leave it empty', () => {
    seedAll()
    const allBad = {
      title: 'Numbers only',
      rationale: 'Every slot arrived as a number.',
      card_ids: [1, 2, 3],
    } as unknown as GroupItem

    const { container } = render(<GroupsView kind="groups" items={[allBad, GROUP]} />)

    expect(sections(container)).toHaveLength(1)
    expect(container.textContent).not.toContain('Numbers only')
  })

  it('renders a bare null array element and a non-array card_ids as skips, never a crash', () => {
    seedAll()
    const malformed = [
      null,
      { title: 'Filler', rationale: 'Ids arrived as a string.', card_ids: 'c-group-3' },
      GROUP,
    ] as unknown as GroupItem[]

    const { container } = render(<GroupsView kind="groups" items={malformed} />)

    expect(sections(container)).toHaveLength(1)
    expect(sectionAt(container, 0).querySelector('.group-section-title')).toHaveTextContent(
      GROUP.title,
    )
  })

  it('degrades an unknown card id to the placeholder while the group’s text still renders', () => {
    seedUnknown('c-group-1')
    seedHydrated('c-group-2')
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)
    const [deadTile, liveTile] = tilesOf(sectionAt(container, 0))

    expect(deadTile.querySelector('.card-placeholder')).toHaveTextContent('Unknown card')
    expect(deadTile.querySelector('.group-tile-image')).toBeNull()
    // The sibling tile and the group's words are untouched: one dead id, one dead thumbnail.
    expect(liveTile.querySelector('.group-tile-image')).toHaveAttribute(
      'src',
      '/api/card-image/c-group-2',
    )
    expect(sectionAt(container, 0).querySelector('.group-section-title')).toHaveTextContent(
      GROUP.title,
    )
    expect(sectionAt(container, 0).querySelector('.group-section-rationale')).toHaveTextContent(
      GROUP.rationale,
    )
  })

  it('renders the shared line when EVERY group is skipped — never an empty list shell', () => {
    const { container } = render(
      <GroupsView
        kind="groups"
        items={[{ title: 'Empty group', rationale: 'Nothing in it.', card_ids: [] }]}
      />,
    )

    // An empty `<ul>` would announce "list, 0 items" with nothing to explain why; the one
    // shared sentence replaces it, and no second sentence is authored for this state.
    expect(screen.queryByRole('list')).toBeNull()
    expect(container.querySelector('.groups-view-empty')).toHaveTextContent(emptyPushLine('groups'))
  })
})

describe('the inspection contract on EVERY tile (UX-DR14, UX-DR20, UX-DR22)', () => {
  it('sets the detail target per tile on hover and focus, and pins on click', () => {
    seedAll()
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)
    const [first, second] = tilesOf(sectionAt(container, 0))

    fireEvent.mouseEnter(first)
    expect(useInspectionStore.getState().hoveredId).toBe('c-group-1')
    fireEvent.mouseLeave(first)
    expect(useInspectionStore.getState().hoveredId).toBeNull()

    fireEvent.focus(second)
    expect(useInspectionStore.getState().focusedId).toBe('c-group-2')
    fireEvent.blur(second)
    expect(useInspectionStore.getState().focusedId).toBeNull()

    fireEvent.click(second)
    expect(useInspectionStore.getState().pinnedId).toBe('c-group-2')
    // A second single click releases (UX-DR20) — never a double-click semantic.
    fireEvent.click(second)
    expect(useInspectionStore.getState().pinnedId).toBeNull()
  })

  it('is one real <button> per card, named by the card, with no tabindex (UX-DR39/40/48)', () => {
    seedAll()
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)
    const tiles = tilesOf(sectionAt(container, 0))

    expect(tiles).toHaveLength(2)
    for (const tile of tiles) {
      expect(tile.tagName).toBe('BUTTON')
      expect(tile).toHaveAttribute('type', 'button')
      expect(tile).not.toHaveAttribute('tabindex')
    }
    expect(screen.getAllByRole('button')).toHaveLength(2)
    // The tile's accessible name is the CARD's name (wire data, visually hidden) — the image's
    // alt stays "" and the strip has no label element, so without this every tile would be an
    // anonymous Tab stop.
    expect(screen.getByRole('button', { name: 'Card c-group-1' })).toBe(tiles[0])
  })

  it('REFUSES every verb on an unknown tile through the store, and stays a button (Q3)', () => {
    seedUnknown('c-group-1')
    seedHydrated('c-group-2')
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)
    const [deadTile] = tilesOf(sectionAt(container, 0))

    fireEvent.mouseEnter(deadTile)
    fireEvent.focus(deadTile)
    fireEvent.click(deadTile)

    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(useInspectionStore.getState().focusedId).toBeNull()
    expect(useInspectionStore.getState().pinnedId).toBeNull()
    expect(deadTile.tagName).toBe('BUTTON')
    expect(deadTile).not.toBeDisabled()

    // The non-vacuity control: the same tile, re-armed, proves the handlers were wired all
    // along and the STORE did the refusing.
    act(() => seedHydrated('c-group-1'))
    fireEvent.mouseEnter(tilesOf(sectionAt(container, 0))[0])
    expect(useInspectionStore.getState().hoveredId).toBe('c-group-1')
  })

  it('releases a stale hover, focus AND pin when an entry settles to unknown (Greptile P1)', () => {
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)
    const [first] = tilesOf(sectionAt(container, 0))

    fireEvent.mouseEnter(first)
    fireEvent.focus(first)
    fireEvent.click(first)
    expect(useInspectionStore.getState().pinnedId).toBe('c-group-1')

    act(() => seedUnknown('c-group-1'))

    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(useInspectionStore.getState().focusedId).toBeNull()
    expect(useInspectionStore.getState().pinnedId).toBeNull()
  })

  it('only releases the id that went unknown, never a sibling tile’s target', () => {
    seedHydrated('c-group-2')
    const { container } = render(<GroupsView kind="groups" items={[GROUP]} />)
    const [, second] = tilesOf(sectionAt(container, 0))

    fireEvent.click(second)
    expect(useInspectionStore.getState().pinnedId).toBe('c-group-2')

    act(() => seedUnknown('c-group-1'))

    expect(useInspectionStore.getState().pinnedId).toBe('c-group-2')
  })
})

describe('hydration is this view’s own, across every group (AD-12)', () => {
  const cardCalls = () =>
    (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls
      .map(([input]) => String(input))
      .filter((path) => path.startsWith('/api/cards/'))

  it('asks once per UNIQUE id across groups', () => {
    render(
      <GroupsView
        kind="groups"
        items={[GROUP, { ...OTHER, card_ids: ['c-group-3', 'c-group-1'] }]} // `c-group-1` twice
      />,
    )

    // Two groups, four id slots, three distinct ids — three reads. The `Set` collapses a card
    // grouped more than once.
    expect(cardCalls()).toHaveLength(3)
    expect(cardCalls()).toContain('/api/cards/c-group-1')
    expect(cardCalls()).toContain('/api/cards/c-group-2')
    expect(cardCalls()).toContain('/api/cards/c-group-3')
  })

  it('hydrates ids from a group the render gate SKIPS — the skip is render-only (the 16.2 pin)', () => {
    // The effect iterates the RAW items, deliberately (see its comment): a duplicate id shared
    // between a skipped group and a healthy one must find the cache warm either way. Rewriting
    // the effect over the filtered sections passes every other test in this file — this is the
    // pin, mirrored from `TierListView.test.tsx`'s.
    render(
      <GroupsView
        kind="groups"
        items={[{ title: '', rationale: 'Blank title, real ids.', card_ids: ['c-group-9'] }, GROUP]}
      />,
    )

    expect(cardCalls()).toContain('/api/cards/c-group-9')
    expect(cardCalls()).toHaveLength(3)
  })

  it('re-hydrates when ITEMS change — replace-in-place brings new ids', () => {
    const { rerender } = render(<GroupsView kind="groups" items={[GROUP]} />)
    expect(cardCalls()).toHaveLength(2)

    rerender(<GroupsView kind="groups" items={[OTHER]} />)

    expect(cardCalls()).toContain('/api/cards/c-group-3')
    expect(cardCalls()).toHaveLength(3)
  })

  it('asks for nothing on an empty push, and nothing for a filtered id', () => {
    render(
      <GroupsView
        kind="groups"
        items={[{ ...GROUP, card_ids: [null, 'c-group-2'] } as unknown as GroupItem]}
      />,
    )

    // The malformed slot was FILTERED before the effect saw it — no request, no tile; the good
    // id was still asked for. One bad entry, one silent slot.
    expect(cardCalls()).toEqual(['/api/cards/c-group-2'])
  })
})
