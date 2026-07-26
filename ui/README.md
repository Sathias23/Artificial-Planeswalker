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
`tests/wire-contract.test.ts`, which also bans re-declaring any shape the backend already
describes anywhere under `src/` outside `src/api/`.

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

## Adding a source directory

Every linted `.ts`/`.tsx` file must belong to a tsconfig — ESLint's `projectService` errors
on any file that does not. `src` and `tests/fixtures/a11y` are in `tsconfig.app.json`;
`vite.config.ts`, `config/` and `tests/` are in `tsconfig.node.json`. A new top-level
directory needs adding to one of those two `include` lists.

## Not here yet

The `/ws` proxy entry is **c5-6**. The runtime `fetch` layer is **c3-1**'s first real
consumer, and **c4-1** owns the store and its in-flight deduping — c2-3 deliberately ships the
generated types with no fetch helper, so neither of those designs is pre-empted. The
self-hosted Space Grotesk `.woff2` fonts land in the same build output directory in **c2-5**.

`ui/dist` is no longer produced. A few ignore patterns still name it (`ui/.gitignore`,
`.prettierignore`, the stylelint `--ignore-pattern`); they are harmless and deliberately left
alone — each removal is a chance to break a gate for nothing.
