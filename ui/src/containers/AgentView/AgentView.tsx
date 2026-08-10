import { type ReactNode, useEffect, useId, useRef, useState } from 'react'

import { focusHome } from '../focusHome'
import { AGENT_VIEW_KICKER, CLOSE_PILL_LABEL } from './copy'
import './AgentView.css'

/**
 * The agent view shell — the app's FIRST modal, first focus trap and first `role="dialog"`
 * (story c6-5, UX-DR23, UX-DR34, UX-DR38, UX-DR39, UX-DR42, UX-DR44, UX-DR46).
 *
 * ================= IT IS A SHELL, AND IT KNOWS NOTHING ABOUT SUGGESTIONS ===============
 *
 * Every agent view in Epic 6 lives inside this component, so it takes a `title`, a `count` and
 * `children` and nothing else: no envelope, no wire type, no `kind`. c6-7 renders suggestion
 * rows INTO it and c6-8 adds nav pills BESIDE it, and neither has to edit this file to do so —
 * which is the property that makes "content-agnostic" a testable claim rather than a hope
 * (`AgentView.test.tsx` mounts it over an arbitrary fixture child).
 *
 * It is a CONTAINER rather than a component: `src/components/` is closed by a set-equality
 * guard (`shell.test.ts:1257`) and `ui/README.md:567-571` homes c6-5..c6-8 here. It also does
 * NOT compose `Panel`, whose header (label + count + right-aligned extras) is structurally
 * identical and therefore tempting: `Panel` is presentation-only by guard — a `<section
 * aria-label>` with no `role`, no `aria-modal`, no refs and no hooks — and this shell needs all
 * four. The visual kinship comes from sharing tokens, not markup.
 *
 * ================= WHERE IT SITS, AND WHAT IT MUST NOT DO ABOUT THAT ===================
 *
 * `App` passes it to `AppShell`'s `overlay` slot, which is a `position: fixed; inset:
 * var(--space-gutter); z-index: 20` layer that has been reserved and guarded since c2-1
 * (`AppShell.css:223-271`). **This component does not position itself.** The slot is the only
 * full-window fixed layer the app permits — `shell.test.ts:952-957` fails the suite on a second
 * one — so `AgentView.css` sets no `position: fixed` and no `z-index` at all, and fills the box
 * it is handed. The scrim is therefore the inset box rather than the whole window, which is the
 * shipped reading of *"inset {spacing.6}"* that `AppShell.css:240-245` recorded for this story
 * by name.
 *
 * It also mounts ONLY while a view is open. `App` passes an absent `overlay` when the store is
 * closed (`AppShell.tsx:134-139`'s click-swallower warning), so "on open" is this component's
 * mount and "on close" is its unmount. Every effect below reads that way, and it is what makes
 * the Esc listener exist only while there is something for Esc to close.
 *
 * ================= THE THREE DISMISSALS ALL END IN ONE PLACE (AC 4, AC 5) ==============
 *
 * The close pill, Esc, and a click on the scrim outside the panel each call `onClose` — which
 * `App` binds to `closeAgentView`, the verb that writes `status` and provably not `content`
 * (`agentView.ts`). Nothing here clears anything: a component that could forget the content
 * would be a second place UX-DR34 had to be obeyed.
 */
export interface AgentViewProps {
  /** The heading, and the dialog's accessible name (`aria-labelledby` → the `h2`). */
  readonly title: string
  /**
   * The summary count beside the title. `Number.isFinite`-gated exactly as `Panel` gates its
   * own (`Panel.tsx:73-80`): `0` is REAL CONTENT and renders, and `count && …` would put a bare
   * `0` in the DOM — the c2-6 falsy-value family arriving in a numeric prop.
   */
  readonly count: number | null
  /** Dismissal. Bound to `closeAgentView` by `App`; called by all three gestures. */
  readonly onClose: () => void
  /** The body. Anything — this shell renders it and asks nothing about it. */
  readonly children?: ReactNode
}

