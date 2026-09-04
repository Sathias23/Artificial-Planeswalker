import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Card, CardSummary, DeckCardSummary } from '../../api/schema'
import { UNKNOWN_CARD_LABEL } from '../../components/CardPlaceholder/copy'
import { resetCardCache, useCardStore } from '../../state/cards'
import { boardsOf } from '../../state/deckGroups'
import { flipCard, resetFaces } from '../../state/faces'
import { FLIP_LABEL } from '../FlipControl/copy'
import {
  clearPin,
  resetInspection,
  setFocused,
  setHovered,
  togglePin,
  useInspectionStore,
} from '../../state/inspection'
import { CardGrid } from '../CardGrid/CardGrid'
import { CardDetail } from './CardDetail'
import { ORACLE_SCROLLER_LABEL, PANEL_TITLE, UNPIN_LABEL, pinnedAnnouncement } from './copy'
import { resetDeckMemory } from './deckMemory'

/**
 * The persistent card detail panel.
 *
 * ================= WHAT THIS SUITE CANNOT CARRY, SAID FIRST ============================
 *
 * An undeclared limit reads as coverage, so the four things this file provably cannot say come
 * before anything it can:
 *
 *   **HOVER APPEARANCE.** `fireEvent.mouseEnter` DISPATCHES the event and jsdom evaluates no CSS
 *   at all, so what a hover WIRES is provable here and what it LOOKS like is not. The pinned
 *   ring, the live ring, the overlay surface and the clamp on the oracle block are all source
 *   claims (`tests/token-usage.test.ts`, `tests/shell.test.ts`) plus **the eye-check**.
 *
 *   **THE REDUCED-MOTION MEDIA QUERY.** jsdom does not evaluate media queries into computed
 *   style, so a test that mounted this panel and read a duration would report the UNREDUCED
 *   value and pass for the wrong reason. What ships is stronger than a fallback and
 *   is asserted as source: there is no `transition` and no `animation` in either of this
 *   component's stylesheets, at any setting.
 *
 *   **THE ACCESSIBLE NAME AS A SCREEN READER PHRASES IT.** `dom-accessibility-api` computes a
 *   name; a real reader announces one, with its own pauses and its own handling of an em dash.
 *   The exact strings are pinned here and against the artefact in
 *   `tests/pin-announcement-copy.test.ts`; how they SOUND is the manual-testing checklist's.
 *
 *   **THE `size=large` CACHE RACE.** jsdom loads no images, fires no `load`/`error` and reports
 *   `naturalWidth: 0` always, so `useCardArt`'s settle is inert in both directions here. What
 *   this file proves is that it does not fire WRONGLY; that it fires rightly — and that the
 *   detail render is COLD on first inspection even when the grid is warm, because `?size=large`
 *   is a different cache key — is the eye-check's, against a real browser.
 *
 * ================= HOW HYDRATION IS DRIVEN, AND WHY ====================================
 *
 * `fetch` is stubbed to a promise that never settles. That is not a way of avoiding the network,
 * it is the state most of these assertions are ABOUT: a read in flight, with the summary tier
 * already on screen behind it. Tests that need the hydrated tier seed a
 * `'hydrated'` entry directly, which `hydrateCard` returns from without issuing anything.
 */

const ATRAXA = 'id-Atraxa'
const PATHWAY = 'id-Pathway'

const summary = (id: string, over: Partial<CardSummary> = {}): CardSummary => ({
  id,
  name: 'Atraxa, Praetors’ Voice',
  mana_cost: '{2}{W}{U}{B}{G}',
  cmc: 6,
  type_line: 'Legendary Creature — Phyrexian Angel Horror',
  oracle_text: 'Flying, vigilance, deathtouch, lifelink',
  colors: ['W', 'U', 'B', 'G'],
  rarity: 'mythic',
  set_code: 'cmr',
  set_name: 'Test Set',
  collector_number: '1',
  oracle_id: 'oracle-1',
  color_identity: [],
  legalities: {},
  games: [],
  ...over,
})

const row = (id: string, over: Partial<CardSummary> = {}): DeckCardSummary => ({
  card_id: id,
  quantity: 1,
  sideboard: false,
  commander: false,
  card: summary(id, over),
})

/** A hydrated record, with the fields `fromCard` reads and nothing invented beyond them. */
const record = (id: string, over: Partial<Card> = {}): Card => ({
  ...summary(id),
  oracle_id: `oracle-${id}`,
  set_name: 'Test Set',
  collector_number: '1',
  color_identity: ['W', 'U', 'B', 'G'],
  legalities: {},
  games: ['paper'],
  ...over,
})

const seedSummary = (id: string, over: Partial<CardSummary> = {}) => {
  useCardStore.setState((state) => ({
    cards: { ...state.cards, [id]: { status: 'summary', summary: summary(id, over) } },
  }))
}

const seedHydrated = (id: string, card: Card) => {
  useCardStore.setState((state) => ({
    cards: { ...state.cards, [id]: { status: 'hydrated', card } },
  }))
}

const oneCardDeck = boardsOf([row(ATRAXA)])

