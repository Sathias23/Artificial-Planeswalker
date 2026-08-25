---
title: 'C6 R2 — vitest probe harness (the frontend half)'
type: 'chore'
created: '2026-08-13'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'b90fa091e619a2654a98c70ace28e50a67289583'
branch: 'chore/c7-prep-r2-vitest-probe-harness'
context:
  - '{project-root}/scripts/probe_harness.py'
  - '{project-root}/ui/vite.config.ts'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `scripts/probe_harness.py` owns the pytest half of firing proofs; the frontend has none,
so every story rebuilds the validation by hand — ~20+ plants hand-run across six C6 stories. The C4
retro recorded five *probe-harness lies* under which **every probe reads CAUGHT for free**: a
lowercase-drive `cwd` (twice), a standalone-runner crash, `shell=True` on Windows, and an unparseable
TSX file that shrank collection to 1,596 from ~1,655. c6-5 then sighted a vitest worker-fork crash
that silently drops a whole test **file** — twice.

**Approach:** A sibling script, `scripts/vitest_probe_harness.py`, that owns cwd and argv so the run
cannot be narrowed or misinvoked, validates the collected count before scoring anything, and
**refuses** to return a verdict on a run carrying a crash signature. Epic C6 retrospective item
**R2**, scope fixed at its four recorded requirements. Termination clause: not built by the C7 retro
→ formally decline.

## Boundaries & Constraints

**Always:**
- **Argv ownership, exactly as the pytest half.** The caller supplies *expectations only* — never a
  test path, `-t`, `--project`, or any vitest flag. The run is CI's own command, `npm test`.
- Resolve the ui directory via `Path(__file__).resolve()`, which normalises `c:` → `C:` (measured).
  Never `os.path.abspath`, which preserves a lowercase drive (measured).
- Resolve npm via `shutil.which`. `subprocess.run(["npm", …])` raises `FileNotFoundError` on Windows
  (measured) — that is what drove lie #4 to `shell=True`. `shell=False`, always.
- Split parsing from running: a pure function over captured text, so every negative control is a
  fixture transcript that needs no npm.
- **A refusal is not a verdict.** Anything making a run non-evidence (crash signature, wrong root,
  unparseable summary, tally mismatch) reports as a REFUSAL and exits non-zero *without* scoring
  `--expect-red`/`--expect-green` — the `probe_harness.py:180` precedent, which exists so a true
  complaint is never paired with false ones.
