# Design: Improve Deck Context Retention

## Architecture Overview

This change introduces three defensive layers to prevent deck context loss:

```
┌─────────────────────────────────────────────────────────────────┐
│                   Agent Run (per message)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: System Message Injection                             │
│  ┌───────────────────────────────────────────────────────┐     │
│  │ IF deps.active_deck exists:                           │     │
│  │   Prepend "ACTIVE DECK: {name} ({id})" to system msg │     │
│  │ → Highest attention weight                            │     │
│  │ → Works regardless of history length                  │     │
│  └───────────────────────────────────────────────────────┘     │
│                           ↓                                     │
│  Layer 2: Tool-First System Prompt                             │
│  ┌───────────────────────────────────────────────────────┐     │
│  │ System prompt mandates:                               │     │
│  │ - "ALWAYS call add_card_to_deck before creating deck" │     │
│  │ - "Only create deck if tool says 'No active deck'"   │     │
│  │ → Prevents premature decisions                        │     │
│  └───────────────────────────────────────────────────────┘     │
│                           ↓                                     │
│  Layer 3: Abbreviated Search Results                           │
│  ┌───────────────────────────────────────────────────────┐     │
│  │ search_cards_advanced returns:                        │     │
│  │ - First 10 cards: Full details                        │     │
│  │ - Remaining: Compact list (name + mana cost only)     │     │
│  │ → Reduces context consumption ~70%                    │     │
│  └───────────────────────────────────────────────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Component Changes

### 1. Agent Core (`src/agent/core.py`)

#### 1.1 System Message Injection

**Function**: `run_agent_with_session`

**Current Behavior**:
```python
async def run_agent_with_session(
    user_input: str,
    session_id: str,
    deps: AgentDependencies,
    agent: Agent[AgentDependencies, str],
) -> RunResult[str]:
    history = _session_manager.get_history(session_id)
    result = await agent.run(
        user_input,
        message_history=history,
        deps=deps,
    )
    # ... update history ...
    return result
```

**New Behavior**:
```python
async def run_agent_with_session(
    user_input: str,
    session_id: str,
    deps: AgentDependencies,
    agent: Agent[AgentDependencies, str],
) -> RunResult[str]:
    history = _session_manager.get_history(session_id)

    # NEW: Inject active deck context into system message
    if deps.active_deck:
        deck_context = _build_deck_context_message(deps.active_deck)
        # Prepend to first system message or inject as new system message
        history = _inject_system_context(history, deck_context)

    result = await agent.run(
        user_input,
        message_history=history,
        deps=deps,
    )
    # ... update history ...
    return result
```

**New Helper Functions**:
```python
def _build_deck_context_message(deck: Deck) -> str:
    """Build system message describing active deck state.

    Returns concise, high-signal context that prevents agent confusion.
    """
    card_count = len(deck.deck_cards)
    deck_id_short = deck.id[:8]

    return (
        f"ACTIVE DECK CONTEXT:\n"
        f"- You currently have a deck loaded: \"{deck.name}\" (ID: {deck_id_short}...)\n"
        f"- Format: {deck.format}\n"
        f"- Cards: {card_count} cards currently in deck\n"
        f"- ALWAYS add cards to this deck unless user explicitly requests a new deck\n"
        f"- If user says 'add [card]', use add_card_to_deck tool on THIS deck"
    )


def _inject_system_context(
    history: list[ModelMessage],
    context: str,
) -> list[ModelMessage]:
    """Inject deck context into conversation history as system message.

    Strategy: Prepend to most recent system message, or create new one.
    System messages have highest attention weight in LLM processing.
    """
    # Find last system message
    for i in range(len(history) - 1, -1, -1):
        if history[i]["role"] == "system":
            # Prepend context to existing system message
            existing_content = history[i]["content"]
            history[i]["content"] = f"{context}\n\n{existing_content}"
            return history

    # No system message found - inject new one at start
    return [
        {"role": "system", "content": context},
        *history,
    ]
