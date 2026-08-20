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

import { MANA_COLOUR_ORDER } from '../src/components/ManaCost/parse.ts'
import { SURFACE_RAMP } from '../src/styles/surfaces.ts'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))
const fixture = (rel: string) => fileURLToPath(new URL(`fixtures/${rel}`, import.meta.url))

/** The one file allowed to declare tokens. Every other stylesheet only consumes them. */
const TOKEN_FILE = 'src/styles/tokens.css'

// git is the file authority, not readdir: it cannot see node_modules, dist or coverage, and
// a stray stylesheet is caught the moment it is committed — which is when CI sees it.
// DECLARED LIMIT (c4-7 review): the same blindness applies to an un-`git add`ed stylesheet, so
// a NEW file passes this sweep vacuously until staged; tree-walk redesign in deferred-work.md.
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
 * reviewer of c6-7 knows to look rather than assuming the gate did. **That review happened
 * (2026-08-11) and its answer is checked in**: `SuggestionsView.css` spends no `--accent-dim` at
 * all, and the two tests further down assert exactly that over the file's bytes — which is the
 * only mechanical purchase available on a case this guard cannot decide.
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
/**
 * Custom properties that are SET FROM MARKUP AT RUNTIME, not declared in the token layer.
 *
 * ================= A THIRD CATEGORY, AND STORY c4-8 IS THE FIRST TO NEED IT =============
 *
 * Until c4-8 every `var(--…)` in every stylesheet in this repo was a DESIGN TOKEN, so
 * `findUnknownTokenReferences` could treat "not declared in tokens.css" as "misspelled, and it
 * resolves to nothing at runtime". That inference is now incomplete: a custom property can also
 * be a *channel*, declared nowhere and written per element by a component through the
 * `style` attribute — which is precisely the escape hatch `eslint.config.js` reserved for *"a
 * computed bar height in c4-8"* and which that story amended the rule to open.
 *
 * **It was found by this guard going red, not by anyone predicting it**, which is worth saying:
 * the story enumerated the ESLint rule and the two lint fixtures as the work, and the token
 * guard is a third gate the hatch collides with that no artefact mentioned.
 *
 * ================= AN ALLOWLIST, IN THE OPEN, FOR THE MANA_DATA_INK REASON ==============
 *
 * Not a pattern exemption (`/^--curve-/`, or "anything with a fallback"). Both of those are
 * rules an author can satisfy by accident, and the failure this guard exists to catch — a
 * MISSPELLED token name resolving to nothing — looks exactly like a runtime channel from the
 * outside. So each entry is named, with the file that consumes it and the reason, and a
 * non-vacuity test proves the consuming file actually references it. A story adding a second
 * channel adds an entry here, the same protocol `MANA_DATA_INK` and `PRIMITIVES` use.
 *
 * The narrowness is the point: the property is allowed in ONE file, so the same name spelled in
 * another stylesheet is still a failure.
 */
const RUNTIME_CUSTOM_PROPERTIES: Map<string, { file: string; reason: string }> = new Map([
  [
    '--curve-bar-height',
    {
      file: 'src/containers/ManaCurve/ManaCurve.css',
      reason:
        'the mana curve bar height IS the data (story c4-8, Q10, AC 17) — a per-bar percentage ' +
        'computed from the deck at render time, which no class can express and which changes ' +
        'whenever the deck does. Written by ManaCurve.tsx through the custom-property escape ' +
        'hatch eslint.config.js reserved for this story by name; declared in NO stylesheet on ' +
        'purpose, because it has no design value — it is a channel, not a token. The fallback ' +
        '`0%` in the rule is what makes an absent attribute draw nothing rather than a full bar.',
    },
  ],
  [
    '--colour-bar-share',
    {
      file: 'src/containers/ColourDistribution/ColourDistribution.css',
      reason:
        'the colour bar segment width IS the data (story c4-9, Q13, AC 19) — one segment per ' +
        'colour, sized by that colour’s share of the deck’s pips, which no class can express ' +
        'because a percentage is continuous. THE SECOND ENTRY ON THIS LIST, and the first test ' +
        'of whether the exact-NAME protocol survives growth rather than sliding back into a ' +
        '`/^--/` prefix: it does, in both places at once (eslint.config.js chains a second ' +
        '`:not([key.value=…])`). It is NARROWER than --curve-bar-height rather than wider — it ' +
        'carries a RAW PIP COUNT, and `flex-grow: var(--colour-bar-share, 0)` makes the BROWSER ' +
        'divide, so no percentage is computed in TSX and no call site can divide by zero. The ' +
        'fallback `0` is what makes an absent attribute draw nothing rather than let a zero ' +
        'basis grow to fill the whole track.',
    },
  ],
])

// The reader is injectable for the same reason findCardRadiusInMarkup's is (and it was the
// c4-8 review that added the seam here): the "nowhere else" half of the channel scoping needs
// to play a channel's declaration in a file its entry does not name, and no shipped stylesheet
// legitimately contains one — so without the seam that half is either untested or vacuous.
const findUnknownTokenReferences = (
  files: string[],
  known: Set<string>,
  read: (file: string) => string = sourceOf,
): string[] =>
  files.flatMap((file) =>
    [...new Set(referencedTokensIn(read(file)))]
      .filter((name) => !known.has(name))
      .filter((name) => RUNTIME_CUSTOM_PROPERTIES.get(name)?.file !== file)
      .map(
        (name) =>
          `${file} references ${name}, which ${TOKEN_FILE} does not declare — it resolves to ` +
          `nothing at runtime. Fix the name, or add the token to ${TOKEN_FILE}.`,
      ),
  )

// ---------------------------------------------------------------------------------------
// AC 14 (story c2-8) — UX-DR7's "the WUBRG tokens are DATA INK" becomes a gate
// ---------------------------------------------------------------------------------------

/**
 * WHY THIS GUARD EXISTS AT ALL, which is the part worth reading. The `--mana-*` tokens have
 * shipped since c2-4 with a rule attached to them — "curve bars, mana pips and colour-identity
 * dots ONLY, never chrome" (tokens.css line 96, UX-DR7) — and MEASURED at c2-8's baseline
 * commit, `git grep -- '--mana-'` over ui/ returned SEVEN hits: all seven were the declarations
 * in tokens.css. For four stories the rule had no consumer and no gate, which makes it a
 * sentence rather than a constraint. c2-8 writes the first consumer and the gate in the same
 * commit, before c4-8's curve segments and c4-9's colour bar arrive to test whether it was ever
 * real.
 *
 * ==== HALF ONE: WHICH FILES MAY REFERENCE ONE AT ALL ====================================
 * An allowlist, each entry carrying the reason it is data ink. Today that is ManaPip.css alone.
 * c4-8 and c4-9 join it IN THE OPEN, in their own stories, which is the same protocol
 * `PRIMITIVES` in tests/shell.test.ts adopted after review made it git-derived — and the
 * non-vacuity test below proves every entry is a file git actually tracks, so a renamed
 * stylesheet fails loudly instead of silently allowing nothing.
 *
 * ==== HALF TWO: WHICH PROPERTIES MAY SPEND ONE ==========================================
 * AN ALLOWLIST OF PROPERTIES, NOT A BAN LIST, and that choice is the whole strength of this
 * guard. "Ban the family, never enumerate members" has been the review finding in five
 * consecutive stories, and the strongest available form of it is not a wider ban — it is an
 * inverted one. A ban keyed on `/^border/`, `/^outline/` and `/shadow$/` is still a list of
 * families its author happened to think of; `filter`, `caret-color`, `text-decoration-color`,
 * `accent-color`, `column-rule-color` and `-webkit-text-stroke-color` are all chrome and none
 * of them is in it. An allowlist cannot be evaded by a property nobody thought of, because
 * thinking of it is not what makes it fail.
 *
 * ==== THE HALF THAT IS NOT STATICALLY DECIDABLE, DECLARED HERE RATHER THAN DISCOVERED ====
 * UX-DR7's rule ends "…or an UNSTACKED curve bar". Whether a given curve bar is genuinely
 * stacked is not a property of its stylesheet: it is a property of the data bound to it and the
 * elements composed at runtime, both of which live in TSX. **Review owns that half**, the same
 * division of labour `surfaces.ts`'s `stepsExactlyOne()` and `findAccentDimOnOverlay` above
 * both declare for their own cross-block cases. c4-8's reviewer must LOOK; this file will not
 * have looked for them.
 *
 * A second, smaller limit in the same breath: this is block-local and value-keyed, so a
 * `--mana-*` reached through an intermediate custom property would be invisible — except that
 * declaring one outside tokens.css is itself a failure two guards up, which is what makes this
 * one safe rather than lucky.
 *
 * A third residual, declared here because it is REVIEW'S too (review 2026-07-29): a chrome-
 * SHAPED spend through an ALLOWED property in an ALLOWLISTED file — a hover tint, a button-like
 * `background: var(--mana-r)` inside ManaPip.css or a file c4-8 adds — passes both halves,
 * because "is this background a datum or chrome" is the same not-statically-decidable question
 * as "is this bar stacked". The allowlist REASON is what review checks it against.
 *
 * ==== THE MARKUP HALF (review 2026-07-29) ===============================================
 * Both halves above read STYLESHEETS, so a `--mana-*` spent from markup — an SVG
 * `fill="var(--mana-r)"` presentation attribute, a value in index.html — would meet neither,
 * and c4-8/c4-9 draw charts, where SVG fill is the natural spelling. So a third check scans
 * every git-tracked non-CSS source file for a `var(--mana-` reference and allows NONE: markup
 * has no allowlist to join, because the way in is always a class in an allowlisted stylesheet,
 * exactly as ManaPip does it. (`referencedTokensIn` strips block comments first, so prose
 * ABOUT the tokens — ManaPip.tsx's own header — does not read as a spend.)
 */
const isManaToken = (name: string) => /^--mana-/i.test(name)

/** File -> why that file is data ink. Later stories ADD an entry with their own reason. */
const MANA_DATA_INK: Map<string, string> = new Map([
  [
    'src/components/ManaPip/ManaPip.css',
    'the pip IS the datum: a filled circle whose entire content is the colour of the symbol it ' +
      'stands for (UX-DR13, story c2-8).',
  ],
  [
    'src/containers/ColourDistribution/ColourDistribution.css',
    'the segment IS the datum: one band per colour, sized by that colour’s share of the deck’s ' +
      'pips, and UX-DR18 calls it "data ink used correctly" in the artefact’s own words (story ' +
      'c4-9). THE FIRST JOINER SINCE c2-8 DECLARED THIS LIST — c2-8 named c4-8 and c4-9 as the ' +
      'two invited, c4-8 declined with a measurement (a curve stacked by colour would paint 24 ' +
      'live rows colourless from a structurally blank `colors` field) and wrote "c4-9 remains ' +
      'invited"; this story cannot decline, because its bar is mana-* ink by specification. ' +
      'Every spend is through `background` and through a CLASS, which is ManaPip.css’s shape ' +
      'and the only way in: the markup half allows none anywhere outside a stylesheet.',
  ],
])

/** Fill properties, and only fill properties. Everything else is chrome by construction. */
const MANA_INK_PROPERTY = /^(background(-color|-image)?|fill|stop-color)$/i

