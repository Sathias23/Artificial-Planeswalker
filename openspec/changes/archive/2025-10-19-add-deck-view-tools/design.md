# Design Document: Deck View and Management Tools

## Context

Story 4.4 from the PRD requires adding deck viewing and card management capabilities to the PydanticAI agent. Users need to:
1. View their deck contents in a formatted, readable way
2. Remove cards or modify quantities through natural language
3. Work with an "active deck" without repeating the deck name in every request

The existing `DeckRepository` (from `deck-management` capability) provides CRUD operations, but the agent currently has no tools to expose this functionality to users.

**Constraints**:
- Agent layer must remain UI-independent (no Chainlit imports in agent code)
- Deck display formatting should be reusable across potential future UIs
- Tools must handle edge cases gracefully (empty deck, invalid quantities, etc.)

**Stakeholders**:
- End users (MTG players building decks)
- Agent layer (needs deck management tools)
- UI layer (needs formatted deck displays)

## Goals / Non-Goals

### Goals
- Enable users to view deck contents through natural language queries
- Support adding, removing, and updating cards in the active deck
- Provide clear, formatted deck displays grouped by type or mana cost
- Track "active deck" context across tool invocations in a session
- Validate all deck operations (quantities, card existence, etc.)

### Non-Goals
- Deck creation tool (covered by Story 4.2)
- Deck loading/switching tool (covered by Story 4.5)
- Mana curve analysis (covered by Epic 5 - Story 5.1)
- Synergy detection (covered by Epic 5 - Stories 5.3-5.4)
- Visual deck rendering (deferred to CopilotKit UI)

## Decisions

### Decision 1: Active Deck Session Context
**What**: Store `active_deck_id` in `AgentDependencies.deck_context` dict to track which deck the user is currently building.

**Why**:
- Enables natural language like "add 4 Lightning Bolt" without "...to deck X"
- Persists across tool invocations within a session
- Aligns with existing `format_context` pattern for format filter

**Alternatives considered**:
1. **Require deck ID in every tool call** - Rejected: Poor UX, verbose tool calls
2. **Use global variable** - Rejected: Not thread-safe, breaks multi-user support
3. **Store in database session** - Rejected: Couples agent to database, not truly session state

**Implementation**:
```python
# In src/agent/dependencies.py
class AgentDependencies:
    deck_context: dict[str, Any]  # {"active_deck_id": "deck-123" | None}
```

### Decision 2: Deck Display Grouping Strategy
**What**: Default to grouping by card type (Creatures, Spells, Lands), with optional mana cost grouping for future enhancement.

**Why**:
- Card type grouping is the most common deck list format (matches MTGA, tournament decklists)
- Easier to scan for specific card categories
- Mana cost grouping is useful for curve analysis but not primary view (Epic 5)

**Alternatives considered**:
1. **Group by mana cost only** - Rejected: Less intuitive for casual deck review
2. **Alphabetical only** - Rejected: Hard to see deck composition at a glance
3. **Both simultaneously** - Rejected: Too complex for MVP, can add later

**Implementation**:
- `format_deck_for_display(deck, grouping="type")` in `src/ui/formatters.py`
- Default grouping: Creatures → Spells (Instants/Sorceries/Enchantments/Artifacts) → Lands
- Within each group: Sort by mana cost ascending, then alphabetically

### Decision 3: Tool Responsibilities - View vs Modify
**What**: Separate tools for viewing (`view_deck`) and modifying (`remove_card_from_deck`, `update_card_quantity`) decks.

**Why**:
- Clear separation of concerns (read vs write operations)
- Enables different permission models in the future (if needed)
- Simpler tool documentation for LLM schema generation

**Alternatives considered**:
1. **Single `manage_deck` tool with operation parameter** - Rejected: Too broad, LLM might confuse operations
2. **Combine remove and update into single tool** - Rejected: Different use cases, different validation logic

**Implementation**:
- `view_deck()` - Read-only, returns formatted deck list
- `remove_card_from_deck(card_name, sideboard)` - Deletes DeckCard entry
- `update_card_quantity(card_name, quantity, sideboard)` - Updates existing quantity

