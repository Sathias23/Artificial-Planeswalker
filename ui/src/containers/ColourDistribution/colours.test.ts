/**
 * The colour distribution derivation.
 *
 * ================= A `.ts`, AND THAT IS THE GATE RATHER THAN A PREFERENCE ==============
 *
 * No JSX anywhere below, so this is a `.ts` — `gate-geometry.test.ts:53` forbids `.tsx` under
 * `tests/`, and `curve.test.ts` is a `.ts` for the same reason. The rendered half lives in
 * `ColourDistribution.test.tsx`.
 *
 * ================= EVERY FIXTURE CARD IS A REAL CORPUS ROW ============================
 *
 * `name`, `mana_cost`, `type_line`, `cmc` and `colors` are copied verbatim from the shipped
 * database, measured with `json_type(card_faces)='array'` — never `card_faces IS NOT NULL`,
 * which matches all 38,261 rows because the column is NOT NULL and a non-faced card stores the
 * JSON *string* `'null'`.
 *
 * An invented fixture can be vacuous: a split-card "pin" giving `Cramped Vents // Access Maze` the
 * invented type line `'Land // Land'` has `isLand` exclude the row before the derivation ever sees
 * it — leaving tautological assertions that would stay green through the very fix the pin exists
 * to catch.
 */

import { describe, expect, it } from 'vitest'

import { type ManaColour, parseManaCost } from '../../components/ManaCost/parse'
import type { CardSummary, DeckCardSummary } from '../../api/schema'
import type { CardEntry } from '../../state/cards'
import { boardsOf } from '../../state/deckGroups'
import { coloursOf } from './colours'

// ---------------------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------------------

interface RowOptions {
  quantity?: number
  sideboard?: boolean
  commander?: boolean
}

/** A real corpus card, spelled as the wire spells it. `cmc` is unused here and honest anyway. */
const card = (
  name: string,
  manaCost: string,
  typeLine: string,
  cmc: number,
  colors: string[] = [],
): CardSummary => ({
  id: `id-${name}`,
  name,
  mana_cost: manaCost,
  cmc,
  type_line: typeLine,
  oracle_text: '',
  colors,
  rarity: 'rare',
  set_code: 'tst',
  set_name: 'Test Set',
  collector_number: '1',
  oracle_id: 'oracle-1',
  color_identity: [],
  legalities: {},
  games: [],
})

const row = (summary: CardSummary, options: RowOptions = {}): DeckCardSummary => ({
  card_id: summary.id,
  quantity: options.quantity ?? 1,
  sideboard: options.sideboard ?? false,
  commander: options.commander ?? false,
  card: summary,
})

/** No hydration has happened. The ordinary first-paint state. */
const COLD: Readonly<Record<string, CardEntry>> = {}

/**
 * The `card` the hydrated arm of {@link CardEntry} carries — named off the union rather than
 * imported, so a change to that arm's shape reaches this fixture through `tsc`.
 */
type HydratedCard = Extract<CardEntry, { status: 'hydrated' }>['card']

/** A hydrated cache entry carrying real `card_faces`, for the blank-cost branch. */
const hydrated = (
  summary: CardSummary,
  faces: { mana_cost?: string }[],
): Readonly<Record<string, CardEntry>> => ({
  [summary.id]: {
    status: 'hydrated',
    // `card_faces` is untyped on the wire (`unknown[]`), so a face literal has to be widened to
    // reach it. The cast is on the CARD rather than on the whole entry, which keeps `status`
    // checked against the union: an entry mis-spelling `'hydrated'` would still fail `tsc`.
    card: { ...summary, card_faces: faces } as unknown as HydratedCard,
  },
})

const distributionOf = (
  rows: DeckCardSummary[],
  cards: Readonly<Record<string, CardEntry>> = COLD,
) => coloursOf(boardsOf(rows), cards)

/** The per-colour counts as a plain object, so a failure prints the whole shape. */
const countsOf = (rows: DeckCardSummary[], cards = COLD): Partial<Record<ManaColour, number>> =>
  Object.fromEntries(distributionOf(rows, cards).segments.map((s) => [s.colour, s.count]))

// ---------------------------------------------------------------------------------------
// The front face, and the deck it changes
// ---------------------------------------------------------------------------------------

