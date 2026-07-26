---
baseline_commit: 9d47b24
epic: c2
story: c2-2
work_branch: feat/companion-c2
story_branch: feat/companion-c2-2-serve-spa
---

# Story C2.2: The backend serves the built SPA as a committed artifact

Status: review

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

- [x] **Task 0 — Baseline verification** (standing agreement; before touching anything)
  - [x] `git rev-parse --short HEAD` = `9d47b24`, `git status --porcelain` empty, branch cut from
        `feat/companion-c2` as `feat/companion-c2-2-serve-spa`
  - [x] `uv run pytest -m "not integration"` → **1,684 / 1 / 45**, exactly as predicted
  - [x] `cd ui && npm ci && npm test` → **55**, exactly as predicted
  - [x] `git check-ignore -v src/companion/app/static/index.html` → no match (exit 1)

- [x] **Task 1 — Redirect the build output** (AC 1, 2, 3)
  - [x] `vite.config.ts`: `build.outDir` via `fileURLToPath(new URL('../src/companion/app/static',
        import.meta.url))`, `emptyOutDir: true`, with a comment naming landmines #1 and #2
  - [x] Stale c2-2 forward-reference comment in `vite.config.ts` deleted
  - [x] `npm run build`, then the junk-file emptying proof; both pasted (redone after a
        self-inflicted vacuity — see Completion Note 9)
  - [x] Config-assertion test `ui/tests/buildOutput.test.ts` (`node` project), proven red on a
        mistyped path

- [x] **Task 2 — Commit the bundle, and make its bytes deterministic** (AC 4, 5, 6)
  - [x] Root `.gitattributes` — **two** scoped `-text` lines, not one (deviation, Completion Note 2)
  - [x] `git add src/companion/app/static`; both AC 4 commands run and pasted
  - [x] Generated-file notice in `ui/index.html`; confirmed present in the built output and pinned
        by a test
  - [x] No repo-wide renormalisation: `w/crlf` count **83 before, 83 after**

- [x] **Task 3 — Serve it** (AC 7, 8, 9, 10, 11)
  - [x] `src/companion/app/spa.py` exporting `STATIC_DIR` and `install_spa(app)`, matching the
        `install_security` / `install_error_handling` naming
  - [x] `StaticFiles` subclass with the fallback rule (`html=False`, Completion Note 6); explicit
        `mimetypes.add_type` registrations; **plus** `_SpaMount`, which the story did not
        anticipate (Completion Note 4)
  - [x] `install_spa(app)` **last** in `build_app()`, with the ordering comment
  - [x] Tests: index, asset + content types, client-route fallback, all four AC 9 contract cases,
        the mount-order guard with its instructive message, `TestConstructionIsInert` passing
        **unchanged**, missing-bundle error, cache headers, ETag/304, query strings, near-miss
        prefixes

- [x] **Task 4 — CI drift check** (AC 12, 13)
  - [x] New `SPA bundle in sync with ui/` step after `Build`; `working-directory: .`; plugin-check
        shape
  - [x] Teeth proof (stale → red, rebuilt → green) pasted, **plus** the scenario that actually
        separates `git status` from `git diff` (Completion Note 1)

- [x] **Task 5 — Plugin mirror and the wheel** (AC 14, 15, 16)
  - [x] `scripts/build_plugin.py` sentinel in the `src/viewer` shape; proven to abort with exit 1
  - [x] `uv run python -m scripts.build_plugin`; regenerated `plugin/` tree committed
  - [x] pytest byte-identity test for the mirrored `index.html` (+ asset-name parity)
  - [x] `uv build` + wheel listing pasted; `pyproject.toml` untouched; `dist/` deleted

- [x] **Task 6 — Records and gates** (AC 18, 19, 20, 21)
  - [x] Forward-dated comments keyed (c2-5 fonts, c3-1 routers, c2-3 types, c8-5 parity, c2-6 shell)
  - [x] `ui/README.md` build-output section; stale "Not in this story" re-pointed
  - [x] Scope-boundary proof pasted (empty)
  - [x] Both suites + all four Python gates + all five frontend gates green

