# Performance evidence — pre-0.5.0-cut cold-open re-measure + drift diagnosis (R11/A10)

Measured 2026-08-23, per `spec-pre-0-5-0-cut-items.md` item 5 (the epic-17 retro's
release-gating item: re-measure NFR-05 at the branch tip — post-17.4/17.5, post the pre-cut
items 1–7 — and diagnose where the cold-open drift O1 recorded lives). Every figure was
produced by the committed instrument (`scripts/cdp_harness.py budget`) plus one throwaway
scratchpad diagnostic whose output is pasted verbatim below. Raw per-run JSON committed beside
this file: `nfr05-budget-2026-08-23.json`.

## 1. Hardware & conditions

| Item | Value |
|------|-------|
| Machine | AMD Ryzen 9 7950X 16-Core, 63.6 GB RAM |
| OS | Windows 11 Pro, 10.0.26200 |
| Chrome | 151.0.7922.109 (`C:\Program Files\Google\Chrome\Application\chrome.exe`), `--headless=new`, fresh profile per run |
| Repo revision | `c84d4cd969abb136beb67f4456d194eab14e6cf8` (branch `feat/companion-epic-17`, tip after pre-cut items 1–7) |
| Data dir | ONE copy of `C:\Users\brads\AppData\Local\artificial-planeswalker` (read-only source) into the session scratchpad, robocopy 462.82 MB / 906 files; `cards.db` = 325,230,592 bytes (matches source); `image_cache` at copy time = 891 files / 92,861,097 bytes. Copy deleted after the session; never committed. |
| Deck | `813d0434-1bed-4419-bf9d-d9e4070704c4` — "Atraxa Counter Cabinet v2 (owned)", 99 distinct cards; the c4-12 / c7-7 / R2 / 17.3 subject, for comparability |
| Suite state | Full pytest (`3341 collected, 0 failed`) and vitest (`2588, 0 failed`) probe runs finished minutes before the batch |

**Machine-quietness samples — NOT idle-range (see Deviations, D1).** R2 protocol
(`Get-Counter '\Processor(_Total)\% Processor Time'`, 3× ~5 s apart, immediately before the
batch), verbatim:

```
05:19:07  CPU: 21.55%
05:19:12  CPU: 22.57%
05:19:17  CPU: 23.33%
bg3_dx11 running: True
```

