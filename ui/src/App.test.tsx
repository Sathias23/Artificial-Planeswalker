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

// `fireEvent` joins at c6-7: the suggestion rows are the first content in this file whose
// contract is a POINTER one (hover sets the detail target, click pins), and `element.click()` —
// this file's idiom for the tile and pill tests — dispatches no `mouseenter` at all.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { sentenceOf } from './components/Footer/copy'
import { CLOSE_PILL_LABEL } from './containers/AgentView/copy'
import { resetDeckMemory } from './containers/CardDetail/deckMemory'
import { EMPTY_DECK_LINE } from './containers/CardGrid/copy'
import { CONNECTION_WORDS, pillText } from './containers/ConnectionPill/copy'
import { emptyPushLine } from './containers/SuggestionsView/copy'
import {
  SUGGESTIONS_VIEW_TITLE,
  closeAgentView,
  openAgentView,
  resetAgentView,
  useAgentViewStore,
} from './state/agentView'
import { MAX_ATTEMPTS_PER_CARD, hydrateCard, resetCardCache, useCardStore } from './state/cards'
import { resetDeckState, useDeckStore } from './state/deck'
import { resetFormatCheckState } from './state/formatCheck'
import { resetInspection, useInspectionStore } from './state/inspection'
import { DISCONNECTED_AFTER_MS, SOCKET_BASE_MS } from './state/socket'
import { INITIAL_SYSTEM_STATE, useSystemStore } from './state/systemState'

/** One canned answer, built the way the backend builds it: a token, and nothing else. */
const refusal = (reason: string, status: number) =>
  new Response(JSON.stringify({ reason }), { status })

const decks = (...names: string[]) =>
  new Response(JSON.stringify(names.map((name) => ({ id: name, name }))), { status: 200 })

/** `GET /api/active-deck`'s body. `null` is the answer a fresh backend gives (FR-07). */
const activeDeck = (deckId: string | null) =>
  new Response(JSON.stringify({ deck_id: deckId }), { status: 200 })

/**
 * `GET /api/session`'s body — story c5-6's FOURTH boot-time route, and the first credential the
 * browser has ever held.
 *
 * A counter rather than a constant, because a reused ticket is exactly the defect AD-5 exists to
 * prevent and a fixture that handed out one string could not show the difference. The real
 * backend mints ~43 url-safe characters per call and pops each on presentation.
 */
let ticketsMinted = 0
const sessionTicket = () => {
  ticketsMinted += 1
  return new Response(JSON.stringify({ ticket: `ticket-${ticketsMinted}` }), {
    status: 200,
    headers: { 'Cache-Control': 'no-store' },
  })
}

/**
 * Every socket the app has opened this test, newest last (story c5-6).
 *
 * ⚠️ **jsdom DOES provide `WebSocket`, and the story's Dev Notes predicted it did not** —
 * measured 2026-08-08 and recorded as a falsified prediction rather than quietly worked around.
 * That makes the stub below mandatory rather than merely convenient: without it every one of this
 * file's ~70 mounts would attempt a real TCP connection to `ws://localhost:3000/ws?ticket=…`,
 * which is slow, noisy, and would make the retry schedule depend on how fast the OS refuses a
 * connection.
 *
 * The stub is the transport and NOTHING else — the URL construction, the mint, the loop, the
 * backoff, the two exhaustion gates, the store write and the `surfaceOf` arm are all the shipped
 * ones. That is the same bargain `fetch` has had in this file since c3-9.
 */
const sockets: FakeSocket[] = []

