/**
 * The last deck the detail panel resolved a cold-open for (review 2026-08-05; reshaped c7-4).
 *
 * MODULE scope, deliberately, for the same reason the inspection slice itself is (c4-5 Q6): the
 * panel unmounts on every surface flip, and a `useRef` would forget the deck across one — letting
 * a pin from deck A outrank deck B's cold-open target after a flip-and-recover. Identity is the
 * `boards` REFERENCE, which `deck.ts` derives once at write time, so it changes exactly when the
 * deck does.
 *
 * ==== WHAT c7-4 CHANGED, AND THE COST IT REMOVED =======================================
 * This module used to answer only a BOOLEAN — "did that replace a different deck?" — and the
 * caller cleared the pin on any true, with an accepted cost on the record: a same-deck edit also
 * mints a new reference, so every c7-3 refetch released the user's pin. R9's ruling (2026-08-14)
 * retired that mechanism: eviction is a MEMBERSHIP TRANSITION over the two decklists, which
 * needs the DEPARTING boards, not a verdict about them. So {@link rememberBoards} now returns
 * what it used to merely compare — the boards being replaced — and the deciding moved to
 * `inspection.ts`'s `evictDepartedPin`, which reads both lists and nothing else.
 *
 * A module of its own rather than a corner of `CardDetail.tsx` because
 * `react-refresh/only-export-components` is an ESLint error and a component file that also
 * exports a helper breaks fast refresh — `./imageUrl.ts`'s stated precedent, one story earlier.
 * NOT in the inspection slice, whose header promises it holds no deck; this module holds the one
 * deck-shaped fact the transition needs, beside the one consumer that has a deck at all.
 */

import type { DeckBoards } from '../../state/deckGroups'

let lastBoards: DeckBoards | null = null

/**
 * Remember `boards`, and hand back the DEPARTING boards when this write REPLACED a different
 * deck — `null` for the first deck ever remembered and for a remount of the same reference,
 * which is what keeps FR-17's pin-survives-the-view contract intact across a surface flip. A
 * non-null return is the caller's cue to run the R9 membership eviction over (departing, next)
 * and to clear the transients, whose stale-by-construction clearing is unchanged from c4-5.
 */
export const rememberBoards = (boards: DeckBoards): DeckBoards | null => {
  const previous = lastBoards
  lastBoards = boards
  return previous !== null && previous !== boards ? previous : null
}

/** Forget the remembered deck. **For tests**, beside `resetInspection`, for the same reason. */
export const resetDeckMemory = (): void => {
  lastBoards = null
}
