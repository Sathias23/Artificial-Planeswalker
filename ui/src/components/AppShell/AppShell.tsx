import type { ReactNode } from 'react'

import './AppShell.css'
// `filled` lives in its own module because deciding whether a Fragment is empty needs VALUE
// imports from react, and this file's react import is pinned type-only by a guard. See
// filled.ts for the whole argument and for the limit it cannot cover. It sits one level up,
// in `src/components/`, because Panel needs the identical logic for its header slots — a
// helper shared by two components does not live inside one of them.
import { filled } from '../filled'

/**
 * The two-column application shell — header, two columns, pinned footer, overlay slot.
 *
 * This is the first component in the codebase, so it sets four conventions every later
 * component inherits rather than re-litigates:
 *
 *   WHERE THE FILES LIVE — `src/components/<Name>/{<Name>.tsx, <Name>.css,
 *   <Name>.test.tsx}`. A directory per component, no `index.ts` barrels. The colocated
 *   `.test.tsx` lands in the `dom` vitest project automatically and satisfies
 *   gate-geometry.test.ts's "no `.tsx` tests under tests/" rule with no thought.
 *
 *   HOW CLASSES ARE NAMED — flat kebab-case, prefixed with the component
 *   (`app-shell-header`), never BEM's `__`/`--`. Not taste: stylelint-config-standard's
 *   `selector-class-pattern` is `^([a-z][a-z0-9]*)(-[a-z0-9]+)*$`, so `app-shell__header` is
 *   a lint ERROR — measured on this very stylesheet with the `-` swapped for `__`: 12
 *   errors, all `selector-class-pattern`. The gate had already picked a convention;
 *   loosening it to fit a habit would have been the wrong repair.
 *
 *   WHO OWNS THE SCROLL — this shell does, once. The root is `100dvh` and the `<main>`
 *   between the header and the footer is the SINGLE scroll container. No later component
 *   introduces a second window-level scroller. The footer is then literally always in the
 *   window, which is what UX-DR32 and NFR-08 require of it.
 *
 *   LANDMARKS — `header` / `main` / `footer`, with BOTH columns inside the one `main`.
 *   The right column is a plain container, NOT an `<aside>`: it holds the deck list, which is
 *   FR-05's primary content satisfied "as a permanent second column rather than a toggled
 *   alternate view" (EXPERIENCE.md), and `complementary` would demote exactly the thing the
 *   redesign promoted. Per-panel `role="region"` labels are UX-DR44's, and belong to the
 *   panels, not here.
 *
 * PRESENTATION-ONLY, DELIBERATELY. It holds no state, fetches nothing, imports no store and
 * subscribes to nothing; every region arrives through a prop. The store and the fetch layer
 * each have their own owner, and a shell that reached for either would pre-empt both designs.
 * `ui/tests/shell.test.ts` asserts this rather than leaving it to inspection, so the posture
 * is a gate and not an omission.
 *
 * An empty region renders NOTHING. When `right` is empty the second column is not rendered
 * and the grid collapses to one track (`data-single`), so the Welcome surface gets the width.
 */