beforeEach(() => {
  resetInspection()
  resetDeckMemory()
  resetCardCache()
  // A read that never settles: the `'loading'` tier, which is the state most assertions here
  // are about. `hydrateCard` never rejects, so nothing here needs a catch.
  vi.stubGlobal(
    'fetch',
    vi.fn(() => new Promise(() => {})),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the panel is always there, and it is a region', () => {
  it('renders through Panel at overlay level, named "Card detail" (UX-DR44)', () => {
    seedSummary(ATRAXA)
    const { container } = render(<CardDetail boards={oneCardDeck} />)

    // BY ROLE AND ACCESSIBLE NAME, because that is what the panel IS to a screen reader. The
    // `<section aria-label>` and the `<h2>` both come from the `Panel` primitive with no ARIA
    // written by hand, which is the whole reason it is shaped that way.
    expect(screen.getByRole('region', { name: PANEL_TITLE })).toBeVisible()
    expect(screen.getByRole('heading', { level: 2, name: PANEL_TITLE })).toBeVisible()
    expect(container.querySelector('.panel-overlay')).not.toBeNull()
  })

  it('names the panel, NOT the card — the string the skip link can rely on', () => {
    seedSummary(ATRAXA)
    render(<CardDetail boards={oneCardDeck} />)

    // A heading that changed on every hover would rename a landmark forty times during one sweep
    // of the grid, and the skip link's target would be unpredictable. The card's name is on
    // screen; it is not a heading.
    expect(PANEL_TITLE).toBe('Card detail')
    expect(screen.queryByRole('heading', { name: /Atraxa/ })).toBeNull()
    expect(screen.getByText(/Atraxa/)).toBeVisible()
  })

  it('is NOT a live region — asserted so it cannot come back', () => {
    seedSummary(ATRAXA)
    const { container } = render(<CardDetail boards={oneCardDeck} />)
    const region = screen.getByRole('region', { name: PANEL_TITLE })

    // THE DEFECT THIS CLOSES: with `aria-live` on this panel, sweeping
    // a cursor across a 60-card grid fires one polite announcement per card and floods the
    // queue. Asserted on the panel AND on everything inside it, because a live region nested
    // anywhere in here would have the identical effect.
    expect(region.getAttribute('aria-live')).toBeNull()
    expect(region.getAttribute('role')).toBeNull()
    expect(region.querySelectorAll('[aria-live]')).toHaveLength(0)
    // …while the app DOES have exactly one polite region, and it is outside the panel.
    const live = container.querySelectorAll('[aria-live]')
    expect(live).toHaveLength(1)
    expect(region.contains(live[0])).toBe(false)
  })

  it('is not a modal: no trap, no aria-modal, no dialog role (UX-DR38)', () => {
    seedSummary(ATRAXA)
    const { container } = render(<CardDetail boards={oneCardDeck} />)

    // "It neither stacks nor traps" — it is a column that is always there. Asserted rather than
    // described, because "persistent panel" and "modal" are one careless prop apart.
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(container.querySelector('[aria-modal]')).toBeNull()

    // ==== SCOPED, NOT DELETED ==========================================================
    // A bare `container.querySelector('[tabindex]')` sweep would fail, because
    // `.card-detail-oracle` carries `tabindex="0"` under WCAG 2.1.1. What this line protects is
    // the NOT-A-MODAL claim, and a modal is made of a focus TRAP — the `[tabindex]` sweep is only
    // a cheap proxy for one. Deleting it would drop the claim; leaving it unscoped would forbid
    // the scroller. So it is scoped to "no `[tabindex]` OUTSIDE the oracle scroller", and the two
    // attributes that would actually make this a modal keep their own unconditional assertions
    // above.
    //
    // The exception is named by SELECTOR rather than counted, so a second focusable element
    // smuggled into the panel fails this even though the count would still be one.
    const tabbables = [...container.querySelectorAll('[tabindex]')]
    expect(tabbables.map((el) => el.className)).toEqual(['card-detail-oracle'])

    // …and the scroller is a GROUP, never a landmark or a dialog: `role="region"` here would put
    // a per-card entry in the landmark list and move the count `AppShell.test.tsx` pins.
    expect(tabbables[0].getAttribute('role')).toBe('group')
    expect(tabbables[0].getAttribute('tabindex')).toBe('0')
    expect(tabbables[0].getAttribute('aria-label')).toBe(ORACLE_SCROLLER_LABEL)

    // THE NON-VACUITY ANCHOR. This fixture must actually RENDER oracle text — a card with none
    // renders no scroller at all, under which every assertion above would be checking an empty
    // list and passing by looking at nothing. That is the "vacuous fixture" shape.
    expect(tabbables).toHaveLength(1)
    // TRIMMED, so a fixture whose oracle text degraded to whitespace cannot satisfy "actually
    // renders oracle text".
    expect(tabbables[0].textContent?.trim()).not.toBe('')
  })
})

describe('the cold-open target, with no interaction at all', () => {
  it('targets the first card the GRID draws, and the two agree', () => {
    // THE CROSS-CHECK THAT MAKES `coldOpenTargetOf` A SECOND WRITING RATHER THAN A SECOND RULE
    // (AD-12). `CardGrid`'s flattening expression is repeated in the slice; what keeps the two
    // from drifting is this — render the
    // grid over the same boards and compare against the id of the tile it actually produced.
    const boards = boardsOf([
      row('id-Forest', { name: 'Forest', type_line: 'Basic Land — Forest' }),
      row('id-Llanowar', { name: 'Llanowar Elves', type_line: 'Creature — Elf Druid' }),
      { ...row(ATRAXA), commander: true },
    ])
    seedSummary(ATRAXA)

    const grid = render(<CardGrid boards={boards} />)
    const firstTileImage = grid.container.querySelector('img')!
    render(<CardDetail boards={boards} />)

    expect(useInspectionStore.getState().defaultId).toBe(ATRAXA)
    // The commander is the first thing the grid draws — the literal reading of UX-DR20 ("the
    // first card of the first type group") and the on-screen reading differ for the 16 of 40
    // real decks that have one, and the panel follows the eye.
    expect(firstTileImage.getAttribute('src')).toBe(`/api/card-image/${ATRAXA}`)
    // Scoped to the panel, because the grid is on screen too and is showing the same card's name
    // in its caption — which is the point of the cross-check rather than an inconvenience.
    const panel = screen.getByRole('region', { name: PANEL_TITLE })
    expect(within(panel).getByText('Atraxa, Praetors’ Voice')).toBeVisible()
  })

  it('survives a deck with nothing in either board — no crash, no stray card', () => {
    // `boardsOf([])` is three empty boards, which is a real state: the empty-deck COPY is owned
    // elsewhere, and what this panel owes is a resolution that is total and a panel that is
    // still there.
    const { container } = render(<CardDetail boards={boardsOf([])} />)

    expect(screen.getByRole('region', { name: PANEL_TITLE })).toBeVisible()
    expect(useInspectionStore.getState().defaultId).toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('.card-detail-name')).toBeNull()
    expect(container.querySelector('.card-placeholder')).toBeNull()
  })
})

