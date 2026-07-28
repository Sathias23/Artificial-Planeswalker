/**
 * The constraints stylelint cannot express, enforced anyway.
 *
 * `.stylelintrc.json` bans literals — a hex colour, an rgb() call, a hand-rolled shadow,
 * radius or spacing value. Three things it cannot see are just as load-bearing:
 *
 *   AC 10 — `--accent-dim` on `--surface-overlay` is 2.70:1 and FAILS the 3:1 non-text
 *           contrast floor (UX-DR6). No stock rule relates two declarations to each other.
 *   AC 2  — no stylesheet outside the token FILE may DECLARE a custom property. Tokens
 *           declared in a component are tokens the four alternate themes cannot reach, which
 *           quietly un-does the whole reason the layer exists.
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
 * Every INNERMOST rule block. An `@media` wrapper contributes its inner block rather than
 * itself, which is what these guards want: contrast and declaration rules apply to the block
 * that actually carries declarations.
 *
 * KNOWN LIMIT, AND THE REASON THE NESTING BAN BELOW EXISTS. Matching innermost brace pairs
 * means declarations sitting in a NESTING PARENT are in no block at all:
 *
 *     .row { background: var(--surface-overlay); &:hover { color: var(--accent-dim); } }
 *              ^^^ this declaration is invisible to every guard in this file
 *
 * Native CSS nesting is supported by every browser this app targets, so that is a live
 * hazard, not a theoretical one. Rather than grow this into a real CSS parser, the hazard is
 * made UNREACHABLE: `findNestedRules` fails the build on any nesting in a shipped stylesheet,
 * so the blind spot cannot be entered. If a later story needs nesting, it replaces this
 * reader with PostCSS — it does not simply lift the ban. (Brad's ruling 2026-07-27.)
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

/**
 * Nesting, in the only two forms that matter: an `&` reference, or a rule block opened inside
 * another rule block. Depth 2 is legal ONLY directly under an at-rule (`@media`, `@supports`,
 * `@layer`), which is how the reduced-motion block in tokens.css is written.
 */
const findNestedRules = (file: string, css: string): string[] => {
  const advice =
    'Native CSS nesting is not used in this project: the block reader in ' +
    'tests/token-usage.test.ts matches innermost braces only, so a declaration in a nesting ' +
    'parent is invisible to the contrast, token-declaration and animation guards. Write the ' +
    'selector out in full, or replace that reader with a real CSS parser first.'

  const source = stripComments(css)
  const findings: string[] = []

  // Track what each open brace belongs to, so "inside an at-rule" is distinguishable from
  // "inside a rule". `preludeStart` is where the current prelude began.
  const stack: { isAtRule: boolean; prelude: string }[] = []
  let preludeStart = 0

  for (let i = 0; i < source.length; i++) {
    const char = source[i]
    if (char === '{') {
      const prelude = source.slice(preludeStart, i).trim().replace(/\s+/g, ' ')
      const isAtRule = prelude.startsWith('@')
      const parent = stack[stack.length - 1]
      if (parent && !parent.isAtRule) {
        findings.push(`${file} — \`${prelude}\` is nested inside \`${parent.prelude}\`. ${advice}`)
      }
      stack.push({ isAtRule, prelude })
      preludeStart = i + 1
    } else if (char === '}') {
      stack.pop()
      preludeStart = i + 1
    } else if (char === ';') {
      preludeStart = i + 1
    }
  }

  // `&` is nesting even where the braces look flat (`& + &`, `&.is-live`), and it is also the
  // spelling a search-and-replace would leave behind after "flattening" a nested rule.
  for (const match of source.matchAll(/&/g)) {
    const line = source.slice(0, match.index).split('\n').length
    findings.push(`${file}:${line} — \`&\` is a nesting reference. ${advice}`)
  }

  return findings
}

const declaredTokensIn = (body: string): string[] =>
  [...body.matchAll(/(^|;)\s*(--[a-z0-9-]+)\s*:/gi)].map((m) => m[2])

