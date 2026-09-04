/**
 * The last deck the detail panel resolved a cold-open for.
 *
 * MODULE scope, deliberately, for the same reason the inspection slice itself is: the
 * panel unmounts on every surface flip, and a `useRef` would forget the deck across one — letting
 * a pin from deck A outrank deck B's cold-open target after a flip-and-recover. Identity is the
 * `boards` REFERENCE, which `deck.ts` derives once at write time, so it changes exactly when the
 * deck does.
 *
 * ==== WHY IT RETURNS THE BOARDS RATHER THAN A VERDICT ==================================
 * A BOOLEAN — "did that replace a different deck?" — is not enough: a same-deck edit also mints
 * a new reference, so clearing the pin on any true would release the user's pin on every
 * refetch. Eviction is a MEMBERSHIP TRANSITION over the two decklists, which needs the
 * DEPARTING boards, not a verdict about them. So {@link rememberBoards} returns the boards being
 * replaced, and the deciding lives in `inspection.ts`'s `evictDepartedPin`, which reads both
 * lists and nothing else.
 *
 * A module of its own rather than a corner of `CardDetail.tsx` because
 * `react-refresh/only-export-components` is an ESLint error and a component file that also
 * exports a helper breaks fast refresh — `../CardTile/imageUrl.ts`'s stated precedent.
 * NOT in the inspection slice, whose header promises it holds no deck; this module holds the one
 * deck-shaped fact the transition needs, beside the one consumer that has a deck at all.
 */

import type { DeckBoards } from '../../state/deckGroups'

let lastBoards: DeckBoards | null = null

/**
 * Remember `boards`, and hand back the DEPARTING boards when this write REPLACED a different
 * deck — `null` for the first deck ever remembered and for a remount of the same reference,
 * which is what keeps FR-17's pin-survives-the-view contract intact across a surface flip. A
 * non-null return is the caller's cue to run the membership eviction over (departing, next)
 * and to clear the transients, which are stale by construction.
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
