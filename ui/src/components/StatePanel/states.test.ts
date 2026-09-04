/**
 * The SEMANTIC pins for `states.ts`.
 *
 * `satisfies` proves the maps are TOTAL; nothing else proves their VALUES. Measured: swapping
 * the two database panels, or flipping `internal-error`'s load-bearing `false`, kept every test
 * and `npm run typecheck` green — "proven exhaustively, never proven forwarded" in map form.
 * These assertions pin the anchors the wire contract states in prose (`types.d.ts`), so a
 * flipped value is a deliberate contract change made against a red test, not a drift the wiring
 * inherits silently.
 *
 * This does NOT replace `typecheck` as the totality gate — `schema.test.ts` explains why a
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

  it('keeps the three designed silences silent', () => {
    // `null` is a NAMED answer: the SPA never generates an invalid_request, and an
    // over-cap push is surfaced to the agent, never the glass.
    expect(PANEL_FOR_REASON.invalid_request).toBeNull()
    expect(PANEL_FOR_REASON.payload_too_large).toBeNull()
    // `forbidden`, and the value matters rather than merely the totality: the browser never
    // holds the agent credential (AD-5), so a panel here would report a failure the reader neither
    // caused nor can fix. Pinned by value because the `satisfies` clause would accept a panel key
    // here just as happily as `null`.
    expect(PANEL_FOR_REASON.forbidden).toBeNull()
    // …and not the OTHER kind of null: `forbidden` has no placeholder destination either. Without
    // this, moving it into PLACEHOLDER_FOR_REASON would keep every type-level assert green.
    expect(PLACEHOLDER_FOR_REASON).not.toHaveProperty('forbidden')
  })

  // ------------------------------------------------------------------------------------------
  // The THIRD meaning of `null`, pinned by value the way the four panels above are.
  //
  // The three type-level asserts in `states.ts` prove every panel-less token is classified as
  // exactly one of {placeholder, nothing}. They do NOT prove WHICH — swapping `card_not_found`
  // into `NO_UI_RESPONSE` and dropping `PLACEHOLDER_FOR_REASON` to `{}` type-checks perfectly
  // and silently deletes the unknown-card destination. That is this file's whole reason for
  // existing, so the placeholder tokens get the same treatment as the panel tokens.
  // ------------------------------------------------------------------------------------------

  it('gives card_not_found no panel but a NAMED non-panel destination', () => {
    // No panel — one unresolvable card must never take a whole view down (FR-13).
    expect(PANEL_FOR_REASON.card_not_found).toBeNull()
    // …but not nothing: the placeholder CardPlaceholder renders.
    expect(PLACEHOLDER_FOR_REASON.card_not_found).toBe('unknown-card')
  })

  it('sends both of c3-5 image failures to the NAMED-CARD placeholder, not the unknown one', () => {
    // Same treatment as the seventh and eighth tokens, for the same reason: the type-level
    // asserts prove these two are classified, never WHICH WAY. Swapping either into
    // `NO_UI_RESPONSE` type-checks perfectly and silently deletes the tile CardPlaceholder renders.
    expect(PANEL_FOR_REASON.no_image_data).toBeNull()
    expect(PANEL_FOR_REASON.image_fetch_failed).toBeNull()

    // …and specifically NOT `unknown-card`. That is the assertion with teeth here: the two
    // placeholders look similar and mean opposite things. `unknown-card` says the app does not
    // know what this card is; `named-card` says it knows exactly, and only lacks the picture — so
    // it can draw the real name, cost and type line. Copy-pasting the line above would pass
    // every type-level assert in `states.ts` and put "Unknown card" under a card the app can name.
    expect(PLACEHOLDER_FOR_REASON.no_image_data).toBe('named-card')
    expect(PLACEHOLDER_FOR_REASON.image_fetch_failed).toBe('named-card')
    expect(PLACEHOLDER_FOR_REASON.no_image_data).not.toBe('unknown-card')
  })

  it('does not confuse "no panel" with "no UI response at all"', () => {
    // The distinction the classification exists to force, asserted in both directions so
    // neither list can quietly absorb the other's members.
    expect([...NO_UI_RESPONSE]).toEqual(['invalid_request', 'forbidden', 'payload_too_large'])
    expect([...NO_UI_RESPONSE]).not.toContain('card_not_found')
    // The two image tokens are panel-less and are NOT silences — the exact confusion this test names.
    expect([...NO_UI_RESPONSE]).not.toContain('no_image_data')
    expect([...NO_UI_RESPONSE]).not.toContain('image_fetch_failed')
    expect(Object.keys(PLACEHOLDER_FOR_REASON)).toEqual([
      'card_not_found',
      'no_image_data',
      'image_fetch_failed',
    ])
  })

  it('never lets the two deterministic states quietly retry — the load-bearing falses', () => {
    // types.d.ts: a deterministic bug re-hit by every identical request. A quiet retry
    // loop would hammer a broken backend under a calm panel that never changes.
    expect(RETRIES_QUIETLY['internal-error']).toBe(false)
    // The ESCALATION state exists because the quiet retry has already failed.
    expect(RETRIES_QUIETLY['database-updating-stalled']).toBe(false)
  })

  it('promises the self-transitions the copy promises', () => {
    // "this page will come alive on its own" / "Reads will resume automatically" — the copy
    // says it, so the contract the wiring reads must too.
    expect(RETRIES_QUIETLY['database-not-initialized']).toBe(true)
    expect(RETRIES_QUIETLY['database-updating']).toBe(true)
    expect(RETRIES_QUIETLY.disconnected).toBe(true)
  })

  it('carries exactly the two client-side panels outside the token vocabulary', () => {
    expect([...CLIENT_ONLY_STATES]).toEqual(['disconnected', 'database-updating-stalled'])
  })
})
