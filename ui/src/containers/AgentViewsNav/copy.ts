/**
 * The agent-views nav's words (story c6-8, AC 1, AC 3; Q2 and Q5, Brad 2026-08-12).
 *
 * ================= WHAT IS HERE, AND WHAT IS DELIBERATELY NOT =========================
 *
 * Five strings since story 17.2 (the History pill's label and quiet sentence joined c6-8's
 * three), and the KIND pill labels are still NOT among them. `Suggestions` / `Swaps` / `Tier list` /
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

/**
 * The fifth pill's visible label (story 17.2, FR-18, the ruled 2026-08-22 session-history home).
 *
 * **Here and NOT in `AGENT_VIEW_LABELS`, and that is a boundary rather than an oversight.** The
 * state table owns one word per {@link AgentViewKind} because a kind's pill label and its view's
 * fallback title are the same word — but History is not a kind: it never pushes, it has no view
 * of its own and no fallback title to share, and keying it into that table would break the
 * `satisfies Record<AgentViewKind, string>` exhaustiveness gate AND make `PILL_ORDER` (derived
 * from the table's keys) grow a pill the enum does not name. So the word belongs to the one
 * container that renders it, which is this module's whole charter.
 *
 * Sentence case for the kind labels' reason: `{typography.label}` uppercases at render, and the
 * string a screen reader speaks is the stored one.
 */
export const HISTORY_LABEL = 'History'

/**
 * What the History pill says before the first push of ANY kind this session (story 17.2) —
 * transcribed from `EXPERIENCE.md`'s `History pill + popover` row, byte for byte, and gated
 * against it by `tests/agent-views-nav-copy.test.ts` exactly as {@link QUIET_TOOLTIP} is gated
 * against its row.
 *
 * Its OWN sentence rather than {@link QUIET_TOOLTIP}, because the two quiet states are
 * different claims: a kind pill is quiet about ONE kind ("your agent hasn't sent THIS yet")
 * while the History pill is quiet about the whole session — it activates on the first push of
 * any kind, so its sentence has to be about "anything". Same dual delivery as the kind pills
 * (Q2's ruling): a `title` for the pointer AND a visually-hidden `aria-describedby` target for
 * the accessibility tree, both carrying this one string.
 *
 * The apostrophe is the ASCII `'` (U+0027) and the dash is the em dash (U+2014) — the gate
 * compares bytes read from the artefact, so neither can drift whichever way it is re-typeset.
 */
export const HISTORY_QUIET_TOOLTIP =
  "Nothing to revisit yet — your agent hasn't sent anything this session."