export interface AppShellProps {
  /**
   * The skip link, rendered as the FIRST child of the shell — before the `<header>`.
   *
   * Every other region fills an existing slot. A skip link cannot work that way: it must be the
   * first Tab stop in the document, so it must PRECEDE the `<header>`, and there is no slot
   * there to displace.
   *
   * ==== WHY IT IS NOT INSIDE `<header>` ==================================================
   * The alternative was to make it the header's first child, which needs no new prop. Declined: a
   * skip link is not banner content, and putting it inside `banner` makes it part of a landmark's
   * accessible content for no benefit to anyone. Here it is outside ALL THREE landmarks, which is
   * what `AppShell.test.tsx` now asserts alongside the counts.
   *
   * **The landmark counts do not move**: still exactly one `banner`, one `main`, one `contentinfo`.
   * A `<div>` before the header is not a landmark, and this slot must never become a fourth.
   *
   * `undefined` renders nothing. This element sits before the header on every surface, including
   * the ones where the link is correctly absent, so nothing may ever stand in for it.
   */
  skipLink?: ReactNode
  /**
   * The `h1`'s content. Defaults to the product name: keeping an `h1` present means the
   * document is never heading-less in the no-active-deck state a fresh install STARTS in, and
   * it stops the state panel (an `h2` by UX-DR44) being the highest heading on the page. The
   * deck arm supplies the deck name here — the element, its level and its position do not
   * move, which is the whole point of it being a prop.
   */
  deckName?: ReactNode
  /**
   * Whether the deck on the glass is being re-read right now (UX-DR35, UX-DR42).
   *
   * True puts `data-updating` on the identity block — the CSS hook for the header's updating
   * veil — and renders a hidden static "Updating…" line beneath the `h1`, which the reduced-
   * motion block in `tokens.css` swaps in for the veil. The span is `aria-hidden` with no role
   * and no live region: announcing the CHANGE happens once, on completion, through the pinned
   * live-region inventory — an in-flight murmur here would be a fourth announcement mechanism.
   * The `<h1>` itself is untouched (focus-restore target; "exactly one h1" is pinned), so the
   * marker is a sibling and an attribute, never a wrapper.
   *
   * ==== THE CALLER'S CONTRACT: GATE THIS ON A LOADED DECK ================================
   * This component renders whatever it is told — pass `updating` with no `deckName` and it will
   * happily mark a deckless header as updating. That is deliberate, not an oversight: the shell
   * is presentation-only and holds no store to second-guess a caller with, so the
   * invariant "no marker unless a deck is on the glass" lives at the ONE call site — `App.tsx`
   * passes `deck !== null && deckUpdating`, reading `surfaceOf`'s own answer. A second caller
   * inherits that obligation, not a safety net here.
   */
  updating?: boolean
  /** Format and size badges, header right. */
  badges?: ReactNode
  /** The agent-view nav pills, header far right. */
  nav?: ReactNode
  /** The fluid column: the card grid, then the curve/colour 1:1 pair. */
  left?: ReactNode
  /** The 452px column: card detail, deck list, format check. */
  right?: ReactNode
  /**
   * The connection pill, rendered between `</main>` and `<footer>`.
   *
   * Like `skipLink`, this is a region whose POSITION is the requirement, with no existing slot
   * to displace: the pill must follow the `</main>` and precede the `<footer>`, and there was
   * no element between those two.
   *
   * ==== WHY THIS POSITION ================================================================
   * UX-DR40 puts the pill between the deck rows and the footer, and `DESIGN.md` places it
   * physically bottom-left — the opposite column from the deck rows. Document order places it
   * AFTER both columns and IMMEDIATELY BEFORE the footer, which makes it the last Tab stop
   * before the footer links — satisfying UX-DR40's enumeration — while `ConnectionPill.css`
   * pins it visually to the bottom-left corner. The alternative, an in-flow last child of the
   * LEFT column, would place it before the entire right column in Tab order.
   *
   * ==== WHY A PROP AND NOT THE LEFT SLOT'S FRAGMENT ======================================
   * `App.tsx` renders `<StatePanel>` into `left` in five of its six arms, so the deck-arm
   * Fragment is reachable on ONE surface. The pill is required on *every* surface — every state
   * panel, an empty deck and a cold open included — so mounting it there would fail silently on
   * the five surfaces nobody would think to check. A slot is the honest shape.
   *
   * `undefined` renders nothing at all: this element is FIXED to a window corner on every
   * surface, so nothing may ever stand in for it.
   *
   * **The landmark counts do not move**: still exactly one `banner`, one `main`, one `contentinfo`.
   * A `<div>` between `main` and `footer` is not a landmark, and this slot must never become one.
   */
  connectionPill?: ReactNode
  /** Scryfall and Fan Content attribution. */
  footer?: ReactNode
  /**
   * The agent view. When absent the slot renders NOTHING: an always-present transparent
   * full-window element is a click-swallower that presents as
   * "the app stopped responding to clicks", which is the default outcome of "reserve a slot"
   * read literally. The slot is reserved in CSS; the element is conditional.
   */
  overlay?: ReactNode
}

