/**
 * The ONE door to the network in `ui/src`: every route, one `fetch`, one socket constructor.
 * `tests/posture.test.ts` asserts the door list exhaustively as `['src/api/client.ts']` (its regex
 * includes the socket constructor's name), so every new route belongs here, not beside its consumer.
 *
 * Every reader returns a total outcome union and never throws; passes the `reason` token through
 * unvalidated (`src/state/panel.ts` owns `PANEL_FOR_REASON`); and requests a per-id route exactly
 * ONCE. The last is structural: a malformed id sent to a backend with no database answers
 * `database_not_initialized`, not `invalid_request` (pinned in `test_routes_cards.py`), so a
 * client retrying on the token alone would retry an id that can never succeed, forever. Only
 * `/api/decks`, with no path parameter, is safe to retry; elsewhere the decision to ask again
 * lives with the layer that counts attempts, or nowhere. A card refusal never becomes a panel (the
 * FR-13 failure: one missing tile taking down a working deck view); a deck refusal does.
 */

import type {
  ActiveDeck,
  AgentEvent,
  AgentEventKind,
  Card,
  DeckDetail,
  DeckSummary,
  ErrorResponse,
  FormatCheckReport,
  HealthResponse,
  SessionTicket,
} from './schema'

/**
 * The polled route. `tests/copy-tails.test.ts` holds `EXPERIENCE.md`'s `GET /api/decks` clause to
 * this constant, so prose and code cannot drift apart silently.
 */
export const DECKS_PATH = '/api/decks'

/**
 * How long one request may take before it is abandoned as `unreachable`. Twice the backend's
 * SQLite busy timeout (`database.py` sets `timeout=5`), so no true answer is ever cut off; it
 * bounds the one failure `fetch` alone cannot: a process that accepts the connection and never
 * responds, which would otherwise leave the poller silent forever.
 */
export const READ_TIMEOUT_MS = 10_000

/**
 * What one poll of `GET /api/decks` came back with. `error` carries the body's token exactly as it
 * crossed the wire, or `null`. `unreachable` (`fetch` rejected) is distinct: no state was decided.
 */
export type DecksOutcome =
  | { readonly kind: 'decks'; readonly decks: readonly string[] }
  | { readonly kind: 'error'; readonly reason: string | null }
  | { readonly kind: 'unreachable' }

/**
 * Where `GET /api/cards/{card_id}` lives, minus the id. A PREFIX rather than a template so
 * `client.test.ts` can assert that {@link DECKS_PATH} carries no `{`, `}` or `:` (retry-safe)
 * while this one visibly takes an id (not retry-safe).
 */
export const CARD_PATH_PREFIX = '/api/cards/'

/**
 * The path for one card id, `encodeURIComponent`-ed. `deck_cards.card_id` has no shape constraint,
 * so an id containing `/`, `?` or `#` would otherwise address a different route; encoded, the
 * route's uuid pattern refuses it and the `400` becomes the unknown-card placeholder. The empty id
 * (`/api/cards/`, a different route) is refused by `hydrateCard` before any request.
 */
export const cardPath = (cardId: string): string =>
  `${CARD_PATH_PREFIX}${encodeURIComponent(cardId)}`

/**
 * What one read of `GET /api/cards/{card_id}` came back with. `card_not_found` is an ordinary
 * `error` member; what makes it a placeholder rather than a panel is `src/state/cards.ts`.
 */
export type CardOutcome =
  | { readonly kind: 'card'; readonly card: Card }
  | { readonly kind: 'error'; readonly reason: string | null }
  | { readonly kind: 'unreachable' }

/** The route the boot asks first (FR-07). No path parameter, and no `DbSession`, so nothing to retry FOR. */
export const ACTIVE_DECK_PATH = '/api/active-deck'

/**
 * What one read of `GET /api/active-deck` came back with. `deckId: null` is the ordinary answer
 * after every backend restart, not a failure: the slot lives in the companion's memory and dies
 * with the process (FR-07). Only `400` and `500` can reach `error`; there is no `503` or `404`.
 */
export type ActiveDeckOutcome =
  | { readonly kind: 'active-deck'; readonly deckId: string | null }
  | { readonly kind: 'error'; readonly reason: string | null }
  | { readonly kind: 'unreachable' }

