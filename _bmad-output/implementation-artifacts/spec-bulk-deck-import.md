---
title: 'Bulk Arena Deck Import MCP Tool'
type: 'feature'
created: '2026-07-10'
status: 'done'
review_loop_iteration: 0
baseline_commit: '552b863deb7787342b5677564d3055fde6ceddb2'
context:
  - '{project-root}/_bmad-output/project-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Populating a saved 60- or 100-card deck currently requires dozens of `add_card_to_deck` MCP calls. Arena already exports the whole list, but the server cannot parse it or expose partial resolution failures in one response.

**Approach:** Add an `import_decklist` MCP tool that accepts an existing `deck_id` and an Arena export blob, parses `Commander` / `Deck` / `Sideboard` sections, resolves and adds each card through existing deck-management behavior, and returns one ordered result per card line.

## Boundaries & Constraints

**Always:** Treat the operation as additive. Map `Commander` and `Deck` entries to the mainboard and `Sideboard` entries to the sideboard. Parse standard Arena lines shaped as `QUANTITY Card Name (SET) COLLECTOR`, preserve source line numbers and annotations in results, resolve exact name before partial name, continue after line-level failures, and summarize imported lines/copies. Successful lines remain persisted when another line is invalid, ambiguous, not found, already present, or encounters a database error. Return structured, bounded Pydantic results and gracefully guard an uninitialized database or missing deck.

**Ask First:** Any requirement to create a deck from the blob, clear/replace existing contents, merge or overwrite existing quantities, make the import atomic, support a non-Arena syntax, or change card/deck database schemas.

**Never:** Filter resolution by the export's set code or collector number because the database stores one aggregated representative printing per oracle identity. Never perform legality/copy-limit/deck-size validation, recompute color identity, reimplement SQL in the tool layer, expose raw exceptions, or alter existing `add_card_to_deck` semantics.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Full import | Existing deck; valid Commander, Deck, and Sideboard lines | Every line is `ok`; quantities persist in the mapped location; overall `ok` | N/A |
| Mixed resolution | Valid lines mixed with a partial ambiguous name, unknown name, or malformed card line | Valid lines persist; ordered results report `ok`, `ambiguous`, `not_found`, or `invalid`; overall `partial` | Ambiguous results include bounded `CardSummary` matches; failures name the source line |
| Existing card | Card already exists in the same deck location | Existing quantity is unchanged; line reports `exists`; overall `partial` | No silent merge or overwrite |
| Invalid request | Blank `deck_id`, blank blob, or no parseable card entry | No writes; overall `invalid` | Message identifies the bad request |
| Unavailable target/data | Missing deck or uninitialized card database | No card lines are processed | Overall `deck_not_found` or `database_not_initialized` |

</frozen-after-approval>

## Code Map

- `src/mcp_server/tools/deck_import.py` -- new parser, per-line/top-level result models, and async import orchestrator.
- `src/mcp_server/tools/deck_management.py` -- existing exact-to-partial resolution and additive write behavior reused via `add_card_to_deck`.
- `src/mcp_server/server.py` -- registers the new async MCP wrapper over the injected session factory.
- `tests/integration/mcp_server/test_deck_import_tool.py` -- helper-level parsing, persistence, mapping, and failure coverage against SQLite.
- `tests/integration/test_mcp_tools.py` -- in-process MCP client coverage proving registration and structured serialization.
- `tests/integration/test_build_plugin.py` -- exact server-tool catalog guard updated for the additive MCP surface.

## Tasks & Acceptance

**Execution:**
- [x] `src/mcp_server/tools/deck_import.py` -- implement section-aware parsing and structured per-line import orchestration while delegating resolution/persistence to existing deck management.
- [x] `src/mcp_server/server.py` -- expose `import_decklist(deck_id, arena_export)` with an LLM-facing docstring that explains additive and partial-success behavior.
- [x] `tests/integration/mcp_server/test_deck_import_tool.py` -- cover every I/O matrix row, section mapping, quantities, result ordering, and persistence after mixed failures.
- [x] `tests/integration/test_mcp_tools.py` -- call the tool through FastMCP and assert the serialized per-line report and resulting deck contents.
- [x] `tests/integration/test_build_plugin.py` -- update the exact tool-catalog contract to require the new importer.

