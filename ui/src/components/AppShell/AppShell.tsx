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
 * Every empty region renders a placeholder line naming the story that replaces it (AC 21), so
 * filling a region is a search for its own story id rather than an archaeology exercise.
 */

export interface AppShellProps {
  /**
   * The `h1`'s content. Provisionally the product name (Q3): keeping an `h1` present means
   * the document is never heading-less in the no-active-deck state a fresh install STARTS in,
   * and it stops c2-9's state panel (an `h2` by UX-DR44) being the highest heading on the
   * page. **c4-2 supplies the deck name here** — the element, its level and its position do
   * not move, which is the whole point of it being a prop.
   */
  deckName?: ReactNode
  /** Format and size badges, header right. c2-7 supplies Badge; c4-2 and c4-10 fill them. */
  badges?: ReactNode
  /** The agent-view nav pills, header far right. c6-8. */
  nav?: ReactNode
  /** The fluid column: the card grid (c4-4), then the curve/colour 1:1 pair (c4-8). */
  left?: ReactNode
  /** The 452px column: card detail (c4-5), deck list (c4-7), format check (c4-10). */
  right?: ReactNode
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
 * `content` if a region was filled, otherwise the placeholder line that names its owner.
 * Module-local on purpose: `react-refresh/only-export-components` is an `error` here and
 * `allowConstantExport` admits constants and types but NOT a helper function, so exporting
 * this beside the component would turn the gate red. Helpers stay unexported, or move to
 * their own module.
 */
const slot = (content: ReactNode, placeholder: string): ReactNode =>
  filled(content) ? content : <p className="app-shell-placeholder">{placeholder}</p>

export function AppShell({ deckName, badges, nav, left, right, footer, overlay }: AppShellProps) {
  return (
    <div className="app-shell">
      <header className="app-shell-header">
        <div className="app-shell-identity">
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
        </div>
        <div className="app-shell-badges">
          {/* Names the FILLERS (c4-2, c4-10) as well as the primitive's supplier (c2-7). AC 21
              exists so the story that replaces a region finds its own id in the copy — and
              c2-7 ships Badge without filling this slot, so a line naming only c2-7 is a line
              the stories that actually fill it would never search for. */}
          {slot(
            badges,
            'Format and size badges land here — c2-7 supplies the Badge primitive, c4-2 and ' +
              'c4-10 fill them.',
          )}
        </div>
        <div className="app-shell-nav">{slot(nav, 'Agent-view nav pills land here — c6-8.')}</div>
      </header>

      {/* THE SINGLE SCROLL CONTAINER (Q2). Both columns live inside it, so `main` is the one
          landmark AC 14 asks for and the one scroller the footer's pinning depends on. */}
      <main className="app-shell-columns">
        <div className="app-shell-column">
          {slot(
            left,
            'The card-art grid lands here — c4-4 — with the mana-curve and colour-distribution ' +
              'panels below it as a 1:1 pair — c4-8 composes the row, c4-9 supplies the second ' +
              'panel.',
          )}
        </div>
        <div className="app-shell-column">
          {slot(
            right,
            'Card detail — c4-5 — the deck list — c4-7 — and the format check — c4-10 — stack here.',
          )}
        </div>
      </main>

      <footer className="app-shell-footer">
        {slot(footer, 'Scryfall and Fan Content attribution lands here — c2-10.')}
      </footer>

      {/* AC 9 — the element is conditional, the SLOT is the CSS rule. Rendering `null` costs
          nothing and intercepts nothing; an unconditional wrapper would cover the page.

          `filled`, not raw truthiness — the same treatment `slot()` got, applied to the one
          place that had been left out of it. The stakes here are higher than a missing
          placeholder: `overlay={views.map(...)}` over an empty list, or `overlay={' '}`, would
          mount a full-window FIXED element containing nothing, which is exactly AC 9's
          click-swallower presenting as "the app stopped responding to clicks". */}
      {filled(overlay) ? <div className="app-shell-overlay">{overlay}</div> : null}
    </div>
  )
}
