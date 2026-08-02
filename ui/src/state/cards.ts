/**
 * The one card cache, and the in-flight deduping around it (story c4-1, AD-12, FR-13).
 *
 * AD-12, verbatim: *"Card hydration has one owner: a single card cache in the zustand store, keyed
 * by card ID, that dedupes in-flight requests. The detail panel updates on hover across a 100-tile
 * grid and every agent view hydrates its own thumbnails, so per-component fetching would fire
 * duplicate requests for the same card on every cursor sweep."* Note the second half: **Epic 6's
 * agent views are the other consumer**, which is why this is a store slice keyed by printing uuid
 * and not a structure hanging off a deck.
 *
 * This module ships **no pixels**. Its whole product is a cache and a request path that eleven
 * later stories consume without opening again: the grid is **c4-4**, the placeholders **c4-3**,
 * the detail panel **c4-5**, the deck bootstrap **c4-2**.
 *
 * ================= THE CACHE IS TWO-TIER, AND THE BULK TIER IS FREE =====================
 *
 * The story's title is slightly misleading and the measurement is why. `GET /api/deck/{deck_id}`
 * returns `DeckDetail`, whose `cards` is a list of `DeckCardSummary` — **each of which already
 * embeds a full `CardSummary`**: id, name, mana cost, cmc, type line, oracle text, colours,
 * rarity, set code. Measured at `61a787a` on the largest real deck on this machine ("Atraxa
 * Counter Cabinet v2 (owned)", 99 distinct tiles):
 *
 *   | the `CardSummary` fields for all 99 |  38,182 bytes |  **1** request (the deck detail) |
 *   | the full `Card` rows for all 99     | 212,436 bytes | **99** requests                  |
 *
 * 5.6× the bytes and 99× the requests. So **hydrating the grid is not this cache's job** —
 * {@link seedCardSummaries} takes the summaries the deck payload already carried and the app
 * never pays that cost. What `GET /api/cards/{card_id}` adds on top is power, toughness,
 * legalities, `card_faces`, `set_name` and `collector_number`, and that is fetched **per id, on
 * demand**, which is exactly what `EXPERIENCE.md`'s Card-detail row describes: *"name and cost are
 * known at hover time and render immediately, the rest fills in place — no spinner"*.
 *
 * ================= WHY THIS IS A SECOND `create()` AND STILL ONE CACHE ==================
 *
 * AC 1 demands exactly one card cache; AD-12 bans a second state LIBRARY. Neither says one
 * `create()` call, and putting the cache inside `useSystemStore` would be a measurable defect
 * rather than tidiness: `useSystemState` subscribes to that store **with no selector**, so every
 * hydration of every tile would re-render `App` and therefore the whole tree. On the 99-tile sweep
 * this module exists to make cheap, that is 99 whole-app renders traded for a shared module
 * variable. `systemState.ts`'s own header calls the card cache *"a new slice BESIDE this one"*,
 * and beside is what this is: one store instance, one cache, one owner, zero new libraries.
 *
 * ================= WHY THERE IS NO `useCard(id)` THAT FETCHES (Q3) =====================
 *
 * `useSystemState`'s docstring states the rule this module obeys: *"`App` is the ONE consumer, and
 * that is a rule, not an observation. Every mounted caller creates its OWN poller."* A
 * `useCard(id)` hook that fetched in an effect would be the same mistake in a new costume — N
 * mounted tiles becoming N request owners — and the deduping below would merely hide it, at the
 * cost of N effects, N subscriptions and N cleanup paths.
 *
 * So the split is: **{@link hydrateCard} is a plain function that owns the request**, callable
 * from an event handler, an effect or a loop; **{@link useCardEntry} is a pure selector hook that
 * starts nothing.** A tile that renders 99 times calls the selector 99 times and issues zero
 * requests.
 *
 * ================= WHAT THIS MODULE DELIBERATELY DOES NOT DO ===========================
 *
 * - **It does not fetch images.** Art reaches the screen through `<img src="/api/card-image/…">`
 *   and the browser's own HTTP cache, backed by `IMAGE_CACHE_CONTROL = "public, max-age=31536000,
 *   immutable"` and c3-7's sharded disk cache. There is no `fetch` for image bytes in this story,
 *   and `no_image_data` / `image_fetch_failed` can never be answered by `GET /api/cards/{card_id}`
 *   (they are not in its `error_responses`) — {@link CARD_READ_IS_RETRYABLE} records them anyway,
 *   because a total map over the token union is what makes an eleventh token a typecheck failure.
 * - **It does not fetch a deck.** {@link seedCardSummaries} takes deck cards as an ARGUMENT.
 * - **It does not put anything on the glass.** See the FR-13 section below.
 * - **It holds no timer and no retry loop.** See {@link MAX_ATTEMPTS_PER_CARD}.
 *
 * ================= FR-13: A CARD REFUSAL NEVER BECOMES A PANEL (AC 13) =================
 *
 * `panelFor()` is not called anywhere in this file, and that is a rule rather than an omission.
 * `card_not_found` maps to `null` in `PANEL_FOR_REASON`, and `panelFor` clamps `null` to
 * `'internal-error'` — so routing a card refusal through it would replace a working deck view with
 * *"The companion hit a bug. Restart the companion."* because one card was missing. That is the
 * FR-13 failure `states.ts:98-104` names outright (*"No banner, no apology"*). Nothing here writes
 * to `useSystemStore`, and `cards.test.ts` proves the system panel is untouched by a 404.
 */

