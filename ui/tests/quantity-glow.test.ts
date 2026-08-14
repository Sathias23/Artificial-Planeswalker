/**
 * The quantity badge's one-shot accent glow and its reduced-motion omission, read from CSS
 * SOURCE (story c7-5, UX-DR16, UX-DR42).
 *
 * READ THE SOURCE, NEVER A RENDERED DOM — `updating-marker.test.ts`'s rule, which is this
 * file's template, and it binds identically: jsdom does not evaluate media queries into
 * computed style, so a test that mounted a tile under a stubbed `matchMedia` and read the
 * badge's `box-shadow` would report the UNREDUCED value and pass for the wrong reason. What the
 * flash WIRES (the `data-flashed` attribute's one-frame lifecycle) is `CardTile.test.tsx`'s,
 * over a real render; what it LOOKS like at each motion setting is only decidable from the
 * stylesheets, which is this file's whole job:
 *
 *   1. The glow is instant-on, fade-off: the flashed rule paints `var(--glow)` with
 *      `transition: none`, and the badge's BASE rule carries the token'd fade-out — no
 *      `@keyframes` (whose rules the reduced-motion reader cannot neutralise), no `animation`
 *      (which invites the loop stylelint bans), no transform (the enumerated shipped-motion pin
 *      in token-usage.test.ts must not move).
 *   2. Under reduced motion the glow is OMITTED, not merely instant — an instant glow that
 *      never fades is a persistent glow — by an explicit `box-shadow: none !important`
 *      registration inside `tokens.css`'s media block, the single registration point
 *      (Decide-once #3), and nowhere else.
 *   3. The curve bars' "instant jump" AC is a CITATION, not a build: `ManaCurve.css` already
 *      expresses the bar entirely through `--motion-glide`, so the four-token zeroing
 *      neutralises it mechanically. Asserted here so the AC's mechanism cannot silently vanish
 *      while this story's record claims it.
 *
 * WHAT THIS CANNOT SEE: whether the glow reads as garnish rather than signal on real pixels —
 * the epic manual-testing checklist's — and the token/duration VALUE legality, which is
 * stylelint's, not re-derived here.
 */

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))
const sourceOf = (repoRelative: string) => readFileSync(join(uiRoot, repoRelative), 'utf8')

const BADGE_CSS = 'src/containers/CardTile/QuantityBadge.css'
const TOKENS_CSS = 'src/styles/tokens.css'
const CURVE_CSS = 'src/containers/ManaCurve/ManaCurve.css'

const stripComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, '')

/**
 * Innermost `selector { body }` pairs — `updating-marker.test.ts`'s minimal reader, safe for the
 * same recorded reason: native CSS nesting is banned in shipped stylesheets by a token-usage
 * guard, so no declaration can hide in a nesting parent this shape would miss.
 */
const blocksIn = (css: string): { selector: string; body: string }[] =>
  [...stripComments(css).matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({
    selector: m[1].trim(),
    body: m[2],
  }))

const blockFor = (css: string, selector: string) =>
  blocksIn(css).find((block) => block.selector === selector)

/**
 * The reduced-motion block's body, brace-aware — re-derived rather than imported, because
 * `token-usage.test.ts` deliberately exports nothing (a guard that exported its reader would
 * invite tests that assert the reader instead of the stylesheet).
 */
