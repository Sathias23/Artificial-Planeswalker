/**
 * The words. This module is the ONLY place a state panel's user-facing prose lives, and every
 * byte of it is `EXPERIENCE.md`'s.
 *
 * WHY A MODULE AND NOT STRINGS IN THE COMPONENT. `ui/tests/copy.test.ts` reads `EXPERIENCE.md`
 * — the artefact itself, not a copy of it — and asserts every headline and body byte for byte,
 * exactly as `tests/tokens.test.ts` asserts the token layer against `DESIGN.md`. "Matches
 * verbatim, reviewed by eye" is the same claim as "the tokens match DESIGN.md, reviewed by
 * eye", and this repo already decided that one. A gate needs one address to point at; this is
 * it, and `tests/copy-rules.test.ts` additionally proves nothing user-facing escaped to
 * somewhere it could not see.
 *
 * ================= WHY THE BODY IS A LIST OF PARTS AND NOT A STRING =====================
 *
 * `EXPERIENCE.md` writes each state in TWO fields — `Headline:` and `Body:`. `DESIGN.md`'s
 * State panel renders THREE slots: headline, guidance body, and **the concrete next action on
 * its own line** in `--type-body-strong` `--accent`. There is no separately-written
 * next-action string anywhere in the design artefacts, so either the copy stops being verbatim
 * or the action line is carved out of the Body — and only the second keeps the copy verbatim.
 *
 * So: **split the Body at sentence boundaries and gate the split by concatenation, in SOURCE
 * order.** Each sentence is tagged with the slot it renders into;
 * re-joining the parts IN ORDER must reproduce `EXPERIENCE.md`'s Body exactly, which
 * `copy.test.ts` asserts per state. Nothing is written here that EXPERIENCE.md did not write —
 * the panel merely knows which sentence is the action.
 *
 * The list-of-parts shape (rather than two strings) is what makes that invariant hold for the
 * two states whose action is NOT the last sentence: `disconnected` reads
 * guidance / action / guidance in the artefact and renders guidance-then-action on screen.
 * Two strings could not recombine to source order without a third field recording it.
 *
 * TWO CONSEQUENCES, BOTH DELIBERATE:
 *
 *   The action line is OPTIONAL. `database-updating` has none, because there genuinely is no
 *   action — "Reads will resume automatically — nothing to do here" is the whole state, and
 *   inventing an action for it would be the one thing this module exists to prevent. A panel
 *   with no action line is a real state, not a defect (see `actionOf`).
 *
 *   The guidance may be EMPTY. `no-active-deck` is a single sentence and that sentence is the
 *   action, so its guidance is the empty string and the panel renders no guidance paragraph.
 *
 * ================= EVERY STATE IS IN THE ARTEFACT, INCLUDING THE LATE ONES ===============
 *
 * `internal-error` and `database-updating-stalled` were WRITTEN INTO `EXPERIENCE.md` rather
 * than authored here, because a panel whose copy lives only in TypeScript is a panel with no
 * contract. The verbatim gate covers all six with no special case.
 */

/**
 * The panel vocabulary. NOT the wire vocabulary — the mapping between the two is `states.ts`,
 * and they are not the same set in either direction.
 */
export type StateKey =
  | 'no-active-deck'
  | 'database-not-initialized'
  | 'database-updating'
  | 'database-updating-stalled'
  | 'disconnected'
  | 'internal-error'

/** Which of `DESIGN.md`'s two body slots a sentence renders into. */
export type CopyRole = 'guidance' | 'action'

export interface BodyPart {
  readonly role: CopyRole
  /** One sentence of `EXPERIENCE.md`'s Body, verbatim, in source order. */
  readonly text: string
}

export interface StateCopy {
  /**
   * The `EXPERIENCE.md` table row this copy came from, spelled exactly as the artefact spells
   * it. This is the JOIN KEY the verbatim gate uses: without it the gate would have to guess
   * which row belongs to which state, and a renamed row would silently drop from the check
   * instead of failing loudly.
   */
  readonly row: string
  readonly headline: string
  /** The Body, split into sentences in SOURCE order. See the header for why it is a list. */
  readonly body: readonly BodyPart[]
}

const guidance = (text: string): BodyPart => ({ role: 'guidance', text })
const action = (text: string): BodyPart => ({ role: 'action', text })

