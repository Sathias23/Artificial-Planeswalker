/**
 * Every word the format check panel authors (story c4-10, AC 15, AC 16, AC 35, Q1, Q3, Q15).
 *
 * **NO IMPORTS, and that is load-bearing rather than incidental.** `tests/` belongs to the
 * `nodenext` TypeScript project and `src/` to the `bundler` one, so a `ui/tests` file may import
 * an app module only if that module is itself import-free — measured at c3-9, where importing one
 * with extensionless relative imports produced twelve `TS2835` errors with `npm test` green
 * throughout. `import type` does not help: `TS2835` is a RESOLUTION error raised against the
 * specifier, and it fires whether or not the import is erased at emit. So both maps below are
 * declared plainly here and held to their wire unions in `FormatCheck.tsx`, which has both halves
 * in scope — `CardPlaceholder`'s shape exactly, and `DeckList`'s before it.
 *
 * ================= WHAT IS COPY HERE, AND WHAT EMPHATICALLY IS NOT (Q15) ================
 *
 * **The six `detail` sentences are DATA.** They are authored by `src/logic/deck_validator.py` and
 * arrive over the wire exactly as a card name does — `Every card is legal in standard.`,
 * `'Pym Particles' is not legal in brawl.` — with card names, counts and format names all
 * interpolated by Python. Moving them here to make the module look complete would be the opposite
 * of what the copy guard is for: `COPY_MODULES` is a claim about where AUTHORED WORDS live, and a
 * module that also held the backend's sentences would make that claim meaningless (decide-once
 * rule 14, the argument `DeckList/copy.ts:25-31` makes verbatim about card names).
 *
 * The six LABELS below are copy, and the line is the same one `GROUP_LABELS` sits on: the wire
 * says `'copy_limit'`, a machine token, and **nothing anywhere on the wire says `'Copy limit'`**.
 * There is no label field in `FormatCheckRow`, in `DESIGN.md`, or in `EXPERIENCE.md`'s prose. An
 * author chose these words.
 */

/**
 * The panel's title, and therefore its `<section>`'s accessible name (AC 4).
 *
 * Sourced, not invented: `DESIGN.md:423` names the component *"Format check (the legality row)"*
 * and `:401` lists *"Format check"* among the composition reference's demonstrated components;
 * `EXPERIENCE.md:37`'s P0 table calls the surface *"Format check panel"*. The word "panel" is
 * dropped for `DECK_LIST_TITLE`'s reason — a `<section>` named "Format check panel" announces its
 * own kind twice to a screen-reader user, once from the name and once from the region role.
 *
 * Sentence case with no period, in the voice `DECK_LIST_TITLE`, `FLIP_LABEL` and `UNPIN_LABEL`
 * established: the string stays in its readable case and any uppercase is CSS, so the accessible
 * name and the clipboard both keep the word a person would say.
 */
export const FORMAT_CHECK_TITLE = 'Format check'

/**
 * The six row labels, keyed by the wire's `FormatCheckName` (Q3, AC 15).
 *
 * ================= THE MOCK SUPPLIES FIVE OF THE SIX, AND ONE OF THOSE IS WRONG =========
 *
 * Read out of the composition reference rather than remembered, because the story's own context
 * had it slightly wrong and the difference decides one of these entries. The mock's table is:
 *
 * ```js
 * {label: 'Standard',             value: 'legal',         tone: 'positive'},
 * {label: 'Maindeck size',        value: '60 / 60',       tone: 'positive'},
 * {label: 'Copy limit',           value: 'no violations', tone: 'positive'},
 * {label: 'Sideboard',            value: '15 / 15',       tone: 'positive'},
 * {label: 'Banned or restricted', value: 'none',          tone: 'positive'},
 * {label: 'Rotation exposure',    value: '11 cards',      tone: 'caution'}
 * ```
 *
 * **The first slot holds a FORMAT STRING, not a label.** That is unusable here for two reasons
 * and both are rulings elsewhere in this story: Q14 keeps every format string out of this panel's
 * own chrome (this report's `format` is the NORMALISED value while `DeckBadges` renders the
 * STORED one 24px away, and a label built from one of them would be the only place in the app
 * that invites the comparison), and a label that changed per deck would not be copy at all. So
 * `'Legality'` is authored from `EXPERIENCE.md:37`'s IA row — *"Legality, size, copy limit,
 * sideboard, banned, rotation exposure"* — and NOT spelled `'Format legality'`, because the panel
 * above it is already titled *Format check* and the word would be said twice.
 *
 * **`'Banned or restricted'` is a FALSE label and does not ship.** `deck_validator.py:433-452`
 * reports a `restricted` card through the **legality** row, deliberately and pinned
 * (`test_restricted_is_unchanged_by_the_banned_split`): `banned_card` splits off only for a
 * legality of exactly `'banned'`, and `restricted` falls through to the plain rule *"because a
 * restricted card is legal with a 1-copy limit, which this validator does not model"*. A row so
 * labelled could therefore never fire for a restricted card, in any format, ever. `'Banned cards'`
 * is what the row actually reports, and it matches the backend's own `_unanswerable` subject —
 * *"so banned cards could not be checked"* — so the label and the sentence beneath it agree.
 * `EXPERIENCE.md:37` carries the matching correction in this commit.
 *
 * The other four are the mock verbatim. Sentence case, no periods, `DECK_LIST_TITLE`'s voice;
 * uppercasing is not done here and is not done at all — unlike a group header, these labels are
 * `{typography.body}` (`DESIGN.md:423`) and stay in the case a person would read.
 *
 * ⚠️ **A note for whoever adds a seventh check.** `deck_validator.py` would have to grow a
 * `FormatCheckName` member, which regenerates `types.d.ts`, which widens the union, which makes
 * `EveryCheckHasALabel` in `FormatCheck.tsx` a `tsc` failure by name. That is the intended path:
 * the label is a decision with a diff, not a fallback to `undefined` beside a real badge.
 */
