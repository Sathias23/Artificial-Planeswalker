---
title: 'Deprecate view_deck and freeze src/viewer'
type: 'chore'
created: '2026-08-17'
status: 'done'
baseline_revision: '999bacd713bdec0d1a8ca2f77f6bda9b597137d6'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-15-context.md'
warnings: ['oversized']
deferred:
  - summary: >-
      The README now deprecates `view_deck` in favour of a companion app it cannot yet tell a reader
      how to start, so between this story and Story 15.4 the docs point at a dead end.
    evidence: |-
      Blind Hunter, 2026-08-17, corroborated by the intent-alignment audit. `README.md:25` marks the
      tool "(deprecated — use the companion app)", while the same table still labels the companion
      "(in development)" and `grep -n companion README.md` returns only lines 25, 28 and 31 — no
      launch command, no prerequisites, no pointer to companion docs. Not fixable here: this story's
      intent assigns the companion README section, the `uv run artificial-planeswalker companion`
      launch string and the fresh-install narrative to Story 15.4, which is `backlog` in the same
      epic. Story 15.4 closes it.
    location: >-
      README.md:25
    severity: low
---

<intent-contract>

## Intent

**Problem:** `view_deck` and `src/viewer` are superseded by the companion app (AD-15), but nothing
says so. The tool's LLM-facing description reads as a first-class feature, `src/viewer` carries no
freeze marker, "the companion never reuses `template.html`" holds only by coincidence, and the
deferred removal is written down nowhere — so a future story can invest in a component that is on
its way out, and the removal can be quietly forgotten.

**Approach:** Say it in the two places that are read (the tool description, the `src/viewer` package
docstring), record the deferred removal in the CHANGELOG, and turn the two properties that are
currently coincidences into guards: a **freeze pin** enumerating `src/viewer`'s modules and public
surface, and a **no-reuse sweep** proving no companion source names `src/viewer` or `template.html`.
No behaviour changes anywhere.

## Boundaries & Constraints

**Always:**
- `view_deck` keeps rendering HTML exactly as it does today, through Phases 1 and 2 (SC-3). Only
  docstrings, comments and documentation change in shipped code — no statement, expression or
  signature under `src/viewer/`, `src/mcp_server/tools/view_deck.py` or `scripts/view_deck.py` moves.
- The deprecation must be visible in the **MCP-visible tool description** (what `list_tools()`
  returns), not only in a Python `__doc__` a client never sees, and it must **name the companion app**
  as the replacement.
- New guards follow the project's guard idiom: a non-vacuity anchor (an empty or mistyped scan path
  fails loudly), a firing half and a silent half proven on synthetic sources, and declared residue.
- New guards are firing-proven through `scripts/probe_harness` with a planted violation, and the
  harness proof line is pasted into this spec. Stage the tree before planting; revert with
  `git diff --exit-code <file>`.
- After editing anything under `src/`, rebuild and commit the plugin mirror — CI fails on a stale
  `plugin/` tree.

**Block If:**
- A guard cannot be made to go red on a planted violation through the full suite.
- Satisfying the freeze pin would require changing `src/viewer` behaviour rather than only recording
  its current surface.

**Never:**
- No new capability in `src/viewer` — this story does not fix, extend or refactor it.
- Do not remove `src/viewer`, `scripts/view_deck.py` or the `view_deck` tool; do not change its
  parameters, result shape, status tokens or rendered HTML.
- Do not write the companion README section, the launch command, the image-cache docs or the
  dependency/version-floor CHANGELOG entries — Story 15.4 owns those. This story adds only the
  deprecation/deferral lines and the one-row tool-table marker.
- Do not edit the built bundle under `src/companion/app/static/` or the `plugin/` tree by hand.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Tool description read | `build_server()` → `list_tools()` | The `view_deck` entry's description marks it deprecated and names the companion app | No error expected |
| Tool still works | `view_deck(deck_id=…)` on a seeded DB | Unchanged: `status="ok"`, `file_path` set, HTML written — existing tests pass untouched | Unchanged guards (`not_found`, `error`, `database_not_initialized`) |
| Freeze pin, clean tree | Today's `src/viewer` | No violations | No error expected |
| Freeze pin, new capability | A new module or new public function added under `src/viewer` | Fails, naming the unclassified module/symbol and citing AD-15 | Assertion message points at the freeze, not at a typo |
| No-reuse sweep, clean tree | Today's companion sources | No violations | No error expected |
| No-reuse sweep, violation | A companion source naming `template.html` or importing `src.viewer` | Fails, naming file + line + the AD-15 rule | Reported as a violation list, one per line |
| Scan path wrong/empty | Guard pointed at an empty directory | Raises rather than passing vacuously | Assertion names the path constant |

