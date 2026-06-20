---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - prd.md
  - research/technical-letta-framework-research-2026-01-04.md
  - docs/project-index.md
workflowType: 'architecture'
project_name: 'Artificial-Planeswalker'
user_name: 'Brad'
date: '2026-01-04'
status: 'complete'
completedAt: '2026-01-04'
---

# Architecture Decision Document

> ⚠️ **SUPERSEDED (architecture only) — 2026-06-20.** This is the **Letta-first** architecture (2026-01-04). The project has since pivoted to an **MCP-server architecture**; the current design of record is [`docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md`](../../docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md) (with the Phase-1 RAG de-risk in [`research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md`](research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md)).
>
> **Still valid:** the MTG **domain** content — functional requirements, data model, and core `data`/`logic` design.
> **Historical only:** anything describing the **Letta agent / Chainlit UI topology** — under the pivot, `src/agent` + `src/ui` are archived to `legacy/` and Letta returns later as a *client* of the MCP server (Phase 2), not the foundation.

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
The PRD defines 10 functional requirements spanning card lookup (FR1-FR3), deck management (FR4-FR5, FR8), deck building intelligence (FR6-FR7), and UI integration (FR9-FR10). All FRs remain valid post-pivot - only the implementation approach changes.

**Non-Functional Requirements:**
- **NFR1 (Offline-first)**: Card queries must not hit external APIs → Letta archival memory serves this via local vector DB
- **NFR3 (Testable agent)**: Agent logic independent of UI → Letta tools are pure Python functions, testable in isolation
- **NFR6 (UI replacement)**: UI layer must be decoupled → Chainlit as thin client to Letta REST API maintains this
- **NFR7 (Performance)**: <500ms query latency → archival memory semantic search must meet this target

**Scale & Complexity:**
- Primary domain: Backend Python + Conversational UI
- Complexity level: Medium (framework migration, not greenfield)
- Estimated architectural components: 4 layers preserved (UI, Agent, Logic, Data)

### Technical Constraints & Dependencies

**Framework Constraint:** Letta framework (formerly MemGPT) replaces PydanticAI
- Letta server required (Docker or pip install)
- letta-client SDK for Chainlit integration
- Embedding model dependency (OpenAI text-embedding-3-small)

**Data Constraints:**
- ~60k MTG cards from Scryfall bulk data
- Cards stored as Letta archival memory entries
- Decks remain in SQLite (structured queries needed)

**Integration Constraints:**
- Chainlit communicates via Letta REST API (not direct agent calls)
- Letta manages conversation history (recall memory)
- Session maps to Letta agent_id

### Cross-Cutting Concerns Identified

1. **Memory Persistence**: Cards (archival), conversation (recall), preferences (core blocks)
2. **Format/Games Filtering**: Must work with semantic search, stored in core memory block
3. **Active Deck Context**: Core memory block updated by tools, synced with SQLite
4. **Session Management**: Chainlit session → Letta agent_id mapping
5. **Error Handling**: Letta API failures, tool execution errors, embedding failures

## Foundation Evaluation

### Project Type

Migration from PydanticAI to Letta framework (not greenfield)

### Technical Preferences (Preserved from Existing Project)

| Category | Decision |
|----------|----------|
| Language | Python 3.12+ |
| Package Manager | UV |
| UI Framework | Chainlit 2.8+ |
| Database (Decks) | SQLite + SQLAlchemy 2.0 async |
| Code Quality | Ruff, mypy, pre-commit |
| Testing | pytest (unit/integration) |

### Letta Server Setup

**Selected Approach:** pip installation with SQLite (development mode)

**Rationale:**
- Matches existing SQLite-based development workflow
- Simpler local development experience
- Can migrate to Docker+PostgreSQL for production
- Single command startup

**Initialization Commands:**

```bash
# Add Letta to project dependencies
uv add letta letta-client

# Start Letta server (development)
letta server --port 8283 --data-dir ./data/letta
```

### Architectural Decisions Provided by Letta

- **State Persistence**: Agent state in Letta database
- **Memory Tiers**: Core (always in context), Recall (conversation), Archival (knowledge)
- **Tool Pattern**: Docstring-based schema (replaces @agent.tool decorator)
- **API Interface**: REST API on port 8283
- **Streaming**: WebSocket support for real-time responses

