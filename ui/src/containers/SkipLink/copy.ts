/**
 * The one word this component authors (UX-DR31, UX-DR40).
 *
 * **NO IMPORTS, and that is load-bearing rather than incidental.** `tests/` belongs to the
 * `nodenext` TypeScript project and `src/` to the `bundler` one, so a `ui/tests` file may import
 * an app module only if that module is itself import-free — importing one with extensionless
 * relative imports produced twelve `TS2835` errors with `npm test` green throughout. The same
 * shape as every other `copy.ts` in the app.
 */

/**
 * The link's visible text, and therefore its accessible name (UX-DR31).
 *
 * ==== IT IS THE CANONICAL STRING, AND THREE ARTEFACTS CARRY IT IDENTICALLY ==============
 * `DESIGN.md:418`, `EXPERIENCE.md:100` and `epics-companion-app.md:506` all write
 * *"Skip past the deck grid"*, byte for byte. There is nothing to decide here: no artefact
 * disagrees with another, and no case, punctuation or wording decision was left
 * open. It is transcribed rather than authored, and `tests/copy-rules.test.ts` compares it against
 * the artefact so a later tidy-up cannot drift it.
 *
 * ==== WHAT THE WORDS PROMISE, AND WHAT THE LINK ACTUALLY DELIVERS ======================
 * *"past the deck grid"* is exactly what it does and deliberately no more. Activating it moves
 * focus to the card detail panel's `<h2>` — the top of the RIGHT column — which is past the grid
 * and past its flip controls. It is **not** "skip to the footer", and measurement is why the
 * distinction is worth keeping in the words: on the largest real deck the footer is still 101 Tab
 * stops away after using this link, because the deck list sits between the two and puts a
 * second focusable row on every card. A label promising the end of the page would be a label that
 * lies on 36 of 40 real decks.
 *
 * Sentence case, no trailing period, no ellipsis: it is a control's name, in the same voice as
 * `UNPIN_LABEL` and `FLIP_LABEL`.
 */
export const SKIP_LINK_LABEL = 'Skip past the deck grid'
