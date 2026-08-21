/**
 * The lint gate proves itself, in both directions.
 *
 * Every rule this story adds is shown FIRING and NOT FIRING from the same invocation
 * (the standing non-vacuity pairing agreement, promoted at the C1 retro). A test that
 * only shows a violation cannot distinguish "the rule fired" from "the config errors on
 * every file it is handed" — which is exactly how a lint gate rots without anyone noticing.
 *
 * IF THE FIRST TEST BELOW TIMES OUT, THAT IS THE COLD START, NOT A BUG. `eslint.config.js` sets
 * `projectService: true`, so the first ESLint call in the process builds a TypeScript program
 * before it lints a line; whichever ESLint test runs first pays all of it and the rest are
 * milliseconds. Eight sightings across C6 and C7 before the timeout was raised — see
 * `vite.config.ts`, the `node` project's `testTimeout`, which carries the measurements.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { ESLint } from 'eslint'
import stylelint from 'stylelint'
import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))
const fixture = (rel: string) => fileURLToPath(new URL(`fixtures/${rel}`, import.meta.url))

const A11Y_STATIC = 'jsx-a11y/no-static-element-interactions'
const A11Y_NONINTERACTIVE = 'jsx-a11y/no-noninteractive-element-interactions'

// The UX-DR46 outline ban (c2-1) and the AC 12 looping-animation ban (c2-4) are both keyed
// on property/value pairs, so they share one stylelint rule name. That is exactly why the
// counts below are asserted per FIXTURE FILE and never in aggregate: `violation.css` still
// reports ten and only ten, and the motion fixture is a separate file so it cannot inflate
// an assertion that has stood since c2-1.
const DISALLOWED_RULE = 'declaration-property-value-disallowed-list'
const ALLOWED_RULE = 'declaration-property-value-allowed-list'

/**
 * Just enough of .stylelintrc.json's shape for the override-drift assertion to be typed.
 * Property key -> the allowed value patterns for it, plus the `{ message }` object — the
 * override carries the same `[map, { message }]` tuple as the base rule, so a violation
 * inside fonts.css reports the token-family guidance rather than stylelint's default text.
 */
type AllowedList = Record<string, string[]>
interface StylelintConfig {
  rules: { [ALLOWED_RULE]: [AllowedList, { message: string }] }
  overrides: {
    files: string[]
    rules: Partial<Record<string, [AllowedList, { message: string }]>>
  }[]
}
const INLINE_STYLE_RULE = 'no-restricted-syntax'
const HEX_RULE = 'color-no-hex'
const NAMED_COLOUR_RULE = 'color-named'
const COLOUR_FN_RULE = 'function-disallowed-list'

describe('eslint accessibility gate (UX-DR47, AC 8)', () => {
  // One ESLint instance, one lintFiles() call, both fixtures — so the acceptance and the
  // rejection genuinely come from the same run and the same config.
  // `ignore: false` is required: eslint.config.js ignores tests/fixtures/** so that
  // `npm run lint` stays green, and these files exist only to be linted here.
  const lintBothFixtures = async () => {
    const eslint = new ESLint({ cwd: uiRoot, ignore: false })
    const results = await eslint.lintFiles([
      fixture('a11y/violation.tsx'),
      fixture('a11y/clean.tsx'),
    ])
    const byFile = (name: string) => results.find((r) => r.filePath.endsWith(name))
    return {
      violation: byFile('violation.tsx'),
      clean: byFile('clean.tsx'),
    }
  }

  it('reports a click handler on a non-interactive element', async () => {
    const { violation } = await lintBothFixtures()

    expect(violation).toBeDefined()
    const ruleIds = violation!.messages.map((m) => m.ruleId)
    expect(ruleIds).toContain(A11Y_STATIC)
    expect(ruleIds).toContain(A11Y_NONINTERACTIVE)

    // `error`, not `warn` — a warning does not gate a build. severity 2 === error.
    const a11ySeverities = violation!.messages
      .filter((m) => m.ruleId === A11Y_STATIC || m.ruleId === A11Y_NONINTERACTIVE)
      .map((m) => m.severity)
    expect(a11ySeverities.length).toBeGreaterThan(0)
    expect(new Set(a11ySeverities)).toEqual(new Set([2]))
  })

  it('leaves a real <button> alone in the same invocation', async () => {
    const { clean } = await lintBothFixtures()

    expect(clean).toBeDefined()
    // The whole point of the pair: this file goes through the identical config and the a11y
    // gate stays silent. Filtered to the two gate rules — mirroring the violation half — so
    // an unrelated future rule (a c2-4 config change, a typescript-eslint minor growing
    // recommendedTypeChecked) cannot fail a test named after the accessibility gate.
    const a11yMessages = clean!.messages.filter(
      (m) => m.ruleId === A11Y_STATIC || m.ruleId === A11Y_NONINTERACTIVE,
    )
    expect(a11yMessages).toEqual([])
  })

  it('narrows the handler list to INTERACTIONS, and the narrowing is exactly two names (c4-4)', async () => {
    // c4-4 removed `onError` and `onLoad` from both rules' handler lists, in the open, because
    // neither is an interaction: they are resource-lifecycle events with no user in the causal
    // chain, no keyboard equivalent to add and no role to promote. `clean.tsx` now carries an
    // `<img onLoad onError>` — the shape c4-4's card tile needs to know whether a picture
    // arrived — and the silence assertion above is what proves the narrowing works.
    //
    // THIS test is the drift half: it reads the RESOLVED config rather than the file, so a
    // future story that restores the defaults, drops the option, or quietly shortens the list
    // past the six interaction handlers goes red HERE, naming the rule.
    const eslint = new ESLint({ cwd: uiRoot, ignore: false })
    const config = (await eslint.calculateConfigForFile(fixture('a11y/clean.tsx'))) as {
      rules: Record<string, unknown[]>
    }

    for (const rule of [A11Y_STATIC, A11Y_NONINTERACTIVE]) {
      const entry = config.rules[rule]
      expect(entry, `${rule} is not configured at all`).toBeDefined()
      const options = entry[1] as { handlers?: string[] } | undefined
      expect(options?.handlers, `${rule} lost its explicit handler list`).toEqual([
        'onClick',
        'onMouseDown',
        'onMouseUp',
        'onKeyPress',
        'onKeyDown',
        'onKeyUp',
      ])
      // The two that were removed, named — so the diff that puts either back is visible here
      // rather than only in a component that stops linting.
      expect(options?.handlers).not.toContain('onLoad')
      expect(options?.handlers).not.toContain('onError')
    }
  })
})

