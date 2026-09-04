/**
 * The one card cache, and the in-flight deduping around it (AD-12, FR-13).
 *
 * AD-12: *"Card hydration has one owner: a single card cache in the zustand store, keyed by card
 * ID, that dedupes in-flight requests."* Per-component fetching would fire duplicate requests on
 * every cursor sweep. The deck payload embeds the whole `Card` per row, so a deck view is seeded
 * from the boot's one request and {@link hydrateCard} serves only ids OUTSIDE the open deck. A
 * separate `create()`, because `useSystemStore` is subscribed selector-less in `App`. No
 * `useCard(id)` that fetches — N mounted tiles would become N request owners.
 *
 * FR-13: a card refusal never becomes a panel. `panelFor()` is not called here — it clamps
 * `card_not_found` to `'internal-error'`, so one missing card would replace a working deck view
 * with *"The companion hit a bug"*. `cards.test.ts` proves the panel is untouched by a 404. This
 * module fetches no images (the browser's HTTP cache owns art), no deck, and holds no timer.
 */

import { create } from 'zustand'

import { readCard, type CardOutcome } from '../api/client'
import type { Card, CardSummary, DeckCardSummary, ErrorReason } from '../api/schema'
import { PLACEHOLDER_FOR_REASON, type PlaceholderKey } from '../components/StatePanel/states'

/**
 * How many times one card id may be requested, ever, for the life of the tab.
 *
 * 3, from a measurement pinned in `test_routes_cards.py`: a malformed id sent to a backend with no
 * database answers `database_not_initialized` (FastAPI resolves dependencies before parameter
 * validation), so deciding retryability from the token ALONE retries forever. Counted per id and
 * cumulatively across calls. Not 1, because an import finishing between two hovers is ordinary; not
 * 10, because the worst case is 3 × 99 = 297 requests per deck view (99 tiles, the largest real deck).
 */
export const MAX_ATTEMPTS_PER_CARD = 3

/**
 * What the cache knows about one id. `undefined` — no entry at all — means **never seen**, and it
 * is the ONLY thing `undefined` means. A discriminated union rather than parallel maps, so "still
 * loading" and "unknown card" are two values and neither is inferred from an absence.
 */
export type CardEntry =
  /** A deck payload named it: renderable now, no request made. */
  | { readonly status: 'summary'; readonly summary: CardSummary }
  /** A read is in flight. `summary` is what was known before, so a drawable tile stays drawable. */
  | { readonly status: 'loading'; readonly summary: CardSummary | null }
  /** `GET /api/cards/{card_id}` answered. */
  | { readonly status: 'hydrated'; readonly card: Card }
  /**
   * A read was refused. `reason` is the wire token when this build recognises it, else `null`
   * (clamped HERE because everything downstream switches on `ErrorReason`). `placeholder` is the
   * non-panel destination, or `null` when *the read did not land and any `summary` still stands*.
   * `retryable` is recorded so no consumer re-implements the bound.
   */
  | {
      readonly status: 'unknown'
      readonly reason: ErrorReason | null
      readonly placeholder: PlaceholderKey | null
      readonly summary: CardSummary | null
      readonly retryable: boolean
    }

/**
 * Whether a refused card read could ever succeed if asked again — a total map over the token
 * union, so a new Python-side token fails typecheck NAMING the token. Not `RETRIES_QUIETLY`
 * itself: that map is keyed by `StateKey`, and reaching one means `panelFor`.
 */
const CARD_READ_IS_RETRYABLE = {
  // A card row is immutable between database refreshes (restart-scale events).
  card_not_found: false,
  // Failed the route's uuid pattern; will fail it identically forever.
  invalid_request: false,
  // Deterministic by wire contract.
  internal_error: false,
  // Agent-facing tokens (AD-5): the request was wrong, not the backend.
  forbidden: false,
  payload_too_large: false,
  // The deck routes' token; present to keep the map total.
  deck_not_found: false,
  // THE TWO THAT ARE ACTUALLY RETRYABLE: a first database build takes minutes and then flips to
  // `200` on its own (FR-22). The attempt bound stops "again" being forever.
  database_not_initialized: true,
  database_unavailable: true,
  // Image tokens, not published by the card route; an image failure says nothing about the ROW.
  no_image_data: false,
  image_fetch_failed: false,
} satisfies Record<ErrorReason, boolean>

/**
 * The named non-panel destination a REFUSED CARD READ has. `card_not_found` is read out of
 * `PLACEHOLDER_FOR_REASON` so the two cannot drift. `invalid_request` is deliberate: `states.ts`
 * classifies it `NO_UI_RESPONSE` on the premise that the SPA never sends a malformed request, but
 * this id came from `deck_cards`, a column with no shape constraint. Every other refusal has NO
 * placeholder: "Unknown card" over a tile whose name the payload supplied would be a lie.
 */
const PLACEHOLDER_FOR_CARD_REFUSAL = {
  card_not_found: PLACEHOLDER_FOR_REASON.card_not_found,
  invalid_request: 'unknown-card',
} satisfies Partial<Record<ErrorReason, PlaceholderKey>>