</intent-contract>

## Code Map

- `src/mcp_server/server.py:452-475` -- the registered `@mcp.tool()` `view_deck` wrapper. **Its
  docstring IS the MCP tool description** — verified: `list_tools()` returns the whole docstring
  verbatim, summary line first. The deprecation belongs on the **first line** so it survives any
  client-side truncation.
- `src/mcp_server/tools/view_deck.py` -- the helper (module docstring at :1-15, `ViewDeckResult`,
  `view_deck`). Behaviour frozen; module docstring gains the same pointer.
- `src/viewer/__init__.py` -- package docstring + `__all__` = `build_view_model`, `deck_viewer_path`,
  `present_deck`, `render_html`. The freeze notice lands here; the pin reads this surface.
- `src/viewer/render.py` (`render_html`), `src/viewer/present.py` (`deck_viewer_path`,
  `present_deck`), `src/viewer/view_model.py` (public: `parse_mana_pips`, `map_pips`,
  `classify_color`, `card_bucket`, `is_land`, `pick_art`, `build_view_model`),
  `src/viewer/template.html` -- the frozen surface the pin enumerates.
- `scripts/view_deck.py` -- the CLI composition root over `present_deck`; docstring pointer only.
- `tests/unit/companion/test_import_boundary.py` -- **the guard idiom to follow**: AST-parse never
  import, `Violation` dataclass with `path:line — symbol (rule)`, `collect_python_files` asserting a
  non-empty walk, synthetic `tmp_path` sources for the firing/silent halves, enumeration pins with
  "add it to X" messages. Reuse the shape, not the module.
- `ui/tests/read-only-glass.test.ts` -- the frontend twin of the same discipline (per-rule
  fires/silent anchors, declared residue). Read for tone; **this story adds no `ui/` source**.
