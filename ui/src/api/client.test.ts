/**
 * The wire boundary's malformed-input half (story c3-9, AC 9, AC 10; extended by c4-1).
 *
 * Every assertion here feeds a reader something the contract does not promise and asserts it
 * came back as a VALUE rather than as a thrown exception. That matters because of where the
 * result goes: `panelFor` turns it into a `StateKey` and `StatePanel` indexes `STATE_COPY` with
 * no fallback branch, so a rejection escaping this module lands as an unhandled render exception
 * — the error screen this whole story exists to ban.
 *
 * **c4-1 renamed the module under this file (`decks.ts` → `client.ts`, Q1) and added `readCard`.**
 * The deck half below is UNCHANGED and that is deliberate: c4-1 refactored both readers onto one
 * shared `request()` helper, and a green run of assertions written before that helper existed is
 * the regression proof that the refactor changed no behaviour.
 *
 * The four AC 9 inputs are four separate `it`s on purpose: they fail in three different layers
 * (`fetch` itself, `.json()`, and the body's shape), and collapsing them would let a fix for one
 * hide a regression in another.
 *
 * jsdom, the jest-dom matchers and afterEach(cleanup) come from the `dom` vitest project; this
 * file needs none of them, but it lives beside the module it tests per AC 25b.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  CARD_PATH_PREFIX,
  DECKS_PATH,
  READ_TIMEOUT_MS,
  cardPath,
  readCard,
  readDecks,
} from './client'

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
    // safety argument evaporates the moment somebody parameterises this constant.
    //
    // **c4-1 arrived and did NOT parameterise it** — `CARD_PATH_PREFIX` is a separate constant,
    // and the assertion below is its opposite number.
    expect(DECKS_PATH).not.toMatch(/[{}:]/)
  })

  it('keeps the card route a SEPARATE constant, so the two are not confusable (c4-1 Q1)', () => {
    // The card route takes an id and is therefore NOT retry-safe on the token alone. Two
    // constants rather than one templated helper means the difference is visible at every call
    // site instead of buried in an argument.
    expect(CARD_PATH_PREFIX).not.toBe(DECKS_PATH)
    expect(CARD_PATH_PREFIX.startsWith(DECKS_PATH)).toBe(false)
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

  it('degrades to NO timeout where the API is absent — never to permanently unreachable', async () => {
    // Greptile PR #37 P2, confirmed: without the guard, `AbortSignal.timeout` throwing INSIDE
    // the try would classify every poll as `unreachable` before `fetch` ever ran — the app
    // would retry forever without contacting a healthy backend. In a runtime without the API
    // the request must still go out (with no signal), and the answer must still be read.
    const fetchMock = responding('{"reason": "database_not_initialized"}', 503)
    vi.stubGlobal('AbortSignal', {})

    await expect(readDecks()).resolves.toEqual({
      kind: 'error',
      reason: 'database_not_initialized',
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][1]?.signal).toBeUndefined()
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

// ===================== c4-1: the card read ==============================================

/** A real id from the shipped corpus, in the canonical spelling the route's pattern demands. */
const SOL_RING = '0d7ac8e1-2ea4-4b6c-9b6a-06bd4bd90ba1'

/** The two fields `cardOf` reads, plus enough to be recognisably a card. */
const solRingBody = JSON.stringify({
  id: SOL_RING,
  name: 'Sol Ring',
  mana_cost: '{1}',
  cmc: 1,
  type_line: 'Artifact',
  oracle_text: '{T}: Add {C}{C}.',
})

