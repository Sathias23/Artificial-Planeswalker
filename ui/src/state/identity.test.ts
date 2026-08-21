/**
 * The identity refresh, at module level (story 17.1 — the I/O matrix's store rows).
 *
 * Drives {@link refreshInstanceId} through its INJECTED reader — the seam the function declares
 * for exactly this — and asserts what the system slice ends up holding. The wire half (what
 * `readInstanceId` makes of real responses) is `client.test.ts`'s; the trigger half (a `'live'`
 * transition fires this at all) is `connection.test.ts`'s; the glass half (the tooltip renders
 * the stored value) is `ConnectionPill.test.tsx`'s. This file owns the two semantics in between:
 * last-confirmed on failure, latest-issued-wins on races.
 *
 * `useSystemStore.setState` in `beforeEach` is the test-only restore every store test uses;
 * `store-writes.test.ts` excludes `.test.ts` files from its writer scan for exactly this case.
 */

import { beforeEach, describe, expect, it } from 'vitest'

import { refreshInstanceId } from './identity'
import { applyInstanceId, INITIAL_SYSTEM_STATE, useSystemStore } from './systemState'

const storedId = () => useSystemStore.getState().instanceId

/** A reader whose settlement the TEST owns — how out-of-order responses are driven. */
const deferred = () => {
  let resolve!: (id: string | null) => void
  const promise = new Promise<string | null>((r) => {
    resolve = r
  })
  return { read: () => promise, resolve }
}

beforeEach(() => {
  useSystemStore.setState(INITIAL_SYSTEM_STATE)
})

describe('a confirmed id is stored, and a failure never blanks one (last-confirmed)', () => {
  it('stores the id a successful read confirms (first connect)', async () => {
    await refreshInstanceId(() => Promise.resolve('abc'))

    expect(storedId()).toBe('abc')
  })

  it('stores the NEW id when a later refresh confirms a different process (AC-4)', async () => {
    await refreshInstanceId(() => Promise.resolve('old-process'))
    await refreshInstanceId(() => Promise.resolve('new-process'))

    expect(storedId()).toBe('new-process')
  })

  it('leaves the store untouched when the read fails before anything was confirmed', async () => {
    // `readInstanceId` folds non-200s, malformed 200s and rejections to `null` before this
    // module sees them; what this pins is that `null` writes NOTHING — the cold-open copy
    // ("not yet confirmed") stays true rather than being replaced by a placeholder.
    await refreshInstanceId(() => Promise.resolve(null))

    expect(storedId()).toBe(null)
  })

  it('leaves the LAST-CONFIRMED id standing when a later read fails', async () => {
    // The tooltip truthfully names the last backend this tab confirmed, through
    // `reconnecting`/`down` and through a refresh that got no answer alike. Blanking here
    // would replace a true statement about the past with an absence.
    await refreshInstanceId(() => Promise.resolve('abc'))
    await refreshInstanceId(() => Promise.resolve(null))

    expect(storedId()).toBe('abc')
  })

  it('never rejects — the trigger fires it void, so a rejection would be unhandled', async () => {
    // The injected reader is total by contract (`readInstanceId` never rejects), so this is
    // belt-and-braces at the seam: the promise settles, whatever the answer was.
    await expect(refreshInstanceId(() => Promise.resolve(null))).resolves.toBeUndefined()
  })
})

describe('applyInstanceId is change-detected — a re-confirmed id costs no write (review)', () => {
  it('notifies subscribers exactly once when the same id is applied twice', () => {
    // The guard this observes is why a reconnect to the SAME process is free: `App` subscribes
    // to this store selector-less, so an unguarded same-value write would re-render the whole
    // tree once per reconnect. Deleting the guard would leave every other test green (review
    // finding) — this count is the assertion that it exists.
    const writes: string[] = []
    const unsubscribe = useSystemStore.subscribe((state) => {
      writes.push(state.instanceId ?? '')
    })

    applyInstanceId('abc')
    applyInstanceId('abc')

    unsubscribe()
    expect(writes).toEqual(['abc'])
  })

  it('still notifies for a genuinely NEW id — the guard blocks repeats, not changes', () => {
    const writes: string[] = []
    const unsubscribe = useSystemStore.subscribe((state) => {
      writes.push(state.instanceId ?? '')
    })

    applyInstanceId('abc')
    applyInstanceId('def')

    unsubscribe()
    expect(writes).toEqual(['abc', 'def'])
  })
})

describe('two refreshes in flight: the latest-issued one wins (the generation guard)', () => {
  it('discards the FIRST refresh’s answer when it settles after the second’s', async () => {
    // The flapping-socket case: live → down → live inside one read timeout. The old process's
    // slow answer must not overwrite the id the new process just confirmed.
    const first = deferred()
    const second = deferred()

    const firstRun = refreshInstanceId(first.read)
    const secondRun = refreshInstanceId(second.read)

    second.resolve('new-process')
    await secondRun
    first.resolve('old-process')
    await firstRun

    expect(storedId()).toBe('new-process')
  })

  it('discards a superseded answer even when NOTHING newer has settled yet', async () => {
    // Issued-order, not settle-order, is the authority: once a newer refresh exists, the older
    // one's answer is evidence about the wrong moment whether or not the newer one has landed.
    const first = deferred()
    const second = deferred()

    const firstRun = refreshInstanceId(first.read)
    void refreshInstanceId(second.read)

    first.resolve('old-process')
    await firstRun

    expect(storedId()).toBe(null)
  })

  it('lets refreshes that settle IN order both land — the guard blocks staleness, not traffic', async () => {
    const first = deferred()
    const second = deferred()

    const firstRun = refreshInstanceId(first.read)
    first.resolve('first')
    await firstRun

    const secondRun = refreshInstanceId(second.read)
    second.resolve('second')
    await secondRun

    expect(storedId()).toBe('second')
  })
})
