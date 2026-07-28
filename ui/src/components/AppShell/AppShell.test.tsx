/**
 * The component half of story c2-6 — the landmarks, the slots and the overlay's presence.
 *
 * WHAT THIS FILE CAN AND CANNOT ASSERT, said once at the top because it governs every test
 * below. jsdom has NO LAYOUT ENGINE: it resolves no grid tracks, evaluates no media query and
 * returns no box geometry, so `getComputedStyle(el).gridTemplateColumns` here is not "452px
 * fixed, fluid beside it" — it is the empty string. Every geometry assertion in this story
 * therefore reads the CSS SOURCE, in `ui/tests/shell.test.ts`, and never a rendered DOM.
 * What lives here is what jsdom genuinely knows: the accessibility tree, the element
 * structure, and whether a node exists at all.
 *
 * Assertions go through @testing-library by ROLE rather than by class name, which is what
 * makes AC 14's landmark requirement a real check rather than a decorative one. The one
 * exception is the overlay slot, which is an unstyled positioning container with no role by
 * design — its own test says so.
 */

import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AppShell } from './AppShell'

describe('AppShell landmarks (AC 14, Q4)', () => {
  it('renders exactly one banner, one main and one contentinfo', () => {
    render(<AppShell />)

    expect(screen.getAllByRole('banner')).toHaveLength(1)
    expect(screen.getAllByRole('main')).toHaveLength(1)
    expect(screen.getAllByRole('contentinfo')).toHaveLength(1)
  })

  it('puts BOTH columns inside the single main landmark', () => {
    render(<AppShell left={<p>left column content</p>} right={<p>right column content</p>} />)

    const main = within(screen.getByRole('main'))
    expect(main.getByText('left column content')).toBeInTheDocument()
    expect(main.getByText('right column content')).toBeInTheDocument()
  })

  it('does not mark the right column complementary (Q4 — it is not an <aside>)', () => {
    // The deck list is FR-05's PRIMARY content, satisfied as a permanent second column
    // rather than a toggled alternate view. `complementary` would demote exactly the thing
    // the redesign promoted, so the absence of that role is the assertion.
    render(<AppShell right={<p>deck list</p>} />)

    expect(screen.queryByRole('complementary')).not.toBeInTheDocument()
  })
})

describe('AppShell header (AC 15, AC 15b, Q3)', () => {
  it('carries the product kicker and an h1', () => {
    render(<AppShell />)

    const banner = within(screen.getByRole('banner'))
    expect(banner.getByRole('heading', { level: 1 })).toHaveTextContent('Artificial Planeswalker')
    expect(banner.getByText('Artificial Planeswalker', { selector: 'span' })).toBeVisible()
  })

  it('lets c4-2 replace the h1 CONTENT without restructuring the header', () => {
    // AC 15's actual requirement: the element, its level and its position are the shell's;
    // only the string is c4-2's. If this ever needs more than a prop, the header moved.
    render(<AppShell deckName="Boros Aggro — RCQ list" />)

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Boros Aggro — RCQ list')
    // Still exactly one h1 — the provisional product name was REPLACED, not joined.
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
  })

  it('never leaves the h1 effectively empty, whatever shape the deck name arrives in', () => {
    // Q3's requirement is that the page is never heading-less, and a default parameter fires
    // only on `undefined`. A whitespace-only string (review round 2) renders an h1 that is
    // present in the DOM, invisible on screen, and announced as an empty heading — the same
    // state Q3 forbids, wearing a shape a `!== ''` check waves through.
    for (const empty of ['', ' ', null, undefined, false] as const) {
      const { unmount } = render(<AppShell deckName={empty} />)
      expect(
        screen.getByRole('heading', { level: 1 }),
        `deckName=${JSON.stringify(empty)} left the h1 without the fallback`,
      ).toHaveTextContent('Artificial Planeswalker')
      unmount()
    }
  })

  it('never renders an EMPTY h1, even for deckName="" (review, 2026-07-28)', () => {
    // A default parameter fires only on `undefined`; an empty string from a loading gap in
    // c4-2's store would render an empty heading and leave the page effectively heading-less
    // — the exact state Q3 exists to prevent. The fallback is value-aware, and this pins it.
    render(<AppShell deckName="" />)

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Artificial Planeswalker')
  })

  it('reserves both right-hand slots, prop-fed (AC 15b)', () => {
    // c2-7 supplies Badge and c6-8 supplies the nav pills. If the header did not already
    // have somewhere to put them, each of those stories would restructure the header
    // instead of filling it, and the alignment would be re-derived twice.
    render(<AppShell badges={<span>standard legal</span>} nav={<button>Card groups</button>} />)

    const banner = within(screen.getByRole('banner'))
    expect(banner.getByText('standard legal')).toBeVisible()
    expect(banner.getByRole('button', { name: 'Card groups' })).toBeVisible()
  })
})

