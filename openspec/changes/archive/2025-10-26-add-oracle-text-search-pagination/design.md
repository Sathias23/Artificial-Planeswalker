# Design Document: Oracle Text Search and Pagination

## Context

Bug report 77c559f3 revealed that users cannot search for specific card effects in oracle text, only keywords. This is a fundamental limitation for deck building, as users need to find cards with precise mechanics (e.g., "target creature you control gains flying" for tempo strategies).

Additionally, the current 20-card result limit prevents users from exploring large result sets, forcing them to narrow filters prematurely or miss relevant cards.

### Background
- Oracle text is already stored in database (`CardModel.oracle_text: str | None`)
- Current `keywords` parameter only searches extracted keywords, not full text
- Current `max_results` parameter limits results but doesn't allow navigation
- User complaint: "show me cards with 'target creature you control gains flying'" returned 31 flying creatures instead of 3 relevant cards

### Constraints
- Maintain <500ms query performance target (NFR7)
- Preserve backward compatibility with existing searches
- Keep offline-first architecture (no external API calls)
- SQLite database with limited full-text search capabilities (no FTS5 configured)

### Stakeholders
- Users: Need precise effect searches and result navigation
- Agent: Needs clear pagination semantics for multi-turn conversations

---

## Goals / Non-Goals

### Goals
1. Enable precise oracle text searches with phrase matching
2. Provide pagination for navigating large result sets
3. Maintain query performance (<500ms)
4. Preserve backward compatibility with existing searches
5. Support natural language pagination requests ("show me more", "next page")

### Non-Goals
1. Full-text search ranking/relevance scoring (future enhancement)
2. Fuzzy matching or spell correction for oracle text
3. Advanced query operators (AND/OR/NOT between phrases)
4. Caching or pre-computed search indices (optimization deferred)
5. Exposing raw SQL query interface

---

## Decisions

### Decision 1: Oracle Text Search Implementation

**Choice**: Case-insensitive substring matching with SQL `LIKE` operator and wildcards

**Rationale**:
- Simple to implement and understand (no external dependencies)
- Sufficient for exact phrase matching ("target creature you control")
- SQLite LIKE is reasonably fast with indexed columns
- Avoids complexity of FTS5 setup/migration

**Query pattern**:
```python
# For oracle_text_phrases = ["target creature", "gains flying"]
query = query.where(
    CardModel.oracle_text.ilike(f"%{phrase1}%"),
    CardModel.oracle_text.ilike(f"%{phrase2}%")
)
```

**Alternatives considered**:
- **SQLite FTS5**: More powerful, but requires schema migration and index maintenance. Deferred for MVP.
- **Regex matching**: Flexible, but slower and less predictable performance.
- **Pre-tokenized keywords**: Already done, but loses phrase ordering and context.

### Decision 2: Phrase Matching Logic

**Choice**: AND logic across all phrases (all must appear in oracle text)

**Rationale**:
- Consistent with existing filter semantics (types, keywords use AND)
- Reduces false positives (user wants BOTH "target creature" AND "gains flying")
- Simpler UX than exposing AND/OR operators

**Example**:
- Query: `["target creature you control", "gains flying"]`
- Matches: "Target creature you control gains flying until end of turn" ✅
- Doesn't match: "Target creature you control gets +1/+1" ❌ (missing "gains flying")

**Alternatives considered**:
- **OR logic**: Too many results, defeats purpose of precision
- **Explicit AND/OR operators**: Complex UX, deferred to future enhancement

### Decision 3: Pagination Implementation

**Choice**: Offset-based pagination with page number and page size

**Parameters**:
- `page: int = 1` (1-indexed for natural UX)
- `page_size: int = 20` (default), max 50
- Deprecate `max_results` but maintain backward compatibility

**Calculation**:
```python
offset = (page - 1) * page_size
limit = page_size
total_pages = math.ceil(total_count / page_size)
```

**Return metadata**:
```python
PaginatedResult(
    items=[Card, ...],
    total_count=52,
    page=1,
    page_size=20,
    total_pages=3
)
```

**Rationale**:
- Simple to implement and understand
- Familiar pattern from web APIs
- Sufficient for expected result set sizes (<1000 cards per query)
- Agent can easily increment page number for "show me more" requests

**Alternatives considered**:
- **Cursor-based pagination**: More efficient for very large sets, but adds complexity and state management. Deferred.
- **Infinite scroll**: Requires stateful continuation tokens. Not suitable for conversational UI.

