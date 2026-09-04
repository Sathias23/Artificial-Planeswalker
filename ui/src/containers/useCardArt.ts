import { useCallback, useState } from 'react'

/**
 * Whether a card's picture has arrived, failed, or is still in flight — and the two `<img>`
 * traps that make knowing it harder than it looks.
 *
 * ================= WHY THIS IS A MODULE OF ITS OWN, AND NOT A COPY =====================
 *
 * Two consumers draw the same card face: the grid tile, and the detail panel at `size=large`.
 * Both need exactly the same three states and exactly the same two race repairs. Two copies of a
 * subtle race fix is one copy that will be repaired and one that will not. So it lives here.
 *
 * The precedent for a shared helper living at the ROOT of a tree rather than inside one member
 * is `src/components/filled.ts`, whose own header states the rule: *"a helper shared by two
 * components does not live inside one of them"*. `shell.test.ts`'s `CONTAINERS` guard globs
 * `src/containers/*.ts`, so this module is covered by the same coverage guard and the same
 * posture as the components beside it, with its own exhaustive import list.
 *
 * ================= THE WARM-CACHE RACE, WHICH IS THE NORMAL PATH IN THE GRID ===========
 *
 * A successful image is served `Cache-Control: public, max-age=31536000, immutable`, so every
 * render after the first is a browser-cache hit and the `load` event can be dispatched **before
 * React has anything listening**. A component that could only leave `'loading'` from an `onLoad`
 * callback would show a silent well forever, on exactly the path NFR-05's one-second warm render
 * describes — the happy case failing while the cold case works.
 *
 * {@link CardArt.ref} closes it by ASKING THE ELEMENT instead of waiting for the event, which is
 * the standard mitigation and is why a `ref` is needed at all — one of the four independent
 * reasons a card tile cannot be a listed primitive.
 *
 * **Both arms, not one.** The mirror of a cached success is a cached FAILURE: a refusal answered
 * instantly — the backend's negative cache holds one in memory for up to 300 s — can dispatch
 * `error` before React is listening, exactly as a warm hit can
 * dispatch `load`. A settle that only knew the success half would leave that element on the
 * silent well forever, with the named placeholder AD-11 promises unreachable. `complete` is true
 * for a broken image too; `naturalWidth` is what says which kind of settled this is.
 *
 * **The detail panel inherits both arms at a DIFFERENT CACHE KEY, and the balance inverts.**
 * `?size=large`
 * is a different URL and therefore a different cache entry, so the detail art is **cold on first
 * inspection even when the grid is fully warm**. In the panel the cold path is the common one
 * and the warm path is the second look at the same card; in the grid it is the other way round.
 * Same code, opposite weighting — stated because it changes what a reader should expect to see.
 *
 * ================= AND A FLIP MAKES THE KEY TWO VALUES ==================================
 *
 * Keying on `cardId` alone stops being enough the day a face can change. `?face=1` is a
 * **different URL and therefore a different browser-cache entry**, so the first flip of any card
 * is always a cold fetch — while `cardId` has not changed, so a `cardId`-keyed state machine
 * would not re-arm. Two failures follow from one line, and both are the kind a screenshot passes:
 *
 *   A flipped tile would sit at `'shown'` over an `<img>` whose new `src` had not arrived — the
 *   OLD face at full opacity, with no silent well, until the new bytes landed and swapped under
 *   the reader.
 *
 *   Worse, a tile whose FRONT art had `'failed'` renders `CardPlaceholder` **instead of** the
 *   `<img>` — so there would be no element for a flip to change at all, and a card whose back
 *   face is perfectly servable could never be reached.
 *
 * So the identity of a picture is `(cardId, face)`, not `cardId`, and {@link useCardArt} takes
 * both. Everything else is unchanged: the reset is still the render-time adjustment React
 * documents, and BOTH cached arms still settle — at the new key, which is the half that makes a
 * warm second flip instant rather than stuck on a well.
 *
 * ================= WHAT jsdom CAN SEE OF ANY OF THIS: NOTHING =========================
 *
 * jsdom loads no images, fires no `load`/`error`, and reports `naturalWidth: 0` always — so the
 * settle is INERT there in both directions, which is what lets the well assertions in the two
 * component suites mean anything. Events are DISPATCHED (`fireEvent.load(img)`), never awaited.
 * The claim this module actually makes is UNPROVABLE in the suite and is checked by eye against
 * a warm browser cache.
 */

