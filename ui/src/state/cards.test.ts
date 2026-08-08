/**
 * The card cache's whole contract, asserted as REQUEST COUNTS (story c4-1, AC 24, AC 25).
 *
 * **The count is the assertion, not the bytes.** Deduping is a claim about how many requests were
 * issued, so every test here drives an INJECTED reader — following `poller.ts`'s
 * `read?: () => Promise<DecksOutcome>` seam, which exists precisely so tests need no global
 * `fetch` stub — and asserts how many times it was called. A test that asserted on cached VALUES
 * would pass over an implementation that fetched a hundred times and threw ninety-nine answers
 * away, which is the exact defect this story exists to prevent.
 *
 * jsdom, the jest-dom matchers and `afterEach(cleanup)` come from the `dom` vitest project; this
 * file needs the store's React binding and lives beside the module it tests.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import type { CardOutcome } from '../api/client'
import type { Card, CardSummary, DeckCardSummary } from '../api/schema'
import { useSystemStore, INITIAL_SYSTEM_STATE } from './systemState'
import {
  INITIAL_CARD_CACHE,
  MAX_ATTEMPTS_PER_CARD,
  hydrateCard,
  resetCardAttempts,
  resetCardCache,
  seedCardSummaries,
  useCardStore,
} from './cards'

// ===================== fixtures =========================================================

/** Canonical printing uuids, in the lowercase hyphenated spelling the route's pattern demands. */
const idAt = (n: number): string => `0d7ac8e1-2ea4-4b6c-9b6a-${n.toString(16).padStart(12, '0')}`

const SOL_RING = idAt(1)
const ARCANE_SIGNET = idAt(2)

const summary = (id: string, name: string): CardSummary => ({
  id,
  name,
  mana_cost: '{1}',
  cmc: 1,
  type_line: 'Artifact',
  oracle_text: '',
  colors: [],
  rarity: 'uncommon',
  set_code: 'cmr',
})

const deckCard = (id: string, name: string): DeckCardSummary => ({
  card_id: id,
  quantity: 1,
  sideboard: false,
  commander: false,
  card: summary(id, name),
})

const fullCard = (id: string, name: string): Card => ({
  id,
  name,
  oracle_id: 'o-1',
  mana_cost: '{1}',
  cmc: 1,
  type_line: 'Artifact',
  oracle_text: '{T}: Add {C}{C}.',
  rarity: 'uncommon',
  set_code: 'cmr',
  set_name: 'Commander Legends',
  collector_number: '1',
  colors: [],
  color_identity: [],
  legalities: { commander: 'legal' },
  games: ['paper'],
})

/** A reader that answers the same outcome for every id, and counts how often it was asked. */
const readerAnswering = (outcome: CardOutcome) => {
  const calls: string[] = []
  const read = vi.fn((id: string): Promise<CardOutcome> => {
    calls.push(id)
    return Promise.resolve(outcome)
  })
  return { read, calls }
}

/** A reader that hydrates whatever it is asked for, and counts per id. */
const hydratingReader = () => {
  const calls: string[] = []
  const read = vi.fn((id: string): Promise<CardOutcome> => {
    calls.push(id)
    return Promise.resolve({ kind: 'card', card: fullCard(id, `Card ${id.slice(-4)}`) })
  })
  return { read, calls }
}

/**
 * A reader whose answer is held open until the returned `settle` is called (AC 7, AC 10).
 *
 * `settle`/`fail` flush EVERY pending read, not the most recent one: a single-slot resolver
 * silently drops all callers but the last, and the two-different-ids test would leave its first
 * read pending past the test's end — a fixture that quietly asserts against the wrong promise.
 */
const deferredReader = () => {
  const calls: string[] = []
  const settlers: { resolve: (outcome: CardOutcome) => void; reject: (error: unknown) => void }[] =
    []
  const read = vi.fn(
    (id: string) =>
      new Promise<CardOutcome>((resolve, reject) => {
        calls.push(id)
        settlers.push({ resolve, reject })
      }),
  )
  return {
    read,
    calls,
    settle: (outcome: CardOutcome) => settlers.splice(0).forEach((s) => s.resolve(outcome)),
    fail: (error: unknown) => settlers.splice(0).forEach((s) => s.reject(error)),
  }
}

const entryOf = (id: string) => useCardStore.getState().cards[id]

afterEach(() => {
  resetCardCache()
  useSystemStore.setState(INITIAL_SYSTEM_STATE, true)
  vi.unstubAllGlobals()
})

// ===================== AC 1, AC 4: the three conditions =================================

