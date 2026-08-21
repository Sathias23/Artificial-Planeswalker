import { useId } from 'react'

import type { AgentViewKind } from '../../api/schema'
import {
  AGENT_VIEW_LABELS,
  reopenAgentView,
  useAgentViewHasPush,
  useAgentViewPushTime,
  useAgentViewUnread,
} from '../../state/agentView'
import './AgentViewsNav.css'
import { NAV_GROUP_LABEL, QUIET_TOOLTIP, UNREAD_WORD } from './copy'
import { pushTimeLabel } from './pushTime'

/**
 * The agent-views nav — one pill per kind of thing the agent can put on the glass (story c6-8,
 * FR-18, UX-DR28, UX-DR33, UX-DR34, UX-DR37, UX-DR39, UX-DR40, UX-DR44, UX-DR45, UX-DR47,
 * `DESIGN.md:260-269`/`:522`, `EXPERIENCE.md:39-42`/`:73`/`:139-147`).
 *
 * It FILLS the header slot the shell has carried empty since c2-6 — `AppShell.tsx:200`'s
 * `slot(nav, 'Agent-view nav pills land here — c6-8.')` — via `App.tsx`'s `nav` prop. The
 * eleventh application of c2-9's displacement ruling: **`AppShell.tsx` is not edited**, the
 * placeholder string stays in the shell where `AppShell.test.tsx` asserts it against the
 * component's own props, and what changes is that nothing renders it any more.
 *
 * ================= IT IS GENERIC OVER THE ENUM, NOT OVER WHAT HAS A VIEW ==============
 *
 * Four pills always, keyed by {@link AgentViewKind} — the closed four-kind union derived in
 * `schema.ts`. Story 9.1's own acceptance criterion depends on it: *"the Swaps pill becomes
 * active automatically, because the nav is generic over the closed `kind` enum from Story
 * 5.1"*, which is only true if this file never mentions which kinds happen to be renderable
 * today. It does not. A fifth kind added on the Python side reaches {@link PILL_ORDER} through
 * the generator and grows a pill here with no edit.
 *
 * **The honest consequence, in the open (Q1, discharged in full at 16.3):** the genericness
 * paid off exactly as promised — `swaps` (16.1), `tier_list` (16.2) and `groups` (16.3) each
 * shipped their tool, dispatch arm and view, and each pill became reachable from the wire with
 * NO edit to this file, which is Q1's ruling proven three times over. All four kinds are now
 * delivered (the socket's dispatch holds no drop arm), so every pill can activate in
 * production. Quiet still means what UX-DR33 says and nothing less: "no push of this kind yet
 * THIS SESSION" — not a degraded state or a placeholder, but the named ninth state with its
 * own copy, and *"your agent hasn't sent this yet"* stays a true sentence about a session, no
 * longer about a tool.
 *
 * ================= WHAT IT IS NOT ====================================================
 *
 * **Not a `<nav>` landmark** (Q5). UX-DR44 enumerates the app's landmarks and this group is not
 * among them; the pills open overlays over the current page rather than navigating anywhere, so
 * the landmark would be a promise about where a click leads. {@link NAV_GROUP_LABEL} is what
 * gives the group its name instead — visibly, for everyone, rather than in an ARIA attribute
 * only some readers meet.
 *
 * **Not a live region** (UX-DR45, which authorises exactly three and none is here). A pill's job
 * is to be findable later, not to interrupt: the unread dot and the timestamp UPDATE, and
 * UX-DR43 is satisfied by their updating rather than by their announcing.
 *
 * **Not reachable while a view is open.** The scrim covers the header and the dialog traps Tab
 * (UX-DR38's one-level stack), so a pill click always starts from a closed view. That is why
 * {@link reopenAgentView} has no displacement branch and why nothing here handles the
 * open-over-open case: it cannot happen from this component, and the case that CAN happen (a
 * push of another kind arriving while a view is open) is the store's, in `openAgentView`.
 *
 * **Props-free**, like `ConnectionPill`: it reads the store itself rather than being handed
 * state by `App.tsx`, which keeps the root's job "where does this go" and not "what does it
 * say".
 */
