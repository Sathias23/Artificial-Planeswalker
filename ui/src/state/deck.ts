/**
 * The deck the companion is showing: the boot that finds it, and the rule that decides whether
 * it or a system panel is on the glass (story c4-2, FR-07, FR-11, AD-12, AD-16).
 *
 * This is the first story in which a **deck** exists in the client, and it is therefore the first
 * that has to answer a question nine stories deferred: *when a deck and a system state are both
 * true, which one is on the glass?* {@link surfaceOf} is that answer, and it is deliberately ONE
 * exported expression rather than a ternary in `App.tsx` — a second copy of a precedence rule is
 * what lets **c4-4**'s grid and **c4-7**'s deck list disagree, which is the epic's own
 * *"the grid and the list panel cannot disagree"* clause read one level up.
 *
 * ================= THE BOOT IS TWO REQUESTS, AND THEY FAIL DIFFERENTLY =================
 *
 * `GET /api/active-deck` first; then, on a non-null id, `GET /api/deck/{deck_id}`. Two requests,
 * in that order, **on mount** — not on a timer, not per component. The asymmetry that shapes the
 * code is in `client.ts`'s header: the first route publishes `200/400/500` and structurally
 * cannot answer `503`, because it holds no `DbSession` at all. So the epic's database-refusal
 * criteria are about the SECOND request, and both requests get their own outcome union.
 *
 * **`deck_id: null` is the ordinary answer, not a failure.** The active-deck slot lives in the
 * backend's memory and dies with the process (FR-07), so a cold open after any restart reports
 * `null` whatever was displayed before.
 *
 * ================= A DECK REFUSAL BECOMES A PANEL. A CARD REFUSAL NEVER DOES ===========
 *
 * c4-1 AC 13 forbade `panelFor()` on the card path, and a reader arriving here holding that rule
 * will think this file breaks it. It does not, and the difference is worth stating where it will
 * be looked for rather than reconstructed:
 *
 *   **A card** is one tile in a working view. `card_not_found` maps to `null` in
 *   `PANEL_FOR_REASON` and `panelFor` clamps `null` to `'internal-error'`, so routing a card
 *   refusal through it would replace a whole working deck view with *"The companion hit a bug"*
 *   because one card was missing — the FR-13 failure `states.ts` bans outright.
 *
 *   **A deck** IS the view. There is nothing left standing to protect, every deck token has an
 *   honest panel, and `PANEL_FOR_REASON` has held the mapping since c2-9 with its reason written
 *   down: *"A deck deleted between a push and a refetch (FR-11) is not an error state of its own
 *   — the honest thing on screen is 'there is no active deck'."*
 *
 * **This story is that entry's FIRST LIVE PRODUCER.** `PANEL_FOR_REASON.deck_not_found` has been
 * unreachable dead code since it was written: `panelFor` is called only by `poller.ts`, which
 * reads only `GET /api/decks` — a route that does not publish `deck_not_found` (verified in
 * `openapi.json`: `200/400/413/500/503`). So the map is CONSUMED here, not paraphrased.
 *
 * ================= WHAT WRITES THIS SLICE, AND WHAT MAY NEVER (AD-12, AC 18) ===========
 *
 * The spine, verbatim: *"its state comes from exactly two inputs — REST responses and WebSocket
 * messages. Nothing else may write the store."* Today that means {@link createDeckBoot}'s two
 * REST answers and nothing else — no component setter, no `localStorage`, no URL parsing, no
 * derived value written back in. Epic 5's `deck_changed` message is the second input and it does
 * not exist yet. `tests/store-writes.test.ts` asserts the rule rather than trusting this
 * paragraph.
 *
 * ================= WHAT THIS STORY DELIBERATELY DOES NOT DO ============================
 *
 * - **No timer, no poll of its own — one boot per mount, plus one EDGE-TRIGGERED re-drive per
 *   poll recovery.** The review found the boot's original one-shot posture let a refusal panel
 *   outlive the condition it reported: a cold open during a DB build settles
 *   `{status:'refused'}`, and when the build finished the poll recovered while the glass stayed
 *   on the stale 503 panel — an FR-22 regression. So {@link useDeckState} re-drives the boot
 *   when the poll transitions INTO a healthy `no-active-deck` while the deck state is
 *   `'refused'` or `'none'` — never while `'deck'` (a loaded deck stays; Epic 5 owns switching)
 *   and never on a timer. The bound Q6 asked for is structural: one re-drive per recovery EDGE,
 *   and edges are backend-state transitions, not a loop the client can wind. A deck the agent
 *   sets while the tab is open and the poll HEALTHY still waits for Epic 5's `deck_changed` —
 *   that half of the residue stands, with its named home. So does a narrower one: a transient
 *   blip on a boot request AFTER the poll has already stopped has no later edge to heal it, and
 *   persists until reload or c5-6's reconnect.
 * - **No render.** The grid is **c4-4**, the placeholders **c4-3**, the detail panel **c4-5**,
 *   the deck list and its group headers **c4-7**, the curve **c4-8**, the format check **c4-10**,
 *   the empty-deck state **c4-12**. {@link DeckBoards} ships declared and unread by this story's
 *   own render, exactly as c4-1's cache did.
 * - **No cache reset.** `resetCardCache()` on a deck transition was homed here on the theory that
 *   this story owns a `deck_changed` transition; measured, it does not — see Q7's ruling in the
 *   story record, which re-homes it and the orphaned-return question to **c5-4 / c5-6** by name.
 */

