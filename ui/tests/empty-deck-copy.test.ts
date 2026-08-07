/**
 * The empty-deck line is EXPERIENCE.md's sentence, and the treatment is DESIGN.md's (story c4-12).
 *
 * Two contracts, one file, because they were opened by the same finding. AC 1 says the line ships
 * *byte-for-byte* from `EXPERIENCE.md`; AC 26 says `DESIGN.md` **specifies the treatment**, because
 * before this story it did not — the string does not appear there, the word *empty* appears twice
 * in unrelated senses, and the entire written specification was two `EXPERIENCE.md` table cells.
 * That made *"the deck view matches DESIGN.md"* unsatisfiable for this branch rather than merely
 * unchecked. Both halves are gated here so the amendment cannot be quietly reverted while the
 * stylesheet keeps citing it.
 *
 * ================= THE SHAPE IS `unknown-card-copy.test.ts`'s, AND SO IS THE REASON ====
 *
 * `copy.test.ts` gates state-panel copy against `EXPERIENCE.md` by selecting *"any table line that
 * writes both a quoted `Headline:` and a quoted `Body:`"*, which is the two-field shape a PANEL
 * has. **This row is neither** — it is a single in-grid sentence, and an empty deck renders no
 * panel at all — so it excludes itself from that parser exactly as `card_not_found`'s row does.
 * The last test below proves that structurally rather than claiming it, and it is the assertion
 * that would fire if anyone "tidied" the artefact row into Headline/Body shape: doing so would
 * move `copy.test.ts`'s pin off 6 and put an empty deck in the state-panel vocabulary, which is
 * the one thing this state is not.
 *
 * **The constant is IMPORTED, not read as source**, which is available only because
 * `src/containers/CardGrid/copy.ts` has no relative imports of its own — the measured `tsc -b`
 * rule for this directory (`tests/**` is the `nodenext` project, `src/**` the `bundler` one). Its
 * own header says so; this file is what depends on it.
 *
 * ================= WHAT THIS FILE CANNOT SEE, DECLARED =================================
 *
 * It reads TEXT. It cannot see the rendered line, its colour, its position, or whether the `<ul>`
 * was really replaced — `CardGrid.test.tsx` and `App.test.tsx` own the DOM half, `shell.test.ts`
 * owns the stylesheet half, and no test in this repo can see the line on a screen. It also cannot
 * judge whether the sentence is *blameless* or *concrete*: `deferred-work.md`'s copy-guard entry
 * is permanently open for exactly that reason and names this story, and the discharge is a human
 * reading recorded in the story's Debug Log, not an assertion here.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { EMPTY_DECK_LINE } from '../src/containers/CardGrid/copy.ts'

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
const DESIGN = artefact('DESIGN.md')

/** The label EXPERIENCE.md uses — and it deliberately writes it TWICE. See {@link rowsFor}. */
const ROW_LABEL = 'Empty active deck (0 cards)'

/**
 * Every table cell written under *label*, in document order — a LIST, never a `Map.set`.
 *
 * `copy.test.ts` throws on a duplicate label and explains why (*"`Map.set` would keep the last row
 * and the size pin would still pass"*). Throwing is wrong here for `unknown-card-copy.test.ts`'s
 * stated reason and then some: `EXPERIENCE.md` writes this label **twice on purpose** — a *Voice
 * and Tone* row carrying the sentence and a *State Patterns* row carrying the behaviour — and both
 * are read below, for different clauses. A parser that kept one would gate half the contract.
 */