describe('eslint inline-style ban (story c2-4 review ruling)', () => {
  // Every gate the token layer ships stops at *.css. `style={{ padding: '18px' }}` in a .tsx
  // file is invisible to all of them — so the ban lives in ESLint, and is proven here in the
  // same both-ways shape as the a11y gate above.
  const lintBothFixtures = async () => {
    const eslint = new ESLint({ cwd: uiRoot, ignore: false })
    const results = await eslint.lintFiles([
      fixture('tsx/inline-style-violation.tsx'),
      fixture('tsx/clean.tsx'),
    ])
    expect(results, 'eslint linted the wrong number of fixtures').toHaveLength(2)
    const byFile = (name: string) => results.find((r) => r.filePath.endsWith(name))
    return { violation: byFile('inline-style-violation.tsx'), clean: byFile('clean.tsx') }
  }

  it('reports every inline style attribute, and names the fix', async () => {
    const { violation } = await lintBothFixtures()

    expect(violation).toBeDefined()
    const inlineStyle = violation!.messages.filter((m) => m.ruleId === INLINE_STYLE_RULE)

    // Two components in the fixture, one `style` attribute each — including the "one innocent
    // property" case, because the precedent is the hole, not the value.
    expect(inlineStyle).toHaveLength(2)
    expect(new Set(inlineStyle.map((m) => m.severity))).toEqual(new Set([2]))
    for (const message of inlineStyle) {
      expect(message.message).toContain('bypasses the whole token layer')
      expect(message.message).toContain('var(--')
    }
  })

  it('leaves class-based styling alone in the same invocation', async () => {
    const { clean } = await lintBothFixtures()

    expect(clean).toBeDefined()
    // Filtered to the rule under test, mirroring the a11y pair: an unrelated future rule must
    // not be able to fail a test named after the inline-style ban.
    expect(clean!.messages.filter((m) => m.ruleId === INLINE_STYLE_RULE)).toEqual([])
  })

  it('admits a custom-property-only style, and STILL reports a plain one (c4-8, AC 17)', async () => {
    // THE AMENDMENT'S OWN GATE. `eslint.config.js`'s own comment reserved a custom-property
    // escape hatch for "a computed bar height in c4-8" on the explicit condition that the story
    // needing it CHANGE THE RULE AND SAY WHY, IN THE OPEN. c4-8 took it; this is the pair that
    // proves the narrowing narrowed rather than loosened.
    //
    // The silent half is `clean.tsx`'s `CustomPropertyStyled`, covered by the zero-messages
    // assertion above — which is the honest place for it, and is why that assertion is the one
    // that would fail if the hatch were ever written wider than it is.
    //
    // The firing half is here, from source rather than from a fixture, because each case is one
    // line and putting five near-identical components in `inline-style-violation.tsx` would
    // move the `toHaveLength(2)` pin three stories old.
    // A REAL FILE ON DISK, not `lintText` against a virtual path: `projectService: true` makes
    // every linted `.ts`/`.tsx` belong to a tsconfig, and a path that is not on disk comes back
    // as a FATAL parsing error with `ruleId: null` — which a filter on this rule's id reads as
    // silence. Measured while writing this test: the first draft asserted five firing cases and
    // saw zero messages for all five, and the reason was the parser, not the selector. A gate
    // that cannot tell "the rule did not fire" from "the file was never parsed" is the vacuity
    // failure this whole file exists to close.
    const eslint = new ESLint({ cwd: uiRoot, ignore: false })
    const [result] = await eslint.lintFiles([fixture('tsx/custom-property-violation.tsx')])

    // NON-VACUITY FIRST: no fatal message, so the fixture genuinely parsed.
    expect(
      result.messages.filter((m) => m.fatal),
      'the fixture did not parse — every count below would be vacuous',
    ).toEqual([])

    const firing = result.messages.filter((m) => m.ruleId === INLINE_STYLE_RULE)

    // (n) TEN attributes, ten messages — one per ATTRIBUTE, which is the property that keeps
    // `inline-style-violation.tsx` at 2. The five from implementation (a plain property, an
    // on-scale one, a MIXED object, a non-literal, and a spread) plus the four the review
    // added: a call and a ternary WRAPPING a compliant literal (the descendant-`:has` evasion
    // — "contains a literal" is not "is a literal"), a REAL design token as the key (the
    // prefix-test hole: `--surface-well` inline re-themes every descendant), and a
    // right-prefix wrong-name channel (`--curve-bar-index` is not on the allowlist).
    //
    // The tenth joined at c4-9, when the allowlist grew from one name to two: the NEW channel
    // beside a plain `width`. It is the `MixedProperties` argument restated against the second
    // entry, because a second entry is exactly when someone re-tests whether the negation still
    // applies per-property — and it is enumerated probe (r), which asks that a plain
    // `style={{ width: … }}` still error after the amendment.
    expect(firing).toHaveLength(10)
    expect(new Set(firing.map((m) => m.severity))).toEqual(new Set([2]))
    for (const message of firing) {
      expect(message.message).toContain('bypasses the whole token layer')
      expect(message.message).toContain('var(--')
    }

    // Each case resolved back through its own line, because a count of nine would also pass if
    // one selector fired nine times and the other never fired at all.
    const source = readFileSync(fixture('tsx/custom-property-violation.tsx'), 'utf8').split('\n')
    const flagged = firing.map((m) => (source[m.line - 1] ?? '').trim())
    for (const declaration of [
      "return <div style={{ height: '62%' }} />",
      "return <span style={{ marginTop: '4px' }} />",
      "return <div style={{ '--bar-height': '62%', color: 'red' } as React.CSSProperties} />",
      'return <div style={someObject} />',
      "return <div style={{ ...someObject, '--bar-height': '62%' } as React.CSSProperties} />",
      "return <div style={identity({ '--curve-bar-height': '62%' })} />",
      "<div style={tall ? ({ '--curve-bar-height': '100%' } as React.CSSProperties) : someObject} />",
      "return <div style={{ '--surface-well': colour } as React.CSSProperties} />",
      "return <div style={{ '--curve-bar-index': share } as React.CSSProperties} />",
      "return <div style={{ '--colour-bar-share': share, width: '62%' } as React.CSSProperties} />",
    ]) {
      expect(
        flagged.some((line) => line === declaration),
        `the narrowed rule no longer fires on \`${declaration}\``,
      ).toBe(true)
    }
  })
})

