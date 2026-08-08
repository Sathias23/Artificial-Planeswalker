/**
 * The reconnect loop's schedule, its ticket discipline, its two-gate escalation and its one
 * dispatch switch (story c5-6, AC 2, AC 3, AC 4, AC 8, AC 11, AC 12, AC 13).
 *
 * `poller.test.ts`'s idiom throughout, because the module under test is written in `poller.ts`'s
 * idiom: EVERY assertion runs on fake timers and nothing sleeps for real time — a suite that
 * waited out a 60-second threshold would take a minute per case and would be deleted by the third
 * person to run it. `vi.setSystemTime(0)` on top of the fake timers is what makes the recorded
 * attempt times readable as offsets rather than as epoch milliseconds.
 *
 * BOTH external effects are INJECTED — the mint and the socket factory — so these tests are about
 * timing, ticket discipline and dispatch and nothing else: what a malformed BODY does is
 * `api/client.test.ts`'s subject, and what the app DOES about a reconnect is `App.test.tsx`'s.
 * The fake socket below is a scriptable object, so no test in this file touches a network, a
 * `WebSocket` constructor or jsdom's socket implementation.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RETRIES_QUIETLY } from '../components/StatePanel/states'
import type { StateKey } from '../components/StatePanel/copy'
import type { AgentSocketHandlers, SessionOutcome } from '../api/client'
import type { AgentEvent } from '../api/schema'
import {
  createAgentSocket,
  DISCONNECTED_AFTER_MS,
  DISCONNECTED_MIN_FAILURES,
  SOCKET_BASE_MS,
  SOCKET_CEILING_MS,
  SOCKET_MULTIPLIER,
  type ConnectionStatus,
  type SystemEventKind,
} from './socket'

const TICKET: SessionOutcome = { kind: 'ticket', ticket: 'a-ticket' }
const UNREACHABLE: SessionOutcome = { kind: 'unreachable' }
const REFUSED: SessionOutcome = { kind: 'error', reason: 'internal_error' }

/** One scriptable socket: what the loop was handed, and the levers a test pulls on it. */
interface FakeSocket {
  readonly ticket: string
  readonly handlers: AgentSocketHandlers
  readonly openedAt: number
  closed: number
}

/**
 * A mint that walks a script (repeating its last entry forever) and records WHEN it was asked and
 * WHAT it handed out, plus a socket factory that records every socket the loop opened.
 *
 * The two are built together because the assertions that matter are about their RELATIONSHIP: a
 * ticket is minted inside an attempt and spent immediately, and the whole of AC 3 is that no
 * ticket ever crosses from one attempt into another.
 */
const driving = (...outcomes: SessionOutcome[]) => {
  const mintedAt: number[] = []
  let handed = 0
  const mint = () => {
    mintedAt.push(Date.now())
    const outcome = outcomes[Math.min(handed, outcomes.length - 1)]
    handed += 1
    // A DISTINCT ticket per mint, so "the same ticket was presented twice" is observable rather
    // than being hidden behind a constant. The real backend does exactly this.
    return Promise.resolve(
      outcome.kind === 'ticket' ? { ...outcome, ticket: `ticket-${handed}` } : outcome,
    )
  }

  const sockets: FakeSocket[] = []
  const open = (ticket: string, handlers: AgentSocketHandlers) => {
    const socket: FakeSocket = { ticket, handlers, openedAt: Date.now(), closed: 0 }
    sockets.push(socket)
    return {
      close: () => {
        socket.closed += 1
      },
    }
  }

  const statuses: ConnectionStatus[] = []
  const events: SystemEventKind[] = []
  let reconnects = 0

  const socket = createAgentSocket({
    onStatus: (status) => statuses.push(status),
    onReconnected: () => {
      reconnects += 1
    },
    onSystemEvent: (kind) => events.push(kind),
    mint,
    open,
  })

  return {
    socket,
    mintedAt,
    sockets,
    statuses,
    events,
    reconnects: () => reconnects,
    /** The socket the loop most recently opened. */
    latest: () => sockets[sockets.length - 1],
  }
}

