/**
 * The poll's schedule, its retry contract and its elapsed clock (story c3-9, AC 3, AC 6, AC 7).
 *
 * EVERY assertion runs on fake timers and nothing sleeps for real time — a suite that waited out
 * a 60-second threshold would take a minute per case and would be deleted by the third person to
 * run it. `vi.setSystemTime(0)` on top of the fake timers is what makes the recorded call times
 * readable as offsets rather than as epoch milliseconds; the poller reads `Date.now()` for its
 * elapsed clock, and vitest's fake timers mock that too.
 *
 * The reader is INJECTED rather than stubbed onto `globalThis.fetch`, so these tests are about
 * scheduling and nothing else: what a malformed body does is `api/client.test.ts`'s subject, and
 * what a token means is `panel.test.ts`'s.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RETRIES_QUIETLY } from '../components/StatePanel/states'
import type { StateKey } from '../components/StatePanel/copy'
import type { DecksOutcome } from '../api/client'
import {
  createPoller,
  POLL_BASE_MS,
  POLL_CEILING_MS,
  POLL_MULTIPLIER,
  STALLED_AFTER_MS,
  STALLED_MIN_REFUSALS,
  type PollUpdate,
} from './poller'

const NOT_INITIALIZED: DecksOutcome = { kind: 'error', reason: 'database_not_initialized' }
const UNAVAILABLE: DecksOutcome = { kind: 'error', reason: 'database_unavailable' }
const BROKEN: DecksOutcome = { kind: 'error', reason: 'internal_error' }
const UNREACHABLE: DecksOutcome = { kind: 'unreachable' }
const READY: DecksOutcome = { kind: 'decks', decks: ['Boros Aggro'] }

/** A reader that always answers the same thing, recording when it was asked. */
const always = (outcome: DecksOutcome) => {
  const at: number[] = []
  const read = () => {
    at.push(Date.now())
    return Promise.resolve(outcome)
  }
  return { at, read }
}

/** A reader that walks a script, repeating its last entry forever. */
const script = (...outcomes: DecksOutcome[]) => {
  const at: number[] = []
  let index = 0
  const read = () => {
    at.push(Date.now())
    const outcome = outcomes[Math.min(index, outcomes.length - 1)]
    index += 1
    return Promise.resolve(outcome)
  }
  return { at, read }
}

const drive = (read: () => Promise<DecksOutcome>) => {
  const updates: PollUpdate[] = []
  const poller = createPoller({ read, onUpdate: (update) => updates.push(update) })
  return { poller, updates, panel: () => updates.at(-1)?.panel }
}

