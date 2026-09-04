import { useEffect, useId, useState } from 'react'

import { CardPlaceholder } from '../../components/CardPlaceholder/CardPlaceholder'
import { useFaceIndex } from '../../state/faces'
import {
  clearFocused,
  clearHovered,
  setFocused,
  setHovered,
  togglePin,
  useIsLiveTarget,
} from '../../state/inspection'
import { FlipControl } from '../FlipControl/FlipControl'
import { useCardArt } from '../useCardArt'
import { useImagedFaceCount } from '../imagedFaces'
import './CardTile.css'
import { cardImageUrl } from './imageUrl'
import './QuantityBadge.css'

/**
 * One card in the art grid: the card face itself, its name beneath it, and its count
 * (FR-19, UX-DR3, UX-DR4, UX-DR7, UX-DR14, UX-DR16, UX-DR22, UX-DR36, UX-DR47).
 *
 * ================= THIS IS A CONTAINER, DELIBERATELY ===================================
 *
 * It holds state, it takes DOM events off an `<img>`, and it holds a `ref`. Every one of those
 * is banned outright for anything under `src/components/`, by four separate `it.each` blocks —
 * `shell.test.ts`'s per-primitive posture bans, and `posture.test.ts`'s cross-tree value-import
 * rule, type-only `react` rule and behaviour-family rule. So this component does not live there,
 * and `ui/tests/shell.test.ts`'s `CONTAINERS` list is the category it lives in instead, with a
 * git-derived coverage guard of its own. `ui/README.md` carries the full argument; the short
 * version is that `src/components/` stays TOTAL — "everything in this directory is
 * presentation-only" remains literally true with no exemptions — and the one hole the
 * alternative would have opened stays shut: because containers sit outside that tree, a
 * primitive that imported one is caught by `posture.test.ts`'s existing cross-tree ban, for
 * free, with no new guard and no edit.
 *
 * ================= NOTHING HERE FETCHES, AND THE ONE-DOOR LIST IS UNTOUCHED ============
 *
 * `posture.test.ts:328` reads `['src/api/client.ts']`, and this component — which puts remote
 * images on the screen — needs no entry there. That is not an oversight to explain away — an
 * `<img src>` is a fetch the BROWSER makes, through its own HTTP cache, and no code in `ui/src`
 * ever holds the bytes. There is no image cache in the SPA and there should not be one
 * (`ui/README.md`): the backend's disk cache and `IMAGE_CACHE_CONTROL`'s
 * `max-age=31536000, immutable` are the cache. "Read the response as a blob and do not derive
 * its handling from the type" is MOOT here, by construction: there is no response to read.
 *
 * ================= WHY THERE IS STATE AT ALL, AND WHY IT IS PER TILE ===================
 *
 * "Silent well" and "faded-in art" are two different renders and something has to know which.
 * There is no stateless spelling that is honest: a CSS-only fade animates on MOUNT rather than
 * on ARRIVAL, and an `<img>` that has not loaded paints nothing at all. `onLoad` is the
 * browser's only signal that the pixels exist, so the tile listens for it — and needing to is
 * exactly the category signal above.
 *
 * **The state is per tile and must not be lifted.** Ninety-nine tiles sharing one loaded-set in
 * the store would be a store write the component tree may not make (AD-12,
 * `tests/store-writes.test.ts`), and it would re-render the whole grid on every image arrival —
 * ninety-nine renders of ninety-nine tiles on the one sweep that must stay cheap.
 *
 * **The state machine lives in `../useCardArt`, shared with the detail panel.** The three
 * states, the warm/cold cache race and BOTH of its arms are identical for the panel's
 * `size=large` render, and a race that has already needed one repair must not exist in two
 * copies — that would be one copy repaired and one not. The state is still per consumer; only
 * the spelling of it is shared. Read that module's header for the whole race argument.
 *
 * ================= THE TILE SETS THE INSPECTION TARGET (UX-DR14, UX-DR20) ==============
 *
 * The `<button>` carries three handlers, and they are the whole of this component's part in the
 * inspection contract. They set a target; they do not decide anything about it, do not fetch,
 * and do not touch a store directly — `setHovered`, `clearHovered` and `togglePin` are the
 * inspection slice's verbs and the slice is where the resolution and the unknown-card refusal
 * live.
 *
 * **Focus parity is not an extra, it is the rule** (UX-DR14 — *"hover OR keyboard focus"*;
 * `EXPERIENCE.md`'s interaction primitives — *"hover is never the only way to reach
 * information"*). `onFocus`/`onBlur` do the same job as `onMouseEnter`/`onMouseLeave` **in a
 * slot of their own** (`setFocused`/`clearFocused` — with one shared slot, a `mouseleave` would
 * erase a still-focused tile's target; call that the erased-focus defect, since it recurs
 * below), and every clear names the card it is leaving so that leaving THIS tile cannot erase a
 * target the tile being reached has already set.
 *
 * **Enter and Space need no handler.** This is a real `<button>`, so the browser turns both into
 * a `click` — which is also why `EXPERIENCE.md`'s ban on double-click semantics costs nothing:
 * the second single click is a release, decided by identity inside `togglePin`.
 *
 * ================= THE TILE FLIPS (FR-04, FR-19, UX-DR15) ==============================
 *
 * **THE BUTTON IS NOT THE OUTERMOST THING, AND THAT IS DELIBERATE.** The obvious home for the
 * flip control is INSIDE this button, on a property that is genuinely load-bearing:
 * `mouseenter`/`mouseleave` do not fire between an element and its **descendants**, so a control
 * inside the button could never read as leaving the tile. What that misses is that `<button>`'s
 * content model bans interactive descendants outright. What actually happens was measured rather
 * than assumed:
 *
 *   React 19.2 emits *"In HTML, `<button>` cannot be a descendant of `<button>`."* — in the
 *   **development build only** (`grep -c` over `react-dom-client.{development,production}.js`
 *   gives 1 and 0). So the console noise never ships. What DOES ship is the tree: React builds
 *   the DOM imperatively, so there is no parser to unnest it, and a `<button>` really inside a
 *   `<button>` is not reliably exposed as a separate control by assistive technology.
 *
 * That is the deciding fact, not the content model in the abstract: an inner button would satisfy
 * every jsdom assertion in this repo and could still be unreachable by a real screen reader —
 * breaking Enter/Space activation and the control's own Tab stop on the only hardware that
 * matters, in the one direction no gate here can see.
 *
 * **So the button and the control are SIBLINGS inside `.card-tile-frame`**, and the frame's box is
 * exactly the card box (this button is `display: block; width: 100%` with `card-shape`'s aspect
 * ratio), so the hover REGION does not change at all — only which element carries the listener.
 * `onMouseEnter`/`onMouseLeave` and `onFocus`/`onBlur` move to the frame, which restores the
 * containment property one element further out: those events still do not fire when the pointer
 * moves between the frame's own children, and `focusin`/`focusout` bubble, so Tabbing from this
 * tile to its OWN control keeps the tile's inspection target instead of dropping it — the
 * erased-focus defect, one element out.
 *
 * **`onClick` stays here**, because pinning is the CARD's action and the control's click must not
 * be one. The control calls `stopPropagation()` anyway: under this shape nothing bubbles here,
 * but the guarantee is what makes the same component safe inside the detail panel's art box and
 * inside any clickable thumbnail that mounts it.
 *
 * **The cascade repair that goes with it** is in `CardTile.css`: with the control outside this
 * button, `.card-tile:hover` is FALSE while a pointer is on the control, so the hover pop and the
 * raised shadow would drop out on exactly the gesture the control exists for. Every specificity
 * in that file is preserved byte-for-byte — see its own comments.
 *
 * **The face itself is two stacked `<img>`s**, rendered only when the card is flippable, so
 * a non-flippable tile still issues exactly one image request. Which one is showing is
 * `src/state/faces.ts`'s, keyed by printing so the panel and every later thumbnail agree.
 *
 * ================= AN `onError` CARRIES NO WIRE TOKEN, AND IT DOES NOT NEED ONE ========
 *
 * `GET /api/card-image/{id}` can refuse three ways — `404 no_image_data`, `502
 * image_fetch_failed`, `503` — and a DOM `error` event carries **no status code and no token**.
 * So this tile cannot tell them apart, and it does not have to: the three draw identical pixels,
 * the only difference between them is which may ever be retried, and the SPA has no per-image
 * retry UI by design (`EXPERIENCE.md`). One render answers all three.
 *
 * **This is not the wire-token re-derivation `cards.ts` exists to prevent.** That rule is about
 * a component running
 * `switch (entry.reason)` over a WIRE TOKEN that `cards.ts` already classified into
 * `entry.placeholder`. Here there is no token to re-derive and no cache entry involved: the
 * input is a DOM event on an element this component owns. It looks like the same shape and it
 * is a different one, which is why it is written down.
 *
 * **`onError` fires once per `src`.** A re-render with the same `src` does not re-arm it — and
 * that is the correct behaviour here, because the backend answers a remembered failure from
 * memory for up to 300 seconds, and *"a tile that retries in a loop will be answered from
 * memory and change nothing"*. What it means mechanically is that the failure must live in
 * STATE rather than be recomputed, which it does.
 *
 * ================= WHAT THIS TILE DELIBERATELY DOES NOT DO =============================
 *
 * No `deck_changed` refetch, no shimmer, and **no live region of its own**: the pin
 * announcement is the DETAIL PANEL's single polite region, because ninety-nine tiles each owning
 * one is ninety-nine ways to say the same sentence. The quantity GLOW — the per-tile one-shot
 * flash below — is garnish, never a signal: the accessible carriers are the group-header counts
 * and the coalesced `deck-announcement` region, both outside this component. And
 * **no hydration** — the tile fetches nothing; whoever decides a full record is needed calls
 * `hydrateCard`, which is `App.tsx`'s after-commit deck sweep as well as the panel.
 *
 * The one cache subscription the tile does hold goes through `../imagedFaces` rather than
 * through `useCardEntry` directly: the tile has to know whether it has a back face to draw, and
 * `CardSummary` carries neither `card_faces` nor `image_uris`. That hook
 * returns a NUMBER, so zustand v5's referential comparison re-renders a tile only when its own
 * card's record lands — not all ninety-nine on every entry the sweep settles.
 */

