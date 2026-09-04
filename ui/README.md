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
sees its own address and the check passes. It is asserted by a real round trip in
`tests/devProxyRoundTrip.test.ts` — both directions — rather than by reading the config object.

Note that `changeOrigin` affects the **`Host`** header only. It does not touch the browser's
`Origin` header — and **the WebSocket upgrade validates `Origin`**, against exactly
`http://127.0.0.1:{bound_port}` and `http://localhost:{bound_port}`, fail-closed.

That combination has a consequence: under `vite dev` the page is served from Vite's own port,
so its `Origin` names Vite, and a proxied handshake with a rewritten `Host` (which passes) and
an unrewritten `Origin` (which does not) is a bodyless `1008`, rendered as a bare `403`, while
every `/api` call on the same page keeps working.

**So the `/ws` entry in `PROXIED_PATTERNS` carries `ws: true` and also rewrites `Origin` to the
backend target** — the same thing `changeOrigin` does for `Host`, applied to the second header.
The backend check stays strict and `security.py` ships no dev-time branch; the whole
accommodation lives in `config/devProxy.ts`, which never reaches the bundle. The two alternatives
both lose: dialling the backend port directly from the dev client makes dev and prod diverge
inside `client.ts` (where `agentSocketUrl` derives the authority from `window.location`
precisely so that it cannot), and an `allowed_origins` widening flag would put a dev-time hole
in the backend. `tests/devProxyRoundTrip.test.ts` proves it with a real upgrade through a real
Vite server, in both directions.

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

The backend serves the bundle behind a fallback rule: a request
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
  rule because its target is a `.tsx` file.
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
(`HealthResponse`, `ErrorResponse`, `DeckSummary`, `ErrorReason`, `Card`, `CardSummary`,
`DeckCardSummary`, `DeckDetail`, `ActiveDeck`, `CardFace`, …). **An alias is added only in the
commit that gives it a consumer** — an unused export is dead code. Both rules are enforced by
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
`declaredTokens.size` at **69** and `tests/tokens.test.ts` asserts every token name
byte-for-byte against `DESIGN.md`'s frontmatter, which contains no layout-width token. An
unenforceable ban is worse than a documented exception, so the rule is:

> A geometry literal is allowed, and it carries a comment naming its source in `DESIGN.md`
> and the reason it is not a token. Where it defines a composition, a test pins it.

`src/components/AppShell/AppShell.css` is the worked example (452px column, 1100px breakpoint,
both pinned in `tests/shell.test.ts`). `StatePanel.css`'s 480px max-width follows the same
rule — `DESIGN.md`'s frontmatter carries `components.state-panel.max-width: 480px`, so the
citation beside it is a true one rather than a borrowed one — and so does the card grid's 176px
minimum. **It is a gate, not just prose**: `tests/shell.test.ts` runs the DESIGN.md citation
check over every `px` literal in **every** tracked stylesheet under `src/components/`, so an
uncited literal fails the moment its CSS is staged. Everything
that _can_ come from a token still must — spacing, colour, radius, shadow, type and duration
are gated, and a geometry literal is never a way around one of those.

**A type size is never a geometry literal, and the boundary is worth more than the rule.**
DESIGN.md's `components.stat-chip.value-size` is `17px`, but the value is spent through
`font-size`, and `font-size` is **gated** — the `font-*` allowed-list admits only CSS-wide
keywords, so `font-size: 17px` is a lint ERROR with no citation that could rescue it. A geometry
literal is a value with **no token family to point at**; a type size has one, and the answer
there is a different **role token**, never an exception. StatChip ships
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
  a child setting the dim border is **not caught** — and that is the normal shape of the
  suggestion rows and the swap rows, because DESIGN.md gives the container the overlay.
  Deciding it needs the render tree, which lives in TSX. **Review owns that half**; when you
  review a row component, check it rather than assuming the gate did. `SuggestionsView.css`
  answers it the only way that is checkable — by spending **no** `--accent-dim` at all, which
  `token-usage.test.ts` asserts over that file's bytes by name. Whether `--accent` reads well
  over the row's own `--accent-glow` tint is still a pixel question, and it belongs to the
  manual checklist.
- **Do not use native CSS nesting.** The block reader in `tests/token-usage.test.ts` matches
  innermost braces, so a declaration in a nesting parent is invisible to every guard there —
  including the contrast one. Rather than grow a real CSS parser prematurely, nesting
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
  `fonts.css` is a Google Fonts `@import`, and **nothing in either lint layer objects to
  one**. `tests/fonts.test.ts` scans the committed bundle and fails on
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
  machine the `frontend` job never runs on — it is ubuntu, and the only Windows job in CI
  (`companion-integration`) runs backend tests and never loads a font.
- **The licence ships with the font.** `src/assets/fonts/LICENSE-OFL-1.1.txt`, as OFL-1.1
  requires, and the copyright line is in `fonts.css`. **The footer does not name the
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

A convention discovered per component is thirty-five chances to diverge, so these are decided
once here rather than re-derived.

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
measured, `export const BADGE_TONES = [...] as const` beside the component is a lint
error, because the rule does not treat an array initialiser as a constant. Keep helpers
unexported, or give the helper
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

`Panel`, `Badge`, `StatChip`, `GroupHeader`, `ManaPip` and `ManaCost`, composed by every
container without being opened again. This is the component _library_ of the codebase, and a
library whose rules are re-derived per consumer has stopped being one.

**Primitives are hook-free, and that is a category rather than a preference.** No `useState`,
no `useEffect`, and specifically **no `useId`** — which is the most reasonable-looking hook one
of these could want, for `aria-labelledby`. The day a primitive needs a hook it has stopped
being presentation-only, and that is a **signal**: the component belongs in a different
category and its story should say so. `tests/shell.test.ts` asserts it over every primitive
with an **exhaustive import list**, hooks keyed by API family (including React 19's lowercase
`use()`), and no `on*` handler prop, no `ref`.

**Region and heading semantics** (UX-DR44):

- A **titled** `Panel` is a `<section aria-label={title}>` whose title is an `<h2>`. That is
  the per-panel `role="region"` labelling the shell deferred to the panels.
- **`aria-label`, not `aria-labelledby`** — the latter needs a generated id, which needs
  `useId`, which is a hook. The accepted consequence is that `title` is typed `string`, not
  `ReactNode`; DESIGN.md already says panel titles are short label strings.
- An **untitled** `Panel` is a plain unnamed `<section>` and **invents no name**. A section
  with no name has no role at all, which is right — a generic invented name fills the landmark
  list with identical entries to navigate past.
- A **title-less `live` `Panel` does not exist** — `live` requires a `title`. With
  no title to recolour and no dot to hang beside it, only the elevation change is left, and
  `graphite` and `ink` declare both elevation tokens as `none`: under two of the five shipped
  themes a live panel would render identically to a resting one. That is an absent signal, not
  a degraded one. A caller wanting a live marker on an unnamed container is being told to name
  it.
- A **`GroupHeader`** is also an `<h2>`, with its count **beside** the label rather than inside
  it. UX-DR44 read literally makes a panel title and its "CREATURES" divider siblings; that is
  the spec's choice, taken as written; a real screen reader disagreeing is the reason to revisit
  it.

**Emptiness is `filled()`, never truthiness.** `src/components/filled.ts` is the settled
answer to `<></>`, `[]`, `' '`, `false` and one-shot iterables — five shapes that render
nothing while looking filled to a naive check. It lives beside the components rather than inside
`AppShell/` because `Panel` is its second consumer. Re-deriving it in a new component is the
reinvention it exists to prevent.

