/**
 * The agent-views nav's words, gated against the artefacts that authorise them (story c6-8,
 * AC 1, AC 3; Q2, Q5, Q6) — the c2-9 / c2-10 / c4-3 / c5-7 pattern.
 *
 * ================= WHY THIS FILE EXISTS FOR THREE STRINGS =============================
 *
 * One of them is TRANSCRIBED and two are AUTHORED, and the gate does a different job for each.
 *
 * {@link QUIET_TOOLTIP} is `EXPERIENCE.md:73`'s sentence, and the comparison is against BYTES
 * READ FROM THE FILE rather than a literal retyped here — which is not ceremony on this
 * particular string. Its apostrophe is the ASCII `'` (U+0027), while the story that specified
 * this work asserted in writing that it was the typographic U+2019, and a reader of the rendered
 * Markdown cannot tell the two apart. A gate written to a retyped literal would have pinned
 * whichever character the developer's editor produced, and agreed with itself forever. This one
 * cannot: if the artefact's character changes, the shipped string must change with it.
 *
 * {@link NAV_GROUP_LABEL} and {@link UNREAD_WORD} were authored at this story and written into
 * the same artefact row in the same commit (c5-7's precedent). For them the gate is a different
 * claim — not *"the code matches the spec"* but *"the spec was actually updated"*, which is the
 * half a story is most likely to skip.
 *
 * The four PILL LABELS are gated here too, by a different mechanism and for a reason worth
 * stating: they live in `src/state/agentView.ts` (one word per kind, one owner — c6-6's ruling),
 * and this file CANNOT IMPORT that module. `ui/tests` is the `nodenext` project and `src/` the
 * `bundler` one, so a test may import an app module only if that module has no relative imports
 * of its own — and the store imports `../api/schema` for the kind union. That is exactly why
 * every `copy.ts` in this repo carries `imports: []`. So the labels are read as SOURCE TEXT and
 * compared to the artefact's IA rows, which is a weaker gate than the byte comparisons above and
 * is labelled as such where it runs; the strings' RENDERED identity is pinned in
 * `AgentViewsNav.test.tsx`, which lives under `src/` and can import the store directly.
 *
 * The formatted push TIME is not copy at all: it is wire data through `Intl.DateTimeFormat`, and
 * a locale render has no bytes anybody could gate.
 *
 * This file reads SOURCES. Whether the rendered pill actually shows these strings is
 * `AgentViewsNav.test.tsx`'s and `App.test.tsx`'s, and whether the words are any GOOD is a human
 * reading recorded in the story's Debug Log — `copy-rules.test.ts`'s header is explicit that no
 * assertion can discharge that.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  HISTORY_LABEL,
  HISTORY_QUIET_TOOLTIP,
  NAV_GROUP_LABEL,
  QUIET_TOOLTIP,
  UNREAD_WORD,
} from '../src/containers/AgentViewsNav/copy.ts'

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

const ROW_LABEL = 'Nav pill, no push yet this session'

/** Every table cell written under *label*, in document order. */
const rowsFor = (label: string, raw: string = EXPERIENCE): string[] =>
  raw
    .split('\n')
    .filter((line) => line.startsWith('|'))
    .map((line) => line.split('|').map((cell) => cell.trim()))
    .filter((cells) => cells[1] === label)
    .map((cells) => cells.slice(2).join(' | '))

/** The nav pill's row, whole. */
const row = (): string => rowsFor(ROW_LABEL).join('\n')

describe('the gate is reading the real artefacts (non-vacuity)', () => {
  it('found both artefacts and the row', () => {
    // Every assertion below filters one of these. An empty read — a moved artefact, a renamed
    // table label — would make the whole file pass by finding nothing, which is the
    // coverage-that-reads-as-coverage failure this epic has now found in five consecutive
    // stories.
    expect(EXPERIENCE.length).toBeGreaterThan(1000)
    expect(DESIGN.length).toBeGreaterThan(1000)
    expect(rowsFor(ROW_LABEL).length).toBeGreaterThan(0)
  })

  it('is comparing three distinct strings, not one repeated', () => {
    expect(new Set([NAV_GROUP_LABEL, QUIET_TOOLTIP, UNREAD_WORD]).size).toBe(3)
  })

  it('would notice a string that is NOT in the row (the positive control)', () => {
    // The twin of every `toContain` below. Without it, a `row()` that returned the whole
    // artefact — a parser that stopped splitting on `|` — would satisfy all of them.
    expect(row()).not.toContain('Your agent has not sent this yet.')
    expect(row()).not.toContain('Agent view pills')
  })
})