class FakeSocket {
  onopen: (() => void) | null = null
  onmessage: ((event: { data: unknown }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = 0
  // A plain field rather than a parameter property: `erasableSyntaxOnly` is on, and a parameter
  // property emits code.
  readonly url: string
  constructor(url: string) {
    this.url = url
    sockets.push(this)
  }
  close() {
    this.closed += 1
  }
}

/** The socket the app is currently holding. */
const socket = () => sockets[sockets.length - 1]

/**
 * Drive one socket event and let everything it started settle.
 *
 * The `advanceTimersByTimeAsync(0)` is not decoration: a socket event fires store writes and, on
 * a reconnect, a whole re-boot — two awaited requests — so a helper that only dispatched would
 * leave every assertion racing the microtask queue it started.
 */
const driveSocket = (fire: () => void) =>
  act(async () => {
    fire()
    await vi.advanceTimersByTimeAsync(0)
  })

/** The upgrade succeeds. */
const connect = () => driveSocket(() => socket().onopen?.())

/** The socket drops — a restart, a refused handshake, a lost process. All one thing on the wire. */
const drop = () => driveSocket(() => socket().onclose?.())

/**
 * One agent frame arrives, exactly as the backend serialises it.
 *
 * `id` became a parameter at c6-6, because that is the story where the envelope's identity stops
 * being inert: it is the REPLACE KEY, so two suggestions pushes that share the default
 * `id-suggestions` are the same push by the wire's own de-duplication rule and the view is
 * correct not to re-announce. Every existing caller keeps the default and its behaviour.
 */
const push = (kind: string, payload: Record<string, unknown> = {}, id = `id-${kind}`) =>
  driveSocket(() =>
    socket().onmessage?.({
      data: JSON.stringify({ kind, id, ts: '2026-08-08T00:00:00Z', payload }),
    }),
  )

const ATRAXA_DECK_ID = '813d0434-1bed-4419-bf9d-d9e4070704c4'

/**
 * One deck row, with the two derivation-bearing fields REAL rather than blanked (c4-9).
 *
 * `mana_cost` and `cmc` were hard-coded to `''` and `0` for every card this helper built, which
 * was harmless while the only derivation reading them bucketed everything at `cmc <= 1` anyway
 * — and stopped being harmless the moment a panel counted PIPS: `Llanowar Elves` below is a real
 * card whose real cost is `{G}`, and a fixture that gives it a blank one is the c4-8 High in
 * miniature (a real card name carrying invented field values, under which a derivation is never
 * exercised at all). Both are parameters now, both default to the old values so every existing
 * call site is unchanged, and the one card that has a real cost is given it.
 */
const deckCard = (name: string, typeLine: string, quantity = 1, manaCost = '', cmc = 0) => ({
  card_id: `id-${name}`,
  quantity,
  sideboard: false,
  commander: false,
  card: {
    id: `id-${name}`,
    name,
    mana_cost: manaCost,
    cmc,
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
        // The real printing's real values, measured at `1ed2e83`: `{G}`, cmc 1. (The corpus
        // also holds a TOKEN `Llanowar Elves` with a blank cost and the type line
        // `'Token Creature — Elf Druid'`; this is the other one.) The curve is unmoved —
        // `bucketOf` folds `cmc <= 1` into bucket 1 either way — and the colour bar now has
        // exactly one green pip to draw, which is what makes c4-9's mount observable here.
        deckCard('Llanowar Elves', 'Creature — Elf Druid', 1, '{G}', 1),
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
/**
 * What `GET /api/deck/{id}/format-check` answers — story c4-10's third boot-time route.
 *
 * Defaults to the REAL all-pass Standard report (`formatCheckReport()` below), so every existing
 * deck-view test in this file gets a panel that draws rather than one that silently does not.
 */
let bootFormatCheck: Response = formatCheckReport()

const booting = (active: Response, deck?: Response, formatCheck?: Response) => {
  bootActive = active
  if (deck !== undefined) bootDeck = deck
  if (formatCheck !== undefined) bootFormatCheck = formatCheck
}

/**
 * `GET /api/deck/{deck_id}/format-check`'s body — story c4-10's route (AC 26).
 *
 * ✅ **VERIFIED REAL BODY, SYNTHETIC PAIRING** (c4-10 review): the BODY is the response the
 * running backend gives for a real all-pass Standard deck, read out at `4e31ea7` by driving the
 * real ASGI app against the shipped database — six rows in `CHECK_ORDER`, five passes and the
 * permanent rotation advisory, which is what 35 of the 40 real decks look like. But this harness
 * serves it beside `ATRAXA_DECK_ID`'s TWO-CARD deck detail, a pairing no backend would produce
 * (the real answer for that deck is a size violation): the routes here are each real and
 * mutually inconsistent, which is fine while nothing compares them and is declared so the day
 * something does. Declared here rather than imported from `src/state/formatCheck.fixtures.ts`
 * because this fixture must be a wire BODY (a JSON string), not a typed value, and stringifying
 * the typed one would couple this harness to that module's shape for nothing.
 */
function formatCheckReport(overrides: Record<string, unknown> = {}) {
  return new Response(
    JSON.stringify({
      is_legal: true,
      format: 'standard',
      format_recognized: true,
      mainboard_count: 60,
      sideboard_count: 0,
      rows: [
        { check: 'legality', status: 'pass', detail: 'Every card is legal in standard.' },
        { check: 'size', status: 'pass', detail: 'Mainboard has 60 cards; the minimum is 60.' },
        {
          check: 'copy_limit',
          status: 'pass',
          detail: 'No card exceeds the copy limit; basic lands are exempt.',
        },
        { check: 'sideboard', status: 'pass', detail: 'Sideboard has 0 cards; the maximum is 15.' },
        { check: 'banned', status: 'pass', detail: 'No card is banned in standard.' },
        {
          check: 'rotation',
          status: 'advisory',
          detail:
            'Rotation exposure cannot be checked: the local card data carries no set release dates.',
        },
      ],
      ...overrides,
    }),
    { status: 200 },
  )
}

/**
 * `GET /api/cards/{card_id}`'s body — the hydration route, which acquired its FIRST production
 * caller in story c4-5.
 *
 * Two fields are all `cardOf` validates (`id` and `name`, both non-blank), and the rest are here
 * because the detail panel draws them. Routed below so that the panel's one hydration is a
 * modelled answer rather than whatever the poll happened to be handing out — which is the same
 * repair c4-2 made when it turned this fixture route-aware for a second caller.
 */
/**
 * The six real MDFC Pathways in `Atraxa Counter Cabinet v2` — the deck's 6 flip controls
 * (c4-6's measurement: the only flippable rows in that deck), under the full `A // B` names the
 * `cards` table actually stores (VERIFIED REAL against the live DB at code review 2026-08-07).
 * Named here so the hydration route below can answer them with two imaged faces, which is what
 * makes a tile grow a flip control.
 */
const PATHWAY_NAMES: readonly string[] = [
  'Branchloft Pathway // Boulderloft Pathway',
  'Barkchannel Pathway // Tidechannel Pathway',
  'Brightclimb Pathway // Grimclimb Pathway',
  'Clearwater Pathway // Murkwater Pathway',
  'Darkbore Pathway // Slitherbore Pathway',
  'Hengegate Pathway // Mistgate Pathway',
]

const cardRecord = (name: string) =>
  new Response(
    JSON.stringify({
      id: `id-${name}`,
      name,
      oracle_id: `oracle-${name}`,
      mana_cost: '{G}',
      cmc: 1,
      type_line: 'Creature — Elf Druid',
      oracle_text: 'Tap: Add G.',
      colors: ['G'],
      color_identity: ['G'],
      rarity: 'common',
      set_code: 'tst',
      set_name: 'Test Set',
      collector_number: '1',
      legalities: {},
      games: ['paper'],
      // Shape C — per-face images, no top-level map — for the six Pathways, so the corridor pin
      // below renders their flip controls exactly as the live backend makes them render. Each
      // half of the stored `A // B` name is its face's name, which is how the corpus spells it.
      ...(PATHWAY_NAMES.includes(name)
        ? {
            image_uris: null,
            card_faces: name.split(' // ').map((faceName, index) => ({
              name: faceName,
              mana_cost: '',
              type_line: 'Land',
              oracle_text: '',
              image_uris: { normal: `https://cards.test/${index === 0 ? 'front' : 'back'}.jpg` },
            })),
          }
        : {}),
    }),
    { status: 200 },
  )

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
    // ⚠️ FIRST, AND THE ORDER IS THE WHOLE POINT (c4-10). `/api/deck/{id}/format-check` STARTS
    // WITH `/api/deck/`, so without this branch placed above the next line the format-check
    // request is answered with the deck-detail body — a `200` that is not the contract, silently,
    // in the one file that exercises the whole path end to end. `formatCheckOf` would report it
    // as a contract violation, the panel would render nothing, and every assertion about the
    // panel's ABSENCE would pass for entirely the wrong reason. There is a SECOND prefix-routing
    // fixture in this file (see `heals a transient boot blip`) and it carries the same branch:
    // fixing one and not the other is the half-repair this comment exists to prevent.
    if (path.endsWith('/format-check')) return Promise.resolve(bootFormatCheck.clone())
    if (path.startsWith('/api/deck/')) return Promise.resolve(bootDeck.clone())
    if (path === '/api/active-deck') return Promise.resolve(bootActive.clone())
    // c5-6's FOURTH route, and the fixture's fourth branch. Unrouted, this request would fall
    // through to the poll's canned answer — a deck array, which `ticketOf` reads as a contract
    // violation — so the loop would fail, back off, and retry through every `advance()` in this
    // file. Not a hypothetical: it is what the suite did before this line was added, and it turned
    // one test's "2 requests" into 26.
    if (path === '/api/session') return Promise.resolve(sessionTicket())
    // c4-5's third caller: the detail panel hydrates its inspection target. Answered from the id
    // in the path, because unlike the two boot routes there is no single "the" card — the panel
    // asks for whichever one it is showing, and a test that pinned one answer for all of them
    // could not tell "hydrates the cold-open card" from "hydrates everything".
    if (path.startsWith('/api/cards/')) {
      return Promise.resolve(cardRecord(decodeURIComponent(path.slice('/api/cards/id-'.length))))
    }
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

/**
 * The two deck-prefixed routes, counted APART (c4-10).
 *
 * `callsTo` matches by prefix, and `/api/deck/{id}/format-check` starts with `/api/deck/` — so
 * from this story onwards `callsTo(mock, '/api/deck/')` is the SUM of two independent reads and
 * says nothing about either. Every request-count assertion that means "the deck detail" uses the
 * first of these; the one that means "the format check" uses the second. Keeping `callsTo`
 * unchanged is deliberate: its other callers (`/api/decks`, `/api/active-deck`) are unaffected,
 * and narrowing it would have moved the problem rather than named it.
 */
const deckDetailCalls = (fetchMock: ReturnType<typeof answering>) =>
  fetchMock.mock.calls.filter(
    ([input]) => String(input).startsWith('/api/deck/') && !String(input).endsWith('/format-check'),
  ).length

const formatCheckCalls = (fetchMock: ReturnType<typeof answering>) =>
  fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/format-check')).length

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
  resetFormatCheckState()
  bootActive = activeDeck(null)
  bootDeck = refusal('deck_not_found', 404)
  bootFormatCheck = formatCheckReport()
  sockets.length = 0
  ticketsMinted = 0
  // The socket is CREATED by every mount and left un-opened unless a test opens it — see
  // {@link sockets}. Un-opened rather than auto-opening, because "the upgrade is in flight" is
  // the quiet default: it costs exactly one `GET /api/session` per mount and produces no
  // failures, so no test inherits a backoff it did not ask for.
  vi.stubGlobal('WebSocket', FakeSocket)
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
    // `CLIENT_ONLY_STATES`, and it now ships: this assertion is about the FIRST SIXTY SECONDS,
    // which is deliberately unchanged (a backend restart must not flash a whole-screen panel).
    // The other side of that threshold is asserted in `the page reconnects on its own`, which
    // closes the dw:3451 residue this comment used to record as open.
    expect(screen.getByRole('region', { name: 'No deck on the glass.' })).toBeVisible()
  })

  // c4-8 AC 2's "absent behind EVERY state panel", made a fact rather than an argument (added
  // at review 2026-08-06). The shipped draft asserted the curve's absence behind the two
  // 503 deck-read panels and covered the rest with a structural comment ("the left slot
  // renders a StatePanel on every non-deck arm") — reasonable, and exactly the shape a later
  // per-arm regression walks through unnoticed. Every distinct panel this file can produce now
  // carries the assertion; the two deck-read 503 arms keep theirs in their own test below.
  const STATE_PANEL_ARMS: [string, () => void][] = [
    ['database-not-set-up (fresh install)', () => {}],
    ['database-updating', () => answering(refusal('database_unavailable', 503))],
    ['internal-error', () => answering(refusal('internal_error', 500))],
    [
      'no-active-deck',
      () => {
        booting(activeDeck(null))
        answering(decks('Boros Aggro'))
      },
    ],
  ]
  it.each(STATE_PANEL_ARMS)(
    'leaves NO analysis panel and NO analysis row behind the %s panel (c4-8/c4-9, AC 3)',
    async (_label, arrange) => {
      arrange()
      render(<App />)
      await settle()

      expect(screen.queryByRole('region', { name: 'Mana curve' })).toBeNull()
      // c4-9's panel rides the SAME `kind === 'deck'` gate, and asserting it per-arm rather
      // than covering it with a structural comment is c4-8's own review finding applied to the
      // sibling that arrived after it.
      expect(screen.queryByRole('region', { name: 'Color distribution' })).toBeNull()
      expect(document.querySelector('.analysis-row')).toBeNull()
      // …and NO format check (c4-10, AC 3). It rides the SAME `kind === 'deck'` gate, inherited
      // from `App.tsx:101-119`'s c4-5 Q14 ruling rather than re-decided — L8 is cited, not
      // re-opened. Asserted per-arm for c4-8's own review reason.
      expect(screen.queryByRole('region', { name: 'Format check' })).toBeNull()
    },
  )

  it.each(STATE_PANEL_ARMS)(
    'issues NO format-check request behind the %s panel (c4-10, AC 3, AC 10)',
    async (_label, arrange) => {
      // ABSENCE OF THE PANEL IS NOT ABSENCE OF THE REQUEST, and only one of the two is visible in
      // the DOM. The effect that drives the read is keyed on the deck id, so a non-deck surface
      // must not reach the wire at all — otherwise the app would be paying a duplicated
      // `get_deck_with_cards` on the backend to populate a panel nothing renders.
      arrange()
      // The current mock, read off the global rather than returned by `arrange` — whose signature
      // is `() => void` and whose members re-stub `fetch` themselves.
      const fetchMock = globalThis.fetch as unknown as ReturnType<typeof answering>
      render(<App />)
      await settle()

      // (The first draft decorated this with `toBeGreaterThanOrEqual(0)` on the deck-detail
      // count — always true, asserting nothing; the c4-10 review deleted it. The format-check
      // absence below is the whole claim.)
      expect(
        fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/format-check')),
        'a format-check request was issued with no deck on the glass',
      ).toHaveLength(0)
    },
  )
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
    // **AND c5-6 MOVES IT TO THREE, WHICH IS THE ASSERTION EARNING ITS KEEP.** The third is the
    // socket's ONE `GET /api/session` — one mint, one upgrade, and then a connection that costs
    // no requests at all for the remaining ten minutes. A reconnect loop that re-minted on a
    // timer, or a socket the fixture failed to route (see `answering`), turns this number into
    // dozens; that is exactly how the missing route was found.
    expect(callsTo(fetchMock, '/api/session')).toBe(1)
    expect(fetchMock).toHaveBeenCalledTimes(3)
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
    // SEPARATED FROM THE FORMAT CHECK (c4-10, AC 10): this read used `callsTo` with the full deck
    // path, which from this story on ALSO matches `/api/deck/{id}/format-check` and would have
    // read 2 while still looking like an assertion about the detail route.
    expect(deckDetailCalls(fetchMock)).toBe(1)
    // …and the third boot-time request, once. Three per mount for a deck view, still a number.
    expect(formatCheckCalls(fetchMock)).toBe(1)
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

    // SCOPED THROUGH THE `h1` RATHER THAN THROUGH `getByRole('banner')`, AND THE REASON IS A
    // MEASURED jsdom FIDELITY LIMIT rather than a change of intent (c4-5).
    //
    // HTML-AAM maps `<header>` to the `banner` landmark ONLY when it is not a descendant of an
    // `article`, `aside`, `main`, `nav` or `section` element. `aria-query` — which
    // testing-library resolves roles through — maps it UNCONDITIONALLY. Measured with a two-
    // header probe: a `<header>` inside `<section aria-label="…">` is reported as a second
    // `banner` here, while a real browser reports one. c4-5's detail panel is the first titled
    // `Panel` on a rendered surface, so its `.panel-header` is the first element to expose the
    // difference — the shipped markup is correct and this suite cannot see that it is.
    //
    // So the shell's header is identified by the thing that actually distinguishes it: it is the
    // one containing the document's `h1`. That is a stronger anchor than "the first banner",
    // which would pass by document order rather than by identity.
    const banner = screen.getByRole('heading', { level: 1 }).closest('header')!
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

    // THIS ASSERTION CHANGED IN c4-4, AND CHANGING IT IS THE POINT. It read
    // `getByText(/The card-art grid lands here — c4-4/)` for two stories: with no grid to put
    // in the vacated column, the shell's own placeholder was what honestly filled it. The grid
    // now displaces that line — the FOURTH application of c2-9's ruling, and the same one.
    // `AppShell.tsx` is untouched and `AppShell.test.tsx` still asserts the placeholder against
    // the component's own props; what changed is which of the two the running app shows.
    expect(screen.queryByText(/The card-art grid lands here/)).toBeNull()

    // …and the C3 retro F1 count moves with it. That action item wants a gate banning
    // story-key-shaped strings from rendered UI text; c4-2 declined it and counted SIX such
    // strings on a real render. This story removes one of the six — the left column's — and the
    // gate itself stays c8-5's. Asserted so the count is a fact rather than a claim.
    expect(document.body.textContent).not.toContain('c4-4')
    expect(document.body.textContent).not.toContain('c4-8')
    // c4-9 too — and as of THIS story it is green by its own panel rather than by a sibling's
    // displacement. All three keys lived in the SAME left-column string, so this one has been
    // off the glass since c4-4; what changes here is that the row that string promised is now
    // FULL. F1 count: the left column contributed three keys to the C3 retro's six, all three
    // gone; `c4-10` is what remains, in the RIGHT column's placeholder. The gate itself stays
    // c8-5's. (This comment named `c4-11` beside it until that story measured the claim and found
    // it false — the skip link renders no story key. See the correction at the end of this test.)
    expect(document.body.textContent).not.toContain('c4-9')

    // THE RIGHT COLUMN'S DISPLACEMENT, THE SAME SHAPE ONE STORY LATER (AC 6, added at review
    // 2026-08-05 — the checkbox predated the assertion). c4-5 fills the right slot with the
    // detail panel, so the shell's own placeholder — the one naming c4-5, c4-7 and c4-10 — is
    // gone from a rendered deck view, and the F1 count drops by three keys at once because all
    // three lived in that single string.
    expect(screen.queryByText(/Card detail — c4-5/)).toBeNull()
    expect(document.body.textContent).not.toContain('c4-5')
    // …and the slot is FILLED, not merely emptied: the panel region is on the glass.
    expect(screen.getByRole('region', { name: 'Card detail' })).toBeVisible()

    // c4-7's OWN DISPLACEMENT (deferral 8, F1). The shell's placeholder named three stories in
    // one string and c4-5 displaced all three at once, so this key was already off the glass
    // before this story mounted anything — what changes at c4-7 is that it is now displaced by
    // its OWN panel rather than by a sibling's. Both halves asserted, because the second is the
    // one that would regress if the mount were dropped.
    expect(document.body.textContent).not.toContain('c4-7')
    const deckListRegion = screen.getByRole('region', { name: 'Deck list' })
    expect(deckListRegion).toBeVisible()
    // PLACEMENT, NOT JUST PRESENCE (AC 1–3, added at review 2026-08-06): the detail panel sits
    // ABOVE the deck list in the right column. Swapping the two Fragment children in `App.tsx`
    // passes every presence assertion in this file; document order is the one thing that notices.
    const detailRegion = screen.getByRole('region', { name: 'Card detail' })
    expect(
      detailRegion.compareDocumentPosition(deckListRegion) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()

    // c4-10's OWN DISPLACEMENT, AND THE RIGHT COLUMN'S THIRD PANEL (c4-10, AC 1, AC 2, AC 3).
    // The NINTH application of the c2-9 ruling, and the story that finally displaces its own key:
    // the shell's right-column placeholder named c4-5, c4-7 and c4-10 in ONE string, so this key
    // has been off a rendered deck view since c4-5 — what changes here is that it is now absent
    // because its OWN panel is present. Both halves asserted, because the second is the one that
    // would regress if the mount were dropped.
    //
    // F1 COUNT: the C3 retro counted six story-key-shaped strings on a real render. The left
    // column's three went at c4-4/c4-8/c4-9 and the right column's three are now all displaced by
    // their own panels. This comment said that left "ONE, `c4-11`, in the skip-link work".
    //
    // ⚠️ MEASURED AT c4-11 AND CORRECTED (Q14). That was wrong twice over, and both halves are
    // worth keeping:
    //
    //   1. The skip link renders NO story key. `c4-11` appears in this repo only inside comments
    //      (`App.tsx`, this file, and ten sites across five other modules) — never as rendered
    //      text. c4-9's and c4-10's records both forward-stated the same claim; all three were
    //      wrong in the same direction.
    //   2. There IS a key still on the glass, and the count of six never included it: `c6-8`, from
    //      `AppShell.tsx:117`'s nav placeholder. `App.tsx` has never passed `nav`, so that string
    //      renders on EVERY surface including this one. The C3 retro's six was itself an
    //      undercount — every assertion in this test names a `c4-*` key, so a `c6-*` one was
    //      invisible to a check that only ever looked for the keys someone had thought of. That is
    //      this epic's coverage-that-reads-as-coverage theme, in a COUNT rather than a guard.
    //
    // So: F1's real remaining count on a rendered deck view is ONE, and it is `c6-8`. Both halves
    // are asserted below rather than left in prose, so the next story inherits a fact.
    expect(document.body.textContent).not.toContain('c4-10')
    expect(document.body.textContent).not.toContain('c4-11')
    expect(document.body.textContent).toContain('c6-8')
    const formatCheckRegion = screen.getByRole('region', { name: 'Format check' })
    expect(formatCheckRegion).toBeVisible()

    // DOCUMENT ORDER, NOT JUST PRESENCE (AC 2). `DESIGN.md:376` writes the column as "card
    // detail, deck list, format check, stacked", in that order. Reordering the three Fragment
    // children passes every presence assertion above; this is the one thing that notices — and
    // it EXTENDS the detail-before-list pair rather than replacing it.
    expect(
      deckListRegion.compareDocumentPosition(formatCheckRegion) & Node.DOCUMENT_POSITION_FOLLOWING,
      'the format check is not beneath the deck list',
    ).toBeTruthy()

    // …and the column has exactly THREE children now, up from two. A count rather than a
    // presence check, so a fourth panel arriving by accident is a decision with a diff.
    const rightColumn = formatCheckRegion.parentElement
    expect(rightColumn?.className).toContain('app-shell-column')
    expect(rightColumn?.children).toHaveLength(3)

    // c4-8's OWN DISPLACEMENT AND ITS PLACEMENT (AC 1, AC 2). The seventh application of the
    // c2-9 ruling and the first on the LEFT slot since c4-4: the curve is mounted, and it is
    // mounted BENEATH the grid inside the analysis row `AppShell.tsx:127` assigned to this
    // story by name.
    const curveRegion = screen.getByRole('region', { name: 'Mana curve' })
    expect(curveRegion).toBeVisible()
    const gridPanel = document.querySelector('.card-grid')
    expect(gridPanel).not.toBeNull()
    expect(
      gridPanel!.compareDocumentPosition(curveRegion) & Node.DOCUMENT_POSITION_FOLLOWING,
      'the mana curve is not beneath the card grid',
    ).toBeTruthy()

    // …and it is inside the ROW rather than a bare third child of the column, because that is
    // what makes c4-9 a one-line addition instead of a layout change (Q6, AC 3).
    const analysisRow = document.querySelector('.analysis-row')
    expect(analysisRow).not.toBeNull()
    expect(analysisRow!.contains(curveRegion)).toBe(true)

    // c4-9's OWN DISPLACEMENT, AND THE ROW'S SECOND CHILD (c4-9, AC 1, AC 2). The EIGHTH
    // application of the c2-9 ruling. This assertion read `toHaveLength(1)` for one story, under
    // a comment promising *"the day c4-9 lands this becomes two"* — this is that day, and the
    // promise is kept with no edit to `App.tsx`'s layout and none at all to `AnalysisRow.tsx`.
    const colourRegion = screen.getByRole('region', { name: 'Color distribution' })
    expect(colourRegion).toBeVisible()
    expect(analysisRow!.contains(colourRegion)).toBe(true)
    expect(analysisRow!.children).toHaveLength(2)

    // DOCUMENT ORDER, NOT JUST PRESENCE (AC 2). Swapping the two children passes every presence
    // assertion above; order is the one thing that notices, and DESIGN.md's layout section
    // writes the pair as *"the mana-curve and color-distribution panels"* in that order.
    expect(
      curveRegion.compareDocumentPosition(colourRegion) & Node.DOCUMENT_POSITION_FOLLOWING,
      'the colour distribution is not the SECOND child of the analysis row',
    ).toBeTruthy()

    // ⚠️ THE 1:1 SHARE ITSELF IS NOT ASSERTED HERE, AND CANNOT BE: jsdom applies no stylesheet,
    // so `flex: 1 1 0` on the child slot is a claim about `AnalysisRow.css` source and is
    // asserted in `shell.test.ts` (AC 2's "read from the stylesheet, not assumed"). The rendered
    // widths are the eye-check's, at 1440px and at UX-DR8's ~1100px floor.
  })

  it('empties the analysis row on a land-only deck — the precondition c4-9 hides it on (Q10)', async () => {
    // c4-8's REVIEW FINDING, AND c4-9's ANSWER TO IT. `<AnalysisRow>` is unconditional in the
    // deck arm, so when BOTH children render null — a land-only deck has no curve and no
    // coloured pips — the row's empty div remains a real flex child of `.app-shell-column`, and
    // the column's 24px panel gap still applied beneath the grid. That was ACCEPTED posture at
    // c4-8, because gating the row in `App.tsx` would have needed the curve's total there: a
    // second derivation of what `curve.ts` owns, for a state NO corpus deck can produce (all 40
    // have a non-empty curve AND at least 2 pips).
    //
    // c4-9 closes it without that derivation: `.analysis-row:empty { display: none }` lets the
    // row answer for itself. What this test can assert in jsdom is the DOM half — the row is
    // present and has NO child nodes, which is exactly the condition `:empty` keys on — and
    // `shell.test.ts` asserts the CSS half against the stylesheet source, because jsdom applies
    // no styles and would report `display` as an empty string either way.
    booting(
      activeDeck(ATRAXA_DECK_ID),
      deckDetail({ cards: [deckCard('Forest', 'Basic Land — Forest', 24)] }),
    )
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // The deck view is on the glass, BOTH panels are hidden, and the row has no children.
    expect(document.querySelector('.card-grid')).not.toBeNull()
    expect(screen.queryByRole('region', { name: 'Mana curve' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Color distribution' })).toBeNull()
    const emptyRow = document.querySelector('.analysis-row')
    expect(emptyRow).not.toBeNull()
    expect(emptyRow!.children).toHaveLength(0)
    // NOT A WHITESPACE TEXT NODE EITHER: `:empty` matches only an element with no child nodes at
    // ALL, text included, so a child rendering `' '` rather than `null` would silently re-open
    // the gap while `children` still read 0. This is the assertion that would notice.
    expect(emptyRow!.childNodes).toHaveLength(0)
  })

  it('puts the deck on the glass as card faces (c4-4, AC 16, FR-19)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // The other half of the displacement: the slot is FILLED, not merely emptied. Two cards in
    // the fixture, so two tiles — each a real button, each pointing at our own origin.
    //
    // SCOPED, NOT BUMPED (c4-7, Q9). This read `screen.getAllByRole('listitem')` — queried over
    // the WHOLE DOCUMENT — until c4-7 put a second `ul`/`li` structure on the same screen, at
    // which point it counted four. Bumping `2` to `2 + rowCount` would have kept the number green
    // while PRESERVING the coupling that made it red: the next story to add a list (c4-10's
    // format check) would hit the identical failure, and the number would say nothing about which
    // list grew. Scoping to the grid's own `<ul>` is the repair, and it makes the assertion mean
    // what its comment always claimed — two TILES.
    //
    // The grid's `<ul>` is reached by class rather than by role+name because its `Panel` is
    // deliberately UNTITLED (c4-4, Q6): an unnamed `<section>` has no role at all, which is
    // correct behaviour and leaves no accessible handle to scope by.
    const grid = document.querySelector('.card-grid')
    expect(grid, 'the card grid is not on the glass at all').not.toBeNull()
    const tiles = within(grid as HTMLElement).getAllByRole('listitem')
    expect(tiles).toHaveLength(2)

    // …and the deck list is the OTHER list, counted separately and by its own name, so the two
    // can never again be conflated by a document-wide query. Two cards in the fixture means two
    // rows, wherever their type groups put them.
    const deckList = screen.getByRole('region', { name: 'Deck list' })
    expect(within(deckList).getAllByRole('listitem')).toHaveLength(2)

    // THE THIRD LIST, COUNTED IN ITS OWN SCOPE (c4-10, AC 5, Q9). The comment above predicted
    // this story by name — *"the next story to add a list (c4-10's format check) would hit the
    // identical failure"* — and the scoping c4-7 added is what makes that prediction land as a
    // new assertion instead of as a broken one. Six checks, always: the backend emits one row per
    // check in `CHECK_ORDER` whether or not anything is wrong, so this number is six on every
    // deck in the corpus and does not vary with the fixture above it.
    const formatCheck = screen.getByRole('region', { name: 'Format check' })
    expect(within(formatCheck).getAllByRole('listitem')).toHaveLength(6)
    // AND THE DOCUMENT-WIDE TOTAL, WHICH IS **FOUR** LISTS AND NOT THREE (c4-10, AC 5).
    // Worth writing down because the story's own context predicted three and the fourth is easy
    // to miss: `ColourDistribution`'s LEGEND is a `<ul>` too (c4-9 shipped it as one deliberately
    // — *"five entries in a mono-to-five-colour range is a list"*), and this fixture's single
    // green pip gives it exactly one entry. So the honest sum is 2 tiles + 2 deck rows + 1 legend
    // entry + 6 checks. Asserting the total beside the scoped counts is what makes the scoping
    // exhaustive rather than merely separate — if a fifth list appears, this is the number that
    // says so, and the scoped counts above say which one grew.
    const legend = document.querySelector('.colour-legend')
    expect(legend).not.toBeNull()
    expect(within(legend as HTMLElement).getAllByRole('listitem')).toHaveLength(1)
    expect(screen.getAllByRole('listitem')).toHaveLength(2 + 2 + 1 + 6)

    // BOTH OF THESE WERE DOCUMENT-WIDE TOO, and both are scoped for the same reason (c4-7, Q9).
    // A tile and a row now name the same card and show the same count, on purpose — they are two
    // views of one deck — so an unscoped `getByRole`/`getByText` throws on multiple matches
    // rather than failing an assertion, which is a worse failure because it says nothing about
    // which view is wrong. Asserting BOTH sides is what makes the duplication deliberate: the
    // grid's tile and the list's row each carry the name and the quantity.
    expect(
      within(grid as HTMLElement).getByRole('button', { name: /Llanowar Elves/ }),
    ).toBeVisible()
    expect(within(grid as HTMLElement).getByText('×10')).toBeVisible()
    expect(within(deckList).getByRole('button', { name: /Llanowar Elves/ })).toBeVisible()
    expect(within(deckList).getByText('×10')).toBeVisible()

    // AND STILL NO REQUEST FOR AN IMAGE, from this app. The pictures arrive through
    // `<img src>` and the browser's own HTTP cache, which is why `posture.test.ts`'s one-door
    // list needed no edit in the first story that puts remote images on the screen. The count
    // comes first (review 2026-08-04): a loop over an empty NodeList passes vacuously, so a
    // regression that dropped the `<img>` entirely would have satisfied the origin rule by
    // removing its subject.
    //
    // ONE MORE THAN THE TILES SINCE c4-5, and the extra one is named rather than absorbed into a
    // `>=`: the detail panel draws the inspection target's face at `size=large`. Spelling the
    // arithmetic keeps this a count rather than a floor — a second stray `<img>` would still
    // fail here, which a loosened comparison would have waved through.
    //
    // c4-7 ADDS NOTHING TO THIS SUM, and that is the assertion rather than an omission: the deck
    // list is TEXT-FIRST (AC 15, UX-DR19), which is exactly why a card with no image data or an
    // unrecognised id renders identically to any other row there. `tiles` is now grid-scoped, so
    // this arithmetic still reads "one per tile, plus the detail panel" and did not need
    // loosening — the correct repair for a document-wide count was to scope the count, not to
    // weaken the comparison.
    const images = [...document.querySelectorAll('img')]
    expect(images).toHaveLength(tiles.length + 1)
    // `<img>` ELEMENTS, not `role="img"` — `ManaCost` legitimately renders its pip run as a
    // labelled `role="img"` span, and counting roles here would assert the opposite of the truth.
    // What the deck list must not do is fetch a picture.
    expect(deckList.querySelectorAll('img')).toHaveLength(0)
    for (const img of images) {
      expect(img.getAttribute('src')).toMatch(/^\/api\/card-image\//)
    }
    // …and exactly one of them is the DETAIL render, at the size only that panel asks for.
    expect(images.filter((img) => img.getAttribute('src')?.includes('size=large'))).toHaveLength(1)
  })

  it('seeds the card cache free, and hydrates each DISTINCT card exactly once (AC 17, c4-6 AC 23)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    const fetchMock = answering(decks())

    render(<App />)
    await settle()

    // THIS ASSERTION HAS MOVED TWICE, AND BOTH MOVES SHARPENED IT RATHER THAN RELAXING IT.
    //
    // c4-2 wrote `toBe(0)`: seeding is free, so while nothing consumed the hydration tier nothing
    // had to ask. c4-5 gave the route its first caller — the detail panel hydrates its inspection
    // target — and the number became ONE. **c4-6 makes it ONE PER DISTINCT CARD**, and the reason
    // is a fact about the wire rather than a change of appetite: the flip control must render
    // "when its tile renders", and whether a card HAS a back face lives only in the hydrated
    // record. `CardSummary` carries neither `card_faces` nor `image_uris`, so a deck-wide sweep is
    // what makes AC 1 true (that story's Q1 prices the two alternatives it declined).
    //
    // WHAT IS STILL ASSERTED, AND IT IS THE PART THAT MATTERS:
    //
    //   the SUMMARY tier is still FREE for every card in the deck — it arrives inside the one
    //   `GET /api/deck/{id}` c4-2 already makes, 38,182 bytes in hand for the real 99-tile deck;
    //
    //   and the sweep costs exactly ONE request per DISTINCT id — not one per tile, not one per
    //   render, and not one per hover. Two cards in this fixture, two requests. On the largest
    //   real deck that ceiling is 99, measured read-only at c4-6's Task 0, and `hydrateCard`'s
    //   in-flight dedupe plus its terminal-refusal gate are what hold it there.
    //
    // The cold-open target is `Llanowar Elves`: no commander in this fixture, so the grid's
    // visual order starts at the first populated type group, and `Creature` precedes `Land`.
    expect(useCardStore.getState().cards['id-Llanowar Elves']?.status).toBe('hydrated')
    expect(useCardStore.getState().cards['id-Forest']?.status).toBe('hydrated')
    expect(callsTo(fetchMock, '/api/cards/')).toBe(2)
    expect(callsTo(fetchMock, '/api/cards/id-Llanowar%20Elves')).toBe(1)
    // THE ONE THAT WOULD CATCH A DOUBLE SWEEP. The panel hydrates its target and the sweep
    // hydrates the whole deck, so the cold-open card is asked for by BOTH — and it must still cost
    // one request, because `hydrateCard` shares the promise rather than issuing a second read.
    expect(callsTo(fetchMock, '/api/cards/id-Forest')).toBe(1)
    // THE WHOLE-MOUNT TOTAL, ITEMISED SO THE NUMBER STAYS READABLE (c4-10, AC 10): one poll of
    // `/api/decks`, one `/api/active-deck`, one deck detail, TWO card hydrations, one format
    // check, and — new in **c5-6** — one `GET /api/session`. SEVEN, with every member broken out
    // beside it so that a bump here can never be absorbed as "the sweep got bigger".
    //
    // The socket's contribution to a cold open is that ONE mint, and then nothing: the upgrade is
    // not an HTTP request the fixture can see, and a live connection costs no polling at all.
    // That is the whole economic case for the channel, stated as a number rather than as prose.
    expect(formatCheckCalls(fetchMock)).toBe(1)
    expect(callsTo(fetchMock, '/api/session')).toBe(1)
    expect(fetchMock).toHaveBeenCalledTimes(7)
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

    // AC 9a's OTHER HALF (Q14, L8 — added at review 2026-08-05: the branch shipped, the test
    // did not). While a state panel occupies the glass the right column carries NO detail
    // panel: `right` is `undefined` on every non-deck arm, so the state panel is the one
    // subject on screen rather than sharing it with a card whose deck was just refused.
    expect(screen.queryByRole('region', { name: 'Card detail' })).toBeNull()
    // …and NO deck list either (c4-7 AC 2 — added at review 2026-08-06: the same checkbox-
    // without-its-test shape, one story on). Both right-column panels ride the one
    // `kind === 'deck'` gate, and this is the assertion that notices if the list ever gets
    // its own.
    expect(screen.queryByRole('region', { name: 'Deck list' })).toBeNull()
    // …and NO mana curve (c4-8 AC 2). Written WITH the branch rather than after it, which is
    // the shape the last two stories had to be corrected into. The left slot renders a
    // `StatePanel` on every non-deck arm, so the curve — and the analysis row that holds it —
    // are absent behind every one of the six state panels, not merely this one.
    expect(screen.queryByRole('region', { name: 'Mana curve' })).toBeNull()
    // …and NO colour distribution (c4-9 AC 3), for the same reason and on the same gate.
    expect(screen.queryByRole('region', { name: 'Color distribution' })).toBeNull()
    expect(document.querySelector('.analysis-row')).toBeNull()
    // …and NO format check (c4-10 AC 3). The whole right column is `undefined` on a non-deck
    // arm, so all three of its panels ride the one gate — and this is the assertion that would
    // notice if the format check ever got a gate of its own.
    expect(screen.queryByRole('region', { name: 'Format check' })).toBeNull()
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
    // TWO deck-DETAIL reads, and ONE format check (c4-10, AC 10). `callsTo` matches by PREFIX and
    // the format-check route shares the deck prefix, so the two are separated here rather than
    // summed — which is also why the number below is 1 and not 2.
    expect(deckDetailCalls(fetchMock)).toBe(2)
    // THE ASYMMETRY IS THE POINT, AND IT IS c4-10's whole staleness argument in one number: the
    // recovery edge re-boots and writes a NEW `DeckDetail` object for the SAME deck, so an effect
    // keyed on that object would fire twice and pay a second `get_deck_with_cards`. Keyed on the
    // deck ID string it fires once. This assertion is what makes that structural rather than
    // careful, and it is c4-2's request count EXTENDED — still a number, still red on a repeat.
    expect(formatCheckCalls(fetchMock)).toBe(1)
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
        // ⚠️ THE SECOND PREFIX-ROUTING FIXTURE, AND IT NEEDS THE SAME BRANCH FIRST (c4-10).
        // `/api/deck/{id}/format-check` starts with `/api/deck/`, so without this line the
        // format-check request is answered by `deckRead()` — which here REJECTS, making the
        // panel silently absent for a reason this test is not about. Fixing `answering()` and
        // not this one is the half-repair the story's Dev Notes warn about by name.
        if (path.endsWith('/format-check')) return Promise.resolve(formatCheckReport())
        if (path.startsWith('/api/deck/')) return deckRead()
        // c5-6's fourth route, in the SECOND prefix-routing fixture too. The comment above warns
        // that fixing `answering()` and not this one is a half-repair; the session route is the
        // fourth chance to make exactly that mistake.
        if (path === '/api/session') return Promise.resolve(sessionTicket())
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
    // Counted apart from this story onwards (c4-10): a poll transition re-renders the whole tree,
    // and the format check must no more re-fire on a render than the boot does. One each.
    expect(deckDetailCalls(fetchMock)).toBe(1)
    expect(formatCheckCalls(fetchMock)).toBe(1)
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
describe('the skip link is present exactly when there is something to skip (c4-11, AC 4)', () => {
  const SKIP = 'Skip past the deck grid'

  it('is on the glass, and FIRST, for a loaded deck with cards', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    const link = screen.getByRole('button', { name: SKIP })
    expect(link).toBeInTheDocument()
    // FIRST in the document, which is first in the Tab order because nothing carries a tabindex.
    expect(document.querySelector('.app-shell')?.firstElementChild).toBe(link)
    // …and there is genuinely a grid behind it, so the presence is not vacuous.
    expect(document.querySelector('.card-tile')).not.toBeNull()
  })

  // WITHDRAWN BEHIND EVERY STATE PANEL — PARAMETRIZED OVER EVERY ARM, NOT A REPRESENTATIVE ONE
  // (AC 4). UX-DR31 withdraws the link when "a state panel occupies the left column", and
  // `surfaceOf` returns `{ kind: 'panel' }` for all six `StateKey`s. A test that checked one arm
  // would pass through a condition written `panel !== 'no-active-deck'`, which is exactly the
  // shape a later edit reaches for. Four arms arrive from the wire; the two client-only states
  // (`disconnected`, `database-updating-stalled`) are unreachable from a wire response by
  // construction — c5-6 and c3-9 own their triggers — so those two are driven through
  // `useSystemStore.setState` directly, exactly as their real triggers will write them. All six,
  // per the AC's letter (code review 2026-08-07: the first written form drove four and declared
  // the other two structurally covered).
  //
  // ⚠️ **c5-6 SPLITS THAT PAIR, AND THE SPLIT IS THE POINT (AC 21).** `disconnected` now HAS a
  // real trigger — the backoff's two exhaustion gates — so driving it through `setState` here
  // would be asserting against a mechanism that no longer needs simulating. It moves to its own
  // test below, driven end to end. `database-updating-stalled` stays store-driven: its trigger
  // is c3-9's 60-second clock inside the poller and reaching it from here would mean sixty
  // seconds of poll fixture to prove a skip-link rule.
  const WIRE_DRIVEN_ARMS: readonly [string, string, number][] = [
    ['database-not-initialized', 'database_not_initialized', 503],
    ['database-updating', 'database_unavailable', 503],
    ['internal-error', 'internal_error', 500],
    ['no-active-deck', 'deck_not_found', 404],
  ]

  for (const [panel, reason, status] of WIRE_DRIVEN_ARMS) {
    it(`is withdrawn behind the ${panel} panel`, async () => {
      answering(refusal(reason, status), decks('Boros Aggro'))

      render(<App />)
      await settle()

      // The state panel really is on the glass — without this the absence below would be an
      // assertion about a page that failed to render anything at all.
      expect(document.querySelector('.state-panel')).not.toBeNull()
      expect(document.querySelector('.card-tile')).toBeNull()

      expect(screen.queryByRole('button', { name: SKIP })).toBeNull()
      // …and nothing rendered a placeholder in its slot either: the shell's first child is the
      // header, so there is no story key sitting where the link would have been.
      expect(document.querySelector('.app-shell')?.firstElementChild?.tagName).toBe('HEADER')
    })
  }

  it('is withdrawn behind the disconnected panel — driven by the REAL backoff (c5-6, AC 21)', async () => {
    // The conversion AC 21 asks for. Nothing here writes a store: the backend simply never
    // answers the mint, the loop fails on its own schedule, and sixty seconds later the two gates
    // agree. What is being asserted is unchanged — the link is withdrawn behind a state panel —
    // but it is now asserted about the panel the shipped mechanism produces.
    // Driven from a LOADED deck rather than from no-deck, which the four wire arms above cannot
    // do: `surfaceOf` ranks a loaded deck above every system panel, so this is simultaneously the
    // skip-link withdrawal AND Q3's fourth arm — the one state that displaces a deck.
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    expect(screen.getByRole('button', { name: SKIP })).toBeInTheDocument()

    // The backend goes away — every route, not just the socket, which is what a restart is.
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )
    await drop()
    await advance(DISCONNECTED_AFTER_MS)

    expect(screen.getByRole('region', { name: 'Lost the companion backend.' })).toBeVisible()
    expect(screen.queryByRole('button', { name: SKIP })).toBeNull()
    expect(document.querySelector('.app-shell')?.firstElementChild?.tagName).toBe('HEADER')
  })

  const STORE_DRIVEN_ARMS = ['database-updating-stalled'] as const

  for (const panel of STORE_DRIVEN_ARMS) {
    it(`is withdrawn behind the ${panel} panel (store-driven — its wire trigger is not this story's)`, async () => {
      // No deck on the glass, which is the state these panels can actually occupy: `surfaceOf`
      // gives a LOADED deck priority over the system panel (deck.ts:426 — the deck-wins posture),
      // so the left column shows these arms only from the no-deck state. Driven through
      // `useSystemStore.setState` exactly as their real triggers (poller unreachable / stalled
      // clock) will write them.
      booting(activeDeck(null))
      answering(decks())

      render(<App />)
      await settle()

      act(() => {
        useSystemStore.setState({ panel, decks: [] })
      })

      expect(document.querySelector('.state-panel')).not.toBeNull()
      expect(document.querySelector('.card-tile')).toBeNull()
      expect(screen.queryByRole('button', { name: SKIP })).toBeNull()
      expect(document.querySelector('.app-shell')?.firstElementChild?.tagName).toBe('HEADER')
    })
  }

  it('is withdrawn on an EMPTY deck — the case UX-DR31 does not cover (Q3, c4-12)', async () => {
    // The gap Q3 exists to close. An empty deck renders NO state panel, so UX-DR31's withdrawal
    // trigger is absent — and its grid is not populated, so the presence trigger is absent too.
    // It falls between both branches of the written rule.
    //
    // The reason is that an empty deck has NOTHING TO SKIP — zero tiles and zero deck rows sit
    // between the link and the right column, so the link would save zero Tab stops. (The first
    // written form of this comment claimed the link's target would not exist; that was FALSE —
    // `CardDetail` renders its frame and `<h2>` unconditionally, and UX-DR20's "first card" fills
    // the panel's content, not its heading. Corrected at code review 2026-08-07.)
    // `distinct_cards: 0` spelled with the other two zeroes — the builder's default of 2 beside
    // `cards: []` is a wire body no backend produces (code review 2026-08-07; the empty-deck
    // describe's own `emptyDeck()` helper records why all three counts are 0 together).
    booting(
      activeDeck(ATRAXA_DECK_ID),
      deckDetail({ cards: [], mainboard_count: 0, distinct_cards: 0 }),
    )
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // A DECK is on the glass — not a state panel. This is what makes the case distinct from the
    // four above, and a fixture that quietly produced a panel would make this test a duplicate.
    expect(document.querySelector('.state-panel')).toBeNull()
    expect(screen.getByRole('heading', { level: 1 }).textContent).not.toBe(
      'Artificial Planeswalker',
    )
    expect(document.querySelector('.card-tile')).toBeNull()

    expect(screen.queryByRole('button', { name: SKIP })).toBeNull()
  })

  it('is PRESENT on a sideboard-only deck — rows are a corridor even when tiles are not', async () => {
    // The state Q3's two documented cases both miss, found at code review 2026-08-07: the grid
    // spreads commander + mainboard (`CardGrid.tsx:76`) but c4-7's deck list ALSO renders a
    // focusable row per sideboard card — so a sideboard-only deck has zero tiles and a real
    // corridor of rows. Ruled: the link's condition is "any focusable deck row exists", not "any
    // tile exists".
    booting(
      activeDeck(ATRAXA_DECK_ID),
      deckDetail({
        cards: [{ ...deckCard('Pithing Needle', 'Artifact'), sideboard: true }],
        mainboard_count: 0,
        sideboard_count: 1,
      }),
    )
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // No tiles — and the link is on the glass anyway, because the rows are.
    expect(document.querySelector('.card-tile')).toBeNull()
    expect(document.querySelector('.deck-row')).not.toBeNull()
    expect(screen.getByRole('button', { name: SKIP })).toBeInTheDocument()
  })

  it('moves focus into the right column when activated, end to end (AC 5)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    const link = screen.getByRole('button', { name: SKIP })
    const detail = screen.getByRole('region', { name: 'Card detail' })

    act(() => {
      link.focus()
      link.click()
    })

    // THE REAL PANEL'S REAL HEADING — not the stand-in `SkipLink.test.tsx` uses. This is the
    // assertion that proves the id on `CardDetail`'s frame and the lookup in `SkipLink` actually
    // meet, which neither file can show on its own.
    const heading = screen.getByRole('heading', { name: 'Card detail' })
    expect(document.activeElement).toBe(heading)
    expect(detail.contains(document.activeElement)).toBe(true)

    // AND IT SKIPPED THE GRID: the focused heading comes AFTER every tile in document order.
    const lastTile = [...document.querySelectorAll('.card-tile')].at(-1)!
    expect(
      lastTile.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })
})

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

  it('is still the LAST pair of Tab stops, with the skip link first (c4-11, AC 11)', async () => {
    // THE CORRIDOR, END TO END, over a real rendered deck (AC 11). Asserted as DOCUMENT ORDER —
    // never as a `tabindex` value and never through `userEvent.tab()` (Q11: jsdom implements no
    // sequential focus navigation, so that call would walk user-event's own heuristic list rather
    // than this app's DOM). `CardTile.test.tsx:595-605` set this precedent.
    booting(
      activeDeck(ATRAXA_DECK_ID),
      deckDetail({
        cards: [
          deckCard('Llanowar Elves', 'Creature — Elf Druid', 1, '{G}', 1),
          deckCard('Forest', 'Basic Land — Forest', 24),
        ],
      }),
    )
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // The focusable set, derived from the DOM rather than listed — the same posture the app-wide
    // guards take. `[tabindex]` is in the selector so the oracle scroller is included; a positive
    // `tabindex` anywhere would also show up here and break the order below, which is the point.
    const focusables = [...document.querySelectorAll<HTMLElement>('a[href], button, [tabindex]')]
    const at = (el: Element | null) => focusables.indexOf(el as HTMLElement)

    // NON-VACUITY (AC 32): this deck really does render a grid, a detail panel and a footer, so
    // the ordering assertions below have something to order. A fixture that rendered none of them
    // would pass every `toBeLessThan` by comparing -1 with -1.
    expect(focusables.length).toBeGreaterThan(4)

    const skip = screen.getByRole('button', { name: 'Skip past the deck grid' })
    const firstTile = document.querySelector('.card-tile')
    const firstRow = document.querySelector('.deck-row')
    const oracle = document.querySelector('.card-detail-oracle')
    const footerLinks = within(screen.getByRole('contentinfo')).getAllByRole('link')

    expect(firstTile).not.toBeNull()
    expect(firstRow).not.toBeNull()
    expect(footerLinks).toHaveLength(2)

    // THE SKIP LINK IS FIRST — before the header, and therefore before every tile.
    expect(at(skip)).toBe(0)
    expect(at(skip)).toBeLessThan(at(firstTile))

    // THE GRID PRECEDES THE RIGHT COLUMN, which is the whole reason the skip link exists.
    expect(at(firstTile)).toBeLessThan(at(firstRow))

    // THE DETAIL PANEL'S OWN STOPS COME BEFORE THE FIRST DECK ROW (Q2's enumeration correction —
    // UX-DR40 omitted them entirely). The oracle scroller is c4-11's new stop; it lives in the
    // detail panel, which stacks ABOVE the deck list.
    expect(oracle).not.toBeNull()
    expect(at(oracle)).toBeLessThan(at(firstRow))

    // AND THE FOOTER LINKS ARE LAST — the two stops the story's user statement is about, and the
    // ones still 101 stops away on the largest real deck even after using the link.
    expect(at(footerLinks[0])).toBe(focusables.length - 2)
    expect(at(footerLinks[1])).toBe(focusables.length - 1)
    expect(at(firstRow)).toBeLessThan(at(footerLinks[0]))
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

/**
 * The corridor numbers of §A, pinned in the SUITE rather than only in the story file (c4-11,
 * AC 31) — over the two shapes the AC names: the 99-tile / 6-flip-control `Atraxa Counter
 * Cabinet v2` and the 1-card `Iron Man, Modern Marvel — reminder`.
 *
 * The identity being pinned is §A's own arithmetic: corridor = tiles + flip controls + the
 * oracle scroller + deck rows, with the skip link before it and the two footer links after it.
 * Atraxa v2 (VERIFIED REAL against the live DB at code review 2026-08-07: 99 rows — 1 commander
 * + 98 mainboard, NO sideboard — quantity 100, exactly 6 flippable Pathways) gives
 * 99 + 6 + 1 + 99 = **205**, of which the link removes the first 105 (tiles + flips) and leaves
 * 100. The 92 filler mainboard names are DECLARED SYNTHETIC IN PLACE: only the COUNT is the
 * fixture's claim, and the count is the real deck's.
 */
describe('the corridor numbers of §A are pinned in the suite (c4-11, AC 31, AC 11)', () => {
  const atraxaShape = () => [
    {
      ...deckCard(
        'Atraxa, Praetors’ Voice',
        'Legendary Creature — Phyrexian Angel',
        1,
        '{G}{W}{U}{B}',
        4,
      ),
      commander: true,
    },
    ...PATHWAY_NAMES.map((name) => deckCard(name, 'Land')),
    ...Array.from({ length: 92 }, (_, i) =>
      deckCard(`Synthetic Filler ${i + 1}`, 'Creature — Test', 1),
    ),
  ]

  const focusablesNow = () => [
    ...document.querySelectorAll<HTMLElement>('a[href], button, [tabindex]'),
  ]

  it('pins 206 = 99 tiles + 6 flips + 1 oracle + 99 rows + 1 pill on Atraxa, and the flip adjacency', async () => {
    booting(
      activeDeck(ATRAXA_DECK_ID),
      deckDetail({ cards: atraxaShape(), mainboard_count: 100, distinct_cards: 99 }),
    )
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    // The hydration sweep is what grows the six flip controls; give its ~99 staggered requests
    // time to land before counting anything.
    await advance(10_000)

    const focusables = focusablesNow()
    const at = (el: Element | null) => focusables.indexOf(el as HTMLElement)

    // The shape really rendered: NON-VACUITY for every count below.
    expect(document.querySelectorAll('.card-tile')).toHaveLength(99)
    expect(document.querySelectorAll('.card-tile-frame .flip-control')).toHaveLength(6)
    expect(document.querySelectorAll('.deck-row')).toHaveLength(99)

    const skip = screen.getByRole('button', { name: 'Skip past the deck grid' })
    const oracle = document.querySelector('.card-detail-oracle')
    const footerLinks = within(screen.getByRole('contentinfo')).getAllByRole('link')
    expect(oracle).not.toBeNull()
    expect(footerLinks).toHaveLength(2)

    // THE PIN: §A's arithmetic, produced by the DOM rather than recomputed from the artefact.
    //
    // ⚠️ EVERY NUMBER BELOW GAINED EXACTLY ONE AT c5-7, AND THAT IS THE PILL. It is the last Tab
    // stop before the footer links (UX-DR40, and `AppShell.tsx` renders it between `</main>` and
    // `<footer>`), so it lands INSIDE the skip→footer corridor and OUTSIDE the skip→oracle prefix
    // — which is why the middle assertion is the one that did not move. The pin was recomputed
    // rather than relaxed: a `toBeGreaterThan` here would have accepted a pill mounted anywhere.
    //
    // 1 skip + 99 tiles + 6 flips + 1 oracle + 99 rows + 1 pill + 2 footer links = 209 focusables…
    expect(focusables).toHaveLength(209)
    // Selected by CLASS, not by accessible name: this suite drives no socket, so the pill sits at
    // the cold-open `'reconnecting'` status throughout and its words are not the live ones. Its
    // POSITION is what this test is about, and the position is the same in every state.
    const pill = document.querySelector('.connection-pill')
    expect(pill).not.toBeNull()
    expect(at(pill)).toBe(focusables.length - 3)
    // …the corridor from the header to the first footer link is 206 stops (205 + the pill)…
    expect(at(footerLinks[0]) - at(skip) - 1).toBe(206)
    // …the link removes the first 105 of them (every tile and every flip control), UNCHANGED
    // because the pill sits on the far side of the deck rows…
    expect(at(oracle) - at(skip) - 1).toBe(105)
    // …and the footer is STILL 101 stops away after using it — the story's own headline, at this
    // deck's scale, one worse than c4-11 measured it. The largest real deck (which carries a
    // sideboard) is a longer corridor again; these are this SHAPE's numbers, not that deck's.
    expect(at(footerLinks[0]) - at(oracle)).toBe(101)

    // THE FLIP ADJACENCY (AC 11): every flip control's immediately-preceding Tab stop is its OWN
    // tile — the sibling inside the same `.card-tile-frame` — never a trailing group.
    const flips = focusables.filter((el) => el.classList.contains('flip-control'))
    expect(flips).toHaveLength(6)
    for (const flip of flips) {
      const ownTile = flip.closest('.card-tile-frame')?.querySelector('.card-tile')
      expect(focusables[at(flip) - 1]).toBe(ownTile)
    }
  })

  it('pins the intra-panel order — unpin, then flip, then oracle — while a flippable card is pinned (AC 11)', async () => {
    booting(
      activeDeck(ATRAXA_DECK_ID),
      deckDetail({ cards: atraxaShape(), mainboard_count: 100, distinct_cards: 99 }),
    )
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    await advance(10_000)

    // Pin a Pathway: its tile's click is the pin gesture (c4-5), and a FLIPPABLE pin is what
    // makes all three panel stops exist at once — the published UX-DR40 enumeration's intra-panel
    // clause, which no other test renders.
    const pathwayFrame = [...document.querySelectorAll('.card-tile-frame')].find((frame) =>
      frame.querySelector('.flip-control'),
    )!
    act(() => {
      pathwayFrame.querySelector<HTMLElement>('.card-tile')!.click()
    })

    const detail = screen.getByRole('region', { name: 'Card detail' })
    const inPanel = focusablesNow().filter((el) => detail.contains(el))
    // Exactly three stops, in exactly the published order — asserted as the full class sequence
    // so a reorder OR an addition reddens this rather than sliding by a `toBeLessThan`.
    expect(inPanel.map((el) => el.className.split(' ')[0])).toEqual([
      'card-detail-unpin',
      'flip-control',
      'card-detail-oracle',
    ])
  })

  it('pins 4 = 1 tile + 1 oracle + 1 row + 1 pill on the 1-card deck (Iron Man, Modern Marvel)', async () => {
    // The other end of the corridor's range, and the deck the AC names (VERIFIED REAL: one card,
    // `Iron Man, Modern Marvel`). The link still renders — presence is "at least one card", and
    // this is exactly one.
    booting(
      activeDeck(ATRAXA_DECK_ID),
      deckDetail({
        cards: [deckCard('Iron Man, Modern Marvel', 'Legendary Creature — Human Hero', 1)],
        mainboard_count: 1,
        distinct_cards: 1,
      }),
    )
    answering(decks('Iron Man, Modern Marvel — reminder'))

    render(<App />)
    await settle()

    const focusables = focusablesNow()
    const at = (el: Element | null) => focusables.indexOf(el as HTMLElement)
    const skip = screen.getByRole('button', { name: 'Skip past the deck grid' })
    const oracle = document.querySelector('.card-detail-oracle')
    const footerLinks = within(screen.getByRole('contentinfo')).getAllByRole('link')

    // 1 skip + 1 tile + 1 oracle + 1 row + 1 pill + 2 footer links = 7 focusables; corridor of 4.
    // The pill is the +1 at BOTH ends of the epic's range, which is the honest cost of a stop that
    // is always present: it is proportionally largest exactly where the corridor is shortest.
    expect(focusables).toHaveLength(7)
    expect(at(footerLinks[0]) - at(skip) - 1).toBe(4)
    expect(at(oracle) - at(skip) - 1).toBe(1)
    expect(at(footerLinks[0]) - at(oracle)).toBe(3)
  })
})

describe('the jsdom phantom-banner count (c4-11, AC 25)', () => {
  it('holds at SIX banners in jsdom on a loaded deck — asserted, not assumed', async () => {
    // aria-query maps `<header>` to `banner` UNCONDITIONALLY, so every titled Panel's `<header>`
    // reads as a banner here while a real browser scopes `banner` to the `<body>`-level header
    // alone — the eye-check read Chrome's OWN AX tree and measured EXACTLY ONE. Six = the shell's
    // real `<header>` + five titled panels (mana curve, colour distribution, format check, card
    // detail, deck list). This assertion is the number's home in the SUITE: when a later story
    // adds a titled panel, this moves by one ON PURPOSE, and the jsdom-vs-Chrome split stays
    // written where the count is enforced rather than only in the story file.
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    expect(screen.getAllByRole('banner')).toHaveLength(6)
  })
})

describe('the empty deck (story c4-12, AC 1, AC 3-5, AC 7-10, AC 14)', () => {
  /**
   * ⚠️ **THIS FIXTURE IS SYNTHETIC, AND IT HAS TO BE** (AC 31, c4-10 AC 26, c4-11 AC 31).
   *
   * Measured read-only against the shipped database on 2026-08-07: **0 of 42 decks** have zero
   * `deck_cards` rows, and the smallest real deck is a ONE-card one (`Iron Man, Modern Marvel —
   * reminder`). There is no verified-real row to reach for, so this is declared synthetic rather
   * than dressed up — the third option does not exist.
   *
   * It is nonetheless a **reachable** state, and reachable two ways: `DeckRepository.create_deck`
   * inserts a deck and writes no card at all (the MCP wrapper's own first line says *"empty
   * `cards`"*), and `remove_card_from_deck` issues one `DELETE`, never counts what remains and
   * never touches `decks`. So this is a synthetic fixture for the NORMAL state at creation, not
   * an invented one — and the backend answers it with a plain **200** carrying `cards: []` (an
   * empty ARRAY, never absent and never `null`), which is what `deckDetail` models below.
   */
  const emptyDeck = () =>
    booting(
      activeDeck(ATRAXA_DECK_ID),
      deckDetail({ cards: [], mainboard_count: 0, distinct_cards: 0 }),
    )

  it('shows the line INSTEAD OF the list, inside the untitled panel (AC 1, AC 3)', async () => {
    emptyDeck()
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // A DECK IS ON THE GLASS, NOT A PANEL. Without this the assertions below would be satisfied
    // by an app that rendered a state panel — the one shape EXPERIENCE.md forbids here by name.
    expect(document.querySelector('.state-panel')).toBeNull()
    expect(document.querySelector('.card-grid-empty')).not.toBeNull()

    // The sentence, from the shipped constant rather than a retyped literal.
    expect(screen.getByText(EMPTY_DECK_LINE)).toBeVisible()

    // REPLACED, not emptied (AC 3). An empty `<ul>` left beside the line announces "list, 0
    // items" before the sentence explaining why — so the grid's list must be GONE, not childless.
    // The deck list panel renders `<ul>`s of its own, which is why this is scoped to the grid's
    // class rather than counting lists document-wide.
    expect(document.querySelector('.card-grid')).toBeNull()
    expect(document.querySelectorAll('.card-tile')).toHaveLength(0)
  })

  it('renders the header exactly as a full deck does, including a 0 maindeck badge (AC 5)', async () => {
    emptyDeck()
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // EXPERIENCE.md: *"Deck name and header render normally."* The zero count is SHOWN rather
    // than hidden — `DeckBadges` pins that behaviour in its own suite, and this is the end-to-end
    // half: a badge that vanished at zero would make an empty deck look like a missing one.
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe(
      'Atraxa Counter Cabinet v2 (owned)',
    )
    // The badge splits its count into its own `<span>` — `{count}` then the bare word — so the
    // assertion is on the BADGE's text rather than on a single text node. Written this way
    // deliberately: `getByText('0 maindeck')` fails against the shipped markup, and "fixing" it by
    // asserting `getByText('0')` alone would pass against a `0` rendered anywhere on the page.
    const maindeck = [...document.querySelectorAll('.badge')].find((node) =>
      node.textContent?.includes('maindeck'),
    )
    // `'0maindeck'` with no space, and that is the SHIPPED markup rather than a defect: JSX drops
    // the newline+indent between `{mainboardCount}`'s span and the bare word, and the visible gap
    // comes from `Badge`'s own layout. Pinned as the real string so a later reader does not
    // "fix" the fixture toward a space the DOM never had.
    expect(maindeck?.textContent).toBe('0maindeck')
    expect(maindeck?.querySelector('.deck-badges-count')?.textContent).toBe('0')
    expect(screen.getByText('brawl')).toBeVisible()
  })

  it('never lets the left slot fall through to the shell placeholder (AC 4)', async () => {
    emptyDeck()
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // THE ASSERTION THIS FILE ALREADY MADE — ON THE WRONG FIXTURE. The existing no-story-key
    // checks run on the TWO-CARD deck, where `left` is obviously filled; the state this story
    // creates is the one where a careless `undefined` would put *"The card-art grid lands here —
    // c4-4 …"* on the glass, and nothing would have caught it. Asserted here, on the empty
    // fixture, which is the whole point of AC 4.
    expect(screen.queryByText(/The card-art grid lands here/)).toBeNull()
    for (const key of ['c4-4', 'c4-5', 'c4-8', 'c4-9', 'c4-10', 'c4-12']) {
      expect(document.body.textContent, `${key} is on the glass`).not.toContain(key)
    }

    // …and the ONE key that IS still on the glass, everywhere, since c2-6: `c6-8`, in the shell's
    // agent-view nav placeholder. c4-11 corrected the record that named `c4-11` here. COUNTED
    // rather than merely present, because "not zero" would survive a second key arriving.
    expect(document.body.textContent?.match(/c6-8/g)).toHaveLength(1)
  })

  it('hides all three analysis panels — and only ONE of them by this story gate (AC 7-9)', async () => {
    emptyDeck()
    const mock = answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    expect(screen.queryByRole('region', { name: 'Mana curve' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Color distribution' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Format check' })).toBeNull()

    // THE ROW ITSELF IS STILL IN THE DOM WITH NO CHILD NODES — the `:empty` condition c4-9
    // shipped for this story by name. That is the proof no card-count gate was added in
    // `App.tsx` for the row: a gate there would have removed the element, not emptied it.
    const row = document.querySelector('.analysis-row')
    expect(row).not.toBeNull()
    expect(row!.childNodes).toHaveLength(0)

    // AND THE REQUEST WAS NEVER MADE (AC 10, Q4) — matching the precedent this file already pins
    // for a state panel. A hidden panel that still fetched would be a wasted round trip on the
    // exact cold-open path NFR-05 measures, for a report of four vacuous greens nobody sees.
    expect(formatCheckCalls(mock)).toBe(0)
    // …while the deck detail WAS read, so the zero above is a suppression rather than an app
    // that never booted.
    expect(deckDetailCalls(mock)).toBe(1)
  })

  it('proves the curve and colour hide on THEIR OWN totals, not on a card count (AC 8)', async () => {
    // THE DISCRIMINATOR, AND WITHOUT IT AC 8 IS UNFALSIFIABLE. On an empty deck "zero cards" and
    // "zero curve total" coincide, so absence there is consistent with EITHER mechanism. A
    // LAND-ONLY deck separates them: it HAS cards (tiles render, the deck list has rows, the skip
    // link is present) and still has nothing for either panel to say, because both exclude lands.
    //
    // So this test asserts the two panels absent WHILE the format check is PRESENT — which is
    // only possible if the curve and the colour bar hide on their own zero totals and the format
    // check is gated on emptiness. A card-count gate in `App.tsx` would have hidden all three
    // here; a self-gate inside the format check would have hidden it too.
    booting(
      activeDeck(ATRAXA_DECK_ID),
      deckDetail({ cards: [deckCard('Forest', 'Basic Land — Forest', 24)] }),
    )
    const mock = answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    expect(document.querySelector('.card-tile')).not.toBeNull()
    expect(screen.queryByRole('region', { name: 'Mana curve' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Color distribution' })).toBeNull()
    // The panel this story gates is on the glass, because the deck is NOT empty.
    expect(screen.getByRole('region', { name: 'Format check' })).toBeVisible()
    expect(formatCheckCalls(mock)).toBe(1)
    // …and no empty-deck line either: a deck of lands is not an empty deck.
    expect(screen.queryByText(EMPTY_DECK_LINE)).toBeNull()
  })

  it('keeps the card detail and deck list panels — the recorded artefact gap (AC 13)', async () => {
    emptyDeck()
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // RULED AND PINNED, NOT SILENT. `EXPERIENCE.md`'s two rows and this story's own ACs each name
    // exactly THREE panels to hide, and neither of these is among them — so they render their
    // frames with no card and no rows. That is status quo by ruling (adding a fourth panel to the
    // hide list would be inventing spec; inventing an empty-state sentence would put unsourced
    // words on the glass), and it CONTRADICTS UX-DR20's "the detail panel is never empty while a
    // deck is loaded", because an empty deck is a loaded deck. The contradiction is recorded in
    // `deferred-work.md` as an artefact defect rather than repaired here, and this assertion is
    // what makes the shipped behaviour a fixed point while that stays open.
    expect(screen.getByRole('region', { name: 'Card detail' })).toBeVisible()
    expect(screen.getByRole('region', { name: 'Deck list' })).toBeVisible()
    expect(document.querySelector('.deck-row')).toBeNull()
  })

  it('adds no live region anywhere, and reads as THREE banners in jsdom (AC 14)', async () => {
    emptyDeck()
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // THREE, not six — and the difference is the reason. aria-query maps `<header>` to `banner`
    // UNCONDITIONALLY, so every titled `Panel`'s header reads as a banner in jsdom while a real
    // browser scopes `banner` to the `<body>`-level header alone (c4-11's eye-check read Chrome's
    // own AX tree and measured exactly ONE). On a loaded deck that gives 6 = the shell's header +
    // five titled panels. Here THREE of those five are hidden — the curve, the colour
    // distribution and the format check — so the count is the shell's header + card detail + deck
    // list. The number moving is the point: it is the same phantom, arithmetically consistent
    // with the three panels this story hides, and the sibling pin at 6 is what it is consistent
    // WITH.
    expect(screen.getAllByRole('banner')).toHaveLength(3)

    // NO SECOND ANNOUNCEMENT MECHANISM FOR *THIS* STORY (decide-once ruling 7). A
    // panel-visibility change that announced itself would be the fourth mechanism in this epic
    // doing the same job. Counted across the whole document, and every survivor is IDENTIFIED —
    // the point of the pin is that a new region has to be declared here, not that the number is 1.
    //
    // ⚠️ THE COUNT MOVED TO TWO AT c5-7, AND THE PIN WAS UPDATED RATHER THAN WEAKENED (AC 11).
    // UX-DR45's inventory authorises exactly three polite regions for this app — the connection
    // pill, the agent-view heading and the pin announcement — so a second one arriving is the
    // inventory being filled, not the rule being broken. The honest form of that is an EXHAUSTIVE
    // list: `>= 1` would have let a genuinely undeclared third region through, which is the whole
    // failure this assertion exists to catch. The agent-view heading is Epic 6's and is absent.
    const live = [...document.querySelectorAll('[aria-live]')]
    expect(live).toHaveLength(2)
    for (const region of live) expect(region.getAttribute('aria-live')).toBe('polite')

    // EACH ONE NAMED. Identified by their own classes, NOT by an ancestor lookup: both
    // announcement elements sit deliberately OUTSIDE the thing they describe — that placement is
    // the whole of the H4/C1 gate fix for the detail panel, and the same reason keeps the pill's
    // region outside the pill's `<button>` — so a `closest()` lookup correctly returns null and
    // would have made this a false failure about a correct app.
    const classes = live.map((region) => region.className)
    expect(classes.some((c) => c.includes('card-detail-announcement'))).toBe(true)
    expect(classes.some((c) => c.includes('connection-pill-announcement'))).toBe(true)

    // BOTH EMPTY AT REST. There is no card to pin on an empty deck, and the connection has not
    // transitioned since mount — the pill's region is silent on the initial render by design
    // (c5-7 Q4), which is what stops every cold open announcing "Reconnecting".
    for (const region of live) expect(region.textContent).toBe('')
  })
})

describe('never blank, defined operationally (story c4-12, AC 23, AC 24)', () => {
  /**
   * **THE DEFINITION, BECAUSE NO ARTEFACT SUPPLIES ONE (Q12).**
   *
   * UX-DR36 asserts *"a blank screen is never shown after first paint"*, `EXPERIENCE.md` asserts
   * it again, and neither says what it means operationally. Two stories would otherwise invent two
   * tests for one unfalsifiable sentence — so it is defined HERE, for this story, in the narrowest
   * form that is still a real claim:
   *
   *   **At no point from first paint onward does the app render a viewport containing none of
   *   {header, left-column content, right-column content, footer}.**
   *
   * Four slots, and the criterion is satisfied if ANY of them carries content — not all four. That
   * matters, because three of the six surfaces this suite drives legitimately have an EMPTY right
   * column: `surfaceOf` returns `{kind:'panel'}` for every refusal, and c4-5's Q14 ruling renders
   * the right column only for `kind === 'deck'`. A definition demanding all four would be red on
   * correct behaviour.
   *
   * ⚠️ **SCOPE, DECLARED (AC 24).** This criterion is a **verbatim duplicate** of a story 7.4
   * acceptance criterion — the epics file writes the same sentence word for word — and c4-12's own
   * wording (*"any point after first paint"*) is BROADER than its epic. The half UX-DR36 is really
   * about is the **refetch teardown**: a surface that empties itself while re-reading. That path
   * does not exist in Epic 4 (there is no `deck_changed` refetch; c7-3 owns it) and is handed back
   * to **c7-4** by name rather than half-tested here.
   *
   * ⚠️ **THE ONE CLASSIFICATION IN TENSION WITH THE SENTENCE**, cited rather than resolved:
   * `states.ts`'s `NO_UI_RESPONSE` names three reasons (`invalid_request`, `forbidden`,
   * `payload_too_large`) that deliberately render NOTHING. They are agent-facing and unreachable
   * from the surfaces this app renders, so they do not blank a viewport today — but a future story
   * that routes one of them to a user surface would satisfy `NO_UI_RESPONSE` and violate UX-DR36
   * at the same time. Recorded, not repaired.
   *
   * ⚠️ **WHAT THIS CANNOT SEE.** jsdom has no layout engine and no paint. "Not blank" here means
   * *the DOM carries text in one of the four slots*, which is strictly weaker than *a human sees
   * something*: a slot filled with `color: transparent`, a zero-height column or an off-screen
   * element would all pass. The visual half is the eye-check's, and it is recorded in the story
   * rather than claimed here.
   */
  const slots = () => ({
    header: document.querySelector('.app-shell-header')?.textContent ?? '',
    left: document.querySelectorAll('.app-shell-column')[0]?.textContent ?? '',
    right: document.querySelectorAll('.app-shell-column')[1]?.textContent ?? '',
    footer: document.querySelector('.app-shell-footer')?.textContent ?? '',
  })

  const notBlank = (where: string) => {
    const filledSlots = Object.entries(slots()).filter(([, text]) => text.trim() !== '')
    expect(filledSlots.length, `${where}: every one of the four slots was empty`).toBeGreaterThan(0)
    return filledSlots.map(([name]) => name)
  }

  it('is a criterion that can FAIL — the non-vacuity anchor for every case below', () => {
    // WITHOUT THIS, `notBlank` IS SATISFIED BY ANY PAGE AT ALL and the six cases below assert
    // nothing — the epic's coverage-that-reads-as-coverage shape, which has landed in the
    // flagship guard of six consecutive stories. Fed a document with no shell in it, the reader
    // must report ZERO filled slots, which is the failing condition it exists to detect.
    document.body.innerHTML = '<div></div>'
    expect(Object.values(slots()).every((text) => text.trim() === '')).toBe(true)
    expect(() => notBlank('an empty document')).toThrow()
  })

  it('holds through the deck boot — before the answer arrives and after', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)

    // FIRST PAINT, BEFORE ANY RESPONSE HAS SETTLED. This is the moment the criterion is really
    // about: the shell renders synchronously with a `booting` state behind it, and the header and
    // footer are what carry it.
    expect(notBlank('first paint, mid-boot')).toEqual(expect.arrayContaining(['header', 'footer']))

    await settle()
    expect(notBlank('deck settled')).toEqual(['header', 'left', 'right', 'footer'])
  })

  it('holds behind every refusal panel, and through recovery back to a deck', async () => {
    // FOUR WIRE REFUSALS. The right column is legitimately EMPTY for all of them (c4-5 Q14), which
    // is why the criterion is "any of the four" rather than "all four" — and asserting the empty
    // one explicitly is what stops that clause reading as a fudge.
    // The third column is whether the POLL can ever announce recovery for this token:
    // `poller.ts`'s `RETRIES_QUIETLY` is deliberately `false` for `internal-error` (deterministic
    // — a quiet retry loop would hammer a bug), and a `deck_not_found` poll answer clamps to the
    // same terminal panel, so for those two the poll stops and NO recovery edge can ever arrive
    // (`deck.ts`: "a blip … after the poll has already stopped has no later edge to heal it").
    // Discovered by measurement at code review 2026-08-07: the first draft of the recovery arm
    // drove all four and iteration three sat on "The companion hit a bug." forever — which is the
    // shipped posture, not a defect.
    for (const [reason, status, recovers] of [
      ['database_not_initialized', 503, true],
      ['database_unavailable', 503, true],
      ['internal_error', 500, false],
      ['deck_not_found', 404, false],
    ] as const) {
      booting(activeDeck(ATRAXA_DECK_ID), refusal(reason, status))
      answering(refusal(reason, status), decks('Boros Aggro'))

      render(<App />)
      await settle()

      // ⚠️ ALL FOUR, AND THE FOURTH IS A MEASUREMENT THAT CORRECTS THIS TEST'S FIRST DRAFT. It
      // asserted `['header', 'left', 'footer']` on the reasoning that `surfaceOf` returns
      // `{kind:'panel'}` for every refusal and c4-5's Q14 ruling renders the right column only for
      // `kind === 'deck'` — true, and yet the slot is NOT empty: `AppShell`'s own `slot()` helper
      // substitutes its placeholder whenever a slot is unfilled, so the right column carries
      // *"Card detail — c4-5 …"* instead of nothing. That is c2-9's honest-displacement posture
      // doing exactly its job, and it is also the reason the C3 retro's F1 story-key count is
      // non-zero at all. Written down here because the first draft's reasoning was sound and its
      // conclusion was wrong, which is precisely what a measured assertion is for.
      expect(notBlank(reason)).toEqual(['header', 'left', 'right', 'footer'])
      expect(document.querySelector('.state-panel')).not.toBeNull()
      expect(slots().right).toContain('c4-5')

      // THE RECOVERY HALF — the title's second clause, and it was MISSING at first review: this
      // loop settled every refusal and never advanced the poll, so "through recovery back to a
      // deck" was a claim the body never exercised (the epic's coverage-that-reads-as-coverage
      // class, seventh consecutive story, this time in a test TITLE — code review 2026-08-07).
      // The backend heals on both routes and the poll's next 2 s tick would carry the queued
      // healthy answer — where the poll is still ticking. For the two tokens that retry, c4-2's
      // recovery edge re-drives the boot and the criterion must hold on the deck surface that
      // RETURNS, from the same mount; for the two terminal tokens the poll has stopped, no edge
      // can arrive, and the criterion must hold on the refusal panel that STAYS — both halves of
      // AC 23's sentence, asserted rather than assumed.
      booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
      await advance(2_000)
      if (recovers) {
        expect(notBlank(`${reason} → recovered`)).toEqual(['header', 'left', 'right', 'footer'])
        expect(document.querySelector('.state-panel')).toBeNull()
        expect(document.querySelector('.card-tile')).not.toBeNull()
      } else {
        expect(notBlank(`${reason} → terminal, still filled`)).toEqual([
          'header',
          'left',
          'right',
          'footer',
        ])
        expect(document.querySelector('.state-panel')).not.toBeNull()
      }

      // The suite's `afterEach(cleanup)` runs once per TEST, not once per loop iteration, and the
      // store reset is in `beforeEach` for the same reason — so a loop that mounts four times has
      // to unmount and reset between them itself, or the second iteration renders two Apps into
      // one document and every `querySelector` reads the first one's DOM.
      cleanup()
      useSystemStore.setState(INITIAL_SYSTEM_STATE)
      resetDeckState()
      resetCardCache()
      resetFormatCheckState()
    }
  })

  it('holds on the EMPTY deck — the state this story creates (AC 23)', async () => {
    // All three counts 0 together — the real wire body, matching the empty-deck describe's own
    // `emptyDeck()` helper rather than leaving the builder's `distinct_cards: 2` beside
    // `cards: []` (code review 2026-08-07).
    booting(
      activeDeck(ATRAXA_DECK_ID),
      deckDetail({ cards: [], mainboard_count: 0, distinct_cards: 0 }),
    )
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // ALL FOUR, and that is the whole argument for the in-grid line over a hidden panel: the deck
    // has nothing in it and the app still fills every slot. The left column carries the sentence
    // (not the shell's placeholder), the right column carries two panels instead of three.
    expect(notBlank('empty deck')).toEqual(['header', 'left', 'right', 'footer'])
    expect(slots().left).toContain(EMPTY_DECK_LINE)
    expect(slots().left).not.toContain('The card-art grid lands here')
  })
})

/**
 * The reconnect loop at the root, and the family of stale-panel defects it closes (story c5-6,
 * AC 5, AC 6, AC 7, AC 9, AC 11–16).
 *
 * ================= WHY THESE ASSERTIONS LIVE HERE AND NOT IN `socket.test.ts` ===========
 *
 * `socket.test.ts` proves the schedule, the ticket discipline and the dispatch — against injected
 * effects, with no store, no render and no React. Every claim in THIS block is about what a human
 * sees on a page they did not touch: a panel that appears, a deck that stays, a screen that comes
 * back. That claim can only be made at the root, from ONE mount, which is the same argument c3-9
 * made for putting FR-22's transition test here rather than on the poller.
 *
 * ================= WHAT THE LEDGER SAID, BEFORE THIS STORY =============================
 *
 * Four entries, all recorded as needing a signal the client did not have (`deferred-work.md`):
 *
 *   | dw:3451 + dw:4930 | first load, backend down: *"No deck on the glass."* forever — its copy **actionable and wrong**, severity raised after it was confirmed live |
 *   | dw:3463           | after one `200` the poll stops; a later database death shows a stale healthy panel until reload |
 *   | dw:3472 + dw:3544 | `database-updating-stalled` is terminal: obey the panel, succeed, and still need a manual refresh |
 *   | dw:3652           | three transient failures make a card id terminal for the tab's life while everything else self-heals |
 *
 * The missing signal was a socket. Each `it` below is one of those rows, driven end to end.
 */
describe('the page reconnects on its own (c5-6)', () => {
  const DISCONNECTED = 'Lost the companion backend.'
  const NO_DECK = 'No deck on the glass.'

  /** A backend that is not there: every route, not just the socket. That is what a restart is. */
  const backendDown = () => {
    const fetchMock = vi.fn(() => Promise.reject(new TypeError('Failed to fetch')))
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock as unknown as ReturnType<typeof answering>
  }

  it('opens exactly ONE socket per tab, built from the page authority (AC 1)', async () => {
    render(<App />)
    await settle()
    await advance(10 * 60_000)

    expect(sockets).toHaveLength(1)
    // No port in the bundle: the socket lands wherever the page came from. `agentSocketUrl`'s own
    // test pins the derivation; this one pins that the APP uses it.
    expect(sockets[0].url).toContain(`//${window.location.host}/ws?ticket=`)
    expect(sockets[0].url).toContain('ticket=ticket-1')
  })

  it('mints a FRESH ticket for every attempt, and never re-presents one (AC 3)', async () => {
    render(<App />)
    await settle()
    await drop()
    await advance(SOCKET_BASE_MS)

    expect(sockets).toHaveLength(2)
    // `state.py:318` pops the ticket on every consume attempt, success or not, so a client that
    // held one would be presenting a credential the backend has already destroyed — and would
    // receive the same indistinguishable `1008` a forged one gets.
    expect(sockets[0].url).not.toBe(sockets[1].url)
    expect(sockets[1].url).toContain('ticket=ticket-2')
  })

  // ==================== dw:3451 + dw:4930 — THE FIRST-LOAD DEFECT ======================
  it('shows the DISCONNECTED panel on a first load with no backend, not "No deck on the glass" (AC 14)', async () => {
    // The ledger's own words for what shipped before this story: the copy is *actionable and
    // wrong* — it tells the reader to ask the agent to set a deck, about a backend that is not
    // running. Confirmed live 2026-08-07 and judged **worse than recorded**.
    backendDown()

    render(<App />)
    await settle()

    // THE DEFECT, ASSERTED. This is what the page said, and for the first sixty seconds it still
    // does — deliberately: a backend that is merely slow to start must not flash a panel.
    expect(screen.getByRole('region', { name: NO_DECK })).toBeVisible()

    await advance(DISCONNECTED_AFTER_MS)

    // …and now the true panel, from the true condition. No token carried it — `disconnected` is
    // in `CLIENT_ONLY_STATES` because there is no response to carry one.
    expect(screen.getByRole('region', { name: DISCONNECTED })).toBeVisible()
    expect(screen.queryByRole('region', { name: NO_DECK })).toBeNull()
  })

  it('KEEPS RETRYING behind the panel, and the panel is not a stop (AC 8)', async () => {
    const fetchMock = backendDown()

    render(<App />)
    await settle()
    await advance(DISCONNECTED_AFTER_MS)
    expect(screen.getByRole('region', { name: DISCONNECTED })).toBeVisible()

    const mints = callsTo(fetchMock, '/api/session')
    await advance(10 * 60_000)

    // Twenty more attempts at the 30 s ceiling. `RETRIES_QUIETLY.disconnected` is `true` and this
    // is what that contract costs — and what makes the recovery below possible without a reload.
    // Counted as MINT REQUESTS rather than as tickets handed out: this backend hands out none.
    expect(callsTo(fetchMock, '/api/session') - mints).toBe(20)
  })

  it('comes back WITHOUT A RELOAD when the backend returns (AC 9, AC 5)', async () => {
    // The family's whole point, and the row every other entry was waiting on.
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    backendDown()

    render(<App />)
    await settle()
    await advance(DISCONNECTED_AFTER_MS)
    expect(screen.getByRole('region', { name: DISCONNECTED })).toBeVisible()

    // The companion comes back. Nothing remounts, nothing reloads, nobody presses anything.
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))
    await advance(30_000)
    await connect()

    expect(screen.queryByRole('region', { name: DISCONNECTED })).toBeNull()
    expect(
      screen.getByRole('heading', { level: 1, name: 'Atraxa Counter Cabinet v2 (owned)' }),
    ).toBeVisible()
  })

  // ==================== UX-DR35 — THE DECK STAYS UP WHILE RECONNECTING =================
  it('leaves a loaded deck on the glass for the whole pre-exhaustion window (AC 7)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    await connect()
    const heading = { level: 1 as const, name: 'Atraxa Counter Cabinet v2 (owned)' }
    expect(screen.getByRole('heading', heading)).toBeVisible()

    backendDown()
    await drop()

    // One second short of the threshold, through five failed attempts: the deck is still there,
    // possibly stale, never torn down to a skeleton. UX-DR35, asserted at the moment it is most
    // tempting to violate.
    await advance(DISCONNECTED_AFTER_MS - 1_000)
    expect(screen.getByRole('heading', heading)).toBeVisible()
    expect(screen.queryByRole('region', { name: DISCONNECTED })).toBeNull()

    // …and only THEN does the panel displace it (Q3's fourth `surfaceOf` arm).
    await advance(1_000)
    expect(screen.getByRole('region', { name: DISCONNECTED })).toBeVisible()
    expect(screen.queryByRole('heading', heading)).toBeNull()
  })

  // ==================== FR-07 — THE ACTIVE DECK DIED WITH THE PROCESS ==================
  it('lands on no-active-deck after a restart, as a state and not as an error (AC 6)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    await connect()
    expect(screen.getByRole('heading', { level: 1, name: /Atraxa/ })).toBeVisible()

    // The companion restarts. `ActiveDeckSlot` lives in the process's memory and dies with it, so
    // the fresh backend answers `{"deck_id": null}` whatever was on the glass before (FR-07).
    await drop()
    booting(activeDeck(null))
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))
    await advance(SOCKET_BASE_MS)
    await connect()

    expect(screen.getByRole('region', { name: NO_DECK })).toBeVisible()
    // NOT an error, and not the deck that no longer exists. `deck.ts:339` short-circuits a null
    // id with no second request, so this costs one route, not a refusal round trip.
    expect(screen.queryByRole('region', { name: 'The companion hit a bug.' })).toBeNull()
    expect(screen.queryByRole('heading', { level: 1, name: /Atraxa/ })).toBeNull()
  })

  // ==================== dw:3756 — A FRAME ARRIVES AND SOMETHING LISTENS ================
  it('switches decks on active_deck_changed — the event that had no listener (AC 11)', async () => {
    booting(activeDeck(null))
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    await connect()
    expect(screen.getByRole('region', { name: NO_DECK })).toBeVisible()

    // The agent sets a deck. Before this story the frame reached the browser and nothing read it.
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    await push('active_deck_changed', { deck_id: ATRAXA_DECK_ID })

    expect(
      screen.getByRole('heading', { level: 1, name: 'Atraxa Counter Cabinet v2 (owned)' }),
    ).toBeVisible()
    // The PAYLOAD is never read — the boot asks `GET /api/active-deck` first, so it fetches
    // whichever deck is active NOW rather than the one the frame named. That is what makes
    // `contracts.py`'s "never refetch the deck you are leaving" structural here.
  })

  it('costs one idempotent refetch per duplicate active_deck_changed (AC 12)', async () => {
    // The backend fires on EVERY `PUT`, including a redundant re-set of the deck that is already
    // active (`ws.py:409-444`). Three frames, three refetches, one screen — not a crash, not a
    // loop, not a growing queue.
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    const fetchMock = answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    await connect()
    const before = callsTo(fetchMock, '/api/active-deck')

    await push('active_deck_changed', { deck_id: ATRAXA_DECK_ID })
    await push('active_deck_changed', { deck_id: ATRAXA_DECK_ID })
    await push('active_deck_changed', { deck_id: ATRAXA_DECK_ID })

    expect(callsTo(fetchMock, '/api/active-deck') - before).toBe(3)
    expect(
      screen.getByRole('heading', { level: 1, name: 'Atraxa Counter Cabinet v2 (owned)' }),
    ).toBeVisible()
    expect(sockets).toHaveLength(1)
  })

  it('refetches on deck_changed, and ignores the three Epic-9 view kinds (AC 11)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    const fetchMock = answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    await connect()
    const before = callsTo(fetchMock, '/api/active-deck')

    // `suggestions` LEFT this list at c6-6, which gave it a view to open — see this file's own
    // c6-6 describe for what it does now. **Epic 9** builds the three that remain (P1), and
    // until it does they are received, dropped, and not a fault.
    for (const kind of ['swaps', 'tier_list', 'groups']) await push(kind)
    expect(callsTo(fetchMock, '/api/active-deck') - before).toBe(0)
    expect(sockets[0].closed).toBe(0)
    // Nor do they open anything: a dropped kind that reached the view arm would put a dialog on
    // the glass with a suggestions view's chrome and a tier list's payload.
    expect(screen.queryByRole('dialog')).toBeNull()

    await push('deck_changed', { deck_id: ATRAXA_DECK_ID })
    expect(callsTo(fetchMock, '/api/active-deck') - before).toBe(1)
  })

  it('ignores a malformed frame without closing the socket or the app (AC 13)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    const fetchMock = answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    await connect()
    const before = fetchMock.mock.calls.length

    await driveSocket(() => {
      socket().onmessage?.({ data: 'not json at all' })
      socket().onmessage?.({ data: '{"kind": "telemetry"}' })
      socket().onmessage?.({ data: JSON.stringify({ kind: 42 }) })
    })

    expect(fetchMock.mock.calls.length).toBe(before)
    expect(sockets[0].closed).toBe(0)
    expect(
      screen.getByRole('heading', { level: 1, name: 'Atraxa Counter Cabinet v2 (owned)' }),
    ).toBeVisible()
  })