describe('what the panel draws, and when', () => {
  it('renders name, cost, type line and oracle text from the SUMMARY tier, with no spinner', () => {
    seedSummary(ATRAXA)
    const { container } = render(<CardDetail boards={oneCardDeck} />)

    // Everything the panel draws is already in hand at the moment of hover, because
    // `CardSummary` carries all four text fields and `seedDeckCards` put them there for
    // free. The hydration request below is still in flight and nothing is waiting for it.
    expect(screen.getByText('Atraxa, Praetors’ Voice')).toBeVisible()
    expect(screen.getByText(/Legendary Creature/)).toBeVisible()
    expect(screen.getByText(/Flying, vigilance/)).toBeVisible()
    // The cost is PIPS, through the shared primitive, so it is announced once from its own
    // `role="img"` name rather than as five stray characters.
    expect(screen.getByRole('img', { name: /2 generic/ })).toBeVisible()

    // NO SPINNER ANYWHERE (UX-DR36). Not a role, not a class, not a word.
    expect(screen.queryByRole('progressbar')).toBeNull()
    expect(screen.queryByRole('status')).toBeNull()
    expect(container.querySelector('[class*="spinner"]')).toBeNull()
    expect(container.textContent).not.toMatch(/loading/i)
  })

  it('asks for the card face at size=large, through the one builder (AD-11)', () => {
    seedSummary(ATRAXA)
    const { container } = render(<CardDetail boards={oneCardDeck} />)
    const img = container.querySelector('img')!

    expect(img.getAttribute('src')).toBe(`/api/card-image/${ATRAXA}?size=large`)
    // Same origin, never the CDN — `tests/no-scryfall-hosts.test.ts` is the static half of this
    // and this is the rendered half.
    expect(img.getAttribute('src')).not.toMatch(/scryfall/i)
    expect(img.getAttribute('src')!.startsWith('/')).toBe(true)
    // `alt=""` — a divergence from UX-DR48's literal words, following its own logic: the
    // name is beneath the art in the same panel, so the image is not the only carrier and the
    // name is announced ONCE.
    expect(img.getAttribute('alt')).toBe('')
    expect([...container.textContent.matchAll(/Atraxa, Praetors’ Voice/g)]).toHaveLength(1)
  })

  it('consumes the shared card shape and re-declares none of it (UX-DR4)', () => {
    seedSummary(ATRAXA)
    const { container } = render(<CardDetail boards={oneCardDeck} />)

    /* The DOM half of the geometry claim and ALL it carries: this box inherits
       `aspect-ratio: 63 / 88` and `border-radius: var(--radius-card)` from the ONE declaration
       in card-geometry.css. That the box is 63:88 ON SCREEN is the eye-check's — jsdom applies
       no CSS.

       A BLOCK COMMENT, DELIBERATELY: CARD_SHAPED's markup half strips block comments only (CSS
       has no line comments, so that is all a STYLESHEET needs) while it also scans `.tsx`, where
       a `//` line comment naming the token fires the guard on prose. Its declared instruction is
       "the repair is to move the prose into a block comment, never to delete the explanation" —
       followed here. */
    const art = container.querySelector('.card-detail-art')!
    expect(art.classList.contains('card-shape')).toBe(true)
  })

  it('renders the FRONT FACE once hydration lands — the 100%-blank population', () => {
    // THE MEASUREMENT THIS WHOLE PANEL TURNS ON. All 3,225 corpus cards carrying `card_faces`
    // have a BLANK top-level `oracle_text` and 2,274 carry the degenerate `Card // Card` type
    // line, so for that population the face is the ONLY source of a type line and rules text.
    // Six of the 99 cards in the largest real deck are in it — the MDFC Pathways, whose shape
    // this fixture reproduces exactly.
    seedHydrated(
      PATHWAY,
      record(PATHWAY, {
        name: 'Clearwater Pathway // Murkwater Pathway',
        mana_cost: '',
        type_line: 'Land // Land',
        oracle_text: '',
        card_faces: [
          {
            name: 'Clearwater Pathway',
            mana_cost: '',
            type_line: 'Land',
            oracle_text: 'Tap: Add U.',
          },
          {
            name: 'Murkwater Pathway',
            mana_cost: '',
            type_line: 'Land',
            oracle_text: 'Tap: Add B.',
          },
        ],
      }),
    )
    render(<CardDetail boards={boardsOf([row(PATHWAY)])} />)

    expect(screen.getByText('Clearwater Pathway')).toBeVisible()
    expect(screen.getByText('Tap: Add U.')).toBeVisible()
    // The FRONT face, not the back — a panel that read `card_faces.at(-1)` would look correct on
    // a two-faced fixture and be wrong on every one of them.
    expect(screen.queryByText('Tap: Add B.')).toBeNull()
    // …and not the combined top-level values, which are the ones that are blank or degenerate.
    expect(screen.queryByText('Land // Land')).toBeNull()
    expect(screen.queryByText('Clearwater Pathway // Murkwater Pathway')).toBeNull()
  })

  it('falls back to the top-level record per FIELD, not per record', () => {
    // A single-faced card is the other 92% of the corpus, and for it hydration adds nothing
    // DRAWABLE — which is the reason the fallback matters. A face that
    // carried a name but no type line is expressible on this wire (every field is optional AND
    // nullable), so the fallback is per field.
    seedHydrated(
      ATRAXA,
      record(ATRAXA, {
        card_faces: [{ name: 'A Face With Only A Name' }],
      }),
    )
    render(<CardDetail boards={oneCardDeck} />)

    expect(screen.getByText('A Face With Only A Name')).toBeVisible()
    expect(screen.getByText(/Legendary Creature/)).toBeVisible()
    expect(screen.getByText(/Flying, vigilance/)).toBeVisible()
  })

  it('does not blank what it was already showing while a read is in flight', () => {
    seedSummary(ATRAXA)
    render(<CardDetail boards={oneCardDeck} />)

    // `hydrateCard` writes a `'loading'` entry that CARRIES the summary it had before, so the
    // free tier survives the request. This is the assertion behind "the rest fills in place":
    // there is no frame in which the panel is empty.
    expect(useCardStore.getState().cards[ATRAXA]?.status).toBe('loading')
    expect(screen.getByText('Atraxa, Praetors’ Voice')).toBeVisible()
    expect(screen.getByText(/Flying, vigilance/)).toBeVisible()
  })

  it('renders NO price — satisfied by absence, at the type', () => {
    seedHydrated(ATRAXA, record(ATRAXA))
    const { container } = render(<CardDetail boards={oneCardDeck} />)

    // `types.d.ts:325`: "There is no price data of any kind in this record." The endpoint ships
    // NO price field rather than a permanently-null one, so the requirement is satisfied by
    // absence — and an absence can only be asserted at the type. The day someone
    // adds a `prices` field to the wire, this line stops compiling and the decision gets made
    // again rather than sliding in.
    type PriceKeys = Extract<keyof Card, 'prices' | 'price'>
    const declaresNoPrice: [PriceKeys] extends [never] ? true : never = true
    expect(declaresNoPrice).toBe(true)
    // …and nothing draws an empty slot for one, which is the rendered half of the same claim.
    expect(container.textContent).not.toMatch(/\$|price/i)
  })
})

