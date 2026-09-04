/**
 * The deck header's badges (UX-DR3, UX-DR8, UX-DR10).
 *
 * jsdom applies no stylesheet, so nothing here can prove the pills LOOK right — that is a
 * manual check.
 * What this file proves is the half jsdom can see: which badges exist, what they say, and that
 * the count is a separate element the numeric role can reach.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DeckBadges } from './DeckBadges'

describe('what the badges say', () => {
  it('renders the format and the maindeck size', () => {
    render(<DeckBadges format="brawl" mainboardCount={100} sideboardCount={0} />)

    expect(screen.getByText('brawl')).toBeVisible()
    expect(screen.getByText('100')).toBeVisible()
    expect(screen.getByText('maindeck')).toBeVisible()
  })

  it('adds a sideboard badge only when there IS a sideboard', () => {
    // 35 of 40 real decks have none; a `0 sideboard` pill would be chrome announcing nothing.
    render(<DeckBadges format="standard" mainboardCount={60} sideboardCount={0} />)
    expect(screen.queryByText('sideboard')).toBeNull()

    render(<DeckBadges format="standard" mainboardCount={60} sideboardCount={15} />)
    expect(screen.getByText('sideboard')).toBeVisible()
    expect(screen.getByText('15')).toBeVisible()
  })

  it.each([
    ['null', null],
    ['blank', '   '],
    ['empty', ''],
  ])('renders NO format badge for a %s format, rather than an empty pill', (_label, format) => {
    const { container } = render(
      <DeckBadges format={format} mainboardCount={60} sideboardCount={0} />,
    )

    // Measured: all 40 saved decks carry a format, so this branch is untested data either way —
    // and between two untested branches the honest one makes no claim. "No format to check
    // against" is a real state with a real token (`format_recognized`) and it belongs to the
    // format check.
    expect(container.querySelectorAll('.badge')).toHaveLength(1)
    expect(screen.getByText('maindeck')).toBeVisible()
  })

  it('makes NO legality claim — no tone but neutral, and no "legal" anywhere', () => {
    const { container } = render(
      <DeckBadges format="standard" mainboardCount={60} sideboardCount={15} />,
    )

    // The mock's third badge is `standard legal` in the POSITIVE tone. Legality comes from
    // `GET /api/deck/{deck_id}/format-check`, a route this component never calls — so a
    // positive pill here would be the app asserting something it never asked.
    for (const badge of container.querySelectorAll('.badge')) {
      expect(badge.className).toContain('badge-neutral')
    }
    expect(container.textContent).not.toMatch(/legal/i)
  })
})

describe('the count is its own element, so the numeric role can reach it (UX-DR3)', () => {
  it('wraps every number in the count class and never the label', () => {
    const { container } = render(
      <DeckBadges format="brawl" mainboardCount={100} sideboardCount={15} />,
    )

    const counts = [...container.querySelectorAll('.deck-badges-count')]
    expect(counts.map((node) => node.textContent)).toEqual(['100', '15'])
    // The label is a SIBLING, not inside the span: `font: var(--type-numeric)` on the whole
    // badge would restyle the words too, which is the thing DESIGN.md's "beside the label, not
    // inside it" guidance is about.
    for (const node of counts) {
      expect(node.textContent).toMatch(/^\d+$/)
    }
  })

  it('keeps the format string OUT of the numeric role — it is a word, not a count', () => {
    const { container } = render(
      <DeckBadges format="standard" mainboardCount={60} sideboardCount={0} />,
    )

    expect(screen.getByText('standard').className).not.toContain('deck-badges-count')
    expect(container.querySelectorAll('.deck-badges-count')).toHaveLength(1)
  })

  it('renders a zero maindeck count rather than hiding it (the empty deck)', () => {
    // `0` is falsy, and a truthiness guard here would silently drop the one badge that tells a
    // reader their deck is empty.
    render(<DeckBadges format="brawl" mainboardCount={0} sideboardCount={0} />)

    expect(screen.getByText('0')).toBeVisible()
    expect(screen.getByText('maindeck')).toBeVisible()
  })
})
