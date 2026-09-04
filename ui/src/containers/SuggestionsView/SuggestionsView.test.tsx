import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Card, CardSummary } from '../../api/schema'
import { resetCardCache, useCardStore } from '../../state/cards'
import { flipCard, resetFaces } from '../../state/faces'
import { resetInspection, useInspectionStore } from '../../state/inspection'
import { SuggestionsView } from './SuggestionsView'
import { EMPTY_PUSH_TEMPLATE, NOUN_PLACEHOLDER, emptyPushLine } from './copy'

/**
 * The suggestions view's body — the empty line and the rows.
 *
 * ================= WHAT THIS SUITE CANNOT CARRY, SAID FIRST ============================
 *
 * jsdom evaluates no stylesheet, so nothing here proves the thumbnail is card-shaped, that the
 * live marker is `--accent` rather than `--accent-dim`, that the confidence is uppercased by its
 * type role, or that the row is 24px tall in any direction. Those are read as SOURCE by
 * `token-usage.test.ts`, `shell.test.ts` and `keyboard-floor.test.ts`, and otherwise only seen
 * with eyes on the manual checklist.
 *
 * jsdom also loads no images: `naturalWidth` is 0 always, `load` and `error` never fire on their
 * own, and `useCardArt`'s cached-settle is inert here in both directions. Art states are driven
 * MANUALLY below, which is what makes the well assertions mean anything at all.
 *
 * What this file proves is the BRANCH and the WIRING — which element renders for which input,
 * which handler reaches which store verb, and that one malformed entry costs exactly one row.
 */

const ITEM = { card_id: 'c-1', reason: 'Fills the two-drop gap.' }
const OTHER = { card_id: 'c-2', reason: 'Second body for the same slot.' }

const summary = (id: string, over: Partial<CardSummary> = {}): CardSummary => ({
  id,
  name: `Card ${id}`,
  mana_cost: '{1}{G}',
  cmc: 2,
  type_line: 'Creature — Elf',
  oracle_text: '',
  colors: ['G'],
  rarity: 'common',
  set_code: 'tst',
  set_name: 'Test Set',
  collector_number: '1',
  oracle_id: 'oracle-1',
  color_identity: [],
  legalities: {},
  games: [],
  ...over,
})

const card = (id: string, over: Partial<Card> = {}): Card => ({
  ...summary(id),
  oracle_id: `oracle-${id}`,
  color_identity: ['G'],
  ...over,
})

/** The cache tiers, written straight into the store — no request, no timing, no flush. */
const seedHydrated = (id: string, over: Partial<Card> = {}) => {
  useCardStore.setState((state) => ({
    cards: { ...state.cards, [id]: { status: 'hydrated', card: card(id, over) } },
  }))
}

const seedUnknown = (id: string) => {
  useCardStore.setState((state) => ({
    cards: {
      ...state.cards,
      [id]: {
        status: 'unknown',
        reason: 'card_not_found',
        placeholder: 'unknown-card',
        summary: null,
        retryable: false,
      },
    },
  }))
}

/**
 * A refusal with NO placeholder — the picture failed, the card did not.
 *
 * The distinction this suite has to keep straight: `placeholder: 'unknown-card'`
 * means *the app does not know what this card is*; `null` means *the read did not land and
 * whatever summary exists still stands*. Only the first is uninspectable.
 */
const seedImagelessButKnown = (id: string) => {
  useCardStore.setState((state) => ({
    cards: {
      ...state.cards,
      [id]: {
        status: 'unknown',
        reason: 'no_image_data',
        placeholder: null,
        summary: summary(id),
        retryable: false,
      },
    },
  }))
}

const rows = (container: HTMLElement) => [
  ...container.querySelectorAll<HTMLButtonElement>('.suggestion-row'),
]

const rowAt = (container: HTMLElement, index: number) => {
  const found = rows(container)[index]
  expect(found, `no row at index ${index}`).toBeDefined()
  return found
}