- **The collected count is the scoring criterion, not the exit code** (ruled at `c6-3:326`: "validate
  the collected count, not the exit code, before scoring any run"). Record npm's exit status in the
  proof line as corroboration; never let it alone decide a verdict.
- Every constant that could narrow the run is a module-level literal carrying a comment that names
  the failure it prevents; match the existing harness's comment density.

**Ask First:**
- The control run coming back RED on a pristine tree for any reason other than the known cold-eslint
  flake — HALT and report; never repair a test to make the control pass.
- Any edit to `ui/vite.config.ts`, `ui/package.json`, or an existing test to make the harness work.

**Never:**
- No new npm dependency, no new npm script, no change to what `npm test` means.
- Do not fix the cold-eslint timeout flake (that is **R5**) or the worker-fork crash itself (filed in
  `deferred-work.md`). This harness only refuses to *score* a run carrying them.
- No committed expected-count constant that stories must bump — the control run produces the number.
- No plant/revert automation and no git operations: the harness observes runs, the author owns the
  plant.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Do-nothing control | `--control` on a clean tree, run warm | Green run; prints the proof line and the literal `--expect-total 2123` to paste | Non-zero REFUSAL if not green |
| Planted probe fires | `--expect-total 2123 --expect-red AgentView` | Total matches and the id is among the FAILs → exit 0 | N/A |
| Plant broke a file's parse | Run reports total 2098 against `--expect-total 2123` | REFUSAL: collection shrank by 25 (lie #5) | Exit non-zero; expectations unscored |
| Worker-fork crash | Output carries `[vitest-pool]` / `Worker exited unexpectedly` | REFUSAL: crash signature; run discarded | Exit non-zero |
| Silent file drop, no signature | ` Test Files  74 passed (75)` | REFUSAL: categories sum 74 ≠ total 75 | Exit non-zero |
| Wrong resolved root | RUN-banner root ≠ the owned ui path | REFUSAL: root mismatch — a cross-check on lies #1–2, which owning the cwd already prevents | Exit non-zero |
| npm not on PATH | `shutil.which("npm")` returns None | RuntimeError naming npm, raised before any run | Exit non-zero |

</frozen-after-approval>

## Code Map

- `scripts/probe_harness.py` — the pytest half and the shape to mirror: owned `_RUN_ARGV`/
  `_COLLECT_ARGV` (45-67), `ProbeResult.proof_line` (112), the non-evidence early return (180-184),
  substring `--expect-red` matching (212). **Its docstring lines 19-23 name this script as the
  missing half** and must be updated by this work.
- `ui/vite.config.ts:46-79` — **two** vitest projects (`node` → `tests/**`, jsdom `dom` → `src/**`).
  This project resolution is precisely what a lowercase-drive `cwd` breaks (lies #1–2), and it makes
  FAIL lines project-prefixed.
- `.github/workflows/ci.yml:100-137` — the `frontend` job: `working-directory: ui`, `run: npm test`.
  The owned argv must equal this and nothing more. (C6 stories typed it by hand; c6-2:510 drifted to
  `npm test -- --run` — the variance argv ownership removes.)
- `scripts/cdp_harness.py:32-39` — the nearest committed precedent, and it already encodes both
  fixes: `Path.resolve` because "a forward-slash `cwd` broke it twice", the `shell=True` note, and
  the principle to reuse — "a run that collected no assertions reads as a pass; every C4 probe
  harness that lied did so by producing zero results and being scored anyway."
- **No verbatim vitest output exists anywhere for the lowercase-drive failure** — it is recorded only
  qualitatively ("~67 failed suites", "resolves no vitest config"; `c6-5:327` and four siblings). Do
  not write a regex against a quoted string for that case; the defence is owning the cwd.
- **Measured on master `b90fa09`, 2026-08-13** — the two transcript shapes the parser targets:
  - green (warm, 6.33 s): ` RUN  v4.1.10 C:/Users/brads/Projects/Artificial-Planeswalker/ui`,
    ` Test Files  75 passed (75)`, `      Tests  2123 passed (2123)`
  - red (cold, 48.94 s): ` Test Files  1 failed | 74 passed (75)`,
    `      Tests  1 failed | 2122 passed (2123)`, and
    ` FAIL  |node| tests/lint-gates.test.ts > <suite> > <test>`
  - That cold run **reproduced C6 R5's eslint flake** (`setup 107.37s`, timeout at 5000 ms) —
    sighting #6, and the reason `--control` is specified warm.
- `tests/unit/search/test_build_card_embeddings_cli.py` — precedent for unit-testing a `scripts/`
  module; `tests/unit/test_paths.py` and `test_setup_bootstrap.py` establish the top-level home for
  repo-tooling tests, where the new test file belongs.
- `_bmad-output/implementation-artifacts/epic-c4-retro-2026-08-07.md:128-139` — the five-lies table
  (read-only evidence; do not edit).

## Tasks & Acceptance

**Execution:**
- [x] `scripts/vitest_probe_harness.py` -- new module: owned `_UI_DIR` / npm resolution / `_RUN_ARGV`;
  a frozen `VitestResult` dataclass with `proof_line()`; a pure parse function over captured text;
  a check function separating REFUSALS from expectation complaints; `main()` exposing `--control`,
  `--expect-total`, `--expect-red` (repeatable) and `--expect-green` -- gives the frontend the argv
  ownership the pytest half already has.
- [x] `tests/unit/test_vitest_probe_harness.py` -- new: one fixture transcript per I/O Matrix row,
  including the **do-nothing negative controls** — the green transcript must score NOT-caught against
  an `--expect-red`, and each recorded lie shape must REFUSE rather than certify -- these are the
  part the C4 retro called least likely to be re-invented correctly. Every refusal test gets its
  **positive twin** in the same file (C6 R8's standing agreement: a harness that refuses everything
  satisfies every refusal assert).
- [x] `scripts/probe_harness.py` -- replace the forward-looking sentence in its "What this cannot see"
  paragraph (19-23) with a one-line pointer to the new script -- honours the standing rule that no
  new forward-looking cross-module prose ships in docstrings.

**Acceptance Criteria:**
- Given a pristine `ui/` tree run warm, when `--control` runs, then it prints a green proof line and
  the literal `--expect-total 2123` line for the planted run to consume.
- Given a transcript whose `Tests` categories sum below the parenthesised total, when it is parsed,
  then the harness reports a REFUSAL and scores no expectation.
- Given npm is invoked, when the harness builds its command, then it uses the `shutil.which`-resolved
  path with `shell=False` and a cwd whose drive letter is uppercase.
- Given a real violation planted in a `src/**` component, when scored with the control's
  `--expect-total`, then the harness reports that node id RED and exits 0 — and reverting the plant
  returns it to green. This firing proof is required before the work is claimed done.

## Design Notes

The `--control` mode is not a convenience: it is requirement #4 (do-nothing negative controls) and
requirement #1 (a validated collected count) collapsed into one mechanism. A control run proves the
unplanted tree reads NOT-caught *and* emits the only number a planted run may be scored against.
That binds the baseline to the tree by *workflow proximity*, not by identity: a stale
`--expect-total` from an older control still scores, and the harness can only see the mismatch it
causes, never the staleness itself. Re-run `--control` whenever the tree moves under you.

```
$ uv run python -m scripts.vitest_probe_harness --control
vitest: 75 files / 2123 tests, 0 failed, exit 0
CONTROL GREEN — score the planted run with:  --expect-total 2123

$ uv run python -m scripts.vitest_probe_harness --expect-total 2123 --expect-red AgentView
```

Internal consistency and the absolute total catch *different* lies and both are needed: a silently
dropped file leaves `74 passed (75)` (sum ≠ total), while a file that fails to parse shrinks both
numbers together and is invisible without the control's baseline.

## Verification

**Commands:**
- `uv run pytest tests/unit/test_vitest_probe_harness.py` -- expected: all pass, and no npm process is
  spawned (every case is a fixture transcript)
- `uv run python -m scripts.vitest_probe_harness --control` -- expected: green proof line plus the
  `--expect-total` paste line; run warm, after one prior `npm test`
- `uv run python -m scripts.probe_harness --expect-green` -- expected: the Python suite still green
  after the docstring edit
- `uv run ruff check . && uv run ruff format --check .` -- expected: clean

**Manual checks (if no CLI):**
- The firing proof: **stage the tree first** (C6 R8 — c6-7's unstaged `git checkout` revert deleted a
  whole component), plant a real violation in a `src/**` component, confirm the harness reports it RED
  at the control's total, then revert and confirm `git diff --exit-code <file>` is clean and the
  suite is green again. Record both proof lines verbatim.

## Suggested Review Order

**The design intent — argv ownership**

- Entry point: the owned cwd, normalised so `c:` can never reach vitest.
  [`vitest_probe_harness.py:61`](../../scripts/vitest_probe_harness.py#L61)

- The whole invocation the caller cannot narrow — CI's command, nothing more.
  [`vitest_probe_harness.py:67`](../../scripts/vitest_probe_harness.py#L67)

- npm resolved to its `.CMD`; why `["npm", …]` alone raises on Windows.
  [`vitest_probe_harness.py:393`](../../scripts/vitest_probe_harness.py#L393)

- The bounded run: explicit utf-8 (the cp1252 crash the firing proof found) and a timeout.
  [`vitest_probe_harness.py:427`](../../scripts/vitest_probe_harness.py#L427)

**Refusals — the part that decides what counts as evidence**

- `check()` returns `(refusals, complaints)`; a non-empty refusal empties complaints.
  [`vitest_probe_harness.py:258`](../../scripts/vitest_probe_harness.py#L258)

- Crash-signature matching, line-anchored so quoting a signature cannot refuse forever.
  [`vitest_probe_harness.py:82`](../../scripts/vitest_probe_harness.py#L82)

- Case-sensitive root cross-check — the observable half of the drive-letter defence.
  [`vitest_probe_harness.py:248`](../../scripts/vitest_probe_harness.py#L248)

- Test-level FAIL ids only, so a file-level FAIL cannot offset an unnamed failure.
  [`vitest_probe_harness.py:182`](../../scripts/vitest_probe_harness.py#L182)

**The CLI contract**

- Refusal printed before anything pasteable; argument shapes rejected up front.
  [`vitest_probe_harness.py:464`](../../scripts/vitest_probe_harness.py#L464)

**Guards worth reading closely (review-added)**

- Drift guard: the owned invocation checked against `ci.yml`, not against itself.
  [`test_vitest_probe_harness.py:863`](../../tests/unit/test_vitest_probe_harness.py#L863)

- The narrowing detector's own non-vacuity proof.
  [`test_vitest_probe_harness.py:854`](../../tests/unit/test_vitest_probe_harness.py#L854)

- Exit-code veto: green tally + non-zero exit refuses (the c5-1 hole, vitest side).
  [`test_vitest_probe_harness.py:438`](../../tests/unit/test_vitest_probe_harness.py#L438)

- Drive-letter refusal, now case-flipped so ubuntu CI actually runs it.
  [`test_vitest_probe_harness.py:464`](../../tests/unit/test_vitest_probe_harness.py#L464)

**Peripherals**

- The measured fixtures every negative control replays.
  [`test_vitest_probe_harness.py:30`](../../tests/unit/test_vitest_probe_harness.py#L30)

- Sibling docstring: forward-looking prose replaced with a pointer.
  [`probe_harness.py:19`](../../scripts/probe_harness.py#L19)
