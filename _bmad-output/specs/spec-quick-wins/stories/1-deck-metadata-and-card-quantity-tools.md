---
title: 'Deck metadata and card-quantity tools'
type: 'feature'
created: '2026-09-06'
status: 'done'
baseline_revision: '26bccfd2e49d1cd3f091552acb614c722b35039b'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** `DeckRepository.update_deck` and `update_card_quantity` exist, but no MCP tool exposes them: an agent cannot rename a deck, set or clear its strategy/tags, or set a card to N copies without a remove-then-add dance (CAP-1, CAP-2 of the quick-wins spec).

**Approach:** Add two stateless MCP tools, `update_deck` and `set_card_quantity`, in the `deck_management.py` helper + `server.py` wrapper shape of `add_card_to_deck` / `remove_card_from_deck`, emitting `deck_changed` after a successful write. `update_deck` takes a nested `changes` object so "omitted" (field absent) and "cleared" (field null) stay distinct across JSON-RPC (FastMCP flattens top-level params, so only `model_fields_set` on a nested model preserves that). `set_card_quantity` routes quantity 0 to removal.

## Boundaries & Constraints

**Always:**
- Both tools are stateless (`deck_id` per call), live in `src/mcp_server`, and emit `deck_changed` only on `status == "ok"`, after the session block closes, via `_emit_deck_changed` exactly like the existing wrappers.
- `update_deck` maps `changes`: field absent from `model_fields_set` → repository `_UNSET`; `strategy`/`tags` present as null → `None` (clear); `name` present → must be non-blank. Bounds reuse `MAX_DECK_NAME_CHARS`, `MAX_STRATEGY_CHARS`, `MAX_TAGS`, `MAX_TAG_CHARS`.
- `set_card_quantity` uses the card_id-or-name selector (`_blank_to_none`, `_selector_error`, `resolve_card`) and the shared message helpers; quantity 0 calls the repository's `remove_card_from_deck`; 1..`MAX_CARD_QUANTITY` calls `update_card_quantity`; it never adds a card.
- Repository `quantity >= 1` contract stands; the tool never passes 0 to `update_card_quantity`.
- Tests drive the real entry points (`build_server` + in-process MCP client), never the repository directly, and never scan source text.
- Ripple in the same change: skills that enumerate deck-management tools, `README.md` tool table, `docs/architecture.md` tool list, `CHANGELOG.md` `[Unreleased]`, `plugin/` rebuild, and every hand-pinned tool-name set in tests.
- Log calls use lazy %-args; timestamps stay aware UTC; no schema change, no migration.

**Block If:**
- A tool cannot distinguish omitted from null at the MCP surface with the nested-object approach (proven to work on mcp 1.28.0 during planning).
- `deck_changed` wiring requires per-session server state to satisfy.

**Never:**
- Merge quantities on add, change `add_card_to_deck` / `remove_card_from_deck` behaviour, or touch `src/viewer/`, `src/companion/` or the frozen `view_deck`.
- Add legality, copy-limit or deck-size checks to either tool (analysis stays in `validate_deck`).
- Expose `update_deck_color_identity` or `merge_decks`; clone/export are later stories.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Rename only | `update_deck(deck_id, changes={"name": "New"})` | `ok`; `deck.name == "New"`; strategy and tags unchanged; `updated_at` advances; one `deck_changed` | No error expected |
| Omit strategy | `changes={"tags": ["a"]}` on a deck with strategy "S" | `ok`; strategy still "S"; tags `["a"]` | No error expected |
| Clear strategy | `changes={"strategy": null}` | `ok`; `deck.strategy is None` | No error expected |
| Clear tags | `changes={"tags": null}` | `ok`; `deck.tags == []` | No error expected |
| Unknown deck | `update_deck("nope", changes={"name": "x"})` | `not_found`; no emit | Graceful status |
| Empty changes | `changes={}` | `invalid` ("nothing to change"); no write, no emit | Graceful status |
| Blank or null name | `changes={"name": "  "}` or `{"name": null}` | `invalid`; no write | Graceful status |
| Over-bound field | name > 100 chars, strategy > 2000, > 20 tags, tag > 50 chars | `invalid` naming the field | Graceful status |
| Set quantity | deck has 4 Bolt mainboard; `set_card_quantity(deck_id, card_id, quantity=3)` | `ok`; `load_deck` shows 3; `updated_at` advances; one emit | No error expected |
| Same quantity | stored 4; `quantity=4` | `unchanged`; no write, no emit, `updated_at` untouched | No error expected |
| Quantity 0 | stored 4; `quantity=0` | `ok`; row gone from `load_deck`; colour identity and `updated_at` refreshed; one emit | No error expected |
| Absent from board | card known, not in that board (either board flag), any quantity incl. 0 | `card_not_found`; card not added; no emit | Graceful status |
| Unknown card | `card_id="nope"` or unmatched name | `card_not_found`; no emit | Graceful status |
| Ambiguous name | `name="bolt"` matches >1 | `ambiguous` with `matches`; no emit | Graceful status |
| Bad quantity / selector | `quantity=-1` or `> 250`; both/neither of `card_id`/`name` | `invalid`; no emit | Graceful status |
| Unknown deck | `set_card_quantity("nope", ...)` | `deck_not_found`; no emit | Graceful status |
| DB error mid-write | repository raises `DatabaseError` | `error`; session rolled back; no emit | Logged with `logger.exception` |
| Uninitialised DB | either tool before `initialize_database` | `database_not_initialized`; no emit | Graceful status |

