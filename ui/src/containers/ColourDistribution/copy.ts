/**
 * Every word the colour distribution panel authors.
 *
 * **NO IMPORTS, and that is load-bearing rather than incidental.** `tests/` belongs to the
 * `nodenext` TypeScript project and `src/` to the `bundler` one, so a `ui/tests` file may import
 * an app module only if that module is itself import-free — importing one with extensionless
 * relative imports produces `TS2835` errors with `npm test` green throughout. `TS2835` is a
 * RESOLUTION error raised against the specifier, so `import type` does not help. Every copy module
 * stays import-free for this reason; {@link COLOUR_LABELS}'s coupling to `ManaColour` is asserted
 * in `ColourDistribution.tsx`, which is `CardPlaceholder`'s and `DeckList`'s shape exactly.
 *
 * ================= WHAT IS COPY HERE, AND WHAT IS EMPHATICALLY NOT =====================
 *
 * The **counts** and the **percentages** are data: they are computed from the deck and no author
 * wrote them. The `%` sign, the word in `"12 pips"`, the panel's title, the figure's accessible
 * name and each colour's NAME are all authored, and they live here.
 *
 * The colour names sit on the copy side of that line for `GROUP_LABELS`'s reason, one axis over:
 * the wire says `'{W}'` and `parse.ts` says `'w'`; **nothing anywhere says `'White'`**. An author
 * chose the word, which makes it copy — and here it carries more weight than a label usually
 * does, because the legend's pip is DECORATIVE, so this word is the only route by which a colour
 * reaches a screen-reader user at all (UX-DR18's *"the legend is the accessible data path"*).
 *
 * ================= TWO WORD TABLES NOW SPELL THE SIX COLOURS, DELIBERATELY ============
 *
 * `parse.ts:208`'s `COLOUR_NAMES` (`w -> 'white'`, …) already exists — as a module-private
 * `const`, not an export, with `describeManaCost` as its only consumer. So the choice was never
 * "import or re-declare"; it was **re-declare, or export a second consumer's worth of parser
 * internals into a module that may not import anything anyway**. Re-declared, and the divergence
 * is stated rather than left silent:
 *
 *   - `describeManaCost`'s copy is **lowercase, inside a sentence** — *"2 generic, white or
 *     blue"* — and it is what a screen reader hears on a card's COST.
 *   - This copy is **capitalised and standalone**, a label in a legend column.
 *
 * They are different registers, so one list would have to be wrong somewhere. If they are ever
 * unified, the change is to export `COLOUR_NAMES` and case it at the call
 * site; that is written down here so the next reader finds a decision rather than a duplicate.
 * `{C}`'s label follows the token (`--mana-colorless`) and `describeManaCost` (`'colorless'`),
 * which is the same American spelling `DESIGN.md` uses throughout — see {@link COLOUR_LABELS}.
 */

/**
 * The panel's title, and therefore its `<section>`'s accessible name.
 *
 * **Sourced, not invented, and spelled the way the artefact spells it**: `DESIGN.md:408` names
 * this component **"Color distribution"** in the anatomy list, exactly as `DESIGN.md:407` names
 * "Mana curve" — the string `MANA_CURVE_TITLE` takes verbatim for the same reason.
 *
 * ⚠️ **The rendered word is American and the identifiers are British, on purpose.** The module,
 * the directory and the class prefix are all `colour`; the words on the glass are
 * `DESIGN.md`'s. That split is already shipped and load-bearing elsewhere: the token is
 * `--mana-colorless`, and `describeManaCost` speaks `"colorless"`. Renaming either half would
 * silently break a byte-comparison against an artefact, so both halves stay as they are and the
 * divergence is written down instead of discovered.
 *
 * The word "panel" is dropped because the element already IS one — a `<section>` named "Color
 * distribution panel" announces its own kind twice, once from the name and once from the region
 * role. Same reasoning, same shape, as `MANA_CURVE_TITLE` and `DECK_LIST_TITLE`.
 */
export const COLOUR_DISTRIBUTION_TITLE = 'Color distribution'

/**
 * The `<figure>`'s accessible name.
 *
 * A `<figure>` maps to role `figure` reliably only when it HAS a name, so this is not decoration:
 * without one some engines expose the element as a generic container, and the accessible
 * alternative loses the thing it is an alternative to.
 *
 * Deliberately NOT the same string as {@link COLOUR_DISTRIBUTION_TITLE}: the panel and the figure
 * are two nested named things, and giving them one name makes a screen-reader user hear it twice
 * with nothing to distinguish the region from the graphic inside it.
 */
export const CHART_LABEL = 'Color distribution chart'

/**
 * One word per colour — the legend's first column, and the ONLY route by which a colour reaches
 * a screen-reader user.
 *
 * Keys are `parse.ts`'s `ManaColour` letters; the coupling in BOTH directions is asserted in
 * `ColourDistribution.tsx`, which imports both halves (see this module's header for why it cannot
 * be asserted here). Both directions catch different mistakes: a SEVENTH colour added to the
 * parser with no label here would render an unlabelled segment, and a label written for a letter
 * the parser does not have is dead copy no render can reach.
 *
 * `'Colorless'` rather than `'Colourless'` — the token is `--mana-colorless`, `describeManaCost`
 * already speaks `"colorless"`, and `DESIGN.md` is American throughout. ⚠️ Measured: **zero `{C}`
 * symbols appear in any of the 40 real decks**, so this particular label ships untested against
 * real data and only `colours.test.ts` exercises it.
 */
export const COLOUR_LABELS = {
  w: 'White',
  u: 'Blue',
  b: 'Black',
  r: 'Red',
  g: 'Green',
  c: 'Colorless',
}

/**
 * The unit noun for a pip count — the word in `"12 pips"`.
 *
 * **The pluralisation is INVENTED**, and stated so here because the rule is in no artefact.
 * UX-DR18 asks for *"a legend of `ManaPip` + count + percentage"* and specifies no noun at all;
 * the bare number would be ambiguous beside a percentage on the same row, so a unit was chosen.
 * It singularises on the COUNT being 1 — `"1 pip"`, `"12 pips"` — which is the only condition
 * available, unlike the mana curve's `barName` where two nouns singularise on two different
 * things.
 *
 * A segment with a zero count never reaches this function: `coloursOf` omits it entirely.
 *
 * Args:
 *   count: The summed quantity of pips of one colour.
 *
 * Returns:
 *   The count and its noun, as one string.
 */
export const pipCount = (count: number): string => `${count} ${count === 1 ? 'pip' : 'pips'}`

/**
 * A whole-number percentage, with its sign.
 *
 * The NUMBER is data — `coloursOf` rounds it — and the `%` is authored, which is the copy/data
 * line this module's header draws and the reason this one-line builder exists rather than a
 * `+ '%'` at the call site.
 *
 * ⚠️ **These do not have to sum to 100**: three equal colours print `33% · 33% · 33%`. The
 * geometry is exact and independent of this number — see `colours.ts` for why forcing the printed
 * set to 100 would be the worse answer.
 *
 * Args:
 *   percent: A whole number, already rounded by the derivation.
 *
 * Returns:
 *   The percentage as rendered — `'33%'`, and `'100%'` rather than `'100.0%'` for the nine
 *   mono-colour decks in the corpus.
 */
export const percentLabel = (percent: number): string => `${percent}%`
