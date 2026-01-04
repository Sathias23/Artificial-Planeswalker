# Design: Card Lookup Tool

## Research Findings

### Archon RAG Knowledge

**Source: ai.pydantic.dev (PydanticAI Documentation)**

Key patterns discovered:

1. **Tool Decorator Pattern**:
   - `@agent.tool` decorator inspects function signature and docstring
   - First parameter must be `RunContext[DepsType]` for dependency injection
   - Subsequent parameters become tool schema for LLM
   - Return type should be serializable (str, dict, Pydantic model)

2. **Dependency Management**:
   - Agent dependency type specified via `Agent(..., deps_type=MyDepsType)`
   - Dependencies injected at runtime via `agent.run(..., deps=my_deps)`
   - Enables testing with mock repositories

3. **Testing Strategy**:
   - Unit tests: Mock `RunContext` and dependencies
   - Integration tests: Use real agent with in-memory SQLite database
   - PydanticAI provides `TestModel` for controlled LLM behavior in tests

### Codebase Analysis

**Existing Infrastructure**:
- `CardRepository` has two relevant methods returning `Card` schemas
- `Card` schema contains all necessary fields (name, mana_cost, type_line, oracle_text, colors)
- Agent currently has `Agent[None, str]` type - needs update for dependencies

## Context

The PydanticAI agent needs access to the local card database to answer user queries about Magic: The Gathering cards. The card lookup tool is the first tool in the agent's toolset, establishing patterns for future tools (deck validation, synergy detection, etc.).

## Goals / Non-Goals

### Goals
- Enable natural language card queries ("Show me Lightning Bolt", "Find cards with bolt")
- Handle both exact and partial name matches intelligently
- Provide helpful error messages for ambiguous or not-found queries
- Establish dependency injection pattern for agent tools
- Maintain type safety throughout tool implementation

### Non-Goals
- Card search by attributes other than name (colors, types, etc.) - deferred to future stories
- Fuzzy matching or spell correction - partial match is sufficient for MVP
- Caching or performance optimization - database queries are already fast (<500ms)
- Multi-card batch lookups - single card per tool invocation is sufficient

## Technical Decisions

### Decision 1: Tool Organization

**What**: Create dedicated `src/agent/tools/` module for all agent tools

**Why**:
- Keeps agent core focused on configuration
- Enables easy addition of future tools (deck validation, synergy detection)
- Follows modular architecture pattern from project conventions
- Each tool file can be independently tested

**Alternatives considered**:
- Define tools inline in `src/agent/core.py` - rejected, violates separation of concerns
- Use `FunctionToolset` class - deferred, single tool doesn't justify toolset overhead

### Decision 2: Dependency Type Structure

**What**: Create `AgentDependencies` dataclass containing repository instances

**Why**:
- Type-safe access to repositories via `ctx.deps.card_repository`
- Easy to extend with future repositories (deck, synergy, etc.)
- Clean testing interface - mock entire dependencies object
- Follows PydanticAI best practices from documentation

**Structure**:
```python
@dataclass
class AgentDependencies:
    """Dependencies injected into agent tools via RunContext."""
    card_repository: CardRepository
    # Future: deck_repository, synergy_engine, etc.
```

**Alternatives considered**:
- Pass `CardRepository` directly as deps type - rejected, not extensible
- Use dict with string keys - rejected, loses type safety
- Dependency injection container - rejected, overkill for MVP scope

### Decision 3: Query Strategy (Exact vs Partial)

**What**: Implement "try exact first, fall back to partial" strategy

**Why**:
- Most precise match when user provides full card name
- Partial match catches typos and incomplete names
- Reduces ambiguity for exact matches (e.g., "Bolt" vs "Lightning Bolt")
- Mirrors typical search UX patterns

**Algorithm**:
```python
1. Attempt exact match (case-insensitive)
2. If found: Return single card
3. If not found: Attempt partial match
4. If 1 result: Return that card
5. If 2-10 results: Return list with "Did you mean?" message
6. If >10 results: Return truncated list with refinement suggestion
7. If 0 results: Return helpful "not found" message
```