### Decision 4: Card Lookup in Deck Tools
**What**: Deck management tools accept `card_name` (string) and perform lookup internally to resolve to `card_id`.

**Why**:
- More natural for LLM tool calls ("remove Lightning Bolt" not "remove card-uuid-123")
- Handles partial matches and suggestions (reuse existing card lookup logic)
- Consistent with card query tools pattern

**Alternatives considered**:
1. **Require card_id parameter** - Rejected: LLM unlikely to have UUID from previous context
2. **Accept either name or ID** - Rejected: Adds complexity, validation burden

**Implementation**:
```python
# In view_deck tool
card = await ctx.deps.card_repository.find_by_name_exact(card_name)
if not card:
    return f"Card '{card_name}' not found. Check spelling or use card search."
```

### Decision 5: Edge Case Handling
**What**: All deck tools return user-friendly error messages for edge cases rather than raising exceptions.

**Edge cases**:
- View empty deck → Return "Your deck is empty. Add cards to get started."
- Remove more cards than present → Return "Deck only has X copies of Y. Remove up to X."
- Remove from non-existent deck → Return "No active deck. Create or load a deck first."
- Remove non-existent card → Return "Card Z not found in deck."

**Why**:
- Aligns with existing tool error handling pattern (see card lookup tools)
- Better UX than stack traces in chat
- Enables LLM to suggest corrections naturally

**Implementation**: Use early returns with descriptive strings in all tools.

## Risks / Trade-offs

### Risk 1: Active Deck Context Lost on Session Expiry
**Risk**: If Chainlit session expires, active deck context is lost.

**Mitigation**:
- Document session behavior in user-facing messages ("Your active deck is [name]")
- Future: Add `set_active_deck` tool to explicitly switch active deck
- Acceptable for MVP since sessions are typically long-lived during deck building

### Risk 2: Deck Display Performance for Large Decks
**Risk**: Formatting 100+ card Commander decks might be slow or verbose in chat.

**Mitigation**:
- MVP focuses on Standard (60-card decks) - acceptable performance
- Format function should be O(n) complexity (single pass grouping)
- Future: Add pagination or summary view for large decks

**Trade-off**: Simplicity over performance optimization for MVP. Monitor in production.

### Risk 3: Card Name Ambiguity in Removal
**Risk**: User says "remove Bolt" but multiple "Bolt" cards exist in deck.

**Mitigation**:
- Exact match preferred over partial match
- If ambiguous, return list of matching cards: "Did you mean: Lightning Bolt, Incinerate?"
- Reuse existing card lookup disambiguation logic

## Migration Plan

**No migration required** - This is a purely additive change with no breaking changes.

**Rollout**:
1. Implement tools in `src/agent/tools/deck_tools.py`
2. Add formatters to `src/ui/formatters.py`
3. Update `AgentDependencies` to include `deck_context`
4. Register tools with agent in `src/agent/core.py`
5. Add integration tests verifying tool behavior
6. Deploy and test in Chainlit UI

**Rollback**: If issues arise, remove tool registration from agent (tools won't be called). No data migration needed.

## Open Questions

1. **Sideboard Support**: Should `view_deck` show sideboard by default or require explicit request?
   - **Answer (for now)**: Show both mainboard and sideboard in deck view, grouped separately. User can ask "show mainboard only" if needed.

2. **Quantity Update vs Remove**: Should `update_card_quantity(quantity=0)` be equivalent to `remove_card_from_deck()`?
   - **Answer (for now)**: Yes - quantity 0 triggers removal. This matches intuitive behavior.

3. **Card Sorting Within Groups**: Should sorting be mana cost → name, or name only?
   - **Answer (for now)**: Mana cost → name (more useful for deck analysis). Can make configurable later.

4. **Active Deck Initialization**: When should active deck be set?
   - **Answer (for now)**: Set when deck is created (Story 4.2) or loaded (Story 4.5). Tools fail gracefully if no active deck.
