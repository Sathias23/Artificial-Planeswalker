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

import { parse } from 'yaml'
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

/**
 * THE SAME RULE, ONE SCOPE WIDER — same-FILE rather than same-block (story c2-7, AC 14).
 *
 * FOUND BY A PROBE THAT PASSED, which is the c2-6 lesson applied rather than quoted: planting
 * `border-color: var(--accent-dim)` on `.badge-accent` — the drift the composition reference
 * ships, so the single most likely way it returns — left every gate green. `.badge-accent`
 * names no surface, so the block-local guard above never looked at it, while
 * `.badge-neutral::before` two rules away paints `--surface-overlay` under badges of EVERY
 * tone. Same stylesheet, same component, same 2.70:1 failure, and AC 14's actual claim ("do
 * not write the token in this component at all") had nothing enforcing it.
 *
 * THE RULE, derived rather than aimed at Badge: a stylesheet that references `--surface-overlay`
 * ANYWHERE has declared that its component paints on the overlay surface, so `--accent-dim`
 * anywhere in that same file is a contrast failure waiting for the two rules to meet on one
 * element. It is exactly the widening c2-6's review made to the citation gate — one file to
 * every component stylesheet — one axis over.
 *
 * WHY NOT BAN `--accent-dim` IN COMPONENTS OUTRIGHT? Because that would be a claim about
 * surfaces nobody has measured. UX-DR6 states the failure against `--surface-overlay`; the
 * token is legitimate on lighter surfaces, and a ban resting on an unmeasured number is the
 * kind a later story switches off. This fires only where the file itself supplies the evidence.
 *
 * THE LIMIT THAT REMAINS, still declared and still review's: CROSS-FILE. A Badge with no
 * `--surface-overlay` in its own stylesheet, rendered inside a `Panel` at `level="overlay"`,
 * is invisible to both scopes — the render tree lives in TSX and is chosen at runtime. That is
 * the same division of labour `surfaces.ts` declares, and it is why the primitives ALSO say in
 * their own headers that they do not write the token at all.
 */
const findAccentDimInOverlayFile = (files: string[]): string[] =>
  files
    .filter((file) => file !== TOKEN_FILE)
    .flatMap((file) => {
      const referenced = referencedTokensIn(sourceOf(file))
      if (!referenced.includes('--accent-dim') || !referenced.includes('--surface-overlay')) {
        return []
      }
      return [
        `${file} references --accent-dim in a stylesheet that also paints --surface-overlay. ` +
          `That pairing is 2.70:1, below the 3:1 non-text floor (UX-DR6), and it does not have ` +
          `to be in the same rule to meet on the same element. Use --accent (5.5:1); it is the ` +
          `named substitute.`,
      ]
    })

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

/**
 * AC 13 (story c2-7) — the THIRD member of the pairing family, after the numeric role and the
 * tracking tokens themselves.
 *
 * THE FAILURE IS IDENTICAL IN SHAPE to `findUnpairedNumericRole` above, which is why it lives
 * beside it rather than in a file of its own. A `font` SHORTHAND cannot carry `letter-spacing`
 * and cannot carry `text-transform`. So `font: var(--type-label)` written alone renders 11px
 * LOWERCASE text at the browser's default tracking, where DESIGN.md specifies uppercase at
 * 0.1em — legible, plausible, and wrong. It is worse than a value that renders as nothing,
 * because nothing prompts anyone to look. Four new stylesheets arrived in one story (a panel
 * title, a badge, a stat-chip label, a group-header label), which is the moment to install it.
 *
 * WRITTEN AS A DERIVED RULE, NOT A LIST OF TWO. The review theme four stories running has been
 * "the guards' own family coverage": round after round found a repair that stopped one member
 * short of its own family. So neither half is enumerated here.
 *
 *   THE TRACKING HALF is derived from THE TOKEN NAMES: a role `--type-X` requires
 *   `letter-spacing: var(--tracking-X)` in the same block if and only if tokens.css declares
 *   `--tracking-X`. Nobody wrote "label and micro" — and the rule therefore also covers
 *   `--type-display`, whose `--tracking-display` sibling nothing in this story uses.
 *
 *   THE UPPERCASE HALF is derived from DESIGN.md's OWN `textTransform:` keys, because it
 *   cannot be read off a token name — the `font` shorthand has no uppercase sibling token to
 *   infer from. Reading the contract is the next best thing to inferring it, and it means the
 *   day DESIGN.md makes a third role uppercase, this guard already requires it.
 *
 * THE VALUE IS CHECKED, NOT JUST THE PRESENCE, for the reason the numeric guard gives:
 * `letter-spacing: var(--tracking-micro)` on a label is the right PROPERTY carrying the wrong
 * role's value (0.08em where DESIGN.md says 0.1em), and `text-transform: lowercase` is the
 * companion applied to say the opposite.
 *
 * THE LIMIT, STATED RATHER THAN DISCOVERED (the c2-4 ruling, and c2-6's correction to it: a
 * declared blind spot is still a CLAIM, so this one is asserted below rather than only
 * described). It is BLOCK-LOCAL, exactly like its sibling, and inherits the same two
 * consequences MEASURED rather than predicted: a correct pair SPLIT across two rules is
 * reported as a failure — the safe direction, and the ruling is "same rule block" anyway — and
 * a correctly paired block UNDONE by a later `font` shorthand in another rule is invisible,
 * because the undoing block applies no role this guard looks at. Review owns that half, the
 * same division of labour `findAccentDimOnOverlay` declares for its own cross-block case.
 */
