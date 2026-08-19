---
title: 'Plugin distribution parity'
type: 'chore'
created: '2026-08-19'
status: 'done'
baseline_revision: '22950da5f25daa8846a3b6c097cb2c31d2459e37'
baseline_commit: '22950da5f25daa8846a3b6c097cb2c31d2459e37'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-15-context.md'
warnings: ['oversized']
deferred:
  - summary: >-
      CHANGELOG's [Unreleased] never says the plugin carries the companion or how to launch it
      from a plugin install, and story 15.6 publishes that section as the release notes.
    evidence: |-
      Story 15-4's entry already records that the bundle is "mirrored into the plugin tree", so the
      fact is present; what is absent is the install route. Adding a second launch form to the
      changelog sits on 15-4's "single documented command" surface, so it is a release-notes
      decision for the gate rather than a parity fix.
    location: >-
      CHANGELOG.md:8
    severity: low
  - summary: >-
      The plugin build and serve guards run only on ubuntu, so the two assertions whose rationale is
      Windows-specific are exercised only where they cannot fail.
    evidence: |-
      CI's `quality` job is ubuntu-latest and the Windows job is path-scoped to
      tests/integration/companion/, so _tree's POSIX-key rationale and the text/javascript
      content-type assertion (which the record states cannot be made to fail on macOS either, since
      only a rewritten Windows registry bites) never run on the platform they are about. Adding
      tests/integration/test_build_plugin.py to the Windows job's scope would close it, at the cost
      of the slowest runner class — a CI budget decision beyond this story's acceptance.
    location: >-
      .github/workflows/ci.yml:232
    severity: medium
---

<intent-contract>

## Intent

**Problem:** The plugin is the install route that has to carry the companion's UI, and almost nothing
proves it does. `scripts/build_plugin.py:194-216` hard-fails when the mirrored SPA bundle or its
`assets/` are missing — a guard whose own comment names this story as the acceptance it serves — and
no test exercises either abort, no test asserts a built tree carries the bundle at all, and the
skills check is presence-only, so a `bmad-*` directory added to `SKILLS` would ship unnoticed. CI's
plugin drift check is the one of the workflow's three drift checks with no non-vacuity guard: if the
mirrored bundle ever slipped out of tracking, `git status --porcelain -- plugin/` would report
nothing and the check would pass on an empty subject. And the two documents a plugin user or a
contributor actually reads — `docs/plugin-structure.md` and `CONTRIBUTING.md` — do not know the
companion exists: the layout tree stops at `paths.py`, nothing states that the two bundle copies are
generated artifacts that are never hand-edited, and no document tells someone who installed via the
plugin how to launch the app their install now contains.

**Approach:** Mechanise the parity claims where they can go red — the mirrored bundle's byte-identity
(in a fresh build *and* in the committed tree), both abort paths, an exclusive skills set, the
absence of any Node toolchain in the shipped tree, and the mirrored copy serving through the real SPA
mount — then close CI's vacuity hole and write the companion into the two documents, including a
plugin-anchored launch command that is run before it is written down. The two `.mcp.json` files are
verified, not touched.

## Boundaries & Constraints

**Always:**
- **Every documented command is exercised before it is documented.** The plugin-anchored launch
  command is run against the committed `plugin/server/` tree and its output recorded in the
  Verification Record; a command that was reasoned about rather than run does not go in the README.
- **Every new guard gets a firing proof** through the committed harness —
  `uv run python -m scripts.probe_harness --expect-red '<node id>'` — with the harness's proof line
  pasted into the Verification Record. Stage the tree before planting a violation.
- **After any `README.md` edit, run `uv run python -m scripts.build_plugin` and commit the
  regenerated `plugin/server/**`.** `README.md` is in `SERVER_FILES`; the `build-plugin-sync`
  pre-commit hook is not installed on this machine, and CI's `quality` job fails on both matrix legs
  when `plugin/` is dirty.
- New README prose stays **outside `### Image cache (companion app)`** (currently `README.md:427-534`,
  byte-gated by `tests/unit/companion/test_image_cache_docs.py`), and any prose added inside
  `## The companion app` (201-380) must leave `tests/unit/companion/test_companion_docs.py` green.
- Anything under `plugin/` changes only by re-running `scripts.build_plugin`.

**Block If:**
- `uv run --directory plugin/server artificial-planeswalker companion` does not actually serve the
  SPA from the plugin tree. That is a defect in the distribution this story only documents, and
  choosing between fixing the packaging, documenting a different launch route, or deferring the AC is
  not a decision to take unattended. HALT with the observed failure.

**Never:**
- Do not hand-edit either copy of the bundle (`src/companion/app/static/**`,
  `plugin/server/src/companion/app/static/**`) — the whole point of this story is that they are
  generated.
- Do not touch `ui/**`. The bundle is a fixed input here; no Node work belongs to this story.
- Do not edit `.mcp.json` or `plugin/.mcp.json`. AC 3 is a verification, and
  `tests/integration/mcp_server/test_entry_point.py::TestMcpJsonNeedsNoChange` already pins both.
- Do not change *what* the build ships — `SKILLS`, `SERVER_FILES`, the manifests. Parity is proven,
  not redesigned.
- Do not cut a release, date a heading or bump `pyproject.toml:3`. Story 15.6 is the gate; 15-4 ruled
  the cut a separate act and this story follows it.

## I/O & Edge-Case Matrix

