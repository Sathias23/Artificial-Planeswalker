/**
 * StatePanel — the rendered half (story c2-9).
 *
 * `tests/copy.test.ts` proves the copy module IS `EXPERIENCE.md`. This file proves the panel
 * puts that copy on the screen, in the right slot, with the right semantics — and the two have
 * to meet in the middle, because c2-8's headline review defect was exactly the gap between
 * them: the mana parser was gated exhaustively and `ManaCost` had no test proving it FORWARDED
 * what the parser returned, so every colour could be dropped and 383 tests stayed green. The
 * identical exposure here is a panel that renders the guidance in the action slot, or drops the
 * action line entirely, with the verbatim gate still passing. `renders each slot from the copy
 * module, per state` below is the assertion that closes it.
 *
 * WHAT jsdom CANNOT PROVE, stated rather than faked (AC 21). No stylesheet is applied and there
 * is no layout engine, so the centring, the 480px measure, the chip's recessed material, the
 * accent colour of the action line and the hairline border are NOT proven here. There is no
 * `getComputedStyle` assertion in this file for that reason — it would report back the
 * defaults and pass over a stylesheet that was never linked. Those claims are read from CSS
 * SOURCE in the node project where they are static, and are on the epic manual-testing
 * checklist where they are not.
 */

import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { STATE_COPY, actionOf, guidanceOf, type StateKey } from './copy'
import { StatePanel } from './StatePanel'

const STATES = Object.keys(STATE_COPY) as StateKey[]

/**
 * A copy string as the USER sees it: the backticks are MARKUP (they become the command chip's
 * element boundaries, AC 11) and must not survive to the screen. Stripping them here rather
 * than loosening the comparison keeps these assertions byte-exact — a swallowed word still
 * fails — while also making "no backtick reaches the reader" a thing this suite states.
 */
const asRendered = (text: string) => text.replaceAll('`', '')

describe('the panel semantics (AC 7, UX-DR44)', () => {
  it('is a region named by its headline, with the headline as an h2', () => {
    render(<StatePanel state="no-active-deck" />)

    const region = screen.getByRole('region', { name: 'No deck on the glass.' })
    // `.textContent` compared with `toBe`, not `toHaveTextContent` — the matcher is a substring
    // check, and a suite whose thesis is "verbatim means checkable" cannot have its rendered
    // headline tolerate appended text (review 2026-07-29).
    expect(within(region).getByRole('heading', { level: 2 }).textContent).toBe(
      'No deck on the glass.',
    )
  })

  it('carries no aria-live — this panel is not in the live-region inventory (landmine 17)', () => {
    // UX-DR45 names three live regions and this is not one of them: the panel REPLACES the main
    // surface, so the landmark change carries it. An aria-live here would re-announce the whole
    // panel — headline, guidance, action and every deck name — on every mount. Asserted over the
    // whole subtree, not just the root, so a helpful `aria-live` on the action line fails too.
    const { container } = render(<StatePanel state="internal-error" />)
    expect(container.querySelectorAll('[aria-live]')).toHaveLength(0)
    expect(container.querySelectorAll('[role="alert"], [role="status"]')).toHaveLength(0)
  })

  it('renders no illustration, icon or image element (AC 2 — the ban is on the ELEMENT)', () => {
    for (const state of STATES) {
      const { container } = render(<StatePanel state={state} />)
      expect(container.querySelectorAll('img, svg, picture, canvas')).toHaveLength(0)
    }
  })
})

describe('every state renders its EXPERIENCE.md copy (AC 3, AC 4)', () => {
  it.each(STATES)('%s — the headline is the h2, byte for byte', (state) => {
    render(<StatePanel state={state} />)
    // Exact, not `toHaveTextContent` — that matcher is a substring check, so five of six states
    // tolerated an appended suffix until the review of 2026-07-29 made this the same bar as
    // every other verbatim assertion in the story.
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(STATE_COPY[state].headline)
  })

  it.each(STATES)('%s — renders each slot from the copy module, per state', (state) => {
    // THE FORWARDING TEST (see this file's header). Paragraphs are read IN ORDER and matched
    // against the copy module's own accessors, so a panel that swapped the two slots, rendered
    // the headline twice, or dropped the action line fails here even though `copy.test.ts`
    // stays green. `textContent` rather than `getByText`, because the command chip splits the
    // string into several DOM nodes and a text matcher would never see the whole sentence.
    const copy = STATE_COPY[state]
    const { container } = render(<StatePanel state={state} />)

    const expected = [guidanceOf(copy), actionOf(copy)]
      .filter((text) => text !== '')
      .map(asRendered)
    expect([...container.querySelectorAll('p')].map((p) => p.textContent)).toEqual(expected)
  })

  it('gives the action its own line — a separate block from the guidance (AC 1)', () => {
    const { container } = render(<StatePanel state="disconnected" />)
    const paragraphs = [...container.querySelectorAll('p')]
    expect(paragraphs).toHaveLength(2)
    expect(paragraphs[0].textContent).toBe(asRendered(guidanceOf(STATE_COPY.disconnected)))
    expect(paragraphs[1].textContent).toBe(asRendered(actionOf(STATE_COPY.disconnected)))
  })

  it('renders NO action line for the state that honestly has none', () => {
    // `database-updating` retries quietly, so there is nothing for the user to do. An empty
    // accent paragraph would be a coloured blank line under "nothing to do here".
    const { container } = render(<StatePanel state="database-updating" />)
    expect(container.querySelectorAll('p')).toHaveLength(1)
    expect(container.querySelector('p')?.textContent).toBe(
      'Reads will resume automatically — nothing to do here.',
    )
  })

  it('renders NO guidance paragraph for the state whose whole body is its action', () => {
    const { container } = render(<StatePanel state="no-active-deck" />)
    expect(container.querySelectorAll('p')).toHaveLength(1)
    expect(container.querySelector('p')?.textContent).toBe(
      asRendered(actionOf(STATE_COPY['no-active-deck'])),
    )
  })
})

