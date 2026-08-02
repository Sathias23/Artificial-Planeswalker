/**
 * c3-5's two tokens do not ship without their UI destination (C2 retro ruling **R1**).
 *
 * R1, in Brad's words: *"c3-2 does not merge with the token alone."* AD-16's extension rule is
 * that a new reason token and the UI state it drives land together; C1 shipped `internal_error`
 * alone and it cost c2-9 a repair AC. `unknown-card-copy.test.ts` is that machine-checked half for
 * the seventh token; this file is it for the ninth and tenth.
 *
 * ================= WHAT MAKES THIS PAIR UNUSUAL ========================================
 *
 * **The UI half was already written, gated and shipped before the tokens existed.**
 * `EXPERIENCE.md` has carried both rows since the artefact was exported: *"Card with no image
 * data → Named Card placeholder (FR-19)"* and *"CDN fetch failure → … UI renders the named Card
 * placeholder"*. So the pairing this file gates is not "did somebody remember to write the copy"
 * but the sharper question: **do the two tokens point at the destination the artefact actually
 * names, and at the same one as each other?**
 *
 * That second half is the one with teeth. The two cases render **identically** and differ only in
 * whether a retry could ever help — so the plausible mistake is not forgetting a destination, it
 * is sending one of them to `unknown-card`, which the artefact reserves for a card the app cannot
 * name at all. Every type-level assert in `states.ts` stays green through that mistake.
 *
 * ================= WHY `copy.test.ts`'s ROW PARSER CANNOT BE REUSED ====================
 *
 * Same reason as `unknown-card-copy.test.ts`: `copy.test.ts` selects rows structurally as *"any
 * table line that writes both a quoted `Headline:` and a quoted `Body:`"*, which is the shape a
 * state PANEL has. Neither of these rows is a panel — the view renders normally and one tile gets
 * a placeholder — so both exclude themselves from that gate by structure, and reaching for it
 * anyway would make `EveryPanelHasASource` demand a source for a panel nobody renders.
 *
 * ================= WHAT THIS FILE DOES **NOT** GATE, DECLARED =========================
 *
 * The rendered placeholder. **c4-3 owns it** (the component) and **c4-4** the tile that fetches an
 * image into it. No copy module exists for it yet, so — exactly as in the c3-2 file — that half is
 * a comment in `copy-rules.test.ts`, not a gate. What is gated here: the artefact says what
 * `states.ts` claims it says, and both tokens agree on it.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/**
 * The ONE place this path is written in this file — `copy.test.ts` and
 * `unknown-card-copy.test.ts` each say the same about their own copies, and all three are
 * deliberately separate constants for separate contracts. The path carries a date because the UX
 * artefacts are exported per run, so the non-vacuity anchor below is what turns a stale path into
 * a named failure rather than a suite asserting nothing.
 */
const EXPERIENCE_MD = fileURLToPath(
  new URL(
    '../../_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md',
    import.meta.url,
  ),
)

const raw = readFileSync(EXPERIENCE_MD, 'utf8')

/**
 * `states.ts` is read as SOURCE TEXT, not imported — the measured tsconfig reason is written out
 * in full in `unknown-card-copy.test.ts`: `tests/**` is the `nodenext` project, `src/**` the
 * `bundler` one, and `states.ts`'s extensionless relative imports are correct for its own project
 * and a `TS2835` in this one. The runtime values are pinned in
 * `src/components/StatePanel/states.test.ts`, which belongs to the app project and imports the
 * real binding; this read is the half that ties those slugs to the ARTEFACT.
 */
const STATES_CODE = readFileSync(
  fileURLToPath(new URL('../src/components/StatePanel/states.ts', import.meta.url)),
  'utf8',
)
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/\/\/.*$/gm, '')

/** Every table line in the artefact, as `label -> cells`, keeping ALL rows for a repeated label. */
const rowsByLabel = new Map<string, string[]>()
for (const line of raw.split(/\r?\n/)) {
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
        'one to know which copy is the contract.',
    )
  }
  return rows[0]
}

const NO_IMAGE_ROW = 'Card with no image data'
const FETCH_FAILURE_ROW = 'CDN fetch failure'

