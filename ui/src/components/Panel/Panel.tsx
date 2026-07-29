import type { ReactNode } from 'react'

import { filled } from '../filled'
import './Panel.css'

/**
 * Panel — the universal container (story c2-7, UX-DR9).
 *
 * PRESENTATION-ONLY, DELIBERATELY (AC 5). It holds no state, calls no hook — not even `useId`
 * — fetches nothing, imports no store and has no event-handler prop. That is a decide-once
 * ruling rather than an omission: the day a primitive needs a hook it has stopped being a
 * presentation-only primitive, and that is a signal worth keeping rather than an inconvenience
 * to route around. `ui/tests/shell.test.ts` asserts it over all four primitives with an
 * exhaustive import list, so the posture is a gate.
 *
 * THE REGION SEMANTICS (Q4, AC 15, UX-DR44). A titled panel is a `<section>` NAMED by its
 * title, which is the per-panel `role="region"` labelling `AppShell.tsx:36-37` explicitly
 * deferred to "the panels (c2-7 onwards)". The title itself is an `<h2>`.
 *
 * `aria-label`, not `aria-labelledby`, and the reason is the hook-free rule above:
 * `aria-labelledby` needs a generated id, `useId` is a hook, and a primitive that reaches for
 * one has changed category. The consequence accepted in exchange is that `title` is typed
 * `string` rather than `ReactNode` — DESIGN.md already says panel titles are short label
 * strings and that a count goes BESIDE the label rather than inside it, so nothing is lost.
 *
 * AN UNTITLED PANEL INVENTS NO NAME. An unnamed `<section>` has no role at all, which is the
 * correct outcome: a generic invented name ("Panel") would fill a screen-reader user's
 * landmark list with identical entries to navigate past.
 */

export type PanelLevel = 'default' | 'overlay'

export interface PanelProps {
  /**
   * The header title, rendered as an `<h2>` and used as the section's accessible name. A
   * `string` by ruling, not a `ReactNode` — see the `aria-label` argument above.
   */
  title?: string
  /**
   * An optional count beside the title, in the numeric role. `0` is REAL CONTENT and renders
   * as "0" — see the `Number.isFinite` note below, which is the whole of AC 16.
   */
  count?: number
  /** Right-aligned badges. Arbitrary nodes, so emptiness is decided by `filled()` (AC 17). */
  badges?: ReactNode
  /** `--surface-panel` by default; `--surface-overlay` one step up the ramp (UX-DR1). */
  level?: PanelLevel
  /**
   * The agent has just changed something here (UX-DR9): the title swaps to `--accent`, a 6px
   * accent dot appears, and elevation rises to `--shadow-raise`. Purely a rendered state —
   * ANIMATING the transition into it belongs to c7-5, which already owns "the change is
   * announced once, and motion is never the only signal" together with its reduced-motion
   * fallback. Nothing here transitions (AC 18).
   */
  live?: boolean
  children?: ReactNode
}

export function Panel({ title, count, badges, level, live, children }: PanelProps) {
  const named = filled(title)

  /**
   * `Number.isFinite`, and NEVER `count &&` or `count ?`. Both of those are the c2-6 falsy-
   * value family arriving in a numeric prop: `{count && <span>{count}</span>}` renders the
   * bare string `0` into the DOM — something, so nobody looks — and `count ? … : null` drops a
   * real zero entirely. "CREATURES 0" is the honest state of an empty group and it has to
   * survive. `isFinite` rather than `!= null` closes the other end: a `NaN` count arriving
   * from an arithmetic slip would render the text "NaN" beside a heading.
   */
  const counted = Number.isFinite(count)

  // `filled()`, not truthiness, and imported rather than re-derived (AC 17). It is the settled
  // answer to `<></>`, `[]`, `' '`, `false` and one-shot iterables — five shapes that cost a
  // Greptile round and two review rounds to get right in c2-6, every one of which renders
  // NOTHING while looking filled to a naive check. A header mounted for an empty badge array
  // is a hairline rule under blank space.
  const hasHeader = named || counted || filled(badges)

  const classes = ['panel']
  if (level === 'overlay') classes.push('panel-overlay')
  if (live) classes.push('panel-live')

  return (
    <section className={classes.join(' ')} aria-label={named ? title : undefined}>
      {hasHeader ? (
        <header className="panel-header">
          {named ? <h2 className="panel-title">{title}</h2> : null}
          {/* DECORATION, and `aria-hidden` on purpose. The live state's accessible signal is
              the title's own colour change plus, from c7-5, a live-region announcement — a
              dot exposed as an unlabelled node would be noise in the accessibility tree
              without adding information. It renders only beside a TITLE (`named`, not merely
              inside a header — review 2026-07-29): a dot next to a bare count or badge row
              marks nothing, which is this comment's own claim, now matched by the code. A
              live panel with no title at all keeps only its elevation change, which the
              graphite and ink themes flatten to nothing — a declared hole, homed at c2-9,
              the first consumer that can decide whether a title-less live panel exists. */}
          {live && named ? <span className="panel-dot" aria-hidden="true" /> : null}
          {counted ? <span className="panel-count">{count}</span> : null}
          <div className="panel-badges">{badges}</div>
        </header>
      ) : null}
      <div className="panel-body">{children}</div>
    </section>
  )
}
