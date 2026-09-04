import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties } from 'react'

import type { AgentViewKind } from '../../api/schema'
import {
  AGENT_VIEW_LABELS,
  type AgentViewContent,
  reopenAgentView,
  reopenPush,
  useAgentViewHasPush,
  useAgentViewHistory,
  useAgentViewHistoryCount,
  useAgentViewIsOpen,
  useAgentViewPushTime,
  useAgentViewStore,
  useAgentViewUnread,
} from '../../state/agentView'
import './AgentViewsNav.css'
import './HistoryPopover.css'
import {
  HISTORY_LABEL,
  HISTORY_QUIET_TOOLTIP,
  NAV_GROUP_LABEL,
  QUIET_TOOLTIP,
  UNREAD_WORD,
} from './copy'
import { pushTimeLabel } from './pushTime'

/**
 * The agent-views nav — one pill per kind of thing the agent can put on the glass (FR-18,
 * UX-DR28, UX-DR33, UX-DR34, UX-DR37, UX-DR39, UX-DR40, UX-DR44, UX-DR45, UX-DR47,
 * `DESIGN.md:260-269`/`:522`, `EXPERIENCE.md:39-42`/`:73`/`:139-147`).
 *
 * It FILLS the header nav slot via `App.tsx`'s `nav` prop; `AppShell.tsx` itself knows nothing
 * about it.
 *
 * ================= IT IS GENERIC OVER THE ENUM, NOT OVER WHAT HAS A VIEW ==============
 *
 * Four pills always, keyed by {@link AgentViewKind} — the closed four-kind union derived in
 * `schema.ts`. A new kind's pill becomes active automatically, because the nav is generic over
 * the closed `kind` enum — which is only true if this file never mentions which kinds happen to
 * be renderable today. It does not. A fifth kind added on the Python side reaches
 * {@link PILL_ORDER} through the generator and grows a pill here with no edit.
 *
 * All four kinds have a tool, a dispatch arm and a view (the socket's dispatch holds no drop
 * arm), so every pill can activate in production. Quiet means what UX-DR33 says and nothing
 * less: "no push of this kind yet THIS SESSION" — not a degraded state or a placeholder, but
 * the named ninth state with its own copy, and *"your agent hasn't sent this yet"* is a true
 * sentence about a session, not about a tool.
 *
 * ================= WHAT IT IS NOT ====================================================
 *
 * **Not a `<nav>` landmark.** UX-DR44 enumerates the app's landmarks and this group is not
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
      {/* THE GROUP'S NAME, ON THE GLASS. A plain `<span>`, not a heading: a heading here
          would enter the document outline between the deck name and the panel titles and claim
          a structural rank this row does not have. The shell's `.app-shell-nav` already ships
          `display:flex; align-items:center; gap: var(--space-3)`, so this and the pill row sit
          beside each other with no wrapper of their own and no shell edit. */}
      <span className="agent-views-nav-kicker">{NAV_GROUP_LABEL}</span>
      {/* A plain flex group rather than a list. Four sibling buttons announce as four
          buttons; wrapping them in `ul`/`li` would add "list, 4 items" to every traversal of
          the header for no navigational gain — the suggestion rows earned their list by being an
          arbitrary-length collection of content, which four fixed controls are not. */}
      <div className="agent-views-nav-pills">
        {PILL_ORDER.map((kind) => (
          <AgentViewPill key={kind} kind={kind} />
        ))}
        {/* THE FIFTH PILL, AFTER THE FOUR KIND PILLS (FR-18).
            Deliberately OUTSIDE the map: History is not an `AgentViewKind` — it never pushes and
            has no view of its own — so keying it into `PILL_ORDER` would put a non-kind in a list
            the enum derives, and the exhaustiveness gate on `AGENT_VIEW_LABELS` would stop
            meaning "one word per wire kind". */}
        <HistoryPill />
      </div>
    </>
  )
}