  // ==================== dw:3472 + dw:3544 — THE TERMINAL STALLED PANEL =================
  it('recovers the stalled panel when the socket says something moved (AC 15)', async () => {
    // C3 retro R3: *"c5-6 resolves the family; it should not solve one third of it."* This is the
    // sibling that was felt live at Block I — wire `200`, poll count moved by exactly 0 over 45 s,
    // because `RETRIES_QUIETLY['database-updating-stalled']` is `false` and rightly so: the quiet
    // retry has already been running and has not worked. The replacement signal is the socket.
    answering(refusal('database_unavailable', 503))

    render(<App />)
    await settle()
    await connect()
    await advance(60_000)
    expect(screen.getByRole('region', { name: 'Card database still updating.' })).toBeVisible()

    // The user obeys the panel, the rebuild finishes, and the agent touches a deck. Before this
    // story the screen stayed exactly as it was until a manual refresh.
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))
    await push('deck_changed', { deck_id: ATRAXA_DECK_ID })

    expect(
      screen.getByRole('heading', { level: 1, name: 'Atraxa Counter Cabinet v2 (owned)' }),
    ).toBeVisible()
  })

  it('re-drives the poll on RECONNECT too, not only on an event (AC 15)', async () => {
    // The other half of Q5: a reconnect restarts the poll unconditionally, because a socket
    // coming back is the strongest evidence the app gets that the process it was talking to is
    // gone. A stalled clock inherited from a process that no longer exists is not evidence.
    answering(refusal('database_unavailable', 503))

    render(<App />)
    await settle()
    await connect()
    await advance(60_000)
    expect(screen.getByRole('region', { name: 'Card database still updating.' })).toBeVisible()

    await drop()
    answering(decks('Boros Aggro'))
    await advance(SOCKET_BASE_MS)
    await connect()

    expect(screen.getByRole('region', { name: NO_DECK })).toBeVisible()
  })

  // ==================== dw:3652 — THE TERMINAL CARD ID ================================
  it('gives an exhausted card id its attempts back on reconnect (AC 16, Q6)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    await connect()

    // Burn one id's three attempts against a backend that is refusing with a token
    // `CARD_READ_IS_RETRYABLE` says IS retryable — which is exactly the case the ledger recorded:
    // everything else self-heals and this one does not.
    const failing = () =>
      Promise.resolve({ kind: 'error', reason: 'database_unavailable' } as const)
    await act(async () => {
      for (let n = 0; n < MAX_ATTEMPTS_PER_CARD; n += 1) await hydrateCard('burned-id', failing)
    })
    const spent = useCardStore.getState().cards['burned-id']
    expect(spent).toEqual(expect.objectContaining({ status: 'unknown', retryable: false }))

    await drop()
    await advance(SOCKET_BASE_MS)
    await connect()

    // Askable again — and note what did NOT happen: nothing was reset. The hydrated entries this
    // cache shares with Epic 6's views are untouched; only the budget came back.
    expect(useCardStore.getState().cards['burned-id']).toEqual(
      expect.objectContaining({ status: 'unknown', retryable: true }),
    )
  })
})

