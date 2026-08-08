/**
 * The connection pill's words are EXPERIENCE.md's row, and the row is this story's own (c5-7, AC 12).
 *
 * ================= THIS GATE IS THE UNUSUAL ONE, AND THE DIFFERENCE MATTERS ============
 *
 * Every other copy gate in this repo checks a TRANSCRIPTION: `copy.test.ts` holds the state panels
 * to `EXPERIENCE.md`, `attribution.test.ts` holds the footer to `DESIGN.md`, `unknown-card-copy`
 * and `empty-deck-copy` do the same for their one sentence each. In all four the artefact came
 * first and the code copied it.
 *
 * **Here the code came first, because no artefact had the words at all.** `DESIGN.md:479` specifies
 * the pill's material — a dot, `{typography.micro}` text *"naming the state"*, the deck name — and
 * not one word of that text; `EXPERIENCE.md:97`'s *"live · reconnecting · backend gone"* is a
 * vocabulary for the spec's readers rather than copy for the glass. So story c5-7 authored the
 * strings (Q3, Brad 2026-08-08) **and wrote them into `EXPERIENCE.md`'s connection-pill row in the
 * same commit**, which is the c2-9/c3 *"the copy row ships with the component"* precedent.
 *
 * That makes this file's job the thing that precedent exists for: keeping the two from drifting
 * APART afterwards. A gate that only checked "the constant equals itself" would be worthless; what
 * is asserted is that every shipped string is quoted in the artefact row, and that the row's own
 * load-bearing clauses are still there to be honoured.
 *
 * ================= WHY THE ROW EXCLUDES ITSELF FROM `copy.test.ts` ====================
 *
 * That parser selects *"any table line that writes both a quoted `Headline:` and a quoted
 * `Body:`"* — the two-field shape a state PANEL has. The pill is not a panel and has neither
 * field, so it stays out of the six-row pin exactly as the `card_not_found` and empty-deck rows
 * do. The last test below proves that structurally rather than claiming it: tidying this row into
 * Headline/Body shape would move `copy.test.ts`'s pin off 6 AND put the pill in the state-panel
 * vocabulary, which is the one thing `socket.ts:150-166` says it must never join.
 *
 * **The constants are IMPORTED, not read as source**, which is available only because
 * `src/containers/ConnectionPill/copy.ts` has no relative imports of its own — the measured
 * `tsc -b` rule for this directory (`tests/**` is the `nodenext` project, `src/**` the `bundler`
 * one). Its own header says so; this file is what depends on it.
 *
 * ================= WHAT THIS FILE CANNOT SEE, DECLARED ================================
 *
 * It reads TEXT. Whether the sentences are *calm* and *blameless* is not statically decidable —
 * `copy-rules.test.ts`'s own header says so in writing (*"a reviewer must READ the copy; this file
 * will not have read it"*) — and the discharge is a human reading recorded in the story's Debug
 * Log, not an assertion here. The rendered pill is `ConnectionPill.test.tsx`'s and `App.test.tsx`'s.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  CONNECTION_WORDS,
  DECK_SEPARATOR,
  pillText,
} from '../src/containers/ConnectionPill/copy.ts'

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

const ROW_LABEL = 'Connection pill'

/** Every table cell written under *label*, in document order. */
const rowsFor = (label: string, raw: string = EXPERIENCE): string[] =>
  raw
    .split('\n')
    .filter((line) => line.startsWith('|'))
    .map((line) => line.split('|').map((cell) => cell.trim()))
    .filter((cells) => cells[1] === label)
    .map((cells) => cells.slice(2).join(' | '))

/** The row's whole text. Module-scoped: three describes below read it. */
const row = (): string => rowsFor(ROW_LABEL).join('\n')