import { create } from 'zustand'

import { readCard, type CardOutcome } from '../api/client'
import type { Card, CardSummary, DeckCardSummary, ErrorReason } from '../api/schema'
import { PLACEHOLDER_FOR_REASON, type PlaceholderKey } from '../components/StatePanel/states'

/**
 * How many times one card id may be requested, ever, for the life of the tab.
 *
 * **3, and the reason is a measurement rather than a taste.** Measured at c3-2 and pinned in
 * `test_routes_cards.py`: a malformed id sent to a backend with no database answers
 * `database_not_initialized`, **not** `invalid_request`, because FastAPI's `solve_dependencies`
 * runs dependencies before it collects parameter-validation errors. `database_not_initialized` is
 * a token `RETRIES_QUIETLY` says to retry quietly — so a client that decides retryability from
 * the token ALONE retries a request whose id can never succeed, forever. c3-9 wrote that warning
 * into three files (`client.ts`'s header, `ui/README.md` and `deferred-work.md`) precisely because
 * this is the story that would walk into it.
 *
 * The bound is what makes the loop terminate regardless of what the token says, so it is counted
 * **per id and cumulatively across calls**, not per call — a bound that reset on every render
 * would not be a bound, and "re-requested on every render" is the exact failure AC 11 bans.
 *
 * Why 3 and not 1: a genuinely transient refusal deserves more than one chance. `database.py`
 * holds a locked read for up to 5 s before answering, and an import that finishes between two
 * hovers is the ordinary case on a fresh install. Why 3 and not 10: on the sweep this module
 * exists for, the worst case a permanently-refusing backend can cost is 3 × 99 = **297 requests
 * per deck view** (99 tiles being the largest real deck, measured) — a number, rather than an
 * unbounded loop. The bound itself is per ID, not global: the id population is open-ended (Epic
 * 6's agent views hydrate arbitrary thumbnails, per this module's header), so 297 is the measured
 * deck-sweep case, not a ceiling on the tab. The user-visible recovery from a genuinely stalled
 * backend is the same one `poller.ts` already promises for the whole screen, and it is a reload.
 */
export const MAX_ATTEMPTS_PER_CARD = 3

