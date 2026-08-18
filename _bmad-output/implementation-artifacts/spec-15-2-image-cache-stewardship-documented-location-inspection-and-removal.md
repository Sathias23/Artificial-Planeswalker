---
title: 'Image cache stewardship — documented location, inspection and removal'
type: 'chore'
created: '2026-08-18'
baseline_revision: '6aa37f368972db9f380ded004b32a30e09488a9f'
status: 'in-progress'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-15-context.md'
warnings: ['oversized']
deferred: []
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

## Review Triage Log

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
