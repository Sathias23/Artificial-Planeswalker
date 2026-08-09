---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/prd.md
  - _bmad-output/planning-artifacts/prds/prd-Artificial-Planeswalker-2026-07-22/addendum.md
  - _bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/DESIGN.md
  - _bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/EXPERIENCE.md
  - _bmad-output/planning-artifacts/ux-designs/ux-Artificial-Planeswalker-2026-07-22/validation-report-2026-07-25.md
  - _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/architecture/architecture-Artificial-Planeswalker-2026-07-25/EPIC-SPLIT.md
  - _bmad-output/project-context.md
---

# Artificial-Planeswalker Companion App - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the **Artificial-Planeswalker
companion app**, decomposing the requirements from the PRD (2026-07-22, addendum amended
2026-07-25), the UX design contract (DESIGN.md + EXPERIENCE.md, Voltglass, 2026-07-25), and the
Architecture Spine (2026-07-25) into implementable stories.

**Scope note.** This is a *feature-level* epic set layered onto an existing brownfield codebase.
It does not supersede `epics.md` (the MCP-server pivot) or `epics-deck-power-assessment.md`; it
adds `src/companion/`, `ui/`, and a small set of new MCP tools alongside them.

## Requirements Inventory

### Functional Requirements

Priorities from the PRD: **P0** = MVP-blocking, **P1** = MVP-desirable, **P2** = post-MVP.
Phase assignment from PRD §11.

**Feature A — Backend service & lifecycle**

FR-01: Backend serves the SPA and REST API on a configurable localhost port (default 8765),
falling back to an ephemeral port on conflict. Exactly one instance runs at a time: on startup,
a discovery file pointing at a live, identity-verified instance (FR-14) makes the new process
exit with an "already running" message; a stale or dead entry is taken over. *(P0, Phase 1)*

FR-02: `GET /api/decks` lists decks; `GET /api/deck/{id}` returns a full decklist with card IDs,
quantities, and metadata (name, format, description — matching `load_deck` output). *(P0, Phase 1)*

FR-03: `GET /api/cards/{card_id}` returns canonical card data hydrated from the local SQLite
database. *(P0, Phase 1)*

FR-04: `GET /api/card-image/{scryfall_id}?size=&face=` serves card images, fetching from the
Scryfall image CDN on first request and disk-caching thereafter. Sizes resolve from the locally
stored `image_uris`; **face handling is driven by the presence of per-face `image_uris` inside
`card_faces`, not by a layout string** (architecture correction, AD-11 — `cards` has no `layout`
column). CDN fetches are concurrency-capped and rate-spaced per Scryfall guidance; failures are
signalled distinguishably and negative-cached with backoff so an unreachable CDN never causes
request storms. Cards with no image data get a stable no-image response. *(P0, Phase 1)*

FR-05: UI renders the active deck as a card-art grid **and** a text list view, grouped by card
type, with a mana curve summary. Double-faced cards group and curve by their front face.
Satisfied by two simultaneous columns rather than a toggled pair (UX 2026-07-25); no toggle is
mandated. *(P0, Phase 1)*

FR-06: Backend exposes `POST /agent/events` (token-authenticated) and relays payloads to all
connected UI clients over WebSocket. The response reports the connected-client count, so tools
can tell the user whether the content was actually displayed. *(P0, Phase 1)*

FR-07: MCP tool `companion_set_active_deck(deck_id)` switches which deck the UI displays. The
companion backend owns the active-deck ID in memory; before any set-active call — and after a
backend restart — the UI shows a defined no-active-deck state listing available decks. *(P0, Phase 1)*

FR-08: MCP tool `companion_show_suggestions(payload)` renders a suggestion list (card ID, reason,
optional category) in the agent panel. Each new push replaces the panel's current content
(FR-18 adds history). *(P0, Phase 1)*

FR-09: MCP tool `companion_show_swaps(payload)` renders proposed swaps as out-card / in-card
pairs with rationale. *(P1, Phase 2)*

FR-10: MCP tool `companion_show_tier_list(payload)` renders tiered buckets of card IDs with
optional notes. Tier vocabulary is **S/A/B/C/D** (UX ruling 4, 2026-07-25). *(P1, Phase 2)*

FR-11: Existing deck-mutation tools emit `deck_changed` events after persisting; deletion counts
as a mutation. The event carries the deck ID; the UI refetches when it matches the active deck
(and may refresh the deck list regardless). A refetch that 404s (deck deleted) clears to the
no-active-deck state. *(P0, Phase 1)*

FR-12: All companion MCP tools degrade gracefully: on any failure — backend unreachable, auth
rejection, or any non-success response — the tool returns a text result describing the outcome,
never a hard error. Tools re-read the discovery file on auth failure and retry once, so a
restarted backend (new token) is picked up transparently mid-session. The agent already holds
the pushed content and presents it in chat as usual; no payload echo is needed. *(P0, Phase 1)*

FR-13: Event payloads reference cards by ID only; the UI hydrates details and art via
FR-03/FR-04. The canonical ID everywhere is the Scryfall printing UUID (`cards.id`, the value in
`deck_cards.card_id`). Name→ID resolution stays with existing MCP tools. *(P0, Phase 1)*

FR-14: Backend writes and refreshes the discovery file `{port, token, instance_id}` on startup
and removes it on clean shutdown. `GET /health` echoes the `instance_id` so callers can verify
they are talking to this app instance — not a foreign process squatting on a recycled port —
before sending the token. **Location is `src.paths.data_dir()/companion.json`**, not
`~/.artificial-planeswalker/` (architecture override, AD-4). *(P0, Phase 1)*

FR-15: UI shows connection status (backend reachable / WebSocket live) and the active deck.
*(P1, Phase 2)*

FR-16: Backend detects out-of-band deck changes by polling SQLite `PRAGMA data_version` and emits
a deck-agnostic `deck_changed`; the UI refetches the active deck. *(P2, Phase 3)*

FR-17: Clicking a card in any panel opens a detail view: full-size card face, oracle text, prices
if present in local data. Satisfied by a **persistent right-column panel** with hover/focus
tracking and click-to-pin, not a modal (UX 2026-07-25). *(P0, Phase 1)*

FR-18: A lightweight session history (capped, e.g. last 20 pushes, labeled by kind and time) lets
the user revisit earlier pushes; revisited entries re-hydrate against current card data. History
is in-browser only and clears on refresh. *(P1, Phase 2)*

FR-19: The card grid displays **full card faces** (frame, name, text box), not art crops, at the
`normal` image size; the detail view uses `large`/`png`. Double-faced cards show the front face
with a dedicated flip control — distinct from clicking the card, which sets/pins the inspection
(FR-17). Cards without image data render a named placeholder. *(P0, Phase 1)*

FR-20: The UI ships a dark, game-adjacent theme (**Voltglass**): card art forward, subtle motion
on updates, evoking Arena/Untapped.gg rather than utilitarian dashboards — never imitative of
WotC trade dress. Motion respects `prefers-reduced-motion` and text meets a baseline contrast
floor. Acceptance is the SC-5 gate against DESIGN.md + EXPERIENCE.md. *(P0, Phase 1)*

FR-21: Deck power assessment (7-dimension vector + bracket from `assess_deck_power`) gets a
dedicated visual panel. *(P2, Phase 3)*

FR-22: Backend starts successfully when the SQLite database is missing or not yet initialized
(fresh install): it serves the SPA and the UI shows a "database not initialized" state with
guidance, never an error page. *(P0, Phase 1)*

FR-23: MCP tool `companion_show_groups(payload)` renders titled groups of cards, each with a
prose rationale and a card-ID list — the agent's answer to "show me the X in this deck". Distinct
from FR-08 in that a group carries a title and a paragraph of reasoning over an arbitrary card
set, **including cards not in the active deck**. *(P1, Phase 2)*

### NonFunctional Requirements

NFR-01: **Security** — backend binds to 127.0.0.1 only; `/agent/events` requires the shared token
from the discovery file; CORS restricted to the app's own origin. WebSocket upgrades are
authenticated via a short-lived ticket from same-origin `GET /api/session`; upgrades without a
valid ticket are rejected. All endpoints, **including the WS upgrade**, validate the `Host` header
(`127.0.0.1:{port}` / `localhost:{port}`) to block DNS rebinding; the upgrade additionally
validates `Origin` (AD-5).

NFR-02: **Concurrency** — SQLite in WAL mode; the MCP server remains the sole writer. *Amended by
AD-2:* read-only is enforced by a **CI import-boundary test**, not by `mode=ro` connections (the
`-shm` recipe is a Windows landmine and `immutable` would foreclose FR-16). **This PRD line needs
amending — tracked as a release-readiness deliverable.**

NFR-03: **Contract** — event payloads are Pydantic models in the shared package with
generated/matching TypeScript types in the UI. The REST layer is the schema boundary; the UI never
assumes DB schema.

NFR-04: **Resilience** — UI reconnects WebSocket with backoff and refetches the active deck on
reconnect. Event delivery is fire-and-forget; state recovers via refetch ("something changed,
refetch" over diff/patch).

NFR-05: **Performance** — deck view renders within 1 s for a 100-card Commander deck with warm
image cache; event-to-render latency under 250 ms on localhost, where "render" means panel layout
with cached-or-placeholder art (first-fetch image paint excluded; the clock stops at first paint
of laid-out content, not at animation settle).

NFR-06: **Offline** — after image-cache warm-up, the app is fully functional with no network
access. Implies the webfont is self-hosted, not CDN-imported.

NFR-07: **Tooling parity** — companion code follows existing project standards (ruff, mypy strict,
pytest, pre-commit, CI). Frontend gets equivalent tooling (eslint, prettier, vitest) in CI. Node
is a dev/CI-only dependency — never required at install or runtime. Applies to every phase from
the first commit.

NFR-08: **Attribution & licensing** — disk caching, rate-spaced fetches (FR-04), and visible
Scryfall attribution in the app footer, consistent with the project's MIT + Scryfall-attribution
stance. The public release also carries the Wizards of the Coast Fan Content Policy notice.

NFR-09: **Image cache stewardship** — the disk cache lives in a documented location under the
project data dir, is written atomically, and has a documented inspection/cleanup story (README +
uninstall notes).

### Additional Requirements

Technical requirements from the Architecture Spine (2026-07-25) that shape stories. Each is
bound to the AD that governs it.

**Starter template / greenfield sub-tree**

- **There is a greenfield scaffold inside this brownfield repo:** `ui/` is a **new Vite + React +
  zustand + TypeScript project** created from scratch (no project-provided starter template is
  specified). It is the only new toolchain in the feature and it lands in the SPA-foundation epic,
  which must therefore carry the scaffold-creation story as its first story: Vite init, TS config,
  eslint/prettier/vitest wiring into CI, and the build-into-`app/static` pipeline. Everything
  Python-side is additive to the existing `src/` package and needs no scaffold. *(AD-13, NFR-07)*

**Structure & boundaries**

- `src/companion/` is a **sibling** of `src/mcp_server/`, both over the same `src/data` +
  `src/logic`. The backend consumes existing repositories and their Pydantic schemas and defines
  no second card or deck shape. It is **not** an MCP client. *(AD-1)*
- `src/companion` splits into a **dependency-free leaf** (`contracts.py`, `discovery.py`,
  `client.py` — importing only `pydantic`, `httpx`, `src.paths`) and the FastAPI `app/`. The MCP
  server **may** import the leaf; it **may not** import `src.companion.app.*`. *(AD-3)*
- **Two CI boundary tests are required deliverables**, landing before the code they guard: (1) an
  AST-walk over `src/companion/**` failing on any repository write method, `session.add`,
  `session.commit`, or `session.delete`; (2) the leaf/app import guard. *(AD-2, AD-3)*
- Inherited: import direction `data → logic → shells`; repositories return Pydantic schemas never
  ORM models; MCP tools stay stateless; no Alembic; `mypy --strict`, ruff line-length 100, Google
  docstrings, module docstrings, `%`-style lazy logging. *(project-context.md)*

**Lifecycle & process**

- `build_app()` has **zero side effects**. Port bind, ephemeral fallback, discovery-file write and
  removal, image-cache directory creation, and engine creation all belong to the **lifespan**. The
  DB engine is **lazy** and its absence is a served UI state, not a startup failure. *(AD-10)*
- Discovery file written **atomically** (temp + rename) at `src.paths.data_dir()/companion.json`,
  honouring `PLANESWALKER_DATA_DIR`. A parse failure is *app not running*, never an error. *(AD-4)*
- `artificial-planeswalker` becomes a **subcommand dispatcher**: no arguments runs the MCP server
  exactly as today; `companion` runs the backend. Verified safe — both `.mcp.json` and
  `plugin/.mcp.json` invoke `python -m src.mcp_server` directly. *(AD-14)*
- The backend is a foreground, user-launched, single-instance local process — no daemon, no
  service install, no auto-restart. Unlike the MCP process it **logs freely to stdout/stderr**.
  *(AD-15)*
- **`view_deck` is deprecated at Phase 1** (docstring names the companion as replacement) but keeps
  rendering HTML through Phases 1–2 so SC-3 holds; `src/viewer` is removed at the next minor. No
  new capability lands in `src/viewer`; the companion never reuses `template.html`. *(AD-15)*

**Contracts & wire format**

- Every WebSocket message is `{kind, id, ts, payload}`. `kind` is a **closed enum** covering agent
  pushes (`suggestions | swaps | tier_list | groups`) and system signals (`deck_changed`). `id` is
  opaque (identity/dedupe, never ordering); **history orders by `ts`** = `datetime.now(UTC)`. One
  Pydantic discriminated union, one generated TS union, one switch. *(AD-6)*
- Per-kind payload item shapes over a bare card reference (resolves OQ-A):
  `suggestions` → `{card_id, reason, category?}`;
  `swaps` → `{out_card_id, in_card_id, rationale, out_qty, in_qty}`;
  `tier_list` → `{letter: Literal["S","A","B","C","D"], name, note?, card_ids[]}`;
  `groups` → `{title, rationale, card_ids[]}`. Every payload carries an optional agent-authored
  `title`. *(AD-7)*
- **Caps** (pydantic, at the endpoint): ≤ 60 items or card IDs per list, ≤ 12 groups or tiers,
  `reason` ≤ 200 chars, `rationale` ≤ 600, `title` ≤ 80, envelope ≤ 64 KB. **Over-cap returns 422 —
  rejected, never truncated.** Empty payloads are **accepted** and render the empty state. Card IDs
  are **not** validated at ingest; the backend shape-validates and relays and **never reads the
  database on the push path**. *(AD-7)*
- Companion tools are `async def`, **never raise**, and return a compact text result carrying
  exactly one token from the closed set
  `displayed | app_not_running | no_clients_connected | payload_rejected | backend_error`, plus the
  connected-client count. No payload echo; results under ~200 tokens. Auth rejection → re-read the
  discovery file and **retry exactly once**. *(AD-8)*
- **Two credentials that never touch:** the agent token (discovery file → `POST /agent/events`,
  **never reaches the browser**) and the WS ticket (same-origin `GET /api/session`, **single-use,
  30 s TTL**, consumed at upgrade, fresh per reconnect attempt). No shared storage, no shared code
  path. *(AD-5)*
- `deck_changed` is emitted by **one shared notifier in the leaf**, called by every deck-mutation
  tool **after commit**, never inside the transaction. All exceptions caught and logged; the
  mutation's own result is never affected. **"Fire-and-forget" means a bounded-timeout `await`
  (~1 s), not a detached task** — `create_task` is banned here. *(AD-9)*

**REST semantics**

- REST is **HTTP-native, not MCP-shaped**: status codes carry the outcome, success bodies are the
  existing Pydantic schemas **unwrapped**. Every non-2xx returns one typed error body with a closed
  snake_case `reason` token mapping 1:1 onto a UX state: `deck_not_found` (404),
  `database_not_initialized` (503), `database_unavailable` (503), `invalid_request` (400),
  `payload_too_large` (413 — **moved from 422 to HTTP's native status by the c1-4 review ruling,
  Brad 2026-07-25**), **`internal_error` (500 — added by the same ruling so an unhandled backend
  bug is distinguishable from the transient `database_unavailable` retry state; its state panel is
  homed on Story 2.9)**, **`card_not_found` (404 — added in Story 3.2 under AD-16's own rule,
  since FR-13's unknown-card placeholder is a UI state and therefore needs a token)**. Adding a UI
  state means adding a token here first. Deck-existence validation for
  `companion_set_active_deck` belongs to the **MCP tool**, not the backend. *(AD-16)*

**Endpoints added beyond the spine's route list** (each recorded here rather than discovered
mid-story):

- `GET /api/deck/{id}/format-check` — the format check panel is P0 in EXPERIENCE.md but had no
  data source. Reuses the existing `src/logic` validators; a TypeScript reimplementation would be
  the second truth AD-1 exists to prevent. *(Story 3.3)*
- `GET /api/active-deck` (same-origin read) and `PUT /api/active-deck` (token-authenticated write)
  — AD-16 calls `set_active_deck` "control, not a push" but names no transport, and nothing told a
  cold-opened tab which deck was active. *(Story 3.4)*

**Image proxy**

- All card imagery routes through the backend proxy; the SPA never contacts Scryfall. Fetching is
  **lazy**, behind a **single backend-global semaphore plus request spacing**, `async` throughout
  (must never block the event loop). CDN URLs resolve from locally stored `image_uris`; no live
  Scryfall metadata call is ever made. **The backend never serves a substitute image** — failure
  and no-image-data are signalled distinguishably so the client draws the named placeholder. Cache
  path `data_dir()/image_cache/<id[0:2]>/<id>/<size>_<face>.<ext>`, temp + rename. Failures
  negative-cached with backoff. Unknown `size` → 400; missing `face` → 404; single-faced with
  `face=0` → the image. **No eviction in MVP**; a cold 100-card deck is ~12 MB / ~10 s to fully
  paint and that is an expected observation, not a defect. *(AD-11)*

**Type generation & frontend distribution**

- Contracts are Pydantic in `src/companion/contracts.py`; TS types are generated by
  **`openapi-typescript`** from the backend's own `app.openapi()` into a **committed** `.d.ts`, and
  CI regenerates and runs `git diff --exit-code`. One generator covers both halves because
  `POST /agent/events` declares the envelope union as its request body. (Resolves OQ-B;
  `datamodel-code-generator` was never a candidate.) *(AD-12)*
- **Card hydration has one owner:** a single card cache in the zustand store, keyed by card ID,
  that dedupes in-flight requests. **No second data-fetching or state library** joins zustand. *(AD-12)*
- The built SPA is a **committed artifact** at `src/companion/app/static/`, mirrored into `plugin/`
  by the existing rebuild + drift-check machinery. Both copies are generated — never hand-edited.
  Node is dev/CI-only. The font is **self-hosted with these assets**. *(AD-13)*

**Testing**

- The bulk of backend testing runs in-process over `httpx.ASGITransport` and the existing
  in-process MCP client. **Exactly one** `integration`-marked test boots a real backend on an
  ephemeral port with a real discovery file, a real client, a real WS upgrade + ticket consume, and
  a restart-mints-new-token retry case. *(AD-10)*
- Browser-level E2E (Playwright) is explicitly **deferred**; SC-5 is a human gate. *(Spine, Deferred)*

**Stack floors** (all `>=`, matching existing `pyproject.toml` convention)

- Python >=3.12 · pydantic >=2.0.0 · httpx >=0.28.1 · platformdirs >=4.0.0 · SQLAlchemy[asyncio]
  >=2.0.44 / aiosqlite >=0.21.0 · mcp/FastMCP >=1.27.0 · **FastAPI >=0.139.2** · **uvicorn[standard]
  >=0.51.0** · Vite >=8.0 · React >=19.2 · **TypeScript >=5.9,<6.1 (upper bound is load-bearing —
  `typescript-eslint` publishes a peer range of `<6.1.0`, so an open floor resolves to TS 7 and
  breaks `npm ci` and the ESLint gate)** · zustand >=5.0 · openapi-typescript >=7 (dev/CI) ·
  Node >=20 (dev/CI only).

**PRD amendments owed** (deliverables, not observations)

- NFR-02's `mode=ro` mechanism → replaced by the CI import boundary (AD-2).
- FR-14 + glossary's `~/.artificial-planeswalker/` → `src.paths.data_dir()` (AD-4).
- FR-04's `layout`-driven face handling → per-face `image_uris` presence (AD-11).

### UX Design Requirements

Extracted from the Voltglass UX design contract (DESIGN.md — visual identity; EXPERIENCE.md —
behavior). These are first-class work items, not styling notes.

**Design tokens & foundations**

UX-DR1: Implement the **Voltglass token set** as CSS custom properties matching DESIGN.md
frontmatter names byte-for-byte: 26 colors (4-step surface ramp `well → base → panel → overlay`,
scrim, 2 borders, 4 text tiers, 4 accent tokens, focus ring, 3 semantic, 7 WUBRG data colors),
7 typography roles, 4 radii + the card radius, the 7-step spacing scale + gutter/panel-gap, 4
motion durations + 3 easings, focus-ring, and 3 elevation tokens. **Every shadow and radius goes
through a token** — a hard-coded literal silently breaks the four alternate themes
(`gilt`/`graphite`/`verdigris`/`ink`), and because `shadow-raise` is the *live* state, a hard-coded
*rest* shadow inverts the hierarchy under the shadowless themes.

UX-DR2: **Self-host Space Grotesk** with the backend's static assets — no CDN import (NFR-06: the
app must render identically offline; a fallback to `system-ui` is a visible regression).

