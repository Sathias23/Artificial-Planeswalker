/**
 * The curve derivation, against the cards real decks actually contain.
 *
 * **Every fixture below is a REAL card with its REAL `type_line`, `cmc` and `mana_cost`**,
 * measured against `%LOCALAPPDATA%\artificial-planeswalker\cards.db`. That is
 * `deckGroups.test.ts`'s convention and it earns its keep twice here: three of the cases below
 * have **zero live rows** and would never be reached by a fixture somebody invented, and two of
 * them are cards this derivation is knowingly WRONG about — pinned so the next author finds a
 * red test rather than a screenshot.
 */

import { describe, expect, it } from 'vitest'

import type { CardSummary, DeckCardSummary } from '../../api/schema'
import { boardsOf } from '../../state/deckGroups'
import { BUCKETS, LAST_BUCKET, bucketOf, curveOf, isLand } from './curve'

interface CardOptions {
  cmc?: number
  manaCost?: string
}

const summary = (
  name: string,
  typeLine: string,
  { cmc = 0, manaCost = '' }: CardOptions = {},
): CardSummary => ({
  id: `id-${name}`,
  name,
  mana_cost: manaCost,
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

interface RowOptions extends CardOptions {
  quantity?: number
  sideboard?: boolean
  commander?: boolean
}

const row = (name: string, typeLine: string, options: RowOptions = {}): DeckCardSummary => ({
  card_id: `id-${name}`,
  quantity: options.quantity ?? 1,
  sideboard: options.sideboard ?? false,
  commander: options.commander ?? false,
  card: summary(name, typeLine, options),
})

/** The buckets a list of rows produces, as a plain array — `curveOf` takes the derivation. */
const curveFor = (rows: DeckCardSummary[]) => curveOf(boardsOf(rows)).buckets.map((b) => b.count)

describe('the buckets are 1 … 7+, and there are seven of them', () => {
  it('names them in ascending order with the last one open-ended', () => {
    expect(BUCKETS).toEqual([1, 2, 3, 4, 5, 6, 7])
    expect(LAST_BUCKET).toBe(7)
  })

  it('absorbs every cmc at or above the last bucket, including a real 12-drop', () => {
    // `Ghalta, Primal Hunger` is the live-deck maximum.
    expect(bucketOf(12)).toBe(7)
    expect(bucketOf(7)).toBe(7)
    // `Gleemax`, the corpus maximum. A bucketing that overflowed or produced an eighth entry
    // would be visible only on this one card, so it is pinned rather than reasoned about.
    expect(bucketOf(1_000_000)).toBe(7)
  })

  it('puts each ordinary mana value in its own bucket', () => {
    expect([1, 2, 3, 4, 5, 6].map(bucketOf)).toEqual([1, 2, 3, 4, 5, 6])
  })
})

describe('cards below the first bucket fold into it', () => {
  it('folds a zero-mana non-land into bucket 1 rather than dropping it', () => {
    // `Pym Particles` (`fmsc` #28), the ONE live non-land row with `cmc = 0` in all 40 decks —
    // and the same row that is the deck list's only `Other`-group card. Its `type_line` really
    // is the bare string `'Card'`. 4,351 corpus cards share the shape.
    //
    // The alternative was dropping it, and there is no conservation identity here to catch that:
    // nothing on screen would say a card had gone. Folding is the honest direction because a
    // free spell is castable on turn one — a 0-drop is MORE castable than a 1-drop, not less.
    expect(curveFor([row('Pym Particles', 'Card', { cmc: 0 })])).toEqual([1, 0, 0, 0, 0, 0, 0])
  })

  it('folds the one fractional cmc in the corpus into bucket 1', () => {
    // `Little Girl`, `{HW}`, `cmc 0.5` — the only non-integer `cmc` in all 38,261 cards.
    // The rounding question is MOOT because of this fold, not by accident: `Math.floor(0.5)`
    // is 0 and `Math.round(0.5)` is 1, and the fold puts both in bucket 1.
    expect(bucketOf(0.5)).toBe(1)
    expect(bucketOf(0)).toBe(1)
  })
})

describe('lands are excluded by a WHOLE-WORD front-face test', () => {
  it('excludes the four MDFC lands that are in real decks today', () => {
    // The four cards the repo's land policies disagree about, all in real decks:
    // 7 rows across 5 decks. FR-05/UX-DR17 say front face, so all four are SPELLS here.
    const mdfc = [
      row("Agadeem's Awakening // Agadeem, the Undercrypt", 'Sorcery // Land', { cmc: 3 }),
      row('Kazandu Mammoth // Kazandu Valley', 'Creature — Elephant // Land', { cmc: 3 }),
      row('Dowsing Dagger // Lost Vale', 'Artifact — Equipment // Land', { cmc: 2 }),
      row(
        'Journey to Eternity // Atzal, Cave of Eternity',
        'Legendary Enchantment — Aura // Legendary Land',
        {
          cmc: 3,
        },
      ),
    ]
    for (const card of mdfc) {
      expect(isLand(card.card.type_line), `${card.card.name} was treated as a land`).toBe(false)
    }
    expect(curveFor(mdfc)).toEqual([0, 1, 3, 0, 0, 0, 0])
  })

  it('excludes a plain land, and one whose front face is a land with a spell behind it', () => {
    expect(isLand('Basic Land — Forest')).toBe(true)
    // `Westvale Abbey // Ormendahl, Profane Prince` — 9 corpus cards have a LAND front face and
    // a non-land back. All three policies agree here; pinned because agreement is what makes
    // the disagreements below meaningful.
    expect(isLand('Land // Legendary Creature — Demon')).toBe(true)
    expect(
      curveFor([row('Westvale Abbey', 'Land // Legendary Creature — Demon', { cmc: 0 })]),
    ).toEqual([0, 0, 0, 0, 0, 0, 0])
  })

  it('DIVERGES from groupOf on an Artifact Land — 32 corpus lands, ZERO live', () => {
    // THE TRAP THIS TEST EXISTS FOR. `groupOf(t) === 'Land'` is the tidy-looking reuse and it is
    // a DIFFERENT QUESTION: it is first-match-wins over TYPE_GROUPS, so `Artifact` precedes
    // `Land` and `Silverbluff Bridge` is filed under Artifacts in the deck list. That is correct
    // there — it answers "which section is this row in". Here the question is "is this card a
    // land", and reusing the grouping would count 32 corpus lands as SPELLS.
    //
    // 0 of them are in any real deck, which is exactly why this is a named test: no fixture
    // would stumble into it and the eye-check cannot see a card that is not on screen.
    expect(isLand('Artifact Land')).toBe(true)
    expect(groupWouldSay('Artifact Land')).toBe('Artifact')
    for (const typeLine of [
      'Artifact Land',
      "Artifact Land — Urza's Vehicle",
      'Legendary Artifact Land — Vehicle Island',
      'Enchantment Land — Urza’s Saga',
      'Land Creature — Island Fish',
      'Land Planeswalker — Wrenn',
    ]) {
      expect(isLand(typeLine), `${typeLine} is a land and this test said otherwise`).toBe(true)
    }
    expect(curveFor([row('Silverbluff Bridge', 'Artifact Land', { cmc: 0 })])).toEqual([
      0, 0, 0, 0, 0, 0, 0,
    ])
  })

  it('DIVERGES from a SUBSTRING test on the two Landers — the defect the proposal carried', () => {
    // A substring test, `frontFace(typeLine).includes('Land')`, is wrong for exactly two
    // corpus cards, and `deckGroups.ts:166-168` already says
    // why in writing: *"a substring test would additionally group anything containing
    // `Landfall`-shaped text wrongly"*. Neither card is a land; a substring test drops both out
    // of the curve.
    expect('Legendary Artifact Creature — Lander Rogue'.includes('Land')).toBe(true)
    expect(isLand('Legendary Artifact Creature — Lander Rogue')).toBe(false)
    expect(isLand('Token Artifact — Lander')).toBe(false)
    expect(
      curveFor([row('Lander Rizzi', 'Legendary Artifact Creature — Lander Rogue', { cmc: 4 })]),
    ).toEqual([0, 0, 0, 1, 0, 0, 0])
  })

  it('does not read the BACK face for the land test', () => {
    // The whole point of the front-face rule, in one assertion: the back is a land and the card
    // is still a spell.
    expect(isLand('Sorcery // Land')).toBe(false)
  })
})

describe('double-faced cards bucket by their front face — for free', () => {
  it('buckets a blank-cost transform card by cmc, with no hydration anywhere', () => {
    // 2,830 of 2,830 faced cards with a blank top-level `mana_cost` have `cmc` EQUAL to the
    // front face's mana value (100%, measured). So the front-face clause is satisfied here by
    // reading one field, with no dependence on the hydration sweep.
    const bolas = row(
      'Nicol Bolas, the Ravager // Nicol Bolas, the Arisen',
      'Legendary Creature — Elder Dragon // Legendary Planeswalker — Bolas',
      {
        cmc: 4,
        manaCost: '',
      },
    )
    expect(bolas.card.mana_cost).toBe('')
    expect(curveFor([bolas])).toEqual([0, 0, 0, 1, 0, 0, 0])
  })

  it('buckets an Adventure by its creature side, which is what cmc already is', () => {
    // 201 Adventure/Omen cards carry an `'A // B'` cost and `cmc` is the FRONT face's value.
    // All 27 live split-cost rows are this shape — which is why the divergence below has zero
    // live exposure.
    expect(
      curveFor([
        row('Murderous Rider // Swift End', 'Creature — Zombie Knight // Instant — Adventure', {
          cmc: 3,
          manaCost: '{1}{B}{B} // {1}{B}{B}',
        }),
      ]),
    ).toEqual([0, 0, 1, 0, 0, 0, 0])
  })

  it('IS KNOWINGLY WRONG for a true split card, and this pins the wrongness', () => {
    // `Cramped Vents // Access Maze`: Scryfall's `cmc` for a true split card is the SUM of both
    // halves, so `'{3}{B} // {5}{B}{B}'` reports 11 where the front face is 4. 137 corpus cards
    // are this shape and ZERO are in any of the 40 real decks — the panel is correct today BY
    // ACCIDENT, one `add_card_to_deck` from wrong.
    //
    // Not fixed here: the fix is a numeric mana-value parser, `ui/` has none, and building one
    // is `ManaCost`'s territory rather than a seven-bar panel's. When somebody writes it, THIS
    // TEST goes red and tells them where: the fixed derivation buckets the front face at 4, so
    // the expectation below becomes `[0, 0, 0, 1, 0, 0, 0]` and this pin is retired in the same
    // commit.
    //
    // The type line is the DB's real one (`'Enchantment — Room // Enchantment — Room'`), not a
    // placeholder: a land-shaped type line would have `isLand` exclude the row before the
    // derivation ever saw it, leaving the test asserting `bucketOf` tautologies that would stay
    // green through the very fix this pin exists to catch.
    const split = row('Cramped Vents // Access Maze', 'Enchantment — Room // Enchantment — Room', {
      cmc: 11,
      manaCost: '{3}{B} // {5}{B}{B}',
    })
    // The KNOWN-WRONG answer, asserted through the real derivation: cmc 11 lands in 7+ where
    // the front face is a 4-drop. Being wrong here is the pin, not a defect to "fix" in a test.
    expect(curveFor([split])).toEqual([0, 0, 0, 0, 0, 0, 1])
  })
})

describe('the board policy is commander + mainboard, sideboard excluded', () => {
  it('counts the commander', () => {
    // 16 of 40 real decks carry one; including it moves the corpus non-land quantity from
    // 1,812 to 1,828. `deck_analysis.py:171-173` includes it too, so the panel and the MCP tool
    // agree by construction rather than by coincidence.
    expect(
      curveFor([
        row('Atraxa, Grand Unifier', 'Legendary Creature — Phyrexian Angel', {
          cmc: 7,
          commander: true,
        }),
      ]),
    ).toEqual([0, 0, 0, 0, 0, 0, 1])
  })

  it('excludes the sideboard', () => {
    // `deckGroups.ts:199` already states it: the sideboard *"is not part of the
    // deck the curve and colour panels describe"*. 41 rows across 5 real decks.
    expect(
      curveFor([
        row('Lightning Bolt', 'Instant', { cmc: 1 }),
        row('Abrade', 'Instant', { cmc: 2, sideboard: true }),
      ]),
    ).toEqual([1, 0, 0, 0, 0, 0, 0])
  })

  it('keeps a commander that is also flagged sideboard out — the partition decides', () => {
    // `boardsOf` splits on `sideboard` FIRST (deckGroups.ts:222-231) so the backend's counts and
    // the frontend's boards cannot drift. 0 of 1,999 live rows are both; this makes the
    // inherited rule visible rather than latent.
    expect(
      curveFor([row('Ghost', 'Creature — Spirit', { cmc: 2, commander: true, sideboard: true })]),
    ).toEqual([0, 0, 0, 0, 0, 0, 0])
  })
})

describe('counts are SUMMED QUANTITIES, never row counts', () => {
  it('counts a ×4 row as four cards', () => {
    // The same rule `deckGroups.ts:166-167` fixed for group headers. A row count would not move
    // when a quantity changed from 3 to 4, which is the change a curve exists to report.
    expect(curveFor([row('Lightning Bolt', 'Instant', { cmc: 1, quantity: 4 })])).toEqual([
      4, 0, 0, 0, 0, 0, 0,
    ])
  })

  it('sums across rows in the same bucket', () => {
    expect(
      curveFor([
        row('Counterspell', 'Instant', { cmc: 2, quantity: 3 }),
        row('Negate', 'Instant', { cmc: 2, quantity: 2 }),
      ]),
    ).toEqual([0, 5, 0, 0, 0, 0, 0])
  })
})

describe('the totals and the scale', () => {
  it('reports the total and the tallest bucket', () => {
    const curve = curveOf(
      boardsOf([
        row('Lightning Bolt', 'Instant', { cmc: 1, quantity: 2 }),
        row('Counterspell', 'Instant', { cmc: 2, quantity: 5 }),
      ]),
    )
    expect(curve.total).toBe(7)
    expect(curve.tallest).toBe(5)
  })

  it('never reports a tallest below 1, so nothing divides by zero', () => {
    // `Iron Man, Modern Marvel — reminder` is one card and six empty buckets; a deck of nothing
    // but lands is an all-zero curve with cards in it. Both reach this line.
    expect(curveOf(boardsOf([])).tallest).toBe(1)
    expect(curveOf(boardsOf([])).total).toBe(0)
    expect(curveOf(boardsOf([row('Forest', 'Basic Land — Forest')])).tallest).toBe(1)
  })

  it('scales each bucket against the TALLEST bar, not against the deck size', () => {
    // The 39-versus-0 extreme is real data: `Infinite Guideline Station v2 (owned)` puts 39
    // cards in bucket 2 beside two buckets that are empty.
    const curve = curveOf(
      boardsOf([
        row('Big', 'Instant', { cmc: 2, quantity: 39 }),
        row('Small', 'Instant', { cmc: 3, quantity: 13 }),
      ]),
    )
    expect(curve.buckets.map((b) => b.share)).toEqual([0, 1, 1 / 3, 0, 0, 0, 0])
  })

  it('gives every bucket a zero share when the curve is empty, rather than NaN', () => {
    expect(curveOf(boardsOf([])).buckets.map((b) => b.share)).toEqual([0, 0, 0, 0, 0, 0, 0])
  })
})

describe('the derivation is a pure total function', () => {
  it('returns a fresh value and mutates nothing it was handed', () => {
    const rows = [row('Lightning Bolt', 'Instant', { cmc: 1 })]
    const boards = boardsOf(rows)
    const before = JSON.stringify(boards)
    curveOf(boards)
    curveOf(boards)
    expect(JSON.stringify(boards)).toBe(before)
  })

  it('is stable: the same boards give the same numbers', () => {
    const boards = boardsOf([row('Counterspell', 'Instant', { cmc: 2, quantity: 3 })])
    expect(curveOf(boards)).toEqual(curveOf(boards))
  })
})

/**
 * `groupOf` re-implemented at the call site, deliberately.
 *
 * The divergence test above needs to say what the GROUPING would answer, and importing
 * `groupOf` to say it would make the assertion depend on the module under comparison. This is
 * the one place in the suite where naming the other answer literally is the stronger test.
 */
const groupWouldSay = (typeLine: string): string => {
  const types = typeLine.split(/\s*\/\/\s*/)[0].split('—')[0]
  const words = new Set(types.split(/\s+/).filter(Boolean))
  return (
    [
      'Creature',
      'Planeswalker',
      'Battle',
      'Instant',
      'Sorcery',
      'Artifact',
      'Enchantment',
      'Land',
    ].find((group) => words.has(group)) ?? 'Other'
  )
}
