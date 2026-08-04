import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { boardsOf } from '../../state/deckGroups'
import { CardGrid } from './CardGrid'

/**
 * The card-art grid (story c4-4, AC 12–AC 16).
 *
 * ================= WHAT THIS SUITE CANNOT CARRY (AC 29) ================================
 *
 * jsdom applies no stylesheet and has no layout engine, so **not one assertion here is about
 * the grid as a grid**: that the track is `repeat(auto-fill, minmax(176px, 1fr))` and that the
 * gap is `var(--space-panel-gap)` are SOURCE claims, asserted POSITIVELY in
 * `tests/shell.test.ts`'s "ships the blessed track and the token gap" test (review 2026-08-04 —
 * this header's first spelling pointed at the ban-shaped guards, which only refuse bad forms
 * and would have stayed green through a drift to a different good-looking one). The
 * content-floored-track ban and the px-literal DESIGN.md citation check are the negative half.
 * That it actually reflows between 1100px and 2560px on a real screen is **Task 7's**.
 *
 * What IS provable here is the thing the derivation exists to protect: which cards reach the
 * glass, in which order, and from which board.
 *
 * THE FIXTURES GO THROUGH `boardsOf` RATHER THAN BEING HAND-BUILT `DeckBoards`. A hand-built
 * board would let this file assert an order the real derivation never produces — the c4-2 probe
 * (b) lesson exactly: the obvious fixtures do not discriminate the rule they appear to test.
 */

const deckCard = (
  name: string,
  typeLine: string,
  extra: { quantity?: number; commander?: boolean; sideboard?: boolean } = {},
) => ({
  card_id: `id-${name}`,
  quantity: extra.quantity ?? 1,
  sideboard: extra.sideboard ?? false,
  commander: extra.commander ?? false,
  card: {
    id: `id-${name}`,
    name,
    mana_cost: '',
    cmc: 0,
    type_line: typeLine,
    oracle_text: '',
    colors: [] as string[],
    rarity: 'rare',
    set_code: 'tst',
  },
})

/**
 * A deck with all three boards populated, and with its groups DELIBERATELY out of
 * `TYPE_GROUPS` order in the payload — the wire's own docstring warns that `cards` order is
 * "not meaningful", so a fixture already in the right order could not tell an ordered render
 * from an unordered one.
 */
const MIXED = [
  deckCard('Swamp', 'Basic Land — Swamp', { quantity: 34 }),
  deckCard('Counterspell', 'Instant'),
  deckCard('Llanowar Elves', 'Creature — Elf Druid'),
  deckCard('Atraxa, Grand Unifier', 'Legendary Creature — Phyrexian Angel', { commander: true }),
  deckCard('Duress', 'Sorcery', { sideboard: true, quantity: 3 }),
]

const captions = () =>
  [...document.querySelectorAll('.card-tile-caption')].map((node) => node.textContent)

describe('the grid renders the store’s answer, not a second one (AC 15)', () => {
  it('draws the commander first, then the mainboard in TYPE_GROUPS order', () => {
    render(<CardGrid boards={boardsOf(MIXED)} />)

    // Commander first and unlabelled; then Creature, Instant, Sorcery, Land — `TYPE_GROUPS`
    // order, which `boardsOf` imposed and this component only preserves. The payload order was
    // Land, Instant, Creature, Commander, so an unordered render would show that instead.
    expect(captions()).toEqual(['Atraxa, Grand Unifier', 'Llanowar Elves', 'Counterspell', 'Swamp'])
  })

  it('does not re-sort, re-group or re-filter — the tiles come from the boards verbatim', () => {
    // The negative form of the same claim, and the one that would catch a `filter`/`sort` added
    // later "just for the grid": the rendered list must equal the flattening of the boards it
    // was handed, whatever those boards happen to be.
    const boards = boardsOf(MIXED)
    render(<CardGrid boards={boards} />)

    const expected = [...boards.commander, ...boards.mainboard.flatMap((group) => group.cards)].map(
      (entry) => entry.card.name,
    )
    expect(captions()).toEqual(expected)
  })
})