### Decisions Remaining for This Architecture

- Core memory block structure
- Tool implementation patterns
- Chainlit ↔ Letta integration
- Card data import strategy

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Core memory block structure (defines agent context)
- Card import strategy (enables card search functionality)
- Chainlit ↔ Letta integration pattern (enables UI communication)

**Important Decisions (Shape Architecture):**
- Tool database access pattern (affects all deck operations)
- Streaming response pattern (affects user experience)

**Deferred Decisions (Post-MVP):**
- Multi-user agent pool management
- Production PostgreSQL migration
- Agent backup/export strategy

### Data Architecture

**Card Storage: Letta Archival Memory**
- ~60,000 MTG cards stored as archival memory entries
- Semantic search via vector embeddings
- Embedding model: OpenAI `text-embedding-3-small`
- One-time import cost: ~$0.60

**Card Import Strategy: File Upload**
- Export Scryfall data to JSON format
- Upload as Letta data source (async processing)
- Letta handles chunking and embedding optimization
- Agent and data source share same embedding model

**Deck Storage: SQLite (Preserved)**
- Existing DeckRepository and DeckModel retained
- Structured queries for deck operations
- Database path: `./data/decks.db`

### Core Memory Block Structure

| Block | Purpose | Limit | Update Pattern |
|-------|---------|-------|----------------|
| `persona` | MTG deck-building expert identity | 2000 chars | Static (set at agent creation) |
| `human` | User preferences, play style, history | 2000 chars | Evolves via agent learning |
| `active_deck` | Current deck summary (name, format, card count, colors) | 5000 chars | Updated by deck tools |
| `format_filter` | Current format/games restriction for searches | 500 chars | Updated by filter tools |

### API & Communication Patterns

**Chainlit ↔ Letta Integration: One Agent per User**
- Create Letta agent on first user visit
- Store agent_id in Chainlit user session
- Reuse agent across sessions (stateful)
- Agent memory persists and grows over time

**Streaming: Step Streaming (Letta Default)**
- Complete `LettaMessage` objects delivered after each agent step
- No client-side token accumulation required
- Steps include: reasoning, tool execution, response generation
- Simpler implementation than token streaming

**Pattern:**
```python
async for chunk in client.agents.messages.stream(agent_id, messages):
    if chunk.message_type == "assistant_message":
        await cl_message.stream_token(chunk.content)
```

### Tool Implementation Pattern

**Database Access: Environment Path Pattern**
- Tools receive database path via environment variable
- Tools create sync SQLite connections as needed
- Keeps tools portable and testable in isolation

**Pattern:**
```python
def add_card_to_deck(card_name: str, quantity: int = 1) -> str:
    """Add a card to the active deck."""
    import os
    import sqlite3

    db_path = os.environ.get("APP_DATABASE_PATH", "data/decks.db")
    conn = sqlite3.connect(db_path)
    # ... tool logic
```

**Tool Execution Environment:**
- Set via `tool_exec_environment_variables` on agent
- Includes: `APP_DATABASE_PATH`, `LETTA_AGENT_ID`

### Infrastructure & Deployment

**Development Workflow:**
- Terminal 1: `letta server --port 8283 --data-dir ./data/letta`
- Terminal 2: `uv run chainlit run src/ui/app.py -w`

**Testing Strategy:**
- Unit tests: Mock Letta client, test tool logic
- Integration tests: Test against local Letta server
- E2E tests: Chainlit test client with live agent

### Decision Impact Analysis

**Implementation Sequence:**
1. Set up Letta server and create base agent with memory blocks
2. Import card data to archival memory
3. Implement core tools (deck CRUD, card search)
4. Integrate Chainlit with Letta SDK
5. Port remaining tools (mana curve, synergy)
6. Remove PydanticAI code

**Cross-Component Dependencies:**
- Card import must complete before card search tools work
- Agent creation must happen before Chainlit can send messages
- Memory blocks must be defined before tools can update them

## Implementation Patterns & Consistency Rules

### Preserved Patterns (from Existing Codebase)

