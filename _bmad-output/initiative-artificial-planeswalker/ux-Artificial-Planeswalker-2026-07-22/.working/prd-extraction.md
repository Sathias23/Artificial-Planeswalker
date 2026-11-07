# UX-EXTRACTION DIGEST — Artificial Planeswalker Companion App

Source: `_bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/` (prd.md + addendum.md), extracted 2026-07-22 by subagent.

## 1. PRODUCT IN ONE PARAGRAPH

The companion app is a **local, browser-based visual surface** that runs beside an MTG deckbuilding coding-agent session (Claude Code / Codex). Artificial Planeswalker is an MCP-server toolkit (local Scryfall SQLite snapshot + RAG search + deck tools) consumed through the agent as terminal text; the companion app adds a persistent visual channel that renders the **active deck with real card art** and displays **structured content the agent pushes via explicit MCP tool calls** — card suggestions, proposed swaps, tier lists. It is a **presentation layer only** — all deck logic, card data, and analysis stay in the existing MCP server and SQLite DB; the app never bypasses or duplicates them. The single user is a solo MTG player running the toolkit inside a coding agent with a browser window snapped beside the terminal (no multi-user, remote, or collaborative use). The defining interaction model: **"The browser is read-only glass" — the agent drives, the app shows.** Everything that changes state flows through the agent; the user's only clicks are to inspect.

## 2. USERS & PERSONAS

- **A single local user** — "an MTG player running Artificial Planeswalker inside a coding agent, with a browser window snapped beside the terminal." No multi-user, remote, or collaborative scenarios.
- **Brad** — named in UJ-1 and SC-5. He is the persona in the brewing-session journey AND "the sole quality gate" who judges the visual bar (SC-5).

## 3. SURFACES / SCREENS IMPLIED (exhaustive)

| Surface / Panel / View | Description | Driving FR(s) |
|---|---|---|
| **Deck view — card-art grid** | Active deck as full-card-face grid (frame, name, text box), grouped by card type, `normal` image size | FR-05, FR-19 |
| **Deck view — text list view** | Text list of the deck, grouped by card type | FR-05 |
| **Mana curve summary** | Curve visualization along the edge of the deck view; DFCs curve by front face | FR-05 |
| **Card detail view** | Full-size card face (`large`/`png`), oracle text, prices if present; opened by clicking any card in any panel | FR-17, FR-19 |
| **DFC flip control** | Dedicated flip control on double-faced cards in the grid — distinct from clicking (which opens detail view) | FR-19 |
| **Named placeholder (card)** | Rendering for cards with no image data | FR-19, FR-04 |
| **Agent panel — suggestions** | Suggestion list: card + one-line reason + optional category; art-forward; each push replaces current content | FR-08, FR-13 |
| **Agent panel — swaps** | Proposed swaps as out-card / in-card pairs with rationale (P1) | FR-09 |
| **Agent panel — tier list** | Tiered buckets (S/A/B/C) of cards with optional notes (P1) | FR-10 |
| **Session history strip/list** | Capped (~last 20) list of prior pushes, labeled by kind + time, revisitable; in-browser only, clears on refresh (P1) | FR-18 |
| **No-active-deck state** | Shown before any set-active call and after backend restart; lists available decks | FR-07, FR-11 |
| **Database-not-initialized state** | Shown on fresh install when SQLite DB missing/uninitialized, with guidance — never an error page | FR-22 |
| **Connection / status indicator** | Shows backend reachable / WebSocket live + active deck (P1) | FR-15, FR-20 |
| **Disconnected / backend-gone state** | Guides user to terminal/relaunch URL when backend restarted onto a different port | Addendum (delegated checklist) |
| **"Database updating" state** | Surfaced if reads fail transiently during bulk data refresh | Risk table, NFR-02 |
| **Unknown-card placeholder** | Degraded render for unknown-ID entries in a push — never fails the whole push | FR-13, Addendum OQ-A |
| **Deck power panel (radar/7-dim vector + bracket)** | Dedicated visual panel for `assess_deck_power` (P2, Phase 3) | FR-21 |
| **Footer / About — Scryfall attribution** | Visible Scryfall attribution; also WotC Fan Content Policy notice | NFR-08 |

## 4. FUNCTIONAL REQUIREMENTS TOUCHING UI (complete, with MVP flag)

Priorities: **P0 = MVP-blocking**, **P1 = MVP-desirable**, **P2 = post-MVP**. Phase 1 (MVP) = FR-01–08, 11–14, 17, 19, 20, 22.

