---
baseline_commit: 3942fe6fa86647196a960555570a7a54ac2a7283
---

# Story 6.1: Commander flag end-to-end

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the assessor (and the Arena importer),
I want each deck card to record whether it is a commander,
so that Bracket rules and commander-required combos work from real data instead of guessing.

## Acceptance Criteria

1. **`DeckCardModel` gains the flag.** `DeckCardModel` (`src/data/models/deck_card.py`) gains
   `commander: Mapped[bool]` via `mapped_column(Boolean, nullable=False, default=False, init=True)`,
   placed after the existing `sideboard` column and mirroring its style. **`commander` is NOT part
   of the composite primary key** (unlike `sideboard`) — a card's mainboard row is unique regardless
   of the flag; the flag is an attribute, not an identity. Two flagged cards in one deck represent
   partners (no uniqueness constraint on the flag). [AD-13 / FR25 schema half]

2. **`DeckCard` schema gains the flag.** `DeckCard` (`src/data/schemas/deck.py`) gains
   `commander: bool = False`, with `from_attributes=True` preserved so
   `DeckCard.model_validate(deck_card_model)` picks it up automatically. `DeckCardSummary` (same
   file) also gains `commander: bool = False` so `load_deck` / `create_deck` projections surface
   the flag (it already carries `sideboard`; the projection is how an MCP client verifies an
   import flagged the commander). [AD-13; layer contract "repositories return Pydantic, never ORM"]

3. **Additive idempotent migration.** A hand-written migration
   `scripts/migrate_add_deck_card_commander.py` (no Alembic) adds the column to existing databases:
   `ALTER TABLE deck_cards ADD COLUMN commander BOOLEAN NOT NULL DEFAULT 0`. Existing rows read
   back `False`. Re-running the script is a safe no-op (detects the column via
   `PRAGMA table_info(deck_cards)`), mirroring `scripts/migrate_add_game_changer.py`. A fresh DB
   created via `Base.metadata.create_all` includes the column automatically.

4. **`add_card_to_deck` accepts and persists the flag — through all three layers.**
   `DeckRepository.add_card_to_deck` (`src/data/repositories/deck.py`), the tool helper
   `add_card_to_deck` (`src/mcp_server/tools/deck_management.py`), and the registered MCP tool
   (`src/mcp_server/server.py`) each gain `commander: bool = False` as a trailing keyword
   parameter (additive — existing callers unchanged), threaded down to the `DeckCardModel(...)`
   construction. [FR25 / AD-13]

5. **`import_decklist`'s `Commander` section sets the flag.** In
   `src/mcp_server/tools/deck_import.py`, cards parsed under the `Commander` section are added
   with `commander=True`; mainboard placement is unchanged (`sideboard` stays `False` for that
   section). All other sections add with `commander=False`. [FR25 / AD-13]

6. **Every `deck_cards` write path is enumerated and dispositioned** (epic-5 retro action item 6 —
   the Epic-4 "end-to-end field" checklist). The enumeration in Dev Notes below is the contract:
   each write path either propagates the flag or has a documented no-change rationale. In
   particular `DeckRepository.merge_decks` propagates `source_card.commander` when copying a card
   into the target deck.

7. **Type + lint gates pass.** `mypy --strict` passes over `src/`, `ruff check` + `ruff format`
   pass, and pre-commit succeeds without `--no-verify` (the `build-plugin-sync` hook re-mirrors
   `src/` → `plugin/server/`).

8. **Tests prove the round-trip at every layer.** Model default + explicit `True`; schema
   validation; repository persistence round-trip (write `commander=True`, read back through
   `get_deck_with_cards` as Pydantic `True`); MCP tool layer (add with `commander=True`; Arena
   import with a `Commander` section flags exactly those cards). Assert with `is True` /
   `is False`, not `==` (the Story 4.1 discipline).

## Tasks / Subtasks