/**
 * `content` if a region was filled, otherwise NOTHING. Keeps `filled()`'s semantics in one
 * place — `false`, `[]`, an empty Fragment and an empty Set all count as empty, and a
 * non-empty array renders.
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
      {/* FIRST IN DOCUMENT ORDER, WHICH IS FIRST IN TAB ORDER.
          Nothing in this app carries a `tabindex`, so the Tab order IS the document order —
          which makes "the first Tab stop" a statement about THIS LINE'S POSITION and nothing
          else. It is outside `<header>`, `<main>` and `<footer>`, so the three landmark counts
          are unchanged; `AppShell.test.tsx` asserts both halves.

          Rendered bare rather than through `slot()`: this region must render NOTHING when empty
          (see the prop's docstring), and the bare form is the stronger statement of that. */}
      {skipLink}
      <header className="app-shell-header">
        {/* `data-updating` on the IDENTITY BLOCK, not the header — the `.agent-view[data-entering]`
            idiom: state travels as an attribute and the stylesheet decides what it looks like.
            Present only while true, so the resting DOM carries no vestigial attribute. */}
        <div className="app-shell-identity" data-updating={updating ? 'true' : undefined}>
          {/* The product kicker, per DESIGN.md's "product kicker + deck name (left)". With no
              deck name in the h1 below, the two carry the same string — the accepted
              consequence of never leaving the page heading-less, not an oversight. */}
          <span className="app-shell-kicker">Artificial Planeswalker</span>
          {/* `filled`, not a default parameter: a default fires only on `undefined`, so an
              empty string or null from a loading gap would render an EMPTY h1 and leave the
              page effectively heading-less — the exact state the fallback exists to prevent. */}
          <h1 className="app-shell-deck-name">
            {filled(deckName) ? deckName : 'Artificial Planeswalker'}
          </h1>
          {/* The reduced-motion fallback's text (UX-DR42): hidden by default, shown only by
              `tokens.css`'s media block while the veil is neutralised. A `<span>` — never a
              `<header>`/`<section>` (banner and region censuses are pinned) — with
              `aria-hidden="true"`, no role and no `aria-live`: the marker is visual state, and the
              announcement inventory lives with the live regions. "Updating…" is authored copy
              (this file is in COPY_MODULES), spelled with U+2026 per the DR-42 inventory verbatim —
              the ellipsis ban does not apply, because this names a bounded in-flight window that
              provably ends, not a steady state promising banned animation. */}
          {updating ? (
            <span className="app-shell-updating" aria-hidden="true">
              Updating…
            </span>
          ) : null}
        </div>
        <div className="app-shell-badges">{slot(badges)}</div>
        <div className="app-shell-nav">{slot(nav)}</div>
      </header>

      {/* THE SINGLE SCROLL CONTAINER. Both columns live inside it, so `main` is the one
          landmark and the one scroller the footer's pinning depends on. */}
      <main className="app-shell-columns" data-single={filled(right) ? undefined : 'true'}>
        {/* `data-single` ON THE GRID, present only when the right column is empty: the
            `data-updating` idiom — state travels as an attribute and the stylesheet decides what
            it looks like. The second column is then not rendered at all rather than rendered
            empty, so the Welcome surface gets the full width instead of a dead 452px track. */}
        <div className="app-shell-column">{slot(left)}</div>
        {filled(right) ? <div className="app-shell-column">{right}</div> : null}
      </main>

      {/* AFTER BOTH COLUMNS, BEFORE THE FOOTER. Nothing in this app carries a `tabindex`, so the
          Tab order IS the document order, and this line's position is therefore the entire
          statement "the pill is the last Tab stop before the footer links" — `UX-DR40`'s
          enumeration and `EXPERIENCE.md`'s Tab-order cell.

          Rendered bare rather than through `slot()`, for the skip link's reason. See the prop. */}
      {connectionPill}
      <footer className="app-shell-footer">{slot(footer)}</footer>

      {/* The element is conditional, the SLOT is the CSS rule. Rendering `null` costs
          nothing and intercepts nothing; an unconditional wrapper would cover the page.

          `filled`, not raw truthiness — the same treatment `slot()` gets. The stakes here are
          higher than a blank region: `overlay={views.map(...)}` over an empty list, or
          `overlay={' '}`, would mount a full-window FIXED element containing nothing, which is
          exactly the click-swallower presenting as "the app stopped responding to clicks". */}
      {filled(overlay) ? <div className="app-shell-overlay">{overlay}</div> : null}
    </div>
  )
}