/** Let the immediate first attempt (a microtask chain, not a timer) settle. */
const settle = () => vi.advanceTimersByTimeAsync(0)

/**
 * One well-formed frame of a given kind, as it crosses the wire.
 *
 * Parameterised by `kind` and carrying an empty payload, which needs no cast: every payload in the
 * generated types is all-optional, so `{}` is a legal member of each. That is the wire being
 * permissive rather than the fixture cheating — and it happens to be exactly the right shape for
 * these tests, because the loop reads `kind` and NOTHING else, which is the property under test.
 */
const frame = (kind: AgentEvent['kind']): AgentEvent => ({
  kind,
  id: `id-${kind}`,
  ts: '2026-08-08T00:00:00Z',
  payload: {},
})

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(0)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('the backoff grows and then STOPS growing (AC 2)', () => {
  it('attempts immediately, then on 2 s, 4 s, 8 s, 16 s and 30 s — and never longer', async () => {
    const { socket, mintedAt } = driving(UNREACHABLE)

    socket.start()
    await settle()
    // No initial wait: a companion that is merely slow to start should be found now, not in two
    // seconds — and a page that opens BEFORE the backend is up is the ordinary dev-loop case.
    expect(mintedAt).toEqual([0])

    // THE GROWTH HALF. Each advance is exactly the delay that should be pending; a shorter one
    // scheduled would record earlier, and a longer one would record nothing at all.
    await vi.advanceTimersByTimeAsync(SOCKET_BASE_MS)
    expect(mintedAt).toEqual([0, 2_000])
    await vi.advanceTimersByTimeAsync(4_000)
    expect(mintedAt).toEqual([0, 2_000, 6_000])
    await vi.advanceTimersByTimeAsync(8_000)
    expect(mintedAt).toEqual([0, 2_000, 6_000, 14_000])
    await vi.advanceTimersByTimeAsync(16_000)
    expect(mintedAt).toEqual([0, 2_000, 6_000, 14_000, 30_000])

    // THE CLAMP HALF, from the same schedule. 16 s × 2 is 32 s and the next gap is 30 s; an
    // unclamped backoff would be silent here and for the two hours after it, while every "it
    // retries" assertion above stayed green.
    await vi.advanceTimersByTimeAsync(SOCKET_CEILING_MS)
    expect(mintedAt).toEqual([0, 2_000, 6_000, 14_000, 30_000, 60_000])
    await vi.advanceTimersByTimeAsync(SOCKET_CEILING_MS)
    expect(mintedAt).toEqual([0, 2_000, 6_000, 14_000, 30_000, 60_000, 90_000])

    socket.stop()
  })

  it('multiplies rather than adding — the arithmetic the constants claim', () => {
    expect(SOCKET_BASE_MS * SOCKET_MULTIPLIER).toBe(4_000)
    expect(SOCKET_BASE_MS * SOCKET_MULTIPLIER ** 4).toBeGreaterThan(SOCKET_CEILING_MS)
  })

  it('resets to the base after a successful connection, not to wherever it had grown', async () => {
    const { socket, mintedAt, latest } = driving(UNREACHABLE, UNREACHABLE, UNREACHABLE, TICKET)

    socket.start()
    await settle()
    await vi.advanceTimersByTimeAsync(SOCKET_BASE_MS) // 2 s
    await vi.advanceTimersByTimeAsync(4_000) // 6 s
    await vi.advanceTimersByTimeAsync(8_000) // 14 s — this one mints a ticket
    latest().handlers.onOpen()

    // …then it drops again. The next retry must be 2 s later, not 16 s: an inherited ceiling
    // would make a second brief outage feel eight times worse than the first for no reason.
    latest().handlers.onClose()
    await vi.advanceTimersByTimeAsync(SOCKET_BASE_MS)

    expect(mintedAt).toEqual([0, 2_000, 6_000, 14_000, 16_000])

    socket.stop()
  })
})

