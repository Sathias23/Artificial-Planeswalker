/**
 * The skip link's label does not ship without its artefacts (story c4-11, AC 1, UX-DR31).
 *
 * ================= THE FOURTH COPY GATE, AND THE FIRST WITH NOTHING TO SETTLE ==========
 *
 * `COPY_MODULES` states the rule this file makes true for one more string: *"copy is gated
 * against whatever wrote it"*. The three existing gates each parse a DIFFERENT shape out of a
 * different document — a state-panel table (`copy.test.ts`), a prose paragraph
 * (`attribution.test.ts`), a template with a hole in it (`pin-announcement-copy.test.ts`).
 *
 * This one is unusual for this epic in having **no fork to rule**. Every prior copy gate exists
 * partly because two artefacts disagreed; here **three artefacts agree byte for byte**, and that
 * agreement is itself what is asserted. A string all three carry identically is a string any one
 * of them could be quietly edited away from, and the panel would still render the old words with
 * every other guard green.
 *
 * ================= WHY ALL THREE, AND NOT THE ONE NEAREST TO HAND =====================
 *
 * `pin-announcement-copy.test.ts` gates against the epic ALONE, correctly — it had to choose,
 * because the two artefacts disagreed and one of them was ruled normative. Nothing is being
 * chosen here, so choosing one anyway would silently make the other two unguarded, and the next
 * story to edit DESIGN.md would find nothing objecting.
 *
 * ================= WHAT THIS FILE DOES **NOT** GATE, DECLARED =========================
 *
 * That the link is FIRST in the document, that it is hidden until focused, that activating it
 * moves focus — all behaviour, asserted where a render can be inspected
 * (`src/containers/SkipLink/SkipLink.test.tsx`, `src/App.test.tsx`). That the revealed chip is
 * legible at the window's top-left is the eye-check's, and no jsdom assertion can stand in for it.
 *
 * ================= IT IS AN IMPORT, AND THAT IS THE ONE NON-OBVIOUS THING =============
 *
 * `tests/` is the `nodenext` TypeScript project and `src/` the `bundler` one, so importing an app
 * module with extensionless relative imports produces a `TS2835` cascade here — measured at c3-9.
 * `SkipLink/copy.ts` has **no imports at all**, deliberately and for exactly this reason, and
 * `shell.test.ts`'s `CONTAINERS` entry records it as `imports: []` so an import added there turns
 * this file red rather than un-gating the copy quietly.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { SKIP_LINK_LABEL } from '../src/containers/SkipLink/copy.ts'

const ARTEFACTS = {
  epic: '../../_bmad-output/planning-artifacts/epics-companion-app.md',
  design:
    '../../_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md',
  experience:
    '../../_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md',
} as const

const sources = Object.fromEntries(
  Object.entries(ARTEFACTS).map(([name, rel]) => [
    name,
    readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8'),
  ]),
) as Record<keyof typeof ARTEFACTS, string>

/**
 * Runs of whitespace collapsed, for `pin-announcement-copy.test.ts`'s measured reason: a markdown
 * artefact is hard-wrapped by its author, so a quoted string can carry a newline in the middle of
 * it. A raw scan would find some occurrences and miss others, turning a count into a weaker claim
 * than it reads as.
 */
const flat = (s: string) => s.replace(/\s+/g, ' ')

describe('the skip link’s label is the artefacts’ own string (AC 1, UX-DR31)', () => {
  it('is reading all three artefacts (non-vacuity)', () => {
    // Every assertion below indexes into these strings. A stale path reads as an empty file, under
    // which every `includes` is false and every `not.toContain` is TRUE — so the half of this file
    // that asserts an absence would pass by looking at nothing. That is the exact
    // coverage-that-reads-as-coverage failure this epic has found in four consecutive stories.
    for (const [name, source] of Object.entries(sources)) {
      expect(source.length, `${name} artefact is empty or missing`).toBeGreaterThan(1000)
    }
    // …and each one is the document it is supposed to be, not merely a non-empty file.
    expect(sources.epic).toContain('UX-DR31')
    expect(sources.design).toContain('**Skip link**')
    expect(sources.experience).toContain('| Skip link |')
  })

  it('ships the exact string all three artefacts carry', () => {
    // The shipped constant, quoted. Not `expect(SKIP_LINK_LABEL).toBe(SKIP_LINK_LABEL)` — the
    // literal is written out here so that changing the constant fails against a value a reader
    // can see, rather than against itself.
    expect(SKIP_LINK_LABEL).toBe('Skip past the deck grid')

    // BOTH HALVES, deliberately, and `pin-announcement-copy.test.ts`'s reason applies unchanged:
    // a changed constant with no artefact check passes, and a changed artefact with no constant
    // check passes. Only the pair catches a drift in either direction.
    for (const [name, source] of Object.entries(sources)) {
      expect(flat(source), `${name} no longer carries the shipped label`).toContain(SKIP_LINK_LABEL)
    }
  })

  it('finds the three artefacts in AGREEMENT, which is the fact worth pinning', () => {
    // Every other copy gate in this repo exists because two artefacts disagreed and one was ruled
    // normative. This string is the exception, and the exception is the assertion: all three carry
    // it identically, so none of them needed to be chosen over the others.
    //
    // The near-misses are what would actually happen — a tidy-up sentence-casing the label, or a
    // story "improving" it to promise the footer it cannot reach. Asserted as absences so a future
    // edit to any one artefact reddens this file instead of silently splitting the three.
    //
    // ⚠️ TO c8-6, BY NAME: `deferred-work.md` costs and homes a SECOND link labelled exactly
    // "Skip to footer" as the ledgered repair for the 100-stops-still-remaining residue. If that
    // story ships it, the 'promises the footer' absence below reddens ON PURPOSE — it is not a
    // copy defect, it is this guard asking to be narrowed to the FIRST link's copy while the
    // second link gets its own pins. Extend this file; do not delete the assertion.
    for (const [name, source] of Object.entries(sources)) {
      const text = flat(source)
      expect(text, `${name} carries a title-cased variant`).not.toContain('Skip past the Deck Grid')
      expect(text, `${name} carries a sentence-terminated variant`).not.toContain(
        'Skip past the deck grid.',
      )
      expect(text, `${name} promises the footer`).not.toContain('Skip to footer')
      expect(text, `${name} promises the content`).not.toContain('Skip to main content')
    }
  })
})
