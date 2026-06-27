---
title: 'Power/Toughness display in the read-only HTML deck viewer'
type: 'feature'
created: '2026-06-27'
status: 'done'
baseline_commit: '0efc057'
context: ['{project-root}/_bmad-output/project-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The read-only HTML deck viewer renders card tiles with name, mana pips, quantity, rarity, and type line, but never shows power/toughness. Worse, P/T is dropped at import time (`transform_scryfall_card` ignores Scryfall's `power`/`toughness`), so it isn't in `cards.db` for single-faced creatures at all — only DFCs retain it nested in `card_faces`.

**Approach:** Plumb `power`/`toughness` end-to-end (ORM model → transformer → batch upsert → Pydantic schema → view model → template), add an idempotent `ALTER TABLE` migration, then re-import Scryfall `oracle_cards` to backfill P/T for the existing corpus. Render P/T as a bottom-right corner badge on creature/vehicle tiles, relocating the ×qty badge to the top-left to avoid overlap.

## Boundaries & Constraints

**Always:** Match existing conventions — `Mapped[...]` + `mapped_column` dataclass-init style, repos return Pydantic schemas, Google-style docstrings, `mypy --strict` clean. New columns are nullable (`str | None`, default `None`). P/T renders only when both values are present; non-creatures omit it. Viewer's `_face_value` DFC fallback pattern is reused for double-faced creatures.

**Ask First:** Any change to the embedded-text recipe or a `card_vec` rebuild (not needed here — P/T is not in the embedding text). Any destructive DB operation beyond the in-place upsert re-import.

**Never:** Don't add P/T to `CardSummary` (search-tool projection, out of scope). Don't wipe/recreate `cards.db` (re-import upserts by id, preserving `card_vec` + decks). Don't touch `legacy/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Single-faced creature | `power="2"`, `toughness="2"` | view-model `pt="2/2"`; corner badge rendered | N/A |
| Non-creature (instant/land) | `power=None`, `toughness=None` | `pt=None`; no badge | N/A |
| DFC creature | top-level P/T `None`, `card_faces[0]` has P/T | `pt` derived via `_face_value` fallback | N/A |
| Variable P/T (`*`) | `power="*"`, `toughness="*"` | `pt="*/*"` rendered verbatim | N/A |
| Vehicle | has P/T, type line "Artifact — Vehicle" | `pt` rendered (P/T present, not creature-gated) | N/A |
| Existing DB pre-backfill | columns absent | migration adds nullable columns; rows `NULL` until re-import | migration idempotent (skip if column exists) |

</frozen-after-approval>

## Code Map

- `src/data/models/card.py` -- `CardModel`; add `power`/`toughness` `Mapped[str | None]` columns
- `src/data/schemas/card.py` -- `Card` schema; add `power`/`toughness: str | None = None`
- `src/data/importers/transformers.py` -- `transform_scryfall_card`; extract Scryfall `power`/`toughness`
- `src/data/importers/importer.py` -- `_insert_batch`; add P/T to `card_dict` + `on_conflict_do_update` set
- `src/viewer/view_model.py` -- `_build_card`; derive `pt` (with `_face_value` DFC fallback), add to dict
- `src/viewer/template.html` -- `cardHtml`; relocate qty badge to top-left, add bottom-right P/T badge
- `scripts/migrate_add_power_toughness.py` -- new idempotent `ALTER TABLE cards ADD COLUMN` migration (mirror `scripts/migrate_add_*.py`)
- `tests/unit/viewer/test_deck_view_model.py` -- extend `make_card` with P/T kwargs; assert `pt`
- `tests/unit/data/importers/` -- transformer test asserting P/T extraction (create if absent)

## Tasks & Acceptance

**Execution:**
- [x] `src/data/models/card.py` -- add `power`/`toughness` nullable columns (`kw_only=True, default=None, init=True`, matching `printed_name`) -- capture P/T at ORM layer
- [x] `src/data/importers/transformers.py` -- `power = card_json.get("power")`, `toughness = card_json.get("toughness")`; pass to `CardModel(...)` -- stop dropping P/T on import
- [x] `src/data/importers/importer.py` -- add `power`/`toughness` to `card_dict` and the `set_` of `on_conflict_do_update` -- upsert must write the new columns
- [x] `src/data/schemas/card.py` -- add `power`/`toughness: str | None = None` to `Card` -- surface P/T to callers
- [x] `src/viewer/view_model.py` -- in `_build_card`, `power = card.power or _face_value(card, "power")` (same for toughness); `pt = f"{power}/{toughness}" if power and toughness else None`; add `"pt": pt` -- expose P/T to template
- [x] `src/viewer/template.html` -- move ×qty badge to top-left (`top:28px;left:6px`); add P/T badge at former qty slot (`bottom:22px;right:6px`) gated on `c.pt` -- bottom-right corner display
- [x] `scripts/migrate_add_power_toughness.py` -- idempotent `ALTER TABLE cards ADD COLUMN power TEXT` + `toughness TEXT` (guard via `PRAGMA table_info`) -- prepare existing DB for backfill
- [x] `tests/unit/viewer/test_deck_view_model.py` -- add P/T kwargs to `make_card`; assert `pt` for creature, `None` for non-creature, DFC fallback path
- [x] transformer unit test -- assert `power`/`toughness` extracted from Scryfall JSON and `None` when absent
- [x] Run migration (done), then `uv run scripts/import_scryfall_data.py --type oracle_cards` to backfill P/T (re-import complete: 38,233 cards, 19,651 with P/T, 0 errors)

