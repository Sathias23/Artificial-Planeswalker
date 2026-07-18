---
title: 'Sprint Change Proposal — Deck Power Assessment plan corrections'
date: '2026-07-12'
status: approved
trigger: 'Adversarial design review of the deck-power-assessment planning set (2026-07-12)'
scope_classification: moderate
mode: incremental (all 8 proposals individually approved by Brad)
---

# Sprint Change Proposal — Deck Power Assessment (2026-07-12)

## 1. Issue Summary

A design review of the deck-power-assessment planning set (PRD 2026-07-11, architecture
spine, epics, SPEC) was run on 2026-07-12 — after global epic-4 (Game Changer data) shipped
and Story 5.1 (calibration benchmark) was done, but before Epics 5.2+, 6, and 7 were built.
The review surfaced 14 findings; the load-bearing ones:

1. **Commander identification is unaddressed** — the deck schema has no commander
   representation, yet the Bracket rules, combo matching, and (former) cache key all need it.
2. **The Spellbook bulk export was never evaluated** against the live-API + cache design; the
   live design carried a cards.db write path, a TTL/backoff ladder, a cache-key invariant, and
   two *clock-dependent* confidence tokens that latently violated the spine's own no-clock rule.
3. **Standard shipped unanchored** (one benchmark deck, no rubric) and the benchmark could not
   constrain the numeric mid-range where the headline diff use case lives.
4. **Output-shape gaps** undermined the diff use case: no data-vintage, absent-vs-false
   ambiguity, a consumed-by-nobody 1–10 scale, and the diff itself delegated to the LLM.
5. Narrative/hygiene: a "save a new version" workflow that doesn't exist, Brawl unmentioned,
   NFR7 self-correcting mid-text.

## 2. Impact Analysis

- **Epic 5 (scoring core, in progress):** completable with modifications. 5.2 loses the
  `game_changers_version` profile constant and `multiplayer_variance` token; 5.8's confidence
  vocabulary shrinks; 5.9 gains Standard anchors + monotonicity properties. Story 5.1's
  fixture is extended additively — no rollback.
- **Epic 6 (backlog):** redefined from "live combo detection" to **"Commander identity &
  local combo snapshot"** — all three stories replaced.
- **Epic 7 (backlog):** 7.2's ladder simplifies (no live fetch); 7.3 gains `data_vintage`,
  fixed flag shape, drops the 1–10; new Story 7.5 `compare_deck_power`.
- **Artifacts:** PRD, addendum, architecture spine, epics doc, SPEC CAP-4, sprint-status.yaml.
- **Technical:** one new additive migration (deck_cards.commander), one new import script
  (Spellbook bulk), one deleted invariant (AD-12). `assess_deck_power` becomes fully local
  and read-only against cards.db.

## 3. Recommended Approach

**Direct Adjustment** (effort: medium, risk: low). No completed work is rolled back; the MVP
is unchanged. The bulk-snapshot swap is lateral in effort for Epic 6 but deletes the feature's
only live dependency, its only cards.db write path, its cache-key machinery, and its two
clock-dependent confidence tokens — making NFR1 (determinism) unconditional.

## 4. Detailed Change Proposals (all approved 2026-07-12)

**P1 — PRD: combo detection goes local.** FG4 retitled "Combo detection (local Spellbook
snapshot)". FR13: match against a locally imported Spellbook bulk variant snapshot
(`included` = all pieces present + commander requirements satisfied; `almost_included` =
exactly one piece missing). FR14: documented operator-initiated import script (Scryfall/
card_vec pattern), records `imported_at` + export version; **no live network call during
assessment**. NFR4: all paths local/instant. NFR5: combo-snapshot freshness joins GC
freshness. §7: live-API risk replaced by bulk-export dependency (URL/format verified at
implementation).

**P2 — Architecture spine.** AD-5: combo snapshot table written only by the import script;
assess is read-only; missing table → `combo_data_unavailable` (card_vec precedent); metadata
row carries vintage. AD-9: per-call client → bulk downloader in `importers/`; matching is a
pure core function. AD-11: ComboRecord survives; bracket_tag normalized at import. **AD-12
deleted.** AD-6 enum: `cards_unresolved`, `combo_data_unavailable`,
`game_changer_data_unavailable`, `commander_unidentified`; `multiplayer_variance` becomes a
fixed Commander summary caveat; clock-dependent stale tokens removed.

**P3 — Epics: Epic 6 rewritten.** 6.1 commander flag end-to-end (`DeckCardModel.commander:
bool` default False, additive migration, `add_card_to_deck(commander=)`, Arena importer
Commander section sets it). 6.2 Spellbook bulk import script + tables + metadata. 6.3 pure
local combo matcher (commander-requirement- and multiplicity-aware, deterministic ordering).

**P4 — Commander identification.** New FR25 (FG1): read the `commander` flag; fall back to
sole-legendary-creature inference (no penalty); else assess without commander-required
variants + `commander_unidentified`. New AD-13 binds schema + inference + degradation.

**P5 — Benchmark funded + property-tested.** §6: ≥3 Standard anchors (competitive / coherent-
untuned / jank) and monotonicity properties (GC add never lowers Bracket floor; tutor add
never lowers consistency; interaction cut never raises interaction). Story 5.9 AC extended;
5.1 fixture extended additively inside 5.9.

**P6 — Output shape.** `assessment.data_vintage` (combo snapshot `imported_at` + version,
`format_profile_version`) sourced only from stored input metadata (AD-8 no-clock holds).
Commander-only fields always present (`bracket: null` + `false` booleans for Standard).
1–10 projection dropped (glossary, FR19, AD-8 Decimal rule).

**P7 — Narrative/hygiene.** §1.1/§3 describe the real versioning workflow (`create_deck` +
`import_decklist` + assess + optional delete). §2.1 adds Brawl/Historic Brawl as an explicit
non-goal (Bracket/GC rubric doesn't map to 1v1 Arena Brawl; natural next format profile).
NFR7 states the async rule cleanly.

**P8 — `compare_deck_power`.** New FR26 + Story 7.5: deterministic compare tool returning
per-dimension deltas, score delta, Bracket change, flags added/removed, both data_vintage
blocks. No persistence.

## 5. Implementation Handoff

- **Scope: Moderate** — backlog reorganization + planning-artifact updates; no code yet.
- **Executed by:** dev agent (this session) — apply edits to PRD, addendum, spine, epics doc,
  SPEC CAP-4, sprint-status.yaml; commit to `feat/deck-power-assessment`.
- **Success criteria:** all four planning docs internally consistent (FR/AD cross-references
  resolve); sprint-status story list matches the rewritten epics; Story 5.2 can start from
  the corrected FormatProfile contract without re-litigating any of the above.
- **Next dev work:** Story 5.2 (FormatProfile) under the amended AD-3/AD-6.