/** Where `GET /api/deck/{deck_id}` lives, minus the id. A PREFIX, for {@link CARD_PATH_PREFIX}'s reason. */
export const DECK_PATH_PREFIX = '/api/deck/'

/**
 * The path for one deck id, `encodeURIComponent`-ed. A deck id has no declared shape and
 * `PUT /api/active-deck` stores any non-blank string verbatim. Measured: a raw `../decks` id
 * answers `200` carrying the DECK LIST (a different route succeeding); `..%2Fdecks` answers
 * `404 invalid_request`. The empty id is refused by `bootDeck` in `src/state/deck.ts` first.
 */
export const deckPath = (deckId: string): string =>
  `${DECK_PATH_PREFIX}${encodeURIComponent(deckId)}`

/**
 * What one read of `GET /api/deck/{deck_id}` came back with. Unlike {@link ActiveDeckOutcome},
 * `error` carries the full refusal vocabulary and DOES become a panel: see `src/state/deck.ts`.
 */
export type DeckOutcome =
  | { readonly kind: 'deck'; readonly deck: DeckDetail }
  | { readonly kind: 'error'; readonly reason: string | null }
  | { readonly kind: 'unreachable' }

/**
 * Where the format check lives: the deck path plus this suffix, because the route hangs off the
 * deck router and two independent prefixes could drift apart. It shares {@link DECK_PATH_PREFIX},
 * so a fixture that routes by prefix must branch on THIS first (`App.test.tsx` does).
 */
export const FORMAT_CHECK_PATH_SUFFIX = '/format-check'

/**
 * The format-check path for one deck id. Built on {@link deckPath} so the encoding argument holds
 * by construction; the empty id (`/api/deck//format-check`) is refused in `src/state/formatCheck.ts`.
 */
export const formatCheckPath = (deckId: string): string =>
  `${deckPath(deckId)}${FORMAT_CHECK_PATH_SUFFIX}`

/**
 * What one read of the format check came back with. A deck whose format cannot be checked is NOT
 * a separate case: `deck_validator.py` answers the same shape, so it lands in `report` with
 * `format_recognized: false`. None of the three becomes a panel: the deck is still on the glass,
 * so `src/state/formatCheck.ts` draws nothing on a refusal rather than inverting FR-13.
 */
export type FormatCheckOutcome =
  | { readonly kind: 'report'; readonly report: FormatCheckReport }
  | { readonly kind: 'error'; readonly reason: string | null }
  | { readonly kind: 'unreachable' }

/**
 * Where one WebSocket ticket is minted (AD-5, NFR-01). Nothing to retry: waiting for a silent
 * backend belongs to `src/state/socket.ts`. The one `200` that carries a credential, so
 * {@link request}'s `no-store` is load-bearing here.
 */
export const SESSION_PATH = '/api/session'

/**
 * What one mint of `GET /api/session` came back with. `ticket` is good for exactly one upgrade
 * attempt. `error` is modelled although the backend declares no refusal: reaching it means
 * something else answered on the port. `unreachable` is the ordinary failure the loop is built for.
 */
export type SessionOutcome =
  | { readonly kind: 'ticket'; readonly ticket: string }
  | { readonly kind: 'error'; readonly reason: string | null }
  | { readonly kind: 'unreachable' }

/** The unauthenticated identity probe (FR-15, AD-4); read once per transition to `'live'`, never polled. */
export const HEALTH_PATH = '/health'

/** Where the socket lives. `ws.py` takes the ticket as a QUERY parameter: a browser cannot set handshake headers. */
export const WS_PATH = '/ws'

/**
 * The full socket URL for one ticket, built entirely from `window.location`. No port is named: the
 * SPA is served BY the companion (AD-13), so the page's authority already is the backend's. The
 * host SPELLING is derived too: `security.py`'s `origin_is_allowed` matches the handshake `Origin`
 * exactly against the two loopback spellings, and the browser derives `Origin` from the page, so a
 * spelling introduced here that the page did not have is one the check has never seen.
 */
export const agentSocketUrl = (ticket: string): string => {
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${scheme}//${window.location.host}${WS_PATH}?ticket=${encodeURIComponent(ticket)}`
}

