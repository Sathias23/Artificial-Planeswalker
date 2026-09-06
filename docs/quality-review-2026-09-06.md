# Repository quality review

Date: 2026-09-06  
Reviewed commit: `5f302f4`  
Scope: Repository-wide review of backend correctness, companion state handling, testing, packaging, and documentation.

## Assessment

The repository has strong automated checks, but several correctness gaps survive them. The highest-priority recommendation is to enforce database referential integrity, followed by improving companion synchronization and recovery.

The review did not modify source files. Backend findings below were reproduced using isolated temporary or in-memory databases; companion timing findings are based on source and test inspection.

## Prioritized findings

### 1. P1 — Enforce database referential integrity

**Location:** [src/data/repositories/deck.py](../src/data/repositories/deck.py), line 225; [src/data/database.py](../src/data/database.py), lines 106–119.

Deck deletion uses a bulk SQL DELETE and relies on cascading foreign keys. The engine never enables SQLite foreign-key enforcement, and bulk deletion bypasses ORM cascades. Deleting a populated deck therefore leaves orphaned card associations.

**Evidence:** An isolated reproduction reported `PRAGMA foreign_keys = 0` and one remaining association row after deleting its deck. The existing cascade test checks that the deck disappeared, rather than checking the association rows.

**Recommendation:** Enable foreign-key enforcement on every SQLite connection, clean existing orphan rows, and add a regression test that verifies deletion removes associations and invalid references are rejected. Verify import and migration paths against the enforced constraints.

### 2. P2 — Close the companion's initial subscription gap

**Location:** [ui/src/state/socket.ts](../ui/src/state/socket.ts), lines 440–445.

Socket initialization refreshes snapshots after reconnection only. If the active deck changes after the initial HTTP snapshot but before the first WebSocket connection is registered, the notification can be lost. The UI can then display the previous deck indefinitely while reporting a live connection.

**Evidence:** Source inspection shows the refresh callback is conditional on a previous connection failure. Existing tests expect no refresh on first connection, but do not interleave a deck mutation between the snapshot and subscription.

**Recommendation:** Establish the subscription before reading the snapshot, or reconcile the snapshot on every socket connection. Add a regression test that changes the active deck between initial snapshot completion and first subscription.

### 3. P2 — Make transient deck failures recover independently

**Location:** [ui/src/state/deck.ts](../ui/src/state/deck.ts), lines 519–521.

Recovery from a refused deck request depends on a later health-state transition. If the deck-list poll succeeds or recovers before the pending deck request returns a transient `database_unavailable` response, no retry is scheduled. The companion can remain on its updating panel despite database recovery.

**Evidence:** The recovery listener reacts only to a transition into `no-active-deck` and skips a deck that is still booting. Existing recovery tests cover the poll recovering after refusal, but not the reverse response ordering.

**Recommendation:** Add bounded-backoff retries for transient deck failures independently of future health-state transitions. Test both response orderings and ensure cancellation prevents obsolete requests from overwriting newer state.

### 4. P2 — Update deck metadata with every card mutation

**Location:** [src/data/repositories/deck.py](../src/data/repositories/deck.py), lines 399–409, 475–487, 553–560, and 623–624; identity calculation at line 673.

Normal card additions, removals, quantity updates, and imports modify association rows without refreshing the deck's stored color identity or modification time. The identity helper also reads `card.colors` instead of `card.color_identity`, so explicitly invoking it can still produce an incorrect identity.

**Evidence:** An isolated reproduction added a colored card and observed `color_identity=[]` with an unchanged timestamp. A separate reproduction gave a card empty colors and a blue color identity; the refresh helper still returned an empty deck identity.

**Recommendation:** Update derived identity and modification time within the same transaction as each card mutation. Calculate identity from `card.color_identity`. Add behavior tests covering additions, removals, imports, quantity changes, and identity-only colors.

### 5. P2 — Refresh search-filter metadata during incremental indexing

**Location:** [src/search/index_builder.py](../src/search/index_builder.py), line 392.

Incremental change detection hashes embedding text and skips a card when that hash is unchanged. Colors and mana value are stored separately as search-filter metadata, but changes confined to those fields do not invalidate the hash. Rebuilding can therefore retain obsolete filter values.

**Evidence:** An isolated reproduction changed a card from red with mana value 1 to green with mana value 3. The incremental build reported the card as skipped, and its index metadata remained red with mana value 1.

**Recommendation:** Track metadata changes separately or include them in invalidation. Prefer refreshing metadata without recomputing embeddings when the embedding text is unchanged. Add regression coverage that changes only colors or mana value and checks filtered search behavior.

### 6. P3 — Refresh the agent-facing project context

**Location:** the agent-facing context block, now [AGENTS.md](../AGENTS.md) (at review time it was the since-deleted `_bmad-output` context file, line 20 onward).

The project context still describes the codebase as a legacy Chainlit/PydanticAI monolith awaiting migration. It includes obsolete architecture, dependency, and launch instructions despite the implemented MCP server and companion application.

**Impact:** Future agents can choose obsolete implementation paths or commands based on instructions presented as foundational project context.

**Recommendation:** Replace obsolete guidance with the current architecture, runtime dependencies, entry points, and development commands. Clearly distinguish retained historical context from active instructions.

## Validation performed

| Check | Result |
| --- | --- |
| Python tests: `uv run --offline pytest -m 'not integration' -q` | 3,175 passed; 1 skipped; 27 deselected |
| Python lint: `ruff check .` | Passed |
| Python formatting: `ruff format --check .` | Passed; 334 files already formatted |
| Python strict typing: `mypy src/` | Passed; 94 source files |
| Frontend ordinary tests | 1,764 passed across 58 files |
| Frontend gate tests | 39 passed across 2 files |
| Frontend lint | Passed |
| TypeScript checks | Passed |
| Isolated backend reproductions | Confirmed orphaned associations, stale deck metadata, incorrect identity calculation, and stale index metadata |

The 27 integration-marked Python tests were excluded from this run. Passing checks do not establish that the timing and data-integrity scenarios above are covered. The companion timing findings were not reproduced in a live browser during this review.

## Recommended implementation order

1. Enforce database integrity and remediate existing orphan rows.
2. Fix companion initial synchronization and transient-failure recovery.
3. Correct deck metadata maintenance and search-index invalidation.
4. Refresh project context.

Add behavioral regression tests alongside the fixes, targeting the demonstrated failures and missing event orderings.