UX-DR3: **Tabular numerals on every count, quantity, price and axis value.** The CSS `font`
shorthand cannot carry `font-variant-numeric`, so the numeric role and its
`numeric-features` property are always applied together; `font: var(--type-numeric)` alone is a
defect.

UX-DR4: **Card geometry is exact and exclusive:** every card face, thumbnail, placeholder and the
detail art uses the card radius (`4.75% / 3.4%`) at a `63 / 88` aspect. Nothing else in the UI
borrows the card radius, and cards never borrow a chrome radius. Grid is
`repeat(auto-fill, minmax(176px, 1fr))`.

UX-DR5: **Every spacing value comes from the 4/8/12/16/24/32/48 scale.** The imported mock's
18/14/9/7px one-offs are drift, not spec, and must not be reproduced.

UX-DR6: Enforce the two **contrast constraints** that have no headroom: `text-tertiary` on
`surface-overlay` is 4.8:1 (do not darken it; do not introduce a fifth surface above
`surface-overlay`), and **`accent-dim` is banned on `surface-overlay`** (2.70:1, fails the 3:1
non-text floor) — live/selected markers on overlay-backed rows use `accent`.

UX-DR7: Enforce the two **brand hard rules**: card art carries all fantasy (no serif lettering,
ornament, parchment or frames in chrome; art renders untinted, un-overlaid, unwatermarked), and
nothing is imitative of WotC trade dress (no Beleren-like faces, no card-frame chrome, no
symbol lookalikes; `ManaPip` is deliberately a plain colored dot). WUBRG tokens are **data ink
only** — never a button, border, background, or an *unstacked* curve-bar fill.

**Layout**

UX-DR8: Build the **two-column composition** under a full-width header: header (kicker + deck
name left; format/size badges + agent-view nav right), fluid left column (card grid panel, with
mana-curve and color-distribution panels below as a 1:1 pair), 452px fixed right column (card
detail, deck list, format check, stacked), and a full-width footer pinned to the window bottom.
Panels float with visible canvas between them. Target ~1100px→~2560px; **below ~1100px the right
column drops beneath the left rather than compressing**. Reference width 1720px. Agent views take
the whole window as a scrim-backed overlay inset by 32px.

**Components — presentation-only primitives (no behavior)**

UX-DR9: **Panel** — the universal container, with `level="overlay"` variant, optional header
(label title + numeric count + right-aligned badges), and a `live` state (accent title, 6px accent
dot, elevation raised to `shadow-raise`).

UX-DR10: **Badge** — pill in 5 tones (neutral, accent, positive, negative, caution); semantic tones
tint background and border **from their own semantic token**, never hard-coded RGB.

UX-DR11: **StatChip** — micro label over a 17px numeric value, with an optional delta tinted
positive/negative by sign.

UX-DR12: **Group header** — type-group divider (e.g. "CREATURES") with right-aligned numeric count
over a hairline rule.

UX-DR13: **ManaPip / ManaCost** — plain circle filled with the `mana-*` token, inverse numeral for
generic costs. `ManaCost` parses full Scryfall cost strings: braces, hybrid (`{2/R}`, `{W/U}`) as a
split or dual-tinted pip, Phyrexian, and `{X}` — **never silently dropping a symbol it doesn't
recognize**.

**Components — deck view**

UX-DR14: **Card tile** — chrome-free card face as the tile, caption below, single-line ellipsis.
Hover **or keyboard focus** sets the inspection target; click **pins** it. Hover pop is
`scale(1.06)` in place raising z-index, presentation only — it never changes hit targets. `live`
adds the accent live-ring. Tiles are focusable, in the Tab order in visual order, and use the
dedicated **focus-ring-over-art** treatment (ring + dark outer edge) because the indicator sits
over arbitrary art.

UX-DR15: **DFC flip control** — 28px circular control with a 32px hit area pinned to the tile's
**top-left** (top-right is the quantity badge; the two must never collide), sharing the badge's
scrim+blur material, carrying a stroke-based two-arrow rotate glyph that could never read as a
mana or set symbol. Rest opacity 0.65, 1.0 when its tile is hovered/focused. Own click target with
`stopPropagation`: a click **only flips** and never sets, pins or clears the inspection.
**Tab order immediately after its own tile**, never a trailing group. Enter/Space flips. Flip state
is **keyed by Scryfall printing UUID, survives `deck_changed` re-renders** (a snap-back reads as a
bug), is per-tab and in-memory, resets on refresh, and applies **everywhere the printing appears**
(grid, agent-view thumbnails, detail panel). Hovering/pinning a flipped tile targets **that face**
— the detail panel shows the back face, its name and its oracle text. Rendered **only where
per-face `image_uris` exist**; split/adventure/flip layouts get no control. 3D Y-rotation on flip.
The detail panel gets its own copy of the control at the same spec.

UX-DR16: **Quantity badge** — "×N" pinned top-right inside 8px on scrim + blur. A changed quantity
on refetch flashes the accent glow once — **garnish only**; the accessible signals are the
group-header count and the coalesced live-region announcement.

UX-DR17: **Mana curve** — bars per mana value on a well track. **Buckets are 1…7+; lands are
excluded; DFCs bucket by front face.** Recomputed from the decklist on every refetch. Bars are
display-only. Unstacked bars fill with the **chrome** token, never a `mana-*` token; if stacked,
segments run W·U·B·R·G·gold·colorless with multicolor contributing one `mana-gold` segment and the
painted segments `aria-hidden`. Each bar exposes an accessible name carrying its count ("3 drops:
8 cards"), and the curve as a whole is backed by a **visually-hidden table**.

UX-DR18: **Color distribution** — one 14px pill-radius bar segmented by `mana-*` proportional to
pip count, with a legend of pip + count + percentage below. **The bar is `aria-hidden`; the legend
is the accessible data path**, so color is never the sole carrier.

UX-DR19: **Deck row** — the text-list unit: quantity (numeric, tertiary), name (body; body-strong
primary when live), mana cost as pips, right-aligned price. Same inspection contract as a card
tile (hover/focus sets, click pins); rows are focusable. DFC rows show the front face's name and
cost. Unknown or imageless cards render identically — the list is text-first.

UX-DR20: **Card detail panel** — persistent right-column `level="overlay"` panel showing the
inspection target, in two modes: **transient** (hover/focus over any tile, thumbnail or deck row
updates it live) and **pinned** (click or Enter fixes it, adds the pinned ring, hover no longer
overrides). Release by clicking the same card again, Esc, or the unpin control. On cold open it
targets the first card of the first type group and is **never empty while a deck is loaded**.
Name and cost render immediately at hover time; the rest hydrates in place with **no spinner**.
Prices render only when present in local data. **Not a modal and not a live region.**

UX-DR21: **Format check** — one row per local validation check, tone-mapped pass → positive,
advisory → caution, violation → negative. Display-only.

UX-DR22: **Card placeholder**, two variants — a deliberately designed card-shaped stand-in, never
a broken-image glyph: named variant (name centered in body-strong, mana pips above, type line in
micro) and unknown-card variant ("Unknown card" + truncated ID, the ID in `text-secondary` because
it is the only identifying information). Image-loading wells use the same shape on `surface-well`
with no text. Named placeholders behave like normal tiles; the unknown variant **cannot be
inspected**.

**Components — agent views**

UX-DR23: **Agent view shell** — full-window scrim + `blur(16px)` overlay inset 32px, containing a
panel with an "AGENT VIEW" accent kicker, heading title, summary count, and a right-aligned
"Close · esc" pill. Enters as fade + 8px rise over 480 ms **on top of an already-complete layout**
(the entry animation is never inside the 250 ms budget). Body scrolls. `role="dialog"
aria-modal="true"` labeled by its heading; **Tab cycles within it while open**.

UX-DR24: **Suggestion row** (P0) — full-row-height thumbnail left, then action badge, name in
body-strong, mana cost, optional confidence right-aligned, and a one-line reason beneath. `live`
marks the row with `accent` (not `accent-dim`). Unknown-ID entries render the unknown placeholder
in the thumbnail slot **and still render their reason text**.

UX-DR25: **Swap row** (P1) — out/in tiles side by side joined by an accent arrow glyph, "Out · N
copies" / "In · N copies" labels tinted negative/positive — **tints on the labels only, never on
the art** — rationale right of the pair, StatChips for price/curve/confidence beneath. A swap whose
"in" card has 0 copies available renders normally reading "0 copies".

UX-DR26: **Tier row** (P1) — 132px chip carrying a 44px tier letter with its name beneath, then a
note and a thumbnail row. Buckets render in payload order; **empty buckets are skipped, not
rendered as empty shells**. Letters ramp `accent-bright` (S) · `accent` (A) · `text-primary` (B) ·
`text-secondary` (C) · `text-tertiary` (D), and **the letter is always accompanied by its name in
text** — color never carries rank alone.

UX-DR27: **Group section** (P1) — title + numeric count + rationale paragraph capped at ~900px
measure + wrapped tile row. **Tiles carry no quantity badge unless the card is in the active deck**
— the badge means "copies in this deck" and "×0" would be a lie. Empty groups are skipped.

UX-DR28: **Agent views nav (nav pills)** — one pill per view kind in the header. A pill is
**quiet/disabled and not focusable** until its kind has received a push this session (tooltip:
"Your agent hasn't sent this yet."); thereafter active, showing the last push's time, and carrying
an **accent unread dot** until its view is opened. Click/Enter re-opens that view.

**Components — system presence & states**

UX-DR29: **Connection pill** — bottom-left pill: an 8px dot (positive live · caution reconnecting ·
negative backend-gone, **all static, never pulsing**) plus micro text naming the state and the
active deck name. **The dot never carries the state alone.** Focusable; hover **or keyboard focus**
reveals port and instance ID from `GET /health` in a tooltip tied via `aria-describedby`.

UX-DR30: **State panel** — one shared centered shell (max-width 480px) for all four system states,
with headline, guidance body, and the concrete next action on its own line in body-strong accent
(commands in a monospace-styled inline chip). **No illustrations, no sad-face icons, no error
styling, no red alert fills, no toast color-coding.** One state panel at a time, in the left-column
area; the right column, nav and footer remain functional around it.

UX-DR31: **Skip link** — "Skip past the deck grid", the first Tab stop on every surface rendering a
populated grid, visually hidden until keyboard focus. Enter moves focus to the card detail panel
heading. The shipped control is a real **`<button>`, not an `<a href="#…">`** (c4-11 Q5, recorded
here at the 2026-08-07 code review so the conventional anchor idiom is not "restored" by a later
tidy-up): this app has no router, so a hash would write a history entry the app never reads, and a
browser does not move `document.activeElement` to a non-focusable fragment target anyway — the
imperative `tabIndex = -1` hand-off is required either way. **Withdrawn when a State panel
replaces the grid** — and also on an **empty deck**, which satisfies neither branch of that rule
as originally written (it renders no State panel and no populated grid) and where there is
**nothing to skip**: zero tiles and zero deck rows sit between the link and the right column, so
the link would save zero Tab stops. (An earlier form of this rule claimed the link's *target*
would not exist on an empty deck; that was false — `CardDetail` renders its frame and heading
unconditionally, and UX-DR20's "first card of the first type group" fills the panel's *content*,
not its heading. Corrected at the c4-11 code review, 2026-08-07.) The shipped condition is
therefore *a loaded deck with at least one card* — where "card" spans **every board including the
sideboard**, because c4-7's deck list renders a focusable row per sideboard card and a
sideboard-only deck still has a corridor of rows (c4-11 Q3, amended at the same review). It
exists because the grid sits between the header and the entire right column.

> **⚠️ MEASURED AT c4-11, 2026-08-07 — the "100+" figure this rule used to carry was stale by
> roughly half.** Over all 40 real decks, deriving the corridor from the shipped component tree:
> the run from the header to the first footer link is **206 Tab stops** on the largest deck,
> **median 78, mean 102.0**. The cause is **c4-7**'s deck list, which turned every card into a
> *second* focusable row — in the very column this link jumps into — and which did not exist when
> "100+" was written. **The link removes only the first 105 of the 206**: after using it the footer
> is still **101 stops away**, **19 of 40** decks remain more than 50 stops from the footer and
> **36 of 40** remain more than 20. See UX-DR40's flag; the residue is homed on **c8-6**.

UX-DR32: **Footer attribution** — one quiet full-width line, visible without scrolling on **every
surface**: "Card data and imagery courtesy of Scryfall. Unofficial Fan Content permitted under the
Wizards of the Coast Fan Content Policy. Not approved/endorsed by Wizards." Text in
`text-secondary` (9.3:1 — legally load-bearing, so a passing tier, not a muted one). Links
**persistently underlined** (identifiable at rest, not hover-only), open in a new tab, each with a
≥24px-tall hit area. **A condition of public release, not a design choice** (NFR-08).

**Copy (Voice and Tone)**

UX-DR33: Ship the specified copy verbatim for all nine states — no-active-deck, database not
initialized, database updating, disconnected/backend-restarted, unknown card, empty active deck,
empty push, image loading (silent), and nav-pill-before-first-push. Voice is **calm, second-person,
terminal-literate**: name commands and tools without apology, **never blame** ("something went
wrong" is banned), always give the concrete next action. No exclamation marks, no emoji, no mascot.

**Behavior & state**

UX-DR34: **Push arrival behavior** — a push **opens its view automatically**. Same-kind push while
that view is open replaces content in place with a crossfade (FR-08 replace semantics);
**different-kind** push switches to the new kind and marks the previous pill unread — **a push is
never silently swallowed**. Dismiss via the close pill, Esc, or a scrim click. **Dismissal never
clears content** — the view is re-openable from its pill for the rest of the session.

UX-DR35: **Deck refetch behavior** — on `deck_changed` matching the active deck, and on WS
reconnect, refetch. **During refetch the current deck stays on screen with a subtle header shimmer
— never a blank or a skeleton teardown of a populated view.** Coalesce to one in-flight request;
a newer event cancels and restarts; last response wins; out-of-order responses discarded. A 404
clears to no-active-deck. A pinned target that survives stays pinned; one that no longer exists
falls back to transient with the first card of the first group.

UX-DR36: **Placeholder-then-fill imagery** — render layout immediately with cached art where
available and silent wells elsewhere; images fade in over 100 ms as they arrive. **Layout never
reflows on image arrival** (fixed 63:88 slots). Skeletons are only for populated surfaces awaiting
refresh; placeholders are for content whose identity is known but whose art isn't. **Blank screens
are never shown after first paint.**

UX-DR37: **Agent-view / left-column interaction** — an open agent view **stays open and stays valid
when the left column falls to a state panel** (agent content is about cards, not deck presence);
on close the user lands on the state panel, and the skip link and grid Tab stops are withdrawn
while the grid is gone. A deck refetch completing behind an open view leaves it untouched and
**announces nothing from behind a modal**.

UX-DR38: **Overlay stack is exactly one level deep** — an agent view covers the window and nothing
opens over it; the detail panel is a persistent column that neither stacks nor traps.

**Interaction primitives**

UX-DR39: **Hover** sets the inspection target and reveals pill detail — and **every hover behavior
has focus parity**; hover is never the only way to reach information. **Click** is inspect and
navigate only: pin/unpin, open a view, dismiss a view, reveal pill detail — **nothing on the glass
mutates the deck**. **Esc** closes the topmost thing (open agent view first, then an active pin) and
never navigates or clears deck state. **Enter/Space** activates the focused element.
**Banned:** drag-and-drop, right-click menus, double-click semantics, hover-only disclosure of
unique information, and any control that edits the deck.

UX-DR40: **Tab order** is document order (nothing in the app carries a `tabindex`), and as of
c4-11 the enumeration below is the order the **shipped DOM actually produces**. Unbuilt stops are
marked as such rather than listed as if they existed:

> skip link → *(header nav pills — **c6-8**, Epic 6; and UX-DR28 makes a pill non-focusable until
> its kind has received a push, so on a cold-open session this stop never exists)* → card tiles in
> visual order, **each DFC's flip control immediately after its own tile** → **card detail: the
> unpin control (while pinned), the panel's own flip control (when the target is flippable), the
> oracle scroller** → deck-row list → **connection pill (c5-7 — SHIPPED 2026-08-08)** → footer
> links; inside an open agent view, Tab is trapped.

**What changed and why (c4-11 Q2).** The previous enumeration was wrong in both directions. It
named three stops that **cannot exist** — the nav pills and the connection pill are backlog, and
`AppShell.tsx:117` still renders a placeholder where the pills go — and it **omitted four that
already ship**: the card detail panel's unpin control (c4-5), its own copy of the flip control
(c4-6), the oracle scroller (c4-11) and the skip link's target heading while it holds
`tabindex="-1"`. `CardDetail.tsx:117-124` predicted the first omission by name and assigned the
correction here: *"c4-11 must add it to the enumeration rather than rediscover it."*

**The connection pill's DOM position WAS decided by nobody, and c5-7 decided it (dw:4597, CLOSED
2026-08-08).** Three stories each assumed someone else had fixed it — this rule put it between the
deck rows and the footer, c5-7 cited UX-DR47 and was silent on position, and c10-1 calls it *"the
last stop before the footer"* — while `DESIGN.md:479` places it physically **bottom-left**, in the
other column from the deck rows. c4-11 declined to decide it without the component and re-homed it
to **c5-7**, which built the component and ruled it (Brad, 2026-08-08):

> The pill is a sibling between `</main>` and `<footer>` in `AppShell.tsx` — **after both columns
> and immediately before the footer**, which is the enumeration above — while `ConnectionPill.css`
> pins it visually to the **bottom-left** corner with a `position: fixed` inset that clears the
> footer strip. Document order and visual position are therefore both satisfied, and the two
> readings that looked contradictory were only ever about different axes: this rule and c10-1 were
> describing TAB order, `DESIGN.md` was describing the SCREEN.

The rejected alternative is recorded because it is the one a later reader would reach for: an
in-flow last child of the LEFT column renders bottom-left with no fixed positioning at all, and
puts the pill *before the entire right column* in Tab order — contradicting this enumeration,
c10-1's wording, and (on any surface where the left column is a state panel) AC 1 as well.

*(Arrow-key grid navigation is explicitly deferred out of MVP — gate H3 — with the skip link as
sole mitigation and a **revisit-before-public-release flag**, since the Fan Content Policy links
sit behind the grid. **The cost, measured over all 40 real decks at c4-11: 206 Tab stops max /
78 median / 102.0 mean from the header to the first footer link; the skip link removes only the
first 105, leaving 101; 19 of 40 decks stay more than 50 stops from the footer and 36 of 40 stay
more than 20.** ⚠️ **Every one of those figures gains exactly +1 as of c5-7 and was not
re-measured** — the connection pill is an always-present stop inside this corridor, so the sweep's
numbers become 207 / 79 / 103.0 with 102 left after the skip link. The suite's pins were recomputed
from the DOM; the 40-deck sweep was not re-run. The flag is carried on **c8-6**, which actions or
re-accepts it.)*

✅ **Coverage-map double-assignments RESOLVED as deliberate splits — Brad's ruling at the C5
retro (2026-08-09, action item R9).** The defect first recorded here (c4-11 code review,
2026-08-07) was that UX-DR40 appears under **Epic 4 and Epic 8**, and UX-DR46 under **Epic 4 and
Epic 5**, unexplained. The ruling makes the explanation the record: the assignments are
complementary slices, now annotated in the UX-DR coverage table itself — Epic 4 builds the focus
floor (UX-DR46) and states the Tab-order cost (UX-DR40); Epic 5 extends 46 to connection-state
changes and the pill; Epic 8 (c8-6) decides at release whether 40's floor is enough. Both halves
of 46 shipped with tests in their own epics (Epic 4's deck-view focus ACs; c5-6/c5-7's
focus-survives-reconnect and pill-arrival assertions).

**Accessibility floor** (acceptance criteria, not polish)

UX-DR41: **Contrast** — all body text ≥ 4.5:1; large text ≥ 3:1; non-text indicators ≥ 3:1, with
the two no-headroom constraints of UX-DR6 enforced.

UX-DR42: **`prefers-reduced-motion` — implement the exhaustive inventory**, each motion with its
named fallback: agent-view bloom → appears in place; push-replace crossfade → instant swap;
card-tile hover pop → no scale, shadow only; image fade-in → instant; curve bar height → instant
jump; deck-row live tint → instant; accent glow → omitted (count text + live region carry the
signal); refetch header shimmer → static "Updating…" micro text; **DFC flip 3D rotation → instant
face swap**; **detail-panel content swap → instant, no crossfade** (it changes on every hover, so it
must never animate). **No element pulses or loops under any setting.** Any motion added later must
be added to this list with a fallback.

UX-DR43: **Motion is never the sole signal** — a deck change updates group-header counts and fires
the coalesced live-region announcement; the badge glow is garnish on top. A new push updates the
view heading, its timestamp, and the nav pill's unread marker.

UX-DR44: **Semantic structure** — deck name `h1`; panel titles and type-group headers `h2`; agent
view `role="dialog" aria-modal="true"` labeled by its `h2`; card grid, deck list and agent-view
lists as `ul`/`li`; state panel `role="region"` with its headline as `h2`; footer `<footer>`;
mana curve and color distribution as `figure`s whose accessible alternatives are the visually-hidden
table and the legend. Card detail panel is `role="region"` labeled "Card detail" and **is not a
live region**.

UX-DR45: **Live regions** — the connection pill, the agent-view heading, and a **separate polite pin
region** announce changes. **Transient hover/focus target changes must not announce** (sweeping a
cursor across a 60-card grid would flood the queue); only a pin announces, once: "Pinned — {card
name}." Deck refetches announce **exactly once per coalesced refetch**, on completion: "Deck
updated — 62 cards."