describe('a card with no picture, and a card the app does not know', () => {
  it('draws the NAMED placeholder when the art fails — never a broken-image glyph', () => {
    seedSummary(ATRAXA)
    const { container } = render(<CardDetail boards={oneCardDeck} />)
    act(() => {
      container.querySelector('img')!.dispatchEvent(new Event('error'))
    })

    // The same 79-card population as the grid — measured, `large` and `normal` are missing for
    // exactly the same set, so no new no-image population appears at this size. The
    // `<img>` is REMOVED rather than hidden: an element with a failed `src` still draws the
    // browser's own glyph, which is the one thing AD-11 promises never happens.
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('.card-placeholder')).not.toBeNull()
    expect(screen.queryByText(UNKNOWN_CARD_LABEL)).toBeNull()
    // The NAMED variant: the app knows exactly what this card is and only lacks its picture.
    expect(screen.getAllByText('Atraxa, Praetors’ Voice').length).toBeGreaterThan(0)
  })

  it('never puts a state panel on the glass for a card refusal (FR-13)', () => {
    // `panelFor()` is not called on the card path, because `card_not_found` maps to
    // `null` there and `panelFor` clamps `null` to `internal-error` — which would replace a
    // working deck view with "The companion hit a bug" because ONE card was missing.
    useCardStore.setState((state) => ({
      cards: {
        ...state.cards,
        [ATRAXA]: {
          status: 'unknown',
          reason: 'card_not_found',
          placeholder: 'unknown-card',
          summary: null,
          retryable: false,
        },
      },
    }))
    render(<CardDetail boards={oneCardDeck} />)

    expect(screen.queryByText(/companion hit a bug/i)).toBeNull()
    expect(screen.queryByRole('region', { name: /companion/i })).toBeNull()
    // The panel is still the panel, and it draws the unknown placeholder inside itself.
    expect(screen.getByRole('region', { name: PANEL_TITLE })).toBeVisible()
    expect(screen.getByText(UNKNOWN_CARD_LABEL)).toBeVisible()
  })

  it('refuses to make an unknown card the inspection target at all (UX-DR22)', () => {
    seedSummary(ATRAXA)
    useCardStore.setState((state) => ({
      cards: {
        ...state.cards,
        'id-ghost': {
          status: 'unknown',
          reason: 'card_not_found',
          placeholder: 'unknown-card',
          summary: null,
          retryable: false,
        },
      },
    }))
    render(<CardDetail boards={oneCardDeck} />)

    // `EXPERIENCE.md:99`: the unknown-card variant "cannot be inspected — there is nothing to
    // show". Both verbs refuse, so a hover and a click are the same answer, and the panel keeps
    // showing the card it was showing.
    act(() => setHovered('id-ghost'))
    act(() => togglePin('id-ghost'))
    expect(screen.getByText('Atraxa, Praetors’ Voice')).toBeVisible()
    expect(screen.queryByText(UNKNOWN_CARD_LABEL)).toBeNull()
  })
})

