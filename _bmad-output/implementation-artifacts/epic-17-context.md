# Epic 17 Context: Session History, Status Detail & Performance Polish

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Close out the companion app's Phase 2: Brad can revisit anything the agent showed him earlier in the session (a capped, in-browser history of pushes), can see at a glance which port and backend instance a tab is actually talking to (connection-pill status detail), and the 250 ms push / 1 s deck-render latency budgets become measured numbers rather than asserted ones. Three small concerns merged into one epic because each is too small to carry its own and all land on the same surfaces. Depends on the realtime channel and push-tool epics (12, 13).

## Stories

- Story 17.1: Connection pill status detail
- Story 17.2: Session history
- Story 17.3: Measure the latency budgets and close the gaps

## Requirements & Constraints

- **Status detail:** the always-visible connection pill (already shipping: live / reconnecting / backend-gone states plus active deck name) gains port and instance-id detail sourced from `GET /health`, revealed on hover **or keyboard focus** — hover is never the only path. After a backend restart, the reconnected tab must show the new instance id so a reconnect to a different process is visible rather than silent.
- **Session history:** a capped list of roughly the last 20 pushes, each labelled by kind and time; revisited entries re-hydrate against current card data; ids that no longer resolve degrade to unknown-card placeholders. History is **in-browser only and clears on refresh** — the backend retains no events (the event model stays stateless and fire-and-forget). Each tab has its own history; divergence between tabs is accepted, never synchronised. At the cap the oldest entry drops silently. Reopening a push never re-requests anything from the agent.
- **Performance budgets:** event-to-painted-layout ≤ 250 ms (clock stops at first paint of laid-out content; entry animation excluded); cold open of a 100-card Commander deck with warm image cache ≤ 1 s. Any measured gap is either closed or recorded as an accepted deviation with its reason. Results are recorded with the hardware and conditions they were measured under.
- **Counter-metrics to confirm:** each image+size+face combination is fetched from the Scryfall CDN at most once per cache lifetime; companion tool results add negligible token cost (compact text, ~200-token ceiling, no payload ever echoed into chat). Measure the real footprint of the unbounded image cache after sustained use so an eviction policy can eventually be sized from evidence.

## Technical Decisions

- **Envelope ordering (AD-6):** every WS message is `{kind, id, ts, payload}`; `id` is opaque — identity and dedupe only. **History orders by `ts`** (UTC), never by `id`. The kind enum is closed: four push kinds (`suggestions | swaps | tier_list | groups`) plus signals (`deck_changed | active_deck_changed`).
- **Payloads (AD-7):** cards are referenced by Scryfall printing UUID only; the UI hydrates names/art through the existing REST card-data and image endpoints. Unknown IDs degrade per entry, never wholesale. The backend never reads the database on the push path.
- **Instance identity (AD-4):** the discovery file carries `{port, token, instance_id}`; `GET /health` echoes `instance_id`. That echo is the tooltip's data source and the restart-visibility mechanism.
- **Image pacing (AD-11):** all imagery routes through the backend proxy behind a single global async semaphore with request spacing; pacing must never block the event loop — 17.3 verifies a concurrent push still meets its budget while a cold-cache image queue drains. Cache is content-addressed, atomic, unbounded in MVP (a cold 100-card deck ≈ 8.5 MB, ~10 s to fully paint — compliant, since the budgets exclude first-fetch paint).
- **State/store:** the UI's state comes only from REST responses and WS messages; card hydration goes through the single zustand card cache. History extends the existing per-kind push-retention store (the one the nav pills' re-open path uses) from "latest per kind" to "last 20 overall" — no second store, no new state library.

## UX & Interaction Patterns

- **Session-history home is RULED (2026-08-22): extend the nav.** A fifth "History" pill after the four kind pills — nav-pill spec verbatim plus a stroke-based clock glyph — toggling a **non-modal popover** anchored under the header. The popover: last ~20 pushes newest-first; each entry a real `<button>` with kind label, push title (when present), and time; activating an entry closes the popover **then** opens that push's view (popover and modal never coexist — overlay stack stays one level deep). Pill is `<button aria-expanded aria-haspopup>`; dismiss via entry activation, Esc, outside click, or re-toggling the pill. Not a modal, not a landmark, not a live region — a push arriving while it is open appears at the top unannounced. The pill **never carries an unread dot** (unread stays per-kind). Quiet/disabled until the first push of any kind, using the kind pills' disabled + pointer-tooltip + programmatic-description pattern with its own copy string. Focus: popover open → first (newest) entry; close → back to the History pill. Enter animation is an opacity-only fade over the existing `glide` token (no new motion token; the reduced-motion inventory still gains its documentation row). Styling tokens live in the design spec's `history-popover` block (surface-overlay, hairline border, elevation glow, 480 px max-height with internal scroll, tabular-numeric timestamps).
- **Connection pill:** stays quiet and static — the dot never animates and never carries state alone; the text names the state. Tooltip is tied to the pill via `aria-describedby`. The pill is the last Tab stop before the footer, carries the standard focus ring, and has a ≥ 24×24 px hit area — as does every history entry.
- **Nav pills** already show each kind's last-push time; history is the re-open path for *any* retained push, not just the latest per kind.

## Cross-Story Dependencies

- 17.2 was gated on the session-history home decision — now ruled and recorded in the UX spec (nav extension, popover); the story's first AC (decide and record before implementing) is satisfied.
- 17.2 builds on the push-retention store and view shell from Epic 13; 17.1 builds on the pill shell and reconnect behaviour from Epic 12 (FR-15's owner split: shell in 12, detail here).
- 17.3 profiles surfaces built across Epics 11–16 and should run after 17.1/17.2 land, since history and tooltip work touch the same render paths it measures.
