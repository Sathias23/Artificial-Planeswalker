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
    // rgb(), hsl(), oklch() — and the rgb() inside the hard-coded box-shadow. The modern
    // colour spaces are banned alongside the legacy ones: reaching for oklch() is no less
    // hard-coding a colour, and a list naming only rgb/hsl is a list that gets walked around.
    expect(countOf('literals-violation', COLOUR_FN_RULE)).toBe(4)

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

    expect(countOf('literals-violation', ALLOWED_RULE)).toBe(13)

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

    // `infinite` in the shorthand, `alternate`, `alternate-reverse`, `alternate` inside the
    // shorthand, and the uppercase spelling of `infinite` (Prettier lowercases property
    // names but NOT keyword values, so that spelling really can reach the linter).
    expect(countOf('motion-violation', DISALLOWED_RULE)).toBe(5)
    // animation-iteration-count: 3, and animation-iteration-count: infinite.
    expect(countOf('motion-violation', ALLOWED_RULE)).toBe(2)
  })

  it('leaves the UX-DR46 outline count at exactly ten, sharing a rule name and all', async () => {
    const { countOf } = await lintAll()
    // AC 8. The looping-animation ban added by c2-4 uses the same stylelint rule as c2-1's
    // outline ban. Keeping the motion cases in their own fixture is what stops that from
    // silently inflating an assertion three stories old.
    expect(countOf('violation', DISALLOWED_RULE)).toBe(10)
    expect(countOf('violation', ALLOWED_RULE)).toBe(0)
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
