import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { SuggestionsEvent } from '../api/schema'
import {
  INITIAL_AGENT_VIEW,
  SUGGESTIONS_VIEW_TITLE,
  closeAgentView,
  openAgentView,
  openSuggestionsPush,
  openViewOf,
  resetAgentView,
  suggestionsViewOf,
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

const ITEM = { card_id: 'c-1', reason: 'Fills the two-drop gap.' } as const

const SUGGESTIONS = {
  id: 'push-1',
  ts: '2026-08-11T09:15:00Z',
  kind: 'suggestions',
  title: 'Suggestions',
  count: 3,
  items: [ITEM, ITEM, ITEM],
} as const
const TIERS = {
  id: 'push-2',
  ts: '2026-08-11T09:16:00Z',
  kind: 'suggestions',
  title: 'Card tiers',
  count: 12,
  items: [],
} as const

/**
 * A `suggestions` frame, with the payload the caller wants to test and nothing else defaulted.
 *
 * The `payload` parameter is deliberately typed LOOSER than the envelope — `undefined` is not
 * what `SuggestionsEvent` declares, and that is the whole point of the rows below: the wire
 * really can deliver it, because `agentEventOf` validates the `kind` discriminant and nothing
 * else. Casting HERE, in the fixture, keeps the cast out of every assertion and keeps the
 * production signature honest about what the generator says.
 */
const frame = (payload: unknown, id = 'push-1'): SuggestionsEvent =>
  ({ id, ts: '2026-08-11T09:15:00Z', kind: 'suggestions', payload }) as SuggestionsEvent

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
    // second level because there is nowhere to put one; what it does instead is replace. That
    // is the STATE half of c6-6's replace-in-place contract and it is the whole of what this
    // store can claim — the re-focus, the announcement and the crossfade are `AgentView.tsx`'s,
    // keyed on the `id` these two fixtures deliberately differ in.
    openAgentView(SUGGESTIONS)
    openAgentView(TIERS)
    expect(useAgentViewStore.getState().content).toBe(TIERS)
    expect(openViewNow()).toBe(TIERS)
  })
})