/** Let the immediate first poll (a microtask chain, not a timer) settle. */
const settle = () => vi.advanceTimersByTimeAsync(0)

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(0)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('the backoff grows and then STOPS growing (AC 3)', () => {
  it('polls immediately, then on 2 s, 4 s, 8 s, 16 s and 30 s — and never longer', async () => {
    const { at, read } = always(NOT_INITIALIZED)
    const { poller } = drive(read)

    poller.start()
    await settle()
    // No initial wait: a fresh install should get its panel now, not in two seconds.
    expect(at).toEqual([0])

    // THE GROWTH HALF. Each advance is exactly the delay that should be pending; if the poller
    // had scheduled a shorter one the recorded time would be earlier, and a longer one would
    // record nothing at all.
    await vi.advanceTimersByTimeAsync(POLL_BASE_MS)
    expect(at).toEqual([0, 2_000])
    await vi.advanceTimersByTimeAsync(4_000)
    expect(at).toEqual([0, 2_000, 6_000])
    await vi.advanceTimersByTimeAsync(8_000)
    expect(at).toEqual([0, 2_000, 6_000, 14_000])
    await vi.advanceTimersByTimeAsync(16_000)
    expect(at).toEqual([0, 2_000, 6_000, 14_000, 30_000])

    // THE CLAMP HALF, from the same schedule (AC 26). 16 s × 2 is 32 s, and the next gap is 30 s;
    // an unclamped backoff would have been silent here and for the two hours after it, while
    // every "it retries" assertion above stayed green. This is probe (a)'s target.
    await vi.advanceTimersByTimeAsync(POLL_CEILING_MS)
    expect(at).toEqual([0, 2_000, 6_000, 14_000, 30_000, 60_000])
    await vi.advanceTimersByTimeAsync(POLL_CEILING_MS)
    expect(at).toEqual([0, 2_000, 6_000, 14_000, 30_000, 60_000, 90_000])

    poller.stop()
  })

  it('stays clamped over a long wait, rather than drifting up slowly', async () => {
    const { at, read } = always(NOT_INITIALIZED)
    const { poller } = drive(read)

    poller.start()
    await settle()
    await vi.advanceTimersByTimeAsync(60 * 60_000)

    // One hour. Under the ceiling the tail is 2 polls/minute; unclamped the delay would have
    // passed an hour by the twelfth retry and the count here would be ~12.
    expect(at.length).toBeGreaterThan(100)
    const gaps = at.slice(1).map((time, index) => time - at[index])
    expect(Math.max(...gaps)).toBe(POLL_CEILING_MS)

    poller.stop()
  })

  it('resets to the base delay when the outcome CHANGES', async () => {
    // Four not-initialized answers put the delay at 16 s; the fifth answer is a different token,
    // and the poll after it must land 2 s later rather than 30 s later. Without this, a page that
    // waited out a long first build would take a full ceiling to notice what happened next.
    const { at, read } = script(
      NOT_INITIALIZED,
      NOT_INITIALIZED,
      NOT_INITIALIZED,
      NOT_INITIALIZED,
      UNAVAILABLE,
      UNAVAILABLE,
    )
    const { poller } = drive(read)

    poller.start()
    await settle()
    await vi.advanceTimersByTimeAsync(14_000)
    expect(at).toEqual([0, 2_000, 6_000, 14_000])

    // The fifth poll (at 30 s) is the first `database_unavailable`; the sixth must be at 32 s.
    await vi.advanceTimersByTimeAsync(16_000)
    expect(at.at(-1)).toBe(30_000)
    await vi.advanceTimersByTimeAsync(POLL_BASE_MS)
    expect(at.at(-1)).toBe(32_000)

    poller.stop()
  })

  it('multiplies rather than adding — the arithmetic the constants claim', () => {
    // The constants carry their sums in their own docstrings; this is the one assertion that
    // the schedule above is those constants and not three magic numbers that happen to agree.
    expect(POLL_BASE_MS * POLL_MULTIPLIER).toBe(4_000)
    expect(POLL_BASE_MS * POLL_MULTIPLIER ** 4).toBeGreaterThan(POLL_CEILING_MS)
  })
})

describe('RETRIES_QUIETLY is the retry contract, and it is READ (AC 7)', () => {
  it('does not poll again after a state the map says never retries itself', async () => {
    const { at, read } = always(BROKEN)
    const { poller, panel } = drive(read)

    poller.start()
    await settle()
    expect(panel()).toBe('internal-error')
    expect(RETRIES_QUIETLY['internal-error']).toBe(false)

    await vi.advanceTimersByTimeAsync(10 * 60_000)

    // Ten minutes. `states.ts` gives the reason in its own docstring: a quiet retry loop would
    // "hammer a broken backend while showing the user a calm panel that never changes".
    expect(at).toEqual([0])

    poller.stop()
  })

  it('does not poll again once a deck list arrives — the agent drives from there', async () => {
    const { at, read } = always(READY)
    const { poller, panel } = drive(read)

    poller.start()
    await settle()
    expect(panel()).toBe('no-active-deck')
    expect(RETRIES_QUIETLY['no-active-deck']).toBe(false)

    await vi.advanceTimersByTimeAsync(10 * 60_000)
    expect(at).toEqual([0])

    poller.stop()
  })

  it('FOLLOWS the map rather than paraphrasing it — flip an entry and the behaviour moves', async () => {
    // The assertion that separates "consults the contract" from "happens to agree with it
    // today". A poller carrying its own list of retryable states passes every other test in this
    // file and fails this one. Probe (b) removes the consult entirely.
    const original = RETRIES_QUIETLY['internal-error']
    try {
      // The cast is the assertion, not a workaround: `satisfies` preserves the LITERAL type, so
      // `RETRIES_QUIETLY['internal-error']` is typed `false` and the compiler refuses the flip.
      // Widening it here is a deliberate, reverted violation of a contract the runtime is
      // supposed to be reading — which is exactly what this test is trying to observe.
      ;(RETRIES_QUIETLY as Record<StateKey, boolean>)['internal-error'] = true

      const { at, read } = always(BROKEN)
      const { poller } = drive(read)

      poller.start()
      await settle()
      await vi.advanceTimersByTimeAsync(POLL_BASE_MS)

      expect(at).toEqual([0, 2_000])
      poller.stop()
    } finally {
      ;(RETRIES_QUIETLY as Record<StateKey, boolean>)['internal-error'] = original
    }
    // …and restored, so the ban is not silently disabled for whatever runs next.
    expect(RETRIES_QUIETLY['internal-error']).toBe(false)
  })

  it('keeps polling the states the map says DO retry — the silent half (AC 26)', async () => {
    for (const [outcome, expected] of [
      [NOT_INITIALIZED, 'database-not-initialized'],
      [UNAVAILABLE, 'database-updating'],
    ] as const) {
      const started = Date.now()
      const { at, read } = always(outcome)
      const { poller, panel } = drive(read)

      poller.start()
      await settle()
      expect(panel()).toBe(expected)
      expect(RETRIES_QUIETLY[expected]).toBe(true)

      await vi.advanceTimersByTimeAsync(POLL_BASE_MS)
      // Offsets, not absolutes: the fake clock is not rewound between the two loop passes.
      expect(at.map((time) => time - started)).toEqual([0, 2_000])
      poller.stop()
    }
  })
})

