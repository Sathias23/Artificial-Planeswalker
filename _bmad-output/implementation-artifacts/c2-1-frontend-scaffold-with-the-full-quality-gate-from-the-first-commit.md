---
baseline_commit: 50dddc3
epic: c2
story: c2-1
work_branch: feat/companion-c2
story_branch: feat/companion-c2-1-frontend-scaffold
---

# Story C2.1: Frontend scaffold with the full quality gate from the first commit

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want the `ui/` project created with linting, formatting, unit testing and type checking wired into
CI on day one,
so that the frontend is born under the same discipline as the Python side rather than having it
retrofitted.

**What this story really is.** `ui/` is the **only new toolchain in the entire 76-story feature**
(Spine, *Starter template / greenfield sub-tree*). Every Python story so far was additive to a
package that already had ruff, `mypy --strict`, pytest, pre-commit and CI. This one creates a
greenfield sub-tree inside a brownfield repo and must arrive with an equivalent gate already
closed — because ~40 frontend stories across C2/C4/C6/C7 will be written against whatever is
standing here.

**Four things are already known to break, and all four were measured on this machine at the
baseline commit — do not rediscover them:**

1. **`eslint@10` cannot coexist with the accessibility plugin this story's AC 7 requires.**
   `eslint-plugin-jsx-a11y@6.10.2` is `latest` (there is no newer release) and its peer range stops
   at `^9`. `npm ci` does not warn — it **fails**:

   ```
   npm error code ERESOLVE
   npm error Found: eslint@10.8.0
   npm error Could not resolve dependency:
   npm error peer eslint@"^3 || ^4 || ^5 || ^6 || ^7 || ^8 || ^9" from eslint-plugin-jsx-a11y@6.10.2
   ```

   ESLint's `latest` dist-tag **is** `10.8.0` today, so an unpinned `eslint` in `devDependencies`
   walks straight into this. **ESLint is a second load-bearing pin, exactly like TypeScript**, and
   the Spine does not know about it — it names only the TS one.

2. **`create-vite@9.1.1`'s `react-ts` template no longer ships ESLint at all.** It ships
   **oxlint** (`.oxlintrc.json`, `"lint": "oxlint"`), no vitest, and `typescript: "~6.0.2"`. The
   scaffold command produces a project whose lint story is *not* the one NFR-07 and this story's
   ACs describe. Replacing it is deliberate work, not an oversight to notice later.

3. **`prettier --check` will fail on 100% of files on Brad's machine and pass in CI.**
   `git config core.autocrlf` is `true` here and the repo has **no `.gitattributes`**, so `ui/`
   files check out CRLF locally and LF on ubuntu. Prettier's default `endOfLine: "lf"` treats CRLF
   as a formatting violation — measured:

   ```
   $ npx prettier --check crlf.ts lf.ts
   [warn] crlf.ts
   [warn] Code style issues found in the above file.
   $ npx prettier --check --end-of-line auto crlf.ts lf.ts
   All matched files use Prettier code style!
   ```

   A gate that is red for the project lead and green for CI is worse than no gate.

4. **The `outline: none` rule (UX-DR46) cannot be written with stock ESLint.** ESLint's CSS
   language plugin `@eslint/css@1.4.0` ships exactly fifteen rules and **none** of them restricts a
   declaration value — enumerated from the installed package:

   ```
   font-family-fallbacks, no-duplicate-imports, no-duplicate-keyframe-selectors, no-empty-blocks,
   no-important, no-invalid-at-rule-placement, no-invalid-at-rules, no-invalid-named-grid-areas,
   no-invalid-properties, no-unmatchable-selectors, prefer-logical-properties, relative-font-units,
   selector-complexity, use-baseline, use-layers
   ```

   The epic AC says "when eslint runs"; the tool that can actually do it — and that c2-4's
   hex/`rgba()`/`box-shadow`/`border-radius` bans will need three stories from now — is
   **stylelint**. Decide-once #2 rules on this.

This story also discharges **two C1 retro obligations** that were homed here by name: ruling **R1**
(the dev proxy's `changeOrigin`, closing c1-5 Open Question 2) and **action item 3** (the
`--platform` mypy gate gap, deferred out of c1-9 because AC 19 froze `ci.yml`). It is the first
story since c1-2 permitted to edit `.github/workflows/ci.yml`.

## Acceptance Criteria

### The scaffold

1. **`ui/` is a Vite + React + TypeScript project at the repository root, and `npm ci && npm run
   build` succeeds from a fresh checkout.** `ui/package-lock.json` is **committed** — `npm ci`
   refuses to run without it. The lockfile must be `lockfileVersion: 3` and must carry the
   **optional platform binaries for every OS**, not just Windows: Vite 8 bundles with rolldown and
   compiles CSS with lightningcss, both of which ship per-platform native packages. Generate the
   lock with a plain `npm install` (never `--no-optional`, never `--omit=optional`) and verify:

   ```
   node -e "const l=require('./package-lock.json'); console.log(l.lockfileVersion,
     Object.keys(l.packages).filter(k=>/linux|win32|darwin/.test(k)).length)"
   ```

   Measured on the probe install of this exact dependency set: `3 20`, including
   `@rolldown/binding-linux-x64-gnu` and `lightningcss-linux-x64-gnu`. **A lock without the linux
   bindings green-lights locally and dies in CI** with `Cannot find module @rolldown/binding-…`.

2. **Node is required only for development and CI — never at install or runtime of the Python
   package (NFR-07, AD-13).** Prove it by boundary, not by assertion: `pyproject.toml` is untouched
   by this story (AC 21), nothing under `src/` gains a Node dependency, and the existing
   `quality` CI job continues to install no Node. `package.json` declares
   `"engines": {"node": ">=20.19.0"}`.

   > The epic says "Node >= 20". The measured floor is **`vite@8.1.5` engines
   > `^20.19.0 || >=22.12.0`**, and `stylelint@17` requires `>=20.19.0` — so a literal Node 20.0
   > does not build. `>=20.19.0` is the honest form of the same requirement and is what CI must
   > pin to. Record the discrepancy in the story's Completion Notes; it is a copy fix for c8-4,
   > not a scope change.

3. **The stack floors are Vite >= 8, React >= 19.2, zustand >= 5.0, and no second data-fetching or
   state-management library is present (AD-12).** zustand is installed **now**, in this story, so
   that AD-12's "one store, one owner" rule is a standing fact rather than a c4-1 decision. A test
   or CI check reads `ui/package.json` and fails if any of `react-query`/`@tanstack/react-query`,
   `swr`, `redux`, `@reduxjs/toolkit`, `mobx`, `jotai`, `recoil`, `valtio` or `axios` appears in
   `dependencies` or `devDependencies`. Pair it non-vacuously: the same test must assert `zustand`
   **is** present, so a typo in the package-reading code cannot make the ban pass by finding
   nothing. The same test asserts `openapi-typescript` is in **`devDependencies` and not
   `dependencies`** (Ruling B2) — one place that reads `package.json`, three facts.

4. **`typescript` is declared `>=5.9 <6.1` — a pin, not an open floor — with the reason recorded in
   a comment or ADR reference next to it.** The recorded reason must be **accurate**, and the
   accurate reason has two measured halves:

   - **Unconstrained, an open floor resolves to TypeScript 7.** `npm view typescript dist-tags`
     gives `latest: 7.0.2`, and a lone `{"typescript": ">=5.9"}` installs `typescript@7.0.2`
     (measured). `typescript-eslint@8.65.0` publishes peer `typescript: ">=4.8.4 <6.1.0"`, so
     TypeScript 7 breaks the ESLint gate outright.
   - **With `typescript-eslint` present, npm back-solves rather than failing** — the same open
     floor alongside `typescript-eslint@^8.65.0` resolves to `typescript@6.0.3`, not 7 (measured).
     So the pin's job is not only to stop a hard `npm ci` failure; it is to keep the constraint
     **explicit and owned here** instead of emergent from a transitive peer that a future
     dependency bump could relax silently.

   Do not write "an open floor breaks `npm ci` outright" without that second half — it is only
   true when `typescript-eslint` is absent.

   **`openapi-typescript` is installed in this story (Ruling B2), and it is what pins the resolved
   version.** Its peer is `typescript: "^5.x"`, so with it present the same declared range resolves
   to **`typescript@5.9.3`**; without it, to `6.0.3`. Installing it here — one devDependency line,
   dev/CI-only, already named in the Spine — means c2-3 wires the generation script against a lock
   that already satisfies it, instead of downgrading TypeScript after two stories of code. Two
   constraints follow, both verifiable:

   - `openapi-typescript` appears in **`devDependencies` only**, never `dependencies` (c2-3's own
     AC requires this; assert it in the same package.json test as AC 3).
   - **Nothing is wired to it.** No generation script, no `ui/src/api/types.d.ts`, no CI step —
     those are c2-3's, and a keyed comment beside the dependency says so (AC 19).

   Confirm the resolved version out of `package-lock.json` rather than assuming: if it is not
   `5.9.x`, something else in the graph is constraining it and that is a finding to record.

