---
title: 'One indexed, bounded card-name resolver'
type: 'bugfix'
ticket: '6'
created: '2026-11-11'
status: done
baseline_revision: 'e1dbe89453bed88243675d816d5115addde5d74e'
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

**Problem:** Three card-name resolvers (`lookup_card`, `deck_management.resolve_card`, `find_similar._resolve_seed`) order candidates differently; `find_similar`'s exact seed match is `lower(name) = lower(?)`, a full scan (#108: 58 ms vs 0.5 ms indexed); the partial read has no `LIMIT`, so a two-letter query materialises thousands of rows and every caller reports the capped list's length as the match count; `%` and `_` in user text act as LIKE wildcards; `remove_card_from_deck` copies the shared wording inline; and printed-name matching, `lookup_card`'s cap, blank guard and `games` pass-through, and `find_similar`'s seed branches are untested.

**Approach:** Pin today's behaviour first (commit 1, green on the old code), then route lookup, the three deck card tools, import and `find_similar` through one resolver in `src/data/repositories/card.py`: NOCASE-equality exact match, an escaped, one-per-oracle, name-ordered partial read capped at `MAX_NAME_MATCHES + 1`, and a result that says whether more matched (review option b: "more than N").

## Boundaries & Constraints

**Always:** One statement builder serves both seams (async session and the sync sqlite-vec connection); the resolver strips and blank-guards the name and never queries for a blank one. Status tokens stay as they are per tool. LLM-facing wording changes move the `server.py` docstrings, the four skills that list `ambiguous`, and `plugin/` in the same PR. Tests run on `tmp_path` databases built through `create_engine` + `init_database` (real schema, connect hooks); the only real-database read is an optional `mode=ro` timing, reported as such.

**Never:** No change to status tokens (5.7), `games`/`format` validation (5.4), the script-only search methods' existence (5.1 deletes them), `src/viewer/`, or the companion. No new index or migration.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Printed name | card `name` X, `printed_name` Y; query Y (exact, any case) or a substring of Y | every tool resolves the card | none |
| Two-letter query | 30 distinct cards contain "zq" | `ambiguous`, 10 `matches` in name order, message says "more than 10"; at most 11 rows read | none |
| 6–10 matches | exactly 7 or 10 cards match | count reported exactly, refine prompt | none |
| Literal wildcard | cards "Fifty 50% Off" and "Lot 50 Gold"; query `50%` | resolves the first card only | none |
| Blank name | `"   "` | lookup `not_found` "must not be empty"; deck tools `invalid`; find_similar `invalid`; no LIKE query | none |
| Games pass-through | paper-only card, lookup with `games=["arena"]` | `not_found` | none |
| Seed exact match | `find_similar_cards(card_name=...)` | plan uses `ix_cards_name_nocase` and `ix_cards_printed_name_nocase`, no `SCAN cards` | none |

</frozen-after-approval>

## Code Map