describe('stylelint focus-ring gate (UX-DR46, AC 9)', () => {
  const lintCss = async (file: string) => {
    const result = await stylelint.lint({
      files: [fixture(file)],
      configFile: fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)),
    })

    // Without this, a moved or renamed fixture makes `results[0]` undefined and the failure
    // reads as a TypeError deep in an expectation rather than "the fixture was never linted"
    // — which is the same vacuous-gate trap this whole file exists to close.
    expect(
      result.results,
      `stylelint linted no file for ${file} — the fixture is missing or was ignored`,
    ).toHaveLength(1)

    return result
  }

  it('reports every spelling of a removed focus ring, replacement or not', async () => {
    const result = await lintCss('css/violation.css')

    expect(result.errored).toBe(true)
    const outlineWarnings = result.results[0].warnings.filter((w) => w.rule === DISALLOWED_RULE)

    // Ten banned declarations in the fixture, four axes of evasion. The six spellings of the
    // original ruling: `outline: none`, `outline: 0`, `outline: 0px`, `outline-style: none`,
    // `outline-width: 0`, `outline-width: 0px` — a ban on only the two literal spellings is
    // one a search-and-replace walks straight around. Plus the round-2 widening (Brad's
    // ruling: widen fully): `outline: NONE` (values match case-insensitively now; the
    // uppercase-PROPERTY variant cannot even reach stylelint — Prettier lowercases CSS
    // property names, proven when it rewrote this very fixture, and the config's
    // `/^outline$/i` keys cover it as defense in depth), `outline: 1px none` and
    // `outline: 0 solid` (multi-token shorthands escape `^…$`-anchored value regexes), and
    // `outline-color: transparent` (a ring nobody can see is a ring removed).
    expect(outlineWarnings).toHaveLength(10)
    expect(new Set(outlineWarnings.map((w) => w.severity))).toEqual(new Set(['error']))

    // And the :focus-visible replacement in the same file bought no exemption.
    expect(result.results[0].source).toContain('violation.css')
  })

  it('leaves a stylesheet with no outline declaration alone', async () => {
    const result = await lintCss('css/clean.css')

    expect(result.errored).toBeFalsy()
    // Deliberately UNFILTERED. This is the assertion that makes clean.css the file which has
    // to satisfy every gate at once — which is why story c2-4 tokenised its `padding: 4px`
    // rather than loosen the new spacing rule or filter this line. If a rule ever fires on
    // everything it is handed, this is where it is caught.
    expect(result.results[0].warnings).toEqual([])
  })
})

