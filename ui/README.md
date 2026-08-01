# `ui/` — the Companion SPA

Vite + React + TypeScript. Node is required **only** for development and CI: it is never
needed to install or run the Python package (NFR-07, AD-13). `pyproject.toml` knows nothing
about this directory, and nothing under `src/` depends on it.

**Node floor: `>=20.19.0`.** Not a typo for "20" — `vite@8` declares
`engines: ^20.19.0 || >=22.12.0` and `stylelint@17` declares `>=20.19.0`, so a literal Node
20.0 cannot build this project.

## The dev loop

Two processes, two terminals.

```bash
# 1. the companion backend (repo root)
uv run artificial-planeswalker companion

# 2. the frontend dev server (this directory)
npm ci          # exactly the committed lockfile; `npm install` would rewrite it on drift
npm run dev
```

Open the URL Vite prints. Requests to `/api` and `/health` are proxied to the backend at
`http://127.0.0.1:8765`; set `COMPANION_PORT` to move it — **the same variable the backend
reads**, so export it once for both processes.

The proxy parses that variable the way the backend's `int()` does, not the way JavaScript's
`Number()` does, so the two processes cannot end up on different ports over `0x50`, `1e3` or
`8_080`. Anything it discards, it says so on the console. One value is worth knowing about:
`COMPANION_PORT=0` is **legal for the backend** — it means "bind an ephemeral port" — but a
dev proxy is configured once, before the backend starts, so it cannot discover that port.
It warns and falls back rather than pretending to work.

### Why the proxy sets `changeOrigin: true`

Because without it every proxied request fails with `400 {"reason": "invalid_request"}`.

In dev the browser talks to Vite on one port and the backend listens on another. The backend
is localhost-only by design (NFR-01): `HostValidationMiddleware` compares each request's
`Host` header against `allowed_authorities(port)` — exactly
`{"127.0.0.1:<port>", "localhost:<port>"}` — by exact match after lowercasing, and rejects
anything else. A proxied request that keeps Vite's authority in `Host` therefore misses that
set and is refused before it reaches a route.

`changeOrigin: true` rewrites the forwarded `Host` to the target's authority, so the backend
sees its own address and the check passes. This is C1 retro ruling **R1**, and it is asserted
by a real round trip in `tests/devProxyRoundTrip.test.ts` — both directions — rather than by
reading the config object.

Note that `changeOrigin` affects the **`Host`** header only. It does not touch the browser's
`Origin` header; the WebSocket upgrade validates `Origin` as well, and that is **c5-3**'s
problem, not this proxy's.

### Where the build output goes

`npm run build` writes into **`../src/companion/app/static/`** — inside the Python package,
not `ui/dist`. **That tree is committed**, because it is what lets a fresh install serve the
UI with no Node toolchain anywhere on the machine (AD-13, SC-4): `pyproject.toml` still knows
nothing about this directory, and the wheel ships the bundle as ordinary package data.

It is **generated output — never hand-edit it.** Edit the source here and rebuild. CI rebuilds
the bundle on every run and fails if the committed copy differs, so a stale bundle cannot
reach master. The same applies to the mirrored copy under `plugin/`, which
`scripts/build_plugin.py` regenerates.

Two consequences worth knowing:

- **`npm run build` now mutates `src/`.** It is no longer a no-op on the Python tree, so check
  `git status` before committing. (`npm test` does not build, so the test loop is unaffected.)
- **Nothing hand-written can live in `src/companion/app/static/`.** `emptyOutDir: true` wipes
  that directory on every build, and Vite's skip list is exactly `.git` — a README, a
  `.gitattributes` or an `__init__.py` placed there is deleted by the next build. That is why
  the "this file is generated" notice lives in `ui/index.html`, and the line-ending attribute
  in the repository-root `.gitattributes`.

### Which URLs the SPA may own

