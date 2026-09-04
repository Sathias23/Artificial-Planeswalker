/**
 * The browser's connect/reconnect loop: one socket per tab, a fresh ticket per attempt, and a
 * backoff that never gives up (FR-11, NFR-04, AD-5, AD-6).
 *
 * The backend half of this channel — mint, upgrade, broadcast, ingest — is complete, and
 * `test_ws.py:130` names the shape this file performs: *"mint, upgrade, mint, upgrade"*.
 *
 * Framework-free on purpose, in `poller.ts`'s exact register: no React, no store import, no
 * module-level state, both external effects INJECTED. So every timing assertion in
 * `socket.test.ts` runs on fake timers against a plain function, the React seam
 * (`connection.ts`) has nothing timing-shaped left in it to get wrong, and the fake socket is a
 * scriptable object rather than a network.
 *
 * ================= THE ORDERING IS `delay → mint → open`, AND IT IS THE DESIGN ==========
 *
 * The ticket's TTL is **30 s** (`TICKET_TTL_SECONDS`, `state.py:163`). This backoff's ceiling is
 * **30 s**. At the ceiling those two windows are exactly equal, so an implementation that minted
 * BEFORE waiting would hand every upgrade a ticket that had spent its entire life in a
 * `setTimeout` — a loop that reconnects perfectly at 2 s and can never reconnect at all at 30 s,
 * which is precisely when it matters. Minting inside the attempt, after the delay, makes the
 * ticket's age the round-trip time and nothing else. {@link createAgentSocket} is written so that
 * there is no other order available: the timer's callback IS the attempt, and the attempt begins
 * with the mint.
 *
 * ================= EVERY ATTEMPT MINTS. THERE IS NO TICKET VARIABLE ====================
 *
 * AD-5, and the wire's own docstring at `types.d.ts:747-761`: *"consuming it destroys it whether
 * or not the handshake then succeeds, so a retry needs a fresh ticket — including after an
 * upgrade that failed for an unrelated reason."* `state.py:318` pops the ticket on **every**
 * consume attempt, so a client holding one for a second try is holding a string the backend
 * has already forgotten. There is deliberately no field on this closure that could cache one:
 * the ticket exists as a local inside a single {@link attempt} call and is unreachable from the
 * next.
 *
 * That also makes the 256-ticket eviction cap (`state.py:183-190`) a non-event by construction
 * rather than by handling: an eviction storm costs this client one failed upgrade and one
 * re-mint, which is the same cost as any other failure, and the code path is the same one.
 *
 * ================= THE CLIENT CANNOT DIAGNOSE A REFUSAL, AND DOES NOT TRY ==============
 *
 * `ws.py:29-40` is explicit: **every** refusal is close code `1008` pre-accept, rendered to the
 * browser as HTTP `403`, with no body and no reason token — a missing ticket, an expired one, a
 * replayed one and a bad `Origin` are deliberately indistinguishable on the wire. A browser
 * cannot even read the status code of a failed handshake. So there is exactly one failure
 * handler here and it does exactly one thing: back off, re-mint, retry. Any branch on *why* would
 * be a branch on information this loop provably does not have.
 *
 * ================= "EXHAUSTED" IS AN ANNOUNCEMENT, NOT A STOP ==========================
 *
 * The epic says the Disconnected panel appears when "the client gives up", and
 * `RETRIES_QUIETLY.disconnected = true` says the state keeps retrying. Both are honoured:
 * **the threshold below is when the panel is ANNOUNCED, not when the loop stops.** The backoff
 * continues at the 30 s ceiling for as long as the tab is open, and a reconnect that later
 * succeeds clears the panel with no reload. A true stop would rebuild the needs-a-manual-refresh
 * defect this loop exists to kill.
 *
 * The map is READ rather than paraphrased, exactly as `poller.ts` reads it: see
 * {@link keepsRetrying} below, and the flip-the-entry test in `socket.test.ts` that proves the
 * behaviour follows it.
 *
 * ================= THE NUMBERS, WITH THEIR ARITHMETIC ==================================
 *
 * `poller.ts`'s shape throughout, and deliberately the same numbers where the question is the
 * same one. Each constant carries the sum that produced it.
 */

import { RETRIES_QUIETLY, type ClientOnlyState } from '../components/StatePanel/states'
import type { StateKey } from '../components/StatePanel/copy'
import {
  openAgentSocket,
  readSessionTicket,
  type AgentSocketHandle,
  type AgentSocketHandlers,
  type SessionOutcome,
} from '../api/client'
import type {
  AgentEvent,
  GroupsEvent,
  SuggestionsEvent,
  SwapsEvent,
  SystemEvent,
  TierListEvent,
} from '../api/schema'