| Category | Pattern | Example |
|----------|---------|---------|
| Python Naming | snake_case functions, PascalCase classes | `create_deck()`, `DeckModel` |
| Database Naming | snake_case tables and columns | `deck_cards.card_id` |
| Repository Returns | Pydantic schemas, never ORM objects | `Card` not `CardModel` |
| Test Organization | `tests/unit/`, `tests/integration/` | `tests/unit/letta/test_tools.py` |
| Layer Separation | data → logic → agent → ui (no reverse imports) | UI never imports from data |

### Letta Tool Definition Pattern

**All tools MUST follow this structure:**
```python
def tool_name(required_param: str, optional_param: int = 1) -> str:
    """
    One-line summary (imperative mood).

    Extended description if needed.

    Args:
        required_param (str): What this parameter controls
        optional_param (int): Default behavior and override cases

    Returns:
        str: User-facing message describing the result
    """
```

**Tool Rules:**
- Return type always `str` (Letta requirement)
- Docstring is the schema (Google style, parsed by Letta)
- No exceptions raised to user - return error messages
- Import dependencies inside function (tool isolation)

### Memory Block Update Pattern

**Tools that modify state MUST include memory update instructions:**
```python
return f"""Added {card_name} to deck.

[MEMORY UPDATE: active_deck]
Name: {deck_name}
Format: {format}
Cards: {total_count}
Colors: {color_identity}
"""
```

**Memory block update rules:**
- Use `[MEMORY UPDATE: block_name]` marker
- Agent interprets and applies to core memory
- Include all fields that changed
- Keep format consistent for agent parsing

### Error Response Pattern

**User-facing error messages:**
```python
# CORRECT: User-friendly, actionable
return "Could not find 'Litning Bolt'. Did you mean 'Lightning Bolt'?"

# WRONG: Technical error
raise CardNotFoundError("No card with name 'Litning Bolt'")
```

**Error categories:**
- **Not Found**: Suggest alternatives or next steps
- **Invalid State**: Explain required state and how to get there
- **Validation**: Explain rule and how to comply

### Archival Memory Card Format

**Card entries stored in this format for semantic search:**
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

**Format rules:**
- One card per archival entry
- Text optimized for embedding similarity
- Include all searchable fields
- Legalities as key=value pairs

### Chainlit ↔ Letta Session Pattern

**Session initialization:**
```python
AGENT_ID_KEY = "letta_agent_id"
LETTA_BASE_URL = "http://localhost:8283"

@cl.on_chat_start
async def on_chat_start():
    agent_id = cl.user_session.get(AGENT_ID_KEY)
    if not agent_id:
        agent = await get_or_create_agent(letta_client)
        cl.user_session.set(AGENT_ID_KEY, agent.id)
```

**Session rules:**
- One Letta agent per user (persisted across sessions)
- Agent ID stored in Chainlit user session
- Lazy agent creation (first message triggers)

### Enforcement Guidelines

**All AI Agents MUST:**
1. Follow existing Python/database naming conventions (snake_case)
2. Use Google-style docstrings for Letta tools
3. Return user-friendly strings, never raise exceptions to user
4. Include `[MEMORY UPDATE: block]` when modifying agent state
5. Import dependencies inside tool functions

**Pattern Verification:**
- Ruff enforces Python naming conventions
- mypy enforces type hints on tool signatures
- Unit tests verify tool return formats
- Integration tests verify memory updates

## Project Structure & Boundaries

### Complete Project Directory Structure

```
Artificial-Planeswalker/
├── pyproject.toml                    # Add letta, letta-client dependencies
├── .env                              # Add LETTA_BASE_URL, OPENAI_API_KEY
├── data/
│   ├── decks.db                      # Deck storage (preserved)
│   └── letta/                        # Letta server data directory
├── src/
│   ├── letta/                        # NEW: Letta agent layer
│   │   ├── agent.py                  # Agent creation, memory blocks
│   │   ├── client.py                 # Letta SDK wrapper
│   │   ├── memory.py                 # Memory block definitions
│   │   └── tools/
│   │       ├── card_tools.py         # search_cards (archival)
│   │       ├── deck_tools.py         # CRUD operations
│   │       ├── filter_tools.py       # Format/games filters
│   │       └── analysis_tools.py     # Curve, synergy
│   ├── data/                         # MODIFIED: Deck-only
│   │   ├── models/deck.py, deck_card.py
│   │   ├── schemas/card.py, deck.py
│   │   └── repositories/deck.py
│   ├── logic/                        # UNCHANGED
│   │   ├── mana_curve.py
│   │   └── synergy.py
│   └── ui/                           # MODIFIED: Letta SDK integration
│       ├── app.py
│       └── handlers/message_handler.py
├── scripts/
│   ├── import_cards_to_letta.py      # NEW: Card import
│   └── create_letta_agent.py         # NEW: Agent setup
└── tests/
    ├── unit/letta/                   # NEW: Tool tests
    └── integration/letta/            # NEW: Agent tests
```