The "input" is the state of the repository the build reads; the output is the tree a plugin user
installs.

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Clean build | Repo with the committed bundle | `server/src/companion/app/static/` in the built tree holds exactly the same relative paths as `src/companion/app/static/`, byte for byte — `index.html`, `favicon.svg` and every file under `assets/` | Exit 0 |
| Bundle lost in the copy | `index.html` absent from the copied server | Build returns `1` and logs the `cd ui && npm run build` hint | Clean exit 1, never a traceback |
| Assets lost in the copy | `assets/` absent or empty in the copied server | Build returns `1` and names the directory | Clean exit 1 |
| Skills copy | `.claude/skills/` holds the four product skills *and* the `bmad-*` dev skills on disk | Built `skills/` holds exactly the four product skills; no `bmad-*` directory anywhere in the built tree | Missing product skill aborts with exit 1 (existing) |
| Serving the mirror | The built tree's bundle directory | `install_spa(app, static_dir=<built bundle>)` answers `GET /` with the index document and `GET /assets/<hashed>.js` with a JavaScript media type | A missing/empty bundle raises `RuntimeError` at construction (existing) |
| Committed pair | The repo exactly as committed | `plugin/server/src/companion/app/static/` equals `src/companion/app/static/` byte for byte | Red the moment either copy is hand-edited |
| Drift check subject | Mirrored bundle untracked or newly gitignored | CI's plugin step fails with a named error rather than passing on an empty subject | Exit 1 with `::error::` |
| No toolchain in the tree | The built tree | No `package.json`, no `node_modules`, no `ui/` — the UI is present only as the built bundle | N/A |

</intent-contract>

## Code Map

**The build and what it already guarantees**

- `scripts/build_plugin.py` — the assembler. `:47` `REPO_ROOT`; `:50-55` `SKILLS`, the four product
  skills, with the "`bmad-*` skills are repo dev-tooling" rule in the comment; `:62` `SERVER_FILES`
  (`pyproject.toml`, `uv.lock`, `README.md`, `LICENSE`, `NOTICE` — **not** `CHANGELOG.md`);
  `:65` `IGNORE`.
  - `:187-193` step 2 copies `src/` wholesale, then the `src/viewer/` presence check (f567062).
  - **`:194-216` — the two guards this story mechanises.** `spa_index` missing → `return 1`;
    `spa_assets` absent or empty → `return 1`. The comment at `:194-198` names "c8-5" — this story's
    older number — as the acceptance they exist for. Neither is exercised by any test today.
  - `:225-233` step 3 copies each named skill; a missing `SKILL.md` aborts. Nothing bounds the set
    from above.
- `.pre-commit-config.yaml:32-39` — `build-plugin-sync`. Its `files:` regex starts `^(src/`, so a
  bundle-only change *does* trigger a rebuild — the local half is sound. It is not installed on this
  machine (see the Always rule).
- `.github/workflows/ci.yml:86` — the `Plugin tree in sync with src/` step: rebuild, then fail on
  `git status --porcelain -- plugin/`. **Compare with `:164`** (the SPA check) and `:204`
  (the generated-types check): both open with a `git ls-files` non-vacuity guard and an `::error::`
  explaining that porcelain reports nothing for an ignored or never-committed path. The plugin step,
  the oldest of the three, has no such guard. `.gitignore` carries unanchored `dist/`, `build/`,
  `lib/`, `var/`, `wheels/` patterns, which is the risk those guards were written against.

**The two copies**

- `src/companion/app/static/` — 5 tracked files: `index.html`, `favicon.svg`,
  `assets/index-DJ7dGud2.js`, `assets/index-DTc6yXI-.css`,
  `assets/space-grotesk-latin-wght-normal-BhU9QXUp.woff2`. 296 KB.
- `plugin/server/src/companion/app/static/` — the same 5, tracked, and **currently identical**
  (`diff -r` clean, measured 2026-08-19).
- `src/companion/app/spa.py:46-51` `STATIC_DIR = Path(__file__).parent / "static"` — package-relative,
  which is *why* the cloned plugin tree serves its own copy. `:1-7` the quotable line: the bundle is
  "generated output, committed to the repository… Nothing here builds anything".
  `:374-417` `install_spa(app, *, static_dir: Path | None = None)` — the override exists for tests;
  `tests/unit/companion/test_spa.py:507-539` is the idiom to copy for driving a bundle directory that
  is not the package's own.

**Tests — where the new guards go**

- `tests/integration/test_build_plugin.py` (199 lines) — the plugin's guard home, and **unmarked**, so
  it runs inside CI's `-m "not integration"` gate. `:31-96` the clean-build assertions (viewer,
  `SERVER_FILES`, the declared readme, per-skill `SKILL.md`, both clients' manifests);
  `:120-128` the `SERVER_FILES` abort test, monkeypatching `build_plugin.SERVER_FILES` — the
  fault-injection idiom already established here; `:130-134` the `IGNORE` matcher test.
  A `build()` copies ~1.8 MB, so new read-only assertions share one module-scoped built tree rather
  than rebuilding per test.
- `tests/integration/mcp_server/test_entry_point.py:328-366` `TestMcpJsonNeedsNoChange` — AC 3 in
  full: both files' `command`/`args`, plus a parametrised test that neither ends in a subcommand
  form. **`git diff v0.4.0 HEAD -- .mcp.json plugin/.mcp.json` is empty** (measured 2026-08-19);
  `v0.4.0` (2026-07-18) predates the companion epics. AC 3 needs recording, not code.

**The documents**

- `docs/plugin-structure.md` (189 lines) — the plugin's design record, companion-blind.
  `:17-30` the "What goes in the plugin" table (server + four skills, no bundle);
  `:32-72` the layout tree, whose `server/src/` listing ends `viewer/`, `paths.py` — no `companion/`;
  `:140-152` "Runtime constraints that packaging can't solve" (three numbered items, none about the
  UI); `:154-178` "Building it"; `:180-189` "How a user installs it", the two-command install, which
  says nothing about the companion.