- [x] **Task 7 — Live checks a test cannot close** (AC 17)
  - [x] Fresh `git worktree` with **no `node_modules`**; `uv run artificial-planeswalker companion`;
        every surface probed live and pasted. **The browser render itself is not confirmed by me** —
        see the note under AC 17; it belongs on Brad's manual-testing checklist.
  - [x] `/health` answers JSON and `/docs` + `/openapi.json` still answer, from the **same**
        running instance behind the catch-all mount (R2's keep-decision holds)

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

Claude Opus 5 (1M context) — `claude-opus-5[1m]`, via bmad `dev-story`.

### Debug Log References

All four open questions were answered **as proposed** by Brad before implementation began (Q1
fallback rule, Q2 cache headers here, Q3 scoped `.gitattributes`, Q4 `git status --porcelain`).
No question remained open during development.

**Task 0 baseline, confirmed on this machine at `9d47b24`:**

- `git rev-parse --short HEAD` = `9d47b24`; branch cut as `feat/companion-c2-2-serve-spa`
- `uv run pytest -m "not integration"` → **1,684 passed / 1 skipped / 45 deselected** (exactly as
  the story predicted; no investigation needed)
- `cd ui && npm ci && npm test` → **55 tests / 6 files** (as predicted)
- `git check-ignore -v src/companion/app/static/index.html` → exit 1, no match (AC 4's premise
  re-confirmed)

### Completion Notes List

#### Deviations, flagged not silently taken

1. **AC 12 — `git status --porcelain`, not `git diff --exit-code`** (Q4, ruled as proposed). Shipped
   as the story directed, and the deviation is now **proven rather than argued**. The first
   scenario tested (edit `App.tsx`, rebuild) turned *both* commands red, because `index.html`
   changed too — so it did **not** justify the deviation. The scenario that actually separates them
   is a **new emitted asset with no tracked file changing** (a file added to `ui/public/`):

   ```
   -- git diff --exit-code -- src/companion/app/static/  -> 0   (PASSES: ships a stale bundle)
   -- git status --porcelain -- src/companion/app/static/ -> ?? src/companion/app/static/manifest.json
   ```

2. **AC 5 — the root `.gitattributes` has TWO scoped lines, not one.** The story called for one
   (`src/companion/app/static/** -text`). One is measurably not enough: the **plugin mirror** of the
   same bundle is compared byte-for-byte against the source of truth (by the `plugin/` drift check
   and by AC 15's test), and it had no attribute. Measured, not reasoned — deleting both copies and
   letting git restore them (which applies the `core.autocrlf` smudge filter exactly as a fresh
   clone does) produced:

   ```
   src/    .../index.html  1093 bytes  (i/lf  w/lf   attr/-text)
   plugin/ .../index.html  1119 bytes  (i/lf  w/crlf attr/)      <- 26 line endings apart
   byte-identical? NO
   ```

   So on any **fresh Windows clone** AC 15's test fails and the plugin drift check reports drift on
   an untouched tree. **CI could never have caught this** — CI is ubuntu, where `autocrlf` is off,
   so it is Windows-only *and* fresh-clone-only. Second line added:
   `plugin/server/src/companion/app/static/** -text`. Still path-scoped, so AC 5's actual concern
   (a repo-wide pattern renormalising every tracked file, which is why c2-1 declined this file)
   is untouched: `git ls-files --eol -- src/ | grep -c 'w/crlf'` is **83 before and 83 after**.

#### Two real bugs found during implementation, both invisible to the story's analysis

3. **`_IncludedRouter` made the reserved-prefix derivation silently empty.** Decide-once #1 says to
   derive reserved prefixes from `app.routes` so c3-1's `/api/decks` reserves `api` on its own. A
   plain `getattr(route, "path", "")` walk finds **nothing** from `include_router`: FastAPI 0.140
   wraps an included router in an `_IncludedRouter` that carries neither `.path` nor `.routes` (its
   routes hang off `.original_router`, its prefix off `.include_context`). `/health` was therefore
   never reserved, and every prefix c3-1 (`/api`) and c5-5 (`/agent`) will register the same way
   would have fallen through to the SPA index instead of the typed 404. `api` masked it, because it
   is seeded. Fixed with a recursive `_route_paths` walk covering all three nesting shapes; the
   reads of FastAPI internals are `getattr` with fallbacks and are **pinned by a test with an
   instructive failure message**, so a FastAPI upgrade goes red rather than quietly emptying the
   reservation.

4. **The mount destroyed `405 Allow`, an existing error-contract guarantee.** Starlette's router
   takes the first `Match.FULL` and returns immediately; a `Mount("/")` reports `FULL` for every
   path, so it beat the `Match.PARTIAL` a real route reports when the path matches but the method
   does not — and that partial is precisely how Starlette produces `405` with the RFC-9110-mandated
   `Allow` header, which [errors.py](src/companion/app/errors.py) deliberately forwards ("dropping
   them would make the typed body a downgrade"). `POST /health` was answering **405 with no
   `Allow`**, and once c5-5 adds a POST-only `/agent/events`, a plain `GET` of it would have
   answered **404 instead of `405 Allow: POST`**. Fixed with `_SpaMount.matches()` returning
   `Match.NONE` for reserved prefixes — handing those paths back to the router, which knows each
   route's real method set — plus `Allow: GET, HEAD` on the mount's own 405, which `StaticFiles`
   omits. Both directions are now pinned by tests. This is the **error-contract enumeration**
   standing agreement doing its job.

5. **32 tests were being served `index.html` instead of running.** `test_errors.py`,
   `test_deps.py` and `test_security.py` attach throwaway routes to a real `build_app()` with
   `@app.get(...)`, which can only *append* — i.e. below `install_spa(app)`, the one thing
   `main.py` forbids. This is AC 10's failure mode, found by the guard it predicts. Fixed in the
   tests, not by weakening the rule: `conftest.keep_spa_mount_last(app)` restores the production
   ordering after the fact. `test_errors.py::test_an_unknown_path_is_a_typed_404` was re-pointed:
   with a SPA mounted, an extension-less path outside the API is a **client route** and correctly
   answers 200 (pinned in `test_spa.py`); the three shapes that must still 404 (reserved prefix,
   file extension, under a registered route) are what it now guards.

#### Implementation decisions worth knowing

6. **`html=False`, not `html=True`.** Gotcha 6 warned that `StaticFiles(html=True)` looks for a
   `404.html` before raising, so a later story adding one would silently change every client route
   to a 404-status HTML document. `html=False` removes that hazard **entirely** rather than
   commenting on it: `GET /` reaches the index through the explicit fallback rule (normpath renders
   the site root as `"."`, which has no meaningful segments), which is the same code path every
   client route takes and the one the tests pin.

7. **AC 4's command needed adjusting to stay non-vacuous.** As written it runs `git check-ignore` on
   `git ls-files -o` (untracked) output — which is empty *after* `git add`, so `check-ignore` gets
   no arguments and exits 128 `fatal: no path specified`. Run instead over every path actually on
   disk, which is the stronger form: it would also catch a file that was ignored and therefore never
   tracked. Result: exit 1 (nothing ignored) against 4 tracked files.

8. **AC 16 needed no packaging change.** `uv build` puts all four bundle files in the wheel with
   `pyproject.toml` untouched — AD-13's "Node is never required at install" proved by the packaging
   config staying ignorant of `ui/`. `dist/` deleted afterwards.

9. **A self-inflicted vacuity, caught and redone.** The first AC 2 emptying proof was invalid: a
   PowerShell `Set-Location` had left the shell in `ui/`, so the junk file was planted at
   `ui/src/companion/app/static/` — a directory Vite never touches — and the "it's gone" check read
   the real directory. Redone with absolute paths on both sides (see the proof below). The stray
   tree was deleted. Recorded because the *class* of error is what this project's reviews punish,
   and it nearly shipped inside a proof.

#### The proofs the story asked for

**AC 2 — `emptyOutDir` really empties (and nothing hand-written can live there):**

```
=== BEFORE npm run build (absolute paths) ===
/c/.../src/companion/app/static/JUNK-STALE-BUNDLE.txt
/c/.../src/companion/app/static/assets/index-kbn8nqvM.js
/c/.../src/companion/app/static/assets/index-tIQG_ZwB.css
/c/.../src/companion/app/static/favicon.svg
/c/.../src/companion/app/static/index.html

=== AFTER npm run build (absolute paths) ===
/c/.../src/companion/app/static/assets/index-kbn8nqvM.js
/c/.../src/companion/app/static/assets/index-tIQG_ZwB.css
/c/.../src/companion/app/static/favicon.svg
/c/.../src/companion/app/static/index.html

JUNK-STALE-BUNDLE.txt still present: NO
```

**AC 3 — the config assertion has teeth.** Mistyping `outDir` to `../src/companion/app` (which
`emptyOutDir: true` would have recursively deleted) turns 2 of the 4 assertions red:

```
FAIL |node| tests/buildOutput.test.ts > ends the resolved path at src/companion/app/static
  Expected: /\/src\/companion\/app\/static$/
  Received: "C:/Users/brads/Projects/Artificial-Planeswalker/src/companion/app"
```

**AC 4 — nothing ignored, and the tree is really tracked:**

```
git check-ignore -v $(find src/companion/app/static -type f)  -> exit 1  (no path is ignored)
git ls-files src/companion/app/static/ | wc -l                -> 4      (non-vacuity pair)
```

**AC 5 — no repo-wide renormalisation, attribute scoped:**

```
w/crlf count across src/:  83 BEFORE  ->  83 AFTER
src/companion/app/static/index.html:  text: unset
src/companion/app/main.py:            text: unspecified
README.md:                            text: unspecified
```

**AC 13 — the drift check red, then green:**

```
=== RED (after editing ui/src and rebuilding, as CI does) ===
::error::src/companion/app/static/ is stale — run 'cd ui && npm run build' and commit the bundle.
 D src/companion/app/static/assets/index-kbn8nqvM.js
 M src/companion/app/static/index.html
?? src/companion/app/static/assets/index-D5XWiX32.js        <- the untracked half git diff cannot see

=== GREEN (after a clean rebuild) ===
   entries: 0
```

**AC 14 — the plugin sentinel aborts rather than shipping a UI-less plugin:**

```
$ (index.html temporarily removed) uv run python -m scripts.build_plugin
ERROR - companion SPA bundle missing from copied server (...\static\index.html) — aborting.
        Build it with: cd ui && npm run build
build_plugin real exit code: 1
```

**AC 16 — the bundle is in the wheel, `pyproject.toml` untouched:**

```
$ git status --porcelain -- pyproject.toml        (empty)
$ uv build && python -m zipfile -l dist/artificial_planeswalker-0.4.0-py3-none-any.whl | grep static
src/companion/app/static/favicon.svg                        806
src/companion/app/static/index.html                        1093
src/companion/app/static/assets/index-kbn8nqvM.js        190581
src/companion/app/static/assets/index-tIQG_ZwB.css          354
```

**AC 17 — fresh install, no Node, live (`git worktree add --detach` at a short temp path; the
scratchpad path hit Windows' 260-char limit — the repo's known "longpaths note pending" item):**

```
ui/node_modules: ABSENT        (the bundle came from the checkout alone)
$ COMPANION_PORT=9222 uv run artificial-planeswalker companion
  Creating virtual environment at: .venv ... Installed 81 packages in 2.98s
  [planeswalker] companion running at http://127.0.0.1:9222

PATH                                  STATUS  CONTENT-TYPE
/                                  -> 200  text/html; charset=utf-8
/decks/42                          -> 200  text/html; charset=utf-8
/assets/index-kbn8nqvM.js          -> 200  text/javascript; charset=utf-8
/assets/index-tIQG_ZwB.css         -> 200  text/css; charset=utf-8
/favicon.svg                       -> 200  image/svg+xml
/health                            -> 200  application/json   {"status":"ok","instance_id":"136cd7d8-…"}
/docs                              -> 200  text/html; charset=utf-8      <- R2 keep-decision holds
/openapi.json                      -> 200  application/json              <- behind a catch-all mount
/api/anything-unknown              -> 404  application/json   {"reason":"invalid_request"}
/assets/does-not-exist.js          -> 404  application/json   {"reason":"invalid_request"}
POST /decks/42                     -> 405  application/json   {"reason":"invalid_request"}

cache-control: no-cache                                  (index.html)
cache-control: public, max-age=31536000, immutable       (hashed asset, with an ETag)
POST /health -> HTTP/1.1 405 / allow: GET                (the AC 9 + Allow fix, live)

served /assets/index-kbn8nqvM.js is byte-identical to the committed file: YES
the served bundle contains "Artificial Planeswalker", "createRoot", "useState"
```

> **One half of AC 17 is Brad's, not mine.** I verified the document, the assets, the content
> types and that the served bundle is the real React app — everything short of eyes on pixels.
> **I did not open a browser and watch it paint**, so "the page renders" is unconfirmed by me and
> belongs on the manual-testing checklist. Everything a non-human can check is green.
> The worktree, the temp venv and the stale discovery file the killed process left behind were all
> removed; `git status` is clean and `git worktree list` shows only the main checkout.

**AC 20 — scope proof:**

```
$ git status --porcelain -- pyproject.toml uv.lock .pre-commit-config.yaml .gitignore \
    README.md CONTRIBUTING.md .mcp.json
(empty)
$ git status --porcelain -- ui/package.json ui/package-lock.json
(empty)
```

**The known flake surfaced once, and is not this story's.** On one full-suite run,
`tests/integration/data/test_deck_repository.py::test_list_decks_with_strategy_field` failed; it
passed 3/3 in isolation and the very next full run was 1,739 green. This is the **pre-existing
order-flake c2-1 found at its own Task 0** (a `created_at` tie with no secondary sort key), already
homed in `deferred-work.md`. `git diff --name-only feat/companion-c2 -- src/data/ tests/integration/`
returns **0 files**, so this story touches neither the repository nor its tests. Recorded rather
than re-run into silence.

**AC 21 — both suites, at or above baseline:**

| Gate | Baseline | Now |
|---|---|---|
| `uv run pytest -m "not integration"` | 1,684 / 1 skipped / 45 deselected | **1,739 passed / 1 skipped / 45 deselected** |
| `uv run ruff check .` | green | green |
| `uv run ruff format --check .` | green | green (284 files) |
| `uv run mypy src/` | green | green (84 files) |
| `uv run mypy src/ --platform win32` | green | green (84 files) |
| `npm run lint` / `format:check` / `typecheck` / `test` / `build` | 55 tests | **59 tests**, all five green |

### File List

**New**

- `.gitattributes` — two scoped `-text` lines (AC 5, + the mirror deviation)
- `src/companion/app/spa.py` — `STATIC_DIR`, `install_spa`, `_SpaMount`, `_SpaFiles`
- `src/companion/app/static/index.html` — generated, committed
- `src/companion/app/static/favicon.svg` — generated, committed
- `src/companion/app/static/assets/index-kbn8nqvM.js` — generated, committed
- `src/companion/app/static/assets/index-tIQG_ZwB.css` — generated, committed
- `tests/unit/companion/test_spa.py` — 53 tests
- `ui/tests/buildOutput.test.ts` — the `outDir` / `emptyOutDir` config assertion
- `plugin/server/src/companion/app/spa.py` + `plugin/server/src/companion/app/static/**` —
  generated by `scripts/build_plugin.py`

**Modified**

- `src/companion/app/main.py` — `install_spa(app)` last, with the ordering comment
- `scripts/build_plugin.py` — mirrored-bundle sentinel
- `.github/workflows/ci.yml` — SPA drift check on the `frontend` job
- `ui/vite.config.ts` — `outDir` + `emptyOutDir`; the stale c2-2 forward-reference removed
- `ui/index.html` — generated-output notice (copied through by Vite)
- `ui/README.md` — where the build output goes; "Not in this story" re-pointed
- `tests/unit/companion/conftest.py` — `keep_spa_mount_last`
- `tests/unit/companion/test_errors.py` — mount ordering; 404 test re-pointed
- `tests/unit/companion/test_deps.py` — mount ordering
- `tests/unit/companion/test_security.py` — mount ordering
- `plugin/server/src/companion/app/main.py` — generated mirror
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status transitions

**Deleted**

- `ui/dist/` — no longer produced (was untracked/gitignored)

## Change Log

| Date | Change | By |
|---|---|---|
| 2026-07-26 | Implemented → review. All 21 ACs met. Two deviations flagged: AC 12's `git status --porcelain` (ruled, and now *proven* — the separating case is a new emitted asset, where `git diff --exit-code` returns 0), and AC 5 shipping **two** scoped `.gitattributes` lines rather than one, because the plugin mirror diverged by 26 line endings on a simulated fresh Windows clone (1093 vs 1119 bytes) — a Windows-only, fresh-clone-only failure CI could never catch. Two real bugs the story's analysis could not foresee: FastAPI 0.140's `_IncludedRouter` exposes neither `.path` nor `.routes`, so the reserved-prefix derivation was silently empty for every `include_router` prefix (c3-1's `/api`, c5-5's `/agent`); and a `Mount("/")` reports `Match.FULL` for every path, beating the `Match.PARTIAL` that produces `405` with the RFC-mandated `Allow` header — `POST /health` was answering 405 with no `Allow`, and a future GET of a POST-only route would have answered 404 instead of `405 Allow: POST`. Fixed with `_SpaMount` declining reserved prefixes. AC 10's guard also caught 32 existing tests appending routes below the mount. Suites 1,684 → 1,739 (Python) and 55 → 59 (frontend); all nine gates green | Amelia (dev-story) |
| 2026-07-26 | Story created — five measured landmines (Vite's outside-root `emptyOutDir` skip, `emptyDir`'s `.git`-only skip list, `git diff --exit-code` blindness to content-hash renames, Starlette's `text/plain` fallback with `.woff2` unresolved, mount-at-`/` route shadowing); AC 9's error-contract preservation and AC 10's mount-order guard added beyond the epic's five blocks; four open questions homed with recommendations | Amelia (create-story) |
