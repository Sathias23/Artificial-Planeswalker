---
title: 'Epic 14 retro R2 — NFR-05 cold-open quiet-machine re-measurement'
type: 'chore'
created: '2026-08-16'
status: 'done'
baseline_revision: '09b8d880a2aed53f3392710786c9d4455b47dc68'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: ['oversized']
deferred:
  - summary: >-
      The Epic 14 retro contradicts itself on what moves the verdict — F7, §7 and the R2 ledger
      item call R2 "the single verdict-moving item" ("THIS IS WHAT MOVES THE VERDICT ... TO
      accepted"), while §9 lists four open items keeping the epic from a clean accepted; whether
      F7's closure flips the verdict is Brad's acceptance ruling, deliberately not made
      unattended (R2 is done either way).
    evidence: |-
      Pre-existing tension inside epic-14-retro-2026-08-16.md, surfaced by the intent-alignment
      audit of this change; the spec's Never clause forbade touching the verdict line, and the
      section-9 addendum records "Verdict line unchanged".
    location: >-
      _bmad-output/implementation-artifacts/epic-14-retro-2026-08-16.md
    severity: medium
---

<intent-contract>

## Intent

**Problem:** NFR-05's cold-open budget (deck view interactive within 1,000 ms) came back over on
2 of 5 runs at c7-7 (420/547/**1076** ms; immediate re-run 420/512/754), against c4-12's
311/363/428 ms on the same instrument with no `ui/src` runtime byte changed. F7 in
`epic-14-retro-2026-08-16.md` is the single item between Epic 14 and a clean `accepted`; the
retro's action item R2 (`epic-c7-retro-item-2-nfr05-quiet-machine-remeasurement`) prescribes a
quiet-machine re-measurement to resolve it.

**Approach:** Execute R2 exactly as prescribed: copy the real data dir once, run
`cdp_harness budget` for 5 runs on a machine doing nothing else, and record the observed figure.
Under 1,000 ms max → record it beside c4-12's figure, close F7 (dated addendum), flip R2 done.
Over 1,000 ms → open an Epic 15 story against the 325 MB-database cold path, record, flip R2 done.

## Boundaries & Constraints

**Always:**
- Exactly ONE measurement invocation (5 runs) decides the branch; record whatever it says. Both
  the console proof lines and the raw `--json` output are preserved verbatim.
- Do NOT run test suites, builds, or any other heavy process before or during the measurement —
  the post-suite machine is run A's suspected contaminant. Measure first in this session's work.
- Record machine-quietness evidence (CPU-load samples immediately before the run) alongside the
  figure, whatever it shows.
- The retro doc is append-only history: F7/§7/§9 get a dated addendum, never rewritten text.
- Ledger updates go through `sprint_status.py update` (the v6.11 tool), not hand edits.

**Block If:**
- The harness exits with anything other than 0 (under budget) or 2 (over budget), or reports
  fewer than 5 valid runs → `instrument failure`.
- The result is OVER budget AND the quietness samples show the machine was demonstrably not quiet
  (sustained CPU well above idle, ~>25%) → `machine not quiet, over-budget result inconclusive`
  (an over-budget number on a busy machine can neither close F7 nor justify a story).
- The real data dir or its `cards.db` is missing → `no real data dir to copy`.

**Never:**
- No re-running until green: a second invocation only happens if the first is invalid per the
  harness's own validity reporting (Block If covers everything else).
- No changes to `ui/src`, `src/`, or the harness — this is a measurement, not an optimization.
- No closing of retro items other than R2. The verdict line in the retro stays
  `accepted-with-open-items` (R3 manual checklist and others remain open regardless of outcome).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Under budget | 5/5 valid runs, max < 1,000 ms, EXIT 0 | Figure recorded beside c4-12's 311/363/428 in retro F7 addendum + §7/§9 addenda; R2 flipped done with ref | No error expected |
| Over budget, quiet | max ≥ 1,000 ms, EXIT 2, CPU samples idle | New Epic 15 story (epics file `### Story 15.7` + sprint-status `15-7-…: backlog`); retro addendum records figure + story pointer; R2 flipped done | No error expected |
| Over budget, not quiet | EXIT 2, CPU samples busy | HALT blocked, result recorded as inconclusive in spec only | Block If #2 |
| Harness failure | EXIT ∉ {0, 2} or <5 valid runs | HALT blocked with harness output | Block If #1 |

</intent-contract>

## Code Map

- `scripts/cdp_harness.py` -- the committed instrument (c4-12/c6-9/c7-7 precedent). `budget`
  subcommand: `--data-dir --deck-id --runs 5 --json`. Boots its own companion with
  `PLANESWALKER_DATA_DIR=<copy>` (`Backend.start`, `:283`); `budget` only reads, so the copy is
  hygiene, but `operator_data_dirs()` (`:1339`) is why a copy is used at all. Exit 0 = under
  budget, 2 = over. READ-ONLY — do not modify.
- `C:\Users\brads\AppData\Local\artificial-planeswalker` -- the real data dir
  (`src.paths.data_dir()`); `cards.db` = 325,230,592 bytes. Copy source. READ-ONLY.
- Copy target: scratchpad temp dir (session-specific), e.g. `<scratchpad>/ap-r2-quiet-copy` —
  same pattern as c7-7's `Temp/ap-c77-copy`.
- Deck id `813d0434-1bed-4419-bf9d-d9e4070704c4` -- "Atraxa Counter Cabinet v2 (owned)", the only
  100-card deck 99/99 image-warm at both sizes; the deck used by c4-12 AND c7-7, so figures are
  comparable (`c4-12-….md:390-403`, `spec-c7-7-….md:317-320`).
- `_bmad-output/implementation-artifacts/epic-14-retro-2026-08-16.md` -- F7 (`:131-139`), action
  item R2 (`:207`), open question 1 (`:243`), §9 open-items list (`:277`). Addendum targets.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- ledger item id
  `epic-c7-retro-item-2-nfr05-quiet-machine-remeasurement` (status open). Flip via
  `uv run --with ruamel.yaml python .claude/skills/bmad-retrospective/scripts/sprint_status.py
  update --file … --epic 14 --set-action-status '[{"id":"…","status":"done"}]'`.
- `_bmad-output/planning-artifacts/epics-companion-app.md` -- Epic 15 ("Release Readiness",
  `## Epic 15` at `:3262`) — where the conditional over-budget story lands as `### Story 15.7`.
- Prior figures for the record: c4-12 = 311/363/428 ms; c7-7 run A = 420/547/1076 (EXIT 2), run B
  = 420/512/754 (EXIT 0).

## Tasks & Acceptance

**Execution:**
1. Quietness sample -- capture 3× CPU-load readings ~5 s apart (PowerShell
   `Get-Counter '\Processor(_Total)\% Processor Time'`) -- evidence the machine is quiet; keep
   the readings.
2. Copy data dir -- `robocopy`/`shutil` the real data dir to `<scratchpad>/ap-r2-quiet-copy` --
   one copy, used for all 5 runs (the retro's "one copied data dir").
3. Run instrument -- `uv run python -m scripts.cdp_harness budget --data-dir <copy>
   --deck-id 813d0434-1bed-4419-bf9d-d9e4070704c4 --runs 5 --json
   _bmad-output/implementation-artifacts/nfr05-quiet-remeasure-2026-08-16.json` -- the R2
   measurement; paste the harness proof lines verbatim into this spec's Auto Run Result.
4. Branch on exit code per the I/O matrix:
   - `_bmad-output/implementation-artifacts/epic-14-retro-2026-08-16.md` -- dated addendum under
     F7 (figure + quietness evidence + disposition), plus one-line addenda at §7 question 1 and
     §9 item 1 -- closes/updates F7 without rewriting history.
   - (over-budget-quiet only) `_bmad-output/planning-artifacts/epics-companion-app.md` -- append
     `### Story 15.7` under Epic 15 with Given/When/Then ACs targeting the 325 MB cold path;
     `sprint-status.yaml` -- add `15-7-<slug>: backlog` inside the epic-15 block (hand edit is
     fine here; only ledger items must use the tool).
5. Ledger flip -- `sprint_status.py update … --set-action-status` R2 → done -- completes the
   retro action item (both non-blocked branches).
6. Cleanup -- delete `<scratchpad>/ap-r2-quiet-copy` -- 325+ MB of temp data.

**Acceptance Criteria:**
- Given the copied data dir and a quiet machine, when `cdp_harness budget --runs 5` completes,
  then 5/5 valid runs are reported and the min/median/max proof line is recorded verbatim in this
  spec and in the retro F7 addendum next to c4-12's 311/363/428 ms.
- Given EXIT 0, when the recording lands, then the retro F7 addendum states NFR-05 holds on a
  quiet machine and ledger item `epic-c7-retro-item-2-…` reads `status: done`.
- Given EXIT 2 with quiet-machine evidence, when the recording lands, then `### Story 15.7`
  exists under Epic 15 with testable ACs, `sprint-status.yaml` carries its backlog key visible to
  `STORY_RE`, and the retro F7 addendum points at it.
- Given any other harness outcome, when the run ends, then the workflow is HALTed blocked with
  the harness output preserved — no addendum claims a measurement that didn't validly happen.

## Spec Change Log

## Review Triage Log

### 2026-08-16 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 7: (high 0, medium 1, low 6)
- defer: 1: (high 0, medium 1, low 0)
- reject: 14
- addressed_findings:
  - `[medium]` `[patch]` F7 addendum closed on budget compliance while staying silent on F7's second observation (residual ~15–20% drift vs c4-12's 311/363/428); addendum now names the drift, states the NFR-05 closure basis per R2's own prescription, and records the drift as recorded-not-explained.
  - `[low]` `[patch]` Addendum claimed quietness was sampled "immediately before the run" though the 453 MB data-dir copy intervened; wording corrected to "before the data-dir copy + runs".
  - `[low]` `[patch]` Addendum's fenced block was a condensed paraphrase, not verbatim harness output; replaced with the five full run lines, the unmodified proof line, and `EXIT: 0` on its own line.
  - `[low]` `[patch]` Spec `## Verification` git-diff expectation listed sprint-status.yaml only for the over-budget branch though the R2 ledger flip changes it on both; corrected to unconditional.
  - `[low]` `[patch]` §9 addendum's fragile ordinals ("items 2–4") replaced with named items (manual checklist R3; F2/F4/F6; five prior action items).
  - `[low]` `[patch]` sprint-status `last_updated` bump had no paired narrative line; one comment line added at the top of the header block recording the R2 closure.
  - `[low]` `[patch]` Verification outcomes were run but unrecorded; appended to Auto Run Result (detect-epic result, changed-file surface, JSON-vs-proof-line cross-check, temp-copy deletion).

## Design Notes

R2's wording ("If it still exceeds 1,000 ms, open a C8 story … if it does not, record … and close
F7") makes BOTH branches a completion of R2 — the flip to done is not conditional on the happy
path, only on having a valid quiet-machine measurement. The not-quiet guard exists because the
whole point of R2 is removing the "machine had just run two suites" confound from run A; an
over-budget figure with the confound still present would reopen the same argument, not settle it.

## Verification

**Commands:**
- `uv run --with ruamel.yaml python .claude/skills/bmad-retrospective/scripts/sprint_status.py detect-epic --file _bmad-output/implementation-artifacts/sprint-status.yaml` -- expected: still `epic: 14`, `retro_status: done`; and on the over-budget branch, `15-7-…` NOT in done_stories (backlog).
- `git diff --stat` -- expected: only the artifacts named in Tasks changed (retro doc, spec, JSON evidence, and sprint-status on both non-blocked branches — the R2 ledger flip touches it unconditionally; the epics file additionally on the over-budget branch only).

**Manual checks (if no CLI):**
- The harness proof line in the retro addendum matches the JSON evidence file's runs exactly.

## Auto Run Result

**Executed 2026-08-16. Branch taken: UNDER BUDGET (EXIT 0).**

Machine-quietness samples (Task 1, `Get-Counter '\Processor(_Total)\% Processor Time'`, ~5 s apart, immediately before the copy+run):

```
10:17:41  CPU: 9.92%
10:17:47  CPU: 2.18%
10:17:53  CPU: 19.55%
```

Data-dir copy (Task 2): robocopy of `C:\Users\brads\AppData\Local\artificial-planeswalker` to `<scratchpad>/ap-r2-quiet-copy`, 453.39 MB; copied `cards.db` = 325,230,592 bytes (matches source). One copy, used for all 5 runs, deleted after (Task 6).

Harness output (Task 3), verbatim:

```
companion on http://127.0.0.1:51330, data dir C:\Users\brads\AppData\Local\Temp\claude\c--Users-brads-Projects-Artificial-Planeswalker\06f31dc7-01e3-49d7-8b96-b301b811a99b\scratchpad\ap-r2-quiet-copy
active deck set to 813d0434-1bed-4419-bf9d-d9e4070704c4
  run 1: layout 420 ms  format-check at queue position 107  (99 card reads, 214 requests)
  run 2: layout 517 ms  format-check at queue position 107  (99 card reads, 214 requests)
  run 3: layout 421 ms  format-check at queue position 107  (99 card reads, 214 requests)
  run 4: layout 409 ms  format-check at queue position 107  (99 card reads, 214 requests)
  run 5: layout 378 ms  format-check at queue position 107  (99 card reads, 214 requests)

layout time over 5/5 valid runs: min 378 / median 420 / max 517 ms   (NFR-05 budget: 1000 ms)
format-check queue position(s): [107]
raw runs -> _bmad-output/implementation-artifacts/nfr05-quiet-remeasure-2026-08-16.json
EXIT: 0
```

Disposition: 5/5 valid runs, max 517 ms < 1,000 ms → NFR-05 holds on a quiet machine. Retro F7 closed via dated addendum (plus §7 question 1 and §9 item 1 one-line addenda); ledger item `epic-c7-retro-item-2-nfr05-quiet-machine-remeasurement` flipped to done via `sprint_status.py update`. No Epic 15 story opened.

Verification outcomes (run 2026-08-16):

- `sprint_status.py detect-epic` → `epic: 14`, `retro_status: done`, `pending_stories: []` — matches the expected result.
- Changed-file surface: tracked = retro doc + `sprint-status.yaml` (ledger flip); untracked = `nfr05-quiet-remeasure-2026-08-16.json` + this spec — exactly the artifacts named in Tasks for the under-budget branch.
- JSON cross-check: the evidence file's five `layout_ms` values (419.8 / 516.9 / 421.1 / 409.2 / 377.6) match the console proof line's runs run-for-run.
- Cleanup (Task 6): `<scratchpad>/ap-r2-quiet-copy` confirmed deleted after the run.

**Review pass (2026-08-16):** four layers (blind hunter, edge-case hunter, verification-gap, intent-alignment). Verification-gap returned zero findings and independently reproduced the JSON-vs-proof-line cross-check. Breakdown: 0 intent_gap, 0 bad_spec, **7 patches applied** (1 medium — the F7 addendum's silence on the residual ~15–20% drift vs c4-12; 6 low — quietness-claim wording, verbatim proof block, spec verification expectation, §9 ordinals, sprint-status narrative line, recorded verification outcomes), **1 deferred** (the retro's pre-existing self-contradiction on whether R2 alone moves the verdict — Brad's acceptance ruling, see frontmatter `deferred`), 14 rejected as noise/by-design/counterfactual. Verification re-run green after patches.

**Follow-up review recommendation:** patched counts — high 0, medium 1, low 6; score = 3×1 + 1×6 = 9 ≥ 5 → `followup_review_recommended: true`.

**Residual risks:**
- The quiet-machine figure (378/420/517) remains ~15–20% above c4-12's 311/363/428 on all three statistics — under budget, but the drift F7 observed is real and unexplained; recorded in the F7 addendum, worth an eye if it widens at the next measurement.
- Acceptance rests on transcript fidelity: the measurement is one out-of-band physical run; nothing in the repo can re-establish it (by design — the spec forbids re-running until green). Raw JSON preserved for scrutiny.
- The retro verdict (`accepted-with-open-items`) was deliberately not flipped; whether F7's closure moves it is the deferred question above.