- `CONTRIBUTING.md` (83 lines) — headings at `:7` Getting set up, `:27` Quality gates, `:43` Code
  conventions, `:56` Architecture in brief (`data → logic → mcp_server`), `:68` Tests, `:74` Pull
  requests. No mention of `plugin/`, `ui/`, or any generated artifact. This is the file with no home
  for "generated, never hand-edited" — and the three artifacts that need it are all already gated:
  `src/companion/app/static/` (`ci.yml:164`), `plugin/` (`ci.yml:86`), and
  `ui/src/api/types.d.ts` + `openapi.json` (`ci.yml:204`).
- `README.md` — `:89-98` `## Connect your client`; `:93-111` the Claude Code `<details>` block with
  the two install commands and the `initialize_database` follow-up; `:201` `## The companion app`,
  `:212` `### Launch it` (the plain `uv run artificial-planeswalker companion`), `:427-534` the
  byte-gated image-cache section.
- `tests/unit/companion/test_companion_docs.py:597-629` — derives the documented command from
  `pyproject [project].scripts` plus the dispatcher's usage text and asserts it appears in the
  section **and** as a whole line inside a fence. It asserts nothing about *how many* commands the
  section carries, so a `--directory`-anchored variant is safe — but it must not displace the plain
  command's own fenced line.
- `src/mcp_server/__main__.py:7-10` — the three invocation forms, `:44-58` `_USAGE`. `plugin/.mcp.json`
  anchors with `uv run --directory ${CLAUDE_PLUGIN_ROOT}/server python -m src.mcp_server`; the
  documented plugin launch is that same anchor with the console script and the `companion` subcommand.
- Claude Code installs a plugin into a **version-keyed cache**
  (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, verified on this machine, holding a
  stale `0.3.0`). The path is machine- and version-specific, so the README names the anchor
  (`<plugin root>/server`, the same directory `${CLAUDE_PLUGIN_ROOT}/server` resolves to) rather than
  a literal path.

**Read-only evidence**

- No test reads `docs/plugin-structure.md` or `CONTRIBUTING.md` — both are unguarded prose today.
- `CONTRIBUTING.md` is not in `SERVER_FILES`, so editing it needs no plugin rebuild. `README.md` is.
- Root markdown is outside Prettier's scope (it runs with `working-directory: ui`; there is no root
  `.prettierrc`), so no formatter will re-wrap these edits.
- Tool count: `test_build_plugin.py:150-172` pins exactly 21 tool names, and both places
  `docs/plugin-structure.md` says "21 tools" are correct — leave them.

## Tasks & Acceptance

**Execution:**

- [x] `tests/integration/test_build_plugin.py` -- add a module-scoped fixture that builds the plugin
      once into a temp directory, and over it assert: (a) the mirrored bundle has the **same set of
      relative paths** as `src/companion/app/static/` and every file is byte-identical; (b) the built
      `skills/` directory contains **exactly** `set(SKILLS)` and no `bmad-*` entry appears anywhere in
      the built tree; (c) the tree carries no `package.json`, no `node_modules` and no `ui/`
      directory -- AC 1, AC 5 and the "no Node toolchain" half of AC 4, none of which any assertion
      covers today.
- [x] `tests/integration/test_build_plugin.py` -- add two fault-injection tests for the abort paths at
      `build_plugin.py:194-216`: a copy that lands without `index.html`, and one whose `assets/` is
      empty, each expected to return `1`. Inject by wrapping `build_plugin.shutil.copytree` so the
      real copy runs and the bundle is removed afterwards -- the guards the story's acceptance leans
      on have never been fired.
- [x] `tests/integration/test_build_plugin.py` -- assert the **committed** pair is identical:
      `plugin/server/src/companion/app/static/` equals `src/companion/app/static/`, path set and
      bytes -- AC 2's hand-edit is caught locally instead of only by CI's rebuild-and-diff.
- [x] `tests/integration/test_build_plugin.py` -- serve the built mirror through the real SPA mount:
      `install_spa(FastAPI(), static_dir=<built bundle>)`, then `GET /` returns the index document and
      `GET /assets/<the hashed .js>` returns it with a JavaScript media type (httpx `ASGITransport`,
      as the companion suite does) -- "the app serves and renders" (AC 4), proven on the copy a plugin
      user gets rather than on the package's own.
- [x] `.github/workflows/ci.yml` -- give the `Plugin tree in sync with src/` step the non-vacuity
      guard its two siblings have: fail with an `::error::` when
      `git ls-files -- plugin/server/src/companion/app/static/` is empty, before the rebuild -- AC 1
      says the existing drift check *covers* the mirrored copy, and a check that reports nothing for
      an ignored path covers nothing.
- [x] `docs/plugin-structure.md` -- write the companion into the design record: a bundle row in the
      "What goes in the plugin" table sourced from `src/companion/app/static/`; `companion/` (with
      `app/static/` marked as the committed, generated bundle) in the layout tree; a fourth runtime
      constraint stating the bundle ships pre-built so no Node toolchain is needed at install or
      runtime; and a line in "How a user installs it" giving the plugin-anchored companion launch.
      State plainly that both copies are generated and never hand-edited.
- [x] `CONTRIBUTING.md` -- add a short **Generated artifacts** section: the three drift-checked
      artifacts (`src/companion/app/static/`, `plugin/`, `ui/src/api/types.d.ts` + `openapi.json`),
      what regenerates each, and the rule that none of them is ever hand-edited -- the rule AC 2
      states currently has no home a contributor would read.