**Where `filled()` applies:** it gates **optional slots**
(Panel's header pieces) and **components whose empty state is visible chrome** — a `Badge` with
empty children is a bordered, washed, empty pill, so it renders `null`. It does **not** gate
required content slots (`GroupHeader.label`, `StatChip.label`/`value`): those components are
only mounted to show that content, so an empty value there is caller error, and each prop's doc
says so. The same reasoning is why those slots are `ReactNode` while Panel's `title` is
`string` — `title` doubles as the region's `aria-label`, which must be a string in a hook-free
component; a slot that is never an accessible name loses nothing by admitting markup.

**Badge clamps a runtime-unknown tone to `neutral`.** The type admits only
the five tones, but tones arrive as server data (legality status, tiers), and an
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
themselves; a _consumer_ writing `{count && <GroupHeader …>}` in the deck list is exactly
the same defect one call site up, and no lint rule or guard reaches it. Stated here so the
asymmetry is a decision rather than an oversight: every other rule on this page got a derived
gate, and this one is prose plus review because the failure lives in consumer files, not in the
primitives.

### The containers — where a component that BEHAVES lives

Every component that holds state, subscribes to a store or takes focus lands here rather than
in `src/components/`: the card tile, the card detail, the flip control, the deck list, the
format check, the skip link, the connection pill (which qualifies on both counts at once — it
subscribes to two slices AND it takes focus), the agent view shell, `SuggestionsView` and
`AgentViewsNav`. The last qualifies the same way the connection pill does — two store
subscriptions per pill and a real focusable button — which is why a row of four header pills is
a container rather than a primitive.

**`src/components/` is CLOSED, and a component that holds state cannot join it.** That is
structural, not stylistic: `tests/shell.test.ts:1257` asserts SET EQUALITY between
`git ls-files 'src/components/*.ts(x)'` and `PRIMITIVES + AppShell.tsx`, and every listed member
is then held to bans on hooks of any family, `on*` in both positions, `ref` in both positions,
spread, and a value `react` import — with `tests/posture.test.ts` banning three of those a second
time over the same directory. A card tile needs `<img onLoad>` to know whether the pixels arrived
and a `ref` to survive the warm-cache race, so a module for it under `src/components/` is a **red
test both ways**: listed, the posture bans fire; unlisted, the coverage guard fires. That is the
category-change signal `shell.test.ts` names in its own prose, arriving for the first time.

**So containers live in `src/containers/`, with their own git-derived coverage guard**
(`tests/shell.test.ts`'s `CONTAINERS` block — an uncovered directory is how every new component
would escape every gate in the repo at once).

**The posture, in full.** A container MAY hold state, call hooks of any family, declare and
attach handlers, hold a `ref`, read the store through `src/state/`, and compose primitives. It
may NOT reach the network (the door is still `src/api/client.ts`, named exhaustively), import a
state library directly, write a store slice from outside its own module, or declare a design
token. Its import list is exhaustive and its permitted roots are checked, same as a primitive's.

**Why a new tree rather than a second list inside `src/components/`, measured.** The
cheaper-looking option was to widen the covered set and leave the files where they were. Three
guards are path-scoped to that directory — `shell.test.ts`'s coverage guard and posture bans,
`posture.test.ts`'s three `it.each(componentSources)` blocks, and `shell.test.ts`'s **`px`-literal
DESIGN.md citation check** — and the decisive one is not the count but what an exemption would
have blinded: `posture.test.ts`'s cross-tree import rule filters on
`!target.startsWith('src/components/')`, so a container exempted from it would have made **a
presentation-only primitive importing a stateful container invisible to every guard in the repo**.
With the containers outside that tree, the rule that was already green catches it, for free. The
one real cost is that the `px`-literal citation check had to be **widened** (its scope is now a
list of roots) rather than weakened — and a later tree of the same kind adds its root there, in
the open.

#### Tinting a surface from a semantic token

The mechanism suggestion rows, swap rows and tier rows reuse rather than each inventing one.
(The suggestion row's badge is in the **neutral** tone — the item's `category` is free text and
no mapping from those to the four semantic tones exists — so the semantic-tint path below has no
shipped consumer yet.) DESIGN.md asks a tone to "tint background and border from its own semantic
token — never from hard-coded RGB", and **every obvious spelling of that is banned**:
`rgba(95,212,160,0.12)` by `function-disallowed-list`, and `color-mix(in srgb, var(--positive)
12%, transparent)` by the **same rule** (measured). There is no translucent `--positive-wash`
token and the layer is closed at 69.

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
token" reads. The `color-mix()` ban stands unchanged; no gate was relaxed for it.
`src/components/Badge/Badge.css` is the worked example, with the full argument in its header.

#### Sizes the token layer does not carry

**A role token plus its companion — never a `font-size`, never a new token, never a stylelint
exception.** DESIGN.md's StatChip value is 17px; `font-size: 17px` is a lint error and a
`--type-stat-value` token would break both `declaredTokens.size === 69` and the byte-for-byte
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

**And the sibling rule, for GEOMETRY DESIGN.md does not carry at all.** A `px`
literal is a named non-ban _provided its citation is true_ — but DESIGN.md's `components.*`
frontmatter declares **no mana entry**, so a pip's `16px` would meet the citation gate with
nothing truthful to cite. That is StatChip's `min-width: 76px` problem with one difference: a chip
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

`ManaPip` is the `--mana-*` tokens' **first consumer in the repository**. Before it,
`git grep -- '--mana-'` over `ui/` returned seven hits, all seven of them the declarations in
`tokens.css`: UX-DR7's "curve bars, mana pips and colour-identity dots ONLY, never a button,
border, background or an unstacked curve bar" was enforced by nothing — a rule with no consumer
and no gate is a sentence.

The gate is in `tests/token-usage.test.ts` and has two halves (plus a markup half, below):

- **Which files may reference a `--mana-*` at all** — the `MANA_DATA_INK` allowlist, each entry
  carrying the reason that file is data ink. The two graphics that have faced the question went
  opposite ways, which is the protocol working rather than failing: **the mana curve DECLINED**
  on a measurement (a curve stacked by colour would paint 24 live rows colourless from a
  structurally blank `colors` field) and **the colour distribution JOINED** —
  `ColourDistribution.css` is the list's second entry, because UX-DR18 calls its bar _"data ink
  used correctly"_ in the artefact's own words. A non-vacuity test proves every entry is a path git actually tracks,
  so a rename fails loudly rather than silently permitting nothing.
- **Which properties may spend one** — an **allowlist**: `background`, `background-color`,
  `background-image`, `fill`, `stop-color`. Nothing else. It is an allowlist rather than a ban
  list on purpose, and that is the general lesson: "ban the family, never enumerate members" has
  a stronger form than a wider ban. A ban keyed on `/^border/`, `/^outline/` and `/shadow$/` is
  still a list of families its author thought of, and `caret-color`, `accent-color`,
  `text-decoration-color` and `column-rule-color` are not in it.

**The markup half:** both halves above read stylesheets, so a
`var(--mana-*)` spent from markup — an SVG `fill` presentation attribute, a value in
`index.html` — would be policed by nothing. A third check scans every git-tracked non-CSS source
file and allows **none**: there is no markup allowlist to join, because the way in is always a
class in an allowlisted stylesheet, the way `ManaPip` does it. Chart segments take a class, not
a `fill=` attribute.

**The half no static reader can decide is review's**, declared in the guard's own comment the
way `surfaces.ts` declares its own: whether a given curve bar is genuinely **stacked** is a
property of the data bound to it and the elements composed at runtime. **The reviewer of a
segmented graphic must look**; the gate will not have looked for them. (The mana curve ships no
stacking at all, so the question does not arise there; the colour distribution's segments are
the first it genuinely applies to.) The same comment declares a second residual:
chrome-shaped spend **through an allowed property in an allowlisted file** (a hover tint, a
button-like background) passes both halves — the allowlist _reason_ is what review checks it
against.

**`--mana-gold` is the family's seventh token and has no consumer** — deliberately: it is
not a cost colour, so `MANA_COLOUR_ORDER` (the parser's vocabulary) excludes it and the pip
class-coverage guard derives 21 classes from six colours. The colour distribution does not spend
it either: UX-DR17's gold is a _multicolour card_ contributing one segment to a stacked curve,
while UX-DR18 specifies a **pip count**, and **a pip is never gold**. `{W/U}` is a white-or-blue
pip, which `ManaPip` already draws as a two-stop gradient across two real tokens.

The spent-token count therefore stays **6 of 7**, and the absence is **asserted by a test**
rather than noted in prose (`tests/token-usage.test.ts`, _"still has NO consumer for
--mana-gold"_) — an absence nothing protects is an absence that ends silently. Gold's real first
consumer is a stacked curve or a colour-identity dot, and **neither exists**.

**One class per colour, never a token name built at runtime.** The composition reference writes
`'var(--mana-' + color + ')'` into an inline style. The lint error is the least of it: a
runtime-built token name is invisible to `findUnknownTokenReferences`, so a bad colour renders a
_transparent_ circle no test can see. The indirection a component author reaches for instead —
`.mana-pip-w { --pip: var(--mana-w) }` — is a **guard** failure, since only `tokens.css` may
declare a custom property. So `ManaPip.css` declares all 21 classes (six colours and all fifteen
unordered pairs), and a guard derives those 21 suffixes from `MANA_COLOUR_ORDER` and proves each
exists **and names a real token**.

#### A parser is total, or it is silently wrong

It generalises past mana: **scan the whole input; never enumerate what you accept and discard
the rest.** The API client's response handling and the WebSocket envelope parsing meet the same
shape.

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

`ManaCost` sets the pattern (UX-DR18, UX-DR44), and **the mana curve and the colour bar reuse
it rather than each inventing one.**

**`role="img"` plus `aria-label` on the wrapper; the coloured parts inside stay decorative.**
This is required, not stylistic: `aria-label` on a bare `<span>` is **name-prohibited** on
`role="generic"`, and screen readers are permitted to ignore it — several do. A `role="img"`
element's children are presentational, so nothing double-announces.

**The name is built by a pure formatter beside the parser and unit-tested with it.**
`{2}{W/U}` reads _"2 generic, white or blue"_; `{B/P}` reads _"Phyrexian black"_. An unknown
symbol reads as its own raw text (`{HW}` → _"HW"_), which is honest rather than silent — the
same rule the pips follow, in words.

**A standalone `ManaPip` is decorative by default**, with an **opt-in** `label`.

**The colour-distribution legend does NOT set `label`**, and that is the opt-in defaulting the
right way: a legend entry puts a pip beside its own text count, and the entry already says the
colour, the count and the percentage in words, so a labelled pip there is exactly the doubled
announcement UX-DR45 warns about. The prop therefore has **no caller yet**, and it is right that
it exists and is unused: the safe direction is the default, and a component that genuinely needs
a named pip (one drawn without text beside it) opts in.

That also makes the colour NAME load-bearing copy rather than a label —
`ColourDistribution/copy.ts` owns the six words, and they are the only route by which a colour
reaches a screen-reader user at all. Which is what UX-DR18's _"the legend is the accessible data
path"_ means when it is taken literally.

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

### The card shape — read this before writing a card-shaped component

The seam the card tile, the detail art and the flipped face inherit rather than re-derive.

**There is exactly ONE declaration of the card geometry in this codebase**, and it is
`.card-shape` in `src/styles/card-geometry.css`:

```css
.card-shape {
  aspect-ratio: 63 / 88;
  border-radius: var(--radius-card);
}
```

**Consume it by class name. Do not import it, and do not write either declaration again.** The
file is `@import`ed by `src/index.css` beside `fonts.css` and `tokens.css`, so the class is
globally available and a card-shaped component's own stylesheet contains only its surface, its
type and its layout. Importing it from a component would ALSO fail `tests/posture.test.ts` — a
component may take a value from nowhere but its own tree, and `../../styles/…` is not that.

**Why a class and not a token.** `tests/tokens.test.ts:265` is a **set equality** over an
inventory derived from `DESIGN.md`'s `colors` / `typography` / `rounded` / `spacing` / `motion` /
`focus` / `elevation` frontmatter blocks, pinned at 69. `components.card-tile.aspect` is in none
of those blocks, so **`--card-aspect` cannot be added without failing that gate**. Adding it is a
DESIGN.md amendment plus a moved pin, argued in the open — not a token added quietly.

**Why global rather than owned by the placeholder.** The same argument `src/index.css` already
makes for the box-sizing reset: every component inherits the same hazard the moment it sizes and
pads itself, which is why the reset is global. Four components draw this rectangle; a class owned
by the first of them would make the other three import across component directories.

**UX-DR4's exclusivity is a GATE, in both directions** — `CARD_SHAPED` in
`tests/token-usage.test.ts`, the same allowlist idiom as `MANA_DATA_INK`:

- nothing outside the listed files may spend `--radius-card` (_"nothing else in the UI borrows
  the card radius"_), and
- **no listed file may spend a chrome radius** (_"cards never borrow a chrome radius"_) — written
  as `--radius-` minus `--radius-card`, so a `--radius-xl` invented later is covered. This half is
  not redundant: `border-radius: var(--radius-md)` on a card is what the composition reference
  actually ships, and DESIGN.md:362 corrects it by name.
- a third half scans non-CSS sources, because a `var(--radius-card)` in markup would meet neither.

**A later card-shaped component adds its stylesheet to `CARD_SHAPED` with its reason**, and gets the
second half applied to it in the same move. What the gate cannot see is declared beside it:
whether an element carrying `card-shape` is genuinely a card (that is markup, and review's),
inline geometry (banned by eslint), and cross-file composition.

**The card tile was the first to join, and it found the collision the list makes visible.** The
tile spends no `--radius-card` at all — the shape arrives through the class — so half ONE would
never have looked at it, and joining is what turns half TWO on. That immediately collided with the
quantity badge, which DESIGN.md gives `{rounded.pill}`: the badge is chrome sitting ON a card
rather than a card. **The resolution is two files, not an exception in the guard** —
`CardTile.css` is card-shaped and listed, `QuantityBadge.css` is chrome and deliberately is not.
Reach for that shape rather than weakening a rule that is currently total.

**Clipping is NOT in the shared class, deliberately.** Whether content clips is a statement about
content, not about shape — `CardPlaceholder.css` sets its own `overflow: hidden` for the
141-character name the corpus really contains, and the tile sets its own to clip art to the
card corners.

**The footprint claim is confirmed by eye.** Tests can only prove that the placeholder declares
the shape and that the element carries the class; whether a placeholder and a real card face
occupy the same rectangle in a real grid needs a browser. Rendered in Edge against the running
backend with a 99-card deck active: **they do** — loading wells, named placeholders and loaded
faces sit in identical rows with no seam, so UX-DR36's _"layout never reflows when art arrives"_
is an observation rather than a derivation.

### Motion — the first of it, and how a later story registers its own

The card tile carries the first `transition`, the first `transform`, the first `:hover` state
on anything but a footer link and the first z-index raise in the codebase. A stylesheet with no
motion at all is the normal case, and correct.

**Durations come from `--motion-*` and easings from `--ease-*`.** A literal duration anywhere in a
`transition` or `animation` is a lint error, and nothing pulses, loops or alternates at any
setting.

**`tokens.css`'s `prefers-reduced-motion` block is the ONE registration point.** The
distinction that matters, because it is easy to get wrong:

- **A motion expressed entirely through a duration token is MECHANICAL.** Zeroing the four
  durations already switches it off. The tile's image fade is this, and it registers nothing —
  writing a second declaration for it would suggest the mechanism does not work.
- **A motion a duration cannot reach registers EXPLICITLY, in that block, in the story that builds
  it.** Zeroing a duration makes `transform: scale(1.06)` INSTANT, not ABSENT — the tile would
  still jump 6% the moment a pointer crossed it, which is the vestibular motion UX-DR42 asks to
  remove, arriving faster.

**That rule is now a GATE rather than prose** (`tests/token-usage.test.ts`): every shipped block
declaring a motion property — `transform`, and the individual `scale`/`rotate`/`translate`, per
property — must have that property `none !important` on the same selector in the reduced-motion
block (a no-`!important` registration is the cascade no-op the paragraph below measures, and
`scale: 1.06` is the same pop in another spelling). The RULE is derived, so the flip control's
3D flip and the agent view's bloom are caught the day they are written — but the guard also
carries an ENUMERATED pin of the shipped-motion list, so the change that adds a motion moves that
pin in the same commit, the way the token pins move. The gate exists because a probe that deleted
the fallback left the whole suite green.

**The override carries `!important`, and that is measured.** `.card-tile:hover` in `tokens.css`
and in `CardTile.css` have identical specificity, and `tokens.css` is `@import`ed first — so
without it the block would parse cleanly, read correctly and do nothing at all.

### The focus ring over art, and why `outline` is still authored

DESIGN.md files `focus-ring-over-art` under `components.card-tile`,
and `.stylelintrc.json`'s `box-shadow` allowed-list admits `none` or a comma-list of
`var(--shadow-…)` / `var(--glow)` **and nothing else** — so the composite cannot be written in a
component stylesheet at all. It ships as **`--shadow-focus-ring-over-art`**, with both pins
moved together (`expectedNames` + `toHaveLength` in `tests/tokens.test.ts`,
`declaredTokens.size` in `tests/token-usage.test.ts`) and its value asserted against the artefact
the way the three elevation tokens are. `components.card-tile.live-ring` (`--shadow-live-ring`)
was added the same way only once something set `live`: an inventory pinned by set equality exists
so that an unused token is a visible decision.

**The `outline` is authored, not removed, and the eye-check is why.** `outline: none` is banned in
every spelling (UX-DR46) and there is no legal way around it — but a browser draws its OWN ring on
`:focus-visible` unless the author sets `outline`, and the first draft of the tile therefore
rendered **two indicators at once**: the composite hugging the card's rounded corners and the UA
ring as a sharp-cornered rectangle around card-plus-caption. Two repairs, together:

- **the focusable element IS the card** (the `<button>` carries `card-shape`, and the caption is a
  sibling that names it through `aria-labelledby`), so an authored outline hugs the same rounded
  rectangle; and
- **the outline is given the composite's own inner band** — `var(--focus-ring-width)` solid
  `var(--focus-ring)` at offset 0 — so the two mechanisms occupy the same pixels instead of
  stacking, and the composite's `--surface-base` outer band still separates the indicator from the
  panel. `--focus-ring-offset` is deliberately unused here: the offset that suits a text link is
  what would split this ring in two.

Confirmed in Edge with a real keyboard focus, over a light card face and a dark one.

### The state panel, and where user-facing copy lives

Every component with a sentence in it — the footer attribution, the "Unknown card" placeholder,
the empty-deck line, the empty push — joins this mechanism rather than inventing one.

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
what lets a new state need no bespoke renderer, and it is why
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

**The smallest copy module is `CardPlaceholder/copy.ts`**, which holds exactly ONE string,
`"Unknown card"`, gated byte-for-byte against `EXPERIENCE.md` by
`tests/unknown-card-copy.test.ts`. Two things about it are worth carrying forward. **A copy
module may legitimately hold one string**: the non-vacuity threshold is a TOTAL across all
declared modules rather than a per-module floor, because a per-module floor would force words
into a module whose own header forbids them. And **the card name, type line, mana cost and truncated ID the
same component renders are DATA, not copy** — they arrive as props and are deliberately absent
from the module, because a copy owner that also held card names would make the claim `COPY_MODULES`
exists to state meaningless.

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

**Retry is a property of the state, and it is written where the poller reads it.**
`RETRIES_QUIETLY` in `states.ts` is total over every panel. `database-updating` and
`database-not-initialized` retry quietly, because their copy promises the page will come alive
on its own. **`internal-error` must never retry** — `types.d.ts` states it as a wire contract:
the companion hit a deterministic bug, so re-issuing the request re-hits it, and a quiet loop
would hammer a broken backend behind a calm panel that never changes. Its next action is a
manual restart. `database-updating-stalled` is the escalation of the quiet retry that did not
work, so it stops. **`src/state/poller.ts` owns the polling, the threshold and the
transitions**; the panel itself ships no fetch, no `setTimeout` and no hook at all.

**"Exactly one panel at a time" is the caller's**, not the component's. There is one `left`
slot in `AppShell` and no manager — do not build a state-panel registry.

**No error styling is a gate, not a review note.** `tests/token-usage.test.ts` holds
`StatePanel.css` to an **allowlist** of calm token families, so `--negative`, `--caution`,
`--positive`, a `--mana-*` red-by-another-name and a status token nobody has invented yet all
fail closed — including through a `var(--negative, …)` fallback. Other components legitimately
spend those tokens (the format check maps a violation to `negative`); the scope is the
rule, and a later calm surface adds its file with its own reason.

**A second family exists, and it is not a hierarchy.** `--font-mono` styles command
literals inside state-panel copy and nothing else — a string the user is about to retype into a
terminal, which is data. It is a system stack: no `@font-face`, no download, so the offline
guarantee is untouched. UX-DR2's "hierarchy never comes from a second family" stands.

### The footer attribution

The one component whose deliverable is a **condition of public release** rather than a design
choice — `DESIGN.md:375` says so in bold, and NFR-08 and UX-DR32 say it twice more. Anything
else could ship slightly wrong and be corrected later; this one shipping wrong is a licensing
defect.

**Copy is gated against the artefact that _wrote_ it — which here is `DESIGN.md`, not
`EXPERIENCE.md`.** The footer inherits the state panel's verbatim-gate _mechanism_, not its
source file.
`EXPERIENCE.md`'s Voice-and-Tone table has **no footer row**: its footer entry (`:101`) is
behavioural ("Static … links persistently underlined … and open in a new tab") and never writes
the words. The words exist in exactly one place — `DESIGN.md`'s `Footer attribution` bullet,
inside one pair of straight double quotes — so `tests/attribution.test.ts` reads that. Two
artefacts, two gate files, deliberately. **A later component asks which artefact wrote its
sentence, not which gate file already exists.**

The parse selects the bullet **by structure** (the bold label at the head of a top-level list
item), never by line number, and it **throws** on all four ways the artefact can change shape
underneath it: no such bullet, no quoted run, more than one quoted run, and a duplicated label.
A parser that silently tolerates a duplicate is a parser that stopped checking.

**The sentence is a list of parts, not three strings.** Two runs are links; the rest is text.
Five separately-authored fragments could drift apart while each stayed individually plausible,
so the parts carry link-or-text tags and `sentenceOf()` re-joins them — asserted byte-for-byte
against the artefact. Nothing is authored that `DESIGN.md` did not write, **link labels
included**. The hrefs are the canonical ones the repository's `NOTICE` already publishes, and
that is asserted too, so the app and the licence docs cannot drift.

**The shell owns the footer's layout; the component owns its ink.**
`.app-shell-footer` used to set `font: var(--type-micro)` and `color: var(--text-tertiary)`,
while the attribution needs `--text-secondary` (9.3:1 — legally load-bearing text gets a passing
tier, not a muted one). Two single-class selectors setting `color` is a source-order race
decided by import order, and this repo has already been bitten once by a cascade it did not
model. So the appearance moved out **wholesale** rather than being overridden: the shell rule
keeps `flex-shrink: 0` — the pinning mechanism, a property of the slot — and `Footer.css`
declares every value `DESIGN.md` assigns to `components.footer-attribution` exactly once.
`tests/shell.test.ts` asserts that only one block in the whole tree declares that colour, so the
race cannot reappear.

**"Every surface" is structural, not enumerated.** There is one `AppShell`, one `footer`
slot and no router, so **every surface renders through `App.tsx`** — and `App.test.tsx` asserts
the attribution inside the `contentinfo` landmark by role and by text, plus that the shell's
placeholder is not what is showing. An enumerated surface list would be a list its author
thought of, which is this repo's standing finding. The agent view is an **overlay inside the
shell**, not a route that replaces it, so the footer survives it by construction. **A future
surface renders through `AppShell`.**

**The footer declares no landmark of its own.** The shell's `<footer>` is the one `contentinfo`
(UX-DR44), and `AppShell.test.tsx` asserts exactly one of each landmark. `Footer.test.tsx`
asserts the absence standalone, so it is a property of the component rather than of today's
arrangement.

**10px all-caps is the spec, taken deliberately.** `DESIGN.md` assigns footer attribution
to `{typography.micro}` and declares that role uppercase, and the companion guard **derives**
the requirement from the artefact's own `textTransform:` key — so the legal notice renders as
10px capitals. `text-transform` does not touch the DOM text, so the verbatim gate, the
copy-rules content half and the screen reader are all unaffected; only the render is. Whether it
is comfortably readable is on the manual-testing checklist, and if it reads badly the
correction is a `DESIGN.md` amendment made with the rendered page in hand.

### Adding an external host to the bundle

`tests/fonts.test.ts` R4 asserts that the set of external hosts in the built bundle equals a
reviewed baseline, and it is **deliberately brittle**: a new host is the moment a human decides
whether the offline guarantee (NFR-06) still holds. The footer was the first to need one —
two, in fact — so the protocol is written down rather than inferred from the diff:

1. **Add the exact host string to `REVIEWED_HOSTS`, with the reason it is not a fetch.** A host
   with no stated reason is a host nobody checked. "It is inert" is a claim about behaviour.
2. **The exact string, never a family.** `scryfall.com` and `www.scryfall.com` are different
   hosts to a set check, as are `company.wizards.com` and `magic.wizards.com`. This is the one
   list in the repo where "a guard proven only against spellings it lists" bites hardest,
   so the evasion probe for a new entry must use a spelling the list does **not** contain —
   including the protocol-relative form (`//host/path`), which R4 also matches.
3. **The URL lives in TypeScript only.** R1 bans every external host from any `.css` or `.html`
   in the bundle outright, so an href belongs in a module — never in `index.html`, never in a
   `content:` or `url()`. R3 separately bans any fetchable asset extension, so a link to a
   `.pdf` copy of a policy would be red even from TypeScript.

**Adding a host does not weaken the offline guarantee, and the distinction is the point.** The
two footer hosts are `href`s on `<a target="_blank">` elements: a human clicks them, the
app never requests them, and the page renders identically with the network blocked. R4 is what
keeps that claim honest instead of asserted — a dependency that starts phoning home goes red and
a human looks.

## What the gates cannot see

Every guard in `ui/tests/` is a static reader. Several of them are load-bearing enough that it
matters exactly where they stop — and each one that stops somewhere **says so in its own source**.
This section is the index of those declarations, so a reviewer can find the edge without reading
fourteen test files first. It is not a list of bugs: every entry is a limit its author chose,
usually because closing it needs the cascade, the render tree or a human eye.

The rule this encodes: **a declared blind spot is still a claim.** One such claim — "neither
pass order is safe" was true, "this one fails on the rarer input" was never measured — once hid a
failure that blinded every guard in the file. If an entry here is load-bearing for your change,
verify it rather than inherit it.

| What is invisible                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Where it is declared                                                                                                                                                                              | Who owns the other half                                   |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **The cascade.** A correctly paired block undone by a later rule in another block reads as clean — resolving it needs specificity, source order and the element's real runtime class list. Applies to the numeric-pairing guard (UX-DR3 tabular numerals) and to the tracking/text-transform companion it spawned.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `tests/token-usage.test.ts:397`, `:473` — and _asserted_, not merely described, at `:1267` and `:1434`                                                                                            | Review                                                    |
| **Untracked files.** Every file-walking guard is keyed on `git ls-files`, so a stylesheet, font or module that is not yet committed passes vacuously. The limit is "invisible until committed", not "never seen" — CI sees it the moment it lands.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `tests/shell.test.ts:88`, and the same construct in `token-usage.test.ts:43`, `gate-geometry.test.ts:23`, `wire-contract.test.ts:60`, `copy-rules.test.ts:86`, `fonts.test.ts:53`                 | CI, one commit later                                      |
| **Cross-block and cross-file CSS.** The block reader matches innermost brace pairs, so a declaration in a nesting parent is in no block at all (made unreachable by the nesting ban, which is asserted). `findAccentDimOnOverlay` was widened from block-local to same-file; **cross-file remains open**.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | `tests/token-usage.test.ts:74`, `:166`, `:209`; `tests/shell.test.ts:41`                                                                                                                          | Review                                                    |
| **Runtime-composed class lists.** A full-window layer assembled at runtime from two classes, a root selector reached through an unrecognised class, or an overflow set from JavaScript — the render tree lives in TSX and is chosen at runtime.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | `tests/shell.test.ts:35`                                                                                                                                                                          | Review                                                    |
| **`var()` indirection.** `overflow: var(--clip)` hides the keyword in a custom property declared elsewhere, evading every value-keyed check. In the data-ink guard the same hole is closed _indirectly_ — declaring a `--mana-*` outside `tokens.css` is itself a failure two guards up, which is what makes that one safe rather than lucky.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | `tests/shell.test.ts:39`; `tests/token-usage.test.ts:604`                                                                                                                                         | The token-location guard, or review                       |
| **External hosts (`REVIEWED_HOSTS`).** Deliberately brittle: the _set_ of external hosts must equal a reviewed baseline, in both directions, so both a new host and a stale entry go red. A runtime-constructed URL (`fetch('htt' + 'ps://…')`) and an IPv6-literal host are still invisible.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | `tests/fonts.test.ts:320`, `:337`, `:520`                                                                                                                                                         | A human, by design — that is the point of the brittleness |
| **Whether a curve bar is stacked (UX-DR7).** Not a property of the stylesheet: it is a property of the data bound to it and the elements composed at runtime. The reviewer of a segmented graphic must look.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | `tests/token-usage.test.ts:596`                                                                                                                                                                   | Review, on any stacked graphic                            |
| **Whether copy is second-person and blameless (UX-DR33).** Not statically decidable, and the most important half of the rule. Four further copy residues are declared beside it: runtime-assembled copy, `aria-label={call()}`, Latin-script-only prose detection, and a single word as a JSX expression child.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | `tests/copy-rules.test.ts:54` and `:57`–`:69`                                                                                                                                                     | Review, on every copy module                              |
| **Anything outside `*.css`.** Every token-layer gate stops at stylesheets: `style={{ padding: '18px' }}` in a `.tsx` file is invisible to all of them.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | `tests/lint-gates.test.ts:100`                                                                                                                                                                    | Review                                                    |
| **Rendering, at all.** jsdom has no layout engine and loads no fonts, so "the glyphs on screen are Space Grotesk" and "a wide glyph fits its pip" are both unprovable here; the latter is pinned by a source read instead.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | `tests/fonts.test.ts:20`; `tests/token-usage.test.ts:1001`                                                                                                                                        | The manual-testing checklist                              |
| **Quotes inside copy strings.** Two artefact parsers capture with `"([^"]*)"`, so a copy string containing a double quote truncates the read. Both declare the ceiling; `copy.test.ts` also fails loudly on a duplicated row label rather than silently taking one.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | `tests/attribution.test.ts:119`; `tests/copy.test.ts:72`                                                                                                                                          | The parser fails loudly; review owns the wording          |
| **String literals containing `//` or `/*`.** The comment-stripper in the unknown-card pairing gate is regex-based, not a lexer: a future string in `states.ts` holding either marker (a URL, a glob) truncates `STATES_CODE` from that point. Guarded by an end-of-file anchor — the file's last live statement must survive stripping — so a mid-file truncation fails loudly rather than disarming the pairing regexes.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | `tests/unknown-card-copy.test.ts`, the `STATES_CODE` comment and the EOF anchor in its pairing test                                                                                               | The anchor fails loudly; review owns any new `//` string  |
| **Whether a binary response body is really binary.** The generated contract types `GET /api/card-image/{scryfall_id}`'s 200 as `content: { "image/*": string }` — `openapi-typescript` renders `format: binary` as `string`, not `Blob`. Nothing goes red if a consumer trusts that and calls `.text()` or `.json()` on an image. **A consumer must read the response as a blob and must not derive its handling from the type.** It is the first non-JSON success body in the document.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `ui/src/api/types.d.ts`, the `read_card_image_…` operation; `scripts/dump_openapi.py`'s module docstring                                                                                          | Review, and the consumer's own tests                      |
| **Whether an image tile asked for the face it rendered.** The backend proves it serves the right face from the right URL (`test_routes_card_image.py` asserts on the bytes AND on what the transport was asked for), but jsdom has no layout engine and loads no images, so "the back face of a transform card is on screen" is unprovable in this suite. Both halves of the pairing exist only in a real browser.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `tests/unit/companion/test_routes_card_image.py::TestTheFourShapes`                                                                                                                               | The manual-testing checklist                              |
| **A cross-project import breaking `tsc` while `npm test` stays green.** `ui/tests` is `nodenext` and `src` is `bundler`, so a `tests/` file importing an app module that has its own relative imports fails `tsc -b` — cascading into errors that name the importee's type asserts, not the import. Vitest resolves it fine, and `tsc -b` caches, so it can hide. Run `npx tsc -b --force` when touching cross-project imports.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | `tests/unknown-card-copy.test.ts`, the `STATES_TS` comment                                                                                                                                        | Review                                                    |
| **Whether a wire description addresses a TypeScript reader.** The backend gate bans the _shapes_ of Python-internal prose (Sphinx role markup, any line-anchored Google section header, doctest prompts) from every OpenAPI description — but "Supports conversion from SQLAlchemy CardModel instances" trips none of them and is exactly the kind of sentence that has had to be rewritten. Structurally clean, semantically internal. Not statically decidable, like UX-DR33's second-person half.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | `tests/unit/companion/test_openapi_contract.py`, the `PYTHON_INTERNAL_FAMILIES` docstring                                                                                                         | Review, on every change that adds or edits a wire schema  |
| **Whether a deck-construction _rule_ was reimplemented in the backend shell.** `find_rule_violations` bans five families from `src/companion`: the name `legalities` in **any** position (attribute, subscript, `getattr`, or a string bound to a variable and used as a key later); any import of the validator module, of a name from it outside the projection surface, **or of any ancestor package** (`import src.logic` / bare `import src` bind a name from which the validator is a plain attribute chain); the limits `60`/`15` appearing anywhere as a number, in any position, `int` or `float`; two or more Scryfall format names together **anywhere under one container** — nested tuples, dict keys _and_ dict values all count; and any `.quantity` access. **Five declared holes.** (1) `1` is outside the limit family — the singleton limit is 1, but `> 1` / `== 1` are ubiquitous, so banning it would be noise; a shell reimplementing the _singleton_ rule specifically would pass. (2) **Adjacent-literal spellings** — `<= 59` / `>= 16` / `>= 5` are the same rules with the off-by-one integer, but the adjacent set is unbounded and its small members as ubiquitous as `1`; a declared limit, same stance as (1). (3) **`4` is in that set too** — the copy limit is 4 and so is every innocent four; `images.FETCH_CONCURRENCY = 4` (a CDN concurrency cap, no deck vocabulary anywhere near it) was the first measured collision. The copy limit is still caught by the `.quantity` family — enforcing it means counting copies — leaving only a shell that counts copies _without_ reading `quantity` (`len(rows) > 4`), which is the same obfuscation stance as (2). Both directions are probed. (4) A fully dynamic form — a limit read from config, a key assembled from fragments — defeats an AST walk by construction; `test_import_boundary.py`'s stance applies, and _"a guard satisfied by obfuscation is theatre"_ makes it a reviewer's call. (5) A rule written in TypeScript is invisible to every Python guard. Everything else here was **measured**: fifteen planted evasions run through the function and all fifteen caught, including a seven-line composite that the first version of this guard missed entirely. | `tests/unit/companion/test_routes_format_check.py`, the `find_rule_violations` docstring and `TestNoRuleInTheShell`                                                                               | Review, on any change that computes legality client-side  |
| **How long a card image can take, and that it is queued at all.** `images.py` puts every outbound image fetch through one process-wide pacer: **0.1 s between fetch starts, at most 4 open at once**. Nothing about that reaches the wire — `openapi.json` and `types.d.ts` are byte-identical with or without it, deliberately — so **the generated types tell the tile nothing about it, and this row is where the number lives instead.** What to expect when building the tile: a cold deck grid is **~99 distinct fetches** (measured — a real 100-card deck resolves to 67–99 distinct card ids because basic lands collapse), so the **last tile starts ~9.8 s after the first** and the whole paint takes roughly 10 seconds. That is an **expected observation, not a defect** — NFR-05 excludes first-fetch image paint from its budget — but a tile that shows a spinner with no skeleton, or that gives up on a slow response, will look broken for reasons that are not the CDN's. There is deliberately **no queue-wait ceiling** and no `504`-shaped answer: a request queues until it is served or the client disconnects (cancelling releases the slot immediately). The numbers are a property of _this_ corpus and _this_ machine, which is exactly why they are written here and not published as a wire promise — "a true count read as a false rule". **Measured against real fetches:** real Scryfall CDN latency is **~99 ms per image**; a **warm read from the disk cache is ~10.3 ms per tile** (1.02 s for 99 sequential requests); and a 99-tile deck is **8.5 MB, ~90 KB per `normal` tile**. Two consequences for the tile: the pacer's constants are vindicated by measurement rather than modelled (`min(1/0.1, 4/0.099)` = `min(10, 40.6)`, so the **spacing turnstile binds with 4× headroom** on the semaphore, and the ~10 s cold figure is right for a _concurrent_ client), and **NFR-05's 1 s warm-render budget is not backend-constrained** — at 10.3 ms/tile served sequentially, the constraint will be paint.                                                                                                                                                                                                            | `src/companion/app/images.py`, the `FETCH_SPACING_SECONDS` and `FETCH_CONCURRENCY` docstrings; `tests/unit/companion/test_images.py::TestTheColdDeckPaint`                                        | The tile; real-bytes and real-latency profiling           |
| **That a tile's second render can carry a slightly different `Content-Type` than its first — and how long a warm paint is allowed to take.** `images.py` keeps a disk cache behind the image route, keyed on id + size + face. Nothing about it reaches the wire (`openapi.json` is byte-identical with or without it), so this row is where the two tile-facing facts live instead. **One:** a cold response echoes the CDN's `Content-Type` verbatim, parameters included (`image/jpeg; charset=binary`), while a warm hit derives it from the stored extension and carries the bare media type — the media type itself always matches (the stored spelling is derived from the same header the cold path served), but any _parameters_ are dropped on every render after the first. No measured Scryfall response sends one and no browser acts on one; a tile that keys logic on the full header string rather than the media type would still be keying on a value that legitimately varies. **Two:** a warm deck paint issues zero CDN requests and never enters the pacer (measured: a 99-tile warm burst advances the injected clock by zero spacing intervals), so the ~10-second cold-paint expectation in the row above applies to the FIRST paint of a deck only; a warm grid should fill at disk speed, and a tile designed around a 10-second budget on every paint would be hiding the cache it sits on.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | `src/companion/app/routes/cards.py`, the `_image_response` docstring; `tests/unit/companion/test_routes_card_image.py::TestTheWarmAnswerMatchesTheColdOne` and `TestAWarmTileNeverEntersThePacer` | The tile                                                  |
| **That a tile can stay a placeholder for up to five minutes _after_ the CDN has recovered.** `NegativeCache` remembers image fetch failures with an exponential backoff, keyed on id + size + face: **30 s** after the first failure, doubling per consecutive failure, **capped at 300 s**. A request inside that window is answered from memory as `502 image_fetch_failed` — byte-identical to a fresh failure, deliberately, because the client has no different action to take. **The consequence for the tile is the whole of this row: the backend will keep saying "no picture" for up to 300 seconds after the CDN starts working again, and the SPA has no per-image retry UI** (`EXPERIENCE.md`'s own words: _"negative-cached with backoff — no request storms, no per-image retry UI"_). A tile that waits for the backend to change its mind will look stuck; a tile that retries in a loop will be answered from memory and change nothing. Recovery is automatic on the next request after the window, and a success clears the key's history entirely. **What this does NOT fix, and the tile should not be designed around it as though it did:** the _first_ paint against a dead CDN still issues all ~99 requests and takes roughly **124 s** at `min(1/0.1, 4/5.0)` = 0.8 fetches/s — 99 distinct keys have nothing remembered yet. The pacer bounds that paint; the backoff bounds every one after it. Unlike the two rows above, this behaviour **is** partly on the wire: the 300 s ceiling and the backoff are described in `ErrorResponse`'s generated JSDoc, deliberately, so the fetch author reads it where they work. The numbers themselves live in code, not in the schema.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | `src/companion/app/images.py`, the four `NEGATIVE_CACHE_*` docstrings and `NegativeCache`; `tests/unit/companion/test_routes_card_image.py::TestTheDeckScaleClaim` and `TestRecoveryIsComplete`   | The tile; real-latency profiling                          |
| **Whether a credential's _vocabulary_ reached the generated types.** The discovery leak scan checks `types.d.ts` for the token value itself (which is exact and total) **and** for four literal markers — `agent_token`, `mint_token`, `companion.json`, `Bearer`. The value check is a real gate; the marker list is an **enumeration, not a family**, and the project's own standing agreement says to ban the family instead. It is kept as an enumeration deliberately, because the family here is _"prose that teaches a browser where a credential lives"_ and that is no more statically decidable than UX-DR33's blameless-copy rule. A docstring explaining the credential in words the list does not contain would pass. What genuinely holds the line is structural and lives elsewhere: the credential is read from `request.headers` inside a dependency, so no `securitySchemes` component and no per-operation `security` block can be generated at all (asserted in `test_committed_schema.py`).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | `tests/unit/companion/test_discovery.py::test_the_token_leaks_into_no_surface_of_the_route_that_reads_it`, and `test_committed_schema.py::test_no_security_scheme_is_documented`                  | Review, on any change that adds an agent-only endpoint    |
| **Whether the fresh-install transition happens on a real screen.** The poll, its backoff, its stalled clock and the wire→panel mapping are all asserted in jsdom from ONE mount, which is what makes FR-22's "no manual refresh" a gate rather than a description — but jsdom paints nothing. The live half was confirmed at the HTTP layer instead (empty data dir → `503 database_not_initialized` → plant `cards.db` → `200`, same process, no restart); what no gate here has seen is the PAGE doing it, or the four newly-reachable panels rendered by a browser — in particular the command chip and the two-paragraph guidance/action stack, which `no-active-deck` does not exercise.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | `src/App.test.tsx`'s FR-22 block                                                                                                                                                                  | The manual-testing checklist                              |
| **Whether an element carrying `card-shape` is actually a CARD (UX-DR4).** The `CARD_SHAPED` allowlist gates both halves of the card-radius rule over STYLESHEETS — nothing outside the listed files may spend `--radius-card`, and no listed file may spend a chrome radius — but the class list that puts the shape on an element lives in TSX and is chosen at runtime. `.card-shape` on a `<nav>` reads as a perfectly clean stylesheet. The converse is also invisible: a card-shaped element given a chrome radius by a rule in a NON-card-shaped file (`.deck-row .card-shape { … }`) is in neither half.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | `tests/token-usage.test.ts`, the `CARD_SHAPED` header                                                                                                                                             | Review                                                    |
| **Whether the RIGHT type role was chosen for the content.** MEASURED by a probe that PASSED: putting the truncated card ID back in the uppercase `--type-micro` role — correctly paired with both its companions, so `findRoleWithoutCompanions` was satisfied — left the whole suite green. Every typography guard asks whether a role travels with its companions; none asks whether the role suits the value. The one instance is closed (the ID's block is checked against `cards.py`'s lowercase-only `_CARD_ID_PATTERN`, read from the file), but the GENERAL rule — do not uppercase data the reader may type back — is not statically decidable, because whether a string is retypeable lives in the product.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | `tests/token-usage.test.ts`, the `_CARD_ID_PATTERN` check                                                                                                                                         | Review, on every component that renders an identifier     |
| **Whether a fixed-aspect box is actually laid out that way.** The placeholder's geometry claim is split across two instruments and NEITHER is a pixel: a source read proves `.card-shape` declares `aspect-ratio: 63 / 88` and `border-radius: var(--radius-card)` exactly once in the tree, and a jsdom test proves the rendered element carries the class. `getComputedStyle(el).aspectRatio` in jsdom returns the empty string and would pass for the wrong reason — a recurring trap. That the box IS 63:88 on screen was confirmed by eye against a 176 × 245.9 rule, and so was the match against a real card FACE beside it (see _The card shape_ above).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | `src/components/CardPlaceholder/CardPlaceholder.test.tsx` header                                                                                                                                  | The eye-check                                             |
| **Running `tests/token-usage.test.ts` ALONE crashes the runner.** Measured: `npx vitest run tests/token-usage.test.ts` fails with `TypeError: Cannot read properties of undefined (reading 'config')` — the file imports two `src/` modules across the project boundary, so resolving it standalone picks the wrong project. `npm test` runs it correctly. This matters for PROBES: a single-file invocation exits non-zero for the wrong reason, and a probe harness matching on exit code alone will report a guard as firing when the runner merely crashed. Run the whole suite when proving a guard fires.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | this row                                                                                                                                                                                          | Anyone writing a probe against that file                  |
| **How a screen READER phrases the tile's accessible name.** The NAME itself is pinned exactly: measured with `computeAccessibleName`, jsdom reports `Black Lotus ×4` — `aria-labelledby` ID order (caption first, badge second, the order the component chose), with a space between the references. What no jsdom assertion carries is how a real screen reader ANNOUNCES that name — pauses, the `×` read as "times" or "multiplication sign", the button role placement.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | `src/containers/CardTile/CardTile.test.tsx`, the accessible-name test                                                                                                                             | The manual-testing checklist, with a real screen reader   |
| **Whether `<div>`-inside-`<button>` matters.** `CardPlaceholder`'s root is a `<div>` and `<button>`'s content model is phrasing content, so mounting the placeholder inside the tile is invalid HTML by the letter of the spec. Measured: every engine renders it, React's `validateDOMNesting` does not warn, and the accessible name computes normally. The alternatives were worse — moving the placeholder outside the button breaks UX-DR36's same-box claim, and changing the primitive's root element is an edit to a closed primitive. **Accepted with the argument; the detail art mounts the same placeholder, so the decision can be revisited with two consumers in view.**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | this row, and the `CardTile.tsx` header                                                                                                                                                           | Review                                                    |
| **Whether a reduced-motion fallback actually reaches its motion.** The transform guard compares SELECTOR TEXT, not resolved specificity: a transform on `.card-tile:hover .thing` neutralised by a rule on `.card-tile:hover` reads as unregistered even though the cascade would switch it off. That is a false FAILURE, whose repair is to write the matching selector — the outcome the rule wants anyway. Resolving it properly needs the cascade, which is the first row of this table.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | `tests/token-usage.test.ts`, the transform-neutralisation guard                                                                                                                                   | The author, loudly; then review                           |

**The four rows above that address the tile have their dispositions here**, so nothing is
left merely ticked:

- **The binary-response type lie** (_"a consumer must read the response as a blob and must not
  derive its handling from the type"_) — **MOOT, by construction.** Nothing in `ui/src` reads the
  image response at all: art reaches the screen through `<img src>` and the browser's HTTP cache,
  so there is no body to mishandle and `posture.test.ts`'s one-door list needed no edit. The row
  stays for whoever eventually fetches image bytes; nobody should.
- **The pacer's cold-paint arithmetic** — **HONOURED.** All ~99 `<img>` mount at once with
  `decoding="async"` and deliberately no `loading="lazy"`. Re-measured: a 99-tile deck is
  **8.47 MB** (the row's 8.5 MB, confirmed) and a fully warm backend serves it at **5.6 ms/tile**
  sequentially — faster than the ~10.3 ms the row records, and the same order.
- **The warm-vs-cold `Content-Type` divergence** — **MOOT.** No code keys on the header, or reads
  it; the tile branches on `load` and `error` events only.
- **The 300-second negative-cache window** — **HONOURED.** The tile shows no spinner, sets no
  timeout and never retries: `onError` fires once per `src` and the failure lives in state, so a
  re-render cannot re-arm it. That is exactly _"a tile that retries in a loop will be answered
  from memory and change nothing"_ implemented rather than merely read.

Backend guards carry the same discipline. The two that matter most here:
`tests/unit/companion/test_import_boundary.py` is **AST-only**, so it sees modules no test imports
but is defeated by `getattr(repo, "create_deck")` — its own docstring forbids routing around it by
convention, because _"a guard satisfied by obfuscation is theatre"_. And
`tests/unit/companion/test_openapi_contract.py` compares the committed schema byte-for-byte against
the live app, which catches drift but **not** meaning: it asserts `Args:` and `>>>` never cross the
wire, but MCP-internal prose and Sphinx role markup (`` :class:`X` ``) sail past it untouched.
That one is a look, not a gate that will tell you.

One more backend limit, worth knowing before trusting an `Allow` header: `errors.supported_methods` recomputes a 405's `Allow` as the union of every partially-matching route, because Starlette builds it from the _first_ match alone and therefore under-reports any path served by more than one method (`/api/active-deck` measured `Allow: GET`, omitting its `PUT`). Recomputing needs a flattened route list, and FastAPI 0.140 does not flatten included routers into `app.routes` — so the walk is written **against attributes**, and a structural change upstream makes it find nothing and silently fall back to Starlette's incomplete header rather than raising inside an error handler. That soft failure is deliberate; the thing that would catch it is a test, not the code.

## Adding a source directory

Every linted `.ts`/`.tsx` file must belong to a tsconfig — ESLint's `projectService` errors
on any file that does not. `src`, `tests/fixtures/a11y` and `tests/fixtures/tsx` are in
`tsconfig.app.json`;
`vite.config.ts`, `config/` and `tests/` are in `tsconfig.node.json`. A new top-level
directory needs adding to one of those two `include` lists.

## Not here yet

**The fetch layer, the store and the card cache.** The boundary as it stands:

- **`src/api/client.ts`** is the ONE door to the network in `ui/src`, asserted exhaustively in
  `tests/posture.test.ts`. It is called `client.ts` rather than `decks.ts` because the property
  that guard protects is _"one door, named exhaustively"_, not _"the door is called `decks.ts`"_:
  a second module per route family fails that green assertion by design, and would mean weakening
  a one-door rule into a per-directory one to buy a filename. It exports `readDecks()`,
  `readCard(cardId)`, `readActiveDeck()`, `readDeck(deckId)`, `readFormatCheck(deckId)` and the
  session reads, each returning a total outcome union and none of them ever rejecting, all
  sharing one private `request()` helper so there is one timeout guard and one `no-store`
  decision.
- **The two boot routes fail in DIFFERENT vocabularies, and that is a design statement.** Measured
  against the committed `openapi.json`: `GET /api/active-deck` publishes `200/400/500` and
  **structurally cannot answer `503`** — `routes/active_deck.py` holds no `DbSession` at all —
  while `GET /api/deck/{deck_id}` publishes `200/400/404/413/500/503`. So database-refusal
  handling is about the second request alone, and the two readers have separate outcome unions
  rather than one that models failures the first route cannot produce.
- **`src/state/`** holds the store: `systemState.ts` (the zustand store plus the `useSystemState`
  hook), `poller.ts` (the backoff and the stalled clock), `panel.ts` (the one place a wire token
  becomes a `StateKey`), **`cards.ts` (the one card hydration cache)**, **`deck.ts` (the boot, the
  refusal vocabulary and `surfaceOf`) and `deckGroups.ts` (the type grouping)**. `cards.ts` and
  `deck.ts` are second and third `create()` calls and still one cache
  and one deck: `useSystemState` subscribes with no selector, so folding them into that store
  would re-render the whole app on every tile's hydration. AD-12 bans a second state LIBRARY, not
  a second store instance. **Nothing outside each slice's own module writes it**, which is
  `tests/store-writes.test.ts` rather than a convention.
- **The deck payload fills the cache, and it is free.** `GET /api/deck/{deck_id}` embeds the whole
  `Card` per row — legalities, `image_uris`, `card_faces` — so `seedDeckCards(deckCards)` writes a
  **hydrated** entry for every id out of the one request the deck boot already makes, and a deck
  view issues **zero** `GET /api/cards/{card_id}`. The boot calls the seeder with the payload its
  own fetch already returns.

  This replaced a per-card sweep. The deck detail used to carry a bounded `CardSummary` per row, so
  anything needing a full record — the flip control's `card_faces`, the detail panel's legalities —
  swept the deck one id at a time: **99 requests** on the largest real deck, 212,436 bytes against
  the 38,182 the summaries cost, and a mount total of 106 requests where it is now **5** (decks,
  active-deck, deck detail, format check, session) at any deck size. `App.test.tsx` pins that five.

  `hydrateCard(cardId)` is still the path for an id the open deck does NOT contain — the agent
  views hydrate arbitrary thumbnails — deduping concurrent callers onto one shared promise. That
  route now sends `Cache-Control: private, max-age=3600`, so a repeat within the hour costs no
  round trip; `client.ts` still passes `cache: 'no-store'` on its own reads, because the in-memory
  cache already guarantees one request per id per tab and a read it _does_ issue is one it wanted
  fresh.

- **The WebSocket.** `openAgentSocket` is in `src/api/client.ts` beside the one `fetch` — the
  door list in `tests/posture.test.ts` still reads exactly one entry — and
  `src/state/socket.ts` takes the factory INJECTED so the loop
  module never contains the banned identifier. The loop mints a fresh ticket per attempt, backs
  off 2/4/8/16/30 s, and announces `disconnected` after 60 s AND 4 failures while continuing to
  retry behind the panel.
- **What still does NOT exist:** any `fetch` for image BYTES — art
  reaches the screen through `<img src="/api/card-image/…">` and the browser's own HTTP cache,
  backed by `IMAGE_CACHE_CONTROL` and the backend's disk cache. There is no image cache in
  `ui/src` and there should not be one. **The card tile puts remote images on the screen and
  leaves the door list untouched**, which is the point: an `<img src>` is a request the browser
  makes, not one the app makes. The URL is built by `cardImageUrl` in
  `src/containers/CardTile/imageUrl.ts` — deliberately NOT in `client.ts`, whose whole meaning is
  "requests are made here" — and it spells no `size`, because `normal` is the route's default and
  **the URL is the browser's cache key**. The detail render (a larger size) and the flip control
  (`face=1`) extend that one function rather than each writing a second template string.

**The retry rule.** The deck poll retries `503`s quietly, and it is safe
to because `/api/decks` **has no path parameter**. Measured and pinned in
`test_routes_cards.py`: a malformed id sent to a backend with no database answers
`database_not_initialized`, not `invalid_request`, because FastAPI solves dependencies before it
collects validation errors. So a per-card fetch that copied this retry loop would retry a request
whose id can never succeed, forever. **`readCard` therefore has no retry at all** — one request,
no timer, no loop — and the bound lives with the thing that decides to ask again:
`MAX_ATTEMPTS_PER_CARD = 3` in `src/state/cards.ts`, counted per id and cumulatively across calls.
A `card_not_found` is terminal on the first answer and remembered for the life of the tab.

**A card refusal never puts a panel on the glass** (FR-13). `panelFor()` is not called on the card
path, and that is a rule: `card_not_found` maps to `null` in `PANEL_FOR_REASON` and `panelFor`
clamps `null` to `'internal-error'`, so routing a card token through it would replace a working
deck view with _"The companion hit a bug"_ because one card was missing. `src/state/cards.ts`
records the token and a `PlaceholderKey` from `states.ts`'s own vocabulary; **`CardPlaceholder`
renders it** — its variant type is BUILT from `PlaceholderKey`, so a third placeholder key
added to `states.ts` is a `tsc` failure in the component. A consumer maps `entry.placeholder` to a
variant and passes plain props; **nothing re-derives a placeholder from a wire token**, and a
`switch (entry.reason)` in a component is the drift that field exists to prevent.
One rule to know: a `400 invalid_request` on a CARD read draws the unknown-card placeholder,
even though `states.ts` classifies that token "no UI response at all" — because the
premise behind that classification (_"the SPA never generates a malformed request"_) is exactly
what fails when the id came out of `deck_cards`, a column with no shape constraint.

**A DECK refusal ALWAYS does, and that is the same rule rather than its opposite.** The
deck IS the surface, so there is no view left standing to protect: `src/state/deck.ts` routes deck
refusals through `panelFor()`, and `PANEL_FOR_REASON.deck_not_found → 'no-active-deck'` —
unreachable from the poll, because `/api/decks` does not publish that token — has its live
producer here. The same shape
recurs: a `400 invalid_request` on a DECK read draws the no-active-deck panel, recorded in a
per-context map beside the consumer with `states.ts` untouched, because the id came from
`PUT /api/active-deck`, which stores **any non-blank string up to 256 characters verbatim** and
never checks the deck exists. Letting it reach `panelFor` unmodified answers an agent typo with
_"The companion hit a bug."_

**Which surface is on the glass is decided in ONE expression**, `surfaceOf(deck, system)` in
`src/state/deck.ts`: a loaded deck first, then a deck refusal that decided a panel of
its own, then the system panel. The middle arm is why the order is not simply "deck, else system"
— the deck read's two `503`s must put THEIR panels up, and a rule that let the poll win would make
that criterion pass only by coincidence. `App.tsx` renders the answer and computes none of it.

**The deck boot has no timer and no poll of its own**, and that is the same argument
`readCard` makes one layer down: `MAX_ATTEMPTS_PER_CARD` exists because RENDERS call the card
path in a loop, and nothing loops here. One `GET /api/active-deck` and at most one
`GET /api/deck/{id}` per mount, asserted as a request count over ten minutes of fake time — plus
**one edge-triggered re-drive per poll recovery**: when the poll's panel
transitions INTO `no-active-deck` while the deck state is `refused` or `none`, the boot re-runs
once, so a deck refusal settled during a DB build does not outlive the build (FR-22). The bound
is structural — edges are backend-state transitions, not a loop the client can wind, and a
loaded deck is never re-driven. The boot is re-driven from three triggers, never a second
poller: the poll-recovery edge above, a WebSocket reconnect success, and any `deck_changed` /
`active_deck_changed` frame. A loaded deck is still never re-driven by the POLL edge.

**The stalled threshold:** `STALLED_AFTER_MS = 60_000` in `src/state/poller.ts` — 60
seconds of _continuous_ `database_unavailable`, and that token only. `database_not_initialized`
never escalates, because a multi-minute first build is its normal case. The poll schedule is 2 s,
doubling, capped at 30 s (`POLL_BASE_MS`, `POLL_MULTIPLIER`, `POLL_CEILING_MS`).

The application shell is the token layer's first real consumer. What the shell deliberately does
_not_ build is every region it holds open, each of which renders a placeholder line naming its
owner until a component fills it. **Every region is filled and every placeholder displaced** —
card detail, the deck list, the format check, the agent view that drops into the overlay slot
and the agent-view nav pills — so the count of rendered placeholders is **zero**. The
placeholders themselves all still live in `AppShell.tsx`, un-deleted and still asserted against
the component's own props — displacement, never deletion. **The `h1` carries the deck name**, and
`filled()`'s fallback still fires when there is no deck, which is what keeps a fresh install from
being heading-less.

**The regions are filled by displacement rather than deletion.** The shell's placeholder still
fires whenever its slot is empty, `AppShell.test.tsx` still asserts it against the component's
own props, and what changed is only which of the two the running app shows. Each displacement is
recorded in `App.tsx` beside the prop that causes it.

- **The left column.** With no deck loaded, `App.tsx` passes a `StatePanel` into the `left`
  slot: which panel shows is chosen from the poll response's `reason` token through `states.ts`'s
  `PANEL_FOR_REASON`, and the app transitions from the database panel to the deck on its own with
  no refresh (FR-22). With a deck loaded the slot holds the `CardGrid` instead. The shell is
  untouched either way; its placeholder still fires when `left` is empty.
- **The `h1` and the header badges.** `deckName` takes the deck's name; `badges` takes
  `<DeckBadges />`, which is `Badge`'s first on-screen consumer anywhere in the app. The badges say
  the format (`brawl`, `standard`, …) and the size (`100 maindeck`, plus `15 sideboard` only when
  there is one), all in the `neutral` tone. **They make no legality claim**, and a `positive` tone
  here would assert something the app never asked the backend.

  **There is deliberately no header legality pill**, although the composition reference draws one.
  Its tone would have to be **synthesized** from `format_recognized` plus a scan of the rows — the
  `is_legal` trap — in the one place on screen with no rows beside it to contradict it; and it
  would put a **second** consumer of `GET /api/deck/{id}/format-check` in a **second** column with
  no shared state. The format-check panel in the right column is the one legality surface.

- **The footer.** `App.tsx` passes `<Footer />` into the `footer` slot. Unlike
  every other region this one is **not waiting for data** — the attribution is a condition of
  public release (NFR-08), correct from day one, and nothing replaces it. See _The
  footer attribution_ above for the three rules it carries.

Ten presentation primitives exist — `Panel`, `Badge`, `StatChip`, `GroupHeader`, `ManaPip`,
`ManaCost`, `StatePanel`, `Footer`, `DeckBadges`, `CardPlaceholder` — and all ten are documented
under _Components_ above. Each was checked by eye at its first on-screen consumer: `Panel` in the
card detail (the first real `level="overlay"` panel) and the deck list, `GroupHeader` in the deck
list, `ManaPip`/`ManaCost` in the colour distribution; `StatChip`'s first consumer is the swaps
view.

**`CardGrid`'s `Panel` is UNTITLED.** The counts a
reader needs are already in the `h1` and `DeckBadges`, so a panel title carrying "60 cards · 16
distinct" — the mock's shape — would be the third statement of the same number on one screen; and
an untitled `Panel` invents no name, so it adds no duplicate landmark. **One live constraint:**
`Panel.css` is `overflow: hidden` with 12px body padding, so a tile's `--shadow-rest` is clipped
at the panel's edge. Measured at the eye-check, the 1.06 hover pop itself fits (5.3px per side
against 12px of padding) and the clipping is not visible on this theme — but a lighter theme or a
larger pop would make it so, and `Panel` is a primitive a consumer may not restyle.

**`ManaPip`'s and `ManaCost`'s appearance is DEV-VERIFIED**, on a throwaway harness
that served the BUILT stylesheet to Edge against hand-written markup — the same instrument
used for `Badge`. Five claims hold:
the pip is a **circle**; the hybrid gradient's **hard stop reads as a clean 45° split with no
blur**; the 13px glyph sits centred and legible in the 16.25px circle (`0 2 X T P S` all
checked); the wide case **GROWS into a pill rather than clipping** (`{1000000}`, `{HW}`, `{100}`);
and a 15-pip cost **wraps to a second row inside a 176px card** rather than overflowing it, as
does the 46-character five-face cost. **The CVD question is measured rather than assumed** — see
_Colour is never the sole carrier_ below. What the harness could NOT answer is composition: a
placeholder beside a real card face in a real grid — confirmed by eye later, see _The card shape_.

**`Badge`'s eye-check and contrast numbers.** Rendered in Edge against the running backend
with a real deck active: the pseudo-element wash sits **behind** the text as `z-index: -1` +
`isolation: isolate` intend, so the feared failure — _a solid blank pill with invisible text_ —
does not occur. Measured contrast, all five tones, text over their own wash: `neutral` **7.60:1**,
`accent` **8.33:1**, `positive` **7.97:1**, `negative` **6.17:1**, `caution` **8.99:1** — every
one clear of the 4.5:1 floor. **One number does not clear a floor**: `neutral`'s
`--border-strong` hairline is **1.89:1** against the page and **1.54:1** against its own wash,
under WCAG 1.4.11's 3:1. That is accepted for `neutral` — a badge is a static label, not a UI
component, and its boundary carries no information the wash does not — but it is a live
constraint for the format-check badge, which carries STATE: the four semantic tones' borders
are 6.73–11.49:1 and fine, so a state distinguished by tone is safe and a state distinguished by
the neutral border would not be.

**The format check discharges that constraint by construction, and its numbers are re-measured
on ITS OWN SURFACE.** `TONE_FOR_STATUS` is total over the wire's three statuses and **never returns
`neutral`**, coupled to `BADGE_TONES` by a type-level assert, so the unsafe state is unreachable
rather than avoided. Two corrections to the figures above, both computed from the shipped hexes:
the ratios on record are on `--surface-base`, and this panel's badges sit on `--surface-panel`,
where **`neutral`'s `--border-strong` hairline is 1.75:1 — worse than the 1.89:1 recorded** — while
the three semantic tones measure **`positive` 7.21:1 · `negative` 5.60:1 · `caution` 8.14:1** text
over their own washes (against 7.96 / 6.15 / 8.99 on `--surface-base`, which reproduces the
record above to rounding). All three clear 4.5:1 with headroom. The unmeasured half — any of this
under the four alternate themes — remains open.

The header badge slot is **filled**, with no legality pill beside it (see the bullet above). The
nav pill is a container (`AgentViewsNav`) rather than a primitive, because it subscribes to the
agent-view store per kind and takes focus — the containers rule applied in the direction it is
usually applied. Its rule is `AgentView.css`'s close pill with three states added, since
`DESIGN.md:522` declares those two controls to be one component.

#### Colour is never the sole carrier — the CVD question

_For a sighted colour-vision-deficient user, a pip's colour IS its sole carrier_ — `ManaPip`
draws no glyph for the five WUBRG colours, deliberately (UX-DR7 bans mana-symbol icon fonts, and
the glyph slot is reserved for counts, `{X}` and Phyrexian `P`).

**Measured** rather than eyeballed: the six shipped `--mana-*` colours were pushed
through the Machado severity-1.0 dichromacy matrices in linear RGB and compared pairwise as CIE
Lab ΔE. The **worst pair under each vision type**:

| vision       | worst pair | ΔE       |
| ------------ | ---------- | -------- |
| normal       | B / C      | **24.5** |
| protanopia   | U / B      | **10.0** |
| deuteranopia | R / G      | **14.1** |
| tritanopia   | B / C      | **10.9** |

Every pair stays above ΔE 10 under every simulated deficiency — roughly **4× the just-noticeable
difference** for large flat colour patches — so the five colours remain mutually distinguishable
and the levers held in reserve (a glyph-slot letter, a DESIGN.md amendment) are **not
needed**. Two honest limits: a simulation is not a person, and this measures _distinguishability_
(can you tell two pips apart) rather than _identifiability_ (can you tell which colour a pip is)
— the latter is what `describeManaCost`'s `role="img"` name carries for screen readers, and for a
sighted CVD reader it remains a real gap that only a glyph would close. **Acceptance against a
real screen is the closing step**; the numbers are what that decision weighs.

The shell itself builds no focus management; `SkipLink` is a container and the hand-off lives in
`containers/focusHome.ts`. The numeric role has real consumers — the panel count, the
group-header count, the StatChip delta and the mana curve's counts — so `findUnpairedNumericRole`
is not a guard with nothing to guard. Note that the curve's **axis labels** are `--type-micro`,
not the numeric role: DESIGN.md:407 puts counts in `{typography.numeric}` and axis labels in
`{typography.micro}`, so it is the counts above the bars that this guard covers.

`ui/dist` is no longer produced. A few ignore patterns still name it (`ui/.gitignore`,
`.prettierignore`, the stylelint `--ignore-pattern`); they are harmless and deliberately left
alone — each removal is a chance to break a gate for nothing.
