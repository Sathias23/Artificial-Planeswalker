import js from '@eslint/js'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

/**
 * The handlers that are actually INTERACTIONS, for the two UX-DR47 rules below.
 *
 * jsx-a11y's default list for both is these six plus `onError` and `onLoad`. See the comment
 * at the rules themselves for why those two are not interactions and why removing them is the
 * whole of the change. Exported shape pinned by `tests/lint-gates.test.ts`, which reads this
 * config through the ESLint Node API — so shortening this list by accident is a red test, not
 * a quiet weakening.
 */
const A11Y_INTERACTION_HANDLERS = [
  'onClick',
  'onMouseDown',
  'onMouseUp',
  'onKeyPress',
  'onKeyDown',
  'onKeyUp',
]

/**
 * The inline-style ban, as `no-restricted-syntax` entries. Hoisted so the copy-ban block below
 * can carry the same entries: flat config replaces a rule's options wholesale for every block
 * that names it, so a second `no-restricted-syntax` block that listed only its own selectors
 * would silently switch the inline-style ban off for the files it matches.
 */
const INLINE_STYLE_BANS = [
  {
    // Not a direct inline object literal at all — nothing static can prove what is in
    // it. The attribute's value must BE `{…}` or `{…} as CSSProperties` (the cast is
    // load-bearing: React's CSSProperties has no index signature for `--` keys, so the
    // bare literal is TS2353); a call, a ternary, a variable or a string hides its keys
    // and stays an error however compliant an object it contains.
    selector:
      'JSXAttribute[name.name="style"]:not([value.expression.type="ObjectExpression"]):not([value.expression.type="TSAsExpression"][value.expression.expression.type="ObjectExpression"])',
    message:
      'Inline style={{…}} bypasses the whole token layer — no stylelint rule and no ' +
      'guard in tests/token-usage.test.ts can see it. A style attribute that is not a ' +
      'literal object (or a literal directly under one `as` cast) hides its keys from ' +
      'every static reader, so it cannot be the named-channel form c4-8 opened. Put the ' +
      'rule in a .css file and reach values through var(--…). See ui/README.md, ' +
      '"The token layer".',
  },
  {
    // The ordinary case, and the one the ban has always been about: the attribute IS a
    // literal, but it carries a spread, a computed key, or any property whose key is not
    // a declared runtime channel. Each `[key.value="…"]` is an exact string match against
    // the allowlist; an identifier key (`padding`) or a computed key has no matching
    // `value`, so the chained `:not()`s fire — conservative in the right direction. A
    // third channel is a third `:not()`, which is the protocol working rather than a
    // reason to loosen back to a prefix.
    selector:
      'JSXAttribute[name.name="style"]:has(:matches(JSXExpressionContainer > ObjectExpression, JSXExpressionContainer > TSAsExpression > ObjectExpression) > :matches(SpreadElement, Property:not([key.value="--curve-bar-height"]):not([key.value="--colour-bar-share"]):not([key.value="--history-popover-top"]):not([key.value="--history-popover-right"])))',
    message:
      'Inline style={{…}} bypasses the whole token layer — no stylelint rule and no ' +
      'guard in tests/token-usage.test.ts can see it. Put the rule in a .css file and ' +
      'reach values through var(--…). The ONLY permitted form is an object literal ' +
      'whose keys are all DECLARED runtime channels (today: --curve-bar-height, ' +
      '--colour-bar-share, --history-popover-top, --history-popover-right), with no ' +
      'spread — a bare `--` prefix is not enough, because a ' +
      'custom property can override a real design token for every descendant (c4-8, ' +
      'AC 17; c4-9, AC 19). See ui/README.md, "The token layer".',
  },
]

/**
 * UX-DR33's voice rules for user-facing copy, as lint: no exclamation mark (including the
 * full-width and compatibility spellings NFKC folds to `!`), no emoji, and never
 * "something went wrong". Selectors over string literals, JSX text and template chunks only —
 * `!` as an operator is never a `Literal`, and a comment is not a node, so neither can fire.
 * The backslashes are doubled because esquery unescapes the selector before it builds the
 * RegExp. Proven both ways by `tests/lint-gates.test.ts` on the `copy-ban-*.tsx` fixtures.
 */