</intent-contract>

## Code Map

- `src/mcp_server/tools/deck_management.py` -- helpers + result models. Reuse `_blank_to_none` (133), `_selector_error` (141), `resolve_card` (186), `ambiguous_message`/`card_not_found_message` (158-170), bounds constants (43-49), `_create_deck_validation_error` (265, extract shared bound checks). `DeckCardResult` status Literal (99-131) gains `unchanged` and an optional `quantity: int | None` field; `DeckResult` (69) is the `update_deck` result. `add_card_to_deck` (410-515) is the shape to copy. Module docstring says "six helpers" — update it.
- `src/data/repositories/deck.py` -- `_UNSET` (24); `update_deck` (145-208: `name=None` means omitted; commits even when nothing changed; **no rollback on `DatabaseError`** — add the try/rollback/re-raise the other writers use); `update_card_quantity` (592-669: returns `None` when the row is absent, returns the row unchanged with a rollback when the quantity matches, raises `ValueError` below 1); `remove_card_from_deck` (538) returns `False` when no row; `get_deck_with_cards` reloads a `DeckDetail`-ready deck.
- `src/mcp_server/server.py` -- `_emit_deck_changed` (123-153) and wrappers `delete_deck`/`add_card_to_deck`/`remove_card_from_deck` (342-472): `async with session_factory()` then emit outside the block on `ok`. Helper imports at 93-107. The docstring of a wrapper is the LLM-facing description.
- `tests/integration/test_mcp_tools.py` -- in-process client pattern (`test_deck_lifecycle_through_client`, 158); `ROUND_TRIPPED` (1751) is hand-pinned and `test_every_registered_tool_has_a_round_trip` fails on a new tool until a round trip and an entry exist.
- `tests/integration/test_build_plugin.py` -- pinned registered-tool name set (267-292).
- `tests/integration/mcp_server/test_deck_changed_wiring.py` -- `TestEachPersistedWriteEmitsExactlyOnce` (204) and `test_every_drivable_no_write_status_is_silent` (312) are the emit-once / silent-on-no-write rows to extend for both tools; fixtures `deck_db`, `notifier`.
- `tests/unit/companion/test_import_boundary.py` -- `_REPO_WRITE_METHODS` (74) already lists `update_deck` and `update_card_quantity`; nothing to add, but the companion must not import the new helpers.
- `.claude/skills/magic-deckbuilding/SKILL.md` -- tool table (156-168) and Step 5 apply guidance (126-141, `exists` → "adjust the quantity" now names `set_card_quantity`). Other skills mention `add_card_to_deck` in prose only (`format-legality` 427-429, `mana-curve-analysis` 219/284-286, `synergy-discovery` 260-266, `companion` none); grep each and edit only where it enumerates write tools.
- `README.md:25` deck-management tool row; `docs/architecture.md:109` tool list; `CHANGELOG.md:8` `[Unreleased]`.
- `scripts/build_plugin.py` -- run `uv run python -m scripts.build_plugin` after the change; CI fails on drift.

## Tasks & Acceptance