- `tests/integration/mcp_server/test_view_deck_tool.py` -- existing behavioural coverage of the
  helper; must stay green **unedited** (that is AC-2's evidence). `test_server_builder.py` shows the
  no-DB `build_server()` + `list_tools()` pattern the description assertion needs.
- `CHANGELOG.md` -- Keep a Changelog format; newest section is `## [0.4.0] - 2026-07-18`. **There is
  no `[Unreleased]` section yet** — this story creates it.
- `README.md:25` -- the tool table row listing `view_deck`.
- `scripts/build_plugin.py` + `.github/workflows/ci.yml:83-92` -- the committed `plugin/` tree is a
  generated mirror of `src/`; CI fails if `git status --porcelain -- plugin/` is dirty after a
  rebuild. The pre-commit `build-plugin-sync` hook is **not reliably installed on this machine** —
  run the rebuild by hand.
- `scripts/probe_harness.py` -- owns its own argv; caller supplies only `--expect-red '<node id>'` /
  `--expect-green`.
- **Read-only evidence:** `grep -rn "template.html"` and `grep -rn "src\.viewer"` show **zero**
  references under `src/companion/`, `ui/` or `src/companion/app/static/` today — the no-reuse
  property holds now and the guard's job is to keep it holding.

## Tasks & Acceptance

**Execution:**
- `src/mcp_server/server.py` -- rewrite the `view_deck` docstring's first line as a deprecation
  notice naming the companion app as the replacement, and add one sentence that it keeps working for
  now; leave `Args:`/`Returns:` and the body untouched -- AC-1's surface is this string.
- `src/mcp_server/tools/view_deck.py` -- add the same deprecation pointer to the module docstring --
  a reader arriving at the helper sees the ruling too.
- `src/viewer/__init__.py` -- add a FROZEN notice to the package docstring: no new capability lands
  here, removal is scheduled for the next minor release once the companion is proven (AD-15) -- the
  freeze needs a marker where a future author will land.
- `scripts/view_deck.py` -- add the same pointer to the module docstring -- the second composition
  root over the frozen package.
- `CHANGELOG.md` -- add an `## [Unreleased]` section with a `### Deprecated` entry recording the
  `view_deck` deprecation, the `src/viewer` freeze, and that removal is **deferred to the next minor
  release once the companion is proven** -- AC-5; 15.4 later extends this same section.
- `README.md` -- mark the `view_deck` entry in the tool table as deprecated, pointing at the
  companion app -- one row only; the rest of the README is 15.4's.
- `tests/unit/viewer/test_viewer_freeze.py` (new) -- two guards over pure functions with thin test
  callers: (a) **freeze pin** — the set of files under `src/viewer/` and the set of public callables
  per module equal frozen expected sets, message citing AD-15 and telling the reader a new capability
  belongs in the companion; (b) **no-reuse sweep** — no git-tracked companion source
  (`src/companion/**/*.py`, `ui/index.html`, `ui/src/**`, `ui/public/**`) imports `src.viewer` or
  names `template.html` / `src/viewer`. Include the non-vacuity anchor (empty scan raises), the
  firing half and the silent half on synthetic `tmp_path` sources, and a declared-residue docstring.
  Name the two whole-tree guards `TestViewerIsFrozen::test_public_surface_is_pinned` and
  `TestCompanionNeverReusesTheViewer::test_no_companion_source_reuses_the_viewer` -- the node ids the
  Verification probes expect -- AC-3 and AC-4.
- `tests/integration/mcp_server/test_view_deck_tool.py` -- append one test that builds the server and
  asserts the `list_tools()` description for `view_deck` marks it deprecated and names the companion;
  do not touch the existing behavioural tests -- AC-1 through the outermost surface.
- `plugin/` -- regenerate with `uv run python -m scripts.build_plugin` and commit the result -- the
  mirror is a generated artifact and CI fails on drift.

**Acceptance Criteria:**
- Given a connected MCP client, when it lists tools, then `view_deck`'s description marks it
  deprecated and names the companion app as its replacement.
- Given the existing `view_deck` test files, when the suite runs, then they pass **with no edits to
  their assertions**, and `git diff` over `src/viewer/`, `src/mcp_server/tools/view_deck.py` and
  `scripts/view_deck.py` shows changes only inside docstrings/comments.
- Given a new module or public function added under `src/viewer/`, when the suite runs, then the
  freeze pin fails and names it.
- Given a companion source that imports `src.viewer` or names `template.html`, when the suite runs,
  then the no-reuse sweep fails and names the file and line.
- Given the CHANGELOG, when its `[Unreleased]` section is read, then it records the deprecation and
  that `src/viewer`'s removal is deferred to the next minor release once the companion is proven.
- Given `uv run python -m scripts.build_plugin`, when it is re-run after the change is committed,
  then `git status --porcelain -- plugin/` is empty.

## Spec Change Log

- **2026-08-17 — the Code Map's read-only evidence was wrong about `src/viewer`.** The Code Map
  states `grep -rn "src\.viewer"` shows *zero* references under `ui/`. Measured at `999bacd`,
  `grep -rn "src/viewer"` (slash, the other spelling the sweep bans) has **two** hits:
  `ui/src/state/deckGroups.ts:26` and `ui/src/state/deckGroups.test.ts:72`, both prose comments
  citing `src/viewer/view_model.py::is_land` as the origin of the front-face land rule. Neither is
  reuse — TypeScript cannot import Python — but a literal ban on the token would have shipped red.
  Resolution, following the project's guard idiom (`_COMPANION_REFERENCE_ALLOWED` in
  `test_import_boundary.py`): a two-entry allow-list, each with its reason, that excuses **only**
  the token `src/viewer` on a line containing the exact citation string
  `src/viewer/view_model.py::is_land`, never `template.html` and never an import. A staleness pin
  (`test_every_citation_exemption_is_still_needed`) fails if either file stops carrying the
  citation, so the exemption cannot rot into a standing permission. Any *new* mention in either
  file, and any mention anywhere else, still fires.
- **2026-08-17 — the freeze pin's synthetic half is generated, not copied.** First cut copied the
  real `src/viewer` into `tmp_path` for the firing/silent halves. Planting the probe violation in
  the real package then fired all ten of them at once, which makes the synthetic half a second
  reading of the same measurement rather than an independent one. The fixture now builds a minimal
  package from `_FROZEN_MODULES` / `_FROZEN_EXPORTS` themselves, so it cannot drift from the pin
  and the two halves answer different questions. Second probe run: exactly one RED.

## Review Triage Log

### 2026-08-17 — Review pass (iteration 2 appended 2026-08-18)

