/**
 * The Scryfall mana-cost scanner, tested against the MEASURED corpus.
 *
 * WHY THIS FILE IS THE PRIMARY GATE AND NOT A SECONDARY ONE. Every other primitive component
 * can be wrong only in how it LOOKS, and jsdom cannot see that anyway. This one can be wrong in
 * what it SAYS: a cost that renders, looks fine, and is missing a symbol — silent dropping is
 * what makes a cost wrong without looking wrong — and the composition reference ships exactly
 * that, in one line:
 *
 *     const parts = String(cost).match(/\d+|[WUBRGC]/gi) || []
 *
 * Measured against this repository's own card database (32,318 non-empty costs), that line
 * renders `{W/U}` as TWO pips, `{2/R}` as a 2 and an R, `{B/P}` as a black pip with the
 * Phyrexian half gone, and `{X}`, `{S}`, `{L}`, `{D}`, `{Y}`, `{Z}` and `{HW}` as NOTHING AT
 * ALL. Those exact four defects are pinned as regression tests at the bottom of this file.
 *
 * THE CORPUS IS THE DATABASE, NOT THE DESIGN NOTES. The obvious cases are four; the shipped
 * card table has NINE families. Three-part hybrid Phyrexian (`{R/W/P}`, Nahiri) and colourless hybrid
 * (`{C/W}`, Ulalek) both break a parser that assumes `/` splits a symbol into exactly two
 * colours, and both are real. So is a seven-digit `{1000000}` (Gleemax) and a five-part
 * ` // ` split card (Who // What // When // Where // Why).
 *
 * AND THE STRUCTURAL CLAIM, which is the one that actually keeps this honest: the
 * scanner is TOTAL. It consumes the whole string, so anything it does not recognise comes back
 * as an `unknown` or `text` token rather than being skipped. That is proven here with a symbol
 * family INVENTED for the test (`{Q/W/E}`), which no enumeration in parse.ts mentions — a guard
 * proven only against the spellings its own author listed is an enumeration test wearing a
 * family test's clothes.
 */

import { describe, expect, it } from 'vitest'

import {
  MANA_COLOUR_ORDER,
  describeManaCost,
  displayGlyph,
  parseManaCost,
  type ManaSymbolToken,
} from './parse'

/** The one symbol in a single-symbol cost, narrowed. Throws loudly rather than returning null. */
const oneSymbol = (cost: string): ManaSymbolToken => {
  const tokens = parseManaCost(cost)
  expect(tokens, `${cost} did not parse to exactly one token`).toHaveLength(1)
  const token = tokens[0]
  if (token.kind !== 'symbol') {
    throw new Error(`${cost} parsed as \`${token.kind}\`, not a recognised symbol`)
  }
  return token
}