/**
 * U+00D7 MULTIPLICATION SIGN, written as an escape so that it cannot be got wrong.
 *
 * A keyboard produces the LETTER `x`, which is a different character, renders visibly narrower
 * and lighter beside a tabular digit, and would be read aloud as a letter. DESIGN.md and
 * UX-DR16 both specify the multiplication sign; the escape is what makes a copy-paste or a
 * find-and-replace unable to substitute the letter silently. `CardTile.test.tsx` pins the
 * rendered codepoint, not the glyph.
 */
const MULTIPLICATION_SIGN = '×'

/** What the tile draws, and what it deliberately is not given. */
export interface CardTileProps {
  /**
   * `DeckCardSummary.card_id` — the printing uuid, and the image route's path parameter.
   *
   * A plain `string`, not a wire alias: `tests/wire-contract.test.ts` bans a re-declared
   * `DeckCardSummary` outside `src/api/`, and this component needs four primitive values rather
   * than a payload shape.
   */
  cardId: string
  /**
   * `CardSummary.name`, verbatim and UNSPLIT — `'X // Y'` included, for the reason
   * `CardPlaceholder` keeps it whole: four surfaces must not call one card by two names. It is
   * the caption, and it is therefore the tile's accessible name.
   */
  name?: string | null
  /** `CardSummary.mana_cost`. Reaches the screen ONLY if the image fails. */
  cost?: string | null
  /** `CardSummary.type_line`. Reaches the screen ONLY if the image fails. */
  typeLine?: string | null
  /**
   * `DeckCardSummary.quantity`. The badge renders for `> 1` and nothing else.
   *
   * Measured on the live database: **395 of 2,027** rows carry more than one copy, but only
   * **1 of 99** in the largest real deck — a Commander deck is singleton, so the badge is very
   * nearly absent from the surface this tile is built for. It is not the tile's dominant feature,
   * and it must fit **two digits** (the largest quantity anywhere is 34, a `Swamp`).
   */
  quantity?: number
}

