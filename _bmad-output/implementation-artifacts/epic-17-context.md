# Epic 17 Context: Session History, Status Detail & Performance Polish (Phase 2)

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Close out the companion app's Phase 2 polish: Brad can revisit anything the agent showed him earlier in the session, see at a glance which backend port and instance a tab is actually connected to, and the 250 ms push and 1 s cold-open performance budgets become measured numbers rather than asserted ones — with any gap either closed or recorded as an accepted deviation.

## Stories

- Story 17.1: Connection pill status detail
- Story 17.2: Session history
- Story 17.3: Measure the latency budgets and close the gaps

## Requirements & Constraints

- **Connection status detail:** the UI must show which backend it is talking to — port and instance id, sourced from `GET /health` — layered onto the existing connection pill. After a backend restart with a new instance id, a reconnect must make the new identity visible rather than silent.
- **Session history:** a capped list (roughly the last 20 pushes), each labelled by kind and time, lets the user reopen earlier pushes. History is **in-browser only and clears on refresh** — the backend retains no events; the event model stays stateless and fire-and-forget. Each tab keeps its own history; divergence between tabs is accepted, never synchronised. At the cap, the oldest entry drops silently. Reopening an entry never re-requests anything from the agent.
- **Re-hydration:** a reopened history entry re-hydrates against current card data; card ids that no longer resolve degrade to unknown-card placeholders (cards travel as Scryfall printing UUIDs only — the UI owns hydration).
- **Performance budgets:** event-to-painted-layout under **250 ms** (clock stops at first paint of laid-out content; the ~480 ms entry animation and first-fetch image paint are excluded), and full layout of a 100-card Commander deck with a warm image cache under **1 second** on cold open. Both must be *measured*, with hardware and conditions recorded. Any gap is closed or written down as an accepted deviation with its reason.
- **Image traffic:** across a full session each image+size+face combination hits the Scryfall CDN at most once per cache lifetime; the pacer must not block the event loop, and a concurrent push must still meet its budget while images are queued. The unbounded cache's real footprint after sustained use gets recorded so a future eviction policy can be sized against evidence (measured baseline: a cold 99-card deck is ~8.5 MB, ~90 KB/image; ~10 s to fully paint is the pacer, not bytes).
- **Token cost:** companion tool results across a session must be confirmed negligible — no payload is ever echoed into chat; tool results stay compact (~200 tokens, one closed outcome token plus client count).

## Technical Decisions

- **Discovery & identity:** `data_dir()/companion.json` holds `{port, token, instance_id}`; `GET /health` echoes `instance_id`, which is how callers distinguish a live backend from a foreign process on a recycled port. Story 17.1 surfaces exactly this identity in the UI.
- **Envelope:** every WS message is `{kind, id, ts, payload}` with `kind` a closed six-value enum (`suggestions | swaps | tier_list | groups | deck_changed | active_deck_changed`). **History must order by `ts`** (`datetime.now(UTC)`), never by `id` — `id` is opaque and carries identity/dedupe only. `id` + `ts` are the fields that make either session-history home buildable.
- **Image proxy:** all art routes through `GET /api/card-image/{scryfall_id}?size=&face=`, paced behind one backend-global semaphore plus request spacing, fully `async` (a blocking pacer would eat the 250 ms push budget — this is exactly what 17.3 verifies). Cache is content-addressed, atomic (temp + rename), unbounded in MVP with a documented location.
- **Push path:** the backend shape-validates and relays; it never reads the database on the push path — the latency budget depends on this.
- **Testing convention:** the bulk runs in-process (httpx `ASGITransport` + in-process MCP client); exactly one `integration`-marked test boots a real backend. Profiling in 17.3 necessarily observes the real process.

## UX & Interaction Patterns

- **Connection pill (17.1):** bottom-left; 8px dot (positive live / caution reconnecting / negative backend-gone), all static — **never pulsing, never animated** — with micro text naming the state and active deck; the dot never carries state alone. Hover **or keyboard focus** reveals the port/instance tooltip, tied via `aria-describedby`; focus parity is mandatory — hover is never the only path to information. Standard focus-visible ring; hit area ≥ 24×24px; it is the last Tab stop before the footer. Every interactive element is a real `<button>`/`<a>`.
- **Session history (17.2):** the history home is **the UX spine's one open residual** — extend the nav pills, or add a strip inside each view's header. The two options produce different components, so the decision must be made and recorded in `EXPERIENCE.md` and `DESIGN.md` **before implementation starts**.
- **Existing view behavior carries over:** a push opens its view automatically; dismissal never clears content (views stay re-openable from their pills); each pill shows the last push's time and an unread dot; agent views are the only modal, one overlay level deep; placeholder-then-fill imagery with no reflow on image arrival; unknown-card entries use the named/unknown placeholder pattern.
- **Motion budget (relevant to 17.3's measurement):** the agent-view entry animation (fade + 8px rise, 480 ms) sits *outside* the 250 ms budget by design — layout must be complete before it plays.

## Cross-Story Dependencies

- **17.2 is blocked on the session-history home decision** (nav extension vs per-view header strip) — an open UX ruling that must be recorded before any history component is built. 17.1 and 17.3 are not blocked by it.
- 17.1 builds on the existing connection pill (Story 12.7) and `GET /health`; 17.2 builds on the existing WS envelope/store and the four shipped push views; 17.3 measures paths built across Epics 10–16 rather than adding features.
- This is the final epic of the 0.5.0 companion release — the release is cut after Epic 17 completes.
