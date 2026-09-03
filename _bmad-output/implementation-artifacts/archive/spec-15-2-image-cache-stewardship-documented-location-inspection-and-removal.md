---
title: 'Image cache stewardship — documented location, inspection and removal'
type: 'chore'
created: '2026-08-18'
baseline_revision: '6aa37f368972db9f380ded004b32a30e09488a9f'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-15-context.md'
warnings: ['oversized']
deferred:
  - summary: >-
      The documented inspect/clear commands need the checkout and its environment (`uv run`), so
      they cannot be run in the post-uninstall case the same section documents.
    evidence: |-
      Measured at review, 2026-08-18: `cd /tmp && uv run python -c "from src import paths; ..."`
      fails with `ModuleNotFoundError: No module named 'src'`. The README now states the
      precondition and points a post-uninstall reader at the per-OS path in the data-dir table
      instead, but a first-class command that works without the checkout would need a console
      entry point — Story 15.4 owns the console-script documentation, and no AC here asks for one.
    location: >-
      README.md:266
    severity: low
  - summary: >-
      "Safe to delete at any time, running app or not" is the one operational claim in the section
      with no test behind it.
    evidence: |-
      It holds because `_write_atomically` re-creates the shard directory
      (`src/companion/app/images.py:1023`, `mkdir(parents=True, exist_ok=True)`), so a root deleted
      under a live process is rebuilt on the next write. Proving it needs a delete-while-running
      exercise against a live cache, which is a behavioural test of `DiskCache` rather than of this
      story's prose. If that mkdir ever moves, the README claim goes stale silently.
    location: >-
      README.md:313
    severity: low
  - summary: >-
      The PowerShell blocks are never executed by any suite, on any platform.
    evidence: |-
      This project's CI runs Linux and Windows lanes but no `pwsh`; the guard executes only the
      Python payload, which is byte-identical across both blocks. `$Cache = …`, `Get-ChildItem`,
      `Measure-Object` and `Remove-Item -Recurse -Force -ErrorAction SilentlyContinue` are
      reviewer-verified only. Also recorded in `deferred-work.md` under `## Deferred from: story
      15-2`.
    location: >-
      README.md:277
    severity: low
  - summary: >-
      The measured footprint figures are pinned by nothing, in the README or in the epic.
    evidence: |-
      ~90 KB per tile, 8.5 MB per deck and ~95 MB per library are C3-retrospective measurements
      with no constant to key on; the guard asserts only that they are present and labelled
      measured. The epic (`epics-companion-app.md:294,888,1846,3329`) still carries the superseded
      ~12 MB with no annotation — reconciling requirement documents with what was built is Story
      15.3's scope, not this one's.
    location: >-
      _bmad-output/planning-artifacts/epics-companion-app.md:3329
    severity: low
---

<intent-contract>

## Intent

**Problem:** The companion writes an **unbounded** image cache into the user's data directory and
nothing tells the user it exists. Its location, its two-hex sharding, the fact that it never evicts,
what it costs, how to look at it or delete it, what an uninstall leaves behind, and the accepted
staleness when a data refresh changes a card's `image_uris` are all discoverable only by reading
`src/companion/app/images.py`. Four `deferred-work.md` entries are homed on this story, and three
docstrings in the shipped module still promise that this story will write the documentation.

**Approach:** Add one stewardship section to the README under **Where the data lives** that states
the location, the sharding, the env override, copy-pasteable inspect/clear commands, the
no-eviction ruling with its **measured** footprint, the staleness behaviour and the uninstall
leftovers; pin the load-bearing facts to the shipped code with a drift guard so the prose cannot
outlive the constants; retire the three "c8-2 will document this" forward references; and settle
the ledger — closing the documentation halves and re-recording the mechanism halves as unbuilt.

## Boundaries & Constraints

**Always:**
- Every documented fact is keyed to shipped code, not to a literal a reader trusted:
  `images.CACHE_DIRECTORY_NAME` for the directory, `images._cache_path` for the
  `<id[0:2]>/<id>/<size>_<face>.<ext>` layout, and `images.cache_root()` for the claim that the
  location follows `PLANESWALKER_DATA_DIR`.
- The footprint is the **measured** one (C3 retrospective, 2026-08-02: ~90 KB per `normal` tile,
  **8.5 MB** for a 99-tile deck, ~95 MB for this user's whole 1,061-id library). The epic's
  ~12 MB is named as the earlier arithmetic estimate it was — the docs must not ship a number the
  project has already measured as a 38 % overestimate. Both figures appear, one labelled measured.
- The commands are copy-pasteable on **Windows PowerShell and macOS/Linux**, and they resolve the
  path through the app's own `src.paths`, so a user who has set `PLANESWALKER_DATA_DIR` — or who
  does not know their platform's default — gets the right directory without editing the command.
- Shipped code changes are **docstrings and comments only**: no statement, expression or signature
  moves under `src/`. `DISK_CACHE_WRITE_FAILURE_LIMIT`'s docstring keeps the literal `99`
  (`test_images.py::test_the_limit_carries_its_reasoning` pins it).
- The new guard follows the project's guard idiom: a **non-vacuity anchor** (a missing or renamed
  README section fails loudly rather than passing on an empty scan), a firing half and a silent
  half, an assertion message that names which side to edit, and **declared residue** in the module
  docstring.
- The guard is **firing-proven through `scripts/probe_harness`** with a planted violation and the
  proof line pasted into this spec's record. Stage the tree before planting; revert and confirm
  with `git diff --exit-code <file>`.
- `README.md` is mirrored into `plugin/server/README.md` by `scripts/build_plugin.py` and CI fails
  on drift — rebuild the mirror and commit it.

