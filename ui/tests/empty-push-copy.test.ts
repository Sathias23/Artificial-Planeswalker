/**
 * The empty-push line is EXPERIENCE.md's sentence, byte for byte (story c6-6, AC 4).
 *
 * ================= THE SHAPE IS `empty-deck-copy.test.ts`'s, AND SO IS THE REASON ======
 *
 * `copy.test.ts` gates state-panel copy against `EXPERIENCE.md` by selecting *"any table line
 * that writes both a quoted `Headline:` and a quoted `Body:`"*, which is the two-field shape a
 * PANEL has. **This row is neither** — it is a single in-view sentence, and an empty push renders
 * no panel at all — so it excludes itself from that parser exactly as the empty-deck row and
 * `card_not_found`'s row do. The last test below proves that structurally rather than claiming
 * it, and it is the assertion that would fire if anyone "tidied" the artefact row into
 * Headline/Body shape: doing so would move `copy.test.ts`'s pin off 6 and put an empty push into
 * the state-panel vocabulary, which is the one thing this state is not.
 *
 * **The constants are IMPORTED, not read as source**, which is available only because
 * `src/containers/SuggestionsView/copy.ts` has no relative imports of its own — the measured
 * `tsc -b` rule for this directory (`tests/**` is the `nodenext` project, `src/**` the `bundler`
 * one). Its own header says so; this file is what depends on it.
 *
 * ================= WHY THE PIN IS ON A TEMPLATE AND NOT ON A SENTENCE ==================
 *
 * The artefact writes `{noun}`, so the artefact's own string is a template and the shipped
 * constant is that template unchanged. Substitution is asserted next door
 * (`SuggestionsView.test.tsx`), where the rendering lives. Splitting it that way is what keeps
 * THIS file's comparison a pure byte-for-byte one — a gate that substituted first would be
 * comparing two strings it had both constructed.
 *
 * ================= WHAT THIS FILE CANNOT SEE, DECLARED =================================
 *
 * It reads TEXT. It cannot see the rendered line, its colour, its position, or that the view
 * really swapped its body — `SuggestionsView.test.tsx` and `App.test.tsx` own the DOM half,
 * `shell.test.ts` owns the stylesheet half, and no test in this repo can see the line on a
 * screen. It also cannot judge whether the sentence is *blameless* or *concrete*:
 * `deferred-work.md`'s copy-guard entry is permanently open for exactly that reason and names
 * this story, and the discharge is a human reading recorded in the story's Debug Log, not an
 * assertion here.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  EMPTY_PUSH_NOUNS,
  EMPTY_PUSH_TEMPLATE,
  NOUN_PLACEHOLDER,
} from '../src/containers/SuggestionsView/copy.ts'

const artefact = (name: string): string =>
  readFileSync(
    fileURLToPath(
      new URL(
        `../../_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/${name}`,
        import.meta.url,
      ),
    ),
    'utf8',
  )

const EXPERIENCE = artefact('EXPERIENCE.md')

/** The label EXPERIENCE.md uses — and it writes it TWICE, in two different tables. */
const ROW_LABEL = 'Empty push'

/**
 * Every table cell written under *label*, in document order — a LIST, never a `Map.set`.
 *
 * `empty-deck-copy.test.ts`'s parser verbatim, and for its reason: `EXPERIENCE.md` writes this
 * label twice on purpose — a *Voice and Tone* row carrying the sentence and a *State Patterns*
 * row carrying the behaviour — and both are read below, for different clauses. A parser that kept
 * one would gate half the contract.
 *
 * `trimEnd()` because the row regex anchors on a final `|`: trailing whitespace after the last
 * pipe silently drops the row.
 */
const rowsFor = (label: string): string[] => {
  const cells: string[] = []
  for (const line of EXPERIENCE.split(/\r?\n/)) {
    const match = /^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|$/.exec(line.trimEnd())
    if (match && match[1] === label) cells.push(match[2])
  }
  return cells
}

/** The one cell of *label* that carries *marker*, refusing to guess. */
const rowWith = (label: string, marker: string): string => {
  const hits = rowsFor(label).filter((cell) => cell.includes(marker))
  if (hits.length !== 1) {
    throw new Error(
      `EXPERIENCE.md writes ${hits.length} rows labelled "${label}" containing "${marker}"; ` +
        'this gate needs exactly one to know which cell is the contract.',
    )
  }
  return hits[0]
}

