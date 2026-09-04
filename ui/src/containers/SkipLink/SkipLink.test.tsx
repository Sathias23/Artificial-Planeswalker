import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { SKIP_TARGET_ID } from '../focusHome'
import { SkipLink } from './SkipLink'
import { SKIP_LINK_LABEL } from './copy'

/**
 * The skip link, in isolation.
 *
 * ================= WHAT THIS FILE CAN AND CANNOT SEE ==================================
 *
 * **jsdom has no layout and no sequential focus navigation.** `getBoundingClientRect()` is
 * zeroes, so the 24×24 hit box is a SOURCE claim here (`shell.test.ts` reads the declarations)
 * and a MEASURED one only in the eye-check. And there is no built-in Tab traversal at all, which
 * is why `userEvent` is not installed: `userEvent.tab()` walks its own heuristic list of
 * tabbable elements, so a test built on it asserts user-event's model of the DOM rather than this
 * app's. Tab ORDER is therefore asserted as DOCUMENT ORDER over a rendered tree, following
 * `CardTile.test.tsx:595-605`, and the real key is pressed in the eye-check.
 *
 * **What it CAN see, and what makes these tests worth having**: that focus actually moves, and
 * where to. `document.activeElement` is real in jsdom, and `.focus()` on an element with
 * `tabIndex = -1` genuinely moves it.
 */

/**
 * The panel this link targets, reduced to the two facts the link depends on: an element carrying
 * `SKIP_TARGET_ID`, containing an `<h2>`.
 *
 * A STAND-IN RATHER THAN THE REAL `CardDetail`, and the reason is that the alternative would be
 * WORSE COVERAGE, not merely slower: rendering the real panel here would couple this file to the
 * card cache, the inspection slice and the deck derivation, and a failure in any of those would
 * read as a skip-link failure. The coupling that actually matters — that the panel really carries
 * this id and really renders an `<h2>` — is asserted against the real component in
 * `CardDetail.test.tsx` and end-to-end in `App.test.tsx`. This file tests the link.
 *
 * DECLARED SYNTHETIC IN PLACE: the heading text below is not `PANEL_TITLE` and is not
 * meant to be. Importing that constant would make this fixture look like a copy of the panel and
 * invite the reader to trust it as one.
 */
const targetPanel = (headingText = 'Stand-in heading') => (
  <div id={SKIP_TARGET_ID}>
    <h2>{headingText}</h2>
  </div>
)

