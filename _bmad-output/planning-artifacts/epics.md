# Artificial-Planeswalker - Epic Breakdown (Letta Migration)

---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - prd.md
  - architecture.md
  - research/technical-letta-framework-research-2026-01-04.md
workflowType: 'create-epics-and-stories'
project_name: 'Artificial-Planeswalker'
user_name: 'Brad'
date: '2026-01-04'
status: 'complete'
completedAt: '2026-01-04'
---

**Author:** Winston (Architect Agent)
**Date:** 2026-01-04
**Project Level:** MVP Migration
**Target Scale:** Single-user local application
**Migration:** PydanticAI → Letta Framework

---

## Overview

This document provides the complete epic and story breakdown for Artificial-Planeswalker's migration from PydanticAI to the Letta framework. It decomposes requirements from the [PRD](./prd.md) and [Architecture](./architecture.md) into implementable stories.

**Technology Pivot Context:** This is a framework migration, not a greenfield project. Epics 1-4 from the original PydanticAI implementation are COMPLETE. This epic breakdown focuses on the Letta migration work.

### Epic Summary

| Epic | Title | User Value | Stories |
|------|-------|------------|---------|
| L1 | Letta Agent Infrastructure | Foundation for stateful AI assistant | 4 |
| L2 | Card Data Migration | 60k searchable cards via semantic search | 4 |
| L3 | Chainlit Letta Integration | Working chat interface with new agent | 4 |
| L4 | Deck Management Tools | Full deck CRUD via Letta tools | 5 |
| L5 | Deck Intelligence Tools | Mana curve and synergy analysis | 4 |
| L6 | Migration Cleanup | Clean codebase, archived legacy code | 3 |

**Total Stories:** 24

---

## Functional Requirements Inventory

| FR ID | Description | Letta Implementation |
|-------|-------------|---------------------|
| FR1 | Download and store Scryfall bulk data locally | Letta archival memory (semantic search) |
| FR2 | Natural language card lookup | Letta tools with archival_memory_search |
| FR3 | Card queries filtered by Standard format | Core memory block `format_filter` |
| FR4 | Deck creation and management | Letta tools + SQLite DeckRepository |
| FR5 | Deck construction rule validation | Logic layer (preserved) |
| FR6 | Mana curve distribution analysis | Logic layer (preserved) + Letta tools |
| FR7 | Card synergy identification | Logic layer (preserved) + Letta tools |
| FR8 | Deck persistence with CRUD operations | SQLite DeckRepository (preserved) |
| FR9 | Chainlit chat interface | Letta SDK integration |
| FR10 | UI/agent layer separation | REST API boundary (Chainlit → Letta) |

---

## Non-Functional Requirements Inventory

| NFR ID | Description | Letta Approach |
|--------|-------------|----------------|
| NFR1 | Offline-first card queries | Archival memory is local vector DB |
| NFR2 | Type safety with Pydantic | Tools return strings, schemas in data layer |
| NFR3 | Agent testable without UI | Pure Python tools, mock Letta client |
| NFR4 | Bulk data updates refreshable | Re-run archival import script |
| NFR5 | Future format support | Core memory block extensible |
| NFR6 | UI replacement support | Letta REST API is UI-agnostic |
| NFR7 | <500ms query performance | Validate semantic search latency |

---

## Additional Requirements from Technology Pivot

| Requirement | Source | Epic |
|-------------|--------|------|
| Letta server setup and configuration | Architecture | L1 |
| Core memory blocks: persona, human, active_deck, format_filter | Architecture | L1 |
| Card import to archival memory (~$0.60 embedding cost) | Architecture | L2 |
| Step streaming for real-time responses | Architecture | L3 |
| Environment path pattern for tool database access | Architecture | L4 |
| Google-style docstrings for all Letta tools | Architecture | L4, L5 |
| `[MEMORY UPDATE: block]` pattern for state changes | Architecture | L4 |
| Archive PydanticAI code after successful migration | Architecture | L6 |

---

## FR Coverage Map

| FR | Epic L1 | Epic L2 | Epic L3 | Epic L4 | Epic L5 | Epic L6 |
|----|---------|---------|---------|---------|---------|---------|
| FR1 | - | L2.1, L2.2 | - | - | - | - |
| FR2 | - | L2.3, L2.4 | - | - | - | - |
| FR3 | L1.3 | L2.4 | - | - | - | - |
| FR4 | - | - | - | L4.2, L4.3 | - | - |
| FR5 | - | - | - | L4.4 | - | - |
| FR6 | - | - | - | - | L5.1, L5.2 | - |
| FR7 | - | - | - | - | L5.3, L5.4 | - |
| FR8 | - | - | - | L4.1, L4.5 | - | - |
| FR9 | - | - | L3.1, L3.2 | - | - | - |
| FR10 | L1.1 | - | L3.2, L3.3 | - | - | L6.1 |