describe('the stalled escalation fires on ONE token only (AC 6, Q3)', () => {
  it('escalates after 60 s of continuous database_unavailable, and then stops retrying', async () => {
    const { at, read } = always(UNAVAILABLE)
    const { poller, panel } = drive(read)

    poller.start()
    await settle()
    expect(panel()).toBe('database-updating')

    // One tick short of the threshold: still the calm panel.
    await vi.advanceTimersByTimeAsync(30_000)
    expect(panel()).toBe('database-updating')

    await vi.advanceTimersByTimeAsync(30_000)
    expect(Date.now()).toBe(STALLED_AFTER_MS)
    expect(panel()).toBe('database-updating-stalled')

    // …and the escalation of a quiet retry that has not worked does not keep retrying quietly.
    const polls = at.length
    expect(RETRIES_QUIETLY['database-updating-stalled']).toBe(false)
    await vi.advanceTimersByTimeAsync(10 * 60_000)
    expect(at).toHaveLength(polls)

    poller.stop()
  })

  it('NEVER escalates database_not_initialized, not even after ten times the threshold', async () => {
    const { read } = always(NOT_INITIALIZED)
    const { poller, panel, updates } = drive(read)

    poller.start()
    await settle()
    await vi.advanceTimersByTimeAsync(STALLED_AFTER_MS * 10)

    // Ten minutes of a first build, which is its NORMAL case — `database.py:135-138` returns
    // not-initialized for the entire multi-minute import, and the panel's own copy promises the
    // wait ("First build takes a few minutes"). Escalating here would call a working import
    // stalled, in the one panel whose whole subject is whether the words are true.
    expect(panel()).toBe('database-not-initialized')
    expect(updates.map((update) => update.panel)).not.toContain('database-updating-stalled')

    poller.stop()
  })

  it('is armed by nothing else either — a 500 for ten minutes does not escalate', async () => {
    const { read } = always(BROKEN)
    const { poller, panel } = drive(read)

    poller.start()
    await settle()
    await vi.advanceTimersByTimeAsync(STALLED_AFTER_MS * 10)

    expect(panel()).toBe('internal-error')

    poller.stop()
  })

  it('lets one good answer reset the clock, so the next outage starts from zero (AC 6)', async () => {
    // 30 s of `database_unavailable`, then a 200 at the 60 s mark — the exact tick that WOULD
    // have escalated had it refused again. The 200 ends the poll on its own (`no-active-deck`
    // never retries itself), and restarting the SAME poller is the realistic shape of "reads
    // resumed and then failed again": `unavailableSince` is that instance's own state, so this
    // proves the reset rather than testing a fresh object.
    const outcome: { current: DecksOutcome } = { current: UNAVAILABLE }
    const { poller, panel } = drive(() => Promise.resolve(outcome.current))

    poller.start()
    await settle()
    await vi.advanceTimersByTimeAsync(30_000)
    expect(panel()).toBe('database-updating')

    outcome.current = READY
    await vi.advanceTimersByTimeAsync(30_000)
    expect(Date.now()).toBe(STALLED_AFTER_MS)
    // The reset happens BEFORE the escalation check, which this tick is what proves: 60 s of
    // continuous refusal had elapsed, and a good answer at exactly that moment is not stalled.
    expect(panel()).toBe('no-active-deck')

    outcome.current = UNAVAILABLE
    poller.stop()
    poller.start()
    await settle()
    expect(panel()).toBe('database-updating')

    // 40 s into the second outage — 100 s since the first refusal. A countdown that survived the
    // good answer would read stalled here.
    await vi.advanceTimersByTimeAsync(40_000)
    expect(panel()).toBe('database-updating')

    // …and the second outage still escalates on its own schedule (the non-vacuity half).
    await vi.advanceTimersByTimeAsync(30_000)
    expect(panel()).toBe('database-updating-stalled')

    poller.stop()
  })

  it('resets on a DIFFERENT token too, which is the reachable case in one poll run', async () => {
    // A 200 ends the poll, so the reset that happens WITHOUT a restart is a token change:
    // unavailable → not-initialized → unavailable. Polls land at 0, 2, 6, 14, 30 and 60 s, so
    // the sixth answer is the reset and it arrives on the tick that would otherwise escalate.
    const { read } = script(
      UNAVAILABLE,
      UNAVAILABLE,
      UNAVAILABLE,
      UNAVAILABLE,
      UNAVAILABLE,
      NOT_INITIALIZED,
      UNAVAILABLE,
    )
    const { poller, panel } = drive(read)

    poller.start()
    await settle()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(panel()).toBe('database-not-initialized')

    // 100 s after the first refusal, 38 s into the second outage.
    await vi.advanceTimersByTimeAsync(40_000)
    expect(panel()).toBe('database-updating')

    await vi.advanceTimersByTimeAsync(30_000)
    expect(panel()).toBe('database-updating-stalled')

    poller.stop()
  })
})

