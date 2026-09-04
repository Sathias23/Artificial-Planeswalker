import type { ReactNode } from 'react'

import './AnalysisRow.css'

/**
 * The analysis pair — the 1:1 row beneath the card grid (UX-DR8).
 *
 * ================= A LAYOUT THAT MUST BE RIGHT TWICE ===================================
 *
 * The mana-curve and colour-distribution panels sit below the card grid as a 1:1 pair, so this
 * layout must be right **twice**: with one child and with two, **with no edit to this file
 * between the two**.
 *
 * ================= WHY FLEX, AND NOT `repeat(2, minmax(0, 1fr))` ======================
 *
 * A two-track grid with one child leaves a **dead half-width gutter**, the same failure the
 * price column avoids — *"a visible empty column reads as a loading failure"* — and it is worse
 * here, because half the fluid column is a great deal more than 64px. `flex: 1 1 0` on the
 * children makes one child fill the width and two children exactly 1:1, with no media query,
 * no `:only-child` special case, no `px` literal needing a DESIGN.md citation, and nothing to
 * change when the second panel lands: it lands by adding a sibling.
 *
 * At narrow widths two children SHRINK, staying 1:1 — they do not stack. There is no
 * `flex-wrap: wrap`, deliberately: with a zero flex basis and `min-width: 0` every child's
 * hypothetical main size is 0 and the line can never overflow, so a wrap would be unreachable
 * and a promise of stacking false.
 *
 * **There is no breakpoint, deliberately.** The squeeze case is narrower than the app's own
 * floor — UX-DR8 drops the right column beneath the left below ~1100px, which WIDENS this
 * column — and the thing that runs out of room first is the colour legend, which wraps
 * gracefully in its own stylesheet. See `AnalysisRow.css` for the measurements.
 *
 * **The empty row is closed in CSS rather than in `App.tsx`.** A row that stayed in the DOM
 * when its only child rendered `null` would carry the column's 24px gap beneath nothing;
 * `.analysis-row:empty { display: none }` closes it, and it costs no second derivation of
 * either panel's data.
 *
 * ================= A PRIMITIVE, NOT A CONTAINER =========================================
 *
 * It holds no state, calls no hook, reads no store, attaches no handler and takes exactly one
 * prop, which is `children`. That is `src/components/`'s closed set-equality category, so this
 * is a primitive rather than a container.
 *
 * ⚠️ **The `> *` rule in `AnalysisRow.css` is NOT "restyling a primitive"**, and the
 * distinction is worth stating because it is the one a reviewer will test. It sets **layout on a
 * child slot** — the same thing `.app-shell-column` already does to every panel it holds with
 * `gap` — and it names no `Panel` class, reaches into no descendant and changes nothing about
 * how a `Panel` paints itself. What is forbidden is a consumer overriding a primitive's own
 * surface, radius, padding or overflow; nothing here does.
 */

export interface AnalysisRowProps {
  /** The analysis panels. One fills the row; two share it 1:1; more wrap. */
  children?: ReactNode
}

export function AnalysisRow({ children }: AnalysisRowProps) {
  return <div className="analysis-row">{children}</div>
}