---

## Epic Structure Plan

### Design Principles Applied

1. **Migration Safety**: Each epic independently verifiable before proceeding
2. **Parallel Capability**: Existing PydanticAI code remains functional until L6
3. **Incremental Delivery**: Each story delivers testable functionality
4. **Architecture Alignment**: Stories directly map to architecture decisions

### Epic Dependency Graph

```
Epic L1: Letta Agent Infrastructure
    │
    ▼
Epic L2: Card Data Migration ◄── Cards need agent with archival memory
    │
    ▼
Epic L3: Chainlit Integration ◄── UI needs agent to communicate with
    │
    ▼
Epic L4: Deck Management Tools ◄── Tools need integration working
    │
    ▼
Epic L5: Deck Intelligence Tools ◄── Analysis needs deck tools
    │
    ▼
Epic L6: Migration Cleanup ◄── Cleanup after all features ported
```

### Technical Context Summary

| Epic | Architecture Components | Key Deliverables |
|------|------------------------|------------------|
| L1 | Letta server, agent, memory blocks | Working Letta agent with persona |
| L2 | Archival memory, card import | Searchable card database |
| L3 | Letta SDK, step streaming | Chat interface with agent |
| L4 | Letta tools, SQLite access | Deck CRUD operations |
| L5 | Logic layer integration | Curve and synergy analysis |
| L6 | Code archival | Clean codebase |

---

## Epic L1: Letta Agent Infrastructure

**Epic Goal:** Establish the Letta framework foundation including server setup, base agent creation, and core memory block definitions.

**User Value:** Foundation enabling stateful AI assistant that remembers context across sessions.

**FRs Addressed:** FR10 (architecture separation)

**Technical Context:**
- Letta server on port 8283
- pip installation with SQLite backend
- Core memory blocks define agent context
- Agent persists across user sessions

---

### Story L1.1: Letta Server Setup and Dependencies

As a **developer**,
I want **Letta framework installed and server running locally**,
So that **I can create and interact with Letta agents**.

**Acceptance Criteria:**

**Given** the existing project structure
**When** I set up Letta
**Then** the following is configured:

- [ ] Dependencies added to `pyproject.toml`:
  - `letta>=0.6.0`
  - `letta-client>=0.1.0`
- [ ] Letta server starts successfully:
  ```bash
  letta server --port 8283 --data-dir ./data/letta
  ```
- [ ] Server health check passes: `GET http://localhost:8283/v1/health`
- [ ] `.env` updated with:
  - `LETTA_BASE_URL=http://localhost:8283`
  - `OPENAI_API_KEY=...` (for embeddings)
- [ ] Data directory created: `./data/letta/`
- [ ] Development workflow documented in README

**Technical Notes:**
- Architecture: pip installation with SQLite (development mode)
- Two terminals needed: Letta server + Chainlit app
- Server persists agent state in `./data/letta/`

**Prerequisites:** None (first story)

---

### Story L1.2: Letta Client Wrapper Module

As a **developer**,
I want **a client wrapper for the Letta SDK**,
So that **I have a consistent interface for agent operations throughout the codebase**.

**Acceptance Criteria:**

**Given** a running Letta server
**When** I use the client wrapper
**Then** the following works:

- [ ] Client module at `src/letta/client.py`:
  ```python
  from letta_client import Letta

  def get_letta_client() -> Letta:
      """Get configured Letta client instance."""
  ```
- [ ] Client reads `LETTA_BASE_URL` from environment
- [ ] Connection error handling with helpful messages
- [ ] Retry logic for transient failures (3 attempts)
- [ ] Unit tests verify client initialization
- [ ] Integration test verifies server connectivity

**Technical Notes:**
- Architecture: REST API on port 8283
- Use `letta-client` SDK for type-safe operations
- Client is stateless; agent state is in server

**Prerequisites:** Story L1.1

---

### Story L1.3: Base Agent Creation with Memory Blocks

As a **developer**,
I want **a Letta agent created with properly configured core memory blocks**,
So that **the agent has persistent context for MTG deck building**.

**Acceptance Criteria:**

**Given** a running Letta server and client
**When** I create the base agent
**Then** the following is configured:

- [ ] Agent creation module at `src/letta/agent.py`:
  ```python
  async def create_mtg_agent(client: Letta) -> Agent:
      """Create MTG deck-building agent with memory blocks."""
  ```
- [ ] Core memory blocks defined per Architecture:
  - `persona` (2000 chars): MTG deck-building expert identity
  - `human` (2000 chars): User preferences placeholder
  - `active_deck` (5000 chars): Current deck summary
  - `format_filter` (500 chars): Current format/games filter
- [ ] Memory block module at `src/letta/memory.py`:
  ```python
  PERSONA_BLOCK = """You are an expert Magic: The Gathering deck-building assistant..."""
  ```
