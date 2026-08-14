# Epic c7 Context: The Deck Updates Itself

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Close the live-update loop: Brad tells the agent to add a card and the glass changes by itself — the card appears in its type group, the mana curve grows, the colour spread shifts, and a screen reader hears about it exactly once — with no action in the browser. Every state change travels agent → MCP tool → SQLite → notification → browser refetch. This is the climax of the primary user journey and closes success criterion SC-2 (agent mutation visible on the glass within roughly a second).

## Stories

- Story 7.1: One shared notifier, with a bounded await and no detached tasks
- Story 7.2: Every deck-mutation tool emits after its transaction commits
- Story 7.3: The glass refetches on `deck_changed`, coalesced and latest-wins
- Story 7.4: Refetch never tears down what's on screen
- Story 7.5: The change is announced once, and motion is never the only signal
- Story 7.6: Deck deletion, and agent views during a refetch
- Story 7.7: The loop closes — UJ-1 end to end

## Requirements & Constraints

- Every deck-mutation tool (add, remove, update, create, import — and **deletion, which counts as a mutation**) emits a `deck_changed` event after persisting. The event carries the deck ID; the UI refetches when it matches the active deck and may refresh the deck list regardless. A refetch that 404s (deck deleted) clears to the no-active-deck state.
- A failed-and-rolled-back mutation emits nothing.
- Notification failure never damages the mutation: the tool's own result is completely unaffected, no error surfaces, and the resulting staleness window is **accepted** (no staleness warning in the UI) until out-of-band change detection ships in a later phase.
- Freshness model is "something changed, refetch" — no diffs, no patches. On WebSocket reconnect the client refetches the active deck, since events may have been missed.
- End-to-end acceptance: with the app open, an agent-side add commits and within ~1 second the card appears in its type group, its curve bar grows, the colour distribution shifts, and its quantity badge flashes — Brad performs no browser action, and nothing on the glass ever mutates the deck (the backend stays read-only).

## Technical Decisions

- **One shared notifier**, living in the companion **leaf** (imports only `pydantic`, `httpx`, `src.paths`, and leaf siblings). Exactly one — no mutation tool grows its own emit path. The MCP server may import the leaf but never `src.companion.app.*`; the existing CI import-boundary and read-only boundary tests must keep passing.
- "Fire-and-forget" means a **bounded-timeout `await` (~1 s), not a detached task** — `asyncio.create_task` is banned on the notification path (a task outliving its tool call can be torn down before it runs and the event is silently lost). A test asserts the ban. The timeout caps the mutation's latency cost.
- The notifier is called **after the transaction commits, never inside it**. All exceptions are caught and logged (`%`-style lazy logging args); nothing propagates to the caller.
- The event is a `deck_changed` envelope carrying the deck ID, under the established wire contract: `{kind, id, ts, payload}` with `kind` a closed enum; `id` is opaque identity, ordering comes from `ts`.
- A test **enumerates the full set of mutation tools** and asserts every one emits, so none is forgotten as tools are added.
- Refetch machinery: coalesce to **one in-flight request**; a newer event cancels and restarts it; **last response wins**; out-of-order responses discarded. On completion the grid, deck list, type-group counts, mana curve, and colour distribution all recompute from the new decklist.

## UX & Interaction Patterns

- **During a refetch the current deck stays on screen** with a subtle shimmer on the deck header — never a blank screen or a skeleton teardown of a populated view. Under `prefers-reduced-motion` the shimmer becomes static "Updating…" micro text. A blank screen is never shown after first paint.
- **Pin eviction is a membership transition, not a deck lookup** (ruling 2026-08-14, amending the refetch rule): a pinned inspection target is evicted — falling back to transient on the first card of the first type group — only when its card **was in the departing deck's list AND is absent from the new one**. A pin on a card that was never in the deck (e.g. a pinned suggestion) **survives every refetch** as a natural consequence; the rule reads only the old and new decklists at refetch completion, with no pin-time classification.
- DFC flip state is keyed by Scryfall printing UUID and **survives `deck_changed` re-renders** — a card showing its back face still shows it after refetch.
- **Announce once**: a polite live region announces exactly once per coalesced refetch, on completion ("Deck updated — 62 cards"); the coalescing machinery is the debounce. A changed quantity flashes the accent glow once, but the glow is garnish — the accessible signals are the group-header count and the announcement. Under reduced motion the glow is omitted and curve bars jump instantly. Motion is never the sole carrier of information.
- **Deck deletion**: refetch 404 → clear to the no-active-deck state panel, which lists remaining decks (non-clickable), in the calm specified voice. When the grid is gone, the skip link and grid Tab stops are withdrawn.
- **An open agent view is untouched** by a refetch completing behind it, and no announcement fires from behind a modal. If the active deck is deleted while a view is open, the view stays open and valid; on close the user lands on the no-active-deck panel.

## Cross-Story Dependencies

- 7.2 consumes 7.1's notifier; 7.4, 7.5, and 7.6 all build on 7.3's coalesced refetch; 7.7 is the end-to-end walk of the whole epic (full journey: deck loads within 1 s, suggestions render within 250 ms, a pin survives dismissing the view, the deck updates by itself).
- Epic-level: depends on the deck view (Epic 4), the realtime channel and envelope contract (Epic 5), and the agent views (Epic 6) — Story 7.6's "agent view survives a refetch behind it" needs those views to exist.
- The pinned-suggestion-survives AC in Story 7.4 is the regression test owed from the earlier suggestions work; the existing pin-survives-close test covers only the view-close half.