describe('the transcribed string matches the artefact BYTE FOR BYTE (AC 1)', () => {
  it('quotes the quiet pill’s sentence exactly as EXPERIENCE.md writes it', () => {
    expect(row()).toContain(`"${QUIET_TOOLTIP}"`)
  })

  it('uses the artefact’s ASCII apostrophe, not the typographic one', () => {
    // THE ASSERTION THIS FILE EXISTS FOR, and it is pinned by CODEPOINT rather than by eye for
    // `AgentView/copy.ts`'s middle-dot reason: "looks like an apostrophe" is exactly the class
    // of difference a reader scanning a diff waves through. The story spec that commissioned
    // this work stated the artefact used U+2019; it uses U+0027, measured. If the artefact is
    // ever re-typeset with curly quotes, THIS test fails and the shipped string follows it —
    // which is the direction the dependency should run.
    expect(QUIET_TOOLTIP).toContain("'")
    expect(QUIET_TOOLTIP).not.toContain('’')
    expect(QUIET_TOOLTIP.codePointAt(QUIET_TOOLTIP.indexOf("'"))).toBe(0x27)
    // …and the artefact itself, so the two claims are about one character and not two.
    expect(row()).toContain("hasn't sent this yet.")
  })

  it('keeps the trailing period — it is a sentence, not a label', () => {
    expect(QUIET_TOOLTIP.endsWith('.')).toBe(true)
  })
})

describe('the authored strings were written into the artefact (AC 1, AC 3)', () => {
  it('records the group kicker', () => {
    expect(row()).toContain(`"${NAV_GROUP_LABEL}"`)
  })

  it('records the unread word', () => {
    expect(row()).toContain(`"${UNREAD_WORD}"`)
  })

  it('records WHY the tooltip is not hover-only — the clause the code must keep honouring', () => {
    // Q2 repaired a real contradiction between UX-DR28 (not focusable) and UX-DR39 (no
    // hover-only disclosure of unique information). The repair is only durable if the reason
    // is in the artefact, where the next reader of "just use a title" will meet it.
    expect(row()).toContain('UX-DR39')
    expect(row()).toContain('programmatic description')
  })

  it('records that the pill does NOT announce (UX-DR45)', () => {
    // The other thing a later story is most likely to "improve": an unread pill that speaks.
    expect(row()).toContain('UX-DR45')
    expect(row()).toContain('not announced')
  })
})

describe('the four pill labels are EXPERIENCE.md’s IA names (AC 1, AC 2)', () => {
  // Read as source text, not imported — see this file's header for why the import is impossible.
  // Weaker than the byte gates above, and deliberately so rather than accidentally: it proves
  // the four strings are declared in the one module that owns them and that the artefact names
  // the same four things. That the COMPONENT renders them is `AgentViewsNav.test.tsx`'s.
  const storeSource = readFileSync(
    fileURLToPath(new URL('../src/state/agentView.ts', import.meta.url)),
    'utf8',
  )

  it('is reading the store module (non-vacuity)', () => {
    expect(storeSource.length).toBeGreaterThan(1000)
    expect(storeSource).toContain('AGENT_VIEW_LABELS')
  })

  it.each([
    ['suggestions', 'Suggestions'],
    ['swaps', 'Swaps'],
    ['tier_list', 'Tier list'],
    ['groups', 'Card groups'],
  ])('%s is called "%s" in the store and named in the artefact', (kind, label) => {
    expect(storeSource).toContain(`${kind}: '${label}'`)
    // `EXPERIENCE.md:39-42` writes each as its own IA row, "Agent view — <name>".
    expect(rowsFor(`Agent view — ${label}`).length).toBeGreaterThan(0)
  })

  it('holds no SECOND copy of those words in the container’s copy module', () => {
    // The c6-6 ruling this story inherited: a kind's word has ONE owner. A copy.ts that grew its
    // own `Suggestions` would compile, render identically, and drift the first time Epic 9
    // renamed a view — which is the failure nothing else here would catch.
    const containerCopy = readFileSync(
      fileURLToPath(new URL('../src/containers/AgentViewsNav/copy.ts', import.meta.url)),
      'utf8',
    )
    for (const label of ['Suggestions', 'Swaps', 'Tier list', 'Card groups']) {
      expect(containerCopy).not.toContain(`'${label}'`)
      expect(containerCopy).not.toContain(`"${label}"`)
    }
  })
})

// =========================================================================================
// STORY 17.2 — the History pill + popover, on the same gate pattern
// =========================================================================================

const HISTORY_ROW_LABEL = 'History pill + popover'
const HISTORY_STATE_ROW_LABEL = 'History pill before the first push'

const historyRow = (): string => rowsFor(HISTORY_ROW_LABEL).join('\n')

describe('the History gate is reading the real artefact rows (non-vacuity, 17.2)', () => {
  it('found both rows', () => {
    expect(rowsFor(HISTORY_ROW_LABEL).length).toBeGreaterThan(0)
    expect(rowsFor(HISTORY_STATE_ROW_LABEL).length).toBeGreaterThan(0)
  })

  it('is comparing two distinct authored strings, neither shared with the kind pills', () => {
    expect(new Set([HISTORY_LABEL, HISTORY_QUIET_TOOLTIP, QUIET_TOOLTIP]).size).toBe(3)
  })

  it('would notice a string that is NOT in the row (the positive control)', () => {
    expect(historyRow()).not.toContain('Nothing to revisit yet - your agent')
    expect(historyRow()).not.toContain('"Session history"')
  })
})

