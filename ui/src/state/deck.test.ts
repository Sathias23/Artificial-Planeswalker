/**
 * The boot, the refusal vocabulary and the precedence rule (story c4-2, AC 1, 5, 8–12, 17, 18).
 *
 * Two testing postures in one file, and the split is deliberate:
 *
 *   **`createDeckBoot` takes injected readers**, exactly as `createPoller` takes `read?:`, so the
 *   sequencing, the generation guard and the token→panel decisions are asserted against plain
 *   functions with no global `fetch` stub anywhere near them.
 *
 *   **AC 17's seeding assertion stubs `globalThis.fetch` instead**, because the claim it makes is
 *   *"this costs ZERO requests"* and a count taken through an injected reader would be a count of
 *   calls to a function the production path does not use. c4-1's own review corrected a vacuous
 *   version of exactly this assertion; the honest count is the one the network sees.
 *
 * `surfaceOf` is a pure function of two states and is asserted as one — no render, no store.
 * What it looks like on a real screen is `App.test.tsx`'s, from one mount.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ActiveDeckOutcome, DeckOutcome } from '../api/client'
import type { CardSummary, DeckCardSummary, DeckDetail } from '../api/schema'
import { INITIAL_CARD_CACHE, resetCardCache, useCardStore } from './cards'
import {
  INITIAL_DECK_STATE,
  createDeckBoot,
  driveDeckChanged,
  resetDeckState,
  surfaceOf,
  useDeckStore,
  type DeckState,
} from './deck'
import { INITIAL_SYSTEM_STATE, type SystemState } from './systemState'

const ATRAXA_DECK_ID = '813d0434-1bed-4419-bf9d-d9e4070704c4'

const summary = (name: string, typeLine: string): CardSummary => ({
  id: `id-${name}`,
  name,
  mana_cost: '',
  cmc: 0,
  type_line: typeLine,
  oracle_text: '',
  colors: [],
  rarity: 'rare',
  set_code: 'tst',
})

const row = (name: string, typeLine: string): DeckCardSummary => ({
  card_id: `id-${name}`,
  quantity: 1,
  sideboard: false,
  commander: false,
  card: summary(name, typeLine),
})

const detail = (overrides: Partial<DeckDetail> = {}): DeckDetail => ({
  id: ATRAXA_DECK_ID,
  name: 'Atraxa Counter Cabinet v2 (owned)',
  format: 'brawl',
  strategy: null,
  color_identity: [],
  tags: [],
  mainboard_count: 2,
  sideboard_count: 0,
  distinct_cards: 2,
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
  cards: [row('Llanowar Elves', 'Creature — Elf Druid'), row('Forest', 'Basic Land — Forest')],
  ...overrides,
})

/** Drive one boot to completion against canned answers, and report every state it emitted. */
const boot = async (
  active: ActiveDeckOutcome,
  deck: DeckOutcome = { kind: 'unreachable' },
): Promise<DeckState[]> => {
  const seen: DeckState[] = []
  const runner = createDeckBoot({
    onUpdate: (state) => seen.push(state),
    readActive: () => Promise.resolve(active),
    readDetail: () => Promise.resolve(deck),
  })
  runner.start()
  await vi.waitFor(() => expect(seen.length).toBeGreaterThan(0))
  return seen
}

beforeEach(() => {
  resetDeckState()
  resetCardCache()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the boot is two requests, in order, on mount (AC 1)', () => {
  it('asks for the active deck first, then for that deck by id', async () => {
    const order: string[] = []
    const runner = createDeckBoot({
      onUpdate: () => order.push('settled'),
      readActive: () => {
        order.push('active-deck')
        return Promise.resolve({ kind: 'active-deck', deckId: ATRAXA_DECK_ID })
      },
      readDetail: (deckId) => {
        order.push(`deck:${deckId}`)
        return Promise.resolve({ kind: 'deck', deck: detail() })
      },
    })

    runner.start()
    await vi.waitFor(() => expect(order).toHaveLength(3))

    expect(order).toEqual(['active-deck', `deck:${ATRAXA_DECK_ID}`, 'settled'])
  })

  it('does NOT ask for a deck when there is no active one — the ordinary cold open', async () => {
    const readDetail = vi.fn(() => Promise.resolve<DeckOutcome>({ kind: 'unreachable' }))
    const settled: DeckState[] = []
    const runner = createDeckBoot({
      onUpdate: (state) => settled.push(state),
      readActive: () => Promise.resolve({ kind: 'active-deck', deckId: null }),
      readDetail,
    })

    runner.start()
    // Waited on the SEQUENCE FINISHING, not on a store read that is defined from the first tick:
    // `expect(getState()).toBeDefined()` resolves immediately and would make the assertion below
    // a race that usually passes.
    await vi.waitFor(() => expect(settled).toHaveLength(1))

    // FR-07: the slot dies with the process, so `null` is the normal answer, not an error path —
    // and a second request for a deck that was never named is a request with no id to carry.
    expect(readDetail).not.toHaveBeenCalled()
  })

  it('never calls the deck reader with an empty id — `/api/deck/` is a different route', async () => {
    const readDetail = vi.fn(() => Promise.resolve<DeckOutcome>({ kind: 'unreachable' }))
    const settled: DeckState[] = []
    const runner = createDeckBoot({
      onUpdate: (state) => settled.push(state),
      // Past `readActiveDeck`'s own blank-folding, to prove the second lock holds on its own.
      readActive: () => Promise.resolve({ kind: 'active-deck', deckId: '' }),
      readDetail,
    })

    runner.start()
    await vi.waitFor(() => expect(settled).toEqual([{ status: 'none' }]))

    expect(readDetail).not.toHaveBeenCalled()
  })

  it('settles a loaded deck with its boards already derived (AC 13)', async () => {
    const [state] = await boot(
      { kind: 'active-deck', deckId: ATRAXA_DECK_ID },
      {
        kind: 'deck',
        deck: detail(),
      },
    )

    expect(state.status).toBe('deck')
    // Derived ONCE, here, at write time — not by whoever renders it.
    expect(state.status === 'deck' && state.boards.mainboard.map((g) => g.group)).toEqual([
      'Creature',
      'Land',
    ])
  })
})

