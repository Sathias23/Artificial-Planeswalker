import { Fragment, useState } from 'react'

import { useAgentViewIsOpen } from '../../state/agentView'
import { useDeckRefetchSettles, useDeckStore } from '../../state/deck'
import { deckUpdatedAnnouncement } from './copy'

/**
 * The deck-refetch announcement region — UX-DR45's deck-refetch channel (story c7-5): the app's
 * third polite region at rest, and the fourth while an agent view is open (its live heading
 * mounts with the view — the census comments in `App.test.tsx` carry the same inventory).
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
 * ================= AND NOW IT IS SILENT BEHIND A MODAL (c7-6) ==========================
 *
 * ✅ **CLOSED.** This paragraph used to read *"No suppression behind a modal — c7-6 owns 'no
 * announcement fires from behind a modal', and the gate would need agent-view state this
 * component deliberately does not read"*. c7-6 is the story, and the deliberate blindness is
 * over: {@link useAgentViewIsOpen} is a fifth PRIMITIVE subscription — one boolean, not
 * `useOpenAgentView`'s content object, which would have resubscribed this component to every
 * push's items and broken the narrowing discipline above.
 *
 * **The settle is CONSUMED, not deferred**, and that is the one thing to preserve when editing
 * the two lines below: `seen` advances to `settles` on a suppressed settle exactly as it does
 * on a spoken one, so what the gate drops is the SENTENCE, never the observation. Announcing on
 * close would speak a count whose moment has passed, at the moment the reader is returning from
 * a dialog about something else — and it would put text into a region the App censuses pin
 * empty behind a modal. The next real refetch is the next real announcement.
 *
 * The clearing branch below is deliberately NOT gated: a deck that departs while a view is open
 * must still empty a standing sentence, because that sentence's claim is false the instant its
 * deck is gone whether or not anyone is looking at a dialog.
 *
 * ================= WHAT THIS DELIBERATELY DOES NOT DO ==================================
 *
 * No format-check announcement (deferred, and as of c7-6 the ledger entry is UNOWNED pending a
 * UX ruling: it would be a SECOND per-refetch announcement with no ruled copy, so no story may
 * home it here without that ruling). No timers and no debounce — the c7-3 supersession IS the
 * coalescing, pinned at the store level as one settle per burst, which arrives here as one
 * counter tick per burst.
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

  // Which deck the sentence is ABOUT — the third narrowed read, and the clearing rule's whole
  // input: a settled id while a deck is on the glass, `null` behind every panel.
  const deckId = useDeckStore((state) =>
    state.deck.status === 'deck' ? state.deck.detail.id : null,
  )

  // THE MODAL GATE'S ONE INPUT (c7-6). A boolean off the agent-view slice — the fifth primitive
  // subscription and the only one that is not a deck field. UX-DR45: *"Nothing announces from
  // behind an open agent view."*
  const viewOpen = useAgentViewIsOpen()

  const [announced, setAnnounced] = useState<{
    readonly seen: number | null
    /** The id of the deck the current `text` describes, or `null` while the region is empty. */
    readonly about: string | null
    readonly text: string
  }>({ seen: null, about: null, text: '' })

  if (announced.seen !== settles) {
    // `&& !viewOpen` is c7-6's WHOLE mechanism, and it is one term in one expression on purpose:
    // suppression that lived anywhere else (a second `useState`, an early return, a store field)
    // would be a second place for "did this settle announce" to be decided. Note what it does
    // NOT touch — `seen: settles` below is unchanged, which is what makes a suppressed settle a
    // DROP rather than a queued announcement waiting for the view to close.
    const speaks =
      announced.seen !== null && mainboardCount !== null && sideboardCount !== null && !viewOpen
    setAnnounced({
      seen: settles,
      about: speaks ? deckId : null,
      text: speaks ? deckUpdatedAnnouncement(mainboardCount, sideboardCount) : '',
    })
  } else if (announced.text !== '' && deckId !== announced.about) {
    // THE SENTENCE MUST NOT OUTLIVE THE DECK IT DESCRIBES. After the 404-clear the glass shows
    // "there is no active deck" and after a switch it shows a different deck — a region still
    // asserting "Deck updated — 102 cards" beside either is a stale claim about a departed
    // deck. So the text is EMPTIED at render time the moment the settled id stops matching the
    // id the sentence was about. CardDetail's pin region is the precedent (releasing a pin
    // empties it), NOT the pill (whose text is a current-state reading that never goes stale).
    // Emptying announces nothing: a live region speaks on content ARRIVING, and both silence
    // tests announce first and then assert the region emptied. Converges in one pass — after
    // the clear `text === ''` and this branch cannot re-enter.
    setAnnounced({ seen: announced.seen, about: null, text: '' })
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