describe('every attempt mints a FRESH ticket, and the order is delay → mint → open (AC 3)', () => {
  it('mints once per attempt and never presents the same ticket twice', async () => {
    const { socket, sockets, mintedAt } = driving(TICKET)

    socket.start()
    await settle()
    sockets[0].handlers.onClose()
    await vi.advanceTimersByTimeAsync(SOCKET_BASE_MS)
    sockets[1].handlers.onClose()
    await vi.advanceTimersByTimeAsync(4_000)

    // `test_ws.py:129-137` is annotated as this story's shape and this is it, from the browser
    // side: mint, upgrade, mint, upgrade — three times over.
    expect(mintedAt).toHaveLength(3)
    expect(sockets.map((s) => s.ticket)).toEqual(['ticket-1', 'ticket-2', 'ticket-3'])
    // The assertion that actually says "never reused", rather than "happened to differ".
    expect(new Set(sockets.map((s) => s.ticket)).size).toBe(sockets.length)

    socket.stop()
  })

  it('mints INSIDE the attempt, so a ceiling-length wait never ages a ticket (the TTL interlock)', async () => {
    // THE LANDMINE THIS FILE EXISTS TO PIN. The ticket TTL is 30 s (`state.py:163`) and the
    // backoff ceiling is 30 s, so `mint → delay → open` would hand every upgrade at the ceiling a
    // ticket that had spent its entire life in a `setTimeout`. The observable difference is the
    // GAP between the mint and the open: it must be zero at every point in the schedule,
    // including at the ceiling, where a pre-delay mint would make it exactly 30 s.
    const { socket, sockets, mintedAt } = driving(TICKET)

    socket.start()
    await settle()
    for (let n = 0; n < 6; n += 1) {
      sockets[sockets.length - 1].handlers.onClose()
      await vi.advanceTimersByTimeAsync(SOCKET_CEILING_MS)
    }

    expect(sockets).toHaveLength(7)
    for (const [index, opened] of sockets.entries()) {
      expect(opened.openedAt - mintedAt[index]).toBe(0)
    }
    // …and the last two really are a full ceiling apart, so the loop above reached the clamp and
    // the zero-gap claim is not being made about six attempts inside the first ten seconds.
    expect(sockets[6].openedAt - sockets[5].openedAt).toBe(SOCKET_CEILING_MS)

    socket.stop()
  })

  it('re-mints after a REFUSED mint too, not just an unreachable one', async () => {
    // `session.py` declares no failure path at all, so an `error` here means something that is
    // not the companion answered on the port. It is still just a failed attempt.
    const { socket, mintedAt, sockets } = driving(REFUSED, TICKET)

    socket.start()
    await settle()
    expect(sockets).toHaveLength(0)

    await vi.advanceTimersByTimeAsync(SOCKET_BASE_MS)
    expect(mintedAt).toEqual([0, 2_000])
    expect(sockets).toHaveLength(1)

    socket.stop()
  })
})

