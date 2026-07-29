/**
 * Badge — the pill label in five tones (story c2-7, UX-DR10, AC 2 / 5 / 6 / 8 / 14).
 *
 * THE TONE IS THE WHOLE COMPONENT, and jsdom can see NONE of it: it applies no stylesheet, so
 * "positive tints its background from --positive" is not observable here at any level of
 * effort. What this file asserts is the part that exists in the DOM — the tone reaches the
 * element as a class, every tone is distinct, and an unknown or missing tone lands on neutral
 * rather than on nothing. The colour claims are read from the CSS SOURCE in
 * ui/tests/token-usage.test.ts (no literal, no colour function, no --accent-dim) and the
 * appearance is on the epic manual-testing checklist (AC 21).
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Badge } from './Badge'
import { BADGE_TONES } from './tones'

describe('Badge tones (AC 2, AC 6)', () => {
  it('names exactly the five tones DESIGN.md declares', () => {
    // The non-vacuity anchor for the loop below: a BADGE_TONES that silently lost a member
    // would make every per-tone assertion pass by iterating over four things, or zero.
    expect([...BADGE_TONES]).toEqual(['neutral', 'accent', 'positive', 'negative', 'caution'])
  })

  it.each(BADGE_TONES)('renders the %s tone as its own class', (tone) => {
    const { container } = render(<Badge tone={tone}>standard</Badge>)

    const badge = container.querySelector('span')
    expect(badge).toHaveClass('badge')
    expect(badge).toHaveClass(`badge-${tone}`)
    expect(badge).toHaveTextContent('standard')
  })

  it('gives each tone a DISTINCT class', () => {
    // Without this, a `badge-${tone}` that had been mistyped into a constant string would pass
    // every assertion above — all five would carry the same class and all five would match.
    const classes = BADGE_TONES.map((tone) => {
      const { container } = render(<Badge tone={tone}>x</Badge>)
      return container.querySelector('span')?.className
    })
    expect(new Set(classes).size).toBe(BADGE_TONES.length)
  })

  it('falls back to neutral when no tone is given', () => {
    const { container } = render(<Badge>legal</Badge>)

    expect(container.querySelector('span')).toHaveClass('badge-neutral')
  })

  it('clamps a runtime-UNKNOWN tone to neutral rather than rendering an unstyled pill', () => {
    // The header's claim, made true by review (2026-07-29): the type admits only the five
    // tones, but a tone will eventually arrive as SERVER DATA (c4-10 format legality, c9
    // tiers), and an unchecked `badge-${tone}` renders `badge-bogus` — no wash, no tone
    // colour, a pill styled by nothing. The cast below is the untyped caller a TS signature
    // cannot rule out.
    const { container } = render(<Badge tone={'bogus' as never}>standard</Badge>)

    const badge = container.querySelector('span')
    expect(badge).toHaveClass('badge-neutral')
    expect(badge?.className).not.toContain('badge-bogus')
  })
})

describe('Badge content', () => {
  it('renders NOTHING for empty children — an empty pill is chrome announcing nothing', () => {
    // `filled()` (AC 17), by review ruling 2026-07-29: without content a Badge is a bordered,
    // washed, visibly EMPTY pill. The shapes below are the c2-6 family — every one looks
    // filled to a naive truthiness check while rendering nothing.
    for (const empty of [undefined, '', ' ', false, <></>, []] as const) {
      const { container } = render(<Badge tone="positive">{empty}</Badge>)
      expect(container.querySelector('span')).toBeNull()
    }
  })

  it('renders arbitrary children', () => {
    render(
      <Badge tone="positive">
        <span>60</span> cards
      </Badge>,
    )

    expect(screen.getByText('60')).toBeInTheDocument()
  })

  it('is a plain span with no role and no interaction (AC 5)', () => {
    // A badge is a chip on a line of text, not a control. If this ever starts failing because
    // something gave it a role, that is a behavioural contract arriving in a component whose
    // entire specification is that it has none.
    const { container } = render(<Badge>standard</Badge>)

    const badge = container.querySelector('span')
    expect(badge?.tagName).toBe('SPAN')
    expect(badge).not.toHaveAttribute('role')
    expect(badge).not.toHaveAttribute('tabindex')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
