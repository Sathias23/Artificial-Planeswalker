import type { ReactNode } from 'react'

import './AnalysisRow.css'

/**
 * The analysis pair — the 1:1 row beneath the card grid (story c4-8, Q6, AC 3, UX-DR8).
 *
 * ================= THIS ROW WAS ASSIGNED TO c4-8 BY NAME, BEFORE ITS SECOND CHILD EXISTS =
 *
 * `AppShell.tsx:124-129`, in the placeholder this story displaces: *"the mana-curve and
 * colour-distribution panels below it as a 1:1 pair — **c4-8 composes the row**, c4-9 supplies
 * the second panel."* So the deliverable is a layout that must be right **twice**: one child
 * today, two the day c4-9 lands, **with no edit to this file when that happens**.
 *
 * ================= WHY FLEX, AND NOT `repeat(2, minmax(0, 1fr))` ======================
 *
 * A two-track grid with one child leaves a **dead half-width gutter**, which is the exact
 * failure c4-7's Q1 rejected in the price column — *"a visible empty column reads as a loading
 * failure"* — and it is worse here, because half the fluid column is a great deal more than
 * 64px. `flex: 1 1 0` on the children makes one child fill the width and two children exactly
 * 1:1, with no media query, no `:only-child` special case, no `px` literal needing a DESIGN.md
 * citation, and nothing for c4-9 to change: that story lands by adding a sibling.
 *
 * At narrow widths two children SHRINK, staying 1:1 — they do not stack. The shipped draft
 * carried a `flex-wrap: wrap` and a comment promising stacking; the review removed both,
 * because with a zero flex basis and `min-width: 0` every child's hypothetical main size is 0
 * and the line can never overflow — the wrap was unreachable and the promise false. If c4-9
 * wants a real stacking breakpoint for the two-panel row, that is a non-zero flex-basis with a
 * derived, cited value — that story's decision, named here so its author finds a decision
 * rather than a surprise.
 *
 * ================= A PRIMITIVE, NOT A CONTAINER (c4-4 Q1, ruling 1) ===================
 *
 * It holds no state, calls no hook, reads no store, attaches no handler and takes exactly one
 * prop, which is `children`. That is `src/components/`'s closed set-equality category, so this
 * is the eighteenth primitive rather than the fourteenth container.
 *
 * ⚠️ **The `> *` rule in `AnalysisRow.css` is NOT "restyling a primitive"** (ruling 13), and the
 * distinction is worth stating because it is the one a reviewer will test. It sets **layout on a
 * child slot** — the same thing `.app-shell-column` already does to every panel it holds with
 * `gap` — and it names no `Panel` class, reaches into no descendant and changes nothing about
 * how a `Panel` paints itself. What ruling 13 forbids is a consumer overriding a primitive's own
 * surface, radius, padding or overflow; nothing here does.
 */

export interface AnalysisRowProps {
  /** The analysis panels. One fills the row; two share it 1:1; more wrap. */
  children?: ReactNode
}

export function AnalysisRow({ children }: AnalysisRowProps) {
  return <div className="analysis-row">{children}</div>
}
