/**
 * The wire boundary's malformed-input half.
 *
 * Every assertion here feeds a reader something the contract does not promise and asserts it
 * came back as a VALUE rather than as a thrown exception. That matters because of where the
 * result goes: `panelFor` turns it into a `StateKey` and `StatePanel` indexes `STATE_COPY` with
 * no fallback branch, so a rejection escaping this module lands as an unhandled render exception
 * — the error screen the readers exist to ban.
 *
 * The four malformed inputs are four separate `it`s on purpose: they fail in three different
 * layers (`fetch` itself, `.json()`, and the body's shape), and collapsing them would let a fix
 * for one hide a regression in another.
 *
 * jsdom, the jest-dom matchers and afterEach(cleanup) come from the `dom` vitest project; this
 * file needs none of them, but it lives beside the module it tests.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ACTIVE_DECK_PATH,
  CARD_PATH_PREFIX,
  DECKS_PATH,
  DECK_PATH_PREFIX,
  FORMAT_CHECK_PATH_SUFFIX,
  HEALTH_PATH,
  READ_TIMEOUT_MS,
  SESSION_PATH,
  WS_PATH,
  agentEventOf,
  agentSocketUrl,
  cardPath,
  deckPath,
  formatCheckPath,
  openAgentSocket,
  readActiveDeck,
  readCard,
  readDeck,
  readDecks,
  readFormatCheck,
  readInstanceId,
  readSessionTicket,
  type AgentSocketHandlers,
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
    // `CARD_PATH_PREFIX` is a separate constant, and the assertion below is its opposite number.
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
    // Without the guard, `AbortSignal.timeout` throwing INSIDE
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
    // poller treats the two differently: the `disconnected` panel is decided from the SOCKET's
    // threshold rather than from this reader, so an `unreachable` here decides nothing, which is
    // what lets the two compose.
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

// ===================== the card read ====================================================

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
    // Not tidiness: the route sets NO cache headers, so a browser is free to
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
    // invalid_request` — which `src/state/cards.ts` turns into the unknown-card placeholder.
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
    // Blank counts as absent, the same rule `namesOf` applies to the deck list (FR-13): a
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
    // The trap: a malformed id sent to a backend with no database
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

// ===================== the two boot reads ===============================================

/** A real deck: "Atraxa Counter Cabinet v2 (owned)", 99 distinct cards, 100 total. */
const ATRAXA_DECK_ID = '813d0434-1bed-4419-bf9d-d9e4070704c4'

/** The three fields `deckOf` reads, plus enough to be recognisably a deck. */
const deckBody = (overrides: Record<string, unknown> = {}) =>
  JSON.stringify({
    id: ATRAXA_DECK_ID,
    name: 'Atraxa Counter Cabinet v2 (owned)',
    format: 'brawl',
    strategy: null,
    color_identity: ['W', 'U', 'B', 'G'],
    tags: [],
    mainboard_count: 100,
    sideboard_count: 0,
    distinct_cards: 99,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-08-01T00:00:00Z',
    cards: [],
    ...overrides,
  })