beforeEach(() => {
  resetCardCache()
  resetInspection()
  resetFaces()
  // A read that never settles. The rows fire hydration from an effect on mount, and every test
  // below wants the cache tier IT seeded rather than whatever a resolved request would overwrite
  // it with. `hydrateCard` never rejects, so nothing here needs a catch.
  vi.stubGlobal(
    'fetch',
    vi.fn(() => new Promise(() => {})),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('an empty push renders the artefact’s line (UX-DR33, AD-7)', () => {
  it('renders the sentence, with the wire kind substituted', () => {
    render(<SuggestionsView kind="suggestions" items={[]} />)

    expect(screen.getByText(emptyPushLine('suggestions'))).toBeInTheDocument()
    // The substitution really happened: the placeholder is gone from what a reader sees. A
    // component that rendered the raw template would satisfy a `toContain('The agent sent')`
    // check and put `{noun}` on the glass.
    expect(document.body.textContent).not.toContain(NOUN_PLACEHOLDER)
    expect(document.body.textContent).toContain('suggestions')
  })

  it('takes the kind from its PROP rather than assuming one', () => {
    // Non-vacuity for the assertion above, and the property every other view kind depends on: a
    // hard-coded `'suggestions'` passes every test above and renders the wrong noun the day a
    // tier list is empty.
    render(<SuggestionsView kind="tier_list" items={[]} />)

    expect(screen.getByText(emptyPushLine('tier_list'))).toBeInTheDocument()
  })

  it('is a bare paragraph and NOT a state panel (EXPERIENCE.md’s "no panel")', () => {
    const { container } = render(<SuggestionsView kind="suggestions" items={[]} />)

    const line = container.querySelector('.suggestions-view-empty')
    expect(line).not.toBeNull()
    expect(line?.tagName).toBe('P')
    // No second live region inside the dialog: the view's announcement is the heading's, and a
    // region here would announce the same arrival twice.
    expect(line).not.toHaveAttribute('aria-live')
    expect(screen.queryByRole('region')).toBeNull()
  })

  it('REPLACES the list rather than sitting inside one (DESIGN.md)', () => {
    // DESIGN.md's `components.empty-push-line`: a `<p>` inside a `<ul>` is
    // invalid against UX-DR44's mandated list semantics, and an empty list beside the sentence
    // announces "list, 0 items" to a screen-reader user BEFORE the sentence explaining why.
    const { container } = render(<SuggestionsView kind="suggestions" items={[]} />)

    expect(screen.queryByRole('list')).toBeNull()
    expect(container.querySelector('ul')).toBeNull()
  })
})

describe('the rows, and their anatomy (UX-DR24, UX-DR44)', () => {
  it('renders a real ul/li — one li per item, in payload order (UX-DR44)', () => {
    seedHydrated('c-1')
    seedHydrated('c-2')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM, OTHER]} />)

    // BY ROLE, because the list semantics are what tell a screen-reader user how many
    // suggestions arrived before they start moving through them.
    const list = screen.getByRole('list')
    expect(list.tagName).toBe('UL')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    // Order is the payload's, unsorted and unregrouped: `contracts.py` calls the suggestions "a
    // flat list with no sectioning", and the agent chose this order.
    expect(rows(container)).toHaveLength(2)
    expect(rowAt(container, 0)).toHaveTextContent(ITEM.reason)
    expect(rowAt(container, 1)).toHaveTextContent(OTHER.reason)
    // …and the empty-state line is NOT also on the glass, which is the inverted-branch failure.
    expect(container.querySelector('.suggestions-view-empty')).toBeNull()
  })

  it('renders every slot DESIGN.md names, in a row that has them all', () => {
    seedHydrated('c-1', { name: 'Llanowar Elves', mana_cost: '{G}' })
    const { container } = render(
      <SuggestionsView
        kind="suggestions"
        items={[{ ...ITEM, category: 'ramp', confidence: 'high' }]}
      />,
    )
    const row = rowAt(container, 0)

    // The thumbnail slot, the badge, the name in its own element, the cost, the confidence, the
    // reason. Asserted as PRESENCE + CONTENT rather than as order-in-the-DOM, because the visual
    // order is the stylesheet's grid and jsdom cannot see it.
    expect(row.querySelector('.suggestion-row-thumb')).not.toBeNull()
    expect(row.querySelector('.badge')).toHaveTextContent('ramp')
    expect(row.querySelector('.suggestion-row-name')).toHaveTextContent('Llanowar Elves')
    expect(row.querySelector('.suggestion-row-cost')).not.toBeNull()
    expect(row.querySelector('.suggestion-row-confidence')).toHaveTextContent('high')
    expect(row.querySelector('.suggestion-row-reason')).toHaveTextContent(ITEM.reason)
  })

  it('renders the wire CATEGORY in the badge, and no badge without one', () => {
    // The "action badge" has no wire backing — the only badge-bearing datum is `category`, and
    // DESIGN.md and EXPERIENCE.md are both annotated to say so. An absent category renders no
    // pill at all, rather than an empty one.
    seedHydrated('c-1')
    seedHydrated('c-2')
    const { container } = render(
      <SuggestionsView kind="suggestions" items={[{ ...ITEM, category: 'removal' }, OTHER]} />,
    )

    expect(rowAt(container, 0).querySelector('.badge')).toHaveTextContent('removal')
    expect(rowAt(container, 1).querySelector('.badge')).toBeNull()
    // NEUTRAL tone, the only one that invents nothing: no mapping from free-text categories to
    // the four semantic tones exists anywhere, and inventing one here would tint a row green for
    // saying "ramp".
    expect(rowAt(container, 0).querySelector('.badge')).toHaveClass('badge-neutral')
  })

  it('renders the confidence TOKEN verbatim, and nothing when it is absent', () => {
    seedHydrated('c-1')
    seedHydrated('c-2')
    const { container } = render(
      <SuggestionsView kind="suggestions" items={[{ ...ITEM, confidence: 'low' }, OTHER]} />,
    )

    // The wire word, unwrapped. `--type-micro` uppercases it in the stylesheet — a type role
    // doing its job — so no authored string is involved and no COPY_MODULES entry is owed.
    expect(rowAt(container, 0).querySelector('.suggestion-row-confidence')).toHaveTextContent('low')
    expect(rowAt(container, 1).querySelector('.suggestion-row-confidence')).toBeNull()
  })

  it('refuses a confidence that is not one of the three tokens (Confidence, contracts.py)', () => {
    // The slot is a CHROME token in a 10px uppercase role, not free text: an arbitrary wire
    // string landing there is a paragraph shouted in a slot sized for one word. `reason` and
    // `category` are free text by specification and are NOT clamped — the difference is the slot,
    // and this test is what keeps the two rules apart.
    const { container } = render(
      <SuggestionsView
        kind="suggestions"
        items={[{ ...ITEM, confidence: 'extremely-high' } as unknown as typeof ITEM]}
      />,
    )

    expect(rowAt(container, 0).querySelector('.suggestion-row-confidence')).toBeNull()
    // The rest of the row is untouched — one bad field is not a bad row.
    expect(rowAt(container, 0)).toHaveTextContent(ITEM.reason)
  })

  it('shows the FRONT face’s name and cost for a double-faced card (UX-DR19)', () => {
    seedHydrated('c-1', {
      name: 'Clearwater Pathway // Murkwater Pathway',
      mana_cost: '',
      card_faces: [{ name: 'Clearwater Pathway', mana_cost: '{U}' }],
    })
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)

    // The combined `X // Y` string belongs on the detail panel; a row's name column shows the
    // front face, exactly as the deck row does. 87.8% of faced cards carry a BLANK top-level
    // `mana_cost` whose real value lives only in `card_faces[0]`, which is the half that needs
    // hydration — and this row has it.
    expect(rowAt(container, 0).querySelector('.suggestion-row-name')).toHaveTextContent(
      'Clearwater Pathway',
    )
    expect(rowAt(container, 0).querySelector('.suggestion-row-name')).not.toHaveTextContent('//')
    expect(container.querySelector('[role="img"]')).toHaveAttribute(
      'aria-label',
      expect.stringContaining('blue'),
    )
  })

  it('renders the row BEFORE the name exists, with the line already reserved', () => {
    // These ids carry no summary seed and no deck sweep, so a row's first frame has a reason and
    // nothing else. The name element is PRESENT and empty rather than absent: a name that
    // appeared by inserting an element would reflow the row under the reader, and the
    // thumbnail's width derives from that height.
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)

    const name = rowAt(container, 0).querySelector('.suggestion-row-name')
    expect(name).not.toBeNull()
    expect(name).toBeEmptyDOMElement()
    expect(rowAt(container, 0)).toHaveTextContent(ITEM.reason)
  })
})