import { useEffect } from 'react'
import { create } from 'zustand'

import {
  readActiveDeck as readActiveDeckRoute,
  readDeck as readDeckRoute,
  type ActiveDeckOutcome,
  type DeckOutcome,
} from '../api/client'
import type { DeckDetail, ErrorReason } from '../api/schema'
import type { StateKey } from '../components/StatePanel/copy'
import { PANEL_FOR_REASON } from '../components/StatePanel/states'
import { boardsOfDeck, type DeckBoards } from './deckGroups'
import { panelFor } from './panel'
import { seedCardSummaries } from './cards'
import { subscribeSystemState, type SystemState } from './systemState'

/**
 * What the client knows about the active deck. A discriminated union, in the manner
 * `DecksOutcome` and `CardEntry` established — so no consumer infers a condition from
 * `undefined` and the compiler can exhaust it (Q2).
 *
 * The alternative — `deck: DeckDetail | null` plus a separate `error` field — is two invariants
 * that can disagree, and the disagreement is invisible until a consumer reads both.
 */
export type DeckState =
  /**
   * The boot has not answered yet. A real state a cold open occupies for one paint, and
   * DISTINCT from `'none'`: "we have not asked" and "there is no deck" are different facts, and
   * only one of them is worth putting on the glass. Both defer to the system panel today, which
   * is what keeps the first frame calm (c3-9's `INITIAL_SYSTEM_STATE` reasoning).
   */
  | { readonly status: 'booting' }
  /**
   * **No deck is on the glass, and no deck-specific panel is claimed** — the system state is the
   * authority. Three inputs reach it, and they are three genuinely different facts that produce
   * the same honest screen:
   *
   *   1. `deck_id: null` — the ordinary post-restart cold open (FR-07).
   *   2. A refusal whose panel IS `'no-active-deck'` — `deck_not_found` (FR-11's *"a 404 clears"*)
   *      and, by Q5's ruling, `invalid_request`.
   *   3. `unreachable` — no response arrived, so nothing was decided. `poller.ts`'s posture
   *      exactly: claiming `internal-error` here would say *"The companion hit a bug"* about a
   *      backend that is merely absent, and the panel that describes an absent backend
   *      (`disconnected`) is **c5-6's** by `CLIENT_ONLY_STATES`.
   */
  | { readonly status: 'none' }
  /** A deck loaded. `boards` is derived ONCE, here, at write time — see `deckGroups.ts`. */
  | { readonly status: 'deck'; readonly detail: DeckDetail; readonly boards: DeckBoards }
  /**
   * A read was refused and the refusal has a panel of its own — both database `503`s, a `500`,
   * or a body that is not the contract. `reason` is the token when this build recognises it,
   * clamped to `null` otherwise for `CardEntry`'s reason: everything downstream switches on
   * `ErrorReason`, and a widened `string` would push that decision into every consumer.
   */
  | { readonly status: 'refused'; readonly reason: ErrorReason | null; readonly panel: StateKey }

/** The state before the boot answers. Exported so tests can restore it between renders. */
export const INITIAL_DECK_STATE: DeckState = { status: 'booting' }