/**
 * The first retry lands this long after a drop.
 *
 * 2 s, matching `POLL_BASE_MS` because the question is the same question: how long after a
 * backend goes away should the client first ask whether it came back. The commonest cause of a
 * drop is a deliberate restart during development, which takes a second or two, so a first retry
 * at 2 s makes the ordinary case invisible — the tab reconnects before a human has finished
 * looking at the terminal.
 */
export const SOCKET_BASE_MS = 2_000

/**
 * Each retry waits this much longer than the last.
 *
 * 2, so the schedule from the base is 2 s, 4 s, 8 s, 16 s, 30 s (the ceiling clamps 32), 30 s… —
 * five attempts in the first thirty seconds, then two per minute forever. Five quick attempts is
 * what covers a restart; two per minute is what makes a backend that is off for an hour cost 120
 * failed handshakes instead of 1,800.
 */
export const SOCKET_MULTIPLIER = 2

/**
 * …but never longer than this.
 *
 * 30 s, and here the ceiling is doing a second job `POLL_CEILING_MS` does not have to do. The
 * first is the same one: without a clamp the delay doubles forever, so a companion restarted
 * after ten minutes of downtime would be picked up minutes later — a backoff that has quietly
 * become a countdown to never. The second is the TTL interlock in this file's header: 30 s is
 * also the ticket's lifetime, so the ceiling is the exact point at which the `delay → mint →
 * open` ordering stops being a nicety and starts being the only ordering that works. Raising
 * this number without raising `TICKET_TTL_SECONDS` would be safe; lowering that one without
 * lowering this is what would break.
 */
export const SOCKET_CEILING_MS = 30_000

/**
 * How long the socket must have been down CONTINUOUSLY before the Disconnected panel is shown.
 *
 * 60 s, the two-gate escalation shape `poller.ts` already uses. At the schedule above that is
 * at least six consecutive failed
 * attempts with the last two a full ceiling apart (t = 0, 2, 6, 14, 30, 60 s), so a backend
 * restart — which is over in a second or two — never reaches it, and the panel keeps meaning
 * what its copy says: *"Lost the companion backend."*
 *
 * The alternative, announcing on the first drop, was declined for a measurable reason rather than
 * a taste: a `uvicorn --reload` restart drops every open socket, so a developer editing a Python
 * file would watch a whole-screen panel flash on and off on every save.
 */
export const DISCONNECTED_AFTER_MS = 60_000

/**
 * …and this many CONSECUTIVE failed attempts must actually have been OBSERVED.
 *
 * The elapsed clock below reads `Date.now()`, which is wall time, and wall time keeps moving when
 * timers do not — `STALLED_MIN_REFUSALS` carries the full argument and every word of it applies
 * here: a suspended laptop and a throttled background tab (browsers clamp `setTimeout` to once a
 * minute or slower there) both advance the clock without running the schedule. Without a floor,
 * one failed attempt on each side of a nap satisfies "60 s of continuous failure", and the panel
 * would announce a lost backend to somebody who merely closed their lid.
 *
 * 4: on the live schedule the floor never binds — 60 s of elapsed failure already means six
 * attempts — so it speaks only when the schedule was frozen, where it demands four real failures
 * before the clock's opinion counts. A resumed tab also fires a burst of queued timers; the
 * generation counter is what keeps THAT safe, and the two mechanisms are separate on purpose.
 */
export const DISCONNECTED_MIN_FAILURES = 4

/**
 * What the app knows about its socket. Three values, and they are genuinely three:
 *
 * - `live` — a socket is open. Agent pushes arrive; the deck on the glass is fresh.
 * - `reconnecting` — no socket, and the loop is trying. **The cold-open value too**, because
 *   before the first upgrade lands "no socket, trying" is exactly true and nothing else is. The
 *   glass shows no panel for this state: UX-DR35 says a loaded deck stays rendered through a
 *   reconnection rather than being torn down, and a fresh install has no socket for its first few
 *   milliseconds either.
 * - `down` — the two gates above have both been satisfied. **The loop is still retrying**; this
 *   value means *say so*, not *stop*. `surfaceOf` reads it and puts the Disconnected panel on the
 *   glass; the connection pill reads the same field for the same reason, and renders its
 *   negative dot beside that panel rather than instead of it.
 *
 * A union rather than a boolean pair (`connected` + `exhausted`) for `DeckState`'s reason: two
 * booleans are two invariants that can disagree, and `{connected: true, exhausted: true}` has no
 * meaning at all.
 */
