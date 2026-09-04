/**
 * The deck announcer's modal gate, at component level (UX-DR45).
 *
 * WHAT IS HERE AND WHAT IS IN `App.test.tsx`. This file drives the two slices directly — the
 * refetch-settle counter and the agent-view status — and asserts what the component makes of
 * them: that a settle landing while a view is open writes NO text, that the settle is
 * nonetheless CONSUMED (so nothing is queued to fire on close), and that the next settle with
 * the view closed announces normally. It cannot prove that a real `deck_changed` frame reaches
 * this component through the socket, the fold, the store and the shell — that is `App.test.tsx`'s
 * end-to-end claim, driven through the real `fetch` seam, and the two are deliberately not the
 * same test.
 *
 * ⚠️ `useDeckStore.setState` rather than a production action, for `ConnectionPill.test.tsx`'s
 * recorded reason: `applyDeckState` is deliberately not exported (`deck.ts:176` — "the ONE
 * writer") and the only production path to a settled refetch is the boot plus a socket frame, so
 * driving it here would test the refetch rather than the announcer. `store-writes.test.ts`
 * excludes `.test.tsx` files from its writer scan for exactly this case; the SHIPPED component
 * still writes nothing.
 *
 * The counter is stepped by hand for the same reason, and it is the honest stand-in: `deck.ts`
 * increments it by exactly one in the refetch sequence's success arm and touches it nowhere
 * else (`deck.test.ts` pins every path), so "+1" IS what a settle looks like from in here.
 */

import { act, render } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import type { DeckDetail } from '../../api/schema'
import {
  INITIAL_AGENT_VIEW,
  type AgentViewContent,
  closeAgentView,
  openAgentView,
  resetAgentView,
  useAgentViewStore,
} from '../../state/agentView'
import { INITIAL_DECK_STATE, useDeckStore } from '../../state/deck'
import { DeckAnnouncer } from './DeckAnnouncer'
import { deckUpdatedAnnouncement } from './copy'

const detail = (mainboard: number, sideboard: number, id = 'deck-a'): DeckDetail => ({
  id,
  name: 'Atraxa Counter Cabinet v2 (owned)',
  format: 'brawl',
  strategy: null,
  color_identity: [],
  tags: [],
  mainboard_count: mainboard,
  sideboard_count: sideboard,
  distinct_cards: 2,
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
  cards: [],
})

const EMPTY_BOARDS = {
  commander: [],
  mainboard: [],
  sideboard: [],
  commanderQuantity: 0,
  mainboardQuantity: 0,
  sideboardQuantity: 0,
}

/** A deck on the glass, at the counts the sentence will read. */
const loadDeck = (mainboard: number, sideboard: number, id = 'deck-a') =>
  act(() =>
    useDeckStore.setState({
      deck: { status: 'deck', detail: detail(mainboard, sideboard, id), boards: EMPTY_BOARDS },
    }),
  )

/** One coalesced refetch settles — the +1 `deck.ts` writes beside the new decklist. */
const settleRefetch = (mainboard: number, sideboard: number, id = 'deck-a') =>
  act(() =>
    useDeckStore.setState({
      deck: { status: 'deck', detail: detail(mainboard, sideboard, id), boards: EMPTY_BOARDS },
      refetchSettles: useDeckStore.getState().refetchSettles + 1,
    }),
  )

const VIEW: AgentViewContent = {
  id: 'push-1',
  ts: '2026-08-15T09:15:00Z',
  kind: 'suggestions',
  title: 'Resilience options',
  count: 2,
  items: [],
}

const region = () => document.querySelector('.deck-announcement')
const seenNow = () => useDeckStore.getState().refetchSettles

beforeEach(() => {
  act(() => useDeckStore.setState({ deck: INITIAL_DECK_STATE, refetchSettles: 0 }))
  resetAgentView()
})

