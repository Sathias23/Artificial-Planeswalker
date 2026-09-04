/**
 * The Scryfall mana-cost scanner and its accessible-name formatter.
 *
 * PURE, TOTAL, AND IT IMPORTS NOTHING. No state, no hook, no DOM, no React — it is a function
 * over a string, held to the presentation-only posture by `ui/tests/shell.test.ts` with an
 * empty import list, exactly as `Badge/tones.ts` is.
 *
 * ==== THE ONE RULE THAT MATTERS =========================================================
 * IT SCANS THE WHOLE STRING. It does not match a list of known patterns and keep the hits.
 * That distinction is the entire story: a `match()` DISCARDS everything it does not recognise
 * BY CONSTRUCTION, so "never silently drops" cannot be a property of the symbol table — it has
 * to be a property of the tokeniser's shape. The composition reference gets this wrong in one
 * line (`String(cost).match(/\d+|[WUBRGC]/gi)`), and measured against this repository's own
 * 32,318 real costs that line loses hybrid, generic-hybrid, Phyrexian, `{X}`, `{S}`, `{C}`
 * variants and the ` // ` separator — a cost that renders, looks fine, and is wrong.
 *
 * The consequence is that EVERY character of the input comes back in some token's `raw`, and
 * parse.test.ts asserts exactly that by re-joining them. An unrecognised braced symbol becomes
 * `unknown` (a pip showing its own text); anything outside braces becomes `text`. Nothing is
 * skipped, so a symbol family invented after this file was written still renders.
 *
 * ==== THE OUTPUT SHAPE ==================================================================
 * THREE kinds rather than two, because `unknown` and `text` RENDER DIFFERENTLY — one is a pip,
 * one is inline text — and collapsing them would draw the ` // ` separator as a chip.
 *
 * COLOURS, GLYPH AND PHYREXIAN-NESS ARE SEPARATE FIELDS. A `split('/')` that treats
 * every part as a colour renders `{R/W/P}` as a three-way split and `{2/R}` as a colour named
 * "2", and BOTH are in the real data: `{R/W/P}` is two colours plus a marker, `{2/R}` is one
 * colour plus a glyph, `{C/P}` is one colour plus a marker.
 *
 * `raw` is on every kind so the formatter below — and any future tooltip — never has to
 * re-derive the source text it came from.
 */

/** The six colours a pip can be filled with. `c` is colourless, not "no colour". */
export type ManaColour = 'w' | 'u' | 'b' | 'r' | 'g' | 'c'

/**
 * WUBRG order, colourless last. Exported because it is a CHECKABLE datum rather than a private
 * constant: ManaPip canonicalises a hybrid pair against it to pick a class, and the
 * class-coverage guard in `ui/tests/token-usage.test.ts` derives all 21 legal colour classes
 * from it. A private copy in each of those three places is three ways to disagree.
 */
export const MANA_COLOUR_ORDER: ManaColour[] = ['w', 'u', 'b', 'r', 'g', 'c']

/** A symbol the scanner recognised: `{W}`, `{2}`, `{X}`, `{W/U}`, `{2/R}`, `{R/W/P}`. */
export interface ManaSymbolToken {
  kind: 'symbol'
  /** The source text INCLUDING its braces, so the whole input can be reconstructed. */
  raw: string
  /** One or two fill colours, in the order the string wrote them. Empty for generic and `{X}`. */
  colours: ManaColour[]
  /** The text in the pip's glyph slot: a generic count, or `X`. `null` for a plain colour pip. */
  glyph: string | null
  /** A MODIFIER, never a third colour. See `displayGlyph` for how it is drawn. */
  phyrexian: boolean
}

/** A braced symbol whose inner text matched nothing. It still renders — as a pip, visibly. */
export interface ManaUnknownToken {
  kind: 'unknown'
  raw: string
  /** What the pip shows. The inner text, or the raw braces when there is no inner text. */
  glyph: string
}

/** Anything outside braces. In the real data that is only ` // ` and whitespace. */
export interface ManaTextToken {
  kind: 'text'
  raw: string
}

export type ManaToken = ManaSymbolToken | ManaUnknownToken | ManaTextToken