describe('the scanner is total (AC 8)', () => {
  it('returns a token list for every string and throws for none', () => {
    // Including the shapes a `match()` would silently return null or [] for. The claim is
    // TOTALITY, so it is asserted over a list rather than on one lucky input.
    const hostile = [
      '',
      '   ',
      '{',
      '}',
      '{W',
      'W}',
      '{}',
      '{{W}}',
      'stray text',
      '{W}garbage{U}',
      '//',
      '{/}',
      '{W//U}',
      '{'.repeat(50),
      'x'.repeat(500),
    ]
    for (const input of hostile) {
      expect(
        () => parseManaCost(input),
        `parseManaCost(${JSON.stringify(input)}) threw`,
      ).not.toThrow()
      expect(Array.isArray(parseManaCost(input))).toBe(true)
    }
  })

  it('consumes the WHOLE input — every character survives in some token', () => {
    // THE STRUCTURAL PROOF, and the reason this test exists rather than a longer symbol list:
    // "never silently drops" is a property of the tokeniser's SHAPE, not of its symbol table.
    // Re-joining every token's `raw` must reproduce the input exactly, for any input at all.
    const inputs = [
      '{2}{W/U}{B/P}{X}',
      '{X}{W} // {2}{R} // {2}{U} // {3}{B} // {1}{G}',
      'leading{W}trailing',
      '{W}{HW}{1000000}{Q/W/E}',
      '{W',
      '{}{}{}',
      '   {W}   ',
    ]
    for (const input of inputs) {
      const rejoined = parseManaCost(input)
        .map((token) => token.raw)
        .join('')
      expect(rejoined, `characters were dropped parsing ${input}`).toBe(input)
    }
  })

  it('is case-insensitive (AC 8c)', () => {
    // Every stored cost in the shipped database is uppercase (measured: zero rows where
    // `mana_cost <> upper(mana_cost)`). Accepting lowercase costs nothing and is one fewer way
    // to be silently wrong — the parser's input is a string, not a database column.
    expect(oneSymbol('{w}').colours).toEqual(['w'])
    expect(oneSymbol('{w/u}').colours).toEqual(['w', 'u'])
    expect(oneSymbol('{b/p}').phyrexian).toBe(true)
    expect(oneSymbol('{x}').glyph).toBe('X')
    expect(oneSymbol('{2/r}').glyph).toBe('2')
  })

  it('treats undefined, null and the empty string identically (AC 4)', () => {
    // The absent cost arrives as `''` from this repo's own data — 5,943 lands carry the empty
    // string and `mana_cost` is never NULL. The wire type is NOT nullable either (`mana_cost:
    // string` on both `Card` and `CardSummary`, from the schemas' NULL-coercing validators). All
    // three spellings are still handled because `parseManaCost` is exported with a
    // `string | null | undefined` parameter for callers the wire does not constrain.
    expect(parseManaCost(undefined)).toEqual([])
    expect(parseManaCost(null)).toEqual([])
    expect(parseManaCost('')).toEqual([])
  })
})

