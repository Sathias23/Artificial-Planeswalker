---
title: 'Games union across printings + brawl singleton enforcement'
type: 'bugfix'
created: '2026-07-10'
status: 'done'
review_loop_iteration: 0
context: []
baseline_commit: '1c80ed8db9f53822f769cab2e2b661a3a4964990'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** (1) The DB stores one printing per card (`oracle_cards` bulk), so a paper-only representative printing masks Arena availability — `validate_deck` flags real Arena cards as "not available on arena" and `games: ["arena"]` filters silently drop Arena staples (Gonti, Fatal Push, Drown in the Loch…) from search/semantic tools. (2) `validate_deck` applies the 4-copy limit to singleton formats — a Brawl deck with 2 copies of a card validates as legal.

**Approach:** Import from `default_cards`, deduplicate to one row per oracle identity at import time, and store `games` as the **union across all printings**; reconcile pre-existing rows by oracle_id so stale printings also get union games. Make the copy-limit rule format-aware: singleton formats (brawl, standardbrawl, commander, duel, oathbreaker, paupercommander) get max 1 copy (basics exempt), everything else keeps 4; normalize the format key to lowercase at the tool layer.

## Boundaries & Constraints

**Always:** One card row per oracle identity (no per-printing DB). Union computed at import time — no query-layer games rewrites. Deterministic canonical-printing choice. Mirror `src/` changes into `plugin/server/src/` via `scripts/build_plugin.py`, commit rebuilt `plugin/`. Stateless tools (D5). `mypy --strict` + ruff clean.

**Ask First:** Any `cards` schema migration (none expected). Deleting rows from an existing DB.

**Never:** No brawl/commander deck-size rules (100-card minima = separate lead). No "any number of…" exemption cards (Seven Dwarves etc.) — documented limitation, parity with the 4-copy rule. Don't default `format` from `deck.format`. Don't touch the embedding pipeline / `card_vec`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior |
|----------|--------------|---------------------------|
| Union import | Paper-only + arena printings in `default_cards` | One row; `games` = sorted union `["arena","mtgo","paper"]` |
| Reconcile stale row | Pre-existing row, `id` not this run's canonical | Row kept; `games` updated to its `oracle_id`'s union |
| No top-level `oracle_id` | Reversible/odd layout | Group by `card_faces[0].oracle_id`, else own `id` (self-group); never drop the card |
| Brawl duplicate | `format="brawl"`, 2× non-basic (both boards combined) | `singleton` violation naming the card; `is_legal=False` |
| Brawl basics | 20× Island in brawl deck | No violation |
| Standard unchanged | `format="standard"`, 4 copies / 5 copies | Legal / `copy_limit` |
| Case-insensitive format | `format=" BRAWL "` | Treated as `brawl` (singleton + legality work) |
| Arena false positive gone | Temple of Malady (paper-set printing), `games=["arena"]`, post-refresh DB | No `game_availability` violation |

</frozen-after-approval>

## Code Map

- `src/data/importers/scryfall.py` -- orchestrator (download → `parser.stream_cards` → `transformers.transform_scryfall_card` → `importer.import_cards`); union work lands here. Upsert keys on printing `id`; `games` clobbered at `importer.py:166`
- `src/mcp_server/tools/initialize_database.py:39` (`_DEFAULT_BULK_TYPE`) + `setup.py:129` -- currently `oracle_cards`; `scripts/import_scryfall_data.py` already defaults `default_cards`
- `src/logic/deck_validator.py` -- `_MAX_COPIES` (~161), copy tally (263-283), `DeckViolation.rule` Literal (177-183), `is_basic_land`
- `src/mcp_server/tools/deck_analysis.py:302` (`format.strip()`) + `src/mcp_server/server.py:406-429` -- tool wrapper + registration docstrings
- `tests/fixtures/card_data.py:627` `create_om1_spm_cards()` -- exact masking scenario (same oracle_id, paper vs arena printings); `tests/unit/logic/test_deck_validator.py:559-733` -- `_vd_*` builders to mirror
- `.claude/skills/format-legality/SKILL.md` (+ `plugin/skills/` copy) -- documents both limitations being fixed (lines 91-147, 119-128, 393-395); `magic-deckbuilding/SKILL.md:277` constructed-60 framing

