/**
 * The deck the companion is showing: the boot that finds it, and the rule that decides whether it
 * or a system panel is on the glass (FR-07, FR-11, AD-12, AD-16).
 *
 * The boot is two requests, on mount: `GET /api/active-deck`, then on a non-null id
 * `GET /api/deck/{deck_id}`. The first route holds no `DbSession` and cannot answer `503`, so
 * database refusals are about the SECOND request. `deck_id: null` is the ordinary answer, not a
 * failure: the active-deck slot dies with the backend process (FR-07).
 *
 * A DECK refusal becomes a panel where a CARD refusal never does (FR-13): a deck IS the view, so
 * there is nothing left standing to protect, and every deck token has an honest panel in
 * `PANEL_FOR_REASON` (FR-11: a deleted deck clears to *"there is no active deck"*).
 *
 * AD-12: *"its state comes from exactly two inputs — REST responses and WebSocket messages."* The
 * WebSocket is a TRIGGER, never a writer: a `deck_changed` frame drives a refetch, and what is
 * written is still a REST response, through one writer (`tests/store-writes.test.ts`). No timer:
 * recovery is edge-triggered — the poll recovering into `no-active-deck`, a reconnect, or a
 * `deck_changed`/`active_deck_changed` frame. No render, and no cache reset (reconnect re-arms card
 * attempt budgets in `cards.ts` rather than discarding hydration the agent views share).
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
import { PANEL_FOR_REASON, type ClientOnlyState } from '../components/StatePanel/states'
import { boardsOfDeck, type DeckBoards } from './deckGroups'
import { panelFor } from './panel'
import { seedDeckCards } from './cards'
import { subscribeSystemState, type SystemState } from './systemState'

/**
 * What the client knows about the active deck. A discriminated union: `deck | null` plus an
 * `error` field would be two invariants that can disagree.
 */
export type DeckState =
  /** The boot has not answered yet — DISTINCT from `'none'`: "not asked" is not "no deck". */
  | { readonly status: 'booting' }
  /**
   * No deck and no deck-specific panel — the system state is the authority. Reached by
   * `deck_id: null` (FR-07), by a refusal whose panel IS `'no-active-deck'`, and by `unreachable`:
   * nothing was decided, and claiming `internal-error` would say *"The companion hit a bug"* about
   * a backend that is merely absent (that panel is {@link surfaceOf}'s connection arm).
   */
  | { readonly status: 'none' }
  /** A deck loaded. `boards` is derived ONCE, here, at write time — see `deckGroups.ts`. */
  | { readonly status: 'deck'; readonly detail: DeckDetail; readonly boards: DeckBoards }
  /** A read was refused with a panel of its own. `reason` is clamped to `null` when unrecognised. */
  | { readonly status: 'refused'; readonly reason: ErrorReason | null; readonly panel: StateKey }

/** The state before the boot answers. Exported so tests can restore it between renders. */
export const INITIAL_DECK_STATE: DeckState = { status: 'booting' }

/**
 * The slice, holding the union **under a key**: zustand's `setState` MERGES by default, so a store
 * whose shape IS `DeckState` would accept `setState({ status: 'none' })` and keep a ghost `detail`.
 * A merge of one key replaces that key's value wholesale, and no call site has a flag to forget.
 */
export interface DeckSlice {
  readonly deck: DeckState
  /**
   * Whether the boot is re-reading the deck RIGHT NOW (UX-DR35, UX-DR42). True from a `start()` or
   * `refetch()` until that sequence's LAST exit, dropped outcomes included. A sibling KEY rather
   * than a member of {@link DeckState}: lifecycle truth about the request, not about the glass.
   */
  readonly updating: boolean
  /**
   * How many coalesced refetches have settled SUCCESSFULLY (UX-DR45) — the announce-once signal.
   * Incremented in exactly ONE place, {@link refetchSequence}'s success arm, so it never moves on a
   * boot settle, the 404-clear or a drop. A COUNTER, not a boolean, because two refetches ending at
   * the same total must still announce twice.
   */
  readonly refetchSettles: number
}

