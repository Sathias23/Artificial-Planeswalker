import { describe, expect, it } from 'vitest'

import type { CardSummary } from '../api/schema'
import type { CardEntry } from '../state/cards'
import { frontFaceCost, frontFaceName } from './frontFaceCost'

/**
 * The front-face resolution, held to the three shapes measured in the shipped database.
 *
 * Every card named below is a REAL row from the corpus, with its real field values —
 * not a hand-invented fixture. That matters for this module specifically: the whole reason it
 * exists is that the obvious one-line implementation is right for one shape and wrong for two.
 */

const summaryOf = (fields: Partial<CardSummary>): CardSummary =>
  ({
    id: 'ffffffff-0000-0000-0000-000000000000',
    name: 'Untitled',
    mana_cost: '',
    cmc: 0,
    type_line: 'Card',
    oracle_text: null,
    colors: [],
    rarity: 'common',
    set_code: 'tst',
    ...fields,
  }) as CardSummary

const hydrated = (faces: { mana_cost?: string | null }[]): CardEntry =>
  ({
    status: 'hydrated',
    card: { ...summaryOf({}), card_faces: faces },
  }) as unknown as CardEntry

describe('frontFaceName — the free half (AC 23)', () => {
  it('splits the combined name 99.0% of faced cards store', () => {
    // Real row: the worst front-face name in any live deck once split (33 chars), and the worst
    // UNSPLIT name in any live deck (56) before it.
    expect(frontFaceName('Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel')).toBe(
      'Sephiroth, Fabled SOLDIER',
    )
  })

  it('leaves a single-faced name untouched', () => {
    expect(frontFaceName('Lightning Bolt')).toBe('Lightning Bolt')
  })

  it('does NOT truncate the one real card whose name carries an UNSPACED slash-slash', () => {
    // THE TRAP, and the reason this module does not reuse `deckGroups.ts`'s `frontFace`.
    // `'SP//dr, Piloted by Peni'` is a SINGLE-faced Legendary Artifact Creature; the loose
    // separator pattern renders it as `'SP'`. Measured: exactly 1 such card in 38,261.
    expect(frontFaceName('SP//dr, Piloted by Peni')).toBe('SP//dr, Piloted by Peni')
  })

  it('trims the split result rather than leaving the separator whitespace', () => {
    expect(frontFaceName('Fire // Ice')).toBe('Fire')
  })

  it('falls back to the raw name when the front segment trims to nothing — never empty', () => {
    // The "Never empty" contract, held at its own boundary: a name beginning with
    // the separator would otherwise slice+trim to `''` and render an empty name cell. Measured
    // 0 such rows in the corpus; the guard is one branch.
    expect(frontFaceName(' // Backface')).toBe(' // Backface')
  })
})

describe('frontFaceCost — shape 1: the split cost, resolved with NO fetch (AC 23)', () => {
  it('splits an Adventure card and never lets a separator reach ManaCost', () => {
    // Real row: `Murderous Rider // Swift End`, 27 live rows carry this shape.
    const summary = summaryOf({
      name: 'Murderous Rider // Swift End',
      mana_cost: '{1}{B}{B} // {1}{B}{B}',
    })
    expect(frontFaceCost(summary, undefined)).toBe('{1}{B}{B}')
  })

  it('splits BEFORE testing non-blankness — the ordering that closes the spoken-separator deferral', () => {
    // If the "non-blank means verbatim" branch ran first, this would return the whole string and
    // `describeManaCost` would speak "slash slash".
    const summary = summaryOf({ mana_cost: '{2}{R} // {3}{G}' })
    expect(frontFaceCost(summary, undefined)).not.toContain('//')
  })

  it('splits from the summary even when a hydrated entry is also available', () => {
    const summary = summaryOf({ mana_cost: '{1}{B}{B} // {1}{B}{B}' })
    expect(frontFaceCost(summary, hydrated([{ mana_cost: '{9}{9}' }]))).toBe('{1}{B}{B}')
  })
})

describe('frontFaceCost — shape 2: a real top-level cost, verbatim (AC 23)', () => {
  it('returns a single-faced cost unchanged', () => {
    // Real row: the widest single-faced live cost, 5 pips.
    expect(frontFaceCost(summaryOf({ mana_cost: '{W}{U}{B}{R}{G}' }), undefined)).toBe(
      '{W}{U}{B}{R}{G}',
    )
  })

  it('returns a faced card that DOES carry a top-level cost verbatim — 16 of the 40 live DFCs', () => {
    expect(frontFaceCost(summaryOf({ mana_cost: '{2}{R}' }), undefined)).toBe('{2}{R}')
  })
})

describe('frontFaceCost — shape 3: the blank cost that only hydration can answer (AC 23, Q2)', () => {
  it('reads card_faces[0] when the summary cost is blank — 26 live rows / 18 cards', () => {
    // Real row: `Agadeem's Awakening // Agadeem, the Undercrypt`, blank top-level cost.
    const summary = summaryOf({
      name: "Agadeem's Awakening // Agadeem, the Undercrypt",
      mana_cost: '',
    })
    expect(frontFaceCost(summary, hydrated([{ mana_cost: '{X}{B}{B}{B}' }]))).toBe('{X}{B}{B}{B}')
  })

  it('re-splits a hydrated face cost that itself carries the separator (c4-7 review)', () => {
    // `card_faces` is untyped on the wire, so a face-level `' // '` is not impossible — merely
    // unmeasured-zero today. Without the re-check, branch 3 would hand the separator to
    // `ManaCost` verbatim and reopen the spoken-separator deferral this module closes.
    const summary = summaryOf({ mana_cost: '' })
    expect(frontFaceCost(summary, hydrated([{ mana_cost: '{1}{W} // {2}{U}' }]))).toBe('{1}{W}')
  })

  it('draws NOTHING until the sweep arrives — the stated first-paint consequence', () => {
    const summary = summaryOf({ mana_cost: '' })
    expect(frontFaceCost(summary, undefined)).toBeNull()
  })

  it.each([
    ['summary', { status: 'summary', summary: summaryOf({ mana_cost: '' }) }],
    ['loading', { status: 'loading', summary: summaryOf({ mana_cost: '' }) }],
    [
      'unknown',
      { status: 'unknown', reason: null, placeholder: null, summary: null, retryable: false },
    ],
  ])('reads no faces from the %s tier — only `hydrated` carries card_faces', (_label, entry) => {
    expect(frontFaceCost(summaryOf({ mana_cost: '' }), entry as CardEntry)).toBeNull()
  })
})

describe('frontFaceCost — shape 4: genuinely costless, and it stays that way (AC 23)', () => {
  it('returns null for a Pathway whose front face has no cost even AFTER hydration', () => {
    // Real row: `Clearwater Pathway // Murkwater Pathway`, `Land // Land`. 12 live rows / 6 cards.
    const summary = summaryOf({
      name: 'Clearwater Pathway // Murkwater Pathway',
      mana_cost: '',
      type_line: 'Land // Land',
    })
    expect(frontFaceCost(summary, hydrated([{ mana_cost: '' }]))).toBeNull()
  })

  it('treats whitespace as blank rather than drawing an empty pip row', () => {
    expect(frontFaceCost(summaryOf({ mana_cost: '   ' }), undefined)).toBeNull()
  })

  it('survives a hydrated entry with no card_faces at all', () => {
    const entry = { status: 'hydrated', card: summaryOf({}) } as unknown as CardEntry
    expect(frontFaceCost(summaryOf({ mana_cost: '' }), entry)).toBeNull()
  })
})