- [ ] Agent creation script at `scripts/create_letta_agent.py`
- [ ] Script outputs agent_id for configuration
- [ ] Unit tests verify memory block structure
- [ ] Integration test verifies agent creation

**Technical Notes:**
- Architecture: persona block sets agent behavior
- Core memory always in LLM context window
- Agent persists across server restarts

**Prerequisites:** Story L1.2

---

### Story L1.4: Agent Retrieval and Session Management

As a **developer**,
I want **to retrieve existing agents by ID or create new ones**,
So that **users can have persistent agents across sessions**.

**Acceptance Criteria:**

**Given** an existing Letta agent
**When** I need to use it
**Then** the following works:

- [ ] Agent retrieval function in `src/letta/agent.py`:
  ```python
  async def get_or_create_agent(client: Letta, agent_id: str | None = None) -> Agent:
      """Get existing agent or create new one if not found."""
  ```
- [ ] Agent ID stored in configuration (single-user MVP)
- [ ] `.env` updated: `LETTA_AGENT_ID=<uuid>`
- [ ] Graceful handling if agent not found (recreate)
- [ ] Tool execution environment configured:
  - `APP_DATABASE_PATH` for SQLite access
  - `LETTA_AGENT_ID` for self-reference
- [ ] Unit tests verify get-or-create logic
- [ ] Integration test verifies agent persistence

**Technical Notes:**
- Architecture: One agent per user (MVP)
- Agent ID stored in Chainlit session in Epic L3
- Tool environment enables database access

**Prerequisites:** Story L1.3

---

### Epic L1 Summary

| Story | Title | Key Deliverables |
|-------|-------|------------------|
| L1.1 | Server Setup | Letta running, dependencies installed |
| L1.2 | Client Wrapper | Reusable Letta SDK interface |
| L1.3 | Base Agent | Agent with 4 core memory blocks |
| L1.4 | Session Management | Get-or-create pattern for agents |

**Epic L1 Complete Criteria:**
- Letta server running on port 8283
- Agent created with all memory blocks
- Agent persists across server restarts
- Client wrapper tested and working
- Ready to proceed to Epic L2

---

## Epic L2: Card Data Migration

**Epic Goal:** Import Scryfall card data into Letta archival memory and implement card search tools.

**User Value:** Users can search 60,000+ MTG cards using natural language with semantic similarity.

**FRs Addressed:** FR1, FR2, FR3

**Technical Context:**
- Archival memory with vector embeddings
- OpenAI text-embedding-3-small model
- One-time import cost ~$0.60
- File upload strategy for bulk import

---

### Story L2.1: Card Data Export for Letta Import

As a **developer**,
I want **Scryfall card data exported in Letta-optimized format**,
So that **cards can be imported to archival memory with good search quality**.

**Acceptance Criteria:**

**Given** existing Scryfall bulk data
**When** I export for Letta
**Then** the following is produced:

- [ ] Export script at `scripts/export_cards_for_letta.py`
- [ ] Each card formatted per Architecture pattern:
  ```
  Card: Lightning Bolt
  Mana Cost: {R}
  Type: Instant
  Oracle Text: Lightning Bolt deals 3 damage to any target.
  Colors: R
  CMC: 1
  Keywords:
  Rarity: common
  Format: Standard=not_legal, Modern=legal, Legacy=legal
  ```
- [ ] Output file: `data/cards_for_letta.jsonl`
- [ ] One JSON object per line with `text` field
- [ ] All ~60,000 cards exported
- [ ] Export completes in < 5 minutes
- [ ] Unit tests verify format structure

**Technical Notes:**
- Text format optimized for embedding similarity
- Include all searchable fields
- Legalities as key=value for filtering

**Prerequisites:** Epic L1 complete

---

### Story L2.2: Archival Memory Card Import

As a **developer**,
I want **card data imported into Letta archival memory**,
So that **the agent can search cards semantically**.

**Acceptance Criteria:**

**Given** exported card data file
**When** I import to Letta
**Then** the following happens:

- [ ] Import script at `scripts/import_cards_to_letta.py`
- [ ] Script creates data source via Letta API
- [ ] File uploaded and processed asynchronously
- [ ] Progress tracking with estimated completion time
- [ ] Import completes successfully (~60k cards)
- [ ] Data source attached to agent
- [ ] Embedding cost logged (~$0.60 expected)
- [ ] Script runnable: `uv run scripts/import_cards_to_letta.py`

**Technical Notes:**
- Architecture: File upload for bulk import
- Letta handles chunking and embedding
- Same embedding model for agent and data source

**Prerequisites:** Story L2.1

---

### Story L2.3: Card Search Tool Implementation

As a **user**,
I want **to search for cards using natural language**,
So that **I can find cards for my deck without knowing exact names**.

**Acceptance Criteria:**