export const useDeckStore = create<DeckSlice>(() => ({
  deck: INITIAL_DECK_STATE,
  updating: false,
  refetchSettles: 0,
}))

/** The ONE writer (AD-12). Every input to this slice goes through here. */
const applyDeckState = (deck: DeckState): void => useDeckStore.setState({ deck })

/** The updating flag's writer. Generation-guarding is the CALLER's (each boot owns its counter). */
const applyUpdating = (updating: boolean): void => useDeckStore.setState({ updating })

/** The settle counter's writer. Takes the NEXT value so reset and increment share one writer. */
const applyRefetchSettles = (refetchSettles: number): void =>
  useDeckStore.setState({ refetchSettles })

/** Forget the deck. **For tests** — production never forgets; it refetches (or 404-clears). */
export const resetDeckState = (): void => {
  applyDeckState(INITIAL_DECK_STATE)
  applyUpdating(false)
  applyRefetchSettles(0)
}

/**
 * The panel a DECK refusal draws where that differs from `PANEL_FOR_REASON` — a per-context map,
 * `states.ts` untouched. `invalid_request` is deliberate: `states.ts` classifies it `NO_UI_RESPONSE`
 * on the premise that the SPA never sends a malformed request, but this id came from
 * `PUT /api/active-deck`, which stores any non-blank string without checking the deck exists. An
 * agent typo must read *"there is no active deck"*, not *"The companion hit a bug"*. Adding the
 * token to `states.ts` would break `ReasonClassificationsAreDisjoint`, rightly: the destination is a
 * property of the context, not of the token.
 */
const PANEL_FOR_DECK_REFUSAL = {
  invalid_request: 'no-active-deck',
} satisfies Partial<Record<ErrorReason, StateKey>>

/** Whether this build recognises a wire token. `PANEL_FOR_REASON`'s own key set — see `panel.ts`. */
const knownReason = (reason: string | null): ErrorReason | null =>
  reason !== null && Object.hasOwn(PANEL_FOR_REASON, reason) ? (reason as ErrorReason) : null

/** The overrides, widened for lookup — an assignment rather than a cast, as `cards.ts` does. */
const deckPanels: Partial<Record<ErrorReason, StateKey>> = PANEL_FOR_DECK_REFUSAL

/** The per-context override, else `panelFor`. `hasOwn` is inside {@link knownReason}. */
const deckPanelFor = (reason: string | null): StateKey => {
  const known = knownReason(reason)
  return (known === null ? undefined : deckPanels[known]) ?? panelFor(reason)
}

/**
 * `'none'` when the honest panel is *"there is no active deck"*, `'refused'` otherwise — the
 * clearing signal read out of the map, not paraphrased.
 */
const stateForPanel = (panel: StateKey, reason: string | null): DeckState =>
  panel === 'no-active-deck'
    ? { status: 'none' }
    : { status: 'refused', reason: knownReason(reason), panel }

/**
 * A refusal on the DECK read. After a `404` clears, the backend still reports the id as active, so
 * the NEXT boot asks again and clears again — one wasted request per cold open, accepted.
 */
const deckRefusalState = (reason: string | null): DeckState =>
  stateForPanel(deckPanelFor(reason), reason)

/**
 * A refusal on the ACTIVE-DECK read: `panelFor`, with **no override**. That route carries NO path
 * parameter, so a `400` from it really is a client bug; folding it to `'none'` would hide it.
 */
const activeRefusalState = (reason: string | null): DeckState =>
  stateForPanel(panelFor(reason), reason)

