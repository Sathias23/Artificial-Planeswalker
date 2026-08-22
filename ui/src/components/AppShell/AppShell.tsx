import type { ReactNode } from 'react'

import './AppShell.css'
// `filled` lives in its own module because deciding whether a Fragment is empty needs VALUE
// imports from react, and this file's react import is pinned type-only by a guard. See
// filled.ts for the whole argument and for the limit it cannot cover. It sits one level up,
// in `src/components/`, because story c2-7's Panel needs the identical logic for its header
// slots (Q3) — a helper shared by two components does not live inside one of them.
import { filled } from '../filled'

/**
 * The two-column application shell — header, two columns, pinned footer, overlay slot.
 *
 * This is the first component in the codebase, so it sets four conventions the ~35 later
 * component stories inherit rather than re-litigate (Brad's rulings, 2026-07-28):
 *
 *   WHERE THE FILES LIVE (Q1) — `src/components/<Name>/{<Name>.tsx, <Name>.css,
 *   <Name>.test.tsx}`. A directory per component, no `index.ts` barrels. The colocated
 *   `.test.tsx` lands in the `dom` vitest project automatically and satisfies
 *   gate-geometry.test.ts's "no `.tsx` tests under tests/" rule with no thought.
 *
 *   HOW CLASSES ARE NAMED — flat kebab-case, prefixed with the component
 *   (`app-shell-header`), never BEM's `__`/`--`. Not taste: stylelint-config-standard's
 *   `selector-class-pattern` is `^([a-z][a-z0-9]*)(-[a-z0-9]+)*$`, so `app-shell__header` is
 *   a lint ERROR — measured on this very stylesheet with the `-` swapped for `__`: **12
 *   errors, all `selector-class-pattern`**. The gate had already picked a convention;
 *   loosening it to fit a habit would have been the wrong repair.
 *
 *   WHO OWNS THE SCROLL (Q2) — this shell does, once. The root is `100dvh` and the `<main>`
 *   between the header and the footer is the SINGLE scroll container. No later component
 *   introduces a second window-level scroller. The footer is then literally always in the
 *   window, which is what UX-DR32 and NFR-08 require of it.
 *
 *   LANDMARKS (Q4) — `header` / `main` / `footer`, with BOTH columns inside the one `main`.
 *   The right column is a plain container, NOT an `<aside>`: it holds the deck list, which is
 *   FR-05's primary content satisfied "as a permanent second column rather than a toggled
 *   alternate view" (EXPERIENCE.md), and `complementary` would demote exactly the thing the
 *   redesign promoted. Per-panel `role="region"` labels are UX-DR44's, and belong to the
 *   panels (c2-7 onwards), not here.
 *
 * PRESENTATION-ONLY, DELIBERATELY (AC 16). It holds no state, fetches nothing, imports no
 * store and subscribes to nothing; every region arrives through a prop. c4-1 owns the store
 * and c3-1 owns the fetch layer, and a shell that reached for either would pre-empt both
 * designs. `ui/tests/shell.test.ts` asserts this rather than leaving it to inspection, so the
 * posture is a gate and not an omission.
 *
 * An empty region renders NOTHING (17.5). From c2-1 to 17.4 it rendered a placeholder line
 * naming the story that would fill it (AC 21) — scaffolding copy with a scheduled death, which
 * came once every region had an owner. When `right` is empty the second column is not rendered
 * and the grid collapses to one track (`data-single`), so the Welcome surface gets the width.
 */

