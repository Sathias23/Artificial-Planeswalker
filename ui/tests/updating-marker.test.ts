/**
 * The refetch header shimmer and its reduced-motion swap, read from CSS SOURCE (story c7-4,
 * UX-DR35, UX-DR42).
 *
 * READ THE SOURCE, NEVER A RENDERED DOM — the rule `tests/shell.test.ts` and the reduced-motion
 * block in `tests/token-usage.test.ts` both state about themselves, and it binds harder here:
 * jsdom does not evaluate media queries into computed style, so a test that mounted the shell
 * under a stubbed `matchMedia` and read the span's `display` would report the UNREDUCED value
 * and pass for the wrong reason. What the marker WIRES (the attribute, the span, the censuses)
 * is `AppShell.test.tsx`'s, over a real render; what it LOOKS like at each motion setting is
 * only decidable from the stylesheets, which is this file's whole job:
 *
 *   1. The shimmer is a NON-ANIMATED veil — an opacity dim eased through a duration token —
 *      with nothing that loops, no `@keyframes` at all (whose rules the reduced-motion reader
 *      cannot neutralise, `AgentView.css`'s recorded reason) and no transform (the enumerated
 *      shipped-motion pin in token-usage.test.ts must not move).
 *   2. The static "Updating…" line is hidden at EVERY setting by default, and the only rule
 *      that shows it lives in `tokens.css`'s reduced-motion block — the single registration
 *      point every motion fallback uses (Decide-once #3) — beside the rule that neutralises
 *      the veil it replaces.
 *
 * WHAT THIS CANNOT SEE: whether 0.55 reads as "muted, still legible" on real pixels, and how
 * the swap behaves mid-flight when the OS setting changes — both are the epic manual-testing
 * checklist's, and the token/duration VALUE legality is stylelint's, not re-derived here.
 */

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))
const sourceOf = (repoRelative: string) => readFileSync(join(uiRoot, repoRelative), 'utf8')

const SHELL_CSS = 'src/components/AppShell/AppShell.css'
const TOKENS_CSS = 'src/styles/tokens.css'

const stripComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, '')

/**
 * Innermost `selector { body }` pairs — the same minimal reader shape as `shell.test.ts`'s,
 * safe for the same recorded reason: native CSS nesting is banned in shipped stylesheets by a
 * token-usage guard, so no declaration can hide in a nesting parent this shape would miss.
 */
const blocksIn = (css: string): { selector: string; body: string }[] =>
  [...stripComments(css).matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({
    selector: m[1].trim(),
    body: m[2],
  }))

const blockFor = (css: string, selector: string) =>
  blocksIn(css).find((block) => block.selector === selector)

