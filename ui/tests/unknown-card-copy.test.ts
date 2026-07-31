/**
 * `card_not_found` does not ship without its copy (story c3-2, C2 retro ruling **R1**).
 *
 * R1, in Brad's words: *"c3-2 does not merge with the token alone."* AD-16's extension rule is
 * that a new reason token and the UI state it drives land together; C1 shipped `internal_error`
 * alone and it cost c2-9 a repair AC. This file is the machine-checked half of that pairing for
 * the seventh token.
 *
 * ================= WHY `copy.test.ts`'s ROW PARSER CANNOT BE REUSED ====================
 *
 * `copy.test.ts` gates the state-panel copy byte-for-byte against `EXPERIENCE.md`, and it
 * selects a row structurally: *"any table line that writes both a quoted `Headline:` and a
 * quoted `Body:`"*. That is the two-field shape a state panel has.
 *
 * **This row is single-field, deliberately, and therefore excludes itself** — `copy.test.ts:66`
 * names it as one of exactly three rows that "exclude themselves without a skip list". It is not
 * an oversight in that parser; it is the parser being honest about what it gates. `card_not_found`
 * is not a panel: the view renders normally and one slot gets a label.
 *
 * So the c2-9 mechanism is structurally unavailable here, and reaching for it anyway would be
 * wrong twice over: `StateKey` is the PANEL vocabulary, and adding a member would make
 * `EveryPanelHasASource` demand a source for a panel nobody renders. This file gates the same
 * artefact with the same "read it from disk" principle, at the shape this row actually has.
 *
 * ================= WHAT THIS FILE DOES **NOT** GATE, DECLARED =========================
 *
 * The rendered placeholder. **c4-3 owns it**, along with the `"Unknown card"` string as a copy
 * module (`copy-rules.test.ts`'s `COPY_MODULES` already names c4-3 for exactly this). c3-2 ships
 * no component, so what is checked here is that the artefact says what `states.ts` claims it
 * says — not that anything renders it. The day c4-3 lands, its copy module joins `COPY_MODULES`
 * and the byte-for-byte assertion moves there.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/**
 * The ONE place this path is written in this file — `copy.test.ts` says the same about its own
 * copy of it, and the two are deliberately separate constants for two separate contracts. The
 * path carries a date because the UX artefacts are exported per run, so the non-vacuity anchor
 * below is what turns a stale path into a named failure rather than a suite asserting nothing.
 */
const EXPERIENCE_MD = fileURLToPath(
  new URL(
    '../../_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md',
    import.meta.url,
  ),
)

const raw = readFileSync(EXPERIENCE_MD, 'utf8')

/**
 * `states.ts` is read as SOURCE TEXT, not imported — and that is a constraint, not a preference.
 *
 * MEASURED 2026-07-31. `tsconfig.node.json` owns `tests/**\/*.ts` with `module: nodenext`, where
 * a relative import needs an explicit file extension; `tsconfig.app.json` owns `src` with
 * `moduleResolution: bundler`, where it must not have one. `states.ts` imports `../../api/schema`
 * and `./copy` extensionlessly — correct for its own project — so a static import from this file
 * pulls it into the NODE project and `tsc -b` reports `TS2835` on those two lines, then cascades:
 * `ErrorReason` fails to resolve, and all three of `states.ts`'s type-level asserts collapse to
 * `false` with errors that point at the asserts rather than at the import.
 *
 * `copy.test.ts` imports `copy.ts` and is fine only because `copy.ts` has **no relative imports
 * at all**. That is a property of that module, not a general permission — so the rule for this
 * directory is: a `ui/tests` file may import an app module only if that module is
 * import-free. Ledgered in `deferred-work.md`.
 *
 * The runtime value is therefore pinned where it can be: `src/components/StatePanel/states.test.ts`
 * belongs to the app project, imports the real binding, and asserts
 * `PLACEHOLDER_FOR_REASON.card_not_found === 'unknown-card'`. This read is the second half — it
 * ties that slug to the ARTEFACT, which the app project cannot reach as conveniently.
 */
const STATES_TS = readFileSync(
  fileURLToPath(new URL('../src/components/StatePanel/states.ts', import.meta.url)),
  'utf8',
)

/** The row label the artefact uses for the in-view case. */
const ROW_LABEL = 'Unknown card in a view'

