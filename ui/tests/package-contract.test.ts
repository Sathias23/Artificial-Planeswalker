/**
 * AD-12 made structural, three stories before there is a store to protect.
 *
 * "One generator, one store, no second data library" is only enforceable against
 * something, so zustand is installed in this story (Decide-once #3) and the ban is a test
 * from the first commit rather than a c4-1 decision.
 *
 * One place reads package.json; three facts come out of it (AC 3, AC 4).
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))

interface PackageJson {
  dependencies?: Record<string, string>
  devDependencies?: Record<string, string>
  engines?: Record<string, string>
  scripts?: Record<string, string>
}

const pkg = JSON.parse(
  readFileSync(fileURLToPath(new URL('../package.json', import.meta.url)), 'utf8'),
) as PackageJson

const deps = pkg.dependencies ?? {}
const devDeps = pkg.devDependencies ?? {}
const allDeps = { ...deps, ...devDeps }
const scripts = pkg.scripts ?? {}

/** AD-12: no second data-fetching or state-management library joins zustand. */
const BANNED = [
  'react-query',
  '@tanstack/react-query',
  'swr',
  'redux',
  '@reduxjs/toolkit',
  'mobx',
  'jotai',
  'recoil',
  'valtio',
  'axios',
] as const

/**
 * AD-12: openapi-typescript is the ONE generator, and it consumes the backend's own
 * `app.openapi()`. A second codegen means a second spelling of every wire shape — precisely
 * the drift the generated pipeline exists to prevent — and it would arrive quietly, as a
 * devDependency nobody reviews twice. Wired in story c2-3 (AC 11).
 */
const BANNED_CODEGEN = [
  'swagger-typescript-api',
  '@hey-api/openapi-ts',
  'orval',
  'oazapfts',
  'openapi-zod-client',
  '@openapitools/openapi-generator-cli',
] as const

describe('package.json dependency contract (AD-12, AD-13)', () => {
  it.each(BANNED)('does not depend on %s', (name) => {
    expect(Object.keys(allDeps)).not.toContain(name)
  })

  // The non-vacuity pair for the ban above. Without this, a typo in the package-reading
  // code (a wrong path, a missing `devDependencies` merge) would make every ban pass by
  // finding nothing at all, and the suite would be green and worthless.
  it('does depend on zustand, so the ban above is reading a populated object', () => {
    expect(Object.keys(deps)).toContain('zustand')
  })

  // Ruling B2. openapi-typescript is installed here so the lockfile lands on typescript@5.9.x
  // from the first commit; c2-3 wires the generation script against it. Node is dev/CI-only
  // (AD-13), and a code generator is emphatically not a runtime dependency.
  //
  // This assertion is ALSO the epic's "openapi-typescript is dev/CI-only" block for story c2-3,
  // which re-verifies it rather than writing a second copy — and it is the non-vacuity pair for
  // the codegen ban below: the one generator is provably present while the alternatives are
  // provably absent.
  it('keeps openapi-typescript in devDependencies and out of dependencies', () => {
    expect(Object.keys(devDeps)).toContain('openapi-typescript')
    expect(Object.keys(deps)).not.toContain('openapi-typescript')
  })

  it.each(BANNED_CODEGEN)('does not depend on the alternative generator %s', (name) => {
    expect(Object.keys(allDeps)).not.toContain(name)
  })

  // A second generator can also arrive without touching the dependency keys at all — `npx orval`
  // inside an npm script downloads and runs it on the fly, and nobody reviews a scripts one-liner
  // twice. So the scripts block is scanned for the same names (c2-3 review, 2026-07-27).
  it.each(BANNED_CODEGEN)('does not invoke %s from an npm script either', (name) => {
    expect(JSON.stringify(scripts)).not.toContain(name)
  })

  // The non-vacuity pair for the scripts scan: the ONE generator is provably invoked from a
  // script (`gen:types`), so the scan above is reading a populated, real scripts block.
  it('invokes openapi-typescript from gen:types, so the scripts scan reads real scripts', () => {
    expect(scripts['gen:types']).toContain('openapi-typescript')
  })

  // `yaml` is read by exactly one test suite (tests/tokens.test.ts parses DESIGN.md's
  // frontmatter). Its package.json "//" note says "nothing in src/ may import it" — and until
  // this test, that was the only note in that block enforced by convention rather than by a
  // gate, sitting between two that are. The token VALUES reach the browser as CSS custom
  // properties; a YAML parser in the bundle would mean the token layer had grown a runtime,
  // which is exactly what AD-13 forbids. (Review finding, Low.)
  it('keeps yaml in devDependencies and out of dependencies', () => {
    expect(Object.keys(devDeps)).toContain('yaml')
    expect(Object.keys(deps)).not.toContain('yaml')
  })

  // ANCHORED on `^import`, not a bare substring: this very file mentions the search term in
  // the argument below, and an unanchored search would report package-contract.test.ts as a
  // yaml importer — a guard whose first finding is itself.
  //
  // `git grep` exits 1 when nothing matches, which execFileSync raises as an error. That is
  // the PASSING case for the src/ scan, so the non-zero exit is translated to "no matches"
  // rather than allowed to fail the test for the wrong reason.
  const importersOf = (pathspec: string): string[] => {
    try {
      return execFileSync('git', ['grep', '-lE', "^import .*from 'yaml'", '--', pathspec], {
        cwd: uiRoot,
        encoding: 'utf8',
      })
        .split('\n')
        .filter(Boolean)
    } catch {
      return []
    }
  }

  it('imports yaml from tests only, never from src/', () => {
    expect(importersOf('src')).toEqual([])
  })

  // The non-vacuity pair for the scan above: the legitimate importers are provably found by
  // the SAME search, so "no importers in src/" cannot be an artefact of a broken grep, a wrong
  // cwd, or the try/catch swallowing a real failure.
  //
  // The list is EXHAUSTIVE rather than a floor, so a new yaml importer has to be added here
  // deliberately. `tests/token-usage.test.ts` joined it in story c2-7: AC 13's companion guard
  // derives its uppercase requirement from DESIGN.md's own `textTransform:` keys, because no
  // token NAME encodes case the way `--tracking-X` encodes tracking — reading the contract is
  // the next best thing to inferring it, and it beats a hand-typed list of two roles. Both
  // importers are test-only and the `src/` scan above is untouched, which is the invariant
  // this block actually protects.
  it('finds exactly the legitimate yaml importers under tests/', () => {
    expect(importersOf('tests').sort()).toEqual([
      'tests/token-usage.test.ts',
      'tests/tokens.test.ts',
    ])
  })

  // AC 2. The declared floor is >=20.19.0, not the epic's looser ">= 20": vite@8 declares
  // engines `^20.19.0 || >=22.12.0` and stylelint@17 declares `>=20.19.0`, so a literal
  // Node 20.0 does not build. CI's `node-version: 20` resolves to the latest 20.x, which
  // satisfies this.
  it('declares the honest Node floor', () => {
    expect(pkg.engines?.node).toBe('>=20.19.0')
  })
})
