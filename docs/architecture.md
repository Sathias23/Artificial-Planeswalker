# MCP-Server Architecture Pivot — Design

**Date:** 2026-06-20
**Branch:** `feat/mcp-server-architecture`
**Status:** Approved (Phase 1 design)
**Supersedes planning direction of:** the Letta-first migration (commit `2b85a71`). Letta is retained, but as a *later* consumer of the MCP server rather than the foundation.

---

> **Public-release note (2026-06-28):** the `legacy/` tree referenced below (the archived PydanticAI agent + Chainlit UI) has since been **removed from the public repository**; it remains in git history. The `legacy/…` references that follow describe the original Phase-1 restructure for context.

## 1. Summary

Artificial-Planeswalker is an MTG deck-building AI assistant. Today it is a 4-layer Python modular monolith: PydanticAI agent + Chainlit UI + business logic + SQLite (60k Scryfall cards & decks).

This pivot reorganizes the project around a single principle:

> **The MCP server is the single source of truth for what the assistant can *do*. Tools and data live there; agents and UIs are interchangeable clients of it.**

The existing domain logic (`src/data`, `src/logic`) is **reused** behind MCP tools. The agent and UI layers (`src/agent`, `src/ui`) are **archived**, because their roles are taken over by swappable clients: Claude Code now, a resurrected Letta agent later, and an Electron UI later still.

### The decoupled architecture

```
                 ┌─────────────────────────────┐
   Phase 1 →     │   Claude Code (agent now)    │
                 ├─────────────────────────────┤
   Phase 2 →     │   Letta agent (resurrected)  │
                 ├─────────────────────────────┤
   Phase 3 →     │   Electron UI (mockup)       │
                 └──────────────┬──────────────┘
                                │  MCP protocol (stdio → HTTP/SSE later)
                 ┌──────────────▼──────────────┐
                 │      MCP Server (tools)      │  card lookup/search, deck CRUD,
                 │   + matching Claude skills   │  mana curve, synergy, validate, RAG
                 └──────────────┬──────────────┘
                                │
                 ┌──────────────▼──────────────┐
                 │   SQLite: relational + RAG   │  one file: 60k cards + decks
                 │   (sqlite-vec vectors)       │  relational filters JOIN vector hits
                 └─────────────────────────────┘
```

---

## 2. Scope

### In scope (Phase 1 — this spec)

1. **MCP server** (Python / FastMCP) wrapping the existing domain logic.
2. **RAG / semantic search** added to SQLite via `sqlite-vec` + local embeddings, exposed as MCP tools.
3. **Claude skills suite** encoding the MTG expertise and multi-tool workflows.
4. **Repo restructure**: archive `src/agent` + `src/ui` to `legacy/`; keep `src/data` + `src/logic` as reusable core; add `src/mcp_server` + `src/search`.
5. **Claude Code** as the driving client (via project `.mcp.json`).

### Out of scope (documented as roadmap in §9)

- **Phase 2** — Letta agent resurrected as a second MCP client.
- **Phase 3** — Electron front end per the approved mockup.

Each later phase gets its own spec → plan → implementation cycle.

---

## 3. Decisions Locked In

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Server language / reuse | **Python + FastMCP, reuse `src/data` + `src/logic`** | Keeps all tested domain logic; Letta (Python) integrates naturally later. |
| D2 | RAG stack | **`sqlite-vec` + local `bge-small-en-v1.5` (via `fastembed`)** | One SQLite file; offline; no API key/cost; relational filters compose with vector hits in one query. |
| D3 | Existing agent + UI | **Archive to `legacy/`** | Superseded by Claude Code / Electron; kept as wiring/prompt reference, out of active build. |
| D4 | Skills granularity | **Focused suite** (orchestrator + a few capability skills) | Skills encode judgment & cross-tool workflows, not tool restatements. |
| D5 | Server statefulness | **Stateless per call** — format/games are tool params; "active deck" tracked by the client | Clean for multiple consumers and HTTP transport later. |
| D6 | Embedding runtime | **`fastembed` (ONNX)** over sentence-transformers/PyTorch | Lighter dependency footprint, fast CPU inference, ships the model. |
| D7 | Phase-1 transport | **stdio**, kept pluggable | What Claude Code consumes; FastMCP swaps to HTTP/SSE later without touching tools. |

---

## 4. Repository Restructure

| Action | From → To | Notes |
|--------|-----------|-------|
| Archive agent | `src/agent/` → `legacy/agent/` | Reference only; excluded from build & active tests. |
| Archive UI | `src/ui/` → `legacy/ui/` | Reference only; excluded from build & active tests. |
| Keep as core | `src/data/`, `src/logic/` | Reused behind MCP tools, unchanged behavior. |
| New | `src/mcp_server/` | FastMCP server: tool definitions + transport entry point. |
| New | `src/search/` | Embedding model wrapper + `sqlite-vec` integration + index builder. |
| Deps | move `pydantic-ai`, `chainlit` to optional `legacy` dependency group; add `mcp`, `sqlite-vec`, `fastembed` | Lean core install; legacy installable on demand. |