/** Every table line in the artefact, as `label -> cell`. */
const rowsByLabel = new Map<string, string>()
for (const line of raw.split(/\r?\n/)) {
  const cells = /^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|$/.exec(line)
  if (cells) rowsByLabel.set(cells[1], cells[2])
}

describe('the unknown-card placeholder copy exists in EXPERIENCE.md (retro R1)', () => {
  // THE NON-VACUITY ANCHOR COMES FIRST, for the reason copy.test.ts gives: every assertion below
  // indexes into a parsed table, and a stale path or a changed table shape would yield an empty
  // map over which the checks assert NOTHING while reporting green.
  it('parsed the artefact, and it is populated', () => {
    expect(raw.length).toBeGreaterThan(1000)
    expect(rowsByLabel.size).toBeGreaterThan(20)
    // A row this file does not otherwise read, so the parse is proved general rather than
    // tuned to the one line under test.
    expect(rowsByLabel.has('No-active-deck')).toBe(true)
  })

  it('carries the row the seventh token points at', () => {
    expect(rowsByLabel.has(ROW_LABEL)).toBe(true)
  })

  it('spells the placeholder label exactly "Unknown card"', () => {
    const label = /Placeholder label:\s*"([^"]*)"/.exec(rowsByLabel.get(ROW_LABEL) ?? '')

    expect(label, `no quoted "Placeholder label:" in the ${ROW_LABEL} row`).not.toBeNull()
    expect(label?.[1]).toBe('Unknown card')
  })

  it('promises a placeholder rather than a banner — the FR-13 posture', () => {
    // The rest of the row is the reason `card_not_found` maps to no panel. If the artefact ever
    // changed its mind and asked for a banner, `states.ts`'s classification would be wrong and
    // this is where that shows up.
    const cell = rowsByLabel.get(ROW_LABEL) ?? ''
    expect(cell).toContain('No banner, no apology')
    expect(cell).toContain('the rest of the view renders normally')
  })

  it('says the same thing for a push, so one unknown card never fails the whole payload', () => {
    // The State-Patterns sibling row (FR-13). Two surfaces, one posture.
    expect(rowsByLabel.get('Unknown card in a push')).toContain('the push never fails wholesale')
  })

  it('is the destination states.ts records for card_not_found', () => {
    // THE PAIRING ITSELF. Without this the two halves could drift: the artefact could keep its
    // row while `states.ts` reclassified the token as "no UI response at all", and every other
    // assertion in this file would still pass.
    //
    // A source read rather than an import — see the STATES_TS comment above for the measured
    // tsconfig reason. Both directions are asserted, so moving the token into NO_UI_RESPONSE
    // (the exact drift this guards) fails here even though the entry above would still parse.
    expect(STATES_TS).toMatch(/card_not_found:\s*'unknown-card'/)
    expect(STATES_TS).not.toMatch(/NO_UI_RESPONSE\s*=\s*\[[^\]]*card_not_found/)

    // Non-vacuity: the file was genuinely read and the patterns are discriminating rather than
    // matching anything. `invalid_request` IS in NO_UI_RESPONSE, so the second pattern's shape
    // provably fires on a token that belongs there.
    expect(STATES_TS.length).toBeGreaterThan(1000)
    expect(STATES_TS).toMatch(/NO_UI_RESPONSE\s*=\s*\[[^\]]*invalid_request/)
  })

  it('is invisible to copy.test.ts by structure, which is why this file exists', () => {
    // Not a claim in prose — measured against the row itself, using copy.test.ts's own selector.
    // If EXPERIENCE.md ever rewrites this row into a two-field Headline+Body panel, THIS test
    // goes red and the copy should move under the c2-9 gate instead of staying here.
    const cell = rowsByLabel.get(ROW_LABEL) ?? ''
    expect(/Headline:\s*"([^"]*)"/.test(cell)).toBe(false)
    expect(/Body:\s*"([^"]*)"/.test(cell)).toBe(false)

    // Non-vacuity for the two negatives above: the selector genuinely fires on a real panel row,
    // so "no match" means this row's shape, not a broken regex.
    const panelRow = rowsByLabel.get('No-active-deck') ?? ''
    expect(/Headline:\s*"([^"]*)"/.test(panelRow)).toBe(true)
    expect(/Body:\s*"([^"]*)"/.test(panelRow)).toBe(true)
  })
})
