/**
 * The state-panel copy is `EXPERIENCE.md` itself — the artefact, not a copy of it.
 *
 * This is `tests/tokens.test.ts`'s pattern applied to prose (story c2-9, AC 8, AC 9, AC 10).
 * That file reads `DESIGN.md`'s frontmatter and asserts the token layer against it, token by
 * token, for one reason: two spellings of one value is one value that will drift. Copy is the
 * same problem with a worse failure mode — a drifted token renders the wrong colour, a drifted
 * sentence tells the user to do the wrong thing — and the epic's own AC sets the bar at
 * "matches EXPERIENCE.md **verbatim**". A verbatim claim reviewed by eye is exactly the claim
 * this repo already decided not to accept for tokens.
 *
 * THREE THINGS ARE ASSERTED, and the third is the one that took a ruling:
 *
 *   1. Every state's HEADLINE is byte-for-byte the artefact's `Headline:`.
 *   2. Every state's BODY, re-joined from its parts IN SOURCE ORDER, is byte-for-byte the
 *      artefact's `Body:`. This is the invariant that makes the two-fields-into-three-slots
 *      split (Q3) a split of the artefact rather than a rewrite of it: a future edit to either
 *      half cannot drift, because their concatenation is checked against the source.
 *   3. The two sides cover the SAME SET of states. A row added to EXPERIENCE.md with no panel,
 *      or a panel whose row was renamed, fails here rather than quietly halving the check.
 *
 * THE NON-VACUITY ANCHOR COMES FIRST, for the reason tokens.test.ts gives about `{}`: every
 * assertion below indexes into a parsed table, and a stale path or a changed table heading
 * would yield an empty map over which every `for` loop asserts NOTHING while reporting green.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  STATE_COPY,
  bodyOf,
  actionOf,
  guidanceOf,
  splitOnCode,
  type StateKey,
} from '../src/components/StatePanel/copy.ts'

/**
 * The ONE place this path is written in this file. It carries a date because the UX artefacts
 * are exported per run; the anchor below turns a stale path into a loud, named failure rather
 * than a suite that asserts nothing. (tokens.test.ts pins the sibling `DESIGN.md` path for its
 * own contract and says the same thing about it — two contracts, two constants, deliberately.)
 */
const EXPERIENCE_MD = fileURLToPath(
  new URL(
    '../../_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md',
    import.meta.url,
  ),
)

interface ArtefactRow {
  headline: string
  body: string
}

/**
 * Every two-field copy row in the artefact, read as `row label -> { headline, body }`.
 *
 * WHAT SELECTS A ROW, and why it is not a line range. The scan walks the WHOLE FILE — not "the
 * Voice-and-Tone table", which an earlier version of this comment claimed and the code never
 * did (review 2026-07-29) — and a row is any table line that writes both a quoted `Headline:`
 * and a quoted `Body:`, which is precisely the two-field shape this gate is about. That is what
 * excludes the non-panel rows ("Unknown card in a view", "Empty push", "Image loading") without
 * a skip list, and it is also a stated consequence: a Headline+Body-shaped table line ANYWHERE
 * in EXPERIENCE.md enters this map, and quoting a real row verbatim elsewhere in the artefact
 * will fail the duplicate check below — loudly, naming the label — rather than silently
 * deciding which copy is the contract.
 *
 * TWO DECLARED CEILINGS, the way copy-rules.test.ts declares its residues:
 *
 *   A field cannot CONTAIN a double quote — the captures are `"([^"]*)"`, so an inner `"`
 *   truncates the read and the byte-for-byte assertion fails pointing at the copy module,
 *   which is the wrong culprit. If UX copy ever needs to quote something, this parser is the
 *   thing to extend, and this sentence is here so that failure is a lookup, not a hunt.
 *
 *   A duplicated row label fails HERE. `Map.set` would keep the last row and the size pin
 *   would still pass — the exact drift this gate exists to catch, hidden by the shape of Map.
 */
const readArtefact = (
  raw: string = readFileSync(EXPERIENCE_MD, 'utf8'),
): Map<string, ArtefactRow> => {
  const rows = new Map<string, ArtefactRow>()

  for (const line of raw.split(/\r?\n/)) {
    const cells = /^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|$/.exec(line)
    if (!cells) continue
    const headline = /Headline:\s*"([^"]*)"/.exec(cells[2])
    const body = /Body:\s*"([^"]*)"/.exec(cells[2])
    if (!headline || !body) continue
    if (rows.has(cells[1])) {
      throw new Error(
        `EXPERIENCE.md writes two copy rows labelled "${cells[1]}" — the gate cannot know ` +
          'which one is the contract. De-duplicate the artefact before trusting this suite.',
      )
    }
    rows.set(cells[1], { headline: headline[1], body: body[1] })
  }

  return rows
}

const artefact = readArtefact()
const stateKeys = Object.keys(STATE_COPY) as StateKey[]