**Core facade (pragmatic, not big-bang):** `src/data` + `src/logic` get a thin agent-agnostic facade *only where* they currently reach into agent-specific types. We extract as we hit coupling, not preemptively.

---

## 5. MCP Server & Tool Catalog

Built with **FastMCP**, importing core repositories/validators directly. Tools port 1:1 from `src/agent/tools`, plus the two new search tools.

**Cards**
- `lookup_card_by_name` — exact/fuzzy name lookup.
- `search_cards` — relational/advanced filters (colors, type, MV, set, format-legality…).
- `semantic_search_cards` *(new)* — natural-language vector search; optional relational filters applied in the same query (hybrid).
- `find_similar_cards` *(new)* — semantic similarity seeded by an existing card's vector.

**Decks**
- `list_decks`, `create_deck`, `load_deck`, `delete_deck`, `add_card_to_deck`, `remove_card_from_deck`.

**Analysis**
- `analyze_mana_curve`, `detect_synergies`, `validate_deck`.

### Statelessness (D5)

The old per-session state is removed:
- **Format / games filter** → become **parameters** on `search_cards`, `semantic_search_cards`, and `validate_deck`.
- **Active deck** → tracked by the *client* (Claude Code conversation now; Electron later), passed as a `deck_id` where needed.
- **`toggle_auto_feedback`** (UI preference) → dropped.

Each tool call is self-contained, which is what makes multiple concurrent clients and HTTP transport clean.

---

## 6. RAG / Semantic Search

- **Storage:** a `sqlite-vec` virtual table (`card_vec`) in the *same* SQLite file as the relational data, keyed by `card_id`. Relational rows and vectors are JOIN-able.
- **Embeddings:** `bge-small-en-v1.5` (384-dim) via **`fastembed`** (ONNX runtime — no PyTorch). Loaded locally; ~millisecond query embedding on CPU.
- **Embedded text per card:** composite of `name + type_line + mana_cost + oracle_text + keywords`.
- **Index build:** `scripts/build_card_embeddings.py` — one-time batch over ~60k cards, **idempotent**, and **incremental** on future Scryfall imports (embeds only new/changed cards, detected by a content hash).
- **Hybrid query path:** `semantic_search_cards` embeds the query → top-K nearest vectors → optional JOIN against relational predicates (format-legal, colors, MV range). Example served by one call: *"semantically like Glorybringer, Standard-legal red 4-drops."* `find_similar_cards` uses the same path seeded by a card's stored vector.

---

## 7. Claude Skills Suite

Location: `.claude/skills/`. Each skill encodes judgment and cross-tool workflows — not tool signatures.

- **`magic-deckbuilding`** *(orchestrator / persona)* — the "Planeswalker AI" identity and the core analyze→suggest→explain loop from the mockup: pull list → mana curve → synergies → legality → propose **ranked swaps with reasons**.
- **`synergy-discovery`** — combine `semantic_search_cards` + `detect_synergies` to find and explain interactions.
- **`mana-curve-analysis`** — how to read a curve, what "too top-heavy" means, contextual/throttled feedback.
- **`format-legality`** — format rules, validation, sideboard guidance.

The exact list is refinable during build; this is the starting shape.

---

## 8. Testing

- **Existing `tests/unit`** for `data`/`logic` stay valid (core behavior unchanged).
- **New `tests/integration/test_mcp_tools.py`** — drive each tool through an in-process MCP client; assert results and error handling.
- **RAG sanity eval** — a small fixture of `query → expected card appears in top-K` checks to guard regressions in the embedding/index path.
- **`legacy/`** tests were excluded from the active suite and have since been removed for public release (see the note at the top; preserved in git history).

---

## 9. Roadmap (documented, not built in Phase 1)

### Phase 2 — Letta agent (second client)

Resurrect the Letta agent as a **client of the MCP server** (Letta supports MCP tool servers), not as the data foundation. Core-memory blocks hold `persona` / `human` / `active_deck`. Crucially, Letta calls `semantic_search_cards` instead of managing its own archival memory — so **search behavior is identical** across Claude Code, Letta, and Electron. This phase likely flips the MCP transport to HTTP/SSE (already anticipated by D7).

### Phase 3 — Electron front end

The UI from the approved mockup: deck columns grouped by mana value, mana-curve chart, color pie, and a chat panel with **Apply to deck / Why?** actions. It talks to either the Letta agent (REST) or a thin backend that orchestrates the MCP server. Visual reference: dark theme, accent-on-color, card-hover detail panel, suggested-change cards with apply/explain affordances.

---

## 10. Open Questions / Risks

- **`sqlite-vec` packaging on Windows** — confirm the extension loads cleanly with the project's SQLite build under `uv`; have a fallback (bundled binary vs. pip wheel) ready.
- **Embedding text composition** — `oracle_text` heavy cards vs. vanilla creatures may need weighting; validate with the RAG sanity eval and tune the composite if recall is poor.
- **Core/agent coupling surface** — the exact extent of the `core` facade (D1 drift toward option C) is unknown until we move `src/agent` and see what `src/data`/`src/logic` import. Handle incrementally.
- **Index build time/footprint** — 60k embeddings at 384-dim is modest, but confirm batch throughput and on-disk size are acceptable for the one-time build and incremental updates.