describe('the nine measured families (AC 6)', () => {
  it('colour: {W} {U} {B} {R} {G}', () => {
    for (const letter of ['W', 'U', 'B', 'R', 'G']) {
      const symbol = oneSymbol(`{${letter}}`)
      expect(symbol.colours).toEqual([letter.toLowerCase()])
      expect(symbol.glyph).toBeNull()
      expect(symbol.phyrexian).toBe(false)
    }
  })

  it('generic: {0} through {16}, and Gleemax’s {1000000}', () => {
    expect(oneSymbol('{0}')).toMatchObject({ colours: [], glyph: '0', phyrexian: false })
    expect(oneSymbol('{16}')).toMatchObject({ colours: [], glyph: '16' })
    // Seven glyphs in ONE symbol. A pip whose width is pinned equal to its height cannot hold
    // it, which is why the pip grows rather than clips.
    expect(oneSymbol('{1000000}')).toMatchObject({ colours: [], glyph: '1000000' })
  })

  it('colourless: {C}', () => {
    expect(oneSymbol('{C}')).toMatchObject({ colours: ['c'], glyph: null, phyrexian: false })
  })

  it('variable: {X}', () => {
    expect(oneSymbol('{X}')).toMatchObject({ colours: [], glyph: 'X', phyrexian: false })
  })

  it('two-colour hybrid: all ten pairs are present in the database, and all ten parse', () => {
    const pairs = [
      ['W', 'U'],
      ['U', 'B'],
      ['B', 'R'],
      ['R', 'G'],
      ['G', 'W'],
      ['W', 'B'],
      ['U', 'R'],
      ['B', 'G'],
      ['R', 'W'],
      ['G', 'U'],
    ]
    expect(pairs).toHaveLength(10)
    for (const pair of pairs) {
      const symbol = oneSymbol(`{${pair[0]}/${pair[1]}}`)
      expect(symbol.colours).toEqual([pair[0].toLowerCase(), pair[1].toLowerCase()])
      expect(symbol.glyph).toBeNull()
      expect(symbol.phyrexian).toBe(false)
    }
  })

  it('generic hybrid: {2/W} — the 2 is a GLYPH, never a colour (AC 9)', () => {
    // `split('/')` treating every part as a colour is the defect this asserts against: it would
    // render `{2/R}` as a colour named "2". Both fields are checked, because getting the colour
    // right while dropping the 2 is the same silent loss one level down.
    for (const letter of ['W', 'U', 'B', 'R', 'G']) {
      const symbol = oneSymbol(`{2/${letter}}`)
      expect(symbol.colours).toEqual([letter.toLowerCase()])
      expect(symbol.glyph).toBe('2')
      expect(symbol.phyrexian).toBe(false)
    }
  })

  it('colourless hybrid: {C/W} — Ulalek, Fused Atrocity', () => {
    for (const letter of ['W', 'U', 'B', 'R', 'G']) {
      const symbol = oneSymbol(`{C/${letter}}`)
      expect(symbol.colours).toEqual(['c', letter.toLowerCase()])
      expect(symbol.glyph).toBeNull()
    }
  })

  it('Phyrexian: {B/P}, and Kozilek’s {C/P} — a MODIFIER, not a colour (AC 9)', () => {
    for (const letter of ['W', 'U', 'B', 'R', 'G', 'C']) {
      const symbol = oneSymbol(`{${letter}/P}`)
      expect(symbol.colours).toEqual([letter.toLowerCase()])
      expect(symbol.phyrexian).toBe(true)
      // P is NOT the glyph field: it is its own field, so a caller can render it, name it, or
      // ignore it without re-parsing. `displayGlyph` is what puts it in the pip's glyph slot.
      expect(symbol.glyph).toBeNull()
      expect(displayGlyph(symbol)).toBe('P')
    }
  })

  it('three-part hybrid Phyrexian: {R/W/P} — TWO colours plus a marker (AC 9)', () => {
    // Nahiri, the Unforgiving. The family that breaks any parser assuming `/` splits a symbol
    // into exactly two colours — and the one the obvious four examples never mention.
    for (const raw of ['{R/W/P}', '{G/U/P}', '{G/W/P}', '{R/G/P}']) {
      const symbol = oneSymbol(raw)
      expect(symbol.colours, `${raw} should carry exactly two colours`).toHaveLength(2)
      expect(symbol.phyrexian).toBe(true)
      expect(displayGlyph(symbol)).toBe('P')
    }
    expect(oneSymbol('{R/W/P}').colours).toEqual(['r', 'w'])
  })
})

describe('the // separator, in up to five parts (AC 7)', () => {
  it('surfaces ` // ` as its own text token rather than dropping it', () => {
    // 338 rows in the shipped database look like this. A tokeniser written as
    // `cost.match(/\{[^}]*\}/g)` keeps the braces and drops everything between them, so a split
    // card renders as one run-on cost — the same silent loss as a missing symbol, one level up.
    const tokens = parseManaCost('{2}{B} // {B}')
    expect(tokens.map((token) => token.kind)).toEqual(['symbol', 'symbol', 'text', 'symbol'])
    expect(tokens[2]).toEqual({ kind: 'text', raw: ' // ' })
  })

  it('handles the five-part case — Who // What // When // Where // Why', () => {
    const tokens = parseManaCost('{X}{W} // {2}{R} // {2}{U} // {3}{B} // {1}{G}')
    const separators = tokens.filter((token) => token.kind === 'text')
    expect(separators).toHaveLength(4)
    for (const separator of separators) {
      expect(separator.raw).toBe(' // ')
    }
    // And the symbols still arrive in order, all TEN of them — two per part.
    const symbols: ManaSymbolToken[] = []
    for (const token of tokens) {
      if (token.kind === 'symbol') symbols.push(token)
    }
    expect(symbols).toHaveLength(10)
    expect(symbols[0].glyph).toBe('X')
    expect(symbols[9].colours).toEqual(['g'])
  })
})