## Tasks & Acceptance

**Execution:**
- [x] `src/data/importers/aggregate.py` (new) -- streaming pass building `group_key → (games_union, canonical_id)`; group key = top-level `oracle_id` → `card_faces[0].oracle_id` → own `id`; canonical = max `released_at`, tiebreak min `id`
- [x] `src/data/importers/scryfall.py` -- pass 1 = aggregate; pass 2 = re-stream, skip non-canonical printings, override `games` with sorted union; then reconcile pre-existing rows: batch-`UPDATE cards SET games=<union> WHERE oracle_id=<oid>` where games differ. Uniform for any bulk_type (no-op union for oracle_cards)
- [x] `initialize_database.py` + `setup.py` -- default to `default_cards`; docstrings note dedup+union semantics and ~450 MB download
- [x] `src/logic/deck_validator.py` -- `_SINGLETON_FORMATS = frozenset({brawl, standardbrawl, commander, duel, oathbreaker, paupercommander})`; copy limit 1 for those; new `rule="singleton"` Literal + message; basics exempt via `is_basic_land`
- [x] `deck_analysis.py` + `server.py` -- `format.strip().lower() or "standard"`; docstrings gain singleton + case notes
- [x] Tests: unit `aggregate` (matrix rows 1-3, small JSON fixtures); unit validator singleton (rows 4-7, mirror `test_five_copies_non_basic_flags_copy_limit`); integration `test_deck_analysis_tool.py` brawl singleton + case-insensitive format; arena-availability test stays green
- [x] `.claude/skills/format-legality/SKILL.md` -- rewrite "tool can't see singleton" + arena false-positive workaround (fixed post-refresh; stale-DB caveat stays); touch `magic-deckbuilding` framing
- [x] Run `scripts/build_plugin.py` -- rebuild `plugin/` (server mirror + skills), include in commit

**Acceptance Criteria:**
- Given a fresh import from `default_cards`, when any printing of a card is on Arena, then its single DB row has `"arena"` in `games` and card-count ≈ oracle-distinct count (not per-printing count).
- Given an existing DB re-imported with the new code, when a deck references a stale printing row, then `validate_deck(games=["arena"])` uses union games (no false positive).
- Given `format="brawl"` (any case), when a non-basic appears twice across boards, then report contains a `singleton` violation and `is_legal` is false; the same deck under `format="standard"` stays legal.
- Given the full suite, when `uv run pytest -m "not integration"` and pre-commit run, then all pass.

## Design Notes

- **Two-pass over one downloaded file:** printings are scattered through `default_cards`; pass 1 needs only a ~35k-entry map, pass 2 reuses the existing transform→batch-upsert path unchanged. Holding all transformed rows in memory would cost hundreds of MB.
- **Reconcile UPDATE is required:** upsert keys on printing `id` and never deletes; an older DB's canonical rows (Scryfall's `oracle_cards` picks) may differ from our picks, and decks reference those old ids. Updating `games` by `oracle_id` gives every surviving row the union — no re-pointing of decks.
- **`rarity`/`set_code` drift accepted:** our canonical heuristic may pick a different printing than Scryfall's — same oracle text, possibly different set/rarity. Pre-existing arbitrariness, not a regression.

## Verification

