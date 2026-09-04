/**
 * The one sentence this container authors (UX-DR33, UX-DR30).
 *
 * **NO IMPORTS, and that is load-bearing rather than incidental.** `tests/` belongs to the
 * `nodenext` TypeScript project and `src/` to the `bundler` one, so a `ui/tests` file may import
 * an app module only if that module is itself import-free — importing one with extensionless
 * relative imports produces `TS2835` errors that `npm test` does not see. The same shape as every
 * other `copy.ts` in the app, and the reason `tests/empty-deck-copy.test.ts` can read this
 * constant at all.
 */

/**
 * What a deck with zero cards on every board says in place of its grid.
 *
 * ==== IT IS TRANSCRIBED, NOT AUTHORED ====================================================
 * `EXPERIENCE.md`'s *Voice and Tone* table is the source, and the string ships **byte for byte**:
 * em dash **U+2014** (not a hyphen, not an en dash), one trailing period, sentence case. It is
 * carried here rather than retyped, and `tests/empty-deck-copy.test.ts` parses that table cell and
 * compares, so a later tidy-up cannot drift it.
 *
 * Shipping the artefact's own words verbatim, rather than an improvement on them, is deliberate:
 * the copy guard can check that a sentence is *registered* and can check the banned characters,
 * but no test can judge whether a sentence is blameless, second-person and concrete. That
 * judgement stays with the artefact, where a human reads it.
 *
 * ==== WHAT THE WORDS DO, AND WHY THE SECOND CLAUSE IS THE WHOLE POINT ===================
 * *"This deck is empty"* states the fact without blaming anyone for it, and *"ask your agent to
 * add cards"* is the concrete next action UX-DR30 requires of a calm state — in the second person,
 * naming the one mechanism that can actually change it. An empty deck is the **normal** state at
 * creation, not a failure: `DeckRepository.create_deck` inserts a deck and
 * writes no card at all, and `remove_card_from_deck` never deletes the deck it empties. So there
 * is no apology here, and there must not be one.
 *
 * ==== WHAT IT IS DELIBERATELY NOT ======================================================
 * **Not a state panel.** EXPERIENCE.md says *"No panel, no error styling"* and DESIGN.md's
 * `components.empty-deck-line` says the same: a plain line inside the
 * untitled grid panel, in `{typography.body}` `{colors.text-secondary}`, spending no length of
 * its own. A deck that exists and answers a plain 200 is not a system fault, and dressing it as
 * one would be the *"reads as a loading failure rather than as an absent feature"* mistake
 * DESIGN.md names by hand.
 *
 * **Not announced.** No `aria-live` anywhere near it: UX-DR45 caps the app's live regions, and
 * none of them is this line's.
 *
 * **Not about the sideboard.** A deck holding only sideboard cards is NOT empty and does not show
 * this line — see `deckIsEmpty`'s docstring in `src/state/deckGroups.ts`. Saying "This deck is
 * empty" over a deck with cards in it would be false copy, which is the one thing UX-DR33 cannot
 * tolerate from a sentence written by a predicate.
 */
export const EMPTY_DECK_LINE = 'This deck is empty — ask your agent to add cards.'