/** What one settled boot decided. Exported for the tests that drive the sequence directly. */
export interface DeckBoot {
  /** Runs the sequence once per `start()`/`stop()` cycle; a settled boot re-runs only via `stop()`. */
  start: () => void
  /** Abandons the sequence: nothing it has in flight may write after this. Idempotent. */
  stop: () => void
  /**
   * Refetch ONE deck by id, sharing the boot's generation counter, settle guard, refusal mapping
   * and seeding. Each call SUPERSEDES any refetch in flight (abort + generation bump), so a burst
   * holds at most one request and the LAST response wins — UX-DR35's *"a newer event cancels and
   * restarts"* with no timer; the supersession IS the coalescing. A no-op unless the boot has
   * settled: racing an unsettled sequence could strand the slice at `'booting'`. Only
   * `deck_not_found` settles (the 404-clear); every other refusal, an unreachable, an abort and a
   * malformed row are DROPPED so the loaded deck stays on the glass (UX-DR35 never-teardown).
   */
  refetch: (deckId: string) => void
  /** Whether the most recent `start()`'s sequence has settled. A refetch neither needs nor clears it. */
  settled: () => boolean
}

export interface DeckBootOptions {
  /** Emitted once per state the boot decides. */
  readonly onUpdate: (state: DeckState) => void
  /** Injected so tests need no global `fetch` stub, exactly as `createPoller`'s `read?:` is. */
  readonly readActive?: () => Promise<ActiveDeckOutcome>
  /** Likewise. **Production passes neither.** `signal` is the refetch's abort handle. */
  readonly readDetail?: (deckId: string, signal?: AbortSignal) => Promise<DeckOutcome>
}

/**
 * Build the boot. Nothing happens until `start()`.
 *
 * A GENERATION COUNTER rather than a `live` boolean (`poller.ts`'s argument), with one extra edge:
 * the second request is issued after an await, and a React StrictMode remount can land a `stop()`
 * and a fresh `start()` in that window. A boolean would let the first sequence resume and write a
 * deck the caller has already left. Every instance owns its own generation.
 */
