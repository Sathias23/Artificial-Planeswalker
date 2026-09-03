---
baseline_commit: fbf121c018db8aaabdcb39a03ab311424e72323a
---

# Story 6.3: Combo-snapshot repository

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the assess edge,
I want read access to the local combo snapshot with its vintage,
so that the edge can hand frozen variants to the pure core and report `data_vintage`.

## Acceptance Criteria

1. **Repository at the data layer, Pydantic out, never ORM.** A new
   `ComboSnapshotRepository` in `src/data/repositories/combo_snapshot.py` (the spine's
   seed name, AD-5/AD-9) extends `BaseRepository` (async `AsyncSession`, matching
   `CardRepository`/`DeckRepository`) and is exported from
   `src/data/repositories/__init__.py`. Every public method returns Pydantic schemas or
   plain values — no `*Model` ever crosses the boundary (layer contract).

2. **Three read methods, decide-once semantics:**
   - `async def snapshot_is_available(self) -> bool` — `True` iff the
     `combo_snapshot_meta` row exists **and** `combo_variants` holds ≥ 1 row (cheap
     EXISTS-style queries, no row materialization). This is the edge's
     `combo_data_unavailable` probe (AD-6) — mirroring
     `database.py::database_is_initialized` / `query.index_is_populated`.
   - `async def get_metadata(self) -> ComboSnapshotMeta | None` — the single meta row
     (`imported_at`, `export_timestamp`, `export_version`, `variant_count`) as a new
     **frozen** Pydantic `ComboSnapshotMeta` schema in `src/data/schemas/combo.py`
     (`from_attributes=True`, `model_validate(meta_model)`), exported from
     `src/data/schemas/__init__.py`. `None` when the row is absent. This is the
     `data_vintage` source (AD-5/AD-7).
   - `async def get_variants_for_names(self, names: Sequence[str]) -> tuple[ComboRecord, ...]`
     — the relevance-filtered variant list as `ComboRecord`s with **`bucket=None`**
     (AD-11: only the core matcher assigns buckets), ordered ascending by
     `spellbook_id` (deterministic for identical input).

3. **Relevance filter = shared `name_keys` over the piece index.** The repo expands the
   supplied card names through `src.data.schemas.combo.name_keys()` (the one
   normalization — DFC hazard) and returns exactly the variants having **at least one**
   `combo_variant_pieces.name_key` in that key set (`SELECT ... WHERE
   ComboVariantModel.spellbook_id IN (SELECT DISTINCT spellbook_id FROM
   combo_variant_pieces WHERE name_key IN :keys)` — one round-trip, uses
   `ix_combo_variant_pieces_name_key`). Documented consequences (decide-once, epic-blessed
   "at minimum by deck card names"):
   - Over-fetch is fine — the pure matcher is the exactness authority (shortfall ≥ 2
     variants are excluded there, AD-9).
   - Zero-overlap variants never surface — a 1-piece variant whose piece is absent from
     the deck cannot appear as `almost_included`. Accepted bound; document it in the
     method docstring.
   - An empty `names` input returns `()` without touching the DB (no `IN ()` SQL).

4. **Read-only.** The repository exposes **no write/commit path** — no `add`/`update`/
   `delete` methods, no `session.commit()` anywhere in the module. The snapshot tables
   are written ONLY by `scripts/import_spellbook_combos.py` (AD-5); module + class
   docstrings state this. `assess_deck_power` (Epic 7) never writes to `cards.db`.

5. **Missing/empty snapshot is absent, never an exception.** All three methods tolerate
   the tables not existing at all (a pre-6.2 `cards.db` that never ran
   `init_database`/the import script): catch `sqlalchemy.exc.OperationalError` (*no such
   table*) and return the absent value (`False` / `None` / `()`), mirroring
   `database_is_initialized`'s no-raise contract. Empty-but-existing tables likewise
   read as absent/empty. A **corrupt row** (e.g. a `bracket_tag` outside the closed
   six-token `ComboBracketTag` Literal) is the opposite case: Pydantic
   `ValidationError` propagates **loudly** — the second line of defense behind 6.2's
   import normalization; never a silent wrong Bracket floor (AD-11).