/**
 * The connection pill against the REAL loop (story c5-7, AC 1, AC 7, AC 18).
 *
 * ================= WHY THESE ASSERTIONS ARE HERE AND NOT IN THE COMPONENT TEST =========
 *
 * `ConnectionPill.test.tsx` drives the two slices directly and proves what the component makes of
 * them. Neither of the two claims below can be made from there:
 *
 *   1. **The pill is on EVERY surface** (AC 1). That is a fact about `App`'s composition — six
 *      arms, five of which render a `StatePanel` into the left slot — and the exact failure mode
 *      it guards is a pill mounted inside the deck-only Fragment, which would look correct in a
 *      component test and be absent on five screens.
 *   2. **A real drop moves it** (AC 18). `applyConnection('down')` in a component test asserts
 *      that the pill reads a field. This walks c5-6's actual machinery — a socket that fails four
 *      times over sixty seconds — so the dot the user would see is the dot produced by the loop.
 *
 * The `FakeSocket` + fake-timer idiom is the one the c5-6 block above established; nothing new is
 * introduced here.
 */
describe('the connection pill reports the real loop (c5-7)', () => {
  const DISCONNECTED = 'Lost the companion backend.'
  const NO_DECK = 'No deck on the glass.'

  const pill = () => document.querySelector('.connection-pill')!
  const dotClass = () => document.querySelector('.connection-pill-dot')!.className
  const announcement = () => document.querySelector('.connection-pill-announcement')!.textContent

  const backendDown = () => {
    const fetchMock = vi.fn(() => Promise.reject(new TypeError('Failed to fetch')))
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  // ==================== AC 18 — THE WALK ==============================================
  it('walks live -> reconnecting -> down on the real backoff, and back (AC 2, AC 4, AC 18)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()

    // COLD OPEN is `'reconnecting'` before the first upgrade completes — the honest value, and
    // the reason the announcement policy must not fire on mount (Q4).
    expect(dotClass()).toContain('is-reconnecting')
    expect(pill()).toHaveTextContent(CONNECTION_WORDS.reconnecting)
    expect(announcement()).toBe('')

    // LIVE. The first upgrade lands, and THIS is the first thing the region ever says.
    await connect()
    expect(dotClass()).toContain('is-live')
    expect(pill()).toHaveTextContent(pillText('live', 'Atraxa Counter Cabinet v2 (owned)'))
    expect(announcement()).toBe(pillText('live', 'Atraxa Counter Cabinet v2 (owned)'))

    // RECONNECTING. A drop, and the pre-exhaustion window: caution dot, deck still named, and
    // (UX-DR35) the deck itself still on the glass — the pill does not pre-empt the panel. This
    // is a genuine transition (live -> reconnecting), so per Q4's ruling the region announces it.
    backendDown()
    await drop()
    expect(dotClass()).toContain('is-reconnecting')
    expect(pill()).toHaveTextContent('Atraxa Counter Cabinet v2 (owned)')
    expect(announcement()).toBe(pillText('reconnecting', 'Atraxa Counter Cabinet v2 (owned)'))
    expect(screen.queryByRole('region', { name: DISCONNECTED })).toBeNull()

    // DOWN. Both gates — sixty seconds AND four observed failures — which is what
    // `advance(DISCONNECTED_AFTER_MS)` over a dead backend produces.
    await advance(DISCONNECTED_AFTER_MS)
    expect(dotClass()).toContain('is-down')
    expect(pill().textContent).toBe(CONNECTION_WORDS.down)
    expect(announcement()).toBe(CONNECTION_WORDS.down)

    // RECOVERY, with no reload. The dot goes positive again and the words come back with it.
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))
    await advance(30_000)
    await connect()
    expect(dotClass()).toContain('is-live')
    expect(announcement()).toContain(CONNECTION_WORDS.live)
  })

  // ==================== AC 7 — THE PILL AND THE PANEL, TOGETHER ========================
  it('renders BESIDE the Disconnected panel, not instead of it (AC 7)', async () => {
    // `EXPERIENCE.md:119` writes this state as "Left column + pill" — both, simultaneously. The
    // failure it guards against is a `surfaceOf`-driven pill, which would go quiet here.
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    backendDown()

    render(<App />)
    await settle()
    await advance(DISCONNECTED_AFTER_MS)

    expect(screen.getByRole('region', { name: DISCONNECTED })).toBeVisible()
    expect(pill()).toBeVisible()
    expect(dotClass()).toContain('is-down')
  })

  // ==================== AC 1 — EVERY SURFACE ==========================================
  it('is present on a STATE-PANEL surface, where the left slot is not a deck at all (AC 1)', async () => {
    // The landmine, asserted from the outside: `App.tsx` renders `<StatePanel>` into `left` in
    // five of its six arms, so a pill mounted in the deck-only Fragment would be absent here and
    // present in every component test.
    booting(activeDeck(null))
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    await connect()

    expect(screen.getByRole('region', { name: NO_DECK })).toBeVisible()
    expect(pill()).toBeVisible()
    // No deck loaded, so no name — and no placeholder standing in for one (AC 6).
    expect(pill().textContent).toBe(CONNECTION_WORDS.live)
  })

  it('is present on a COLD OPEN, before any answer has arrived at all (AC 1)', async () => {
    // The very first paint: no socket, no poll answer, no deck. `settle()` is deliberately NOT
    // awaited — this is the frame before anything resolves.
    booting(activeDeck(null))
    answering(decks())

    render(<App />)

    expect(pill()).toBeVisible()
    expect(dotClass()).toContain('is-reconnecting')
    expect(announcement()).toBe('')
    await settle()
  })

  it('is present on an EMPTY deck, and names it (AC 1, AC 6)', async () => {
    booting(
      activeDeck(ATRAXA_DECK_ID),
      deckDetail({ cards: [], mainboard_count: 0, sideboard_count: 0, distinct_cards: 0 }),
    )
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    await connect()

    expect(screen.getByText(EMPTY_DECK_LINE)).toBeVisible()
    expect(pill()).toHaveTextContent('Atraxa Counter Cabinet v2 (owned)')
  })

  // ==================== AC 9 — THE DOM POSITION, AT THE ROOT ===========================
  it('is the LAST Tab stop before the footer links, on a state-panel surface too (AC 9)', async () => {
    // The corridor pins above assert this on a loaded deck. Asserted here as well because the
    // shell slot is what makes it true, and a slot is easy to move: `AppShell` renders the pill
    // between `</main>` and `<footer>` on every arm, not only the one with a deck in it.
    booting(activeDeck(null))
    answering(decks('Atraxa Counter Cabinet v2 (owned)'))

    render(<App />)
    await settle()
    await connect()

    const focusables = [...document.querySelectorAll<HTMLElement>('a[href], button, [tabindex]')]
    const footerLinks = within(screen.getByRole('contentinfo')).getAllByRole('link')
    expect(footerLinks).toHaveLength(2)
    expect(focusables.indexOf(pill() as HTMLElement)).toBe(focusables.indexOf(footerLinks[0]) - 1)
  })
})

