---
title: 'Pre-Epic-7 Real-Deck Gate (G-R2) — real-deck sanity pass'
type: 'chore'
created: '2026-07-17'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '92e9307'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The green benchmark (real snapshot data since 6.3) proves scoring *shape* on ten reconstructed decks, not real-world validity — and Epic 7, where tuning ossifies into the MCP tools, is next. Epic-5 action item 5 was never executed; the epic-6 retro escalated it to this blocking gate.

**Approach:** Throwaway harness (scratchpad, never committed) that loads every real saved deck from the live central DB through the exact Epic 7 path — `DeckRepository.get_deck_with_cards` → `ComboSnapshotRepository.get_variants_for_names` → pure `score()` — and emits a committed gate report (tier / Bracket floor / cEDH candidacy / signals per deck) for Sathias to review. Each divergence from his judgment is logged as a **named Epic 7 calibration input** — a divergence is data, not automatically a bug.

## Boundaries & Constraints

**Always:**
- Harness is scratchpad-only and read-only against the DB; its full source is embedded in the report appendix for reproducibility (6.3 Task 5 precedent).
- Mirror the benchmark wiring (`test_assessment_benchmark.py`): mainboard-only (`sideboard=False`) into `score()`; commanders as resolved name strings.
- Commander resolution: `DeckCard.commander` flag first; the live DB has **zero flagged rows** (all decks predate 6.1), so fall back to an explicit harness-local `deck_id → commander names` override map (the two Kotis decks, Sephiroth). No name-guessing heuristics.
- Profile mapping is explicit and reported per deck: `standard`/`historic` → `STANDARD_PROFILE`; `brawl`/`standardbrawl` → `COMMANDER_PROFILE` **flagged provisional** (Epic 7 owns the real format→profile mapping; this mapping choice is itself a calibration observation).
- Report every deck (all 20), keyed by deck id (duplicate names exist); decks below format minimum (3-, 1-, 20-card stubs) are scored but flagged "incomplete — outputs not meaningful".
- Carry the standing caveats into the report: `CEDH_TUTOR_MIN=3`, FR6 tutor definition undercounts, `game_changers.unknown_count` surfaced per deck.

**Ask First:**
- If the harness surfaces a crash or defect in `src/logic/assessment/**` / repositories, stop and ask — a fix is its own spec, not gate scope.
- Any urge to retune constants or thresholds based on results — that is Epic 7 calibration work.

**Never:**
- No edits anywhere under `src/**`, `tests/**`, or `scripts/**`; the working tree gains only the report (+ this spec).
- No committing the harness file; no network on the assessment path; no DB writes.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Standard 60-card deck | e.g. Mardu Midrange v2 | Vector, for_format_score, tier; `bracket_floor=None`, `cedh_candidate=False` (heuristic_only) | N/A |
| Brawl-family deck | Kotis 60/100-card, commander via override map | Commander named in report; bracket floor {2,3,4} + cEDH candidacy under provisional `COMMANDER_PROFILE` | N/A |
| Stub deck | Graveyard Gravy (3), Iron Man (1), Sephiroth (20) | Scored, flagged incomplete | Never crashes the run |
| No commander resolvable | Standard decks (expected) | `commanders=[]`; commander_required variants excluded by matcher | N/A |
| Snapshot unavailable | `snapshot_is_available()` False | Abort with clear message before scoring | Expected available (94,962 variants); abort = investigate env |
| Combo-relevant deck | e.g. Ultron's Forge (combo engine) | Matched combos listed with bucket + bracket_tag | N/A |

</frozen-after-approval>

## Code Map

- `src/logic/assessment/scorer.py:109` -- `score(deck_cards, *, commanders, variants, profile) -> CoreAssessment`; `CoreAssessment` fields at :63 (vector, for_format_score, tier, bracket_floor, cedh_candidate, game_changers, combos, structural_gaps, mass_land_denial, extra_turn_chains)
- `src/logic/assessment/profiles.py:132,:168` -- `COMMANDER_PROFILE` (brackets) / `STANDARD_PROFILE` (heuristic_only)
- `src/data/repositories/deck.py:547` -- `get_deck_with_cards(deck_id) -> Deck | None`; nests full `Card` per `DeckCard` (schemas `deck.py:14,:39`)
- `src/data/repositories/combo_snapshot.py:40,:62,:79` -- `snapshot_is_available` / `get_metadata` / `get_variants_for_names(names)`
- `src/data/database.py:32,:69` -- `create_engine()` (central URL default) + `create_session_factory`; async, so `asyncio.run`
- `scripts/view_deck.py:78-107` -- canonical script pattern: engine → session → repo → dispose (deck detaches safely; scoring is pure)
- `tests/integration/logic/test_assessment_benchmark.py:102,:159` -- precedent wiring + expectation vocabulary; DO NOT modify
- `src/logic/assessment/dimensions.py:133` -- `CEDH_TUTOR_MIN=3` caveat source
- Live data: 20 decks (14 full Standard 60s, Prismatic Dragon 59/60, Kotis standardbrawl 60 / brawl 100, 3 stubs at 1/3/20 cards); 0 `commander` flags; snapshot v5.6.0 with 94,962 variants