/**
 * What the cache knows about one id. `undefined` — no entry at all — means **this id has never
 * been seen**, and it is the ONLY thing `undefined` means (AC 4).
 *
 * A discriminated union rather than parallel maps of cards / loading / errors, in the manner
 * `DecksOutcome` established and `panelFor` proved out. Three maps are three invariants that can
 * disagree, and the disagreement is invisible until a consumer reads two of them; one union is a
 * value the compiler can exhaust. In particular **"still loading" and "unknown card" are two
 * different values and neither is inferred from an absence**, which is the epic AC verbatim.
 */
export type CardEntry =
  /**
   * A deck payload named it. Name, mana cost and type line are renderable RIGHT NOW and no
   * request has been made — the free tier, and the one `EXPERIENCE.md`'s "no spinner" rests on.
   */
  | { readonly status: 'summary'; readonly summary: CardSummary }
  /**
   * A read is in flight. `summary` is whatever was known before it started, so a tile that was
   * already drawable stays drawable instead of flashing a skeleton (`EXPERIENCE.md`'s
   * skeleton-vs-placeholder policy: the rest fills in **place**).
   */
  | { readonly status: 'loading'; readonly summary: CardSummary | null }
  /**
   * `GET /api/cards/{card_id}` answered. Everything the corpus holds about the printing — to the
   * extent `cardOf` verified it, which is two fields; see that function's declared residue for
   * the (backend-bug-only) case of a `Card` with holes.
   */
  | { readonly status: 'hydrated'; readonly card: Card }
  /**
   * A read was refused, and this entry records which refusal.
   *
   * - `reason` — the token exactly as it crossed the wire when this build recognises it, else
   *   `null` (an unreadable body, an unknown token, or a network rejection). Unrecognised strings
   *   are clamped to `null` HERE rather than carried on, because everything downstream of this
   *   type switches on `ErrorReason` and a widened `string` would push that decision into every
   *   consumer.
   * - `placeholder` — the named non-panel destination from `states.ts`'s OWN vocabulary, or
   *   `null` when the refusal has none. `'unknown-card'` means *the app does not know what this
   *   card is*; `null` means *the read did not land and whatever `summary` exists still stands*.
   *   That distinction is what lets c4-3 draw the right thing without re-deriving it from tokens.
   * - `retryable` — whether a further {@link hydrateCard} call would issue another request. It is
   *   a value rather than a derivation so that a consumer never has to re-implement
   *   {@link CARD_READ_IS_RETRYABLE} and the attempt bound to answer "is anything still coming".
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
 * union, in the manner of `states.ts`'s four maps.
 *
 * `satisfies Record<ErrorReason, boolean>` rather than a list or a `switch`: an eleventh token
 * added on the Python side arrives through the generator and fails `npx tsc -b --force` **naming
 * the token**, which is how c3-2's seventh token and c3-4's eighth were both caught. A list would
 * silently default the new token to one answer or the other.
 *
 * This is NOT a second vocabulary (AC 14). The tokens are `ErrorReason`'s, unchanged; what is new
 * is one per-context decision over them, which is exactly the shape `states.ts` uses four times
 * over — `PANEL_FOR_REASON`, `PLACEHOLDER_FOR_REASON`, `NO_UI_RESPONSE`, `RETRIES_QUIETLY`. It is
 * NOT `RETRIES_QUIETLY` itself, because that map is keyed by `StateKey` and reaching a `StateKey`
 * from a token means `panelFor`, which AC 13 forbids on this path.
 */