describe('the cache distinguishes never-seen, summary-known, loading and hydrated (AC 4)', () => {
  it('has no entry at all for an id it has never seen — the ONLY meaning of undefined', () => {
    expect(entryOf(SOL_RING)).toBeUndefined()
  })

  it('is keyed by the printing uuid, so two ids are two entries (AC 1)', () => {
    seedCardSummaries([deckCard(SOL_RING, 'Sol Ring'), deckCard(ARCANE_SIGNET, 'Arcane Signet')])

    expect(Object.keys(useCardStore.getState().cards).sort()).toEqual(
      [SOL_RING, ARCANE_SIGNET].sort(),
    )
  })

  it('lets a summary-known consumer render name, cost and type line with NO request', () => {
    // `EXPERIENCE.md`: "name and cost are known at hover time and render immediately, the rest
    // fills in place — no spinner". This assertion is that sentence, mechanically.
    seedCardSummaries([deckCard(SOL_RING, 'Sol Ring')])

    const entry = entryOf(SOL_RING)
    expect(entry?.status).toBe('summary')
    expect(entry).toMatchObject({
      summary: { name: 'Sol Ring', mana_cost: '{1}', type_line: 'Artifact' },
    })
  })

  it('distinguishes STILL LOADING from UNKNOWN CARD as two values, not two absences', async () => {
    const pendingRead = deferredReader()
    const inFlight = hydrateCard(SOL_RING, pendingRead.read)

    expect(entryOf(SOL_RING)?.status).toBe('loading')

    pendingRead.settle({ kind: 'error', reason: 'card_not_found' })
    await inFlight

    expect(entryOf(SOL_RING)?.status).toBe('unknown')
    // Neither condition is `undefined`, which is what makes AC 4 mechanical rather than a
    // convention a consumer has to remember.
    expect(entryOf(SOL_RING)).toBeDefined()
  })

  it('keeps a known summary visible WHILE the full record is loading', async () => {
    // The skeleton-vs-placeholder policy: the rest fills in *place*. A tile that was drawable
    // before the hover must not flash empty during it.
    seedCardSummaries([deckCard(SOL_RING, 'Sol Ring')])
    const pendingRead = deferredReader()
    const inFlight = hydrateCard(SOL_RING, pendingRead.read)

    expect(entryOf(SOL_RING)).toMatchObject({
      status: 'loading',
      summary: { name: 'Sol Ring' },
    })

    pendingRead.settle({ kind: 'card', card: fullCard(SOL_RING, 'Sol Ring') })
    await inFlight
  })

  it('reaches hydrated, and hydrated carries the full record', async () => {
    const reader = hydratingReader()

    await hydrateCard(SOL_RING, reader.read)

    expect(entryOf(SOL_RING)).toMatchObject({
      status: 'hydrated',
      card: { id: SOL_RING, legalities: { commander: 'legal' }, set_name: 'Commander Legends' },
    })
  })
})

// ===================== AC 5, AC 6: seeding is free ======================================

