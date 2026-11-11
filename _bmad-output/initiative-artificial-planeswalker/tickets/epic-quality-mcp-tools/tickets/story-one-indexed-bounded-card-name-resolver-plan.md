---
title: 'One indexed, bounded card-name resolver'
type: 'bugfix'
ticket: '6'
created: '2026-11-11'
status: 'in-progress'
baseline_revision: 'e1dbe89453bed88243675d816d5115addde5d74e'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: ''
review_source: ''
lenses_ran: []
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
- [ ] `tests/integration/mcp_server/test_card_name_resolution.py` (new, commit 1) -- B2-P5 printed name on all six name tools; B9-P14 11-match cap, whitespace name, Arena-only lookup; B9-P16 printed-name seed, 11-oracle partial, blank-format port. Green on the old code.
- [ ] `base.py`, `card.py`, `deck.py` -- resolver, builders, escaping.
- [ ] `messages.py`, `card_lookup.py`, `deck_management.py`, `deck_import.py`, `find_similar.py` -- route through the resolver; shared wording.
- [ ] same test file -- bug tests: "more than 10" + rows read ≤ 11 (async: ORM load count; sync: per-statement row count), `50%` literal on lookup, deck add, search_cards and find_similar, EXPLAIN on find_similar's traced seed SQL; update the pins' message assertions.
- [ ] `server.py`, four skills -- wording; `uv run python -m scripts.build_plugin`.

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

## Plan Change Log

## Review Triage Log