export const createDeckBoot = ({
  onUpdate,
  readActive = readActiveDeckRoute,
  readDetail = readDeckRoute,
}: DeckBootOptions): DeckBoot => {
  let live = false
  let generation = 0
  /** Set inside {@link settleFor}'s guard, so a superseded sequence's late settle cannot flip it. */
  let sequenceSettled = false
  /** The in-flight refetch's abort handle, or `null`. Aborted on every supersede and on stop. */
  let refetchController: AbortController | null = null

  const abortRefetch = (): void => {
    refetchController?.abort()
    refetchController = null
  }

  /** The ONE settle guard, shared by boot and refetch: emit only if the caller still owns the store. */
  const settleFor =
    (gen: number) =>
    (state: DeckState): void => {
      if (gen !== generation || !live) return
      sequenceSettled = true
      onUpdate(state)
    }

  /**
   * The updating flag's clear, reached through `finally` so no exit misses it, and generation-
   * guarded so a SUPERSEDED run's exit cannot clear the flag its successor just raised.
   * `settleFor` cannot carry this: dropped outcomes never settle, yet each ends the window.
   */
  const clearUpdatingFor = (gen: number): void => {
    if (gen !== generation) return
    applyUpdating(false)
  }

  const runSequence = async (gen: number): Promise<void> => {
    /** Emit only if this sequence still owns the store. The one place staleness is stopped. */
    const settle = settleFor(gen)

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

    // Refused HERE with no request: `deckPath('')` is the bare collection path `/api/deck/`, a
    // DIFFERENT route. `readActiveDeck` already folds a blank id to `null`; this second lock stays
    // because the sequence must never call `readDetail('')`, and it trims because a lock weaker
    // than the first (`'  '` reaching `/api/deck/%20%20`) is no lock.
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

    // `deckOf` validates the envelope, not the rows, so a malformed row inside a `200` throws in
    // `boardsOfDeck` AFTER every guard. Without the catch that is an unhandled rejection and a
    // slice stuck at `'booting'` forever. Unreachable with the real backend; reachable on skew.
    try {
      // The payload's whole cards become HYDRATED cache entries at ZERO requests. Before `settle`,
      // so a consumer re-rendered by the state below reads a warm cache; the generation check
      // above means a superseded boot discards its payload WITHOUT seeding.
      seedDeckCards(detail.deck.cards)
      settle({ status: 'deck', detail: detail.deck, boards: boardsOfDeck(detail.deck) })
    } catch {
      settle(deckRefusalState(null))
    }
  }

  /** {@link runSequence}, with the updating window closed on EVERY exit path. */
  const run = async (gen: number): Promise<void> => {
    try {
      await runSequence(gen)
    } finally {
      clearUpdatingFor(gen)
    }
  }

  /**
   * The single-request refetch: the boot's machinery with a different OUTCOME MAPPING (UX-DR35).
   * `deck_not_found` settles the clearing state; every other refusal, an `unreachable` (which is
   * also what an abort surfaces as) and a malformed row are DROPPED, because tearing a loaded deck
   * down to a panel on a transient blip is the teardown UX-DR35 forbids. The `invalid_request`
   * override does NOT clear here: THIS id is the settled `detail.id`, which just resolved, so a 400
   * about it mid-session reads as a blip, not a verdict.
   */
  const refetchSequence = async (
    gen: number,
    deckId: string,
    signal: AbortSignal,
  ): Promise<void> => {
    const settle = settleFor(gen)

    let detail: DeckOutcome
    try {
      detail = await readDetail(deckId, signal)
    } catch {
      detail = { kind: 'unreachable' }
    }
    if (gen !== generation || !live) return

    if (detail.kind === 'unreachable') return
    if (detail.kind === 'error') {
      if (detail.reason === 'deck_not_found') settle(deckRefusalState(detail.reason))
      return
    }

    try {
      // The same zero-request seeding the boot does, for the same reason.
      seedDeckCards(detail.deck.cards)
      settle({ status: 'deck', detail: detail.deck, boards: boardsOfDeck(detail.deck) })
      // THE ANNOUNCE-ONCE SIGNAL (UX-DR45): incremented HERE and nowhere else, synchronous with the
      // generation check above, and AFTER the settle so a throw in `boardsOfDeck` skips both. The
      // boot's own success arm deliberately has no counterpart.
      applyRefetchSettles(useDeckStore.getState().refetchSettles + 1)
    } catch {
      // A malformed row inside a 200: the deck store is left untouched, because the deck on the
      // glass parsed (UX-DR35). `seedDeckCards` ran first, so the card cache may retain the
      // payload's valid rows — additive data a later successful refetch would seed anyway.
    }
  }

  /** {@link refetchSequence}, with the updating window closed on EVERY exit path. */
  const refetchRun = async (gen: number, deckId: string, signal: AbortSignal): Promise<void> => {
    try {
      await refetchSequence(gen, deckId, signal)
    } finally {
      clearUpdatingFor(gen)
    }
  }

  return {
    start: () => {
      if (live) return
      live = true
      generation += 1
      sequenceSettled = false
      // Synchronous with the generation bump, so the header marks the very frame the sequence
      // begins on. A cold boot raises it too; the App layer's `deck !== null` gate hides that.
      applyUpdating(true)
      void run(generation)
    },
    stop: () => {
      live = false
      generation += 1
      // The bump already silences a running refetch's settle; the abort stops paying for it.
      abortRefetch()
      // The aborted run's own `finally` will SKIP its clear (gen no longer matches), so `stop()`
      // clears directly — unguarded, because a stopped world has nothing in flight.
      applyUpdating(false)
    },
    refetch: (deckId) => {
      // Never race an unsettled sequence: the bump would silence the in-flight boot and could
      // strand the slice at `'booting'` forever.
      if (!live || !sequenceSettled) return
      // Supersede FIRST, then abort: the bump is what fails the aborted response's settle guard,
      // so the abort is a network economy and never load-bearing.
      generation += 1
      abortRefetch()
      // AFTER the gate and the bump: an ungated set would mark an event the boot refused, and a
      // pre-bump set would belong to the generation being superseded.
      applyUpdating(true)
      const controller = new AbortController()
      refetchController = controller
      void refetchRun(generation, deckId, controller.signal)
    },
    settled: () => sequenceSettled,
  }
}