const findRoleWithoutCompanions = (
  blocks: Block[],
  requirements: Map<string, { tracking?: string; uppercase: boolean }>,
): string[] => {
  // `[,)]`, not `)`: `var(--type-label, sans-serif)` is a reference to the role WITH a
  // fallback, and a `)`-anchored regex reads it as no reference at all — the evasion c2-4's
  // review found in the motion ban and c2-5's numeric guard had to be repaired for.
  const ROLE_IN_FONT = /var\(\s*(--type-[a-z0-9-]+)\s*[,)]/gi
  const findings: string[] = []

  for (const block of blocks) {
    const declarations = declarationsIn(block.body)
    const where = `${block.file} — \`${block.selector}\``

    for (const [property, value] of declarations) {
      // `font` only. A role token spent through any other property is invalid CSS that the
      // typography ban in .stylelintrc.json catches first — and `font-variant-numeric:
      // var(--type-numeric-features)` must not be mistaken for a role application, which
      // falls out for free: `--type-numeric-features` is not a key in `requirements`.
      if (property !== 'font') continue

      for (const match of value.matchAll(ROLE_IN_FONT)) {
        const role = match[1].toLowerCase()
        const required = requirements.get(role)
        if (!required) continue

        if (required.tracking) {
          const paired = declarations.some(
            ([p, v]) =>
              p === 'letter-spacing' &&
              new RegExp(`var\\(\\s*${required.tracking}\\s*[,)]`, 'i').test(v),
          )
          if (!paired) {
            findings.push(
              `${where} applies ${role} without \`letter-spacing: var(${required.tracking});\` ` +
                `in the same rule. The \`font\` shorthand cannot carry letter-spacing, so the ` +
                `text renders at the browser's DEFAULT tracking rather than DESIGN.md's ` +
                `(UX-DR5, AC 13). Add that declaration to this block.`,
            )
          }
        }

        if (required.uppercase) {
          // NOT bare equality (review 2026-07-29): the tracking half above tolerates a legal
          // decoration (`var(--tracking-label, 0.1em)` matches through `[,)]`), and an
          // exact-string uppercase check gave the two halves inconsistent tolerance — a legal
          // `uppercase !important` would have produced a FALSE "missing companion" finding,
          // which is the false positive a later story fights by weakening the guard.
          const cased = declarations.some(
            ([p, v]) =>
              p === 'text-transform' &&
              v
                .toLowerCase()
                .replace(/\s*!important\s*$/, '')
                .trim() === 'uppercase',
          )
          if (!cased) {
            findings.push(
              `${where} applies ${role} without \`text-transform: uppercase;\` in the same ` +
                `rule. The \`font\` shorthand cannot carry text-transform, and DESIGN.md ` +
                `declares this role uppercase — so the text renders in whatever case the ` +
                `caller happened to type (AC 13). Add that declaration to this block.`,
            )
          }
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

/**
 * AC 13's requirements, DERIVED from the two contracts rather than typed out.
 *
 * The path is the same one tests/tokens.test.ts pins, and it is written out here rather than
 * shared because that file's constant is deliberately "the ONE place this path is written" for
 * the token-fidelity suite. Both files carry a loud anchor that turns a stale path into a
 * named failure instead of a guard asserting nothing over an empty map — see the `it()` below.
 */
const DESIGN_MD = fileURLToPath(
  new URL(
    '../../_bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md',
    import.meta.url,
  ),
)

const designTypography = (): Record<string, { textTransform?: string }> => {
  const raw = readFileSync(DESIGN_MD, 'utf8')
  const match = /^---\r?\n([\s\S]*?)\r?\n---/.exec(raw)
  if (!match) {
    throw new Error(`No YAML frontmatter found in ${DESIGN_MD} — has the artefact moved?`)
  }
  const parsed = parse(match[1]) as {
    typography?: Record<string, { textTransform?: string }>
  } | null
  // The SECOND loud anchor (review 2026-07-29): frontmatter that parses but has lost or
  // renamed its `typography:` key would otherwise reach Object.entries(undefined) — a bare
  // TypeError at module scope that fails every suite in this file with an unnamed error,
  // which is exactly what these anchors exist to prevent.
  if (!parsed?.typography) {
    throw new Error(
      `No \`typography\` block in ${DESIGN_MD}'s frontmatter — renamed, or the artefact changed shape?`,
    )
  }
  return parsed.typography
}

/**
 * `--type-X` -> what it may not travel without. The tracking half comes from the TOKEN NAMES
 * (a `--tracking-X` sibling exists, therefore the role requires it); the uppercase half comes
 * from DESIGN.md's own `textTransform:` keys, because no token name encodes it. Neither is a
 * list, so a role nobody thought about is covered the moment its sibling or its key exists.
 */
const companionRequirements = new Map<string, { tracking?: string; uppercase: boolean }>()
for (const [name, role] of Object.entries(designTypography())) {
  const roleToken = `--type-${name}`
  if (!declaredTokens.has(roleToken)) continue
  const trackingToken = `--tracking-${name}`
  const tracking = declaredTokens.has(trackingToken) ? trackingToken : undefined
  const uppercase = role?.textTransform === 'uppercase'
  if (tracking || uppercase) companionRequirements.set(roleToken, { tracking, uppercase })
}

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

  it('never puts --accent-dim in a stylesheet that paints --surface-overlay (c2-7 AC 14)', () => {
    expect(findAccentDimInOverlayFile(shippedStylesheets)).toEqual([])
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

  it('derived AC 13 requirements from the real contracts, not from a hand-typed list', () => {
    // THE NON-VACUITY ANCHOR for the guard below, and the loud failure a moved DESIGN.md
    // produces: an empty map would make `findRoleWithoutCompanions` pass over every block in
    // the tree by requiring nothing of any of them.
    //
    // The three expectations are stated as VALUES rather than as "not empty", because the
    // point of deriving them is that they are checkable: `display` earns a tracking
    // requirement and NO uppercase one, which is exactly the member a "label and micro" list
    // would have missed, and `heading` and `body` earn neither so they are absent entirely.
    expect([...companionRequirements.keys()].sort()).toEqual([
      '--type-display',
      '--type-label',
      '--type-micro',
    ])
    expect(companionRequirements.get('--type-display')).toEqual({
      tracking: '--tracking-display',
      uppercase: false,
    })
    expect(companionRequirements.get('--type-label')).toEqual({
      tracking: '--tracking-label',
      uppercase: true,
    })
    expect(companionRequirements.get('--type-micro')).toEqual({
      tracking: '--tracking-micro',
      uppercase: true,
    })
  })

  it('never applies a type role without its companions (AC 13, UX-DR5)', () => {
    expect(findRoleWithoutCompanions(shippedBlocks, companionRequirements)).toEqual([])
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

  it('catches --accent-dim meeting --surface-overlay ACROSS blocks in one file (AC 14)', () => {
    // The firing half for the widened scope, on the shape a probe found passing: two rules,
    // neither wrong alone, that meet on one element at render time. The block-local guard is
    // proven SILENT on the same input in the same breath — otherwise this test would pass
    // because the old guard caught it, and the widening would be untested.
    const file = 'tests/fixtures/css/accent-dim-cross-block.css'
    const source = readFileSync(fixture('css/accent-dim-cross-block.css'), 'utf8')

    expect(findAccentDimOnOverlay(blocksIn(file, source))).toEqual([])

    const findings = findAccentDimInOverlayFile([file])
    expect(findings).toHaveLength(1)
    expect(findings[0]).toContain('2.70:1')
    expect(findings[0]).toContain('Use --accent (5.5:1)')
  })

  it('leaves --accent-dim alone in a file that paints no overlay (the silent half)', () => {
    // A guard proven only on files containing BOTH tokens would be silent for the wrong
    // reason. `--accent-dim` is a legitimate token on lighter surfaces; UX-DR6's measured
    // claim is about `--surface-overlay` specifically, and this guard must not grow into a
    // ban resting on a number nobody measured.
    expect(findAccentDimInOverlayFile(['tests/fixtures/css/clean.css'])).toEqual([])
  })

  it('reads code, not the prose about the code', () => {
    // EVERY primitive stylesheet explains in its header why it does not use `--accent-dim`,
    // and Badge.css names BOTH tokens in that prose while genuinely painting the overlay
    // surface in `.badge-neutral::before`. A guard that read documentation as code would fire
    // on precisely the files that got it right, and the repair someone would reach for is
    // deleting the explanation. `referencedTokensIn` strips comments first; this is the
    // non-vacuity proof that it does, asserted against the real file rather than a mock of it.
    const badge = sourceOf('src/components/Badge/Badge.css')
    expect(badge).toContain('--accent-dim')
    expect(referencedTokensIn(badge)).not.toContain('--accent-dim')
    expect(referencedTokensIn(badge)).toContain('--surface-overlay')
    expect(findAccentDimInOverlayFile(['src/components/Badge/Badge.css'])).toEqual([])
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

  it('catches every way a type role can travel without its companions (AC 13)', () => {
    const findings = findRoleWithoutCompanions(violation(), companionRequirements)
    const joined = findings.join('\n')

    // The TOTAL is pinned per fixture file, never in aggregate (the house standard this test
    // originally missed — review 2026-07-29): containment assertions alone would pass a guard
    // regression that ADDED spurious findings on the fixture's clean-looking lines. And the
    // pin earned its keep the day it was written: this test's own prose undercounted the
    // fixture at eight — `.bare-label-inside-media` applies the bare role, so it is reported
    // TWICE, once per missing companion, exactly like `.bare-micro`. Nine, measured.
    expect(findings).toHaveLength(9)

    // NINE findings across seven blocks: tracking missing, uppercase missing, BOTH missing
    // (two findings from one block), the role the guard was not written for, the right
    // property carrying the wrong role's value, the companion saying the opposite, and a bare
    // role inside a media query (two findings again) so the guard is proven to read innermost
    // blocks rather than only top-level ones.
    expect(joined).toContain('.bare-label-tracking')
    expect(joined).toContain('.bare-label-case')
    expect(joined).toContain('.bare-micro')
    expect(joined).toContain('.wrong-tracking-sibling')
    expect(joined).toContain('.opts-out-of-uppercase')
    expect(joined).toContain('.bare-label-inside-media')

    // THE MEMBER A LIST OF TWO WOULD HAVE MISSED. `--type-display` is caught for its missing
    // tracking and — separately — is NOT asked for uppercase, because DESIGN.md does not
    // declare it uppercase. Both halves of that matter: a guard that demanded uppercase of
    // every role would turn the shell's own `h1` red.
    expect(joined).toContain('.bare-display-tracking')
    expect(findings.filter((f) => f.includes('.bare-display-tracking')).join('\n')).not.toContain(
      'text-transform',
    )

    // `.bare-micro` declares NEITHER companion, so it is reported twice — once per missing
    // companion. A guard that stopped at the first fault per block would tell a developer to
    // add the tracking, and then tell them about the case only after they had run it again.
    expect(findings.filter((f) => f.includes('.bare-micro'))).toHaveLength(2)

    // The house rule: every message names the exact declaration that is missing, so a
    // developer who trips it does not have to go and read DESIGN.md to find out what to type.
    for (const finding of findings) {
      expect(finding).toMatch(/letter-spacing: var\(--tracking-|text-transform: uppercase;/)
      expect(finding).toContain('AC 13')
    }
  })

  it('leaves correctly paired blocks alone — including the roles it requires nothing of', () => {
    // THE SILENT HALF, over blocks that DO apply a role. A guard proven only on blocks with no
    // `font` declaration at all would be silent for the wrong reason.
    const legal = blocksIn(
      'inline',
      `.title { font: var(--type-label); letter-spacing: var(--tracking-label);
                text-transform: uppercase; }
       .kicker { font: var(--type-micro); letter-spacing: var(--tracking-micro);
                 text-transform: uppercase; }
       .deck-name { font: var(--type-display); letter-spacing: var(--tracking-display); }
       .value { font: var(--type-heading); }
       .row { font: var(--type-body); }
       .strong { font: var(--type-body-strong); }
       .count { font: var(--type-numeric); font-variant-numeric: var(--type-numeric-features); }`,
    )
    expect(legal).toHaveLength(7)
    expect(findRoleWithoutCompanions(legal, companionRequirements)).toEqual([])

    // Declaration ORDER is not part of the rule — CSS does not care and neither may the guard.
    expect(
      findRoleWithoutCompanions(
        blocksIn(
          'inline',
          `.a { text-transform: uppercase; letter-spacing: var(--tracking-label);
                font: var(--type-label); }`,
        ),
        companionRequirements,
      ),
    ).toEqual([])

    // A LEGAL DECORATION is not a missing companion (review 2026-07-29): `!important` is
    // valid CSS on both companions, and an exact-string uppercase check read it as absence —
    // a false positive on a block that got the rule RIGHT, which is the kind a later story
    // repairs by weakening the guard. The tracking half already tolerated it through `[,)]`;
    // this pins the uppercase half to the same tolerance.
    expect(
      findRoleWithoutCompanions(
        blocksIn(
          'inline',
          `.b { font: var(--type-label); letter-spacing: var(--tracking-label) !important;
                text-transform: uppercase !important; }`,
        ),
        companionRequirements,
      ),
    ).toEqual([])
  })

  it('catches the role hidden behind a var() fallback, and the near-miss it must not read', () => {
    // `var(--type-label, sans-serif)` is a reference to the role WITH a fallback, and a
    // `)`-anchored regex reads it as no reference at all — the evasion c2-4's review found in
    // the motion ban. Proven on BOTH sides, so neither anchor can regress alone.
    expect(
      findRoleWithoutCompanions(
        blocksIn('inline', '.a { font: var(--type-label, sans-serif); }'),
        companionRequirements,
      ),
    ).toHaveLength(2)
    expect(
      findRoleWithoutCompanions(
        blocksIn(
          'inline',
          `.b { font: var(--type-label, sans-serif);
                letter-spacing: var(--tracking-label, 0.1em); text-transform: uppercase; }`,
        ),
        companionRequirements,
      ),
    ).toEqual([])
    // `--type-numeric-features` shares its first fifteen characters with `--type-numeric` and
    // is not a role at all: it is not a key in the derived map, so it can never be read as one.
    expect(
      findRoleWithoutCompanions(
        blocksIn('inline', '.c { font-variant-numeric: var(--type-numeric-features); }'),
        companionRequirements,
      ),
    ).toEqual([])
  })

  it('is honest about the two limits it shares with the numeric guard (AC 13)', () => {
    // DECLARED BLIND SPOTS, ASSERTED rather than only described — c2-6's keeper lesson was
    // that a declared limit is still a CLAIM, and its own unmeasured one was hiding a real
    // failure. Both of these are MEASURED here.
    //
    // (1) A SPLIT PAIR is reported, not passed. The guard is block-local, so this is a false
    //     FAILURE — the safe direction to be wrong in, and "same rule block" is the ruling
    //     anyway.
    const split = blocksIn(
      'inline',
      `.group { letter-spacing: var(--tracking-label); text-transform: uppercase; }
       .group-label { font: var(--type-label); }`,
    )
    expect(findRoleWithoutCompanions(split, companionRequirements)).toHaveLength(2)

    // (2) THE CASCADE IS INVISIBLE. A correctly paired block undone by a later `font`
    //     shorthand in ANOTHER rule reads as clean, because the undoing block applies a role
    //     whose own companions it satisfies vacuously — `--type-body` requires none. Resolving
    //     it needs specificity, source order and the element's real class list, which live in
    //     TSX and are chosen at runtime. If this ever starts FAILING, the guard grew a
    //     cross-block reader and this comment needs rewriting, not deleting.
    const undone = blocksIn(
      'inline',
      `.label { font: var(--type-label); letter-spacing: var(--tracking-label);
                text-transform: uppercase; }
       .is-plain { font: var(--type-body); }`,
    )
    expect(findRoleWithoutCompanions(undone, companionRequirements)).toEqual([])
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