describe('pin, release, and the one announcement', () => {
  it('carries the pinned ring only while pinned, and offers the unpin control with it', () => {
    seedSummary(ATRAXA)
    const { container } = render(<CardDetail boards={oneCardDeck} />)
    const frame = container.querySelector('.card-detail')!

    // A CLASS, not a computed style — jsdom applies none. The ring itself is
    // `--shadow-pinned-ring` in CardDetailChrome.css and `tests/tokens.test.ts` holds its VALUE
    // to DESIGN.md; that it is VISIBLE is the eye-check's.
    expect(frame.classList.contains('is-pinned')).toBe(false)
    expect(screen.queryByRole('button', { name: UNPIN_LABEL })).toBeNull()

    act(() => togglePin(ATRAXA))
    expect(frame.classList.contains('is-pinned')).toBe(true)

    // A REAL `<button>` (UX-DR47, unconditional), with a real word rather than an invented glyph
    // — see copy.ts. Its hit box and its focus ring are source claims in CardDetailChrome.css.
    const unpin = screen.getByRole('button', { name: UNPIN_LABEL })
    expect(unpin.tagName).toBe('BUTTON')
    expect(unpin.getAttribute('type')).toBe('button')
    // In the panel's own header, which is the Tab stop UX-DR40's enumerated order does not
    // contain — written down here and in the module header.
    expect(unpin.closest('.panel-header')).not.toBeNull()
  })

  it('releases on the unpin control, and hover resumes control', () => {
    seedSummary(ATRAXA)
    seedSummary('id-Other', { name: 'Some Other Card' })
    const { container } = render(<CardDetail boards={oneCardDeck} />)

    act(() => togglePin(ATRAXA))
    act(() => setHovered('id-Other'))
    // Hover no longer overrides a pin — the whole point of pinning.
    expect(screen.getByText('Atraxa, Praetors’ Voice')).toBeVisible()

    act(() => screen.getByRole('button', { name: UNPIN_LABEL }).click())
    expect(container.querySelector('.card-detail')!.classList.contains('is-pinned')).toBe(false)
    // …and control goes back to where the cursor actually is, not to the cold-open card.
    expect(screen.getByText('Some Other Card')).toBeVisible()
  })

  it('releases on Esc, from anywhere on the document (UX-DR39)', () => {
    seedSummary(ATRAXA)
    render(<CardDetail boards={oneCardDeck} />)
    act(() => togglePin(ATRAXA))
    expect(useInspectionStore.getState().pinnedId).toBe(ATRAXA)

    // ON `document`, because the pin can be set from a tile in the OTHER column — a listener on
    // this panel would only work while focus happened to be inside it.
    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    })
    expect(useInspectionStore.getState().pinnedId).toBeNull()

    // THE HALF THIS SUITE DOES NOT TEST. UX-DR39 layers Esc — an open agent view closes first,
    // then a pin — and the layering is covered deliberately NOT here: `AgentView.test.tsx` owns
    // the phase mechanism and `App.test.tsx` owns the end-to-end keystroke, because both need
    // the overlay mounted and this file renders `CardDetail` alone. What this suite proves is
    // its own half — the bubble listener releases the pin when nothing is above it.
  })

  it('lets the pin outlive the panel, and stops listening when it does', () => {
    seedSummary(ATRAXA)
    const panel = render(<CardDetail boards={oneCardDeck} />)
    act(() => togglePin(ATRAXA))
    panel.unmount()

    // TWO CLAIMS, AND THEY ARE THE SAME UNMOUNT SEEN FROM BOTH SIDES.
    //
    // The pin SURVIVES, which is `EXPERIENCE.md:90` — "the pinned target survives closing the
    // view" — and the whole reason the slice is a module-scope store rather than state inside
    // this component or a context under the left column. The agent view mounts and unmounts
    // over this panel; a pin set inside it has to still be here afterwards.
    expect(useInspectionStore.getState().pinnedId).toBe(ATRAXA)

    // The LISTENER does not, because it is on `document` rather than on this subtree. One that
    // outlived its panel would release a pin for a component that is no longer on screen —
    // invisible today, and exactly the kind of thing the agent view would inherit as a mystery.
    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    })
    expect(useInspectionStore.getState().pinnedId).toBe(ATRAXA)
    clearPin()
  })

  it('announces a pin EXACTLY once, in the separate polite region (UX-DR45)', () => {
    seedSummary(ATRAXA)
    const { container } = render(<CardDetail boards={oneCardDeck} />)
    const region = container.querySelector('[aria-live]')!

    // Silent at rest. A live region with content on mount would announce on every page load.
    expect(region.getAttribute('aria-live')).toBe('polite')
    expect(region.textContent).toBe('')

    act(() => togglePin(ATRAXA))
    expect(region.textContent).toBe('Pinned — Atraxa, Praetors’ Voice')
    expect(region.textContent).toBe(pinnedAnnouncement('Atraxa, Praetors’ Voice'))

    // EXACTLY ONCE, AND THIS IS THE ASSERTION THAT MAKES IT SO. A faced card's name resolves
    // from `card_faces` when hydration lands, so an announcement recomputed from the rendered
    // name would change — and change is what `aria-live` speaks. The effect is keyed on the
    // pinned ID alone and reads the name imperatively at pin time, so a later hydration is
    // silent.
    act(() => seedHydrated(ATRAXA, record(ATRAXA, { card_faces: [{ name: 'A Different Face' }] })))
    expect(screen.getByText('A Different Face')).toBeVisible()
    expect(region.textContent).toBe('Pinned — Atraxa, Praetors’ Voice')
  })

  it('says nothing on a TRANSIENT change, however many there are', () => {
    seedSummary(ATRAXA)
    seedSummary('id-Other', { name: 'Some Other Card' })
    const { container } = render(<CardDetail boards={oneCardDeck} />)
    const region = container.querySelector('[aria-live]')!

    // The flood the not-a-live-region rule closes: one announcement per hovered card across a
    // 60-card grid. Five
    // hovers here, and the region never acquires a character.
    for (const id of [ATRAXA, 'id-Other', ATRAXA, 'id-Other', ATRAXA]) {
      act(() => setHovered(id))
      expect(region.textContent).toBe('')
    }
  })

  it('moves focus to the panel title when unpin is activated', () => {
    seedSummary(ATRAXA)
    render(<CardDetail boards={oneCardDeck} />)
    act(() => togglePin(ATRAXA))

    // Activating unpin UNMOUNTS the activated element, and a removed activeElement drops
    // keyboard focus to <body> — Tab would restart from the top of the page. The hand-off
    // target is the panel's <h2>: the one element the skip link aims at too, so both converge
    // on a single focus home.
    const unpin = screen.getByRole('button', { name: UNPIN_LABEL })
    act(() => {
      unpin.focus()
      unpin.click()
    })
    const title = screen.getByRole('heading', { name: PANEL_TITLE })
    expect(document.activeElement).toBe(title)

    // The panel AT REST carries no `[tabindex]` here (the not-a-modal claim): the attribute is
    // imperative, and it leaves with the focus.
    act(() => title.blur())
    expect(title.hasAttribute('tabindex')).toBe(false)
  })

  it('announces LATE, and still exactly once, when the pin precedes the name', () => {
    // The slice deliberately does not refuse an id the cache has never seen — the agent view's
    // thumbnails are that population. A capture keyed on the id alone would speak `''` and stay
    // silent forever: "exactly once" silently becoming ZERO is the defect; one late capture,
    // settling the first time a name exists, is the repair.
    render(<CardDetail boards={oneCardDeck} />)
    const region = document.querySelector('[aria-live]')!

    act(() => togglePin('id-late'))
    expect(region.textContent).toBe('')

    act(() => seedSummary('id-late', { name: 'A Late Arrival' }))
    expect(region.textContent).toBe(pinnedAnnouncement('A Late Arrival'))

    // …and the late capture is still ONE capture: a subsequent hydration that renames the card
    // does not re-announce, exactly as it does not for a pin that captured on time.
    act(() =>
      seedHydrated('id-late', record('id-late', { card_faces: [{ name: 'A Renamed Face' }] })),
    )
    expect(region.textContent).toBe(pinnedAnnouncement('A Late Arrival'))
  })

  it('empties the region on release — a removal is not a message', () => {
    seedSummary(ATRAXA)
    const { container } = render(<CardDetail boards={oneCardDeck} />)
    const region = container.querySelector('[aria-live]')!

    act(() => togglePin(ATRAXA))
    expect(region.textContent).not.toBe('')
    // A SECOND SINGLE CLICK of the same card, never a double-click (UX-DR39, banned outright).
    act(() => togglePin(ATRAXA))
    expect(region.textContent).toBe('')
  })
})