describe('the command chip is derived from the copy (AC 1, AC 11)', () => {
  it('marks up the backticked command, and shows no backtick to the user', () => {
    const { container } = render(<StatePanel state="database-not-initialized" />)

    const chips = [...container.querySelectorAll('code')]
    expect(chips.map((chip) => chip.textContent)).toEqual(['initialize_database'])
    expect(container.textContent).not.toContain('`')
  })

  it('marks up a multi-word command in the state this story wrote', () => {
    const { container } = render(<StatePanel state="internal-error" />)
    expect([...container.querySelectorAll('code')].map((chip) => chip.textContent)).toEqual([
      'artificial-planeswalker companion',
    ])
  })

  it('renders no chip at all for copy with no backticks', () => {
    const { container } = render(<StatePanel state="disconnected" />)
    expect(container.querySelectorAll('code')).toHaveLength(0)
    // …and the sentence still arrives whole, which is the half a "no chip" assertion alone
    // would let a swallowed string pass.
    expect(container.textContent).toContain('it printed a fresh URL — open that.')
  })
})

describe('the available-deck list (AC 5)', () => {
  it('lists the names it is given', () => {
    render(<StatePanel state="no-active-deck" decks={['Boros Aggro', 'Simic Ramp']} />)
    const items = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual(['Boros Aggro', 'Simic Ramp'])
  })

  it('makes none of them clickable — the agent drives (NG1)', () => {
    // By ROLE, not by class name: "non-clickable" means there is no link and no button in the
    // subtree, and that is the only assertion that says so. A `.state-panel-decks li` selector
    // would pass just as happily over a list of anchors.
    const { container } = render(
      <StatePanel state="no-active-deck" decks={['Boros Aggro', 'Simic Ramp']} />,
    )
    expect(screen.queryAllByRole('link')).toHaveLength(0)
    expect(screen.queryAllByRole('button')).toHaveLength(0)
    expect(container.querySelectorAll('a, button, [onclick], [tabindex]')).toHaveLength(0)
  })

  it('renders nothing extra when there are no decks — the day-one case, not an edge', () => {
    // A fresh install has no decks at all, so this is the COMMON render. An empty `<ul>` under
    // the guidance is a hairline of blank space announced as "list, 0 items".
    for (const decks of [undefined, [] as string[]]) {
      const { container } = render(<StatePanel state="no-active-deck" decks={decks} />)
      expect(screen.queryByRole('list')).toBeNull()
      expect(container.querySelectorAll('ul')).toHaveLength(0)
    }
  })

  it('decides emptiness with filled(), not truthiness — the shapes that look filled', () => {
    // The c2-6 family, applied to this prop: an array whose every element renders nothing is
    // EMPTY OF OUTPUT even though `decks.length` is 2. `filled()` is imported rather than
    // re-derived precisely so this case is already handled here.
    const { container } = render(
      <StatePanel state="no-active-deck" decks={['', '  '] as string[]} />,
    )
    expect(container.querySelectorAll('ul')).toHaveLength(0)
  })

  it('drops a blank name without dropping the list — the MIXED case (review 2026-07-29)', () => {
    // `['', 'Boros Aggro']` passes `filled()` as a whole, so the all-blank test above never
    // exercised the per-name decision: the first version rendered an empty, announced `<li>`
    // for the blank — the exact empty-chrome shape one level down. String blankness is trim's
    // question (c2-8's AC 4 lesson), decided per element in the component.
    render(<StatePanel state="no-active-deck" decks={['', 'Boros Aggro', '  ']} />)
    const items = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual(['Boros Aggro'])
  })

  it('renders duplicate names as two rows — nothing in the prop contract forbids them', () => {
    // Deck names are user-authored strings; a `key={name}` collides on a duplicate and React
    // silently drops or mis-reconciles one row. Index keys are correct for this static,
    // non-interactive list, and this is the assertion that keeps both rows on screen.
    render(<StatePanel state="no-active-deck" decks={['Burn', 'Burn']} />)
    expect(within(screen.getByRole('list')).getAllByRole('listitem')).toHaveLength(2)
  })
})

describe('the copy rules, at the point of render (AC 6)', () => {
  it.each(STATES)('%s — shows no exclamation mark, emoji or blame to the user', (state) => {
    // The static guard over copy.ts is tests/copy-rules.test.ts; this is the same rule asserted
    // against what actually reached the DOM, which is the half a source scan cannot see (a
    // string assembled at render time, a stray character in this component's own JSX).
    const { container } = render(<StatePanel state={state} decks={['Boros Aggro']} />)
    const rendered = container.textContent ?? ''
    expect(rendered.normalize('NFKC')).not.toContain('!')
    expect(rendered).not.toMatch(/\p{Extended_Pictographic}/u)
    expect(rendered.toLowerCase()).not.toContain('something went wrong')
  })
})
