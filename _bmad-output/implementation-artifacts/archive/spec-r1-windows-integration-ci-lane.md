---
title: 'R1 — Windows integration CI lane for the companion real-socket test'
type: 'chore'
created: '2026-08-09'
status: 'done'
review_loop_iteration: 0
baseline_commit: '5cd140be6cf50287f46b3e5483f2dcb47975ade0'
branch: 'chore/c6-prep-r1-windows-ci-lane'
context:
  - '{project-root}/.github/workflows/ci.yml'
  - '{project-root}/tests/integration/companion/test_live_backend.py'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `tests/integration/companion/test_live_backend.py` is the only test anywhere that boots
a real backend process and drives a real socket — the whole of the repo's coverage of the process
boundary AD-10 names — and **no CI job runs it.** Both `quality` jobs are ubuntu running
`-m "not integration"`, which deselects it; its "passes on Windows" acceptance was discharged by a
local run recorded in c5-8's Dev Agent Record. A test with no automated home rots silently.

**Approach:** Add one Windows job to `.github/workflows/ci.yml` that installs the locked environment
and runs that directory, and correct the three shipped prose claims this change falsifies. Epic C5
retrospective action item **R1**; ruled YES at the retro (`dw:5668` region).

## Boundaries & Constraints

**Always:**
- Scope the lane **by PATH** — `uv run pytest tests/integration/companion/` — never a bare
  `-m integration`, which also collects the twice-sighted `test_list_decks_with_strategy_field`
  flake and the live-network Scryfall contract tests.
- Keep the job **single-purpose**: install, then run that one directory.
- Pin every `uses:` to a commit SHA with a version comment, matching the two existing jobs.
- Replacement prose states **current behaviour only** — no forward-looking claims about future
  stories or jobs (the standing rule adopted with R2).
- Do not tighten or loosen the test's timeouts. `_BOOT_DEADLINE = 30.0` is deliberately generous
  for a cold runner.

**Ask First:**
- `uv sync --locked` or the test failing on `windows-latest` for any reason other than a deliberately
  planted break — HALT and report; do not repair the test to make the lane pass.
- The firing proof coming back **green** on a planted break, or **red** on ubuntu — HALT. Either
  result means the lane is not measuring what it claims.

**Never:**
- No ruff, mypy, plugin-drift or frontend step in this job; no change to the `frontend` job's runner.
- No pytest source-reading guard over `ci.yml` (ruled out: pytest exit 5 / 4 already makes a
  scope-broken lane fail rather than pass vacuously).
- No companion pytest marker or scoped alias — that is **R4**, deliberately separate.
- No branch-protection / required-check changes; that is Brad's call after the lane is green.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Healthy run | Push or PR, tree as committed | Windows job collects exactly 1 test, passes | N/A |
| Real regression | Channel broken (e.g. restart reuses the previous token) | Windows job **red**, both ubuntu `quality` jobs green | Failing phase named; `_Backend.log_tail()` puts the child's own output in the message |
| Test gone / dir renamed or deleted | Nothing collected under the path | pytest exits 5 (or 4 if the pathspec does not resolve) → job red | Non-zero exit; the lane cannot pass on nothing |
| Child never boots | Backend exits or hangs before publishing `companion.json` | `AssertionError` in `_await_record` within 30 s | Child exit code + log tail in the message |

</frozen-after-approval>

## Code Map

- `.github/workflows/ci.yml` -- the only behavioural change. Match `quality` (ubuntu py3.12/3.13
  matrix) and `frontend` (ubuntu node 20) for style and SHA pins. The header comment at lines 3–8
  enumerates the jobs and asserts the pytest scope; both go stale.
- `tests/integration/companion/test_live_backend.py` -- the test being given a home. **Docstring
  only** — lines 35–39's "CI never runs it" paragraph is falsified here. Verified green locally:
  1 passed, 3.82 s, py3.12.13, win32.