describe('the deck transition is where an inspection dies', () => {
  it('clears a pin and a stale hover when the deck is REPLACED', () => {
    // FR-22 deck loads are live: the agent calls `load_deck` and the glass follows with no
    // refresh. Without this clearing, a pin from deck A outranks deck B's cold-open target
    // forever — the panel renders a card that is not on the glass, the live ring matches no
    // tile, and only a manual Esc recovers. The stale-HOVER twin is the same defect without
    // even a control to notice it by: a hovered tile unmounted by the reload fires no
    // `mouseleave`, so `hoveredId` would keep pointing at the removed card.
    //
    // NON-VACUOUS UNDER THE MEMBERSHIP RULE: eviction is a membership transition rather than a
    // reference comparison, and ATRAXA genuinely satisfies it — in the departing deck's list,
    // absent from deck B's. The transients' clear on replacement is unconditional.
    seedSummary(ATRAXA)
    seedSummary('id-Elves', { name: 'Llanowar Elves', type_line: 'Creature — Elf Druid' })
    const view = render(<CardDetail boards={oneCardDeck} />)
    act(() => togglePin(ATRAXA))
    act(() => setHovered(ATRAXA))
    act(() => setFocused(ATRAXA))

    const deckB = boardsOf([row('id-Elves', { name: 'Llanowar Elves' })])
    view.rerender(<CardDetail boards={deckB} />)

    expect(useInspectionStore.getState().pinnedId).toBeNull()
    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(useInspectionStore.getState().focusedId).toBeNull()
    // …and the panel falls to the NEW deck's cold-open target, not to a ghost of the old one.
    expect(screen.getByText('Llanowar Elves')).toBeVisible()
    expect(screen.queryByText('Atraxa, Praetors’ Voice')).toBeNull()
  })

  it('does NOT clear across a remount of the SAME deck — the pin still outlives the panel', () => {
    // The other half, and the reason the deck memory is module-scope rather than a ref: the
    // panel unmounts on every surface flip (a backend hiccup puts a state panel on the glass),
    // and FR-17's pin must survive the round trip. `rememberBoards` keys the TRANSITION on the
    // `boards` reference, which `deck.ts` derives once per deck write — a remount of the same
    // reference returns no departing boards, so nothing clears. This is also the non-vacuity
    // twin of the eviction test above: it is what proves the clear there fired for the
    // membership transition and not for the mere act of re-rendering.
    seedSummary(ATRAXA)
    const first = render(<CardDetail boards={oneCardDeck} />)
    act(() => togglePin(ATRAXA))
    first.unmount()

    render(<CardDetail boards={oneCardDeck} />)
    expect(useInspectionStore.getState().pinnedId).toBe(ATRAXA)
    expect(screen.getByText('Atraxa, Praetors’ Voice')).toBeVisible()
  })

  it('keeps a pin across a SAME-DECK refetch — new boards reference, card in both lists', () => {
    // THE MEMBERSHIP RULE AT ITS SEAM. Every agent-edit settle mints a new `boards` reference,
    // and a reference-comparison eviction would release the pin on each one.
    // Under the membership rule the pinned card is in BOTH lists, so the pin survives; the
    // TRANSIENTS still die (ephemeral by contract, stale by construction on any replacement).
    seedSummary(ATRAXA)
    seedSummary('id-Elves', { name: 'Llanowar Elves', type_line: 'Creature — Elf Druid' })
    const view = render(<CardDetail boards={oneCardDeck} />)
    act(() => togglePin(ATRAXA))
    act(() => setHovered(ATRAXA))

    // The refetched deck: a NEW derivation (new reference) that still contains the pinned card.
    const refetched = boardsOf([row(ATRAXA), row('id-Elves', { name: 'Llanowar Elves' })])
    view.rerender(<CardDetail boards={refetched} />)

    expect(useInspectionStore.getState().pinnedId).toBe(ATRAXA)
    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(screen.getByText('Atraxa, Praetors’ Voice')).toBeVisible()
  })
})

