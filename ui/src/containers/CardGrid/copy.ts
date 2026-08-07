/**
 * The one sentence this container authors (story c4-12, AC 1, AC 2, UX-DR33, UX-DR30).
 *
 * **NO IMPORTS, and that is load-bearing rather than incidental.** `tests/` belongs to the
 * `nodenext` TypeScript project and `src/` to the `bundler` one, so a `ui/tests` file may import
 * an app module only if that module is itself import-free — measured at c3-9, where importing one
 * with extensionless relative imports produced twelve `TS2835` errors with `npm test` green
 * throughout. The same shape as every other `copy.ts` in the app, and the reason
 * `tests/empty-deck-copy.test.ts` can read this constant at all.
 */

/**
 * What a deck with zero cards on every board says in place of its grid (AC 1, AC 3).
 *
 * ==== IT IS TRANSCRIBED, NOT AUTHORED — AND THAT IS THE DISPOSITION OF A LEDGER ENTRY ====
 * `EXPERIENCE.md`'s *Voice and Tone* table is the source, and the string ships **byte for byte**:
 * em dash **U+2014** (not a hyphen, not an en dash), one trailing period, sentence case. It is
 * carried here rather than retyped, and `tests/empty-deck-copy.test.ts` parses that table cell and
 * compares, so a later tidy-up cannot drift it.
 *
 * Shipping the artefact's own words verbatim is a DELIBERATE discharge of
 * `deferred-work.md`'s permanently-open copy-guard entry, which names this story: the guard can
 * check that a sentence is *registered*, and it can check the banned characters, but *"a reviewer
 * of c2-10, c4-3, **c4-12** and c6-6 must READ the copy"* — no test can judge whether a sentence
 * is blameless, second-person and concrete. c4-3 discharged exactly that judgement by shipping
 * EXPERIENCE.md's own label rather than an improvement on it, and its disposition says *"c4-12 and
 * c6-6 owe the same reading."* This module pays that debt the same way. **The reading itself was
 * performed and recorded in the story's Debug Log (AC 6) — it is a human act, and the record of it
 * is the deliverable, not this comment.**
 *
 * ==== WHAT THE WORDS DO, AND WHY THE SECOND CLAUSE IS THE WHOLE POINT ===================
 * *"This deck is empty"* states the fact without blaming anyone for it, and *"ask your agent to
 * add cards"* is the concrete next action UX-DR30 requires of a calm state — in the second person,
 * naming the one mechanism that can actually change it. An empty deck is the **normal** state at
 * creation, not a failure: measured 2026-08-07, `DeckRepository.create_deck` inserts a deck and
 * writes no card at all, and `remove_card_from_deck` never deletes the deck it empties. So there
 * is no apology here, and there must not be one.
 *
 * ==== WHAT IT IS DELIBERATELY NOT ======================================================
 * **Not a state panel.** EXPERIENCE.md says *"No panel, no error styling"* and DESIGN.md's
 * `components.empty-deck-line` (added by this story) says the same: a plain line inside the
 * untitled grid panel, in `{typography.body}` `{colors.text-secondary}`, spending no length of
 * its own. A deck that exists and answers a plain 200 is not a system fault, and dressing it as
 * one would be the *"reads as a loading failure rather than as an absent feature"* mistake
 * DESIGN.md names by hand.
 *
 * **Not announced.** No `aria-live` anywhere near it (AC 14). `CardDetail`'s single polite region
 * remains the only one in the app; a panel-visibility change that announced itself would be the
 * fourth mechanism in this epic doing the same job.
 *
 * **Not about the sideboard.** A deck holding only sideboard cards is NOT empty and does not show
 * this line — see `deckIsEmpty`'s docstring in `src/state/deckGroups.ts`. Saying "This deck is
 * empty" over a deck with cards in it would be false copy, which is the one thing UX-DR33 cannot
 * tolerate from a sentence written by a predicate.
 */
export const EMPTY_DECK_LINE = 'This deck is empty — ask your agent to add cards.'
