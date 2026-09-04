/**
 * The composition seam's status wiring, at the seam — the trigger half.
 *
 * `connection.ts` is where the loop's reports are given their meanings, and exactly one of
 * them does two things: `onStatus` writes the status straight through, and a transition to
 * `'live'` ALSO fires the identity refresh. This file mocks the SOCKET FACTORY to capture the
 * handlers `useAgentConnection` wires — the loop's own timing is `socket.test.ts`'s subject, and
 * re-driving it here would test the loop — and mocks the one network door's health reader so the
 * refresh has a wire to answer from. What lands in the store is then asserted for real:
 * `identity.ts` and `systemState.ts` both run un-mocked, so this is the trigger, the guard and
 * the verb proven as one path, which is what the "one trigger point" claim is.
 *
 * `vi.hoisted` for the two seams the factories close over: `vi.mock` is hoisted above the
 * imports, and a plain module-scope `const` would still be in its temporal dead zone when the
 * factory first runs.
 *
 * The full socket-to-glass composition (a REAL socket drop moving the pill) stays
 * `App.test.tsx`'s, exactly as `ConnectionPill.test.tsx`'s header divides it.
 */

import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAgentConnection } from './connection'
import type { AgentSocketOptions } from './socket'
import { INITIAL_SYSTEM_STATE, useSystemStore } from './systemState'

const { captured, readInstanceId } = vi.hoisted(() => {
  /** The handlers the hook wired — set by the mocked factory, read by {@link wired}. */
  const handlers: { options: AgentSocketOptions | null } = { options: null }
  return {
    captured: handlers,
    /** The health read's answer, owned per-test. */
    readInstanceId: vi.fn<() => Promise<string | null>>(),
  }
})

vi.mock('./socket', async (importOriginal) => ({
  // The types and constants come through un-mocked; only the factory is replaced, and it
  // neither connects nor schedules — this file owns the handlers.
  ...(await importOriginal<typeof import('./socket')>()),
  createAgentSocket: vi.fn((options: AgentSocketOptions) => {
    captured.options = options
    return { start: vi.fn(), stop: vi.fn() }
  }),
}))

vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  readInstanceId: (): Promise<string | null> => readInstanceId(),
}))

/** Mount the hook and hand back the handlers it wired. */
const wired = (): AgentSocketOptions => {
  renderHook(() => useAgentConnection())
  const options = captured.options
  if (options === null) throw new Error('useAgentConnection wired no socket')
  return options
}

/** Let the void-fired refresh's microtasks drain. */
const settled = () => new Promise<void>((resolve) => setTimeout(resolve, 0))

beforeEach(() => {
  captured.options = null
  readInstanceId.mockReset()
  readInstanceId.mockResolvedValue(null)
  useSystemStore.setState(INITIAL_SYSTEM_STATE)
})

describe('a transition to live refreshes the confirmed identity ', () => {
  it('still writes every status straight through to the system slice', async () => {
    const { onStatus } = wired()

    onStatus('live')
    expect(useSystemStore.getState().connection).toBe('live')
    onStatus('down')
    expect(useSystemStore.getState().connection).toBe('down')
    await settled()
  })

  it('reads and stores the instance id on the FIRST transition to live', async () => {
    readInstanceId.mockResolvedValue('abc')
    const { onStatus } = wired()

    onStatus('live')
    await settled()

    expect(readInstanceId).toHaveBeenCalledTimes(1)
    expect(useSystemStore.getState().instanceId).toBe('abc')
  })

  it('refreshes again on EVERY return to live — reconnects included, one trigger point', async () => {
    // The socket emits on change only, so `'live'` fires exactly once per (re)connection —
    // which is why the trigger is the status and not `onReconnected` (the first connect needs
    // the id too). A restarted backend's new id lands with no reload.
    readInstanceId.mockResolvedValueOnce('old-process').mockResolvedValueOnce('new-process')
    const { onStatus } = wired()

    onStatus('live')
    await settled()
    onStatus('reconnecting')
    onStatus('live')
    await settled()

    expect(readInstanceId).toHaveBeenCalledTimes(2)
    expect(useSystemStore.getState().instanceId).toBe('new-process')
  })

  it('does NOT read health on reconnecting or down — transitions to live only, never a poll', async () => {
    const { onStatus } = wired()

    onStatus('reconnecting')
    onStatus('down')
    await settled()

    expect(readInstanceId).not.toHaveBeenCalled()
  })

  it('leaves the last-confirmed id standing when the refresh gets no answer', async () => {
    readInstanceId.mockResolvedValueOnce('abc').mockResolvedValueOnce(null)
    const { onStatus } = wired()

    onStatus('live')
    await settled()
    onStatus('down')
    onStatus('live')
    await settled()

    expect(useSystemStore.getState().instanceId).toBe('abc')
  })
})