- [x] **Task 0 — Story-start state verification** (epic-5 retro action item: verify, don't trust)
  - [x] Prove the live DB's `deck_cards` schema before writing code. Drop this into a scratch
        file (session scratchpad, not the repo) and run it with `uv run python <file>`:

        ```python
        import asyncio
        from sqlalchemy import text
        from src.data.database import create_engine

        async def main() -> None:
            engine = create_engine()
            async with engine.connect() as conn:
                rows = (await conn.execute(text("PRAGMA table_info(deck_cards)"))).fetchall()
            print([r[1] for r in rows])
            await engine.dispose()

        asyncio.run(main())
        ```

  - [x] Record the output in the Dev Agent Record. Expected: `deck_id, card_id, quantity,
        sideboard` — **no `commander`**. If `commander` already exists, stop and investigate
        before writing code.

- [x] **Task 1 — ORM model** (AC: 1, 7)
  - [x] In `src/data/models/deck_card.py`, add
        `commander: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, init=True)`
        immediately after the `sideboard` column. Do **not** add `primary_key=True`.
        (Dataclass ordering is safe: `commander` has a default and follows the defaulted
        `sideboard`; the relationship fields are `init=False`.)
  - [x] Add a short comment stating the flag marks the deck's commander(s), two flagged rows =
        partners, and that it is deliberately **not** part of the composite PK.
  - [x] Update the class docstring (currently "quantity and sideboard tracking") and optionally
        `__repr__` to mention the flag.

- [x] **Task 2 — Pydantic schemas** (AC: 2, 7)
  - [x] In `src/data/schemas/deck.py`, add `commander: bool = False` to `DeckCard` (after
        `sideboard`). No validator — plain bool with default.
  - [x] Add `commander: bool = False` to `DeckCardSummary` (after `sideboard`) and thread it in
        the `_deck_detail` projection in `src/mcp_server/tools/deck_management.py`
        (`DeckCardSummary(... commander=dc.commander ...)`) so `load_deck` surfaces it.

- [x] **Task 3 — Migration script** (AC: 3)
  - [x] Create `scripts/migrate_add_deck_card_commander.py` by mirroring
        `scripts/migrate_add_game_changer.py` structurally (same engine/session/PRAGMA-check/
        rollback/exit-1 shape, `logging.basicConfig`, `uv run` usage note in the module
        docstring). Differences: table is `deck_cards`, column is
        `commander BOOLEAN NOT NULL DEFAULT 0` (NOT nullable — this flag is two-state, unlike
        `game_changer`'s three-state `NULL`).
  - [x] Run it against the live central DB; then re-run to prove the no-op path. Record both
        outputs in the Dev Agent Record.

- [x] **Task 4 — Repository write path** (AC: 4, 6)
  - [x] `DeckRepository.add_card_to_deck` gains `commander: bool = False` (trailing param, after
        `sideboard`); pass it into `DeckCardModel(...)`. Update the docstring Args/Example.
  - [x] `DeckRepository.merge_decks`: in the "card doesn't exist in target" branch, pass
        `commander=source_card.commander` to `self.add_card_to_deck(...)`. The
        "card exists in target" branch keeps the **target's** flag (quantity-only merge) — add a
        one-line comment stating that choice.
  - [x] `update_card_quantity`, `remove_card_from_deck`, `delete_deck`: no change (see write-path
        table in Dev Notes — quantity-only update / deletes).

- [x] **Task 5 — MCP tool layer** (AC: 4, 5, 6)
  - [x] Helper `add_card_to_deck` in `src/mcp_server/tools/deck_management.py`: add
        `commander: bool = False` keyword param, pass through to
        `deck_repo.add_card_to_deck(deck_id, card.id, quantity, sideboard, commander=commander)`.
        Update docstring Args.
  - [x] Registered tool `add_card_to_deck` in `src/mcp_server/server.py` (~line 274): add
        `commander: bool = False` parameter + one Args line (the docstring is the LLM-facing tool
        description — say "mark this card as the deck's commander; flag two cards for partners"),
        forward to the helper.
  - [x] `src/mcp_server/tools/deck_import.py`: give `_ParsedArenaLine` a `commander` property
        (`return self.section == "commander"`) beside the existing `sideboard` property; pass
        `commander=item.commander` in the `_add_card_to_deck(...)` call inside `import_decklist`.
        Update the `import_decklist` docstring and the registered-tool docstring in `server.py`
        ("Commander entries become mainboard cards **flagged as commanders**").

- [x] **Task 6 — Tests (RED first, per TDD discipline)** (AC: 8)
  - [x] `tests/unit/data/models/test_deck_card.py`: default `commander is False` when omitted;
        explicit `commander=True` sticks; existing constructions keep passing untouched (proves
        additivity).
  - [x] `tests/unit/data/schemas/test_deck.py`: `DeckCard` and `DeckCardSummary` default
        `commander is False`; `model_validate` from an ORM-like object with `commander=True`
        yields `True`.
  - [x] `tests/integration/data/test_deck_repository.py`: add a card with `commander=True`
        (sideboard False) → `get_deck_with_cards` returns a Pydantic `DeckCard` with
        `commander is True`; a merge_decks case where the source deck's flagged card lands in the
        target still flagged.
  - [x] `tests/integration/mcp_server/test_deck_management_tool.py`: tool add with
        `commander=True` → `load_deck` shows the card with `commander` true in its
        `DeckCardSummary` row.
  - [x] `tests/integration/mcp_server/test_deck_import_tool.py`: an Arena export with a
        `Commander` section (e.g. `1 Atraxa, Praetors' Voice (2X2) 190`) plus `Deck` +
        `Sideboard` sections → exactly the Commander-section card has `commander=True`, it is
        mainboard (`sideboard=False`), and all other cards are `commander=False`.
  - [x] Async tests: plain `async def test_...` (asyncio_mode auto — no marker); integration
        tests carry the `integration` marker convention already used in those files.

- [x] **Task 7 — Quality gates + docs** (AC: 7)
  - [x] `uv run ruff check . --fix && uv run ruff format .`
  - [x] `uv run mypy src/`
  - [x] `uv run pytest -m "not integration"` then the touched integration files.
  - [x] Commit normally — the installed `build-plugin-sync` pre-commit hook re-mirrors
        `plugin/server/`; do not hand-edit the mirror, do not bypass hooks.

## Dev Notes

### What this story is (and is NOT)

This is the **schema / migration / write-path** slice of commander identity (feature Story 3.1,
sprint key `6-1`). It does **NOT** include:
- **Edge resolution / inference** (flagged cards → sole-legendary inference → `commander_unidentified`) —
  that is Epic 7, Story 7.1 (feature 4.1), per FR25's split. Do not add inference logic anywhere.
- The Spellbook snapshot import (Story 6.2) or the combo-snapshot repository (Story 6.3).
- Any scorer change: `score(cards, commanders, combos, profile)` already takes a resolved
  `commanders` argument (Epic 5); nothing in `src/logic/` changes here.
- Deck-validator or viewer behavior. `src/logic/deck_validator.py` mentions "commander" only as
  format names; `src/viewer/` has no commander concept. Leave both alone.

### THE checklist — every `deck_cards` write path, enumerated (AC 6)

Epic-5 retro action item 6 requires this story to enumerate every `deck_cards` write path before
claiming "end-to-end" (the Epic-4 lesson: `game_changer` shipped "end-to-end" while a write path
silently dropped it). The full set, verified against the current tree (`grep DeckCardModel`):

| # | Write path | Location | Disposition |
|---|---|---|---|
| 1 | `DeckRepository.add_card_to_deck` | `src/data/repositories/deck.py:294` (constructs `DeckCardModel` at :331) | **CHANGE** — new `commander` param → `DeckCardModel(...)` |
| 2 | `DeckRepository.update_card_quantity` | `src/data/repositories/deck.py:422` | No change — updates `quantity` only, keyed by `(deck_id, card_id, sideboard)`; flag untouched by design |
| 3 | `DeckRepository.merge_decks` | `src/data/repositories/deck.py:566` | **CHANGE** — new-card branch passes `commander=source_card.commander`; exists-branch merges quantity only and keeps the target's flag (documented) |
| 4 | `DeckRepository.remove_card_from_deck` / `delete_deck` | `src/data/repositories/deck.py` | No change — deletes |
| 5 | MCP helper `add_card_to_deck` | `src/mcp_server/tools/deck_management.py:402` | **CHANGE** — thread `commander` through |
| 6 | MCP registered tool `add_card_to_deck` | `src/mcp_server/server.py:274` | **CHANGE** — new param + docstring |
| 7 | `import_decklist` | `src/mcp_server/tools/deck_import.py:304` (delegates to #5) | **CHANGE** — Commander section → `commander=True` |
| 8 | Scryfall importer reconcile (repoint) | `src/data/importers/scryfall.py:241-250` — `update(DeckCardModel).values(card_id=canonical)` | No change — updates `card_id` only; `commander` survives in place |
| 9 | Scryfall importer reconcile (merge + delete stale) | `src/data/importers/scryfall.py:251-267` — `.values(quantity=... + q)` then delete stale row | No column-list change. **Known micro-edge:** if a deck held two printings of the same oracle identity and only the *stale* row was flagged, the flag is lost with the stale row. Accepted for v1 (requires holding duplicate printings of your commander); do not build machinery for it — note it, move on |
| 10 | `Base.metadata.create_all` (fresh DB) | `src/data/database.py` `init_database` | No change — ORM model defines the column; fresh DBs get it automatically |
| 11 | Test fixtures constructing `DeckCardModel(...)` | `tests/unit/data/models/test_deck_card.py`, `tests/integration/data/test_scryfall_import_e2e.py:405-505` | No change required — `default=False` absorbs keyword-only construction (same as Story 4.1's `database.py` health-check finding). They must still pass untouched; that IS the additivity proof |

There is **no** `deck_cards` upsert column list anywhere (the `on_conflict_do_update` upsert in
`src/data/importers/importer.py` targets the `cards` table — the Epic-4 miss lived there, but it
has no `deck_cards` counterpart). If you find a write path not in this table, stop and add it to
this table before proceeding.

### Precedent to copy — Story 4.1 (`game_changer`), with three deliberate differences

Story 4.1 (`4-1-add-the-nullable-game-changer-field-end-to-end.md`) + `scripts/migrate_add_game_changer.py`
are the structural template: same additive-column story shape, same file discipline, same test
style. Differences that matter:

1. **Two-state, not three-state.** `game_changer` is `bool | None` with NULL = unknown;
   `commander` is `Mapped[bool]`, `nullable=False`, `DEFAULT 0`. There is no "unknown" here — an
   unflagged card is simply not a commander. Do not import the AD-4 NULL discipline.
2. **No backfill / no re-import.** `deck_cards` is small user data; `DEFAULT 0` on the ALTER is
   the entire backfill. The migration is complete in one step (unlike 4.2's heavy Scryfall
   re-import).
3. **The write surface is wide.** 4.1 changed one constructor (the transformer); this story's
   whole point is the multi-path table above. That's why the retro pinned the checklist to 6.1.

Also inherit 4.1's dataclass-init lesson: defaulted `mapped_column` fields must not precede
non-defaulted ones. Here `commander` (defaulted) goes after `sideboard` (defaulted) — safe without
`kw_only`, but adding `kw_only=True` is also acceptable if you prefer parity with `card.py`.

### Composite-PK subtlety — read before touching the model

`deck_cards`'s composite PK is `(deck_id, card_id, sideboard)` — `sideboard` is
`primary_key=True` so one card can sit in both mainboard and sideboard. **Do not** mirror that for
`commander`: making it part of the PK would let the same card exist twice in the mainboard
(flagged + unflagged), corrupting quantity semantics and the `exists` detection in the tool layer
(which relies on `IntegrityError` from the current PK). Plain non-PK `Boolean` column, nothing else.

### Migration specifics

- SQLite supports `ADD COLUMN ... NOT NULL DEFAULT 0` on a populated table (constant default) —
  no table rebuild, instant on a small table. `BOOLEAN` affinity stores 0/1; SQLAlchemy's
  `Boolean` reads it back as `bool`.
- Mirror `migrate_add_game_changer.py` exactly for shape: `PRAGMA table_info(deck_cards)`
  idempotency check, commit, schema echo, rollback + `sys.exit(1)` on failure, `await
  engine.dispose()` in `finally`.
- DB URL comes from `CARDS_DATABASE_URL` (never `DATABASE_URL` — Chainlit hijacks it); the
  engine/session factory from `src.data.database` already handles this — copy the precedent's
  imports, don't hand-roll a connection.
- Document in the module docstring: no follow-up backfill step exists for this migration.

### Arena importer notes

- `_ParsedArenaLine` is a frozen slots dataclass with a `sideboard` property derived from
  `section`; add the `commander` property the same way. The section literal is already
  `"commander"` (`_SECTION_HEADERS`), and Commander-section cards already land in the mainboard —
  only the flag is new. "Mainboard placement unchanged" (AC 5) means: do not touch
  `_SIDEBOARD_SECTIONS`.
- `Companion` section: sideboard, `commander=False`. No new sections.
- A `Commander`-section card that already exists in the deck mainboard returns `status="exists"`
  and does **not** retro-flag the existing row — same semantics as quantity (no upsert). Don't
  "fix" this; it's the established additive-import contract.
- Optional, cheap: surface `commander: bool | None = None` on `DeckImportLineResult` (like its
  `sideboard` field) so per-line results show what was flagged. If added, keep it derived from the
  section, and update the model docstring.

### Previous-story intelligence (Epic 5 retro + importer gate, 2026-07-15)

- **Verify, don't trust** (5.9 saga → retro action item 4): hence Task 0's PRAGMA check. The
  story author verified nothing about the live DB's `deck_cards` schema — the dev must.
- **"Drop the claim or write the message":** don't check off AC 6 until the write-path table's
  CHANGE rows are all implemented and the no-change rows re-verified against your diff.
- **Review-severity pattern:** Epic 5's early stories shipped correctness defects in exactly this
  kind of plumbing (dup handling, key collisions). The PK subtlety above is this story's
  equivalent trap.
- **Plugin mirror:** the `build-plugin-sync` pre-commit hook is installed (verified at epic-5
  retro, `88b1e66`); expect `plugin/server/src/...` files in your diff after commit — they are
  generated, never hand-edited.
- **DFC `_name_keys` hazard is 6.2's problem, not yours** — name resolution here goes through the
  existing `_resolve_card` exact→partial path unchanged.

### Web/library research

No new dependencies, no version-sensitive APIs. SQLAlchemy 2.0 typed `Mapped` + SQLite additive
`ALTER TABLE` are both already exercised by this repo's precedents (`card.py`,
`migrate_add_game_changer.py`); Scryfall/Spellbook data is not involved in this story. Nothing to
research externally.

### Testing standards summary

- pytest config in `pyproject.toml`; `asyncio_mode = "auto"` (no `@pytest.mark.asyncio`);
  `--strict-markers`; integration tests marked `integration` (deselectable via
  `-m "not integration"`).
- Layout mirrors `src/`: unit model/schema tests in `tests/unit/data/...`; repo round-trips in
  `tests/integration/data/test_deck_repository.py`; tool tests in
  `tests/integration/mcp_server/test_deck_{management,import}_tool.py` (reuse those files'
  existing fixtures/factories — do not spin up a new harness).
- Assert flag states with `is True` / `is False` (Story 4.1 discipline).
- `tests.*` exempt from `mypy --strict`; ruff/naming still apply.
- Full suite baseline at story start: **1,136 passed, 0 failed, 0 skipped** (epic-5 retro).
  Anything below that at story end is a regression you introduced.

### Project Structure Notes

- Layer discipline: `data → logic → mcp_server` import direction; repositories return Pydantic,
  never ORM (`DeckCard.model_validate(...)` already at every exit). All edits stay in
  `src/data/{models,schemas,repositories}`, `src/mcp_server/{tools,server.py}`, `scripts/`.
- MCP tools stay stateless: `commander` is a caller-supplied per-call parameter, exactly like
  `sideboard` (D5 — no session state).
- Modern 3.12 syntax (`bool`, not `Optional`); Google-style docstrings — the tool docstrings are
  the LLM-facing descriptions, so the new param's Args line must be written for an agent reader.
- Transaction discipline in repo writes (try/commit/refresh, rollback on
  `IntegrityError`/`DatabaseError`) already wraps `add_card_to_deck` — you're adding a kwarg, not
  touching the error handling.
- Branch policy: work stays on `feat/deck-power-assessment` (no merge to master until Epic 7
  completes — epic-5 retro decision). Conventional Commits (`feat:` for this).

### References

- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#Story 3.1] — story +
  ACs (epic file numbers this "3.1"; sprint tracks it as `6-1`).
- [Source: _bmad-output/planning-artifacts/epics-deck-power-assessment.md#AD-13] — commander
  identity invariant: schema, `add_card_to_deck(commander=)`, Arena importer, edge-resolution
  split (edge half = Story 7.1, not here).
- [Source: _bmad-output/planning-artifacts/sprint-change-proposal-2026-07-12.md#P3/P4] — Epic 6
  re-scope + FR25/AD-13 origin.
- [Source: _bmad-output/implementation-artifacts/epic-5-retro-2026-07-15.md#Action Items] —
  item 4 (story-start verification → Task 0), item 6 (write-path checklist → AC 6).
- [Source: _bmad-output/implementation-artifacts/4-1-add-the-nullable-game-changer-field-end-to-end.md] —
  the end-to-end-field precedent story (structure, test discipline, dataclass-init lesson).
- [Source: src/data/models/deck_card.py:15-48] — model to edit; composite-PK layout.
- [Source: src/data/schemas/deck.py:14-35,102-117] — `DeckCard` + `DeckCardSummary` to edit.
- [Source: src/data/repositories/deck.py:294-372,566-722] — `add_card_to_deck` + `merge_decks`
  write paths.
- [Source: src/mcp_server/tools/deck_management.py:402-511] — tool helper + `_deck_detail`
  projection.
- [Source: src/mcp_server/server.py:274-335] — registered `add_card_to_deck` + `import_decklist`
  docstrings.
- [Source: src/mcp_server/tools/deck_import.py:79-95,255-265,400-439] — `_ParsedArenaLine`,
  section handling, the `_add_card_to_deck` call site.
- [Source: src/data/importers/scryfall.py:204-267] — reconcile repoint/merge (write paths #8/#9).
- [Source: scripts/migrate_add_game_changer.py] — migration template.
- [Source: _bmad-output/project-context.md] — layer contract, `CARDS_DATABASE_URL`, `uv run`
  discipline, mypy/ruff gates, no-Alembic migration rule.

## Dev Agent Record

### Agent Model Used

claude-fable-5 (Claude Code)

### Debug Log References

- **Task 0 — story-start state verification (2026-07-16):** `PRAGMA table_info(deck_cards)`
  against the live central DB returned `['deck_id', 'card_id', 'quantity', 'sideboard']` —
  no `commander`, exactly the expected pre-story state. Proceeded.
- **Task 3 — migration first run (2026-07-16):** `uv run python
  scripts/migrate_add_deck_card_commander.py` → "Adding commander column to deck_cards
  table... ✓ commander column added successfully"; schema echo shows
  `deck_id (VARCHAR), card_id (VARCHAR), quantity (INTEGER), sideboard (BOOLEAN),
  commander (BOOLEAN)`; "✅ Migration completed successfully!"
- **Task 3 — migration re-run (no-op proof):** second run → "✓ commander column already
  exists in deck_cards table" + same schema echo + success. Idempotent.
- **Task 3 — backfill check:** `SELECT commander, COUNT(*) FROM deck_cards GROUP BY
  commander` → `[(0, 587)]` — all 587 existing live rows read back `False` via the
  `DEFAULT 0`; no separate backfill step needed (as designed).
- **TDD:** every layer done RED→GREEN. RED evidence: 6 unit failures
  (`AttributeError: ... no attribute 'commander'`), 2+ repo failures
  (`TypeError: ... unexpected keyword argument 'commander'`), 2 tool-layer failures
  (`AttributeError: 'DeckImportLineResult' object has no attribute 'commander'`) — all
  before any production edit for that layer; all green after.

### Completion Notes List

- **AC 1–2:** `DeckCardModel.commander` (`Boolean, nullable=False, default=False, init=True`,
  NOT part of the composite PK — comment in the model states why) + `commander: bool = False`
  on `DeckCard` and `DeckCardSummary`; `_deck_detail` threads it so `load_deck`/`create_deck`
  projections surface the flag.
- **AC 3:** `scripts/migrate_add_deck_card_commander.py` mirrors `migrate_add_game_changer.py`
  (PRAGMA idempotency check, rollback + exit(1), engine dispose in finally). Two-state
  `NOT NULL DEFAULT 0` — no NULL discipline imported. Run + re-run outputs above.
- **AC 4:** `commander: bool = False` threaded through all three layers: repository
  `add_card_to_deck` → tool helper → registered MCP tool (docstring written for LLM readers:
  "flag two cards for partners"). Trailing keyword param — every existing caller unchanged.
- **AC 5:** `_ParsedArenaLine.commander` property (`section == "commander"`);
  `import_decklist` passes it through; mainboard placement untouched
  (`_SIDEBOARD_SECTIONS` unchanged; Companion stays sideboard + `commander=False`). Also took
  the story's optional add: `DeckImportLineResult.commander: bool | None` (derived from
  section, like `sideboard`) so per-line results show what was flagged.
- **AC 6:** write-path table re-verified against the final diff via
  `grep DeckCardModel(|update(DeckCardModel)` over `src/`: the only constructor is
  `deck.py` `add_card_to_deck` (CHANGED); scryfall reconcile updates touch `card_id` /
  `quantity` only (flag survives in place; stale-row micro-edge accepted per story);
  `merge_decks` new-card branch propagates `source_card.commander`, exists-branch keeps the
  target's flag (commented). No unlisted write path found.
- **AC 7:** `ruff check` + `ruff format --check` clean; `mypy --strict src/` clean
  (64 files); committed through the `build-plugin-sync` pre-commit hook (no `--no-verify`).
- **AC 8:** 12 new tests across 5 files, all `is True`/`is False` assertions. Full suite
  **1174 passed, 0 failed, 0 skipped** (baseline 1136 at epic-5 retro + importer-gate tests +
  this story's 12 — no regressions).
- Import-tool commander test uses seeded-fixture Counterspell as the Commander-section card
  (fixture has no Atraxa); coverage is identical to the story's example.

### File List

- src/data/models/deck_card.py (modified — commander column + docstring/repr)
- src/data/schemas/deck.py (modified — DeckCard + DeckCardSummary commander field)
- src/data/repositories/deck.py (modified — add_card_to_deck param; merge_decks propagation)
- src/mcp_server/tools/deck_management.py (modified — helper param + _deck_detail projection)
- src/mcp_server/server.py (modified — registered add_card_to_deck param; import_decklist docstring)
- src/mcp_server/tools/deck_import.py (modified — _ParsedArenaLine.commander, line-result field, pass-through)
- scripts/migrate_add_deck_card_commander.py (new — additive idempotent migration)
- tests/unit/data/models/test_deck_card.py (modified — 2 new tests)
- tests/unit/data/schemas/test_deck.py (modified — 4 new tests)
- tests/integration/data/test_deck_repository.py (modified — 4 new tests)
- tests/integration/mcp_server/test_deck_management_tool.py (modified — 1 new test)
- tests/integration/mcp_server/test_deck_import_tool.py (modified — 1 new test)
- plugin/server/src/data/models/deck_card.py (generated — build-plugin-sync mirror)
- plugin/server/src/data/schemas/deck.py (generated — build-plugin-sync mirror)
- plugin/server/src/data/repositories/deck.py (generated — build-plugin-sync mirror)
- plugin/server/src/mcp_server/tools/deck_management.py (generated — build-plugin-sync mirror)
- plugin/server/src/mcp_server/server.py (generated — build-plugin-sync mirror)
- plugin/server/src/mcp_server/tools/deck_import.py (generated — build-plugin-sync mirror)
- _bmad-output/implementation-artifacts/6-1-commander-flag-end-to-end.md (this story file)
- _bmad-output/implementation-artifacts/sprint-status.yaml (status tracking)

## Change Log

- 2026-07-16: Story 6.1 implemented — commander flag end-to-end (model, schemas, idempotent
  migration run live + no-op re-run, repository + merge propagation, MCP tool layer, Arena
  Commander-section import). 12 new tests; full suite 1174 passed. Status → review.
