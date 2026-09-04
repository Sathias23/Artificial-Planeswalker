/**
 * The connection pill, at component level.
 *
 * WHAT IS HERE AND WHAT IS IN `App.test.tsx`. This file drives the two SLICES directly and asserts
 * what the component makes of them — the dot's class, the words, the deck name, the focusability
 * and the announcement's transition policy. It cannot prove that the pill is on the glass on every
 * SURFACE, or that a real socket drop moves it: both of those are claims about `App`'s composition
 * and the socket loop, so they live in `App.test.tsx` with the `FakeSocket` + fake-timer idiom.
 *
 * ⚠️ `useDeckStore.setState` rather than a production action, and the reason is worth stating:
 * `applyDeckState` is deliberately NOT exported (`deck.ts:176` — "the ONE writer"), and the only
 * production path to a loaded deck is `createDeckBoot`, which makes two requests. Driving the boot
 * here would test the boot. `store-writes.test.ts` excludes `.test.tsx` files from its writer scan
 * for exactly this case; the SHIPPED component still writes nothing, which is what that guard is
 * about.
 */

import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import type { DeckDetail } from '../../api/schema'
import { INITIAL_DECK_STATE, useDeckStore } from '../../state/deck'
import type { ConnectionStatus } from '../../state/socket'
import {
  applyConnection,
  applyInstanceId,
  INITIAL_SYSTEM_STATE,
  useSystemStore,
} from '../../state/systemState'
import { ConnectionPill } from './ConnectionPill'
import { CONNECTION_WORDS, pillText, tooltipText } from './copy'
import { pagePort } from './port'

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
  created_at: '2025-07-01T00:00:00Z',
  updated_at: '2025-08-01T00:00:00Z',
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

describe('the dot reports the status, and never carries it alone', () => {
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
    'names the %s state in WORDS, not in colour alone',
    (status) => {
      applyConnection(status)
      render(<ConnectionPill />)

      expect(pill()).toHaveTextContent(CONNECTION_WORDS[status])
    },
  )

  it('carries the retrying-quietly note in the down state', () => {
    // The last clause of `EXPERIENCE.md`'s disconnected row, and it is TRUE rather than
    // reassuring: `RETRIES_QUIETLY.disconnected === true` and the socket loop reads that map to
    // decide whether to keep scheduling. `copy-tails.test.ts` is where the two are held together.
    applyConnection('down')
    render(<ConnectionPill />)

    expect(pill()).toHaveTextContent('retrying quietly')
  })
})

