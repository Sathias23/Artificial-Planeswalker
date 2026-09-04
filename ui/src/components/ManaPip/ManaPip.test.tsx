/**
 * ManaPip's DOM contract.
 *
 * WHAT THIS FILE CANNOT PROVE, stated before the first assertion so nobody writes the tempting
 * version of it: jsdom applies NO stylesheet. There is no fill here, no circle, no gradient and
 * no size. A `getComputedStyle(pip).background` assertion would read the empty string and pass
 * for the wrong reason — the vacuity trap. Every CLAIM about
 * appearance is read as CSS SOURCE in `ui/tests/token-usage.test.ts` (which colour classes
 * exist, and which properties may spend a `--mana-*`), or checked by eye on the consuming
 * surfaces — the card placeholders, the deck row, the colour legend.
 *
 * So what is left for this file is what a USER PERCEIVES through the accessibility tree and the
 * text layer: what is announced, what is not, and what text the glyph slot carries. Assertions
 * go by ROLE and by TEXT, never by class name — a class-name assertion proves nothing about
 * what anyone perceives, and the one place class names ARE load-bearing (they must exist in the
 * stylesheet) is proven against the stylesheet itself, where the answer actually lives.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ManaPip } from './ManaPip'

describe('the glyph slot (AC 1, AC 16)', () => {
  it('shows a generic count', () => {
    render(<ManaPip glyph="2" />)
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('shows X, and the Phyrexian marker as a PLAIN LETTER (UX-DR7)', () => {
    // The whole point of the glyph slot: `{X}`, a generic count, a Phyrexian marker and an
    // unrecognised symbol all take the same route, so no drawn iconography is ever needed. A
    // Phyrexian Φ inside the pip would be the trade-dress imitation UX-DR7 bans by name.
    render(
      <>
        <ManaPip glyph="X" />
        <ManaPip colours={['b']} glyph="P" />
      </>,
    )
    expect(screen.getByText('X')).toBeInTheDocument()
    expect(screen.getByText('P')).toBeInTheDocument()
  })

  it('shows an unrecognised symbol’s own text rather than nothing (AC 3)', () => {
    render(<ManaPip glyph="HW" />)
    expect(screen.getByText('HW')).toBeInTheDocument()
  })

  it('shows the seven-digit Gleemax cost in full, unclipped and untruncated (AC 16)', () => {
    // The DOM half of AC 16. Whether it FITS is a layout question jsdom cannot answer — the
    // stylesheet answers it with min-width + a pill radius and no `overflow: hidden`, and the
    // grow-not-clip guard in ui/tests/token-usage.test.ts reads exactly that source. What this
    // asserts is the half that would otherwise be a truncating `.slice(0, 3)` nobody noticed:
    // the text arrives whole.
    render(<ManaPip glyph="1000000" />)
    expect(screen.getByText('1000000')).toBeInTheDocument()
  })

  it('renders no text at all for a plain colour pip', () => {
    const { container } = render(<ManaPip colours={['w']} />)
    expect(container.textContent).toBe('')
  })
})

describe('the accessibility posture (AC 15, Q4)', () => {
  it('is DECORATIVE by default — a pip inside a labelled cost must not announce itself', () => {
    const { container } = render(<ManaPip colours={['r']} glyph="2" />)
    const pip = container.firstElementChild
    expect(pip).toHaveAttribute('aria-hidden', 'true')
    expect(pip).not.toHaveAttribute('role')
    expect(pip).not.toHaveAttribute('aria-label')
    // And it is genuinely absent from the accessibility tree, not merely unlabelled.
    expect(screen.queryByRole('img')).toBeNull()
  })

  it('becomes a named role="img" when a label is supplied — c4-9’s legend case', () => {
    render(<ManaPip colours={['g']} label="green" />)
    // BY ROLE AND NAME, which is what a screen-reader user actually reaches. An `aria-label`
    // on a bare <span> is name-PROHIBITED on role="generic" and may be ignored outright, so
    // the role is not decoration — it is what makes the name exist at all.
    expect(screen.getByRole('img', { name: 'green' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'green' })).not.toHaveAttribute('aria-hidden')
  })

  it('treats an EMPTY label as absent, not as a nameless role="img"', () => {
    // An empty accessible name on role="img" is an element that announces itself and then says
    // nothing — worse than being skipped, and the shape a caller reaches by passing through an
    // absent field. `''` and `undefined` behave identically.
    const { container } = render(<ManaPip colours={['u']} label="" />)
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true')
    expect(screen.queryByRole('img')).toBeNull()
  })

  it('treats a WHITESPACE-ONLY label the same way (review 2026-07-29)', () => {
    // `label=" "` is the same nothing wearing a space: an exact-`''` check let it through to a
    // role="img" whose accessible name is a blank — the precise failure the branch above was
    // written and tested against.
    const { container } = render(<ManaPip colours={['u']} label="   " />)
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true')
    expect(screen.queryByRole('img')).toBeNull()
  })
})

describe('the colour class, which is the ONE thing a class assertion may prove (AC 12)', () => {
  // The exception to "never assert by class name", and it is narrow: the class is not a styling
  // detail here, it is the MECHANISM by which a colour reaches a token at all. The stylesheet
  // half — that every suffix these produce is actually declared, with a real `--mana-*` — is
  // proven in ui/tests/token-usage.test.ts against ManaPip.css itself.
  const classOf = (element: Element | null) => element?.getAttribute('class') ?? ''

  it('names one class per colour', () => {
    const { container } = render(<ManaPip colours={['b']} />)
    expect(classOf(container.firstElementChild)).toBe('mana-pip mana-pip-b')
  })

  it('CANONICALISES a hybrid pair into WUBRG order, so one class serves both spellings', () => {
    const first = render(<ManaPip colours={['g', 'w']} />).container.firstElementChild
    expect(classOf(first)).toBe('mana-pip mana-pip-wg')
  })

  it('falls back to a REAL token, never to nothing (AC 12)', () => {
    // Three shapes that must all land on a declared class rather than an unstyled — which is
    // to say transparent, which is to say invisible — circle: no colours at all (the generic
    // and `{X}` case), and more colours than a two-stop gradient can express.
    const generic = render(<ManaPip colours={[]} glyph="2" />).container.firstElementChild
    expect(classOf(generic)).toBe('mana-pip mana-pip-c')

    const noProp = render(<ManaPip glyph="X" />).container.firstElementChild
    expect(classOf(noProp)).toBe('mana-pip mana-pip-c')

    const tooMany = render(<ManaPip colours={['w', 'u', 'b']} />).container.firstElementChild
    expect(classOf(tooMany)).toBe('mana-pip mana-pip-c')
  })
})