**Acceptance Criteria:**
- Given a deck with a single-faced creature, when `render_html` runs, then its tile shows a bottom-right `P/T` badge and the ×qty badge appears top-left.
- Given a non-creature card, when rendered, then no P/T badge appears.
- Given a DFC creature whose P/T lives in `card_faces`, when rendered, then P/T still displays via the `_face_value` fallback.
- Given the migration has run and the re-import completed, when a creature is looked up, then `Card.power`/`Card.toughness` are populated; `card_vec` and saved decks are unaffected.
- `uv run pytest`, `uv run ruff check .`, and `uv run mypy src/` all pass.

## Design Notes

P/T values are Scryfall **strings** (`"2"`, `"*"`, `"1+*"`), never ints — keep them `str`. Gate display on `power and toughness` (both truthy) so vehicles/creatures show and planeswalkers/lands/spells don't; this is more robust than parsing the type line. Re-import upserts every row by id (`INSERT ... ON CONFLICT(id) DO UPDATE`), so it refreshes all card fields to current Scryfall data as a side effect — desirable, and it leaves the `card_vec` virtual table (keyed by `card_id`) and deck rows untouched. Columns must exist before the upsert references them, so the migration runs *before* the re-import.

## Verification

**Commands:**
- `uv run pytest tests/unit/viewer/ tests/unit/data/` -- expected: all pass, including new P/T cases
- `uv run mypy src/` -- expected: no errors (nullable `str | None` columns/fields type-check)
- `uv run ruff check . && uv run ruff format --check .` -- expected: clean
- `uv run python scripts/migrate_add_power_toughness.py` -- expected: adds columns (idempotent on re-run)
- `uv run python scripts/import_scryfall_data.py --type oracle_cards` -- expected: completes; P/T populated

**Manual checks:**
- Render a deck containing a known creature (e.g. a 2/2) and a non-creature; open the HTML and confirm the corner P/T badge shows for the creature, the ×qty badge sits top-left, and no badge shows for the non-creature.

## Suggested Review Order

**Display logic (start here)**

- Entry point — derives `pt` with the DFC `_face_value` fallback; truthiness guard keeps "0", drops absent
  [`view_model.py:257`](../../src/viewer/view_model.py#L257)
- Tile badge — P/T at bottom-right, ×qty relocated to top-left, gated on `c.pt`
  [`template.html:80`](../../src/viewer/template.html#L80)
- Detail pane — P/T beside the type line (review patch: keep the big preview consistent with tiles)
  [`template.html:158`](../../src/viewer/template.html#L158)

**Data plumbing**

- Transformer stops dropping Scryfall `power`/`toughness` (kept as `None` for non-creatures)
  [`transformers.py:64`](../../src/data/importers/transformers.py#L64)
- Upsert writes both new columns — values dict + `on_conflict` set (else re-import wouldn't backfill)
  [`importer.py:124`](../../src/data/importers/importer.py#L124)
- ORM columns, nullable + `kw_only` to keep the dataclass init valid (mirrors `printed_name`)
  [`card.py:41`](../../src/data/models/card.py#L41)
- Pydantic schema surfaces P/T to callers
  [`card.py:34`](../../src/data/schemas/card.py#L34)

**Migration & tests**

- Idempotent `ALTER TABLE … ADD COLUMN` for the existing DB (re-import backfills the rows)
  [`migrate_add_power_toughness.py:41`](../../scripts/migrate_add_power_toughness.py#L41)
- View-model cases: creature, non-creature, "0", variable, DFC fallback, vehicle
  [`test_deck_view_model.py:269`](../../tests/unit/viewer/test_deck_view_model.py#L269)
- Transformer extraction + `None` for non-creatures
  [`test_transformers.py:256`](../../tests/unit/data/importers/test_transformers.py#L256)
