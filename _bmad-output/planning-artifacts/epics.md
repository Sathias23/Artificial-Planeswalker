---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md
  - _bmad-output/planning-artifacts/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md
project_name: 'Artificial-Planeswalker'
user_name: 'Brad'
date: '2026-06-20'
scope: 'Phase 1 — MCP-server architecture pivot'
status: 'complete'
---

# Artificial-Planeswalker - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for **Artificial-Planeswalker — Phase 1 (MCP-server architecture pivot)**. Requirements are decomposed from the two current design-of-record inputs:

1. **MCP-Server Architecture Pivot — Design** (`docs/superpowers/specs/2026-06-20-mcp-server-architecture-design.md`) — locked decisions D1–D7, the MCP tool catalog (§5), RAG/semantic-search design (§6), the Claude skills suite (§7), testing approach (§8), and repo restructure (§4).
2. **RAG-stack de-risk research** (`…/research/technical-sqlite-vec-fastembed-rag-stack-on-windows-research-2026-06-20.md`) — GO verdict, six design deltas (research §6), the implementation roadmap (research §8), and the validated performance envelope.

> **Project type:** Brownfield restructure of an existing Python modular monolith — **not greenfield**. There is no starter template; Epic 1 Story 1 is the repo restructure + dependency reshape, not a scaffold.
>
> **Scope:** Phase 1 only. Phase 2 (Letta agent as a second MCP client) and Phase 3 (Electron UI) are documented roadmap (spec §9) and each gets its own spec → plan → implementation cycle. They are intentionally excluded from these epics.
>
> **Superseded inputs (excluded):** `prd.md` (PydanticAI→Letta framing) and `architecture.md` (Letta-first, carries its own SUPERSEDED banner). The still-valid MTG domain behavior they described lives unchanged in `src/data` + `src/logic` and is reused behind MCP tools.

## Requirements Inventory

### Functional Requirements

> Derived from MCP spec §5 (tool catalog), §6 (RAG), §7 (skills), §4 (restructure), and decisions D1/D5/D7. Each FR is a capability the Phase-1 system must expose.

**MCP server & transport**
- **FR1:** The system shall provide an MCP server built with FastMCP that wraps the existing `src/data` + `src/logic` domain code and exposes it as MCP tools (D1).
- **FR2:** The MCP server shall run over **stdio** in Phase 1, consumable by Claude Code via a project `.mcp.json`, with the transport kept pluggable so it can switch to HTTP/SSE later without changing tool code (D7).
- **FR3:** Every tool call shall be **stateless / self-contained** — format & games are tool parameters, "active deck" is a client-supplied `deck_id`; no per-session server state, and the old `toggle_auto_feedback` preference is dropped (D5).

**Card tools**
- **FR4:** The server shall expose `lookup_card_by_name` — exact/fuzzy card name lookup.
- **FR5:** The server shall expose `search_cards` — relational/advanced filtering (colors, type, mana value, set, format-legality), with format/games passed as parameters.
- **FR6:** The server shall expose `semantic_search_cards` *(new)* — natural-language vector search, with optional relational filters applied in the **same hybrid query** (e.g. "semantically like Glorybringer, Standard-legal red 4-drops").
- **FR7:** The server shall expose `find_similar_cards` *(new)* — semantic similarity seeded by an existing card's stored vector.

**Deck tools**
- **FR8:** The server shall expose deck-management tools: `list_decks`, `create_deck`, `load_deck`, `delete_deck`, `add_card_to_deck`, `remove_card_from_deck`, operating on SQLite-persisted decks via the existing repositories.

**Analysis tools**
- **FR9:** The server shall expose `analyze_mana_curve` over the existing `src/logic` curve logic.
- **FR10:** The server shall expose `detect_synergies` over the existing `src/logic` synergy logic.
- **FR11:** The server shall expose `validate_deck` — format-legal deck validation, with format/games as parameters.

**Misc tools**
- **FR12:** The server shall expose `report_bug` as a simple tool.

