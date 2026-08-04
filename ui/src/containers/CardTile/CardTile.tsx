import { useCallback, useId, useState } from 'react'

import { CardPlaceholder } from '../../components/CardPlaceholder/CardPlaceholder'
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
 * ================= THE WARM-CACHE RACE, WHICH IS THE NORMAL PATH HERE ==================
 *
 * A successful image is served `Cache-Control: public, max-age=31536000, immutable`, so **every
 * render after the first is a browser-cache hit** and the `load` event can be dispatched before
 * React has anything listening. A tile that could only ever leave the loading state from an
 * `onLoad` callback would then show a silent well forever, on exactly the path NFR-05's
 * one-second warm render describes — the happy case failing while the cold case works.
 *
 * {@link CardTile.settleIfCached} closes it by asking the element instead of waiting for the
 * event, which is the standard mitigation and needs a `ref` — the third independent reason this
 * cannot be a listed primitive. `naturalWidth > 0` is load-bearing beside `complete`:
 * `complete` is also true for a BROKEN image, and treating a broken image as loaded would swap
 * the named placeholder for a blank rectangle, which AD-11 forbids.
 *
 * **jsdom can see neither half of this.** It loads no images, fires no `load` and reports
 * `naturalWidth` as 0 — so the guard is inert there (which is what lets the well assertions in
 * `CardTile.test.tsx` mean anything) and the claim it makes is UNPROVABLE in this suite. It is
 * declared here and checked by eye against a warm browser cache in Task 7.
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
 * No inspection, no pin, no hover→detail wiring: the `<button>` ships with **no handler at
 * all**, so **c4-5** adds one rather than reshaping the component. No flip control and no
 * `face` parameter — **c4-6's**, and it owns the tile's TOP-LEFT, which is why the badge is
 * pinned top-right. No `deck_changed` refetch, no shimmer, no quantity glow, no live region —
 * Epic 5 and c7-5. No `useCardEntry` subscription (Q9): see {@link CardTileProps}.
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
 * Whether the image has arrived, failed, or is still in flight.
 *
 * A three-state union rather than two booleans, because `loading && failed` is a state that
 * cannot happen and a pair of booleans is a pair that can express it.
 */
type ArtState = 'loading' | 'shown' | 'failed'

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
  const [art, setArt] = useState<ArtState>('loading')
  // THE VERDICT BELONGS TO THE CARD, NOT TO THE SLOT (review 2026-08-04). Today's one call site
  // keys each `<li>` by `card_id`, so a different card remounts a fresh tile — but that is the
  // CALLER's discipline, and this component is exported. A tile handed a different `cardId` on
  // the same mount would otherwise keep the old card's `failed` (a placeholder for a card whose
  // picture is fine) or its `shown` (opacity 1 over pixels that have not arrived). The reset is
  // the render-time adjustment React documents for exactly this — during render, BEFORE the new
  // `src` ever commits, so no cached `load`/`error` for the old card can race it the way an
  // effect could be raced.
  const [artFor, setArtFor] = useState(cardId)
  if (artFor !== cardId) {
    setArtFor(cardId)
    setArt('loading')
  }
  // `useId` — a HOOK, in a component whose caption sits OUTSIDE its button and therefore has to
  // be pointed at rather than contained. A listed primitive may not call one at all; `Panel`
  // records that exact constraint as the reason it uses `aria-label` instead. This component is
  // a container, so the hook is available and the structure below is free to be the right one.
  const captionId = useId()

  // See the header. `useCallback` with no dependencies is what keeps the identity stable, so
  // React attaches this ONCE rather than detaching and re-attaching it on every state change —
  // which would call it again with the same node and make the reasoning here harder than it is.
  //
  // BOTH halves of the race, not one (review 2026-08-04). The mirror of the cached success is
  // the cached FAILURE: a refusal answered instantly — the negative cache holds one in memory
  // for up to 300 s (c3-8) — can dispatch `error` before React is listening, exactly as a warm
  // hit can dispatch `load`. A settle that only knew the success half would leave that tile on
  // the silent well forever, with the named placeholder AD-11 promises unreachable. `complete`
  // is true for a broken image too; `naturalWidth` is what says which kind of settled this is.
  const settleIfCached = useCallback((node: HTMLImageElement | null) => {
    if (node === null) return
    if (!node.complete) return
    setArt(node.naturalWidth > 0 ? 'shown' : 'failed')
  }, [])

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
      <button type="button" className="card-shape card-tile" aria-labelledby={labelledBy}>
        {art === 'failed' ? (
          /* THE NAMED PLACEHOLDER, from the props the deck payload already carried. Not from
             `entry.placeholder` and not from a wire token — see the header. */
          <CardPlaceholder variant="named-card" name={name} cost={cost} typeLine={typeLine} />
        ) : (
          <>
            {/* THE SILENT WELL, until the pixels exist. It is a SIBLING the image covers
                rather than a background under it, and that is Q8's ruling: a `--surface-well`
                painted on the same element would sit under a card face whose PNG corners are
                transparent, which DESIGN.md explicitly cares about ("png faces with
                transparent corners sit flush"). */}
            {art === 'loading' ? <CardPlaceholder variant="loading" /> : null}
            <img
              ref={settleIfCached}
              className="card-tile-image"
              data-loaded={art === 'shown' ? 'true' : 'false'}
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
                 accessible name carries the name exactly once. */
              alt=""
              /* Q7: all ~99 mount at once, and the arithmetic is in the story record.
                 `decoding="async"` keeps decode off the main thread; `loading="lazy"` is
                 DELIBERATELY ABSENT — the grid is the app's primary surface and a
                 scroll-triggered second fill pattern is one the UX inventory never describes.
                 Lowercase DOM attributes, passed through unchanged by React 19; the one that
                 would need camelCase is `fetchPriority`, and this tile sets none. */
              decoding="async"
              onLoad={() => setArt('shown')}
              onError={() => setArt('failed')}
            />
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
      {/* THE CAPTION (AC 5, AC 6, UX-DR14).

          NOT RENDERED BESIDE THE NAMED PLACEHOLDER, and that is AC 11 applied to the path it is
          easiest to forget. c4-3's named placeholder centres the card's name inside the card box
          (its own AC 13) — so a caption underneath would put the SAME NAME ON THE TILE TWICE,
          visibly, and announce it twice inside one `<button>`. Q4's ruling is that the name is
          announced once; the failed path is the same question with a different carrier, so it
          gets the same answer: whichever element is naming the card, only one of them does.

          A SIBLING OF THE BUTTON, not a child — see the button's own comment. It is the button's
          accessible name by reference rather than by containment, which is what lets the focus
          ring be the card's shape rather than a rectangle around card-plus-text.

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
