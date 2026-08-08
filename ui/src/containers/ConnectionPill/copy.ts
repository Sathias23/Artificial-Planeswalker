/**
 * The connection pill's words (story c5-7, AC 12; Q3, Brad 2026-08-08).
 *
 * ================= THESE STRINGS WERE SPECIFIED NOWHERE ================================
 *
 * `DESIGN.md:479` describes the pill's MATERIAL — a dot, `{typography.micro}` text "naming the
 * state", the active deck name — and gives not one word of that text. `EXPERIENCE.md:97` names the
 * three states as *"live (WS open) · reconnecting (backoff in progress) · backend gone (retries
 * exhausted)"*, which is a vocabulary for the SPEC's readers, not copy for the glass. So unlike
 * `StatePanel/copy.ts` (transcribed from EXPERIENCE.md) or `Footer/copy.ts` (transcribed from
 * DESIGN.md), this module **authors** its strings, and Q3 is where they were decided rather than
 * smuggled in as literals. The chosen strings were written into `EXPERIENCE.md`'s connection-pill
 * row in the same commit, and `tests/connection-pill-copy.test.ts` gates them against it — the
 * c2-9 / c2-10 / c4-3 precedent, applied to copy that had no artefact until this story wrote one.
 *
 * ================= WHY THESE WORDS, AGAINST UX-DR33's VOICE RULES ======================
 *
 *   **Calm, and never blaming.** *"Backend gone"* states a fact about a process; it does not say
 *   the user closed a terminal, and it does not say the app failed. No exclamation mark, no emoji,
 *   no "Oops", no "Error".
 *
 *   **No ellipsis, and that is a MOTION decision as much as a punctuation one.** *"Reconnecting…"*
 *   is the natural spelling and it implies an animation this pill is forbidden to have — UX-DR42
 *   and `tokens.css:305-312` ban a pulse repo-wide, *naming this component as the reason the ban
 *   exists*. A trailing "…" is that same promise made in text. The word alone is the whole claim.
 *
 *   **`down` carries the retrying-quietly note (AC 5), and it is TRUE rather than reassuring.**
 *   `EXPERIENCE.md:67`'s disconnected row ends *"Retrying-quietly note in the connection pill"* —
 *   the last clause of that row nothing mirrored, and `copy-tails.test.ts` deliberately asserted it
 *   to be unasserted until this story. It is honest because c5-6's loop genuinely keeps retrying
 *   behind the Disconnected panel forever: `RETRIES_QUIETLY.disconnected === true`, and `socket.ts`
 *   reads that map to decide whether to keep scheduling. If that entry ever flips, the note becomes
 *   a lie and `copy-tails.test.ts` fails — which is the point of mirroring it there.
 *
 * ================= WHAT IS DATA AND NOT COPY =========================================
 *
 * The **deck name** is data: it arrives from the wire through the deck slice and is never authored
 * here. {@link DECK_SEPARATOR} is the punctuation that joins them, and it is the only authored
 * character in that half. A copy module that also held deck names would make `COPY_MODULES`'
 * claim meaningless — the distinction `CardPlaceholder/copy.ts` and `DeckList/copy.ts` both draw.
 *
 * `imports: []` for the settled `TS2835` reason: `ui/tests` is the `nodenext` project and `src/`
 * the `bundler` one, so a `ui/tests` file may import an app module only if that module has no
 * relative imports of its own. `tests/connection-pill-copy.test.ts` imports this one directly to
 * compare the strings against `EXPERIENCE.md`, so the import-freedom is load-bearing here rather
 * than conventional.
 */

/**
 * The word each connection status is named by. **The dot never carries the state alone** (AC 4,
 * UX-DR29) — this map is the half that makes that true, and it is TOTAL over `ConnectionStatus`
 * rather than defaulted, so a fourth status added to the union has no entry and `tsc` says so.
 *
 * Keyed by the CODE's vocabulary (`'down'`), not the artefacts' (*"backend gone"*, *"disconnected"*)
 * — `socket.ts:150-166` and `systemState.ts:53-60` both record why those vocabularies are kept
 * apart, and the state-panel key `'disconnected'` is a third one again. The mapping from the key to
 * the words is exactly what this module is for.
 */
export const CONNECTION_WORDS = {
  live: 'Connected',
  reconnecting: 'Reconnecting',
  down: 'Backend gone — retrying quietly',
  // `as const` for `FormatCheck`'s measured reason: without it every value infers as `string` and
  // the totality assertions in the component become vacuously true.
} as const

/**
 * What joins the state word to the deck name. An EM DASH with spaces either side, the same
 * separator `EXPERIENCE.md` uses in its own copy rows ("Deck updated — 62 cards") and the
 * `down` string uses internally.
 */
export const DECK_SEPARATOR = '—'

/**
 * The pill's whole text, and therefore also its accessible name and the string its live region
 * announces (AC 4, AC 6, AC 10).
 *
 * ONE BUILDER, THREE CONSUMERS, and that is deliberate: the visible text, the button's accessible
 * name and the announcement must be the same sentence or a screen-reader user is told something
 * the screen does not say. The component renders the parts into separate elements for typography
 * (see `ConnectionPill.css` for why the deck name may not take the micro role) — this function is
 * what guarantees the three readings still agree.
 *
 * ⚠️ ONE MEASURED DIFFERENCE, RECORDED RATHER THAN HIDDEN: the DOM text and the announcement are
 * this string byte for byte, but the COMPUTED accessible name is `Connected—Sultai Midrange` —
 * the accname algorithm trims each contributing text node before joining, so the separator's
 * surrounding spaces do not survive it. The words and their order do, which is what a reader
 * hears (an em dash between words is voiced as a pause or not at all).
 * `ConnectionPill.test.tsx` pins both forms rather than asserting a sameness that is not true.
 *
 * `deckName === null` is the honest absence: **no placeholder and no "undefined"** (AC 6). A
 * pill with no deck loaded reads `Connected`, full stop.
 *
 * Args:
 *   status: The connection status.
 *   deckName: The active deck's name, or `null` when none is loaded — and also `null` in the
 *     `'down'` state, which is the CALLER's decision and is argued at the call site.
 *
 * Returns:
 *   The pill's text.
 */
export const pillText = (status: keyof typeof CONNECTION_WORDS, deckName: string | null): string =>
  deckName === null
    ? CONNECTION_WORDS[status]
    : `${CONNECTION_WORDS[status]} ${DECK_SEPARATOR} ${deckName}`
