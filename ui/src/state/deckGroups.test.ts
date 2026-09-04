/**
 * The type-group derivation, against the type lines real decks actually contain (FR-05,
 * UX-DR17).
 *
 * **Every fixture below is a REAL card with its REAL `type_line`**, measured against
 * the live database at `%LOCALAPPDATA%\artificial-planeswalker\cards.db`. Invented uuids and
 * invented type lines would prove the function does what it does; these prove it does what the
 * corpus needs, and the four double-faced cards in particular are the exact four the repo's own
 * two land policies disagree about — all four of them in decks today.
 *
 * The `card_id`s are shaped like the real ones but are not asserted against the database: the
 * derivation never reads them, and pinning 40 uuids into a test file would be 40 things to
 * rewrite the next time a set is reprinted.
 */

import { describe, expect, it } from 'vitest'

import type { CardSummary, DeckCardSummary, DeckDetail } from '../api/schema'
import {
  TYPE_GROUPS,
  boardsOf,
  boardsOfDeck,
  byManaValueThenName,
  frontFace,
  groupOf,
} from './deckGroups'

/** A `CardSummary` with only the fields the derivation reads made meaningful. */
const summary = (name: string, typeLine: string, cmc = 0): CardSummary => ({
  id: `id-${name}`,
  name,
  mana_cost: '',
  cmc,
  type_line: typeLine,
  oracle_text: '',
  colors: [],
  rarity: 'rare',
  set_code: 'tst',
  set_name: 'Test Set',
  collector_number: '1',
  oracle_id: 'oracle-1',
  color_identity: [],
  legalities: {},
  games: [],
})

interface RowOptions {
  quantity?: number
  sideboard?: boolean
  commander?: boolean
  cmc?: number
}

const row = (
  name: string,
  typeLine: string,
  { quantity = 1, sideboard = false, commander = false, cmc = 0 }: RowOptions = {},
): DeckCardSummary => ({
  card_id: `id-${name}`,
  quantity,
  sideboard,
  commander,
  card: summary(name, typeLine, cmc),
})

describe('the front face is the whole rule (FR-05, UX-DR17)', () => {
  it('takes the segment before the first separator', () => {
    expect(frontFace('Creature — Elephant // Land')).toBe('Creature — Elephant')
  })

  it('leaves a single-faced type line untouched', () => {
    expect(frontFace('Legendary Creature — Phyrexian Praetor')).toBe(
      'Legendary Creature — Phyrexian Praetor',
    )
  })

  it('tolerates the unspaced separator the literal split would miss', () => {
    // Not in the corpus — every one of the 3,183 `//` type lines uses the spaced form — so this
    // costs nothing today. It is here because the failure it prevents is silent: the whole
    // unsplit string matches no group and the card lands in `Other` looking like data loss.
    expect(frontFace('Sorcery//Land')).toBe('Sorcery')
  })
})

describe('the four cards the repo’s two land policies disagree about', () => {
  // src/viewer/view_model.py::is_land splits on the front face; src/logic/mana_curve.py and
  // src/logic/assessment/mana_base.py test the WHOLE string for "land". FR-05 and UX-DR17 both
  // say front face, so all four of these are NOT lands — and all four are in real decks.
  it.each([
    ['Agadeem’s Awakening // Agadeem, the Undercrypt', 'Sorcery // Land', 'Sorcery'],
    ['Kazandu Mammoth // Kazandu Valley', 'Creature — Elephant // Land', 'Creature'],
    ['Dowsing Dagger // Lost Vale', 'Artifact — Equipment // Land', 'Artifact'],
    [
      'Journey to Eternity // Atzal, Cave of Eternity',
      'Legendary Enchantment — Aura // Legendary Land',
      'Enchantment',
    ],
  ])('%s groups as its front face, not as a Land', (_name, typeLine, expected) => {
    expect(groupOf(typeLine)).toBe(expected)
    expect(groupOf(typeLine)).not.toBe('Land')
  })

  it('would call all four LANDS under src/logic/mana_curve.py’s whole-string policy', () => {
    // The disagreement spelled out: `"land" in type_line.lower()` is that module's rule, and
    // running it here shows the four are real rather than theoretical. **This is a statement
    // about the PYTHON policy, not a discriminating test of the code below** — see the block
    // that follows, which is the one that actually holds `groupOf` to the front face.
    const wholeString = (typeLine: string) => typeLine.toLowerCase().includes('land')
    for (const typeLine of [
      'Sorcery // Land',
      'Creature — Elephant // Land',
      'Artifact — Equipment // Land',
      'Legendary Enchantment — Aura // Legendary Land',
    ]) {
      expect(wholeString(typeLine)).toBe(true)
      expect(groupOf(typeLine)).not.toBe('Land')
    }
  })
})

