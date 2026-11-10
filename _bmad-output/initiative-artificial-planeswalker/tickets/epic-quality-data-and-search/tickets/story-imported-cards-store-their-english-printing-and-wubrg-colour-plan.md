---
title: 'Imported cards store their English printing and WUBRG colours'
type: 'bugfix'
ticket: '5'
created: '2026-11-10'
status: done
baseline_revision: 'ef32f517be5c45109e2460fe5d39c01476b2a4ee'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The import picks a card's canonical printing by date alone, so 91 cards in the real `cards.db` are stored in a non-English printing (`B3-D1`). It copies Scryfall's alphabetical colour lists verbatim, so 5,350 `color_identity`, 4,162 `colors` and 1 `color_indicator` rows are out of WUBRG order (`B3-P1`). Its reconcile merge drops a stale row's `commander=True` and never checks the summed quantity against the 250-copy cap (`B3-P3`).

**Approach:** Use review option (a): an English printing outranks any other, then the latest `released_at`, then the smallest `id`. The transformer stores `colors`, `color_identity` and `color_indicator` in WUBRG order. The reconcile merge ORs the commander flag onto the canonical row and caps the summed quantity at `MAX_CARD_QUANTITY`, logging a warning when it caps. Existing databases need no connect hook: the next `initialize_database(update=true)` upserts the sorted colours and repoints the non-English rows through the existing reconcile.

## Boundaries & Constraints

**Always:** WUBRG ordering keeps any letter outside WUBRG, after the five and in its original order (the transformer never drops data). A missing `lang` counts as English, so fixtures without `lang` rank exactly as before. Tests drive the real orchestrator (`import_through_orchestrator` / `serve_bulk_file`) and the real `initialize_database` entry point, against tmp-path databases only. Each new test fails with its fix reverted, and the committed probe harness proves it.

**Never:** No full preference order (option b: digital, promo). No connect-hook repair and no `scripts/migrate_*.py` (no DDL). No rewrite of the `card_faces` JSON: `CardFace` is served "exactly as Scryfall publishes it". No change to `merge_decks`, whose kept-target commander rule is a user-facing design. No touching the real data directory, except read-only (`mode=ro`) counts.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Same-day non-English first | ja printing (smaller id) and en printing, same `released_at` | en printing is canonical | none |
| Newer non-English | ja 2025, en 2020 | en printing is canonical | none |
| No English printing | two ja printings | latest date, then smallest id (unchanged rule) | none |
| Out-of-order colours | `colors` `["G","U"]`, identity `["B","G","R","U","W"]`, indicator `["G","U"]` | stored `["U","G"]`, `["W","U","B","R","G"]`, `["U","G"]` | none |
| Null indicator / unknown letter | `color_indicator` absent; a list with `"X"` | stays `None`; `"X"` kept after WUBRG | none |
| Merge with stale commander | deck holds stale (commander, qty 1) and canonical (qty 1) | one canonical row, commander true, qty 2 | none |
| Merge over the cap | stale 200 plus canonical 100 | qty 250 and a WARNING naming the deck and card | none |
| Existing DB repaired | old-state DB: ja canonical row, unsorted colours, deck commander on the ja row | after `initialize_database(update=true)`, `cards` rows equal a fresh import's, and the deck row points at the en id with its commander flag kept | none |

</frozen-after-approval>

## Code Map

