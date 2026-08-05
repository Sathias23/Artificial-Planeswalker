import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { UNKNOWN_CARD_LABEL } from '../../components/CardPlaceholder/copy'
import { resetCardCache, useCardStore } from '../../state/cards'
import {
  resetInspection,
  setDefaultTarget,
  targetIdOf,
  togglePin,
  useInspectionStore,
} from '../../state/inspection'
import { CardTile, type CardTileProps } from './CardTile'
import { cardImageUrl } from './imageUrl'

/**
 * The card tile (story c4-4, AC 3–AC 11, AC 17–AC 21).
 *
 * ================= WHAT THIS SUITE CANNOT CARRY, SAID FIRST (AC 29) ====================
 *
 * An undeclared limit reads as coverage, so the limits come before the assertions. jsdom has no
 * layout engine, applies no stylesheet, and **loads no images**. Everything below follows from
 * those three facts:
 *
 *   **The geometry is not a pixel here, and cannot be.** `getComputedStyle(el).aspectRatio`
 *   returns the empty string in jsdom and would PASS FOR THE WRONG REASON — the seventh recorded
 *   instance of that trap in this epic. The two instruments this story has are the two c4-3
 *   declared: a source read (`card-geometry.css` declares the shape exactly once, asserted in
 *   `tests/token-usage.test.ts`) and the DOM assertion below that the element carries the class.
 *   Together they prove the tile CONSUMES the shared shape; that the box is 63:88 ON SCREEN, and
 *   that a placeholder sits at the same footprint beside a real card face, is **Task 7's**.
 *
 *   **Nothing here proves the tile looks like a card.** No stylesheet is applied, so the shadow,
 *   the ring, the uppercase caption, the badge's blur and the hover pop are all unrendered. They
 *   are asserted as SOURCE in `tests/shell.test.ts` and `tests/token-usage.test.ts`, and looked
 *   at in **Task 7**.
 *
 *   **The happy path is the one jsdom can never see.** A successful image ships
 *   `max-age=31536000, immutable`, so every render after the first is a browser-cache hit and
 *   `load` can fire before React is listening. `settleIfCached` exists for exactly that, and
 *   jsdom reports `complete: false` / `naturalWidth: 0` for every element — so the guard is
 *   INERT here in both directions. What this file proves is that the guard does not fire
 *   wrongly (the well still shows before load); that it fires RIGHTLY is **Task 7's**, against a
 *   warm browser cache.
 *
 *   **The ~10-second cold paint, the pacer and the 300-second negative cache are backend
 *   behaviour.** No request is made from here at all. They are the epic manual-testing
 *   checklist's and c10-3's.
 *
 * The `load` and `error` events below are DISPATCHED, not awaited — which is honest about what
 * is being tested: the component's response to the browser's two signals, not the browser.
 */

const BLACK_LOTUS = {
  cardId: 'b3a40e8e-1a1b-4b4b-9f9f-0a0a0a0a0a0a',
  name: 'Black Lotus',
  cost: '{0}',
  typeLine: 'Artifact',
}

const imageOf = (container: HTMLElement) => container.querySelector('img')

// The inspection slice is module-scope, as stores are; without this the target a previous test
// left behind is what the next one starts from — and every `is-live` assertion below would be
// reading the wrong tile's liveness.
afterEach(() => {
  resetInspection()
  resetCardCache()
})