/**
 * THE CARDS THAT ACTUALLY DISCRIMINATE THE FRONT-FACE RULE — probe (b)'s real home.
 *
 * **Found by a probe that DEFEATED the block above.** Deleting `frontFace()` from `groupOf` left
 * all 27 assertions green, and the reason is worth the paragraph: `groupOf` already strips
 * everything after the em-dash, which removes the back face outright for any DFC whose FRONT face
 * carries a subtype — three of the four cards above — and the fourth (`Sorcery // Land`) is saved
 * by `Sorcery` preceding `Land` in the precedence order. So those four prove the FR-05-versus-
 * `mana_curve.py` point and prove nothing about this implementation.
 *
 * A type line discriminates only when the front face has NO em-dash (so the subtype strip cannot
 * remove the back face) AND the back face's group PRECEDES the front's. Measured across the
 * corpus: **29 distinct type lines**, and **0 of them in any live deck** — so the
 * rule is latent for the discriminating shapes, exactly as `'Card // Card'` is. Latent is not
 * untestable, and these are real printings by name.
 */
describe('the front face decides, even when the back face outranks it — probe (b)', () => {
  it.each([
    // The sharpest one in the corpus: a LAND whose back is a Legendary Creature. The broken rule
    // files a land under Creatures, which is a nonland count and a curve both wrong at once.
    ['Westvale Abbey // Ormendahl, Profane Prince', 'Land // Legendary Creature — Demon', 'Land'],
    [
      'Autumnal Gloom // Ancient of the Equinox',
      'Enchantment // Creature — Treefolk',
      'Enchantment',
    ],
    ['Incubation // Incongruity', 'Sorcery // Instant', 'Sorcery'],
    ['The Arkenstone // Seek the Heart', 'Legendary Artifact // Sorcery — Adventure', 'Artifact'],
    ['Porcine Portent // Lend a Ham', 'Enchantment // Instant — Adventure', 'Enchantment'],
    [
      "Liliana's Other Contract // Liliana's Undead Minion",
      'Enchantment // Legendary Planeswalker — You',
      'Enchantment',
    ],
  ])('%s groups by its front face', (_name, typeLine, expected) => {
    expect(groupOf(typeLine)).toBe(expected)
  })

  it('is a REAL discrimination — the broken rule answers differently on every one', () => {
    // The non-vacuity half, and the assertion the first version of this suite was missing: each
    // fixture above must produce a DIFFERENT answer under the whole-string reading, or it is
    // another card that happens to agree.
    //
    // The counterfactual is spelled out RATHER THAN routed through `groupOf`, and that is the
    // second correction this block needed: `broken = (t) => groupOf(t.split('—')[0])` applies
    // `frontFace` inside `groupOf` and therefore models the CORRECT rule with extra steps — it
    // reported "no discrimination" on cards that discriminate perfectly well.
    const broken = (typeLine: string) => {
      const words = new Set(
        typeLine
          .split('—')[0]
          .split(/\s+/)
          .filter((word) => word !== ''),
      )
      return TYPE_GROUPS.find((group) => words.has(group)) ?? 'Other'
    }
    for (const [typeLine, correct] of [
      ['Land // Legendary Creature — Demon', 'Land'],
      ['Enchantment // Creature — Treefolk', 'Enchantment'],
      ['Sorcery // Instant', 'Sorcery'],
      ['Legendary Artifact // Sorcery — Adventure', 'Artifact'],
    ] as const) {
      expect(groupOf(typeLine)).toBe(correct)
      expect(broken(typeLine)).not.toBe(correct)
    }
  })
})