### Decision 4: Backward Compatibility

**Choice**: Maintain `max_results` parameter, map to `page_size` when present

**Behavior**:
- If `max_results` provided and `page`/`page_size` not: Use `max_results` as `page_size`, `page=1`
- If `page_size` provided: Use `page_size`, ignore `max_results`
- Default: `page=1, page_size=20`

**Rationale**:
- Existing code continues to work unchanged
- Graceful migration path for users
- Clear deprecation path (document max_results as legacy)

### Decision 5: Pagination Metadata in Results

**Choice**: Include pagination context in formatted output

**Format**:
```
Found 52 cards (Page 1 of 3, showing 1-20):
[card list]

There are 32 more results. Say "next page" or "show me more" to see page 2.
```

**Rationale**:
- Users understand where they are in result set
- Clear call-to-action for next page
- Agent can parse natural language pagination requests
- Transparent about total results available

---

## Technical Design

### Data Layer Changes

**File**: `src/data/schemas/pagination.py` (new)
```python
from typing import Generic, TypeVar

T = TypeVar("T")

class PaginatedResult(BaseModel, Generic[T]):
    items: list[T]
    total_count: int
    page: int
    page_size: int
    total_pages: int
```

**File**: `src/data/repositories/card.py`

Updated signature:
```python
async def search_advanced(
    self,
    colors: list[str] | None = None,
    types: list[str] | None = None,
    keywords: list[str] | None = None,
    oracle_text_phrases: list[str] | None = None,  # NEW
    mana_value_min: float | None = None,
    mana_value_max: float | None = None,
    rarity: str | list[str] | None = None,
    page: int = 1,  # NEW
    page_size: int = 20,  # NEW
    limit: int | None = None,  # DEPRECATED, for backward compat
    format_filter: str | None = None,
) -> PaginatedResult[Card]:
    """Search with pagination and oracle text phrases."""
```

Implementation:
```python
# Oracle text filtering
if oracle_text_phrases:
    for phrase in oracle_text_phrases:
        query = query.where(CardModel.oracle_text.ilike(f"%{phrase}%"))

# Pagination
offset = (page - 1) * page_size
query_limit = page_size

# Get total count (before pagination)
count_query = select(func.count()).select_from(query.subquery())
total_count = await self.session.scalar(count_query)

# Apply pagination
query = query.offset(offset).limit(query_limit)

# Execute
results = await self.session.scalars(query)
cards = [Card.model_validate(card) for card in results]

# Calculate pagination metadata
total_pages = math.ceil(total_count / page_size)

return PaginatedResult(
    items=cards,
    total_count=total_count,
    page=page,
    page_size=page_size,
    total_pages=total_pages
)
```

### Agent Layer Changes

**File**: `src/agent/tools/card_search.py`

Updated `CardSearchFilters`:
```python
class CardSearchFilters(BaseModel):
    # ... existing fields ...
    oracle_text: list[str] | None = Field(
        default=None,
        description="Oracle text phrases to search for (case-insensitive). "
        "ALL phrases must appear in the card's oracle text. "
        "For example: ['target creature you control', 'gains flying']"
    )
    page: int = Field(
        default=1,
        description="Page number for pagination (1-indexed). Use for 'next page' requests."
    )
    page_size: int = Field(
        default=20,
        description="Number of results per page (max 50)."
    )
    max_results: int | None = Field(
        default=None,
        description="DEPRECATED: Use page_size instead. Maintained for backward compatibility."
    )
```

Updated tool function:
```python
async def search_cards_advanced(
    ctx: RunContext[AgentDependencies],
    filters: CardSearchFilters,
    auto_filter: bool = True,
) -> str:
    # Handle backward compat
    if filters.max_results and not filters.page_size:
        page_size = filters.max_results
        page = 1
    else:
        page_size = min(filters.page_size, 50)  # Cap at 50
        page = filters.page

    # Call repository with pagination
    result = await repo.search_advanced(
        colors=filters.colors,
        types=filters.types,
        keywords=filters.keywords,
        oracle_text_phrases=filters.oracle_text,  # NEW
        mana_value_min=filters.mana_value_min,
        mana_value_max=filters.mana_value_max,
        rarity=filters.rarity,
        page=page,  # NEW
        page_size=page_size,  # NEW
        format_filter=format_filter,
    )

    # Format with pagination metadata
    return _format_search_results_paginated(result, filters, format_filter, auto_filter)
```

