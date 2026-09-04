import type { ReactNode } from 'react'

import { filled } from '../filled'
import './Panel.css'

/**
 * Panel — the universal container (UX-DR9).
 *
 * PRESENTATION-ONLY, DELIBERATELY. It holds no state, calls no hook — not even `useId`
 * — fetches nothing, imports no store and has no event-handler prop. That is deliberate rather
 * than an omission: the day a primitive needs a hook it has stopped being a
 * presentation-only primitive, and that is a signal worth keeping rather than an inconvenience
 * to route around. `ui/tests/shell.test.ts` asserts it over all four primitives with an
 * exhaustive import list, so the posture is a gate.
 *
 * THE REGION SEMANTICS (UX-DR44). A titled panel is a `<section>` NAMED by its
 * title, which is the per-panel `role="region"` labelling `AppShell.tsx` explicitly
 * leaves to the panels. The title itself is an `<h2>`.
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

interface PanelBaseProps {
  /**
   * The header title, rendered as an `<h2>` and used as the section's accessible name. A
   * `string` deliberately, not a `ReactNode` — see the `aria-label` argument above.
   */
  title?: string
  /**
   * An optional count beside the title, in the numeric role. `0` is REAL CONTENT and renders
   * as "0" — see the `Number.isFinite` note below.
   */
  count?: number
  /** Right-aligned badges. Arbitrary nodes, so emptiness is decided by `filled()`. */
  badges?: ReactNode
  /** `--surface-panel` by default; `--surface-overlay` one step up the ramp (UX-DR1). */
  level?: PanelLevel
  children?: ReactNode
}

/**
 * `live`: the agent has just changed something here (UX-DR9): the title swaps to `--accent`, a
 * 6px accent dot appears, and elevation rises to `--shadow-raise`. Purely a rendered state —
 * and it STAYS one. Nothing here transitions: `live` has NO production producer — only
 * `Panel.test.tsx` and `CardGrid`'s bare `<Panel>` mount this component, and neither sets it —
 * so animating a transition nothing enters is unverifiable at any surface. The code that first
 * SETS `live` owns the animation, together with its reduced-motion registration in tokens.css's
 * media block.
 *
 * **`live` REQUIRES a `title`, IN THE TYPE.** A title-less live panel: with no title to recolour
 * and no dot to hang beside it, all that remains is the elevation change, which `graphite` and
 * `ink` flatten to nothing — an absent signal, not a degraded one, so the type refuses the
 * combination rather than leaving it to a comment. See the dot's comment in the header below
 * for the whole argument. The render path below still guards (`live && named`) because a JS
 * caller is not bound by this union — the type is the gate, the guard is the floor.
 */
export type PanelProps = PanelBaseProps & ({ live?: false } | { live: true; title: string })

export function Panel({ title, count, badges, level, live, children }: PanelProps) {
  const named = filled(title)

  /**
   * `Number.isFinite`, and NEVER `count &&` or `count ?`. Both of those are the falsy-value
   * family arriving in a numeric prop: `{count && <span>{count}</span>}` renders the
   * bare string `0` into the DOM — something, so nobody looks — and `count ? … : null` drops a
   * real zero entirely. "CREATURES 0" is the honest state of an empty group and it has to
   * survive. `isFinite` rather than `!= null` closes the other end: a `NaN` count arriving
   * from an arithmetic slip would render the text "NaN" beside a heading.
   */
  const counted = Number.isFinite(count)

  // `filled()`, not truthiness, and imported rather than re-derived. It is the settled
  // answer to `<></>`, `[]`, `' '`, `false` and one-shot iterables — five shapes every one of
  // which renders NOTHING while looking filled to a naive check. A header mounted for an empty
  // badge array is a hairline rule under blank space.
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
              the title's own colour change plus a live-region announcement — a dot exposed as
              an unlabelled node would be noise in the accessibility tree without adding
              information. It renders only beside a TITLE (`named`, not merely inside a header):
              a dot next to a bare count or badge row marks nothing.

              THE TITLE-LESS LIVE PANEL DOES NOT EXIST. `live` requires a `title`. A live panel
              with no title keeps only its elevation change, and `graphite` and `ink` declare
              both elevation tokens as `none`, so under two of the five shipped themes it
              renders IDENTICALLY to a resting panel: the agent changed something and the UI
              says nothing at all. That is not a degraded signal, it is an absent one. `live`
              is therefore a modifier on a NAMED panel, and a caller wanting a live marker on an
              unnamed container is being told to name it. (The state panel is NOT a `Panel`:
              DESIGN.md declares a separate `components.state-panel.*` block, and its headline
              is `--type-heading` where a Panel's title is `--type-label`.) */}
          {live && named ? <span className="panel-dot" aria-hidden="true" /> : null}
          {counted ? <span className="panel-count">{count}</span> : null}
          <div className="panel-badges">{badges}</div>
        </header>
      ) : null}
      <div className="panel-body">{children}</div>
    </section>
  )
}
