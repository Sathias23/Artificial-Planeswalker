/**
 * The surface-ramp predicate, proven in both directions (AC 9).
 *
 * The half of UX-DR1 that CAN be mechanised is "is this pair of surfaces one step apart?".
 * A predicate only ever tested on the legal step is a predicate that could be
 * `() => true` — so the two-level skip is asserted here beside it, and so are the
 * backwards step and the no-op.
 */

import { describe, expect, it } from 'vitest'

import { SURFACE_RAMP, nextSurface, stepsExactlyOne, surfaceVar } from './surfaces.ts'

describe('the surface ramp (UX-DR1)', () => {
  it('is the four closed levels, darkest to lightest', () => {
    expect(SURFACE_RAMP).toEqual([
      'surface-well',
      'surface-base',
      'surface-panel',
      'surface-overlay',
    ])
  })

  it('accepts every legal single step', () => {
    expect(stepsExactlyOne('surface-well', 'surface-base')).toBe(true)
    expect(stepsExactlyOne('surface-base', 'surface-panel')).toBe(true)
    expect(stepsExactlyOne('surface-panel', 'surface-overlay')).toBe(true)
  })

  it('rejects a two-level skip — the failure UX-DR1 names', () => {
    expect(stepsExactlyOne('surface-well', 'surface-panel')).toBe(false)
    expect(stepsExactlyOne('surface-base', 'surface-overlay')).toBe(false)
  })

  it('rejects a three-level skip', () => {
    expect(stepsExactlyOne('surface-well', 'surface-overlay')).toBe(false)
  })

  it('rejects standing still, and rejects going backwards', () => {
    expect(stepsExactlyOne('surface-panel', 'surface-panel')).toBe(false)
    expect(stepsExactlyOne('surface-panel', 'surface-base')).toBe(false)
    expect(stepsExactlyOne('surface-overlay', 'surface-well')).toBe(false)
  })

  it('walks the whole ramp with nextSurface and then runs out', () => {
    expect(nextSurface('surface-well')).toBe('surface-base')
    expect(nextSurface('surface-base')).toBe('surface-panel')
    expect(nextSurface('surface-panel')).toBe('surface-overlay')

    // Not an oversight to fix later: the ramp is closed at four (UX-DR41 leaves
    // --text-tertiary on --surface-overlay at 4.8:1 with no headroom). The answer to
    // `null` is to flatten the nesting.
    expect(nextSurface('surface-overlay')).toBeNull()
  })

  it('renders a token reference callers do not have to retype', () => {
    expect(surfaceVar('surface-panel')).toBe('var(--surface-panel)')
  })
})