- `src/data/importers/aggregate.py:22-37,88-136` -- `OracleAggregate` and `build_oracle_aggregates`: the only canonical pick. Add the canonical printing's English-ness to the aggregate and rank (english, released_at), then the smallest id. Update both docstrings.
- `src/data/importers/scryfall.py:110-146` `iter_canonical_models` -- keeps only `canonical_id`; it needs no change.
- `src/data/importers/transformers.py:46-47,138-150,296-304` -- `_WUBRG` and `_face_color_union` exist. Add one ordering helper and apply it to the three top-level lists, including the face-derived path. `card_faces` stays verbatim.
- `src/data/importers/scryfall.py:257-318` `reconcile_oracle_identities` -- the deck_cards scan selects no `commander`. Add it, carry `stale_commander` into `merges`, set `commander=True` on the canonical row when the stale row had it, and cap with `func.min(DeckCardModel.quantity + quantity, MAX_CARD_QUANTITY)`. Track planned sums per target key, because several stale printings can merge into one row, and log one lazy %-style warning per capped row. Repoints already keep the flag.
- `src/mcp_server/tools/deck_management.py:53-55` -- `MAX_CARD_QUANTITY = 250` lives here, but `src/data` cannot import `mcp_server`. Move the constant and its comment to `src/data/schemas/deck.py`, which already names it in docstrings. `deck_management` imports it from there, and `deck_import` keeps importing it from `deck_management`.
- `tests/fixtures/scryfall_sample.json` -- the sample bulk file. Append: a Transguild Courier-like card with alphabetical `colors`, `color_identity` and `color_indicator`, and one card with a same-day `ja` printing (smaller id, `printed_name`) listed before its `en` printing, both with `lang`. Indices 0-5 stay put.
- `tests/unit/data/importers/test_parser.py:15`, `tests/integration/data/test_scryfall_import_e2e.py:29-50` -- counts that grow with the appended printings.
- `tests/unit/data/importers/test_aggregate.py` -- `_printing(**extra)` accepts `lang=`. Add the three ranking matrix rows here.
- `tests/unit/data/importers/test_transformers.py` -- add the colour-ordering and null/unknown rows.
- `tests/integration/data/test_scryfall_import_e2e.py:438-470` -- the merge test pattern (`create_om1_spm_cards`, `_snapshot_b`). Add the commander and cap merges beside it.
- `tests/fixtures/scryfall_bulk.py` `serve_bulk_file` and `src/mcp_server/tools/initialize_database.py` -- the existing-DB test points `CARDS_DATABASE_URL` at a tmp file, seeds the old state and calls `initialize_database(update=True)` with the real importer behind `serve_bulk_file`.

## Tasks & Acceptance

**Execution:**
- [ ] `tests/...` (as above) -- write the matrix tests first and see each one fail on the baseline -- tests-first rule.
- [ ] `src/data/schemas/deck.py`, `src/mcp_server/tools/deck_management.py` -- move `MAX_CARD_QUANTITY` -- the data layer needs it.
- [ ] `src/data/importers/aggregate.py` -- English-first canonical pick.
- [ ] `src/data/importers/transformers.py` -- WUBRG ordering of the three lists.
- [ ] `src/data/importers/scryfall.py` -- commander OR and the quantity cap in the merge, plus a docstring note.
- [ ] `plugin/` -- `uv run python -m scripts.build_plugin`, commit the result.

**Acceptance Criteria:**
- Given the sample bulk file, when it is imported through the orchestrator, then every stored card's `colors`, `color_identity` and `color_indicator` is WUBRG-ordered, and the card whose first printing is `ja` stores its `en` id and no `printed_name`.
- Given the full gate, when it runs, then everything is green, and each new test is proved red with its fix reverted through `scripts.probe_harness`.

## Implementation Notes

- Tests first: on the baseline, 12 new nodes failed on their own assertions. The no-English ranking row (`test_without_an_english_printing_the_date_then_id_rule_holds`) passes on the baseline by design. It guards the unchanged rule, so it cannot go red with the fix reverted.
- `MAX_CARD_QUANTITY` moved to `src/data/schemas/deck.py`. `deck_management`, `deck_import` and `test_deck_management_tool.py` import it from there; there is no re-export.
- `_wubrg_ordered(list[str]) -> list[str]` is a stable sort that ranks any non-WUBRG letter after the five. An absent `color_indicator` stays `None` at the call site. `_face_color_union` builds a union in first-seen order and sorts it with the helper. Before this change it dropped non-WUBRG letters.
- The reconcile keeps the uncapped running sum per `(deck, card, sideboard)` key and the set of keys that received a merge. The SQL `min(quantity + n, 250)` caps each merge step, so the stored total is the capped total. After the commit it logs one warning per merged key over the cap, giving the full sum and the copies dropped.
- The existing-DB test compares against a fresh import, so it also asserts the repaired Courier row is WUBRG-ordered. Without that, it stayed green with the transformer reverted, because both sides were equally unsorted.
- Fixture rows appended at indices 6-8: Transguild Courier (alphabetical lists), then the ja and en Counterspell (same day, ja id smaller, ja listed first). Pass 2 skips the ja printing, so `total_processed` is 8.
- Grep for the patterns: the other WUBRG orderings (`src/data/database.py:158`, `src/data/repositories/deck.py:872`) were already WUBRG. `merge_decks` keeps the target's commander flag by documented design and is out of scope. `card_faces` colours stay as Scryfall sends them, per the `CardFace` contract.
- Real `cards.db`, read strictly read-only (`sqlite3` `mode=ro`) on 2026-11-10, before any update: 39,503 cards. Out of WUBRG order: 5,350 `color_identity`, 4,162 `colors` and 1 `color_indicator`. 91 rows have a non-ASCII `printed_name`, and 27 `deck_cards` rows point at a card with a `printed_name`. Out of order inside `card_faces` (left as is): face `colors` on 113 cards and face `color_indicator` on 68.