describe('seeding from a deck payload issues ZERO requests (AC 5, AC 6)', () => {
  // `seedCardSummaries` takes no reader — it has nothing to inject — so the ONLY honest request
  // count here is the network door itself. A spy on an unwired local mock would be vacuous: an
  // implementation that fired-and-forgot `hydrateCard(id)` per seeded id (default reader, global
  // `fetch`) would sail past it. The global stub is what makes these two assertions falsifiable.
  it('populates the summary tier for every id with no reader at all', () => {
    const fetchSpy = vi.fn<typeof fetch>()
    vi.stubGlobal('fetch', fetchSpy)

    seedCardSummaries([deckCard(SOL_RING, 'Sol Ring'), deckCard(ARCANE_SIGNET, 'Arcane Signet')])

    // The whole argument of the story's measurement: 38,182 bytes in ONE request the app already
    // makes, against 212,436 bytes in 99 it would otherwise have to.
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(entryOf(SOL_RING)?.status).toBe('summary')
    expect(entryOf(ARCANE_SIGNET)?.status).toBe('summary')
  })

  it('walks no deck issuing per-card reads — 99 seeded ids cost 0 requests (AC 6)', () => {
    const fetchSpy = vi.fn<typeof fetch>()
    vi.stubGlobal('fetch', fetchSpy)
    const deck = Array.from({ length: 99 }, (_, i) => deckCard(idAt(i + 100), `Card ${i}`))

    seedCardSummaries(deck)

    expect(fetchSpy).not.toHaveBeenCalled()
    expect(Object.keys(useCardStore.getState().cards)).toHaveLength(99)
  })

  it('leaves a HYDRATED id hydrated — seeding never downgrades a paid-for request', async () => {
    const reader = hydratingReader()
    await hydrateCard(SOL_RING, reader.read)

    seedCardSummaries([deckCard(SOL_RING, 'Sol Ring')])

    expect(entryOf(SOL_RING)?.status).toBe('hydrated')
  })

  it('leaves an UNKNOWN id unknown, and does not re-arm it', async () => {
    // If seeding reset the tier, a deck refetch would defeat AC 11: the id would be re-requested
    // the moment anything re-read the deck.
    const refusing = readerAnswering({ kind: 'error', reason: 'card_not_found' })
    await hydrateCard(SOL_RING, refusing.read)

    seedCardSummaries([deckCard(SOL_RING, 'Sol Ring')])

    expect(entryOf(SOL_RING)?.status).toBe('unknown')
    await hydrateCard(SOL_RING, refusing.read)
    expect(refusing.read).toHaveBeenCalledTimes(1)
  })

  it('fills in the summary of an id that was refused, so the tile can still be named', async () => {
    const refusing = readerAnswering({ kind: 'error', reason: 'database_unavailable' })
    await hydrateCard(SOL_RING, refusing.read)

    seedCardSummaries([deckCard(SOL_RING, 'Sol Ring')])

    expect(entryOf(SOL_RING)).toMatchObject({
      status: 'unknown',
      summary: { name: 'Sol Ring' },
    })
  })

  it('is keyed on the deck row card_id, and an empty deck is a no-op', () => {
    seedCardSummaries([])

    expect(useCardStore.getState().cards).toEqual({})
  })

  it('keeps a summary seeded WHILE the read was in flight when that read then REFUSES', async () => {
    // The ordering c4-2 actually produces: a hover starts a hydration on an unseeded id, the
    // deck fetch lands mid-flight and seeds the name, the read then settles as a 503. The
    // settled entry must carry the seeded summary, not the null captured before the request —
    // a tile that became drawable must not go blank because a refusal settled second.
    const pendingRead = deferredReader()
    const settled = hydrateCard(SOL_RING, pendingRead.read)

    seedCardSummaries([deckCard(SOL_RING, 'Sol Ring')])

    pendingRead.settle({ kind: 'error', reason: 'database_unavailable' })
    await settled

    expect(entryOf(SOL_RING)).toMatchObject({
      status: 'unknown',
      summary: { name: 'Sol Ring' },
    })
  })
})

// ===================== AC 7, AC 8, AC 10: the deduping ==================================

describe('two simultaneous reads of one id make ONE request (AC 7)', () => {
  it('shares the in-flight promise and gives both callers its result', async () => {
    const pendingRead = deferredReader()

    const first = hydrateCard(SOL_RING, pendingRead.read)
    const second = hydrateCard(SOL_RING, pendingRead.read)

    expect(pendingRead.read).toHaveBeenCalledTimes(1)
    pendingRead.settle({ kind: 'card', card: fullCard(SOL_RING, 'Sol Ring') })

    const [a, b] = await Promise.all([first, second])
    // The PROMISE is shared, not the result copied — so both callers hold the same object.
    expect(a).toBe(b)
    expect(a.status).toBe('hydrated')
  })

  it('still makes TWO requests for two DIFFERENT ids — the non-vacuity half', () => {
    const pendingRead = deferredReader()

    void hydrateCard(SOL_RING, pendingRead.read)
    void hydrateCard(ARCANE_SIGNET, pendingRead.read)

    expect(pendingRead.read).toHaveBeenCalledTimes(2)
    expect(pendingRead.calls).toEqual([SOL_RING, ARCANE_SIGNET])
    pendingRead.settle({ kind: 'unreachable' })
  })

  it('dedupes N mounted consumers, not just two (AD-12s 100-tile hover case)', async () => {
    const pendingRead = deferredReader()

    const callers = Array.from({ length: 50 }, () => hydrateCard(SOL_RING, pendingRead.read))

    expect(pendingRead.read).toHaveBeenCalledTimes(1)
    pendingRead.settle({ kind: 'card', card: fullCard(SOL_RING, 'Sol Ring') })
    const results = await Promise.all(callers)
    expect(new Set(results).size).toBe(1)
  })
})

describe('an already-hydrated id is never re-requested (AC 8)', () => {
  it('makes no request at all on the second read', async () => {
    const reader = hydratingReader()

    await hydrateCard(SOL_RING, reader.read)
    await hydrateCard(SOL_RING, reader.read)
    await hydrateCard(SOL_RING, reader.read)

    expect(reader.read).toHaveBeenCalledTimes(1)
  })
})