A foreground game (`bg3_dx11`, Baldur's Gate 3) was running for the whole session and did not
stop within the session's window; 17.3's baseline samples were ~6%. The measurement was taken
anyway rather than halted — the spec blocks only on non-executability — and every absolute
number below is therefore a **pessimistic upper bound**, recorded as deviation D1.

## 2. Cold-open budget (NFR-05, 1,000 ms budget)

`budget --data-dir <scratchpad copy> --deck-id 813d0434-… --runs 5 --json …` — verbatim:

```
companion on http://127.0.0.1:55541, data dir <scratchpad>\ap-data-copy
active deck set to 813d0434-1bed-4419-bf9d-d9e4070704c4
  run 1: layout 753 ms  format-check at queue position 109  (99 card reads, 216 requests)
  run 2: layout 798 ms  format-check at queue position 109  (99 card reads, 216 requests)
  run 3: layout 587 ms  format-check at queue position 109  (99 card reads, 216 requests)
  run 4: layout 652 ms  format-check at queue position 109  (99 card reads, 216 requests)
  run 5: layout 597 ms  format-check at queue position 109  (99 card reads, 216 requests)

layout time over 5/5 valid runs: min 587 / median 652 / max 798 ms   (NFR-05 budget: 1000 ms)
format-check queue position(s): [109]
raw runs -> _bmad-output/implementation-artifacts/nfr05-budget-2026-08-23.json
EXIT: 0
```

**Verdict: 587/652/798 ms over 5/5 valid runs, max < 1,000 ms, EXIT 0 — the budget holds even
under adverse load.** Because the machine was demonstrably NOT quiet, this is an a-fortiori
result for the budget question (a quiet machine can only be faster) and a *confounded* result
for the drift-magnitude question — see §4 and D1.

## 3. Per-surface comparison across the three sessions

Per-run per-surface DOM-arrival times (ms from `performance.timeOrigin`), from the three
committed JSONs. `grid`/`curve`/`colour`/`deck-list` land within 0.2 ms of each other in every
run of every session, so one "grid family" column stands for the four.

| Session (conditions) | Run | header | grid family | format-check (= layout) |
|---|---|---|---|---|
| 2026-08-16 quiet (`nfr05-quiet-remeasure-2026-08-16.json`) | 1–5 | 36.0–38.5 | 87.5–108.9 | 377.6 / 409.2 / 419.8 / 421.1 / 516.9 |
| 2026-08-22 quiet, 17.3 (`nfr05-budget-2026-08-22.json`) | 1–4 | 36.3–39.4 | 88.1–106.6 | 430.6 / 433.2 / 528.6 / 531.0 |
| 2026-08-22 quiet, 17.3 — run 5 outlier | 5 | 566.7 | 624.0 | 960.3 |
| 2026-08-23 LOADED, this session (`nfr05-budget-2026-08-23.json`) | 1–5 | 44.5–66.2 | 110.9–188.7 | 586.8 / 597.3 / 651.8 / 753.1 / 798.5 |

Session medians: 419.8 (08-16) → 528.6 (08-22) → 651.8 (08-23, loaded). Structural counters:
`card_reads` 99 in every run of every session; `requests_total` 214 (08-16) → 215 (08-22) →
**216 (08-23)**; format-check queue position 107 → 108 → **109**.

## 4. Where the drift lives

**Between the two QUIET sessions (08-16 → 08-22), the drift lives entirely in the
`format-check` surface.** `header` (~37 ms) and the grid family (~88–109 ms) are flat
run-for-run between those sessions; `format-check` moved +11–110 ms per rank position
(medians 419.8 → 528.6). The 08-22 run-5 outlier is a whole-run stall (its header alone took
566.7 ms), not a format-check-specific event. This confirms 17.3's O1 attribution.

**This session cannot extend the quiet-vs-quiet trend line** — under D1's load every surface
inflated together (~+20–75% on header/grid, +13–51% on format-check vs 08-22), which is the
signature of machine contention, not of new code weight on one surface. The structural
counters, which load cannot move, are where this session's diagnosis is honest:

**The "17.4/17.5 landed no code on the measured deck-view path" claim is REFUTED at the
network level.** One request was added to the active-deck cold open: a throwaway diagnostic
run (same harness seams, one run, resource URLs dumped) — verbatim:

```
active deck set to 813d0434-1bed-4419-bf9d-d9e4070704c4
total resources: 216
non-/api/ resources, in start order:
     387.5  http://127.0.0.1:62864/assets/space-grotesk-latin-wght-normal-BhU9QXUp.woff2
     387.8  http://127.0.0.1:62864/assets/index-CQ1PGxaO.css
     387.8  http://127.0.0.1:62864/assets/index-SqKY0adY.js
     479.0  http://127.0.0.1:62864/hero.jpg
     490.1  http://127.0.0.1:62864/favicon.svg
     503.3  http://127.0.0.1:62864/health
```

`/hero.jpg` — 17.5's hero art, 420,280 bytes — is fetched on EVERY cold open, active deck or
not: the boot's transient frame before `GET /api/active-deck` resolves renders the
no-active-deck arm, `Welcome` mounts, and its `<img src="/hero.jpg">` fires before the deck
answer unmounts it. That is the 215 → 216 request and the 108 → 109 queue-position move. (The
"every cold open" holds for the harness's fresh-profile runs and a real first visit; a warm
real-world browser revalidates under the hero's `no-cache` policy — a 304, no re-download — so
the regression's real cost is the first-visit/fresh-profile case.) It is
render-invisible on the deck view (no measured surface is the hero; the DOM claim in the spec
stands) but not network-invisible: a ~420 KB loopback fetch and its decode now share the
cold-open window with the 99 card reads. Its start (479 ms in the dump) puts it in flight
across exactly the span where `format-check` completes. 17.4 landed nothing on the path
(backend/tool/skill only) — the claim is confirmed for 17.4, refuted for 17.5.

**Magnitude honesty:** whether the hero fetch costs measurable layout milliseconds cannot be
separated from D1's load in this session's numbers. What is certain: the budget holds with it
(max 798 ms loaded), and the fetch is architecture, not accident — removing it, deferring it,
or gating the Welcome mount on the active-deck answer are all post-cut options if the trend
keeps widening.

## 5. Hero cache-header pin (R11's second half)

R11 claimed no test pins the hero's cache policy; the source refutes it, verified green this
session: `tests/unit/companion/test_spa.py::test_the_hero_art_is_served_from_the_bundle_root`
asserts `image/jpeg` + `cache-control: no-cache` on `/hero.jpg`, inside the
`TestCacheHeaders` family (policy at `src/companion/app/spa.py:348-371`,
`_REVALIDATE_CACHE_CONTROL`). Nothing was added — the pin already exists; this citation is the
deliverable.

## 6. Deviations

| # | Item | Disposition |
|---|------|-------------|
| D1 | **Machine not quiet**: a foreground game (`bg3_dx11`) ran throughout; CPU samples 21.6/22.6/23.3% against 17.3's ~6% baseline. The spec's block clause covers only non-executability (Chrome/data/deck/zero-valid-runs), so the measurement proceeded and is recorded verbatim. | **Open, for Brad's cut decision.** The budget verdict (EXIT 0, max 798 ms) is safe — load can only have inflated it. The quiet-machine drift trend (363 ms at the c4-12 session, per 17.3's O1 → 420 at R2 → 529 at 17.3) gains no comparable fourth point from this session; if the cut decision wants one, re-run `budget` on a quiet machine (~3 minutes) — the instrument, deck and committed JSON path are ready. |
| D2 | Cold-open median 652 ms / max 798 ms — higher than every prior session. | **Not a budget breach** (EXIT 0, 20% headroom on the max) and not attributable to code vs load (D1); recorded verbatim per the spec's "over budget is not a block" rule, which a-fortiori covers "under budget but higher". |
| D3 | The spec's Code Map said "17.4/17.5 landed no code on the measured deck-view path"; §4 refutes the network half for 17.5 (`/hero.jpg` fetched on every cold open, +1 request, queue 108→109). | **Recorded.** DOM half of the claim stands (no measured surface changed). Post-cut option if drift widens: defer or gate the hero fetch on the active-deck answer. |
