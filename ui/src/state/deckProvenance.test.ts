/**
 * Push provenance (quick wins 1.5): which saved deck a push is about, and whether it is stale.
 *
 * `provenanceOf` is pure, so each row of the plan's I/O matrix is one call; the store half is
 * driven through its exported verbs over a stubbed `fetch`, and the hook through `renderHook`
 * against the real deck and provenance stores.
 */

import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DeckDetail } from '../api/schema'
import type { AgentViewContent } from './agentView'
import { resetDeckState, useDeckStore } from './deck'
import { boardsOfDeck } from './deckGroups'
import {
  provenanceOf,
  refreshDeckProvenance,
  refreshDeckProvenanceIfWanted,
  resetDeckProvenance,
  useDeckProvenanceStore,
  usePushProvenance,
} from './deckProvenance'

const SENT = '2026-11-10T10:00:00+00:00'
const BEFORE = '2026-11-10T09:00:00+00:00'
const AFTER = '2026-11-10T11:00:00+00:00'

const A = { name: 'Boros Aggro', updatedAt: BEFORE }

const decksBody = (...rows: { id: string; name: string; updated_at: string }[]) =>
  new Response(JSON.stringify(rows), { status: 200 })

afterEach(() => {
  vi.unstubAllGlobals()
  resetDeckProvenance()
  resetDeckState()
})

describe('provenanceOf — one call per row of the I/O matrix', () => {
  it('other deck: names the push’s own deck and marks it not the deck on screen', () => {
    expect(provenanceOf('deck-a', SENT, A, true, 'deck-b')).toEqual({
      deckName: 'Boros Aggro',
      stale: ['other_deck'],
    })
  })

  it('edited since: a later updated_at marks it changed after it was sent', () => {
    expect(provenanceOf('deck-a', SENT, { ...A, updatedAt: AFTER }, true, 'deck-a')).toEqual({
      deckName: 'Boros Aggro',
      stale: ['edited'],
    })
  })

  it('fresh, same deck: labelled and not stale', () => {
    expect(provenanceOf('deck-a', SENT, A, true, 'deck-a')).toEqual({
      deckName: 'Boros Aggro',
      stale: [],
    })
  })

  it('an edit at the same instant as the push is not "after" it', () => {
    expect(provenanceOf('deck-a', SENT, { ...A, updatedAt: SENT }, true, 'deck-a')?.stale).toEqual(
      [],
    )
  })

  it('no deck_id: nothing to say, whatever else is known', () => {
    expect(provenanceOf(undefined, SENT, A, true, 'deck-b')).toBeNull()
    expect(provenanceOf(null, SENT, A, true, 'deck-b')).toBeNull()
  })

  it('unknown id: absent from a loaded answer reads as no longer saved, and stale', () => {
    expect(provenanceOf('deck-gone', SENT, undefined, true, null)).toEqual({
      deckName: null,
      stale: ['missing'],
    })
  })

  it('summaries not loaded: no label yet and no stale claim', () => {
    expect(provenanceOf('deck-a', SENT, undefined, false, 'deck-b')).toBeNull()
    expect(provenanceOf('deck-a', SENT, A, false, 'deck-b')).toBeNull()
  })

  it('no deck displayed: there is no deck on screen to disagree with', () => {
    expect(provenanceOf('deck-a', SENT, A, true, null)?.stale).toEqual([])
  })

  it('an unparseable ts or updated_at makes no edited claim', () => {
    const edited = { ...A, updatedAt: AFTER }
    expect(provenanceOf('deck-a', 'not a time', edited, true, 'deck-a')?.stale).toEqual([])
    expect(provenanceOf('deck-a', undefined, edited, true, 'deck-a')?.stale).toEqual([])
    expect(
      provenanceOf('deck-a', SENT, { ...A, updatedAt: 'soon' }, true, 'deck-a')?.stale,
    ).toEqual([])
  })

  it('edited AND another deck displayed states both reasons', () => {
    expect(provenanceOf('deck-a', SENT, { ...A, updatedAt: AFTER }, true, 'deck-b')?.stale).toEqual(
      ['edited', 'other_deck'],
    )
  })
})

