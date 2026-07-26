---
title: Companion App — Artificial Planeswalker
status: final
created: 2026-07-22
updated: 2026-07-22
---

# Companion App — PRD

## 1. Overview

Artificial Planeswalker is an MCP-server toolkit for Magic: The Gathering deckbuilding —
a local Scryfall SQLite snapshot, RAG search, and deck tools consumed through a coding
agent (Claude Code / Codex). This PRD adds the **companion app**: a local, browser-based
visual surface that runs beside the agent session. It renders the active deck with real
card art and displays rich, structured content the agent pushes via explicit MCP tool
calls — card suggestions, proposed swaps, and tier lists — that today are flattened into
terminal text.

The companion app is a **presentation layer only**. All deck logic, card data, and
analysis stay in the existing MCP server and SQLite database; the app never bypasses or
duplicates them. It ships as part of the public release once quality meets the bar —
release-grade docs, install polish, and CI parity apply from the start.

## 2. Problem Statement

Deck building is a visual activity. Users want to see card art, scan a decklist at a
glance, and compare suggested cards side by side — but Artificial Planeswalker's output
is consumed entirely as text in a coding-agent session. Text cannot express structured
results (tier lists, swap proposals) in a way that is easy to evaluate, and there is no
persistent visual surface that stays in sync with the deck as the agent modifies it.

## 3. Users & Journey

A single local user: an MTG player running Artificial Planeswalker inside a coding
agent, with a browser window snapped beside the terminal. No multi-user, remote, or
collaborative scenarios.

**UJ-1 — Brewing session.** Brad is tuning a Commander brew. He starts the companion
backend once (`uv run artificial-planeswalker companion`), opens `localhost:8765`, and
snaps it beside his terminal. He asks the agent to load the deck; the deck view fills
with full card faces, grouped by type, mana curve along the edge. He asks "what would
make the token engine more resilient?" — the agent calls
`companion_show_suggestions`, and a suggestion panel slides in with six cards,
art-forward, each with a one-line reason. He clicks one to read its full oracle text in
the detail view, decides against two others, and tells the agent to add the one he
liked. The deck view updates by itself within a second. The browser is read-only glass:
his only clicks are to inspect — flip a card, open the detail view — while everything that
changes state flows through the agent. The agent drives, the app shows.

## 4. Goals

- G1: Give the user a live, always-visible view of the active deck — with real card
  art — that updates when the agent modifies the deck.
- G2: Let the agent push structured, ephemeral content (suggestions, swaps, tier lists)
  to a dedicated UI panel via explicit tool calls.
- G3: Preserve the local-first, no-API-key philosophy: everything runs on localhost
  against the existing SQLite database.
- G4: Keep the MCP server stateless and session-scoped; the companion app must degrade
  gracefully when the other side is not running.
- G5: Look *good* — the visual experience is the point of the feature, not a byproduct.
  Dark, game-adjacent aesthetic; card art forward.

## 5. Non-Goals

- NG1: Editing decks from the UI (read-only in MVP; UI-initiated edits are a future
  feature with its own brief).
- NG2: LLM calls from the companion app itself.
- NG3: Multi-user, remote access, or cloud sync. The app binds to 127.0.0.1 only.
- NG4: Electron/Tauri packaging in MVP (web-first; wrapping later requires no
  architecture change).
- NG5: Replacing chat output. The agent presents results in chat as usual whether or
  not the app is running; companion tools add a visual channel, never replace the
  conversational one.

## 6. Architecture Context

Three processes (mechanism detail in the addendum and downstream architecture):

1. **Coding agent + MCP server** (existing) — FastMCP over stdio, stateless, spawned
   per session. Gains a small set of new companion tools.
2. **Companion backend** (new) — a long-running FastAPI process in the same Python
   codebase. Serves the built SPA, exposes read-only REST for decks/cards, proxies and
   disk-caches card images, holds WebSocket connections to the UI, and accepts
   token-authenticated event POSTs from the MCP server. Writes a discovery file
   (`~/.artificial-planeswalker/companion.json`) so tools can find it.
3. **Browser UI** (new) — Vite + React SPA served by the backend. State comes from
   exactly two inputs: REST responses and WebSocket messages.

Agent-pushed content flows: MCP tool → discovery file → authenticated POST
`/agent/events` → WebSocket broadcast → UI renders. Deck sync flows: existing mutation
tool persists → fires `deck_changed` → UI refetches the deck.

