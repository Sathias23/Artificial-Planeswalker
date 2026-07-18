---
baseline_commit: dfc45b2
---

# Story 7.3: `AssessDeckPowerResult` — assembly, deterministic serialization & human summary

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a caller diffing two runs,
I want one versioned result that serializes byte-identically,
so that comparison is trustworthy.

## Acceptance Criteria

1. **The `assessment` block is widened from `None` to the full AD-7 shape.** On the
   `status="ok"` path the edge serializes the existing `ScoredAssessment` seam (7.2's
   carrier — do not re-derive anything) into a new nested Pydantic model on
   `AssessDeckPowerResult.assessment`; every non-ok status keeps `assessment=None`
   (all 5 early-return construction sites unchanged). `schema_version` stays `"1"` and
   always present — the block was documented as pending since 7.1, so completing it IS
   v1, not a version bump (decide-once #1). The `status` enum is not widened.

2. **`assessment` carries the fixed closed shape — no format-conditional keys (FR23/AD-7).**
   All fields always present, any format:
   - `format`: the resolved profile key (`"commander" | "standard"`) — in the
     `docs/deck-assess.md` schema and not on FR22's minus-list; 7.5 reads it for the
     `format_mismatch` check.
   - `vector`: the 7-key integer vector — exactly `speed, consistency, resilience,
     interaction, mana_efficiency, card_advantage, combo_potential`, all seven always
     present, each an `int` 0–100 (serialize `CoreAssessment.vector` field-for-field).
   - `for_format_score`: `int` 0–100 (FR19) + `tier`: the FR24 descriptive label
     (`Unfocused | Focused | Tuned | High-Power | Competitive`) — no score without its
     label, no 1–10 projection anywhere.
   - `bracket`: `int | None` — `CoreAssessment.bracket_floor` renamed at the boundary
     (the scorer docstring pins this mapping: `bracket_floor=None` → `bracket: null`).
     Standard always `null`; never omitted.
   - `data_vintage`: from stored input metadata ONLY (FR22/AD-8):
     `combo_snapshot_imported_at: str | None`, `combo_snapshot_export_version: str | None`
     (both from the seam's `vintage: ComboSnapshotMeta | None`, `None` → JSON `null` —
     fixed keys, never omitted; decide-once #2), and `format_profile_version: str` from
     `inputs.profile`. No datetime parsing — the strings pass through verbatim.
   - `confidence`: `{level, reasons[]}` from the seam's `confidence_level` /
     `confidence_reasons` (already bytewise-sorted by 7.2's ladder — emit as-is).
   - `flags`: exactly `{game_changers, combos, structural_gaps, mass_land_denial,
     extra_turn_chains, cedh_candidate}` — `game_changers` =
     `core.game_changers.card_names` (already sorted), `combos` = the matched
     `ComboRecord`s verbatim (AD-11 — bucket populated; already sorted by
     `spellbook_id`; no derived `type`/`earliest_turn_estimate` fields, decide-once #3),
     `structural_gaps` = the closed tokens (already sorted), the two booleans from
     the core, and `cedh_candidate` homed HERE and only here (Standard: `False`,
     `bracket: null`, booleans `False` when absent — fixed shape, candidacy never
     asserted as Bracket 5).

3. **Serialization is deterministic (AD-8/NFR1).** Two calls on the same deck + card
   snapshot + combo snapshot produce byte-identical `model_dump_json()`: all list
   fields emitted pre-sorted (reasons/gaps/game_changers bytewise ascending; combos by
   `spellbook_id`; each `ComboRecord`'s `cards`/`produces` already sorted by its
   validator), all dimension scores `int`, and the result embeds **no call-time
   clock** — no `assessed_at`, no `now()`, nothing `datetime`-derived anywhere in the
   new models. "As of" facts come only from `data_vintage`. A serialization-equality
   test pins this at the model level (the client-level byte test is Story 7.4).

4. **The human `summary` is a pure deterministic projection (FR22/FR24/AD-8).** Rebuilt
   from the assembled facts only — no clock, no randomness, no unsorted iteration. It
   must state at minimum: resolved format + `format_profile_version`, the
   commander-resolution facts (existing `_commander_text`), score as `N/100` with the
   tier label, the Bracket (Commander only, phrased as a floor — e.g. "Bracket 3
   floor"; omitted from the sentence for Standard — prose may vary by format, the
   structured shape may not), confidence level + sorted reasons (or "no degradations"),
   and the flag facts that drove the result (Game Changer count, structural gaps,
   `cedh_candidate` when `True`). The provisional "…lands in Story 7.3" sentence is
   removed.

5. **`included` vs `almost_included` are disambiguated in the summary (7.2 review
   deferral, owned here).** The summary never counts a shortfall-1 variant as a matched
   combo: report the two bucket counts distinctly (e.g. "2 combos included, 1 one card
   away" — exact phrasing free, conflation banned). The structured `flags.combos`
   carries `bucket` per record, so the diff surface is already honest.

6. **The multiplayer-variance caveat lands (FR21/AD-3/AD-6).** When
   `inputs.profile.multiplayer_variance_caveat` is `True` (Commander), the summary
   appends the fixed caveat sentence — profile-driven `summary` text, NEVER a
   confidence reason, never a token. Standard (`False`) emits no caveat. This is the
   first implementation of the caveat anywhere — define the sentence as a module
   `Final` constant so 7.4/7.5 can assert against it.

7. **The LLM-facing tool docstring is updated (`server.py`).** The registered
   `assess_deck_power` docstring drops "provisional — resolution facts only" /
   "The scored assessment block is not populated yet" and documents the real result:
   the assessment block's shape (vector, score+tier, bracket, data_vintage, confidence,
   flags), determinism, and the degradation behavior. The docstring IS the tool
   description agents read — treat it as a product surface. The helper-module docstring
   in `assess_deck_power.py` sheds its "Result widening is still pending" paragraph the
   same way.

8. **Type + lint gates pass.** `mypy --strict` over `src/`, `ruff check` +
   `ruff format`, pre-commit succeeds without `--no-verify` (the `build-plugin-sync`
   hook re-mirrors `src/` → `plugin/server/`).

9. **Tests prove the shape, determinism, and projection offline (no live DB, no
   network).** Extend `tests/integration/mcp_server/test_assess_deck_power_tool.py`
   (existing fixture stack, 41 tests) and `tests/integration/test_mcp_tools.py`:
   - ok path → `assessment` populated; every non-ok status → `assessment is None`.
   - **Fixed shape:** a Standard deck's assessment has all 7 vector keys,
     `bracket is None`, `cedh_candidate is False` — key set identical to a Commander
     deck's (assert same `model_dump()` key sets, both formats).
   - **data_vintage:** seeded snapshot meta → `imported_at`/`export_version` echoed
     verbatim + `format_profile_version`; absent meta (or `combos_enabled=False`
     profile) → both combo keys `None`, key still present.
   - **Determinism:** two runs, same session fixtures → identical
     `model_dump_json()` bytes (assert equality, not just equal dicts).
   - **Sorted emission:** reasons/gaps/game_changers bytewise-sorted; combos by
     `spellbook_id`.
   - **Summary projection:** pins format+profile version, `N/100 (tier)`, bucket-split
     combo counts (an `almost_included` fixture must NOT read as matched/included),
     confidence + reasons, caveat present for Commander profile / absent for Standard.
   - **No clock:** assert the serialized JSON contains no key or value derived from
     call time (e.g. grep the dump for `assessed_at` absence; the real guard is that
     the models simply have no such field).
   - MCP-client level: happy path round-trips `structuredContent["assessment"]` with
     the vector + flags; the 7.2 summary assertions (`/100`, `confidence `) still pass;
     update any assertion pinning the removed provisional sentence.

## Tasks / Subtasks

- [x] Task 0: Story-start state verification (standing team agreement) (AC: all)
  - [x] `git status` — clean tree expected on `feat/deck-power-assessment` at `dfc45b2`
        (7.2 review patch committed). If dirty, stop and reconcile first.
  - [x] `uv run pytest --collect-only -q | tail -1` — confirm full-suite baseline
        **1,299** (7.2's post-review count); record actual in Dev Agent Record.
  - [x] Confirm imports resolve in one probe:
        `from src.logic.assessment import CoreAssessment, DimensionVector, GameChangerSignal, TierLabel`
        and `from src.data.schemas.combo import ComboRecord, ComboSnapshotMeta`
        (all verified exported 2026-07-17, incl. the `TierLabel` re-export).
  - [x] Re-read `ScoredAssessment` + the ok-path tail of
        `src/mcp_server/tools/assess_deck_power.py:523-549` before writing any code.
- [x] Task 1: Result models (TDD — shape tests first) (AC: 1, 2)
  - [x] New frozen Pydantic models in `assess_deck_power.py` (suggested names:
        `AssessmentVector`, `DataVintage`, `Confidence`, `AssessmentFlags`,
        `Assessment`) — declaration order IS emission order; model_config
        `frozen=True`. `flags.combos: tuple[ComboRecord, ...]` reuses the AD-11 schema
        directly (it is already frozen Pydantic — never mirror it).
  - [x] Widen `AssessDeckPowerResult.assessment: Assessment | None = None`; update its
        class docstring (drop "provisional shape" wording).
  - [x] Pure assembly function (suggested: `_build_assessment(scored: ScoredAssessment)
        -> Assessment`) — field-for-field from the seam, zero recomputation, zero I/O.
- [x] Task 2: Summary projection + caveat (AC: 4, 5, 6)
  - [x] Module `Final` constant for the multiplayer-variance caveat sentence; append
        iff `profile.multiplayer_variance_caveat`.
  - [x] Rewrite the ok-path summary builder as a function of the assembled
        `Assessment` (+ deck name / commander text): bucket-split combo counts
        (`sum(1 for c in combos if c.bucket == "included")` vs `"almost_included"`),
        Bracket-floor phrasing for Commander, drop the Story-7.3 pointer sentence.
  - [x] Keep every fragment deterministic: no set iteration, no dict iteration over
        unsorted sources, no timestamps.
- [x] Task 3: Docstring surfaces (AC: 7)
  - [x] `server.py` `assess_deck_power` docstring: describe the real result block +
        determinism + degradation; keep Args/Returns Google style.
  - [x] `assess_deck_power.py` module docstring: 7.1/7.2/7.3 slice now complete;
        remove the pending-widening paragraph.
- [x] Task 4: Tests (AC: 9)
  - [x] Extend `test_assess_deck_power_tool.py`: shape parity (Commander vs Standard
        key sets), non-ok `assessment is None` (all 4 non-ok statuses), data_vintage
        verbatim + null-vintage, `model_dump_json()` byte-equality across two calls,
        sorted-emission pins, summary projection matrix (incl. `almost_included`
        disambiguation + caveat gating).
  - [x] `test_mcp_tools.py`: extend the happy-path `structuredContent` assertion to
        `assessment` (vector keys + a flag), fix any assertion on the removed sentence.
- [x] Task 5: Quality gates + story wrap-up (AC: 8)
  - [x] `uv run ruff check . --fix && uv run ruff format .`; `uv run mypy src/`;
        `uv run pytest` full suite green; pre-commit re-syncs the plugin mirror —
        commit it.
  - [x] Update this story file (Dev Agent Record, File List, Change Log); status →
        review. Conventional Commit suggestion:
        `feat: assess_deck_power result assembly + deterministic serialization (story 7.3)`.

## Dev Notes

### What this story is (and is NOT)

The **output-contract slice** of the `assess_deck_power` edge (feature Story 4.3,
sprint key `7-3`): widen `assessment` to the full AD-7 block, make its serialization
AD-8-deterministic, and turn the provisional summary into the real FR22 projection
(incl. the multiplayer caveat and the `almost_included` wording fix). It does **NOT**
include:

- **The end-to-end determinism/diff regression suite** — Story 7.4 (client-level
  byte-identical JSON, dimension-delta direction tests, degradation-path e2e matrix).
  This story pins determinism at the model level only.
- **`compare_deck_power`** — Story 7.5 (it consumes `assessment.format` and the field
  names chosen here as its delta keys — name fields deliberately).
- **Any calibration/tuning** — the G-R2 named calibration inputs (card_advantage
  saturation at 80, interaction railing 0/100, Brawl mana_efficiency floor,
  almost_included dominance, format-blind almost_included inflation) are Epic 7
  inputs owned by later work, not this story. Do not touch `src/logic/assessment`
  scoring math, profiles, or the matcher.
- **Any change to `src/logic/` or `src/data/`** — every value this story emits
  already exists on the `ScoredAssessment` seam or `CoreAssessment`, and every type it
  imports is already re-exported (verified, incl. `TierLabel`). If a shape seems
  missing, stop and surface it; do not add core fields.
- **Status-enum or schema_version changes** — decide-once #1.

### Critical code facts (verified 2026-07-17)

- **The seam is complete** — `ScoredAssessment`
  (`src/mcp_server/tools/assess_deck_power.py:133-156`): `inputs:
  ResolvedDeckInputs`, `core: CoreAssessment`, `vintage: ComboSnapshotMeta | None`,
  `confidence_level: ConfidenceLevel`, `confidence_reasons: tuple[str, ...]` (already
  bytewise-sorted). Everything this story serializes is already on it.
- **`CoreAssessment`** (`src/logic/assessment/scorer.py:63-107`, frozen dataclass):
  `vector: DimensionVector` (7 int fields, declaration order = the AD-7 key order),
  `for_format_score: int`, `tier: TierLabel`, `bracket_floor: int | None` (always
  `{2,3,4}` under Commander, `None` under Standard — rename to `bracket` at the
  boundary), `cedh_candidate: bool`, `game_changers: GameChangerSignal`, `combos:
  tuple[ComboRecord, ...]` (buckets set, sorted by `spellbook_id`), `structural_gaps:
  tuple[str, ...]` (sorted), `mass_land_denial: bool`, `extra_turn_chains: bool`. Its
  class docstring: "All collection fields are tuples that arrive pre-sorted from
  their producers … nothing is re-sorted here" — the edge likewise emits as-is,
  re-sorting nothing (a re-sort would mask a producer regression 7.4 wants to catch).
- **The scorer module docstring pins this story's mapping**
  (`scorer.py:34-40`): "7.3 serializes `CoreAssessment` into `AssessDeckPowerResult`
  (`bracket_floor=None` → `bracket: null`, `game_changers.card_names` →
  `flags.game_changers`); 7.5 diffs two of these — the field names here are its delta
  keys."
- **`DimensionVector`** (`src/logic/assessment/dimensions.py:436-462`): fields
  `speed, consistency, resilience, interaction, mana_efficiency, card_advantage,
  combo_potential` — mirror this exact order in `AssessmentVector`.
- **`GameChangerSignal`** (`dimensions.py:247-265`): `known_count: int`,
  `card_names: tuple[str, ...]` (sorted, True-only), `unknown_count: int`. Only
  `card_names` enters `flags`; the counts stay off the output (AD-6: counts live in
  structured fields where a token needs one — no token here needs a count).
- **`ComboRecord`** (`src/data/schemas/combo.py:69-107`): frozen Pydantic —
  `spellbook_id: str`, `cards: tuple[str, ...]` (validator-sorted),
  `commander_required: bool`, `bucket: "included" | "almost_included" | None`,
  `bracket_tag` (closed 6-token enum), `produces: tuple[str, ...]`
  (validator-sorted), `popularity: int | None`. Nest it directly in `flags.combos` —
  AD-11 says "used verbatim by … `flags.combos`". Matched records always have
  `bucket` set (the matcher assigns via `model_copy(update=...)`).
- **`ComboSnapshotMeta`** (`combo.py:110-130`): `imported_at: str`,
  `export_timestamp: str`, `export_version: str`, `variant_count: int` — ISO-8601
  **strings**, pass through verbatim (its docstring: "no datetime parsing, nothing
  clock-derived"). Only `imported_at` + `export_version` enter `data_vintage`
  (AC/AD-7 name exactly those two; decide-once #2).
- **Confidence vocabulary** (`src/logic/assessment/aggregate.py:47-74`): tokens
  `cards_unresolved`, `combo_data_unavailable`, `commander_unidentified`,
  `game_changer_data_unavailable`; `ConfidenceLevel = Literal["low","medium","high"]`.
  `TierLabel = Literal["Unfocused","Focused","Tuned","High-Power","Competitive"]`
  (`profiles.py:49`).
- **Structural-gap tokens** (`consistency.py:292-307`): `card_draw_below_baseline`,
  `interaction_below_baseline`, `ramp_below_baseline`, `wincon_missing` — closed,
  emitted sorted by the core.
- **Profiles** (`profiles.py:131-204`): `COMMANDER_PROFILE.format_profile_version ==
  "commander-v4"`, `multiplayer_variance_caveat=True`;
  `STANDARD_PROFILE.format_profile_version == "standard-v4"`,
  `multiplayer_variance_caveat=False`. The caveat flag has **no consumer yet** —
  AC 6 is its first implementation (`profiles.py:117`: "Whether the edge emits the
  fixed multiplayer-variance caveat").
- **Current ok-path tail** (`assess_deck_power.py:523-549`): builds `ScoredAssessment`
  then a provisional summary ending "The structured assessment block lands in Story
  7.3." and returns `AssessDeckPowerResult(status="ok", deck_id=deck_id,
  summary=summary)` — this is the code AC 1/4 replaces. `combos_matched =
  len(scored.core.combos)` at `:537` is the conflation AC 5 fixes.
- **Construction sites:** 5 non-ok early returns + 1 ok site, all constructing
  `AssessDeckPowerResult` with required `summary` — this story changes ONLY the ok
  site (adds `assessment=`); re-verify the enumeration against the final diff
  (epic-6 retro standing discipline).
- **FastMCP surface:** the tool returns the Pydantic model; FastMCP emits it as
  `structuredContent` (7.1/7.2 tests already round-trip it). Model-level
  `model_dump_json()` determinism is what this story can and must pin; the
  client-level byte test is 7.4's.
- **41 existing tests** in `test_assess_deck_power_tool.py`; the MCP-level happy path
  in `test_mcp_tools.py:355-391` pins `/100` and `confidence ` summary fragments (safe)
  — nothing pins the "lands in Story 7.3" sentence (verified by grep), but re-check
  after rewriting the summary.

### Decide-once decisions this story owns (document each in code)

1. **`schema_version` stays `"1"`.** The assessment block was documented as
   pending-widening from 7.1 (`assessment: None` placeholder with an explicit "Story
   7.3 widens it" note); completing it is the v1 contract, not a change to a released
   one — the tool has never shipped (feature branch, "experimental" release policy per
   epic-5 retro). First post-release shape change bumps it.
2. **`data_vintage` renders an absent vintage as `null`-valued fixed keys**
   (`combo_snapshot_imported_at: null`, `combo_snapshot_export_version: null`) — never
   a missing key, never a conditional sub-object. Rationale: AD-7 bans
   format-conditional keys and absent-vs-false ambiguity for the diff surface; flat
   scalar keys diff cleanest. This closes 7.2's decide-once #6 ("7.3 decides how
   `data_vintage` renders a `None`"). Note `vintage` may be non-`None` even when
   `combo_data_unavailable` fired (meta row present, zero variants) — serialize
   whatever the seam carries; the reason token and the vintage are independent facts.
   `export_timestamp` and `variant_count` are deliberately NOT emitted (AD-7 names
   exactly "imported_at + export version"; additive later if wanted).
3. **`flags.combos` = `ComboRecord` verbatim, no derived fields.** AD-11 pins the
   record shape as the flags entry; the derived `combo_type` /
   `earliest_turn_estimate` helpers are core-internal heuristics (PROVISIONAL per
   their docstrings, 5.9-owned tuning) — emitting them would freeze tunable heuristics
   into the diff surface. `bucket` on each record already gives callers the
   included/almost_included split (FR13). Additive later if a real consumer appears.
4. **`assessment.format` is emitted.** Present in the `docs/deck-assess.md` schema and
   not on FR22's minus-list; AD-7's "no format-conditional keys" bans keys that appear
   conditionally, not a constant-shape `format` value; 7.5's `format_mismatch` check
   needs each side's resolved format without re-resolving.
5. **Bracket is phrased as a floor in the summary, `bracket` in the structure.** The
   core computes a floor (`{2,3,4}` — Brackets 1 and 5 are intent-declared, never
   computed); the structured field is named `bracket` per AD-7/scorer-docstring, and
   the human sentence says "floor" so nobody reads Bracket 3 as an exact rating.
   `cedh_candidate=True` phrasing must stay candidacy ("cEDH candidate"), never
   "Bracket 5" (FR18).
6. **Summary derives from assembled facts only** — the `Assessment` instance plus
   deck-identity facts already on the seam (deck name, commander text). Nothing may be
   recomputed from raw cards at summary time (one derivation path = no drift), and
   nothing non-deterministic may enter (FR22: the summary is a projection of the
   structured block; deck name is stable input, so byte-determinism holds).

### Previous-story intelligence (7.2 + review)

- **7.2 built the seam FOR this story** — `ScoredAssessment` carries inputs/core/
  vintage/confidence precisely so 7.3 "can serialize the full assessment block
  without re-deriving anything" (its docstring). Honor that: `_build_assessment` is a
  mapping, not a computation.
- **7.2 review deferral #2 lands here (AC 5):** `combos_matched =
  len(scored.core.combos)` counts `almost_included` as matched — "a deck one card
  short of a single combo reads '1 combo variant matched', implying a live combo."
  Split the counts by bucket in the summary.
- **7.2 review patch precedent:** all DB reads on this path now sit under
  `DatabaseError → status="error"` guards — this story adds **no new DB reads** (pure
  assembly), so no new guard sites; do not disturb the existing ones.
- **7.2's summary-assertion lesson:** MCP-level tests pin summary fragments (`/100`,
  `confidence `) — keep those fragments stable or update the assertions in the same
  commit.
- **7.1/7.2 style contract:** `summary` not `message`; Google docstrings; module
  logger with lazy `%s` args; modern 3.12 syntax (`X | None`, builtin generics);
  frozen carriers; `format` deliberately shadows the builtin (domain convention).
- **Task 0 state verification is a standing team agreement** — it has caught real
  traps in four consecutive stories (httpx decoding 6.2, baseline off-by-one 6.3,
  7.1's import confirmations, 7.2's uncommitted-patch warning).

### Architecture compliance checklist

- **AD-7:** one versioned Pydantic result; `status` enum unchanged; `assessment`
  object or `null`; `schema_version` always present; fixed closed shape — all seven
  vector keys any format, `bracket: null` + `false` booleans for Standard, no 1–10,
  `cedh_candidate` homed once in `flags`, candidacy never asserted.
- **AD-8:** lists emitted pre-sorted (never re-sorted, never set/insertion order);
  integer dimension scores; **no call-time clock** — the project-context rule
  "timezone-aware UTC everywhere" is deliberately overridden here by AD-8 (the spine
  says so explicitly): there is simply no datetime anywhere in the result. `data_vintage`
  strings pass through verbatim.
- **AD-6:** confidence level + reasons come from the seam untouched; tokens never
  embed counts; the multiplayer caveat is summary text driven by the profile, never a
  reason.
- **AD-11:** `ComboRecord` nested verbatim; derived values stay derived (not
  emitted, decide-once #3).
- **AD-2/AD-9:** edge assembles and serializes only — zero scoring math, zero new
  logic in `src/logic`/`src/data`, no I/O added.
- **NFR2 (explainability):** `flags` carries the exact cards/combos/gaps; the summary
  references them.
- **NFR7:** stateless; no per-session state; sibling-tool conventions kept.

### Testing standards summary

- pytest config in `pyproject.toml`; `asyncio_mode = "auto"` (plain
  `async def test_...`); `--strict-markers`; `tests.*` exempt from `mypy --strict`
  (ruff/naming still apply).
- Extend `tests/integration/mcp_server/test_assess_deck_power_tool.py` — reuse its
  fixture stack (engine → `init_database` → session factory → seeded `CardModel`s →
  `DeckRepository.create_deck` + `add_card_to_deck(..., commander=)`; snapshot
  seeding helpers from 7.2: meta via `ComboSnapshotMetaModel`, variants via
  `ComboVariantModel` + `cards_list` setter + `ComboVariantPieceModel` keyed by
  `name_keys`). The `card-gc-null` "Mystery Relic" seed card exists for the NULL-GC
  fixture; `_card` seeds `game_changer=False` by default.
- Byte-equality: call the helper twice against the same fixtures, compare
  `result_a.model_dump_json() == result_b.model_dump_json()` — string equality, not
  dict equality (dict equality would pass even with unstable ordering).
- Shape parity: `set(commander_result.assessment.model_dump())` ==
  `set(standard_result.assessment.model_dump())` and recursively for `flags` /
  `vector` / `data_vintage` key sets.
- An `almost_included` fixture: seed a 2-card variant, put exactly one piece in the
  deck (7.2's pattern) — then assert the summary does NOT call it included/matched.
- TDD order per task: shape tests first (RED), models/assembly (GREEN). No live DB,
  no network.

### Project Structure Notes

- Modified: `src/mcp_server/tools/assess_deck_power.py` (result models, assembly,
  summary, docstrings), `src/mcp_server/server.py` (tool docstring only),
  `tests/integration/mcp_server/test_assess_deck_power_tool.py`,
  `tests/integration/test_mcp_tools.py`.
- **No new modules**, no `src/logic` / `src/data` / `scripts/` changes, no profile
  edits.
- Generated: `plugin/server/src/mcp_server/...` mirrors (pre-commit hook).
- Naming suggestions: `Assessment`, `AssessmentVector`, `AssessmentFlags`,
  `DataVintage`, `Confidence` (Pydantic, frozen); `_build_assessment`; caveat constant
  e.g. `MULTIPLAYER_VARIANCE_CAVEAT`. Modern 3.12 syntax; Google docstrings.
- Branch: stays on `feat/deck-power-assessment` (no master merge until Epic 7
  completes — "experimental" release policy).

### References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 4.3] —
  story + ACs (sprint key `7-3`); FR22/FR23/FR24 texts; Epic 4 preamble.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-7]
  — the binding result shape (status enum, fixed keys, `data_vintage` fields,
  flags set, "minus" list vs `docs/deck-assess.md`); #AD-8 — sorted lists, integer
  scores, no clock (explicit project-context override note); #AD-6 — caveat is
  summary text, never a reason; #AD-11 — `ComboRecord` verbatim in `flags.combos`,
  derived values never stored.
- [Source: docs/deck-assess.md#7.3 Proposed MCP output schema (JSON)] — the
  illustrative pre-spine schema FR22 subtracts from; AD-7 is authoritative where they
  differ.
- [Source: _bmad-output/implementation-artifacts/7-2-combo-provisioning-the-degradation-ladder.md]
  — `ScoredAssessment` seam contract; decide-once #6 (vintage `None` → 7.3);
  review deferral #2 (`almost_included` wording → this story); fixture/seeding
  patterns; summary-assertion locations.
- [Source: src/mcp_server/tools/assess_deck_power.py:71-156,523-549] — current result
  model + seam + ok-path tail this story rewrites.
- [Source: src/logic/assessment/scorer.py:34-40,63-107] — Epic-7 consumer map
  (bracket_floor→bracket, card_names→flags.game_changers); `CoreAssessment` fields,
  pre-sorted-tuples note.
- [Source: src/logic/assessment/dimensions.py:247-265,436-462] — `GameChangerSignal`;
  `DimensionVector` field order.
- [Source: src/logic/assessment/profiles.py:49,117,131-204] — `TierLabel`; the
  unconsumed `multiplayer_variance_caveat` flag; profile versions.
- [Source: src/logic/assessment/aggregate.py:47-74] — confidence tokens/levels.
- [Source: src/logic/assessment/consistency.py:292-307] — structural-gap tokens.
- [Source: src/data/schemas/combo.py:69-130] — `ComboRecord` (frozen, validator-sorted
  names) + `ComboSnapshotMeta` (verbatim ISO strings).
- [Source: src/mcp_server/server.py:474-501] — the registered tool + LLM-facing
  docstring AC 7 rewrites.
- [Source: _bmad-output/implementation-artifacts/pre-epic-7-real-deck-gate-report-2026-07-17.md#Cross-deck observations]
  — the named calibration inputs this story must NOT fix.

## Dev Agent Record

### Agent Model Used

claude-fable-5 (Claude Fable 5, Claude Code)

### Debug Log References

- Task 0 (2026-07-17): tree "dirty" only with this story's own creation artifacts
  (story file untracked + sprint-status flip to ready-for-dev) — no source changes,
  reconciled as benign, proceeded. HEAD `dfc45b2` on `feat/deck-power-assessment` ✓.
  Baseline collect: **1,299 tests** (matches 7.2's post-review count exactly).
  Import probe: all six names resolve, incl. the `TierLabel` re-export ✓.
- Construction-site re-verification against the final diff (epic-6 standing
  discipline): **7 sites, not 6** — the Dev Notes' "5 non-ok early returns" predates
  the 7.2 review patch, which added a sixth non-ok site (combo-provisioning
  `DatabaseError → error`). All 6 non-ok sites construct without `assessment`
  (default `None`, verified by `test_every_non_ok_status_keeps_assessment_none`
  covering all 4 non-ok statuses); only the ok site passes `assessment=`.
- TDD: new tests written first — collection failed on the missing imports
  (`MULTIPLAYER_VARIANCE_CAVEAT` ImportError, RED) before any model code landed.

### Completion Notes List

- **AC 1/2 — models + assembly:** five frozen Pydantic models (`AssessmentVector`,
  `DataVintage`, `Confidence`, `AssessmentFlags`, `Assessment`) declared in AD-7
  emission order; `AssessDeckPowerResult.assessment` widened to
  `Assessment | None = None` so every non-ok site is unchanged. `_build_assessment`
  is a pure field-for-field map off the `ScoredAssessment` seam — zero recomputation,
  zero I/O; the only renames are the scorer-docstring-pinned boundary pair
  (`bracket_floor` → `bracket`, `game_changers.card_names` → `flags.game_changers`).
  `flags.combos` nests `ComboRecord` verbatim (AD-11, decide-once #3);
  `schema_version` stays `"1"` (decide-once #1); `assessment.format` emitted
  (decide-once #4).
- **AC 3 — determinism:** nothing re-sorted at the edge (producer order emitted
  as-is per the CoreAssessment contract), all dimension scores int, no datetime
  anywhere in the new models. Pinned by `test_two_calls_serialize_byte_identically`
  (string equality on `model_dump_json()`, not dict equality) +
  `test_lists_are_emitted_sorted` + `test_serialized_result_embeds_no_clock`
  (also proves the ONLY timestamp-shaped content is the verbatim vintage string).
- **AC 2 — decide-once #2 landed:** absent vintage renders as `null`-valued fixed
  keys (`test_data_vintage_null_keys_when_snapshot_absent`); the meta-row-present +
  zero-variants case proves token and vintage are independent facts
  (`test_data_vintage_survives_meta_without_variants`). `export_timestamp` /
  `variant_count` deliberately not emitted.
- **AC 4/5/6 — summary:** `_build_summary` is a pure projection of the assembled
  `Assessment` + stable deck-identity inputs (decide-once #6). Bucket-split combo
  counts ("N combo variants included, M one card away" — the 7.2 review deferral;
  the word "matched" is gone from the ok summary), "Bracket N floor" phrasing
  (decide-once #5, Commander only), "cEDH candidate" phrasing (never Bracket 5),
  structural-gap tokens + Game Changer count surfaced, and
  `MULTIPLAYER_VARIANCE_CAVEAT` module `Final` appended iff
  `profile.multiplayer_variance_caveat` (first consumer of that flag). The 7.2 MCP
  assertion fragments (`/100`, `confidence `, `no degradations`, `N combo variant(s)`)
  were kept stable — zero existing summary assertions needed edits; the one test
  pinning the removed "lands in Story 7.3" sentence was rewritten to pin the
  populated block instead.
- **AC 7 — docstrings:** `server.py` tool docstring now sells the real contract
  (block shape, determinism, degradation behavior); helper module + function +
  result-class docstrings shed all "pending/provisional" wording.
- **AC 8/9 — gates + tests:** ruff check/format clean, `mypy --strict` clean
  (69 files), full suite **1,313 passed** (baseline 1,299 + 14 new, 0 regressions).
  New coverage: full-shape ok path, all-4-non-ok `assessment is None`, Commander vs
  Standard key-set parity (recursive), vintage verbatim/null/independent, byte
  determinism, sorted emission, summary projection matrix (incl. `almost_included`
  disambiguation + caveat gating), MCP-level `structuredContent["assessment"]`
  round-trip, plus 3 pure `_build_summary` branch tests (cEDH candidacy, gaps+reasons
  listing, bracket-None) for branches unreachable via cheap fixtures.
- Test seed gained two `game_changer=True` cards ("Aura Shards" < "Bolas's Citadel",
  deliberately added in reverse bytewise order) to make sorted-emission assertions
  meaningful; additive only — no existing fixture touched.
- **Not done (per story scope):** no `src/logic`/`src/data` changes, no calibration,
  no client-level byte test (7.4), no `compare_deck_power` (7.5), status enum and
  `schema_version` untouched.

### File List

- `src/mcp_server/tools/assess_deck_power.py` — modified (result models, assembly,
  summary builder, caveat constant, docstrings)
- `src/mcp_server/server.py` — modified (tool docstring only)
- `tests/integration/mcp_server/test_assess_deck_power_tool.py` — modified (14 new
  tests, 1 rewritten, 2 new seed cards, module docstring)
- `tests/integration/test_mcp_tools.py` — modified (happy-path assessment round-trip)
- `plugin/server/src/mcp_server/tools/assess_deck_power.py` — generated (pre-commit
  mirror)
- `plugin/server/src/mcp_server/server.py` — generated (pre-commit mirror)
- `_bmad-output/implementation-artifacts/7-3-assess-deck-power-result-assembly-deterministic-serialization-human-summary.md`
  — this story file
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status tracking

## Review Findings

_Code review 2026-07-17 (baseline `dfc45b2`..`15cec07`; 3 layers: Blind Hunter,
Edge Case Hunter, Acceptance Auditor). Acceptance Auditor found zero AC
violations. 3 findings survived triage (all low severity), 7 dismissed as noise._

- [x] [Review][Patch] Tighten `bracket` to `Literal[2, 3, 4] | None` (decision resolved 2026-07-17) [src/mcp_server/tools/assess_deck_power.py:226] — Structured field accepted any int; the summary renders `f", Bracket {bracket} floor"` for any non-None value (`assess_deck_power.py:636`). Core `bracket_floor` is documented `{2,3,4}`/None (Brackets 1 & 5 are intent-declared, never computed — FR18). Chosen fix: encode the FR18 invariant at the boundary so a producer regression becomes a loud ValidationError (which 7.4's determinism suite catches) instead of silent "Bracket 5 floor" prose.
- [x] [Review][Patch] Summary "one card away" clause is ungrammatical for every count except 1 [src/mcp_server/tools/assess_deck_power.py:653] — `f"{included} {included_noun} included, {almost} one card away"` pluralizes the `included` side but hardcodes a bare "one card away" for `almost`, so the common no-shortfall deck reads "0 one card away" and a multi-shortfall deck reads "2 one card away". Standard decks (combos disabled) always render "0 combo variants included, 0 one card away". AC5 leaves phrasing free (conflation is banned, and it is correctly un-conflated), so this is cosmetic on the product surface an LLM relays — but it reads wrong. Fix: pluralize/zero-handle the `almost` clause (e.g. "1 one card away" / "2 one card short" / omit when 0).
- [x] [Review][Patch] `Assessment.format` is typed `str`, not a closed `Literal`, in a "fixed closed shape" model [src/mcp_server/tools/assess_deck_power.py:222] — Every other constrained field is closed (`tier: TierLabel`, `confidence.level: ConfidenceLevel`) and the field's own docstring promises `"commander" | "standard"`; 7.5 branches on it for `format_mismatch`. `inputs.format` is always one of the two profile keys, so tightening to `Literal["commander", "standard"]` is safe and matches the model's stated intent. Low-value consistency fix.

## Change Log

- 2026-07-17: Story 7.3 implemented — `assessment` block widened to the full AD-7
  shape (5 frozen models, pure seam assembly), AD-8-deterministic serialization
  pinned at model level, summary rebuilt as a pure projection (bucket-split combo
  counts, Bracket-floor phrasing, multiplayer-variance caveat), LLM-facing
  docstrings updated. 1,313 tests green (+14), mypy --strict + ruff clean.
  Status → review.
