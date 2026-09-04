import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AgentView } from './AgentView'
import { AGENT_VIEW_KICKER, CLOSE_PILL_LABEL } from './copy'

/**
 * The agent view shell.
 *
 * ================= WHAT THIS SUITE CANNOT CARRY, SAID FIRST ============================
 *
 * jsdom evaluates no stylesheet, resolves no media query, performs no layout and implements no
 * sequential focus navigation. Four consequences, stated rather than discovered:
 *
 *   - **Nothing here proves the scrim is dark, the blur is 16px, the panel carries the raise
 *     elevation or that the body is the only thing that scrolls.** `toHaveClass` proves the
 *     class was EMITTED, not that anything was painted. Those claims are held by
 *     `token-usage.test.ts` and `shell.test.ts` reading the stylesheet as source, and finally
 *     by eye on the manual checklist.
 *   - **Nothing here proves the bloom animates.** What is asserted is the STATE the animation
 *     transitions out of, which is the half a source reader and a stylesheet gate can both see.
 *   - **Pressing Tab moves nothing.** So the trap is asserted as the handler's arithmetic —
 *     given which element holds focus, which element does it move focus to — and never by
 *     tabbing and looking. A test that "tabbed to the end" would be asserting its own
 *     `fireEvent` calls.
 *   - **`@testing-library/user-event` is not installed, deliberately.** `fireEvent`
 *     and hand-dispatched events only.
 *
 * ================= WHY ESC IS DISPATCHED AT AN ELEMENT AND NOT AT `document` ===========
 *
 * `CardDetail.test.tsx:508-525` dispatches its Esc on `document`, which is correct for a suite
 * with ONE listener in it. It would be wrong here, and the reason is the whole mechanism this
 * shell exists to land: when an event's target IS `document`, every listener on `document` runs
 * in the AT_TARGET phase — capture and bubble alike, in registration order — and
 * `stopPropagation()` does not stop a sibling listener on the same node. A test that dispatched
 * there would prove nothing about layering and could pass or fail on import order.
 *
 * Dispatching at an ELEMENT is also what really happens: a `keydown` targets whatever has focus.
 * `document` is then a genuine ancestor, capture runs before the target and bubble after it, and
 * `stopPropagation()` in the capture listener means the bubble listener is never reached. That
 * is the property `CardDetail.tsx:89-101` and `inspection.ts:55-67` declare, and it is tested
 * below.
 */

const TITLE = 'Suggestions for Atraxa Counter Cabinet'

/**
 * The shell over an arbitrary child, plus the two things the focus arms need around it: an
 * `<h1>` (the disconnected-restore fallback's target, and the app really does have exactly one)
 * and outside controls to hand focus back to.
 *
 * `open` toggles the MOUNT, because that is what `App` does — the store closed means an absent
 * `overlay` prop, so "on open" is this component's mount and "on close" is its unmount.
 */
function Harness({
  open = true,
  decoy = true,
  panel = false,
  pushId = 'push-1',
  title = TITLE,
  count = 3,
  onClose = () => {},
}: {
  open?: boolean
  decoy?: boolean
  /**
   * A state panel occupying the left column behind the view — `StatePanel.tsx:115-126`'s
   * headline element, which is the only part of it ARM 3 queries for.
   */
  panel?: boolean
  /** Which push is showing. A CHANGE of this while `open` stays true is a replace. */
  pushId?: string
  title?: string
  count?: number | null
  onClose?: () => void
}) {
  return (
    <>
      <h1>Atraxa Counter Cabinet</h1>
      {panel ? (
        <section className="state-panel" role="region" aria-label="No active deck">
          <h2 className="state-panel-headline">No active deck</h2>
        </section>
      ) : null}
      <button type="button" data-testid="outside-a">
        outside a
      </button>
      {decoy ? (
        <button type="button" data-testid="outside-decoy">
          outside decoy
        </button>
      ) : null}
      {open ? (
        <AgentView pushId={pushId} title={title} count={count} onClose={onClose}>
          <p data-testid="fixture">an arbitrary child</p>
          {/* TWO FOCUSABLE CHILDREN, and they are what make the trap tests non-vacuous. The
              shell's own only focusable is the close pill, so with an inert body the pill is
              both ends of the trap at once and "wrapping to the first" is indistinguishable
              from doing nothing at all. With these, the two ends are DIFFERENT elements and a
              handler that no-opped would fail. They are also the suggestions view's real
              shape: each suggestion row IS a single `<button>`, so a view of six rows puts
              six focusables in the trap between the close pill's two ends. */}
          <button type="button" data-testid="body-first">
            body first
          </button>
          <button type="button" data-testid="body-last">
            body last
          </button>
        </AgentView>
      ) : null}
    </>
  )
}