/**
 * The reduced-motion block's body, brace-aware — `token-usage.test.ts`'s extractor, re-derived
 * rather than imported because that file deliberately exports nothing (a guard that exported
 * its reader would invite tests that assert the reader instead of the stylesheet).
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

const shellCss = sourceOf(SHELL_CSS)
const tokensCss = sourceOf(TOKENS_CSS)
const reduced = reducedMotionBlockOf(stripComments(tokensCss))

describe('the shimmer is a non-animated veil, expressed only through tokens (c7-4)', () => {
  it('is reading real stylesheets — the non-vacuity anchor', () => {
    // An empty read (wrong cwd, a rename) would let every assertion below pass by finding
    // nothing; the extractor is additionally proven able to FAIL, so a deleted media block
    // cannot satisfy the reduced-motion tests vacuously.
    expect(blocksIn(shellCss).length).toBeGreaterThan(5)
    expect(reduced, 'no reduced-motion block in tokens.css').not.toBeNull()
    expect(reducedMotionBlockOf('.no-media-here { display: none; }')).toBeNull()
  })

  it('dims the identity block while data-updating is set, easing over a duration token', () => {
    const veil = blockFor(shellCss, ".app-shell-identity[data-updating='true']")
    expect(veil, 'no veil rule for the updating attribute in AppShell.css').toBeDefined()
    expect(veil!.body).toMatch(/opacity\s*:\s*0?\.\d+/)

    // The transition lives on the block AT REST (so the dim eases both in and out), and its
    // duration is a --motion-* token — the mechanism the reduced-motion zeroing reaches.
    const identity = blockFor(shellCss, '.app-shell-identity')
    expect(identity!.body).toMatch(/transition\s*:\s*opacity\s+var\(--motion-glide\)/)
  })

  it('ships no @keyframes, no animation and no transform anywhere in the shell stylesheet', () => {
    // The three spellings a "shimmer" most naturally reaches for, and every one is refused by
    // construction: keyframes rules cannot be neutralised by the reduced-motion block's own
    // reader, `animation` invites the loop stylelint bans, and a transform would move the
    // 5-entry enumerated pin in token-usage.test.ts.
    const bare = stripComments(shellCss)
    expect(bare).not.toMatch(/@keyframes/)
    expect(bare).not.toMatch(/\banimation\b/)
    // Lookbehind, not `\b`: `text-transform: uppercase` is the marker's own casing companion,
    // and the hyphen before `transform` IS a word boundary — the bare `\b` spelling failed on
    // this very stylesheet's first run.
    expect(bare).not.toMatch(/(?<![\w-])transform\s*:/)
  })
})

describe('the static "Updating…" text replaces the veil under reduced motion (c7-4, AC 2)', () => {
  it('is hidden at every setting by default, with the micro companions declared beside it', () => {
    const text = blockFor(shellCss, '.app-shell-updating')
    expect(text, 'no .app-shell-updating rule in AppShell.css').toBeDefined()
    expect(text!.body).toMatch(/display\s*:\s*none/)
    // `font: var(--type-micro)` drops tracking and casing on the floor — the shorthand carries
    // neither — so the two companions and the AC's colour tier are asserted as declarations.
    expect(text!.body).toMatch(/font\s*:\s*var\(--type-micro\)/)
    expect(text!.body).toMatch(/letter-spacing\s*:\s*var\(--tracking-micro\)/)
    expect(text!.body).toMatch(/text-transform\s*:\s*uppercase/)
    expect(text!.body).toMatch(/color\s*:\s*var\(--text-secondary\)/)
  })

  it('swaps veil for text INSIDE the tokens.css media block, and nowhere else', () => {
    // Both halves of the UX-DR42 registration, in the single registration point. The veil's
    // neutralisation must carry `!important` (tokens.css is @imported first and the two
    // selectors tie at (0,2,0) — c4-4's measured cascade no-op, refused here the way
    // token-usage refuses unimportant transform registrations); the show rule outranks the
    // component's `display: none` on specificity alone.
    expect(reduced).toMatch(
      /\.app-shell-identity\[data-updating='true'\]\s*\{\s*opacity\s*:\s*1\s*!important\s*;\s*\}/,
    )
    expect(reduced).toMatch(
      /\.app-shell-identity\[data-updating='true'\]\s+\.app-shell-updating\s*\{\s*display\s*:\s*block\s*;\s*\}/,
    )

    // …and ONLY there — a TOTAL census, not a first-match read: EVERY block in the component
    // stylesheet whose selector names the marker is collected, and across all of them the only
    // `display` declared is the `none` above. A first-block read (`blockFor`) would let a later
    // duplicate `.app-shell-updating { display: block }` reveal the text unconditionally and
    // still pass. tokens.css then names the marker nowhere outside its media block — the
    // "reduced-motion handled ONLY in the tokens block" constraint as a check, not a comment.
    const markerBlocks = blocksIn(shellCss).filter((block) =>
      block.selector.includes('.app-shell-updating'),
    )
    expect(markerBlocks.length).toBeGreaterThan(0)
    const displays = markerBlocks.flatMap((block) =>
      [...block.body.matchAll(/display\s*:\s*([a-z-]+)/g)].map((m) => m[1]),
    )
    expect(displays).toEqual(['none'])
    const outsideMedia = stripComments(tokensCss).replace(reduced!, '')
    expect(outsideMedia).not.toContain('app-shell-updating')
  })
})
