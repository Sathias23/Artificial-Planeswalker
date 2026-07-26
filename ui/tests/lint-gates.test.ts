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
    const outlineWarnings = result.results[0].warnings.filter((w) => w.rule === OUTLINE_RULE)

    // Five banned declarations in the fixture: `outline: none`, `outline: 0`, `outline: 0px`,
    // `outline-style: none`, `outline-width: 0` and `outline-width: 0px` — six. A ban on only
    // the two literal spellings is one a search-and-replace walks straight around, so the
    // longhands and the zero-with-unit forms are banned too.
    expect(outlineWarnings).toHaveLength(6)
    expect(new Set(outlineWarnings.map((w) => w.severity))).toEqual(new Set(['error']))

    // And the :focus-visible replacement in the same file bought no exemption.
    expect(result.results[0].source).toContain('violation.css')
  })

  it('leaves a stylesheet with no outline declaration alone', async () => {
    const result = await lintCss('css/clean.css')

    expect(result.errored).toBeFalsy()
    expect(result.results[0].warnings).toEqual([])
  })
})