**Given** cards imported to archival memory
**When** I search for cards
**Then** the agent finds relevant matches:

- [ ] Tool at `src/letta/tools/card_tools.py`:
  ```python
  def search_cards(query: str, limit: int = 10) -> str:
      """
      Search for Magic: The Gathering cards.

      Args:
          query (str): Natural language search query
          limit (int): Maximum results to return

      Returns:
          str: Formatted list of matching cards
      """
  ```
- [ ] Tool uses `archival_memory_search` internally
- [ ] Results formatted with name, mana cost, type, text
- [ ] Semantic similarity finds related cards:
  - "red burn spells" → Lightning Bolt, Shock, etc.
  - "flying creatures" → cards with flying keyword
- [ ] No results handled gracefully
- [ ] Unit tests with mock archival memory
- [ ] Integration test verifies search quality

**Technical Notes:**
- Archival search returns similar text entries
- Tool parses card format back to fields
- Return user-friendly formatted string

**Prerequisites:** Story L2.2

---

### Story L2.4: Format Filter Integration

As a **user**,
I want **card searches filtered by format legality**,
So that **I only see cards I can use in my deck**.

**Acceptance Criteria:**

**Given** format filter set in core memory
**When** I search for cards
**Then** only legal cards returned:

- [ ] Filter tool at `src/letta/tools/filter_tools.py`:
  ```python
  def set_format_filter(format: str | None, games: list[str] | None = None) -> str:
      """
      Set format and platform filter for card searches.

      Args:
          format (str | None): Format name (standard, modern, etc.) or None
          games (list[str] | None): Platforms (arena, paper, mtgo) or None

      Returns:
          str: Confirmation of filter settings
      """
  ```
- [ ] Tool updates `format_filter` core memory block
- [ ] Card search tool reads filter from context
- [ ] Search results filtered by legality field
- [ ] "standard" filters to Standard-legal only
- [ ] `None` shows all cards
- [ ] Memory update pattern used:
  ```
  [MEMORY UPDATE: format_filter]
  Format: standard
  Games: arena
  ```
- [ ] Integration test verifies filtering works

**Technical Notes:**
- Architecture: Core memory block for filter state
- Agent has filter context in every interaction
- Games filter for platform availability

**Prerequisites:** Story L2.3

---

### Epic L2 Summary

| Story | Title | Key Deliverables |
|-------|-------|------------------|
| L2.1 | Card Export | JSONL file with 60k cards |
| L2.2 | Archival Import | Cards searchable in Letta |
| L2.3 | Search Tool | Natural language card search |
| L2.4 | Format Filter | Standard/Modern/etc. filtering |

**Epic L2 Complete Criteria:**
- All cards imported to archival memory
- `search_cards` tool returns relevant results
- Format filtering works via core memory
- Ready to proceed to Epic L3

---

## Epic L3: Chainlit Letta Integration

**Epic Goal:** Update the Chainlit UI to communicate with Letta agent via REST API with step streaming.

**User Value:** Users interact with the new Letta-powered agent through familiar chat interface.

**FRs Addressed:** FR9, FR10

**Technical Context:**
- Letta SDK for API calls
- Step streaming for real-time responses
- Session maps to Letta agent_id
- Thin UI layer (no business logic)

---

### Story L3.1: Chainlit Session to Letta Agent Mapping

As a **developer**,
I want **Chainlit sessions mapped to Letta agents**,
So that **users have persistent agents across chat sessions**.

**Acceptance Criteria:**

**Given** the Chainlit application
**When** a user starts a chat
**Then** they connect to a Letta agent:

- [ ] Updated `src/ui/app.py`:
  ```python
  AGENT_ID_KEY = "letta_agent_id"

  @cl.on_chat_start
  async def on_chat_start():
      agent_id = cl.user_session.get(AGENT_ID_KEY)
      if not agent_id:
          agent = await get_or_create_agent(letta_client)
          cl.user_session.set(AGENT_ID_KEY, agent.id)
  ```
- [ ] Agent ID persisted in Chainlit session
- [ ] Welcome message displays on start
- [ ] Letta client initialized at app startup
- [ ] Error handling for Letta connection failures
- [ ] Unit tests with mock Letta client

**Technical Notes:**
- Architecture: One agent per user (MVP)
- Agent ID stored in Chainlit user session
- Lazy agent creation on first message

**Prerequisites:** Epic L1 and L2 complete

---

### Story L3.2: Step Streaming Message Handler

As a **user**,
I want **to see agent responses stream in real-time**,
So that **I get immediate feedback as the agent thinks**.

**Acceptance Criteria:**

**Given** a connected Letta agent
**When** I send a message
**Then** I see streaming response:

- [ ] Message handler at `src/ui/handlers/message_handler.py`:
  ```python
  async def handle_message(message: str, agent_id: str) -> None:
      async for chunk in client.agents.messages.stream(agent_id, messages):
          if chunk.message_type == "assistant_message":
              await cl_message.stream_token(chunk.content)
  ```
