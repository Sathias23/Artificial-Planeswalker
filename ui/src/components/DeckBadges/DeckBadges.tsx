import { Badge } from '../Badge/Badge'
import './DeckBadges.css'

/**
 * The deck header's format and size badges — `Badge`'s first on-screen consumer (UX-DR8,
 * UX-DR10).
 *
 * This is the module that fills `AppShell`'s badges slot. **`AppShell.tsx` is not edited**; the
 * slot is a prop and the filling happens at the call site in `App.tsx`.
 *
 * PRESENTATION-ONLY (the `shell.test.ts` posture every primitive in `src/components/` inherits):
 * no state, no hook, no fetch, no store, no event handler, no ref, no spread. It takes three
 * plain values and renders pills. A `DeckDetail` prop would have dragged the wire alias into the
 * component tree, which `posture.test.ts`'s cross-tree value-import ban exists to prevent — so
 * the caller does the reading and this file does the drawing.
 *
 * ================= WHAT THESE BADGES MAY NOT SAY =======================================
 *
 * The design mock shows THREE badges — `standard legal` (positive tone), `60 maindeck`,
 * `15 sideboard` — and the first one is **not this component's to render**. *"Standard legal"*
 * is a legality CLAIM, and legality comes from `GET /api/deck/{deck_id}/format-check`, a route
 * this component never calls, which carries its own ledgered warning about binding `is_legal`
 * to a headline. A `positive` tone here would be the app asserting something it never asked the
 * backend. So the format badge is the deck's own `format` STRING in the `neutral` tone — a fact
 * the payload carries — and the claim about it belongs to the format check.
 *
 * **A missing format renders NOTHING, not a `caution` badge.** Measured: all 40 saved decks
 * have a non-null format, so this branch is untested data either way — and between two untested
 * branches the honest one is the one that makes no claim. *"No format to check against"* is a
 * real state with a real token (`format_recognized`) and it belongs to the format check.
 *
 * ================= WHY THE COUNT IS ITS OWN SPAN (UX-DR3) ==============================
 *
 * `Badge.css:77` sets `font: var(--type-label)` — 11px, uppercase, tracked — so a size badge
 * written as one string renders `100 MAINDECK` in **proportional** figures, while UX-DR3 requires
 * tabular numerals on *"every count, quantity, price and axis value"* and DESIGN.md's own label
 * guidance says *"panel titles that need to carry counts should put the count in
 * `{typography.numeric}` beside the label, not inside it."* So the count is a `<span>` carrying
 * the numeric role, and `DeckBadges.css` applies `font` and `font-variant-numeric` **together**,
 * because the `font` shorthand cannot carry the feature and `token-usage.test.ts`'s
 * `findUnpairedNumericRole` fails the split pair.
 *
 * **`Badge.tsx` is NOT edited** — it takes `children`, so the span is the caller's, which is
 * exactly the seam that lets this happen without a second title role.
 *
 * The LABEL still renders uppercase, and that is accepted rather than overlooked: uppercase is
 * `Badge`'s declared type role and the mock's badges are uppercase too. The landmine is a
 * whole SENTENCE rendering all-caps; a one-word chip label is what a badge is.
 */

export interface DeckBadgesProps {
  /** `DeckDetail.format`, verbatim. `null` — or blank — renders no format badge at all. */
  format: string | null
  /** `DeckDetail.mainboard_count`. Includes the commander, which is how the backend counts it. */
  mainboardCount: number
  /** `DeckDetail.sideboard_count`. Zero renders no sideboard badge — 35 of 40 decks have none. */
  sideboardCount: number
}

export function DeckBadges({ format, mainboardCount, sideboardCount }: DeckBadgesProps) {
  // Blank counts as absent, the posture `filled()` takes for every slot in this codebase: a
  // whitespace format would otherwise render a bordered, washed, empty pill — visible chrome
  // announcing nothing, which is the exact failure `Badge`'s own `filled()` guard was added for.
  //
  // `typeof`, not `format !== null`, and it is not belt-and-braces: `format.trim()` after a
  // null check throws `Cannot read properties of undefined` the moment a caller passes a
  // partial deck. The wire cannot produce that today (`format` is REQUIRED in `DeckDetail`,
  // verified in `types.d.ts`), but a
  // presentation primitive that crashes the whole app on one absent prop is the FR-13 posture
  // inverted, and totality here costs one keyword.
  const named = typeof format === 'string' && format.trim() !== '' ? format : null

  return (
    <>
      {named === null ? null : <Badge>{named}</Badge>}
      <Badge>
        <span className="deck-badges-count">{mainboardCount}</span>
        maindeck
      </Badge>
      {sideboardCount > 0 ? (
        <Badge>
          <span className="deck-badges-count">{sideboardCount}</span>
          sideboard
        </Badge>
      ) : null}
    </>
  )
}
