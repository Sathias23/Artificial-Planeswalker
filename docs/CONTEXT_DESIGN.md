# Context Engineering Design

This document provides a deep dive into the context management architecture of Artificial-Planeswalker, explaining how information flows through the agent system across conversation turns.

## Overview

The context management system uses **three parallel state machines** to maintain conversation history, session preferences, and ephemeral tool execution state. This architecture enables persistent conversations while preventing unbounded context growth.

## What Information Is Passed on Each Turn?

Every agent invocation receives a **composite context bundle** consisting of:

### 1. System Prompt (Static)

Defined in `src/agent/core.py:250-271`

- Role definition, capabilities, behavioral guidelines
- **CRITICAL**: HTML formatting preservation instruction for visual mana symbols
- Always present (preserved even during history truncation)

```python
SYSTEM_PROMPT = """You are Artificial-Planeswalker, an expert Magic: The Gathering \
deck building assistant.

IMPORTANT: When presenting card information from tools, you MUST preserve ALL HTML \
formatting exactly as provided...
"""
```

### 2. Message History (Dynamic)

Retrieved from `ConversationSessionManager._sessions[session_id]`

Contains `list[ModelMessage]` from PydanticAI with message types:
- `ModelRequest` with `UserPromptPart` (user messages)
- `ModelRequest` with `SystemPromptPart` (system messages)
- `ModelResponse` (agent responses)
- Tool calls (`ToolCallPart`) and returns (`ToolReturnPart`)

**Key**: Tool call/return pairs are NEVER separated (PydanticAI maintains integrity)

### 3. Current User Input (Fresh)

The new message from `on_message(message)` in `src/ui/app.py:369`, appended to history before agent invocation.

### 4. AgentDependencies (Session-Aware State)

Created fresh per request via `get_agent_dependencies()` context manager (`src/ui/app.py:247`)

Contains:
- **Repositories**: `CardRepository`, `DeckRepository` (new DB session each turn)
- **Session State** (restored from `ConversationSessionManager`):
  - `format_filter: FormatFilter` - Current format restriction (e.g., "standard")
  - `active_deck_id` (property) - UUID of loaded deck
  - `session_id: str` - Session identifier
- **Collection Buckets** (empty at start of turn):
  - `ui_elements: list[Any]` - For card images, etc.
  - `sidebar_needs_update: bool` - Trigger flag for UI refresh

## How Information Changes Over Turns

There are **three parallel state machines** managing different aspects of context:

### State Machine 1: Message History

**Location**: `src/agent/core.py:95-233`

```
Turn N: [system, user1, agent1, tool1_call, tool1_return, agent1_final]
         ↓ (agent runs with this history)
Turn N+1: [system, user1, agent1, tool1_call, tool1_return, agent1_final, user2, agent2, ...]
```

**Flow**:

1. `run_agent_with_session()` retrieves history: `_session_manager.get_history(session_id)` (line 458)
2. Agent runs: `agent.run(user_input, deps=deps, message_history=history)` (line 461)
3. Result extracted: `all_messages = result.all_messages()` (line 464)
4. History updated: `_session_manager.update_history(session_id, all_messages)` (line 467)

**CRITICAL**: History is **append-only** until truncation kicks in!

### State Machine 2: Session State

**Location**: `src/agent/core.py:162-232`

Separate dictionaries in `ConversationSessionManager`:
- `_format_filters: dict[str, FormatFilter]` - Persists format preference
- `_active_deck_ids: dict[str, str]` - Persists active deck UUID

**Flow Example**:

```
Turn 1: User says "only show standard cards"
  → Tool calls set_format_filter()
  → _session_manager.set_format_filter(session_id, "standard")

Turn 2: User asks "find a red creature"
  → get_agent_dependencies() restores format_filter="standard" (line 269)
  → Tool lookup_card_by_name() uses ctx.deps.format_filter
  → Query automatically filters to Standard-legal cards!
```

**Key Insight**: Session state is **restored at start of each turn** into `AgentDependencies`, then tools read from it. Tools can also **write back** to session manager (e.g., `load_deck()` sets active deck ID).

### State Machine 3: Tool Execution Context (Per-Turn Ephemeral)

`AgentDependencies` fields reset each turn:
- `ui_elements: list[Any]` - Starts empty, tools append during execution
- `sidebar_needs_update: bool` - Starts False, tools set to True

**Flow**:

```python
# src/ui/app.py:394-475
async with get_agent_dependencies(session_id) as deps:  # Fresh deps
    result = await run_agent_with_session(...)

    # Tool executions populate deps.ui_elements during agent.run()
    # Example: lookup_card_by_name() appends card images (src/agent/tools/card_lookup.py:88)

    if deps.ui_elements:  # Collect UI artifacts
        response_message.elements = deps.ui_elements

    if deps.sidebar_needs_update:  # Check trigger flag
        await update_deck_sidebar(session_id)
```

**Design Rationale**: Separates **persistent state** (message history, format filter) from **transient artifacts** (UI elements, update flags).

## What Happens When Context Gets Too Big?

Multi-layer defense strategy to prevent context overflow:

### Layer 1: Message History Truncation

**Location**: `src/agent/core.py:274-312`

```python
def keep_recent_messages(messages: list[ModelMessage]) -> list[ModelMessage]:
```

**Strategy**:

1. **Threshold**: 10 messages (≈5 user-agent exchanges)
2. **Token budget**: ~2,000-10,000 tokens (well under 200k window for Claude Sonnet 4.5)
3. **Algorithm**:
   - Separate system messages from user/agent messages
   - Keep ALL system messages (agent personality must remain consistent)
   - Keep LAST 10 non-system messages
   - Merge: `[system_messages] + recent_messages[-10:]`

