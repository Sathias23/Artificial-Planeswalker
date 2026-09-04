/**
 * The one sentence this container authors (UX-DR33, UX-DR30, AD-7).
 *
 * **NO IMPORTS, and that is load-bearing rather than incidental.** `tests/` belongs to the
 * `nodenext` TypeScript project and `src/` to the `bundler` one, so a `ui/tests` file may import
 * an app module only if that module is itself import-free — importing one with extensionless
 * relative imports produces twelve `TS2835` errors with `npm test` green throughout. The same
 * shape as every other `copy.ts` in the app, and the reason
 * `tests/empty-push-copy.test.ts` can read these constants at all.
 *
 * It is also why {@link EMPTY_PUSH_NOUNS} is declared HERE rather than derived from the store's
 * `AGENT_VIEW_LABELS`: importing the store — even type-only — would give this module a relative
 * import and take the verbatim gate away. The two tables are kept from drifting by
 * `agentView.test.ts`, which lives in the `bundler` project and can import both.
 */

/**
 * The empty-push line, EXACTLY as `EXPERIENCE.md`'s *Voice and Tone* table writes it — including
 * the `{noun}` placeholder, which is why this is a template rather than a sentence.
 *
 * ==== IT IS TRANSCRIBED, NOT AUTHORED ====
 * The string ships **byte for byte**: em dash **U+2014** (not a hyphen, not an en dash), one
 * trailing period, sentence case. `tests/empty-push-copy.test.ts` parses that table cell and
 * compares, so a later tidy-up cannot drift it.
 *
 * Substituting the raw WIRE kind into a sentence produces *'The agent sent an empty
 * suggestions.'* — grammatically wrong, and worse for `tier_list` — so the artefact's cell
 * writes `{noun}` and names the four display nouns, and this module transcribes it. The
 * sentence is built around a possessive because "an empty {noun}" fails on the plural nouns
 * ("an empty card groups"); the possessive reads correctly for all four.
 */
export const EMPTY_PUSH_TEMPLATE =
  "The agent's {noun} came back empty. Nothing to show — ask it for another pass."

/**
 * The placeholder the display noun replaces. Named rather than inlined so the gate that compares
 * this module against the artefact and the function that substitutes cannot disagree about it.
 */
export const NOUN_PLACEHOLDER = '{noun}'

/**
 * The display noun per wire kind — the artefact's own list, and the nav's labels lowercased.
 *
 * EXPERIENCE.md's cell enumerates exactly these four ("suggestions", "swaps", "tier list",
 * "card groups"), and `tests/empty-push-copy.test.ts` gates this table against that
 * enumeration. Each value is also `AGENT_VIEW_LABELS[kind].toLowerCase()`, and
 * `agentView.test.ts` pins THAT identity from the store's side, so a fifth kind or a renamed
 * pill cannot leave this table behind. Declared here rather than derived
 * because this module must stay import-free (see the header).
 */
export const EMPTY_PUSH_NOUNS: Record<string, string> = {
  suggestions: 'suggestions',
  swaps: 'swaps',
  tier_list: 'tier list',
  groups: 'card groups',
}

/**
 * The line for one kind of push.
 *
 * A single `.replace()` of a literal (not a global regex): the template carries exactly one
 * placeholder, and the assertion that it does lives in `tests/empty-push-copy.test.ts` where the
 * artefact is the authority. A `String.replace` with a string pattern substitutes the FIRST match
 * only, which is the intended semantics here rather than a limitation worked around.
 *
 * ==== WHAT THE WORDS DO, AND WHY THE SECOND CLAUSE IS THE WHOLE POINT ===================
 * *"The agent's {noun} came back empty"* states the fact and blames nobody — an empty push is the
 * agent honestly reporting that it looked and found nothing, which `types.d.ts:1103-1105` calls
 * out as a first-class case (*"an empty `items` list is legal … so 'I looked and found nothing'
 * is expressible"*). *"ask it for another pass"* is the concrete next action UX-DR30 requires of
 * a calm state, in the second person, naming the one mechanism that can change it. There is no
 * apology, and there must not be one: this is not a failure of anything.
 *
 * Args:
 *   kind: The envelope's own `kind` — a closed wire literal, never user data. It selects the
 *     display noun from {@link EMPTY_PUSH_NOUNS}; a kind the table does not know (impossible
 *     while the dispatch switch is total, but this function refuses to render a hole) falls back
 *     to the wire literal itself — degraded rather than thrown.
 *
 * Returns:
 *   The artefact's sentence with the placeholder filled.
 */
export const emptyPushLine = (kind: string): string =>
  EMPTY_PUSH_TEMPLATE.replace(NOUN_PLACEHOLDER, EMPTY_PUSH_NOUNS[kind] ?? kind)
