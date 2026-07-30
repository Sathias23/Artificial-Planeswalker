/**
 * Footer — the rendered half (story c2-10).
 *
 * `tests/attribution.test.ts` proves the copy module IS `DESIGN.md`'s sentence. This file proves
 * the component puts that sentence on the screen, whole, with the two runs that are links being
 * links. The two have to meet in the middle for the same reason c2-9's suite says so: c2-8's
 * headline review defect was precisely the gap between an exhaustively-gated data module and a
 * component that silently failed to forward what it returned. The identical exposure here is a
 * footer that renders the text runs and drops the link runs — or renders the link labels and
 * drops the connecting prose — with the verbatim gate still green. `renders the whole sentence`
 * below is the assertion that closes it.
 *
 * WHAT jsdom CANNOT PROVE, stated rather than faked (AC 22). No stylesheet is applied and there
 * is no layout engine, so the persistent underline, the hover brightening, the focus ring, the
 * 24px hit box AS LAID OUT and the uppercase render are NOT proven here. There is no
 * `getComputedStyle` assertion in this file for that reason — it would report the jsdom defaults
 * and pass over a stylesheet that was never linked. Each of those claims is read from CSS SOURCE
 * in `tests/shell.test.ts`, where it is static, and is on the epic manual-testing checklist,
 * where it is not.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ATTRIBUTION, sentenceOf } from './copy'
import { Footer } from './Footer'

describe('the attribution reaches the screen intact (AC 1)', () => {
  it('renders the whole sentence, byte for byte, across its five parts', () => {
    const { container } = render(<Footer />)

    // `.textContent` compared with `toBe`, not a substring matcher: a footer that dropped a
    // link run, or one that appended anything of its own, must fail. `text-transform` is a
    // RENDER property and does not touch the DOM text, so this stays exact under Q1's
    // uppercase ruling — which is the whole reason that ruling was safe to take.
    expect(container.textContent).toBe(sentenceOf())
  })

  it('renders each part in source order, so the sentence cannot be reassembled wrongly', () => {
    render(<Footer />)
    const rendered = screen.getByText(/Card data and imagery/).textContent ?? ''

    let cursor = -1
    for (const part of ATTRIBUTION) {
      const at = rendered.indexOf(part.text, cursor + 1)
      expect(at, `${JSON.stringify(part.text)} is missing or out of order`).toBeGreaterThan(cursor)
      cursor = at
    }
  })
})

describe('the links (AC 5)', () => {
  it('marks exactly the two runs the copy module marks, by accessible name and href', () => {
    render(<Footer />)

    const links = screen.getAllByRole('link')
    const expected = ATTRIBUTION.filter((part) => part.href !== undefined)
    expect(links).toHaveLength(expected.length)
    expect(links).toHaveLength(2)

    // Asserted through the rendered text — which, for a plain-text link, is exactly the
    // accessible name a screen-reader announces ("Scryfall, link") — rather than by class or
    // position. `textContent`, not an accessible-name query: the two coincide here, and the
    // comment says which one the code actually reads (review find, 2026-07-30).
    expect(links.map((link) => link.textContent)).toEqual(expected.map((part) => part.text))
    expect(links.map((link) => link.getAttribute('href'))).toEqual(
      expected.map((part) => part.href),
    )
  })

  it('opens every link in a new tab, with both rel promises spelled out', () => {
    render(<Footer />)

    for (const link of screen.getAllByRole('link')) {
      expect(link).toHaveAttribute('target', '_blank')
      // Both tokens, asserted separately: `target="_blank"` implies `noopener` in current
      // browsers but promises nothing about the referrer, and a `rel` that lost one token while
      // keeping the other would satisfy any substring check on the pair.
      const rel = (link.getAttribute('rel') ?? '').split(/\s+/)
      expect(rel).toContain('noopener')
      expect(rel).toContain('noreferrer')
    }
  })

  it('never renders a link with an empty accessible name', () => {
    // A link announced as "link" with no name is unusable, and it is the shape an over-eager
    // split of the sentence would produce — an empty text run carrying an href.
    render(<Footer />)
    for (const link of screen.getAllByRole('link')) {
      expect(link.textContent?.trim()).not.toBe('')
    }
  })
})

describe('the semantics (AC 13, AC 17, UX-DR44)', () => {
  it('declares no landmark role of its own — the shell owns contentinfo', () => {
    render(<Footer />)

    // Rendered STANDALONE, outside any shell. If this component carried
    // `role="contentinfo"` or its own `<footer>`, this query would find one — and inside the
    // shell that would be a SECOND contentinfo, which AppShell.test.tsx asserts against.
    // Asserting it here rather than only in the composed tree is what makes the property
    // belong to this component instead of to today's arrangement.
    expect(screen.queryByRole('contentinfo')).toBeNull()
    expect(screen.queryByRole('banner')).toBeNull()
    expect(screen.queryByRole('main')).toBeNull()
    expect(screen.queryByRole('region')).toBeNull()
  })

  it('takes no props at all (Q4)', () => {
    // The type-level half is `tsc`'s and the source half is shell.test.ts's; this is the
    // runtime floor. `Footer.length` is the declared parameter count of the function, so a
    // props object added later fails HERE as well as in review.
    expect(Footer).toHaveLength(0)
  })

  it('renders identically on every render — nothing about it is stateful', () => {
    // AC 17's observable consequence. A component holding state, reading a store or subscribing
    // to anything could differ between two independent mounts; this one cannot.
    const first = render(<Footer />).container.innerHTML
    const second = render(<Footer />).container.innerHTML
    expect(first).toBe(second)
  })
})