/**
 * `Prismatic Dragon`'s ten TDM Omen rows, verbatim from the shipped database — quantities
 * included. These ten rows are the ENTIRE difference between the two readings of UX-DR18 for
 * that deck: the other 28 rows contribute 19 pips identically either way.
 */
const PRISMATIC_OMENS: DeckCardSummary[] = [
  row(
    card(
      'Disruptive Stormbrood // Petty Revenge',
      '{4}{G} // {1}{B}',
      'Creature — Dragon // Sorcery — Omen',
      5,
      ['G'],
    ),
    { quantity: 3 },
  ),
  row(
    card('Sagu Wildling // Roost Seek', '{4}{G} // {G}', 'Creature — Dragon // Sorcery — Omen', 5, [
      'G',
    ]),
    { quantity: 3 },
  ),
  row(
    card(
      'Purging Stormbrood // Absorb Essence',
      '{4}{B} // {1}{W}',
      'Creature — Dragon // Instant — Omen',
      5,
      ['B'],
    ),
    { quantity: 2 },
  ),
  row(
    card(
      'Feral Deathgorger // Dusk Sight',
      '{5}{B} // {1}{B}',
      'Creature — Dragon // Instant — Omen',
      6,
      ['B'],
    ),
  ),
  row(
    card(
      'Marang River Regent // Coil and Catch',
      '{4}{U}{U} // {3}{U}',
      'Creature — Dragon // Instant — Omen',
      6,
      ['U'],
    ),
    { quantity: 3 },
  ),
  row(
    card(
      'Runescale Stormbrood // Chilling Screech',
      '{3}{R} // {1}{U}',
      'Creature — Dragon // Instant — Omen',
      4,
      ['R'],
    ),
    { quantity: 2 },
  ),
  row(
    card(
      'Scavenger Regent // Exude Toxin',
      '{3}{B} // {X}{B}{B}',
      'Creature — Dragon // Sorcery — Omen',
      4,
      ['B'],
    ),
    { quantity: 3 },
  ),
  row(
    card(
      'Twinmaw Stormbrood // Charring Bite',
      '{5}{W} // {1}{R}',
      'Creature — Dragon // Instant — Omen',
      6,
      ['W'],
    ),
    { quantity: 2 },
  ),
  row(
    card(
      'Whirlwing Stormbrood // Dynamic Soar',
      '{4}{U} // {2}{G}',
      'Creature — Dragon // Instant — Omen',
      5,
      ['U'],
    ),
    { quantity: 2 },
  ),
  row(
    card(
      'Stormshriek Feral // Flush Out',
      '{4}{R} // {1}{R}',
      'Creature — Dragon // Instant — Omen',
      5,
      ['R'],
    ),
    { quantity: 2 },
  ),
]

/** The same tokeniser over the WHOLE string — the reading that was declined, computed here so
 *  the comparison is a measurement in the suite rather than a claim in a comment. */
const wholeStringPips = (rows: DeckCardSummary[]): Partial<Record<ManaColour, number>> => {
  const counts: Partial<Record<ManaColour, number>> = {}
  for (const entry of rows) {
    for (const token of parseManaCost(entry.card.mana_cost)) {
      if (token.kind !== 'symbol') continue
      for (const colour of token.colours) {
        counts[colour] = (counts[colour] ?? 0) + entry.quantity
      }
    }
  }
  return counts
}