- [ ] Step streaming per Architecture pattern
- [ ] Complete LettaMessage objects received
- [ ] Tool execution steps visible (optional debug mode)
- [ ] Response completes and displays fully
- [ ] Error messages shown for failures
- [ ] Integration test verifies streaming works

**Technical Notes:**
- Architecture: Step streaming (Letta default)
- No client-side token accumulation
- Steps: reasoning → tool execution → response

**Prerequisites:** Story L3.1

---

### Story L3.3: Tool Step Display

As a **user**,
I want **to see when the agent uses tools**,
So that **I understand what the agent is doing**.

**Acceptance Criteria:**

**Given** agent executing tools
**When** I watch the response
**Then** I see tool activity:

- [ ] Tool calls displayed as Chainlit Steps
- [ ] Step shows tool name and brief input
- [ ] Step collapses after completion
- [ ] Tool results integrated into response
- [ ] Multiple tools show in sequence
- [ ] Error states displayed if tool fails
- [ ] Manual testing confirms UX is clear

**Technical Notes:**
- Use existing `src/ui/tool_steps.py` pattern
- Adapt for Letta message format
- Keep tool display optional/collapsible

**Prerequisites:** Story L3.2

---

### Story L3.4: Error Handling and Reconnection

As a **user**,
I want **graceful error handling when things go wrong**,
So that **I can continue working without confusion**.

**Acceptance Criteria:**

**Given** possible Letta failures
**When** errors occur
**Then** user sees helpful messages:

- [ ] Connection errors: "Connecting to AI assistant..."
- [ ] Timeout errors: "Response taking longer than expected"
- [ ] Tool failures: Error message from tool (not stack trace)
- [ ] Server restart: Automatic reconnection attempt
- [ ] Agent not found: Recreate agent transparently
- [ ] Rate limits: Backoff and retry
- [ ] All error paths tested

**Technical Notes:**
- Wrap all Letta calls in try/except
- User never sees technical error details
- Log full errors for debugging

**Prerequisites:** Stories L3.1-L3.3

---

### Epic L3 Summary

| Story | Title | Key Deliverables |
|-------|-------|------------------|
| L3.1 | Session Mapping | Chainlit → Letta agent connection |
| L3.2 | Step Streaming | Real-time response display |
| L3.3 | Tool Display | Visible tool execution steps |
| L3.4 | Error Handling | Graceful failure recovery |

**Epic L3 Complete Criteria:**
- Chat interface connects to Letta agent
- Messages stream in real-time
- Tool usage visible to user
- Errors handled gracefully
- Ready to proceed to Epic L4

---

## Epic L4: Deck Management Tools

**Epic Goal:** Port all deck CRUD operations to Letta tool format with proper memory updates.

**User Value:** Users can create, edit, and manage decks through natural language.

**FRs Addressed:** FR4, FR5, FR8

**Technical Context:**
- SQLite access via environment path pattern
- Sync database connections in tools
- Memory update pattern for active_deck block
- Google-style docstrings for schema

---

### Story L4.1: Deck Repository Access Pattern

As a **developer**,
I want **Letta tools to access SQLite deck database**,
So that **deck operations work with existing data layer**.

**Acceptance Criteria:**

**Given** the SQLite deck database
**When** a tool needs deck data
**Then** access works correctly:

- [ ] Environment variable: `APP_DATABASE_PATH=data/decks.db`
- [ ] Database helper in `src/letta/tools/_db.py`:
  ```python
  def get_db_connection():
      """Get sync SQLite connection for tool use."""
      import os
      import sqlite3
      db_path = os.environ.get("APP_DATABASE_PATH", "data/decks.db")
      return sqlite3.connect(db_path)
  ```
- [ ] All deck tools use this pattern
- [ ] Connection closed after each operation
- [ ] Error handling for DB failures
- [ ] Unit tests with test database

**Technical Notes:**
- Architecture: Environment path pattern
- Sync connections (Letta tools are sync)
- Keep tool logic minimal, delegate to helper

**Prerequisites:** Epic L3 complete

---

### Story L4.2: Create Deck Tool

As a **user**,
I want **to create a new deck through conversation**,
So that **I can start building a deck with a name**.

**Acceptance Criteria:**

**Given** no active deck
**When** I say "create a deck called Mono Red"
**Then** deck is created and active:

- [ ] Tool at `src/letta/tools/deck_tools.py`:
  ```python
  def create_deck(name: str, format: str = "standard") -> str:
      """
      Create a new deck and set it as active.

      Args:
          name (str): Name for the new deck
          format (str): Deck format (standard, modern, etc.)

      Returns:
          str: Confirmation with deck details
      """
  ```