const reducedMotionBlockOf = (css: string): string | null => {
  const opener = /@media\s*\(\s*prefers-reduced-motion:\s*reduce\s*\)\s*\{/.exec(css)
  if (!opener) return null
  const start = opener.index + opener[0].length
  let depth = 1
  for (let i = start; i < css.length; i++) {
    if (css[i] === '{') depth++
    else if (css[i] === '}' && --depth === 0) return css.slice(start, i)
  }
  return null
}

const badgeCss = sourceOf(BADGE_CSS)
const tokensCss = sourceOf(TOKENS_CSS)
const reduced = reducedMotionBlockOf(stripComments(tokensCss))

describe('the glow is instant-on, fade-off, expressed only through tokens (c7-5)', () => {
  it('is reading real stylesheets — the non-vacuity anchor', () => {
    // An empty read (wrong cwd, a rename) would let every assertion below pass by finding
    // nothing; the extractor is additionally proven able to FAIL, so a deleted media block
    // cannot satisfy the reduced-motion tests vacuously.
    expect(blocksIn(badgeCss).length).toBeGreaterThan(1)
    expect(reduced, 'no reduced-motion block in tokens.css').not.toBeNull()
    expect(reducedMotionBlockOf('.no-media-here { display: none; }')).toBeNull()
  })

  it('carries the fade-out on the badge AT REST, through the motion tokens', () => {
    // The base rule owns the DEPARTURE: when `data-flashed` drops, box-shadow eases from
    // `var(--glow)` back to nothing over `--motion-glide` — which is also what makes the fade
    // MECHANICAL under reduced motion (a zeroed duration), leaving only the omission below to
    // register explicitly.
    const base = blockFor(badgeCss, '.card-tile-quantity')
    expect(base, 'no .card-tile-quantity rule in QuantityBadge.css').toBeDefined()
    expect(base!.body).toMatch(
      /transition\s*:\s*box-shadow\s+var\(--motion-glide\)\s+var\(--ease-glide\)/,
    )
  })

  it('paints the flash instantly — var(--glow) with the transition suspended', () => {
    // `transition: none` is load-bearing: a fade-IN reversed after one rAF frame would never
    // reach full glow. And `var(--glow)` is the ONLY legal inline glow (stylelint's box-shadow
    // allowed-list) — asserted as the exact value so a composite or a literal cannot creep in.
    const flashed = blockFor(badgeCss, ".card-tile-quantity[data-flashed='true']")
    expect(flashed, "no [data-flashed='true'] rule in QuantityBadge.css").toBeDefined()
    expect(flashed!.body).toMatch(/box-shadow\s*:\s*var\(--glow\)\s*;/)
    expect(flashed!.body).toMatch(/transition\s*:\s*none\s*;/)
  })

  it('ships no @keyframes, no animation and no transform anywhere in the badge stylesheet', () => {
    // The three spellings a "flash" most naturally reaches for, refused by construction:
    // keyframes rules cannot be neutralised by the reduced-motion block's own reader,
    // `animation` invites the loop stylelint bans, and a transform would move the 5-entry
    // enumerated pin in token-usage.test.ts.
    const bare = stripComments(badgeCss)
    expect(bare).not.toMatch(/@keyframes/)
    expect(bare).not.toMatch(/\banimation\b/)
    // Lookbehind, not `\b` — `updating-marker.test.ts`'s measured spelling: a hyphen before
    // `transform` IS a word boundary, so the bare `\b` form false-fails on properties like
    // `text-transform`.
    expect(bare).not.toMatch(/(?<![\w-])transform\s*:/)
  })

  it('omits the glow under reduced motion — inside the tokens media block, and only there', () => {
    // The registration half of UX-DR42's "glow omitted" row, in the single registration point.
    // RAW `!important`, because tokens.css is @imported first and the two selectors tie at
    // (0,3,0) — without it the override would parse cleanly and do nothing (the c4-4 measured
    // cascade no-op, refused here the way token-usage refuses unimportant transform
    // registrations).
    expect(reduced).toMatch(
      /\.card-tile-quantity\[data-flashed='true'\]\s*\{\s*box-shadow\s*:\s*none\s*!important\s*;\s*\}/,
    )

    // …and ONLY there: tokens.css names the badge nowhere outside its media block — the
    // "reduced-motion rules ONLY in the tokens block" constraint as a check, not a comment.
    const outsideMedia = stripComments(tokensCss).replace(reduced!, '')
    expect(outsideMedia).not.toContain('card-tile-quantity')
  })

  it('leaves the curve bars on their existing mechanical zeroing — the citation half (AC 5)', () => {
    // The curve-bar "instant jump" is CITED, not built: `ManaCurve.css` expresses the bar's
    // height entirely through `--motion-glide`, so the media block's duration zeroing already
    // neutralises it with no registration owed. This assertion is what keeps the c7-5 AC's
    // mechanism from silently vanishing while the story record still claims it.
    expect(sourceOf(CURVE_CSS)).toMatch(/transition\s*:\s*height\s+var\(--motion-glide\)/)
  })
})
