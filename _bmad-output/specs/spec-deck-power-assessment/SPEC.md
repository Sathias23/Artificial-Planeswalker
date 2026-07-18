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
it can't answer *"how strong is this deck, and did my edit make it stronger?"* This adds an MCP
tool, `assess_deck_power`, that scores a saved deck, plus a thin `compare_deck_power` tool that
answers the comparison server-side — so the deck's owner sees what changed between two decks or two
versions of one deck without the calling agent doing arithmetic. *(Amended 2026-07-12 per
`sprint-change-proposal-2026-07-12.md`.)* The value is **relative comparison of the owner's own decks**; the scoring is
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

- **CAP-4** — Detect combos via a local Commander Spellbook snapshot
  - **intent:** Match the deck against a locally imported Spellbook bulk variant snapshot (no live
    call) and feed real two-card-infinite / loop combos into both the Commander Bracket floor and
    the `combo_potential` dimension, respecting commander requirements (CAP-8).
  - **success:** A deck containing a known `included` combo surfaces it in `flags.combos` and it
    sets/raises the Bracket floor per the WotC two-card-infinite trigger; a missing snapshot
    degrades (CAP-6) instead of fetching.

- **CAP-5** — Detect Game Changers
  - **intent:** Determine per-card Game Changer membership and the deck's count, feeding the Commander
    Bracket floor per the WotC decision tree.
  - **success:** A deck with N Game Changers lists them in `flags.game_changers` and floors the
    Bracket accordingly (e.g. 1–3 GC → Bracket 3); unpopulated (NULL) GC data does not silently floor
    the deck to Bracket 2.

- **CAP-6** — Stay honest under degradation
  - **intent:** Every score carries a categorical confidence (`low | medium | high`) plus named
    reasons; unresolved cards, a missing combo snapshot, unpopulated GC data, or an unidentifiable
    commander lower confidence rather than crashing or silently scoring zero.
  - **success:** Combo snapshot absent → `combo_data_unavailable` + degrade; unresolved cards →
    `cards_unresolved` + count; NULL `game_changer` → `game_changer_data_unavailable`; commander
    unknown → `commander_unidentified` — in every case a score still returns, with no crash and no
    silent zero. No clock-derived reason exists.

- **CAP-7** — Dual output
  - **intent:** Return both a human-readable formatted summary and the raw structured assessment, with
    a `flags` block surfacing the exact Game Changers, combos, structural gaps, hard triggers, and
    `cedh_candidate` that drove the result.
  - **success:** One `AssessDeckPowerResult` carries both a `summary` string and the structured
    `assessment` (including its `data_vintage`); `flags` name the specific cards/combos/gaps behind
    the score.

- **CAP-8** — Identify the commander(s)
  - **intent:** Resolve the deck's commander(s) from the per-card `commander` flag, falling back to
    sole-legendary inference, so Bracket rules and commander-required combo variants work from real
    data.
  - **success:** A flagged commander (or an unambiguous sole legendary) is used for matching; an
    ambiguous deck assesses without commander-required variants + `commander_unidentified`.

- **CAP-9** — Compare two decks server-side
  - **intent:** `compare_deck_power(deck_id_a, deck_id_b, format?)` assesses both decks through the
    same pipeline and returns the deltas, so comparison is never LLM arithmetic.
  - **success:** Per-dimension deltas, score delta, Bracket change, flags added/removed, and both
    `data_vintage` blocks; the deltas equal the subtraction of the two assess results.

## Constraints

- **Determinism is load-bearing (NFR1).** No randomness in v1; identical deck + card snapshot +
  combo snapshot → identical scores. This is what makes diffing trustworthy. Enforced at the output
  boundary by spine **AD-8** (sorted lists, integer scores, fixed shape, no call-time clock in the
  result; "as of" only via `data_vintage`).
- **Commander-first; Standard is deliberately shallower** — heuristic-only (curve / interaction /
  Karsten-60 / combos), with **no Bracket** and **no meta-tier percentile**. Standard's for-format
  score always ships with a descriptive tier label so no bare number is presented.