describe('the boot is cancellable and generation-guarded (AC 5)', () => {
  it('writes nothing after stop(), even mid-sequence', async () => {
    const seen: DeckState[] = []
    let releaseActive: (outcome: ActiveDeckOutcome) => void = () => undefined
    const runner = createDeckBoot({
      onUpdate: (state) => seen.push(state),
      readActive: () =>
        new Promise<ActiveDeckOutcome>((resolve) => {
          releaseActive = resolve
        }),
      readDetail: () => Promise.resolve({ kind: 'deck', deck: detail() }),
    })

    runner.start()
    runner.stop()
    releaseActive({ kind: 'active-deck', deckId: ATRAXA_DECK_ID })
    await Promise.resolve()
    await Promise.resolve()

    expect(seen).toEqual([])
  })

  it('lets a RESTART win over the sequence it interrupted — probe (e)', async () => {
    // The failure a plain `live` boolean cannot see, and the reason the counter exists: React
    // StrictMode remounts the effect in development, so `stop()` then `start()` can land inside
    // the window between the two requests. A boolean would let the FIRST sequence resume, issue
    // its second request against an abandoned world, and write a deck the caller had left.
    const seen: DeckState[] = []
    let releaseFirst: (outcome: ActiveDeckOutcome) => void = () => undefined
    let call = 0
    const runner = createDeckBoot({
      onUpdate: (state) => seen.push(state),
      readActive: () => {
        call += 1
        if (call === 1) {
          return new Promise<ActiveDeckOutcome>((resolve) => {
            releaseFirst = resolve
          })
        }
        return Promise.resolve({ kind: 'active-deck', deckId: null })
      },
      readDetail: () => Promise.resolve({ kind: 'deck', deck: detail({ name: 'Stale Deck' }) }),
    })

    runner.start()
    runner.stop()
    runner.start()
    // The abandoned first sequence answers LAST, which is the whole point of the ordering.
    releaseFirst({ kind: 'active-deck', deckId: ATRAXA_DECK_ID })
    await vi.waitFor(() => expect(seen).toHaveLength(1))
    await Promise.resolve()
    await Promise.resolve()

    expect(seen).toEqual([{ status: 'none' }])
    expect(seen.some((state) => state.status === 'deck')).toBe(false)
  })

  it('is idempotent while running — a second start() starts nothing', async () => {
    const readActive = vi.fn(() =>
      Promise.resolve<ActiveDeckOutcome>({ kind: 'active-deck', deckId: null }),
    )
    const runner = createDeckBoot({ onUpdate: () => undefined, readActive })

    runner.start()
    runner.start()
    runner.start()
    await vi.waitFor(() => expect(readActive).toHaveBeenCalled())

    expect(readActive).toHaveBeenCalledTimes(1)
  })

  it('survives a reader that THROWS, which the total readers never do', async () => {
    const seen: DeckState[] = []
    const runner = createDeckBoot({
      onUpdate: (state) => seen.push(state),
      readActive: () => {
        throw new Error('injected')
      },
    })

    runner.start()
    await vi.waitFor(() => expect(seen).toHaveLength(1))

    expect(seen).toEqual([{ status: 'none' }])
  })
})