- intent_gap: 0
- bad_spec: 0
- patch: 14: (high 0, medium 5, low 9)
- defer: 1: (high 0, medium 0, low 1)
- reject: 12: (high 0, medium 0, low 12)
- addressed_findings:
  - `[medium]` `[patch]` P1 — the freeze pin could not see a capability added to `template.html`, the
    file that *is* the renderer; `_FROZEN_DATA_FILES` now pins a CRLF-normalised sha256 per file.
  - `[medium]` `[patch]` P2 — the freeze pin walked the filesystem while its sibling sweep used git,
    so a gitignored stray reported as new capability; `git ls-files` is now the authority for both.
  - `[medium]` `[patch]` P3 — the committed, `plugin/`-mirrored SPA bundle was excluded by rule while
    AC-4's subject is the UI "when its assets are inspected"; every tracked non-binary file under
    `src/companion/` is now swept, retiring the unpinned `.py`-only premise with it.
  - `[medium]` `[patch]` P4 — `ui/vite.config.ts`, `ui/config/` and `ui/package.json` added to the
    pathspecs: a build-time reuse of the template is wired there and nowhere under `ui/src/`.
  - `[low]` `[patch]` P5 — error containment in the sweep (utf-8-sig, unparsable files reported not
    raised, NUL-split `git ls-files`, absent tracked paths skipped, named failure when git is absent).
  - `[low]` `[patch]` P6 — freeze-pin robustness (`__all__` by membership, computed/annotated/appended
    `__all__` reported rather than crashing, symbols nested in module-level blocks now seen).
  - `[low]` `[patch]` P7 — the citation exemption now requires a comment-only line, closing the
    `import … // <citation>` hole this spec's own change log claimed was already closed.
  - `[low]` `[patch]` P8 — reuse violations carry a fix note, the sweep's twin of `_FREEZE_FIX`.
  - `[low]` `[patch]` P9 — residue extended: the sweep sees reference, not duplication.
  - `[low]` `[patch]` P10 — `server.py`'s module docstring no longer introduces `view_deck` as a
    current feature.
  - `[low]` `[patch]` P11 — the description's first line keeps the tool's capability, so a truncating
    client still tells an agent what `view_deck` does.
  - `[low]` `[patch]` P12 — `[Unreleased]` gained its compare-link definition; the internal test path
    left the user-facing entry.
  - `[low]` `[patch]` P13 — the description assertion names the missing deprecation instead of raising
    `IndexError`.
  - `[medium]` `[patch]` P14 — public names bound by *import* escaped the freeze pin outside
    `__init__.py`, so a one-line re-export added a reachable capability with the guard green;
    `_FROZEN_IMPORTS` now pins each module's import bindings (star imports reported as unpinnable,
    `as _x` aliases deliberately private).

Rejected as noise or as contrary to a standing project ruling (12): deduplicating the sibling guard's
machinery (this repo's recorded ruling favours the duplication); flipping `sprint-status.yaml` (its
entries are written at PR merge and cite the merge commit); guarding the three prose notices by test;
resolving the bare `AD-15` token in shipped source (each site already states the rule in words); a
second deferral home in `deferred-work.md`; a golden-HTML snapshot for AC-2 (subsumed by P1); a
fixture path hypothetical for nested frozen modules; the `oversized` warning (already declared);
freeze pointers in `present.py` and `docs/plugin-structure.md`; the observation that the scheduled
removal will require editing the pin (deliberate, and `_FREEZE_FIX` instructs it); and the CHANGELOG
naming no version number for "the next minor".

**Iteration 1 (2026-08-17) — four-layer review: 0 intent gaps, 0 spec defects, 13 patches, all
applied.** The three measured findings first:

- **P1 (medium) — the freeze pin could not see the renderer.** `template.html` *is* the renderer:
  `render_html` only substitutes a JSON blob into it, and its ~200 lines of inline JS
  (`cardHtml`, `columnsHtml`, `curveHtml`) are where a deck becomes a page. The pin checked
  presence only, so a whole new panel could land in the frozen package with no Python symbol
  changing — while `src/viewer/__init__.py` and the CHANGELOG both told a reader "no new
  behaviour" was enforced. `_FROZEN_DATA_FILES` is now `name -> sha256`, hashed over
  **CRLF-normalised** bytes: the repo's `.gitattributes` scopes its `-text` rules to the SPA
  bundle only, so a raw hash would have fired on a Windows checkout under `core.autocrlf=true`
  and nowhere else. Verified against the real tree, not only the synthetic one.
