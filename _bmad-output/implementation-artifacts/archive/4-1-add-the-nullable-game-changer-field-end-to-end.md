---
baseline_commit: ae2025834e2a92c89082d6bd1a0901bb003640ba
---

# Story 4.1: Add the nullable `game_changer` field end-to-end

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the deck-power assessor,
I want each `Card` to expose its official WotC Game Changer status (or `None` when unknown),
so that the scorer can floor Commander Brackets on real WotC data instead of guessing.

## Acceptance Criteria

1. **`CardModel` gains the field.** `CardModel` (`src/data/models/card.py`) gains
   `game_changer: Mapped[bool | None]` via `mapped_column(...)` with dataclass init flags
   (`nullable=True, default=None, kw_only=True, init=True`), matching the existing typed-`Mapped`
   style of the sibling nullable `power` / `toughness` columns. `kw_only=True` is required — a
   defaulted field declared amid non-defaulted columns would otherwise break the dataclass init
   signature (defaulted fields must follow non-defaulted ones). [AC covers FR11 / AD-4]

2. **`Card` schema gains the field.** `Card` (`src/data/schemas/card.py`) gains
   `game_changer: bool | None = None`, with `model_config = ConfigDict(from_attributes=True)`
   preserved so `Card.model_validate(card_model)` picks it up automatically. **No
   `field_validator` / NULL-coercion is added for this field** — unlike the string/list/dict fields,
   `None` must remain `None` (see AC5). [FR11 / AD-4]

3. **`transform_scryfall_card` extracts the field.** In `transform_scryfall_card`
   (`src/data/importers/transformers.py`) the Scryfall bulk `game_changer` boolean is read and set
   on the produced `CardModel`. When the source record omits the key, the value is `None` (unknown).
   Use `card_json.get("game_changer")` (no `or` fallback, no `bool(...)` cast) so a missing key →
   `None`, `true` → `True`, `false` → `False`. [FR11 / AD-4]

4. **Round-trips through the Pydantic schema, never leaking ORM.** A repository returning cards
   surfaces `game_changer` through the Pydantic `Card` schema (never an ORM `CardModel`). This holds
   automatically via `from_attributes=True` — no repository code change is required for this story.
   [AD-4; project-context layer contract "repositories return Pydantic, never ORM"]

5. **`None` / `True` / `False` remain three distinct states everywhere.** No code path coalesces
   `None` to `False`. `None` = "unknown / not yet backfilled"; `False` = "confirmed not a Game
   Changer"; `True` = "confirmed Game Changer". This three-state contract is load-bearing: a later
   story lowers assessment confidence when any card is `None`, and the absent count must never lower
   the Commander Bracket floor. [AD-4 — "Never coalesce `None` to `False`"]

6. **Type + lint gates pass.** Type hints are complete (`bool | None`), `mypy --strict` passes over
   `src/`, and `ruff check` + `ruff format` pass. Pre-commit succeeds without `--no-verify`.

7. **Unit tests prove all three states.** `tests/unit/data/importers/test_transformers.py` gains
   coverage that a record with `"game_changer": true` → `card.game_changer is True`,
   `"game_changer": false` → `card.game_changer is False`, and an omitted key →
   `card.game_changer is None`. Assert with `is`, not `==`, to catch a `None`/`False` conflation.

## Tasks / Subtasks

- [x] **Task 1 — Add `game_changer` to the ORM model** (AC: 1, 6)
  - [x] In `src/data/models/card.py`, add `game_changer: Mapped[bool | None] = mapped_column(...)`
        immediately after the `power` / `toughness` block (the natural home for nullable,
        `kw_only` combat-adjacent metadata), using
        `mapped_column(nullable=True, default=None, kw_only=True, init=True)`.
  - [x] Add a short comment mirroring the `power`/`toughness` comment style, stating that `None`
        means "unknown / not yet backfilled" and must never be coalesced to `False` (AD-4).
  - [x] No `Boolean` import gymnastics needed — SQLAlchemy infers the column type from the
        `Mapped[bool | None]` annotation, consistent with the other `mapped_column` declarations in
        this file (they pass an explicit type like `String`/`JSON`; you may pass `Boolean` from
        `sqlalchemy` for parity, but the annotation-inferred type is acceptable and matches how the
        JSON columns are typed). Prefer passing `Boolean` explicitly to match the file's
        "explicit type first arg" convention. **(Passed `Boolean` explicitly per the convention.)**

