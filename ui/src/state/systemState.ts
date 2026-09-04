/**
 * The store's first slice, and the one React seam this story adds (story c3-9; Q1).
 *
 * `zustand` has been a declared dependency with **zero** consumers since c2-1 —
 * `tests/package-contract.test.ts` asserts the dependency exists purely so that its "no second
 * store" ban is not reading an empty object. This is its first consumer, and the slice is
 * deliberately the smallest honest one: which system panel is on the glass, and the deck names
 * that one of those panels carries.
 *
 * **c4-1 extends this store; it does not replace it.** The card cache and the in-flight deduping
 * are new slices beside this one, and `AD-12`'s one-store rule is what makes that the cheap path.
 *
 * ================= WHY THE INITIAL PANEL IS `no-active-deck` ============================
 *
 * It is the honest value the moment the active-deck read answers `null`, and picking a database
 * state before asking the backend would be a guess presented as a fact. What it is NOT is a first
 * frame: `surfaceOf` masks this panel behind its `booting` arm until the active-deck read settles,
 * so a cold open that is about to render a deck never paints the Welcome surface (or fetches its
 * hero art) on the way there. This constant governs what the panel says once booting ends, not
 * what the first commit draws.
 *
 * ================= WHY THE POLLER LIVES IN AN EFFECT AND NOT AT MODULE SCOPE ============
 *
 * A module-level `createPoller().start()` would fire during import — in every test file that
 * touches this module, in the SSR-less build's first evaluation, and twice under React
 * StrictMode with no cleanup between. In an effect it starts on mount and is cancelled on
 * unmount, which is also what makes `App.test.tsx`'s transition test able to prove FR-22's *"no
 * manual refresh"*: one mount, two answers, one component.
 */

import { useEffect } from 'react'
import { create } from 'zustand'

import type { StateKey } from '../components/StatePanel/copy'
import { RETRIES_QUIETLY } from '../components/StatePanel/states'
import { createPoller, type Poller } from './poller'
import type { ConnectionStatus } from './socket'

export interface SystemState {
  /** Which system panel is on the glass. Chosen from the wire token, never from a status code. */
  readonly panel: StateKey
  /** Deck names, carried by `no-active-deck` alone — every other panel is handed `[]`. */
  readonly decks: readonly string[]
  /**
   * What the app knows about its WebSocket (story c5-6, Q8, Brad 2026-08-08).
   *
   * **A field on this slice rather than a fourth store, and that was a ruling.** The alternative
   * spends a `STORES` entry in `store-writes.test.ts` and a whole writer module on ONE
   * three-valued field whose only two consumers — `surfaceOf` and the connection pill (**shipped
   * at c5-7**, reading through {@link useConnection}) — both already read this slice. The
   * prediction held: the second consumer arrived one story later and needed no new store. What
   * makes the field belong here rather than merely fit: the poll and
   * the socket are the app's two answers to the same question, *is the backend there*, and the
   * one place they are reconciled is `surfaceOf`, which takes this whole object.
   *
   * **It is NOT the `panel` field, and that separation is load-bearing.** A socket that wrote
   * `panel: 'disconnected'` would be racing the poller for one slot: with the HTTP half up and
   * the WS half failing (a proxy misconfiguration is the realistic case), the next poll SUCCESS
   * is a change, and it would overwrite the disconnected panel while the socket was still down.
   * Two writers, one field, last one wins. Keeping the connection in its own field means
   * `surfaceOf` composes the two opinions instead of one erasing the other, and it is why
   * `PANEL_FOR_REASON` stays untouched — `disconnected` has no wire token by design.
   *
   * Written on CHANGE only, by {@link applyConnection}, from `connection.ts`'s loop.
   */
  readonly connection: ConnectionStatus
  /**
   * The backend instance id the tab last CONFIRMED, or `null` before the first confirmation
   * (story 17.1, FR-15, AD-4).
   *
   * A field on this slice rather than an eighth store, for the `connection` field's own reason
   * one entry up: it is the same question — *which backend is this tab talking to* — answered
   * with an identity instead of a status, and its one consumer (the pill's tooltip) already
   * reads this slice through a selector hook.
   *
   * **Last-confirmed semantics, and that is the whole contract.** Written by
   * {@link applyInstanceId} on a successful `GET /health` read only — `src/state/identity.ts`
   * refreshes it on every transition to `'live'`, and a failed read leaves it alone. So through
   * `reconnecting` and `down` the field truthfully names the LAST backend this tab confirmed,
   * which is the honest thing a tooltip can say while nothing is answering. (Deliberately the
   * opposite of the deck-name asymmetry, which withholds in `down` — the pill's deck claim is
   * about a deck the app can no longer answer for; this one is explicitly about the past.)
   */
  readonly instanceId: string | null
}

/**
 * The state before the first answer. Exported so tests can restore it between renders.
 *
 * `connection: 'reconnecting'` is the honest cold-open value and not a placeholder: before the
 * first upgrade lands there is no socket and the loop is trying, which is what that word means.
 * It draws no panel — only `'down'` does — so the first frame is unchanged from c3-9's, which is
 * what `INITIAL_SYSTEM_STATE`'s original docstring was protecting.
 */