/** Esc, as a browser really delivers it: at the focused element, bubbling through `document`. */
const pressEscapeOn = (target: Element, init: KeyboardEventInit = {}) => {
  act(() => {
    target.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true, ...init }),
    )
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('the chrome is the shell DESIGN.md specifies (AC 1)', () => {
  it('renders the kicker, the title, the count and the close pill', () => {
    render(<Harness />)

    expect(screen.getByText(AGENT_VIEW_KICKER)).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: TITLE })).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: CLOSE_PILL_LABEL })).toBeInTheDocument()
  })

  it('spells the close pill with a MIDDLE DOT, by codepoint', () => {
    // "Looks like a dot" is exactly the class of difference an eye scanning a diff waves
    // through, so the separator is asserted as U+00B7 with its spaces rather than by eye.
    expect(CLOSE_PILL_LABEL).toBe('Close · esc')
    expect(CLOSE_PILL_LABEL).not.toContain('•')
    expect(CLOSE_PILL_LABEL).not.toContain('-')
  })

  it('renders a count of ZERO — `0` is real content, not an absent count', () => {
    // `Panel.tsx:73-80`'s falsy-value family, in the second component to take a numeric count.
    // `count && …` would put a bare `0` in the DOM and `count ? … : null` would drop a real one.
    render(<Harness count={0} />)
    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('renders NO count when there is nothing to count', () => {
    render(<Harness count={null} />)
    expect(document.querySelector('.agent-view-count')).toBeNull()
  })

  it('renders an arbitrary child and knows nothing about it (content-agnostic)', () => {
    // The claim that lets `SuggestionsView` render suggestion rows without editing this
    // component. The body renders what it is handed, and nothing in the shell mentions a
    // suggestion.
    render(<Harness />)
    expect(screen.getByTestId('fixture')).toBeInTheDocument()
    expect(document.querySelector('.agent-view-body')).toContainElement(
      screen.getByTestId('fixture'),
    )
  })

  it('puts the scroll container on the BODY, not on the shell (AC 1)', () => {
    // EMISSION, not paint — jsdom resolves no `overflow`. What this pins is that the body is a
    // distinct element from the panel, which is the structural half of "the body scrolls while
    // the shell does not"; `AgentView.css` carries the `overflow-y` and the px-citation guard
    // and stylelint read it there.
    render(<Harness />)
    const panel = document.querySelector('.agent-view')
    const body = document.querySelector('.agent-view-body')
    expect(body).not.toBeNull()
    expect(body).not.toBe(panel)
    expect(panel).toContainElement(body as HTMLElement)
  })
})

describe('the semantics are a modal dialog labelled by its heading (AC 2)', () => {
  it('is role=dialog with aria-modal=true', () => {
    render(<Harness />)
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
  })

  it('takes its accessible name from its OWN h2, not from any other heading (non-vacuity)', () => {
    // The decoy is `SkipLink.test.tsx:180-199`'s pattern: an `<h1>` precedes the dialog in
    // document order, so a lookup that reached for "a heading" rather than for THIS heading
    // would find the deck name and this assertion would read it back.
    render(<Harness />)
    const dialog = screen.getByRole('dialog')
    const heading = screen.getByRole('heading', { level: 2, name: TITLE })

    expect(dialog.getAttribute('aria-labelledby')).toBe(heading.id)
    expect(heading.id).not.toBe('')
    expect(dialog).toHaveAccessibleName(TITLE)
    expect(dialog).not.toHaveAccessibleName('Atraxa Counter Cabinet')
  })

  it('gives two mounted shells DIFFERENT heading ids (why it is useId, not a constant)', () => {
    // A hand-written second constant would be a second thing to keep unique. `useId` cannot
    // collide, which is what makes the labelled-by lookup safe in any tree that mounts two.
    render(<Harness />)
    render(<Harness title="A second view" />)
    const ids = screen.getAllByRole('dialog').map((d) => d.getAttribute('aria-labelledby'))

    expect(ids).toHaveLength(2)
    expect(new Set(ids).size).toBe(2)
  })

  it('makes the heading the polite live region EXPERIENCE.md:159 authorises', () => {
    render(<Harness />)
    expect(screen.getByRole('heading', { level: 2, name: TITLE })).toHaveAttribute(
      'aria-live',
      'polite',
    )
  })

  it('declares no positive tabindex anywhere in the shell', () => {
    // `keyboard-floor.test.ts` bans positive tabindex repo-wide, and the trap DEPENDS on that
    // ban: it reads `querySelectorAll` order as tab order, which is only true while nothing
    // reorders the sequence out from under the DOM.
    render(<Harness />)
    for (const element of document.querySelectorAll('[tabindex]')) {
      expect(Number(element.getAttribute('tabindex'))).toBeLessThanOrEqual(0)
    }
  })
})