describe('the thumbnail (UX-DR36, AD-11, AD-12)', () => {
  it('draws from the backend PROXY at the unspelled rendition', () => {
    seedHydrated('c-1')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)

    const image = container.querySelector('.suggestion-row-image')
    expect(image).not.toBeNull()
    expect(image).toHaveAttribute('src', '/api/card-image/c-1')
    // UNSPELLED, so this shares the grid's browser-cache key. `?size=normal` is a SECOND
    // cache entry for one picture, and a suggested card that later joins the deck would then
    // fetch it twice. `no-scryfall-hosts.test.ts` bans the CDN family across all of `src/`; this
    // asserts the positive form for the one surface that draws agent-supplied ids.
    expect(image?.getAttribute('src')).not.toContain('size=')
    expect(image?.getAttribute('src')).not.toContain('scryfall')
  })

  it('carries alt="" EXACTLY — the name is announced once, from the row text', () => {
    seedHydrated('c-1', { name: 'Llanowar Elves' })
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)

    const image = container.querySelector('.suggestion-row-image')
    expect(image).toHaveAttribute('alt', '')
    // UX-DR48's own words for this shape. The failure it prevents is audible: with `alt={name}`
    // a screen-reader user hears "Llanowar Elves Llanowar Elves" inside one button.
    expect(rowAt(container, 0).textContent?.match(/Llanowar Elves/g)).toHaveLength(1)
    expect(image).not.toHaveAttribute('aria-label')
  })

  it('keeps a silent WELL under the picture from the first frame (UX-DR36)', () => {
    seedHydrated('c-1')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)

    // The well is what gives the slot its size before any byte arrives, so it stays mounted
    // UNDER a shown image rather than being swapped out for one — that swap is the reflow
    // UX-DR36 bans. It carries no text and no spinner.
    const well = container.querySelector('.card-placeholder-well')
    expect(well).not.toBeNull()
    expect(well).toBeEmptyDOMElement()
    expect(well).toHaveAttribute('aria-hidden', 'true')
    expect(container.querySelector('.suggestion-row-image')).toHaveAttribute('data-loaded', 'false')
  })

  it('reveals the picture on load, and swaps to the NAMED placeholder on error (AD-11)', () => {
    seedHydrated('c-1', { name: 'Llanowar Elves', type_line: 'Creature — Elf Druid' })
    const { container, rerender } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)

    // Driven MANUALLY: jsdom fetches nothing and fires neither event on its own.
    fireEvent.load(container.querySelector('.suggestion-row-image')!)
    expect(container.querySelector('.suggestion-row-image')).toHaveAttribute('data-loaded', 'true')

    rerender(<SuggestionsView kind="suggestions" items={[ITEM]} />)
    fireEvent.error(container.querySelector('.suggestion-row-image')!)

    // The picture failed; the CARD did not. AD-11 promises the backend serves no substitute, so
    // the app draws the one it designed — carrying what the cache knows about the card.
    expect(container.querySelector('.suggestion-row-image')).toBeNull()
    const placeholder = container.querySelector('.card-placeholder')
    expect(placeholder).toHaveTextContent('Llanowar Elves')
    expect(placeholder).toHaveTextContent('Creature — Elf Druid')
    // …and it is NOT the unknown variant: this card is perfectly well known.
    expect(placeholder).not.toHaveTextContent('Unknown card')
  })

  it('honours the flip STATE and renders no flip CONTROL (EXPERIENCE.md:85)', () => {
    seedHydrated('c-1')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)
    expect(container.querySelector('.suggestion-row-image')).toHaveAttribute(
      'src',
      '/api/card-image/c-1',
    )

    // Flipped ELSEWHERE — the grid, or the detail panel — because the state is keyed by printing
    // rather than by location: "a flipped tile is flipped everywhere it appears". Wrapped in
    // `act` because this is a store write from OUTSIDE an event handler: `fireEvent` batches and
    // flushes on its own, a bare `setState` does not, and the row would still be showing the
    // front face when the assertion ran.
    act(() => flipCard('c-1', 2))

    expect(container.querySelector('.suggestion-row-image')).toHaveAttribute(
      'src',
      '/api/card-image/c-1?face=1',
    )
    // The CONTROL is withheld: UX-DR15 places it on tiles and the detail panel, nothing specs it
    // for a row, and a ≥32px hit area does not fit a thumbnail this size. Flipping stays reachable
    // through the panel this row targets on hover.
    expect(container.querySelector('.flip-control')).toBeNull()
    expect(rowAt(container, 0).querySelectorAll('button')).toHaveLength(0)
  })
})

