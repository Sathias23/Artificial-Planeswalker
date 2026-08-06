/**
 * The format-check slice: one read, one writer, and a staleness rule that a deck change cannot
 * defeat (story c4-10, AC 9, AC 11, AC 12).
 *
 * Every fixture here is either a **verified real row** or **declared synthetic in place**, with
 * no third option (AC 26). The reports below were read out of the running backend at `4e31ea7`
 * by driving the real ASGI app against the shipped database; where a state has no real instance
 * — there are five — the fixture says so at its declaration and names how it was produced.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { FormatCheckOutcome } from '../api/client'
import {
  INITIAL_FORMAT_CHECK_STATE,
  clearFormatCheck,
  loadFormatCheck,
  resetFormatCheckState,
  useFormatCheckStore,
} from './formatCheck'
import { ALL_PASS_REPORT, FORMATLESS_REPORT } from './formatCheck.fixtures'

const stateNow = () => useFormatCheckStore.getState().formatCheck

/** A reader that never settles until the test releases it. */
const deferred = () => {
  let release: (outcome: FormatCheckOutcome) => void = () => {}
  const promise = new Promise<FormatCheckOutcome>((resolve) => {
    release = resolve
  })
  return { read: () => promise, release }
}

beforeEach(() => {
  resetFormatCheckState()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the slice starts idle and every outcome is a value (AC 9)', () => {
  it('starts idle', () => {
    expect(stateNow()).toEqual(INITIAL_FORMAT_CHECK_STATE)
    expect(stateNow()).toEqual({ status: 'idle' })
  })

  it('goes loading, then report — and the report is the wire value verbatim', async () => {
    const { read, release } = deferred()

    const pending = loadFormatCheck('deck-1', read)
    expect(stateNow()).toEqual({ status: 'loading' })

    release({ kind: 'report', report: ALL_PASS_REPORT })
    await pending

    expect(stateNow()).toEqual({ status: 'report', report: ALL_PASS_REPORT })
  })

  const OUTCOMES: [string, FormatCheckOutcome][] = [
    ['a refusal', { kind: 'error', reason: 'deck_not_found' }],
    ['an unreadable body', { kind: 'error', reason: null }],
    ['an unreachable backend', { kind: 'unreachable' }],
  ]

  it.each(OUTCOMES)(
    'turns %s into `refused`, and never into a panel (Q6, AC 12)',
    async (_label, outcome) => {
      await loadFormatCheck('deck-1', () => Promise.resolve(outcome))

      expect(stateNow()).toEqual({ status: 'refused' })
    },
  )

  it('never rejects, even when an injected reader throws', async () => {
    await expect(
      loadFormatCheck('deck-1', () => {
        throw new TypeError('nope')
      }),
    ).resolves.toBeUndefined()

    expect(stateNow()).toEqual({ status: 'refused' })
  })

  it('refuses a blank id with NO request at all', async () => {
    // `formatCheckPath('')` is `/api/deck//format-check`, which addresses nothing — a route-shape
    // fact, answered above the route exactly as `hydrateCard` and `createDeckBoot` answer theirs.
    const read = vi.fn(() => Promise.resolve<FormatCheckOutcome>({ kind: 'unreachable' }))

    await loadFormatCheck('', read)
    expect(read).not.toHaveBeenCalled()
    expect(stateNow()).toEqual({ status: 'refused' })

    // …and a whitespace-only id too. `deckPath('  ')` would encode to `/api/deck/%20%20/…`, a
    // request guaranteed to 404 — the second-lock weakness `createDeckBoot`'s review closed.
    await loadFormatCheck('   ', read)
    expect(read).not.toHaveBeenCalled()
  })
})

describe('a deck change mid-flight cannot land the old deck’s report (AC 9)', () => {
  it('drops a superseded load, even when it settles LAST', async () => {
    // THE FAILURE THIS PREVENTS, CONCRETELY: the agent switches decks while a read is in flight
    // and the previous deck's legality verdict lands on top of the new one — a panel confidently
    // describing a deck that is no longer on the glass. The old read settling SECOND is the
    // ordering that a naive "last write wins" gets wrong, so it is the one asserted.
    const first = deferred()
    const second = deferred()

    const a = loadFormatCheck('deck-1', first.read)
    const b = loadFormatCheck('deck-2', second.read)

    second.release({ kind: 'report', report: ALL_PASS_REPORT })
    await b
    expect(stateNow()).toEqual({ status: 'report', report: ALL_PASS_REPORT })

    // The abandoned first read settles now, with a DIFFERENT report — and writes nothing.
    first.release({ kind: 'report', report: FORMATLESS_REPORT })
    await a
    expect(stateNow()).toEqual({ status: 'report', report: ALL_PASS_REPORT })
  })

  it('drops a load abandoned by clearFormatCheck — a cleared world stays cleared', async () => {
    const { read, release } = deferred()

    const pending = loadFormatCheck('deck-1', read)
    clearFormatCheck()
    expect(stateNow()).toEqual({ status: 'idle' })

    release({ kind: 'report', report: ALL_PASS_REPORT })
    await pending

    expect(stateNow()).toEqual({ status: 'idle' })
  })

  it('clears a settled report when the deck goes away — it does not outlive its deck', async () => {
    await loadFormatCheck('deck-1', () =>
      Promise.resolve({ kind: 'report', report: ALL_PASS_REPORT }),
    )
    expect(stateNow().status).toBe('report')

    clearFormatCheck()

    expect(stateNow()).toEqual({ status: 'idle' })
  })

  it('is a REPLACE, not a merge — no arm keeps the previous arm’s fields', async () => {
    // `deck.ts` found this with a probe: zustand's `setState` merges by default, so a store whose
    // shape IS the union would accept `{status:'idle'}` and keep the `report` beside it. The
    // wrapper key is what makes that impossible rather than guarded; this is the assertion that
    // would notice if the key were ever unwrapped.
    await loadFormatCheck('deck-1', () =>
      Promise.resolve({ kind: 'report', report: ALL_PASS_REPORT }),
    )
    await loadFormatCheck('deck-2', () => Promise.resolve({ kind: 'unreachable' }))

    expect(stateNow()).toEqual({ status: 'refused' })
    expect(Object.keys(stateNow())).toEqual(['status'])
  })
})

describe('one request per call, and never a retry (AC 11)', () => {
  const RETRY_OUTCOMES: [string, FormatCheckOutcome][] = [
    ['a refusal', { kind: 'error', reason: 'database_not_initialized' }],
    ['an unreachable backend', { kind: 'unreachable' }],
  ]

  it.each(RETRY_OUTCOMES)(
    'asks exactly once for %s — no timer, no backoff',
    async (_label, outcome) => {
      const read = vi.fn(() => Promise.resolve(outcome))

      await loadFormatCheck('deck-1', read)
      // Ten minutes of a real timer would prove nothing here — there is no timer to advance. What
      // proves it is that the module exports no scheduler and this counter never moves again.
      expect(read).toHaveBeenCalledTimes(1)
      expect(read).toHaveBeenCalledWith('deck-1')
    },
  )
})
