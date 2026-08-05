import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { DeckCardSummary } from '../api/schema'
import { resetCardCache, useCardStore } from './cards'
import { boardsOf } from './deckGroups'
import {
  clearHovered,
  clearPin,
  coldOpenTargetOf,
  resetInspection,
  setDefaultTarget,
  setHovered,
  targetIdOf,
  togglePin,
  useInspectionStore,
  useInspectionTargetId,
  useIsLiveTarget,
  usePinnedId,
} from './inspection'

/**
 * The inspection slice (story c4-5, AC 3, AC 4, AC 5, AC 8, AC 9, AC 17, AC 19, AC 20).
 *
 * ================= WHAT THIS SUITE CANNOT CARRY, SAID FIRST ============================
 *
 * Nothing here renders a tile or a panel, so nothing here proves that a POINTER reaching a card
 * sets a target — that is `CardTile.test.tsx`'s wiring claim and `CardDetail.test.tsx`'s render
 * claim. What this file proves is the resolution itself: which of three inputs wins, what a
 * refusal does, and that the cold-open answer is total.
 *
 * The one thing no jsdom suite can carry at all is hover APPEARANCE — jsdom evaluates no CSS —
 * and it is declared in every file that touches it rather than in one.
 */

/** A deck row, shaped the way `boardsOf` reads it: the flags, the quantity, the summary. */
const row = (
  name: string,
  typeLine: string,
  flags: { commander?: boolean; sideboard?: boolean } = {},
): DeckCardSummary => ({
  card_id: `id-${name}`,
  quantity: 1,
  sideboard: flags.sideboard ?? false,
  commander: flags.commander ?? false,
  card: {
    id: `id-${name}`,
    name,
    mana_cost: '',
    cmc: 0,
    type_line: typeLine,
    oracle_text: '',
    colors: [],
    rarity: 'rare',
    set_code: 'tst',
  },
})

afterEach(() => {
  resetInspection()
  resetCardCache()
})

describe('the three inputs, and the order they win in (AC 8, AC 19, AC 20)', () => {
  it('resolves to nothing at all before a deck exists', () => {
    // Not a bug and not an empty state: `App` mounts the panel only for a loaded deck (Q14), so
    // this is the shape the slice holds for the one paint before `setDefaultTarget` runs.
    expect(targetIdOf(useInspectionStore.getState())).toBeNull()
  })

  it('targets the cold-open card with no interaction (AC 8, FR-17, UX-DR20)', () => {
    setDefaultTarget('id-Atraxa')
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-Atraxa')
  })

  it('lets hover override the cold-open target, and lets go again', () => {
    setDefaultTarget('id-Atraxa')
    setHovered('id-Llanowar Elves')
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-Llanowar Elves')

    clearHovered('id-Llanowar Elves')
    // NEVER EMPTY (UX-DR20): letting go of a card falls back to the cold-open target rather
    // than to nothing.
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-Atraxa')
  })

  it('lets a pin outrank hover, so hover no longer overrides it (AC 19)', () => {
    setDefaultTarget('id-Atraxa')
    togglePin('id-Forest')
    setHovered('id-Llanowar Elves')

    expect(targetIdOf(useInspectionStore.getState())).toBe('id-Forest')
    // …and the hover is still REMEMBERED rather than discarded, which is what makes release
    // hand control back to wherever the cursor actually is (AC 20).
    expect(useInspectionStore.getState().hoveredId).toBe('id-Llanowar Elves')
  })

  it('releases on a SECOND click of the same card — never a double-click (AC 20, UX-DR39)', () => {
    setDefaultTarget('id-Atraxa')
    setHovered('id-Llanowar Elves')
    togglePin('id-Forest')
    togglePin('id-Forest')

    expect(useInspectionStore.getState().pinnedId).toBeNull()
    // Hover RESUMES CONTROL on release, which is the half a "clears the pin" test would miss.
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-Llanowar Elves')
  })

  it('moves the pin when a DIFFERENT card is clicked', () => {
    togglePin('id-Forest')
    togglePin('id-Island')
    expect(useInspectionStore.getState().pinnedId).toBe('id-Island')
  })

  it('releases on clearPin — the Esc and unpin-control path (AC 20)', () => {
    setDefaultTarget('id-Atraxa')
    togglePin('id-Forest')
    clearPin()
    expect(useInspectionStore.getState().pinnedId).toBeNull()
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-Atraxa')
  })

  it('clears the hover only for the card that still holds it', () => {
    // THE RACE THIS EXISTS FOR (Q8's one addition). `blur` on the tile being left and `focus` on
    // the tile being reached both fire, and a bare `setHovered(null)` on the losing tile lands
    // AFTER the winner in the ordering keyboard traversal actually produces. The visible result
    // is the panel snapping back to the cold-open card in the middle of a sweep.
    setHovered('id-A')
    setHovered('id-B')
    clearHovered('id-A')
    expect(useInspectionStore.getState().hoveredId).toBe('id-B')

    clearHovered('id-B')
    expect(useInspectionStore.getState().hoveredId).toBeNull()
  })

  it('takes an explicit null on setHovered, because a pointer really can leave the grid', () => {
    setHovered('id-A')
    setHovered(null)
    expect(useInspectionStore.getState().hoveredId).toBeNull()
  })
})