- **P2 (medium) — git is now the freeze pin's file authority too**, as it always was for the
  sweep. `rglob("*")` meant a `.DS_Store`, an editor's `render.py.orig` or a stray `.pyc`
  reported as *new capability in a frozen package* on any working copy. Split into
  `tracked_viewer_files()` (git, real tree) and `walk_viewer_files()` (filesystem, the synthetic
  packages in `tmp_path`, which are not git repos); `find_freeze_violations` now takes the
  collected mapping, so it stays pure and both callers share it.
- **P3 (medium) — the committed SPA bundle is swept.** "It is built from sources we already
  scan" was the wrong argument: the bundle is a committed artifact that is also mirrored into
  `plugin/` and shipped, and AC-4's subject is the UI "when its assets are inspected". The
  `is_swept` premise that only `*.py` counts under `src/companion/` was also true-but-unpinned,
  so a future `app/templates/deck.html` would have escaped on its suffix. One uniform rule now:
  every tracked non-binary file. Measured: the committed bundle produces no false positive
  (Vite strips the comments that carry the citation).
- **P4** — `ui/vite.config.ts`, `ui/config/` and `ui/package.json` added to the pathspecs: a
  build-time reuse (a `?raw` import, a copy plugin, an npm script) is wired there and in no file
  under `ui/src/`. `ui/tests/` stays out, for the reason `read-only-glass.test.ts` excludes
  itself; that is now residue 3.
- **P5** — error containment: `utf-8-sig` (a BOM-saved companion `.py` used to raise
  `invalid non-printable character U+FEFF`), unreadable/unparsable files reported as violations
  rather than raising, `_resolve_import`'s deliberate `ValueError` contained at the call site,
  `git -c core.quotePath=false ls-files -z` split on NUL, tracked-but-absent paths skipped, and
  a git failure turned into a named `pytest.fail`.
- **P6** — freeze-pin robustness: `__all__` compared by **membership** (a reorder no longer
  fires with the wrong diagnosis), a computed `__all__` and `__all__ +=` / `.append` reported
  instead of crashing `ast.literal_eval`, `AnnAssign` handled, and `public_symbols` now recurses
  into module-level `if`/`try`/`with`/loop bodies and unpacks tuple targets.
- **P7** — the citation exemption requires a **comment** line, closing the
  `import … // src/viewer/view_model.py::is_land` hole that contradicted this spec's own change-log
  entry. A new guard also pins that both real citations still sit on comment lines.
- **P8** — reuse violations carry `_NO_REUSE_FIX`, the sweep's twin of `_FREEZE_FIX`.
- **P9** — residue 5: the sweep sees *reference*, not *duplication*; copy-pasting the template's
  markup into a component names none of the banned tokens.
- **P10 / P11** — `server.py`'s module docstring no longer introduces `view_deck` as a current
  feature, and the tool's summary line keeps its capability so a truncating client still shows an
  agent what the tool does: *"DEPRECATED — renders a saved deck as static HTML; superseded by the
  companion app."*
- **P12** — `[Unreleased]` gained its compare link beside the other release definitions, and the
  internal test path was dropped from the user-facing entry.
- **P13** — the description assertion fails naming the missing deprecation instead of raising
  `IndexError` on an empty description.

One follow-on found while re-running the proofs, fixed in the same pass:
`test_an_untracked_stray_is_not_a_new_capability` first asserted the *whole* tree was clean, so
it went red alongside `test_public_surface_is_pinned` during the planted-violation probe — the
same "two readings of one measurement" mistake recorded in the Spec Change Log. It now asserts
only that nothing reported mentions the stray.

**Iteration 2 (2026-08-18) — PR #84 automated review (Greptile): 1 finding, 1 patch.**

- **P14 (medium) — imported exports escaped the freeze pin.** `public_symbols()` reads `def`,
  `class` and module-level assignment and deliberately skips imports, deferring re-exports to
  `__all__` — but `__all__` was validated for `__init__.py` alone. A `def` was therefore never the
  only way to put a capability on a frozen module: one line of
  `from src.viewer.render import render_compact` in `present.py` makes
  `viewer.present.render_compact` reachable, and the pin stayed green. `imported_symbols()` now
  reads what each import statement *binds* — `import a.b` binds `a`, `import a.b as c` binds `c` —
  and `_FROZEN_IMPORTS` pins that per module, with its own rule and fix note rather than folding
  into `_FREEZE_RULE`: "you added an import" and "you wrote a new function here" want different
  answers, and this file's standing position is that a wrong diagnosis is worse than none. A star
  import is reported as unpinnable in its own right, for the same reason a computed `__all__` is.
  An `as _x` alias binds privately and is invisible to the pin — the honest way to use a name
  without offering it, and the first line of the fix note. Both the synthetic fixture and residue 1
  were updated: the fixture is still generated from the pin's own constants, and the residue now
  states what the private alias costs. Verified against the real tree, not only the synthetic one —
  a planted `import os` in `src/viewer/render.py` fires `test_public_surface_is_pinned` naming
  `render.py:1 — os`; removed, the guard is green. 64 tests in the file, 2644 in `tests/unit`.

