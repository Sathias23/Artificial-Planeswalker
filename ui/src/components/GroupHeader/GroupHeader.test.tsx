/**
 * Group header — the type-group divider ("CREATURES 24") over a hairline rule (UX-DR12).
 *
 * The rule and the uppercase are CSS, and jsdom applies none — `text-transform: uppercase`
 * does not change `textContent`, so an assertion on "CREATURES" would be asserting the
 * caller's own string back at itself. What is real here is the heading LEVEL, which UX-DR44
 * fixes, and the zero-count behaviour.
 */

import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { GroupHeader } from './GroupHeader'

describe('Group header semantics (AC 4, AC 15, UX-DR44)', () => {
  it('renders its label as an h2 with the count beside it', () => {
    const { container } = render(<GroupHeader label="Creatures" count={24} />)

    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Creatures')
    expect(within(container).getByText('24')).toBeInTheDocument()
  })

  it('puts the count OUTSIDE the heading, not inside it', () => {
    // DESIGN.md, `{typography.label}`: "Panel titles that need to carry counts should put the
    // count in {typography.numeric} BESIDE the label, not inside it." A count folded into the
    // heading text is also what a screen reader would read as part of the group's name, so
    // "Creatures 24" would become the accessible name of a group whose size changes.
    render(<GroupHeader label="Creatures" count={24} />)

    const heading = screen.getByRole('heading', { level: 2 })
    expect(heading).toHaveTextContent('Creatures')
    expect(heading.textContent).not.toContain('24')
  })

  it('is an h2 at the same level as a panel title — UX-DR44 taken as written', () => {
    // The literal reading of UX-DR44 ("panel titles AND type-group headers h2") makes a deck
    // list panel's title and its "CREATURES" divider siblings at the same level. That is the
    // spec's choice, taken as written and recorded here rather than quietly "corrected" to an
    // h3.
    render(<GroupHeader label="Creatures" count={1} />)

    expect(screen.queryByRole('heading', { level: 3 })).not.toBeInTheDocument()
  })
})

describe('Group header counts (AC 16)', () => {
  it('RENDERS "0" for count={0}', () => {
    // "CREATURES 0" is the honest state of an empty group and the exact state a deck being
    // built passes through. `{count && <span>{count}</span>}` renders the bare string `0` and
    // `count ? … : null` drops it — the falsy-value family in a numeric prop.
    const { container } = render(<GroupHeader label="Creatures" count={0} />)

    expect(within(container).getByText('0')).toBeInTheDocument()
  })

  it('renders no count element at all when none is given', () => {
    const { container } = render(<GroupHeader label="Lands" />)

    expect(container.querySelector('.group-header-count')).toBeNull()
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Lands')
  })

  it('renders nothing rather than "NaN" for a non-finite count', () => {
    const { container } = render(<GroupHeader label="Lands" count={Number.NaN} />)

    expect(container.querySelector('.group-header-count')).toBeNull()
  })
})

describe('Group header is presentation-only (AC 5)', () => {
  it('exposes no interaction', () => {
    render(<GroupHeader label="Creatures" count={2} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