describe('the in-flight entry is released on EVERY outcome (AC 10)', () => {
  // A permanently-pending entry is invisible to a success-path test and turns one bad request
  // into an id that can never be read again: the next caller joins a promise that already
  // settled, so no further request is ever made. Proved on all three outcomes.
  it('releases after a SUCCESS', async () => {
    const first = deferredReader()
    const settled = hydrateCard(SOL_RING, first.read)
    first.settle({ kind: 'card', card: fullCard(SOL_RING, 'Sol Ring') })
    await settled

    // Falsifiable on the SAME id, which is the only id a per-id map can leak against: drop the
    // hydrated entry so the early-return cannot mask a leak, then read again. A leaked in-flight
    // entry would be JOINED — a settled promise, no new request — so the reader being reached a
    // second time is the release, observed. (A different-id probe cannot fail here: one id's
    // leak never blocks another's.)
    useCardStore.setState(INITIAL_CARD_CACHE, true)
    const second = deferredReader()
    void hydrateCard(SOL_RING, second.read)
    expect(second.read).toHaveBeenCalledTimes(1)
    second.settle({ kind: 'card', card: fullCard(SOL_RING, 'Sol Ring') })
    await Promise.resolve()
  })

  it('releases after a REFUSAL — a second read really does reach the reader again', async () => {
    const reader = readerAnswering({ kind: 'error', reason: 'database_unavailable' })

    await hydrateCard(SOL_RING, reader.read)
    await hydrateCard(SOL_RING, reader.read)

    // Two requests, which is only possible if the first in-flight entry was released.
    expect(reader.read).toHaveBeenCalledTimes(2)
  })

  it('releases after a REJECTION — an injected reader that throws is not a wedge', async () => {
    const throwing = vi.fn((): Promise<CardOutcome> => Promise.reject(new Error('reader blew up')))

    // The call itself must not reject: `hydrateCard`'s contract is total.
    await expect(hydrateCard(SOL_RING, throwing)).resolves.toMatchObject({ status: 'unknown' })
    await hydrateCard(SOL_RING, throwing)

    expect(throwing).toHaveBeenCalledTimes(2)
  })

  it('releases after a rejection RAISED FROM AN OPEN PROMISE, not just a sync throw', async () => {
    const pendingRead = deferredReader()
    const first = hydrateCard(SOL_RING, pendingRead.read)
    pendingRead.fail(new TypeError('Failed to fetch'))
    await first

    const again = readerAnswering({ kind: 'unreachable' })
    await hydrateCard(SOL_RING, again.read)

    expect(again.read).toHaveBeenCalledTimes(1)
  })
})

// ===================== AC 9: the measured sweep =========================================

describe('the 100-tile sweep, measured rather than asserted (AC 9)', () => {
  it('fetches each of 99 distinct ids AT MOST ONCE across TWO full sweeps', async () => {
    // 99, because that is the number of distinct tiles in the largest real deck on this machine
    // ("Atraxa Counter Cabinet v2 (owned)", measured at `61a787a`: 99 distinct ids, 100 total
    // quantity). The epic's "100-tile grid" is not a round figure someone invented.
    const deck = Array.from({ length: 99 }, (_, i) => deckCard(idAt(i + 1000), `Card ${i}`))
    const reader = hydratingReader()

    seedCardSummaries(deck)

    for (let sweep = 0; sweep < 2; sweep += 1) {
      for (const card of deck) {
        await hydrateCard(card.card_id, reader.read)
      }
    }

    expect(reader.calls).toHaveLength(99)
    expect(new Set(reader.calls).size).toBe(99)
    const perId = new Map<string, number>()
    for (const id of reader.calls) perId.set(id, (perId.get(id) ?? 0) + 1)
    expect(Math.max(...perId.values())).toBe(1)
  })

  it('holds when the cursor sweeps CONCURRENTLY, which is what a real hover does', async () => {
    const deck = Array.from({ length: 99 }, (_, i) => deckCard(idAt(i + 2000), `Card ${i}`))
    const reader = hydratingReader()
    seedCardSummaries(deck)

    // Two overlapping sweeps launched without awaiting — the shape a cursor crossing a grid
    // twice actually produces, and the one a sequential loop would never exercise.
    await Promise.all([
      ...deck.map((card) => hydrateCard(card.card_id, reader.read)),
      ...deck.map((card) => hydrateCard(card.card_id, reader.read)),
    ])

    expect(reader.calls).toHaveLength(99)
  })
})

// ===================== AC 11, AC 12: refusals and the bound =============================

describe('a 404 marks the id unknown and is remembered (AC 11, Q4)', () => {
  it('records the token and the unknown-card placeholder', async () => {
    const reader = readerAnswering({ kind: 'error', reason: 'card_not_found' })

    await hydrateCard(SOL_RING, reader.read)

    expect(entryOf(SOL_RING)).toMatchObject({
      status: 'unknown',
      reason: 'card_not_found',
      placeholder: 'unknown-card',
      retryable: false,
    })
  })

  it('is NOT re-requested on every render — a hundred reads cost one request', async () => {
    const reader = readerAnswering({ kind: 'error', reason: 'card_not_found' })

    for (let render = 0; render < 100; render += 1) {
      await hydrateCard(SOL_RING, reader.read)
    }

    // Forever, for the life of the tab (Q4). A card row is immutable between database refreshes
    // and a refresh is a restart-scale event; measured today, 0 of 2,027 deck rows dangle, so the
    // population a TTL would help is empty.
    expect(reader.read).toHaveBeenCalledTimes(1)
  })
})

