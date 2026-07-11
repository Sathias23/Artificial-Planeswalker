---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/specs/spec-deck-power-assessment/SPEC.md
  - _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md
  - docs/deck-assess.md
  - _bmad-output/project-context.md
  - _bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-11/prd.md
  - _bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-11/addendum.md
project_name: 'Artificial-Planeswalker — Deck Power-Level Assessment'
user_name: 'Brad'
date: '2026-07-11'
scope: 'assess_deck_power MCP capability (PRD 2026-07-11, FG1–FG6)'
status: 'complete'
---

# Artificial-Planeswalker — Deck Power-Level Assessment — Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the **Deck Power-Level
Assessment** feature — a single new MCP tool, `assess_deck_power`, that scores a saved deck and
returns both a human-readable summary and a deterministic, diffable structured result. It is
**Commander-first** (WotC Commander Brackets) with **Standard** as a lighter heuristic-only format.

Requirements are decomposed from the canonical contract (`SPEC.md` + companions) and traced to the
PRD's stable `FR*`/`NFR*` IDs. The architecture spine's invariants (`AD-1…AD-12`) are the binding
"how"; downstream stories cite these AD IDs, which are stable.

> **Project type:** Brownfield addition to an existing Python modular monolith
> (`data → logic → mcp_server → ui`). **No starter template, no UI.** This is a headless MCP
> capability; there is no UX design contract and therefore no UX-DR section.
>
> **Superseded inputs (excluded):** `planning-artifacts/architecture.md` and the old
> `planning-artifacts/prd.md` (Letta/PydanticAI framing) — both carry SUPERSEDED banners and are
> unrelated to this feature.
>
> **Existing `epics.md` (Phase-1 MCP pivot) is deliberately untouched** — this feature lives in
> its own `epics-deck-power-assessment.md`.

## Requirements Inventory

### Functional Requirements

**Score-scale glossary** (three coexisting scales, named once to prevent conflation): **Bracket
(1–5)** Commander-only WotC tier · **For-format score (0–100)** weighted aggregate, the diff basis
· **1–10 projection** derived rescale · **Descriptive label** (FR24) the human tier word on every
score.

**FG1 — Ingest & format resolve**
- **FR1** — Expose `assess_deck_power(deck_id, format?)`. Load the deck via
  `DeckRepository.get_deck_with_cards` (full `Card` rows incl. `legalities`, `keywords`,
  `oracle_text`) — not the trimmed `CardSummary` path. `format` accepts `commander | standard`.
- **FR2** — If `format` is omitted, infer it from the deck's stored format / card `legalities`. An
  unsupported/unrecognized format returns a graceful error result (not a crash), naming supported
  formats.
- **FR3** — Resolve every card against the local Scryfall snapshot; count unresolved/ambiguous
  cards and carry that count into confidence (FR21).
- **FR4** — Load a **versioned format profile** (rubric selector, expected-win-turn band, Bracket
  rules version, Game Changers list version). Emit `format_profile_version` in the output.

**FG2 — Heuristic extraction (deterministic, local)**
- **FR5** — Compute mana curve and average mana value (from `cmc`); land count.
- **FR6** — Count ramp, card-draw/advantage, removal/interaction, and tutors via `oracle_text` +
  `type_line` classification.
- **FR7** — Interaction detail: instant-speed ratio and interaction-CMC distribution.
- **FR8** — Mana-base quality: Karsten land-count delta (Commander and 60-card formulas) →
  mana-flood / mana-screw flag, **and** colored-source / pip consistency (Karsten pip math),
  feeding the mana-efficiency dimension.
- **FR9** — Rule-of-8 / functional-redundancy signal (Commander) and 8×8 structural-coverage gaps
  (e.g. "ramp below baseline").
- **FR10** — Win-condition tagging (combo pieces, "you win the game" text, evasive/haymaker
  finishers).

**FG3 — Card-power signals**
- **FR11** — Determine **Game Changer** membership per card and the deck's Game Changer count.
  Source: a new `game_changer` field added to the Scryfall import (`transform_scryfall_card`) and to
  `CardModel` / `Card` schema, populated from the Scryfall bulk `game_changer` field; requires a
  backfill migration / re-import. Assessment reads the field locally.
- **FR12** — Detect hard Bracket triggers via oracle-text patterns: **mass land denial** and
  **extra-turn chains**.

**FG4 — Combo detection (single live dependency)**
- **FR13** — Call Commander Spellbook `find-my-combos`; bucket results into `included` vs
  `almostIncluded`; capture per-combo `bracket_tag`, produced result, popularity, and an
  earliest-turn estimate.
- **FR14** — Cache Spellbook responses (≥24h) with polite throttling and 429 backoff.
- **FR15** — Map combos to the two-card-infinite Bracket trigger and the combo-potential dimension.

**FG5 — Score & classify**
- **FR16** — Compute the **7-dimension vector** (speed, consistency, resilience, interaction,
  mana_efficiency, card_advantage, combo_potential), each 0–100. `speed` is estimated
  deterministically from curve + ramp density + combo earliest-turn heuristics (no goldfish
  simulation). The signal→0–100 mapping per dimension is an architecture deliverable (NFR8).
- **FR17** — Consistency computed analytically via **hypergeometric** key-piece and mana access by
  turn N (deterministic; no simulation).