- `ui/README.md:404` -- "protects a machine CI never runs on", about the `core.autocrlf` font guard.
  Windows becomes a CI machine; the `frontend` job that runs `fonts.test.ts` does not.
- `pyproject.toml` -- read-only. `addopts` carries **no `-m`**, so path scoping alone selects the
  test; `websockets>=12.0` is in the `dev` group and `httpx` in main deps, so plain
  `uv sync --locked` suffices.

## Tasks & Acceptance

**Execution:**

- [x] `.github/workflows/ci.yml` -- add a third job, `companion-integration`, `runs-on:
      windows-latest`, no matrix. Steps: Checkout → Install uv (`python-version: "3.12"`) →
      `uv sync --locked` → `uv run pytest tests/integration/companion/`, reusing the file's existing
      `uses:` SHA pins. Comment why it is separate from the `quality` matrix (different OS, different
      pytest scope; folding it in would run the unit suite twice on the slowest runner) and why it is
      not itself a matrix (the target is the process boundary, not version coverage) -- matches the
      "deliberately NOT folded into" precedent on the `frontend` job.
- [x] `.github/workflows/ci.yml` -- rewrite the header comment (lines 3–8) to name three jobs and
      state the scope accurately: the `quality` matrix runs `-m "not integration"`, the new job runs
      the companion integration directory. Keep the no-network statement true — the new job is
      loopback-only, so `frontend` remains the sole network consumer.
- [x] `tests/integration/companion/test_live_backend.py` -- rewrite the "**CI never runs it.**"
      paragraph to what is now true: a Windows job runs this directory on every push and PR; local
      runs stay path-scoped because a bare `-m integration` also collects the flake and the live
      Scryfall tests. Delete the sentence discharging the Windows acceptance via a local Dev Agent
      Record run. Keep the AD-2 reference.
- [x] `ui/README.md` -- narrow "a machine CI never runs on" to name the `frontend` job rather than CI
      as a whole -- the claim's substance survives; only the word "CI" is now wrong.
- [x] `ui/tests/fonts.test.ts:82` -- **ADDED DURING IMPLEMENTATION**, not in the approved plan. The
      same falsified claim in a fourth site: the comment on the `core.autocrlf` guard asserted flatly
      that "CI is ubuntu". Narrowed to name the `frontend` job, with the new Windows job named and
      its irrelevance to fonts stated. Found by grepping the frontend tests for content assertions on
      `ui/README.md` before trusting that edit — no test reads the README as a file, but this comment
      carried the identical claim. Same shape and same one-sentence cost as the README task; folding
      it in rather than deferring keeps the "no shipped sentence says CI never runs on Windows" AC
      literally true.

**Acceptance Criteria:**

- Given a push or PR, when CI runs, then a companion-integration job runs on `windows-latest`,
  collects **exactly one** test, and passes.
- Given the tree as committed, when that job's pytest step runs, then no network call beyond loopback
  is made and no `cards.db`, model, or secret is required.
- Given a temporary commit on the PR branch deliberately breaking the real channel, when CI runs,
  then the **Windows job is red and both ubuntu `quality` jobs are green** — and that commit is
  reverted before merge. This is the lane's firing proof: it shows the lane discriminates, and that
  it catches a failure nothing else in CI can see.
  - **Plant selection criterion (AMENDED — see change log entry 1).** The plant MUST sit in a seam
    the in-process suite structurally cannot reach: the subprocess dispatch, the bind→publish
    ordering, or the c1-8 reclaim path. It must NOT be `discovery.mint_token`
    (`test_discovery.py::test_minted_tokens_are_never_repeated` pins uniqueness and would redden
    ubuntu too) and must NOT be raw socket bind/fallback (`test_server.py`, `test_client.py` bind
    real loopback sockets on ubuntu).
  - **Local pre-check, mandatory before pushing the plant:** run `uv run pytest -m "not integration"`
    against the planted tree. If it goes RED, the plant is disqualified — it proves nothing about
    what this lane uniquely covers. Only a plant that leaves that run GREEN is worth pushing.