describe('one envelope becomes one view, for every payload the wire admits (c6-6, AC 1, AC 4)', () => {
  it('carries the payload through — title, count and the items themselves', () => {
    // THE DELEGATION CLAIM, and the reason it is asserted on real values rather than on a spy:
    // c6-4's planted regression was a builder that ignored its argument and minted an empty
    // shape regardless, which a "was it called" assertion passes with flying colours.
    const content = suggestionsViewOf(
      frame({ title: 'Resilience options', items: [ITEM, ITEM] }, 'push-9'),
    )

    expect(content.title).toBe('Resilience options')
    expect(content.count).toBe(2)
    expect(content.items).toEqual([ITEM, ITEM])
    expect(content.id).toBe('push-9')
    expect(content.kind).toBe('suggestions')
  })

  it('retains `ts` and `id` unread — c6-8’s pill time and this story’s replace key', () => {
    // The two fields nothing in c6-6 renders. They are asserted here because "retained for a
    // later story" is a claim that decays silently: a builder that dropped `ts` would break
    // nothing until c6-8, and by then the diff that dropped it is a year of stories back.
    const content = suggestionsViewOf(frame({ items: [] }, 'push-42'))

    expect(content.ts).toBe('2026-08-11T09:15:00Z')
    expect(content.id).toBe('push-42')
  })

  it('builds an EMPTY view rather than throwing when the payload is absent entirely', () => {
    // `agentEventOf` validates only `kind` (`client.ts:701-716`), so `{"kind":"suggestions"}`
    // reaches this function typed as a full event. A `TypeError` here would be an uncaught
    // exception inside a socket message handler: the socket survives, the store write does not,
    // and the push is silently lost — which is the failure AC 4's "rather than rejecting" is
    // about, arriving through the wire instead of through the agent.
    const content = suggestionsViewOf(frame(undefined))

    expect(content.items).toEqual([])
    expect(content.count).toBe(0)
    expect(content.title).toBe(SUGGESTIONS_VIEW_TITLE)
  })

  it('treats an absent `items` as an empty push — the ORDINARY path, not the malformed one', () => {
    // `SuggestionsPayload.items` is optional in the generated type
    // (`types.d.ts:1108-1111`), so an agent that looked and found nothing sends exactly this.
    const content = suggestionsViewOf(frame({ title: 'Resilience options' }))

    expect(content.items).toEqual([])
    expect(content.count).toBe(0)
    // The title survives the empty items — an empty push is still a NAMED push.
    expect(content.title).toBe('Resilience options')
  })

  it('counts an explicitly empty list as 0 and not as “nothing to count”', () => {
    // `count` is `number | null` and the two mean different things (see the field's docstring).
    // A suggestions push always counts, so `0` must be a real `0` — `null` here would render
    // no count at all and make an empty push look like a view that does not count things.
    const content = suggestionsViewOf(frame({ items: [] }))

    expect(content.count).toBe(0)
    expect(content.count).not.toBeNull()
  })

  it.each([
    ['absent', undefined],
    ['null', null],
    ['empty', ''],
    ['whitespace only', '   '],
  ])('falls back to the authored title when the pushed one is %s', (_label, title) => {
    // `aria-labelledby` points at the heading, so a blank title is a `role="dialog"` with no
    // discernible name — `deferred-work.md`'s entry asks for the guard exactly here, "at the
    // point content is constructed". `'   '` is the row a truthiness check would pass.
    const content = suggestionsViewOf(frame({ title, items: [ITEM] }))

    expect(content.title).toBe(SUGGESTIONS_VIEW_TITLE)
    // NON-VACUITY: the fallback is a real non-blank string rather than an import that resolved
    // to `undefined` and matched an equally-undefined field.
    expect(SUGGESTIONS_VIEW_TITLE.trim()).toBe(SUGGESTIONS_VIEW_TITLE)
    expect(SUGGESTIONS_VIEW_TITLE.length).toBeGreaterThan(0)
  })

  it('keeps a pushed title that merely has whitespace AROUND it, trimmed', () => {
    // The counterweight to the row above: the guard must not eat a real title. Trimming rather
    // than passing through, because leading space in a heading is invisible in a diff and
    // visible on the glass.
    const content = suggestionsViewOf(frame({ title: '  Resilience options  ', items: [] }))

    expect(content.title).toBe('Resilience options')
  })

  it('OPENS the view it builds — the one verb `connection.ts` calls (AC 1)', () => {
    // The auto-open ruling (2026-07-25) with no click anywhere in it. Asserted through the
    // store rather than through the builder, because the verb's whole job is the composition.
    openSuggestionsPush(frame({ title: 'Resilience options', items: [ITEM] }, 'push-7'))

    expect(useAgentViewStore.getState().status).toBe('open')
    expect(openViewNow()).toEqual({
      id: 'push-7',
      ts: '2026-08-11T09:15:00Z',
      kind: 'suggestions',
      title: 'Resilience options',
      count: 1,
      items: [ITEM],
    })
  })

  it('REPLACES a showing view with the newer push, keeping it open (AC 2, state half)', () => {
    openSuggestionsPush(frame({ title: 'First look', items: [ITEM] }, 'push-1'))
    openSuggestionsPush(frame({ title: 'Second look', items: [] }, 'push-2'))

    expect(useAgentViewStore.getState().status).toBe('open')
    expect(openViewNow()?.id).toBe('push-2')
    expect(openViewNow()?.title).toBe('Second look')
  })

  it('OPENS a view that was closed with retained content — a push is never swallowed (SC-1)', () => {
    // The third arrival case, and the one the shell treats differently: this is a MOUNT (bloom,
    // focus, restore-target capture), not a replace. The store cannot tell them apart and does
    // not try — `App.tsx`'s absent-`overlay` conditional is what makes the distinction real.
    openSuggestionsPush(frame({ items: [ITEM] }, 'push-1'))
    closeAgentView()
    expect(openViewNow()).toBeNull()

    openSuggestionsPush(frame({ items: [ITEM, ITEM] }, 'push-2'))

    expect(useAgentViewStore.getState().status).toBe('open')
    expect(openViewNow()?.count).toBe(2)
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