const CARD_READ_IS_RETRYABLE = {
  // The card is not in the corpus. A card row is immutable between database refreshes, and a
  // refresh is a restart-scale event (`initialize_database` takes minutes, and `poller.ts`
  // already exists to notice the transition) — so this is a statement about local data, not a
  // transient failure. Q4: remembered for the life of the tab. Measured today: 0 dangling
  // references across 2,027 `deck_cards` rows, so the population an expiry would help is empty.
  card_not_found: false,
  // The id failed the route's uuid pattern. It will fail it identically forever. Q5.
  invalid_request: false,
  // Deterministic by wire contract — `types.d.ts` says the companion hit a bug, so re-issuing the
  // same request re-hits it. `RETRIES_QUIETLY['internal-error']` is `false` for the same reason.
  internal_error: false,
  // Agent-facing tokens. The browser never holds the agent token and never calls a route that
  // wants one (AD-5), so these arriving means the request was wrong, not the backend.
  forbidden: false,
  payload_too_large: false,
  // The deck routes' token. It cannot be answered by a card route; `false` is the safe reading
  // and the entry exists so the map stays total.
  deck_not_found: false,
  // THE TWO THAT ARE ACTUALLY RETRYABLE — and the two the c3-2 trap is about. A first
  // `initialize_database` build takes minutes and then flips to `200` on its own (FR-22), so an
  // id refused during it is worth asking about again. The attempt bound is what stops that
  // "again" from being forever when the 503 is really a 400 in disguise.
  database_not_initialized: true,
  database_unavailable: true,
  // Image tokens. `GET /api/cards/{card_id}` does not publish either (its `error_responses` is
  // `card_not_found` plus the app-wide set) — asserted against the committed `openapi.json` in
  // `tests/wire-contract.test.ts`, and asserted as behaviour in `cards.test.ts` in case one ever
  // arrives anyway. Present because the map is total; `false` because an image failure says
  // nothing about the card ROW.
  no_image_data: false,
  image_fetch_failed: false,
} satisfies Record<ErrorReason, boolean>

/**
 * The named non-panel destination a REFUSED CARD READ has — `states.ts`'s `PlaceholderKey`
 * vocabulary, applied to this one context.
 *
 * `card_not_found`'s value is READ OUT of `PLACEHOLDER_FOR_REASON` rather than re-typed, so the
 * two cannot drift: `states.ts` is where that pairing lives and this is a consumer of it.
 *
 * **`invalid_request` is the entry that is a ruling, and it is Q5's** (AC 15, ledgered on this
 * story at `deferred-work.md:2069`). `states.ts` classifies that token `NO_UI_RESPONSE` — *"the
 * SPA never generates a malformed request"* — and **that premise is exactly what fails here**:
 * the id came from `deck_cards`, a column with no shape constraint, on an async engine with FK
 * enforcement off, and the planned Arena `arena_card_map` work introduces ids from a second
 * source. One character of difference would otherwise decide between a placeholder and a silently
 * empty slot. **An id the app cannot render is an id the app cannot render, whichever token says
 * so**, so on THIS path it draws the unknown-card placeholder.
 *
 * That does not weaken `NO_UI_RESPONSE`: it stays correct for the whole-screen poll, where an
 * `invalid_request` really does mean a client bug with nothing to show. `states.ts` is untouched —
 * adding `invalid_request` to `PLACEHOLDER_FOR_REASON` would break
 * `ReasonClassificationsAreDisjoint`, and rightly, because the destination is context-dependent
 * rather than a property of the token.
 *
 * Every other refusal has NO placeholder, deliberately. A 503 does not mean "unknown card" — it
 * means the read did not land — and drawing "Unknown card" over a tile whose name the deck payload
 * already supplied would be a lie the summary tier can disprove.
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
 * The one card cache (AC 1), keyed by the **Scryfall printing uuid** — the same identifier
 * `deck_cards.card_id`, `GET /api/cards/{card_id}` and `GET /api/card-image/{scryfall_id}` all
 * carry, and the spine's *"Card identity is the Scryfall printing UUID, everywhere, always"*.
 *
 * A second cache keyed by oracle id or by name is the failure AC 1 exists to prevent: the corpus
 * holds 38,261 printings and multiple printings share an oracle id, so a name- or oracle-keyed
 * cache would serve the wrong art and the wrong set code for a deck that specifies a printing.
 */
export const useCardStore = create<CardCacheState>(() => INITIAL_CARD_CACHE)