/**
 * What the loop wants to be told about a socket: three plain callbacks, no DOM types, because the
 * door regex includes the socket constructor's name and a loop module holding one would be a
 * second network door. `message` is already narrowed: parsing the wire is this module's job.
 */
export interface AgentSocketHandlers {
  /** The upgrade succeeded. At most once per socket. */
  readonly onOpen: () => void
  /** One text frame arrived; `null` means it was not a frame this build can read (dropped, not swallowed). */
  readonly onMessage: (event: AgentEvent | null) => void
  /**
   * The socket ended, for ANY reason: `ws.py` makes the four browser outcomes indistinguishable by
   * design (every refusal is close code 1008, no body). May fire twice (`error` then `close`).
   */
  readonly onClose: () => void
}

/** What the caller holds after {@link openAgentSocket}: the ability to abandon the socket. */
export interface AgentSocketHandle {
  /** Idempotent from the caller's side: a second close on a closed socket is a platform no-op. */
  readonly close: () => void
}

/** The `reason` a body carries, or `null` if it carries none this code can read. */
const reasonOf = (body: unknown): string | null => {
  if (typeof body !== 'object' || body === null) return null
  // `in` rather than a cast: the value on the wire is untyped JSON and may be anything at all.
  if (!('reason' in body)) return null
  const reason: unknown = (body as Partial<ErrorResponse>).reason
  return typeof reason === 'string' ? reason : null
}

/**
 * The deck names out of a `200` body, or `null` if the body was not the promised array: "no
 * decks" would be a calm, wrong panel. Within a well-formed array a row without a non-blank string
 * `name` is DROPPED rather than failing the read (FR-13: one bad row must never take down a view).
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
 * The card out of a `200` body, or `null` if the body was not the promised record. Two fields of
 * a 42-field record: a full validator would be a hand-maintained copy of `openapi.json`, the drift
 * `wire-contract.test.ts` bans. A hole below `id` and `name` is the openapi drift gate's business.
 */
const cardOf = (body: unknown): Card | null => {
  if (typeof body !== 'object' || body === null) return null
  const record = body as Partial<Card>
  // Blank counts as absent: an id that cannot key the cache or a name that cannot label a tile.
  if (typeof record.id !== 'string' || record.id.trim() === '') return null
  if (typeof record.name !== 'string' || record.name.trim() === '') return null
  return body as Card
}

/**
 * The active deck id out of a `200` body, or `undefined` if the body was not the promised record.
 * Three-valued by necessity: `null` is a real answer on this route, and folding it into `undefined`
 * would report the ordinary post-restart cold open and a captive portal as the same thing. A blank
 * id reads as `null`: "there is no active deck" is the honest sentence for an unresolvable id.
 */
const activeDeckIdOf = (body: unknown): string | null | undefined => {
  if (typeof body !== 'object' || body === null) return undefined
  // `in` rather than a cast, for `reasonOf`'s reason: the value on the wire is untyped JSON.
  if (!('deck_id' in body)) return undefined
  const deckId: unknown = (body as Partial<ActiveDeck>).deck_id
  if (deckId === null) return null
  if (typeof deckId !== 'string') return undefined
  return deckId.trim() === '' ? null : deckId
}

/**
 * The deck out of a `200` body, or `null` if the body was not the promised record. `id` and
 * `name` for {@link cardOf}'s reason, plus `cards` because it is the WHOLE PRODUCT of this read:
 * a body without it would put a calm, empty, confidently-wrong decklist on the glass.
 */
const deckOf = (body: unknown): DeckDetail | null => {
  if (typeof body !== 'object' || body === null) return null
  const record = body as Partial<DeckDetail>
  // Blank counts as absent: an id that cannot be re-requested or a name that cannot fill the `h1`.
  if (typeof record.id !== 'string' || record.id.trim() === '') return null
  if (typeof record.name !== 'string' || record.name.trim() === '') return null
  if (!Array.isArray(record.cards)) return null
  return body as DeckDetail
}