const findManaTokenOutsideDataInk = (files: string[]): string[] =>
  files
    .filter((file) => file !== TOKEN_FILE && !MANA_DATA_INK.has(file))
    .flatMap((file) => {
      const spent = [...new Set(referencedTokensIn(sourceOf(file)))].filter(isManaToken)
      if (spent.length === 0) return []
      return [
        `${file} references ${spent.join(', ')}. The WUBRG tokens are DATA INK — pips, colour ` +
          `bars and STACKED curve segments only, never chrome (UX-DR7). If this file genuinely ` +
          `draws a datum, add it to MANA_DATA_INK in tests/token-usage.test.ts with the reason, ` +
          `the way c4-8 and c4-9 will; otherwise use a --surface-*, --border-* or --accent token.`,
      ]
    })

// The markup half's file list: everything git tracks that is not a stylesheet and not a
// fixture. Fixtures exist to be broken and are fed to the guard explicitly below.
const shippedMarkupFiles = execFileSync(
  'git',
  ['ls-files', 'index.html', 'src/*.ts', 'src/*.tsx'],
  {
    cwd: uiRoot,
    encoding: 'utf8',
  },
)
  .split('\n')
  .filter(Boolean)

const findManaTokenInMarkup = (files: string[]): string[] =>
  files.flatMap((file) => {
    const spent = [...new Set(referencedTokensIn(sourceOf(file)))].filter(isManaToken)
    if (spent.length === 0) return []
    return [
      `${file} references ${spent.join(', ')} outside a stylesheet. The data-ink guards read ` +
        `CSS only, so a var(--mana-*) in markup — an inline style, an SVG fill attribute — ` +
        `would be policed by NOTHING. There is no markup allowlist to join: give the element a ` +
        `class in a MANA_DATA_INK stylesheet instead, the way ManaPip does (UX-DR7).`,
    ]
  })

const findManaTokenInChromeProperty = (blocks: Block[]): string[] =>
  blocks.flatMap((block) =>
    declarationsIn(block.body)
      .filter(
        ([property, value]) =>
          referencedTokensIn(value).some(isManaToken) && !MANA_INK_PROPERTY.test(property),
      )
      .map(
        ([property]) =>
          `${block.file} — \`${block.selector}\` spends a --mana-* token through \`${property}\`. ` +
          `A WUBRG colour may only FILL a datum (background, background-color, ` +
          `background-image, fill, stop-color); every other property is chrome, which is what ` +
          `UX-DR7 bans. Use a --surface-*, --border-* or --accent token for chrome.`,
      ),
  )

/**
 * The other side of AC 12: every colour class ManaPip.tsx can NAME must exist in ManaPip.css,
 * and must name a real `--mana-*` token.
 *
 * WHY IT IS A GUARD AND NOT A COMMENT. A class that does not exist is not an error anywhere: it
 * renders an unstyled — which is to say transparent, which is to say INVISIBLE — circle, and
 * `findUnknownTokenReferences` cannot help because there is no `var()` to be wrong. That is the
 * same defect the mock's runtime-built `'var(--mana-' + color + ')'` produces, arriving through
 * the door the fix left open. The 21 suffixes are DERIVED from `MANA_COLOUR_ORDER` — six
 * singles plus all fifteen unordered pairs — so a seventh colour would demand its classes here
 * without anyone remembering to ask.
 */
const pipColourSuffixes = (): string[] => {
  const suffixes: string[] = []
  for (let i = 0; i < MANA_COLOUR_ORDER.length; i++) {
    suffixes.push(MANA_COLOUR_ORDER[i])
    for (let j = i + 1; j < MANA_COLOUR_ORDER.length; j++) {
      suffixes.push(`${MANA_COLOUR_ORDER[i]}${MANA_COLOUR_ORDER[j]}`)
    }
  }
  return suffixes
}

const MANA_PIP_CSS = 'src/components/ManaPip/ManaPip.css'

const findUndeclaredPipColourClasses = (blocks: Block[]): string[] =>
  pipColourSuffixes().flatMap((suffix) => {
    const selector = `.mana-pip-${suffix}`
    const block = blocks.find((b) => b.file === MANA_PIP_CSS && b.selector === selector)
    if (!block) {
      return [
        `${MANA_PIP_CSS} declares no \`${selector}\`, but ManaPip.tsx can produce that class ` +
          `from MANA_COLOUR_ORDER. An undeclared class is not an error anywhere — it renders a ` +
          `TRANSPARENT circle, which is invisible rather than wrong-coloured.`,
      ]
    }
    if (!referencedTokensIn(block.body).some(isManaToken)) {
      return [
        `${MANA_PIP_CSS} — \`${selector}\` names no --mana-* token, so the pip it styles has no ` +
          `fill of its own (AC 12).`,
      ]
    }
    return []
  })

// ---------------------------------------------------------------------------------------
// AC 12 (story c4-3) — UX-DR4's EXCLUSIVITY half becomes a gate
// ---------------------------------------------------------------------------------------

/**
 * WHY THIS GUARD EXISTS AT ALL, and why the answer is "because of this commit".
 *
 * DESIGN.md:362 states the rule in one sentence with two halves: *"Tiles, thumbnails, placeholders
 * and the detail art all use `{rounded.card}` … at a `{components.card-tile.aspect}` of 63:88 …
 * **Nothing else in the UI borrows the card radius, and cards never borrow a chrome radius** —
 * cards must be the ONLY card-shaped things on screen, and they must ACTUALLY be card-shaped."*
 *
 * The first half of that sentence has had a token since c2-4. The second half has had NOTHING
 * checking it, and until story c4-3 it was **vacuously true**: measured across `ui/`, the only
 * occurrences of `--radius-card` were its own declaration in `tokens.css`, one line in a fixture,
 * and two assertions in `tokens.test.ts` that it is a percentage. **Zero consumers.** A rule with
 * no consumer is indistinguishable from a rule nobody obeys, which is exactly the state the
 * `--mana-*` tokens were in for four stories before the guard below this one was written.
 *
 * c4-3 is the first consumer, so it is the commit where the rule stops being free — and building
 * it now means building it against ONE card-shaped file instead of the four that c4-4, c4-5 and
 * c4-6 are about to add.
 *
 * ==== HALF ONE: WHICH FILES MAY SPEND `--radius-card` AT ALL ============================
 * An allowlist, each entry carrying the reason that file is card-shaped — the same protocol as
 * `MANA_DATA_INK` above and `PRIMITIVES` in tests/shell.test.ts, and the non-vacuity test below
 * proves every entry is a file git actually tracks. c4-4, c4-5 and c4-6 join it IN THE OPEN.
 *
 * ==== HALF TWO: A CARD-SHAPED FILE MAY NOT SPEND A CHROME RADIUS =======================
 * The converse, and it is NOT redundant: an allowlist keyed on "spends the card radius" would say
 * nothing at all about `border-radius: var(--radius-md)` written on `.card-placeholder`, which is
 * the *"chrome-shaped cards"* half of DESIGN.md's own anti-pattern table. So membership of this
 * list is a declaration that the FILE draws cards, and it cuts both ways: in, and out.
 *
 * Written as a NEGATED PATTERN (`--radius-` that is not `--radius-card`) rather than as a list of
 * `sm | md | lg | pill`, because "ban the family, never enumerate members" is this epic's standing
 * review finding: a `--radius-xl` added to tokens.css next year is covered without anyone
 * remembering to come back here.
 *
 * ==== THE MARKUP HALF ==================================================================
 * Both halves above read STYLESHEETS. The `--mana-*` guard learned this the hard way, so it is
 * built in from the start here: a `var(--radius-card)` reached from markup — an SVG presentation
 * attribute, a value in index.html — would meet neither half. There is no markup allowlist to
 * join, because the way in is always the `card-shape` class. (ESLint already bans inline `style`
 * attributes outright, so this half is a second lock on a closed door rather than the only one.)
 *
 * ==== WHAT THIS GUARD CANNOT SEE, DECLARED RATHER THAN DISCOVERED ======================
 * The same division of labour `findAccentDimOnOverlay` and `surfaces.ts` declare for their halves:
 *
 *   1. **WHETHER AN ELEMENT IS ACTUALLY A CARD.** `.card-shape` on a `<nav>` is a stylesheet this
 *      guard finds perfectly clean — the class list lives in TSX and is chosen at runtime. That is
 *      the *"cards must be the ONLY card-shaped things on screen"* half, and it is REVIEW'S.
 *   2. **GEOMETRY APPLIED FROM MARKUP.** An inline `style={{ borderRadius: … }}` is banned by
 *      eslint's inline-style rule, not by this one.
 *   3. **CROSS-FILE COMPOSITION.** A card-shaped element given a chrome radius by a rule in a
 *      NON-card-shaped stylesheet (`.deck-row .card-shape { border-radius: … }`) is invisible
 *      here, because the file it lives in is not in the list and the property is not `--radius-
 *      card`. Deciding it needs specificity and the real class list. Review's, and c4-4's tile is
 *      the first story where it becomes plausible.
 *   4. **A CARD-SHAPED FILE THAT NEVER DECLARES ITSELF** (review finding). A later stylesheet
 *      that draws a card but never joins CARD_SHAPED, and rounds itself with `--radius-md`,
 *      meets NEITHER half — half one fires only on `--radius-card` spends, half two reads only
 *      listed files. This is the likeliest real drift for c4-4/c4-5/c4-6, and it is review's:
 *      joining the list is the reviewable act, and a new card-drawing stylesheet that does not
 *      is the thing to catch at the PR.
 *   5. **PROSE IN A LINE COMMENT** (review finding). `stripComments` strips BLOCK comments only
 *      — CSS has no line comments, so that is all a STYLESHEET needs — but the markup half reads
 *      `.tsx` too, where a `// use var(--radius-card) via card-shape` line comment IS stripped by
 *      no one and fires the guard on prose. The failure is loud and names the file, so it cannot
 *      pass wrongly — but the repair is to move the prose into a block comment, never to delete
 *      the explanation.
 */
const CARD_GEOMETRY_CSS = 'src/styles/card-geometry.css'

/** File -> why that file draws cards. Later stories ADD an entry with their own reason. */
const CARD_SHAPED: Map<string, string> = new Map([
  [
    CARD_GEOMETRY_CSS,
    'the ONE declaration of the card shape — `aspect-ratio: 63 / 88` and `border-radius: ' +
      'var(--radius-card)` on `.card-shape`, consumed by class name so that c4-3, c4-4, c4-5 and ' +
      'c4-6 cannot drift from each other (story c4-3, UX-DR4, UX-DR36).',
  ],
  [
    'src/components/CardPlaceholder/CardPlaceholder.css',
    'the named and unknown placeholders and the loading well — card-shaped by specification ' +
      '(DESIGN.md:389), and therefore held to the OTHER half of UX-DR4: it may not round its own ' +
      'corners with a chrome radius (story c4-3).',
  ],
  [
    'src/containers/CardTile/CardTile.css',
    'the card tile — the grid unit whose whole content IS a card face (DESIGN.md:379, ' +
      '"the card face IS the tile"), so it is card-shaped by definition rather than by ' +
      'resemblance (story c4-4). Joining is the reviewable act blind spot #4 above describes: ' +
      'this file spends no --radius-card at all — the shape arrives through the `card-shape` ' +
      'class — so half one would never have looked at it, and it is half TWO that has to hold. ' +
      'The mock ships --radius-md for tiles and DESIGN.md:362 corrects it by name. Its quantity ' +
      'badge is CHROME on a card rather than a card, DESIGN.md gives it {rounded.pill}, and ' +
      'that is why the badge is a separate stylesheet (QuantityBadge.css, deliberately NOT in ' +
      'this list) instead of an exception carved into this guard.',
  ],
  [
    'src/containers/CardDetail/CardDetail.css',
    'the detail panel’s ART — DESIGN.md gives `components.card-detail` an `art-radius` of ' +
      '`{rounded.card}`, so the full card face in the right column is card-shaped by ' +
      'specification, at the same 63:88 and the same PERCENTAGE corner as a 176px grid ' +
      'thumbnail (story c4-5). Joining is the reviewable act blind spot #4 describes: this file ' +
      'spends no --radius-card at all — the shape arrives through the `card-shape` class — so ' +
      'half one would never have looked at it, and it is half TWO that has to hold. Its ' +
      'chrome — the panel frame’s --radius-lg pinned ring, the unpin control’s --radius-sm — ' +
      'is deliberately in a SECOND stylesheet (CardDetailChrome.css, not in this list), which ' +
      'is the CardTile.css / QuantityBadge.css precedent rather than a new exception.',
  ],
])