describe('a DECK refusal becomes a panel, through PANEL_FOR_REASON (AC 8, 9, 10, 11)', () => {
  it('clears a 404 deck_not_found to the no-active-deck state (FR-11, AD-16)', async () => {
    const [state] = await boot(
      { kind: 'active-deck', deckId: ATRAXA_DECK_ID },
      {
        kind: 'error',
        reason: 'deck_not_found',
      },
    )

    // c2-9 wrote the mapping and its reason; this story is its FIRST live producer. `'none'` is
    // the clearing, and the system panel — already `no-active-deck` with its names — is what the
    // reader sees.
    expect(state).toEqual({ status: 'none' })
  })

  it('leaves NO stale deck behind when a 404 arrives — probe (d)', async () => {
    // **This test used to prove nothing**, and a probe is what said so: it supplied its own
    // `onUpdate` carrying `setState(state, true)`, so deleting that replace flag from PRODUCTION
    // left it green — this epic's standing finding (*the wiring is right and nothing asserts the
    // wiring*) wearing a store's costume. The repair was structural rather than a better
    // assertion: the slice now holds the union under a `deck` key, so a merge replaces it
    // wholesale and no call site has a flag to forget. See `DeckSlice`.
    useDeckStore.setState({
      deck: {
        status: 'deck',
        detail: detail(),
        boards: {
          commander: [],
          mainboard: [],
          sideboard: [],
          commanderQuantity: 0,
          mainboardQuantity: 0,
          sideboardQuantity: 0,
        },
      },
    })

    const runner = createDeckBoot({
      onUpdate: (state) => useDeckStore.setState({ deck: state }),
      readActive: () => Promise.resolve({ kind: 'active-deck', deckId: ATRAXA_DECK_ID }),
      readDetail: () => Promise.resolve({ kind: 'error', reason: 'deck_not_found' }),
    })
    runner.start()
    await vi.waitFor(() => expect(useDeckStore.getState().deck.status).toBe('none'))

    // A `'none'` carrying a ghost `detail` would satisfy every consumer that narrows on `status`.
    expect(useDeckStore.getState().deck).toEqual({ status: 'none' })
    expect('detail' in useDeckStore.getState().deck).toBe(false)
  })

  it.each([
    ['database_not_initialized', 'database-not-initialized'],
    ['database_unavailable', 'database-updating'],
  ])('turns %s into the %s panel — two 503s, two panels (AD-16)', async (reason, panel) => {
    const [state] = await boot(
      { kind: 'active-deck', deckId: ATRAXA_DECK_ID },
      {
        kind: 'error',
        reason,
      },
    )

    expect(state).toEqual({ status: 'refused', reason, panel })
  })

  it('turns a 400 invalid_request into no-active-deck, NOT into the bug panel (Q5, AC 11)', async () => {
    const [state] = await boot(
      { kind: 'active-deck', deckId: 'not-a-deck-id' },
      {
        kind: 'error',
        reason: 'invalid_request',
      },
    )

    // `states.ts` classifies this token NO_UI_RESPONSE on the premise that "the SPA never
    // generates a malformed request" — and that premise fails here: the id came from
    // `PUT /api/active-deck`, which stores any non-blank string verbatim. Letting it reach
    // `panelFor` unmodified would answer an agent typo with "The companion hit a bug."
    expect(state).toEqual({ status: 'none' })
  })

  it('still clamps a token this build has never heard of to the bug panel', async () => {
    const [state] = await boot(
      { kind: 'active-deck', deckId: ATRAXA_DECK_ID },
      {
        kind: 'error',
        reason: 'quantum_flux_capacitor_failed',
      },
    )

    // The unknown token is clamped to `null` HERE rather than carried on as a widened string.
    expect(state).toEqual({ status: 'refused', reason: null, panel: 'internal-error' })
  })

  it('reports a lost backend as no-deck, never as "the companion hit a bug"', async () => {
    // `panelFor(null)` is `'internal-error'`, which would be a LIE about an absent backend. The
    // panel that describes one is `disconnected`, and it is c5-6's by `CLIENT_ONLY_STATES` —
    // `poller.ts` takes exactly this posture for exactly this reason. c5-6 has shipped it, and
    // this arm is UNCHANGED: the panel is chosen in `surfaceOf` from the connection status, not
    // here from a boot outcome, so a deck read that found nothing still settles `'none'`.
    const [state] = await boot(
      { kind: 'active-deck', deckId: ATRAXA_DECK_ID },
      {
        kind: 'unreachable',
      },
    )

    expect(state).toEqual({ status: 'none' })
  })

  it('routes an ACTIVE-DECK refusal through the same boundary', async () => {
    // This route publishes only 400 and 500 — no 503 — so a refusal here is a real bug on one
    // side or the other, and `internal-error` is the honest panel for both.
    const [state] = await boot({ kind: 'error', reason: 'internal_error' })

    expect(state).toEqual({ status: 'refused', reason: 'internal_error', panel: 'internal-error' })
  })

  it('does NOT apply the Q5 override to a 400 on the ACTIVE-DECK route — review finding', async () => {
    // Q5's entire justification is "the id in the path came from `PUT /api/active-deck`", and
    // this route carries NO path parameter — so a 400 from it is exactly the client-bug case
    // `states.ts` classifies, and folding it to a calm 'none' would hide a real bug behind
    // "there is no active deck". The comment above this describe said internal-error is the
    // honest panel here; this is the assertion that stops the override from contradicting it.
    const [state] = await boot({ kind: 'error', reason: 'invalid_request' })

    // The token is KNOWN (it is in `PANEL_FOR_REASON`'s key set, mapped to `null`), so it is
    // carried on the state; only the PANEL is the clamp's doing.
    expect(state).toEqual({ status: 'refused', reason: 'invalid_request', panel: 'internal-error' })
  })
})