describe('a per-id read has a bound on attempts, and it is not the token (AC 12)', () => {
  it('terminates for an id that answers 503 FOREVER', async () => {
    // THE TRAP, and the reason this AC exists. A malformed id sent to a backend with no database
    // answers `database_not_initialized` — a token `RETRIES_QUIETLY` says to retry quietly — and
    // the request can never succeed (measured at c3-2, pinned in `test_routes_cards.py`). A loop
    // keyed on the token alone runs forever.
    const reader = readerAnswering({ kind: 'error', reason: 'database_not_initialized' })

    for (let render = 0; render < 500; render += 1) {
      await hydrateCard(SOL_RING, reader.read)
    }

    expect(reader.read).toHaveBeenCalledTimes(MAX_ATTEMPTS_PER_CARD)
    expect(entryOf(SOL_RING)).toMatchObject({ retryable: false })
  })

  // Typed on `it.each` rather than with a cast per row: an untyped array widens `kind` to
  // `string`, which `vitest run` never notices (the table is data) and `npx tsc -b --force`
  // rejects at the call site. That asymmetry is the c3-2 ledger entry homed on this story,
  // arriving from the other direction — see the story record.
  it.each<[string, CardOutcome]>([
    ['database_unavailable', { kind: 'error', reason: 'database_unavailable' }],
    ['a network rejection', { kind: 'unreachable' }],
    ['an unreadable body', { kind: 'error', reason: null }],
    ['an unknown token', { kind: 'error', reason: 'quantum_flux' }],
  ])('terminates for %s too', async (_label, outcome) => {
    const reader = readerAnswering(outcome)

    for (let render = 0; render < 50; render += 1) {
      await hydrateCard(SOL_RING, reader.read)
    }

    expect(reader.read).toHaveBeenCalledTimes(MAX_ATTEMPTS_PER_CARD)
  })

  it('lets a transient refusal RECOVER inside the bound — the non-vacuity half', async () => {
    // A bound that terminated on the first refusal would pass every test above and break the one
    // case the retry exists for: an import that finishes between two hovers.
    let answered = 0
    const read = vi.fn((id: string): Promise<CardOutcome> => {
      answered += 1
      return Promise.resolve(
        answered === 1
          ? { kind: 'error', reason: 'database_not_initialized' }
          : { kind: 'card', card: fullCard(id, 'Sol Ring') },
      )
    })

    await hydrateCard(SOL_RING, read)
    expect(entryOf(SOL_RING)).toMatchObject({ status: 'unknown', retryable: true })

    await hydrateCard(SOL_RING, read)
    expect(entryOf(SOL_RING)?.status).toBe('hydrated')
    expect(read).toHaveBeenCalledTimes(2)
  })

  it('bounds each id SEPARATELY, so one bad id does not starve the deck', async () => {
    const refusing = readerAnswering({ kind: 'error', reason: 'database_unavailable' })
    for (let render = 0; render < 10; render += 1) {
      await hydrateCard(SOL_RING, refusing.read)
    }

    const reader = hydratingReader()
    await hydrateCard(ARCANE_SIGNET, reader.read)

    expect(entryOf(ARCANE_SIGNET)?.status).toBe('hydrated')
  })

  it('spends an attempt on a read that is still in flight, so a wedge cannot un-spend it', () => {
    // Counted before the request rather than after: a backend that accepts the connection and
    // never answers must still cost an attempt, or the bound is not a bound.
    const pendingRead = deferredReader()
    void hydrateCard(SOL_RING, pendingRead.read)

    expect(pendingRead.read).toHaveBeenCalledTimes(1)
    pendingRead.settle({ kind: 'unreachable' })
  })

  it('holds no timer — the loop AC 12 bounds is the CALLER’s, not an internal schedule', async () => {
    const timeout = vi.spyOn(globalThis, 'setTimeout')
    const reader = readerAnswering({ kind: 'error', reason: 'database_unavailable' })

    for (let render = 0; render < 10; render += 1) {
      await hydrateCard(SOL_RING, reader.read)
    }

    // Q6: this story does not copy `poller.ts`'s backoff, and it never will — **c5-6 ruled the
    // damping question NO DAMPING (Q4) and closed dw:3526**, on the ground that the socket loop
    // has one failure kind and supplies the recovery signal that made the question matter. What
    // c5-6 added instead is `resetCardAttempts`, tested below: a budget, not a schedule.
    expect(timeout).not.toHaveBeenCalled()
    timeout.mockRestore()
  })
})