describe('a multi-type front face lands in exactly one group, by the declared order', () => {
  it.each([
    ['Artifact Creature — Golem', 'Creature'],
    ['Enchantment Creature — Spirit', 'Creature'],
    ['Legendary Artifact Planeswalker — Equipment', 'Planeswalker'],
    ['Legendary Artifact Creature — Golem', 'Creature'],
    // Dryad Arbor's shape. 4 in the corpus, 0 in any deck — the declared consequence of
    // first-match-wins, asserted so it is a decision on the record rather than a surprise.
    ['Land Creature — Forest Dryad', 'Creature'],
  ])('%s → %s', (typeLine, expected) => {
    expect(groupOf(typeLine)).toBe(expected)
  })

  it('reads the ONE list for both order and precedence, so they cannot drift', () => {
    // The order is asserted by value, not merely by membership: the deck grid renders these
    // headers and the cold-open inspection target ("the first card of the first type group")
    // depends on it being deterministic.
    expect([...TYPE_GROUPS]).toEqual([
      'Creature',
      'Planeswalker',
      'Battle',
      'Instant',
      'Sorcery',
      'Artifact',
      'Enchantment',
      'Land',
      'Other',
    ])
    // Precedence IS that order: the earlier of any two co-occurring types wins.
    expect(groupOf('Artifact Creature')).toBe('Creature')
    expect(TYPE_GROUPS.indexOf('Creature')).toBeLessThan(TYPE_GROUPS.indexOf('Artifact'))
  })

  it('matches whole words, not substrings', () => {
    // The whole-string policy's other failure mode, and the reason the match is word-keyed:
    // a subtype or an ability word containing a type name must not decide the group.
    expect(groupOf('Enchantment — Aura')).toBe('Enchantment')
    expect(groupOf('Instant — Arcane')).toBe('Instant')
    // The subtype half is dropped before matching, so a Creature subtype cannot make a
    // non-creature a Creature.
    expect(groupOf('Artifact — Equipment')).toBe('Artifact')
  })
})

describe('a type the scheme does not name is CARRIED, never dropped', () => {
  it('files the corpus’s literal "Card" type line under the residual group', () => {
    // "Pym Particles" — 2 live deck rows, and the only rows outside the eight primary types.
    expect(groupOf('Card')).toBe('Other')
  })

  it('files the latent "Card // Card" printing under it too, by its front face', () => {
    // 2,274 in the corpus, 0 in any deck. Its real front-face type lives only in
    // `card_faces[0].type_line`, which the deck payload does not carry — so this is LATENT,
    // declared, and correct-as-far-as-the-data-goes rather than fixed by 99 extra requests.
    expect(groupOf('Card // Card')).toBe('Other')
  })

  it('never answers undefined, for any string at all', () => {
    for (const typeLine of ['', '   ', '—', '//', 'Whatsit — Thing', 'LAND', 'lands']) {
      expect(TYPE_GROUPS).toContain(groupOf(typeLine))
    }
    // Case matters, and that is correct: Scryfall's type lines are title-case by contract, and a
    // case-insensitive match would group an ability word like "landfall" in a subtype.
    expect(groupOf('LAND')).toBe('Other')
  })
})

describe('the comparator — ascending mana value, ties alphabetical', () => {
  it('orders by cmc ascending', () => {
    const cheap = row('Llanowar Elves', 'Creature — Elf Druid', { cmc: 1 })
    const dear = row('Wrath of God', 'Sorcery', { cmc: 4 })

    expect(byManaValueThenName(cheap, dear)).toBeLessThan(0)
    expect(byManaValueThenName(dear, cheap)).toBeGreaterThan(0)
  })

  it('breaks a cmc tie alphabetically by name, via localeCompare', () => {
    const a = row('Avacyn, Angel of Hope', 'Creature — Angel', { cmc: 8 })
    const z = row('Zealous Conscripts', 'Creature — Human Warrior', { cmc: 8 })

    expect(byManaValueThenName(a, z)).toBeLessThan(0)
    expect(byManaValueThenName(z, a)).toBeGreaterThan(0)
    expect(
      byManaValueThenName(a, row('Avacyn, Angel of Hope', 'Creature — Angel', { cmc: 8 })),
    ).toBe(0)
  })

  it('handles a fractional cmc — 0.5 exists (Little Girl) and sorts between 0 and 1', () => {
    const zero = row('Ornithopter', 'Artifact Creature — Thopter', { cmc: 0 })
    const half = row('Little Girl', 'Creature — Human Child', { cmc: 0.5 })
    const one = row('Llanowar Elves', 'Creature — Elf Druid', { cmc: 1 })

    expect([one, half, zero].sort(byManaValueThenName).map((c) => c.card.name)).toEqual([
      'Ornithopter',
      'Little Girl',
      'Llanowar Elves',
    ])
  })
})