export type ConnectionStatus = 'live' | 'reconnecting' | 'down'

// There is deliberately no kind-only `SystemEventKind` alias exported here: `schema.ts`'s
// `SystemEvent` owns the pair (both spellings of the system/view partition live in that file, both
// derived), and an exported alias with no consumer is exactly the drift surface the
// alias-lands-with-its-consumer rule exists to prevent. A caller wanting the kinds writes
// `SystemEvent['kind']`.

export interface AgentSocketOptions {
  /**
   * Emitted once per CHANGE of {@link ConnectionStatus}, never once per attempt. `poller.ts`'s
   * rule and for its measured reason: the system store is subscribed selector-less in `App`, so
   * every write re-renders the whole tree — and a loop against an absent backend would otherwise
   * re-render the app twice a minute forever to say the same thing.
   */
  readonly onStatus: (status: ConnectionStatus) => void
  /**
   * A socket opened that follows at least one failure — i.e. a RE-connect, not the first connect
   * of the tab. The caller refetches (`connection.ts`).
   *
   * The distinction is the whole reason this is a separate callback from `onStatus('live')`: the
   * boot has already run by the time the first socket opens, so re-driving on it would double
   * every cold open's request count for nothing. A first attempt that FAILS and then succeeds
   * does fire this — correctly, since a boot that raced a dead backend has a stale answer to
   * replace.
   */
  readonly onReconnected: () => void
  /**
   * A `deck_changed` or `active_deck_changed` frame arrived. The two are reported separately —
   * as one union whose discriminant survives — because `contracts.py:902-905` is emphatic that
   * conflating them is the interesting bug: *"a client that conflates them refetches the deck it
   * is leaving instead of the one it is switching to"*. See `connection.ts` for what each one
   * does.
   *
   * **It carries the WHOLE EVENT**, not the bare kind: `deck_changed`'s `deck_id` is read (by
   * `connection.ts`, never here) to choose between a single-deck refetch and a full
   * re-drive, while `active_deck_changed`'s payload stays deliberately unread, because the boot
   * asks `GET /api/active-deck` first and so can never fetch the deck being left. Carrying the
   * envelope rather than a second `deckId` parameter keeps this module payload-blind: it hands
   * over what arrived and holds no opinion about which fields matter — the same argument
   * {@link AgentSocketOptions.onSuggestions} makes one entry down.
   */
  readonly onSystemEvent: (event: SystemEvent) => void
  /**
   * A `suggestions` push arrived. The caller opens its view
   * (`connection.ts` → `openSuggestionsPush`).
   *
   * **It carries the WHOLE EVENT, as {@link AgentSocketOptions.onSystemEvent} also does —
   * for a different reason worth keeping apart.** The system kinds carry their envelope because
   * the refetch branch reads ONE routing field (`deck_changed`'s `deck_id`) out of it; this
   * one carries the envelope because the payload IS the content: the title, the items and the
   * `id` that makes a repeat push identifiable are all in it, and an `id`-only callback would
   * force the caller to hold a second copy of the frame to look them up in.
   *
   * Every agent-view kind has a callback of its own, and the shape is one callback per
   * renderable kind rather than `onViewEvent(kind, payload)`, deliberately: a kind must not
   * become *acceptable* before something can display it, because a push the UI silently cannot
   * draw breaks never-silently-swallowed from the other side. So each callback is added
   * alongside the view that can receive what it carries, and no kind is dropped anywhere.
   */
  readonly onSuggestions: (event: SuggestionsEvent) => void
  /**
   * A `swaps` push arrived. The caller opens its view
   * (`connection.ts` → `openSwapsPush`).
   *
   * It carries the WHOLE EVENT for {@link AgentSocketOptions.onSuggestions}'s reason verbatim:
   * the payload IS the content, and an `id`-only callback would force the caller to hold a
   * second copy of the frame to look the title, items and replace key up in.
   */
  readonly onSwaps: (event: SwapsEvent) => void
  /**
   * A `tier_list` push arrived. The caller opens its view
   * (`connection.ts` → `openTierListPush`).
   *
   * It carries the WHOLE EVENT for {@link AgentSocketOptions.onSuggestions}'s reason verbatim:
   * the payload IS the content, and an `id`-only callback would force the caller to hold a
   * second copy of the frame to look the title, items and replace key up in.
   */
  readonly onTierList: (event: TierListEvent) => void
  /**
   * A `groups` push arrived. The caller opens its view
   * (`connection.ts` → `openGroupsPush`).
   *
   * It carries the WHOLE EVENT for {@link AgentSocketOptions.onSuggestions}'s reason verbatim:
   * the payload IS the content, and an `id`-only callback would force the caller to hold a
   * second copy of the frame to look the title, items and replace key up in. With it, every
   * kind in the closed six-member event enum is delivered somewhere, and the dispatch switch
   * below contains no drop arm at all.
   */
  readonly onGroups: (event: GroupsEvent) => void
  /** Injected so tests need no `fetch` stub; production passes nothing. */
  readonly mint?: () => Promise<SessionOutcome>
  /**
   * Injected so tests need no network AND so this module never names the socket constructor:
   * `posture.test.ts:322-342` asserts the network-door list is
   * exactly `['src/api/client.ts']` and its family regex includes the constructor's name, so the
   * identifier appearing anywhere in this file would make it the app's second door. The door
   * stays one and hands out this factory; see `AgentSocketHandlers` in `client.ts`.
   * **Production passes nothing.**
   */
  readonly open?: (ticket: string, handlers: AgentSocketHandlers) => AgentSocketHandle
  /**
   * The status already believed when the loop starts, so the emit-on-change rule has something
   * true to compare against. `createPoller`'s `initialPanel` exactly.
   */
  readonly initialStatus?: ConnectionStatus
}