describe('the tile points at our own origin and nowhere else (AC 3)', () => {
  it('asks the app for the picture, not the CDN', () => {
    const { container } = render(<CardTile {...BLACK_LOTUS} />)
    const img = imageOf(container)!

    // Relative, same-origin, and the route c3-5 shipped. `tests/no-scryfall-hosts.test.ts` bans
    // the host FAMILY across all of `src/`, which is the static half; this is the rendered half.
    expect(img.getAttribute('src')).toBe(`/api/card-image/${BLACK_LOTUS.cardId}`)
    expect(img.getAttribute('src')).not.toMatch(/scryfall/i)
    expect(img.getAttribute('src')?.startsWith('/')).toBe(true)
  })

  it('spells no size, because `normal` is the route default AND the cache key', () => {
    // Two spellings of one request are two entries in a cache whose whole value here is that it
    // is warm. c4-5 and c4-6 add their parameters to `cardImageUrl`, not to a second template.
    //
    // UNCHANGED BY c4-5, WHICH IS THE POINT OF ITS PARAMETER BEING OPTIONAL. That story extended
    // this builder rather than writing a second one, and the grid's URL is byte-identical.
    expect(cardImageUrl('x')).toBe('/api/card-image/x')
    expect(cardImageUrl('x')).not.toContain('size=')
    expect(cardImageUrl('x')).not.toContain('face=')
  })

  it('takes a size when a caller genuinely needs one — c4-5s detail render', () => {
    // ONE BUILDER (imageUrl.ts's own instruction, and this is the story that carries it out).
    expect(cardImageUrl('x', 'large')).toBe('/api/card-image/x?size=large')
    // The id is still encoded with the size attached — a `?` in the id must not become a second
    // query parameter, which is exactly what a template-string second implementation would have
    // got wrong somewhere else in the tree.
    expect(cardImageUrl('a?b=1', 'large')).toBe('/api/card-image/a%3Fb%3D1?size=large')
    // …and passing the DEFAULT explicitly is a different URL, which is the browser-cache fact
    // the docstring rests on: `?size=normal` is a second cache entry for one picture. Nothing in
    // the app spells it; asserted so the asymmetry is a recorded property rather than a habit.
    expect(cardImageUrl('x', 'normal')).not.toBe(cardImageUrl('x'))
  })

  it('encodes an id that would otherwise address a different route (c4-1 Q5)', () => {
    // The id comes out of `deck_cards`, a column with no shape constraint. Unencoded, a `/` in
    // it would silently walk up the path rather than producing a refusal the tile can draw.
    expect(cardImageUrl('../decks')).toBe('/api/card-image/..%2Fdecks')
    expect(cardImageUrl('a?b=1')).toBe('/api/card-image/a%3Fb%3D1')
  })

  it('defers decode but NOT loading (Q7)', () => {
    const { container } = render(<CardTile {...BLACK_LOTUS} />)
    const img = imageOf(container)!

    // `decoding` and `loading` are lowercase DOM attributes React passes through unchanged, so
    // asserting the rendered ATTRIBUTE rather than the prop is what catches a casing slip — the
    // failure mode React 19 reports as a silent no-op plus a console warning, never a build
    // error. (`fetchPriority` is the camelCase one; this tile sets none, and its absence is
    // asserted so that adding one is a decision.)
    expect(img.getAttribute('decoding')).toBe('async')
    expect(img.getAttribute('loading')).toBeNull()
    expect(img.getAttribute('fetchpriority')).toBeNull()
  })
})

describe('the shape is consumed, never re-declared (AC 4, AC 7)', () => {
  it('carries `card-shape` on the box every state fills', () => {
    const { container } = render(<CardTile {...BLACK_LOTUS} />)
    const art = container.querySelector('.card-tile')!

    /* The DOM half of the geometry claim, and ALL it carries: this element inherits
       `aspect-ratio: 63 / 88` and `border-radius: var(--radius-card)` from the ONE declaration
       in card-geometry.css. It does NOT carry "the box is 63:88 on screen" — see the header.

       A BLOCK COMMENT, DELIBERATELY, and c4-3 predicted this exact repair: CARD_SHAPED's markup
       half strips block comments only (CSS has no line comments, so that is all a STYLESHEET
       needs) while it also scans `.tsx`, where a `//` line comment naming the token fires the
       guard on prose. Its declared instruction is "the repair is to move the prose into a block
       comment, never to delete the explanation" — measured here, in the first story to write
       that sentence in a `.tsx` file. */
    expect(art.classList.contains('card-shape')).toBe(true)
  })

  it('puts the well and the image in the SAME box, which is what makes AC 7 structural', () => {
    const { container } = render(<CardTile {...BLACK_LOTUS} />)
    const art = container.querySelector('.card-tile')!

    // Both children of one card-shaped frame. The frame's size comes from its own aspect ratio
    // rather than from whichever child happens to be rendered, so the slot is at full size
    // before any image exists — the mechanism behind "layout never reflows when art arrives".
    expect(art.querySelector('.card-placeholder-well')).not.toBeNull()
    expect(art.querySelector('img')).not.toBeNull()
  })
})