**Block If:**
- The documented inspect/clear command cannot be shown to resolve the same root the app writes to
  (i.e. the guard cannot be made non-vacuous) — a stewardship doc whose command points elsewhere is
  worse than none.
- An acceptance criterion can only be met by asserting an unmeasured number or by contradicting a
  measurement already in the ledger.

**Never:**
- **No mechanism.** No eviction, TTL, size accounting, index, `.tmp` sweep, startup retry,
  write-latch re-enable path, or new CLI subcommand. The two lifecycle entries homed here stay
  unbuilt and are re-recorded as such — this story's intent is disclosure.
- No companion overview, launch command, prerequisites, fresh-install narrative, port/discovery
  explanation, licensing section or dependency/version-floor CHANGELOG entries — **Story 15.4**
  owns those, and this section must not absorb them.
- No PRD, architecture or `EXPERIENCE.md` amendments — **Story 15.3**'s.
- No behaviour change in `src/companion/app/images.py`; no hand edit of
  `src/companion/app/static/` or `plugin/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Docs current | Today's README + shipped constants | Guard passes | No error expected |
| Directory renamed | `CACHE_DIRECTORY_NAME` changed, README not | Fails naming both the shipped name and the documented one | Message says which side to edit |
| Layout changed | `_cache_path` shard width or `<size>_<face>` shape changed | Fails naming the shipped path built from a synthetic id | Path derived from the function, never a literal |
| Override honoured | `PLANESWALKER_DATA_DIR` pinned to `tmp_path` | The README's own one-liner, executed, prints exactly `images.cache_root()` | Any mismatch fails naming both paths |
| Section removed/renamed | README with no `### Image cache` heading | Fails loudly, naming the heading it looked for | Never a vacuous pass on an empty scan |
| Command block missing | Section present, fenced command removed | Fails naming the missing block | Extraction returns nothing → explicit failure |

</intent-contract>

## Code Map

- `README.md:196-241` -- **`## Where the data lives`**, with `### Semantic search index` (:211) and
  `### Combo snapshot (deck power assessment)` (:226). The new `### Image cache (companion app)`
  lands after :241, before `## Development` (:242). The data-dir table at :199-207 and the
  `PLANESWALKER_DATA_DIR` sentence at :209 already exist — reference them, do not restate them.
- `src/companion/app/images.py:369` -- `CACHE_DIRECTORY_NAME = "image_cache"`; its docstring
  (`:370-376`) is **forward reference #1**: "the documented location, the removal command and the
  uninstall notes that quote it are **c8-2**'s".
- `src/companion/app/images.py:782-801` -- `cache_root()` = `paths.data_dir() / CACHE_DIRECTORY_NAME`,
  resolved at call time. This is why the documented one-liner honours `PLANESWALKER_DATA_DIR`.
- `src/companion/app/images.py:845-869` -- `_cache_path`: `<root>/<id[0:2]>/<id>/<size>_<face>.<ext>`.
  All 256 shards used, 107-218 cards each against a flat 38,261 card directories. The filename is
  constructed and never parsed back.
- `src/companion/app/images.py:83` -- forward reference #2, inside the "what is deliberately NOT
  here" list: "no eviction, no size accounting, no TTL and no index … the documented location and
  the removal command are **c8-2**'s".
- `src/companion/app/images.py:1124` (in `class DiskCache`, :1073) -- forward reference #3, same
  promise.
- `src/companion/app/images.py:167-192` -- `IMAGE_CACHE_CONTROL = "public, max-age=31536000,
  immutable"`: the **browser** also holds an image for a year, and accepts the same staleness for
  the same reason. Relevant to the staleness paragraph — deleting the disk cache alone may not
  refresh an already-open tab.
- `src/companion/app/images.py:378-416` -- `DISK_CACHE_WRITE_FAILURE_LIMIT = 5`: five *consecutive*
  failed writes disable the cache's writes **for the process**, announced once. Reads keep working;
  every image is still served. This is one of the two lifecycle exposures to disclose. Its
  docstring is pinned on the literal `99` by
  `tests/unit/companion/test_images.py:2176-2181`.
- `src/companion/discovery.py:50,98` -- `COMPANION_FILENAME = "companion.json"` at
  `paths.data_dir()/companion.json`; written on startup, removed on clean shutdown, **left behind
  by a crash** (a stale file is read as "not running", never an error).
- `src/companion/app/singleton.py:65,82-94,147-160` -- `LOCK_FILENAME = "companion.lock"` at
  `paths.data_dir()/companion.lock`. A zero-byte file **deliberately never deleted** — on POSIX
  `flock` attaches to the inode, so unlink-and-recreate would let two processes both hold "the
  lock". c1-9 ruling #4 homes documenting its existence on this story.
- `src/paths.py:24-47` -- `data_dir()`, the `PLANESWALKER_DATA_DIR` override and the per-OS defaults
  the README table already quotes. `database_path()` (`cards.db`) and `fastembed_cache_dir()`
  (`fastembed_cache/`) are the data dir's other residents — name them only as "what else is in
  there", they are not the companion's leftovers.
- `_bmad-output/implementation-artifacts/deferred-work.md:3440-3450` (unbounded cache: location,
  removal command, uninstall notes — **Home: 15-2**), `:3613-3622` (orphaned `.tmp` debris — "one
  sentence in its stewardship notes"), `:3625-3640` (transient startup `OSError` disables the cache
  for the process — re-homed here for a *lifecycle* decision), `:3783-3790` (a ~6 s transient
  latches writes off — "any re-enable/recovery mechanism is cache stewardship. **Home: 15-2**").
  The measured footprint table is at `:3452-3470`.
