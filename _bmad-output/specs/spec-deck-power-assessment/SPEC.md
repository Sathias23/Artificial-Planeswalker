---
id: SPEC-deck-power-assessment
companions:
  - ../../planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md
  - ../../../docs/deck-assess.md
  - ../../project-context.md
sources:
  - ../../planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-11/prd.md
  - ../../planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-11/addendum.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Deck Power-Level Assessment

## Why

An **opportunity and a vision**: Artificial Planeswalker already gives an agent expert MTG
deckbuilding tools (curve, synergy, legality, semantic search) over a local Scryfall snapshot, but
it can't answer *"how strong is this deck, and did my edit make it stronger?"* This adds one MCP
tool, `assess_deck_power`, that scores a saved deck and — because comparison runs caller-side (assess
twice, diff the results) — lets the deck's owner see what changed between two decks or two versions
of one deck. The value is **relative comparison of the owner's own decks**; the scoring is
**deterministic, explainable, and honest about what it doesn't know**. It is Commander-first, built
on WotC's official Commander Brackets rubric, with Standard as a lighter second format. The affected
user is the single operator (the deck's owner) working through an AI agent.

## Capabilities

- **CAP-1** — Assess a saved deck
  - **intent:** A caller runs `assess_deck_power(deck_id, format?)` to get a power read: a Commander
    Bracket (1–5), a for-format 0–100 score, a descriptive tier label, and a 7-dimension vector
    (`speed, consistency, resilience, interaction, mana_efficiency, card_advantage, combo_potential`).
  - **success:** A Commander deck returns a Bracket + all seven dimensions + a tier label; a Standard
    deck returns a heuristic for-format score + all seven dimensions + a tier label (no Bracket).

- **CAP-2** — Resolve format gracefully
  - **intent:** Infer the format from the deck when `format` is omitted, and reject an unsupported
    format without crashing.
  - **success:** An omitted format is inferred (`commander | standard`); an unsupported or
    unrecognized format returns a graceful error result naming the supported formats, never an
    exception.

- **CAP-3** — Deterministic, diffable output
  - **intent:** Identical deck + Scryfall snapshot + cached combo data always produce identical
    structured output, so a caller can diff two runs; a meaningful edit produces a
    correctly-directioned dimension delta.
  - **success:** A regression test shows byte-identical JSON for identical inputs, and adding a Game
    Changer or a combo piece moves the expected dimension in the expected direction.

- **CAP-4** — Detect combos via Commander Spellbook
  - **intent:** Find real two-card-infinite / loop combos in the deck and feed them into both the
    Commander Bracket floor and the `combo_potential` dimension.
  - **success:** A deck containing a known `included` combo surfaces it in `flags.combos` and it
    sets/raises the Bracket floor per the WotC two-card-infinite trigger.

- **CAP-5** — Detect Game Changers
  - **intent:** Determine per-card Game Changer membership and the deck's count, feeding the Commander
    Bracket floor per the WotC decision tree.
  - **success:** A deck with N Game Changers lists them in `flags.game_changers` and floors the
    Bracket accordingly (e.g. 1–3 GC → Bracket 3); unpopulated (NULL) GC data does not silently floor
    the deck to Bracket 2.

- **CAP-6** — Stay honest under degradation
  - **intent:** Every score carries a categorical confidence (`low | medium | high`) plus named
    reasons; unresolved cards, an unreachable Spellbook, or unpopulated GC data lower confidence
    rather than crashing or silently scoring zero.
  - **success:** Spellbook unreachable → `combo_data_unavailable`/`combo_data_stale` reason + degrade;
    unresolved cards → `cards_unresolved` + count; NULL `game_changer` → `game_changer_data_unavailable`
    — in every case a score still returns, with no crash and no silent zero.

- **CAP-7** — Dual output
  - **intent:** Return both a human-readable formatted summary and the raw structured assessment, with
    a `flags` block surfacing the exact Game Changers, combos, structural gaps, hard triggers, and
    `cedh_candidate` that drove the result.
  - **success:** One `AssessDeckPowerResult` carries both a `summary` string and the structured
    `assessment`; `flags` name the specific cards/combos/gaps behind the score.

## Constraints

- **Determinism is load-bearing (NFR1).** No randomness in v1; identical deck + snapshot + cached
  combo data → identical scores. This is what makes caller-side diffing trustworthy. Enforced at the
  output boundary by spine **AD-8** (sorted lists, integer scores, no call-time clock in the result).
- **Commander-first; Standard is deliberately shallower** — heuristic-only (curve / interaction /
  Karsten-60 / combos), with **no Bracket** and **no meta-tier percentile**. Standard's for-format
  score always ships with a descriptive tier label so no bare number is presented.
- **One live external dependency.** Commander Spellbook `find-my-combos` (keyless, MIT) is the only
  non-local call; it must be cached ≥24h with polite throttling + 429 backoff and degrade gracefully
  (mirrors the existing `index_unavailable` pattern).
- **Game Changer data requires a data-layer change.** A **nullable** `game_changer` field on
  `CardModel` / `Card` + `transform_scryfall_card`, a hand-written migration (no Alembic), and a heavy
  Scryfall re-import to backfill. NULL = unknown and lowers confidence; readers never coalesce NULL to
  `False`. GC freshness couples to import cadence.
- **cEDH is flagged as candidacy only**, never auto-asserted from cards alone. Intent is unobservable;
  Brackets are officially "not an exact science," so auto-classification carries an irreducible error
  band reflected in mandatory confidence.
- **Architecture conformance.** The feature is bound by the adopted architecture spine **AD-1…AD-12**:
  an async MCP tool (sibling to the analysis tools); a pure deterministic scorer in `src/logic` vs an
  impure I/O edge; framework-free `src/data` & `src/logic`; one canonical `ComboRecord` + one
  canonical multiplicity-aware cache key; closed-enum confidence/flag vocabularies. Downstream stories
  cite these AD IDs, which are stable.
- **Power is an estimate, not a verdict.** Output never presents a bare number and never claims a deck
  is "better" — non-cEDH Commander is social-first; a higher score is a power estimate only.
- **v1 scoring is hand-tuned and benchmark-validated.** The per-dimension signal→0–100 mappings and
  aggregate weights are documented, adjustable, and validated against a **committed calibration
  benchmark**; composing that benchmark set (WotC precons expected ~Bracket 2; known cEDH lists
  expected to flag as candidates) is the **first implementation task** and is the scorer's acceptance
  signal.

## Non-goals

- Monte Carlo goldfish simulation for win-turn distributions.
- ML / embedding-based scoring or nearest-archetype percentile.
- Limited / Draft assessment.
- A calibrated cross-format **absolute** score and per-format offset anchoring.
- 60-card **meta-tier** percentile scoring (MTGTop8 / MTGGoldfish — would require web scraping).
- EDHREC enrichment (inclusion %, synergy/lift, salt, community percentile).
- A dedicated `compare_decks` tool — comparison is caller-side (run `assess_deck_power` twice, diff
  the two structured results).

## Success signal

Brad assesses a Commander deck — the agent reports, say, Bracket 3, a for-format score of 68, a
dimension breakdown, and notes the two Game Changers and one late-game two-card combo that set the
floor. He swaps three cards, saves a new version, re-assesses, and diffs the two structured results:
`combo_potential` up, `speed` up, `mana_efficiency` down — the exact "did my edit make it stronger,
and what changed?" question, answered. Acceptance is anchored by the committed benchmark: WotC precons
land ~Bracket 2, known cEDH lists flag as candidates, and identical inputs produce identical output.

## Open Questions

- **Dimension mappings + aggregate weights** — the actual signal→0–100 curves and weighting values
  (hand-tuned, documented, benchmark-validated). Owned by the first implementation/calibration pass;
  the architecture fixes *where* they live (`FormatProfile`, AD-3), not the numbers.
- **Benchmark composition** — which precons and cEDH lists make up the calibration set. The first
  implementation task; becomes the scorer's acceptance signal once composed.
- **Combo earliest-turn heuristic** — the method and confidence for the derived
  `earliest_turn_estimate` (feeds `speed` and `combo_potential`). Owned by the implementation phase
  (spine AD-11 fixes that it is core-derived, not the method).