- **FR18** — **Commander:** set the **Bracket floor** (1–5) from Game Changer count + hard triggers
  + combos per the WotC decision tree. Flag cEDH **candidacy** only; never assert Bracket 5.
- **FR19** — Weighted-aggregate the vector into a **for-format 0–100** score; derive the familiar
  **1–10** as a secondary projection. No absolute cross-format score in v1.
- **FR20** — **Standard:** heuristic-only for-format score (curve / interaction / Karsten-60 /
  combos). No Bracket, no meta-tier percentile. Always accompanied by the descriptive label (FR24).

**FG6 — Confidence & output**
- **FR21** — Emit a **categorical** confidence level (`low | medium | high`) with a `reasons[]`
  list, derived from card-resolution completeness, combo-data availability, multiplayer variance
  (Commander lowers confidence), and format-profile freshness. **No numeric band in v1.**
  Degradation lowers confidence; never crashes or silently scores zero.
- **FR22** — Return **both** a human-readable formatted **summary** and the **raw structured JSON**
  (the `docs/deck-assess.md` schema, minus absolute-score, per-score numeric `low`/`high` band,
  percentile, and EDHREC fields).
- **FR23** — A `flags` block surfaces the exact cards/combos/gaps that drove the result: Game
  Changers list, combos, structural gaps, mass-land-denial / extra-turn booleans, `cedh_candidate`.
- **FR24** — Every for-format score carries a **descriptive tier label** (e.g. Unfocused / Focused /
  Tuned / High-Power / Competitive) so no score is presented as a bare number. Commander: alongside
  the Bracket; Standard: the primary human-facing tier.

### NonFunctional Requirements

- **NFR1 — Determinism.** Identical deck + snapshot + cached combo data → identical scores. No
  randomness in v1. Makes the diff use case trustworthy.
- **NFR2 — Explainability.** Every score traces to the cards/signals that produced it (via
  `flags`); no black-box numbers.
- **NFR3 — Graceful degradation.** Unresolved cards, unreachable Spellbook, or empty combo DB →
  lower confidence + reason flag, never a crash or silent zero. Mirrors `index_unavailable`.
- **NFR4 — Latency.** Local heuristics + hypergeometric are effectively instant. The single live
  call (Spellbook) is cached (≥24h) with 429 backoff; warm-cache assessment feels interactive; a
  cold combo fetch is the only slow path.
- **NFR5 — Data freshness / versioning.** Game Changers list and Bracket rules change over time; the
  format profile is versioned and the output states which profile/rules version produced it.
- **NFR6 — Testability / calibration.** A committed benchmark set anchors correctness (Success
  Metric 1). Composing the benchmark set is the first implementation task and the scorer's
  acceptance signal.