export const STATE_COPY: Record<StateKey, StateCopy> = {
  'no-active-deck': {
    row: 'No-active-deck',
    headline: 'No deck on the glass.',
    body: [
      action('Ask your agent to set an active deck — it will appear here the moment it does.'),
    ],
  },
  'database-not-initialized': {
    row: 'Database not initialized',
    headline: 'Card database not set up yet.',
    // Source order is action-then-guidance; the panel renders guidance-then-action. The
    // concatenation invariant is checked against SOURCE order, which is what keeps this a
    // split of the artefact rather than a rewrite of it.
    body: [
      action('In your agent session, ask it to initialize the database (`initialize_database`).'),
      guidance(
        "First build takes a few minutes — this page will come alive on its own when it's ready.",
      ),
    ],
  },
  'database-updating': {
    row: 'Database updating',
    headline: 'Card database is updating.',
    // NO ACTION PART, and that is the point of this state. It retries quietly (types.d.ts's
    // `database_unavailable`), so there is nothing for the user to do, and an accent line
    // reading "wait" would be chrome pretending to be help.
    body: [guidance('Reads will resume automatically — nothing to do here.')],
  },
  'database-updating-stalled': {
    row: 'Database updating, stalled',
    headline: 'Card database still updating.',
    // The corrupt-database case. A durably corrupt cards.db answers `database_unavailable`
    // forever, so the row above — "nothing to do here" — is FALSE for it, with no repair path.
    // The backend cannot tell 200ms of mid-import from a month of garbage; the distinguisher is
    // elapsed time on the CLIENT, and the polling layer owns the threshold and the switch.
    body: [
      guidance("Reads haven't resumed for a while."),
      action(
        'Check your agent session — if no import is running, ask it to rebuild the database (`initialize_database`).',
      ),
    ],
  },
  disconnected: {
    row: 'Disconnected / backend restarted',
    headline: 'Lost the companion backend.',
    // THREE parts, guidance / action / guidance — the state that makes the list-of-parts shape
    // necessary rather than merely tidy.
    body: [
      guidance('Check your terminal.'),
      action('If the backend restarted, it printed a fresh URL — open that.'),
      guidance("If it moved ports, this tab can't follow it automatically."),
    ],
  },
  'internal-error': {
    row: 'Internal error',
    headline: 'The companion hit a bug.',
    // AD-16's sixth reason token, homed HERE by name. Checked against UX-DR33 line by line:
    // second-person,
    // terminal-literate, names the command without apology, NEVER BLAMES (the companion hit
    // it — not you, and not "something"), concrete next action, no exclamation mark, no emoji.
    //
    // "Restart" is a MANUAL, deterministic action and deliberately not a retry: that is the
    // distinction `ui/src/api/types.d.ts` draws between this token and
    // `database_unavailable`, and it is a property of this panel rather than of the fetch layer.
    // See `states.ts` for the declaration the wiring is held to.
    body: [
      action('Restart the companion in your terminal (`artificial-planeswalker companion`).'),
      guidance("The traceback is in that terminal — it's what a bug report needs."),
    ],
  },
}

/**
 * The Body as `EXPERIENCE.md` wrote it: every part, in source order, joined by one space.
 *
 * This is the function the verbatim gate compares against the artefact, and it is exported
 * rather than inlined into the test so that the thing asserted is the thing the module can
 * produce — a test that re-implemented the join would be asserting its own arithmetic.
 */
export const bodyOf = (copy: StateCopy): string => copy.body.map((part) => part.text).join(' ')

/** The guidance sentences, in source order. `''` when the state's whole body is its action. */
export const guidanceOf = (copy: StateCopy): string =>
  copy.body
    .filter((part) => part.role === 'guidance')
    .map((part) => part.text)
    .join(' ')

/** The next-action line. `''` when the state honestly has no next action (see the header). */
export const actionOf = (copy: StateCopy): string =>
  copy.body
    .filter((part) => part.role === 'action')
    .map((part) => part.text)
    .join(' ')

/**
 * A copy string split on its own BACKTICK markup, so the command chip is DERIVED from the copy
 * rather than authored per state.
 *
 * Deriving the chip from the markup rather than hard-coding `initialize_database` is what lets a
 * state carrying a different command — `artificial-planeswalker companion` — need no bespoke
 * renderer, and what keeps any future copy from needing one either.
 *
 * ODD indices are the code runs, which is a property of `split` on a delimiter rather than an
 * assumption about the input: `'a `b` c'` yields `['a ', 'b', ' c']`. An UNPAIRED backtick
 * therefore leaves a trailing odd segment, which renders as a chip — accepted deliberately
 * over throwing, because the verbatim gate is what catches malformed copy and a panel that
 * renders nothing at all is strictly worse than one that renders an over-eager chip. A string
 * with NO backtick yields a single even segment and therefore no chip, without error.
 */
export const splitOnCode = (text: string): { readonly code: boolean; readonly text: string }[] =>
  text
    .split('`')
    .map((segment, index) => ({ code: index % 2 === 1, text: segment }))
    .filter((segment) => segment.text !== '')