describe('the two boot routes are addressed correctly (AC 2, AC 3)', () => {
  it('asks for /api/active-deck, uncached, with no path parameter to be malformed', async () => {
    const fetchMock = responding('{"deck_id": null}', 200)

    await readActiveDeck()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe(ACTIVE_DECK_PATH)
    expect(fetchMock.mock.calls[0][1]?.cache).toBe('no-store')
    expect(ACTIVE_DECK_PATH).not.toMatch(/[{}:]/)
  })

  it('asks for /api/deck/<id>, uncached', async () => {
    const fetchMock = responding(deckBody(), 200)

    await readDeck(ATRAXA_DECK_ID)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe(`${DECK_PATH_PREFIX}${ATRAXA_DECK_ID}`)
    expect(fetchMock.mock.calls[0][1]?.cache).toBe('no-store')
  })

  it('keeps the deck route a SEPARATE constant that visibly DOES take an id', () => {
    // The opposite number of the `DECKS_PATH` assertion above, and the reason the retry argument
    // does not transfer between them: this one carries a path parameter, so a `503` it sees may
    // be masking a `400` about an id that can never succeed (the measurement in `client.ts`'s
    // header).
    expect(DECK_PATH_PREFIX).not.toBe(DECKS_PATH)
    expect(DECK_PATH_PREFIX).not.toBe(CARD_PATH_PREFIX)
    // …and `/api/decks` is not a prefix of `/api/deck/`, so the two cannot be confused by a
    // startsWith check anywhere downstream.
    expect(DECK_PATH_PREFIX.startsWith(DECKS_PATH)).toBe(false)
  })

  it.each([
    ['a slash', 'a/b'],
    ['a query marker', 'a?b'],
    ['a fragment marker', 'a#b'],
    ['a traversal', '../decks'],
    ['a space', 'my deck'],
    ['a percent', '100%'],
  ])('encodes %s so the id stays ONE path segment (AC 3)', (_label, deckId) => {
    const path = deckPath(deckId)

    expect(path.startsWith(DECK_PATH_PREFIX)).toBe(true)
    // The id contributes no separator of its own: everything after the prefix is one segment.
    expect(path.slice(DECK_PATH_PREFIX.length)).not.toMatch(/[/?#]/)
    expect(path).toBe(`${DECK_PATH_PREFIX}${encodeURIComponent(deckId)}`)
  })

  it('is the encoding of a REAL threat, not a defensive habit', () => {
    // `ActiveDeckRequest` stores any non-blank string up to 256 chars VERBATIM and deliberately
    // does not check that the deck exists — so a traversal id is one agent typo away, and raw
    // interpolation would address `/api/decks` and render its answer as this deck.
    expect(deckPath('../decks')).not.toContain('/api/decks')
  })
})

describe('a 200 from /api/active-deck: null is an ANSWER, not an absence (AC 1)', () => {
  it('reads a real id', async () => {
    responding(`{"deck_id": "${ATRAXA_DECK_ID}"}`, 200)

    expect(await readActiveDeck()).toEqual({ kind: 'active-deck', deckId: ATRAXA_DECK_ID })
  })

  it('reads null as no active deck — the ordinary post-restart cold open (FR-07)', async () => {
    responding('{"deck_id": null}', 200)

    // NOT `{kind:'error'}`. The slot lives in the backend's memory and dies with the process, so
    // this is the most common answer there is on a fresh backend.
    expect(await readActiveDeck()).toEqual({ kind: 'active-deck', deckId: null })
  })

  it.each([
    ['blank', '{"deck_id": "   "}'],
    ['empty', '{"deck_id": ""}'],
  ])(
    'folds a %s id to no active deck rather than to a request for /api/deck/',
    async (_l, body) => {
      // `deckPath('')` is the bare collection path — a DIFFERENT route, not a malformed parameter.
      // `ActiveDeckRequest` refuses blanks on the way in, so this can only be a non-contract body.
      responding(body, 200)

      expect(await readActiveDeck()).toEqual({ kind: 'active-deck', deckId: null })
    },
  )

  it.each([
    ['no deck_id key', '{"deck": "x"}'],
    ['a number', '{"deck_id": 42}'],
    ['an array body', '[]'],
    ['a scalar body', '"nope"'],
    ['not JSON at all', '<!doctype html><title>captive portal</title>'],
  ])('reports %s as a contract violation, distinct from null', async (_label, body) => {
    responding(body, 200)

    expect(await readActiveDeck()).toEqual({ kind: 'error', reason: null })
  })
})

describe('a 200 from /api/deck/<id>: three fields, and cards is one of them', () => {
  it('returns the promised record', async () => {
    responding(deckBody(), 200)

    const outcome = await readDeck(ATRAXA_DECK_ID)

    expect(outcome.kind).toBe('deck')
    expect(outcome.kind === 'deck' && outcome.deck.name).toBe('Atraxa Counter Cabinet v2 (owned)')
  })

  it.each([
    ['a blank name', deckBody({ name: '   ' })],
    ['a missing id', deckBody({ id: undefined })],
    ['a numeric name', deckBody({ name: 7 })],
    ['a scalar body', '"deck"'],
    ['a body that is not JSON', '<!doctype html><title>proxy</title>'],
  ])('reports %s as a contract violation', async (_label, body) => {
    responding(body, 200)

    expect(await readDeck(ATRAXA_DECK_ID)).toEqual({ kind: 'error', reason: null })
  })

  it('reports a MISSING cards array as a violation, not as an empty deck', async () => {
    // The third field, and the reason it is checked where `cardOf` checks only two: `cards` is
    // the whole product of this read. Answering "a deck with no cards" would put a calm,
    // confidently-empty decklist on the glass — the failure `namesOf` refuses for the poll.
    responding(deckBody({ cards: undefined }), 200)

    expect(await readDeck(ATRAXA_DECK_ID)).toEqual({ kind: 'error', reason: null })
  })

  it('still accepts a GENUINELY empty deck — the non-vacuity half (c4-12)', async () => {
    responding(deckBody({ cards: [], mainboard_count: 0 }), 200)

    const outcome = await readDeck(ATRAXA_DECK_ID)

    expect(outcome.kind).toBe('deck')
    expect(outcome.kind === 'deck' && outcome.deck.cards).toEqual([])
  })
})

describe('the two routes refuse in DIFFERENT vocabularies, and both stay values', () => {
  it.each([
    ['invalid_request', 400],
    ['internal_error', 500],
  ])('passes %s (%d) from the active-deck route through unvalidated', async (reason, status) => {
    responding(JSON.stringify({ reason }), status)

    expect(await readActiveDeck()).toEqual({ kind: 'error', reason })
  })

  it.each([
    ['deck_not_found', 404],
    ['database_not_initialized', 503],
    ['database_unavailable', 503],
    // `404`, not `400`, and it is MEASURED against the running backend rather than assumed: an
    // id that fails the route's uuid pattern answers `404 invalid_request`. The status and the
    // token disagree about what happened, which is precisely why AD-16 says nothing may key off
    // the status — a client reading `404` here would call a malformed id "deck not found".
    ['invalid_request', 404],
    ['payload_too_large', 413],
    ['internal_error', 500],
  ])('passes %s (%d) from the deck route through unvalidated', async (reason, status) => {
    responding(JSON.stringify({ reason }), status)

    expect(await readDeck(ATRAXA_DECK_ID)).toEqual({ kind: 'error', reason })
  })

  it('never rejects, on any of the four malformed inputs, for either reader', async () => {
    for (const body of [null, '<!doctype html>', '{"detail": "x"}', '{"reason": 42}']) {
      responding(body, 503)
      await expect(readActiveDeck()).resolves.toEqual({ kind: 'error', reason: null })
      responding(body, 503)
      await expect(readDeck(ATRAXA_DECK_ID)).resolves.toEqual({ kind: 'error', reason: null })
    }

    stubFetch(() => Promise.reject(new TypeError('Failed to fetch')))
    await expect(readActiveDeck()).resolves.toEqual({ kind: 'unreachable' })
    await expect(readDeck(ATRAXA_DECK_ID)).resolves.toEqual({ kind: 'unreachable' })
  })

  it('carries the shared abort signal on both, rather than a second copy of the clock', async () => {
    // The point of both readers going through the private `request()` helper: one timeout guard,
    // one `no-store`, one place to get either wrong.
    const fetchMock = responding('{"deck_id": null}', 200)
    await readActiveDeck()
    expect(fetchMock.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal)

    const deckMock = responding(deckBody(), 200)
    await readDeck(ATRAXA_DECK_ID)
    expect(deckMock.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal)
  })
})

/**
 * The caller-signal merge: a superseded refetch aborts its OWN request.
 *
 * These assertions observe the wire directly: reverting `request()`'s merge to timeout-only —
 * dropping the caller's signal on the floor — would leave everything upstream green, because
 * `deck.ts`'s abort-on-supersede is proven against INJECTED readers. The fetch stubs here react
 * to their signal the way the real `fetch` does — reject with an `AbortError` on abort,
 * immediately when the signal arrives already aborted — because the property under test is
 * exactly that the abort REACHES the wire.
 */
describe('a caller can abandon a deck read mid-flight (c7-3)', () => {
  /** A fetch that never answers on its own and honours its signal exactly as the real one does. */
  const hangingFetch = () => {
    const fetchMock = vi.fn<typeof fetch>(
      (_input, init) =>
        new Promise<Response>((_resolve, reject) => {
          const refuse = () => reject(new DOMException('The operation was aborted.', 'AbortError'))
          if (init?.signal?.aborted) {
            refuse()
            return
          }
          init?.signal?.addEventListener('abort', refuse)
        }),
    )
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('merges the caller signal into the request: an abort reaches fetch and reads unreachable', async () => {
    const fetchMock = hangingFetch()
    const controller = new AbortController()

    const pending = readDeck(ATRAXA_DECK_ID, controller.signal)
    controller.abort()

    // The reader settles NOW, off the abort — no response is coming, so a resolution at all is
    // proof the caller's handle reached the wire. An abort is a discarded outcome, never a
    // throw: the reader stays total and the caller's generation guard is what tells it apart.
    await expect(pending).resolves.toEqual({ kind: 'unreachable' })
    expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(true)
  })

  it('still merges where AbortSignal.any is absent — the manual fallback, caller side', async () => {
    // The floor-miss precedent above removes the WHOLE AbortSignal API; this stub removes only
    // `any`, which is the exact gap the fallback exists for: `any` postdates `timeout` in
    // browsers (Chrome 116 / Firefox 124 / Safari 17.4 against 103/100/15.4), so a browser
    // inside the bundle's floor can hold the clock and still lack the merge. Without the
    // fallback this run would be dead code in every test — node 24 and jsdom 29 both ship
    // `any`.
    const timeout = AbortSignal.timeout.bind(AbortSignal)
    vi.stubGlobal('AbortSignal', { timeout })
    const fetchMock = hangingFetch()
    const controller = new AbortController()

    const pending = readDeck(ATRAXA_DECK_ID, controller.signal)
    controller.abort()

    await expect(pending).resolves.toEqual({ kind: 'unreachable' })
    expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(true)
  })

  it('propagates the TIMEOUT input through the manual fallback too — either side aborts', async () => {
    // The other input of the merge, driven by handing `request()` a controllable "timeout": the
    // clock firing must end the request even when the caller's signal stays quiet, or the
    // fallback would have silently traded the wedge guard for the abort feature.
    const clock = new AbortController()
    vi.stubGlobal('AbortSignal', { timeout: () => clock.signal })
    const fetchMock = hangingFetch()
    const caller = new AbortController()

    const pending = readDeck(ATRAXA_DECK_ID, caller.signal)
    clock.abort()

    await expect(pending).resolves.toEqual({ kind: 'unreachable' })
    expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(true)
    expect(caller.signal.aborted).toBe(false)
  })

  it('honours a caller signal ALREADY aborted at merge time (fallback arm)', async () => {
    // The `signal.aborted` branch of the manual merge's `follow`: an `addEventListener`-only
    // fallback would wait forever on an event that already fired — a supersession landing in
    // the same tick as the read it kills is exactly how `deck.ts` uses this.
    const timeout = AbortSignal.timeout.bind(AbortSignal)
    vi.stubGlobal('AbortSignal', { timeout })
    const fetchMock = hangingFetch()
    const controller = new AbortController()
    controller.abort()

    await expect(readDeck(ATRAXA_DECK_ID, controller.signal)).resolves.toEqual({
      kind: 'unreachable',
    })
    expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(true)
  })
})

describe('neither boot reader retries (AC 12, Q6)', () => {
  it.each([
    ['a 503 on the deck read', () => responding('{"reason": "database_not_initialized"}', 503)],
    ['a network rejection', () => stubFetch(() => Promise.reject(new TypeError('nope')))],
  ])('makes exactly ONE request for %s', async (_label, arrange) => {
    // The header's trap applies to `/api/deck/{deck_id}` exactly as it does to `/api/cards/{card_id}`:
    // a backend with no database answers `database_not_initialized` to an id that could never
    // succeed. `readCard` needed `MAX_ATTEMPTS_PER_CARD` because RENDERS call it in a loop.
    // Nothing loops here — so the bound is replaced by there being no "again" at all.
    const fetchMock = arrange()

    await readDeck(ATRAXA_DECK_ID)

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('makes exactly ONE request from the active-deck reader too', async () => {
    const fetchMock = responding('{"reason": "internal_error"}', 500)

    await readActiveDeck()

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

// ===================== the format check =================================================

/**
 * A REAL report, copied out of the running backend rather than composed: this is
 * `GET /api/deck/{id}/format-check` for a real all-pass Standard deck, verbatim — six rows in
 * `CHECK_ORDER`, five passes and the permanent rotation advisory. Nothing here is invented.
 */
const formatCheckBody = (overrides: Record<string, unknown> = {}) =>
  JSON.stringify({
    is_legal: true,
    format: 'standard',
    format_recognized: true,
    mainboard_count: 60,
    sideboard_count: 0,
    rows: [
      { check: 'legality', status: 'pass', detail: 'Every card is legal in standard.' },
      { check: 'size', status: 'pass', detail: 'Mainboard has 60 cards; the minimum is 60.' },
      {
        check: 'copy_limit',
        status: 'pass',
        detail: 'No card exceeds the copy limit; basic lands are exempt.',
      },
      { check: 'sideboard', status: 'pass', detail: 'Sideboard has 0 cards; the maximum is 15.' },
      { check: 'banned', status: 'pass', detail: 'No card is banned in standard.' },
      {
        check: 'rotation',
        status: 'advisory',
        detail:
          'Rotation exposure cannot be checked: the local card data carries no set release dates.',
      },
    ],
    ...overrides,
  })

describe('readFormatCheck addresses the deck route it hangs off (c4-10 AC 7)', () => {
  it('asks for /api/deck/<id>/format-check, uncached, with the shared clock', async () => {
    const fetchMock = responding(formatCheckBody(), 200)

    await readFormatCheck(ATRAXA_DECK_ID)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/deck/${ATRAXA_DECK_ID}/format-check`)
    expect(fetchMock.mock.calls[0][1]?.cache).toBe('no-store')
    // One `request()` helper, one timeout guard — not a second copy of the clock.
    expect(fetchMock.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal)
  })

  it('is built ON deckPath, so the encoding argument holds rather than being restated', () => {
    // MEASURED against the running backend, not argued: a RAW `../decks` id answers
    // `200` carrying the DECK LIST. This route inherits that hazard, and inherits the fix by
    // construction rather than by a second `encodeURIComponent` call that could be forgotten.
    expect(formatCheckPath('../decks')).toBe('/api/deck/..%2Fdecks/format-check')
    expect(formatCheckPath(ATRAXA_DECK_ID)).toBe(`${deckPath(ATRAXA_DECK_ID)}/format-check`)
    expect(formatCheckPath('a/b?c#d')).toBe('/api/deck/a%2Fb%3Fc%23d/format-check')
  })

  it('shares the deck prefix — the fact every routing fixture has to branch on FIRST', () => {
    // Not trivia: `'/api/deck/x/format-check'.startsWith(DECK_PATH_PREFIX)` is TRUE, so a test
    // harness that checks the deck prefix first answers this route with the deck-detail body —
    // a `200` that is not this contract, silently, in whichever file exercises the whole path.
    // `App.test.tsx` carries the branch in BOTH of its routing fixtures because of this line.
    expect(formatCheckPath(ATRAXA_DECK_ID).startsWith(DECK_PATH_PREFIX)).toBe(true)
    expect(formatCheckPath(ATRAXA_DECK_ID).endsWith(FORMAT_CHECK_PATH_SUFFIX)).toBe(true)
  })
})

describe('a 200 from the format check: the rows are the contract (c4-10 AC 7)', () => {
  it('returns the promised record, six rows in CHECK_ORDER', async () => {
    responding(formatCheckBody(), 200)

    const outcome = await readFormatCheck(ATRAXA_DECK_ID)

    expect(outcome.kind).toBe('report')
    expect(outcome.kind === 'report' && outcome.report.rows.map((r) => r.check)).toEqual([
      'legality',
      'size',
      'copy_limit',
      'sideboard',
      'banned',
      'rotation',
    ])
  })

  it.each([
    ['a missing rows array', formatCheckBody({ rows: undefined })],
    ['rows as an object', formatCheckBody({ rows: { legality: 'pass' } })],
    ['a scalar body', '"format-check"'],
    ['a body that is not JSON', '<!doctype html><title>proxy</title>'],
    ['a null body', 'null'],
    // EMPTY rows would draw the exact panel the missing-rows case above refuses — a titled
    // "Format check" over nothing. A NULL or SCALAR element is worse than empty: the container
    // dereferences `row.check` during render with no error boundary, so one bad element would
    // take down the whole deck view (FR-13 inverted).
    ['an empty rows array', formatCheckBody({ rows: [] })],
    ['a null row element', formatCheckBody({ rows: [{ check: 'legality' }, null] })],
    ['a scalar row element', formatCheckBody({ rows: ['legality'] })],
  ])('reports %s as a contract violation, not as a report with no rows', async (_label, body) => {
    // The `namesOf` posture: an empty format-check panel reads as "nothing to report" about a
    // deck that was never checked, which is a calm and confidently wrong thing to draw.
    responding(body, 200)

    expect(await readFormatCheck(ATRAXA_DECK_ID)).toEqual({ kind: 'error', reason: null })
  })

  it('accepts the FORMATLESS report unchanged — it is a 200, never an error (Q8)', async () => {
    // DECLARED SYNTHETIC, and measured rather than composed: produced by overriding a real
    // deck's format to `'potato'` and running the real `format_check`. `deck_validator.py`'s own
    // docstring says so — *"never a different body and never an error"* — so a reader that
    // routed this to the `error` arm would be inventing a shape the contract deliberately
    // does not have.
    responding(
      formatCheckBody({
        is_legal: false,
        format: 'potato',
        format_recognized: false,
        rows: [
          {
            check: 'legality',
            status: 'advisory',
            detail: "'potato' is not a recognized format, so legality could not be checked.",
          },
          { check: 'size', status: 'pass', detail: 'Mainboard has 60 cards; the minimum is 60.' },
          {
            check: 'copy_limit',
            status: 'pass',
            detail: 'No card exceeds the copy limit; basic lands are exempt.',
          },
          {
            check: 'sideboard',
            status: 'pass',
            detail: 'Sideboard has 0 cards; the maximum is 15.',
          },
          {
            check: 'banned',
            status: 'advisory',
            detail: "'potato' is not a recognized format, so banned cards could not be checked.",
          },
          {
            check: 'rotation',
            status: 'advisory',
            detail:
              'Rotation exposure cannot be checked: the local card data carries no set release dates.',
          },
        ],
      }),
      200,
    )

    const outcome = await readFormatCheck(ATRAXA_DECK_ID)

    expect(outcome.kind).toBe('report')
    expect(outcome.kind === 'report' && outcome.report.format_recognized).toBe(false)
    expect(outcome.kind === 'report' && outcome.report.rows).toHaveLength(6)
  })

  it('accepts a single off-vocabulary row object — the non-vacuity half', async () => {
    // Otherwise every refusal above would pass for a narrower that refused anything unusual.
    // Row FIELDS are deliberately not validated (see `formatCheckOf`): only the
    // shape the renderer cannot survive — a non-object element, an empty array — is refused, so
    // an off-vocabulary row still reaches the report arm and renders degraded-but-standing.
    responding(
      formatCheckBody({ rows: [{ check: 'nonsense', status: 'exploded', detail: '' }] }),
      200,
    )

    const outcome = await readFormatCheck(ATRAXA_DECK_ID)

    expect(outcome.kind).toBe('report')
    expect(outcome.kind === 'report' && outcome.report.rows).toHaveLength(1)
  })
})

describe('the format check refuses in the deck vocabulary, and stays a value', () => {
  it.each([
    // MEASURED, not assumed: an unknown id AND a malformed id both answer `404 deck_not_found`
    // on this route — the deck routes carry no id shape constraint, unlike the card ones, so
    // there is no `400 invalid_request` to expect here at all.
    ['deck_not_found', 404],
    ['database_not_initialized', 503],
    ['database_unavailable', 503],
    ['payload_too_large', 413],
    ['internal_error', 500],
  ])('passes %s (%d) through unvalidated', async (reason, status) => {
    responding(JSON.stringify({ reason }), status)

    expect(await readFormatCheck(ATRAXA_DECK_ID)).toEqual({ kind: 'error', reason })
  })

  it('never rejects, on any of the four malformed inputs', async () => {
    for (const body of [null, '<!doctype html>', '{"detail": "x"}', '{"reason": 42}']) {
      responding(body, 503)
      await expect(readFormatCheck(ATRAXA_DECK_ID)).resolves.toEqual({
        kind: 'error',
        reason: null,
      })
    }

    stubFetch(() => Promise.reject(new TypeError('Failed to fetch')))
    await expect(readFormatCheck(ATRAXA_DECK_ID)).resolves.toEqual({ kind: 'unreachable' })
  })

  it.each([
    ['a 503', () => responding('{"reason": "database_not_initialized"}', 503)],
    ['a network rejection', () => stubFetch(() => Promise.reject(new TypeError('nope')))],
  ])('makes exactly ONE request for %s — no retry, no timer (AC 11)', async (_label, arrange) => {
    // The c3-2 trap applies here as it does to every path-parameter route, and this route has a
    // second reason of its own: the panel draws NOTHING on a refusal (Q6), so a retry would be
    // spending requests to fix a screen nobody can see is broken.
    const fetchMock = arrange()

    await readFormatCheck(ATRAXA_DECK_ID)

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

/**
 * The socket half of the one door.
 *
 * `posture.test.ts` asserts the network-door list is exactly this module, and its family regex
 * includes the socket constructor's name — so the construction stays HERE and the loop takes a
 * factory. These blocks test that: everything DOM-shaped about a socket stops in this file, and
 * `src/state/socket.test.ts` never touches a constructor at all.
 */
describe('readSessionTicket mints one ticket, and never twice (AC 3)', () => {
  it('asks for /api/session, uncached, and says so', async () => {
    const fetchMock = responding('{"ticket": "abc"}', 200)

    await expect(readSessionTicket()).resolves.toEqual({ kind: 'ticket', ticket: 'abc' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe(SESSION_PATH)
    // `no-store` on the CLIENT, matching `session.py`'s `no-store` on the response — and here
    // both halves are load-bearing rather than tidy, because this is the one 200 in the app that
    // carries a credential. A single-use ticket a cache is free to replay is single-use in name.
    expect(fetchMock.mock.calls[0][1]?.cache).toBe('no-store')
  })

  it('has no path parameter — the property that makes the loop cheap to reason about', () => {
    expect(SESSION_PATH).not.toMatch(/[{}:]/)
  })

  it('makes exactly ONE request against a wedged backend — the WAITING belongs to the loop', async () => {
    // The mint holds no retry of its own, and here that is a TTL argument rather than the usual
    // one: the ticket lives 30 s and the backoff ceiling is 30 s, so a reader that quietly waited
    // before answering would hand the upgrade a ticket that had already begun expiring — at
    // exactly the point in the schedule where there is no slack at all.
    const fetchMock = stubFetch(() => new Promise<Response>(() => undefined))

    void readSessionTicket()
    await Promise.resolve()

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['a body that is not JSON', () => responding('<html>captive portal</html>', 200)],
    ['a body with no ticket', () => responding('{}', 200)],
    ['a ticket that is not a string', () => responding('{"ticket": 42}', 200)],
    ['a BLANK ticket', () => responding('{"ticket": "   "}', 200)],
  ])('reports %s as a contract violation, not as a credential', async (_label, arrange) => {
    // A blank is refused for the same reason a missing one is: it is not a credential, and
    // presenting it costs a failed upgrade that the wire cannot even explain (`1008`, no body,
    // no reason token).
    arrange()

    await expect(readSessionTicket()).resolves.toEqual({ kind: 'error', reason: null })
  })

  it('carries a refusal token through, on a route that declares none', async () => {
    // `session.py` publishes no failure path at all, so reaching this arm means something that is
    // not the companion answered on the port. Modelled anyway: the union is a statement about the
    // wire, not about the backend.
    responding('{"reason": "internal_error"}', 500)

    await expect(readSessionTicket()).resolves.toEqual({ kind: 'error', reason: 'internal_error' })
  })

  it('reports a lost backend as unreachable — the ordinary case this whole story is about', async () => {
    stubFetch(() => Promise.reject(new TypeError('Failed to fetch')))

    await expect(readSessionTicket()).resolves.toEqual({ kind: 'unreachable' })
  })
})

describe('readInstanceId reads the health probe once, and folds every failure to null (17.1)', () => {
  it('asks for /health, uncached, with the shared clock', async () => {
    const fetchMock = responding('{"status": "ok", "instance_id": "3f9c1a7e"}', 200)

    await expect(readInstanceId()).resolves.toBe('3f9c1a7e')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe(HEALTH_PATH)
    expect(fetchMock.mock.calls[0][1]?.cache).toBe('no-store')
    // One `request()` helper, one timeout guard — not a second copy of the clock.
    expect(fetchMock.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal)
  })

  it('asks the route the BACKEND declares — the constant is pinned, not self-compared', () => {
    // Every other assertion in this describe compares the fetch call against HEALTH_PATH, so a
    // typo'd constant would ship as a permanently "not yet confirmed" tooltip with every test
    // green. A LITERAL pin rather than a type-level one against the generated
    // `paths`: `wire-contract.test.ts` allows the generated file to be imported through
    // `src/api/schema.ts` alone, and the backend's own `openapi.json` (which the drift gate
    // holds this repo to) declares `/health` — so the literal is the same authority, one hop
    // shorter.
    expect(HEALTH_PATH).toBe('/health')
  })

  it('has no path parameter, and no auth either — health is what a caller reads FIRST (AD-4)', () => {
    expect(HEALTH_PATH).not.toMatch(/[{}:]/)
  })

  it('sends NO credential of any kind — the probe precedes the decision to present one', async () => {
    // AD-4's ordering made concrete: health is what a caller reads BEFORE deciding to trust the
    // port, so the request must carry nothing worth stealing. The app's one credential is the
    // WS ticket, which travels as a query parameter on the socket URL and never as a header —
    // asserted here as the absence of any auth-shaped header on the recorded call.
    const fetchMock = responding('{"status": "ok", "instance_id": "abc"}', 200)

    await readInstanceId()

    const headers = fetchMock.mock.calls[0][1]?.headers ?? {}
    expect(Object.keys(headers).map((name) => name.toLowerCase())).toEqual(['accept'])
  })

  it('preserves the id’s case and length exactly — it is the identity, not a label', async () => {
    responding('{"status": "ok", "instance_id": "AbCdEf0123456789AbCdEf0123456789"}', 200)

    await expect(readInstanceId()).resolves.toBe('AbCdEf0123456789AbCdEf0123456789')
  })

  it('TRIMS a padded id — the fold must not be weaker than the equality it feeds', async () => {
    // The stored id feeds `applyInstanceId`'s same-value guard and the "did the process change"
    // reading, so a padded copy of the same id passed through raw would compare as a different
    // backend — `connection.ts`'s deck_id trim, for the same reason.
    responding('{"status": "ok", "instance_id": "  abc  "}', 200)

    await expect(readInstanceId()).resolves.toBe('abc')
  })

  it.each([
    ['a body that is not JSON', () => responding('<html>captive portal</html>', 200)],
    ['a body with no instance_id', () => responding('{"status": "ok"}', 200)],
    ['an instance_id that is not a string', () => responding('{"instance_id": 42}', 200)],
    ['a BLANK instance_id', () => responding('{"instance_id": "   "}', 200)],
    ['a scalar body', () => responding('"ok"', 200)],
  ])('reports %s as null, not as an identity', async (_label, arrange) => {
    // A blank cannot distinguish one process from another, so confirming it would let the
    // tooltip claim an identity nothing asserted — `ticketOf`'s posture, applied to an id.
    arrange()

    await expect(readInstanceId()).resolves.toBe(null)
  })

  it('reports a refusal as null — the consumer has one question and no reason to act on tokens', async () => {
    responding('{"reason": "internal_error"}', 500)

    await expect(readInstanceId()).resolves.toBe(null)
  })

  it('reports a lost backend as null too, and never rejects — the trigger fires it void', async () => {
    // The caller's last-confirmed semantics are what make one flat `null` sufficient here: a
    // failed refresh writes nothing, so the three-case outcome union's distinctions would be
    // computed and then discarded.
    stubFetch(() => Promise.reject(new TypeError('Failed to fetch')))

    await expect(readInstanceId()).resolves.toBe(null)
  })
})

describe('agentSocketUrl is built entirely from window.location (AC 1)', () => {
  it('never names a port, and never switches the host spelling', () => {
    const url = new URL(agentSocketUrl('abc'))

    // The page's OWN authority, whatever it is. A hardcoded 8765 — or a hardcoded `127.0.0.1`
    // where the page said `localhost` — would be visible right here. The spelling matters as much
    // as the number: `security.py`'s `origin_is_allowed` compares the handshake's Origin by EXACT
    // match after lowercasing, with nothing parsed or normalised.
    expect(url.host).toBe(window.location.host)
    expect(url.pathname).toBe(WS_PATH)
    expect(agentSocketUrl('abc')).toContain(window.location.host)
  })

  it('presents the ticket as a QUERY parameter, encoded', () => {
    // `ws.py:97` takes it in the query because a browser socket cannot set headers — the
    // constructor accepts a URL and a subprotocol list and nothing else.
    expect(new URL(agentSocketUrl('a b/c?d')).searchParams.get('ticket')).toBe('a b/c?d')
    expect(agentSocketUrl('a b/c?d')).toContain('ticket=a%20b%2Fc%3Fd')
  })

  it('speaks ws: from an http: page and wss: from an https: one', () => {
    expect(agentSocketUrl('abc').startsWith('ws://')).toBe(true)

    // The `wss:` arm is unreachable today — the companion is http on loopback — and it exists
    // because a hardcoded `ws:` on an https page is refused by every browser as mixed content:
    // a one-word failure to prevent and an afternoon to diagnose.
    const location = window.location
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { protocol: 'https:', host: 'example.test:443' },
    })
    try {
      expect(agentSocketUrl('abc')).toBe('wss://example.test:443/ws?ticket=abc')
    } finally {
      Object.defineProperty(window, 'location', { configurable: true, value: location })
    }
  })
})

describe('agentEventOf narrows one frame, or refuses it (AC 13)', () => {
  const envelope = (kind: string) =>
    JSON.stringify({ kind, id: 'x', ts: '2026-08-08T00:00:00Z', payload: {} })

  it.each(['suggestions', 'swaps', 'tier_list', 'groups', 'deck_changed', 'active_deck_changed'])(
    'accepts a %s frame',
    (kind) => {
      expect(agentEventOf(envelope(kind))?.kind).toBe(kind)
    },
  )

  it.each([
    ['a non-JSON frame', 'not json at all'],
    ['an empty frame', ''],
    ['a JSON scalar', '42'],
    ['a JSON array', '[1, 2, 3]'],
    ['JSON null', 'null'],
    ['an object with no kind', '{"id": "x"}'],
    ['a kind that is not a string', '{"kind": 7}'],
    ['a kind this build does not know', envelope('telemetry')],
    // `Object.hasOwn` rather than a truthiness check, for `panel.ts`'s reason: indexing a plain
    // object with an inherited key returns a value, and a wire string is attacker-adjacent input.
    ['a prototype key masquerading as a kind', envelope('__proto__')],
    ['a prototype METHOD name', envelope('constructor')],
  ])('refuses %s with null rather than throwing', (_label, data) => {
    expect(agentEventOf(data)).toBeNull()
  })

  it('refuses a BINARY frame — the backend sends only text', () => {
    // A frame's payload is genuinely `unknown`: a binary frame delivers a Blob or an
    // ArrayBuffer. A non-string here is a contract violation and lands in the same null.
    expect(agentEventOf(new ArrayBuffer(8))).toBeNull()
    expect(agentEventOf(null)).toBeNull()
    expect(agentEventOf(undefined)).toBeNull()
  })
})

describe('openAgentSocket wires one socket, and collapses four outcomes into one (Q1)', () => {
  /** A scriptable stand-in for the platform constructor. jsdom HAS one; we never want to use it. */
  class FakeSocket {
    static built: FakeSocket[] = []
    onopen: (() => void) | null = null
    onmessage: ((event: { data: unknown }) => void) | null = null
    onclose: (() => void) | null = null
    onerror: (() => void) | null = null
    closed = 0
    // A plain field, not a parameter property: `erasableSyntaxOnly` is on and a parameter
    // property emits code.
    readonly url: string
    constructor(url: string) {
      this.url = url
      FakeSocket.built.push(this)
    }
    close() {
      this.closed += 1
    }
  }

  const recording = () => {
    const opens: number[] = []
    const closes: number[] = []
    const messages: (string | null)[] = []
    const handlers: AgentSocketHandlers = {
      onOpen: () => opens.push(1),
      onMessage: (event) => messages.push(event === null ? null : event.kind),
      onClose: () => closes.push(1),
    }
    return { opens, closes, messages, handlers }
  }

  const install = () => {
    FakeSocket.built = []
    vi.stubGlobal('WebSocket', FakeSocket)
    return FakeSocket
  }

  it('dials the URL the ticket belongs to, and attaches all four slots before returning', () => {
    const Fake = install()
    const { handlers } = recording()

    openAgentSocket('the-ticket', handlers)

    expect(Fake.built).toHaveLength(1)
    expect(Fake.built[0].url).toBe(agentSocketUrl('the-ticket'))
    // Attached BEFORE the return, so a handshake refused fast on loopback cannot dispatch into an
    // empty slot.
    for (const slot of ['onopen', 'onmessage', 'onclose', 'onerror'] as const) {
      expect(Fake.built[0][slot]).not.toBeNull()
    }
  })

  it('reports BOTH close and error as the same ending, and does not suppress the second', () => {
    // `ws.py:29-40`: every refusal is close code 1008 pre-accept, rendered as HTTP 403, with no
    // body and no reason token — a missing ticket, an expired one, a replayed one and a bad
    // Origin are DELIBERATELY indistinguishable. There is nothing for two callbacks to say.
    // Firing twice is left to the loop's generation counter on purpose: one mechanism answers
    // both the duplicate and the stale-callback case, rather than two that must agree.
    const Fake = install()
    const { closes, handlers } = recording()

    openAgentSocket('t', handlers)
    Fake.built[0].onerror?.()
    Fake.built[0].onclose?.()

    expect(closes).toHaveLength(2)
  })

  it('narrows each frame on the way through, so the loop never sees a raw one', () => {
    const Fake = install()
    const { messages, handlers } = recording()

    openAgentSocket('t', handlers)
    Fake.built[0].onmessage?.({
      data: JSON.stringify({ kind: 'deck_changed', id: 'x', ts: 'now', payload: {} }),
    })
    Fake.built[0].onmessage?.({ data: 'not json' })

    expect(messages).toEqual(['deck_changed', null])
  })

  it('DETACHES before it closes, so its own close event cannot call back', () => {
    // The ordering is the assertion. `close()` dispatches a close event, so leaving the slot
    // attached would call back into a loop that has already decided this socket is over —
    // harmless today (the generation check catches it) and exactly the kind of harmless that
    // stops being harmless the day someone adds a counter to that path.
    const Fake = install()
    const { closes, handlers } = recording()

    const handle = openAgentSocket('t', handlers)
    handle.close()

    expect(Fake.built[0].closed).toBe(1)
    expect(Fake.built[0].onclose).toBeNull()
    expect(Fake.built[0].onmessage).toBeNull()
    expect(closes).toHaveLength(0)
  })

  it('opens the socket the LOOP would open — the two are not two spellings of the URL', () => {
    // The non-vacuity half: this module is the only place a socket URL is built,
    // so `createAgentSocket`'s default factory and this test dial the identical string. A second
    // builder in `state/socket.ts` would be a second network door AND a second spelling.
    const Fake = install()
    const { handlers } = recording()

    openAgentSocket('shared', handlers)

    expect(Fake.built[0].url).toContain(`${WS_PATH}?ticket=shared`)
  })
})
