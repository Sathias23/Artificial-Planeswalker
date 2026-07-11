---
baseline_commit: eb405c90881874415b1d0df7a6c0795169450404
---

# Story 4.2: Migrate and backfill existing databases

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the operator maintaining a live `cards.db`,
I want an idempotent migration plus a documented re-import path that populates `game_changer`,
so that decks assessed against my existing snapshot get real Game Changer data instead of a
permanent "unknown".

## Acceptance Criteria

1. **New migration script adds the column additively (no Alembic).** A new
   `scripts/migrate_add_game_changer.py` adds the nullable `game_changer` column to the existing
   `cards` table via a raw `ALTER TABLE cards ADD COLUMN game_changer BOOLEAN NULL`, mirroring
   `scripts/migrate_add_power_toughness.py` structurally (same `PRAGMA table_info(cards)` guard,
   same `create_engine()` / `create_session_factory()` wiring, same logging + `sys.exit(1)`-on-error
   shape). No Alembic. [AC covers epics Story 1.2 / AD-4 / project-context "Schema changes: no
   Alembic — migrations are hand-written scripts in `scripts/`"]

2. **Existing rows are left `NULL` (unknown) until backfilled.** The migration only performs the
   additive `ALTER TABLE`; it does **not** write any values into `game_changer`. Every pre-existing
   row reads back `game_changer IS NULL` immediately after the migration. `NULL` = "unknown / not
   yet backfilled" — never `False` (AD-4). [AD-4; epics Story 1.2]

3. **Re-running the script is a safe no-op (idempotent).** Detects the column already exists via
   `PRAGMA table_info(cards)` and logs a "already exists" message without attempting a second
   `ALTER TABLE` (a duplicate `ADD COLUMN` would raise `OperationalError: duplicate column name`).
   Running the script twice in a row exits 0 both times and leaves the schema unchanged. [epics
   Story 1.2]

4. **The migration does NOT auto-trigger the re-import.** The heavy Scryfall re-import is a
   separate, deliberate, operator-invoked step. The migration script must not import or call
   `import_scryfall_bulk_data` / shell out to `import_scryfall_data.py`. Its docstring documents the
   explicit backfill command the operator runs next. [epics Story 1.2; project-context "The one-time
   Scryfall import is heavy (~60k cards) … don't re-import casually"]

5. **The documented re-import backfills `game_changer` for the whole corpus.** After the migration,
   running the Scryfall re-import populates `game_changer` from the bulk data for every card
   (`transform_scryfall_card` already extracts it — Story 4.1). The docstring names the exact
   command (see Dev Notes: `--type oracle_cards` is the lighter, sufficient backfill because
   `game_changer` is an oracle-level property). [epics Story 1.2; FR11]

6. **Spot-check confirms real data flows back.** After a backfill re-import, a spot-check confirms
   the three states are populated: at least one known Game Changer reads back `True`, a clearly
   non-GC common reads `False`, and the count of `game_changer IS TRUE` rows is in the right
   ballpark (~50 for the Feb 2026 `is:gamechanger` list, not 0 and not the whole corpus). Provide the
   verification query in the completion notes; do not hardcode a brittle card-name list in committed
   code. [epics Story 1.2]

7. **Quality gates pass.** `ruff check scripts/migrate_add_game_changer.py` and `ruff format` are
   clean (the new script matches the line-length/style of the sibling `migrate_*.py` scripts).
   Pre-commit succeeds without `--no-verify`. **Note:** `mypy --strict` runs over `^src/` only, so
   `scripts/` is not type-checked by the gate — but still write complete type hints (`-> None`) to
   match the precedent scripts. [project-context Code Quality rules]

## Tasks / Subtasks

- [x] **Task 1 — Author `scripts/migrate_add_game_changer.py`** (AC: 1, 2, 3, 7)
  - [x] Copy `scripts/migrate_add_power_toughness.py` as the template — same imports
        (`asyncio`, `logging`, `sys`, `from sqlalchemy import text`,
        `from src.data.database import create_engine, create_session_factory`), same
        `logging.basicConfig(level=logging.INFO)` + module `logger`, same `async def migrate()`
        skeleton and `if __name__ == "__main__": asyncio.run(migrate())`.
  - [x] Set the single new column: `_NEW_COLUMN = "game_changer"` (or reuse the P/T `_NEW_COLUMNS`
        tuple pattern with one entry — either is fine; a single scalar reads cleaner here).
  - [x] Guard with `PRAGMA table_info(cards)` → build `existing = {col[1] for col in ...}`; if
        `game_changer in existing`, log `"✓ game_changer column already exists in cards table"` and
        return (AC3 idempotency). Otherwise run
        `ALTER TABLE cards ADD COLUMN game_changer BOOLEAN NULL`, `await session.commit()`, log
        success. **Column type is `BOOLEAN`** (not `VARCHAR` — the P/T columns were strings; this is
        a `bool | None` column declared with SQLAlchemy `Boolean`, so the on-disk affinity matches
        `Boolean` and round-trips 0/1/NULL correctly).
  - [x] Do **not** UPDATE / backfill any values — the `ALTER` alone satisfies AC2; rows stay NULL.
  - [x] Keep the post-migration schema dump (`PRAGMA table_info(cards)` → log each column) and the
        `try/except → logger.error + rollback + sys.exit(1)` + `finally: await engine.dispose()`
        exactly as the precedent does.
  - [x] Write a module docstring in the precedent's style: one-line purpose, "Idempotent: skips the
        column if it already exists", the `Run with: uv run python scripts/migrate_add_game_changer.py`
        line, **and** the explicit backfill note (Task 2 wording). Mention `None`/`True`/`False` are
        three distinct states and NULL is the expected interim until backfill (AD-4).

- [x] **Task 2 — Document (do NOT execute) the backfill re-import** (AC: 4, 5)
  - [x] In the docstring, state that after the migration the operator backfills by explicitly
        running the Scryfall re-import, and give the command
        `uv run python scripts/import_scryfall_data.py --type oracle_cards`
        (oracle-level, ~lighter than `default_cards`; `game_changer` is a per-oracle-identity
        property so `oracle_cards` is sufficient — mirrors the P/T migration docstring's
        `--type oracle_cards` guidance).
  - [x] Explicitly note the migration does not run this for the operator (AC4) — it is a heavy,
        deliberate step per the project's "don't re-import casually" rule.
  - [x] Do **not** add any code path that shells out to or imports the importer.

- [x] **Task 3 — Manual verification (no automated test file)** (AC: 3, 6)
  - [x] There is **no** unit/integration test for this story — the sibling `migrate_*.py` scripts
        have none (`grep -rln migrate tests/` → empty) and migrations are exercised operationally.
        Do not invent a test harness; the acceptance signal is the manual smoke below, recorded in
        Completion Notes.
  - [x] **Idempotency smoke (AC3):** against a scratch DB that predates the column
        (e.g. a copy of `cards.db`, or `--db-path`-style throwaway), run the migration twice;
        confirm run 1 adds the column and run 2 logs "already exists" — both exit 0.
  - [x] **NULL-interim smoke (AC2):** immediately after the first migration run,
        `SELECT count(*) FROM cards WHERE game_changer IS NULL` equals the row count and
        `... IS NOT NULL` equals 0.
  - [x] **Backfill spot-check (AC6)** — optional locally (heavy); documented the exact queries in
        Completion Notes so the operator can run them post-import:
        `SELECT count(*) FROM cards WHERE game_changer = 1;` (expect ~50, not 0),
        `SELECT name FROM cards WHERE game_changer = 1 ORDER BY name;` (eyeball for known GCs), and
        `SELECT game_changer FROM cards WHERE name = '<a vanilla common>';` (expect 0/`False`).

- [x] **Task 4 — Quality gates** (AC: 7)
  - [x] `uv run ruff check scripts/migrate_add_game_changer.py --fix && uv run ruff format .`
  - [x] `uv run pre-commit run --all-files` (or let the commit hook run) — do **not** bypass hooks.
        The `build-plugin-sync` hook will **not** fire for this change: its `files:` scope is
        `^(src/|.claude/skills/(…)/|pyproject.toml|uv.lock|README.md|LICENSE|NOTICE|scripts/build_plugin.py)`
        — a new `scripts/migrate_*.py` is out of scope, so there is **no** plugin mirror to re-sync
        this story (unlike Story 4.1, which touched `src/`).

## Dev Notes

### What this story is (and is NOT)

This is the **operational migration + backfill** slice of the Game Changer feature. Story 4.1
already landed the field end-to-end in code (`CardModel`, `Card` schema, `transform_scryfall_card`)
and it is verified by unit tests. This story delivers the **schema migration for existing on-disk
databases** and the **documented re-import** that populates real values.

It does **NOT** include:
- Any change to `src/` — the model/schema/transformer are done (Story 4.1). This story adds exactly
  **one new file**: `scripts/migrate_add_game_changer.py`.
- Any scorer read of the field — that is Epic 5 (feature Epic 2), Story 5.7
  (`5-7-dimension-vector-commander-bracket-floor-cedh-candidacy`).
- The combo-cache WAL migration — that is a *different* migration (Story 3.3 / epic-6, AD-5).
  **This game_changer migration does not need to touch `PRAGMA journal_mode`.** Do not conflate the
  two; the WAL requirement in AD-5 is scoped to the combo-cache table, not to `cards`.

### Why this exists — the pre-backfill window (AD-4)

`Base.metadata.create_all` (in `init_database`) already creates the `game_changer` column for a
**fresh** DB because Story 4.1 added it to the ORM model. But `create_all` **never alters existing
tables** — an on-disk `cards.db` created before Story 4.1 has no `game_changer` column, and reads
would fail. This migration is the additive `ALTER TABLE` that closes that gap for live databases.
The interim state (column present, all values `NULL`) is **expected and correct**: NULL = "unknown /
not yet backfilled", and a later assessment story degrades confidence (`game_changer_data_unavailable`)
rather than lowering the Bracket floor on absent data. **Never coalesce `None` to `False`** — that
would produce a confidently-wrong Bracket on a pre-backfill DB (AD-4's stated failure mode).

### Precedent to copy — `scripts/migrate_add_power_toughness.py`

This is the **near-exact template**. Read it first. The only substantive differences:

| Aspect | `power`/`toughness` precedent | `game_changer` (this story) |
|---|---|---|
| Columns added | two (`power`, `toughness`) | one (`game_changer`) |
| Column type in `ALTER` | `VARCHAR NULL` | **`BOOLEAN NULL`** |
| Backfill re-import type | `--type oracle_cards` | `--type oracle_cards` (same) |
| Idempotency guard | `PRAGMA table_info(cards)` set-membership | identical |

Everything else — engine/session wiring, logging style (`%`-lazy args, `✓`/`✅`/`❌` markers),
`try/except/rollback/sys.exit(1)`, `finally: await engine.dispose()`, the post-run schema dump — is
copied verbatim. Compare also `scripts/migrate_add_deck_strategy.py` (same shape, single column) for
a second reference; note it *also* creates an index — **you do NOT need an index** on `game_changer`
(assessment reads full deck rows, not a `WHERE game_changer = …` scan), so skip the index step.

### DB target — the migration and the importer hit the same file by default

`create_engine()` with no argument resolves the URL via `default_database_url()` → the shared
**central data dir** `cards.db` (`src/paths.database_path()`), with an explicit `CARDS_DATABASE_URL`
still winning. `scripts/import_scryfall_data.py` resolves the same `database_path()`. So the default
(no-arg `create_engine()`) migration and the default backfill import operate on the **same** file —
the migration you run and the data you backfill line up with what the MCP server reads. Mirror the
precedent exactly (`create_engine()` no-arg); do not hardcode `./data/cards.db`.

### The `BOOLEAN` column type (the one non-mechanical detail)

SQLite is dynamically typed, but column **affinity** should match how SQLAlchemy declared the
column so values round-trip cleanly. Story 4.1 declared `game_changer` with SQLAlchemy `Boolean`,
which SQLAlchemy renders as `BOOLEAN` and stores as integer `0`/`1`/`NULL`. Use
`ALTER TABLE cards ADD COLUMN game_changer BOOLEAN NULL` so a fresh-`create_all` DB and a
migrated-then-backfilled DB are indistinguishable. (`INTEGER NULL` would also functionally work
under SQLite affinity, but `BOOLEAN` is the honest, self-documenting match to the ORM declaration.)

### Backfill mechanics — why it "just works" and why `oracle_cards`

`transform_scryfall_card` already reads `card_json.get("game_changer")` and passes it into
`CardModel(...)` (Story 4.1, `src/data/importers/transformers.py:79,123`). The importer upserts one
row per oracle identity, so a re-import over the migrated DB overwrites every card's `game_changer`
with the real bulk value — `None`/`True`/`False` all preserved (no coercion in the schema). Prefer
`--type oracle_cards` for the backfill: `game_changer` is a per-oracle-identity property, so the
smaller oracle bulk is sufficient and lighter than `default_cards` (all printings). Either type
backfills correctly (both dedupe to one row per oracle); `oracle_cards` just does less work. The
epic AC's "~60k cards / `scripts/import_scryfall_data.py`" phrasing refers to the default import —
functionally equivalent for this field, just heavier.

### Verifying the backfill (AC6) — query, don't hardcode names

The GC list changes over time (NFR5), so **don't** commit a hardcoded card-name assertion. Verify
by shape instead: `SELECT count(*) FROM cards WHERE game_changer = 1` should land near ~50 (the Feb
2026 `is:gamechanger` list is ~53 cards) — a `0` means the extraction didn't flow, the full corpus
count means something coalesced. Then eyeball `SELECT name FROM cards WHERE game_changer = 1` for
recognizable staples, and confirm a vanilla common reads `0`/`False`. Record the actual numbers in
Completion Notes.

### Testing standards

No automated test is required or expected for this story — consistent with every existing
`migrate_*.py` (none have tests; `grep -rln migrate tests/` is empty). Migrations are validated
operationally. The acceptance signal is the manual idempotency + NULL-interim smoke (Task 3),
recorded in Completion Notes. Do not add a test module that spins up a pre-field DB just to exercise
the `ALTER` — it has no precedent here and isn't in the ACs.

### Project Structure Notes

- **One new file only:** `scripts/migrate_add_game_changer.py`. No `src/` edits, no schema/model
  edits (done in 4.1), no new dependency.
- `scripts/` is exempt from the `mypy --strict` pre-commit gate (`^src/` only) but **is** covered by
  `ruff check .` — match the sibling scripts' style (module docstring required, `%`-lazy logging,
  `print()` is acceptable in `scripts/` per project-context, 100-char lines).
- The `build-plugin-sync` hook will not re-mirror anything (its `files:` scope excludes
  `scripts/migrate_*.py`) — expect a clean pre-commit with no plugin diff, unlike Story 4.1.
- Conventional Commits: `feat:` (new migration capability) is appropriate, e.g.
  `feat: add game_changer migration + documented backfill (Story 4.2)`.

### References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 1.2] — story
  definition + acceptance criteria (epic file numbers this "1.2"; the sprint tracks it as `4-2`).
- [Source: _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-11/ARCHITECTURE-SPINE.md#AD-4] —
  nullable `game_changer`, NULL = "unknown" degrades confidence, never coalesce to `False`,
  backfill requires a re-import; the interim degraded window is expected.
- [Source: scripts/migrate_add_power_toughness.py] — the structural template (idempotent
  `PRAGMA table_info` guard, engine/session wiring, error handling, backfill docstring).
- [Source: scripts/migrate_add_deck_strategy.py] — second single-column precedent (note: it adds an
  index; `game_changer` does **not** need one).
- [Source: scripts/import_scryfall_data.py] — the operator-invoked backfill entry point;
  `--type oracle_cards` is the lighter sufficient backfill.
- [Source: src/data/importers/transformers.py:75-79,123] — Story 4.1's extraction
  (`card_json.get("game_changer")` → `CardModel(...)`) that the re-import replays to backfill.
- [Source: src/data/models/card.py:48-54] — the `Boolean`-typed `game_changer` column the `ALTER`
  must match on affinity.
- [Source: src/data/database.py#create_engine] + [src/paths.py#database_path] — no-arg
  `create_engine()` and the importer resolve the **same** central `cards.db`.
- [Source: .pre-commit-config.yaml#build-plugin-sync] — `files:` scope excludes new `scripts/`
  migrations, so no plugin mirror this story.
- [Source: _bmad-output/implementation-artifacts/4-1-add-the-nullable-game-changer-field-end-to-end.md] —
  prior story: the field is already live end-to-end in `src/`; this story only migrates existing DBs.
- [Source: _bmad-output/project-context.md] — no Alembic (hand-written `scripts/migrate_*.py`),
  heavy import is deliberate ("don't re-import casually"), `mypy` scope is `^src/`, ruff over all,
  `uv run …` command discipline, three-state `None`/`False` contract.
- Precedent commit: `77e1463` "feat: show power/toughness in the read-only deck viewer" (the P/T
  migration + backfill pattern this story mirrors).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Claude Code, bmad-dev-story workflow)

### Debug Log References

Idempotency + NULL-interim smoke run against a throwaway copy of the live
`cards.db` (38,232 rows, no pre-existing `game_changer` column), targeted via
`CARDS_DATABASE_URL=sqlite+aiosqlite:///<scratch>`:

```
===== RUN 1 (adds the column) =====
Adding game_changer column to cards table...
✓ game_changer column added successfully
  - game_changer (BOOLEAN)
✅ Migration completed successfully!   (exit 0)

===== NULL-interim smoke (AC2) =====
total rows:               38232
game_changer IS NULL:     38232
game_changer IS NOT NULL: 0
column affinity:          BOOLEAN

===== RUN 2 (idempotent no-op) =====
✓ game_changer column already exists in cards table
  - game_changer (BOOLEAN)
✅ Migration completed successfully!   (exit 0)
```

### Implementation Plan

Single new file `scripts/migrate_add_game_changer.py`, structurally mirroring
`scripts/migrate_add_power_toughness.py` (the near-exact precedent): same engine/
session wiring, `PRAGMA table_info(cards)` set-membership guard, `%`-lazy logging
with `✓`/`✅`/`❌` markers, `try/except → logger.error + rollback + sys.exit(1)`,
`finally: await engine.dispose()`, and the post-migration schema dump. The only
substantive differences from the precedent: one column instead of two, and
`BOOLEAN NULL` instead of `VARCHAR NULL` (to match Story 4.1's `Boolean`-typed
ORM column so a fresh-`create_all` DB and a migrated DB are indistinguishable).
No index (unlike `migrate_add_deck_strategy.py` — assessment reads full deck
rows, not a `WHERE game_changer` scan). No backfill UPDATE — the additive
`ALTER` alone satisfies AC2; rows stay `NULL` (AD-4 "unknown"). The backfill
re-import is documented in the docstring only, never invoked (AC4). No `src/`
edits, no test module (no `migrate_*.py` has one; migrations are validated
operationally).

### Completion Notes List

- ✅ **AC1** — new `scripts/migrate_add_game_changer.py` adds the column additively
  via raw `ALTER TABLE cards ADD COLUMN game_changer BOOLEAN NULL`, mirroring the
  P/T migration's structure (same PRAGMA guard, engine/session wiring, logging,
  `sys.exit(1)`-on-error shape). No Alembic.
- ✅ **AC2** — migration performs only the additive `ALTER`; no values written.
  Post-run smoke on a 38,232-row DB: `game_changer IS NULL` = 38232,
  `IS NOT NULL` = 0. NULL = "unknown / not yet backfilled" (never `False`, AD-4).
- ✅ **AC3** — idempotent. Run 2 detected the column via `PRAGMA table_info(cards)`,
  logged "already exists", made no second `ALTER`, exited 0. Both runs exit 0;
  schema unchanged between runs.
- ✅ **AC4** — the migration does not import or shell out to the importer. The
  docstring documents the operator-invoked backfill as a separate deliberate step
  ("don't re-import casually").
- ✅ **AC5** — docstring names the exact backfill command
  `uv run python scripts/import_scryfall_data.py --type oracle_cards`
  (oracle-level is sufficient — `game_changer` is a per-oracle-identity property;
  Story 4.1's `transform_scryfall_card` already extracts it, so the re-import
  replays real values across the corpus).
- ✅ **AC6** — live backfill spot-check is deliberately operator-side (heavy import,
  not run locally). Verify-by-shape queries to run **after** the backfill re-import
  (do NOT hardcode a card-name list — the GC list changes over time, NFR5):

  ```sql
  -- Expect a count near ~50 (Feb 2026 is:gamechanger list ≈ 53). 0 = extraction
  -- didn't flow; full-corpus count = something coalesced.
  SELECT count(*) FROM cards WHERE game_changer = 1;
  -- Eyeball for recognizable Game Changer staples.
  SELECT name FROM cards WHERE game_changer = 1 ORDER BY name;
  -- A vanilla common should read back 0/False.
  SELECT game_changer FROM cards WHERE name = 'Grizzly Bears';
  ```
- ✅ **AC7** — `ruff check` clean, `ruff format --check` reports already-formatted,
  `pre-commit run --files scripts/migrate_add_game_changer.py` passes: ruff +
  ruff-format Passed; `mypy` Skipped (`^src/` scope only); `build-plugin-sync`
  Skipped (its `files:` scope excludes new `scripts/migrate_*.py`) — exactly as
  the story predicted, no plugin mirror this story.
- **Scope note:** one new file only; no `src/` changes. The scratch DB used for the
  smoke lives outside the repo (session scratchpad) and is not committed.

### File List

- `scripts/migrate_add_game_changer.py` (new)

### Change Log

- 2026-07-11 — Story 4.2: added `scripts/migrate_add_game_changer.py`, an
  idempotent additive migration (`ALTER TABLE cards ADD COLUMN game_changer
  BOOLEAN NULL`) with a documented `oracle_cards` re-import backfill path. Rows
  stay NULL (AD-4 "unknown") until the operator runs the deliberate re-import.
  Verified via idempotency + NULL-interim smoke on a copy of the live DB.

### Review Findings

- [x] [Review][Decision] Documented backfill (AC5/AC6) could not actually populate `game_changer` — `game_changer` was completely absent from `src/data/importers/importer.py::_insert_batch`'s hand-listed `card_dict` (insert values) and its `on_conflict_do_update` `set_` mapping. `power`/`toughness` were added to both dicts when *their* migration story landed, but Story 4.1 never touched `importer.py` when it added `game_changer` to `CardModel`/`Card`/`transform_scryfall_card`. **Resolved:** Brad chose to expand this story's scope — added `"game_changer": card.game_changer` to the insert dict and `"game_changer": stmt.excluded.game_changer` to the `on_conflict_do_update` `set_` mapping in `src/data/importers/importer.py` (2 lines, mirrors the existing `power`/`toughness` pattern exactly). Verified: `ruff check`/`mypy` clean, 113 tests pass (7 e2e import tests, 0 regressions). Plugin mirror (`plugin/server/src/data/importers/importer.py`) will auto-sync via the `build-plugin-sync` pre-commit hook since this touches `src/`. [src/data/importers/importer.py]
- [x] [Review][Defer] Pre-`try` engine/session-factory failures aren't caught, and `rollback()`/`dispose()` in the `except`/`finally` aren't guarded against secondary exceptions [scripts/migrate_add_game_changer.py:42-46,67-72] — deferred, pre-existing (verbatim structure copied from `scripts/migrate_add_power_toughness.py` per this story's own template mandate; not introduced by this diff).
- [x] [Review][Defer] TOCTOU race: the `PRAGMA table_info` idempotency check and the `ALTER TABLE` aren't atomic, so two concurrent runs can both pass the check before either commits, and the loser surfaces a raw "duplicate column name" error instead of a benign no-op [scripts/migrate_add_game_changer.py:50-57] — deferred, pre-existing (identical race exists in the precedent script).
- [x] [Review][Defer] `PRAGMA table_info(cards)` on a database with no `cards` table returns an empty result set (not an error), so the script proceeds to `ALTER TABLE` on a nonexistent table and surfaces a raw "no such table: cards" failure instead of a bootstrap hint [scripts/migrate_add_game_changer.py:47-55] — deferred, pre-existing (same gap in `migrate_add_power_toughness.py`; same class as the previously-resolved G3 bootstrap-gap pattern, but not fixed in this template).
- [x] [Review][Defer] Upsert-based backfill only overwrites rows present in the current Scryfall bulk export; a card absent from a fresh export keeps its prior (NULL) `game_changer` value indefinitely — the docstring's "overwrites every card" framing overstates coverage [src/data/importers/importer.py] — deferred, pre-existing (inherent to the importer's existing upsert design, not introduced by this diff).
- [x] [Review][Defer] The idempotency guard checks only column *presence*, not the existing column's declared type/nullability — a differently-typed partial/failed prior migration would be silently treated as already-satisfied [scripts/migrate_add_game_changer.py:50-53] — deferred, pre-existing (identical guard shape in the precedent script).