- **FR-01** [P0/MVP] — Backend serves SPA + REST on localhost port (default 8765), ephemeral-port fallback; single-instance enforcement. *(UI: relaunch-URL implications.)*
- **FR-02** [P0/MVP] — `GET /api/decks` lists decks; `GET /api/deck/{id}` returns full decklist (card IDs, quantities, metadata: name, format, description). *Drives deck view + deck list.*
- **FR-03** [P0/MVP] — `GET /api/cards/{card_id}` returns canonical card data. *UI hydrates detail/art from this.*
- **FR-04** [P0/MVP] — `GET /api/card-image/{scryfall_id}?size=&face=` serves card images (CDN fetch + disk cache); placeholder response on failure. *Drives all card imagery + placeholders.*
- **FR-05** [P0/MVP] — UI renders active deck as card-art grid + text list, grouped by card type, with mana curve summary; DFCs group/curve by front face.
- **FR-06** [P0/MVP] — `POST /agent/events` relays payloads to all UI clients over WebSocket; response reports connected-client count. *Drives agent panel + multi-tab broadcast.*
- **FR-07** [P0/MVP] — `companion_set_active_deck(deck_id)` switches displayed deck; backend owns active-deck ID in memory; no-active-deck state before first set-active and after restart.
- **FR-08** [P0/MVP] — `companion_show_suggestions(payload)` renders suggestion list (card ID, reason, optional category); each push replaces current panel content.
- **FR-09** [P1] — `companion_show_swaps(payload)` renders proposed swaps as out/in pairs with rationale.
- **FR-10** [P1] — `companion_show_tier_list(payload)` renders tiered buckets (S/A/B/C) of card IDs with optional notes.
- **FR-11** [P0/MVP] — Mutation tools emit `deck_changed`; UI refetches when matching active deck; 404 refetch (deleted) clears to no-active-deck state.
- **FR-12** [P0/MVP] — Companion MCP tools degrade gracefully (text results: "app not running", "app running but no browser tab connected"); never hard error.
- **FR-13** [P0/MVP] — Event payloads reference cards by Scryfall printing UUID only; UI hydrates details/art via FR-03/FR-04.
- **FR-14** [P0/MVP] — Discovery file `{port, token, instance_id}`; `GET /health` echoes `instance_id`.
- **FR-15** [P1] — UI shows connection status (backend reachable / WebSocket live) + active deck.
- **FR-16** [P2] — Backend polls SQLite `PRAGMA data_version` for out-of-band changes, emits deck-agnostic `deck_changed`; UI refetches active deck.
- **FR-17** [P0/MVP — **PROMOTED TO MVP**] — Clicking a card in **any** panel opens a **detail view**: full-size card face, oracle text, prices if present in local data.
- **FR-18** [P1] — Lightweight session history (capped ~20, labeled by kind + time), revisitable, re-hydrates against current card data; in-browser only, clears on refresh.
- **FR-19** [P0/MVP] — Grid displays **full card faces** at `normal` size (not art crops); detail view uses `large`/`png`; DFCs show front face + dedicated flip control (distinct from click→detail); cards without image data render named placeholder.
- **FR-20** [P0/MVP] — Dark, game-adjacent theme: card art forward, subtle motion on updates, evoking Arena/Untapped.gg (never imitative of WotC trade dress); motion respects `prefers-reduced-motion`; text meets baseline contrast floor. Concrete direction set by UX spec; acceptance = SC-5 gate.
- **FR-21** [P2] — Deck power assessment (7-dimension vector + bracket) gets a dedicated visual panel.
- **FR-22** [P0/MVP] — Backend starts when SQLite DB missing/uninitialized; UI shows "database not initialized" state with guidance, never an error page.

## 5. NON-FUNCTIONAL REQUIREMENTS RELEVANT TO UX

- **NFR-01 (Security)** — Backend binds 127.0.0.1 only; token-auth on `/agent/events`; CORS same-origin; WebSocket upgrade needs short-lived ticket from `GET /api/session`; Host-header validation (DNS-rebinding). *UX implication: WS handshake/ticket flow, reconnect must re-mint ticket.*
- **NFR-02 (Concurrency)** — SQLite WAL, read-only backend connections; MCP server sole writer. *Implies "database updating" transient-read state.*
- **NFR-03 (Contract)** — Pydantic models with matching generated TS types; REST is the schema boundary; UI never assumes DB schema.
- **NFR-04 (Resilience)** — UI reconnects WebSocket with backoff, refetches active deck on reconnect; fire-and-forget events; "something changed, refetch" model (no diff/patch).
- **NFR-05 (Performance)** — Deck view renders **within 1 s** for a 100-card Commander deck (warm cache); **event-to-render latency under 250 ms** on localhost, where "render" = panel layout with cached-or-placeholder art (first-fetch image paint excluded).
- **NFR-06 (Offline)** — After image-cache warm-up, app fully functional with no network.
- **NFR-07 (Tooling parity)** — Frontend gets eslint/prettier/vitest in CI; **Node is dev/CI-only, never required at install or runtime.**
- **NFR-08 (Attribution & licensing)** — Disk caching, rate-spaced fetches, **visible Scryfall attribution in app footer/about** (exact styling = UX spec); public release carries **WotC Fan Content Policy notice**.
- **NFR-09 (Image cache stewardship)** — Cache under `~/.artificial-planeswalker/`, atomic writes, documented inspection/cleanup.

