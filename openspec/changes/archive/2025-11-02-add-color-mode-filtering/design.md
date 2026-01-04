# Color Mode Filtering - Technical Design

## Context

Magic: The Gathering cards have a `colors` field stored as a JSON array in SQLite (e.g., `["W", "U"]` for Azorius cards). The current implementation only supports OR logic when filtering by multiple colors, which is insufficient for common deck-building queries.

**Current implementation** (`src/data/repositories/card.py:312-317`):
```python
if colors:
    color_conditions = []
    for color in colors:
        color_conditions.append(cast(CardModel.colors, String).like(f'%"{color}"%'))
    stmt = stmt.where(or_(*color_conditions))
```

**Constraints:**
- SQLite 3.45+ with JSON1 extension (already in use)
- Must maintain backward compatibility (default behavior unchanged)
- Query performance target: <500ms for complex searches
- Offline-first: No external API calls

**Stakeholders:**
- Users building multicolor decks (Azorius, Boros, etc.)
- Agent needs to understand and fulfill precise color queries
- Repository layer maintainers

## Goals / Non-Goals

**Goals:**
- Support four color filtering modes: any, all, exact, at_most
- Maintain backward compatibility (default to "any")
- Type-safe implementation with Enum for color modes
- Test coverage >80% for new functionality
- Clear documentation for LLM agent interpretation

**Non-Goals:**
- Optimizing for edge cases with >3 colors (rare in practice)
- Supporting custom color logic expressions (e.g., "(W OR U) AND (R OR G)")
- Changing format filter behavior
- Modifying single-color `find_by_colors()` method (separate use case)

## Decisions

### Decision 1: Use Enum for Color Modes

**Choice:** Use `Literal["any", "all", "exact", "at_most"]` type hint

**Rationale:**
- Type-safe at runtime and in IDEs
- Self-documenting for LLM agent
- Prevents invalid mode strings
- Pydantic validates automatically

**Alternatives considered:**
- Boolean flags (`colors_any`, `colors_all`, etc.) - Rejected: mutually exclusive flags are error-prone
- Scryfall-style operators (`:`, `=`, `>=`, `<=`) - Rejected: less intuitive for LLM

### Decision 2: SQLite JSON Operations

**Implementation for each mode:**

```python
# ANY (current, default) - OR logic
stmt = stmt.where(or_(
    cast(CardModel.colors, String).like(f'%"{color}"%')
    for color in colors
))

# ALL - AND logic (all colors must be present)
stmt = stmt.where(and_(
    cast(CardModel.colors, String).like(f'%"{color}"%')
    for color in colors
))

# EXACT - all colors present + array length matches
stmt = stmt.where(
    and_(
        # Has all specified colors
        *[cast(CardModel.colors, String).like(f'%"{color}"%') for color in colors],
        # No extra colors
        func.json_array_length(CardModel.colors) == len(colors)
    )
)

# AT_MOST - each card color must be in allowed set
# Most complex - requires checking all card colors are in allowed list
# Implementation: Use json_each to iterate card colors, verify all in allowed set
# Alternative: Use combination of checks:
#   - Exclude cards with colors not in allowed set (W, U, B, R, G)
#   - Use NOT LIKE for colors not in the set
```

**Performance characteristics:**
- `any`/`all`: String pattern matching (fast, current performance)
- `exact`: Adds one `json_array_length()` call (negligible overhead)
- `at_most`: Most complex, may need optimization if slow in practice

### Decision 3: Empty Colors List Behavior

**Choice:** Empty `colors=[]` means "no color filter" (all cards), NOT "colorless cards only"

**Rationale:**
- Consistent with current behavior (None = no filter)
- Colorless cards use `colors=["C"]` convention (hypothetical) or separate parameter
- Edge case for colorless: `exact` mode with empty list could mean colorless

**Special case:** `color_mode="exact"` with `colors=[]` → colorless cards only

### Decision 4: Agent Tool Integration

Add `color_mode` field to `CardSearchFilters` with detailed descriptions:

