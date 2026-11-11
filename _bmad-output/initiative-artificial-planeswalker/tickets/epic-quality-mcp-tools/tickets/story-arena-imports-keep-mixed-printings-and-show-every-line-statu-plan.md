---
title: 'Arena imports keep mixed printings and show every line status'
type: 'bugfix'
ticket: '9'
created: '2026-11-11'
status: 'review'
baseline_revision: '8b60a1452ebc8029a4e02641a7ef8a3245354eaf'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Card rows are oracle identities, so `2 Island (ELD) 250` and `2 Island (THB) 251` in one Arena export resolve to one `card_id`; the second line answers `exists`, the deck comes back 2 Islands short and the import `partial` (B8-D1). The per-line `quantity < 1` and `> 250` branches are never driven by a test (B8-P5). `_line_result` maps each token to itself and turns any status it does not know into `error`, hiding a bug as a database-looking failure (B8-P14).

**Approach:** Pin today's behaviour first (commit 1, green on the old code), then sum the lines of one export that resolve to the same `(card_id, sideboard)` in one function, check the sum against `MAX_CARD_QUANTITY`, keep `exists` only for rows already in the deck (B8-D1 option a, a tool behaviour change), and build each line result directly instead of projecting a throwaway `DeckCardResult`.

## Boundaries & Constraints

**Always:** The summing rule lives in one function in `deck_import.py` that 2.4 can extend for its duplicate-line rules. Still one bulk write, one commit, one deck-changed emit. `imported_lines` counts lines answered `ok`; `imported_copies` sums their quantities. Lines keep source order and their own parsed quantity. The import docstring in `server.py`, the helper docstring and the result-model docstrings say the new rule; `plugin/` is rebuilt. Tests run on `tmp_path` databases (`seeded_card_db` plus a seeded Island); the real data directory is never touched.

