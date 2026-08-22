# Epic 17 Context: Session History, Status Detail & Performance Polish

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Brad can revisit what the agent showed him earlier in the session, see at a glance which backend port and instance a tab is actually talking to, and the companion's 250 ms push and 1 s cold-open budgets become measured numbers instead of asserted ones. This is the Phase-2 closing epic for the companion: it covers connection-status detail, capped in-browser session history, and NFR-05 hardening (profiling beyond the Phase-1 baseline), governed by the envelope, payload, and image-proxy decisions already in force. The session-history home was the UX spine's last open residual; that decision has now been made and recorded (2026-08-22), so no story in this epic is blocked.

## Stories

- Story 17.1: Connection pill status detail
- Story 17.2: Session history
- Story 17.3: Measure the latency budgets and close the gaps

## Requirements & Constraints

- **Status detail:** the connection pill must reveal the backend's port and instance id (from `GET /health`) on hover **or keyboard focus** — hover is never the only path. Tooltip semantics via `aria-describedby`. The pill stays quiet and static: the dot never animates and never carries state without text. After a backend restart, a reconnect must surface the *new* instance id rather than silently pretending continuity.
- **Session history:** a lightweight capped list (roughly the last 20 pushes), each entry labelled by kind and time. Entries re-hydrate against current card data when reopened; ids that no longer resolve degrade to unknown-card placeholders per entry — a revisit never fails wholesale and never re-requests anything from the agent. History is **in-browser only, per-tab, and clears on refresh** — the backend retains no events, keeping the event model stateless and fire-and-forget. Multiple tabs diverge; that is accepted, not synchronised. At the cap, the oldest entry drops silently.
- **Performance budgets:** event-to-painted-layout under **250 ms** (clock stops at first paint of laid-out content; entry animation excluded) and cold open of a 100-card Commander deck with warm image cache under **1 second**. Any measured gap is either closed or recorded as an accepted deviation with its reason. Each image/size/face combination is fetched from the CDN at most once per cache lifetime; companion tool results must stay token-cheap with no payload ever echoed into chat. Profiling results are recorded with the hardware and conditions they were measured under, and the unbounded image cache's real footprint after sustained use is recorded so a future eviction policy can be sized against evidence.

## Technical Decisions

- **One WebSocket envelope** `{kind, id, ts, payload}` with a closed six-value `kind` enum (four push kinds + `deck_changed` / `active_deck_changed`). `id` is opaque — identity and dedupe only. **History orders by `ts`, never by `id`.**
- **Push path never reads the database**; payloads reference cards by Scryfall printing UUID only and the UI hydrates everything else through the existing card/image endpoints. Unknown ids degrade per entry.
- **Image proxy** (`GET /api/card-image/...`) paces all CDN fetches behind a single backend-global semaphore with request spacing, fully async — pacing must never block the event loop, and a concurrent push must still meet its 250 ms budget while a cold-cache deck's images are queued. Cache is content-addressed, atomic (temp + rename), unbounded in MVP; failures are negative-cached with backoff.
- **History storage** extends the retention store the kind pills' re-open path already uses — widened from "latest push per kind" to "last 20 pushes overall". Same store, larger window; capacity 20, per-tab, in-memory.

## UX & Interaction Patterns

The working design authorities are `EXPERIENCE.md` and `DESIGN.md` in the current UX spine (`ux-Artificial-Planeswalker-2026-07-22/`). The FR-18 home ruling (2026-08-22) is recorded there; the former blocker on 17.2 is **RESOLVED — session history's home is the nav**.

- **History pill:** a fifth "History" nav pill after the four kind pills, visually `components.nav-pill` verbatim plus a stroke-based clock glyph (plain UI glyph, never set-symbol-like). It is a `<button aria-expanded aria-haspopup>` toggle. Quiet/disabled until the first push of **any** kind this session, using the kind pills' exact disabled + pointer-tooltip + programmatic-description pattern with its own copy string. **It never carries an unread dot** — unread stays per-kind on the kind pills.
- **Popover** (`{components.history-popover}` in DESIGN.md): **non-modal**, anchored under the header, listing the last ~20 pushes newest-first ordered by envelope `ts`. Each entry is a real `<button>`: kind label + push title (when present) + time (tabular numerals, tertiary foreground). Max-height 480px; the list scrolls inside it. No listbox roving-focus widgetry, no focus trap, no scrim; not a landmark, not a live region — open/close announce nothing, and a push arriving while it is open simply appears at the top, unannounced (the push still auto-opens its view; the popover closes first).
- **Popover and agent-view modal never coexist** — the overlay stack stays one level deep. Activating an entry closes the popover, then opens that push's view.
- **Motion:** opacity-only fade over `{components.motion.glide}` — no rise, no new motion-inventory entry (opacity-only self-neutralises under reduced motion).
- **Focus/dismissal contract:** popover open → focus to the first (newest) entry; popover close → focus returns to the History pill. Dismiss via entry activation, Esc, outside click, or toggling the pill again. Esc closes topmost-first: open agent view, then popover, then active pin. Entries ≥ 24×24px hit areas; standard focus ring. While open, entries are ordinary document-order Tab stops, withdrawn on dismiss.
- Sub-treatments the spine marks `[ASSUMPTION]` (e.g. exact Tab position, dismissal set, no-unread-dot) are drafted pending confirmation; the home choice itself is ruled. The decision aid is `.working/session-history-home-options.html` in the UX spine directory.
- **Connection pill (17.1):** last Tab stop before the footer, standard focus ring, ≥ 24×24px hit area; text always names the state.

## Cross-Story Dependencies

- 17.1 shipped first (merged to the epic umbrella via PR #96); 17.2 and 17.3 are independent of it.
- 17.2's history builds on the push-retention store the existing agent-view pills use — widen it, don't fork it.
- 17.3 profiles the paths 17.2 touches (push → paint); measure after 17.2 lands so history overhead is inside the measured number.
- Epic 17 closes the 0.5.0 companion scope; the release is cut after it, so accepted deviations recorded here are release-notes material.
