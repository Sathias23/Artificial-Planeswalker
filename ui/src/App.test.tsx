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
import { INITIAL_SYSTEM_STATE, useSystemStore } from './state/systemState'

/** One canned answer, built the way the backend builds it: a token, and nothing else. */
const refusal = (reason: string, status: number) =>
  new Response(JSON.stringify({ reason }), { status })

const decks = (...names: string[]) =>
  new Response(JSON.stringify(names.map((name) => ({ id: name, name }))), { status: 200 })

/**
 * Answer the poll with each response in turn, repeating the last one forever.
 *
 * `globalThis.fetch` rather than an injected reader, deliberately: this file is the only place
 * the whole path — request, body parsing, token validation, panel choice, render — is exercised
 * end to end, and injecting past any of it would leave that seam untested at every level.
 */
const answering = (...responses: Response[]) => {
  let index = 0
  const fetchMock = vi.fn(() => {
    const response = responses[Math.min(index, responses.length - 1)]
    index += 1
    return Promise.resolve(response.clone())
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** Let the in-flight poll settle without waiting for real time. */
const settle = () => act(async () => void (await vi.advanceTimersByTimeAsync(0)))

const advance = (ms: number) => act(async () => void (await vi.advanceTimersByTimeAsync(ms)))

beforeEach(() => {
  vi.useFakeTimers()
  // The store is module-level, as a store is; without this the panel a previous test left behind
  // would be the panel the next one starts from.
  useSystemStore.setState(INITIAL_SYSTEM_STATE)
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
    expect(fetchMock).toHaveBeenCalledTimes(2)
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
    expect(fetchMock).toHaveBeenCalledTimes(1)
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