describe('the named-card placeholder copy exists in EXPERIENCE.md (retro R1)', () => {
  // THE NON-VACUITY ANCHOR COMES FIRST, for the reason copy.test.ts gives: every assertion below
  // indexes into a parsed table, and a stale path or a changed table shape would yield an empty
  // map over which the checks assert NOTHING while reporting green.
  it('parsed the artefact, and it is populated', () => {
    expect(raw.length).toBeGreaterThan(1000)
    expect(rowsByLabel.size).toBeGreaterThan(20)
    // A row this file does not otherwise read, so the parse is proved general rather than tuned
    // to the two lines under test.
    expect(rowsByLabel.has('No-active-deck')).toBe(true)
  })

  it('carries exactly one row for each of the two tokens', () => {
    expect(() => oneRow(NO_IMAGE_ROW)).not.toThrow()
    expect(() => oneRow(FETCH_FAILURE_ROW)).not.toThrow()
  })

  it('asks for the NAMED Card placeholder in both, not a substitute image', () => {
    // AD-11's non-negotiable: no grey rectangle, no 1x1 pixel, no generic card back. The artefact
    // is where that is promised to the reader; `test_routes_card_image.py` is where the backend
    // is held to it.
    expect(oneRow(NO_IMAGE_ROW)).toMatch(/[Nn]amed Card placeholder/)
    expect(oneRow(FETCH_FAILURE_ROW)).toMatch(/named Card placeholder/)
  })

  it('says the fetch failure is answered by the BACKEND and recovered without a retry UI', () => {
    // The rest of that row is the reason `image_fetch_failed` is a wire token at all, and the
    // reason c3-8 can add negative caching as pure behaviour: the artefact already promises the
    // backoff and forbids the per-image retry control.
    const cell = oneRow(FETCH_FAILURE_ROW)
    expect(cell).toContain('negative-cached with backoff')
    expect(cell).toContain('no per-image retry UI')
  })

  it('is the destination states.ts records for BOTH tokens, and the same one', () => {
    // THE PAIRING ITSELF, and the assertion this file exists for. Matched against CODE ONLY: this
    // pairing is discussed at length in `states.ts`'s comments, so a match over the raw file would
    // be satisfied by the prose describing the entry rather than by the entry (c3-2 review).
    expect(STATES_CODE).toMatch(/no_image_data:\s*'named-card'/)
    expect(STATES_CODE).toMatch(/image_fetch_failed:\s*'named-card'/)

    // …and NOT the c3-2 destination. The two placeholders look similar and mean opposite things:
    // `unknown-card` is for a card the app cannot name, `named-card` for one it can name and only
    // lacks a picture for. Copy-pasting the wrong line type-checks perfectly.
    expect(STATES_CODE).not.toMatch(/no_image_data:\s*'unknown-card'/)
    expect(STATES_CODE).not.toMatch(/image_fetch_failed:\s*'unknown-card'/)

    // Non-vacuity for the two negatives: the comment stripper did not eat the code, and the
    // matcher provably finds a `'unknown-card'` binding that IS there.
    expect(STATES_CODE.length).toBeGreaterThan(1000)
    expect(STATES_CODE).toMatch(/card_not_found:\s*'unknown-card'/)
    // The stripper is not string-aware (declared in ui/README.md's blind-spot table), so a `//`
    // inside a future string literal would truncate live code from that point. This anchor is the
    // file's LAST live statement, so a mid-file truncation cannot pass silently.
    expect(STATES_CODE).toMatch(/EveryPlaceholderIsAReal/)
  })

  it('is invisible to copy.test.ts by structure, which is why this file exists', () => {
    // Measured against the rows themselves using copy.test.ts's own selector, not claimed in
    // prose. If EXPERIENCE.md ever rewrites either into a two-field Headline+Body panel, THIS
    // test goes red and the copy should move under the c2-9 gate instead of staying here.
    for (const label of [NO_IMAGE_ROW, FETCH_FAILURE_ROW]) {
      expect(/Headline:\s*"([^"]*)"/.test(oneRow(label))).toBe(false)
      expect(/Body:\s*"([^"]*)"/.test(oneRow(label))).toBe(false)
    }

    // Non-vacuity for those negatives: the selector genuinely fires on a real panel row.
    const panelRow = oneRow('No-active-deck')
    expect(/Headline:\s*"([^"]*)"/.test(panelRow)).toBe(true)
    expect(/Body:\s*"([^"]*)"/.test(panelRow)).toBe(true)
  })
})
