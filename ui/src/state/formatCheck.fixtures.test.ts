/**
 * The pins that keep `formatCheck.fixtures.ts` honest.
 *
 * ================= WHY THE PINS LIVE APART FROM THE DATA ===============================
 *
 * Holding the fixtures and these nine pins in ONE `.test.ts`, imported by `FormatCheck.test.tsx`
 * and `formatCheck.test.ts`, would register the describes in every importer's collection —
 * importing a test file does that — so every pin would run THREE times and the suite's pass count
 * would be silently inflated with duplicates. The data therefore lives in `./formatCheck.fixtures`
 * (a plain module, registered by name in the two source gates that scan it — see its header), and
 * this file is the ONE place the pins register.
 *
 * A fixture set is only as honest as the assertions holding it to the shipped contract, and these
 * hold shape (six rows in `CHECK_ORDER`), vocabulary, the corpus census, and the three measured
 * defects pinned rather than fixed.
 */

import { describe, expect, it } from 'vitest'

import {
  ALL_FIXTURES,
  BRAWL_VIOLATION_REPORT,
  FORMATLESS_REPORT,
  NO_FORMAT_REPORT,
  ONE_CARD_REPORT,
  ROTATION_ADVISORY,
  SINGLETON_VIOLATION_REPORT,
} from './formatCheck.fixtures'

/** `CHECK_ORDER`, as `deck_validator.py:487-494` declares it. */
const CHECK_ORDER = ['legality', 'size', 'copy_limit', 'sideboard', 'banned', 'rotation'] as const

