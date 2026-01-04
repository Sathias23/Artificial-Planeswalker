---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'letta-framework-for-mtg-assistant'
research_goals: 'Evaluate Letta framework for replacing PydanticAI agent backend, focusing on memory systems (especially archival memory for card data) and tool integration patterns'
user_name: 'Brad'
date: '2026-01-04'
web_research_enabled: true
source_verification: true
---

# Technical Research Report: Letta Framework for MTG Assistant

**Date:** 2026-01-04
**Author:** Brad
**Research Type:** Technical

---

## Research Overview

**Context:** Evaluating Letta framework as a replacement for PydanticAI in the Artificial-Planeswalker MTG deck-building assistant.

**Key Research Questions:**
1. How does Letta's archival memory work, and is it suitable for storing ~60k MTG cards as immutable metadata?
2. How does Letta's tool system compare to PydanticAI's tool pattern?
3. What architectural changes would be required for migration?
4. What can be preserved from the current codebase (UI layer, data layer)?

**Hypothesis to Validate:** Archival memory could serve as an ideal store for MTG card information - immutable metadata embedded for each card as separate archival memory entries.

---

<!-- Content will be appended sequentially through research workflow steps -->

## Technical Research Scope Confirmation

**Research Topic:** Letta Framework for MTG Assistant
**Research Goals:** Evaluate Letta framework for replacing PydanticAI agent backend, focusing on memory systems (especially archival memory for card data) and tool integration patterns

**Priority Focus Areas:**
- Archival Memory - suitability for ~60k MTG cards as immutable metadata entries
- Memory Architecture - core/recall/archival memory interaction, retrieval patterns
- Tool System - comparison to PydanticAI's tool pattern, migration complexity
- Integration Patterns - SQLite database integration, Chainlit UI compatibility

**Standard Technical Research Scope:**
- Architecture Analysis - design patterns, frameworks, system architecture
- Implementation Approaches - development methodologies, coding patterns
- Technology Stack - languages, frameworks, tools, platforms
- Integration Patterns - APIs, protocols, interoperability
- Performance Considerations - scalability, optimization, patterns

**Research Methodology:**
- Current web data with rigorous source verification
- Multi-source validation for critical technical claims
- Confidence level framework for uncertain information
- Comprehensive technical coverage with architecture-specific insights

**Scope Confirmed:** 2026-01-04

---

## Technology Stack Analysis

### Core Framework: Letta (formerly MemGPT)

Letta is a platform for building **stateful LLM agents** with persistent memory. It evolved from the MemGPT research paper that introduced self-managed memory for LLMs.

**Key Characteristics:**
- Python-based framework (supports Python 3.13+)
- Built by systems engineers for production at scale
- 20,400+ GitHub stars as of January 2026
- Agent microservices architecture with REST APIs
- Official TypeScript SDK available (v0.6.4+)

