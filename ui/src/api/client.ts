/**
 * The ONE door to the network in `ui/src` — every route, one `fetch`, asserted by name.
 *
 * Written by c3-9 as `src/api/decks.ts` when `GET /api/decks` was the only route the SPA called;
 * **renamed here by c4-1 (Q1) in the same commit as the first card route.**
 *
 * ================= WHY THE FILE HAS A ROUTE-NEUTRAL NAME NOW (c4-1, Q1) =================
 *
 * `tests/posture.test.ts` asserts the network-door list **exhaustively** — `expect(doors)
 * .toEqual([…])`, one entry — and the property it is protecting is *"one door, named
 * exhaustively"*, not *"the door is called `decks.ts`"*. c4-1 had two ways to add
 * `GET /api/cards/{card_id}`:
 *
 *   1. A second module, `src/api/cards.ts`. It is the natural layout and it **fails that green
 *      test by design**. Taking it would have meant weakening the one-door rule into a
 *      per-directory rule — a real loss, argued nowhere, to buy a filename.
 *   2. Keep one module and give it a name that does not lie. A module called `decks` exporting
 *      `readCard` is *"prose outrunning code"*, which is this epic's standing finding four rounds
 *      running.
 *
 * (2), and the guard, its comment and `ui/README.md`'s *"Not here yet"* section were edited in
 * this same commit. **The next route goes here too.** `GET /api/deck/{deck_id}` is c4-2's,
 * `GET /api/active-deck` is c4-2's, the format check is c4-10's — all of them belong in this file
 * until somebody argues the one-door property away on purpose.
 *
 * ================= WHAT c4-2 INHERITS ===================================================
 *
 * **c4-2** adds the real deck bootstrap. It inherits a poll that already calls `GET /api/decks`,
 * and its job is to read the DECK rather than the deck NAMES: c3-9 renders the `no-active-deck`
 * panel for every `200`, because until c4-2 there is no deck view to show. It also inherits
 * {@link readCard}'s seeding partner — `seedCardSummaries` in `src/state/cards.ts` — which turns
 * the `DeckCardSummary[]` its own fetch already returns into the cache's summary tier for free.
 *
 * ================= WHY THE DECK POLL IS SAFE TO RETRY, AND A CARD READ IS NOT ===========
 *
 * Measured at c3-2 and pinned in `test_routes_cards.py`: a malformed id sent to a backend with no
 * database answers **`database_not_initialized`, not `invalid_request`**, because FastAPI's
 * `solve_dependencies` runs dependencies before it collects parameter-validation errors, so
 * `get_session`'s `CompanionError` propagates first. A client that treats both database tokens as
 * "retry quietly" therefore retries a request whose id can never succeed, forever.
 *
 * **The deck poll is immune, and the reason is structural rather than careful: `/api/decks` has no
 * path parameter.** There is no id to be malformed, so no `503` it sees can be masking a `400`.
 * **{@link readCard} is NOT immune**, and this module does not try to solve it: `readCard` makes
 * exactly ONE request and has no retry of its own. The bound on attempts per id lives one layer up
 * with the thing that decides to ask again — `MAX_ATTEMPTS_PER_CARD` in `src/state/cards.ts`.
 * Keeping the two apart is deliberate: a retry inside this module would be invisible to the cache
 * that counts requests, and AC 25 makes the request COUNT the assertion.
 *
 * ================= A TOTAL UNION, NEVER A REJECTION ====================================
 *
 * Neither reader throws and neither returns `null`. Four failure inputs — a non-2xx with no body,
 * a body that is not JSON, a body with no `reason`, and a network rejection — are four distinct
 * things and every one of them is a value in the unions below. The panel decision is NOT made
 * here (see `src/state/panel.ts`): this module reports what came back, including a `reason` string
 * it has deliberately **not** validated, and the one place a wire value becomes a `StateKey` is
 * the boundary that owns `PANEL_FOR_REASON`.
 *
 * **A card refusal never reaches that boundary at all** (c4-1 AC 13). `card_not_found` maps to
 * `null` in `PANEL_FOR_REASON`, which `panelFor` clamps to `'internal-error'` — so routing a card
 * refusal through it would replace a working deck view with *"The companion hit a bug"* because
 * one card was missing. That is the FR-13 failure `states.ts` bans outright. `src/state/cards.ts`
 * is where a card token goes.
 */