describe('an unreachable backend claims no state and keeps trying', () => {
  it('leaves the panel alone and retries anyway, even though no-active-deck never retries', async () => {
    const { at, read } = always(UNREACHABLE)
    const { poller, updates } = drive(read)

    poller.start()
    await settle()
    await vi.advanceTimersByTimeAsync(POLL_BASE_MS + 4_000)

    // No update at all: `fetch` rejecting produced no response, so no state was decided.
    // `disconnected` — the panel that describes a lost backend — is c5-6's by
    // `CLIENT_ONLY_STATES`, and this story must not claim it.
    expect(updates).toEqual([])
    expect(at).toEqual([0, 2_000, 6_000])

    poller.stop()
  })

  it('hands control straight back to the map once a real answer arrives (non-vacuity)', async () => {
    const { at, read } = script(UNREACHABLE, UNREACHABLE, BROKEN)
    const { poller, panel } = drive(read)

    poller.start()
    await settle()
    await vi.advanceTimersByTimeAsync(6_000)

    expect(panel()).toBe('internal-error')
    const polls = at.length
    await vi.advanceTimersByTimeAsync(10 * 60_000)
    // The "retry regardless" rule is scoped to the outcome, not sticky on the poller.
    expect(at).toHaveLength(polls)

    poller.stop()
  })
})

describe('stopping is real, not advisory', () => {
  it('drops an answer that lands after stop(), and schedules nothing', async () => {
    let resolve: ((outcome: DecksOutcome) => void) | undefined
    const { poller, updates } = drive(
      () =>
        new Promise<DecksOutcome>((r) => {
          resolve = r
        }),
    )

    poller.start()
    await settle()
    poller.stop()
    resolve?.(NOT_INITIALIZED)
    await vi.advanceTimersByTimeAsync(10 * 60_000)

    // Writing a panel into an unmounted app is the React warning nobody reads; asserted rather
    // than assumed because React StrictMode mounts the effect twice in development.
    expect(updates).toEqual([])
  })

  it('starts only once, so a double mount cannot double the poll rate', async () => {
    const { at, read } = always(NOT_INITIALIZED)
    const { poller } = drive(read)

    poller.start()
    poller.start()
    await settle()
    await vi.advanceTimersByTimeAsync(POLL_BASE_MS)

    expect(at).toEqual([0, 2_000])

    poller.stop()
  })

  it('drops an answer still in flight across a stop()/start(), and forks no second chain', async () => {
    // The hole a plain boolean cannot see: the STALE read resolves after the restart, when
    // `live` is true again. Applying it would emit an outdated panel; scheduling from it would
    // fork a second timer chain the next stop() could never fully clear.
    const resolvers: ((outcome: DecksOutcome) => void)[] = []
    const { poller, updates } = drive(() => new Promise<DecksOutcome>((r) => resolvers.push(r)))

    poller.start()
    await settle()
    poller.stop()
    poller.start()
    await settle()
    expect(resolvers).toHaveLength(2)

    resolvers[0]?.(BROKEN)
    await settle()
    // The stale answer decided nothing: no update, no panel, no schedule.
    expect(updates).toEqual([])

    resolvers[1]?.(NOT_INITIALIZED)
    await settle()
    expect(updates.map((update) => update.panel)).toEqual(['database-not-initialized'])

    // ONE chain: exactly one retry lands at the base delay. A forked chain would have asked
    // twice.
    await vi.advanceTimersByTimeAsync(POLL_BASE_MS)
    expect(resolvers).toHaveLength(3)

    poller.stop()
  })

  it('restarts as a NEW poll: base delay and a clean stalled clock, not the inherited ones', async () => {
    const { at, read } = always(UNAVAILABLE)
    const { poller, panel, updates } = drive(read)

    poller.start()
    await settle()
    // Refusals at 0, 2, 6, 14 and 30 s: the delay is at the ceiling and the clock is 30 s old.
    await vi.advanceTimersByTimeAsync(30_000)
    expect(panel()).toBe('database-updating')
    poller.stop()

    // Ten minutes pass while nobody is polling — wall time a surviving clock would count.
    vi.setSystemTime(600_000)
    poller.start()
    await settle()

    // A clock that survived stop() reads >60 s of "continuous" refusal here and escalates a
    // backend nobody was watching. The restart reset it: still the calm panel.
    expect(updates.map((update) => update.panel)).not.toContain('database-updating-stalled')

    // …and the backoff restarted at the base, not at the inherited ceiling.
    await vi.advanceTimersByTimeAsync(POLL_BASE_MS)
    expect(at.filter((time) => time >= 600_000)).toEqual([600_000, 602_000])

    poller.stop()
  })
})

