import { MANA_COLOUR_ORDER, type ManaColour } from '../ManaCost/parse'
import './ManaPip.css'

/**
 * ManaPip — one mana symbol, drawn as a plain filled circle (story c2-8, UX-DR13, UX-DR7).
 *
 * PRESENTATION-ONLY (AC 18): no state, no hook of any kind, no fetch, no store, no event
 * handler, no ref. Its entire contract is "fill a circle with these colours and put this text
 * in it", and `ui/tests/shell.test.ts` asserts that with an exhaustive import list.
 *
 * ==== THE TWO BRAND HARD RULES IT IMPLEMENTS (UX-DR7) ====================================
 * 1. IT IS DELIBERATELY NOT A MANA-SYMBOL SHAPE. No border, no inner ring, no drawn glyph, no
 *    set or planeswalker likeness — and, the member that is easy to miss, NO PHYREXIAN Φ. The
 *    marker for a Phyrexian symbol is a plain letter `P` in the app's own typeface, because
 *    reproducing the Φ inside the circle is the same trade-dress imitation by another route.
 *    That decision lives in `displayGlyph` beside the parser, so the pip stays dumb.
 * 2. THE `--mana-*` TOKENS ARE DATA INK. This is their FIRST consumer in the repository —
 *    measured: `git grep -- '--mana-'` over ui/ returned seven hits at the baseline commit, all
 *    of them the declarations in tokens.css — so UX-DR7's "never a button, border, background
 *    or an unstacked curve bar" had been enforced by nothing for four stories. ManaPip.css is
 *    the first entry on the allowlist in `ui/tests/token-usage.test.ts`; c4-8's stacked curve
 *    segments and c4-9's colour bar join it in the open, in their own stories.
 *
 * ==== ONE CLASS PER COLOUR, NEVER A BUILT TOKEN NAME (AC 12) =============================
 * The composition reference writes `'var(--mana-' + color + ')'` into an inline style. Three
 * things are wrong with that and only one of them is the lint error: a runtime-built token name
 * is INVISIBLE to `findUnknownTokenReferences`, so a bad colour renders a transparent circle
 * that no test can see. The indirection a component author would reach for instead —
 * `.mana-pip-w { --pip: var(--mana-w) }` — is a GUARD failure, not a lint one (only tokens.css
 * may declare a custom property). So each colour and each hybrid pair is its own class naming
 * its own token directly, and `ui/tests/token-usage.test.ts` proves all 21 of them exist.
 *
 * DECORATIVE BY DEFAULT (Q4). A pip alone carries no accessible name: `ManaCost` labels the
 * whole cost on a `role="img"` wrapper, and a labelled pip inside it would double-announce. It
 * is opt-IN because the flooding UX-DR45 warns about is the default failure.
 *
 * ⚠️ THIS COMMENT USED TO NAME c4-9's LEGEND AS THE `label` PROP'S CASE, AND c4-9 SHIPPED IT
 * DECORATIVE. The correction is kept rather than deleted, because the reasoning was right and
 * the conclusion was inverted by it: a legend entry puts a pip beside its own text count, and
 * that entry already reads the colour, the count and the percentage as words — so a labelled pip
 * there is precisely the doubled announcement this sentence warns about. UX-DR18 makes the
 * legend the accessible data path, and it does that through TEXT.
 *
 * So the prop has NO CALLER in Phase 1, and that is the opt-in defaulting correctly rather than
 * dead code: the case it exists for is a pip drawn with no text beside it, which nothing has
 * needed yet. `ManaPip.test.tsx:78` remains its only witness, and it is titled for c4-9's legend
 * — a name that is now historical rather than predictive.
 *
 * APPEARANCE IS NOT DEV-VERIFIED IN THIS STORY (AC 21). Nothing imports this component yet and
 * jsdom applies no stylesheet, so every claim about the circle, the fill and the split gradient
 * is read as CSS SOURCE by the guards or checked by eye at the first consuming story — c4-3's
 * card placeholders, c4-7's deck row, c4-9's colour legend.
 */

export interface ManaPipProps {
  /**
   * One or two fill colours. EMPTY is the generic case (`{2}`, `{X}`) and fills colourless —
   * never nothing, because an unfilled circle is an invisible one.
   */
  colours?: ManaColour[]
  /**
   * The text in the glyph slot: a generic count, `X`, the Phyrexian `P`, or an unrecognised
   * symbol's own text. `null` for a plain colour pip, which shows no text at all.
   */
  glyph?: string | null
  /**
   * An accessible name. OMITTED means decorative (`aria-hidden`), which is what a pip inside a
   * labelled `ManaCost` must be. Supplying one makes the pip a `role="img"` — an `aria-label`
   * on a bare `<span>` is name-PROHIBITED on `role="generic"` and screen readers may ignore it.
   */
  label?: string
}

/**
 * The class suffix for a set of colours, canonicalised into WUBRG order so `{G/W}` and a
 * hypothetical `{W/G}` land on the same class rather than needing thirty of them.
 *
 * DERIVED FROM `MANA_COLOUR_ORDER` BY FILTERING, which is what makes the fallback safe: any
 * one- or two-length result is guaranteed to be one of the 21 classes ManaPip.css declares, so
 * no lookup table can drift out of step with the stylesheet. Everything else — no colours at
 * all, or more than a two-stop gradient can express — falls to `c`, a real token (AC 12).
 */
const colourKey = (colours: ManaColour[]): string => {
  const ordered = MANA_COLOUR_ORDER.filter((colour) => colours.includes(colour))
  return ordered.length === 1 || ordered.length === 2 ? ordered.join('') : 'c'
}

export function ManaPip({ colours = [], glyph = null, label }: ManaPipProps) {
  // An empty OR whitespace-only label counts as absent: an empty accessible name on a
  // `role="img"` is an element that announces itself and then says nothing, which is worse than
  // being skipped — and `label=" "` is the same nothing wearing a space (review 2026-07-29).
  const decorative = label === undefined || label.trim() === ''

  return (
    <span
      className={`mana-pip mana-pip-${colourKey(colours)}`}
      role={decorative ? undefined : 'img'}
      aria-label={decorative ? undefined : label}
      aria-hidden={decorative ? true : undefined}
    >
      {glyph}
    </span>
  )
}