- [x] `README.md` -- in the Claude Code plugin `<details>` block, add that the plugin ships the
      companion too and give the plugin-anchored launch
      (`uv run --directory <plugin root>/server artificial-planeswalker companion`), linking to
      `## The companion app`; note the same anchor in `### Launch it` for readers who arrive there
      first. Keep the plain command's fenced line intact -- the plugin path is the one install route
      whose reader cannot use the repo-clone command.
- [x] `plugin/server/**` -- regenerate with `uv run python -m scripts.build_plugin` and commit --
      mandatory after the `README.md` edit; the sync hook does not run on commit on this machine.

**Acceptance Criteria:**

- Given a fresh `build()`, when the built tree is compared with the repository, then the mirrored SPA
  bundle matches `src/companion/app/static/` path-for-path and byte-for-byte, and the built `skills/`
  directory is exactly the four product skills with no `bmad-*` anywhere in the tree.
- Given the committed tree, when the two bundle copies are compared, then they are identical — and a
  hand-edit to either one turns a test red without waiting for CI.
- Given the mirrored bundle, when it is mounted through `install_spa` and driven, then `/` returns the
  index document and the hashed asset returns with a JavaScript media type — the plugin's copy serves.
- Given `.mcp.json` and `plugin/.mcp.json`, when they are compared against the pre-companion release
  `v0.4.0`, then neither has changed and both still invoke `python -m src.mcp_server` directly, with
  `TestMcpJsonNeedsNoChange` standing as the guard. Evidence is recorded; neither file is edited.
- Given the mirrored bundle became untracked or gitignored, when CI runs, then the plugin drift check
  fails with a named error instead of passing on an empty subject.
- Given someone who installed via the plugin, when they read the README or `docs/plugin-structure.md`,
  then they learn the plugin carries the companion, how to launch it against the installed plugin
  root, and that no Node toolchain is involved.
- Given a contributor, when they read `CONTRIBUTING.md`, then they are told which artifacts are
  generated, what regenerates them, and that none is hand-edited.
- Given the edited tree, when the gates run, then the full suite is green with no regression against
  the baseline count, each new guard has a `probe_harness` firing proof recorded, and
  `git status --porcelain -- plugin/` is empty after a rebuild.

## Spec Change Log

## Review Triage Log

