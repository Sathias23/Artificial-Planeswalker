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
 * module. Be precise about what that means: `copy-rules.test.ts:99` names "c4-3's 'Unknown card'"
 * in a PROSE COMMENT above `COPY_MODULES`, not as an entry in it — the Map is git-checked, so it
 * cannot name a module that does not exist yet. That half is therefore a comment, not a gate, and
 * an earlier draft of this header wrongly called it machine-checked. c3-2 ships no component, so
 * what is gated here is that the artefact says what `states.ts` claims it says — not that anything
 * renders it. The day c4-3 lands, its copy module joins `COPY_MODULES` and the byte-for-byte
 * assertion moves there.
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

/**
 * `states.ts` with its comments removed — the only text the pairing assertions may match.
 *
 * c3-2 added roughly sixty lines of block comment to that file explaining this exact pairing, and
 * several of them spell `card_not_found` and `unknown-card` in prose. A regex over the raw source
 * is therefore satisfied by the documentation of the entry rather than the entry, which is a guard
 * that cannot fail for the reason it exists (review, 2026-07-31).
 */
const STATES_CODE = STATES_TS.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')

/**
 * The member tokens of `NO_UI_RESPONSE`, read from the code.
 *
 * Reads the array body up to its `] as const` close — the terminator the declaration actually
 * has — rather than to the first bare `]`. Two earlier forms each had a truncation: `[^\]]*`
 * against the raw file was disarmed by any `]` in a comment, and the same class against stripped
 * text would still stop at a `]` inside a future nested literal (review round 2, 2026-07-31).
 */
const noUiResponseMembers = (): string[] => {
  const body = /NO_UI_RESPONSE\s*=\s*\[([\s\S]*?)\]\s*as const/.exec(STATES_CODE)?.[1] ?? ''
  return [...body.matchAll(/'([^']+)'/g)].map((m) => m[1])
}

/** The row label the artefact uses for the in-view case. */
const ROW_LABEL = 'Unknown card in a view'

/**
 * Every table line in the artefact, as `label -> cell`, keeping ALL rows for a repeated label.
 *
 * `copy.test.ts:93` THROWS on a duplicate label, and its comment says why: *"`Map.set` would keep
 * the last row and the size pin would still pass — the exact drift this gate exists to catch,
 * hidden by the shape of Map."* The first version of this file used a bare `Map.set` anyway
 * (review, 2026-07-31).
 *
 * Throwing is wrong HERE, though, and that is a real difference rather than an excuse: `copy.test`
 * scans only two-field `Headline:`+`Body:` rows, of which the artefact has none repeated. This
 * file scans EVERY table line, and `EXPERIENCE.md` already repeats eight labels legitimately
 * (`Card detail panel`, `Agent views nav`, `Empty push`, … — a Voice-and-Tone row and a
 * State-Patterns row for the same concept). Throwing would make this suite red on an artefact
 * that is perfectly correct.
 *
 * So the map collects a LIST per label, and the assertions below say which row they mean. A
 * repeated `Unknown card in a view` therefore makes the pairing test fail loudly on an ambiguous
 * lookup, rather than silently gating whichever row happened to come last.
 */
const rowsByLabel = new Map<string, string[]>()
for (const line of raw.split(/\r?\n/)) {
  // `trimEnd()` because the row regex anchors on a final `|`: trailing whitespace after the
  // last pipe would silently drop the row from the map (review round 2, 2026-07-31).
  const cells = /^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|$/.exec(line.trimEnd())
  if (!cells) continue
  const existing = rowsByLabel.get(cells[1])
  if (existing) existing.push(cells[2])
  else rowsByLabel.set(cells[1], [cells[2]])
}