describe('the state-panel copy is EXPERIENCE.md, byte for byte (AC 3, AC 8)', () => {
  it('parsed the artefact, and it is populated (non-vacuity)', () => {
    expect(
      artefact.size,
      `no two-field copy rows parsed out of ${EXPERIENCE_MD} — has the artefact moved, or did ` +
        'the Voice and Tone table change shape?',
    ).toBe(6)
    // And the module side: six panels, so neither loop below can pass by iterating nothing.
    expect(stateKeys).toHaveLength(6)
  })

  it('covers exactly the artefact rows — no panel without a row, no row without a panel', () => {
    // Set equality both ways. A seventh state added to EXPERIENCE.md with no panel written for
    // it fails here, which is the same failure `schema.test.ts` produces for a seventh reason
    // token: the vocabulary grew and something did not follow it.
    expect(new Set(stateKeys.map((key) => STATE_COPY[key].row))).toEqual(new Set(artefact.keys()))
  })

  it.each(stateKeys)('%s — the headline is the artefact headline', (key) => {
    const copy = STATE_COPY[key]
    expect(artefact.get(copy.row), `${copy.row} is not a row in EXPERIENCE.md`).toBeDefined()
    expect(copy.headline).toBe(artefact.get(copy.row)?.headline)
  })

  it('keeps every headline free of backticks — only the body slots feed the chip mechanism', () => {
    // The panel renders `copy.headline` RAW, into the `h2` and into `aria-label` — deliberately,
    // because a heading is a name, not furniture for a command chip. That is only safe while no
    // headline carries backtick markup, and nothing upstream forbade one (review 2026-07-29): a
    // future EXPERIENCE.md row with a backticked headline would pass the byte-for-byte gate and
    // show literal backticks on screen. This is the assertion that makes it fail here instead.
    for (const key of stateKeys) {
      expect(
        STATE_COPY[key].headline,
        `${key}'s headline carries backtick markup, which the headline slot does not render`,
      ).not.toContain('`')
    }
  })

  it('fails loudly on a duplicated artefact row label (the Map.set drift)', () => {
    // The firing half of the parser's duplicate check, fed inline the way the guard suites
    // feed their readers — a duplicated label must throw, not last-writer-win.
    const duplicated =
      '| Dup | Headline: "One." Body: "First." |\n| Dup | Headline: "One." Body: "Second." |'
    expect(() => readArtefact(duplicated)).toThrowError(/two copy rows labelled "Dup"/)
    // …and the silent half: two DIFFERENT labels parse as two rows.
    const distinct =
      '| A | Headline: "One." Body: "First." |\n| B | Headline: "Two." Body: "Second." |'
    expect(readArtefact(distinct).size).toBe(2)
  })

  it.each(stateKeys)('%s — the body parts recombine to the artefact body exactly (AC 9)', (key) => {
    const copy = STATE_COPY[key]
    expect(bodyOf(copy)).toBe(artefact.get(copy.row)?.body)
  })
})

describe('the split into DESIGN.md three slots preserves the two artefact fields (AC 9)', () => {
  it.each(stateKeys)('%s — guidance and action are drawn from the body and nothing else', (key) => {
    const copy = STATE_COPY[key]
    const body = bodyOf(copy)
    // Every rendered sentence is a substring of the artefact body: not merely "they re-join",
    // but "neither slot contains a word the artefact did not write". The join test above and
    // this one together leave no room for an invented sentence.
    for (const part of copy.body) expect(body).toContain(part.text)
    expect(guidanceOf(copy) === '' && actionOf(copy) === '').toBe(false)
  })

  it('gives every state at most one action line, and allows a state to have none', () => {
    for (const key of stateKeys) {
      expect(STATE_COPY[key].body.filter((part) => part.role === 'action').length).toBeLessThan(2)
    }
    // The state that has none, named rather than merely tolerated: `database-updating` retries
    // quietly, so there is no next action, and inventing one would be the lie this whole story
    // exists to prevent. If a later story gives it an action, THIS assertion is what makes that
    // a deliberate change rather than a drift.
    expect(actionOf(STATE_COPY['database-updating'])).toBe('')
    // And the state whose whole body IS its action, so the guidance slot is empty.
    expect(guidanceOf(STATE_COPY['no-active-deck'])).toBe('')
  })

  it('renders the action in the order the panel shows it, not the order the artefact reads', () => {
    // The two states whose action is NOT the last sentence — the reason the body is a list of
    // parts rather than two strings (Q3's accepted consequence, asserted so it stays accepted).
    const notInitialized = STATE_COPY['database-not-initialized']
    expect(notInitialized.body[0].role).toBe('action')
    expect(bodyOf(notInitialized).startsWith(actionOf(notInitialized))).toBe(true)

    const disconnected = STATE_COPY.disconnected
    expect(disconnected.body.map((part) => part.role)).toEqual(['guidance', 'action', 'guidance'])
  })
})

describe('the command chip is derived from the copy own backtick markup (AC 11)', () => {
  it('finds the commands the copy actually contains, and marks only those', () => {
    const segments = splitOnCode(actionOf(STATE_COPY['database-not-initialized']))
    expect(segments.filter((segment) => segment.code).map((segment) => segment.text)).toEqual([
      'initialize_database',
    ])
    // The state this story wrote, proving the derivation is a MECHANISM and not the one string
    // that happened to exist at 109a7d9 — a two-word command with a hyphen in it.
    expect(
      splitOnCode(actionOf(STATE_COPY['internal-error']))
        .filter((segment) => segment.code)
        .map((segment) => segment.text),
    ).toEqual(['artificial-planeswalker companion'])
  })

  it('renders no chip for copy with no backticks, without error', () => {
    const plain = splitOnCode(guidanceOf(STATE_COPY['database-updating']))
    expect(plain).toEqual([
      { code: false, text: 'Reads will resume automatically — nothing to do here.' },
    ])
    expect(splitOnCode('')).toEqual([])
  })

  it('loses no character of the copy to the split', () => {
    // The c2-8 tokeniser lesson: "never silently drops" is a property of the SHAPE, proved by
    // re-joining, not a claim about the delimiter table. Every state, both slots.
    for (const key of stateKeys) {
      const copy = STATE_COPY[key]
      for (const text of [guidanceOf(copy), actionOf(copy)]) {
        expect(
          splitOnCode(text)
            .map((segment) => segment.text)
            .join(''),
        ).toBe(text.replaceAll('`', ''))
      }
    }
  })
})
