# Feature Brief: Companion App for Artificial Planeswalker

**Status:** Draft for BMAD intake
**Author:** Brad
**Date:** 2026-07-22
**Related project:** Artificial Planeswalker (github.com/Sathias23/Artificial-Planeswalker)

---

## 1. Overview

A local, browser-based companion app that runs side by side with the coding agent (Claude Code / Codex). The app renders the current deck with real card art and displays rich, structured output pushed by the agent — card suggestions, proposed swaps, and inclusion tier lists — that would otherwise be limited to plain text in the terminal.

The companion app is a presentation layer only. All deck logic, card data, and analysis remain in the existing MCP server and local Scryfall SQLite database. The app never bypasses or duplicates that logic.

## 2. Problem Statement

Artificial Planeswalker's output is currently consumed entirely as text inside a coding-agent session. Deck building is a visual activity: users want to see card art, scan a decklist at a glance, and compare suggested cards visually. Text output also cannot express structured results (tier lists, swap proposals) in a way that is easy to evaluate. There is no persistent visual surface that stays in sync with the deck as the agent modifies it.

## 3. Goals

- G1: Give the user a live, always-visible view of the active deck, with real card art, that updates when the agent modifies the deck.
- G2: Let the agent push structured, ephemeral content (suggestions, swaps, tier lists) to a dedicated UI panel via explicit tool calls.
- G3: Preserve the local-first, no-API-key philosophy of the project: everything runs on localhost against the existing SQLite database.
- G4: Keep the MCP server stateless and session-scoped; the companion app must degrade gracefully when the other side is not running.

## 4. Non-Goals (Out of Scope for this feature)

- NG1: Editing decks from the UI (read-only in MVP; UI-initiated edits are a future feature).
- NG2: Any LLM calls from the companion app itself.
- NG3: Multi-user, remote access, or cloud sync. The app binds to 127.0.0.1 only.
- NG4: Electron/Tauri packaging in MVP (see Section 9 — web-first, wrap later).
- NG5: Replacing chat output. MCP tools continue to return text results so agent workflows work without the app.

## 5. Users

Single local user: an MTG player running Artificial Planeswalker inside a coding agent, with a browser window snapped beside the terminal.

## 6. Proposed Solution — Architecture Summary

Three processes:

1. **Coding agent + MCP server** (existing). FastMCP over stdio, spawned per session, stateless. Gains a small set of new "companion" tools.
2. **Companion backend** (new). A long-running FastAPI process in the same Python codebase (`uv run artificial-planeswalker companion` or similar console script). Responsibilities:
   - Serve the built React SPA as static files.
   - Expose REST endpoints for deck and card reads (read-only SQLite access).
   - Hold WebSocket connections to the UI and broadcast events.
   - Accept authenticated event POSTs from the MCP server on `/agent/events`.
   - Proxy and disk-cache Scryfall card images.
   - On startup, write a discovery file `~/.artificial-planeswalker/companion.json` containing `{port, token}`.
3. **Browser UI** (new). Vite + React + zustand SPA served from the backend. State is fed by exactly two inputs: REST responses and WebSocket messages. The agent never interacts with the zustand store directly; WebSocket message handlers call `store.setState`.

Primary data flow for agent-pushed content:

```
agent invokes companion MCP tool
  → MCP server reads companion.json for port + token
  → POST JSON payload to http://127.0.0.1:{port}/agent/events
  → backend validates token, broadcasts on WebSocket
  → UI handler routes payload into zustand
  → React renders suggestion panel / tier list / swap view
```

Deck sync flow:

```
agent mutates deck via existing MCP tool
  → MCP server persists change (existing behavior)
  → MCP server fires {type: "deck_changed", deck_id} event POST
  → UI refetches GET /api/deck/{id}
```

Fallback: decks are rows in the SQLite database, not files, so file-watching does not apply. The backend instead polls SQLite's `PRAGMA data_version` (a cheap counter that increments when another connection commits) and emits the same `deck_changed` event when an out-of-band commit is detected (see FR-16).