/**
 * The glass follows the agent's active-deck choice (story c6-3).
 *
 * ================= WHY THIS BLOCK IS TESTS AND NOTHING ELSE =============================
 *
 * The runtime path this story is named for ALREADY SHIPPED — at c4-2 (the boot), c4-5 (the
 * inspection release) and c5-6 (the socket and its one system-event action) — and the C5 retro
 * says so in writing (item J2: *"C5's `connection.ts` already re-drives the deck boot on
 * `active_deck_changed`"*). So what c6-3 owes is PROOF, not plumbing, and Q1 was ruled that way
 * before a line was written: a tests-only diff, runtime code only if a test exposes a real defect.
 * None did.
 *
 * The block above at `switches decks on active_deck_changed` already pins **none → deck**, which
 * is AC 1; it is cited rather than duplicated. The four gaps left open, and closed here:
 *
 *   1. **deck A → deck B** at App level. The shipped test only ever went from no-deck to a deck,
 *      so nothing asserted what happens to the deck being LEFT.
 *   2. **The pin release across an envelope-driven switch.** `CardDetail.test.tsx:646` drives the
 *      `boards` prop directly — no envelope, no App, no socket — so the release had never been
 *      observed as a consequence of a frame arriving on the wire.
 *   3. **The 404-after-switch, from a mounted App.** `deck.test.ts:260` drives the boot's readers
 *      directly; this walks the whole path to a rendered panel.
 *   4. **The none-interlude stale pin** — found while writing this story, and ruled ACCEPTED rather
 *      than fixed (Q2, 2026-08-09). See the third test for what that means and why.
 *
 * ================= AC 3 IS STRUCTURAL, AND THE TEST IS A REQUEST LOG ====================
 *
 * *"It must not treat `active_deck_changed` as `deck_changed`"* is satisfied by REQUEST ORDER, not
 * by a branch: `connection.ts:96-108` reads neither the kind nor the payload, and the boot it
 * re-drives asks `GET /api/active-deck` **first**. So the id of the deck being left is never
 * interpolated into anything, and the way to assert that is to audit every path asked since the
 * envelope — which is what {@link pathsSince} is for. There is deliberately no `deck_changed`
 * branch to test; adding one would be building c7-3's story.
 *
 * ================= WHAT THESE TESTS CANNOT SEE =========================================
 *
 * The real WebSocket. `FakeSocket` is the transport and nothing else, so a defect in the wire
 * itself — a frame that never arrives — is invisible here; c5-8's one real-socket test owns that
 * (AD-10) and is push-shaped and untouched. AC 5 ("several tabs, every tab switches") is likewise
 * not testable from one jsdom: all-tabs delivery is `ws.py` fan-out, tested at c5-4, and a
 * two-instance mount here would fake the very fan-out it claimed to prove (Q5). What each tab does
 * on receipt is exactly what this block pins.
 */
