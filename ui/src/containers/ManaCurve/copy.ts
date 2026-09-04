/**
 * Every word the mana curve panel authors.
 *
 * **NO IMPORTS, and that is load-bearing rather than incidental.** `tests/` belongs to the
 * `nodenext` TypeScript project and `src/` to the `bundler` one, so a `ui/tests` file may import
 * an app module only if that module is itself import-free — importing one with extensionless
 * relative imports produces twelve `TS2835` errors with `npm test` green throughout. This is the
 * tenth copy module and it stays import-free exactly as the nine before
 * it do.
 *
 * ================= WHAT IS COPY HERE, AND WHAT IS EMPHATICALLY NOT =====================
 *
 * The **counts** and the **mana values** are data: they are computed from the deck and no author
 * wrote them. The sentence they are interpolated into, the table's caption, its two column
 * headers and the `+` that makes the last bucket open-ended are all authored, and they live here.
 *
 * {@link barName} is the case `copy-rules.test.ts:62` names explicitly as residue 3 — *"a string
 * reaching an `aria-label` through an EXPRESSION"*. The guard cannot read a call's result, so
 * the words are declared here **first** rather than discovered by a reviewer: the builder's
 * literals are inside this module, where the content half of the copy gate scans every one of
 * them, and `ManaCurve.test.tsx` asserts the rendered names over the real DOM the way
 * `StatePanel.test.tsx` does.
 */

/**
 * The panel's title, and therefore its `<section>`'s accessible name.
 *
 * Sourced, not invented: `DESIGN.md:407` names this component **"Mana curve"** in the anatomy
 * list and `EXPERIENCE.md` uses the same two words. The word "panel" is dropped because the
 * element already IS one — a `<section>` named "Mana curve panel" announces its own kind twice,
 * once from the name and once from the region role. Same reasoning, same shape, as
 * `DECK_LIST_TITLE`.
 */
export const MANA_CURVE_TITLE = 'Mana curve'

/**
 * The `<figure>`'s accessible name.
 *
 * A `<figure>` maps to role `figure` reliably only when it HAS a name, so this is not
 * decoration — without it some engines expose the element as a generic container and the
 * accessible alternative loses the thing it is an alternative to.
 *
 * Deliberately NOT the same string as {@link MANA_CURVE_TITLE}: the panel and the figure are
 * two nested named things, and giving them one name makes a screen-reader user hear "Mana curve"
 * twice with nothing to distinguish the region from the graphic inside it.
 */
export const CHART_LABEL = 'Mana curve chart'

/**
 * The visually-hidden table's caption.
 *
 * The caption is what tells a screen-reader user what the table is FOR before they enter it —
 * a two-column table of bare numbers is otherwise arrived at with no context, which is the
 * failure the caption element exists to prevent.
 */
export const TABLE_CAPTION = 'Cards by mana value'

/** The table's two column headers. Authored words, not data. */
export const COLUMN_MANA_VALUE = 'Mana value'
export const COLUMN_CARDS = 'Cards'

/**
 * The suffix that makes the last bucket open-ended — the `+` of `7+`.
 *
 * Authored, and named rather than spelled at the call site so the axis label, the accessible
 * name and the table row cannot drift into saying three different things. UX-DR17 and
 * `DESIGN.md:407` both write the bucket range as *"1 … 7+"*.
 */
export const OPEN_ENDED_SUFFIX = '+'

/**
 * The visible axis label for one bucket — `'3'`, or `'7+'` for the open-ended one.
 *
 * Args:
 *   bucket: The bucket's mana value.
 *   openEnded: Whether this is the last bucket, which absorbs everything above it.
 *
 * Returns:
 *   The label, as rendered on the axis and in the table's first column.
 */
export const bucketLabel = (bucket: number, openEnded: boolean): string =>
  openEnded ? `${bucket}${OPEN_ENDED_SUFFIX}` : `${bucket}`

/**
 * One bar's accessible name — UX-DR17's own form.
 *
 * The artefact gives exactly one worked example, `"3 drops: 8 cards"`, and **no rule**. Applied
 * literally it produces `"1 drops: 1 cards"`, which is wrong in English twice in five words.
 *
 * **So the pluralisation below is INVENTED**, and stated here rather than left to be
 * discovered. The two nouns singularise
 * on DIFFERENT conditions, deliberately: `drops` on the BUCKET being 1 (bucket 1 names one mana
 * value, whatever it holds — `"1 drop: 2 cards"`), `cards` on the COUNT being 1. The open-ended
 * bucket keeps the plural — `"7+ drops: 2 cards"` — because `7+` names a RANGE of mana values
 * rather than one, so "7+ drop" would be wrong even when the range holds a single card.
 *
 * Args:
 *   bucket: The bucket's mana value.
 *   count: The summed quantity in it. `0` is real content and renders — 24 of the 40 real decks
 *     have at least one empty bucket, so `"5 drops: 0 cards"` is an ordinary announcement here
 *     rather than an edge case.
 *   openEnded: Whether this is the last bucket.
 *
 * Returns:
 *   The bar's accessible name.
 */
export const barName = (bucket: number, count: number, openEnded: boolean): string => {
  const drops = !openEnded && bucket === 1 ? 'drop' : 'drops'
  const cards = count === 1 ? 'card' : 'cards'
  return `${bucketLabel(bucket, openEnded)} ${drops}: ${count} ${cards}`
}