describe('the deck list is read only when wanted, latest-wins, and kept on failure', () => {
  it('reads nothing until some push has named a deck', () => {
    const fetchMock = vi.fn(() => Promise.resolve(decksBody()))
    vi.stubGlobal('fetch', fetchMock)

    refreshDeckProvenanceIfWanted()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(useDeckProvenanceStore.getState().wanted).toBe(false)
  })

  it('a refresh files the decks by id and arms later re-reads', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(decksBody({ id: 'deck-a', name: 'Boros Aggro', updated_at: BEFORE })),
    )
    vi.stubGlobal('fetch', fetchMock)

    await refreshDeckProvenance()

    const state = useDeckProvenanceStore.getState()
    expect(state.loaded).toBe(true)
    expect(state.wanted).toBe(true)
    expect(state.decks['deck-a']).toEqual(A)

    refreshDeckProvenanceIfWanted()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('a failed read keeps the previous map rather than blanking every label', async () => {
    vi.stubGlobal('fetch', () =>
      Promise.resolve(decksBody({ id: 'deck-a', name: 'Boros Aggro', updated_at: BEFORE })),
    )
    await refreshDeckProvenance()
    vi.stubGlobal('fetch', () => Promise.reject(new TypeError('Failed to fetch')))

    await refreshDeckProvenance()

    expect(useDeckProvenanceStore.getState().loaded).toBe(true)
    expect(useDeckProvenanceStore.getState().decks['deck-a']).toEqual(A)
  })

  it('a failed FIRST read leaves the slice unloaded, so nothing is claimed', async () => {
    vi.stubGlobal('fetch', () => Promise.resolve(new Response('{}', { status: 503 })))

    await refreshDeckProvenance()

    expect(useDeckProvenanceStore.getState().loaded).toBe(false)
    expect(useDeckProvenanceStore.getState().wanted).toBe(true)
  })

  it('a read overtaken by a newer one writes nothing, whichever settles last', async () => {
    let releaseOld: (response: Response) => void = () => {}
    const old = new Promise<Response>((resolve) => (releaseOld = resolve))
    const fetchMock = vi
      .fn<() => Promise<Response>>()
      .mockReturnValueOnce(old)
      .mockResolvedValueOnce(decksBody({ id: 'deck-a', name: 'Renamed', updated_at: AFTER }))
    vi.stubGlobal('fetch', fetchMock)

    const first = refreshDeckProvenance()
    await refreshDeckProvenance()
    releaseOld(decksBody({ id: 'deck-a', name: 'Boros Aggro', updated_at: BEFORE }))
    await first

    expect(useDeckProvenanceStore.getState().decks['deck-a']?.name).toBe('Renamed')
  })

  it('an id like __proto__ is an ordinary key, not a reach into Object.prototype', async () => {
    vi.stubGlobal('fetch', () => Promise.resolve(decksBody()))
    await refreshDeckProvenance()
    const absent = renderHook(() => usePushProvenance(contentFor('__proto__', SENT)))
    expect(absent.result.current).toEqual({ deckName: null, stale: ['missing'] })
    absent.unmount()

    vi.stubGlobal('fetch', () =>
      Promise.resolve(decksBody({ id: '__proto__', name: 'Odd Name', updated_at: BEFORE })),
    )
    await refreshDeckProvenance()
    const present = renderHook(() => usePushProvenance(contentFor('__proto__', SENT)))

    expect(present.result.current).toEqual({ deckName: 'Odd Name', stale: [] })
  })
})

/** A minimal push for the hook: only `deckId` and `ts` are read. */
const contentFor = (deckId: string | undefined, ts: string): AgentViewContent => ({
  id: 'push-1',
  ts,
  kind: 'suggestions',
  title: 'Suggestions',
  count: 0,
  items: [],
  deckId,
})

/** Put a deck on the glass, the way a settled boot does. */
const display = (id: string) => {
  const detail = { id, name: id, cards: [] } as unknown as DeckDetail
  act(() => {
    useDeckStore.setState({ deck: { status: 'deck', detail, boards: boardsOfDeck(detail) } })
  })
}

describe('usePushProvenance follows the push’s own deck, live', () => {
  it('returns null for no content and for a push that names no deck, asking nothing', () => {
    const fetchMock = vi.fn(() => Promise.resolve(decksBody()))
    vi.stubGlobal('fetch', fetchMock)

    expect(renderHook(() => usePushProvenance(null)).result.current).toBeNull()
    expect(renderHook(() => usePushProvenance(contentFor(undefined, SENT))).result.current).toBe(
      null,
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('flips to edited when a re-read brings a later updated_at', async () => {
    vi.stubGlobal('fetch', () =>
      Promise.resolve(decksBody({ id: 'deck-a', name: 'Boros Aggro', updated_at: BEFORE })),
    )
    await refreshDeckProvenance()
    display('deck-a')
    const { result } = renderHook(() => usePushProvenance(contentFor('deck-a', SENT)))
    expect(result.current).toEqual({ deckName: 'Boros Aggro', stale: [] })

    vi.stubGlobal('fetch', () =>
      Promise.resolve(decksBody({ id: 'deck-a', name: 'Boros Aggro', updated_at: AFTER })),
    )
    await act(() => refreshDeckProvenance())

    expect(result.current).toEqual({ deckName: 'Boros Aggro', stale: ['edited'] })
  })

  it('keeps naming deck A after the glass switches to deck B', async () => {
    vi.stubGlobal('fetch', () =>
      Promise.resolve(
        decksBody(
          { id: 'deck-a', name: 'Boros Aggro', updated_at: BEFORE },
          { id: 'deck-b', name: 'Dimir Mill', updated_at: BEFORE },
        ),
      ),
    )
    await refreshDeckProvenance()
    display('deck-a')
    const { result } = renderHook(() => usePushProvenance(contentFor('deck-a', SENT)))

    display('deck-b')

    expect(result.current).toEqual({ deckName: 'Boros Aggro', stale: ['other_deck'] })
  })
})
