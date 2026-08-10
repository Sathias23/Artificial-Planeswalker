import { useEffect, useRef } from 'react'

import { SKIP_TARGET_ID, focusHome } from '../focusHome'
import './SkipLink.css'
import { SKIP_LINK_LABEL } from './copy'

/**
 * The first Tab stop in the document — the one way past the card grid (story c4-11, UX-DR31,
 * UX-DR40, UX-DR46, UX-DR47, `DESIGN.md:418`, `EXPERIENCE.md:100`).
 *
 * ================= WHAT IT ACTUALLY BUYS, AS A MEASURED NUMBER ==========================
 *
 * Re-measured read-only over all 40 real decks at Task 0, deriving the corridor from the shipped
 * component tree rather than from any artefact: the run from the header to the first footer link
 * is **206 Tab stops** on the largest deck, median **78**, mean **102.0**. Not the *"100+"*
 * UX-DR40, UX-DR31 and `EXPERIENCE.md:143` all still said — that figure predates **c4-7**, which
 * turned every card into a second focusable row.
 *
 * This link removes the first **105** of those 206. It is a real mitigation and it is not a fix:
 * **after using it the footer is still 101 stops away**, because the deck list sits between this
 * link's target and the footer, in the very column it jumps into. **19 of 40 decks remain more
 * than 50 stops from the footer after it is used, and 36 of 40 remain more than 20.** Behind those
 * stops are exactly two links, one of them the Wizards Fan Content Policy notice that NFR-08 and
 * `DESIGN.md:419` both make *"a condition of public release, not a design choice"*.
 *
 * **That gap is not closed here, and pretending otherwise would be the failure.** UX-DR31
 * specifies ONE link; a second escape hatch is a DESIGN.md/EXPERIENCE.md amendment and a new
 * component, which is Brad's decision rather than this story's (Q1). The residue is carried with
 * those numbers on **c8-6** by name, and `validation-report-2026-07-25.md:45` already records it as
 * gate H3's still-open half.
 *
 * ================= A `<button>`, NOT AN `<a href="#…">` (Q5, AC 7, UX-DR47) =============
 *
 * The conventional skip link is an anchor, and this one is not, for two reasons that are specific
 * to this app rather than stylistic:
 *
 *   **A hash would be a navigation this app has no router for.** `#card-detail` writes a history
 *   entry and a URL the app never reads, and Back would then appear to do something.
 *
 *   **An anchor would not satisfy AC 5.** Browsers do NOT move `document.activeElement` to a
 *   non-focusable fragment target; they move the *sequential focus navigation starting point* and
 *   leave focus on `<body>`. The heading is a heading, so the imperative `tabIndex = -1` hand-off
 *   is required either way — and once it is, the `href` is decoration over the real mechanism.
 *
 * It is a real `<button>`, so **Enter and Space are the browser's** and no `onKeyDown` is written
 * — the same contract every other control in this app relies on (`FlipControl.tsx:60`,
 * `DeckList.tsx:177`, `CardTile.tsx:375`). `SkipLink.test.tsx` proves the absence rather than
 * trusting this paragraph.
 *
 * ================= ONE FOCUS HOME, AND IT WAS ALREADY BUILT (AC 5, AC 6) ================
 *
 * The target is `CardDetail`'s `<h2>` — the element whose text is the literal `PANEL_TITLE`
 * `'Card detail'`, which `CardDetail/copy.ts:18` describes as *"the element c4-11's skip link
 * moves focus to"* and pins as **the panel's name, not the card's**: a heading that changed on
 * every hover would rename a landmark forty times during one sweep of the grid, and this link's
 * target would be a name nobody could predict.
 *
 * The hand-off itself is `../focusHome` — the four lines `CardDetail` shipped first for its unpin
 * control. **There is one focus home and one implementation of it** (AC 6); this file adds a
 * caller, not a copy.
 *
 * ================= WITHDRAWAL, AND THE HALF THIS STORY CANNOT FIX (Q4, AC 9) ============
 *
 * AC 3 requires this link to be **withdrawn** when a state panel takes the left column, and AC 9
 * bans focus ever being dropped to `document.body`. Those two can contradict each other: React
 * unmounting the focused node does precisely that, and `CardDetail.tsx:385-388` records the same
 * failure being found and fixed for the unpin control.
 *
 * **The half this file owns is closed below**: if this link holds focus when it unmounts, focus is
 * handed to the `<h1>` deck name, which survives every surface change.
 *
 * **The half it does not own is stated rather than silently left open**: a *tile* or a *deck row*
 * holding focus when the deck is deleted or refetched to `no-active-deck` has the identical
 * problem, and the repair is a focus hand-off at that transition — which needs `deck_changed`,
 * an Epic 7 signal, in the story that renders the transition. Ledgered with **c7-6** named. This
 * story therefore does **not** claim the epic's AC 9 is fully covered.
 *
 * ================= WHAT IT DELIBERATELY DOES NOT DO ====================================
 *
 * **No `aria-live`, no announcement** (AC 26, Q12). The link's own accessible name is the
 * announcement. (This used to add *"`CardDetail`'s single polite region stays the only one in the
 * app"* — falsified at **c5-7**, which shipped the connection pill's, the second of the three
 * UX-DR45 authorises. The claim this component actually makes is the one above: it announces
 * nothing.)
 *
 * **No key listener of any kind.** Esc is `CardDetail`'s document-BUBBLE listener and the agent
 * view's document-CAPTURE one — the two the keyboard floor admits since c6-5 filled the
 * reservation this line used to describe (`CardDetail.tsx:88-101`). This component adds no third
 * document-level listener in either phase.
 *
 * **No store read, no derivation.** Whether it renders at all is `App.tsx`'s call, off the one
 * `surfaceOf` answer — `deck.ts:388-390` warns explicitly against a third re-derivation.
 */
