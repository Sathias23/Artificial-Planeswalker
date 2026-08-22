---
title: 'Story 17.3: Measure the latency budgets and close the gaps'
type: 'chore'
created: '2026-08-22'
status: 'done'
baseline_revision: 'bb196c03bf4d4abcbc65eec1f54440e028f8f4b7'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: ['oversized']
deferred:
  - summary: >-
      Cold-open (NFR-05) drift keeps widening: quiet-machine medians c4-12 363 ms → R2 420 ms →
      17.3 529 ms, with a 960 ms outlier leaving 4% headroom on the 1,000 ms max; worth a
      diagnosis pass before the 0.5.0 cut if any more render-path weight lands.
    evidence: |-
      Three quiet-machine measurements on the same committed instrument and deck
      (nfr05-quiet-remeasure-2026-08-16.json vs nfr05-budget-2026-08-22.json); R2's addendum
      called the earlier drift "recorded-not-explained" and it has since widened. Under budget,
      so 17.3 records it as Observation O1 in perf-evidence-17-3-2026-08-22.md rather than a
      deviation, but the trend has survived two remeasurements and has no tracking home a
      release-cut checklist would look at.
    location: >-
      _bmad-output/implementation-artifacts/perf-evidence-17-3-2026-08-22.md
    severity: medium
---

<intent-contract>

## Intent

**Problem:** The companion's performance claims are part-verified, part-asserted: the 250 ms push and 1 s cold-open budgets were last measured before Epics 16–17 touched the render paths; the AD-11 "concurrent push while a cold-cache image queue drains" case has NO instrument (its unit test explicitly re-homes the literal AC on 17-3); CM-2's once-per-image guarantee is proven only in unit tests, never observable in a real session (a successful CDN fetch logs nothing); CM-1's token arithmetic predates the three epic-16 push tools; and the image-cache footprint figures are one-off 2026-08-02 prose.

**Approach:** Build the two missing observation seams — a `drain` arm on the committed `cdp_harness push` instrument (push measured while a cold-cache 99-card image queue drains through the pacer) and one INFO log line per successful CDN fetch — then run the full measurement session on a quiet machine (warm push, cold-open budget, drain arm, CDN-fetch count, real cache footprint, five-tool token arithmetic) and record every figure with hardware and conditions in a committed evidence report plus raw JSONs. Any measured gap is closed or recorded as a deviation with its reason.

## Boundaries & Constraints

