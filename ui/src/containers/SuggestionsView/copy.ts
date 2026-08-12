/**
 * The one sentence this container authors (story c6-6, AC 4, UX-DR33, UX-DR30, AD-7).
 *
 * **NO IMPORTS, and that is load-bearing rather than incidental.** `tests/` belongs to the
 * `nodenext` TypeScript project and `src/` to the `bundler` one, so a `ui/tests` file may import
 * an app module only if that module is itself import-free — measured at c3-9, where importing one
 * with extensionless relative imports produced twelve `TS2835` errors with `npm test` green
 * throughout. The same shape as every other `copy.ts` in the app, and the reason
 * `tests/empty-push-copy.test.ts` can read these constants at all.
 *
 * It is also why {@link emptyPushLine} takes a plain `string` rather than the store's
 * `AgentViewContent['kind']`: importing that union — even type-only — would give this module a
 * relative import and take the verbatim gate away. The caller passes `content.kind`, which is a
 * closed wire literal, and `SuggestionsView.tsx` is where the type is held.
 */

/**
 * The empty-push line, EXACTLY as `EXPERIENCE.md`'s *Voice and Tone* table writes it — including
 * the `{kind}` placeholder, which is why this is a template rather than a sentence.
 *
 * ==== IT IS TRANSCRIBED, NOT AUTHORED — AND THAT IS THE DISPOSITION OF A LEDGER ENTRY ====
 * The string ships **byte for byte**: em dash **U+2014** (not a hyphen, not an en dash), one
 * trailing period, sentence case. `tests/empty-push-copy.test.ts` parses that table cell and
 * compares, so a later tidy-up cannot drift it.
 *
 * Shipping the artefact's own words verbatim is the same discharge `c4-3` and `c4-12` made of
 * `deferred-work.md`'s permanently-open copy-guard entry, which names THIS STORY by name: the
 * guard can check that a sentence is registered and can check the banned characters, but *"a
 * reviewer of c2-10, c4-3, c4-12 and c6-6 must READ the copy"*. c4-12's disposition recorded that
 * *"c6-6 still owes it"*. **The reading was performed and recorded in the story's Debug Log — it
 * is a human act, and the record of it is the deliverable, not this comment.**
 *
 * ⚠️ ONE RESIDUE OF THE TRANSCRIPTION, DECLARED RATHER THAN QUIETLY REPAIRED. Substituting the
 * WIRE kind into an article-carrying template produces *"The agent sent an empty suggestions."* —
 * grammatically wrong, and worse for Epic 9's `tier_list`. The artefact writes `{kind}` and the
 * story's task list rules the substitution to be the wire kind, so that is what ships; inventing
 * a per-kind display noun ("suggestions list") would be authoring copy no artefact carries, one
 * story before the second kind that would need it. Carried to the ledger as an ARTEFACT defect
 * for the story that adds the second view kind, which is where the decision has two data points
 * instead of one.
 */
export const EMPTY_PUSH_TEMPLATE =
  'The agent sent an empty {kind}. Nothing to show — ask it for another pass.'

/**
 * The placeholder the wire kind replaces. Named rather than inlined so the gate that compares
 * this module against the artefact and the function that substitutes cannot disagree about it.
 */
export const KIND_PLACEHOLDER = '{kind}'

/**
 * The line for one kind of push.
 *
 * A single `.replace()` of a literal (not a global regex): the template carries exactly one
 * placeholder, and the assertion that it does lives in `tests/empty-push-copy.test.ts` where the
 * artefact is the authority. A `String.replace` with a string pattern substitutes the FIRST match
 * only, which is the intended semantics here rather than a limitation worked around.
 *
 * ==== WHAT THE WORDS DO, AND WHY THE SECOND CLAUSE IS THE WHOLE POINT ===================
 * *"The agent sent an empty {kind}"* states the fact and blames nobody — an empty push is the
 * agent honestly reporting that it looked and found nothing, which `types.d.ts:1103-1105` calls
 * out as a first-class case (*"an empty `items` list is legal … so 'I looked and found nothing'
 * is expressible"*). *"ask it for another pass"* is the concrete next action UX-DR30 requires of
 * a calm state, in the second person, naming the one mechanism that can change it. There is no
 * apology, and there must not be one: this is not a failure of anything.
 *
 * Args:
 *   kind: The envelope's own `kind` — a closed wire literal, never user data. It is the ONE
 *     thing this story interpolates into a user-facing string, and it is safe for exactly that
 *     reason (c6-4's echo-hygiene rule: nothing payload-sourced reaches the glass unbounded).
 *
 * Returns:
 *   The artefact's sentence with the placeholder filled.
 */
export const emptyPushLine = (kind: string): string =>
  EMPTY_PUSH_TEMPLATE.replace(KIND_PLACEHOLDER, kind)
