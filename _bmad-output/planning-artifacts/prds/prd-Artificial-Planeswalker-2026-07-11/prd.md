---
title: Deck Power-Level Assessment — Artificial Planeswalker
status: final
created: 2026-07-11
updated: 2026-07-11
---

# Deck Power-Level Assessment — PRD

## 1. Overview

Artificial Planeswalker is an MCP-server toolkit for Magic: The Gathering deckbuilding
(local Scryfall snapshot, sqlite-vec/fastembed RAG, tools such as `analyze_mana_curve`,
`detect_synergies`, `validate_deck`). This PRD adds a new capability: **deck power-level
assessment** — an MCP tool, `assess_deck_power`, that scores a saved deck and returns
both a human-readable summary and a structured result, plus a thin `compare_deck_power`
diff tool (FR26) that answers the comparison question server-side.

The assessment is deterministic, explainable, and honest about uncertainty. It is
**Commander-first** (using WotC's official Commander Brackets rubric) with **Standard** as a
lighter second format. Source research: `docs/deck-assess.md`.

### 1.1 Primary use case

The headline is **relative comparison of the owner's own decks** — comparing two decks, or two
versions of the same deck, to answer *"did my edit make this stronger, and what changed?"*
Because the comparison is between the user's own decks, a **consistent, stable for-format score
plus a per-dimension breakdown** is the real payload; the paper's calibrated cross-format
"absolute" score is out of scope for v1. Comparison runs server-side via the thin
`compare_deck_power` tool (FR26), which assesses both decks through the same deterministic
pipeline and returns the deltas — the arithmetic is never delegated to the calling agent.
Comparing two *versions* of one deck uses the supported duplication workflow: snapshot the
current build with `create_deck` + `import_decklist` (its Arena export), edit, then compare
the two deck ids.

### 1.2 Vision

> A new MCP capability that scores a saved deck's power level and lets me compare two of my
> decks — or two versions of one deck — and see what changed and whether it got stronger.
> Deterministic, explainable, and honest about what it doesn't know.

## 2. Goals

1. **Assess** — score any saved deck: a Commander Bracket (1–5), a for-format 0–100 score, and a
   7-dimension breakdown (speed, consistency, resilience, interaction, mana efficiency, card
   advantage, combo potential).
2. **Compare / diff** — enable side-by-side comparison of two decks or two versions of one deck:
   stable, diffable structured output plus a server-side `compare_deck_power` tool (FR26) that
   returns the deltas directly. *Headline goal.*
3. **Detect combos** — real two-card infinite/loop detection via a locally imported Commander
   Spellbook snapshot, feeding both the Bracket floor and the combo-potential dimension.
4. **Stay honest** — every score carries a confidence level and reasons; degradation lowers
   confidence rather than crashing or silently scoring zero. No score ships without context.

### 2.1 Non-goals (v1)

Explicitly excluded, deferred to the roadmap (§8):

- Monte Carlo goldfish simulation.
- ML / embedding-based scoring.
- Limited / Draft assessment.
- **Brawl / Historic Brawl** — the Bracket / Game Changers rubric does not map to 1v1 Arena
  Brawl (different life totals, pool, and social contract); it is the natural *next* format
  profile once the Commander/Standard fork is proven, but is explicitly out of v1.
- Calibrated cross-format **absolute** score and per-format offset anchoring.
- 60-card **meta-tier** scoring via MTGTop8 / MTGGoldfish (would require web scraping).
- EDHREC enrichment (inclusion %, synergy/lift, salt, community percentile).

## 3. How it's used (single-operator narrative)

The operator is the deck's owner, working through an AI agent that calls the MCP tool. There is no
separate UI and no standalone persona section.

> Brad tunes a Commander deck. He asks the agent to assess the current build; the agent calls
> `assess_deck_power(deck_id)` and reports Bracket 3, a for-format score of 68, and a dimension
> breakdown, noting the two Game Changers and one late-game two-card combo that set the floor.
> Before editing, he snapshots the build: the agent creates a scratch deck with `create_deck` and
> `import_decklist` (the current build's Arena export). Brad swaps three cards in the original,
> then asks what changed. The agent calls `compare_deck_power(old_id, new_id)`: combo-potential
> up 12, speed up 6, mana efficiency down 3. Brad now knows the edit made the deck faster and
> more explosive at a small mana cost — the exact question he had — and deletes the scratch copy.

## 4. Functional Requirements

FRs are grouped by pipeline stage (feature group) with globally stable IDs.

**Score-scale glossary** (the coexisting scales, named once to prevent conflation):

- **Bracket (1–5)** — Commander only; the WotC categorical tier (Exhibition → cEDH).
- **For-format score (0–100)** — the weighted-aggregate power score, interpreted *within* its
  format; the basis for deck-to-deck diffs.
- **Descriptive label** (FR24) — the human-facing tier word attached to every for-format score.

*(The legacy community 1–10 scale is deliberately not emitted — a third numeric scale invites
exactly the conflation this glossary exists to prevent; the `summary` may reference it in prose
if useful.)*

### FG1 — Ingest & format resolve
- **FR1** — Expose `assess_deck_power(deck_id, format?)`. Load the deck via
  `DeckRepository.get_deck_with_cards` (full `Card` rows, including `legalities`, `keywords`,
  `oracle_text`) — **not** the trimmed `CardSummary` path. `format` accepts `commander | standard`.
- **FR2** — If `format` is omitted, infer it from the deck's stored format / card `legalities`. An
  unsupported or unrecognized format returns a graceful error result (not a crash), naming the
  supported formats.
- **FR3** — Resolve every card against the local Scryfall snapshot; count unresolved or ambiguous
  cards and carry that count into confidence (FR21).
- **FR4** — Load a **versioned format profile** (rubric selector, expected-win-turn band, Bracket
  rules version). Emit `format_profile_version` in the output. (Game Changer data vintage comes
  from the card snapshot itself, not a profile constant — see FR22 `data_vintage`.)
- **FR25** — Determine the deck's **commander(s)**: read the per-card `commander` flag on deck
  cards (a new nullable-default-`False` field set by the Arena importer's `Commander` section and
  by `add_card_to_deck`). When no card is flagged in a Commander-format deck, infer a **sole
  legendary creature** (no confidence penalty). When zero or multiple candidates remain, assess
  without commander-required combo variants and add confidence reason `commander_unidentified`.

### FG2 — Heuristic extraction (deterministic, local)
- **FR5** — Compute mana curve and average mana value (from `cmc`); land count.
- **FR6** — Count ramp, card-draw/advantage, removal/interaction, and tutors via `oracle_text` +
  `type_line` classification.
- **FR7** — Interaction detail: instant-speed ratio and interaction-CMC distribution.
- **FR8** — Mana-base quality: Karsten land-count delta (Commander and 60-card formulas) →
  mana-flood / mana-screw flag, **and** colored-source / pip consistency (Karsten pip math — the
  single biggest hidden mana lever), feeding the mana-efficiency dimension.
- **FR9** — Rule-of-8 / functional-redundancy signal (Commander) and 8×8 structural-coverage gaps
  (e.g. "ramp below baseline").
- **FR10** — Win-condition tagging (combo pieces, "you win the game" text, evasive/haymaker finishers).

### FG3 — Card-power signals
- **FR11** — Determine **Game Changer** membership per card and the deck's Game Changer count.
  Source: a new `game_changer` boolean added to the Scryfall import (`transform_scryfall_card`) and
  to `CardModel` / `Card` schema, populated from the Scryfall bulk `game_changer` field; requires a
  backfill migration / re-import (see addendum). Assessment reads the field locally.
- **FR12** — Detect hard Bracket triggers via oracle-text patterns: **mass land denial** and
  **extra-turn chains**.

### FG4 — Combo detection (local Spellbook snapshot)
- **FR13** — Match the deck against a **locally imported Commander Spellbook bulk variant
  snapshot**; bucket matches into `included` (all pieces present and commander requirements
  satisfied, per FR25) vs `almost_included` (exactly one piece missing); capture per-combo
  `bracket_tag`, produced results, and popularity. An earliest-turn estimate is derived in the
  scorer.
- **FR14** — Import the Spellbook bulk export into a dedicated local table via a **documented,
  operator-initiated script** (the same operational pattern as the Scryfall import and the
  `card_vec` index build); record the snapshot's `imported_at` and export version. **Assessment
  performs no live network call.** A missing/empty snapshot degrades gracefully (NFR3).
- **FR15** — Map combos to the two-card-infinite Bracket trigger and the combo-potential dimension.

### FG5 — Score & classify
- **FR16** — Compute the **7-dimension vector** (speed, consistency, resilience, interaction, mana
  efficiency, card advantage, combo potential), each 0–100. Because Monte Carlo simulation is a v1
  cut, **`speed` is estimated deterministically** from curve + ramp density + combo earliest-turn
  heuristics, not from goldfish simulation. The signal→0–100 mapping for each dimension is an
  architecture deliverable (see NFR8).
- **FR17** — Consistency computed analytically via **hypergeometric** key-piece and mana access by
  turn N (deterministic; no simulation).
- **FR18** — **Commander:** set the **Bracket floor** (1–5) from Game Changer count + hard triggers
  + combos per the WotC decision tree. Flag cEDH **candidacy** only; never assert Bracket 5.
- **FR19** — Weighted-aggregate the vector into a **for-format 0–100** score. No absolute
  cross-format score in v1, and no 1–10 projection in the structured output (see glossary note).
- **FR20** — **Standard:** heuristic-only for-format score (curve / interaction / Karsten-60 /
  combos). No Bracket, no meta-tier percentile. To avoid shipping a bare number, Standard's score is
  always accompanied by the descriptive label (FR24).

### FG6 — Confidence & output
- **FR21** — Emit a **categorical** confidence level (`low | medium | high`) with a `reasons[]`
  list, derived from run-specific degradations only: card-resolution completeness, combo-snapshot
  availability, Game Changer data availability, and commander identification (FR25). Commander's
  irreducible multiplayer variance is a **fixed caveat in the `summary`**, not a confidence
  reason — a penalty every Commander run carries discriminates nothing. **No numeric low/high
  band in v1** — a numeric confidence interval implies calibrated precision the deterministic v1
  does not have. Degradation lowers confidence; it never crashes or silently scores zero.
- **FR22** — Return **both** a human-readable formatted **summary** and the **raw structured JSON**
  (the `docs/deck-assess.md` schema, minus the absolute-score, per-score numeric `low`/`high` band,
  percentile, and EDHREC fields), including a **`data_vintage` block** (combo snapshot
  `imported_at` + export version, `format_profile_version`) sourced only from stored input
  metadata — so a caller diffing two runs can detect that they used different data.
- **FR23** — A `flags` block surfaces the exact cards/combos/gaps that drove the result: Game
  Changers list, combos, structural gaps, mass-land-denial / extra-turn booleans, `cedh_candidate`.
- **FR24** — Every for-format score carries a **descriptive tier label** (e.g. Unfocused / Focused /
  Tuned / High-Power / Competitive) so no score — Commander or Standard — is presented as a bare
  number. For Commander this sits alongside the Bracket; for Standard it is the primary human-facing
  tier.
- **FR26** — Expose `compare_deck_power(deck_id_a, deck_id_b, format?)`: assess both decks through
  the same deterministic pipeline and return per-dimension deltas, the for-format score delta,
  Bracket change (Commander), flags added/removed, and **both** `data_vintage` blocks. Stateless,
  no persistence; the comparison arithmetic is never delegated to the calling agent.

## 5. Non-Functional Requirements

- **NFR1 — Determinism.** Identical deck + snapshot + cached combo data → identical scores. No
  randomness in v1. This is what makes the diff use case trustworthy.
- **NFR2 — Explainability.** Every score traces to the cards/signals that produced it (via
  `flags`); no black-box numbers.
- **NFR3 — Graceful degradation.** Unresolved cards, a missing/empty combo snapshot, or NULL Game
  Changer data → lower confidence + reason flag, never a crash or silent zero. Mirrors the
  existing `index_unavailable` / `card_vec` pattern (a build prerequisite that may be absent).
- **NFR4 — Latency.** The assessment path is **fully local** — heuristics, hypergeometric math,
  and combo matching against the local snapshot are effectively instant. The only slow step is
  the operator-initiated Spellbook snapshot import, which is not on the assessment path.
- **NFR5 — Data freshness / versioning.** The Game Changers data, combo snapshot, and Bracket
  rules change over time; the format profile is versioned, the combo snapshot records its
  `imported_at` + export version, and the output's `data_vintage` states what produced it.
  Freshness couples to import cadence (as `game_changer` already does).
- **NFR6 — Testability / calibration.** A committed benchmark set anchors correctness (see §6).
- **NFR7 — Architecture conformance.** Both tools are stateless **async `def`**, registered
  alongside the existing deck-analysis tools (`analyze_mana_curve` / `detect_synergies` /
  `validate_deck`), which `await` the async `src/data` repositories on the FastMCP event loop
  (architecture spine **AD-1**). `format` / `deck_id` are caller-supplied parameters (no
  per-session server state); `src/data` and `src/logic` stay framework-free. Follows the
  project's MCP conventions.
- **NFR8 — Scoring transparency (architecture deliverable).** The per-dimension signal→0–100
  mappings and the aggregate weighting are defined during the architecture phase, not this PRD. They
  MUST be documented, hand-tuned, adjustable, and validated against the calibration benchmark (§6).
  Fixed (non-random) mappings and weights are what make NFR1 (determinism) hold across builds.

## 6. Success Metrics & Counter-Metrics

**Success metrics**
1. **Calibration benchmark passes** — **composing the benchmark set is the first implementation
   task**: a handful of WotC precons expected ~Bracket 2, known cEDH lists expected to flag as
   candidates / score high, **and ≥3 Standard anchors** (a current competitive archetype expected
   high tier, a coherent-but-untuned deck expected mid, a jank pile expected low) so FR20's tier
   labels have an acceptance signal. Once composed, that set is the acceptance signal for the
   scorer. Framed this way so "done" is decidable rather than blocked on an open question.
2. **Diff sensitivity** — a meaningful edit (adding a Game Changer or a combo piece) produces a
   visible, correctly-directioned score/dimension delta.
3. **Determinism** — identical inputs → identical output (regression-tested).
4. **Monotonicity (property-tested)** — a strictly-power-positive edit never moves the affected
   output the wrong way: adding a Game Changer never lowers the Bracket floor; adding a tutor
   never lowers consistency; cutting all interaction never raises the interaction dimension.
   These properties constrain the numeric mid-range — where the diff use case actually operates —
   which the small categorical benchmark cannot.

**Counter-metrics**
- **No over-rating "goodstuff piles"** — high average card quality without cohesion must not score
  top-tier; synergy / 8×8 / combo dimensions pull it down.
- **No false precision** — no score ships without its confidence + reasons.

## 7. Dependencies & Risks

- **Game Changers data (FR11)** is not currently imported; adding the `game_changer` field requires
  a schema change + backfill migration and re-import (~60k cards, heavy). GC freshness couples to
  import cadence.
- **Commander Spellbook bulk export (FR13/FR14)** is the combo data source — imported locally like
  the Scryfall snapshot, so **no live dependency exists at assessment time**. The export is
  MIT-licensed and keyless; its exact URL/format is verified at implementation (Epic 6). Combo
  freshness couples to import cadence (mitigated by `data_vintage` in the output); a missing
  snapshot degrades gracefully (NFR3).
- **Commander identification (FR25)** depends on the new per-card `commander` flag; pre-existing
  decks rely on the sole-legendary inference, and ambiguous decks assess without
  commander-required combo variants (confidence reason `commander_unidentified`).
- **Intent is not observable** — Brackets are officially "not an exact science"; auto-classification
  has an irreducible error band, reflected in mandatory confidence (FR21) and "bracket up when in
  doubt."
- **cEDH cannot be auto-asserted** from cards alone — only flagged as a candidate (FR18).
- **Standard has no official power rubric** and no local meta corpus; its score is deliberately
  heuristic-only and shallower than Commander's (FR20).
- **Power ≠ "better."** A higher Bracket or score is a *power estimate*, not a verdict that a deck is
  better — non-cEDH Commander is explicitly social-first. The output frames scores as estimates, not
  judgments.
- **Heuristic mis-rating of cohesive-but-unusual decks** — commander-centric, tribal, and pure-aggro
  decks are known to fool count-based heuristics (the "pile of good cards" inverse). The synergy /
  8×8 / combo dimensions partially counter this; it remains a residual error source reflected in
  confidence.

## 8. Staging / Roadmap

**v1 (this PRD)** — the full heuristic-plus-combo pipeline (FG1–FG6), both Commander and Standard,
dual output, committed calibration benchmark.

**Deferred (future)** — EDHREC percentile enrichment; Monte Carlo goldfish for win-turn
distributions; ML / embeddings for synergy clustering and nearest-archetype percentile; Limited /
Draft assessment (17Lands); calibrated cross-format absolute score; 60-card meta-tier scoring.

## 9. Open Questions

All three are **owned by the architecture / first-implementation phase**, not blockers for this PRD:

- **Dimension mappings + aggregate weights** — signal→0–100 per dimension and the weighting. Owner:
  architecture phase (NFR8); hand-tuned, documented, benchmark-validated.
- **Benchmark composition** — which precons and cEDH lists. Owner: first implementation task (§6);
  the set becomes the acceptance signal once composed.
- **Combo earliest-turn heuristic** (FR16/combo speed) — method and confidence. Owner: architecture
  phase.