**RAG / semantic-search index**
- **FR13:** The system shall store per-card embeddings in a `sqlite-vec` virtual table (`card_vec`) in the **same** SQLite file as the relational data, keyed by `card_id` so vectors and relational rows are JOIN-aligned (D2).
- **FR14:** Embeddings shall be produced locally by `fastembed` using `bge-small-en-v1.5` (384-dim, ONNX, no PyTorch), over a composite embedded text per card of `name + type_line + mana_cost + oracle_text + keywords` (D2/D6, spec §6).
- **FR15:** The system shall provide `scripts/build_card_embeddings.py` — a one-time batch index build over ~60k cards that is **idempotent** and **incremental** on future Scryfall imports, re-embedding only new/changed cards detected by a content hash.
- **FR16:** The hybrid query path shall embed the query → retrieve top-K nearest vectors (**over-fetch `k`**, with a mandatory `k`/`LIMIT` on every KNN query) → apply relational predicates by JOIN/filter; low-cardinality high-selectivity filters (`mana_value` + the 5 color booleans) are `vec0` metadata columns, multi-valued attributes (format legality, display fields) resolved via JOIN (research §6, integration §A).

**Claude skills suite**
- **FR17:** A Claude skills suite under `.claude/skills/` shall provide an orchestrator/persona skill `magic-deckbuilding` (the analyze→suggest→explain loop: pull list → curve → synergies → legality → ranked swaps with reasons) plus capability skills `synergy-discovery`, `mana-curve-analysis`, and `format-legality` (D4, spec §7).

### NonFunctional Requirements

> Derived from research performance envelope, the §6 design deltas, and the concurrency/lifecycle findings.

- **NFR1 — Query latency:** Semantic search end-to-end shall be **< ~100 ms** at 60k cards (≈3 ms query embed + brute-force KNN <75 ms).
- **NFR2 — Offline / no egress:** No external API calls, API keys, or network egress for card search or embeddings; model and vectors are local (D2/D6).
- **NFR3 — Build performance:** A full 60k index build shall complete in **minutes**, and incremental re-import shall embed only changed cards.
- **NFR4 — Footprint:** Vector storage shall stay modest (~92 MB raw float32 at 60k×384, single file); binary quantization available if needed.
- **NFR5 — Windows / target environment:** The stack shall run on the project's environment — Windows 11, CPython 3.12.13, bundled SQLite 3.50.4 — on stdlib `sqlite3` (extension loading confirmed available); no driver fallback required for Phase 1.
- **NFR6 — Concurrency model:** Tools shall be plain **sync `def`** (FastMCP threadpools them); SQLite shall use **WAL mode with a connection per worker thread**; the embedding model shall be held as a **process-lifetime singleton** (never per-call).
- **NFR7 — Core behavior preserved:** `src/data` and `src/logic` behavior shall remain unchanged; existing `tests/unit` for data/logic shall continue to pass (no regression). `legacy/` is excluded from the active suite.
- **NFR8 — Code quality:** Existing project conventions hold — ruff + mypy clean, snake_case/PascalCase naming, repositories return schemas not ORM objects.
- **NFR9 — RAG recall quality:** Embedding/index recall shall be guarded by a RAG sanity eval (`query → expected card in top-K`); quantized-model recall is the variable to watch (research §10, open-low).
- **NFR10 — Backup/migration ops:** WAL must be checkpointed before file-copy backups; a model/dimension change requires rebuilding the `card_vec` table (treated as a migration).

### Additional Requirements

> Technical/structural requirements from MCP spec §4 and the research's six design deltas (research §6) — these shape Epic 1 and the search core.