/**
 * The slice, holding the union **under a key** rather than as the store's own shape.
 *
 * **A probe found the reason, and it is not stylistic.** zustand's `setState` MERGES by default,
 * so a store whose shape IS `DeckState` accepts `setState({ status: 'none' })` and keeps the
 * `detail` of the deck that was there a moment ago — a `'none'` state carrying a ghost deck, in a
 * store every consumer narrows on `status`. The obvious guard is the replace flag
 * (`setState(next, true)`) at every call site, and the probe that deleted it stayed GREEN,
 * because the test was driving its own `onUpdate` rather than the production one — this epic's
 * standing finding (*the wiring is right and nothing asserts the wiring*) in a new costume.
 *
 * Wrapping the union in `{ deck }` makes the whole failure impossible instead of guarded: a merge
 * of one key replaces that key's value wholesale, so no member's fields can outlive it and no
 * call site has a flag to forget. A guard nobody can bypass beats a guard nobody remembers.
 */
export interface DeckSlice {
  readonly deck: DeckState
}

export const useDeckStore = create<DeckSlice>(() => ({ deck: INITIAL_DECK_STATE }))

/** The ONE writer (AD-12, AC 18). Every input to this slice goes through here. */
const applyDeckState = (deck: DeckState): void => useDeckStore.setState({ deck })

/**
 * Forget the deck. **For tests** — the module holds no other lifetime to reset.
 *
 * Not a production `deck_changed` handler: that transition is Epic 5's and this story does not
 * have it (Q7).
 */
export const resetDeckState = (): void => {
  applyDeckState(INITIAL_DECK_STATE)
}

/**
 * The panel a DECK refusal draws, where that differs from `PANEL_FOR_REASON`'s answer (Q5, AC 11).
 *
 * A per-context map beside its consumer, `states.ts` untouched — the identical shape c4-1's Q5
 * ruled for card reads (`PLACEHOLDER_FOR_CARD_REFUSAL`), and for the identical reason: a token's
 * UI destination can be context-dependent without the token's own classification being wrong.
 *
 * **`invalid_request` is the whole map, and it is a ruling.** `states.ts` classifies that token
 * `NO_UI_RESPONSE` — *"The SPA never generates a malformed request, so this token means a client
 * bug or a stray caller on the port"* — and **that premise is exactly what fails on this route**.
 * The id in the path did not come from the SPA. It came from `PUT /api/active-deck`, whose
 * `ActiveDeckRequest` accepts **any non-blank string of up to 256 characters, stores it verbatim,
 * and deliberately does not check that the deck exists**. An agent typo is therefore a perfectly
 * ordinary way to reach this token, and letting it fall through to `panelFor` would put *"The
 * companion hit a bug. Restart the companion."* on screen for one. An id the app cannot resolve
 * is an id the app cannot resolve, whichever token says so, and *"there is no active deck"* is
 * the true sentence.
 *
 * That does not weaken `NO_UI_RESPONSE`: it stays correct for the whole-screen poll, where
 * `/api/decks` carries no id and an `invalid_request` really does mean a client bug with nothing
 * to show. `states.ts` is untouched deliberately — adding `invalid_request` to
 * `PLACEHOLDER_FOR_REASON` or to `PANEL_FOR_REASON` would break
 * `ReasonClassificationsAreDisjoint`, *and rightly*, because the destination is a property of the
 * context and not of the token.
 *
 * Every other token is `panelFor`'s call, unmodified — which is the point of the map being
 * `Partial` and one entry long rather than a second `switch` over the vocabulary.
 */
const PANEL_FOR_DECK_REFUSAL = {
  invalid_request: 'no-active-deck',
} satisfies Partial<Record<ErrorReason, StateKey>>

/** Whether this build recognises a wire token. `PANEL_FOR_REASON`'s own key set — see `panel.ts`. */
const knownReason = (reason: string | null): ErrorReason | null =>
  reason !== null && Object.hasOwn(PANEL_FOR_REASON, reason) ? (reason as ErrorReason) : null

/** The overrides, widened for lookup — an assignment rather than a cast, as `cards.ts` does. */
const deckPanels: Partial<Record<ErrorReason, StateKey>> = PANEL_FOR_DECK_REFUSAL

/**
 * The panel a refused DECK read puts on the glass: the per-context override, else `panelFor`.
 *
 * `Object.hasOwn` is inside {@link knownReason}; the lookup below is on an already-narrowed
 * token, so `'__proto__'` cannot reach it.
 */
