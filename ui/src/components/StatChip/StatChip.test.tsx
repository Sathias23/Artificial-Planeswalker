/**
 * StatChip — a micro label over a numeric value, with an optional delta (UX-DR11).
 *
 * THE DELTA'S SIGN CONTRACT IS THE WHOLE OF THIS FILE. The tint is chosen by NUMERIC
 * SIGN, never by a string prefix: the mock's `String(delta).startsWith('-')` is wrong for
 * `-0`, wrong for a Unicode minus, and wrong for anything pre-formatted. Which COLOUR each
 * sign produces is a CSS claim jsdom cannot see, so what is asserted here is the class and the
 * rendered text — the colours are read from the CSS source and checked by eye at the first
 * consuming story.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatChip } from './StatChip'

describe('StatChip structure (AC 3)', () => {
  it('renders its label and its value', () => {
    render(<StatChip label="Cards" value={60} />)

    expect(screen.getByText('Cards')).toBeInTheDocument()
    expect(screen.getByText('60')).toBeInTheDocument()
  })

  it('renders no delta when none is given', () => {
    const { container } = render(<StatChip label="Cards" value={60} />)

    expect(container.querySelector('.stat-chip-delta')).toBeNull()
  })

  // The mock's `minWidth: 76` is NOT reproduced — but that is a CSS-source claim, and
  // a DOM assertion here cannot fail for it: jsdom applies no stylesheet, so a `min-width` in
  // StatChip.css would never reach any attribute this file can read. Such a test would pass
  // vacuously; the assertion lives in ui/tests/shell.test.ts where the CSS source is actually
  // read.
})

describe('StatChip delta, tinted by numeric sign (AC 6, Q6)', () => {
  it('renders a positive delta with an explicit + sign', () => {
    const { container } = render(<StatChip label="Power" value={12} delta={3} />)

    const delta = container.querySelector('.stat-chip-delta')
    expect(delta).toHaveTextContent('+3')
    expect(delta).toHaveClass('stat-chip-delta-positive')
  })

  it('renders a negative delta with its own sign, not a doubled one', () => {
    const { container } = render(<StatChip label="Power" value={12} delta={-2} />)

    const delta = container.querySelector('.stat-chip-delta')
    expect(delta).toHaveTextContent('-2')
    expect(delta).not.toHaveTextContent('+-2')
    expect(delta).toHaveClass('stat-chip-delta-negative')
  })

  it('renders a ZERO delta as neutral, with no sign — a zero delta is not an improvement', () => {
    const { container } = render(<StatChip label="Power" value={12} delta={0} />)

    const delta = container.querySelector('.stat-chip-delta')
    expect(delta).toHaveTextContent('0')
    expect(delta).not.toHaveTextContent('+0')
    expect(delta).toHaveClass('stat-chip-delta-neutral')
    // The falsy-value family, arriving in a second numeric prop: `{delta && …}` would have dropped
    // this element entirely, and `delta ? 'positive' : 'negative'` would have tinted a zero
    // RED — a no-change reading presented as a regression.
    expect(delta).not.toHaveClass('stat-chip-delta-negative')
  })

  it('reads -0 as ZERO, not as negative', () => {
    // `String(-0)` is "0", so a string-prefix check calls it positive; `-0 < 0` is FALSE, so a
    // naive comparison calls it positive too. `Math.sign(-0)` is `-0`, which is `=== 0`. This
    // is the member of the family that has to be written down because every shortcut gets it
    // wrong in a different direction.
    const { container } = render(<StatChip label="Power" value={12} delta={-0} />)

    expect(container.querySelector('.stat-chip-delta')).toHaveClass('stat-chip-delta-neutral')
  })

  it('renders NOTHING rather than "NaN" or "Infinity" for a non-finite delta', () => {
    for (const delta of [Number.NaN, Infinity, -Infinity]) {
      const { container } = render(<StatChip label="Power" value={12} delta={delta} />)
      expect(container.querySelector('.stat-chip-delta')).toBeNull()
    }
    expect(screen.queryByText(/NaN|Infinity/)).not.toBeInTheDocument()
  })
})

describe('StatChip is presentation-only (AC 5)', () => {
  it('exposes no role and no interaction', () => {
    render(<StatChip label="Cards" value={60} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
  })
})