- [ ] Deck created in SQLite via DeckRepository
- [ ] Active deck set in core memory:
  ```
  [MEMORY UPDATE: active_deck]
  Name: Mono Red
  Format: standard
  ID: <uuid>
  Cards: 0
  Colors: none
  ```
- [ ] Format filter auto-set to match deck format
- [ ] Duplicate name handled (suggest alternative)
- [ ] Integration test verifies creation

**Technical Notes:**
- Memory update pattern per Architecture
- Format filter synced automatically
- Return user-friendly confirmation

**Prerequisites:** Story L4.1

---

### Story L4.3: Add Card to Deck Tool

As a **user**,
I want **to add cards to my deck through conversation**,
So that **I can build my deck naturally**.

**Acceptance Criteria:**

**Given** an active deck
**When** I say "add 4 Lightning Bolt"
**Then** cards are added:

- [ ] Tool at `src/letta/tools/deck_tools.py`:
  ```python
  def add_card_to_deck(card_name: str, quantity: int = 1, sideboard: bool = False) -> str:
      """
      Add a card to the active deck.

      Args:
          card_name (str): Name of the card to add
          quantity (int): Number of copies (default 1)
          sideboard (bool): Add to sideboard if True

      Returns:
          str: Confirmation with updated deck status
      """
  ```
- [ ] Card looked up via archival memory search
- [ ] Best match used if exact match not found
- [ ] Card added to SQLite deck_cards table
- [ ] Active deck memory block updated with new count/colors
- [ ] Ambiguous names prompt for clarification
- [ ] Integration test verifies addition

**Technical Notes:**
- Two-step: search archival → add to SQLite
- Update active_deck block with new state
- Handle card not found gracefully

**Prerequisites:** Story L4.2, Epic L2

---

### Story L4.4: Deck Validation Tool

As a **user**,
I want **deck construction rules enforced**,
So that **my deck is legal for the format**.

**Acceptance Criteria:**

**Given** adding cards to deck
**When** rules would be violated
**Then** I'm warned:

- [ ] Validation in `add_card_to_deck`:
  - Max 4 copies (except basic lands)
  - Card is legal in deck format
- [ ] Warning returned (not error):
  - "You already have 4 Lightning Bolt - can't add more"
  - "Counterspell is not legal in Standard"
- [ ] Use existing `src/logic/deck_validator.py`
- [ ] Validation can be bypassed with confirmation
- [ ] Unit tests for all validation rules

**Technical Notes:**
- Logic layer preserved unchanged
- Tools call into logic layer
- Return warnings, not exceptions

**Prerequisites:** Story L4.3

---

### Story L4.5: View, Load, and Delete Deck Tools

As a **user**,
I want **to see, switch between, and delete decks**,
So that **I can manage multiple deck ideas**.

**Acceptance Criteria:**

**Given** saved decks
**When** I manage decks
**Then** operations work:

- [ ] View tool:
  ```python
  def view_deck() -> str:
      """Display the active deck contents grouped by card type."""
  ```
- [ ] List tool:
  ```python
  def list_decks(format_filter: str | None = None) -> str:
      """List all saved decks with optional format filter."""
  ```
- [ ] Load tool:
  ```python
  def load_deck(name: str | None = None, deck_id: str | None = None) -> str:
      """Load a deck by name or ID and set as active."""
  ```
- [ ] Delete tool:
  ```python
  def delete_deck(name: str | None = None, deck_id: str | None = None, confirmed: bool = False) -> str:
      """Delete a deck with confirmation."""
  ```
- [ ] Load updates active_deck memory block
- [ ] Delete requires confirmation
- [ ] Integration tests for all operations

**Technical Notes:**
- Pattern consistent with Architecture
- Memory updates for state changes
- Confirmation for destructive actions

**Prerequisites:** Story L4.4

---

### Epic L4 Summary

| Story | Title | Key Deliverables |
|-------|-------|------------------|
| L4.1 | DB Access Pattern | SQLite connection helper |
| L4.2 | Create Deck | Deck creation with memory |
| L4.3 | Add Card | Card addition from archival |
| L4.4 | Validation | Format and copy rules |
| L4.5 | Deck Management | View, load, delete tools |

**Epic L4 Complete Criteria:**
- All deck CRUD operations working
- Memory blocks update correctly
- Validation rules enforced
- Integration tests pass
- Ready to proceed to Epic L5

---

## Epic L5: Deck Intelligence Tools

**Epic Goal:** Port mana curve analysis and synergy detection to Letta tool format.

**User Value:** Users receive intelligent feedback on deck composition and synergies.

**FRs Addressed:** FR6, FR7

**Technical Context:**
- Existing logic layer preserved
- Tools wrap logic layer calls
- Results formatted for chat display
- Auto-feedback system integration

---

### Story L5.1: Mana Curve Analysis Tool