describe('malformed input becomes visible, never absent (AC 3, AC 8b)', () => {
  it('emits an unrecognised braced symbol as `unknown`, carrying its inner text', () => {
    // Snow, and the four un-set / recent one-offs, all measured in the shipped database. None
    // of them is in the parser's symbol table, and none of them may vanish.
    for (const inner of ['S', 'HW', 'Y', 'Z', 'L', 'D']) {
      const tokens = parseManaCost(`{${inner}}`)
      expect(tokens).toHaveLength(1)
      expect(tokens[0]).toEqual({ kind: 'unknown', raw: `{${inner}}`, glyph: inner })
    }
  })

  it('emits an INVENTED symbol family as unknown — the structural proof (AC 25)', () => {
    // `{Q/W/E}` appears in no enumeration anywhere in parse.ts. If AC 3 held only because the
    // author listed the symbols they happened to know about, this is where that shows.
    const tokens = parseManaCost('{Q/W/E}')
    expect(tokens).toHaveLength(1)
    expect(tokens[0]).toEqual({ kind: 'unknown', raw: '{Q/W/E}', glyph: 'Q/W/E' })
  })

  it('emits an EMPTY brace pair as unknown, showing the braces themselves', () => {
    // `{}` has no inner text to show, and a pip rendering "" is a pip rendering nothing —
    // silent dropping through the back door. The raw text is what is surfaced instead.
    expect(parseManaCost('{}')).toEqual([{ kind: 'unknown', raw: '{}', glyph: '{}' }])
  })

  it('emits an UNCLOSED brace as text, to the end of the string', () => {
    expect(parseManaCost('{W')).toEqual([{ kind: 'text', raw: '{W' }])
    expect(parseManaCost('{2}{B/')).toEqual([
      { kind: 'symbol', raw: '{2}', colours: [], glyph: '2', phyrexian: false },
      { kind: 'text', raw: '{B/' },
    ])
  })

  it('emits stray text around symbols as text', () => {
    const tokens = parseManaCost('cost: {W}!')
    expect(tokens.map((token) => token.raw)).toEqual(['cost: ', '{W}', '!'])
    expect(tokens[0].kind).toBe('text')
    expect(tokens[2].kind).toBe('text')
  })

  it('rejects a Phyrexian marker with no colour, and a doubled one', () => {
    // Neither is real data. Both are shapes a "P means Phyrexian" special case would wave
    // through into a pip with no colour and no glyph — a blank circle.
    expect(parseManaCost('{P}')[0].kind).toBe('unknown')
    expect(parseManaCost('{P/P}')[0].kind).toBe('unknown')
  })

  it('rejects a symbol with more colours than a pip can render', () => {
    // Three colours is not a hybrid the pip's two-stop gradient can express, and rendering two
    // of the three would be the silent loss this whole file exists to prevent.
    expect(parseManaCost('{W/U/B}')[0].kind).toBe('unknown')
  })

  it('rejects a duplicated colour, but accepts a reordered one (review 2026-07-29)', () => {
    // `{W/W}` is not real data, and waving it through would render a plain white pip announced
    // as "white or white" — a malformed wire value made to look RIGHT, which is the inverse of
    // this module's contract for everything else. Order-insensitivity is different: `{P/W}` and
    // `{U/2}` have exactly one canonical reading, so accepting them is the same deliberate
    // leniency as lowercase — nothing can be misrepresented.
    expect(parseManaCost('{W/W}')[0].kind).toBe('unknown')
    expect(oneSymbol('{P/W}')).toMatchObject({ colours: ['w'], phyrexian: true })
    expect(oneSymbol('{U/2}')).toMatchObject({ colours: ['u'], glyph: '2' })
  })

  it('shows a whitespace-only brace pair as its raw braces, like the empty one', () => {
    // `{ }` with a space glyph is a pip rendering nothing, and the space would survive into the
    // accessible name as a stray word. The raw text is surfaced instead, same as `{}`.
    expect(parseManaCost('{ }')).toEqual([{ kind: 'unknown', raw: '{ }', glyph: '{ }' }])
    expect(describeManaCost(parseManaCost('{2}{ }'))).toBe('2 generic, { }')
  })
})

