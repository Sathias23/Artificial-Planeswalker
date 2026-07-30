import { ManaPip } from '../ManaPip/ManaPip'
import './ManaCost.css'
import { describeManaCost, displayGlyph, parseManaCost } from './parse'

/**
 * ManaCost — a whole Scryfall cost string, rendered symbol by symbol (story c2-8, UX-DR13).
 *
 * PRESENTATION-ONLY (AC 18): no state, no hook of any kind, no fetch, no store, no event
 * handler, no ref. It parses a string and arranges pips.
 *
 * ==== IT NEVER SILENTLY DROPS ANYTHING (AC 2, 3, 7) =====================================
 * That property is inherited from `./parse`, not implemented here, and the distinction is the
 * whole design: the scanner is TOTAL, so this component's job is only to give each of the three
 * token kinds somewhere to go. A recognised symbol becomes a pip; an unrecognised one becomes a
 * pip showing its own text; anything outside braces — which in the real data is only ` // ` and
 * whitespace — becomes inline text. There is no `else` branch that discards, because there is
 * nothing left for it to discard.
 *
 * The ` // ` separator matters more than it looks: 338 rows in the shipped card database carry
 * one, up to FIVE parts deep (`{X}{W} // {2}{R} // {2}{U} // {3}{B} // {1}{G}`), and a
 * tokeniser written as `cost.match(/\{[^}]*\}/g)` renders all five as one run-on cost.
 *
 * ==== HOW IT IS ANNOUNCED (AC 15, Q4) ===================================================
 * `role="img"` with an `aria-label` on THIS wrapper, its pips left decorative inside it. That
 * is required rather than stylistic: an `aria-label` on a bare `<span>` is name-PROHIBITED on
 * `role="generic"`, and screen readers are permitted to ignore it — several do. A `role="img"`
 * element's children are presentational, so nothing double-announces, and ManaPip is decorative
 * by default anyway.
 *
 * The name is built by `describeManaCost` beside the parser and unit-tested with it:
 * `{2}{W/U}` reads "2 generic, white or blue". This is UX-DR18's already-ruled "colour is never
 * the sole carrier", applied to the component that is nothing but colour — and it is the ruling
 * c4-8's curve and c4-9's colour bar reuse rather than each inventing one.
 *
 * APPEARANCE IS NOT DEV-VERIFIED IN THIS STORY (AC 21): nothing imports this component yet and
 * jsdom applies no stylesheet. The look is checked at c4-3 / c4-7 / c4-9.
 */

export interface ManaCostProps {
  /**
   * A Scryfall cost string. `undefined`, `null`, `''` and a whitespace-only string all render
   * NOTHING, without error (AC 4) — a land's absent cost arrives as `''` from this repo's own
   * data (5,943 rows; `mana_cost` is never NULL), but the wire type c3-2 generates may still be
   * nullable, so all four spellings are handled identically rather than one being guessed at.
   */
  cost?: string | null
}

export function ManaCost({ cost }: ManaCostProps) {
  // THE EMPTY CHECK IS A *STRING* QUESTION, which is why `filled()` is not reused here: that
  // helper answers "does this ReactNode render anything", and a whitespace-only cost is a
  // perfectly filled string that must still render nothing. Checked BEFORE parsing, so the
  // whitespace token the total scanner correctly produces never reaches the DOM as an empty
  // wrapper with an accessible name attached to it. The `typeof` spelling also keeps the
  // totality contract against an UNTYPED wire value — a number reaching `.trim()` would throw,
  // and a blank screen is the one failure worse than a wrong cost (review 2026-07-29).
  if (typeof cost !== 'string' || cost.trim() === '') return null

  const tokens = parseManaCost(cost)

  return (
    <span className="mana-cost" role="img" aria-label={describeManaCost(tokens)}>
      {tokens.map((token, index) => {
        // The INDEX is the key, deliberately: a cost is a fixed, unkeyed sequence rendered from
        // one string, `{B}{B}{B}` is three legitimately identical siblings, and there is no
        // reorder, insert or removal for a stable identity to protect against.
        if (token.kind === 'text') {
          return (
            <span className="mana-cost-text" key={index}>
              {token.raw}
            </span>
          )
        }
        const colours = token.kind === 'symbol' ? token.colours : []
        const glyph = token.kind === 'symbol' ? displayGlyph(token) : token.glyph
        return <ManaPip key={index} colours={colours} glyph={glyph} />
      })}
    </span>
  )
}
