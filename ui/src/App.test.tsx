/**
 * App's own job, now that it has one: composing the shell, and showing whichever system state is
 * true right now (story c3-9).
 *
 * The landmark, header and slot assertions moved to
 * `src/components/AppShell/AppShell.test.tsx` in story c2-6, where the element structure
 * actually lives — asserting them twice would mean two files to update when c4-2 changes the
 * heading, and the second one would be the one nobody remembers. What stays here is the part
 * only this file can be wrong about: that the root renders the shell at all, that it renders
 * exactly one of it, and — as of c3-9 — that the panel it renders is the one the WIRE chose.
 *
 * WHY THE STATE ASSERTIONS ARE HERE RATHER THAN ON THE POLLER. `poller.test.ts` proves the
 * schedule and `panel.test.ts` proves the mapping; neither of them renders anything, and the
 * claim FR-22 actually makes is about what a human sees on a page they did not touch. That claim
 * can only be made at the root, from ONE mount.
 *
 * The jsdom environment, the jest-dom matchers and afterEach(cleanup) all come from the `dom`
 * vitest project in vite.config.ts; nothing needs setting up per file.
 */

import { act, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { sentenceOf } from './components/Footer/copy'
import { resetCardCache, useCardStore } from './state/cards'
import { resetDeckState, useDeckStore } from './state/deck'
import { INITIAL_SYSTEM_STATE, useSystemStore } from './state/systemState'

/** One canned answer, built the way the backend builds it: a token, and nothing else. */
const refusal = (reason: string, status: number) =>
  new Response(JSON.stringify({ reason }), { status })

const decks = (...names: string[]) =>
  new Response(JSON.stringify(names.map((name) => ({ id: name, name }))), { status: 200 })

/** `GET /api/active-deck`'s body. `null` is the answer a fresh backend gives (FR-07). */
const activeDeck = (deckId: string | null) =>
  new Response(JSON.stringify({ deck_id: deckId }), { status: 200 })

const ATRAXA_DECK_ID = '813d0434-1bed-4419-bf9d-d9e4070704c4'

const deckCard = (name: string, typeLine: string, quantity = 1) => ({
  card_id: `id-${name}`,
  quantity,
  sideboard: false,
  commander: false,
  card: {
    id: `id-${name}`,
    name,
    mana_cost: '',
    cmc: 0,
    type_line: typeLine,
    oracle_text: '',
    colors: [],
    rarity: 'rare',
    set_code: 'tst',
  },
})

/** `GET /api/deck/{id}`'s body, with the fields the header and the derivation actually read. */
const deckDetail = (overrides: Record<string, unknown> = {}) =>
  new Response(
    JSON.stringify({
      id: ATRAXA_DECK_ID,
      name: 'Atraxa Counter Cabinet v2 (owned)',
      format: 'brawl',
      strategy: null,
      color_identity: [],
      tags: [],
      mainboard_count: 100,
      sideboard_count: 0,
      distinct_cards: 2,
      created_at: '2026-07-01T00:00:00Z',
      updated_at: '2026-08-01T00:00:00Z',
      cards: [
        deckCard('Llanowar Elves', 'Creature — Elf Druid'),
        deckCard('Forest', 'Basic Land — Forest', 10),
      ],
      ...overrides,
    }),
    { status: 200 },
  )

/**
 * What the two BOOT routes answer. Set per test by {@link booting}; reset every test to the
 * fresh-install truth — no active deck, and therefore no deck to fetch.
 *
 * **Why the harness became route-aware at c4-2, and why that is not a weakening.** Until this
 * story there was exactly ONE caller, so "the nth response" and "the nth poll" were the same
 * thing and `answering()` could serve a flat sequence. c4-2 adds a second, independent caller —
 * the deck boot — and a flat sequence would hand the poll's second answer to the boot's first
 * request, which is not a scenario any backend can produce. Routing by path restores what the
 * fixture always MEANT. **Every `expect` in this file's pre-existing blocks is unchanged**
 * (AC 7); what changed is which canned answer each route receives, which is the fixture becoming
 * more like the backend rather than less.
 */
let bootActive: Response = activeDeck(null)
let bootDeck: Response = refusal('deck_not_found', 404)

const booting = (active: Response, deck?: Response) => {
  bootActive = active
  if (deck !== undefined) bootDeck = deck
}

/**
 * Answer the POLL with each response in turn, repeating the last one forever — and answer the two
 * boot routes from {@link booting}.
 *
 * `globalThis.fetch` rather than an injected reader, deliberately: this file is the only place
 * the whole path — request, body parsing, token validation, panel choice, render — is exercised
 * end to end, and injecting past any of it would leave that seam untested at every level.
 */
const answering = (...responses: Response[]) => {
  let index = 0
  const fetchMock = vi.fn((input?: unknown) => {
    const path = String(input)
    if (path.startsWith('/api/deck/')) return Promise.resolve(bootDeck.clone())
    if (path === '/api/active-deck') return Promise.resolve(bootActive.clone())
    const response = responses[Math.min(index, responses.length - 1)]
    index += 1
    return Promise.resolve(response.clone())
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** How many times one route was actually asked. The honest count once there are two callers. */
const callsTo = (fetchMock: ReturnType<typeof answering>, path: string) =>
  fetchMock.mock.calls.filter(([input]) => String(input).startsWith(path)).length

/** Let the in-flight poll settle without waiting for real time. */
const settle = () => act(async () => void (await vi.advanceTimersByTimeAsync(0)))

const advance = (ms: number) => act(async () => void (await vi.advanceTimersByTimeAsync(ms)))

beforeEach(() => {
  vi.useFakeTimers()
  // The stores are module-level, as stores are; without this the panel — or the deck — a previous
  // test left behind would be what the next one starts from.
  useSystemStore.setState(INITIAL_SYSTEM_STATE)
  resetDeckState()
  resetCardCache()
  bootActive = activeDeck(null)
  bootDeck = refusal('deck_not_found', 404)
  answering(refusal('database_not_initialized', 503))
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('App', () => {
  it('renders the application shell', () => {
    render(<App />)

    // By role, not by class name — and ONE landmark, not the full triple: the landmark
    // CONTRACT (exactly one banner/main/contentinfo, Q4's structure) is AppShell.test.tsx's,
    // and re-asserting it here would be exactly the duplication this file's header says was
    // moved — two files to update when Q4's structure changes, and the second one forgotten.
    //
    // What this assertion is and is NOT: `main` alone proves App renders SOMETHING with a
    // main landmark, which a bare `<main/>` impostor would also satisfy. The composition
    // proof is the heading test below — the shell supplies that heading, and an impostor
    // would not. Together they are the pair; neither carries it alone, and an earlier version
    // of this comment claimed the first one did.
    expect(screen.getAllByRole('main')).toHaveLength(1)
  })

  it('gives the document a top-level heading before any deck exists', () => {
    // Q3's ruling, asserted at the root because it is a property of what a fresh install
    // SHOWS, not of the shell in isolation: the no-active-deck state is the state the app
    // starts in, and it must not be heading-less. c4-2 replaces the string via `deckName`.
    render(<App />)

    expect(screen.getByRole('heading', { level: 1, name: 'Artificial Planeswalker' })).toBeVisible()
  })
})

/**
 * The fresh-install path, at the root, from the wire (story c3-9, AC 1, AC 2, AC 4, AC 5).
 *
 * This block REPLACES c2-9's static-panel assertion rather than sitting beside it. That
 * assertion's own comment named this story as its inheritor: *"c3-9 replaces the static choice
 * with the wire-driven one and inherits this assertion."* The shape it established — by role and
 * accessible name, because that is what the panel IS to a screen reader — is kept exactly.
 *
 * The no-error-styling half of AC 1 is INHERITED STRUCTURALLY and is not re-asserted here:
 * `tests/token-usage.test.ts` bans `--negative` and `--caution` from the state panel's
 * stylesheet, and `StatePanel.tsx` contains no `<img>`, `<svg>`, icon or spinner — both of which
 * are source-read gates that jsdom could not improve on, since jsdom applies no stylesheet at all.
 */
describe('the panel is chosen by the wire, not by a constant (AC 1, AC 2)', () => {
  it('greets a fresh install with the database panel, not an error page', async () => {
    render(<App />)
    await settle()

    expect(screen.getByRole('region', { name: 'Card database not set up yet.' })).toBeVisible()
    // …and the state it replaced is gone, so this is a CHOICE rather than an accumulation.
    expect(screen.queryByRole('region', { name: 'No deck on the glass.' })).toBeNull()
  })

  it('reads the TOKEN, not the status — two 503s, two different panels (AD-16)', async () => {
    // The same status code, twice, with the only difference in the body. A client keyed on
    // `response.status` cannot tell these apart and would show a database-is-updating panel to
    // someone who has never built a database. This is AD-16's central rule made executable at
    // the root for the first time.
    answering(refusal('database_unavailable', 503))
    render(<App />)
    await settle()

    expect(screen.getByRole('region', { name: 'Card database is updating.' })).toBeVisible()
    expect(screen.queryByRole('region', { name: 'Card database not set up yet.' })).toBeNull()
  })

  it('shows the bug panel for a 500, and its restart line', async () => {
    answering(refusal('internal_error', 500))
    render(<App />)
    await settle()

    expect(screen.getByRole('region', { name: 'The companion hit a bug.' })).toBeVisible()
  })

  it('does not crash on a body the contract never promised (AC 8, AC 9)', async () => {
    // The end-to-end half of `panel.test.ts`: an out-of-union token delivered as untyped JSON,
    // all the way to a render. `STATE_COPY[state]` has no fallback branch, so without the
    // boundary's clamp this render throws and the app shows a blank screen — the error page the
    // whole story exists to ban. Probe (d) removes the clamp and this is what must break.
    answering(new Response('{"reason": "quantum_flux_capacitor_failed"}', { status: 503 }))
    render(<App />)
    await settle()

    expect(screen.getByRole('region', { name: 'The companion hit a bug.' })).toBeVisible()
  })

  it('does not crash on a 503 with no body at all (AC 9)', async () => {
    answering(new Response(null, { status: 503 }))
    render(<App />)
    await settle()

    expect(screen.getByRole('region', { name: 'The companion hit a bug.' })).toBeVisible()
  })

  it('does not crash when the backend cannot be reached at all (AC 9)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )
    render(<App />)
    await settle()

    // No response means no state was decided, so the initial panel stands and the poll keeps
    // trying. `disconnected` — the panel that describes a lost backend — is **c5-6's** by
    // `CLIENT_ONLY_STATES`; ledgered in deferred-work.md so the residue has a named home.
    expect(screen.getByRole('region', { name: 'No deck on the glass.' })).toBeVisible()
  })
})

/**
 * FR-22, which is the story's headline and the one claim no unit test can carry (AC 4).
 *
 * ONE MOUNT. Two answers. No remount, no user action, no `location.reload()`. A test that
 * unmounted and re-rendered between the two responses would pass while FR-22 was false, and that
 * is the shape probe (f) plants: the epic's shared review theme — *the wiring is right and
 * nothing asserts the wiring* — wearing this story's costume.
 */
describe('the app comes alive on its own (AC 4, FR-22)', () => {
  it('transitions from the database panel to the deck list with no refresh', async () => {
    const fetchMock = answering(
      refusal('database_not_initialized', 503),
      decks('Boros Aggro', 'Dimir Mill'),
    )

    render(<App />)
    await settle()
    expect(screen.getByRole('region', { name: 'Card database not set up yet.' })).toBeVisible()

    // The landmarks BEFORE the transition, captured as node identities. If the app were torn
    // down and re-created between the two answers, these would not be the same objects
    // afterwards — which is what makes "no remount" an assertion rather than a description.
    const main = screen.getByRole('main')
    const contentinfo = screen.getByRole('contentinfo')

    await advance(2_000)

    expect(screen.getByRole('region', { name: 'No deck on the glass.' })).toBeVisible()
    expect(screen.queryByRole('region', { name: 'Card database not set up yet.' })).toBeNull()
    expect(screen.getByRole('main')).toBe(main)
    expect(screen.getByRole('contentinfo')).toBe(contentinfo)

    // Two polls from one mount — the transition is a second ANSWER, not a second render pass.
    //
    // Route-scoped at c4-2 for the reason the "stops polling" test below spells out: the raw
    // total now includes the deck boot's own request, so only a count of `/api/decks` still says
    // anything about the POLL. The claim is unchanged and the number is unchanged.
    expect(callsTo(fetchMock, '/api/decks')).toBe(2)
  })

  it('lists the deck names beneath the panel, non-clickable, once they arrive', async () => {
    answering(refusal('database_not_initialized', 503), decks('Boros Aggro', 'Dimir Mill'))

    render(<App />)
    await settle()
    // Nothing to list yet, and nothing pretending there is.
    expect(screen.queryByText('Boros Aggro')).toBeNull()

    await advance(2_000)

    const panel = screen.getByRole('region', { name: 'No deck on the glass.' })
    expect(within(panel).getByText('Boros Aggro')).toBeVisible()
    expect(within(panel).getByText('Dimir Mill')).toBeVisible()
    // `EXPERIENCE.md`: "names only, non-clickable — the agent drives".
    expect(within(panel).queryAllByRole('link')).toHaveLength(0)
    expect(within(panel).queryAllByRole('button')).toHaveLength(0)
  })

  it('renders an empty deck list as nothing extra — the ordinary fresh answer (AC 5)', async () => {
    answering(refusal('database_not_initialized', 503), decks())

    render(<App />)
    await settle()
    await advance(2_000)

    const panel = screen.getByRole('region', { name: 'No deck on the glass.' })
    expect(within(panel).queryAllByRole('listitem')).toHaveLength(0)
    expect(within(panel).queryAllByRole('list')).toHaveLength(0)
  })

  it('stops polling once the database is there — the map says so (AC 7)', async () => {
    const fetchMock = answering(decks('Boros Aggro'))

    render(<App />)
    await settle()
    await advance(10 * 60_000)

    // `RETRIES_QUIETLY['no-active-deck']` is false: the agent sets the deck and a `deck_changed`
    // event delivers it (c5-x). Ten minutes of a mounted, idle tab must not be ten minutes of
    // requests.
    //
    // **ONE OF THE TWO PRE-EXISTING ASSERTIONS c4-2 CHANGED (the other is the FR-22 transition
    // test's count above), and it is strengthened rather than
    // relaxed.** It read `expect(fetchMock).toHaveBeenCalledTimes(1)`, which counted the poll
    // only because the poll was the only caller in the app. c4-2 adds a second, non-polling
    // caller, so a raw total can no longer say anything about the POLL — the property this test
    // is named for. Counting the route makes the claim directly, and the total below pins the
    // other half: the boot's one active-deck request, and nothing else, for ten minutes.
    expect(callsTo(fetchMock, '/api/decks')).toBe(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})

/**
 * The deck bootstrap, at the root, from one mount (story c4-2, AC 1, 6, 7, 9, 12, 17, 19, 20).
 *
 * FR-07's claim — *"a fresh tab shows my deck rather than assuming there isn't one"* — is about
 * what a human sees on a page they did not touch, so it can only be made HERE, the way the FR-22
 * block above is written: ONE mount, real `fetch`, no remount between the two answers. A test
 * that rendered the store's output directly would prove the store, not the boot.
 */
describe('a cold open finds the deck and puts it on the glass (AC 1, FR-07)', () => {
  it('asks both routes, in order, and renders the deck name in the h1 (AC 19)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    const fetchMock = answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    expect(callsTo(fetchMock, '/api/active-deck')).toBe(1)
    expect(callsTo(fetchMock, `/api/deck/${ATRAXA_DECK_ID}`)).toBe(1)
    // C3 retro F2: the kicker and the `h1` stop saying the same words. `AppShell` is not edited —
    // the element, its level and its position are exactly where c2-6 put them.
    expect(
      screen.getByRole('heading', { level: 1, name: 'Atraxa Counter Cabinet v2 (owned)' }),
    ).toBeVisible()
    expect(screen.queryByRole('heading', { level: 1, name: 'Artificial Planeswalker' })).toBeNull()
  })

  it('fills the header badges with the format and the size (AC 20)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail({ sideboard_count: 15 }))
    answering(decks())

    render(<App />)
    await settle()

    const banner = screen.getByRole('banner')
    expect(within(banner).getByText('brawl')).toBeVisible()
    expect(within(banner).getByText('100')).toBeVisible()
    expect(within(banner).getByText('maindeck')).toBeVisible()
    expect(within(banner).getByText('15')).toBeVisible()
    // …and the placeholder they displace is gone, which is what makes this a FILLED slot rather
    // than a fillable one — the c2-10 assertion shape, applied to the badges.
    expect(banner.textContent).not.toContain('Format and size badges land here')
  })

  it('displaces the system panel, and says so honestly in the left column (AC 6)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // A deck, or a panel, never both.
    expect(screen.queryByRole('region', { name: 'No deck on the glass.' })).toBeNull()
    // The declared consequence, asserted rather than discovered: with no grid until c4-4, the
    // shell's own placeholder is what fills the vacated column — the same displacement c2-9 and
    // c2-10 accepted, and the thing that makes c4-4's slot findable by its own id.
    expect(screen.getByText(/The card-art grid lands here — c4-4/)).toBeVisible()
  })

  it('seeds the card cache from the payload, at no extra request (AC 17)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    const fetchMock = answering(decks())

    render(<App />)
    await settle()

    expect(useCardStore.getState().cards['id-Llanowar Elves']?.status).toBe('summary')
    expect(useCardStore.getState().cards['id-Forest']?.status).toBe('summary')
    // Two cards in the cache, and NOT ONE request to `/api/cards/`. Measured on the real 99-tile
    // deck: 38,182 bytes already in hand against 212,436 bytes over 99 requests.
    expect(callsTo(fetchMock, '/api/cards/')).toBe(0)
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('shows the no-active-deck panel when there is genuinely no deck (AC 7)', async () => {
    booting(activeDeck(null))
    answering(decks('Boros Aggro'))

    render(<App />)
    await settle()

    // FR-07's ordinary case: the slot dies with the backend process. The panel and its names are
    // the poll's, unchanged, and the `h1` falls back to `filled()`'s value (c2-6 Q3).
    const panel = screen.getByRole('region', { name: 'No deck on the glass.' })
    expect(within(panel).getByText('Boros Aggro')).toBeVisible()
    expect(screen.getByRole('heading', { level: 1, name: 'Artificial Planeswalker' })).toBeVisible()
  })
})

describe('a deck refusal reaches the glass as a PANEL, never as a status code (AC 8, 9, 11)', () => {
  it('clears a 404 to the no-active-deck state, with the poll’s names (FR-11, AC 8)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), refusal('deck_not_found', 404))
    answering(decks('Boros Aggro', 'Dimir Mill'))

    render(<App />)
    await settle()

    const panel = screen.getByRole('region', { name: 'No deck on the glass.' })
    expect(within(panel).getByText('Boros Aggro')).toBeVisible()
    // Nothing of the deck survives the clearing — probe (d) at the root.
    expect(screen.queryByRole('heading', { level: 1, name: /Atraxa/ })).toBeNull()
  })

  it.each([
    ['database_not_initialized', 'Card database not set up yet.'],
    ['database_unavailable', 'Card database is updating.'],
  ])('turns a 503 %s on the DECK read into its own panel (AD-16, AC 9)', async (reason, name) => {
    // Two 503s, two panels, chosen from the TOKEN — and the poll is deliberately answering `200`
    // underneath, so this can only be the deck path's decision. That is what makes the assertion
    // non-vacuous: with the poll agreeing, it would pass no matter which route decided.
    booting(activeDeck(ATRAXA_DECK_ID), refusal(reason, 503))
    answering(decks('Boros Aggro'))

    render(<App />)
    await settle()

    expect(screen.getByRole('region', { name })).toBeVisible()
  })

  it('answers a 400 on the deck read with no-active-deck, not the bug panel (Q5, AC 11)', async () => {
    booting(activeDeck('an id the agent typed'), refusal('invalid_request', 400))
    answering(decks('Boros Aggro'))

    render(<App />)
    await settle()

    expect(screen.getByRole('region', { name: 'No deck on the glass.' })).toBeVisible()
    expect(screen.queryByRole('region', { name: 'The companion hit a bug.' })).toBeNull()
  })

  it('leaves no ghost deck in the store after clearing — probe (d), at the root', async () => {
    // **The only honest home for this claim**, and a probe is why it moved here. The same
    // assertion in `deck.test.ts` supplied its OWN `onUpdate` and therefore never touched the
    // writer `useDeckState` actually uses — two successive probes that broke production's writer
    // both stayed green there. Rendering `App` is what puts the production hook, the production
    // effect and the production writer in the path.
    useDeckStore.setState({
      deck: {
        status: 'deck',
        detail: {
          id: ATRAXA_DECK_ID,
          name: 'Ghost Deck',
          format: 'brawl',
          strategy: null,
          color_identity: [],
          tags: [],
          mainboard_count: 1,
          sideboard_count: 0,
          distinct_cards: 1,
          created_at: '2026-07-01T00:00:00Z',
          updated_at: '2026-08-01T00:00:00Z',
          cards: [],
        },
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
    booting(activeDeck(ATRAXA_DECK_ID), refusal('deck_not_found', 404))
    answering(decks('Boros Aggro'))

    render(<App />)
    await settle()

    const deck = useDeckStore.getState().deck
    expect(deck).toEqual({ status: 'none' })
    // A merge would leave `detail` beside `status: 'none'` — satisfying every consumer that
    // narrows on `status`, while the ghost's name is one property access away from the screen.
    expect('detail' in deck).toBe(false)
    expect(screen.queryByRole('heading', { level: 1, name: 'Ghost Deck' })).toBeNull()
  })

  it('never renders a bare status code anywhere — probe (f)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), refusal('database_unavailable', 503))
    answering(decks())

    render(<App />)
    await settle()

    expect(document.body.textContent).not.toMatch(/\b(503|404|400|500)\b/)
  })
})

/**
 * The recovery re-drive (review finding on AC 9/FR-22): a deck refusal must not outlive the
 * condition it reported. Before this fix, a cold open during a DB build settled
 * `{status:'refused'}` and NOTHING ever left that state — when the build finished, the poll
 * recovered to `200` while the glass stayed on the stale 503 panel until a manual reload, and
 * the stalled escalation was invisible behind it. The fix is edge-triggered: the poll's panel
 * transitioning INTO `no-active-deck` re-drives the boot once, and only while no deck is loaded.
 */
describe('a deck refusal does not outlive the condition it reported (FR-22)', () => {
  it('re-drives the boot when the poll recovers, and the deck comes alive with no refresh', async () => {
    // The backend timeline, modelled honestly: while the DB is building, BOTH the poll and the
    // deck read answer `database_not_initialized`; when the build finishes, both routes heal.
    booting(activeDeck(ATRAXA_DECK_ID), refusal('database_not_initialized', 503))
    const fetchMock = answering(
      refusal('database_not_initialized', 503),
      decks('Atraxa Counter Cabinet v2 (owned)'),
    )

    render(<App />)
    await settle()
    // The deck refusal's own panel is on the glass — the AC 9 state, one mount, no remount.
    expect(screen.getByRole('region', { name: 'Card database not set up yet.' })).toBeVisible()

    // The DB build finishes: from here every answer is healthy.
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    await advance(2_000)

    // The poll's recovery EDGE re-drove the boot: the deck is on the glass, from the same mount.
    expect(
      screen.getByRole('heading', { level: 1, name: 'Atraxa Counter Cabinet v2 (owned)' }),
    ).toBeVisible()
    expect(screen.queryByRole('region', { name: 'Card database not set up yet.' })).toBeNull()
    // Exactly TWO boots — the mount's and the edge's — not a poll of its own. Ten further
    // minutes of a healthy, idle tab add nothing: the edge fired once and cannot re-fire
    // without the panel leaving `no-active-deck` first.
    await advance(10 * 60_000)
    expect(callsTo(fetchMock, '/api/active-deck')).toBe(2)
    expect(callsTo(fetchMock, '/api/deck/')).toBe(2)
  })

  it('heals a transient boot blip the same way, when a poll transition follows', async () => {
    // The unreachable→'none' half of the finding: the glass said "No deck on the glass." about
    // a deck whose read was merely unlucky. Covered by the same edge — with the declared
    // residue: a blip with the poll ALREADY settled healthy has no later edge, and waits for
    // reload or c5-6's reconnect. A hand-rolled stub rather than `answering`, because the shape
    // under test is a route that REJECTS once and then heals, which the fixture cannot say.
    let deckRead: () => Promise<Response> = () => Promise.reject(new TypeError('Failed to fetch'))
    let pollAnswer = refusal('database_not_initialized', 503)
    vi.stubGlobal(
      'fetch',
      vi.fn((input?: unknown) => {
        const path = String(input)
        if (path === '/api/active-deck') return Promise.resolve(activeDeck(ATRAXA_DECK_ID))
        if (path.startsWith('/api/deck/')) return deckRead()
        return Promise.resolve(pollAnswer.clone())
      }),
    )

    render(<App />)
    await settle()
    expect(screen.queryByRole('heading', { level: 1, name: /Atraxa/ })).toBeNull()

    // The network heals and the poll recovers in the same window: 503 → 200 is the edge.
    deckRead = () => Promise.resolve(deckDetail())
    pollAnswer = decks('Atraxa Counter Cabinet v2 (owned)')
    await advance(2_000)

    expect(
      screen.getByRole('heading', { level: 1, name: 'Atraxa Counter Cabinet v2 (owned)' }),
    ).toBeVisible()
  })
})

describe('the boot does not poll, whatever the backend says (AC 12, Q6)', () => {
  it('issues ONE deck request in ten minutes against a forever-503 id', async () => {
    // The 503-outranks-400 trap, at the root: a backend with no database answers
    // `database_not_initialized` to an id that could NEVER succeed, and that token is one
    // `RETRIES_QUIETLY` says to retry. The boot is immune because it has no "again" at all —
    // and this is the assertion that says so rather than the docstring.
    booting(activeDeck('an-id-that-can-never-resolve'), refusal('database_not_initialized', 503))
    const fetchMock = answering(refusal('database_not_initialized', 503))

    render(<App />)
    await settle()
    await advance(10 * 60_000)

    expect(callsTo(fetchMock, '/api/active-deck')).toBe(1)
    expect(callsTo(fetchMock, '/api/deck/')).toBe(1)
    // …while the POLL, which is the thing that IS meant to retry, has been busy the whole time.
    // Asserting both in one test is what stops "nothing retries" reading as "the boot is right".
    expect(callsTo(fetchMock, '/api/decks')).toBeGreaterThan(4)
  })

  it('boots exactly once from one mount, whatever re-renders happen', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    const fetchMock = answering(refusal('database_not_initialized', 503), decks('A'))

    render(<App />)
    await settle()
    // A poll transition re-renders the whole tree; the boot must not re-run on a render.
    await advance(2_000)

    expect(callsTo(fetchMock, '/api/active-deck')).toBe(1)
    expect(callsTo(fetchMock, '/api/deck/')).toBe(1)
  })
})

/**
 * The attribution on every top-level surface (story c2-10, AC 15, NFR-08, UX-DR32).
 *
 * THIS IS A RELEASE CONDITION, NOT A DESIGN CHOICE — `DESIGN.md:375` says so in bold. So it is
 * asserted at the ROOT, where a human would look, rather than only in `Footer.test.tsx` where
 * the component is rendered in isolation. c2-9's review measured the exact hole this closes:
 * reverting `App.tsx`'s `left` prop kept all 487 tests green, because nothing asserted the
 * wiring one layer above the component. Reverting the `footer` prop must not stay green.
 *
 * "EVERY SURFACE" IS STRUCTURAL, NOT ENUMERATED (Q3, Brad 2026-07-30). There is one `AppShell`,
 * one `footer` slot and no router, so every surface renders through `App`. An enumerated list of
 * surfaces would be a list its author thought of — this epic's standing finding. The rule is
 * written into `App.tsx` and `ui/README.md` where the next surface's author will read it, and
 * the second test below is what makes it a gate rather than a note.
 */
describe('the attribution is on the surface (c2-10, AC 15)', () => {
  it('renders inside the contentinfo landmark, by role and by text', () => {
    render(<App />)

    const contentinfo = screen.getByRole('contentinfo')
    // BY TEXT, against the copy module's own join — so this assertion cannot drift from the
    // artefact independently of `tests/attribution.test.ts`. `toHaveTextContent` would be a
    // substring check; the landmark's whole text is the sentence and nothing else.
    expect(contentinfo.textContent).toBe(sentenceOf())
  })

  it('exposes both attribution links from the rendered app, not just from the component', () => {
    render(<App />)

    const links = within(screen.getByRole('contentinfo')).getAllByRole('link')
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      'https://scryfall.com/docs/api',
      'https://company.wizards.com/en/legal/fancontentpolicy',
    ])
  })

  it('leaves no surface without it — the slot is filled, not merely fillable (Q3)', () => {
    render(<App />)

    // The structural half. The shell renders a PLACEHOLDER whenever `footer` is empty, so a
    // reverted or dropped `footer` prop presents as the placeholder line rather than as an
    // empty landmark — which a "is the landmark non-empty" check would happily accept. Naming
    // the placeholder is what makes that specific regression fail here.
    expect(screen.getByRole('contentinfo').textContent).not.toContain('lands here')
    expect(screen.queryByText(/Scryfall and Fan Content attribution lands here/)).toBeNull()
  })

  it('survives every system state, because it is not in the changing slot', async () => {
    // The left column is now wire-driven, and the footer is not. Asserted after a transition
    // rather than only at mount, because "correct from day one and forever" is the claim
    // c2-10 made and this is the first story that could have broken it.
    answering(refusal('database_not_initialized', 503), decks('Boros Aggro'))

    render(<App />)
    await settle()
    expect(screen.getByRole('contentinfo').textContent).toBe(sentenceOf())

    await advance(2_000)
    expect(screen.getByRole('contentinfo').textContent).toBe(sentenceOf())
  })
})