describe('the stalled clock needs OBSERVATIONS, not just elapsed wall time', () => {
  it('does not escalate off two refusals bracketing a suspend, then does off real ones (AC 26)', async () => {
    // Wall time advances through a laptop sleep or a throttled background tab; the schedule
    // does not. Two busy blips separated by a ten-minute nap satisfy "60 s elapsed" — and
    // because the stalled panel never retries itself, escalating here would be terminal.
    const { read } = always(UNAVAILABLE)
    const { poller, panel } = drive(read)

    poller.start()
    await settle() // refusal 1 arms the clock at t=0
    vi.setSystemTime(600_000) // the nap: ten minutes of wall time, zero timer fires
    await vi.advanceTimersByTimeAsync(POLL_BASE_MS) // refusal 2 — elapsed reads ten minutes

    expect(panel()).toBe('database-updating')

    // The firing half from the same run: two more REAL refusals reach the floor, the elapsed
    // clock has long been satisfied, and the escalation goes through.
    await vi.advanceTimersByTimeAsync(4_000)
    expect(panel()).toBe('database-updating')
    await vi.advanceTimersByTimeAsync(8_000)
    expect(panel()).toBe('database-updating-stalled')

    poller.stop()
  })

  it('never binds on the live schedule — 60 s of refusal already means six observations', () => {
    // The floor exists for frozen schedules only. On the real one (t = 0, 2, 6, 14, 30, 60 s)
    // the sixth refusal is what crosses 60 s, so a floor of four cannot delay a genuine
    // escalation — asserted so the two constants cannot drift into an arrangement where it can.
    const schedule = [0, 2_000, 6_000, 14_000, 30_000, 60_000]
    const observedBefore = schedule.filter((time) => time <= STALLED_AFTER_MS).length
    expect(observedBefore).toBeGreaterThanOrEqual(STALLED_MIN_REFUSALS)
  })
})

describe('an update is a CHANGE, not a heartbeat', () => {
  it('emits once for a whole build of identical answers, and again when the answer moves', async () => {
    // A first build answers `database_not_initialized` for minutes. Re-emitting the identical
    // decision every 2–30 s would re-render the whole app for nothing — the poller's own
    // `lastOutcome` already knows nothing changed.
    const outcome: { current: DecksOutcome } = { current: NOT_INITIALIZED }
    const { poller, updates } = drive(() => Promise.resolve(outcome.current))

    poller.start()
    await settle()
    await vi.advanceTimersByTimeAsync(5 * 60_000)
    expect(updates).toHaveLength(1)

    // The non-vacuity half: the import finishes and the CHANGE emits immediately.
    outcome.current = READY
    await vi.advanceTimersByTimeAsync(POLL_CEILING_MS)
    expect(updates).toHaveLength(2)
    expect(updates.at(-1)).toEqual({ panel: 'no-active-deck', decks: ['Boros Aggro'] })

    poller.stop()
  })
})