/**
 * What is actually on the glass: a deck, or one system panel — **never both**. A value, so
 * `App.tsx` renders an answer instead of computing one and no consumer re-derives it.
 */
export type Surface =
  | { readonly kind: 'deck'; readonly detail: DeckDetail; readonly boards: DeckBoards }
  | { readonly kind: 'panel'; readonly panel: StateKey }
  /**
   * The boot has not heard back yet — the ABSENCE of a decision, carrying no `StateKey` because no
   * copy belongs to a frame nobody is meant to read. Without this arm the `no-active-deck` panel,
   * hero art included, painted on the first frame of EVERY cold open.
   */
  | { readonly kind: 'booting' }

/**
 * The panel a lost connection draws. Typed `ClientOnlyState`, not `StateKey`: `disconnected` has
 * no wire token by design, and retargeting this at a wire-sourced panel fails `npm run typecheck`.
 */
const DISCONNECTED_PANEL: ClientOnlyState = 'disconnected'

/**
 * THE PRECEDENCE, IN ONE EXPRESSION — `EXPERIENCE.md`'s state table, every row *a deck, or a
 * panel, never both*. A lost connection outranks even a loaded deck, but only on `'down'`, the
 * two-gate threshold in `socket.ts`; through the whole `'reconnecting'` window the deck stays on
 * the glass, possibly stale, as UX-DR35 asks. It reads the CONNECTION, not the `panel` field:
 * writing `'disconnected'` into the shared field would put two writers on one slot, and the next
 * poll success would overwrite it while the socket was still down (`PanelSourcesAreDisjoint`). The
 * deck slice is untouched underneath, so the socket coming back re-renders the deck with no reload.
 * Then booting renders nothing; a loaded deck displaces the system panel; a deck REFUSAL's own
 * panel outranks the poll's opinion (the two routes usually agree, so a rule that let the poll win
 * would pass only by coincidence); else the system panel.
 *
 * Args:
 *   deck: The deck slice.
 *   system: The system slice — `panel` and `connection`.
 */
export const surfaceOf = (deck: DeckState, system: SystemState): Surface => {
  if (system.connection === 'down') return { kind: 'panel', panel: DISCONNECTED_PANEL }
  // Any panel chosen before the active-deck read settles is a guess — and the `no-active-deck`
  // guess draws the Welcome hero, 420 KB of art, on the way to a deck view that never wanted it.
  // Every settle path leaves `'booting'`, so this arm cannot latch.
  if (deck.status === 'booting') return { kind: 'booting' }
  if (deck.status === 'deck') return { kind: 'deck', detail: deck.detail, boards: deck.boards }
  if (deck.status === 'refused') return { kind: 'panel', panel: deck.panel }
  return { kind: 'panel', panel: system.panel }
}

/**
 * The mounted `App`'s deck boot, or `null` — the seam `connection.ts` re-drives it through. A
 * module slot rather than an exported boot because the instance must stay inside the effect (a
 * module-level boot fires during import, and twice under StrictMode); the mirror of
 * `systemState.ts`'s `mounted` poller. A reconnect re-drives whatever the state is, INCLUDING a
 * loaded deck — unlike the poll edge — because the deck may have changed while the socket was gone.
 */
let mounted: DeckBoot | null = null

export const redriveDeckBoot = (): void => {
  if (mounted === null) return
  mounted.stop()
  mounted.start()
}

