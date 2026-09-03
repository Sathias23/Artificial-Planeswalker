# Epic 17 Context: Session History, Status Detail & Performance Polish

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Close out the companion app's Phase 2 (formerly "c10" in planning docs): Brad can revisit anything the agent showed him earlier in the session via a capped, in-browser history of pushes; he can see at a glance which port and backend instance a tab is actually talking to through connection-pill status detail; and the 250 ms push / 1 s deck-render latency budgets become numbers someone observed rather than sentences someone wrote. Three small concerns share one epic because each is too small to carry its own and all land on the same surfaces. Depends on the realtime channel and push-tool epics (12, 13).

## Stories

- Story 17.1: Connection pill status detail
- Story 17.2: Session history
- Story 17.3: Measure the latency budgets and close the gaps
- Story 17.4: Open the companion from the agent
- Story 17.5: Welcome surface — a first impression instead of placeholders and a list

## Requirements & Constraints

- **Status detail:** the always-visible connection pill (live / reconnecting / backend-gone plus active deck name) reveals the port and instance id from `GET /health` on hover **or keyboard focus** — hover is never the only path. After a backend restart, the reconnected tab must show the new instance id so a reconnect to a different process is visible rather than silent.
- **Session history:** a capped list of roughly the last 20 pushes, each labelled by kind and time. Revisited entries re-hydrate against current card data; ids that no longer resolve degrade per entry to unknown-card placeholders. History is **in-browser only and clears on refresh** — the backend retains no events (the event model stays stateless and fire-and-forget). Each tab has its own history; divergence between tabs is accepted, never synchronised. At the cap the oldest entry drops silently. Reopening a push never re-requests anything from the agent.
- **Performance budgets:** event-to-painted-layout ≤ 250 ms (clock stops at first paint of laid-out content; entry animation excluded); cold open of a 100-card Commander deck with a warm image cache ≤ 1 s. Any measured gap is either closed or recorded as an accepted deviation with its reason — never left ambiguous. Results are recorded with the hardware and conditions they were measured under.
- **Counter-metrics to confirm:** each image+size+face combination is fetched from the Scryfall CDN at most once per cache lifetime; companion tool results add negligible token cost (compact text, ~200-token ceiling, no payload ever echoed into chat). Measure the real footprint of the unbounded image cache after sustained use so an eviction policy can eventually be sized from evidence.

- **Open from the agent (17.4):** a read-only `companion_status` tool reports running / URL / connected tabs (a new optional `clients` field on `GET /health`) / the exact launch command (`uv run --directory "<install root>" artificial-planeswalker companion --open`, root derived from `__file__`); a new `companion` skill drives it — status first, then the launch command in a background shell, wait for the URL line, confirm. `--open` is the launcher's own `webbrowser.open` after the URL line (and on the already-running branch, the live URL). AD-15 holds: the MCP server never spawns the companion. `app_not_running` copy and the four existing skills ripple from "skip silently" to "offer to open it".
- **Welcome surface (17.5):** the shell's c2-1 placeholder convention is retired (every slot filled since c6-8; an empty region renders nothing, `slot()` returns `null`); the main grid collapses to one track (`data-single`) when `right` is empty; the no-active-deck arm renders `Welcome` — `ui/public/hero.jpg` (copy of `docs/hero-image.jpg`) as a decorative `<img alt="">` banner above the unchanged `StatePanel`, the deck names restyled as wrapping chips (`<ul>/<li>` semantics kept, non-clickable). DESIGN.md gains `components.welcome`; the other five panels are untouched.

## Technical Decisions

- **Envelope ordering:** every WS message is `{kind, id, ts, payload}`; `id` is opaque — identity and dedupe only. **History orders by `ts`** (UTC), never by `id`. The kind enum is closed: four push kinds (`suggestions | swaps | tier_list | groups`) plus signals (`deck_changed | active_deck_changed`).
- **Payloads:** cards are referenced by Scryfall printing UUID only; the UI hydrates names/art through the existing REST card-data and image endpoints. Unknown IDs degrade per entry, never wholesale. The backend never reads the database on the push path.
- **Instance identity:** the discovery file carries `{port, token, instance_id}`; `GET /health` echoes `instance_id`. That echo is the tooltip's data source and the restart-visibility mechanism.
- **Image pacing:** all imagery routes through the backend proxy behind a single global async semaphore with request spacing; pacing must never block the event loop — profiling must verify a concurrent push still meets its budget while a cold-cache image queue drains. Cache is content-addressed, atomic, unbounded in MVP (a cold 100-card deck ≈ 8.5 MB / ~90 KB per image, ~10 s to fully paint — an expected observation, not a defect, since the budgets exclude first-fetch paint).
- **State/store:** the UI's state comes only from REST responses and WS messages; card hydration goes through the single zustand card cache. History extends the existing per-kind push-retention store (the one the nav pills' re-open path uses) from "latest per kind" to "last 20 overall" — no second store, no new state library.

## UX & Interaction Patterns

- **Session-history home is RULED (2026-08-22): extend the nav** — the per-view-header strip was not taken. A fifth "History" pill after the four kind pills (nav-pill spec verbatim plus a stroke-based clock glyph) toggles a **non-modal popover** anchored under the header. Popover: last ~20 pushes newest-first; each entry a real `<button>` with kind label, push title (when present), and tabular-numeric time; activating an entry closes the popover **then** opens that push's view (popover and modal never coexist — overlay stack stays one level deep). Pill is `<button aria-expanded aria-haspopup>`; dismiss via entry activation, Esc, outside click, or re-toggling the pill. Not a modal, not a landmark, not a live region — a push arriving while it is open appears at the top unannounced (and still opens its view, closing the popover first). The pill **never carries an unread dot** (unread stays per-kind). Quiet/non-focusable until the first push of any kind, using the kind pills' disabled + pointer-tooltip + programmatic-description pattern with its own copy string. Focus: popover open → first (newest) entry; close → back to the History pill. Enter animation is an opacity-only fade over the existing `glide` token (no new motion token or reduced-motion CSS; the documentation inventory still gains its row). Styling tokens live in the design spec's `history-popover` block (surface-overlay, hairline border, elevation glow, 480 px max-height with internal scroll).
- **Esc order:** topmost first — open agent view, then history popover, then active pin. One accepted residual: with focus outside the pill+popover wrapper while the popover is open, a single Esc closes the popover and releases an active pin together.
- **Connection pill:** stays quiet and static — the dot never animates and never carries state alone; the text names the state. Tooltip is tied to the pill via `aria-describedby`. The pill is the last Tab stop before the footer, carries the standard focus ring, and has a ≥ 24×24 px hit area — as does every history entry.
- **Nav pills** already show each kind's last-push time; history is the re-open path for *any* retained push, not just the latest per kind.

## Cross-Story Dependencies

- 17.2's first AC (decide and record the history home before implementing) is satisfied — the ruling and its sub-treatments are in the UX spec, confirmed at implementation.
- 17.2 builds on the push-retention store and view shell from Epic 13; 17.1 builds on the pill shell and reconnect behaviour from Epic 12 (status-requirement split: shell in 12, detail here).
- 17.3 profiles surfaces built across Epics 11–16 and runs after 17.1/17.2 land, since history and tooltip work touch the same render paths it measures.
- Status note (2026-08-22): all three stories are merged to the epic umbrella branch; budgets measured and holding. Remaining: epic retro, integration PR to master, 0.5.0 cut.