describe('the gate is reading the real artefact (non-vacuity)', () => {
  it('found the artefacts and the row', () => {
    // Every assertion below filters one of these. An empty read — a moved artefact, a renamed
    // table label — would make the whole file pass by finding nothing, which is the
    // coverage-that-reads-as-coverage failure this epic has found in four consecutive stories.
    expect(EXPERIENCE.length).toBeGreaterThan(1000)
    expect(DESIGN.length).toBeGreaterThan(1000)
    expect(rowsFor(ROW_LABEL).length).toBeGreaterThan(0)
  })

  it('is comparing three distinct strings, not one repeated', () => {
    // If the words map collapsed — a copy-paste, a widened type erasing the literals — the
    // per-state assertions below would all check the same sentence and pass for the wrong reason.
    expect(new Set(Object.values(CONNECTION_WORDS)).size).toBe(3)
  })
})

describe('every shipped string is quoted in EXPERIENCE.md’s row (AC 12)', () => {
  it.each(Object.entries(CONNECTION_WORDS))(
    'the %s state’s words appear in the artefact verbatim',
    (_status, words) => {
      expect(row()).toContain(`"${words}"`)
    },
  )

  it('records the em-dash separator and a worked example of the joined form', () => {
    // The separator is the only authored character in the deck-name half, so it is gated as a
    // character AND through the builder — a change to `pillText`'s spacing would pass a bare
    // `includes('—')` and fail here.
    expect(DECK_SEPARATOR).toBe('—')
    expect(row()).toContain(pillText('live', 'Sultai Midrange'))
  })
})

describe('the row’s load-bearing clauses are still there to be honoured', () => {
  it('states that the deck name is OMITTED in the backend-gone state (Q3)', () => {
    // The asymmetry a later reader is most likely to "fix". It is a ruling: the Disconnected
    // panel owns the guidance and the pill owns the status.
    expect(row()).toMatch(/omitted in the backend-gone state/i)
  })

  it('states that no deck loaded means no placeholder', () => {
    expect(row()).toMatch(/no placeholder/i)
  })

  it('records WHY there is no ellipsis after "Reconnecting" — it is a motion decision', () => {
    // `tokens.css:305-312` bans a pulse repo-wide and names this component as the reason. A
    // trailing "…" is that same promise made in text, so the artefact carries the reason and not
    // just the string — otherwise the next author "improves" the copy and reopens the question.
    expect(row()).toMatch(/ellipsis/i)
    expect(CONNECTION_WORDS.reconnecting).not.toContain('…')
    expect(CONNECTION_WORDS.reconnecting).not.toMatch(/\.\.\./)
  })

  it('keeps the retrying-quietly note the Disconnected row refers to (AC 5)', () => {
    // The two rows are one contract: the Disconnected panel row ends "Retrying-quietly note in the
    // connection pill", and this is the note. `copy-tails.test.ts` holds the other end.
    expect(CONNECTION_WORDS.down).toContain('retrying quietly')
    expect(row()).toMatch(/retrying-quietly note/i)
  })

  it('is amended in DESIGN.md too — the deck name may not take the micro role', () => {
    // The typography split c4-3 and c4-10 both discovered the hard way, recorded in the file that
    // assigns the role rather than only in the stylesheet that works around it.
    const bullet = DESIGN.split('\n').find((line) => line.startsWith('- **Connection pill**'))
    expect(bullet).toBeDefined()
    expect(bullet).toMatch(/story c5-7/)
    expect(bullet).toMatch(/typography\.body/)
  })
})

describe('the row stays OUT of the state-panel vocabulary (structural)', () => {
  it('writes neither a quoted Headline: nor a quoted Body:', () => {
    // The assertion that fires if anyone tidies this row into panel shape. Doing so would move
    // `copy.test.ts`'s six-row pin AND enrol the pill in a vocabulary `socket.ts:150-166` keeps
    // deliberately separate — `connection` is not `panel`, and `disconnected` is a third word again.
    for (const cell of rowsFor(ROW_LABEL)) {
      expect(cell).not.toMatch(/Headline:\s*"/)
      expect(cell).not.toMatch(/Body:\s*"/)
    }
  })
})