import type { Card, DeckSummary, ErrorResponse } from './schema'

/**
 * The one route this story polls. Read by `tests/copy-tails.test.ts`, which holds
 * `EXPERIENCE.md`'s un-quoted no-active-deck clause (*"the available-deck list from
 * `GET /api/decks`"*) to the endpoint this file actually calls — so the artefact and the code
 * cannot drift apart silently in either direction.
 */
export const DECKS_PATH = '/api/decks'

/**
 * How long one request may take before it is abandoned as `unreachable`.
 *
 * 10 s: the backend's SQLite connection waits up to **5 s** on a locked database
 * (`database.py` sets `timeout=5`), so every answer a healthy backend will ever give arrives
 * inside that; twice it means no true answer is ever cut off. What the clock is FOR is the one
 * failure `fetch` alone has no bound on — a process that accepts the connection and never
 * writes a response. Without it, `await read()` never settles, the poller schedules nothing,
 * and the calm initial panel stands forever with the whole "comes alive on its own" loop
 * silently dead. With it, a wedge becomes `{kind: 'unreachable'}` and rides the ordinary
 * backoff like any other lost backend.
 */
export const READ_TIMEOUT_MS = 10_000

/**
 * What one poll of `GET /api/decks` came back with. Three cases, and they are genuinely three:
 *
 * - `decks` — a `200` whose body was the array the contract promises. The deck NAMES, which is
 *   all the `no-active-deck` panel renders.
 * - `error` — a response arrived and the request was refused. `reason` is the body's token
 *   **exactly as it crossed the wire and unvalidated**, or `null` when the body could not yield
 *   one at all (absent, unparseable, no `reason` key, or a `reason` that is not a string).
 * - `unreachable` — no response at all: `fetch` itself rejected. NOT the same as `error` with a
 *   `null` reason, and the difference is load-bearing — see the poller, which retries this one
 *   without claiming a state, because the panel that describes a lost backend
 *   (`disconnected`) is **c5-6's** by `CLIENT_ONLY_STATES` and this story may not claim it.
 */
export type DecksOutcome =
  | { readonly kind: 'decks'; readonly decks: readonly string[] }
  | { readonly kind: 'error'; readonly reason: string | null }
  | { readonly kind: 'unreachable' }

/**
 * Where `GET /api/cards/{card_id}` lives, minus the id.
 *
 * A PREFIX and not a template, so that `client.test.ts` can keep asserting what
 * `decks.test.ts` asserted before it: {@link DECKS_PATH} carries no `{`, `}` or `:` and is
 * therefore structurally retry-safe, while this one obviously does carry an id and is therefore
 * obviously not. The difference is the whole subject of the retry section in this file's header,
 * and two constants that look alike would bury it.
 */
export const CARD_PATH_PREFIX = '/api/cards/'

/**
 * The path for one card id.
 *
 * `encodeURIComponent`, and it is load-bearing rather than defensive. The id comes from
 * `deck_cards.card_id`, a column with **no shape constraint** and no FK enforcement on the async
 * engine (measured today: 0 of 2,027 rows are non-canonical, so this is latent, not live). An id
 * containing `/`, `?` or `#` would otherwise change which route is addressed — a value that is
 * merely unknown would become a request to somewhere else entirely. Encoded, it stays one path
 * segment, the route's uuid pattern refuses it, and the answer is `400 invalid_request`, which
 * `src/state/cards.ts` turns into the unknown-card placeholder by Q5's ruling.
 *
 * The one id encoding cannot make safe is the EMPTY one: `cardPath('')` is the bare collection
 * path `/api/cards/` — there is no segment to keep singular — which is a different route, not a
 * malformed parameter. `hydrateCard` refuses that id one layer up, before any request is made.
 *
 * Args:
 *   cardId: The Scryfall printing uuid — untrusted, and treated that way.
 *
 * Returns:
 *   The request path.
 */
export const cardPath = (cardId: string): string =>
  `${CARD_PATH_PREFIX}${encodeURIComponent(cardId)}`

/**
 * What one read of `GET /api/cards/{card_id}` came back with. The same three cases as
 * {@link DecksOutcome}, and for the same reasons:
 *
 * - `card` — a `200` whose body was the promised record.
 * - `error` — a response arrived and the request was refused. `reason` is the body's token
 *   **exactly as it crossed the wire and unvalidated**, or `null` when the body could not yield
 *   one. `card_not_found` is the interesting member and it is NOT an exception: it rides the
 *   ordinary refusal path, and the thing that makes it a placeholder rather than a panel is
 *   `src/state/cards.ts`, not this union.
 * - `unreachable` — no response at all.
 */