As a **user**,
I want **to analyze my deck's mana curve**,
So that **I can build a balanced deck**.

**Acceptance Criteria:**

**Given** an active deck with cards
**When** I ask "analyze my curve"
**Then** I get analysis:

- [ ] Tool at `src/letta/tools/analysis_tools.py`:
  ```python
  def analyze_mana_curve() -> str:
      """
      Analyze the active deck's mana curve distribution.

      Returns:
          str: Curve analysis with recommendations
      """
  ```
- [ ] Uses existing `src/logic/mana_curve.analyze_mana_curve()`
- [ ] Output includes:
  - CMC distribution (0-7+)
  - Average CMC
  - Curve assessment (aggro/midrange/control)
  - Issues detected
  - Recommendations
- [ ] Text-based curve visualization
- [ ] Unit tests verify integration

**Technical Notes:**
- Logic layer unchanged
- Tool formats results for chat
- Keep existing analysis algorithms

**Prerequisites:** Epic L4 complete

---

### Story L5.2: Automatic Curve Feedback

As a **user**,
I want **curve feedback when I add cards**,
So that **I'm guided during deck building**.

**Acceptance Criteria:**

**Given** auto-feedback enabled
**When** I add a card
**Then** I may get feedback:

- [ ] `add_card_to_deck` triggers feedback check
- [ ] Uses `src/logic/mana_curve.generate_contextual_feedback()`
- [ ] Throttling rules preserved:
  - Always for first 5 cards
  - When distribution shifts >15%
  - When problems detected
- [ ] Feedback types: positive, warning, neutral
- [ ] Toggle tool:
  ```python
  def toggle_auto_feedback(enabled: bool) -> str:
      """Enable or disable automatic curve feedback."""
  ```
- [ ] Preference stored in core memory
- [ ] Integration test verifies feedback triggers

**Technical Notes:**
- Feedback appended to add_card response
- Throttling prevents spam
- User can disable via tool

**Prerequisites:** Story L5.1

---

### Story L5.3: Synergy Detection Tool

As a **user**,
I want **to see synergies in my deck**,
So that **I can build more cohesive decks**.

**Acceptance Criteria:**

**Given** an active deck with cards
**When** I ask "what synergies does my deck have?"
**Then** I get synergy report:

- [ ] Tool at `src/letta/tools/analysis_tools.py`:
  ```python
  def detect_synergies() -> str:
      """
      Analyze the active deck for card synergies.

      Returns:
          str: Synergy report with patterns and explanations
      """
  ```
- [ ] Uses existing `src/logic/synergy.detect_synergies()`
- [ ] Reports:
  - Tribal synergies (e.g., "8 Goblins")
  - Keyword synergies (e.g., "6 flying creatures")
  - Mechanic combos (e.g., "sacrifice theme")
- [ ] Explains why cards synergize
- [ ] "No synergies" handled helpfully
- [ ] Unit tests verify integration

**Technical Notes:**
- Logic layer unchanged
- Tool formats results for chat
- Return structured analysis

**Prerequisites:** Story L5.1

---

### Story L5.4: Synergy Card Suggestions

As a **user**,
I want **card suggestions that synergize with my deck**,
So that **I can discover cards I might not know**.

**Acceptance Criteria:**

**Given** a deck with identified themes
**When** I ask "suggest cards for my deck"
**Then** I get suggestions:

- [ ] Tool at `src/letta/tools/analysis_tools.py`:
  ```python
  def suggest_synergy_cards(limit: int = 7) -> str:
      """
      Suggest cards that synergize with the active deck.

      Args:
          limit (int): Maximum suggestions to return

      Returns:
          str: Suggested cards with explanations
      """
  ```
- [ ] Process:
  1. Detect deck themes via synergy logic
  2. Search archival for matching cards
  3. Filter to format-legal, not already in deck
  4. Return top suggestions with explanations
- [ ] Each suggestion explains synergy
- [ ] Suggestions respect format filter
- [ ] Integration test verifies relevance

**Technical Notes:**
- Combines synergy detection + archival search
- LLM curates final suggestions
- Limit to 5-7 to avoid overwhelming

**Prerequisites:** Story L5.3

---

### Epic L5 Summary

| Story | Title | Key Deliverables |
|-------|-------|------------------|
| L5.1 | Curve Analysis | Mana curve tool |
| L5.2 | Auto Feedback | Contextual curve guidance |
| L5.3 | Synergy Detection | Pattern recognition tool |
| L5.4 | Suggestions | LLM-curated card suggestions |

**Epic L5 Complete Criteria:**
- All analysis tools working
- Auto-feedback triggers appropriately
- Synergy detection accurate
- Suggestions relevant and helpful
- Ready to proceed to Epic L6

---

## Epic L6: Migration Cleanup

**Epic Goal:** Archive PydanticAI code, remove deprecated components, and validate complete migration.