## 7. Functional Requirements

Priorities: P0 = MVP-blocking, P1 = MVP-desirable, P2 = post-MVP.

### Feature A — Backend service & lifecycle

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | Backend serves the SPA and REST API on a configurable localhost port (default 8765), falling back to an ephemeral port on conflict. Exactly one instance runs at a time: on startup, if the discovery file points to a live instance (identity-verified, see FR-14), the new process exits with an "already running" message; a stale or dead entry is taken over. | P0 |
| FR-14 | Backend writes and refreshes the discovery file `{port, token, instance_id}` on startup and removes it on clean shutdown. `GET /health` echoes the `instance_id` so callers can verify they are talking to this app instance — not a foreign process squatting on a recycled port — before sending the token. | P0 |
| FR-22 | Backend starts successfully when the SQLite database is missing or not yet initialized (fresh install — the database is built by the MCP side on first run): it serves the SPA and the UI shows a "database not initialized" state with guidance, never an error page. | P0 |

### Feature B — Deck view

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-02 | `GET /api/decks` lists decks; `GET /api/deck/{id}` returns a full decklist with card IDs, quantities, and metadata (name, format, description — matching `load_deck` output). | P0 |
| FR-03 | `GET /api/cards/{card_id}` returns canonical card data hydrated from the local SQLite database. | P0 |
| FR-05 | UI renders the active deck as a card-art grid and a text list view, grouped by card type, with a mana curve summary. Double-faced cards group and curve by their front face. | P0 |
| FR-17 | Clicking a card in any panel opens a detail view: full-size card face, oracle text, prices if present in local data. | P0 |
| FR-19 | The card grid displays **full card faces** (frame, name, text box), not art crops, at the `normal` image size; the detail view (FR-17) uses `large`/`png`. Double-faced cards show the front face with a dedicated flip control — distinct from clicking the card, which opens the detail view (FR-17). Cards without image data render a named placeholder. | P0 |

### Feature C — Card imagery

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-04 | `GET /api/card-image/{scryfall_id}?size=&face=` serves card images, fetching from the Scryfall image CDN on first request and disk-caching thereafter. Sizes resolve from the locally stored `image_uris`; face handling is driven by the card's Scryfall `layout` (faces exist only where per-face `image_uris` exist — split/adventure/flip layouts serve their single image; meld backs are separate printings). CDN fetches are concurrency-capped and rate-spaced per Scryfall guidance; fetch failures return a defined placeholder response and are negative-cached with backoff so an unreachable CDN never causes request storms. Cards with no image data get a stable placeholder response. | P0 |

### Feature D — Agent panel (pushed content)

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-06 | Backend exposes `POST /agent/events` (token-authenticated) and relays payloads to all connected UI clients over WebSocket. The response reports the connected-client count, so tools can tell the user whether the content was actually displayed. | P0 |
| FR-13 | Event payloads reference cards by ID only; the UI hydrates details and art via FR-03/FR-04. The canonical ID everywhere is the Scryfall printing UUID (`cards.id`, the value in `deck_cards.card_id`). Name→ID resolution stays with existing MCP tools; agents use the IDs those tools return. | P0 |
| FR-08 | MCP tool `companion_show_suggestions(payload)` renders a suggestion list (card ID, reason, optional category) in the agent panel. Each new push replaces the panel's current content (FR-18 adds history). | P0 |
| FR-09 | MCP tool `companion_show_swaps(payload)` renders proposed swaps as out-card / in-card pairs with rationale. | P1 |
| FR-10 | MCP tool `companion_show_tier_list(payload)` renders tiered buckets (e.g. S/A/B/C) of card IDs with optional notes. | P1 |
| FR-18 | A lightweight session history (capped, e.g. last 20 pushes, labeled by kind and time) lets the user revisit earlier pushes; revisited entries re-hydrate against current card data. History is in-browser only and clears on refresh. | P1 |
| FR-23 | MCP tool `companion_show_groups(payload)` renders titled groups of cards, each with a prose rationale and a card-ID list — the agent's answer to "show me the X in this deck" (one-drops that carry the curve, answers to a specific threat, budget substitutes, sideboard cards for a matchup). Distinct from FR-08 suggestions (flat list, one-line reasons, no grouping) in that a group carries a title and a paragraph of reasoning over an arbitrary card set, including cards *not* in the active deck. Added 2026-07-25 from the UX design; consistent with the OQ-2 ruling that each push kind gets its own tool rather than a generic `companion_display`. | P1 |

