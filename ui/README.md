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

| Banned                                                                                                                                                                                           | Rule                                                      |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------- |
| a hex colour, a named colour, `rgb()`/`hsl()`/`oklch()`/`drop-shadow()`…                                                                                                                         | `color-no-hex`, `color-named`, `function-disallowed-list` |
| a `box-shadow` or `text-shadow` not built from `--shadow-*`/`--glow`                                                                                                                             | `declaration-property-value-allowed-list`                 |
| a `border-radius` not from `--radius-*` — **including every longhand**                                                                                                                           | `declaration-property-value-allowed-list`                 |
| `padding`/`margin`/`gap` not from `--space-*` — **including every longhand**                                                                                                                     | `declaration-property-value-allowed-list`                 |
| a literal duration in `transition`/`animation` or their duration/delay longhands                                                                                                                 | allowed-list + disallowed-list                            |
| anything that pulses, loops or alternates                                                                                                                                                        | disallowed-list + a guard                                 |
| `style={{…}}` on a JSX element                                                                                                                                                                   | `no-restricted-syntax` (ESLint)                           |
| native CSS nesting in a shipped stylesheet                                                                                                                                                       | a guard                                                   |
| a hard-coded `font`/`font-*`/`line-height`/`letter-spacing` value — and the sibling `word-spacing`/`text-indent`                                                                                 | `declaration-property-value-allowed-list`                 |
| any `font-variant-numeric` value except `var(--type-numeric-features)`                                                                                                                           | `declaration-property-value-allowed-list`                 |
| `font: var(--type-numeric)` without its `font-variant-numeric` companion                                                                                                                         | a guard                                                   |
| an `@font-face` anywhere but `src/styles/fonts.css`                                                                                                                                              | a guard                                                   |
| any external URL in the built bundle's `.css`/`.html`; font-CDN hosts, fetchable assets and unreviewed hosts anywhere                                                                            | a guard                                                   |
| a class name that is not flat kebab-case — BEM's `__` and `--` included                                                                                                                          | `selector-class-pattern`                                  |
| a bare `1fr` grid track, or any `minmax()` floored at `auto`/`min-content`/`max-content`                                                                                                         | a guard                                                   |
| clipping a root (`html`/`body`/`:root`/`#root`/`.app-shell`) or `.app-shell-columns`, the one scroller — by `overflow: hidden`/`clip`, by `contain: paint`/`strict`/`content`, or by `clip-path` | a guard                                                   |
| a second full-window `position: fixed` layer outside the shell's stylesheet                                                                                                                      | a guard                                                   |
| a viewport height on the document root — `vh`/`dvh`/`svh`/`lvh`… **and `%`**, since `html`'s containing block _is_ the viewport                                                                  | a guard                                                   |

**And one named NON-ban, with its reason: geometry literals.** A track width, a breakpoint, a
stacking level, a card-tile minimum — these are the one value family that stays a literal, and
saying so explicitly is what stops the next author reading `452px` as drift. There is no token
family to point at, and adding one is not available: `tests/token-usage.test.ts` pins
`declaredTokens.size` at **64** and `tests/tokens.test.ts` asserts every token name
byte-for-byte against `DESIGN.md`'s frontmatter, which contains no layout-width token. An
unenforceable ban is worse than a documented exception, so the rule is:

> A geometry literal is allowed, and it carries a comment naming its source in `DESIGN.md`
> and the reason it is not a token. Where it defines a composition, a test pins it.

`src/components/AppShell/AppShell.css` is the worked example (452px column, 1100px breakpoint,
both pinned in `tests/shell.test.ts`), and c2-7's 17px StatChip value, c2-9's 480px state-panel
max-width and c4-4's 176px grid minimum inherit a stated rule rather than a habit — **and a
gate, not just prose** (review round, 2026-07-28): `tests/shell.test.ts` runs the DESIGN.md
citation check over every `px` literal in **every** tracked stylesheet under `src/components/`,
so a later story's uncited literal fails the moment its CSS is staged. Everything
that _can_ come from a token still must — spacing, colour, radius, shadow, type and duration
are gated, and a geometry literal is never a way around one of those.

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
  requires. UI attribution is **c2-10**'s footer; the fact it needs is the copyright line in
  `fonts.css`.
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

**A component module may export the component, types and constants — but not a helper
function.** `react-refresh/only-export-components` is an `error` with `allowConstantExport:
true`, so a helper exported beside the component turns the gate red. Keep helpers unexported,
or give them their own module.

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
region arrives through a prop, and `tests/shell.test.ts` asserts it. c2-7's primitives restate
the same posture.

## Adding a source directory

Every linted `.ts`/`.tsx` file must belong to a tsconfig — ESLint's `projectService` errors
on any file that does not. `src`, `tests/fixtures/a11y` and `tests/fixtures/tsx` are in
`tsconfig.app.json`;
`vite.config.ts`, `config/` and `tests/` are in `tsconfig.node.json`. A new top-level
directory needs adding to one of those two `include` lists.

## Not here yet

The `/ws` proxy entry is **c5-6**. The runtime `fetch` layer is **c3-1**'s first real
consumer, and **c4-1** owns the store and its in-flight deduping — c2-3 deliberately ships the
generated types with no fetch helper, so neither of those designs is pre-empted.

The application shell landed in **c2-6**, so the token layer now has a real consumer and
`src/App.css` is gone with the placeholder it styled. What the shell deliberately does _not_
build is every region it holds open, each of which renders a placeholder line naming its owner
until that story lands: the presentation primitives are **c2-7**, the shared state panel and
its copy are **c2-9**, the footer's attribution text is **c2-10**, the card grid is **c4-4**
and the curve/colour pair below it is **c4-8**, card detail is **c4-5**, the deck list is
**c4-7**, the format check is **c4-10**, the header badges are **c2-7** filled by **c4-2** and
**c4-10**, the agent-view nav pills are **c6-8**, and the agent view that drops into the
overlay slot is **c6-5**. The `h1` carries the product name provisionally; **c4-2** replaces
its content with the deck name and nothing about the element moves.

The skip link and Tab-order work are **c4-11** — the shell builds no focus management. Nothing
applies the numeric role yet: `c2-7`'s StatChip and `c6-8`'s curve axis are still the first
things that will.

`ui/dist` is no longer produced. A few ignore patterns still name it (`ui/.gitignore`,
`.prettierignore`, the stylelint `--ignore-pattern`); they are harmless and deliberately left
alone — each removal is a chance to break a gate for nothing.