/** The one cell for *label*, refusing to guess when the artefact writes more than one. */
const oneRow = (label: string): string => {
  const rows = rowsByLabel.get(label) ?? []
  if (rows.length !== 1) {
    throw new Error(
      `EXPERIENCE.md writes ${rows.length} rows labelled "${label}"; this gate needs exactly ` +
        'one to know which copy is the contract. De-duplicate the artefact, or teach this file ' +
        'which surface it means.',
    )
  }
  return rows[0]
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

  it('carries exactly one row for the label the seventh token points at', () => {
    // `oneRow` throws on a repeat rather than silently taking the last — see its comment.
    expect(() => oneRow(ROW_LABEL)).not.toThrow()
  })

  it('spells the placeholder label exactly "Unknown card"', () => {
    const label = /Placeholder label:\s*"([^"]*)"/.exec(oneRow(ROW_LABEL))

    expect(label, `no quoted "Placeholder label:" in the ${ROW_LABEL} row`).not.toBeNull()
    expect(label?.[1]).toBe('Unknown card')
  })

  it('promises a placeholder rather than a banner — the FR-13 posture', () => {
    // The rest of the row is the reason `card_not_found` maps to no panel. If the artefact ever
    // changed its mind and asked for a banner, `states.ts`'s classification would be wrong and
    // this is where that shows up.
    const cell = oneRow(ROW_LABEL)
    expect(cell).toContain('No banner, no apology')
    expect(cell).toContain('the rest of the view renders normally')
  })

  it('says the same thing for a push, so one unknown card never fails the whole payload', () => {
    // The State-Patterns sibling row (FR-13). Two surfaces, one posture.
    expect(oneRow('Unknown card in a push')).toContain('the push never fails wholesale')
  })

  it('is the destination states.ts records for card_not_found', () => {
    // THE PAIRING ITSELF. Without this the two halves could drift: the artefact could keep its
    // row while `states.ts` reclassified the token as "no UI response at all", and every other
    // assertion in this file would still pass.
    //
    // A source read rather than an import — see the STATES_TS comment above for the measured
    // tsconfig reason. Matched against CODE ONLY: c3-2 added ~60 lines of comment to `states.ts`
    // that discuss this very pairing, so a match anywhere in the raw file would be satisfied by
    // the prose describing the entry rather than the entry (review, 2026-07-31).
    expect(STATES_CODE).toMatch(/card_not_found:\s*'unknown-card'/)
    expect(noUiResponseMembers()).not.toContain('card_not_found')

    // Non-vacuity: the file was genuinely read, comment-stripping did not eat the code, and the
    // member reader is discriminating rather than returning nothing. `invalid_request` IS in
    // NO_UI_RESPONSE, so the reader provably finds a token that belongs there.
    expect(STATES_CODE.length).toBeGreaterThan(1000)
    expect(noUiResponseMembers()).toEqual(['invalid_request', 'payload_too_large'])
    // The stripper above is NOT string-aware: a future `//` or `/*` inside a string literal in
    // states.ts would truncate live code from that point (declared in ui/README.md's blind-spot
    // table). This anchor is the file's LAST live statement, so a mid-file truncation cannot
    // pass silently (review round 2, 2026-07-31).
    expect(STATES_CODE).toMatch(/EveryPlaceholderIsAReal/)
  })

  it('is invisible to copy.test.ts by structure, which is why this file exists', () => {
    // Not a claim in prose — measured against the row itself, using copy.test.ts's own selector.
    // If EXPERIENCE.md ever rewrites this row into a two-field Headline+Body panel, THIS test
    // goes red and the copy should move under the c2-9 gate instead of staying here.
    const cell = oneRow(ROW_LABEL)
    expect(/Headline:\s*"([^"]*)"/.test(cell)).toBe(false)
    expect(/Body:\s*"([^"]*)"/.test(cell)).toBe(false)

    // Non-vacuity for the two negatives above: the selector genuinely fires on a real panel row,
    // so "no match" means this row's shape, not a broken regex.
    const panelRow = oneRow('No-active-deck')
    expect(/Headline:\s*"([^"]*)"/.test(panelRow)).toBe(true)
    expect(/Body:\s*"([^"]*)"/.test(panelRow)).toBe(true)
  })
})