/**
 * A string prop that is actually there, or `null`.
 *
 * The identical `typeof` + `trim()` spelling `CardPlaceholder`, `DeckBadges` and `ManaCost` all
 * use, for a measured reason: *"a presentation primitive that crashes
 * the whole app on one absent prop is the FR-13 posture inverted, and totality here costs one
 * keyword."* Truthiness is banned outright — a whitespace-only name would otherwise render a
 * present, invisible, announced-as-empty caption, which is the exact shape a placeholder exists
 * to prevent.
 */
const given = (value: string | null | undefined): string | null => {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

export function CardTile({ cardId, name, cost, typeLine, quantity }: CardTileProps) {
  // WHICH FACE, AND WHETHER THERE IS A SECOND ONE AT ALL. A tile re-renders when ITS card's
  // record lands or ITS face changes, and not otherwise — by two different mechanisms:
  // `useFaceIndex`'s selector really does return a number zustand v5 compares by value, but
  // `useImagedFaceCount` subscribes through `useCardEntry`'s per-id ENTRY selector and derives
  // its number after the comparison — the per-tile granularity is the per-id selector's, and the
  // derived count never enters any subscription comparison.
  const faceIndex = useFaceIndex(cardId)
  const imagedFaces = useImagedFaceCount(cardId)
  const flippable = imagedFaces > 1
  // `data-flipped` is a boolean but the index is not: for every printing that exists today the
  // two coincide (all 2,778 flippable cards have exactly two imaged faces, measured), and for a
  // hypothetical third face "not the front" is still the honest thing for the rotation to say
  // while the back `<img>`'s `src` follows the index.
  const flipped = flippable && faceIndex !== 0
  const backFace = faceIndex === 0 ? 1 : faceIndex

  // The three art states, the `ref` that settles a cached image and both event handlers — see
  // `../useCardArt`, shared with the detail panel's `size=large` render. DESTRUCTURED rather
  // than held as an object, and that is a lint requirement rather than a habit:
  // `react-hooks/refs` reads a member access during render as reading a ref, so
  // `art.settleIfCached` in the JSX below is an error while a plain identifier is not (measured
  // — see that module's `CardArt` docstring).
  //
  // TWO CALLS, ONE PER FACE. `?face=1` is a different URL and therefore a different
  // browser-cache entry, so the two faces load, fail and settle INDEPENDENTLY — a hook keyed on
  // `cardId` alone would leave a flipped tile at `'shown'` over bytes that had not arrived. Both
  // are called unconditionally because hooks must be; only the FLIPPABLE tile renders the second
  // `<img>`, so a single-faced card still issues exactly one request.
  //
  // BOTH DESTRUCTURED, for the same lint rule: holding each handle as an object (`front.onLoad`)
  // makes `react-hooks/refs` report every member access in the JSX as a ref read during render
  // — eight errors, measured. A plain identifier does not.
  const {
    state: frontArt,
    settleIfCached: settleFront,
    onLoad: onFrontLoad,
    onError: onFrontError,
  } = useCardArt(cardId, 0)
  const {
    state: backArt,
    settleIfCached: settleBack,
    onLoad: onBackLoad,
    onError: onBackError,
  } = useCardArt(cardId, backFace)
  // WHICHEVER FACE IS ON SCREEN GOVERNS THE WELL AND THE PLACEHOLDER. The alternative —
  // letting the FRONT decide for both — would show a silent well over a back face that had
  // already arrived, and would strand a card whose front picture failed on a placeholder it could
  // never flip out of. The control itself is a sibling of this button, so it survives the failed
  // branch replacing everything inside it, which is the other half of the same decision.
  const art = flipped ? backArt : frontArt
  // A per-tile SELECTOR rather than a prop from the grid, and this is the whole reason: it
  // returns a BOOLEAN, so zustand v5's referential comparison re-renders exactly the
  // tiles whose value flipped — two per hover — instead of all ninety-nine on every cursor
  // movement across the grid.
  const live = useIsLiveTarget(cardId)
  // `useId` — a HOOK, in a component whose caption sits OUTSIDE its button and therefore has to
  // be pointed at rather than contained. A listed primitive may not call one at all; `Panel`
  // records that exact constraint as the reason it uses `aria-label` instead. This component is
  // a container, so the hook is available and the structure below is free to be the right one.
  const captionId = useId()

  const caption = given(name)

  // `Number.isFinite`, never `quantity &&` and never `quantity ?`, and this is deliberate:
  // `{quantity && <Badge/>}` renders the bare string `0` into the DOM and `quantity ? … : null`
  // drops a real zero. The threshold here is `> 1`, which is neither — a single copy gets no
  // badge because "1" on ninety-eight of ninety-nine tiles is noise, not information.
  const copies = Number.isFinite(quantity) ? (quantity as number) : 1

  // THE ONE-SHOT ACCENT GLOW ON A CHANGED QUANTITY (UX-DR16). Per-tile state, the same shape
  // this component's header defends for its art states and for the same measured reason:
  // lifting a seen-quantity map into a store would be a write `store-writes.test.ts` bans and
  // would re-render all ~99 tiles on the one sweep that must stay cheap.
  //
  // THE CHANGE IS DETECTED AT RENDER TIME, NOT IN AN EFFECT — `ConnectionPill.tsx:86-109`'s
  // idiom, for its documented reason (`react-hooks/set-state-in-effect` rejects the effect
  // spelling, and an effect's setState is a second commit). `seen` initialises from the MOUNT
  // prop, so a freshly mounted tile never flashes: a new card's appearance is itself the signal,
  // and a grid remount must not light ninety-nine badges at once. A re-render with the same
  // quantity leaves `seen` equal and flashes nothing.
  const [flash, setFlash] = useState<{ readonly seen: number; readonly flashed: boolean }>({
    seen: copies,
    flashed: false,
  })
  if (flash.seen !== copies) setFlash({ seen: copies, flashed: true })

  // THE FLIP-OFF IS IN A FRAME CALLBACK — `AgentView.tsx:143-175`'s data-entering idiom, and the
  // same correctness point: the browser must PAINT the flashed state before the attribute drops,
  // or the two writes coalesce into one frame and no transition runs. `data-flashed` lands
  // instantly (the flashed rule carries `transition: none`), one real frame passes, the
  // attribute drops, and the badge's base transition fades `var(--glow)` out over
  // `--motion-glide`. Instant-on, eased-off, no keyframes, no loop — and under reduced motion
  // the tokens.css media block omits the glow entirely, so this state machine runs and shows
  // nothing, which is the fallback UX-DR42's inventory names.
  //
  // KEYED ON THE WHOLE FLASH OBJECT, not the boolean: each detected
  // change stores a FRESH object, so a second change landing while a flash is still pending
  // re-runs this effect — the cleanup cancels the first change's frame and a new one is armed
  // from the second change. On the boolean alone (`true` → `true`, no re-run), the FIRST
  // change's rAF would clear the SECOND change's flash early instead of giving it its own
  // full frame.
  useEffect(() => {
    if (!flash.flashed) return
    const frame = requestAnimationFrame(() =>
      setFlash((state) => (state.flashed ? { seen: state.seen, flashed: false } : state)),
    )
    return () => cancelAnimationFrame(frame)
  }, [flash])

  const captioned = art !== 'failed' && caption !== null
  const badgeId = `${captionId}-n`
  // The elements that NAME the button, in reading order. `undefined` on the failed path and on a
  // nameless card, so the accessible name falls back to the button's own contents rather than to
  // a dangling reference — an `aria-labelledby` pointing at no element leaves a control unnamed.
  const labelledBy = captioned ? (copies > 1 ? `${captionId} ${badgeId}` : captionId) : undefined

  return (
    <>
      {/* THE FRAME. It exists for ONE reason and carries no appearance of its own: the
          flip control is a `<button>` and so is the tile, and an interactive descendant of a
          `<button>` is invalid HTML that React 19.2 warns about in development and that assistive
          technology does not reliably expose as a separate control (both measured — see the
          header). So the two are SIBLINGS, and something has to hold them.

          Its box is exactly the card box, because the button below is `display: block` at
          `width: 100%` with `card-shape`'s aspect ratio — so pinning the control to this element's
          top-left inside `--space-2` is pinning it to the CARD's top-left, which is DESIGN.md's
          words, and the hover REGION is exactly the card.

          THE POINTER AND FOCUS HANDLERS LIVE HERE, AND THE CLICK DOES NOT. `mouseenter`/
          `mouseleave` do not fire when the pointer moves between this element's own children, so
          reaching the control never reads as leaving the tile — the containment a control INSIDE
          the button would have had, restored one element further out. `focusin`/`focusout`
          (React's `onFocus`/`onBlur`) bubble, so Tabbing from the tile to its OWN control keeps
          the tile's inspection target rather than dropping it: the erased-focus defect the header
          names, one element out. `onClick` stays on the button, because pinning is the card's
          action and the flip must not be one. */}
      <div
        className="card-tile-frame"
        onMouseEnter={() => setHovered(cardId)}
        onMouseLeave={() => clearHovered(cardId)}
        onFocus={() => setFocused(cardId)}
        onBlur={() => clearFocused(cardId)}
      >
        {/* THE BUTTON **IS** THE CARD, AND THAT IS A REPAIR THE EYE-CHECK FORCED.
          Wrapping the art and the caption in one button and drawing the focus ring on an inner
          frame shows, in a real browser with a real keyboard focus, TWO indicators at once: the
          composite ring hugging the card's rounded corners, and the
          browser's OWN focus ring as a sharp-cornered rectangle around card-plus-caption.
          Nothing here may write `outline: none` in any spelling (UX-DR46, and stylelint bans
          all four), so the UA ring cannot be removed — but an AUTHORED outline replaces it, and
          an authored outline is only the right shape if the focused element is the card itself.

          So the button carries `card-shape`, and the caption is its SIBLING, pointed at by
          `aria-labelledby`. Three things fall out, all of them improvements:
            - the outline hugs the same rounded rectangle the composite does, and is given the
              same width and colour tokens, so the two coincide instead of competing;
            - `--shadow-rest`, `overflow: hidden` and the ring all live on one element rather
              than on a wrapper invented to hold them;
            - the hover pop scales the CARD FACE while the caption stays put and legible.

          `aria-labelledby` on the FAILED path is deliberately absent: there is no caption to
          point at, and the accessible name falls back to the button's contents — which is the
          named placeholder, already naming the card exactly once. */}
        <button
          type="button"
          /* `is-live` is the class DESIGN.md's `components.card-tile.live-ring` hangs on, and it
           is the ONLY thing this component does with its liveness — the ring itself is
           `--shadow-live-ring` in CardTile.css, because a composite box-shadow cannot be
           written in a component stylesheet at all (stylelint's allowed-list). */
          className={live ? 'card-shape card-tile is-live' : 'card-shape card-tile'}
          aria-labelledby={labelledBy}
          /* THE INSPECTION CONTRACT, AND NOTHING ELSE (UX-DR14, UX-DR20). Four handlers,
           no decisions: what an id MEANS — whether it can be inspected at all, whether a click
           pins or releases, what wins between hover and pin — belongs to the slice, so that
           the deck rows and the agent view's thumbnails get the identical behaviour from the
           identical verbs rather than from four copies of a rule.

           HOVER AND FOCUS ARE THE SAME CONTRACT IN TWO SLOTS, which is UX-DR14 read literally
           ("hover OR keyboard focus") and `EXPERIENCE.md`'s "hover is never the only way to
           reach information". Each modality writes its OWN slot (one shared slot would let a
           `mouseleave` erase a still-focused tile's target), and each leave-handler
           names the card it is leaving, so that a `blur` landing after the next tile's
           `focus` cannot erase a target that tile has already set (see `clearHovered` /
           `clearFocused`).

           NO `onKeyDown`. This is a real `<button>`, so the browser already turns Enter and
           Space into a `click` — which is also what makes "release is a second SINGLE click"
           free rather than something to implement (double-click semantics are banned outright,
           `EXPERIENCE.md`).

           THE POINTER AND FOCUS HANDLERS ARE ON THE FRAME ABOVE, NOT HERE, because the flip
           control is a SIBLING of this button rather than a descendant of it. `onClick` stays,
           because pinning is the card's action; the control calls `stopPropagation()` for the
           ancestors that are clickable elsewhere. */
          onClick={() => togglePin(cardId)}
        >
          {art === 'failed' ? (
            /* THE NAMED PLACEHOLDER, from the props the deck payload already carried. Not from
             `entry.placeholder` and not from a wire token — see the header.
             ON THE SHOWN FACE: a card whose BACK picture failed draws this while
             flipped and its own face while not, because `?face=1` is a different negative-cache
             key and the two faces genuinely fail independently. The flip control survives this
             branch — it is outside this button — so a failed face can always be flipped out of. */
            <CardPlaceholder variant="named-card" name={name} cost={cost} typeLine={typeLine} />
          ) : (
            <>
              {/* THE SILENT WELL, until the pixels exist. It is a SIBLING the image covers
                rather than a background under it, deliberately: a `--surface-well`
                painted on the same element would sit under a card face whose PNG corners are
                transparent, which DESIGN.md explicitly cares about ("png faces with
                transparent corners sit flush"). */}
              {art === 'loading' ? <CardPlaceholder variant="loading" /> : null}
              {/* THE TWO STACKED FACES. `data-flipped` is present only when there
                IS a second face, which is what scopes the 3D machinery to the 42 flippable rows
                in the 40 real decks rather than putting a `preserve-3d` context on all ninety-nine
                tiles. The rotation, the `backface-visibility` and the reduced-motion fallback all
                live in FlipControl.css and tokens.css — this component chooses the FACE and
                nothing about how it arrives. */}
              <div className="card-faces" data-flipped={flippable ? String(flipped) : undefined}>
                <img
                  ref={settleFront}
                  className="card-tile-image card-face is-front"
                  data-loaded={frontArt === 'shown' ? 'true' : 'false'}
                  src={cardImageUrl(cardId)}
                  /* `alt=""`, and it is deliberate rather than a default. UX-DR48 keeps
                   `alt={name}` on grid tiles *"because there the image is the only carrier"* —
                   and for THIS component that premise is measurably false: UX-DR14 puts the same
                   name in a caption directly beneath the art, and `aria-labelledby` makes that
                   caption the button's accessible name. With `alt={name}` as well, a
                   screen-reader user would hear "Black Lotus Black Lotus". This tile has exactly
                   the structure UX-DR48's OTHER clause describes for row thumbnails — *"use
                   `alt=""` — the name is announced once, from the row text"* — so the rule's own
                   logic is applied rather than its letter. `CardTile.test.tsx` proves the
                   accessible name carries the name exactly once.

                   A DECLARED RESIDUE: while a DFC shows its back face, this tile's caption still
                   reads the printing's COMBINED name (`Clearwater Pathway // Murkwater Pathway`)
                   while the art shows one half. The panel's heading follows the face; the
                   caption does not. The pin announcement carries the same divergence, one
                   surface further — a manual-testing check, not a jsdom assertion. */
                  alt=""
                  /* All ~99 mount at once.
                   `decoding="async"` keeps decode off the main thread; `loading="lazy"` is
                   DELIBERATELY ABSENT — the grid is the app's primary surface and a
                   scroll-triggered second fill pattern is one the UX inventory never describes.
                   Lowercase DOM attributes, passed through unchanged by React 19; the one that
                   would need camelCase is `fetchPriority`, and this tile sets none. */
                  decoding="async"
                  onLoad={onFrontLoad}
                  onError={onFrontError}
                />
                {flippable ? (
                  /* THE BACK FACE, RENDERED ONLY WHEN THERE IS ONE. Measured: this costs 6 extra
                   images on the 99-card Atraxa deck, 1 on `Prismatic Dragon`, and 42 across all
                   40 real decks — the price of the flip being WARM and INSTANT rather than a
                   cold fetch at the rotation's midpoint, which would have needed a JS timer.

                   `?face=` follows the INDEX rather than being pinned to 1, so a hypothetical
                   third face swaps this element's `src` while the rotation stays put — and for
                   every printing that exists today `backFace` is the constant 1, which keeps
                   this URL a stable browser-cache key. */
                  <img
                    ref={settleBack}
                    className="card-tile-image card-face is-back"
                    data-loaded={backArt === 'shown' ? 'true' : 'false'}
                    src={cardImageUrl(cardId, undefined, backFace)}
                    alt=""
                    decoding="async"
                    onLoad={onBackLoad}
                    onError={onBackError}
                  />
                ) : null}
              </div>
            </>
          )}
          {copies > 1 ? (
            /* THE QUANTITY BADGE (UX-DR3, UX-DR16). Top-RIGHT: the flip control owns the
             top-left and the two must never collide.

             IT IS NAMED RATHER THAN HIDDEN. UX-DR16 delegates the accessible quantity signal to
             "the group-header count and the coalesced live-region announcement", and both of
             those carriers exist (the group-header counts and the `deck-announcement` region) —
             the badge stays in `aria-labelledby` anyway, because hiding it would change the name
             a reader knows this control by, for zero user gain. Its id joins `aria-labelledby`
             above, which also fixes the reading ORDER: name first, then count, rather than the
             DOM order a name-from-contents would have imposed. No authored string is involved,
             so no COPY_MODULES entry is owed.

             `data-flashed` is the one-shot glow's state attribute (UX-DR16): present for
             exactly one frame after a quantity CHANGE — see the flash state above — and absent
             otherwise, so QuantityBadge.css's flashed rule is entered and left rather than
             animated. The attribute is presentation only; nothing accessible hangs on it. */
            <span
              id={badgeId}
              className="card-tile-quantity"
              data-flashed={flash.flashed ? 'true' : undefined}
            >{`${MULTIPLICATION_SIGN}${copies}`}</span>
          ) : null}
        </button>
        {/* THE FLIP CONTROL. A SIBLING of the button, immediately after it in DOM order — which
            is the whole of UX-DR40's *"immediately after its own tile"* Tab stop, asserted as
            document order rather than as a `tabindex`. It renders `null` for the 35,483 cards
            that are not flippable, so the Tab order of an ordinary deck is unchanged by it.

            It takes only a `cardId`: the predicate, the material, the glyph and the label are all
            its own, and the panel mounts the identical component against its art box. */}
        <FlipControl cardId={cardId} />
      </div>
      {/* THE CAPTION (UX-DR14).

          NOT RENDERED BESIDE THE NAMED PLACEHOLDER, which is the path it is easiest to forget.
          The named placeholder centres the card's name inside the card box — so a caption
          underneath would put the SAME NAME ON THE TILE TWICE, visibly, and announce it twice
          inside one `<button>`. The name is announced once; the failed path is the same question
          with a different carrier, so it gets the same answer: whichever element is naming the
          card, only one of them does.

          OUTSIDE THE FRAME, not merely outside the button — so the hover region stays the CARD
          rather than growing to include a line of text below it. It is the button's accessible
          name by reference rather than by
          containment, which is what lets the focus ring be the card's shape rather than a
          rectangle around card-plus-text.

          Rendered only when there is a name to render, for the rest: `filled`-style totality
          rather than a present, invisible, announced-as-empty element. Measured: 0 of the 1,061
          distinct cards across all 40 real decks lack a name, so that branch has no live
          population — it is the FR-13 posture, not a case being handled. */}
      {captioned ? (
        <span id={captionId} className="card-tile-caption">
          {caption}
        </span>
      ) : null}
    </>
  )
}