```python
color_mode: Literal["any", "all", "exact", "at_most"] | None = Field(
    default="any",
    description=(
        "How to interpret the colors filter:\n"
        "- 'any': Contains ANY specified color (OR logic) - default\n"
        "- 'all': Contains ALL specified colors (AND logic)\n"
        "- 'exact': Exactly these colors, no more, no less\n"
        "- 'at_most': Only these colors or fewer (color identity)\n\n"
        "Examples:\n"
        "- colors=['W', 'U'], mode='any': white OR blue cards\n"
        "- colors=['W', 'U'], mode='all': multicolor cards with W AND U\n"
        "- colors=['W', 'U'], mode='exact': Azorius (W/U) cards only\n"
        "- colors=['W', 'U'], mode='at_most': colorless, mono-W, mono-U, or W/U"
    )
)
```

## Risks / Trade-offs

### Risk: "at_most" Mode Performance

**Risk:** Iterating JSON arrays to verify subset relationship may be slow for large result sets.

**Mitigation:**
- Implement simple version first using NOT LIKE for excluded colors
- Benchmark with real Scryfall dataset (~70K cards)
- If >500ms, optimize with:
  - Materialized color columns (W_count, U_count, etc.)
  - Denormalized color_count field
  - Pre-computed color identity strings

### Risk: Backward Compatibility

**Risk:** Adding new parameter might break existing calls.

**Mitigation:**
- Default `color_mode="any"` maintains current behavior
- All existing calls work unchanged
- No required parameter changes

### Risk: LLM Misunderstanding Color Modes

**Risk:** Agent might choose wrong mode for user queries like "Azorius cards."

**Mitigation:**
- Provide rich examples in field description
- Test with real user queries in integration tests
- Document MTG terminology mappings:
  - "Azorius" → `colors=["W", "U"], color_mode="exact"`
  - "White and blue" → `colors=["W", "U"], color_mode="all"` or `"exact"` (depends on context)
  - "White or blue" → `colors=["W", "U"], color_mode="any"`

### Trade-off: Complexity vs Flexibility

**Trade-off:** Four modes add complexity to the API.

**Justification:**
- MTG color system inherently has these distinct use cases
- Alternative (one mode) would require multiple tool calls
- Enum prevents misuse (better than boolean flags)
- Matches user mental model (guilds, color identity, etc.)

## Migration Plan

**Phase 1: Repository Layer (1-2 hours)**
1. Add `color_mode` parameter to `search_advanced()`
2. Implement filtering logic for each mode
3. Add unit tests with fixtures

**Phase 2: Agent Tools Layer (30 min)**
1. Add `color_mode` field to `CardSearchFilters`
2. Pass parameter through to repository
3. Update docstrings and examples

**Phase 3: Testing (1-2 hours)**
1. Unit tests for all four modes
2. Edge case tests (empty colors, single color, all 5 colors)
3. Integration tests with real card data
4. Performance benchmarks for `at_most` mode

**Phase 4: Documentation (30 min)**
1. Update CLAUDE.md with color mode examples
2. Update tool docstrings for LLM clarity

**Rollback plan:**
- If performance issues: disable `at_most` mode temporarily
- Default mode="any" preserves current behavior
- No database schema changes required

## Open Questions

1. **Should single-color queries with different modes behave identically?**
   - Example: `colors=["R"], mode="any"` vs `colors=["R"], mode="exact"`
   - Proposal: All modes return same results for single color (no-op for mode)
   - Alternative: Warn/error on redundant mode?

2. **How to handle colorless in "exact" mode?**
   - Proposal: `colors=[], mode="exact"` → colorless cards
   - Alternative: Require explicit `colorless=True` parameter?
   - Decision: Use empty list for now, can add explicit param later if needed

3. **Should we support hybrid mana colors?**
   - Context: Hybrid cards like "{W/U}" appear in colors as `["W", "U"]`
   - Proposal: Current filtering works for hybrid (treat as multicolor)
   - Non-goal: Special hybrid-specific filtering (future enhancement)

4. **Performance threshold for "at_most" mode?**
   - If `at_most` exceeds 500ms on real dataset, what optimization strategy?
   - Proposal: Measure first, optimize only if needed
   - Fallback: Denormalize color_count field if required