**Registered** as history processor at agent creation:

```python
# src/agent/core.py:376
agent: Agent[AgentDependencies, str] = Agent(
    ...,
    history_processors=[keep_recent_messages],  # Automatic truncation!
)
```

**CRITICAL INSIGHT**: PydanticAI **automatically** maintains tool call/return pairing during truncation. If a tool call is kept, its return is ALWAYS kept too (prevents context corruption).

### Layer 2: Selective History Scope

**Location**: `src/ui/app.py:406`

```python
current_turn_messages = result.new_messages()  # NOT all_messages()!
tool_calls = extract_tool_calls(current_turn_messages)
```

**Why**: Tool step display in UI only shows **current turn**, preventing clutter from historical tool calls. The agent still sees full (truncated) history, but UI presentation is scoped.

### Layer 3: Format Filter Efficiency

Session state pattern **avoids context pollution**:

- Instead of "remember I said standard only" in every message → 1-2k tokens/turn
- Format preference stored in `_format_filters` dict → 0 tokens overhead!
- Tools read `ctx.deps.format_filter` directly from session state

Same for `active_deck_id` - no need to repeat "I'm working on deck XYZ" every turn.

### Layer 4: Database Session Lifecycle

**Location**: `src/ui/app.py:271-302`

```python
async with _session_factory() as session:
    try:
        if session.in_transaction():  # Safety check!
            await session.rollback()  # Clear contamination

        yield AgentDependencies(...)  # Fresh repos each turn

    except Exception:
        await session.rollback()  # Cleanup on error
```

**Why**: Prevents **state leakage** between turns. Each turn gets:
- Fresh DB session (no lingering locks/transactions)
- Fresh repository instances
- Clean error recovery

## Emergent Properties

This architecture creates some **non-obvious behaviors**:

### 1. Intra-Turn State Propagation

Multiple tools in same agent run can communicate via session manager:

```python
# Tool 1 (create_deck) runs:
deck_id = await ctx.deps.deck_repository.create_deck(...)
ctx.deps._session_manager.set_active_deck_id(ctx.deps.session_id, deck_id)

# Tool 2 (add_card_to_deck) in SAME run reads:
active_id = ctx.deps.active_deck_id  # Property reads from session manager!
```

This is why `active_deck_id` is a **property** (`src/agent/dependencies.py:89-111`) - ensures real-time reads from session manager, not stale values.

### 2. Graceful Degradation on Context Limits

If history grows beyond 10 messages:
- Older user requests forgotten → Agent can't reference them
- BUT: Session state (format filter, active deck) PERSISTS!
- User doesn't need to "remind" the agent of their preferences

### 3. Token Usage is Sub-Linear

- Without truncation: O(n²) token growth (each turn adds to history)
- With truncation: O(1) token usage (~constant after 10 messages)
- Session state: O(1) memory (dict lookups, no tokens)

## Potential Issues

**What could go wrong?**

1. **Context Window Exceeded Despite Truncation**:
   - If EACH message is huge (e.g., user pastes 50k-char document)
   - Mitigation: 10-message limit assumes ~2k tokens/message average

2. **Session Manager is In-Memory**:
   - Server restart → All session state lost (format filters, active decks)
   - Mitigation: Could persist to SQLite in future

3. **Tool Call/Return Pairing Edge Case**:
   - If truncation happens MID-execution (not currently possible)
   - PydanticAI protects against this by design

4. **Sidebar Update Race Condition**:
   - `deps.sidebar_needs_update` flag could miss updates if exception mid-turn
   - Mitigation: Flag check happens in UI layer after agent completes (line 470)

## Information Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Turn N                                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  restore   ┌─────────────────────────┐  │
│  │   Session    │────────────→│  AgentDependencies     │  │
│  │   Manager    │ format_filter│  (fresh each turn)    │  │
│  │              │ active_deck │                         │  │
│  └──────────────┘             └─────────────────────────┘  │
│         ↑                                ↓                  │
│         │ update                    read/write              │
│         │ history                        ↓                  │
│  ┌──────────────┐   history    ┌─────────────────────────┐│
│  │   Message    │─────────────→│      PydanticAI        ││
│  │   History    │              │        Agent           ││
│  │ (last 10)    │←─────────────│  (with tools)          ││
│  └──────────────┘  append new  └─────────────────────────┘│
│                                            ↓                │
│                                   ┌─────────────────────┐  │
│                                   │   Tool Execution    │  │
│                                   │  - Reads format     │  │
│                                   │  - Queries DB       │  │
│                                   │  - Appends UI elems │  │
│                                   └─────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Insight

**The Genius Move**: Separating message history (LLM context) from session state (application state) while making both **transparent** to the UI layer. The UI just calls `run_agent_with_session()` and everything "just works"!

This separation enables:
- **Conversation continuity** (LLM remembers recent exchanges)
- **Preference persistence** (format filter, active deck survive history truncation)
- **Clean boundaries** (UI layer never touches session manager directly)
- **Predictable scaling** (constant token usage after initial turns)

## Code References

Key files for context management:

- `src/agent/core.py` - `ConversationSessionManager`, `keep_recent_messages()`, `run_agent_with_session()`
- `src/agent/dependencies.py` - `AgentDependencies` dataclass with session state
- `src/ui/app.py` - `get_agent_dependencies()`, `on_message()` handler
- `src/agent/tools/` - Individual tools reading/writing session state via `ctx.deps`