// ===================== AC 13, AC 14, AC 15: the FR-13 posture ===========================

describe('a card refusal NEVER puts a state panel on the glass (AC 13)', () => {
  it('leaves the system panel exactly where it was after a card_not_found', async () => {
    useSystemStore.setState({ panel: 'no-active-deck', decks: ['Atraxa Counter Cabinet v2'] })
    const before = useSystemStore.getState()
    const reader = readerAnswering({ kind: 'error', reason: 'card_not_found' })

    await hydrateCard(SOL_RING, reader.read)

    // `panelFor(null)` clamps to `'internal-error'`, so routing a card refusal through it would
    // replace a working deck view with "The companion hit a bug" because ONE card was missing.
    // That is the FR-13 failure `states.ts:98-104` names outright ("No banner, no apology").
    expect(useSystemStore.getState()).toBe(before)
    expect(useSystemStore.getState().panel).toBe('no-active-deck')
  })

  it.each([
    'card_not_found',
    'invalid_request',
    'internal_error',
    'database_not_initialized',
    'database_unavailable',
    'payload_too_large',
  ])('leaves it untouched for %s as well', async (reason) => {
    useSystemStore.setState({ panel: 'no-active-deck', decks: [] })
    const reader = readerAnswering({ kind: 'error', reason })

    await hydrateCard(SOL_RING, reader.read)

    expect(useSystemStore.getState().panel).toBe('no-active-deck')
  })

  it('does not put an internal-error panel up for an UNREACHABLE card read either', async () => {
    useSystemStore.setState({ panel: 'no-active-deck', decks: [] })

    await hydrateCard(SOL_RING, readerAnswering({ kind: 'unreachable' }).read)

    expect(useSystemStore.getState().panel).toBe('no-active-deck')
  })
})

describe('the token reaches the consumer intact, in states.ts vocabulary (AC 14)', () => {
  it('records WHICH reason refused the id', async () => {
    await hydrateCard(SOL_RING, readerAnswering({ kind: 'error', reason: 'internal_error' }).read)

    expect(entryOf(SOL_RING)).toMatchObject({ reason: 'internal_error', placeholder: null })
  })

  it('clamps a token this build does not know to null rather than widening the type', async () => {
    await hydrateCard(SOL_RING, readerAnswering({ kind: 'error', reason: 'quantum_flux' }).read)

    // Not carried on as a bare string: everything downstream switches on `ErrorReason`, and a
    // widened `string` would push that decision into every consumer.
    expect(entryOf(SOL_RING)).toMatchObject({ reason: null, placeholder: null })
  })

  it('gives a 503 NO placeholder — "unknown card" would be a lie the summary can disprove', async () => {
    seedCardSummaries([deckCard(SOL_RING, 'Sol Ring')])

    await hydrateCard(
      SOL_RING,
      readerAnswering({ kind: 'error', reason: 'database_unavailable' }).read,
    )

    expect(entryOf(SOL_RING)).toMatchObject({
      placeholder: null,
      summary: { name: 'Sol Ring' },
    })
  })

  it('never produces an IMAGE placeholder — those tokens are not on this route (AC 14)', async () => {
    // `no_image_data` and `image_fetch_failed` map to `named-card` in `PLACEHOLDER_FOR_REASON`,
    // and they are image tokens: `GET /api/cards/{card_id}` publishes `card_not_found` plus the
    // app-wide set and neither of them. Asserted as behaviour in case one ever arrives anyway.
    for (const reason of ['no_image_data', 'image_fetch_failed']) {
      resetCardCache()
      await hydrateCard(SOL_RING, readerAnswering({ kind: 'error', reason }).read)
      expect(entryOf(SOL_RING)).toMatchObject({ reason, placeholder: null })
    }
  })
})

