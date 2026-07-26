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

## The quality gate

All four run in CI and gate the build, and all four are runnable here:

| Command                | What it gates                                                                |
| ---------------------- | ---------------------------------------------------------------------------- |
| `npm run lint`         | ESLint **and** stylelint — both, in one script; `npm run lint` _is_ the gate |
| `npm run format:check` | Prettier                                                                     |
| `npm run typecheck`    | `tsc -b` across both sub-projects                                            |
| `npm test`             | vitest                                                                       |

Some notes that are easy to trip over:

- **Type-checking is `tsc -b`, never `tsc --noEmit`.** `tsconfig.json` has `"files": []` and
  only project references, so a bare `tsc --noEmit` type-checks _zero files_ and exits 0 — a
  perfectly green, perfectly vacuous gate. `tsc -b` builds both referenced projects, which is
  also the only way `vite.config.ts` gets checked at all.
- **CSS rules live in stylelint, not ESLint.** `@eslint/css` ships fifteen rules and none of
  them can restrict a declaration _value_, which is what banning `outline: none` (UX-DR46)
  requires. c2-4 adds four more rules of the same shape. Decided as ruling B1.
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

## Adding a source directory

Every linted `.ts`/`.tsx` file must belong to a tsconfig — ESLint's `projectService` errors
on any file that does not. `src` and `tests/fixtures/a11y` are in `tsconfig.app.json`;
`vite.config.ts`, `config/` and `tests/` are in `tsconfig.node.json`. A new top-level
directory needs adding to one of those two `include` lists.

## Not here yet

The generated `src/api/types.d.ts` is **c2-3**. The `/ws` proxy entry is **c5-6**. The
self-hosted Space Grotesk `.woff2` fonts land in the same build output directory in **c2-5**.

`ui/dist` is no longer produced. A few ignore patterns still name it (`ui/.gitignore`,
`.prettierignore`, the stylelint `--ignore-pattern`); they are harmless and deliberately left
alone — each removal is a chance to break a gate for nothing.