The backend serves the bundle behind a fallback rule (c2-2's decide-once ruling): a request
reaches `index.html` only if it is a `GET`/`HEAD`, its **final path segment contains no dot**,
and its **first segment is not reserved** — `api` plus every registered backend prefix
(`health`, `docs`, `redoc`, `openapi.json`, and whatever later stories register), plus
`assets/`, which never falls back. Design client-side routes inside that shape: `/decks/42`
renders the app; `/decks/v1.2` (dot in the final segment) and anything under a reserved prefix
answer a typed JSON 404 instead. The Vite dev server does not enforce this rule, so a route
that violates it works in dev and 404s in production.

## The quality gate

All five run in CI and gate the build, and all five are runnable here:

| Command                | What it gates                                                                |
| ---------------------- | ---------------------------------------------------------------------------- |
| `npm run lint`         | ESLint **and** stylelint — both, in one script; `npm run lint` _is_ the gate |
| `npm run format:check` | Prettier                                                                     |
| `npm run typecheck`    | `tsc -b` across both sub-projects                                            |
| `npm test`             | vitest                                                                       |
| `npm run build`        | the bundle builds — and CI then fails if the committed copy is stale         |

Some notes that are easy to trip over:

- **Type-checking is `tsc -b`, never `tsc --noEmit`.** `tsconfig.json` has `"files": []` and
  only project references, so a bare `tsc --noEmit` type-checks _zero files_ and exits 0 — a
  perfectly green, perfectly vacuous gate. `tsc -b` builds both referenced projects, which is
  also the only way `vite.config.ts` gets checked at all.
- **CSS rules live in stylelint, not ESLint.** `@eslint/css` ships fifteen rules and none of
  them can restrict a declaration _value_, which is what banning `outline: none` (UX-DR46)
  requires. The token layer's literal bans are rules of the same shape — see _The token
  layer_ below. The one exception is the inline-`style` ban, which is necessarily an ESLint
  rule because its target is a `.tsx` file. Decided as ruling B1.
- **ESLint is pinned to `^9`** and TypeScript to `>=5.9 <6.1`. Both pins are load-bearing and
  both carry their reason in `package.json` — read it before running `npm update`.
- **Line endings are forced to LF** by `ui/.gitattributes`, because the repository sets
  `core.autocrlf=true`. Without it `prettier --check` is red on Windows and green on CI from
  the same commit.
- `tests/fixtures/` holds deliberately-broken files. They are inputs to the lint-gate tests,
  are excluded from `npm run lint` (ESLint via config `ignores`, stylelint via
  `--ignore-pattern` so the Node-API tests are unaffected), and should stay broken.
- **The proxy keys are anchored regexes, not path prefixes.** Vite treats a plain `'/api'`
  key as a prefix, so it would also swallow a future frontend route named `/api-docs`.
- `engine-strict=true` in `.npmrc` makes the declared Node floor an install-time error
  rather than a warning npm prints and ignores.
- **CI runs a sixth step these five do not cover:** it regenerates `src/api/types.d.ts` and
  fails if the committed copy is stale. See _Wire types are generated, never hand-written_
  below — the fix is always `npm run gen:api`, never editing the generated file.

## Wire types are generated, never hand-written

Every shape that crosses the wire is declared once, in Python, in
`src/companion/contracts.py`. The TypeScript half is generated from the backend's own
`app.openapi()` output and committed (AD-12):

```
src/companion/contracts.py
        │  uv run python -m scripts.dump_openapi        ← the Python half
        ▼
ui/src/api/openapi.json          (generated, committed)
        │  npm run gen:types                            ← the Node half
        ▼
ui/src/api/types.d.ts            (generated, committed)
        │  import type
        ▼
ui/src/api/schema.ts             ← the ONLY module that reads types.d.ts
```

**After touching a Pydantic model, run `npm run gen:api`** — it does both halves and rewrites
both generated files. Commit them **together**: a commit carrying a fresh `openapi.json` and a
stale `types.d.ts` is red in CI, and a bisect landing on it has a broken frontend gate for
reasons unrelated to whatever is being bisected.

**Import wire types from `src/api/schema.ts`, never from `./types` directly.** The generated
file is shaped for a generator, not a reader — reaching a response body means indexing
`components['schemas'][…]`. `schema.ts` does that once and re-exports narrow aliases
(`HealthResponse`, `ErrorResponse`, `ErrorReason`). Both rules are enforced by
`tests/wire-contract.test.ts`, which bans re-declaring any shape the backend describes — or any
alias `schema.ts` exports, `ErrorReason` included — anywhere in tracked TypeScript (`src/`,
`tests/`, `config/`) outside `src/api/`, and scans everything but `schema.ts` itself (files
inside `src/api/` included) for direct imports of the generated `./types`.

### Which job checks which half, and why it splits

| Half   | Gate                                                     | CI job     |
| ------ | -------------------------------------------------------- | ---------- |
| Python | `tests/unit/companion/test_openapi_contract.py` (pytest) | `quality`  |
| Node   | `npm run gen:types` + a `git status --porcelain` check   | `frontend` |

CI cannot run the whole pipeline in one job: `quality` has uv and the project's Python
dependencies and **no Node**, while `frontend` has Node and `npm ci` and never runs `uv sync`.
So `openapi.json` is a committed hand-off artifact and each half fails in the gate that owns
it — no new toolchain in either job. A model change with no regeneration reddens pytest; a
regenerated schema with stale TypeScript reddens the frontend job.

Two smaller things worth knowing:

- **Both generated files are in `.prettierignore`,** and must stay there. Prettier would
  reformat each of them (the `.d.ts` uses 4-space indent and long union lines; prettier
  collapses the short arrays `json.dumps(indent=2)` expands), which would fight the generators
  and redden the drift checks. Never add a formatting pass to either generation step.
- **`npm test` does not gate `src/api/schema.test.ts`.** Its `expectTypeOf` assertions are
  erased at runtime, so vitest passes whatever the generated types say. `npm run typecheck` is
  the gate that catches a drifted shape.

## The token layer

Every colour, type role, radius, space, motion and elevation value in the app is a named
custom property in **`src/styles/tokens.css`**, imported first from `src/index.css`. The
values come from the YAML frontmatter of the UX artefact `DESIGN.md`, and
`tests/tokens.test.ts` asserts the whole inventory against that file directly — there is no
second copy of the tokens in this repo to drift.

**`src/styles/tokens.css` is the only file in `ui/` where a literal is legal.** Everywhere
else these bans apply, and each one fails the build:

| Banned                                                                                                                                                                                                                                   | Rule                                                      |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| a hex colour, a named colour, `rgb()`/`hsl()`/`oklch()`/`drop-shadow()`…                                                                                                                                                                 | `color-no-hex`, `color-named`, `function-disallowed-list` |
| a `box-shadow` or `text-shadow` not built from `--shadow-*`/`--glow`                                                                                                                                                                     | `declaration-property-value-allowed-list`                 |
| a `border-radius` not from `--radius-*` — **including every longhand**                                                                                                                                                                   | `declaration-property-value-allowed-list`                 |
| `padding`/`margin`/`gap` not from `--space-*` — **including every longhand**                                                                                                                                                             | `declaration-property-value-allowed-list`                 |
| a literal duration in `transition`/`animation` or their duration/delay longhands                                                                                                                                                         | allowed-list + disallowed-list                            |
| anything that pulses, loops or alternates                                                                                                                                                                                                | disallowed-list + a guard                                 |
| `style={{…}}` on a JSX element                                                                                                                                                                                                           | `no-restricted-syntax` (ESLint)                           |
| native CSS nesting in a shipped stylesheet                                                                                                                                                                                               | a guard                                                   |
| a hard-coded `font`/`font-*`/`line-height`/`letter-spacing` value — and the sibling `word-spacing`/`text-indent`                                                                                                                         | `declaration-property-value-allowed-list`                 |
| any `font-variant-numeric` value except `var(--type-numeric-features)`                                                                                                                                                                   | `declaration-property-value-allowed-list`                 |
| `font: var(--type-numeric)` without its `font-variant-numeric` companion                                                                                                                                                                 | a guard                                                   |
| any type role without its companions — `letter-spacing: var(--tracking-*)` where a `--tracking-*` sibling exists, and `text-transform: uppercase` where DESIGN.md declares the role uppercase                                            | a guard                                                   |
| an `@font-face` anywhere but `src/styles/fonts.css`                                                                                                                                                                                      | a guard                                                   |
| any external URL in the built bundle's `.css`/`.html`; font-CDN hosts, fetchable assets and unreviewed hosts anywhere                                                                                                                    | a guard                                                   |
| a class name that is not flat kebab-case — BEM's `__` and `--` included                                                                                                                                                                  | `selector-class-pattern`                                  |
| a bare `1fr` grid track, or any `minmax()` floored at `auto`/`min-content`/`max-content`                                                                                                                                                 | a guard                                                   |
| clipping a root (`html`/`body`/`:root`/`#root`/`.app-shell`) or `.app-shell-columns`, the one scroller — by `overflow: hidden`/`clip`, by `contain: paint`/`strict`/`content`, or by `clip-path`                                         | a guard                                                   |
| a second full-window `position: fixed` layer outside the shell's stylesheet                                                                                                                                                              | a guard                                                   |
| a viewport height on the document root — `vh`/`dvh`/`svh`/`lvh`… **and `%`**, since `html`'s containing block _is_ the viewport                                                                                                          | a guard                                                   |
| a `--mana-*` token in any stylesheet outside the **data-ink allowlist**                                                                                                                                                                  | a guard                                                   |
| a `--mana-*` token spent through anything but a **fill** property — `background`, `background-color`, `background-image`, `fill`, `stop-color`                                                                                           | a guard                                                   |
| a `var(--mana-*)` anywhere outside a stylesheet — an SVG `fill=` attribute, a value in `index.html`; markup has no allowlist to join                                                                                                     | a guard                                                   |
| an **alarm token** (`--negative`, `--caution`, `--positive`, `--mana-*`, or one nobody has invented) in a stylesheet declared **calm** — the state panel. An ALLOWLIST of calm families, so a new status token fails closed              | a guard                                                   |
| user-facing **prose** outside a declared copy module, and `!`, an emoji or `"something went wrong"` in **any** string in `src/` — both halves read the TypeScript AST, so comments and the `!` operator are out of scope by construction | a guard                                                   |

**And one named NON-ban, with its reason: geometry literals.** A track width, a breakpoint, a
stacking level, a card-tile minimum — these are the one value family that stays a literal, and
saying so explicitly is what stops the next author reading `452px` as drift. There is no token
family to point at, and adding one is not available: `tests/token-usage.test.ts` pins
`declaredTokens.size` at **65** and `tests/tokens.test.ts` asserts every token name
byte-for-byte against `DESIGN.md`'s frontmatter, which contains no layout-width token. An
unenforceable ban is worse than a documented exception, so the rule is:

> A geometry literal is allowed, and it carries a comment naming its source in `DESIGN.md`
> and the reason it is not a token. Where it defines a composition, a test pins it.

`src/components/AppShell/AppShell.css` is the worked example (452px column, 1100px breakpoint,
both pinned in `tests/shell.test.ts`). **c2-9's 480px state-panel max-width shipped, and this
paragraph predicted it correctly** — `DESIGN.md`'s frontmatter carries
`components.state-panel.max-width: 480px`, so the citation beside it in `StatePanel.css` is a
true one rather than a borrowed one. c4-4's 176px grid minimum inherits the same stated rule
rather than a habit — **and a
gate, not just prose** (review round, 2026-07-28): `tests/shell.test.ts` runs the DESIGN.md
citation check over every `px` literal in **every** tracked stylesheet under `src/components/`,
so a later story's uncited literal fails the moment its CSS is staged. Everything
that _can_ come from a token still must — spacing, colour, radius, shadow, type and duration
are gated, and a geometry literal is never a way around one of those.

**This rule was over-applied once, and the correction is worth more than the rule.** Until
story c2-7 the paragraph above named "c2-7's 17px StatChip value" as a future geometry literal.
That prediction was **wrong**, and measuring it is what found the boundary: DESIGN.md's
`components.stat-chip.value-size` is `17px`, but the value is spent through `font-size`, and
`font-size` is **gated** — the `font-*` allowed-list admits only CSS-wide keywords, so
`font-size: 17px` is a lint ERROR with no citation that could rescue it. A geometry literal is
a value with **no token family to point at**; a type size has one, and the answer there is a
different **role token**, never an exception. c2-7's StatChip ships
`font: var(--type-heading)` (which _is_ `500 17px/1.3`) plus
`font-variant-numeric: var(--type-numeric-features)`. See _Sizes the token layer does not
carry_ below.

**The value must be from the right FAMILY, not merely a token.** `padding: var(--radius-pill)`
is invalid CSS that renders as nothing, and the unknown-token guard cannot catch it because
`--radius-pill` genuinely exists — so each allowed-list is keyed to its category prefix.

**Literal durations are an accessibility gate, not a preference.** The reduced-motion block
neutralises motion by zeroing the four `--motion-*` tokens; a hard-coded `300ms` is simply
unreachable by it and plays in full for a user who asked for less motion. `0s`/`0ms` stay
legal, and so do comma-separated lists of tokenised animations.

**Exemptions are path-scoped `overrides` entries** in `.stylelintrc.json`, never a
`stylelint-disable` comment — a comment is something any author can copy into their own file,
and no test can see it. There are **exactly two**, and that list is asserted:

- **`src/styles/tokens.css`** relaxes exactly three colour rules. The shadow, radius, spacing
  and duration bans are keyed on property _names_, and the token file declares custom
  properties, so they never applied to it in the first place.
- **`src/styles/fonts.css`** is exempt from the six **typography** entries only, because an
  `@font-face` legitimately declares `font-family`, `font-weight` and `font-style`. Because a
  stylelint override _replaces_ a rule's whole option object rather than merging into it, that
  entry restates the other seven families verbatim (with a message of its own) — and
  `tests/lint-gates.test.ts` asserts that the override is exactly the base map minus its six
  typography keys, so a family added to the base rule later cannot silently stop applying to
  the font stylesheet. The exemption is not a blank cheque inside the file either:
  `tests/fonts.test.ts` pins fonts.css to exactly one `@font-face` naming exactly one family.

`tests/lint-gates.test.ts` lints both real files under the real config to prove the overrides
work, and lints the same hex — and the same `@font-face` — in a file the overrides do not name
to prove they do not leak.

Why this is a gate rather than a convention: four alternate themes (`gilt`, `graphite`,
`verdigris`, `ink`) already exist in the imported design system, and **two of them are
shadowless**. Under those, `--shadow-raise` is the live state, so a hard-coded _rest_ shadow
does not merely look wrong — it inverts the elevation hierarchy.

Things worth knowing before writing a stylesheet against it:

- **Composing shadows is supported**: `box-shadow: var(--shadow-rest), var(--glow)` passes,
  and so does `none`. What does _not_ pass is a partly-tokenised shadow like
  `0 0 0 1px var(--accent)` — the geometry is still hard-coded and an alternate theme cannot
  reach it. If you need a new composite (a live ring, a pinned ring), **add a token to the
  layer**; do not inline it, and do not declare it in your own file.
- **No component may declare a token.** `tests/token-usage.test.ts` enforces that, along with
  two constraints stylelint cannot express: `--accent-dim` never sits on `--surface-overlay`
  (2.70:1, below the 3:1 non-text floor — use `--accent`), and no `var()` may name a token
  that does not exist. That last one looks like a job for `no-unknown-custom-properties`; it
  is not — that rule is file-scoped and reports every legitimate cross-file reference.
- **The contrast guard catches the same-block case only.** `--accent-dim` and
  `--surface-overlay` in one rule block is a gate. A parent setting the overlay background and
  a child setting the dim border is **not caught** — and that is the normal shape of c6-7's
  suggestion rows and c9-1's swap rows, because DESIGN.md gives the container the overlay.
  Deciding it needs the render tree, which lives in TSX. **Review owns that half**; when you
  review a row component, check it rather than assuming the gate did.
- **Do not use native CSS nesting.** The block reader in `tests/token-usage.test.ts` matches
  innermost braces, so a declaration in a nesting parent is invisible to every guard there —
  including the contrast one. Rather than grow a real CSS parser three stories early, nesting
  is banned so the blind spot is unreachable. Write the selector out in full. A story that
  genuinely needs nesting replaces that reader with PostCSS first; it does not lift the ban.
- **Nothing pulses or loops, at any setting.** Enforced twice: stylelint catches the keyword
  spellings on every `npm run lint`, and `tests/token-usage.test.ts` additionally catches an
  iteration count written into the `animation` shorthand (`animation: pulse
var(--motion-glide) 3`), which a value-level regex cannot tell apart from the numbers inside
  a `cubic-bezier()`. Both layers parse comma-separated lists per animation — a keyword with a
  comma after it used to evade both at once.
- **No inline `style={{…}}`.** Every rule above stops at `*.css`, so an inline style bypasses
  the entire token layer; ESLint bans the attribute. If you need a runtime value (a bar
  height, a grid template), that is a real need — change the rule and say why, in the open,
  rather than discovering it does not apply to you.
- **Reduced motion registers in one place.** The `@media (prefers-reduced-motion: reduce)`
  block at the foot of `tokens.css` zeroes the four duration tokens and carries UX-DR42's
  full inventory. A story that adds a motion adds its fallback _there_. A motion with no
  registered fallback is an incomplete story.
- **The surface ramp is ordered data**, in `src/styles/surfaces.ts`, with a
  `stepsExactlyOne()` predicate. Nesting steps exactly one level
  `well → base → panel → overlay`. Be aware this half is a mechanism plus review, not a lint
  gate: which component renders inside which is decided in TSX at runtime and is not
  statically decidable.
- **Type comes from a role token, always.** The seven `--type-*` tokens are complete `font`
  shorthands, so `font: var(--type-body)` is the whole declaration; `font-size`,
  `font-weight` and `line-height` are carried _by_ the role and are never set beside it. The
  family token `var(--font-sans)` and the `var(--tracking-*)` companions are the only other
  legal typography values — and `--type-numeric-features` is **not** a role: it lives in the
  `--type-*` namespace but is not a `font` shorthand, so `font: var(--type-numeric-features)`
  is banned by name. The ban is keyed on a property-name **family** — `font-stretch` and
  `font-optical-sizing` fail without anyone having listed them, and so does a property CSS
  has not shipped yet — and extends to the tracking siblings `word-spacing` and `text-indent`,
  which are longhands of nothing and have no token: `0` or a CSS-wide keyword only.
- **The numeric role never travels alone.** The `font` shorthand cannot carry
  `font-variant-numeric`, so `font: var(--type-numeric)` on its own renders _proportional_
  digits and a column of counts stops lining up (UX-DR3). Write both declarations in the same
  rule block. This one fails plausibly rather than visibly, which is why it is a gate — twice:
  stylelint admits only `var(--type-numeric-features)` as a `font-variant-numeric` value
  anywhere (every other value, `normal` included, turns tabular numerals off), and
  `tests/token-usage.test.ts` catches the role without the companion in the same block. What
  neither layer can see is a later rule undoing a correct pair through the `font` shorthand
  itself (`.is-compact { font: var(--type-micro); }` on the same element — every declaration
  legal, and the shorthand resets `font-variant-numeric` as a side effect). **Review owns
  that half.**

## The typeface is self-hosted

`Space Grotesk` ships **in this repository**: a 22 kB variable `.woff2` subset committed at
`src/assets/fonts/`, declared by the single `@font-face` in `src/styles/fonts.css`, which
`src/index.css` imports above the token import. The build content-hashes it into the bundle's
`assets/` directory, which is what earns it a one-year immutable cache from `spa.py`; a font
in `public/` would land unhashed at the bundle root and be revalidated on every load.

- **Nothing is fetched from a CDN, ever** (UX-DR2, NFR-06). The imported design system's own
  `fonts.css` is a Google Fonts `@import`, and measured at c2-4's HEAD **nothing in either
  lint layer objected to one**. `tests/fonts.test.ts` scans the committed bundle and fails on
  an external reference: totally, in every `.css` and `.html`; by host family and by asset
  extension everywhere; and against a reviewed list of the hosts that legitimately appear as
  inert strings (`www.w3.org` namespace URIs, React's `react.dev` error links). A new external
  host in the bundle is a red test and a review, not a silent diff in a minified line.
- **One family, forever.** `@font-face` is confined to `fonts.css` by a guard, because an
  `@font-face` _declares_ a family rather than consuming one and so escapes every value-level
  rule. The seven role tokens are 400/500/700, which is what makes UX-DR2's "weight ≥ 400" a
  consequence of the token layer rather than a second rule.
- **Check the bytes, not the render.** A corrupted font and an unapplied `@font-face` look
  identical in a browser — both show `system-ui`. `tests/fonts.test.ts` asserts the `wOF2`
  signature, the exact byte length, and that `git check-attr` resolves the file as binary, so
  a `core.autocrlf=true` checkout on Windows cannot normalise it. That last one protects a
  machine CI never runs on.
- **The licence ships with the font.** `src/assets/fonts/LICENSE-OFL-1.1.txt`, as OFL-1.1
  requires, and the copyright line is in `fonts.css`. **c2-10's footer does not name the
  typeface**, and that is correct rather than an omission: OFL-1.1 requires the licence to
  travel with the font, not an on-screen credit, and the footer's sentence is `DESIGN.md`'s
  verbatim — adding a font credit to it would fail the byte-for-byte gate. If a UI credit is
  ever wanted it is a `DESIGN.md` amendment first.
- **`index.html` preloads the font**, with `crossorigin` — font fetches are always CORS-mode,
  and a preload without it downloads the file twice. The `href` names the _source_ path and
  Vite rewrites it to the same hashed URL the `@font-face` gets.
- **What no test here can prove:** that the glyphs on screen are Space Grotesk. jsdom does not
  load fonts or apply `@font-face`. That check is a browser, with the network throttled to
  offline, and it lives on the epic's manual-testing checklist.

## Components

Set by story **c2-6**, the first component in the codebase, and inherited by every component
story after it. A convention discovered per story is thirty-five chances to diverge, so these
are decided once here rather than re-derived.

**One directory per component, three files, no barrels:**

```
src/components/<Name>/
  <Name>.tsx        the component
  <Name>.css        its stylesheet, imported from the .tsx
  <Name>.test.tsx   colocated
```

- The colocated `.test.tsx` lands in the **`dom`** vitest project automatically and satisfies
  `tests/gate-geometry.test.ts`'s "no `.tsx` test files under `tests/`" rule with no thought.
  Node-project gate and guard tests still live in `ui/tests/`.
- `src` is already in `tsconfig.app.json`'s `include`, so a new component needs **no**
  configuration change. If one seems to, the files have been put somewhere they should not be.
- **No `index.ts` barrels.** Each would be a file per component existing only to re-export,
  and they make `react-refresh/only-export-components` harder to reason about. Import the
  path: `import { AppShell } from './components/AppShell/AppShell'`.

**Class names are flat kebab-case, prefixed with the component** — `app-shell-header`, never
`app-shell__header`. This is a gate, not taste: stylelint-config-standard's
`selector-class-pattern` is `^([a-z][a-z0-9]*)(-[a-z0-9]+)*$`, and BEM's `__` produced **12
`selector-class-pattern` errors** when measured against the shell's own stylesheet. The gate
had already picked a convention; loosening it to fit a habit would have been the wrong repair.

**A component module may export the component and types — but not a helper function, and not
an array or object constant either.** `react-refresh/only-export-components` is an `error`
with `allowConstantExport: true`, and that option is **narrower than its name suggests**:
measured in c2-7, `export const BADGE_TONES = [...] as const` beside the component is a lint
error, because the rule does not treat an array initialiser as a constant. (The c2-6 note here
said constants were fine; that was untested and it is corrected rather than deleted, because
the next author would otherwise measure it again.) Keep helpers unexported, or give the helper
_or the datum_ its own module — `src/components/filled.ts` and
`src/components/Badge/tones.ts` are the two worked examples.

**Component tests assert by ROLE**, through `@testing-library/react` — not by class name and
not by test id. That is what makes a landmark or heading requirement a real check rather than
a decorative one. The one place the shell's own tests reach for a class is the overlay slot,
which is an unstyled positioning container with no role by design, and the test says so.

### The shell owns the window, and the scroll

`AppShell` is `height: 100dvh` with the gutter as padding; its `<main>` — the two-column
region between the header and the footer — is the app's **single scroll container**
(`flex: 1; min-height: 0; overflow-y: auto`). Three consequences for everything built inside
it:

- **No later component introduces a second window-level scroller.** A panel that scrolls its
  own content is fine; a second `100dvh` region is not.
- **The footer is _literally_ always in the window**, which is what UX-DR32 and NFR-08 require
  of the Scryfall and Fan Content attribution. The header and footer are `flex-shrink: 0` so
  the content region is the only child that gives ground.
- **The scrollbar sits at the content region's edge, not the window's.** That is the normal
  appearance of an app-shell SPA, and it is deliberate.

The landmarks are `header` / `main` / `footer`, with **both** columns inside the one `main`.
The right column is a plain container, **not** an `<aside>`: it carries the deck list, which is
FR-05's primary content satisfied as a permanent second column, and `complementary` would
demote exactly the thing the redesign promoted. Per-panel `role="region"` labels (UX-DR44)
belong to the panels.

**There is exactly one full-window overlay layer** (UX-DR38), it lives in `AppShell.css`, and
it is `position: fixed` — never `absolute`. The composition reference is a fixed 1720×1440
slab where the two coincide; a real document is taller than the window, so an absolute overlay
would be sized to the _document_, scroll away with it, and put its 32px inset nowhere near the
window edge. Render into the shell's `overlay` prop rather than declaring a second layer; a
guard in `tests/shell.test.ts` fails the build if one appears.

**The shell is presentation-only** — no state, no fetch, no store, no subscriptions; every
region arrives through a prop, and `tests/shell.test.ts` asserts it. The six primitives hold the
same posture, asserted by the same suite in the same shape.

### The presentation-only primitives

Set by story **c2-7** — `Panel`, `Badge`, `StatChip`, `GroupHeader` — extended by **c2-8** with
`ManaPip` and `ManaCost`, and inherited by the ~20 component stories that compose them without
opening them again. This is the first component _library_ in the codebase, and a library whose
rules are re-derived per consumer has stopped being one.

**Primitives are hook-free, and that is a category rather than a preference.** No `useState`,
no `useEffect`, and specifically **no `useId`** — which is the most reasonable-looking hook one
of these could want, for `aria-labelledby`. The day a primitive needs a hook it has stopped
being presentation-only, and that is a **signal**: the component belongs in a different
category and its story should say so. `tests/shell.test.ts` asserts it over every primitive
with an **exhaustive import list**, hooks keyed by API family (including React 19's lowercase
`use()`), and no `on*` handler prop, no `ref`.

**Region and heading semantics** (UX-DR44, Q4):

- A **titled** `Panel` is a `<section aria-label={title}>` whose title is an `<h2>`. That is
  the per-panel `role="region"` labelling the shell deferred to the panels.
- **`aria-label`, not `aria-labelledby`** — the latter needs a generated id, which needs
  `useId`, which is a hook. The accepted consequence is that `title` is typed `string`, not
  `ReactNode`; DESIGN.md already says panel titles are short label strings.
- An **untitled** `Panel` is a plain unnamed `<section>` and **invents no name**. A section
  with no name has no role at all, which is right — a generic invented name fills the landmark
  list with identical entries to navigate past.
- A **title-less `live` `Panel` does not exist** — `live` requires a `title` (c2-9, Q6). With
  no title to recolour and no dot to hang beside it, only the elevation change is left, and
  `graphite` and `ink` declare both elevation tokens as `none`: under two of the five shipped
  themes a live panel would render identically to a resting one. That is an absent signal, not
  a degraded one. A caller wanting a live marker on an unnamed container is being told to name
  it.
- A **`GroupHeader`** is also an `<h2>`, with its count **beside** the label rather than inside
  it. UX-DR44 read literally makes a panel title and its "CREATURES" divider siblings; that is
  the spec's choice, taken as written, and c4-7 may home a correction if a real screen reader
  disagrees.

**Emptiness is `filled()`, never truthiness.** `src/components/filled.ts` is the settled
answer to `<></>`, `[]`, `' '`, `false` and one-shot iterables — five shapes that render
nothing while looking filled to a naive check, and that cost c2-6 a Greptile round and two
review rounds. It moved up out of `AppShell/` in c2-7 when `Panel` became its second consumer.
Re-deriving it in a new component is the reinvention it exists to prevent.

**Where `filled()` applies, ruled at c2-7's review (2026-07-29):** it gates **optional slots**
(Panel's header pieces) and **components whose empty state is visible chrome** — a `Badge` with
empty children is a bordered, washed, empty pill, so it renders `null`. It does **not** gate
required content slots (`GroupHeader.label`, `StatChip.label`/`value`): those components are
only mounted to show that content, so an empty value there is caller error, and each prop's doc
says so. The same ruling records why those slots are `ReactNode` while Panel's `title` is
`string` — `title` doubles as the region's `aria-label`, which must be a string in a hook-free
component; a slot that is never an accessible name loses nothing by admitting markup.

**Badge clamps a runtime-unknown tone to `neutral`** (review 2026-07-29). The type admits only
the five tones, but tones will arrive as server data (c4-10 legality, c9 tiers), and an
unchecked `badge-${tone}` renders an unstyled pill. The failure mode is "wrong tone", never
"no tone".

**A numeric prop is `Number.isFinite`, never `count &&` and never `count ?`.** `{count &&
<span>{count}</span>}` renders the bare string `0` into the DOM — _something_, so nobody looks
— and `count ? … : null` drops a real zero. "CREATURES 0" is the honest state of an empty
group. `isFinite` closes the other end too: a `NaN` from an arithmetic slip renders nothing
rather than the text "NaN". Deltas follow the same rule and are tinted by `Math.sign`, with
**zero neutral** — a no-change reading tinted green would report it as a win, and
`Math.sign(-0) === 0` is why the tone is derived rather than spelled out in branches.

**The consumer half of this rule has no gate — review owns it.** The tests pin the primitives
themselves; a _consumer_ writing `{count && <GroupHeader …>}` in c4-7's deck list is exactly
the same defect one call site up, and no lint rule or guard reaches it. Stated here (review
2026-07-29) so the asymmetry is a decision rather than an oversight: every other decide-once
ruling in c2-7 got a derived gate, and this one is prose plus review because the failure lives
in files that do not exist yet.

#### Tinting a surface from a semantic token

The mechanism c6-7's suggestion rows, c9-1's swap rows and c9-2's tier rows reuse rather than
each inventing one. DESIGN.md asks a tone to "tint background and border from its own semantic
token — never from hard-coded RGB", and **every obvious spelling of that is banned**:
`rgba(95,212,160,0.12)` by `function-disallowed-list`, and `color-mix(in srgb, var(--positive)
12%, transparent)` by the **same rule** (measured). There is no translucent `--positive-wash`
token and the layer is closed at 64.

The answer is a **pseudo-element wash**:

```css
.badge {
  position: relative;
  isolation: isolate; /* confines the negative layer to this element */
}

.badge::before {
  position: absolute;
  z-index: -1; /* without this the wash covers the element's own text */
  opacity: 0.12;
  content: '';
  inset: 0; /* the PADDING box — so the wash stops at the border */
}

.badge-positive::before {
  background: var(--positive);
}
```

The colour is still the token, so all four alternate themes restyle it — which is the entire
reason the literal is banned. `inset: 0` resolving against the padding box is what leaves the
**border at the token's full strength**, which is how "tints border from its own semantic
token" reads. The `color-mix()` ban stands unchanged; this story shipped no gate relaxation.
`src/components/Badge/Badge.css` is the worked example, with the full argument in its header.

#### Sizes the token layer does not carry

**A role token plus its companion — never a `font-size`, never a new token, never a stylelint
exception.** DESIGN.md's StatChip value is 17px; `font-size: 17px` is a lint error and a
`--type-stat-value` token would break both `declaredTokens.size === 64` and the byte-for-byte
name contract against DESIGN.md's frontmatter, which makes it a UX-artefact change rather than
a frontend one. `--type-heading` **is** `500 17px/1.3`, so:

```css
.stat-chip-value {
  font: var(--type-heading);
  font-variant-numeric: var(--type-numeric-features);
}
```

The accepted consequence is a line-height of 1.3 rather than the numeric role's 1.4 —
immaterial on a single-line number, and the alternative is unavailable rather than merely
worse.

**And the sibling ruling, for GEOMETRY DESIGN.md does not carry at all** (story c2-8). A `px`
literal is a named non-ban _provided its citation is true_ — but DESIGN.md's `components.*`
frontmatter declares **no mana entry**, so a pip's `16px` would meet the citation gate with
nothing truthful to cite. That is c2-7's `min-width: 76px` problem with one difference: a chip
can size to its content and **a pip must have a size**. The answer is to make the problem
disappear rather than negotiate with it — **express the geometry in `em` off the type role the
component already carries**, so no literal exists and no citation can be untrue:

```css
.mana-pip {
  min-width: 1.25em;
  height: 1.25em;
  border-radius: var(--radius-pill);
  font: var(--type-numeric);
}
```

**Measured, and worth knowing before reusing it:** `em` on width and height resolves against the
**element's own** font-size, not the inherited one. Because this element carries the numeric
role (13px), the pip is 16.25px everywhere rather than scaling with its container. Moving the
role to an inner span to recover that is **worse, not merely different** — a glyph's size comes
from a role token and is therefore fixed, so a context-relative circle would be 12.5px around a
13px numeral inside a `--type-micro` caption. **A fixed glyph cannot live in a varying circle.**

**And `min-width` + `height`, never `width`** — with **no `overflow: hidden`**. Gleemax's
`{1000000}` is seven glyphs in one symbol. A fixed width clips it, and clipping is the
layout-shaped member of "silently wrong": the defect hidden rather than fixed. A pill radius
already supports the fix, because a circle _is_ a pill whose width equals its height.

#### The WUBRG tokens are data ink, and joining the allowlist is how a story says so

Set by story **c2-8**, which wrote the `--mana-*` tokens' **first consumer in the repository**.
Measured at that story's baseline: `git grep -- '--mana-'` over `ui/` returned seven hits, all
seven of them the declarations in `tokens.css`. UX-DR7's "curve bars, mana pips and
colour-identity dots ONLY, never a button, border, background or an unstacked curve bar" had
been enforced by nothing for four stories — a rule with no consumer and no gate is a sentence.

The gate is in `tests/token-usage.test.ts` and has two halves (plus a markup half, below):

- **Which files may reference a `--mana-*` at all** — the `MANA_DATA_INK` allowlist, each entry
  carrying the reason that file is data ink. Today it is `ManaPip.css` alone. **c4-8** (stacked
  curve segments) and **c4-9** (the colour-distribution bar) add their own entry, in their own
  story, in the open — the same protocol `PRIMITIVES` uses. A non-vacuity test proves every
  entry is a path git actually tracks, so a rename fails loudly rather than silently permitting
  nothing.
- **Which properties may spend one** — an **allowlist**: `background`, `background-color`,
  `background-image`, `fill`, `stop-color`. Nothing else. It is an allowlist rather than a ban
  list on purpose, and that is the general lesson: "ban the family, never enumerate members" has
  a stronger form than a wider ban. A ban keyed on `/^border/`, `/^outline/` and `/shadow$/` is
  still a list of families its author thought of, and `caret-color`, `accent-color`,
  `text-decoration-color` and `column-rule-color` are not in it.

**The markup half** (added at c2-8's review): both halves above read stylesheets, so a
`var(--mana-*)` spent from markup — an SVG `fill` presentation attribute, a value in
`index.html` — would be policed by nothing. A third check scans every git-tracked non-CSS source
file and allows **none**: there is no markup allowlist to join, because the way in is always a
class in an allowlisted stylesheet, the way `ManaPip` does it. c4-8/c4-9: your chart segments
take a class, not a `fill=` attribute.

**The half no static reader can decide is review's**, declared in the guard's own comment the
way `surfaces.ts` declares its own: whether a given curve bar is genuinely **stacked** is a
property of the data bound to it and the elements composed at runtime. **c4-8's reviewer must
look**; the gate will not have looked for them. The same comment declares a second residual:
chrome-shaped spend **through an allowed property in an allowlisted file** (a hover tint, a
button-like background) passes both halves — the allowlist _reason_ is what review checks it
against.

**`--mana-gold` is the family's seventh token and has no consumer yet** — deliberately: it is
not a cost colour, so `MANA_COLOUR_ORDER` (the parser's vocabulary) excludes it and the pip
class-coverage guard derives 21 classes from six colours. Its first consumer (likely c4-9's
colour-identity bar) joins `MANA_DATA_INK` in the open and moves the guard's spent-token count
from 6 to 7 there, not silently.

**One class per colour, never a token name built at runtime.** The composition reference writes
`'var(--mana-' + color + ')'` into an inline style. The lint error is the least of it: a
runtime-built token name is invisible to `findUnknownTokenReferences`, so a bad colour renders a
_transparent_ circle no test can see. The indirection a component author reaches for instead —
`.mana-pip-w { --pip: var(--mana-w) }` — is a **guard** failure, since only `tokens.css` may
declare a custom property. So `ManaPip.css` declares all 21 classes (six colours and all fifteen
unordered pairs), and a guard derives those 21 suffixes from `MANA_COLOUR_ORDER` and proves each
exists **and names a real token**.

#### A parser is total, or it is silently wrong

Set by story **c2-8**, and it generalises past mana: **scan the whole input; never enumerate what
you accept and discard the rest.** `c3-*`'s response handling and `c5-*`'s envelope parsing meet
the same shape.

`ManaCost/parse.ts` returns a token list for **every** string and throws for none. Every
character of the input survives in some token's `raw` — asserted by re-joining them — so an
unrecognised braced symbol comes back as `unknown` (rendered as a pip showing its own text) and
anything outside braces comes back as `text`. There is no `else` branch that discards, because
there is nothing left for one to discard.

The rule exists because the alternative _looks fine_. The composition reference's
`String(cost).match(/\d+|[WUBRGC]/gi)` drops hybrid, generic-hybrid, Phyrexian, `{X}`, `{S}` and
the `//` separator — measured against this repository's own 32,318 real costs — and renders a
cost that is wrong without looking wrong. A `match()` of known patterns discards the rest **by
construction**, so "never silently drops" cannot be a property of the symbol table; it has to be
a property of the tokeniser's shape. Tests prove it with a symbol family **invented for the
test** (`{Q/W/E}`), which no enumeration in the module mentions.

#### Naming a graphic whose whole meaning is colour

Set by story **c2-8** (UX-DR18, UX-DR44), and **c4-8's curve and c4-9's colour bar reuse it
rather than each inventing one.**

**`role="img"` plus `aria-label` on the wrapper; the coloured parts inside stay decorative.**
This is required, not stylistic: `aria-label` on a bare `<span>` is **name-prohibited** on
`role="generic"`, and screen readers are permitted to ignore it — several do. A `role="img"`
element's children are presentational, so nothing double-announces.

**The name is built by a pure formatter beside the parser and unit-tested with it.**
`{2}{W/U}` reads _"2 generic, white or blue"_; `{B/P}` reads _"Phyrexian black"_. An unknown
symbol reads as its own raw text (`{HW}` → _"HW"_), which is honest rather than silent — the
same rule the pips follow, in words.

**A standalone `ManaPip` is decorative by default**, with an **opt-in** `label`. c4-9's legend
puts a pip beside its own text count, and a doubled announcement there is the flooding UX-DR45
warns about, so the default is the safe direction.

#### No symbol lookalike, including the Phyrexian Φ

UX-DR7's "no symbol lookalikes" is not only a claim about a pip's outline. Reproducing the
Phyrexian mana symbol, a tap symbol or a set symbol **inside** the pip is the same trade-dress
imitation by another route. So the pip has no border, no inner ring and no drawn glyph, and the
Phyrexian marker is a plain letter **`P`** in the app's own typeface — the same glyph slot the
generic count, `{X}` and every unrecognised symbol already use. That single slot is what keeps
the ban cheap: **do not add a mana-symbol font or icon set** (UX-DR7 bans "icon fonts styled as
mana symbols" by name, and it would be a new dependency besides).

#### `--accent-dim` is not written in a primitive at all

UX-DR6 puts it at 2.70:1 on `--surface-overlay`, below the 3:1 non-text floor, and badges land
on overlay surfaces inside every agent view. The `findAccentDimOnOverlay` guard is
**same-block only**, and a badge whose _container_ supplies the overlay background is precisely
the cross-block case that guard declares it cannot see. So the rule is not "check the guard" —
it is **do not write the token here**. The composition reference uses it for the accent badge's
border; that is the drift this rule exists to stop.

### The state panel, and where user-facing copy lives

Set by story **c2-9**. Every later story with a sentence in it — c2-10's attribution, c4-3's
"Unknown card", c4-12's empty-deck line, c6-6's empty push — joins this mechanism rather than
inventing one.

**`EXPERIENCE.md` is the copy, and a test reads the artefact itself.** `tests/copy.test.ts`
parses the Voice-and-Tone table out of `EXPERIENCE.md` and asserts every headline and body
**byte-for-byte** against `src/components/StatePanel/copy.ts` — the same pattern
`tests/tokens.test.ts` uses for `DESIGN.md`, and for the same reason: two spellings of one
value is one value that will drift. "Matches verbatim, reviewed by eye" is the claim this repo
already decided not to accept for tokens.

**`EXPERIENCE.md` writes two fields; `DESIGN.md` renders three slots.** The Body is split at
sentence boundaries into `guidance` and `action` parts, **in source order**, and the split is
gated by concatenation: re-joining the parts must reproduce the artefact's Body exactly. So
nothing is written that `EXPERIENCE.md` did not write — the panel only knows which sentence is
the action. Two consequences are real states rather than defects: the **action line is
optional** (`database-updating` has none, and inventing one would be the lie), and the
**guidance may be empty** (`no-active-deck` is a single sentence which _is_ its action).

**A command chip is derived from the copy's own backticks**, never authored per state. That is
what let the two states c2-9 added need no bespoke renderer, and it is why
`` `initialize_database` `` and `` `artificial-planeswalker companion` `` both render as chips
with one mechanism.

**How a later state joins.** Add the row to `EXPERIENCE.md`'s copy table in the same two-field
shape; add the `StateKey` and its parts to `copy.ts`; give it a home in `states.ts` — either a
reason token in `PANEL_FOR_REASON` or an entry in `CLIENT_ONLY_STATES` — and decide its
`RETRIES_QUIETLY` value. All four are **total maps**, so three of the four steps fail
`npm run typecheck` if you skip them, and the fourth fails `tests/copy.test.ts`.

**Where copy may live is itself a gate.** `tests/copy-rules.test.ts` enforces UX-DR33 in two
halves, because either alone is worthless:

- **The file half** — user-facing prose lives only in the modules listed in `COPY_MODULES`,
  each with the reason it owns copy. A sentence anywhere else fails, naming the module it
  belongs in. Adding a copy module is the open way to grow this, exactly as `MANA_DATA_INK`
  grows.
- **The content half** — no `!`, no emoji, no "something went wrong", in **any** string in
  `src/`. Keyed by **character family**: emoji by `\p{Extended_Pictographic}`, and exclamation
  marks by NFKC-normalising first, so Unicode's own compatibility decompositions enumerate
  `！`, `︕`, `﹗`, `‼` and `⁉` instead of a hand-written list.

Both halves read the **TypeScript AST**, not the file text, and that is load-bearing: the
generated `types.d.ts` quotes the banned phrase in a JSDoc comment, and `!` is an operator in
nine of eleven component modules. A comment is not a string node and `!x` is not a string
literal, so both are out of scope **by construction** rather than by a special case listing
today's files.

**What the guard does not decide, and review does.** Whether a sentence is _second-person and
blameless_ is not statically decidable, and it is the most important half of UX-DR33. Copy
assembled from single words at runtime (`describeManaCost`) and a name reaching `aria-label`
through an expression are the other two residues. All three are declared in the guard's own
header, the way `surfaces.ts` declares its half.

**Retry is a property of the state, and it is written where c3-9 will read it.**
`RETRIES_QUIETLY` in `states.ts` is total over every panel. `database-updating` and
`database-not-initialized` retry quietly, because their copy promises the page will come alive
on its own. **`internal-error` must never retry** — `types.d.ts` states it as a wire contract:
the companion hit a deterministic bug, so re-issuing the request re-hits it, and a quiet loop
would hammer a broken backend behind a calm panel that never changes. Its next action is a
manual restart. `database-updating-stalled` is the escalation of the quiet retry that did not
work, so it stops. **c3-9 owns the polling, the threshold and the transitions**; c2-9 ships no
fetch, no `setTimeout` and no hook at all.

**"Exactly one panel at a time" is the caller's**, not the component's. There is one `left`
slot in `AppShell` and no manager — do not build a state-panel registry.

**No error styling is a gate, not a review note.** `tests/token-usage.test.ts` holds
`StatePanel.css` to an **allowlist** of calm token families, so `--negative`, `--caution`,
`--positive`, a `--mana-*` red-by-another-name and a status token nobody has invented yet all
fail closed — including through a `var(--negative, …)` fallback. Other components legitimately
spend those tokens (c4-10's format check maps a violation to `negative`); the scope is the
rule, and a later calm surface adds its file with its own reason.

**A second family exists, and it is not a hierarchy.** `--font-mono` (c2-9, Q2) styles command
literals inside state-panel copy and nothing else — a string the user is about to retype into a
terminal, which is data. It is a system stack: no `@font-face`, no download, so the offline
guarantee is untouched. UX-DR2's "hierarchy never comes from a second family" stands.

### The footer attribution

Set by story **c2-10**, the last of Epic C2 and the only one whose deliverable is a **condition
of public release** rather than a design choice — `DESIGN.md:375` says so in bold, and NFR-08
and UX-DR32 say it twice more. Every other C2 story could ship slightly wrong and be corrected
in Epic 4; this one shipping wrong is a licensing defect.

**Copy is gated against the artefact that _wrote_ it — which here is `DESIGN.md`, not
`EXPERIENCE.md`.** c2-10 inherits c2-9's verbatim-gate _mechanism_, not its source file.
`EXPERIENCE.md`'s Voice-and-Tone table has **no footer row**: its footer entry (`:101`) is
behavioural ("Static … links persistently underlined … and open in a new tab") and never writes
the words. The words exist in exactly one place — `DESIGN.md`'s `Footer attribution` bullet,
inside one pair of straight double quotes — so `tests/attribution.test.ts` reads that. Two
artefacts, two gate files, deliberately. **A later story asks which artefact wrote its sentence,
not which gate file already exists.**

The parse selects the bullet **by structure** (the bold label at the head of a top-level list
item), never by line number, and it **throws** on all four ways the artefact can change shape
underneath it: no such bullet, no quoted run, more than one quoted run, and a duplicated label.
c2-9's review is the reason — a parser that silently tolerates a duplicate is a parser that
stopped checking.

**The sentence is a list of parts, not three strings.** Two runs are links; the rest is text.
Five separately-authored fragments could drift apart while each stayed individually plausible,
so the parts carry link-or-text tags and `sentenceOf()` re-joins them — asserted byte-for-byte
against the artefact. Nothing is authored that `DESIGN.md` did not write, **link labels
included**. The hrefs are the canonical ones the repository's `NOTICE` already publishes, and
that is asserted too, so the app and the licence docs cannot drift.

**The shell owns the footer's layout; the component owns its ink** (Q2, Brad 2026-07-30).
`.app-shell-footer` used to set `font: var(--type-micro)` and `color: var(--text-tertiary)`,
while the attribution needs `--text-secondary` (9.3:1 — legally load-bearing text gets a passing
tier, not a muted one). Two single-class selectors setting `color` is a source-order race
decided by import order, and this repo has already been bitten once by a cascade it did not
model. So the appearance moved out **wholesale** rather than being overridden: the shell rule
keeps `flex-shrink: 0` — the pinning mechanism, a property of the slot — and `Footer.css`
declares every value `DESIGN.md` assigns to `components.footer-attribution` exactly once.
`tests/shell.test.ts` asserts that only one block in the whole tree declares that colour, so the
race cannot reappear.

**"Every surface" is structural, not enumerated** (Q3). There is one `AppShell`, one `footer`
slot and no router, so **every surface renders through `App.tsx`** — and `App.test.tsx` asserts
the attribution inside the `contentinfo` landmark by role and by text, plus that the shell's
placeholder is not what is showing. An enumerated surface list would be a list its author
thought of, which is this epic's standing finding. It holds through Epic 6 without amendment:
c6-5's agent view is an **overlay inside the shell**, not a route that replaces it, so the
footer survives it by construction. **A future surface renders through `AppShell`.**

**The footer declares no landmark of its own.** The shell's `<footer>` is the one `contentinfo`
(UX-DR44), and `AppShell.test.tsx` asserts exactly one of each landmark. `Footer.test.tsx`
asserts the absence standalone, so it is a property of the component rather than of today's
arrangement.

**10px all-caps is the spec, taken deliberately** (Q1). `DESIGN.md` assigns footer attribution
to `{typography.micro}` and declares that role uppercase, and the companion guard **derives**
the requirement from the artefact's own `textTransform:` key — so the legal notice renders as
10px capitals. `text-transform` does not touch the DOM text, so the verbatim gate, the
copy-rules content half and the screen reader are all unaffected; only the render is. Whether it
is comfortably readable is on the epic manual-testing checklist, and if it reads badly the
correction is a `DESIGN.md` amendment in Epic 8's release-readiness pass, made with the rendered
page in hand.

### Adding an external host to the bundle

`tests/fonts.test.ts` R4 asserts that the set of external hosts in the built bundle equals a
reviewed baseline, and it is **deliberately brittle**: a new host is the moment a human decides
whether the offline guarantee (NFR-06) still holds. Story **c2-10** was the first to need one —
two, in fact — so the protocol is written down rather than inferred from the diff:

1. **Add the exact host string to `REVIEWED_HOSTS`, with the reason it is not a fetch.** A host
   with no stated reason is a host nobody checked. "It is inert" is a claim about behaviour.
2. **The exact string, never a family.** `scryfall.com` and `www.scryfall.com` are different
   hosts to a set check, as are `company.wizards.com` and `magic.wizards.com`. This is the one
   list in the repo where c2-9's "a guard proven only against spellings it lists" bites hardest,
   so the evasion probe for a new entry must use a spelling the list does **not** contain —
   including the protocol-relative form (`//host/path`), which R4 also matches.
3. **The URL lives in TypeScript only.** R1 bans every external host from any `.css` or `.html`
   in the bundle outright, so an href belongs in a module — never in `index.html`, never in a
   `content:` or `url()`. R3 separately bans any fetchable asset extension, so a link to a
   `.pdf` copy of a policy would be red even from TypeScript.

**Adding a host does not weaken the offline guarantee, and the distinction is the point.** The
two hosts c2-10 added are `href`s on `<a target="_blank">` elements: a human clicks them, the
app never requests them, and the page renders identically with the network blocked. R4 is what
keeps that claim honest instead of asserted — a dependency that starts phoning home goes red and
a human looks.

## What the gates cannot see

Every guard in `ui/tests/` is a static reader. Several of them are load-bearing enough that it
matters exactly where they stop — and each one that stops somewhere **says so in its own source**.
This section is the index of those declarations, so a reviewer can find the edge without reading
fourteen test files first. It is not a list of bugs: every entry is a limit its author chose,
usually because closing it needs the cascade, the render tree or a human eye.

The rule this encodes: **a declared blind spot is still a claim.** c2-6 lost a round to one —
"neither pass order is safe" was true, "this one fails on the rarer input" was never measured, and
it was hiding a failure that blinded every guard in the file. If an entry here is load-bearing for
your story, verify it rather than inherit it.

| What is invisible                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | Where it is declared                                                                                                                                                              | Who owns the other half                                                         |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **The cascade.** A correctly paired block undone by a later rule in another block reads as clean — resolving it needs specificity, source order and the element's real runtime class list. Applies to the numeric-pairing guard (UX-DR3 tabular numerals) and to the tracking/text-transform companion it spawned.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | `tests/token-usage.test.ts:397`, `:473` — and _asserted_, not merely described, at `:1267` and `:1434`                                                                            | Review                                                                          |
| **Untracked files.** Every file-walking guard is keyed on `git ls-files`, so a stylesheet, font or module that is not yet committed passes vacuously. The limit is "invisible until committed", not "never seen" — CI sees it the moment it lands.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | `tests/shell.test.ts:88`, and the same construct in `token-usage.test.ts:43`, `gate-geometry.test.ts:23`, `wire-contract.test.ts:60`, `copy-rules.test.ts:86`, `fonts.test.ts:53` | CI, one commit later                                                            |
| **Cross-block and cross-file CSS.** The block reader matches innermost brace pairs, so a declaration in a nesting parent is in no block at all (made unreachable by the nesting ban, which is asserted). `findAccentDimOnOverlay` was widened from block-local to same-file; **cross-file remains open**.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `tests/token-usage.test.ts:74`, `:166`, `:209`; `tests/shell.test.ts:41`                                                                                                          | Review                                                                          |
| **Runtime-composed class lists.** A full-window layer assembled at runtime from two classes, a root selector reached through an unrecognised class, or an overflow set from JavaScript — the render tree lives in TSX and is chosen at runtime.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `tests/shell.test.ts:35`                                                                                                                                                          | Review                                                                          |
| **`var()` indirection.** `overflow: var(--clip)` hides the keyword in a custom property declared elsewhere, evading every value-keyed check. In the data-ink guard the same hole is closed _indirectly_ — declaring a `--mana-*` outside `tokens.css` is itself a failure two guards up, which is what makes that one safe rather than lucky.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | `tests/shell.test.ts:39`; `tests/token-usage.test.ts:604`                                                                                                                         | The token-location guard, or review                                             |
| **External hosts (`REVIEWED_HOSTS`).** Deliberately brittle: the _set_ of external hosts must equal a reviewed baseline, in both directions, so both a new host and a stale entry go red. A runtime-constructed URL (`fetch('htt' + 'ps://…')`) and an IPv6-literal host are still invisible.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | `tests/fonts.test.ts:320`, `:337`, `:520`                                                                                                                                         | A human, by design — that is the point of the brittleness                       |
| **Whether a curve bar is stacked (UX-DR7).** Not a property of the stylesheet: it is a property of the data bound to it and the elements composed at runtime. c4-8's reviewer must look.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | `tests/token-usage.test.ts:596`                                                                                                                                                   | Review, at c4-8                                                                 |
| **Whether copy is second-person and blameless (UX-DR33).** Not statically decidable, and the most important half of the rule. Four further copy residues are declared beside it: runtime-assembled copy, `aria-label={call()}`, Latin-script-only prose detection, and a single word as a JSX expression child.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `tests/copy-rules.test.ts:54` and `:57`–`:69`                                                                                                                                     | Review, at c4-3 / c4-12 / c6-6                                                  |
| **Anything outside `*.css`.** Every token-layer gate stops at stylesheets: `style={{ padding: '18px' }}` in a `.tsx` file is invisible to all of them.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | `tests/lint-gates.test.ts:100`                                                                                                                                                    | Review                                                                          |
| **Rendering, at all.** jsdom has no layout engine and loads no fonts, so "the glyphs on screen are Space Grotesk" and "a wide glyph fits its pip" are both unprovable here; the latter is pinned by a source read instead.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | `tests/fonts.test.ts:20`; `tests/token-usage.test.ts:1001`                                                                                                                        | The epic manual-testing checklist                                               |
| **Quotes inside copy strings.** Two artefact parsers capture with `"([^"]*)"`, so a copy string containing a double quote truncates the read. Both declare the ceiling; `copy.test.ts` also fails loudly on a duplicated row label rather than silently taking one.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | `tests/attribution.test.ts:119`; `tests/copy.test.ts:72`                                                                                                                          | The parser fails loudly; review owns the wording                                |
| **String literals containing `//` or `/*`.** The comment-stripper in the unknown-card pairing gate is regex-based, not a lexer: a future string in `states.ts` holding either marker (a URL, a glob) truncates `STATES_CODE` from that point. Guarded by an end-of-file anchor — the file's last live statement must survive stripping — so a mid-file truncation fails loudly rather than disarming the pairing regexes.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `tests/unknown-card-copy.test.ts`, the `STATES_CODE` comment and the EOF anchor in its pairing test                                                                               | The anchor fails loudly; review owns any new `//` string                        |
| **Whether a binary response body is really binary.** The generated contract types `GET /api/card-image/{scryfall_id}`'s 200 as `content: { "image/*": string }` — `openapi-typescript` renders `format: binary` as `string`, not `Blob`. Nothing goes red if a consumer trusts that and calls `.text()` or `.json()` on an image. **c4-4 must read the response as a blob and must not derive its handling from the type.** Measured at c3-5, the first non-JSON success body in the document.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | `ui/src/api/types.d.ts`, the `read_card_image_…` operation; `scripts/dump_openapi.py`'s module docstring                                                                          | Review, and c4-4's own tests                                                    |
| **Whether an image tile asked for the face it rendered.** The backend proves it serves the right face from the right URL (`test_routes_card_image.py` asserts on the bytes AND on what the transport was asked for), but jsdom has no layout engine and loads no images, so "the back face of a transform card is on screen" is unprovable in this suite. Both halves of the pairing exist only in a real browser.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | `tests/unit/companion/test_routes_card_image.py::TestTheFourShapes`                                                                                                               | The epic manual-testing checklist                                               |
| **A cross-project import breaking `tsc` while `npm test` stays green.** `ui/tests` is `nodenext` and `src` is `bundler`, so a `tests/` file importing an app module that has its own relative imports fails `tsc -b` — cascading into errors that name the importee's type asserts, not the import. Vitest resolves it fine, and `tsc -b` caches, so it can hide. Run `npx tsc -b --force` when touching cross-project imports.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `tests/unknown-card-copy.test.ts`, the `STATES_TS` comment                                                                                                                        | Review; ledgered in `deferred-work.md`                                          |
| **Whether a wire description addresses a TypeScript reader.** The backend gate bans the _shapes_ of Python-internal prose (Sphinx role markup, any line-anchored Google section header, doctest prompts) from every OpenAPI description — but "Supports conversion from SQLAlchemy CardModel instances" trips none of them and is exactly the sentence c3-2 had to rewrite. Structurally clean, semantically internal. Not statically decidable, like UX-DR33's second-person half.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | `tests/unit/companion/test_openapi_contract.py`, the `PYTHON_INTERNAL_FAMILIES` docstring                                                                                         | Review, on every story that adds or edits a wire schema                         |
| **Whether a deck-construction _rule_ was reimplemented in the backend shell.** c3-3's guard bans five families from `src/companion`: the name `legalities` in **any** position (attribute, subscript, `getattr`, or a string bound to a variable and used as a key later); any import of the validator module, of a name from it outside the projection surface, **or of any ancestor package** (`import src.logic` / bare `import src` bind a name from which the validator is a plain attribute chain — closed at round-2 review); the limits `60`/`15` appearing anywhere as a number, in any position, `int` or `float`; two or more Scryfall format names together **anywhere under one container** — nested tuples, dict keys _and_ dict values all count (widened from direct-elements-only at round-2 review); and any `.quantity` access. **Five declared holes.** (1) `1` is outside the limit family — the singleton limit is 1, but `> 1` / `== 1` are ubiquitous, so banning it would be noise; a shell reimplementing the _singleton_ rule specifically would pass. (2) **Adjacent-literal spellings** — `<= 59` / `>= 16` / `>= 5` are the same rules with the off-by-one integer, but the adjacent set is unbounded and its small members as ubiquitous as `1`; ruled a declared limit (2026-08-01), same stance as (1). (3) **`4` joined that set at c3-6** — the copy limit is 4 and so is every innocent four; c3-6's `images.FETCH_CONCURRENCY = 4` (a CDN concurrency cap, no deck vocabulary anywhere near it) was the first measured collision, and keeping `4` in while `3`/`5`/`16` were already declared out was the order of discovery rather than a stance. The copy limit is still caught by the `.quantity` family — enforcing it means counting copies — leaving only a shell that counts copies _without_ reading `quantity` (`len(rows) > 4`), which is the same obfuscation stance as (2). Both directions are probed. (4) A fully dynamic form — a limit read from config, a key assembled from fragments — defeats an AST walk by construction; `test_import_boundary.py`'s stance applies, and _"a guard satisfied by obfuscation is theatre"_ makes it a reviewer's call. (5) A rule written in TypeScript is invisible to every Python guard. Everything else here was **measured**: fifteen planted evasions run through the function and all fifteen caught, including a seven-line composite that the first version of this guard missed entirely. | `tests/unit/companion/test_routes_format_check.py`, the `find_rule_violations` docstring and `TestNoRuleInTheShell`                                                               | Review, on any story that computes legality client-side                         |
| **How long a card image can take, and that it is queued at all.** c3-6 puts every outbound image fetch through one process-wide pacer: **0.1 s between fetch starts, at most 4 open at once**. Nothing about that reaches the wire — `openapi.json` and `types.d.ts` are byte-identical across the story, deliberately (Q4) — so **the generated types tell c4-4 nothing about it, and this row is where the number lives instead.** What to expect when building the tile: a cold deck grid is **~99 distinct fetches** (measured — a real 100-card deck resolves to 67–99 distinct card ids because basic lands collapse), so the **last tile starts ~9.8 s after the first** and the whole paint is the epic's _"roughly 12 MB over roughly 10 seconds"_. That is an **expected observation, not a defect** — NFR-05 excludes first-fetch image paint from its budget — but a tile that shows a spinner with no skeleton, or that gives up on a slow response, will look broken for reasons that are not the CDN's. There is deliberately **no queue-wait ceiling** and no `504`-shaped answer: a request queues until it is served or the client disconnects (cancelling releases the slot immediately). The numbers are a property of _this_ corpus and _this_ machine, which is exactly why they are written here and not published as a wire promise — c3-2's "a true count read as a false rule".                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `src/companion/app/images.py`, the `FETCH_SPACING_SECONDS` and `FETCH_CONCURRENCY` docstrings; `tests/unit/companion/test_images.py::TestTheColdDeckPaint`                        | c4-4, which owns the tile; c10-3 owns the real-bytes and real-latency profiling |
| **Whether a credential's _vocabulary_ reached the generated types.** c3-4's leak scan checks `types.d.ts` for the token value itself (which is exact and total) **and** for four literal markers — `agent_token`, `mint_token`, `companion.json`, `Bearer`. The value check is a real gate; the marker list is an **enumeration, not a family**, and the project's own standing agreement says to ban the family instead. It is kept as an enumeration deliberately, because the family here is _"prose that teaches a browser where a credential lives"_ and that is no more statically decidable than UX-DR33's blameless-copy rule. A docstring explaining the credential in words the list does not contain would pass. What genuinely holds the line is structural and lives elsewhere: the credential is read from `request.headers` inside a dependency, so no `securitySchemes` component and no per-operation `security` block can be generated at all (asserted in `test_committed_schema.py`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `tests/unit/companion/test_discovery.py::test_the_token_leaks_into_no_surface_of_the_route_that_reads_it`, and `test_committed_schema.py::test_no_security_scheme_is_documented`  | Review, on any story that adds an agent-only endpoint                           |

Backend guards carry the same discipline. The two that matter most here:
`tests/unit/companion/test_import_boundary.py` is **AST-only**, so it sees modules no test imports
but is defeated by `getattr(repo, "create_deck")` — its own docstring forbids routing around it by
convention, because _"a guard satisfied by obfuscation is theatre"_. And
`tests/unit/companion/test_openapi_contract.py` compares the committed schema byte-for-byte against
the live app, which catches drift but **not** meaning: it asserts `Args:` and `>>>` never cross the
wire, and c3-1 found that MCP-internal prose and Sphinx role markup (`` :class:`X` ``) sail past it
untouched. That one is a look, not a gate that will tell you.

One more backend limit, added by **c3-4** and worth knowing before trusting an `Allow` header: `errors.supported_methods` recomputes a 405's `Allow` as the union of every partially-matching route, because Starlette builds it from the _first_ match alone and therefore under-reports any path served by more than one method (`/api/active-deck` measured `Allow: GET`, omitting its `PUT`). Recomputing needs a flattened route list, and FastAPI 0.140 does not flatten included routers into `app.routes` — so the walk is written **against attributes**, and a structural change upstream makes it find nothing and silently fall back to Starlette's incomplete header rather than raising inside an error handler. That soft failure is deliberate; the thing that would catch it is a test, not the code.

## Adding a source directory

Every linted `.ts`/`.tsx` file must belong to a tsconfig — ESLint's `projectService` errors
on any file that does not. `src`, `tests/fixtures/a11y` and `tests/fixtures/tsx` are in
`tsconfig.app.json`;
`vite.config.ts`, `config/` and `tests/` are in `tsconfig.node.json`. A new top-level
directory needs adding to one of those two `include` lists.

## Not here yet

The `/ws` proxy entry is **c5-6**. **c4-1** owns the runtime `fetch` layer, the store and its
in-flight deduping, and **c4-2** owns the deck bootstrap that calls `GET /api/decks` — c2-3
deliberately ships the generated types with no fetch helper, so neither of those designs is
pre-empted. **c3-1** shipped the endpoints themselves and no client-side code at all, so the
generated types still have no runtime consumer.

The application shell landed in **c2-6**, so the token layer now has a real consumer and
`src/App.css` is gone with the placeholder it styled. What the shell deliberately does _not_
build is every region it holds open, each of which renders a placeholder line naming its owner
until that story lands: card detail is **c4-5**, the deck list is **c4-7**, the format check is
**c4-10**, the agent-view nav pills are **c6-8**, and the agent view that drops into the overlay
slot is **c6-5**. The `h1` carries the product name provisionally; **c4-2** replaces its content
with the deck name and nothing about the element moves.

**Two regions are already filled, and both by displacement rather than deletion.** The pattern
is c2-9's decide-once ruling, applied twice now: the shell's placeholder still fires whenever
its slot is empty, `AppShell.test.tsx` still asserts it against the component's own props, and
what changed is only which of the two the running app shows. Each displacement is recorded in
`App.tsx` beside the prop that causes it.

- **The left column, as of c2-9.** `App.tsx` passes the no-active-deck `StatePanel` into the
  `left` slot, displacing the placeholder that names c4-4 and c4-8. It is honest rather than a
  demo: with no fetch layer and no store (both **c4-1**), there genuinely is no active
  deck. **c4-2 / c4-4** replace the static choice with the real one and **c3-9** owns the
  transition (FR-22).
- **The footer, as of c2-10.** `App.tsx` passes `<Footer />` into the `footer` slot. Unlike
  every other region this one is **not waiting for data** — the attribution is a condition of
  public release (NFR-08), correct from day one, and no later story replaces it. See _The
  footer attribution_ above for the three rulings it carries.

Eight presentation primitives have landed — `Panel`, `Badge`, `StatChip` and `GroupHeader` in
**c2-7**, `ManaPip` and `ManaCost` in **c2-8**, `StatePanel` in **c2-9**, `Footer` in **c2-10** —
and all eight are documented under _Components_ above. **`StatePanel` and `Footer` are the two
with an on-screen consumer**; the other six still have none, so `npm run build` leaves them out
of the module graph entirely and their **appearance is not dev-verified** (jsdom applies no
stylesheet). Each is checked by
eye at its first consuming story: `Panel` at **c4-5** (card detail, the first real
`level="overlay"` panel) and **c4-7** (the deck list) — **re-homed from c2-9**, which turned out
not to render a `Panel` at all (Q6) — the group header and deck-row context at **c4-7**, the
badge at **c4-2** and **c4-10**, and the pip and cost at **c4-3** (card placeholders), **c4-7**
(deck rows) and **c4-9** (the colour-distribution legend). The header badge slot in `AppShell.tsx` is **still
empty on purpose** — c2-7 shipped `Badge` without filling it, and **c4-2** and **c4-10** are its
fillers. The one remaining primitive is the nav pill (**c6-8**).

The skip link and Tab-order work are **c4-11** — the shell builds no focus management. The
numeric role now has real consumers: the panel count, the group-header count and the StatChip
delta all landed in **c2-7**, so `findUnpairedNumericRole` is no longer a guard with nothing to
guard; **c6-8**'s curve axis is next.

`ui/dist` is no longer produced. A few ignore patterns still name it (`ui/.gitignore`,
`.prettierignore`, the stylelint `--ignore-pattern`); they are harmless and deliberately left
alone — each removal is a chance to break a gate for nothing.
