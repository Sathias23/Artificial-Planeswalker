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
 * It is what shipped in c2-9 and it is still true before the first answer arrives: there is no
 * active deck, and an empty deck list renders nothing extra. The alternatives are worse in a way
 * a human would see — rendering no panel at all hands the shell's `left` slot back to its
 * placeholder line (the one naming c4-4 and c4-8), and picking a database state before asking the
 * backend would be a guess presented as a fact. On localhost the first answer lands in
 * milliseconds, so what this constant really governs is the first frame, not a state anyone reads.
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
import { createPoller } from './poller'

export interface SystemState {
  /** Which system panel is on the glass. Chosen from the wire token, never from a status code. */
  readonly panel: StateKey
  /** Deck names, carried by `no-active-deck` alone — every other panel is handed `[]`. */
  readonly decks: readonly string[]
}

/** The state before the first answer. Exported so tests can restore it between renders. */
export const INITIAL_SYSTEM_STATE: SystemState = { panel: 'no-active-deck', decks: [] }

export const useSystemStore = create<SystemState>(() => INITIAL_SYSTEM_STATE)

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
    poller.start()
    return () => poller.stop()
  }, [])

  return useSystemStore()
}