- `tests/unit/companion/test_import_boundary.py:63,237,557` -- **the guard idiom to follow**:
  `REPO_ROOT = Path(__file__).resolve().parents[3]`, a repo-root sanity assert, violations rendered
  as `path:line — symbol (rule)`, enumeration pins whose message says "add it to X".
- `tests/unit/companion/test_images.py:2985-3007` --
  `test_the_wire_prose_in_contracts_matches_the_shipped_schedule`: **the prose-drift gate this story
  reuses**, keyed on the constants and never on literals, "so the pin moves with any renumbering
  that also updates the prose".
- `tests/unit/companion/conftest.py:100-115` -- autouse `isolated_data_dir` pins
  `PLANESWALKER_DATA_DIR` at each test's `tmp_path`. The override assertion gets its isolation free.
- `scripts/build_plugin.py:58-62,217-222` -- `SERVER_FILES` includes `README.md`; the mirror is
  regenerated with `uv run python -m scripts.build_plugin` and CI fails if `plugin/` is dirty after.
- `scripts/probe_harness.py:1-27` -- owns its own argv; the caller supplies only
  `--expect-red '<node id>'` / `--expect-green`.
- **Read-only evidence:** `grep -rn "image_cache" README.md docs/ ui/README.md` returns **nothing**
  today — no section is being replaced, and no other document carries a figure that could disagree
  with this one. `README.md` is outside the pathspecs of Story 15.1's no-reuse sweep, and this
  change names neither `src/viewer` nor `template.html`, so neither 15.1 guard is in play.

## Tasks & Acceptance

**Execution:**
- `README.md` -- add `### Image cache (companion app)` as the last subsection of **Where the data
  lives**, covering, in this order: (1) what it is and where — `<data dir>/image_cache/`, pointing
  at the table above for the per-OS default and stating it follows `PLANESWALKER_DATA_DIR`;
  (2) the layout `image_cache/<first two characters of the card id>/<card id>/<size>_<face>.<ext>`
  and one sentence on why the two-character shard exists (all 256 shards used, ~150 cards each,
  against 38k card directories in one flat directory); (3) **inspect** and (4) **clear** — a
  `bash` block and a PowerShell block, each resolving the path with
  `uv run python -c "from src import paths; print(paths.data_dir() / 'image_cache')"`;
  (5) **no eviction**, stated plainly, with the measured footprint (~90 KB per `normal` tile,
  **8.5 MB** per 100-card deck at one size, ~95 MB for a 40-deck library) beside the epic's earlier
  ~12 MB arithmetic estimate, and the ruling that any future eviction policy is sized against a
  measured footprint rather than guessed; (6) **staleness** — a data refresh that changes a card's
  `image_uris` keeps serving the old entry because the key is id + size + face; the remedy is
  deleting the directory, and a browser may hold its own copy for up to a year; (7) **safe to
  delete at any time** — every entry is reconstructible by refetching, nothing indexes it, and this
  also removes any `.tmp` debris a hard kill left mid-write; (8) **what an uninstall leaves behind**
  — `image_cache/`, `companion.lock` (always, and deliberately: deleting it is a correctness bug),
  and `companion.json` only if the process did not exit cleanly; plus one line that the data
  directory also holds `cards.db` and `fastembed_cache/`, so removing the directory removes
  everything; (9) one short paragraph on the two accepted cache-disable behaviours (a transient
  failure while creating the root at startup, and five consecutive failed writes) — in both cases
  every image is still served and already-cached images still read, and **restarting the app is the
  remedy**. -- this is the whole of AC-1 through AC-5.