### Feature E — Deck sync & agent control

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-07 | MCP tool `companion_set_active_deck(deck_id)` switches which deck the UI displays. The companion backend owns the active-deck ID (in memory); before any set-active call — and after a backend restart — the UI shows a defined no-active-deck state listing available decks. | P0 |
| FR-11 | Existing deck-mutation tools emit `deck_changed` events after persisting; deletion counts as a mutation. The event carries the deck ID; the UI refetches when it matches the active deck (and may refresh the deck list regardless). A refetch that 404s (deck deleted) clears to the no-active-deck state. | P0 |
| FR-16 | Backend detects out-of-band deck changes by polling SQLite `PRAGMA data_version` and emits a deck-agnostic `deck_changed`; the UI refetches the active deck. | P2 |

### Feature F — Resilience & status

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-12 | All companion MCP tools degrade gracefully: on any failure — backend unreachable, auth rejection, or any non-success response — the tool returns a text result describing the outcome ("app not running", "app running but no browser tab connected", …), never a hard error. Tools re-read the discovery file on auth failure and retry once, so a restarted backend (new token) is picked up transparently mid-session. The agent already holds the pushed content and presents it in chat as usual, so nothing is lost and no payload echo is needed. | P0 |
| FR-15 | UI shows connection status (backend reachable / WebSocket live) and the active deck. | P1 |

### Feature G — Visual experience

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-20 | The UI ships a dark, game-adjacent theme: card art forward, subtle motion on updates (new push, deck change), evoking Arena/Untapped.gg rather than utilitarian dashboards — never imitative of WotC trade dress. Motion respects `prefers-reduced-motion` and text meets a baseline contrast floor. The concrete direction (reference screenshots, comparison set, motion inventory) is set by the UX spec produced before Phase-1 implementation; acceptance is the SC-5 gate against that spec. | P0 |
| FR-21 | Deck power assessment (7-dimension vector + bracket from `assess_deck_power`) gets a dedicated visual panel. | P2 |

## 8. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | **Security:** backend binds to 127.0.0.1 only; `/agent/events` requires the shared token from the discovery file; CORS restricted to the app's own origin. WebSocket upgrades are authenticated via a short-lived ticket obtained from same-origin `GET /api/session` (CORS alone does not protect WebSockets); upgrades without a valid ticket are rejected. All endpoints, including the WS upgrade, validate the `Host` header (`127.0.0.1:{port}` / `localhost:{port}`) to block DNS rebinding. Together these mitigate malicious-webpage-to-localhost attacks. |
| NFR-02 | **Concurrency:** SQLite in WAL mode; the companion backend uses read-only connections (`file:...?mode=ro`). The MCP server remains the sole writer. |
| NFR-03 | **Contract:** event payloads are Pydantic models in the shared package with generated/matching TypeScript types in the UI. The REST layer is the schema boundary; the UI never assumes DB schema. |
| NFR-04 | **Resilience:** UI reconnects WebSocket with backoff and refetches the active deck on reconnect. Event delivery is fire-and-forget; state recovers via refetch ("something changed, refetch" over diff/patch). |
| NFR-05 | **Performance:** deck view renders within 1 s for a 100-card Commander deck with warm image cache; event-to-render latency under 250 ms on localhost, where "render" means panel layout with cached-or-placeholder art (first-fetch image paint excluded). |
| NFR-06 | **Offline:** after image-cache warm-up, the app is fully functional with no network access. |
| NFR-07 | **Tooling parity:** companion code follows existing project standards (ruff, mypy strict, pytest, pre-commit, CI). Frontend gets equivalent tooling (eslint, prettier, vitest or similar) in CI. Node is a dev/CI-only dependency — never required at install or runtime. Applies to every phase from the first commit. |
| NFR-08 | **Attribution & licensing:** the app respects Scryfall's imagery guidance — disk caching, rate-spaced fetches (FR-04), and visible Scryfall attribution in the app footer/about (exact styling in the UX spec), consistent with the project's existing MIT + Scryfall-attribution stance. The public release also carries the Wizards of the Coast Fan Content Policy notice. |
| NFR-09 | **Image cache stewardship:** the disk cache lives in a documented location under `~/.artificial-planeswalker/`, is written atomically, and has a documented inspection/cleanup story (README + uninstall notes). |