## Design Notes

**Why the description and not `__doc__`.** AD-15's rule is "its docstring names the companion as the
replacement", and the docstring's purpose here is the LLM-facing tool description. FastMCP returns
the whole docstring, so asserting through `list_tools()` observes the surface an agent actually
reads; a `view_deck.__doc__` assertion would pass even if registration stopped exposing it.

**Why two guards rather than a note.** AD-15 exists to prevent "a story 'improving' `view_deck` after
the decision to retire it" and two renderers diverging. Both properties hold today only because
nobody has written the offending line — the same "rule vs coincidence" gap `read-only-glass.test.ts`
was written to close. The freeze pin is an enumeration pin (the idiom
`test_import_boundary.py::test_every_companion_file_sits_in_a_guarded_category` uses): adding a
capability is exactly adding a module or a public symbol, so the pin fires on the act itself.

**Declared residue** (state it in the guard's docstring, do not claim completeness): the freeze pin
sees module and public-symbol *addition* plus the pinned bytes of `template.html`, not a body that
grows a new behaviour inside an existing Python function — that stays a reviewer's judgement. The
no-reuse sweep is a text/AST scan of **git-tracked source**, and a runtime-assembled path string
defeats it. *(Amended at review — the original text excused the generated bundle under
`src/companion/app/static/` on the grounds that it is built from the swept sources. Review P3
overturned that: the bundle is a committed, `plugin/`-mirrored artifact, and AC-4's subject is the UI
"when its assets are inspected", so it is swept like any other tracked file.)*

**One home for the deferral.** AC-5 says "release notes or CHANGELOG". Use the CHANGELOG only — a
second copy in `deferred-work.md` would be a second source of truth for the same scheduled removal.

## Verification

**Commands:**
- `uv run ruff check . --fix && uv run ruff format .` -- expected: clean.
- `uv run mypy src/` -- expected: clean (`--strict` via pre-commit over `^src/`).
- `uv run python -m scripts.probe_harness --expect-green` -- expected: full suite green; record the
  collected count from the proof line.
- `uv run python -m scripts.probe_harness --expect-red
  'tests/unit/viewer/test_viewer_freeze.py::TestViewerIsFrozen::test_public_surface_is_pinned'`
  after planting a new public function in `src/viewer/view_model.py` -- expected: RED for that node
  id. Revert, then `git diff --exit-code src/viewer/view_model.py`.
- `uv run python -m scripts.probe_harness --expect-red
  'tests/unit/viewer/test_viewer_freeze.py::TestCompanionNeverReusesTheViewer::test_no_companion_source_reuses_the_viewer'`
  after planting a `template.html` reference in a companion source -- expected: RED for that node id.
  Revert and verify with `git diff --exit-code`.
- `uv run python -m scripts.build_plugin && git status --porcelain -- plugin/` -- expected: rebuild
  succeeds and, once `plugin/` is committed, the status output is empty.

**Manual checks:**
- Paste both harness proof lines into this spec's record — a hand-transcribed count is not evidence.
- Read the new `view_deck` description as printed by `list_tools()`: the first line alone must tell
  an agent it is deprecated and what replaced it.

## Verification Record (2026-08-17, re-run after review iteration 1)

- `uv run ruff check . --fix && uv run ruff format .` — clean (`All checks passed!`).
- `uv run mypy src/` — clean (`Success: no issues found in 94 source files`).
- Baseline green, before any planting (the count rose from 3086 to 3107 with the review's new
  guards):

  ```
  full suite (-m 'not integration'): 3107 collected, 0 failed, exit 0
  ```

- **Freeze pin, fired.** Planted `def build_sideboard_panel(...)` at the end of
  `src/viewer/view_model.py`:

  ```
  full suite (-m 'not integration'): 3107 collected, 1 failed, 0 errored, exit 1
    RED    tests/unit/viewer/test_viewer_freeze.py::TestViewerIsFrozen::test_public_surface_is_pinned
  ```

  Reverted; `git diff --exit-code src/viewer/view_model.py` clean.

- **Freeze pin, fired on the renderer itself (P1).** The reviewer's own scenario, run against the
  real package rather than a synthetic one — appended
  `<script>function sideboardPanel(){return 1}</script>` to `src/viewer/template.html`:

  ```
  src/viewer/template.html:0 — template.html content changed (sha256 2bd1e76c9518, pinned
  679dbb94d775) (template.html IS the renderer (its inline JS builds the page), so its bytes are
  pinned — editing it is adding behaviour to a frozen package (AD-15)); if this addition is
  deliberate, it is the wrong package: build it in the companion. …
  ```

  Reverted; `git diff --exit-code src/viewer/template.html` clean.

- **No-reuse sweep, fired.** Planted `_LEGACY_TEMPLATE = "template.html"` in
  `src/companion/app/spa.py`:

  ```
  full suite (-m 'not integration'): 3107 collected, 1 failed, 0 errored, exit 1
    RED    tests/unit/viewer/test_viewer_freeze.py::TestCompanionNeverReusesTheViewer::test_no_companion_source_reuses_the_viewer
  ```

  Reverted; `git diff --exit-code src/companion/app/spa.py` clean.

- Green again after both reverts:

  ```
  full suite (-m 'not integration'): 3107 collected, 0 failed, exit 0
  ```

- `uv run pytest -m integration` — `55 passed, 3107 deselected`.

- `uv run python -m scripts.build_plugin` — rebuilt; the mirrored files
  (`plugin/server/README.md`, `plugin/server/src/mcp_server/server.py`,
  `plugin/server/src/mcp_server/tools/view_deck.py`, `plugin/server/src/viewer/__init__.py`)
  were regenerated and committed, after which a re-run leaves
  `git status --porcelain -- plugin/` empty.

- **The description, as `list_tools()` prints it.** First line, verbatim (revised under P11 so a
  client that truncates to one line still tells the agent what the tool *does*):

  ```
  DEPRECATED — renders a saved deck as static HTML; superseded by the companion app.
  ```

  It stands alone: what it does, that it is deprecated, and what replaced it, before any
  truncation point; `companion_set_active_deck` is named in the next paragraph. (FastMCP does
  not dedent the body — the remaining lines keep their source indentation, exactly as every other
  tool in this server already does.)

## Auto Run Result

Status: done
Baseline: `999bacd` → `bc6196f` (two commits on `feat/companion-epic-15`, not pushed)

**Summary.** AD-15's ruling is now stated where it is read and enforced where it can be broken.
`view_deck` keeps rendering HTML byte-for-byte as before — no statement, expression or signature
moved — while its MCP-visible description, the two composition roots and the `src/viewer` package
docstring all name the companion app as the replacement and record that removal is deferred to the
next minor release once the companion is proven. Two properties that previously held only because
nobody had written the offending line are now guards: a **freeze pin** over `src/viewer`'s module
set, per-module public surface, `__all__` and the pinned bytes of `template.html`, and a **no-reuse
sweep** over every git-tracked companion source — backend, frontend, build config and the committed
SPA bundle — for any reference to the frozen renderer.

**Files changed** (14; `plugin/` is a generated mirror rebuilt by `scripts/build_plugin.py`):

- `src/mcp_server/server.py` — the registered `view_deck` docstring (the MCP tool description) leads
  with the deprecation while keeping the tool's capability in the summary line; the module docstring
  no longer introduces `view_deck` as a current feature.
- `src/mcp_server/tools/view_deck.py`, `scripts/view_deck.py` — the same pointer in their module
  docstrings. Behaviour untouched.
- `src/viewer/__init__.py` — the FROZEN (AD-15) notice: no new module, no new public function, no new
  behaviour; removal scheduled for the next minor once the companion is proven.
- `CHANGELOG.md` — a new `## [Unreleased]` → `### Deprecated` entry with its compare-link definition,
  recording the deprecation, the freeze and the deferred removal.
- `README.md` — the one tool-table row marked deprecated.
- `tests/unit/viewer/test_viewer_freeze.py` (new, 57 tests) — both guards, with non-vacuity anchors,
  firing and silent halves on generated synthetic packages, staleness pins and declared residue.
- `tests/integration/mcp_server/test_view_deck_tool.py` — one appended test over `list_tools()`; the
  five existing behavioural tests are byte-identical.
- `_bmad-output/implementation-artifacts/epic-15-context.md` — compiled epic context (new).
- `plugin/server/{README.md,src/mcp_server/server.py,src/mcp_server/tools/view_deck.py,src/viewer/__init__.py}`
  — regenerated mirror.

**Review findings.** Four layers (Blind Hunter, Edge Case Hunter, Verification Gap, Intent
Alignment). 0 intent gaps, 0 spec defects, **13 patches applied** (4 medium, 9 low), **1 deferred**
(low — see frontmatter), **12 rejected**. Three of the four medium findings were measured by a
reviewer rather than argued: the freeze pin returned `[]` for a script tag appended to
`template.html`; a `.DS_Store` in `src/viewer/` reported as new capability; and the committed SPA
bundle — AC-4's literal "assets" — was excluded from the sweep by rule.

**Follow-up review recommended: true.** Patched findings this pass: high 0, medium 4, low 9 →
`3 × 4 + 1 × 9 = 21`, at or above the threshold of 5.

**Verification** (re-run independently after the patch pass, from a clean tree):

- `uv run ruff check .` — All checks passed. `ruff format --check .` — 332 files already formatted.
- `uv run mypy src/` — Success: no issues found in 94 source files.
- `uv run python -m scripts.probe_harness --expect-green` —
  `full suite (-m 'not integration'): 3107 collected, 0 failed, exit 0`.
- Freeze pin, planted public function in `src/viewer/view_model.py` —
  `3107 collected, 1 failed, 0 errored, exit 1` /
  `RED tests/unit/viewer/test_viewer_freeze.py::TestViewerIsFrozen::test_public_surface_is_pinned`.
  Reverted; `git diff --exit-code` clean.
- Freeze pin, planted `<script>function sideboardPanel(){return 1}</script>` appended to
  `src/viewer/template.html` — the scenario a reviewer measured as *passing* before P1 —
  `3107 collected, 1 failed, 0 errored, exit 1` / RED on the same node id. Reverted; clean.
- No-reuse sweep, planted `_LEGACY_TEMPLATE = "template.html"` in `src/companion/app/spa.py` —
  `3107 collected, 1 failed, 0 errored, exit 1` / `RED …::TestCompanionNeverReusesTheViewer::`
  `test_no_companion_source_reuses_the_viewer`. Reverted; clean.
- No-reuse sweep, planted `<!-- lifted from src/viewer/template.html -->` in the committed bundle
  `src/companion/app/static/index.html` — the P3 surface — reported two violations at
  `src/companion/app/static/index.html:45` with the fix note attached. Reverted; clean.
- `uv run pytest -m integration` — 55 passed, 3107 deselected.
- `uv run python -m scripts.build_plugin` then `git status --porcelain -- plugin/` — empty.
- **Matrix test audit:** all seven I/O-matrix rows are covered by tests that ran and passed in the
  green run above — the description row by `test_view_deck_is_advertised_as_deprecated`, the
  unchanged-behaviour row by the five untouched existing tests, both guards' clean-tree and firing
  halves by their whole-tree and synthetic cases, and the vacuity row by
  `TestScansCannotPassVacuously`.

**Residual risks.**

- The freeze pin sees *names and pinned bytes*; a signature change on an existing public function
  (`render_html(deck, *, compact=False)`) and a new behaviour grown inside an existing Python
  function body both pass. Reviewer judgement, declared in the guard docstring.
- The no-reuse sweep sees *reference*, not *duplication*: markup copy-pasted out of `template.html`
  into a companion component names none of the banned tokens and passes. This is the failure AD-15
  actually describes, so it stays a review responsibility.
- `git ls-files` is the file authority for both halves, so an unstaged violation is invisible until
  it is staged — the same limit `posture.test.ts` and `read-only-glass.test.ts` declare.
- The scheduled removal will turn the freeze pin red until `_FROZEN_MODULES` / `_FROZEN_DATA_FILES`
  are edited in the same change. Deliberate; `_FREEZE_FIX` instructs it.
- `template.html`'s digest is taken over CRLF-normalised bytes because the repo's `.gitattributes`
  scopes its `-text` rules to the SPA bundle only; a raw hash would have fired on a Windows checkout
  under `core.autocrlf=true` and nowhere else. A dedicated test pins that a line-ending rewrite is
  silent while a script tag fires.
- Story 15.4 must close the deferred README gap before release.

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

PR #84 MERGED 2026-08-18 at f938d03 into feat/companion-epic-15 (commits 22c9a56 deprecate+freeze, bc6196f review iteration 1, bdde98e review record, 6bf69ba iteration 2 P14 import-binding pin). Merged AFTER the previous tracking write (08-17 19:32), which is why the status view still recommended building it.