/**
 * The decision table over one `deck_changed`. Exported so `deck.test.ts` can drive it with an
 * injected boot; production reaches it through {@link refetchOnDeckChanged}.
 *
 * A settled `'deck'` with a matching or deck-agnostic id → {@link DeckBoot.refetch} of the
 * SETTLED `detail.id` (the event's copy was only ever a routing hint). A settled `'deck'` with a
 * DIFFERENT id → nothing. Anything else — `'none'`, `'refused'`, `'booting'`, or an unsettled
 * re-drive → the full two-request re-drive: the server is the referee, because adjudicating ids
 * client-side while the settled id is not current truth is how a refetch of a DEPARTING deck beats
 * an in-flight re-drive and strands the glass on the old deck. A STOPPED boot dies silently at
 * `refetch()`'s `!live` no-op; unreachable through the production seam. There is no stored
 * `activeDeckId` anywhere — inventing one would be a second source of truth.
 *
 * Args:
 *   boot: The boot to drive — production's mounted instance, or a test's own.
 *   deckId: The event's `deck_id`, already FOLDED: `null` means deck-agnostic ("refetch whatever
 *     is active").
 */
export const driveDeckChanged = (boot: DeckBoot, deckId: string | null): void => {
  const { deck } = useDeckStore.getState()
  if (deck.status !== 'deck' || !boot.settled()) {
    boot.stop()
    boot.start()
    return
  }
  if (deckId !== null && deckId !== deck.detail.id) return
  boot.refetch(deck.detail.id)
}

/** The mounted `App`'s answer to a `deck_changed` frame — or a no-op when nothing is mounted. */
export const refetchOnDeckChanged = (deckId: string | null): void => {
  if (mounted === null) return
  driveDeckChanged(mounted, deckId)
}

/** The header's updating marker. A primitive selector: re-renders only when the flag flips. */
export const useDeckUpdating = (): boolean => useDeckStore((slice) => slice.updating)

/**
 * How many copies of one card the active deck runs, or `null` when it runs none — the group tile's
 * quantity badge. A PRIMITIVE selector, because a group strip mounts one subscriber per tile.
 * `null` and never `0`: a card the deck does not run carries NO badge (*"rendering '×0' would be a
 * lie"*). SUMMED across boards — `detail.cards` carries one row per (card, board).
 */
export const useDeckCardQuantity = (cardId: string): number | null =>
  useDeckStore((slice) => {
    const { deck } = slice
    if (deck.status !== 'deck') return null
    let copies = 0
    let found = false
    for (const card of deck.detail.cards) {
      if (card.card_id === cardId) {
        copies += card.quantity
        found = true
      }
    }
    return found ? copies : null
  })

/** How many coalesced refetches have settled successfully — the `DeckAnnouncer`'s trigger. */
export const useDeckRefetchSettles = (): number => useDeckStore((slice) => slice.refetchSettles)

/**
 * Subscribe to the deck state, and boot it once for as long as the caller is mounted.
 *
 * **`App` is the ONE consumer**: every mounted caller creates its OWN boot. Other components read
 * {@link useDeckStore} directly. In an effect, because a module-level boot would fire during import.
 *
 * The recovery re-drive (FR-22) is an EDGE, not a level: the poll's panel transitioning INTO
 * `no-active-deck` is the poll saying "the backend went from refusing to healthy". On it a
 * `'refused'` or `'none'` state is re-booted once; a `'deck'` never is (`App.test.tsx`'s "boots
 * exactly once" crosses this edge with a loaded deck). Level-triggering would loop forever against
 * an id that refuses forever. The listener reads `useDeckStore.getState()` rather than a render's
 * closure, because the decision must be made against the state of NOW.
 */
export const useDeckState = (): DeckState => {
  useEffect(() => {
    const boot = createDeckBoot({ onUpdate: applyDeckState })
    mounted = boot
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
      // Identity-checked: a StrictMode remount runs this cleanup BEFORE the next effect, so an
      // unconditional clear would silently un-register the live boot the day that order changed.
      if (mounted === boot) mounted = null
      boot.stop()
    }
  }, [])

  return useDeckStore((slice) => slice.deck)
}
