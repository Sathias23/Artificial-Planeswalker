import type { CSSProperties } from 'react'

import { ManaPip } from '../../components/ManaPip/ManaPip'
import { Panel } from '../../components/Panel/Panel'
import type { ManaColour } from '../../components/ManaCost/parse'
import { useCardStore } from '../../state/cards'
import type { DeckBoards } from '../../state/deckGroups'
import './ColourDistribution.css'
import {
  CHART_LABEL,
  COLOUR_DISTRIBUTION_TITLE,
  COLOUR_LABELS,
  percentLabel,
  pipCount,
} from './copy'
import { coloursOf } from './colours'

/**
 * The colour distribution — one proportional bar and its legend, beside the mana curve
 * (FR-05, UX-DR7, UX-DR8, UX-DR13, UX-DR18, UX-DR40, UX-DR44, UX-DR45, UX-DR47).
 *
 * ================= THE SECOND CHILD OF THE ANALYSIS ROW ================================
 *
 * `AnalysisRow` puts `flex: 1 1 0; min-width: 0` on its children so that one fills the width and
 * two are exactly 1:1. This panel lands by adding a sibling inside it and editing neither that
 * component nor `AppShell.tsx`.
 *
 * ================= AND IT WALKS BACK INTO THE HYDRATION WINDOW ==========================
 *
 * The mana curve needs nothing from the deck-wide sweep, because `cmc` rides on `CardSummary`.
 * **A pip count does not**: 87.75% of faced cards carry a blank top-level `mana_cost`, and
 * hydration is worth **+48 pips across 16 of 40 real decks**. So this is a panel whose
 * **percentages move after first paint**, which is exactly why *"no `aria-live`"* below is
 * load-bearing rather than a formality.
 *
 * **THE CACHE IS READ THROUGH ONE SUBSCRIPTION TO THE WHOLE MAP, AND THE ALTERNATIVES ARE BOTH
 * WRONG.** `DeckList` reads the cache with `useCardEntry(cardId)` inside `DeckRow` — one
 * component per row, one unconditional hook each. This panel is **one** component aggregating up
 * to 99 rows, and a hook in a loop over a list whose length changes with the deck is the
 * rules-of-hooks violation React actually breaks on. `readCardEntry` is imperative and **not
 * reactive**, so the bar would settle on its pre-hydration numbers and never correct itself —
 * silently plausible and wrong, the worst of the three.
 *
 * `useCardStore((state) => state.cards)` returns the **stored map reference**, so zustand v5's
 * dropped equality argument is not a hazard here: a selector building an array or an object
 * (`Object.values(s.cards)`) returns a new value every call and re-renders forever. The cost is
 * real and stated: this panel re-renders on **every one of ~99 hydrations** during a cold-open
 * sweep, each running `coloursOf` over ~99 rows at ~48 µs — **~4.8 ms of derivation across the
 * whole sweep**, which is why there is no `useMemo` (see `colours.ts`).
 *
 * **It starts nothing.** `hydrateCard` is not called here; `App.tsx` owns
 * the sweep, and this panel reads what it has already put in the cache.
 *
 * ================= THE ACCESSIBLE SHAPE IS THE EXACT INVERSE OF THE CURVE'S ============
 *
 * `ManaCurve` gives **every bar** a `role="img"` and an accessible name and hides the painted
 * text. UX-DR18 inverts it in writing — *"the bar is `aria-hidden`; the legend is the accessible
 * data path"* — and copying the sibling would have been wrong. So:
 *
 *   - **The bar and every segment are `aria-hidden`, with no `role` and no name.** They carry no
 *     information a screen-reader user could not get better from the legend, and the reason is
 *     measurable: **15 of the 15 adjacent `--mana-*` pairs are under the 3:1 non-text floor**, 8
 *     of them under 1.3:1, the worst (`--mana-b` against `--mana-colorless`) at **1.03:1**. A
 *     named segment would be announcing a distinction the picture cannot make.
 *   - **The legend is VISIBLE text**, so there is **no visually-hidden block in this panel at
 *     all** — stated rather than left as an absence.
 *   - **The legend's `ManaPip` is DECORATIVE** (no `label`). The entry already reads its colour,
 *     its count and its percentage as text, and a labelled pip beside its own text count is the
 *     doubled announcement `ManaPip.tsx` warns about.
 *   - **The `<figure>` carries a name distinct from the panel title**, for the same reason
 *     `ManaCurve`'s does: two nested named things sharing one name makes a screen reader say it
 *     twice with nothing to distinguish them.
 *   - **No `aria-live`.** A percentage that re-announced through ~99 hydrations is the exact
 *     flood UX-DR45 bans, and louder than a pip appearing in a deck row.
 *
 * ================= DISPLAY-ONLY, LITERALLY ============================================
 *
 * No handler, no `tabindex`, no `role="button"`, no inspection verb. **This panel adds ZERO Tab
 * stops** and touches the inspection slice not at all — a colour segment is not an inspection
 * target.
 *
 * ================= THE EMPTY CASE, AND THE ROW ========================================
 *
 * The panel renders nothing when the pip TOTAL is zero — the condition is on the data, not on the
 * deck's card count, the same condition the curve uses. Measured: **no deck in the corpus
 * reaches this state** (all 40 have at least 2 pips), so it is not producible from live data and
 * `colours.test.ts` asserts it against the derivation rather than against a hand-built deck.
 *
 * An `.analysis-row` whose only child renders null would otherwise sit **empty** in the DOM with
 * a phantom 24px column gap. `AnalysisRow.css` hides it with `:empty`, which needs no gate in
 * `App.tsx`, no curve total and **no second derivation of anything**.
 */