describe('each board arrives sorted — cmc ascending, ties alphabetical', () => {
  it('sorts within a mainboard group, whatever order the payload used', () => {
    // Deliberately supplied in DESCENDING cmc — the wire's order is "not meaningful" and a
    // fixture already ascending could not tell a sorted render from a preserved one.
    const boards = boardsOf([
      row('Wrath of God', 'Sorcery', { cmc: 4 }),
      row('Ponder', 'Sorcery', { cmc: 1 }),
      row('Divination', 'Sorcery', { cmc: 3 }),
    ])

    expect(boards.mainboard[0].cards.map((c) => c.card.name)).toEqual([
      'Ponder',
      'Divination',
      'Wrath of God',
    ])
  })

  it('breaks within-group cmc ties alphabetically', () => {
    const boards = boardsOf([
      row('Zealous Conscripts', 'Creature — Human Warrior', { cmc: 5 }),
      row('Avacyn, Angel of Hope', 'Creature — Angel', { cmc: 5 }),
    ])

    expect(boards.mainboard[0].cards.map((c) => c.card.name)).toEqual([
      'Avacyn, Angel of Hope',
      'Zealous Conscripts',
    ])
  })

  it('sorts an all-cmc-0 Lands group alphabetically', () => {
    const boards = boardsOf([
      row('Swamp', 'Basic Land — Swamp', { cmc: 0 }),
      row('Forest', 'Basic Land — Forest', { cmc: 0 }),
    ])

    expect(boards.mainboard[0].cards.map((c) => c.card.name)).toEqual(['Forest', 'Swamp'])
  })

  it('sorts the sideboard with the same comparator', () => {
    const boards = boardsOf([
      row('Duress', 'Sorcery', { cmc: 1, sideboard: true }),
      row('Pithing Needle', 'Artifact', { cmc: 1, sideboard: true }),
      row('Rest in Peace', 'Enchantment', { cmc: 2, sideboard: true }),
    ])

    expect(boards.sideboard.map((c) => c.card.name)).toEqual([
      'Duress',
      'Pithing Needle',
      'Rest in Peace',
    ])
  })

  it('sorts the commander board too — usually 1 card, and consistency is free', () => {
    const boards = boardsOf([
      row('Tymna the Weaver', 'Legendary Creature — Human Cleric', { cmc: 3, commander: true }),
      row('Thrasios, Triton Hero', 'Legendary Creature — Merfolk Wizard', {
        cmc: 2,
        commander: true,
      }),
    ])

    expect(boards.commander.map((c) => c.card.name)).toEqual([
      'Thrasios, Triton Hero',
      'Tymna the Weaver',
    ])
  })

  it('never mutates the input — the payload array and its rows are untouched', () => {
    const cards = [row('Wrath of God', 'Sorcery', { cmc: 4 }), row('Ponder', 'Sorcery', { cmc: 1 })]
    const before = [...cards]

    boardsOf(cards)

    expect(cards).toEqual(before)
    expect(cards.map((c) => c.card.name)).toEqual(['Wrath of God', 'Ponder'])
  })
})

describe('the three boards, and what each one holds', () => {
  const cards = [
    row('Atraxa, Grand Unifier', 'Legendary Creature — Phyrexian Angel', { commander: true }),
    row('Llanowar Elves', 'Creature — Elf Druid', { quantity: 4 }),
    row('Wrath of God', 'Sorcery'),
    row('Forest', 'Basic Land — Forest', { quantity: 10 }),
    row('Pithing Needle', 'Artifact', { sideboard: true, quantity: 2 }),
  ]

  it('keeps the commander out of the type groups', () => {
    const boards = boardsOf(cards)

    expect(boards.commander.map((card) => card.card.name)).toEqual(['Atraxa, Grand Unifier'])
    // The failure this prevents, stated as an assertion: a commander filed under "Creature"
    // misstates the deck to anyone reading the list, and inflates the creature count by one.
    const creatures = boards.mainboard.find((group) => group.group === 'Creature')
    expect(creatures?.cards.map((card) => card.card.name)).toEqual(['Llanowar Elves'])
  })

  it('keeps the sideboard out of the type groups', () => {
    const boards = boardsOf(cards)

    expect(boards.sideboard.map((card) => card.card.name)).toEqual(['Pithing Needle'])
    expect(boards.mainboard.some((group) => group.group === 'Artifact')).toBe(false)
  })

  it('emits groups in TYPE_GROUPS order, and only the ones with cards in them', () => {
    const boards = boardsOf(cards)

    expect(boards.mainboard.map((group) => group.group)).toEqual(['Creature', 'Sorcery', 'Land'])
  })

  it('counts a group by summed QUANTITY, never by row count', () => {
    const boards = boardsOf(cards)
    const lands = boards.mainboard.find((group) => group.group === 'Land')

    expect(lands?.cards).toHaveLength(1)
    expect(lands?.quantity).toBe(10)
  })

  it('splits on `sideboard` FIRST, so the boards agree with the backend’s own arithmetic', () => {
    // `deck.py::_counts` sums on `sideboard` alone, so a sideboarded commander is counted in
    // `sideboard_count`. 0 live rows are both today; this pins the latent case to the same
    // answer the backend gives rather than to the one "commander first" would give.
    const boards = boardsOf([
      row('Odd One', 'Legendary Creature — Human', { sideboard: true, commander: true }),
    ])

    expect(boards.commander).toHaveLength(0)
    expect(boards.sideboard).toHaveLength(1)
    expect(boards.sideboardQuantity).toBe(1)
    expect(boards.mainboardQuantity).toBe(0)
  })
})