describe('an unknown card cannot become the inspection target (AC 17, UX-DR22)', () => {
  /** The cache entry `hydrateCard` writes for a `card_not_found` / malformed id. */
  const unknown = (cardId: string) => {
    useCardStore.setState((state) => ({
      cards: {
        ...state.cards,
        [cardId]: {
          status: 'unknown',
          reason: 'card_not_found',
          placeholder: 'unknown-card',
          summary: null,
          retryable: false,
        },
      },
    }))
  }

  it('refuses it on hover — there is nothing to show', () => {
    // `EXPERIENCE.md:99`: "Placeholder tiles behave like normal tiles (inspection contract)
    // EXCEPT the unknown-card variant, which cannot be inspected — there is nothing to show."
    setDefaultTarget('id-Atraxa')
    unknown('id-ghost')
    setHovered('id-ghost')

    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-Atraxa')
  })

  it('refuses it on click too — a pin is the same contract with a longer life (AC 19)', () => {
    unknown('id-ghost')
    togglePin('id-ghost')
    expect(useInspectionStore.getState().pinnedId).toBeNull()
  })

  it('does NOT refuse a card whose PICTURE merely failed', () => {
    // The silent half, and the distinction the refusal turns on. `no_image_data` and
    // `image_fetch_failed` map to the NAMED placeholder — the app knows exactly what the card
    // is and only lacks its art, so the panel has a name, a cost, a type line and oracle text
    // to draw. Refusing those would empty the panel for 79 corpus cards that render fine.
    useCardStore.setState((state) => ({
      cards: {
        ...state.cards,
        'id-artless': {
          status: 'unknown',
          reason: 'database_unavailable',
          placeholder: null,
          summary: null,
          retryable: true,
        },
      },
    }))
    setHovered('id-artless')
    expect(useInspectionStore.getState().hoveredId).toBe('id-artless')
  })

  it('does NOT refuse an id the cache has never seen', () => {
    // `undefined` means "never seen" and nothing else (c4-1 AC 4). A slice that refused on
    // absence would refuse every card on the very first hover of a cold open, before any
    // hydration had run — the FR-13 posture inverted.
    setHovered('id-brand-new')
    expect(useInspectionStore.getState().hoveredId).toBe('id-brand-new')
  })
})