**User Value:** Clean, maintainable codebase focused on Letta implementation.

**FRs Addressed:** All (validation)

**Technical Context:**
- Archive, don't delete (git history)
- Validate all FRs work with Letta
- Update documentation
- Remove unused dependencies

---

### Story L6.1: Archive PydanticAI Code

As a **developer**,
I want **old agent code archived**,
So that **the codebase is clean but history preserved**.

**Acceptance Criteria:**

**Given** successful Letta migration
**When** I archive old code
**Then** the following is done:

- [ ] Move `src/agent/` to `archive/pydanticai-agent/`
- [ ] Move `src/data/models/card.py` to archive
- [ ] Move `src/data/repositories/card.py` to archive
- [ ] Remove `data/cards.db` (cards now in Letta)
- [ ] Update imports throughout codebase
- [ ] Remove PydanticAI from `pyproject.toml`
- [ ] Git commit with clear message
- [ ] All tests still pass

**Technical Notes:**
- Archive for reference, not permanent storage
- Could be deleted in future cleanup
- Preserve git history of changes

**Prerequisites:** Epics L1-L5 complete

---

### Story L6.2: Documentation Update

As a **developer**,
I want **documentation updated for Letta**,
So that **the codebase is self-documenting**.

**Acceptance Criteria:**

**Given** completed migration
**When** I update docs
**Then** the following is current:

- [ ] CLAUDE.md updated:
  - Letta tech stack documented
  - Old PydanticAI sections marked deprecated
  - New development workflow documented
- [ ] README.md updated:
  - Setup includes Letta server
  - Two-terminal development workflow
  - New environment variables
- [ ] Architecture.md is authoritative (already updated)
- [ ] Inline code comments updated
- [ ] Remove outdated diagrams/references

**Technical Notes:**
- CLAUDE.md was partially updated during architecture
- Ensure consistency across all docs
- Remove references to OpenRouter (if not used)

**Prerequisites:** Story L6.1

---

### Story L6.3: Full Migration Validation

As a **developer**,
I want **validation that all features work**,
So that **I'm confident the migration is complete**.

**Acceptance Criteria:**

**Given** complete Letta implementation
**When** I run validation
**Then** all features work:

- [ ] Validation script at `scripts/validate_letta_migration.py`
- [ ] Validates each FR:
  - [ ] FR1: Cards searchable in archival (query test)
  - [ ] FR2: Natural language lookup works
  - [ ] FR3: Format filtering works
  - [ ] FR4: Deck creation works
  - [ ] FR5: Validation rules enforced
  - [ ] FR6: Curve analysis works
  - [ ] FR7: Synergy detection works
  - [ ] FR8: Deck CRUD works
  - [ ] FR9: Chainlit UI works
  - [ ] FR10: Layers properly separated
- [ ] Performance validation:
  - Card search < 500ms
  - Deck operations < 500ms
- [ ] Report output with pass/fail
- [ ] All tests pass: `uv run pytest`

**Technical Notes:**
- This is the GATE for migration completion
- Must pass before declaring migration done
- Run against real Letta server

**Prerequisites:** Stories L6.1-L6.2

---

### Epic L6 Summary

| Story | Title | Key Deliverables |
|-------|-------|------------------|
| L6.1 | Archive Old Code | Clean codebase |
| L6.2 | Update Docs | Current documentation |
| L6.3 | Validation | FR verification |

**Epic L6 Complete Criteria:**
- PydanticAI code archived
- All documentation current
- All FRs validated working
- Performance targets met
- Migration declared COMPLETE

---

## Summary

This epic breakdown documents Artificial-Planeswalker's migration from PydanticAI to Letta framework.

### Migration Overview

| Phase | Epics | Stories | Focus |
|-------|-------|---------|-------|
| Foundation | L1 | 4 | Letta server and agent setup |
| Data | L2 | 4 | Card import and search |
| Integration | L3 | 4 | Chainlit connection |
| Features | L4, L5 | 9 | Deck management and intelligence |
| Cleanup | L6 | 3 | Archival and validation |

**Total: 6 Epics, 24 Stories**

### What's Preserved

- Logic layer (`src/logic/`) - unchanged
- DeckRepository and SQLite - unchanged
- Chainlit UI patterns - adapted for Letta SDK
- Test structure - extended for Letta

### What's New

- Letta agent with tiered memory
- Archival memory for card search
- Core memory blocks for context
- Letta tool patterns (Google docstrings)
- Step streaming for responses

### Implementation Sequence

1. **Epic L1**: Set up Letta, create agent
2. **Epic L2**: Import cards, implement search
3. **Epic L3**: Connect Chainlit to Letta
4. **Epic L4**: Port deck tools
5. **Epic L5**: Port analysis tools
6. **Epic L6**: Clean up and validate

---

_Generated via BMAD Method workflow. 2026-01-04._