describe('a 400 on a card read IS the unknown-card case (AC 15, Q5)', () => {
  it('draws the placeholder rather than nothing at all', async () => {
    // `states.ts` classifies `invalid_request` as NO UI RESPONSE on the premise that "the SPA
    // never generates a malformed request" — and that premise is exactly what fails here: the id
    // came from `deck_cards`, which carries no shape constraint. One character of difference
    // would otherwise decide between a placeholder and a silently empty slot.
    const reader = readerAnswering({ kind: 'error', reason: 'invalid_request' })

    await hydrateCard(SOL_RING, reader.read)

    expect(entryOf(SOL_RING)).toMatchObject({
      status: 'unknown',
      reason: 'invalid_request',
      placeholder: 'unknown-card',
      retryable: false,
    })
  })

  it('costs exactly one request, because a malformed id stays malformed', async () => {
    const reader = readerAnswering({ kind: 'error', reason: 'invalid_request' })

    for (let render = 0; render < 20; render += 1) {
      await hydrateCard(SOL_RING, reader.read)
    }

    expect(reader.read).toHaveBeenCalledTimes(1)
  })

  it('refuses the EMPTY id with ZERO requests — /api/cards/ is a different route', async () => {
    // `cardPath('')` is the bare collection path: there is no segment for `encodeURIComponent`
    // to keep singular, so the uuid gate that answers every other hostile id never sees this
    // one. Refused in `hydrateCard` itself, before any request, terminally.
    const reader = hydratingReader()

    const entry = await hydrateCard('', reader.read)

    expect(reader.read).not.toHaveBeenCalled()
    expect(entry).toMatchObject({
      status: 'unknown',
      reason: null,
      placeholder: 'unknown-card',
      retryable: false,
    })

    await hydrateCard('', reader.read)
    expect(reader.read).not.toHaveBeenCalled()
  })
})

// ===================== the reset boundary and the production seam =======================

describe('a read that outlives resetCardCache is an orphan, not a resurrection', () => {
  it('writes NOTHING into the fresh store when it settles after a reset', async () => {
    // `resetCardCache` clears the maps but cannot cancel a running continuation. Without the
    // generation check, the orphan's `put()` would land its entry in the NEXT world — cross-test
    // contamination today, and a real bug the moment reset is reused for a deck switch.
    const pendingRead = deferredReader()
    const orphan = hydrateCard(SOL_RING, pendingRead.read)

    resetCardCache()

    pendingRead.settle({ kind: 'card', card: fullCard(SOL_RING, 'Sol Ring') })
    await orphan

    expect(entryOf(SOL_RING)).toBeUndefined()
  })

  it('cannot release a NEWER in-flight read for the same id when it settles', async () => {
    const before = deferredReader()
    const orphan = hydrateCard(SOL_RING, before.read)
    resetCardCache()

    const after = deferredReader()
    const fresh = hydrateCard(SOL_RING, after.read)
    before.settle({ kind: 'error', reason: 'card_not_found' })
    await orphan

    // The newer read must still be joinable — the orphan's `finally` must not have deleted it
    // from the in-flight map (the delete is identity-checked, and this is the probe).
    void hydrateCard(SOL_RING, after.read)
    expect(after.read).toHaveBeenCalledTimes(1)

    after.settle({ kind: 'card', card: fullCard(SOL_RING, 'Sol Ring') })
    await fresh
    expect(entryOf(SOL_RING)?.status).toBe('hydrated')
  })
})