describe('the three art states (AC 8)', () => {
  it('shows the silent well before anything has arrived', () => {
    const { container } = render(<CardTile {...BLACK_LOTUS} />)

    const well = container.querySelector('.card-placeholder-well')!
    expect(well).not.toBeNull()
    // SILENT: `aria-hidden`, and with no text of its own to leak. c4-3's component gives the
    // loading variant one property, so there is nothing to say it with.
    expect(well.getAttribute('aria-hidden')).toBe('true')
    expect(well.textContent).toBe('')
    // …and the name is NOT in the well. The caption sits beside it, which is c4-3's review
    // finding applied in the consumer this time.
    expect(well.querySelector('.card-tile-caption')).toBeNull()
  })

  it('fades the image in on load and drops the well', () => {
    const { container } = render(<CardTile {...BLACK_LOTUS} />)
    fireEvent.load(imageOf(container)!)

    expect(imageOf(container)!.getAttribute('data-loaded')).toBe('true')
    expect(container.querySelector('.card-placeholder-well')).toBeNull()
  })

  it('swaps to the NAMED placeholder on error — never a broken-image glyph (AD-11)', () => {
    const { container } = render(<CardTile {...BLACK_LOTUS} />)
    fireEvent.error(imageOf(container)!)

    // The `<img>` is REMOVED rather than hidden: an element with a failed `src` still draws the
    // browser's own broken-image glyph, which is the one thing AD-11 promises never happens.
    expect(imageOf(container)).toBeNull()
    expect(screen.getByText('Black Lotus')).toBeVisible()
    expect(screen.getByText('Artifact')).toBeVisible()
    // The NAMED variant, not the unknown one: the app knows exactly what this card is and only
    // lacks its picture.
    expect(screen.queryByText(UNKNOWN_CARD_LABEL)).toBeNull()
    expect(container.querySelector('.card-placeholder')).not.toBeNull()
  })

  it('reaches the named placeholder from an EVENT, with no token anywhere (AC 8)', () => {
    // The record's claim, asserted AT THE TYPE (review 2026-08-04 — the first spelling of this
    // test inspected `Object.keys` of its own fixture, which could never contain the banned
    // names by construction). A DOM `error` carries no status code and no wire token, so one
    // render answers `404 no_image_data`, `502 image_fetch_failed` and `503` alike — and that is
    // NOT c4-3's AC 16 being violated, because there is no `entry.placeholder` and no
    // `entry.reason` in this path at all. The interface is what the claim is about, so the
    // assertion reads the interface: the day someone adds a `placeholder` or `reason` prop to
    // `CardTileProps`, this line stops compiling.
    type WireTokenKeys = Extract<keyof CardTileProps, 'placeholder' | 'reason'>
    const declaresNoWireToken: [WireTokenKeys] extends [never] ? true : never = true
    expect(declaresNoWireToken).toBe(true)
  })

  it('does not re-arm the error, because the backend answers from memory for 300 s (c3-8)', () => {
    const { container, rerender } = render(<CardTile {...BLACK_LOTUS} />)
    fireEvent.error(imageOf(container)!)
    // A RE-RENDER with the same props — `rerender`, not a click on a handler-less button (review
    // 2026-08-04: the first spelling clicked, which triggers no state change and no render, so
    // the assertion passed because nothing happened) — must not put the `<img>` back and start
    // the loop the negative cache exists to make pointless: "a tile that retries in a loop will
    // be answered from memory and change nothing."
    rerender(<CardTile {...BLACK_LOTUS} />)
    expect(imageOf(container)).toBeNull()
  })

  it('re-arms for a DIFFERENT card — the verdict belongs to the card, not the slot', () => {
    const { container, rerender } = render(<CardTile {...BLACK_LOTUS} />)
    fireEvent.error(imageOf(container)!)
    expect(imageOf(container)).toBeNull()
    // Today's call site keys each `<li>` by `card_id`, so this path needs a remount to reach in
    // the app — but the component is exported, and a tile that kept the OLD card's failure for a
    // NEW card would show a placeholder for a card whose picture is fine.
    rerender(<CardTile {...BLACK_LOTUS} cardId="a-different-printing" />)
    expect(imageOf(container)).not.toBeNull()
    expect(imageOf(container)!.getAttribute('src')).toBe('/api/card-image/a-different-printing')
  })

  it('survives a card with no name at all — totality, not a handled case', () => {
    // 0 of the 1,061 distinct cards in the 40 real decks lack a name, so this branch has no live
    // population. It is here for c4-2's measured reason: a component that crashes the whole app
    // on one absent prop is the FR-13 posture inverted, and totality costs one keyword.
    const { container } = render(<CardTile cardId="x" name={null} cost={null} typeLine={null} />)
    expect(container.querySelector('.card-tile-caption')).toBeNull()
    expect(container.querySelector('.card-tile')).not.toBeNull()
    // …and with no caption to point at, `aria-labelledby` is ABSENT rather than dangling: a
    // reference to a missing element leaves the control unnamed, which is worse than falling
    // back to its contents.
    expect(container.querySelector('button')!.getAttribute('aria-labelledby')).toBeNull()

    const blank = render(<CardTile cardId="y" name="   " />)
    expect(blank.container.querySelector('.card-tile-caption')).toBeNull()
  })
})

