# Performance evidence — Story 17.3 (measure the latency budgets and close the gaps)

Measured 2026-08-22, per `spec-17-3-measure-latency-budgets-close-gaps.md`. Every figure in this
report was produced after the story's code changes and full-suite gates, on a quiet machine, by
the committed instrument (`scripts/cdp_harness.py`) plus two throwaway scratchpad analysis
scripts whose output is pasted verbatim below. Raw per-run JSONs are committed beside this file
(the R2 precedent; c6-9's push JSONs were lost to the scratchpad — that gap is closed here):

- `nfr05-push-warm-2026-08-22.json`
- `nfr05-budget-2026-08-22.json`
- `nfr05-push-drain-2026-08-22.json`

## 1. Hardware & conditions

| Item | Value |
|------|-------|
| Machine | AMD Ryzen 9 7950X 16-Core, 63.6 GB RAM |
| OS | Windows 11 Pro, 10.0.26200 |
| Chrome | 151.0.7922.170 (`C:\Program Files\Google\Chrome\Application\chrome.exe`), `--headless=new`, fresh profile per the arm's rule |
| Repo revision | `bb196c03bf4d4abcbc65eec1f54440e028f8f4b7` (branch `feat/companion-epic-17`) + this story's working-tree changes |
| Data dir | ONE copy of `C:\Users\brads\AppData\Local\artificial-planeswalker` (read-only source) into the session scratchpad, robocopy 453.69 MB / 820 files; `cards.db` = 325,230,592 bytes (matches source); `image_cache` at copy time = 806 files / 83,293,578 bytes. Copy deleted after the session. |
| Deck | `813d0434-1bed-4419-bf9d-d9e4070704c4` — "Atraxa Counter Cabinet v2 (owned)", 99 distinct cards; the c4-12 / c7-7 / R2 subject, for comparability |
| Suite state | Full `-m "not integration"` suite (3,271 collected, 0 failed) finished ~5 minutes before the first quietness sample; nothing else ran during the batch |

Machine-quietness samples (R2 protocol, `Get-Counter '\Processor(_Total)\% Processor Time'`,
3× ~5 s apart, immediately before the measurement batch):

```
12:30:34  CPU: 6.23%
12:30:39  CPU: 6.11%
12:30:44  CPU: 5.85%
```

A second set was taken before the drain arm's re-invocation (see Deviations, D1):

```
12:37:40  CPU: 6.49%
12:37:45  CPU: 6.81%
12:37:50  CPU: 6.83%
```

Both sets are idle-range; no over-budget result needed the quietness ruling.

## 2. Warm push (SC-1 / NFR-05, 250 ms budget)

`push --arm warm --runs 5` — verbatim:

```
companion on http://127.0.0.1:58391, data dir <scratchpad>\ap-copy
arm warm, 6 item(s) per push, 5 run(s)
  prime: 6 image(s) fetched over the network (6 requested)
  run 1: layout 40 ms (from POST return -1 ms, bracket 41 ms)  6 row(s), 6 picture(s) painted, 0/6 off the network
  run 2: layout 42 ms (from POST return -1 ms, bracket 43 ms)  6 row(s), 6 picture(s) painted, 0/6 off the network
  run 3: layout 39 ms (from POST return -1 ms, bracket 41 ms)  6 row(s), 6 picture(s) painted, 0/6 off the network
  run 4: layout 20 ms (from POST return -1 ms, bracket 22 ms)  6 row(s), 6 picture(s) painted, 0/6 off the network
  run 5: layout 31 ms (from POST return -1 ms, bracket 32 ms)  6 row(s), 6 picture(s) painted, 0/6 off the network

warm arm, layout over 5/5 valid runs: min 20 / median 39 / max 42 ms   (SC-1 budget: 250 ms; conservative bracket -- t0 stamped before the POST)
  SC-1's literal reading (t0 at the POST returning): min -1 / median -1 / max -1 ms
  card images fetched over the network per run: [0]
  card images painted per run: [6]
raw runs -> _bmad-output/implementation-artifacts/nfr05-push-warm-2026-08-22.json
EXIT: 0
```

**Verdict: 20/39/42 ms over 5/5 valid runs, max < 250 ms, EXIT 0 — budget holds** on the
post-17.1/17.2 surface. Prior figures on the same instrument: c6-9 = 15/21/36 ms, c7-7 =
17/19/37 ms. The max is +5–6 ms over the prior maxima — same order, no gap.

## 3. Cold-open budget (NFR-05, 1,000 ms budget)

`budget --runs 5` — verbatim:

```
companion on http://127.0.0.1:61508, data dir <scratchpad>\ap-copy
active deck set to 813d0434-1bed-4419-bf9d-d9e4070704c4
  run 1: layout 431 ms  format-check at queue position 108  (99 card reads, 215 requests)
  run 2: layout 529 ms  format-check at queue position 108  (99 card reads, 215 requests)
  run 3: layout 531 ms  format-check at queue position 108  (99 card reads, 215 requests)
  run 4: layout 433 ms  format-check at queue position 108  (99 card reads, 215 requests)
  run 5: layout 960 ms  format-check at queue position 108  (99 card reads, 215 requests)

layout time over 5/5 valid runs: min 431 / median 529 / max 960 ms   (NFR-05 budget: 1000 ms)
format-check queue position(s): [108]
raw runs -> _bmad-output/implementation-artifacts/nfr05-budget-2026-08-22.json
EXIT: 0
```

**Verdict: 431/529/960 ms over 5/5 valid runs, max < 1,000 ms, EXIT 0 — budget holds.** Prior
figures on the same instrument and deck: c4-12 = 311/363/428; c7-7 run A = 420/547/1076 (EXIT 2,
post-suite machine); R2 quiet-machine = 378/420/517 (EXIT 0). Beside R2, min/median drifted
+14%/+26% and the request count moved 214 → 215 (one request added since epic 16/17 landed on the
render path). Run 5's 960 ms outlier leaves only 4% headroom on the max — under budget, so no
deviation is opened, but see Observations O1.

## 4. Drain arm — the AD-11 instrument (push while a cold-cache image queue drains)

New this story: `push --arm drain` re-fetches the 99-card deck's art from the real Scryfall CDN
through the pacer (fresh browser profile AND an emptied backend `image_cache` per run), issues
the push mid-drain, and records the count of `/api/card-image/*` requests genuinely outstanding
(CDP `Network` events: sent − finished/failed) at the push as the positive control — a run with
zero outstanding or a falsy `clients` receipt is named invalid, never numbered. Verdict rule is
the warm arm's: exit 2 when max `layout_ms` ≥ 250 ms.

`push --arm drain --deck-id 813d0434-… --runs 3` (default 3 runs — each is ~99 real CDN
fetches; the pacer's own spacing keeps the harness a polite client) — verbatim:

```
companion on http://127.0.0.1:54221, data dir <scratchpad>\ap-copy
arm drain, 6 item(s) per push, 3 run(s)
active deck set to 813d0434-1bed-4419-bf9d-d9e4070704c4
  run 1: layout 20 ms (from POST return -3 ms, bracket 23 ms)  6 row(s), 6 picture(s) painted, 6/6 off the network, 106 image request(s) outstanding at the push
  run 2: layout 22 ms (from POST return -3 ms, bracket 25 ms)  6 row(s), 6 picture(s) painted, 6/6 off the network, 106 image request(s) outstanding at the push
  run 3: layout 20 ms (from POST return -0 ms, bracket 21 ms)  6 row(s), 6 picture(s) painted, 6/6 off the network, 105 image request(s) outstanding at the push

drain arm, layout over 3/3 valid runs: min 20 / median 20 / max 22 ms   (SC-1 budget: 250 ms; conservative bracket -- t0 stamped before the POST)
  SC-1's literal reading (t0 at the POST returning): min -3 / median -3 / max -0 ms
  card images fetched over the network per run: [6]
  card images painted per run: [6]
  card-image requests outstanding at the push per run: [105, 106]
raw runs -> _bmad-output/implementation-artifacts/nfr05-push-drain-2026-08-22.json
EXIT: 0
```

The 105–106 outstanding requests against the "~99 tiles" prose account exactly: the deck holds
99 distinct cards, six of which (the six modal Pathway lands) carry two imaged faces and so
issue a second `?face=1` grid request each (99 + 6 = 105 `normal` tiles), and the commander's
detail panel adds one `size=large` fetch for Atraxa herself (its fetch-success line at `large`
is in the session log) — 106 in all, with run 3's 105 being a moment when the `large` request
was not among the outstanding.

**Verdict: 20/20/22 ms over 3/3 valid runs with 105–106 card-image requests outstanding at every
push, max < 250 ms, EXIT 0.** The push renders in the same ~20 ms it takes on an idle page while
the pacer holds a hundred-deep cold-cache queue — end-to-end observation that pacing waits in the
queue, never on the event loop, beside the existing AST-scan guards (`test_images.py`) and the
unit interleaving test (`test_routes_card_image.py::TestAQueuedBurstDoesNotStallTheApp`), whose
docstring homes the literal AC on this story. An earlier same-session invocation of this arm
produced equivalent figures (22/20/19 ms, 106 outstanding, EXIT 0) but is superseded — see
Deviations D1 for why it was re-run.

## 5. CM-2 in a real session — fetch-success lines grouped per key per cache lifetime

The new INFO line (`cards.py`, this story) fires once per paid CDN exchange, carrying the full
key (id, face, size); the drain arm records the `companion.log` byte offset at each cache-empty,
so the count below groups per key per lifetime. Scratchpad `cm2_log_count.py` over the drain
JSON — verbatim:

```
lifetime 1 (drain run 1): 29 distinct key(s), 29 fetch(es), 0 key(s) fetched more than once
lifetime 2 (drain run 2): 34 distinct key(s), 34 fetch(es), 0 key(s) fetched more than once
lifetime 3 (drain run 3, + post-drain paint-out/warm-repaint): 112 distinct key(s), 112 fetch(es), 0 key(s) fetched more than once

TOTAL: 175 fetches across 3 cache lifetime(s); 0 duplicate key-lifetime(s)
CM-2 LOG CHECK: PASS -- no key exceeded one fetch per cache lifetime
```

(Lifetimes 1 and 2 are short because each measured run closes its browser ~13 s in, cancelling
the still-queued requests — a cancelled fetch is not a paid exchange and correctly logs nothing.
Lifetime 3 additionally covers the full paint-out below, and its zero duplicates also proves the
keys drain run 3 fetched were served warm during the paint-out.)

**Warm-repaint zero-fetch check** (scratchpad `warm_repaint_check.py`: fresh companion on the
same copy, deck painted fully once, then a second fresh browser repaints the same deck — the
backend disk cache, not the browser cache, must answer) — verbatim:

```
paint-out: 82 fetch-success line(s) (the drain's leftovers)
warm repaint: 99 tile(s) on the glass, 0 new fetch-success line(s)
WARM-REPAINT CHECK: PASS -- zero new fetch-success lines
```

**Verdict: no key exceeded one fetch per cache lifetime, and the warm repaint of all 99 tiles
added zero lines.** The declined in-flight-coalescing residual (two simultaneous first requests
for one key both fetching — c3-7 Q5) was **not observed** in this session; it remains a known
accepted deviation if it ever appears.

## 6. Image-cache footprint (real cache, read-only, 2026-08-22)

Measured on the REAL `%LOCALAPPDATA%\artificial-planeswalker\image_cache` (never written by this
session; the drain arm emptied only the scratchpad copy's cache):

| Metric | Value |
|--------|-------|
| Files | 806 |
| Bytes | 83,293,578 (79.4 MiB) |
| Distinct printings | 580 |
| Shards in use | 227 of 256 |
| `normal` | 597 files, 54,109,146 bytes — avg 88.5 KiB/tile |
| `large` | 209 files, 29,184,432 bytes — avg 136.4 KiB/tile |

Beside README.md's 2026-08-02 figures (~90 KB per `normal` tile, ~8.5 MB per 99-tile deck,
~95 MB per ~1,000-printing library): the measured `normal` average of 88.5 KiB confirms the
~90 KB figure; 580 printings at ~79 MiB extrapolates to ~140 MB per 1,000 printings **when the
detail panel's `large` renditions are in the mix** (the README's ~95 MB figure is `normal`-only
arithmetic and predates 209 `large` entries). README figures deliberately unchanged
(`test_image_cache_docs.py` pins them); the growth-rate context lives here. Still unbounded by
design — this measurement is what an eventual eviction policy would be sized against.

## 7. CM-1 — result-size arithmetic over the five companion tools

Scratchpad `cm1_token_arithmetic.py`: every status of every result model the five tools can
mint, serialized exactly as the wire does (`model_dump_json()`), with 10,000-char adversarial
`deck_id`/`deck_name` inputs pushed through the shipped `_truncate_for_echo` bound. Replaces
c6-9's two-tool figure. Output (condensed to the per-tool summary; ~4 chars/token):

```
  companion_show_suggestions   worst  224 chars (~56 tok)   ordinary  116 chars (~29 tok)
  companion_show_swaps         worst  218 chars (~54 tok)   ordinary  115 chars (~29 tok)
  companion_show_tier_list     worst  218 chars (~54 tok)   ordinary  106 chars (~26 tok)
  companion_show_groups        worst  219 chars (~55 tok)   ordinary  107 chars (~27 tok)
  companion_set_active_deck    worst  369 chars (~92 tok)   ordinary  198 chars (~50 tok)

  max single result           : 369 chars (~92 tokens)
  ceiling (CM-1 / AC 5)       : 800 chars (~200 tokens)
  test-suite per-result bound : 400 chars
  session-level worst case    : all five tools once each at their worst = 1248 chars (~312 tokens)
```

**Verdict: the ~200-token per-result ceiling holds with 2× headroom** — worst single result is
369 chars (~92 tokens), the `database_not_initialized` control-tool answer; every push-tool
worst case is ≤ 224 chars. Session-level figure: a session that hit all five tools at their
worst pays ~312 tokens of results total; an ordinary five-tool session pays ~161 tokens
(642 chars). Enforcement citations (the tests that pin these properties): the 400-char
per-result bounds and planted-sentinel no-payload-echo assertions in
`tests/integration/mcp_server/test_companion_tool.py` — suggestions `:720-751`, swaps
`:915-943`, tiers `:1093-1120`, groups `:1271-1298`, control `:463-571` (all in the ordinary
`-m "not integration"` set and green in this session's full-suite runs).

## 8. Probe proof (Testing Rules)

Planted violation: the new fetch-success line demoted to DEBUG. Full-suite probe, verbatim:

```
full suite (-m 'not integration'): 3271 collected, 3 failed, 0 errored, exit 1
  RED    tests/unit/companion/test_routes_card_image.py::TestAFetchSuccessLogsExactlyOnce::test_one_real_fetch_logs_one_success_line_carrying_the_full_key
  RED    tests/unit/companion/test_routes_card_image.py::TestAFetchSuccessLogsExactlyOnce::test_two_fetches_for_two_keys_log_two_lines_grouped_apart
  RED    tests/unit/companion/test_routes_card_image.py::TestAFetchSuccessLogsExactlyOnce::test_a_warm_cache_hit_logs_no_new_success_line
```

Plant restored, full suite re-run:

```
full suite (-m 'not integration'): 3271 collected, 0 failed, exit 0
```

## 9. Deviations

| # | Item | Disposition |
|---|------|-------------|
| D1 | The drain arm's FIRST invocation (same session, quiet, 3/3 valid, 22/20/19 ms, EXIT 0) could not support the per-lifetime CM-2 count: its cache-lifetime marker — a line appended to `companion.log` by the harness process — was **overwritten** by the backend child, whose inherited stdout handle writes at its own file pointer (not OS-level append). Instrument failure on the CM-2 seam, not an over-budget result. | **Closed.** The instrument was repaired to record read-only log byte-offsets in the run JSON instead of writing markers, and the arm was re-invoked once (fresh quietness samples taken, figures equivalent: 20/20/22 ms). The committed JSON and §4/§5 are the repaired invocation. Within the spec's one-re-invocation allowance. |
| D2 | In-flight-coalescing residual (two simultaneous first fetches for one key, c3-7 Q5). | **Not observed** in 175 logged fetches across 3 lifetimes. Remains the known accepted deviation if ever seen. |
| D3 | Session-level CM-1 worst case is ~312 tokens (five tools once each at their individual worst). | **No gap.** CM-1's ceiling is per result (~200 tokens); every single result is ≤ ~92 tokens. The session figure is recorded as context, as the spec asks. |

No budget was breached; nothing is pending acceptance, and the spec's frontmatter `deferred`
stays empty.

## 10. Observations (recorded, not deviations)

- **O1 — cold-open drift continues.** Quiet-machine cold-open medians: c4-12 363 → R2 420 →
  now 529 ms, with a 960 ms outlier in run 5 (the other four runs sit 431–531). Still EXIT 0,
  but headroom on the max is down to 4% on this machine and the trend has survived two quiet
  remeasurements — R2's addendum called the earlier drift "recorded-not-explained", and it has
  since widened. Worth a diagnosis pass before 0.5.0 if any more render-path weight lands.
- **O2 — request count 214 → 215** on the cold open versus R2 (one request added by epics 16–17;
  format-check queue position moved 107 → 108 correspondingly).
- **O3 — drain-arm pushes render marginally faster than warm-arm ones** (20/20/22 vs 20/39/42 ms)
  even though their six suggestion images are cold; layout never waits on images (AC 5's blocked
  arm proved that at c6-9), so this is run-to-run noise, consistent with pacing not touching the
  event loop.