describe('stylelint literal bans (UX-DR1, UX-DR5, story c2-4 AC 4/5/7)', () => {
  // Read once, so a warning's line number can be resolved back to the declaration that
  // caused it. Split on \n only: ui/.gitattributes forces LF over all of ui/.
  const literalsSource = readFileSync(fixture('css/literals-violation.css'), 'utf8').split('\n')

  // ONE invocation, ONE config, all four fixtures — so every "it fired" and every "it stayed
  // silent" below genuinely comes from the same run. Splitting them into separate lint()
  // calls would let a config that errors on every file masquerade as four working rules.
  const lintAll = async () => {
    const files = [
      'clean',
      'violation',
      'literals-violation',
      'motion-violation',
      'typography-violation',
    ].map((n) => fixture(`css/${n}.css`))
    const result = await stylelint.lint({
      files,
      configFile: fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)),
    })

    // The non-vacuity anchor for the whole block: five fixtures in, five results out. A
    // moved or ignored fixture would otherwise make every count assertion below read
    // `undefined` warnings and fail confusingly, or — worse for the clean half — pass.
    expect(result.results, 'stylelint did not lint all five fixtures').toHaveLength(5)

    const by = (name: string) => {
      const found = result.results.find((r) => r.source?.endsWith(`${name}.css`))
      expect(found, `no stylelint result for ${name}.css`).toBeDefined()
      return found!.warnings
    }
    const countOf = (name: string, rule: string) => by(name).filter((w) => w.rule === rule).length

    return { by, countOf }
  }

  it('fails a hard-coded hex, a named colour and every colour function', async () => {
    const { countOf, by } = await lintAll()

    expect(countOf('literals-violation', HEX_RULE)).toBe(1)
    // A named colour evades both the hex ban and the function ban, so it gets its own rule.
    expect(countOf('literals-violation', NAMED_COLOUR_RULE)).toBe(1)
    // rgb(), hsl(), oklch(), the rgb() inside the hard-coded box-shadow and the one inside
    // text-shadow, plus drop-shadow() and the rgb() nested inside IT — seven. The modern
    // colour spaces are banned alongside the legacy ones: reaching for oklch() is no less
    // hard-coding a colour, and a list naming only rgb/hsl is a list that gets walked around.
    // `drop-shadow` joined this rule at review: it paints shadow geometry that the shadowless
    // themes cannot switch off, and it is a FUNCTION, so it has no property key to ban.
    expect(countOf('literals-violation', COLOUR_FN_RULE)).toBe(7)

    // Each ban names its fix, per the house rule. A developer who trips one must not have to
    // go and find out what to write instead.
    for (const rule of [HEX_RULE, NAMED_COLOUR_RULE, COLOUR_FN_RULE]) {
      for (const warning of by('literals-violation').filter((w) => w.rule === rule)) {
        expect(warning.text, `${rule} does not name its fix`).toContain('tokens.css')
      }
    }
  })

  it('fails every shadow, radius and spacing literal — LONGHANDS INCLUDED', async () => {
    const { by, countOf } = await lintAll()

    // 13 at implementation; 18 after review added `text-shadow` and the four wrong-family
    // token cases; 20 after Greptile's P1 split padding from margin (`padding: auto` and
    // `padding-inline: auto`).
    expect(countOf('literals-violation', ALLOWED_RULE)).toBe(20)

    // The count alone would pass if thirteen shorthand violations fired and every longhand
    // walked free — which is precisely what happens with plain string property keys
    // (measured at the baseline commit: `padding-left: 18px`, `margin-top: 9px`,
    // `column-gap: 7px` and `border-bottom-right-radius: 10px` ALL pass silently). So the
    // set of PROPERTIES reported is asserted, not just how many.
    //
    // Resolved through the reported LINE rather than the warning text, deliberately: the
    // rule carries a custom `message` naming the fix (the house rule), which replaces
    // stylelint's default "Unexpected value X for property Y" wording. Reading the source
    // line back is also the stronger assertion — it proves the rule fired on that exact
    // declaration rather than that a substring appeared somewhere in a message.
    const reported = by('literals-violation').filter((w) => w.rule === ALLOWED_RULE)
    const flaggedLines = reported.map((w) => literalsSource[w.line - 1] ?? '')
    const mentions = (property: string) =>
      flaggedLines.some((line) => new RegExp(`^\\s*${property}\\s*:`).test(line))

    for (const property of [
      'box-shadow',
      'border-radius',
      'border-bottom-right-radius', // physical longhand
      'border-start-start-radius', // LOGICAL longhand — a second axis of evasion
      'padding',
      'padding-left',
      'margin',
      'margin-top',
      'margin-block-start', // logical spacing longhand
      'gap',
      'column-gap',
    ]) {
      expect(mentions(property), `the ban never fires on \`${property}\``).toBe(true)
    }
  })

  it('fails a value that is on the scale but still written by hand', async () => {
    const { by } = await lintAll()
    // `padding: 8px` is the right number from the wrong source. It ignores every alternate
    // theme exactly as much as `18px` does, and it is the reason the rule is an ALLOWED-list
    // rather than a list of banned numbers — a ban-list would have to enumerate every value
    // that is not on the scale, which is all of them.
    const onScale = by('literals-violation')
      .filter((w) => w.rule === ALLOWED_RULE)
      .map((w) => literalsSource[w.line - 1] ?? '')
      .filter((line) => /^\s*padding:\s*8px;\s*$/.test(line))
    expect(onScale).toHaveLength(1)
  })

  it('fails every spelling of a loop or a pulse (AC 12)', async () => {
    const { countOf } = await lintAll()

    // Thirteen across the disallowed-list: the five keyword cases from implementation
    // (`infinite` in the shorthand, `alternate`, `alternate-reverse`, `alternate` inside the
    // shorthand, and the uppercase `INFINITE` — Prettier lowercases property names but NOT
    // keyword values, so that spelling really can reach the linter), plus the three
    // COMMA-LIST cases review found walking free, plus the five literal-duration cases.
    // ...16 after Greptile's P2 added the wrong-family-var and calc() cases, and 20 after
    // round 2 replaced the calc() ban with a family-level one (max/clamp/min + var fallback).
    expect(countOf('motion-violation', DISALLOWED_RULE)).toBe(20)
    // animation-iteration-count 3 and infinite, plus transition-duration and animation-delay.
    expect(countOf('motion-violation', ALLOWED_RULE)).toBe(4)

    // The comma cases by name, because the count alone cannot show WHICH five are new.
    const source = readFileSync(fixture('css/motion-violation.css'), 'utf8').split('\n')
    const flaggedLines = (await lintAll())
      .by('motion-violation')
      .map((w) => source[w.line - 1] ?? '')
    for (const declaration of [
      'pulse 2s infinite,', // `infinite` followed by a comma
      'animation-direction: alternate, normal;', // keyword followed by a comma
    ]) {
      expect(
        flaggedLines.some((line) => line.trim() === declaration),
        `the comma-list evasion is still open on \`${declaration}\``,
      ).toBe(true)
    }
  })

  it('leaves the UX-DR46 outline count at exactly ten, sharing a rule name and all', async () => {
    const { countOf } = await lintAll()
    // AC 8. The looping-animation ban added by c2-4 uses the same stylelint rule as c2-1's
    // outline ban. Keeping the motion cases in their own fixture is what stops that from
    // silently inflating an assertion three stories old.
    expect(countOf('violation', DISALLOWED_RULE)).toBe(10)
    expect(countOf('violation', ALLOWED_RULE)).toBe(0)
  })

  it('fails a literal duration, which the reduced-motion block cannot reach', async () => {
    const { countOf } = await lintAll()
    // Brad's ruling 2026-07-27. A hard-coded `300ms` is not merely off-token: the
    // @media (prefers-reduced-motion: reduce) block neutralises motion by zeroing the four
    // --motion-* tokens, and a literal ignores it entirely. A user who asked for less motion
    // gets the full animation and no gate notices. That makes it an accessibility failure.
    //
    // Six cases across the two rules: `transition-duration`/`animation-delay` longhands hit
    // the allowed-list; the `transition` shorthand (whole-second, fractional, and inside a
    // comma-separated list) hits the disallowed-list.
    expect(countOf('motion-violation', ALLOWED_RULE)).toBe(4)
    expect(countOf('motion-violation', DISALLOWED_RULE)).toBe(20)

    // Counts alone would pass if the four keyword cases fired twice each and no duration case
    // fired at all, so the specific declarations are resolved back through their line numbers.
    const source = readFileSync(fixture('css/motion-violation.css'), 'utf8').split('\n')
    const flaggedLines = (await lintAll())
      .by('motion-violation')
      .map((w) => source[w.line - 1] ?? '')
    for (const declaration of [
      'transition-duration: 300ms;', // longhand
      'animation-delay: 250ms;', // delay, not just duration
      'transition: opacity 300ms;', // the shorthand
      'transition: opacity 0.5s ease;', // fractional seconds
    ]) {
      expect(
        flaggedLines.some((line) => line.trim() === declaration),
        `the duration ban never fires on \`${declaration}\``,
      ).toBe(true)
    }
    // `0s` and `0ms` stay legal — proven by the clean fixture staying silent below.
  })

  it('does NOT report the two blocks only the guard can see', async () => {
    const { by } = await lintAll()
    const source = readFileSync(fixture('css/motion-violation.css'), 'utf8').split('\n')

    // The honest half of the two-layer claim. Every block in motion-violation.css is a
    // violation, but stylelint can only see the ones whose fault is a KEYWORD or a literal
    // duration. An iteration count in the `animation` shorthand is a bare number that a
    // value-level regex cannot separate from `cubic-bezier(0.4, 0, 0.2, 1)` — so the two
    // blocks below, whose durations are tokenised and whose only fault is the count, are
    // provably silent here and provably caught in tests/token-usage.test.ts.
    const selectorOf = (line: number) => {
      for (let i = line - 1; i >= 0; i--) {
        const match = /^\.([a-z0-9-]+)\s*\{/.exec(source[i])
        if (match) return `.${match[1]}`
      }
      return ''
    }
    const flaggedSelectors = new Set(by('motion-violation').map((w) => selectorOf(w.line)))

    expect(flaggedSelectors).not.toContain('.loops-by-count-with-tokenised-duration')
    expect(flaggedSelectors).not.toContain('.loops-by-scientific-count-with-tokenised-duration')
    // Non-vacuity: the set is populated, so "not contained" means something.
    expect(flaggedSelectors.size).toBeGreaterThan(8)
    expect(flaggedSelectors).toContain('.loops-forever')
  })

  it('fails a token from the WRONG family — invalid CSS the unknown-token guard cannot see', async () => {
    const { by } = await lintAll()
    const source = readFileSync(fixture('css/literals-violation.css'), 'utf8').split('\n')
    const flaggedLines = by('literals-violation')
      .filter((w) => w.rule === ALLOWED_RULE)
      .map((w) => source[w.line - 1] ?? '')

    // `padding: var(--radius-pill)` is worse than a literal: it renders as NOTHING, and the
    // unknown-token guard cannot catch it because --radius-pill genuinely exists. The value
    // regexes are keyed to the category prefix, so a right-shaped var of the wrong family
    // fails here. (Review finding, Medium.)
    for (const wrongFamily of [
      'padding: var(--radius-pill);',
      'border-radius: var(--space-4);',
      'box-shadow: var(--accent);',
      'gap: var(--motion-glide);',
    ]) {
      expect(
        flaggedLines.some((line) => line.trim() === wrongFamily),
        `the ban never fires on \`${wrongFamily}\``,
      ).toBe(true)
    }
  })

  it('fails `padding: auto` — valid for margin, invalid for padding (Greptile P1)', async () => {
    const { by } = await lintAll()
    const source = readFileSync(fixture('css/literals-violation.css'), 'utf8').split('\n')
    const flaggedByOurRule = by('literals-violation')
      .filter((w) => w.rule === ALLOWED_RULE)
      .map((w) => (source[w.line - 1] ?? '').trim())

    // `padding` takes a length or a percentage; `auto` is margin-only, so the browser drops
    // the declaration — the same lints-clean-renders-as-nothing class as a wrong-family token.
    expect(flaggedByOurRule).toContain('padding: auto;')
    expect(flaggedByOurRule).toContain('padding-inline: auto;')

    // HONESTY ABOUT WHAT THIS FIXED. `declaration-property-value-no-unknown`, which comes
    // free with stylelint-config-standard, ALREADY reported both of these — measured — so
    // this was never a hole a component could have shipped through. The allowed-list was
    // still wrong to accept them, and AC 7's rule is that a gate is asserted by its own rule
    // name rather than left to be covered by a neighbour. Both fire now, and this assertion
    // would fail if the split were reverted even though the file would still be red.
    expect(
      by('literals-violation').filter((w) => w.rule === 'declaration-property-value-no-unknown'),
    ).toHaveLength(2)

    // And the other half: `auto` is still legal where it is valid. `margin: 0 auto` is the
    // only way to centre a block and clean.css exercises it.
    expect(by('clean')).toEqual([])
  })

  it('fails a duration that is tokenised but still unreachable by reduced motion (P2)', async () => {
    const { by } = await lintAll()
    const source = readFileSync(fixture('css/motion-violation.css'), 'utf8').split('\n')
    const flagged = by('motion-violation')
      .filter((w) => w.rule === DISALLOWED_RULE)
      .map((w) => (source[w.line - 1] ?? '').trim())

    // Banning literal times is not the same as REQUIRING a motion token. A var() from the
    // wrong family is not a <time> at all (the declaration is discarded), and a calc() hides
    // its literal inside parentheses where the time regex cannot reach it. Neither is
    // touched by the @media block that zeroes --motion-*, which is the whole guarantee.
    expect(flagged).toContain('transition: opacity var(--space-1);')
    expect(flagged).toContain('transition: opacity calc(2s * 3);')
    expect(flagged).toContain('animation: bloom calc(var(--motion-bloom) * 2);')

    // ROUND 2: banning `calc(` was enumerating one member of a family. `max()` and `clamp()`
    // are the genuinely broken ones — under reduced motion `max(300ms, 0s)` is 300ms and the
    // motion survives — and a fifth member is a CSS release away. The rule now bans ANY
    // function call in these shorthands except var/cubic-bezier/steps, so this list is
    // illustrative rather than exhaustive; nothing has to be added when CSS grows one.
    expect(flagged).toContain('transition: opacity max(300ms, var(--motion-glide));')
    expect(flagged).toContain('transition: opacity clamp(100ms, 2vw, 300ms);')
    expect(flagged).toContain('transition: opacity min(300ms, var(--motion-glide));')
    // A literal hiding in a var() fallback: a closing paren is not the `\s|,|$` the old
    // trailing boundary required, so the time regex could not reach it.
    expect(flagged).toContain('transition: opacity var(--motion-glide, 300ms);')

    // The family ban is proven by an invented function name, not only by today's list —
    // otherwise this is an enumeration test dressed up as a family test.
    const invented = await stylelint.lint({
      code: '.a { transition: opacity futurefn(300ms); }',
      codeFilename: fileURLToPath(new URL('../src/probe.css', import.meta.url)),
      configFile: fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)),
    })
    expect(invented.results[0].warnings.map((w) => w.rule)).toContain(DISALLOWED_RULE)

    // The clean fixture composes real motion and easing tokens through the same shorthand,
    // so the new `var()` restriction cannot have degraded into "no var() in a transition".
    expect(by('clean')).toEqual([])
  })

  it('fails shadow geometry written through text-shadow or drop-shadow()', async () => {
    const { by } = await lintAll()
    const source = readFileSync(fixture('css/literals-violation.css'), 'utf8').split('\n')
    const lineOf = (w: { line: number }) => (source[w.line - 1] ?? '').trim()

    // Keying the elevation ban on `box-shadow` alone left two more properties painting
    // shadow geometry that the shadowless themes (`graphite`, `ink`) cannot switch off.
    expect(
      by('literals-violation')
        .filter((w) => w.rule === ALLOWED_RULE)
        .map(lineOf),
    ).toContain('text-shadow: 0 1px 2px rgb(0 0 0 / 50%);')
    expect(
      by('literals-violation')
        .filter((w) => w.rule === COLOUR_FN_RULE)
        .map(lineOf)
        .join('\n'),
    ).toContain('drop-shadow')
  })

  it('fails every hard-coded typography value — LONGHANDS AND SHORTHAND (c2-5 AC 10)', async () => {
    const { by, countOf } = await lintAll()
    const source = readFileSync(fixture('css/typography-violation.css'), 'utf8').split('\n')

    // Twenty-five: five hand-written longhands, the `font` shorthand that carries five of them
    // at once, six right-shaped wrong-family vars (the review round added `font:
    // var(--type-numeric-features)`), four properties the rule never enumerated, two
    // on-scale-by-hand values, two keyword values, and the review round's five: two standalone
    // font-variant-numeric literals, the two tracking siblings, and `font-weight: 0`. Own
    // fixture file, own count — the house rule that keeps c2-1's ten and c2-4's twenty
    // independent of this one.
    expect(countOf('typography-violation', ALLOWED_RULE)).toBe(25)

    const flaggedLines = by('typography-violation')
      .filter((w) => w.rule === ALLOWED_RULE)
      .map((w) => source[w.line - 1] ?? '')
    const mentions = (property: string) =>
      flaggedLines.some((line) => new RegExp(`^\\s*${property}\\s*:`).test(line))

    // The count alone would pass if the five obvious longhands fired four times each. The set
    // of PROPERTIES is what proves the family regex reaches where it claims to.
    for (const property of [
      'font', // the shorthand — five properties in one declaration
      'font-family',
      'font-size',
      'font-weight',
      'line-height',
      'letter-spacing',
    ]) {
      expect(mentions(property), `the typography ban never fires on \`${property}\``).toBe(true)
    }
  })

  it('bans the FAMILY, not the members — properties nobody enumerated fail too', async () => {
    const { by } = await lintAll()
    const source = readFileSync(fixture('css/typography-violation.css'), 'utf8').split('\n')
    const flagged = by('typography-violation')
      .filter((w) => w.rule === ALLOWED_RULE)
      .map((w) => (source[w.line - 1] ?? '').trim())

    // The single most expensive lesson of c2-4, learned twice there: a ban that lists members
    // is a ban the next member walks around (`calc()` banned, `min`/`max`/`clamp` walked
    // through). None of these four appear anywhere in .stylelintrc.json, and `font-stretch` and
    // `font-optical-sizing` are real levers on a VARIABLE font specifically — the exact class
    // of value a later story would reach for.
    expect(flagged).toContain('font-stretch: 87.5%;')
    expect(flagged).toContain('font-optical-sizing: none;')
    expect(flagged).toContain('font-size-adjust: 0.5;')
    expect(flagged).toContain('font-synthesis: none;')

    // And the family ban is proven by an INVENTED property, not only by today's list —
    // otherwise this is an enumeration test wearing a family test's name.
    const invented = await stylelint.lint({
      code: '.a { font-hyperkerning: 3; }',
      codeFilename: fileURLToPath(new URL('../src/probe.css', import.meta.url)),
      configFile: fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)),
    })
    expect(invented.results[0].warnings.map((w) => w.rule)).toContain(ALLOWED_RULE)
  })

  it('fails a TYPE token of the wrong family — invalid CSS that renders as nothing', async () => {
    const { by } = await lintAll()
    const source = readFileSync(fixture('css/typography-violation.css'), 'utf8').split('\n')
    const flagged = by('typography-violation')
      .filter((w) => w.rule === ALLOWED_RULE)
      .map((w) => (source[w.line - 1] ?? '').trim())

    // The c2-4 review theme in its typography spelling. Every token below genuinely exists, so
    // the unknown-token guard in token-usage.test.ts cannot see any of them, and every one is
    // invalid for the property it is on — the declaration is discarded and the element
    // inherits, which reads as "the style didn't apply" rather than as an error. Keying each
    // property to its OWN family prefix is what catches them.
    expect(flagged).toContain('font: var(--tracking-label);')
    expect(flagged).toContain('font-family: var(--type-body);')
    expect(flagged).toContain('font-weight: var(--space-1);')
    expect(flagged).toContain('line-height: var(--space-2);')
    expect(flagged).toContain('letter-spacing: var(--type-label);')
    // The review round's instance of the same theme, from INSIDE the type namespace:
    // --type-numeric-features is a real --type-* token, but it resolves to `tabular-nums`,
    // which is not a `font` shorthand — the declaration is discarded and the element
    // inherits. The `font` regex now excludes exactly that member.
    expect(flagged).toContain('font: var(--type-numeric-features);')
  })

  it('closes the review round holes: standalone font-variant-numeric, the tracking siblings, zero weights', async () => {
    const { by } = await lintAll()
    const source = readFileSync(fixture('css/typography-violation.css'), 'utf8').split('\n')
    const flagged = by('typography-violation')
      .filter((w) => w.rule === ALLOWED_RULE)
      .map((w) => (source[w.line - 1] ?? '').trim())

    // font-variant-numeric was carved OUT of the ban at implementation, justified as "the
    // pairing guard already requires its one legal value" — which held only inside blocks
    // that apply the numeric role. A standalone literal in a role-less block passed both
    // layers. It now has its own allowed-list entry admitting ONLY the token: `normal` (the
    // cascade-undo spelling) and every other keyword turn tabular numerals off, so none of
    // them is legal anywhere (UX-DR3 is unconditional).
    expect(flagged).toContain('font-variant-numeric: oldstyle-nums;')
    expect(flagged).toContain('font-variant-numeric: normal;')
    // The tracking SIBLINGS — not longhands of any banned property, so the family regex never
    // reached them (Brad's review ruling extends the ban): no token governs them, so `0` and
    // the CSS-wide keywords are all that is left.
    expect(flagged).toContain('word-spacing: 0.5em;')
    expect(flagged).toContain('text-indent: 2ch;')
    // `0` used to be allowed for every font-* longhand; it is a valid value for none of them
    // (`font-weight: 0` is discarded — the lints-clean-renders-as-nothing class again).
    expect(flagged).toContain('font-weight: 0;')

    // The silent halves: the paired numeric block and `word-spacing: 0`/`text-indent: 0` in
    // clean.css pass the same config in the same lintAll() invocation (asserted unfiltered in
    // the clean-fixture test below).
    const legal = await stylelint.lint({
      code: '.a { font-variant-numeric: var(--type-numeric-features); }',
      codeFilename: fileURLToPath(new URL('../src/probe.css', import.meta.url)),
      configFile: fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)),
    })
    expect(legal.results[0].warnings).toEqual([])
  })

  it('lints the REAL font stylesheet clean, and the SAME @font-face elsewhere red', async () => {
    // AC 12's pair, in the shape c2-4 established for tokens.css. An @font-face legitimately
    // declares font-family, font-weight and font-style — the exact values AC 10 bans — so the
    // font stylesheet carries a path-scoped `overrides` entry. A typo in that path would be
    // invisible to the suite otherwise: `npm run lint` would simply go red in CI.
    const real = await stylelint.lint({
      files: [fileURLToPath(new URL('../src/styles/fonts.css', import.meta.url))],
      configFile: fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)),
    })
    expect(real.results).toHaveLength(1)
    expect(real.results[0].warnings).toEqual([])

    // The firing half: the same declarations, the same config, a path the override does not
    // name. If the exemption were ever widened to `src/styles/**` or to every file, this goes
    // silent and the ban means nothing.
    const elsewhere = await stylelint.lint({
      code: "@font-face { font-family: 'Space Grotesk'; font-weight: 300 700; font-style: normal; }",
      codeFilename: fileURLToPath(new URL('../src/components/Panel.css', import.meta.url)),
      configFile: fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)),
    })
    expect(elsewhere.results[0].warnings.filter((w) => w.rule === ALLOWED_RULE)).toHaveLength(3)
  })

  it('exempts the font stylesheet from the TYPE rules only — and proves it stays that way', () => {
    // AC 12 asks for the narrowest exemption that works. An override REPLACES a rule's whole
    // option object rather than merging into it, so exempting the font properties means
    // restating the other seven entries — and a restated map is a map that drifts the first
    // time someone adds a family to the base rule and forgets this copy. That risk is closed
    // mechanically here rather than by a comment asking people to remember.
    // Typed on the way in. `JSON.parse` is `any`, and the type-aware ESLint config rejects
    // every use of it — which is the rule working: an untyped config object is exactly how a
    // drift assertion quietly starts comparing `undefined` to `undefined`.
    const config = JSON.parse(
      readFileSync(fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)), 'utf8'),
    ) as StylelintConfig

    const base = config.rules[ALLOWED_RULE][0]
    const exempted = config.overrides.find((o) => o.files.includes('src/styles/fonts.css'))?.rules[
      ALLOWED_RULE
    ]
    // `throw`, not `expect(...).toBeDefined()`. The latter reads the same but does not NARROW
    // the type, so everything below would stay `AllowedList | undefined` and the drift
    // comparison could quietly degrade into `undefined === undefined` — the vacuous-gate
    // failure this whole file exists to prevent, arriving through the type system.
    if (!exempted) {
      throw new Error('no overrides entry names src/styles/fonts.css with an allowed-list')
    }

    const isTypeRule = (key: string) => /font|letter-spacing|line-height/.test(key)
    const typeKeys = Object.keys(base).filter(isTypeRule)

    // Six type entries in the base rule (the review round split line-height out with the
    // tracking siblings and gave font-variant-numeric its own entry), none in the override…
    expect(typeKeys).toHaveLength(6)
    expect(Object.keys(exempted[0]).filter(isTypeRule)).toEqual([])
    // …and every OTHER entry present, byte-identical. This is the assertion that fails when a
    // later story adds a family to the base rule and does not carry it here.
    for (const key of Object.keys(base).filter((k) => !isTypeRule(k))) {
      expect(exempted[0][key], `the fonts.css override has drifted: ${key} is missing`).toEqual(
        base[key],
      )
    }
    expect(Object.keys(exempted[0])).toHaveLength(Object.keys(base).length - 6)
    // The override carries a `{ message }` of its own (review round: a bare map restatement
    // dropped the guidance, so a spacing violation inside fonts.css reported stylelint's
    // default text). Not asserted equal to the base message — the base one now speaks mostly
    // about typography, which is exactly what the override strips — just present and pointed
    // the same way.
    expect(exempted[1].message).toContain('design token')

    // The exemption list is THREE named paths and stays a list rather than becoming a habit
    // (AC 12). Another entry is a decision, not a detail — this is where it gets noticed.
    // The third was 16.2's, and it is the decision this pin exists to surface: DESIGN.md's
    // `components.tier-row` fixes the tier letter at 44px/500 as a component value, no
    // `--type-*` role carries 44px (StatChip's decide-once route — a role at the exact size
    // asked for — has nothing to reach), and the token pin may not move for one letter. The
    // narrowness is asserted below rather than trusted.
    expect(config.overrides).toHaveLength(3)
    expect(config.overrides.flatMap((o) => o.files)).toEqual([
      'src/styles/tokens.css',
      'src/styles/fonts.css',
      'src/containers/TierListView/TierListView.css',
    ])
  })

  it('widens the tier-letter exemption to the three cited values and NOTHING else (16.2)', () => {
    // The override REPLACES the whole allowed-list for that one file, so the narrowness that
    // matters is twofold: the widened entries admit only DESIGN.md components.tier-row's own
    // literals (44px, 500, and line-height 1 to hug the glyph), and every non-type entry is
    // byte-identical to the base rule — the same drift-proofing the fonts.css override carries.
    const config = JSON.parse(
      readFileSync(fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)), 'utf8'),
    ) as StylelintConfig

    const base = config.rules[ALLOWED_RULE][0]
    const exempted = config.overrides.find((o) =>
      o.files.includes('src/containers/TierListView/TierListView.css'),
    )?.rules[ALLOWED_RULE]
    if (!exempted) {
      throw new Error('no overrides entry names TierListView.css with an allowed-list')
    }

    // The three widened entries admit exactly one literal each beside the CSS-wide keywords —
    // a fourth value, or a widening to any px, fails by name.
    expect(exempted[0]['/^font-size$/i']).toEqual([
      '/^(44px|initial|inherit|revert|revert-layer|unset)$/i',
    ])
    expect(exempted[0]['/^font-weight$/i']).toEqual([
      '/^(500|initial|inherit|revert|revert-layer|unset)$/i',
    ])
    expect(exempted[0]['/^line-height$/i']).toEqual([
      '/^(0|1|initial|inherit|revert|revert-layer|unset)$/i',
    ])

    // Every entry the base rule carries that is NOT one of the three widenings (nor the
    // catch-all and line-height groupings the split re-shapes) is present byte-identical, so
    // a family added to the base rule cannot silently go unpoliced in this one file.
    const reshaped = [
      '/^(line-height|word-spacing|text-indent)$/i',
      '/^(?!font-family$|font-variant-numeric$)font-[a-z-]+$/i',
    ]
    for (const key of Object.keys(base).filter((k) => !reshaped.includes(k))) {
      expect(exempted[0][key], `the TierListView override has drifted: ${key}`).toEqual(base[key])
    }
    // The re-shaped pair still exists in a stricter-or-equal form: word-spacing/text-indent
    // keep their keyword-only list, and the font-* catch-all still bans every other longhand.
    expect(exempted[0]['/^(word-spacing|text-indent)$/i']).toEqual([
      '/^(0|initial|inherit|revert|revert-layer|unset)$/i',
    ])
    expect(
      exempted[0][
        '/^(?!font-family$|font-variant-numeric$|font-size$|font-weight$)font-[a-z-]+$/i'
      ],
    ).toEqual(['/^(initial|inherit|revert|revert-layer|unset)$/i'])
    expect(exempted[1].message).toContain('tier-row')
  })

  it('lints the REAL token file clean — the override is proven, not just configured', async () => {
    // Every rule in this file ships a firing/silent pair. The path-scoped `overrides` entry
    // that exempts tokens.css did not: `npm run lint` covered it in CI only, so a typo in the
    // override path would have been invisible to the suite. This is that pair's silent half —
    // the real file, the real config, no fixture involved.
    const result = await stylelint.lint({
      files: [fileURLToPath(new URL('../src/styles/tokens.css', import.meta.url))],
      configFile: fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)),
    })
    expect(result.results).toHaveLength(1)
    expect(result.results[0].warnings).toEqual([])

    // And the firing half: the SAME hex, under the SAME config, in a file the override does
    // not name. If the override were widened to every file, this would go silent.
    const elsewhere = await stylelint.lint({
      code: ':root { --smuggled: #0d0f1a; }',
      codeFilename: fileURLToPath(new URL('../src/not-the-token-file.css', import.meta.url)),
      configFile: fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)),
    })
    expect(elsewhere.results[0].warnings.map((w) => w.rule)).toContain(HEX_RULE)
  })

  it('says nothing at all about the clean fixture, in the same invocation', async () => {
    const { by } = await lintAll()
    // The other half of all five pairs above. The clean fixture composes two shadow tokens,
    // uses the percentage card radius, spends spacing through longhands AND logical
    // longhands, runs a single-iteration animation, and puts --accent-dim on a legal
    // surface — every legal form the rules above could over-reach into.
    expect(by('clean')).toEqual([])
  })
})