/**
 * The pills, left to right: **Suggestions, Swaps, Tier list, Card groups**.
 *
 * ENUM ORDER, read off {@link AGENT_VIEW_LABELS}' declaration order rather than authored a
 * second time here. Three artefacts give three different orders — the mock omits Suggestions
 * entirely and leads with Card groups, the IA table reads suggestions/groups/swaps/tier_list,
 * and the wire enum reads suggestions/swaps/tier_list/groups — so the enum's wins: a nav
 * *defined* as generic over the contract should get its order from the contract rather than
 * from a fourth authored opinion. Suggestions first is also the only P0
 * kind first.
 *
 * The cast is the honest cost of that derivation, and it is sound for a reason the type system
 * cannot state: `AGENT_VIEW_LABELS` is declared `satisfies Record<AgentViewKind, string>`, so
 * its keys ARE exactly the union — no more (excess-property checking) and no fewer (missing-key
 * checking). `Object.keys` merely loses that on the way out. Deriving it this way rather than
 * retyping the four strings is what makes "a new kind needs no nav work" literally true, and
 * `AgentViewsNav.test.tsx` pins the rendered order so the implicitness stays gated.
 */
const PILL_ORDER = Object.keys(AGENT_VIEW_LABELS) as readonly AgentViewKind[]

/**
 * One pill.
 *
 * A module-local component rather than an inline branch in the map, because each pill takes TWO
 * store subscriptions of its own — that is the point of the per-kind selectors, and it is what
 * makes a `swaps` push re-render the `swaps` pill and nothing else. Hooks cannot be called in a
 * loop, so the loop calls a component. `SuggestionRow` in `SuggestionsView.tsx` is the shipped
 * precedent for the shape.
 *
 * ================= QUIET IS `disabled`, NEVER `tabindex="-1"` =========================
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
 * ================= AND NO `onKeyDown`, ON EITHER STATE (UX-DR39) ======================
 *
 * Enter and Space are the button element's own click. A synthetic key handler here would be dead
 * three times over: the document-capture Esc handler's `stopPropagation()` starves React's synthetic delegation while a view is open; the pills sit
 * under the scrim while a view is open anyway; and a real `<button>` already does the thing the
 * handler would do.
 */