describe('the entry animation starts from a state and settles (AC 7)', () => {
  // Fake timers ONLY here, and only because this is the one behaviour in the file with a frame
  // in the middle of it. Vitest's fake clock stands in for `requestAnimationFrame`, which is
  // what lets both ENDS of the transition be asserted — the starting state a real-timer test
  // could never catch, and the settled state it would have to wait for.
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('renders IN the entering state, so the transition has somewhere to come from', () => {
    // The half that makes the bloom a bloom rather than an appearance. `AgentView.css` hangs
    // `opacity: 0` and the 8px offset on this exact attribute value, so a component that
    // settled during its own first commit would paint the rest state immediately and animate
    // nothing at all.
    render(<Harness />)
    expect(screen.getByRole('dialog')).toHaveAttribute('data-entering', 'true')
  })

  it('leaves the entering state on the next frame, so the transition runs', () => {
    render(<Harness />)

    act(() => {
      vi.advanceTimersByTime(20)
    })
    expect(screen.getByRole('dialog')).toHaveAttribute('data-entering', 'false')
  })

  it('keys the animation on the attribute the reduced-motion block names (three files agree)', () => {
    // The contract between three files: this component writes the attribute, `AgentView.css`
    // hangs the 8px offset on `[data-entering='true']`, and `tokens.css`'s single
    // reduced-motion block neutralises that exact selector text. `token-usage.test.ts` asserts
    // the last two agree with each other; this asserts the first really emits what they are
    // keyed on — the join none of the three files could check alone.
    render(<Harness />)
    expect(screen.getByRole('dialog').getAttribute('data-entering')).toBe('true')
  })
})

describe('focus moves to the heading on open (AC 3, UX-DR46)', () => {
  it('focuses the h2, not the dialog and not the close pill', () => {
    render(<Harness />)
    expect(document.activeElement).toBe(screen.getByRole('heading', { level: 2, name: TITLE }))
  })

  it('makes the heading focusable WITHOUT leaving a Tab stop behind', () => {
    // `focusHome`'s dance, asserted at its consumer: `tabindex="-1"` while focused, and gone
    // once focus departs. The attribute's absence at rest is what keeps the heading out of the
    // trap's focusable list — which is why the first Tab out of it reaches the close pill.
    render(<Harness />)
    const heading = screen.getByRole('heading', { level: 2, name: TITLE })
    expect(heading).toHaveAttribute('tabindex', '-1')

    act(() => {
      screen.getByRole('button', { name: CLOSE_PILL_LABEL }).focus()
    })
    expect(heading).not.toHaveAttribute('tabindex')
  })
})