describe('pips come from the FRONT FACE, and `Prismatic Dragon` is the deck it moves', () => {
  it('counts only the front half of the ten Omen rows, and the back half is 26 pips it drops', () => {
    // FRONT: W 2, U 8, B 6, R 4, G 6 — 26 pips.
    expect(countsOf(PRISMATIC_OMENS)).toEqual({ w: 2, u: 8, b: 6, r: 4, g: 6 })
    expect(distributionOf(PRISMATIC_OMENS).total).toBe(26)

    // WHOLE STRING: W 4, U 13, B 16, R 8, G 11 — 52 pips, exactly twice as many, and a
    // DIFFERENT ORDER (black leads instead of blue).
    expect(wholeStringPips(PRISMATIC_OMENS)).toEqual({ w: 4, u: 13, b: 16, r: 8, g: 11 })
  })

  it('reproduces the deck-level 71-versus-45 measurement', () => {
    // The whole deck, measured against the shipped database: whole string 71 pips ordered
    // B > U > G > R > W; front face 45 pips ordered U > B ≈ G > R > W.
    //
    // ⚠️ `OTHER_ROWS = 19` is a RECORDED MEASUREMENT, not a suite-derived number — the
    // remaining 28 rows carry no `//` at all, so
    // they contribute 19 pips identically under both readings, but this test cannot re-derive
    // that premise and would not notice if it drifted. What the suite genuinely re-derives is
    // the ten pinned Omen rows (26 vs 52 above), which is the entire policy difference; the
    // constant only re-bases those halves to the deck-level headline numbers.
    const OTHER_ROWS = 19
    const front = distributionOf(PRISMATIC_OMENS).total + OTHER_ROWS
    const whole =
      Object.values(wholeStringPips(PRISMATIC_OMENS)).reduce((a, b) => a + b, 0) + OTHER_ROWS
    expect(front).toBe(45)
    expect(whole).toBe(71)
    // The headline number: 37% of the bar.
    expect(Math.round(((whole - front) / whole) * 100)).toBe(37)
  })

  it('orders the segments in WUBRG order, colourless last — never by count', () => {
    // `MANA_COLOUR_ORDER` is the checkable datum (`parse.ts:39-43`) and is not copied here.
    expect(distributionOf(PRISMATIC_OMENS).segments.map((s) => s.colour)).toEqual([
      'w',
      'u',
      'b',
      'r',
      'g',
    ])
  })

  it('applies the front-face rule to a TRUE split card too, where either half is a real cast', () => {
    // `Heaven // Earth` — `Instant // Sorcery`, `'{X}{G} // {X}{R}{R}'`, verbatim from the DB.
    // The front-face rationale about Omens ("the back half of an Omen is a cost you pay
    // separately or never") does NOT hold for the 137 true split cards, where either half is a
    // first-class cast — but the RULE still applies, uniformly: every other surface splits the
    // same way, and a policy fork by subclass would make the bar disagree with the deck row.
    // 0 live rows today; this is the subclass every other `' // '` fixture in this file misses.
    const HEAVEN_EARTH = card('Heaven // Earth', '{X}{G} // {X}{R}{R}', 'Instant // Sorcery', 3, [
      'G',
      'R',
    ])
    // Front half only: one green. The back half's `{R}{R}` — a fully castable half — is the
    // documented cost of the front-face rule, invisible on this panel.
    expect(countsOf([row(HEAVEN_EARTH)])).toEqual({ g: 1 })
  })
})

// ---------------------------------------------------------------------------------------
// Hydration
// ---------------------------------------------------------------------------------------

describe('the blank-cost faced cards contribute their real pips once hydrated', () => {
  // `Ayara, Widow of the Realm // Ayara, Furnace Queen` — the deck's own namesake in
  // `Ayara Black Devotion`, blank at the top level, `{1}{B}{B}` on its front face.
  const AYARA = card(
    'Ayara, Widow of the Realm // Ayara, Furnace Queen',
    '',
    'Legendary Creature — Elf Noble // Legendary Creature — Phyrexian Elf Noble',
    3,
  )

  it('contributes NOTHING before the sweep reaches it — the first-paint state', () => {
    expect(countsOf([row(AYARA)])).toEqual({})
    expect(distributionOf([row(AYARA)]).total).toBe(0)
  })

  it('contributes two black pips once the cache holds its faces', () => {
    const cache = hydrated(AYARA, [{ mana_cost: '{1}{B}{B}' }, { mana_cost: '' }])
    expect(countsOf([row(AYARA)], cache)).toEqual({ b: 2 })
  })

  it('reads the FRONT face only when the hydrated back face carries a cost too', () => {
    // `Birgi, God of Storytelling // Harnfel, Horn of Bounty` — a real corpus MDFC whose faces
    // BOTH carry a cost (`{2}{R}` / `{4}{R}`, verbatim from the DB), which is the only shape
    // this rule is visible on.
    const BIRGI = card(
      'Birgi, God of Storytelling // Harnfel, Horn of Bounty',
      '',
      'Legendary Creature — God // Legendary Artifact',
      3,
    )
    const cache = hydrated(BIRGI, [{ mana_cost: '{2}{R}' }, { mana_cost: '{4}{R}' }])
    expect(countsOf([row(BIRGI)], cache)).toEqual({ r: 1 })
  })

  it('leaves a Pathway MDFC land contributing nothing, hydrated or not', () => {
    // 12 of the 46 live blank-cost copies are these, and they are lands: they contribute nothing
    // BEFORE `isLand` is consulted, because neither face carries a cost at all.
    const PATHWAY = card('Branchloft Pathway // Boulderloft Pathway', '', 'Land // Land', 0)
    const cache = hydrated(PATHWAY, [{ mana_cost: '' }, { mana_cost: '' }])
    expect(countsOf([row(PATHWAY, { quantity: 2 })], cache)).toEqual({})
  })
})