describe('the glass follows the agent’s active-deck choice (c6-3, AC 2, AC 3, AC 4)', () => {
  const NO_DECK = 'No deck on the glass.'
  const SKIP_LINK = 'Skip past the deck grid'
  const CARD_DETAIL = 'Card detail'
  const ATRAXA_NAME = 'Atraxa Counter Cabinet v2 (owned)'

  /**
   * Deck B — ✅ **VERIFIED REAL** against the live database at story time: id, name, format and
   * both counts are `Arabella Mobilize (Boros) v2 - owned` as `list_decks` reports it, and the two
   * cards below are real rows of that real deck at their real quantities and real costs.
   *
   * A SECOND deck is the whole point: every fixture in this file until now has been one deck, so
   * "switches to the new deck" and "does not refetch the old one" were both unassertable. Built
   * through `deckDetail`'s existing overrides rather than as a second literal body, so there is
   * still exactly one place that knows the shape of a deck-detail response.
   */
  const ARABELLA_DECK_ID = '45d80726-0f7b-460a-97fc-d0b457215d6d'
  const ARABELLA_NAME = 'Arabella Mobilize (Boros) v2 - owned'

  const arabellaDetail = () =>
    deckDetail({
      id: ARABELLA_DECK_ID,
      name: ARABELLA_NAME,
      format: 'standard',
      mainboard_count: 60,
      distinct_cards: 18,
      cards: [
        deckCard('Arabella, Abandoned Doll', 'Legendary Artifact Creature — Toy', 4, '{R}{W}', 2),
        deckCard('Mountain', 'Basic Land — Mountain', 6),
      ],
    })

  /**
   * Every path asked since a marker index, so ONE envelope's traffic can be audited on its own.
   *
   * A marker rather than a fresh `answering()` because re-stubbing mid-test would throw away the
   * boot's own history, and the claim AC 3 makes is about what the switch did — not about what the
   * whole test did.
   */
  const pathsSince = (fetchMock: ReturnType<typeof answering>, from: number) =>
    fetchMock.mock.calls.slice(from).map(([input]) => String(input))

  /**
   * Deck-DETAIL reads of ONE id. Exact equality, not `startsWith`: `/api/deck/{id}/format-check`
   * shares the prefix, and a switch legitimately fires one of those for the NEW deck (`App.tsx`'s
   * `[deckId, emptyDeck]` effect). Counting by prefix would fold the two together and make every
   * assertion below either flaky or vacuous.
   */
  const detailReadsOf = (paths: readonly string[], deckId: string) =>
    paths.filter((path) => path === `/api/deck/${deckId}`).length

  const activeDeckReads = (paths: readonly string[]) =>
    paths.filter((path) => path === '/api/active-deck').length

  const tiles = () => [...document.querySelectorAll<HTMLElement>('.card-tile')]
  const detailName = () => document.querySelector('.card-detail-name')?.textContent ?? null
  const unpinControl = () => document.querySelector('.card-detail-unpin')

  beforeEach(() => {
    // ⚠️ THE FILE'S OWN `beforeEach` DOES NOT COVER THESE TWO, and both are module-scope state
    // that a previous test leaves behind: the inspection slice (a live `pinnedId`) and
    // `deckMemory`'s `lastBoards`. Every existing test in this file survives that because a
    // completed boot releases a stale pin on its way in — which is precisely the mechanism these
    // tests are trying to OBSERVE, so inheriting it would make them assert their own premise.
    // Reset here rather than in the shared block: this is the only describe that depends on
    // starting from a genuine cold open, and widening the shared block would re-baseline 69 files
    // for one story's benefit.
    resetInspection()
    resetDeckMemory()
  })

  // ==================== AC 2 + AC 3 — THE SWITCH, AND THE DECK IT LEAVES ================
  it('switches deck → deck, releases the old deck’s pin, and never asks for the deck it left (AC 2, AC 3)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    const fetchMock = answering(decks(ATRAXA_NAME, ARABELLA_NAME))

    render(<App />)
    await settle()
    await connect()
    expect(screen.getByRole('heading', { level: 1, name: ATRAXA_NAME })).toBeVisible()

    // PIN THE SECOND TILE, NOT THE FIRST, and that choice is what makes the release observable at
    // all. `Llanowar Elves` is ALREADY deck A's cold-open target, so a pin on it would agree with
    // the default target — and the assertion after the switch could not tell a released pin from a
    // surviving one. `Forest` disagrees with the default, so it can only still be showing if the
    // release failed. The click is the real pin gesture (c4-5), not a `setState`.
    act(() => {
      tiles()[1].click()
    })
    await settle()
    expect(detailName()).toBe('Forest')
    expect(unpinControl()).not.toBeNull()

    // The agent switches decks. The payload names deck B, and the app pointedly does not read it.
    const marker = fetchMock.mock.calls.length
    booting(activeDeck(ARABELLA_DECK_ID), arabellaDetail())
    await push('active_deck_changed', { deck_id: ARABELLA_DECK_ID })
    await settle()

    expect(screen.getByRole('heading', { level: 1, name: ARABELLA_NAME })).toBeVisible()
    expect(screen.queryByRole('heading', { level: 1, name: ATRAXA_NAME })).toBeNull()

    // AC 3, MADE MECHANICAL. One envelope buys exactly one active-deck read and exactly one read
    // of the deck being switched TO — and zero reads of the deck being switched FROM, which is the
    // conflation `contracts.py:902-905` warns about ("refetches the deck it is leaving instead of
    // the one it is switching to") shown to be unavailable here.
    const switchPaths = pathsSince(fetchMock, marker)
    expect(activeDeckReads(switchPaths)).toBe(1)
    expect(detailReadsOf(switchPaths, ARABELLA_DECK_ID)).toBe(1)
    expect(detailReadsOf(switchPaths, ATRAXA_DECK_ID)).toBe(0)

    // …AND THE WHOLE LOG SWEPT FOR THE OLD ID, WHICH IS c6-2's GREPTILE LESSON APPLIED. That
    // review patched an unbounded echo on the one branch the finding cited and left three siblings
    // open; Greptile found them after the merge. The AC here names the deck read, so asserting only
    // that one path would repeat the mistake in miniature: the format check and the hydration sweep
    // are deck-scoped requests too. Nothing asked since the envelope may name deck A at all.
    expect(switchPaths.filter((path) => path.includes(ATRAXA_DECK_ID))).toEqual([])

    // THE RELEASE, MADE VISIBLE (AC 2). The pin is gone — no unpin control, because it renders only
    // while pinned — and the panel has landed on deck B's OWN cold-open card rather than sitting
    // empty (UX-DR20: "never empty while a deck is loaded"). `Arabella, Abandoned Doll` is that
    // card because `Legendary Artifact Creature — Toy` groups as **Creature**, which leads
    // `TYPE_GROUPS`, so `Artifact` never gets a look in.
    expect(unpinControl()).toBeNull()
    expect(detailName()).toBe('Arabella, Abandoned Doll')
    expect(useInspectionStore.getState().pinnedId).toBeNull()

    // One socket throughout. A switch is a re-drive of the boot, never a reconnect.
    expect(sockets).toHaveLength(1)
  })

  // ==================== AC 4 — THE DECK THE AGENT CHOSE IS ALREADY GONE =================
  it('clears to the no-active-deck state when the deck the agent chose 404s (AC 4)', async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    const fetchMock = answering(decks(ATRAXA_NAME, ARABELLA_NAME))

    render(<App />)
    await settle()
    await connect()
    expect(screen.getByRole('heading', { level: 1, name: ATRAXA_NAME })).toBeVisible()
    expect(screen.getByRole('button', { name: SKIP_LINK })).toBeVisible()

    // The agent set a deck that no longer exists — deleted between its `PUT` and this read. The
    // 404 reaches the client as a TOKEN and never as a status code (AD-16):
    // `{kind:'error', reason:'deck_not_found'}` maps through `PANEL_FOR_REASON` to
    // `'no-active-deck'`, and `stateForPanel` turns that into `{status:'none'}`.
    const marker = fetchMock.mock.calls.length
    booting(activeDeck(ARABELLA_DECK_ID), refusal('deck_not_found', 404))
    await push('active_deck_changed', { deck_id: ARABELLA_DECK_ID })
    await settle()

    const panel = screen.getByRole('region', { name: NO_DECK })
    expect(panel).toBeVisible()
    // A STATE, NOT AN ERROR (FR-11) — the distinction the whole token mapping exists to make.
    expect(screen.queryByRole('region', { name: 'The companion hit a bug.' })).toBeNull()
    // The deck that WAS on the glass is gone from both columns, not left stale beside the panel.
    expect(screen.queryByRole('heading', { level: 1, name: ATRAXA_NAME })).toBeNull()
    expect(screen.queryByRole('region', { name: CARD_DETAIL })).toBeNull()
    // …and the skip link is withdrawn with the grid it existed to skip (UX-DR31). Its ABSENCE is
    // the cheap half of that rule, asserted here because this path reaches it; the full keyboard
    // floor stays Epic 4's suite.
    expect(screen.queryByRole('button', { name: SKIP_LINK })).toBeNull()
    // The panel says what IS available, from `system.decks` — names only, non-clickable.
    expect(within(panel).getByText(ARABELLA_NAME)).toBeVisible()

    // NO RETRY STORM, WHICH IS THE OTHER HALF OF THE STATE BEING A STATE.
    // `RETRIES_QUIETLY['no-active-deck']` is `false`: the boot lands on `'none'` and stops, because
    // recovery here is the agent's next set arriving on the socket — not a poll grinding against a
    // deck that will never come back. A full minute of a mounted, idle tab buys zero requests on
    // either boot route.
    const afterClear = fetchMock.mock.calls.length
    await advance(60_000)
    const idlePaths = pathsSince(fetchMock, afterClear)
    expect(detailReadsOf(idlePaths, ARABELLA_DECK_ID)).toBe(0)
    expect(activeDeckReads(idlePaths)).toBe(0)
    // NON-VACUITY FOR THE TWO ZEROES ABOVE: a torn-down app makes no requests either, so "quiet"
    // and "dead" are the same measurement without this. The panel is still on the glass and the
    // socket is still the one this test opened — quiet because it is settled, not because it left.
    expect(screen.getByRole('region', { name: NO_DECK })).toBeVisible()
    expect(sockets).toHaveLength(1)
    expect(sockets[0].closed).toBe(0)

    // The clear cost exactly what the switch costs: one active-deck read, one deck read, no more.
    const clearPaths = pathsSince(fetchMock, marker)
    expect(activeDeckReads(clearPaths)).toBe(1)
    expect(detailReadsOf(clearPaths, ARABELLA_DECK_ID)).toBe(1)
  })

  // ==================== Q2 — THE PIN THAT OUTLIVES ITS DECK, ACCEPTED AND PINNED ========
  it('heals a pin that outlived a no-active-deck interlude instead of showing it on the next deck (AC 2, Q2)', async () => {
    // ⚠️ THIS TEST DOCUMENTS A LATENT STATE RATHER THAN A FIX, BY RULING (Q2, Brad 2026-08-09).
    //
    // The release lives in `CardDetail`'s `[boards]` effect, and that effect only runs while a deck
    // surface is MOUNTED. So on the path below — pinned deck, then a fall to a state panel — the
    // panel unmounts without clearing and the slice keeps a `pinnedId` for a deck that is no longer
    // on the glass. Ruled accepted rather than fixed, and the two reasons are both asserted here:
    // while the state exists it is INVISIBLE (there is no right column to render it in), and it
    // SELF-HEALS at the exact moment it could first matter (the next deck's boards arrive and the
    // shipped release fires before anything stale is settled-visible). A fix would need a second
    // release site — a panel-fall effect — for zero user-visible gain, and a second store-writer
    // path for the governance suites to scrutinise.
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks(ATRAXA_NAME, ARABELLA_NAME))

    render(<App />)
    await settle()
    await connect()

    act(() => {
      tiles()[1].click()
    })
    await settle()
    expect(detailName()).toBe('Forest')

    // Deck A is deleted out from under the pin. The re-drive's active-deck read still names it —
    // the backend will keep reporting a dead id, and the client does not PUT to correct it
    // (`deck.ts:251-258`, accepted residue) — so the deck read 404s and the surface falls.
    booting(activeDeck(ATRAXA_DECK_ID), refusal('deck_not_found', 404))
    await push('active_deck_changed', { deck_id: ATRAXA_DECK_ID })
    await settle()

    expect(screen.getByRole('region', { name: NO_DECK })).toBeVisible()
    // THE LATENT STATE, ASSERTED RATHER THAN DENIED — this is the honest half of "accept and pin".
    expect(useInspectionStore.getState().pinnedId).toBe('id-Forest')
    // …and INVISIBLE while it exists, which is the reason it is acceptable. There is no panel.
    expect(screen.queryByRole('region', { name: CARD_DETAIL })).toBeNull()

    // Now the agent picks a real deck. The interlude is where a naive implementation would carry
    // `Forest` onto a deck that has never contained one.
    booting(activeDeck(ARABELLA_DECK_ID), arabellaDetail())
    await push('active_deck_changed', { deck_id: ARABELLA_DECK_ID })
    await settle()

    expect(screen.getByRole('heading', { level: 1, name: ARABELLA_NAME })).toBeVisible()
    // SELF-HEALED. `replacesRememberedDeck` compares the boards REFERENCE, which `deck.ts` mints
    // once per completed boot — so it is still holding deck A's from before the interlude and the
    // release fires on deck B's arrival, one deck later than the pin was set.
    expect(useInspectionStore.getState().pinnedId).toBeNull()
    expect(unpinControl()).toBeNull()
    expect(detailName()).toBe('Arabella, Abandoned Doll')
  })
})

