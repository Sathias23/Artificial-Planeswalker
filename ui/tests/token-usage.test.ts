/**
 * The constraints stylelint cannot express, enforced anyway.
 *
 * `.stylelintrc.json` bans literals — a hex colour, an rgb() call, a hand-rolled shadow,
 * radius or spacing value. Three things it cannot see are just as load-bearing:
 *
 *   AC 10 — `--accent-dim` on `--surface-overlay` is 2.70:1 and FAILS the 3:1 non-text
 *           contrast floor (UX-DR6). No stock rule relates two declarations to each other.
 *   AC 2  — no stylesheet outside src/styles may DECLARE a custom property. Tokens declared
 *           in a component are tokens the four alternate themes cannot reach, which quietly
 *           un-does the whole reason the layer exists.
 *   (+)   — a `var(--typo)` that names no real token renders as nothing at all.
 *           `no-unknown-custom-properties` is the obvious rule for this and it DOES NOT WORK
 *           here: measured at the baseline commit, it reports "Unknown custom property" for
 *           `var(--shadow-rest)`, `var(--radius-lg)` and `var(--text-primary)` in a
 *           component stylesheet, because it is FILE-SCOPED and the tokens live in another
 *           file. Enabling it would flag every legitimate reference in the codebase. So the
 *           cross-file resolution it lacks is done here instead.
 *
 * Each guard is proven FIRING and NOT FIRING (the standing non-vacuity pairing agreement):
 * the real tree is scanned and must be clean, and a fixture built to break each rule must be
 * caught. A guard only ever run against clean input cannot tell "nothing is wrong" from
 * "nothing was read".
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { SURFACE_RAMP } from '../src/styles/surfaces.ts'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))
const fixture = (rel: string) => fileURLToPath(new URL(`fixtures/${rel}`, import.meta.url))

/** The one file allowed to declare tokens. Every other stylesheet only consumes them. */
const TOKEN_FILE = 'src/styles/tokens.css'

// git is the file authority, not readdir: it cannot see node_modules, dist or coverage, and
// a stray stylesheet is caught the moment it is committed — which is when CI sees it.
// `tests/fixtures/` is excluded for the same reason `npm run lint` excludes it: those files
// exist to be broken, and are fed to these guards explicitly below.
const shippedStylesheets = execFileSync('git', ['ls-files', '*.css'], {
  cwd: uiRoot,
  encoding: 'utf8',
})
  .split('\n')
  .filter(Boolean)
  .filter((f) => !f.startsWith('tests/fixtures/'))

const sourceOf = (repoRelative: string) => readFileSync(join(uiRoot, repoRelative), 'utf8')

// ---------------------------------------------------------------------------------------
// A minimal CSS reader — enough to see rule blocks, and honest about being no more than that
// ---------------------------------------------------------------------------------------

interface Block {
  file: string
  selector: string
  body: string
}

const stripComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, '')

/**
 * Every innermost rule block. An `@media` wrapper contributes its inner block rather than
 * itself, which is what these guards want: contrast and declaration rules apply to the
 * block that actually carries declarations.
 */
const blocksIn = (file: string, css: string): Block[] => {
  const blocks: Block[] = []
  for (const match of stripComments(css).matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    blocks.push({
      file,
      selector: match[1].trim().replace(/\s+/g, ' '),
      body: match[2],
    })
  }
  return blocks
}

const declaredTokensIn = (body: string): string[] =>
  [...body.matchAll(/(^|;)\s*(--[a-z0-9-]+)\s*:/gi)].map((m) => m[2])