- `tests/unit/companion/test_image_cache_docs.py` (new) -- the drift guard over the section above,
  as one class with a module docstring declaring its residue. Cover: the section heading exists
  (non-vacuity anchor — every other assertion reads the extracted section, so its absence must fail
  first and by name); the documented directory equals `images.CACHE_DIRECTORY_NAME`; the documented
  layout matches a path built by `images._cache_path` from a synthetic id (shard width and
  `<size>_<face>` shape derived, never asserted as literals); the README's own path one-liner,
  extracted from its fenced block and executed in-process under the autouse `isolated_data_dir`
  fixture, prints exactly `images.cache_root()` (this is simultaneously the override claim and the
  command's correctness); the no-eviction, staleness and leftovers claims each name their subject
  (`companion.lock` from `singleton.LOCK_FILENAME`, `companion.json` from
  `discovery.COMPANION_FILENAME`); and a silent half proving the guard does not fire on ordinary
  edits to prose elsewhere in the README. -- the I/O matrix rows.
- `src/companion/app/images.py` -- retire the three "**c8-2**'s" forward references (`:83`, `:374`,
  `:1124`) so they name the shipped README section instead of promising a future story; **docstrings
  only**, and keep the `99` in `DISK_CACHE_WRITE_FAILURE_LIMIT`'s docstring -- a module that still
  says "someone will document this" after it was documented is the drift this story is about.
- `_bmad-output/implementation-artifacts/deferred-work.md` -- settle the four entries homed here:
  mark the unbounded-cache entry (`:3440`) and the `.tmp`-debris entry (`:3613`) **closed by 15-2**,
  citing the README section; and re-record the two lifecycle entries (`:3625`, `:3783`) as
  **disclosed but unbuilt**, with the honest reason (this story's intent is disclosure, not
  mechanism; retrying still means deciding *when*) and a forcing function — a real report of a
  silently disabled cache -- so neither entry rots into an unowned promise. Append a
  `## Deferred from: story 15-2` section only if a new residue is found; do not restructure the file.
- `plugin/` -- regenerate with `uv run python -m scripts.build_plugin` and commit
  `plugin/server/README.md` (and any other regenerated file) -- the mirror is a generated artifact
  and CI fails on drift.

**Acceptance Criteria:**
- Given the README, when the cache section is read, then it names `<data dir>/image_cache/`,
  explains the two-character shard, and says the location follows `PLANESWALKER_DATA_DIR`.
- Given a user on Windows **or** macOS/Linux who has never resolved their data directory, when they
  copy the documented inspect and clear commands verbatim, then both act on the directory the app
  actually writes to, including under a `PLANESWALKER_DATA_DIR` override.
- Given the README, when the eviction paragraph is read, then it states plainly that nothing is ever
  evicted, gives the measured footprint per deck and per library, distinguishes it from the epic's
  earlier arithmetic estimate, and records that a future policy is sized against a measurement.
- Given the README, when the uninstall paragraph is read, then it names `image_cache/`,
  `companion.lock` and — conditioned on an unclean exit — `companion.json`.
- Given a data refresh that changes a card's `image_uris`, when the README's staleness paragraph is
  read, then the old entry being served is stated as accepted behaviour with its cause (the key is
  id + size + face) and its remedy.
- Given `src/companion/app/images.py`, when its diff is read, then only docstrings and comments
  changed, and no docstring still promises that a future story will document the cache.
- Given `uv run python -m scripts.build_plugin`, when it is re-run after the change is committed,
  then `git status --porcelain -- plugin/` is empty.

## Spec Change Log

### Implementation record (2026-08-18)

No change to the intent contract. Two additions the contract permitted but did not name, both
docstring-only and both listed here so the diff has no unexplained lines:

1. `src/companion/app/images.py`'s `DISK_CACHE_WRITE_FAILURE_LIMIT` docstring carried **two more**
   `c8-2` references beyond the three the Code Map lists (`:401`, `:417` at baseline) — not
   "c8-2 will document this" but "both lifecycle entries now live on c8-2". Since this story
   declined both and re-recorded them as unbuilt, leaving those sentences would have left the
   module pointing at a story that had already answered. They now record the outcome (disclosed in
   the README, mechanism unbuilt, home unowned, forcing function named). The literal `99` is
   untouched — `test_images.py::test_the_limit_carries_its_reasoning` still passes.
2. `DiskCache`'s class docstring said the class "writes roughly 12 MB per deck viewed" and that
   "the real-bytes measurement belongs to **c10-3**". That measurement landed at the C3
   retrospective; both figures now read as the measured **8.5 MB**, with the ~124 KB / ~130 MB
   arithmetic named as the 38 % overestimate it was. Same rule as the README: this project does not
   ship a number it has already disproved.

The whole `src/companion/app/images.py` diff was verified **docstrings only** mechanically, not by
eye: `ast.parse` of the baseline and the working copy, with every docstring and bare string-literal
statement blanked, produce **identical `ast.dump` output**. No statement, expression or signature
moved.

`## Deferred from: story 15-2` **was** appended to `deferred-work.md` — two new residues, both
belonging to the guard rather than to the cache (the shell syntax around the documented commands is
unverified and the PowerShell block is unexecutable on this project's Linux CI; the footprint
figures are pinned by nothing). Nothing else in that file was restructured.

### Orchestrator verification and one guard strengthening (2026-08-18)

The Verification commands were re-run independently after the implementation returned, and the
matrix audit found **one row not actually covered**, which is recorded here rather than smoothed
over:

- **Matrix row 6 ("Command block missing") was only half-guarded.** `test_both_platforms_get_a_copy_
  pasteable_block` asserted `"```powershell" in section`, and the section carries **two** PowerShell
  blocks (inspect and clear). Deleting the PowerShell *inspect* block therefore left the token alive
  and the full suite stayed green — measured, not argued (`--expect-red` complained that the node
  "was not" red). The test is now
  `test_both_platforms_get_a_copy_pasteable_block_for_both_actions`: a `_fenced_blocks` helper
  parses each fence as `(language, body)`, and each platform must carry both an inspect verb
  (`du`/`find`, `Get-ChildItem`/`Measure-Object`) and a clear verb (`rm -rf`, `Remove-Item`).
  Re-planted with the same deletion: **RED**. Guard count unchanged at 11; suite unchanged at 3125.

The pre-existing environmental red was confirmed **at the baseline commit itself**, not by
inference: a `git worktree` at `6aa37f3` runs
`test_discovery.py::test_reader_returns_none_when_the_file_is_unreadable` and it fails there with
the same assertion (uid 0 ignores `chmod(0o000)`).

`uv run pytest -m integration` is **not clean in this container and cannot be**: 2 failed, 3 errors,
all five the real-embedder / RAG tests, all from
`ValueError: Could not load model BAAI/bge-small-en-v1.5 from any source` — the sandbox proxy
answers `403` for `huggingface.co`. Nothing in this change reaches the search layer. 31 passed,
19 skipped.

### Firing proof (probe harness)

Every line below is pasted from `scripts/probe_harness` stdout. The tree was staged (`git add -A`)
before each plant and restored with `git checkout --` after it.

**Baseline / green expectation**

```
full suite (-m 'not integration'): 3125 collected, 1 failed, 0 errored, exit 1
  RED    tests/unit/companion/test_discovery.py::test_reader_returns_none_when_the_file_is_unreadable
```

That one red is **pre-existing and environmental**, not this story's: the container runs as uid 0,
so the test's `chmod(0o000)` does not make the file unreadable to root and `read_discovery()`
returns a record instead of `None`. Verified by `git stash -u` → the same single failure on the
untouched baseline tree → `git stash pop`. Nothing else in the suite is red, so the suite is green
modulo a root-user artifact that predates this change.

**Plant 1 — `CACHE_DIRECTORY_NAME = "image_cache2"`, README untouched** (`--expect-red
'…::test_the_documented_directory_is_the_shipped_directory_name'`, exit 0):

```
full suite (-m 'not integration'): 3125 collected, 14 failed, 0 errored, exit 1
  RED    tests/unit/companion/test_discovery.py::test_reader_returns_none_when_the_file_is_unreadable
  RED    tests/unit/companion/test_image_cache_docs.py::TestTheImageCacheSectionMatchesTheShippedCache::test_the_documented_directory_is_the_shipped_directory_name
  RED    tests/unit/companion/test_image_cache_docs.py::TestTheImageCacheSectionMatchesTheShippedCache::test_the_documented_layout_is_the_path_the_shipped_code_builds
  RED    tests/unit/companion/test_image_cache_docs.py::TestTheImageCacheSectionMatchesTheShippedCache::test_the_documented_command_resolves_the_shipped_cache_root
  RED    tests/unit/companion/test_image_cache_docs.py::TestTheImageCacheSectionMatchesTheShippedCache::test_the_leftovers_list_names_every_file_an_uninstall_leaves
  RED    tests/unit/companion/test_images.py::TestTheCachePath::test_the_path_is_the_architecture_decision_spelled_out
  RED    tests/unit/companion/test_images.py::TestTheCacheReadAndWrite::test_the_file_lands_at_exactly_the_constructed_path
  RED    tests/unit/companion/test_images.py::TestTheCacheReadAndWrite::test_an_ordinary_png_card_lands_as_png_on_disk
  RED    tests/unit/companion/test_images.py::TestTheCacheReadAndWrite::test_a_rewrite_under_the_other_extension_displaces_the_stale_sibling
  RED    tests/unit/companion/test_images.py::TestTheWriteIsAtomic::test_the_temp_file_is_uniquely_named_and_sits_beside_its_target
  RED    tests/unit/companion/test_images.py::TestBuildingTheCache::test_the_root_is_resolved_under_the_data_directory
  RED    tests/unit/companion/test_images.py::TestBuildingTheCache::test_building_one_creates_the_root
  RED    tests/unit/companion/test_images.py::TestBuildingTheCache::test_a_root_that_cannot_be_created_disables_the_cache_rather_than_raising
  RED    tests/unit/companion/test_routes_session.py::TestTheStoreIsCreatedByTheLifespan::test_nothing_is_written_to_the_data_directory_by_minting
```

The spec predicted "RED for that node id **and no other**" and that was **wrong**, so it is
recorded rather than glossed: nine of the collateral reds are **pre-existing tests that pin the
string `image_cache` as a literal** (`test_images.py`, `test_routes_session.py:581`) and would fire
on any rename of that constant with or without this story. The remaining three are this guard's own
sibling assertions — the layout example, the executed one-liner and the leftovers list all embed
the directory name, so a rename is *supposed* to move all four. Nothing red is unexplained, and the
named node id fired for the planted reason.

Revert: `git checkout -- src/companion/app/images.py` → `git diff --exit-code
src/companion/app/images.py` → **exit 0**.

**Plant 2 — README heading renamed to `### Picture cache (companion app)`, code untouched**
(`--expect-red '…::test_the_documented_section_exists'`, exit 0):

```
full suite (-m 'not integration'): 3125 collected, 12 failed, 0 errored, exit 1
  RED    tests/unit/companion/test_discovery.py::test_reader_returns_none_when_the_file_is_unreadable
  RED    …::test_the_documented_section_exists
  RED    …::test_the_documented_directory_is_the_shipped_directory_name
  RED    …::test_the_documented_location_follows_the_data_dir_override
  RED    …::test_the_documented_layout_is_the_path_the_shipped_code_builds
  RED    …::test_the_documented_command_resolves_the_shipped_cache_root
  RED    …::test_both_platforms_get_a_copy_pasteable_block
  RED    …::test_the_eviction_paragraph_states_the_measured_footprint
  RED    …::test_the_staleness_paragraph_names_its_cause_and_its_remedy
  RED    …::test_the_leftovers_list_names_every_file_an_uninstall_leaves
  RED    …::test_the_two_cache_disable_behaviours_are_disclosed
  RED    …::test_ordinary_prose_edits_elsewhere_in_the_readme_do_not_move_this_guard
```

(`…` = `tests/unit/companion/test_image_cache_docs.py::TestTheImageCacheSectionMatchesTheShippedCache`.)
This is the **non-vacuity proof in full**: **all eleven** assertions in the module go red on a
missing heading, each naming the heading it looked for. Not one of them passes over an empty scan.

Revert: `git checkout -- README.md` → `git diff --exit-code README.md` → **exit 0**; the module is
back to 11 passed.

### Other verification

- `uv run ruff check . --fix && uv run ruff format .` — **All checks passed / 333 files left
  unchanged** (two E501s were introduced and fixed during the work).
- `uv run mypy src/` — **Success: no issues found in 94 source files**.
- `uv run python -m scripts.build_plugin` — rebuilt; `git status --porcelain -- plugin/` names
  exactly `plugin/server/README.md` and `plugin/server/src/companion/app/images.py`, the two mirrors
  of the two changed sources. A second run produced no further change (idempotent), and
  `diff plugin/server/README.md README.md` is empty.

### Manual checks

- **The documented bash block was run verbatim on this container.** The one-liner printed
  `/root/.local/share/artificial-planeswalker/image_cache`; after planting a synthetic 90 KB entry
  at `81/813d0434-…/normal_0.jpg`, `du -sh` reported `104K`, `find … -type f | wc -l` reported `1`,
  and the documented `rm -rf "$CACHE"` removed the directory. The path it named is the one
  `images.cache_root()` resolves — which the guard also asserts, in-process, under a
  `PLANESWALKER_DATA_DIR` override.
- **The PowerShell block was NOT executed.** This is a Linux container with no `pwsh`; the block's
  Python payload is byte-identical to the bash block's and is executed by the guard, but its
  `$Cache = …` capture, `Get-ChildItem`/`Measure-Object` and `Remove-Item -Recurse -Force` are
  unverified. Ledgered as residue in `deferred-work.md` under `## Deferred from: story 15-2`
  rather than implied to have been run.
- **Read as a first-time user.** The section answers, in order and without following a link: where
  it is (`<data dir>/image_cache/`, following `PLANESWALKER_DATA_DIR`), what is inside it (the
  shard, with a concrete example path), how big it gets (measured, with the superseded estimate
  named), how to look at it and how to delete it (two blocks per platform), why an old picture may
  persist and how to fix that, what an uninstall leaves behind (three files, one of them
  deliberately), and the two ways the cache can switch itself off with the restart that fixes them.


## Review Triage Log

### 2026-08-18 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 19: (high 0, medium 6, low 13)
- defer: 4: (high 0, medium 0, low 4)
- reject: 9: (high 0, medium 0, low 9)
- addressed_findings:
  - `[medium]` `[patch]` P1 — **the clear command's target was never tied to the verified path.**
    Measured by a reviewer: rewriting `rm -rf "$CACHE"` to `rm -rf ~/.cache/planeswalker-images`,
    leaving the correct one-liner above it untouched, kept all eleven guards green — the payload
    test still passed (the payload was right) and the block test still passed (`rm -rf` was
    present). `test_each_clear_command_deletes_the_path_its_own_block_resolved` now captures each
    block's assignment target and asserts the deletion argument dereferences that same name, on
    both platforms.
  - `[medium]` `[patch]` P2 — `_extract_section` terminated only on `## `/`### ` and ignored fenced
    blocks, so a `#### ` sub-subsection would extend the section into prose it does not own and a
    `### ` line inside a shell block would truncate it. Now any ATX level, fence-aware, with both
    rules tested rather than asserted in prose, plus a duplicate-heading assertion.
  - `[medium]` `[patch]` P3 — `_documented_one_liners` matched `python -c "…"` anywhere in the
    section, including prose, and `_run` `exec`s what it returns. Extraction is now restricted to
    fenced-block bodies and every payload must start with `from src import paths`, so a future
    documented command that reached for `shutil.rmtree` could not be executed by the suite.
  - `[medium]` `[patch]` P4 — the commands need the checkout and `uv` (`ModuleNotFoundError` when
    run from `/tmp`), which collided with the section's own "deleting the checkout does not touch
    the data directory". The precondition is stated, and the post-uninstall reader is pointed at
    the per-OS path in the data-dir table and told that deleting that directory is the one step
    that removes everything.
  - `[medium]` `[patch]` P5 — the footprint arithmetic did not close: 8.5 MB ÷ 99 ≈ 86 KB against
    the 90 KB quoted beside it, and "38 %" was the per-tile ratio attached to a sentence about the
    per-deck figure. Both numbers are now stated as separate measurements, and the 38 % names the
    comparison it is of.
  - `[medium]` `[patch]` P6 — closing the unbounded-cache ledger entry retired the *eviction*
    question with it: the two lifecycle entries are about the cache disabling itself, not about
    size, so nothing owned "should this ever be bounded, now that we have a measurement". Split
    into its own open entry with a forcing function.
  - `[low]` `[patch]` P7 — `_NUMBER_WORDS[limit]` raised `KeyError` for a limit outside 1-6,
    swallowing the message it exists to print; `.get` with a numeric fallback, as its sibling
    already did.
  - `[low]` `[patch]` P8 — `_run` was called twice on failure, so the message could disagree with
    the value tested.
  - `[low]` `[patch]` P9 — a flattened `_cache_path` would `IndexError` on `parts[1]` instead of
    failing by name.
  - `[low]` `[patch]` P10 — an unterminated fence silently dropped its block, so a missing-block
    failure would have named the wrong cause.
  - `[low]` `[patch]` P11 — `Remove-Item` errored on a not-yet-created cache where `rm -rf` does
    not; `-ErrorAction SilentlyContinue`, plus a line saying "no such file" means nothing has been
    cached yet.
  - `[low]` `[patch]` P12 — resolving the path creates the data directory as a side effect; said
    so rather than letting an inspect command surprise the reader.
  - `[low]` `[patch]` P13 — "this project's entire 40-deck, 1,061-distinct-card library" is a
    private referent in a public README; reframed as "a library of ~1,000 distinct printings".
  - `[low]` `[patch]` P14 — the section quantified disk but never the cost of getting the bytes
    back; clearing now states the re-fetch (~10 s for a 100-card deck, needs a connection).
  - `[low]` `[patch]` P15 — "documented choice" was incomplete without saying there is no opt-out,
    no size cap setting, and no way to relocate `image_cache/` on its own.
  - `[low]` `[patch]` P16 — "the table at the top of this section" is ambiguous read from inside a
    subsection that contains no table; now an explicit link to *Where the data lives*.
  - `[low]` `[patch]` P17 — both ledger closures struck a mid-paragraph `Home:` line rather than
    the entry headline, so the entries still read as open to a headline scan; matched the file's
    own closure idiom.
  - `[low]` `[patch]` P18 — the `epic :3185-3212` citation was dropped from
    `CACHE_DIRECTORY_NAME`'s docstring when its forward reference was retired; restored beside the
    README pointer so traceability survives.
  - `[low]` `[patch]` P19 — the silent-half test hardcoded a neighbouring section's heading
    (coupling this guard to a title it does not own) and proved extraction bounding only; it now
    anchors on `SECTION_HEADING` and exercises all three trailing heading levels.

Rejected as noise or as contrary to a standing project ruling (9): guarding the `plugin/` README
mirror by assertion (CI rebuilds and diffs it — byte-identical by construction); re-homing the two
lifecycle entries on a named future story (`Home: unowned` with a forcing function is this file's
own idiom, and inventing an owner is how a ledger acquires fiction); indented fenced blocks
(nothing in this README indents a fence, and `lstrip` would misparse a fence inside a list);
merging inspect and clear into one block per platform (a reader still gets both commands); listing
`cards.db-wal`/`-shm` among the leftovers (the line orients, it is not an inventory); guarding
`rm -rf ""` when the one-liner fails (it fails safely and loudly); `uv` writing to stdout before
the path (`uv run` diagnostics go to stderr); the empty `## Review Triage Log` heading (this entry
fills it); and the companion row at `README.md:28` still reading "(in development)" with no pointer
to this section — that is Story 15.1's standing deferral, closed by Story 15.4.

## Design Notes

**Why the measured 8.5 MB and not the epic's 12 MB.** The epic asks for "roughly 12 MB per 100-card
deck", which was `12 MB ÷ 99 tiles ≈ 124 KB` arithmetic taken from its own acceptance observation.
The C3 retrospective then fetched all 99 distinct ids of a real deck through the real route and
measured **~90 KB** per tile — the ledger records the epic's figure as a **38 % overestimate** and
hands this story "a measured footprint rather than a guess", which is also what the epic's own
constraint sentence demands ("sized against a real measured footprint rather than guessed"). Quoting
12 MB as fact would ship a number this project has already disproved; dropping 12 MB silently would
leave the two documents disagreeing with no explanation. Both appear, one labelled measured.

**Why a guard on prose.** This README section states four things that are true only because a
constant currently says so — the directory name, the shard width, the entry filename shape, and
which environment variable moves them. `test_images.py`'s wire-prose gate is the precedent: key the
pin on the constants, never on literals, so it moves with any rename that also updates the prose and
fires on one that does not. Executing the README's own one-liner is the same discipline applied to a
command: a documented `rm -rf` that resolves the wrong directory is the one defect in this story that
would actually cost a user something.

**Declared residue** (state it in the guard's docstring, do not claim completeness): the guard proves
the *Python* path expression resolves the real root; it does not execute `du`, `rm -rf`,
`Get-ChildItem` or `Remove-Item`, so a typo in the surrounding shell syntax is a reviewer's
judgement. It reads one README section by heading, so prose that contradicts the section from
elsewhere in the file is invisible to it. The footprint figures are measurements from a dated
retrospective with no constant to key on — they are pinned by nothing and age with the corpus.

**Three leftovers, not two.** The epic names the image cache and the discovery file. `companion.lock`
is a third: c1-9's ruling #4 made it a zero-byte file that outlives every run *on purpose* (unlinking
it would hand the next launch a different inode and let two processes both hold the lock), and homed
documenting it here. A leftovers list that omits a file the user will find is not a disclosure.

## Verification

**Commands:**
- `uv run ruff check . --fix && uv run ruff format .` -- expected: clean.
- `uv run mypy src/` -- expected: clean.
- `uv run python -m scripts.probe_harness --expect-green` -- expected: full suite green; record the
  collected count from the proof line.
- `uv run python -m scripts.probe_harness --expect-red '<the drift-gate node id>'` after renaming
  `images.CACHE_DIRECTORY_NAME`'s value (e.g. to `image_cache2`) without touching the README --
  expected: RED for that node id and no other. Revert; `git diff --exit-code src/companion/app/images.py`.
- `uv run python -m scripts.probe_harness --expect-red '<the section-anchor node id>'` after
  renaming the README heading -- expected: RED, proving the guard cannot pass vacuously. Revert;
  `git diff --exit-code README.md`.
- `uv run python -m scripts.build_plugin && git status --porcelain -- plugin/` -- expected: empty
  once the regenerated mirror is committed.

**Manual checks:**
- Paste every harness proof line into this spec's record — a hand-transcribed count is not evidence.
- Run the documented inspect command verbatim in `bash` and read what it prints; confirm it names an
  `image_cache` directory under the resolved data dir. (The PowerShell block cannot be executed on
  this Linux container — say so in the record rather than implying it was run.)
- Read the section as a first-time user: it must answer "where is it, how big will it get, how do I
  look at it, how do I delete it, and what is left after I uninstall" without following a link.


## Auto Run Result

Status: done
Baseline: `6aa37f3` → this change set, on `claude/hello-7v0acf` (`1616f71` planning, `21c9ac4`
implementation, plus the review patch commit).

**Summary.** The unbounded image cache is now a documented choice rather than a surprise.
`README.md`'s *Where the data lives → Image cache (companion app)* section states where the cache
is (`<data dir>/image_cache/`, following `PLANESWALKER_DATA_DIR`, movable only with the rest of the
data directory), how it is laid out (two-character shard, `<size>_<face>.<ext>`, with a derived
example), how to inspect and clear it on both platforms, that nothing is ever evicted and what that
costs in measured bytes, why a data refresh keeps serving the old picture and how to force a
refetch, what an uninstall leaves behind, and the two ways the cache switches itself off with the
restart that fixes them. The prose is not trusted: `tests/unit/companion/test_image_cache_docs.py`
keys every load-bearing claim on the shipped symbols, executes the README's own path one-liner
under a data-dir override, and pins each clear command to the path its own block resolved.

**Files changed** (7; `plugin/` is a generated mirror rebuilt by `scripts/build_plugin.py`):

- `README.md` — the new stewardship section (97 lines) under *Where the data lives*.
- `tests/unit/companion/test_image_cache_docs.py` (new, 13 tests) — the drift guard, with a
  non-vacuity anchor, fence-aware bounded extraction, an executed payload restricted to fenced
  blocks of a known shape, the clear-target binding, and declared residue.
- `src/companion/app/images.py` — docstrings only (proved mechanically by comparing docstring-blanked
  ASTs): five `c8-2` forward references retired in favour of the shipped README section, the
  disproved 12 MB / 130 MB figures corrected to the measured 8.5 MB, epic traceability kept.
- `_bmad-output/implementation-artifacts/deferred-work.md` — two entries closed in the file's own
  headline-strike idiom, two lifecycle entries re-recorded as disclosed-but-unbuilt with a forcing
  function, one new entry carrying the still-open eviction question, and a
  `## Deferred from: story 15-2` section for the two new residues.
- `_bmad-output/implementation-artifacts/spec-15-2-…md` — this record.
- `plugin/server/README.md`, `plugin/server/src/companion/app/images.py` — regenerated mirrors.

**Review findings.** Four layers (Blind Hunter, Edge Case Hunter, Verification Gap, Intent
Alignment). **0 intent gaps, 0 spec defects, 19 patches applied** (6 medium, 13 low), **4 deferred**
(all low — see frontmatter), **9 rejected**. Two of the six medium findings were measured by a
reviewer rather than argued: a mis-targeted `rm -rf` beside a correct one-liner left the whole suite
green, and the documented commands fail with `ModuleNotFoundError` when run from outside the
checkout — the case the section's own uninstall paragraph describes.

**Follow-up review recommended: true.** Patched this pass: high 0, medium 6, low 13 →
`3 × 6 + 1 × 13 = 31`, at or above the threshold of 5.

**Verification** (re-run from the patched tree):

- `uv run ruff check . --fix && uv run ruff format .` — All checks passed; 333 files unchanged.
- `uv run mypy src/` — Success: no issues found in 94 source files.
- `uv run python -m scripts.probe_harness --expect-green` —
  `full suite (-m 'not integration'): 3127 collected, 1 failed, 0 errored, exit 1`. The single red
  is `test_discovery.py::test_reader_returns_none_when_the_file_is_unreadable`, **confirmed failing
  at the baseline commit itself** in a separate `git worktree` at `6aa37f3`: this container runs as
  uid 0, so `chmod(0o000)` does not make a file unreadable to root. Not caused by, and not fixable
  by, this change.
- **Firing proof 5 (the review's own finding).** `rm -rf "$CACHE"` rewritten to
  `rm -rf ~/.cache/planeswalker-images`, the one-liner above it untouched:
  `3127 collected, 2 failed, 0 errored, exit 1` /
  `RED …::test_each_clear_command_deletes_the_path_its_own_block_resolved` (the other red is the
  environmental one above). Before the patch this exact plant was **green**. Reverted;
  `git diff --exit-code README.md` clean.
- Earlier proofs, re-stated: constant rename → the directory guard RED; README heading rename → all
  guards RED (non-vacuity); shard width changed → the layout guard RED; PowerShell inspect block
  deleted → RED only after the block guard was strengthened.
- `uv run pytest -m integration` — 31 passed, 19 skipped, 2 failed + 3 errors, all five the real
  embedder / RAG tests failing on `Could not load model BAAI/bge-small-en-v1.5 from any source`
  (this sandbox's proxy returns 403 for `huggingface.co`). Nothing in this change reaches the
  search layer.
- `uv run python -m scripts.build_plugin` — rebuilt; the two mirrors regenerate identically and a
  re-run after commit leaves `git status --porcelain -- plugin/` empty.

**Matrix test audit.** All six I/O-matrix rows are covered by tests that ran and passed in the green
run: docs-current by the whole class, directory rename by
`test_the_documented_directory_is_the_shipped_directory_name` (proved by plant 1), layout change by
`test_the_documented_layout_is_the_path_the_shipped_code_builds` (plant 3), the override by
`test_the_documented_command_resolves_the_shipped_cache_root` (behavioural, under
`isolated_data_dir`), section removal by `test_the_documented_section_exists` (plant 2), and the
missing-command row by `test_both_platforms_get_a_copy_pasteable_block_for_both_actions` — which is
the row the audit found **uncovered** before the guard was strengthened, and which now fires (plant
4).

**Residual risks.**

- The documented commands need the checkout and `uv`. A reader who deleted the checkout is pointed
  at the per-OS path instead, in words the guard cannot execute.
- The PowerShell blocks are never run by any suite; their Python payload is byte-identical to the
  bash one and is executed, the cmdlets around it are reviewer-verified only.
- The footprint figures have no constant to key on and age with the corpus and with Scryfall's
  encoder; the guard asserts they are present and labelled measured, not that they are still true.
- The epic still carries the superseded ~12 MB at four sites — Story 15.3's scope.
- "Safe to delete at any time, running app or not" rests on `_write_atomically` re-creating the
  shard directory; nothing exercises delete-while-running.
- The eviction question stays open and unowned, now in its own ledger entry with a forcing function
  rather than folded into a closed one.

## Sprint journal (moved verbatim from sprint-status.yaml, 2026-08-25)

PR #85 MERGED 2026-08-18 at e424166 into feat/companion-epic-15 (1616f71 spec, 21c9ac4 implementation, a1c9081 review patches). README `Where the data lives -> Image cache (companion app)` documents location/shard/inspect/clear/no-eviction/staleness/uninstall; tests/unit/companion/test_image_cache_docs.py (13 tests) keys the prose to shipped symbols and executes the documented one-liner. Review: 4 layers, 0 intent gaps, 0 spec defects, 19 patches, 4 deferred (low), 9 rejected; followup_review_recommended: true (score 31 >= 5) - NOT yet run. deferred-work.md: 3 entries closed, 1 new (whether the cache should ever be bounded - Home: unowned), plus a `Deferred from: story 15-2` section.
