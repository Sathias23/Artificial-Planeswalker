/**
 * The five Badge tones, as data.
 *
 * WHY THIS IS ITS OWN MODULE, and not a `const` beside the component. `react-refresh/
 * only-export-components` is an `error` in this project, and its `allowConstantExport` option
 * is narrower than it sounds: MEASURED here, `export const BADGE_TONES = [...] as const`
 * beside the component is a lint error — the rule treats an array initialiser as a
 * non-constant export. So this follows the route `filled.ts` already established: a helper or
 * a datum that has to be exported alongside a component moves to its own module rather than
 * having a gate relaxed to fit it.
 *
 * WHY IT IS EXPORTED AT ALL. It is the NON-VACUITY ANCHOR for Badge's per-tone tests. Those
 * tests loop over this list, and a list that had quietly lost a member would make every
 * assertion in the loop pass by iterating over four things — or, if it were emptied, by
 * iterating over none. The list is asserted against DESIGN.md's five names first, and only
 * then used to drive the loop.
 */

export const BADGE_TONES = ['neutral', 'accent', 'positive', 'negative', 'caution'] as const

export type BadgeTone = (typeof BADGE_TONES)[number]
