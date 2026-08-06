/**
 * The analysis pair row (story c4-8, Q6, AC 3).
 *
 * **The arity is the acceptance criterion**, and it is the one thing this component exists to
 * get right twice: one child today, two the day c4-9 lands, with no edit here. jsdom has no
 * layout engine, so what is asserted below is the CONTRACT that produces the ratio — the flex
 * rule in `AnalysisRow.css` — rather than two rendered widths. The pixels are AC 33's
 * eye-check.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AnalysisRow } from './AnalysisRow'

describe('the arity, both ways (AC 3)', () => {
  it('renders ONE child, and it is the only thing in the row', () => {
    const { container } = render(
      <AnalysisRow>
        <section>Mana curve</section>
      </AnalysisRow>,
    )
    const row = container.querySelector('.analysis-row')
    expect(row).not.toBeNull()
    expect(row!.children).toHaveLength(1)
    expect(screen.getByText('Mana curve')).toBeTruthy()
  })

  it('renders TWO children as siblings — the shape c4-9 lands by adding one', () => {
    const { container } = render(
      <AnalysisRow>
        <section>Mana curve</section>
        <section>Colour distribution</section>
      </AnalysisRow>,
    )
    const row = container.querySelector('.analysis-row')!
    expect(row.children).toHaveLength(2)
    expect([...row.children].map((c) => c.textContent)).toEqual([
      'Mana curve',
      'Colour distribution',
    ])
  })

  it('renders an empty row rather than throwing when handed nothing', () => {
    const { container } = render(<AnalysisRow />)
    expect(container.querySelector('.analysis-row')!.children).toHaveLength(0)
  })
})

/*
 * THE OTHER HALF OF AC 3 IS IN `ui/tests/shell.test.ts`, DELIBERATELY.
 *
 * The 1:1 split is a property of the STYLESHEET, and jsdom has no layout engine to observe it
 * with: with `flex-basis: auto` the wider panel's content would decide the split and every
 * arity assertion above would still pass. Reading the CSS is the only static way to catch that
 * — and source reads live in `ui/tests/`, over the git-derived file list, which is the house
 * idiom and the one that cannot go vacuous on an untracked file. `import.meta.url` is not even
 * a `file:` URL in the jsdom project, measured, so the read does not belong here on two counts.
 */