**Never:** No change to the status tokens (D3: b), the 250-line pre-count (5.5), name resolution (5.6's resolver), name-only lines or other 2.4 rules, the companion, or the repository's bulk write. No new line-status token.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Mixed printings | `2 Island (ELD) 250`, `2 Island (THB) 251` under `Deck`, empty deck | both lines `ok`, status `ok`, one row of 4 Islands, `imported_lines` 2, `imported_copies` 4 | none |
| Same card, two boards | 2 Island in `Deck`, 1 Island in `Sideboard` | two rows (2 main, 1 side), no summing across boards | none |
| Commander and Deck | the same card under `Commander` and `Deck` | one mainboard row, summed, flagged commander | none |
| Sum past cap | lines for one card in one board totalling 251 (e.g. `200` + `51`) | every line of that card `invalid`, message names the total and the cap; none of its copies added; other cards import | none |
| Already in deck | card already in that board, named on two lines | both lines `exists`, stored quantity unchanged | none |
| Per-line bounds | a `0 …` or `251 …` line plus a valid line | that line `invalid`, the next line imported, deck otherwise unchanged | none |
| Unexpected status | the resolver answers a status the import does not handle | the import raises before any write; the MCP call answers `isError` with text naming the status; deck unchanged | not answered as a status (`tools/failures.py`: a bug surfaces as an MCP error) |

**Decisions (Brad, 2026-11-11):**
- Unexpected status (B8-P14): (a) fail loudly — raise before any write, surfacing as an MCP error naming the status; the branch is also exhaustive for mypy.
- Skills: (b) replace "There is no bulk-import tool" at `magic-deckbuilding/SKILL.md:57` with a line naming `import_decklist` for Arena-format lists, its line statuses, and `exists` = already in the deck.
- Plan size: keep the full plan (~2,100 tokens); no split.

</frozen-after-approval>

## Code Map

- `src/mcp_server/tools/deck_import.py:291-340` -- `_error_line` stays; `_line_result` and its `elif` chain go. Add a direct builder for a resolved line (from `_ParsedArenaLine` + status/card/matches/message).
- `deck_import.py:441-505` -- the resolve loop. Split into: pass 1 resolves every parsed line (ambiguous / not_found / error decided here, found lines held with their card); pass 2 is the new summing function over found lines grouped by `(card.id, sideboard)` in first-seen order, against `occupied` (rows already in the deck, now only those). It returns the per-line results and the `DeckCardEntry` list (summed quantity, `commander` = any line's). `DeckCardEntry` is built only after the cap check (it rejects < 1, not > 250).
- `deck_import.py:507-565` -- the failure arms swap every `ok` line to `_error_line`; counts come from `ok` lines. `deck_import.py:345-358` helper docstring.
- `src/mcp_server/tools/deck_management.py:224-235` -- `card_exists_message`, `card_added_message` reused unchanged (shared with `add_card_to_deck`); the import appends its own "(N copies in all from lines a, b)" suffix for a summed line and its own over-cap wording.
- `src/mcp_server/server.py:592-618` -- `import_decklist` docstring: summing, `exists` = already in the deck, over-cap lines `invalid`.
- `.claude/skills/magic-deckbuilding/SKILL.md:57` -- the false "no bulk-import tool" sentence (Decisions).
- Tests: `tests/integration/mcp_server/test_deck_import_tool.py` (helper-level, `_WriteSpy`, `seeded_card_db`; the existing `..._same_card_twice_in_one_board_is_exists_on_the_second_line` pins the old rule and flips in commit 2); `tests/integration/test_mcp_tools.py:766` (client pattern for the unexpected-status test). Probe harness: `uv run python -m scripts.probe_harness --expect-red '<node id>'`; these files are not marked `integration`.

## Tasks & Acceptance

**Execution:**
- [x] `tests/integration/mcp_server/test_deck_import_tool.py` -- commit 1, green on the old code: per-line `0` and `251` parametrised (line `invalid`, next line imported, deck otherwise unchanged); the mixed-printing Island export pinned at today's `ok`/`exists`/`partial`/2 copies.
- [x] `src/mcp_server/tools/deck_import.py` -- direct line results, the summing function, the cap check, `exists` only for deck rows, the unexpected-status handling.
- [x] same test file -- flip the mixed-printing pin and the same-board duplicate test to the new rule; add the matrix rows (two boards, Commander+Deck, sum past cap, already-in-deck twice) and the unexpected-status test.
- [x] `src/mcp_server/server.py`, helper and model docstrings, `magic-deckbuilding/SKILL.md` -- wording; `uv run python -m scripts.build_plugin`.

**Acceptance Criteria:**
- Given the summing function, the cap check and the unexpected-status handling each removed in turn, when the probe harness runs the full suite, then the named test goes red.
- Given the fix, when `grep` runs over `src/` and `.claude/skills/` for the import's status mapping (`_line_result`, `"exists"`, `ImportLineStatus`, `partial`), then every hit is the new builder, the summing function, or updated wording.

## Design Notes

```python
def _sum_printings(found, occupied) -> tuple[dict[int, DeckImportLineResult], list[DeckCardEntry]]:
    """Lines of one export naming the same (card_id, sideboard) are one row: sum, cap, write."""
```

Over-cap is refused whole (every line of that card), not trimmed: adding part of the copies would leave the deck short silently, the bug this story fixes. Commander+Deck lines of one card share the mainboard row's primary key, so they sum and the flag is kept.

## Verification

**Commands:**
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, `uv run pytest` -- all green
- `uv run python -m scripts.probe_harness --expect-red '<node id>'` per planted removal -- proof lines in Implementation Notes
- `uv run python -m scripts.build_plugin` then `git status --short plugin/` -- committed, no drift

## Implementation Notes

Commits on `fix/quality-5-9-arena-mixed-printings`: `b9b48c2` (commit 1, pins green on the old code: mixed-printing Island export at `ok`/`exists`/`partial`/2 copies, per-line `0` and `251` parametrised), `c74ee76` (the fix, flipped pins, matrix rows, wording, `plugin/` rebuilt).

- `deck_import.py`: `_line_result` and the `DeckCardResult` projection are gone; `_resolved_line` builds every resolved line's result directly (`_error_line` now wraps it). Pass 1 resolves every line with a `match` on `NameResolution.status` (`found` / `ambiguous` / `not_found`, `case _` → `_unhandled_status(status: Never) -> NoReturn`, which raises `AssertionError` naming the status before any write; mypy rejects the call if a status is left unhandled, checked by planting a renamed case). Pass 2 is `_sum_printings(found, occupied)`: groups by `(card_id, sideboard)` in first-seen order; `exists` only for rows the deck held at load; over-cap groups are refused whole (every line `invalid`, message names the total, the line numbers and the 250 cap); otherwise every line `ok` and one `DeckCardEntry` of the summed quantity, `commander` = any line's. A summed `ok` line's message is `card_added_message(...)` with a "(N copies in all from lines a, b)" suffix. Failure arms swap every `ok` line to `_error_line`; `imported_lines` / `imported_copies` come from `ok` lines.
- The unexpected-status test lives in `test_deck_import_tool.py` and drives the real MCP client (`build_server` + `create_connected_server_and_client_session`), patching `NameResolution.status` to answer `"retired"`: `isError` true, text names `'retired'`, deck empty.
- Skills: `magic-deckbuilding/SKILL.md:57` rewritten per decision (b); the line-52 "then one `add_card_to_deck` per line" also names `import_decklist` so the two bullets agree. `synergy-discovery/SKILL.md:263-270` still describes per-line `add_card_to_deck` persistence only; it is not false, so left alone.
- AC grep (`_line_result|"exists"|ImportLineStatus|partial` over `src/` and the five skills): `_line_result` has no hits; the import's hits are the `ImportLineStatus` alias and field, the `_resolved_line` parameter, the `exists` arm of `_sum_printings`, the unchanged `ok`/`partial` top-level computation, and the updated docstrings. Every other hit is unrelated (`add_card_to_deck`'s own `exists`, "partial name", partial imports/files).

Probe proofs (full suite, each plant reverted and checked with `git diff --exit-code`):

- Summing removed (group keeps only its last line): `full suite (-m 'not integration'): 3523 collected, 5 failed, 0 errored, exit 1` — RED `test_import_decklist_mixed_printings_of_one_card` (expected), plus `..._same_card_twice_in_one_board_sums_into_one_row`, `..._commander_and_deck_lines_sum_into_the_commander_row`, `..._lines_summing_past_the_cap_are_all_invalid`, `..._card_already_in_deck_named_twice_is_exists_on_both_lines`.
- Cap check removed (`if False:`): `full suite (-m 'not integration'): 3523 collected, 1 failed, 0 errored, exit 1` — RED `test_import_decklist_lines_summing_past_the_cap_are_all_invalid`.
- Unexpected-status handling removed (unknown status answered as a line `error`, the old behaviour): `full suite (-m 'not integration'): 3523 collected, 1 failed, 0 errored, exit 1` — RED `test_import_decklist_unexpected_resolver_status_is_an_mcp_error`.

Gate: `ruff check .`, `ruff format --check .`, `mypy src/`, `mypy src/ --platform win32` clean; `uv run pytest` 3548 passed, 2 skipped. `build_plugin` run and committed; pre-commit's plugin-drift hook passed.

## Plan Change Log

## Review Triage Log

Pass 1 (lens `quick`, 2026-11-11): 2 findings — high 0, medium 1, low 1, false 0, maybe-false 0.
Both routed **patch**; no loopback.

| # | Finding | Verdict | Route | Evidence / action |
|---|---------|---------|-------|-------------------|
| 1 | The skill's new import bullet says same-card lines "are summed into one row" without "for the same board", and its `invalid` gloss omits that an over-cap group is refused whole | medium | patch | Verified: `_sum_printings` groups by `(card_id, sideboard)` and `test_import_decklist_same_card_in_two_boards_is_two_rows` pins two rows; `server.py` and the helper docstring say "for the same board", the skill (LLM-facing, the agent's guide) does not. Action: add the board qualifier and the whole-group refusal; reflow the edited line-52 bullet. |
| 2 | `DeckImportResult`'s new docstring names only `ok` / `partial` | low | patch | Verified: the `status` Literal also carries `invalid`, `deck_not_found`, `error`, `database_not_initialized`, and a failed bulk write answers `error` with non-ok lines; the model docstring becomes the tool's output-schema description. Action: list all six and scope the `ok`/`partial` rule to a resolved-and-written import. |

Review patches (`dc29eb2`, docs only, no new guard): the skill bullet says "for the same board", that a Deck and a Sideboard copy stay two rows, and that an over-250 sum refuses all of that card's lines; `DeckImportResult`'s docstring lists all six statuses and scopes the `ok`/`partial` rule. After the patches: ruff, ruff format, mypy (both platforms) clean; `uv run pytest` 3548 passed, 2 skipped; plugin rebuild, no drift. Commit 1 (`b9b48c2`) re-checked in a detached worktree: `test_deck_import_tool.py` 24 passed on the old code.