describe('the boot is total even against inputs the wire cannot produce (review findings)', () => {
  it('never calls the deck reader with a WHITESPACE id — the second lock trims', async () => {
    // `activeDeckIdOf` folds blanks on `trim()`, so production cannot deliver `'  '` — but the
    // second lock is advertised as holding on its own, and a lock that catches `''` while
    // passing `'  '` to `/api/deck/%20%20` is weaker than the door it backs.
    const readDetail = vi.fn(() => Promise.resolve<DeckOutcome>({ kind: 'unreachable' }))
    const settled: DeckState[] = []
    const runner = createDeckBoot({
      onUpdate: (state) => settled.push(state),
      readActive: () => Promise.resolve({ kind: 'active-deck', deckId: '  ' }),
      readDetail,
    })

    runner.start()
    await vi.waitFor(() => expect(settled).toEqual([{ status: 'none' }]))

    expect(readDetail).not.toHaveBeenCalled()
  })

  it('settles a REFUSAL, not a forever-booting silence, on a malformed row in a 200 body', async () => {
    // `deckOf` validates the envelope, not the rows — its own docstring says bad rows reach the
    // derivation. Before the review, a row without a `card` threw inside `boardsOfDeck` AFTER
    // the last generation check and OUTSIDE any try/catch: an unhandled rejection, no settle,
    // and a slice stuck at 'booting' forever with no panel — the one outcome this module's
    // "every outcome is a value" posture exists to ban. Unreachable with the real Pydantic
    // backend; reachable the day the SPA and the backend skew.
    const malformed = detail()
    const brokenRow = { card_id: 'id-broken', quantity: 1 } as unknown as DeckCardSummary
    const seen: DeckState[] = []
    const runner = createDeckBoot({
      onUpdate: (state) => seen.push(state),
      readActive: () => Promise.resolve({ kind: 'active-deck', deckId: ATRAXA_DECK_ID }),
      readDetail: () =>
        Promise.resolve({ kind: 'deck', deck: { ...malformed, cards: [brokenRow] } }),
    })

    runner.start()
    await vi.waitFor(() => expect(seen).toHaveLength(1))

    expect(seen).toEqual([{ status: 'refused', reason: null, panel: 'internal-error' }])
  })
})