describe('the skip link is a real control with a real name (UX-DR47)', () => {
  it('renders a real <button> carrying the canonical string', () => {
    render(<SkipLink />)
    const link = screen.getByRole('button', { name: SKIP_LINK_LABEL })

    // A REAL `<button>`, not a `tabIndex` on a div — UX-DR47, and the same pin
    // `CardTile.test.tsx:788-797` and `DeckList.tsx:151-159` carry for their own controls.
    expect(link.tagName).toBe('BUTTON')
    // `type="button"`: the default is `submit`, and a submit button inside a future form would
    // navigate rather than skip. Cheap to get wrong, invisible until there is a form.
    expect(link.getAttribute('type')).toBe('button')
  })

  it('carries NO tabindex — it is a button, so it is already in the Tab order', () => {
    render(<SkipLink />)
    const link = screen.getByRole('button', { name: SKIP_LINK_LABEL })

    // A positive `tabindex` is the obvious way to make something "first" and it is the wrong one:
    // it would be a new doctrine for this app, whose Tab order is DOCUMENT ORDER. What
    // makes this link first is its POSITION — `AppShell` renders it before the `<header>`.
    expect(link.hasAttribute('tabindex')).toBe(false)
  })

  it('adds no aria-live and announces nothing', () => {
    const { container } = render(<SkipLink />)

    // This component announces nothing — its accessible name is the announcement. Asserted here
    // so a later change cannot add "an announcement for the skip" without a red test.
    expect(container.querySelectorAll('[aria-live]')).toHaveLength(0)
    expect(container.querySelectorAll('[role="status"]')).toHaveLength(0)
    expect(container.querySelectorAll('[role="alert"]')).toHaveLength(0)
  })

  it('is visually hidden by class, not by an attribute that would unname it', () => {
    render(<SkipLink />)
    const link = screen.getByRole('button', { name: SKIP_LINK_LABEL })

    // The clip-rect idiom keeps the element in the accessibility tree; `hidden`, `display: none`
    // and `aria-hidden` all remove it, which would make the link unreachable BY THE ONLY USERS IT
    // EXISTS FOR — a failure that renders identically to a correct implementation on screen.
    expect(link.className.split(' ')).toContain('visually-hidden')
    expect(link.hasAttribute('hidden')).toBe(false)
    expect(link.getAttribute('aria-hidden')).toBeNull()
    // …and `getByRole` above already proves it is still in the tree with its name intact, which is
    // the assertion the three absences exist to protect.
  })

  it('adds NO `onKeyDown` — Enter and Space are the browser’s', () => {
    // A real `<button>` turns both into a `click`, which is why there is no key handler to write
    // and why writing one would be the bug: a `keydown` handler beside the browser's own
    // activation would move focus TWICE for one Enter. `FlipControl.test.tsx:392-407`'s
    // precedent: a jsdom `fireEvent.keyDown` does not synthesise the browser's click, so a key
    // handler is the ONLY thing that could react here — and nothing may.
    render(
      <>
        <SkipLink />
        {targetPanel()}
      </>,
    )
    const link = screen.getByRole('button', { name: SKIP_LINK_LABEL })
    link.focus()

    fireEvent.keyDown(link, { key: 'Enter' })
    fireEvent.keyDown(link, { key: ' ' })
    // No handler fired: focus never moved to the target heading.
    expect(document.activeElement).toBe(link)

    // …and the click the browser WOULD synthesise does move it, so the assertion above is about
    // the absence of a second handler rather than about the control being inert.
    link.click()
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'Stand-in heading' }))
  })

  it('introduces no landmark of its own', () => {
    // `AppShell.test.tsx` pins the landmark count with a STAND-IN in the `skipLink` slot, so a
    // `<nav>`/`<aside>` wrapper added HERE would keep every shell test green while moving the
    // landmark count the artefacts pin at three. Asserted against the real component: the button
    // is the root, and nothing in the subtree carries a landmark role.
    const { container } = render(<SkipLink />)
    expect(container.firstElementChild?.tagName).toBe('BUTTON')
    expect(
      container.querySelectorAll('nav, aside, header, footer, main, section, form'),
    ).toHaveLength(0)
    expect(
      container.querySelectorAll(
        '[role="navigation"], [role="banner"], [role="contentinfo"], [role="main"], ' +
          '[role="complementary"], [role="region"], [role="search"], [role="form"]',
      ),
    ).toHaveLength(0)
  })
})