- Given the companion test directory is renamed or emptied, when the job runs, then pytest exits
  non-zero and the job is red rather than passing vacuously.
- Given the merged change, when the three edited files are read, then no sentence in any of them
  asserts that CI does not run this test or does not run on Windows.

**AC verification status at end of implementation** (step-03 forbids push / remote ops, so the two
ACs whose evidence only exists in a CI run are recorded as pending rather than claimed):

| AC | Status | Evidence |
|----|--------|----------|
| Job on windows-latest, collects exactly 1, passes | **Partly verified** | `yaml.safe_load` confirms three jobs and `companion-integration: windows-latest`; `--collect-only -q` = `1 test collected`; the test passes locally on win32 in 3.85 s. The CI-run half is pending the PR. |
| No network beyond loopback, no DB/model/secret | **Verified** | Passing run in an isolated `tmp_path` data dir; the test's httpx client sets `trust_env=False` and every URL is literal `127.0.0.1`. |
| Firing proof — planted break red on Windows, green on ubuntu | **PENDING — requires the PR** | Cannot be produced without a push. Procedure and revert are in Verification → Manual checks. **This AC is not satisfied and must not be reported as such until both run URLs exist.** |
| Renamed/emptied directory goes red, not vacuously green | **Verified** | Measured, not assumed: `--ignore` of the test file → exit **5**; a non-existent directory path → exit **4**. Both non-zero. |
| No shipped sentence claims CI does not run this test | **Verified** | `git grep` over all four edited files returns no match for the falsified claims. |

## Spec Change Log

**Entry 1 — the firing-proof plant did not discriminate (self-found during implementation).**
Triggering finding: the AC named "the restarted backend reuses the previous process's token" as the
plant. `tests/unit/companion/test_discovery.py::test_minted_tokens_are_never_repeated` pins token
uniqueness in the UNIT suite, so that plant reddens the ubuntu `quality` jobs too — destroying the
"green on ubuntu" half, which is the half that proves the lane sees something nothing else does.
Amended: replaced the named plant with a selection CRITERION plus a mandatory local pre-check
(`-m "not integration"` must stay green on the planted tree). Known-bad state avoided: pushing a
plant that reddens everything, then reading it as proof the lane works. **KEEP:** the two-sided
red-Windows/green-ubuntu shape, and the reason the proof is required at all (probe_harness.py is
pinned to `not integration` and structurally cannot plant here).

**Entry 2 — the sweep verification was scoped to the fix, not to the falsehood (Blind Hunter).**
Triggering finding: the AC read "when *the three edited files* are read…" and the verification
command was `git grep "CI never runs it"` — the exact phrase already being repaired. Both are
satisfiable by construction regardless of how many un-edited files carry the same claim, and three
did: `.gitattributes:29-30`, `ui/.gitattributes:21`, and
`tests/integration/data/test_scryfall_live_contract.py:16-19`. Amended the verification to grep the
CLAIM pattern repo-wide. Known-bad state avoided: declaring a prose sweep complete on the strength
of a search that could only ever confirm itself. **KEEP:** fixing falsified prose inside this change
rather than deferring it to R2 — the principle was right, only the search was too narrow.

**Entry 3 — no code re-derivation was performed for entries 1 and 2 (deviation, flagged).**
The workflow routes spec-caused findings to `bad_spec`, which mandates reverting the code and
re-deriving it. Not done here, deliberately: this diff is comment and prose only, both root causes
live in the non-frozen Acceptance/Verification sections, and a revert would have re-derived the same
text plus three more one-line edits. The amendments and patches were applied directly instead. This
is a judgment call and is reversible on request — see the review report for the full triage.

## Design Notes

**The lane cannot be probed.** `scripts/probe_harness.py:44` pins `_MARKER = "not integration"`, so a
planted defect in this test is invisible to the harness by construction — the harness scores exactly
the subset this lane complements. The deliberate-break push is therefore the *only* firing proof
available, and the ubuntu-green half is what proves the lane covers something the rest of CI cannot.

