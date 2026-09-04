import type { CSSProperties } from 'react'

import { Panel } from '../../components/Panel/Panel'
import type { DeckBoards } from '../../state/deckGroups'
import './ManaCurve.css'
import {
  CHART_LABEL,
  COLUMN_CARDS,
  COLUMN_MANA_VALUE,
  MANA_CURVE_TITLE,
  TABLE_CAPTION,
  barName,
  bucketLabel,
} from './copy'
import { LAST_BUCKET, curveOf } from './curve'

/**
 * The mana curve — seven bars and a count, beneath the card grid (FR-05, UX-DR3, UX-DR7,
 * UX-DR17, UX-DR40, UX-DR42, UX-DR44, UX-DR47).
 *
 * ================= COMPLETE AT FIRST PAINT =============================================
 *
 * `CardSummary.cmc` rides on the deck payload, so **this file fetches nothing, subscribes to
 * nothing and waits for nothing**. It is the third reader of `surface.boards`, after `CardGrid`
 * and `DeckList`, and it adds no fourth derivation of the deck — `curve.ts` walks the boards
 * along a different axis (mana value) rather than re-partitioning them (AD-12).
 *
 * **The hydration sweep and its no-re-drive window are NOT TRIGGERED HERE.** The sweep exists
 * for `card_faces` and `card_faces[0].mana_cost`; this panel needs neither.
 *
 * ================= WHAT IS DERIVED, AND WHERE ==========================================
 *
 * `curveOf` is called **in render, with no `useMemo`**. UX-DR17 says the curve is *"recomputed
 * from the decklist"* rather than cached, a memo is a cache, and the memo's dependency would be
 * `boards` — whose REFERENCE IDENTITY is the deck's identity for `deckMemory.ts` and
 * `CardDetail.tsx`. Measured over a 99-row board (the largest real deck's shape), V8 warm:
 * **~24 µs per call** (mean of 20,000 calls; a single warm call reads ~21 µs) — a single pass
 * with one `Map` of seven entries. A memo would have to beat 24 µs to earn its hazard.
 *
 * ================= THE ACCESSIBLE PATH, AND WHY IT IS NOT THE PAINTED ONE ==============
 *
 * UX-DR17 asks for **both** a per-bar accessible name and a whole-curve visually-hidden table,
 * the two can be read to contradict each other. Resolved here, explicitly:
 *
 *   - **Each `.mana-curve-bar` carries `role="img"` and an `aria-label`** — UX-DR17's own
 *     `"3 drops: 8 cards"` form, built in `copy.ts`. Every bar, not the first.
 *   - **The painted COUNT and AXIS text are `aria-hidden`**. They are the duplicates:
 *     every number they show is already inside the bar's name and inside the table. Without
 *     this a screen-reader user meets each number three times.
 *   - **The `<table>` is the whole-curve alternative**, kept in the accessibility tree
 *     by the clip-rect idiom rather than removed from it by `display: none`.
 *
 * **This panel is not a live region and adds no `aria-live` anywhere.** The only
 * announcer in the app remains `CardDetail`'s single polite region; a curve that spoke on every
 * deck change would be a second one.
 *
 * ================= DISPLAY-ONLY, LITERALLY =============================================
 *
 * The bars are `<div>`s with **no handler, no `tabindex` and no `role="button"`**, so UX-DR47's
 * *"never a `<div>` with a click handler"* is satisfied by there being no handler at all. **This
 * panel adds ZERO Tab stops**, which matters beyond itself: the page's Tab order runs from the
 * grid to the right column, and seven stops in between would be a real cost. The inspection slice
 * is not touched — a curve bar is not an inspection target.
 *
 * ================= THE EMPTY CURVE, AND THE CONDITION THAT HIDES IT ====================
 *
 * **The condition is ZERO CARDS IN THE CURVE, not zero cards in the deck**, and the difference
 * is real: a deck of only lands has cards and nothing for a curve to describe. Seven empty wells
 * under seven zeroes is a worse answer than absence, so the panel renders nothing. Measured:
 * **no deck in the corpus reaches this state** — all 40 have rows and the smallest
 * curve is one card (`Iron Man, Modern Marvel — reminder`) — so it is not producible from live
 * data and `ManaCurve.test.tsx` is its only witness.
 */

/** What the curve draws. One prop, and it is the derivation — never the raw payload. */
export interface ManaCurveProps {
  /** `surfaceOf`'s answer for a loaded deck, verbatim. The SAME value `CardGrid` receives. */
  boards: DeckBoards
}

/**
 * A bucket's share of the tallest bar, as a CSS percentage — the number that becomes a height.
 *
 * `toFixed(2)` because the raw quotient is a float: `13 / 39` is `0.3333333333333333`, and
 * writing sixteen significant figures into a style attribute is noise in every DOM inspection
 * and in every diff of this component's tests. Two decimals is finer than any screen can resolve
 * at these sizes; the eye-check measures the rendered pixels.
 *
 * `Number.parseFloat` strips the trailing zeroes `toFixed` adds, so a whole number renders
 * `100%` rather than `100.00%` and a zero bucket renders `0%`.
 *
 * ⚠️ **IT RETURNS A STRING, NOT A `CSSProperties`.** Returning the whole style object from here
 * and writing `style={barHeight(share)}` is what the narrowed `no-restricted-syntax` rejects:
 * *"a style attribute that is not a literal object hides its keys from every static reader, so
 * it cannot be shown to be custom-property-only"*. Moving the literal out of the JSX is exactly
 * the evasion the first of the three selectors exists to close. The object literal therefore
 * stays **inline at the call site**, where the gate can read its keys.
 */