### 2026-08-19 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 22: (high 0, medium 7, low 15)
- defer: 2: (high 0, medium 1, low 1)
- reject: 7: (high 0, medium 0, low 7)
- addressed_findings:
  - `[medium]` `[patch]` The CI non-vacuity guard was directory-wide, so a newly-ignored `assets/`
    passed while `index.html` stayed tracked — the exact case its own comment argued. Split into
    two subjects, the lesson the generated-types check learned in the c2-3 review, plus a third
    executable test for the partially-tracked repo.
  - `[medium]` `[patch]` The committed `plugin/` tree was never compared as a path set against a
    fresh build; `build()` cleans only four managed paths, so a stale file under `plugin/server/`
    would survive rebuild-and-diff forever. Added `TestTheCommittedTreeIsExactlyWhatTheBuildEmits`,
    keyed on `git ls-files` so gitignored runtime cruft is excluded by construction.
  - `[medium]` `[patch]` Both abort-path tests asserted only `build(...) == 1`, a status six abort
    paths share, so neither could tell which guard fired. Pinned the logged hint with `caplog`.
  - `[medium]` `[patch]` The story's own new prose was the one thing in it nothing could see go
    wrong. Added `TestThePluginInstallRouteIsDocumented`: the anchored command derived from
    `[project.scripts]` + the dispatcher's usage text, and the design record's README deep link
    checked against the README's actual headings.
  - `[medium]` `[patch]` README's "everything else on this page applies unchanged" was false — every
    later example is the bare command and needs the anchor. Reworded, with the `--port` case shown.
  - `[medium]` `[patch]` `<plugin root>` inside a bash fence is a redirect syntax error on paste and
    the docs never said how to find it. Both fences now assign `PLUGIN_ROOT` and carry a discovery
    line (verified against this machine's install layout).
  - `[medium]` `[patch]` The first-run cost of the anchored launch (a virtualenv and the server's
    dependencies, inside the client's version-keyed cache, repeated on every plugin update) was
    undocumented despite appearing in this story's own verification transcript.
  - `[low]` `[patch]` No Windows form of the anchored launch, in a README that carries PowerShell
    variants elsewhere. Added, without inventing an unverified cache path.
  - `[low]` `[patch]` The Codex plugin route — the same tree, the same `server/` — was never told
    the companion ships to it. Added to the README block and to the design record's launch section.
  - `[low]` `[patch]` CONTRIBUTING's rebuild-trigger column omitted `uv.lock` and
    `scripts/build_plugin.py`, both in the sync hook's `files:` regex.
  - `[low]` `[patch]` README's Development block and CONTRIBUTING's new section listed different
    numbers of generated artifacts with no link between them. Added the pointer.
  - `[low]` `[patch]` `scripts/build_plugin.py` still called this story "c8-5"; it now names 15-5
    and the test class that fires its guards.
  - `[low]` `[patch]` `_tree` did not filter names `IGNORE` drops, so a stray `.DS_Store` would have
    turned the byte-parity tests red for a file the build correctly omits.
  - `[low]` `[patch]` `_BUNDLE_RELATIVE` mixed a resolved `REPO_ROOT` with an unresolved
    `STATIC_DIR`; under a symlinked checkout that raises at import and takes the module down at
    collection. Both sides resolved.
  - `[low]` `[patch]` The hashed-script lookup unpacked a glob and would have failed opaquely under
    code splitting; now asserted, then taken.
  - `[low]` `[patch]` The empty-assets plant unlinked children and would have raised
    `IsADirectoryError` on a nested Vite output directory.
  - `[low]` `[patch]` `_drift_step_script` searched to end of file and could have read a later
    step's script; bounded to the next step, with the rebuild command asserted to appear once.
  - `[low]` `[patch]` The bash tests skipped on missing `bash` but not on missing `git`, and had no
    subprocess timeouts.
  - `[low]` `[patch]` The `bmad-*` leak check was case-sensitive.
  - `[low]` `[patch]` The Node-artifact check was narrower than the sentence the design record now
    asserts; extended to lockfiles, `vite.config.ts`, `tsconfig.json` and `.nvmrc`.
  - `[low]` `[patch]` The `copytree` wrapper took `dst` positionally only and patched the stdlib
    module object process-wide with no note of the blast radius.
  - `[low]` `[patch]` The new helpers deviated from the repo's full-type-hints convention.

## Design Notes

**Why a serving proof instead of a browser.** AC 4 says the app "serves and renders" after a plugin
install on a clean machine. No test here can produce a clean machine, and a browser check would need
the toolchain the AC is about not needing. What *can* be proven hermetically is the thing that
actually differs between the two copies: whether the bytes a plugin user receives are the bytes the
app serves. `install_spa`'s `static_dir` override was built for exactly this, so the test drives the
mirrored directory through the real mount — the same subclassing, the same media-type registration —
and the residue (a real browser, a real clean machine) is a recorded manual check, not a silent gap.

**Why the vacuity guard, when the mirror is tracked today.** CI's other two drift checks each carry a
`git ls-files` preamble because `git status --porcelain` is silent about paths git is not watching, so
a drift check whose subject vanished passes loudest of all. The plugin step predates that lesson.
`.gitignore`'s unanchored `dist/`, `build/` and `lib/` are the concrete route: a future Vite output
directory under the bundle would be ignored in *both* copies at once, and the mirror check would then
certify a plugin with no UI. Three checks, one shape.

**The documents are the deliverable, not decoration.** AC 2 ("treated as generated artifacts and
neither is hand-edited") is a rule about human behaviour, and a rule with no written home is enforced
only by whoever remembers it. `CONTRIBUTING.md` is where a contributor looks; `docs/plugin-structure.md`
is where the next person to touch the build looks; the README's plugin block is where the person who
cannot run the repo-clone command looks. Each edit puts one claim where its reader already is.

**What this story deliberately does not do.** It changes nothing about *what* the build ships: no new
`SERVER_FILES`, no `SKILLS` edit, no manifest change. Both `.mcp.json` files stay byte-identical to
their pre-companion selves, which is the acceptance, and their existing guard is cited rather than
duplicated. And no release is cut — 15.6 is the gate.

## Verification

**Commands:**
- `uv run pytest tests/integration/test_build_plugin.py -q` -- expected: green, including the new
  guards. Fast inner loop.
- `uv run pytest tests/unit/companion/test_companion_docs.py tests/unit/companion/test_image_cache_docs.py -q`
  -- expected: green after every `README.md` edit; these two own the sections either side of the new
  prose.
- `uv run python -m scripts.build_plugin && git status --porcelain -- plugin/` -- expected: no output
  after the README edit is committed with its regenerated mirror.
- `uv run python -m scripts.probe_harness --expect-red '<node id>'` -- one run per new guard, each
  against a planted violation, with the tree staged first and reverted via
  `git diff --exit-code <file>`. Paste each proof line into the Verification Record.
- `uv run python -m scripts.probe_harness --expect-green` -- expected: the full suite green, with the
  collected count compared against the baseline recorded before any edit.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` -- expected: clean.

**Manual checks (if no CLI):**
- Run `uv run --directory plugin/server artificial-planeswalker companion --port <free port>` against
  the committed plugin tree, fetch `/` and `/health`, confirm the index document and the hashed asset
  come back, then stop it. Record the launch line and the fetched status codes verbatim in the
  Verification Record — this is the evidence behind the README's plugin-anchored command, and it must
  be run before that command is written down. If it fails, HALT per **Block If**.
- Confirm no companion is already running before that check (a second launch exits `0` with an
  "already running" line, which would look like success and prove nothing).

## Verification Record (2026-08-19)

**Block If — cleared before anything was written down.** No companion was running (no
`companion.json` in the data dir, no matching process) and the launch was made against the
**committed** `plugin/server/` tree, which `uv` built into its own `.venv` from scratch:

```
$ uv run --directory plugin/server artificial-planeswalker companion --port 8791
[planeswalker] companion running at http://127.0.0.1:8791 — open this URL in your browser (Ctrl-C to stop)

  (stderr) Creating virtual environment at: .venv
           Building artificial-planeswalker @ file:///…/Artificial-Planeswalker/plugin/server
           Installed 80 packages in 118ms
           INFO src.companion.app.main: Published discovery file …/companion.json for port 8791
           INFO:     Application startup complete.

$ curl  http://127.0.0.1:8791/health                       status=200 content-type=application/json
$ curl  http://127.0.0.1:8791/                             status=200 content-type=text/html; charset=utf-8      size=1916
$ curl  http://127.0.0.1:8791/assets/index-DJ7dGud2.js      status=200 content-type=text/javascript; charset=utf-8 size=238962

$ cmp <served /> plugin/server/src/companion/app/static/index.html                    → identical
$ cmp <served asset> plugin/server/src/companion/app/static/assets/index-DJ7dGud2.js  → identical
```

Ctrl-C stopped it; `plugin/` stayed clean afterwards (the `.venv` and `*.egg-info` are gitignored).
This is the evidence behind the README's and `docs/plugin-structure.md`'s plugin-anchored command,
run **before** either was written. The documented form drops `--port` (the default 8765 applies) and
names `<plugin root>/server` rather than a literal path, because Claude Code installs into a
version-keyed cache directory that is machine- and version-specific.

**AC 3 — recorded, not edited.** `git diff v0.4.0 HEAD -- .mcp.json plugin/.mcp.json` is **empty**
(`v0.4.0` = `5835c45`, 2026-07-18, which predates the companion epics), and
`git status --porcelain -- .mcp.json plugin/.mcp.json` is empty in the working tree, so this story
touched neither. `tests/integration/mcp_server/test_entry_point.py::TestMcpJsonNeedsNoChange` stands
as the guard; nothing was duplicated.

**Counts.** `scripts.probe_harness` owns its argv and runs `-m "not integration"`: **3155 → 3163**,
+8, exactly the eight tests added. Baseline measured before the first edit.

**Firing proofs** — every run is the full suite via `uv run python -m scripts.probe_harness
--expect-red`, tree staged before each plant, each revert verified with `git diff --exit-code`:

```
green baseline (before any edit)   full suite (-m 'not integration'): 3155 collected, 0 failed, exit 0
green after the edits              full suite (-m 'not integration'): 3163 collected, 0 failed, exit 0

1 build_plugin IGNORE drops favicon.svg from the copy
                 full suite (-m 'not integration'): 3163 collected, 1 failed, 0 errored, exit 1
  RED    test_build_plugin.py::TestTheBuiltTreeCarriesTheCompanion::test_the_built_bundle_matches_the_source_bundle

2 a bmad-* skill (bmad-code-review) added to SKILLS
                 full suite (-m 'not integration'): 3163 collected, 2 failed, 0 errored, exit 1
  RED    test_build_plugin.py::TestTheBuiltTreeCarriesTheCompanion::test_the_built_skills_are_exactly_the_product_skills
  RED    test_build_plugin.py::TestTheBuiltTreeCarriesTheCompanion::test_no_bmad_skill_leaks_anywhere_into_the_built_tree

3 a ui/package.json planted under src/, so the verbatim copy carries it
                 full suite (-m 'not integration'): 3163 collected, 1 failed, 0 errored, exit 1
  RED    test_build_plugin.py::TestTheBuiltTreeCarriesTheCompanion::test_the_built_tree_carries_no_node_toolchain

4 the missing-index guard logs but no longer returns 1
                 full suite (-m 'not integration'): 3163 collected, 1 failed, 0 errored, exit 1
  RED    test_build_plugin.py::TestTheBundleGuardsFire::test_a_copy_that_lost_the_index_aborts_cleanly

5 the empty-assets guard logs but no longer returns 1
                 full suite (-m 'not integration'): 3163 collected, 1 failed, 0 errored, exit 1
  RED    test_build_plugin.py::TestTheBundleGuardsFire::test_a_copy_whose_assets_are_empty_aborts_cleanly

6 plugin/'s mirrored favicon.svg hand-edited
                 full suite (-m 'not integration'): 3163 collected, 1 failed, 0 errored, exit 1
  RED    test_build_plugin.py::TestTheCommittedPairIsIdentical::test_the_committed_mirror_matches_the_committed_source

7 spa.py reserves /assets, so the mount declines the hashed script
                 full suite (-m 'not integration'): 3163 collected, 7 failed, 0 errored, exit 1
  RED    test_build_plugin.py::TestTheMirroredBundleServes::test_the_built_bundle_serves_its_index_and_its_hashed_script
  (+ 6 pre-existing test_spa.py guards on the same mount — the plant is deliberately upstream of
   both, and the new node id is the one being proved)
```

**Two plants were wrong before they were right, and both corrections are the story's own findings.**

*The skills set was tautological.* The first plant — `bmad-code-review` appended to `SKILLS` — reddened
only `test_no_bmad_skill_leaks_anywhere_into_the_built_tree`. The exclusivity test compared the built
directory against `set(SKILLS)`, the same constant the build reads, so a **widened** `SKILLS` stays
correct against itself; only a build that *diverged* from `SKILLS` could ever fail it. Fixed by naming
the four product skills literally in the test and asserting `set(SKILLS)` equals that literal, exactly
as the tool surface is named once in `test_server_registers_expected_tools`. Shipping a fifth skill now
has to edit a test that says so. `SKILLS` itself was not touched (see the spec's **Never**).

*The `.js` media type is not independently firable on macOS.* Deleting `(".js", "text/javascript")`
from `spa.py`'s `_MEDIA_TYPES` left the full suite **green** — Python's stdlib `mimetypes` already maps
`.js` to `text/javascript` on this platform, so the registration is belt-and-braces here and only bites
where the Windows registry has been rewritten (which is the documented reason it exists). The
`content-type` assertion is kept because it is AC 4's wording and the registry risk is real, but its
firing proof comes from a plant on the serving path itself (`_RESERVED_SEED`), and the honest statement
is: **on macOS that one assertion cannot be made to fail by removing the registration.**

**CI's vacuity guard, both branches exercised locally** (the step itself only runs on GitHub):

```
$ git ls-files -- plugin/server/src/companion/app/static/
  plugin/server/src/companion/app/static/assets/index-DJ7dGud2.js
  plugin/server/src/companion/app/static/assets/index-DTc6yXI-.css
  plugin/server/src/companion/app/static/assets/space-grotesk-latin-wght-normal-BhU9QXUp.woff2
  plugin/server/src/companion/app/static/favicon.svg
  plugin/server/src/companion/app/static/index.html
  → non-empty, guard passes

$ git ls-files -- plugin/server/src/companion/app/nowhere/
  → empty, guard fires (the untracked/gitignored case)
```

The workflow file was re-parsed as YAML and the step's `run:` block read back, so the added preamble
is really in the script the runner executes. It is placed **before** the rebuild, so a vanished subject
names itself instead of producing an empty diff.

**Remaining gates.** `uv run pytest tests/integration/test_build_plugin.py -q` → 14 passed.
`uv run pytest tests/unit/companion/test_companion_docs.py tests/unit/companion/test_image_cache_docs.py -q`
→ 33 passed, run after every `README.md` edit. `uv run ruff check . && uv run ruff format --check . &&
uv run mypy src/` → clean (335 files formatted, 94 source files typed).
`uv run python -m scripts.build_plugin` then `git diff --name-only -- plugin/` → **no output**: the
regenerated mirror equals the committed one, with `plugin/server/README.md` carrying the README edit.

**Residue, declared.** No test here can produce a clean machine or a real browser, so "the app renders
after a plugin install" remains covered by the manual check above (real `uv` build of the committed
plugin tree, real HTTP, byte-compared responses) plus the hermetic mount test — not by a browser. The
`--port 8791` used in that check is not the documented form; the default-port path is unchanged and is
covered by `test_companion_docs.py`. Story 15.6 is the release gate; no version was bumped, no heading
dated, and `CHANGELOG.md` was not touched.

## Verification Record — addendum (2026-08-19, matrix audit)

**Matrix row 7 had no covering test.** The CI vacuity guard was verified by running both
`git ls-files` branches by hand and re-parsing the workflow — evidence, but not a test that runs in
the suite, and the row's stated behaviour ("CI fails with a named error rather than passing on an
empty subject") was therefore unguarded. Closed with
`TestTheDriftCheckCannotPassOnNothing` in `tests/integration/test_build_plugin.py`, which reads the
step's `run:` block **out of `.github/workflows/ci.yml`** and then executes its preamble:

- `test_the_guard_names_the_mirrored_bundle_and_runs_before_the_rebuild` — the subject is derived
  from `_MIRRORED_BUNDLE`, and the guard is asserted to sit above the rebuild command.
- `test_the_guard_fails_where_the_mirrored_bundle_is_not_tracked` — the preamble is run under
  `bash` in a freshly `git init`-ed empty repository, where the subject is untracked; expects a
  non-zero exit carrying `::error::`. This is the GitHub-only branch, fired locally.
- `test_the_guard_passes_on_this_repository` — the same preamble against this checkout, so the
  failure above is attributable to the missing subject rather than to a script that cannot run.

The workflow is parsed as **text, not YAML**: the only YAML reader available here arrives
transitively via `uvicorn[standard]`, and the repo's own rule (the reason `websockets` is a declared
dev dependency) is that a committed tool must not lean on another package's extra. Both bash tests
skip where `bash` is absent; on this machine both ran.

`_BUNDLE_RELATIVE` now derives from the shipped `spa.STATIC_DIR` instead of transcribing
`companion/app/static`, so a move of the bundle inside the package moves the whole module's pins
with it.

**Firing proofs** — full suite, tree staged before each plant, each revert verified with
`git diff --exit-code .github/workflows/ci.yml`:

```
1 the guard's `exit 1` weakened to `exit 0` (it reports and continues)
                 full suite (-m 'not integration'): 3166 collected, 1 failed, 0 errored, exit 1
  RED    test_build_plugin.py::TestTheDriftCheckCannotPassOnNothing::test_the_guard_fails_where_the_mirrored_bundle_is_not_tracked

2 the guard's subject mistyped (`.../app/statix/`), i.e. it watches a path nothing writes
                 full suite (-m 'not integration'): 3166 collected, 2 failed, 0 errored, exit 1
  RED    test_build_plugin.py::TestTheDriftCheckCannotPassOnNothing::test_the_guard_names_the_mirrored_bundle_and_runs_before_the_rebuild
  RED    test_build_plugin.py::TestTheDriftCheckCannotPassOnNothing::test_the_guard_passes_on_this_repository

green after the addendum   full suite (-m 'not integration'): 3166 collected, 0 failed, exit 0
```

**Counts.** 3155 → 3163 (the implementation) → **3166** (+3 here). `ruff check`, `ruff format
--check` and `mypy src/` clean; `uv run python -m scripts.build_plugin` leaves `plugin/` with no
unstaged change.

**Every matrix row now has a covering test that ran and passed:** rows 1/4/8
`TestTheBuiltTreeCarriesTheCompanion`, rows 2-3 `TestTheBundleGuardsFire`, row 5
`TestTheMirroredBundleServes`, row 6 `TestTheCommittedPairIsIdentical`, row 7
`TestTheDriftCheckCannotPassOnNothing`.

## Verification Record — addendum (2026-08-19, review pass)

The review's 22 patch findings were applied; the implementation agent was interrupted immediately
before its firing proofs, so every proof below was run here, after re-reading the patched tree.

**Renames to keep the record readable.** The guard test named
`test_the_guard_names_the_mirrored_bundle_and_runs_before_the_rebuild` in the matrix-audit addendum
above is now `test_the_guard_names_every_subject_and_runs_before_the_rebuild`; the earlier proof
lines are historical and were true of the name at the time.

**Firing proofs** — every run is the full suite via `scripts.probe_harness`, tree staged before each
plant, each revert confirmed with `git diff --exit-code` (and, for the tracked-stray plant, with
`git status --porcelain -- plugin/`):

```
1 the CI guard reverted to one directory-wide subject
                 full suite (-m 'not integration'): 3171 collected, 2 failed, 0 errored, exit 1
  RED    TestTheDriftCheckCannotPassOnNothing::test_the_guard_names_every_subject_and_runs_before_the_rebuild
  RED    TestTheDriftCheckCannotPassOnNothing::test_the_guard_fails_where_only_the_assets_slipped_out_of_tracking

2 a tracked stray committed under plugin/server/ (a file no build emits)
                 full suite (-m 'not integration'): 3171 collected, 1 failed, 0 errored, exit 1
  RED    TestTheCommittedTreeIsExactlyWhatTheBuildEmits::test_the_tracked_plugin_files_are_exactly_the_built_ones

3 the missing-index abort no longer names the rebuild command
                 full suite (-m 'not integration'): 3171 collected, 1 failed, 0 errored, exit 1
  RED    TestTheBundleGuardsFire::test_a_copy_that_lost_the_index_aborts_cleanly

4 README anchors the launch at the plugin root instead of its server/ directory
                 full suite (-m 'not integration'): 3171 collected, 1 failed, 0 errored, exit 1
  RED    TestThePluginInstallRouteIsDocumented::test_the_anchored_launch_command_is_the_installed_console_script[README.md]

5 the design record's README deep link points at no heading
                 full suite (-m 'not integration'): 3171 collected, 1 failed, 0 errored, exit 1
  RED    TestThePluginInstallRouteIsDocumented::test_the_design_records_deep_link_into_the_readme_still_resolves

green after the patch set   full suite (-m 'not integration'): 3171 collected, 0 failed, exit 0
```

Proof 1 is the one that mattered: the new partially-tracked test is **red against the guard as this
story first shipped it** and green against the per-subject one, so the fix is demonstrated rather
than asserted.

**Counts.** 3155 (baseline) → 3163 (implementation) → 3166 (matrix audit) → **3171** (review patch
set, +5). `uv run pytest tests/unit/companion/test_companion_docs.py
tests/unit/companion/test_image_cache_docs.py -q` → 33 passed after the README edits. `ruff check`,
`ruff format --check`, `mypy src/` → clean. `uv run python -m scripts.build_plugin` then
`git status --porcelain -- plugin/` → only the staged `plugin/server/README.md`, i.e. no new drift.

**The discovery lines are checked, not composed.** `ls -d ~/.claude/plugins/cache/*/artificial-planeswalker/*/`
matches this machine's install, whose root holds `server/`, `skills/` and `codex-mcp.json` — the
anchor the documented command uses. No literal path is presented as canonical.

## Auto Run Result

Status: done
Blocking condition: none

**What was implemented.** Story 15.5 asked whether the plugin — the install route that has to carry
the companion's UI — actually arrives complete. Four of its five acceptance criteria were already
true and unproven, so the work is mechanisation and documentation rather than behaviour change: the
plugin build, `.mcp.json` and every shipped byte except `README.md` are untouched.

**Files changed**

- `tests/integration/test_build_plugin.py` — 19 new tests across six classes: the built tree carries
  the bundle byte-for-byte and exactly the four product skills with no `bmad-*` and no Node
  artefacts; both never-fired SPA abort paths, now pinned by their logged hint; the committed pair
  byte-identical; the committed `plugin/` tree exactly what a fresh build emits; the mirrored bundle
  served through the real `install_spa` mount; the documented plugin-anchored launch derived from
  the console script; and the CI drift step's own preamble, executed against three repositories.
- `.github/workflows/ci.yml` — the plugin drift check gains the non-vacuity preamble its two younger
  siblings carry, per subject (`index.html` and `assets/`) rather than over the bundle directory.
- `docs/plugin-structure.md` — the companion written into the design record: bundle row, layout
  tree, a fourth runtime constraint, the generated-and-never-hand-edited rule, and the anchored
  launch for both clients.
- `CONTRIBUTING.md` — a Generated artifacts section: the three drift-checked artifacts, what
  regenerates each, and the rule that none is hand-edited.
- `README.md` — the plugin install routes (Claude Code and Codex) now say the companion ships with
  them and give a runnable anchored launch with a discovery line, a PowerShell form, and the
  first-run cost; `### Launch it` says plainly that the flags are unchanged and the invocation is not.
- `plugin/server/README.md` — regenerated mirror of the README edit.
- `scripts/build_plugin.py` — comment only: the guard now names story 15-5 and the test that fires it.

**Review findings.** 22 patched (7 medium, 15 low), 2 deferred, 7 rejected; no intent gaps and no
spec deviations. Follow-up review recommended: **true** (0 high, 7 medium, 15 low → 3×7 + 15 = 36).

**Verification.** Full suite green at 3171 collected, 0 failed; 12 firing proofs in total across the
three passes, each a full-suite run against a planted violation with a confirmed revert; lint, format
and strict types clean; the plugin tree rebuilt with no drift; and the plugin-anchored launch command
executed against the committed tree before it was documented (`/`, `/health` and the hashed script
returned byte-identical to the committed files).

**Residual risks.** No test can produce a clean machine or a real browser, so "renders after a plugin
install" rests on the manual launch plus the hermetic mount test. The `text/javascript` assertion
cannot be made to fail on macOS, and the two Windows-facing rationales run only on ubuntu — deferred
with evidence. AC 3 is a point-in-time comparison against `v0.4.0` plus the standing content guard,
not a byte pin of the pre-companion files. `CHANGELOG.md` was not touched and no version was cut:
story 15.6 is the release gate.