const COPY_BANS = [
  {
    selector:
      ':matches(Literal[value=/[!！︕﹗‼⁉]/u], JSXText[value=/[!！︕﹗‼⁉]/u], TemplateElement[value.cooked=/[!！︕﹗‼⁉]/u])',
    message:
      'UX-DR33: calm, terminal-literate copy carries no exclamation mark (the full-width and ' +
      'compatibility spellings fold to `!` and are banned with it).',
  },
  {
    selector:
      ':matches(Literal[value=/\\p{Extended_Pictographic}/u], JSXText[value=/\\p{Extended_Pictographic}/u], TemplateElement[value.cooked=/\\p{Extended_Pictographic}/u])',
    message: 'UX-DR33: no emoji and no mascot in copy.',
  },
  {
    selector:
      ':matches(Literal[value=/something\\s+went\\s+wrong/iu], JSXText[value=/something\\s+went\\s+wrong/iu], TemplateElement[value.cooked=/something\\s+went\\s+wrong/iu])',
    message:
      'UX-DR33: never blame and never shrug — "something went wrong" is banned; say what ' +
      'happened and what to do next.',
  },
]

export default tseslint.config(
  {
    // `dist` is the build output (vite.config.ts redirects it into src/companion/app/static/).
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
    // a real bug in the store hooks — silently skip exactly those files.
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
      //
      // THE HANDLER LIST IS NARROWED, IN THE OPEN, AND THIS IS A RULE CHANGE RATHER THAN A
      // LOCAL EXCEPTION. Both rules default to
      // `['onClick', 'onError', 'onLoad', 'onMouseDown', 'onMouseUp', 'onKeyPress',
      // 'onKeyDown', 'onKeyUp']`, and `onLoad` / `onError` are not interactions at all: they
      // are RESOURCE-LIFECYCLE events, fired by the browser when a subresource finishes or
      // fails, with no user anywhere in the causal chain. There is no keyboard equivalent to
      // add and no role to promote — the whole premise of both rules ("this element looks
      // clickable to a mouse and is invisible to a keyboard") does not apply.
      //
      // The card tile renders an `<img>`, and `<img onLoad onError>` is the ONLY way a
      // component can know whether the pixels arrived — which is the whole of the
      // placeholder-then-fill contract (UX-DR36). The alternatives were an inline
      // `eslint-disable` on the one line that matters, or dropping the rule; narrowing the list
      // keeps the rules total over every interaction spelling while removing two names that
      // were never interactions.
      //
      // The six that remain are the interaction handlers, and `tests/lint-gates.test.ts` both
      // pins this list against drift and proves the pair still fires on `onClick` while staying
      // silent on `<img onLoad>`.
      'jsx-a11y/no-static-element-interactions': ['error', { handlers: A11Y_INTERACTION_HANDLERS }],
      'jsx-a11y/no-noninteractive-element-interactions': [
        'error',
        { handlers: A11Y_INTERACTION_HANDLERS },
      ],

      // THE TOKEN LAYER'S BLIND SPOT.
      //
      // Every other gate stops at `*.css`: stylelint bans hard-coded colours, shadows, radii,
      // spacing and durations, and tests/token-usage.test.ts covers what stylelint cannot
      // express. None of them can see a single character of
      // `style={{ padding: '18px', boxShadow: '0 12px 32px rgba(0,0,0,.5)' }}` in a `.tsx`
      // file — which is the most convenient way to write a style and therefore the way a
      // component author reaches for under time pressure. Wanting an inline style is usually
      // a signal that layout is being done in JS that belongs in CSS; the application shell,
      // whose whole job is geometry, needed none.
      //
      // `no-restricted-syntax` rather than `react/forbid-dom-props`: the latter needs
      // eslint-plugin-react, which this project does not install and which AD-12's
      // one-tool-per-job discipline would make us justify. A selector on the JSX attribute
      // name costs no dependency and says exactly what it means.
      //
      // Escape hatch, deliberately narrow. A genuinely dynamic value sets a CSS CUSTOM PROPERTY
      // through the style attribute's own typing — but that is still this attribute, so a
      // component needing it changes this rule and says why, in the open, rather than
      // discovering the gate does not apply to it.
      //
      // ==== THE HATCH, TAKEN IN THE OPEN ======================================================
      //
      // A mana curve's bar height IS the data. There is no class-based spelling of "this bar is
      // 62% as tall as the tallest one" — the value is a number computed from the deck at
      // render time, and seven of them change whenever the deck does. The alternatives were
      // priced: a stylesheet of pre-baked percentage classes is a quantisation of the data (and
      // the real scale extreme is 39-versus-0 in one deck, so the buckets it would need are not
      // a small set), and an `eslint-disable` comment on the one line that matters is the
      // failure this reservation exists to prevent.
      //
      // SO THE RULE IS NARROWED, NOT DISABLED, AND NOT TURNED OFF FOR A FILE. The two
      // selectors below keep the error for every `style` attribute this project has ever had
      // and admit exactly one new shape: an object literal whose keys are ALL drawn from the
      // NAMED runtime-channel allowlist. `style={{ padding: '18px' }}` is still an error. So is
      // `style={{ '--h': x, color: 'red' }}` — one non-permitted property re-opens the whole
      // hole — and so is `style={{ '--surface-well': x }}`: a `--`-prefixed key can name a REAL
      // design token and re-theme every descendant consuming it, which no stylelint rule and no
      // stylesheet scan would ever see. The hatch is therefore an exact NAME allowlist, not a
      // prefix test — the same protocol RUNTIME_CUSTOM_PROPERTIES uses in
      // tests/token-usage.test.ts, and the two lists move together: adding a channel adds it
      // in both places, in the open, or one of the two gates goes red.
      //
      // --colour-bar-share carries a RAW PIP COUNT, not a percentage, which makes that channel
      // narrower than the bar height's rather than wider: `flex-grow` performs the division in
      // the browser, so no percentage is computed in TSX at all, nothing can divide by zero at
      // the call site, and the value crossing the attribute is an integer. The consuming
      // declaration is `flex-grow: var(--colour-bar-share, 0)` in ColourDistribution.css, where
      // stylelint and tests/token-usage.test.ts can both see the rule around it.
      //
      // Today the list is four names: --curve-bar-height (the mana curve's bar height),
      // --colour-bar-share (the colour distribution's segment width), and the history
      // popover's pair --history-popover-top / --history-popover-right (the popover's clamp
      // anchor terms: its measured distances from the viewport top and to its right-anchored
      // edge, which no stylesheet can know because the header above it is content-sized and
      // its pill row wraps).
      //
      // DIRECT-CHILD PATHS, NOT DESCENDANT :has, in both selectors. Testing
      // `:has(ObjectExpression …)` over the attribute's whole subtree reads "contains a
      // literal somewhere" as "IS a literal": `style={fn({ '--h': x })}` and
      // `style={cond ? { '--h': x } : hiddenObj}` both contain a compliant literal and both
      // smuggle arbitrary properties past every static reader — the exact shape the first
      // selector's own message claims to close. The anchor is `JSXExpressionContainer`, which
      // can only ever be the attribute's own value wrapper, so a literal nested inside a
      // property's VALUE (`fmt({ pad: 1 })`) does not false-positive either. (esquery does
      // not support a leading combinator inside :has — `:has(> X)` matches NOTHING, silently —
      // which is why the anchor is a named parent rather than a child combinator.)
      //
      // Reported once per ATTRIBUTE, never per property, and that is what keeps
      // tests/lint-gates.test.ts's `inline-style-violation.tsx` pin at exactly 2: that fixture
      // has two `style` attributes carrying five plain properties between them, and a
      // property-level selector would report five. If that count moves, the narrowing is wrong.
      // The two firing shapes share one selector (`:matches`) for the same reason: a spread
      // AND a plain property in one attribute is one violation, not two.
      //
      // What the token layer still protects, unchanged: every colour, radius, shadow, spacing,
      // duration and type value in this project comes from a token, because the custom property
      // this hatch admits is CONSUMED in a .css file (`height: var(--curve-bar-height)`) where
      // stylelint and tests/token-usage.test.ts can both see the declaration around it. The
      // hatch passes a NUMBER through the attribute; it does not pass a style — and with the
      // name allowlist, it cannot pass a token override either.
      'no-restricted-syntax': ['error', ...INLINE_STYLE_BANS],
    },
  },

  {
    // Shipped UI source only: colocated tests may quote the banned strings while asserting on
    // rendered copy, and `tests/fixtures/tsx/copy-ban-*.tsx` are the fixtures that prove the
    // ban fires and stays silent.
    files: ['src/**/*.{ts,tsx}', 'tests/fixtures/tsx/copy-ban-*.tsx'],
    ignores: ['src/**/*.test.{ts,tsx}'],
    rules: {
      'no-restricted-syntax': ['error', ...INLINE_STYLE_BANS, ...COPY_BANS],
    },
  },

  {
    // Node-side code: build config, the shared dev-proxy module and the gate-proving tests.
    files: ['vite.config.ts', 'vitest.gates.config.ts', 'config/**/*.ts', 'tests/**/*.ts'],
    languageOptions: { globals: globals.node },
  },
)
