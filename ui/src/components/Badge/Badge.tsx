import type { ReactNode } from 'react'

import { filled } from '../filled'
import './Badge.css'
import { BADGE_TONES, type BadgeTone } from './tones'

/**
 * Badge — the pill label, in five tones (story c2-7, UX-DR10).
 *
 * PRESENTATION-ONLY (AC 5): no state, no hook, no fetch, no store, no event handler. Its
 * entire contract is "render these children in this tone", and `ui/tests/shell.test.ts`
 * asserts that with an exhaustive import list rather than leaving it to inspection.
 *
 * THE TONE IS A CLASS, NOT A STYLE OBJECT. The mock keeps a `tones` lookup table of literal
 * colour triples and spreads it into an inline `style` — which is an ESLint error here, and
 * would be wrong even if it were not: every literal in that table is invisible to the four
 * alternate themes (`gilt`, `graphite`, `verdigris`, `ink`), which is the exact defect UX-DR10
 * names. The tint mechanism is in Badge.css, once per tone, in tokens.
 *
 * THE TONE LIST LIVES IN `./tones`, not here. It is exported because it is the non-vacuity
 * anchor for the per-tone tests — a loop over a list that quietly lost a member passes by
 * iterating over four things — and exporting it BESIDE the component is a lint error:
 * `react-refresh/only-export-components`'s `allowConstantExport` does not admit an array
 * initialiser, measured on this very file. So it takes the route `filled.ts` established: the
 * datum moves to its own module rather than the gate being relaxed to fit it.
 */

export interface BadgeProps {
  /**
   * One of DESIGN.md's five tones. Defaults to `neutral` — and an UNKNOWN tone lands on
   * neutral too (review ruling 2026-07-29): the type admits only the five, but tones will
   * eventually arrive as server data (c4-10's format legality, c9's tiers), and an unchecked
   * `badge-${tone}` would render an unstyled `badge-bogus` pill. Clamping to the same list the
   * per-tone tests anchor on keeps the failure mode "wrong tone" rather than "no tone".
   */
  tone?: BadgeTone
  /** The pill's content. An EMPTY shape renders nothing — see the `filled()` note below. */
  children?: ReactNode
}

export function Badge({ tone = 'neutral', children }: BadgeProps) {
  // `filled()`, not truthiness (AC 17, review ruling 2026-07-29): a Badge with no content is a
  // bordered, washed, empty pill — visible chrome announcing nothing. `<></>`, `[]` and `' '`
  // all look filled to a naive check while rendering nothing inside it.
  if (!filled(children)) return null

  const shown = BADGE_TONES.includes(tone) ? tone : 'neutral'
  return <span className={`badge badge-${shown}`}>{children}</span>
}