- **Repo restructure (spec §4):** Archive `src/agent/` → `legacy/agent/` and `src/ui/` → `legacy/ui/` (reference only, excluded from build & active tests). Keep `src/data/` + `src/logic/` as reusable core. Add `src/mcp_server/` (FastMCP server + transport entry point) and `src/search/` (embedder wrapper + sqlite-vec integration + index builder).
- **Dependency reshape (spec §4):** Move `pydantic-ai` and `chainlit` to an optional `legacy` dependency group; add `mcp`, `sqlite-vec`, `fastembed` to the lean core install. (Bundled `FastMCP` from the `mcp` SDK is the lean default per research.)
- **`ConnectionFactory` port (research delta):** A single connection factory enables `load_extension`, calls `sqlite_vec.load(conn)`, applies WAL, and returns a stdlib `sqlite3` connection by default — with an `apsw` substitution seam kept as a documented contingency (not built in Phase 1). No code may hardcode `sqlite3.connect`.
- **`Embedder` port (research delta):** A fastembed singleton with a **persistent `FASTEMBED_CACHE_DIR`** pinned to a project path (default cache is a volatile Temp dir); exposes `encode(text) -> float32 vector`. Build-time and serve-time share this one port.
- **`card_vec` schema (research delta):** Metadata columns `mana_value` + `color_{w,u,b,r,g}` for pre-filtered KNN; format-legality and display fields resolved via JOIN; note that auxiliary (`+`) columns can be stored but **cannot** be filtered.
- **Core facade (spec §4, pragmatic):** Extract a thin agent-agnostic facade over `src/data`/`src/logic` **only where** archiving `src/agent` reveals agent-specific coupling — incrementally, not big-bang.
- **Testing infra (spec §8):** New `tests/integration/test_mcp_tools.py` drives each tool through an **in-process / in-memory MCP client** (no subprocess); add the RAG sanity-eval fixture; exclude `legacy/` tests from the active suite.

### UX Design Requirements

**N/A for Phase 1.** There is no UX specification and no UI in this phase — Claude Code is the driving client via `.mcp.json`. UI work (the Electron front end from the approved mockup) is Phase 3 roadmap (spec §9) and will be specified separately.

### FR Coverage Map

- **FR1:** Epic 1 — FastMCP server wrapping `src/data`+`src/logic`
- **FR2:** Epic 1 — stdio transport, kept pluggable
- **FR3:** Epic 1 — stateless tools (format/games params, client `deck_id`)
- **FR4:** Epic 1 — `lookup_card_by_name`
- **FR5:** Epic 1 — `search_cards` (relational filters)
- **FR6:** Epic 2 — `semantic_search_cards` (hybrid NL vector search)
- **FR7:** Epic 2 — `find_similar_cards` (seeded by card vector)
- **FR8:** Epic 1 — deck CRUD tools
- **FR9:** Epic 1 — `analyze_mana_curve`
- **FR10:** Epic 1 — `detect_synergies`
- **FR11:** Epic 1 — `validate_deck`
- **FR12:** Epic 1 — `report_bug`
- **FR13:** Epic 2 — `card_vec` virtual table in shared SQLite file
- **FR14:** Epic 2 — fastembed/bge-small composite embedded text
- **FR15:** Epic 2 — `build_card_embeddings.py` (idempotent/incremental)
- **FR16:** Epic 2 — hybrid over-fetch-`k` → JOIN/filter query path
- **FR17:** Epic 3 — Claude skills suite (orchestrator + 3 capability skills)

## Epic List

### Epic 1: MCP Server & Core Tool Surface
Through Claude Code, a player can look up and filter cards, create/manage Standard decks, and analyze curve/synergy/legality — everything the existing agent did, now served by a stateless FastMCP server over stdio. Delivers a connectable, end-to-end MCP server. Enabling work: archive `src/agent`+`src/ui`→`legacy/`, dependency reshape, `ConnectionFactory` (WAL + per-thread + `enable_load_extension`/`sqlite_vec.load`), and the in-memory MCP integration-test harness.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR8, FR9, FR10, FR11, FR12
**NFRs addressed:** NFR5, NFR6, NFR7, NFR8

### Epic 2: Semantic Card Search (RAG)
A player can search by natural-language description (e.g. "hasty flying red dragon that deals direct damage") and find cards similar to a given card, with relational filters composed into the same query. Builds on Epic 1's server. Enabling work: `Embedder` port (fastembed singleton + persistent `FASTEMBED_CACHE_DIR`), `card_vec` schema (metadata cols `mana_value` + 5 color booleans), `build_card_embeddings.py`, the hybrid query path, and a RAG sanity eval.
**FRs covered:** FR6, FR7, FR13, FR14, FR15, FR16
**NFRs addressed:** NFR1, NFR2, NFR3, NFR4, NFR9, NFR10