export const INITIAL_SYSTEM_STATE: SystemState = {
  panel: 'no-active-deck',
  decks: [],
  connection: 'reconnecting',
  // `null` is the honest cold open: no backend has confirmed an identity yet, and the tooltip's
  // copy says so in words rather than showing a placeholder id (story 17.1).
  instanceId: null,
}

export const useSystemStore = create<SystemState>(() => INITIAL_SYSTEM_STATE)

/**
 * Write the connection status (story c5-6). **The second input to this slice, and its owner is
 * still this module** — `store-writes.test.ts`'s rule is one writer per store, not one writer per
 * field, so the socket loop reports and this function applies, exactly as `poller.ts` reports and
 * the effect below applies.
 *
 * No change-detection here: {@link createAgentSocket} already emits on change only, for the
 * measured reason its own docstring gives (this store is subscribed selector-less in `App`, so
 * every write re-renders the whole tree). A second guard here would be a second copy of the same
 * invariant, free to disagree with the first.
 *
 * Args:
 *   connection: The status the loop has reached.
 */
export const applyConnection = (connection: ConnectionStatus): void => {
  useSystemStore.setState({ connection })
}

/**
 * Write a CONFIRMED backend instance id (story 17.1). **The third input to this slice, and its
 * owner is still this module** — `store-writes.test.ts`'s rule is one writer per store, not one
 * writer per field, so `identity.ts` reports and this function applies, exactly as the socket
 * loop reports through {@link applyConnection} and `poller.ts` reports through the effect below.
 *
 * Change-detected, unlike {@link applyConnection} — and the asymmetry is the two callers'.
 * The socket already emits status on change only, so a guard there would duplicate an invariant;
 * NOTHING dedupes identity reads, because every reconnect refreshes and most reconnects land on
 * the same process. `App` subscribes to this store selector-less, so an unguarded same-value
 * write here would re-render the whole tree once per reconnect for nothing.
 *
 * Never called with a failure: `identity.ts` swallows those before this verb is reached, which
 * is what makes the field's last-confirmed contract true by construction.
 *
 * Args:
 *   instanceId: The id a `GET /health` read just confirmed.
 */
export const applyInstanceId = (instanceId: string): void => {
  if (useSystemStore.getState().instanceId === instanceId) return
  useSystemStore.setState({ instanceId })
}

/**
 * The connection status alone, for a consumer that wants only that field (story c5-7, Q5).
 *
 * ==== WHY A SECOND HOOK RATHER THAN A SECOND `useSystemState()` CALLER ==================
 * {@link useSystemState} does two things — it subscribes AND it owns the poll — and its docstring
 * makes "`App` is the ONE consumer" a rule rather than an observation, because every mounted
 * caller creates its own poller. So a second consumer could not use it even if it wanted the whole
 * slice. This hook is the read half with none of the ownership: no effect, no poller, no writes.
 *
 * ==== AND IT IS SELECTOR-BASED, WHICH IS dw:5430's DISPOSITION ==========================
 * That entry records the selector-less subscription in `App` as a standing cost *"the pill (c5-7)
 * and Epic 6 will both inherit"*, and homes the question here: **"c5-7 if the pill wants finer
 * granularity."** It does. `App` re-renders wholesale on every system write — `panel`, `decks` and
 * `connection` alike — and a pill that subscribed the same way would add a second whole-store
 * subscription to re-render a component that can only ever show one of the three fields. With the
 * selector, the pill re-renders when `connection` changes and at no other time.
 *
 * **The entry is CLOSED by this, and the cost it records is not.** `App`'s own subscription is
 * unchanged and still selector-less, deliberately: it reads all three fields, so a selector there
 * would be ceremony. What dw:5430 asked was whether the pill wanted finer granularity; the answer
 * is yes, and it is one line rather than a change to how the store is written.
 *
 * The store, {@link applyConnection} and `store-writes.test.ts`'s `STORES` table are untouched:
 * this adds a READER, and a reader is not a writer.
 *
 * Returns:
 *   The current connection status. Re-renders the caller only when that field changes.
 */
export const useConnection = (): ConnectionStatus => useSystemStore((state) => state.connection)

/**
 * The last-confirmed instance id alone (story 17.1) — {@link useConnection}'s pattern for
 * {@link useConnection}'s reason: the pill is the one consumer, it can only ever show this
 * field and `connection`, and a whole-slice subscription would re-render it on every `panel`
 * and `decks` write. A reader, not a writer; the store and the `STORES` table are untouched.
 *
 * Returns:
 *   The last-confirmed instance id, or `null` before the first confirmation. Re-renders the
 *   caller only when that field changes.
 */
export const useInstanceId = (): string | null => useSystemStore((state) => state.instanceId)

/**
 * Watch the system state change, without naming the store (c4-2 review, the recovery re-drive).
 *
 * `deck.ts` needs to see the poll transition back into a healthy `no-active-deck` so a deck
 * refusal does not outlive the condition it reported — but it may not import `useSystemStore`
 * by name: `tests/store-writes.test.ts`'s writer scan treats any module containing both
 * `setState` and a store's name as a writer of that store, and `deck.ts` owns a `setState` of
 * its own. This wrapper is the seam that keeps the subscription and the gate both honest:
 * subscribers get the values, never the store.
 *
 * Args:
 *   listener: Called with the new and previous state on every store write.
 *
 * Returns:
 *   An unsubscribe function.
 */