/** The five colours plus colourless, as the letters Scryfall writes them. */
const COLOUR_LETTERS: Record<string, ManaColour> = {
  W: 'w',
  U: 'u',
  B: 'b',
  R: 'r',
  G: 'g',
  C: 'c',
}

const DIGITS = /^\d+$/

/**
 * One braced symbol, classified. The ONLY place the recognised families are enumerated — and
 * the enumeration is deliberately SMALL, because everything it does not name falls through to
 * `unknown` rather than being dropped.
 */
const classify = (raw: string, inner: string): ManaSymbolToken | ManaUnknownToken => {
  // A WHITESPACE-ONLY inner (`{ }`) shows the raw braces for the same reason `{}` does: a pip
  // rendering spaces is a pip rendering nothing — silent dropping through the back door — and
  // the space would survive into the accessible name as a stray word.
  const unknown: ManaUnknownToken = {
    kind: 'unknown',
    raw,
    glyph: inner.trim() === '' ? raw : inner,
  }
  const upper = inner.toUpperCase()

  // Generic, including `{0}` and Gleemax's seven-digit `{1000000}`.
  if (DIGITS.test(upper)) {
    return { kind: 'symbol', raw, colours: [], glyph: upper, phyrexian: false }
  }
  // The variable cost. `{Y}` and `{Z}` are NOT included: they exist in exactly one un-set card
  // and behave differently, and guessing them into this branch would be a claim nobody measured.
  if (upper === 'X') {
    return { kind: 'symbol', raw, colours: [], glyph: 'X', phyrexian: false }
  }

  const colours: ManaColour[] = []
  const others: string[] = []
  let phyrexian = false

  for (const part of upper.split('/')) {
    // A SECOND `P` is not a second marker — it falls through to `others` and makes the whole
    // symbol unknown. `{P/P}` is not real data, and a "P means Phyrexian" special case that
    // swallowed it would produce a pip with no colour and no glyph: a blank circle.
    if (part === 'P' && !phyrexian) {
      phyrexian = true
      continue
    }
    const colour = COLOUR_LETTERS[part]
    if (colour !== undefined) {
      colours.push(colour)
      continue
    }
    others.push(part)
  }

  // ONE or TWO colours. Zero means nothing to fill the pip with (so `{P}` alone is unknown, and
  // so is `{HW}`); three means a gradient with two stops cannot express it, and rendering two of
  // the three would be exactly the silent loss this module exists to prevent.
  if (colours.length < 1 || colours.length > 2) return unknown
  // A DUPLICATED colour (`{W/W}`) is not real data, and waving it through would render a plain
  // white pip announced as "white or white" — a malformed wire value made to look right, which
  // is the `{P/P}` rule again one branch down. Order-insensitivity (`{P/W}`,
  // `{U/2}`) is DELIBERATE leniency, like case: the canonical reading is the only one possible.
  if (colours.length === 2 && colours[0] === colours[1]) return unknown
  // At most one glyph, and it must be a generic count — `{2/W}`. Anything else in that slot is a
  // family this scanner does not know, which is a fact worth SHOWING rather than approximating.
  if (others.length > 1) return unknown
  const glyph = others.length === 1 ? others[0] : null
  if (glyph !== null && !DIGITS.test(glyph)) return unknown

  return { kind: 'symbol', raw, colours, glyph, phyrexian }
}

/**
 * Scryfall's cost notation, tokenised. TOTAL: every string yields a list, nothing throws, and
 * every character of the input survives in some token's `raw`.
 *
 * `undefined`, `null` and `''` behave identically: the absent cost arrives as `''` from
 * this repo's own data — 5,943 lands carry the empty string and `mana_cost` is never NULL.
 *
 * The wire type is NOT nullable (`mana_cost: string` on both `Card` and `CardSummary`, from the
 * schemas' NULL-coercing validators). All three spellings are still handled, because this is an
 * exported function whose argument type is `string | null | undefined` for callers the wire does
 * not constrain. `ManaCost.tsx`'s `cost` prop takes the same posture.
 */
