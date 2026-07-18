---
stepsCompleted: [1, 2, 3, 4, 5, 6]
readinessStatus: 'READY'
findings: { critical: 0, major: 0, minor: 3 }
assessmentDate: '2026-07-11'
feature: 'Deck Power-Level Assessment'
documentsUnderReview:
  - _bmad-output/specs/spec-deck-power-assessment/SPEC.md
  - _bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-11/prd.md
  - _bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-11/addendum.md
  - _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/epics-deck-power-assessment.md
documentsExcluded:
  - _bmad-output/planning-artifacts/prd.md (SUPERSEDED — Letta/PydanticAI)
  - _bmad-output/planning-artifacts/architecture.md (SUPERSEDED — Letta-first)
  - _bmad-output/planning-artifacts/epics.md (different scope — Phase-1 MCP pivot)
---

# Implementation Readiness Assessment Report

**Date:** 2026-07-11
**Project:** Artificial-Planeswalker — Deck Power-Level Assessment

## Document Inventory

**Under review (Jul-11 deck-power-assessment set):**

| Type | File |
| --- | --- |
| SPEC (canonical contract) | `specs/spec-deck-power-assessment/SPEC.md` |
| PRD | `prds/prd-…-2026-07-11/prd.md` (+ `addendum.md`) |
| Architecture | `architecture/…-2026-07-11/ARCHITECTURE-SPINE.md` (AD-1…AD-12) |
| Epics & Stories | `epics-deck-power-assessment.md` (4 epics / 18 stories) |
| UX | N/A — headless MCP feature, no UI |

**Excluded (superseded / different scope):** `prd.md`, `architecture.md`, `epics.md` (Jul-10
MCP-pivot generation).

## PRD Analysis

Source: `prds/prd-…-2026-07-11/prd.md` (+ `addendum.md`), cross-checked against `SPEC.md`.

### Functional Requirements (24)

- **FR1** — Expose `assess_deck_power(deck_id, format?)`; load via `get_deck_with_cards` (full `Card` rows), `format ∈ {commander, standard}`.
- **FR2** — Infer format when omitted; graceful error (not crash) on unsupported/unrecognized format.
- **FR3** — Resolve every card against the local snapshot; count unresolved/ambiguous → confidence.
- **FR4** — Load a versioned format profile; emit `format_profile_version`.
- **FR5** — Mana curve, average mana value, land count.
- **FR6** — Count ramp / draw / removal / tutors via oracle-text + type-line classification.
- **FR7** — Interaction detail: instant-speed ratio + interaction-CMC distribution.
- **FR8** — Karsten land-count delta (Commander + 60-card) → flood/screw flag; pip/colored-source consistency.
- **FR9** — Rule-of-8 / functional-redundancy + 8×8 structural-coverage gaps.
- **FR10** — Win-condition tagging (combo pieces, "you win the game", evasive/haymaker finishers).
- **FR11** — Game Changer membership per card + deck count (new `game_changer` field; backfill re-import).
- **FR12** — Hard Bracket triggers: mass land denial + extra-turn chains (oracle-text patterns).
- **FR13** — Call Spellbook `find-my-combos`; bucket `included` vs `almostIncluded`; capture per-combo tag/produces/popularity/earliest-turn.
- **FR14** — Cache Spellbook responses (≥24h) with throttling + 429 backoff.
- **FR15** — Map combos → two-card-infinite Bracket trigger + combo-potential dimension.
- **FR16** — 7-dimension vector (each 0–100); `speed` deterministic (curve + ramp + combo earliest-turn).
- **FR17** — Consistency via hypergeometric key-piece + mana access by turn N (deterministic).
- **FR18** — Commander: Bracket floor (1–5) from GC + triggers + combos; cEDH candidacy only, never assert B5.
- **FR19** — Weighted-aggregate → for-format 0–100; derive 1–10 projection. No absolute cross-format score.
- **FR20** — Standard: heuristic-only score, no Bracket, no percentile; always with descriptive label.
- **FR21** — Categorical confidence (`low|medium|high`) + `reasons[]`; degradation lowers confidence, never crash/silent-zero. No numeric band.
- **FR22** — Return both a human summary and raw structured JSON (schema minus absolute-score/low-high/percentile/EDHREC).
- **FR23** — `flags` block: Game Changers, combos, structural gaps, mass-land-denial/extra-turn booleans, `cedh_candidate`.
- **FR24** — Every for-format score carries a descriptive tier label (no bare number).