const referencedTokensIn = (text: string): string[] =>
  [...stripComments(text).matchAll(/var\(\s*(--[a-z0-9-]+)/gi)].map((m) => m[1])

// ---------------------------------------------------------------------------------------
// The guards
// ---------------------------------------------------------------------------------------

/** UX-DR6: `--accent-dim` is 2.70:1 on `--surface-overlay`. The substitute is `--accent`. */
const findAccentDimOnOverlay = (blocks: Block[]): string[] =>
  blocks
    .filter(
      (b) =>
        referencedTokensIn(b.body).includes('--accent-dim') &&
        referencedTokensIn(b.body).includes('--surface-overlay'),
    )
    .map(
      (b) =>
        `${b.file} — \`${b.selector}\` puts --accent-dim on --surface-overlay (2.70:1, below the ` +
        `3:1 non-text floor, UX-DR6). Use --accent instead (5.5:1); it is the named substitute.`,
    )

/** AC 2: only the token file declares tokens; everything else consumes them. */
const findTokenDeclarationsOutsideTokenFile = (blocks: Block[]): string[] =>
  blocks
    .filter((b) => b.file !== TOKEN_FILE)
    .flatMap((b) =>
      declaredTokensIn(b.body).map(
        (name) =>
          `${b.file} — \`${b.selector}\` declares ${name}. Only ${TOKEN_FILE} declares tokens; a ` +
          `token declared in a component is one the alternate themes cannot restyle. Add it there.`,
      ),
    )

/** Declarations of one block, as `[property, value]`, with `!important` dropped. */
const declarationsIn = (body: string): [string, string][] =>
  body
    .split(';')
    .map((decl) => (decl.indexOf(':') === -1 ? null : decl))
    .filter((decl): decl is string => decl !== null)
    .map((decl) => {
      const colon = decl.indexOf(':')
      return [
        decl.slice(0, colon).trim().toLowerCase(),
        decl
          .slice(colon + 1)
          .replace(/!important\s*$/i, '')
          .trim()
          .replace(/\s+/g, ' '),
      ] as [string, string]
    })

/** `cubic-bezier(0.4, 0, 0.2, 1)` -> `cubic-bezier()`, repeatedly, so nesting collapses too. */
const withoutFunctionArguments = (value: string): string => {
  let previous = value
  for (;;) {
    const next = previous.replace(/\([^()]*\)/g, '()')
    if (next === previous) return next
    previous = next
  }
}

const LOOP_ADVICE =
  'Nothing pulses or loops, at any setting (DESIGN.md and EXPERIENCE.md both say so, four ' +
  'times between them). Run the animation exactly once, or carry the signal with text.'

/**
 * AC 12, and deliberately MORE precise than the stylelint rules that share its job.
 *
 * `.stylelintrc.json` bans the keyword spellings (`infinite` in a shorthand,
 * `animation-iteration-count` other than 1, alternate/alternate-reverse direction) and does
 * it on every `npm run lint`, over every stylesheet, which is where that layer earns its
 * place. What it CANNOT express is an iteration count written into the `animation`
 * shorthand: `animation: pulse 2s 3` loops three times, and a value-level regex cannot tell
 * that bare `3` from the bare numbers inside `cubic-bezier(0.4, 0, 0.2, 1)` in the same
 * value — banning bare numbers there would false-positive on a legal easing.
 *
 * This guard strips parenthesised groups first, so it can tell them apart. Two layers, each
 * honest about its reach.
 */
const findLoopingAnimation = (blocks: Block[]): string[] => {
  const findings: string[] = []
  const allowedCount = /^(1|initial|inherit|revert|revert-layer|unset)$/i

  for (const block of blocks) {
    for (const [property, value] of declarationsIn(block.body)) {
      const where = `${block.file} — \`${block.selector}\``

      if (property === 'animation-iteration-count' && !allowedCount.test(value)) {
        findings.push(`${where}: animation-iteration-count is \`${value}\`. ${LOOP_ADVICE}`)
      }
      if (property === 'animation-direction' && /^alternate(-reverse)?$/i.test(value)) {
        findings.push(`${where}: animation-direction is \`${value}\`. ${LOOP_ADVICE}`)
      }
      if (property === 'animation') {
        const bare = withoutFunctionArguments(value)
        if (/(?:^|\s)infinite(?:\s|$)/i.test(bare)) {
          findings.push(`${where}: the animation shorthand says \`infinite\`. ${LOOP_ADVICE}`)
        }
        if (/(?:^|\s)alternate(-reverse)?(?:\s|$)/i.test(bare)) {
          findings.push(`${where}: the animation shorthand alternates. ${LOOP_ADVICE}`)
        }
        // A bare, unitless number in the shorthand IS the iteration count — durations and
        // delays always carry a unit, so there is nothing else it could be.
        const counts = [...bare.matchAll(/(?:^|\s)(\d+(?:\.\d+)?)(?:\s|$)/g)].map((m) => m[1])
        if (counts.some((c) => c !== '1')) {
          findings.push(
            `${where}: the animation shorthand carries an iteration count of ` +
              `\`${counts.filter((c) => c !== '1').join(', ')}\`. ${LOOP_ADVICE}`,
          )
        }
      }
    }
  }
  return findings
}

/** A `var()` naming no real token silently renders nothing. */
const findUnknownTokenReferences = (files: string[], known: Set<string>): string[] =>
  files.flatMap((file) =>
    [...new Set(referencedTokensIn(sourceOf(file)))]
      .filter((name) => !known.has(name))
      .map(
        (name) =>
          `${file} references ${name}, which ${TOKEN_FILE} does not declare — it resolves to ` +
          `nothing at runtime. Fix the name, or add the token to ${TOKEN_FILE}.`,
      ),
  )

const tokenFileSource = sourceOf(TOKEN_FILE)
const declaredTokens = new Set(
  blocksIn(TOKEN_FILE, tokenFileSource).flatMap((b) => declaredTokensIn(b.body)),
)
const shippedBlocks = shippedStylesheets.flatMap((f) => blocksIn(f, sourceOf(f)))

// ---------------------------------------------------------------------------------------

describe('token usage across the shipped stylesheets', () => {
  // THE NON-VACUITY ANCHOR. Every guard below filters these two lists. An empty list — a
  // wrong cwd, a git call resolving another tree, a regex that stopped matching blocks —
  // makes all three guards pass by finding nothing at all, which is exactly the failure
  // mode the c2-3 review found in every guard it looked at.
  it('is reading real stylesheets and real tokens', () => {
    expect(shippedStylesheets).toContain(TOKEN_FILE)
    expect(shippedStylesheets).toContain('src/index.css')
    expect(shippedStylesheets).toContain('src/App.css')
    expect(shippedBlocks.length).toBeGreaterThan(3)
    expect(declaredTokens.size).toBe(64)
  })

  it('never puts --accent-dim on --surface-overlay (AC 10, UX-DR6)', () => {
    expect(findAccentDimOnOverlay(shippedBlocks)).toEqual([])
  })

  it('declares tokens in exactly one file (AC 2)', () => {
    expect(findTokenDeclarationsOutsideTokenFile(shippedBlocks)).toEqual([])
  })

  it('references no token that does not exist', () => {
    expect(findUnknownTokenReferences(shippedStylesheets, declaredTokens)).toEqual([])
  })

  it('never pulses or loops (AC 12)', () => {
    expect(findLoopingAnimation(shippedBlocks)).toEqual([])
  })

  it('keeps the surface ramp in src/styles/surfaces.ts in step with the tokens', () => {
    // AC 9's mechanism reasons about four names. If a token were renamed without updating
    // the ordered data, `stepsExactlyOne` would keep answering confidently about a ramp that
    // no longer exists — and every unit test of it would still pass.
    for (const name of SURFACE_RAMP) {
      expect(
        declaredTokens,
        `surfaces.ts names --${name}, which tokens.css does not declare`,
      ).toContain(`--${name}`)
    }
    const declarationOrder = [...tokenFileSource.matchAll(/^\s*(--surface-[a-z]+):/gm)].map(
      (m) => m[1],
    )
    expect(declarationOrder).toEqual(SURFACE_RAMP.map((n) => `--${n}`))
  })
})

describe('the guards themselves fire (the other half of the pair)', () => {
  const violation = () => {
    const file = 'tests/fixtures/css/token-usage-violation.css'
    return blocksIn(file, readFileSync(fixture('css/token-usage-violation.css'), 'utf8'))
  }

  it('catches --accent-dim on --surface-overlay, and names --accent as the fix', () => {
    const findings = findAccentDimOnOverlay(violation())
    expect(findings).toHaveLength(2)
    // The house rule: a guard's failure message names its fix. A developer who trips this
    // must not have to go and read UX-DR6 to learn what to write instead.
    for (const finding of findings) {
      expect(finding).toContain('Use --accent instead')
      expect(finding).toContain('2.70:1')
    }
    // Order-independent: both offending selectors are reported, not just the first.
    expect(findings.join('\n')).toContain('.suggestion-row')
    expect(findings.join('\n')).toContain('.tier-row-inside-media')
  })

  it('catches a token declared outside the token file', () => {
    const findings = findTokenDeclarationsOutsideTokenFile(violation())
    expect(findings).toHaveLength(2)
    expect(findings.join('\n')).toContain('--local-accent')
    expect(findings.join('\n')).toContain('--swap-row-shadow')
    expect(findings[0]).toContain('Only src/styles/tokens.css declares tokens')
  })

  it('catches a var() that names no token', () => {
    const findings = findUnknownTokenReferences(
      ['tests/fixtures/css/token-usage-violation.css'],
      declaredTokens,
    )
    expect(findings.join('\n')).toContain('--shadow-rst')
    expect(findings.join('\n')).toContain('resolves to nothing at runtime')
  })

  it('catches every spelling of a loop, including the one stylelint cannot see', () => {
    const motion = blocksIn(
      'tests/fixtures/css/motion-violation.css',
      readFileSync(fixture('css/motion-violation.css'), 'utf8'),
    )
    const findings = findLoopingAnimation(motion)
    const joined = findings.join('\n')

    expect(joined).toContain('.loops-forever') // `infinite` in the shorthand
    expect(joined).toContain('.loops-a-few-times') // iteration-count: 3
    expect(joined).toContain('.loops-forever-by-longhand') // iteration-count: infinite
    expect(joined).toContain('.ping-pongs') // direction: alternate
    expect(joined).toContain('.ping-pongs-backwards') // direction: alternate-reverse
    expect(joined).toContain('.ping-pongs-in-shorthand') // alternate inside the shorthand
    expect(joined).toContain('.loops-forever-uppercase') // case is an evasion of its own

    // THE ONE THE LINT RULE MISSES. `animation: pulse 2s 3` loops three times through a bare
    // number; stylelint's value regex cannot separate it from `cubic-bezier(0.4, 0, 0.2, 1)`.
    expect(joined).toContain('.loops-by-numeric-shorthand')
    expect(joined).toContain('iteration count of `3`')

    // Every block in that fixture is a violation, so nothing may be missed silently.
    const flagged = new Set(
      findings.map((f) => f.slice(f.indexOf('`') + 1, f.indexOf('`', f.indexOf('`') + 1))),
    )
    expect(flagged.size).toBe(motion.length)

    for (const finding of findings) {
      expect(finding).toContain('Run the animation exactly once')
    }
  })

  it('does not flag a legal single-run animation, easing numbers and all', () => {
    // The paren-stripping is what makes this pass: a literal cubic-bezier in the shorthand
    // is four bare numbers, and a blunter guard would call `0.4` an iteration count. If this
    // ever fails, c6-5's agent-view bloom is about to have to fight the gate.
    const legal = blocksIn(
      'inline',
      `.bloom { animation: bloom 480ms cubic-bezier(0.4, 0, 0.2, 1) 1; }
       .once { animation: fade var(--motion-glide) var(--ease-out); animation-iteration-count: 1; }`,
    )
    expect(findLoopingAnimation(legal)).toEqual([])
  })

  it('leaves the clean fixture alone under every guard, in the same invocation', () => {
    const clean = blocksIn(
      'tests/fixtures/css/clean.css',
      readFileSync(fixture('css/clean.css'), 'utf8'),
    )
    expect(clean.length).toBeGreaterThan(5)
    expect(findAccentDimOnOverlay(clean)).toEqual([])
    expect(findTokenDeclarationsOutsideTokenFile(clean)).toEqual([])
    expect(findLoopingAnimation(clean)).toEqual([])
  })

  it('does not flag --accent-dim beside a surface that is not overlay', () => {
    // The rule is specific: `--accent-dim` is fine on well, base and panel. A guard that
    // banned the token outright would be a guard c6-7 and c9-1 have to fight.
    const legal = blocksIn(
      'inline',
      '.skip-link { background: var(--surface-panel); border-color: var(--accent-dim); }',
    )
    expect(findAccentDimOnOverlay(legal)).toEqual([])
  })
})

describe('the reduced-motion mechanism (AC 11, AC 13)', () => {
  // READ THE CSS SOURCE, NEVER A RENDERED DOM. jsdom does not implement window.matchMedia by
  // default and getComputedStyle() does not apply media queries, so a test that mounted a
  // component and read a duration would report the UNREDUCED value and pass for the wrong
  // reason — vacuous by construction. AC 13 exists because that trap is the obvious way to
  // write this test.
  const reduced = /@media\s*\(\s*prefers-reduced-motion:\s*reduce\s*\)\s*\{([\s\S]*)\}/.exec(
    tokenFileSource,
  )

  it('has a prefers-reduced-motion block at all', () => {
    expect(reduced, 'no @media (prefers-reduced-motion: reduce) block in tokens.css').not.toBeNull()
  })

  it('zeroes all four duration tokens', () => {
    const body = reduced![1]
    for (const name of ['pulse', 'glide', 'bloom', 'aurora']) {
      expect(body, `--motion-${name} is not neutralised under reduced motion`).toMatch(
        new RegExp(`--motion-${name}\\s*:\\s*0m?s`),
      )
    }
  })

  it('applies to the themed selector, not only :root', () => {
    // Otherwise the fallback silently stops working the moment an alternate theme ships.
    expect(reduced![1]).toContain("[data-theme='voltglass']")
  })

  it('names itself as the registration point later stories extend', () => {
    // AC 11 asks for a mechanism that is the SINGLE place later epics register their own
    // fallbacks. That is a documentation contract as much as a code one, and c4/c6/c7 will
    // only honour it if the file says so where they will be reading.
    expect(tokenFileSource).toContain('REGISTRATION POINT')
    expect(tokenFileSource).toContain('UX-DR42')
    // The inventory is reproduced in the file, so a story adding a motion can see the shape
    // of the entry it owes without opening another document.
    for (const owner of ['c6-5', 'c6-6', 'c4-4', 'c4-8', 'c4-7', 'c7-5', 'c4-6', 'c4-5']) {
      expect(tokenFileSource, `UX-DR42's inventory is missing ${owner}`).toContain(owner)
    }
  })
})
