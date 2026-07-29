/**
 * ManaCost's DOM contract (story c2-8, AC 2, 3, 4, 7, 15, 17, 18).
 *
 * THE SAME LIMIT ManaPip.test.tsx states, for the same reason: jsdom applies no stylesheet, so
 * there is no wrapping, no gap and no colour here. What IS decidable in the DOM is the thing
 * this component can get catastrophically wrong — WHICH SYMBOLS SURVIVE — and that is what
 * every assertion below is about. Assertions go by ROLE and by TEXT, with ManaPip.test.tsx's
 * one narrow class exception (review 2026-07-29): `.mana-pip` / `.mana-pip-*` selectors are the
 * MECHANISM by which a symbol reaches a token at all, so counting pips and reading their colour
 * classes is asserting what survives, not how it is styled. Nothing here asserts a style.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ManaCost } from './ManaCost'

/** Every pip in the rendered cost, in document order, as the text each one shows. */
const pipText = (container: HTMLElement): string[] => {
  const pips = container.querySelectorAll('.mana-pip')
  const texts: string[] = []
  pips.forEach((pip) => texts.push(pip.textContent ?? ''))
  return texts
}

const pipCount = (container: HTMLElement): number => container.querySelectorAll('.mana-pip').length

describe('every symbol renders (AC 2) — the epic’s own four cases, and the five it omits', () => {
  it('renders braces, hybrid, generic-hybrid, Phyrexian and {X} — all five as ONE pip each', () => {
    const { container } = render(<ManaCost cost="{2}{W/U}{2/R}{B/P}{X}" />)
    expect(pipCount(container)).toBe(5)
    // The COUNT is the assertion that matters. The composition reference renders this same
    // string as SIX pips with two symbols mangled and one gone: `{W/U}` splits into two, `{2/R}`
    // splits into a 2 and an R, `{B/P}`'s marker vanishes and `{X}` disappears entirely.
    expect(pipText(container)).toEqual(['2', '', '2', 'P', 'X'])
  })

  it('renders the four families the epic never names', () => {
    // Colourless hybrid, three-part hybrid Phyrexian, colourless, and a seven-digit generic.
    const { container } = render(<ManaCost cost="{C/W}{R/W/P}{C}{1000000}" />)
    expect(pipCount(container)).toBe(4)
    expect(pipText(container)).toEqual(['', 'P', '', '1000000'])
  })

  it('forwards each symbol’s COLOURS to its pip, not only its glyph (review 2026-07-29)', () => {
    // The regression nothing else can see: replace `token.colours` with `[]` in ManaCost.tsx
    // and every count, text and aria-label assertion in this file stays green while every cost
    // renders colourless — "wrong without looking wrong", one layer above the parser it was so
    // carefully gated out of. The colour class is the one channel the colour travels through.
    const { container } = render(<ManaCost cost="{W/U}{G}{2}" />)
    const classes = [...container.querySelectorAll('.mana-pip')].map((pip) => pip.className)
    expect(classes).toEqual(['mana-pip mana-pip-wu', 'mana-pip mana-pip-g', 'mana-pip mana-pip-c'])
  })
})