/** What the bar draws. One prop, and it is the derivation — never the raw payload. */
export interface ColourDistributionProps {
  /** `surfaceOf`'s answer for a loaded deck, verbatim. The SAME value `CardGrid` receives. */
  boards: DeckBoards
}

/**
 * {@link COLOUR_LABELS} is coupled to `ManaColour` **in both directions**, and the assertion
 * lives here rather than in `copy.ts`.
 *
 * `copy.ts` must stay import-free so that `ui/tests/` can import it across the tsconfig project
 * boundary — `tests/` is `nodenext`, `src/` is `bundler`, and `TS2835` is a RESOLUTION error that
 * fires against the specifier whether or not `import type` erases it at emit. So the map is
 * declared there and held to the union here, which is `CardPlaceholder.tsx`'s and `DeckList.tsx`'s
 * shape exactly.
 *
 * Both directions are needed and each catches a different mistake:
 *
 *   {@link EveryColourHasALabel} — a SEVENTH colour added to `ManaColour` has no label, and the
 *   legend would render `undefined` beside a real pip count. Not hypothetical in kind: `{C}` is
 *   in the union today with **zero occurrences in every real deck**, so a missing label would
 *   ship green and appear the day somebody adds an Eldrazi.
 *
 *   {@link EveryLabelIsAColour} — a label written for a letter the parser does not have is dead
 *   copy no render can reach. It also closes the WIDENING hole: annotate the map
 *   `Record<string, string>` and `keyof` becomes `string`, which this assertion rejects while the
 *   first would still pass.
 */
type Assert<T extends true> = T

export type EveryColourHasALabel = Assert<
  [Exclude<ManaColour, keyof typeof COLOUR_LABELS>] extends [never] ? true : false
>

export type EveryLabelIsAColour = Assert<
  [Exclude<keyof typeof COLOUR_LABELS, ManaColour>] extends [never] ? true : false
>