describe('a settle behind an OPEN agent view is DROPPED, not deferred (c7-6, UX-DR45)', () => {
  it('writes no text when the settle lands while a view is showing', () => {
    loadDeck(100, 0)
    render(<DeckAnnouncer />)
    // The mount-silence sentinel first: a region that was never empty could not show a
    // suppression, and every assertion below would be about a component that never speaks.
    expect(region()!.textContent).toBe('')

    act(() => openAgentView(VIEW))
    settleRefetch(101, 1)

    // THE HEADLINE CLAIM. The counter moved — this is a real settle, not a skipped one — and
    // the region stayed empty behind the dialog.
    expect(seenNow()).toBe(1)
    expect(region()!.textContent).toBe('')
  })

  it('does NOT queue the suppressed sentence to fire when the view closes', () => {
    // The distinction the whole design note is about: a DROP leaves nothing behind, a DEFER
    // would speak a stale count at the moment the reader returns from a dialog about something
    // else. Closing the view is a plain store write with no settle behind it, so if the region
    // spoke here the suppression would have been a queue.
    loadDeck(100, 0)
    render(<DeckAnnouncer />)
    act(() => openAgentView(VIEW))
    settleRefetch(101, 1)
    expect(region()!.textContent).toBe('')

    act(closeAgentView)

    expect(region()!.textContent).toBe('')
    expect(seenNow()).toBe(1)
  })

  it('announces the NEXT settle normally once the view is closed — no replay of the dropped one', () => {
    loadDeck(100, 0)
    render(<DeckAnnouncer />)
    act(() => openAgentView(VIEW))
    settleRefetch(101, 1)
    act(closeAgentView)
    expect(region()!.textContent).toBe('')

    // A second, ordinary refetch: the deck now totals 103 + 1. The sentence is about THIS
    // settle's counts and not about the suppressed one's, which is what "no replay" means.
    settleRefetch(103, 1)

    expect(region()!.textContent).toBe(deckUpdatedAnnouncement(103, 1))
    expect(region()!.textContent).toBe('Deck updated — 104 cards')
    expect(seenNow()).toBe(2)
  })

  it('suppresses EVERY settle for as long as the view stays open', () => {
    // The gate is re-evaluated per settle rather than latched, so a burst arriving during a long
    // read is silent throughout rather than silent once.
    loadDeck(100, 0)
    render(<DeckAnnouncer />)
    act(() => openAgentView(VIEW))

    settleRefetch(101, 0)
    settleRefetch(102, 0)
    settleRefetch(103, 0)

    expect(seenNow()).toBe(3)
    expect(region()!.textContent).toBe('')
  })
})

describe('the gate changes nothing about the closed-view paths (non-vacuity)', () => {
  it('still announces a settle with no view open — the c7-5 behaviour, unmoved', () => {
    loadDeck(100, 0)
    render(<DeckAnnouncer />)

    settleRefetch(101, 1)

    // Without this the suppression tests above would all pass on a component that never speaks
    // at all, which is the shape of coverage this repo has caught in its own guards before.
    expect(useAgentViewStore.getState()).toEqual(INITIAL_AGENT_VIEW)
    expect(region()!.textContent).toBe('Deck updated — 102 cards')
  })

  it('leaves a STANDING sentence alone when a view opens over it', () => {
    // Opening a view is not a settle, so nothing is recomputed and the text node is not touched
    // — a live region speaks on MUTATION, so leaving it in place announces nothing. Emptying it
    // here would be inventing a second clearing rule; the only one is "the deck departed".
    loadDeck(100, 0)
    render(<DeckAnnouncer />)
    settleRefetch(101, 1)
    expect(region()!.textContent).toBe('Deck updated — 102 cards')

    act(() => openAgentView(VIEW))

    expect(region()!.textContent).toBe('Deck updated — 102 cards')
  })

  it('still empties a standing sentence when the deck departs BEHIND an open view', () => {
    // The clearing branch is deliberately ungated: a sentence asserting "Deck updated — 102
    // cards" beside a no-deck panel is a false claim whether or not a dialog is covering it, and
    // the deletion walk (App.test.tsx) is exactly that arrangement.
    loadDeck(100, 0)
    render(<DeckAnnouncer />)
    settleRefetch(101, 1)
    expect(region()!.textContent).toBe('Deck updated — 102 cards')

    act(() => openAgentView(VIEW))
    act(() => useDeckStore.setState({ deck: { status: 'none' } }))

    expect(region()!.textContent).toBe('')
    // …and emptying is not a settle: the counter is untouched, so nothing was announced by it.
    expect(seenNow()).toBe(1)
  })

  it('keeps the region itself mounted and polite behind a view (the census contract)', () => {
    // Suppression is about the TEXT, never about the region: tearing the element out of the
    // accessibility tree mid-session would break both App live-region censuses, which count
    // three regions at rest and three mid-flight.
    loadDeck(100, 0)
    render(<DeckAnnouncer />)
    act(() => openAgentView(VIEW))
    settleRefetch(101, 1)

    expect(document.querySelectorAll('[aria-live]')).toHaveLength(1)
    expect(region()!.getAttribute('aria-live')).toBe('polite')
    expect(region()!.className).toContain('visually-hidden')
  })
})
