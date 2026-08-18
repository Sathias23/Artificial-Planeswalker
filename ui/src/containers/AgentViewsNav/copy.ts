/**
 * The agent-views nav's words (story c6-8, AC 1, AC 3; Q2 and Q5, Brad 2026-08-12).
 *
 * ================= WHAT IS HERE, AND WHAT IS DELIBERATELY NOT =========================
 *
 * Three strings, and the PILL LABELS ARE NOT AMONG THEM. `Suggestions` / `Swaps` / `Tier list` /
 * `Card groups` live in `src/state/agentView.ts`'s `AGENT_VIEW_LABELS`, because c6-6's review
 * ruled that the word for a KIND has one owner and the state layer is it — a view's fallback
 * title and its pill label are the same word, and Epic 9's three view stories each need theirs
 * before their container exists. A copy module here holding a second copy of those four strings
 * is precisely the drift that ruling was made to prevent. What is left over is what belongs to
 * this container alone: the group's kicker, the quiet pill's sentence, and the word that keeps
 * the unread dot from carrying its meaning in colour alone.
 *
 * ================= ONE STRING IS TRANSCRIBED, TWO ARE AUTHORED ========================
 *
 * {@link QUIET_TOOLTIP} is `EXPERIENCE.md:73`'s, byte for byte, and `tests/agent-views-nav-
 * copy.test.ts` gates it against that row — the c2-9 / c2-10 / c4-3 / c5-7 pattern. The
 * artefact's apostrophe is the ASCII `'` (U+0027) and NOT the typographic U+2019 that a reader
 * of the rendered Markdown would assume; the gate compares bytes read from the file rather than
 * a retyped literal, so the two cannot drift whichever character the artefact settles on.
 *
 * {@link NAV_GROUP_LABEL} and {@link UNREAD_WORD} are AUTHORED here (Q5, Q6) and were written
 * into `EXPERIENCE.md`'s nav-pill row in the same commit, so the gate has an artefact to read
 * for them too — c5-7's precedent for copy that had no artefact until its story wrote one.
 *
 * `imports: []` for the settled `TS2835` reason: `ui/tests` is the `nodenext` project and `src/`
 * the `bundler` one, so a `ui/tests` file may import an app module only if that module has no
 * relative imports of its own. The copy gate imports this module directly to compare its strings
 * against the artefacts, so the import-freedom is load-bearing here rather than conventional.
 */

/**
 * The group's visible label, left of the pills (Q5, and the mock's kicker at
 * `Planeswalker Companion.dc.html:33-51`).
 *
 * **It exists because the group has no landmark.** UX-DR44 assigns the header nav none, and Q5
 * kept it that way — the pills open overlays, they do not navigate, so a `<nav>` would be a
 * promise about where a click leads. That leaves the four pills describing themselves and
 * nothing describing what they are collectively FOR, which on a cold open is four quiet words
 * with no context. The kicker is that context, in `{typography.micro}` `{colors.text-tertiary}`
 * — the same quiet register the pills' own timestamps use.
 *
 * Sentence case, not "AGENT VIEWS": the micro role uppercases at render, so the string a screen
 * reader speaks stays a phrase rather than an initialism.
 */
export const NAV_GROUP_LABEL = 'Agent views'

/**
 * What a pill says when its kind has never pushed this session (AC 1, UX-DR28, UX-DR33's ninth
 * state) — transcribed from `EXPERIENCE.md:73`.
 *
 * **It reaches assistive technology two ways, and that is Q2's ruling rather than belt-and-
 * braces.** The pill is `disabled`, because UX-DR28 says not focusable and UX-DR40's cold-open
 * enumeration ("this stop never exists") is load-bearing about it — so the copy cannot be
 * disclosed on focus, which is UX-DR39's usual remedy. Shipping it as a bare `title` would leave
 * exactly the hover-only disclosure UX-DR39 bans and the 2026-07-22 accessibility review already
 * called a violation once, on the connection pill. So it ships as BOTH: a `title` for the
 * pointer, and a visually-hidden element referenced by `aria-describedby` for the accessibility
 * tree, where a browse-mode reader meets the disabled button and is told why it is disabled.
 *
 * The residual is closed: the artefacts described this as *"tooltip"*, singular, and story 15.3
 * amended UX-DR28 on 2026-08-18 to name this dual mechanism. (Filed here as "Story 8.3" until
 * then — the story was `c8-3`, and `c8` renumbered to Epic 15, not Epic 8; Story 8.3 is a live,
 * unrelated story about port selection.)
 *
 * *"Your agent"* rather than *"the agent"* — the artefact's word, and the same second-person
 * register UX-DR33's voice rules ask for everywhere else on the glass.
 */
export const QUIET_TOOLTIP = "Your agent hasn't sent this yet."

/**
 * The word beside the unread dot, in the pill's accessible name and nowhere on the glass
 * (AC 3, Q6).
 *
 * **The dot never carries the state alone** — UX-DR29's rule, made when the connection pill's
 * dot was given `aria-hidden` and its words were put in text beside it. Here the dot is the only
 * visual difference between a read pill and an unread one, so without this word the entire
 * distinction is a colour, which is both a WCAG 1.4.1 failure and invisible to a screen reader.
 *
 * Lower case, because it is appended to a name that already has one: the pill computes as
 * *"Suggestions 14:32 unread"*, a phrase, not two sentences. And it is a WORD rather than a live
 * announcement — UX-DR45 enumerates exactly three live regions (the connection pill, the
 * agent-view heading, the pin region) and this pill is not one of them. It must be discoverable,
 * not spoken on arrival.
 */
export const UNREAD_WORD = 'unread'