export interface AppShellProps {
  /**
   * The skip link (c4-11), rendered as the FIRST child of the shell — before the `<header>`.
   *
   * ==== THIS IS AN EXCEPTION TO THE c2-9 DISPLACEMENT RULING, NOT AN APPLICATION OF IT ====
   * Nine consecutive stories filled a region by DISPLACING a placeholder inside an existing slot,
   * and this file was not edited once in any of them. A skip link cannot work that way: it must be
   * the first Tab stop in the document, so it must PRECEDE the `<header>`, and there is no slot
   * there to displace. Calling it what it is matters more than preserving a streak — the ruling
   * held for nine stories because every one of those stories genuinely had a slot.
   *
   * ==== WHY IT IS NOT INSIDE `<header>` (c4-11 Q5) ======================================
   * The alternative was to make it the header's first child, which needs no new prop. Declined: a
   * skip link is not banner content, and putting it inside `banner` makes it part of a landmark's
   * accessible content for no benefit to anyone. Here it is outside ALL THREE landmarks, which is
   * what `AppShell.test.tsx` now asserts alongside the counts.
   *
   * **The landmark counts do not move**: still exactly one `banner`, one `main`, one `contentinfo`.
   * A `<div>` before the header is not a landmark, and this slot must never become a fourth.
   *
   * NO PLACEHOLDER — originally the one deliberate break from every other slot in this file, when
   * every empty region below rendered a line naming the story that fills it (AC 21): that line was
   * rendered TEXT, and this element sits before the header on every surface including the ones
   * where the link is correctly absent, so a story key here would have sat on the glass permanently
   * in the most prominent position in the document (the C3 retro's F1 defect). Since 17.5 every
   * slot renders nothing when empty, so this is no longer an exception. `undefined` renders nothing.
   */
  skipLink?: ReactNode
  /**
   * The `h1`'s content. Provisionally the product name (Q3): keeping an `h1` present means
   * the document is never heading-less in the no-active-deck state a fresh install STARTS in,
   * and it stops c2-9's state panel (an `h2` by UX-DR44) being the highest heading on the
   * page. **c4-2 supplies the deck name here** — the element, its level and its position do
   * not move, which is the whole point of it being a prop.
   */
  deckName?: ReactNode
  /**
   * Whether the deck on the glass is being re-read right now (c7-4, UX-DR35, UX-DR42).
   *
   * True puts `data-updating` on the identity block — the CSS hook for the header's updating
   * veil — and renders a hidden static "Updating…" line beneath the `h1`, which the reduced-
   * motion block in `tokens.css` swaps in for the veil. The span is `aria-hidden` with no role
   * and no live region: announcing the CHANGE is c7-5's, on completion, through the pinned
   * live-region inventory — an in-flight murmur here would be a fourth announcement mechanism.
   * The `<h1>` itself is untouched (focus-restore target; "exactly one h1" is pinned), so the
   * marker is a sibling and an attribute, never a wrapper.
   *
   * ==== THE CALLER'S CONTRACT: GATE THIS ON A LOADED DECK ================================
   * This component renders whatever it is told — pass `updating` with no `deckName` and it will
   * happily mark a deckless header as updating. That is deliberate, not an oversight: the shell
   * is presentation-only (AC 16) and holds no store to second-guess a caller with, so the
   * invariant "no marker unless a deck is on the glass" lives at the ONE call site — `App.tsx`
   * passes `deck !== null && deckUpdating`, reading `surfaceOf`'s own answer. A second caller
   * inherits that obligation, not a safety net here.
   */
  updating?: boolean
  /** Format and size badges, header right. c2-7 supplies Badge; c4-2 and c4-10 fill them. */
  badges?: ReactNode
  /** The agent-view nav pills, header far right. c6-8. */
  nav?: ReactNode
  /** The fluid column: the card grid (c4-4), then the curve/colour 1:1 pair (c4-8). */
  left?: ReactNode
  /** The 452px column: card detail (c4-5), deck list (c4-7), format check (c4-10). */
  right?: ReactNode
  /**
   * The connection pill (c5-7), rendered between `</main>` and `<footer>`.
   *
   * ==== THE SECOND EXCEPTION TO THE c2-9 DISPLACEMENT RULING, AND THE SECOND NEW SLOT ====
   * `skipLink` above is the first, and this is its mirror image at the other end of the document:
   * a region whose POSITION is the requirement, with no existing slot to displace. The skip link
   * must precede the `<header>`; the pill must follow the `</main>` and precede the `<footer>`,
   * and there was no element between those two.
   *
   * ==== WHY THIS POSITION, WHICH IS A RULING THIS PROP EXISTS TO RECORD (c5-7 Q1, dw:4597) ====
   * Three artefacts each assumed someone else had decided it: UX-DR40 put the pill between the
   * deck rows and the footer, c10-1 calls it *"the last stop before the footer"*, and
   * `DESIGN.md:479` places it physically **bottom-left** — the opposite column from the deck rows.
   * c4-11 declined to decide without the component and re-homed it here by name.
   *
   * Ruled (Brad, 2026-08-08): document order places it AFTER both columns and IMMEDIATELY BEFORE
   * the footer, which makes it the last Tab stop before the footer links — satisfying UX-DR40's
   * enumeration and c10-1's wording at once — while `ConnectionPill.css` pins it visually to the
   * bottom-left corner. The alternative, an in-flow last child of the LEFT column, would place it
   * before the entire right column in Tab order and contradict all three artefacts.
   *
   * ==== WHY A PROP AND NOT THE LEFT SLOT'S FRAGMENT ======================================
   * `App.tsx` renders `<StatePanel>` into `left` in five of its six arms, so the deck-arm Fragment
   * that c4-8 and c4-9 extended is reachable on ONE surface. The pill's AC 1 is *every* surface —
   * every state panel, an empty deck and a cold open included — so mounting it there would fail
   * silently on the five surfaces nobody would think to check. A slot is the honest shape.
   *
   * NO PLACEHOLDER, the skip link's reason applied a second time: this element is FIXED to a
   * window corner on every surface, so a placeholder line here would put a story key permanently
   * on the glass in one of the most persistent positions in the document — the C3 retro's F1
   * defect, made worse by never scrolling away. `undefined` renders nothing at all.
   *
   * **The landmark counts do not move**: still exactly one `banner`, one `main`, one `contentinfo`.
   * A `<div>` between `main` and `footer` is not a landmark, and this slot must never become one.
   */
  connectionPill?: ReactNode
  /** Scryfall and Fan Content attribution. c2-10. */
  footer?: ReactNode
  /**
   * The agent view (c6-5). When absent the slot renders NOTHING — see AC 9: an
   * always-present transparent full-window element is a click-swallower that presents as
   * "the app stopped responding to clicks", which is the default outcome of "reserve a slot"
   * read literally. The slot is reserved in CSS; the element is conditional.
   */
  overlay?: ReactNode
}

