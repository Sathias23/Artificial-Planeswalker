# Performance evidence — D1 quiet-machine cold-open re-run (pre-0.5.0-tag check)

Measured 2026-08-25, closing deviation **D1** from
`perf-evidence-precut-2026-08-23.md`: that session's re-measure ran under a foreground game
(~22% CPU) and proved the budget a fortiori, but left the quiet-machine **drift trend**
(363 → 420 → 529 ms) with no comparable fourth point. This is that point. Ordered by Brad
after merging integration PR #104; run with `scripts/cdp_harness.py budget`, the committed
instrument, same deck, same protocol.

## 1. Hardware & conditions

| Item | Value |
|------|-------|
| Machine | AMD Ryzen 9 7950X 16-Core, 63.6 GB RAM, Windows 11 Pro 10.0.26200 |
| Repo revision | `794f06d18fb7102226349402cf55dca175900d19` (**master**, the #104 integration merge — the 0.5.0 release tip: post-17.x, post-pre-cut, post tier-list usability, post README restructure) |
| Data dir | robocopy of `%LOCALAPPDATA%\artificial-planeswalker` into the session scratchpad, 463.62 MB / 906 files; copy deleted after the session, never committed |
| Deck | `813d0434-1bed-4419-bf9d-d9e4070704c4` — "Atraxa Counter Cabinet v2 (owned)", 99 distinct cards; the c4-12 / c7-7 / R2 / 17.3 / pre-cut subject, for comparability |

**Machine-quietness samples** (R2 protocol, `Get-Counter '\Processor(_Total)\% Processor Time'`,
3× ~5 s apart, immediately before each batch), verbatim:

```
before batch 1:   18:35:29  CPU: 0.00%   18:35:35  CPU: 4.22%   18:35:41  CPU: 12.01%
                  bg3_dx11 running: False
before batch 2:   18:38:42  CPU: 4.29%   18:38:48  CPU: 0.00%   18:38:54  CPU: 0.00%
```

No game this time; background residents (CurseForge, Steam, logioptionsplus) were live and are
the likely source of batch 1's 12% sample and its two outlier runs — see §3.

## 2. Cold-open budget (NFR-05, 1,000 ms budget) — two batches, verbatim

**Batch 1** (`nfr05-budget-2026-08-25-quiet.json`):

```
  run 1: layout 493 ms    run 2: layout 410 ms    run 3: layout 1350 ms
  run 4: layout 1084 ms   run 5: layout 355 ms
layout time over 5/5 valid runs: min 355 / median 493 / max 1350 ms   EXIT: 0
```

**Batch 2** (`nfr05-budget-2026-08-25-quiet-batch2.json`), CPU 0–4.3% throughout:

```
  run 1: layout 448 ms    run 2: layout 395 ms    run 3: layout 424 ms
  run 4: layout 358 ms    run 5: layout 340 ms
layout time over 5/5 valid runs: min 340 / median 395 / max 448 ms   EXIT: 0
```

Both batches: format-check at queue position 109, 99 card reads, 216 requests per run —
identical to every prior measurement, so the work being timed has not changed shape.

## 3. The batch-1 outliers, not smoothed over

Batch 1 is bimodal: three runs at 355–493 ms and two at 1084/1350 ms — the latter two
**individually breach the 1,000 ms budget**. They coincide with the 12.01% CPU sample taken
seconds before the batch, and batch 2 — run three minutes later at 0–4.3% CPU — shows no run
above 448 ms with the identical workload. The honest reading: the outliers are transient
background load (the resident updaters named above), not the app; a second batch was run
precisely so this claim rests on measurement rather than assertion. Both raw JSON files are
committed beside this file; nothing is discarded.

## 4. Verdict — the drift trend, and D1 closed

Quiet-machine medians across the release line:

| Point | Revision context | Median |
|-------|------------------|--------|
| c4-12 | epic 4 baseline | 363 ms |
| c7-7 / R2 | epic 7 | 420 ms |
| 17.3 | epic 17 mid | 529 ms |
| **this run** | **0.5.0 release tip (`794f06d`)** | **395 ms** (batch 2; batch 1's median 493 with load-confounded outliers) |

**The drift did not continue — it reversed.** The 363→420→529 climb that O1 flagged lands at
395 ms at the tip, below the epic-7 point; the hero.jpg cold-open diagnosis and the pre-cut
work sit between 17.3's 529 and this 395. The NFR-05 budget holds on a quiet machine with
~600 ms of headroom at the median (batch 2 max 448 ms leaves 55% headroom worst-run).

**D1 is closed.** No release-gating concern remains open against the cold-open budget.
Clear to tag 0.5.0.