describe('nothing is silently dropped (AC 3, AC 7)', () => {
  it('surfaces an unrecognised symbol as a visible pip showing its own text', () => {
    // The epic's own named test. `{HW}` (Little Girl) and `{S}` (snow) are both real and
    // neither is in the parser's symbol table — which is the point: they must render anyway.
    const { container } = render(<ManaCost cost="{2}{HW}{S}" />)
    expect(pipCount(container)).toBe(3)
    expect(screen.getByText('HW')).toBeInTheDocument()
    expect(screen.getByText('S')).toBeInTheDocument()
  })

  it('surfaces an INVENTED symbol family — the structural proof, not an enumeration (AC 25)', () => {
    // `{Q/W/E}` is in no list anywhere in this feature. If "never drops" held only because the
    // author happened to know about snow and Little Girl, this is where that would show.
    render(<ManaCost cost="{Q/W/E}" />)
    expect(screen.getByText('Q/W/E')).toBeInTheDocument()
  })

  it('surfaces the ` // ` split-card separator as text between the parts (AC 7)', () => {
    const { container } = render(<ManaCost cost="{2}{B} // {B}" />)
    expect(pipCount(container)).toBe(3)
    expect(container.textContent).toContain('//')
    // ORDER is asserted over the child SEQUENCE, not textContent — colour pips contribute no
    // text, so a textContent check would pass a renderer that dropped, duplicated or reordered
    // the two {B} pips around the separator (review 2026-07-29). Class-by-class, in order:
    const wrapper = container.firstElementChild
    expect(wrapper).not.toBeNull()
    expect([...wrapper!.children].map((child) => child.className)).toEqual([
      'mana-pip mana-pip-c',
      'mana-pip mana-pip-b',
      'mana-cost-text',
      'mana-pip mana-pip-b',
    ])
    expect(container.textContent).toBe('2 // ')
  })

  it('handles the five-part split card — ten pips and four separators', () => {
    const { container } = render(<ManaCost cost="{X}{W} // {2}{R} // {2}{U} // {3}{B} // {1}{G}" />)
    expect(pipCount(container)).toBe(10)
    expect(container.querySelectorAll('.mana-cost-text')).toHaveLength(4)
  })

  it('renders malformed input rather than throwing on it (AC 8)', () => {
    // Totality, at the component layer. An unclosed brace is the shape a truncated wire value
    // arrives in, and it must render something a human can see is wrong — not nothing, and not
    // a blank screen.
    const { container } = render(<ManaCost cost="{2}{B/" />)
    expect(container.textContent).toContain('{B/')
    expect(pipCount(container)).toBe(1)
  })
})

describe('an absent cost renders nothing, in all four spellings (AC 4)', () => {
  it('renders nothing for undefined, null, empty and whitespace-only', () => {
    // A land's cost. All four are asserted because the wire type may be nullable while this
    // repo's own data uses `''` — picking one and defending it is how the other three become
    // an empty `role="img"` announcing an empty name.
    for (const cost of [undefined, null, '', '   ']) {
      const { container } = render(<ManaCost cost={cost} />)
      expect(container.innerHTML, `cost=${JSON.stringify(cost)} rendered something`).toBe('')
    }
  })

  it('renders no wrapper at all, so nothing is announced either', () => {
    render(<ManaCost cost="" />)
    expect(screen.queryByRole('img')).toBeNull()
  })
})

describe('how it is announced (AC 15, Q4)', () => {
  it('carries an accessible name on a role="img" wrapper', () => {
    render(<ManaCost cost="{2}{W/U}" />)
    // BY ROLE AND NAME. `aria-label` on a bare <span> is name-prohibited on role="generic", so
    // the role is what makes the name exist at all — this assertion fails if the role is
    // dropped, which is exactly the regression it exists to catch.
    expect(screen.getByRole('img', { name: '2 generic, white or blue' })).toBeInTheDocument()
  })

  it('does not let its pips announce themselves as well', () => {
    // Colour is the pip's entire meaning, so the cost must be named — but naming BOTH the cost
    // and each pip is the flooding UX-DR45 warns about. There is exactly one named element.
    render(<ManaCost cost="{1}{U}{B}" />)
    expect(screen.getAllByRole('img')).toHaveLength(1)
    expect(screen.getByRole('img', { name: '1 generic, blue, black' })).toBeInTheDocument()
  })

  it('names an unknown symbol honestly rather than skipping it', () => {
    render(<ManaCost cost="{2}{HW}" />)
    expect(screen.getByRole('img', { name: '2 generic, HW' })).toBeInTheDocument()
  })
})

describe('the long-cost case (AC 17)', () => {
  it('renders all fifteen pips of B.F.M. — the row wraps, it does not truncate', () => {
    // Whether it WRAPS is a layout question jsdom cannot answer; ManaCost.css decides it in
    // source with `flex-wrap: wrap` and says why. What this asserts is the half a truncating
    // renderer would break: every pip is in the DOM.
    const { container } = render(<ManaCost cost={'{B}'.repeat(15)} />)
    expect(pipCount(container)).toBe(15)
  })
})
