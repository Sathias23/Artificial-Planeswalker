/**
 * The gates' file-class geometry, made structural (review round 2, decision D3).
 *
 * Three latent holes shared one shape — a file class some tool's glob quietly excludes:
 * a test file outside `src/` and `tests/` is collected by NEITHER vitest project (the
 * directory-axis twin of the `.tsx`-extension hole the round-1 patch closed); a
 * `tests/*.test.tsx` file runs in vitest but matches no tsconfig `include` (`tests/**\/*.ts`
 * does not match `.tsx`), so `tsc -b` never checks it and `eslint .` fails on it with a
 * projectService error; and a `.jsx`/`.mjs`/`.cjs` file matches no ESLint `files` block and
 * no tsconfig at all, so a `<div onClick>` in `src/Foo.jsx` would pass the UX-DR47 a11y gate
 * and the type gate wholesale. Rather than widening every config to admit the classes, the
 * classes are banned — the same "enforced by tests, not convention" idiom as
 * package-contract.test.ts.
 */

import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))

// git is the file authority, not readdir: node_modules, dist and coverage are invisible to
// it, and a stray file is caught the moment it is committed — which is when CI sees it.
const trackedFiles = execFileSync('git', ['ls-files'], { cwd: uiRoot, encoding: 'utf8' })
  .split('\n')
  .filter(Boolean)

const testFiles = trackedFiles.filter((f) => /\.test\.[^/]+$/.test(f))

describe('gate geometry: no file class escapes the gates', () => {
  // The non-vacuity anchor: every ban below filters this list, and an empty list (a wrong
  // cwd, git resolving the wrong tree) would make every ban pass by finding nothing.
  it('is reading a populated tracked-file list', () => {
    expect(trackedFiles).toContain('package.json')
    expect(testFiles.length).toBeGreaterThan(0)
  })

  // Mirrors the union of the two vitest include globs in vite.config.ts. A test file
  // anywhere else — a colocated `config/devProxy.test.ts`, a root-level `foo.test.ts` —
  // matches neither project and silently never runs while the suite stays green.
  it('keeps every test file inside the two vitest roots', () => {
    const uncollected = testFiles.filter(
      (f) => !(f.startsWith('tests/') || f.startsWith('src/')) || !/\.test\.(?:ts|tsx)$/.test(f),
    )
    expect(uncollected).toEqual([])
  })

  // tests/ is the node-environment project and belongs to tsconfig.node.json, whose include
  // stops at `.ts` — a `.test.tsx` file there would run in vitest (the widened glob catches
  // it) while being type-checked by nobody. Component tests are `.tsx` and live in `src/`,
  // where the dom project and tsconfig.app.json both know about them.
  it('keeps .tsx test files out of tests/ — component tests live in src/', () => {
    expect(testFiles.filter((f) => f.startsWith('tests/') && f.endsWith('.tsx'))).toEqual([])
  })

  // eslint.config.js lints `**/*.{ts,tsx}` type-aware and `**/*.js` with the base rules;
  // nothing lints `.jsx`/`.mjs`/`.cjs` and no tsconfig admits them, so the classes are
  // banned rather than half-covered. The one legitimate `.js` file is the flat config
  // itself, which its own comment documents as deliberately un-type-checked.
  it('allows no source-file extension the lint and type gates do not cover', () => {
    expect(trackedFiles.filter((f) => /\.(?:jsx|mjs|cjs)$/.test(f))).toEqual([])
    expect(trackedFiles.filter((f) => f.endsWith('.js'))).toEqual(['eslint.config.js'])
  })
})
