# Proposal: Improve Deck Context Retention

## Problem Statement

The agent loses track of the active deck during long conversations with large search results, causing it to incorrectly create new decks instead of adding cards to the existing active deck. This results in:

- Multiple decks with similar names ("Fire Lord Zuko Deck", "Fire Lord Zuko", "Fire Lord Zuko Exile")
- Cards spread across different decks when user intended a single deck
- Poor user experience requiring manual deck consolidation

### Root Cause Analysis

**Technical Infrastructure (Working Correctly)**:
- ✅ Active deck ID stored in session manager
- ✅ Dependencies correctly load active deck from database
- ✅ All deck data accessible to tools

**Agent Decision-Making (Failing)**:
- ❌ Agent makes premature decisions without calling tools to check state
- ❌ Agent loses deck context when conversation history contains large search results (104 cards with full formatting)
- ❌ `keep_recent_messages` function limits history to 10 messages, but large messages consume significant context

### Evidence from Production Incident

Timeline from session `4e33b685-89dd-414a-a012-caeadef7bd9e`:

1. **21:06:47** - User: "create a deck and add 2 of zuko to it"
   - ✅ Created "Fire Lord Zuko Deck" (ID: 5a4e8678...)
   - ✅ Added Fire Lord Zuko to deck

2. **21:07:46** - User: "Lets look for red instants that could be cast using Zuko..."
   - Long conversation with 104 card search results
   - Consumed significant context window space

3. **21:09:17** - User: "add 2 boros charm"
   - ✅ Dependencies showed `active_deck_id=5a4e8678...` (deck WAS active!)
   - ❌ Agent responded "I don't have an active deck loaded" WITHOUT calling tools
   - ❌ Created NEW deck "Fire Lord Zuko" (81b2216a...)
   - Added Boros Charm to wrong deck

4. **21:18:11** - User: "add 2 kellan"
   - ❌ Created THIRD deck "Fire Lord Zuko Exile" (5af366a9...)
   - Added Kellan to wrong deck

The logs prove the active deck **was present** in dependencies, but the agent didn't recognize it from conversation context.

## Proposed Solution

Implement multi-layered improvements to prevent deck context loss:

### 1. System Message Deck State Injection (Primary Solution)

**Approach**: Inject active deck information into the system message on every agent run when a deck is active.

**Benefits**:
- Most reliable - system messages have highest attention weight
- Works regardless of conversation history length
- Minimal performance impact (single string template)

**Implementation**:
- Modify `run_agent_with_session` to check `deps.active_deck`
- If active deck exists, prepend to system message:
  ```
  ACTIVE DECK CONTEXT:
  - You currently have a deck loaded: "{deck.name}" (ID: {deck.id[:8]}...)
  - Format: {deck.format}
  - Cards: {len(deck.deck_cards)} cards
  - ALWAYS add cards to this deck unless user explicitly requests a new deck
  ```

### 2. Tool-First Approach (Secondary Defense)

**Approach**: Modify agent system prompt to mandate tool calls before making deck-related decisions.

**Benefits**:
- Prevents premature assumptions
- Forces verification of actual state
- Better error messages from tools vs agent guesses

**Implementation**:
- Update agent system prompt with explicit instruction:
  ```
  When user asks to add cards:
  1. ALWAYS call add_card_to_deck first
  2. If tool returns "No active deck", THEN create a new deck
  3. NEVER decide to create a deck without attempting add_card_to_deck first
  ```

### 3. Abbreviated Search Results (Tertiary Optimization)

**Approach**: Truncate large search results more aggressively to preserve context.

**Benefits**:
- Reduces context window consumption
- Preserves deck creation/load events in history
- Improves overall conversation coherence

**Implementation**:
- Modify `search_cards_advanced` tool to return abbreviated results
- Show first 10 cards with full details
- Show remaining cards as compact list (name only)
- Add "Use filters to narrow results" suggestion

### 4. Conversation History Optimization (Future Enhancement)

**Approach**: Implement smart message pruning that preserves deck-related context.

**Benefits**:
- Maintains critical deck context across long conversations
- Better than naive "last N messages" approach

**Implementation** (deferred to future change):
- Modify `keep_recent_messages` to detect and preserve deck operations
- Keep all messages with tool calls to `create_deck`, `load_deck`, `delete_deck`
- Prune large search results but keep deck state changes
- Increase message limit from 10 to 15 for deck-building sessions

## Scope

**In Scope**:
- System message deck state injection (Solution #1)
- Tool-first approach system prompt updates (Solution #2)
- Abbreviated search results formatting (Solution #3)
- Tests for new behavior

**Out of Scope**:
- Smart message pruning (Solution #4) - requires separate change proposal
- UI improvements (deck name validation to prevent similar names)
- Multi-deck session support (user actively building multiple decks)

## Success Criteria

1. Agent NEVER creates duplicate decks when adding cards to active deck
2. System message injection prevents context loss in 99% of cases
3. Tool-first approach catches remaining edge cases
4. Abbreviated results reduce context consumption by ~70% for large searches
5. All existing tests pass
6. New integration test validates fix for reported scenario

## Dependencies

- No blocking dependencies
- Builds on existing `agent-core` and `agent-tools` specs
- No database schema changes required

## Risk Assessment

**Low Risk**:
- System message injection is additive (doesn't break existing behavior)
- Tool-first approach improves error handling
- Abbreviated results maintain all functionality with better UX

**Testing Strategy**:
- Unit tests for message formatting
- Integration test reproducing exact bug scenario
- Manual validation with long conversations