const referencedTokensIn = (text: string): string[] =>
  [...stripComments(text).matchAll(/var\(\s*(--[a-z0-9-]+)/gi)].map((m) => m[1])

// ---------------------------------------------------------------------------------------
// The guards
// ---------------------------------------------------------------------------------------

/**
 * UX-DR6: `--accent-dim` is 2.70:1 on `--surface-overlay`. The substitute is `--accent`.
 *
 * WHAT THIS CATCHES AND WHAT IT DOES NOT — stated as plainly as surfaces.ts states its own
 * half, because a guard presented without its limit is worse than one presented with it.
 *
 * CAUGHT: both tokens referenced in the SAME rule block. That is the self-contained case, and
 * it is a real gate — a component cannot ship it.
 *
 * NOT CAUGHT: the cross-block case, where a parent sets `background: var(--surface-overlay)`
 * and a child sets `border-color: var(--accent-dim)`. That is not an edge case — it is the
 * NORMAL shape of c6-7's suggestion rows and c9-1's swap rows, because DESIGN.md gives the
 * container the overlay background and the row its own border. Deciding it statically needs
 * the render tree, which lives in TSX and is chosen at runtime. **Review owns that half**, the
 * same split surfaces.ts declares for the surface ramp. It is also in ui/README.md, so a
 * reviewer of c6-7 knows to look rather than assuming the gate did.
 */
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
 * `animation`, `animation-direction` and `animation-iteration-count` are LIST properties: one
 * declaration can carry several animations, comma-separated. Splitting on top-level commas
 * (never inside `cubic-bezier(…)` or `steps(…)`) lets every check below reason about ONE
 * animation at a time, which is the only way the anchors can be trusted.
 */
const commaSegments = (value: string): string[] => {
  const segments: string[] = []
  let depth = 0
  let current = ''
  for (const char of value) {
    if (char === '(') depth++
    if (char === ')') depth--
    if (char === ',' && depth === 0) {
      segments.push(current.trim())
      current = ''
    } else {
      current += char
    }
  }
  segments.push(current.trim())
  return segments.filter(Boolean)
}

/**
 * AC 12, and deliberately MORE precise than the stylelint rules that share its job.
 *
 * `.stylelintrc.json` bans the keyword spellings and does it on every `npm run lint`, over
 * every stylesheet, which is where that layer earns its place. What it CANNOT express is an
 * ITERATION COUNT written into the `animation` shorthand: `animation: pulse
 * var(--motion-glide) 3` loops three times, and a value-level regex cannot tell that bare `3`
 * from the bare numbers inside a `cubic-bezier(0.4, 0, 0.2, 1)` in the same value — banning
 * bare numbers there would false-positive on a legal easing. This guard strips parenthesised
 * groups first, so it can. `motion-violation.css` proves it: stylelint is silent on exactly
 * the two blocks whose duration is tokenised and whose only fault is the count.
 *
 * TWO EVASIONS FOUND BY REVIEW, both closed here and in the config:
 *
 *   1. COMMAS. Every anchor was `(?:\s|$)`, so in `animation: pulse 2s infinite, fade 1s` the
 *      comma after `infinite` meant nothing matched — in BOTH layers at once. Values are now
 *      split into per-animation segments before anything is tested.
 *   2. SCIENTIFIC NOTATION. `1e2` is one hundred iterations and walks straight past
 *      `\d+(\.\d+)?`. Counts are now parsed as NUMBERS and compared to 1, so `1e2`, `3.0`,
 *      `01` and `1e0` all resolve correctly rather than being string-matched.
 */
const findLoopingAnimation = (blocks: Block[]): string[] => {
  const findings: string[] = []
  const allowedCount = /^(1|1\.0+|initial|inherit|revert|revert-layer|unset)$/i
  // A whole, unitless token: `2s` and `0.5s` must not match, `1e2` must.
  const BARE_NUMBER = /(?:^|\s)(\d*\.?\d+(?:e[+-]?\d+)?)(?:\s|$)/gi

  for (const block of blocks) {
    for (const [property, value] of declarationsIn(block.body)) {
      const where = `${block.file} — \`${block.selector}\``

      if (property === 'animation-iteration-count') {
        const illegal = commaSegments(value).filter(
          (segment) => !allowedCount.test(segment) && Number(segment) !== 1,
        )
        if (illegal.length > 0) {
          findings.push(
            `${where}: animation-iteration-count is \`${illegal.join(', ')}\`. ${LOOP_ADVICE}`,
          )
        }
      }
      if (
        property === 'animation-direction' &&
        commaSegments(value).some((segment) => /^alternate(-reverse)?$/i.test(segment))
      ) {
        findings.push(`${where}: animation-direction is \`${value}\`. ${LOOP_ADVICE}`)
      }
      if (property === 'animation') {
        const bare = withoutFunctionArguments(value)
        const segments = commaSegments(bare)

        if (segments.some((s) => /(?:^|\s)infinite(?:\s|$)/i.test(s))) {
          findings.push(`${where}: the animation shorthand says \`infinite\`. ${LOOP_ADVICE}`)
        }
        if (segments.some((s) => /(?:^|\s)alternate(-reverse)?(?:\s|$)/i.test(s))) {
          findings.push(`${where}: the animation shorthand alternates. ${LOOP_ADVICE}`)
        }
        // A bare, unitless number in the shorthand IS the iteration count — durations and
        // delays always carry a unit, so there is nothing else it could be.
        const counts = segments.flatMap((s) => [...s.matchAll(BARE_NUMBER)].map((m) => m[1]))
        const looping = counts.filter((c) => Number(c) !== 1)
        if (looping.length > 0) {
          findings.push(
            `${where}: the animation shorthand carries an iteration count of ` +
              `\`${looping.join(', ')}\`. ${LOOP_ADVICE}`,
          )
        }
      }
    }
  }
  return findings
}

/**
 * UX-DR3 (story c2-5, AC 8) — the numeric role never travels alone.
 *
 * `--type-numeric` is a `font` SHORTHAND, and the shorthand cannot carry
 * `font-variant-numeric`. So `font: var(--type-numeric)` on its own renders PROPORTIONAL
 * digits: in a column of counts the 1 is narrower than the 8, every row is a different width,
 * and the numbers no longer line up — which is the entire thing UX-DR3 exists to prevent. It
 * is a worse failure than the ones above rather than a milder one, because it renders
 * something plausible instead of nothing at all, so nobody goes looking.
 *
 * THE VALUE IS CHECKED, NOT JUST THE PRESENCE. `font-variant-numeric: tabular-nums` written by
 * hand is the right answer today from the wrong source, and `proportional-nums` is the
 * companion applied to say the opposite. Only `var(--type-numeric-features)` pairs.
 *
 * WHAT THIS CANNOT SEE, in the same breath as the guard (AC 9, and the c2-4 review's ruling
 * that a guard shipped without its limit is worse than one shipped with it). The story
 * predicted the limit would be a split pair reading as clean; MEASURED, it is the opposite,
 * and the difference matters enough to write down rather than paper over:
 *
 *   NOT A LIMIT — the role in one rule and the features in another IS reported. The guard is
 *   block-local, so it flags `.stat-value` and asks for the pairing there. That is a false
 *   FAILURE, not a false pass, and it is the correct direction to be wrong in: it is also
 *   exactly the decide-once ruling this story sets ("in the same rule block"). c7-2's StatChip
 *   and c6-8's curve axis write both declarations together, which is what we want them to do.
 *
 *   THE REAL LIMIT IS THE CASCADE. A separate rule can undo a correctly paired block. The
 *   literal spelling of that attack — `.is-compact { font-variant-numeric: normal; }` — is
 *   now caught by stylelint (review round: the property's allowed-list admits ONLY
 *   `var(--type-numeric-features)`, keywords included, because every other value turns
 *   tabular numerals off). What remains invisible is the shape no value rule can object to:
 *
 *       .count      { font: var(--type-numeric); font-variant-numeric: var(--type-numeric-features); }
 *       .is-compact { font: var(--type-micro); }
 *
 *   Every declaration there is legal, but the `font` SHORTHAND resets font-variant-numeric
 *   to normal — so an element carrying both classes renders proportional digits, and this
 *   guard reports nothing: `.is-compact` applies no numeric role, so it is not a block the
 *   guard even looks at. Resolving that needs specificity, source order and the element's
 *   real class list, which lives in TSX and is chosen at runtime. **Review owns that half**,
 *   the same division of labour findAccentDimOnOverlay declares for its own cross-block case.
 */
const findUnpairedNumericRole = (blocks: Block[]): string[] => {
  // `[,)]`, not `)`. `var(--type-numeric, sans-serif)` is the same fallback evasion c2-4's
  // review found in the motion ban (`var(--motion-glide, 300ms)`): a closing paren is not the
  // only thing that can follow a token name, and a `)`-anchored regex reads that as no
  // reference at all. `--type-numeric-features` is still excluded, because what follows
  // `--type-numeric` there is `-`.
  const NUMERIC_ROLE = /var\(\s*--type-numeric\s*[,)]/i
  const NUMERIC_FEATURES = /var\(\s*--type-numeric-features\s*[,)]/i

  return blocks
    .filter((block) => {
      const declarations = declarationsIn(block.body)
      // `font` is the only property the role token can legally be spent through: it is a
      // complete shorthand, so `font-family: var(--type-numeric)` is invalid CSS that the
      // typography ban in .stylelintrc.json catches first.
      if (!declarations.some(([p, v]) => p === 'font' && NUMERIC_ROLE.test(v))) return false
      return !declarations.some(
        ([p, v]) => p === 'font-variant-numeric' && NUMERIC_FEATURES.test(v),
      )
    })
    .map(
      (block) =>
        `${block.file} — \`${block.selector}\` applies --type-numeric without ` +
        `\`font-variant-numeric: var(--type-numeric-features);\` in the same rule. The \`font\` ` +
        `shorthand cannot carry font-variant-numeric, so the digits render PROPORTIONAL and a ` +
        `column of counts stops lining up (UX-DR3). Add that declaration to this block.`,
    )
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
    // WAS `toContain('src/App.css')` until story c2-6, which deleted that placeholder when the
    // real shell arrived (AC 19). Naming a third file by path made this anchor fail on a
    // legitimate RENAME, for a reason that has nothing to do with what the anchor is for — and
    // an anchor that fails for the wrong reason is one people learn to weaken. What the anchor
    // actually needs to know is that COMPONENT stylesheets are reaching the guards at all, and
    // "there is at least one stylesheet under src/components/" is structural: the component
    // directory convention is the decide-once ruling ~35 later stories inherit, and the app
    // cannot render without a shell.
    expect(
      shippedStylesheets.filter((f) => f.startsWith('src/components/')).length,
    ).toBeGreaterThan(0)
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

  it('never applies the numeric role without its features (UX-DR3, c2-5 AC 8)', () => {
    expect(findUnpairedNumericRole(shippedBlocks)).toEqual([])
  })

  it('uses no CSS nesting, so the block reader above has no blind spot', () => {
    // Brad's ruling 2026-07-27. This is not a style preference: `blocksIn` matches innermost
    // brace pairs, so a declaration in a nesting PARENT belongs to no block and every guard
    // in this file silently skips it. Banning nesting makes that hazard unreachable rather
    // than growing a real CSS parser three stories before anything needs one.
    expect(shippedStylesheets.flatMap((f) => findNestedRules(f, sourceOf(f)))).toEqual([])
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

  it('catches the numeric role travelling alone, in all four spellings', () => {
    const findings = findUnpairedNumericRole(violation())

    // Four blocks, four different ways of getting it wrong: the companion missing entirely,
    // the same thing inside a media query (so the guard reads innermost blocks, not only
    // top-level ones), the companion hand-written as a literal, and the companion present but
    // saying the OPPOSITE. A guard that only checked for the PRESENCE of font-variant-numeric
    // would pass the last two, which is why it checks the value.
    expect(findings).toHaveLength(4)
    const joined = findings.join('\n')
    expect(joined).toContain('.count-cell')
    expect(joined).toContain('.curve-axis-value')
    expect(joined).toContain('.hand-written-features')
    expect(joined).toContain('.opts-out-of-tabular')

    // The house rule: the message names the exact declaration that is missing, so a developer
    // who trips it does not have to go and read UX-DR3 to find out what to type.
    for (const finding of findings) {
      expect(finding).toContain('font-variant-numeric: var(--type-numeric-features);')
      expect(finding).toContain('UX-DR3')
    }
  })

  it('leaves a correctly paired numeric block alone, and every other role too', () => {
    // The silent half, over blocks that DO use the role — a guard proven only on blocks with
    // no `font` declaration at all would be silent for the wrong reason.
    const legal = blocksIn(
      'inline',
      `.stat-chip { font: var(--type-numeric); font-variant-numeric: var(--type-numeric-features); }
       .heading { font: var(--type-heading); }
       .label { font: var(--type-label); letter-spacing: var(--tracking-label); }`,
    )
    expect(legal).toHaveLength(3)
    expect(findUnpairedNumericRole(legal)).toEqual([])

    // Declaration ORDER is not part of the rule — CSS does not care and neither may the guard.
    expect(
      findUnpairedNumericRole(
        blocksIn(
          'inline',
          '.a { font-variant-numeric: var(--type-numeric-features); font: var(--type-numeric); }',
        ),
      ),
    ).toEqual([])
  })

  it('reports a split pair rather than passing it — the ruling is "same rule block"', () => {
    // The story predicted this would read as clean. It does not, and the assertion is written
    // the way it MEASURES rather than the way it was predicted. Being block-local means a
    // split pair is a false FAILURE, which is the safe direction: the fix is to write both
    // declarations together, which is the decide-once ruling anyway.
    const split = blocksIn(
      'inline',
      `.stat-grid { font-variant-numeric: var(--type-numeric-features); }
       .stat-value { font: var(--type-numeric); }`,
    )
    expect(findUnpairedNumericRole(split)).toHaveLength(1)
    expect(findUnpairedNumericRole(split)[0]).toContain('.stat-value')
  })

  it('is honest about the cascade it cannot see (AC 9)', () => {
    // THE DECLARED BLIND SPOT, asserted rather than only described. A correctly paired block
    // undone by a later rule is invisible to this guard. The undoing block below is made of
    // entirely LEGAL declarations — stylelint now bans every literal font-variant-numeric
    // value (review round), so the one spelling of this attack left standing is the `font`
    // shorthand itself, which resets font-variant-numeric to normal as a side effect. That
    // block applies no numeric role, so this guard never looks at it, and resolving it would
    // need the element's real class list. If this ever starts FAILING, the guard grew a
    // cross-block reader and the comment above it needs rewriting — not deleting.
    const undone = blocksIn(
      'inline',
      `.count { font: var(--type-numeric); font-variant-numeric: var(--type-numeric-features); }
       .is-compact { font: var(--type-micro); }`,
    )
    expect(undone).toHaveLength(2)
    expect(findUnpairedNumericRole(undone)).toEqual([])
  })

  it('catches the role hidden behind a var() fallback', () => {
    // `var(--type-numeric, sans-serif)` is a reference to the role token with a fallback, and
    // a `)`-anchored regex reads it as no reference at all — the same evasion c2-4's review
    // found in the motion ban. Proven with BOTH halves carrying a fallback, so neither anchor
    // can regress alone.
    expect(
      findUnpairedNumericRole(blocksIn('inline', '.a { font: var(--type-numeric, sans-serif); }')),
    ).toHaveLength(1)
    expect(
      findUnpairedNumericRole(
        blocksIn(
          'inline',
          `.b { font: var(--type-numeric, sans-serif);
                font-variant-numeric: var(--type-numeric-features, tabular-nums); }`,
        ),
      ),
    ).toEqual([])
    // And the near-miss that must NOT be read as the role: the companion token starts with the
    // same fifteen characters.
    expect(
      findUnpairedNumericRole(
        blocksIn('inline', '.c { font-variant-numeric: var(--type-numeric-features); }'),
      ),
    ).toEqual([])
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

    // COMMA-SEPARATED LISTS (review finding, High). Every anchor used to be `(?:\s|$)`, so a
    // keyword followed by a comma matched nothing — in this guard AND in stylelint at once.
    expect(joined).toContain('.loops-forever-in-a-list')
    expect(joined).toContain('.loops-by-count-in-a-list')
    expect(joined).toContain('.ping-pongs-in-a-list')

    // THE TWO THE LINT RULE GENUINELY MISSES — the honest pair. Their durations are tokenised,
    // so the ONLY thing wrong with them is an iteration count in the `animation` shorthand,
    // which a value-level regex cannot separate from `cubic-bezier(0.4, 0, 0.2, 1)`'s numbers.
    // (The earlier `pulse 2s 3` blocks now also trip stylelint — for their literal DURATION,
    // not their count — so they can no longer carry this claim.)
    expect(joined).toContain('.loops-by-count-with-tokenised-duration')
    expect(joined).toContain('.loops-by-scientific-count-with-tokenised-duration')
    expect(joined).toContain('iteration count of `3`')
    // Scientific notation: `1e2` is one hundred, and walks past `\d+(\.\d+)?` untouched.
    expect(joined).toContain('iteration count of `1e2`')

    // EVERY looping block is flagged — no silent misses. The fixture also carries five
    // literal-DURATION blocks, which are a different ban (stylelint's, added by the same
    // review); this guard is right not to flag them, and asserting so keeps the two families
    // from quietly merging.
    const flagged = new Set(
      findings.map((f) => f.slice(f.indexOf('`') + 1, f.indexOf('`', f.indexOf('`') + 1))),
    )
    const isLoopBlock = (selector: string) =>
      selector.startsWith('.loops') || selector.startsWith('.ping-pongs')
    const loopBlocks = motion.filter((b) => isLoopBlock(b.selector))
    // Everything else in the fixture is a DURATION violation — stylelint's ban, not this
    // guard's. Defined as the complement rather than by prefix, so a block added later cannot
    // fall between the two lists and be silently unasserted.
    const durationBlocks = motion.filter((b) => !isLoopBlock(b.selector))

    expect(loopBlocks.length).toBe(14)
    expect(durationBlocks.length).toBe(12)
    expect(loopBlocks.length + durationBlocks.length).toBe(motion.length) // nothing unclassified
    expect(flagged).toEqual(new Set(loopBlocks.map((b) => b.selector)))
    for (const block of durationBlocks) {
      expect(flagged, `${block.selector} is stylelint's to catch, not this guard's`).not.toContain(
        block.selector,
      )
    }

    for (const finding of findings) {
      expect(finding).toContain('Run the animation exactly once')
    }
  })

  it('catches nesting, in both the brace form and the `&` form', () => {
    const nested = findNestedRules(
      'inline',
      `.row {
         background: var(--surface-overlay);
         .child { color: var(--accent-dim); }
       }`,
    )
    expect(nested).toHaveLength(1)
    expect(nested[0]).toContain('`.child` is nested inside `.row`')
    expect(nested[0]).toContain('Write the selector out in full')

    const ampersand = findNestedRules('inline', '.row { &:hover { color: var(--accent); } }')
    // Both signals fire: the nested brace pair AND the `&`.
    expect(ampersand.length).toBe(2)
    expect(ampersand.join('\n')).toContain('`&` is a nesting reference')

    // THE CASE THAT MOTIVATES THE BAN: with nesting present, the parent's declaration is in
    // NO block, so the contrast guard reads clean on a stylesheet that violates UX-DR6. This
    // asserts the blind spot is real — and therefore that the ban is load-bearing, not taste.
    const evasive = `.row { background: var(--surface-overlay); &:hover { color: var(--accent-dim); } }`
    expect(findAccentDimOnOverlay(blocksIn('inline', evasive))).toEqual([])
    expect(findNestedRules('inline', evasive).length).toBeGreaterThan(0)
  })

  it('does not call an at-rule or a flat stylesheet "nesting"', () => {
    // @media wrapping a rule is depth 2 and entirely legal — it is how the reduced-motion
    // block in tokens.css is written. A guard that flagged it would fail the real tree.
    expect(
      findNestedRules('inline', '@media (width >= 40em) { .a { color: var(--accent); } }'),
    ).toEqual([])
    expect(findNestedRules('inline', '.a { color: var(--accent); } .b { padding: 0; }')).toEqual([])
    // @supports and @layer nest the same way.
    expect(findNestedRules('inline', '@layer base { .a { padding: 0; } }')).toEqual([])
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
    expect(findUnpairedNumericRole(clean)).toEqual([])
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
  //
  // BRACE-AWARE, not `\{([\s\S]*)\}`. That greedy form ran to the LAST `}` in the file and
  // worked only because the media block happens to come last today; the moment any rule is
  // appended after it — the sibling `[data-theme]` block this file's own header invites — the
  // "reduced" body would swallow it and the four zeroing assertions below could be satisfied
  // by declarations sitting OUTSIDE the media query. (Review finding, Low.)
  const extractReducedMotionBlock = (css: string): string | null => {
    const opener = /@media\s*\(\s*prefers-reduced-motion:\s*reduce\s*\)\s*\{/.exec(css)
    if (!opener) return null
    const start = opener.index + opener[0].length
    let depth = 1
    for (let i = start; i < css.length; i++) {
      if (css[i] === '{') depth++
      else if (css[i] === '}' && --depth === 0) return css.slice(start, i)
    }
    return null // unbalanced braces — treated as "no block", and the first test says so
  }

  const reduced = extractReducedMotionBlock(stripComments(tokenFileSource))

  it('has a prefers-reduced-motion block at all', () => {
    expect(reduced, 'no @media (prefers-reduced-motion: reduce) block in tokens.css').not.toBeNull()
  })

  it('stops at the media query, so a later rule cannot satisfy these assertions', () => {
    // The non-vacuity guard for the extraction itself: the body must be a strict, small slice
    // of the file rather than "everything from the @media to EOF".
    expect(reduced!.length).toBeLessThan(tokenFileSource.length / 4)
    expect(reduced).not.toContain('@media')
    // A token declared after the media block must NOT appear in the extracted body.
    const spliced = stripComments(tokenFileSource) + '\n.appended-later { --motion-glide: 999ms; }'
    expect(extractReducedMotionBlock(spliced)).not.toContain('999ms')
  })

  it('zeroes all four duration tokens', () => {
    const body = reduced!
    for (const name of ['pulse', 'glide', 'bloom', 'aurora']) {
      expect(body, `--motion-${name} is not neutralised under reduced motion`).toMatch(
        new RegExp(`--motion-${name}\\s*:\\s*0m?s`),
      )
    }
  })

  it('applies to the themed selector, not only :root', () => {
    // Otherwise the fallback silently stops working the moment an alternate theme ships.
    expect(reduced!).toContain("[data-theme='voltglass']")
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
