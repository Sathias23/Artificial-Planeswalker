/**
 * The deck-refetch announcement does not ship without its artefacts (story c7-5, UX-DR45).
 *
 * `pin-announcement-copy.test.ts`'s shape, one region over: `COPY_MODULES` states the rule —
 * *"copy is gated against whatever wrote it"* — and for this string TWO artefacts wrote it,
 * carrying the identical worked example: `EXPERIENCE.md`'s live-region row (*"Deck refetches
 * announce once per coalesced refetch, on completion: 'Deck updated — 62 cards'"*) and the
 * epic's Story 7.5 AC. So the gate is BOTH halves in both directions: the shipped builder
 * reproduces the artefacts' sentence, and the artefacts still contain it. Either alone lets the
 * pair drift.
 *
 * ================= WHAT IS DECIDED HERE, AND WHAT IS ONLY RECORDED ====================
 *
 * The SINGULAR is invented: no artefact states a one-card form, and `ManaCurve/copy.ts`'s
 * pluralisation (its `cards` noun singularises on the count being exactly 1) is the recorded
 * precedent this module follows in the open. The COUNT SEMANTICS are the story's Design-Notes
 * ruling made testable: the announced number is `mainboard_count + sideboard_count` — all cards
 * on the glass, equal to the sum of every group-header count by `deckGroups.ts`'s conservation
 * identity — so a sideboard-only mutation still moves it.
 *
 * ================= WHAT THIS FILE DOES **NOT** GATE, DECLARED =========================
 *
 * That the region announces AT ALL, exactly once per coalesced refetch, and only on the refetch
 * path — behaviour, asserted where a render can be inspected (`App.test.tsx`'s c7-5 describe)
 * and where the counter lives (`deck.test.ts`). How a real screen reader phrases the em dash is
 * the epic manual-testing checklist's.
 *
 * IT IS AN IMPORT, and that is the one non-obvious thing: `tests/` is the `nodenext` project
 * and `src/` the `bundler` one, so `DeckAnnouncer/copy.ts` ships with NO imports at all —
 * deliberately, which is the property that makes it importable here (the `CardDetail/copy.ts`
 * precedent, verbatim).
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { deckUpdatedAnnouncement } from '../src/containers/DeckAnnouncer/copy.ts'

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

/** The worked example both artefacts carry, U+2014 EM DASH included. */
const WORKED_EXAMPLE = 'Deck updated — 62 cards'

describe('the deck announcement is the artefacts’ own sentence (UX-DR45)', () => {
  it('is reading the artefacts, and they still say what this file is about (non-vacuity)', () => {
    // Every assertion below indexes into these two strings; a stale path would make both empty
    // and turn the file into tautologies — the failure mode every guard review here has found.
    expect(epic.length).toBeGreaterThan(1000)
    expect(experience.length).toBeGreaterThan(1000)
    expect(epic).toContain('Story 14.5')
    expect(experience).toContain('once per coalesced refetch')
  })

  it('ships the worked example byte-for-byte, and BOTH artefacts still carry it', () => {
    // Both directions, both artefacts: the builder reproduces the sentence, and the sentence is
    // still in the documents this file claims wrote it.
    expect(deckUpdatedAnnouncement(62, 0)).toBe(WORKED_EXAMPLE)
    expect(epic).toContain(WORKED_EXAMPLE)
    expect(experience).toContain(WORKED_EXAMPLE)
  })

  it('opens with the template prefix, spaced em dash and all', () => {
    // The prefix is the authored half of the sentence — everything before the data begins —
    // asserted byte-for-byte so a "tidied" hyphen or a dropped space cannot ship.
    expect(deckUpdatedAnnouncement(7, 0).startsWith('Deck updated — ')).toBe(true)
  })

  it('uses the EM DASH the artefacts use, not a hyphen — by codepoint', () => {
    // U+2014, asserted as a codepoint rather than a glyph, for the reason c4-4 asserted its
    // multiplication sign that way: a font, an editor or a find-and-replace can make the three
    // dashes look identical in a diff.
    const sentence = deckUpdatedAnnouncement(3, 0)
    const dash = sentence.slice('Deck updated '.length, 'Deck updated '.length + 1)
    expect(dash.codePointAt(0)).toBe(0x2014)
    expect(sentence).not.toContain('-')
  })

  it('singularises on exactly one card, and only there — the invented rule, in the open', () => {
    // "1 card" is INVENTED (no artefact states it); ManaCurve/copy.ts's count===1 rule is the
    // precedent. Zero keeps the plural — the honest sentence for a refetch that emptied a deck.
    expect(deckUpdatedAnnouncement(1, 0)).toBe('Deck updated — 1 card')
    expect(deckUpdatedAnnouncement(0, 1)).toBe('Deck updated — 1 card')
    expect(deckUpdatedAnnouncement(0, 0)).toBe('Deck updated — 0 cards')
    expect(deckUpdatedAnnouncement(2, 0)).toBe('Deck updated — 2 cards')
  })

  it('announces mainboard PLUS sideboard — all cards on the glass (Design Notes)', () => {
    // The count-semantics ruling: the number is the payload's two counts summed, so it equals
    // the sum of every group-header count (the conservation identity) and the two accessible
    // signals can never disagree — and a sideboard-only mutation still moves it.
    expect(deckUpdatedAnnouncement(101, 1)).toBe('Deck updated — 102 cards')
    expect(deckUpdatedAnnouncement(100, 2)).not.toBe(deckUpdatedAnnouncement(100, 1))
  })
})