### Epic 3: Deckbuilding Skills Suite
A player gets the expert "Planeswalker AI" experience — the analyze→suggest→explain loop producing ranked card swaps with reasons — by orchestrating the Epic 1 + Epic 2 tools. The top-of-stack value layer.
**FRs covered:** FR17

## Epic 1: MCP Server & Core Tool Surface

A connectable, stateless FastMCP server (stdio) exposing the existing card/deck/analysis capabilities to Claude Code. **FRs:** FR1–FR5, FR8–FR12 · **NFRs:** NFR5–NFR8. Stories flow forward (restructure → data seam → server + first tools → search → decks → analysis) with no future dependencies.

### Story 1.1: Repository Restructure & Dependency Reshape

As a developer,
I want the repo reorganized around the MCP-server architecture with a lean core dependency set,
So that agent/UI code is archived out of the active build and the new server/search packages have a home.

**Acceptance Criteria:**

**Given** the current `src/agent` and `src/ui` trees
**When** the restructure runs
**Then** they move to `legacy/agent/` and `legacy/ui/`
**And** build/test config excludes `legacy/`

**Given** `pyproject.toml`
**When** dependencies are reshaped
**Then** `pydantic-ai` and `chainlit` move to an optional `legacy` dependency group
**And** `mcp`, `sqlite-vec`, and `fastembed` are added to core dependencies

**Given** the new architecture
**When** packages are scaffolded
**Then** `src/mcp_server/` and `src/search/` exist with `__init__.py` and import cleanly

**Given** a fresh `uv sync` of the core group on Windows
**When** installed
**Then** it succeeds without pulling `pydantic-ai`/`chainlit` (NFR5)
**And** existing `tests/unit` for data/logic still pass (NFR7)

### Story 1.2: SQLite ConnectionFactory with WAL & Extension Loading

As a developer,
I want all SQLite access routed through one connection factory that enables loadable extensions and WAL,
So that tools are driver-agnostic and the vector extension can load without hardcoding `sqlite3.connect`.

**Acceptance Criteria:**

**Given** any data-layer or tool code
**When** it needs a SQLite connection
**Then** it obtains one from `ConnectionFactory`
**And** no module calls `sqlite3.connect` directly

**Given** a new connection
**When** the factory creates it
**Then** `enable_load_extension(True)` is set, `sqlite_vec.load(conn)` is applied, and `vec_version()` returns a value
**And** WAL journal mode is enabled

**Given** concurrent worker threads
**When** tools run
**Then** each thread receives its own connection (NFR6)

**Given** a future non-extension-capable driver
**When** the factory is configured
**Then** an `apsw` substitution seam exists and is documented but defaults to stdlib `sqlite3`

**Given** the factory
**When** unit-tested
**Then** a probe asserts the extension loads and a relational query succeeds

### Story 1.3: FastMCP Server with Card Lookup & Bug Report

As a player using Claude Code,
I want a running MCP server exposing card lookup and bug reporting,
So that I can fetch a card by name conversationally and report issues.

**Acceptance Criteria:**

**Given** the project
**When** the server starts
**Then** a FastMCP server runs over stdio, registered in a project `.mcp.json` consumable by Claude Code (FR1, FR2)

**Given** the transport
**When** configured
**Then** it is selected at the entry point so HTTP/SSE can swap in later without changing tool definitions (FR2)

**Given** `lookup_card_by_name` with an exact or fuzzy name
**When** invoked
**Then** it returns structured card data via existing `src/data` repositories using `ConnectionFactory` (FR4)
**And** a no-match returns a graceful message with no exception surfaced to the client

**Given** `report_bug` with a description
**When** invoked
**Then** it records/acknowledges the report and returns a confirmation (FR12)

**Given** each tool
**When** defined
**Then** it is a plain sync `def` with no per-call session state (FR3, NFR6)