// CASE-SENSITIVE, deliberately (review finding): CSS custom properties are case-sensitive, so
// `var(--RADIUS-CARD)` is a DIFFERENT, undefined property — a `/i` here would classify that typo
// as the card radius and mis-police it in both directions instead of leaving it to fail visibly.
const isCardRadius = (name: string) => /^--radius-card$/.test(name)
const isChromeRadius = (name: string) => /^--radius-/.test(name) && !isCardRadius(name)

const findCardRadiusOutsideCardShape = (
  files: string[],
  read: (file: string) => string = sourceOf,
  cardShaped: Map<string, string> = CARD_SHAPED,
): string[] =>
  files
    .filter((file) => file !== TOKEN_FILE && !cardShaped.has(file))
    .flatMap((file) => {
      const spent = [...new Set(referencedTokensIn(read(file)))].filter(isCardRadius)
      if (spent.length === 0) return []
      return [
        `${file} references --radius-card. The card radius is EXCLUSIVE to card faces, ` +
          `thumbnails, placeholders and detail art (UX-DR4) — "nothing else in the UI borrows ` +
          `the card radius". A card-shaped element inherits the shape from the \`card-shape\` ` +
          `class in ${CARD_GEOMETRY_CSS}; it does not re-declare it. If this file genuinely ` +
          `draws a card, add it to CARD_SHAPED in tests/token-usage.test.ts with the reason, the ` +
          `way c4-4, c4-5 and c4-6 will; otherwise use --radius-sm, --radius-md, --radius-lg or ` +
          `--radius-pill.`,
      ]
    })

const findChromeRadiusInCardShapedFile = (
  files: string[],
  read: (file: string) => string = sourceOf,
  cardShaped: Map<string, string> = CARD_SHAPED,
): string[] =>
  files
    .filter((file) => cardShaped.has(file))
    .flatMap((file) => {
      const spent = [...new Set(referencedTokensIn(read(file)))].filter(isChromeRadius)
      if (spent.length === 0) return []
      return [
        `${file} references ${spent.join(', ')}. ${cardShaped.get(file)} UX-DR4's other half is ` +
          `"cards never borrow a chrome radius" — a card rounded at --radius-md is the ` +
          `"chrome-shaped cards" anti-pattern DESIGN.md names, and it is the failure an allowlist ` +
          `keyed only on --radius-card would never look for. Use var(--radius-card) through the ` +
          `\`card-shape\` class, or take this file out of CARD_SHAPED.`,
      ]
    })

const findCardRadiusInMarkup = (
  files: string[],
  read: (file: string) => string = sourceOf,
): string[] =>
  files.flatMap((file) => {
    const spent = [...new Set(referencedTokensIn(read(file)))].filter(isCardRadius)
    if (spent.length === 0) return []
    return [
      `${file} references --radius-card outside a stylesheet. The two halves of the UX-DR4 gate ` +
        `read CSS only, so a var(--radius-card) in markup would be policed by NOTHING. There is ` +
        `no markup allowlist to join: give the element the \`card-shape\` class instead.`,
    ]
  })

/**
 * NO ERROR STYLING, WHERE THAT IS A CONSTRUCTIVE RULE RATHER THAN A REVIEW NOTE (story c2-9,
 * AC 2, AC 14, UX-DR30).
 *
 * The epic bans illustration, icon, red fill, exclamation mark and error styling in one breath,
 * and exactly one of those is decidable by a machine: the TOKEN. `--negative` exists, and a red
 * panel is the single most natural thing to reach for on a 500 — so leaving it to review is how
 * it arrives in c4-10 instead of being impossible.
 *
 * IT IS AN ALLOWLIST, NOT A BAN LIST, and that is this epic's own standing finding applied
 * rather than merely quoted. c2-8's review round measured it directly: a family ban keyed on
 * `--negative`/`--caution` is still a list its author thought of, and says nothing about
 * `--positive` used as a reassurance tint, `--mana-r` spent as a red fill by another name, or a
 * `--danger` a later story adds. The families below are the ones a CALM panel is made of; every
 * other token fails closed, which is the only form of this rule that covers a token that does
 * not exist yet.
 *
 * SCOPED TO THE STYLESHEETS THAT DECLARE THEMSELVES CALM, and the scope is the reason rather
 * than an oversight: c4-10's format check maps a violation to `negative` and MUST spend that
 * token, and c5-7's connection pill spends all three status colours by specification — SHIPPED
 * 2026-08-08, and `src/containers/ConnectionPill/ConnectionPill.css` is deliberately NOT added to
 * the map below, which is exactly what this paragraph pre-authorised. A
 * repo-wide ban would be false. A later story that ships a calm surface adds its file here with
 * its own reason, the way `MANA_DATA_INK` grows.
 */
const CALM_STYLESHEETS: Map<string, string> = new Map([
  [
    'src/components/StatePanel/StatePanel.css',
    'the state panel is the surface UX-DR30 bans error styling on by name — "calm text on a ' +
      'calm panel", including for the 500 (story c2-9).',
  ],
])

/**
 * Token families a calm surface is built from. Everything else fails closed.
 *
 * `--accent` is EXACT, not a prefix — the review of 2026-07-29 found the open prefix admitted
 * `--accent-dim`, the one calm-named token this repo already documents as an alarm in disguise
 * (2.70:1, failing the 3:1 floor — tokens.css and StatePanel.css both say so). A prefix here
 * would have been the guard's own fallback evasion: a token that PASSES because its name starts
 * calmly. Every entry that is a genuine open family stays a prefix.
 */
const CALM_TOKEN_FAMILY: { prefix: string; exact?: true; why: string }[] = [
  { prefix: '--surface-', why: 'the four-step ramp is neutral by construction' },
  { prefix: '--border-', why: 'hairline and strong are both neutral' },
  { prefix: '--text-', why: 'the three text tones carry no status' },
  {
    prefix: '--accent',
    exact: true,
    why: 'UX-DR30 puts the NEXT ACTION in --accent; that is its job here — the ONE token, not the family: --accent-dim fails the 3:1 floor on this text',
  },
  { prefix: '--radius-', why: 'geometry' },
  { prefix: '--space-', why: 'geometry' },
  { prefix: '--type-', why: 'type roles' },
  { prefix: '--tracking-', why: 'the companions some type roles require' },
  { prefix: '--font-', why: 'families, including c2-9 --font-mono for the command chip' },
]

