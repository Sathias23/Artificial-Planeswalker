/**
 * The pin announcement does not ship without its artefact (story c4-5, AC 23, UX-DR45).
 *
 * ================= WHY A THIRD COPY GATE RATHER THAN AN EDIT TO ONE ====================
 *
 * `COPY_MODULES` in `tests/copy-rules.test.ts` states the rule this file makes true for one more
 * string: *"copy is gated against whatever wrote it"*. The state-panel copy is gated against
 * `EXPERIENCE.md` (`tests/copy.test.ts`), the attribution against `DESIGN.md`
 * (`tests/attribution.test.ts`), the unknown-card label against `EXPERIENCE.md` again
 * (`tests/unknown-card-copy.test.ts`) — three artefacts, three files, because each parses a
 * DIFFERENT shape out of a different document. This one parses a TEMPLATE with a hole in it out
 * of the epic, which none of the other three can express.
 *
 * ================= THE ARTEFACTS DISAGREE, AND THIS FILE IS WHERE THAT IS SETTLED ======
 *
 * The story asked for the trailing period to be DECIDED rather than assumed, and it turned out
 * to be a real fork:
 *
 *   `epics-companion-app.md` — **`"Pinned — {card name}"`**, stated twice, with no period.
 *   `EXPERIENCE.md:154` — *"…via a separate polite region: "Pinned — Adeline, Resplendent
 *   Cathar.""*, inside a prose sentence that itself ends at that point.
 *
 * **Ruled: no trailing period**, and the epic is therefore the artefact this file gates against.
 * Three grounds, all recorded in `src/containers/CardDetail/copy.ts` beside the constant: the
 * epic states a TEMPLATE and a template is the normative form of a string with a hole in it; the
 * EXPERIENCE.md full stop is indistinguishable from the terminator of the sentence carrying the
 * example, which a template has no such ambiguity about; and the announcement is a LABEL rather
 * than a sentence.
 *
 * The assertion below is deliberately BOTH halves — the shipped function reproduces the epic's
 * template exactly, AND the artefact still contains that template. Either one alone would let
 * the pair drift: a changed constant with no artefact check passes, and a changed artefact with
 * no constant check passes.
 *
 * ================= IT IS AN IMPORT, AND THAT IS THE ONE NON-OBVIOUS THING =============
 *
 * `tests/` is the `nodenext` TypeScript project and `src/` the `bundler` one, so importing an
 * app module with extensionless relative imports produces a `TS2835` cascade here — measured at
 * c3-9, twelve errors with `npm test` green throughout. `CardDetail/copy.ts` has **no imports at
 * all**, deliberately and for exactly this reason, which is the property that makes it
 * importable — the same property `copy.test.ts` and `unknown-card-copy.test.ts` rely on for the
 * two copy modules they import.
 *
 * ================= WHAT THIS FILE DOES **NOT** GATE, DECLARED =========================
 *
 * That the region announces AT ALL, that it announces ONCE, and that it is separate from the
 * panel — those are behaviour, and they are asserted where a render can be inspected
 * (`src/containers/CardDetail/CardDetail.test.tsx`). How a real screen reader PHRASES an em dash
 * is neither's: it is the epic manual-testing checklist's, and it is declared rather than
 * implied.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { PANEL_TITLE, UNPIN_LABEL, pinnedAnnouncement } from '../src/containers/CardDetail/copy.ts'

/**
 * The ONE place this path is written in this file. The other copy gates each keep their own
 * constant for their own artefact deliberately; the non-vacuity anchor below is what turns a
 * moved or renamed artefact into a named failure rather than a suite asserting nothing.
 */
const EPICS_MD = fileURLToPath(
  new URL('../../_bmad-output/planning-artifacts/epics-companion-app.md', import.meta.url),
)

const EXPERIENCE_MD = fileURLToPath(
  new URL(
    '../../_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md',
    import.meta.url,
  ),
)

const epic = readFileSync(EPICS_MD, 'utf8')
const experience = readFileSync(EXPERIENCE_MD, 'utf8')