describe('one bad entry costs one row and never the push (FR-13, AD-7)', () => {
  it('degrades an UNKNOWN id to the placeholder while its reason still renders', () => {
    seedUnknown('c-1')
    seedHydrated('c-2')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM, OTHER]} />)

    const bad = rowAt(container, 0)
    expect(bad.querySelector('.card-placeholder')).toHaveTextContent('Unknown card')
    // THE HALF THAT IS THE WHOLE POINT: the reason survives. A push whose third id is stale is
    // still a push of six suggestions, and the words explaining the sixth are what the agent
    // actually said.
    expect(bad).toHaveTextContent(ITEM.reason)
    expect(bad.querySelector('.suggestion-row-image')).toBeNull()

    // …and the NEIGHBOUR is untouched: one dead entry, one dead thumbnail.
    expect(rowAt(container, 1).querySelector('.suggestion-row-image')).toHaveAttribute(
      'src',
      '/api/card-image/c-2',
    )
    expect(rowAt(container, 1)).toHaveTextContent(OTHER.reason)
  })

  it('shows the truncated id on the unknown thumbnail — the only identity left', () => {
    seedUnknown('abcdef0123456789')
    const { container } = render(
      <SuggestionsView kind="suggestions" items={[{ ...ITEM, card_id: 'abcdef0123456789' }]} />,
    )

    expect(container.querySelector('.card-placeholder-id')).toHaveTextContent('abcdef01')
  })

  it('keeps a card whose PICTURE failed fully inspectable', () => {
    // The distinction `entry.placeholder` exists to carry: a `no_image_data` refusal is NOT an
    // unknown card. The app knows its name, cost and type line, so the row draws the named
    // placeholder and the store lets it be inspected.
    seedImagelessButKnown('c-1')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)

    // The picture is still attempted — `no_image_data` is the METADATA read's refusal, and the
    // image route is a different door with its own answer. jsdom fetches nothing, so the failure
    // is driven by hand.
    fireEvent.error(container.querySelector('.suggestion-row-image')!)

    const placeholder = container.querySelector('.card-placeholder')
    expect(placeholder).toHaveTextContent(`Card c-1`)
    expect(placeholder).not.toHaveTextContent('Unknown card')
    // …and the store lets it be inspected, because the app knows what this card IS.
    fireEvent.mouseEnter(rowAt(container, 0))
    expect(useInspectionStore.getState().hoveredId).toBe('c-1')
  })

  it('renders a NON-STRING card_id as the unknown placeholder, and never throws', () => {
    // The envelope builder lets a `card_id` that is not a string pass through untouched; the row
    // that renders it is the gate. A `TypeError` here is React unmounting the whole dialog — the
    // wholesale failure FR-13 bans — so the gate is a `typeof`, not a `?.`.
    const malformed = [
      { card_id: 42, reason: 'A number id.' },
      { card_id: null, reason: 'A null id.' },
      { card_id: undefined, reason: 'An absent id.' },
      { card_id: { id: 'c-1' }, reason: 'An object id.' },
    ] as unknown as (typeof ITEM)[]

    const { container } = render(<SuggestionsView kind="suggestions" items={malformed} />)

    expect(rows(container)).toHaveLength(4)
    for (const [index, item] of malformed.entries()) {
      const row = rowAt(container, index)
      expect(row.querySelector('.card-placeholder')).toHaveTextContent('Unknown card')
      // The REASON still renders — the row is degraded, not lost.
      expect(row).toHaveTextContent(item.reason)
      // No request was made for a picture of nothing.
      expect(row.querySelector('.suggestion-row-image')).toBeNull()
    }
  })

  it('renders a MISSING or non-string reason as an empty line, row otherwise normal', () => {
    seedHydrated('c-1', { name: 'Llanowar Elves' })
    const malformed = [
      { card_id: 'c-1' },
      { card_id: 'c-1', reason: null },
      { card_id: 'c-1', reason: 7 },
      { card_id: 'c-1', reason: '   ' },
    ] as unknown as (typeof ITEM)[]

    const { container } = render(<SuggestionsView kind="suggestions" items={malformed} />)

    expect(rows(container)).toHaveLength(4)
    for (const [index] of malformed.entries()) {
      const line = rowAt(container, index).querySelector('.suggestion-row-reason')
      // The ELEMENT is present either way. Dropping it would silently change the row's height —
      // and therefore the width of the thumbnail beside it, which derives from that height.
      expect(line, `row ${index} lost its reason line`).not.toBeNull()
      expect(rowAt(container, index).querySelector('.suggestion-row-name')).toHaveTextContent(
        'Llanowar Elves',
      )
    }
    // A blank-but-present reason is rendered as it arrived rather than trimmed away: the row has
    // no standing to decide the agent meant nothing by it.
    expect(rowAt(container, 0).querySelector('.suggestion-row-reason')).toBeEmptyDOMElement()
  })

  it('renders a non-string CATEGORY as no badge at all', () => {
    seedHydrated('c-1')
    const { container } = render(
      <SuggestionsView
        kind="suggestions"
        items={[{ ...ITEM, category: 12 } as unknown as typeof ITEM]}
      />,
    )

    expect(rowAt(container, 0).querySelector('.badge')).toBeNull()
    expect(rowAt(container, 0)).toHaveTextContent(ITEM.reason)
  })

  it('renders duplicate ids as separate rows, with no key collision', () => {
    // Agent-supplied ids are NOT unique by the data — `CardGrid`'s "unique by (deck_id, card_id)"
    // argument does not transfer. `contracts.py` caps the item count and each field's length and
    // says nothing about duplicates, so two rows suggesting the same card in different words are
    // a legal push. A bare-id key would collide and React would drop one.
    seedHydrated('c-1')
    const { container } = render(
      <SuggestionsView
        kind="suggestions"
        items={[ITEM, { ...ITEM, reason: 'And again, for the sideboard.' }]}
      />,
    )

    expect(rows(container)).toHaveLength(2)
    expect(rowAt(container, 0)).toHaveTextContent(ITEM.reason)
    expect(rowAt(container, 1)).toHaveTextContent('And again, for the sideboard.')
  })
})

