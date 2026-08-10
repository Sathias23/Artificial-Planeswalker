import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import {
  INITIAL_AGENT_VIEW,
  closeAgentView,
  openAgentView,
  openViewOf,
  resetAgentView,
  useAgentViewStore,
  useOpenAgentView,
} from './agentView'

/**
 * The agent-view slice (story c6-5, AC 5, AC 6).
 *
 * ================= WHAT THIS SUITE CANNOT CARRY, SAID FIRST ============================
 *
 * Nothing here renders the shell, so nothing here proves that pressing Esc closes anything —
 * that is `AgentView.test.tsx`'s wiring claim, and `App.test.tsx`'s end-to-end one. What this
 * file proves is the STATE contract the three dismissal gestures all funnel into: that closing
 * writes one field, that the field it does not write is the content, and that the shape admits
 * one view rather than a stack.
 *
 * AC 6 ("nothing opens over an open view") is carried here as a TYPE claim plus the replacement
 * behaviour below, because the alternative — a stack that this store refuses to push onto — is
 * not expressible: `content` is one nullable slot, so there is no second level for a test to
 * fail to create. That is the intended reading (see the module header), and it is why the
 * assertion below is about REPLACEMENT rather than about a rejected second open.
 */

// The store is module-scope, as stores are; without this a view left open by one test is what
// the next one starts from.
afterEach(resetAgentView)

const SUGGESTIONS = { title: 'Suggestions', count: 3 } as const
const TIERS = { title: 'Card tiers', count: 12 } as const

/**
 * The slot's answer, read without rendering a component.
 *
 * Deliberately NOT named `use…`: it is the plain selector applied to a snapshot, and a `use`
 * prefix would make `react-hooks` read every call below as a hook call outside a component.
 */
const openViewNow = () => openViewOf(useAgentViewStore.getState())

describe('the session starts with nothing to show', () => {
  it('is closed and holds no content', () => {
    expect(useAgentViewStore.getState()).toEqual(INITIAL_AGENT_VIEW)
    expect(useAgentViewStore.getState().status).toBe('closed')
    expect(useAgentViewStore.getState().content).toBeNull()
  })

  it('resolves the overlay slot to nothing, which is what App must pass as ABSENT', () => {
    // `null` here is what `App.tsx` turns into an omitted `overlay` prop rather than a falsy
    // one — `AppShell.tsx:134-139`'s click-swallower warning is about exactly that difference.
    const { result } = renderHook(() => useOpenAgentView())
    expect(result.current).toBeNull()
  })
})

describe('opening shows the pushed content (AC 6)', () => {
  it('writes status and content in one go, so no render sees open-with-stale-content', () => {
    openAgentView(SUGGESTIONS)
    expect(useAgentViewStore.getState()).toEqual({ status: 'open', content: SUGGESTIONS })
  })

  it('resolves the slot to the content the caller passed', () => {
    openAgentView(SUGGESTIONS)
    const { result } = renderHook(() => useOpenAgentView())
    expect(result.current).toBe(SUGGESTIONS)
  })

  it('REPLACES rather than stacks — the scalar is AC 6 in the type (UX-DR38)', () => {
    // The overlay stack is exactly one level deep, permanently. A second open cannot create a
    // second level because there is nowhere to put one; what it does instead is replace, which
    // is also c6-6's replace-in-place contract arriving for free.
    openAgentView(SUGGESTIONS)
    openAgentView(TIERS)
    expect(useAgentViewStore.getState().content).toBe(TIERS)
    expect(openViewNow()).toBe(TIERS)
  })
})

describe('dismissal never clears the content (AC 5, UX-DR34)', () => {
  it('closes by writing STATUS ONLY — the content survives, byte for byte', () => {
    // The whole of UX-DR34: *"dismissal never clears it — the view remains re-openable for the
    // rest of the session"*. zustand's shallow merge is what makes the omission of `content`
    // from `closeAgentView`'s object load-bearing rather than an oversight, so this assertion
    // is what would fail if somebody "tidied" it into `{ status: 'closed', content: null }`.
    openAgentView(SUGGESTIONS)
    closeAgentView()

    expect(useAgentViewStore.getState().status).toBe('closed')
    expect(useAgentViewStore.getState().content).toBe(SUGGESTIONS)
  })

  it('hides the view from the overlay slot while still holding it', () => {
    // The two halves that make "re-openable" real: the slot goes empty (so `App` passes an
    // absent `overlay` and the wrapper does not mount), and the store still has the answer.
    openAgentView(SUGGESTIONS)
    closeAgentView()

    expect(openViewOf(useAgentViewStore.getState())).toBeNull()
    expect(useAgentViewStore.getState().content).toBe(SUGGESTIONS)
  })

  it('re-opens the SAME content with no second push (AC 5)', () => {
    // What "re-openable for the rest of the session" means operationally, and the reason c6-8
    // can build nav pills that re-open a view without asking the agent for anything.
    openAgentView(SUGGESTIONS)
    closeAgentView()
    openAgentView(useAgentViewStore.getState().content!)

    expect(openViewNow()).toBe(SUGGESTIONS)
  })

  it('is idempotent — closing a closed view is a no-op, not an error (clearPin’s idiom)', () => {
    openAgentView(SUGGESTIONS)
    closeAgentView()
    const after = useAgentViewStore.getState()
    closeAgentView()

    expect(useAgentViewStore.getState()).toEqual(after)
  })
})

describe('the test-only reset is the one thing that forgets (non-vacuity)', () => {
  it('clears content, which no production path does', () => {
    // The counterweight to every assertion above: if `resetAgentView` did not really clear,
    // the retention claims would be passing on a store nothing had ever emptied. It is also
    // the proof that the retention is a property of `closeAgentView` specifically rather than
    // of this store being unable to write `null` at all.
    openAgentView(SUGGESTIONS)
    resetAgentView()

    expect(useAgentViewStore.getState()).toEqual(INITIAL_AGENT_VIEW)
    expect(useAgentViewStore.getState().content).toBeNull()
  })
})