/**
 * The format-check report out of a `200` body, or `null` if the body was not the promised record.
 * `rows` is the one field checked (the scalars are bound to nothing), and it must be a NON-EMPTY
 * array of objects. Empty: the six-rows-always contract means `{rows: []}` is never the promised
 * record, and accepting it drew a titled "Format check" over nothing. Objects: the container
 * dereferences `row.check` on every element during render with no error boundary above it, so one
 * `null` element would take down the whole deck view. Row FIELDS are not validated: an off-vocabulary
 * row renders degraded but standing, and the type-level totality asserts in `FormatCheck.tsx` are
 * the defence against a vocabulary change.
 */
const formatCheckOf = (body: unknown): FormatCheckReport | null => {
  if (typeof body !== 'object' || body === null) return null
  const record = body as Partial<FormatCheckReport>
  if (!Array.isArray(record.rows) || record.rows.length === 0) return null
  if (!record.rows.every((row) => typeof row === 'object' && row !== null)) return null
  return body as FormatCheckReport
}

/**
 * The six kinds this build knows, as a lookup; keys only. `satisfies Record<AgentEventKind, true>`
 * makes it a derivation: a seventh kind on the Python side fails `npm run typecheck` naming the
 * missing key, where a `readonly string[]` with `includes` would compile and drop the new kind.
 */
const AGENT_EVENT_KINDS = {
  suggestions: true,
  swaps: true,
  tier_list: true,
  groups: true,
  deck_changed: true,
  active_deck_changed: true,
} satisfies Record<AgentEventKind, true>

/**
 * One text frame's payload, narrowed to an {@link AgentEvent}, or `null` if it is not one. Only
 * `kind` is checked: the consumer is a `switch` over the discriminant, and the known set is
 * derived, so a new kind cannot be accepted here and fall off the end of that switch.
 * `Object.hasOwn` rather than `.includes`: a wire string is attacker-adjacent input and
 * `'__proto__'` indexes an inherited value. A non-string (binary frame) is a malformed frame.
 */
export const agentEventOf = (data: unknown): AgentEvent | null => {
  if (typeof data !== 'string') return null

  let body: unknown
  try {
    body = JSON.parse(data)
  } catch {
    return null
  }

  if (typeof body !== 'object' || body === null) return null
  if (!('kind' in body)) return null
  const kind: unknown = (body as Partial<AgentEvent>).kind
  if (typeof kind !== 'string' || !Object.hasOwn(AGENT_EVENT_KINDS, kind)) return null
  return body as AgentEvent
}

/** The ticket out of a `200` body, or `null`. A blank counts as absent: it is not a credential. */
const ticketOf = (body: unknown): string | null => {
  if (typeof body !== 'object' || body === null) return null
  // `in` rather than a cast, for `reasonOf`'s reason: the value on the wire is untyped JSON.
  if (!('ticket' in body)) return null
  const ticket: unknown = (body as Partial<SessionTicket>).ticket
  if (typeof ticket !== 'string' || ticket.trim() === '') return null
  return ticket
}

/**
 * The instance id out of a `200` body, or `null`. `status` is not checked (`schema.test.ts` pins
 * the `'ok'` literal at the type level). TRIMMED, not merely blank-checked: the id feeds
 * `applyInstanceId`'s equality guard, so a padded copy of the same id would read as a new backend.
 */
const instanceIdOf = (body: unknown): string | null => {
  if (typeof body !== 'object' || body === null) return null
  // `in` rather than a cast, for `reasonOf`'s reason: the value on the wire is untyped JSON.
  if (!('instance_id' in body)) return null
  const instanceId: unknown = (body as Partial<HealthResponse>).instance_id
  if (typeof instanceId !== 'string') return null
  const trimmed = instanceId.trim()
  return trimmed === '' ? null : trimmed
}

/** A response that ARRIVED: whether it was a 2xx, and whatever body could be read out of it. */
interface Received {
  readonly ok: boolean
  readonly body: unknown
}

/**
 * One signal that aborts when EITHER input does, or the one input that exists, or nothing (the
 * timeout is itself guarded in `request`). The manual arm mirrors `AbortSignal.any` where absent.
 */
const mergedSignal = (
  timeout: AbortSignal | undefined,
  caller: AbortSignal | undefined,
): AbortSignal | undefined => {
  if (timeout === undefined) return caller
  if (caller === undefined) return timeout
  if (typeof AbortSignal.any === 'function') return AbortSignal.any([timeout, caller])
  const controller = new AbortController()
  const follow = (signal: AbortSignal): void => {
    if (signal.aborted) controller.abort(signal.reason)
    else signal.addEventListener('abort', () => controller.abort(signal.reason), { once: true })
  }
  follow(timeout)
  follow(caller)
  return controller.signal
}

