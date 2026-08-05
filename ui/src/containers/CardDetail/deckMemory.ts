/**
 * The last deck the detail panel resolved a cold-open for (review 2026-08-05).
 *
 * MODULE scope, deliberately, for the same reason the inspection slice itself is (c4-5 Q6): the
 * panel unmounts on every surface flip, and a `useRef` would forget the deck across one — letting
 * a pin from deck A outrank deck B's cold-open target after a flip-and-recover. Identity is the
 * `boards` REFERENCE, which `deck.ts` derives once at write time, so it changes exactly when the
 * deck does. The accepted cost, ruled at review: a same-deck edit also produces a new reference
 * and releases an active pin — rarer and less wrong than the panel rendering a card that is not
 * on the glass.
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
 * Remember `boards`, and answer whether it REPLACED a different deck — true exactly when an
 * inspection set against the previous deck should die. The first deck ever remembered, and a
 * remount of the same deck, both answer false: that is what keeps FR-17's pin-survives-the-view
 * contract intact across a surface flip.
 */
export const replacesRememberedDeck = (boards: DeckBoards): boolean => {
  const replaced = lastBoards !== null && lastBoards !== boards
  lastBoards = boards
  return replaced
}

/** Forget the remembered deck. **For tests**, beside `resetInspection`, for the same reason. */
export const resetDeckMemory = (): void => {
  lastBoards = null
}
