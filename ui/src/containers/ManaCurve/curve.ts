import type { DeckBoards } from '../../state/deckGroups'
import { frontFace } from '../../state/deckGroups'

/**
 * The mana curve, derived from the deck already in the store (FR-05, UX-DR17).
 *
 * Its own module rather than a helper inside `ManaCurve.tsx`, for the settled reason:
 * `react-refresh/only-export-components` is an ESLint **error**, so a function exported beside a
 * component turns the gate red. `imageUrl.ts`, `deckMemory.ts`, `imagedFaces.ts`, `useCardArt.ts`
 * and `frontFaceCost.ts` are the five precedents; this is the sixth.
 *
 * ================= THIS PANEL FETCHES NOTHING, AND THAT IS WORTH SAYING ================
 *
 * `CardSummary.cmc` is a non-optional `number` on the wire and it is present on every row of
 * every deck payload at first paint. **There is no hydration dependency anywhere in this file,
 * and none is needed** — the panel is complete the instant the deck lands. The deck-wide sweep
 * exists for `card_faces` and `card_faces[0].mana_cost`; this needs neither, so **the sweep's
 * no-re-drive window is not triggered here**. Stated so the next reader does not add a
 * dependency this panel does not have.
 *
 * ================= "DFCS BUCKET BY THEIR FRONT FACE" IS ALREADY TRUE, FOR FREE ==========
 *
 * Measured against the shipped database: of the **2,830** faced cards carrying a blank top-level
 * `mana_cost` — the population that forces the mana-cost display onto the hydration sweep —
 * `cmc` **equals the front face's mana value in 2,830 of 2,830 cases (100%)**. The clause that
 * reads like the expensive one is satisfied by reading one field. This is the exact inverse of
 * the mana-cost display, where the front-face cost is blank for 87.8% of faced cards.
 *
 * ⚠️ **AND IT IS WRONG FOR TRUE SPLIT CARDS, BY ACCIDENT RATHER THAN BY DESIGN.** For the
 * **137** corpus cards whose cost is a genuine split (`'{3}{B} // {5}{B}{B}'`), Scryfall's `cmc`
 * is the **SUM of both halves**: `Cramped Vents // Access Maze` buckets at 11 where its front
 * face is 4. **Zero of those are in any of the 40 real decks** — all 27 live split-cost rows are
 * Adventure/Omen cards, where `cmc` is already the creature side. So the panel is correct on
 * every real deck today and one `add_card_to_deck` from wrong.
 *
 * Not fixed here. The fix is a numeric mana-value parser; `ui/` has none — `ManaCost` and
 * `describeManaCost` parse a cost into PIPS and nothing anywhere converts a cost string to a
 * number — and writing the second cost parser in `ui/` inside a seven-bar panel is the wrong
 * home. `curve.test.ts` pins the known-wrong bucket, so the next author finds a red test rather
 * than a screenshot. **The real home is whoever needs a numeric mana value.**
 *
 * ================= THE BOARD POLICY, WHICH IS INVISIBLE FROM THE CODE ==================
 *
 * **Commander + mainboard; the sideboard is excluded.** The sideboard half is stated in
 * `deckGroups.ts:199` — *"the sideboard is not part of the deck the curve and colour panels
 * describe"*. The commander half matters:
 * **16 of 40 real decks carry one**, and including it moves the corpus non-land quantity from
 * **1,812 to 1,828**. `src/mcp_server/tools/deck_analysis.py:171-173` already includes the
 * commander and excludes the sideboard, so matching it costs nothing and means the panel and the
 * MCP tool cannot answer the same question differently — *"the grid and the list panel cannot
 * disagree"*, one layer out.
 *
 * This file reads `DeckBoards`, which is where that partition already lives, so the policy is
 * expressed by WHICH BOARDS IT READS rather than by a second `filter` over `sideboard`. AD-12.
 */

/**
 * The buckets, in ascending order — UX-DR17 and `DESIGN.md:407`, verbatim: *"Buckets are 1 … 7+"*.
 *
 * A `readonly` tuple rather than a number: the seven-entry shape is closed, and
 * {@link CurveBuckets} is coupled to it in the type, so a change that wanted an eighth bucket
 * would have to say so in the open.
 */
export const BUCKETS = [1, 2, 3, 4, 5, 6, 7] as const

export type Bucket = (typeof BUCKETS)[number]

/** The open-ended bucket. `7+` absorbs everything at or above it — see {@link bucketOf}. */
export const LAST_BUCKET: Bucket = 7