export type CardOutcome =
  | { readonly kind: 'card'; readonly card: Card }
  | { readonly kind: 'error'; readonly reason: string | null }
  | { readonly kind: 'unreachable' }

/** The `reason` a body carries, or `null` if it carries none this code can read. */
const reasonOf = (body: unknown): string | null => {
  if (typeof body !== 'object' || body === null) return null
  // `in` rather than a cast to `ErrorResponse`: the value on the wire is untyped JSON, and the
  // whole point of this function is that it may be anything at all.
  if (!('reason' in body)) return null
  const reason: unknown = (body as Partial<ErrorResponse>).reason
  return typeof reason === 'string' ? reason : null
}

/**
 * The deck names out of a `200` body, or `null` if the body was not the promised array.
 *
 * A `200` that is not an array is a **contract violation**, not an empty deck list, and it is
 * reported as one (the caller turns it into `internal-error`) — answering "no decks" would put a
 * calm, wrong panel on the glass. Within a well-formed array the posture flips: an entry that is
 * not an object with a non-blank string `name` is DROPPED rather than failing the whole read,
 * which is FR-13's *"one unresolvable row must never take down a view"* read across to this list.
 * `StatePanel` already drops blank names for the same reason; doing it here too costs nothing and
 * means the panel is never handed one.
 */
const namesOf = (body: unknown): readonly string[] | null => {
  if (!Array.isArray(body)) return null
  const rows: readonly unknown[] = body
  return rows
    .map((row) =>
      typeof row === 'object' && row !== null && 'name' in row
        ? (row as Partial<DeckSummary>).name
        : undefined,
    )
    .filter((name): name is string => typeof name === 'string' && name.trim() !== '')
}

/**
 * The card out of a `200` body, or `null` if the body was not the promised record.
 *
 * **How much of a 42-field record to check, and why the answer is two fields.** The generated
 * type promises all of them, so a full validator would be a second, hand-maintained copy of
 * `openapi.json` — exactly the drift `wire-contract.test.ts` exists to ban. What the checks below
 * are actually for is the case `namesOf` handles for the deck poll: a `200` that is not this
 * contract at all (a captive portal's HTML, a proxy's JSON error page), which must be reported as
 * a contract violation rather than cached as a card whose every field is `undefined`. `id` and
 * `name` are the two the cache and every consumer read first, so a body carrying both as strings
 * is a body from this route.
 *
 * The residue, declared rather than closed: a `200` carrying `{id, name}` and nothing else is
 * accepted here and reaches consumers as a `Card` with holes. That is a backend contract
 * violation, not attacker input — the route's `response_model=Card` makes it a FastAPI bug — and
 * the answer to it is the openapi drift gate, not a validator here.
 */
const cardOf = (body: unknown): Card | null => {
  if (typeof body !== 'object' || body === null) return null
  const record = body as Partial<Card>
  // Blank counts as absent, exactly as `namesOf` above rules for the deck list (FR-13's posture):
  // a "card" whose id cannot key the cache or whose name cannot label a tile is not this
  // contract, whatever its field types say.
  if (typeof record.id !== 'string' || record.id.trim() === '') return null
  if (typeof record.name !== 'string' || record.name.trim() === '') return null
  return body as Card
}

/** A response that ARRIVED: whether it was a 2xx, and whatever body could be read out of it. */
interface Received {
  readonly ok: boolean
  readonly body: unknown
}

/**
 * Issue one request and read its body, or report that nothing arrived.
 *
 * **The one `fetch` in `ui/src`, and the reason both readers share it rather than each spelling
 * it out.** `tests/posture.test.ts` asserts the door list by FILE, so two calls in this module
 * would pass it — but the timeout guard below is subtle enough that a second copy is a second
 * place to get it wrong, and c3-9's own review found the bug it now prevents. One call site, two
 * routes.
 *
 * `cache: 'no-store'` on both, for two different reasons that happen to agree. For the deck poll
 * the whole point is to observe the backend CHANGE state underneath it: `deps.get_session`
 * re-probes readiness on every request and never caches (FR-22), and a client-side cache would be
 * the one place that promise could still be broken. For a card read the reason is
 * determinism: `GET /api/cards/{card_id}` sets **no** cache headers at all (ledgered, and
 * re-homed by c4-1 Q7 — see `deferred-work.md`), so a browser is free to apply heuristic freshness
 * to it and serve a row from before a database refresh. The app's own in-memory cache is the
 * caching layer here — one request per id per tab — so `no-store` costs nothing and removes the
 * only source of staleness that is not ours.
 *
 * Args:
 *   path: The request path.
 *
 * Returns:
 *   What arrived, or `null` if nothing did. Never rejects.
 */
