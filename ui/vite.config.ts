/// <reference types="vitest/config" />
import { fileURLToPath } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

import { createDevProxy } from './config/devProxy.ts'

// AD-13: the build output is a COMMITTED artifact inside the Python package, so a fresh
// install serves the UI with no Node toolchain anywhere. This is the one place the path is
// computed; `tests/buildOutput.test.ts` pins the resolved value, because `emptyOutDir` below
// makes a typo here a recursive delete of a real source directory.
//
// `fileURLToPath`, never `new URL(...).pathname` — the latter yields "/C:/..." on Windows,
// which Vite then resolves against the cwd into `C:\C:\...` (patched out of
// devProxyRoundTrip.test.ts in c2-1's round-1 review for exactly this reason).
const outDir = fileURLToPath(new URL('../src/companion/app/static', import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir,
    // Load-bearing, not tidiness. Vite only empties an outDir that is INSIDE the project
    // root; outside it, it skips the wipe and merely warns ("outDir ... is not inside project
    // root and will not be emptied. Use --emptyOutDir to override."). Without this flag every
    // rebuild ADDS content-hashed assets and never removes the old ones, so the drift check
    // would stay green while `static/` grew a graveyard of dead bundles that all ship.
    //
    // The flip side, and the reason nothing hand-written may live in that directory: Vite's
    // emptyDir() skip list is exactly [".git"]. A .gitattributes, a README or an __init__.py
    // placed in `static/` is eaten by the next build. The byte-determinism attribute therefore
    // lives in the ROOT .gitattributes, and the "this is generated" notice lives in
    // `ui/index.html` (the source template), which Vite copies through.
    emptyOutDir: true,
  },
  server: {
    // Dev-only. The built SPA is served by FastAPI from the same origin, so nothing
    // proxies in production.
    proxy: createDevProxy(process.env),
  },
  test: {
    // Two projects rather than one, because the suites genuinely need different worlds and
    // the alternative is per-file boilerplate that ~40 downstream C2/C4/C6/C7 stories would
    // each have to remember. Splitting here means a new component test needs no setup at all.
    projects: [
      {
        extends: true,
        test: {
          name: 'node',
          environment: 'node',
          // Gate-proving suites: the ESLint/stylelint Node APIs, a real Vite dev server,
          // and the package.json contract. `tests/fixtures/**` holds inputs to those
          // suites, not test files, and is excluded by the `*.test.*` pattern itself.
          //
          // `{ts,tsx}` on BOTH projects is deliberate. With `tests/**/*.test.ts` here and
          // `src/**/*.test.{ts,tsx}` in the dom project, a file at `tests/foo.test.tsx`
          // matched NEITHER glob: vitest would collect nothing, report every other suite
          // green, and the missing coverage would be invisible. Overlap is impossible
          // because the two roots are disjoint, so widening both is free.
          include: ['tests/**/*.test.{ts,tsx}'],
        },
      },
      {
        extends: true,
        test: {
          name: 'dom',
          environment: 'jsdom',
          // See the note on the `node` project: both roots take `{ts,tsx}` so no test file
          // can fall between them.
          include: ['src/**/*.test.{ts,tsx}'],
          // Registers the jest-dom matchers and — the part that is easy to miss — an
          // afterEach(cleanup). Without globals enabled, @testing-library/react does NOT
          // auto-register its cleanup, so a second render in the same file finds two
          // copies of the component and every getByRole throws "found multiple elements".
          setupFiles: ['./src/test-setup.ts'],
        },
      },
    ],
  },
})
