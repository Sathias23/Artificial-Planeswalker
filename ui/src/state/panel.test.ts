/**
 * The boundary that makes `StatePanel` safe to hand a wire value.
 *
 * Two claims, and they are different claims:
 *
 *   **First** — the panel comes from the TOKEN, not from the status. Proved by discrimination
 *   rather than by inspection: the two database tokens share one status and produce two panels,
 *   so no implementation that read `response.status` could pass this file. That is AD-16's
 *   *"nothing in the SPA keys off a bare status code"* made executable for the first time.
 *
 *   **Second** — the function is TOTAL. Not "handles the cases we thought of": every string, plus
 *   `null`, has an answer, and the three routes to `internal-error` are asserted separately
 *   because they are three different mistakes (an unknown token, a token with no panel, and no
 *   token at all).
 */

import { describe, expect, it } from 'vitest'

import { STATE_COPY } from '../components/StatePanel/copy'
import { PANEL_FOR_REASON } from '../components/StatePanel/states'
import { panelFor } from './panel'

describe('the panel comes from the token, never from the status', () => {
  it('gives two DIFFERENT panels to the two tokens that share status 503', () => {
    // The whole of AD-16 in three lines. Both of these arrive as `503`; a client keyed on the
    // status could not tell them apart, and the fresh-install path would show "Card database is
    // updating." to someone who has never built a database.
    expect(panelFor('database_not_initialized')).toBe('database-not-initialized')
    expect(panelFor('database_unavailable')).toBe('database-updating')
    expect(panelFor('database_not_initialized')).not.toBe(panelFor('database_unavailable'))
  })

  it('maps every panel-bearing token to the panel states.ts declares', () => {
    // Read out of the map rather than re-listed here: a test that enumerated today's four would
    // be a second copy of the decision, free to drift from the one the compiler checks.
    for (const [reason, panel] of Object.entries(PANEL_FOR_REASON)) {
      if (panel === null) continue
      expect(panelFor(reason), `${reason} should map to ${panel}`).toBe(panel)
    }
  })

  it('is reading a populated map with more than one destination (non-vacuity)', () => {
    const panels = Object.values(PANEL_FOR_REASON).filter((panel) => panel !== null)
    expect(panels.length).toBeGreaterThan(1)
    expect(new Set(panels).size).toBeGreaterThan(1)
  })
})

describe('it is total, so nothing unrenderable reaches STATE_COPY', () => {
  it('clamps a token that is not in the union at all', () => {
    expect(panelFor('quantum_flux_capacitor_failed')).toBe('internal-error')
  })

  it('clamps a token that HAS no panel by design', () => {
    // Six tokens map to `null` in `states.ts`, and two of them — `invalid_request` and
    // `payload_too_large` — are declared on `GET /api/decks` itself. `null` there means "no UI
    // response at all", which a whole-screen poll cannot honour: it must render something. Either
    // one arriving means the SPA sent a request it should never have sent, which is a client bug.
    expect(panelFor('invalid_request')).toBe('internal-error')
    expect(panelFor('payload_too_large')).toBe('internal-error')
  })

  it('clamps the absence of a token', () => {
    expect(panelFor(null)).toBe('internal-error')
  })

  it('clamps inherited object keys rather than returning them', () => {
    // `PANEL_FOR_REASON['__proto__']` is an OBJECT, not `undefined`, so a truthiness check or a
    // `?? 'internal-error'` on a bare index would hand `Object.prototype` to `StatePanel`'s
    // `state` prop and crash on `STATE_COPY[state].headline`. A wire string is attacker-adjacent
    // input by construction — the companion is one `fetch` away from any page in the browser.
    expect(panelFor('__proto__')).toBe('internal-error')
    expect(panelFor('constructor')).toBe('internal-error')
    expect(panelFor('toString')).toBe('internal-error')
    expect(panelFor('hasOwnProperty')).toBe('internal-error')
  })

  it.each(['', ' ', 'DATABASE_UNAVAILABLE', 'database_unavailable ', 'null', 'undefined'])(
    'clamps %o',
    (reason) => {
      expect(panelFor(reason)).toBe('internal-error')
    },
  )

  it('and a KNOWN token still maps normally — the non-vacuity half', () => {
    // Everything above resolves to `internal-error`, which `() => 'internal-error'` would also
    // satisfy. This is the assertion that says the clamp is a clamp and not the whole function.
    expect(panelFor('deck_not_found')).toBe('no-active-deck')
    expect(panelFor('internal_error')).toBe('internal-error')
  })

  it('never returns a key STATE_COPY cannot render — checked against the copy module', () => {
    // The end-to-end version of totality: whatever this function returns must be indexable in
    // `STATE_COPY`, because that index has no fallback branch at `StatePanel.tsx:104`.
    const inputs = [
      'database_not_initialized',
      'database_unavailable',
      'deck_not_found',
      'internal_error',
      'card_not_found',
      'forbidden',
      '__proto__',
      'not_a_token',
      '',
      null,
    ]
    for (const input of inputs) {
      expect(
        STATE_COPY[panelFor(input)],
        `panelFor(${String(input)}) is unrenderable`,
      ).toBeDefined()
    }
  })
})
