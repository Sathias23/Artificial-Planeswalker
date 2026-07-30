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
    // The hooks rules must cover `.ts` as well as `.tsx`. A custom hook lives in a plain
    // `.ts` file more often than not (`src/hooks/useDeck.ts`), and scoping this to `.tsx`
    // would let `rules-of-hooks` and `exhaustive-deps` — the two rules most likely to catch
    // a real bug in c4-1's store work — silently skip exactly those files.
    files: ['**/*.{ts,tsx}'],
    // `reactHooks.configs.flat[...]`, NOT `reactHooks.configs[...]`: eslint-plugin-react-hooks@7
    // exports BOTH shapes under near-identical names, and the top-level one is the legacy
    // eslintrc config (`plugins: ["react-hooks"]`, an array of strings). Passing it to flat
    // config fails the whole run with "A config object has a 'plugins' key defined as an
    // array of strings" — it does not degrade quietly.
    extends: [reactHooks.configs.flat['recommended-latest']],
  },

  {
    // JSX-only concerns, deliberately NOT widened to `.ts`: a11y rules need JSX elements to
    // look at, and react-refresh reasons about component exports, which a `.ts` file cannot
    // have. Keeping them here rather than in the block above avoids arguing with every
    // non-component module in `config/` and `tests/`.
    files: ['**/*.tsx'],
    plugins: { 'jsx-a11y': jsxA11y },
    extends: [reactRefresh.configs.vite],
    rules: {
      // UX-DR47. Enabled by name rather than by spreading jsx-a11y's recommended config:
      // these two are the ones the design requirement actually names, and an explicit
      // pair is what tests/lint-gates.test.ts asserts on. Both are `error` — the gate has
      // no warning tier.
      'jsx-a11y/no-static-element-interactions': 'error',
      'jsx-a11y/no-noninteractive-element-interactions': 'error',

      // THE TOKEN LAYER'S BLIND SPOT, CLOSED BEFORE THE FIRST COMPONENT EXISTS.
      //
      // Every gate story c2-4 shipped stops at `*.css`: stylelint bans hard-coded colours,
      // shadows, radii, spacing and durations, and tests/token-usage.test.ts covers what
      // stylelint cannot express. None of them can see a single character of
      // `style={{ padding: '18px', boxShadow: '0 12px 32px rgba(0,0,0,.5)' }}` in a `.tsx`
      // file — which is the most convenient way to write a style and therefore the way a
      // component author reaches for under time pressure. The gate had to exist BEFORE the
      // first component, or the exception becomes the convention.
      //
      // It held: c2-6 wrote the application shell — the first component in the codebase, and
      // the one whose whole job is geometry — with no inline style anywhere, and needed no
      // escape hatch to do it. That is the datum this rule was betting on. If a later story
      // reaches for a dynamic value, the shell is the precedent to look at first: c2-6 found
      // that wanting one was a signal the layout was being done in JS that belonged in CSS.
      //
      // `no-restricted-syntax` rather than `react/forbid-dom-props`: the latter needs
      // eslint-plugin-react, which this project does not install and which AD-12's
      // one-tool-per-job discipline would make us justify. A selector on the JSX attribute
      // name costs no dependency and says exactly what it means.
      //
      // Escape hatch, deliberately narrow: none. A genuinely dynamic value (a computed bar
      // height in c4-8, a grid template in c6-6) sets a CSS CUSTOM PROPERTY through the style
      // attribute's own typing — but that is still this attribute, so a story needing it
      // changes this rule and says why, in the open, rather than discovering the gate does
      // not apply to it. (Brad's ruling 2026-07-27.)
      'no-restricted-syntax': [
        'error',
        {
          selector: 'JSXAttribute[name.name="style"]',
          message:
            'Inline style={{…}} bypasses the whole token layer — no stylelint rule and no ' +
            'guard in tests/token-usage.test.ts can see it. Put the rule in a .css file and ' +
            'reach values through var(--…). See ui/README.md, "The token layer".',
        },
      ],
    },
  },

  {
    // Node-side code: build config, the shared dev-proxy module and the gate-proving tests.
    files: ['vite.config.ts', 'config/**/*.ts', 'tests/**/*.ts'],
    languageOptions: { globals: globals.node },
  },
)
