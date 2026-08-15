# Epic c7 Context: The Deck Updates Itself

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Close the product's central promise: Brad tells the agent to add a card and the glass changes by
itself — the card appears in its type group, the mana curve grows, the colour spread shifts, the
quantity badge flashes, and a screen reader hears about it exactly once. He performs no action in
the browser. Every deck-mutation tool gains a single shared way to say "something changed" after it
commits; the UI turns that signal into a coalesced refetch that never tears down what's on screen.
This is the climax of the primary user journey and closes the success criterion that agent-driven
deck edits appear in the deck view without user action.

## Stories

- Story 7.1: One shared notifier, with a bounded await and no detached tasks
- Story 7.2: Every deck-mutation tool emits after its transaction commits
- Story 7.3: The glass refetches on `deck_changed`, coalesced and latest-wins
- Story 7.4: Refetch never tears down what's on screen
- Story 7.5: The change is announced once, and motion is never the only signal
- Story 7.6: Deck deletion, and agent views during a refetch
- Story 7.7: The loop closes — UJ-1 end to end

## Requirements & Constraints

- **Emit after persistence.** Deck-mutation tools (add, remove, update, create, import, delete)
  emit a `deck_changed` event carrying the deck id once the change is really saved. Deletion counts
  as a mutation. A mutation that fails and rolls back emits nothing.
- **Notification failure is invisible.** Any failure to notify — unreachable backend, auth
  rejection, timeout, error response — is caught and logged, never propagated. The tool's own result
  is completely unaffected, and no error surfaces in the UI. The resulting staleness window is
  accepted behaviour (out-of-band change detection is a later phase); the UI shows no staleness
  warning.
- **Refetch, never diff.** The freshness model is "something changed, refetch" — no diffs, no
  patches. The UI refetches the active deck when the event's deck id matches it, and again on
  WebSocket reconnect (events may have been missed while disconnected). The deck list may be
  refreshed regardless of which deck changed.
- **Coalescing and ordering.** One in-flight deck fetch at a time; a newer event cancels and
  restarts the request; last response wins; out-of-order responses are discarded.
- **A refetch that 404s** (the deck was deleted) clears the app to the no-active-deck state.
- **End-to-end budget.** From mutation commit to visible update, roughly one second, with the
  notifier's own await bounded so the mutation's latency cost is capped.
- **Enumerated coverage.** The full set of mutation tools is enumerated in test so that none is
  forgotten as new tools are added.

## Technical Decisions

- **One notifier, in the dependency-free leaf.** It lives in the companion leaf and may import only
  `pydantic`, `httpx`, `src.paths`, and its own leaf siblings — never `src.companion.app.*`. This
  keeps the existing CI import-boundary test passing when mutation tools start calling it. There is
  exactly one; no mutation tool grows its own emit path.
- **"Fire-and-forget" means a bounded-timeout `await` (~1 s), not a detached task.** `create_task`
  and any other detached task is banned on the notification path, and a test asserts the ban. A task
  that outlives its tool call can be torn down before it runs — the event never leaves the process
  and the deck view silently goes stale. This rule is the whole point of the epic.
- **Called after commit, never inside the transaction.**
- **Event shape is the existing envelope.** `deck_changed` uses the established
  `{kind, id, ts, payload}` contract with its `kind` in the closed enum; no new wire shape is
  introduced. The payload carries the deck id.
- **Exceptions logged with `%`-style lazy args**, per project logging convention.
- **Refetch reads `GET /api/deck/{id}`**; all derived state (grid, deck list, type-group counts,
  mana curve, colour distribution) recomputes from the returned decklist rather than being patched.
- **Error tokens stay closed.** Any new UI state needs a token in the existing closed `reason` set
  first; this epic should need none beyond `deck_not_found`.

## UX & Interaction Patterns

- **Never tear down a populated view.** During a refetch the current deck stays on screen with a
  subtle shimmer on the deck header. No blank screen and no skeleton teardown of populated content,
  at any point after first paint.
- **Pin eviction is a membership transition, not a deck lookup** (ruling of 2026-08-14, amending the
  original "no longer exists in the deck" wording). A pinned inspection target is evicted — falling
  back to transient inspection on the first card of the first type group — **only when its card was
  in the departing deck's list and is absent from the new one**. A pin on a card that was never in
  the deck (a pinned suggestion from an agent view) therefore survives every refetch as a natural
  consequence, with no pin-time classification and no special-casing: the rule reads only the old
  and new decklists at refetch completion. A pinned target that still exists stays pinned.
- **Flip state survives.** A double-faced card showing its back face is still showing its back face
  after the grid re-renders; flip state is keyed by printing UUID.
- **Announced exactly once.** A polite live region announces "Deck updated — {N} cards" once per
  coalesced refetch, on completion — the refetch-coalescing machinery *is* the debounce, so a burst
  of events yields one announcement. Nothing announces from behind an open agent view.
- **Motion is never the sole signal.** A changed quantity flashes the accent glow once, but that is
  garnish; the accessible carriers are the updated group-header count and the live-region
  announcement.
- **Reduced motion has named fallbacks:** header shimmer → static "Updating…" micro text in
  secondary colour; accent glow → omitted entirely (count text plus announcement carry it); mana
  curve bar heights → instant jump. Nothing pulses or loops under any setting.
- **Agent views are untouched by a refetch behind them,** and stay open and valid even if the active
  deck is deleted; on close the user lands on the no-active-deck state panel.
- **No-active-deck state** uses the shared state-panel shell with the specified verbatim copy, and
  lists the remaining decks non-clickably. When the grid is gone, the skip link and the grid's Tab
  stops are withdrawn.
- **Nothing on the glass mutates the deck.** Every state change must travel agent → MCP tool →
  SQLite → notification → browser refetch.

## Cross-Story Dependencies

- 7.1 is the foundation: 7.2 calls its notifier, and 7.3–7.7 all depend on the event actually
  arriving.
- 7.3 (coalescing and latest-wins) is the machinery that 7.4's no-teardown behaviour and 7.5's
  exactly-once announcement are both defined against.
- 7.6 depends on 7.2's deletion emit and on the agent-view surface built in the preceding epic.
- 7.7 is the end-to-end acceptance walk over everything above plus the deck view, event channel, and
  agent-push work from earlier epics.
- Epic-level: depends on the deck-view epic (grid, panels, inspection, flip state), the event-channel
  epic (envelope, WebSocket, reconnect), and the agent-push epic (agent views must exist for 7.6).