const rowsFor = (label: string): string[] => {
  const cells: string[] = []
  for (const line of EXPERIENCE.split(/\r?\n/)) {
    // `trimEnd()` because the row regex anchors on a final `|`: trailing whitespace after the last
    // pipe silently drops the row (the defect `unknown-card-copy.test.ts` records at review).
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

describe('the empty-deck line is the artefact’s sentence (c4-12, AC 1, AC 2)', () => {
  // THE NON-VACUITY ANCHOR COMES FIRST, for `copy.test.ts`'s reason: every assertion below reads a
  // parsed table, and a stale artefact path or a changed table shape yields NOTHING to match while
  // the suite still reports green. Both artefacts are proved present and parsed, and the row
  // parser is proved general by finding a row this file never otherwise reads.
  it('parsed both artefacts, and the row parser is general', () => {
    expect(EXPERIENCE.length).toBeGreaterThan(1000)
    expect(DESIGN.length).toBeGreaterThan(1000)
    expect(rowsFor('Unknown card in a view')).toHaveLength(1)
    // The label really is written twice — the property `rowsFor` exists for. If the artefact ever
    // merges them, the two lookups below must be re-pointed rather than silently reading one cell.
    expect(rowsFor(ROW_LABEL)).toHaveLength(2)
  })

  it('ships the sentence BYTE-FOR-BYTE, em dash and trailing period included', () => {
    // Byte-for-byte against the quoted value, not `toContain` and not a normalised compare: "This
    // deck is empty - ask…" (hyphen), "…add cards" (no period) and "This Deck Is Empty" are all
    // plausible edits that read fine in a diff, and each breaks either UX-DR33's voice or the
    // artefact contract. The artefact is the authority; the constant is what ships; this is the
    // only line where the two meet.
    const quoted = /In-grid line:\s*"([^"]*)"/.exec(rowWith(ROW_LABEL, 'In-grid line:'))

    expect(quoted, 'no quoted "In-grid line:" in the Voice and Tone row').not.toBeNull()
    expect(EMPTY_DECK_LINE).toBe(quoted?.[1])

    // NON-VACUITY for the comparison above: an import that resolved to `undefined` would match an
    // equally-undefined capture group if the regex ever stopped firing. Both sides are proved
    // independently, and the dash is pinned by CODEPOINT because U+2014, U+2013 and U+002D are
    // visually near-identical in a terminal diff and only one of them is the artefact's.
    expect(typeof EMPTY_DECK_LINE).toBe('string')
    expect(EMPTY_DECK_LINE.length).toBeGreaterThan(20)
    expect(EMPTY_DECK_LINE).toContain('—')
    expect(EMPTY_DECK_LINE).not.toContain('–')
    expect(EMPTY_DECK_LINE.endsWith('.')).toBe(true)
  })

  it('carries the "no panel, no error styling" posture the treatment is built on', () => {
    // The rest of the Voice and Tone cell is WHY the line is a bare `<p>` in the grid panel rather
    // than a `StatePanel`. If the artefact ever changed its mind, the DESIGN.md amendment below
    // and `CardGrid.tsx`'s branch would both be wrong and this is where it surfaces.
    const cell = rowWith(ROW_LABEL, 'In-grid line:')
    expect(cell).toContain('No panel, no error styling')
    expect(cell).toContain('Deck name and header render normally')
  })

  it('names EXACTLY three panels to hide — and the deck list is not one of them', () => {
    // THE ARTEFACT GAP, PINNED RATHER THAN DESCRIBED (AC 13, Q5, Q6). Both rows enumerate the
    // curve, the colour distribution and the format check. Neither mentions the DECK LIST or the
    // CARD DETAIL panel, while UX-DR20 separately says the detail panel is "never empty while a
    // deck is loaded" — and an empty deck is a loaded deck. That contradiction is recorded in
    // `deferred-work.md` as an artefact defect rather than repaired by inventing copy, and this
    // assertion is what makes the *silence* itself a fixed point: the day someone adds a fourth
    // panel to either sentence, this test goes red and the ruling gets re-opened deliberately.
    // Length asserted HERE, not only in the anchor test above: a filtered or skipped anchor
    // would leave this loop iterating an empty list and passing over nothing (code review
    // 2026-08-07 — each loop test carries its own non-vacuity).
    const cells = rowsFor(ROW_LABEL)
    expect(cells).toHaveLength(2)
    for (const cell of cells) {
      expect(cell.toLowerCase()).toContain('curve')
      expect(cell.toLowerCase()).toContain('format check')
      expect(cell.toLowerCase()).toMatch(/colou?r distribution/)
      expect(cell.toLowerCase()).not.toContain('deck list')
      expect(cell.toLowerCase()).not.toContain('card detail')
    }
    // Non-vacuity for the two negatives: the same artefact DOES write both phrases elsewhere, so
    // "absent here" is a fact about these rows rather than about a phrase nobody ever uses.
    expect(EXPERIENCE.toLowerCase()).toContain('deck list')
    expect(EXPERIENCE.toLowerCase()).toContain('card detail')
  })

  it('is invisible to copy.test.ts by structure, which is why this file exists', () => {
    // Measured with `copy.test.ts`'s own selector rather than claimed. `copy.test.ts:114` and
    // `copy-tails.test.ts` are both pinned at 6 rows; this row is neither `Headline:` nor `Body:`
    // shape, so it is invisible to them and those pins do not move. Rewording it into that shape
    // would move both pins AND put an empty deck into the state-panel vocabulary — which is
    // exactly what EXPERIENCE.md's "no panel" clause forbids.
    // The same in-test length pin as the enumeration test above, for the same reason: two
    // negative assertions over an empty list are the quietest possible green.
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

describe('DESIGN.md specifies the empty-deck treatment (c4-12, AC 26)', () => {
  /**
   * The frontmatter block, as raw text.
   *
   * Read as TEXT and not through a YAML parse, deliberately: the block's own reason is written in
   * `#` comments that a parse would discard, and it is those comments that record WHY the
   * treatment spends no length of its own. A gate that read only the values could not tell an
   * amendment from an amendment-with-its-reason, which is the difference the c4-7/c4-9/c4-10
   * amendment style exists to make.
   *
   * ⚠️ `\r?\n` at every line break, not `\n`. **The UX artefacts are CRLF** (measured — 485 of 485
   * line endings), so an `\n`-only anchor captures the empty string and every assertion below then
   * passes over nothing while reporting green. That is this epic's coverage-that-reads-as-coverage
   * class arriving in a NEW guard, and it was caught here only by the non-vacuity anchor being
   * written first and failing.
   */
  const block = /\r?\n {2}empty-deck-line:\r?\n([\s\S]*?)\r?\n {2}\w[\w-]*:/.exec(DESIGN)?.[1] ?? ''

  it('carries a components.empty-deck-line block with its reason inline', () => {
    // NON-VACUITY: the regex genuinely captured a block rather than an empty string, and it
    // stopped at the NEXT frontmatter key rather than running to the end of the file.
    expect(block.length).toBeGreaterThan(200)
    expect(block).not.toContain('card-placeholder:')

    expect(block).toContain("type: '{typography.body}'")
    expect(block).toContain("foreground: '{colors.text-secondary}'")
    // The reason, not just the values — the amendment style this file's peers established.
    expect(block).toContain('story c4-12')
    expect(block).toMatch(/spends no length of its own/i)
  })

  it('specifies the treatment in the Components prose, not only in the frontmatter', () => {
    // `shell.test.ts`'s px-literal gate reads the frontmatter; a HUMAN comparing the screen
    // against the artefact reads the Components section. AC 25 is answered from the prose, so the
    // amendment has to exist in both places or SC-5 is still unanswerable for this branch.
    const bullet = /^- \*\*Empty deck line\*\*.*$/m.exec(DESIGN)?.[0] ?? ''
    expect(bullet.length).toBeGreaterThan(400)
    expect(bullet).toContain('{components.empty-deck-line.type}')
    expect(bullet).toContain('{components.empty-deck-line.foreground}')
    // The three decisions no artefact carried before this story, each of which the implementation
    // depends on: the `<ul>` is REPLACED, there is no panel of its own, and nothing is announced.
    expect(bullet).toContain('replaces')
    expect(bullet).toMatch(/no panel of its own/i)
    expect(bullet).toContain('aria-live')
  })

  it('still bans the off-scale literals the line therefore cannot spend', () => {
    // The reason `CardGrid.css`'s rule has no `px` in it at all. If this sentence ever leaves
    // DESIGN.md, "spends no length of its own" stops being a consequence of the scale and becomes
    // an unexplained preference.
    expect(DESIGN).toContain('**Every value in the UI comes from this scale**')
  })
})