export interface AgentSocket {
  /**
   * Connects IMMEDIATELY — no initial wait — then on the backoff. Idempotent while running. A
   * restart after `stop()` is a NEW connection: the backoff, the failure count and the elapsed
   * clock all reset, because wall time that passed while nobody was connecting is not evidence
   * about the backend.
   */
  start: () => void
  /**
   * Cancels the pending timer, abandons any socket and drops any mint still in flight.
   * Idempotent.
   */
  stop: () => void
}

/**
 * The panel whose retry contract governs this loop.
 *
 * Typed `ClientOnlyState` rather than `StateKey`:
 * this is the second of the two places in the app that names a panel produced by a client-side
 * condition, and the type is what stops either of them drifting onto a wire-sourced one. See
 * `CLIENT_ONLY_STATES` in `states.ts` for why the consumption is type-level rather than runtime.
 *
 * This constant is the ONLY point at which the loop and the panel vocabulary meet, and they meet
 * by NAME — nothing here derives a panel from a token, a status or a response.
 */
const DISCONNECTED_PANEL: ClientOnlyState = 'disconnected'

/**
 * The retry contract, widened for lookup — an assignment rather than a cast, as `deck.ts` and
 * `cards.ts` both do.
 *
 * `satisfies` preserves the literal types on `RETRIES_QUIETLY`, so a direct
 * `RETRIES_QUIETLY.disconnected` is typed `true` and the compiler would fold the guard below into
 * a constant. Widening it here is what makes the read a real runtime read — and what lets
 * `socket.test.ts` flip the entry and watch the behaviour follow, which is the assertion that
 * separates *consults the contract* from *happens to agree with it today*.
 */
const retriesQuietly: Record<StateKey, boolean> = RETRIES_QUIETLY

/**
 * Build the loop. Nothing happens until `start()`.
 *
 * ==== WHY A GENERATION COUNTER, AND WHY IT IS BUMPED IN MORE PLACES THAN THE POLLER'S ====
 *
 * `poller.ts:161-168` carries the base argument in full — *"a plain `live` boolean cannot tell
 * 'stopped' from 'stopped and restarted'"* — and `deck.ts:286-302` extends it to a sequence with
 * two awaits. This loop is the third and hardest case, because its continuations are not all
 * awaits: an attempt reaches the network twice (the mint, then the upgrade) and then hands FOUR
 * more entry points to the browser (`open`, `message`, `close`, `error`), any of which can fire
 * at any later time, including after the loop has moved on to a different attempt entirely.
 *
 * So every one of those entry points is guarded by the generation it was created under, and the
 * counter is bumped by `start()`, by `stop()` **and by every failure** — the last of which is the
 * one the poller does not need. A browser that dispatches `error` and then `close` for the same
 * dead socket calls the failure path twice; without the bump inside {@link fail} that is two
 * scheduled timers, i.e. a second timer chain running at double rate that the next `stop()`
 * (which clears one `timer` slot) could never fully cancel. `client.ts`'s `openAgentSocket`
 * deliberately does NOT suppress the duplicate — one mechanism answers both it and the stale-
 * callback case, rather than two that must agree.
 *
 * Args:
 *   options: See {@link AgentSocketOptions}.
 *
 * Returns:
 *   An {@link AgentSocket}. Every instance owns its own backoff, failure count and elapsed clock,
 *   so a second one (React StrictMode remounts the effect in development) cannot inherit the
 *   first's countdown or silence it.
 */