describe('readCard addresses one card, safely (c4-1 AC 2, AC 15)', () => {
  it('asks for /api/cards/<id>, uncached', async () => {
    const fetchMock = responding(solRingBody, 200)

    await readCard(SOL_RING)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe(`${CARD_PATH_PREFIX}${SOL_RING}`)
    // Not tidiness: the route sets NO cache headers (ledgered, c4-1 Q7), so a browser is free to
    // apply heuristic freshness and serve a row from before a database refresh. The app's own
    // cache is the caching layer; `no-store` removes the only staleness that is not ours.
    expect(fetchMock.mock.calls[0][1]?.cache).toBe('no-store')
  })

  it('carries the same abort signal the deck poll does', async () => {
    const fetchMock = responding(solRingBody, 200)

    await readCard(SOL_RING)

    expect(fetchMock.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal)
  })

  it.each([
    ['a path separator', 'a/b'],
    ['a query opener', 'a?b=c'],
    ['a fragment', 'a#b'],
    ['a parent traversal', '../health'],
    ['a whole absolute URL', 'https://evil.example/x'],
  ])('encodes %s so an id cannot change WHICH route is called', (_label, hostile) => {
    // `deck_cards.card_id` carries no shape constraint and FK enforcement is off on the async
    // engine (measured: 0 of 2,027 rows are non-canonical today, so this is latent, not live).
    // Unencoded, an id like these would address a different endpoint entirely; encoded, it stays
    // one path segment, the route's uuid pattern refuses it, and the answer is `400
    // invalid_request` — which `src/state/cards.ts` turns into the unknown-card placeholder (Q5).
    const path = cardPath(hostile)

    expect(path.startsWith(CARD_PATH_PREFIX)).toBe(true)
    expect(path.slice(CARD_PATH_PREFIX.length)).not.toMatch(/[/?#]/)
  })

  it('leaves a CANONICAL id byte-identical — the silent half', () => {
    // The encoder must not be doing anything to the 38,261 ids that are already canonical: a
    // percent-escaped hyphen would miss every card in the corpus.
    expect(cardPath(SOL_RING)).toBe(`${CARD_PATH_PREFIX}${SOL_RING}`)
  })
})

describe('a card read is a total outcome union, exactly like the deck poll (c4-1 AC 2)', () => {
  it('reads a 200 as the card', async () => {
    responding(solRingBody, 200)

    const outcome = await readCard(SOL_RING)

    expect(outcome.kind).toBe('card')
    expect(outcome).toMatchObject({ card: { id: SOL_RING, name: 'Sol Ring' } })
  })

  it.each([
    ['card_not_found', 404],
    ['invalid_request', 400],
    ['database_not_initialized', 503],
    ['database_unavailable', 503],
    ['payload_too_large', 413],
    ['internal_error', 500],
  ])('passes %s (%d) through as it crossed the wire', async (reason, status) => {
    responding(JSON.stringify({ reason }), status)

    // Unvalidated and unclamped, the same as the deck poll: deciding what a token MEANS is the
    // cache's job, and doing it in two places would mean two places to get it wrong.
    expect(await readCard(SOL_RING)).toEqual({ kind: 'error', reason })
  })

  it('reads a network rejection as unreachable, not as a refusal', async () => {
    stubFetch(() => Promise.reject(new TypeError('Failed to fetch')))

    await expect(readCard(SOL_RING)).resolves.toEqual({ kind: 'unreachable' })
  })

  it.each([
    ['no body at all', null, 503],
    ['a body that is not JSON', '<!doctype html><title>proxy error</title>', 503],
    ['a JSON body with no reason key', '{"detail": "something"}', 404],
  ])('reads %s as a refusal with no readable token', async (_label, body, status) => {
    responding(body, status)

    await expect(readCard(SOL_RING)).resolves.toEqual({ kind: 'error', reason: null })
  })

  it.each([
    ['not an object', '"Sol Ring"'],
    ['an array', '[{"id": "x", "name": "y"}]'],
    ['missing id', '{"name": "Sol Ring"}'],
    ['missing name', `{"id": "${SOL_RING}"}`],
    ['an id that is not a string', '{"id": 7, "name": "Sol Ring"}'],
    // Blank counts as absent, the same ruling `namesOf` applies to the deck list (FR-13): a
    // blank name cannot label a tile and a blank id cannot key the cache, so neither is this
    // contract whatever its field TYPES say.
    ['a name that is blank', `{"id": "${SOL_RING}", "name": "   "}`],
    ['an id that is blank', '{"id": "", "name": "Sol Ring"}'],
    ['HTML behind a 200', '<!doctype html><title>captive portal</title>'],
  ])('reports a 200 that is %s as a contract violation, not as a card', async (_label, body) => {
    responding(body, 200)

    // The alternative is worse than an error: caching a hollow object would put `undefined`
    // where a card name goes, in every consumer, silently.
    expect(await readCard(SOL_RING)).toEqual({ kind: 'error', reason: null })
  })

  it('still accepts a well-formed record — the non-vacuity half of the block above', async () => {
    responding(solRingBody, 200)

    expect((await readCard(SOL_RING)).kind).toBe('card')
  })
})

describe('readCard issues ONE request and never retries (c4-1 AC 12, AC 25)', () => {
  it('makes exactly one request for a 503 — the bound lives in the cache, not here', async () => {
    // The trap c3-9 wrote down for this story: a malformed id sent to a backend with no database
    // answers `database_not_initialized`, a token `RETRIES_QUIETLY` says to retry quietly, and
    // the request can never succeed. A retry loop HERE would be invisible to the cache that
    // counts requests, so there is none: `MAX_ATTEMPTS_PER_CARD` is the bound and it is one
    // layer up, where the decision to ask again is actually made.
    const fetchMock = responding('{"reason": "database_not_initialized"}', 503)

    await readCard(SOL_RING)

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('makes exactly one request for a network rejection too', async () => {
    const fetchMock = stubFetch(() => Promise.reject(new TypeError('Failed to fetch')))

    await readCard(SOL_RING)

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