- **NFR7 — Architecture conformance.** Tool is stateless and registered alongside the existing
  deck-analysis tools; `format` / `deck_id` are caller-supplied (no per-session state); `src/data`
  and `src/logic` stay framework-free. **Async `def`** per architecture spine AD-1 (this overrides
  the PRD's earlier "sync `def` / threadpool" framing — see AD-1).
- **NFR8 — Scoring transparency (architecture deliverable).** The per-dimension signal→0–100
  mappings and the aggregate weighting MUST be documented, hand-tuned, adjustable, and validated
  against the calibration benchmark. Fixed (non-random) mappings/weights are what make NFR1 hold.

### Additional Requirements

Binding technical requirements from the **Architecture Spine (AD-1…AD-12)** and the addendum's
technical-how notes. These are the "how" that downstream stories cite by AD ID.

- **AD-1 — Async MCP tool.** Register `assess_deck_power` as an `async def` tool in
  `src/mcp_server/server.py`, sibling to `analyze_mana_curve` / `detect_synergies` / `validate_deck`;
  `await` `get_deck_with_cards` and use async httpx for Spellbook on the FastMCP event loop.
- **AD-2 — Pure core / impure edge.** All scoring lives in `src/logic/assessment/` as pure functions
  `score(cards, combos, profile) -> assessment` — **no network, DB, or clock**. The edge fetches +
  caches combos and passes them into the core as **frozen plain values** (cache hit == cache miss).
- **AD-3 — FormatProfile is passive frozen data.** Per-dimension mappings, aggregate weights,
  expected-win-turn band, rubric selector (`brackets | heuristic_only`), and flags live as typed
  frozen constants in an in-repo Python `FormatProfile` module — one profile per format. The single
  scorer reads and branches on it. Adjusting weights = edit module + bump version + re-run benchmark.
- **AD-4 — `game_changer` is nullable; NULL = "unknown."** Add `game_changer: bool | None` to
  `CardModel` + `Card` schema via a hand-written additive migration in `scripts/` (no Alembic),
  populated in `transform_scryfall_card` from the Scryfall bulk field; backfill needs a re-import.
  If ANY deck card is NULL → confidence reason `game_changer_data_unavailable` and the absent count
  MUST NOT lower the Commander Bracket floor. **Never coalesce `None` to `False`.**
- **AD-5 — Combo cache = ephemeral table in `cards.db`.** Reached via a repository in
  `src/data/repositories` returning Pydantic (never ORM). Key = the AD-12 cache key; row carries
  `fetched_at` (24h TTL) + a list of canonical `ComboRecord`s under a versioned cache-row schema.
  Only the `included` + `almostIncluded` buckets feed the core. `assess_deck_power` is the sole
  writer (single upsert-by-hash under WAL); the **migration must ensure `PRAGMA journal_mode=WAL`**
  (write path must not depend on the search index having been built first).
- **AD-6 — Degradation ladder.** Every degradation maps to a categorical confidence level +
  `reasons[]` drawn from a **closed snake_case token enum** (`cards_unresolved`, `combo_data_stale`,
  `combo_data_unavailable`, `game_changer_data_unavailable`, `multiplayer_variance`,
  `format_profile_stale`) — never an exception or silent zero. **Tokens never embed counts/phrases**
  (counts live in separate structured fields; phrasing only in `summary`). `structural_gaps[]` is
  likewise a closed enum. Combo ladder: fresh hit → full; expired + fetch fails → stale entry +
  `combo_data_stale`; no entry + fetch fails → absent + `combo_data_unavailable` + degrade.
- **AD-7 — One versioned Pydantic `AssessDeckPowerResult`.** Carries a `status` enum
  (`ok | deck_not_found | unsupported_format | database_not_initialized | error`), a `summary`
  string, an `assessment` object (or `null` when `status != ok`), and an always-present
  `schema_version`. `assessment` carries the 7-dimension vector (**fixed closed key set, all seven
  always present regardless of format**), the for-format 0–100 + descriptive label, the derived 1–10
  projection, `confidence{level, reasons[]}`, and `flags{...}`. **Commander-only flags** (`bracket`,
  `mass_land_denial`, `extra_turn_chains`, `cedh_candidate`) are absent/`false` for Standard;
  `cedh_candidate` homed once in `flags`; cEDH flagged as candidacy, never asserted.
- **AD-8 — Deterministic serialization; no clock in the diff surface.** Two runs of the same deck +
  snapshot + cache MUST yield byte-identical JSON: (1) all flag lists + `confidence.reasons[]`
  emitted **sorted ascending bytewise**; (2) dimension scores are **integer 0–100**, 1–10 projection
  = `1 + score*9/100` **half-up to 1 decimal via `Decimal`**, emitted as a JSON number; (3) the
  Result embeds **no call-time clock** (no `assessed_at`/`now()`); "as of" comes only from inputs.
- **AD-9 — Layer placement.** Spellbook client = async httpx **I/O adapter at the data layer**
  (sibling to `importers/scryfall_api.py`), never in `src/logic`. Combo-cache repo in
  `src/data/repositories` returns Pydantic. All scoring in `src/logic/assessment/` (framework-free).
  The tool orchestrates only. **Spellbook client policy:** explicit timeout, required `User-Agent` +
  `Accept` headers, polite throttling, **manual exponential backoff** mirroring
  `importers/scryfall_api.py` (`tenacity` is NOT a dependency); on exhausted retries returns cleanly
  (never raises to the client) so the edge can apply the AD-6 ladder.
- **AD-10 — Shared oracle-text taxonomy.** Ramp/draw/removal/tutor counting (FR6), win-condition
  tagging (FR10), and mass-land-denial + extra-turn detection (FR12) are new pure functions in
  `src/logic/assessment` following existing `src/logic/synergy.py` conventions (lowercased matching
  over `Card.oracle_text` + `Card.keywords`) — not duplicated into the tool layer.
- **AD-11 — One canonical `ComboRecord`.** Frozen shape used verbatim by cache, scorer, and
  `flags.combos`. Spellbook-sourced fields only: `{spellbook_id, cards[] (sorted names), bucket,
  bracket_tag, produces, popularity}`. Derived `type` + `earliest_turn_estimate` computed in the
  **pure core, not cached**. `bracket_tag` is a closed enum in exact Spellbook wire casing
  (`RUTHLESS→4, SPICY→3, POWERFUL→3, ODDBALL→2, PRECON_APPROPRIATE→2, CASUAL→1`), normalized once at
  the edge; the core's combo→bracket map keys on it exactly.
- **AD-12 — One canonical, multiplicity-aware cache key.** `sha256` of a **canonical JSON**
  `{"commanders": [sorted names], "main": {name: qty}}` (includes multiplicities), produced by one
  named pure helper used by both read and write paths. **Builtin `hash()` is forbidden** (salted /
  non-deterministic across processes).
- **Data model & migration (addendum §B, AD-4).** `game_changer` on `CardModel`
  (`src/data/models/card.py`) + `Card` schema (`src/data/schemas/card.py`); extracted in
  `transform_scryfall_card` (`src/data/importers/transformers.py`); hand-written
  `scripts/migrate_add_game_changer.py` (additive; ensures WAL) + heavy Scryfall re-import to
  backfill (~60k cards).
- **Implementation constants (addendum §C).** Karsten Commander lands
  `31.42 + 3.13·avgMV − 0.28·(cheap draw + ramp)`; Karsten 60-card lands
  `19.59 + 1.90·avgMV − 0.28·(cheap draw + ramp)`; redundancy openers (4/8/12 copies →
  39.9%/65.4%/80.9%); Bracket gating (0 GC → B1–2; 1–3 GC → B3; 4+ GC / mass land denial / early
  two-card infinite → B4; cEDH B5 self-declared = candidacy flag only); GC list ~53 cards as of
  Feb 9 2026 (`is:gamechanger`).
- **Calibration benchmark (addendum §D, NFR6).** A committed held-out set (WotC precons expected
  ~Bracket 2; known cEDH lists expected to flag as candidates / score high) is the scorer's
  acceptance gate. Composing it is the **first implementation task**; the 7-dimension aggregate
  weights start hand-tuned (documented, adjustable) and are validated against this set.

### UX Design Requirements

**N/A** — This is a headless MCP capability with no UI (PRD §3: "no separate UI and no standalone
persona section"). The only human-facing surface is the `summary` string inside
`AssessDeckPowerResult`, which is a deterministic projection of the structured `assessment` (AD-8)
and is covered by FR22/FR24. There is no UX design contract to decompose.

### FR Coverage Map

- **FR1** → Epic 4 — tool signature + deck load via `get_deck_with_cards`
- **FR2** → Epic 4 — format inference + graceful unsupported-format error
- **FR3** → Epic 4 — card resolution + unresolved count → confidence
- **FR4** → Epic 2 — versioned `FormatProfile` (selected/emitted at edge in Epic 4)
- **FR5** → Epic 2 — curve / avg MV / land count
- **FR6** → Epic 2 — ramp/draw/removal/tutor classifiers (AD-10)
- **FR7** → Epic 2 — instant-speed ratio + interaction-CMC distribution
- **FR8** → Epic 2 — Karsten land + pip math → flood/screw + mana efficiency
- **FR9** → Epic 2 — rule-of-8 / 8×8 structural gaps
- **FR10** → Epic 2 — win-condition tagging (AD-10)
- **FR11** → Epic 1 — `game_changer` field / import / migration (read by Epic 2 scorer)
- **FR12** → Epic 2 — mass-land-denial + extra-turn detection (AD-10)
- **FR13** → Epic 3 — Spellbook `find-my-combos` + included/almostIncluded bucketing
- **FR14** → Epic 3 — ≥24h cache + throttle + 429 backoff
- **FR15** → Epic 2 — combo → two-card-infinite trigger + combo_potential
- **FR16** → Epic 2 — 7-dimension vector (speed deterministic)
- **FR17** → Epic 2 — hypergeometric consistency
- **FR18** → Epic 2 — Commander Bracket floor + cEDH candidacy
- **FR19** → Epic 2 — for-format aggregate + 1–10 projection
- **FR20** → Epic 2 — Standard heuristic-only score
- **FR21** → Epic 4 — degradation → categorical confidence ladder (AD-6); vocabulary + core-derived reasons defined in Epic 2
- **FR22** → Epic 4 — dual output (summary + structured)
- **FR23** → Epic 4 — flags block assembly (values computed across Epics 1–3)
- **FR24** → Epic 2 — descriptive tier label (surfaced in Epic 4 output)

> **Cross-cutting note (FR21 / FR23):** these are split by the functional-core / imperative-shell
> design — the *values* are computed in the pure core (Epic 2), while the *degradation policy* and
> *serialization/assembly* live at the edge (Epic 4). Intended architecture, not a coverage gap.

## Epic List

### Epic 1: Game Changer card data
Every card in the local Scryfall snapshot carries its official WotC **Game Changer** membership, so
the assessor can floor Commander Brackets on real data rather than guessing. Adds a **nullable**
`game_changer` field to `CardModel` + `Card` schema, extracts it in `transform_scryfall_card`, ships
a hand-written additive migration (no Alembic), and backfills via a Scryfall re-import. NULL means
"unknown" and must never coalesce to `False`.
**FRs covered:** FR11 · **Architecture:** AD-4

### Epic 2: Deterministic scoring core (the assessor's brain)
A **pure, benchmark-validated** scorer in `src/logic/assessment/` turns a resolved deck + combo data
+ a `FormatProfile` into the 7-dimension vector, Commander Bracket floor, for-format 0–100 score,
descriptive tier label, and confidence math — with **no network, DB, or clock**, so identical inputs
yield byte-identical results. Includes the oracle-text classifiers (AD-10), Karsten mana math,
hypergeometric consistency, the canonical `ComboRecord` shape + combo→bracket map (AD-11), the
versioned `FormatProfile` constants (AD-3), and the committed **calibration benchmark** (NFR6) that
is its acceptance gate. Validated with combo *fixtures* — no live dependency required.
**FRs covered:** FR4, FR5, FR6, FR7, FR8, FR9, FR10, FR12, FR15, FR16, FR17, FR18, FR19, FR20, FR24
(+ FR21 vocabulary) · **Architecture:** AD-2, AD-3, AD-10, AD-11 · **NFRs:** NFR6, NFR8

### Epic 3: Live combo detection via Commander Spellbook
The deck's real two-card-infinite / loop combos are **fetched, cached (≥24h), and degraded
gracefully**, ready to feed the scorer and the Bracket floor. Adds an async httpx Spellbook client at
the data layer (manual exponential backoff mirroring `importers/scryfall_api.py` — no `tenacity`),
an ephemeral combo-cache table in `cards.db` reached through a repository that returns Pydantic
(never ORM), keyed by the AD-12 multiplicity-aware cache key, populating the `included` +
`almostIncluded` buckets into canonical `ComboRecord`s. The only external live dependency.
**FRs covered:** FR13, FR14 · **Architecture:** AD-5, AD-9, AD-11, AD-12 · **NFRs:** NFR4

### Epic 4: The `assess_deck_power` MCP tool & deterministic output
An agent calls **one MCP tool** on a saved deck and gets back a deterministic, diffable
`AssessDeckPowerResult` (human `summary` + structured `assessment` + `flags` + `confidence`), with
graceful format resolution and the AD-6 degradation ladder. Registers the `async def` tool alongside
the existing analysis tools (AD-1), orchestrates deck-load → format-resolve → combo-fetch → pure
scorer, assembles the versioned result with a fixed 7-key vector and format-gated flags (AD-7), and
serializes it deterministically (sorted lists, integer scores, `Decimal` 1–10 projection, **no
call-time clock** — AD-8). This is where the "did my edit make it stronger, and what changed?"
question gets answered.
**FRs covered:** FR1, FR2, FR3, FR21, FR22, FR23 · **Architecture:** AD-1, AD-6, AD-7, AD-8 ·
**NFRs:** NFR1, NFR3, NFR7

---

## Epic 1: Game Changer card data

Every card in the local Scryfall snapshot carries its official WotC **Game Changer** membership, so
the assessor can floor Commander Brackets on real data. Nullable field (`None` = unknown, never
coalesced to `False`), additive migration (no Alembic), backfilled by a deliberate re-import.
**FRs covered:** FR11 · **Architecture:** AD-4 · **Precedent:** `scripts/migrate_add_power_toughness.py`.

### Story 1.1: Add the nullable `game_changer` field end-to-end

As the deck-power assessor,
I want each `Card` to expose its official Game Changer status (or `None` when unknown),
So that the scorer can floor Commander Brackets on real WotC data instead of guessing.

**Acceptance Criteria:**

**Given** the ORM and schema layers
**When** the field is added
**Then** `CardModel` (`src/data/models/card.py`) gains `game_changer: Mapped[bool | None]` via `mapped_column(...)` with dataclass init flags (`default=None`), matching the existing typed-`Mapped` style
**And** `Card` (`src/data/schemas/card.py`) gains `game_changer: bool | None = None` with `from_attributes=True` preserved.

**Given** a Scryfall bulk record being imported
**When** `transform_scryfall_card` (`src/data/importers/transformers.py`) runs
**Then** it reads the bulk `game_changer` boolean and sets it on the produced card
**And** when the source record omits the key, the value is `None` (unknown), never coerced to `False`.

**Given** the layer contract
**When** a repository returns cards
**Then** `game_changer` round-trips through the Pydantic `Card` schema (never leaks an ORM model), and `None` / `True` / `False` remain three distinct states everywhere.

**Given** `mypy --strict` and ruff gates
**When** the change is committed
**Then** type hints are complete (`bool | None`) and pre-commit passes.

### Story 1.2: Migrate and backfill existing databases

As the operator maintaining a live `cards.db`,
I want an idempotent migration plus a re-import path that populates `game_changer`,
So that decks assessed against my existing snapshot get real Game Changer data, not a permanent "unknown".

**Acceptance Criteria:**

**Given** an existing `cards.db` created before this field
**When** I run `scripts/migrate_add_game_changer.py`
**Then** it adds the nullable `game_changer` column additively (no Alembic), mirroring `scripts/migrate_add_power_toughness.py`
**And** existing rows are left as `NULL` (unknown) until backfilled
**And** re-running the script is a safe no-op (idempotent; detects the column already exists).

**Given** the migrated database
**When** I run the Scryfall re-import (`scripts/import_scryfall_data.py`)
**Then** `game_changer` is backfilled from the bulk data for all ~60k cards
**And** a spot-check confirms known Game Changers (e.g. from the ~53-card Feb 2026 list, `is:gamechanger`) read back `True` and a clearly-non-GC common reads `False`.

**Given** the heavy re-import is a documented, deliberate step
**When** the migration script runs
**Then** it does not trigger the re-import automatically; the operator invokes it explicitly (per the project's "don't re-import casually" rule).

---

## Epic 2: Deterministic scoring core (the assessor's brain)

A pure, benchmark-validated `score(cards, combos, profile)` in `src/logic/assessment/` — no network,
DB, or clock (AD-2). Built in dependency order: benchmark → profile → signals → dimensions →
aggregate → validated entry point.
**FRs covered:** FR4, FR5, FR6, FR7, FR8, FR9, FR10, FR12, FR15, FR16, FR17, FR18, FR19, FR20, FR24
(+ FR21 vocabulary) · **Architecture:** AD-2, AD-3, AD-10, AD-11 · **NFRs:** NFR6, NFR8 ·
**Precedents:** `src/logic/synergy.py`, `src/logic/mana_curve.py`, `src/logic/deck_validator.py`.

### Story 2.1: Compose the calibration benchmark set

As the scorer's author,
I want a committed held-out set of decklists with expected outcomes,
So that "done" is decidable rather than blocked on an open question.

**Acceptance Criteria:**

**Given** the acceptance gate (NFR6, Success Metric 1)
**When** the benchmark is composed
**Then** it commits a handful of WotC precons (expected ~Bracket 2) and known cEDH lists (expected to flag as cEDH candidates / score high) as test fixtures with documented expected results
**And** each entry records the format, the decklist, and the expected Bracket / flag / tier outcome
**And** it is structured for later stories to assert against (a pytest fixture/dataset), with no scorer dependency yet.

### Story 2.2: `FormatProfile` frozen-data module

As the scorer,
I want per-format constants in one passive typed data bag,
So that scoring behavior is versioned and tunable without code branching.

**Acceptance Criteria:**

**Given** AD-3
**When** the module is created in `src/logic/assessment`
**Then** it defines typed **frozen** `FormatProfile` constants with a `commander` and a `standard` profile, each carrying: rubric selector (`brackets | heuristic_only`), expected-win-turn band, aggregate weights, per-dimension mapping parameters, and flags (`combos_enabled`, `multiplayer_variance`, `game_changers_version`), plus a monotonic `format_profile_version` string (FR4)
**And** the profile is a passive data bag — no behavior/methods; the scorer reads and branches on it
**And** it is an in-repo Python constants module (not an external data file, not inline literals).

### Story 2.3: Shared oracle-text classifiers

As the scorer,
I want one oracle-text taxonomy,
So that ramp/draw/removal/tutor counts, win-conditions, and hard triggers share vocabulary rather than forking it.

**Acceptance Criteria:**

**Given** the `src/logic/synergy.py` conventions (lowercased matching over `Card.oracle_text` + `Card.keywords`)
**When** classifiers are added to `src/logic/assessment`
**Then** pure functions count ramp, card-draw/advantage, removal/interaction, and tutors via oracle-text + `type_line` classification (FR6)
**And** win-condition tagging identifies combo pieces, "you win the game" text, and evasive/haymaker finishers (FR10)
**And** mass-land-denial and extra-turn-chain detection return booleans (FR12)
**And** the vocabulary is defined once here and not duplicated into the tool layer (AD-10).

### Story 2.4: Mana-base & curve signals

As the scorer,
I want curve and Karsten mana math,
So that mana efficiency and consistency reflect real mana-base quality.

**Acceptance Criteria:**

**Given** the deck's cards
**When** computed
**Then** mana curve, average mana value (from `cmc`), and land count are produced (FR5)
**And** the Karsten land-count delta is computed with both Commander (`31.42 + 3.13·avgMV − 0.28·(cheap draw + ramp)`) and 60-card (`19.59 + 1.90·avgMV − 0.28·(…)`) formulas → mana-flood / mana-screw flags (FR8)
**And** colored-source / pip consistency (Karsten pip math) is computed and feeds the mana-efficiency dimension.

### Story 2.5: Consistency, interaction & structural-coverage signals

As the scorer,
I want deterministic consistency and structural signals,
So that the vector reflects reliability and coverage without simulation.

**Acceptance Criteria:**

**Given** hypergeometric math
**When** computed
**Then** key-piece and mana access by turn N are derived analytically (deterministic, no Monte Carlo) (FR17)
**And** instant-speed ratio and interaction-CMC distribution are computed (FR7)
**And** rule-of-8 / functional-redundancy (Commander) plus 8×8 structural-coverage gaps are emitted as a **closed-enum `structural_gaps[]`** token list (e.g. `ramp_below_baseline`) (FR9).

### Story 2.6: `ComboRecord` + combo→bracket mapping

As the scorer,
I want one canonical combo shape and a fixed bracket mapping,
So that cache, core, and output never diverge on combo data.

**Acceptance Criteria:**

**Given** AD-11
**When** defined in the core
**Then** a frozen `ComboRecord` carries Spellbook-sourced fields `{spellbook_id, cards[] (sorted names), bucket (included | almostIncluded), bracket_tag, produces, popularity}`; derived `type` and `earliest_turn_estimate` are computed in the core and are **not** part of the cached shape
**And** `bracket_tag` is a closed enum in exact Spellbook wire casing mapped `RUTHLESS→4, SPICY→3, POWERFUL→3, ODDBALL→2, PRECON_APPROPRIATE→2, CASUAL→1`; a casing mismatch is a hard error, never a silent wrong floor
**And** combos feed both the two-card-infinite Bracket trigger and the `combo_potential` dimension (FR15).

### Story 2.7: Dimension vector + Commander Bracket floor + cEDH candidacy

As the scorer,
I want the 7-dimension vector and the Commander Bracket floor,
So that a deck gets its power read.

**Acceptance Criteria:**

**Given** the signals from Stories 2.3–2.6 plus the `FormatProfile`
**When** scored
**Then** all seven dimensions (`speed, consistency, resilience, interaction, mana_efficiency, card_advantage, combo_potential`) are produced as **integer 0–100**, always present; `speed` is estimated deterministically from curve + ramp density + combo earliest-turn (no goldfish sim) (FR16)
**And** the Commander Bracket floor (1–5) is set from Game Changer count + hard triggers + combos per the WotC decision tree; `cedh_candidate` is flagged only, never asserting Bracket 5 (FR18)
**And** when any card's `game_changer` is `None`, the absent GC count does not lower the Bracket floor (AD-4 read side).

### Story 2.8: For-format aggregate, tier label, Standard fork & confidence vocabulary

As the scorer,
I want the aggregate score, human label, Standard path, and confidence vocabulary,
So that every deck gets a labeled score with honest confidence tokens.

**Acceptance Criteria:**

**Given** the dimension vector + profile weights
**When** aggregated
**Then** a for-format **0–100** score is produced and the derived 1–10 projection value is available (final rounding/serialization is Epic 4 / AD-8) (FR19)
**And** every for-format score carries a descriptive tier label (e.g. Unfocused / Focused / Tuned / High-Power / Competitive) from profile thresholds — no bare number (FR24)
**And** the Standard fork (rubric `heuristic_only`) scores from curve / interaction / Karsten-60 / combos with no Bracket and no percentile, always with the label (FR20)
**And** the closed snake_case confidence-reason enum is defined (`cards_unresolved`, `combo_data_stale`, `combo_data_unavailable`, `game_changer_data_unavailable`, `multiplayer_variance`, `format_profile_stale`) with the core-derived reasons (`multiplayer_variance`, `format_profile_stale`) populated; tokens never embed counts (FR21 vocabulary).

### Story 2.9: Pure `score()` entry point + benchmark validation

As the scorer's author,
I want one pure entry point validated against the benchmark,
So that the core is proven deterministic and correctly calibrated.

**Acceptance Criteria:**

**Given** all prior Epic 2 stories
**When** `score(cards, combos, profile)` is composed
**Then** it returns the full core assessment object (vector, bracket/label, aggregate, flags, confidence) with no network/DB/clock access (AD-2)
**And** identical `(cards, combos, profile)` inputs yield an identical object (determinism, core side of NFR1)
**And** run against Story 2.1's benchmark, WotC precons land ~Bracket 2 and cEDH lists flag as candidates; weights are hand-tuned (documented, adjustable) until it passes (NFR8)
**And** adding a Game Changer or a combo piece to a fixture moves the expected dimension in the expected direction (diff-sensitivity).

---

## Epic 3: Live combo detection via Commander Spellbook

The deck's real two-card-infinite / loop combos are fetched, cached (≥24h), and degrade gracefully,
ready to feed the scorer and the Bracket floor. Delivers the reusable adapters (cache-key helper,
Spellbook client, cache table/repo); the cache-first → fetch → stale/degrade **orchestration** lives
in Epic 4's edge tool (AD-6).
**FRs covered:** FR13, FR14 · **Architecture:** AD-5, AD-9, AD-11 (populate), AD-12 · **NFRs:** NFR4 ·
**Precedent:** `src/data/importers/scryfall_api.py` (manual exponential backoff; `tenacity` is not a dependency).

### Story 3.1: Canonical, multiplicity-aware cache-key helper

As the combo cache,
I want one deterministic cache key,
So that two callers hashing the same deck always agree and a 4-of never collides with a 1-of.

**Acceptance Criteria:**

**Given** AD-12
**When** the helper runs
**Then** one named **pure** function returns `sha256` of a canonical JSON document `{"commanders": [sorted names], "main": {name: qty}}` that includes card multiplicities
**And** both the read and write paths call this same helper
**And** Python's builtin `hash()` is not used (it is `PYTHONHASHSEED`-salted / non-deterministic across processes)
**And** it is unit-tested: identical decks → identical key; a quantity change → a different key.

### Story 3.2: Async Spellbook `find-my-combos` client

As the assess edge,
I want an async httpx adapter that returns canonical combo records or fails cleanly,
So that combo detection never crashes the assessment.

**Acceptance Criteria:**

**Given** the data layer (sibling to `importers/scryfall_api.py`)
**When** the client calls `find-my-combos`
**Then** it reads the paginated `results` envelope and feeds only the `included` and `almostIncluded` buckets into `ComboRecord`s (change-commander / add-color buckets excluded — fixed-commander assessment) (FR13)
**And** it sets an explicit timeout, required `User-Agent` + `Accept` headers, and polite throttling
**And** it retries 429 / network failures with manual exponential backoff mirroring `scryfall_api.py`'s `max_retries` / `retry_delay` / `2**attempt` loop (no `tenacity`) (FR14 partial)
**And** on exhausted retries it returns cleanly (signaling failure) rather than raising to the caller, so the edge can apply the AD-6 ladder
**And** `bracket_tag` is normalized to the exact Spellbook wire casing at this edge (AD-11).

### Story 3.3: Ephemeral combo-cache table & repository

As the assess edge,
I want a cached, TTL'd combo store in `cards.db`,
So that warm assessments are instant and combo data is diffable.

**Acceptance Criteria:**

**Given** AD-5
**When** the cache is created
**Then** a hand-written migration adds a dedicated ephemeral table in `cards.db` and **ensures `PRAGMA journal_mode=WAL`** (the write path must not depend on the search index having been built first)
**And** a repository in `src/data/repositories` returns Pydantic schemas (never ORM), keyed by the Story 3.1 cache key, with each row carrying `fetched_at` (24h TTL) and a list of canonical `ComboRecord`s under a versioned cache-row schema (not raw JSON)
**And** writes are a single upsert-by-hash under WAL, and the table is truncatable/rebuildable (like `card_vec`)
**And** the repository exposes reading a row with its freshness (fresh vs. stale vs. absent, for AD-6) but does not itself perform the fetch or the degradation decision.

---

## Epic 4: The `assess_deck_power` MCP tool & deterministic output

An agent calls one MCP tool on a saved deck and gets back a deterministic, diffable
`AssessDeckPowerResult` (human `summary` + structured `assessment` + `flags` + `confidence`), with
graceful format resolution and the AD-6 degradation ladder. The integrator that lights up the
"did my edit make it stronger, and what changed?" question.
**FRs covered:** FR1, FR2, FR3, FR21, FR22, FR23 · **Architecture:** AD-1, AD-6, AD-7, AD-8 ·
**NFRs:** NFR1, NFR3, NFR7 · **Precedents:** `src/mcp_server/tools/deck_analysis.py`, `server.py`,
`tests/integration/test_mcp_tools.py`.

### Story 4.1: Register the async tool; load deck & resolve format

As an agent,
I want to call `assess_deck_power(deck_id, format?)` and have it load the right deck data and format,
So that assessment starts from correct, complete inputs.

**Acceptance Criteria:**

**Given** AD-1
**When** the tool is registered in `server.py`
**Then** `assess_deck_power` is an **`async def`** tool sibling to `analyze_mana_curve` / `detect_synergies` / `validate_deck`, stateless (`deck_id` / `format` params only) (FR1, NFR7)
**And** it loads the deck via `DeckRepository.get_deck_with_cards` (full `Card` rows incl. `legalities` / `keywords` / `oracle_text`) — not the `CardSummary` / `load_deck` projection (FR1)
**And** when `format` is omitted it is inferred (`commander | standard`) from the deck's stored format / card `legalities`; an unsupported/unrecognized format returns a graceful `unsupported_format` result naming supported formats — never a crash (FR2)
**And** a missing deck → `deck_not_found`; an uninitialized DB → `database_not_initialized` (status enum, AD-7)
**And** every card is resolved against the local snapshot and the unresolved/ambiguous count is captured for confidence (FR3).

### Story 4.2: Combo orchestration & the degradation ladder

As the edge,
I want cache-first combo provisioning with graceful degradation,
So that a Spellbook outage or stale data lowers confidence instead of crashing or silently scoring zero.

**Acceptance Criteria:**

**Given** `combos_enabled` on the profile
**When** the edge provisions combos
**Then** it applies the AD-6 ladder: fresh cache hit → full contribution; expired entry + fetch fails → **stale** entry + `combo_data_stale`; no entry + fetch fails → combos absent + `combo_data_unavailable` + degrade
**And** on a successful fetch it upserts the cache (Story 3.3) keyed by the Story 3.1 key
**And** edge-derived confidence reasons are assembled from a closed enum: `cards_unresolved` (+ separate count field, from Story 4.1), `combo_data_stale` / `combo_data_unavailable`, `game_changer_data_unavailable` when any card's `game_changer` is `None` (AD-4), plus core-derived `multiplayer_variance` / `format_profile_stale` — tokens never embed counts (FR21)
**And** degradation never raises to the client and never yields a silent zero (NFR3).

### Story 4.3: `AssessDeckPowerResult` — assembly, deterministic serialization & human summary

As a caller diffing two runs,
I want one versioned result that serializes byte-identically,
So that comparison is trustworthy.

**Acceptance Criteria:**

**Given** the resolved inputs
**When** the edge calls the pure `score(cards, combos, profile)` (Epic 2) and assembles the result
**Then** it returns a single `AssessDeckPowerResult` with a `status` enum, a human `summary` string, an `assessment` object (or `null` when `status != ok`), and an always-present `schema_version` (AD-7)
**And** `assessment` carries the 7-key vector (all seven always present, any format), the for-format 0–100 + descriptive tier label (FR24), the 1–10 projection, `confidence{level, reasons[]}`, and `flags{game_changers, combos, structural_gaps, mass_land_denial, extra_turn_chains, cedh_candidate}` — Commander-only flags absent/`false` for Standard; `cedh_candidate` homed once, candidacy never asserted (FR23, AD-7)
**And** serialization is deterministic (AD-8): all flag lists + `confidence.reasons[]` sorted ascending bytewise; dimension scores integer 0–100; the 1–10 projection = `1 + score*9/100` half-up to 1 decimal via `Decimal`, emitted as a JSON number; and the result embeds no call-time clock (no `assessed_at` / `now()`)
**And** the human `summary` is a pure, deterministic projection of `assessment` (FR22) — the diff surface is the structured block.

### Story 4.4: End-to-end tool test + determinism & diff regression

As the maintainer,
I want the tool proven end-to-end,
So that determinism and diff-sensitivity are guarded against regressions.

**Acceptance Criteria:**

**Given** an in-process MCP client
**When** the tool is driven in `tests/integration/test_mcp_tools.py`
**Then** a Commander deck returns Bracket + all seven dimensions + tier label; a Standard deck returns a for-format score + all seven dimensions + label + no Bracket
**And** two runs of the same deck + snapshot + cache produce byte-identical JSON (determinism regression, NFR1)
**And** swapping cards (adding a Game Changer / combo piece) produces a correctly-directioned dimension delta (diff-sensitivity)
**And** the degradation paths (Spellbook unreachable, unresolved cards, NULL `game_changer`) each return a scored result with the right confidence reason — no crash, no silent zero.
