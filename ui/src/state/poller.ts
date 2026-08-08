/**
 * The poll that makes a fresh install come alive on its own (story c3-9, FR-22, AC 3/6/7).
 *
 * The backend half of FR-22 has been done since **c1-6**: `deps.get_session` re-probes readiness
 * on **every** request and never caches, *"because a database created while the backend is
 * running must be picked up with no restart, which a remembered `True` would break as surely as a
 * remembered `False`"*. So `GET /api/decks` flips from `503` to `200` by itself the moment the
 * import finishes, and nothing needs restarting, busting or reloading. **This file is the client
 * half**: something has to ask again.
 *
 * Framework-free on purpose — no React, no store import, no module-level state. It takes a
 * reader and emits updates, so every timing assertion in `poller.test.ts` runs on fake timers
 * against a plain function, and the React seam (`systemState.ts`) has nothing timing-shaped left
 * in it to get wrong.
 *
 * ================= THE RETRY DECISION IS `RETRIES_QUIETLY`, READ AT RUNTIME =============
 *
 * `states.ts` has held the retry contract since c2-9 and it is **not uniform**:
 * `database-not-initialized` and `database-updating` retry; `no-active-deck`,
 * `database-updating-stalled` and `internal-error` do not. Its docstring gives the reason for the
 * load-bearing `false`: `internal_error` is deterministic, so *"a quiet retry loop would hammer a
 * broken backend while showing the user a calm panel that never changes"*. This file therefore
 * INDEXES that map rather than carrying a list of retryable states — a paraphrase would be a
 * second copy of a contract, free to drift, and `poller.test.ts` flips an entry and watches the
 * behaviour follow it.
 *
 * **The one outcome the map does not decide is `unreachable`**, and that is not an exception to
 * the rule so much as a case outside its domain: `RETRIES_QUIETLY` answers *"does this STATE
 * retry itself"*, and a `fetch` rejection produced no state — the panel does not change, so there
 * is nothing to look up. It is retried on the same backoff because a lost backend is transient by
 * nature. The panel that actually describes one — `disconnected`, *"Lost the companion backend"* —
 * is **c5-6's** by `CLIENT_ONLY_STATES`, whose condition is the WebSocket backoff reaching its
 * announcement threshold, and this story may not claim it.
 *
 * **THE RESIDUE THAT LEFT IS CLOSED (c5-6, 2026-08-08).** It read *"a backend down at first load
 * shows the initial panel, quietly retrying"* — ledgered at dw:3451, confirmed live at Block I and
 * judged worse than recorded, because the panel it showed was `no-active-deck`, whose copy is
 * actionable and wrong about a backend that is not running. `src/state/socket.ts` now supplies the
 * missing signal: sixty seconds and four failed attempts after a cold open against nothing, the
 * connection reads `'down'` and `surfaceOf` puts the true panel on the glass. **This poller is
 * unchanged** — it still claims no state for an `unreachable`, which is what made the two halves
 * composable instead of racing.
 *
 * ================= THE NUMBERS, WITH THEIR ARITHMETIC (Q2, Q3) ==========================
 *
 * Each constant carries the sum that produced it, in the manner of `FETCH_SPACING_SECONDS`.
 * They are not tuned against a benchmark — there is one client and one localhost backend — they
 * are chosen so that the two things a human notices are both true: the page does not hammer a
 * backend that is deliberately busy importing, and it does not feel dead when the import lands.
 */

import { RETRIES_QUIETLY } from '../components/StatePanel/states'
import type { StateKey } from '../components/StatePanel/copy'
import { readDecks, type DecksOutcome } from '../api/client'
import { panelFor } from './panel'

/**
 * The first retry lands this long after the first answer.
 *
 * 2 s: a first `initialize_database` build takes **minutes** (`database.py:135-138` — the file,
 * the table, an empty table and a mid-way-killed import all read as not-initialized, so the
 * "Card database not set up yet." panel is what shows for the *whole* first import). At a fixed
 * 2 s that would be ~150 requests against a backend that is deliberately busy, which is what the
 * multiplier below exists to stop; as a STARTING point it is short enough that a database which
 * lands two seconds after the page opens is picked up immediately.
 */
export const POLL_BASE_MS = 2_000

/**
 * Each retry waits this much longer than the last.
 *
 * 2, so the schedule from the base is 2 s, 4 s, 8 s, 16 s, 30 s (the ceiling clamps 32), 30 s… —
 * five requests in the first thirty seconds and two per minute thereafter, against an import that
 * runs for minutes.
 */
export const POLL_MULTIPLIER = 2

/**
 * …but never longer than this.
 *
 * 30 s. Without a ceiling the delay doubles forever and the *"this page will come alive on its
 * own when it's ready"* promise the copy makes becomes false in the only way a human can measure
 * it: after ten minutes of waiting the next check would be minutes away, so the page would
 * transition long after the database landed. A ceiling is the difference between a backoff and a
 * countdown to never, and it is invisible to any test that only asserts "it retries" — which is
 * why `poller.test.ts` asserts the growth AND the clamp from the same schedule.
 */