describe('the DEFAULT reader is the real network door', () => {
  it('reaches fetch at /api/cards/{id} when no reader is injected', async () => {
    // Every other test injects a reader, so nothing else proves the `= readCard` default is
    // wired at all — a typo there would pass 60 injected-reader tests and fail in production.
    // One stubbed-global test covers the seam the whole cache stands on.
    const fetchMock = vi.fn<typeof fetch>(() =>
      Promise.resolve(
        new Response(JSON.stringify(fullCard(SOL_RING, 'Sol Ring')), { status: 200 }),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    await hydrateCard(SOL_RING)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/cards/${SOL_RING}`)
    expect(entryOf(SOL_RING)?.status).toBe('hydrated')
  })
})

/**
 * The attempt budget comes back on a reconnect; the knowledge does not go away
 * (story c5-6, Q6, AC 16 — closing `deferred-work.md:3652-3671`).
 *
 * The asymmetry the ledger recorded: three transient failures make a card id terminal **for the
 * life of the tab**, while the poll recovers, the deck boot re-drives and — as of c5-6 — the
 * socket reconnects. A backend restarted mid-sweep therefore left a deck view with permanent
 * holes that no amount of the app working correctly could fill, and the only recovery was a
 * reload — the exact defect the rest of this story exists to remove one layer up.
 */
describe('resetCardAttempts gives the budget back, and only the budget (c5-6, Q6, AC 16)', () => {
  const entry = (id: string) => useCardStore.getState().cards[id]

  const refusing = (reason: string) => () =>
    Promise.resolve({ kind: 'error', reason } as CardOutcome)

  /** Spend one id's three attempts against a token `CARD_READ_IS_RETRYABLE` says IS retryable. */
  const burn = async (id: string, reason = 'database_unavailable') => {
    for (let n = 0; n < MAX_ATTEMPTS_PER_CARD; n += 1) await hydrateCard(id, refusing(reason))
  }

  it('re-arms an id the BOUND made terminal', async () => {
    await burn(SOL_RING)
    expect(entry(SOL_RING)).toEqual(
      expect.objectContaining({
        status: 'unknown',
        reason: 'database_unavailable',
        retryable: false,
      }),
    )

    resetCardAttempts()

    expect(entry(SOL_RING)).toEqual(expect.objectContaining({ status: 'unknown', retryable: true }))
  })

  it('and the re-armed id really is asked again — the flag is not decoration', async () => {
    // Clearing the attempt MAP alone would do nothing visible, and this is where that half-repair
    // would land: `retryable` is recorded ON the entry and `hydrateCard`'s gate reads the entry,
    // not the map. Counting requests is the only assertion that can tell the two apart.
    await burn(SOL_RING)
    const { read, calls } = readerAnswering({ kind: 'error', reason: 'database_unavailable' })

    await hydrateCard(SOL_RING, read)
    expect(calls).toEqual([])

    resetCardAttempts()
    await hydrateCard(SOL_RING, read)

    expect(calls).toEqual([SOL_RING])
  })

  it('leaves an id terminal BY TOKEN exactly where it was', async () => {
    // `card_not_found` and `invalid_request` cannot succeed however many attempts they are given
    // — a card row is immutable between database refreshes, and a malformed id fails the route's
    // uuid pattern identically forever. Re-arming them would spend a request per missing card on
    // every reconnect, forever, which is a worse defect than the one being fixed.
    await hydrateCard(SOL_RING, refusing('card_not_found'))
    await hydrateCard(ARCANE_SIGNET, refusing('invalid_request'))

    resetCardAttempts()

    expect(entry(SOL_RING)).toEqual(expect.objectContaining({ retryable: false }))
    expect(entry(ARCANE_SIGNET)).toEqual(expect.objectContaining({ retryable: false }))
  })

  it('re-arms an id whose failure carried NO token at all', async () => {
    // A network rejection, an unreadable body, an unknown token: `entryFor` treats all three as
    // retryable-by-the-token, because the bound caps the cost either way and guessing "terminal"
    // would permanently un-hydrate a card because a proxy returned HTML once. This function has
    // to agree with that decision, or the two halves of one rule would disagree.
    for (let n = 0; n < MAX_ATTEMPTS_PER_CARD; n += 1) {
      await hydrateCard(SOL_RING, () => Promise.resolve({ kind: 'unreachable' }))
    }
    expect(entry(SOL_RING)).toEqual(expect.objectContaining({ retryable: false }))

    resetCardAttempts()

    expect(entry(SOL_RING)).toEqual(expect.objectContaining({ retryable: true }))
  })

  it('NEVER touches a hydrated entry — the knowledge is shared with Epic 6', async () => {
    // The reason a blanket `resetCardCache()` was the wrong repair: this cache is shared (this
    // module's own header names Epic 6's agent views as the other consumer), so discarding
    // hydration would throw away rows two decks and four future views hold in common, and buy
    // back a request per id for cards that were never broken.
    await hydrateCard(SOL_RING, () =>
      Promise.resolve({ kind: 'card', card: fullCard(SOL_RING, 'Sol Ring') }),
    )
    const before = entry(SOL_RING)

    resetCardAttempts()

    // Identity, not equality: a rewritten entry with the same contents is still a re-render.
    expect(entry(SOL_RING)).toBe(before)
    expect(entry(SOL_RING)?.status).toBe('hydrated')
  })

  it('leaves the summary tier alone as well', async () => {
    seedCardSummaries([deckCard(ARCANE_SIGNET, 'Arcane Signet')])
    // …with a burned id in the same store, so the write really does happen and this assertion is
    // about what the write SPARED rather than about a write that never occurred.
    await burn(SOL_RING)
    const before = entry(ARCANE_SIGNET)

    resetCardAttempts()

    expect(entry(ARCANE_SIGNET)).toBe(before)
  })

  it('does not write the store at all when there is nothing to give back', () => {
    // The store is read by every tile, so a no-op write on every reconnect would re-render a
    // 99-tile grid for nothing.
    const before = useCardStore.getState()

    resetCardAttempts()
    resetCardAttempts()

    expect(useCardStore.getState()).toBe(before)
  })

  it('creates no orphans — the dw:3666 declare stands unchanged', async () => {
    // `resetCardCache` bumps a generation precisely because a read in flight when the world is
    // thrown away must write nowhere. This function throws nothing away and bumps nothing, so a
    // read in flight across it settles normally — which is the DISPOSITION that ledger entry was
    // waiting for rather than a repair of it.
    let settleRead: (outcome: CardOutcome) => void = () => undefined
    const pending = hydrateCard(
      SOL_RING,
      () => new Promise<CardOutcome>((resolve) => (settleRead = resolve)),
    )

    resetCardAttempts()
    settleRead({ kind: 'card', card: fullCard(SOL_RING, 'Sol Ring') })
    await pending

    expect(entry(SOL_RING)?.status).toBe('hydrated')
  })
})