// ---------------------------------------------------------------------------------------
// What one symbol contributes
// ---------------------------------------------------------------------------------------

describe('a hybrid pip credits EVERY colour it can be paid with', () => {
  it('gives `{W/U}` one white and one blue, so the total exceeds the symbol count', () => {
    // `Sokka, Lateral Strategist` — `{1}{W/U}{W/U}`, live in `Aanging Loose`.
    const SOKKA = card(
      'Sokka, Lateral Strategist',
      '{1}{W/U}{W/U}',
      'Legendary Creature — Human Warrior Ally',
      3,
      ['U', 'W'],
    )
    expect(countsOf([row(SOKKA)])).toEqual({ w: 2, u: 2 })
    // FOUR pips from TWO coloured symbols. This is the clause the legend has to explain, and
    // the reason the percentages are of THIS total rather than of a symbol count.
    expect(distributionOf([row(SOKKA)]).total).toBe(4)
  })

  it('credits both colours of the one live `{G/W/P}`, and the Phyrexian marker adds none', () => {
    // `Ajani, Sleeper Agent` — `{1}{G}{G/W/P}{W}`, live in `Atraxa Counter Cabinet`. Hybrid AND
    // Phyrexian in one symbol, and the only one in any real deck.
    const AJANI = card(
      'Ajani, Sleeper Agent',
      '{1}{G}{G/W/P}{W}',
      'Legendary Planeswalker — Ajani',
      4,
      ['G', 'W'],
    )
    expect(countsOf([row(AJANI)])).toEqual({ w: 2, g: 2 })
  })
})

describe('Phyrexian is a MODIFIER, never a third colour', () => {
  it('counts `{U/P}` as one blue pip and nothing else', () => {
    // `Tezzeret's Gambit` — `{3}{U/P}`, live in `Dragon-God Superfriends`. Life is not a colour.
    const GAMBIT = card("Tezzeret's Gambit", '{3}{U/P}', 'Sorcery', 4, ['U'])
    expect(countsOf([row(GAMBIT)])).toEqual({ u: 1 })
  })
})

describe('a generic-hybrid credits its COLOUR only', () => {
  it('counts `{2/W}{2/B}{2/G}` as one pip each and the generic halves as none', () => {
    // `Kin-Tree Severance` — the corpus's generic-hybrid shape. ZERO live copies, so this
    // is a corpus card exercising a rule no real deck reaches today, and the test says so.
    const SEVERANCE = card('Kin-Tree Severance', '{2/W}{2/B}{2/G}', 'Instant', 6, ['B', 'G', 'W'])
    expect(countsOf([row(SEVERANCE)])).toEqual({ w: 1, b: 1, g: 1 })
  })
})