**Given** an in-memory MCP client harness
**When** it drives the tools in-process
**Then** lookup and report_bug assertions pass without a subprocess

### Story 1.4: Advanced Card Search Tool

As a player,
I want to search cards by relational filters with format/games passed per call,
So that I can find Standard-legal cards matching color/type/mana criteria without server-side state.

**Acceptance Criteria:**

**Given** `search_cards` with filters (colors, type, mana value, set, format-legality)
**When** invoked
**Then** it returns matching cards via existing repository queries (FR5)

**Given** format/games as tool parameters
**When** passed
**Then** they filter results
**And** no format state persists on the server between calls (FR3)

**Given** an over-broad result
**When** returned
**Then** results are bounded/limited and the tool communicates that clearly

**Given** invalid filter values
**When** invoked
**Then** the tool returns a clear validation message rather than raising

**Given** the in-memory harness
**When** filter combinations are exercised
**Then** integration assertions pass

### Story 1.5: Deck Management Tools

As a player,
I want to create, list, load, delete decks and add/remove cards via the MCP server,
So that I can build and persist Standard decks, with the active deck tracked by my client.

**Acceptance Criteria:**

**Given** `create_deck`/`list_decks`/`load_deck`/`delete_deck`
**When** invoked
**Then** they operate via the existing `DeckRepository` and return confirmation/results (FR8)

**Given** `add_card_to_deck`/`remove_card_from_deck` with a `deck_id` and card
**When** invoked
**Then** the deck updates and the change persists to SQLite (FR8)

**Given** statelessness
**When** deck tools run
**Then** the active deck is the client-supplied `deck_id` with no server-side "active deck" (FR3)

**Given** a missing deck or card
**When** a deck tool is invoked
**Then** it returns a graceful error message

**Given** WAL with single-writer deck CRUD
**When** concurrent reads occur
**Then** writes operate correctly (NFR6)

**Given** the in-memory harness
**When** deck CRUD runs end-to-end
**Then** assertions pass

### Story 1.6: Deck Analysis Tools

As a player,
I want mana-curve, synergy, and legality analysis tools,
So that I can evaluate a deck's curve, internal synergies, and format legality on demand.

**Acceptance Criteria:**

**Given** `analyze_mana_curve` for a deck
**When** invoked
**Then** it returns the curve distribution via existing `src/logic` curve logic (FR9)

**Given** `detect_synergies` for a deck
**When** invoked
**Then** it returns detected synergies via existing `src/logic` synergy logic (FR10)

**Given** `validate_deck` with format/games parameters
**When** invoked
**Then** it returns legality/validation results such as 60+ cards and ≤4 copies (FR11, FR3)

**Given** an invalid or empty deck
**When** any analysis tool runs
**Then** it returns a clear message rather than raising

**Given** existing `src/logic`
**When** wrapped by tools
**Then** logic-layer behavior is unchanged and its unit tests still pass (NFR7)

**Given** the in-memory harness
**When** the three tools are driven
**Then** integration assertions pass

## Epic 2: Semantic Card Search (RAG)

Natural-language and find-similar card search over `sqlite-vec`, with relational filters composed into one hybrid query. **FRs:** FR6, FR7, FR13–FR16 · **NFRs:** NFR1–NFR4, NFR9, NFR10. Builds on Epic 1's server + ConnectionFactory; stories flow embedder → schema → builder → semantic tool → similar tool → eval.

### Story 2.1: Embedder Port (fastembed singleton + persistent cache)

As a developer,
I want an `Embedder` port backed by a fastembed singleton with a persistent cache,
So that build-time and serve-time share one fast, offline embedding path.

**Acceptance Criteria:**

**Given** the `Embedder` port
**When** `encode(text)` is called
**Then** it returns a 384-dim float32 vector from `bge-small-en-v1.5` via fastembed (FR14)

**Given** the embedding model
**When** first loaded
**Then** it is held as a process-lifetime singleton and reused across calls, never re-instantiated per call (NFR6)

**Given** the model cache
**When** configured
**Then** `FASTEMBED_CACHE_DIR` is pinned to a persistent project path (not a volatile Temp dir)
**And** after first download the model loads offline (NFR2)