### Architectural Boundaries

**Layer Communication:**
- UI → Letta: REST API calls via `letta-client` SDK
- Letta → Logic: Direct Python imports in tools
- Letta → Data: Sync SQLite in tools (via env path)
- Letta → Cards: Archival memory semantic search

**Data Boundaries:**

| Data | Storage | Access |
|------|---------|--------|
| Cards | Letta Archival | `archival_memory_search` |
| Decks | SQLite | DeckRepository (sync) |
| Conversation | Letta Recall | Automatic |
| Preferences | Core Memory | Agent updates |

### Integration Points

**Chainlit ↔ Letta:**
- `on_chat_start`: Get or create agent, store ID in session
- `on_message`: Stream messages via `client.agents.messages.stream()`
- Session maps to persistent Letta agent

**Letta Tools ↔ SQLite:**
- Tools import `sqlite3` internally
- DB path from `APP_DATABASE_PATH` env var
- Sync connections (Letta tools are sync)

**Letta Tools ↔ Logic Layer:**
- Tools import from `src/logic/` directly
- `mana_curve.analyze()`, `synergy.detect()`
- Logic layer unchanged

### Requirements to Structure Mapping

| Epic | Components |
|------|------------|
| Epic 2: Agent Core | `src/letta/agent.py`, `src/letta/memory.py` |
| Epic 2: Card Lookup | `src/letta/tools/card_tools.py` |
| Epic 3: Chainlit | `src/ui/app.py`, `src/ui/handlers/` |
| Epic 4: Deck CRUD | `src/letta/tools/deck_tools.py` |
| Epic 5: Intelligence | `src/letta/tools/analysis_tools.py`, `src/logic/` |

### Removed Components (Post-Migration)

After successful migration, archive:
- `src/agent/` (entire directory)
- `src/data/models/card.py`
- `src/data/repositories/card.py`
- `data/cards.db`

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:** All technology choices verified compatible
- Letta framework works with Python 3.12+
- SQLite accessible via sync connections in Letta tools
- Step streaming maps cleanly to Chainlit's streaming API

**Pattern Consistency:** All patterns align with technology stack
- Google-style docstrings parsed by Letta SDK
- snake_case naming matches existing codebase
- Memory block update pattern works with Letta core memory

**Structure Alignment:** Project structure supports all decisions
- `src/letta/` contains all Letta-specific code
- Layer boundaries maintained (UI → Letta → Logic → Data)
- Integration points use REST API and environment variables

### Requirements Coverage ✅

**Functional Requirements:** All 10 FRs architecturally supported
- Card operations via Letta archival memory
- Deck operations via SQLite + DeckRepository
- Intelligence features via logic layer (preserved)
- UI via Chainlit + Letta SDK integration

**Non-Functional Requirements:**
- NFR1 (Offline-first): ✅ Archival memory is local
- NFR3 (Testable): ✅ Pure Python tools
- NFR6 (UI replacement): ✅ Letta API is UI-agnostic
- NFR7 (Performance): ⚠️ Verify semantic search meets <500ms

### Implementation Readiness ✅

**Decision Completeness:**
- All critical decisions documented with rationale
- Technology versions specified where applicable
- Trade-offs explained for major choices

**Structure Completeness:**
- Full directory tree with new/modified/preserved markers
- Integration points specified (REST API, env vars, imports)
- Migration path clear (what to archive post-migration)

**Pattern Completeness:**
- Tool definition pattern with example
- Memory block update pattern with example
- Error response pattern with example
- Session management pattern with example

