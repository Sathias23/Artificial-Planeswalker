/**
 * The SEMANTIC pins for `states.ts` (review 2026-07-29).
 *
 * `satisfies` proves the maps are TOTAL; nothing proved their VALUES. The review measured that
 * swapping the two database panels, or flipping `internal-error`'s load-bearing `false`, kept
 * every test and `npm run typecheck` green — c2-8's "proven exhaustively, never proven
 * forwarded" defect in map form. These assertions pin the anchors the wire contract states in
 * prose (`types.d.ts:67-69`), so a flipped value is a deliberate contract change made against a
 * red test, not a drift c3-9 inherits silently.
 *
 * This does NOT replace `typecheck` as the totality gate — `schema.test.ts:4` explains why a
 * runtime enumeration cannot. It pins MEANINGS, which is the half the type cannot hold.
 */

import { describe, expect, it } from 'vitest'

import {
  CLIENT_ONLY_STATES,
  NO_UI_RESPONSE,
  PANEL_FOR_REASON,
  PLACEHOLDER_FOR_REASON,
  RETRIES_QUIETLY,
} from './states'

describe('the state maps mean what the wire contract says (review 2026-07-29)', () => {
  it('routes each token to its own panel — the values, not merely the totality', () => {
    expect(PANEL_FOR_REASON.deck_not_found).toBe('no-active-deck')
    expect(PANEL_FOR_REASON.database_not_initialized).toBe('database-not-initialized')
    expect(PANEL_FOR_REASON.database_unavailable).toBe('database-updating')
    expect(PANEL_FOR_REASON.internal_error).toBe('internal-error')
  })

  it('keeps the two designed silences silent', () => {
    // `null` is a NAMED answer (AC 12): the SPA never generates an invalid_request, and an
    // over-cap push is surfaced to the agent, never the glass.
    expect(PANEL_FOR_REASON.invalid_request).toBeNull()
    expect(PANEL_FOR_REASON.payload_too_large).toBeNull()
  })

  // ------------------------------------------------------------------------------------------
  // c3-2: the THIRD meaning of `null`, pinned by value the way the four panels above are.
  //
  // The three type-level asserts in `states.ts` prove every panel-less token is classified as
  // exactly one of {placeholder, nothing}. They do NOT prove WHICH — swapping `card_not_found`
  // into `NO_UI_RESPONSE` and dropping `PLACEHOLDER_FOR_REASON` to `{}` type-checks perfectly
  // and silently deletes c4-3's destination. That is this file's whole reason for existing
  // (review 2026-07-29), so the seventh token gets the same treatment as the other six.
  // ------------------------------------------------------------------------------------------

  it('gives card_not_found no panel but a NAMED non-panel destination', () => {
    // No panel — one unresolvable card must never take a whole view down (FR-13).
    expect(PANEL_FOR_REASON.card_not_found).toBeNull()
    // …but not nothing: the placeholder c4-3 renders.
    expect(PLACEHOLDER_FOR_REASON.card_not_found).toBe('unknown-card')
  })

  it('does not confuse "no panel" with "no UI response at all"', () => {
    // The distinction retro R1 exists to force, asserted in both directions so neither list can
    // quietly absorb the other's members.
    expect([...NO_UI_RESPONSE]).toEqual(['invalid_request', 'payload_too_large'])
    expect([...NO_UI_RESPONSE]).not.toContain('card_not_found')
    expect(Object.keys(PLACEHOLDER_FOR_REASON)).toEqual(['card_not_found'])
  })

  it('never lets the two deterministic states quietly retry — the load-bearing falses', () => {
    // types.d.ts:67-69: a deterministic bug re-hit by every identical request. A quiet retry
    // loop would hammer a broken backend under a calm panel that never changes.
    expect(RETRIES_QUIETLY['internal-error']).toBe(false)
    // The ESCALATION state exists because the quiet retry has already failed (Q5).
    expect(RETRIES_QUIETLY['database-updating-stalled']).toBe(false)
  })

  it('promises the self-transitions the copy promises', () => {
    // "this page will come alive on its own" / "Reads will resume automatically" — the copy
    // says it, so the contract c3-9 reads must too.
    expect(RETRIES_QUIETLY['database-not-initialized']).toBe(true)
    expect(RETRIES_QUIETLY['database-updating']).toBe(true)
    expect(RETRIES_QUIETLY.disconnected).toBe(true)
  })

  it('carries exactly the two client-side panels outside the token vocabulary', () => {
    expect([...CLIENT_ONLY_STATES]).toEqual(['disconnected', 'database-updating-stalled'])
  })
})