- [x] **Task 2 — Add `game_changer` to the Pydantic schema** (AC: 2, 4, 5, 6)
  - [x] In `src/data/schemas/card.py`, add `game_changer: bool | None = None` to the `Card` model,
        placed after the `power` / `toughness` fields for parity.
  - [x] **Do NOT** add this field to any `@field_validator` and do **not** add a new coercion
        validator for it — `None` must survive as `None`.
  - [x] **Do NOT** add `game_changer` to `CardSummary` — the assessor reads full `Card` rows via
        `get_deck_with_cards` (FR1), and `CardSummary` is a deliberately bounded projection.
        Adding it there is out of scope for this story.

- [x] **Task 3 — Extract the field in the transformer** (AC: 3, 5, 6)
  - [x] In `src/data/importers/transformers.py`, after the `power` / `toughness` extraction block,
        add `game_changer = card_json.get("game_changer")` with a comment explaining that a missing
        key yields `None` (unknown) and that `None`/`True`/`False` are three distinct states (do NOT
        use `or`, which would turn a legitimate `False` into `None`, nor a truthiness cast).
  - [x] Add `game_changer=game_changer` to the `CardModel(...)` keyword construction (near the
        `power=power, toughness=toughness` args).

- [x] **Task 4 — Unit tests** (AC: 7)
  - [x] In `tests/unit/data/importers/test_transformers.py`, add tests mirroring
        `test_transform_creature_extracts_power_toughness` /
        `test_transform_noncreature_has_no_power_toughness`:
    - [x] `test_transform_card_game_changer_true` — a minimal valid card_json with
          `"game_changer": true` → `assert card.game_changer is True`.
    - [x] `test_transform_card_game_changer_false` — `"game_changer": false` →
          `assert card.game_changer is False` (this is the regression guard against `None`/`False`
          conflation — the reason `or` is forbidden).
    - [x] `test_transform_card_game_changer_missing_is_none` — key absent →
          `assert card.game_changer is None`.
  - [x] (Optional, cheap) extend `test_transform_card_with_defaults` with
        `assert card.game_changer is None`.

- [x] **Task 5 — Quality gates** (AC: 6)
  - [x] `uv run ruff check . --fix && uv run ruff format .`
  - [x] `uv run mypy src/`
  - [x] `uv run pytest tests/unit/data/importers/test_transformers.py -q`
  - [x] `uv run pre-commit run --all-files` (or let the commit hook run) — do **not** bypass hooks.

## Dev Notes

### What this story is (and is NOT)

This is the **schema/model/transformer** slice of the Game Changer feature — the field flowing
end-to-end through code. It does **NOT** include:
- The migration script (`scripts/migrate_add_game_changer.py`) or the Scryfall backfill re-import —
  that is **Story 4.2** (`4-2-migrate-and-backfill-existing-databases`).
- Any scorer read of the field — that is Epic 5 (feature Epic 2), Story 5.7.

Because there is no migration in this story, a *fresh* DB created via
`Base.metadata.create_all` (`init_database`) will include the new column automatically (the ORM
model defines it), but an *existing* on-disk `cards.db` will not have the column until Story 4.2's
migration runs. That is expected and by design.

### The one non-obvious rule: `None` ≠ `False` (AD-4)

`game_changer` is a **three-state** field: `True` (is a Game Changer), `False` (confirmed not),
`None` (unknown — the window between the migration adding the column and a Scryfall re-import
backfilling it). Everywhere it is read or transferred, these three states must stay distinct:

- Transformer: `card_json.get("game_changer")` — **not** `... or False`, `... or None`, or
  `bool(card_json.get("game_changer"))`. A `.get` with no default returns `None` for a missing key,
  which is exactly the desired "unknown" state; and it faithfully preserves an explicit `false`.
- Schema: no coercion validator. The existing `_coerce_none_to_empty_*` validators exist because
  those fields (`oracle_text`, `colors`, `legalities`, …) are declared non-optional and real
  Scryfall rows carry NULLs; `game_changer` is intentionally `bool | None`, so it needs **no**
  coercion — adding one would destroy the "unknown" signal.

Rationale (for context, not to implement here): a later story emits confidence reason
`game_changer_data_unavailable` when any deck card's `game_changer` is `None`, and the absent GC
count must not lower the Commander Bracket floor. Collapsing `None`→`False` would silently produce a
confidently-wrong Bracket on a pre-backfill DB.

### Precedent to copy — the `power` / `toughness` field (commit `77e1463`)

`power` and `toughness` are the exact structural template for `game_changer`: nullable columns added
across the same three files, using `kw_only=True, default=None, init=True` on the model and a
`... | None = None` field on the schema. Read the three touch-points before editing:

- **Model** `src/data/models/card.py:41-46` — the `power` / `toughness` `mapped_column` block with
  the "Nullable … kw_only matches printed_name" comment. Place `game_changer` right after it.