describe('the fixtures model the shipped contract (AC 26, AC 27)', () => {
  it.each(ALL_FIXTURES)('$name is six rows in CHECK_ORDER', ({ report }) => {
    // Six rows always, in a declared order, is a BACKEND guarantee — pinned on both sides there
    // (`test_routes_format_check.py:208-219`, `test_format_check.py:116`). Pinning it on the
    // fixtures too is what stops a hand-edited fixture from quietly modelling a contract the
    // backend does not have, which is how a panel test starts passing for the wrong reason.
    expect(report.rows.map((row) => row.check)).toEqual([...CHECK_ORDER])
  })

  it.each(ALL_FIXTURES)('$name uses only the three-word status vocabulary', ({ report }) => {
    for (const row of report.rows) {
      expect(['pass', 'advisory', 'violation']).toContain(row.status)
      // No empty detail anywhere: every sentence is the backend's and every one is non-blank,
      // which is what lets the panel render a second line unconditionally.
      expect(row.detail.trim()).not.toBe('')
    }
  })

  it('has rotation ADVISORY in every fixture — 40 of 40 real decks, permanently', () => {
    // `deck_validator.py:589-600`: `cards` has 23 columns and none is a release date, there is no
    // sets table, and answering rotation needs a schema change, an importer change, a migration,
    // a full re-import of 38,261 cards AND a rotation-schedule source Scryfall does not publish.
    // Measured over the 240 real rows: every single advisory in the corpus is this one sentence.
    // So a caution badge in this panel is FURNITURE rather than a signal — which is a design fact
    // this assertion keeps in the suite.
    for (const { name, report } of ALL_FIXTURES) {
      const rotation = report.rows.find((row) => row.check === 'rotation')
      expect(rotation, name).toEqual(ROTATION_ADVISORY)
    }
  })

  it('pins the 195 / 40 / 5 census the corpus actually produced', () => {
    // NOT derived from the fixtures — these are RECORDED MEASUREMENTS the suite cannot re-derive.
    // Measured read-only over all 40 decks through the real ASGI app: 240 rows, 195 pass,
    // 40 advisory, 5 violation, and every one of the 40 advisories is the rotation row.
    const CENSUS = { decks: 40, rows: 240, pass: 195, advisory: 40, violation: 5 } as const
    expect(CENSUS.decks * CHECK_ORDER.length).toBe(CENSUS.rows)
    expect(CENSUS.pass + CENSUS.advisory + CENSUS.violation).toBe(CENSUS.rows)
    // The advisory count equals the deck count exactly, which is the same statement as "rotation
    // is the only advisory in the corpus" — and the arithmetic is what makes it checkable.
    expect(CENSUS.advisory).toBe(CENSUS.decks)
  })

  it('pins the size sentence a brawl deck sees — a minimum 40 BELOW its format’s (AC 28)', () => {
    // §2's whole finding, kept in the suite rather than only in the record. All 18 `brawl` decks
    // have a mainboard of EXACTLY 100 (min 100 / max 100, measured on deck ids), and Brawl
    // (Historic) is an exact-100 format per this repo's own shipped skill
    // (`plugin/skills/format-legality/SKILL.md:77`) — while `_MIN_MAINBOARD = 60` applies
    // regardless of format. So 45% of the deck table is shown a `pass` sentence naming a minimum
    // forty cards below its format's real requirement.
    //
    // No badge flips today, because every one of the 18 is at exactly 100 — the defect is in the
    // SENTENCE, not the verdict. A 61-card Brawl deck would be told `pass`; a 99-card one would
    // be told the minimum is 60. Declining the Python fix is deliberate: a per-format minimum is
    // a rule change in `src/logic` with MCP blast radius, so the record is corrected instead.
    const size = BRAWL_VIOLATION_REPORT.rows.find((row) => row.check === 'size')
    expect(size).toEqual({
      check: 'size',
      status: 'pass',
      detail: 'Mainboard has 100 cards; the minimum is 60.',
    })
    expect(BRAWL_VIOLATION_REPORT.mainboard_count).toBe(100)
  })

  it('pins `Mainboard has 1 cards` — a live plural defect, now in front of a person', () => {
    // `deck_validator.py:693` interpolates a count into a fixed plural. One real deck reaches it
    // (`Iron Man, Modern Marvel — reminder`), and this panel is the first thing that renders it.
    // Pinned rather than fixed: Python is deliberately untouched.
    const size = ONE_CARD_REPORT.rows.find((row) => row.check === 'size')
    expect(size?.detail).toBe('Mainboard has 1 cards; the minimum is 60.')
  })

  it('pins the trap: `is_legal: false` with NOT ONE violation row', () => {
    // Its live exposure is ZERO — the trap needs an unrecognised format and all 40 decks have
    // one, which is exactly the condition under which a wrong binding ships green. Both
    // formatless spellings produce it.
    for (const report of [FORMATLESS_REPORT, NO_FORMAT_REPORT]) {
      expect(report.is_legal).toBe(false)
      expect(report.format_recognized).toBe(false)
      expect(report.rows.some((row) => row.status === 'violation')).toBe(false)
      // …and the three format-INDEPENDENT checks keep answering, which is what makes "the same
      // shape whatever the answer" true rather than merely claimed.
      expect(
        report.rows.filter((row) => ['size', 'copy_limit', 'sideboard'].includes(row.check)),
      ).toHaveLength(3)
      for (const row of report.rows) {
        if (['size', 'copy_limit', 'sideboard'].includes(row.check)) expect(row.status).toBe('pass')
      }
    }
  })

  it('carries the ONLY `(+N more)` instance in the suite — it has none in the corpus', () => {
    // `_summarise` appends the suffix when several violations land on one row. Verified against
    // raw `validate_deck`: all five real violations are one-per-deck, so this shape has zero live
    // instances and would otherwise ship unrendered.
    const copyLimit = SINGLETON_VIOLATION_REPORT.rows.find((row) => row.check === 'copy_limit')
    expect(copyLimit?.detail).toContain('(+15 more)')
    expect(
      ALL_FIXTURES.filter((f) => f.report.rows.some((r) => r.detail.includes('more'))),
    ).toHaveLength(1)
  })

  it('covers every status × every check across the fixture set — no silent gap', () => {
    // The non-vacuity half, and the reason the set is this size: without it, a panel test could
    // be green over six passes and a caution while never rendering a violation tone at all.
    const seen = new Set<string>()
    for (const { report } of ALL_FIXTURES) {
      for (const row of report.rows) seen.add(`${row.check}:${row.status}`)
    }
    // Five of the six checks can violate; `rotation` never can (it appears in `CHECK_FOR_RULE`'s
    // values nowhere — nothing in this database can produce it).
    for (const check of ['legality', 'size', 'copy_limit', 'sideboard', 'banned']) {
      expect(seen, `${check} never passes in any fixture`).toContain(`${check}:pass`)
    }
    for (const check of ['legality', 'size', 'copy_limit', 'sideboard', 'banned']) {
      expect(seen, `${check} never violates in any fixture`).toContain(`${check}:violation`)
    }
    expect(seen).toContain('rotation:advisory')
    expect(seen).toContain('legality:advisory')
    expect(seen).toContain('banned:advisory')
    // …and `rotation` is NEVER anything else, in any fixture.
    expect(seen.has('rotation:pass')).toBe(false)
    expect(seen.has('rotation:violation')).toBe(false)
  })
})
