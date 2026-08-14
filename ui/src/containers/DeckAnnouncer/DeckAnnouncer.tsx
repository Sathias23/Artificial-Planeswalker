import { Fragment, useState } from 'react'

import { useDeckRefetchSettles, useDeckStore } from '../../state/deck'
import { deckUpdatedAnnouncement } from './copy'

/**
 * The deck-refetch announcement region — UX-DR45's third and last polite channel (story c7-5).
 *
 * A c7-3 coalesced refetch completes silently for a screen-reader user: the card appears, its
 * group count moves and its curve bar grows, and nothing says so. This container is the fix —
 * ONE visually-hidden `aria-live="polite"` region that speaks "Deck updated — {N} cards" exactly
 * once per settled refetch, on completion, and at no other moment.
 *
 * ================= IT READS STORE TRUTH, NOT AN EVENT (Design Notes) ===================
 *
 * The trigger is `refetchSettles` — the monotonic counter `deck.ts` increments ONLY in the
 * refetch sequence's success arm, beside its settle. Everything the announce-silence matrix
 * legislates therefore holds by construction rather than by branches here: a cold boot, a deck
 * switch (`active_deck_changed` re-drives the boot), a reconnect re-drive, the 404-clear and
 * every dropped outcome all leave the counter untouched, so this component has no list of cases
 * to keep in sync with the store's. It could not re-derive that truth from what it can see —
 * the `updating` falling edge fires on drops too, and `detail` identity moves on boots and
 * switches — which is exactly why the counter exists (`deck.ts`'s slice docstring).
 *
 * ================= PROPS-FREE, LIKE THE PILL IT RIDES BESIDE ===========================
 *
 * `ConnectionPill`'s posture, for `App.tsx`'s recorded reason: the root's job is where things
 * go, not what they say. It subscribes through primitive selectors — the counter, and the two
 * header counts narrowed to numbers — so it re-renders on those values and not on the boards.
 *
 * ================= THE ANNOUNCEMENT IS CAPTURED DURING RENDER, NOT IN AN EFFECT ========
 *
 * `ConnectionPill.tsx:86-109` is the template, for the reason it documents: `react-hooks/
 * set-state-in-effect` rejects the effect spelling, and a `setState` in an effect is a second
 * render pass. The `seen: null` sentinel is the mount silence — the first render stores the
 * counter's current value with an EMPTY text, so a remount over an already-settled store (or a
 * cold boot) announces nothing; only an ADVANCE observed across renders speaks. The
 * `status === 'deck'` gate (read through the narrowed counts being non-null) is belt to the
 * counter's braces: a counter advance and a loaded deck arrive in the same settle today, and the
 * gate keeps a hypothetical divergence from announcing numbers for a deck that is not there.
 *
 * ================= THE KEYED FRAGMENT IS THE RE-ANNOUNCE (AgentView.tsx:506-532) =======
 *
 * A live region speaks on DOM MUTATION, and two sequential refetches can end at the SAME total —
 * byte-identical text mutates nothing. Keying the Fragment on the counter makes React drop the
 * old text node and insert a new one per settle, so "announces every completion" is true for
 * every completion rather than only for the ones that changed the number. The region itself is
 * never keyed: a brand-new region is not a mutation of an existing one.
 *
 * ================= WHAT THIS DELIBERATELY DOES NOT DO ==================================
 *
 * No suppression behind a modal — c7-6 owns "no announcement fires from behind a modal", and the
 * gate would need agent-view state this component deliberately does not read; today the region
 * announces on completion regardless of an open view. No format-check announcement (deferred,
 * spec frontmatter: it would be a SECOND per-refetch announcement with no ruled copy). No
 * timers and no debounce — the c7-3 supersession IS the coalescing, pinned at the store level
 * as one settle per burst, which arrives here as one counter tick per burst.
 */
export function DeckAnnouncer() {
  const settles = useDeckRefetchSettles()

  // NARROWED TO PRIMITIVES, one field per subscription — `ConnectionPill`'s deck-name selector
  // shape. `null` outside the `'deck'` arm is the absence of a branch rather than a fallback
  // number: no deck, no count, no sentence.
  const mainboardCount = useDeckStore((state) =>
    state.deck.status === 'deck' ? state.deck.detail.mainboard_count : null,
  )
  const sideboardCount = useDeckStore((state) =>
    state.deck.status === 'deck' ? state.deck.detail.sideboard_count : null,
  )

  const [announced, setAnnounced] = useState<{
    readonly seen: number | null
    readonly text: string
  }>({ seen: null, text: '' })

  if (announced.seen !== settles) {
    setAnnounced({
      seen: settles,
      text:
        announced.seen === null || mainboardCount === null || sideboardCount === null
          ? ''
          : deckUpdatedAnnouncement(mainboardCount, sideboardCount),
    })
  }

  // EMPTY AT REST AND EMPTY MID-FLIGHT: the text is written only when a settle lands, so the
  // in-flight window (c7-4's `updating` marker) never leaks a word in here — App.test.tsx's
  // mid-flight census pins that alongside the other two regions.
  return (
    <p className="visually-hidden deck-announcement" aria-live="polite">
      <Fragment key={settles}>{announced.text}</Fragment>
    </p>
  )
}
