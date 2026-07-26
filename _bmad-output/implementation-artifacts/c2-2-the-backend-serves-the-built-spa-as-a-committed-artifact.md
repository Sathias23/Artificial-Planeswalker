---
baseline_commit: 9d47b24
epic: c2
story: c2-2
work_branch: feat/companion-c2
story_branch: feat/companion-c2-2-serve-spa
---

# Story C2.2: The backend serves the built SPA as a committed artifact

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As Brad installing the plugin,
I want the browser UI to arrive already built inside the Python package,
so that opening the URL shows the app with no Node toolchain anywhere on my machine.

**What this story really is.** It joins the two halves of the feature that have never met: c2-1's
`ui/` toolchain and C1's FastAPI backend. After this story the build output stops living in
`ui/dist` and starts living **inside the Python package** at `src/companion/app/static/`, committed,
mirrored into `plugin/`, and served at `/`. That is AD-13 in full, and it is what makes SC-4
("a fresh install launches with a single `uv` command and no build step") true rather than aspirational.

It is a small diff with an unusually large blast radius, because it makes a **generated tree a
tracked part of `src/`** — which means it touches the drift-check machinery, the plugin mirror, the
pre-commit hook, the wheel contents and the route table all at once.

**Five things are already known to break, all five measured on this machine at the baseline commit
(`9d47b24`, vite 8.1.5 / starlette 0.48.0 / fastapi 0.140.0) — do not rediscover them:**

1. **Vite will not empty an `outDir` outside the project root, and only *warns*.** From the
   installed `vite/dist/node/chunks/node.js`:

   ```js
   if (!normalizePath(outDir).startsWith(withTrailingSlash(root)))
     warn(`outDir ${outDir} is not inside project root and will not be emptied.
   Use --emptyOutDir to override.`)
   ```

   Without an explicit `emptyOutDir: true`, every rebuild **adds** hashed assets and never removes
   the old ones. The drift check would stay green while `static/` grew a graveyard of dead bundles
   that all ship to users. `emptyOutDir: true` is load-bearing, not tidiness.

2. **…and `emptyOutDir` deletes *everything* in the directory except `.git`.** Same file, the
   `emptyDir(outDir, [...])` call site passes exactly one skip entry: `".git"`. So **no hand-written
   file can live inside `src/companion/app/static/`** — not a `.gitattributes`, not a `README`, not
   an `__init__.py`. The first rebuild eats it. Anything that needs to be said about this directory
   must be said *outside* it (see AC 3 and AC 6).

3. **`git diff --exit-code` cannot detect a stale bundle.** The epic AC says to use it. Vite emits
   content-hashed filenames, so a source change produces a **new, untracked** file plus a deletion —
   and `git diff` does not see untracked files. The existing `plugin/` drift check in
   [ci.yml](.github/workflows/ci.yml) already knows this and uses `git status --porcelain -- plugin/`.
   The epic's own words are "mirroring the existing `plugin/` drift-check pattern"; the *pattern* is
   `git status --porcelain`, and the literal flag in the AC text is wrong. AC 12 rules on it.

4. **Starlette serves an unknown extension as `text/plain`, and `.woff2` is unknown here.** From
   `starlette/responses.py`: `media_type = guess_type(...)[0] or "text/plain"`. Measured on this
   machine:

   ```
   .js  -> text/javascript      .css  -> text/css       .svg  -> image/svg+xml
   .woff2 -> None  (=> text/plain)      .map -> None  (=> text/plain)
   ```

   `.js` resolves correctly *today on this machine*, but `mimetypes` consults the **Windows
   registry**, which any installed application can change — and a `.js` served as `text/plain` makes
   a module script refuse to execute and the page render blank, with a 200 in the network tab.
   c2-5 self-hosts Space Grotesk into this same directory, where the `.woff2` gap is already real.
   Register the types explicitly (AC 8).

5. **A mount at `/` swallows every route registered after it.** Starlette matches routes in list
   order and `Mount("/")` matches every path. So `install_spa(app)` must be the **last** thing
   `build_app()` does, and c3-1 / c5-2 / c5-5 must add their routers *above* that line. A convention
   is not enough here — the failure is silent (`GET /api/decks` quietly returns `index.html` with a
   200), which is exactly the failure class c2-1's round-2 review caught in the dev proxy. AC 10
   makes it a guard test.

**What this story does not do.** No visual work: `App.tsx` is still c2-1's placeholder and c2-6
replaces it. No fonts (c2-5), no generated types (c2-3), no `base`-path or sub-path serving.

## Acceptance Criteria

Epic-derived ACs are marked **[epic]**. The rest are requirements the epic's five blocks imply but
do not state; each says why it exists. Nothing here is optional — an AC the epic did not write down
is still an AC (standing agreement: a story must leave the system working end to end).

### The bundle — build side

1. **[epic] `npm run build` in `ui/` emits the bundle to `src/companion/app/static/`, and that
   directory is committed.** `vite.config.ts` sets `build.outDir` to that path, resolved from
   `import.meta.url` with **`fileURLToPath`, never `new URL(...).pathname`** — the latter yields
   `C:\C:\…` on Windows and was patched out of `devProxyRoundTrip.test.ts` for exactly that reason
   in c2-1's round-1 review. The path is computed **once**, in one place.

2. **`emptyOutDir: true` is set, and stale-file removal is proven.** See landmine #1: outside the
   project root, Vite *skips* emptying and only warns. Prove it rather than reading the config:
   drop a junk file into `src/companion/app/static/`, run `npm run build`, and show it is gone.
   Paste the before/after. (This same proof demonstrates landmine #2 — which is why nothing
   hand-written may live in that directory.)