describe('generic and `{X}` count for nobody, and invent no colourless segment', () => {
  it('gives a colourless artifact no segment at all', () => {
    // A generic cost is `colours: []` in the tokeniser, which is the whole test — no `unknown`
    // special case is needed either, because an `unknown` token has no `colours` field.
    const SOL_RING = card('Sol Ring', '{1}', 'Artifact', 1)
    expect(countsOf([row(SOL_RING)])).toEqual({})
    expect(distributionOf([row(SOL_RING)]).total).toBe(0)
  })

  it('drops `{X}` and keeps the coloured pips beside it', () => {
    // `Black Sun's Zenith` — a real corpus row with exactly the `{X}{B}{B}` shape that is live
    // today as `Exude Toxin`, the back half of `Scavenger Regent // Exude Toxin` in `Prismatic
    // Dragon`.
    const XSPELL = card("Black Sun's Zenith", '{X}{B}{B}', 'Sorcery', 2, ['B'])
    expect(countsOf([row(XSPELL)])).toEqual({ b: 2 })
  })

  it('DOES count `{C}` as colourless — a real colour in this vocabulary', () => {
    // `Eldrazi Confluence` — `{2}{C}{C}`. ⚠️ ZERO `{C}` symbols appear in ANY of the 40 real
    // decks, so the colourless segment ships untested against real data and this test is
    // its only witness. Stated rather than left as a silent gap.
    const CONFLUENCE = card('Eldrazi Confluence', '{2}{C}{C}', 'Instant', 4)
    expect(countsOf([row(CONFLUENCE)])).toEqual({ c: 2 })
    // …and it sorts LAST, which is `MANA_COLOUR_ORDER`'s own order.
    const mixed = [row(CONFLUENCE), row(card('Doom Blade', '{1}{B}', 'Instant', 2, ['B']))]
    expect(distributionOf(mixed).segments.map((s) => s.colour)).toEqual(['b', 'c'])
  })

  it('drops `{S}` snow — an `unknown` token contributes nothing, pinned', () => {
    // `parse.ts` classifies `{S}` as `unknown`, so a snow pip renders in a deck row (unknown
    // tokens draw) yet is silently absent from this bar. Zero `{S}` symbols in any real deck;
    // this pins the CURRENT behaviour so a `classify` change surfaces here rather than as a
    // silent bar shift. `Icehide Golem` is all-snow; `Wowzer` shows `{S}` dropped while the
    // coloured pips and `{C}` beside it are all kept.
    const GOLEM = card('Icehide Golem', '{S}', 'Snow Artifact Creature — Golem', 1)
    expect(countsOf([row(GOLEM)])).toEqual({})
    expect(distributionOf([row(GOLEM)]).total).toBe(0)

    const WOWZER = card(
      'Wowzer, the Aspirational',
      '{C}{W}{U}{B}{R}{G}{S}',
      'Legendary Snow Creature — Wurm',
      7,
      ['B', 'G', 'R', 'U', 'W'],
    )
    expect(countsOf([row(WOWZER)])).toEqual({ w: 1, u: 1, b: 1, r: 1, g: 1, c: 1 })
  })
})