describe('AppShell placeholder copy (AC 21)', () => {
  it('names the owner story of every region it is holding open', () => {
    render(<AppShell />)

    // Mechanical repair rather than archaeological: the story that fills each region is in
    // the copy, so removing a placeholder is a search for its own story id. EVERY id the
    // copy names is in this list — c4-9 was the one the first version omitted, which made
    // half of the left column's placeholder deletable without failing anything.
    for (const owner of [
      'c4-4',
      'c4-8',
      'c4-9',
      'c4-5',
      'c4-7',
      'c4-10',
      'c2-10',
      'c2-7',
      'c6-8',
    ]) {
      // `getAllByText`, not `getByText`: an owner may legitimately appear in TWO placeholders
      // — c4-10 both fills a header badge and owns the format-check panel — and the single
      // getter throws on a second match, which would turn a correct placeholder into a test
      // failure.
      expect(
        screen.getAllByText(new RegExp(owner)).length,
        `no placeholder names ${owner}`,
      ).toBeGreaterThan(0)
    }
  })

  it('drops a placeholder the moment its region is filled', () => {
    render(<AppShell left={<p>the card grid</p>} />)

    expect(screen.getByText('the card grid')).toBeInTheDocument()
    expect(screen.queryByText(/c4-4/)).not.toBeInTheDocument()
    // The regions that are still empty keep theirs.
    expect(screen.getByText(/c2-10/)).toBeInTheDocument()
  })

  it('keeps the placeholder when a region is passed the idiomatic false (review, 2026-07-28)', () => {
    // `left={hasDeck && <CardGrid />}` passes `false` when there is no deck. `false` is not
    // nullish and renders nothing, so a `??`-based slot would drop BOTH the content and the
    // placeholder — the region would just be silently blank.
    render(<AppShell left={false} />)

    expect(screen.getByText(/c4-4/)).toBeInTheDocument()
  })

  it('keeps the placeholder for an EMPTY ARRAY — the most idiomatic empty of all', () => {
    // `left={cards.map(...)}` over an empty list (review round 2). `[]` is not nullish, not a
    // boolean and not `''`, so the first version of `filled()` called it filled and the region
    // rendered blank with no clue which story owed it. `[false, null]` is the same defect one
    // level down: empty of OUTPUT rather than empty of elements.
    render(<AppShell left={[]} right={[false, null]} />)

    expect(screen.getByText(/c4-4/)).toBeInTheDocument()
    expect(screen.getByText(/c4-7/)).toBeInTheDocument()
  })

  it('still renders a NON-empty array — the empty check must not eat real content', () => {
    // The silent half. A `filled()` that answered "false" for every array would drop c4-4's
    // real grid, which is a far worse failure than the one above.
    render(<AppShell left={[<p key="a">the card grid</p>]} />)

    expect(screen.getByText('the card grid')).toBeInTheDocument()
    expect(screen.queryByText(/c4-4/)).not.toBeInTheDocument()
  })
})

describe('AppShell overlay slot (AC 7, AC 9)', () => {
  // The slot is an unstyled positioning container: it has no role, and giving it one would
  // invent a landmark c6-5 does not want. So these two assert on the ELEMENT, which is the
  // honest thing to assert about a thing whose whole contract is "exists / does not exist".
  const overlayIn = (container: HTMLElement) => container.querySelector('.app-shell-overlay')

  it('renders NOTHING when no agent view is open', () => {
    // AC 9. An always-present transparent full-window div is a click-swallower that presents
    // as "the app stopped responding to clicks", and it is the default outcome of "reserve a
    // slot" read literally. The slot is reserved in CSS; the ELEMENT is conditional.
    const { container } = render(<AppShell />)

    expect(overlayIn(container)).toBeNull()
  })

  it('renders the overlay when given one, so the slot is proven to WORK', () => {
    // Proven to work rather than proven to be absent — a slot only ever tested empty is a
    // slot nobody has shown c6-5 can use.
    const { container } = render(<AppShell overlay={<p>agent view</p>} />)

    expect(overlayIn(container)).not.toBeNull()
    expect(screen.getByText('agent view')).toBeVisible()
  })

  it('mounts NO overlay element for an empty array or whitespace (review round 2)', () => {
    // The slot had been left out of the `filled()` treatment the other regions got, and the
    // stakes here are higher than a missing placeholder: `overlay={views.map(...)}` over an
    // empty list would mount a full-window FIXED element containing nothing — AC 9's
    // click-swallower, presenting as "the app stopped responding to clicks".
    expect(overlayIn(render(<AppShell overlay={[]} />).container)).toBeNull()
    expect(overlayIn(render(<AppShell overlay={' '} />).container)).toBeNull()
    expect(overlayIn(render(<AppShell overlay={false} />).container)).toBeNull()
  })

  it('keeps the overlay OUT of the main landmark', () => {
    // It is a sibling of header/main/footer, not content of the page beneath it. c6-5 puts a
    // dialog here; a dialog nested inside `main` is a different accessibility story.
    render(<AppShell overlay={<p>agent view</p>} />)

    expect(within(screen.getByRole('main')).queryByText('agent view')).not.toBeInTheDocument()
  })
})
