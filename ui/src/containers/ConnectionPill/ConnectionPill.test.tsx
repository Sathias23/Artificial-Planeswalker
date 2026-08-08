/**
 * The connection pill, at component level (story c5-7, AC 2–8, AC 10).
 *
 * WHAT IS HERE AND WHAT IS IN `App.test.tsx`. This file drives the two SLICES directly and asserts
 * what the component makes of them — the dot's class, the words, the deck name, the focusability
 * and the announcement's transition policy. It cannot prove that the pill is on the glass on every
 * SURFACE, or that a real socket drop moves it: both of those are claims about `App`'s composition
 * and c5-6's loop, so they live in `App.test.tsx` with the `FakeSocket` + fake-timer idiom (AC 18).
 *
 * ⚠️ `useDeckStore.setState` rather than a production action, and the reason is worth stating:
 * `applyDeckState` is deliberately NOT exported (`deck.ts:176` — "the ONE writer"), and the only
 * production path to a loaded deck is `createDeckBoot`, which makes two requests. Driving the boot
 * here would test the boot. `store-writes.test.ts` excludes `.test.tsx` files from its writer scan
 * for exactly this case; the SHIPPED component still writes nothing, which is what that guard is
 * about.
 */

import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import type { DeckDetail } from '../../api/schema'
import { INITIAL_DECK_STATE, useDeckStore } from '../../state/deck'
import type { ConnectionStatus } from '../../state/socket'
import { applyConnection, INITIAL_SYSTEM_STATE, useSystemStore } from '../../state/systemState'
import { ConnectionPill } from './ConnectionPill'
import { CONNECTION_WORDS, pillText } from './copy'

const detail = (name: string): DeckDetail => ({
  id: 'a7f3c2d1-0000-4000-8000-000000000001',
  name,
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
})