describe('focus returns where it came from on close (AC 4, UX-DR39, UX-DR46)', () => {
  it('ARM 1 — restores the element that had focus when the view opened', () => {
    const { rerender } = render(<Harness open={false} />)
    const outside = screen.getByTestId('outside-a')
    act(() => outside.focus())

    rerender(<Harness open />)
    expect(document.activeElement).not.toBe(outside)

    rerender(<Harness open={false} />)
    expect(document.activeElement).toBe(outside)
    expect(document.activeElement).not.toBe(document.body)
  })

  it('ARM 2 — leaves focus alone when something else has already taken it', () => {
    // `SkipLink.tsx:110-112`'s guard: moving focus again would be this component reversing a
    // decision it did not make.
    const { rerender } = render(<Harness open={false} />)
    act(() => screen.getByTestId('outside-a').focus())
    rerender(<Harness open />)

    const elsewhere = screen.getByTestId('outside-decoy')
    act(() => elsewhere.focus())
    rerender(<Harness open={false} />)

    expect(document.activeElement).toBe(elsewhere)
  })

  it('ARM 3 — falls back to the h1 when the remembered element is GONE (Q5)', () => {
    // A control that only existed on a surface that has since changed. Brad's Q5 ruling makes
    // the `<h1>` deck name the destination when NO state panel is showing — and never
    // `document.body`, which is AC 4's own words. c6-6 added the panel arm above it; this is
    // the no-panel half of the same ruling.
    const { rerender } = render(<Harness open={false} />)
    act(() => screen.getByTestId('outside-decoy').focus())
    rerender(<Harness open decoy />)

    // The remembered button leaves the document while the view is open.
    rerender(<Harness open decoy={false} />)
    rerender(<Harness open={false} decoy={false} />)

    expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1 }))
    expect(document.activeElement).not.toBe(document.body)
  })

  it('ARM 3 — prefers the STATE PANEL’s headline when one is showing (c6-6, AC 5, Q5)', () => {
    // EXPERIENCE.md:122 — *"on close, the user lands on the state panel"*. The remembered
    // control is gone precisely BECAUSE the panel replaced the surface it lived on, so this is
    // the ordinary shape of that sentence rather than an edge case.
    const { rerender } = render(<Harness open={false} />)
    act(() => screen.getByTestId('outside-decoy').focus())
    rerender(<Harness open decoy />)

    // The deck is lost while the view is open: the remembered control leaves and a state panel
    // takes the left column. The view itself is untouched — agent content is about cards, not
    // about the deck's presence (UX-DR37).
    rerender(<Harness open decoy={false} panel />)
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    rerender(<Harness open={false} decoy={false} panel />)

    expect(document.activeElement).toBe(document.querySelector('.state-panel-headline'))
    // NON-VACUITY, and the assertion that separates this arm from the one above it: the `<h1>`
    // is still in the document and still the arm's fallback, so landing on the panel is a
    // PREFERENCE that fired rather than the h1 having gone missing.
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(document.activeElement).not.toBe(screen.getByRole('heading', { level: 1 }))
  })

  it('does NOT override a CONNECTED restore target just because a panel is showing (UX-DR46)', () => {
    // The boundary of the fallback, and the rejected alternative. *"Focus returns to the
    // element focused before the view took it"* is not overridden by a panel appearing behind
    // the view — the panel arm is a FALLBACK for a target that no longer exists, and a rule
    // that always chose the panel would be this component reversing a decision it did not make.
    const { rerender } = render(<Harness open={false} panel />)
    const opener = screen.getByTestId('outside-a')
    act(() => opener.focus())

    rerender(<Harness open panel />)
    rerender(<Harness open={false} panel />)

    expect(document.activeElement).toBe(opener)
    expect(document.activeElement).not.toBe(document.querySelector('.state-panel-headline'))
  })

  it('ARM 4 — holds nothing when nothing was focused, and grabs nothing on the way out', () => {
    // Opening with focus on `<body>` records NO restore target, so closing must not invent a
    // destination. The h1 is the fallback for a DISCONNECTED target, not for an absent one.
    const { rerender } = render(<Harness open={false} />)
    expect(document.activeElement).toBe(document.body)

    rerender(<Harness open />)
    rerender(<Harness open={false} />)

    expect(document.activeElement).not.toBe(screen.getByRole('heading', { level: 1 }))
  })
})