/** The cache itself: one entry per id ever seen. */
export interface CardCacheState {
  readonly cards: Readonly<Record<string, CardEntry>>
}

/** The state before anything is seeded or read. Exported so tests can restore it. */
export const INITIAL_CARD_CACHE: CardCacheState = { cards: {} }

/**
 * The one card cache, keyed by the Scryfall printing uuid — the identifier every card route
 * carries. A cache keyed by oracle id or name would serve the wrong art for a specified printing.
 */
export const useCardStore = create<CardCacheState>(() => INITIAL_CARD_CACHE)

/**
 * The read in flight for an id, shared by every caller that asks while it is running. Module
 * scope, not store state: a `Promise` is not state, and publishing one would re-render consumers.
 */
const inFlight = new Map<string, Promise<CardEntry>>()

/** How many requests each id has cost, ever — the cumulative half of {@link MAX_ATTEMPTS_PER_CARD}. */
const attempts = new Map<string, number>()

/**
 * Which lifetime of the cache a read belongs to. Bumped by {@link resetCardCache}, so a read in
 * flight across a reset does not `put()` its entry into the FRESH store.
 */
let generation = 0

/** Forget everything: entries, in-flight promises and attempt counts. For tests. */
export const resetCardCache = (): void => {
  useCardStore.setState(INITIAL_CARD_CACHE, true)
  inFlight.clear()
  attempts.clear()
  generation += 1
}

/**
 * Give every id its {@link MAX_ATTEMPTS_PER_CARD} back, and re-arm the entries the bound alone
 * made terminal. Called on reconnect, so a backend restarted mid-sweep leaves no permanent holes.
 * Not `resetCardCache()`: hydration is knowledge, the attempt count is a budget, and a restart
 * invalidates only the budget. `retryable` is recorded ON the entry, so the map alone is not
 * enough; never-succeeding tokens stay terminal. Writes only when something changed.
 */
export const resetCardAttempts = (): void => {
  if (attempts.size === 0) return
  attempts.clear()

  useCardStore.setState((state) => {
    const cards: Record<string, CardEntry> = { ...state.cards }
    let changed = false
    for (const [cardId, entry] of Object.entries(cards)) {
      if (entry.status !== 'unknown' || entry.retryable) continue
      // `null` — no token at all — is retryable: guessing "terminal" would permanently un-hydrate
      // a card because a proxy returned HTML once.
      if (entry.reason !== null && !CARD_READ_IS_RETRYABLE[entry.reason]) continue
      cards[cardId] = { ...entry, retryable: true }
      changed = true
    }
    return changed ? { cards } : state
  })
}

/** Whatever summary an existing entry carries, or `null`. `hydrated` needs none — it has the row. */
const summaryOf = (entry: CardEntry | undefined): CardSummary | null => {
  if (entry === undefined) return null
  if (entry.status === 'hydrated') return null
  return entry.summary
}

/** Replace one id's entry, leaving every other id's identity untouched. */
const put = (cardId: string, entry: CardEntry): void => {
  useCardStore.setState((state) => ({ cards: { ...state.cards, [cardId]: entry } }))
}

/**
 * Whether this build recognises a wire token — keyed on {@link CARD_READ_IS_RETRYABLE}'s own key
 * set. `Object.hasOwn`, because indexing a plain object with `'__proto__'` returns an inherited
 * value and a wire string is attacker-adjacent input.
 */
const knownReason = (reason: string | null): ErrorReason | null =>
  reason !== null && Object.hasOwn(CARD_READ_IS_RETRYABLE, reason) ? (reason as ErrorReason) : null

/** The placeholder map, widened for lookup — an assignment rather than a cast, so the shape is checked. */
const placeholders: Partial<Record<ErrorReason, PlaceholderKey>> = PLACEHOLDER_FOR_CARD_REFUSAL

/** Whether this id has spent its {@link MAX_ATTEMPTS_PER_CARD}. */
const spent = (cardId: string): boolean => (attempts.get(cardId) ?? 0) >= MAX_ATTEMPTS_PER_CARD

/**
 * Seed the cache from a deck payload. **Issues zero requests**: every row carries the WHOLE
 * `Card`. The payload's card always wins, hydrated entries included — it is the server's current
 * record, and keeping the old entry would freeze costs, faces and legalities at the first read. A
 * malformed row is skipped, since `deckOf` validates the envelope and not the rows. Keyed on
 * `card_id`, the FK the rest of the app addresses cards by; a card in both boards lands twice.
 */
export const seedDeckCards = (deckCards: readonly DeckCardSummary[]): void => {
  if (deckCards.length === 0) return

  useCardStore.setState((state) => {
    const cards: Record<string, CardEntry> = { ...state.cards }
    for (const deckCard of deckCards) {
      const cardId = deckCard?.card_id
      const card = deckCard?.card
      if (typeof cardId !== 'string' || cardId === '') continue
      if (typeof card !== 'object' || card === null) continue
      cards[cardId] = { status: 'hydrated', card }
    }
    return { cards }
  })
}