export function ColourDistribution({ boards }: ColourDistributionProps) {
  // ONE subscription, to the stored map reference — see the header for why neither `useCardEntry`
  // in a loop nor `readCardEntry` is available here.
  const cards = useCardStore((state) => state.cards)
  const distribution = coloursOf(boards, cards)

  // The only branch in this component. `total` rather than a count of rows: a
  // deck of only lands, or only generic costs, has cards and nothing for a colour bar to say.
  if (distribution.total === 0) return null

  return (
    /* A TITLED PANEL AT level="default", for the reason `ManaCurve`'s is titled: this is
       the second of two panels in a fluid row, and `<section aria-label>` is what puts "Color
       distribution" in a screen-reader user's landmark list.

       No `count` prop. The pip TOTAL is a number this panel could show, and deliberately does
       not: `DESIGN.md:408`'s anatomy asks for a bar and a legend of pip + count + percentage,
       and the per-colour counts in that legend are the numbers this panel adds. A total in the
       chrome would also invite the arithmetic `colours.ts` warns about — hybrids make the counts
       sum to more than the symbols on the cards. */
    <Panel title={COLOUR_DISTRIBUTION_TITLE}>
      {/* The figure is NAMED: a `<figure>` maps to role `figure` reliably only when it has an
          accessible name, and without one some engines expose it as a generic container —
          which would leave the legend with nothing to be the alternative TO. Verified against
          Chrome's own accessibility tree, not jsdom's. */}
      <figure className="colour-distribution" aria-label={CHART_LABEL}>
        {/* THE BAR (UX-DR18). `aria-hidden` on the WRAPPER, so the segments inside are removed
            from the tree with it — the inverse of `ManaCurve`, whose every bar carries a name.
            No `role`, no `aria-label`, nothing focusable. */}
        <div className="colour-bar" aria-hidden="true">
          {distribution.segments.map(({ colour, count }) => (
            /* THE WIDTH IS THE DATA, THROUGH A NAMED RUNTIME CHANNEL. `--colour-bar-share` is
               allow-listed in BOTH `eslint.config.js`'s exact-name set and
               `RUNTIME_CUSTOM_PROPERTIES` in tests/token-usage.test.ts: a channel is added in
               both places, in the open, or one of the two gates goes red.

               IT CARRIES A RAW COUNT, NOT A PERCENTAGE, AND THAT IS THE WHOLE OF "no division
               by zero is possible". `flex-grow` divides — the browser distributes the track's
               free space in proportion to the grow factors — so there is no division at this
               call site to guard, no rounding in the geometry, and the segments always fill the
               bar exactly however the printed percentages round.

               ⚠️ THE OBJECT LITERAL IS INLINE AT THE JSX CALL SITE, and that is a trap rather
               than a style: a helper returning the object is precisely the evasion the first of
               the three narrowed ESLint selectors closes. THE CAST IS REQUIRED — React's
               `CSSProperties` has no index signature for `--`-prefixed keys, so the bare
               literal is `TS2353`. */
            <div
              key={colour}
              className={`colour-bar-segment colour-bar-segment-${colour}`}
              style={{ '--colour-bar-share': `${count}` } as CSSProperties}
            />
          ))}
        </div>

        {/* THE LEGEND — UX-DR18's *"the legend is the accessible data path"*, and therefore the
            only part of this panel a screen reader reads.

            A real `<ul>`: five entries in a mono-to-five-colour range is a list, and "list, 5
            items" is orientation a row of loose spans does not give. Every entry carries its
            colour AS TEXT, so colour is never the sole carrier — which is the half the hairline
            below the bar does NOT close: the hairline makes adjacent segments distinguishable,
            and only the text makes a colour identifiable. */}
        <ul className="colour-legend">
          {distribution.segments.map(({ colour, count, percent }) => (
            <li className="colour-legend-entry" key={colour}>
              {/* DECORATIVE, deliberately: no `label`. The three text nodes beside it
                  already say the colour, the count and the percentage, and a labelled pip here
                  would announce the colour twice. */}
              <ManaPip colours={[colour]} />
              <span className="colour-legend-name">{COLOUR_LABELS[colour]}</span>
              <span className="colour-legend-count">{pipCount(count)}</span>
              <span className="colour-legend-percent">{percentLabel(percent)}</span>
            </li>
          ))}
        </ul>
      </figure>
    </Panel>
  )
}