```

**Trade-offs**:
- ✅ Most reliable solution (system messages have highest weight)
- ✅ Works with any conversation length
- ✅ Minimal performance impact (<1ms per request)
- ⚠️ Slightly increases context window usage (~100 tokens)
- ⚠️ Requires careful message structure handling

### 2. Agent Tools System Prompt (`src/agent/core.py`)

#### 2.1 Tool-First Behavioral Constraint

**Location**: `create_agent()` function, system prompt

**Current System Prompt Excerpt**:
```
TOOL USAGE RULES:
1. ALWAYS use tools for card information (never from memory)
2. ALWAYS copy tool outputs exactly with all HTML/formatting intact
3. Your commentary can frame the output but must not replace it
4. NEVER autonomously add cards to decks - ONLY add cards when user explicitly requests it
```

**New System Prompt Addition**:
```
TOOL USAGE RULES:
1. ALWAYS use tools for card information (never from memory)
2. ALWAYS copy tool outputs exactly with all HTML/formatting intact
3. Your commentary can frame the output but must not replace it
4. NEVER autonomously add cards to decks - ONLY add cards when user explicitly requests it

DECK OPERATION RULES (CRITICAL):
5. When user asks to add cards:
   a. ALWAYS call add_card_to_deck tool FIRST
   b. If tool returns "No active deck", THEN create a new deck
   c. NEVER decide to create a deck without attempting add_card_to_deck first
   d. Trust the tool's error message over your assumptions about deck state

6. When user asks to create a deck:
   a. ALWAYS call create_deck tool explicitly
   b. Do NOT infer deck creation from "add card" requests
   c. Creating a deck requires explicit user intent
```

**Rationale**:
- Prevents agent from guessing about deck state
- Forces verification through tool calls
- Tools have accurate state from database
- Better error handling (tool provides context-specific errors)

### 3. Search Result Formatting (`src/agent/tools/card_tools.py`)

#### 3.1 Abbreviated Search Results

**Function**: `search_cards_advanced`

**Current Behavior**:
```python
# Returns full details for ALL cards (up to 100)
formatted_text = "Found 104 cards (Page 1 of 6, showing 1-20):\n\n"
for i, card in enumerate(cards, start=1):
    formatted_text += format_card_for_display(card)  # Full details per card
```

**New Behavior**:
```python
# Show first 10 cards with full details, rest as compact list
FULL_DETAIL_COUNT = 10

formatted_text = f"Found {total_count} cards (Page {page} of {total_pages}):\n\n"

# Full details for first N cards
for i, card in enumerate(cards[:FULL_DETAIL_COUNT], start=1):
    formatted_text += format_card_for_display(card)

# Compact list for remaining cards (if any)
if len(cards) > FULL_DETAIL_COUNT:
    formatted_text += "\n**Additional Results** (compact view):\n\n"
    for i, card in enumerate(cards[FULL_DETAIL_COUNT:], start=FULL_DETAIL_COUNT + 1):
        # IMPORTANT: Use wrap_card_name_with_hover to preserve image preview on hover
        card_name_with_hover = wrap_card_name_with_hover(card.name, card)
        mana_symbols = format_mana_symbols(card.mana_cost)
        formatted_text += f"{i}. {card_name_with_hover} {mana_symbols} - {card.type_line}\n"

    formatted_text += "\n_Use filters or pagination to see more details._\n"