describe('lands are excluded, by the FRONT-FACE WHOLE-WORD test', () => {
  it('drops a land that carries a real coloured cost', () => {
    // `Glade of the Pump Spells` — `Land`, `{2}{G}`. A land that taps for mana is a SOURCE, not
    // a demand, and the panel's question is "does my mana base match my SPELLS".
    const GLADE = card('Glade of the Pump Spells', '{2}{G}', 'Land', 3, ['G'])
    expect(countsOf([row(GLADE)])).toEqual({})
  })

  it('drops a Land//Adventure whose top-level cost is the ADVENTURE half', () => {
    // `Midgar, City of Mako // Reactor Raid` — front face `Land — Town`, top-level cost
    // `{2}{B}`. `frontFaceCost` would hand back `{2}{B}` quite correctly; `isLand` is what stops
    // a land contributing a black pip, and the two orderings are visible only in a card shaped
    // like this one.
    const MIDGAR = card(
      'Midgar, City of Mako // Reactor Raid',
      '{2}{B}',
      'Land — Town // Sorcery — Adventure',
      0,
    )
    expect(countsOf([row(MIDGAR)])).toEqual({})
  })

  it('is the WHOLE-WORD test, so `Lander Rizzi` is not a land', () => {
    // A substring test would drop this card (and the `Lander` token) out of the panel. 0 live
    // rows either way; the word test removes a way to be wrong later. The real row is
    // `{X}{G}{G}`, cmc 2, `["G"]`.
    const LANDER = card(
      'Lander Rizzi',
      '{X}{G}{G}',
      'Legendary Artifact Creature — Lander Rogue',
      2,
      ['G'],
    )
    expect(countsOf([row(LANDER)])).toEqual({ g: 2 })
  })

  it('does NOT use `groupOf`, which would file an Artifact Land under Artifact', () => {
    // The third land policy, and the tidy-looking mistake: `groupOf('Artifact Land — …')` is
    // `'Artifact'` (first-match-wins over TYPE_GROUPS), which would count 25 corpus lands as
    // spells. Zero live, so no fixture stumbles into it and no eye-check can see it.
    //
    // ⚠️ THE FIRST FIXTURE IS SYNTHETIC, deliberately — the ONLY non-corpus fixture in this
    // file. Every one of the corpus's 25 Artifact Lands is costless (verified: 0 rows with
    // `type_line LIKE '%Artifact Land%'` carry a cost), so a real fixture contributes zero pips
    // under EITHER policy and the guard would stay green through the exact defect it names. A
    // coloured cost is the tooth: under `isLand` (correct) the row is excluded and counts
    // nothing; under `groupOf` (the mistake) it would leak `{ g: 1 }`.
    const SYNTHETIC_ARTIFACT_LAND = card(
      'Synthetic Artifact Land (no corpus card has this shape)',
      '{G}',
      'Artifact Land',
      1,
      ['G'],
    )
    expect(countsOf([row(SYNTHETIC_ARTIFACT_LAND)])).toEqual({})
    // …and one that genuinely IS an artifact still counts — a real corpus row with a coloured
    // cost, so THIS half has teeth too (a generic-cost fixture would assert `{}` either way).
    const SENTINEL = card('Esper Sentinel', '{W}', 'Artifact Creature — Human Soldier', 1, ['W'])
    expect(countsOf([row(SENTINEL)])).toEqual({ w: 1 })
  })
})

// ---------------------------------------------------------------------------------------
// Which rows, and how many of each
// ---------------------------------------------------------------------------------------

describe('the board policy: commander + mainboard, sideboard excluded', () => {
  const MAIN = card('Doom Blade', '{1}{B}', 'Instant', 2, ['B'])
  const COMMANDER = card(
    // Straight apostrophe and real `colors`, both verbatim from the DB.
    "Atraxa, Praetors' Voice",
    '{G}{W}{U}{B}',
    'Legendary Creature — Phyrexian Angel Horror',
    4,
    ['B', 'G', 'U', 'W'],
  )
  const SIDE = card('Abrade', '{1}{R}', 'Instant', 2, ['R'])

  it('counts the commander', () => {
    expect(countsOf([row(MAIN), row(COMMANDER, { commander: true })])).toEqual({
      w: 1,
      u: 1,
      b: 2,
      g: 1,
    })
  })

  it('ignores the sideboard — 87 live pips across 5 decks that do not reach the bar', () => {
    expect(countsOf([row(MAIN), row(SIDE, { sideboard: true, quantity: 4 })])).toEqual({ b: 1 })
  })
})

describe('counts are SUMMED QUANTITIES, never row counts', () => {
  it('multiplies a ×4 row by four', () => {
    // `Pond Prophet` — `{G/U}{G/U}`, live at ×4 in `Astonishing Ant-Man`. Four copies, two
    // hybrid symbols each, both colours credited: 8 green and 8 blue from ONE row.
    const POND = card('Pond Prophet', '{G/U}{G/U}', 'Creature — Frog Advisor', 2, ['G', 'U'])
    expect(countsOf([row(POND, { quantity: 4 })])).toEqual({ u: 8, g: 8 })
    expect(distributionOf([row(POND, { quantity: 4 })]).total).toBe(16)
  })
})

// ---------------------------------------------------------------------------------------
// The percentages
// ---------------------------------------------------------------------------------------