## 6. PLATFORM & TECH CONSTRAINTS

- **Web page first, NOT Electron** (NG4). Backend serves SPA at `localhost:8765`; OS window snapping provides side-by-side. **Tauri preferred over Electron** if wrapped later (Phase 3); wrapping needs no architecture change (loads same URL).
- **Browser SPA: Vite + React**, served by the backend. State comes from **exactly two inputs: REST responses and WebSocket messages.**
- **Client state: zustand store, client-side only.** Suggested slices: `activeDeck`, `agentPanel` (latest push + session history), `connectionStatus`. WS handlers call `store.setState`; the agent never touches the store directly.
- **Backend: FastAPI**, long-running, same Python codebase/DB layer/Pydantic models as the FastMCP server. Entry point `uv run artificial-planeswalker companion`.
- **Backend owns the active-deck ID** (in memory) — not the UI (FR-07).
- **Transport: localhost HTTP + WebSocket** (not file-watching).
- **Port:** default **8765**, ephemeral fallback on conflict; **discovery file is source of truth**, port never hardcoded.
- **Binds to 127.0.0.1 only** — no remote access (NG3).
- **No LLM calls from the app itself** (NG2). **No deck editing from the UI** — read-only in MVP (NG1).
- **Frontend build ships as static package data** inside the Python package (SC-4 — fresh install needs no Node).
- **Full-card-art data already local:** `cards.image_uris` size map (`small`/`normal`/`large`/`png`/`art_crop`/`border_crop`); DFCs store `image_uris` per `card_faces` entry (needs `face` param + per-face cache keys). `png` = full face w/ transparent corners; `normal`/`large` = JPG full faces.

## 7. JOURNEYS / FLOWS

- **UJ-1 — Brewing session** (verbatim name). Brad tunes a Commander brew: starts backend once (`uv run artificial-planeswalker companion`), opens `localhost:8765`, snaps beside terminal. Asks agent to load the deck → deck view fills with full card faces, grouped by type, mana curve along the edge. Asks "what would make the token engine more resilient?" → agent calls `companion_show_suggestions` → suggestion panel **slides in** with six cards, art-forward, each with a one-line reason. He clicks one to read full oracle text in the detail view, decides against two others, tells the agent to add the one he liked → deck view **updates by itself within a second**. Key principle: **"The browser is read-only glass: his only clicks are to inspect — flip a card, open the detail view — while everything that changes state flows through the agent. The agent drives, the app shows."**

Success criteria that read as flow assertions:
- **SC-1** — Suggestion panel renders within 250 ms of tool-call completion; cached art immediate, placeholders fill in as fetched.
- **SC-2** — Agent-driven deck edits appear in deck view without user action.
- **SC-3** — All agent workflows complete successfully with the app closed.
- **SC-4** — Fresh install launches with a single `uv` command, no config; uninitialized DB → says so (FR-22).
- **SC-5** — Deck view + agent panel "look like a deliberate product, not a debug dashboard," judged by Brad against the UX spec's reference direction (FR-20).

## 8. STATES & EDGE CASES (exhaustive)

**Empty / initial states:**
- **No-active-deck state** — before any `companion_set_active_deck` call, and after backend restart; lists available decks (FR-07, FR-11).
- **Database-not-initialized state** — fresh install, SQLite missing/uninitialized; guidance shown, never an error page (FR-22, SC-4).
- **Empty-payload push** — zero suggestions / all-empty tiers; schema design decides reject-at-schema vs. render-empty-state (Addendum OQ-A) — **UX must define the empty-state render if render-empty is chosen.**

**Loading / async states:**
- **Placeholder-then-fill imagery** — cached art shown immediately, placeholders for uncached art filling in as fetched (SC-1, NFR-06).
- **Deck refetch on `deck_changed`** — "something changed, refetch" model; loading during refetch (NFR-04, FR-11).
- **"Database updating" state** — surfaced if reads fail transiently during bulk data refresh (Risk table, NFR-02).

**Connection / disconnection states:**
- **Backend reachable / WebSocket live indicator** (FR-15).
- **WebSocket reconnect with backoff** + refetch active deck on reconnect (NFR-04).
- **Backend restarted onto a different port while UI open** — disconnected state should guide user to the terminal/relaunch URL (Addendum, delegated to UX spec).
- **"App not running" / "app running but no browser tab connected"** — tool-side text outcomes that the UI's connection status must reflect (FR-12, FR-06 client-count).