describe('Tab cycles within the view (AC 2, UX-DR44)', () => {
  it('reads its focusables in DOCUMENT order — the pill first, the body’s last', () => {
    // The premise the two wrap tests rest on, asserted rather than assumed: the header precedes
    // the body, so the close pill is the trap's first stop and the body's last control is its
    // last. If this ever stopped being true the wraps below would still pass while trapping in
    // the wrong direction.
    render(<Harness />)
    const focusables = [...document.querySelectorAll('.agent-view button')]

    expect(focusables[0]).toBe(screen.getByRole('button', { name: CLOSE_PILL_LABEL }))
    expect(focusables.at(-1)).toBe(screen.getByTestId('body-last'))
  })

  it('wraps forward from the last focusable to the first', () => {
    render(<Harness />)
    const dialog = screen.getByRole('dialog')
    const last = screen.getByTestId('body-last')
    const pill = screen.getByRole('button', { name: CLOSE_PILL_LABEL })
    act(() => last.focus())

    fireEvent.keyDown(dialog, { key: 'Tab' })
    expect(document.activeElement).toBe(pill)
  })

  it('wraps backward from the first focusable to the last', () => {
    render(<Harness />)
    const dialog = screen.getByRole('dialog')
    const pill = screen.getByRole('button', { name: CLOSE_PILL_LABEL })
    act(() => pill.focus())

    fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(screen.getByTestId('body-last'))
  })

  it('does NOT intercept a Tab in the middle of the sequence', () => {
    // The trap wraps at the two ends and does nothing else. Intercepting here would mean the
    // shell was driving the whole tab sequence itself, which is how a trap strands focus.
    render(<Harness />)
    const dialog = screen.getByRole('dialog')
    const middle = screen.getByTestId('body-first')
    act(() => middle.focus())

    // jsdom moves focus for nobody, so "not intercepted" reads as "focus is where it was" —
    // the same assertion shape, distinguished from the wraps by which element that is.
    fireEvent.keyDown(dialog, { key: 'Tab' })
    expect(document.activeElement).toBe(middle)
  })

  it('pulls Shift+Tab from the HEADING into the trap rather than out of the view', () => {
    // The ordinary opening state: focus is on the heading, which `focusHome` made focusable at
    // `tabindex="-1"` and which is therefore NOT a trap stop. Backwards from there would leave
    // the view entirely — into the browser chrome — so it wraps to the last focusable instead.
    render(<Harness />)
    const dialog = screen.getByRole('dialog')
    expect(document.activeElement).toBe(screen.getByRole('heading', { level: 2, name: TITLE }))

    fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(screen.getByTestId('body-last'))
  })

  it('leaves every other key alone', () => {
    // The trap is a Tab handler and nothing else — an over-eager one would eat keys a list may
    // want. Suggestion rows ship with NO `onKeyDown` at all (UX-DR40 rules out a roving-tabindex
    // composite, and a row handler would never see Escape anyway), so nothing in a suggestions view competes for a key today.
    render(<Harness />)
    const dialog = screen.getByRole('dialog')
    const heading = screen.getByRole('heading', { level: 2, name: TITLE })

    fireEvent.keyDown(dialog, { key: 'ArrowDown' })
    expect(document.activeElement).toBe(heading)
  })
})

