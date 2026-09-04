/**
 * Panel — the universal container (UX-DR9).
 *
 * WHAT THIS FILE CAN AND CANNOT ASSERT, for the same reason AppShell.test.tsx says it: jsdom
 * has NO LAYOUT ENGINE and applies no stylesheet, so "the overlay level is a step up the
 * ramp", "rest elevation is --shadow-rest" and "the live dot glows" are not observable here at
 * ANY level of effort — a getComputedStyle() assertion would read the empty string and pass
 * for the wrong reason. Those claims are read from the CSS SOURCE in ui/tests/shell.test.ts
 * and ui/tests/token-usage.test.ts, or they are an eye-check.
 *
 * What lives here is what jsdom genuinely knows: the accessibility tree, the element
 * structure, and whether a node exists at all. Assertions go through @testing-library BY ROLE
 * — a class-name assertion would prove nothing about the region-and-heading semantics, which
 * are the only reason those semantics are worth having.
 */

import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Panel } from './Panel'

describe('Panel semantics (AC 15, Q4)', () => {
  it('exposes a titled panel as a NAMED region with its title as an h2', () => {
    // This is the per-panel `role="region"` labelling AppShell.tsx leaves to the panels.
    // A <section> is only exposed as a region WHEN IT HAS A NAME —
    // an unnamed section has no role at all — so the name and the role stand or fall together.
    render(<Panel title="Mana curve" />)

    const region = screen.getByRole('region', { name: 'Mana curve' })
    expect(within(region).getByRole('heading', { level: 2 })).toHaveTextContent('Mana curve')
  })

  it('invents NO name for an untitled panel', () => {
    // The other half, and the one worth a test: an untitled panel is a plain unnamed
    // <section>, not a region called "Panel". A generic invented name is worse than none —
    // it fills the landmark list with nine identical entries a screen-reader user must
    // navigate past.
    render(<Panel>body content</Panel>)

    expect(screen.queryByRole('region')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
    expect(screen.getByText('body content')).toBeInTheDocument()
  })

  it('renders its children inside the section', () => {
    render(<Panel title="Deck list">the deck rows</Panel>)

    expect(
      within(screen.getByRole('region', { name: 'Deck list' })).getByText('the deck rows'),
    ).toBeInTheDocument()
  })
})

describe('Panel header slots (AC 1, AC 16, AC 17)', () => {
  it('renders title, count and badges together', () => {
    render(<Panel title="Creatures" count={24} badges={<span>legal</span>} />)

    const region = within(screen.getByRole('region', { name: 'Creatures' }))
    expect(region.getByRole('heading', { level: 2 })).toHaveTextContent('Creatures')
    expect(region.getByText('24')).toBeInTheDocument()
    expect(region.getByText('legal')).toBeInTheDocument()
  })

  it('renders a title-only header', () => {
    render(<Panel title="Curve" />)

    const region = within(screen.getByRole('region', { name: 'Curve' }))
    expect(region.getByRole('heading', { level: 2 })).toHaveTextContent('Curve')
    expect(region.queryByText('0')).not.toBeInTheDocument()
  })

  it('renders NO header at all when nothing fills one', () => {
    const { container } = render(<Panel>body</Panel>)

    expect(container.querySelector('header')).toBeNull()
  })

  it('RENDERS "0" for count={0}, rather than dropping it (AC 16)', () => {
    // The single most likely defect in this story. `{count && <span>{count}</span>}` renders
    // the bare string `0` into the DOM — something, so nobody looks — and `count ? … : null`
    // drops a real zero. A zero count is REAL CONTENT: "CREATURES 0" is the honest state of an
    // empty group, and a group header that silently loses its count in exactly that state is
    // the falsy-value family arriving in a numeric prop.
    render(<Panel title="Creatures" count={0} />)

    const region = within(screen.getByRole('region', { name: 'Creatures' }))
    expect(region.getByText('0')).toBeInTheDocument()
  })

  it('renders a header carrying ONLY a zero count', () => {
    // The other half of the same family: `title || count` is false for a zero-count-only
    // header, so the header vanishes and takes the count with it.
    const { container } = render(<Panel count={0} />)

    expect(container.querySelector('header')).not.toBeNull()
    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('renders a header carrying ONLY badges', () => {
    const { container } = render(<Panel badges={<span>standard</span>} />)

    expect(container.querySelector('header')).not.toBeNull()
    expect(screen.getByText('standard')).toBeInTheDocument()
  })

  it('uses filled() for the badge slot, so an empty shape mounts nothing (AC 17)', () => {
    // Not raw truthiness. `badges={<></>}` and `badges={[]}` are the shapes that took a
    // Greptile round and two review rounds to settle in filled() — an empty Fragment is a
    // React ELEMENT, so every nullish/boolean/string/array check calls it filled while the
    // browser paints nothing. Re-deriving that here is the reinvention AC 17 forbids; this
    // test is what proves the helper is actually reached.
    const { container: fragment } = render(<Panel badges={<></>} />)
    expect(fragment.querySelector('header')).toBeNull()

    const { container: array } = render(<Panel badges={[]} />)
    expect(array.querySelector('header')).toBeNull()

    const { container: blank } = render(<Panel title=" " />)
    expect(blank.querySelector('header')).toBeNull()
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
  })
})

describe('Panel levels and states (AC 1)', () => {
  // These four assert the CLASS, and say why: the class is the only part of "default vs
  // overlay" and "rest vs live" that exists in the DOM. What the class MEANS — --surface-panel
  // against --surface-overlay, --shadow-rest against --shadow-raise, the accent title, the
  // 6px dot — is a CSS claim, and jsdom applies no CSS. The stylesheet's half is read as
  // source in ui/tests/shell.test.ts; the appearance is a manual check.
  it('carries the default level with no level modifier', () => {
    const { container } = render(<Panel title="a" />)

    expect(container.querySelector('section')).toHaveClass('panel')
    expect(container.querySelector('section')).not.toHaveClass('panel-overlay')
  })

  it('carries the overlay level when asked', () => {
    const { container } = render(<Panel title="a" level="overlay" />)

    expect(container.querySelector('section')).toHaveClass('panel-overlay')
  })

  it('is not live by default, and mounts no dot', () => {
    const { container } = render(<Panel title="a" />)

    expect(container.querySelector('section')).not.toHaveClass('panel-live')
    expect(container.querySelector('.panel-dot')).toBeNull()
  })

  it('marks itself live and mounts a decorative dot', () => {
    const { container } = render(<Panel title="a" live />)

    expect(container.querySelector('section')).toHaveClass('panel-live')
    // The dot is DECORATION: the live state's accessible signal is the accent title and a
    // live-region announcement. A dot announced as an unlabelled node would be noise.
    expect(container.querySelector('.panel-dot')).toHaveAttribute('aria-hidden', 'true')
  })

  it('mounts no dot when live but header-less — there is nothing to mark', () => {
    // A title-less live panel DOES NOT EXIST IN THE TYPE — the
    // union in PanelProps rejects this combination, which is what the expect-error proves.
    // The render still guards it, because a JS caller is not bound by the union: this test is
    // the runtime FLOOR under the compile-time gate, and both halves are asserted here.
    // @ts-expect-error — `live` requires a `title`; a title-less live panel does not exist
    const { container } = render(<Panel live>body</Panel>)

    expect(container.querySelector('header')).toBeNull()
    expect(container.querySelector('.panel-dot')).toBeNull()
  })

  it('mounts no dot beside a TITLE-LESS header either — a dot next to a bare count marks nothing', () => {
    // The dot marks the title, so a count-only header must not mount it. The dot requires
    // `named`, not merely a header.
    // @ts-expect-error — same union: `live` without `title` is not a legal Panel
    const { container } = render(<Panel count={3} live />)

    expect(container.querySelector('header')).not.toBeNull()
    expect(container.querySelector('section')).toHaveClass('panel-live')
    expect(container.querySelector('.panel-dot')).toBeNull()
  })
})

describe('Panel combined variants (AC 6 — the matrix, not just the axes)', () => {
  // The review found the axes tested in isolation only, and the isolation was hiding a real
  // combination decision (the title-less live dot above). These pin the class COMPOSITION —
  // the one thing about combined states that exists in jsdom — so a `classes.join` regression
  // under multiple modifiers cannot pass the single-modifier tests.
  it('composes overlay + live with a full header', () => {
    const { container } = render(
      <Panel title="Suggestions" count={2} badges={<span>fresh</span>} level="overlay" live />,
    )

    const section = container.querySelector('section')
    expect(section).toHaveClass('panel', 'panel-overlay', 'panel-live')
    const region = within(screen.getByRole('region', { name: 'Suggestions' }))
    expect(region.getByRole('heading', { level: 2 })).toHaveTextContent('Suggestions')
    expect(region.getByText('2')).toBeInTheDocument()
    expect(region.getByText('fresh')).toBeInTheDocument()
    expect(container.querySelector('.panel-dot')).not.toBeNull()
  })

  it('composes overlay with a headerless body', () => {
    const { container } = render(<Panel level="overlay">body</Panel>)

    expect(container.querySelector('section')).toHaveClass('panel', 'panel-overlay')
    expect(container.querySelector('section')).not.toHaveClass('panel-live')
    expect(container.querySelector('header')).toBeNull()
  })

  it('keeps overlay and live independent — live alone adds no overlay class', () => {
    const { container } = render(<Panel title="a" live />)

    expect(container.querySelector('section')).toHaveClass('panel-live')
    expect(container.querySelector('section')).not.toHaveClass('panel-overlay')
  })
})