export function SkipLink() {
  /**
   * Whether this element held focus, sampled while it still existed.
   *
   * The unmount cleanup below cannot ask the DOM: React has already removed the node by the time
   * a `useEffect` cleanup runs, so `document.activeElement` reads `<body>` for BOTH "this link was
   * focused and just died" and "focus was somewhere else entirely and this link was never
   * involved". Handing focus to the `h1` in the second case would YANK it away from wherever the
   * user actually was — a fix worse than the defect. So the answer is recorded on the way in,
   * from the events that know.
   *
   * A ref rather than state: nothing renders differently, and a `setState` on blur would re-render
   * this component on every focus change for no visible reason.
   */
  const heldFocus = useRef(false)

  useEffect(
    () => () => {
      // WITHDRAWAL'S FOCUS HAND-OFF (Q4a, AC 9). Only when this link was the thing that died with
      // focus on it, and only when focus actually landed nowhere — if something else has already
      // taken it, moving it again would be this component overriding a decision it did not make.
      if (!heldFocus.current) return
      if (document.activeElement !== null && document.activeElement !== document.body) return
      // The `<h1>` deck name. `AppShell.test.tsx:66` pins that there is EXACTLY ONE `h1` in the
      // document, which is what makes a document-wide query the precise selector here rather than
      // a hopeful one — and the header survives every surface change, so the target always exists.
      focusHome(document.querySelector('h1'))
    },
    [],
  )

  return (
    <button
      type="button"
      className="visually-hidden skip-link"
      onFocus={() => {
        heldFocus.current = true
      }}
      onBlur={() => {
        heldFocus.current = false
      }}
      /* NO `onKeyDown`. A real `<button>` fires `onClick` on both Enter and Space, which is AC 7,
         and `SkipLink.test.tsx` asserts the absence so a later story cannot add one "for
         keyboard support" and quietly double-fire. */
      onClick={() => {
        // The panel's frame carries `SKIP_TARGET_ID`; the panel's own `<h2>` is what takes focus.
        // Two steps rather than one because `Panel` is a primitive that may not call a hook, so it
        // can produce no `id` of its own — and a document-wide `'h2'` would find the MANA CURVE's
        // heading, since the left column precedes the right in document order.
        focusHome(document.getElementById(SKIP_TARGET_ID)?.querySelector('h2'))
      }}
    >
      {SKIP_LINK_LABEL}
    </button>
  )
}