const request = async (path: string): Promise<Received | null> => {
  // The clock, where the runtime can build one. `AbortSignal.timeout` is inside the bundle's
  // own browser floor (no `build.target` in vite.config.ts, so Vite's default
  // `baseline-widely-available` — Chrome/Edge 107+, Firefox 104+, Safari 16+ — every one of
  // which postdates the API: Chrome 103, Firefox 100, Safari 15.4), so the `undefined` arm is
  // unreachable in a browser this bundle targets. The guard exists because the failure without
  // it is the worst this module can produce: the constructor throwing INSIDE the `try` below
  // would classify every read as `unreachable` before `fetch` ever ran — a calm panel retrying
  // forever against a healthy backend it never contacts. An out-of-floor browser degrades to
  // NO timeout instead (the wedge risk returns, on a browser the bundle does not target); it
  // never masquerades as a lost backend.
  const signal =
    typeof AbortSignal.timeout === 'function' ? AbortSignal.timeout(READ_TIMEOUT_MS) : undefined

  let response: Response
  try {
    response = await fetch(path, {
      cache: 'no-store',
      headers: { Accept: 'application/json' },
      // A timeout abort is a rejection, so it lands in the same `unreachable` as a lost
      // backend — which is what it is. See `READ_TIMEOUT_MS` for the arithmetic.
      signal,
    })
  } catch {
    return null
  }

  // `.json()` rejects on an empty body and on anything that is not JSON — the two of the four
  // malformed inputs that arrive one layer earlier than a missing `reason` key.
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }

  return { ok: response.ok, body }
}

/**
 * Poll `GET /api/decks` once, and report what happened without ever throwing.
 *
 * Returns:
 *   A `DecksOutcome`. Never rejects — a rejection is `{ kind: 'unreachable' }`.
 */
export const readDecks = async (): Promise<DecksOutcome> => {
  const received = await request(DECKS_PATH)
  if (received === null) return { kind: 'unreachable' }

  if (!received.ok) return { kind: 'error', reason: reasonOf(received.body) }

  const decks = namesOf(received.body)
  // A `200` whose body is not the promised array: see `namesOf`. `null` is the reason a
  // contract violation has — there is no token for "the backend answered something else".
  return decks === null ? { kind: 'error', reason: null } : { kind: 'decks', decks }
}

/**
 * Read one card's full record once, and report what happened without ever throwing.
 *
 * **ONE request, no retry, no loop, no timer.** Whether to ask again is the caller's decision and
 * it is bounded there — see `MAX_ATTEMPTS_PER_CARD` in `src/state/cards.ts` and this file's
 * header for why a per-card route cannot be retried on the token alone.
 *
 * **Nothing here dedupes, either.** Two concurrent calls for the same id make two requests, and
 * that is correct for a function whose whole contract is "issue one request": the deduping is the
 * cache's, it goes AROUND this function, and keeping it out of here is what lets
 * `cards.test.ts` count requests by counting calls.
 *
 * Args:
 *   cardId: The Scryfall printing uuid. Encoded into the path by {@link cardPath}; not validated
 *     here, because the route's own uuid pattern is the authority and a second copy of it in the
 *     client would be a shape to drift.
 *
 * Returns:
 *   A `CardOutcome`. Never rejects — a rejection is `{ kind: 'unreachable' }`.
 */
export const readCard = async (cardId: string): Promise<CardOutcome> => {
  const received = await request(cardPath(cardId))
  if (received === null) return { kind: 'unreachable' }

  if (!received.ok) return { kind: 'error', reason: reasonOf(received.body) }

  const card = cardOf(received.body)
  // A `200` that is not the promised record: the same posture `readDecks` takes on a `200` that
  // is not the promised array. Caching a hollow object would put `undefined` where a name goes.
  return card === null ? { kind: 'error', reason: null } : { kind: 'card', card }
}