describe('the three dismissal gestures (AC 4)', () => {
  it('closes on the close pill, which is a REAL button (so Enter and Space work)', () => {
    // The Enter/Space half is carried by the ELEMENT rather than by a handler: a real
    // `<button>` fires `click` for both keys, and adding an `onKeyDown` "for keyboard support"
    // would double-fire (`SkipLink.tsx:133-136`). jsdom synthesises no click from a key, so
    // what is provable here is the element kind and the absence of a key handler — the two
    // things that make the browser's behaviour the shell's behaviour.
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    const pill = screen.getByRole('button', { name: CLOSE_PILL_LABEL })

    expect(pill.tagName).toBe('BUTTON')
    expect(pill).toHaveAttribute('type', 'button')

    fireEvent.keyDown(pill, { key: 'Enter' })
    expect(onClose, 'the pill must carry no onKeyDown of its own').not.toHaveBeenCalled()

    fireEvent.click(pill)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on Esc', () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)

    pressEscapeOn(screen.getByRole('button', { name: CLOSE_PILL_LABEL }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on a scrim click that BOTH pressed and released on the scrim', () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    const scrim = document.querySelector('.agent-view-scrim') as HTMLElement

    fireEvent.mouseDown(scrim)
    fireEvent.mouseUp(scrim)
    fireEvent.click(scrim)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does NOT close when a drag started on the panel and ended on the scrim (Q3)', () => {
    // The paper cut a bare `click` handler ships: selecting a line of text inside the panel and
    // releasing outside it fires `click` on their common ancestor, which is the scrim. Both
    // ends of the gesture must be the scrim.
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    const scrim = document.querySelector('.agent-view-scrim') as HTMLElement

    fireEvent.mouseDown(screen.getByTestId('fixture'))
    fireEvent.mouseUp(scrim)
    fireEvent.click(scrim)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('does NOT close when a drag started on the scrim and ended on the panel (the Q3 mirror, found at code review)', () => {
    // The symmetric paper cut: a press that lands on the scrim — a misaimed click near the
    // shell's edge — and releases over panel content still fires `click` on their common
    // ancestor, the scrim. Requiring BOTH ends of the gesture to be the scrim closes this
    // side too, not just the panel-to-scrim one above.
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    const scrim = document.querySelector('.agent-view-scrim') as HTMLElement

    fireEvent.mouseDown(scrim)
    fireEvent.mouseUp(screen.getByTestId('fixture'))
    fireEvent.click(scrim)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('does NOT close on a click INSIDE the panel', () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)

    fireEvent.mouseDown(screen.getByTestId('fixture'))
    fireEvent.click(screen.getByTestId('fixture'))
    expect(onClose).not.toHaveBeenCalled()
  })

  it('prevents the default on a scrim mousedown, so the browser does not blur focus out of the trap (found at code review)', () => {
    // A mousedown on a non-focusable element blurs whatever currently holds focus, by browser
    // default — which would strand the trap's forward-Tab branch in the one state it doesn't
    // recognize as "inside" (`document.activeElement === document.body`). `fireEvent` returns
    // `dispatchEvent`'s own result, which is `false` only when a cancelable event was cancelled.
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    const scrim = document.querySelector('.agent-view-scrim') as HTMLElement

    expect(fireEvent.mouseDown(scrim)).toBe(false)
  })

  it('does NOT prevent the default on a mousedown INSIDE the panel (non-vacuity)', () => {
    // The suppression above is scoped to the scrim itself — a control elsewhere in the panel
    // must still take focus on click exactly as a `<button>` should.
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)

    expect(fireEvent.mouseDown(screen.getByTestId('fixture'))).toBe(true)
  })

  it('ignores an Esc that is cancelling an IME composition', () => {
    // `CardDetail.tsx:371-375`'s guards, inherited: reachable the moment a text input lands on
    // the page.
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)

    pressEscapeOn(screen.getByTestId('fixture'), { isComposing: true })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('ignores an Esc another handler has already consumed', () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)

    // `window` capture runs before `document` capture, so this really does arrive
    // `defaultPrevented` at the shell's listener — the ordering a browser would produce.
    const consume = (event: Event) => event.preventDefault()
    window.addEventListener('keydown', consume, true)
    try {
      pressEscapeOn(screen.getByTestId('fixture'))
    } finally {
      window.removeEventListener('keydown', consume, true)
    }

    expect(onClose).not.toHaveBeenCalled()
  })

  it('ignores every other key', () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)

    act(() => {
      screen
        .getByTestId('fixture')
        .dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    })
    expect(onClose).not.toHaveBeenCalled()
  })
})

describe('Esc closes the view and NOTHING ELSE — the layering (UX-DR39, EXPERIENCE.md:141)', () => {
  /**
   * THE TEST `CardDetail.tsx:99-101` AND `inspection.ts:65-67` PROMISE.
   *
   * Both files declare the layering untestable without an overlay. This is the overlay, and
   * this is the layering.
   *
   * The stand-in below is a document BUBBLE `keydown` listener — which is precisely what
   * `CardDetail` registers (`CardDetail.tsx:369-380`), same receiver, same event, same phase.
   * It stands in rather than mounting `CardDetail` because that component needs a deck, a card
   * cache and a hydration path to exist, none of which this claim depends on; the claim is
   * about EVENT PHASE, and the end-to-end version over a real pin lives in `App.test.tsx`.
   */
  it('never lets the event reach a document BUBBLE listener (the pin survives)', () => {
    const onClose = vi.fn()
    const pinRelease = vi.fn()
    render(<Harness onClose={onClose} />)

    document.addEventListener('keydown', pinRelease)
    try {
      pressEscapeOn(screen.getByTestId('fixture'))
    } finally {
      document.removeEventListener('keydown', pinRelease)
    }

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(
      pinRelease,
      'the capture listener must stopPropagation() — one Esc closing the view AND releasing ' +
        'the pin is the regression dw:4766-4773 was written about',
    ).not.toHaveBeenCalled()
  })

  it('holds even when focus sits on <body>, which is why it is not element-scoped', () => {
    // The hole the first written form of this contract had: a
    // `keydown` targeting `<body>` never passes through the overlay's subtree, so a handler
    // scoped to the overlay could not pre-empt anything. A document capture listener sees it.
    const onClose = vi.fn()
    const pinRelease = vi.fn()
    render(<Harness onClose={onClose} />)
    act(() => (document.activeElement as HTMLElement | null)?.blur())

    document.addEventListener('keydown', pinRelease)
    try {
      pressEscapeOn(document.body)
    } finally {
      document.removeEventListener('keydown', pinRelease)
    }

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(pinRelease).not.toHaveBeenCalled()
  })

  it('leaves the bubble listener working once the view has closed (non-vacuity)', () => {
    // Without this, the two assertions above would pass just as well if the stand-in listener
    // were never wired up at all. It also proves the shell's listener is removed on unmount —
    // an always-mounted capture listener would swallow Esc for the pin when no view is
    // showing, which inverts UX-DR39 rather than implementing it.
    const pinRelease = vi.fn()
    const { rerender } = render(<Harness />)
    rerender(<Harness open={false} />)

    document.addEventListener('keydown', pinRelease)
    try {
      pressEscapeOn(screen.getByTestId('outside-a'))
    } finally {
      document.removeEventListener('keydown', pinRelease)
    }

    expect(pinRelease).toHaveBeenCalledTimes(1)
  })
})

