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
  ACTIVE_DECK_PATH,
  CARD_PATH_PREFIX,
  DECKS_PATH,
  DECK_PATH_PREFIX,
  FORMAT_CHECK_PATH_SUFFIX,
  READ_TIMEOUT_MS,
  cardPath,
  deckPath,
  formatCheckPath,
  readActiveDeck,
  readCard,
  readDeck,
  readDecks,
  readFormatCheck,
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

// ===================== c4-2: the two boot reads =========================================

/**
 * The deck the epic describes and this machine actually holds: "Atraxa Counter Cabinet v2
 * (owned)", 99 distinct cards, 100 total, measured at `2095050`.
 */
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
    // be masking a `400` about an id that can never succeed (the c3-2 measurement).
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

describe('neither boot reader retries (AC 12, Q6)', () => {
  it.each([
    ['a 503 on the deck read', () => responding('{"reason": "database_not_initialized"}', 503)],
    ['a network rejection', () => stubFetch(() => Promise.reject(new TypeError('nope')))],
  ])('makes exactly ONE request for %s', async (_label, arrange) => {
    // The c3-2 trap applies to `/api/deck/{deck_id}` exactly as it did to `/api/cards/{card_id}`:
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

// ===================== c4-10: the format check ==========================================

/**
 * A REAL report, copied out of the running backend rather than composed (c4-10 AC 26).
 *
 * Measured read-only at `4e31ea7` by driving the real ASGI app against the shipped database:
 * this is `GET /api/deck/{id}/format-check` for a real all-pass Standard deck, verbatim — six
 * rows in `CHECK_ORDER`, five passes and the permanent rotation advisory. Nothing here is
 * invented, which is what AC 26 asks for and what c4-8's High cost when it was not true.
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
    // MEASURED at c4-2 against the running backend, not argued: a RAW `../decks` id answers
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
    // The next three are c4-10 review decision 1a. EMPTY rows drew the exact panel the
    // missing-rows case above refuses — a titled "Format check" over nothing — and the first
    // draft's own docstring made the argument while the code accepted it, untested. A NULL or
    // SCALAR element is worse than empty: the container dereferences `row.check` during render
    // with no error boundary, so one bad element took down the whole deck view (FR-13 inverted).
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
    // docstring rules it — *"never a different body and never an error"* — so a reader that
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
    // (The c4-10 review retitled this: the first draft's title claimed "rows are all violations"
    // over a fixture that was one nonsense row — the body was right and the caption was not.)
    // Otherwise every refusal above would pass for a narrower that refused anything unusual.
    // Row FIELDS are deliberately not validated (see `formatCheckOf`, decision 1a): only the
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