_Source: [GitHub - letta-ai/letta](https://github.com/letta-ai/letta)_

### Memory Architecture (Critical for MTG Card Storage)

Letta's memory system is inspired by operating system memory hierarchies:

| Memory Tier | Analogy | Characteristics | MTG Use Case |
|-------------|---------|-----------------|--------------|
| **Core Memory** | RAM | Always in context, editable blocks, 2k char default limit per block | Active deck context, user preferences |
| **Recall Memory** | Conversation logs | Complete interaction history, auto-saved to disk, searchable | Chat history, deck-building session |
| **Archival Memory** | Vector DB / Disk | Out-of-context storage, semantic search, **scales to millions of entries** | **MTG card database (~60k cards)** |

**Archival Memory Deep Dive:**
- Implemented as vector database store
- Each memory entry = text chunk + embedding vector
- Default embedding: OpenAI `text-embedding-3-small`
- Retrieval via semantic similarity search
- **No specified upper limit on entries** - documentation states "millions of entries"
- Persists across conversations and agent restarts

_Source: [Memory overview | Letta Docs](https://docs.letta.com/guides/agents/memory/), [Archival memory | Letta Docs](https://docs.letta.com/guides/ade/archival-memory/)_

### Tool System

Letta provides rich tool support comparable to PydanticAI:

**Built-in Tools:**
- `send_message` - Agent output
- `memory_insert` / `memory_replace` - Core memory management
- `archival_memory_insert` / `archival_memory_search` - Archival memory access

**Custom Tool Creation:**
- Python SDK with `BaseTool` class extension
- Docstring-based schema parsing (similar to PydanticAI pattern)
- Pydantic object support for explicit argument schemas
- Tools can access Letta client for agent-to-agent communication
- MCP (Model Context Protocol) tool integration
- Composio integration (7,000+ tools)

**Tool Editor (ADE):**
- Write and test Python code directly in Agent Development Environment
- Mock input testing with response/log/error visibility

_Source: [Define and customize tools | Letta](https://docs.letta.com/guides/agents/custom-tools)_

### Data Source Integration

**File Upload to Archival Memory:**
- Supported formats: PDF, TXT, MD, JSON
- Async job processing: chunking → embedding → storage
- Data sources can be attached to multiple agents
- **Requirement**: Agent and source must use same embedding model

**Filesystem Support:**
- Folder attachment with file browsing tools
- Windowed context to prevent overflow
- Agent can navigate and search files

_Source: [Connecting agents to data sources | Letta](https://docs.letta.com/guides/agents/sources)_

### Programming Languages & Dependencies

- **Primary**: Python 3.10+ (3.13 supported as of v0.6.4)
- **Embedding Models**: OpenAI, Anthropic, Gemini, local models via Ollama
- **LLM Providers**: Multi-provider support (OpenAI, Anthropic, etc.)
- **Database**: PostgreSQL for production, SQLite for development
- **Vector Store**: Built-in or external (custom integration possible)

_Source: [letta · PyPI](https://pypi.org/project/letta/)_

### Deployment Options

**Local Development:**
- Docker Compose setup
- SQLite backend
- Single-agent testing

**Production (Letta Cloud):**
- Managed infrastructure
- Agent microservices with REST APIs
- Multi-agent orchestration
- ADE (Agent Development Environment) for debugging

_Source: [Letta](https://www.letta.com/)_

### Letta vs PydanticAI Comparison

| Aspect | PydanticAI (Current) | Letta (Proposed) |
|--------|---------------------|------------------|
| **Core Focus** | Type safety, structured outputs | Long-term memory, stateful agents |
| **Architecture** | Library/framework | Microservices with REST APIs |
| **Memory** | Session-based (manual) | Built-in tiered memory system |
| **Tool Definition** | `@agent.tool` decorator | `BaseTool` class or docstring |
| **Conversation History** | Manual management | Automatic recall memory |
| **Card Storage** | External SQLite + Repository pattern | Archival memory (vector DB) |
| **Best For** | Validation, IDE integration | Agents that learn over time |

_Source: [PydanticAI](https://ai.pydantic.dev/), [Letta Blog](https://www.letta.com/blog/agent-memory)_

### Technology Adoption Trends

- Letta Code ranked #1 on Terminal-Bench (AI coding benchmark) for model-agnostic agents
- Growing adoption of Agent File (.af) format for portable stateful agents
- AI Memory SDK enables "subconscious agent" pattern for memory management
- Community moving toward memory-first agent design

_Source: [Letta Code Blog](https://www.letta.com/blog/letta-code), [AI Memory SDK](https://github.com/letta-ai/ai-memory-sdk)_

### Open Architectural Questions

**Deck Storage Decision** (flagged during research):
- Option A: Decks in Letta (core memory blocks or archival memory)
- Option B: Decks remain in SQLite (existing DeckRepository pattern)
- Option C: Hybrid approach (metadata in Letta, persistence in SQLite)

This requires deeper investigation in integration patterns analysis.

---

## Integration Patterns Analysis

### Letta REST API Architecture

Letta exposes a comprehensive REST API for programmatic agent interaction:

**Core Endpoints:**
| Resource | Operations | Use Case |
|----------|------------|----------|
| `/agents` | CRUD, export/import | Agent lifecycle management |
| `/agents/{id}/messages` | create, stream, list, reset | Conversation handling |
| `/agents/{id}/blocks` | attach, detach, update | Memory block management |
| `/agents/{id}/tools` | attach, run, approve | Tool execution |
| `/agents/{id}/passages` | create, search, delete | Archival memory operations |

**Python SDK (`letta-client`):**
```python
from letta_client import Letta

# Cloud connection
client = Letta(api_key="LETTA_API_KEY")

# Self-hosted connection
client = Letta(base_url="http://localhost:8283")
```

- Sync, async, and streaming support
- Type-safe with mypy/pyright compatibility
- Python 3.8+ compatible

_Source: [Letta Python SDK](https://docs.letta.com/api/python/), [GitHub - letta-python](https://github.com/letta-ai/letta-python)_

### Chainlit Integration Pattern

**Finding:** No native Letta-Chainlit integration exists. Custom integration required.

**Recommended Pattern:**
```
[Chainlit UI] <--HTTP/WebSocket--> [Letta REST API] <--> [Letta Agent]
                                         |
                                   [Letta Server]
                                   (PostgreSQL/SQLite)
```

**Integration Approach:**
1. Chainlit `on_message` handler calls Letta SDK
2. Use streaming endpoint for real-time response
3. Map Chainlit session to Letta agent ID
4. Store agent ID in Chainlit user session

**Code Pattern (conceptual):**
```python
@cl.on_message
async def handle_message(message: cl.Message):
    agent_id = cl.user_session.get("letta_agent_id")

    # Stream response from Letta
    async for chunk in client.agents.messages.stream(
        agent_id=agent_id,
        messages=[{"role": "user", "content": message.content}]
    ):
        await cl.Message(content=chunk).send()
```

_Source: [Chainlit Docs](https://docs.chainlit.io/), [Letta API Reference](https://docs.letta.com/api-reference/overview/)_

### Database Integration Patterns

**Letta's Internal Storage:**
- PostgreSQL (production) or SQLite (development)
- Stores: agent state, memories, tools, messages
- Normalized tables with pgvector for embeddings
- Alembic migrations (PostgreSQL only)

**External Database Integration Options:**

| Approach | Description | Pros | Cons |
|----------|-------------|------|------|
| **Custom Tools** | Tool that queries SQLite | Keeps existing DeckRepository | Extra latency, tool overhead |
| **Data Source Upload** | Import cards as Letta data source | Native archival memory | One-time import, sync complexity |
| **Hybrid** | Letta for agent state, SQLite for app data | Clear separation | Two databases to manage |

_Source: [Letta FAQs](https://docs.letta.com/faq), [AWS Aurora + Letta](https://aws.amazon.com/blogs/database/how-letta-builds-production-ready-ai-agents-with-amazon-aurora-postgresql/)_

### Deck Storage Decision Framework

Based on research, here's the analysis for your specific question:

#### Option A: Decks in Letta Core Memory Blocks

**How it would work:**
- Create a `deck` memory block (up to 5000 chars)
- Store deck summary: name, format, card list with quantities
- Agent always sees active deck in context

**Pros:**
- Always in context (no retrieval needed)
- Agent can modify deck directly via `memory_replace`
- Natural fit for "active deck" concept

**Cons:**
- 5000 char limit (~50-100 cards with metadata)
- No query/filter capabilities
- Single deck at a time (need block per deck for multiple)

**Verdict:** Good for **active deck summary**, not full deck storage.

#### Option B: Decks in Letta Archival Memory

**How it would work:**
- Each deck as archival memory entry
- Semantic search to find decks by description
- Store full deck JSON as passage

**Pros:**
- Scales to many decks
- Persists across sessions
- Semantic search for deck discovery

**Cons:**
- Retrieval required (not always in context)
- Vector search less precise than SQL queries
- No relational queries (e.g., "all decks with Lightning Bolt")

**Verdict:** Possible but **not ideal** for structured deck data.

#### Option C: Decks in SQLite (Existing Pattern) [RECOMMENDED]

**How it would work:**
- Keep existing `DeckRepository` and SQLite schema
- Create Letta custom tools that call repository
- Letta handles conversation; SQLite handles persistence

**Pros:**
- Preserves existing working code
- SQL queries for complex deck operations
- Clear separation: Letta = agent brain, SQLite = app database
- Can still use Letta for conversation history and user preferences

**Cons:**
- Two storage systems to maintain
- Tool overhead for every deck operation

**Verdict:** **Best fit** for structured, queryable deck data.

#### Recommended Hybrid Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     LETTA AGENT                             │
├─────────────────────────────────────────────────────────────┤
│ Core Memory Blocks:                                         │
│   - persona: "MTG deck-building assistant..."               │
│   - user_preferences: "Prefers aggro, plays Standard..."    │
│   - active_deck_summary: "Current: 'Red Deck Wins' (45/60)" │
├─────────────────────────────────────────────────────────────┤
│ Archival Memory (Vector DB):                                │
│   - ~60,000 MTG card entries (immutable, semantic search)   │
│   - "Find cards with flying and lifelink"                   │
├─────────────────────────────────────────────────────────────┤
│ Custom Tools:                                               │
│   - search_cards() → queries archival memory                │
│   - create_deck() → calls SQLite via DeckRepository         │
│   - add_card_to_deck() → calls SQLite                       │
│   - view_deck() → calls SQLite, updates core memory block   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLITE DATABASE                          │
│   - decks table (id, name, format, strategy, tags)          │
│   - deck_cards table (deck_id, card_id, quantity, sideboard)│
│   - (cards table removed - now in Letta archival memory)    │
└─────────────────────────────────────────────────────────────┘
```

_Source: [Memory Blocks](https://docs.letta.com/guides/agents/memory-blocks/), [Memory Overview](https://docs.letta.com/guides/agents/memory/)_

### Communication Protocols

**Letta Server Communication:**
- REST API over HTTP/HTTPS
- WebSocket support for streaming
- JSON data format throughout
- OpenAPI specification available

**Authentication:**
- API key header for Letta Cloud
- Optional auth for self-hosted
- Per-agent access control possible

_Source: [Letta API Overview](https://docs.letta.com/api-reference/overview/)_

### MCP (Model Context Protocol) Integration

Letta acts as an MCP client, enabling:
- Connection to external MCP servers
- Access to 7,000+ Composio tools
- Custom MCP server integration via ADE

**Relevance:** Could connect to Scryfall MCP or other MTG data sources if needed.

_Source: [Define and customize tools | Letta](https://docs.letta.com/guides/agents/custom-tools)_

---

## Architectural Patterns and Design

### Letta V1 Agent Architecture

Letta has evolved from the original MemGPT architecture to Letta V1, optimized for modern LLM capabilities:

**Core Design Principles:**
| Aspect | MemGPT (Legacy) | Letta V1 (Current) |
|--------|-----------------|-------------------|
| Tool Calling | Everything via tools (even `send_message`) | Direct assistant messages + tools |
| Reasoning | Prompted chain-of-thought | Native model reasoning |
| Loop Control | `request_heartbeat` mechanism | Model-driven termination |
| LLM Requirements | Tool calling required | Works with any LLM |

**Key Architectural Features:**
- **Stateful by default**: All agent interactions persist to database
- **Checkpointed execution**: Each step saved, enabling recovery
- **Memory blocks**: Self-editing context that evolves over time
- **Agent as microservice**: REST API endpoint with auth support

_Source: [Rearchitecting Letta's Agent Loop](https://www.letta.com/blog/letta-v1-agent), [Building stateful agents](https://docs.letta.com/guides/agents/overview/)_

### Migration Architecture: PydanticAI → Letta

**Current PydanticAI Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│                    CHAINLIT UI                              │
│   on_message() → run_agent_with_session()                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   PYDANTICAI AGENT                          │
│   - Agent() with system prompt                              │
│   - @agent.tool decorators                                  │
│   - AgentDependencies (repos, session)                      │
│   - ConversationSessionManager (manual history)             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 DATA LAYER (SQLite)                         │
│   - CardRepository (60k cards)                              │
│   - DeckRepository (user decks)                             │
│   - SQLAlchemy async                                        │
└─────────────────────────────────────────────────────────────┘
```

**Proposed Letta Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│                    CHAINLIT UI                              │
│   on_message() → letta_client.agents.messages.stream()      │
│   Session maps to Letta agent_id                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LETTA SERVER                             │
│   (Docker container or self-hosted)                         │
│   PostgreSQL/SQLite backend                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    LETTA AGENT                              │
├─────────────────────────────────────────────────────────────┤
│ Memory Blocks (Core Memory):                                │
│   - persona: "MTG deck-building expert..."                  │
│   - human: "User preferences, play style..."                │
│   - active_deck: "Current deck summary..."                  │
├─────────────────────────────────────────────────────────────┤
│ Archival Memory:                                            │
│   - 60k MTG card entries (vector embeddings)                │
│   - Semantic search: "flying creatures under 3 mana"        │
├─────────────────────────────────────────────────────────────┤
│ Recall Memory:                                              │
│   - Full conversation history (auto-managed)                │
│   - Searchable chat context                                 │
├─────────────────────────────────────────────────────────────┤
│ Custom Tools:                                               │
│   - search_cards() → archival_memory_search                 │
│   - create_deck() → SQLite DeckRepository                   │
│   - add_card_to_deck() → SQLite + update active_deck block  │
│   - analyze_mana_curve() → logic layer                      │
│   - detect_synergies() → logic layer                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              APPLICATION DATABASE (SQLite)                  │
│   - decks table                                             │
│   - deck_cards table                                        │
│   (cards table REMOVED - now in Letta archival memory)      │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibility Mapping

| Component | PydanticAI (Current) | Letta (Proposed) |
|-----------|---------------------|------------------|
| **Agent Definition** | `Agent()` with system prompt | Agent config via SDK/ADE |
| **Tool Registration** | `@agent.tool` decorator | `BaseTool` class or docstring |
| **Conversation History** | `ConversationSessionManager` (manual) | Recall memory (automatic) |
| **Session State** | `AgentDependencies` passed per call | Agent state persists in Letta |
| **Card Database** | `CardRepository` + SQLite | Archival memory (vector DB) |
| **Deck Storage** | `DeckRepository` + SQLite | Keep `DeckRepository` + SQLite |
| **Format Filter** | `deps.format_filter` | Core memory block or tool state |
| **UI Integration** | Direct agent call | Letta SDK client call |

_Source: [Letta Docs](https://docs.letta.com/), [PydanticAI Docs](https://ai.pydantic.dev/)_

### Design Principles for Migration

**1. Memory-First Design**
> "Programming agents starts with programming memory." - Letta philosophy

- Define memory blocks before tools
- Use archival memory for knowledge base (cards)
- Use core memory for runtime context (active deck, preferences)

**2. Tool Simplification**
Letta tools focus on actions, not context management:
```python
# PydanticAI: Tool needs full context
@agent.tool
async def search_cards(ctx: RunContext[AgentDeps], query: str):
    deps = ctx.deps
    cards = await deps.card_repository.search_advanced(...)
    return format_cards(cards)

# Letta: Tool is simpler, memory handles context
def search_cards(query: str) -> str:
    """Search MTG cards by semantic query."""
    # archival_memory_search handles the retrieval
    # Tool just formats/returns results
    return formatted_results
```

**3. Stateful Agent Pattern**
- One agent per user (not per session)
- Agent "grows" with user over time
- Memory blocks capture learned preferences

**4. Separation of Concerns**
```
Letta Agent    → Conversation, memory, tool orchestration
SQLite         → Structured application data (decks)
Archival Memory → Knowledge base (cards)
Logic Layer    → Business rules (mana curve, synergies)
Chainlit       → UI rendering only
```

_Source: [Agent Memory Blog](https://www.letta.com/blog/agent-memory), [AI Agents Stack](https://www.letta.com/blog/ai-agents-stack)_

### Scalability Patterns

**Single-User (Current MVP):**
- One Letta agent per user
- SQLite backend (Letta + app)
- Local development mode

**Multi-User (Future):**
- Agent pool with user mapping
- PostgreSQL backend (required for migrations)
- Letta Cloud or self-hosted Docker

**Agent Lifecycle:**
| Event | Action |
|-------|--------|
| New user | Create Letta agent with base persona |
| Chat session | Resume existing agent (stateful) |
| Deck operation | Tool updates SQLite + core memory block |
| Card search | Archival memory semantic search |
| User returns later | Full history preserved in recall memory |

_Source: [Letta FAQs](https://docs.letta.com/faq)_

### Security Architecture

**Authentication:**
- Letta Cloud: API key authentication
- Self-hosted: Optional auth, can integrate with app auth

**Data Isolation:**
- Each agent is isolated
- Shared memory blocks possible (not needed for MTG)
- Tool access controlled per agent

**Sensitive Data:**
- API keys in environment variables
- No card data is sensitive (public Scryfall data)
- User deck data stays in app SQLite

_Source: [Letta API Overview](https://docs.letta.com/api-reference/overview/)_

### Multi-Agent Patterns (Future Consideration)

Letta supports multi-agent orchestration if needed:

**Potential MTG Use Cases:**
- **Deck Advisor Agent**: Suggests improvements, meta analysis
- **Rules Agent**: MTG rules queries and interactions
- **Collection Agent**: Tracks user's card collection

**Orchestration Options:**
- Direct agent-to-agent calls
- Supervisor agent pattern
- Shared memory blocks between agents

**For MVP:** Single agent is sufficient. Multi-agent adds complexity without clear benefit yet.

_Source: [Letta Multi-Agent](https://docs.letta.com/guides/legacy/workflows-legacy/)_

---

## Implementation Approaches and Technology Adoption

### Migration Strategy: Phased Approach

**Phase 1: Foundation (Parallel Development)**
1. Set up Letta server (Docker or pip)
2. Create base agent with memory blocks
3. Import card data to archival memory
4. Build minimal tool set

**Phase 2: Core Features**
1. Port deck operations to Letta tools
2. Integrate Chainlit with Letta SDK
3. Migrate conversation handling
4. Test memory persistence

**Phase 3: Cutover**
1. Remove PydanticAI agent code
2. Remove CardRepository (cards now in archival memory)
3. Update documentation
4. Production testing

_Source: [Developer Quickstart](https://docs.letta.com/quickstart/)_

### Step 1: Letta Server Setup

**Option A: Docker (Recommended for PostgreSQL)**
```bash
docker run \
  -v ~/.letta/.persist/pgdata:/var/lib/postgresql/data \
  -p 8283:8283 \
  -e OPENAI_API_KEY="your_key" \
  -e ANTHROPIC_API_KEY="your_key" \
  letta/letta:latest
```

**Option B: pip (SQLite, simpler for dev)**
```bash
pip install letta letta-client
letta server --port 8283
```

**SDK Installation:**
```bash
pip install letta-client  # New SDK
# Note: letta package contains legacy LocalClient (deprecated)
```

_Source: [Letta GitHub](https://github.com/letta-ai/letta)_

### Step 2: Agent Creation with Memory Blocks

```python
from letta_client import Letta

# Connect to server
client = Letta(base_url="http://localhost:8283")
# Or: client = Letta(api_key="LETTA_API_KEY") for cloud

# Create agent with MTG-specific memory blocks
agent = client.agents.create(
    name="mtg-deckbuilder",
    model="anthropic/claude-sonnet-4-5",
    embedding="openai/text-embedding-3-small",
    context_window_limit=16000,
    memory_blocks=[
        {
            "label": "persona",
            "description": "The agent's personality and expertise",
            "value": """You are an expert Magic: The Gathering deck-building assistant.
You help users build competitive decks, analyze mana curves, detect synergies,
and provide strategic advice. You have deep knowledge of MTG formats,
card interactions, and meta strategies.""",
            "limit": 2000
        },
        {
            "label": "human",
            "description": "Information about the user's preferences",
            "value": "New user. Preferences unknown.",
            "limit": 2000
        },
        {
            "label": "active_deck",
            "description": "Current deck being built/edited",
            "value": "No active deck.",
            "limit": 5000
        },
        {
            "label": "format_filter",
            "description": "Current format restriction for card searches",
            "value": "No format filter set. All formats allowed.",
            "limit": 500
        }
    ]
)
print(f"Created agent: {agent.id}")
```

_Source: [Building stateful agents](https://docs.letta.com/guides/agents/overview/)_

### Step 3: Card Data Import to Archival Memory

**Option A: File-based Data Source (Recommended for 60k cards)**

```python
import json

# 1. Export cards to JSON file (one-time)
# Format: Each card as a JSON object with embedded metadata
cards_for_letta = []
for card in all_cards:
    cards_for_letta.append({
        "name": card.name,
        "mana_cost": card.mana_cost,
        "type_line": card.type_line,
        "oracle_text": card.oracle_text,
        "colors": card.colors,
        "cmc": card.cmc,
        "keywords": card.keywords,
        "legalities": card.legalities,
        "rarity": card.rarity
    })

with open("mtg_cards.json", "w") as f:
    json.dump(cards_for_letta, f)

# 2. Create folder and upload
folder = client.folders.create(
    name="mtg-card-database",
    embedding="openai/text-embedding-3-small"
)

# Upload file (async processing)
job = client.folders.files.upload(
    folder_id=folder.id,
    file=open("mtg_cards.json", "rb")
)

# Wait for processing to complete
while job.status != "completed":
    job = client.jobs.get(job.id)
    time.sleep(5)

# 3. Attach folder to agent
client.agents.folders.attach(
    agent_id=agent.id,
    folder_id=folder.id
)
```

**Option B: Direct Archival Memory Insert (for smaller datasets)**

```python
# Insert cards directly to archival memory
for card in cards_batch:
    client.agents.archival_memory.insert(
        agent_id=agent.id,
        text=f"""Card: {card.name}
Mana Cost: {card.mana_cost}
Type: {card.type_line}
Oracle Text: {card.oracle_text}
Colors: {', '.join(card.colors)}
CMC: {card.cmc}
Keywords: {', '.join(card.keywords)}
"""
    )
```

**Embedding Model Considerations:**
- `text-embedding-3-small`: Good balance of cost/quality
- Agent and data source MUST use same embedding model
- ~60k cards × ~$0.00002/1k tokens ≈ $1-2 for initial embedding

_Source: [Connecting agents to data sources](https://docs.letta.com/guides/agents/sources), [Archival memory](https://docs.letta.com/guides/ade/archival-memory/)_

### Step 4: Custom Tool Implementation

**Tool Pattern: Function with Google-style Docstring**

```python
# tools/deck_tools.py

def create_deck(name: str, format: str, strategy: str = None) -> str:
    """
    Create a new MTG deck and set it as the active deck.

    This creates a deck in the application database and updates
    the agent's active_deck memory block.

    Args:
        name (str): Name for the new deck (e.g., "Red Deck Wins")
        format (str): MTG format (standard, modern, legacy, commander)
        strategy (str): Optional strategy description (e.g., "aggro", "control")

    Returns:
        str: Confirmation message with deck ID
    """
    import os
    import sqlite3
    import uuid

    deck_id = str(uuid.uuid4())
    db_path = os.environ.get("APP_DATABASE_PATH", "data/decks.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO decks (id, name, format, strategy) VALUES (?, ?, ?, ?)",
        (deck_id, name, format, strategy)
    )
    conn.commit()
    conn.close()

    return f"Created deck '{name}' (ID: {deck_id[:8]}...) for {format} format."


def add_card_to_deck(card_name: str, quantity: int = 1, sideboard: bool = False) -> str:
    """
    Add a card to the active deck.

    Searches archival memory to find the card, then adds it to the
    current deck in the database.

    Args:
        card_name (str): Exact name of the card to add
        quantity (int): Number of copies (default: 1, max: 4 for non-basic lands)
        sideboard (bool): If True, add to sideboard instead of mainboard

    Returns:
        str: Confirmation or error message
    """
    # Implementation calls archival_memory_search internally
    # or uses injected Letta client
    pass
```

**Registering Tools with Agent:**

```python
# Create tool from function
tool = client.tools.create_from_function(
    func=create_deck,
    name="create_deck"
)

# Attach tool to agent
client.agents.tools.attach(
    agent_id=agent.id,
    tool_id=tool.id
)

# Set tool environment variables
client.agents.update(
    agent_id=agent.id,
    tool_exec_environment_variables={
        "APP_DATABASE_PATH": "/app/data/decks.db"
    }
)
```

_Source: [Define and customize tools](https://docs.letta.com/guides/agents/custom-tools)_

### Step 5: Chainlit Integration

```python
# src/ui/app.py (updated for Letta)

import chainlit as cl
from letta_client import Letta

# Initialize Letta client
letta_client = Letta(base_url="http://localhost:8283")

# Agent ID storage (in production, persist per user)
AGENT_ID = "your-agent-id"  # Or create per user


@cl.on_chat_start
async def on_chat_start():
    """Initialize session with Letta agent."""
    # Store agent ID in session
    cl.user_session.set("agent_id", AGENT_ID)

    # Send welcome message
    await cl.Message(
        content="Welcome to the MTG Deck Builder! I can help you build decks, "
                "search for cards, and analyze strategies. What would you like to do?"
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle user messages via Letta agent."""
    agent_id = cl.user_session.get("agent_id")

    # Create streaming message
    msg = cl.Message(content="")
    await msg.send()

    # Stream response from Letta
    full_response = ""
    async for chunk in letta_client.agents.messages.stream(
        agent_id=agent_id,
        messages=[{"role": "user", "content": message.content}]
    ):
        if hasattr(chunk, 'content'):
            full_response += chunk.content
            await msg.stream_token(chunk.content)

    await msg.update()
```

_Source: [Chainlit Docs](https://docs.chainlit.io/), [Letta Python SDK](https://docs.letta.com/api/python/)_

### Development Workflow and Tooling

**Local Development Setup:**
```bash
# Terminal 1: Letta server
letta server --port 8283

# Terminal 2: Chainlit UI
uv run chainlit run src/ui/app.py -w

# Terminal 3: Tests
uv run pytest tests/
```

**ADE for Debugging:**
- Access at `http://localhost:8283` (when running Letta server)
- View agent memory blocks in real-time
- Test tools with mock inputs
- Inspect conversation history

**Testing Strategy:**
| Layer | Test Approach |
|-------|---------------|
| Tools | Unit tests with mocked Letta client |
| Agent | Integration tests against local server |
| Memory | Verify block updates via SDK |
| UI | End-to-end with Chainlit test client |

_Source: [Using the ADE](https://docs.letta.com/guides/ade/usage/)_

### Risk Assessment and Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Card search quality degrades | Medium | High | A/B test archival vs SQL queries; hybrid fallback |
| Embedding costs for 60k cards | Low | Medium | One-time cost ~$2; cache embeddings |
| Letta server reliability | Medium | High | Docker with volume persistence; health checks |
| Tool execution latency | Medium | Medium | Async tools; batch operations where possible |
| Memory block size limits | Low | Medium | Summarize deck in block; full data in SQLite |

### Cost Optimization

**Embedding Costs (One-time):**
- 60k cards × ~500 tokens avg = 30M tokens
- OpenAI text-embedding-3-small: $0.02/1M tokens
- Total: ~$0.60 for initial embedding

**LLM Costs (Per conversation):**
- Claude Sonnet 4.5: $3/$15 per 1M tokens (in/out)
- Typical conversation: ~5k tokens in, ~2k out
- Cost per conversation: ~$0.05

**Storage:**
- Letta SQLite/PostgreSQL: Free (self-hosted)
- Archival memory: Grows with cards + conversation history

_Source: [OpenAI Pricing](https://openai.com/pricing), [Anthropic Pricing](https://anthropic.com/pricing)_

---

## Technical Research Recommendations

### Implementation Roadmap

**Week 1: Foundation**
- [ ] Set up Letta server (Docker)
- [ ] Create MTG agent with memory blocks
- [ ] Export card data to JSON format
- [ ] Import cards to archival memory
- [ ] Verify semantic search works for cards

**Week 2: Core Tools**
- [ ] Port `create_deck` tool
- [ ] Port `add_card_to_deck` tool
- [ ] Port `view_deck` tool
- [ ] Implement `search_cards` (archival memory wrapper)
- [ ] Test tool execution in ADE

**Week 3: Integration**
- [ ] Update Chainlit to use Letta SDK
- [ ] Implement streaming responses
- [ ] Test conversation flow end-to-end
- [ ] Migrate mana curve analysis to tool
- [ ] Migrate synergy detection to tool

**Week 4: Polish & Cutover**
- [ ] Remove PydanticAI agent code
- [ ] Remove CardRepository
- [ ] Update CLAUDE.md documentation
- [ ] Performance testing
- [ ] Production deployment

### Technology Stack Recommendations

| Component | Current | Recommended | Notes |
|-----------|---------|-------------|-------|
| Agent Framework | PydanticAI | Letta | Memory-first architecture |
| Card Storage | SQLite | Letta Archival | Semantic search built-in |
| Deck Storage | SQLite | SQLite (keep) | Structured queries needed |
| UI | Chainlit | Chainlit (keep) | Thin client to Letta API |
| Embedding Model | N/A | text-embedding-3-small | Balance of cost/quality |
| LLM | Claude via Anthropic | Claude via Letta | Same model, different orchestration |

### Success Metrics and KPIs

| Metric | Current Baseline | Target | Measurement |
|--------|-----------------|--------|-------------|
| Card search relevance | SQL exact match | Semantic + exact | User feedback, A/B test |
| Response latency | <2s | <3s (acceptable) | P95 response time |
| Memory persistence | Session-only | Cross-session | Verify recall after restart |
| Conversation context | 10 messages | Unlimited (recall) | Test long conversations |
| Deck operation accuracy | 100% | 100% | Automated tests |

### Skill Development Requirements

**Required Learning:**
- Letta SDK patterns (memory blocks, tools, archival)
- Vector database concepts (embeddings, semantic search)
- Letta ADE for debugging

**Transferable Skills:**
- Tool definition (similar to PydanticAI)
- Chainlit integration (mostly unchanged)
- SQLAlchemy for deck storage (unchanged)

**Resources:**
- [Letta Documentation](https://docs.letta.com/)
- [Letta GitHub Examples](https://github.com/letta-ai/letta)
- [Codecademy Letta Course](https://www.codecademy.com/learn/intro-to-ai-agents-with-letta)

---

## Research Conclusion

**Research Completed:** 2026-01-04

**Primary Finding:** Letta framework is a strong candidate for replacing PydanticAI in the Artificial-Planeswalker project. The archival memory system is well-suited for storing ~60k MTG cards as immutable, semantically-searchable entries.

**Key Recommendations:**
1. **Proceed with migration** - Letta's memory-first architecture aligns well with the MTG assistant use case
2. **Hybrid storage** - Cards in Letta archival memory, decks in SQLite
3. **Phased approach** - Build in parallel, then cut over
4. **Validate hypothesis early** - Test card semantic search quality in Week 1

**Next Steps:**
- Use this research to update PRD and Architecture documents
- Create implementation stories based on the 4-week roadmap
- Begin Phase 1: Foundation setup

---

*Technical Research Report generated via BMad Method workflow*