- **Schema** `src/data/schemas/card.py:33-34` — `power: str | None = None` / `toughness: str | None
  = None`. Place `game_changer: bool | None = None` after it. Note these two fields are **not** in
  any validator — same for `game_changer`.
- **Transformer** `src/data/importers/transformers.py:69-73` (extract) and `:106-129` (the
  `CardModel(...)` kwargs). `power = card_json.get("power")` is the exact pattern to mirror.

The only differences from `power`/`toughness`: the type is `bool | None` not `str | None`, and the
`kw_only`/`None`-preservation discipline is even more load-bearing (a `False` must survive).

### Construction sites — no collateral changes needed

`CardModel` is constructed at:
- `src/data/importers/transformers.py:106` — **you edit this** (Task 3).
- `src/data/database.py:179` — a health-check `test_card = CardModel(...)` insert. Because
  `game_changer` has `default=None`, this keyword-only construction absorbs the new field with **no
  change required**. (Verify it still type-checks; it will.)

`Card` is only ever built via `Model.model_validate(...)` in repositories (never field-by-field in
`src/`), so the new optional field flows through automatically. The `Card(...)` occurrences in
`src/logic/deck_validator.py` are **docstring doctest examples** (`Card(..., ...)`), not executable
construction — leave them.

### Scryfall source field

Scryfall's bulk card object carries a top-level boolean `game_changer` (added by Scryfall for the
WotC Commander Brackets initiative; `is:gamechanger` in Scryfall search). The architecture spine and
epics both specify the bulk key is exactly `game_changer` (AD-4, epics FR11). Read it verbatim as
`card_json.get("game_changer")`. The ~53-card Feb 2026 GC list is what a real backfill (Story 4.2)
will populate; this story only needs the extraction path to be correct, proven by unit tests with
synthetic `true`/`false`/absent inputs — **no live Scryfall data or re-import is required to satisfy
this story.**

### Testing standards

- pytest config lives in `pyproject.toml`; `asyncio_mode = "auto"` (no `@pytest.mark.asyncio`
  needed). These transformer tests are **synchronous** (`def test_...`) — `transform_scryfall_card`
  is a pure sync function; match the existing tests in the file.
- Test layout mirrors `src/`: this work belongs in the existing
  `tests/unit/data/importers/test_transformers.py` (fast, no I/O). No new fixture file needed —
  build inline `card_json` dicts as the sibling tests do.
- Assert state with `is True` / `is False` / `is None`, not `==`, so a `None`/`False` conflation
  fails loudly.
- `tests.*` is exempt from `mypy --strict`, but still follow ruff/naming rules.

### Project Structure Notes

- All edits stay within `src/data` (the framework-free domain core) — no `logic` / `mcp_server`
  imports, consistent with the layer contract. No new module, no new dependency.
- Modern 3.12 syntax is enforced by ruff `UP`: use `bool | None`, never `Optional[bool]`.
- Google-style docstrings + module docstrings are already present in these files; you're adding
  fields/lines, so keep the existing comment density and style. Use `%`-style lazy logging if you
  touch any log call (you shouldn't need to).
- No Alembic — but again, the migration itself is Story 4.2, not here.

### References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 1.1] — story
  definition + acceptance criteria (epic file numbers this "1.1"; the sprint tracks it as `4-1`).
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-4] —
  nullable `game_changer`, NULL = "unknown", never coalesce to `False`; touch-points named.
- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#FR11] — field origin
  (Scryfall bulk `game_changer`), read-side floor behavior.
- [Source: src/data/models/card.py:41-46] — `power`/`toughness` `mapped_column` precedent.
- [Source: src/data/schemas/card.py:33-34,63-83] — nullable-field precedent + why the coercion
  validators exist (and why `game_changer` gets none).
- [Source: src/data/importers/transformers.py:69-73,106-129] — `.get(...)`-preserve-None extraction
  precedent + the `CardModel(...)` kwargs.
- [Source: scripts/migrate_add_power_toughness.py] — the migration template for **Story 4.2** (not
  this story), noted so the dev doesn't build a migration here.
- [Source: _bmad-output/project-context.md] — SQLAlchemy 2.0 typed-`Mapped` style, repos-return-
  Pydantic contract, `mypy --strict` + ruff gates, `uv run …` command discipline.
- Precedent commit: `77e1463` "feat: show power/toughness in the read-only deck viewer".

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Claude Code dev-story workflow)

### Debug Log References

- RED confirmed before implementation: `uv run pytest -k "game_changer or defaults"` → 4 failures,
  all `AttributeError: 'CardModel' object has no attribute 'game_changer'`.
- One ruff `E501` (comment line too long) fixed by shortening the transformer comment; no logic change.
- Pre-commit `build-plugin-sync` hook re-mirrored `src/` → `plugin/server/` on first run (expected,
  since `src/` changed) and passed clean on the second run.

