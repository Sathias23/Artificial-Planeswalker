# Epic c7 Context: The Deck Updates Itself

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Brad tells the agent to add a card and the glass changes by itself: the card appears in its type group, the mana curve grows, the colour spread shifts, and a screen reader hears about it exactly once — he never touches the browser. This is the climax of the primary user journey (agent drives, app shows) and closes the success criterion "agent-driven deck edits appear in the deck view without user action." The mechanism is deliberately simple: every deck-mutation tool emits a `deck_changed` event through one shared notifier after its transaction commits, and the UI's freshness model is "something changed, refetch" — no diffs, no patches.

## Stories

- Story c7-1: One shared notifier, with a bounded await and no detached tasks
- Story c7-2: Every deck-mutation tool emits after its transaction commits
- Story c7-3: The glass refetches on `deck_changed`, coalesced and latest-wins
- Story c7-4: Refetch never tears down what's on screen
- Story c7-5: The change is announced once, and motion is never the only signal
- Story c7-6: Deck deletion, and agent views during a refetch
- Story c7-7: The loop closes — UJ-1 end to end

## Requirements & Constraints

- Existing deck-mutation tools (add, remove, update, create, import — and **deletion counts**) emit `deck_changed` after persisting. The event carries the deck ID; the UI refetches when it matches the active deck and may refresh the deck list regardless. A refetch that 404s (deck deleted) clears to the no-active-deck state.
- Event delivery is fire-and-forget; a notification failure must never affect the mutation's own result, and no error surfaces in the UI. The resulting staleness window (until the out-of-band poller ships in a later phase) is **accepted behaviour** — no staleness warning is shown.
- Resilience model: the UI reconnects its WebSocket with backoff and refetches the active deck on reconnect, since events may have been missed while disconnected.
- End-to-end target: with the app open and an active deck, an agent mutation is visible on the glass within roughly a second of committing, with zero browser interaction.

## Technical Decisions

- **One shared notifier lives in the companion leaf** (importing only `pydantic`, `httpx`, `src.paths`, and leaf siblings). No mutation tool grows its own emit path. The MCP server may import the leaf but never `src.companion.app.*` — the CI import-boundary tests must still pass after every tool is wired up.
- **"Fire-and-forget" means a bounded-timeout `await` of roughly 1 second, never a detached task.** `asyncio.create_task` is banned on the notification path (a task outliving its tool call can be torn down before it runs, silently losing the event), and a test asserts the ban. The timeout caps the latency cost a notification can add to a mutation.
- The notifier catches and logs **every** exception (`%`-style lazy logging args, per project convention); nothing propagates to the caller.
- Emission happens **after the transaction commits, never inside it**; a rolled-back mutation emits nothing — the view can never show something the database doesn't have.
- The event is a `deck_changed` envelope carrying the deck ID, under the closed envelope contract (`{kind, id, ts, payload}` discriminated union) already established by the channel epic. Payloads reference by ID only; the UI re-hydrates via its existing REST endpoints and single card-hydration cache.
- Refetch concurrency: **one in-flight `GET /api/deck/{id}` at a time; a newer event cancels and restarts it; last response wins; out-of-order responses are discarded.** The coalescing machinery doubles as the announcement debounce.
- An enumeration test covers the full set of mutation tools so a future tool can't be forgotten.

## UX & Interaction Patterns

- **During a refetch the current deck stays on screen** with a subtle shimmer on the deck header — never a blank screen, never a skeleton teardown of a populated view. Blank screens are never shown after first paint.
- On refetch completion, all derived views recompute from the new decklist: grid, type-grouped deck list, group-header counts, mana curve, colour distribution.
- **Pin and flip state survive**: a pinned inspection target that still exists stays pinned; one that no longer exists falls back to transient inspection of the first card of the first type group. DFC flip state is keyed by Scryfall printing UUID, so a card showing its back face still shows it after re-render.
- **One announcement per coalesced refetch**, on completion, via a polite live region: "Deck updated — 62 cards." A burst of events yields exactly one announcement.
- **Motion is never the sole signal.** The changed-quantity badge glow flashes once and is garnish; the accessible signals are the updated group-header count and the live-region announcement. Under `prefers-reduced-motion`: glow omitted entirely, shimmer becomes static "Updating…" micro text in `text-secondary`, curve bars jump instantly.
- **Deck deletion**: the triggered refetch 404s and the app clears to the no-active-deck state panel, listing remaining decks (non-clickable — the agent drives). The skip link and grid Tab stops are withdrawn while the grid is gone.
- **An open agent view is untouched by a refetch** completing behind it, and **no announcement fires from behind a modal**. If the active deck is deleted while a view is open, the view stays open and valid (agent content is about cards, not deck presence); closing it lands on the no-active-deck panel.

## Cross-Story Dependencies

- Depends on Epics c4, c5, c6: the deck view and derived panels (c4) are what refetches repaint; the WebSocket channel and envelope contract (c5) carry `deck_changed`; the agent views (c6) must exist for c7-6's view-survives-refetch behaviour.
- Within the epic: c7-1 (notifier) precedes c7-2 (wiring every tool); c7-3 (refetch/coalescing) underpins c7-4 (non-teardown rendering) and c7-5 (its coalescing is the announcement debounce); c7-7 is the end-to-end capstone walking the full journey — deck loads within 1 s, suggestions bloom within 250 ms, a pin survives dismissing the view, the deck updates by itself, and an audit confirms nothing in the browser ever mutated the deck (every change travels agent → MCP tool → SQLite → notification → browser refetch).