// =====================================================================================
// A SECOND PUSH REPLACES THE CONTENT IN PLACE
// =====================================================================================

describe('a replace re-fires what a remount would have, and nothing it must not (c6-6, AC 2)', () => {
  // Fake timers for the entry-animation block's reason, and one more of this block's own: the
  // crossfade's attribute lives for exactly one frame, so both ends of it are only observable
  // with the clock under test control.
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  /** Open, settle the bloom, and leave focus wherever the mount effects put it. */
  const openedAndSettled = (props: Parameters<typeof Harness>[0] = {}) => {
    const view = render(<Harness {...props} />)
    act(() => {
      vi.advanceTimersByTime(20)
    })
    return view
  }

  const heading = () => screen.getByRole('heading', { level: 2 })

  it('moves focus BACK to the heading when a new push arrives (UX-DR45, UX-DR46)', () => {
    const { rerender } = openedAndSettled()
    // Focus is put somewhere real inside the view first, so "focus is on the heading" afterwards
    // is a MOVE rather than the mount effect's leftover. Without this the assertion would pass
    // over a component that does nothing on replace at all.
    act(() => screen.getByTestId('body-last').focus())
    expect(document.activeElement).toBe(screen.getByTestId('body-last'))

    rerender(<Harness pushId="push-2" title="A second look" />)

    expect(document.activeElement).toBe(heading())
  })

  it('does NOT re-fire on a re-render that is not a new push', () => {
    // The other half of the claim above: the effect is keyed on identity, not on rendering. A
    // dependency-less effect would drag focus back to the heading on every parent render and
    // make the view impossible to interact with.
    const { rerender } = openedAndSettled()
    act(() => screen.getByTestId('body-last').focus())

    rerender(<Harness pushId="push-1" title="A retitled same push" />)

    expect(document.activeElement).toBe(screen.getByTestId('body-last'))
  })

  it('does NOT re-fire for a REPEAT of the id already showing (AD-6 de-duplication)', () => {
    // `id` is the wire's de-duplication field, so a frame repeating one is the wire saying "you
    // already have this". Re-announcing it would be the app disagreeing with the only authority
    // on the question. Stated in the effect's own comment rather than left to be discovered.
    const { rerender } = openedAndSettled({ pushId: 'push-9' })
    act(() => screen.getByTestId('body-first').focus())

    rerender(<Harness pushId="push-9" />)

    expect(document.activeElement).toBe(screen.getByTestId('body-first'))
  })

  it('does NOT re-run the entry bloom — the crossfade is a different motion', () => {
    // A `key` on `<AgentView>` would remount and replay the 480 ms fade-plus-rise. A replace is
    // a 240 ms opacity crossfade, which is the reason `App.tsx` carries no key and this
    // assertion is what would fail if one were added.
    const { rerender } = openedAndSettled()
    expect(screen.getByRole('dialog')).toHaveAttribute('data-entering', 'false')

    rerender(<Harness pushId="push-2" />)

    expect(screen.getByRole('dialog')).toHaveAttribute('data-entering', 'false')
  })

  it('flips the crossfade attribute on, and off again on the next frame', () => {
    const { rerender } = openedAndSettled()
    expect(screen.getByRole('dialog')).toHaveAttribute('data-replacing', 'false')

    rerender(<Harness pushId="push-2" />)
    // The starting state the transition comes FROM — `AgentView.css` hangs `opacity: 0` on this
    // exact attribute value for the title and the body. A swap that settled inside its own
    // commit would paint the rest state immediately and cross-fade nothing.
    expect(screen.getByRole('dialog')).toHaveAttribute('data-replacing', 'true')

    act(() => {
      vi.advanceTimersByTime(20)
    })
    expect(screen.getByRole('dialog')).toHaveAttribute('data-replacing', 'false')
  })

  it('MUTATES the live region even when the new title is byte-identical (Q4)', async () => {
    // THE ASSERTION THIS WHOLE MECHANISM EXISTS FOR. `aria-live` announces on DOM MUTATION, and
    // re-rendering the same string is not one — while the COMMON case is exactly that, because
    // an agent that omits `payload.title` gets the same fallback word twice. A `MutationObserver`
    // is the only thing in jsdom that can tell "React re-rendered" from "the DOM changed".
    const { rerender } = openedAndSettled({ title: 'Suggestions' })
    const region = heading()
    expect(region).toHaveAttribute('aria-live', 'polite')

    const records: MutationRecord[] = []
    const observer = new MutationObserver((list) => records.push(...list))
    observer.observe(region, { childList: true, characterData: true, subtree: true })
    try {
      rerender(<Harness pushId="push-2" title="Suggestions" />)
      await act(async () => {})
    } finally {
      observer.disconnect()
    }

    expect(records.length).toBeGreaterThan(0)
    // …and the region still says the right thing afterwards. A mutation that emptied the heading
    // would satisfy the count above and destroy the dialog's accessible name.
    expect(region).toHaveTextContent('Suggestions')
  })

  it('does not mutate the live region when nothing was pushed (non-vacuity)', async () => {
    // The counterweight: without it, the observer above could be recording React's ordinary
    // re-render churn rather than the keyed replacement, and the claim would be about nothing.
    const { rerender } = openedAndSettled({ title: 'Suggestions' })
    const region = heading()

    const records: MutationRecord[] = []
    const observer = new MutationObserver((list) => records.push(...list))
    observer.observe(region, { childList: true, characterData: true, subtree: true })
    try {
      rerender(<Harness pushId="push-1" title="Suggestions" />)
      await act(async () => {})
    } finally {
      observer.disconnect()
    }

    expect(records).toEqual([])
  })

  it('renders the NEW content — the header really is the second push’s', () => {
    const { rerender } = openedAndSettled()

    rerender(<Harness pushId="push-2" title="A second look" count={7} />)

    expect(screen.getByRole('heading', { level: 2, name: 'A second look' })).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toHaveAccessibleName('A second look')
  })

  it('keeps the SAME dialog element across the replace — in place is in place', () => {
    // Node identity, not appearance. A remount would satisfy every content assertion above and
    // fail this one, which is what makes it the load-bearing half of "in place".
    const { rerender } = openedAndSettled()
    const before = screen.getByRole('dialog')

    rerender(<Harness pushId="push-2" title="A second look" />)

    expect(screen.getByRole('dialog')).toBe(before)
  })

  it('leaves the RESTORE TARGET untouched, so closing after a replace still returns focus', () => {
    // The return-focus hazard, as an assertion. At replace time focus is inside the view, so a
    // mechanism that re-captured `document.activeElement` would remember the heading — and
    // closing would return focus to the view's own corpse while every other test here stayed
    // green.
    const { rerender } = render(<Harness open={false} />)
    act(() => screen.getByTestId('outside-a').focus())
    const opener = screen.getByTestId('outside-a')

    rerender(<Harness open />)
    act(() => {
      vi.advanceTimersByTime(20)
    })
    rerender(<Harness open pushId="push-2" title="A second look" />)
    expect(document.activeElement).toBe(heading())

    rerender(<Harness open={false} pushId="push-2" />)

    expect(document.activeElement).toBe(opener)
  })

  it('treats a push arriving while CLOSED as an open — bloom and all', () => {
    // The third arrival case. The overlay is absent while the store is closed, so this is a real
    // mount and the mount-only effects own it; the replace effect's ref is initialised to the
    // new id and its mount run does nothing.
    const { rerender } = render(<Harness open={false} />)
    act(() => screen.getByTestId('outside-a').focus())

    rerender(<Harness open pushId="push-2" title="A second look" />)

    expect(screen.getByRole('dialog')).toHaveAttribute('data-entering', 'true')
    expect(document.activeElement).toBe(heading())
  })
})
