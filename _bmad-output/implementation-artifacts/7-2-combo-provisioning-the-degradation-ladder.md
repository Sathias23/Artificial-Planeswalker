---
baseline_commit: 5b17006
---

# Story 7.2: Combo provisioning & the degradation ladder

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the edge,
I want snapshot-backed combo provisioning with graceful degradation,
so that a missing combo snapshot or missing data lowers confidence instead of crashing or silently scoring zero.

## Acceptance Criteria

1. **Combo provisioning, gated on the profile (AD-2/AD-5).** When `profile.combos_enabled`
   is `True`, the helper reads the local snapshot through
   `ComboSnapshotRepository(session)` (Story 6.3's seam — do not modify it): availability
   via `snapshot_is_available()`, vintage via `get_metadata()`, and variants via
   `get_variants_for_names([dc.card.name for dc in mainboard])`. **Never a live fetch,
   never a write** — the assessment path stays read-only against `cards.db`. When
   `combos_enabled` is `False`, provisioning is skipped entirely (no repo reads,
   `variants=()`) and **no** `combo_data_unavailable` token is emitted — a profile choice
   is not a run-specific degradation (AD-6). Both shipped profiles are `combos_enabled=True`
   today; the gate is exercised in tests with a hand-built profile.

2. **Missing/empty snapshot degrades, probed correctly (AD-5/AD-6).** Unavailability is
   detected via `snapshot_is_available()` (meta row present AND ≥1 variant row) — **never**
   inferred from an empty `get_variants_for_names` result: a healthy snapshot with zero
   overlapping variants is a legitimate no-combos outcome (G-R2 proved this on real decks),
   not a degradation. Unavailable → `variants=()` + `combo_data_unavailable` + lowered
   confidence; scoring still proceeds. Never an exception to the client for this path.

3. **The pure core is invoked once, with frozen values (AD-2).** The helper calls
   `score(inputs.mainboard, commanders=inputs.commanders, variants=variants,
   profile=inputs.profile)` (keyword-only; param is `variants`, not `combos`) and carries
   the returned `CoreAssessment` on a new frozen seam carrier for Story 7.3, together with
   the vintage (`ComboSnapshotMeta | None`) and the assembled confidence. The edge performs
   **no matching** — `match_combos` runs inside `score()` (AD-9); the edge never calls it
   directly (one scoring path, no divergence). The empty/all-sideboard mainboard case is
   guarded by `score()`'s proven zero-safety (the 7.1 review D2 decision routed it here) —
   it returns a scored result, never crashes.

4. **Edge confidence reasons from the closed enum only (FR21/AD-6).** Reasons are assembled
   at the edge by importing the existing constants from `src.logic.assessment`
   (`CARDS_UNRESOLVED`, `COMBO_DATA_UNAVAILABLE`, `COMMANDER_UNIDENTIFIED`,
   `GAME_CHANGER_DATA_UNAVAILABLE` — never re-declared, never new tokens):
   - `cards_unresolved` when `inputs.unresolved_count > 0` (the count stays a separate
     structured fact on the seam; the token never embeds it). Structurally 0 today — see
     Dev Notes; wire it honestly, test it through the pure ladder function.
   - `combo_data_unavailable` per AC 2.
   - `game_changer_data_unavailable` when `core.game_changers.unknown_count > 0` (AD-4 —
     the core's quantity-aware signal; do not re-derive `game_changer is None` at the edge).
   - `commander_unidentified` when `inputs.commander_resolution == "unidentified"` **AND
     the resolved format is `commander`** (profile `rubric == "brackets"`). A Standard deck
     always resolves `unidentified` by construction (7.1's ladder never infers outside
     Commander) and must NOT carry a permanent degradation for a format that has no
     commanders (FR25/AD-13 scope the concern to Commander-format decks).
   `reasons[]` is emitted **sorted ascending bytewise** (AD-8); tokens never embed counts or
   phrases; nothing clock-derived exists anywhere.

5. **Categorical confidence level — decide-once mapping (FR21/AD-6).** A pure, unit-testable
   ladder function maps the assembled reasons to `ConfidenceLevel` (import from
   `src.logic.assessment`): **0 reasons → `"high"`, exactly 1 → `"medium"`, ≥2 → `"low"`.**
   This is the first edge confidence policy in the codebase (verified: no reasons→level
   mapping exists anywhere) — document it in the function docstring as hand-tuned and
   adjustable (NFR8 spirit); 7.3/7.4 pin it in the output contract.

6. **Degradation never raises, never silently zeros (NFR3).** Every degradation path returns
   a `status="ok"` scored result with lowered confidence — the 4-step error pattern from 7.1
   (`database_not_initialized` / `deck_not_found` / `DatabaseError` → `error` /
   `unsupported_format`) is unchanged. The ok-path `summary` is updated to a deterministic
   projection of the new facts (confidence level + sorted reasons + combos matched count),
   still stating that the structured assessment block lands in Story 7.3. No call-time
   clock anywhere (AD-8).

7. **Type + lint gates pass.** `mypy --strict` over `src/`, `ruff check` + `ruff format`,
   pre-commit succeeds without `--no-verify` (the `build-plugin-sync` hook re-mirrors
   `src/` → `plugin/server/`).

8. **Tests prove every path offline (no live DB, no network).** Extend
   `tests/integration/mcp_server/test_assess_deck_power_tool.py` (existing fixture stack)
   + the pure-ladder unit tests: snapshot absent → `combo_data_unavailable` + still scored;
   snapshot seeded + variants matched → combos on the core result, no token; healthy
   snapshot with zero overlap → no token; `combos_enabled=False` profile → no repo read, no
   token; Commander deck with `unidentified` resolution → `commander_unidentified`;
   Standard deck (also `unidentified` by construction) → **no** `commander_unidentified`;
   NULL `game_changer` card → `game_changer_data_unavailable`; every reason combination →
   correct level + bytewise-sorted `reasons[]`; empty-mainboard deck → scored, no crash.
   MCP-client-level: `assess_deck_power` still graceful in `test_mcp_tools.py` (existing
   tests keep passing; extend the happy-path `structuredContent` assertion to the new
   summary facts if it pins the old text).

## Tasks / Subtasks

- [ ] Task 0: Story-start state verification (standing team agreement) (AC: all)
  - [ ] `git status` — the working tree currently carries the **uncommitted 7.1 review
        patch** (`src/mcp_server/tools/assess_deck_power.py` + plugin mirror comment, story
        file + sprint-status edits). Commit it first (e.g.
        `docs: story 7.1 review findings + unresolved_count patch`) so this story starts
        from a clean tree; verify with `git status` after.
  - [ ] `uv run pytest --collect-only -q | tail -1` — confirm full-suite baseline **1,270**
        (7.1's verified count); record the actual number in Dev Agent Record.
  - [ ] Confirm imports:
        `from src.logic.assessment import CARDS_UNRESOLVED, COMBO_DATA_UNAVAILABLE, COMMANDER_UNIDENTIFIED, GAME_CHANGER_DATA_UNAVAILABLE, CONFIDENCE_REASON_TOKENS, ConfidenceLevel, CoreAssessment, score`
        and `from src.data.repositories.combo_snapshot import ComboSnapshotRepository`,
        `from src.data.schemas.combo import ComboSnapshotMeta` (all exist — verified
        2026-07-17).
  - [ ] Read `ComboSnapshotRepository` (combo_snapshot.py, ~140 lines) and the NOTE comment
        at `assess_deck_power.py:326-332` before writing any code.
- [ ] Task 1: Pure confidence ladder (TDD — test first) (AC: 4, 5)
  - [ ] New pure function in `assess_deck_power.py` (e.g.
        `_derive_confidence(*, unresolved_count, combo_data_unavailable, gc_unknown_count,
        commander_unidentified) -> tuple[ConfidenceLevel, tuple[str, ...]]`) — takes plain
        facts, returns level + bytewise-sorted reasons tuple. No I/O, no profile, no clock.
  - [ ] Unit tests for all 16 fact combinations (or a representative matrix): token
        presence/absence, sort order (`CONFIDENCE_REASON_TOKENS` is already the sorted
        order — assert against it), level mapping 0/1/≥2.
  - [ ] `cards_unresolved` is exercised here (pure inputs) — do NOT invent a live
        name-matching pipeline to make it fire end-to-end (7.1 review D1).
- [ ] Task 2: Combo provisioning (AC: 1, 2)
  - [ ] In the helper's ok path (after `ResolvedDeckInputs` is built): if
        `inputs.profile.combos_enabled` → `combo_repo = ComboSnapshotRepository(session)`;
        `available = await combo_repo.snapshot_is_available()`;
        `vintage = await combo_repo.get_metadata()` (may be `None`); variants via
        `get_variants_for_names` over mainboard card names when available, else `()`.
  - [ ] `combos_enabled=False` short-circuit: no repo construction, `variants=()`,
        `vintage=None`, no token (document the AD-6 rationale in a comment).
  - [ ] Do NOT catch `pydantic.ValidationError` from a corrupt stored row — loud by design
        (Story 6.3 contract; consistent with the 7.1 orphan-row deferral).
- [ ] Task 3: `score()` invocation + seam carrier + summary (AC: 3, 6)
  - [ ] Call `score(...)` exactly once; new frozen dataclass carrier (e.g.
        `ScoredAssessment`: `inputs: ResolvedDeckInputs`, `core: CoreAssessment`,
        `vintage: ComboSnapshotMeta | None`, `confidence_level: ConfidenceLevel`,
        `confidence_reasons: tuple[str, ...]`) — the 7.3 seam. Keep `ResolvedDeckInputs`
        untouched.
  - [ ] Update the ok-path `summary` deterministically: resolution facts + `score`/`tier`
        facts optional, but at minimum confidence level, sorted reasons (or "no
        degradations"), combos matched count, and "structured assessment pending Story
        7.3". No timestamps, no unsorted iteration anywhere.
  - [ ] Enumerate every `AssessDeckPowerResult` construction site again (epic-6 retro
        discipline) — this story must not add a new early return that forgets
        `schema_version`/`summary` (both required fields keep omissions loud).
- [ ] Task 4: Integration tests — degradation matrix (AC: 8)
  - [ ] Extend `tests/integration/mcp_server/test_assess_deck_power_tool.py`. Snapshot
        seeding: copy the `_variant`/`seeded_snapshot` pattern from
        `tests/integration/data/test_combo_snapshot_repository.py` (meta row via
        `ComboSnapshotMetaModel(...)`, variants via `ComboVariantModel` + `cards_list`
        setter + `ComboVariantPieceModel` piece rows keyed by `name_keys`).
  - [ ] Cover: absent snapshot (tables exist via `init_database`, no rows) → token +
        scored; seeded snapshot matching a deck combo → combos surface on the seam/summary,
        no token; zero-overlap healthy snapshot → no token; Commander vs Standard
        `commander_unidentified` gating; NULL-`game_changer` seed card → token;
        multi-degradation → `level="low"` + sorted reasons; empty mainboard → ok.
  - [ ] MCP-client level (`tests/integration/test_mcp_tools.py`): existing
        `assess_deck_power` tests stay green; adjust the happy-path summary assertion if it
        pinned the 7.1 provisional text.
- [ ] Task 5: Quality gates + story wrap-up (AC: 7)
  - [ ] `uv run ruff check . --fix && uv run ruff format .`; `uv run mypy src/`;
        `uv run pytest` full suite green; pre-commit (plugin mirror re-syncs
        `plugin/server/src/mcp_server/tools/assess_deck_power.py` — expected, commit it).
  - [ ] Update this story file (Dev Agent Record, File List, Change Log); status → review.
        Conventional Commit:
        `feat: assess_deck_power combo provisioning + degradation ladder (story 7.2)`.

## Dev Notes

### What this story is (and is NOT)

The **combo-provisioning + degradation slice** of the `assess_deck_power` edge (feature
Story 4.2, sprint key `7-2`): repo reads (availability / vintage / variants), the single
`score()` invocation, and the AD-6 confidence ladder (tokens + level), carried on a frozen
seam for 7.3. It does **NOT** include:

- **Result widening / deterministic serialization / human summary projection /
  `data_vintage` output block** — Story 7.3 (AD-7/AD-8). `assessment` stays `None` on the
  result; the `CoreAssessment` + vintage + confidence ride the internal seam only. The
  ok-path `summary` is refreshed with the new facts but remains provisional.
- **`compare_deck_power`** — Story 7.5.
- **Any calibration/tuning** — the G-R2 named calibration inputs (card_advantage
  saturation at 80, interaction railing 0/100, Brawl mana_efficiency floor,
  almost_included dominance, **format-blind almost_included inflation** — the last one is
  in `deferred-work.md` as a product-level item) are Epic 7 *inputs*, not this story's
  fixes. Do not touch `src/logic/assessment` scoring math, profiles, or the matcher.
- **Any change to `src/logic/` or `src/data/`** — `score()`, the matcher, the tokens, the
  level vocabulary, and the repository are all done (5.6/5.8/5.9/6.3). If a lower layer
  seems wrong, stop and surface it.
- **Making `cards_unresolved` fire live** — the count is structurally 0 today (see below);
  hardening the shared load path is a future data-layer story.

### Critical code facts (verified 2026-07-17)

- **`score()`** (`src/logic/assessment/scorer.py:109-115`):
  `score(deck_cards, *, commanders: Sequence[str], variants: Sequence[ComboRecord],
  profile: FormatProfile) -> CoreAssessment` — keyword-only, param name **`variants`**.
  Empty inputs (`variants=()`, `commanders=()`, empty deck) score without raising
  (zero-safety test exists at `test_assessment_scorer.py:353-376`).
- **`CoreAssessment`** (scorer.py:63-107) is a **frozen dataclass, not Pydantic**: `vector`,
  `for_format_score: int`, `tier`, `bracket_floor: int | None`, `cedh_candidate: bool`,
  `game_changers: GameChangerSignal`, `combos: tuple[ComboRecord, ...]` (buckets assigned,
  sorted by `spellbook_id`), `structural_gaps`, `mass_land_denial`, `extra_turn_chains`.
  **It carries NO confidence, NO reasons, NO summary, NO vintage** — the module docstring
  explicitly assigns those to the Epic-7 edge. This story writes that missing piece.
- **Confidence vocabulary** (`src/logic/assessment/aggregate.py:47-74`): the four token
  constants + `CONFIDENCE_REASON_TOKENS` (a tuple that is **already bytewise-sorted** —
  emitting reasons in constant order satisfies AD-8) + `ConfidenceLevel =
  Literal["low","medium","high"]` + `CONFIDENCE_LEVELS`. All re-exported from
  `src.logic.assessment`. **No reasons→level mapping exists anywhere — this story authors
  the first one** (AC 5).
- **Matcher** (`src/logic/assessment/combos.py:136-198`): runs **inside `score()`**;
  buckets: shortfall 0 → `included`, 1 → `almost_included`, ≥2 → dropped. When
  `variant.commander_required` and `commanders` is empty, the variant is **skipped**
  (FR25) — the core already does the "skip commander-required variants" half of AD-13;
  the edge only emits the token.
- **`ComboSnapshotRepository`** (`src/data/repositories/combo_snapshot.py`, all async,
  read-only, never raises on missing/empty tables):
  `snapshot_is_available() -> bool` (:40-60, meta row AND ≥1 variant);
  `get_metadata() -> ComboSnapshotMeta | None` (:62-77);
  `get_variants_for_names(names) -> tuple[ComboRecord, ...]` (:79-138 — expands via
  `name_keys` so DFC full names from `card.name` are matched on both full and front-face
  keys; empty `names` → `()` with no DB hit; missing tables → `()`). **May raise
  `pydantic.ValidationError` on a corrupt stored row — loud by design, do not catch.**
- **`ComboSnapshotMeta`** (`src/data/schemas/combo.py:110-131`): frozen;
  `imported_at: str`, `export_timestamp: str`, `export_version: str`,
  `variant_count: int` — ISO-8601 **strings**, stored input metadata only (AD-8-safe; this
  becomes 7.3's `data_vintage`).
- **Profiles** (`src/logic/assessment/profiles.py:132,168`): **both**
  `COMMANDER_PROFILE` and `STANDARD_PROFILE` have `combos_enabled=True`; rubric is
  `"brackets"` vs `"heuristic_only"` — use `rubric == "brackets"` (or
  `inputs.format == "commander"`, equivalent today) for the `commander_unidentified` gate.
  `multiplayer_variance_caveat` drives 7.3's summary caveat — not touched here, never a
  reason.
- **Game Changer signal**: `CoreAssessment.game_changers` is a `GameChangerSignal`
  (`dimensions.py:247-292`): `known_count`, `card_names` (sorted, True-only),
  **`unknown_count`** (quantity-aware count of `game_changer is None`). Token condition:
  `unknown_count > 0`. Never coalesce, never re-derive at the edge.
- **Current edge state** (`src/mcp_server/tools/assess_deck_power.py`, 357 lines): 5
  result construction sites; `ResolvedDeckInputs` frozen carrier already holds everything
  this story consumes (`mainboard`, `profile`, `commanders`, `commander_resolution`,
  `unresolved_count`); helper takes `session: AsyncSession` first and instantiates repos
  itself — add `ComboSnapshotRepository(session)` beside `DeckRepository(session)` (same
  session, no new connection).
- **`unresolved_count` is structurally 0 today** (NOTE at assess_deck_power.py:326-332,
  applied as the 7.1 review patch): `DeckCard.card` is a required nested field, so an
  orphan row fails validation inside the repo before the count could ever be nonzero. The
  `cards_unresolved` token is wired honestly (fires iff count > 0) and tested through the
  pure ladder — not through a live orphan fixture.
- **Live-DB reality (G-R2):** all 20 real decks predate 6.1 → zero commander flags; on the
  live central DB, `game_changers.unknown_count == 0` (backfill complete, 53 TRUE) and the
  snapshot is populated (94,962 variants, export 5.6.0). The degradation paths are
  therefore **test-fixture paths right now** — build them as first-class fixtures, don't
  expect to reproduce them against the live DB.

### Decide-once decisions this story owns (document each in code)

1. **Reasons→level mapping** (AC 5): 0 → high, 1 → medium, ≥2 → low. Simple, count-based,
   deterministic; hand-tuned and adjustable per NFR8. Alternatives (weighted per-token
   severity) deliberately rejected for v1 — no calibration data justifies asymmetry yet.
2. **`commander_unidentified` is Commander-format-only** (AC 4): 7.1's resolver returns
   `"unidentified"` for every Standard deck by construction; emitting the token there would
   permanently degrade every Standard assessment. FR25/AD-13 scope commander identity to
   Commander-format decks; the G-R2 harness scored all Standard decks with no commander
   concept at all.
3. **`combos_enabled=False` ≠ degradation** (AC 1): AD-6 restricts reasons to
   *run-specific degradations*; a profile that disables combos is configuration. Skip the
   repo reads entirely (also keeps the path cheap).
4. **Unavailability probe is `snapshot_is_available()`, not "variants == ()"** (AC 2):
   G-R2 verified a full 60-card deck legitimately fetching 0 candidates from a healthy
   94k-variant snapshot (Kotis Saboteur Tempo — probed, NOT a normalization failure).
   Conflating the two would emit false degradations on combo-inert decks.
5. **Corrupt-snapshot `ValidationError` stays loud** (Task 2): 6.3's repo contract raises
   on a corrupt stored row by design; 7.1's review already deferred the sibling
   orphan-row `ValidationError` to a data-layer story. Catching it here would hide data
   corruption behind a fake degradation token (`combo_data_unavailable` would lie).
6. **`vintage` may be `None` even when tokens say nothing** — when `combos_enabled` is
   False, or (edge case) meta row present but variants empty (`snapshot_is_available()`
   False → token emitted, but `get_metadata()` may still return the row). Carry whatever
   `get_metadata()` returned; 7.3 decides how `data_vintage` renders a `None`.

### Previous-story intelligence (7.1 + review)

- **7.1 review D2 (accepted):** empty/all-sideboard mainboard returns `status="ok"` — the
  decision text says *"7.2's `score()` will guard the empty case"*. That is why this story
  invokes `score()` (zero-safe on empty inputs) rather than adding an `empty` status. Do
  not widen the status enum.
- **7.1 review D1 (patched):** `unresolved_count` is a dead signal today — the NOTE
  comment at assess_deck_power.py:326-332 is addressed to *this story*: honest wiring,
  pure-ladder testing, no live-source invention.
- **Construction-site enumeration** (epic-6 retro discipline, applied in 7.1): 5 existing
  result construction sites; this story should not add early returns, but re-verify the
  enumeration against the final diff anyway.
- **7.1 established:** result model uses `summary` (not `message`), `SCHEMA_VERSION = "1"`,
  `_FORMAT_PROFILES` map, `CommanderResolution` Literal. Match its style (Google
  docstrings, module logger with lazy `%s` args, modern 3.12 syntax).
- **Working tree at story creation carries the uncommitted 7.1 review patch** — Task 0
  commits it before work starts (never mix it into this story's feature commit).
- **Task 0 state verification is a standing team agreement** — it has caught real traps in
  three consecutive stories (httpx decoding 6.2, baseline off-by-one 6.3, and 7.1's
  clean-import confirmations).

### Architecture compliance checklist

- **AD-2:** combos enter the core as frozen plain values (`ComboRecord` is frozen
  Pydantic; the tuple from the repo is passed through untouched); matching inside the
  core; no network/DB/clock in anything this story adds to the scoring path itself.
- **AD-5:** snapshot read-only via the repository; assessment never writes; missing/empty
  snapshot degrades as `combo_data_unavailable` (the `index_unavailable` precedent).
- **AD-6:** closed token enum imported from the core vocabulary; tokens never embed
  counts; counts live on the seam as structured fields; reasons are run-specific only; no
  clock-derived token; categorical level only (no numeric band).
- **AD-8 (respected at a distance):** reasons emitted bytewise-sorted; nothing
  clock-derived in the summary or seam; `ComboSnapshotMeta` strings come from stored
  metadata only. Full serialization discipline lands in 7.3.
- **AD-9:** edge orchestrates only (repo read → `score()` → carrier); zero new logic in
  `src/logic` / `src/data`; repositories return Pydantic.
- **AD-4 (read side):** `game_changer_data_unavailable` from the core's `unknown_count`;
  `None` never coalesced anywhere.
- **NFR3:** every degradation path returns a scored `status="ok"` result; the only raises
  reaching FastMCP remain the pre-existing loud-by-design corruption paths.
- **NFR7:** stateless; no per-session state; `format` keeps shadowing the builtin
  (domain convention).

### Testing standards summary

- pytest config in `pyproject.toml`; `asyncio_mode = "auto"` (plain `async def test_...`);
  `--strict-markers`; `tests.*` exempt from `mypy --strict` (ruff/naming still apply).
- **Pure ladder tests** may live beside the helper tests in
  `tests/integration/mcp_server/test_assess_deck_power_tool.py` (7.1 put its pure-ladder
  unit tests there) — keep the file's existing structure.
- **Snapshot seeding precedent:** `tests/integration/data/test_combo_snapshot_repository.py`
  — `_variant()` helper builds `ComboVariantModel` (+ `cards_list`/`produces_list` JSON
  setters) and `ComboVariantPieceModel` rows keyed by `name_keys(name)`; meta via
  `ComboSnapshotMetaModel(imported_at=..., export_timestamp=..., export_version=...,
  variant_count=...)`. `init_database` creates the (empty) combo tables — an
  un-seeded engine is exactly the "absent snapshot" fixture.
- **Combo fixtures:** `tests/fixtures/assessment.py::make_combo_record` for pure-side
  records; seed cards for the deck side via the existing fixture stack
  (`create_engine` → `init_database` → `create_session_factory` → seed `CardModel`s →
  `DeckRepository.create_deck` + `add_card_to_deck(..., commander=)`).
- To make a **matchable** combo end-to-end: seed two `CardModel`s whose names are the
  variant's `cards`, add both to the deck mainboard, seed the variant with the same names
  — `included` bucket; omit one for `almost_included`.
- NULL-`game_changer` fixture: seed a `CardModel` with `game_changer=None` (default) —
  the core's `unknown_count` picks it up by quantity.
- `combos_enabled=False` profile fixture: `FormatProfile` is a frozen dataclass — build the
  variant with `dataclasses.replace(STANDARD_PROFILE, combos_enabled=False)` and inject it
  by monkeypatching `_FORMAT_PROFILES` (or exercising the provisioning helper directly);
  assert no token is emitted even with an absent snapshot (that proves the gate
  short-circuits before the availability probe).
- TDD order per task: test first (RED), implement (GREEN). No live DB, no network.

### Project Structure Notes

- Modified: `src/mcp_server/tools/assess_deck_power.py` (provisioning, ladder, carrier,
  summary), `tests/integration/mcp_server/test_assess_deck_power_tool.py`,
  possibly `tests/integration/test_mcp_tools.py` (summary assertion only).
- **No new modules, no `server.py` change** (tool already registered), no `src/data` /
  `src/logic` / `scripts/` changes.
- Generated: `plugin/server/src/mcp_server/tools/assess_deck_power.py` mirror (pre-commit).
- Naming: seam carrier suggestion `ScoredAssessment` (frozen dataclass, module-private is
  fine); pure ladder `_derive_confidence`; modern 3.12 syntax; Google docstrings.
- Branch: stays on `feat/deck-power-assessment` (no master merge until Epic 7 completes).

### References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 4.2] —
  story + ACs (sprint key `7-2`); FR21 text; AD-2/AD-5/AD-6 texts; Epic 4 preamble.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-6]
  — closed token enum, "run-specific degradations only", no clock-derived reason,
  categorical level only; #AD-5 snapshot/degrade rule; #AD-4 `unknown_count` read side;
  #AD-2 frozen-values rule; flowchart (combos_enabled? → read snapshot → degrade per AD-6).
- [Source: _bmad-output/implementation-artifacts/7-1-register-the-async-tool-load-deck-resolve-format.md]
  — `ResolvedDeckInputs` seam contract; review D1 (`unresolved_count` dead signal) + D2
  ("7.2's score() will guard the empty case"); construction-site enumeration; fixture
  stack.
- [Source: _bmad-output/implementation-artifacts/pre-epic-7-real-deck-gate-report-2026-07-17.md]
  — zero-candidate-is-legitimate proof (Kotis Saboteur probe); snapshot vintage shape;
  named calibration inputs this story must NOT fix; live-DB degradation-path reality.
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#Deferred from: code review of spec-pre-epic-7-real-deck-gate]
  — format-blind almost_included inflation = product-level deferred item, out of scope.
- [Source: src/logic/assessment/scorer.py:109-115,63-107] — `score()` signature +
  `CoreAssessment` fields; docstring assigning confidence to the Epic-7 edge.
- [Source: src/logic/assessment/aggregate.py:47-74] — token constants (bytewise-sorted
  tuple), `ConfidenceLevel`; docstring: reasons→level ladder is Epic-7 edge code.
- [Source: src/logic/assessment/combos.py:136-198] — matcher buckets +
  commander_required skip when commanders empty.
- [Source: src/logic/assessment/profiles.py:132-205] — both profiles `combos_enabled=True`;
  rubric values; `multiplayer_variance_caveat` summary-only.
- [Source: src/logic/assessment/dimensions.py:247-292] — `GameChangerSignal.unknown_count`.
- [Source: src/data/repositories/combo_snapshot.py:40-138] — `snapshot_is_available` /
  `get_metadata` / `get_variants_for_names` contracts (return shapes, no exceptions for
  absence, ValidationError loud on corruption).
- [Source: src/data/schemas/combo.py:35-131] — `name_keys`, `ComboRecord` (frozen,
  `bucket=None` from repo), `ComboSnapshotMeta` string timestamps.
- [Source: src/mcp_server/tools/assess_deck_power.py:88-115,326-332] — `ResolvedDeckInputs`
  + the structurally-0 `unresolved_count` NOTE addressed to this story.
- [Source: tests/integration/data/test_combo_snapshot_repository.py:55-95] — snapshot
  seeding pattern to copy.
- [Source: tests/fixtures/assessment.py:48-65] — `make_combo_record` defaults.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List