/**
 * Whether the image has arrived, failed, or is still in flight.
 *
 * A three-state union rather than two booleans, because `loading && failed` is a state that
 * cannot happen and a pair of booleans is a pair that can express it.
 */
export type ArtState = 'loading' | 'shown' | 'failed'

/**
 * What a consumer attaches to its `<img>`, plus the state it draws from.
 *
 * **A CONSUMER DESTRUCTURES THIS AT THE TOP OF ITS RENDER, and that is a lint requirement rather
 * than a style.** `react-hooks/refs` treats a member access on an object during render as
 * reading a ref, so `<img ref={art.settleIfCached} onLoad={art.onLoad}>` is four ESLint errors —
 * measured, on the first run of this extraction. Destructuring produces plain identifiers and
 * the rule has nothing to look at. The field is `settleIfCached` rather than `ref` for the same
 * reason, one step earlier: a property literally named `ref` is what put the rule on the scent.
 */
export interface CardArt {
  /** Which of the three states this card's picture is in. */
  readonly state: ArtState
  /** The `ref` callback that settles a picture the browser had already finished with. */
  readonly settleIfCached: (node: HTMLImageElement | null) => void
  /** `<img onLoad>`. */
  readonly onLoad: () => void
  /** `<img onError>`. */
  readonly onError: () => void
}

/**
 * Track one card's picture.
 *
 * **The verdict belongs to the CARD, not to the slot.** A consumer
 * handed a different `cardId` on the same mount would otherwise keep the old card's `'failed'`
 * (a placeholder for a card whose picture is fine) or its `'shown'` (opacity 1 over pixels that
 * have not arrived). That is the ordinary case in the detail panel, where ONE mounted component
 * shows a different card on every hover — so the reset below is not a defensive edge case here,
 * it is the main path.
 *
 * It is a render-time adjustment, which is what React documents for exactly this — during
 * render, BEFORE the new `src` ever commits, so no cached `load`/`error` for the old card can
 * race it the way an effect could be raced.
 *
 * Args:
 *   cardId: The Scryfall printing uuid whose picture is being drawn. Changing it re-arms.
 *   face: Which of that card's IMAGES is being drawn, zero-based. Changing it
 *     re-arms too, because `?face=1` is a different URL and therefore a different cache entry —
 *     see the header. Defaults to `0`, so every caller that draws one face only is unchanged and
 *     needs no edit.
 *
 * Returns:
 *   The {@link CardArt} handle. Nothing here issues a request: the fetch is the BROWSER's, made
 *   by the `<img src>` the consumer renders, which is why `posture.test.ts`'s one-door list
 *   still reads `['src/api/client.ts']` with no edit.
 */
export const useCardArt = (cardId: string, face = 0): CardArt => {
  // ONE STRING RATHER THAN TWO STATES, so the reset below stays a single comparison and cannot
  // half-fire. The `cardId` here is the RAW store id — encoding happens later, in `cardImageUrl`,
  // and ids carry no shape constraint — so a `#` in an id is expressible and the separator does
  // not pretend otherwise. What bounds the risk: `face` is a small integer, so two keys collide
  // only if one id textually ends in the other plus `#<digit>` — and the key never reaches a URL
  // at all, so even that collision would only cost a missed re-arm rather than a wrong request.
  const key = `${cardId}#${face}`
  const [state, setState] = useState<ArtState>('loading')
  const [artFor, setArtFor] = useState(key)

  if (artFor !== key) {
    setArtFor(key)
    setState('loading')
  }

  // `useCallback` with no dependencies is what keeps the identity stable, so React attaches this
  // ONCE rather than detaching and re-attaching it on every state change — which would call it
  // again with the same node and make the reasoning above harder than it is.
  const settleIfCached = useCallback((node: HTMLImageElement | null) => {
    if (node === null) return
    if (!node.complete) return
    setState(node.naturalWidth > 0 ? 'shown' : 'failed')
  }, [])

  const onLoad = useCallback(() => setState('shown'), [])
  // `onError` fires once per `src`. A re-render with the same `src` does not re-arm it — and
  // that is correct here, because the backend answers a remembered failure from memory for up to
  // 300 seconds: "a tile that retries in a loop will be answered from memory and change
  // nothing". What it means mechanically is that the failure must live in STATE rather than be
  // recomputed, which is what this hook is.
  const onError = useCallback(() => setState('failed'), [])

  return { state, settleIfCached, onLoad, onError }
}
