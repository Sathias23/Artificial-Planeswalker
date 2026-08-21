import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { SuggestionsEvent, SwapsEvent } from '../api/schema'
import {
  AGENT_VIEW_LABELS,
  type AgentViewContent,
  INITIAL_AGENT_VIEW,
  SUGGESTIONS_VIEW_TITLE,
  closeAgentView,
  openAgentView,
  openSuggestionsPush,
  openSwapsPush,
  openViewOf,
  reopenAgentView,
  resetAgentView,
  suggestionsViewOf,
  swapsViewOf,
  useAgentViewIsOpen,
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
  it('writes the WHOLE slice in one go, so no render sees open-with-stale-content', () => {
    // Kept as a whole-state `toEqual` at c6-8 rather than relaxed to `toMatchObject`, and that
    // is the point of it: this is the one assertion in the file that fails when the slice grows
    // a field, which is exactly the notice a reader wants when a story extends a store. It grew
    // by two here — `retained` and `unread` — and both are written in the SAME `setState` as
    // `status` and `content`, which is the claim this test has always made.
    openAgentView(SUGGESTIONS)
    expect(useAgentViewStore.getState()).toEqual({
      status: 'open',
      content: SUGGESTIONS,
      retained: { suggestions: SUGGESTIONS },
      unread: {},
    })
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

// =========================================================================================
// STORY 16.1 — the second builder, in the first one's exact harness
// =========================================================================================

const SWAP = {
  out_card_id: 'c-out',
  in_card_id: 'c-in',
  rationale: 'Same role, one turn earlier.',
  out_qty: 2,
  in_qty: 0,
} as const

/** A `swaps` frame, cast for the fixture's reason above: the wire really can omit `payload`. */
const swapsFrame = (payload: unknown, id = 'push-s1'): SwapsEvent =>
  ({ id, ts: '2026-08-21T09:15:00Z', kind: 'swaps', payload }) as SwapsEvent

describe('one swaps envelope becomes one view, for every payload the wire admits (16.1)', () => {
  it('carries the payload through — title, count and the items themselves', () => {
    const content = swapsViewOf(swapsFrame({ title: 'Cheaper removal', items: [SWAP] }, 'push-9'))

    expect(content.title).toBe('Cheaper removal')
    expect(content.count).toBe(1)
    expect(content.items).toEqual([SWAP])
    expect(content.id).toBe('push-9')
    expect(content.kind).toBe('swaps')
    expect(content.ts).toBe('2026-08-21T09:15:00Z')
  })

  it('builds an EMPTY view rather than throwing when the payload is absent entirely', () => {
    // `agentEventOf` validates only `kind`, so `{"kind":"swaps"}` reaches this function typed
    // as a full event — the same totality claim `suggestionsViewOf` carries, on the second arm.
    const content = swapsViewOf(swapsFrame(undefined))

    expect(content.items).toEqual([])
    expect(content.count).toBe(0)
    expect(content.title).toBe(AGENT_VIEW_LABELS.swaps)
  })

  it.each([
    ['absent', undefined],
    ['null', null],
    ['empty', ''],
    ['whitespace only', '   '],
  ])('falls back to the table’s word when the pushed title is %s', (_label, title) => {
    // The dialog's accessible name guard, "at the point content is constructed" — and the
    // fallback is the SAME word the nav pill carries, one owner for the kind's word.
    const content = swapsViewOf(swapsFrame({ title, items: [SWAP] }))

    expect(content.title).toBe(AGENT_VIEW_LABELS.swaps)
  })

  it('keeps a pushed title that merely has whitespace around it, trimmed', () => {
    const content = swapsViewOf(swapsFrame({ title: '  Cheaper removal  ', items: [] }))

    expect(content.title).toBe('Cheaper removal')
  })

  it('counts an explicitly empty list as 0 and not as “nothing to count”', () => {
    const content = swapsViewOf(swapsFrame({ items: [] }))

    expect(content.count).toBe(0)
    expect(content.count).not.toBeNull()
  })

  it('OPENS the view it builds — the second verb `connection.ts` calls', () => {
    openSwapsPush(swapsFrame({ title: 'Cheaper removal', items: [SWAP] }, 'push-7'))

    expect(useAgentViewStore.getState().status).toBe('open')
    expect(openViewNow()).toEqual({
      id: 'push-7',
      ts: '2026-08-21T09:15:00Z',
      kind: 'swaps',
      title: 'Cheaper removal',
      count: 1,
      items: [SWAP],
    })
    expect(useAgentViewStore.getState().retained.swaps).toBe(openViewNow())
  })

  it('DISPLACES an open suggestions view and marks it unread — through the wire verb', () => {
    // c6-8 proved displacement with a synthetic second kind because no wire path could reach
    // it; 16.1 is the story that makes the traversal real, so it is re-proven here through the
    // production verb rather than a hand-built content object.
    openSuggestionsPush(frame({ items: [ITEM] }))
    openSwapsPush(swapsFrame({ items: [SWAP] }))

    expect(openViewNow()).toMatchObject({ kind: 'swaps' })
    expect(useAgentViewStore.getState().unread).toEqual({ suggestions: true })
    expect(useAgentViewStore.getState().retained.suggestions).toBeDefined()
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

// =========================================================================================
// STORY c6-8 — per-kind retention, the unread state machine, and re-open
// =========================================================================================

/**
 * A view of any kind, including the three the socket still refuses to deliver.
 *
 * **The synthetic second kind is this story's central honesty, not a shortcut.** Q1 ruled that
 * the nav, the store and the vocabulary go fully four-kind generic while the SOCKET keeps
 * dropping `swaps`/`tier_list`/`groups` at its dispatch switch — because Epic 9 pairs each tool
 * with its view precisely so a push never arrives that the UI cannot display, and accepting one
 * early would recreate that bug from the other side. So AC 5's displacement cannot be reached
 * from production code until Story 9.1 ships, and it is proven HERE, at the seam that owns it,
 * with a second kind constructed by hand. That is the c6-6 AC-3 structural-deferral precedent:
 * the mechanism is built and tested in the story that owns it, and its first production
 * traversal belongs to the story whose own acceptance criterion already banks on it.
 *
 * No cast is needed for the kind itself — `AgentViewContent['kind']` widened to the real
 * four-member union in this story, so `'swaps'` is a legal value of a legal type. What is
 * synthetic is only that nothing on the wire can currently produce one.
 */
const viewOf = (kind: AgentViewContent['kind'], id = `push-${kind}`): AgentViewContent => ({
  id,
  ts: '2026-08-12T14:32:00Z',
  kind,
  title: AGENT_VIEW_LABELS[kind],
  count: 0,
  // `[]` is a legal member of EVERY arm of 16.1's discriminated union, which is what lets this
  // fixture stay computed-kind generic with no cast.
  items: [],
})

describe('the pill vocabulary is one table with one owner (c6-8, Task 2)', () => {
  it('names all four kinds, in the enum’s order', () => {
    // The order is load-bearing: `AgentViewsNav` derives the pill order from this table's keys
    // rather than authoring it a second time (Q3), so a reordering here reorders the header.
    expect(Object.keys(AGENT_VIEW_LABELS)).toEqual(['suggestions', 'swaps', 'tier_list', 'groups'])
  })

  it('is where the fallback title now comes from — one word, one owner', () => {
    // c6-6's review kept `SUGGESTIONS_VIEW_TITLE` in this module explicitly AS the c6-8
    // precedent. This is that precedent honoured rather than a second copy of the word.
    expect(SUGGESTIONS_VIEW_TITLE).toBe(AGENT_VIEW_LABELS.suggestions)
    expect(suggestionsViewOf(frame({}))).toMatchObject({ title: AGENT_VIEW_LABELS.suggestions })
  })

  it('holds four DISTINCT words (non-vacuity)', () => {
    // A collapsed table — a copy-paste, a widened type erasing the literals — would make the
    // assertion above and the nav's order assertion pass for the wrong reason.
    expect(new Set(Object.values(AGENT_VIEW_LABELS)).size).toBe(4)
  })
})

describe('a push is retained under its own kind (c6-8, AC 4)', () => {
  it('files the content in `retained` beside `content`, as the SAME object', () => {
    openAgentView(SUGGESTIONS)

    expect(useAgentViewStore.getState().retained.suggestions).toBe(SUGGESTIONS)
    // The same reference, not a copy — which is what makes AC 4's "the same content" an
    // identity rather than a deep comparison, and what makes it impossible for the map and the
    // glass to disagree.
    expect(useAgentViewStore.getState().content).toBe(SUGGESTIONS)
  })

  it('retains nothing for a kind that has not pushed (non-vacuity)', () => {
    openAgentView(SUGGESTIONS)

    expect(useAgentViewStore.getState().retained.swaps).toBeUndefined()
    expect(useAgentViewStore.getState().retained.tier_list).toBeUndefined()
    expect(useAgentViewStore.getState().retained.groups).toBeUndefined()
  })

  it('keeps ONE view per kind — the newest replaces the older (c6-6’s replace, from the map)', () => {
    openAgentView(SUGGESTIONS)
    openAgentView(TIERS)

    expect(useAgentViewStore.getState().retained.suggestions).toBe(TIERS)
    expect(Object.keys(useAgentViewStore.getState().retained)).toEqual(['suggestions'])
  })

  it('accumulates kinds and never drops one, including across a dismissal', () => {
    openAgentView(SUGGESTIONS)
    openAgentView(viewOf('swaps'))
    closeAgentView()

    // "Re-openable for the rest of the session" (UX-DR34) is exactly this map not shrinking —
    // including across a dismissal, the gesture most likely to be given a tidy-up.
    expect(Object.keys(useAgentViewStore.getState().retained).sort()).toEqual([
      'suggestions',
      'swaps',
    ])
  })

  it('writes a NEW map object, so a subscriber re-renders', () => {
    openAgentView(SUGGESTIONS)
    const first = useAgentViewStore.getState().retained
    openAgentView(viewOf('swaps'))

    // zustand compares slices by reference; a map mutated in place would leave every pill
    // showing its previous state with no test noticing.
    expect(useAgentViewStore.getState().retained).not.toBe(first)
  })
})

describe('unread has exactly one setter, and it is displacement (c6-8, AC 5)', () => {
  it('marks NOTHING unread on the first push of a session', () => {
    openAgentView(SUGGESTIONS)

    expect(useAgentViewStore.getState().unread).toEqual({})
  })

  it('marks the DISPLACED kind unread when a different kind arrives over an open view', () => {
    openAgentView(SUGGESTIONS)
    openAgentView(viewOf('swaps'))

    // AC 5, and the whole of "a push is never silently swallowed": the suggestions view is no
    // longer on the glass, and the person is told where it went.
    expect(useAgentViewStore.getState().unread).toEqual({ suggestions: true })
    expect(openViewNow()).toMatchObject({ kind: 'swaps' })
    // …and the displaced view is still there to go back to.
    expect(useAgentViewStore.getState().retained.suggestions).toBe(SUGGESTIONS)
  })

  it('does NOT mark the same kind unread — c6-6’s replace-in-place is untouched', () => {
    openAgentView(SUGGESTIONS)
    openAgentView(TIERS)

    // Otherwise a pill would say "you haven't seen this" about the thing being looked at.
    expect(useAgentViewStore.getState().unread).toEqual({})
  })

  it('does NOT mark a CLOSED kind unread — dismissal is Brad’s act (UX-DR34)', () => {
    openAgentView(SUGGESTIONS)
    closeAgentView()
    openAgentView(viewOf('swaps'))

    // The `status === 'open'` half of the displacement test, and the half most likely to be
    // dropped as redundant. It is not: a push arriving while nothing is on the glass displaces
    // nothing, because the previous view was already dismissed on purpose.
    expect(useAgentViewStore.getState().unread).toEqual({})
  })

  it('closing a view never sets unread, and never clears retention', () => {
    openAgentView(SUGGESTIONS)
    closeAgentView()

    expect(useAgentViewStore.getState().unread).toEqual({})
    expect(useAgentViewStore.getState().retained.suggestions).toBe(SUGGESTIONS)
  })

  it('clears the flag when that kind is opened again — and the flag MOVES', () => {
    openAgentView(SUGGESTIONS)
    openAgentView(viewOf('swaps'))
    expect(useAgentViewStore.getState().unread).toEqual({ suggestions: true })

    openAgentView(SUGGESTIONS)

    // Opened by a push here; `reopenAgentView` routes through the same verb, so the clear is one
    // behaviour with two entrances. `swaps` is now the displaced one — the flag moved rather
    // than merely vanishing, which is the stronger claim.
    expect(useAgentViewStore.getState().unread).toEqual({ swaps: true })
  })

  it('writes a NEW unread object, so a subscriber re-renders', () => {
    openAgentView(SUGGESTIONS)
    const first = useAgentViewStore.getState().unread
    openAgentView(viewOf('swaps'))

    expect(useAgentViewStore.getState().unread).not.toBe(first)
  })
})

describe('reopenAgentView puts a retained view back (c6-8, AC 4)', () => {
  it('re-opens the retained content, by identity, asking nothing of the agent', () => {
    openAgentView(SUGGESTIONS)
    closeAgentView()
    reopenAgentView('suggestions')

    expect(openViewNow()).toBe(SUGGESTIONS)
  })

  it('clears that kind’s unread flag', () => {
    openAgentView(SUGGESTIONS)
    openAgentView(viewOf('swaps'))
    closeAgentView()
    reopenAgentView('suggestions')

    expect(useAgentViewStore.getState().unread.suggestions).toBeUndefined()
  })

  it('is a NO-OP for a kind that has never pushed', () => {
    reopenAgentView('tier_list')

    expect(useAgentViewStore.getState()).toEqual(INITIAL_AGENT_VIEW)
  })

  it('is a no-op even with another kind retained (the positive twin)', () => {
    // Without this, the assertion above would also pass for a `reopenAgentView` that opened
    // whatever happened to be in the map regardless of the kind asked for.
    openAgentView(SUGGESTIONS)
    closeAgentView()
    reopenAgentView('groups')

    expect(useAgentViewStore.getState().status).toBe('closed')
    expect(openViewNow()).toBeNull()
  })
})

describe('the c6-8 fields did not reshape the c6-5 ones (UX-DR38, Landmine 15)', () => {
  it('keeps `content` a scalar — the map is bookkeeping, not a second open view', () => {
    openAgentView(SUGGESTIONS)
    openAgentView(viewOf('swaps'))

    // Two kinds retained, ONE on the glass. If `retained` ever became a second open-view
    // mechanism, this is where it would show first.
    expect(Object.keys(useAgentViewStore.getState().retained)).toHaveLength(2)
    expect(openViewNow()).toMatchObject({ kind: 'swaps' })
    expect(openViewOf(useAgentViewStore.getState())).toBe(
      useAgentViewStore.getState().retained.swaps,
    )
  })

  it('starts empty, and the test-only reset really empties both maps', () => {
    expect(INITIAL_AGENT_VIEW.retained).toEqual({})
    expect(INITIAL_AGENT_VIEW.unread).toEqual({})

    openAgentView(SUGGESTIONS)
    openAgentView(viewOf('swaps'))
    resetAgentView()

    // The counterweight to every retention assertion above: if `resetAgentView` did not clear
    // these, they would all be passing on a store nothing had ever emptied.
    expect(useAgentViewStore.getState()).toEqual(INITIAL_AGENT_VIEW)
  })
})

// =========================================================================================
// STORY c7-6 — the one bit the deck announcer reads
// =========================================================================================

/**
 * `useAgentViewIsOpen`, walked across every writer that can move `status` (story c7-6).
 *
 * The consumer is `DeckAnnouncer`, whose gate is *"is a modal covering the deck"* and nothing
 * else — so what this block owes is the LIFECYCLE of the boolean rather than a second reading of
 * the content: false before anything pushes, true after each of the three open paths, false
 * again after the one close path. `useOpenAgentView` beside it already has its own coverage
 * above; the pair's whole reason to both exist is the last test here.
 */
describe('the announcer’s open/closed bit (c7-6)', () => {
  it('is FALSE before anything has pushed — the mount state of every session', () => {
    const { result } = renderHook(() => useAgentViewIsOpen())
    expect(result.current).toBe(false)
  })

  it('is TRUE after a direct open', () => {
    openAgentView(SUGGESTIONS)
    const { result } = renderHook(() => useAgentViewIsOpen())
    expect(result.current).toBe(true)
  })

  it('is TRUE after a push off the socket — the production writer', () => {
    // `openSuggestionsPush` is the one verb `connection.ts` calls, so this is the path a real
    // agent frame takes to the bit the announcer reads. Asserted separately from the direct open
    // above because a gate that only worked for hand-written opens would suppress nothing in the
    // running app.
    openSuggestionsPush(frame({ title: 'Resilience options', items: [ITEM] }))
    const { result } = renderHook(() => useAgentViewIsOpen())
    expect(result.current).toBe(true)
  })

  it('is TRUE after a re-open from a nav pill', () => {
    openAgentView(SUGGESTIONS)
    closeAgentView()
    reopenAgentView('suggestions')
    const { result } = renderHook(() => useAgentViewIsOpen())
    expect(result.current).toBe(true)
  })

  it('is FALSE after dismissal — even though the content is still retained', () => {
    // THE ASYMMETRY THAT MATTERS TO THE ANNOUNCER. `closeAgentView` writes `status` and nothing
    // else (UX-DR34), so `content` and `retained` both survive the dismissal — and a bit derived
    // from either of those would still read "open" here and go on suppressing announcements for
    // the rest of the session. Reading `status` is what makes the suppression end when the view
    // leaves the glass.
    openAgentView(SUGGESTIONS)
    closeAgentView()

    const { result } = renderHook(() => useAgentViewIsOpen())
    expect(result.current).toBe(false)
    expect(useAgentViewStore.getState().content).toBe(SUGGESTIONS)
    expect(useAgentViewStore.getState().retained.suggestions).toBe(SUGGESTIONS)
  })

  it('is a PRIMITIVE, which is why it exists beside `useOpenAgentView` (Design Notes)', () => {
    // The pair is not a duplication: this one answers with a boolean, its sibling with the
    // content object. `DeckAnnouncer` subscribes to primitives only, one field per subscription,
    // so that a second push while a view is open cannot re-render a region whose sentence has
    // nothing to do with agent content. A selector returning the object would re-render it on
    // every push — and the two must never disagree about whether something is showing, which is
    // the second half of this assertion.
    openAgentView(SUGGESTIONS)
    const { result: isOpen } = renderHook(() => useAgentViewIsOpen())
    const { result: content } = renderHook(() => useOpenAgentView())

    expect(typeof isOpen.current).toBe('boolean')
    expect(isOpen.current).toBe(content.current !== null)

    closeAgentView()
    const { result: closedIsOpen } = renderHook(() => useAgentViewIsOpen())
    const { result: closedContent } = renderHook(() => useOpenAgentView())
    expect(closedIsOpen.current).toBe(closedContent.current !== null)
  })
})
