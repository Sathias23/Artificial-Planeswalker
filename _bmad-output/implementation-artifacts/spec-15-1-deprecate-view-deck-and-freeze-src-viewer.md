---
title: 'Deprecate view_deck and freeze src/viewer'
type: 'chore'
created: '2026-08-17'
status: 'complete'
baseline_revision: '999bacd713bdec0d1a8ca2f77f6bda9b597137d6'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-15-context.md'
warnings: ['oversized']
deferred: []
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
sees module and public-symbol *addition*, not a body that grows a new behaviour inside an existing
function — that stays a reviewer's judgement. The no-reuse sweep is a text/AST scan of **git-tracked
source**; the generated bundle under `src/companion/app/static/` is out of scope because it is built
from exactly the swept sources, and a runtime-assembled path string defeats it.

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

## Verification Record (2026-08-17)

- `uv run ruff check . --fix && uv run ruff format .` — clean (`All checks passed!`).
- `uv run mypy src/` — clean (`Success: no issues found in 94 source files`).
- Baseline green, before any planting:

  ```
  full suite (-m 'not integration'): 3086 collected, 0 failed, exit 0
  ```

- **Freeze pin, fired.** Planted `def build_sideboard_panel(...)` at the end of
  `src/viewer/view_model.py`:

  ```
  full suite (-m 'not integration'): 3086 collected, 1 failed, 0 errored, exit 1
    RED    tests/unit/viewer/test_viewer_freeze.py::TestViewerIsFrozen::test_public_surface_is_pinned
  ```

  Reverted; `git diff --exit-code src/viewer/view_model.py` clean.

- **No-reuse sweep, fired.** Planted `_LEGACY_TEMPLATE = "template.html"` in
  `src/companion/app/spa.py`:

  ```
  full suite (-m 'not integration'): 3086 collected, 1 failed, 0 errored, exit 1
    RED    tests/unit/viewer/test_viewer_freeze.py::TestCompanionNeverReusesTheViewer::test_no_companion_source_reuses_the_viewer
  ```

  Reverted; `git diff --exit-code` clean over the whole tree.

- Green again after both reverts:

  ```
  full suite (-m 'not integration'): 3086 collected, 0 failed, exit 0
  ```

- `uv run python -m scripts.build_plugin` — rebuilt; the four mirrored files
  (`plugin/server/README.md`, `plugin/server/src/mcp_server/server.py`,
  `plugin/server/src/mcp_server/tools/view_deck.py`, `plugin/server/src/viewer/__init__.py`)
  were regenerated and committed, after which a re-run leaves
  `git status --porcelain -- plugin/` empty.

- **The description, as `list_tools()` prints it.** First line, verbatim:

  ```
  DEPRECATED — superseded by the companion app; prefer ``companion_set_active_deck``.
  ```

  It stands alone: deprecated, and what replaced it, before any truncation point. (FastMCP does
  not dedent the body — the remaining lines keep their source indentation, exactly as every other
  tool in this server already does.)