describe('the generation counter survives every await and every callback (AC 4)', () => {
  it('drops a mint that was in flight when the loop stopped', async () => {
    let release: (outcome: SessionOutcome) => void = () => undefined
    const sockets: { ticket: string }[] = []
    const socket = createAgentSocket({
      onStatus: () => undefined,
      onReconnected: () => undefined,
      onSystemEvent: () => undefined,
      mint: () => new Promise<SessionOutcome>((resolve) => (release = resolve)),
      open: (ticket) => {
        sockets.push({ ticket })
        return { close: () => undefined }
      },
    })

    socket.start()
    await settle()
    socket.stop()
    // The answer lands AFTER the stop. A `live` boolean would be enough here; the next test is
    // the one it cannot survive.
    release(TICKET)
    await settle()

    expect(sockets).toHaveLength(0)
  })

  it('drops a mint from a loop that was stopped AND restarted — the boolean cannot see this', async () => {
    const answers: ((outcome: SessionOutcome) => void)[] = []
    const sockets: { ticket: string }[] = []
    const socket = createAgentSocket({
      onStatus: () => undefined,
      onReconnected: () => undefined,
      onSystemEvent: () => undefined,
      mint: () => new Promise<SessionOutcome>((resolve) => answers.push(resolve)),
      open: (ticket) => {
        sockets.push({ ticket })
        return { close: () => undefined }
      },
    })

    socket.start()
    await settle()
    socket.stop()
    socket.start()
    await settle()

    expect(answers).toHaveLength(2)
    // The FIRST attempt's answer settles second, into a world where `live` is true again.
    answers[1]({ kind: 'ticket', ticket: 'the-live-one' })
    answers[0]({ kind: 'ticket', ticket: 'the-abandoned-one' })
    await settle()

    expect(sockets.map((s) => s.ticket)).toEqual(['the-live-one'])

    socket.stop()
  })

  it('schedules ONCE when a browser dispatches error and then close for the same socket', async () => {
    // A real browser fires `error` then `close` on a refused handshake, and `client.ts`
    // deliberately routes both to the same callback WITHOUT suppressing the second — the
    // generation bump inside the failure path is the one mechanism that answers it. Without that
    // bump this is two timer chains from one drop, polling at double rate forever, and the next
    // `stop()` (which clears one `timer` slot) could never fully cancel it.
    // The first attempt gets a socket to double-close; every later mint is unreachable, so the
    // chain sustains itself and a SECOND chain would show up as an extra entry rather than as a
    // schedule that merely looks right.
    const { socket, mintedAt, latest } = driving(TICKET, UNREACHABLE)

    socket.start()
    await settle()
    latest().handlers.onClose()
    latest().handlers.onClose()

    await vi.advanceTimersByTimeAsync(SOCKET_BASE_MS)
    expect(mintedAt).toEqual([0, 2_000])
    // …and still one chain a full schedule later, which is where a doubled one would be obvious:
    // two chains from one drop would both be due at 4 s and 6 s from here.
    await vi.advanceTimersByTimeAsync(4_000)
    expect(mintedAt).toEqual([0, 2_000, 6_000])
    await vi.advanceTimersByTimeAsync(8_000)
    expect(mintedAt).toEqual([0, 2_000, 6_000, 14_000])

    socket.stop()
  })

  it('ignores a frame from a socket the loop has already abandoned', async () => {
    const { socket, sockets, events, latest } = driving(TICKET)

    socket.start()
    await settle()
    const stale = latest()
    stale.handlers.onClose()
    await vi.advanceTimersByTimeAsync(SOCKET_BASE_MS)
    expect(sockets).toHaveLength(2)

    stale.handlers.onMessage(frame('deck_changed'))
    expect(events).toEqual([])

    // …and the CURRENT socket's frame is still delivered, so this is a generation check rather
    // than a dispatch that stopped working.
    latest().handlers.onMessage(frame('deck_changed'))
    expect(events).toEqual(['deck_changed'])

    socket.stop()
  })

  it('closes the socket it holds when it stops, and re-connects from scratch on restart', async () => {
    const { socket, sockets, mintedAt, latest } = driving(TICKET)

    socket.start()
    await settle()
    latest().handlers.onOpen()
    socket.stop()
    expect(sockets[0].closed).toBe(1)

    socket.start()
    await settle()
    expect(mintedAt).toEqual([0, 0])
    expect(sockets).toHaveLength(2)

    socket.stop()
  })
})