**Given** a batch of texts
**When** `encode` is called in batch
**Then** it returns vectors efficiently for index building

**Given** the port
**When** unit-tested
**Then** encoding a known string yields a stable 384-dim float32 vector

### Story 2.2: card_vec Schema with Metadata Columns

As a developer,
I want a `card_vec` virtual table in the shared SQLite file with filterable metadata columns,
So that vectors live alongside relational rows and support pre-filtered KNN.

**Acceptance Criteria:**

**Given** the SQLite file
**When** the schema migration runs
**Then** a `vec0` virtual table `card_vec` exists keyed by `card_id` (rowid = card_id), JOIN-aligned with the relational `cards` table (FR13)

**Given** `card_vec`
**When** declared
**Then** it has a 384-dim embedding column plus metadata columns `mana_value` and `color_{w,u,b,r,g}` for pre-filtered KNN

**Given** the metadata-vs-JOIN design
**When** the schema is created
**Then** format-legality and display fields resolve via JOIN (not metadata columns)
**And** auxiliary (`+`) columns are not relied on for filtering

**Given** a model/dimension change
**When** it occurs
**Then** the documented migration path is to rebuild `card_vec` (NFR10)

**Given** the schema
**When** unit-tested
**Then** a vector insert plus a metadata-filtered KNN query returns expected rows

### Story 2.3: Card Embedding Index Builder (idempotent & incremental)

As a developer,
I want `scripts/build_card_embeddings.py` to embed ~60k cards idempotently and incrementally,
So that the index builds once in minutes and future imports only re-embed changed cards.

**Acceptance Criteria:**

**Given** ~60k cards
**When** the builder runs the first time
**Then** it composes per-card text (`name + type_line + mana_cost + oracle_text + keywords`), batch-embeds, serializes to float32, and inserts into `card_vec` keyed by `card_id` (FR14, FR15)

**Given** a content hash of the composite text stored per card
**When** the builder re-runs
**Then** only new or changed cards are re-embedded (FR15)

**Given** the full build
**When** it completes
**Then** it finishes in minutes and logs progress/counts
**And** on-disk vector footprint is in the expected ~92 MB raw range (NFR3, NFR4)

**Given** an interrupted or re-run build
**When** executed again
**Then** it converges to a complete index with no duplicate vectors

**Given** the builder
**When** run via a uv command
**Then** it is invocable as a script

### Story 2.4: semantic_search_cards Tool (hybrid query)

As a player,
I want natural-language card search with optional relational filters in one call,
So that I can ask for "Standard-legal red 4-drops like Glorybringer" and get relevant hits fast.

**Acceptance Criteria:**

**Given** `semantic_search_cards` with a natural-language query
**When** invoked
**Then** it embeds the query via the `Embedder` and returns top-K nearest cards (FR6)

**Given** a KNN query
**When** executed
**Then** it carries a mandatory `k`/`LIMIT` and over-fetches `k` before relational filtering (FR16)

**Given** optional relational filters (format-legal, colors, mana value range)
**When** passed
**Then** they apply via JOIN/metadata pre-filter in the same query path, serving the "semantically like Glorybringer, Standard-legal red 4-drops" example (FR16)

**Given** 60k scale
**When** a query runs
**Then** end-to-end completes in under ~100ms (NFR1)

**Given** format/games filters
**When** passed
**Then** they are tool parameters with no server-side state (FR3)

**Given** the in-memory harness
**When** semantic search is driven
**Then** integration assertions pass

### Story 2.5: find_similar_cards Tool

As a player,
I want to find cards similar to a given card,
So that I can discover alternatives and synergy pieces from a seed card.

**Acceptance Criteria:**

**Given** `find_similar_cards` with a seed card identifier
**When** invoked
**Then** it uses the seed card's stored vector to retrieve top-K nearest cards via the same hybrid path (FR7)

**Given** the seed is its own nearest neighbor
**When** results return
**Then** the seed is excluded or clearly marked so results are useful alternatives

**Given** optional relational filters
**When** passed
**Then** they compose with the similarity query (over-fetch `k`, JOIN/filter)

