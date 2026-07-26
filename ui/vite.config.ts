/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

import { createDevProxy } from './config/devProxy.ts'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev-only. The built SPA is served by FastAPI from the same origin, so nothing
    // proxies in production. c2-2 owns redirecting `outDir` into
    // src/companion/app/static/ and serving it; this story keeps the default `ui/dist`.
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
          // suites, not test files, and is excluded by the `*.test.ts` pattern itself.
          include: ['tests/**/*.test.ts'],
        },
      },
      {
        extends: true,
        test: {
          name: 'dom',
          environment: 'jsdom',
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