/**
 * Everything inside `root` that can take focus, in DOCUMENT ORDER.
 *
 * `querySelectorAll` returns document order by specification, which is the whole reason the
 * trap needs no sorting and no `tabindex` arithmetic: `keyboard-floor.test.ts` bans positive
 * `tabindex` anywhere in the app, so document order IS tab order here and the first and last
 * elements of this list are the two ends the trap wraps between.
 *
 * `[tabindex]:not([tabindex='-1'])` admits a deliberately-focusable non-control and excludes
 * the programmatic-only kind — which matters immediately, because `focusHome` puts
 * `tabindex="-1"` on the heading this component focuses on open. The heading is therefore NOT
 * a trap stop, and the first Tab out of it lands on the close pill by document order.
 *
 * WHAT THIS CANNOT SEE, DECLARED: visibility. A control hidden by CSS is focusable to this
 * query and unfocusable to a browser, and jsdom evaluates no stylesheet at all (no layout, no
 * `offsetParent`, no resolved `display`) — so an `offsetParent` filter would behave one way in
 * the tests that check it and another way in the browser that matters. `[hidden]` and
 * `aria-hidden` are excluded because those are declared in MARKUP, which is the half a source
 * reader can honestly know about. The residue is a shell that hides a control with CSS alone,
 * which nothing in Epic 6 does.
 */
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  "[tabindex]:not([tabindex='-1'])",
].join(', ')

const focusablesIn = (root: HTMLElement | null): HTMLElement[] =>
  root === null
    ? []
    : [...root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)].filter(
        (element) =>
          !element.hasAttribute('hidden') && element.getAttribute('aria-hidden') !== 'true',
      )

