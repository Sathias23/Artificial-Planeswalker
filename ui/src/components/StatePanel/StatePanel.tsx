import { filled } from '../filled'
import { STATE_COPY, actionOf, guidanceOf, splitOnCode, type StateKey } from './copy'
import './StatePanel.css'

/**
 * StatePanel — the shared shell for every system state (story c2-9, UX-DR30, FR-22).
 *
 * PRESENTATION-ONLY, DELIBERATELY. It holds no state, calls no hook — not `useId`, not
 * `useEffect`, not anything — fetches nothing, imports no store, polls nothing and retries
 * nothing. `ui/tests/shell.test.ts` asserts that with an exhaustive import list, so the posture
 * is a gate rather than a convention. Which state to show is decided by **c3-9** (the wiring and
 * FR-22's self-transition), fed by **c4-1**'s fetch layer and store over **c3-1**'s endpoints;
 * the map from
 * wire token to panel is `states.ts`, and the retry contract each state is owed is
 * `RETRIES_QUIETLY` in that same file, written where c3-9 will read it.
 *
 * "EXACTLY ONE PANEL AT A TIME" IS THE CALLER'S, NOT THIS COMPONENT'S (AC 2). A
 * presentation-only panel cannot know about its siblings, and this is said here rather than
 * left for the next author so that nobody builds a state-panel registry to enforce it: there is
 * exactly one `left` slot in `AppShell`, and no manager. The right column, header nav and
 * footer stay functional around it because the shell composes them independently.
 *
 * THE SEMANTICS (AC 7, UX-DR44). `role="region"` with the headline as an `<h2>`, NAMED by
 * `aria-label`. `aria-labelledby` would need a generated id, `useId` is a banned hook, and a
 * primitive that reaches for one has changed category — the identical argument, and the
 * identical outcome, as `Panel`. The role is written EXPLICITLY rather than relying on a named
 * `<section>`'s implicit one, because that implicit mapping is conditional on the name
 * computing, and a region that quietly demotes to `generic` is exactly the kind of silent
 * degradation this epic keeps finding.
 *
 * AND NO `aria-live`, WHICH WOULD BE THE DEFECT (landmine 17). UX-DR45's live-region inventory
 * (EXPERIENCE.md:156) names three: the connection pill, the agent-view heading, and the pin
 * announcement. This panel is not among them, on purpose — it REPLACES the main surface, so the
 * focus and landmark change already carries it. A `role="region"` that were also `aria-live`
 * would re-announce the entire panel, headline, guidance, action and deck list, on every mount.
 *
 * NO ILLUSTRATION, NO ICON, NO RED FILL, NO EXCLAMATION MARK (AC 2, AC 6). Note that the ban on
 * illustration is a ban on the ELEMENT and not only on the styling: there is no `<img>`, no
 * `<svg>`, no icon font and no spinner in this file, and no `--negative`/`--caution` in its
 * stylesheet (gated in tests/token-usage.test.ts). The copy ban — no `!`, no emoji, no
 * "something went wrong" — is gated in tests/copy-rules.test.ts over `copy.ts`, which is the
 * only place this component's words live.
 */

/**
 * A DISCRIMINATED UNION, not a flat shape (Greptile round, 2026-07-30): EXPERIENCE.md attaches
 * a deck list to the no-active-deck row and to NO other, and a flat `decks` prop left future
 * wiring free to put deck names under database or internal-error copy. The constraint lives in
 * the TYPE and only there — the renderer below stays exactly as dumb as before, no runtime
 * policing, which keeps the posture: the component still does not check its caller any more
 * than it checks "exactly one panel". The prose contract just became a compile-time one.
 */