export function AgentViewsNav() {
  return (
    <>
      {/* THE GROUP'S NAME, ON THE GLASS (Q5). A plain `<span>`, not a heading: a heading here
          would enter the document outline between the deck name and the panel titles and claim
          a structural rank this row does not have. The shell's `.app-shell-nav` already ships
          `display:flex; align-items:center; gap: var(--space-3)`, so this and the pill row sit
          beside each other with no wrapper of their own and no shell edit. */}
      <span className="agent-views-nav-kicker">{NAV_GROUP_LABEL}</span>
      {/* A plain flex group rather than a list (Q5). Four sibling buttons announce as four
          buttons; wrapping them in `ul`/`li` would add "list, 4 items" to every traversal of
          the header for no navigational gain — c6-7's rows earned their list by being an
          arbitrary-length collection of content, which four fixed controls are not. */}
      <div className="agent-views-nav-pills">
        {PILL_ORDER.map((kind) => (
          <AgentViewPill key={kind} kind={kind} />
        ))}
      </div>
    </>
  )
}

/**
 * The pills, left to right: **Suggestions, Swaps, Tier list, Card groups** (Q3).
 *
 * ENUM ORDER, read off {@link AGENT_VIEW_LABELS}' declaration order rather than authored a
 * second time here. Three artefacts give three different orders — the mock omits Suggestions
 * entirely and leads with Card groups, the IA table reads suggestions/groups/swaps/tier_list,
 * and the wire enum reads suggestions/swaps/tier_list/groups — so Q3 took the enum's, on the
 * grounds that a nav *defined* as generic over the contract should get its order from the
 * contract rather than from a fourth authored opinion. Suggestions first is also the only P0
 * kind first.
 *
 * The cast is the honest cost of that derivation, and it is sound for a reason the type system
 * cannot state: `AGENT_VIEW_LABELS` is declared `satisfies Record<AgentViewKind, string>`, so
 * its keys ARE exactly the union — no more (excess-property checking) and no fewer (missing-key
 * checking). `Object.keys` merely loses that on the way out. Deriving it this way rather than
 * retyping the four strings is what makes Story 9.1's *"with no nav work"* literally true, and
 * `AgentViewsNav.test.tsx` pins the rendered order so the implicitness stays gated.
 */
const PILL_ORDER = Object.keys(AGENT_VIEW_LABELS) as readonly AgentViewKind[]

/**
 * One pill (AC 1, AC 2, AC 3, AC 4).
 *
 * A module-local component rather than an inline branch in the map, because each pill takes TWO
 * store subscriptions of its own — that is the point of the per-kind selectors, and it is what
 * makes a `swaps` push re-render the `swaps` pill and nothing else. Hooks cannot be called in a
 * loop, so the loop calls a component. `SuggestionRow` in `SuggestionsView.tsx` is the shipped
 * precedent for the shape.
 *
 * ================= QUIET IS `disabled`, NEVER `tabindex="-1"` (AC 1) ==================
 *
 * `keyboard-floor.test.ts:753-780` pins exactly ONE named `tabindex` exception in this app
 * (`focusHome`'s), so a quiet pill spelled `tabindex="-1"` would be a second exception and a red
 * guard — and UX-DR40's *"nothing in this app carries a tabindex"* would stop being true.
 * `disabled` is also what `AgentView.tsx:108-115`'s focus-trap selector already excludes, and
 * what makes the cold-open Tab order contain no pill at all, which is UX-DR40's *"this stop
 * never exists"* read literally rather than approximately.
 *
 * A pill can never go active → quiet (retention is only ever added), so no focused element can
 * become disabled underfoot — the one real hazard of disabling controls dynamically.
 *
 * ================= AND NO `onKeyDown`, ON EITHER STATE (UX-DR39, dw:49) ===============
 *
 * Enter and Space are the button element's own click. A synthetic key handler here would be dead
 * three times over: `deferred-work.md:49` records that the document-capture Esc handler's
 * `stopPropagation()` starves React's synthetic delegation while a view is open; the pills sit
 * under the scrim while a view is open anyway; and a real `<button>` already does the thing the
 * handler would do. dw:49 names these pills by name and this is the annotation it was waiting
 * for.
 */