3. **A vitest config assertion pins the resolved `outDir` to the expected absolute path.**
   `emptyOutDir: true` on a mistyped path is a recursive delete of a real source directory. One
   assertion in the `node` project — the same shape as c2-1's `devProxy.test.ts` — turns a typo
   into a red test instead of a data-loss incident. Assert the resolved value ends with
   `src/companion/app/static` **and** that `emptyOutDir === true`, so neither half can regress alone.

4. **Nothing in the emitted tree is gitignored, and the tree is really tracked.** The root
   [.gitignore](.gitignore) ignores an **unanchored `dist/`, `build/` and `lib/`** — none of which
   match today's output, but a future asset directory could. Verify both directions, and paste both:

   ```
   git check-ignore -v $(git ls-files -o --exclude-standard src/companion/app/static/)   # must find nothing
   git ls-files src/companion/app/static/ | wc -l                                        # must be > 0
   ```

   The second half is the non-vacuity pair: "no ignored files" is trivially true of an empty tree.

5. **A root `.gitattributes` is created containing exactly one scoped line:**
   `src/companion/app/static/** -text`. Reasons, all three needed:
   - the drift check compares committed bytes against rebuilt bytes; `-text` removes
     `core.autocrlf` (which is `true` on Brad's machine) from the equation by declaration rather
     than by an argument about when git normalises;
   - it **cannot** live inside `static/` — landmine #2 deletes it on the next build;
   - it must **not** be `text eol=lf`: c2-5 puts `.woff2` fonts in this same tree, and an eol
     attribute on a binary font corrupts it.

   **Do not add `* text=auto` to this file.** c2-1's AC 10 rejected a root `.gitattributes` because
   a repo-wide pattern would renormalise every tracked file; a single scoped path pattern does not.
   Confirm that with `git ls-files --eol -- src/ | grep -c 'w/crlf'` unchanged before and after.

6. **The built `index.html` says it is generated.** Add an HTML comment to **`ui/index.html`**
   (the source) naming `ui/` as the place to edit and this directory as generated output; Vite
   copies it through to `src/companion/app/static/index.html`. This is the only way to leave a
   notice in a directory that is wiped on every build (landmine #2), and it is what a person who
   opens the built file to "just fix one string" will actually read. Enforcement is AC 12 + AC 13;
   this is discoverability.

### Serving — backend side

7. **[epic] `GET /` serves the SPA index from `src/companion/app/static/`, and client-side routes
   fall back to the index rather than 404ing.** A path with no file extension, under no registered
   route prefix (e.g. `/decks/42`), returns **200** with the index document. Reuse
   `starlette.staticfiles.StaticFiles` — do not hand-roll file serving; ETag, `Last-Modified`,
   conditional requests and range support all come free and none of them should be rewritten.

8. **Content types are asserted, not assumed.** A test asserts the served `Content-Type` for the
   emitted `.js` and `.css` assets (`text/javascript`, `text/css`) and for `index.html`
   (`text/html`). The serving module registers its types explicitly at import
   (`mimetypes.add_type(...)` for at least `.js`, `.mjs`, `.css`, `.svg`, `.json`, and `.woff2` →
   `font/woff2` with a **c2-5** key on the comment), so a Windows registry entry cannot downgrade a
   module script to `text/plain` and blank the page behind a 200 (landmine #4).

9. **The typed error contract survives the fallback, and this is where the story is most likely to
   go wrong.** From one test module, all four:
   - `GET /api/anything-unknown` → **`404 {"reason": "invalid_request"}`**, `application/json` —
     *not* the index. (`/api` has no routes until c3-1; the reservation must hold anyway.)
   - `GET /assets/does-not-exist.js` → typed JSON 404, not the index. An asset miss answering with
     HTML and a 200 is the "health probe gets HTML that claims success" failure c2-1's round-2
     review caught in the proxy.
   - `POST /decks/42` (a path the GET fallback *would* serve) → typed JSON, never the index.
   - `GET /health` still returns `{"status": "ok", "instance_id": …}`, and `/docs` +
     `/openapi.json` still answer (retro ruling R2 keeps them enabled) — the regression pair.
   - `app.openapi()` gains **no** new path entry from the mount. c2-3 generates the UI's types from
     that schema and drift-checks them in CI; a mount that leaked a path into `paths` would show up
     two stories later as unexplained generated-file churn.

   No new reason token is minted: `StaticFiles` raises Starlette's `HTTPException(404)`, which
   [errors.py](src/companion/app/errors.py)'s `http_exception_handler` already types as
   `invalid_request` at the framework's own status. Verify that end to end rather than assuming it.

10. **The mount is last in `app.routes`, and a guard test says so with instructions.** A test
    asserts the SPA mount is the final entry, and its failure message tells the next author the
    rule: *register routers above `install_spa(app)` in `build_app()`*. Pair it non-vacuously —
    the same test (or its sibling) proves a registered route still wins over the mount, by asking
    for `/health` and getting JSON. Comment the call site in `build_app()` too; c3-1, c5-2 and
    c5-5 all add routes and will meet this line first (AC 17 keys).

11. **Construction stays inert (AD-10) and a missing bundle fails legibly.** `build_app()` must
    still create no directory, bind no port, open no database and resolve no data path — the
    existing `test_app.py::TestConstructionIsInert` tests must pass **unchanged**. A `Path.is_dir()`
    stat of a packaged directory is not a side effect and is permitted; a `mkdir` is not. If
    `static/` is missing or has no `index.html`, construction raises with a message naming the fix
    (`cd ui && npm run build`) instead of a bare `RuntimeError: Directory 'static' does not exist`
    or a 404 at request time. Test both: the happy path, and the missing-directory path against a
    temporary location.

12. **[epic] CI rebuilds the bundle and fails on drift — using `git status --porcelain`, not
    `git diff --exit-code`.** The step attaches to the `frontend` job's existing `Build` step
    (added by c2-1's round-2 ruling) and mirrors the `plugin/` check's shape exactly: `::error::`
    annotation naming the fix, then `git status --porcelain` and `git --no-pager diff` for the log.

    > **Deliberate deviation from the epic's letter, flagged not silently taken** (the c1-9 / c2-1
    > precedent). `git diff --exit-code` misses untracked files, and a content-hash rename produces
    > exactly that: one deletion (seen) plus one untracked addition (unseen). The epic's own
    > sentence says to mirror the `plugin/` pattern, and that pattern is `git status --porcelain`.
    > Record it in the Completion Notes.

    Note the job has `defaults.run.working-directory: ui`, so the drift step needs its own
    `working-directory: .` (or repo-root-relative paths) — a `git status` run from `ui/` with a
    `src/…` pathspec silently matches nothing and passes vacuously.

13. **The drift check is proven to have teeth.** Edit a `ui/src` file, do **not** rebuild, run the
    check command locally, and paste the red output; then rebuild and paste it green. Same
    discipline as c2-1's AC 17 deliberate mypy break.

### The plugin mirror and the wheel

14. **[epic] `plugin/` receives the mirrored bundle through the existing machinery, and a check
    asserts the copy is real.** `scripts/build_plugin.py` already `copytree`s the whole of `src/`,
    so the mirror is automatic — but "automatic" is how a UI-less plugin ships unnoticed. Add a
    sentinel in the same shape as the existing `src/viewer/__init__.py` check: after the copy,
    abort with a logged error if `server/src/companion/app/static/index.html` is missing. The
    committed `plugin/` tree is rebuilt and committed in this story (the `build-plugin-sync`
    pre-commit hook fires on any `^src/` change, so this happens whether or not you ask for it —
    expect the mirror in your diff and do not fight it).

15. **[epic] Both copies are treated as generated artifacts — neither is hand-edited.** Two CI
    checks already cover it once AC 12 lands (the SPA drift check for `src/`, the plugin drift
    check for `plugin/`). Add one cheap pytest test that the mirrored `index.html` is
    **byte-identical** to the source-of-truth one, so a `plugin/` committed without a rebuild is
    caught locally rather than only on CI.

16. **The bundle is inside the built wheel.** hatchling's `packages = ["src"]` includes non-Python
    files, and nothing gitignores this path today (AC 4) — but the failure mode if that ever
    changes is an installed package that serves nothing, which is precisely SC-4 inverted. Prove
    it once, and paste it:

    ```
    uv build
    python -m zipfile -l dist/artificial_planeswalker-*.whl | grep companion/app/static | head
    ```

    `dist/` is gitignored, so this leaves no trace. **`pyproject.toml` is not edited** — if the
    bundle needs a packaging directive to be included, that is a finding to record and raise, not a
    quiet edit (AD-13's "Node is never required at install" is proved by `pyproject.toml` staying
    ignorant of `ui/`).

### Fresh install, docs, and boundaries

17. **[epic] A fresh install with no Node present serves and renders (SC-4).** A test cannot close
    this. Do it by hand: `git worktree add` (or `git clone`) the branch to a temporary directory —
    which has **no `node_modules`** — then from there run `uv run artificial-planeswalker companion`
    and open the printed URL in a browser. Confirm the page renders (c2-1's placeholder `App.tsx` is
    the expected content), and that the network tab shows the hashed asset with the right
    `Content-Type`. Paste the URL, the status codes and what you saw. Remove the worktree
    afterwards.

18. **Every forward-dated comment carries a story key** (standing agreement, C1 retro item 1).
    Concretely: the `.woff2` mimetype registration → **c2-5**; the "register routers above this
    line" note → **c3-1** (first router to arrive); `ui/src/api/types.d.ts` still absent → **c2-3**;
    the plugin-parity acceptance → **c8-5**; the real shell replacing `App.tsx` → **c2-6**.

19. **`ui/README.md` states where the build output goes and that it is committed** — one paragraph
    in the existing dev-loop section: `npm run build` writes into `src/companion/app/static/`, that
    tree is committed and generated, never hand-edit it, and CI fails if it is stale. Do not also
    write it in `CONTRIBUTING.md`; user-facing release documentation is **c8-4**'s.

20. **Scope proof, by command, pasted** (nine for nine in C1, again in c2-1):

    ```
    git status --porcelain -- pyproject.toml uv.lock .pre-commit-config.yaml .gitignore \
      README.md CONTRIBUTING.md .mcp.json
    ```

    must be **empty**. This story legitimately touches `ui/`, `src/companion/app/`, `tests/`,
    `scripts/build_plugin.py`, `.github/workflows/ci.yml`, `plugin/` (generated) and a new root
    `.gitattributes` — and nothing else.

    **No new dependency is added on either side.** Everything needed already ships: `StaticFiles`
    and `FileResponse` come with Starlette (a FastAPI dependency), and Vite already writes the
    bundle. If you find yourself reaching for `aiofiles`, `whitenoise`, `starlette-spa` or an npm
    copy plugin, stop — that is a signal the approach has drifted, not that a package is missing.
    `pyproject.toml`, `uv.lock` and `ui/package-lock.json` all stay out of the diff.

21. **Both suites green, at or above baseline.** Python: `uv run pytest -m "not integration"` at
    **1,684 passed / 1 skipped / 45 deselected** plus this story's new tests — confirm the baseline
    yourself in Task 0 (standing agreement) before you start. `uv run ruff check .`,
    `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32` all
    green. Frontend: all five gates (`lint`, `format:check`, `typecheck`, `test`, `build`) green,
    suite at **55 tests** plus this story's additions.

## Tasks / Subtasks

- [ ] **Task 0 — Baseline verification** (standing agreement; before touching anything)
  - [ ] `git rev-parse --short HEAD` = `9d47b24`, `git status --porcelain` empty, branch cut from
        `feat/companion-c2` as `feat/companion-c2-2-serve-spa`
  - [ ] `uv run pytest -m "not integration"` → record exact counts (expected 1,684 / 1 / 45; if it
        differs, investigate before proceeding — c2-1's Task 0 caught a real order-flake this way,
        already homed in `deferred-work.md`)
  - [ ] `cd ui && npm ci && npm test` → record the count (expected 55)
  - [ ] `git check-ignore -v src/companion/app/static/index.html` → no match (verified at story
        creation; re-confirm, it is the premise of AC 4)

- [ ] **Task 1 — Redirect the build output** (AC 1, 2, 3)
  - [ ] `vite.config.ts`: `build.outDir` via `fileURLToPath(new URL('../src/companion/app/static',
        import.meta.url))`, `emptyOutDir: true`, with a comment naming landmines #1 and #2
  - [ ] Delete the now-stale c2-2 forward-reference comment in `vite.config.ts` (c2-1 left one
        saying "c2-2 owns redirecting `outDir`") — this is that story
  - [ ] `npm run build`, then the junk-file emptying proof; paste both
  - [ ] Config-assertion test (`ui/tests/`, `node` project) for the resolved path and `emptyOutDir`

- [ ] **Task 2 — Commit the bundle, and make its bytes deterministic** (AC 4, 5, 6)
  - [ ] Root `.gitattributes` with the single scoped `-text` line (nowhere else — landmine #2)
  - [ ] `git add src/companion/app/static`; run the two AC 4 commands and paste both
  - [ ] Generated-file comment in `ui/index.html`; rebuild; confirm it survives into the output
  - [ ] Confirm no repo-wide renormalisation: `git ls-files --eol -- src/ | grep -c 'w/crlf'`
        unchanged before/after

- [ ] **Task 3 — Serve it** (AC 7, 8, 9, 10, 11)
  - [ ] New module (suggested `src/companion/app/spa.py`) exporting `STATIC_DIR` and
        `install_spa(app)`, following the `install_security` / `install_error_handling` naming
  - [ ] `StaticFiles` subclass whose 404 falls back to `index.html` for extension-less GET/HEAD
        paths outside the reserved prefixes; explicit `mimetypes.add_type` registrations
  - [ ] Call `install_spa(app)` **last** in `build_app()`, with the ordering comment
  - [ ] Tests: index, asset + content types, client-route fallback, the four AC 9 contract cases,
        the mount-order guard with its instructive message, inertness unchanged, missing-bundle
        error

- [ ] **Task 4 — CI drift check** (AC 12, 13)
  - [ ] New step after `Build` in the `frontend` job; `working-directory: .`; plugin-check shape
  - [ ] Local teeth proof (stale → red, rebuilt → green); paste both

- [ ] **Task 5 — Plugin mirror and the wheel** (AC 14, 15, 16)
  - [ ] `scripts/build_plugin.py` sentinel for the mirrored `index.html`, in the `src/viewer` shape
  - [ ] `uv run python -m scripts.build_plugin`; commit the regenerated `plugin/` tree
  - [ ] pytest byte-identity test for the mirrored `index.html`
  - [ ] `uv build` + wheel listing; paste; confirm `pyproject.toml` untouched

- [ ] **Task 6 — Records and gates** (AC 18, 19, 20, 21)
  - [ ] Forward-dated comments keyed; `ui/README.md` paragraph
  - [ ] Scope-boundary proof pasted
  - [ ] Both suites + all four Python gates + all five frontend gates green

- [ ] **Task 7 — Live checks a test cannot close** (AC 17)
  - [ ] Temporary worktree/clone with no `node_modules`; `uv run artificial-planeswalker companion`;
        browser open; paste what you saw
  - [ ] While there: confirm `/health` still answers JSON and `/docs` still renders, from the
        **same** running instance (R2's keep-decision, now behind a catch-all mount)

## Dev Notes

### Decide-once rulings (c2-3 … c2-10 and the C4/C6/C7 frontend stories inherit these)

**#1 — the SPA fallback is decided by the request, not by a wildcard.** The rule, in one sentence:
*fall back to `index.html` only for a `GET`/`HEAD` whose path has no file extension and whose first
segment is not a registered route prefix; everything else keeps the typed error contract.* The
three parts each buy something:

- **method** — a `POST` to a client route is never a document request; letting it 200 with HTML
  would make a mistyped API call look like a success.
- **no file extension** — `/assets/index-abc123.js` that does not exist is a *broken deployment*,
  and it must say 404 loudly rather than return an HTML document with a 200 that the browser then
  fails to parse as JavaScript.
- **not a registered prefix** — `/api/deckz` (a typo, no extension) must not answer with the index.
  Derive the reserved set from `app.routes` at install time rather than hand-typing it, so c3-1's
  `/api/decks` reserves `api` automatically; seed it with `api` so the reservation holds *before*
  any `/api` route exists. This is also why the mount must be installed last (AC 10) — at install
  time the route table must already be complete.

**#2 — `StaticFiles` is subclassed, not replaced.** The fallback is `get_response()` catching its
own 404; everything else (ETag, `Last-Modified`, `304`, ranges, `HEAD`) stays Starlette's. Do not
write a `@app.get("/{path:path}")` handler that opens files — it re-implements four RFCs badly and
would be the first hand-rolled file server in a repo that has none.

**#3 — the generated tree is `src/`-shaped, and that has consequences the dev must not "fix".**
`src/companion/app/static/` is inside the Python package on purpose (AD-13). Therefore:
`ruff check .` visits only `*.py` and never sees it; `mypy src/` is `*.py`-scoped; pytest's
`testpaths = ["tests"]` never descends into it; and `tests/unit/companion/test_import_boundary.py`
walks `rglob("*.py")` (verified) so the bundle is invisible to the AD-2/AD-3 guards. **No exclude
entries are needed anywhere** — and adding one to `pyproject.toml` would break AC 16's proof that
the packaging config knows nothing about `ui/`.

**#4 — `index.html` is served `no-cache`; hashed assets are immutable.** *(Proposed ruling —
see Open Questions Q2; implement it unless Brad overrules.)* Starlette sets **no `Cache-Control` at
all**, which leaves the browser free to heuristically cache `index.html`. Combined with
`emptyOutDir: true` — which *deletes* the previous hashed assets — a stale cached index after a
`git pull` references files that no longer exist: a blank page that a reload does not fix. One
header on one file closes it: `Cache-Control: no-cache` on `index.html` (revalidate, do not
re-download), and `public, max-age=31536000, immutable` on `/assets/*`, which is safe precisely
because those names are content hashes.

### Architecture rules this story implements

- **AD-13** in full, both halves: *"The bundle is committed at `src/companion/app/static/` and
  mirrored into `plugin/` by the existing rebuild + drift-check machinery. Both copies are generated
  artifacts — never hand-edited. Node is dev/CI-only."* c2-1 delivered the second sentence's
  precondition (`pyproject.toml` knows nothing about `ui/`); this story delivers the rest.
- **FR-01**: *"Backend serves the SPA and REST API on a configurable localhost port."* The REST half
  has existed since c1-2; the SPA half is this story.
- **SC-4**: *"A fresh install can launch the companion app with a single `uv` command and no build
  step."* AC 17 is the only proof that counts, and it is a human one.
- **AD-16 / the c1-4 contract**: the closed reason-token set is not extended. The catch-all mount is
  the first thing in the feature that can *shadow* the contract, which is why AC 9 exists at all.
- **AD-10**: construction stays inert. A stat is not a side effect; a `mkdir` is.

### Source tree — what exists, what this story adds

```text
.gitattributes                        # NEW — one scoped line          (AC 5)
src/companion/app/
  spa.py                              # NEW — STATIC_DIR + install_spa (AC 7-11)
  static/                             # NEW — GENERATED + COMMITTED    (AC 1, 4)
    index.html  favicon.svg  assets/…
  main.py                             # UPDATE — install_spa(app), last (AC 10)
ui/
  vite.config.ts                      # UPDATE — outDir + emptyOutDir  (AC 1, 2)
  index.html                          # UPDATE — generated-file notice (AC 6)
  README.md                           # UPDATE — where the build lands (AC 19)
  tests/                              # UPDATE — outDir config assertion (AC 3)
scripts/build_plugin.py               # UPDATE — mirrored-bundle sentinel (AC 14)
.github/workflows/ci.yml              # UPDATE — SPA drift check        (AC 12)
tests/unit/companion/
  test_spa.py                         # NEW — serving + contract + guard tests
plugin/server/src/companion/app/static/  # GENERATED by the pre-commit hook
```

**Current state of the files being modified** (read them before editing — this is the step whose
absence causes review cycles):

- [src/companion/app/main.py](src/companion/app/main.py) — `build_app()` is 17 lines of body:
  constructs `_CompanionFastAPI` (a `FastAPI` subclass whose `openapi()` strips the auto-422),
  `include_router(health.router)`, then `install_security(app)` then `install_error_handling(app)`
  **in that order**. *What must be preserved:* the middleware ordering comment and its reasoning
  (`user_middleware[0]` is the most recently added, so the error middleware must be installed last
  to end up outermost). Your `install_spa(app)` adds a **route**, not middleware, so it does not
  disturb that ordering — but it must come after `include_router` and it should be the final line,
  with a comment saying why. The lifespan, `bound_port`, `agent_token` and the discovery publish are
  untouched by this story.
- [src/companion/app/errors.py](src/companion/app/errors.py) — `http_exception_handler` converts any
  Starlette `HTTPException` to the typed body, keeping the framework's status and headers, with
  `invalid_request` for 4xx and `internal_error` for 5xx. **This is why AC 9 mostly works for free**:
  `StaticFiles` raises `HTTPException(404)`, which is dispatched by `ExceptionMiddleware` (the mount
  sits inside it) and comes out as `404 {"reason": "invalid_request"}`. Verify rather than assume,
  and do not register a second handler.
- [src/companion/app/security.py](src/companion/app/security.py) — `HostValidationMiddleware` is a
  pure-ASGI middleware, so it wraps the mount too: static assets are behind the same localhost-only
  envelope as everything else. Nothing to change; read it so you know why a test client must address
  the app as `127.0.0.1:<bound_port>` (the conftest seam does this for you).
- [tests/unit/companion/conftest.py](tests/unit/companion/conftest.py) — `lifespan_client` enters
  `main.lifespan` directly (ASGI transport never sends lifespan messages), stamps
  `app.state.bound_port = 54321` and derives a matching `base_url` so the `Host` check passes. An
  autouse `isolated_data_dir` fixture points `PLANESWALKER_DATA_DIR` at `tmp_path`. **Use this
  seam** — a hand-rolled `httpx.AsyncClient` will get a typed 400 and you will spend an hour on it.
- [tests/unit/companion/test_app.py](tests/unit/companion/test_app.py) —
  `TestConstructionIsInert` asserts that importing and constructing creates no data directory
  (`data_dir()` ends in `mkdir`, so one call would create it). These tests must pass **unchanged**
  after your change (AC 11); if they need editing, your construction is doing something it should
  not.
- [scripts/build_plugin.py](scripts/build_plugin.py) — `shutil.copytree(REPO_ROOT/"src", …,
  ignore=IGNORE)` with `IGNORE = __pycache__, *.py[cod], *.swp, *.swo, .DS_Store` — the bundle rides
  along untouched. The `src/viewer/__init__.py` existence check at line ~191 is the exact precedent
  for AC 14's sentinel (it exists because omitting `src/viewer/` broke the first `.mcpb` build).
  *What must be preserved:* the "clean managed outputs only" behaviour (a blanket `rmtree` chokes on
  a locked `.venv` on Windows) and `_write_json`'s `newline="\n"`.
- [.github/workflows/ci.yml](.github/workflows/ci.yml) — two jobs. `quality` (Python 3.12/3.13
  matrix) ends with the `plugin/`-in-sync step: rebuild, then `git status --porcelain -- plugin/`
  with an `::error::` annotation and a diff dump. **Copy that shape.** `frontend` (node 20) has
  `defaults.run.working-directory: ui` and five gate steps ending in `Build`. *What must be
  preserved:* every action SHA-pinned with the version in a trailing comment; `permissions:
  contents: read`; the `concurrency` block; the plugin drift step staying **last** in `quality`;
  `pytest` scoped to `not integration`.
- [ui/vite.config.ts](ui/vite.config.ts) — react plugin, `server.proxy` from `createDevProxy`, and
  a two-project vitest block (`node` for `tests/**`, `dom` for `src/**`). The comment at lines 11-13
  forward-references **this story** for the `outDir` redirect; replace it with the real thing.
  *What must be preserved:* both vitest projects' `{ts,tsx}` includes (a round-1 review patch — a
  file matching neither glob is a silently-never-run test) and the `dom` project's `setupFiles`.
- [ui/package.json](ui/package.json) — `"build": "tsc -b && vite build"`. The `"//"` block is the
  home for pin rationales; the stylelint/prettier ignore patterns mention `dist/**`, which becomes
  vestigial after this story. Leaving them is fine and cheaper than reasoning about it; do not
  "tidy" them into a behaviour change.

### Gotchas specific to this story

1. **`ui/dist` stops being produced.** `ui/.gitignore`, `.prettierignore` and the stylelint
   `--ignore-pattern "dist/**"` still name it. Harmless. Removing them is not this story's change
   and each removal is a chance to break a gate for nothing.

2. **The pre-commit `build-plugin-sync` hook fires on `^src/`** — and `src/companion/app/static/**`
   matches. So *every* commit that touches the bundle regenerates `plugin/` and pre-commit fails
   once, asking you to re-add. That is the hook working, not a problem: `git add plugin && git commit`
   again. (c2-1 never saw this because it never touched `src/`.)

3. **`npm run build` now writes outside `ui/`, so a build is no longer a no-op on the Python tree.**
   Running the frontend suite is still safe (vitest does not build), but any command you run in
   `ui/` that ends in `vite build` mutates `src/`. Check `git status` before you commit.

4. **`emptyOutDir: true` is a recursive delete keyed off a computed path.** Get the path assertion
   (AC 3) in place *before* the first build, not after.

5. **The mount at `/` is matched only after earlier routes — including FastAPI's own.** `/docs`,
   `/redoc` and `/openapi.json` are registered by `FastAPI.__init__`, so they precede everything and
   survive. `/health` precedes it because `include_router` runs earlier. A route added **after**
   `install_spa(app)` does not, and will fail in the most confusing possible way: it returns the
   index with a 200 instead of 404ing. AC 10's guard test message is what saves the next author.

6. **A `404.html` in the bundle would silently change the fallback.** `StaticFiles(html=True)`
   looks for `404.html` before raising, and would answer client routes with a **404 status** and
   that document. Vite does not emit one today (nothing in `ui/public/` produces it); if a later
   story adds one, this behaviour changes underneath the tests. Say so in a comment.

7. **Do not add `check_dir=False` to make a missing bundle "work".** It converts a legible startup
   error into a 404 on every page load, which is the same class of quiet failure as landmine #4.
   AC 11 wants the loud version, with the rebuild command in the message.

8. **Cross-platform build determinism is the one thing this story cannot fully verify locally.**
   Brad builds on Windows / node 24; CI rebuilds on ubuntu / node 20 and diffs. Hashes are
   content-derived and the lockfile pins rolldown and lightningcss, so they *should* match
   byte-for-byte — but "should" is doing work. **Push early and let CI tell you** (an early draft PR
   is cheaper than discovering it at the end). If CI reports drift on an otherwise-unmodified tree:
   that is a finding to record and raise, **not** a reason to loosen the check into uselessness.
   Options if it happens, in preference order: identify and pin the varying input; normalise the
   compared surface (file list + content hashes) while keeping it a hard gate; escalate to Brad.
   Do not make the check advisory.

9. **`git status --porcelain` from inside `ui/`.** The `frontend` job's `defaults.run` sets
   `working-directory: ui`. A pathspec of `src/companion/app/static/` from there matches nothing and
   the check passes vacuously — the exact vacuity shape this project's reviews punish. Set
   `working-directory: .` on that step and prove the check fails when it should (AC 13).

10. **Two `index.html` files now exist and they are not the same file.** `ui/index.html` is the
    Vite *source* template; `src/companion/app/static/index.html` is *generated output*. Edit the
    former, never the latter. AC 6's embedded comment exists because that mistake is one keystroke
    away in an editor's fuzzy file-open.

11. **`uv build` writes to `dist/`, which the root `.gitignore` covers.** AC 16's proof leaves no
    trace, but delete the artifact afterwards anyway so a later `git status` is not noisy.

### Testing standards

- **Two suites, two homes, no overlap** (c2-1's standing rule). Backend serving is pytest under
  `tests/unit/companion/`; the `outDir` config assertion is vitest under `ui/tests/` (the `node`
  project). Do **not** add a pytest test that shells out to `npm` — it would need Node at test time
  and contradict AD-13.
- **Drive the backend through the `lifespan_client` seam**, in-process over `httpx.ASGITransport`
  (AD-10). This story adds **no** real-socket test; the one integration-marked test in the whole
  feature is c5-8's.
- **Non-vacuity pairing is an AC, not a nicety** (standing agreement promoted at the C1 retro).
  Every gate here names its pair: AC 2 (junk file present → absent), AC 4 (no ignored files → and
  files exist), AC 9 (fallback fires → and does *not* fire for `/api`, assets, `POST`), AC 10 (mount
  is last → and a real route still wins), AC 13 (drift check red → green).
- **The gate proves itself by breaking.** The two mutations this story owes are the AC 2 junk-file
  removal and the AC 13 stale-bundle red. Paste both outputs.
- The Python test file naming follows the package: `tests/unit/companion/test_spa.py`, classes
  `Test*`, `async def test_*` with no `@pytest.mark.asyncio` (`asyncio_mode = "auto"`).

### Previous story intelligence (c2-1, done 2026-07-26; PR #18 merged into `feat/companion-c2`)

- **Two review rounds, 28 patches.** The patterns that bit, and that this story is exposed to:
  - **Prefix-vs-anchor matching.** The dev proxy's `/api` and `/health` keys were bare prefixes, so
    `/healthcheck` was forwarded to the backend; the fix was anchored regexes, and round 2 then
    found that Vite matches the **full URL including the query string**, so `^/health$` failed on
    `/health?verbose=1` and served HTML with a 200. **Your fallback rule has the same shape.** Test
    query strings and near-miss prefixes (`/api-docs`, `/healthcheck`) explicitly.
  - **`new URL(...).pathname` → `C:\C:\…` on Windows.** Use `fileURLToPath` (AC 1).
  - **Gate geometry.** Round 2 added `ui/tests/gate-geometry.test.ts` banning test files outside the
    two vitest roots and stray `.jsx/.mjs/.cjs`. If you add a test file in `ui/`, put it under
    `ui/tests/` (`node` project) or beside a component in `ui/src/` — anywhere else is a silent
    non-run **and** now a red guard test.
  - **A gate that ignores one tool's output.** stylelint was the one tool not ignoring `coverage/**`.
    Ask the same question of your new drift check: what *else* writes into
    `src/companion/app/static/`? (Answer today: nothing but Vite — keep it that way, landmine #2.)
- **c2-1 deliberately did not create `src/companion/app/static/`** (its AC 20) and left keyed
  comments pointing at this story in `vite.config.ts`. Those comments are your first edit.
- **`npm ci`, never `npm install`** — the lock is canonical and CI fails on drift rather than
  updating. Nothing in this story changes dependencies; if `package-lock.json` appears in your diff,
  something went wrong.
- **Three load-bearing pins** live in `ui/package.json`'s `"//"` block (`typescript >=5.9 <6.1`,
  `eslint ^9`, `@testing-library/jest-dom ~6.9.1`). Do not bump anything.
- **AC-deviation culture:** c1-9 and c2-1 both hit ACs that could not be satisfied literally and
  **said so loudly** rather than quietly picking a side. AC 12 here is the same situation
  (`git diff --exit-code`). Follow the precedent.

### Git intelligence

- `9d47b24` merged PR #18 (`feat/companion-c2-1-frontend-scaffold` → `feat/companion-c2`). Your
  branch cuts from `feat/companion-c2` and your PR targets it — **not** master. One integration PR
  per epic goes to master after the retro, with no Greptile pass (standing rule, OSS free-tier
  budget).
- Commit-message convention across the epic: `feat(companion): …`, `fix(companion): …`,
  `docs(companion): …`. A commit carrying the generated bundle is still `feat(companion): …`.
- Expect the bundle and the `plugin/` mirror to make this a large diff by line count and a small one
  by hand-written lines. Say so in the PR body so a reviewer knows what to skip and what to read.
- c2-1's story PR carried its whole scaffold in one commit and then two review-patch commits. Same
  shape is fine here; do not split the bundle from the code that serves it, or a bisect lands on a
  commit that serves a directory that does not exist.

### Latest technical information

Measured on this machine at `9d47b24`, from the installed packages — not quoted from documentation.

| Thing | Value | Why it matters here |
|---|---|---|
| `vite` | 8.1.5 | `emptyOutDir` defaults to *true only when `outDir` is inside the project root*; outside it, Vite warns and skips (source read from `chunks/node.js`) |
| Vite `emptyDir` skip list | `[".git"]` only | every other file in `static/` is deleted on each build |
| `starlette` | 0.48.0 | `StaticFiles(directory, packages, html, check_dir, follow_symlink)`; `html=True` serves `index.html` for a directory and looks for `404.html` before raising |
| `FileResponse` media type | `guess_type(...)[0] or "text/plain"` | an unknown extension is served as `text/plain` |
| `mimetypes` here | `.js`→`text/javascript`, `.css`→`text/css`, `.svg`→`image/svg+xml`, **`.woff2`→`None`**, `.map`→`None` | c2-5's fonts would ship as `text/plain`; `.js` is registry-dependent on Windows |
| `fastapi` | 0.140.0 | `/docs`, `/redoc`, `/openapi.json` are registered in `FastAPI.__init__`, i.e. before any mount |
| `git check-ignore` on the new paths | no match (exit 1) | nothing in `.gitignore` blocks the bundle — the premise of AC 4 and AC 16 |
| hatchling | `packages = ["src"]` | includes non-Python files under the package; VCS-ignored files are excluded by default, which is why AC 4 and AC 16 are separate proofs |

### Project Structure Notes

- `src/companion/app/static/` is inside the Python package **by architectural decision**, not
  convenience: the project ships as a cloned plugin tree, so a wheel-build hook that compiled the
  SPA at install time would leave plugin users with nothing (AD-13).
- The new serving module belongs beside `security.py` and `errors.py` in `src/companion/app/`, not
  under `routes/` — it installs a mount, not a router. Follow the `install_*(app)` naming so
  `build_app()` reads as four verbs.
- `tests/unit/companion/test_import_boundary.py::test_every_companion_file_sits_in_a_guarded_category`
  enumerates every `*.py` under `src/companion/` and requires each to fall in a guarded category. A
  new `spa.py` inside `app/` is an app-role file and is covered — but **run that test early**, not
  at the end, so a categorisation surprise is cheap.
- Naming inside `ui/` stays frontend-convention (`camelCase.ts`, `PascalCase.tsx`); the
  project-context.md rules govern `src/` and stop at the language boundary.

### References

- [epics-companion-app.md#Story-2.2](_bmad-output/planning-artifacts/epics-companion-app.md) — the
  five AC blocks (lines 1243-1272)
- [epics-companion-app.md#Structure-and-boundaries](_bmad-output/planning-artifacts/epics-companion-app.md)
  — the committed-artifact requirement (lines 300-302); *Starter template / greenfield sub-tree*
  naming the "build-into-`app/static` pipeline" as this epic's work (lines 183-190)
- [epics-companion-app.md#Story-8.5](_bmad-output/planning-artifacts/epics-companion-app.md) —
  plugin distribution parity, which consumes what this story produces (lines 3283-3306)
- [ARCHITECTURE-SPINE.md#AD-13](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md)
  — committed artifact, mirrored into `plugin/`, Node dev/CI-only (lines 292-302)
- [ARCHITECTURE-SPINE.md#Structural-Seed](_bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md)
  — `static/  # COMMITTED SPA build output` (line 453)
- [prd.md#FR-01](_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md)
  — backend serves the SPA and REST API (line 102); **SC-4** (line 180)
- [c2-1 story record](_bmad-output/implementation-artifacts/c2-1-frontend-scaffold-with-the-full-quality-gate-from-the-first-commit.md)
  — the scaffold, the three pins, both review rounds, and the keyed comments pointing here
- [epic-c1-retro-2026-07-26.md](_bmad-output/implementation-artifacts/epic-c1-retro-2026-07-26.md) —
  ruling R2 (`/docs` stays enabled), the six standing team agreements
- [project-context.md](_bmad-output/project-context.md) — Python-side conventions (Google
  docstrings, module docstrings, logging not prints, `mypy --strict`)

## Open questions for Brad — answer before `dev-story`

Raised at story-creation time and homed here rather than left to surface mid-implementation (C1
retro action item 2). Each carries a recommendation; **the story is implementable as written if all
four are accepted** — an answer of "as proposed" needs no edits.

**Q1 — the SPA fallback rule (Decide-once #1).** Recommended: fall back to `index.html` only for
`GET`/`HEAD`, extension-less paths, outside registered route prefixes (with `api` reserved from the
start); everything else keeps the typed contract. *Alternative considered and not recommended:*
gating on `Accept: text/html` instead, which makes `curl /decks/42` return JSON and confuses manual
testing. **Recommend: as proposed.**

**Q2 — cache headers (Decide-once #4).** Recommended: `no-cache` on `index.html`,
`immutable` on `/assets/*`. It is ~6 lines and it closes a real "blank page after `git pull`"
failure that `emptyOutDir` creates. *Alternative:* defer to c10-3 (performance polish) and accept the
stale-index risk in the meantime. **Recommend: do it here.**

**Q3 — the root `.gitattributes` (AC 5).** c2-1 deliberately avoided creating one. This adds a root
file with a **single path-scoped** `-text` line — no repo-wide pattern, no renormalisation.
*Alternative:* rely on git's binary auto-detection plus `core.autocrlf` transparency, which does
work today but is an argument rather than a declaration, and gets more fragile when c2-5 adds fonts.
**Recommend: create it, scoped.**

**Q4 — the `git status --porcelain` deviation (AC 12).** The epic AC literally says
`git diff --exit-code`, which cannot see the untracked half of a content-hash rename. Proposed:
ship `git status --porcelain` (the pattern the same AC sentence points at) and flag it in the
Completion Notes, as c1-9 and c2-1 flagged theirs. **Recommend: as proposed** — this one is a
correctness fix, not a preference.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-07-26 | Story created — five measured landmines (Vite's outside-root `emptyOutDir` skip, `emptyDir`'s `.git`-only skip list, `git diff --exit-code` blindness to content-hash renames, Starlette's `text/plain` fallback with `.woff2` unresolved, mount-at-`/` route shadowing); AC 9's error-contract preservation and AC 10's mount-order guard added beyond the epic's five blocks; four open questions homed with recommendations | Amelia (create-story) |