```

**Benefits**:
- Reduces token usage for large result sets by ~70%
- Maintains full functionality (pagination for details)
- Preserves important context in conversation history
- User can still see all results, just with less detail
- **Card image hover preserved**: Compact entries include full hover functionality
- Users can preview card images for ALL results (not just first 10)
- Consistent UX between full and compact display formats

**Impact Example**:
- Old: 104 cards × ~200 tokens = 20,800 tokens
- New: 10 cards × ~200 tokens + 94 cards × ~30 tokens = 4,820 tokens
- Savings: ~16,000 tokens (~77% reduction)

## Testing Strategy

### Unit Tests

1. **Test System Message Injection**:
   - `test_build_deck_context_message` - Verify message format
   - `test_inject_system_context_with_existing_system_msg` - Prepend to existing
   - `test_inject_system_context_without_system_msg` - Create new message
   - `test_no_injection_when_no_active_deck` - Verify conditional logic

2. **Test Abbreviated Results**:
   - `test_search_results_full_detail_under_threshold` - ≤10 cards show full details
   - `test_search_results_abbreviated_over_threshold` - >10 cards use compact view
   - `test_abbreviated_results_preserve_card_data` - All cards still in response

### Integration Tests

1. **Test Context Retention Scenario** (reproduces bug):
   ```python
   async def test_deck_context_retention_with_large_search(session_id):
       """
       Reproduce the exact bug scenario:
       1. Create deck "Fire Lord Zuko Deck"
       2. Search for red instants (104 results - large context)
       3. Add Boros Charm
       4. Verify card added to ORIGINAL deck, not new deck
       """
       # Create deck
       result1 = await agent.run("create a deck called Fire Lord Zuko Deck", deps=deps1)
       assert "Fire Lord Zuko Deck" in result1

       # Large search
       result2 = await agent.run("search for red instants", deps=deps2)
       assert "Found 104 cards" in result2

       # Add card - should NOT create new deck
       result3 = await agent.run("add 2 boros charm", deps=deps3)

       # Verify NO new deck created
       all_decks = await deck_repo.list_decks()
       assert len(all_decks) == 1, "Should still have only 1 deck"
       assert all_decks[0].name == "Fire Lord Zuko Deck"

       # Verify card added to original deck
       deck = await deck_repo.get_deck_with_cards(all_decks[0].id)
       assert any(c.card.name == "Boros Charm" for c in deck.deck_cards)
   ```

2. **Test Tool-First Approach**:
   ```python
   async def test_tool_first_deck_operations():
       """Verify agent calls add_card_to_deck before creating deck."""
       # Mock agent to track tool calls
       tool_calls = []

       result = await agent.run("add Lightning Bolt", deps=deps)

       # First tool call should be add_card_to_deck (even if it fails)
       assert tool_calls[0]["name"] == "add_card_to_deck"

       # create_deck should only be called if add_card fails
       if "No active deck" in tool_calls[0]["result"]:
           assert tool_calls[1]["name"] == "create_deck"
   ```

### Manual Testing Checklist

- [ ] Create deck, do large search (50+ cards), add card → Card goes to correct deck
- [ ] Multiple sequential card additions → All go to same deck
- [ ] User explicitly says "create new deck" → New deck created correctly
- [ ] No active deck, add card → Agent asks to create deck or errors appropriately
- [ ] Deck creation with similar names → Agent suggests unique name or confirms intent

## Rollout Plan

### Phase 1: System Message Injection (Days 1-2)
- Implement `_build_deck_context_message` and `_inject_system_context`
- Add unit tests
- Deploy to development environment
- Manual validation with reproduction scenario

### Phase 2: Tool-First System Prompt (Day 3)
- Update agent system prompt with new rules
- Add integration test for tool-first behavior
- Validate agent follows new constraints

### Phase 3: Abbreviated Search Results (Days 4-5)
- Modify `search_cards_advanced` formatting
- Add unit tests for formatting
- Validate UI rendering of abbreviated results
- User acceptance testing

### Phase 4: Integration Testing (Day 6)
- Run full integration test suite
- Reproduce original bug scenario and verify fix
- Performance testing (context window usage)
- User acceptance testing with beta testers

### Phase 5: Documentation & Release (Day 7)
- Update CLAUDE.md with new agent behavior
- Document abbreviated search results in UI guide
- Release notes highlighting fix
- Archive OpenSpec change

## Monitoring & Validation

**Success Metrics**:
1. Zero duplicate deck creation incidents (track via bug reports)
2. 70% reduction in search result token usage (track via logging)
3. Active deck state injection in 100% of relevant agent runs (logging)
4. User satisfaction survey: "Deck management is intuitive" > 4.5/5

**Monitoring**:
- Log deck creation events with stack trace to detect inappropriate creation
- Track conversation history token usage before/after change
- Monitor tool call sequences (should see add_card_to_deck before create_deck)
- Alert on multiple decks with similar names created in same session

## Future Enhancements (Out of Scope)

1. **Smart Message Pruning** (separate change):
   - Preserve deck operation messages in history
   - Prune large search results more aggressively
   - Increase message limit to 15 for deck-building sessions

2. **Deck Name Validation**:
   - Warn user if creating deck with similar name to existing deck
   - Suggest unique names or confirm intent

3. **Multi-Deck Session Support**:
   - Allow user to explicitly switch between multiple active decks
   - "Switch to deck X" command
   - Session manager tracks deck stack/history

4. **Context Window Optimization**:
   - Implement token-based pruning (not just message count)
   - Summarize old messages with LLM
   - Selective message retention based on importance scoring