describe('"exhausted" is TWO gates, and it is an announcement rather than a stop (AC 8; Q2)', () => {
  it('shows nothing until BOTH sixty seconds and four failures have passed', async () => {
    const { socket, statuses } = driving(UNREACHABLE)

    socket.start()
    await settle()
    // One failure at t=0. Neither gate is satisfied, and the status the app sees is the calm one:
    // a backend restart takes a second or two and must never flash a whole-screen panel.
    expect(statuses).toEqual([])
    expect(Date.now()).toBe(0)

    // t = 2, 6, 14, 30 s — four more failures, five in total, but only 30 s elapsed.
    await vi.advanceTimersByTimeAsync(30_000)
    expect(statuses).toEqual([])

    // t = 60 s. Now both gates are true, and this is the first status the loop has emitted at
    // all — `reconnecting` was already the initial value, so emit-on-change said nothing.
    await vi.advanceTimersByTimeAsync(30_000)
    expect(Date.now()).toBe(DISCONNECTED_AFTER_MS)
    expect(statuses).toEqual(['down'])

    socket.stop()
  })

  it('will not announce on a clock that moved while the schedule was frozen', async () => {
    // THE REASON `DISCONNECTED_MIN_FAILURES` EXISTS, made observable. `Date.now()` is wall time
    // and keeps counting through a laptop sleep or a throttled background tab while `setTimeout`
    // does not — so without the observation floor, two failures bracketing a nap satisfy "sixty
    // seconds of continuous failure" and the panel announces a lost backend to somebody who
    // merely closed their lid.
    const { socket, statuses } = driving(UNREACHABLE)

    socket.start()
    await settle()
    // The lid closes. The clock jumps an hour; no timer runs.
    vi.setSystemTime(60 * 60_000)

    // Two more failures on waking. Elapsed is now an hour — the first gate is wide open — and the
    // status is still calm, because only three failures have ever been OBSERVED.
    await vi.advanceTimersByTimeAsync(SOCKET_BASE_MS)
    await vi.advanceTimersByTimeAsync(4_000)
    expect(statuses).toEqual([])

    // The fourth observation is the one that speaks.
    await vi.advanceTimersByTimeAsync(8_000)
    expect(statuses).toEqual(['down'])
    expect(DISCONNECTED_MIN_FAILURES).toBe(4)

    socket.stop()
  })

  it('KEEPS RETRYING behind the panel — the whole point of AC 9', async () => {
    const { socket, statuses, mintedAt } = driving(UNREACHABLE)

    socket.start()
    await settle()
    await vi.advanceTimersByTimeAsync(DISCONNECTED_AFTER_MS)
    expect(statuses).toEqual(['down'])

    // Ten more minutes behind the panel, at the 30 s ceiling: twenty further attempts. A loop
    // that treated "exhausted" as a STOP would sit here forever and the page would need a
    // reload — which is the exact defect three ledger entries record and this story exists to
    // kill. `RETRIES_QUIETLY.disconnected` is `true` and this is what that costs.
    const attempts = mintedAt.length
    await vi.advanceTimersByTimeAsync(10 * 60_000)
    expect(mintedAt.length).toBe(attempts + 20)

    socket.stop()
  })

  it('FOLLOWS `RETRIES_QUIETLY` rather than paraphrasing it — flip the entry and behaviour moves', async () => {
    // The assertion that separates "consults the contract" from "happens to agree with it
    // today", and the one `copy-tails.test.ts` declined at c3-9 for want of a mechanism to check
    // against. A loop carrying its own "always retry" rule passes every other test in this file
    // and fails this one.
    const original = RETRIES_QUIETLY.disconnected
    try {
      // The cast is the assertion, not a workaround: `satisfies` preserves the LITERAL type, so
      // `RETRIES_QUIETLY.disconnected` is typed `true` and the compiler refuses the flip.
      ;(RETRIES_QUIETLY as Record<StateKey, boolean>).disconnected = false

      const { socket, statuses, mintedAt } = driving(UNREACHABLE)
      socket.start()
      await settle()
      await vi.advanceTimersByTimeAsync(DISCONNECTED_AFTER_MS)
      expect(statuses).toEqual(['down'])

      const attempts = mintedAt.length
      await vi.advanceTimersByTimeAsync(10 * 60_000)
      expect(mintedAt.length).toBe(attempts)

      socket.stop()
    } finally {
      ;(RETRIES_QUIETLY as Record<StateKey, boolean>).disconnected = original
    }
    // …and restored, so the shipped contract is not silently disabled for whatever runs next.
    expect(RETRIES_QUIETLY.disconnected).toBe(true)
  })

  it('clears the announcement the moment a socket comes back (AC 9)', async () => {
    const { socket, statuses, latest } = driving(
      UNREACHABLE,
      UNREACHABLE,
      UNREACHABLE,
      UNREACHABLE,
      UNREACHABLE,
      UNREACHABLE,
      TICKET,
    )

    socket.start()
    await settle()
    await vi.advanceTimersByTimeAsync(DISCONNECTED_AFTER_MS)
    expect(statuses).toEqual(['down'])

    await vi.advanceTimersByTimeAsync(SOCKET_CEILING_MS)
    latest().handlers.onOpen()

    // No reload, no remount, no second mechanism: the same loop that announced the loss withdraws
    // it. The `reconnecting` in between is never emitted, because the open follows the failure
    // directly — the loop goes straight from `down` to `live`.
    expect(statuses).toEqual(['down', 'live'])

    socket.stop()
  })
})