**Acceptance Criteria:**
- Given an existing saved deck and a standard Arena export, when `import_decklist` is called once, then all resolvable entries are persisted with exported quantities and correct mainboard/sideboard mapping.
- Given multiple card lines, when resolution or persistence outcomes differ, then the response contains exactly one ordered result per nonblank, non-header source line with its line number, parsed metadata when available, status, and actionable message.
- Given any line-level failure, when other lines are valid, then valid lines remain persisted and the top-level result reports `partial` with accurate imported-line and imported-copy totals.
- Given a missing target deck or uninitialized database, when the tool is called, then it returns a graceful top-level status and performs no deck-card writes.

## Design Notes

The export's `(SET) COLLECTOR` suffix is parsed and echoed for traceability, but card identity is name-based. This deliberately survives the importer's oracle-level aggregation choosing a different representative printing. Calling the existing single-card helper per parsed entry preserves its exact/partial ambiguity buckets, duplicate behavior, database rollback discipline, and independently committed partial successes without adding SQL or a second resolver.

## Verification

**Commands:**
- `uv run pytest tests/integration/mcp_server/test_deck_import_tool.py tests/integration/test_mcp_tools.py` -- expected: new helper and MCP harness tests pass.
- `uv run pytest -m "not integration"` -- expected: existing non-integration suite remains green.
- `uv run ruff check src/mcp_server tests/integration/mcp_server/test_deck_import_tool.py tests/integration/test_mcp_tools.py` -- expected: no lint findings.
- `uv run ruff format --check src/mcp_server tests/integration/mcp_server/test_deck_import_tool.py tests/integration/test_mcp_tools.py` -- expected: formatting is clean.
- `uv run mypy src/` -- expected: strict type checking passes.

## Suggested Review Order

**MCP entry and contract**

- Start at the public tool signature, behavior promise, and session boundary.
  [`server.py:312`](../../src/mcp_server/server.py#L312)

- Follow the top-level guards, target lookup, partial-success loop, and summary totals.
  [`deck_import.py:285`](../../src/mcp_server/tools/deck_import.py#L285)

**Parsing and failure boundaries**

- Review section parsing, source-order retention, fail-closed routing, and quantity validation.
  [`deck_import.py:118`](../../src/mcp_server/tools/deck_import.py#L118)

- Confirm character, result-line, and quantity limits bound work and responses.
  [`deck_import.py:29`](../../src/mcp_server/tools/deck_import.py#L29)

- Check single-card outcomes map into stable import-line statuses without leaking internals.
  [`deck_import.py:252`](../../src/mcp_server/tools/deck_import.py#L252)

**Verification**

- Happy-path coverage proves all section mappings and quantities persist correctly.
  [`test_deck_import_tool.py:23`](../../tests/integration/mcp_server/test_deck_import_tool.py#L23)

- Mixed outcomes prove ordered reporting and independently committed successful lines.
  [`test_deck_import_tool.py:61`](../../tests/integration/mcp_server/test_deck_import_tool.py#L61)

- Review-found edge cases prove unknown headers fail closed and inputs remain bounded.
  [`test_deck_import_tool.py:99`](../../tests/integration/mcp_server/test_deck_import_tool.py#L99)

- In-process MCP coverage verifies registration, serialization, and persisted deck contents.
  [`test_mcp_tools.py:200`](../../tests/integration/test_mcp_tools.py#L200)

- Exact catalog equality prevents accidental tool removal or substitution.
  [`test_build_plugin.py:133`](../../tests/integration/test_build_plugin.py#L133)