**Execution:**
- `src/data/repositories/deck.py` -- wrap `update_deck`'s write in the try/`rollback`/re-raise pattern of `update_card_quantity` -- repository convention for writers.
- `src/mcp_server/tools/deck_management.py` -- add `DeckMetadataUpdate(BaseModel)` (`name`, `strategy`, `tags`, all optional, default None), `update_deck(session, *, deck_id, changes)` returning `DeckResult` (reload via `get_deck_with_cards` so counts are right), and `set_card_quantity(session, *, deck_id, card_id, name, quantity, sideboard)` returning `DeckCardResult`; extend `DeckCardResult` with `unchanged` and `quantity`; point `card_exists_message` at `set_card_quantity`; update the module docstring -- the CAP-1/CAP-2 logic.
- `src/mcp_server/server.py` -- register `update_deck(deck_id: str, changes: DeckMetadataUpdate)` and `set_card_quantity(deck_id, card_id=None, name=None, quantity: int, sideboard=False)` wrappers with LLM-facing docstrings (state the omitted-vs-null rule and the 0-removes rule); emit on `ok` outside the session block -- wiring.
- `tests/integration/test_mcp_tools.py` -- round trips covering every matrix row through `client.call_tool`, `updated_at` compared via `load_deck` before/after, add both names to `ROUND_TRIPPED` -- behaviour proof.
- `tests/integration/mcp_server/test_deck_changed_wiring.py` -- emit-once rows for both tools' `ok`; silent rows for `not_found`/`invalid`/`unchanged`/`card_not_found`/`ambiguous`/`deck_not_found` -- AD-9 promise.
- `tests/integration/test_build_plugin.py` -- add both names to the pinned set -- guard.
- `.claude/skills/magic-deckbuilding/SKILL.md` (+ any other skill that enumerates write tools), `README.md`, `docs/architecture.md`, `CHANGELOG.md` -- document both tools, params and status vocabulary -- skills ripple site.
- `plugin/` -- `uv run python -m scripts.build_plugin` and commit the emitted tree -- generated artifact.

**Acceptance Criteria:**
- Given the MCP server, when the client lists tools, then `update_deck` and `set_card_quantity` are present and every registered tool still has a round trip.
- Given a deck with strategy "S" and tags `["a"]`, when the client calls `update_deck` with `changes={"name": "N"}`, then the reloaded deck has name "N", strategy "S", tags `["a"]` and a later `updated_at`, and the notifier stub received the deck id exactly once.
- Given a deck with 4 Bolt mainboard, when the client calls `set_card_quantity` with quantity 0, then `load_deck` no longer lists Bolt and the deck's `color_identity` and `updated_at` reflect the removal.
- Given a card not in the requested board, when the client calls `set_card_quantity`, then the status is `card_not_found`, the deck's cards are unchanged and nothing was emitted.
- Given the shipped skills and plugin, when `uv run python -m scripts.build_plugin` runs after the docs edits, then `git status` shows no further plugin drift and the magic-deckbuilding table names both tools.

## Spec Change Log

## Review Triage Log

### 2026-09-06 — Review pass
- intent_gap: 0
- bad_spec: 0
- patch: 5: (high 1, medium 2, low 2)
- defer: 0
- reject: 18: (high 0, medium 3, low 15)
- addressed_findings:
  - `[high]` `[patch]` `set_card_quantity` defaulted `quantity` to 1, silently trimming a card to one copy when omitted; made required in wrapper, helper and skill table, with a client test that omission is rejected and writes nothing.
  - `[medium]` `[patch]` `DeckMetadataUpdate` ignored unknown keys (a typo became "nothing to change" or a partial write); `extra="forbid"` plus a client test.
  - `[medium]` `[patch]` No test wrote to a sideboard row while the card was also in the mainboard, so a board-blind entry predicate would have passed; added the two-board test (ok / ok-not-unchanged / unchanged).
  - `[low]` `[patch]` A blank strategy string was stored verbatim; it now clears like null, documented and tested.
  - `[low]` `[patch]` Test hygiene: aware pinned `updated_at` with parsed comparisons, exact invalid messages per tag case, module-level `DatabaseError` import, a call-recording assertion on the patched repository method, and a "row vanished after the pre-read" row proving `card_not_found` and silence.