**Total FRs: 24.**

### Non-Functional Requirements (8)

- **NFR1** — Determinism: identical deck + snapshot + cached combo data → identical scores (no randomness).
- **NFR2** — Explainability: every score traces to cards/signals via `flags`.
- **NFR3** — Graceful degradation (mirrors `index_unavailable`): never crash or silent zero.
- **NFR4** — Latency: local heuristics instant; single live Spellbook call cached with backoff.
- **NFR5** — Data freshness / versioning: format profile versioned; output states which version.
- **NFR6** — Testability / calibration: committed benchmark set anchors correctness.
- **NFR7** — Architecture conformance: stateless tool alongside analysis tools; `src/data`/`src/logic` framework-free. (Async per AD-1, overriding PRD's stale "sync def".)
- **NFR8** — Scoring transparency: signal→0–100 mappings + weights documented, hand-tuned, adjustable, benchmark-validated.

**Total NFRs: 8.**

### Additional Requirements (Architecture spine + addendum)

- **AD-1…AD-12** — binding invariants (async tool; pure core / impure edge; `FormatProfile` frozen data; nullable `game_changer`; ephemeral combo cache w/ WAL; degradation ladder; versioned `AssessDeckPowerResult`; deterministic serialization; layer placement + Spellbook client policy; shared oracle-text taxonomy; canonical `ComboRecord`; canonical multiplicity-aware cache key).
- **Data-model change** — `game_changer: bool | None` on `CardModel`/`Card` + `transform_scryfall_card`; hand-written migration + re-import.
- **Implementation constants** — Karsten formulas, redundancy tables, Bracket gating, GC list (~53 cards).
- **Calibration benchmark** — committed held-out set (precons ~B2; cEDH lists flag as candidates); first implementation task.

### PRD Completeness Assessment

The PRD is **final, self-consistent, and unusually complete** for readiness purposes: FRs are grouped
by pipeline stage with globally stable IDs, NFRs are explicit, and the three open questions (dimension
curves, benchmark composition, earliest-turn heuristic) are each **assigned an owner** (architecture /
first-implementation phase) rather than left unresolved. One PRD/architecture conflict exists (NFR7
"sync def" vs AD-1 "async def") — **already reconciled** in the architecture spine and the epics, with
AD-1 binding. No missing requirement classes detected.

## Epic Coverage Validation

### Coverage Matrix

| FR | Requirement (short) | Epic → Story | Status |
| --- | --- | --- | --- |
| FR1 | Tool signature + full-row deck load | E4 → 4.1 | ✓ Covered |
| FR2 | Format inference + graceful error | E4 → 4.1 | ✓ Covered |
| FR3 | Card resolution + unresolved count | E4 → 4.1 | ✓ Covered |
| FR4 | Versioned `FormatProfile` | E2 → 2.2 | ✓ Covered |
| FR5 | Curve / avg MV / land count | E2 → 2.4 | ✓ Covered |
| FR6 | Ramp/draw/removal/tutor classifiers | E2 → 2.3 | ✓ Covered |
| FR7 | Instant-speed ratio + interaction CMC | E2 → 2.5 | ✓ Covered |
| FR8 | Karsten land + pip math | E2 → 2.4 | ✓ Covered |
| FR9 | Rule-of-8 / 8×8 structural gaps | E2 → 2.5 | ✓ Covered |
| FR10 | Win-condition tagging | E2 → 2.3 | ✓ Covered |
| FR11 | Game Changer field + count | E1 → 1.1, 1.2 (read in E2 → 2.7) | ✓ Covered |
| FR12 | Mass-land-denial + extra-turn triggers | E2 → 2.3 | ✓ Covered |
| FR13 | Spellbook `find-my-combos` + buckets | E3 → 3.2 | ✓ Covered |
| FR14 | ≥24h cache + throttle + backoff | E3 → 3.2, 3.3 | ✓ Covered |
| FR15 | Combo → bracket trigger + dimension | E2 → 2.6 | ✓ Covered |
| FR16 | 7-dimension vector (speed deterministic) | E2 → 2.7 | ✓ Covered |
| FR17 | Hypergeometric consistency | E2 → 2.5 | ✓ Covered |
| FR18 | Commander Bracket floor + cEDH candidacy | E2 → 2.7 | ✓ Covered |
| FR19 | For-format aggregate + 1–10 projection | E2 → 2.8 | ✓ Covered |
| FR20 | Standard heuristic-only path | E2 → 2.8 | ✓ Covered |
| FR21 | Categorical confidence + reasons ladder | E2 → 2.8 (vocab) + E4 → 4.2 (ladder) | ✓ Covered |
| FR22 | Dual output (summary + structured) | E4 → 4.3 | ✓ Covered |
| FR23 | `flags` block | E4 → 4.3 (values from E1–E3) | ✓ Covered |
| FR24 | Descriptive tier label | E2 → 2.8 + E4 → 4.3 (surface) | ✓ Covered |

### Missing Requirements

**None.** All 24 FRs trace to at least one story's acceptance criteria. No orphan requirements
(FR-in-PRD-but-not-epics) and no phantom coverage (epic-story-with-no-PRD-basis) detected.

### Coverage Statistics

- Total PRD FRs: **24**
- FRs covered in epics/stories: **24**
- Coverage percentage: **100%**
- NFR anchoring: all 8 NFRs anchored to stories (NFR1 → 2.9/4.3/4.4; NFR3 → 4.2; NFR6 → 2.1/2.9; NFR7 → 4.1; NFR8 → 2.9; NFR2/4/5 within their dimension/cache/profile stories).
- Architecture invariant coverage: all AD-1…AD-12 cited by their implementing stories.

## UX Alignment Assessment

### UX Document Status

**Not Found — and correctly absent (not a gap).** No `*ux*` document exists.

### Alignment Issues

**None.** UX is not implied by this feature. PRD §3 states explicitly: *"There is no separate UI and
no standalone persona section."* This is a **headless MCP capability** — the single operator works
through an AI agent that calls the tool; the only human-facing surface is the `summary` string inside
`AssessDeckPowerResult`, which is a deterministic projection of the structured assessment (AD-8) and
is covered by FR22 / FR24. There are no screens, flows, components, or accessibility surfaces to
design or align.

### Warnings

**None.** The absence of a UX document is a deliberate, PRD-stated design decision — not a missing
artifact. No architectural gap results (the summary-string contract is fully specified by AD-7/AD-8
and FR22/FR24).

## Epic Quality Review

Validated against the create-epics-and-stories standards: user value, epic independence, forward
dependencies, story sizing, AC quality, DB-creation timing, and brownfield fit.

### 🔴 Critical Violations

**None.** No technical-milestone epics that are *pure* plumbing with zero downstream value; no forward
dependencies (no story depends on a later story in its epic); no epic requires a *future* epic; no
epic-sized unimplementable stories.

### 🟠 Major Issues

**None.** All 18 stories are single-session-sized with Given/When/Then ACs that include error/edge
paths (unsupported format, `deck_not_found`, NULL `game_changer`, Spellbook outage, stale cache,
casing mismatch). DB entities are created only where first needed (Epic 1 alters `card`; Epic 3
creates the combo-cache table) — no upfront "create all tables."

### 🟡 Minor Concerns (accept-with-awareness, not blockers)

1. **Enabler epics precede user-visible value (inherent to a single-tool feature).** A strict reading
   of "each epic delivers independent end-user value" is only *fully* met by **Epic 4** — the feature
   becomes callable through the agent only when the tool is registered. Epics 1–3 are enabling layers
   (card data / pure scorer / combo adapters). **Verdict: accepted.** This is the correct decomposition
   for a functional-core/imperative-shell single tool: each of 1–3 still delivers *independently
   testable* value (a queryable `is:gamechanger` attribute; a benchmark-validated pure `score()`; a
   cached combo adapter), and the split maps to real risk boundaries (heavy re-import; calibration
   uncertainty; external API). Collapsing them would create a monolithic epic that can't be reviewed
   or de-risked incrementally. Documented rationale already sits in the epic list.

2. **Cross-epic seam: `ComboRecord` couples Epic 3 to Epic 2 (Story 2.6).** Epic 3's Stories 3.2/3.3
   consume the canonical `ComboRecord` **defined in Epic 2 Story 2.6**. This is a *backward*
   dependency (Epic 3 builds on Epic 2 — allowed), but it means Epic 3 is **not** completable from
   Epic 1 output alone. **Remediation for sprint planning:** sequence **2.6 before 3.2/3.3**. Not a
   defect, but an explicit ordering constraint the sprint plan must honor.

3. **Story 2.8 is the densest story** — it bundles the for-format aggregate (FR19), Standard fork
   (FR20), tier label (FR24), and confidence vocabulary (FR21). Cohesive (all "final classification /
   labeling"), but if a dev agent finds it heavy, it splits cleanly along confidence-vocab vs.
   aggregate/label lines. **Verdict: acceptable as-is; flagged for the implementer's judgment.**

### Best-Practices Compliance Checklist

| Check | Result |
| --- | --- |
| Epics deliver value (not pure technical milestones) | ✅ (see 🟡 #1 for the single-tool nuance) |
| Epic independence (no epic needs a *future* epic) | ✅ |
| Stories appropriately sized | ✅ (🟡 #3 densest = 2.8) |
| No forward (later-story) dependencies | ✅ |
| DB tables/entities created only when needed | ✅ |
| Clear, testable Given/When/Then ACs | ✅ |
| FR traceability maintained | ✅ (100%, all 24) |
| Brownfield integration points present | ✅ (`get_deck_with_cards`, `transform_scryfall_card`, `synergy.py`, `scryfall_api.py` backoff, sibling analysis tools) |
| Starter template (greenfield) | N/A — brownfield; Epic 1 Story 1 is real capability, not a scaffold ✅ |

### Remediation Summary

No blocking remediation required. One **actionable input for sprint planning**: honor the
`2.6 → 3.2/3.3` ordering (🟡 #2). The two other minor items are accept-with-awareness.

## Summary and Recommendations

### Overall Readiness Status

**✅ READY** — cleared for Phase 4 (Sprint Planning → implementation).

The deck-power-assessment planning set is coherent and traceable end-to-end: SPEC (canonical
contract) → PRD (FR1–24 / NFR1–8) → Architecture spine (AD-1…AD-12) → Epics (4 epics / 18 stories).
FR coverage is 100%, no UX gap (headless by design), and the epic/story structure passes the
quality bar with zero critical or major violations.

### Critical Issues Requiring Immediate Action

**None.** No blockers were found.

### Recommended Next Steps

1. **Proceed to `[SP] bmad-sprint-planning`** (fresh context window) to sequence the 18 stories.
   Feed it the scoped epics file `epics-deck-power-assessment.md` — **not** the default `epics.md`.
2. **Encode the one ordering constraint** in the sprint plan: Story **2.6 (`ComboRecord`) before
   3.2/3.3** — the combo cache/client consume the record shape the core defines.
3. **Front-load Story 2.1 (calibration benchmark composition)** — it is the scorer's acceptance gate
   and the resolver for two of the three PRD open questions; nothing in Epic 2 is "done" without it.
4. *(Optional, implementer's call)* Consider whether **Story 2.8** should be split (confidence-vocab
   vs. aggregate/label) once its dev agent scopes it.
5. **Sequence Epic 1's re-import deliberately** — the ~60k-card backfill (Story 1.2) is heavy; it
   gates real Game Changer data but the scorer degrades gracefully on NULL until it runs.

### Final Note

This assessment reviewed 5 documents across 6 validation dimensions and identified **0 critical, 0
major, and 3 minor (accept-with-awareness)** findings. There are **no blocking issues** — the
artifacts may proceed to implementation as-is. The three minor items are captured above as sprint-
planning inputs rather than rework.

---

**Assessed by:** BMad Implementation Readiness workflow · **Date:** 2026-07-11 · **Feature:** Deck
Power-Level Assessment
