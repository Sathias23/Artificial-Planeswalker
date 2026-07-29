import type { ReactNode } from 'react'

import './GroupHeader.css'

/**
 * Group header — the type-group divider ("CREATURES 24") over a hairline rule (story c2-7,
 * UX-DR12).
 *
 * PRESENTATION-ONLY (AC 5): no state, no hook, no fetch, no store, no event handler.
 *
 * AN `<h2>`, BY UX-DR44 TAKEN AS WRITTEN (AC 15, Q4). The rule reads "panel titles and
 * type-group headers h2", which makes a deck-list panel's title and its "CREATURES" divider
 * siblings at the same heading level. That is the spec's choice rather than an oversight in
 * this implementation, and it is recorded here instead of being quietly "corrected" to an
 * `h3`; c4-7 — the first story to put real group headers inside a real panel — may home a
 * correction if it reads wrong in a real screen reader.
 *
 * THE COUNT SITS BESIDE THE LABEL, NOT INSIDE IT. DESIGN.md says so for panel titles in the
 * same breath as the label role ("put the count in {typography.numeric} beside the label, not
 * inside it"), and the accessibility reason is stronger than the typographic one: a count
 * folded into the heading text becomes part of the group's announced name, so a group whose
 * size changes is a group whose NAME changes.
 */

export interface GroupHeaderProps {
  /**
   * The group's name, rendered as an `<h2>` and uppercased by CSS, not by the caller. A
   * `ReactNode`, unlike Panel's `title` — recorded, not accidental (review ruling 2026-07-29):
   * Q4 typed `title` as `string` because it doubles as the region's `aria-label`, which must
   * be a string in a hook-free component. An `<h2>`'s accessible name comes from its CONTENT,
   * so markup costs nothing here. Emptiness stays the CALLER's problem: a group header is only
   * mounted to name a group, so an empty label is caller error — the c4-7 deck list, its first
   * consumer, always has a type name to give it.
   */
  label: ReactNode
  /** The group's size, right-aligned in the numeric role. `0` renders as "0" (AC 16). */
  count?: number
}

export function GroupHeader({ label, count }: GroupHeaderProps) {
  // `Number.isFinite`, for the reason Panel's identical line gives: `{count && …}` renders the
  // bare string `0` and `count ? … : null` drops a real zero, and "CREATURES 0" is the honest
  // state of an empty group — the exact state a deck under construction passes through.
  const counted = Number.isFinite(count)

  return (
    <div className="group-header">
      <h2 className="group-header-label">{label}</h2>
      {counted ? <span className="group-header-count">{count}</span> : null}
    </div>
  )
}
