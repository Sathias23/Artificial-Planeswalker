import js from '@eslint/js'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    // `dist` is the build output (c2-2 redirects it into src/companion/app/static/).
    // `tests/fixtures` holds deliberately-broken files that exist to be linted BY A TEST —
    // linting them here would make `npm run lint` permanently red. tests/lint-gates.test.ts
    // lints them through the ESLint Node API with ignores disabled.
    ignores: ['dist/**', 'node_modules/**', 'coverage/**', 'tests/fixtures/**'],
  },

  // This config file itself is plain ESM JavaScript and belongs to no tsconfig, so it is
  // deliberately kept out of the type-aware block below (see the `files` filter there).
  {
    files: ['**/*.js'],
    languageOptions: { globals: globals.node },
    extends: [js.configs.recommended],
  },

  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, tseslint.configs.recommendedTypeChecked],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        // Every linted .ts/.tsx file must belong to a tsconfig: `src` and
        // `tests/fixtures/a11y` are in tsconfig.app.json, `vite.config.ts`, `config/` and
        // `tests/` are in tsconfig.node.json. Adding a source directory means adding it to
        // one of those two `include` lists as well, or projectService will error here.
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },

  {
    files: ['**/*.tsx'],
    plugins: { 'jsx-a11y': jsxA11y },
    // `reactHooks.configs.flat[...]`, NOT `reactHooks.configs[...]`: eslint-plugin-react-hooks@7
    // exports BOTH shapes under near-identical names, and the top-level one is the legacy
    // eslintrc config (`plugins: ["react-hooks"]`, an array of strings). Passing it to flat
    // config fails the whole run with "A config object has a 'plugins' key defined as an
    // array of strings" — it does not degrade quietly.
    extends: [reactHooks.configs.flat['recommended-latest'], reactRefresh.configs.vite],
    rules: {
      // UX-DR47. Enabled by name rather than by spreading jsx-a11y's recommended config:
      // these two are the ones the design requirement actually names, and an explicit
      // pair is what tests/lint-gates.test.ts asserts on. Both are `error` — the gate has
      // no warning tier.
      'jsx-a11y/no-static-element-interactions': 'error',
      'jsx-a11y/no-noninteractive-element-interactions': 'error',
    },
  },

  {
    // Node-side code: build config, the shared dev-proxy module and the gate-proving tests.
    files: ['vite.config.ts', 'config/**/*.ts', 'tests/**/*.ts'],
    languageOptions: { globals: globals.node },
  },
)