describe('the empty-push line is the artefact’s sentence (c6-6, AC 4)', () => {
  // THE NON-VACUITY ANCHOR COMES FIRST, for `copy.test.ts`'s reason: every assertion below reads
  // a parsed table, and a stale artefact path or a changed table shape yields NOTHING to match
  // while the suite still reports green. The artefact is proved present and parsed, and the row
  // parser is proved general by finding a row this file never otherwise reads.
  it('parsed the artefact, and the row parser is general', () => {
    expect(EXPERIENCE.length).toBeGreaterThan(1000)
    expect(rowsFor('Unknown card in a view')).toHaveLength(1)
    // The label really is written twice — the property `rowsFor` exists for. If the artefact
    // ever merges them, the lookups below must be re-pointed rather than silently reading one.
    expect(rowsFor(ROW_LABEL)).toHaveLength(2)
  })

  it('ships the sentence BYTE-FOR-BYTE, placeholder and em dash and trailing period included', () => {
    // Byte-for-byte against the quoted value, not `toContain` and not a normalised compare: "The
    // agent's {noun} came back empty - nothing to show" (hyphen), "…another pass" (no period) and
    // a helpfully-expanded "{noun}" are all plausible edits that read fine in a diff, and each
    // breaks either UX-DR33's voice or the artefact contract.
    const quoted = /In-view:\s*"([^"]*)"/.exec(rowWith(ROW_LABEL, 'In-view:'))

    expect(quoted, 'no quoted "In-view:" in the Voice and Tone row').not.toBeNull()
    expect(EMPTY_PUSH_TEMPLATE).toBe(quoted?.[1])

    // NON-VACUITY for the comparison above: an import that resolved to `undefined` would match an
    // equally-undefined capture group if the regex ever stopped firing. Both sides are proved
    // independently, and the dash is pinned by CODEPOINT because U+2014, U+2013 and U+002D are
    // visually near-identical in a terminal diff and only one of them is the artefact's.
    expect(typeof EMPTY_PUSH_TEMPLATE).toBe('string')
    expect(EMPTY_PUSH_TEMPLATE.length).toBeGreaterThan(20)
    expect(EMPTY_PUSH_TEMPLATE).toContain('—')
    expect(EMPTY_PUSH_TEMPLATE).not.toContain('–')
    expect(EMPTY_PUSH_TEMPLATE.endsWith('.')).toBe(true)
  })

  it('keeps the artefact’s PLACEHOLDER rather than a hard-coded noun', () => {
    // The half that makes this row different from every other transcribed sentence in the app:
    // the artefact's string has a hole in it, and the constant ships the hole. What fills it is
    // no longer the wire kind — the epic-16 retro (item 4) ruled the c6-6 grammar ledger entry
    // release-gating, the artefact's cell moved first to `{noun}` + a named noun list, and the
    // substitution below gates that list against the cell.
    expect(EMPTY_PUSH_TEMPLATE).toContain(NOUN_PLACEHOLDER)
    expect(EMPTY_PUSH_TEMPLATE.split(NOUN_PLACEHOLDER)).toHaveLength(2)
  })

  it('ships the artefact’s own noun list, no more and no fewer', () => {
    // The amended cell ENUMERATES the display nouns after the sentence ("suggestions", "swaps",
    // "tier list", "card groups"), which makes the noun table transcribable rather than
    // authored: every quoted string in the cell after the sentence itself is a noun. The wire
    // kinds keying the table are not in the artefact — the store's `AGENT_VIEW_LABELS` is that
    // half of the contract, and `agentView.test.ts` pins table↔labels from the side that may
    // import both. A fifth kind added to the store without a noun here fails THAT test; a noun
    // here the artefact never named fails THIS one.
    const cell = rowWith(ROW_LABEL, 'In-view:')
    const quoted = [...cell.matchAll(/"([^"]*)"/g)].map((m) => m[1])
    const nouns = quoted.filter((q) => q !== EMPTY_PUSH_TEMPLATE)

    expect(nouns.length, 'the cell must enumerate the nouns beside the sentence').toBeGreaterThan(0)
    expect([...Object.values(EMPTY_PUSH_NOUNS)].sort()).toEqual([...nouns].sort())
  })

  it('carries the "opens and renders rather than rejecting" posture the branch is built on', () => {
    // The State Patterns row is WHY the view opens at all for a push with nothing in it. If the
    // artefact ever changed its mind, `suggestionsViewOf`'s total construction and this
    // container's branch would both be wrong, and this is where it surfaces.
    const cell = rowWith(ROW_LABEL, 'deliberate empty state')
    expect(cell).toContain('The view opens')
    expect(cell.toLowerCase()).toContain('rather than rejecting')
  })

  it('is invisible to copy.test.ts by structure, which is why this file exists', () => {
    // Measured with `copy.test.ts`'s own selector rather than claimed. That file and
    // `copy-tails.test.ts` are both pinned at 6 rows; this row is neither `Headline:` nor `Body:`
    // shape, so it is invisible to them and those pins do not move. Rewording it into that shape
    // would move both pins AND put an empty push into the state-panel vocabulary — which is
    // exactly what "no panel" means here.
    const cells = rowsFor(ROW_LABEL)
    expect(cells).toHaveLength(2)
    for (const cell of cells) {
      expect(/Headline:\s*"([^"]*)"/.test(cell)).toBe(false)
      expect(/Body:\s*"([^"]*)"/.test(cell)).toBe(false)
    }
    // Non-vacuity: the selector genuinely fires on a real panel row in the same artefact.
    const panelRow = rowsFor('No-active-deck')[0]
    expect(
      panelRow,
      'the No-active-deck row vanished — the parser is broken, not the artefact',
    ).toBeDefined()
    expect(/Headline:\s*"([^"]*)"/.test(panelRow)).toBe(true)
    expect(/Body:\s*"([^"]*)"/.test(panelRow)).toBe(true)
  })
})