const loadDeck = (name: string) =>
  useDeckStore.setState({
    deck: {
      status: 'deck',
      detail: detail(name),
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

const pill = () => screen.getByRole('button')
const dot = () => document.querySelector('.connection-pill-dot')
const region = () => document.querySelector('[aria-live]')

beforeEach(() => {
  useSystemStore.setState(INITIAL_SYSTEM_STATE)
  useDeckStore.setState({ deck: INITIAL_DECK_STATE })
})

describe('the dot reports the status, and never carries it alone (AC 2, AC 3, AC 4)', () => {
  it.each([
    ['live', 'is-live'],
    ['reconnecting', 'is-reconnecting'],
    ['down', 'is-down'],
  ] as [ConnectionStatus, string][])('draws the %s dot as %s', (status, className) => {
    applyConnection(status)
    render(<ConnectionPill />)

    expect(dot()?.className).toContain(className)
  })

  it('marks the dot aria-hidden, because the words already name the state', () => {
    // UX-DR29's "the dot never carries it alone" is what MAKES the dot safe to hide: a screen
    // reader that skipped a semantic dot would lose nothing, because the text says the same thing.
    applyConnection('live')
    render(<ConnectionPill />)

    expect(dot()?.getAttribute('aria-hidden')).toBe('true')
  })

  it.each(['live', 'reconnecting', 'down'] as ConnectionStatus[])(
    'names the %s state in WORDS, not in colour alone (AC 4)',
    (status) => {
      applyConnection(status)
      render(<ConnectionPill />)

      expect(pill()).toHaveTextContent(CONNECTION_WORDS[status])
    },
  )

  it('carries the retrying-quietly note in the down state (AC 5)', () => {
    // The last unmirrored clause of `EXPERIENCE.md`'s disconnected row, and it is TRUE rather than
    // reassuring: `RETRIES_QUIETLY.disconnected === true` and c5-6's loop reads that map to decide
    // whether to keep scheduling. `copy-tails.test.ts` is where the two are held together.
    applyConnection('down')
    render(<ConnectionPill />)

    expect(pill()).toHaveTextContent('retrying quietly')
  })
})

describe('the deck name comes from the DECK SLICE (AC 6)', () => {
  it('names the loaded deck beside the state', () => {
    loadDeck('Sultai Midrange')
    applyConnection('live')
    render(<ConnectionPill />)

    expect(pill()).toHaveTextContent('Connected — Sultai Midrange')
  })

  it('names NO deck when none is loaded — no placeholder, no "undefined"', () => {
    applyConnection('live')
    render(<ConnectionPill />)

    expect(pill().textContent).toBe('Connected')
    expect(pill().textContent).not.toContain('undefined')
  })

  it('preserves the deck name’s CASE — it must not ride the micro role (c4-3’s lesson)', () => {
    // The DOM text is what a screen reader and the copy gates read; `text-transform` only changes
    // the render. So the assertion that survives is that the NAME is in the document verbatim,
    // and `ConnectionPill.css` is where the role split that keeps it readable is argued.
    loadDeck('Ghired, Conclave Exile')
    applyConnection('live')
    render(<ConnectionPill />)

    expect(screen.getByText('Ghired, Conclave Exile')).toBeInTheDocument()
  })

  it('still knows a deck is loaded in the DOWN state, and withholds the name anyway (Q3)', () => {
    // THE LANDMINE THIS COMPONENT IS SHAPED AROUND, from the other side. `surfaceOf` returns a
    // PANEL surface whenever `connection === 'down'` while the deck slice underneath still holds
    // the deck — so a pill reading the surface would be indistinguishable from this one here, and
    // would differ everywhere else. What this test pins is the RULING: the name is withheld
    // because the Disconnected panel owns the guidance, not because the pill cannot see it.
    loadDeck('Sultai Midrange')
    applyConnection('down')
    render(<ConnectionPill />)

    expect(pill().textContent).toBe(CONNECTION_WORDS.down)
    expect(pill()).not.toHaveTextContent('Sultai Midrange')
    // …and the slice really did hold it, or the assertion above would pass vacuously.
    expect(useDeckStore.getState().deck.status).toBe('deck')
  })

  it('does not re-render its way out of the name when the deck is renamed', () => {
    loadDeck('Sultai Midrange')
    applyConnection('live')
    const { rerender } = render(<ConnectionPill />)
    loadDeck('Temur Ramp')
    rerender(<ConnectionPill />)

    expect(pill()).toHaveTextContent('Connected — Temur Ramp')
  })
})

describe('the pill is a real focusable control (AC 8, UX-DR47)', () => {
  it('is a <button>, not a div with a tabindex', () => {
    applyConnection('live')
    render(<ConnectionPill />)

    expect(pill().tagName).toBe('BUTTON')
    expect(pill().getAttribute('type')).toBe('button')
    expect(pill()).not.toHaveAttribute('tabindex')
  })

  it('takes focus, and its accessible name is its own text', () => {
    loadDeck('Sultai Midrange')
    applyConnection('live')
    render(<ConnectionPill />)

    pill().focus()
    expect(pill()).toHaveFocus()

    // THE NAME IS THE TEXT, and the DOM text is `pillText()` byte for byte — that is what the
    // announcement and the glass both use, and it is asserted above and below.
    expect(pill().textContent).toBe(pillText('live', 'Sultai Midrange'))

    // ⚠️ THE COMPUTED ACCESSIBLE NAME LOSES THE SPACES AROUND THE EM DASH, and that is the accname
    // ALGORITHM rather than a defect here: it trims each contributing text node before joining, so
    // the separator span's " — " arrives as "—". Measured, not assumed. Asserted in the normalised
    // form rather than papered over, because the alternative — restructuring the DOM until the two
    // agree — would mean giving up the typography split that keeps the deck name mixed-case, for a
    // difference no screen reader voices (an em dash between words is read as a pause or not at
    // all). The WORDS and their ORDER are what matter, and both are pinned.
    expect(pill()).toHaveAccessibleName('Connected—Sultai Midrange')
    expect(pill().textContent.replace(/\s+/g, '')).toBe(
      'Connected—Sultai Midrange'.replace(/\s+/g, ''),
    )
  })

  it('claims NO behaviour it does not have — the tooltip is c10-1’s (scope fence)', () => {
    // A focusable element that does nothing yet must not lie about what it does. Each of these
    // attributes would announce an interaction this build has not shipped, and `aria-describedby`
    // pointing at nothing would strip meaning from the name computation for no gain.
    loadDeck('Sultai Midrange')
    applyConnection('live')
    render(<ConnectionPill />)

    for (const attribute of ['aria-expanded', 'aria-pressed', 'aria-haspopup', 'title']) {
      expect(pill()).not.toHaveAttribute(attribute)
    }
    expect(pill()).not.toHaveAttribute('aria-describedby')
  })
})

describe('the announcement is a transition, not a level (AC 10, Q4)', () => {
  it('ships a polite live region that is EMPTY at rest', () => {
    applyConnection('live')
    render(<ConnectionPill />)

    expect(region()?.getAttribute('aria-live')).toBe('polite')
    expect(region()?.textContent).toBe('')
  })

  it('says NOTHING on the initial cold-open render (the reconnecting first frame)', () => {
    // `INITIAL_SYSTEM_STATE.connection` is `'reconnecting'` — the honest cold-open value, and the
    // socket loop's own `initialStatus` default. A pill that announced on mount would tell every
    // fresh page load that the app is reconnecting before it had failed at anything.
    render(<ConnectionPill />)

    expect(region()?.textContent).toBe('')
  })

  it('announces the pill’s own text on a real transition', () => {
    loadDeck('Sultai Midrange')
    const { rerender } = render(<ConnectionPill />)
    applyConnection('live')
    rerender(<ConnectionPill />)

    expect(region()?.textContent).toBe(pillText('live', 'Sultai Midrange'))
    expect(region()?.textContent).toBe('Connected — Sultai Midrange')
  })

  it('stays SILENT when only the deck name changes (UX-DR45’s flood rule)', () => {
    // The coalesced deck-refetch announcement already owns that channel. The capture is keyed on
    // the STATUS alone, which is what makes this true by construction rather than by a guard.
    loadDeck('Sultai Midrange')
    const { rerender } = render(<ConnectionPill />)
    applyConnection('live')
    rerender(<ConnectionPill />)
    const afterTransition = region()?.textContent

    loadDeck('Temur Ramp')
    rerender(<ConnectionPill />)

    expect(region()?.textContent).toBe(afterTransition)
    expect(region()?.textContent).not.toContain('Temur Ramp')
  })

  it('announces again on the NEXT transition, and each one carries that state’s words', () => {
    const { rerender } = render(<ConnectionPill />)
    applyConnection('live')
    rerender(<ConnectionPill />)
    expect(region()?.textContent).toBe('Connected')

    applyConnection('reconnecting')
    rerender(<ConnectionPill />)
    expect(region()?.textContent).toBe('Reconnecting')

    applyConnection('down')
    rerender(<ConnectionPill />)
    expect(region()?.textContent).toBe(CONNECTION_WORDS.down)
  })

  it('is OUTSIDE the button — the control must not itself be a live region', () => {
    applyConnection('live')
    render(<ConnectionPill />)

    expect(pill().contains(region())).toBe(false)
  })
})