// =====================================================================================
// c6-5 — THE AGENT VIEW REACHES THE OVERLAY SLOT, AND ESC LAYERS OVER THE PIN
// =====================================================================================

describe('the agent view fills the shell’s overlay slot (c6-5, AC 4, AC 5, AC 6)', () => {
  const ATRAXA_NAME = 'Atraxa Counter Cabinet v2 (owned)'
  const overlay = () => document.querySelector('.app-shell-overlay')
  const tiles = () => [...document.querySelectorAll<HTMLElement>('.card-tile')]
  const unpinControl = () => document.querySelector('.card-detail-unpin')
  // c6-6 gave `AgentViewContent` the four fields the two stories after it read — the envelope
  // `id` (the replace key), `ts` (c6-8's pill time), the `kind` and the items themselves — so
  // this fixture is a whole one. These tests still exercise the STORE-driven path (c6-5's
  // claim); the socket-driven path is c6-6's own describe further down.
  const SUGGESTIONS = {
    id: 'push-c6-5',
    ts: '2026-08-11T09:15:00Z',
    kind: 'suggestions',
    title: 'Suggestions',
    count: 2,
    items: [],
  } as const

  /** Esc, delivered where a browser delivers it: at the focused element, bubbling. */
  const escape = () =>
    act(() => {
      document.activeElement!.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }),
      )
    })

  const bootedDeck = async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    answering(decks(ATRAXA_NAME))
    render(<App />)
    await settle()
    await connect()
  }

  beforeEach(() => {
    // ⚠️ THE FILE'S OWN `beforeEach` COVERS NONE OF THESE THREE, and all three are module-scope
    // state a previous test leaves behind. c6-3 nested the first two for its own reasons; the
    // agent-view slice joins them for a sharper one — its whole contract is that closing a view
    // does NOT clear it, so a view left retained by one test is exactly the premise the next one
    // is trying to establish for itself.
    resetInspection()
    resetDeckMemory()
    resetAgentView()
  })

  it('renders NOTHING in the slot while the store is closed (AC 9’s click-swallower)', async () => {
    // `App` passes an ABSENT `overlay`, so `filled()` refuses to mount the wrapper at all. Not a
    // hidden element, not an empty one: no element. A full-window fixed layer containing nothing
    // is what `AppShell.tsx:134-139` warns presents as "the app stopped responding to clicks".
    await bootedDeck()

    expect(overlay()).toBeNull()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('mounts the view when the store opens, and unmounts it when the store closes', async () => {
    await bootedDeck()

    act(() => openAgentView(SUGGESTIONS))
    expect(overlay()).not.toBeNull()
    expect(screen.getByRole('dialog')).toHaveAccessibleName(SUGGESTIONS.title)

    act(() => closeAgentView())
    expect(overlay()).toBeNull()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('re-opens the SAME view after dismissal, with no second push (AC 5, UX-DR34)', async () => {
    // UX-DR34 end to end: the content outlives the dismissal, so the view is re-openable for the
    // rest of the session. c6-8's nav pills are what will re-open it from the glass.
    await bootedDeck()

    act(() => openAgentView(SUGGESTIONS))
    act(() => closeAgentView())
    expect(screen.queryByRole('dialog')).toBeNull()

    const retained = useAgentViewStore.getState().content
    expect(retained).toEqual(SUGGESTIONS)

    act(() => openAgentView(retained!))
    expect(screen.getByRole('dialog')).toHaveAccessibleName(SUGGESTIONS.title)
  })

  it('closes on the close pill and hands focus back to the tile that opened it (AC 4)', async () => {
    await bootedDeck()

    // A real element of the real app holds focus when the view opens — not a fixture button.
    const tile = tiles()[1]
    act(() => tile.focus())
    act(() => openAgentView(SUGGESTIONS))
    expect(document.activeElement).toBe(
      screen.getByRole('heading', { level: 2, name: SUGGESTIONS.title }),
    )

    act(() => {
      screen.getByRole('button', { name: CLOSE_PILL_LABEL }).click()
    })

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(tile)
    expect(document.activeElement).not.toBe(document.body)
  })

  // ==================== THE TEST THREE SHIPPED COMMENTS HAVE PROMISED SINCE c4-5 ========
  it('ESC CLOSES THE VIEW AND LEAVES THE PIN (UX-DR39, EXPERIENCE.md:141, Flow 1 :188)', async () => {
    // `CardDetail.tsx:99-101`, `inspection.ts:65-67` and `CardDetail.test.tsx:521-524` all said
    // *"no overlay exists yet, so this story cannot test the layering"*. This is that test, over
    // BOTH real document listeners at once: CardDetail's bubble-phase pin release and the agent
    // view's capture-phase dismissal, in one app, on one keystroke.
    await bootedDeck()

    // A REAL pin, set by the real gesture (a click on a tile), not by a `setState`.
    act(() => {
      tiles()[1].click()
    })
    await settle()
    const pinned = useInspectionStore.getState().pinnedId
    expect(pinned).not.toBeNull()
    expect(unpinControl()).not.toBeNull()

    act(() => openAgentView(SUGGESTIONS))
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    escape()

    expect(screen.queryByRole('dialog'), 'the topmost thing closed').toBeNull()
    expect(
      useInspectionStore.getState().pinnedId,
      'the pin survived the same Esc — UX-DR39 closes the TOPMOST thing, one per keystroke',
    ).toBe(pinned)
    expect(unpinControl()).not.toBeNull()
  })

  it('releases the pin on the NEXT Esc, once the view is gone (non-vacuity)', async () => {
    // Without this, the assertion above would pass just as well against a pin that Esc could
    // never release at all — and the layering claim would be about a dead listener. Two
    // keystrokes, two dismissals, in the order UX-DR39 specifies.
    await bootedDeck()

    act(() => {
      tiles()[1].click()
    })
    await settle()
    act(() => openAgentView(SUGGESTIONS))

    escape()
    expect(useInspectionStore.getState().pinnedId).not.toBeNull()

    escape()
    expect(useInspectionStore.getState().pinnedId).toBeNull()
    expect(unpinControl()).toBeNull()
  })
})

// =====================================================================================
// c6-6 — A PUSH OPENS ITS VIEW, AND A REPEAT PUSH REPLACES IT IN PLACE
// =====================================================================================

describe('a suggestions push opens its view, end to end (c6-6, AC 1, AC 2, AC 4, AC 5, AC 6)', () => {
  const ATRAXA_NAME = 'Atraxa Counter Cabinet v2 (owned)'
  const SKIP = 'Skip past the deck grid'
  const dialog = () => screen.queryByRole('dialog')
  // Queried by CLASS rather than by role: a state panel's headline is an `<h2>` too, and half
  // these tests deliberately put one on the glass behind the view.
  const viewTitle = () => document.querySelector<HTMLElement>('.agent-view-title')
  const viewCount = () => document.querySelector('.agent-view-count')
  const emptyLine = () => document.querySelector('.suggestions-view-empty')

  const ITEMS = [
    { card_id: 'c-1', reason: 'Fills the two-drop gap.' },
    { card_id: 'c-2', reason: 'Second body for the same slot.' },
  ]

  const bootedDeck = async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    const fetchMock = answering(decks(ATRAXA_NAME))
    render(<App />)
    await settle()
    await connect()
    return fetchMock
  }

  /**
   * A push, plus the frame the entry bloom needs in order to settle.
   *
   * This file runs on FAKE timers, so `requestAnimationFrame` does not fire on its own — and
   * `driveSocket`'s `advanceTimersByTimeAsync(0)` is not enough for it. Without this, every
   * dialog in this describe would sit permanently in `data-entering='true'` and the
   * "the bloom did not replay" assertion below would be unable to tell a settled view from a
   * remounted one.
   */
  const pushSettled = async (payload: Record<string, unknown>, id?: string) => {
    await push('suggestions', payload, id)
    await advance(20)
  }

  beforeEach(() => {
    // c6-3's discipline: the file's shared block covers none of these three, and all three are
    // module-scope state a previous test leaves behind. The agent-view slice matters most here —
    // its whole contract is that closing does NOT clear, so a view retained by an earlier test
    // is exactly the premise these tests establish for themselves.
    resetInspection()
    resetDeckMemory()
    resetAgentView()
  })

  it('opens the view with NO click — the frame is the whole gesture (AC 1, UX-DR34)', async () => {
    await bootedDeck()
    expect(dialog()).toBeNull()

    await push('suggestions', { title: 'Resilience options', items: ITEMS })

    // The 2026-07-25 arrival ruling, driven through the real socket seam: `client.ts` narrows the
    // frame, `socket.ts` dispatches it, `connection.ts` calls the verb, the store opens and `App`
    // fills the overlay slot. Nothing in this test writes a store.
    expect(dialog()).not.toBeNull()
    expect(dialog()).toHaveAccessibleName('Resilience options')
    expect(viewCount()).toHaveTextContent('2')
    expect(document.activeElement).toBe(viewTitle())
  })

  it('falls back to the authored title when the agent names nothing (Q7, dw:30-32)', async () => {
    await bootedDeck()

    await push('suggestions', { items: ITEMS })

    // `aria-labelledby` points at the heading, so a blank title would be a `role="dialog"` with
    // no discernible name at all — the ledger entry this closes, asserted where the accessible
    // name is actually computed rather than at the constant.
    expect(dialog()).toHaveAccessibleName(SUGGESTIONS_VIEW_TITLE)
  })

  it('renders the artefact’s line for an EMPTY push rather than rejecting it (AC 4)', async () => {
    await bootedDeck()

    await push('suggestions', { title: 'Nothing found', items: [] })

    expect(dialog()).not.toBeNull()
    expect(emptyLine()).not.toBeNull()
    expect(emptyLine()).toHaveTextContent(emptyPushLine('suggestions'))
    // `0` is a REAL count and renders — "0 suggestions" and "a view that does not count things"
    // are different sentences, and this is the first.
    expect(viewCount()).toHaveTextContent('0')
  })

  it('survives a frame with NO PAYLOAD AT ALL — the narrower validates only `kind`', async () => {
    // `agentEventOf` checks the discriminant and nothing else, so this frame reaches the builder
    // typed as a full event. A `TypeError` on that path is an uncaught exception inside a socket
    // message handler: the socket stays open and the push is silently lost. Serialised by hand
    // here so the absence is a genuinely absent KEY rather than an explicit `undefined`.
    await bootedDeck()

    await driveSocket(() =>
      socket().onmessage?.({
        data: JSON.stringify({ kind: 'suggestions', id: 'bare', ts: '2026-08-08T00:00:00Z' }),
      }),
    )

    expect(dialog()).not.toBeNull()
    expect(emptyLine()).not.toBeNull()
    expect(sockets[0].closed).toBe(0)
  })

  it('REPLACES in place on a second push — same dialog node, new content (AC 2)', async () => {
    await bootedDeck()
    await pushSettled({ title: 'First look', items: ITEMS }, 'push-1')
    const before = screen.getByRole('dialog')
    // Focus is moved somewhere real inside the view first, so "focus is on the heading" below is
    // a MOVE rather than the open-time hand-off's leftover.
    act(() => screen.getByRole('button', { name: CLOSE_PILL_LABEL }).focus())

    await push('suggestions', { title: 'Second look', items: [ITEMS[0]] }, 'push-2')

    // NODE IDENTITY is the load-bearing half of "in place": a `key` on `<AgentView>` would
    // satisfy every content assertion here and fail this one.
    expect(screen.getByRole('dialog')).toBe(before)
    expect(dialog()).toHaveAccessibleName('Second look')
    expect(viewCount()).toHaveTextContent('1')
    expect(document.activeElement).toBe(viewTitle())
    // The entry bloom did NOT replay — the crossfade is a different motion with its own token.
    expect(before).toHaveAttribute('data-entering', 'false')
  })

  it('RE-OPENS a view dismissed earlier, as a fresh mount (SC-1 — never swallowed)', async () => {
    await bootedDeck()
    await push('suggestions', { title: 'First look', items: ITEMS }, 'push-1')

    act(() => screen.getByRole('button', { name: CLOSE_PILL_LABEL }).click())
    expect(dialog()).toBeNull()
    // The content survived the dismissal — UX-DR34, and the premise of the re-open below.
    expect(useAgentViewStore.getState().content).not.toBeNull()

    await push('suggestions', { title: 'Second look', items: [] }, 'push-2')

    expect(dialog()).not.toBeNull()
    expect(dialog()).toHaveAccessibleName('Second look')
    // A MOUNT, not a replace: the overlay was absent, so the bloom runs exactly as it does for
    // the first push of the session.
    expect(dialog()).toHaveAttribute('data-entering', 'true')
  })

  it('stays open and stays VALID when the deck is lost behind it (AC 5, UX-DR37)', async () => {
    // *"Agent content is about cards, not about the deck's presence, so a lost deck does not
    // invalidate a tier list."* True by construction — nothing in the overlay path reads deck
    // state — so this pins the COMPOSED behaviour rather than describing the construction.
    await bootedDeck()
    await push('suggestions', { title: 'Resilience options', items: ITEMS })
    expect(dialog()).not.toBeNull()

    // `booting()` and NOT a second `answering()`: the deck-detail route is answered from the
    // module-level fixture this helper writes, so re-stubbing the poll would leave the refetch
    // still succeeding and the panel would never appear.
    booting(activeDeck(ATRAXA_DECK_ID), refusal('deck_not_found', 404))
    await push('deck_changed', { deck_id: ATRAXA_DECK_ID })

    // The panel really did take the left column — without this the survival below would be an
    // assertion about a page where nothing happened.
    expect(document.querySelector('.state-panel')).not.toBeNull()
    expect(document.querySelector('.card-tile')).toBeNull()
    // …and the view is untouched: still mounted, still named, still counting its own push.
    expect(dialog()).not.toBeNull()
    expect(dialog()).toHaveAccessibleName('Resilience options')
    expect(viewCount()).toHaveTextContent('2')
  })

  it('lands the reader on the state panel when the view closes over one (AC 5)', async () => {
    // EXPERIENCE.md:122's second clause. The remembered restore target is a card tile the panel
    // replaced, so the disconnected-restore arm is what runs — and Q5's ruling sends it to the
    // panel's headline rather than to the deck `<h1>`, which is no longer on the glass.
    await bootedDeck()
    act(() => {
      document.querySelectorAll<HTMLElement>('.card-tile')[1].focus()
    })
    const opener = document.activeElement
    expect(opener).not.toBe(document.body)

    await push('suggestions', { title: 'Resilience options', items: ITEMS })
    booting(activeDeck(ATRAXA_DECK_ID), refusal('database_unavailable', 503))
    await push('deck_changed', { deck_id: ATRAXA_DECK_ID })
    expect(opener?.isConnected).toBe(false)

    act(() => screen.getByRole('button', { name: CLOSE_PILL_LABEL }).click())

    expect(document.activeElement).toBe(document.querySelector('.state-panel-headline'))
    expect(document.activeElement).not.toBe(document.body)
  })

  it('withdraws the skip link and the grid’s Tab stops behind that panel (AC 5)', async () => {
    // The already-shipped withdrawals (c4-11's link, and the grid's stops vanishing with the
    // grid), pinned in the COMPOSED state this story creates — a panel behind an OPEN view. No
    // module was changed to make these true; what is new is that they are now asserted together
    // with a dialog on the glass, which is the arrangement AC 5 describes.
    await bootedDeck()
    await push('suggestions', { title: 'Resilience options', items: ITEMS })

    booting(activeDeck(ATRAXA_DECK_ID), refusal('database_unavailable', 503))
    await push('deck_changed', { deck_id: ATRAXA_DECK_ID })

    expect(document.querySelector('.state-panel')).not.toBeNull()
    expect(dialog()).not.toBeNull()
    expect(screen.queryByRole('button', { name: SKIP })).toBeNull()
    expect(document.querySelectorAll('.card-tile')).toHaveLength(0)
  })

  it('updates the NON-MOTION signals on a replace — heading, count, live region (AC 6)', async () => {
    // UX-DR43: *"motion is never the sole signal"*. The three signals this story owns are the
    // heading text, the count beside it, and a real mutation of the `aria-live` region. The nav
    // pill's unread marker and its timestamp are structurally c6-8's — the pill does not exist
    // yet, and the composition reference carries no timestamp in the view header — so what is
    // asserted for that half is that the store RETAINS the envelope's `ts` for c6-8 to render.
    await bootedDeck()
    await push('suggestions', { title: 'First look', items: ITEMS }, 'push-1')

    const region = viewTitle()!
    expect(region).toHaveAttribute('aria-live', 'polite')
    const records: MutationRecord[] = []
    const observer = new MutationObserver((list) => records.push(...list))
    observer.observe(region, { childList: true, characterData: true, subtree: true })
    try {
      await push('suggestions', { title: 'Second look', items: [ITEMS[0]] }, 'push-2')
    } finally {
      observer.disconnect()
    }

    expect(records.length).toBeGreaterThan(0)
    expect(region).toHaveTextContent('Second look')
    expect(viewCount()).toHaveTextContent('1')
    // The retained ordering key, unrendered by this story and read by the next one.
    expect(useAgentViewStore.getState().content?.ts).toBe('2026-08-08T00:00:00Z')
  })

  it('announces a replace whose title is BYTE-IDENTICAL to the one showing (Q4)', async () => {
    // FOUND BY A PLANT (2026-08-11): removing the heading's `key` left the test above green,
    // because two DIFFERENT titles mutate the region whatever mechanism is used. The claim that
    // actually needs an end-to-end pin is the common case — an agent that omits `payload.title`
    // twice, so both pushes carry the same fallback word and a plain re-render mutates nothing.
    await bootedDeck()
    await push('suggestions', { items: ITEMS }, 'push-1')

    const region = viewTitle()!
    expect(region).toHaveTextContent(SUGGESTIONS_VIEW_TITLE)
    const records: MutationRecord[] = []
    const observer = new MutationObserver((list) => records.push(...list))
    observer.observe(region, { childList: true, characterData: true, subtree: true })
    try {
      await push('suggestions', { items: [ITEMS[0]] }, 'push-2')
    } finally {
      observer.disconnect()
    }

    expect(records.length).toBeGreaterThan(0)
    expect(region).toHaveTextContent(SUGGESTIONS_VIEW_TITLE)
    // The push really was a different one — without this the mutation could be about nothing.
    expect(viewCount()).toHaveTextContent('1')
  })

  it('re-drives NO boot route — a push is content, not a staleness signal', async () => {
    // The property that separates this callback from the two system kinds beside it in the
    // dispatch switch. `deck_changed` means "ask again"; a push means "here it is", and an
    // implementation that re-drove the boot on one would double every push's cost forever.
    //
    // AMENDED BY c6-7, AND THE CLAIM IS SHARPENED RATHER THAN RELAXED. This read
    // `fetchMock.mock.calls.length` unchanged — "costs the app NO request" — which was true only
    // while a push rendered nothing. c6-7's rows hydrate their own ids (AC 7): a suggested card
    // is not in the deck, so nothing seeded it and the deck sweep will never reach it, and one
    // `GET /api/cards/{id}` per UNIQUE id is what this story exists to spend. Counting total
    // calls would have made that legitimate cost look like the regression this test guards
    // against, so the boot routes are now counted BY NAME — which is what the test always meant.
    const fetchMock = await bootedDeck()
    const boots = () =>
      deckDetailCalls(fetchMock) +
      formatCheckCalls(fetchMock) +
      callsTo(fetchMock, '/api/active-deck') +
      callsTo(fetchMock, '/api/decks')
    const before = boots()
    const cardsBefore = callsTo(fetchMock, '/api/cards/')

    await push('suggestions', { title: 'Resilience options', items: ITEMS })

    expect(boots(), 'a push re-drove a boot route').toBe(before)
    // …and the hydration really happened, so the assertion above is not passing because the view
    // rendered nothing at all: two items, two distinct ids, two reads.
    expect(callsTo(fetchMock, '/api/cards/') - cardsBefore).toBe(ITEMS.length)
    expect(sockets).toHaveLength(1)
  })
})

// =====================================================================================
// c6-7 — THE SUGGESTION ROWS, INSIDE THE REAL VIEW, ON THE REAL INSPECTION CONTRACT
// =====================================================================================

describe('a pushed suggestion is a card you can look at (c6-7, AC 2, AC 4, AC 7)', () => {
  const ATRAXA_NAME = 'Atraxa Counter Cabinet v2 (owned)'
  const unpinControl = () => document.querySelector('.card-detail-unpin')
  const detailName = () => document.querySelector('.card-detail-name')
  const rows = () => [...document.querySelectorAll<HTMLButtonElement>('.suggestion-row')]
  /**
   * The PIN announcement's region, by name.
   *
   * `document.querySelector('[aria-live]')` would be wrong here and quietly so: the app ships
   * exactly three live regions — this one, the connection pill's, and the agent view's own
   * heading — and while a view is open the heading is one of them. A DOM-order query would pick
   * whichever happened to come first.
   */
  const pinRegion = () => document.querySelector('.card-detail-announcement')

  /**
   * Two suggestions whose ids the card route can actually answer.
   *
   * The fixture route answers `/api/cards/{id}` by slicing `id-` off the path and echoing the
   * REST as the card's name, so an id shaped `id-{name}` is what makes a hydrated row carry a
   * name a test can read. That is the same convention the deck fixtures use.
   */
  const ITEMS = [
    { card_id: 'id-Llanowar Elves', reason: 'Fills the one-drop ramp slot.', category: 'ramp' },
    { card_id: 'id-Birds of Paradise', reason: 'Fixes all five colours.', confidence: 'high' },
  ]

  const bootedDeck = async () => {
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail())
    const fetchMock = answering(decks(ATRAXA_NAME))
    render(<App />)
    await settle()
    await connect()
    return fetchMock
  }

  const pushRows = async (items: unknown[] = ITEMS, id = 'push-c6-7') => {
    await push('suggestions', { title: 'Resilience options', items }, id)
    // The hydration effect fires on commit and its answers land a microtask later; without this
    // the rows are all still on their silent wells and every name assertion below reads ''.
    await settle()
    await advance(20)
  }

  /** Esc, delivered where a browser delivers it: at the focused element, bubbling. */
  const escape = () =>
    act(() => {
      document.activeElement!.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }),
      )
    })

  beforeEach(() => {
    resetInspection()
    resetDeckMemory()
    resetAgentView()
  })

  it('renders the rows INSIDE the dialog, hydrated from the card route (AC 7)', async () => {
    const fetchMock = await bootedDeck()
    await pushRows()

    const dialog = screen.getByRole('dialog')
    expect(rows()).toHaveLength(2)
    // Inside the dialog rather than merely on the page — the rows are the view's content, and
    // the shell needed no editing to hold them (`AgentView.test.tsx:158`'s claim, end to end).
    for (const row of rows()) expect(dialog).toContainElement(row)
    expect(rows()[0]).toHaveTextContent('Llanowar Elves')
    expect(rows()[0]).toHaveTextContent(ITEMS[0].reason)

    // ONE READ PER UNIQUE ID, over the real client and the real route (AD-12): these ids are in
    // no deck, so nothing seeded them and the deck sweep will never reach them.
    expect(callsTo(fetchMock, '/api/cards/id-Llanowar%20Elves')).toBe(1)
    expect(callsTo(fetchMock, '/api/cards/id-Birds%20of%20Paradise')).toBe(1)
  })

  it('hovering a row shows that card in the DETAIL PANEL, announcing nothing (UX-DR45)', async () => {
    await bootedDeck()
    await pushRows()

    fireEvent.mouseEnter(rows()[1])
    await settle()

    // The panel behind the view follows the row — the inspection contract is location-agnostic
    // and this is the first surface outside the deck to spend it.
    expect(detailName()).toHaveTextContent('Birds of Paradise')
    // A TRANSIENT TARGET MUST NOT ANNOUNCE (UX-DR45). Sweeping six rows would otherwise queue six
    // interruptions for a screen-reader user who is only moving a cursor.
    expect(pinRegion()).toBeEmptyDOMElement()
  })

  it('clicking a row pins it and announces ONCE, from the shipped region (AC 2)', async () => {
    await bootedDeck()
    await pushRows()

    fireEvent.click(rows()[0])
    await settle()

    expect(useInspectionStore.getState().pinnedId).toBe('id-Llanowar Elves')
    expect(unpinControl()).not.toBeNull()
    // THE SHIPPED REGION, not a second one. The rows add NO `aria-live` of their own — a second
    // region inside the dialog would announce the same arrival twice — so this is `CardDetail`'s
    // polite region carrying the pin, exactly as it does for a tile or a deck row. Asserted as
    // "none inside the list" rather than as a count of the whole document: the app ships three
    // live regions and the agent view's own heading is one of them.
    expect(document.querySelectorAll('.suggestions-view-rows [aria-live]')).toHaveLength(0)
    expect(pinRegion()).toHaveTextContent('Pinned — Llanowar Elves')
  })

  // ==================== UJ-1 STEP 6, WHICH FINALLY EXISTS END TO END ====================
  it('ESC CLOSES THE VIEW AND THE PIN SET FROM A ROW SURVIVES (AC 2, UJ-1 step 6)', async () => {
    // `EXPERIENCE.md:188`: *"dismissing a suggestion view leaves that card in the detail panel"*.
    // c6-5 pinned the Esc LAYERING with a pin set from a tile, because no row existed to set one
    // from; this is the same layering with the gesture the flow actually describes.
    //
    // Nothing implements the survival: `closeAgentView()` writes `status` and touches nothing in
    // the inspection slice, which is module-level state that outlives the dialog's unmount
    // (`inspection.ts:32-39` — *"Recorded here so c6-7 inherits it rather than re-deciding it"*).
    // This test is what turns that inheritance into a claim with a tripwire.
    await bootedDeck()
    await pushRows()

    fireEvent.click(rows()[0])
    await settle()
    expect(useInspectionStore.getState().pinnedId).toBe('id-Llanowar Elves')

    escape()

    expect(screen.queryByRole('dialog'), 'the topmost thing closed').toBeNull()
    // ONE Esc RELEASES ONE THING (UX-DR39). The pin is still held, and the panel is still showing
    // the suggested card — which is a card that is NOT in the open deck, the case that makes this
    // flow worth having.
    expect(useInspectionStore.getState().pinnedId).toBe('id-Llanowar Elves')
    expect(unpinControl()).not.toBeNull()
    expect(detailName()).toHaveTextContent('Llanowar Elves')

    // …and the SECOND Esc releases the pin, which is the layering c6-5 established holding with a
    // row-set pin rather than a tile-set one.
    escape()
    expect(useInspectionStore.getState().pinnedId).toBeNull()
  })

  it('degrades ONE unknown id and leaves its neighbours drawing art (AC 4, FR-13)', async () => {
    // End to end, over the real refusal: the route answers `card_not_found` for this id, the
    // cache records `placeholder: 'unknown-card'`, and the row draws the placeholder while its
    // REASON still renders. c6-6's structurally-deferred AC 3, discharged where its subject is.
    const fetchMock = await bootedDeck()
    const answer = fetchMock.getMockImplementation()!
    fetchMock.mockImplementation((input?: unknown) =>
      String(input) === '/api/cards/ghost'
        ? Promise.resolve(refusal('card_not_found', 404))
        : answer(input),
    )

    await pushRows([
      { card_id: 'ghost', reason: 'A card the corpus has never heard of.' },
      ITEMS[0],
    ])

    expect(rows()).toHaveLength(2)
    expect(rows()[0].querySelector('.card-placeholder')).toHaveTextContent('Unknown card')
    expect(rows()[0]).toHaveTextContent('A card the corpus has never heard of.')
    // THE NEIGHBOUR IS UNHARMED — one dead entry is one dead thumbnail, never a failed push.
    expect(rows()[1].querySelector('.suggestion-row-image')).toHaveAttribute(
      'src',
      '/api/card-image/id-Llanowar%20Elves',
    )
    expect(rows()[1]).toHaveTextContent('Llanowar Elves')
    // …and the unknown row refuses inspection, through the store, with the view still open.
    fireEvent.click(rows()[0])
    expect(useInspectionStore.getState().pinnedId).toBeNull()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('re-hydrates on a REPLACE, so the second push’s rows are not silent wells', async () => {
    // c6-6 replaces in place against a MOUNTED shell: the same component instance receives the
    // new items. A mount-only hydration effect would leave every id of the second push unfetched.
    const fetchMock = await bootedDeck()
    await pushRows([ITEMS[0]], 'push-1')
    expect(callsTo(fetchMock, '/api/cards/id-Llanowar%20Elves')).toBe(1)

    await pushRows([ITEMS[1]], 'push-2')

    expect(callsTo(fetchMock, '/api/cards/id-Birds%20of%20Paradise')).toBe(1)
    expect(rows()).toHaveLength(1)
    expect(rows()[0]).toHaveTextContent('Birds of Paradise')
  })

  it('survives a push whose items are malformed, with the socket still open (AD-7)', async () => {
    // The wholesale-failure case FR-13 bans: a `TypeError` in a row is React unmounting the whole
    // dialog around it, and the connection is what would look broken afterwards.
    await bootedDeck()
    await pushRows([
      { card_id: 42, reason: 'A number id.' },
      { card_id: 'id-Forest' },
      { reason: 'No id at all.' },
    ])

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(rows()).toHaveLength(3)
    // The connection is what would LOOK broken after a render crash: the fake socket counts its
    // own closes, and one that was never closed is one the app is still holding.
    expect(sockets).toHaveLength(1)
    expect(sockets[0].closed).toBe(0)
  })
})
