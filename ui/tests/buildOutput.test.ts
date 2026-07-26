/**
 * AC 3 — the guard on a recursive delete.
 *
 * `build.emptyOutDir: true` wipes the output directory on every build, and the directory is
 * computed from a relative path. A typo there ("../src/companion/app" instead of
 * "../src/companion/app/static") is not a broken build — it is a silent recursive delete of a
 * real source tree. So the resolved value is pinned here, and both halves are asserted: a
 * correct path with `emptyOutDir` off ships a graveyard of stale hashed bundles (Vite skips
 * emptying an outDir outside the project root and only warns), and a wrong path with it on
 * deletes source. Neither half may regress alone.
 *
 * `resolveConfig` rather than importing the config object: this asks Vite what it will
 * actually build into, which is the thing that has consequences.
 */

import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'
import { resolveConfig } from 'vite'

const uiRoot = fileURLToPath(new URL('..', import.meta.url))

/**
 * Computed from `ui/tests/`, i.e. by a different route than vite.config.ts computes it from
 * `ui/`. Two independent derivations agreeing is the point; re-importing the config's own
 * constant would assert nothing.
 */
const EXPECTED_OUT_DIR = fileURLToPath(
  new URL('../../src/companion/app/static', import.meta.url),
)

describe('build output contract (AD-13)', () => {
  it('builds into the committed bundle directory inside the Python package', async () => {
    const config = await resolveConfig({ root: uiRoot }, 'build')

    // resolve() on both sides so a posix-normalised value from Vite and a native-separator
    // value from fileURLToPath compare equal on Windows.
    expect(resolve(config.build.outDir)).toBe(resolve(EXPECTED_OUT_DIR))
  })

  it('ends the resolved path at src/companion/app/static and nowhere shallower', async () => {
    const config = await resolveConfig({ root: uiRoot }, 'build')

    expect(config.build.outDir.replace(/\\/g, '/')).toMatch(
      /\/src\/companion\/app\/static$/,
    )
  })

  it('empties the output directory, so a rebuild removes stale hashed assets', async () => {
    const config = await resolveConfig({ root: uiRoot }, 'build')

    expect(config.build.emptyOutDir).toBe(true)
  })

  // Non-vacuity: if resolveConfig ever returned a stub, every assertion above would still
  // need this to be a real absolute path outside ui/.
  it('resolves to an absolute path outside ui/', async () => {
    const config = await resolveConfig({ root: uiRoot }, 'build')
    const outDir = resolve(config.build.outDir)

    expect(resolve(outDir)).toBe(outDir)
    expect(outDir.startsWith(resolve(uiRoot))).toBe(false)
  })
})
