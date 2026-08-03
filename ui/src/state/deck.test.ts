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
    // `poller.ts` takes exactly this posture for exactly this reason.
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

describe('surfaceOf — the precedence, in one place (Q1, AC 6, AC 7)', () => {
  const system = (panel: SystemState['panel']): SystemState => ({ panel, decks: [] })
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
})