/**
 * Whether a type line names a LAND — the curve's own test, and deliberately not `groupOf`'s.
 *
 * ================= THERE ARE THREE LAND POLICIES IN THIS REPO. THIS IS THE THIRD ========
 *
 * | policy | test | where |
 * |---|---|---|
 * | **A — whole string** | `'land' in type_line.lower()` | `src/logic/mana_curve.py:74`, `:277`, `src/logic/assessment/mana_base.py:80` |
 * | **B — group** | `groupOf(type_line) === 'Land'` | `deckGroups.ts:176-181`, first-match-wins |
 * | **C — this one** | the word `Land` in the front face's type half | here |
 *
 * **B is NOT this question, and reusing it is the tidy-looking mistake.** `groupOf` answers
 * *"which section is this row filed under"*, by first-match-wins over `TYPE_GROUPS` — so
 * `Artifact Land` groups as **Artifact**, which is right in a deck list and would count **32
 * corpus lands as SPELLS** here. **Zero of the 32 are in any real deck**, which is precisely why
 * `curve.test.ts` pins the divergence by name: no fixture would stumble into it and no
 * eye-check can see a card that is not on screen.
 *
 * **A disagrees with this test on 84 corpus cards and 7 live rows across 5 decks** — the four
 * MDFC lands (`Agadeem's Awakening`, `Kazandu Mammoth`, `Dowsing Dagger`, `Journey to Eternity`).
 * FR-05 and UX-DR17 say FRONT FACE, so this file is right and the Python is wrong; the fix has
 * MCP blast radius (`analyze_mana_curve`, and `mana_base.py` feeds `assess_deck_power`'s frozen
 * benchmark set) and is not made here. The observable consequence, stated rather than
 * discovered: **`analyze_mana_curve` and this panel
 * report different non-land counts for the same deck.**
 *
 * ================= WHOLE WORD, NOT SUBSTRING ===========================================
 *
 * A substring test, `frontFace(typeLine).includes('Land')`, is wrong for two corpus cards:
 * `Lander Rizzi` (`Legendary Artifact Creature — Lander Rogue`) and the `Lander` token
 * (`Token Artifact — Lander`) are not lands and a substring test drops both out of the curve.
 * `deckGroups.ts:166-168` says why in writing — *"a substring test would additionally group
 * anything containing `Landfall`-shaped text wrongly"*. The word test costs nothing today (0 live
 * rows either way) and removes a way to be wrong later.
 *
 * Two reductions, the same two `groupOf` performs and for the same reasons:
 *
 *   1. **The front face only**, via `deckGroups.ts`'s exported {@link frontFace} — reused
 *      verbatim, loose separator and all. The loose pattern INVERTS for a *name*
 *      (`'SP//dr, Piloted by Peni'` truncates to `'SP'`), which is why the name path uses a
 *      literal split; a **type line** is the case the loose pattern was written for.
 *   2. **The supertype/type half only** — everything before the em-dash (U+2014). Without it a
 *      SUBTYPE containing the word would decide the answer.
 *
 * Args:
 *   typeLine: The card's `type_line`, verbatim.
 *
 * Returns:
 *   `true` if the card's front face is a land.
 */
export const isLand = (typeLine: string): boolean =>
  frontFace(typeLine).split('—')[0].split(/\s+/).includes('Land')

/**
 * Which bucket a mana value falls in.
 *
 * ================= BOTH ENDS ARE DECISIONS =============================================
 *
 * **The top.** `7+` absorbs every value at or above 7. Load-bearing on real data: 43 live rows /
 * 49 quantity sit at `cmc >= 7`, up to `Ghalta, Primal Hunger` at 12, and the corpus maximum is
 * `Gleemax` at 1,000,000.
 *
 * **The bottom, which is the one that changes what a user sees.** Buckets start at 1, so a
 * zero-mana non-land has no bucket of its own — **1 live row** (`Pym Particles`, whose
 * `type_line` is the bare string `'Card'`) and **4,351 corpus cards**. Unlike `deckGroups.ts`
 * there is **no conservation identity here** and no number on screen that stops summing, so a
 * dropped card would be invisible.
 *
 * **`cmc <= 1` folds into bucket 1, deliberately.** The reasons are asymmetric and worth stating. A
 * free spell is castable on turn one — a 0-drop is *more* castable than a 1-drop, not less — so
 * folding downward misstates nothing the curve is for ("what can I cast, and when"). Silently
 * dropping it is the alternative and it is strictly worse. **No `0` bucket is added**: 1…7+ is
 * UX-DR17's own number and one live row is not a measurement that justifies amending an artefact.
 *
 * The rounding falls out of the same fold and is therefore **moot rather than lucky**:
 * `Little Girl` (`{HW}`, `cmc 0.5`) is the only non-integer `cmc` in 38,261 cards, and
 * `Math.floor(0.5)` and `Math.round(0.5)` both land in bucket 1 once `<= 1` folds. `Math.round`
 * is what ships, because "which turn can I cast this" rounds rather than truncates.
 *
 * Args:
 *   cmc: A `CardSummary.cmc`. Non-optional on the wire and a SQLite `FLOAT`, so it is a JS
 *     `number` that may legitimately be fractional.
 *
 * Returns:
 *   One of {@link BUCKETS}.
 */