describe('the inspection contract, verb for verb (UX-DR14, UX-DR20)', () => {
  it('sets the target on hover and on focus, in their OWN slots', () => {
    seedHydrated('c-1')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)
    const row = rowAt(container, 0)

    fireEvent.mouseEnter(row)
    expect(useInspectionStore.getState().hoveredId).toBe('c-1')
    expect(useInspectionStore.getState().lastTransient).toBe('hover')

    fireEvent.focus(row)
    expect(useInspectionStore.getState().focusedId).toBe('c-1')
    // TWO SLOTS, not one: a `mouseleave` must not erase a still-focused row.
    expect(useInspectionStore.getState().hoveredId).toBe('c-1')
    expect(useInspectionStore.getState().lastTransient).toBe('focus')
  })

  it('clears each slot on the matching leave, keyed by id', () => {
    seedHydrated('c-1')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)
    const row = rowAt(container, 0)

    fireEvent.mouseEnter(row)
    fireEvent.focus(row)
    fireEvent.mouseLeave(row)
    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(useInspectionStore.getState().focusedId).toBe('c-1')

    fireEvent.blur(row)
    expect(useInspectionStore.getState().focusedId).toBeNull()
  })

  it('pins on click and RELEASES on a second single click (UX-DR20)', () => {
    seedHydrated('c-1')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)
    const row = rowAt(container, 0)

    fireEvent.click(row)
    expect(useInspectionStore.getState().pinnedId).toBe('c-1')

    // A second SINGLE click, never a double-click: `EXPERIENCE.md`'s banned-interactions list
    // names double-click semantics outright.
    fireEvent.click(row)
    expect(useInspectionStore.getState().pinnedId).toBeNull()
  })

  it('is a real <button> with no tabindex and no keydown handler (UX-DR39, UX-DR40, UX-DR47)', () => {
    seedHydrated('c-1')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)
    const row = rowAt(container, 0)

    expect(row.tagName).toBe('BUTTON')
    expect(row).toHaveAttribute('type', 'button')
    // No `tabindex` ANYWHERE: nothing in the app carries one (UX-DR40), and the shell's focus
    // trap mishandles `tabindex="-1"` on natively-focusable elements, so
    // a roving composite here would be the first content to trip it.
    expect(row).not.toHaveAttribute('tabindex')
    // Enter and Space are the button's own click, which is why the element was chosen. A row
    // `onKeyDown` would also never see Escape while a view is open, because the document-capture
    // listener calls `stopPropagation()` below React's delegation root.
    expect(screen.getAllByRole('button')).toHaveLength(1)
  })

  it('marks EXACTLY the live row, and marks it on hover, focus and pin', () => {
    seedHydrated('c-1')
    seedHydrated('c-2')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM, OTHER]} />)

    expect(rows(container).filter((r) => r.classList.contains('is-live'))).toHaveLength(0)

    fireEvent.mouseEnter(rowAt(container, 1))
    expect(rowAt(container, 1)).toHaveClass('is-live')
    expect(rowAt(container, 0)).not.toHaveClass('is-live')

    // The pin wins over the hover, which is `targetIdOf`'s precedence and not this row's opinion.
    fireEvent.click(rowAt(container, 0))
    expect(rowAt(container, 0)).toHaveClass('is-live')
    expect(rowAt(container, 1)).not.toHaveClass('is-live')
    expect(rows(container).filter((r) => r.classList.contains('is-live'))).toHaveLength(1)
  })

  it('REFUSES every verb on an unknown-card row, through the store (UX-DR22)', () => {
    // The refusal is `inspection.ts`'s `inspectable()`, written for thumbnails whose ids do not
    // come from a deck at all — exactly this surface. What this test proves is that the row
    // actually ROUTES through it: the handlers are
    // attached to an unknown row exactly as to any other, and the store is what says no.
    seedUnknown('c-1')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)
    const row = rowAt(container, 0)

    fireEvent.mouseEnter(row)
    fireEvent.focus(row)
    fireEvent.click(row)

    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(useInspectionStore.getState().focusedId).toBeNull()
    expect(useInspectionStore.getState().pinnedId).toBeNull()
    expect(row).not.toHaveClass('is-live')
    // AND IT IS STILL A BUTTON. Dropping it would make a focused row's control vanish underneath
    // the person as `loading → unknown` lands — inside the shell's focus trap, dropping focus to
    // `<body>`. Uniform buttons make that state unreachable.
    expect(row.tagName).toBe('BUTTON')
    expect(row).not.toBeDisabled()

    // THE NON-VACUITY CONTROL, AND IT IS THE HALF THAT CARRIES THE CLAIM: the assertions above
    // are satisfied by a row with NO HANDLERS AT ALL. Every expectation up to here is an ABSENCE,
    // and unwiring all five verbs produces exactly the same absences.
    //
    // So the same row, on the same mount, is driven again with the ONLY thing changed being the
    // cache tier. If the handlers were missing, this hover would set nothing either and the test
    // fails — which is what makes "the store did the refusing" a claim rather than a coincidence.
    act(() => seedHydrated('c-1'))
    fireEvent.mouseEnter(rowAt(container, 0))

    expect(useInspectionStore.getState().hoveredId).toBe('c-1')
  })

  it('survives the loading → unknown transition with focus intact (Landmine 4)', () => {
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)
    rowAt(container, 0).focus()
    expect(document.activeElement).toBe(rowAt(container, 0))

    // The entry resolves to "not a card" WHILE the row is focused — the ordinary path, not an
    // edge case: every one of these ids starts life unseen. `act` so the re-render this causes
    // actually happens before the assertion, rather than the test passing on a stale tree.
    act(() => seedUnknown('c-1'))
    expect(rowAt(container, 0).querySelector('.card-placeholder')).toHaveTextContent('Unknown card')

    expect(document.activeElement).toBe(rowAt(container, 0))
    expect(document.activeElement).not.toBe(document.body)
  })

  it('releases a stale hover, focus AND pin when the entry resolves to unknown', () => {
    // `inspectable()` only refuses an id it ALREADY knows is dead — it has no opinion about one
    // that is ABOUT TO become dead. A suggestion id starts life `undefined`, which IS
    // inspectable (deliberately, for deck cards' cold-open hover), so a real interaction in the
    // window before hydration settles can set every one of the three targets on a card that is
    // moments from resolving to `unknown`. jsdom's near-synchronous promises never expose this
    // ordering on their own — this test forces it with `seedUnknown` after the targets are set.
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)
    const row = rowAt(container, 0)

    fireEvent.mouseEnter(row)
    fireEvent.focus(row)
    fireEvent.click(row)
    expect(useInspectionStore.getState().hoveredId).toBe('c-1')
    expect(useInspectionStore.getState().focusedId).toBe('c-1')
    expect(useInspectionStore.getState().pinnedId).toBe('c-1')
    expect(row).toHaveClass('is-live')

    act(() => seedUnknown('c-1'))

    expect(useInspectionStore.getState().hoveredId).toBeNull()
    expect(useInspectionStore.getState().focusedId).toBeNull()
    expect(useInspectionStore.getState().pinnedId).toBeNull()
    expect(rowAt(container, 0)).not.toHaveClass('is-live')
  })

  it('only releases the id that actually went unknown, never a sibling row’s target', () => {
    // The non-vacuity half: a keyed release that fired unconditionally would be indistinguishable
    // from this test's assertions unless a SECOND, still-good row is in play to prove it was left
    // alone.
    seedHydrated('c-2')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM, OTHER]} />)

    fireEvent.click(rowAt(container, 1))
    expect(useInspectionStore.getState().pinnedId).toBe('c-2')

    act(() => seedUnknown('c-1'))

    expect(useInspectionStore.getState().pinnedId).toBe('c-2')
    expect(rowAt(container, 1)).toHaveClass('is-live')
  })
})