describe('the displayed percentage is rounded and NEED NOT sum to 100', () => {
  // A HAND-ASSEMBLED set of real corpus rows, not a corpus deck, deliberately: no real deck
  // lands on three exactly-equal colours, and the 33/33/33 rounding edge is the whole point of
  // this pin. The eye-check is where real corpus decks render.
  const evenThree = [
    row(card('Doom Blade', '{1}{B}', 'Instant', 2, ['B'])),
    row(card('Lightning Bolt', '{R}', 'Instant', 1, ['R'])),
    row(card('Giant Growth', '{G}', 'Instant', 1, ['G'])),
  ]

  it('prints 33% · 33% · 33% for three equal colours, and says 99 rather than inventing 100', () => {
    const percents = distributionOf(evenThree).segments.map((s) => s.percent)
    expect(percents).toEqual([33, 33, 33])
    expect(percents.reduce((a, b) => a + b, 0)).toBe(99)
  })

  it('prints 100% for a mono-colour deck — the second most common shape in the corpus', () => {
    // 9 of the 40 real decks are mono-colour, and `Ayara Black Devotion` is 116 black pips in
    // ONE segment. `100%`, not `100.0%`.
    const mono = [row(card('Doom Blade', '{1}{B}', 'Instant', 2, ['B']), { quantity: 4 })]
    const { segments, total } = distributionOf(mono)
    expect(segments).toHaveLength(1)
    expect(segments[0].percent).toBe(100)
    expect(total).toBe(4)
  })

  it('prints a rounded 0% honestly rather than flooring a non-zero count to 1%', () => {
    // Deliberate: the count beside it is the un-rounded truth, and a floor would make the
    // printed percentage disagree with its own arithmetic in the one case anyone would check.
    // NOT producible from live data — the thinnest live share is 1 of 26 (3.8%) — so this
    // fixture is synthetic ON PURPOSE and says so.
    const lopsided = [
      row(card('Doom Blade', '{1}{B}', 'Instant', 2, ['B']), { quantity: 300 }),
      row(card('Lightning Bolt', '{R}', 'Instant', 1, ['R'])),
    ]
    const segments = distributionOf(lopsided).segments
    expect(segments.map((s) => [s.colour, s.count, s.percent])).toEqual([
      ['b', 300, 100],
      ['r', 1, 0],
    ])
  })
})

// ---------------------------------------------------------------------------------------
// The empty case, asserted against the DERIVATION
// ---------------------------------------------------------------------------------------

describe('the zero-pip case', () => {
  it('is EMPTY, not a bar of zeroes, for a deck with no cards', () => {
    const { segments, total } = distributionOf([])
    expect(segments).toEqual([])
    expect(total).toBe(0)
  })

  it('is empty for a land-only deck — cards, but nothing for a colour bar to describe', () => {
    // NO DECK IN THE CORPUS REACHES THIS STATE — all 40 have at least 2 pips — so it is
    // asserted against the derivation rather than against a hand-built deck.
    const lands = [
      row(card('Forest', '', 'Basic Land — Forest', 0), { quantity: 24 }),
      row(card('Glade of the Pump Spells', '{2}{G}', 'Land', 3, ['G']), { quantity: 4 }),
    ]
    expect(distributionOf(lands).total).toBe(0)
    expect(distributionOf(lands).segments).toEqual([])
  })

  it('is empty for a deck of purely generic costs, with cards in it', () => {
    const artifacts = [row(card('Sol Ring', '{1}', 'Artifact', 1), { quantity: 4 })]
    expect(distributionOf(artifacts).total).toBe(0)
  })

  it('never emits a segment with a zero count', () => {
    // A colour with no pips has no entry at all — the legend is a list of what the deck HAS,
    // not six rows of which four say nothing. The percentage arithmetic never divides by zero
    // because a zero total emits nothing to divide.
    const mono = [row(card('Doom Blade', '{1}{B}', 'Instant', 2, ['B']))]
    expect(distributionOf(mono).segments.every((s) => s.count > 0)).toBe(true)
  })
})

// ---------------------------------------------------------------------------------------
// Purity
// ---------------------------------------------------------------------------------------

describe('the derivation is pure and copies nothing (AD-12)', () => {
  it('returns the same answer twice and mutates neither argument', () => {
    const rows = [...PRISMATIC_OMENS]
    const boards = boardsOf(rows)
    const first = coloursOf(boards, COLD)
    const second = coloursOf(boards, COLD)
    expect(second).toEqual(first)
    // The `boards` REFERENCE is the deck's identity for `deckMemory.ts` and `CardDetail`'s
    // effect, so this function may read it and may not rebuild it.
    expect(boardsOf(rows)).toEqual(boards)
  })
})