## 9. Success Criteria & Counter-Metrics

Success criteria gate the MVP release (Phase 2's "NFR-05 hardening" is profiling beyond
this baseline, not a deferral of it).

- SC-1: With the app open beside the agent, asking for card suggestions produces a
  rendered suggestion panel within 250 ms of the tool call completing — cached art
  shown immediately, placeholders for uncached art filling in as fetched.
- SC-2: Agent-driven deck edits appear in the deck view without user action.
- SC-3: All agent workflows complete successfully with the companion app closed.
- SC-4: A fresh install can launch the companion app with a single `uv` command and no
  additional configuration; if the card database has not yet been initialized, the app
  says so (FR-22) rather than erroring.
- SC-5: The deck view and agent panel look like a deliberate product, not a debug
  dashboard — judged by Brad, the sole quality gate, against the UX spec's reference
  direction (FR-20) before release (no external playtest).

Counter-metrics (what must *not* regress while chasing the above):

- CM-1: Companion tool calls add negligible overhead to agent sessions — tool text
  results stay under ~200 tokens and never echo payloads back into chat.
- CM-2: Scryfall CDN is hit at most once per image+size per cache lifetime; no request
  storms on deck load (rate-spacing per FR-04).
- CM-3: The MCP server's stateless, per-session model is unchanged — no new session
  state in the MCP server. (The companion backend, by contrast, legitimately holds
  ephemeral display state: active deck, connections, tickets.)

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Companion tools invoked with the app closed | FR-12 graceful degradation; the agent presents content in chat as usual |
| Port conflict on default 8765 | Ephemeral-port fallback; discovery file is the source of truth, tools never hardcode the port |
| Stale discovery file after a crash | Tools validate with lightweight `GET /health` (identity-verified via `instance_id`, FR-14) before POSTing; failure means "app not running" |
| SQLite lock contention during bulk data refresh | WAL + read-only connections; backend surfaces a "database updating" state if reads fail transiently |
| Payload schema drift between Python and TS | Single Pydantic source of truth; TS types generated and drift-checked in CI |
| Dark-theme polish under-delivers ("cool" is the point) | UX spec precedes Phase-1 implementation (§11); SC-5 gate against it before release |

## 11. Phasing

NFR-07 (tooling parity) applies to all phases from the first commit. Phase 1 begins
with the UX spec that sets FR-20/SC-5's concrete visual direction.

- **Phase 1 (MVP):** FR-01–FR-08, FR-11–FR-14, FR-17, FR-19, FR-20, FR-22;
  NFR-01–NFR-04, NFR-06, NFR-08, NFR-09.
- **Phase 2:** FR-09, FR-10, FR-15, FR-18, FR-23; NFR-05 hardening.
- **Phase 3:** FR-16, FR-21 (power panel), Tauri wrapper, UI-initiated deck edits (new
  brief).

## 12. Open Questions

- OQ-A: Exact payload schemas for suggestions, swaps, and tier lists (fields,
  optionality, max sizes, empty-payload semantics, ID-validation locus) — **deferred to
  design/architecture**; constraints parked in the addendum.
- OQ-B: TS type-generation tooling (datamodel-code-gen / json-schema-to-typescript /
  other) — **deferred to architecture**.

A delegated design checklist (edge cases that are architecture/UX-spec decisions, not
PRD requirements) is maintained in the addendum.

## 13. Glossary

| Term | Meaning |
|------|---------|
| **Companion app** | The whole feature: companion backend + browser UI. |
| **Companion backend** | The long-running FastAPI process serving the SPA, REST, images, and WebSocket. |
| **Companion tools** | The new MCP tools (`companion_set_active_deck`, `companion_show_*`) the agent calls. |
| **Deck view** | The UI surface rendering the active deck (grid + list + curve). |
| **Agent panel** | The UI surface rendering agent-pushed content. A "suggestion panel" is the agent panel displaying a suggestions push; likewise swap and tier-list panels. |
| **Push / pushed content** | A structured payload sent by a companion tool through `/agent/events` to the UI. |
| **Active deck** | The deck the UI currently displays; owned by the companion backend in memory (FR-07). |
| **Discovery file** | `~/.artificial-planeswalker/companion.json` — `{port, token, instance_id}`, written by the backend, read by tools. |