**Why Windows, why 3.12.** Windows is the platform of record (AD-2) and where this seam is hardest:
`terminate()` is a hard kill, an un-waited child holds the port and `cards.db`, and `localhost`
resolves `::1` against an IPv4-only bind. `py312` is the declared floor; the seam does not vary
across 3.12/3.13, so a matrix would double the slowest runner class for no new failure mode.

## Verification

**Commands:**
- `uv run pytest tests/integration/companion/` -- expected: `1 passed`, exit 0. Run before and after
  the docstring edit; the edit is prose-only and must not change the result.
- `uv run pytest tests/integration/companion/ --collect-only -q` -- expected: exactly one item,
  `test_the_real_channel_end_to_end`. Confirms the CI invocation selects what the lane claims.
- `python -c "import yaml,pathlib;yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text())"`
  -- expected: no exception. Syntax gate before pushing a workflow change.
- `git grep -nE "CI (never|is ubuntu|cannot see|could never)"` -- expected: no match that asserts CI
  never runs on Windows. **AMENDED (change log entry 2)** — the original command grepped for the one
  phrase already being fixed, which is satisfiable by construction and missed three sites. Grep the
  CLAIM, not the sentence.

**Manual checks (if no CLI):**
- On the PR: the Actions run lists **three** jobs, the new one on a Windows runner, its pytest step
  reading `collected 1 item` … `1 passed`.
- Firing proof: Windows red, both ubuntu jobs green; the revert restores all three. Choose the plant
  by the criterion in the AC, and run the local `-m "not integration"` pre-check first. Record both
  run URLs in the PR description — that evidence is not reproducible after merge.

## Suggested Review Order

**The lane itself — read this first**

- The whole deliverable: four steps, path-scoped, 15-minute cap.
  [`ci.yml:264`](../../.github/workflows/ci.yml#L264)

- Why a hang here would queue every later master run — the reviewer-found gap.
  [`ci.yml:270`](../../.github/workflows/ci.yml#L270)

**The reasoning that defends the design (every claim here was wrong on the first pass)**

- Why this job exists at all, stated from AD-10's actual text.
  [`ci.yml:226`](../../.github/workflows/ci.yml#L226)

- Path-scoping's real justification: model-loading tests, not the flake the retro named.
  [`ci.yml:250`](../../.github/workflows/ci.yml#L250)

- The vacuity floor, stated with its limits rather than as a reason to skip a guard.
  [`ci.yml:258`](../../.github/workflows/ci.yml#L258)

- Why not folded into `quality` — cost, explicitly not "no new failure mode".
  [`ci.yml:234`](../../.github/workflows/ci.yml#L234)

- Windows justified without the AD-2 label that does not say this.
  [`ci.yml:241`](../../.github/workflows/ci.yml#L241)

**The prose sweep — six sites, one fact**

- The falsified paragraph this change exists to correct.
  [`test_live_backend.py:35`](../../tests/integration/companion/test_live_backend.py#L35)

- The flake claim retracted at source, with the measurement date.
  [`test_live_backend.py:42`](../../tests/integration/companion/test_live_backend.py#L42)

- The most load-bearing site: a Windows-checkout claim, now that CI checks out on Windows.
  [`.gitattributes:29`](../../.gitattributes#L29)

- Scoped to the font tests rather than to "CI".
  [`ui/.gitattributes:21`](../../ui/.gitattributes#L21)

- The sibling integration test, which needed to know an integration lane now exists.
  [`test_scryfall_live_contract.py:16`](../../tests/integration/data/test_scryfall_live_contract.py#L16)

- Two narrowings of the same claim in the frontend docs.
  [`ui/README.md:404`](../../ui/README.md#L404) · [`fonts.test.ts:82`](../../ui/tests/fonts.test.ts#L82)
