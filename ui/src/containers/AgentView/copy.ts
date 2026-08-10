/**
 * The agent view shell's words, and the ONLY place they live (story c6-5, AC 1; the mechanism
 * is decide-once ruling #1 of story c2-9).
 *
 * Two strings, both of them CHROME rather than prose: they name the surface and its dismissal
 * gesture, and neither is a sentence the app composes. They are here rather than inline for the
 * reason `copy-rules.test.ts` exists at all — a user-facing string in a component is a string
 * no gate can see — and `COPY_MODULES` carries this module's entry with that reason.
 *
 * ================= WHY THESE ARE NOT ASSERTED BYTE-FOR-BYTE AGAINST EXPERIENCE.md ======
 *
 * `tests/copy.test.ts` reads `EXPERIENCE.md` and pins the six state-panel bodies to the
 * artefact, because those are PROSE the UX artefact authors. These two are not in
 * `EXPERIENCE.md` at all: they are in `DESIGN.md`, as component chrome — the *"AGENT VIEW"
 * kicker* and the *"Close · esc"* nav pill of the agent-view shell (`DESIGN.md:471`,
 * `:451`). So the pin that holds them honest is this module's own test asserting the exact
 * bytes, plus the design artefact naming both in the shell's component row. Stating the
 * distinction here rather than leaving the absence of a verbatim gate to look like an
 * oversight.
 *
 * The one byte worth naming: the separator in {@link CLOSE_PILL_LABEL} is U+00B7 MIDDLE DOT
 * (` · `), spaced, exactly as `DESIGN.md` writes it — not a hyphen, not a bullet (U+2022) and
 * not an interpunct without its spaces. `AgentView.test.tsx` asserts the codepoint, because
 * "looks like a dot" is precisely the class of difference an eye scanning a diff waves through.
 */

/**
 * The accent kicker above the title — `DESIGN.md`'s *"'AGENT VIEW' kicker in {typography.micro}
 * {colors.accent}"*.
 *
 * Stored UPPERCASE rather than lowercased-and-transformed. The `font` shorthand carries no
 * `text-transform`, so `--type-micro` gets one declared beside it in `AgentView.css` — the
 * companion `token-usage.test.ts:484-520` derives from `DESIGN.md`'s own `textTransform:` key
 * and requires in the same rule block. That makes the CSS uppercase this string a second time,
 * which is a deliberate no-op: the artefact writes the kicker uppercase, a screen reader reads
 * the SOURCE rather than the rendered case, and some announce CSS-uppercased text letter by
 * letter. Both layers therefore say the same thing, and the DOM says it without help.
 */
export const AGENT_VIEW_KICKER = 'AGENT VIEW'

/**
 * The close control's label — `DESIGN.md`'s *"a 'Close · esc' nav pill right-aligned"*.
 *
 * The label names the keyboard gesture as well as the pointer one, which is why the pill is
 * the app's only control whose accessible name contains a key name: UX-DR23 asks the shell to
 * TEACH the Esc dismissal rather than leave it to be discovered, and the pill is the only
 * always-visible place it can say so.
 */
export const CLOSE_PILL_LABEL = 'Close · esc'