describe('the panel updates in place on hover AND on focus (UX-DR14)', () => {
  it('follows the target wherever it comes from, with no remount', () => {
    seedSummary(ATRAXA)
    seedSummary('id-Other', { name: 'Some Other Card' })
    const { container } = render(<CardDetail boards={oneCardDeck} />)

    // NODE IDENTITY, captured before the change. "Updates in place" is a claim about the same
    // panel showing a different card — a component that tore itself down and remounted would
    // satisfy a text assertion and fail this one, and it is the difference between a continuous
    // motion and a flicker.
    const region = screen.getByRole('region', { name: PANEL_TITLE })
    const live = container.querySelector('[aria-live]')!

    act(() => setHovered('id-Other'))
    expect(within(region).getByText('Some Other Card')).toBeVisible()
    expect(screen.getByRole('region', { name: PANEL_TITLE })).toBe(region)
    expect(container.querySelector('[aria-live]')).toBe(live)

    // The slice is location-agnostic: a deck row and an agent-view thumbnail arrive
    // through the same verbs. Keyboard focus arrives through ITS OWN verb and slot,
    // and the panel answers it identically — `CardTile.test.tsx` proves the
    // tile's handlers reach both; this proves the panel follows both.
    act(() => setFocused(ATRAXA))
    expect(within(region).getByText('Atraxa, Praetors’ Voice')).toBeVisible()
  })
})

/**
 * The panel follows the FACE.
 *
 * ================= WHAT THESE CANNOT CARRY ============================================
 *
 * The panel's copy of the control is asserted here as an element, a name and a place in the DOM.
 * Its 28px disc, its 32px hit box, its 0.65 → 1.0 opacity and the 3D rotation of the art behind
 * it are all unevaluated in jsdom — source claims in `FlipControl.css` and `tokens.css`, checked
 * by eye. That `?size=large&face=1` is a fourth distinct browser-cache key is likewise
 * a browser fact: jsdom loads no images at all.
 */
