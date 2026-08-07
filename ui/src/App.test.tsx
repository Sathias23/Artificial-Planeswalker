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
import { resetFormatCheckState } from './state/formatCheck'
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
    // `/api/decks`, one `/api/active-deck`, one deck detail, TWO card hydrations, and — new in
    // this story — one format check. Six, and the new member is broken out beside it so that a
    // bump here can never again be absorbed as "the sweep got bigger".
    expect(formatCheckCalls(fetchMock)).toBe(1)
    expect(fetchMock).toHaveBeenCalledTimes(6)
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

  const STORE_DRIVEN_ARMS = ['disconnected', 'database-updating-stalled'] as const

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
    booting(activeDeck(ATRAXA_DECK_ID), deckDetail({ cards: [], mainboard_count: 0 }))
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

  it('pins 205 = 99 tiles + 6 flips + 1 oracle + 99 rows on the Atraxa shape, and the flip adjacency', async () => {
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
    // 1 skip + 99 tiles + 6 flips + 1 oracle + 99 rows + 2 footer links = 208 focusables…
    expect(focusables).toHaveLength(208)
    // …the corridor from the header to the first footer link is 205 stops…
    expect(at(footerLinks[0]) - at(skip) - 1).toBe(205)
    // …the link removes the first 105 of them (every tile and every flip control)…
    expect(at(oracle) - at(skip) - 1).toBe(105)
    // …and the footer is STILL 100 stops away after using it — the story's own headline, at this
    // deck's scale (206/105/101 is the LARGEST deck's row count, which carries a sideboard).
    expect(at(footerLinks[0]) - at(oracle)).toBe(100)

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

  it('pins 3 = 1 tile + 1 oracle + 1 row on the 1-card deck (Iron Man, Modern Marvel — reminder)', async () => {
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

    // 1 skip + 1 tile + 1 oracle + 1 row + 2 footer links = 6 focusables; corridor of 3.
    expect(focusables).toHaveLength(6)
    expect(at(footerLinks[0]) - at(skip) - 1).toBe(3)
    expect(at(oracle) - at(skip) - 1).toBe(1)
    expect(at(footerLinks[0]) - at(oracle)).toBe(2)
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
