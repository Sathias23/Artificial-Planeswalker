/**
 * Every word the flip control authors (UX-DR15, UX-DR47).
 *
 * **One string, and it is the whole of it.** The card's name, its faces and its type lines are
 * DATA — they arrive from the wire and are deliberately not in this module, for the reason
 * `CardPlaceholder/copy.ts` and `CardDetail/copy.ts` both state about their own: a copy owner that
 * also held card names would make the claim `COPY_MODULES` exists to state meaningless.
 *
 * **NO IMPORTS, and that is load-bearing rather than incidental.** `tests/` belongs to the
 * `nodenext` TypeScript project and `src/` to the `bundler` one, so a `ui/tests` file may import
 * an app module only if that module is itself import-free — measured: importing one
 * with extensionless relative imports produced twelve `TS2835` errors with `npm test` green
 * throughout. This module stays import-free exactly as the other copy modules do.
 */

/**
 * The flip control's accessible name.
 *
 * ==== IT IS SPECIFIED NOWHERE, AND THIS IS THE DECISION ================================
 * DESIGN.md describes the control's material, its size, its position and its glyph, and gives it
 * no label at all. The superseded working mocks used the text character `⇄` (U+21C4) with
 * `aria-label="Flip card"` — so the label is the one piece of that mock that is precedent rather
 * than superseded, and it is kept verbatim. Voltglass moved the control to the top-left and asked
 * for a stroke glyph, which replaced the MARK and said nothing about the words.
 *
 * ==== IT IS STATIC, AND THAT IS DELIBERATE RATHER THAN A DEFAULT =======================
 * The obvious-looking alternative is a name that says which face is coming — *"Show Murkwater
 * Pathway"*. It is refused on two grounds, and the second is a gate rather than a preference:
 *
 *   A name that changes is a name a keyboard user cannot learn. `aria-pressed` carries the STATE
 *   (UX-DR45 lists the live regions and a flip is not among them), so the name is free to name
 *   the ACTION and stay put — which is what a toggle button is for.
 *
 *   A face name is card DATA, and this module is a COPY module. Interpolating a wire string into
 *   `aria-label` would put data into a read-aloud attribute, which is exactly what
 *   `tests/copy-rules.test.ts`'s attribute half collects: *"card data is not copy."*
 *
 * ==== TWO WORDS, SENTENCE CASE, NO PERIOD =============================================
 * A button label rather than a sentence, in the voice `UNPIN_LABEL` established:
 * the string here stays in its plain case and any uppercase is CSS, so the accessible name and
 * the clipboard both keep the readable word. It carries no period, because it names an action
 * rather than making a statement.
 */
export const FLIP_LABEL = 'Flip card'