describe('the caption (AC 5, AC 6)', () => {
  it('renders the name below the art, verbatim and UNSPLIT', () => {
    render(<CardTile cardId="x" name="Barkchannel Pathway // Tidechannel Pathway" />)
    // The longest name in the largest real deck (42 characters), and it is rendered whole: four
    // surfaces must not call one card by two names, which is `CardPlaceholder`'s own Q5 ruling.
    expect(screen.getByText('Barkchannel Pathway // Tidechannel Pathway')).toBeVisible()
  })

  it('renders the name as DATA — the uppercase is CSS, not a transformed string', () => {
    // Q3 ships the uppercase through `text-transform`, which leaves the DOM text and therefore
    // the accessible name and the clipboard untouched. A component that had uppercased the
    // STRING would pass a "looks right" screenshot and fail this.
    render(<CardTile {...BLACK_LOTUS} />)
    expect(screen.getByText('Black Lotus')).toBeVisible()
    expect(screen.queryByText('BLACK LOTUS')).toBeNull()
  })
})

describe('the quantity badge (AC 9, AC 10)', () => {
  it('renders ×N above one copy, with U+00D7 and not the letter x', () => {
    render(<CardTile {...BLACK_LOTUS} quantity={4} />)

    // BYTE-FOR-BYTE. A keyboard produces `x` (U+0078); DESIGN.md and UX-DR16 both specify the
    // MULTIPLICATION SIGN. Asserted as a codepoint rather than as a glyph so that a font, an
    // editor or a find-and-replace cannot make the two look the same in a diff.
    const badge = screen.getByText('×4')
    expect(badge).toBeVisible()
    expect(badge.textContent.codePointAt(0)).toBe(0x00d7)
    expect(badge.textContent).not.toBe('x4')
  })

  it('fits two digits, because the largest real quantity is 34', () => {
    render(<CardTile cardId="swamp" name="Swamp" quantity={34} />)
    expect(screen.getByText('×34')).toBeVisible()
  })

  it('renders NO badge for a single copy, an absent quantity, a zero or a NaN', () => {
    // The c2-7 decide-once ruling, in the one place it bites: `{quantity && …}` renders the bare
    // string `0` into the DOM — something, so nobody looks — and `quantity ? … : null` drops a
    // real zero. The threshold is `> 1`, guarded by `Number.isFinite`.
    const one = render(<CardTile cardId="a" name="A" quantity={1} />)
    expect(one.container.querySelector('.card-tile-quantity')).toBeNull()

    const none = render(<CardTile cardId="b" name="B" />)
    expect(none.container.querySelector('.card-tile-quantity')).toBeNull()

    const zero = render(<CardTile cardId="c" name="C" quantity={0} />)
    expect(zero.container.querySelector('.card-tile-quantity')).toBeNull()
    expect(zero.container.textContent).not.toContain('0')

    const nan = render(<CardTile cardId="d" name="D" quantity={Number.NaN} />)
    expect(nan.container.querySelector('.card-tile-quantity')).toBeNull()
    expect(nan.container.textContent).not.toContain('NaN')
  })

  it('sits INSIDE the card, in the corner c4-6 does not own', () => {
    const { container } = render(<CardTile {...BLACK_LOTUS} quantity={2} />)
    const badge = container.querySelector('.card-tile-quantity')!
    // Positioned against the card box rather than the card-plus-caption, so "inside {spacing.2}
    // of the tile" means inside the ART. c4-6's flip control takes the top-left; DESIGN.md says
    // the two must never collide, and the structure is what keeps that true.
    expect(badge.parentElement!.classList.contains('card-tile')).toBe(true)
    expect(badge.parentElement!.tagName).toBe('BUTTON')
  })
})