export const parseManaCost = (cost: string | null | undefined): ManaToken[] => {
  if (cost === undefined || cost === null || cost === '') return []

  const tokens: ManaToken[] = []
  let index = 0

  while (index < cost.length) {
    if (cost[index] === '{') {
      const close = cost.indexOf('}', index)
      // An UNCLOSED brace is not a symbol and not an error: the rest of the string becomes text,
      // which renders visibly. Returning early here would drop it.
      if (close === -1) {
        tokens.push({ kind: 'text', raw: cost.slice(index) })
        break
      }
      tokens.push(classify(cost.slice(index, close + 1), cost.slice(index + 1, close)))
      index = close + 1
      continue
    }
    // Everything up to the next brace, in ONE token — so ` // ` arrives whole rather than as a
    // separator flanked by two anonymous spaces.
    const next = cost.indexOf('{', index)
    const end = next === -1 ? cost.length : next
    tokens.push({ kind: 'text', raw: cost.slice(index, end) })
    index = end
  }

  return tokens
}

/**
 * What the pip's glyph slot SHOWS for a recognised symbol.
 *
 * THE PHYREXIAN MARKER IS A PLAIN LETTER `P`, IN THE APP'S OWN TYPEFACE. Reproducing the
 * Phyrexian Φ — or a tap symbol, or a set symbol — inside the pip is the same trade-dress
 * imitation UX-DR7 bans by name, arrived at by another route: "no symbol lookalikes" is not
 * only a claim about the pip's outline. The glyph slot is the single answer to generic counts,
 * `{X}`, Phyrexian and (via `unknown`) everything else, which is what keeps that ban cheap.
 */
export const displayGlyph = (token: ManaSymbolToken): string | null => {
  if (!token.phyrexian) return token.glyph
  return token.glyph === null ? 'P' : `${token.glyph}P`
}

const COLOUR_NAMES: Record<ManaColour, string> = {
  w: 'white',
  u: 'blue',
  b: 'black',
  r: 'red',
  g: 'green',
  c: 'colorless',
}

/** `{2}` -> "2 generic"; `{X}` -> "X". A bare count means nothing spoken aloud. */
const describeGlyph = (glyph: string): string => (DIGITS.test(glyph) ? `${glyph} generic` : glyph)

const describeSymbol = (token: ManaSymbolToken): string => {
  const colours = token.colours.map((colour) => COLOUR_NAMES[colour]).join(' or ')
  const glyph = token.glyph === null ? '' : describeGlyph(token.glyph)

  let body = colours
  if (glyph !== '' && colours !== '') body = `${glyph} or ${colours}`
  else if (glyph !== '') body = glyph

  return token.phyrexian ? `Phyrexian ${body}` : body
}

/**
 * The cost as a spoken sentence — "2 generic, white or blue".
 *
 * WHY THIS EXISTS AT ALL: a pip's entire meaning is its FILL COLOUR, and "colour is never the
 * sole carrier" is already a requirement in this same design contract (UX-DR18, for the
 * colour-distribution bar). `ManaCost` puts this string on a `role="img"` wrapper, because
 * an `aria-label` on a bare `<span>` is name-PROHIBITED on `role="generic"` and screen readers
 * are permitted to ignore it — several do.
 *
 * UNKNOWN SYMBOLS READ AS THEIR RAW TEXT (`{HW}` -> "HW"), which is honest rather than silent:
 * the same rule the pips follow, in words.
 *
 * SEPARATORS ARE SPOKEN, NOT PUNCTUATED. A text token joins with a SPACE on both sides rather
 * than the list comma, so `{2}{B} // {B}` reads "2 generic, black // black" instead of the
 * "black, //, black" a naive join produces.
 */
export const describeManaCost = (tokens: ManaToken[]): string => {
  let name = ''
  let previousWasText = false

  for (const token of tokens) {
    let piece = ''
    if (token.kind === 'symbol') piece = describeSymbol(token)
    else if (token.kind === 'unknown') piece = token.glyph
    else piece = token.raw.trim()

    // Whitespace between symbols carries no meaning and is not spoken. It is still a TOKEN —
    // the scanner never drops it — but a name is a sentence, not a transcript.
    if (piece === '') continue

    const isText = token.kind === 'text'
    if (name === '') name = piece
    else if (isText || previousWasText) name = `${name} ${piece}`
    else name = `${name}, ${piece}`
    previousWasText = isText
  }

  return name
}