**Stale / error / degraded states:**
- **Deck deleted (refetch 404s)** — clears to no-active-deck state (FR-11).
- **Unknown-ID entry in a push** — renders degraded ("unknown card" placeholder), never fails the whole push (FR-13, Addendum OQ-A).
- **Card with no image data** — stable **named placeholder** (FR-19, FR-04).
- **CDN fetch failure** — defined placeholder response, negative-cached with backoff; no request storms (FR-04, CM-2).
- **Mutation persists but event POST fails** — emission failure swallowed; staleness window accepted until FR-16 (Addendum).
- **Refetch racing a second mutation** — latest-wins; coalescing / in-flight cancellation / version check (Addendum, NFR-04).
- **Stale/corrupt/partially-written discovery file** — treated as "app not running" (Risk table, Addendum).

**Interaction-specific edge cases (UX must decide):**
- **DFC flip-state persistence across `deck_changed` re-renders** — a snap-back reads as a bug (Addendum, delegated to UX spec).
- **Cross-tab history divergence** — FR-06 broadcasts to all tabs, but FR-18 history is per-tab (Addendum, delegated to UX spec).
- **Click-vs-flip disambiguation** — clicking a DFC opens detail view; flip control is separate (FR-19).
- **Session history clears on refresh** — in-browser only (FR-18).

## 9. LEGAL / BRAND CONSTRAINTS (verbatim key points)

- **NFR-08:** "The public release also carries the **Wizards of the Coast Fan Content Policy notice**." App respects Scryfall's imagery guidance — disk caching, rate-spaced fetches (FR-04), and **"visible Scryfall attribution in the app footer/about (exact styling in the UX spec)"**, consistent with "the project's existing MIT + Scryfall-attribution stance."
- **FR-20:** Dark game-adjacent theme "evoking Arena/Untapped.gg rather than utilitarian dashboards — **never imitative of WotC trade dress**."
- Card imagery is fetched from the Scryfall image CDN and disk-cached; **CDN hit at most once per image+size per cache lifetime** (CM-2); rate-spaced/concurrency-capped per Scryfall guidance (FR-04).

## 10. OPEN QUESTIONS / RESIDUALS

- **OQ-A** — Exact payload schemas for suggestions/swaps/tier lists (fields, optionality, max sizes, **empty-payload semantics** [reject vs. render-empty — a UX call], ID-validation locus) — deferred to design/architecture.
- **OQ-B** — TS type-generation tooling — deferred to architecture.
- **FR-20 concrete visual direction** — reference screenshots, comparison set, motion inventory — **explicitly set by the UX spec produced before Phase-1 implementation**; acceptance is the SC-5 gate. This is the UX spec's primary charter.
- **Delegated design checklist (UX spec must decide each deliberately):** backend-restarted-different-port disconnected-state guidance; DFC flip-state persistence across re-renders; cross-tab history divergence; empty-state renders; unknown-card degraded render styling; ticket lifecycle (expiry/single-use — architecture-leaning).
- **Discrepancy noted:** intake memory mentioned "observability NFR + platformdirs" residuals; neither appears in the final prd.md/addendum.md (NFR-01..NFR-09, cache at `~/.artificial-planeswalker/`). Treated as out of scope for the UX spec.
- **Motion inventory** — subtle motion on new push and deck change, respecting `prefers-reduced-motion` (FR-20) — specific motions undefined, UX to inventory.
- **Attribution styling** — footer/about exact styling explicitly deferred to UX spec (NFR-08).

## 11. VERBATIM NAMES (must mirror)

**Features / concepts:** Companion app · Companion backend · Companion tools · Push / pushed content · Active deck · Discovery file (`~/.artificial-planeswalker/companion.json`, `{port, token, instance_id}`).

**Surfaces:** Deck view · Agent panel · Suggestion panel · Swap panel · Tier-list panel · Detail view · No-active-deck state · "Database not initialized" state · "Database updating" state.

**Tool names:** `companion_set_active_deck(deck_id)` · `companion_show_suggestions(payload)` · `companion_show_swaps(payload)` · `companion_show_tier_list(payload)`.

**Endpoints:** `GET /api/decks` · `GET /api/deck/{id}` · `GET /api/cards/{card_id}` · `GET /api/card-image/{scryfall_id}?size=&face=` · `POST /agent/events` · `GET /health` · `GET /api/session`.

**Events:** `deck_changed`.

**Image sizes:** `small`, `normal`, `large`, `png`, `art_crop`, `border_crop`. Grid uses `normal`; detail view uses `large`/`png`.

**Journey:** **UJ-1 — Brewing session.**

**Aesthetic references:** "Arena/Untapped.gg"; "dark, game-adjacent"; "card art forward"; "read-only glass"; "The agent drives, the app shows."

**Tier labels:** "S/A/B/C".