/**
 * The read in flight for an id, shared by every caller that asks while it is running (AC 7).
 *
 * Module scope rather than store state, and the distinction is not a technicality: a `Promise` is
 * not state — nothing renders it, nothing may subscribe to it, and putting it in the store would
 * publish a value whose identity changes on every request into every consumer's re-render
 * calculation. The store holds what is KNOWN; this holds what is HAPPENING.
 *
 * **The promise is shared, not the result copied** (AC 7). Two callers get the same object, so
 * there is exactly one request and exactly one place it can be released from.
 */
const inFlight = new Map<string, Promise<CardEntry>>()

/**
 * How many requests each id has cost, ever. The cumulative half of {@link MAX_ATTEMPTS_PER_CARD}
 * — see that constant for why "cumulative" is the load-bearing word.
 */
const attempts = new Map<string, number>()

/**
 * Which lifetime of the cache a read belongs to. Incremented by {@link resetCardCache}, so a read
 * that was in flight when the world was thrown away can tell, at settle time, that its store no
 * longer exists — clearing `inFlight` cannot cancel an already-running continuation, and without
 * this check the orphan would `put()` its entry into the FRESH store (cross-test contamination
 * today; a real bug the moment reset is reused for a deck switch).
 */
let generation = 0

/**
 * Forget everything: the entries, the in-flight promises and the attempt counts.
 *
 * For tests. The module-scope maps outlive a `useCardStore.setState` reset, so a suite that
 * restored only the store would carry an exhausted attempt count into the next test and watch a
 * request silently not happen. All three are cleared together for exactly that reason — and the
 * {@link generation} bump is what handles the one thing clearing cannot: a read still in flight,
 * whose settle-time write must land nowhere.
 */