export const CHECK_LABELS = {
  legality: 'Legality',
  size: 'Maindeck size',
  copy_limit: 'Copy limit',
  sideboard: 'Sideboard',
  banned: 'Banned cards',
  rotation: 'Rotation exposure',
}

/**
 * What the badge SAYS, keyed by the wire's `FormatCheckStatus` (Q1, AC 16, AC 31).
 *
 * ================= WHY THE STATUS WORD, AND NOT THE MOCK'S SIX VALUES ==================
 *
 * The mock puts short derived values in this slot — `'60 / 60'`, `'no violations'`, `'11 cards'`,
 * `'none'`, `'legal'`, `'15 / 15'` — and **not one of them is on the wire**. Computing them means
 * re-deriving construction rules in TypeScript, which is precisely the fifth declared hole in
 * c3-3's own rule guard: `find_rule_violations`
 * (`tests/unit/companion/test_routes_format_check.py:844-1011`) enforces that `format_check`
 * reimplements no rule, and **declares in writing that it cannot see TypeScript**
 * (`ui/README.md:1149`). A `'no violations'` computed here would be a construction rule living
 * where no Python guard can reach it, disagreeing with the backend the first time either side
 * moved. **They do not ship, and this paragraph exists so the next reader does not re-propose
 * them.**
 *
 * The status word is the one short string the wire actually carries. Three consequences, all
 * deliberate:
 *
 *   1. **Nothing is derived.** The badge is a lookup on a field, and `deck_validator.py:475-482`
 *      says that field is *"domain vocabulary, not presentation: mapping these onto a visual tone
 *      is the consuming shell's job"* — which is exactly what this map and `TONE_FOR_STATUS` are,
 *      and nothing more.
 *   2. **Colour is never the sole carrier** (AC 31, UX-DR26/UX-DR29). The word rides beside the
 *      tone, so the row reads the same in greyscale — the rule those two decision records state
 *      for the tier letter and the connection dot, applied here.
 *   3. **It is never empty**, which is load-bearing: `Badge` renders `null` for empty content
 *      (*"a bordered, washed, empty pill — visible chrome announcing nothing"*), so a blank status
 *      word would silently drop the pill and leave a bare label row.
 *
 * Uppercase is CSS, not these strings: `Badge` is `{typography.label}`, whose
 * `text-transform: uppercase` is in `Badge.css`. Storing `'PASS'` here would uppercase twice
 * (harmless) while destroying the readable form for anyone reading the accessible name or copying
 * the text (not harmless) — `GROUP_LABELS`' rule, applied.
 *
 * ⚠️ **The honest cost, recorded rather than smoothed over: `Advisory` is a word many players will
 * not parse.** It is the backend's own vocabulary and it means *"this could not be answered"*
 * rather than *"this failed"* — a distinction the badge alone cannot make. That is why the
 * `detail` sentence renders beneath the label (Q2) instead of the row being a label and a pill:
 * the sentence is what says *"Rotation exposure cannot be checked: the local card data carries no
 * set release dates."*, and without it this word would be the whole message.
 */
export const STATUS_WORDS = {
  pass: 'Pass',
  advisory: 'Advisory',
  violation: 'Violation',
}
