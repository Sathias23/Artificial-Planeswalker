/**
 * The lint gate proves itself, in both directions.
 *
 * Every rule this story adds is shown FIRING and NOT FIRING from the same invocation
 * (the standing non-vacuity pairing agreement, promoted at the C1 retro). A test that
 * only shows a violation cannot distinguish "the rule fired" from "the config errors on
 * every file it is handed" — which is exactly how a lint gate rots without anyone noticing.
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
    const files = ['clean', 'violation', 'literals-violation', 'motion-violation'].map((n) =>
      fixture(`css/${n}.css`),
    )
    const result = await stylelint.lint({
      files,
      configFile: fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)),
    })

    // The non-vacuity anchor for the whole block: four fixtures in, four results out. A
    // moved or ignored fixture would otherwise make every count assertion below read
    // `undefined` warnings and fail confusingly, or — worse for the clean half — pass.
    expect(result.results, 'stylelint did not lint all four fixtures').toHaveLength(4)

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