export const bucketOf = (cmc: number): Bucket => {
  const rounded = Math.round(cmc)
  if (rounded <= 1) return 1
  return (rounded >= LAST_BUCKET ? LAST_BUCKET : rounded) as Bucket
}

/** One bar's worth of the answer. */
export interface CurveBucket {
  /** The mana value this bar stands for. The last one means "this or more". */
  readonly bucket: Bucket
  /** The SUMMED QUANTITY in this bucket, never a row count. */
  readonly count: number
  /**
   * {@link count} as a fraction of the TALLEST bucket, in `0…1` — the number the bar's height
   * is drawn from. Scaled to the tallest bar rather than to the deck size, which is the one
   * thing the composition reference supplies that no artefact does; `0` when the curve is empty,
   * never `NaN`.
   */
  readonly share: number
}

/** The whole curve: seven bars, their total, and the scale they were drawn against. */
export interface CurveBuckets {
  readonly buckets: readonly [
    CurveBucket,
    CurveBucket,
    CurveBucket,
    CurveBucket,
    CurveBucket,
    CurveBucket,
    CurveBucket,
  ]
  /** Every bucket summed — the number the panel's hide condition tests. */
  readonly total: number
  /** The tallest bucket's count, floored at 1 so nothing divides by zero. */
  readonly tallest: number
}

/**
 * The curve for a deck.
 *
 * ================= DERIVED IN RENDER, NOT CACHED AND NOT MEMOISED ======================
 *
 * UX-DR17 says the curve is *"recomputed from the decklist"* rather than cached, and this is a
 * single pass over at most 99 rows. Three reasons there is no `useMemo` and no store write:
 *
 *   1. **A memo is a cache**, which is the thing UX-DR17 rules out.
 *   2. **The memo's dependency would be `boards`, whose REFERENCE IDENTITY is the deck's
 *      identity.** `deckMemory.ts:8-9` and `CardDetail.tsx:333-336` both detect a deck
 *      replacement by comparing that reference. Touching it at all is a hazard for no measured
 *      gain.
 *   3. Computing it beside `boardsOf` at store-write time would be both the cache UX-DR17 forbids
 *      and a display concern in the store.
 *
 * This is a different AXIS over the same partition (mana value, rather than board and type), not
 * a second partition, so AD-12's ban on re-deriving what `boardsOf` computed is not engaged:
 * nothing here filters, sorts or regroups cards.
 *
 * Args:
 *   boards: `surfaceOf`'s answer for a loaded deck, verbatim — the same value `CardGrid` and
 *     `DeckList` receive. Read, never copied.
 *
 * Returns:
 *   Seven buckets in ascending order, with the total and the scale.
 */
export const curveOf = (boards: DeckBoards): CurveBuckets => {
  const counts = new Map<Bucket, number>(BUCKETS.map((bucket) => [bucket, 0]))

  // The commander board and the mainboard's groups; the sideboard is simply not read.
  // `boards.mainboard` is already `TYPE_GROUPS`-ordered and this ignores that order entirely —
  // the curve's axis is mana value, and a group is only a container to walk through.
  const rows = [...boards.commander, ...boards.mainboard.flatMap((group) => [...group.cards])]

  for (const entry of rows) {
    if (isLand(entry.card.type_line)) continue
    const bucket = bucketOf(entry.card.cmc)
    // `+ entry.quantity`, never `+ 1`. A ×4 row is four cards, the same rule
    // `deckGroups.ts:166-167` fixed for group headers.
    counts.set(bucket, (counts.get(bucket) ?? 0) + entry.quantity)
  }

  const raw = BUCKETS.map((bucket) => ({ bucket, count: counts.get(bucket) ?? 0 }))
  const total = raw.reduce((sum, entry) => sum + entry.count, 0)
  // `Math.max(1, …)` is the divide-by-zero guard, and it is exercised by real data rather than
  // by a fixture: `Iron Man, Modern Marvel — reminder` is one card and six empty buckets, and a
  // land-only deck is an all-zero curve with cards in it.
  const tallest = Math.max(1, ...raw.map((entry) => entry.count))

  const buckets = raw.map((entry) => ({
    ...entry,
    // Guarded on `total` rather than on `tallest`: with `tallest` floored at 1 an empty curve
    // would otherwise produce seven honest-looking `0`s from a scale that describes nothing.
    share: total === 0 ? 0 : entry.count / tallest,
  })) as unknown as CurveBuckets['buckets']

  return { buckets, total, tallest }
}
