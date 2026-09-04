import { defineConfig } from 'vitest/config'

import base from './vite.config.ts'

// The two suites that shell into a real tool — `lint-gates.test.ts` drives the ESLint and
// stylelint Node APIs (and `projectService: true` builds a TypeScript program before the first
// line is linted), `devProxyRoundTrip.test.ts` boots a real Vite dev server. Cold, that first
// call has been measured at well over vitest's 5,000 ms default, so these two run under
// `npm run test:gates` with their own timeout, and the ordinary `npm test` node project keeps
// the default. Same plugins and build settings as `vite.config.ts`; only the `test` block differs.
export default defineConfig({
  plugins: base.plugins,
  build: base.build,
  server: base.server,
  test: {
    name: 'gates',
    environment: 'node',
    include: ['tests/lint-gates.test.ts', 'tests/devProxyRoundTrip.test.ts'],
    testTimeout: 180_000,
  },
})
