import { useId } from 'react'

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
 * (story c4-4, FR-19, UX-DR3, UX-DR4, UX-DR7, UX-DR14, UX-DR16, UX-DR22, UX-DR36, UX-DR47).
 *
 * ================= THIS IS A CONTAINER, AND THAT IS THE STORY'S FIRST RULING (Q1) ======
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
 * `posture.test.ts:328` still reads `['src/api/client.ts']` with no edit, in the first story
 * that puts remote images on the screen. That is not an oversight to explain away — an
 * `<img src>` is a fetch the BROWSER makes, through its own HTTP cache, and no code in `ui/src`
 * ever holds the bytes. There is no image cache in the SPA and there should not be one
 * (`ui/README.md`): the backend's disk cache (c3-7) and `IMAGE_CACHE_CONTROL`'s
 * `max-age=31536000, immutable` (c3-5) are the cache. The consequence for the blind-spot row
 * that told c4-4 to "read the response as a blob and not derive its handling from the type" is
 * that it is MOOT here, by construction, and the record says so rather than leaving it ticked.
 *
 * ================= WHY THERE IS STATE AT ALL, AND WHY IT IS PER TILE (Q8) ==============
 *
 * "Silent well" and "faded-in art" are two different renders and something has to know which.
 * There is no stateless spelling that is honest: a CSS-only fade animates on MOUNT rather than
 * on ARRIVAL, and an `<img>` that has not loaded paints nothing at all. `onLoad` is the
 * browser's only signal that the pixels exist, so the tile listens for it — and needing to is
 * exactly the category signal above.
 *
 * **The state is per tile and must not be lifted.** Ninety-nine tiles sharing one loaded-set in
 * the store would be a store write this story is not allowed to make (AD-12,
 * `tests/store-writes.test.ts`), and it would re-render the whole grid on every image arrival —
 * ninety-nine renders of ninety-nine tiles on the one sweep the epic wants to be cheap.
 *
 * **It now lives in `../useCardArt`, and that is a MOVE rather than a change** (c4-5). The
 * three states, the warm/cold cache race and BOTH of its arms are identical for the detail
 * panel's `size=large` render, and this particular fix has already been repaired once — two
 * copies would be one copy repaired and one not. The state is still per consumer; only the
 * spelling of it is shared. Read that module's header for the whole race argument, which used
 * to live here.
 *
 * ================= AND NOW THE TILE RESPONDS (c4-5, UX-DR14, UX-DR20) ==================
 *
 * The `<button>` c4-4 shipped with no handler at all has three now, and they are the whole of
 * this component's part in the inspection contract. They set a target; they do not decide
 * anything about it, do not fetch, and do not touch a store directly — `setHovered`,
 * `clearHovered` and `togglePin` are the inspection slice's verbs and the slice is where the
 * resolution and the unknown-card refusal live (c4-5's Q8 and AC 17).
 *
 * **Focus parity is not an extra, it is the rule** (UX-DR14 — *"hover OR keyboard focus"*;
 * `EXPERIENCE.md`'s interaction primitives — *"hover is never the only way to reach
 * information"*). `onFocus`/`onBlur` do the same job as `onMouseEnter`/`onMouseLeave` **in a
 * slot of their own** (`setFocused`/`clearFocused` — PR #44's P1: with one shared slot, a
 * `mouseleave` erased a still-focused tile's target), and every clear names the card it is
 * leaving so that leaving THIS tile cannot erase a target the tile being reached has already
 * set.
 *
 * **Enter and Space need no handler.** This is a real `<button>`, so the browser turns both into
 * a `click` — which is also why `EXPERIENCE.md`'s ban on double-click semantics costs nothing:
 * the second single click is a release, decided by identity inside `togglePin`.
 *
 * ================= AND NOW THE TILE FLIPS (c4-6, FR-04, FR-19, UX-DR15) ================
 *
 * **THE BUTTON IS NO LONGER THE OUTERMOST THING, AND THAT IS c4-6's SHARPEST RULING (Q2).**
 * Four shipped comments — including the one that used to stand here — reserved the flip control's
 * home INSIDE this button, on a property that is genuinely load-bearing:
 * `mouseenter`/`mouseleave` do not fire between an element and its **descendants**, so a control
 * inside the button could never read as leaving the tile. What none of them priced is that
 * `<button>`'s content model bans interactive descendants outright. Task 0 measured what actually
 * happens rather than assuming it:
 *
 *   React 19.2 emits *"In HTML, `<button>` cannot be a descendant of `<button>`."* — in the
 *   **development build only** (`grep -c` over `react-dom-client.{development,production}.js`
 *   gives 1 and 0). So the console noise never ships. What DOES ship is the tree: React builds
 *   the DOM imperatively, so there is no parser to unnest it, and a `<button>` really inside a
 *   `<button>` is not reliably exposed as a separate control by assistive technology.
 *
 * That is the deciding fact, not the content model in the abstract: an inner button would satisfy
 * every jsdom assertion in this repo and could still be unreachable by a real screen reader —
 * breaking c4-6's AC 7 (Enter and Space) and AC 8 (its Tab stop) on the only hardware that
 * matters, in the one direction no gate here can see.
 *
 * **So the button and the control are SIBLINGS inside `.card-tile-frame`**, and the frame's box is
 * exactly the card box (this button is `display: block; width: 100%` with `card-shape`'s aspect
 * ratio), so the hover REGION does not change at all — only which element carries the listener.
 * `onMouseEnter`/`onMouseLeave` and `onFocus`/`onBlur` move to the frame, which restores the
 * containment property one element further out: those events still do not fire when the pointer
 * moves between the frame's own children, and `focusin`/`focusout` bubble, so Tabbing from this
 * tile to its OWN control keeps the tile's inspection target instead of dropping it — PR #44's P1
 * defect, one element out.
 *
 * **`onClick` stays here**, because pinning is the CARD's action and the control's click must not
 * be one. The control calls `stopPropagation()` anyway (its AC 6): under this shape nothing
 * bubbles here, but the guarantee is what makes the same component safe inside the detail panel's
 * art box today and inside c6-5's clickable thumbnails later.
 *
 * **The cascade repair that goes with it** is in `CardTile.css`: with the control outside this
 * button, `.card-tile:hover` is FALSE while a pointer is on the control, so the hover pop and the
 * raised shadow would drop out on exactly the gesture the control exists for. Every specificity
 * in that file is preserved byte-for-byte — see its own comments.
 *
 * **The face itself is two stacked `<img>`s** (Q10), rendered only when the card is flippable, so
 * a non-flippable tile still issues exactly one image request. Which one is showing is
 * `src/state/faces.ts`'s, keyed by printing so the panel and every later thumbnail agree.
 *
 * ================= AN `onError` CARRIES NO WIRE TOKEN, AND IT DOES NOT NEED ONE ========
 *
 * `GET /api/card-image/{id}` can refuse three ways — `404 no_image_data`, `502
 * image_fetch_failed`, `503` — and a DOM `error` event carries **no status code and no token**.
 * So this tile cannot tell them apart, and by c4-3's decide-once ruling #2 it does not have to:
 * *"the pixels are identical … but only this one may ever be retried"*, and the SPA has no
 * per-image retry UI by design (`EXPERIENCE.md`). One render answers all three.
 *
 * **This is not the re-derivation c4-3's AC 16 bans.** That rule is about a component running
 * `switch (entry.reason)` over a WIRE TOKEN that `cards.ts` already classified into
 * `entry.placeholder`. Here there is no token to re-derive and no cache entry involved: the
 * input is a DOM event on an element this component owns. It looks like the same shape and it
 * is a different one, which is why it is written down.
 *
 * **`onError` fires once per `src`.** A re-render with the same `src` does not re-arm it — and
 * that is the correct behaviour here, because the backend answers a remembered failure from
 * memory for up to 300 seconds (c3-8) and *"a tile that retries in a loop will be answered from
 * memory and change nothing"*. What it means mechanically is that the failure must live in
 * STATE rather than be recomputed, which it does.
 *
 * ================= WHAT THIS TILE DELIBERATELY DOES NOT DO =============================
 *
 * No `deck_changed` refetch, no shimmer, no quantity glow, and **no live region of its own** —
 * Epic 5 and c7-5; the pin announcement is the DETAIL PANEL's single polite region (c4-5 AC 23),
 * because ninety-nine tiles each owning one is ninety-nine ways to say the same sentence. And
 * **no hydration** — the tile still fetches nothing; whoever decides a full record is needed
 * calls `hydrateCard`, and from c4-6 that is `App.tsx`'s after-commit deck sweep as well as the
 * panel.
 *
 * c4-4's *"no `useCardEntry` subscription"* is the one line of this list that c4-6 spends, and it
 * is spent through `../imagedFaces` rather than directly: the tile has to know whether it has a
 * back face to draw, and `CardSummary` carries neither `card_faces` nor `image_uris`. That hook
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
   * `CardSummary.name`, verbatim and UNSPLIT — `'X // Y'` included, for `CardPlaceholder`'s own
   * Q5 reason: four surfaces must not call one card by two names. It is the caption, and it is
   * therefore the tile's accessible name (Q4).
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
   * nearly absent from the surface this story is about. It is not the tile's dominant feature,
   * and it must fit **two digits** (the largest quantity anywhere is 34, a `Swamp`).
   */
  quantity?: number
}

/**
 * A string prop that is actually there, or `null`.
 *
 * The identical `typeof` + `trim()` spelling `CardPlaceholder`, `DeckBadges` and `ManaCost` all
 * use, for the measured reason c4-2's review recorded: *"a presentation primitive that crashes
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
  // WHICH FACE, AND WHETHER THERE IS A SECOND ONE AT ALL (c4-6, Q3, Q10). A tile re-renders when
  // ITS card's record lands or ITS face changes, and not otherwise — by two different mechanisms
  // (review 2026-08-06 corrected this comment, which first credited "returns a NUMBER" for both):
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
  // `../useCardArt`, which is where c4-4's own implementation of all of it moved when c4-5
  // needed the identical thing at `size=large`. DESTRUCTURED rather than held as an object, and
  // that is a lint requirement rather than a habit: `react-hooks/refs` reads a member access
  // during render as reading a ref, so `art.settleIfCached` in the JSX below is an error while a
  // plain identifier is not (measured — see that module's `CardArt` docstring).
  //
  // TWO CALLS, ONE PER FACE (c4-6 Q7, Q8). `?face=1` is a different URL and therefore a different
  // browser-cache entry, so the two faces load, fail and settle INDEPENDENTLY — a hook keyed on
  // `cardId` alone would leave a flipped tile at `'shown'` over bytes that had not arrived. Both
  // are called unconditionally because hooks must be; only the FLIPPABLE tile renders the second
  // `<img>`, so a single-faced card still issues exactly one request.
  //
  // BOTH DESTRUCTURED, AND THE SECOND ONE PROVED THE RULE AGAIN: the first spelling here held
  // each handle as an object (`front.onLoad`), and `react-hooks/refs` reported eight errors —
  // exactly the failure `useCardArt`'s `CardArt` docstring records from the extraction that
  // created it. A member access during render reads as reading a ref; a plain identifier does not.
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
  // WHICHEVER FACE IS ON SCREEN GOVERNS THE WELL AND THE PLACEHOLDER (Q8). The alternative —
  // letting the FRONT decide for both — would show a silent well over a back face that had
  // already arrived, and would strand a card whose front picture failed on a placeholder it could
  // never flip out of. The control itself is a sibling of this button, so it survives the failed
  // branch replacing everything inside it, which is the other half of that ruling.
  const art = flipped ? backArt : frontArt
  // Q7's ruling, and the whole reason it is a per-tile SELECTOR rather than a prop from the
  // grid: this returns a BOOLEAN, so zustand v5's referential comparison re-renders exactly the
  // tiles whose value flipped — two per hover — instead of all ninety-nine on every cursor
  // movement across the grid.
  const live = useIsLiveTarget(cardId)
  // `useId` — a HOOK, in a component whose caption sits OUTSIDE its button and therefore has to
  // be pointed at rather than contained. A listed primitive may not call one at all; `Panel`
  // records that exact constraint as the reason it uses `aria-label` instead. This component is
  // a container, so the hook is available and the structure below is free to be the right one.
  const captionId = useId()

  const caption = given(name)

  // `Number.isFinite`, never `quantity &&` and never `quantity ?` (the c2-7 decide-once ruling):
  // `{quantity && <Badge/>}` renders the bare string `0` into the DOM and `quantity ? … : null`
  // drops a real zero. The threshold here is `> 1`, which is neither — a single copy gets no
  // badge because "1" on ninety-eight of ninety-nine tiles is noise, not information.
  const copies = Number.isFinite(quantity) ? (quantity as number) : 1

  const captioned = art !== 'failed' && caption !== null
  const badgeId = `${captionId}-n`
  // The elements that NAME the button, in reading order. `undefined` on the failed path and on a
  // nameless card, so the accessible name falls back to the button's own contents rather than to
  // a dangling reference — an `aria-labelledby` pointing at no element leaves a control unnamed.
  const labelledBy = captioned ? (copies > 1 ? `${captionId} ${badgeId}` : captionId) : undefined

  return (
    <>
      {/* THE FRAME (c4-6, Q2). It exists for ONE reason and carries no appearance of its own: the
          flip control is a `<button>` and so is the tile, and an interactive descendant of a
          `<button>` is invalid HTML that React 19.2 warns about in development and that assistive
          technology does not reliably expose as a separate control (both measured — see the
          header). So the two are SIBLINGS, and something has to hold them.

          Its box is exactly the card box, because the button below is `display: block` at
          `width: 100%` with `card-shape`'s aspect ratio — so pinning the control to this element's
          top-left inside `--space-2` is pinning it to the CARD's top-left, which is DESIGN.md's
          words, and the hover REGION is unchanged from c4-4's.

          THE POINTER AND FOCUS HANDLERS LIVE HERE, AND THE CLICK DOES NOT. `mouseenter`/
          `mouseleave` do not fire when the pointer moves between this element's own children, so
          reaching the control never reads as leaving the tile — the property four shipped comments
          were reaching for, restored one element further out. `focusin`/`focusout` (React's
          `onFocus`/`onBlur`) bubble, so Tabbing from the tile to its OWN control keeps the tile's
          inspection target rather than dropping it: PR #44's P1 defect, one element out. `onClick`
          stays on the button, because pinning is the card's action and the flip must not be one. */}
      <div
        className="card-tile-frame"
        onMouseEnter={() => setHovered(cardId)}
        onMouseLeave={() => clearHovered(cardId)}
        onFocus={() => setFocused(cardId)}
        onBlur={() => clearFocused(cardId)}
      >
        {/* THE BUTTON **IS** THE CARD, AND THAT IS A REPAIR THE EYE-CHECK FORCED (Task 7).
          The first draft wrapped the art and the caption in one button and drew the focus ring
          on an inner frame. Rendered in a real browser with a real keyboard focus, that showed
          TWO indicators at once: the composite ring hugging the card's rounded corners, and the
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
          point at, and the accessible name falls back to the button's contents — which is c4-3's
          named placeholder, already naming the card exactly once. */}
        <button
          type="button"
          /* `is-live` is the class DESIGN.md's `components.card-tile.live-ring` hangs on, and it
           is the ONLY thing this component does with its liveness — the ring itself is
           `--shadow-live-ring` in CardTile.css, because a composite box-shadow cannot be
           written in a component stylesheet at all (stylelint's allowed-list). */
          className={live ? 'card-shape card-tile is-live' : 'card-shape card-tile'}
          aria-labelledby={labelledBy}
          /* THE INSPECTION CONTRACT, AND NOTHING ELSE (c4-5, UX-DR14, UX-DR20). Four handlers,
           no decisions: what an id MEANS — whether it can be inspected at all, whether a click
           pins or releases, what wins between hover and pin — belongs to the slice, so that
           c4-7's deck rows and Epic 6's thumbnails get the identical behaviour from the
           identical verbs rather than from four copies of a rule.

           HOVER AND FOCUS ARE THE SAME CONTRACT IN TWO SLOTS, which is UX-DR14 read literally
           ("hover OR keyboard focus") and `EXPERIENCE.md`'s "hover is never the only way to
           reach information". Each modality writes its OWN slot (PR #44 P1: one shared slot
           let a `mouseleave` erase a still-focused tile's target), and each leave-handler
           names the card it is leaving, so that a `blur` landing after the next tile's
           `focus` cannot erase a target that tile has already set (see `clearHovered` /
           `clearFocused`).

           NO `onKeyDown`. This is a real `<button>`, so the browser already turns Enter and
           Space into a `click` — which is also what makes "release is a second SINGLE click"
           free rather than something to implement (double-click semantics are banned outright,
           `EXPERIENCE.md`).

           THE POINTER AND FOCUS HANDLERS ARE NO LONGER HERE — they moved to the frame above at
           c4-6, because the flip control had to become a SIBLING of this button rather than a
           descendant of it. `onClick` stayed, because pinning is the card's action; the control
           calls `stopPropagation()` for the ancestors that are clickable elsewhere. */
          onClick={() => togglePin(cardId)}
        >
          {art === 'failed' ? (
            /* THE NAMED PLACEHOLDER, from the props the deck payload already carried. Not from
             `entry.placeholder` and not from a wire token — see the header.
             ON THE SHOWN FACE (c4-6 Q8): a card whose BACK picture failed draws this while
             flipped and its own face while not, because `?face=1` is a different negative-cache
             key and the two faces genuinely fail independently. The flip control survives this
             branch — it is outside this button — so a failed face can always be flipped out of. */
            <CardPlaceholder variant="named-card" name={name} cost={cost} typeLine={typeLine} />
          ) : (
            <>
              {/* THE SILENT WELL, until the pixels exist. It is a SIBLING the image covers
                rather than a background under it, and that is Q8's ruling: a `--surface-well`
                painted on the same element would sit under a card face whose PNG corners are
                transparent, which DESIGN.md explicitly cares about ("png faces with
                transparent corners sit flush"). */}
              {art === 'loading' ? <CardPlaceholder variant="loading" /> : null}
              {/* THE TWO STACKED FACES (c4-6 Q10, AC 14). `data-flipped` is present only when there
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
                  /* `alt=""`, and it is a RULING rather than a default (Q4, AC 11). UX-DR48 keeps
                   `alt={name}` on grid tiles *"because there the image is the only carrier"* —
                   and for THIS component that premise is measurably false: UX-DR14 puts the same
                   name in a caption directly beneath the art, and `aria-labelledby` makes that
                   caption the button's accessible name. With `alt={name}` as well, a
                   screen-reader user would hear "Black Lotus Black Lotus". This tile has exactly
                   the structure UX-DR48's OTHER clause describes for row thumbnails — *"use
                   `alt=""` — the name is announced once, from the row text"* — so the rule's own
                   logic is applied rather than its letter. `CardTile.test.tsx` proves the
                   accessible name carries the name exactly once.

                   UNCHANGED BY c4-6, AND THE RESIDUE IS DECLARED (Q12): while a DFC shows its
                   back face, this tile's caption still reads the printing's COMBINED name
                   (`Clearwater Pathway // Murkwater Pathway`) while the art shows one half. The
                   panel's heading follows the face; the caption does not. Same divergence c4-5
                   ledgered for the pin announcement, one surface further — epic manual-testing
                   checklist, not a jsdom assertion. */
                  alt=""
                  /* Q7: all ~99 mount at once, and the arithmetic is in the story record.
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
                   cold fetch at the rotation's midpoint, which is what Q10's declined option (b)
                   would have needed a JS timer for.

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
            /* THE QUANTITY BADGE (AC 9, UX-DR3, UX-DR16). Top-RIGHT: c4-6's flip control owns the
             top-left and the two must never collide.

             IT IS NAMED RATHER THAN HIDDEN (Q6). UX-DR16 delegates the accessible quantity
             signal to "the group-header count and the coalesced live-region announcement", and
             this story ships NEITHER — no group headers in the grid (Q5), no live region until
             c7-5 — so delegating anyway would leave the count visual-only. Its id joins
             `aria-labelledby` above, which also fixes the reading ORDER: name first, then
             count, rather than the DOM order a name-from-contents would have imposed. No
             authored string is involved, so no COPY_MODULES entry is owed. */
            <span
              id={badgeId}
              className="card-tile-quantity"
            >{`${MULTIPLICATION_SIGN}${copies}`}</span>
          ) : null}
        </button>
        {/* THE FLIP CONTROL (c4-6, AC 1, AC 8, AC 12). A SIBLING of the button, immediately after
            it in DOM order — which is the whole of UX-DR40's *"immediately after its own tile"*
            Tab stop, asserted as document order rather than as a `tabindex` (AC 8). It renders
            `null` for the 35,483 cards that are not flippable, so the Tab order of an ordinary
            deck is exactly c4-4's.

            It takes only a `cardId`: the predicate, the material, the glyph and the label are all
            its own, and the panel mounts the identical component against its art box (AC 12). */}
        <FlipControl cardId={cardId} />
      </div>
      {/* THE CAPTION (AC 5, AC 6, UX-DR14).

          NOT RENDERED BESIDE THE NAMED PLACEHOLDER, and that is AC 11 applied to the path it is
          easiest to forget. c4-3's named placeholder centres the card's name inside the card box
          (its own AC 13) — so a caption underneath would put the SAME NAME ON THE TILE TWICE,
          visibly, and announce it twice inside one `<button>`. Q4's ruling is that the name is
          announced once; the failed path is the same question with a different carrier, so it
          gets the same answer: whichever element is naming the card, only one of them does.

          OUTSIDE THE FRAME, not merely outside the button — so the hover region stays the CARD
          (c4-4's ruling, preserved through c4-6's restructure) rather than growing to include a
          line of text below it. It is the button's accessible name by reference rather than by
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