describe('the deck name comes from the DECK SLICE', () => {
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

  it('still knows a deck is loaded in the DOWN state, and withholds the name anyway', () => {
    // THE LANDMINE THIS COMPONENT IS SHAPED AROUND, from the other side. `surfaceOf` returns a
    // PANEL surface whenever `connection === 'down'` while the deck slice underneath still holds
    // the deck — so a pill reading the surface would be indistinguishable from this one here, and
    // would differ everywhere else. What this test pins is the DECISION: the name is withheld
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

describe('the pill is a real focusable control (UX-DR47)', () => {
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

  it('still claims NO behaviour it does not have (scope fence)', () => {
    // The tooltip exists, so `aria-describedby` is asserted PRESENT (in its own describe
    // below) — but a tooltip is a description, not a popup the button controls, so the
    // popup-shaped claims stay banned, and `title` stays banned because the visible tooltip is
    // the one channel (UX-DR39's hover-only ban; two channels could disagree).
    loadDeck('Sultai Midrange')
    applyConnection('live')
    render(<ConnectionPill />)

    for (const attribute of ['aria-expanded', 'aria-pressed', 'aria-haspopup', 'title']) {
      expect(pill()).not.toHaveAttribute(attribute)
    }
  })
})

describe('the tooltip names the port and the last-confirmed instance', () => {
  const tooltip = () => screen.getByRole('tooltip')

  it('wires aria-describedby to the tooltip, and the description IS its text', () => {
    applyInstanceId('3f9c1a7e')
    applyConnection('live')
    render(<ConnectionPill />)

    // The wiring is jsdom's half of the AC; the visual reveal is CSS + the eye-check.
    expect(pill().getAttribute('aria-describedby')).toBe(tooltip().id)
    expect(pill()).toHaveAccessibleDescription(tooltipText(pagePort(), '3f9c1a7e'))
  })

  it('shows the port with the not-yet-confirmed copy before any health read lands', () => {
    applyConnection('live')
    render(<ConnectionPill />)

    // `instanceId: null` is the cold open; the copy says so in words rather than a placeholder.
    expect(tooltip().textContent).toBe(tooltipText(pagePort(), null))
    expect(tooltip().textContent).toContain('not yet confirmed')
  })

  it('shows the NEW id when a reconnect confirms a different process (AC-4)', () => {
    applyInstanceId('old-process')
    applyConnection('live')
    const { rerender } = render(<ConnectionPill />)
    expect(tooltip().textContent).toContain('old-process')

    applyInstanceId('new-process')
    rerender(<ConnectionPill />)

    expect(tooltip().textContent).toBe(tooltipText(pagePort(), 'new-process'))
    expect(tooltip().textContent).not.toContain('old-process')
  })

  it('shows the id IN FULL with its case preserved — it is data (c4-3’s lesson)', () => {
    applyInstanceId('AbCdEf0123456789AbCdEf0123456789')
    applyConnection('live')
    render(<ConnectionPill />)

    expect(tooltip().textContent).toContain('AbCdEf0123456789AbCdEf0123456789')
  })

  it('retains the last-confirmed id through reconnecting and down — unlike the deck name', () => {
    // The identity truthfully names the last-confirmed backend; the deck-name asymmetry
    // (withheld in `down`) is a different decision about a different claim, and stays untouched.
    loadDeck('Sultai Midrange')
    applyInstanceId('3f9c1a7e')
    applyConnection('down')
    render(<ConnectionPill />)

    expect(tooltip().textContent).toBe(tooltipText(pagePort(), '3f9c1a7e'))
    expect(pill()).not.toHaveTextContent('Sultai Midrange')
  })

  it('sits OUTSIDE the button as its IMMEDIATE next sibling', () => {
    // Outside, or its text would join the accessible NAME (the pinned accname would break);
    // immediately next, or the stylesheet's `+` reveal combinator would match nothing.
    applyConnection('live')
    render(<ConnectionPill />)

    expect(pill().contains(tooltip())).toBe(false)
    expect(pill().nextElementSibling).toBe(tooltip())
  })

  it('leaves the pinned accessible NAME byte-identical with the tooltip present', () => {
    // The description must not leak into the name computation: the accessible name is
    // byte-identical with or without the tooltip present.
    loadDeck('Sultai Midrange')
    applyConnection('live')
    render(<ConnectionPill />)

    expect(pill()).toHaveAccessibleName('Connected—Sultai Midrange')
    expect(pill().textContent).toBe(pillText('live', 'Sultai Midrange'))
  })
})

describe('Escape suppresses the reveal until blur or mouse-leave (WCAG 1.4.13)', () => {
  const tooltip = () => screen.getByRole('tooltip')

  it('suppresses on Escape at the DOCUMENT while the pill is unfocused — the hover channel', () => {
    // The dispatch target is the whole reason for this shape: a hover-only reveal holds
    // no focus, so the key lands on `document.body`, and a button-scoped handler would never
    // hear it. The listener is at the document, and this test would go red if it moved back.
    applyConnection('live')
    render(<ConnectionPill />)
    expect(document.activeElement).not.toBe(pill())

    fireEvent.keyDown(document.body, { key: 'Escape' })

    // The class is the whole mechanism: CSS gates every reveal selector on its absence, so
    // jsdom asserts the bit and the eye-check owns the disappearance.
    expect(tooltip().className).toContain('is-suppressed')
  })

  it('suppresses on Escape while the pill is focused — the keyboard channel', () => {
    applyConnection('live')
    render(<ConnectionPill />)
    pill().focus()

    // Dispatched at the focused pill, which is where a real keydown lands; it reaches the
    // document listener by bubbling, exactly as in a browser.
    fireEvent.keyDown(pill(), { key: 'Escape' })

    expect(tooltip().className).toContain('is-suppressed')
  })

  it('keeps aria-describedby wired and the description intact WHILE suppressed', () => {
    // The header's "ALWAYS wired, whatever the reveal state" claim, asserted in the one state
    // it could silently stop being true: the description is a fact about the
    // pill whether or not it is painted, so dismissing the visual must not strip the semantics.
    applyInstanceId('3f9c1a7e')
    applyConnection('live')
    render(<ConnectionPill />)
    pill().focus()

    fireEvent.keyDown(pill(), { key: 'Escape' })

    expect(tooltip().className).toContain('is-suppressed')
    expect(pill().getAttribute('aria-describedby')).toBe(tooltip().id)
    expect(pill()).toHaveAccessibleDescription(tooltipText(pagePort(), '3f9c1a7e'))
  })

  it('clears the suppression on blur — always, whatever dismissed it', () => {
    applyConnection('live')
    render(<ConnectionPill />)
    pill().focus()
    fireEvent.keyDown(pill(), { key: 'Escape' })

    fireEvent.blur(pill())

    expect(tooltip().className).not.toContain('is-suppressed')
  })

  it('clears the suppression on mouse-leave while the pill is UNFOCUSED — the hover channel ends', () => {
    applyConnection('live')
    render(<ConnectionPill />)
    expect(document.activeElement).not.toBe(pill())
    fireEvent.keyDown(document.body, { key: 'Escape' })

    fireEvent.mouseLeave(pill())

    expect(tooltip().className).not.toContain('is-suppressed')
  })

  it('does NOT clear on mouse-leave while the pill is focused — an exit for the OTHER channel', () => {
    // While the pill holds focus, the keyboard session's dismissal is the standing intent, and
    // a pointer LEAVING the pill is not an event in that session — only blur, or a new ENTRY
    // event beginning a new session, may end the suppression.
    applyConnection('live')
    render(<ConnectionPill />)
    pill().focus()
    fireEvent.keyDown(pill(), { key: 'Escape' })

    fireEvent.mouseLeave(pill())

    expect(tooltip().className).toContain('is-suppressed')
  })

  it('CLEARS on focus after an unrelated Escape — a new session must not inherit the latch', () => {
    // The scenario: Escape pressed anywhere — unpinning the card detail is the common
    // case — reaches the document listener with the pill neither hovered nor focused, and
    // without an entry-time reset the user's NEXT visit to the pill would silently reveal
    // nothing. A new entry is a new intent.
    applyConnection('live')
    render(<ConnectionPill />)
    expect(document.activeElement).not.toBe(pill())
    fireEvent.keyDown(document.body, { key: 'Escape' })
    expect(tooltip().className).toContain('is-suppressed')

    fireEvent.focus(pill())

    expect(tooltip().className).not.toContain('is-suppressed')
  })

  it('CLEARS on mouse-enter after an unrelated Escape — the pointer channel’s same reset', () => {
    // The dismissal contract survives intact: an Escape during an ACTIVE hover stays dismissed
    // precisely because no new mouseenter fires while the pointer is held on the pill — the
    // suppress-at-body test above is that case, entered and not re-entered.
    applyConnection('live')
    render(<ConnectionPill />)
    fireEvent.keyDown(document.body, { key: 'Escape' })
    expect(tooltip().className).toContain('is-suppressed')

    fireEvent.mouseEnter(pill())

    expect(tooltip().className).not.toContain('is-suppressed')
  })

  it('ignores every other key — Escape is the whole vocabulary', () => {
    applyConnection('live')
    render(<ConnectionPill />)

    fireEvent.keyDown(document.body, { key: 'Enter' })

    expect(tooltip().className).not.toContain('is-suppressed')
  })

  it('ignores an Escape inside an IME composition session — the guard the popover taught us', () => {
    // A composition session's Escape cancels the composition, not the reveal, so an unguarded
    // listener would latch on it.
    applyConnection('live')
    render(<ConnectionPill />)

    fireEvent.keyDown(document.body, { key: 'Escape', isComposing: true })

    expect(tooltip().className).not.toContain('is-suppressed')
  })

  it('ignores an Escape another surface already consumed — defaultPrevented stands down', () => {
    // The unit-level twin of the composed App test: the History popover preventDefault()s the
    // Escape that closes it, and a consumed key must not also dismiss this tooltip.
    applyConnection('live')
    render(<ConnectionPill />)

    const consume = (event: KeyboardEvent) => event.preventDefault()
    document.addEventListener('keydown', consume, true)
    try {
      fireEvent.keyDown(document.body, { key: 'Escape', cancelable: true })
    } finally {
      document.removeEventListener('keydown', consume, true)
    }

    expect(tooltip().className).not.toContain('is-suppressed')
  })
})

describe('the page port is window.location’s, never a configured number', () => {
  it('reads the explicit port when the URL carries one', () => {
    expect(pagePort({ port: '8000', protocol: 'http:' })).toBe('8000')
  })

  it('names the default the browser elided — 443 for https, 80 otherwise', () => {
    // jsdom's fixed test URL cannot reach these arms, which is why the helper takes an
    // injectable location; production callers pass nothing and get `window.location`.
    expect(pagePort({ port: '', protocol: 'https:' })).toBe('443')
    expect(pagePort({ port: '', protocol: 'http:' })).toBe('80')
  })

  it('defaults to the REAL window.location — the production arm is executed, not assumed', () => {
    // jsdom's test URL carries an explicit port, so the non-vacuity check pins that this smoke
    // run exercises the explicit-port arm against the real global rather than passing on an
    // empty string (without it the zero-argument arm would never run).
    expect(window.location.port).not.toBe('')
    expect(pagePort()).toBe(window.location.port)
  })
})

describe('the announcement is a transition, not a level', () => {
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

  it('stays SILENT when only the INSTANCE ID changes — identity is not a status', () => {
    // The dot never carries state alone and the region announces status TRANSITIONS only; an
    // identity confirmation is data for the tooltip, not a transition, and the capture being
    // keyed on the status alone is what makes this true by construction — the deck-name rule's
    // argument, applied to the second piece of data this component now renders.
    const { rerender } = render(<ConnectionPill />)
    applyConnection('live')
    rerender(<ConnectionPill />)
    const afterTransition = region()?.textContent

    applyInstanceId('3f9c1a7e')
    rerender(<ConnectionPill />)

    expect(region()?.textContent).toBe(afterTransition)
    expect(region()?.textContent).not.toContain('3f9c1a7e')
  })

  it('is OUTSIDE the button — the control must not itself be a live region', () => {
    applyConnection('live')
    render(<ConnectionPill />)

    expect(pill().contains(region())).toBe(false)
  })
})