**Given** a seed card not in the index
**When** invoked
**Then** it returns a graceful message

**Given** the in-memory harness
**When** find_similar is driven
**Then** integration assertions pass

### Story 2.6: RAG Sanity Eval

As a developer,
I want a small RAG sanity eval of query→expected-card-in-top-K checks,
So that embedding/index regressions are caught and recall is monitored.

**Acceptance Criteria:**

**Given** a fixture of MTG queries with expected top-K card memberships
**When** the eval runs
**Then** it asserts each expected card appears in the top-K for its query (NFR9)

**Given** the eval
**When** run in the test suite
**Then** it executes through the same hybrid path used in production against a built or fixture index

**Given** the quantized model's recall as the watch variable
**When** the eval reports below target hit-rate
**Then** it fails or flags so the composite-text weighting can be tuned (NFR9)

**Given** the eval
**When** integrated
**Then** it is part of the active suite and `legacy/` tests remain excluded

## Epic 3: Deckbuilding Skills Suite

The expert "Planeswalker AI" experience — judgment and cross-tool workflows that turn the Epic 1+2 tools into ranked, explained recommendations. **FRs:** FR17. These are `.claude/skills/` content encoding judgment, not tool restatements (spec §7). The orchestrator (3.1) functions standalone by calling tools directly; the capability skills (3.2–3.4) are independent of one another.

### Story 3.1: magic-deckbuilding Orchestrator Skill

As a player,
I want a "Planeswalker AI" orchestrator skill that runs the analyze→suggest→explain loop,
So that I get ranked card swaps with reasons rather than raw tool output.

**Acceptance Criteria:**

**Given** `.claude/skills/magic-deckbuilding/`
**When** the skill is present
**Then** it defines the Planeswalker AI persona and the core loop: pull list → mana curve → synergies → legality → ranked swaps with reasons (FR17)

**Given** a deck
**When** the orchestrator runs
**Then** it invokes the Epic 1+2 tools (`search_cards`/`semantic_search_cards`, `analyze_mana_curve`, `detect_synergies`, `validate_deck`) in order and synthesizes a recommendation

**Given** swap suggestions
**When** produced
**Then** each includes a reason
**And** they are ranked

**Given** the skill metadata
**When** loaded
**Then** its description triggers for deckbuilding requests
**And** it references the capability skills

### Story 3.2: synergy-discovery Skill

As a player,
I want a synergy-discovery skill,
So that I can find and understand card interactions for my deck or strategy.

**Acceptance Criteria:**

**Given** `.claude/skills/synergy-discovery/`
**When** invoked
**Then** it combines `semantic_search_cards` + `detect_synergies` to surface and explain interactions (FR17)

**Given** a strategy or seed cards
**When** run
**Then** it returns candidate cards with explanations of why they synergize

**Given** the results
**When** presented
**Then** they are format-aware (format passed as parameters) and bounded to avoid overwhelming the player

### Story 3.3: mana-curve-analysis Skill

As a player,
I want a mana-curve-analysis skill,
So that I understand whether my curve is healthy and how to fix it.

**Acceptance Criteria:**

**Given** `.claude/skills/mana-curve-analysis/`
**When** invoked
**Then** it explains how to read a curve, what "too top-heavy" means, and gives contextual feedback (FR17)

**Given** a deck
**When** run
**Then** it calls `analyze_mana_curve` and interprets the result into actionable guidance

**Given** repeated card additions
**When** feedback is given
**Then** it is throttled and contextual, not spammy

### Story 3.4: format-legality Skill

As a player,
I want a format-legality skill,
So that I get format rules, validation, and sideboard guidance.

**Acceptance Criteria:**

**Given** `.claude/skills/format-legality/`
**When** invoked
**Then** it encodes format rules and uses `validate_deck` for legality checks and sideboard guidance (FR17)

**Given** a deck and format
**When** run
**Then** it reports legality issues (deck size, copy limits, illegal cards) with how to comply

**Given** varying format/games
**When** run
**Then** they are passed as parameters (statelessness, FR3)