export const POLL_CEILING_MS = 30_000

/**
 * How long `database_unavailable` must answer CONTINUOUSLY before the stalled panel replaces the
 * updating one (Q3 — this story's only new number, held open by `EXPERIENCE.md:66` since c2-9).
 *
 * 60 s. At the schedule above that is at least six consecutive refusals with the last two a full
 * ceiling apart (t = 0, 2, 6, 14, 30, 60 s), so a single slow write burst cannot escalate: the
 * backend would have to refuse every read for a solid minute. The state it escalates to says
 * *"Reads haven't resumed for a while"* and tells the user to check whether an import is actually
 * running — a claim that is only worth making once "a while" is long enough to be true.
 *
 * **`database_not_initialized` never escalates, at any elapsed time**, and that is the whole
 * subject of Q3 rather than an omission. A multi-minute first build is that token's NORMAL case,
 * and its own copy already promises the wait; escalating it would call a working import stalled,
 * in the one panel whose entire subject is whether the words are true. The clock below is armed
 * by `database_unavailable` and by nothing else.
 */
export const STALLED_AFTER_MS = 60_000

/**
 * …and this many CONSECUTIVE `database_unavailable` answers must actually have been observed.
 *
 * The elapsed clock reads `Date.now()`, which is wall time, and wall time keeps moving when
 * timers do not: a suspended laptop and a background tab (browsers clamp `setTimeout` to once a
 * minute or slower there) both advance the first without running the second. Without a floor,
 * two refusals bracketing a nap satisfy "60 s of continuous refusal" — one busy blip on each
 * side of a sleep would escalate, and because the stalled state never retries itself, the wrong
 * panel would then be terminal.
 *
 * 4: on the live schedule the floor never binds — 60 s of elapsed refusal already means six
 * observations (t = 0, 2, 6, 14, 30, 60 s) — so it only speaks when the schedule was frozen,
 * where it demands four real answers before the clock's opinion counts.
 */
export const STALLED_MIN_REFUSALS = 4

/** What one poll decided: the panel to show, and the deck names it carries (never both slots). */
export interface PollUpdate {
  readonly panel: StateKey
  readonly decks: readonly string[]
}

export interface PollerOptions {
  /** Emitted once per outcome that DECIDED a panel. Not called for `unreachable`. */
  readonly onUpdate: (update: PollUpdate) => void
  /** Injected so tests need no global `fetch` stub; production passes nothing. */
  readonly read?: () => Promise<DecksOutcome>
  /**
   * The panel already on screen when polling starts, so the first `RETRIES_QUIETLY` lookup and
   * the "unreachable leaves it unchanged" rule both have something true to read.
   */
  readonly initialPanel?: StateKey
}

export interface Poller {
  /**
   * Polls IMMEDIATELY, then on the backoff. Idempotent while running. A restart after `stop()`
   * begins a NEW poll: the backoff, the outcome identity and the stalled clock all reset,
   * because wall time that passed while nobody was polling is not evidence about the backend.
   */
  start: () => void
  /** Cancels the pending timer and drops any answer still in flight. Idempotent. */
  stop: () => void
}

/**
 * Build a poller. Nothing happens until `start()`.
 *
 * Args:
 *   options: See `PollerOptions`.
 *
 * Returns:
 *   A `Poller`. Every instance owns its own backoff and its own elapsed clock, so a second one
 *   (React StrictMode remounts the effect in development) cannot inherit the first's countdown.
 */