const findAlarmingTokenInCalmStylesheet = (
  files: string[],
  // The reader is injected so the firing half can feed source that is not on disk — the shape
  // `findStrayFontFaces` in tests/fonts.test.ts already uses. A fixture FILE was declined here:
  // the thing being proven is a token reference, which needs no valid stylesheet around it.
  read: (file: string) => string = sourceOf,
  calm: Map<string, string> = CALM_STYLESHEETS,
): string[] =>
  files
    .filter((file) => calm.has(file))
    .flatMap((file) => {
      // `referencedTokensIn` matches `var(` followed by the name, so a FALLBACK spelling —
      // `var(--negative, transparent)` — is caught by the same call. That evasion has bitten
      // this repo three times and is probed explicitly below rather than assumed.
      const spent = [...new Set(referencedTokensIn(read(file)))]
      return spent
        .filter(
          (token) =>
            !CALM_TOKEN_FAMILY.some(({ prefix, exact }) =>
              exact ? token === prefix : token.startsWith(prefix),
            ),
        )
        .map(
          (token) =>
            `${file} references ${token}. ${calm.get(file)} This stylesheet may ` +
            `only spend the calm families (${CALM_TOKEN_FAMILY.map((f) => f.prefix).join(', ')}); ` +
            `an ALLOWLIST rather than a ban list, because "no error styling" has to cover a ` +
            `status token nobody has invented yet. If this surface genuinely needs ${token}, ` +
            `that is a UX-DR30 change and it is made HERE, in the open.`,
        )
    })

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
    // 64 until story c2-9's `--font-mono` (Q2); 65 until story c4-4's
    // `--shadow-focus-ring-over-art` (Q2); 66 until story c4-5's two inspection rings,
    // `--shadow-live-ring` and `--shadow-pinned-ring` (Q4), which move together because one
    // story gives both a consumer. Sibling pin: `expectedNames` in tests/tokens.test.ts, which
    // is the one that checks the VALUE against DESIGN.md. Both move together or the pair is
    // wrong — and c4-4's probe (j) is the proof that moving only one goes red. 68 until story
    // c4-7's `--shadow-deck-row-live` (Q6), the deck row's inset live rule. 69 until story
    // c6-7's `--shadow-suggestion-row-live` (Q2), the same marker on the one surface where
    // `--accent-dim` genuinely fails its floor rather than merely being weak.
    expect(declaredTokens.size).toBe(70)
  })

  it('never puts --accent-dim on --surface-overlay (AC 10, UX-DR6)', () => {
    expect(findAccentDimOnOverlay(shippedBlocks)).toEqual([])
  })

  it('never puts --accent-dim in a stylesheet that paints --surface-overlay (c2-7 AC 14)', () => {
    expect(findAccentDimInOverlayFile(shippedStylesheets)).toEqual([])
  })

  // ==================== THE ASSERTION `AgentView.css:29` PROMISED WOULD LAND AT c6-7 ======
  //
  // That header says the repo-wide guard *"covers this stylesheet the day it is added; the
  // tile-level assertion lands with c6-7's rows, which is where the first tile inside a view
  // exists"* (Brad's Q7 ruling, 2026-08-10). This is it, and it is HERE rather than in the
  // component suite for the reason this file's own blind-spot note gives: the composition it
  // worries about — a parent painting `--surface-overlay` while a CHILD file sets an accent-dim
  // border — is *"the NORMAL shape of c6-7's suggestion rows"* and no guard can decide it
  // statically. jsdom evaluates no stylesheet at all, so the component suite could not assert it
  // either. What CAN be asserted is that the file spends none of the token in any spelling, over
  // the same bytes the guards above read — and that is what this does, named, so a later edit
  // that introduces one is caught by a test that says why.
  //
  // Note what it still does NOT close: whether `--accent` at 5.5:1 is legible over the row's own
  // `--accent-glow` tint is a PIXEL question, and the row is on DESIGN.md's no-visual-precedent
  // list. That is the C6 manual checklist's (c8-6).
  const SUGGESTION_ROW_CSS = 'src/containers/SuggestionsView/SuggestionsView.css'

  it('spends no --accent-dim in the suggestion row, the guard’s own named blind spot (c6-7)', () => {
    const css = stripComments(sourceOf(SUGGESTION_ROW_CSS))

    // NON-VACUITY FIRST: this is the right file, it really does paint the overlay surface, and it
    // really does spend the accent family — otherwise "contains no accent-dim" would pass on an
    // empty read or a path typo, which is this suite's own recorded failure mode.
    expect(shippedStylesheets).toContain(SUGGESTION_ROW_CSS)
    expect(css).toContain('.suggestion-row')
    expect(css).toContain('var(--surface-overlay)')
    expect(css).toContain('var(--accent-glow)')
    expect(css).toContain('var(--shadow-suggestion-row-live)')

    expect(
      css,
      'accent-dim measures 2.70:1 on surface-overlay — under the 3:1 non-text floor (UX-DR6)',
    ).not.toMatch(/accent-dim/)
  })

  it('floors the two text rows at one line each, so a malformed item cannot collapse the thumbnail (Greptile P1, 2026-08-11)', () => {
    // jsdom evaluates no layout, so nothing in the component suite can prove a row does NOT
    // shrink to a sliver — this is a SOURCE read, the same shape as the accent-dim test above.
    // Every child of `.suggestion-row-head` renders NOTHING for absent data (`Badge` returns
    // `null`, an unhydrated name is `''`, `ManaCost` renders nothing for a `null` cost, confidence
    // is absent by default), and `.suggestion-row-reason` is a bare empty span for a missing
    // `reason` — so a maximally malformed or not-yet-hydrated item leaves both grid rows with zero
    // content, and an empty flex/grid item with no padding is 0px tall. The thumbnail spans both
    // rows (`grid-row: 1 / span 2`), so a collapsed pair collapses it too.
    const css = stripComments(sourceOf(SUGGESTION_ROW_CSS))

    expect(css).toContain('.suggestion-row-head')
    expect(css).toContain('.suggestion-row-reason')
    expect(
      (css.match(/min-height:\s*1lh/g) ?? []).length,
      "both text rows need the floor — one is not enough to protect the thumbnail's span",
    ).toBe(2)
  })

  it('draws no card in the suggestion row — the CARD_SHAPED split, stated (c6-7)', () => {
    // Blind spot #4 in this guard's own header is *"a card-drawing stylesheet that never joins
    // CARD_SHAPED"*, and c6-7's row stylesheet is exactly the file that could become one: it
    // holds a card thumbnail and rounds ITSELF with `--radius-md`. It stays unlisted, so it must
    // draw no card — the thumbnail's geometry arrives through the global `card-shape` class and
    // `CardPlaceholder`'s own listed stylesheet, and this file only says where the card goes.
    // DECLARATIONS ONLY, and that is blind spot #5 applied rather than tripped over: this file's
    // header EXPLAINS the split in prose, naming both `--radius-card` and `aspect-ratio` as the
    // things it deliberately does not spend. A raw-source read would fire on the explanation —
    // and the guard's own note says the repair is never to delete the prose.
    const css = stripComments(sourceOf(SUGGESTION_ROW_CSS))

    expect(CARD_SHAPED.has(SUGGESTION_ROW_CSS)).toBe(false)
    expect(css).not.toMatch(/--radius-card/)
    expect(css).not.toMatch(/aspect-ratio/)
    // …while it DOES spend the chrome radius the artefact gives the row, which is what makes the
    // two absences above a decision rather than an empty file.
    expect(css).toContain('var(--radius-md)')
  })

  it('declares tokens in exactly one file (AC 2)', () => {
    expect(findTokenDeclarationsOutsideTokenFile(shippedBlocks)).toEqual([])
  })

  it('references no token that does not exist', () => {
    expect(findUnknownTokenReferences(shippedStylesheets, declaredTokens)).toEqual([])
  })

  describe('the runtime custom-property channel (story c4-8, Q10, AC 17)', () => {
    it('permits each declared channel in its OWN file, and nowhere else', () => {
      // The narrowness is the whole guard. `--curve-bar-height` is legal in ManaCurve.css
      // because a component writes it there; the same name in any other stylesheet is still a
      // reference to a token that does not exist.
      for (const [name, { file }] of RUNTIME_CUSTOM_PROPERTIES) {
        expect(
          findUnknownTokenReferences([file], declaredTokens).join('\n'),
          `${name} is not permitted in its own file`,
        ).not.toContain(name)

        // THE "NOWHERE ELSE" HALF, DRIVEN RATHER THAN LOCATED (review finding, c4-8): the
        // shipped draft found a second stylesheet, asserted it EXISTED, and never fed it
        // through the guard — and its exclusion predicate keyed FILE PATHS into a Map keyed
        // by PROPERTY NAMES, so it proved nothing and nobody noticed because the result was
        // discarded. The injected reader (the findCardRadiusInMarkup seam) plays the same
        // declaration in a file the entry does not name, and the guard must report it — this
        // is the assertion that goes red if the per-file filter in findUnknownTokenReferences
        // ever degrades into a name-only exemption.
        expect(
          findUnknownTokenReferences(
            ['src/probe.css'],
            declaredTokens,
            () => `.probe { height: var(${name}); }`,
          ).join('\n'),
          `${name} outside ${file} is not reported — the scoping is not real`,
        ).toContain(name)
      }
    })

    it('is NOT vacuous — every entry is a tracked file that really references its property', () => {
      // The `MANA_DATA_INK` lesson: an allowlist entry naming a renamed or deleted file permits
      // nothing and reads as coverage. Both halves are checked, so a stale entry fails loudly.
      for (const [name, { file, reason }] of RUNTIME_CUSTOM_PROPERTIES) {
        expect(shippedStylesheets, `${file} is not a git-tracked stylesheet`).toContain(file)
        expect(
          referencedTokensIn(sourceOf(file)),
          `${file} does not reference ${name} — the entry permits nothing`,
        ).toContain(name)
        // And the property really is undeclared: an entry for something tokens.css DOES declare
        // would be a token quietly relabelled as a runtime channel to dodge the two pins.
        expect(declaredTokens.has(name), `${name} is a declared token, not a runtime channel`).toBe(
          false,
        )
        expect(reason.length, `${name}'s entry carries no real reason`).toBeGreaterThan(40)
      }
    })

    it('still fails a MISSPELLED token — the failure this guard exists for', () => {
      // The firing half, and the reason this is an allowlist rather than a pattern exemption:
      // a misspelled token name and a runtime channel look identical from the outside, so any
      // rule shaped like `/^--curve-/` or "has a fallback" would let the typo through too.
      const misspelled = findUnknownTokenReferences(
        ['src/containers/ManaCurve/ManaCurve.css'],
        new Set([...declaredTokens].filter((t) => t !== '--surface-well')),
      )
      expect(misspelled.join('\n')).toContain('--surface-well')
    })
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

  it('spends --mana-* tokens in the data-ink files only (AC 14, UX-DR7)', () => {
    expect(findManaTokenOutsideDataInk(shippedStylesheets)).toEqual([])
  })

  it('spends --mana-* tokens through FILL properties only (AC 14, UX-DR7)', () => {
    expect(findManaTokenInChromeProperty(shippedBlocks)).toEqual([])
  })

  it('spends no --mana-* token from markup at all (AC 14, the markup half)', () => {
    // NON-VACUITY FIRST: the list must be reading the real tree — the shell, both components
    // and index.html — or an empty scan passes for a clean one.
    expect(shippedMarkupFiles).toContain('index.html')
    expect(shippedMarkupFiles).toContain('src/components/ManaPip/ManaPip.tsx')
    expect(shippedMarkupFiles.length).toBeGreaterThan(10)
    expect(findManaTokenInMarkup(shippedMarkupFiles)).toEqual([])
  })

  it('styles no calm surface with an alarm token (c2-9 AC 14, UX-DR30)', () => {
    // NON-VACUITY FIRST: every file that declares itself calm must be one git actually tracks,
    // or the scan passes by reading nothing — the exact trap c2-4 hit with an unstaged
    // tokens.css and five stories have re-hit since.
    expect(CALM_STYLESHEETS.size).toBeGreaterThan(0)
    for (const file of CALM_STYLESHEETS.keys()) {
      expect(
        shippedStylesheets,
        `CALM_STYLESHEETS names ${file}, which git does not track`,
      ).toContain(file)
      // …and the file must actually spend tokens, so a stylesheet that had been emptied could
      // not pass for a clean one.
      expect(referencedTokensIn(sourceOf(file)).length).toBeGreaterThan(5)
    }
    expect(findAlarmingTokenInCalmStylesheet(shippedStylesheets)).toEqual([])
  })

  it('reads the grow-not-clip geometry ManaPip.test.tsx defers to (AC 16)', () => {
    // THE SOURCE READ THAT COMMENT PROMISES (review 2026-07-29 — the first draft promised it
    // without it existing, c2-7's StatChip lesson verbatim). jsdom cannot see whether a wide
    // glyph fits, so the claim is pinned where it lives: the pip grows from a MINIMUM, never a
    // fixed width, and nothing in the file clips what grew.
    const pipBlock = shippedBlocks.find(
      (block) => block.file === MANA_PIP_CSS && block.selector === '.mana-pip',
    )
    expect(pipBlock, `${MANA_PIP_CSS} declares no .mana-pip block`).toBeTruthy()
    const properties = declarationsIn(pipBlock!.body).map(([property]) => property.toLowerCase())
    expect(properties).toContain('min-width')
    expect(properties).not.toContain('width')
    for (const block of shippedBlocks.filter((b) => b.file === MANA_PIP_CSS)) {
      for (const [property] of declarationsIn(block.body)) {
        expect(
          property.toLowerCase().startsWith('overflow'),
          `${MANA_PIP_CSS} — \`${block.selector}\` declares \`${property}\`, which hides AC 16's defect rather than fixing it`,
        ).toBe(false)
      }
    }
  })

  it('is enforcing a rule that has a real consumer, not an empty one (non-vacuity, AC 14)', () => {
    // THE ANCHOR THIS GUARD NEEDS MORE THAN MOST. Both halves are filters: with no consumer
    // anywhere they pass by finding nothing, which is precisely the state the tokens were in
    // for the four stories before this one — and it is indistinguishable from compliance.
    //
    // Every allowlist entry must be a file GIT TRACKS, so a rename fails loudly here rather
    // than silently permitting a path that no longer exists (and, worse, no longer constrains
    // the file that replaced it).
    for (const [file, reason] of MANA_DATA_INK) {
      expect(shippedStylesheets, `MANA_DATA_INK names ${file}, which git does not track`).toContain(
        file,
      )
      expect(reason.length, `${file}'s allowlist entry carries no reason`).toBeGreaterThan(40)
    }
    // And the consumer genuinely spends the tokens, so "no findings" means "checked and clean".
    // SIX of the family's SEVEN: `--mana-gold` (tokens.css declares it for multicolour
    // identity) has no pip class and no consumer yet — deliberately, because MANA_COLOUR_ORDER
    // is the parser's colour vocabulary and "gold" is not a cost colour.
    const spent = referencedTokensIn(sourceOf(MANA_PIP_CSS)).filter(isManaToken)
    expect(new Set(spent).size).toBe(6)
  })

  it('still has NO consumer for --mana-gold — c4-9 declined it, and the count stays 6 of 7', () => {
    // ==== THE PREDICTION THIS ASSERTION REPLACES (story c4-9, Q8, AC 17) =================
    // The comment above used to end *"its first consumer (c4-9's colour-identity bar is the
    // likely one) joins MANA_DATA_INK in the open and spends it as a fill, and this count moves
    // to 7 THERE"*, and `ui/README.md` said the same. **That prediction was wrong, and it is
    // corrected here rather than left standing**: c4-9 DID join MANA_DATA_INK — it is the first
    // joiner since this list was declared — and it did NOT spend gold.
    //
    // The reason is the one MANA_COLOUR_ORDER already encodes in writing: gold is a CARD-level
    // property (UX-DR17 uses it for a multicolour card contributing one segment to a stacked
    // curve), and UX-DR18 specifies a PIP count. **A pip is never gold.** `{W/U}` is a
    // white-or-blue pip, and ManaPip already draws it as a two-stop gradient across two real
    // tokens; a gold band in a colour bar would name neither half of a cost anyone pays.
    //
    // ASSERTED RATHER THAN OBSERVED (c4-5's AC-14 pattern): an absence that is only ever noted
    // in prose is an absence nothing protects. Gold's first consumer is a stacked curve or a
    // colour-identity dot, neither of which is in Phase 1 — and whichever story ships it moves
    // this count to 7 by deleting this test, in the open.
    const goldSpenders = [...MANA_DATA_INK.keys()].filter((file) =>
      referencedTokensIn(sourceOf(file)).some((name) => /^--mana-gold$/.test(name)),
    )
    expect(goldSpenders).toEqual([])

    // …and specifically not in c4-9's own stylesheet, named so the failure says which file.
    const COLOUR_BAR_CSS = 'src/containers/ColourDistribution/ColourDistribution.css'
    expect(MANA_DATA_INK.has(COLOUR_BAR_CSS), 'the colour bar is not declared data ink').toBe(true)
    expect(sourceOf(COLOUR_BAR_CSS)).not.toMatch(/var\(\s*--mana-gold/)

    // NON-VACUITY: the same reader DOES find the six colours the bar really spends, so an empty
    // result above means "checked and clean" rather than "read the wrong file".
    const barSpends = new Set(referencedTokensIn(sourceOf(COLOUR_BAR_CSS)).filter(isManaToken))
    expect(barSpends.size).toBe(6)
  })

  it('declares every colour class ManaPip.tsx can name — all 21 of them (AC 12)', () => {
    expect(pipColourSuffixes()).toHaveLength(21)
    expect(findUndeclaredPipColourClasses(shippedBlocks)).toEqual([])
  })

  it('writes the card geometry EXACTLY ONCE, where four later stories inherit it (c4-3 AC 2)', () => {
    // AC 4's INSTRUMENT (a), and it is the honest one. jsdom has no layout engine, so
    // `getComputedStyle(el).aspectRatio` in a component test returns the empty string and PASSES
    // FOR THE WRONG REASON — the sixth time this epic has recorded that trap (c2-2 AC 17, c2-5
    // AC 4, c2-6 AC 4/5, c2-7 AC 21, c2-8 AC 21). A source read is what can actually see the
    // declarations; the component test's half is that the rendered element carries the CLASS.
    // Neither instrument proves a pixel, and that limit is stated in the story record.
    const shape = shippedBlocks.find(
      (block) => block.file === CARD_GEOMETRY_CSS && block.selector === '.card-shape',
    )
    expect(shape, `${CARD_GEOMETRY_CSS} declares no \`.card-shape\` block`).toBeTruthy()

    const declarations = new Map(
      declarationsIn(shape!.body).map(([property, value]) => [property.toLowerCase(), value]),
    )
    // `63 / 88` with the spaces the file actually writes — the printed card, not "about 0.716".
    expect(declarations.get('aspect-ratio')?.replace(/\s+/g, ' ')).toBe('63 / 88')
    expect(declarations.get('border-radius')).toBe('var(--radius-card)')

    // …AND NOWHERE ELSE. This is the "exactly once" half, and it is what makes UX-DR36's claim
    // — the placeholder occupies the same footprint as a real card face, so layout never reflows
    // when art arrives — structurally true rather than asserted separately by four stories. A
    // second `aspect-ratio` anywhere in the shipped tree is a second value free to drift.
    const elsewhere = shippedBlocks
      .filter((block) => block.file !== CARD_GEOMETRY_CSS)
      .filter((block) =>
        declarationsIn(block.body).some(([property]) => property.toLowerCase() === 'aspect-ratio'),
      )
      .map((block) => `${block.file} — \`${block.selector}\` declares its own aspect-ratio`)
    expect(elsewhere).toEqual([])

    // …AND THE RADIUS TOO (review finding). The scan above covers `aspect-ratio` only, and the
    // two halves of the UX-DR4 gate cannot close this one: half one EXEMPTS every CARD_SHAPED
    // file, and half two only bans CHROME radii there — so a card-shaped file re-declaring
    // `border-radius: var(--radius-card)` of its own passed everything, and that is the drift
    // channel for the radius half of the footprint claim. Exactly once means BOTH declarations.
    const radiusElsewhere = shippedBlocks
      .filter((block) => block.file !== CARD_GEOMETRY_CSS && block.file !== TOKEN_FILE)
      .filter((block) =>
        declarationsIn(block.body).some(([, value]) =>
          referencedTokensIn(value).some(isCardRadius),
        ),
      )
      .map((block) => `${block.file} — \`${block.selector}\` re-declares the card radius`)
    expect(radiusElsewhere).toEqual([])
  })

  it('never uppercases the truncated card ID, because the route would refuse it (c4-3 Q4)', () => {
    // FOUND BY A PROBE THAT PASSED, which is the c2-6 lesson applied rather than quoted. Probe
    // (j) of this story put the id back in `--type-micro` — correctly paired with BOTH its
    // companions, so `findRoleWithoutCompanions` was satisfied — and the whole suite stayed
    // GREEN at 1,021 passed. Every typography guard in this file asks whether a role travels
    // with its companions; NONE of them asks whether the right role was chosen for the content,
    // and here that difference is not cosmetic.
    //
    // THE PREMISE IS READ FROM THE BACKEND, not restated. `cards.py`'s `_CARD_ID_PATTERN` is
    // lowercase-only by an explicit ruling ("Nothing is reachable by normalising an uppercase
    // id"), so a `text-transform: uppercase` on the id puts a value on screen that the route
    // would refuse if a reader typed it back — and the id is the ONLY identifying thing the
    // unknown variant has. Reading the pattern rather than asserting the rule means that if the
    // backend ever accepts uppercase, this guard's own premise fails loudly instead of enforcing
    // a rule that has quietly stopped being true.
    const cardsPy = readFileSync(
      fileURLToPath(new URL('../../src/companion/app/routes/cards.py', import.meta.url)),
      'utf8',
    )
    const pattern = /_CARD_ID_PATTERN\s*=\s*r?"([^"]+)"/.exec(cardsPy)
    expect(pattern, 'no _CARD_ID_PATTERN in cards.py — has the route moved?').not.toBeNull()
    expect(
      pattern![1],
      'the card-id route is no longer lowercase-only; re-decide c4-3 Q4',
    ).toContain('0-9a-f')
    expect(pattern![1]).not.toContain('A-F')

    const idBlock = shippedBlocks.find(
      (block) =>
        block.file === 'src/components/CardPlaceholder/CardPlaceholder.css' &&
        block.selector === '.card-placeholder-id',
    )
    expect(idBlock, 'CardPlaceholder.css declares no `.card-placeholder-id` block').toBeTruthy()
    for (const [property, value] of declarationsIn(idBlock!.body)) {
      expect(
        property.toLowerCase() === 'text-transform' && /uppercase|capitalize/i.test(value),
        `the truncated card ID is rendered \`${value}\`, but ${pattern![1]} is lowercase-only — ` +
          `the reader would be shown an id the route refuses. Use a role with no textTransform ` +
          `(--type-numeric is the ruled one, and it must carry font-variant-numeric with it).`,
      ).toBe(false)
    }

    // DECLARED LIMIT: this names ONE selector. A later story that renders an id, a set code or
    // any other retypeable value elsewhere is not covered — the general rule ("do not uppercase
    // data the user may type back") is not statically decidable, because whether a string is
    // retypeable lives in the product, not the stylesheet. Review's, and it is in ui/README.md.
    //
    // AND ONE MORE (review finding): the loop reads the declarations IN this block. A
    // `text-transform: uppercase` arriving by INHERITANCE from an ancestor rule in the same
    // file (`.card-placeholder { text-transform: uppercase }`) uppercases the id while this
    // guard stays green — same shape as blind spot 3 of the radius gate above (cross-rule
    // composition needs specificity and the cascade, which a source read does not have).
    // Review's, at any edit that touches an ancestor selector of `.card-placeholder-id`.
  })

  it('spends --radius-card in the card-shaped files only (c4-3 AC 12, UX-DR4)', () => {
    expect(findCardRadiusOutsideCardShape(shippedStylesheets)).toEqual([])
  })

  it('never gives a card-shaped file a CHROME radius (c4-3 AC 12, UX-DR4)', () => {
    expect(findChromeRadiusInCardShapedFile(shippedStylesheets)).toEqual([])
  })

  it('spends no --radius-card from markup at all (c4-3 AC 12, the markup half)', () => {
    expect(findCardRadiusInMarkup(shippedMarkupFiles)).toEqual([])
  })

  it('is enforcing a card-shape rule that has a real consumer (non-vacuity, c4-3 AC 12)', () => {
    // THE ANCHOR THIS GUARD NEEDS MOST, for the reason the --mana-* one gives: both halves are
    // FILTERS, so with no consumer anywhere they pass by finding nothing — which is precisely the
    // state `--radius-card` was in for the four stories before c4-3 (zero consumers, measured),
    // and which is indistinguishable from compliance.
    for (const [file, reason] of CARD_SHAPED) {
      expect(shippedStylesheets, `CARD_SHAPED names ${file}, which git does not track`).toContain(
        file,
      )
      expect(reason.length, `${file}'s allowlist entry carries no reason`).toBeGreaterThan(40)
    }
    // And the token is genuinely SPENT — this is the assertion that would have failed on every
    // commit before this one.
    expect(referencedTokensIn(sourceOf(CARD_GEOMETRY_CSS)).filter(isCardRadius)).toHaveLength(1)
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

  // ---- c2-9 AC 14: no error styling on a calm surface -----------------------------------
  //
  // Every case below is a spelling the guard does NOT name, which is the whole argument for an
  // allowlist over a ban list (c2-8's ruling). `--negative` is here because the AC names it;
  // the other four are the ones a ban list would have missed.
  const CALM_FIXTURE = new Map([['src/calm.css', 'a calm surface, for the firing half.']])
  const probeCalm = (css: string) =>
    findAlarmingTokenInCalmStylesheet(['src/calm.css'], () => css, CALM_FIXTURE)

  it.each([
    ['the token the AC names', '.p { background: var(--negative); }', '--negative'],
    ['the other alarm colour', '.p { border-color: var(--caution); }', '--caution'],
    // THE FALLBACK EVASION, three times bitten. `var(--negative, transparent)` renders as
    // nothing under this theme and as a red panel under any theme that declares the token
    // differently — a value that lints clean and looks fine on the author's machine.
    ['a fallback spelling', '.p { background: var(--negative, transparent); }', '--negative'],
    // Neither of these is an "error" colour, and a ban list keyed on negative/caution waves
    // both through: a green reassurance tint on a panel that is telling the user something is
    // broken, and a red fill spelled as data ink.
    ['a reassurance tint', '.p { border-color: var(--positive); }', '--positive'],
    ['a red fill by another name', '.p { background: var(--mana-r); }', '--mana-r'],
    // THE CALM-NAMED ALARM (review 2026-07-29): the one token an open `--accent` prefix waved
    // through. It exists, it is documented failing the 3:1 floor on this text, and it is why
    // that entry is exact-match.
    [
      'the dim accent, an alarm with a calm name',
      '.p { color: var(--accent-dim); }',
      '--accent-dim',
    ],
    // And a token that does not exist yet, which is the case no ban list can ever cover.
    [
      'a status token nobody has invented',
      '.p { background: var(--danger-strong); }',
      '--danger-strong',
    ],
  ])('catches %s', (_label, css, token) => {
    const findings = probeCalm(css)
    expect(findings).toHaveLength(1)
    expect(findings[0]).toContain(token)
    // The house rule: the message names the fix — here, that changing it is a UX-DR30 decision.
    expect(findings[0]).toContain('UX-DR30')
  })

  it('leaves a calm stylesheet alone, including the accent the next action needs (silent half)', () => {
    expect(
      probeCalm(
        `.p { background: var(--surface-panel); border: 1px solid var(--border-hairline);
              border-radius: var(--radius-lg); padding: var(--space-5); color: var(--accent);
              font: var(--type-body-strong); font-family: var(--font-mono); }`,
      ),
    ).toEqual([])
  })

  it('says nothing about a stylesheet that never declared itself calm', () => {
    // c4-10's format check MUST spend --negative. The scope is the rule, not a loophole.
    expect(
      findAlarmingTokenInCalmStylesheet(
        ['src/other.css'],
        () => '.x { color: var(--negative); }',
        CALM_FIXTURE,
      ),
    ).toEqual([])
  })

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

  it('catches a --mana-* token in a file that is not data ink (AC 14, half one)', () => {
    const file = 'tests/fixtures/css/token-usage-violation.css'
    const findings = findManaTokenOutsideDataInk([file])

    // ONE finding per FILE, not per reference — the fix is "this file should not touch these
    // tokens", so seven separate messages about one stylesheet would be seven copies of one
    // instruction. The names are still all listed inside it.
    expect(findings).toHaveLength(1)
    expect(findings[0]).toContain('--mana-r')
    expect(findings[0]).toContain('--mana-b')
    // The house rule: the message names its fix, INCLUDING the legitimate route — c4-8 and c4-9
    // must be told how to join rather than left to conclude the tokens are unusable.
    expect(findings[0]).toContain('MANA_DATA_INK')
    expect(findings[0]).toContain('UX-DR7')
  })

  it('leaves the data-ink file and an unrelated file alone (half one, the silent half)', () => {
    // Both directions, because a guard that fired on ManaPip.css would be repaired by deleting
    // the allowlist, and one that never fired at all would be indistinguishable from this.
    expect(findManaTokenOutsideDataInk([MANA_PIP_CSS])).toEqual([])
    expect(findManaTokenOutsideDataInk(['tests/fixtures/css/clean.css'])).toEqual([])
  })

  it('catches a --mana-* spent from MARKUP — SVG fill and the inline-style fallback', () => {
    // The markup half's firing proof, on the two spellings the stylesheet guards cannot see:
    // an SVG `fill` presentation attribute (not an inline style, so not the ESLint ban either)
    // and an inline style carrying the `var(--mana-r, transparent)` fallback this repo has
    // been bitten by three times. ONE finding per file, both token names inside it.
    const findings = findManaTokenInMarkup(['tests/fixtures/markup/mana-var-in-markup.html'])
    expect(findings).toHaveLength(1)
    expect(findings[0]).toContain('--mana-w')
    expect(findings[0]).toContain('--mana-r')
    // The house rule: the message names the legitimate route.
    expect(findings[0]).toContain('MANA_DATA_INK')
    // And the silent half is proven on a REAL markup file that talks ABOUT the tokens at
    // length: ManaPip.tsx's header quotes the mock's runtime-built token name inside a block
    // comment, and prose about the tokens must never read as a spend.
    expect(sourceOf('src/components/ManaPip/ManaPip.tsx')).toContain('--mana-')
    expect(findManaTokenInMarkup(['src/components/ManaPip/ManaPip.tsx'])).toEqual([])
  })

  it('catches a --mana-* spent through chrome, in five spellings it never lists', () => {
    const file = 'tests/fixtures/css/token-usage-violation.css'
    const findings = findManaTokenInChromeProperty(
      blocksIn(file, readFileSync(fixture('css/token-usage-violation.css'), 'utf8')),
    )
    const joined = findings.join('\n')

    // The COUNT is pinned PER FIXTURE FILE, never in aggregate (the house standard): a
    // containment-only assertion would pass a guard regression that also flagged the two legal
    // fill blocks sitting in the same file.
    expect(findings).toHaveLength(5)
    expect(joined).toContain('.mana-token-as-border')
    expect(joined).toContain('.mana-token-as-border-longhand')
    expect(joined).toContain('.mana-token-as-outline')
    expect(joined).toContain('.mana-token-as-shadow')
    expect(joined).toContain('.mana-token-as-text')

    // THE MEMBERS A HAND-WRITTEN BAN WOULD HAVE MISSED, named so a later story cannot quietly
    // convert this allowlist back into a ban list: `outline-color`, `box-shadow` and
    // `border-block-end-color` are not spelled anywhere in the guard.
    expect(joined).toContain('`outline-color`')
    expect(joined).toContain('`box-shadow`')
    expect(joined).toContain('`border-block-end-color`')

    // And the two FILL blocks in the same file are silent — including the gradient, which is
    // the shape the split hybrid pip actually ships.
    expect(joined).not.toContain('.mana-token-as-fill')
    expect(joined).not.toContain('.mana-token-as-gradient-fill')

    for (const finding of findings) {
      expect(finding).toContain('UX-DR7')
      expect(finding).toContain('background')
    }
  })

  it('catches a property the ban list would have to have guessed (the allowlist’s whole point)', () => {
    // Written INLINE rather than in the fixture, deliberately: these four are properties nobody
    // has proposed, which is the only interesting kind. If this guard is ever rewritten as a
    // ban list, this is the test that fails.
    const invented = blocksIn(
      'inline',
      `.a { caret-color: var(--mana-w); }
       .b { text-decoration-color: var(--mana-u); }
       .c { accent-color: var(--mana-b); }
       .d { filter: drop-shadow(0 0 1px var(--mana-r)); }`,
    )
    expect(findManaTokenInChromeProperty(invented)).toHaveLength(4)
  })

  it('catches a missing pip colour class, and a class with no fill (AC 12)', () => {
    const missing = blocksIn(MANA_PIP_CSS, '.mana-pip-w { background: var(--mana-w); }')
    const findings = findUndeclaredPipColourClasses(missing)
    // 21 suffixes, one declared: twenty are reported, and the message says why an undeclared
    // class is worse than a wrong one.
    expect(findings).toHaveLength(20)
    expect(findings[0]).toContain('TRANSPARENT')

    // A class that EXISTS but names no token — the shape a copy-paste that forgot the
    // background produces, which lints clean and renders nothing (c2-7's StatChip-padding
    // lesson, in this component's own currency).
    const hollow = blocksIn(
      MANA_PIP_CSS,
      pipColourSuffixes()
        .map((suffix) =>
          suffix === 'wu'
            ? '.mana-pip-wu { border-radius: var(--radius-pill); }'
            : `.mana-pip-${suffix} { background: var(--mana-w); }`,
        )
        .join('\n'),
    )
    const hollowFindings = findUndeclaredPipColourClasses(hollow)
    expect(hollowFindings).toHaveLength(1)
    expect(hollowFindings[0]).toContain('.mana-pip-wu')
    expect(hollowFindings[0]).toContain('no fill of its own')
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

  // ---- c4-3 AC 12: UX-DR4's two clauses ------------------------------------------------
  //
  // The fixtures are real files rather than inline strings, deliberately: both of these are
  // failures a person will one day WRITE, and a fixture that reads like the stylesheet they
  // would have written documents the mistake in a way a one-line string cannot.

  const CHROME_FIXTURE = 'tests/fixtures/css/card-radius-on-chrome.css'
  const CARD_FIXTURE = 'tests/fixtures/css/chrome-radius-on-card.css'
  const readFixture = (file: string) =>
    readFileSync(fixture(`css/${file.replace('tests/fixtures/css/', '')}`), 'utf8')

  it('catches the card radius borrowed by chrome, in all three spellings (probe (a))', () => {
    const findings = findCardRadiusOutsideCardShape([CHROME_FIXTURE], readFixture, new Map())

    // ONE finding per FILE, not per spelling — the guard is file-scoped like its `--mana-*`
    // sibling — so the assertion is that the message names the token and the file, and the
    // non-vacuity below is what proves all three spellings were actually seen.
    expect(findings).toHaveLength(1)
    expect(findings[0]).toContain(CHROME_FIXTURE)
    expect(findings[0]).toContain('--radius-card')
    // The house rule: the message names the fix, including the way a legitimate card joins.
    expect(findings[0]).toContain('UX-DR4')
    expect(findings[0]).toContain('CARD_SHAPED')

    // THE THREE SPELLINGS, PROVEN INDIVIDUALLY. The fallback form is the one that has escaped
    // three previous guards in this repo, and a longhand is how a PARTIAL borrow arrives.
    for (const spelling of [
      '.panel { border-radius: var(--radius-card); }',
      '.panel { border-radius: var(--radius-card, 10px); }',
      '.panel { border-top-left-radius: var(--radius-card); }',
    ]) {
      expect(
        findCardRadiusOutsideCardShape(['src/probe.css'], () => spelling, new Map()),
      ).toHaveLength(1)
    }
  })

  it('catches a CARD-shaped file rounding itself with chrome (probe (b))', () => {
    const cardShaped = new Map([[CARD_FIXTURE, 'a card-shaped fixture, for the firing half.']])
    const findings = findChromeRadiusInCardShapedFile([CARD_FIXTURE], readFixture, cardShaped)

    expect(findings).toHaveLength(1)
    // All three chrome radii named, which is what proves the NEGATED pattern reads the family
    // rather than a list somebody typed: `--radius-md` is the value the composition reference
    // actually ships for card tiles, and DESIGN.md corrects it by name.
    for (const token of ['--radius-lg', '--radius-pill', '--radius-md']) {
      expect(findings[0]).toContain(token)
    }
    expect(findings[0]).toContain('UX-DR4')

    // AND A RADIUS THAT DOES NOT EXIST YET — the case no ban list can ever cover, and the whole
    // reason the pattern is `--radius-` minus `--radius-card` rather than four names.
    expect(
      findChromeRadiusInCardShapedFile(
        ['src/probe.css'],
        () => '.card-shape { border-radius: var(--radius-xl); }',
        new Map([['src/probe.css', 'a card-shaped probe.']]),
      ),
    ).toHaveLength(1)
  })

  it('leaves the real card-shaped files alone — the SILENT half of both clauses', () => {
    // A guard proven only against violations is half a guard. Half one EXCLUDES allowlisted
    // files by construction, so feeding them back in with the default reader would assert
    // nothing at all — the first draft of this test did exactly that, and the expect was
    // decoration (review finding). Assert the exclusion ITSELF instead: a reader that throws
    // proves half one never even opens an allowlisted file, which is the real claim.
    expect(
      findCardRadiusOutsideCardShape([...CARD_SHAPED.keys()], () => {
        throw new Error('half one read an allowlisted file — its exclusion filter has changed')
      }),
    ).toEqual([])
    // Half two genuinely scans the listed files: the geometry file spends --radius-card and no
    // chrome radius, and the placeholder spends neither because it inherits the shape.
    expect(findChromeRadiusInCardShapedFile([...CARD_SHAPED.keys()])).toEqual([])

    // …and the converse silence, which is the one a too-blunt rule would break: every OTHER
    // stylesheet in the tree spends chrome radii freely, and must go on doing so.
    const chromeSpenders = shippedStylesheets
      .filter((file) => file !== TOKEN_FILE && !CARD_SHAPED.has(file))
      .filter((file) => referencedTokensIn(sourceOf(file)).some(isChromeRadius))
    expect(chromeSpenders.length).toBeGreaterThan(0)
    expect(findCardRadiusOutsideCardShape(chromeSpenders)).toEqual([])
  })

  it('reads code, not the prose about the code (both clauses)', () => {
    // CardPlaceholder.css's header DISCUSSES `border-radius` and names the rule; the geometry
    // file's header discusses the chrome radii by name. A guard that read documentation as code
    // would fire on precisely the files that got it right — and the repair someone would reach
    // for is deleting the explanation. `referencedTokensIn` strips comments first; this is the
    // proof, against the real files.
    const placeholder = sourceOf('src/components/CardPlaceholder/CardPlaceholder.css')
    expect(placeholder).toContain('--radius-md')
    expect(referencedTokensIn(placeholder).filter(isChromeRadius)).toEqual([])
    expect(referencedTokensIn(placeholder).filter(isCardRadius)).toEqual([])
  })

  it('catches --radius-card reached from MARKUP, where no stylesheet guard looks', () => {
    // The half the `--mana-*` rule had to learn in review. The guard takes an injectable reader
    // like its two stylesheet siblings (review finding — the first draft had no seam, so its
    // file-scan wiring was never proven firing), and the firing probe drives the WHOLE function:
    expect(shippedMarkupFiles.length).toBeGreaterThan(10)
    expect(
      findCardRadiusInMarkup(['src/probe.tsx'], () => '<rect rx="var(--radius-card)" />'),
    ).toHaveLength(1)
    expect(referencedTokensIn('<rect rx="var(--radius-card)" />').filter(isCardRadius)).toEqual([
      '--radius-card',
    ])
    // …and the silent half: prose about the token in a .tsx header is not a spend.
    expect(
      referencedTokensIn('/* the shape is var(--radius-card) elsewhere */').filter(isCardRadius),
    ).toEqual([])
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

  /**
   * A TRANSFORM IS NOT NEUTRALISED BY A ZEROED DURATION, AND UNTIL c4-4 NOTHING CHECKED THAT.
   *
   * Found by c4-4's probe (e), which deleted the scale fallback from the registration block and
   * left the WHOLE SUITE GREEN. The four duration assertions above prove the MECHANISM works;
   * they say nothing about the motions the mechanism cannot reach — and the block's own
   * instruction is exactly about those: *"any motion that cannot be switched off by a duration
   * alone — a transform, a 3D rotation, a crossfade — adds its own declaration HERE, in this
   * block, in the story that builds it. A motion with no registered fallback is an incomplete
   * story."* That was prose with no gate behind it, in a codebase whose standing review finding
   * is that a rule with no consumer is indistinguishable from a rule nobody obeys.
   *
   * Zeroing `--motion-glide` makes `transform: scale(1.06)` INSTANT, not ABSENT: the tile still
   * jumps 6% larger the moment a pointer crosses it, which is precisely the vestibular motion
   * UX-DR42 asks to remove, arriving faster. So the rule is DERIVED rather than listed: any
   * shipped block that declares a transform must have its selector neutralised in the block
   * above. Nobody writes "the card tile" here — c4-6's 3D flip and c6-5's bloom are covered the
   * day they are written.
   *
   * ==== THE LIMIT, STATED (and it is the safe direction) ================================
   * Selectors are compared as NORMALISED TEXT, not resolved against the DOM. A transform on
   * `.card-tile:hover .card-tile-art` neutralised by a rule on `.card-tile:hover` would be
   * reported as unregistered even though the cascade would in fact switch it off. That is a
   * FALSE FAILURE, not a false pass — the author reads this comment and writes the matching
   * selector, which is the outcome the rule wants anyway. Resolving it properly needs
   * specificity and the runtime class list, which is `ui/README.md`'s cascade blind spot.
   *
   * ==== TWO HOLES CLOSED BY REVIEW (2026-08-04), both false-PASS directions ============
   * One: the first spelling read values through `declarationsIn`, which strips `!important` —
   * so a registration of `transform: none` WITHOUT it was accepted, and tokens.css's own
   * comment measures exactly that spelling as a cascade no-op (identical specificity, imported
   * first: it would parse cleanly and do nothing). A neutralisation only counts here if the
   * RAW declaration carries `!important`. Two: the first spelling matched only the `transform`
   * property, and `scale: 1.06` — the idiomatic modern form of this very story's hover pop —
   * is the same vestibular motion in another spelling, as are `rotate:` and `translate:`. All
   * four are covered, PER PROPERTY: `transform: none` does not reset an individual `scale:`,
   * so a motion is only registered when the SAME property is `none !important` on the SAME
   * selector.
   */
  const normaliseSelector = (selector: string) => selector.replace(/\s+/g, ' ').trim()

  const MOTION_PROPERTIES: readonly string[] = ['transform', 'scale', 'rotate', 'translate']

  /** Every motion declaration in `blocks`, as `'selector :: property'` pairs. */
  const motionDeclarationsIn = (blocks: Block[]): string[] =>
    blocks.flatMap((block) =>
      declarationsIn(block.body)
        .filter(
          ([property, value]) =>
            MOTION_PROPERTIES.includes(property) && normaliseSelector(value) !== 'none',
        )
        .flatMap(([property]) =>
          block.selector.split(',').map((s) => `${normaliseSelector(s)} :: ${property}`),
        ),
    )

  /**
   * Every `<motion-property>: none !important` in `blocks`, as `'selector :: property'` pairs —
   * read RAW, not through `declarationsIn`, because `!important` is load-bearing here and that
   * helper strips it.
   */
  const importantNoneNeutralisationsIn = (blocks: Block[]): string[] =>
    blocks.flatMap((block) =>
      block.body
        .split(';')
        .map((decl) => {
          const colon = decl.indexOf(':')
          if (colon === -1) return null
          return [
            decl.slice(0, colon).trim().toLowerCase(),
            decl
              .slice(colon + 1)
              .trim()
              .replace(/\s+/g, ' '),
          ] as [string, string]
        })
        .filter((decl): decl is [string, string] => decl !== null)
        .filter(
          ([property, value]) =>
            MOTION_PROPERTIES.includes(property) && /^none !important$/i.test(value),
        )
        .flatMap(([property]) =>
          block.selector.split(',').map((s) => `${normaliseSelector(s)} :: ${property}`),
        ),
    )

  it('neutralises every TRANSFORM in the tree, not merely every duration (c4-4, AC 18)', () => {
    const neutralised = new Set(importantNoneNeutralisationsIn(blocksIn(TOKEN_FILE, reduced!)))
    const moving = [...new Set(motionDeclarationsIn(shippedBlocks))]

    // NON-VACUITY, and it is load-bearing here more than anywhere: this guard asserts that a
    // list is empty, so a tree with no transforms in it at all — which is what every commit
    // before c4-4 looked like — passes it while checking nothing. The day the last transform is
    // deleted, this line is what says the guard has stopped having a subject.
    expect(
      moving.length,
      'no stylesheet declares a transform — this guard has no subject',
    ).toBeGreaterThan(0)
    // Comma-split, so a selector LIST is checked part by part: a rule that neutralised the hover
    // and forgot the focus would be caught, which is the half a whole-selector comparison would
    // have waved through. THIS PIN IS ENUMERATED: the derived rule below needs no edit for a new
    // motion, but this list does — a story that adds or removes a transform moves it, on
    // purpose, the way the token pins move.
    expect(
      moving,
      'the shipped-motion list moved — the story that added or removed a motion updates this pin',
      //
      // MOVED BY c4-6, AND ALL FOUR ENTRIES ARE THAT STORY'S (2026-08-05). Two are the hover pop
      // RE-HOMED rather than added: the flip control had to become a sibling of the tile's
      // `<button>` instead of a descendant, so the pop moved from `.card-tile:hover` onto the
      // `.card-tile-frame` that now holds both — same box, different element, and this pin is what
      // made forgetting to move the registration impossible. The other two are the flip itself: the
      // stacked-faces box turns 180°, and the back face carries a STATIC 180° so it reads the right
      // way round once it has. That static one is the entry a property-keyed guard catches and an
      // animation-keyed one would not — and it genuinely needs the fallback, because with both
      // rotations gone `backface-visibility` has nothing to decide from and the back face would
      // cover the front at every setting. See tokens.css for the two `visibility` rules that
      // replace it.
    ).toEqual([
      //
      // MOVED BY c6-5 (2026-08-10), AND THE FIFTH ENTRY IS EPIC 6's FIRST. The agent view enters
      // as a fade plus an 8px rise (`DESIGN.md:471`), and only the rise appears here: the fade is
      // expressed entirely through `--motion-bloom`, so zeroing that token already makes it
      // instant and it is MECHANICAL in c4-4's sense. The rise is a transform, which a zeroed
      // duration makes instant rather than absent, so it earns a registration in tokens.css and
      // therefore an entry here.
      //
      // The selector is the STATE ATTRIBUTE rather than `.agent-view`, and that is this guard's
      // own reader deciding the implementation rather than the other way round: a `@keyframes`
      // bloom would present to `blocksIn` as two rules named `from` and `to`, and the
      // registration that would then be demanded — `from { transform: none !important }` — is
      // ignored inside keyframes by specification, so the gate would have forced an override
      // that parses cleanly and does nothing. A transition out of `[data-entering='true']` is
      // the shape that can be honestly registered. Both files record the reasoning at the rule.
      ".agent-view[data-entering='true'] :: transform",
      '.card-tile-frame:hover :: transform',
      // `:has(:focus-visible)`, frame-wide, since review 2026-08-06: the first spelling read
      // `:has(.card-tile:focus-visible)`, which dropped the pop the moment a keyboard reader
      // Tabbed from the tile onto its OWN flip control — the mirror image of the pointer defect
      // the frame was built to repair. The registration moved with the selector, as this pin
      // exists to force.
      '.card-tile-frame:has(:focus-visible) :: transform',
      ".card-faces[data-flipped='true'] :: transform",
      '.card-face.is-back :: transform',
    ])

    expect(moving.filter((entry) => !neutralised.has(entry))).toEqual([])
  })

  it('would catch a transform with no registered fallback — probe (e), the firing half', () => {
    // Fed inline rather than by deleting the real rule, so the proof survives the repair. This
    // is the exact shape the probe planted: a scale that the duration zeroing makes instant
    // rather than absent, with nothing in the registration block naming it.
    const planted = blocksIn('src/probe.css', '.probe:hover { transform: scale(1.06); }')
    const neutralised = new Set(importantNoneNeutralisationsIn(blocksIn(TOKEN_FILE, reduced!)))

    expect(motionDeclarationsIn(planted)).toEqual(['.probe:hover :: transform'])
    expect(motionDeclarationsIn(planted).filter((e) => !neutralised.has(e))).toHaveLength(1)

    // A registration WITHOUT `!important` is refused (review 2026-08-04 — the hole the first
    // spelling shipped). tokens.css's own comment measures that spelling as a cascade no-op, so
    // accepting it here would be an accessibility gate passing on broken code.
    expect(
      importantNoneNeutralisationsIn(blocksIn(TOKEN_FILE, '.probe:hover { transform: none; }')),
    ).toEqual([])

    // The INDIVIDUAL properties are the same motion in another spelling (review 2026-08-04):
    // `scale: 1.06` is the idiomatic modern form of this story's own hover pop — and a
    // `transform: none` registration does NOT reset it, so per-property matching is what keeps
    // the registered set honest.
    const scaled = blocksIn('src/probe.css', '.probe:hover { scale: 1.06; }')
    expect(motionDeclarationsIn(scaled)).toEqual(['.probe:hover :: scale'])
    const transformOnly = new Set(
      importantNoneNeutralisationsIn(
        blocksIn(TOKEN_FILE, '.probe:hover { transform: none !important; }'),
      ),
    )
    expect(motionDeclarationsIn(scaled).filter((e) => !transformOnly.has(e))).toHaveLength(1)

    // …and the silent halves: each rule WITH its matching fallback registered is accepted.
    const registered = new Set([
      ...neutralised,
      ...importantNoneNeutralisationsIn(
        blocksIn(TOKEN_FILE, '.probe:hover { transform: none !important; }'),
      ),
    ])
    expect(motionDeclarationsIn(planted).filter((e) => !registered.has(e))).toEqual([])
    const scaleRegistered = new Set(
      importantNoneNeutralisationsIn(
        blocksIn(TOKEN_FILE, '.probe:hover { scale: none !important; }'),
      ),
    )
    expect(motionDeclarationsIn(scaled).filter((e) => !scaleRegistered.has(e))).toEqual([])
  })

  /**
   * THE CLASS THE TRANSFORM PIN CANNOT SEE (SC-5 gate finding M5, 2026-08-20). The pin above
   * covers transform/scale/rotate/translate only — blind by construction to `opacity`,
   * `height`, `background-color` and `box-shadow` transitions, which is the exact class three
   * shipped motions (flip-control fade, suggestion-row tint, suggestion thumbnail fade)
   * slipped through on a fully green suite. These need no `none !important` registration —
   * every one is expressed through a duration token, so zeroing makes it instant — but
   * UX-DR42 declares the INVENTORY exhaustive, and that is a separate obligation this guard
   * now enforces: every shipped visual-class transition must be claimed by a named inventory
   * row in tokens.css. `all` is tracked too, because `transition: all` would smuggle the
   * whole class in one word.
   */
  const VISUAL_TRANSITION_PROPERTIES: readonly string[] = [
    'opacity',
    'height',
    'background-color',
    'box-shadow',
  ]

  /** Comma-split at depth 0 only, so `var(--motion-glide, 200ms)` stays one segment. */
  const transitionSegmentsIn = (value: string): string[] => {
    const segments: string[] = []
    let depth = 0
    let current = ''
    for (const char of value) {
      if (char === '(') depth++
      if (char === ')') depth--
      if (char === ',' && depth === 0) {
        segments.push(current)
        current = ''
      } else {
        current += char
      }
    }
    segments.push(current)
    return segments.map((s) => s.trim()).filter(Boolean)
  }

  /** Whitespace-split at depth 0 only, so `cubic-bezier(0.4, 0, 0.2, 1)` stays one word. */
  const wordsAtDepthZero = (segment: string): string[] => {
    const words: string[] = []
    let depth = 0
    let current = ''
    for (const char of segment) {
      if (char === '(') depth++
      if (char === ')') depth--
      if (/\s/.test(char) && depth === 0) {
        if (current) words.push(current)
        current = ''
      } else {
        current += char
      }
    }
    if (current) words.push(current)
    return words
  }

  /**
   * The transitioned property of one shorthand segment. The shorthand grammar is ORDER-FREE
   * (`||` combinator — Greptile P2, PR #90): `transition: var(--motion-glide) opacity` is as
   * valid as the property-first spelling, and a segment with NO property token at all means
   * the implicit `all`. So the property is found by elimination — not by position: drop
   * functions (var(), cubic-bezier(), steps()), times, easing keywords and `none`; the first
   * survivor is the property; no survivor is `all`.
   */
  const TRANSITION_EASINGS = new Set([
    'ease',
    'ease-in',
    'ease-out',
    'ease-in-out',
    'linear',
    'step-start',
    'step-end',
  ])
  const transitionPropertyOf = (segment: string): string => {
    const survivors = wordsAtDepthZero(segment).filter((word) => {
      const lower = word.toLowerCase()
      if (lower.includes('(')) return false
      if (/^[+-]?(\d+\.?\d*|\.\d+)(ms|s)$/.test(lower)) return false
      if (TRANSITION_EASINGS.has(lower)) return false
      // `none` is NOT filtered: the grammar puts it in the PROPERTY slot, so it must survive
      // as the resolved property — `transition: none` means "nothing transitions", and a
      // resolver that dropped the word would misread it as the implicit `all`. (Found live:
      // QuantityBadge.css's flashed rule is exactly `transition: none`.)
      return true
    })
    return survivors[0]?.toLowerCase() ?? 'all'
  }

  /** Every visual-class transition in `blocks`, as `'selector :: property'` pairs. */
  const visualTransitionDeclarationsIn = (blocks: Block[]): string[] =>
    blocks.flatMap((block) =>
      declarationsIn(block.body)
        .filter(([property]) => property === 'transition' || property === 'transition-property')
        .flatMap(([name, value]) =>
          transitionSegmentsIn(value)
            .map((segment) =>
              // `transition-property` segments ARE property names; the shorthand needs the
              // order-free resolver.
              name === 'transition-property'
                ? segment.toLowerCase()
                : transitionPropertyOf(segment),
            )
            .filter(
              (property) => property === 'all' || VISUAL_TRANSITION_PROPERTIES.includes(property),
            )
            .flatMap((property) =>
              block.selector.split(',').map((s) => `${normaliseSelector(s)} :: ${property}`),
            ),
        ),
    )

  it('keys every visual-class transition to an inventory row (SC-5 gate, M5)', () => {
    const found = [...new Set(visualTransitionDeclarationsIn(shippedBlocks))]

    // NON-VACUITY: this guard maps a list to rows, so an empty list checks nothing. Thirteen
    // entries shipped the day it was written; zero means the reader broke, not the tree.
    expect(
      found.length,
      'no stylesheet ships a visual-class transition — this guard has no subject',
    ).toBeGreaterThan(0)

    // THIS MAP IS ENUMERATED, like the transform pin above: a story that adds or removes a
    // visual-class transition moves it on purpose — and a NEW entry owes an inventory row in
    // tokens.css before it can be claimed here. The two rows read as classes carry the SC-5
    // gate ruling (Brad, 2026-08-20): "Image fade-in" covers image fades as a family,
    // "Deck-row live tint" covers the row tint+shadow family, per the no-new-row ruling
    // recorded at SuggestionsView.css:113-118 and c6-7.
    const INVENTORY_CLAIMS: Record<string, string> = {
      '.app-shell-identity :: opacity': 'Refetch header shimmer',
      '.agent-view :: opacity': 'Agent-view bloom',
      '.agent-view-title :: opacity': 'Push-replace crossfade',
      '.agent-view-body :: opacity': 'Push-replace crossfade',
      '.card-tile-image :: opacity': 'Image fade-in',
      '.suggestion-row-image :: opacity': 'Image fade-in',
      '.card-tile-quantity :: box-shadow': 'Accent glow fade',
      '.deck-row :: background-color': 'Deck-row live tint',
      '.deck-row :: box-shadow': 'Deck-row live tint',
      '.suggestion-row :: background-color': 'Deck-row live tint',
      '.suggestion-row :: box-shadow': 'Deck-row live tint',
      '.flip-control :: opacity': 'Flip-control chrome fade',
      '.mana-curve-bar :: height': 'Curve-bar height',
    }

    expect(
      [...found].sort(),
      'the shipped visual-transition list moved — the story that moved it updates this map, and a new entry owes an inventory row first',
    ).toEqual(Object.keys(INVENTORY_CLAIMS).sort())

    // A ROW, not a mention (Greptile P2, PR #90): two labels also appear in the
    // rows-read-as-classes prose note, so a bare substring search would stay green with the
    // actual row deleted. Every inventory row is `Label -> fallback`, arrow on the label's own
    // line, and prose never quotes a label with its arrow — so the arrow is what makes the
    // match a row.
    const escapeForRegex = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    for (const [entry, row] of Object.entries(INVENTORY_CLAIMS)) {
      expect(
        new RegExp(`${escapeForRegex(row)}[^\\n]*->`).test(tokenFileSource),
        `${entry} claims inventory row "${row}", which tokens.css no longer carries as a row (label + '->' on one line)`,
      ).toBe(true)
    }
  })

  it('would catch a visual-class transition the map does not claim — the M5 probe', () => {
    // Fed inline, like probe (e) above, so the proof survives the repair.
    const planted = blocksIn(
      'src/probe.css',
      '.probe:hover { transition: opacity var(--motion-glide) ease, background-color 200ms; }',
    )
    expect(visualTransitionDeclarationsIn(planted)).toEqual([
      '.probe:hover :: opacity',
      '.probe:hover :: background-color',
    ])

    // The ORDER-FREE spellings Greptile named (P2, PR #90): property after the duration, and
    // the implicit-`all` segment with no property token at all. Both must resolve, not vanish.
    expect(
      visualTransitionDeclarationsIn(
        blocksIn('src/probe.css', '.probe { transition: var(--motion-glide) opacity; }'),
      ),
    ).toEqual(['.probe :: opacity'])
    expect(
      visualTransitionDeclarationsIn(
        blocksIn('src/probe.css', '.probe { transition: var(--motion-glide); }'),
      ),
    ).toEqual(['.probe :: all'])
    // `transition: none` is the PROPERTY `none` — no transition — never the implicit `all`.
    // The shipped shape that proves it matters: QuantityBadge.css's flashed rule.
    expect(
      visualTransitionDeclarationsIn(blocksIn('src/probe.css', '.probe { transition: none; }')),
    ).toEqual([])

    // A cubic-bezier's inner spaces do not shed words the resolver would mistake for a property.
    expect(
      visualTransitionDeclarationsIn(
        blocksIn(
          'src/probe.css',
          '.probe { transition: opacity 200ms cubic-bezier(0.4, 0, 0.2, 1); }',
        ),
      ),
    ).toEqual(['.probe :: opacity'])

    // `transition: all` cannot smuggle the class past the reader in one word.
    expect(
      visualTransitionDeclarationsIn(
        blocksIn('src/probe.css', '.probe { transition: all var(--motion-glide); }'),
      ),
    ).toEqual(['.probe :: all'])

    // A comma inside var() does not split a segment (the reader is paren-aware).
    expect(
      visualTransitionDeclarationsIn(
        blocksIn(
          'src/probe.css',
          '.probe { transition: opacity var(--motion-glide, 200ms) ease; }',
        ),
      ),
    ).toEqual(['.probe :: opacity'])

    // Non-class transitions stay invisible to THIS guard — color/outline are not motion the
    // inventory tracks, and the transform family belongs to the pin above.
    expect(
      visualTransitionDeclarationsIn(
        blocksIn('src/probe.css', '.probe { transition: color var(--motion-glide); }'),
      ),
    ).toEqual([])
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