6. **No matching, no degradation decisions.** The repository performs no bucket
   assignment, no shortfall math, no commander gating (those are
   `src.logic.assessment.combos.match_combos`'s, AD-9) and emits no confidence
   tokens/levels (the edge's, AD-6 — Story 7.2). It reports facts; callers decide. It
   also applies no deck-composition policy (mainboard/sideboard filtering belongs to the
   caller — the standing 5.3/5.4/5.5 policy).

7. **Type + lint gates pass.** `mypy --strict` over `src/`, `ruff check` + `ruff
   format`, pre-commit succeeds without `--no-verify` (the `build-plugin-sync` hook
   re-mirrors `src/` → `plugin/server/`).

8. **Tests prove the read path offline (no live network, no live DB in any test).**
   Unit: `ComboSnapshotMeta` schema (frozen, `from_attributes` round-trip) extends
   `tests/unit/data/schemas/test_combo.py`. Integration
   (`tests/integration/data/test_combo_snapshot_repository.py`, in-memory engine +
   `init_database` fixture pattern from `test_deck_repository.py`, snapshot seeded via
   the ORM models): available/metadata/variants round-trip; relevance filter includes
   ≥1-piece overlap and excludes zero-overlap; DFC keys match both full-name and
   front-face; multiplicity-inclusive `cards` survive the JSON round-trip; `bucket` is
   `None` on every returned record; ordering deterministic; empty `names` → `()`;
   empty tables → absent; **missing tables** (engine without `init_database`) → absent,
   no exception; corrupt `bracket_tag` row → `ValidationError` raised.

## Tasks / Subtasks

- [x] **Task 0 — Story-start state verification** (epic-5 retro action item 4: verify,
      don't trust)
  - [x] Live DB probe (scratchpad script, `uv run python <file>`) against the central DB
        (`src.paths.database_path()`): `SELECT imported_at, export_version,
        variant_count FROM combo_snapshot_meta` and `SELECT COUNT(*) FROM
        combo_variants` / `combo_variant_pieces`. Expected from 6.2's live acceptance
        (2026-07-16): meta present, export version 5.6.0, 94,962 variants, 344,176
        piece rows. If absent, the optional live tasks below need a re-import first —
        the code tasks proceed regardless (tests are offline).
  - [x] Confirm the 6.2 contract surface is as documented: `ComboVariantModel`
        column names, `name_keys` importable from `src.data.schemas.combo`. Record
        both outputs in the Dev Agent Record.

- [x] **Task 1 — `ComboSnapshotMeta` schema** (AC: 2)
  - [x] Add frozen `ComboSnapshotMeta` to `src/data/schemas/combo.py`
        (`model_config = ConfigDict(frozen=True, from_attributes=True)`; fields
        `imported_at: str`, `export_timestamp: str`, `export_version: str`,
        `variant_count: int` — exactly the `ComboSnapshotMetaModel` columns minus the
        pinned `id`). Google-style docstring naming it the `data_vintage` source
        (AD-5/AD-7) and noting timestamps stay ISO-8601 **strings** (stored metadata
        passed through verbatim; no datetime parsing, nothing clock-derived — AD-8).
  - [x] Export from `src/data/schemas/__init__.py` (alphabetical `__all__`).

- [x] **Task 2 — Repository module** (AC: 1, 2, 3, 4, 5, 6)
  - [x] Create `src/data/repositories/combo_snapshot.py` with
        `ComboSnapshotRepository(BaseRepository)`. Module docstring: read side of AD-5
        (written only by the import script; a build prerequisite like `card_vec` — a
        fresh checkout has empty tables); no matching, no degradation decisions here.
  - [x] `snapshot_is_available`: meta-row existence + ≥1 variant row via two scalar
        queries (`select(ComboSnapshotMetaModel.id).limit(1)` /
        `select(ComboVariantModel.spellbook_id).limit(1)`); `OperationalError` → `False`.
  - [x] `get_metadata`: `session.execute(select(ComboSnapshotMetaModel))` →
        `ComboSnapshotMeta.model_validate(model)` or `None`; `OperationalError` → `None`.
  - [x] `get_variants_for_names`: guard `if not names: return ()`; build
        `keys = sorted({key for name in names for key in name_keys(name)})`; the AC-3
        IN-subquery `.order_by(ComboVariantModel.spellbook_id)`; construct each record
        via **`ComboRecord.model_validate({...})` with a plain dict** —
        `{"spellbook_id": row.spellbook_id, "cards": tuple(row.cards_list),
        "commander_required": row.commander_required, "bracket_tag": row.bracket_tag,
        "produces": tuple(row.produces_list), "popularity": row.popularity}` — dict-form
        validation keeps `mypy --strict` happy (`row.bracket_tag` is `str`, the field is
        a `Literal`; direct kwargs would need a cast) while Pydantic enforces the closed
        enum at runtime (AC 5). Leave `bucket` unset (defaults `None`); read
        `cards`/`produces` ONLY through the `*_list` accessors (JSON-in-Text rule).
        `OperationalError` → `()`.
  - [x] Export `ComboSnapshotRepository` from `src/data/repositories/__init__.py`.

- [x] **Task 3 — Tests (RED first, per TDD discipline)** (AC: 8)
  - [x] Extend `tests/unit/data/schemas/test_combo.py`: `ComboSnapshotMeta` frozen
        (assignment raises), `model_validate` from a `ComboSnapshotMetaModel` instance
        round-trips all four fields.
  - [x] New `tests/integration/data/test_combo_snapshot_repository.py` (fixtures:
        `in_memory_engine` + `session` copied from `test_deck_repository.py`; a
        `seeded_snapshot` fixture inserting `ComboVariantModel` rows via the `*_list`
        setters + `ComboVariantPieceModel` rows built with `name_keys()` + the meta
        row — seed through the models directly; the importer pipeline is already
        e2e-tested in 6.2):
    - [x] availability: seeded → `True`; init'd-but-empty DB → `False`.
    - [x] metadata: seeded values round-trip exactly; empty → `None`.
    - [x] variants: overlapping name returns the record with `bucket is None`,
          multiplicity-inclusive `cards` (seed a variant whose stored list repeats a
          name, e.g. `["Basalt Monolith", "Basalt Monolith"]` — the duplicate must
          survive the JSON round-trip into the tuple), sorted-tuple normalization,
          `popularity` preserved; zero-overlap variant NOT returned; result ordered by
          `spellbook_id`.
    - [x] DFC: a deck name `"Alive // Well"` matches a variant piece indexed under its
          front face, and a front-face-only deck name matches a DFC piece's front-face
          key row (both directions through `name_keys`).
    - [x] empty `names` → `()` (and no SQL error).
    - [x] missing tables: `create_engine("sqlite+aiosqlite:///:memory:")` **without**
          `init_database` → all three methods return absent values, no exception.
    - [x] corrupt row: seed `bracket_tag="BOGUS"` directly; `get_variants_for_names`
          raises `ValidationError` (loud, AC 5).
    - [x] plain `async def test_...` (asyncio_mode auto); integration-marker convention
          per the sibling files in `tests/integration/data/`.

- [x] **Task 4 — Quality gates** (AC: 7)
  - [x] `uv run ruff check . --fix && uv run ruff format .`
  - [x] `uv run mypy src/`
  - [x] `uv run pytest -m "not integration"`, the new integration file, then the full
        suite — baseline at story start: **1,219 passed / 0 failed / 0 skipped** (story
        6.2 close). Anything below is a regression you introduced.
  - [x] Commit normally (`build-plugin-sync` mirrors `src/` → `plugin/server/src/`;
        never hand-edit the mirror). Conventional Commit:
        `feat: combo-snapshot repository (story 6.3)`.

- [x] **Task 5 (OPTIONAL, recommended) — Benchmark re-run with real snapshot data**
      (epic-5 retro action item 8: "after 6.2/6.3 land, re-run the benchmark swapping
      5.9's hand-built cEDH combo variants for real snapshot data")
  - [x] Throwaway harness in the scratchpad (NOT committed): open the central DB, use
        `ComboSnapshotRepository.get_variants_for_names` with each cEDH benchmark
        deck's card names, feed the returned records through `match_combos` + the
        benchmark's scoring path in place of the hand-built fixture variants; compare
        Bracket floors / `cedh_candidate` flags against the benchmark expectations
        (note: candidacy also depends on `CEDH_TUTOR_MIN=3`, so a delta is not
        automatically a bug — record and report).
  - [x] Record outcomes in the Dev Agent Record. Divergences feed the epic-6 retro /
        Epic 7 tuning; do NOT retune weights inside this story.

## Dev Notes

### What this story is (and is NOT)

The **read half** of the local combo snapshot (feature Story 3.3, sprint key `6-3`,
AD-5): one new schema, one new repository module, exports, tests. It does NOT include:

- **Matching** — `match_combos` (5.6) is done and frozen; the repo returns `bucket=None`
  records and never calls it. Zero edits to `src/logic/`.
- **Degradation policy** — `combo_data_unavailable` is an Epic 7 (Story 7.2) edge
  decision. The repo only supplies the probe (`snapshot_is_available`) the edge will
  consult. Do NOT define or emit any confidence token here.
- **Edge/tool work** — no MCP tool registration, no `server.py` changes, nothing in
  `src/mcp_server/`. `assess_deck_power` arrives in Epic 7.
- **Import changes** — `src/data/importers/spellbook*.py`, the models in
  `src/data/models/combo.py`, and `scripts/import_spellbook_combos.py` are 6.2's,
  reviewed and done. Read-only consumers here; if a model column seems wrong, stop and
  surface it rather than patching it silently.

This is deliberately a small story — the last of Epic 6. The value is the clean seam:
Epic 7's Story 7.2 ("read variants + vintage from the combo-snapshot repository (Story
3.3) and pass them, with the resolved commanders, into the pure core as frozen values")
consumes exactly these three methods.

### The consumer contract (design the API against this)

Epic 7's edge flow (epics Story 4.2 / spine AD-2): read variants + vintage → pass into
pure `score(cards, commanders, combos, profile)` as **frozen plain values** → core
matcher assigns buckets. Concretely:

- `match_combos(deck_cards, commanders=..., variants=<your output>)` takes
  `Sequence[ComboRecord]` with `bucket=None` and compares `piece.lower()` against deck
  `name_keys` (`src/logic/assessment/combos.py:136-198`). Your relevance filter must
  never exclude a variant the matcher could bucket: matcher-includable variants have at
  most one missing piece, so every one (except the documented zero-overlap 1-piece case)
  shares ≥ 1 name with the deck — the AC-3 filter is safe. Over-fetch is harmless.
- `ComboSnapshotMeta` feeds `data_vintage` (combo snapshot `imported_at` + export
  version — AD-7). Keep the fields verbatim strings; Epic 7 serializes them untouched.
- Commander names are deck cards (6.1 flags them on `deck_cards`), so their keys are
  already in the deck-name key set — no separate commander parameter on the repo.

### Existing code you MUST read before implementing

- [src/data/models/combo.py](src/data/models/combo.py) — the three tables 6.2 built.
  Current state: `ComboVariantModel` (PK `spellbook_id`; `cards`/`produces` are
  JSON-in-Text with `cards_list`/`produces_list` accessors — never touch the raw
  columns), `ComboVariantPieceModel` (composite PK `(spellbook_id, name_key)`, index
  `ix_combo_variant_pieces_name_key`), `ComboSnapshotMetaModel` (single row, `id=1`
  CHECK). This story changes nothing here; it only reads.
- [src/data/schemas/combo.py](src/data/schemas/combo.py) — `ComboRecord` (frozen;
  `cards` min_length=1; sorted-tuple validator; `bucket: ComboBucket | None = None`),
  the closed `ComboBracketTag` Literal, and `name_keys()` (relocated here by 6.2
  precisely so this layer can use it). You ADD `ComboSnapshotMeta` beside them.
- [src/data/repositories/base.py](src/data/repositories/base.py) +
  [src/data/repositories/card.py](src/data/repositories/card.py) /
  [src/data/repositories/deck.py](src/data/repositories/deck.py) — the repository
  pattern to match: `BaseRepository.__init__(session)`, async methods, SQLAlchemy 2.0
  `select()`, exits via `Schema.model_validate(model)` (deck.py:547
  `get_deck_with_cards` is the canonical example).
- [src/logic/assessment/combos.py](src/logic/assessment/combos.py) — the matcher you
  feed (read `match_combos` + `_availability` to internalize the name-key semantics;
  do not modify).
- [src/data/database.py](src/data/database.py) — `database_is_initialized` (~line 126):
  the no-raise absent-table precedent your `OperationalError` handling mirrors; also the
  model side-effect import block (already registers the combo models — nothing to add).
- [tests/integration/data/test_deck_repository.py](tests/integration/data/test_deck_repository.py)
  — the `in_memory_engine`/`session`/repo fixture stack to copy.
- [tests/unit/data/schemas/test_combo.py](tests/unit/data/schemas/test_combo.py) — where
  `ComboRecord`/`name_keys` tests live; extend, don't fork.

### Relevance-filter design notes (decide-once, documented)

- **Key expansion happens in the repo**, with the SAME `name_keys()` the importer used
  to build the index — a DFC deck card `"Alive // Well"` yields keys
  `{"alive // well", "alive"}`, and a DFC *piece* was indexed under both of its keys, so
  full-name↔front-face matches work in both directions. Re-implementing the
  normalization is the exact 5.3/5.6/5.9 hazard 6.2 relocated the function to prevent.
- **Scale/limits:** a 100-card Commander deck yields ≤ ~200 keys — far under SQLite's
  parameter limit; the piece index (~344k rows live) resolves the `IN` via
  `ix_combo_variant_pieces_name_key`. Staple-heavy decks may pull thousands of candidate
  variants; that is fine (all local, matcher filters; NFR4). Do NOT add a
  count-based `HAVING matched >= pieces - 1` tightening: DFC pieces hold two index rows,
  so row-counting can wrongly exclude a true `almost_included` variant with one missing
  DFC piece. Simple ≥1-overlap is the correct, safe filter.
- **Determinism:** sort the key set before binding (stable SQL text) and `ORDER BY
  spellbook_id` (stable results). The matcher re-sorts its own output, but the repo's
  contract is deterministic anyway (AD-8 spirit).

### mypy trap (known, decided)

`ComboVariantModel.bracket_tag` is `Mapped[str]`; `ComboRecord.bracket_tag` is a
`Literal`. Direct kwargs (`ComboRecord(bracket_tag=row.bracket_tag, ...)`) fails
`mypy --strict`. Use **`ComboRecord.model_validate({...dict...})`** — mypy-clean, and
Pydantic's runtime Literal check is exactly the corrupt-row failure mode AC 5 wants
(loud `ValidationError`, never a silent wrong floor). Do not `cast()` — that would
silence the type checker AND skip nothing at runtime, but loses the documented intent.

### Previous-story intelligence (6.2 + epic-5 retro)

- **6.2 is done and reviewed** (all 9 ACs, 6 Low review patches applied; full suite
  1,219 green). Live central DB carries a real snapshot: 94,962 variants / 344,176
  piece rows / meta `export_version=5.6.0`, `export_timestamp=2026-07-16T07:28:23Z`.
  Task 0 re-verifies rather than trusts (retro item 4).
- **Layer contract is the point of this story**: 6.2's model docstrings already promise
  "Story 6.3's repository treats empty as absent (`combo_data_unavailable`)" and
  "read-only everywhere else". Honor both exactly.
- **6.1's review lesson** (a flag silently dropped in a third constructor): enumerate
  every construction site of what you touch. Here: `ComboRecord` is constructed in
  6.2's normalizer, 5.6's test factory, and now your repo — three sites; keep field
  lists complete (Pydantic's required fields make an omission loud, but `popularity`
  and `bucket` have defaults — assert `popularity` round-trips in tests).
- **JSON-in-Text discipline** (project context): read `cards`/`produces` only via
  `cards_list`/`produces_list`. Raw-column access on a NULL column returns `None` and
  json-decodes to `[]` via the accessor — the accessor already handles it.
- **Plugin mirror:** expect `plugin/server/src/data/...` diffs after commit (generated
  by the pre-commit hook). Tests and scripts are not mirrored.

### Architecture compliance checklist

- **AD-5:** repo in `src/data/repositories`, returns Pydantic (never ORM), exposes
  variants + metadata row, performs no matching; snapshot written only by the import
  script; missing/empty snapshot reads as absent (build-prerequisite precedent:
  `card_vec` / `index_unavailable`).
- **AD-6 (respected at a distance):** the repo makes no degradation decision and emits
  no token — it returns absent values the edge (7.2) maps to `combo_data_unavailable`.
- **AD-9:** data-layer placement; matching stays in `src/logic/assessment/combos.py`;
  nothing here is imported by `src/logic`.
- **AD-11:** output is the canonical `ComboRecord`, `bucket=None`, derived fields never
  stored/computed here; the closed-enum Literal validates on the way out.
- **AD-2/AD-8 (respected at a distance):** no clock anywhere in this story;
  `imported_at`/`export_timestamp` are pass-through stored strings.
- **Async rule:** `src/data` is async — all repo methods `async def` on
  `AsyncSession`, matching every sibling repository (the "MCP tools are sync" rule
  applies to the legacy relational tools, not repositories; the Epic 7 assess tools are
  async per AD-1).
- **Layer contract:** `src/data` imports nothing from `src/logic` (that is why
  `name_keys` lives in the schema layer).

### Testing standards summary

- pytest config in `pyproject.toml`; `asyncio_mode = "auto"` (plain `async def
  test_...`, no marker); `--strict-markers`; integration files follow the
  `tests/integration/data/` sibling conventions.
- Layout mirrors `src/`: schema unit tests extend `tests/unit/data/schemas/test_combo.py`;
  the repo integration tests go in `tests/integration/data/test_combo_snapshot_repository.py`.
- In-memory SQLite via `create_engine("sqlite+aiosqlite:///:memory:")` +
  `init_database(engine)` (the `test_deck_repository.py` fixture stack) — no tmp files
  needed, no live DB, no network.
- `tests.*` exempt from `mypy --strict`; ruff/naming still apply.
- Full-suite baseline at story start: **1,219 passed / 0 failed / 0 skipped**.

### Project Structure Notes

- New files: `src/data/repositories/combo_snapshot.py`,
  `tests/integration/data/test_combo_snapshot_repository.py`.
- Modified: `src/data/schemas/combo.py` (+`ComboSnapshotMeta`),
  `src/data/schemas/__init__.py`, `src/data/repositories/__init__.py`,
  `tests/unit/data/schemas/test_combo.py`.
- Naming: class `ComboSnapshotRepository`; schema `ComboSnapshotMeta` (unsuffixed
  Pydantic counterpart convention); modern 3.12 syntax (`X | None`, built-in generics);
  Google-style docstrings + module docstring; module `logger` only if logging is needed
  (probably not — repositories don't log).
- Branch: stays on `feat/deck-power-assessment` (no master merge until Epic 7 —
  epic-5 retro "experimental" release decision). Conventional Commit:
  `feat: combo-snapshot repository (story 6.3)`.
- After this story: Epic 6 code is complete → epic-6 retrospective is `optional` in
  sprint-status; the epic-5 retro benchmark re-run (Task 5) is the recommended closer.

### References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 3.3] —
  story + ACs (epic file numbers this "3.3"; sprint tracks it as `6-3`); AD-5/AD-6/AD-9/
  AD-11 texts; FR13/FR14 context.
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-5]
  — repo returns Pydantic, exposes variants + metadata, performs no matching; #AD-6
  degradation is the edge's; #AD-9 layer placement; #AD-11 one canonical record.
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-07-12.md#P2] —
  bulk-snapshot re-scope: assess is read-only; missing table → `combo_data_unavailable`
  (card_vec precedent); metadata row carries vintage.
- [Source: _bmad-output/implementation-artifacts/6-2-spellbook-bulk-combo-snapshot-import.md]
  — the tables/importer this story reads; live-acceptance numbers for Task 0; the
  "treats empty as absent" contract; plugin-mirror + baseline facts.
- [Source: _bmad-output/implementation-artifacts/epic-5-retro-2026-07-15.md#Next-Epic Readiness]
  — "6.3 returns Pydantic records with `bucket=None` (only the core matcher sets
  bucket)"; action items 4 (Task 0) and 8 (Task 5).
- [Source: src/data/models/combo.py] — `ComboVariantModel` / `ComboVariantPieceModel` /
  `ComboSnapshotMetaModel` (read-only here).
- [Source: src/data/schemas/combo.py] — `ComboRecord`, `ComboBracketTag`, `name_keys`;
  where `ComboSnapshotMeta` is added.
- [Source: src/logic/assessment/combos.py:136-198] — `match_combos`, the consumer whose
  semantics bound the relevance filter.
- [Source: src/data/repositories/deck.py:547-576] — `get_deck_with_cards`, the
  canonical Pydantic-exit repository method.
- [Source: src/data/database.py:126-138] — `database_is_initialized`, the no-raise
  missing-table precedent.
- [Source: tests/integration/data/test_deck_repository.py] — fixture stack to copy;
  [Source: tests/unit/data/schemas/test_combo.py] — schema test home to extend.

## Dev Agent Record

### Agent Model Used

claude-fable-5 (Claude Fable 5) via Claude Code

### Debug Log References

- **Task 0 live DB probe** (2026-07-16, scratchpad `probe_snapshot.py` against
  `src.paths.database_path()` = `%LOCALAPPDATA%\artificial-planeswalker\cards.db`):
  meta row `('2026-07-16T09:07:00.910971+00:00', '2026-07-16T07:28:23.230742+00:00',
  '5.6.0', 94962)`; `combo_variants` = 94,962; `combo_variant_pieces` = 344,176 —
  exactly 6.2's live-acceptance numbers. Contract surface confirmed by reading
  `src/data/models/combo.py` (columns as documented, `cards_list`/`produces_list`
  accessors present) and `src/data/schemas/combo.py` (`name_keys` importable).
- **Baseline discrepancy resolved**: documented baseline was 1,219, but `git stash` +
  `pytest --collect-only` at baseline collects **1,220** — the 6.2 close note was off
  by one. This story adds 19 tests (2 unit + 17 integration); full suite now
  **1,239 passed / 0 failed / 0 skipped**, delta accounts exactly.

### Completion Notes List

- TDD order held per task: unit test for `ComboSnapshotMeta` written first (RED:
  ImportError), schema added (GREEN); integration test file written next (RED: module
  missing), repository implemented (GREEN, 23/23 on the two touched files).
- `ComboSnapshotMeta` (frozen, `from_attributes=True`) added beside `ComboRecord`;
  timestamps kept as verbatim ISO-8601 strings (AD-8 — nothing clock-derived).
- `ComboSnapshotRepository(BaseRepository)`: three async read methods, no
  write/commit path anywhere in the module. `snapshot_is_available` uses two
  `.limit(1)` scalar probes; `get_variants_for_names` guards empty input, expands via
  the shared `name_keys()`, one round-trip IN-subquery over
  `ix_combo_variant_pieces_name_key`, `ORDER BY spellbook_id`, exits via
  `ComboRecord.model_validate({dict})` (the documented mypy-strict-clean form that
  keeps Pydantic's runtime Literal check live — corrupt `bracket_tag` raises
  `ValidationError` loudly, verified by test). `OperationalError` → absent value on
  all three methods (missing-tables tests run on an engine without `init_database`).
- Quality gates: `ruff check` + `ruff format` clean, `mypy --strict src/` clean
  (68 files), unit suite 1,199 passed / 40 deselected, full suite 1,239 passed
  (0 failed / 0 skipped). Pre-commit (incl. `build-plugin-sync` mirror) ran on commit.
- **Task 5 benchmark re-run with REAL snapshot data** (scratchpad
  `benchmark_real_snapshot.py`, not committed): all 6 Commander benchmark entries meet
  expectations with real variants swapped in for the 5.9 hand-built fixtures — **zero
  divergences**, no retuning needed. Per-entry (real: floor/cedh/#candidates/
  #included/#almost): prosper 2/False/5052/0/45; talrand 2/False/1663/0/17; wilhelt
  3/False/1109/1/44 (floor 3 also in fixture run — within [2,3] tolerance);
  atraxa 3/False/2233/0/19; tymna-thrasios 4/True/2210/3/91; kinnan
  4/True/5329/17/348. Over-fetch scale (1.1k–5.3k candidates) confirmed harmless —
  matcher trims to single/double digits. Feeds the epic-6 retro; no weight changes
  made (per story instruction).

### File List

- `src/data/schemas/combo.py` (modified — added `ComboSnapshotMeta`)
- `src/data/schemas/__init__.py` (modified — export)
- `src/data/repositories/combo_snapshot.py` (new)
- `src/data/repositories/__init__.py` (modified — export)
- `tests/unit/data/schemas/test_combo.py` (modified — `TestComboSnapshotMeta`)
- `tests/integration/data/test_combo_snapshot_repository.py` (new)
- `plugin/server/src/data/schemas/combo.py` (generated mirror)
- `plugin/server/src/data/schemas/__init__.py` (generated mirror)
- `plugin/server/src/data/repositories/combo_snapshot.py` (generated mirror)
- `plugin/server/src/data/repositories/__init__.py` (generated mirror)

## Change Log

- 2026-07-16: Story 6.3 implemented — `ComboSnapshotMeta` schema, read-only
  `ComboSnapshotRepository` (availability probe, vintage metadata, name-key relevance
  filter), 19 new tests (full suite 1,239 green), optional benchmark re-run with real
  snapshot data passed with zero divergences. Status → review.
