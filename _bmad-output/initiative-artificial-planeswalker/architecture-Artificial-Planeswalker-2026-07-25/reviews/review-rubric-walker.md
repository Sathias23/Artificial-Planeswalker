# Reviewer lens — good-spine rubric walker

**Target:** `ARCHITECTURE-SPINE.md` (companion-app, 2026-07-25)
**Verdict:** PASS with two gaps, both closed.

## Rubric

| Criterion | Verdict | Note |
| --- | --- | --- |
| Fixes the real divergence points for the level below; misses none | **was FAIL** | Seven holes found by the adversarial-seam lens; all closed. Now passes. |
| Every AD's Rule is enforceable and prevents its stated divergence | PASS | Two are machine-enforced (AD-2, AD-3 via one test file; AD-12 via `git diff --exit-code`). The rest are legible constraints a reviewer can apply without judgement calls. AD-1's "defines no second card or deck shape" is the softest, but its consequence — reusing the existing repositories — is concrete. |
| Nothing under Deferred could let two units diverge | PASS | Each deferral names either an accepted divergence (cross-tab) or a decision with no current consumer (eviction policy, TS 7, Playwright). FR-18's deferred *home* is safe because AD-6 already fixes the data it needs. |
| Named tech verified-current | **was FAIL** | `TypeScript >=5.9` was asserted. See `review-tech-currency.md` C-1 — corrected to `>=5.9,<6.1`. |
| Ratifies rather than contradicts the brownfield codebase | PASS | Inherited Invariants ratifies seven existing project constraints by source. Every code claim was checked against the files, not memory. AD-2 deliberately *departs* from PRD NFR-02 and says so, with the amendment flagged — a stated override, not a silent contradiction. |
| Covers the driving spec's capabilities | **was PARTIAL** | Capability map covered Features A–G plus NFR-01/03 but had no row for NFR-05 (performance), whose invariants live split across AD-7 and AD-11. Row added. |
| No new AD weakens an inherited one | N/A | No parent spine. The sibling deck-power spine is same-altitude; its status-token convention is adopted (AD-8), not contradicted. |
| Every dimension the altitude owns is decided, deferred, or open — especially the operational envelope | **was PARTIAL** | Operational envelope is covered (AD-15 process model + logging, AD-4 single-instance and lifecycle, AD-13 packaging, AD-14 launch). Data model: explicitly no new tables. Security: AD-5. Testing: AD-10. Build/release: AD-12/AD-13. **Gap found in the frontend dimension** — see R-1. |

## Findings

### R-1 — MEDIUM — Client-side card hydration has no owner

The spine says UI state comes from exactly two inputs and lives in zustand. It does not say
**how a card is hydrated**, and the UX makes that load-bearing: the detail panel updates on
*hover* across a 100-tile grid, and every agent view hydrates its own thumbnails. Two builders
diverge predictably — one reaches for a data-fetching library with request dedup and caching
built in, another hand-rolls per-component `fetch` in an effect. The second produces duplicate
in-flight requests for the same card ID on every cursor sweep.

This also quietly contradicts the addendum's "zustand store is client-side only" if a second
state library arrives alongside it.

**Fix applied** — AD-12 now requires a single card-hydration cache in the store, keyed by card
ID, deduping in-flight requests, and bans a second data-fetching/state library.

### R-2 — LOW — NFR-05 had no capability-map row

Its invariants exist (AD-7's no-DB-read-on-push-path, AD-11's excluded first-fetch paint) but
nothing pointed at them from the map, which is the consistency auditor's checklist. **Row added.**

## Notes, not findings

- The spine is long for a feature spine (16 ADs). Justified: three processes, two languages, two
  credentials and a public release gate. No AD reads as filler; each names a divergence.
- The Deferred section carries eight entries, which is the right shape — it is doing real work
  keeping FR-16/FR-21/Tauri/edits out of the invariants.
- AD-2 and AD-15 both depart from or extend PRD text. Both are flagged for amendment rather than
  left to diverge silently. That is the correct handling.

## Verdict

Two gaps, both closed in-place. The spine covers its altitude's dimensions with nothing silent.