describe('activating it moves focus to the panel heading', () => {
  it('focuses the target panel’s <h2>, and leaves no [tabindex] behind after blur', () => {
    render(
      <>
        <SkipLink />
        {targetPanel()}
      </>,
    )
    const link = screen.getByRole('button', { name: SKIP_LINK_LABEL })
    const heading = screen.getByRole('heading', { name: 'Stand-in heading' })

    // Focus starts on the link, exactly as a real first Tab would leave it.
    link.focus()
    expect(document.activeElement).toBe(link)

    link.click()

    // THE WHOLE POINT: focus is now past the grid, on the right column's first heading.
    expect(document.activeElement).toBe(heading)
    // `tabIndex = -1`, so the heading took focus WITHOUT becoming a Tab stop of its own.
    expect(heading.getAttribute('tabindex')).toBe('-1')

    // …and the attribute leaves with the focus, so the panel AT REST carries no `[tabindex]` —
    // which is what `CardDetail`'s not-a-modal assertion checks one file over.
    heading.blur()
    expect(heading.hasAttribute('tabindex')).toBe(false)
  })

  it('does nothing at all when the target is absent, rather than throwing', () => {
    // Reachable in principle: the link is gated on a deck with at least one card, but a render
    // between those two commits would have a link and no panel. An exception inside an onClick
    // surfaces as a control that "does nothing" ANYWAY — this just makes it honestly nothing.
    render(<SkipLink />)
    const link = screen.getByRole('button', { name: SKIP_LINK_LABEL })
    link.focus()

    expect(() => link.click()).not.toThrow()
    // Focus stays where it was rather than being dropped to <body> — the failure mode the
    // withdrawal rule bans.
    expect(document.activeElement).toBe(link)
  })

  it('does not reach a heading that is NOT inside the target (the non-vacuity anchor)', () => {
    // WITHOUT THIS, the test above passes for the wrong reason. A lookup written
    // `document.querySelector('h2')` — the obvious simplification — would find the FIRST h2 in
    // the document and pass every assertion above, while in the real app that is the MANA CURVE's
    // heading, because the left column precedes the right in document order. This is that mistake,
    // reproduced: a decoy h2 rendered BEFORE the real target.
    render(
      <>
        <SkipLink />
        <h2>Mana curve (the decoy — first in document order)</h2>
        {targetPanel('The real target')}
      </>,
    )
    const link = screen.getByRole('button', { name: SKIP_LINK_LABEL })
    link.focus()
    link.click()

    expect(document.activeElement).toBe(screen.getByRole('heading', { name: 'The real target' }))
    expect(document.activeElement).not.toBe(screen.getByRole('heading', { name: /decoy/ }))
  })
})

describe('withdrawal never drops focus to document.body', () => {
  it('hands focus to the h1 when it unmounts WHILE FOCUSED', () => {
    const { rerender } = render(
      <>
        <h1>Atraxa Counter Cabinet</h1>
        <SkipLink />
      </>,
    )
    const link = screen.getByRole('button', { name: SKIP_LINK_LABEL })
    link.focus()
    expect(document.activeElement).toBe(link)

    // The withdrawal: a state panel takes the left column, so the link is gone. React removing the
    // focused node drops focus to <body> and Tab restarts from the top of the page — the exact
    // failure `CardDetail.tsx:385-388` records for the unpin control.
    rerender(
      <>
        <h1>Atraxa Counter Cabinet</h1>
      </>,
    )

    const h1 = screen.getByRole('heading', { level: 1 })
    expect(document.activeElement).toBe(h1)
    expect(document.activeElement).not.toBe(document.body)

    h1.blur()
    expect(h1.hasAttribute('tabindex')).toBe(false)
  })

  it('does NOT steal focus when it unmounts without having it', () => {
    // The half that makes the fix a fix rather than a new bug. If the cleanup ran unconditionally,
    // every withdrawal would yank focus to the h1 from wherever the user actually was — which is
    // worse than the defect, and invisible to a test that only checks the focused case.
    render(
      <>
        <h1>Atraxa Counter Cabinet</h1>
        <button type="button">Somewhere else entirely</button>
      </>,
    )
    const elsewhere = screen.getByRole('button', { name: 'Somewhere else entirely' })

    const { rerender } = render(<SkipLink />)
    elsewhere.focus()
    expect(document.activeElement).toBe(elsewhere)

    rerender(<></>)

    // Focus is untouched: the link never had it, so its departure is none of its business.
    expect(document.activeElement).toBe(elsewhere)
  })

  it('does NOT steal focus when it had focus but something else already took it', () => {
    // The third arm, and the one a two-case test would miss: the link held focus, then lost it to
    // another element BEFORE unmounting. `onBlur` clears the flag, so the cleanup stays out of it.
    render(
      <>
        <h1>Atraxa Counter Cabinet</h1>
        <button type="button">Took it next</button>
      </>,
    )
    const next = screen.getByRole('button', { name: 'Took it next' })

    const { rerender } = render(<SkipLink />)
    const link = screen.getByRole('button', { name: SKIP_LINK_LABEL })
    link.focus()
    next.focus()

    rerender(<></>)

    expect(document.activeElement).toBe(next)
  })
})
