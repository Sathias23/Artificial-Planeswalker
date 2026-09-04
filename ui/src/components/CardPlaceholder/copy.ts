/**
 * The one authored sentence the card placeholder puts on screen (UX-DR22, UX-DR33).
 *
 * A DECLARED COPY MODULE: user-facing prose lives only in a module listed in `COPY_MODULES`
 * (tests/copy-rules.test.ts), and a component with a sentence in it adds an entry there rather
 * than inventing a second mechanism.
 *
 * ================= WHAT IS COPY HERE, AND WHAT IS EMPHATICALLY NOT =====================
 *
 * EXACTLY ONE STRING. The card NAME, the TYPE LINE, the mana COST and the truncated ID that the
 * placeholder also renders are **data** — they arrive as props, from the corpus, and no author
 * wrote them. Moving them here to make the module look complete would be the opposite of what the
 * copy guard is for: `COPY_MODULES` is a claim about where AUTHORED WORDS live, and a module that
 * also held card names would make that claim meaningless.
 *
 * ================= WHY IT IS A SEPARATE MODULE RATHER THAN A LITERAL IN THE TSX =========
 *
 * `DeckBadges.tsx` is the precedent for the other shape — the component itself joins
 * `COPY_MODULES` — and it is right there because its two words are structural fragments of the
 * badges. This string is different in kind: it is a **contract with an artefact**.
 * `EXPERIENCE.md`'s "Unknown card in a view" row spells it, `states.ts` routes `card_not_found` to
 * it, and `tests/unknown-card-copy.test.ts` holds the string to the artefact byte-for-byte. A
 * module with **no imports at all** is what lets that assertion be written: a `ui/tests/` file
 * may import an app module only if that module has no relative imports (the measured `tsc -b`
 * project-boundary rule), which is exactly why `StatePanel/copy.ts` is importable by
 * `copy.test.ts` and `states.ts` is not.
 *
 * So this file has no imports, permanently. Adding one would silently un-gate the copy.
 */

/**
 * The unknown-card placeholder's name-slot label, byte-for-byte from `EXPERIENCE.md`.
 *
 * *"Unknown card in a view — Placeholder label: `"Unknown card"` + truncated ID. No banner, no
 * apology — the rest of the view renders normally."*
 *
 * Sentence case, not title case, and not shouted: it is a label for a slot, not an error. UX-DR33
 * bans the exclamation mark and the blame; FR-13 bans the banner. The whole of the app's response
 * to a card it cannot name is these two words in one slot of an otherwise untouched view.
 */
export const UNKNOWN_CARD_LABEL = 'Unknown card'