---

## Risks / Trade-offs

### Risk 1: Oracle Text Search Performance
**Risk**: `LIKE '%phrase%'` queries can be slow on large datasets

**Mitigation**:
- Oracle text column is already indexed (verify in schema)
- Typical result sets are <1000 cards with other filters applied
- Monitor query performance, add `EXPLAIN QUERY PLAN` logging
- Future: Consider SQLite FTS5 if performance degrades

**Trade-off**: Simple implementation now vs. potential optimization later

### Risk 2: Case Sensitivity Edge Cases
**Risk**: Case-insensitive matching may miss cards with unusual capitalization

**Mitigation**:
- SQLite `ILIKE` handles standard case folding
- Scryfall oracle text is consistently formatted
- Document expected behavior in tool docstring

**Trade-off**: Simplicity vs. perfect Unicode case handling

### Risk 3: Pagination State in Conversations
**Risk**: Users lose context between pagination requests

**Mitigation**:
- Include pagination metadata in every response
- Agent can track last search in conversation history
- Clear messaging: "Page 1 of 3" helps users orient

**Trade-off**: Stateless pagination (user must remember context) vs. server-side state management

### Risk 4: Backward Compatibility Confusion
**Risk**: Two parameters for same concept (`max_results` vs `page_size`)

**Mitigation**:
- Document `max_results` as deprecated
- Clear precedence: `page_size` overrides `max_results`
- Future: Remove `max_results` in v2.0

**Trade-off**: Temporary API complexity vs. breaking existing code

---

## Migration Plan

### Phase 1: Implementation (This Change)
1. Add `oracle_text_phrases` and pagination to repository
2. Add `oracle_text`, `page`, `page_size` to tool
3. Deprecate `max_results` (maintain support)
4. Update tests and documentation

### Phase 2: Rollout
1. No database migration required (oracle_text column exists)
2. No breaking changes (backward compatible)
3. Update CLAUDE.md with usage examples
4. Resolve bug 77c559f3

### Phase 3: Future Enhancements (Deferred)
1. SQLite FTS5 integration for ranking
2. Remove `max_results` parameter (breaking change, v2.0)
3. Cursor-based pagination for very large sets
4. Query performance optimization (caching, indices)

### Rollback Plan
If oracle text search causes performance issues:
1. Add feature flag: `ENABLE_ORACLE_TEXT_SEARCH=false`
2. Return empty results for `oracle_text` queries when disabled
3. Investigate FTS5 migration or query optimization
4. Pagination remains unaffected (independent feature)

---

## Open Questions

1. **Q**: Should we limit the number of oracle text phrases?
   **A**: Deferred. Monitor usage, add limit if needed (e.g., max 5 phrases)

2. **Q**: Should oracle text search support regex or wildcards?
   **A**: No. Keep simple substring matching for MVP. User can use multiple phrases for precision.

3. **Q**: Should we cache pagination results to avoid re-querying?
   **A**: No. Query performance is sufficient, caching adds complexity. Revisit if needed.

4. **Q**: How should agent handle "show me more" without explicit page number?
   **A**: Agent infers from conversation context: increment last page number. No special state needed.

---

## Validation Criteria

### Functional Correctness
- [ ] Oracle text search returns only cards matching ALL phrases
- [ ] Case-insensitive matching works (e.g., "Flying" matches "flying")
- [ ] Pagination returns correct page with correct offset
- [ ] Total count and total pages calculated correctly
- [ ] Backward compatibility: `max_results` still works

### Performance
- [ ] Oracle text + pagination query completes in <500ms
- [ ] Combined filters (colors + types + oracle text + pagination) <500ms
- [ ] No N+1 queries (verify with SQL logging)

### User Experience
- [ ] Bug 77c559f3 scenario resolves correctly (returns 3 cards, not 31)
- [ ] Pagination metadata clearly indicates position ("Page 1 of 3")
- [ ] "No results" suggestions mention oracle text search
- [ ] Agent can handle "show me more" / "next page" naturally

### Edge Cases
- [ ] Oracle text search with None/empty list returns all cards
- [ ] Pagination beyond last page returns empty results
- [ ] Page size > 50 capped at 50
- [ ] Oracle text with special characters (quotes, apostrophes) handled correctly