/**
 * The tile finally responds (story c4-5, AC 10, AC 19, AC 34).
 *
 * ================= WHAT THESE CANNOT CARRY (c4-5 Q9, AC 37) ============================
 *
 * `fireEvent.mouseEnter` DISPATCHES a `mouseenter`; jsdom evaluates no CSS, so what a hover
 * WIRES is provable here and what it LOOKS like is not. The live ring is a source claim in
 * CardTile.css plus Task 7's eye-check, and `is-live` below is the class that carries it — not
 * the ring itself.
 *
 * `fireEvent`, and NO new dependency: `@testing-library/user-event` is not installed and
 * `tests/package-contract.test.ts` pins the dependency list, so adding one would be a decision
 * with a diff. The suite's existing DOM-event idiom is `fireEvent.load` / `.error` a few blocks
 * up, and this is the same idiom applied to a pointer.
 */
describe('the tile sets the inspection target (c4-5 AC 10, AC 19, UX-DR14, UX-DR20)', () => {
  it('sets the target on hover and lets go on leave', () => {
    render(<CardTile {...BLACK_LOTUS} />)
    const tile = screen.getByRole('button')

    fireEvent.mouseEnter(tile)
    expect(useInspectionStore.getState().hoveredId).toBe(BLACK_LOTUS.cardId)

    fireEvent.mouseLeave(tile)
    expect(useInspectionStore.getState().hoveredId).toBeNull()
  })

  it('does the same on keyboard FOCUS — full parity, in a slot of its own (UX-DR14)', () => {
    render(<CardTile {...BLACK_LOTUS} />)
    const tile = screen.getByRole('button')

    // `EXPERIENCE.md`'s interaction primitives: "hover is never the only way to reach
    // information — every hover behavior has focus parity". A tile that only answered a pointer
    // would leave the whole detail panel unreachable from a keyboard. ITS OWN SLOT, not the
    // hover's (PR #44 P1): with one shared slot, a `mouseleave` erased a still-focused tile's
    // target — so focus writes `focusedId` and never `hoveredId`.
    fireEvent.focus(tile)
    expect(useInspectionStore.getState().focusedId).toBe(BLACK_LOTUS.cardId)
    expect(useInspectionStore.getState().hoveredId).toBeNull()

    fireEvent.blur(tile)
    expect(useInspectionStore.getState().focusedId).toBeNull()
  })

  it('clears only its OWN focus, so a blur cannot erase the next tile’s focus', () => {
    // THE RACE the keyed clears EXIST FOR (c4-5 Q8). Leaving one card and reaching the next
    // produces two events and the losing tile's is free to land second; an unkeyed clear on
    // blur would then erase a target the tile being MOVED TO has already set, and the panel
    // would snap back to the cold-open card in the middle of a sweep.
    const first = render(<CardTile {...BLACK_LOTUS} />)
    const second = render(<CardTile cardId="second-card" name="Mox Pearl" />)
    const tileOf = (r: ReturnType<typeof render>) => r.container.querySelector('button')!

    fireEvent.focus(tileOf(first))
    fireEvent.focus(tileOf(second))
    fireEvent.blur(tileOf(first))

    expect(useInspectionStore.getState().focusedId).toBe('second-card')
  })

  it('a mouse-leave does not strand a still-focused tile (PR #44 P1)', () => {
    // THE REPORTED DEFECT, at the tile's own wiring: Tab-focus one tile, sweep the mouse over
    // another and away. The leave clears only the POINTER slot, so the focused tile takes the
    // target back — the panel and the live ring stay consistent with the focus ring on screen.
    const focused = render(<CardTile {...BLACK_LOTUS} />)
    const swept = render(<CardTile cardId="second-card" name="Mox Pearl" />)
    const tileOf = (r: ReturnType<typeof render>) => r.container.querySelector('button')!

    fireEvent.focus(tileOf(focused))
    fireEvent.mouseEnter(tileOf(swept))
    fireEvent.mouseLeave(tileOf(swept))

    expect(useInspectionStore.getState().focusedId).toBe(BLACK_LOTUS.cardId)
    expect(targetIdOf(useInspectionStore.getState())).toBe(BLACK_LOTUS.cardId)
  })

  it('pins on click, and releases on a SECOND single click (AC 19, AC 20)', () => {
    render(<CardTile {...BLACK_LOTUS} />)
    const tile = screen.getByRole('button')

    // Enter and Space need no handler of their own: this is a real `<button>`, so the browser
    // turns both into a `click`. That is also what makes "release is a second SINGLE click"
    // free — `EXPERIENCE.md` bans double-click semantics outright.
    fireEvent.click(tile)
    expect(useInspectionStore.getState().pinnedId).toBe(BLACK_LOTUS.cardId)

    fireEvent.click(tile)
    expect(useInspectionStore.getState().pinnedId).toBeNull()
  })

  it('refuses to pin a card the app does not know (AC 17, UX-DR22)', () => {
    // The refusal lives in the SLICE, not here — which is why this tile needs no `inspectable`
    // prop and c4-3's placeholder needed no API change. The tile is where it is checked from,
    // because Epic 6's thumbnails will click the same way.
    useCardStore.setState((state) => ({
      cards: {
        ...state.cards,
        [BLACK_LOTUS.cardId]: {
          status: 'unknown',
          reason: 'card_not_found',
          placeholder: 'unknown-card',
          summary: null,
          retryable: false,
        },
      },
    }))
    render(<CardTile {...BLACK_LOTUS} />)

    fireEvent.click(screen.getByRole('button'))
    expect(useInspectionStore.getState().pinnedId).toBeNull()
  })

  it('lets a CHILD control opt out with stopPropagation — c4-6’s flip, proven early', () => {
    // The contract c4-6 relies on, asserted now rather than discovered then: its flip control
    // sits INSIDE this button and must "only flip, and never set, pin or clear the inspection".
    // Because the handlers are on the button and `click` bubbles, a `stopPropagation()` in the
    // child suppresses the pin with no edit to this component — and this is the proof, planted
    // as a real listener on a real descendant.
    const { container } = render(<CardTile {...BLACK_LOTUS} quantity={2} />)
    const child = container.querySelector('.card-tile-quantity')!
    child.addEventListener('click', (event) => event.stopPropagation())

    fireEvent.click(child)
    expect(useInspectionStore.getState().pinnedId).toBeNull()

    // …and the same click WITHOUT the child stopping it does reach the tile, so the assertion
    // above is about propagation rather than about the element being unclickable.
    const other = render(<CardTile cardId="other" name="Mox Ruby" quantity={2} />)
    fireEvent.click(other.container.querySelector('.card-tile-quantity')!)
    expect(useInspectionStore.getState().pinnedId).toBe('other')
  })

  it('carries `is-live` when it IS the target, and nothing when it is not (AC 34)', () => {
    const { container } = render(<CardTile {...BLACK_LOTUS} />)
    const tile = container.querySelector('button')!

    expect(tile.classList.contains('is-live')).toBe(false)

    act(() => setDefaultTarget(BLACK_LOTUS.cardId))
    // THE COLD-OPEN CARD IS LIVE WITH NO INTERACTION, which is why the slice holds the default
    // rather than the panel resolving it privately: the tile and the panel are looking at one
    // answer. A CLASS, not a computed style — jsdom applies none, and the ring itself is
    // `--shadow-live-ring` in CardTile.css (Task 7 looks at it).
    expect(tile.classList.contains('is-live')).toBe(true)
    // …and it is still card-shaped, so the class list is added to rather than replaced.
    expect(tile.classList.contains('card-shape')).toBe(true)

    act(() => togglePin('some-other-card'))
    expect(tile.classList.contains('is-live')).toBe(false)
  })
})