function AgentViewPill({ kind }: { kind: AgentViewKind }) {
  // The quiet/active decision is `useAgentViewHasPush`'s alone, deliberately separate from the
  // time below — a retained push with an unreadable `ts` must still read as ACTIVE (review
  // finding, 2026-08-12): reading activeness off `pushedAt` conflated "never pushed" with
  // "pushed, timestamp unreadable" and made the latter permanently unreachable via its pill.
  const hasPushed = useAgentViewHasPush(kind)
  const pushedAt = useAgentViewPushTime(kind)
  const unread = useAgentViewUnread(kind)
  // Generated rather than derived from `kind` (`agent-views-nav-suggestions-hint` would have
  // read fine) for `AgentView.tsx:129-135`'s reason: two mounted navs in one test document
  // would then share one id, and `aria-describedby` would resolve to whichever rendered first.
  const hintId = useId()

  if (!hasPushed) {
    return (
      <>
        <button
          type="button"
          className="agent-views-nav-pill"
          disabled
          /* BOTH, and that is Q2's ruling (see `copy.ts`). `title` is the pointer affordance the
             artefacts ask for; `aria-describedby` is what keeps it from being a hover-only
             disclosure of unique information, which UX-DR39 bans and which the 07-22
             accessibility review already caught once on the connection pill. Both carry the same
             string, so the two channels cannot say different things. */
          title={QUIET_TOOLTIP}
          aria-describedby={hintId}
        >
          {AGENT_VIEW_LABELS[kind]}
        </button>
        {/* OUTSIDE the button, deliberately. Inside, this text would join the button's CONTENTS
            and therefore its accessible NAME — the pill would compute as "Suggestions Your agent
            hasn't sent this yet." and then be described with the same sentence again. Outside,
            the name stays "Suggestions" and the sentence is purely a description. It is
            `.visually-hidden`, which is absolutely positioned, so it is not a flex item in the
            pill row either. */}
        <span id={hintId} className="visually-hidden">
          {QUIET_TOOLTIP}
        </span>
      </>
    )
  }

  // `pushedAt` can be `null` even on an active pill — a retained push with an absent `ts`
  // (`useAgentViewHasPush` is what decided this pill is active, not this value). `pushTimeLabel`
  // itself already degrades a present-but-unparseable `ts` string to `null`; this guards the
  // remaining case, an absent one, the same way.
  const time = pushedAt === null ? null : pushTimeLabel(pushedAt)
  return (
    <button
      type="button"
      className="agent-views-nav-pill"
      /* AC 4, and the whole of it. Everything the re-opened view needs was retained when the
         push arrived, so this asks the agent for nothing — and because `App.tsx` renders the
         overlay only while a view is open, this write MOUNTS the shell: the entry bloom, the
         focus-to-heading and the return-focus capture (which grabs this pill, since this pill is
         what was just clicked) all re-fire for free, and `SuggestionsView`'s `items`-keyed
         hydration effect re-runs against the CURRENT card cache. Stale ids degrade to
         unknown-card placeholders through machinery this story does not touch. */
      onClick={() => reopenAgentView(kind)}
    >
      {AGENT_VIEW_LABELS[kind]}
      {/* Both halves of the `&&` chain narrow `pushedAt` to `string` for the JSX below — written
         this way rather than `time === null ? null : …` because `time`'s nullness no longer
         implies `pushedAt`'s (an absent `ts` makes both null; a present-but-unparseable one
         makes only `time` null), so the render guard must check the value it actually uses. */}
      {pushedAt !== null && time !== null && (
        /* `<time>` with the raw `ts` in `dateTime`, so the machine-readable instant survives
           beside the human-readable one — the rendered text is locale-formatted and lossy about
           the date, the attribute is not. */
        <time className="agent-views-nav-time" dateTime={pushedAt}>
          {time}
        </time>
      )}
      {!unread ? null : (
        <>
          {/* PRESENTATIONAL (Q6). The word below is what carries the meaning; this is the
              colour that makes it glanceable. `aria-hidden` rather than an `aria-label` on the
              dot, because a labelled decorative span is a second name fragment in an order the
              accname algorithm decides, not the designer. */}
          <span className="agent-views-nav-dot" aria-hidden="true" />
          {/* INSIDE the button, unlike the quiet pill's description — this word belongs in the
              accessible NAME. "Suggestions 14:32 unread" is what a reader hears, and UX-DR29's
              *"the dot never carries the state alone"* is what requires it to be a word at all
              rather than a colour. Not announced: UX-DR45 licenses no live region here. */}
          <span className="visually-hidden">{UNREAD_WORD}</span>
        </>
      )}
    </button>
  )
}