### Gap Analysis Results

| Gap | Priority | Mitigation |
|-----|----------|------------|
| Letta API error handling in UI | Minor | Add try/except in on_message |
| Agent reconnection on server restart | Minor | Retry logic in client wrapper |
| Semantic search quality validation | Minor | Integration tests for relevance |

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed (Medium - migration)
- [x] Technical constraints identified (Letta, hybrid storage)
- [x] Cross-cutting concerns mapped (memory, session, filters)

**✅ Architectural Decisions**
- [x] Critical decisions documented (5 decisions)
- [x] Technology stack specified (Letta, SQLite, Chainlit)
- [x] Integration patterns defined (REST API, step streaming)
- [x] Performance considerations noted (NFR7 needs validation)

**✅ Implementation Patterns**
- [x] Naming conventions established (snake_case, Google docstrings)
- [x] Structure patterns defined (tool isolation, memory updates)
- [x] Communication patterns specified (REST API, env vars)
- [x] Process patterns documented (error handling, session)

**✅ Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High

**Key Strengths:**
- Clear migration path from PydanticAI to Letta
- Hybrid storage decision validated (cards in Letta, decks in SQLite)
- Existing logic layer fully preserved
- Patterns provide concrete examples for AI agents

**Areas for Future Enhancement:**
- Multi-user agent pool management (post-MVP)
- Production PostgreSQL migration
- Semantic search quality optimization

### Implementation Handoff

**AI Agent Guidelines:**
1. Follow all architectural decisions exactly as documented
2. Use Letta tool definition pattern for all new tools
3. Include `[MEMORY UPDATE: block]` in tools that modify state
4. Respect layer boundaries (no direct data access from UI)
5. Use step streaming for Chainlit integration

**First Implementation Priority:**
1. `uv add letta letta-client` - Add dependencies
2. `scripts/create_letta_agent.py` - Create base agent with memory blocks
3. `scripts/import_cards_to_letta.py` - Import card data to archival memory
4. `src/letta/tools/deck_tools.py` - Port first tool

## Architecture Completion Summary

### Workflow Completion

**Architecture Decision Workflow:** COMPLETED ✅
**Total Steps Completed:** 8
**Date Completed:** 2026-01-04
**Document Location:** `_bmad-output/planning-artifacts/architecture.md`

### Final Architecture Deliverables

**Complete Architecture Document**
- All architectural decisions documented with rationale
- Implementation patterns ensuring AI agent consistency
- Complete project structure with migration markers
- Requirements to architecture mapping
- Validation confirming coherence and completeness

**Implementation Ready Foundation**
- 5 core architectural decisions made
- 5 implementation patterns defined
- 4-layer architecture preserved with Letta integration
- 10 functional requirements fully supported

**AI Agent Implementation Guide**
- Technology stack: Letta + SQLite + Chainlit
- Consistency rules preventing implementation conflicts
- Project structure with clear boundaries
- Integration patterns and communication standards

### Development Sequence

1. Add dependencies: `uv add letta letta-client`
2. Start Letta server: `letta server --port 8283 --data-dir ./data/letta`
3. Create agent with memory blocks: `scripts/create_letta_agent.py`
4. Import cards to archival memory: `scripts/import_cards_to_letta.py`
5. Port tools to Letta format: `src/letta/tools/`
6. Update Chainlit integration: `src/ui/app.py`
7. Archive PydanticAI code: `src/agent/` → archive

### Quality Assurance Checklist

**✅ Architecture Coherence**
- [x] All decisions work together without conflicts
- [x] Technology choices are compatible
- [x] Patterns support the architectural decisions
- [x] Structure aligns with all choices

**✅ Requirements Coverage**
- [x] All functional requirements supported
- [x] All non-functional requirements addressed
- [x] Cross-cutting concerns handled
- [x] Integration points defined

**✅ Implementation Readiness**
- [x] Decisions are specific and actionable
- [x] Patterns prevent agent conflicts
- [x] Structure is complete and unambiguous
- [x] Examples provided for clarity

---

**Architecture Status:** READY FOR IMPLEMENTATION ✅

**Next Phase:** Create epics and stories for Letta migration implementation

**Document Maintenance:** Update this architecture when major technical decisions are made during implementation

