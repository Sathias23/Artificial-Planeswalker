/**
 * The surface ramp as ordered data, plus the predicate that makes UX-DR1's adjacency rule
 * checkable.
 *
 * UX-DR1: a component nested inside another steps EXACTLY one level along
 * `well -> base -> panel -> overlay`, never skipping two. Two skipped levels read as a
 * different material rather than a nearer pane, which is the whole illusion Voltglass is
 * built on.
 *
 * BE HONEST ABOUT WHAT THIS IS. Cross-file CSS nesting depth is not statically decidable —
 * a component's parent is chosen by whoever renders it, in TSX, at runtime — so this is a
 * MECHANISM PLUS ITS PROOF, not a lint gate. `stepsExactlyOne` is unit-tested in both
 * directions here; whether a given component passes its real parent to it is caught by
 * review; the adjacency half is not automated. (Its sibling constraint, `accent-dim` never on `surface-overlay`, IS a real
 * guard — see tests/token-usage.test.ts.)
 *
 * THE RAMP IS CLOSED AT FOUR. Do not add a fifth surface above `surface-overlay`:
 * `--text-tertiary` on `--surface-overlay` is already 4.8:1, with zero headroom under the
 * 4.5:1 floor (UX-DR41). A lighter surface has nowhere left to put tertiary text.
 *
 * The names below are the CSS custom-property names minus the `--` prefix, and
 * tests/token-usage.test.ts asserts they exist in src/styles/tokens.css IN THIS ORDER — so
 * renaming a token without updating this list fails the suite instead of leaving the
 * predicate quietly reasoning about a ramp that no longer exists.
 */

/** The four surfaces, darkest (furthest) to lightest (nearest). Order is the contract. */
export const SURFACE_RAMP = [
  'surface-well',
  'surface-base',
  'surface-panel',
  'surface-overlay',
] as const

export type SurfaceName = (typeof SURFACE_RAMP)[number]

/**
 * True when `to` sits exactly one level nearer than `from`.
 *
 * Directional on purpose: nesting moves UP the ramp. `stepsExactlyOne('panel', 'base')` is
 * false, because a nested pane that gets darker than its parent reads as a hole rather than
 * a pane.
 */
export function stepsExactlyOne(from: SurfaceName, to: SurfaceName): boolean {
  const fromIndex = SURFACE_RAMP.indexOf(from)
  const toIndex = SURFACE_RAMP.indexOf(to)
  // The -1 guard is not defensive noise. Without it `indexOf` returns -1 for an unknown name
  // and the arithmetic says YES to nonsense: stepsExactlyOne('bogus', 'surface-well') is
  // 0 - (-1) === 1. The `SurfaceName` type stops that at every call site TypeScript checks —
  // and stops at none of them the moment a value arrives through an `as` cast, a JSON payload
  // or plain JS. A predicate whose whole job is to be trusted must not answer confidently
  // about a surface that does not exist.
  if (fromIndex === -1 || toIndex === -1) return false
  return toIndex - fromIndex === 1
}

/**
 * The surface a component nested inside `from` must use, or `null` at the top of the ramp.
 *
 * `null` is not a failure to handle later — it is the answer "you have run out of ramp, and
 * the fix is to flatten the nesting, not to add a fifth surface".
 */
export function nextSurface(from: SurfaceName): SurfaceName | null {
  const index = SURFACE_RAMP.indexOf(from)
  // Same -1 hazard as stepsExactlyOne: unguarded, `indexOf(unknown) + 1` is 0 and an unknown
  // surface would be told its child is `surface-well` — the bottom of the ramp, confidently
  // wrong. `null` here means "not a surface", which is the same answer as "out of ramp": in
  // both cases the caller must not nest.
  if (index === -1) return null
  return SURFACE_RAMP[index + 1] ?? null
}

/** The `var(--…)` reference for a surface, so consumers never retype the `--` prefix. */
export function surfaceVar(name: SurfaceName): string {
  return `var(--${name})`
}