- `src/data/repositories/base.py` -- add `LIKE_ESCAPE` and `contains_pattern(text)` (`%…%` with `\`, `%`, `_` escaped); every user-text LIKE pairs it with `escape=LIKE_ESCAPE`.
- `src/data/repositories/card.py` -- `MAX_NAME_MATCHES = 10`; generic frozen `NameResolution[T]` (`card`, `matches`, `more`, `status` property); module builders `_exact_name_statement` / `_partial_name_statement` over any column set (exact: NOCASE `==` on name OR printed_name, `ORDER BY id LIMIT 1`; partial: escaped `ilike`, filters, `_apply_unique_oracle_filter`, `ORDER BY name COLLATE NOCASE, id`, `LIMIT cap+1`); `CardRepository.resolve_name(name, *, format_filter, games)`; `resolve_name_on_connection(conn, name, columns)` for the sync seam (compiles the same statements with the named-paramstyle SQLite dialect). `find_by_name_exact` keeps its SQL via the builder; `find_by_name_partial` becomes bounded. Make the three `_apply_*` helpers static. Escape LIKE in `_apply_games_filter`, `find_by_type`, `search_by_keywords`, `search_advanced` (types, keywords, phrases).
- `src/data/repositories/deck.py:451` -- `find_deck_by_name` escapes (no caller; 5.1 deletes it).
- `src/mcp_server/tools/messages.py` -- `REFINE_THRESHOLD = 5` and `ambiguous_lookup_message(name, resolution, *, card_id_hint)`, the three-bucket wording `lookup_card` and `find_similar` share.
- `src/mcp_server/tools/card_lookup.py` -- call `resolve_name`; drop local constants.
- `src/mcp_server/tools/deck_management.py:211-270, 657, 791, 915` -- `resolve_card` returns a `NameResolution[Card]`; `ambiguous_message(name, resolution)`; `remove_card_from_deck` uses `ambiguous_message`, `card_not_found_message`, `_location` (M51).
- `src/mcp_server/tools/deck_import.py:454-478` -- same `resolve_card` shape.
- `src/mcp_server/tools/find_similar.py:206-301` -- name path through `resolve_name_on_connection` with `CardModel` columns; id path stays a raw point lookup; drop local constants.
- `src/mcp_server/server.py` -- docstrings of lookup, add/set/remove, import, find_similar.
- `.claude/skills/{magic-deckbuilding,synergy-discovery,format-legality,mana-curve-analysis}/SKILL.md` -- the `ambiguous` bullets.
- Tests to reuse: `tests/integration/conftest.py` (`create_engine`/`init_database`/`build_card_embeddings` pattern), `test_infrastructure_failures.py` (`create_connected_server_and_client_session`, structured result), `tests/unit/data/test_card_repository.py:118` (existing EXPLAIN pattern).

## Tasks & Acceptance

**Execution:**
- [x] `tests/integration/mcp_server/test_card_name_resolution.py` (new, commit 1) -- B2-P5 printed name on all six name tools; B9-P14 11-match cap, whitespace name, Arena-only lookup; B9-P16 printed-name seed, 11-oracle partial, blank-format port. Green on the old code.
- [x] `base.py`, `card.py`, `deck.py` -- resolver, builders, escaping.
- [x] `messages.py`, `card_lookup.py`, `deck_management.py`, `deck_import.py`, `find_similar.py` -- route through the resolver; shared wording.
- [x] same test file -- bug tests: "more than 10" + rows read ≤ 11 (async: ORM load count; sync: per-statement row count), `50%` literal on lookup, deck add, search_cards and find_similar, EXPLAIN on find_similar's traced seed SQL; update the pins' message assertions.
- [x] `server.py`, four skills -- wording; `uv run python -m scripts.build_plugin`.

**Acceptance Criteria:**
- Given the resolver routed, when `grep` runs over `src/` for `find_by_name_partial`, `lower(name)`, `_MAX_MATCHES`, `_REFINE_THRESHOLD` and `ilike(`/`.like(` on user text, then each hit is the resolver or an escaped/validated site listed in Implementation Notes.
- Given each new guard removed in turn (the cap, the escape, the NOCASE seed match, the `more` wording), when the probe harness runs the full suite, then the named test goes red.

## Design Notes

```python
@dataclass(frozen=True)
class NameResolution[T]:
    card: T | None = None          # the one card the name names
    matches: list[T] = field(default_factory=list)  # >1 candidates, ≤ MAX_NAME_MATCHES
    more: bool = False             # more than MAX_NAME_MATCHES matched
```

Handoff for 2.1: `await CardRepository(session).resolve_name(name, format_filter=..., games=...)` is the whole interface. The sync seam compiles the same `Select` objects (`sqlite.dialect(paramstyle="named")`), so there is one SQL source, not two. Ordering is name then id for every tool (previously unordered / by id).

## Verification

**Commands:**
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, `uv run mypy src/ --platform win32`, `uv run pytest` -- all green
- `uv run python -m scripts.probe_harness --expect-red …` per planted removal -- proof lines in Implementation Notes
- `uv run python -m scripts.build_plugin` then `git status --short plugin/` -- committed, no drift

## Implementation Notes

Commits on `fix/quality-5-6-card-name-resolver`: `a4abeae` (commit 1, the pins, green on the old
code: B2-P5 printed name on all six name tools, B9-P14 11-match cap / whitespace name / Arena-only
lookup, B9-P16 printed-name seed / 11-oracle partial / per-oracle collapse / blank-format port) and
`df47b6b` (the resolver, the escaping, the shared wording, the bug tests, docstrings, skills,
`plugin/` rebuilt).

Choices the plan left open:

- `resolve_name` runs its exact step through `find_by_name_exact` (which builds its SQL with
  `_exact_name_statement`), so the existing per-line `DatabaseError` test in
  `test_deck_import_tool.py`, which patches `find_by_name_exact`, still drives the import's error arm.
- `find_by_name_partial` keeps its positional signature and gains a keyword `limit`
  (default `MAX_NAME_MATCHES`); no tool calls it any more, only `scripts/validate_data_layer.py`.
- `lookup_card` now strips `card_name` before resolving and echoing it (the resolver strips anyway;
  stripping first keeps the echoed name and the resolved name the same). This lands the name half of
  M5 incidentally; `games`/`format` validation (5.4) is untouched.
- `NameResolution.status` is used by the deck tools; lookup and find_similar branch on `card` /
  `matches` directly (same thing, reads clearer next to the field use).
- `test_import_boundary.py`'s pinned read-method set gains `resolve_name` (the guard requires every
  public repository method to be classified).
- Wording: lookup / find_similar share `ambiguous_lookup_message` (2-5 "Which one did you mean?",
  6-10 "Please refine your search.", cut list "Found more than 10 cards matching 'x'. Please refine
  your search; showing the first 10.", with ", or re-call with a specific card_id" for find_similar).
  The deck tools keep their own shape: "'x' matches more than 10 cards. Re-call with a specific
  card_id, or refine the name."
- Rows-read guard, async seam: a `CardModel` mapper `load` listener counts ORM instances built
  (≤ 11 for a 30-match query). Sync seam: the server is built over a tracing connection factory whose
  connections record each statement and the rows its cursor handed back; the same trace feeds the
  EXPLAIN test (the exact-seed statement, re-planned with its own params on the real schema).

AC 1 grep (`find_by_name_partial`, `lower(name)`, `_MAX_MATCHES`, `_REFINE_THRESHOLD`, `ilike(`,
`.like(` over `src/`), every hit classified:

- resolver: `card.py` `_partial_name_statement` (name / printed_name `ilike`, escaped),
  `find_by_name_partial` (definition + docstring examples).
- escaped user text: `_apply_games_filter`, `find_by_type`, `search_by_keywords` (oracle text +
  keywords array), `search_advanced` types / keywords / oracle phrases, `deck.py`
  `find_deck_by_name`; `base.py` line 5 is the `LIKE_ESCAPE` comment.
- validated, not user text: `search_advanced` colour `like`s (four, colour codes checked against
  WUBRG by `card_search._validation_error`) and rarity `ilike`s (checked against the rarity
  vocabulary there); `find_by_colors`' colour `like` (script-only method, 5.1 deletes it, no tool
  reaches it).
- `lower(name)`, `_MAX_MATCHES`, `_REFINE_THRESHOLD`: no hits.

Verification:

- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`,
  `uv run mypy src/ --platform win32`: clean. `uv run pytest`: 3538 passed, 2 skipped.
- `uv run python -m scripts.build_plugin` then `git status --short plugin/`: committed in `df47b6b`,
  no drift (the pre-commit rebuild hook passed on the commit).

Probe-harness proofs (each plant applied to the committed, clean tree by a script, reverted with
`git checkout -- <file>`, revert checked with `git diff --exit-code`; harness exit 0 = every
`--expect-red` met):

cap removed (`_partial_name_statement` without `.limit(limit)`):
```
full suite (-m 'not integration'): 3513 collected, 2 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_card_name_resolution.py::test_a_two_letter_lookup_says_more_than_ten_and_reads_at_most_eleven_rows
  RED    tests/integration/mcp_server/test_card_name_resolution.py::test_a_two_letter_seed_says_more_than_ten_and_reads_at_most_eleven_rows
```
escape removed (`contains_pattern` returns `f"%{text}%"`):
```
full suite (-m 'not integration'): 3513 collected, 2 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_card_name_resolution.py::test_a_percent_sign_in_a_name_or_phrase_is_literal
  RED    tests/integration/mcp_server/test_card_name_resolution.py::test_an_underscore_in_a_name_is_literal
```
NOCASE seed match removed (`_exact_name_statement` back to `lower(name) = lower(?)` on both terms;
one builder now, so the async exact path's existing EXPLAIN test goes red with it):
```
full suite (-m 'not integration'): 3513 collected, 2 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_card_name_resolution.py::test_find_similar_seed_exact_match_is_an_index_search
  RED    tests/unit/data/test_card_repository.py::TestFindByNameExact::test_mixed_case_lookup_is_an_index_search
```
`more` wording removed (`count = str(shown)` in `ambiguous_lookup_message` and `ambiguous_message`):
```
full suite (-m 'not integration'): 3513 collected, 5 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_card_name_resolution.py::test_lookup_caps_an_eleven_match_query_at_ten
  RED    tests/integration/mcp_server/test_card_name_resolution.py::test_find_similar_caps_an_eleven_oracle_partial_at_ten
  RED    tests/integration/mcp_server/test_card_name_resolution.py::test_a_two_letter_lookup_says_more_than_ten_and_reads_at_most_eleven_rows
  RED    tests/integration/mcp_server/test_card_name_resolution.py::test_a_deck_tool_says_more_than_ten_for_a_cut_candidate_list
  RED    tests/integration/mcp_server/test_card_name_resolution.py::test_a_two_letter_seed_says_more_than_ten_and_reads_at_most_eleven_rows
```

Optional real-database timing (the developer's `cards.db`, 39,503 cards, opened `mode=ro`, both
NOCASE indexes present; the seed resolver's old SQL against the shared statements compiled for the
sync seam; median ms, rows returned):

- exact seed "lightning bolt": old 182.8 ms → new 0.02 ms (1 row each).
- partial "el": old 275.9 ms, 3,676 rows → new 252.6 ms, 11 rows. A leading-`%` LIKE still scans;
  the gain is the rows read and validated, not the scan.
- partial "zq": old 227.3 ms → new 179.4 ms (1 row each).

Review patches (`e56106e`): `test_wildcards_in_types_keywords_and_games_are_literal` sends `%`/`_`
through `search_cards` `types` and `keywords` and lookup `games=["%"]`; the `find_deck_by_name`
docstring now says it raises `MultipleResultsFound` on more than one match. After the patches:
ruff, ruff format, mypy (both platforms) clean; `uv run pytest` 3539 passed, 2 skipped; plugin
rebuild, no drift.

`search_advanced` types escape removed (back to `ilike(f"%{type_str}%")`, tree staged first,
reverted with `git checkout`, `git diff --exit-code` clean):
```
full suite (-m 'not integration'): 3514 collected, 1 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_card_name_resolution.py::test_wildcards_in_types_keywords_and_games_are_literal
```

## Plan Change Log

## Review Triage Log

Pass 1 (lens `quick`, 2026-11-11): 2 findings — high 0, medium 1, low 1, false 0, maybe-false 0.
Both routed **patch**; no loopback.

| # | Finding | Verdict | Route | Evidence / action |
|---|---------|---------|-------|-------------------|
| 1 | Escape proven only at `contains_pattern`; a call site that drops `escape=LIKE_ESCAPE` or reverts to `f"%{x}%"` passes the suite | medium | patch | Verified: `search_cards` passes `types` and `keywords` unvalidated (`card_search._validation_error` checks colours, rarity, games, mana, paging only), and `lookup_card` passes `games` unvalidated; no test sends `%`/`_` through those sites. Action: one entry-point test over `search_cards` types/keywords and lookup `games=["%"]`. |
| 2 | `find_deck_by_name`'s rewritten docstring still says "Returns the first match if multiple decks match" | low | patch | Verified: body calls `scalar_one_or_none()` over an unordered `ILIKE`, which raises `MultipleResultsFound` on two matches (`scripts/view_deck.py:46` avoids it for that reason). Direct docstring correction; no behaviour change (5.1 deletes the method). |

Pass 2 (Greptile, PR #129, 4/5): 1 finding, P2, routed **patch**.

| # | Finding | Verdict | Route | Evidence / action |
|---|---------|---------|-------|-------------------|
| 1 | The backslash escape in `contains_pattern` has no test; only `%` and `_` alone are covered | low | patch | Verified: no test sends a `\` through a resolver. Action: `test_a_backslash_before_a_wildcard_is_literal_on_both_resolver_paths` sends `a\_z` through `lookup_card_by_name` (async) and `find_similar_cards` (sync) against `A\_Z`, `A\QZ` and `A_Z` near misses. |

Backslash doubling removed from `contains_pattern` (tree staged first, reverted with
`git checkout`, `git diff --exit-code` clean):
```
full suite (-m 'not integration'): 3515 collected, 1 failed, 0 errored, exit 1
  RED    tests/integration/mcp_server/test_card_name_resolution.py::test_a_backslash_before_a_wildcard_is_literal_on_both_resolver_paths
```