describe('the status is emitted on CHANGE only', () => {
  it('says nothing at all while a healthy socket stays open', async () => {
    const { socket, statuses, latest } = driving(TICKET)

    socket.start()
    await settle()
    latest().handlers.onOpen()
    expect(statuses).toEqual(['live'])

    latest().handlers.onMessage(frame('deck_changed'))
    latest().handlers.onMessage(frame('suggestions'))
    await vi.advanceTimersByTimeAsync(10 * 60_000)

    // One emission for the whole session. The system store is subscribed selector-less in `App`,
    // so every write re-renders the entire tree — a loop that re-emitted its status would repaint
    // the app for saying the same thing.
    expect(statuses).toEqual(['live'])

    socket.stop()
  })

  it('does not re-announce `down` on every further failure', async () => {
    const { socket, statuses } = driving(UNREACHABLE)

    socket.start()
    await settle()
    await vi.advanceTimersByTimeAsync(DISCONNECTED_AFTER_MS + 10 * 60_000)

    expect(statuses).toEqual(['down'])

    socket.stop()
  })

  it('reports `reconnecting` when a LIVE socket drops, which is a real change', async () => {
    const { socket, statuses, latest } = driving(TICKET)

    socket.start()
    await settle()
    latest().handlers.onOpen()
    latest().handlers.onClose()

    expect(statuses).toEqual(['live', 'reconnecting'])

    socket.stop()
  })
})

describe('the reconnect signal fires on a RE-connect, never on the first one (AC 5)', () => {
  it('says nothing when the very first socket of the tab opens', async () => {
    const { socket, reconnects, latest } = driving(TICKET)

    socket.start()
    await settle()
    latest().handlers.onOpen()

    // The boot has already run by now; re-driving here would double every cold open's request
    // count for nothing, and `App.test.tsx`'s "boots exactly once" pins that number.
    expect(reconnects()).toBe(0)

    socket.stop()
  })

  it('fires when a socket opens after a drop', async () => {
    const { socket, reconnects, latest } = driving(TICKET)

    socket.start()
    await settle()
    latest().handlers.onOpen()
    latest().handlers.onClose()
    await vi.advanceTimersByTimeAsync(SOCKET_BASE_MS)
    latest().handlers.onOpen()

    expect(reconnects()).toBe(1)

    socket.stop()
  })

  it('fires when the FIRST attempt failed and the second succeeded', async () => {
    // The cold-open-against-a-dead-backend case, and it is deliberately on the firing side: a
    // boot that raced a backend which was not up yet has a stale answer worth replacing.
    const { socket, reconnects, latest } = driving(UNREACHABLE, TICKET)

    socket.start()
    await settle()
    await vi.advanceTimersByTimeAsync(SOCKET_BASE_MS)
    latest().handlers.onOpen()

    expect(reconnects()).toBe(1)

    socket.stop()
  })
})