describe('the panel follows the flipped face', () => {
  /** A flippable printing, hydrated: two faces, each carrying its own images (shape C). */
  const PATHWAY = 'id-Clearwater'
  const pathwayCard = (): Card => ({
    ...record(PATHWAY, {
      name: 'Clearwater Pathway // Murkwater Pathway',
      type_line: 'Land // Land',
      oracle_text: '',
      mana_cost: '',
      image_uris: null,
      card_faces: [
        {
          name: 'Clearwater Pathway',
          mana_cost: '{U}',
          type_line: 'Land',
          oracle_text: '{T}: Add {U}.',
          image_uris: { normal: 'n', large: 'l' },
        },
        {
          name: 'Murkwater Pathway',
          mana_cost: '{B}',
          type_line: 'Land — Swamp',
          oracle_text: '{T}: Add {B}.',
          image_uris: { normal: 'n', large: 'l' },
        },
      ],
    }),
  })

  const pathwayDeck = boardsOf([row(PATHWAY, { name: 'Clearwater Pathway // Murkwater Pathway' })])

  afterEach(resetFaces)

  it('carries its OWN copy of the control, pinned inside the art box', () => {
    seedHydrated(PATHWAY, pathwayCard())
    const { container } = render(<CardDetail boards={pathwayDeck} />)

    const control = screen.getByRole('button', { name: FLIP_LABEL })
    expect(control).toBeVisible()
    // "pinned to its art's top-left" — asserted as CONTAINMENT, which is what makes the CSS
    // `top: var(--space-2); left: var(--space-2)` mean the ART BOX's corner rather than the
    // panel's. The same component the tile mounts, not a second implementation (UX-DR15).
    expect(container.querySelector('.card-detail-art')!.contains(control)).toBe(true)
    expect(control.classList.contains('flip-control')).toBe(true)
  })

  it('renders NO control for a single-faced card, in the panel as in the grid', () => {
    seedHydrated(ATRAXA, record(ATRAXA))
    render(<CardDetail boards={oneCardDeck} />)
    expect(screen.queryByRole('button', { name: FLIP_LABEL })).toBeNull()
  })

  it('renders the BACK face in all four fields once flipped', () => {
    seedHydrated(PATHWAY, pathwayCard())
    const { container } = render(<CardDetail boards={pathwayDeck} />)

    // The front face first — `fromCard` reads `card_faces[0]`, never the top-level `Land // Land`.
    expect(screen.getByText('Clearwater Pathway')).toBeVisible()
    expect(screen.getByText('Land')).toBeVisible()
    expect(screen.getByText('{T}: Add {U}.')).toBeVisible()

    // A flip made through the STORE, which is how a click on the tile in the OTHER COLUMN reaches
    // this panel: one answer, two readers. The panel's own control is exercised below.
    act(() => flipCard(PATHWAY, 2))

    expect(screen.getByText('Murkwater Pathway')).toBeVisible()
    expect(screen.getByText('Land — Swamp')).toBeVisible()
    expect(screen.getByText('{T}: Add {B}.')).toBeVisible()
    expect(screen.queryByText('Clearwater Pathway')).toBeNull()
    // …and the mana cost, which is the fourth field and the one that renders as PIPS rather than
    // as text: the front face is `{U}` and the back is `{B}`, so the blue pip must be gone.
    expect(container.querySelectorAll('.mana-pip-b')).toHaveLength(1)
    expect(container.querySelectorAll('.mana-pip-u')).toHaveLength(0)
  })

  it('asks the image route for the SAME face the text came from', () => {
    seedHydrated(PATHWAY, pathwayCard())
    const { container } = render(<CardDetail boards={pathwayDeck} />)
    const srcOf = (selector: string) => container.querySelector(selector)!.getAttribute('src')

    // FRONT: `size=large` and NO `face=`, so the panel's front render is the plain `size=large`
    // cache key and the warm cache is not split.
    expect(srcOf('.is-front')).toBe(`/api/card-image/${PATHWAY}?size=large`)
    // BACK: both parameters, in a stable order — a second ordering would be a second cache key for
    // one picture, which is the whole reason the builder composes them as a list.
    expect(srcOf('.is-back')).toBe(`/api/card-image/${PATHWAY}?size=large&face=1`)

    act(() => flipCard(PATHWAY, 2))
    expect(container.querySelector('.card-faces')!.getAttribute('data-flipped')).toBe('true')
  })

  it('keeps the per-field fallback, for the ten flippable cards with a null type line', () => {
    // MEASURED: ten cards that DO get a flip control have a face with a null `type_line` — the
    // Un-set "(cont'd)" minigame cards. `fromCard`'s `??` is PER FIELD, so such a face keeps its
    // own name and rules text while the type line falls through to the top-level value. A
    // per-record choice would blank the type line the moment the card was flipped.
    const card = pathwayCard()
    seedHydrated(PATHWAY, {
      ...card,
      card_faces: [card.card_faces![0], { ...card.card_faces![1], type_line: null }],
    })
    render(<CardDetail boards={pathwayDeck} />)

    act(() => flipCard(PATHWAY, 2))
    expect(screen.getByText('Murkwater Pathway')).toBeVisible()
    expect(screen.getByText('{T}: Add {B}.')).toBeVisible()
    expect(screen.getByText('Land // Land')).toBeVisible()
  })

  it('flips from the PANEL’s control without pinning, setting or clearing anything', () => {
    seedHydrated(PATHWAY, pathwayCard())
    render(<CardDetail boards={pathwayDeck} />)
    const before = useInspectionStore.getState()

    fireEvent.click(screen.getByRole('button', { name: FLIP_LABEL }))

    // Against the SLICE's whole state: the panel's own control is inside a clickable-looking box
    // and must still touch none of the inspection verbs: a flip is not an inspection.
    expect(useInspectionStore.getState()).toEqual(before)
    expect(screen.getByText('Murkwater Pathway')).toBeVisible()
  })

  it('keeps the control while the shown face’s art has FAILED', () => {
    // The panel's half of the same decision, and the reason the two art branches share ONE
    // art box: the placeholder replaces the FACES, not the box, so the control survives inside it
    // and a face whose picture failed can always be flipped out of.
    seedHydrated(PATHWAY, pathwayCard())
    const { container } = render(<CardDetail boards={pathwayDeck} />)

    fireEvent.error(container.querySelector('.is-front')!)
    expect(container.querySelector('.card-placeholder')).not.toBeNull()
    expect(screen.getByRole('button', { name: FLIP_LABEL })).toBeVisible()

    fireEvent.click(screen.getByRole('button', { name: FLIP_LABEL }))
    // Flipped to a face whose art has NOT failed: the placeholder is gone and the faces are back.
    expect(container.querySelector('.card-placeholder')).toBeNull()
    expect(container.querySelector('.is-back')).not.toBeNull()
  })
})