## 7. Functional Requirements

Priorities: P0 = MVP-blocking, P1 = MVP-desirable, P2 = post-MVP.

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | Backend serves the SPA and REST API on a configurable localhost port (default 8765). | P0 |
| FR-02 | `GET /api/decks` lists decks; `GET /api/deck/{id}` returns a full decklist with card IDs, quantities, and metadata. | P0 |
| FR-03 | `GET /api/cards/{card_id}` returns canonical card data hydrated from the local SQLite database. | P0 |
| FR-04 | `GET /api/card-image/{scryfall_id}?size=` serves card art, fetching from the Scryfall image CDN on first request and disk-caching thereafter. | P0 |
| FR-05 | UI renders the active deck as a card-art grid and a text list view, grouped by card type, with mana curve summary. | P0 |
| FR-06 | Backend exposes `POST /agent/events` (token-authenticated) and relays payloads to all connected UI clients over WebSocket. | P0 |
| FR-07 | New MCP tool `companion_set_active_deck(deck_id)` switches which deck the UI displays. | P0 |
| FR-08 | New MCP tool `companion_show_suggestions(payload)` renders a suggestion list (card ID, reason, optional category) in the agent panel. | P0 |
| FR-09 | New MCP tool `companion_show_swaps(payload)` renders proposed swaps as out-card / in-card pairs with rationale. | P1 |
| FR-10 | New MCP tool `companion_show_tier_list(payload)` renders tiered buckets (e.g., S/A/B/C) of card IDs with optional notes. | P1 |
| FR-11 | Existing deck-mutation tools emit `deck_changed` events after persisting; UI refetches on receipt. | P0 |
| FR-12 | All companion MCP tools degrade gracefully: if the backend is unreachable, return a text result noting the app is not running, never a hard error. | P0 |
| FR-13 | Event payloads reference cards by ID only; the UI hydrates card details and art via FR-03/FR-04. The canonical card ID everywhere (payloads, REST paths, image requests) is the Scryfall printing UUID — `cards.id`, the same value stored in `deck_cards.card_id`. Name→ID resolution stays with the existing MCP tools; agents use the IDs those tools return. | P0 |
| FR-14 | Backend writes and refreshes the discovery file on startup and removes it on clean shutdown. | P0 |
| FR-15 | UI shows connection status (backend reachable / WebSocket live) and the currently active deck. | P1 |
| FR-16 | Backend detects out-of-band deck changes by polling SQLite `PRAGMA data_version` and emits a deck-agnostic `deck_changed`; the UI refetches the active deck. | P2 |
| FR-17 | Clicking a card in any panel shows a detail view (full art, oracle text, prices if present in local data). | P1 |

## 8. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | **Security:** backend binds to 127.0.0.1 only; `/agent/events` requires the shared token from the discovery file; CORS restricted to the app's own origin. WebSocket connections are authenticated via a ticket pattern: the SPA obtains a short-lived ticket from same-origin `GET /api/session` (CORS-protected, so unreadable cross-origin) and presents it on the WS upgrade; upgrades without a valid ticket are rejected — CORS alone does not apply to WebSockets. All endpoints, including the WS upgrade, validate that the `Host` header is `127.0.0.1:{port}` or `localhost:{port}` to block DNS rebinding. Together these mitigate malicious-webpage-to-localhost attacks. |
| NFR-02 | **Concurrency:** SQLite opened in WAL mode; companion backend uses read-only connections (`file:...?mode=ro`). The MCP server remains the sole writer. |
| NFR-03 | **Contract:** event payloads defined as Pydantic models in the shared package, with generated/matching TypeScript types in the UI. The REST layer is the schema boundary; the UI never assumes DB schema. |
| NFR-04 | **Resilience:** UI reconnects WebSocket with backoff; on reconnect it refetches the active deck. Event delivery is fire-and-forget; state is recoverable via refetch ("something changed, refetch" over diff/patch). |
| NFR-05 | **Performance:** deck view renders within 1s for a 100-card Commander deck with warm image cache; event-to-render latency under 250ms on localhost. |
| NFR-06 | **Offline:** after image cache warm-up, the app is fully functional with no network access. |
| NFR-07 | **Tooling parity:** companion code follows existing project standards (ruff, mypy, pytest, pre-commit, CI). Frontend code gets equivalent tooling (eslint, prettier, vitest or similar) run in CI; Node is a dev/CI-only dependency, never required at install or runtime. |