## Tasks & Acceptance

**Execution:**
- [x] `<scratchpad>/g_r2_real_deck_harness.py` -- write harness: open central DB, verify `snapshot_is_available` + `get_metadata` (report data vintage), enumerate all decks, per deck: load with cards → resolve commanders (flag, else override map) → mainboard filter → `get_variants_for_names(card names)` → `score()` under mapped profile → collect full `CoreAssessment` + candidate-variant count -- the exact Epic 7 path, G-R2
- [x] `_bmad-output/implementation-artifacts/pre-epic-7-real-deck-gate-report-2026-07-17.md` -- run harness against live DB; write report: snapshot metadata header, summary table (deck / format / profile / commanders / score / tier / bracket / cEDH / combos matched / flags), per-deck detail (vector, game_changers incl. unknown_count, structural gaps, matched combos with buckets, MLD/extra-turn flags), caveats section, **review sheet** (per deck: `[ ] plausible / [ ] divergence:` with named-calibration-input template), harness source appendix -- the reviewable gate artifact
- [ ] Sathias review -- accept each deck as plausible or log named divergences in the report; gate closes on completed review sheet (divergences become Epic 7 calibration inputs) -- *Owner: Sathias*

**Acceptance Criteria:**
- Given the live central DB, when the harness runs, then it exits 0 and all 20 saved decks appear in the report with tier + score; Brawl-family decks additionally carry bracket floor + cEDH candidacy and their resolved commander names.
- Given the run completes, when `git status` is checked, then the tree contains only the report (and spec updates) — no `src/` changes, no harness file.
- Given Sathias completes the review sheet, when every deck is marked plausible or has a named divergence entry, then G-R2 is closed and Epic 7 story creation unblocks.

## Spec Change Log

## Verification

**Commands:**
- `uv run python <scratchpad>/g_r2_real_deck_harness.py` -- expected: exit 0, per-deck output, no exceptions
- `git status --short` -- expected: only the report + spec artifacts

**Manual checks (if no CLI):**
- Report review sheet completed by Sathias — every deck marked plausible or divergence-logged.

## Suggested Review Order

**The gate verdict surface — start here**

- All 20 decks at a glance: score, tier, bracket, cEDH, flags.
  [`report:22`](pre-epic-7-real-deck-gate-report-2026-07-17.md#L22)

- Cross-deck saturation patterns — pre-digested calibration-input candidates.
  [`report:859`](pre-epic-7-real-deck-gate-report-2026-07-17.md#L859)

- Format-blind almost_included inflation (Betor, combo_potential=100 on Standard decks).
  [`report:868`](pre-epic-7-real-deck-gate-report-2026-07-17.md#L868)

- Kotis Saboteur 0-variant outlier: probe-verified genuinely combo-inert, not a normalization bug.
  [`report:869`](pre-epic-7-real-deck-gate-report-2026-07-17.md#L869)

**Your review task — what closes the gate**

- Review sheet: 20 decks, two checkboxes each — plausible or named divergence.
  [`report:872`](pre-epic-7-real-deck-gate-report-2026-07-17.md#L872)

- Named-divergence template — divergences become Epic 7 calibration inputs.
  [`report:937`](pre-epic-7-real-deck-gate-report-2026-07-17.md#L937)

- Standing caveats to hold in mind while judging (CEDH_TUTOR_MIN, provisional Brawl profile).
  [`report:849`](pre-epic-7-real-deck-gate-report-2026-07-17.md#L849)

**Commander/bracket path — the only decks exercising it**

- Kotis 100-card Brawl row: bracket 2, 12 combos matched — deepest Commander-path exercise.
  [`report:32`](pre-epic-7-real-deck-gate-report-2026-07-17.md#L32)

- Sephiroth DFC override note — commander storage/lookup calibration input for 7.1.
  [`report:735`](pre-epic-7-real-deck-gate-report-2026-07-17.md#L735)

**Provenance & peripherals**

- Run provenance: baseline commit, snapshot vintage v5.6.0 / 94,962 variants.
  [`report:6`](pre-epic-7-real-deck-gate-report-2026-07-17.md#L6)

- Full harness source appendix — one-file reproducibility, 6.3 Task 5 precedent.
  [`report:948`](pre-epic-7-real-deck-gate-report-2026-07-17.md#L948)

- Deferred product-level finding: format-blind combo_potential inflation.
  [`deferred-work.md:3`](deferred-work.md#L3)