Probe-harness proof lines (tree staged first; each plant restored from the index with `git diff --exit-code` clean):

- P1, `aggregate.py` reverted to `ef32f51`: `full suite (-m 'not integration'): 3351 collected, 5 failed, 0 errored, exit 1`, harness exit 0. Red: the three aggregate English rows, `test_end_to_end_import`, and `test_update_repairs_a_database_imported_before_the_english_first_rank`.
- P2, `transformers.py` reverted to `ef32f51`: `full suite (-m 'not integration'): 3351 collected, 6 failed, 0 errored, exit 1`, harness exit 0. Red: the four transformer colour rows, `test_end_to_end_import`, and the existing-DB repair test.
- P3, commander OR removed: `full suite (-m 'not integration'): 3351 collected, 1 failed, 0 errored, exit 1`, harness exit 0. Red: `test_reconcile_merge_keeps_the_stale_rows_commander_flag`.
- P4, warning sum taken from the capped running total (the `d2b0a54` behaviour): `full suite (-m 'not integration'): 3351 collected, 1 failed, 0 errored, exit 1`, harness exit 0. Red: `test_reconcile_merge_caps_the_summed_quantity[canonical-and-two-stale]`.
- P5, SQL cap removed: `full suite (-m 'not integration'): 3351 collected, 3 failed, 0 errored, exit 1`, harness exit 0. Red: all three `test_reconcile_merge_caps_the_summed_quantity` params.

Gate on the final tree: ruff check and format are clean, and mypy is clean both native and with `--platform win32`. `uv run pytest` gave 3376 passed and 2 skipped. `scripts.build_plugin` rebuilt `plugin/` and the result is committed.

## Plan Change Log

## Review Triage Log

Pass 1, lens `quick`: 3 findings, 3 `medium`, 0 false. All three routed to patch, and all were already queued follow-ups to the reviewer-side fixes made after `d2b0a54`. Those fixes were: the running-sum warning, the typed `_wubrg_ordered`, the dropped re-export, and an exact warning assertion with a third cap case.

| # | Finding | Verdict | Route | Evidence / action |
|---|---------|---------|-------|-------------------|
| 1 | `plugin/` was stale after the working-tree edits to four `src/` files | medium | patch | Real: the reviewer ran before the rebuild. Re-ran `scripts.build_plugin`, and its four mirrored files are in the commit. |
| 2 | The probe proofs predate the third cap parameter and the running-sum fix | medium | patch | Real. Re-proved through the harness (P1-P5 above); P4 targets the new case. |
| 3 | Implementation Notes and Code Map describe the removed re-export and the `None` passthrough | medium | patch | Real for the notes, which are rewritten above. The Code Map line says `deck_import` "keeps importing it from `deck_management`", which is now stale. The plan's design intent is unchanged, so the note above records the deviation. |

## Design Notes

The cap is the review's "cap or report", resolved as both. Every tool write path enforces 250 copies, and a reconcile is no user intent to exceed it. The warning names what was dropped. Real decks never reach it (it needs two printings at more than 125 each). It is the cheapest choice that keeps the invariant, and it is flagged for Brad.

Ranking sketch (aggregate):

```python
candidate = (is_english, released_at)
current = (aggregate.canonical_is_english, aggregate.canonical_released_at)
replaces = candidate > current or (candidate == current and card_id < aggregate.canonical_id)
```

## Verification

**Commands:**
- `uv run ruff check .` / `uv run ruff format --check .` -- clean
- `uv run mypy src/` and `uv run mypy src/ --platform win32` -- clean
- `uv run pytest` -- all green
- `uv run python -m scripts.probe_harness --expect-red '<node>'` with each fix reverted in turn -- harness reports the expected nodes red
- `uv run python -m scripts.build_plugin` then `git status --porcelain plugin/` -- the rebuilt tree is committed