const heightPercent = (share: number): string => `${Number.parseFloat((share * 100).toFixed(2))}%`

export function ManaCurve({ boards }: ManaCurveProps) {
  const curve = curveOf(boards)

  // The only branch in this component. `curve.total` rather than a count of
  // rows: see the module header for why a land-only deck takes this path too.
  if (curve.total === 0) return null

  return (
    /* A TITLED PANEL AT level="default". Titled, where `CardGrid`'s panel is deliberately
       not: this is the second of an eventual three panels in a fluid column, and
       `<section aria-label>` is what puts "Mana curve" in a screen-reader user's landmark list.

       No `count` prop. The deck's totals are on screen twice already (the `h1` and `DeckBadges`),
       and a curve's own total is not a number DESIGN.md's anatomy asks for — the per-bucket
       counts above the bars are the numbers this panel adds. */
    <Panel title={MANA_CURVE_TITLE}>
      {/* THE `<figure>`, NAMED, not bare: a `<figure>` maps to role `figure` reliably only when
          it has an accessible name, and without one some engines expose it as a generic
          container — which would leave the accessible alternative with nothing to be an
          alternative to. Verified against Chrome's own accessibility tree, not jsdom's. */}
      <figure className="mana-curve" aria-label={CHART_LABEL}>
        <div className="mana-curve-chart">
          {curve.buckets.map(({ bucket, count, share }) => {
            const openEnded = bucket === LAST_BUCKET
            return (
              <div className="mana-curve-column" key={bucket}>
                {/* THE COUNT (UX-DR3, DESIGN.md:407): `--type-numeric` with its
                    companion, at `--text-tertiary`. `aria-hidden` because the bar's own name
                    and the table both already carry this number.

                    Rendered unconditionally, including `0`. `{count && …}` renders the bare
                    string `0` and `count ? … : null` drops a real zero — and 24 of the 40 real
                    decks have at least one empty bucket, so this component renders more zeroes
                    than any before it. */}
                <span className="mana-curve-count" aria-hidden="true">
                  {count}
                </span>
                {/* THE WELL — `components.curve-bar.track`. It is what makes an empty
                    bucket legible without a 2px floor: the track says "this bucket exists and is
                    empty", where a floored stub would say "this bucket has a small number in
                    it". The mock's answer is the one being declined. */}
                <div className="mana-curve-track">
                  {/* THE BAR. `role="img"` + a name from copy.ts is UX-DR17's per-bar
                      accessible name; the height is the data, and the fill is the CHROME
                      token, never a `--mana-*` one (UX-DR7). */}
                  {/* THE ESCAPE HATCH, TAKEN AT ITS ONE CALL SITE. `eslint.config.js`'s
                      `no-restricted-syntax` reserves the `style` attribute for a computed bar
                      height: the rule still errors on any `style` attribute carrying a property
                      that is not a `--`-prefixed custom property, so
                      `style={{ padding: '18px' }}` is illegal.

                      ⚠️ THE CAST IS REQUIRED. A dynamic value does NOT set a CSS custom
                      property through the style attribute's own typing (measured with
                      `npx tsc -b --force` at React 19.2): `CSSProperties` extends csstype's
                      `Properties`, which has NO index signature for `--`-prefixed keys, so the
                      bare literal is `TS2353`. The hatch is real; the typing does not carry
                      it. */}
                  <div
                    className="mana-curve-bar"
                    role="img"
                    aria-label={barName(bucket, count, openEnded)}
                    style={{ '--curve-bar-height': heightPercent(share) } as CSSProperties}
                  />
                </div>
                {/* THE AXIS LABEL: `--type-micro`. `aria-hidden` for the same reason as
                    the count — it is inside the bar's name and the table's first column. */}
                <span className="mana-curve-axis" aria-hidden="true">
                  {bucketLabel(bucket, openEnded)}
                </span>
              </div>
            )
          })}
        </div>

        {/* THE ACCESSIBLE ALTERNATIVE (UX-DR17, UX-DR44).

            A REAL table with real `<th scope>`, not a grid of divs with roles: the row/column
            relationship is what lets a screen-reader user move down the curve and hear "5, 0"
            rather than seven unanchored numbers. Visually hidden by the clip-rect idiom in
            `ManaCurve.css` — NOT `display: none` and NOT `visibility: hidden`, both of which
            remove it from the accessibility tree entirely. */}
        {/* `visually-hidden` carries the clip-rect, shared from `src/styles/`. `mana-curve-table`
            survives as this table's hook and declares no geometry of its own. */}
        <table className="visually-hidden mana-curve-table">
          <caption>{TABLE_CAPTION}</caption>
          <thead>
            <tr>
              <th scope="col">{COLUMN_MANA_VALUE}</th>
              <th scope="col">{COLUMN_CARDS}</th>
            </tr>
          </thead>
          <tbody>
            {curve.buckets.map(({ bucket, count }) => (
              <tr key={bucket}>
                <th scope="row">{bucketLabel(bucket, bucket === LAST_BUCKET)}</th>
                <td>{count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </figure>
    </Panel>
  )
}