describe('the three boards each have a home or a named owner (AC 14)', () => {
  it('renders the commander — 16 of 40 real decks have one', () => {
    render(<CardGrid boards={boardsOf(MIXED)} />)
    expect(screen.getByText('Atraxa, Grand Unifier')).toBeVisible()
  })

  it('does NOT render the sideboard — 41 rows across 5 real decks, and c4-7 owns them', () => {
    // The boundary, asserted rather than left to "not mentioned". The art grid is the DECK; the
    // sideboard mixed in would inflate every count a reader takes off the screen. c4-7's deck
    // list draws it, from the same `boards.sideboard` this component ignores.
    render(<CardGrid boards={boardsOf(MIXED)} />)
    expect(screen.queryByText('Duress')).toBeNull()
    // …and it is IGNORED rather than lost: the derivation still carries it, so c4-7 has it.
    expect(boardsOf(MIXED).sideboard.map((entry) => entry.card.name)).toEqual(['Duress'])
  })

  it('loses no mainboard card — conservation, at the render', () => {
    const boards = boardsOf(MIXED)
    render(<CardGrid boards={boards} />)
    // DERIVED from the boards, not restated from the fixture (review 2026-08-04 — the first
    // spelling was `commander.length + 4 - 1`, a magic-number census of MIXED that a fixture
    // edit would silently re-mean). The identity is the derivation's own conservation claim:
    // everything the commander and mainboard boards carry reaches the glass, nothing else does.
    const carried = boards.commander.length + boards.mainboard.flatMap((g) => g.cards).length
    expect(carried).toBeGreaterThan(0)
    expect(captions()).toHaveLength(carried)
    expect(screen.getAllByRole('listitem')).toHaveLength(carried)
  })
})

describe('the structure (AC 13, AC 16)', () => {
  it('is a real ul/li, not a div soup and not a painted role', () => {
    const { container } = render(<CardGrid boards={boardsOf(MIXED)} />)

    const list = screen.getByRole('list')
    expect(list.tagName).toBe('UL')
    // A `role` attribute painted onto a div would satisfy `getByRole` and fail this.
    expect(list.getAttribute('role')).toBeNull()
    expect(container.querySelectorAll('li')).toHaveLength(4)
    for (const item of container.querySelectorAll('li')) {
      expect(item.parentElement).toBe(list)
      expect(within(item as HTMLElement).getByRole('button')).toBeVisible()
    }
  })

  it('sits in an UNTITLED panel, which invents no name (Q6)', () => {
    render(<CardGrid boards={boardsOf(MIXED)} />)
    // c2-7's ruling: an unnamed `<section>` has no role at all, which is right — a generic
    // invented title would add an identical entry to every landmark list. The counts a reader
    // needs are already in the `h1` and `DeckBadges`; a panel title would be the third copy.
    expect(screen.queryByRole('region')).toBeNull()
    expect(screen.queryByRole('heading')).toBeNull()
  })

  it('one tile per DISTINCT card, with the copies on the badge (not repeated tiles)', () => {
    render(<CardGrid boards={boardsOf(MIXED)} />)
    // 34 Swamps are ONE tile carrying `×34`, which is the whole point of the badge — and the
    // measured reason the grid is 99 tiles rather than 100 for the largest real deck.
    expect(screen.getAllByRole('listitem')).toHaveLength(4)
    expect(screen.getByText('×34')).toBeVisible()
  })
})

describe('an empty deck reaches this story, and it must not invent c4-12’s copy (Q10)', () => {
  it('renders an empty list and nothing else', () => {
    const { container } = render(<CardGrid boards={boardsOf([])} />)

    // `boardsOf([])` returns three empty boards. The honest render is an empty `<ul>` inside an
    // untitled panel — a PLACE for c4-12 to put EXPERIENCE.md:70's line, rather than a state
    // pretending to be one. Writing that copy here would fail `copy-rules.test.ts` and pre-empt
    // a story; crashing, or drawing a titled panel with a stray header, would be worse than
    // either.
    expect(screen.getByRole('list')).toBeVisible()
    expect(container.querySelectorAll('li')).toHaveLength(0)
    expect(container.textContent).toBe('')
  })
})