describe('CONSERVATION — nothing is lost and the counts still sum', () => {
  const cards = [
    row('Atraxa, Grand Unifier', 'Legendary Creature — Phyrexian Angel', { commander: true }),
    row('Llanowar Elves', 'Creature — Elf Druid', { quantity: 4 }),
    row('Kazandu Mammoth // Kazandu Valley', 'Creature — Elephant // Land', { quantity: 2 }),
    row('Agadeem’s Awakening // Agadeem, the Undercrypt', 'Sorcery // Land'),
    row('Pym Particles', 'Card', { quantity: 2 }),
    row('Reversible Thing', 'Card // Card'),
    row('Invasion of Ravnica', 'Battle — Siege'),
    row('Forest', 'Basic Land — Forest', { quantity: 10 }),
    row('Pithing Needle', 'Artifact', { sideboard: true, quantity: 2 }),
    row('Rest in Peace', 'Enchantment', { sideboard: true }),
  ]

  const detail: DeckDetail = {
    id: 'deck-1',
    name: 'Conservation Fixture',
    format: 'brawl',
    strategy: null,
    color_identity: [],
    tags: [],
    // The backend's own arithmetic: `sum(quantity for dc if not dc.sideboard)` and its
    // complement. Written out here so the assertions below compare the derivation against the
    // WIRE'S numbers rather than against a total this file computed the same way twice.
    mainboard_count: 1 + 4 + 2 + 1 + 2 + 1 + 1 + 10,
    sideboard_count: 2 + 1,
    distinct_cards: 10,
    created_at: '2025-08-02T00:00:00Z',
    updated_at: '2025-08-02T00:00:00Z',
    cards,
  }

  it('places every single row in exactly one board-or-group', () => {
    const boards = boardsOfDeck(detail)
    const placed = [
      ...boards.commander,
      ...boards.mainboard.flatMap((group) => group.cards),
      ...boards.sideboard,
    ]

    expect(placed).toHaveLength(cards.length)
    // Exactly one, not at least one: a duplicate placement inflates the grid as surely as a
    // dropped row shrinks it, and only a set comparison catches both.
    expect(new Set(placed.map((card) => card.card_id)).size).toBe(cards.length)
    for (const card of cards) {
      expect(placed).toContain(card)
    }
  })

  it('sums to the payload’s OWN counts, board by board', () => {
    const boards = boardsOfDeck(detail)

    expect(boards.commanderQuantity + boards.mainboardQuantity).toBe(detail.mainboard_count)
    expect(boards.sideboardQuantity).toBe(detail.sideboard_count)
    // …and the group quantities sum to the mainboard, which is the half a per-group bug hides in.
    expect(boards.mainboard.reduce((total, group) => total + group.quantity, 0)).toBe(
      boards.mainboardQuantity,
    )
  })

  it('carries the unnameable types rather than dropping them — probe (c)', () => {
    const boards = boardsOfDeck(detail)
    const other = boards.mainboard.find((group) => group.group === 'Other')

    // Three rows the scheme cannot name: two "Card" and one "Card // Card". A derivation that
    // filtered to known types instead of falling back would lose them silently and the
    // conservation assertions above would be the only thing that noticed. The order below is the
    // comparator's answer, not insertion order: both rows are cmc 0, so the tie breaks
    // alphabetically — which happens to match how the fixture lists them.
    expect(other?.cards.map((card) => card.card.name)).toEqual([
      'Pym Particles',
      'Reversible Thing',
    ])
    expect(other?.quantity).toBe(3)
  })

  it('holds for the empty deck, which must not be a special case', () => {
    const boards = boardsOf([])

    expect(boards.mainboard).toEqual([])
    expect(boards.commander).toEqual([])
    expect(boards.sideboard).toEqual([])
    expect(boards.mainboardQuantity).toBe(0)
  })
})