export function AgentView({ title, count, onClose, children }: AgentViewProps) {
  /**
   * The heading's `id`, for `aria-labelledby`.
   *
   * `useId()` rather than a constant, and this is the one place the app's *"exactly one DOM
   * id"* rule bends rather than breaks (`focusHome.ts:50`). `SKIP_TARGET_ID` is a hand-written
   * constant because two DIFFERENT modules have to agree on it across a directory boundary;
   * this id is produced and consumed inside one element tree, which is precisely the case
   * `useId` exists for. A hand-written second constant would be a second thing to keep unique;
   * `useId` cannot collide with anything, including a second AgentView that a future story
   * mounts in a test.
   *
   * `aria-label` was rejected rather than not considered: it would duplicate the heading text
   * and drift from it, and UX-DR23's contract is *labelled by its heading*, not *labelled with
   * the same words as its heading*.
   */
  const headingId = useId()

  /**
   * THE BLOOM'S STARTING STATE (AC 7, `DESIGN.md:471`, UX-DR23).
   *
   * The view enters as a fade plus an 8px rise over `--motion-bloom`. That is expressed as a
   * TRANSITION out of a starting state carried by this attribute, rather than as a
   * `@keyframes` animation, and the reason is a real constraint rather than a preference: the
   * CSS reader behind the reduced-motion gate (`token-usage.test.ts:88-97`) matches innermost
   * brace pairs, so a keyframes block registers as two rules named `from` and `to` — and the
   * enumerated shipped-motion pin would then demand a `from { transform: none !important }`
   * registration, which is meaningless CSS (`!important` is ignored inside keyframes by
   * specification). A state attribute gives the pin ONE honest entry,
   * `.agent-view[data-entering='true'] :: transform`, and gives UX-DR42's *"appears in place"*
   * an exact meaning: under reduced motion the starting offset is zeroed, so there is no rise
   * to arrive from.
   *
   * THE FLIP IS IN A FRAME CALLBACK, not in the effect body, and that is a correctness point
   * rather than a lint accommodation. A transition needs the browser to have PAINTED the
   * starting state before the ending one arrives; two style changes inside one frame are
   * coalesced and the transition never runs. `requestAnimationFrame` puts a real frame between
   * them. (It also keeps `react-hooks/set-state-in-effect` satisfied, which is the same rule
   * pointing at the same hazard from the other side.)
   *
   * **Nothing waits on this either way** (EXPERIENCE.md:165, and Ruled #3): the DOM is complete
   * and interactive at the first render, and the bloom is presentation laid on top of it. If the
   * frame never came, the cost is a view that appears instantly — which is exactly the
   * reduced-motion fallback, and not a defect anything downstream can observe.
   */
  const [entering, setEntering] = useState(true)
  useEffect(() => {
    const frame = requestAnimationFrame(() => setEntering(false))
    return () => cancelAnimationFrame(frame)
  }, [])

  const scrimRef = useRef<HTMLDivElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)

  /**
   * Whichever element had focus when this view opened — captured on the way IN, because by the
   * time the unmount cleanup runs React has removed this subtree and `document.activeElement`
   * reads `<body>` for every case at once. `SkipLink.tsx:95-106` learned this first and states
   * it at length; this is the same lesson in the modal shape.
   *
   * A ref rather than state: nothing renders differently, and a `setState` here would re-render
   * the shell for no visible reason.
   */
  const restoreTargetRef = useRef<HTMLElement | null>(null)

  /**
   * `onClose`, read at event time rather than captured when the listener was registered.
   *
   * The Esc effect below must run EXACTLY ONCE per open — it registers a document-level capture
   * listener, and re-registering it on every render because a caller passed an inline arrow
   * would make the app's most load-bearing keyboard contract depend on a caller's memoisation.
   * The ref is what lets the effect's dependency list be empty and still call the current
   * handler.
   */
  const onCloseRef = useRef(onClose)
  // Written in an EFFECT, not during render: a ref mutated while rendering is
  // `react-hooks/refs`'s error, and the rule is right — render must stay repeatable, and React
  // may render without committing. No dependency array, so it tracks every render.
  useEffect(() => {
    onCloseRef.current = onClose
  })

  // FOCUS ON OPEN, AND FOCUS BACK ON CLOSE (AC 3, AC 4, UX-DR39, UX-DR46).
  useEffect(() => {
    const previous = document.activeElement
    // `<body>` is not a restore target — it is the ABSENCE of one, and AC 4 says focus must
    // never return there. Recording `null` for it is what makes the "never held" arm below a
    // real arm rather than an accident.
    restoreTargetRef.current =
      previous instanceof HTMLElement && previous !== document.body ? previous : null

    // AC 3: focus moves to the view's HEADING. `focusHome` is the shipped hand-off — it does the
    // `tabIndex = -1` plus once-blur-cleanup dance, so the heading at rest carries no
    // `[tabindex]` and never becomes a Tab stop of its own.
    focusHome(headingRef.current)

    return () => {
      const target = restoreTargetRef.current
      // ARM 1 — nothing was held. Focus was on `<body>` (or nowhere) when this opened, so there
      // is nothing to restore, and moving focus anyway would be this component inventing a
      // destination nobody asked for.
      if (target === null) return
      // ARM 2 — something else already took focus. `SkipLink.tsx:110-112`'s guard verbatim:
      // overriding that would be this component reversing a decision it did not make.
      if (document.activeElement !== null && document.activeElement !== document.body) return
      // ARM 3 — the remembered element is GONE (Brad's Q5 ruling, 2026-08-10). A row that was
      // re-rendered away, or a control that only exists on a surface that has since changed.
      // The `<h1>` deck name is the shared fallback for every disconnected-restore case until
      // c6-6 refines the state-panel arm; `AppShell.test.tsx:66` pins that there is exactly one
      // `h1` in the document, which is what makes a document-wide query precise here.
      if (!target.isConnected) {
        focusHome(document.querySelector('h1'))
        return
      }
      // The ordinary path. `.focus()` and deliberately NOT `focusHome`: this element was
      // focusable a moment ago (it HAD focus), and `focusHome` would write `tabIndex = -1` onto
      // it — which on a native control evicts a real Tab stop until the next blur. `focusHome`
      // is for the two headings above, which are not focusable without it.
      target.focus()
    }
  }, [])

  // ESC CLOSES THE VIEW, AND THE PIN SURVIVES (AC 4, UX-DR39, EXPERIENCE.md:141).
  //
  // On `document`, in the CAPTURE phase, registered only while a view is open — the contract
  // `CardDetail.tsx:89-101` and `inspection.ts:55-67` have both stated verbatim since c4-5 and
  // which this story is the first to be able to honour. Capture at the document runs before
  // CardDetail's document BUBBLE listener for EVERY target, so `stopPropagation()` here means a
  // single Esc closes this view and leaves an active pin alone even when focus sits on `<body>`
  // rather than inside this subtree. An element-scoped handler could not hold that: a `keydown`
  // targeting `<body>` never passes through this overlay at all.
  //
  // `keyboard-floor.test.ts:507-633` pins the listener set and the phase of each entry, and this
  // is the exemption it was written to admit (dw:4766-4773).
  useEffect(() => {
    const dismiss = (event: globalThis.KeyboardEvent) => {
      // Both guards are `CardDetail.tsx:371-375`'s, for its reasons: an Esc that cancels an IME
      // composition is not a request to close a view, and an Esc some other handler has already
      // consumed is not this listener's to act on.
      if (event.key !== 'Escape' || event.isComposing || event.defaultPrevented) return
      // BEFORE the close, so the ordering does not depend on React's scheduling of the unmount
      // this triggers. `stopPropagation` (not `stopImmediatePropagation`): the contract is about
      // OTHER nodes in the path, and a second listener on `document` itself is already banned by
      // the keyboard floor.
      event.stopPropagation()
      onCloseRef.current()
    }
    document.addEventListener('keydown', dismiss, true)
    return () => document.removeEventListener('keydown', dismiss, true)
  }, [])

  /**
   * TAB CYCLES WITHIN THE VIEW (AC 2, UX-DR44, EXPERIENCE.md:142).
   *
   * The app's first focus trap, and it is deliberately the small kind: it wraps at the two ends
   * and does nothing else. Nothing is made `inert`, and no listener watches for focus escaping —
   * a shell that fought the browser for focus would be a shell that could strand it.
   *
   * The wrap is asserted directly by `AgentView.test.tsx` rather than by tabbing, because jsdom
   * implements no sequential focus navigation at all: pressing Tab in a test moves nothing, so a
   * test that "tabbed to the end" would be asserting its own `fireEvent` calls. What is provable
   * is this handler's arithmetic — which element it moves focus to given which element has it —
   * and that is what the suite checks.
   */
  /**
   * Whether the mousedown and the mouseup that bracket the current click BOTH landed on the
   * SCRIM itself (Brad's Q3 ruling, 2026-08-10; symmetric mouseup check added at code review,
   * 2026-08-10).
   *
   * A bare `click` handler is not enough, and the failure is ordinary rather than exotic: when
   * mousedown and mouseup target different elements, `click` fires on their common ancestor —
   * the scrim, since it wraps the whole panel. A drag that starts on the panel — selecting a
   * line of a suggestion's rationale — and ends on the scrim would otherwise close the view
   * mid-selection; the mirror drag, starting on the scrim and ending on panel content (a
   * misaimed press near the edge, released over a control), would otherwise close it when the
   * gesture reads as an in-panel interaction. So BOTH ends of the gesture must independently be
   * the scrim — the standard modal guard, checked in both directions.
   */
  const scrimMouseDownOnScrimRef = useRef(false)
  const scrimMouseUpOnScrimRef = useRef(false)

  /**
   * THE TRAP AND THE SCRIM, AS NATIVE LISTENERS ON THE TWO NODES.
   *
   * Attached through refs rather than as JSX `onKeyDown`/`onClick` props, and the reason is that
   * `jsx-a11y` is right about what those props would mean. A `<div>` carrying mouse handlers is
   * `no-static-element-interactions`, and `role="dialog"` carrying a key handler is
   * `no-noninteractive-element-interactions` — both rules exist to catch a `<div>` pretending to
   * be a control, and the honest answer here is that NEITHER of these elements is one. The scrim
   * is a backdrop whose click merely duplicates the close pill, and the dialog root is a
   * container that watches for Tab. Suppressing the rules would have claimed otherwise, and
   * inventing a `role="presentation"` or a `tabIndex` to quiet them would have put semantics on
   * the page for a linter's benefit. A listener on the node says exactly what is true.
   *
   * One effect for both, on `[]`: the two nodes live and die with this component.
   */
  useEffect(() => {
    const dialog = dialogRef.current
    const scrim = scrimRef.current
    if (dialog === null || scrim === null) return

    // TAB CYCLES WITHIN THE VIEW (AC 2, UX-DR44, EXPERIENCE.md:142).
    //
    // The app's first focus trap, and deliberately the small kind: it wraps at the two ends and
    // does nothing else. Nothing is made `inert` and no listener watches for focus escaping — a
    // shell that fought the browser for focus would be a shell that could strand it.
    //
    // The wrap is asserted by `AgentView.test.tsx` as ARITHMETIC — which element it moves focus
    // to, given which element has it — and never by tabbing, because jsdom implements no
    // sequential focus navigation: pressing Tab there moves nothing, so a test that "tabbed to
    // the end" would be asserting its own `fireEvent` calls.
    const trapTab = (event: globalThis.KeyboardEvent) => {
      if (event.key !== 'Tab' || event.isComposing || event.defaultPrevented) return
      const focusables = focusablesIn(dialog)
      // A shell with no focusable descendant at all: let Tab do whatever the browser would.
      // Unreachable while the close pill ships, and cheaper than a crash if a later story ever
      // conditions the pill away.
      if (focusables.length === 0) return

      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      const active = document.activeElement
      // The heading holds focus on open and is NOT in this list (`focusHome` gives it
      // `tabindex="-1"`), so "focus is inside the view but not on a trap stop" is the ordinary
      // opening state rather than an edge case. Backwards from there wraps to the end; forwards
      // falls through to the browser, which finds the pill by document order.
      const inTrap = active instanceof HTMLElement && focusables.includes(active)

      if (event.shiftKey && (active === first || !inTrap)) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault()
        first.focus()
      }
    }

    const onScrimMouseDown = (event: globalThis.MouseEvent) => {
      const onScrim = event.target === scrim
      scrimMouseDownOnScrimRef.current = onScrim
      // A mousedown on a non-focusable element blurs whatever currently holds focus by
      // default (found at code review, 2026-08-10) — which would put the trap's forward-Tab
      // branch in the one state it doesn't recognize as "inside." Suppressed only when the
      // press is on the scrim itself, so a real control elsewhere in the panel still takes
      // focus on click exactly as a `<button>` should.
      if (onScrim) event.preventDefault()
    }

    const onScrimMouseUp = (event: globalThis.MouseEvent) => {
      scrimMouseUpOnScrimRef.current = event.target === scrim
    }

    const onScrimClick = () => {
      const dismissed = scrimMouseDownOnScrimRef.current && scrimMouseUpOnScrimRef.current
      scrimMouseDownOnScrimRef.current = false
      scrimMouseUpOnScrimRef.current = false
      if (dismissed) onCloseRef.current()
    }

    dialog.addEventListener('keydown', trapTab)
    scrim.addEventListener('mousedown', onScrimMouseDown)
    scrim.addEventListener('mouseup', onScrimMouseUp)
    scrim.addEventListener('click', onScrimClick)
    return () => {
      dialog.removeEventListener('keydown', trapTab)
      scrim.removeEventListener('mousedown', onScrimMouseDown)
      scrim.removeEventListener('mouseup', onScrimMouseUp)
      scrim.removeEventListener('click', onScrimClick)
    }
  }, [])

  // `Number.isFinite`, and never `count &&` or `count ?` — `Panel.tsx:73-80`'s reasoning
  // verbatim, in the second component to take a numeric count prop.
  const counted = Number.isFinite(count)

  return (
    <div
      ref={scrimRef}
      className="agent-view-scrim"
      /* NO `role` and NO `aria-hidden`. The scrim is paint: it carries the backdrop blur and it
         catches a click, and both of those are things a `<div>` does without being announced.
         `aria-hidden` here would hide the dialog it contains. Its two pointer listeners are
         attached natively — see the effect above for why that is the honest shape rather than a
         lint dodge. */
    >
      <div
        ref={dialogRef}
        className="agent-view"
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        data-entering={entering ? 'true' : 'false'}
      >
        <header className="agent-view-header">
          <p className="agent-view-kicker">{AGENT_VIEW_KICKER}</p>
          {/* `aria-live="polite"` on the HEADING — one of exactly three live regions in the app
              (`EXPERIENCE.md:159`; the other two are CardDetail's pin announcement and the
              connection pill's). Nothing announces on FIRST open: no announcement is specified
              anywhere for it, and focus moving here is the open-time signal (AC 3). What the
              region is for is c6-6's replacement — one view swapped for another under a reader
              who is already inside it. */}
          <h2 ref={headingRef} className="agent-view-title" id={headingId} aria-live="polite">
            {title}
          </h2>
          {counted ? <p className="agent-view-count">{count}</p> : null}
          <button type="button" className="agent-view-close" onClick={onClose}>
            {CLOSE_PILL_LABEL}
          </button>
        </header>
        {/* THE ONE SCROLL CONTAINER (AC 1 — *"the body scrolls while the shell does not"*).
            The overflow lives here rather than on `.agent-view`, so the header row stays put
            while a long list moves under it. */}
        <div className="agent-view-body">{children}</div>
      </div>
    </div>
  )
}