export const createAgentSocket = ({
  onStatus,
  onReconnected,
  onSystemEvent,
  onSuggestions,
  onSwaps,
  onTierList,
  onGroups,
  mint = readSessionTicket,
  open = openAgentSocket,
  initialStatus = 'reconnecting',
}: AgentSocketOptions): AgentSocket => {
  let live = false
  let generation = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  let delay = SOCKET_BASE_MS
  /** The open socket, or `null`. Held ONLY so `stop()` and a superseded attempt can abandon it. */
  let socket: AgentSocketHandle | null = null
  /** Consecutive failed attempts since the last successful open. The observation gate. */
  let failures = 0
  /** When the current run of failures began, or `null` if there is no run. The elapsed gate. */
  let failingSince: number | null = null
  /** The last status handed to `onStatus`, so an identical one is not re-emitted. */
  let emitted: ConnectionStatus = initialStatus

  const emit = (status: ConnectionStatus): void => {
    if (status === emitted) return
    emitted = status
    onStatus(status)
  }

  /**
   * Whether the loop keeps scheduling once the panel is up — READ from the contract, not assumed.
   *
   * The shipped value is `true`, so this returns `true` and the loop is endless. What the read
   * buys is that this is not a second copy of the contract: flipping
   * `RETRIES_QUIETLY.disconnected` to `false` makes this loop stop retrying behind the panel,
   * which is exactly what the map would then be saying. `copy-tails.test.ts`'s fourth tail is
   * checkable because of this line.
   */
  const keepsRetrying = (status: ConnectionStatus): boolean =>
    status !== 'down' || retriesQuietly[DISCONNECTED_PANEL]

  /** BOTH gates, because they measure different things. See the two constants. */
  const statusAfterFailure = (): ConnectionStatus =>
    failingSince !== null &&
    failures >= DISCONNECTED_MIN_FAILURES &&
    Date.now() - failingSince >= DISCONNECTED_AFTER_MS
      ? 'down'
      : 'reconnecting'

  const abandon = (): void => {
    socket?.close()
    socket = null
  }

  const schedule = (gen: number): void => {
    timer = setTimeout(() => void attempt(gen), delay)
    // Grown AFTER the wait is committed, so the first retry lands at exactly the base delay —
    // `poller.ts:200-204`'s line, and the same off-by-one it exists to prevent.
    delay = Math.min(delay * SOCKET_MULTIPLIER, SOCKET_CEILING_MS)
  }

  /**
   * One attempt failed, for any of the four reasons the wire refuses to distinguish.
   *
   * The generation bump is the FIRST thing it does, so every remaining callback of the attempt
   * that just died — including the `close` that a browser dispatches after an `error` — reads as
   * stale at its own guard and does nothing. See the constructor's docstring.
   */
  const fail = (gen: number): void => {
    if (gen !== generation || !live) return
    generation += 1
    const next = generation
    abandon()

    failures += 1
    failingSince ??= Date.now()
    const status = statusAfterFailure()
    // In `finally`, so a throwing `onStatus` consumer (e.g. a render bug — the system store is
    // subscribed selector-less, so every write re-renders `App`) cannot silently stop the loop:
    // "never gives up" has to survive its own status callback misbehaving.
    try {
      emit(status)
    } finally {
      if (keepsRetrying(status)) schedule(next)
    }
  }

  const succeed = (gen: number): void => {
    if (gen !== generation || !live) return
    // Read BEFORE the reset, because the reset is what destroys the evidence: "did this open
    // follow a failure" is the whole of the re-drive's trigger.
    const reconnected = failures > 0
    failures = 0
    failingSince = null
    delay = SOCKET_BASE_MS
    emit('live')
    if (reconnected) onReconnected()
  }

  /**
   * One frame arrived. **The one total switch over the six-kind closed enum** (AD-6).
   *
   * `null` is a frame this build could not read — non-JSON, an unknown kind, the wrong shape —
   * and it is IGNORED: no close, no throw, no state change. The socket stays open because
   * a malformed frame says nothing about the connection, and `ws.py:284` says the same thing from
   * the other side about client chatter.
   */
  const receive = (gen: number, event: AgentEvent | null): void => {
    if (gen !== generation || !live) return
    if (event === null) return

    switch (event.kind) {
      // THE WHOLE EVENT: the shared case arms narrow `event` to
      // exactly the `SystemEvent` union, so the callback's envelope and the switch's narrowing
      // are the same type by construction. What each kind DOES with its payload is
      // `connection.ts`'s decision — this module still reads nothing but the discriminant.
      case 'active_deck_changed':
      case 'deck_changed':
        onSystemEvent(event)
        return
      // THE FIRST AGENT VIEW WITH SOMEWHERE TO GO. The whole event, not its kind — the payload
      // IS the content. `connection.ts` turns it into an open view; this module still knows
      // nothing about a store.
      case 'suggestions':
        onSuggestions(event)
        return
      // THE SECOND AGENT VIEW WITH SOMEWHERE TO GO. Same shape as the arm above: the whole
      // event, because the payload is the content, and `connection.ts` decides what a store
      // does with it.
      case 'swaps':
        onSwaps(event)
        return
      // THE THIRD AGENT VIEW WITH SOMEWHERE TO GO. Same shape as the two arms above: the whole
      // event, because the payload is the content, and `connection.ts` decides what a store
      // does with it.
      case 'tier_list':
        onTierList(event)
        return
      // THE FOURTH AND LAST AGENT VIEW WITH SOMEWHERE TO GO. Same shape as its three siblings:
      // every kind the enum admits is delivered somewhere, and the `never` arm below is the
      // only non-delivering path left.
      case 'groups':
        onGroups(event)
        return
      default: {
        // A seventh kind is a COMPILE failure naming the kind, not a runtime fallthrough.
        // `AGENT_EVENT_KINDS` in `client.ts` is the narrower's half of the
        // same guarantee, so a new kind cannot even reach this switch unrecognised.
        const unhandled: never = event
        return unhandled
      }
    }
  }

  /**
   * `delay → mint → open`, once. Every await is followed by a generation re-check.
   *
   * The delay is not in this function — it is the `setTimeout` that called it — which is what
   * makes the ordering structural: there is no code path on which a ticket is minted and then
   * waited on. See the module header for why that matters at exactly the ceiling.
   */
  const attempt = async (gen: number): Promise<void> => {
    if (gen !== generation || !live) return

    let outcome: SessionOutcome
    try {
      outcome = await mint()
    } catch {
      // `readSessionTicket` is total and cannot reject; an injected reader might.
      outcome = { kind: 'unreachable' }
    }
    if (gen !== generation || !live) return

    // Every non-ticket outcome is the same failure: there is nothing to open a socket with. The
    // `error` arm is the interesting one only in that reaching it means something that is not the
    // companion answered on the port — see `SessionOutcome`.
    if (outcome.kind !== 'ticket') return fail(gen)

    let handle: AgentSocketHandle
    try {
      handle = open(outcome.ticket, {
        onOpen: () => succeed(gen),
        onMessage: (event) => receive(gen, event),
        onClose: () => fail(gen),
      })
    } catch {
      // The constructor throws on a malformed URL and in a runtime with no socket support at all.
      // Neither is recoverable by retrying, and neither is worth a branch of its own: the loop
      // backs off, which costs one failed attempt per ceiling against a browser that was never
      // going to work, and leaves the Disconnected panel saying the true thing.
      return fail(gen)
    }

    // The socket is created SYNCHRONOUSLY, but `open` above may already have driven the loop to a
    // new generation (a fake in a test does; a real browser that refuses a handshake instantly
    // could). Assigning it to the shared slot in that case would hand `stop()` a socket belonging
    // to an attempt that is already over, and — worse — would leave the CURRENT attempt's socket
    // unreferenced and uncloseable.
    if (gen !== generation || !live) {
      handle.close()
      return
    }
    socket = handle
  }

  return {
    start: () => {
      if (live) return
      live = true
      generation += 1
      // A restart is a NEW connection. Wall time that passed while stopped is not evidence: an
      // inherited ceiling would make the first retry half a minute late on a tab that just
      // remounted, and an inherited failure clock would announce a lost backend that nobody was
      // even connected to.
      delay = SOCKET_BASE_MS
      failures = 0
      failingSince = null
      void attempt(generation)
    },
    stop: () => {
      live = false
      generation += 1
      clearTimeout(timer)
      timer = undefined
      abandon()
    },
  }
}