/**
 * Issue one request and read its body, or return `null` if nothing arrived. Never rejects.
 *
 * The one `fetch` in `ui/src`: the timeout guard below is subtle enough that a second copy would
 * be a second place to get it wrong. `cache: 'no-store'` on every route: the poll exists to observe
 * the backend CHANGE state (`deps.get_session` re-probes readiness on every request, FR-22), and a
 * card read wants determinism against the route's `Cache-Control: private, max-age=3600`.
 * `callerSignal` lets `readDeck`'s refetch path abort a superseded read; an abort is a rejection.
 */
const request = async (path: string, callerSignal?: AbortSignal): Promise<Received | null> => {
  // `AbortSignal.timeout` is inside the bundle's browser floor; the guard exists because the
  // constructor throwing INSIDE the `try` below would classify every read as `unreachable` before
  // `fetch` ever ran, a calm panel retrying forever. A floor miss degrades to NO timeout instead.
  const timeoutSignal =
    typeof AbortSignal.timeout === 'function' ? AbortSignal.timeout(READ_TIMEOUT_MS) : undefined
  // `AbortSignal.any` postdates `AbortSignal.timeout` in browsers (Chrome 116, Firefox 124, Safari
  // 17.4 against 103, 100, 15.4), so it is guarded for the same reason: a floor miss degrades.
  const signal = mergedSignal(timeoutSignal, callerSignal)

  let response: Response
  try {
    response = await fetch(path, {
      cache: 'no-store',
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch {
    return null
  }

  // `.json()` rejects on an empty body and on non-JSON, one layer earlier than a missing `reason`.
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }

  return { ok: response.ok, body }
}

/** Poll `GET /api/decks` once, and report what happened without ever throwing. */
export const readDecks = async (): Promise<DecksOutcome> => {
  const received = await request(DECKS_PATH)
  if (received === null) return { kind: 'unreachable' }

  if (!received.ok) return { kind: 'error', reason: reasonOf(received.body) }

  const decks = namesOf(received.body)
  // A contract violation has no token, so its reason is `null`.
  return decks === null ? { kind: 'error', reason: null } : { kind: 'decks', decks }
}

/**
 * Read one card's full record once, and report what happened without ever throwing. ONE request,
 * no retry, no dedupe: asking again is bounded one layer up by `MAX_ATTEMPTS_PER_CARD` in
 * `src/state/cards.ts`, and a retry here would be invisible to the cache that counts requests
 * (`cards.test.ts` counts them by counting calls). The route's own uuid pattern validates the id.
 */
export const readCard = async (cardId: string): Promise<CardOutcome> => {
  const received = await request(cardPath(cardId))
  if (received === null) return { kind: 'unreachable' }

  if (!received.ok) return { kind: 'error', reason: reasonOf(received.body) }

  const card = cardOf(received.body)
  // Caching a hollow object would put `undefined` where a name goes.
  return card === null ? { kind: 'error', reason: null } : { kind: 'card', card }
}

/**
 * Ask which deck the companion is displaying, once, and report what happened without throwing.
 * ONE request, no retry: this route holds no database, so its only refusals are a client bug
 * (`400`) and a backend bug (`500`), and neither becomes true by asking again.
 */
export const readActiveDeck = async (): Promise<ActiveDeckOutcome> => {
  const received = await request(ACTIVE_DECK_PATH)
  if (received === null) return { kind: 'unreachable' }

  if (!received.ok) return { kind: 'error', reason: reasonOf(received.body) }

  const deckId = activeDeckIdOf(received.body)
  // `undefined` is the sentinel and `null` is an ANSWER; see `activeDeckIdOf`.
  return deckId === undefined ? { kind: 'error', reason: null } : { kind: 'active-deck', deckId }
}

/**
 * Read one deck's full record once, and report what happened without ever throwing. ONE request,
 * no retry: this route carries a path parameter, so the header's argument applies in full, and
 * nothing loops here (`src/state/deck.ts` proves one request per mount with a request count). A
 * request may be ABANDONED, which is still not a retry: the `deck_changed` refetch passes `signal`
 * so a superseded read is aborted mid-flight, surfacing as the same total `{ kind: 'unreachable' }`
 * the caller's generation guard then discards. A deck id has no declared shape to validate.
 */
export const readDeck = async (deckId: string, signal?: AbortSignal): Promise<DeckOutcome> => {
  const received = await request(deckPath(deckId), signal)
  if (received === null) return { kind: 'unreachable' }

  if (!received.ok) return { kind: 'error', reason: reasonOf(received.body) }

  const deck = deckOf(received.body)
  return deck === null ? { kind: 'error', reason: null } : { kind: 'deck', deck }
}

/**
 * Check one deck against its own format, once, and report what happened without ever throwing.
 * ONE request, no retry: `readDeck`'s path-parameter argument transfers, and the panel this feeds
 * draws nothing when the read fails, so a retry would spend requests fixing a screen the user
 * cannot tell is broken. The cost is not the validation (median 5.2 ms over 40 real decks, against
 * NFR-05's 1 s) but a second `get_deck_with_cards` on top of the one the deck read already paid.
 * Measured, an unknown id and a malformed one both answer `404 deck_not_found`, never `400`.
 */
export const readFormatCheck = async (deckId: string): Promise<FormatCheckOutcome> => {
  const received = await request(formatCheckPath(deckId))
  if (received === null) return { kind: 'unreachable' }

  if (!received.ok) return { kind: 'error', reason: reasonOf(received.body) }

  const report = formatCheckOf(received.body)
  return report === null ? { kind: 'error', reason: null } : { kind: 'report', report }
}

/**
 * Mint one WebSocket ticket, and report what happened without ever throwing. ONE request, no
 * retry, and here it matters most: the ticket's TTL is 30 s (`state.py`) and the backoff's ceiling
 * is 30 s, so a mint that quietly waited before answering would hand the upgrade a ticket already
 * expiring at the one point with no slack. The loop's contract is `delay → mint → open`.
 */
export const readSessionTicket = async (): Promise<SessionOutcome> => {
  const received = await request(SESSION_PATH)
  if (received === null) return { kind: 'unreachable' }

  if (!received.ok) return { kind: 'error', reason: reasonOf(received.body) }

  const ticket = ticketOf(received.body)
  return ticket === null ? { kind: 'error', reason: null } : { kind: 'ticket', ticket }
}

/**
 * Read the backend's instance id once, and report it, or `null`, without ever throwing. ONE
 * request, no retry: the trigger is a transition to `'live'`, the best moment this route will ever
 * have. `null` collapses every failure because the consumer has one question (what id did the
 * backend just confirm?) and leaves the store untouched on failure. Health is unauthenticated
 * (AD-4: read BEFORE presenting a credential), so there is no token plumbing.
 */
export const readInstanceId = async (): Promise<string | null> => {
  const received = await request(HEALTH_PATH)
  if (received === null) return null

  if (!received.ok) return null

  return instanceIdOf(received.body)
}

/**
 * Open the agent socket for one ticket: the second network door, in the same file as the first.
 * ONE socket with ONE ticket; retrying, backing off and re-minting live one layer up, with the
 * thing that counts the tries. The handlers are wired before this function returns, so a handshake
 * refused fast on loopback cannot dispatch into an empty slot. The ticket is single-presentation:
 * `state.py` pops it on every consume attempt, so a re-used one gets a forged one's `1008`.
 */
export const openAgentSocket = (
  ticket: string,
  handlers: AgentSocketHandlers,
): AgentSocketHandle => {
  const socket = new WebSocket(agentSocketUrl(ticket))

  socket.onopen = () => handlers.onOpen()
  socket.onmessage = (event: MessageEvent<unknown>) => handlers.onMessage(agentEventOf(event.data))
  socket.onclose = () => handlers.onClose()
  socket.onerror = () => handlers.onClose()

  return {
    close: () => {
      // Detached BEFORE the close: `close()` dispatches a `close` event, so leaving `onclose`
      // attached would call back into a loop that has already decided this socket is over.
      socket.onopen = null
      socket.onmessage = null
      socket.onclose = null
      socket.onerror = null
      socket.close()
    },
  }
}