export type StatePanelProps =
  | {
      /**
       * Which system state is on the glass. The copy for it is `EXPERIENCE.md`'s, byte for
       * byte — see `copy.ts`, and `tests/copy.test.ts` for the gate that proves it.
       */
      state: 'no-active-deck'
      /**
       * Available deck names — the one state that carries them (AC 5). A PROP: `GET /api/decks`
       * ships as of **c3-1**, but **c4-2** owns calling it and there is no fetch layer yet.
       *
       * EMPTY IS THE COMMON CASE, NOT AN EDGE. A fresh install has no decks at all, so an empty
       * array renders NOTHING EXTRA — no empty `<ul>`, no rule under blank space. That decision
       * goes through `filled()` rather than truthiness, because `[]`, `' '`, `false` and a
       * one-shot iterable all render nothing while looking filled to a naive check; it cost
       * c2-6 two review rounds plus a Greptile round to settle and is not re-derived here.
       */
      decks?: readonly string[]
    }
  | {
      state: Exclude<StateKey, 'no-active-deck'>
      /** Never here: EXPERIENCE.md gives no other state a deck list. See the union's header. */
      decks?: never
    }

/**
 * One copy string, with its backticked runs rendered as command chips (AC 11).
 *
 * The chip is DERIVED from the copy's own markup rather than authored per state, which is what
 * let the two states c2-9 added need no bespoke renderer — and what will keep **c4-3's** copy
 * from needing one. A string with no backticks yields one plain segment and no chip, without
 * error. (Re-homed from c3-2 to c4-3, 2026-07-31: c3-2 ships no copy string and no renderer —
 * see `copy.ts` for the same correction.)
 *
 * Plain segments are returned as bare STRINGS, not wrapped in a `<span>` or a `Fragment`. React
 * requires no key for a string child, so this needs no `Fragment` value import — which keeps
 * this module's react import at zero and the exhaustive list in `shell.test.ts` that much
 * shorter. It also emits no element that exists only to satisfy a loop.
 */
const withCommandChips = (text: string) =>
  splitOnCode(text).map((segment, index) =>
    segment.code ? (
      <code className="state-panel-command" key={index}>
        {segment.text}
      </code>
    ) : (
      segment.text
    ),
  )

export function StatePanel({ state, decks }: StatePanelProps) {
  const copy = STATE_COPY[state]
  const guidance = guidanceOf(copy)
  const action = actionOf(copy)

  // PER-NAME emptiness is decided here, with `trim()` — `filled()` answers the whole-list
  // question and nothing about a string's own blankness (c2-8's AC 4 lesson, re-found by the
  // review of 2026-07-29): `['', 'Boros Aggro']` passes `filled()` whole yet would render an
  // empty, announced `<li>`. A blank name is not a deck; it renders nothing.
  const names = (decks ?? []).filter((name) => name.trim() !== '')

  return (
    <section className="state-panel" role="region" aria-label={copy.headline}>
      <h2 className="state-panel-headline">{copy.headline}</h2>

      {/* Both slots are CONDITIONAL, and both conditions are real states rather than defensive
          coding. `no-active-deck` is a single sentence which IS its action, so it has no
          guidance; `database-updating` retries quietly and has no next action at all, and
          rendering an empty accent paragraph for it would put a coloured blank line where the
          user is being told there is nothing to do. `copy.test.ts` pins both. */}
      {guidance === '' ? null : (
        <p className="state-panel-guidance">{withCommandChips(guidance)}</p>
      )}
      {action === '' ? null : <p className="state-panel-action">{withCommandChips(action)}</p>}

      {/* NON-CLICKABLE, by construction rather than by styling: `<li>` with a text child, no
          anchor, no button, no handler. The agent drives (NG1, UX-DR33), and
          `StatePanel.test.tsx` asserts it by the ABSENCE of `link` and `button` roles in the
          subtree — the only assertion that says what AC 5 actually means. A class name would
          have proved nothing.

          An EXPLICIT `role="list"` on the `<ul>` (17.5): the stylesheet now lays the names out as
          flex chips with `list-style: none`, and Safari/VoiceOver strips a list's implicit
          semantics exactly when it sees that combination — the "list, N items" announcement this
          panel relies on would vanish. The explicit role restores it; it is the element's own
          role, so nothing else in the accessibility tree changes. */}
      {filled(names) ? (
        <ul className="state-panel-decks" role="list">
          {/* INDEX keys, deliberately: nothing in the prop contract forbids two decks sharing a
              name (the names are user-authored, c3-1 delivers them as bare strings), and a
              name key would silently drop the second (review 2026-07-29). The list is static
              and non-interactive, which is the one case index keys are exactly right for. */}
          {names.map((name, index) => (
            <li key={index}>{name}</li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