describe('the History quiet sentence matches the artefact BYTE FOR BYTE (17.2)', () => {
  it('quotes the sentence exactly as the Component Patterns row writes it', () => {
    expect(historyRow()).toContain(`"${HISTORY_QUIET_TOOLTIP}"`)
  })

  it('uses the artefact’s ASCII apostrophe and em dash — pinned by codepoint', () => {
    // The c6-8 gate's exact concern, on the new sentence: "looks like an apostrophe" and
    // "looks like a dash" are the differences a diff reader waves through, and the artefact is
    // the authority in both directions.
    expect(HISTORY_QUIET_TOOLTIP.codePointAt(HISTORY_QUIET_TOOLTIP.indexOf("'"))).toBe(0x27)
    expect(HISTORY_QUIET_TOOLTIP).not.toContain('’')
    expect(HISTORY_QUIET_TOOLTIP.codePointAt(HISTORY_QUIET_TOOLTIP.indexOf('—'))).toBe(0x2014)
    expect(historyRow()).toContain("hasn't sent anything this session.")
  })

  it('keeps the trailing period — it is a sentence, not a label', () => {
    expect(HISTORY_QUIET_TOOLTIP.endsWith('.')).toBe(true)
  })

  it('is the sentence the STATE row points at rather than a second spelling', () => {
    // The State Patterns row defers to the Component Patterns row for the string ("see the
    // History pill + popover row"), so ONE artefact spelling exists and this file gates it once.
    expect(rowsFor(HISTORY_STATE_ROW_LABEL).join('\n')).toContain('History pill + popover')
  })
})

describe('the History pill label was written into the artefact (17.2)', () => {
  it('records the pill’s word', () => {
    expect(historyRow()).toContain(`"${HISTORY_LABEL}"`)
  })

  it('records the ordering ruling the store carries in code — by ts, never by id', () => {
    expect(historyRow()).toContain('ordered by envelope `ts` — never by `id`')
  })

  it('records the dual quiet mechanism, the kind pills’ Q2 pattern', () => {
    expect(historyRow()).toContain('disabled + pointer-tooltip + programmatic-description')
  })

  it('records that the pill never carries an unread dot', () => {
    expect(historyRow()).toContain('Never carries an unread dot')
  })
})

describe('DESIGN.md carries the history-popover block the CSS cites (17.2)', () => {
  it('names the component and its material tokens', () => {
    expect(DESIGN).toContain('history-popover:')
    expect(DESIGN).toContain("background: '{colors.surface-overlay}'")
    expect(DESIGN).toContain("shadow: '{components.elevation.glow}'")
    expect(DESIGN).toContain("radius: '{rounded.md}'")
  })

  it('carries the documented max-height literal the stylesheet cites', () => {
    // `shell.test.ts`'s geometry gate requires the 480px in AgentViewsNav.css to cite DESIGN.md;
    // this is the other half — the cited line really exists.
    expect(DESIGN).toContain('max-height: 480px')
  })

  it('specs the entry type roles, tabular time included', () => {
    expect(DESIGN).toContain("entry-kind-type: '{typography.label}'")
    expect(DESIGN).toContain("entry-title-type: '{typography.body}'")
    expect(DESIGN).toContain("entry-time-type: '{typography.numeric}'")
    expect(DESIGN).toContain("entry-time-foreground: '{colors.text-tertiary}'")
  })

  it('specs the enter as the glide pair — the opacity-only fade’s tokens', () => {
    expect(DESIGN).toContain("enter: '{components.motion.glide} {components.motion.ease-glide}'")
  })
})

describe('DESIGN.md carries the visual half of the same three states', () => {
  it('names the quiet foreground, the timestamp and the dot size as tokens', () => {
    // Task 1's amendment. Asserted here rather than trusted, because the CSS cites these token
    // names in comments and a citation to a line that does not exist is worse than none.
    expect(DESIGN).toContain('quiet-foreground:')
    expect(DESIGN).toContain('time-type:')
    expect(DESIGN).toContain('time-foreground:')
    expect(DESIGN).toContain('unread-dot-size:')
  })

  it('no longer specifies the off-scale padding the spacing section calls drift', () => {
    // The repair Brad's c6-5 Q4 ruling shipped on the close pill and this story wrote back into
    // the frontmatter. `7px 14px` is a stylelint build failure, not a preference — if it ever
    // returns to the block, the two halves of one spec have diverged again.
    expect(DESIGN).not.toContain("padding: '7px 14px'")
    expect(DESIGN).toContain("padding: '{spacing.2} {spacing.3}'")
  })
})
