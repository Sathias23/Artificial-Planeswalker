# Tech-Spec: Synergy Suggestions User Request Override

**Created:** 2025-12-08
**Status:** Completed

## Overview

### Problem Statement

The `suggest_synergy_cards` tool currently operates fully automatically - it analyzes deck composition and suggests cards based on detected synergies and gaps. Users have no way to guide the suggestions toward specific card categories (removal, card draw, lands, tribal support, etc.).

When a user says "suggest removal cards for me suitable for this deck", the agent has no parameter to pass this intent to the suggestion tool, resulting in generic synergy-based suggestions that may not address the user's immediate need.

### Solution

Add an optional `user_request: str | None` parameter to the `suggest_synergy_cards` tool that:

1. Gets passed to the **Analysis LLM** as a constraint/focus area
2. Guides search criteria generation toward the user's specific request
3. Influences the **Curation LLM** to prioritize cards matching the request
4. Preserves deck-awareness (color identity, format, mana curve considerations)

### Scope

**In Scope:**
- Add `user_request` parameter to `suggest_synergy_cards` function signature
- Modify analysis prompt to incorporate user request when provided
- Modify curation prompt to prioritize user request when provided
- Update tool docstring for agent understanding
- Add unit tests for new parameter behavior

**Out of Scope:**
- Changes to UI signal handling (existing `has_suggestions` signal unchanged)
- Changes to `detect_deck_synergies` tool (pattern-based, not LLM-hybrid)
- New tool creation (enhancing existing tool)

## Context for Development

### Codebase Patterns

**Tool Parameter Pattern** (from `src/agent/tools/card_lookup.py`):
```python
async def lookup_card_by_name(
    ctx: RunContext[AgentDependencies],
    name: str,
    auto_filter: bool = True,  # Optional parameter with default
) -> str | dict[str, Any]:
```

**Pydantic Model Pattern** (from existing `DeckAnalysis`):
- Structured outputs use Pydantic models with `Field()` descriptions
- LLM agents receive prompts and return typed outputs

**Agent Prompt Modification Pattern**:
- Analysis and curation prompts are built as f-strings
- Conditional sections added based on context

### Files to Reference

| File | Purpose |
|------|---------|
| `src/agent/tools/synergy_suggestions.py` | Main implementation to modify |
| `src/agent/tools/card_lookup.py:28-52` | Example of optional tool parameters |
| `tests/unit/agent/tools/test_synergy_suggestions.py` | Test file to extend |

### Technical Decisions

1. **Parameter Type**: `user_request: str | None = None`
   - Optional string, defaults to None (preserves backward compatibility)
   - Agent decides when to populate based on user's message

2. **Prompt Injection Strategy**: Conditional sections in both prompts
   - Analysis: "USER REQUEST: {user_request}\nFocus your analysis on..."
   - Curation: "USER PRIORITY: {user_request}\nPrioritize cards that..."

3. **Validation**: No strict validation of user_request content
   - LLM interprets natural language flexibly
   - Empty string treated as None

## Implementation Plan

### Tasks

- [x] Task 1: Add `user_request` parameter to `suggest_synergy_cards` function signature
  - Add parameter with type `str | None = None`
  - Update function docstring to document the parameter
  - Ensure backward compatibility (None = existing behavior)

- [x] Task 2: Modify analysis prompt to incorporate user request
  - Add conditional section when `user_request` is provided
  - Instruct LLM to focus search criteria on user's request
  - Preserve deck-aware context (colors, format, curve)

- [x] Task 3: Modify curation prompt to prioritize user request
  - Add conditional section when `user_request` is provided
  - Instruct LLM to prioritize cards matching user's intent
  - Maintain synergy explanations in output

- [x] Task 4: Add unit tests for user_request parameter
  - Test None behavior (unchanged from current)
  - Test with user_request provided (prompt includes request)
  - Test empty string treated as None

- [x] Task 5: Run full test suite and verify no regressions

### Acceptance Criteria

- [x] AC1: When `user_request=None`, tool behaves identically to current implementation
  - Given: A deck with 10+ cards and no user_request
  - When: `suggest_synergy_cards` is called
  - Then: Suggestions are based on detected synergies (unchanged behavior)

- [x] AC2: When `user_request="removal"`, suggestions focus on removal spells
  - Given: A deck with 10+ cards and user_request="removal"
  - When: `suggest_synergy_cards` is called
  - Then: Analysis criteria includes removal-focused searches
  - And: Suggested cards are primarily removal (destroy, exile, damage)

- [x] AC3: User request is passed to both analysis and curation stages
  - Given: A user_request value is provided
  - When: Internal LLM agents are invoked
  - Then: Both analysis_prompt and curation_prompt contain the user_request

- [x] AC4: Deck context is preserved when user_request is provided
  - Given: A red/white deck with user_request="card draw"
  - When: `suggest_synergy_cards` is called
  - Then: Suggestions respect color identity (R/W cards only)
  - And: Suggestions respect format filter if set

- [x] AC5: Empty string user_request is treated as None
  - Given: user_request=""
  - When: `suggest_synergy_cards` is called
  - Then: Behaves as if user_request=None

## Additional Context

### Dependencies

- No new dependencies required
- Uses existing PydanticAI agent infrastructure
- Uses existing `DeckAnalysis` and `CardSuggestions` models (no changes needed)

### Testing Strategy

**Unit Tests** (mock LLM agents):
- Verify prompt construction includes user_request when provided
- Verify prompt construction excludes user_request section when None
- Verify empty string normalization

**Integration Test** (optional, requires API key):
- Manual verification that "removal" request yields removal-focused suggestions
- Manual verification that "lands" request yields land-focused suggestions

### Notes

**Example User Interactions:**

1. User: "Suggest some removal cards for my deck"
   - Agent calls: `suggest_synergy_cards(user_request="removal cards")`
   - Result: Focus on destroy, exile, damage-based removal

2. User: "What card draw would work well here?"
   - Agent calls: `suggest_synergy_cards(user_request="card draw")`
   - Result: Focus on draw spells that fit deck's colors/strategy

3. User: "Suggest cards for my deck" (no specific request)
   - Agent calls: `suggest_synergy_cards()` (no user_request)
   - Result: Standard synergy-based suggestions (current behavior)

**Prompt Modification Examples:**

Analysis prompt addition:
```
USER REQUEST: {user_request}
Focus your search criteria on cards that address this request while still
considering the deck's overall composition and needs.
```

Curation prompt addition:
```
USER PRIORITY: {user_request}
When selecting your top picks, prioritize cards that best address the user's
specific request while maintaining synergy with the deck.
```