5. **`eslint` is declared `^9` (equivalently `>=9 <10`) and carries the same kind of recorded
   reason.** This pin is **not** in the Spine's stack table and is being added by this story: see
   the ERESOLVE output above. `eslint@9.39.5` is the current `maintenance` dist-tag and is what the
   probe install resolved. Lifting it requires `eslint-plugin-jsx-a11y` to publish an `^10` peer
   range; until then, raising ESLint deletes the UX-DR47 gate.

6. **The scaffold's default linter is removed deliberately, not left alongside.** `create-vite`'s
   `.oxlintrc.json` and the `oxlint` devDependency and its `"lint": "oxlint"` script do **not**
   survive into the committed tree. `npm run lint` runs ESLint. A stray second linter would mean
   two rule sets disagreeing about the same file and neither being the gate.

### The quality gate

7. **CI runs eslint, prettier `--check`, TypeScript type-checking and vitest, and each one gates the
   build (NFR-07).** All four are also available as `ui/package.json` scripts so a developer runs
   locally exactly what CI runs. Type-checking uses the template's project-references layout
   (`tsconfig.json` → `tsconfig.app.json` + `tsconfig.node.json`); the check is `tsc -b` (both
   sub-projects already set `"noEmit": true`), **not** a bare `tsc --noEmit`, which would ignore
   `vite.config.ts` entirely.

8. **The eslint config includes accessibility rules that fail on a click handler attached to a
   non-interactive element (UX-DR47).** `eslint-plugin-jsx-a11y` with at least
   `jsx-a11y/no-noninteractive-element-interactions` and
   `jsx-a11y/no-static-element-interactions` at **error**. Prove it the way c1-5 onward proved
   every rejection — **paired with an acceptance from the same run**: a fixture with
   `<div onClick={…}>` is reported, and a fixture with `<button onClick={…}>` in the same lint
   invocation is clean. A test that only shows the violation cannot distinguish "the rule fired"
   from "the config errors on everything".