UX-DR46: **Focus management** — view open → focus to the view heading; in-place push replacement →
focus to the heading; view close → focus returns to the previously focused element. **Focus is
never dropped to `document.body`.** `focus-visible` ring on every focusable element,
keyboard-triggered only; no `outline: none` without the replacement.

UX-DR47: **Every interactive element is a real `<button>` or `<a>`** with a ≥ 24×24px hit box —
never a `<div>` with a click handler.

UX-DR48: **Alt text** — every card image's alt is the card name, **face-specific for DFCs**;
placeholders expose the same name. Thumbnails in rows that already show the name as text
(suggestion, swap, tier rows) use `alt=""`; grid tiles and the detail panel keep name alt because
there the image is the only carrier.

**Gate**

UX-DR49: **SC-5 is a human judgement by Brad** against DESIGN.md + EXPERIENCE.md before release —
it cannot be automated or delegated. Anti-patterns it tests against: raw JSON views, log panes,
dense ID tables, error pages, toast storms. With four analytical panels always on screen,
"deliberate product, not debug dashboard" is carried by typography, spacing and restraint rather
than by sparseness.

**UX rulings — CONFIRMED 2026-07-25**

The four rulings EXPERIENCE.md flagged as needing Brad's confirmation (and which the
validation-report explicitly did not test) are **all accepted as specified**. They are settled
inputs to story writing, not open questions:

1. **A push opens its agent view automatically.** Nav pills are the re-open/switch path and carry
   an unread dot. SC-1 therefore stands as written — 250 ms push-to-**render**, not
   time-to-notification.
2. **Inspection is hover-transient plus click-to-pin**, with full focus parity.
3. **The card detail panel is not a modal** — a persistent region, no focus trap, no return-focus
   contract. Only the agent view is modal; the overlay stack stays one level deep.
4. **Tier vocabulary is S/A/B/C/D**, empty buckets skipped. **Decided against adding F** — the
   DESIGN.md tier-letter ramp (`accent-bright` · `accent` · `text-primary` · `text-secondary` ·
   `text-tertiary`) is exactly five steps and is exhausted; `accent-dim` is the only unused token
   and is banned on `surface-overlay`, the surface tier rows sit on. A sixth letter would cost a
   colour decision plus a contract regeneration through the committed `.d.ts` and both mirrored
   plugin bundles.

**Open UX item carried into story work**

- **FR-18 session-history home is undecided** — extend the nav, or a strip inside each view's
  header. Blocks the history story in Epic 10, not any Phase-1 work.

### FR Coverage Map

Every FR maps to exactly one **owning** epic (where it is built and accepted). Where a second
epic consumes or completes it, that is noted as a contributor — the owner still holds acceptance.

| FR | Owner | Contributors | Note |
|---|---|---|---|
| FR-01 | Epic 1 | — | Port, fallback, single-instance |
| FR-02 | Epic 3 | Epic 4 | Endpoints owned by 3; consumed by 4 |
| FR-03 | Epic 3 | Epic 4 | Hydration cache is Epic 4's |
| FR-04 | Epic 3 | Epic 4 | Face resolution in 3; placeholder render in 4 |
| FR-05 | Epic 4 | — | Grid + list + curve as simultaneous columns |
| FR-06 | Epic 5 | — | `/agent/events` + WS relay + client count |
| FR-07 | Epic 6 | Epics 2, 3 | State slot + `GET`/`PUT /api/active-deck` in 3; no-active-deck panel in 2; MCP tool + deck-existence validation in 6 |
| FR-08 | Epic 6 | — | Tool + Suggestions view together |
| FR-09 | Epic 9 | — | Phase 2 |
| FR-10 | Epic 9 | — | Phase 2 |
| FR-11 | Epic 7 | — | Notifier + refetch + announcement |
| FR-12 | Epic 6 | Epic 7 | Outcome tokens in 6; notifier swallow in 7 |
| FR-13 | Epic 5 | Epics 4, 6 | ID-only contract in 5; hydration in 4; degradation in 6 |
| FR-14 | Epic 1 | — | Discovery file + `instance_id` |
| FR-15 | Epic 10 | Epic 5 | Pill shell + reconnect in 5; status detail in 10 |
| FR-16 | — | — | **Phase 3 — out of scope for this breakdown** |
| FR-17 | Epic 4 | — | Persistent detail panel, not a modal |
| FR-18 | Epic 10 | — | Phase 2; blocked on the UX residual decision |
| FR-19 | Epic 4 | Epic 3 | Flip control + placeholders in 4; `face` param in 3 |
| FR-20 | Epic 2 | Epic 8 | Identity + tokens in 2; SC-5 gate in 8 |
| FR-21 | — | — | **Phase 3 — out of scope for this breakdown** |
| FR-22 | Epic 1 | Epics 2, 3 | Lazy engine + 503 token in 1; state-panel surface + copy in 2; wiring + self-transition in 3 |
| FR-23 | Epic 9 | — | Phase 2 |

**NFR coverage**

| NFR | Owner | Contributors |
|---|---|---|
| NFR-01 | Epic 5 (ticket, Origin, token separation) | Epic 1 (bind 127.0.0.1, Host validation, CORS) |
| NFR-02 | Epic 1 (both CI boundary tests) | Epic 3 (WAL reads) |
| NFR-03 | Epic 2 (generation pipeline + drift check) | Epic 5 (envelope union) |
| NFR-04 | Epic 5 (WS backoff + ticket re-mint) | Epic 7 (refetch coalescing) |
| NFR-05 | Epic 4 (1 s deck render) | Epic 6 (250 ms push), Epic 10 (hardening) |
| NFR-06 | Epic 2 (self-hosted font) | Epic 3 (warm cache) |
| NFR-07 | Epics 1 + 2 (from the first commit) | all — cross-cutting, never a story of its own |
| NFR-08 | Epic 2 (footer attribution) | Epic 3 (rate-spacing), Epic 8 (release notice) |
| NFR-09 | Epic 3 (location + atomic writes) | Epic 8 (README + uninstall notes) |

**UX-DR coverage**

| Epic | UX-DRs |
|---|---|
| Epic 2 | 1, 2, 3, 5, 6, 7 (tokens, font, numerals, spacing, contrast, brand rules), 8 (layout shell), 9–13 (presentation-only primitives), 30 (state panel), 32 (footer), 33 (copy). **Mechanism only:** 4 (card-radius token defined here, enforced in Epic 4), 42 (reduced-motion mechanism here, per-motion inventory completed in Epics 4 and 6), 47 (lint rule here, applied in every later epic) |
| Epic 4 | 4 (card geometry enforced), 14–22 (card tile, DFC flip, quantity badge, curve, colour distribution, deck row, detail panel, format check, placeholder), 31 (skip link), 36 (placeholder-then-fill), 39–41 (interaction primitives, Tab order, contrast), 44–48 (semantics, live regions, focus, hit targets, alt text). *(35 — refetch — belongs wholly to Epic 7, where `deck_changed` originates. 40 and 46 are deliberate splits, ruled at the C5 retro: this epic builds the focus FLOOR (46) and states the Tab-order cost (40); Epic 5 owns 46's connection-state half, c8-6 owns 40's release-gate revisit)* |
| Epic 5 | 29 (connection pill behaviour), 46 (focus never dropped **across connection-state changes and the pill's arrival** — extends Epic 4's floor; deliberate split, ruled at the C5 retro) |
| Epic 6 | 23–24 (agent view shell, suggestion row), 28 (nav pills), 34 (push arrival), 37–38 (view/left-column interaction, overlay depth), 43 (motion never sole signal), 45 (live regions) |
| Epic 7 | 16 (quantity flash), 35 (refetch), 43, 45 (coalesced announcement) |
| Epic 8 | 49 (SC-5 gate), 40 (Tab-order revisit flag) |
| Epic 9 | 25–27 (swap row, tier row, group section) |
| Epic 10 | 28–29 (nav timestamps, pill detail) |

## Epic List

**10 epics.** Eight deliver Phase 1 (MVP); two deliver Phase 2. Phase 3 (FR-16, FR-21, Tauri,
UI-initiated edits) is explicitly out of scope — the last needs its own brief per AD-2.

**Deviations from EPIC-SPLIT.md, stated rather than silent:**

1. Its **E1 + E7** (backend skeleton, SPA foundation) become **Epics 1 + 2** — same content,
   resequenced so that Epic 1 + Epic 2 together deliver **SC-4**, a real user outcome, instead of
   two half-outcomes.
2. The **`openapi-typescript` pipeline moves from E4 to Epic 2**, standing itself up against the
   endpoints that exist after Epic 1 (`/health` + the typed error body). EPIC-SPLIT's own
   "land the generation pipeline early and change it rarely" argues for this; leaving it in the
   realtime epic would make the deck view (which needs REST types) wait on the WS work.
3. Its **E5** splits across **Epics 5 and 6** at the security/presentation seam: Epic 5 owns the
   channel (credentials, upgrade, envelope, relay), Epic 6 owns what the agent puts through it and
   what the user sees.
4. Its **E12 + E13** merge into **Epic 10** — FR-15, FR-18 and NFR-05 hardening are each too small
   to carry an epic and all land on the same surfaces.

**File-churn check — consolidation considered and rejected.** Six epics touch `ui/` (2, 4, 6, 7, 9,
10) and three touch `src/companion/app/` (1, 3, 5), so the overlap was assessed rather than
assumed. It is **incidental, not churn**: each epic owns distinct components within those trees —
tokens and shell, deck view, agent views, refetch, additional push kinds, history — and the splits
fall on genuine feedback boundaries, each closing a named success criterion (SC-4 at Epic 3, SC-5
answerable at Epic 4, SC-1 and SC-3 at Epic 6, SC-2 at Epic 7). Consolidating the frontend into one
epic would produce a ~40-story unit with no delivery checkpoint between "the app launches" and "the
app is finished", which is precisely the feedback loop the split exists to provide. No epic revisits
a component another epic has already completed.

### Epic 1: Launch the Companion

Brad can start the companion backend from a fresh install with one command, and it behaves like a
well-mannered local process: it claims a port (or falls back), publishes how to reach it, refuses
politely if it is already running, survives a missing database, and never leaves a booby-trapped
file behind on a clean exit. The boundary tests that make the read-only premise structural land
here, before there is any code to retrofit them against.

**FRs covered:** FR-01, FR-14, FR-22 (backend half)
**Also covers:** NFR-01 (bind, Host validation, CORS), NFR-02 (both CI boundary tests), NFR-07
**Governed by:** AD-1, AD-2, AD-3, AD-4, AD-10, AD-14, AD-15, AD-16
**Depends on:** nothing
**Note:** EPIC-SPLIT calls the two boundary tests the highest-leverage stories in the whole
feature. They are what make AD-2 and AD-3 real rather than aspirational.

### Epic 2: The Glass — Foundation, Identity & Honest States

Brad opens the URL and gets a real product: the Voltglass identity, the two-column composition,
and a calm panel that names exactly what to do next — whether the database isn't built yet, no
deck is set, or the backend went away. Nothing here is a placeholder for a later epic; the
system-state surfaces are the finished article.

**FRs covered:** FR-20 (visual identity + token system), FR-22 (state-panel surface + copy; the
wiring and self-transition land in Epic 3, where the 503 originates)
**Also covers:** NFR-03 (generation pipeline + CI drift check), NFR-06 (self-hosted font),
NFR-07 (eslint/prettier/vitest in CI), NFR-08 (footer attribution)
**Governed by:** AD-12, AD-13
**Depends on:** Epic 1
**Note:** carries the greenfield `ui/` scaffold — the only new toolchain in the feature. The
TypeScript `>=5.9,<6.1` pin is load-bearing and belongs to the scaffold story.

### Epic 3: Deck Data & Card Imagery on Tap

The backend can answer everything the glass will ever ask about a deck and its art: decks, a full
decklist, canonical card data, and card faces fetched once from Scryfall and cached on disk
forever. This is the epic that touches an external service, so it owns all the pacing, caching,
failure and attribution behaviour in one place.