const deckPanelFor = (reason: string | null): StateKey => {
  const known = knownReason(reason)
  return (known === null ? undefined : deckPanels[known]) ?? panelFor(reason)
}

/**
 * What a refusal turns into: `'none'` when the honest panel is *"there is no active deck"*,
 * `'refused'` otherwise.
 *
 * The `'no-active-deck'` answer is the CLEARING signal, and reading it out of the map is what
 * makes AC 8 a consumption of `PANEL_FOR_REASON` rather than a paraphrase of it.
 */
const stateForPanel = (panel: StateKey, reason: string | null): DeckState =>
  panel === 'no-active-deck'
    ? { status: 'none' }
    : { status: 'refused', reason: knownReason(reason), panel }

/**
 * A refusal on the DECK read (`GET /api/deck/{deck_id}`): the per-context override, else
 * `panelFor`. Note the honest consequence of a `404` clearing, recorded rather than fixed:
 * after a `404` the backend still reports that deck id as active, so the NEXT boot (a reload,
 * or a remount) asks for it again and clears again. That is one wasted request per cold open
 * against a deleted deck, it is self-correcting the moment the agent sets another deck, and the
 * alternative — the client telling the backend to forget an id — is a `PUT` this story has no
 * mandate to make.
 */
const deckRefusalState = (reason: string | null): DeckState =>
  stateForPanel(deckPanelFor(reason), reason)

/**
 * A refusal on the ACTIVE-DECK read (`GET /api/active-deck`): `panelFor`, with **no override**.
 *
 * The Q5 override does not apply here, and applying it was a review finding, not a nuance: its
 * entire justification is *"the id in the path came from `PUT /api/active-deck`"*, and this
 * route carries NO path parameter. A `400 invalid_request` from it is therefore exactly the
 * case `states.ts` classifies — a client bug or a stray caller on the port — and folding it to
 * a calm `'none'` would render a real bug as *"there is no active deck"*. `panelFor` clamps it
 * to `'internal-error'`, which is the honest panel; the test on this route says the same.
 */
const activeRefusalState = (reason: string | null): DeckState =>
  stateForPanel(panelFor(reason), reason)

/** What one settled boot decided. Exported for the tests that drive the sequence directly. */
export interface DeckBoot {
  /**
   * Runs the two-request sequence once per `start()`/`stop()` cycle. Idempotent while running
   * AND after settling — `live` is never cleared by completion, so a settled boot re-runs only
   * via `stop()` then `start()`, which is exactly how the recovery re-drive uses it.
   */
  start: () => void
  /** Abandons the sequence: nothing it has in flight may write after this. Idempotent. */
  stop: () => void
}

export interface DeckBootOptions {
  /** Emitted once per state the boot decides. */
  readonly onUpdate: (state: DeckState) => void
  /** Injected so tests need no global `fetch` stub, exactly as `createPoller`'s `read?:` is. */
  readonly readActive?: () => Promise<ActiveDeckOutcome>
  /** Likewise. **Production passes neither.** */
  readonly readDetail?: (deckId: string) => Promise<DeckOutcome>
}

/**
 * Build the boot. Nothing happens until `start()`.
 *
 * **WHY A GENERATION COUNTER AND NOT A `live` BOOLEAN (AC 5).** `createPoller` carries the
 * argument in full at `poller.ts:161` — *"a plain `live` boolean cannot tell 'stopped' from
 * 'stopped and restarted'"* — and it applies here with one extra edge the poller does not have:
 * this is a TWO-REQUEST sequence, so the second request is issued **after an await**, and a
 * React StrictMode remount (mount → cleanup → mount, in development) can land a `stop()` and a
 * fresh `start()` in that exact window. A boolean would let the first sequence resume, issue its
 * second request against an abandoned world, and write a deck the caller has already left. The
 * counter is re-checked after BOTH awaits, and `onUpdate` is called through a guard rather than
 * directly, so there is one place a stale write can be stopped instead of three.
 *
 * Args:
 *   options: See {@link DeckBootOptions}.
 *
 * Returns:
 *   A {@link DeckBoot}. Every instance owns its own generation, so a second one cannot silence
 *   the first by accident or be silenced by it.
 */