describe('hydration is this view’s own (AD-12)', () => {
  const cardCalls = () =>
    (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls
      .map(([input]) => String(input))
      .filter((path) => path.startsWith('/api/cards/'))

  it('asks once per UNIQUE id, for ids no deck sweep will ever reach', () => {
    render(
      <SuggestionsView
        kind="suggestions"
        items={[ITEM, OTHER, { ...ITEM, reason: 'Same card, second argument.' }]}
      />,
    )

    // Three rows, two distinct ids, two reads. `hydrateCard` dedupes in flight as well, so this
    // is belt and braces at the seam that decides — but the `Set` is what makes a 60-item push
    // of one repeated card cost one request rather than sixty.
    expect(cardCalls()).toHaveLength(2)
    expect(cardCalls()).toContain('/api/cards/c-1')
    expect(cardCalls()).toContain('/api/cards/c-2')
  })

  it('re-hydrates when ITEMS change — a replace-in-place brings new ids', () => {
    const { rerender } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)
    expect(cardCalls()).toHaveLength(1)

    // Replace-in-place is a re-fire against a MOUNTED shell, so a second push reaches
    // this component as new props on the same instance. A mount-only effect would leave every id
    // of the second push unhydrated — a whole view of silent wells.
    rerender(<SuggestionsView kind="suggestions" items={[OTHER]} />)

    expect(cardCalls()).toContain('/api/cards/c-2')
    expect(cardCalls()).toHaveLength(2)
  })

  it('asks for nothing at all on an empty push', () => {
    render(<SuggestionsView kind="suggestions" items={[]} />)
    expect(cardCalls()).toHaveLength(0)
  })

  it('issues NO request for a malformed id, and lands it on the placeholder anyway', () => {
    // `hydrateCard('')` refuses terminally with `placeholder: 'unknown-card'` and issues nothing:
    // the empty id addresses the collection route rather than a card, so the uuid gate never sees
    // it. That is what routes a malformed item into the degradation an unknown card already gets,
    // through machinery that already exists — rather than into a new refusal invented at the row.
    const { container } = render(
      <SuggestionsView
        kind="suggestions"
        items={[{ card_id: null, reason: 'A null id.' } as unknown as typeof ITEM]}
      />,
    )

    expect(cardCalls()).toHaveLength(0)
    expect(container.querySelector('.card-placeholder')).toHaveTextContent('Unknown card')
    expect(useCardStore.getState().cards['']?.status).toBe('unknown')
  })
})

