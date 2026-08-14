import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { DeckCardSummary } from '../api/schema'
import { resetCardCache, useCardStore } from './cards'
import { boardsOf } from './deckGroups'
import {
  clearFocused,
  clearHovered,
  clearPin,
  clearTransientTargets,
  coldOpenTargetOf,
  evictDepartedPin,
  resetInspection,
  setDefaultTarget,
  setFocused,
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
    // THE RACE THIS EXISTS FOR (Q8's one addition), per modality: `mouseleave` on the tile
    // being left and `mouseenter` on the tile being reached both fire, and the losing tile's
    // is free to land second. An unkeyed clear would then erase the winner's target and the
    // panel would snap back to the cold-open card in the middle of a sweep.
    setHovered('id-A')
    setHovered('id-B')
    clearHovered('id-A')
    expect(useInspectionStore.getState().hoveredId).toBe('id-B')

    clearHovered('id-B')
    expect(useInspectionStore.getState().hoveredId).toBeNull()
  })

  it('clears the focus only for the card that still holds it — the blur-after-focus race', () => {
    setFocused('id-A')
    setFocused('id-B')
    clearFocused('id-A')
    expect(useInspectionStore.getState().focusedId).toBe('id-B')
  })

  it('clears BOTH transients at once on a deck transition', () => {
    // `clearTransientTargets` is the boards effect's verb (review 2026-08-05): a hover or a
    // focus pointing into a deck that left the glass is stale whichever modality set it.
    setHovered('id-A')
    setFocused('id-B')
    clearTransientTargets()
    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(useInspectionStore.getState().focusedId).toBeNull()
    expect(targetIdOf(useInspectionStore.getState())).toBeNull()
  })
})

describe('hover and focus are TWO slots, resolved by recency (PR #44 P1, UX-DR14)', () => {
  it('a mouse-leave cannot strand a still-focused tile', () => {
    // THE REPORTED DEFECT, found independently by the review's edge-case layer and by Greptile:
    // Tab-focus tile A, sweep the mouse over B and away. With one shared slot the leave erased
    // A's target and the panel snapped to the cold-open card while A still drew its focus ring
    // — the one case where "hover OR keyboard focus" parity has both at once.
    setDefaultTarget('id-Atraxa')
    setFocused('id-A')
    setHovered('id-B')
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-B')

    clearHovered('id-B')
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-A')
  })

  it('a blur cannot strand a still-hovered tile — the same hole, mirrored', () => {
    setDefaultTarget('id-Atraxa')
    setHovered('id-B')
    setFocused('id-A')
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-A')

    clearFocused('id-A')
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-B')
  })

  it('while both hold a card, the modality used LAST wins — in both orders', () => {
    // "Whichever the person used last" is the only resolution that matches what the eye is
    // doing: Tab past a resting pointer and the panel follows the keyboard; sweep the mouse
    // past a forgotten focus ring and it follows the pointer.
    setFocused('id-A')
    setHovered('id-B')
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-B')

    setFocused('id-C')
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-C')
  })

  it('a clear does not rewrite recency — letting go says nothing about intent', () => {
    // Hover B (last=hover), focus A, hover C, leave C: the pointer let go, so the panel falls
    // to the focused tile even though the POINTER was the last modality used. A clear that
    // flipped recency would instead have to invent an answer for a modality holding nothing.
    setFocused('id-A')
    setHovered('id-C')
    clearHovered('id-C')
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-A')
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

  it('refuses it on keyboard focus — the same door, the other modality', () => {
    setDefaultTarget('id-Atraxa')
    unknown('id-ghost')
    setFocused('id-ghost')

    expect(useInspectionStore.getState().focusedId).toBeNull()
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

describe('pin eviction is a membership transition, not a deck lookup (c7-4, R9)', () => {
  // The four-row truth table of the R9 rule (ruling 2026-08-14), plus the sideboard row. The
  // verb reads only the TWO DECKLISTS handed to it — no pin-time classification anywhere — and
  // its caller (`CardDetail`'s boards effect, via `deckMemory`) is `CardDetail.test.tsx`'s and
  // `App.test.tsx`'s to prove; what is pinned here is the rule itself.
  const deckWith = (...names: string[]) => boardsOf(names.map((name) => row(name, 'Sorcery')))

  it('evicts on present → absent, and the panel falls back to the default resolution', () => {
    setDefaultTarget('id-Ponder')
    togglePin('id-Forest')

    evictDepartedPin(deckWith('Forest', 'Ponder'), deckWith('Ponder'))

    expect(useInspectionStore.getState().pinnedId).toBeNull()
    // `clearPin` alone IS the fall-back: resolution lands on the default target, which the
    // boards effect re-sets to `coldOpenTargetOf(next)` — the first card the grid draws.
    expect(targetIdOf(useInspectionStore.getState())).toBe('id-Ponder')
  })

  it('survives absent → absent — the pinned suggestion, with no special-casing (c6-7 debt)', () => {
    togglePin('id-Birds of Paradise')

    evictDepartedPin(deckWith('Ponder'), deckWith('Ponder', 'Opt'))

    expect(useInspectionStore.getState().pinnedId).toBe('id-Birds of Paradise')
  })

  it('survives present → present — the same-deck refetch this story exists for', () => {
    togglePin('id-Forest')

    evictDepartedPin(deckWith('Forest', 'Ponder'), deckWith('Forest', 'Opt'))

    expect(useInspectionStore.getState().pinnedId).toBe('id-Forest')
  })

  it('never evicts on a first boards — previous === null has no departing deck', () => {
    togglePin('id-Forest')

    evictDepartedPin(null, deckWith('Ponder'))

    expect(useInspectionStore.getState().pinnedId).toBe('id-Forest')
  })

  it('counts the SIDEBOARD as membership — a sideboard pin evicts when its card leaves', () => {
    // A sideboard card is pinnable (DeckList rows) and is "in the deck's list" in R9's words —
    // deliberately asymmetric with `coldOpenTargetOf`, which draws only what the grid draws.
    togglePin('id-Pithing Needle')
    const departing = boardsOf([
      row('Pithing Needle', 'Artifact', { sideboard: true }),
      row('Ponder', 'Sorcery'),
    ])

    evictDepartedPin(departing, deckWith('Ponder'))
    expect(useInspectionStore.getState().pinnedId).toBeNull()

    // …and STAYING in the sideboard is membership too: no eviction on present → present.
    togglePin('id-Pithing Needle')
    evictDepartedPin(departing, departing)
    expect(useInspectionStore.getState().pinnedId).toBe('id-Pithing Needle')
  })

  it('does nothing at all while no pin is held', () => {
    evictDepartedPin(deckWith('Forest'), deckWith('Ponder'))
    expect(useInspectionStore.getState().pinnedId).toBeNull()
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