export const resetCardCache = (): void => {
  useCardStore.setState(INITIAL_CARD_CACHE, true)
  inFlight.clear()
  attempts.clear()
  generation += 1
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
 * Whether this build recognises a wire token.
 *
 * Keyed on {@link CARD_READ_IS_RETRYABLE}'s own key set, which `satisfies Record<ErrorReason, …>`
 * makes exactly `ErrorReason` at compile time — so an eleventh token cannot join the union without
 * appearing here. `Object.hasOwn` rather than a truthiness check for the reason `panel.ts` gives:
 * indexing a plain object with `'__proto__'` or `'constructor'` returns an inherited value, and a
 * wire string is attacker-adjacent input by construction.
 */
const knownReason = (reason: string | null): ErrorReason | null =>
  reason !== null && Object.hasOwn(CARD_READ_IS_RETRYABLE, reason) ? (reason as ErrorReason) : null

/**
 * The placeholder map, widened for lookup.
 *
 * An assignment rather than a cast, so the compiler still checks the shape; the `satisfies` on
 * the constant itself is what catches a key that is not a token, and this alias is only how a
 * narrowed `ErrorReason` indexes a `Partial`.
 */
const placeholders: Partial<Record<ErrorReason, PlaceholderKey>> = PLACEHOLDER_FOR_CARD_REFUSAL

/** Whether this id has spent its {@link MAX_ATTEMPTS_PER_CARD}. */
const spent = (cardId: string): boolean => (attempts.get(cardId) ?? 0) >= MAX_ATTEMPTS_PER_CARD

/**
 * Seed the summary tier from a deck payload (AC 5). **Issues zero requests.**
 *
 * This is the mechanism that makes the 5.6× / 99-request cost in this module's header a cost the
 * app never pays: the summaries already arrived, embedded in the one `GET /api/deck/{deck_id}`
 * that **c4-2** makes, so handing them here is free. c4-2 calls this; c4-1 ships and tests it.
 *
 * **An existing id's hydration tier is left untouched** — a `hydrated` entry stays hydrated, a
 * `loading` entry stays loading, an `unknown` entry stays unknown. Only the carried summary is
 * refreshed. Downgrading a hydrated card to a summary because its deck was re-read would throw
 * away a request that has already been paid for, and re-arming an `unknown` would defeat AC 11's
 * "not re-requested on every render" the moment a deck refetch happened on a timer.
 *
 * Args:
 *   deckCards: The `cards` array of a `DeckDetail`, verbatim. Keyed on `card_id` — the deck row's
 *     own column — rather than on the nested `card.id`, because `card_id` is the FK the rest of
 *     the app addresses cards by. A duplicate id (a card in both boards) simply lands twice.
 */
export const seedCardSummaries = (deckCards: readonly DeckCardSummary[]): void => {
  if (deckCards.length === 0) return

  useCardStore.setState((state) => {
    const cards: Record<string, CardEntry> = { ...state.cards }
    for (const deckCard of deckCards) {
      const existing = cards[deckCard.card_id]
      const summary = deckCard.card

      if (existing === undefined || existing.status === 'summary') {
        cards[deckCard.card_id] = { status: 'summary', summary }
        continue
      }
      if (existing.status === 'hydrated') continue
      cards[deckCard.card_id] = { ...existing, summary }
    }
    return { cards }
  })
}

/**
 * What one finished read turns into, given the id and what was already known about it.
 *
 * **`retryable` is where the attempt bound and the token meet, and it is ONE decision rather than
 * two.** `spent(cardId)` is read here and nowhere else that matters, so the field a consumer sees
 * and the gate {@link hydrateCard} enforces cannot disagree — the field *is* the gate's answer,
 * recorded. An entry that says `retryable: true` will genuinely be re-read on the next call; one
 * that says `false` never will be, whether because the token can never succeed or because the id
 * has spent its three attempts.
 */
const entryFor = (cardId: string, outcome: CardOutcome, summary: CardSummary | null): CardEntry => {
  if (outcome.kind === 'card') return { status: 'hydrated', card: outcome.card }

  // A network rejection carries no token at all, which is NOT the same as a refusal with an
  // unreadable body — but the two produce the same entry, because from a consumer's side both
  // mean "no answer, and it might work later". `poller.ts` keeps them apart because one of them
  // decides a panel; nothing here decides a panel (AC 13), so nothing here needs the difference.
  const reason = outcome.kind === 'unreachable' ? null : knownReason(outcome.reason)

  return {
    status: 'unknown',
    reason,
    placeholder: reason === null ? null : (placeholders[reason] ?? null),
    summary,
    // An unrecognised token or no token at all is treated as retryable-by-the-token, and that is
    // the safe direction: the bound caps the cost either way, whereas guessing "terminal" would
    // permanently un-hydrate a card because a proxy returned HTML once.
    retryable: !spent(cardId) && (reason === null || CARD_READ_IS_RETRYABLE[reason]),
  }
}

/**
 * Ensure one card's full record is in the cache, making at most one request and sharing it.
 *
 * The three ways this returns without issuing a request, which together are AC 8, AC 7, AC 11 and
 * AC 12:
 *
 *   1. The id is already `hydrated` — nothing to fetch (AC 8).
 *   2. A read for the id is already in flight — the CALLER JOINS IT (AC 7). One request, both
 *      callers, the same promise object.
 *   3. The id's last refusal was terminal (`retryable: false`). That single flag carries **both**
 *      reasons an id can be terminal — a token that can never succeed (`card_not_found`,
 *      remembered for the life of the tab by Q4; AC 11) and an id that has spent
 *      {@link MAX_ATTEMPTS_PER_CARD} attempts against a token that says "retry quietly"
 *      (AC 12) — because {@link entryFor} computes it from both. One gate, one predicate: a
 *      separate attempt check here would be a second copy of the same invariant, free to drift
 *      from the value consumers read.
 *
 * There is **no internal loop and no timer**: this function issues at most one request per call,
 * and the "loop" AC 12 bounds is the caller's — a component re-rendering, a cursor sweeping. That
 * is the honest shape for a cache whose consumers are renders, and it is why Q6 re-homed the
 * backoff-damping question to c5-6 rather than copying `poller.ts`'s schedule into a per-id path.
 *
 * Args:
 *   cardId: The Scryfall printing uuid.
 *   read: Injected so tests need no global `fetch` stub, exactly as `createPoller`'s `read?:`
 *     option is. **Production passes nothing.** A second caller arriving while a read is in flight
 *     joins the FIRST caller's request whatever reader it passed — one request is the contract.
 *
 * Returns:
 *   The entry the READ produced. Never rejects: every outcome of `readCard` is a value, and an
 *   injected reader that throws is caught and read as unreachable. One declared residue
 *   (Greptile PR #40, P2): a read that {@link resetCardCache} orphans still resolves with the
 *   entry it computed, even though the store discarded that world — the honest alternative,
 *   widening the return to `CardEntry | undefined`, would tax every consumer with an
 *   undefined-check for a case only resets produce, and resets are test-only today. The store is
 *   the authority: a consumer that cares about CURRENT truth reads {@link useCardEntry}, and the
 *   c4-2 `deck_changed` reset design inherits this question (see deferred-work.md).
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

  // The empty id is refused HERE, with no request, and it is a route-shape fact rather than a
  // validation opinion: `cardPath('')` is the bare collection path `/api/cards/` — a DIFFERENT
  // route, not a malformed parameter — so the uuid gate that answers every other hostile id
  // never gets to see this one. Q5's ruling applied one layer earlier: an id the app cannot
  // render is an id the app cannot render. `reason` is `null` because no wire token was (or
  // could be) received; `retryable: false` because an empty string stays empty forever.
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
  // Counted BEFORE the request, not after: a read that never settles must still have cost an
  // attempt, or a wedged backend would leave the bound un-spent forever.
  attempts.set(cardId, (attempts.get(cardId) ?? 0) + 1)

  const startedIn = generation

  const pending = (async (): Promise<CardEntry> => {
    let outcome: CardOutcome
    try {
      outcome = await read(cardId)
    } catch {
      // `readCard` is total and cannot reject; an injected reader might. Swallowing it here is
      // what keeps the "never rejects" contract true for every caller of this function.
      outcome = { kind: 'unreachable' }
    }
    // The summary is re-read at settle time, NOT the capture from before the request:
    // `seedCardSummaries` may have landed while the read was in flight (c4-2's deck fetch
    // overlapping a hover is the ordinary case), and it updates the `loading` entry's summary.
    // Writing the pre-flight capture back would erase a name the deck payload already supplied —
    // a tile that was drawable going blank because a 503 settled second.
    const entry = entryFor(cardId, outcome, summaryOf(useCardStore.getState().cards[cardId]))
    // A read that settles after `resetCardCache` writes nothing: the store it started against no
    // longer exists, and resurrecting its entry would contaminate whatever replaced it.
    if (generation === startedIn) put(cardId, entry)
    return entry
  })()

  inFlight.set(cardId, pending)
  try {
    return await pending
  } finally {
    // AC 10: released on EVERY outcome — success, refusal and rejection alike. A permanently
    // pending entry after a failed read is invisible to any success-path test and turns one bad
    // request into an id that can never be read again, because case 2 above would join a promise
    // that has already settled and no further request would ever be made. Identity-checked so an
    // orphan settling after a reset cannot delete a NEWER in-flight read for the same id.
    if (inFlight.get(cardId) === pending) inFlight.delete(cardId)
  }
}

/**
 * Subscribe to one id's entry. **Starts nothing** (Q3).
 *
 * A pure selector: no effect, no request, no cleanup. A tile may call this on every render of
 * every frame of a cursor sweep and the cost is a store read. Whoever decides that a full record
 * is actually needed — a hover handler, a detail panel opening — calls {@link hydrateCard}.
 *
 * Args:
 *   cardId: The Scryfall printing uuid.
 *
 * Returns:
 *   The entry, or `undefined` if this id has never been seen (AC 4: that is the ONLY meaning of
 *   `undefined`; "still loading" and "unknown card" are values).
 */
export const useCardEntry = (cardId: string): CardEntry | undefined =>
  useCardStore((state) => state.cards[cardId])