**FRs covered:** FR-02, FR-03, FR-04, FR-22 (UI wiring + self-transition — closes **SC-4**),
FR-07 (backend state slot + both transports; the MCP tool is Epic 6's)
**Also covers:** NFR-02 (WAL reads), NFR-06 (warm cache), NFR-08 (rate-spacing), NFR-09 (cache
location + atomic writes), CM-2
**Governed by:** AD-11, AD-16
**Depends on:** Epic 1 (independent of Epic 2)
**Note:** the only externally-paced work in the feature. A cold 100-card deck at ~12 MB / ~10 s to
fully paint is an **expected observation in acceptance, not a defect**.

### Epic 4: The Deck on the Glass

Brad sees his deck as full card faces with quantity badges, reads any card in the persistent
detail panel by moving his cursor, flips a double-faced card, and takes in the curve, colour
spread, type-grouped list and format check without a single click. This is the first epic where
**SC-5** becomes answerable and the largest UX surface in the feature.

**FRs covered:** FR-05, FR-17, FR-19
**Also covers:** NFR-05 (1 s deck render, warm cache)
**Governed by:** AD-11, AD-12 (single card-hydration cache), AD-16
**Depends on:** Epics 2, 3
**Note:** the DFC flip control (UX-DR15) is the densest single component in the feature — it was
the UX gate's H2 and carries a dozen distinct rules. The accessibility floor is acceptance
criteria here, not polish.

### Epic 5: The Agent's Channel

The pipe from agent to glass exists and is safe: two credentials that never touch, an
authenticated WebSocket the browser holds open and re-establishes on its own, one envelope shape
both halves of the codebase agree on, and a CI check that stops them ever disagreeing. Brad can
watch the connection state and see the app recover from a backend restart without touching it.

**FRs covered:** FR-06, FR-13 (ID-only contract), FR-15 (pill shell + reconnect behaviour)
**Also covers:** NFR-01 (ticket, Origin, token separation), NFR-03 (envelope union), NFR-04
**Governed by:** AD-5, AD-6, AD-7 (payload shapes and caps as models, and their enforcement at the
ingest endpoint; AD-8's tool-side vocabulary is Epic 6's), AD-10 (the single real-socket test), AD-12
**Depends on:** Epics 3, 4 — the reconnect refetch (Story 5.6) and the connection pill's active-deck
name (Story 5.7) both read deck state, so this epic sits after the deck view rather than beside it
**Note:** `contracts.py` is the one serialisation worth respecting — every later epic reads it,
and AD-12's drift check means a late change ripples through a committed `.d.ts` and both mirrored
bundles. Carries the single real-socket integration test (AD-10).

### Epic 6: The Agent Pushes to the Glass

Brad asks his agent a question and the answer appears on the glass: the agent sets the active
deck, pushes suggestions, and the view blooms open within 250 ms with art-forward rows he can read
without clicking. When the app is closed or the tab is gone, the agent says so in one calm line
and presents the content in chat as usual — nothing is ever lost. This closes **SC-1** and **SC-3**.

**FRs covered:** FR-07, FR-08, FR-12
**Also covers:** FR-13 (per-entry degradation), NFR-05 (250 ms push-to-render), CM-1
**Governed by:** AD-7, AD-8, AD-16
**Depends on:** Epics 4, 5
**Note:** the four UX rulings land here and are **confirmed as of 2026-07-25** — a push auto-opens
its view, so SC-1 stands as 250 ms push-to-render and this epic's acceptance criteria are settled.

### Epic 7: The Deck Updates Itself

Brad tells the agent to add a card and the glass changes by itself — the card appears in its type
group, the curve grows, the colour spread shifts, and a screen reader hears it once. He never
touches the app. This is UJ-1's climax and closes **SC-2**.

**FRs covered:** FR-11
**Also covers:** FR-12 (emission failure swallowed), NFR-04 (coalescing, latest-wins)
**Governed by:** AD-9
**Depends on:** Epics 4, 5, 6 — Story 7.6's "an agent view survives a refetch behind it" needs the
agent view to exist
**Note:** the "fire-and-forget means bounded-timeout `await`, not a detached task" rule is the
whole point of this epic — a `create_task` that outlives its tool call silently goes stale.

### Epic 8: Release Readiness

The companion is something Brad would put in front of strangers: `view_deck` points at its
replacement, the docs tell you where the image cache lives and how to remove it, the PRD no longer
contradicts the architecture, and Brad has personally judged the thing against the UX spec and
said yes.

**FRs covered:** FR-20 (SC-5 acceptance gate)
**Also covers:** NFR-08 (Fan Content notice), NFR-09 (README + uninstall notes)
**Governed by:** AD-13, AD-15
**Depends on:** Epics 4, 6, 7
**Note:** **SC-5 is a human judgement by Brad and cannot be automated or delegated.** This epic
also carries the three owed PRD amendments and the pre-public-release Tab-order revisit flag.

### Epic 9: The Remaining Push Kinds *(Phase 2)*

The agent gains its full vocabulary: proposed swaps as out/in pairs, tier lists, and titled card
groups with a paragraph of reasoning each — including cards the deck doesn't yet run. Deliberately
cheap, because Epics 5 and 6 settled the envelope and the payload discipline: three new tools,
three new views, no new seam.

**FRs covered:** FR-09, FR-10, FR-23
**Governed by:** AD-6, AD-7
**Depends on:** Epic 6

### Epic 10: Session History, Status Detail & Performance Polish *(Phase 2)*

Brad can revisit what the agent showed him earlier in the session, see at a glance which port and
instance he's connected to, and the 250 ms / 1 s budgets are measured rather than assumed.

**FRs covered:** FR-15 (status detail), FR-18
**Also covers:** NFR-05 (hardening — profiling beyond the Phase-1 baseline)
**Governed by:** AD-6, AD-7, AD-11
**Depends on:** Epics 6, 7
**Note:** FR-18 is **blocked on a UX decision** — the session-history home (extend the nav, or a
strip inside each view's header) is the UX spine's open residual.

---

## Epic 1: Launch the Companion

Brad can start the companion backend from a fresh install with one command, and it behaves like a
well-mannered local process: it claims a port (or falls back), publishes how to reach it, refuses
politely if it is already running, survives a missing database, and never leaves a booby-trapped
file behind on a clean exit. The boundary tests that make the read-only premise structural land
here, before there is any code to retrofit them against.

### Story 1.1: Companion package skeleton with CI-enforced import boundaries

As a developer building the companion,
I want the read-only and leaf/app import boundaries enforced by CI before any companion code exists,
So that the single-writer premise is structural rather than aspirational, and no later story can quietly breach it.

**Acceptance Criteria:**

**Given** a new `src/companion/` package containing only `__init__.py` and `app/__init__.py`
**When** the default `uv run pytest` run executes
**Then** `tests/unit/companion/test_import_boundary.py` passes with no marker required
**And** `ruff check`, `ruff format --check` and `mypy --strict` pass over the new package from this commit (NFR-07)

**Given** any module under `src/companion/**` that references a repository write method, `session.add`, `session.commit`, or `session.delete`
**When** the write-guard test AST-walks the package
**Then** the test fails, naming the offending module, symbol and line (AD-2)
**And** the failure message states that `src/mcp_server` is the sole writer

**Given** a module under `src/mcp_server/**`
**When** the leaf/app guard inspects its imports
**Then** an import of `src.companion.contracts`, `src.companion.discovery` or `src.companion.client` passes
**And** an import of `src.companion.app` or any of its submodules fails the test (AD-3)

**Given** a leaf module (`contracts.py`, `discovery.py`, `client.py`)
**When** the leaf/app guard inspects its imports
**Then** only stdlib, `pydantic`, `httpx` and `src.paths` are permitted
**And** any `fastapi`, `uvicorn` or `sqlalchemy` import fails the test (AD-3)

**Given** any module outside `src/companion/app/`
**When** it imports anything under `src/companion/app/`
**Then** the leaf/app guard fails

**Given** the guards are AST-based rather than import-based
**When** they run
**Then** they require no FastAPI or uvicorn install to execute
**And** they detect violations in modules that are never imported at runtime

### Story 1.2: Side-effect-free ASGI app with a lifespan and a health endpoint

As a developer,
I want `build_app()` to construct the ASGI application without touching anything outside the process,
So that the whole backend is testable in-process without binding a port or overwriting real files on disk.

**Acceptance Criteria:**

**Given** a test that calls `build_app()`
**When** construction completes
**Then** no port is bound, no file is written, no directory is created and no database engine exists (AD-10)
**And** the returned app is drivable over `httpx.ASGITransport` with no network

**Given** the application starts under its lifespan
**When** startup completes
**Then** a per-process `instance_id` is minted and held in application state
**And** the `instance_id` is stable for the process lifetime and different on every restart

**Given** a running application
**When** a client calls `GET /health`
**Then** the response is `200` with a typed body carrying at least `{status, instance_id}` (FR-14)
**And** the endpoint requires no authentication, because it is what callers use *before* deciding to send a token

**Given** the application shuts down cleanly
**When** the lifespan exits
**Then** every resource acquired at startup is released
**And** no exception escapes the shutdown path

### Story 1.3: Port selection with ephemeral fallback and a printed launch URL

As Brad launching the companion,
I want the backend to take port 8765 when it is free and quietly pick another when it is not,
So that a port conflict never blocks me and I always know from the terminal where to point my browser.

**Acceptance Criteria:**

**Given** port 8765 is free
**When** the backend starts
**Then** it binds `127.0.0.1:8765` (FR-01)
**And** it prints the reachable URL to stdout (AD-15 — the companion process owns its stdout)

**Given** port 8765 is occupied by an unrelated process
**When** the backend starts
**Then** it falls back to an ephemeral port rather than exiting (FR-01)
**And** it prints the actual URL it bound, not the default

**Given** an explicit port is supplied by configuration
**When** the backend starts
**Then** that port is attempted first
**And** the same ephemeral fallback applies on conflict

**Given** the backend has bound a port
**When** application state is inspected
**Then** the actual bound port is readable from state
**And** nothing else in the codebase hardcodes 8765 except the default bind attempt (AD-4)

**Given** the socket is opened
**When** the bind address is inspected
**Then** it is `127.0.0.1` only, never `0.0.0.0` (NFR-01)

### Story 1.4: Typed REST error contract with closed reason tokens

As a UI developer,
I want every non-2xx response to carry one token from a closed set,
So that each backend failure maps 1:1 onto a defined user-facing state instead of a guess.

**Acceptance Criteria:**

**Given** the error contract module
**When** its reason token type is inspected
**Then** it is a closed enum of exactly `deck_not_found`, `database_not_initialized`, `database_unavailable`, `invalid_request`, `payload_too_large`, `internal_error` (AD-16; `internal_error` and the 413 status for `payload_too_large` added by the c1-4 review ruling, Brad 2026-07-25)
**And** adding a UI state requires adding a token here first

**Given** any endpoint raises a defined failure
**When** the response is returned
**Then** the body is the single typed error model carrying its `reason` token
**And** the HTTP status code carries the outcome — `404`, `503`, `400`, `422` respectively

**Given** a successful response
**When** its body is inspected
**Then** it is the existing Pydantic schema **unwrapped** — no `{"status": "ok", ...}` envelope (AD-16)
**And** the MCP `status`-enum convention does not appear anywhere in the REST layer

**Given** an unhandled exception inside a route
**When** it propagates
**Then** the client receives the typed error body, never a stack trace or an untyped 500 page
**And** the exception is logged to stderr with `%`-style lazy args

### Story 1.5: Localhost-only security envelope — Host validation and CORS

As Brad running the companion beside a browser,
I want the backend to refuse requests that did not address it as localhost,
So that a malicious web page I happen to have open cannot reach into the app through DNS rebinding.

**Acceptance Criteria:**

**Given** a request carrying `Host: 127.0.0.1:{bound_port}` or `Host: localhost:{bound_port}`
**When** it reaches any endpoint
**Then** it is processed normally (NFR-01, AD-5)

**Given** a request carrying any other `Host` value — including a rebound domain name or a mismatched port
**When** it reaches any endpoint
**Then** it is rejected before the route handler runs
**And** the rejection uses the typed error body from Story 1.4 with `reason: "invalid_request"` (AD-16)

**Given** the bound port was chosen by ephemeral fallback
**When** Host validation runs
**Then** it validates against the **actual** bound port from application state, not the configured default

**Given** a cross-origin request from any origin other than the app's own
**When** CORS preflight runs
**Then** it is refused (NFR-01)

**Given** the validation is implemented as middleware
**When** a later story adds the WebSocket upgrade
**Then** the same Host check applies to the upgrade path without duplication (AD-5)

### Story 1.6: Lazy database engine so a fresh install starts instead of erroring

As Brad on a brand-new machine,
I want the companion to start before the card database exists,
So that a fresh install is a guided next step rather than a crash on first run.

**Acceptance Criteria:**

**Given** the SQLite database file does not exist
**When** the backend starts
**Then** startup succeeds and the process stays up (FR-22, AD-10)
**And** no engine is created at startup

**Given** the database is absent
**When** a client calls any data-backed endpoint
**Then** the response is `503` with `reason: "database_not_initialized"` (AD-16)
**And** `GET /health` still returns `200`, because the process itself is healthy

**Given** the database is present
**When** the first data-backed request arrives
**Then** the engine is created on demand and reused for subsequent requests
**And** the engine uses the same single session-factory recipe as the MCP side (AD-2)

**Given** the database exists but a read fails transiently — for example during a bulk refresh
**When** the failure is caught
**Then** the response is `503` with `reason: "database_unavailable"`, distinct from `database_not_initialized` (AD-16)

**Given** the database appears while the backend is running
**When** the next data-backed request arrives
**Then** it succeeds without a restart

### Story 1.7: Discovery file as the sole rendezvous

As a companion MCP tool,
I want the backend to publish where it is and how to authenticate in one atomically written file,
So that I can find a running app without hardcoding a port and without ever reading a half-written file.

**Acceptance Criteria:**

**Given** the backend starts
**When** the lifespan runs
**Then** `{port, token, instance_id}` is written to `src.paths.data_dir()/companion.json` (FR-14, AD-4)
**And** the location honours `PLANESWALKER_DATA_DIR`, so tests and parallel dev instances isolate for free

**Given** the file is being written
**When** the write occurs
**Then** it is written to a temporary file and renamed into place (AD-4)
**And** no reader can observe a partially written file

**Given** the backend shuts down cleanly
**When** the lifespan exits
**Then** the discovery file is removed (FR-14)

**Given** the token is minted
**When** its value is inspected
**Then** it is cryptographically random, per-process, and different on every restart
**And** it appears in no log line, no HTML, no REST response and no WebSocket frame (AD-5)

**Given** a reader in the leaf `discovery.py`
**When** it encounters a missing, unparseable or truncated file
**Then** it reports *app not running* rather than raising (AD-4)

**Given** the backend bound an ephemeral port
**When** the discovery file is written
**Then** it records the actual bound port

### Story 1.8: Single-instance enforcement with verified identity

As Brad who forgot the backend was already running,
I want a second launch to tell me so and exit,
So that I never end up with two instances fighting over one discovery file and a browser pointed at the wrong one.

**Acceptance Criteria:**

**Given** a discovery file exists and a `GET /health` against its port returns an `instance_id` matching the file
**When** a second backend process starts
**Then** it exits with a clear "already running" message naming the live URL (FR-01, AD-4)
**And** it does **not** overwrite or delete the existing discovery file

**Given** a discovery file exists but nothing answers on its port
**When** a new backend starts
**Then** it reclaims the stale entry and starts normally (FR-01)

**Given** a discovery file exists and something answers on its port but the `instance_id` does not match — a foreign process on a recycled port
**When** a new backend starts
**Then** the entry is treated as dead and reclaimed
**And** no token is ever sent to the foreign process (AD-4)

**Given** the previous run crashed without cleaning up
**When** the next backend starts
**Then** the stale file is reclaimed without manual intervention (AD-15)

**Given** identity verification is needed by both the startup check and, later, by the companion tools
**When** the probe is implemented
**Then** it lives in the leaf so both callers share one implementation (AD-3)

### Story 1.9: One console script that dispatches, without disturbing the MCP server

As Brad following the README,
I want `uv run artificial-planeswalker companion` to start the backend while the bare command still runs the MCP server,
So that there is a single documented entry point and no existing MCP client configuration breaks.

**Acceptance Criteria:**

**Given** `artificial-planeswalker` is invoked with no arguments
**When** it runs
**Then** it starts the MCP server exactly as today, with identical stdio behaviour (AD-14)
**And** a regression test asserts stdout carries only the JSON-RPC stream

**Given** `artificial-planeswalker companion` is invoked
**When** it runs
**Then** it starts the companion backend in the foreground and prints its URL (AD-14, AD-15)
**And** Ctrl-C shuts it down cleanly, removing the discovery file

**Given** an unknown subcommand is supplied
**When** it runs
**Then** it exits non-zero with usage text naming the valid subcommands

**Given** `.mcp.json` and `plugin/.mcp.json` invoke `python -m src.mcp_server` directly
**When** this story lands
**Then** neither file needs changing, and a test asserts both still resolve (AD-14)

**Given** the companion backend is running under this entry point
**When** it logs
**Then** it logs freely to stdout and stderr, because it owns them — unlike the MCP process (AD-15)

**Given** a companion instance is starting (Brad's ruling 2026-07-26, closing the two c1-8 residuals
homed in `deferred-work.md`: the check-then-act launch race and, through it, the only reachable path
to `remove_discovery`'s ownership-guard TOCTOU — the finding Greptile held PR #15 at 3/5 over)
**When** it acquires single-instance mutual exclusion
**Then** it holds an OS-level advisory lock on a lock file under `src.paths.data_dir()` for the
process's whole lifetime (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX) — the **held-lock**
design, never create-and-delete-on-exit: the kernel releases the lock on any death, so AD-15's
crash-is-ordinary stance holds with no stale-lock state and no PID heuristics
**And** a second launch that fails the non-blocking acquire refuses without racing — c1-8's probe
still supplies the *who/where* for the refusal message, the lock supplies the atomic *whether*
**And** the lock file is a separate file from `companion.json` (the rendezvous stays c1-7's atomic
publish; the lock is never read for data) and lives under `PLANESWALKER_DATA_DIR` isolation so the
autouse test fixture keeps tests contention-free

---

## Epic 2: The Glass — Foundation, Identity & Honest States

Brad opens the URL and gets a real product: the Voltglass identity, the two-column composition,
and a calm panel that names exactly what to do next — whether the database isn't built yet, no
deck is set, or the backend went away. Nothing here is a placeholder for a later epic; the
system-state surfaces are the finished article.

### Story 2.1: Frontend scaffold with the full quality gate from the first commit

As a developer,
I want the `ui/` project created with linting, formatting, unit testing and type checking wired into CI on day one,
So that the frontend is born under the same discipline as the Python side rather than having it retrofitted.

**Acceptance Criteria:**

**Given** a fresh checkout
**When** `npm ci && npm run build` runs in `ui/`
**Then** the build succeeds on Node >= 20
**And** Node is required only for development and CI — never at install or runtime of the Python package (NFR-07, AD-13)

**Given** `package.json` is inspected
**When** the TypeScript dependency is read
**Then** it is pinned `>=5.9,<6.1`, **not** an open floor
**And** a comment or ADR reference records why: `typescript-eslint` publishes a peer range of `<6.1.0`, so an open floor resolves to TypeScript 7 and breaks `npm ci` and the ESLint gate outright

**Given** the scaffold
**When** its stack is inspected
**Then** it is Vite >= 8, React >= 19.2, zustand >= 5.0
**And** no second data-fetching or state-management library is present (AD-12)

**Given** CI runs
**When** the frontend job executes
**Then** eslint, prettier `--check`, `tsc --noEmit` and vitest all run and gate the build (NFR-07)
**And** the eslint config includes accessibility rules that fail on a click handler attached to a non-interactive element (UX-DR47)

**Given** any component is written
**When** eslint runs
**Then** `outline: none` without a replacement focus style is reported (UX-DR46)

**Given** the Vite dev server runs on its own port and proxies to the companion backend
**When** the proxy is configured
**Then** it sets `changeOrigin: true` so the proxied request carries a loopback `Host`
**And** a test or documented check asserts it, because without the rewrite **every** proxied call
returns c1-5's typed `400 {"reason": "invalid_request"}` from `HostValidationMiddleware`
> *Ruling R1 (Brad, C1 retro 2026-07-26) — closes c1-5 Open Question 2. The dev proxy is the
> committed dev workflow; the second origin it creates in development is accepted, and the
> `changeOrigin` requirement is asserted rather than left to be discovered as a confusing 400. See
> `epic-c1-retro-2026-07-26.md` §Rulings.*

**Given** this story is the first since c1-2 permitted to edit `.github/workflows/ci.yml`
**When** the frontend job is added
**Then** the opposite-platform mypy invocation (`mypy src/ --platform linux` alongside `mypy src/`)
is added to the same gate
> *C1 retro action item 3. `src/companion/app/singleton.py` branches on `sys.platform` and each
> mypy run type-checks only its own half; today the POSIX half is covered only because CI happens
> to run on ubuntu, and the Windows half only by Brad's local runs.*

### Story 2.2: The backend serves the built SPA as a committed artifact

As Brad installing the plugin,
I want the browser UI to arrive already built inside the Python package,
So that opening the URL shows the app with no Node toolchain anywhere on my machine.

**Acceptance Criteria:**

**Given** `npm run build` runs in `ui/`
**When** it completes
**Then** the bundle is emitted to `src/companion/app/static/` (AD-13)
**And** that directory is committed to the repository

**Given** the backend is running
**When** a browser requests `/`
**Then** the SPA index is served from `src/companion/app/static/` (FR-01)
**And** client-side routes fall back to the index rather than 404ing

**Given** the committed bundle is stale relative to `ui/` source
**When** CI runs
**Then** it rebuilds and fails on `git diff --exit-code`, mirroring the existing `plugin/` drift-check pattern (AD-13)

**Given** the bundle changes
**When** the plugin tree is rebuilt
**Then** `plugin/` receives the mirrored copy through the existing machinery
**And** both copies are treated as generated artifacts — a test or CI check asserts neither is hand-edited (AD-13)

**Given** a fresh install with no Node present
**When** the backend starts and the URL is opened
**Then** the app renders (SC-4)

### Story 2.3: TypeScript types generated from the backend's own OpenAPI, drift-checked in CI

As a developer on either side of the wire,
I want the UI's types generated from the backend's OpenAPI output and checked in CI,
So that a Python schema change cannot silently diverge from the TypeScript that consumes it.

**Acceptance Criteria:**

**Given** the backend exposes `app.openapi()`
**When** the generation script runs
**Then** `openapi-typescript` emits `ui/src/api/types.d.ts` (AD-12, NFR-03)
**And** that file is committed

**Given** a Pydantic model changes without regenerating
**When** CI runs
**Then** it regenerates and fails on `git diff --exit-code`, naming the drifted file (AD-12)

**Given** the pipeline
**When** its inputs are inspected
**Then** exactly one generator produces both the REST types and — once Epic 5 lands — the WebSocket envelope union, because `POST /agent/events` declares the envelope as its request body (AD-12)
**And** no second generation tool and no dummy endpoint exist

**Given** the UI consumes an API response
**When** the code is type-checked
**Then** it reads the generated types
**And** it never re-declares a shape the backend already describes, and never assumes DB schema (NFR-03)

**Given** `openapi-typescript` is a dependency
**When** the dependency graph is inspected
**Then** it is dev/CI only

### Story 2.4: The Voltglass token layer

As a developer building any surface,
I want every colour, type role, radius, space, motion and elevation value available as a named token,
So that the identity is enforced by construction and a hard-coded literal is a visible defect.

**Acceptance Criteria:**

**Given** the token stylesheet
**When** its custom properties are compared to `DESIGN.md` frontmatter
**Then** every token name matches byte-for-byte (UX-DR1)
**And** it defines 26 colours, 7 typography roles, the 4 radii plus the card radius, the 7-step spacing scale plus gutter and panel-gap, 4 motion durations, 3 easings, the focus ring, and 3 elevation tokens

**Given** any component stylesheet in `ui/`
**When** a lint rule inspects it
**Then** a hard-coded hex or `rgba()` literal fails (UX-DR1)
**And** a hard-coded `box-shadow` or `border-radius` literal fails — because a literal *rest* shadow inverts the hierarchy under shadowless themes, where `shadow-raise` is the live state

**Given** the surface ramp
**When** a component nests inside another
**Then** it steps exactly one level `well → base → panel → overlay`, never skipping two (UX-DR1)

**Given** a spacing value anywhere in the UI
**When** it is inspected
**Then** it comes from the 4/8/12/16/24/32/48 scale — the imported mock's 18/14/9/7px values are drift and are not reproduced (UX-DR5)

**Given** `accent-dim` is used
**When** the surface behind it is `surface-overlay`
**Then** the usage fails review or lint, because the pair is 2.70:1 and fails the 3:1 non-text floor — `accent` is the substitute (UX-DR6)

**Given** the user has `prefers-reduced-motion: reduce` set
**When** any tokenised transition runs
**Then** the shared motion mechanism resolves it to its non-animated fallback (UX-DR42)
**And** the mechanism is the single place later epics register their own motion fallbacks
**And** no element pulses or loops under any setting

**Given** the MVP ships Voltglass only as `:root`
**When** the token layer is authored
**Then** it is structured so an alternate `[data-theme]` block could be added later without touching component code

### Story 2.5: Self-hosted Space Grotesk with offline parity and tabular numerals

As Brad using the app with no network,
I want the typeface to load from the app's own assets,
So that the product looks identical offline, which is its entire posture.

**Acceptance Criteria:**

**Given** the app is loaded with all external network access blocked
**When** it renders
**Then** Space Grotesk displays, not the `system-ui` fallback (UX-DR2, NFR-06)
**And** no `@import` or `<link>` to a font CDN exists anywhere in the bundle

**Given** the font files
**When** the build runs
**Then** they are bundled with the backend's static assets and served from the same origin (AD-13)

**Given** any count, quantity, price or axis value renders
**When** its computed style is inspected
**Then** `font-variant-numeric: tabular-nums` is applied (UX-DR3)

**Given** the CSS `font` shorthand cannot carry `font-variant-numeric`
**When** the numeric role is applied
**Then** the role and its numeric-features property are applied together
**And** a lint rule or unit test fails on the numeric role being applied alone

**Given** any text on a dark surface
**When** its weight is inspected
**Then** it is 400 or above, and no second font family is introduced (UX-DR2)

### Story 2.6: The two-column application shell

As Brad snapping the browser beside my terminal,
I want the app laid out as a header, two columns and a pinned footer,
So that the deck and its analysis are both visible at once at the window sizes I actually use.

**Acceptance Criteria:**

**Given** a viewport between ~1100px and ~2560px
**When** the app renders
**Then** it composes a full-width header, a fluid left column, a 452px fixed right column, and a full-width footer pinned to the window bottom (UX-DR8)
**And** panels float with visible canvas between them at the panel-gap, framed by the 32px gutter

**Given** a viewport narrower than ~1100px
**When** the app renders
**Then** the right column drops beneath the left rather than compressing (UX-DR8)

**Given** the reference width of 1720px
**When** the layout is compared against the composition reference
**Then** proportions match the design intent

**Given** the page renders at any supported width
**When** the body is inspected
**Then** it never scrolls horizontally

**Given** an agent view will later overlay the window
**When** the shell is built
**Then** it reserves a full-window overlay slot inset by 32px, so Epic 6 adds the view without restructuring the shell (UX-DR8)

### Story 2.7: Presentation-only primitives — Panel, Badge, StatChip, Group header

As a developer building every later surface,
I want the four pure container and label primitives available and tokenised,
So that panels, badges, stat chips and group dividers look identical everywhere without being reimplemented.

**Acceptance Criteria:**

**Given** the `Panel` component
**When** it renders
**Then** it supports a default and an `overlay` level, an optional header carrying a label title plus an optional numeric count plus right-aligned badges, and a `live` state that swaps the title to accent, adds a 6px accent dot and raises elevation to `shadow-raise` (UX-DR9)
**And** its rest elevation is `shadow-rest`, applied via token

**Given** the `Badge` component
**When** it renders in each of its five tones — neutral, accent, positive, negative, caution
**Then** each tints background and border from its own semantic token, never from a hard-coded RGB (UX-DR10)

**Given** the `StatChip` component
**When** it renders
**Then** it shows a micro label above a 17px numeric value, with an optional delta tinted positive or negative by sign (UX-DR11)

**Given** the `Group header` component
**When** it renders
**Then** it shows an uppercase label with a right-aligned numeric count over a hairline rule (UX-DR12)

**Given** all four primitives
**When** their implementation is inspected
**Then** they hold no state, respond to no interaction, and have no behavioural contract beyond rendering their props — this is deliberate and recorded, not an omission (UX-DR9–12)

**Given** each primitive
**When** vitest runs
**Then** unit tests cover every documented variant and state

### Story 2.8: ManaPip and ManaCost with complete Scryfall cost parsing

As Brad reading a card's cost anywhere in the app,
I want every symbol in a mana cost rendered,
So that a cost is never quietly wrong — and never looks like a Wizards mana symbol.

**Acceptance Criteria:**

**Given** a `ManaPip`
**When** it renders
**Then** it is a plain filled circle in the relevant `mana-*` token, with an inverse-coloured numeral for generic costs (UX-DR13)
**And** it is deliberately not a mana-symbol shape, and carries no set or planeswalker-symbol likeness (UX-DR7)

**Given** a Scryfall cost string containing braces, hybrid such as `{W/U}`, generic-hybrid such as `{2/R}`, Phyrexian, and `{X}`
**When** `ManaCost` parses it
**Then** every symbol renders — hybrid as a split or dual-tinted pip (UX-DR13)

**Given** a cost string containing a symbol the parser does not recognise
**When** it renders
**Then** the symbol is surfaced visibly rather than silently dropped (UX-DR13)
**And** a unit test asserts this, because silent dropping is the failure mode that makes a cost wrong without looking wrong

**Given** an empty or absent cost — a land, for instance
**When** `ManaCost` renders
**Then** it renders nothing, without error

**Given** the `mana-*` tokens
**When** their usage across the codebase is inspected
**Then** they appear only as data ink — pips, colour bars, stacked curve segments — and never colour a button, border, background or an unstacked curve bar (UX-DR7)

### Story 2.9: The shared state panel and every system-state message

As Brad when something isn't ready,
I want a calm panel that tells me plainly what is happening and exactly what to do next,
So that I am never shown an error page or left guessing at a terminal command.

**Acceptance Criteria:**

**Given** the `State panel` component
**When** it renders
**Then** it is centred, max-width 480px, on `surface-panel` with a hairline border and large radius, carrying a heading, guidance body copy, and the concrete next action on its own line in body-strong accent (UX-DR30)
**And** a command inside the next action renders as a monospace-styled inline chip on `surface-well`

**Given** any system state
**When** its panel renders
**Then** there is no illustration, no icon, no red fill, no exclamation mark and no error styling (UX-DR30)
**And** exactly one state panel shows at a time, occupying the left-column area while the right column, header nav and footer remain functional around it

**Given** the four system states
**When** their copy is inspected
**Then** it matches `EXPERIENCE.md` verbatim for no-active-deck, database-not-initialized, database-updating and disconnected/backend-restarted (UX-DR33)

**Given** the `internal_error` (500) reason token — added to AD-16's closed set by the c1-4 review ruling (Brad, 2026-07-25), whose state panel is homed **here**
**When** the backend reports an unhandled bug
**Then** a fifth state panel renders with its own EXPERIENCE.md-reviewed copy — deterministic, so it must **not** quietly retry the way database-updating does; the concrete next action is restarting the companion / reporting the bug (UX-DR30, UX-DR33)

**Given** the no-active-deck state
**When** it renders
**Then** it lists available deck names beneath the guidance, **non-clickable** — the agent drives (UX-DR33, NG1)

**Given** any copy anywhere in the app
**When** it is reviewed
**Then** it is second-person and terminal-literate, names commands and tools without apology, never blames, always gives a concrete next action, and contains no exclamation marks, emoji or mascot (UX-DR33)
**And** the string "something went wrong" appears nowhere

**Given** the panel is rendered
**When** its semantics are inspected
**Then** it is `role="region"` with its headline as an `h2` (UX-DR44)

### Story 2.10: Footer attribution on every surface

As the maintainer publishing this app,
I want the Scryfall and Wizards Fan Content notices visible on every screen,
So that the public release meets its licensing obligations rather than relying on a page nobody visits.

**Acceptance Criteria:**

**Given** any surface in the app — deck view, any state panel, or an open agent view
**When** it renders
**Then** the footer attribution is visible without scrolling (UX-DR32, NFR-08)

**Given** the footer
**When** its text is read
**Then** it states: "Card data and imagery courtesy of Scryfall. Unofficial Fan Content permitted under the Wizards of the Coast Fan Content Policy. Not approved/endorsed by Wizards." (UX-DR32)

**Given** the footer text
**When** its colour is inspected
**Then** it uses `text-secondary` at 9.3:1 — a passing tier, not a muted one, because this text is legally load-bearing (UX-DR32)

**Given** the footer links
**When** they render at rest
**Then** they are persistently underlined and identifiable without hovering
**And** each has a hit area at least 24px tall, opens in a new tab, and brightens to `text-primary` on hover (UX-DR32, UX-DR47)

**Given** the footer
**When** its semantics are inspected
**Then** it is a `<footer>` element exposing the `contentinfo` landmark (UX-DR44)

**Given** a test suite covering every top-level surface
**When** it runs
**Then** each asserts the footer is present — this is a release condition, not a design choice

---

## Epic 3: Deck Data & Card Imagery on Tap

The backend can answer everything the glass will ever ask about a deck and its art: decks, a full
decklist, canonical card data, format legality, and card faces fetched once from Scryfall and
cached on disk forever. This is the epic that touches an external service, so it owns all the
pacing, caching, failure and attribution behaviour in one place. It closes **SC-4**.

### Story 3.1: Deck list and deck detail endpoints

As the browser UI,
I want to read the deck list and any full decklist over REST,
So that I can render a deck without knowing anything about the database schema.

**Acceptance Criteria:**

**Given** decks exist
**When** a client calls `GET /api/decks`
**Then** it receives the existing Pydantic deck schemas **unwrapped** — no status envelope (FR-02, AD-16)

**Given** a deck id that exists
**When** a client calls `GET /api/deck/{id}`
**Then** it receives the full decklist with card ids, quantities, and metadata (name, format, description), matching `load_deck` output (FR-02)
**And** the handler consumes the **existing repositories** and defines no second deck shape (AD-1)

**Given** a deck id that does not exist
**When** a client calls `GET /api/deck/{id}`
**Then** the response is `404` with `reason: "deck_not_found"` (AD-16)

**Given** the handler
**When** it obtains a session
**Then** it uses the shared lazy engine from Story 1.6
**And** the import-boundary test from Story 1.1 continues to pass, proving no write path was opened (AD-2, NFR-02)

**Given** the database is missing or transiently unreadable
**When** either endpoint is called
**Then** it returns `503` with `database_not_initialized` or `database_unavailable` respectively (AD-16)

**Given** the endpoints exist
**When** the type-generation pipeline from Story 2.3 runs
**Then** their schemas appear in the committed `types.d.ts` and CI's drift check covers them

### Story 3.2: Card detail endpoint

As the browser UI,
I want canonical card data for any printing id,
So that I can hydrate names, costs, type lines, oracle text and prices for cards a payload referenced only by id.

**Acceptance Criteria:**

**Given** a Scryfall printing uuid present in the local database
**When** a client calls `GET /api/cards/{card_id}`
**Then** it receives the existing card schema unwrapped, including `image_uris` and any `card_faces` (FR-03)
**And** the identifier is the Scryfall printing uuid everywhere — the value in `cards.id` and `deck_cards.card_id` (FR-13)

**Given** a well-formed uuid that is not in the local database
**When** the endpoint is called
**Then** the response is `404` with `reason: "card_not_found"`
**And** the closed reason-token set from Story 1.4 is **extended** with `card_not_found`, following AD-16's own rule that a new UI state — here, the unknown-card placeholder of FR-13 — requires a token first

**Given** a malformed card id
**When** the endpoint is called
**Then** the response is `400` with `reason: "invalid_request"` (AD-16)

**Given** prices are absent from local data for a card
**When** the response is returned
**Then** the price fields are absent or null rather than zero, so the UI can omit them rather than display a false price

### Story 3.3: Format check endpoint over the existing validators

As Brad glancing at the right column,
I want the app to tell me whether my deck is legal and where it isn't,
So that I see the same verdict the agent would give me, without asking for it.

**Acceptance Criteria:**

**Given** a deck id that exists
**When** a client calls `GET /api/deck/{id}/format-check`
**Then** it receives one row per check covering legality, deck size, copy limit, sideboard, banned cards and rotation exposure (UX-DR21)
**And** each row carries a status of pass, advisory or violation, plus a human-readable detail string

**Given** the checks are computed
**When** the implementation is inspected
**Then** it calls the **existing `src/logic` validators** — the same rules the `validate_deck` MCP tool applies (AD-1)
**And** no deck-construction rule is reimplemented in this endpoint or in TypeScript, because a second truth would drift from `src/logic`

**Given** a deck id that does not exist
**When** the endpoint is called
**Then** the response is `404` with `reason: "deck_not_found"`

**Given** a deck with no format set
**When** the endpoint is called
**Then** it returns a defined response the UI can render as "no format to check against", rather than an error

**Given** the endpoint reads the database
**When** the boundary test runs
**Then** no write path is introduced (AD-2)

### Story 3.4: The active deck — readable by the glass, settable by the agent

As the browser UI on cold open,
I want to ask which deck is active,
So that a fresh tab, or one that reconnected, shows the right deck instead of assuming there isn't one.

**Acceptance Criteria:**

**Given** the backend holds no active deck
**When** a client calls `GET /api/active-deck`
**Then** it receives a defined "none" response that the UI maps to the no-active-deck state (FR-07, UX-DR30)
**And** the endpoint is same-origin and requires no token, because it is a read the glass performs

**Given** the backend holds an active deck
**When** `GET /api/active-deck` is called
**Then** it returns that deck id

**Given** a caller presents the agent token from the discovery file
**When** it calls `PUT /api/active-deck` with a deck id
**Then** the backend stores the id in memory and returns success (FR-07, AD-16)
**And** the backend performs **no** deck-existence check — validation belongs to the MCP tool in Epic 6, which has database access and must report `deck_not_found` to the agent (AD-16)

**Given** a caller presents no token or a wrong token
**When** it calls `PUT /api/active-deck`
**Then** the request is rejected and the active deck is unchanged (NFR-01)

**Given** the backend restarts
**When** `GET /api/active-deck` is called
**Then** it reports none, because active deck is ephemeral backend memory and is gone with the process (FR-07, CM-3)

**Given** the active-deck slot is implemented
**When** the MCP server package is inspected
**Then** it holds no active-deck state of any kind — the MCP server stays stateless (CM-3)

### Story 3.5: Card image endpoint with face resolution and a defined parameter contract

As the browser UI rendering a grid of card faces,
I want one endpoint that serves any card's face at any size,
So that every image in the app comes from the app's own origin and never from a hotlink.

**Acceptance Criteria:**

**Given** a card with top-level `image_uris`
**When** a client calls `GET /api/card-image/{scryfall_id}?size=normal`
**Then** the image is served, with the CDN url resolved from the **locally stored** `image_uris` (FR-04, AD-11)
**And** no live Scryfall metadata API call is ever made

**Given** a card whose `card_faces` entries each carry their own `image_uris`
**When** a client requests `face=0` or `face=1`
**Then** the corresponding face is served (FR-04)

**Given** a card with `card_faces` but **no** per-face `image_uris` — split, adventure and flip layouts
**When** face resolution runs
**Then** it falls out as single-image automatically (AD-11)
**And** the implementation keys on the **presence of per-face `image_uris`**, never on a layout string — `cards` has no `layout` column, and the presence test is the more precise signal

**Given** a single-faced card
**When** `face=0` is requested
**Then** the image is served (AD-11)

**Given** an unrecognised `size` value
**When** the endpoint is called
**Then** the response is `400` (AD-11)

**Given** a `face` index the card does not have
**When** the endpoint is called
**Then** the response is `404` (AD-11)

**Given** the SPA renders any card image anywhere
**When** its request url is inspected
**Then** it points at this endpoint — the SPA never contacts Scryfall directly (AD-11, UX-DR36)

### Story 3.6: Paced, concurrency-capped CDN fetching at one global choke point

As a good citizen of Scryfall's infrastructure,
I want every outbound image fetch to pass through a single pacer,
So that a 100-card deck load is a polite trickle rather than a request storm.

**Acceptance Criteria:**

**Given** many image requests arrive at once
**When** they miss the cache
**Then** outbound fetches pass through **one backend-global semaphore plus request spacing** (AD-11, NFR-08)
**And** there is exactly one pacer in the process — not one per route, per card, or per client

**Given** the pacer is running
**When** a burst of fetches is queued
**Then** the pacing is `async` throughout and never blocks the event loop (AD-11)
**And** a concurrent push through `POST /agent/events` still meets its latency budget while images are queued (NFR-05)

**Given** an image has been fetched once
**When** the same id, size and face is requested again within the cache lifetime
**Then** no CDN request is made (CM-2)

**Given** fetching is lazy
**When** a deck is loaded
**Then** only the images a tab actually asks for are fetched — the backend never pre-fetches a whole deck (AD-11)

**Given** a cold cache and a 100-card deck
**When** the deck is fully painted
**Then** roughly 12 MB is fetched over roughly 10 seconds
**And** this is recorded in the test or acceptance notes as an **expected observation, not a defect** — NFR-05 excludes first-fetch image paint

### Story 3.7: Sharded, atomically written disk cache

As Brad running this app for months,
I want cached card art stored somewhere predictable and never half-written,
So that the cache survives crashes and I can find and delete it when I want to.

**Acceptance Criteria:**

**Given** an image is fetched
**When** it is cached
**Then** it is written to `data_dir()/image_cache/<id[0:2]>/<id>/<size>_<face>.<ext>` (AD-11, NFR-09)
**And** the two-hex-character shard exists because a flat directory would reach roughly 60,000 entries

**Given** a cache write
**When** it occurs
**Then** it is written to a temporary file and renamed into place (AD-11, NFR-09)
**And** a crash mid-write can never leave a truncated file that a later read would serve

**Given** the cache directory does not exist
**When** the backend starts
**Then** the lifespan creates it — never `build_app()` (AD-10)

**Given** the cache is keyed
**When** a data refresh changes a card's `image_uris`
**Then** the stale entry is served, because the key is id plus size plus face
**And** this staleness is accepted and documented rather than solved (AD-11)

**Given** the cache grows
**When** its size is inspected
**Then** **no eviction runs** — the cache is unbounded in MVP with a documented location and a clear removal command, revisited when a real footprint exists to size a policy against (AD-11)

**Given** the app runs with no network after the cache is warm
**When** a cached image is requested
**Then** it is served from disk (NFR-06)

### Story 3.8: Distinguishable failure signalling and negative caching

As the browser UI,
I want to know the difference between "this card has no art" and "the fetch failed",
So that I can draw the named placeholder the design specifies instead of showing a grey rectangle.

**Acceptance Criteria:**

**Given** a CDN fetch fails
**When** the endpoint responds
**Then** it signals the failure **distinguishably** from a card that has no image data at all (AD-11)
**And** in neither case does the backend serve a substitute image — serving a generic grey card would make the client's named placeholder unreachable and degrade the app to silent rectangles

**Given** a fetch has failed
**When** the same image is requested again
**Then** the failure is negative-cached with backoff, so an unreachable CDN never causes a request storm (FR-04, AD-11)

**Given** a card has no `image_uris` at all
**When** its image is requested
**Then** a stable no-image response is returned and **no fetch is ever attempted** (AD-11)

**Given** the CDN becomes reachable again after a backoff window
**When** the image is requested
**Then** the fetch is retried and, on success, cached normally

**Given** any of these outcomes
**When** the client receives them
**Then** it has enough information to render the named placeholder — card name, mana pips, type line — which only the client has the data to draw (AD-11, UX-DR22)

### Story 3.9: Fresh install guides instead of erroring, and comes alive on its own

As Brad on a brand-new machine,
I want the app to tell me the card database isn't built yet and then start working by itself once it is,
So that going from a fresh install to card art on screen never involves a config file or an error page.

**Acceptance Criteria:**

**Given** a fresh install with no card database
**When** Brad runs `uv run artificial-planeswalker companion` and opens the printed URL
**Then** the app renders the "Card database not set up yet" state panel with its verbatim copy (FR-22, UX-DR30, UX-DR33)
**And** no error page, stack trace or red styling appears anywhere

**Given** the app is showing that state
**When** its network activity is inspected
**Then** it is retrying a data endpoint on a backoff, not spinning

**Given** the agent initialises the database in the terminal while the page is open
**When** the build completes
**Then** the app transitions on its own to the no-active-deck state, listing available decks — **no manual refresh** (FR-22, UX-DR33)

**Given** a transient read failure during a bulk data refresh
**When** the UI receives `503 database_unavailable`
**Then** it shows the "Card database is updating" panel, distinct from the not-initialized panel (AD-16, UX-DR33)
**And** it retries silently on backoff until reads succeed

**Given** the whole path from a `pip`-fresh machine
**When** Flow 2 of `EXPERIENCE.md` is walked end to end
**Then** it completes with a single `uv` command, no configuration, and no error page — closing **SC-4**

---

## Epic 4: The Deck on the Glass

Brad sees his deck as full card faces with quantity badges, reads any card in the persistent
detail panel by moving his cursor, flips a double-faced card, and takes in the curve, colour
spread, type-grouped list and format check without a single click. This is the first epic where
**SC-5** becomes answerable and the largest UX surface in the feature.

### Story 4.1: A single card-hydration cache with in-flight deduping

As a developer building every card-rendering surface,
I want one owner for card lookups in the store,
So that sweeping a cursor across a hundred tiles doesn't fire a hundred duplicate requests for cards already in memory.

**Acceptance Criteria:**

**Given** the zustand store
**When** its slices are inspected
**Then** exactly one card cache exists, keyed by Scryfall printing uuid (AD-12)
**And** no component fetches card data directly

**Given** two components request the same uncached card id simultaneously
**When** the cache handles them
**Then** one request goes to `GET /api/cards/{card_id}` and both callers receive its result (AD-12)

**Given** a card is already cached
**When** it is requested again
**Then** no request is made

**Given** the detail panel updates on hover across a 100-tile grid
**When** the cursor sweeps the whole grid twice
**Then** each distinct card is fetched at most once (AD-12)

**Given** `GET /api/cards/{card_id}` returns `404 card_not_found`
**When** the cache stores the outcome
**Then** the id is marked unknown and not re-requested on every render
**And** consumers can distinguish "unknown card" from "still loading" (FR-13)

**Given** the store
**When** its dependencies are inspected
**Then** no second data-fetching or state-management library is present (AD-12)

### Story 4.2: Deck state bootstrap and the type-grouped decklist

As Brad opening a tab,
I want the app to work out which deck is active and load it,
So that a fresh tab shows my deck rather than assuming there isn't one.

**Acceptance Criteria:**

**Given** a cold open
**When** the app boots
**Then** it calls `GET /api/active-deck`, and on a deck id calls `GET /api/deck/{id}` (FR-07)

**Given** the backend reports no active deck
**When** the app renders
**Then** it shows the no-active-deck state panel with the available deck names from `GET /api/decks`, non-clickable (UX-DR30, UX-DR33)

**Given** a loaded decklist
**When** the store derives its groupings
**Then** cards are grouped by card type, and **double-faced cards group by their front face** (FR-05)
**And** the derivation happens once in the store, so the grid and the list panel cannot disagree

**Given** `GET /api/deck/{id}` returns `404 deck_not_found`
**When** the app handles it
**Then** it clears to the no-active-deck state (FR-11, AD-16)

**Given** the backend returns `503 database_not_initialized` or `503 database_unavailable`
**When** the app handles it
**Then** it shows the matching state panel from Story 2.9 rather than a deck view (AD-16)

**Given** the store holds deck state
**When** its inputs are inspected
**Then** they are exactly REST responses and — from Epic 5 — WebSocket messages, and nothing else writes the store (AD-12)

### Story 4.3: Card placeholders — named, unknown, and loading wells

As Brad looking at a card whose art hasn't arrived or doesn't exist,
I want a deliberately designed card-shaped stand-in,
So that a gap in the data never reads as a broken app.

**Acceptance Criteria:**

**Given** a card with no image data
**When** its placeholder renders
**Then** it is card-shaped at the card radius and 63:88 aspect, showing the card name centred in body-strong, mana pips above, and the type line in micro (FR-19, UX-DR22)
**And** it is never a broken-image glyph

**Given** a card id the local database does not recognise
**When** the unknown variant renders
**Then** the name slot reads "Unknown card" with the truncated id in `text-secondary` — a passing tier, because the id is the only identifying information available (UX-DR22, UX-DR33)

**Given** an image is still loading
**When** the loading well renders
**Then** it uses the same card shape on `surface-well` with no text and no spinner (UX-DR22, UX-DR33)

**Given** any placeholder
**When** it is inspected against a real card face
**Then** it occupies exactly the same footprint, so layout never reflows when art arrives (UX-DR36)

**Given** a named placeholder
**When** a user interacts with it
**Then** it behaves as a normal tile under the inspection contract
**And** the **unknown-card** variant cannot be inspected, because there is nothing to show (UX-DR22)

### Story 4.4: Card tile and the card-art grid

As Brad looking at my deck,
I want to see it as full card faces I can take in at a glance,
So that reading my decklist feels like looking at cards rather than at a spreadsheet.

**Acceptance Criteria:**

**Given** an active deck with cards
**When** the grid renders
**Then** each tile is the card face itself at the `normal` image size — no frame, no title bar, no art crop (FR-19, UX-DR14)
**And** the caption sits below in label type, single-line with ellipsis

**Given** any card face, thumbnail or placeholder anywhere in the app
**When** its geometry is inspected
**Then** it uses the card radius `4.75% / 3.4%` at a 63:88 aspect (UX-DR4)
**And** nothing else in the UI borrows the card radius, and no card borrows a chrome radius

**Given** the grid container
**When** it lays out
**Then** it is `repeat(auto-fill, minmax(176px, 1fr))` with the 24px grid gap, and tiles reflow at any supported width (UX-DR4, UX-DR8)

**Given** a card has a quantity above one
**When** the tile renders
**Then** a quantity badge reading "×N" is pinned top-right inside 8px, on scrim with blur and a strong border (UX-DR16)

**Given** the deck loads
**When** images arrive
**Then** layout renders immediately with cached art where available and silent wells elsewhere, and images fade in over the pulse duration (UX-DR36)
**And** layout never reflows on image arrival

**Given** a tile is hovered or receives keyboard focus
**When** the effect applies
**Then** it scales 1.06 in place over the glide transition, raising z-index so neighbours slide under (UX-DR14)
**And** the pop is presentation only — it never changes hit targets

**Given** `prefers-reduced-motion: reduce`
**When** a tile is hovered
**Then** no scale is applied and only the shadow changes; image fade-in is instant (UX-DR42)

**Given** a tile receives keyboard focus
**When** the focus indicator renders
**Then** it uses the focus-ring-over-art treatment — the ring plus a dark outer edge — so it is legible over light or dark card art alike (UX-DR14, UX-DR41)

**Given** the card art
**When** it renders
**Then** it is untinted, un-overlaid, un-gradient-faded and unwatermarked (UX-DR7)

**Given** every card image
**When** its alt text is inspected
**Then** it is the card name, face-specific for double-faced cards (UX-DR48)

### Story 4.5: Persistent card detail panel with transient and pinned inspection

As Brad reading through my deck,
I want the full card I'm pointing at to appear in a panel that's always there,
So that reading the whole deck is one continuous motion with no clicks.

**Acceptance Criteria:**

**Given** the right column
**When** the app renders with a deck loaded
**Then** the card detail panel is always present, at `overlay` level, and is **never empty** — on cold open it targets the first card of the first type group (FR-17, UX-DR20)

**Given** the cursor hovers, or keyboard focus lands on, any card tile, thumbnail or deck row
**When** the inspection target changes
**Then** the panel updates in place, showing the full card face at `large`, the name, mana cost, type line, price if present, and oracle text (FR-17, UX-DR20)
**And** name and cost render immediately from data known at hover time while the rest fills in place — **no spinner** (UX-DR36)

**Given** a card is clicked, or Enter is pressed on a focused card
**When** the pin applies
**Then** the target is fixed, the panel carries the pinned ring, and hover no longer overrides it (UX-DR20)

**Given** a pinned target
**When** the same card is clicked again, Esc is pressed, or the unpin control is used
**Then** the pin releases and hover resumes control (UX-DR20, UX-DR39)

**Given** prices are absent from local data
**When** the panel renders
**Then** no price is shown, rather than a zero or a placeholder value (UX-DR20)

**Given** the panel's semantics
**When** they are inspected
**Then** it is `role="region"` labelled "Card detail", it is **not** a modal, and it is **not** a live region (UX-DR20, UX-DR44)
**And** transient hover or focus changes announce nothing, because sweeping a cursor across a 60-card grid would otherwise flood the announcement queue

**Given** a pin occurs
**When** the announcement fires
**Then** a **separate** polite region announces once: "Pinned — {card name}" (UX-DR45)

**Given** `prefers-reduced-motion: reduce`
**When** the inspection target changes
**Then** the content swap is instant with no crossfade — it changes on every hover, so it must never animate (UX-DR42)

### Story 4.6: Double-faced card flip control

As Brad running double-faced cards,
I want a control that flips a card to its back without opening anything,
So that inspecting a card and flipping it are two obviously different actions.

**Acceptance Criteria:**

**Given** a card whose `card_faces` carry per-face `image_uris`
**When** its tile renders
**Then** a 28px circular flip control appears with a 32px hit area, pinned to the tile's **top-left** inside 8px (FR-19, UX-DR15)
**And** it never collides with the quantity badge, which occupies the top-right

**Given** a split, adventure or flip layout — `card_faces` without per-face `image_uris`
**When** its tile renders
**Then** **no** flip control is rendered (FR-04, UX-DR15)

**Given** the control
**When** its appearance is inspected
**Then** it shares the quantity badge's scrim-plus-blur material, carries a stroke-based two-arrow rotate glyph, and sits at 0.65 opacity at rest rising to 1.0 when its tile is hovered or focused (UX-DR15)
**And** the glyph could never read as a mana symbol, set symbol or planeswalker symbol (UX-DR7)

**Given** the control is clicked
**When** the event is handled
**Then** it flips the face via the image endpoint's `face` parameter and **stops propagation** — it never sets, pins or clears the inspection (UX-DR15)

**Given** the control has keyboard focus
**When** Enter or Space is pressed
**Then** the card flips
**And** the control sits in the Tab order **immediately after its own tile**, never as a trailing group divorced from the cards (UX-DR15, UX-DR40)

**Given** a card has been flipped
**When** the same printing appears elsewhere — grid, agent-view thumbnail, or the detail panel
**Then** it shows the same face, because flip state is keyed by Scryfall printing uuid rather than by location (UX-DR15)

**Given** a flipped tile
**When** it is hovered or pinned
**Then** the detail panel shows **that face** — its art, its name and its oracle text (UX-DR15, UX-DR20)
**And** the detail panel carries its own copy of the flip control at the same spec, pinned to its art's top-left

**Given** a `deck_changed` re-render occurs — from Epic 7 onward
**When** the grid re-renders
**Then** flip state **persists**, because a snap-back to the front face reads as a bug (UX-DR15)
**And** the state is per-tab, in memory, and resets on a page refresh

**Given** `prefers-reduced-motion: reduce`
**When** a card is flipped
**Then** the face swaps instantly with no 3D rotation (UX-DR42)

### Story 4.7: Deck list panel

As Brad checking quantities and prices,
I want the deck as a text list grouped by type beside the grid,
So that I can read it as a list without giving up the card art.

**Acceptance Criteria:**

**Given** an active deck
**When** the right column renders
**Then** the deck list panel is permanently present alongside the grid — not a toggled alternate view (FR-05, UX-DR19)

**Given** a deck row
**When** it renders
**Then** it shows quantity in numeric tertiary, name in body, mana cost as pips, and price right-aligned in numeric (UX-DR19)
**And** the row uses body-strong primary for the name when it is the live inspection target, with the live tint and inset rule

**Given** the list
**When** it is grouped
**Then** type-group headers show the group name in label type with a right-aligned count over a hairline rule (UX-DR12)

**Given** a deck row is hovered or focused
**When** the inspection contract applies
**Then** it sets the detail panel target; a click pins it — identical to a card tile (UX-DR19)
**And** rows are focusable and sit in the Tab order

**Given** a double-faced card
**When** its row renders
**Then** it shows the **front** face's name and cost (UX-DR19)

**Given** a card with no image data or an unrecognised id
**When** its row renders
**Then** it renders identically to any other row, because the list is text-first (UX-DR19)

**Given** the list
**When** its semantics are inspected
**Then** it is a `ul`/`li` structure and its panel title is an `h2` (UX-DR44)

### Story 4.8: Mana curve panel

As Brad judging whether my deck can function,
I want the curve rendered from the deck I'm looking at,
So that I can see the shape of my draws without asking the agent.

**Acceptance Criteria:**

**Given** a loaded decklist
**When** the curve renders
**Then** buckets are **1 through 7+**, lands are **excluded**, and double-faced cards bucket by their **front face** (FR-05, UX-DR17)

**Given** the deck changes
**When** the panel re-renders
**Then** the curve is recomputed from the decklist rather than cached (UX-DR17)

**Given** the bars
**When** their fill is inspected
**Then** unstacked bars use the **chrome** curve-bar fill token, never a `mana-*` token (UX-DR7, UX-DR17)
**And** counts render above the bars in numeric tertiary with axis labels in micro

**Given** the bars are stacked by colour
**When** segments render
**Then** they run in fixed order W·U·B·R·G·gold·colourless separated by hairlines, multicolour cards contribute one gold segment, and the painted segments are `aria-hidden` decoration (UX-DR17)

**Given** a screen reader user
**When** they reach the curve
**Then** each bar exposes an accessible name carrying its count — for example "3 drops: 8 cards" — and the curve as a whole is backed by a **visually-hidden table** (UX-DR17, UX-DR44)
**And** the panel is a `figure` whose accessible alternative is that table

**Given** the bars
**When** a user clicks one
**Then** nothing happens — the curve is display-only (UX-DR17)

**Given** `prefers-reduced-motion: reduce`
**When** bar heights change
**Then** they jump instantly rather than animating (UX-DR42)

### Story 4.9: Colour distribution panel

As Brad checking whether my mana base matches my spells,
I want the deck's colour balance shown as one proportional bar with a readable legend,
So that I can see at a glance which colour is carrying the deck.

**Acceptance Criteria:**

**Given** a loaded decklist
**When** the panel renders
**Then** a single 14px pill-radius bar on the well track is segmented by `mana-*` tokens proportional to pip count across the deck (UX-DR18)

**Given** the bar
**When** the legend renders beneath it
**Then** each entry shows a `ManaPip`, a count and a percentage (UX-DR18)

**Given** a screen reader user
**When** they reach the panel
**Then** the **bar is `aria-hidden`** and the legend is the accessible data path, so colour is never the sole carrier of the information (UX-DR18, UX-DR44)
**And** the panel is a `figure` whose accessible alternative is that legend

**Given** the `mana-*` tokens
**When** their use here is inspected
**Then** this is data ink used correctly — the same tokens remain banned from buttons, borders, backgrounds and unstacked curve bars (UX-DR7)

**Given** a colourless or single-colour deck
**When** the panel renders
**Then** it renders correctly rather than dividing by zero or showing an empty bar

### Story 4.10: Format check panel

As Brad about to register a deck,
I want the legality verdict visible in the right column,
So that I find out about a banned card or a copy-limit violation while I'm looking at the deck.

**Acceptance Criteria:**

**Given** an active deck
**When** the panel renders
**Then** it shows one row per check from `GET /api/deck/{id}/format-check` (UX-DR21)

**Given** a check row
**When** it renders
**Then** the label is in body `text-secondary` with a right-aligned `Badge`, over a hairline rule (UX-DR21)
**And** tone maps pass → positive, advisory → caution, violation → negative

**Given** the rows
**When** a user interacts with them
**Then** nothing happens — they are display-only (UX-DR21)

**Given** the deck has no format set
**When** the panel renders
**Then** it renders the endpoint's defined "no format to check against" response calmly, not as an error (UX-DR30)

**Given** a violation
**When** it renders
**Then** it uses the negative semantic token in a badge — never a red panel fill, an alert icon or an exclamation mark (UX-DR30)

### Story 4.11: Keyboard floor — skip link, Tab order and focus management

As a keyboard user,
I want to reach everything in the app without tabbing through a hundred cards to get there,
So that the right column and the footer's licensing links are reachable in practice, not just in theory.

**Acceptance Criteria:**

**Given** any surface rendering a populated grid
**When** the first Tab is pressed
**Then** the skip link "Skip past the deck grid" appears, visually hidden until focused, as a chip at the window's top-left carrying the standard focus ring (UX-DR31)

**Given** the skip link has focus
**When** Enter is pressed
**Then** focus moves to the card detail panel heading — past the grid, into the right column (UX-DR31)

**Given** a state panel occupies the left column instead of the grid
**When** the Tab order is walked
**Then** the skip link is **withdrawn**, because there is nothing to skip (UX-DR31, UX-DR37)

**Given** a full surface
**When** Tab is pressed repeatedly
**Then** the order is skip link → header nav pills → card tiles in visual order, **each double-faced card's flip control immediately after its own tile** → deck rows → connection pill → footer links (UX-DR40)

**Given** any focusable element
**When** it receives keyboard focus
**Then** the 2px `accent-bright` focus ring at 2px offset is visible, keyboard-triggered only (UX-DR46)
**And** no element sets `outline: none` without that replacement

**Given** any interactive element in the app
**When** its markup is inspected
**Then** it is a real `<button>` or `<a>` with a hit box of at least 24×24px — never a `<div>` with a click handler (UX-DR47)

**Given** hover reveals any information
**When** the same element is reached by keyboard
**Then** focus reveals it identically — hover is never the only path (UX-DR39)

**Given** focus moves anywhere in the app
**When** it lands
**Then** it is never dropped to `document.body` (UX-DR46)

**Given** arrow-key grid navigation is deferred out of MVP
**When** the deferral is recorded
**Then** the cost is stated plainly in the story notes — **measured at c4-11 over all 40 real decks: 206 sequential Tab stops max / 78 median / 102.0 mean** from the header to the first footer link (the stale "100+" this clause used to carry predated c4-7's second focusable row per card), with the skip link as sole mitigation removing only the first 105 — and it carries a revisit-before-public-release flag, since the footer's Fan Content Policy links sit behind the grid (UX-DR40)

### Story 4.12: Empty deck state and the cold-open render budget

As Brad opening a deck that has nothing in it yet,
I want the app to say so calmly and still render everything that makes sense,
So that an empty deck looks intentional rather than broken — and a full deck appears fast.

**Acceptance Criteria:**

**Given** an active deck with zero cards
**When** the deck view renders
**Then** the deck header and name render normally, and the grid area shows the in-grid line "This deck is empty — ask your agent to add cards." in body `text-secondary` (UX-DR33)
**And** there is no state panel and no error styling

**Given** an active deck with zero cards
**When** the analysis panels are considered
**Then** the mana curve, colour distribution and format check panels are **hidden** until the deck has cards (UX-DR33)

**Given** a 100-card Commander deck and a warm image cache
**When** the app cold-opens
**Then** full layout — header, grid, curve, colour distribution, deck list and format check — is reached within **1 second** (NFR-05, SC-2)
**And** the measurement is recorded as an acceptance observation, not assumed

**Given** a cold image cache
**When** the deck loads
**Then** layout still reaches the 1 second budget, because art fills placeholder-then-fill and first-fetch image paint is excluded from the budget (NFR-05, UX-DR36)

**Given** any point after first paint
**When** the app is observed
**Then** a blank screen is never shown (UX-DR36)

**Given** the deck view is complete
**When** it is compared against `DESIGN.md` and `EXPERIENCE.md`
**Then** every panel, token and behaviour matches the contract, making **SC-5** answerable for the deck view — the formal gate is Epic 8

---

## Epic 5: The Agent's Channel

The pipe from agent to glass exists and is safe: two credentials that never touch, an
authenticated WebSocket the browser holds open and re-establishes on its own, one envelope shape
both halves of the codebase agree on, and a CI check that stops them ever disagreeing. Brad can
watch the connection state and see the app recover from a backend restart without touching it.

### Story 5.1: The event envelope and every per-kind payload contract

As a developer on either side of the wire,
I want one envelope and all four payload shapes defined once, up front,
So that no later epic has to change a contract that ripples through a committed `.d.ts` and two mirrored bundles.

**Acceptance Criteria:**

**Given** `src/companion/contracts.py`
**When** its models are inspected
**Then** every message is `{kind, id, ts, payload}` as a single Pydantic discriminated union (AD-6, NFR-03)
**And** the module imports only `pydantic` and stdlib, keeping the leaf dependency-free (AD-3)

**Given** the `kind` field
**When** its type is inspected
**Then** it is a **closed** enum covering agent pushes `suggestions | swaps | tier_list | groups` and system signals `deck_changed | active_deck_changed` (AD-6)
**And** `active_deck_changed` is distinct from `deck_changed`, because conflating them would make the UI refetch the deck it is leaving rather than the one it is switching to

**Given** the `id` field
**When** its use is documented
**Then** it is unique per push and **opaque** — it carries identity and dedupe, never ordering (AD-6)
**And** `ts` is `datetime.now(UTC)`, and session history orders by `ts`

**Given** all four payload kinds
**When** their item shapes are inspected
**Then** each defines its own shape over a bare card reference, not one fat optional bag (AD-7):
`suggestions` → `{card_id, reason, category?}`;
`swaps` → `{out_card_id, in_card_id, rationale, out_qty, in_qty}`;
`tier_list` → `{letter: Literal["S","A","B","C","D"], name, note?, card_ids[]}`;
`groups` → `{title, rationale, card_ids[]}`
**And** every payload carries an optional agent-authored `title`

**Given** the tier `letter`
**When** its type is inspected
**Then** it is the closed five-value enum, so the design's five-colour ramp is total (AD-7)
**And** the free-text `name` carries the MTG meaning — "Auto-include", "Filler", "Cut"

**Given** the caps
**When** the model constraints are inspected
**Then** they enforce ≤ 60 items or card ids per list, ≤ 12 groups or tiers, `reason` ≤ 200 characters, `rationale` ≤ 600, `title` ≤ 80, envelope ≤ 64 KB (AD-7)

**Given** cards are referenced
**When** any payload is inspected
**Then** it carries **Scryfall printing uuids only** and no names — name-to-id resolution stays with the existing MCP tools (FR-13, AD-7)

**Given** all four kinds are defined now rather than incrementally
**When** Epic 9 adds the remaining tools and views
**Then** it changes no contract, which is why Phase 2 is cheap (AD-6)

**Given** the union is defined
**When** Story 2.3's generator runs
**Then** the TypeScript union is produced from the same source and drift-checked (AD-12)

### Story 5.2: Same-origin session endpoint minting single-use WebSocket tickets

As the browser UI,
I want a short-lived ticket before I open a socket,
So that the WebSocket upgrade is authenticated by something CORS alone cannot protect.

**Acceptance Criteria:**

**Given** a same-origin request
**When** it calls `GET /api/session`
**Then** it receives a freshly minted WebSocket ticket (NFR-01, AD-5)

**Given** a minted ticket
**When** its properties are inspected
**Then** it is **single-use** with a **30 second TTL** (AD-5)

**Given** a ticket is consumed at a WebSocket upgrade
**When** the same ticket is presented again
**Then** it is rejected — it was destroyed on consumption (AD-5)

**Given** a ticket older than its TTL
**When** it is presented
**Then** it is rejected

**Given** the agent token from the discovery file
**When** the session endpoint's implementation is inspected
**Then** the two credentials share **no storage and no code path** (AD-5)
**And** the agent token never appears in this response, in any HTML, or in any WebSocket frame

**Given** tickets are held
**When** their storage is inspected
**Then** they live in backend memory only and are gone on restart (CM-3)

### Story 5.3: Authenticated WebSocket upgrade with Host and Origin validation

As Brad with other tabs open,
I want the companion's socket to refuse connections that didn't come from its own page,
So that a malicious local page cannot attach to my session and read what my agent is doing.

**Acceptance Criteria:**

**Given** an upgrade request carrying a valid, unexpired ticket
**When** it is processed
**Then** the socket is established and the ticket is consumed and destroyed (AD-5)

**Given** an upgrade request with no ticket, an expired ticket or an already-consumed ticket
**When** it is processed
**Then** the upgrade is rejected (NFR-01)

**Given** an upgrade request
**When** its headers are validated
**Then** the `Host` header is checked against `127.0.0.1:{port}` / `localhost:{port}` **and** the `Origin` header is checked against the app's own origin (AD-5)
**And** both are required, because `Host` identifies what was addressed while `Origin` identifies the calling page, and the threat model is a malicious local page

**Given** the Host middleware from Story 1.5
**When** the upgrade path is implemented
**Then** it reuses that check rather than duplicating it (AD-5)

**Given** the socket
**When** its bind address is inspected
**Then** it is `127.0.0.1` only (NFR-01)

### Story 5.4: Broadcast to every connected client

As Brad with the app open,
I want anything the backend learns to reach my browser immediately,
So that the glass reflects what the agent just did without me refreshing.

**Acceptance Criteria:**

**Given** one or more connected clients
**When** an envelope is broadcast
**Then** every connected client receives it (FR-06)

**Given** multiple tabs are open
**When** an envelope is broadcast
**Then** **every tab** receives it — cross-tab view state and unread markers diverge by design and are not synchronised (UX-DR37)

**Given** a client disconnects
**When** the next broadcast occurs
**Then** it is removed from the connection set without error, and other clients are unaffected

**Given** the active deck is set through `PUT /api/active-deck`
**When** the store succeeds
**Then** an `active_deck_changed` envelope is broadcast carrying the new deck id (AD-6)

**Given** connections are tracked
**When** their storage is inspected
**Then** they live in backend memory only (CM-3)

**Given** a broadcast is attempted with no clients connected
**When** it runs
**Then** it succeeds silently — delivery is fire-and-forget (NFR-04)

### Story 5.5: Token-authenticated event ingest that reports who is listening

As a companion MCP tool,
I want one authenticated endpoint that validates my payload and tells me how many browsers saw it,
So that I can report to Brad whether his content was actually displayed.

**Acceptance Criteria:**

**Given** a request carrying the agent token from the discovery file
**When** it POSTs a valid envelope to `/agent/events`
**Then** the payload is relayed to all connected clients and the response reports the **connected-client count** (FR-06)

**Given** a request with a missing or wrong token
**When** it is processed
**Then** it is rejected and nothing is broadcast (NFR-01)

**Given** a payload exceeding any cap from Story 5.1
**When** it is validated
**Then** the response is **413** with `reason: "payload_too_large"` — **rejected, never truncated** (AD-7, AD-16; 413 per the c1-4 review ruling, was 422)
**And** a partial render that reads as the complete answer is thereby impossible

**Given** a payload referencing card ids
**When** the endpoint processes it
**Then** it **shape-validates and relays without reading the database** — card ids are not validated at ingest (AD-7)
**And** the push path performs no database round-trip, protecting the 250 ms budget (NFR-05)

**Given** an empty payload — zero suggestions, or all-empty tiers
**When** it is posted
**Then** it is **accepted** and relayed, so the UI can render its deliberate empty state (AD-7)

**Given** the endpoint declares the envelope union as its request body
**When** `app.openapi()` is produced
**Then** the WebSocket types land in the OpenAPI components with no dummy endpoint and no second generator (AD-12)

### Story 5.6: Client reconnection with backoff and a fresh ticket per attempt

As Brad who restarted the backend mid-session,
I want the page to reconnect on its own,
So that a restart is a blip rather than something I have to notice and fix.

**Acceptance Criteria:**

**Given** the socket drops
**When** the client reconnects
**Then** it retries with exponential backoff (NFR-04)

**Given** each reconnect attempt
**When** it begins
**Then** it mints a **fresh** ticket from `GET /api/session` — tickets are single-use, so a cached one would fail (AD-5)

**Given** a reconnect succeeds
**When** the client resumes
**Then** it refetches the active deck (NFR-04)
**And** if the backend restarted, the active deck is gone with it, so the app lands on the no-active-deck state (FR-07)

**Given** reconnection is in progress
**When** the deck view is observed
**Then** existing deck content **stays rendered**, possibly stale — the view is never torn down to a skeleton (UX-DR35)

**Given** retries are exhausted
**When** the client gives up
**Then** the Disconnected state panel takes the left column with its verbatim terminal-and-relaunch-URL guidance (UX-DR30, UX-DR33)

**Given** freshness recovery
**When** its mechanism is inspected
**Then** it is "something changed, refetch" — no diffs and no patches (NFR-04)

### Story 5.7: Connection pill

As Brad glancing at the corner of the window,
I want to know whether the app is actually connected and to what,
So that I can tell a quiet app from a dead one.

**Acceptance Criteria:**

**Given** the app is running
**When** any surface renders
**Then** the connection pill is visible at the bottom-left (FR-15, UX-DR29)

**Given** each connection state
**When** the pill renders
**Then** the dot is positive for live, caution for reconnecting, negative for backend-gone — **all static, never pulsing** (UX-DR29)
**And** the pill **text names the state**, so the dot never carries it alone

**Given** an active deck
**When** the pill renders
**Then** it also names the active deck (FR-15)

**Given** the pill
**When** it is reached by Tab
**Then** it is focusable and carries the standard focus ring (UX-DR47)

**Given** the pill state changes
**When** the change occurs
**Then** it announces via a polite live region (UX-DR45)

**Given** the pill at rest
**When** it is observed over time
**Then** it never animates (UX-DR29)

### Story 5.8: The one real-socket integration test

As a developer,
I want exactly one test that boots a real backend on a real port,
So that the seams which only fail in a real process are proven in a real process, and nothing else pays for sockets.

**Acceptance Criteria:**

**Given** the test suite
**When** integration-marked companion tests are counted
**Then** there is exactly **one** that boots a real backend process (AD-10)
**And** every other backend test runs in-process over `httpx.ASGITransport` or the existing in-process MCP client

**Given** the integration test
**When** it runs
**Then** it starts a real backend on an **ephemeral port**, writes a **real discovery file** under an isolated `PLANESWALKER_DATA_DIR`, and cleans up afterwards (AD-10, AD-4)

**Given** the running backend
**When** the test exercises the channel
**Then** it performs a real `GET /health` identity verification, a real ticket mint, a real WebSocket upgrade with ticket consume, and a real token-authenticated event POST that arrives over the socket (AD-10)

**Given** the backend is restarted mid-test with a new token
**When** a caller retries after an auth rejection
**Then** it re-reads the discovery file and succeeds on the second attempt (AD-10, FR-12)

**Given** the test runs on Windows
**When** it executes
**Then** it passes — the platform where the read-only WAL open recipe would have been discovered as a Story-1 bug had AD-2 not replaced it with the import boundary

**Given** the test is marked
**When** `-m "not integration"` is used
**Then** it is deselected and the rest of the suite still covers the channel logic

---

## Epic 6: The Agent Pushes to the Glass

Brad asks his agent a question and the answer appears on the glass: the agent sets the active
deck, pushes suggestions, and the view blooms open within 250 ms with art-forward rows he can read
without clicking. When the app is closed or the tab is gone, the agent says so in one calm line
and presents the content in chat as usual — nothing is ever lost. This closes **SC-1** and **SC-3**.

### Story 6.1: Leaf client with health verification, retry-once, and the closed outcome vocabulary

As a companion MCP tool,
I want one shared client that finds the backend, proves its identity, posts, and reports a single token,
So that every tool fails the same way and none of them can break an agent turn.

**Acceptance Criteria:**

**Given** `src/companion/client.py`
**When** its imports are inspected
**Then** it uses only `pydantic`, `httpx`, `src.paths` and `src.companion.contracts`/`discovery` — never FastAPI or uvicorn (AD-3)

**Given** a push is requested
**When** the client runs
**Then** it reads the discovery file, calls `GET /health`, and **matches the echoed `instance_id`** before sending the token (AD-4)
**And** a mismatch or a failed probe is reported as *app not running*, with no token sent

**Given** any outcome
**When** the client reports it
**Then** it returns exactly one token from the closed set `displayed | app_not_running | no_clients_connected | payload_rejected | backend_error`, plus the connected-client count (AD-8)
**And** the tokens carry no counts inside them and no free phrases, matching the project's existing status-token convention

**Given** the backend rejects the token — it restarted mid-session with a new one
**When** the client handles the rejection
**Then** it **re-reads the discovery file and retries exactly once**, so the restart is picked up transparently (FR-12, AD-8)
**And** a second failure returns `backend_error` rather than retrying again

**Given** the backend returns `413 payload_too_large` (413 per the c1-4 review ruling, was 422)
**When** the client maps it
**Then** the outcome is `payload_rejected` (AD-7, AD-8)

**Given** the backend is reachable but no browser tab is connected
**When** the client reports
**Then** the outcome is `no_clients_connected`, distinguishable from `app_not_running` (FR-12)

**Given** any failure whatsoever — unreachable backend, corrupt discovery file, timeout, malformed response
**When** it occurs
**Then** the client **never raises** (FR-12, AD-8)

**Given** a corrupt or partially written discovery file
**When** the client parses it
**Then** the parse failure is treated as *app not running*, never an error (AD-4)

### Story 6.2: `companion_set_active_deck` — the agent chooses what the glass shows

As Brad,
I want to tell my agent which deck to put on the glass,
So that the browser follows the conversation instead of me managing it.

**Acceptance Criteria:**

**Given** the tool is defined
**When** its signature is inspected
**Then** it is `async def`, matching the existing Epic-1 tools — a blocking POST in a sync tool would hold a FastMCP threadpool worker for a whole round trip (AD-8)

**Given** a deck id that exists
**When** the agent calls `companion_set_active_deck(deck_id)`
**Then** the tool calls `PUT /api/active-deck` with the agent token and returns a compact text result carrying `displayed` and the client count (FR-07)

**Given** a deck id that does not exist
**When** the tool runs
**Then** it validates existence **itself**, against the database, and returns `deck_not_found` without contacting the backend (AD-16)
**And** this token is a documented addition to AD-8's set for the control tool, since AD-16 requires the tool — not the backend — to report it

**Given** the backend is not running
**When** the tool runs
**Then** it returns `app_not_running` as a text result and never raises (FR-12)

**Given** the tool returns
**When** its result is measured
**Then** it is under roughly 200 tokens and echoes no payload back into chat (CM-1)

**Given** the MCP server package after this story
**When** it is inspected
**Then** it holds no active-deck state — the state lives in backend memory only (CM-3)
**And** the import-boundary test still passes, proving no `src.companion.app` import was introduced (AD-3)

### Story 6.3: The glass follows the agent's active-deck choice

As Brad watching the browser,
I want the deck view to switch when my agent switches decks,
So that I never have to refresh or click to keep up with the conversation.

**Acceptance Criteria:**

**Given** the app is showing the no-active-deck state
**When** an `active_deck_changed` envelope arrives
**Then** the app fetches that deck and renders the deck view (FR-07, AD-6)

**Given** the app is showing one deck
**When** an `active_deck_changed` envelope arrives for a different deck
**Then** the app switches to the new deck, and any pinned inspection from the previous deck is released

**Given** an `active_deck_changed` envelope arrives
**When** the app handles it
**Then** it does **not** treat it as `deck_changed` — the distinction is what stops the app refetching the deck it is leaving (AD-6)

**Given** a `GET /api/deck/{id}` that 404s after the switch
**When** the app handles it
**Then** it clears to the no-active-deck state (FR-11, AD-16)

**Given** several tabs are open
**When** the envelope is broadcast
**Then** every tab switches (UX-DR37)

### Story 6.4: `companion_show_suggestions` — the agent's first push

As Brad asking for card suggestions,
I want them on the glass as cards rather than as a wall of text in my terminal,
So that I can evaluate six cards by looking at them.

**Acceptance Criteria:**

**Given** the tool is defined
**When** its signature and docstring are inspected
**Then** it is `async def` and its docstring is written as the LLM-facing description, since per-tool docstrings are why OQ-2 rejected a generic `companion_display` (AD-8)

**Given** a valid payload of card ids with reasons and optional categories
**When** the agent calls the tool
**Then** the envelope is posted to `/agent/events` and the result carries `displayed` plus the connected-client count (FR-08, AD-8)

**Given** a payload exceeding a cap
**When** the tool posts it
**Then** the backend returns 413 `payload_too_large`, the tool returns `payload_rejected`, and the agent presents the content in chat as usual — nothing is lost (AD-7 as amended by the c1-4 review ruling; FR-12) <!-- amended at the C5 retro 2026-08-09: 5.5 and 6.1 were corrected to 413 at c5-5, this AC had been missed; field-cap breaches remain 400 per c5-5 Q7 -->

**Given** an empty suggestions payload
**When** it is posted
**Then** it is accepted and the view renders its deliberate empty state (AD-7)

**Given** the tool returns
**When** its result is inspected
**Then** the payload is **never echoed back into chat** and the result stays under roughly 200 tokens (CM-1)

**Given** the agent holds the pushed content regardless
**When** the app is closed
**Then** the agent presents the suggestions in chat as it always would — the companion adds a visual channel and never replaces the conversational one (NG5, SC-3)

### Story 6.5: Agent view shell with focus management and dismissal

As Brad reading agent content,
I want it presented as a full-window panel I can dismiss with Esc,
So that it commands attention while it's open and gets out of the way when I'm done.

**Acceptance Criteria:**

**Given** an agent view opens
**When** it renders
**Then** it is a full-window scrim with a 16px backdrop blur, inset 32px, containing a panel with the raise elevation, carrying an "AGENT VIEW" accent kicker, a heading title, a summary count, and a right-aligned "Close · esc" pill (UX-DR23)
**And** the body scrolls while the shell does not

**Given** the view is open
**When** its semantics are inspected
**Then** it is `role="dialog" aria-modal="true"` labelled by its heading `h2`, and **Tab cycles within it** (UX-DR23, UX-DR44)

**Given** the view opens
**When** focus moves
**Then** it moves to the view's heading (UX-DR46)

**Given** the view is dismissed by the close pill, Esc, or a click on the scrim outside the shell
**When** it closes
**Then** focus returns to the element focused before the view took it — never to `document.body` (UX-DR39, UX-DR46)

**Given** the view is dismissed
**When** its content is considered
**Then** dismissal **never clears it** — the view remains re-openable for the rest of the session (UX-DR34)

**Given** an agent view is open
**When** anything else tries to open over it
**Then** nothing does — the overlay stack is exactly one level deep (UX-DR38)

**Given** the view enters
**When** the animation runs
**Then** it fades and rises 8px over the bloom duration, **on top of an already-complete layout** (UX-DR23)
**And** under `prefers-reduced-motion` it appears in place (UX-DR42)

**Given** a card tile inside an agent view
**When** its live marker renders
**Then** it uses `accent`, not `accent-dim`, because tiles here sit on `surface-overlay` where `accent-dim` fails the 3:1 floor (UX-DR6)

### Story 6.6: A push opens its view, and a repeat push replaces it in place

As Brad who just asked a question,
I want the answer to appear without me clicking anything,
So that the agent driving the glass is something I see rather than something I have to go and find.

**Acceptance Criteria:**

**Given** no agent view is open
**When** a push arrives
**Then** its view **opens automatically** (UX-DR34 — confirmed ruling, 2026-07-25)

**Given** a Suggestions view is open
**When** another suggestions push arrives
**Then** the content is replaced **in place** with a brief crossfade over the glide duration (FR-08, UX-DR34)
**And** focus moves to the heading, whose live region announces the new push (UX-DR45, UX-DR46)
**And** under `prefers-reduced-motion` the swap is instant (UX-DR42)

**Given** a push carrying an unknown card id
**When** the view renders
**Then** that entry alone degrades to the unknown-card placeholder and the rest of the push renders normally — a push never fails wholesale (FR-13, AD-7)

**Given** an empty push
**When** the view opens
**Then** it renders the deliberate empty state with its verbatim copy, rather than rejecting (UX-DR33, AD-7)

**Given** a state panel occupies the left column while an agent view is open
**When** the deck is lost or the database becomes unavailable
**Then** the view **stays open and stays valid** — agent content is about cards, not about the deck's presence, so a lost deck does not invalidate it (UX-DR37)
**And** on close the user lands on the state panel, with the skip link and grid Tab stops withdrawn

**Given** a push arrives
**When** the announcement fires
**Then** motion is never the sole signal — the heading, its timestamp and the nav pill's marker all update (UX-DR43)

### Story 6.7: Suggestions view

As Brad evaluating six suggested cards,
I want each one shown as art with a one-line reason,
So that I can judge them by looking rather than by reading a list of names.

**Acceptance Criteria:**

**Given** a suggestions payload
**When** the view renders
**Then** each row shows a full-row-height card thumbnail at the card radius on the left, then an action badge, the card name in body-strong, the mana cost, an optional confidence in micro right-aligned, and the one-line reason beneath in body `text-secondary` (UX-DR24)

**Given** a row is hovered, focused or clicked
**When** the inspection contract applies
**Then** it behaves exactly as a card tile — hover or focus sets the detail-panel target, click pins (UX-DR24)
**And** a pinned target **survives closing the view**, so dismissing the view leaves that card in the detail panel

**Given** a row is the live inspection target
**When** its marker renders
**Then** it uses `accent` — not `accent-dim`, which fails 3:1 on this surface (UX-DR24, UX-DR6)

**Given** an entry whose card id is unknown
**When** the row renders
**Then** the thumbnail slot shows the unknown-card placeholder **and the row still renders its reason text** (UX-DR24, FR-13)

**Given** the rows
**When** their semantics are inspected
**Then** they form a `ul`/`li` structure (UX-DR44)

**Given** a thumbnail sits in a row that already shows the card name as text
**When** its alt text is inspected
**Then** it is `alt=""` — the name is announced once, from the row text (UX-DR48)

**Given** every card image in the view
**When** its source is inspected
**Then** it comes from the backend image proxy, hydrated through the single card cache (AD-11, AD-12)

### Story 6.8: Agent views nav — unread markers, re-open, and kind switching

As Brad who dismissed a view and wants it back,
I want a pill in the header for each kind of thing my agent has sent,
So that nothing the agent showed me is ever more than one click away.

**Acceptance Criteria:**

**Given** a kind that has received no push this session
**When** its pill renders
**Then** it is quiet — `text-tertiary`, no hover glow, **not focusable** — with the tooltip "Your agent hasn't sent this yet." (UX-DR28, UX-DR33)

**Given** a kind that has received a push
**When** its pill renders
**Then** it is active and shows the last push's time (UX-DR28)

**Given** a view has an unread push
**When** its pill renders
**Then** it carries the accent unread dot until that view is opened (UX-DR28)

**Given** an active pill
**When** it is clicked or activated with Enter
**Then** its view re-opens with the same content, **re-hydrated against current card data** — stale ids degrade to unknown-card placeholders (UX-DR28)
**And** nothing is re-requested from the agent

**Given** a view of one kind is open
**When** a push of a **different** kind arrives
**Then** the view switches to the new kind and the previous kind's pill is marked unread — **a push is never silently swallowed** (UX-DR34, SC-1)

**Given** the pills
**When** the Tab order is walked
**Then** they sit in the header nav, ahead of the card grid (UX-DR40)

**Given** several tabs are open
**When** pushes arrive
**Then** each tab keeps its own view state and unread markers — divergence between tabs is accepted, not solved (UX-DR37)

### Story 6.9: Degradation with the app closed, and the 250 ms push budget

As Brad running my agent with no browser open,
I want every workflow to work exactly as it did before the companion existed,
So that the app is something I open when I want it, not something I have to run.

**Acceptance Criteria:**

**Given** the companion backend is not running
**When** any companion tool is called
**Then** it returns `app_not_running` as a text result, the agent presents the content in chat as usual, and **no agent turn errors** (FR-12, SC-3)

**Given** the backend is running but no browser tab is connected
**When** a push tool is called
**Then** it returns `no_clients_connected`, so Brad can be told the content was not displayed (FR-06, FR-12)

**Given** every agent workflow that existed before this feature
**When** it is exercised with the companion app closed
**Then** it completes successfully — closing **SC-3**

**Given** the app is open with a warm image cache
**When** a suggestions push completes at the tool boundary
**Then** the view reaches **painted layout within 250 ms** — view layout, text, and cached-or-placeholder art (SC-1, NFR-05)
**And** the clock stops at first paint of the laid-out content, **not** at animation settle; the 480 ms entry animation runs on top of a complete layout and is never inside the budget

**Given** the 250 ms budget
**When** the push path is inspected
**Then** the view never blocks on image fetches, and card hydration runs concurrently with the open animation (NFR-05)

**Given** the measurement
**When** acceptance is recorded
**Then** it is an observed figure, not an assumption

**Given** all companion tool results
**When** their token cost is measured across a session
**Then** they add negligible overhead and never echo payloads (CM-1)

---

## Epic 7: The Deck Updates Itself

Brad tells the agent to add a card and the glass changes by itself — the card appears in its type
group, the curve grows, the colour spread shifts, and a screen reader hears it once. He never
touches the app. This is UJ-1's climax and closes **SC-2**.

### Story 7.1: One shared notifier, with a bounded await and no detached tasks

As a deck-mutation tool,
I want one place to tell the companion something changed,
So that a failure to notify can never damage a mutation that already succeeded — and the event can never be lost to a torn-down task.

**Acceptance Criteria:**

**Given** the notifier
**When** its location is inspected
**Then** it lives in the companion **leaf**, importing only `pydantic`, `httpx`, `src.paths` and the leaf's own siblings (AD-3, AD-9)
**And** there is exactly one — no mutation tool grows its own emit path

**Given** the notifier is called
**When** it runs
**Then** it performs a **bounded-timeout `await` of roughly 1 second** (AD-9)
**And** it does **not** use `asyncio.create_task` or any detached task, because a task that outlives its tool call can be torn down before it runs — the event never leaves the process and the deck view silently goes stale

**Given** a test asserting the ban
**When** the codebase is checked
**Then** no detached task is used on the notification path (AD-9)

**Given** the backend is unreachable, slow, or returns an error
**When** the notifier runs
**Then** every exception is **caught and logged** with `%`-style lazy args (AD-9)
**And** nothing propagates to the caller

**Given** the timeout elapses
**When** the notifier returns
**Then** the mutation's latency cost is capped at that timeout — this is what the bound is for (AD-9)

**Given** the event is emitted
**When** its shape is inspected
**Then** it is a `deck_changed` envelope carrying the deck id, under the contract from Story 5.1 (AD-6, FR-11)

### Story 7.2: Every deck-mutation tool emits after its transaction commits

As Brad editing a deck through the agent,
I want the glass told only once the change is really saved,
So that the view can never show something the database doesn't have.

**Acceptance Criteria:**

**Given** any deck-mutation tool — add, remove, update, create, import
**When** it succeeds
**Then** it calls the shared notifier **after the transaction commits**, never inside it (AD-9, FR-11)

**Given** a deck deletion
**When** it succeeds
**Then** it emits too — **deletion counts as a mutation** (FR-11, AD-9)

**Given** a mutation that fails and rolls back
**When** it returns
**Then** no event is emitted

**Given** the notifier fails while the mutation succeeded
**When** the tool returns
**Then** its own result is **completely unaffected** (AD-9)
**And** the resulting staleness window is **accepted** until FR-16, with the UI showing no staleness warning

**Given** the mutation tools after this story
**When** the import-boundary test runs
**Then** it still passes — the notifier is leaf-only, so no tool imports `src.companion.app` (AD-3)

**Given** the full set of mutation tools
**When** they are enumerated in test
**Then** every one of them emits, so none is forgotten as new tools are added

### Story 7.3: The glass refetches on `deck_changed`, coalesced and latest-wins

As Brad watching the deck view,
I want it to catch up with every change without piling up requests,
So that a burst of edits lands as one correct final state rather than a race.

**Acceptance Criteria:**

**Given** a `deck_changed` event whose deck id matches the active deck
**When** the app handles it
**Then** it refetches `GET /api/deck/{id}` (FR-11)

**Given** a `deck_changed` event for a different deck
**When** the app handles it
**Then** the active deck is not refetched
**And** the deck list may be refreshed regardless (FR-11)

**Given** a refetch is in flight
**When** a newer `deck_changed` arrives
**Then** the in-flight request is cancelled and restarted — one in-flight fetch at a time, **last response wins** (UX-DR35, NFR-04)
**And** out-of-order responses are discarded

**Given** the WebSocket reconnects
**When** the client resumes
**Then** it refetches the active deck, since events may have been missed while disconnected (NFR-04)

**Given** the freshness model
**When** it is inspected
**Then** it is "something changed, refetch" — no diffs and no patches (NFR-04)

**Given** a refetch completes
**When** the derived state updates
**Then** the grid, deck list, type-group counts, mana curve and colour distribution all recompute from the new decklist (UX-DR17, UX-DR18)

### Story 7.4: Refetch never tears down what's on screen

As Brad mid-read when a change lands,
I want the deck to stay on screen while it updates,
So that an update never blanks the thing I was looking at.

**Acceptance Criteria:**

**Given** a refetch is in flight
**When** the deck view renders
**Then** the current deck **stays on screen** with a subtle shimmer on the deck header (UX-DR35)
**And** there is never a blank screen or a skeleton teardown of a populated view

**Given** `prefers-reduced-motion: reduce`
**When** a refetch is in flight
**Then** the shimmer is replaced by static "Updating…" text in micro `text-secondary` (UX-DR42)

**Given** a pinned inspection target that still exists after the refetch
**When** the view updates
**Then** it **stays pinned** (UX-DR35)

**Given** a pinned target that no longer exists in the deck
**When** the view updates
**Then** inspection falls back to transient, targeting the first card of the first type group (UX-DR35)

**Given** a double-faced card showing its back face
**When** the refetch re-renders the grid
**Then** it is **still showing its back face** — flip state is keyed by printing uuid and survives (UX-DR15)

**Given** any point during or after a refetch
**When** the app is observed
**Then** a blank screen is never shown after first paint (UX-DR36)

### Story 7.5: The change is announced once, and motion is never the only signal

As a screen-reader user,
I want one clear statement that the deck changed,
So that I learn about the update without a flood of announcements or a glow I can't see.

**Acceptance Criteria:**

**Given** a coalesced refetch completes
**When** the announcement fires
**Then** a polite live region announces **exactly once**: "Deck updated — 62 cards" (UX-DR45)
**And** the refetch-coalescing machinery is the debounce, so a burst of `deck_changed` events yields exactly one announcement

**Given** a card's quantity changed
**When** its tile re-renders
**Then** the quantity badge flashes the accent glow **once** (UX-DR16)
**And** the flash is **garnish** — the accessible signals are the updated group-header count and the live-region announcement

**Given** `prefers-reduced-motion: reduce`
**When** a quantity changes
**Then** the glow is omitted entirely, and the count text plus the announcement carry the signal alone (UX-DR42, UX-DR43)

**Given** any deck change
**When** its signalling is reviewed
**Then** motion is never the sole carrier of the information (UX-DR43)

**Given** the mana curve bars change height
**When** they animate
**Then** under reduced motion they jump instantly (UX-DR42)

### Story 7.6: Deck deletion, and agent views during a refetch

As Brad whose deck was just deleted,
I want the glass to fall back cleanly,
So that a deleted deck leaves a calm empty state rather than a broken view.

**Acceptance Criteria:**

**Given** the active deck is deleted through the agent
**When** the emitted `deck_changed` triggers a refetch
**Then** the refetch 404s and the app clears to the **no-active-deck** state (FR-11, AD-16, UX-DR30)

**Given** the app has cleared to no-active-deck
**When** the state panel renders
**Then** it lists the remaining decks from `GET /api/decks`, non-clickable (UX-DR33)

**Given** an agent view is open
**When** a deck refetch completes behind it
**Then** the view is **untouched** and the deck view updates behind it (UX-DR37)
**And** **no announcement fires from behind a modal**

**Given** an agent view is open
**When** the active deck is deleted
**Then** the view stays open and stays valid; on close the user lands on the no-active-deck panel (UX-DR37)

**Given** the grid is gone
**When** the Tab order is walked
**Then** the skip link and the grid's Tab stops are withdrawn (UX-DR31)

### Story 7.7: The loop closes — UJ-1 end to end

As Brad,
I want to tell my agent to add a card and watch the glass update by itself,
So that the product's central promise — the agent drives, the app shows — is something I experience rather than something I'm told.

**Acceptance Criteria:**

**Given** the app is open with an active deck and the agent adds a card
**When** the mutation commits
**Then** within roughly a second the card appears in its type group, the curve bar for its mana value grows, the colour distribution shifts, and its quantity badge flashes (SC-2, UJ-1 step 9)
**And** Brad performs **no** action in the browser

**Given** the whole of UJ-1
**When** Flow 1 of `EXPERIENCE.md` is walked end to end
**Then** every beat completes: deck loads within 1 s, suggestions bloom within 250 ms, a pin survives dismissing the view, and the deck updates by itself

**Given** the event POST fails after the mutation persisted
**When** the failure path is exercised
**Then** the deck view is stale until the next event or reconnect, **no error surfaces**, and the mutation's result is unaffected (AD-9, FR-12)
**And** this accepted staleness window is recorded as expected behaviour until FR-16

**Given** the glass throughout
**When** its interactions are audited
**Then** nothing in the browser mutated the deck — every state change travelled agent → MCP tool → SQLite → notification → browser refetch (AD-2, NG1)

---

## Epic 8: Release Readiness

The companion is something Brad would put in front of strangers: `view_deck` points at its
replacement, the docs tell you where the image cache lives and how to remove it, the PRD no longer
contradicts the architecture, and Brad has personally judged the thing against the UX spec and
said yes.

### Story 8.1: Deprecate `view_deck` and freeze `src/viewer`

As a user of the existing tools,
I want the old HTML deck renderer to keep working while telling me what replaced it,
So that nothing breaks under me and nobody invests in a component that's on its way out.

**Acceptance Criteria:**

**Given** the `view_deck` tool
**When** its docstring is read
**Then** it is marked deprecated and **names the companion app as its replacement** (AD-15)

**Given** `view_deck` is called
**When** it runs
**Then** it still renders HTML exactly as before, through Phases 1 and 2, so **SC-3** holds through the transition (AD-15)

**Given** `src/viewer`
**When** any new work is proposed against it
**Then** no new capability lands there, and its removal is scheduled for the next minor release once the companion is proven (AD-15)

**Given** the companion's UI
**When** its assets are inspected
**Then** it never reuses `src/viewer/template.html` — two renderers of one entity would diverge (AD-15)

**Given** the removal is deferred rather than done
**When** the deferral is recorded
**Then** it is written into the release notes or CHANGELOG so it is not forgotten

### Story 8.2: Image cache stewardship — documented location, inspection and removal

As Brad wondering what this app is doing to my disk,
I want to know where the cached art lives and how to get rid of it,
So that an unbounded cache is a documented choice rather than a surprise.

**Acceptance Criteria:**

**Given** the README
**When** the cache section is read
**Then** it names the exact location `data_dir()/image_cache/` and explains the two-character sharding (NFR-09)
**And** it notes that the location follows `PLANESWALKER_DATA_DIR` when set

**Given** a user wants to inspect or clear the cache
**When** they read the documentation
**Then** there is a clear, copy-pasteable command to do so (NFR-09, AD-11)

**Given** the cache has no eviction
**When** the documentation describes it
**Then** it says so plainly, gives the expected footprint — roughly 12 MB per 100-card deck at one size — and records that a policy will be sized against a real footprint rather than guessed (AD-11)

**Given** the uninstall path
**When** it is documented
**Then** it tells the user what the app leaves behind: the image cache, and the discovery file if the process did not exit cleanly (NFR-09, AD-15)

**Given** a data refresh changes a card's `image_uris`
**When** the staleness is documented
**Then** the accepted behaviour — the old entry is served, because the key is id plus size plus face — is stated rather than left to be discovered (AD-11)

### Story 8.3: Reconcile the PRD with what was built

As the next person to read the PRD,
I want it to describe the system that exists,
So that a requirement document and an architecture spine don't quietly contradict each other for the next reader.

**Acceptance Criteria:**

**Given** PRD NFR-02
**When** it is amended
**Then** it no longer names `mode=ro` as the mechanism, and instead describes the **CI import boundary** that enforces read-only — with the reason: `mode=ro` on a WAL database drags in the `-shm` recipe, and `immutable` would foreclose FR-16 (AD-2)

**Given** PRD FR-14 and the glossary
**When** they are amended
**Then** the discovery file location is `src.paths.data_dir()/companion.json`, not `~/.artificial-planeswalker/` (AD-4)

**Given** PRD FR-04
**When** it is amended
**Then** face handling is described as driven by the **presence of per-face `image_uris`**, not by the card's Scryfall `layout` — `cards` has no `layout` column (AD-11)

**Given** the six additions made during story work
**When** the PRD or its addendum is updated
**Then** each is recorded: the `card_not_found` reason token; `GET /api/deck/{id}/format-check`; `GET`/`PUT /api/active-deck`; the `active_deck_changed` envelope kind; `deck_not_found` as a `companion_set_active_deck` outcome; and the ruling that all four payload shapes were fixed in Phase 1

**Given** the four UX rulings
**When** the spines are updated
**Then** `EXPERIENCE.md` and the 2026-07-25 validation report record them as **confirmed** rather than awaiting Brad's decision

**Given** the amendments are made
**When** the documents are re-read together
**Then** no PRD statement contradicts an architecture decision

### Story 8.4: Release documentation for the companion app

As someone installing this for the first time,
I want the README to tell me what the companion is, how to start it, and what it needs,
So that I can get from install to card art without reading the source.

**Acceptance Criteria:**

**Given** the README
**When** the companion section is read
**Then** it explains what the companion app is, that it is optional, and that every agent workflow works without it (SC-3, NG5)

**Given** the launch instructions
**When** they are followed
**Then** `uv run artificial-planeswalker companion` is the single documented command, matching the copy in the PRD and `EXPERIENCE.md` (AD-14, SC-4)
**And** the docs state that Node is never required at install or runtime (NFR-07, AD-13)

**Given** a fresh install with no card database
**When** the docs describe first run
**Then** they explain that the app starts anyway and guides you to `initialize_database` (FR-22)

**Given** the licensing obligations
**When** the docs are reviewed
**Then** the Scryfall attribution and the Wizards of the Coast Fan Content Policy notice appear in the project's documentation as well as in the app footer (NFR-08)

**Given** the CHANGELOG
**When** the release is prepared
**Then** it records the companion app, the `view_deck` deprecation, and the new dependencies with their version floors — including **why TypeScript is pinned below 6.1**

**Given** the port and discovery behaviour
**When** they are documented
**Then** the default port, the ephemeral fallback, the single-instance rule and the "already running" message are explained, so a port conflict is self-diagnosable

### Story 8.5: Plugin distribution parity

As someone installing via the Claude Code plugin,
I want the companion to arrive complete,
So that the plugin path isn't a second-class install missing the UI it is supposed to serve.

**Acceptance Criteria:**

**Given** the plugin tree
**When** it is rebuilt
**Then** it mirrors the committed SPA bundle from `src/companion/app/static/` (AD-13)
**And** the existing drift check covers the mirrored copy

**Given** both copies of the bundle
**When** they are inspected
**Then** they are treated as **generated artifacts** and neither is hand-edited (AD-13)

**Given** `.mcp.json` and `plugin/.mcp.json`
**When** they are compared against the pre-companion versions
**Then** neither changed — both still invoke `python -m src.mcp_server` directly (AD-14)

**Given** a plugin install on a clean machine
**When** the two-command install is performed and the companion is launched
**Then** the app serves and renders, with no Node toolchain present (SC-4, AD-13)

**Given** the skills directory convention
**When** the plugin is built
**Then** only product skills ship — the `bmad-*` skills do not leak into the plugin

### Story 8.6: The SC-5 gate

As Brad, the sole quality gate,
I want to judge the finished app against the UX spec before it ships,
So that "looks like a deliberate product" is a decision I made rather than an assumption someone else recorded.

**Acceptance Criteria:**

**Given** the completed Phase-1 app
**When** Brad reviews it against `DESIGN.md` and `EXPERIENCE.md`
**Then** he judges whether the deck view and agent panel read as a deliberate product rather than a debug dashboard (SC-5, UX-DR49)
**And** this judgement is **human, performed by Brad, and cannot be automated or delegated**

**Given** the anti-patterns the gate tests against
**When** the app is reviewed
**Then** there are no raw JSON views, no log panes, no dense tables of ids, no error pages, no toast storms and no alert colours (UX-DR49, UX-DR30)

**Given** four analytical panels are permanently on screen
**When** the "not a debug dashboard" question is asked
**Then** the answer is carried by typography, spacing and restraint rather than by sparseness — the tension is acknowledged, not ignored (UX-DR49)

**Given** the deferred arrow-key grid navigation
**When** the pre-public-release checklist is reviewed
**Then** the revisit flag is consciously **actioned or re-accepted**, because the footer's Fan Content Policy links sit behind the grid in the Tab order (UX-DR40)

**Given** the reduced-motion inventory
**When** it is audited against the shipped app
**Then** every motion in the app has an entry with a fallback, and any motion added during implementation was added to the list (UX-DR42)

**Given** the footer attribution
**When** every surface is checked
**Then** it is present and visible without scrolling — a condition of public release (NFR-08, UX-DR32)

**Given** the gate outcome
**When** it is recorded
**Then** it is written down with its date and any conditions, so a later reader knows the gate was actually run

---

## Epic 9: The Remaining Push Kinds *(Phase 2)*

The agent gains its full vocabulary: proposed swaps as out/in pairs, tier lists, and titled card
groups with a paragraph of reasoning each — including cards the deck doesn't yet run. Deliberately
cheap, because Epics 5 and 6 settled the envelope and the payload discipline: three new tools,
three new views, **no new seam and no contract change**.

Each story pairs its tool with its view. Landing a tool without its renderer would let a push
arrive that the UI cannot display, breaking the "a push is never silently swallowed" rule mid-epic.

### Story 9.1: Proposed swaps — tool and view

As Brad weighing a change to my deck,
I want swaps shown as the card leaving beside the card arriving,
So that I can judge a trade by looking at both cards rather than reading two names.

**Acceptance Criteria:**

**Given** `companion_show_swaps(payload)`
**When** it is implemented
**Then** it is `async def`, posts the `swaps` envelope through the existing leaf client, and returns one closed outcome token plus the client count (FR-09, AD-8)
**And** it requires **no change** to `contracts.py`, because the `swaps` payload shape and its caps were fixed in Story 5.1 (AD-6, AD-7)

**Given** a swaps payload
**When** the view renders each row
**Then** the out-card and in-card tiles sit side by side joined by an accent arrow glyph, on `surface-overlay` at the medium radius (UX-DR25)
**And** "Out · N copies" is tinted negative and "In · N copies" positive, in micro, above their respective tiles

**Given** the tints
**When** they are applied
**Then** they appear on the **labels only — never on the art** (UX-DR25, UX-DR7)

**Given** a row
**When** it renders its explanation
**Then** the rationale sits right of the pair in body `text-secondary`, with `StatChip`s for price, curve and confidence beneath (UX-DR25)

**Given** a swap whose "in" card has zero copies available
**When** the row renders
**Then** it renders normally with its count label reading "0 copies", and the rationale carries the explanation (UX-DR25)

**Given** either tile
**When** it is hovered, focused or clicked
**Then** it follows the standard inspection contract (UX-DR25)

**Given** an unknown card id on either side
**When** the row renders
**Then** that tile degrades to the unknown-card placeholder and the row still renders (FR-13)

**Given** the Swaps nav pill
**When** the first swaps push arrives
**Then** the pill becomes active automatically, because the nav is generic over the closed `kind` enum from Story 5.1 (UX-DR28)

### Story 9.2: Tier lists — tool and view

As Brad ranking a pool of cards,
I want tiers shown as labelled buckets with the cards in them,
So that a ranking reads at a glance and the rank never depends on colour alone.

**Acceptance Criteria:**

**Given** `companion_show_tier_list(payload)`
**When** it is implemented
**Then** it is `async def`, posts the `tier_list` envelope through the existing leaf client, and returns one closed outcome token plus the client count (FR-10, AD-8)
**And** it requires no contract change (AD-6)

**Given** a tier row
**When** it renders
**Then** a 132px chip on the well surface carries the tier letter at 44px with the tier name in micro `text-tertiary` beneath, followed by the note in body `text-secondary` and a thumbnail row (UX-DR26)

**Given** the five tier letters
**When** they render
**Then** they ramp `accent-bright` (S) · `accent` (A) · `text-primary` (B) · `text-secondary` (C) · `text-tertiary` (D) (UX-DR26)
**And** at 44px all five are large text and clear the contrast floor comfortably

**Given** any tier
**When** it renders
**Then** the letter is **always accompanied by its name in text**, so colour never carries rank alone (UX-DR26, UX-DR41)

**Given** a payload containing an empty bucket
**When** the view renders
**Then** that bucket is **skipped**, not rendered as an empty shell (UX-DR26)

**Given** the buckets
**When** they render
**Then** they appear in **payload order**, not re-sorted by the UI (UX-DR26)

**Given** the free-text tier `name`
**When** it renders
**Then** it carries the MTG meaning — "Auto-include", "Filler", "Cut" — while the closed `letter` enum drives the colour ramp (AD-7)

**Given** thumbnails in a tier row
**When** they are used
**Then** they follow the inspection contract, and their alt text is `alt=""` where the row already names the card in text (UX-DR26, UX-DR48)

### Story 9.3: Card groups — tool and view

As Brad asking "show me the one-drops that carry this curve",
I want titled groups of cards each with a paragraph of reasoning,
So that the agent can answer a question about an arbitrary set of cards, including ones my deck doesn't run.

**Acceptance Criteria:**

**Given** `companion_show_groups(payload)`
**When** it is implemented
**Then** it is `async def`, posts the `groups` envelope through the existing leaf client, and returns one closed outcome token plus the client count (FR-23, AD-8)
**And** it requires no contract change (AD-6)

**Given** a group
**When** it renders
**Then** it shows the title in heading type with a card count in numeric `text-tertiary`, the rationale paragraph in body `text-secondary` capped at roughly a 900px measure, then a wrapped tile row (UX-DR27)

**Given** a group contains cards **not in the active deck** — budget substitutes, sideboard options, answers the deck doesn't yet run
**When** those tiles render
**Then** they carry **no quantity badge** (UX-DR27, FR-23)
**And** the badge means "copies in this deck", so rendering "×0" would be a lie

**Given** a group contains cards that **are** in the active deck
**When** those tiles render
**Then** they carry their quantity badge as normal (UX-DR27)

**Given** an empty group
**When** the view renders
**Then** it is skipped (UX-DR27)

**Given** the tiles
**When** they are interacted with
**Then** they follow the standard inspection contract (UX-DR27)

**Given** this view is distinct from Suggestions
**When** the two are compared
**Then** Suggestions is a flat list with one-line reasons and no grouping, while Groups carries a title and a paragraph of reasoning over an arbitrary card set — which is why OQ-2's ruling gives each kind its own tool rather than a generic `companion_display` (FR-23)

**Given** all four push kinds now exist
**When** the nav renders
**Then** it shows a pill per kind, each quiet until its first push, and the agent-view switching rules from Story 6.8 apply unchanged (UX-DR28, UX-DR34)

---

## Epic 10: Session History, Status Detail & Performance Polish *(Phase 2)*

Brad can revisit what the agent showed him earlier in the session, see at a glance which port and
instance he's connected to, and the 250 ms / 1 s budgets are measured rather than assumed.

### Story 10.1: Connection pill status detail

As Brad with more than one thing running,
I want the pill to tell me which backend instance I'm actually talking to,
So that I can tell a stale tab from a live one without guessing.

**Acceptance Criteria:**

**Given** the connection pill from Story 5.7
**When** it is hovered **or receives keyboard focus**
**Then** it reveals the port and instance id from `GET /health` in a tooltip (FR-15, UX-DR29)
**And** focus parity is required — hover is never the only path (UX-DR39)

**Given** the tooltip
**When** its semantics are inspected
**Then** it is tied to the pill via `aria-describedby` (UX-DR29, UX-DR44)

**Given** the pill at rest
**When** it is observed
**Then** it remains quiet and static — the dot never animates, and the text still names the state (UX-DR29)

**Given** the backend has restarted with a new instance id
**When** the tab reconnects
**Then** the tooltip reflects the new instance id, so a reconnect to a *different* process is visible rather than silent (AD-4)

**Given** the pill is the last stop before the footer in the Tab order
**When** it is reached
**Then** it carries the standard focus ring and a hit area of at least 24×24px (UX-DR40, UX-DR47)

### Story 10.2: Session history

As Brad two pushes later,
I want to get back to something the agent showed me earlier,
So that dismissing a view never means losing what was in it.

**Acceptance Criteria:**

**Given** the session-history home is the UX spine's open residual
**When** this story begins
**Then** the decision is made and recorded **first** — extend the nav, or add a strip inside each view's header — because the two produce different components
**And** the chosen option is written into `EXPERIENCE.md` and `DESIGN.md` before implementation starts

**Given** pushes arrive during a session
**When** history records them
**Then** it retains a capped list — roughly the last 20 — each labelled by kind and time (FR-18)

**Given** the history list
**When** it is ordered
**Then** it orders by **`ts`**, never by `id` — `id` is opaque and carries identity and dedupe, not ordering (AD-6)

**Given** a history entry is opened
**When** it renders
**Then** it **re-hydrates against current card data**, and ids that no longer resolve degrade to unknown-card placeholders (FR-18, FR-13)

**Given** history storage
**When** it is inspected
**Then** it is **in-browser only** and clears on refresh — the backend retains no events, which is what keeps the event model stateless and fire-and-forget (FR-18)

**Given** several tabs are open
**When** history is compared between them
**Then** each tab has its own — divergence is accepted, not synchronised (UX-DR37)

**Given** the cap is reached
**When** a new push arrives
**Then** the oldest entry is dropped without error

**Given** a revisited push
**When** it is opened
**Then** nothing is re-requested from the agent (UX-DR28)

### Story 10.3: Measure the latency budgets and close the gaps

As Brad,
I want the performance claims verified rather than asserted,
So that "under 250 ms" is a number someone observed instead of a sentence someone wrote.

**Acceptance Criteria:**

**Given** the push path
**When** it is profiled
**Then** event-to-painted-layout is measured against the **250 ms** budget, with the clock stopping at first paint of laid-out content and the entry animation excluded (NFR-05, SC-1)

**Given** a 100-card Commander deck with a warm image cache
**When** cold open is profiled
**Then** full layout is measured against the **1 second** budget (NFR-05, SC-2)

**Given** any measured gap against either budget
**When** it is found
**Then** it is closed, or recorded as an accepted deviation with its reason — not left ambiguous

**Given** the image pacer under a cold-cache deck load
**When** it is profiled
**Then** the pacing is confirmed not to block the event loop, and a concurrent push still meets its budget while images are queued (AD-11, NFR-05)

**Given** a full session
**When** CDN requests are counted
**Then** each image, size and face combination was fetched **at most once** per cache lifetime (CM-2)

**Given** the unbounded image cache
**When** a real footprint is measured after sustained use
**Then** the figure is recorded, so an eviction policy can eventually be sized against evidence rather than guessed (AD-11)

**Given** companion tool results across a session
**When** their token cost is measured
**Then** it is confirmed negligible, with no payload ever echoed into chat (CM-1)

**Given** the profiling results
**When** they are recorded
**Then** they are written down with the hardware and conditions they were measured under