export const createDeckBoot = ({
  onUpdate,
  readActive = readActiveDeckRoute,
  readDetail = readDeckRoute,
}: DeckBootOptions): DeckBoot => {
  let live = false
  let generation = 0

  const run = async (gen: number): Promise<void> => {
    /** Emit only if this sequence still owns the store. The one place staleness is stopped. */
    const settle = (state: DeckState): void => {
      if (gen !== generation || !live) return
      onUpdate(state)
    }

    let active: ActiveDeckOutcome
    try {
      active = await readActive()
    } catch {
      // `readActiveDeck` is total and cannot reject; an injected reader might.
      active = { kind: 'unreachable' }
    }
    if (gen !== generation || !live) return

    if (active.kind === 'unreachable') return settle({ status: 'none' })
    if (active.kind === 'error') return settle(activeRefusalState(active.reason))

    // The blank id is refused HERE, with no request, and it is a route-shape fact rather than a
    // validation opinion: `deckPath('')` is the bare collection path `/api/deck/` — a DIFFERENT
    // route, not a malformed parameter — so the id gate that answers every other hostile value
    // never gets to see this one. `hydrateCard` refuses `''` one layer up for the same reason.
    // `readActiveDeck` already folds a blank id to `null`, so this is the second lock on a door
    // that has one; it stays because the sequence below must never call `readDetail('')` — and
    // it trims, because `activeDeckIdOf` folds on `trim()` and a second lock weaker than the
    // first (`'  '` slipping through to `/api/deck/%20%20`) is the review finding it closed.
    if (active.deckId === null || active.deckId.trim() === '') return settle({ status: 'none' })

    let detail: DeckOutcome
    try {
      detail = await readDetail(active.deckId)
    } catch {
      detail = { kind: 'unreachable' }
    }
    if (gen !== generation || !live) return

    if (detail.kind === 'unreachable') return settle({ status: 'none' })
    if (detail.kind === 'error') return settle(deckRefusalState(detail.reason))

    // In a try/catch because `deckOf` validates the envelope, not the rows (`id`, `name`,
    // `Array.isArray(cards)` — its own docstring declares that bad rows reach the derivation),
    // so a malformed row inside a valid-looking `200` throws in `boardsOfDeck` AFTER every
    // guard has passed. Without the catch that is an unhandled rejection and a slice stuck at
    // `'booting'` forever — no panel, no signal — which breaks this module's own "every outcome
    // is a value" posture (a review finding). Unreachable with the real Pydantic backend;
    // reachable the day the SPA and the backend skew.
    try {
      // AC 17 — the summaries the payload ALREADY carried become the card cache's summary tier,
      // at a cost of ZERO requests. Measured on the largest real deck (99 distinct cards):
      // 38,182 bytes already in hand, against 212,436 bytes over 99 requests to fetch the same
      // fields again. Called before `settle` so that a consumer re-rendered by the state below
      // can read a cache that is already warm. The generation check after the await above
      // guards this too: a stopped or superseded boot discards its payload WITHOUT seeding —
      // conservative on purpose, since seeding from an abandoned boot would be an unmeasured
      // optimization sharing a shape with the mid-flight-seed clobber c4-1's review closed.
      seedCardSummaries(detail.deck.cards)
      settle({ status: 'deck', detail: detail.deck, boards: boardsOfDeck(detail.deck) })
    } catch {
      settle(deckRefusalState(null))
    }
  }

  return {
    start: () => {
      if (live) return
      live = true
      generation += 1
      void run(generation)
    },
    stop: () => {
      live = false
      generation += 1
    },
  }
}

/**
 * What is actually on the glass: a deck, or one system panel — **never both** (Q1, AC 6).
 *
 * A value rather than a pair of booleans, so `App.tsx` renders an answer instead of computing
 * one, and so **c4-4**, **c4-7** and **c4-12** read the same answer rather than each re-deriving
 * it from `deck !== null`.
 */
export type Surface =
  | { readonly kind: 'deck'; readonly detail: DeckDetail; readonly boards: DeckBoards }
  | { readonly kind: 'panel'; readonly panel: StateKey }