**Alternatives considered**:
- Partial match only - rejected, too many false positives for common names
- Require exact match - rejected, poor UX for users who can't remember full names
- Fuzzy matching (Levenshtein distance) - deferred, complexity not justified for MVP

### Decision 4: Return Type Format

**What**: Return formatted string (not raw Card schema) from tool

**Why**:
- LLM expects human-readable tool results
- Agent can present card info naturally in conversation
- String format is flexible for future formatting changes
- Raw schemas are too verbose for LLM context window

**Format**:
```
Card: {name}
Mana Cost: {mana_cost}
Type: {type_line}
Text: {oracle_text}
Colors: {colors_joined}
```

**Alternatives considered**:
- Return `Card` schema directly - rejected, not LLM-friendly
- Return JSON string - rejected, harder for LLM to parse naturally
- Return only card name - rejected, defeats purpose of lookup

### Decision 5: Error Handling Strategy

**What**: Return user-friendly error strings (not raise exceptions) for expected errors

**Why**:
- Agent can communicate errors naturally to user
- Exceptions break conversation flow
- "Not found" is an expected outcome, not exceptional
- Maintains conversational UX

**Error types**:
- **Not found**: "I couldn't find a card matching '{query}'. Could you check the spelling?"
- **Ambiguous**: "I found {count} cards matching '{query}': {names}. Which did you mean?"
- **Database error**: Raise exception (unexpected, should be logged and handled by agent)

**Alternatives considered**:
- Raise custom exceptions - rejected, breaks conversation flow
- Return None - rejected, LLM can't explain failure to user
- Return error codes - rejected, not conversational

## Risks / Trade-offs

### Risk 1: Partial Match Ambiguity
**Risk**: User says "Show me Bolt" - finds 20 cards with "bolt" in name

**Mitigation**:
- Limit partial match results to 10 cards
- Provide helpful "refine your search" message
- Future: Add confidence scoring based on query length

**Trade-off**: Accept some ambiguity for better UX (vs requiring exact names)

### Risk 2: Context Window Overhead
**Risk**: Verbose card descriptions consume LLM context tokens

**Mitigation**:
- Return only essential fields (not full card JSON)
- Truncate oracle text to 200 chars for long cards
- Future: Add "brief" vs "detailed" lookup modes

**Trade-off**: Some info omitted vs manageable context usage

### Risk 3: Async Database Access
**Risk**: Tool blocks on slow database queries

**Mitigation**:
- CardRepository methods already async
- SQLite queries are fast (<10ms for name lookups)
- Database indexed on card name (Story 1.2)

**Trade-off**: None - async is required by PydanticAI, no performance concerns

## Implementation Plan

### Phase 1: Core Tool (This Story)
1. Create `AgentDependencies` dataclass
2. Implement `lookup_card_by_name` tool with exact + partial logic
3. Update `create_agent()` to accept and configure dependencies
4. Unit tests for tool logic (mocked repository)
5. Integration tests for agent + tool + database

### Phase 2: UI Integration (Separate Story)
1. Modify Chainlit handlers to create `AgentDependencies`
2. Pass dependencies to `agent.run()` calls
3. Manual testing of conversational card lookups

### Phase 3: Future Enhancements (Post-MVP)
- Add "brief" vs "detailed" lookup modes
- Implement fuzzy matching for typo tolerance
- Add card image URLs to tool responses
- Support batch lookups ("Show me Lightning Bolt and Counterspell")

## Migration Plan

### Breaking Changes
None - this is a new capability with no existing usage.

### Rollback Plan
Remove tool decorator and revert agent configuration changes. No database migrations required.

## Open Questions

1. **Should tool handle multi-face cards specially?** (e.g., double-faced cards)
   - Decision: Return first face in formatted string, note "// {back_face_name}" for DFCs
   - Rationale: Keeps output concise, users rarely need full back face details immediately

2. **Should exact match be case-sensitive?**
   - Decision: No, use case-insensitive (`.ilike()` already in CardRepository)
   - Rationale: Users shouldn't need to remember exact capitalization

3. **What if user asks for card by nickname?** (e.g., "Bob" for "Dark Confidant")
   - Decision: Out of scope for MVP, requires nickname database
   - Future enhancement: Add nickname mapping table