export const createPoller = ({
  onUpdate,
  read = readDecks,
  initialPanel = 'no-active-deck',
}: PollerOptions): Poller => {
  let live = false
  /**
   * Bumped by every `start()` AND every `stop()`, and carried by each tick and each timer. A
   * plain `live` boolean cannot tell "stopped" from "stopped and restarted": a read that was in
   * flight across a restart would see `live === true` again, apply its stale outcome and call
   * `schedule()` — a second timer chain, polling at double rate, that the next `stop()` (which
   * clears only the single `timer` slot) could never fully cancel.
   */
  let generation = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  let delay = POLL_BASE_MS
  let panel: StateKey = initialPanel
  /** The last update handed to `onUpdate`, so an identical decision is not re-emitted. */
  let emitted: PollUpdate = { panel: initialPanel, decks: [] }

  /**
   * The identity of the last outcome, so a CHANGE resets the backoff.
   *
   * Without it a page that spent ten minutes on a fresh install would still be waiting a full
   * ceiling before noticing the next thing that happened, which is the same "comes alive on its
   * own, eventually" failure the ceiling itself exists to prevent — just one layer up.
   */
  let lastOutcome: string | null = null

  /**
   * When `database_unavailable` started answering continuously, or `null` if it is not.
   *
   * `null` is the reset, and EVERY other outcome performs it — a `200`, a different token, even a
   * network rejection. One good answer means reads resumed, and a countdown that survived it
   * would escalate a database that had already recovered.
   */
  let unavailableSince: number | null = null

  /**
   * How many times in a row `database_unavailable` has actually been OBSERVED — the elapsed
   * clock's partner, because `Date.now()` keeps counting through a laptop sleep or a throttled
   * background tab while the schedule does not. See `STALLED_MIN_REFUSALS`.
   */
  let unavailableStreak = 0

  const schedule = (gen: number) => {
    timer = setTimeout(() => void tick(gen), delay)
    // Grown AFTER the wait is committed, so the first retry lands at exactly the base delay.
    delay = Math.min(delay * POLL_MULTIPLIER, POLL_CEILING_MS)
  }

  const identify = (outcome: DecksOutcome): string =>
    // A token-less refusal is bare `'error'`, which no real token can spell (`'error:' + token`
    // always carries the colon) — template-stringing `null` would collide with a literal
    // `"null"` token and merge distinct malformed refusals into one identity.
    outcome.kind === 'error'
      ? outcome.reason === null
        ? 'error'
        : `error:${outcome.reason}`
      : outcome.kind

  const apply = (outcome: DecksOutcome) => {
    const identity = identify(outcome)
    if (identity !== lastOutcome) {
      lastOutcome = identity
      delay = POLL_BASE_MS
    }

    // THE ESCALATION GUARD. Armed by one token and reset by everything else — including by
    // `database_not_initialized`, which is why a multi-minute first build never escalates.
    if (outcome.kind === 'error' && outcome.reason === 'database_unavailable') {
      unavailableSince ??= Date.now()
      unavailableStreak += 1
    } else {
      unavailableSince = null
      unavailableStreak = 0
    }

    // No response arrived, so nothing was decided: the panel stands and no update is emitted.
    if (outcome.kind === 'unreachable') return

    // A `200` is `no-active-deck` and its deck list. **c4-2 has now shipped the deck view, and
    // this line did NOT change** — which is the interesting half. This poll answers *"is the
    // backend serving decks, and what are they called"*; whether a DECK is on the glass is a
    // different question, answered by `GET /api/active-deck` in `src/state/deck.ts`, and
    // `surfaceOf` is the one place the two are reconciled. So the decision below is still made
    // and is simply not rendered when a deck outranks it — honest and cheap, and it keeps this
    // file's single subject intact. What the deck view DOES still depend on here is the deck
    // NAMES: they are what the `no-active-deck` panel lists, and nothing else fetches them.
    //
    // An empty array is the ordinary fresh-install answer, not an edge case, and renders nothing
    // extra.
    const decided = outcome.kind === 'decks' ? 'no-active-deck' : panelFor(outcome.reason)
    // BOTH halves, because they measure different things: the clock measures elapsed wall time,
    // the streak measures that anyone was awake to watch it pass. See `STALLED_MIN_REFUSALS`.
    const stalled =
      unavailableSince !== null &&
      unavailableStreak >= STALLED_MIN_REFUSALS &&
      Date.now() - unavailableSince >= STALLED_AFTER_MS

    panel = stalled ? 'database-updating-stalled' : decided
    const decks = outcome.kind === 'decks' ? outcome.decks : []

    // Emitted once per CHANGE, not once per poll: `lastOutcome` already knows an identical
    // answer is identical, and re-emitting it would re-render the whole app every 2–30 s for
    // the entire length of a first build, for nothing.
    const unchanged =
      emitted.panel === panel &&
      emitted.decks.length === decks.length &&
      emitted.decks.every((name, index) => name === decks[index])
    if (unchanged) return

    emitted = { panel, decks }
    onUpdate(emitted)
  }

  const tick = async (gen: number) => {
    if (gen !== generation || !live) return
    let outcome: DecksOutcome
    try {
      outcome = await read()
    } catch {
      // `readDecks` is total and cannot reject; an injected reader might.
      outcome = { kind: 'unreachable' }
    }
    // Re-checked after the await, against the GENERATION and not just the flag: `stop()` may
    // have run while the request was in flight — and so may `stop()` then `start()`, which a
    // boolean cannot see. A stale answer applied here would write an outdated panel and fork a
    // second timer chain.
    if (gen !== generation || !live) return

    apply(outcome)

    // `unreachable` decided no state, so there is no `RETRIES_QUIETLY` entry to consult — see
    // the header. Everything else is the map's call and only the map's.
    if (outcome.kind === 'unreachable' || RETRIES_QUIETLY[panel]) schedule(gen)
  }

  return {
    start: () => {
      if (live) return
      live = true
      generation += 1
      // A restart is a NEW poll. Wall time that passed while stopped is not evidence: an
      // inherited ceiling would make the first retry minutes late, and an inherited stalled
      // clock would escalate a backend nobody was even watching.
      delay = POLL_BASE_MS
      lastOutcome = null
      unavailableSince = null
      unavailableStreak = 0
      void tick(generation)
    },
    stop: () => {
      live = false
      generation += 1
      clearTimeout(timer)
      timer = undefined
    },
  }
}
