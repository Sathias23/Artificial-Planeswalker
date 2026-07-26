/**
 * The lint gate proves itself, in both directions.
 *
 * Every rule this story adds is shown FIRING and NOT FIRING from the same invocation
 * (the standing non-vacuity pairing agreement, promoted at the C1 retro). A test that
 * only shows a violation cannot distinguish "the rule fired" from "the config errors on
 * every file it is handed" — which is exactly how a lint gate rots without anyone noticing.
 */

import { fileURLToPath } from 'node:url'

import { ESLint } from 'eslint'
import stylelint from 'stylelint'
import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))
const fixture = (rel: string) => fileURLToPath(new URL(`fixtures/${rel}`, import.meta.url))

const A11Y_STATIC = 'jsx-a11y/no-static-element-interactions'
const A11Y_NONINTERACTIVE = 'jsx-a11y/no-noninteractive-element-interactions'
const OUTLINE_RULE = 'declaration-property-value-disallowed-list'

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
    // The whole point of the pair: this file goes through the identical config and is clean.
    expect(clean!.messages).toEqual([])
    expect(clean!.errorCount).toBe(0)
  })
})

describe('stylelint focus-ring gate (UX-DR46, AC 9)', () => {
  const lintCss = (file: string) =>
    stylelint.lint({
      files: [fixture(file)],
      configFile: fileURLToPath(new URL('../.stylelintrc.json', import.meta.url)),
    })

  it('reports outline:none even when a :focus-visible replacement is present', async () => {
    const result = await lintCss('css/violation.css')

    expect(result.errored).toBe(true)
    const warnings = result.results[0].warnings
    const outlineWarnings = warnings.filter((w) => w.rule === OUTLINE_RULE)

    // Both `outline: none` and `outline: 0` are banned, so both declarations are reported —
    // and the :focus-visible replacement in the same file does not buy an exemption.
    expect(outlineWarnings).toHaveLength(2)
    expect(new Set(outlineWarnings.map((w) => w.severity))).toEqual(new Set(['error']))
  })

  it('leaves a stylesheet with no outline declaration alone', async () => {
    const result = await lintCss('css/clean.css')

    expect(result.errored).toBeFalsy()
    expect(result.results[0].warnings).toEqual([])
  })
})