## 9. Key Technical Decisions

- **Web page first, not Electron.** The backend serves the SPA at `localhost:8765`; OS window snapping provides side-by-side. Electron/Tauri would only add always-on-top and a launcher icon, and since it would load the same URL, wrapping later requires no architecture change. Tauri preferred over Electron if/when wrapped.
- **FastAPI for the backend**, sharing the existing Python codebase, DB access layer, and Pydantic models with the FastMCP server.
- **Transport is localhost HTTP + WebSocket**, not file-watching, for agent-pushed content (lower latency, simpler payload semantics). File-watching is reserved for the FR-16 fallback.
- **The zustand store is a client-side concern only.** Suggested slices: `activeDeck`, `agentPanel` (last suggestions/swaps/tier list), `connectionStatus`.
- **Distribution:** console script entry point alongside the MCP server; consider a plugin skill instructing the agent how/when to use companion tools.
- **Frontend packaging:** the built Vite bundle ships as static assets inside the Python package (package data), so a fresh install needs no Node toolchain (satisfies SC-4). CI builds the SPA and drift-checks the committed build output, mirroring the existing `plugin/` tree pattern.

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| User invokes companion tools with the app closed | FR-12 graceful degradation; tools return results as text |
| Port conflict on default port | Backend falls back to an ephemeral port; discovery file is the source of truth, tools never hardcode the port |
| Stale discovery file after crash | Tools validate with a lightweight `GET /health` before POSTing; treat failure as "app not running" |
| SQLite lock contention during bulk data refresh | WAL mode + read-only connections; backend surfaces a "database updating" state if reads fail transiently |
| Scryfall image hotlink etiquette | Disk cache per FR-04 satisfies Scryfall's caching guidance and enables offline use |
| Payload schema drift between Python and TS | Single Pydantic source of truth; generate TS types in CI (e.g., via JSON Schema) |

## 11. Success Criteria

- SC-1: With the app open beside the agent, asking the agent for card suggestions results in a rendered suggestion panel with card art within 250ms of the tool call completing.
- SC-2: Agent-driven deck edits appear in the deck view without user action.
- SC-3: All agent workflows complete successfully with the companion app closed.
- SC-4: A fresh install can launch the companion app with a single `uv` command and no additional configuration.

## 12. Open Questions

- OQ-1: Exact payload schemas for suggestions, swaps, and tier lists (fields, optionality, max sizes) — recommend resolving first in design.
- OQ-2: One generic `companion_display` tool with a `kind` discriminator vs. separate tools per content type (brief assumes separate tools for clearer agent affordances).
- OQ-3: Whether power-assessment output (7-dimension vector, bracket) gets a dedicated panel in MVP or post-MVP.
- OQ-4: Retention of agent-panel history (show only latest push vs. scrollable history of pushes).
- OQ-5: TS type generation tooling choice (datamodel-code-gen / json-schema-to-typescript / manual).

## 13. Suggested Phasing

- **Phase 1 (MVP):** FR-01–FR-08, FR-11–FR-14; NFR-01–NFR-04, NFR-06.
- **Phase 2:** FR-09, FR-10, FR-15, FR-17; NFR-05 hardening.
- **Phase 3:** FR-16, Tauri wrapper, UI-initiated deck edits (new brief), power-assessment panel.