/**
 * What one finished read turns into. `retryable` is where the bound and the token meet, in ONE
 * decision, so the field a consumer sees and the gate {@link hydrateCard} enforces cannot disagree.
 */
const entryFor = (cardId: string, outcome: CardOutcome, summary: CardSummary | null): CardEntry => {
  if (outcome.kind === 'card') return { status: 'hydrated', card: outcome.card }

  // A network rejection and an unreadable body both mean "no answer, and it might work later".
  const reason = outcome.kind === 'unreachable' ? null : knownReason(outcome.reason)

  return {
    status: 'unknown',
    reason,
    placeholder: reason === null ? null : (placeholders[reason] ?? null),
    summary,
    // An unrecognised or absent token is retryable-by-the-token: the bound caps the cost, whereas
    // guessing "terminal" would permanently un-hydrate a card because a proxy returned HTML once.
    retryable: !spent(cardId) && (reason === null || CARD_READ_IS_RETRYABLE[reason]),
  }
}

/**
 * Ensure one card's full record is in the cache, making at most one request and sharing it.
 *
 * Returns without a request when the id is already `hydrated`, when a read is in flight (the
 * caller JOINS the same promise), or when the last refusal was terminal — `retryable: false`
 * carries both a never-succeeding token and a spent bound. No internal loop, timer or damping.
 *
 * Args:
 *   cardId: The Scryfall printing uuid.
 *   read: Injected for tests; production passes nothing. A mid-flight caller joins the FIRST
 *     caller's request whatever reader it passed.
 *
 * Returns:
 *   The entry the READ produced. Never rejects. A read orphaned by {@link resetCardCache} still
 *   resolves with its entry; a consumer that cares about CURRENT truth reads {@link useCardEntry}.
 */
export const hydrateCard = async (
  cardId: string,
  read: (id: string) => Promise<CardOutcome> = readCard,
): Promise<CardEntry> => {
  const existing = useCardStore.getState().cards[cardId]

  if (existing?.status === 'hydrated') return existing

  const joined = inFlight.get(cardId)
  if (joined !== undefined) return joined

  if (existing?.status === 'unknown' && !existing.retryable) return existing

  // Refused HERE with no request: `cardPath('')` is the bare collection path `/api/cards/` — a
  // DIFFERENT route, not a malformed parameter — so the uuid gate never sees it.
  if (cardId === '') {
    const refused: CardEntry = {
      status: 'unknown',
      reason: null,
      placeholder: 'unknown-card',
      summary: summaryOf(existing),
      retryable: false,
    }
    put(cardId, refused)
    return refused
  }

  const summary = summaryOf(existing)
  put(cardId, { status: 'loading', summary })
  // Counted BEFORE the request: a read that never settles must still cost an attempt.
  attempts.set(cardId, (attempts.get(cardId) ?? 0) + 1)

  const startedIn = generation

  const pending = (async (): Promise<CardEntry> => {
    let outcome: CardOutcome
    try {
      outcome = await read(cardId)
    } catch {
      // `readCard` is total and cannot reject; an injected reader might.
      outcome = { kind: 'unreachable' }
    }
    // Re-read at settle time, NOT the pre-flight capture: `seedDeckCards` may have landed while
    // the read was in flight, and writing the capture back would erase a name it supplied.
    const current = useCardStore.getState().cards[cardId]
    // A REFUSAL NEVER DISPLACES A HYDRATED ENTRY — otherwise the ordinary "hover, deck lands, 503
    // settles second" sequence blanks a drawable tile.
    if (current?.status === 'hydrated' && outcome.kind !== 'card') return current
    const entry = entryFor(cardId, outcome, summaryOf(current))
    // A read that settles after `resetCardCache` writes nothing: its store no longer exists.
    if (generation === startedIn) put(cardId, entry)
    return entry
  })()

  inFlight.set(cardId, pending)
  try {
    return await pending
  } finally {
    // Released on EVERY outcome, or the id could never be read again (the join above would return
    // a settled promise). Identity-checked so an orphan cannot delete a NEWER read for the id.
    if (inFlight.get(cardId) === pending) inFlight.delete(cardId)
  }
}

/**
 * Subscribe to one id's entry. **Starts nothing** — a pure selector a tile may call on every render
 * of a cursor sweep. Returns `undefined` only for an id never seen.
 */
export const useCardEntry = (cardId: string): CardEntry | undefined =>
  useCardStore((state) => state.cards[cardId])

/**
 * The same read, imperatively, for a caller that is not a component. An EXPORT rather than
 * `useCardStore.getState()` at the call site because `tests/store-writes.test.ts` decides who
 * writes a store by NAME PRESENCE (`setState` anywhere plus the store's name anywhere), so a module
 * that writes its OWN store and merely mentions `useCardStore` would read as a second writer.
 */
export const readCardEntry = (cardId: string): CardEntry | undefined =>
  useCardStore.getState().cards[cardId]