- **No live dependency at assessment time.** Combo data comes from the Commander Spellbook bulk
  export (keyless, MIT), imported locally by an operator-initiated script — the Scryfall-import /
  `card_vec` pattern. A missing snapshot degrades gracefully (mirrors `index_unavailable`); freshness
  couples to import cadence and is surfaced via `data_vintage`.
- **Game Changer data requires a data-layer change.** A **nullable** `game_changer` field on
  `CardModel` / `Card` + `transform_scryfall_card`, a hand-written migration (no Alembic), and a heavy
  Scryfall re-import to backfill. NULL = unknown and lowers confidence; readers never coalesce NULL to
  `False`. GC freshness couples to import cadence.
- **cEDH is flagged as candidacy only**, never auto-asserted from cards alone. Intent is unobservable;
  Brackets are officially "not an exact science," so auto-classification carries an irreducible error
  band reflected in mandatory confidence.
- **Architecture conformance.** The feature is bound by the adopted architecture spine
  **AD-1…AD-13** (AD-12 withdrawn 2026-07-12): async MCP tools (siblings to the analysis tools); a
  pure deterministic scorer + combo matcher in `src/logic` vs an impure I/O edge; assessment never
  writes to `cards.db`; framework-free `src/data` & `src/logic`; one canonical `ComboRecord`;
  explicit commander identity (AD-13); closed-enum confidence/flag vocabularies. Downstream stories
  cite these AD IDs, which are stable.
- **Power is an estimate, not a verdict.** Output never presents a bare number and never claims a deck
  is "better" — non-cEDH Commander is social-first; a higher score is a power estimate only.
- **v1 scoring is hand-tuned and benchmark-validated.** The per-dimension signal→0–100 mappings and
  aggregate weights are documented, adjustable, and validated against a **committed calibration
  benchmark** (WotC precons expected ~Bracket 2; known cEDH lists expected to flag as candidates;
  **≥3 Standard anchors** across the tier range) **plus monotonicity property tests** (a
  strictly-power-positive edit never moves the affected output the wrong way) — the properties
  constrain the numeric mid-range the categorical set cannot.

## Non-goals

- Monte Carlo goldfish simulation for win-turn distributions.
- ML / embedding-based scoring or nearest-archetype percentile.
- Limited / Draft assessment.
- A calibrated cross-format **absolute** score and per-format offset anchoring.
- 60-card **meta-tier** percentile scoring (MTGTop8 / MTGGoldfish — would require web scraping).
- EDHREC enrichment (inclusion %, synergy/lift, salt, community percentile).
- **Brawl / Historic Brawl** — the Bracket / Game Changers rubric does not map to 1v1 Arena Brawl;
  it is the natural next format profile, explicitly out of v1.
- The legacy community **1–10 scale** in the structured output (summary prose may reference it).

## Success signal

Brad assesses a Commander deck — the agent reports, say, Bracket 3, a for-format score of 68, a
dimension breakdown, and notes the two Game Changers and one late-game two-card combo that set the
floor. He snapshots the build (`create_deck` + `import_decklist` of its Arena export), swaps three
cards, and calls `compare_deck_power`: `combo_potential` up, `speed` up, `mana_efficiency` down —
the exact "did my edit make it stronger, and what changed?" question, answered. Acceptance is
anchored by the committed benchmark (precons ~Bracket 2, cEDH candidates flagged, Standard anchors
in their tier bands), the monotonicity properties, and byte-identical output for identical inputs.

## Open Questions

- **Dimension mappings + aggregate weights** — the actual signal→0–100 curves and weighting values
  (hand-tuned, documented, benchmark-validated). Owned by the first implementation/calibration pass;
  the architecture fixes *where* they live (`FormatProfile`, AD-3), not the numbers.
- **Benchmark composition** — the initial precon/cEDH set is composed (Story 2.1 done); the
  **Standard anchors** (which three+ decks) land with the validation story (2.9/5.9).
- **Combo earliest-turn heuristic** — the method and confidence for the derived
  `earliest_turn_estimate` (feeds `speed` and `combo_potential`). Owned by the implementation phase
  (spine AD-11 fixes that it is core-derived, not the method).