/**
 * The epic with runs of whitespace collapsed — because ONE OF THE TWO STATEMENTS IS WRAPPED.
 *
 * Measured rather than anticipated: the first occurrence sits at `epics-companion-app.md:599`
 * and the prose wraps mid-template, so the raw file contains `Pinned — {card` then a newline
 * then `name}`. A raw scan finds one of the two and would have quietly turned the count
 * assertion below into a weaker claim than it reads as. A markdown artefact is hard-wrapped by
 * its author, so line breaks inside a quoted string are ordinary there and this collapse is the
 * honest reading rather than a loosening.
 */
const epicFlat = epic.replace(/\s+/g, ' ')

/** The template the epic states, with its placeholder intact. U+2014 EM DASH, from the artefact. */
const TEMPLATE = 'Pinned — {card name}'

describe('the pin announcement is the epic’s own template (AC 23, UX-DR45)', () => {
  it('is reading the artefacts, and they still say what this file is about (non-vacuity)', () => {
    // Every assertion below indexes into these two strings. A stale path would make both empty
    // and turn the whole file into a set of tautologies — the failure mode this project's
    // reviews have found in every guard they looked at.
    expect(epic.length).toBeGreaterThan(1000)
    expect(experience.length).toBeGreaterThan(1000)
    expect(epic).toContain('Story 4.5: Persistent card detail panel')
    expect(experience).toContain('The card detail panel = `role="region"` labeled "Card detail"')
  })

  it('states the template TWICE in the epic, which is what makes it the normative form', () => {
    // Not "appears somewhere" — the count is the argument. A string stated once beside a worked
    // example could be the example; a string stated twice, as a template, in two different
    // sections, is the contract.
    expect([...epicFlat.matchAll(/Pinned — \{card name\}/g)]).toHaveLength(2)
  })

  it('ships the template exactly, with the hole filled and nothing else changed', () => {
    // BYTE-FOR-BYTE, in both directions: the shipped function reproduces the artefact's template
    // with `{card name}` replaced, and the artefact still contains that template. Either check
    // alone lets the pair drift.
    const name = 'Adeline, Resplendent Cathar'
    expect(pinnedAnnouncement(name)).toBe(TEMPLATE.replace('{card name}', name))
    expect(epicFlat).toContain(TEMPLATE)
  })

  it('carries NO trailing period — the ruling, asserted so it is not "tidied" back in', () => {
    // The fork this file's header records. `EXPERIENCE.md`'s worked example has a full stop and
    // the epic's template does not; the template wins. Asserted as a property of the OUTPUT
    // rather than of the constant, so a period added to the template string fails here too.
    expect(pinnedAnnouncement('Black Lotus').endsWith('.')).toBe(false)
    expect(pinnedAnnouncement('Black Lotus')).toBe('Pinned — Black Lotus')
    // …and the disagreement is real rather than remembered: EXPERIENCE.md really does carry the
    // period, so this test documents a decision rather than a coincidence.
    expect(experience).toContain('"Pinned — Adeline, Resplendent Cathar."')
  })

  it('uses the EM DASH the artefacts use, not a hyphen', () => {
    // U+2014, asserted as a codepoint rather than as a glyph, for the reason c4-4 asserted its
    // multiplication sign that way: a font, an editor or a find-and-replace can make the three
    // dashes look identical in a diff.
    const dash = pinnedAnnouncement('X').slice('Pinned '.length, 'Pinned '.length + 1)
    expect(dash.codePointAt(0)).toBe(0x2014)
    expect(pinnedAnnouncement('X')).not.toContain('-')
  })

  it('names the panel with the string EXPERIENCE.md labels the region with (AC 26)', () => {
    // The skip-link target (gate finding H3/C2) and the region's accessible name are one string,
    // and it is the artefact's.
    expect(PANEL_TITLE).toBe('Card detail')
    expect(experience).toContain('labeled "Card detail"')
  })

  it('gives the unpin control a WORD, since no artefact gives it anything at all (Q3)', () => {
    // THE HOLE IN THE DESIGN CONTRACT, RECORDED AS A TEST. UX-DR20 requires the control —
    // "click the panel's unpin control to release" — and no artefact gives it a size, a glyph, a
    // position, a label or a token. So this string is authored by the STORY rather than read
    // from a document, and the honest thing a gate can assert is the shape of the decision: a
    // real word, and not a symbol that UX-DR7 would call a symbol-lookalike.
    expect(experience).toContain('unpin control')
    expect(UNPIN_LABEL).toBe('Unpin')
    expect(UNPIN_LABEL).toMatch(/^[A-Za-z]+$/)
  })
})