describe('the exact defects the composition reference ships (regression)', () => {
  it('renders {W/U} as ONE token, not two', () => {
    expect(parseManaCost('{W/U}')).toHaveLength(1)
  })

  it('renders {2/R} as ONE token, not a 2 and an R', () => {
    const tokens = parseManaCost('{2/R}')
    expect(tokens).toHaveLength(1)
    expect(tokens[0]).toMatchObject({ kind: 'symbol', colours: ['r'], glyph: '2' })
  })

  it('keeps {B/P}’s Phyrexian marker instead of dropping it', () => {
    expect(oneSymbol('{B/P}').phyrexian).toBe(true)
  })

  it('renders {X} at all', () => {
    // The mock's `/\d+|[WUBRGC]/gi` matches nothing in `{X}`, so it renders as empty space.
    expect(parseManaCost('{X}')).toHaveLength(1)
  })
})

describe('the accessible-name formatter (AC 15, Q4)', () => {
  const name = (cost: string) => describeManaCost(parseManaCost(cost))

  it('names every family in words, because the pip carries meaning only in colour', () => {
    expect(name('{W}')).toBe('white')
    expect(name('{2}')).toBe('2 generic')
    expect(name('{0}')).toBe('0 generic')
    expect(name('{C}')).toBe('colorless')
    expect(name('{X}')).toBe('X')
    expect(name('{W/U}')).toBe('white or blue')
    expect(name('{2/R}')).toBe('2 generic or red')
    expect(name('{C/W}')).toBe('colorless or white')
    expect(name('{B/P}')).toBe('Phyrexian black')
    expect(name('{C/P}')).toBe('Phyrexian colorless')
    expect(name('{R/W/P}')).toBe('Phyrexian red or white')
  })

  it('reads a whole cost as a list, and the mock’s own example', () => {
    expect(name('{2}{W/U}')).toBe('2 generic, white or blue')
    expect(name('{1}{U}{B}')).toBe('1 generic, blue, black')
  })

  it('reads an unknown symbol as its raw text, which is honest rather than silent', () => {
    expect(name('{HW}')).toBe('HW')
    expect(name('{S}')).toBe('S')
    expect(name('{2}{S}')).toBe('2 generic, S')
  })

  it('keeps the split-card separator in the spoken name', () => {
    expect(name('{2}{B} // {B}')).toBe('2 generic, black // black')
  })

  it('says nothing at all for an absent or whitespace-only cost', () => {
    expect(name('')).toBe('')
    expect(name('   ')).toBe('')
    expect(describeManaCost([])).toBe('')
  })
})

describe('the colour order is a shared, checkable datum', () => {
  it('lists the six pip colours in WUBRG order, colourless last', () => {
    // The non-vacuity anchor for ManaPip's class-coverage guard in tests/token-usage.test.ts,
    // which derives all 21 legal colour classes from this list. A list that quietly lost a
    // member would make that guard assert less while still passing.
    expect(MANA_COLOUR_ORDER).toEqual(['w', 'u', 'b', 'r', 'g', 'c'])
  })

  it('emits hybrid colours in the order the string wrote them, not sorted', () => {
    // The parser reports what it READ. Canonicalising is a CONSUMER'S decision, made per
    // consumer: the accessible-name formatter keeps this written order ("green or white"),
    // while ManaPip's class canonicalises to WUBRG so fifteen classes serve thirty spellings —
    // a deliberate deviation from a symbol-order gradient. Sorting HERE would take the choice
    // away from both.
    expect(oneSymbol('{G/W}').colours).toEqual(['g', 'w'])
    expect(oneSymbol('{W/B}').colours).toEqual(['w', 'b'])
  })
})