function AgentViewPill({ kind }: { kind: AgentViewKind }) {
  // The quiet/active decision is `useAgentViewHasPush`'s alone, deliberately separate from the
  // time below — a retained push with an unreadable `ts` must still read as ACTIVE: reading
  // activeness off `pushedAt` would conflate "never pushed" with "pushed, timestamp unreadable"
  // and make the latter permanently unreachable via its pill.
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
          /* BOTH, deliberately (see `copy.ts`). `title` is the pointer affordance the
             artefacts ask for; `aria-describedby` is what keeps it from being a hover-only
             disclosure of unique information, which UX-DR39 bans. Both carry the same string,
             so the two channels cannot say different things. */
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
      /* RE-OPEN, and the whole of it. Everything the re-opened view needs was retained when the
         push arrived, so this asks the agent for nothing — and because `App.tsx` renders the
         overlay only while a view is open, this write MOUNTS the shell: the entry bloom, the
         focus-to-heading and the return-focus capture (which grabs this pill, since this pill is
         what was just clicked) all re-fire for free, and `SuggestionsView`'s `items`-keyed
         hydration effect re-runs against the CURRENT card cache. Stale ids degrade to
         unknown-card placeholders through the view's own machinery. */
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
          {/* PRESENTATIONAL. The word below is what carries the meaning; this is the
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

/**
 * The stroke-based clock glyph on the History pill (DESIGN.md's
 * `components.history-popover` header note) — **a plain UI glyph, never anything
 * set-symbol-shaped**, which is the note's own emphasis: a circular glyph in a Magic app is one
 * careless flourish away from reading as a set symbol, so this is the most generic clock
 * drawable — a circle and two hands, stroked in `currentColor` so it takes the pill's own
 * foreground in every state (quiet `text-tertiary`, rest `text-secondary`, hover
 * `accent-bright`) with no rule of its own.
 *
 * `aria-hidden` + `focusable="false"`: the label word "History" beside it carries the whole
 * accessible name, exactly as the unread dot's word does — a glyph never carries meaning alone
 * (UX-DR29's rule, applied preemptively). Sized in CSS at `1em` so it rides the label's own
 * type role rather than declaring a geometry literal.
 */
function ClockGlyph() {
  return (
    <svg className="agent-views-nav-clock" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M8 4.75V8l2.25 1.75"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/**
 * The History pill and its popover — FR-18's home (`EXPERIENCE.md`'s `History pill + popover`
 * row, DESIGN.md `{components.history-popover}`).
 *
 * ================= THE APP'S FIRST DISCLOSURE CONTROL, AND WHAT THAT IS NOT ===========
 *
 * A real `<button aria-haspopup aria-expanded>` toggling a **non-modal** popover: no scrim, no
 * focus trap, no roving focus, no landmark, no live region — opening and closing announce
 * nothing, and a push arriving while it is open closes it unannounced (an arriving push opens
 * its view, and popover and modal never coexist — see {@link showPopover}). The entries
 * are ordinary document-order Tab stops, withdrawn on dismiss.
 *
 * ================= QUIET UNTIL THE FIRST PUSH OF *ANY* KIND ===========================
 *
 * The kind pills' exact quiet pattern — `disabled` + `title` + `aria-describedby` to a
 * visually-hidden sibling OUTSIDE the button — with its own sentence ({@link
 * HISTORY_QUIET_TOOLTIP}), because this pill's quiet is about the session rather than a kind.
 * It **never carries an unread dot**: unread stays per-kind on the kind pills, and history is a
 * place to revisit, not a place to catch up.
 *
 * ================= DISMISSAL, AND WHERE EACH LISTENER LIVES ===========================
 *
 * Four gestures: entry activation, Esc, outside click, toggling the pill. Esc is TWO listeners
 * with one outcome: a native keydown on the WRAPPER node — pill and popover together, the
 * `AgentView` trap's attach-through-refs pattern — that `preventDefault()`s, which is what
 * keeps `CardDetail`'s document-level pin release out of the same keystroke, honouring
 * UX-DR39's amended order (view → popover → pin) whenever focus sits anywhere inside the
 * wrapper (opening puts it on the newest entry; toggling leaves it on the pill — both inside) —
 * plus a document-level BUBBLE keydown for an Esc struck with focus elsewhere (the entries are
 * ordinary Tab stops, so focus can leave without dismissing). The document listener is in the
 * keyboard-floor census with its written reason; the modal's capture listener pre-empts both
 * while a view is open, and by invariant the popover is already closed then anyway. Outside
 * click is a native document `pointerdown` per the `AgentView` scrim convention.
 *
 * Focus contract: open → the first (newest) entry; close → back to this pill whenever focus
 * would otherwise be dropped (it was inside the popover, or already on `<body>`) — never to
 * `document.body`. Entry activation closes FIRST (focus → pill), then opens the view through
 * {@link reopenPush}, so the view's own mount capture records the pill as its return target and
 * the overlay stack stays one level deep.
 */
function HistoryPill() {
  const count = useAgentViewHistoryCount()
  const viewIsOpen = useAgentViewIsOpen()
  const [open, setOpen] = useState(false)
  const hintId = useId()
  // The popover element's own id, for `aria-controls` on the pill — the programmatic half of
  // the disclosure relationship the `aria-expanded`/`aria-haspopup` pair only implies. `useId`
  // for the hint id's reason: two mounted navs must not share one target.
  const popoverId = useId()
  const pillRef = useRef<HTMLButtonElement>(null)
  const wrapperRef = useRef<HTMLSpanElement>(null)

  /**
   * Whether the popover is on the glass RIGHT NOW. Derived rather than `open` alone, so the
   * commit that mounts an agent view is the same commit that unmounts the popover — "popover
   * and modal never coexist" held by construction in a single render, with no frame in which
   * the DOM holds both. `open` itself is reset by the effect below so the popover does not
   * spring back when the view closes.
   */
  const showPopover = open && !viewIsOpen

  /**
   * `closePopover`, read through a ref at event time, so the two document listeners below can
   * register once per open (`[showPopover]`) without re-subscribing on every render — the
   * `AgentView` shell's `onCloseRef` pattern, for its reason.
   */
  const closeRef = useRef<() => void>(() => {})

  const closePopover = () => {
    const pill = pillRef.current
    const active = document.activeElement
    // Focus returns to the pill whenever closing would otherwise DROP it — it sits inside the
    // wrapper (an entry, or the pill itself) and the entries are about to unmount, or it is
    // already on `<body>`. Focus resting on some other control (the entries are ordinary Tab
    // stops, so it can wander out) is a decision this close did not make and must not reverse —
    // `AgentView`'s arm-2 guard, in the non-modal shape.
    const inWrapper = active instanceof Node && (wrapperRef.current?.contains(active) ?? false)
    if (pill !== null && (inWrapper || active === null || active === document.body)) pill.focus()
    setOpen(false)
  }
  useEffect(() => {
    closeRef.current = closePopover
  })

  // A PUSH ARRIVED (or a view opened by any route) WHILE THE POPOVER WAS OPEN: the derived
  // `showPopover` unmounts it in the very commit the view mounts — closed "first", before the
  // view is seen — and this SUBSCRIPTION settles the residue durably. A store subscription
  // rather than an effect body write, which is `react-hooks/set-state-in-effect`'s own
  // recommended shape (subscribe to the external system, set state in the callback) — and the
  // callback runs SYNCHRONOUSLY on the store write, before React commits, which buys the focus
  // hand-off its timing: focus still sits on the entry that is ABOUT to unmount, so it is moved
  // to the pill here, and the view's mount-time return-focus capture then records the pill —
  // never `document.body`. The `open` reset is synchronous too, deliberately: parked in a
  // requestAnimationFrame, a view closed before that frame fired would cancel the reset in the
  // effect cleanup — leaving `open` true and the popover springing back uninvited the moment
  // the view left the glass.
  useEffect(() => {
    if (!open) return
    return useAgentViewStore.subscribe((state) => {
      if (state.status !== 'open') return
      // `closePopover` verbatim, through the ref (see its declaration): one body for the
      // focus-return arm-2 guard and the synchronous `open` reset, not a duplicate to drift.
      closeRef.current()
    })
  }, [open])

  // ESC, THE WRAPPER-LEVEL HALF (see the header): a native listener attached through the ref —
  // `jsx-a11y` is right that the wrapper `<span>` is not a control, so the listener goes on the
  // node rather than into a prop, the `AgentView` trap's exact reasoning. On the WRAPPER rather
  // than the popover root: focus can legitimately sit on the
  // PILL while the popover is open — toggling put it there — and a popover-scoped listener
  // would miss that Esc, closing via the document half below WITHOUT consuming the keystroke
  // and co-releasing an active pin. It `preventDefault()`s, which is what keeps the SAME Esc
  // from also releasing a pin (`CardDetail`'s document listener honours `defaultPrevented`):
  // UX-DR39's amended order — view, then popover, then pin — one layer per keystroke. It does
  // NOT stop propagation; the document-level twin sees `defaultPrevented` and stands down.
  useEffect(() => {
    if (!showPopover) return
    const wrapper = wrapperRef.current
    if (wrapper === null) return
    const dismiss = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape' || event.isComposing || event.defaultPrevented) return
      event.preventDefault()
      closeRef.current()
    }
    wrapper.addEventListener('keydown', dismiss)
    return () => wrapper.removeEventListener('keydown', dismiss)
  }, [showPopover])

  // ESC CLOSES THE POPOVER — the document-level BUBBLE half (see the header). Registered only
  // while the popover shows; never stops propagation and never needs to: the agent view's
  // capture listener pre-empts it while a view is open (when this is unregistered anyway), and
  // the wrapper's own listener has already `preventDefault()`ed — which the standard guard
  // below honours — whenever focus was inside. `keyboard-floor.test.ts` carries this entry in
  // the listener census with the phase asserted.
  useEffect(() => {
    if (!showPopover) return
    const dismiss = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Escape' || event.isComposing || event.defaultPrevented) return
      closeRef.current()
    }
    document.addEventListener('keydown', dismiss)
    return () => document.removeEventListener('keydown', dismiss)
  }, [showPopover])

  // OUTSIDE CLICK CLOSES THE POPOVER — a native document pointer listener per the `AgentView`
  // scrim convention (native on the node that owns the gesture, never a synthetic prop on a
  // non-control). `pointerdown` rather than `click`, because a click whose mousedown and
  // mouseup straddle the popover edge would fire on a common ancestor and misread the gesture;
  // the DOWN alone is the honest "you pressed elsewhere". The wrapper (pill + popover) is the
  // inside — a press on the pill itself must fall through to the pill's own toggle rather than
  // close-then-reopen.
  useEffect(() => {
    if (!showPopover) return
    const onPointerDown = (event: globalThis.Event) => {
      const target = event.target
      if (target instanceof Node && (wrapperRef.current?.contains(target) ?? false)) return
      closeRef.current()
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [showPopover])

  const activateEntry = (id: string) => {
    // CLOSE FIRST, THEN OPEN: `closePopover` puts focus on the pill and
    // unmounts the entries; `reopenPush` then mounts the view, whose capture effect records the
    // pill as the element to restore focus to on dismissal. One handler, one commit, one
    // overlay level.
    closePopover()
    reopenPush(id)
  }

  if (count === 0) {
    return (
      <span ref={wrapperRef} className="agent-views-nav-history">
        <button
          type="button"
          className="agent-views-nav-pill agent-views-nav-history-pill"
          disabled
          /* BOTH channels, the kind pills' pattern verbatim — a pointer `title` plus a
             programmatic description, one string, so the two cannot disagree. The disclosure
             attributes stay on the quiet pill too: it IS the toggle, merely not yet usable, and
             a control whose role changes when it activates is a control a reader has to
             re-learn. */
          title={HISTORY_QUIET_TOOLTIP}
          aria-describedby={hintId}
          aria-haspopup="true"
          aria-expanded="false"
        >
          <ClockGlyph />
          {HISTORY_LABEL}
        </button>
        {/* OUTSIDE the button, for the kind pills' reason: inside, the sentence would join the
            accessible NAME and then describe the pill with itself again. */}
        <span id={hintId} className="visually-hidden">
          {HISTORY_QUIET_TOOLTIP}
        </span>
      </span>
    )
  }

  return (
    <span ref={wrapperRef} className="agent-views-nav-history">
      <button
        ref={pillRef}
        type="button"
        className="agent-views-nav-pill agent-views-nav-history-pill"
        aria-haspopup="true"
        aria-expanded={showPopover}
        /* Wired only while the popover is mounted: an `aria-controls` naming an id that is not
           in the document is a dangling reference, which is the same silence a dangling
           `aria-describedby` would be. */
        aria-controls={showPopover ? popoverId : undefined}
        onClick={() => {
          if (showPopover) closePopover()
          else setOpen(true)
        }}
      >
        <ClockGlyph />
        {HISTORY_LABEL}
        {/* NO time, NO unread dot, ever: the pill names a LIST, not a push — the times live on
            the entries inside, and unread stays per-kind on the kind pills. */}
      </button>
      {showPopover && <HistoryPopover id={popoverId} onActivate={activateEntry} />}
    </span>
  )
}

/**
 * The popover itself — a plain group of entry `<button>`s, newest first, exactly
 * as the store holds them ({@link useAgentViewHistory} is the stored reference; the ORDERING —
 * by envelope `ts`, never `id`, malformed `ts` at arrival position — is the store's, decided
 * once in `historyWith`, so this component renders the array and re-sorts nothing).
 *
 * NOT a modal, NOT a landmark, NOT a live region, NOT a listbox: no role, no label, no
 * `aria-live`, no roving focus — the entries are ordinary Tab stops and open/close announce
 * nothing. Mounting moves focus to the first
 * (newest) entry; every later focus move is the person's own.
 *
 * The enter is an OPACITY-ONLY fade over the glide tokens, expressed as a transition out of a
 * `data-entering` state with the flip in a frame callback — `AgentView.tsx`'s bloom pattern,
 * for both of its reasons (a keyframes block would defeat the CSS reader's brace matching, and
 * two style writes in one frame coalesce into no transition at all). No rise, no transform: an
 * opacity fade over a tokenised duration self-neutralises under reduced motion, so the
 * reduced-motion block registers nothing for it.
 */
function HistoryPopover({ id, onActivate }: { id: string; onActivate: (id: string) => void }) {
  const history = useAgentViewHistory()
  const rootRef = useRef<HTMLDivElement>(null)

  const [entering, setEntering] = useState(true)
  useEffect(() => {
    const frame = requestAnimationFrame(() => setEntering(false))
    return () => cancelAnimationFrame(frame)
  }, [])

  // THE CLAMPS' ANCHOR TERMS. The popover hangs below a content-sized header on a row that is
  // ALLOWED to wrap (`.agent-views-nav-pills` declares `flex-wrap: wrap` as the honest
  // narrow-window failure mode), so neither of its distances — from the viewport top (the
  // height clamp's subtrahend) nor from the viewport left to its own right-anchored edge (the
  // width clamp's budget: a wrapped pill leaves the viewport's right edge, and a 100vw-based
  // cap then lets a long title run past the LEFT edge) — is knowable in CSS alone. Both are
  // measured before paint into custom properties (the ManaCurve/ColourDistribution channel —
  // literal inline styles stay illegal) and RE-measured on window resize while open: resize is
  // the only thing that can move
  // the anchor mid-open — the header re-wraps with the window, and the list itself cannot
  // change under an open popover (an arriving push closes it). `rect.right` is anchor-stable
  // even as content grows, because the popover is right-anchored to the wrapper. Not a key
  // listener, so the keyboard-floor census has no stake. jsdom's zero rects degrade both terms
  // to 0px, and exact geometry stays the eye-check's.
  const [anchor, setAnchor] = useState({ top: 0, right: 0 })
  useLayoutEffect(() => {
    const measure = () => {
      const rect = rootRef.current?.getBoundingClientRect()
      setAnchor({ top: rect?.top ?? 0, right: rect?.right ?? 0 })
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [])

  // FOCUS TO THE FIRST (NEWEST) ENTRY ON OPEN — a mount effect, and mount-only is sufficient
  // rather than lazy: the list cannot change while the popover shows, because every arriving
  // push auto-opens its view and that closes the popover (the pill's derived `showPopover`).
  useEffect(() => {
    rootRef.current?.querySelector<HTMLElement>('button')?.focus()
  }, [])

  // Esc handling lives on the WRAPPER in `HistoryPill` (both halves — the consuming node
  // listener and the census-registered document one), not here: focus can sit on the pill while
  // the popover shows, and a popover-scoped listener would miss that keystroke.

  return (
    <div
      ref={rootRef}
      id={id}
      className="agent-views-nav-popover"
      data-entering={entering ? 'true' : undefined}
      style={
        {
          '--history-popover-top': `${anchor.top}px`,
          '--history-popover-right': `${anchor.right}px`,
        } as CSSProperties
      }
    >
      {history.map((entry) => (
        <HistoryEntry key={entry.id} entry={entry} onActivate={onActivate} />
      ))}
    </div>
  )
}

/**
 * One history entry: kind label + push title (when the agent supplied one) + time.
 *
 * The TITLE renders only when it differs from the kind's own word: the store's builders fall
 * back to `AGENT_VIEW_LABELS[kind]` for an untitled push, and "Suggestions — Suggestions" would
 * be the fallback read out twice. That is what the artefact's *"push title (when present)"*
 * means once the fallback exists — present is "the agent named it".
 *
 * The TIME is `pushTimeLabel` verbatim (never re-implemented; its bytes are host-locale and are
 * never asserted), inside a `<time>` carrying the raw `ts`, exactly as the kind pills render
 * theirs — and it degrades to nothing on an absent or unparseable `ts`, per that module's own
 * contract, while the entry stays activatable: a push whose clock is unreadable is still a push
 * worth revisiting.
 */
function HistoryEntry({
  entry,
  onActivate,
}: {
  entry: AgentViewContent
  onActivate: (id: string) => void
}) {
  // `ts` is typed as a string, but `agentEventOf` validates only `kind`, so at runtime it can
  // be absent — the same two-guard shape the kind pill wears at its `<time>`.
  const raw = typeof entry.ts === 'string' ? entry.ts : null
  const time = raw === null ? null : pushTimeLabel(raw)
  return (
    <button type="button" className="agent-views-nav-entry" onClick={() => onActivate(entry.id)}>
      <span className="agent-views-nav-entry-kind">{AGENT_VIEW_LABELS[entry.kind]}</span>
      {entry.title !== AGENT_VIEW_LABELS[entry.kind] && (
        <span className="agent-views-nav-entry-title">{entry.title}</span>
      )}
      {raw !== null && time !== null && (
        <time className="agent-views-nav-entry-time" dateTime={raw}>
          {time}
        </time>
      )}
    </button>
  )
}