describe('the card shape arrives through the CLASS, never by hand (UX-DR4)', () => {
  // The MARKUP half of the `CARD_SHAPED` rule. Its guard's own header says there is *"no markup
  // allowlist to join, because the way in is always the `card-shape` class"* — so this is the
  // positive form of that claim for the first surface to draw an agent-supplied card.
  //
  // The SOURCE half — that this stylesheet spends no `--accent-dim`, no `--radius-card` and no
  // `aspect-ratio` — lives in `tests/token-usage.test.ts` beside the guard whose declared blind
  // spot is this exact composition. It cannot live here: jsdom evaluates no stylesheet at all.
  it('puts card-shape on the picture, with no inline geometry anywhere', () => {
    seedHydrated('c-1')
    const { container } = render(<SuggestionsView kind="suggestions" items={[ITEM]} />)

    expect(container.querySelector('.suggestion-row-image')).toHaveClass('card-shape')
    expect(container.querySelector('.suggestion-row-image')).not.toHaveAttribute('style')
    // The placeholders bring their own, from their own listed stylesheet.
    expect(container.querySelector('.card-placeholder-well')).toHaveClass('card-shape')
  })
})

describe('the template is a template (non-vacuity for the gate next door)', () => {
  it('carries exactly one placeholder, and the builder fills it', () => {
    // `tests/empty-push-copy.test.ts` compares this constant against EXPERIENCE.md byte for
    // byte. This asserts the property that makes the comparison meaningful for a RENDERED line:
    // one hole, filled once, leaving no marker behind.
    expect(EMPTY_PUSH_TEMPLATE.split(NOUN_PLACEHOLDER)).toHaveLength(2)
    expect(emptyPushLine('suggestions')).not.toContain(NOUN_PLACEHOLDER)
    expect(emptyPushLine('suggestions')).toBe(
      "The agent's suggestions came back empty. Nothing to show — ask it for another pass.",
    )
    // The display-noun table's whole point, asserted at the rendered surface: the kind whose
    // wire literal would put an underscore on the glass renders its display noun instead.
    expect(emptyPushLine('tier_list')).toBe(
      "The agent's tier list came back empty. Nothing to show — ask it for another pass.",
    )
    expect(emptyPushLine('groups')).toContain('card groups')
  })
})