**Always:**
- Implementation and full-suite verification come FIRST; official measurements run AFTER, on a quiet machine, with 3× CPU-load samples (~5 s apart) captured before the batch and recorded whatever they show (R2 protocol).
- All measured runs use a COPY of the real data dir (`C:\Users\brads\AppData\Local\artificial-planeswalker`, READ-ONLY source) in the session scratchpad; the harness's `refuse_the_operators_data_dir` guard stays intact. Deck `813d0434-1bed-4419-bf9d-d9e4070704c4` (Atraxa, the c4-12/c7-7/R2 deck) for comparability. Copy deleted after.
- The drain arm's run validity needs a positive control: card-image requests genuinely outstanding (queued/in-flight through the pacer) at the moment the push is issued, plus `clients ≥ 1`; an invalid run is named, never numbered. Verdict: exit 2 when max `layout_ms` ≥ 250 ms, matching the warm arm. Per-run cold cache = the harness empties `image_cache` inside its own copied data dir; default 3 runs (real Scryfall CDN traffic — c6-9's cold-arm precedent; pacer spacing respected by construction).
- The new fetch-success log line fires exactly once per actual CDN fetch (same gate as the existing failure line: the `fetch_image` call itself) and carries the full key (id, face, size) so `companion.log` lines can be grouped per key. Warm cache hits and negative-cache refusals log nothing new.
- CM-2 is counted per cache lifetime: within one lifetime (one cold start of the cache), a key with >1 fetch-success line is a duplicate. The declined in-flight-coalescing residual (two simultaneous first requests for one key both fetch) is a KNOWN accepted deviation — if observed, record it as such with the existing rationale; any OTHER duplicate is a gap.
- Raw `--json` outputs for warm push, budget, and drain are committed beside the evidence report (the R2 precedent; c6-9's push JSONs were lost to the scratchpad — close that gap). Console proof lines pasted verbatim into the report and this spec's Auto Run Result.
- Every recorded figure carries hardware + conditions (machine, OS, Chrome, data-dir sizes, quietness samples) hand-recorded in the report — c6-9 prose precedent.
- A quiet-machine budget breach (exit 2) is recorded with its figure and reason as a deviation pending Brad's acceptance (report + frontmatter `deferred`) — never silently, never "left ambiguous", and never chased with optimization work in this story.
- `src/` changes ship with pre-commit's `plugin/` rebuild included in the same commit.

**Block If:** the harness exits outside its documented codes or reports fewer valid runs than the arm's minimum (warm/budget 5, drain 3) after one re-invocation (`instrument failure`); an over-budget result lands on a demonstrably non-quiet machine (sustained CPU ≫ idle, ~>25%) (`over-budget result inconclusive`); the real data dir or its `cards.db`/`image_cache` is missing (`no real data dir to copy`).

**Never:** No optimization of `ui/src`, `src/companion` runtime behavior, pacer constants, or cache policy (the log line is the sole `src/` runtime change — one INFO record per already-paid network exchange); no eviction policy (footprint is measured so one can EVENTUALLY be sized); no backend event retention; no re-running a valid measurement until it goes green; no touching the existing `budget`/`refetch`/`warm`/`cold`/`blocked` measurement semantics; no hand edits to prior evidence artifacts.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Warm push, under | `push --arm warm --runs 5`, 5/5 valid | min/median/max recorded vs 250 ms; EXIT 0 | No error expected |
| Cold open, under | `budget --runs 5`, quiet machine | min/median/max recorded vs 1000 ms beside c4-12/R2 figures; EXIT 0 | No error expected |
| Drain push, valid | queue draining at push, `clients ≥ 1` | `layout_ms` + outstanding-images count recorded; verdict vs 250 ms | No error expected |
| Drain push, queue empty at push | images all landed before push | run named invalid (positive control failed), never numbered | Re-run; <3 valid ⇒ Block If |
| Any budget breach, quiet | EXIT 2, CPU samples idle | figure + reason recorded as deviation pending acceptance; `deferred` entry | No error expected |
| Any budget breach, busy | EXIT 2, CPU samples busy | HALT | Block If |
| CM-2 duplicate, known residual | 2 fetch lines, one key, simultaneous first requests | recorded as the accepted coalescing deviation | No error expected |
| CM-2 duplicate, unexplained | >1 fetch line per key otherwise | gap: diagnose; close or record with reason | No error expected |
| Warm repaint after drain | reload same deck, warm cache | 0 new fetch-success lines for held keys | No error expected |
| CM-1 worst case | five tools × all statuses, oversized adversarial inputs | max result ≤ ~200 tokens; per-key figures recorded | No error expected |
| Footprint | real `image_cache`, read-only | bytes + file count + context recorded vs README's 2026-08-02 figures | No error expected |
| Fetch-success log | one real CDN fetch | exactly one INFO line with id/face/size; none on warm hit, none extra on failure | No error expected |

</intent-contract>

## Code Map

- `scripts/cdp_harness.py` -- the committed instrument. `measure_push` (`:595-686`): t_pre/t_post bracket around `POST /agent/events` (`:631-639`), stop = last of five `PUSH_SURFACES` (`:487-493`) via document-start MutationObserver (`:351-378`); entry animation excluded by construction (layout commits at `opacity:0`, `:625-629`). `cmd_push` (`:718-797`) + parser (`:1692-1717`): arms `warm|cold|blocked`; warm primer `:753-769`; per-run reload `_reset_for_next_run` (`:705-715`); cold uses a fresh browser profile per run (`:746`, `:773`) and always exits 0 (`:853-856`). Validity/exit rules in `_print_run`/`_report_push` (`:800-857`); `PUSH_BUDGET_MS = 250` (`:502-503`). `Companion` (`:266-338`) boots the backend as a child with `PLANESWALKER_DATA_DIR`, stdout+stderr → `<data_dir>/companion.log` (`:274`, `:289-291`) — the CM-2 counting seam. `Browser.block` / `Network.setBlockedURLs` (`:234-237`), `_CARD_IMAGE_PATTERN` (`:500`). `operator_data_dirs`/`refuse_the_operators_data_dir` (`:1339-1398`). `budget` subcommand (`:412-503`, parser `:1679-1690`) — REUSE UNCHANGED. Drain arm slots in beside `cold`: fresh profile + emptied `image_cache` in the copy + deck view open and draining before the push; count outstanding `/api/card-image/*` at t_pre (CDP Network events or in-page resource timing — the budget path already counts requests, `:400-409`).
- `src/companion/app/routes/cards.py` -- `read_card_image` (`:223`); the one CDN fetch call site `await fetch_image(client, url, pacer)` (`:414-415`); existing failure INFO line (`:425-431`) is the format to mirror; success path continues at `:434-454` (negative-cache clear, cache write). Insert the success INFO line immediately after the successful fetch, before the cache write.
- `src/companion/app/images.py` -- context only, READ-ONLY: `Pacer` (`:641`, spacing 0.1 s `:260`, concurrency 4 `:287`), `fetch_image` (`:1712`), `build_image_client` seam (`:571`), `DiskCache` (`:1084`), `cache_root()` = `data_dir()/image_cache` (`:793`, `:371`), sharded `<id[0:2]>/<id>/<size>_<face>.<ext>` (`:856`), unbounded-by-design (`:1132`), AD-11 static guards live in `test_images.py:1310`/`:2763`.
- `tests/unit/companion/test_routes_card_image.py` -- fixture `cdn` patches the client factory (`:93-109`), `Recorder.requested` counts fetches (`:59-90`); `TestARepeatRequestMakesNoCdnRequest` (`:1656`) and `TestAWarmTileNeverEntersThePacer` (`:1917`) are the CM-2 unit precedents; `TestAQueuedBurstDoesNotStallTheApp` (`:1171-1239`) — its docstring (`:1177-1183`) records that the literal concurrent-push AC is homed HERE, on 17-3. New log-line tests join this file (caplog: one line per fetch, none on warm hit, failure path unchanged).
- `src/mcp_server/tools/companion.py` -- CM-1 sources: result models (suggestions `:219-257`, swaps `:363-399`, tiers `:456-495`, groups `:609-649`, set-active-deck `:80-121`), `_push_messages` (`:260-303`), success sentences (`:549`, `:208`), `_ECHO_LIMIT = 48` (`:58-77`). READ-ONLY — measure, don't change.
- `tests/integration/mcp_server/test_companion_tool.py` -- the 400-char-per-result bounds + planted-sentinel no-echo assertions (suggestions `:720-751`, swaps `:915-943`, tiers `:1093-1120`, groups `:1271-1298`, control `:463-571`) — cite as the enforcement; the session-level figure is new arithmetic recorded in the report (throwaway scratchpad script over the real models, output pasted — c6-9 `:735-745` precedent, which covered only two tools).
- `_bmad-output/implementation-artifacts/` -- prior figures for the record: c6-9 warm 15/21/36 ms (also blocked/cold/60-item arms + the negative literal-reading bracket); c7-7 warm 17/19/37, refetch 221/240/243, budget run A 420/547/1076 EXIT 2; R2 quiet-machine budget 378/420/517 EXIT 0 (`nfr05-quiet-remeasure-2026-08-16.json`, the committed-JSON precedent + quietness protocol in `spec-epic-14-r2-nfr05-quiet-machine-remeasure.md`). Evidence report lands here as `perf-evidence-17-3-2026-08-22.md`.
- `README.md:520-566` -- footprint measurement commands + the 2026-08-02 figures (~90 KB/tile, 8.5 MB/deck, ~95 MB library) the new measurement sits beside; `test_image_cache_docs.py:403-424` pins those strings — do not change README figures (add to the report instead).
- `src/companion/app/server.py:256` -- entry point configures root logger at INFO on stderr → the new line reaches `companion.log` under the harness.
- `src/paths.py:23-43` -- data-dir resolution (`PLANESWALKER_DATA_DIR` override; Windows `%LOCALAPPDATA%\artificial-planeswalker`).

## Tasks & Acceptance

**Execution:**
1. `src/companion/app/routes/cards.py` -- add one INFO fetch-success line (id, face, size) after the successful `fetch_image` call -- makes CM-2 observable in a real session; lazy `%` args, mirrors the failure line.
2. `tests/unit/companion/test_routes_card_image.py` -- caplog tests: exactly one success line per real fetch; zero on warm-cache hit and negative-cache refusal; failure path emits only the existing line -- guard ships with the change.
3. `scripts/cdp_harness.py` -- add `push --arm drain`: per-run fresh browser profile + emptied `image_cache` in the harness's copied data dir, deck view open and draining, push issued mid-drain, outstanding-card-image count at t_pre recorded as the positive control (run invalid if zero or `clients` falsy), default 3 runs, exit 2 on max ≥ 250 ms, `--json` includes the new fields -- the missing AD-11 instrument.
4. Quality gates + probe proof -- `uv run pytest -m "not integration"` (plus the touched integration file), ruff, mypy; `uv run python -m scripts.probe_harness --expect-red '<planted log-line test>'` with proof line pasted -- committed-harness firing proof per Testing Rules.
5. Measurement session (after gates; quiet machine; one data-dir copy) -- quietness samples; `push --arm warm --runs 5 --json`; `budget --runs 5 --json`; `push --arm drain --runs 3 --json`; CM-2 count grouped per key per lifetime from `companion.log`; warm-repaint zero-fetch check; real `image_cache` footprint (bytes + file count, read-only); CM-1 arithmetic script over the five result models (worst case + ordinary, all statuses); delete the copy -- the story's evidence.
6. `_bmad-output/implementation-artifacts/perf-evidence-17-3-2026-08-22.md` + committed run JSONs (`nfr05-push-warm-2026-08-22.json`, `nfr05-budget-2026-08-22.json`, `nfr05-push-drain-2026-08-22.json`) -- every figure with hardware/conditions/quietness, verbatim proof lines, prior-figure comparisons, and a Deviations section (each: closed, known-accepted, or pending-acceptance with reason) -- AC 3 and AC 8's home.
7. `plugin/` -- pre-commit rebuild included in the commit -- distribution parity for the `src/` change.

**Acceptance Criteria:**
- Given the shipped surface (post 17.1/17.2), when `push --arm warm --runs 5` and `budget --runs 5` complete on a quiet machine, then min/median/max land in the report vs 250 ms/1000 ms with verbatim proof lines, committed JSONs, and hardware/conditions.
- Given the drain arm with its positive control satisfied on ≥3 valid runs, when the push is measured while the cold-cache queue drains through the pacer, then the report records the figures and the verdict, confirming end-to-end that pacing never blocked the event loop (beside the existing AST-scan guards).
- Given the drain session's `companion.log`, when fetch-success lines are grouped per key per cache lifetime, then no key exceeds one fetch (or a duplicate is recorded as the known coalescing deviation / a diagnosed gap), and the warm repaint adds zero lines.
- Given the five companion tools, when worst-case and ordinary result sizes are measured across all statuses, then the ~200-token ceiling holds, the no-payload-echo sentinels are cited, and the session-level figure is recorded.
- Given any measured gap against either budget, when the report lands, then it is closed or recorded as a deviation with its reason — nothing left ambiguous.
- Given the full suite after the code changes, when it runs, then every existing pin stays green and the planted-RED probe proof line is recorded.

## Spec Change Log

## Review Triage Log

### 2026-08-22 — Review pass

- intent_gap: 0
- bad_spec: 0
- patch: 10: (high 0, medium 2, low 8)
- defer: 1: (high 0, medium 1, low 0)
- reject: 8
- addressed_findings:
  - `[medium]` `[patch]` The push validity predicate and reporter (`_push_run_is_valid`/`_report_push`) — which decide the SC-1/AD-11 exit-code verdict — shipped unpinned while their refetch twins are fully tested; pinned with a shipped `push_result` builder (used by `measure_push` itself, closing fixture drift), refusal + positive-twin pairs for non-200 / missing-surfaces / falsy-clients / zero-outstanding, the None-means-absent rule so a warm run without the key is never failed, and the "described as invalid then counted anyway" failure demonstrated refused.
  - `[medium]` `[patch]` The drain arm's operator-data-dir write-gate wiring in `cmd_push` was untested (deleting the two-line gate left every test green while the arm empties `image_cache` up to three times); pinned mirroring `test_cmd_refetch_refuses_before_it_opens_anything` + positive twin + warm-arm-not-gated twin, with a `No cards.db` pre-check added to the drain branch.
  - `[low]` `[patch]` `_empty_image_cache` untested (inverting its success condition shipped half-warm "cold" runs undetected by the positive control); tmp_path units added: emptied / absent no-op / SystemExit naming the mislabelled-measurement stakes.
  - `[low]` `[patch]` `cmd_push` accepted `--runs 0`/negative and reported "NO VALID RUNS" as if the app were broken; refused with a clean SystemExit (refetch's guard), tested.
  - `[low]` `[patch]` `--deck-id` on a non-drain arm was silently ignored; now refused, tested.
  - `[low]` `[patch]` The drain arm's active-deck PUT duplicated `cmd_budget`'s and a transport error surfaced as a raw traceback; extracted into shared `_set_active_deck` with `httpx.HTTPError` → named SystemExit.
  - `[low]` `[patch]` `_outstanding_card_images` trusted a single fixed 0.05 s pump (stale events could overcount) and would KeyError on an event without `requestId`; now pumps until the event buffer stops growing and skips id-less events.
  - `[low]` `[patch]` The lifetime-offset quietness rested on a fixed 2.0 s sleep and `_empty_image_cache` slept after its final failed attempt while hiding the failure cause; offsets now come from `_await_stable_size` (bounded watch until the log stops growing), the final sleep is gone, and the refusal names the last concrete OSError and path.
  - `[low]` `[patch]` The `== 0` positive-control threshold read as an accident; documented as a ruling (any nonzero satisfies "while images are queued"; the depth is recorded in JSON and printed per run).
  - `[low]` `[patch]` The report's 105–106 outstanding requests vs "~99 tiles" prose was unexplained; §4 now accounts for them exactly (99 face-0 `normal` tiles + 6 second-face requests from the deck's six modal Pathway lands, verified against `cards.db` + the commander's `size=large` detail fetch).

Deferred: the cold-open drift trend (O1) — pre-existing, recorded in frontmatter `deferred`. Rejected as noise/by-design: `_push_run_is_valid` naming (matches the `_refetch_run_is_valid` convention); scratchpad analysis scripts not committed (intent's "counted"/"recorded" satisfied; c6-9 precedent; offsets + line format are committed); JSON trailing-newline nit (harness output convention, same as the R2 file); byte-count field unasserted in tests (not load-bearing for the CM-2 key); the failure line's INFO level pinned without comment (pre-existing behavior); two-keys test ordering/default-size brittleness (deterministic sequential awaits; API default); `images_outstanding_at_push: None` passing the control (counterfactual — the key is only written when counted; now also pinned by P1's tests); intent-alignment Reading-A scope note (the intent's own unmeasurable clauses authorize the two observation seams; every surface substitution is ruled openly in the report).

## Design Notes

- The drain arm is the AC's literal shape: "cold-cache deck load" = the deck view genuinely re-fetching ~99 images from the real CDN through the pacer (c4-12 cold precedent, ~8.5 MB, ~10 s to fully paint) — not a stalled or blocked transport, which the c6-9 `blocked` arm already covers and which proves waiting, not concurrency. 3 runs bounds real CDN traffic; the pacer's own spacing keeps the harness a polite client.
- Counting fetches at the route (not `_fetch_within_deadline`) is deliberate: the route owns the key (id/face/size); the fetcher knows only a URL. One line per paid network exchange bounds log rate by fetch rate — same argument the failure line's comment already makes.
- CM-1 stays arithmetic-plus-measurement rather than a live-chat capture: the 400-char bounds and sentinel-absence tests are the enforcement; the report's job is a current, five-tool figure replacing c6-9's two-tool one.
- Budget-breach handling deviates from R2 on purpose: R2 had a prescribed story-opening branch; 17.3's AC offers close-or-record, and "accepted" is Brad's word — so a quiet-machine breach records the deviation as pending acceptance and surfaces it in `deferred` rather than blocking or silently optimizing.

## Verification

**Commands:**
- `uv run pytest tests/unit/companion/test_routes_card_image.py -q` then `uv run pytest -m "not integration"` -- expected: green, including the new caplog tests.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` -- expected: clean.
- `uv run python -m scripts.probe_harness --expect-red '<new log-line test node id>'` -- expected: pasteable RED proof line.
- `uv run python -m scripts.cdp_harness push --help` -- expected: `drain` listed among arms with its documented default runs.
- `git diff --stat` -- expected: only `cards.py`, its test file, `cdp_harness.py`, `plugin/` mirror, the evidence report + JSONs, and this spec.

**Manual checks (if no CLI):**
- Report proof lines match the committed JSONs run-for-run; every figure carries hardware + conditions; the Deviations section has no ambiguous entries.

## Auto Run Result

**Executed 2026-08-22. All budgets held; nothing pending acceptance; `deferred` stays empty.**

Implementation (Tasks 1–3): fetch-success INFO line in `cards.py` (id/face/size + byte count,
lazy `%` args, gated on the `fetch_image` call exactly as the failure line is); five caplog
tests in `test_routes_card_image.py::TestAFetchSuccessLogsExactlyOnce`; `push --arm drain` in
`cdp_harness.py` (per-run fresh profile + emptied copy `image_cache`, active deck view draining,
outstanding-count positive control via CDP Network events, default 3 runs, exit 2 at ≥250 ms,
new JSON fields `images_outstanding_at_push` / `log_offset_at_lifetime_start`; the drain arm
also inherits `refuse_the_operators_data_dir` because emptying a cache is a write).

Quality gates + probe proof (Task 4), verbatim:

```
full suite (-m 'not integration'): 3271 collected, 3 failed, 0 errored, exit 1
  RED    tests/unit/companion/test_routes_card_image.py::TestAFetchSuccessLogsExactlyOnce::test_one_real_fetch_logs_one_success_line_carrying_the_full_key
  RED    tests/unit/companion/test_routes_card_image.py::TestAFetchSuccessLogsExactlyOnce::test_two_fetches_for_two_keys_log_two_lines_grouped_apart
  RED    tests/unit/companion/test_routes_card_image.py::TestAFetchSuccessLogsExactlyOnce::test_a_warm_cache_hit_logs_no_new_success_line
```

(plant: the new line demoted to DEBUG; restored, then:)

```
full suite (-m 'not integration'): 3271 collected, 0 failed, exit 0
```

`ruff check` / `ruff format --check` / `mypy src/` all clean. The cited integration file
(`test_companion_tool.py`) runs inside the `-m "not integration"` set and is green above.

Measurement session (Tasks 5–6) — quiet machine (CPU samples 6.23/6.11/5.85%, second set
6.49/6.81/6.83% before the drain re-invocation), one 453.69 MB data-dir copy (deleted after),
deck `813d0434-1bed-4419-bf9d-d9e4070704c4`:

```
warm arm, layout over 5/5 valid runs: min 20 / median 39 / max 42 ms   (SC-1 budget: 250 ms; conservative bracket -- t0 stamped before the POST)
EXIT: 0

layout time over 5/5 valid runs: min 431 / median 529 / max 960 ms   (NFR-05 budget: 1000 ms)
EXIT: 0

drain arm, layout over 3/3 valid runs: min 20 / median 20 / max 22 ms   (SC-1 budget: 250 ms; conservative bracket -- t0 stamped before the POST)
  card-image requests outstanding at the push per run: [105, 106]
EXIT: 0

TOTAL: 175 fetches across 3 cache lifetime(s); 0 duplicate key-lifetime(s)
CM-2 LOG CHECK: PASS -- no key exceeded one fetch per cache lifetime

warm repaint: 99 tile(s) on the glass, 0 new fetch-success line(s)
WARM-REPAINT CHECK: PASS -- zero new fetch-success lines

  max single result           : 369 chars (~92 tokens)   [CM-1 ceiling: ~800 chars / ~200 tokens]
  session-level worst case    : all five tools once each at their worst = 1248 chars (~312 tokens)
```

Footprint (real cache, read-only): 806 files, 83,293,578 bytes (79.4 MiB), 580 distinct
printings; `normal` avg 88.5 KiB — confirms README's 2026-08-02 ~90 KB/tile; README figures
untouched. Full detail, prior-figure comparisons, and the Deviations section (D1 instrument
repair: log-marker write measured overwritten by the child's non-append stdout handle →
replaced with read-only offset recording, one drain re-invocation; D2 coalescing residual not
observed; D3 session figure recorded) live in `perf-evidence-17-3-2026-08-22.md`.

Verification outcomes:

- `pytest tests/unit/companion/test_routes_card_image.py -q` → 120 passed; full suite → 3271/0 (above).
- `push --help` lists `drain` among the arms with its documented default of 3 runs.
- JSON cross-check: `nfr05-push-warm` layout_ms 39.5/41.7/39.4/20.4/31.2, `nfr05-budget`
  430.6/528.6/531/433.2/960.3, `nfr05-push-drain` 20.3/22.5/20.5 with outstanding [106,106,105]
  and clients [1,1,1] — match the console proof lines run-for-run.
- `git status` surface: `src/companion/app/routes/cards.py`, `tests/unit/companion/test_routes_card_image.py`,
  `scripts/cdp_harness.py`, `plugin/server/src/companion/app/routes/cards.py` (rebuild), plus the
  untracked evidence report, three JSONs, and this spec — exactly the expected set.
- Copy deleted after the session; real data dir opened read-only throughout.

### 2026-08-22 — Review-pass patches (10 applied, instrument hardening only)

The review triaged 10 patch findings; all applied. **No measurement was re-run and no committed
figure changed** — the hardening applies to future invocations of the instrument.

- P1/P2/P3 (`tests/unit/test_cdp_harness.py`): the push validity predicate, reporter and drain
  gates pinned the way their refetch twins are — a shipped `push_result` builder (mirroring
  `refetch_result`, used by `measure_push` and the tests, closing the fixture-drift risk), a
  `_push_run` test helper, refusal+positive-twin pairs for non-200 / missing-surfaces / falsy
  clients / zero-outstanding, the None-means-absent rule for the positive control, the drain
  arm's operator-data-dir gate through `cmd_push` (refusal before anything opens, twin reaching
  the next gate, warm arm not gated), and `_empty_image_cache` units (emptied / no-op /
  SystemExit naming the mislabelled-measurement stakes).
- P4/P5 (`scripts/cdp_harness.py`): `cmd_push` refuses `--runs < 1` before anything is opened
  (refetch's guard) and refuses `--deck-id` on a non-drain arm instead of silently ignoring it;
  a drain against a data dir with no `cards.db` is refused before the companion starts.
- P6: the active-deck PUT extracted into `_set_active_deck` shared by `cmd_budget` and the drain
  arm, with `httpx.HTTPError` → named SystemExit.
- P7: `_outstanding_card_images` pumps until the event buffer stops growing and skips events
  without a `requestId` rather than KeyError-ing a measured run.
- P8: the lifetime offset is taken via `_await_stable_size` (log watched until it stops growing,
  bounded) rather than trusting the fixed sleep; `_empty_image_cache` no longer sleeps after its
  final failed attempt and its refusal names the last concrete `OSError`.
- P9: the `== 0` positive-control threshold documented as a ruling (the AC's condition is
  "while images are queued"; the depth is in the JSON and on the run line for the reader).
- P10 (`perf-evidence-17-3-2026-08-22.md` §4): the 105–106 outstanding requests accounted
  against the ~99-tile prose — 99 `normal` face-0 tiles + 6 second-face requests from the six
  modal Pathway lands + the commander's `size=large` detail fetch (Atraxa; verified against
  `cards.db` and the session log's `large` fetch line).

Re-verification: `tests/unit/test_cdp_harness.py` + `tests/unit/companion/test_routes_card_image.py`
→ 162 passed; ruff check / format / mypy clean; `push --help` unchanged surface (drain listed,
default-3 documented); full suite re-run, verbatim:

```
full suite (-m 'not integration'): 3287 collected, 0 failed, exit 0
```

(3,287 vs the pre-review 3,271: the 16 new harness unit tests.)

**Review findings breakdown:** four layers (blind hunter, edge-case hunter, verification-gap, intent-alignment). 0 intent_gap, 0 bad_spec, **10 patches applied** (0 high, 2 medium, 8 low — the two mediums were unpinned verdict/write-gate logic in the new drain instrument, closed with 16 unit tests mirroring the refetch conventions), **1 deferred** (the pre-existing cold-open drift trend, see frontmatter `deferred`), **8 rejected** as noise/by-design (full list in the Review Triage Log). The coordinator independently re-ran ruff/format/mypy and both touched test files after the patches (162 passed, all gates clean).

**Follow-up review recommendation:** true — patched counts: high 0, medium 2, low 8; score 3×2 + 1×8 = 14 ≥ 5.

**Residual risks:**
- The drain arm's committed figures were produced by the pre-hardening instrument (one repaired re-invocation, D1); the hardening (stable-size log watch, event-pump loop, guards) applies to future runs only — semantics unchanged for the recorded runs, whose 105–106-deep queues and per-lifetime zero-duplicate counts are internally consistent.
- AD-11's "does not block the event loop" claim rests on the end-to-end drain observation plus the pre-existing AST-scan guards; the pacer itself is still never runtime-instrumented (recorded openly in the report §4).
- CM-1 remains arithmetic over the real serialized result models rather than a live-chat capture (c6-9 precedent, spec-ruled); CM-2's session count is app-self-reported log lines calibrated by the caplog unit tests, not an external network tap.
- The cold-open drift (deferred, medium) is the one number trending the wrong way: 4% headroom on the max on this machine.
