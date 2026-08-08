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

  it('keeps the counts at 1/1/1 WITH a skip link present (c4-11, AC 2)', () => {
    // The first structural addition to this file in nine stories, and the thing it must not do is
    // become a fourth landmark. Asserted WITH the slot filled, because the test above renders an
    // empty shell and would stay green through a `<nav>` or `<aside>` wrapper here.
    render(<AppShell skipLink={<button type="button">Skip past the deck grid</button>} />)

    expect(screen.getAllByRole('banner')).toHaveLength(1)
    expect(screen.getAllByRole('main')).toHaveLength(1)
    expect(screen.getAllByRole('contentinfo')).toHaveLength(1)
    expect(screen.queryAllByRole('navigation')).toHaveLength(0)
    expect(screen.queryAllByRole('complementary')).toHaveLength(0)
    expect(screen.queryAllByRole('region')).toHaveLength(0)
  })

  it('renders the skip link OUTSIDE all three landmarks, and FIRST (c4-11, AC 1, AC 2, Q5)', () => {
    const { container } = render(
      <AppShell
        skipLink={<button type="button">Skip past the deck grid</button>}
        left={<p>left column content</p>}
        footer={<p>footer content</p>}
      />,
    )
    const link = screen.getByRole('button', { name: 'Skip past the deck grid' })

    // OUTSIDE ALL THREE. Q5 declined putting it inside `<header>`: a skip link is not banner
    // content, and joining a landmark's accessible content buys nothing.
    expect(screen.getByRole('banner').contains(link)).toBe(false)
    expect(screen.getByRole('main').contains(link)).toBe(false)
    expect(screen.getByRole('contentinfo').contains(link)).toBe(false)

    // FIRST IN DOCUMENT ORDER, which — because nothing in this app carries a `tabindex` — is the
    // whole of "the first Tab stop" (c4-6's ruling). Asserted as POSITION rather than as a
    // `tabindex` value, following `CardTile.test.tsx:595-605`.
    expect(container.querySelector('.app-shell')?.firstElementChild).toBe(link)
    expect(
      link.compareDocumentPosition(screen.getByRole('banner')) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('renders NOTHING in the skip-link slot when it is empty — no placeholder (c4-11)', () => {
    // The one slot in this file that deliberately breaks the AC 21 placeholder convention. Every
    // other empty region renders a line naming its owning story; this one renders nothing at all,
    // because it sits before the header on EVERY surface — including the ones where the link is
    // correctly absent — so a placeholder would put a story key permanently in the most prominent
    // position in the document. That is the exact defect the C3 retro's F1 item is about.
    const { container } = render(<AppShell left={<p>left column content</p>} />)

    expect(container.querySelector('.app-shell')?.firstElementChild?.tagName).toBe('HEADER')
    expect(container.textContent).not.toContain('c4-11')
    expect(container.textContent).not.toContain('Skip past the deck grid')
  })

  it('renders the connection pill AFTER main and BEFORE the footer (c5-7, AC 9, Q1)', () => {
    // THE DOM-POSITION RULING, ASSERTED RATHER THAN DESCRIBED — this is the machine-checkable
    // half of dw:4597, which three artefacts each assumed someone else had closed. Nothing in
    // this app carries a `tabindex`, so document order IS Tab order (c4-6's ruling) and these
    // two comparisons ARE the claim "the last Tab stop before the footer links".
    render(
      <AppShell
        left={<p>left column content</p>}
        connectionPill={<button type="button">Connected</button>}
        footer={<p>footer content</p>}
      />,
    )
    const pill = screen.getByRole('button', { name: 'Connected' })

    // AFTER the columns: `main` precedes the pill.
    expect(
      screen.getByRole('main').compareDocumentPosition(pill) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    // BEFORE the footer: the pill precedes `contentinfo`.
    expect(
      pill.compareDocumentPosition(screen.getByRole('contentinfo')) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    // And OUTSIDE all three landmarks, like the skip link at the other end of the document —
    // a `<div>` between `main` and `footer` must never become a fourth landmark.
    expect(screen.getByRole('banner').contains(pill)).toBe(false)
    expect(screen.getByRole('main').contains(pill)).toBe(false)
    expect(screen.getByRole('contentinfo').contains(pill)).toBe(false)
  })

  it('keeps the counts at 1/1/1 WITH a connection pill present (c5-7, AC 9)', () => {
    render(
      <AppShell
        connectionPill={<button type="button">Connected</button>}
        footer={<p>footer content</p>}
      />,
    )

    expect(screen.getAllByRole('banner')).toHaveLength(1)
    expect(screen.getAllByRole('main')).toHaveLength(1)
    expect(screen.getAllByRole('contentinfo')).toHaveLength(1)
  })

  it('renders NOTHING in the pill slot when it is empty — no placeholder (c5-7)', () => {
    // The skip link's exception applied a second time, and for a sharper reason: this element is
    // FIXED to a window corner on every surface, so a placeholder naming c5-7 would sit on the
    // glass permanently AND never scroll away. `main` is followed directly by the footer.
    const { container } = render(<AppShell left={<p>left column content</p>} />)

    expect(screen.getByRole('main').nextElementSibling?.tagName).toBe('FOOTER')
    expect(container.textContent).not.toContain('c5-7')
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

  it('keeps the placeholder for an empty Fragment and an empty Set (Greptile, PR #23)', () => {
    // Both are shapes every earlier version of `filled()` called "filled": a Fragment is a
    // React element, and a Set is not an array. Neither renders anything, so both left a
    // silently blank region with no clue which story owed it.
    render(<AppShell left={<></>} right={new Set() as never} />)

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

  it('mounts NO overlay element for any empty shape a caller can express', () => {
    // The slot had been left out of the `filled()` treatment the other regions got, and the
    // stakes here are higher than a missing placeholder: `overlay={views.map(...)}` over an
    // empty list would mount a full-window FIXED element containing nothing — AC 9's
    // click-swallower, presenting as "the app stopped responding to clicks".
    //
    // The last two are Greptile's (PR #23), and they are the sharp ones: an empty Fragment is
    // a React ELEMENT, so every nullish/boolean/string/array check says "filled" while the
    // browser paints nothing; and a Set is a legal React child that `Array.isArray` denies.
    expect(overlayIn(render(<AppShell overlay={[]} />).container)).toBeNull()
    expect(overlayIn(render(<AppShell overlay={' '} />).container)).toBeNull()
    expect(overlayIn(render(<AppShell overlay={false} />).container)).toBeNull()
    expect(overlayIn(render(<AppShell overlay={<></>} />).container)).toBeNull()
    expect(overlayIn(render(<AppShell overlay={<>{[]}</>} />).container)).toBeNull()
    expect(overlayIn(render(<AppShell overlay={new Set() as never} />).container)).toBeNull()
  })

  it('does not CONSUME a one-shot iterable while inspecting it (Greptile, PR #23)', () => {
    // A generator returns itself from [Symbol.iterator](), so spreading it to check for
    // emptiness hands React an exhausted iterator: measured, the region rendered EMPTY and
    // lost its placeholder as well — strictly worse than not looking at all. React itself
    // warns that iterators are unsupported as children; the shell must not make that worse.
    function* views() {
      yield <p key="a">agent view</p>
    }
    const { container } = render(<AppShell left={views()} />)

    expect(container.textContent).toContain('agent view')
  })

  it('still mounts the overlay for a NON-empty Fragment or Set', () => {
    // The silent half. A `filled()` that answered "false" for every Fragment would stop c6-5's
    // agent view from ever mounting, which is a far worse failure than the one above.
    const fragment = render(<AppShell overlay={<>agent view</>} />)
    expect(overlayIn(fragment.container)).not.toBeNull()
    expect(fragment.getByText('agent view')).toBeVisible()

    const iterable = render(<AppShell overlay={new Set([<p key="a">from a Set</p>]) as never} />)
    expect(overlayIn(iterable.container)).not.toBeNull()
    expect(iterable.getByText('from a Set')).toBeVisible()
  })

  it('keeps the overlay OUT of the main landmark', () => {
    // It is a sibling of header/main/footer, not content of the page beneath it. c6-5 puts a
    // dialog here; a dialog nested inside `main` is a different accessibility story.
    render(<AppShell overlay={<p>agent view</p>} />)

    expect(within(screen.getByRole('main')).queryByText('agent view')).not.toBeInTheDocument()
  })
})