describe('the cold-open target is the grid’s own visual order (AC 8, AC 9, Q15)', () => {
  it('is the commander, because the grid draws the commander first', () => {
    // UX-DR20 says "the first card of the first type group"; `boards.commander` is a SEPARATE
    // board the grid draws BEFORE the type groups, so the literal reading and the on-screen
    // reading differ for the 16 of 40 real decks that have a commander. The panel targets what
    // the eye lands on.
    const boards = boardsOf([
      row('Llanowar Elves', 'Creature — Elf Druid'),
      row('Atraxa, Praetors’ Voice', 'Legendary Creature — Phyrexian Angel Horror', {
        commander: true,
      }),
    ])
    expect(coldOpenTargetOf(boards)).toBe('id-Atraxa, Praetors’ Voice')
  })

  it('falls to the first card of the first populated group when there is no commander', () => {
    // `TYPE_GROUPS` order with EMPTY GROUPS OMITTED, so `mainboard[0]` is genuinely the first
    // group with cards in it rather than "Creature" whether or not the deck runs any.
    const boards = boardsOf([row('Forest', 'Basic Land — Forest'), row('Ponder', 'Sorcery')])
    expect(coldOpenTargetOf(boards)).toBe('id-Ponder')
  })

  it('ignores the sideboard, which the grid does not draw', () => {
    const boards = boardsOf([
      row('Pithing Needle', 'Artifact', { sideboard: true }),
      row('Ponder', 'Sorcery'),
    ])
    expect(coldOpenTargetOf(boards)).toBe('id-Ponder')
  })

  it('is TOTAL over a deck with nothing in either board (AC 9)', () => {
    // `boardsOf([])` is three empty boards, and c4-12 owns the copy for what that looks like.
    // What this story owes is no crash and no half-resolved target.
    expect(coldOpenTargetOf(boardsOf([]))).toBeNull()
  })
})

describe('the selectors return primitives, which is the whole of Q7', () => {
  it('gives a tile a boolean rather than an object', () => {
    setDefaultTarget('id-Atraxa')
    const live = renderHook(() => useIsLiveTarget('id-Atraxa'))
    const notLive = renderHook(() => useIsLiveTarget('id-Forest'))

    expect(live.result.current).toBe(true)
    expect(notLive.result.current).toBe(false)
  })

  it('gives the panel the resolved id and the pinned id, each on its own subscription', () => {
    setDefaultTarget('id-Atraxa')
    const target = renderHook(() => useInspectionTargetId())
    const pinned = renderHook(() => usePinnedId())

    expect(target.result.current).toBe('id-Atraxa')
    // The pinned subscription is the ID, not a boolean: AC 23's "announces exactly once" needs
    // the panel to see a pin MOVING between two cards, which `true` → `true` cannot express.
    expect(pinned.result.current).toBeNull()

    act(() => togglePin('id-Forest'))
    expect(pinned.result.current).toBe('id-Forest')
    act(() => togglePin('id-Island'))
    expect(pinned.result.current).toBe('id-Island')
  })

  it('re-renders a tile only when ITS liveness changed', () => {
    // THE MEASUREMENT Q7 RULED ON. Under zustand v5 there is no equality-function argument and
    // the comparison is React's referential default, so a selector returning `{ targetId,
    // pinned }` re-renders every subscriber on every hover — all 99 tiles, on the sweep the
    // whole card cache exists to make cheap. A boolean re-renders exactly the two tiles whose
    // value flipped, and this counts them rather than describing them.
    setDefaultTarget('id-Atraxa')
    let atraxaRenders = 0
    let forestRenders = 0
    renderHook(() => {
      atraxaRenders += 1
      return useIsLiveTarget('id-Atraxa')
    })
    renderHook(() => {
      forestRenders += 1
      return useIsLiveTarget('id-Forest')
    })
    const before = { atraxa: atraxaRenders, forest: forestRenders }

    // A hover that touches NEITHER tile: the target moves from Atraxa to Ponder. `act`, because
    // a store write outside it leaves React's re-render scheduled but not flushed — and a
    // counter read before the flush reports ZERO for every subscriber, which would make the
    // "did not re-render" half of this test pass for the wrong reason.
    act(() => setHovered('id-Ponder'))
    expect(forestRenders - before.forest).toBe(0)
    // Atraxa stopped being live, so it re-renders — exactly once, and it is the only one.
    expect(atraxaRenders - before.atraxa).toBe(1)
  })
})