### Implementation Plan

Followed the `power`/`toughness` precedent (commit `77e1463`) verbatim across the three `src/data`
touch-points, with the extra `None`-preservation discipline that `game_changer` requires (a `False`
must survive, so no `or`/`bool(...)` cast and no schema coercion validator). Tests written first
(RED), then the model/schema/transformer edits (GREEN), then quality gates.

### Completion Notes List

- **AC1** — `CardModel.game_changer: Mapped[bool | None]` added after the P/T block with
  `Boolean, nullable=True, default=None, kw_only=True, init=True` (explicit `Boolean` per the file's
  "explicit type first arg" convention; added `Boolean` to the `sqlalchemy` import).
- **AC2** — `Card.game_changer: bool | None = None` added after P/T; `from_attributes=True`
  preserved. Deliberately **not** added to any `@field_validator`.
- **AC3** — transformer reads `card_json.get("game_changer")` (no `or`, no cast) and passes
  `game_changer=game_changer` into the `CardModel(...)` kwargs.
- **AC4** — round-trips via `Card.model_validate(...)` automatically (`from_attributes=True`); no
  repository change needed, confirmed by the green repo/schema unit tests.
- **AC5** — three-state `None`/`True`/`False` contract preserved end-to-end; no coalescing path added.
- **AC6** — `ruff check` + `ruff format` clean, `mypy --strict src/` → "no issues found in 54 files",
  full pre-commit green without `--no-verify`.
- **AC7** — three `is`-based state tests added plus a `game_changer is None` assertion on the
  defaults test; all pass.
- Regression: full non-integration suite **692 passed, 5 deselected** — no regressions. The
  `database.py:179` health-check `CardModel(...)` insert absorbs the defaulted field with no change,
  as predicted in Dev Notes.
- Out of scope (untouched, per story): migration script + Scryfall backfill (Story 4.2), scorer read
  (Story 5.7), `CardSummary`.

### File List

- `src/data/models/card.py` — added `Boolean` import + `game_changer` `mapped_column`.
- `src/data/schemas/card.py` — added `game_changer: bool | None = None` (no validator).
- `src/data/importers/transformers.py` — extract `game_changer` via `.get` + pass to `CardModel(...)`.
- `tests/unit/data/importers/test_transformers.py` — added `_minimal_card_json` helper + three
  game_changer state tests + `Any` import; extended `test_transform_card_with_defaults`.
- `plugin/server/src/data/{models/card.py,schemas/card.py,importers/transformers.py}` — auto-generated
  marketplace mirror, re-synced from `src/` by the `build-plugin-sync` pre-commit hook (not hand-edited).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — story status transitions.

### Change Log

- 2026-07-11 — Implemented Story 4.1: nullable three-state `game_changer` field added end-to-end
  across `CardModel`, `Card` schema, and `transform_scryfall_card`; 4 new unit tests (RED→GREEN).
  All quality gates pass; 692 tests green. Status → review.

### Review Findings

- [x] [Review][Defer] Untyped `game_changer` value could reach the `Boolean` column unchecked [src/data/importers/transformers.py:79] — deferred, pre-existing: no field in `transform_scryfall_card` has type validation beyond null-coalescing; Scryfall is a trusted, documented source for this field.
- [x] [Review][Defer] No cross-printing `game_changer` reconciliation in oracle aggregation, unlike the `games` union [src/data/importers/aggregate.py] — deferred, pre-existing: mirrors the identical, deliberate gap already present for `power`/`toughness`; out of this story's scope per Dev Notes.
- [x] [Review][Defer] `tests/fixtures/scryfall_sample.json` not updated with a realistic `game_changer` key; new tests use a hand-built minimal dict [tests/unit/data/importers/test_transformers.py] — deferred, pre-existing: story Dev Notes explicitly scope this story to synthetic-input unit tests only.
- [x] [Review][Defer] No DB round-trip test proves `game_changer=False` survives real SQLite persistence (only the in-memory `CardModel` is asserted) [tests/unit/data/importers/test_transformers.py] — deferred, pre-existing: identical gap already exists for the `power`/`toughness` precedent; no such test exists anywhere in the suite today.
- [x] [Review][Defer] No Pydantic schema-layer test (`Card.model_validate`) proving `game_changer=False` isn't coerced by a validator [tests/unit/data/schemas] — deferred, pre-existing: identical gap already exists for `power`/`toughness` in `test_schemas.py`.
- [x] [Review][Defer] Sprint-status prose doesn't note the feature isn't usable end-to-end until Story 4.2's migration ships [_bmad-output/implementation-artifacts/sprint-status.yaml] — deferred, low-stakes: already documented clearly in this story's own Dev Notes section.