describe('what a screen reader gets (AC 10, AC 11, AC 20)', () => {
  it('is a real button, in the Tab order', () => {
    render(<CardTile {...BLACK_LOTUS} />)
    const tile = screen.getByRole('button')

    // A REAL `<button>` (UX-DR47, unconditional) — not a `tabIndex` on a div, which
    // `jsx-a11y/no-static-element-interactions` makes an ESLint error. It is focusable by being
    // a button, so nothing sets `tabindex` and nothing needs to.
    //
    // This test read "…with no handler in this story" until c4-5, which is the story that added
    // them. What it asserts about the ELEMENT is unchanged, and deliberately so: the handlers
    // arrived without reshaping the control, which is exactly what c4-4 shipped it bare for.
    expect(tile.tagName).toBe('BUTTON')
    expect(tile.getAttribute('type')).toBe('button')
    expect(tile.getAttribute('tabindex')).toBeNull()
    expect(tile.hasAttribute('disabled')).toBe(false)
  })

  it('is card-shaped itself, so its focus ring can be the card’s shape (Task 7 repair)', () => {
    const { container } = render(<CardTile {...BLACK_LOTUS} />)
    const tile = screen.getByRole('button')

    // The eye-check found a real defect and this is the assertion that pins the repair: the
    // FOCUSABLE element is the card, so the authored outline hugs the same rounded rectangle
    // the composite ring does instead of boxing card-plus-caption in a second, sharp-cornered
    // indicator. The caption is therefore a SIBLING, not a child.
    expect(tile.classList.contains('card-shape')).toBe(true)
    expect(tile.querySelector('.card-tile-caption')).toBeNull()
    expect(container.querySelector('.card-tile-caption')).not.toBeNull()
  })

  it('announces the card name EXACTLY ONCE (Q4, AC 11)', () => {
    render(<CardTile {...BLACK_LOTUS} />)

    // THE MEASUREMENT UX-DR48'S GRID-TILE CLAUSE RESTS ON IS FALSE HERE. That clause keeps
    // `alt={name}` on grid tiles "because there the image is the only carrier" — and this tile
    // has a caption directly beneath the art, inside the same button, so the image is NOT the
    // only carrier. With both strings inside one control, `alt={name}` would make the
    // accessible name "Black Lotus Black Lotus".
    //
    // The rule's OWN logic for the structure this component actually has is its row-thumbnail
    // clause: "use `alt=''` — the name is announced once, from the row text". Applied here.
    // `name` here is an EXACT match, so this passes only if the accessible name is the card's
    // name and nothing else — not "Black Lotus Black Lotus", and not the name plus an alt.
    const tile = screen.getByRole('button', { name: 'Black Lotus' })
    expect(tile).toBeVisible()
    // …and the name is on screen exactly once too, which is the visible half of the same claim.
    expect([...document.body.textContent.matchAll(/Black Lotus/g)]).toHaveLength(1)

    // The `<img>` contributes nothing to the name, which is what makes it once rather than twice.
    const img = tile.querySelector('img')!
    expect(img.getAttribute('alt')).toBe('')
    // The name reaches the button BY REFERENCE, from the sibling caption — the structure that
    // lets the focus ring be the card's shape (see the card-shape assertion above).
    expect(tile.getAttribute('aria-labelledby')).toBe(
      screen.getByText('Black Lotus').getAttribute('id'),
    )
  })

  it('announces the name ONCE on the FAILED path too — the same question, a different carrier', () => {
    // THE DEFECT THIS TEST WAS WRITTEN TO CATCH, AND DID. c4-3's named placeholder centres the
    // card's name INSIDE the card box (its AC 13), so a caption underneath it would put the same
    // name on one tile twice — visibly, and twice inside one accessible name. Q4's ruling is
    // that the name is announced once; the failed path is that question with a different
    // carrier, so it gets the same answer rather than a second one.
    const { container } = render(<CardTile {...BLACK_LOTUS} />)
    fireEvent.error(imageOf(container)!)

    const tile = screen.getByRole('button')
    expect([...tile.textContent.matchAll(/Black Lotus/g)]).toHaveLength(1)
    expect(container.querySelector('.card-tile-caption')).toBeNull()
    // …and the placeholder is what is naming it now, rather than the name having been dropped.
    expect(container.querySelector('.card-placeholder-name')!.textContent).toBe('Black Lotus')
  })

  it('carries the quantity into the accessible name rather than hiding it (Q6)', () => {
    render(<CardTile {...BLACK_LOTUS} quantity={4} />)

    // UX-DR16 delegates the accessible quantity signal to "the group-header count and the
    // coalesced live-region announcement" — and this story ships NEITHER (no group headers in
    // the grid, Q5; no live region until c7-5). Delegating anyway would leave the count
    // visual-only. So the badge is not `aria-hidden`: it sits inside the button and its text
    // joins the name, which needs no authored string and therefore no COPY_MODULES entry.
    //
    // THE EXACT SPELLING, MEASURED (review 2026-08-04). This assertion's first form checked
    // membership only, on a recorded claim that jsdom runs the parts together as `×4Black
    // Lotus`. Measured with `computeAccessibleName`, that claim was false twice over: accname
    // follows `aria-labelledby` ID ORDER (caption first, badge second — the order the component
    // chose on purpose), and `dom-accessibility-api` separates the two references with a space.
    // So the strong claim is available and this is it: name first, then count, one space. What
    // no jsdom assertion carries is how a real screen READER phrases it — that stays Task 7's
    // and the epic checklist's.
    const tile = screen.getByRole('button', { name: 'Black Lotus ×4' })
    expect(tile).toBeVisible()
    expect(screen.getByText('×4').getAttribute('aria-hidden')).toBeNull()
  })

  it('smuggles no authored copy into a read-aloud attribute (AC 10)', () => {
    const { container } = render(<CardTile {...BLACK_LOTUS} quantity={4} />)
    const tile = container.querySelector('button')!

    // `copy-rules.test.ts`'s attribute half collects every literal reaching `aria-label`, `alt`,
    // `title` and six others, whatever its shape. The tile writes to none of them: the name is
    // TEXT and the quantity is a symbol plus a number, so there is no sentence to own.
    expect(tile.getAttribute('aria-label')).toBeNull()
    expect(tile.getAttribute('title')).toBeNull()
    expect(tile.getAttribute('aria-description')).toBeNull()
  })
})