export const subscribeSystemState = (
  listener: (state: SystemState, previous: SystemState) => void,
): (() => void) => useSystemStore.subscribe(listener)

/**
 * The poller the mounted `App` owns, or `null` — the seam the socket re-drives it through
 * (story c5-6, AC 15; Q5).
 *
 * ==== WHY A MODULE SLOT AND NOT AN EXPORTED POLLER =====================================
 * The poller must stay inside the effect: `useSystemState`'s own docstring gives the measured
 * reason (a module-level `createPoller().start()` fires during import, in every test file that
 * touches this module, and twice under StrictMode with no cleanup between). But the reconnect
 * loop lives in a different module and needs to restart it. So the INSTANCE stays in the effect
 * and this slot holds a reference to it for as long as one is mounted — the mirror image of
 * {@link subscribeSystemState}, which lets `deck.ts` watch this store without naming it.
 *
 * `null` when nothing is mounted, and every function below tolerates that rather than asserting:
 * a socket callback landing after `App` unmounted is an ordinary race, not a fault.
 */
let mounted: Poller | null = null

/**
 * Subscribe to the system state, and keep the poll running for as long as the caller is mounted.
 *
 * **`App` is the ONE consumer, and that is a rule, not an observation.** Every mounted caller
 * creates its OWN poller — a second consumer silently doubles the request rate and races two
 * backoffs and two stalled clocks into one store, last writer wins. A future component that
 * needs this state (a header pill, a c4-x tile) reads `useSystemStore` directly and lets the
 * root keep the poll; if the poll itself ever needs to move, it moves — it does not multiply.
 *
 * Returns:
 *   The current `SystemState`. Re-renders the caller whenever the poll changes it.
 */
export const useSystemState = (): SystemState => {
  useEffect(() => {
    const poller = createPoller({
      onUpdate: (update) => useSystemStore.setState(update),
      initialPanel: INITIAL_SYSTEM_STATE.panel,
    })
    mounted = poller
    poller.start()
    return () => {
      // Identity-checked, for the reason {@link mounted} gives: a StrictMode remount runs this
      // cleanup BEFORE the next effect, so an unconditional clear would be correct today and
      // would silently un-register the live poller the day the order changed.
      if (mounted === poller) mounted = null
      poller.stop()
    }
  }, [])

  return useSystemStore()
}

/**
 * Restart the poll from scratch — a NEW poll, with the backoff, the outcome identity and the
 * stalled clock all reset (`poller.ts:293-306` spells out what `start()` after `stop()` means).
 *
 * **Called on reconnect success** (Q5). A socket coming back means the backend process is
 * answering again, and after a restart that is a genuinely fresh backend: whatever the poll
 * believed about the old one — a 60-second stalled clock, a ceiling-length backoff, a remembered
 * outcome identity — is evidence about a process that no longer exists.
 */
export const restartPoll = (): void => {
  if (mounted === null) return
  mounted.stop()
  mounted.start()
}

/**
 * Restart the poll **only if it has stopped** — i.e. only if the panel on the glass is one
 * `RETRIES_QUIETLY` says does not retry itself (story c5-6, AC 15; Q5).
 *
 * ==== THIS IS THE HALF THAT CLOSES THREE LEDGER ENTRIES ================================
 * `poller.ts` stops on `no-active-deck`, `database-updating-stalled` and `internal-error`, and
 * each `false` is correct on its own terms — but each one also leaves a panel that can outlive
 * its condition with nothing to notice:
 *
 *   - **dw:3472/3544** — a user obeys the stalled panel, rebuilds the database successfully, and
 *     still needs a manual refresh, because the panel that told them to act is the one state that
 *     stopped asking. (Felt live at Block I: wire `200`, poll count moved by exactly 0 over 45 s.)
 *   - **dw:3463** — after one `200` the poll stops on `no-active-deck`; a database that dies later
 *     shows a stale healthy panel until reload.
 *   - **dw:3756** — an `active_deck_changed` arrives on the wire and nothing listens.
 *
 * The signal the first two were missing is a socket, and this story has one. The gate is the
 * CONTRACT rather than a list of three panel names: `RETRIES_QUIETLY[panel] === false` is exactly
 * *"the poll has stopped on this"*, so a seventh panel decided later is covered without an edit
 * here — and a panel the poll is still working on is not disturbed, which is what stops this from
 * becoming a second polling mechanism racing the first.
 *
 * **Not called on reconnect success** — that path takes {@link restartPoll} unconditionally, see
 * above. This one answers the other trigger: a `deck_changed` / `active_deck_changed` frame,
 * which is the backend telling us it is alive and that something moved.
 */
export const restartPollIfStopped = (): void => {
  if (mounted === null) return
  if (RETRIES_QUIETLY[useSystemStore.getState().panel]) return
  mounted.stop()
  mounted.start()
}
