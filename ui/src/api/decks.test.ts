/**
 * The wire boundary's malformed-input half (story c3-9, AC 9, AC 10).
 *
 * Every assertion here feeds `readDecks` something the contract does not promise and asserts it
 * came back as a VALUE rather than as a thrown exception. That matters because of where the
 * result goes: `panelFor` turns it into a `StateKey` and `StatePanel` indexes `STATE_COPY` with
 * no fallback branch, so a rejection escaping this module lands as an unhandled render exception
 * — the error screen this whole story exists to ban.
 *
 * The four AC 9 inputs are four separate `it`s on purpose: they fail in three different layers
 * (`fetch` itself, `.json()`, and the body's shape), and collapsing them would let a fix for one
 * hide a regression in another.
 *
 * jsdom, the jest-dom matchers and afterEach(cleanup) come from the `dom` vitest project; this
 * file needs none of them, but it lives beside the module it tests per AC 25b.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import { DECKS_PATH, READ_TIMEOUT_MS, readDecks } from './decks'

// Typed as `fetch` itself, not as the zero-argument stub it happens to be: the assertions below
// read `mock.calls[0][1]`, and a mock typed from the implementation would make that index a
// compile error rather than a request-options check.
const stubFetch = (impl: () => Promise<Response>) => {
  const fetchMock = vi.fn<typeof fetch>(impl)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const responding = (body: BodyInit | null, status: number) =>
  stubFetch(() => Promise.resolve(new Response(body, { status })))

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('readDecks reads the route the artefact names', () => {
  it('asks for /api/decks, uncached, and says so', async () => {
    const fetchMock = responding('[]', 200)

    await readDecks()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe(DECKS_PATH)
    // `no-store` is load-bearing rather than tidy: the entire point of the poll is to see the
    // backend change state underneath it, and `deps.get_session` re-probes readiness on every
    // request precisely so that it can (FR-22). A cached 503 would be the one place that
    // promise could still be broken, on the client side, invisibly.
    expect(fetchMock.mock.calls[0][1]?.cache).toBe('no-store')
  })

  it('has no path parameter, which is WHY retrying it is safe (AC 10)', () => {
    // Measured at c3-2 and pinned in `test_routes_cards.py`: a malformed id sent to a backend
    // with no database answers `database_not_initialized`, NOT `invalid_request`, because
    // FastAPI solves dependencies before it collects validation errors. So a client that treats
    // both database tokens as "retry quietly" retries a request whose id can never succeed.
    //
    // This poll cannot hit that, and the reason is structural rather than careful: there is no
    // id in the path to be malformed. Asserted rather than merely written down, because the
    // safety argument evaporates the moment somebody parameterises this constant — which is
    // exactly what **c4-1** will be tempted to do when it copies this module for
    // `GET /api/cards/{card_id}`, a route where the argument does NOT hold.
    expect(DECKS_PATH).not.toMatch(/[{}:]/)
  })
})

describe('a 200 becomes deck names, and a malformed one does not become an empty list', () => {
  it('takes the names out of the promised array', async () => {
    responding(
      JSON.stringify([
        { id: 'a', name: 'Boros Aggro', main_count: 60, side_count: 15, distinct_count: 24 },
        { id: 'b', name: 'Dimir Mill', main_count: 60, side_count: 0, distinct_count: 30 },
      ]),
      200,
    )

    expect(await readDecks()).toEqual({ kind: 'decks', decks: ['Boros Aggro', 'Dimir Mill'] })
  })

  it('reads an empty array as an empty list — the ordinary fresh-install answer', async () => {
    responding('[]', 200)

    expect(await readDecks()).toEqual({ kind: 'decks', decks: [] })
  })

  it('drops a blank or missing name rather than failing the whole read', async () => {
    responding(JSON.stringify([{ name: '   ' }, { name: 'Real Deck' }, {}, null, 7]), 200)

    // FR-13's posture read across to this list: one unusable row must not take the panel down.
    expect(await readDecks()).toEqual({ kind: 'decks', decks: ['Real Deck'] })
  })

  it('reports a 200 that is not an array as a contract violation, NOT as zero decks', async () => {
    responding('{"decks": []}', 200)

    // The firing half of the pair above. Answering `{kind:'decks', decks: []}` here would put a
    // calm, wrong panel on the glass — "no decks" is a claim, and this response did not make it.
    expect(await readDecks()).toEqual({ kind: 'error', reason: null })
  })

  it('reports a 200 whose body is not JSON at all the same way', async () => {
    // The one branch combination (`response.ok && body === null`) the suite did not pin, and
    // exactly the shape a misconfigured proxy serves: a happy status wrapping an HTML page.
    responding('<!doctype html><title>captive portal</title>', 200)

    expect(await readDecks()).toEqual({ kind: 'error', reason: null })
  })
})

describe('a request cannot hang forever', () => {
  it('carries an abort signal on every request', async () => {
    // A backend that accepts the connection and never responds is the one failure `fetch` has
    // no clock on: without a signal, `await read()` never settles, the poller schedules
    // nothing, and the calm initial panel stands forever. See `READ_TIMEOUT_MS`.
    const fetchMock = responding('[]', 200)

    await readDecks()

    expect(fetchMock.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal)
  })

  it('reads a timeout abort as unreachable, like any other lost backend', async () => {
    stubFetch(() => Promise.reject(new DOMException('The operation timed out.', 'TimeoutError')))

    await expect(readDecks()).resolves.toEqual({ kind: 'unreachable' })
  })

  it('outwaits the backend busy timeout rather than racing it', () => {
    // `database.py` holds a locked read for up to 5 s (`timeout=5`) before answering; a clock
    // shorter than that would abort true answers and report a healthy backend unreachable.
    expect(READ_TIMEOUT_MS).toBeGreaterThan(5_000)
  })
})

describe('a refusal carries its token through unvalidated (AC 2)', () => {
  it.each([
    ['database_not_initialized', 503],
    ['database_unavailable', 503],
    ['internal_error', 500],
    ['invalid_request', 400],
  ])('passes %s (%d) through as it crossed the wire', async (reason, status) => {
    responding(JSON.stringify({ reason }), status)

    expect(await readDecks()).toEqual({ kind: 'error', reason })
  })

  it('passes a token this build has never heard of through UNCHANGED (AC 8)', async () => {
    // Delivered as untyped JSON, which is the only way it can arrive: `ErrorReason` is erased at
    // runtime. This module deliberately does NOT clamp — clamping is `panelFor`'s single job,
    // and doing it in two places would mean two places to get it wrong.
    responding('{"reason": "quantum_flux_capacitor_failed"}', 503)

    expect(await readDecks()).toEqual({ kind: 'error', reason: 'quantum_flux_capacitor_failed' })
  })
})

describe('the four malformed inputs of AC 9, none of which may reject', () => {
  it('a 503 with no body at all', async () => {
    responding(null, 503)

    await expect(readDecks()).resolves.toEqual({ kind: 'error', reason: null })
  })

  it('a body that is not JSON', async () => {
    responding('<!doctype html><title>proxy error</title>', 503)

    await expect(readDecks()).resolves.toEqual({ kind: 'error', reason: null })
  })

  it('a JSON body with no reason key', async () => {
    responding('{"detail": "something"}', 503)

    await expect(readDecks()).resolves.toEqual({ kind: 'error', reason: null })
  })

  it('a network rejection — distinct from all three above', async () => {
    stubFetch(() => Promise.reject(new TypeError('Failed to fetch')))

    // NOT `{kind:'error', reason:null}`. No response arrived, so no state was decided, and the
    // poller treats the two differently: see its header on why `disconnected` is c5-6's.
    await expect(readDecks()).resolves.toEqual({ kind: 'unreachable' })
  })

  it.each([
    ['a number', '{"reason": 42}'],
    ['null', '{"reason": null}'],
    ['an object', '{"reason": {"reason": "database_unavailable"}}'],
    ['an array', '{"reason": ["database_unavailable"]}'],
    ['a JSON scalar body', '"database_unavailable"'],
  ])('a reason that is %s reads as no reason', async (_label, body) => {
    responding(body, 503)

    await expect(readDecks()).resolves.toEqual({ kind: 'error', reason: null })
  })

  it('still reads a WELL-FORMED body — the non-vacuity half of every case above', async () => {
    // Five inputs in this block resolve to `reason: null`, which an implementation that always
    // returned `null` would also satisfy. This is the assertion that says the reads above are
    // reads.
    responding('{"reason": "database_unavailable"}', 503)

    await expect(readDecks()).resolves.toEqual({
      kind: 'error',
      reason: 'database_unavailable',
    })
  })
})