9. **`outline: none` without a replacement focus style is reported (UX-DR46).** Implemented in
   **stylelint** over `ui/**/*.css` (Decide-once #2), running as part of the same
   `npm run lint` gate, with `declaration-property-value-disallowed-list` banning `outline: none`
   and `outline: 0`. Same non-vacuity pairing: a stylesheet using `outline: none` alongside a
   `:focus-visible` replacement is *still* reported (the rule is deliberately blunt — the
   replacement is asserted by human review and by c2-4's token work, not by the linter), and a
   stylesheet with no `outline` declaration is clean.

10. **`prettier --check` is green on Brad's Windows checkout and on ubuntu CI, from the same
    commit.** Add **`ui/.gitattributes`** containing `* text=auto eol=lf` so the sub-tree checks out
    LF regardless of the repo-wide `core.autocrlf=true`. Scope it to `ui/` — a root-level
    `.gitattributes` would renormalise every tracked file in the repository, which is not this
    story's change. Setting `endOfLine: "auto"` in the prettier config is the alternative and is
    **rejected**: it would let CRLF and LF both pass, and c2-2/c2-3's `git diff --exit-code` drift
    checks need one deterministic byte sequence.

11. **A vitest test exists and actually asserts something.** At minimum one component test that
    renders through `@testing-library/react` under `jsdom` and one plain unit test. The suite must
    go **red** if the component under test is emptied — state that check in the Completion Notes
    with the failing output, per the standing *non-vacuity pairing* agreement.

### The dev proxy (Ruling R1)

12. **The Vite dev server proxies to the companion backend and sets `changeOrigin: true`.** Proxy
    `/api` and `/health` — the two surfaces that exist or are imminent — to
    `http://127.0.0.1:${COMPANION_PORT ?? 8765}`, reading the same environment variable name the
    backend reads (`COMPANION_PORT`, renamed by C1 retro ruling R4;
    [server.py](src/companion/app/server.py) is the declaration site). Do **not** hard-code `8765`
    anywhere else — `DEFAULT_PORT` in `server.py` is the only place in `src/` that names it and the
    frontend should mirror that discipline via the env var plus one documented default.

13. **`changeOrigin: true` is asserted by a real round trip, not only by reading the config.** The
    config assertion (`vite.config.ts`'s proxy entry has `changeOrigin === true`) is necessary and
    insufficient — it is precisely the vacuous shape the C1 retro punished twice. Add a vitest test
    that:
    - starts a throwaway `node:http` server that records the `Host` header it receives,
    - starts a real Vite dev server (`createServer` from `vite`) pointed at it on an ephemeral port,
    - fetches a proxied path, and asserts the recorded `Host` is the **target's** authority
      (`127.0.0.1:<targetPort>`),
    - and, as the non-vacuity pair, repeats it with `changeOrigin: false` and asserts the recorded
      `Host` is the **Vite** server's authority.

    The second half is the whole point: without the rewrite, [security.py](src/companion/app/security.py)'s
    `host_is_allowed` compares the forwarded `Host` against
    `allowed_authorities(port) = {"127.0.0.1:<backendPort>", "localhost:<backendPort>"}`, misses,
    and `HostValidationMiddleware` answers **`400 {"reason": "invalid_request"}`** for *every*
    proxied call. R1 accepted the second dev-time origin on condition that this is asserted rather
    than discovered.

14. **The proxy is documented where a developer will meet it.** `ui/README.md` (or `CONTRIBUTING.md`
    — one place, not both) states the dev loop: backend via
    `uv run artificial-planeswalker companion`, frontend via `npm run dev`, and *why*
    `changeOrigin` exists, naming the typed 400 it prevents.

### CI, and the C1 debts this story clears

15. **`.github/workflows/ci.yml` gains a frontend job.** Node is installed with `actions/setup-node`
    **pinned by commit SHA** — the repo's standing convention, see the existing `checkout` and
    `setup-uv` steps. Current `v7` tag resolves to
    `820762786026740c76f36085b0efc47a31fe5020`; verify it yourself before committing
    (`gh api repos/actions/setup-node/git/refs/tags`) rather than trusting this line. Use
    `node-version: 20` (the declared floor — `setup-node` resolves it to the latest 20.x, which
    satisfies `>=20.19.0`), `cache: npm` and
    `cache-dependency-path: ui/package-lock.json`. The job runs `npm ci` then the four gates. It
    must **not** be folded into the existing `quality` matrix job — that job is a
    Python 3.12/3.13 matrix and would install Node twice for no reason. **One job, no Node matrix**
    (Ruling B5): the floor is the version nobody develops on and therefore the one worth gating;
    current Node is covered incidentally by Brad's local v24.15.0.

16. **The same edit closes the `--platform` mypy gate gap (C1 retro action item 3).** The `quality`
    job gains **`uv run mypy src/ --platform win32`** alongside the existing `uv run mypy src/`.

    > **The epic AC and the retro's success criterion disagree, and the success criterion wins.**
    > The epic text says to add "`mypy src/ --platform linux` alongside `mypy src/`" — true from
    > Brad's Windows machine, where the bare run *is* the win32 run. CI is `ubuntu-latest`, where
    > the bare run is already the linux run, so adding `--platform linux` there would be a pure
    > no-op and the stated success criterion ("a deliberately Windows-broken `singleton.py` branch
    > fails CI") would still not hold. Add `--platform win32`. Flag this in the Completion Notes
    > the way c1-9 flagged its own internally-impossible AC pair — do not silently satisfy the
    > letter of the epic text.

    All three invocations pass at the baseline commit; verified before writing this story:

    ```
    uv run mypy src/                     -> Success: no issues found in 83 source files
    uv run mypy src/ --platform linux    -> Success: no issues found in 83 source files
    uv run mypy src/ --platform win32    -> Success: no issues found in 83 source files
    ```

17. **Prove the new mypy step has teeth.** Temporarily break the Windows half of
    [singleton.py](src/companion/app/singleton.py) (e.g. call `msvcrt.locking` with a wrong arity
    inside the `if sys.platform == "win32":` branch), confirm `uv run mypy src/ --platform win32`
    goes red while `uv run mypy src/ --platform linux` stays green, paste both outputs into the
    Debug Log, and revert. This is the retro's literal success criterion; a green CI proves nothing
    on its own.

18. **`deferred-work.md` is updated, not appended to.** Close the c1-9 review entry *"The 'both
    mypy runs are mandatory' comment is enforced by no gate"* (line ~977) in place, recording what
    actually shipped (`--platform win32` in CI, and why not `linux`). If ruling R1 left a
    corresponding entry, close that too.

19. **Every forward-dated comment this story writes carries a story key** (C1 retro action item 1,
    now a standing agreement). Concretely: the proxy's missing `/ws` entry is c5-6's to add, the
    `outDir` redirect into `src/companion/app/static/` is **c2-2's**, and the generated
    `ui/src/api/types.d.ts` is **c2-3's**. Where a config or comment asserts one of those absences,
    it names the story key in the same commit.

### Boundaries

20. **`src/companion/app/static/` is not created and `vite.config.ts` keeps the default `outDir`.**
    The build lands in `ui/dist` for this story. Redirecting the output, committing the bundle,
    serving it from FastAPI and mirroring it into `plugin/` are **all** c2-2. `ui/dist` is already
    ignored — `create-vite` writes a `ui/.gitignore` covering `node_modules` and `dist`, and the
    root [.gitignore](.gitignore) additionally ignores unanchored `dist/`.

21. **Nothing outside this story's surface is touched.** Prove it by command and paste the output,
    the way all nine C1 stories did:

    ```
    git status --porcelain -- pyproject.toml uv.lock .pre-commit-config.yaml .gitignore \
      src/ tests/ plugin/ scripts/ README.md CONTRIBUTING.md .mcp.json
    ```

    must be **empty**. In particular: no `pyproject.toml` edit (AC 2 depends on it), no
    `.pre-commit-config.yaml` edit (the frontend gate is CI-only for now — Decide-once #4), and no
    `src/` edit (which would also trip the `build-plugin-sync` pre-commit hook and drag the
    `plugin/` mirror into a frontend-scaffold commit).

22. **The full existing Python suite is unchanged and green**: `uv run pytest -m "not integration"`
    at the same count as the baseline (**1,684 passed / 1 skipped / 45 deselected** as of the C1
    retro's R4 commit — confirm the baseline yourself in Task 0 before you start, per the standing
    *Task 0 story-start verification* agreement).

## Tasks / Subtasks

- [x] **Task 0 — Baseline verification** (standing agreement; do this before touching anything)
  - [x] `git rev-parse --short HEAD` = `50dddc3`, `git status --porcelain` empty, branch
        `feat/companion-c2`
  - [x] `uv run pytest -m "not integration"` → record the exact counts
  - [x] `uv run mypy src/`, `uv run mypy src/ --platform linux`, `uv run mypy src/ --platform win32`
        → all three green (they are, at `50dddc3`)
  - [x] `node --version` / `npm --version` → this machine has **v24.15.0 / 11.12.1**; note that the
        local Node is *not* the CI floor, so a local-only green build does not prove AC 2

- [x] **Task 1 — Scaffold `ui/`** (AC 1, 3, 6, 20)
  - [x] `npm create vite@latest ui -- --template react-ts` from the repo root
  - [x] Delete `.oxlintrc.json`, the `oxlint` devDependency and the `"lint": "oxlint"` script
  - [x] Delete the template's demo assets that will never ship (`src/assets/*`, `public/icons.svg`,
        the counter demo in `App.tsx`) — keep `index.html` and `main.tsx`; c2-6 replaces `App.tsx`
        with the real shell
  - [x] Add `zustand` (dependency) and `openapi-typescript` (**devDependency**, Ruling B2, with the
        keyed comment saying c2-3 wires it); set `"engines": {"node": ">=20.19.0"}`; set `<title>`
        in `index.html` to the product name
  - [x] `npm install` → confirm the lockfile's `lockfileVersion` and cross-platform binding count

- [x] **Task 2 — Pin the two load-bearing versions** (AC 4, 5)
  - [x] `typescript` → `>=5.9 <6.1`, with the two-part reason recorded verbatim next to it
  - [x] `eslint` → `^9`, with the ERESOLVE reason recorded next to it
  - [x] Re-run `npm install` and read the resolved versions out of `package-lock.json` — do not
        assume. With `openapi-typescript` present (Ruling B2) the probe resolved
        **`typescript@5.9.3`** / `eslint@9.39.5`. Anything other than `5.9.x` means something else
        is constraining the graph: record it, don't work around it
  - [x] *(added)* A **third** pin was required: `@testing-library/jest-dom` → `~6.9.1`

- [x] **Task 3 — ESLint flat config** (AC 7, 8)
  - [x] `eslint.config.js` (flat config): `typescript-eslint` recommended + type-aware,
        `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`, `eslint-plugin-jsx-a11y`
  - [x] Set the two a11y rules to `error`
  - [x] Write the paired fixture test: `<div onClick>` reported, `<button onClick>` clean, one run

- [x] **Task 4 — Prettier + line endings** (AC 7, 10)
  - [x] `.prettierrc` + `.prettierignore` (ignore `dist`, `node_modules`, and — forward-dated with
        the key — **c2-3's** generated `src/api/types.d.ts`)
  - [x] `ui/.gitattributes` with `* text=auto eol=lf`
  - [x] Re-clone or `git rm --cached -r ui && git reset` to confirm the working tree comes back LF,
        then `npm run format:check` green **on Windows**

- [x] **Task 5 — stylelint** (AC 9)
  - [x] `stylelint` + `stylelint-config-standard`, config at `ui/.stylelintrc.json`
  - [x] `declaration-property-value-disallowed-list` for `outline: none|0`
  - [x] Paired fixture test; wire into `npm run lint`
  - [x] Leave a keyed comment: the hex/`rgba()`/`box-shadow`/`border-radius` bans are **c2-4's**

- [x] **Task 6 — vitest** (AC 7, 11)
  - [x] `vitest` + `jsdom` + `@testing-library/react` + `@testing-library/jest-dom`
  - [x] `test` block in `vite.config.ts` (with `/// <reference types="vitest/config" />`) or a
        separate `vitest.config.ts` — one of them, not both
  - [x] One component test, one unit test; prove the component test goes red when the component is
        emptied

- [x] **Task 7 — Dev proxy + R1** (AC 12, 13, 14)
  - [x] `server.proxy` for `/api` and `/health`, target from `COMPANION_PORT` with 8765 default,
        `changeOrigin: true`
  - [x] Config assertion **and** the two-direction real round-trip test
  - [x] Document the dev loop and the reason for `changeOrigin`

- [x] **Task 8 — CI** (AC 15, 16, 17)
  - [x] New `frontend` job: pinned `setup-node` SHA, `node-version: 20`, npm cache keyed on
        `ui/package-lock.json`, `npm ci`, then the four gates
  - [x] `uv run mypy src/ --platform win32` added to the `quality` job
  - [x] Run the deliberate-break proof and paste both mypy outputs into the Debug Log

- [x] **Task 9 — Records and gates** (AC 18, 19, 21, 22)
  - [x] Close the c1-9 mypy-gate entry in `deferred-work.md` in place
  - [x] Scope-boundary `git status --porcelain` proof, pasted
  - [x] Full Python suite at baseline counts; all three mypy runs green; ruff lint + format green
  - [x] Note the `Node >= 20` → `>= 20.19.0` copy discrepancy for c8-4

- [x] **Task 10 — Live checks a test cannot close**
  - [x] Start the backend (`uv run artificial-planeswalker companion`), start `npm run dev`, open
        the Vite URL and confirm a proxied `/health` returns `200` with the real `instance_id` —
        not `400 invalid_request`. This is R1 end to end with two real processes; the vitest proxy
        test uses a stub target and cannot prove the middleware accepts the rewritten `Host`
  - [x] Repeat once with `COMPANION_PORT` set to a non-default value on both sides

## Dev Notes

### Decide-once rulings (made here so c2-2 … c2-10 and the C4/C6/C7 frontend stories inherit them)

**#1 — ESLint is pinned to `^9`, and that pin is this story's own decision.** The Spine's stack
table lists only the TypeScript pin. The measured ERESOLVE above makes ESLint a second one of the
same kind, and it must be recorded with the same weight — in `package.json` next to the dependency,
not only in this story file, because the next person to run `npm update` will read `package.json`
and nothing else. The exit condition is explicit: lift it when `eslint-plugin-jsx-a11y` publishes
an `^10` peer range. **Confirmed by Brad as Ruling B3**, which also declined oxlint outright.

**#2 — CSS rules are enforced by stylelint, not ESLint.** The epic AC phrases UX-DR46 as "when
eslint runs", but `@eslint/css`'s fifteen rules contain nothing that can restrict a declaration
value (enumerated above from the installed package), so satisfying the letter would require
authoring and maintaining a custom ESLint rule against an experimental CSS AST. stylelint's
`declaration-property-value-disallowed-list` does it in one config line, and **c2-4 needs four more
rules of exactly this shape** — hex, `rgba()`, `box-shadow`, `border-radius`. The intent of the AC
is "the lint gate reports it"; `npm run lint` runs both tools and `npm run lint` is the gate.
**Confirmed by Brad as Ruling B1.**

**#3 — zustand is installed in c2-1, before anything stores state.** AD-12's "no second
data-fetching or state library joins zustand" is only enforceable against something. Installing it
here makes AC 3's ban test meaningful from the first commit rather than from c4-1, and costs one
dependency line.

**#4 — the frontend gates are CI-only; `.pre-commit-config.yaml` is not touched.** pre-commit hooks
run on every Python commit, and `npm ci`/`eslint` on a Python-only change would be a several-second
tax on every commit for a sub-tree that did not change. NFR-07 says "Frontend gets equivalent
tooling (eslint, prettier, vitest) **in CI**" — CI is the stated venue. A `files: ^ui/`-scoped
local hook is the obvious later refinement if the CI round trip proves too slow.
**Confirmed by Brad as Ruling B4.**

**#5 — the dev proxy reads `COMPANION_PORT`, the same variable the backend reads.** One name, two
processes, no second convention to document in c8-4. The backend's `PORT_ENV_VAR` constant lives in
[server.py](src/companion/app/server.py) and was renamed from `PLANESWALKER_COMPANION_PORT` by C1
retro ruling R4 on 2026-07-26 — read the current value out of the module rather than trusting this
sentence.

### Architecture rules this story implements

- **AD-13**, the half that is not c2-2's: *"Node is dev/CI-only and must not be required at install
  or runtime."* AC 2 is that sentence made structural — the proof is that `pyproject.toml` never
  learns about `ui/`.
- **AD-12**, its second paragraph: *"No second data-fetching or state library joins zustand."*
  AC 3 turns it into a test, three stories before there is a store to protect.
- **NFR-07**: *"Frontend gets equivalent tooling (eslint, prettier, vitest) in CI. … Applies to
  every phase from the first commit."* That last clause is why this story exists at all and why it
  is first in the epic.
- **UX-DR46 / UX-DR47**: the two design requirements that are *lint rules* rather than components.
  Landing them now is the same bet c1-1 made with the import boundaries — and the C1 retro's
  headline finding was that the bet paid: `test_import_boundary.py` was never edited once across
  eight subsequent stories.
- **Spine, *Starter template / greenfield sub-tree***: *"it lands in the SPA-foundation epic, which
  must therefore carry the scaffold-creation story as its first story."*

### Source tree — what exists, what this story adds

```text
ui/                             # NEW — the entire sub-tree
  .gitattributes                # NEW — * text=auto eol=lf   (AC 10)
  .gitignore                    # NEW — from the template (node_modules, dist)
  .prettierrc / .prettierignore # NEW
  .stylelintrc.json             # NEW — outline:none ban     (AC 9; c2-4 extends)
  eslint.config.js              # NEW — flat config          (AC 8)
  package.json                  # NEW — the two pins live here
  package-lock.json             # NEW — COMMITTED; npm ci requires it
  index.html                    # NEW — from the template, title changed
  tsconfig.json                 # NEW — project references (app + node)
  tsconfig.app.json             # NEW
  tsconfig.node.json            # NEW
  vite.config.ts                # NEW — react plugin, dev proxy, vitest block
  README.md                     # NEW — the dev loop + why changeOrigin  (AC 14)
  src/
    main.tsx  App.tsx  index.css  App.css     # NEW — template, demo stripped
    __tests__/ (or *.test.tsx alongside)      # NEW — the gate-proving tests
.github/workflows/
  ci.yml                        # UPDATE — new `frontend` job; `--platform win32` on `quality`
_bmad-output/implementation-artifacts/
  deferred-work.md              # UPDATE — close the c1-9 mypy-gate entry in place
```

**Current state of the files being modified** (read before editing):

- [.github/workflows/ci.yml](.github/workflows/ci.yml) — 68 lines, one job (`quality`), matrix
  `python-version: ["3.12", "3.13"]` on `ubuntu-latest`. Steps: checkout (SHA-pinned
  `9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0`), `setup-uv` (SHA-pinned
  `fac544c07dec837d0ccb6301d7b5580bf5edae39`, `enable-cache: true`), `uv sync --locked`, ruff
  check, ruff format check, `uv run mypy src/`, `uv run pytest -m "not integration"`, and the
  `plugin/` drift check. **What must be preserved:** every action stays SHA-pinned with the version
  in a trailing comment; `permissions: contents: read` unchanged; the `concurrency` block unchanged
  (it deliberately lets push-to-master runs finish); the plugin drift step stays **last** in
  `quality`; `pytest` stays scoped to `not integration`. The header comment says "No DB, model,
  network, or secrets are required" — a Node job downloads from the npm registry, so extend that
  comment rather than leaving it false.
- [.gitignore](.gitignore) — 104 lines. Already ignores unanchored `dist/`, `build/`, `lib/`,
  `.venv/`, and anchored `/data/`, `/temp/`. **It does not mention `node_modules`** — the
  template's own `ui/.gitignore` covers it, which is why AC 21 forbids editing the root file. Note
  the load-bearing comment at the bottom: `plugin/` is committed on purpose.
- [.pre-commit-config.yaml](.pre-commit-config.yaml) — ruff, ruff-format, then a `mypy --strict
  --ignore-missing-imports` hook scoped `files: ^src/` with an explicit
  `additional_dependencies` list, then the local `build-plugin-sync` hook. **Read it, do not edit
  it** (Decide-once #4). Its `additional_dependencies` list is the third declaration site c1-2
  enumerated — relevant only if a *Python* dependency changes, which this story has none of.
- [src/companion/app/singleton.py](src/companion/app/singleton.py) — the module AC 17 deliberately
  breaks and reverts. Lines 56-59 carry the comment this story finally backs with a gate: *"each
  platform's run type-checks only its own half … `mypy src/` and `mypy src/ --platform linux` are
  therefore mandatory and neither is redundant."* Consider whether that comment should now name the
  CI step; if you change it, that is a `src/` edit and AC 21 forbids it — so **leave it and record
  the observation for a later story instead.**
- [src/companion/app/security.py](src/companion/app/security.py) — `allowed_authorities(port)`
  returns `{"127.0.0.1:{port}", "localhost:{port}"}` (plus the bare authority only when the port is
  80), and `host_is_allowed` lowercases and strips before an **exact** match. That exactness is why
  `changeOrigin` is not optional. Read it; do not edit it.
- [src/companion/app/routes/health.py](src/companion/app/routes/health.py) — `GET /health`,
  **unauthenticated by design**, returns `{"status": "ok", "instance_id": …}`. It is the only
  shipped route today and therefore the only honest target for Task 10's live proxy check.

**Deviation from the Spine's Structural Seed:** none in shape — the seed already lists
`ui/  # SPA source — Vite/React/zustand; builds into app/static`. Two **additions to the Spine's
stack table** are recorded by this story: the `eslint ^9` pin (Decide-once #1) and `stylelint` as
the CSS gate (Decide-once #2). Neither moves or renames anything.

### Gotchas specific to this story

1. **`npm ci` is not `npm install`.** It deletes `node_modules`, refuses to run without a lockfile,
   and **fails instead of updating** when `package.json` and the lock disagree. Every pin edit in
   Task 2 must be followed by an `npm install` to re-sync the lock, or CI's `npm ci` dies on a file
   that looked fine locally.

2. **The template's `tsconfig` is a project-references pair, and a bare `tsc --noEmit` silently
   checks nothing useful.** `tsconfig.json` has `"files": []` and only `references`. `tsc --noEmit`
   against it type-checks zero files and exits 0 — a perfectly green vacuous gate. Use `tsc -b`.

3. **ESLint flat config + type-aware `typescript-eslint` needs `projectService` (or an explicit
   `project`), and it will error on files outside the tsconfig `include`.** `eslint.config.js`
   itself, and `vite.config.ts`, are the usual casualties. `tsconfig.node.json` includes only
   `vite.config.ts` — decide up front whether `eslint.config.js` is type-checked or excluded, and
   do it in one place.

4. **`eslint-plugin-jsx-a11y` has no flat-config export in some versions.** Import it as a plugin
   object and enable rules explicitly rather than spreading a `flat/recommended` config that may
   not exist on 6.10.2. Enabling the two rules by name (AC 8) is more precise anyway, and the paired
   fixture test is what proves it worked.

5. **jsx-a11y cannot see a click handler on a *component*, only on a DOM element.**
   `<Foo onClick={…}/>` is invisible to `no-static-element-interactions`. The fixture must use a
   literal `<div onClick>` or the test passes without the rule being on.

6. **A stylelint rule that reports nothing is indistinguishable from a stylelint that never ran.**
   `stylelint` exits 0 when its glob matches no files — and `ui/**/*.css` will match almost nothing
   in this story. Point the paired fixtures at real committed `.css` files (or a fixtures dir the
   config includes) and assert the *violation* case exits non-zero.

7. **`vite`'s `createServer` in the AC 13 test binds a real port and must be closed.** Use port `0`
   / an ephemeral port and `await server.close()` in a `finally` — a leaked dev server keeps vitest
   from exiting and turns a fast suite into a hang. (c1-9 hit the same class of problem from the
   other side: a mutation that *hung* for 591 s instead of failing.)

8. **`changeOrigin` is not the same as `Origin`.** Vite's `changeOrigin: true` rewrites the **`Host`
   header** of the proxied request to the target's authority. It does **not** touch the browser's
   `Origin` header. C5's WebSocket upgrade validates `Origin` *as well as* `Host` (AD-5, NFR-01) —
   that is a c5-3 problem, not solved here, and the proxy config should say so with the story key
   (AC 19).

9. **`create-vite`'s template writes `.gitignore` inside `ui/`, and root `.gitignore` already
   ignores unanchored `dist/`.** Belt and braces, deliberately: do not "tidy" either one away.
   Conversely, do not add `node_modules` to the root `.gitignore` — that is an AC 21 violation for
   zero benefit.

10. **Your local Node is v24.15.0; CI's floor is 20.** Vite 8 supports both, but a green local build
    proves nothing about the floor. If anything in the toolchain turns out to need >= 22, that is a
    finding to record and escalate, not to paper over by raising the CI node-version.

11. **`prettier --check` on a freshly scaffolded template will fail before you have written a line.**
    The template's own files are not prettier-formatted to your config. Run `prettier --write` once
    over `ui/` as part of Task 4 and commit that, or the gate is red at its first run for reasons
    that have nothing to do with the gate.

12. **The plugin mirror is not this story's problem — and touching `src/` makes it one.** The
    `build-plugin-sync` pre-commit hook fires on any `^src/` change and rewrites `plugin/`. AC 21's
    `git status` proof is what keeps a frontend-scaffold commit from carrying a regenerated plugin
    tree.

### Testing standards

- **Two suites, two homes, no overlap.** Frontend tests live under `ui/` and run through vitest;
  the Python suite is untouched (AC 22). Do **not** add a pytest test that shells out to `npm` —
  it would need Node at test time and quietly contradict AC 2.
- **Real servers and real files over mocks** — the standing C1 rule (c1-3, restated by c1-7, c1-8,
  c1-9). AC 13's proxy test starts a real Vite server against a real HTTP listener because the
  behaviour under test lives in Vite's proxy middleware, not in a config object.
- **Non-vacuity pairing is an AC here, not a nicety** (standing agreement, promoted at the C1
  retro): every rule this story adds must be shown firing *and* not firing from the same
  invocation — AC 3, 8, 9, 11, 13 and 17 each name their pair.
- **The gate proves itself by breaking.** AC 17's deliberate `singleton.py` break and AC 11's
  emptied component are the two mutations this story owes; paste both outputs.
- `asyncio_mode = "auto"` and the pytest conventions in `pyproject.toml` are unchanged and
  irrelevant here — no Python test is added.

### Previous story intelligence (c1-9, done 2026-07-26; PR #16 merged, then C1 retro + PR #17 to master)

- **c1-9 froze `ci.yml` and `.pre-commit-config.yaml`** (its AC 19), which is *why* the mypy gate
  gap is this story's inheritance rather than a c1-9 patch. The deferred entry naming the fix as
  "one line in either file" is at `deferred-work.md:977`.
- **c1-9's AC 15 was internally impossible** and the dev flagged the contradiction instead of
  quietly picking a side. AC 16 here is the same situation — the epic text and the retro success
  criterion cannot both be satisfied literally. Do the same thing: pick the one that achieves the
  purpose, and say so loudly.
- **Exit-status vocabulary is fixed feature-wide** (c1-9 Decide-once #5): `0` = intent satisfied,
  `2` = the user typed something the program does not understand. Nothing in this story mints an
  exit code, but do not let a new npm script invent one.
- **`COMPANION_PORT` is the settled env-var name** (retro R4, commit `b2ff74b`) and its live
  end-to-end confirmation is an open C1 residual — Task 10's second bullet closes it incidentally.
  If it works, say so in the Completion Notes; `deferred-work.md:993` is the entry it would close.
- **Scope proof by `git status --porcelain -- <paths>` ran nine for nine in C1** with zero
  accidental edits. AC 21 continues it.

### Git intelligence

- `50dddc3` merged PR #17 (`feat/companion-app` → `master`), the C1 integration PR. **Merge is not
  release** — no tag, no CHANGELOG entry until c8-4 (retro R3). This story's branch is cut from
  that master merge.
- `b2ff74b` is the `COMPANION_PORT` rename — one constant in `server.py` plus two docstring sites;
  the tests read `server.PORT_ENV_VAR` and needed no edit. Read the constant, don't retype the name.
- Commit-message convention across the epic: `feat(companion): …`, `fix(companion): …`,
  `docs(companion): …`. A scaffold commit is `feat(companion): …` even though it adds no Python.
- The nine C1 story PRs each targeted the epic umbrella branch, and one integration PR went to
  master after the retro **with no Greptile pass** (OSS free-tier budget, standing rule). This
  story's PR targets `feat/companion-c2`.

### Latest technical information

All version data below was probed against the live npm registry on **2026-07-26** from this
machine — not quoted from documentation.

| Package | `latest` | This story uses | Why |
|---|---|---|---|
| `vite` | 8.1.5 | `^8.1.5` | engines `^20.19.0 \|\| >=22.12.0` |
| `react` / `react-dom` | 19.2.8 | `^19.2.8` | Spine floor >= 19.2 |
| `typescript` | **7.0.2** | `>=5.9 <6.1` | **pinned** — see AC 4 |
| `eslint` | **10.8.0** | `^9` (resolved 9.39.5) | **pinned** — see AC 5 |
| `typescript-eslint` | 8.65.0 | `^8.65.0` | peers: `eslint ^8.57 \|\| ^9 \|\| ^10`, `typescript >=4.8.4 <6.1.0` |
| `eslint-plugin-jsx-a11y` | 6.10.2 | `^6.10.2` | **peer `eslint ^3…^9`** — the pin's cause |
| `eslint-plugin-react-hooks` | 7.1.1 | `^7.1.1` | peer allows `^10`, so it is not the blocker |
| `eslint-plugin-react-refresh` | 0.5.3 | `^0.5.3` | peer `^9 \|\| ^10` |
| `prettier` | 3.9.6 | `^3.9.6` | — |
| `stylelint` / `-config-standard` | 17.14.1 / 40.0.0 | `^17` / `^40` | engines `>=20.19.0` |
| `vitest` | 4.1.10 | `^4.1.10` | engines `^20 \|\| ^22 \|\| >=24` |
| `jsdom` | 29.1.1 | `^29.1.1` | — |
| `@testing-library/react` | 16.3.2 | `^16.3.2` | peers accept React 19 |
| `@vitejs/plugin-react` | 6.0.4 | `^6.0.4` | peer `vite ^8.0.0` |
| `zustand` | 5.0.14 | `^5.0.14` | Spine floor >= 5.0 |
| `openapi-typescript` | 7.13.0 | `^7.13.0`, **devDependency, unwired** | Ruling B2 — installed here, wired by c2-3 |

**The TypeScript resolution is not what the pin alone predicts, and Ruling B2 is what makes it
predictable.** A probe install of this exact dependency set resolved **`typescript@5.9.3`**, not
`6.0.3`, because **`openapi-typescript@7.13.0` peers at `typescript: "^5.x"`**. Without
`openapi-typescript` in the graph the same `>=5.9 <6.1` range resolves to `6.0.3` — and c2-3, adding
`openapi-typescript@^7` two stories later, would hit an ERESOLVE and have to downgrade TypeScript
under existing code. B2 spends one devDependency line now to make that impossible.

**ESLint 10 vs oxlint — declined, not overlooked (Ruling B3).** `create-vite@9.1.1` ships oxlint,
which has jsx-a11y rules built in and no peer-dependency surface at all, and would sidestep
Decide-once #1 entirely. Declined because the epic AC names eslint, `typescript-eslint`'s type-aware
rules have no oxlint equivalent today, and ~40 downstream stories would be written against the
choice. Revisit only if the `eslint ^9` pin becomes genuinely blocking.

**`@eslint/css@1.4.0`** exists and would let ESLint parse CSS, but its complete rule list (fifteen
rules, enumerated in the preamble) contains no declaration-value restriction. This is measured from
the installed package, not inferred from docs.

### Project Structure Notes

- `ui/` sits at the repository root, a sibling of `src/`, `tests/`, `scripts/` and `plugin/` — as
  the Spine's Structural Seed draws it. It is **not** under `src/`: `pyproject.toml`'s
  `[tool.hatch.build.targets.wheel] packages = ["src"]` would otherwise sweep the whole Node
  project into the wheel and violate AD-13.
- Python tooling ignores `ui/` for free: `ruff check .` only visits Python files, `mypy src/` is
  path-scoped, and `pytest`'s `testpaths = ["tests"]` never descends into it. **No exclude entries
  need adding** — and adding them would be a `pyproject.toml` edit AC 21 forbids.
- The two committed generated artefacts this feature will carry — `src/companion/app/static/`
  (c2-2) and `ui/src/api/types.d.ts` (c2-3) — do not exist yet. Where a config anticipates them
  (e.g. `.prettierignore`), name the story key.
- Naming inside `ui/` follows frontend convention, not the Python one: `PascalCase.tsx` for
  components, `camelCase.ts` for modules. The project-context.md naming rules govern `src/`; they
  do not reach across the language boundary.

### References

- [epics-companion-app.md#Story-2.1](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  six AC blocks, including the R1 `changeOrigin` annotation and the `--platform` mypy annotation
  (lines 1193-1241)
- [epics-companion-app.md#Additional-Requirements](_bmad-output/planning-artifacts/epics-companion-app.md)
  — *Starter template / greenfield sub-tree*; *Stack floors* (lines 183-190, 312-319)
- [ARCHITECTURE-SPINE.md#AD-12](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md)
  — one generator, one store, no second data library (lines 272-290)
- [ARCHITECTURE-SPINE.md#AD-13](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md)
  — committed artifact, Node dev/CI-only, self-hosted font (lines 292-302)
- [ARCHITECTURE-SPINE.md#Stack](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md)
  — the version table and the TypeScript pin rationale (lines 362-388)
- [epic-c1-retro-2026-07-26.md#Rulings](_bmad-output/implementation-artifacts/epic-c1-retro-2026-07-26.md)
  — R1 (`changeOrigin`), R2 (`/docs` keep-decision), R4 (`COMPANION_PORT`) (lines 192-222)
- [epic-c1-retro-2026-07-26.md#Action-Items](_bmad-output/implementation-artifacts/epic-c1-retro-2026-07-26.md)
  — items 1, 2 and 3, and the six standing team agreements (lines 270-293)
- [deferred-work.md](_bmad-output/implementation-artifacts/deferred-work.md) — the c1-9 mypy-gate
  entry (line 977) and the C1 manual-testing residuals (line 988)
- [project-context.md](_bmad-output/project-context.md) — Python-side conventions; note they stop
  at the language boundary
- UX-DR46 / UX-DR47 —
  [epics-companion-app.md](_bmad-output/planning-artifacts/epics-companion-app.md) lines 603-609

## Rulings — Brad, 2026-07-26 (asked and answered before implementation began)

All five questions this story raised were settled at story-creation time. **Nothing here is open.**
They are recorded as rulings rather than deleted, so a later story can see what was declined.

**B1 — stylelint enforces the CSS rules; `npm run lint` runs both tools.** The epic AC's "when
eslint runs" is read as *the lint gate reports it*, and `npm run lint` is the gate. Governs AC 9 and
Decide-once #2 below. Rationale accepted as written: `@eslint/css@1.4.0` has no declaration-value rule, a
custom rule against an experimental CSS AST would become ours to maintain, and c2-4 needs four more
rules of exactly this shape. *Declined: a hand-written ESLint rule; deferring the whole CSS gate to
c2-4.*

**B2 — `openapi-typescript` is installed as a devDependency in this story.** The lock therefore
lands on `typescript@5.9.3` from the first commit, and c2-3 only wires the generation script instead
of downgrading TypeScript after two stories of code. Governs **AC 4** and the *Latest technical
information* table. *Declined: making c2-3 pay it; tightening the pin to `<6.0`, which would have
required amending the epic AC.*

**B3 — ESLint stays, pinned `^9`.** oxlint is declined for MVP: the epic AC names eslint,
`typescript-eslint`'s type-aware rules have no oxlint equivalent today, and ~40 downstream
C2/C4/C6/C7 stories inherit this choice. Governs **AC 5**, **AC 6** and Decide-once #1. The exit condition
is unchanged — lift the pin when `eslint-plugin-jsx-a11y` publishes an `^10` peer range. *Declined:
switching to oxlint; running both linters.*

**B4 — the frontend gates are CI-only; `.pre-commit-config.yaml` is not touched.** NFR-07's venue is
CI, and a `files: ^ui/`-scoped local hook stays available if the CI round trip later proves to be
the bottleneck. Governs Decide-once #4 and **AC 21**'s forbidden-file list.

**B5 — one frontend CI job on `node-version: 20`, no matrix.** The floor is the version nobody
develops on and therefore the one worth testing; current Node is covered incidentally by Brad's
local runs on v24.15.0. Governs **AC 15**. *Declined: a `[20, 24]` matrix mirroring the Python job;
pinning CI to 24.*

## Dev Agent Record

### Agent Model Used

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via the bmad-dev-story workflow.

### Debug Log References

**Task 0 — baseline at `50dddc3`, branch `feat/companion-c2`, working tree clean apart from this
story file + sprint-status.**

```
node --version -> v24.15.0     npm --version -> 11.12.1

uv run mypy src/                  -> Success: no issues found in 83 source files
uv run mypy src/ --platform linux -> Success: no issues found in 83 source files
uv run mypy src/ --platform win32 -> Success: no issues found in 83 source files
```

The first `pytest` run did **not** match the story's stated baseline:

```
FAILED tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field
  AssertionError: assert 'Control' is None
===== 1 failed, 1683 passed, 1 skipped, 45 deselected in 83.30s =====
```

Investigated before proceeding rather than assuming. The test passed 5/5 in isolation and an
immediate full-suite re-run at the same commit gave the story's exact figure:

```
=============== 1684 passed, 1 skipped, 45 deselected in 51.02s ===============
```

Diagnosis: `list_decks()` orders newest-first on `created_at`, the three fixture decks can be
created within the same microsecond, and there is no secondary tie-breaker — so two of them can
come back in either order under load. Pre-existing at the baseline commit and unrelated to this
story, which adds no Python. Not patched (AC 21 forbids touching `tests/`); homed in
`deferred-work.md`.

**AC 1 / AC 4 — lockfile verification (the story's own command, run against the real lock).**

```
lockfileVersion: 3
platform-binding pkg count: 20
linux bindings include: @rolldown/binding-linux-x64-gnu, lightningcss-linux-x64-gnu (+10 more)

typescript              => 5.9.3      eslint                  => 9.39.5
eslint-plugin-jsx-a11y  => 6.10.2     typescript-eslint       => 8.65.0
vite                    => 8.1.5      react                   => 19.2.8
stylelint               => 17.14.1    vitest                  => 4.1.10
openapi-typescript      => 7.13.0     zustand                 => 5.0.14
@testing-library/jest-dom => 6.9.1    @testing-library/react  => 16.3.2
```

`3 20` and `typescript@5.9.3` are exactly what the story predicted, confirming Ruling B2's
mechanism (`openapi-typescript`'s `typescript: ^5.x` peer is what lands the resolution on 5.9.x).

**AC 17 — the deliberate `singleton.py` break, the retro's literal success criterion.**
`msvcrt.locking(fd, msvcrt.LK_NBLCK, _LOCK_BYTES)` → `msvcrt.locking(fd, msvcrt.LK_NBLCK)` inside
the `if sys.platform == "win32":` branch:

```
$ uv run mypy src/ --platform win32
src\companion\app\singleton.py:130: error: Too few arguments for "locking"  [call-arg]
Found 1 error in 1 file (checked 83 source files)          exit=1

$ uv run mypy src/ --platform linux
Success: no issues found in 83 source files                exit=0
```

The linux run stays green on the identical broken code — which is precisely why
`--platform linux` on an ubuntu runner would have been a no-op gate. Break reverted;
`git status --porcelain -- src/` empty afterwards and `--platform win32` back to
`Success: no issues found in 83 source files`.

**AC 11 — the emptied-component mutation.** With `App.tsx` reduced to `return null`:

```
FAIL |dom| src/App.test.tsx > App > renders the product name as the page heading
FAIL |dom| src/App.test.tsx > App > renders inside a main landmark
  TestingLibraryElementError: Unable to find an accessible element with the role "main"
 Test Files  1 failed (1)          Tests  2 failed (2)          exit=1
```

Restored; 32/32 green.

**AC 10 — the line-ending round trip.** Every tracked `ui/` file was deleted from the working tree
and restored with `git restore -- ui`, on a machine where `git config core.autocrlf` is `true`:

```
$ git ls-files --eol -- ui
i/lf    w/lf    attr/text=auto eol=lf   ui/src/App.tsx
i/lf    w/lf    attr/text=auto eol=lf   ui/package.json
...  (30 files; zero `w/crlf`)
```

Then, from that freshly-checked-out tree, a clean `npm ci` followed by all four gates and the build:

```
npm ci            exit=0
npm run format:check  -> All matched files use Prettier code style!   exit=0
npm run lint          -> eslint . && stylelint "src/**/*.css"         exit=0
npm run typecheck     -> tsc -b                                       exit=0
npm test              -> Test Files 5 passed (5)  Tests 32 passed (32) exit=0
npm run build         -> ✓ built in 96ms                              exit=0
```

Non-vacuity check on stylelint itself (gotcha #6 — it exits 0 on an empty glob):
`npx stylelint "src/**/*.css" --formatter verbose` → `2 sources checked … 0 problems found`,
naming `src/App.css` and `src/index.css`. The glob matches real files.

**AC 21 — scope proof.**

```
$ git status --porcelain -- pyproject.toml uv.lock .pre-commit-config.yaml .gitignore \
    src/ tests/ plugin/ scripts/ README.md CONTRIBUTING.md .mcp.json
(empty)
```

`git ls-files ui/dist ui/node_modules` is also empty — neither is tracked. The pre-commit run on
the scaffold commit reported `no files to check` for ruff, mypy **and** `rebuild plugin/`,
confirming no `src/` file was touched and no plugin mirror was dragged in.

**AC 22 — Python gates after the change.**

```
uv run ruff check .          -> All checks passed!
uv run ruff format --check . -> 281 files already formatted
uv run pytest -m "not integration" -> 1684 passed, 1 skipped, 45 deselected in 47.39s
```

**Task 10 — live checks, two real processes.** Default port:

```
backend  : [planeswalker] companion running at http://127.0.0.1:8765
           Companion instance f1a0f4e6-5980-4d29-8241-b6b82ac0573b started
vite     : VITE v8.1.5 ready — Local: http://localhost:5173/

GET http://127.0.0.1:8765/health  -> 200 {"status":"ok","instance_id":"f1a0f4e6-…"}
GET http://localhost:5173/health  -> 200 {"status":"ok","instance_id":"f1a0f4e6-…"}   <-- proxied
```

Non-default port, `$env:COMPANION_PORT = "9125"` exported before launching *both* processes:

```
backend  : [planeswalker] companion running at http://127.0.0.1:9125
           Published discovery file … for port 9125
           Companion instance 9be64dcd-fc62-4b69-bf46-4554fca1bcca started

GET http://127.0.0.1:9125/health  -> 200 {"status":"ok","instance_id":"9be64dcd-…"}
GET http://localhost:5173/health  -> 200 {"status":"ok","instance_id":"9be64dcd-…"}   <-- proxied
GET http://127.0.0.1:8765/health  -> connection refused (nothing there any more)
```

Both proxied calls returned `200` with the real `instance_id`, never `400 invalid_request`. R1 is
closed end to end.

### Completion Notes List

**AC 16 — the epic text and the retro success criterion disagree, and I did not silently satisfy
the letter of the epic.** The epic asks for `mypy src/ --platform linux` alongside `mypy src/`.
CI is `ubuntu-latest`, where the bare run **already is** the linux run, so that addition would be
a pure no-op and the retro's stated success criterion — "a deliberately Windows-broken
`singleton.py` branch fails CI" — would still not hold. **`--platform win32` shipped instead**,
and AC 17's proof above shows why: on the identical broken code, win32 goes red and linux stays
green. The epic's wording was written from a Windows machine, where the bare run is the win32 run;
the intent transfers, the literal flag does not. Flagged here the way c1-9 flagged its own
internally-impossible AC pair.

**A THIRD load-bearing pin exists that no planning document predicted:
`@testing-library/jest-dom` at `~6.9.1`.** The story named two (`typescript`, `eslint`) and
predicted the ERESOLVE for one of them. This one surfaced at install time as a deprecation warning:
both `latest` (7.0.0) and 6.10.0 declare `engines.node: ">=22"`, which is **above this project's
declared `>=20.19.0` floor and above CI's `node-version: 20`**; 6.10.0 is additionally deprecated
upstream as an incorrect minor release. 6.9.1 is the last release declaring `>=14`.

It is worth separating this from the other two pins because it fails *differently and more
quietly*: `npm` treats `engines` as advisory, so an unpinned bump installs cleanly on a dev machine
running Node 24 and breaks only later, on the Node 20 CI job. There is no ERESOLVE to catch it. The
reason and the exit condition (lifting it is a **Node-floor decision**, AC 2 / AC 15, not a
dependency bump) are recorded in `ui/package.json` beside the dependency, per Decide-once #1's
principle that the next person to run `npm update` reads `package.json` and nothing else.
**The Spine's stack table now lags reality by two entries** — `eslint ^9` and this one.

**`Node >= 20` → `>= 20.19.0` copy discrepancy, for c8-4.** The measured floor is higher than the
epic/PRD copy: `vite@8.1.5` declares `engines: ^20.19.0 || >=22.12.0` and `stylelint@17` declares
`>=20.19.0`, so a literal Node 20.0 cannot build `ui/`. `>=20.19.0` shipped in
`ui/package.json`; CI's `node-version: 20` resolves to the latest 20.x, which satisfies it. This
is a copy fix, not a scope change. Homed in `deferred-work.md`.

**`"strict": true` was added to both tsconfigs, and it is not in the template.** `create-vite@9.1.1`'s
`react-ts` template ships **no** `strict` flag in either `tsconfig.app.json` or `tsconfig.node.json`.
NFR-07 asks for a frontend gate "equivalent" to the Python side's, and the Python side is
`mypy --strict`; a non-strict `tsc` is not an equivalent gate, and ~40 downstream stories would
have been written under it. Recorded as a deviation from the template with the reason inline in
both files. It cost nothing — `tsc -b` was green on the first run with `strict` already on.

**A fifth landmine, of the same family as the story's four: `eslint-plugin-react-hooks@7` exports
both a flat config and a legacy eslintrc config under near-identical names.** The story's gotcha #4
warned about `jsx-a11y`'s flat-config export; the actual casualty was react-hooks.
`reactHooks.configs['recommended-latest']` is the **legacy** shape (`plugins: ["react-hooks"]`, an
array of strings) and the flat one is `reactHooks.configs.flat['recommended-latest']`. Passing the
wrong one aborts the entire ESLint run with "A config object has a 'plugins' key defined as an
array of strings" — it does not degrade quietly, which is the one mercy. Noted inline in
`eslint.config.js` so the next person editing it does not re-derive it. (For the record,
`eslint-plugin-jsx-a11y@6.10.2` *does* expose `flatConfigs`, contrary to gotcha #4 — but the two
rules were still enabled by name, per AC 8.)

**vitest is configured as two projects (`node` + `dom`) rather than one.** Not decoration: without
vitest globals enabled, `@testing-library/react` does **not** auto-register its `afterEach(cleanup)`,
so a second `render()` in the same file finds two copies of the component and every `getByRole`
throws "found multiple elements". That surfaced as a real failure here. The alternatives were
per-file boilerplate in every future component test, or enabling globals across the whole suite.
The project split puts jsdom + jest-dom matchers + cleanup behind one `setupFiles` entry that only
the `dom` project loads, so a new component test in c2-6…c2-10 needs no setup at all, and the
node-side gate suites keep a clean node environment.

**Gate-proving fixtures live in `ui/tests/fixtures/` and are deliberately excluded from
`npm run lint`.** They are inputs to `tests/lint-gates.test.ts`, which drives the ESLint and
stylelint **Node APIs** directly (ESLint with `ignore: false`) so the violation and the acceptance
come out of one invocation against the shipped config. `tests/fixtures/a11y` is added to
`tsconfig.app.json`'s `include` because ESLint's `projectService` errors on any `.tsx` that belongs
to no tsconfig — noted in both the tsconfig and `ui/README.md`, since it is the rule anyone adding
a source directory will trip over.

**AC 3's ban test is non-vacuous by construction.** `tests/package-contract.test.ts` asserts all
nine banned libraries are absent, that `zustand` **is** present (so a typo in the package-reading
code cannot make the bans pass by finding nothing), that `openapi-typescript` is in
`devDependencies` and not `dependencies`, and that `engines.node` is the honest floor. One file
reads `package.json`; four facts come out.

**`npm audit` reports 8 high-severity advisories and no gate looks at it.** All transitive and
dev-only — `brace-expansion`/`minimatch` via `eslint` and `eslint-plugin-jsx-a11y`, `js-yaml` via
`@redocly/openapi-core` (a dependency of `openapi-typescript`). **Deliberately not fixed here:**
`npm audit fix --force` resolves it by installing `eslint-plugin-jsx-a11y@6.4.1`, a major-version
downgrade of the plugin that carries the entire UX-DR47 gate — trading a working accessibility gate
for a DoS advisory in a linter is the wrong trade. Nothing here ships (Node is dev/CI-only, AD-13).
Homed in `deferred-work.md` against c8-4/c8-5 with the upstream exit condition, which is the same
one as the `eslint ^9` pin.

**AC 19 — every forward-dated comment carries a story key.** `/ws` → **c5-6** (in `devProxy.ts`,
and asserted absent by a test); `outDir` staying at `ui/dist` → **c2-2** (in `vite.config.ts`);
`src/api/types.d.ts` → **c2-3** (in `.prettierignore` and beside the `openapi-typescript` entry in
`package.json`); the hex/`rgba()`/`box-shadow`/`border-radius` CSS bans → **c2-4** (in `index.css`);
the `Origin`-vs-`Host` distinction → **c5-3** (in `ui/README.md`); the real shell, primitives and
state panel → **c2-6 / c2-7 / c2-9** (in `App.tsx`).

**Observation recorded rather than acted on (AC 21).** `singleton.py`'s lines 56-59 comment still
says "`mypy src/` and `mypy src/ --platform linux` are therefore mandatory". That sentence is now
backed by a CI step, but the step is `--platform win32` and the comment does not name it. Editing
it would be a `src/` edit that AC 21 forbids and would drag the `plugin/` mirror into a
frontend-scaffold commit, so it is left alone and recorded here for a later story.

**Incidental close: the C1 `COMPANION_PORT` residual** (`deferred-work.md`, C1 retro manual-testing
section). Task 10's second run exported `COMPANION_PORT=9125` in a real shell and the companion
served on 9125 and published discovery for it — so a real environment variable under the renamed
key does reach `resolve_preferred_port`. c8-4 may now describe the variable as hand-verified. The
other half of that checklist block (`--port` beating the env var) was still not hand-run and the
entry says so.

### File List

**New — the entire `ui/` sub-tree:**

- `ui/.gitattributes`
- `ui/.gitignore`
- `ui/.prettierignore`
- `ui/.prettierrc`
- `ui/.stylelintrc.json`
- `ui/README.md`
- `ui/config/devProxy.ts`
- `ui/eslint.config.js`
- `ui/index.html`
- `ui/package-lock.json`
- `ui/package.json`
- `ui/public/favicon.svg`
- `ui/src/App.css`
- `ui/src/App.test.tsx`
- `ui/src/App.tsx`
- `ui/src/index.css`
- `ui/src/main.tsx`
- `ui/src/test-setup.ts`
- `ui/tests/devProxy.test.ts`
- `ui/tests/devProxyRoundTrip.test.ts`
- `ui/tests/fixtures/a11y/clean.tsx`
- `ui/tests/fixtures/a11y/violation.tsx`
- `ui/tests/fixtures/css/clean.css`
- `ui/tests/fixtures/css/violation.css`
- `ui/tests/lint-gates.test.ts`
- `ui/tests/package-contract.test.ts`
- `ui/tsconfig.app.json`
- `ui/tsconfig.json`
- `ui/tsconfig.node.json`
- `ui/vite.config.ts`

**Modified:**

- `.github/workflows/ci.yml` — new `frontend` job; `mypy src/ --platform win32` on `quality`;
  header comment extended (the npm registry is the one network dependency)
- `_bmad-output/implementation-artifacts/deferred-work.md` — c1-9 mypy-gate entry closed in place;
  C1 `COMPANION_PORT` residual closed in place; four new c2-1 entries
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — story status
- `_bmad-output/implementation-artifacts/c2-1-…md` — this file

**Deleted (from the `create-vite` scaffold, before first commit):** `ui/.oxlintrc.json`,
`ui/public/icons.svg`, `ui/src/assets/` (`hero.png`, `react.svg`, `vite.svg`).

**Touched and reverted (AC 17 proof):** `src/companion/app/singleton.py` — byte-identical to
baseline in the shipped commit.

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-07-26 | Story created — comprehensive context analysis; four measured landmines (eslint 10 ERESOLVE, oxlint template default, prettier/CRLF, `@eslint/css` rule gap), R1 and retro action item 3 folded in | Amelia (create-story) |
| 2026-07-26 | All five open questions asked and answered before implementation — rulings B1–B5 recorded; B2 (`openapi-typescript` installed here) folded into AC 3, AC 4, Task 1, Task 2 and the version table; B5 into AC 15. **No open questions remain.** | Brad + Amelia |
| 2026-07-26 | Implemented. `ui/` scaffolded and re-toolchained (oxlint out, eslint + stylelint + prettier + vitest in); lock verified at `3 20` / `typescript@5.9.3` / `eslint@9.39.5`; CI gains a `frontend` job and `mypy --platform win32`; c1-9 mypy-gate entry and the C1 `COMPANION_PORT` residual closed in `deferred-work.md`. All 22 ACs met; 32 frontend tests, Python suite at baseline 1,684. **Three deviations recorded, none silent:** AC 16 ships `--platform win32` not `linux` (the epic's letter would be a no-op on ubuntu — the retro's success criterion wins); a third load-bearing pin `@testing-library/jest-dom ~6.9.1` was required (newer releases need Node ≥ 22); `"strict": true` added to both tsconfigs, which the template omits. | Amelia (dev-story) |
