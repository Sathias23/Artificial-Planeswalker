import { flipCard, useFaceIndex } from '../../state/faces'
import { useImagedFaceCount } from '../imagedFaces'
import './FlipControl.css'
import { FLIP_LABEL } from './copy'

/**
 * The control that turns a double-faced card over — *"the densest single component in the
 * feature"* (FR-04, FR-19, UX-DR7, UX-DR15, UX-DR40, UX-DR41, UX-DR45, UX-DR47).
 *
 * ================= ONE COMPONENT, MOUNTED TWICE ========================================
 *
 * UX-DR15 requires the detail panel to carry *"its own copy of the control at the same spec"*.
 * Two components would be two chances to drift on a spec with a dozen rules, so this is ONE — and
 * the *"does this card get a control?"* question is asked in exactly one place, here, by returning
 * `null`. Both mounts pass a `cardId` and nothing else; neither is told where it is, which is what
 * lets any further mount — an agent-view thumbnail, say — happen without an API change.
 *
 * ================= IT IS A CONTAINER, AND IT IS ALSO A SIBLING =========================
 *
 * A container because it attaches a handler and reads two stores, every one of which is banned
 * outright under `src/components/` (`shell.test.ts`'s per-primitive posture).
 *
 * A **sibling** of the tile's `<button>` rather than a child of it, and that is deliberate. The
 * tempting home is INSIDE that button, because `mouseenter`/`mouseleave` do not fire between an
 * element and its descendants — so a control inside the button could never read as leaving the
 * tile. But `<button>`'s content model bans interactive descendants outright, and measurement says
 * what actually happens:
 *
 *   React 19.2 emits `"In HTML, <button> cannot be a descendant of <button>."` — **in the
 *   development build only** (`grep -c` over `react-dom-client.{development,production}.js`
 *   gives 1 and 0), so the console noise never ships. What DOES ship is the tree: React builds
 *   the DOM imperatively, so unlike a parsed document there is no parser to unnest it, and a
 *   `<button>` genuinely inside a `<button>` is not reliably exposed as a separate control by
 *   assistive technology.
 *
 * That is what decides it. An inner button would satisfy every jsdom assertion in this file and
 * could still be unreachable by a real screen reader — breaking Enter, Space and its Tab stop on
 * the only hardware that matters, in the one direction no gate here can see. So
 * `CardTile` renders a positioned `.card-tile-frame` holding the button and this control as
 * siblings, and moves its POINTER and FOCUS handlers to that frame — which restores the
 * containment property the original design was reaching for, one element further out. See
 * `CardTile.tsx` for the cascade repair that goes with it.
 *
 * ================= A FLIP IS NOT AN INSPECTION =========================================
 *
 * Stated twice elsewhere (`inspection.ts:43-54`, `CardTile.tsx:86-92`): this control touches
 * **none** of `setHovered` / `clearHovered` /
 * `setFocused` / `clearFocused` / `togglePin` / `clearPin`. It imports the inspection slice not at
 * all, which is the strongest available form of that claim — there is no verb in scope to call by
 * accident. `FlipControl.test.tsx` asserts it against the SLICE's whole state rather than against
 * a spy, because a spy only proves that the function somebody thought to watch went uncalled.
 *
 * The `stopPropagation()` below is the second half. Under the sibling shape nothing bubbles to the
 * tile's button anyway — but the control is mounted inside `.card-detail-art` today and may be
 * mounted inside a clickable thumbnail later, and a guarantee is worth more than the current
 * geometry's accident.
 *
 * ================= NO `onKeyDown`, AND ITS ABSENCE IS TESTED ===========================
 *
 * This is a real `<button>` (UX-DR47, unconditional), so the browser already turns Enter and Space
 * into a `click`. A `keydown` handler beside that is not a belt-and-braces addition — it fires the
 * flip TWICE for one Space and lands back on the face it started from.
 *
 * ================= WHAT IT DELIBERATELY DOES NOT DO ====================================
 *
 * **No live region and no announcement.** UX-DR45 enumerates them — the connection pill, the
 * agent-view heading, the detail panel's separate polite pin region — and a flip is not among
 * them; transient changes must not flood the queue. `aria-pressed` gives a keyboard user the state
 * with no region and no second string.
 *
 * **No fetch, and no URL.** It writes a face index; `cardImageUrl` is where that becomes a
 * request, in the two components that draw a picture. The one door is still `src/api/client.ts`.
 *
 * **No knowledge of what a card IS.** The imaged-face count comes from `../imagedFaces`, the one
 * mirror of `resolve_face_images`, so this file spends no predicate of its own.
 */