/**
 * THE PRECEDENCE, IN ONE EXPRESSION (Q1, AC 6, AC 7, AC 8, AC 9, AC 11).
 *
 * `EXPERIENCE.md`'s state table gives the answer row by row — *"Cold open, backend live, deck
 * set"* → the deck view; *"Fresh install, DB missing"* → a panel; *"Deck deleted"* → a panel —
 * and every one of those rows is *a deck, or a panel, never both*. Three arms, in this order,
 * and each one is an acceptance criterion:
 *
 *   1. **A loaded deck displaces the system panel** (AC 6). Note what that costs and why it is
 *      correct anyway: with the panel gone and no grid until **c4-4**, the shell's `left` slot
 *      falls back to its own placeholder — *"The card-art grid lands here — c4-4 …"* — which is
 *      the honest displacement rather than a regression, and the same pattern c2-9 and c2-10
 *      both accepted for the slots they filled.
 *   2. **Else a deck REFUSAL that decided a panel of its own** (AC 9, AC 11). This arm is why the
 *      order is not simply "deck, else system": the deck read's `503 database_unavailable` and
 *      `503 database_not_initialized` must put THEIR panels on the glass, and a rule that let the
 *      poll's opinion win would make that criterion pass only by coincidence — the two routes
 *      usually agree, so the assertion would be vacuous exactly when it mattered.
 *   3. **Else the system panel** (AC 7). `booting` and `none` both land here, so a fresh install
 *      still shows `no-active-deck` with the deck names the poll already fetched, non-clickable,
 *      and `App.test.tsx`'s existing assertions on that panel pass **unmodified**.
 *
 * Args:
 *   deck: The deck slice.
 *   system: The system slice — `panel` only; `decks` belongs to whoever renders the panel.
 *
 * Returns:
 *   The one surface to render.
 */
export const surfaceOf = (deck: DeckState, system: SystemState): Surface => {
  if (deck.status === 'deck') return { kind: 'deck', detail: deck.detail, boards: deck.boards }
  if (deck.status === 'refused') return { kind: 'panel', panel: deck.panel }
  return { kind: 'panel', panel: system.panel }
}

/**
 * Subscribe to the deck state, and boot it once for as long as the caller is mounted.
 *
 * **`App` is the ONE consumer**, which is `useSystemState`'s rule and holds here for a sharper
 * reason: every mounted caller creates its OWN boot, so a second consumer would silently double
 * the request count on a route this story exists to make cheap. A future component that needs
 * the deck reads {@link useDeckStore} directly and lets the root keep the boot.
 *
 * In an effect rather than at module scope, for `systemState.ts`'s reason: a module-level boot
 * would fire during import — in every test file that touches this module, and twice under
 * StrictMode with no cleanup between. In an effect it starts on mount and is abandoned on
 * unmount, which is also what lets `App.test.tsx` prove FR-07 from ONE mount.
 *
 * ================= THE RECOVERY RE-DRIVE (review finding, FR-22) =======================
 *
 * The subscription below is the module header's re-drive, and its trigger is an EDGE, not a
 * level: the poll's panel transitioning INTO `no-active-deck` from anything else. That edge is
 * the poll saying "the backend went from refusing to healthy" — the moment a deck refusal
 * settled during the outage stops being true. On it, a `'refused'` or `'none'` deck state is
 * re-booted once via `stop()`/`start()` (fresh generation, so the guard argument above holds
 * unchanged); a `'deck'` never is — `App.test.tsx`'s "boots exactly once" test crosses this
 * exact edge with a loaded deck and pins the request count — and a `'booting'` sequence is left
 * to settle against whatever it reads, a window declared in the header. Level-triggering
 * instead (re-drive whenever the poll IS healthy and the deck refused) would loop forever
 * against an id that refuses forever, which is precisely what AC 12's ten-minute test bans.
 *
 * The listener reads the slice through `useDeckStore.getState()` rather than closing over a
 * render's value: an effect's closure sees the state of the render that ran it, and this
 * decision must be made against the state of NOW.
 *
 * Returns:
 *   The current `DeckState`. Re-renders the caller whenever the boot changes it.
 */
export const useDeckState = (): DeckState => {
  useEffect(() => {
    const boot = createDeckBoot({ onUpdate: applyDeckState })
    boot.start()
    const unsubscribe = subscribeSystemState((state, previous) => {
      if (state.panel !== 'no-active-deck' || previous.panel === 'no-active-deck') return
      const { deck } = useDeckStore.getState()
      if (deck.status === 'deck' || deck.status === 'booting') return
      boot.stop()
      boot.start()
    })
    return () => {
      unsubscribe()
      boot.stop()
    }
  }, [])

  return useDeckStore((slice) => slice.deck)
}