describe('ONE total switch over the six-kind closed enum (AC 11, AC 12, AC 13)', () => {
  const open = async () => {
    const driver = driving(TICKET)
    driver.socket.start()
    await settle()
    driver.latest().handlers.onOpen()
    return driver
  }

  it('reports the two system kinds, separately', async () => {
    const { socket, events, latest } = await open()

    latest().handlers.onMessage(frame('active_deck_changed'))
    latest().handlers.onMessage(frame('deck_changed'))

    // Kept apart on the way through, because `contracts.py:902-905` is emphatic that conflating
    // them is the interesting bug — a client that does refetches the deck it is LEAVING.
    expect(events).toEqual(['active_deck_changed', 'deck_changed'])

    socket.stop()
  })

  it('costs one report per duplicate `active_deck_changed`, and nothing else (AC 12)', async () => {
    // The backend fires this on EVERY `PUT /api/active-deck`, including a redundant re-set of the
    // deck that is already active (`ws.py:409-444`). Three identical frames are three idempotent
    // refetches — not a crash, not a loop, not a growing queue.
    const { socket, events, statuses, latest } = await open()

    latest().handlers.onMessage(frame('active_deck_changed'))
    latest().handlers.onMessage(frame('active_deck_changed'))
    latest().handlers.onMessage(frame('active_deck_changed'))

    expect(events).toEqual(['active_deck_changed', 'active_deck_changed', 'active_deck_changed'])
    // …and the connection was never disturbed by any of it.
    expect(statuses).toEqual(['live'])
    expect(latest().closed).toBe(0)

    socket.stop()
  })

  it('receives and DROPS the four agent-view kinds, without treating them as faults', async () => {
    const { socket, events, statuses, latest } = await open()

    for (const kind of ['suggestions', 'swaps', 'tier_list', 'groups'] as const) {
      latest().handlers.onMessage(frame(kind))
    }

    // Epic 6 builds the views these carry. Until it does, a push is a well-formed message about a
    // surface that does not exist yet — and treating a VALID frame as malformed would make the
    // agent's pushes look like a wire fault to whoever debugs c6-x.
    expect(events).toEqual([])
    expect(statuses).toEqual(['live'])
    expect(latest().closed).toBe(0)

    socket.stop()
  })

  it('ignores a frame this build cannot read, and keeps the socket open (AC 13)', async () => {
    const { socket, events, statuses, latest } = await open()

    // `null` is what `client.ts`'s narrower hands over for non-JSON, an unknown `kind` and the
    // wrong shape alike — three inputs, one answer, because the loop's response to all three is
    // the same. A malformed frame says nothing about the CONNECTION.
    latest().handlers.onMessage(null)
    latest().handlers.onMessage(null)

    expect(events).toEqual([])
    expect(statuses).toEqual(['live'])
    expect(latest().closed).toBe(0)

    // …and a good frame after two bad ones is still delivered, so "ignored" is not "stopped".
    latest().handlers.onMessage(frame('deck_changed'))
    expect(events).toEqual(['deck_changed'])

    socket.stop()
  })
})

describe('the loop survives a socket factory that fails outright', () => {
  it('treats a throwing constructor as one failed attempt and backs off', async () => {
    const mintedAt: number[] = []
    const statuses: ConnectionStatus[] = []
    const socket = createAgentSocket({
      onStatus: (status) => statuses.push(status),
      onReconnected: () => undefined,
      onSystemEvent: () => undefined,
      mint: () => {
        mintedAt.push(Date.now())
        return Promise.resolve(TICKET)
      },
      open: () => {
        // A malformed URL, or a runtime with no socket support at all. Neither is fixed by
        // retrying — but neither is worth a branch either: the loop backs off, which costs one
        // attempt per ceiling and leaves the Disconnected panel saying the true thing.
        throw new TypeError('no socket here')
      },
    })

    socket.start()
    await settle()
    await vi.advanceTimersByTimeAsync(DISCONNECTED_AFTER_MS)

    expect(mintedAt).toEqual([0, 2_000, 6_000, 14_000, 30_000, 60_000])
    expect(statuses).toEqual(['down'])

    socket.stop()
  })
})