- rejected (reasons): `plugin/` absent from the review diff (excluded on purpose, rebuilt and committed); `_UNSET` import across the data→mcp_server boundary (sanctioned direction, project names it so); blank/duplicate tags and unstripped name helper (matches `create_deck`, no spec ask); full-deck pre-read cost (≤100 rows); helper/repository double no-op check (deliberate, needed for `unchanged`); wrapper `Returns:` omitting `error`/`database_not_initialized` (matches sibling wrappers); `unchanged` on the shared model (documented per tool); rollback test ORM-state assertion; emitter list in docs; CHANGELOG `IntegrityError` wording; other skills (auditor confirmed they stay true); `update_deck` lacking an `unchanged` branch (no spec row; a write does land); concurrent-delete races on a single-writer local SQLite; repository blank-name / non-DatabaseError handling (pre-existing); docs/plugin-structure listing; success message listing sent fields.

## Design Notes

- Nested `changes` is deliberate: FastMCP validates top-level params into a model and `model_dump_one_level()`s them, so a flat `strategy: str | None = None` cannot tell null from omitted; a nested Pydantic field keeps `model_fields_set`. Probe run in planning: `{"changes": {"strategy": null}}` → fields_set `{"strategy"}`; `{"changes": {}}` → `set()`.
- Absent-from-board answers `card_not_found` (the SPEC's stated success criterion), even though `remove_card_from_deck` says `not_in_deck` for the same state; the message should say in words that the card is not in that board and that `add_card_to_deck` adds it.
- `unchanged` exists so the emit predicate stays "status == ok ⇔ a write landed"; the repository already treats an equal quantity as a rollback no-op.

## Verification

**Commands:**
- `uv run ruff check . && uv run ruff format --check .` -- expected: clean
- `uv run mypy src/ && uv run mypy src/ --platform win32` -- expected: no issues
- `uv run pytest` -- expected: all pass (the seeded DB fixtures build their own database; integration-marked tests may skip if the card database is absent)
- `uv run python -m scripts.build_plugin && git status --short plugin/` -- expected: plugin rebuilt, then no drift after commit

## Auto Run Result

Status: done

**Summary:** Two new stateless MCP tools. `update_deck(deck_id, changes)` renames a deck and sets or clears strategy/tags; `changes` is a nested object with `extra="forbid"`, omitted fields map to `_UNSET`, null (or a blank strategy) clears. `set_card_quantity(deck_id, quantity, card_id|name, sideboard)` sets an absolute count, `0` removes, an equal count answers `unchanged` without a write, a card absent from that board answers `card_not_found` and is never added. Both emit `deck_changed` on `ok` only. The repository's `update_deck` now rolls back on `DatabaseError` like the other writers.

**Files changed:**
- `src/data/repositories/deck.py` -- `update_deck` try/rollback/re-raise.
- `src/mcp_server/tools/deck_management.py` -- `DeckMetadataUpdate`, `update_deck`, `set_card_quantity`, shared `_metadata_bounds_error`, `DeckCardResult.unchanged` + `quantity`, `card_exists_message` points at the new tool.
- `src/mcp_server/server.py` -- the two wrappers with LLM-facing docstrings and emit wiring.
- `tests/integration/test_mcp_tools.py` -- 15 client-driven tests over every matrix row; `ROUND_TRIPPED` extended.
- `tests/integration/mcp_server/test_deck_changed_wiring.py` -- emit-once, silent-on-no-write, uninitialised, DB-error and vanished-row rows for both tools.
- `tests/integration/data/test_deck_repository.py` -- `update_deck` rollback proof.
- `tests/integration/test_build_plugin.py` -- pinned name set extended.
- `.claude/skills/magic-deckbuilding/SKILL.md`, `README.md`, `docs/architecture.md`, `docs/plugin-structure.md`, `CHANGELOG.md` -- documentation ripple; `plugin/` rebuilt.

**Review findings:** 5 patched (high 1, medium 2, low 2), 0 deferred, 18 rejected; no intent gap or bad_spec.

**Follow-up review recommendation:** true — one patched finding was high severity (score 3×2 + 2 = 8 ≥ 5 as well).

**Verification:** `ruff check` clean, `ruff format --check` clean, `mypy src/` and `--platform win32` clean, `pytest` 3281 passed / 1 skipped (after patches; 3274 before), `scripts.build_plugin` rebuilt with only the five mirrored files changed.

**Residual risks:**
- `card_not_found` now means both "unknown card" and "known card not in that board" for `set_card_quantity`, while `remove_card_from_deck` says `not_in_deck` for the latter; this follows the SPEC wording and is documented in the skill table.
- The wiring test's module docstring still describes an "enumeration half" guard that no longer exists in the file (pre-existing drift, untouched).
- `update_deck` has no `unchanged` branch: sending a value equal to the stored one still writes, bumps `updated_at` and emits.