describe('the deck payload seeds the card cache, for ZERO requests (AC 17)', () => {
  it('populates the summary tier and issues no request of its own', async () => {
    // The count is taken on `globalThis.fetch` — the real network path — because "costs zero
    // requests" is a claim about the network and not about an injected function.
    const fetchMock = vi.fn<typeof fetch>(() =>
      Promise.resolve(new Response('{}', { status: 200 })),
    )
    vi.stubGlobal('fetch', fetchMock)

    const payload = detail()
    await boot({ kind: 'active-deck', deckId: ATRAXA_DECK_ID }, { kind: 'deck', deck: payload })

    expect(useCardStore.getState().cards['id-Llanowar Elves']).toEqual({
      status: 'summary',
      summary: payload.cards[0].card,
    })
    expect(useCardStore.getState().cards['id-Forest']?.status).toBe('summary')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('seeds nothing when the read was refused', async () => {
    await boot(
      { kind: 'active-deck', deckId: ATRAXA_DECK_ID },
      {
        kind: 'error',
        reason: 'deck_not_found',
      },
    )

    expect(useCardStore.getState()).toEqual(INITIAL_CARD_CACHE)
  })
})

/**
 * The `deck_changed` refetch: one request, coalesced by supersession, latest-wins (story c7-3).
 *
 * Store-level, on injected readers — this file's declared split. Unlike the harness at the top,
 * `onUpdate` here writes the REAL store, because `driveDeckChanged`'s decision table reads
 * `useDeckStore.getState()` and a test driving its own array would assert a table over state the
 * table never saw (the exact vacuity probe (d) recorded). What a refetch looks like on a real
 * screen — derived panels recomputing, the format check re-asking — is `App.test.tsx`'s, from one
 * mount; what is pinned HERE is the request discipline: which reader fires, with which id, whose
 * signal aborts, and which response is allowed to settle.
 */
describe('the deck_changed refetch is one request, coalesced, latest-wins (c7-3)', () => {
  /** One captured `readDetail` call: the id asked for, and the abort handle it was handed. */
  interface DetailCall {
    readonly deckId: string
    readonly signal: AbortSignal | undefined
    resolve: (outcome: DeckOutcome) => void
  }

  /**
   * A boot on injected readers whose `onUpdate` writes the real store, with every detail read
   * captured and MANUALLY resolvable — the shape the burst rows need, and the settled rows just
   * resolve immediately.
   */
  const buildBoot = (activeId: string | null = ATRAXA_DECK_ID) => {
    const detailCalls: DetailCall[] = []
    const settles: DeckState[] = []
    const readActive = vi.fn(() =>
      Promise.resolve<ActiveDeckOutcome>({ kind: 'active-deck', deckId: activeId }),
    )
    const boot = createDeckBoot({
      onUpdate: (state) => {
        settles.push(state)
        useDeckStore.setState({ deck: state })
      },
      readActive,
      readDetail: (deckId, signal) =>
        new Promise<DeckOutcome>((resolve) => {
          detailCalls.push({ deckId, signal, resolve })
        }),
    })
    return { boot, readActive, detailCalls, settles }
  }

  /** Flush the microtask chain a resolved reader continues on. */
  const flush = async (): Promise<void> => {
    for (let i = 0; i < 8; i += 1) await Promise.resolve()
  }

  /** Boot to a settled `'deck'`, which is the decision table's quiet starting row. */
  const settled = async (harness: ReturnType<typeof buildBoot>, deck = detail()) => {
    harness.boot.start()
    await vi.waitFor(() => expect(harness.detailCalls).toHaveLength(1))
    harness.detailCalls[0].resolve({ kind: 'deck', deck })
    await vi.waitFor(() => expect(useDeckStore.getState().deck.status).toBe('deck'))
  }

  it('refetches ONLY the deck read on a matching event — the active-deck route is never asked', async () => {
    const harness = buildBoot()
    await settled(harness)

    driveDeckChanged(harness.boot, ATRAXA_DECK_ID)
    await vi.waitFor(() => expect(harness.detailCalls).toHaveLength(2))
    harness.detailCalls[1].resolve({ kind: 'deck', deck: detail({ name: 'After the edit' }) })
    await flush()

    // The matrix's first row, as a request log: one `GET /api/deck/{id}`, zero
    // `GET /api/active-deck` beyond the boot's own — the whole point of the story's one-request
    // shape against the old two-request re-drive.
    expect(harness.readActive).toHaveBeenCalledTimes(1)
    expect(harness.detailCalls[1].deckId).toBe(ATRAXA_DECK_ID)
    const after = useDeckStore.getState().deck
    expect(after.status === 'deck' && after.detail.name).toBe('After the edit')
  })

  it('treats a deck-agnostic (null) id as "refetch whatever is active"', async () => {
    const harness = buildBoot()
    await settled(harness)

    driveDeckChanged(harness.boot, null)
    await vi.waitFor(() => expect(harness.detailCalls).toHaveLength(2))

    // The folded null refetches the SETTLED id — the only id the client holds as truth.
    expect(harness.detailCalls[1].deckId).toBe(ATRAXA_DECK_ID)
    expect(harness.readActive).toHaveBeenCalledTimes(1)
  })

  it('does NOTHING on a different deck’s event — not even the refetch', async () => {
    const harness = buildBoot()
    await settled(harness)
    const before = useDeckStore.getState().deck

    driveDeckChanged(harness.boot, 'a-deck-this-tab-is-not-showing')
    await flush()

    // Zero requests of either kind since the boot: the deck on the glass was not edited, and
    // the poll-restart half of the ruling lives in `connection.ts`, outside this table.
    expect(harness.detailCalls).toHaveLength(1)
    expect(harness.readActive).toHaveBeenCalledTimes(1)
    expect(useDeckStore.getState().deck).toBe(before)
  })

  it('coalesces a burst by supersession: each newer event aborts the prior request', async () => {
    const harness = buildBoot()
    await settled(harness)
    const settlesBefore = harness.settles.length

    driveDeckChanged(harness.boot, ATRAXA_DECK_ID)
    driveDeckChanged(harness.boot, null)
    driveDeckChanged(harness.boot, ATRAXA_DECK_ID)
    await vi.waitFor(() => expect(harness.detailCalls).toHaveLength(4))

    // ≤1 in flight, structurally: the first two refetch requests were ABORTED the moment their
    // successor started (UX-DR35's "a newer event cancels and restarts"), and the last one is
    // still live. The boot's own request (index 0) was never touched.
    expect(harness.detailCalls[1].signal?.aborted).toBe(true)
    expect(harness.detailCalls[2].signal?.aborted).toBe(true)
    expect(harness.detailCalls[3].signal?.aborted).toBe(false)

    // Every response now lands, oldest first. Only the LAST is allowed to settle.
    harness.detailCalls[1].resolve({ kind: 'deck', deck: detail({ name: 'First — stale' }) })
    harness.detailCalls[2].resolve({ kind: 'deck', deck: detail({ name: 'Second — stale' }) })
    harness.detailCalls[3].resolve({ kind: 'deck', deck: detail({ name: 'Third — wins' }) })
    await flush()

    const after = useDeckStore.getState().deck
    expect(after.status === 'deck' && after.detail.name).toBe('Third — wins')
    // EXACTLY one settle for the whole burst — the coalescing claim as a count, and the claim
    // c7-5's announce-once banks on ("the coalescing machinery is the debounce").
    expect(harness.settles.length - settlesBefore).toBe(1)
  })

  it('discards an out-of-order response: the OLDER one resolving later cannot win', async () => {
    const harness = buildBoot()
    await settled(harness)

    driveDeckChanged(harness.boot, ATRAXA_DECK_ID)
    driveDeckChanged(harness.boot, ATRAXA_DECK_ID)
    await vi.waitFor(() => expect(harness.detailCalls).toHaveLength(3))

    // The NEWER request answers first and settles; the OLDER limps in afterwards — the abort
    // cannot un-send a response already in flight, so the generation guard is what stops it.
    harness.detailCalls[2].resolve({ kind: 'deck', deck: detail({ name: 'Newest — wins' }) })
    await flush()
    harness.detailCalls[1].resolve({ kind: 'deck', deck: detail({ name: 'Oldest — must lose' }) })
    await flush()

    const after = useDeckStore.getState().deck
    expect(after.status === 'deck' && after.detail.name).toBe('Newest — wins')
  })

  it('aborts an in-flight refetch on stop(), and its response can never settle', async () => {
    // `stop()`'s c7-3 duty, found untested by review: deleting `abortRefetch()` from `stop()`
    // stayed green, because every abort assertion until this one was about refetch-supersedes-
    // refetch. The generation bump already silences the settle — the abort is what stops a
    // stopped world PAYING for a request nobody can use.
    const harness = buildBoot()
    await settled(harness)
    const settlesBefore = harness.settles.length

    driveDeckChanged(harness.boot, ATRAXA_DECK_ID)
    await vi.waitFor(() => expect(harness.detailCalls).toHaveLength(2))
    expect(harness.detailCalls[1].signal?.aborted).toBe(false)

    harness.boot.stop()
    expect(harness.detailCalls[1].signal?.aborted).toBe(true)

    // …and the response limping in anyway settles nothing: `live` is false and the generation
    // moved, so the stale write dies at the shared guard.
    harness.detailCalls[1].resolve({ kind: 'deck', deck: detail({ name: 'Post-stop — stale' }) })
    await flush()
    expect(harness.settles.length - settlesBefore).toBe(0)
  })

  it('clears to no-active-deck when the refetch 404s — the one legislated teardown', async () => {
    const harness = buildBoot()
    await settled(harness)

    driveDeckChanged(harness.boot, ATRAXA_DECK_ID)
    await vi.waitFor(() => expect(harness.detailCalls).toHaveLength(2))
    harness.detailCalls[1].resolve({ kind: 'error', reason: 'deck_not_found' })
    await flush()

    // UX-DR35: "a 404 clears to no-active-deck" — through the boot's own shared mapping
    // (`PANEL_FOR_REASON.deck_not_found`), so this is a consumption, not a second copy.
    expect(useDeckStore.getState().deck).toEqual({ status: 'none' })
  })

  it.each<[string, DeckOutcome]>([
    ['a 503 database_unavailable', { kind: 'error', reason: 'database_unavailable' }],
    ['a 500 internal_error', { kind: 'error', reason: 'internal_error' }],
    // The boot's Q5 override folds THIS token to 'none'; on a refetch of an id that just
    // resolved it is a blip, and dropping it is the row that stops the override leaking here.
    ['a 400 invalid_request', { kind: 'error', reason: 'invalid_request' }],
    ['an unreachable backend', { kind: 'unreachable' }],
    [
      'a 200 with a malformed row',
      {
        kind: 'deck',
        deck: {
          ...detail(),
          cards: [{ card_id: 'id-broken', quantity: 1 } as unknown as DeckCardSummary],
        },
      },
    ],
  ])('DROPS %s and leaves the loaded deck untouched (never-teardown)', async (_label, outcome) => {
    const harness = buildBoot()
    await settled(harness)
    const before = useDeckStore.getState().deck
    const settlesBefore = harness.settles.length

    driveDeckChanged(harness.boot, ATRAXA_DECK_ID)
    await vi.waitFor(() => expect(harness.detailCalls).toHaveLength(2))
    harness.detailCalls[1].resolve(outcome)
    await flush()

    // The boot maps every one of these to a panel or a clear, because a cold open has nothing
    // on the glass to protect. A refetch has, so the DECK STORE is untouched: same state, by
    // reference, and zero settles — staleness accepted, recovery owned by the next event, the
    // reconnect re-drive or the poll edge. (The malformed-200 row's card CACHE is deliberately
    // not asserted clean: seeding runs before the derivation throws, and the validly-shaped
    // summaries it may retain are additive and harmless — `deck.ts`'s catch says why.)
    expect(useDeckStore.getState().deck).toBe(before)
    expect(harness.settles.length - settlesBefore).toBe(0)
  })

  it('folds a mid-boot event into a fresh FULL re-drive — never a refetch against a departing id', async () => {
    // Its own harness rather than `buildBoot`: the mid-boot window only exists while the
    // active-deck answer is WITHHELD, so this reader must be manually resolvable too.
    const detailCalls: DetailCall[] = []
    const activeResolvers: ((outcome: ActiveDeckOutcome) => void)[] = []
    const readActive = vi.fn(
      () => new Promise<ActiveDeckOutcome>((resolve) => activeResolvers.push(resolve)),
    )
    const boot = createDeckBoot({
      onUpdate: (state) => useDeckStore.setState({ deck: state }),
      readActive,
      readDetail: (deckId, signal) =>
        new Promise<DeckOutcome>((resolve) => {
          detailCalls.push({ deckId, signal, resolve })
        }),
    })

    boot.start()
    await vi.waitFor(() => expect(activeResolvers).toHaveLength(1))
    activeResolvers[0]({ kind: 'active-deck', deckId: ATRAXA_DECK_ID })
    await vi.waitFor(() => expect(detailCalls).toHaveLength(1))
    detailCalls[0].resolve({ kind: 'deck', deck: detail() })
    await vi.waitFor(() => expect(useDeckStore.getState().deck.status).toBe('deck'))

    // A re-drive is in flight (reconnect, poll edge — any caller of stop()/start()): the store
    // still shows the old deck, but the settled id is no longer current truth.
    boot.stop()
    boot.start()
    await vi.waitFor(() => expect(readActive).toHaveBeenCalledTimes(2))
    expect(useDeckStore.getState().deck.status).toBe('deck')

    driveDeckChanged(boot, ATRAXA_DECK_ID)
    await vi.waitFor(() => expect(readActive).toHaveBeenCalledTimes(3))

    // The fold is a full boot — active-deck FIRST (the server referees, c6-3 ruling #1's
    // principle) — and no single-deck read was issued against the possibly-departing id: the
    // only detail call so far is still the settled boot's own.
    expect(detailCalls).toHaveLength(1)

    // …and the folded re-drive OWNS the store now. It answers a DIFFERENT deck — the exact
    // supersession race the fold exists to win: a single-deck refetch here would have re-read
    // the departing deck and beaten the re-drive to the store.
    activeResolvers[2]({ kind: 'active-deck', deckId: 'the-newly-activated-deck' })
    await vi.waitFor(() => expect(detailCalls).toHaveLength(2))
    expect(detailCalls[1].deckId).toBe('the-newly-activated-deck')
  })

  it('re-drives the full boot from a settled none state — the no-deck row', async () => {
    const harness = buildBoot(null)
    harness.boot.start()
    await vi.waitFor(() => expect(useDeckStore.getState().deck).toEqual({ status: 'none' }))

    driveDeckChanged(harness.boot, ATRAXA_DECK_ID)
    await vi.waitFor(() => expect(harness.readActive).toHaveBeenCalledTimes(2))

    // Today's behaviour, kept: the full two-request sequence, which is also what recovers the
    // unreachable-blip and 404-residue windows the module header describes.
    expect(harness.detailCalls).toHaveLength(0)
  })

  it('refuses a bare refetch() before the sequence settles — the boot cannot be misused into a stuck boot', async () => {
    const harness = buildBoot()
    harness.boot.start()
    await vi.waitFor(() => expect(harness.readActive).toHaveBeenCalledTimes(1))

    // Called DIRECTLY, past the decision table — the gate this pins is the boot's own: an
    // ungated refetch would bump the generation out from under the in-flight sequence, and a
    // dropped outcome would then strand the slice at 'booting' forever with no panel.
    harness.boot.refetch(ATRAXA_DECK_ID)
    await flush()

    expect(harness.detailCalls).toHaveLength(1)
    harness.detailCalls[0].resolve({ kind: 'deck', deck: detail() })
    await vi.waitFor(() => expect(useDeckStore.getState().deck.status).toBe('deck'))
  })
})

describe('surfaceOf — the precedence, in one place (Q1, AC 6, AC 7)', () => {
  /**
   * A system slice for one panel. `connection` defaults to `'live'` — "the socket is not what
   * this test is about" — so every assertion written before c5-6 keeps meaning exactly what it
   * meant, and the fourth arm gets its own describe below rather than leaking into these.
   */
  const system = (
    panel: SystemState['panel'],
    connection: SystemState['connection'] = 'live',
  ): SystemState => ({ panel, decks: [], connection })
  const loaded: DeckState = {
    status: 'deck',
    detail: detail(),
    boards: {
      commander: [],
      mainboard: [],
      sideboard: [],
      commanderQuantity: 0,
      mainboardQuantity: 0,
      sideboardQuantity: 0,
    },
  }

  it('puts a loaded deck on the glass, displacing the system panel (AC 6)', () => {
    const surface = surfaceOf(loaded, system('no-active-deck'))

    expect(surface.kind).toBe('deck')
    expect(surface.kind === 'deck' && surface.detail.name).toBe('Atraxa Counter Cabinet v2 (owned)')
  })

  it('keeps the deck even when the POLL has since gone unhappy', () => {
    // The precedence is a rule, not a coincidence of the two usually agreeing. A deck already in
    // hand is still the true thing on screen while the deck LIST route is refusing.
    expect(surfaceOf(loaded, system('database-updating')).kind).toBe('deck')
  })

  it('gives a deck REFUSAL priority over the poll’s opinion (AC 9)', () => {
    // The arm that makes AC 9 non-vacuous: without it, the deck read's 503 panel would only ever
    // appear because the poll happened to see the same 503, and the assertion would prove
    // nothing about the deck path at all.
    const surface = surfaceOf(
      { status: 'refused', reason: 'database_unavailable', panel: 'database-updating' },
      system('no-active-deck'),
    )

    expect(surface).toEqual({ kind: 'panel', panel: 'database-updating' })
  })

  // TYPED TABLE, not an inline literal: c4-1 lost a diagnosis to an untyped `it.each` widening a
  // discriminant to `string`, which fails `tsc -b` while `npm test` stays green.
  const deferring: [string, DeckState][] = [
    ['booting', INITIAL_DECK_STATE],
    ['none', { status: 'none' }],
  ]

  it.each(deferring)('defers to the system panel while %s (AC 7)', (_label, deck) => {
    expect(surfaceOf(deck, system('database-not-initialized'))).toEqual({
      kind: 'panel',
      panel: 'database-not-initialized',
    })
    expect(surfaceOf(deck, system('no-active-deck'))).toEqual({
      kind: 'panel',
      panel: 'no-active-deck',
    })
  })

  it('is never both — every input produces exactly one surface', () => {
    const states: DeckState[] = [
      INITIAL_DECK_STATE,
      { status: 'none' },
      loaded,
      { status: 'refused', reason: null, panel: 'internal-error' },
    ]
    for (const deck of states) {
      const surface = surfaceOf(deck, INITIAL_SYSTEM_STATE)
      expect(['deck', 'panel']).toContain(surface.kind)
    }
  })

  describe('the FOURTH arm: a lost connection outranks everything (c5-6, Q3, AC 7, AC 8)', () => {
    const states: [string, DeckState][] = [
      ['booting', INITIAL_DECK_STATE],
      ['none', { status: 'none' }],
      ['a loaded deck', loaded],
      ['a deck refusal', { status: 'refused', reason: 'internal_error', panel: 'internal-error' }],
    ]

    it.each(states)('displaces %s once the connection is down', (_label, deck) => {
      // Every arm, not a representative one: the whole content of Q3's ruling is that this one
      // outranks arm 1, and a test that only checked `none` would pass through a rule written
      // "below the deck".
      expect(surfaceOf(deck, system('no-active-deck', 'down'))).toEqual({
        kind: 'panel',
        panel: 'disconnected',
      })
    })

    it.each(states)(
      'leaves %s exactly as it was while merely reconnecting (UX-DR35)',
      (_l, deck) => {
        // THE SILENT HALF, and the one that carries UX-DR35. The pre-exhaustion window is the whole
        // of an ordinary backend restart, and during it this function must behave as though c5-6 had
        // never touched it — a deck stays rendered, possibly stale, never torn down to a skeleton.
        expect(surfaceOf(deck, system('database-updating', 'reconnecting'))).toEqual(
          surfaceOf(deck, system('database-updating', 'live')),
        )
      },
    )

    it('overrides even a deck REFUSAL panel, which is the arm that outranks the poll', () => {
      // Arm 2 exists so a deck read's own 503 is not overwritten by the poll's opinion. The
      // connection arm sits above it too, because a 503 the client observed before the backend
      // vanished says nothing about a backend that is now gone.
      const refused: DeckState = {
        status: 'refused',
        reason: 'database_unavailable',
        panel: 'database-updating',
      }
      expect(surfaceOf(refused, system('no-active-deck', 'down'))).toEqual({
        kind: 'panel',
        panel: 'disconnected',
      })
    })

    it('reads the CONNECTION and not the panel field — the two-writers race Q3 avoided', () => {
      // The failure this shape prevents: with the HTTP half up and the WS half failing (a proxy
      // misconfiguration is the realistic case), a poll SUCCESS is a change, and a socket that had
      // written `panel: 'disconnected'` into the shared field would have it overwritten while the
      // socket was still down. Here a healthy poll and a dead socket compose instead of racing.
      expect(surfaceOf({ status: 'none' }, system('no-active-deck', 'down'))).toEqual({
        kind: 'panel',
        panel: 'disconnected',
      })
    })

    it('restores the deck the instant the connection returns — no reload, nothing recomputed', () => {
      // AC 9 at the level of the pure function: the deck slice was never cleared, so recovery is a
      // re-render of state nobody destroyed.
      expect(surfaceOf(loaded, system('no-active-deck', 'down')).kind).toBe('panel')
      expect(surfaceOf(loaded, system('no-active-deck', 'live')).kind).toBe('deck')
    })
  })
})