**Commands:**
- `uv run pytest -m "not integration"` -- expected: all pass
- `uv run pytest tests/integration/mcp_server/test_deck_analysis_tool.py` -- expected: all pass
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` -- expected: clean
- `uv run python scripts/build_plugin.py` -- expected: plugin/ rebuilt, drift check green

**Manual checks (if no CLI):**
- After Brad refreshes his live DB: `lookup_card_by_name("Temple of Malady")` shows arena in games; `validate_deck` on the Kotis deck (`a839fc0b…`, `games=["arena"]`) reports no arena false positives; `format="brawl"` on a deck with a doubled non-basic flags `singleton`.

## Suggested Review Order

**Games union — import pipeline (goal 1)**

- Entry point: the 6-stage orchestration docstring shows the whole two-pass + reconcile design.
  [`scryfall.py:135`](../../src/data/importers/scryfall.py#L135)

- Pass-1 streaming aggregation: games union + deterministic canonical pick per oracle identity.
  [`aggregate.py:67`](../../src/data/importers/aggregate.py#L67)

- Group-key precedence (oracle_id → first-face oracle_id → own id) — the dedup identity rule.
  [`aggregate.py:39`](../../src/data/importers/aggregate.py#L39)

- Pass 2: skips non-canonical printings, overrides `games` with the sorted union.
  [`scryfall.py:58`](../../src/data/importers/scryfall.py#L58)

- Reconcile: stale rows from older imports get union games — decks keep their card ids.
  [`scryfall.py:90`](../../src/data/importers/scryfall.py#L90)

- Default bulk set flipped to `default_cards`; `update=true` is the stale-DB remediation path.
  [`initialize_database.py:42`](../../src/mcp_server/tools/initialize_database.py#L42)

- New MCP-facing `update` parameter (beyond spec letter — enables in-client refresh).
  [`server.py:560`](../../src/mcp_server/server.py#L560)

**Brawl singleton — validator (goal 2)**

- The singleton-format set (review-extended with gladiator/competitivebrawl/predh).
  [`deck_validator.py:169`](../../src/logic/deck_validator.py#L169)

- Format-aware copy limit: 1 vs 4, `singleton` vs `copy_limit` rule.
  [`deck_validator.py:304`](../../src/logic/deck_validator.py#L304)

- Defensive lowercase in the pure function (review finding — direct callers bypass the tool).
  [`deck_validator.py:268`](../../src/logic/deck_validator.py#L268)

- Tool-layer normalization, per the frozen intent.
  [`deck_analysis.py:308`](../../src/mcp_server/tools/deck_analysis.py#L308)

**Skill & docs truth-sync**

- Rewritten limitations narrative: singleton enforced, case-insensitivity scoped, stale-DB caveat.
  [`format-legality/SKILL.md:20`](../../.claude/skills/format-legality/SKILL.md#L20)

- Golden rule now warns other tools' `format` filter is still exact-match lowercase.
  [`format-legality/SKILL.md:28`](../../.claude/skills/format-legality/SKILL.md#L28)

- README first-run numbers updated for the ~500 MB `default_cards` download.
  [`README.md:36`](../../README.md#L36)

**Tests**

- Aggregation unit tests: union, canonical selection, group-key fallbacks, null games.
  [`test_aggregate.py:1`](../../tests/unit/data/importers/test_aggregate.py#L1)

- Import e2e: dedup+union, stale-row reconcile, oracle_cards no-op.
  [`test_scryfall_import_e2e.py:224`](../../tests/integration/data/test_scryfall_import_e2e.py#L224)

- Singleton suite incl. review additions (gladiator, quantity=2 mainboard, logic-layer case).
  [`test_deck_validator.py:736`](../../tests/unit/logic/test_deck_validator.py#L736)

- Tool-level brawl singleton + case-insensitive format.
  [`test_deck_analysis_tool.py:381`](../../tests/integration/mcp_server/test_deck_analysis_tool.py#L381)

**Peripherals**

- setup.py: default_cards import + stale-DB hint on the skip path.
  [`setup.py:124`](../../setup.py#L124)

- CLI help text describes the new dedup+union semantics.
  [`import_scryfall_data.py:29`](../../scripts/import_scryfall_data.py#L29)

- `plugin/` is a `scripts/build_plugin.py` rebuild — mirrors `src/` + skills, no hand edits.