/** What the control needs, and it is deliberately one value. */
export interface FlipControlProps {
  /**
   * The Scryfall printing uuid — the key the face store, the card cache and the image route all
   * use, and the whole of *"flip state is keyed by printing rather than by location"* (UX-DR15).
   *
   * A plain `string`, not a wire alias: `tests/wire-contract.test.ts` bans a re-declared wire shape
   * outside `src/api/`, and this component needs one primitive rather than a payload.
   */
  cardId: string
}

export function FlipControl({ cardId }: FlipControlProps) {
  // Both hooks run before the early return, which is React's rule and not a preference: a card
  // that becomes flippable when the deck sweep lands must re-render this component, and it can
  // only do that if the subscription was already there while the answer was still `null`.
  const imagedFaces = useImagedFaceCount(cardId)
  const faceIndex = useFaceIndex(cardId)

  // THE ONE PLACE THE QUESTION IS ASKED. `> 1` rather than `> 0`: a card with exactly
  // one picture has nothing to flip TO, which is 35,483 of the corpus's 38,261 rows — every
  // ordinary card, every split and adventure card, and the whole 79-row placeholder population.
  if (imagedFaces < 2) return null

  return (
    <button
      type="button"
      className="flip-control"
      /* The accessible name, from `./copy` and therefore from `COPY_MODULES`. STATIC: a name
         that named the target face would put card DATA into a read-aloud attribute, which is
         exactly what `copy-rules.test.ts`'s attribute half collects. The state travels on
         `aria-pressed` instead. */
      aria-label={FLIP_LABEL}
      /* A TOGGLE BUTTON. `aria-pressed` is what tells a keyboard user which face is
         showing without a live region and without a second announcement — UX-DR45's regions are
         enumerated and a flip is not one of them. `!== 0` rather than a boolean in the store,
         because the store holds an INDEX and the pressed state is a projection of it: for
         every printing that exists today the two coincide, and the day one does not, "not the
         front face" is still the honest thing to say. */
      aria-pressed={faceIndex !== 0}
      onClick={(event) => {
        // See the header: under the sibling shape nothing bubbles to the tile's button, so this
        // is the guarantee for the ancestors that DO exist (the panel's art box) and any that
        // may (a clickable thumbnail) rather than a description of today's geometry.
        event.stopPropagation()
        // The count is passed rather than looked up, so the `resolve_face_images` mirror has one
        // home. The slice does the modulo, which is also what makes two rapid clicks advance twice
        // rather than both reading the same "current" face.
        flipCard(cardId, imagedFaces)
      }}
    >
      {/* THE FIRST INLINE `<svg>` IN `ui/src`, AND ITS CONVENTIONS ARE SET HERE.
          DESIGN.md asks for "a stroke-based two-arrow rotate glyph … a plain UI glyph, never
          anything that could read as a mana or set symbol" (UX-DR7) and specifies nothing else —
          no viewBox, no stroke width, no size. So each of those is a decision, recorded:

            `viewBox="0 0 24 24"` — the ordinary UI-icon grid, and the one that makes a 2px stroke
            read as a hairline at the 18px this renders at.
            `fill="none"` + `stroke="currentColor"` — the STRUCTURAL half of "could never read as
            a mana or set symbol": both of those are FILLED marks, and this app already draws a
            filled circle that means something else entirely (`ManaPip`). `currentColor` is also
            what lets the stylesheet tint the glyph with one `color` declaration on hover.
            `strokeWidth="2"`, round caps and joins — a soft, unmistakably-chrome line.

          The MARK is two 180° arcs chasing each other with an arrowhead at each end, drawn with
          visible gaps on both sides so that it never closes into a circle. A closed circle is
          exactly the silhouette UX-DR7 bans.

          `aria-hidden` because the control's name is the authored one on the button; a titled
          glyph would be the name announced twice inside one control. There is no `<title>` and no
          text node here, which `FlipControl.test.tsx` asserts.

          The two shipped "no `<svg>` in this subtree" assertions (`StatePanel.test.tsx:61`,
          `CardPlaceholder.test.tsx:81`) are about OTHER components and stay green. No tree-wide
          ban joins them, deliberately: a rule against `<svg>` in `src/components/` would fall
          hardest on the one category that could legitimately own an icon later. */}
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M5 11a7 7 0 0 1 14 0" />
        <path d="M16 8l3 3 3-3" />
        <path d="M19 13a7 7 0 0 1-14 0" />
        <path d="M8 16l-3-3-3 3" />
      </svg>
    </button>
  )
}