/**
 * `content` if a region was filled, otherwise NOTHING. Until story 17.5 this returned a
 * placeholder line naming the story that would fill the region (c2-1, AC 21); every region has
 * had an owner since c6-8, so that copy met its scheduled death and the helper now only keeps
 * `filled()`'s semantics in one place — `false`, `[]`, an empty Fragment and an empty Set all
 * still count as empty, and a non-empty array still renders.
 * Module-local on purpose: `react-refresh/only-export-components` is an `error` here and
 * `allowConstantExport` admits constants and types but NOT a helper function, so exporting
 * this beside the component would turn the gate red. Helpers stay unexported, or move to
 * their own module.
 */
const slot = (content: ReactNode): ReactNode => (filled(content) ? content : null)

export function AppShell({
  skipLink,
  deckName,
  updating,
  badges,
  nav,
  left,
  right,
  connectionPill,
  footer,
  overlay,
}: AppShellProps) {
  return (
    <div className="app-shell">
      {/* FIRST IN DOCUMENT ORDER, WHICH IS FIRST IN TAB ORDER (c4-11, AC 1).
          Nothing in this app carries a `tabindex`, so the Tab order IS the document order (c4-6's
          ruling) — which makes "the first Tab stop" a statement about THIS LINE'S POSITION and
          nothing else. It is outside `<header>`, `<main>` and `<footer>`, so the three landmark
          counts are unchanged; `AppShell.test.tsx` asserts both halves.

          Rendered bare rather than through `slot()` — historically because that helper substituted
          a placeholder naming the owning story, and this region had to render NOTHING when empty
          (see the prop's docstring). Since 17.5 `slot()` renders nothing too; the bare form stays
          as the stronger statement. */}
      {skipLink}
      <header className="app-shell-header">
        {/* `data-updating` on the IDENTITY BLOCK, not the header — the `.agent-view[data-entering]`
            idiom: state travels as an attribute and the stylesheet decides what it looks like
            (c7-4). Present only while true, so the resting DOM carries no vestigial attribute. */}
        <div className="app-shell-identity" data-updating={updating ? 'true' : undefined}>
          {/* The product kicker, per DESIGN.md's "product kicker + deck name (left)". Until
              c4-2 lands a deck name in the h1 below, the two carry the same string — that is
              Q3's accepted consequence of never leaving the page heading-less, not an
              oversight, and c4-2 resolves it by supplying `deckName`. */}
          <span className="app-shell-kicker">Artificial Planeswalker</span>
          {/* `filled`, not a default parameter: a default fires only on `undefined`, so an
              empty string or null from a loading gap would render an EMPTY h1 and leave the
              page effectively heading-less — the exact state Q3 exists to prevent. */}
          <h1 className="app-shell-deck-name">
            {filled(deckName) ? deckName : 'Artificial Planeswalker'}
          </h1>
          {/* The reduced-motion fallback's text (c7-4, UX-DR42): hidden by default, shown only by
              `tokens.css`'s media block while the veil is neutralised. A `<span>` — never a
              `<header>`/`<section>` (banner and region censuses are pinned) — with
              `aria-hidden="true"`, no role and no `aria-live`: the marker is visual state, and the
              announcement inventory is c7-5's. "Updating…" is authored copy (this file is in
              COPY_MODULES), spelled with U+2026 per the epic AC and the DR-42 inventory verbatim —
              the c5-7 ellipsis ban does not apply, because this names a bounded in-flight window
              that provably ends, not a steady state promising banned animation. */}
          {updating ? (
            <span className="app-shell-updating" aria-hidden="true">
              Updating…
            </span>
          ) : null}
        </div>
        <div className="app-shell-badges">{slot(badges)}</div>
        <div className="app-shell-nav">{slot(nav)}</div>
      </header>

      {/* THE SINGLE SCROLL CONTAINER (Q2). Both columns live inside it, so `main` is the one
          landmark AC 14 asks for and the one scroller the footer's pinning depends on. */}
      <main className="app-shell-columns" data-single={filled(right) ? undefined : 'true'}>
        {/* `data-single` ON THE GRID, present only when the right column is empty (17.5): the
            `data-updating` idiom — state travels as an attribute and the stylesheet decides what
            it looks like. The second column is then not rendered at all rather than rendered
            empty, so the Welcome surface gets the full width instead of a dead 452px track. */}
        <div className="app-shell-column">{slot(left)}</div>
        {filled(right) ? <div className="app-shell-column">{right}</div> : null}
      </main>

      {/* AFTER BOTH COLUMNS, BEFORE THE FOOTER — WHICH IS THE WHOLE OF THE RULING (c5-7 Q1).
          Nothing in this app carries a `tabindex`, so the Tab order IS the document order (c4-6's
          ruling), and this line's position is therefore the entire statement "the pill is the last
          Tab stop before the footer links". `UX-DR40`'s enumeration and `EXPERIENCE.md`'s Tab-order
          cell were updated from their "(connection pill — c5-7)" markers to this shipped truth in
          the same commit.

          Rendered bare rather than through `slot()`, for the skip link's reason (and, since 17.5,
          with the same result either way). See the prop. */}
      {connectionPill}
      <footer className="app-shell-footer">{slot(footer)}</footer>

      {/* AC 9 — the element is conditional, the SLOT is the CSS rule. Rendering `null` costs
          nothing and intercepts nothing; an unconditional wrapper would cover the page.

          `filled`, not raw truthiness — the same treatment `slot()` got, applied to the one
          place that had been left out of it. The stakes here are higher than a blank region:
          `overlay={views.map(...)}` over an empty list, or `overlay={' '}`, would
          mount a full-window FIXED element containing nothing, which is exactly AC 9's
          click-swallower presenting as "the app stopped responding to clicks". */}
      {filled(overlay) ? <div className="app-shell-overlay">{overlay}</div> : null}
    </div>
  )
}
