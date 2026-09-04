/**
 * The card placeholders, in the project that can see a render (story c4-3).
 *
 * WHAT THIS FILE CAN AND CANNOT PROVE, stated first because an undeclared limit reads as
 * coverage. jsdom has **no layout engine and applies no stylesheet**: `getComputedStyle(el)
 * .aspectRatio` returns the empty string here and an assertion on it PASSES FOR THE WRONG
 * REASON — the sixth time this epic has recorded that trap (c2-2 AC 17, c2-5 AC 4, c2-6 AC 4/5,
 * c2-7 AC 21, c2-8 AC 21). So AC 1/2/4's geometry is split across two instruments and neither
 * claims the other's ground:
 *
 *   **here** — the rendered element CARRIES the `card-shape` class, and writes no geometry of
 *   its own;
 *   **`tests/token-usage.test.ts`** — that class, in `src/styles/card-geometry.css`, declares
 *   `aspect-ratio: 63 / 88` and `border-radius: var(--radius-card)`, exactly once in the tree.
 *
 * Neither is a pixel. **That the 63:88 box actually looks like a card, at the 176px grid floor,
 * with a 141-character name in it, is Task 6's eye-check** and its outcome is in the story
 * record — not here, and not implied by a green suite.
 *
 * THE FIXTURES ARE REAL ROWS from the shipped corpus, read at `2a64231`, because the population
 * this component exists for is small and strange: all **79** cards that permanently need the
 * named variant are `'Card // Card'` reversible printings with a **blank** `mana_cost` and a
 * doubled name, so the name-only rendering is not an edge case — it is the only permanent case.
 */

import { act, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import { hydrateCard, resetCardCache, seedDeckCards, useCardEntry } from '../../state/cards'
import { PLACEHOLDER_FOR_REASON } from '../StatePanel/states'
import { CardPlaceholder, CARD_ID_PREFIX_LENGTH } from './CardPlaceholder'
import { UNKNOWN_CARD_LABEL } from './copy'

/**
 * One of the 79, verbatim: `b3a40e8e-…` is `Asmoranomardicadaistinaculdacar //
 * Asmoranomardicadaistinaculdacar`, blank cost, `'Card // Card'` type line. Its name is 66
 * characters — the longest in that population — and its halves are IDENTICAL, which is exactly
 * why it cannot be the fixture for the split question below.
 */
const NO_IMAGE_CARD = {
  id: 'b3a40e8e-9c30-4d8b-a2db-1aa9dd97f0ae',
  name: 'Asmoranomardicadaistinaculdacar // Asmoranomardicadaistinaculdacar',
  cost: '',
  typeLine: 'Card // Card',
}

/**
 * A card whose two faces have DIFFERENT names — `Heaven // Earth`, a real printing.
 *
 * c4-2's probe (b) is the reason this fixture is chosen and named: **2,246 of the corpus's
 * 3,194 split-named cards are `X // X`**, so a fixture drawn from the 79 would produce identical
 * output whether the name were split to its front face or not. It could not discriminate the
 * rule it appeared to test.
 */
const SPLIT_CARD = {
  id: 'b0bd107d-3915-4177-aa02-9106f3abbd86',
  name: 'Heaven // Earth',
  cost: '{X}{G} // {X}{R}{R}',
  typeLine: 'Instant // Sorcery',
}

describe('every variant is card-shaped, and none of them writes the shape (AC 1, 2, 4)', () => {
  it.each([
    ['named', <CardPlaceholder variant="named-card" name={NO_IMAGE_CARD.name} />],
    ['unknown', <CardPlaceholder variant="unknown-card" cardId={NO_IMAGE_CARD.id} />],
    ['the loading well', <CardPlaceholder variant="loading" />],
  ])('%s carries the one shared geometry class', (_label, element) => {
    const { container } = render(element)
    const root = container.firstElementChild

    expect(root).not.toBeNull()
    expect(root!.classList.contains('card-shape')).toBe(true)

    // AND WRITES NO GEOMETRY ITSELF. An inline style is the one place jsdom CAN see geometry,
    // and it is also the only way a component could smuggle a second aspect ratio past the
    // stylesheet guard. (eslint bans inline styles outright; this is the render-side proof that
    // the ban is not being worked around with `setAttribute`.)
    expect(root!.getAttribute('style')).toBeNull()
  })

  it('draws NO image of any kind — never a broken glyph, a 1x1 pixel or a card back (AC 6)', () => {
    // AD-11's non-negotiable, client half. `test_routes_card_image.py` holds the backend to the
    // same promise; this is the assertion that the SPA never invents one either. `<img>` with a
    // dead src is the failure this whole component exists to replace, so its absence is the
    // claim — not "the src is right".
    for (const element of [
      <CardPlaceholder variant="named-card" name={NO_IMAGE_CARD.name} />,
      <CardPlaceholder variant="unknown-card" cardId={NO_IMAGE_CARD.id} />,
      <CardPlaceholder variant="loading" />,
    ]) {
      const { container } = render(element)
      expect(container.querySelectorAll('img, svg, picture, canvas, object')).toHaveLength(0)
    }
  })
})

describe('the named variant — name, pips, type line (AC 5, 7, 13; Q5, Q9)', () => {
  it('renders the three parts in the order the design specifies', () => {
    const { container } = render(
      <CardPlaceholder
        variant="named-card"
        name={SPLIT_CARD.name}
        cost={SPLIT_CARD.cost}
        typeLine={SPLIT_CARD.typeLine}
      />,
    )

    expect(screen.getByText(SPLIT_CARD.name)).toBeVisible()
    expect(screen.getByText(SPLIT_CARD.typeLine)).toBeVisible()

    // PIPS ABOVE THE NAME (UX-DR22). DOM order is visual order — the stylesheet uses a flex
    // column with no `order` — so asserting the sequence here is asserting the layout that a
    // screen reader and a sighted reader both get.
    const parts = [
      ...container.querySelectorAll('.mana-cost, .card-placeholder-name, .card-placeholder-type'),
    ]
    expect(parts.map((node) => node.className)).toEqual([
      'mana-cost',
      'card-placeholder-name',
      'card-placeholder-type',
    ])
  })

  it('gets its pips from ManaCost — its FIRST consumer — and not a second parser', () => {
    const { container } = render(
      <CardPlaceholder variant="named-card" name={SPLIT_CARD.name} cost={SPLIT_CARD.cost} />,
    )

    // `{X}{G} // {X}{R}{R}` is five symbols and a separator across two faces. The count is
    // ManaCost's own contract (a total scanner that drops nothing), and reading it here is what
    // proves the cost went THROUGH that component rather than through something written here.
    expect(container.querySelectorAll('.mana-pip')).toHaveLength(5)
    expect(container.querySelector('.mana-cost-text')?.textContent).toBe(' // ')
  })

  it('announces the card name, and does NOT announce the cost twice (AC 13)', () => {
    const { container } = render(
      <CardPlaceholder variant="named-card" name={SPLIT_CARD.name} cost={SPLIT_CARD.cost} />,
    )

    // EXPERIENCE.md:157 — "Placeholders expose the same name to assistive tech". The name is
    // plain text, so it is announced by being read; nothing wraps it in a label.
    expect(screen.getByText(SPLIT_CARD.name)).toBeVisible()

    // The cost's accessible name is ManaCost's `role="img"`, built by `describeManaCost`. Exactly
    // one element carries it, and the placeholder wrapper carries NO name of its own — a second
    // `aria-label` here would make a screen reader read the cost, then read it again.
    const named = container.querySelectorAll('[aria-label]')
    expect(named).toHaveLength(1)
    expect(named[0].className).toBe('mana-cost')
    expect(container.firstElementChild!.getAttribute('aria-label')).toBeNull()
  })

  it('renders the name the payload carries, UNSPLIT (Q5)', () => {
    render(<CardPlaceholder variant="named-card" name={SPLIT_CARD.name} />)

    // THE FIXTURE IS `X // Y`, WHICH IS THE POINT. `Heaven // Earth` renders whole; a
    // `frontFace()` split would render `Heaven`, and the deck list, the detail panel and the alt
    // text would all still say `Heaven // Earth` — four surfaces, two names. Face-specific
    // rendering is c4-6's, where `CardFace` is already typed.
    expect(screen.getByText('Heaven // Earth')).toBeVisible()
    expect(screen.queryByText('Heaven')).toBeNull()
  })

  it('renders a `Card // Card` type line unchanged, because it is what the data says (Q9)', () => {
    render(
      <CardPlaceholder
        variant="named-card"
        name={NO_IMAGE_CARD.name}
        typeLine={NO_IMAGE_CARD.typeLine}
      />,
    )
    // 12 characters that carry no information, and suppressing them would mean writing a special
    // case for a string the corpus really contains — and making the ONLY permanent population of
    // this variant render differently from every other card.
    expect(screen.getByText('Card // Card')).toBeVisible()
  })

  it('is correct when two of its three parts are EMPTY — the only permanent case (AC 7)', () => {
    const { container } = render(
      <CardPlaceholder
        variant="named-card"
        name={NO_IMAGE_CARD.name}
        cost={NO_IMAGE_CARD.cost}
        typeLine={NO_IMAGE_CARD.typeLine}
      />,
    )

    expect(screen.getByText(NO_IMAGE_CARD.name)).toBeVisible()
    // NO EMPTY WRAPPER. `ManaCost` returns `null` for a blank cost, and the placeholder does not
    // wrap it in an element that survives its absence — a collapsed box inside a `gap`ped flex
    // column is a stray space with nothing in it.
    expect(container.querySelectorAll('.mana-cost')).toHaveLength(0)
    expect(container.firstElementChild!.children).toHaveLength(2)
  })

  it.each([
    ['undefined', undefined],
    ['null', null],
    ['empty', ''],
    ['whitespace-only', '   '],
  ])('renders NO name element for a %s name, and does not throw (AC 7)', (_label, name) => {
    // TOTALITY, IN THE SPELLING c4-2's REVIEW MEASURED. `DeckBadges` called `format.trim()`
    // behind a `!== null` check and threw `Cannot read properties of undefined` on a partial
    // deck: a presentation primitive that crashes the whole app on one absent prop is the FR-13
    // posture inverted. Whitespace is in this list because a `??` default fires only on
    // `undefined` — truthiness would leave a present, invisible, empty-announced element.
    const { container } = render(<CardPlaceholder variant="named-card" name={name} />)

    expect(container.querySelectorAll('.card-placeholder-name')).toHaveLength(0)
    expect(container.firstElementChild!.classList.contains('card-shape')).toBe(true)
  })

  it('survives a card with NO props at all rather than blanking the app', () => {
    const { container } = render(<CardPlaceholder variant="named-card" />)
    expect(container.firstElementChild!.children).toHaveLength(0)
    expect(container.firstElementChild!.classList.contains('card-placeholder')).toBe(true)
  })
})

describe('the unknown variant — two words and eight characters (AC 8, 9)', () => {
  it('reads exactly the artefact’s label', () => {
    render(<CardPlaceholder variant="unknown-card" cardId={NO_IMAGE_CARD.id} />)

    // The string is the copy module's, which `tests/unknown-card-copy.test.ts` holds to
    // EXPERIENCE.md byte-for-byte. Asserting the CONSTANT here rather than a literal is what
    // makes this test about the render and that one about the words.
    expect(screen.getByText(UNKNOWN_CARD_LABEL)).toBeVisible()
    expect(UNKNOWN_CARD_LABEL).toBe('Unknown card')
  })

  it('truncates the id to 8 characters, and the number carries its measurement (AC 9)', () => {
    const { container } = render(
      <CardPlaceholder variant="unknown-card" cardId={NO_IMAGE_CARD.id} />,
    )

    const shown = container.querySelector('.card-placeholder-id')!.textContent
    expect(shown).toBe('b3a40e8e')
    expect(shown).toHaveLength(CARD_ID_PREFIX_LENGTH)

    // THE ARITHMETIC, ASSERTED RATHER THAN TRUSTED. 8 is the uuid's first hyphen-delimited
    // group — the boundary a reader matches against a log line without counting characters —
    // and it was measured as the shortest prefix unique across all 38,261 corpus ids (6 collides
    // 45 times). The full 36 characters do not fit a 176px tile at any legible size.
    expect(NO_IMAGE_CARD.id.indexOf('-')).toBe(CARD_ID_PREFIX_LENGTH)
    expect(NO_IMAGE_CARD.id).toHaveLength(36)
  })

  it('trims a padded id BEFORE slicing, so the prefix is always 8 real characters', () => {
    // Review finding: the first `given()` validated on `trim()` but returned the padded
    // original, so `'  b3a40e8e…'.slice(0, 8)` rendered SIX real characters — a prefix the
    // measured uniqueness says collides 45 times. Reachable via the `invalid_request` route,
    // which is exactly the malformed-id population the unknown variant exists for.
    const { container } = render(
      <CardPlaceholder variant="unknown-card" cardId={`  ${NO_IMAGE_CARD.id}`} />,
    )

    expect(container.querySelector('.card-placeholder-id')!.textContent).toBe('b3a40e8e')
  })

  it.each([
    ['undefined', undefined],
    ['null', null],
    ['blank', '  '],
  ])('shows the label alone when the id is %s, never an empty line', (_label, cardId) => {
    const { container } = render(<CardPlaceholder variant="unknown-card" cardId={cardId} />)

    expect(screen.getByText(UNKNOWN_CARD_LABEL)).toBeVisible()
    expect(container.querySelectorAll('.card-placeholder-id')).toHaveLength(0)
  })

  it('carries no card NAME, and the type is what makes that true (AC 8, probe (d))', () => {
    // `<CardPlaceholder variant="unknown-card" name="Black Lotus" />` does not compile — the
    // props are a discriminated union and the unknown member has no `name`. That is the
    // copy-paste this epic's probe list calls "the one that type-checks", and here it does not;
    // the runtime half of the claim is that nothing but the label and the id is ever rendered.
    const { container } = render(<CardPlaceholder variant="unknown-card" cardId={SPLIT_CARD.id} />)

    expect(container.textContent).toBe(`${UNKNOWN_CARD_LABEL}b0bd107d`)
    expect(container.querySelectorAll('.mana-cost, .card-placeholder-type')).toHaveLength(0)
  })

  it('is reachable from every token states.ts maps to it, with no re-derivation here (AC 8, 16)', () => {
    // THE COUPLING, AT RUNTIME. `PLACEHOLDER_FOR_REASON`'s VALUES are the variants this
    // component must accept — `card_not_found` to `unknown-card`, both image tokens to
    // `named-card` — and this loop renders each one rather than trusting the type. A third key
    // added to `states.ts` fails `tsc` at the two asserts in CardPlaceholder.tsx; this is the
    // half that would notice a variant that type-checks but renders nothing.
    const variants = [...new Set(Object.values(PLACEHOLDER_FOR_REASON))]
    expect(variants.sort()).toEqual(['named-card', 'unknown-card'])

    for (const variant of variants) {
      const { container } = render(
        variant === 'unknown-card' ? (
          <CardPlaceholder variant="unknown-card" cardId={NO_IMAGE_CARD.id} />
        ) : (
          <CardPlaceholder variant="named-card" name={NO_IMAGE_CARD.name} />
        ),
      )
      expect(container.firstElementChild!.textContent.length).toBeGreaterThan(0)
    }
  })
})

describe('the loading well stays silent (AC 10, probe (e))', () => {
  it('renders no text, no children and no accessible name', () => {
    const { container } = render(<CardPlaceholder variant="loading" />)
    const well = container.firstElementChild!

    // "No copy. Wells stay silent" (EXPERIENCE.md:72), and silent means silent in the
    // ACCESSIBILITY TREE too — an empty well with a name is a screen reader announcing a
    // rectangle. Three independent ways of being silent, because any one of them alone could be
    // true by accident.
    expect(well.textContent).toBe('')
    expect(well.children).toHaveLength(0)
    expect(well.getAttribute('aria-label')).toBeNull()
    expect(well.getAttribute('title')).toBeNull()
    expect(well.getAttribute('aria-hidden')).toBe('true')

    // NO SPINNER, by the same reasoning as no text: the well IS the loading indication.
    expect(container.querySelectorAll('[role], [class*="spinner"]')).toHaveLength(0)
  })

  it('cannot be given anything to say — the API is the guarantee (Q8)', () => {
    // `<CardPlaceholder variant="loading" name="…" />` does not compile: the loading member of
    // the union has exactly one property. Q8 named this as the risk of choosing ONE component
    // with a variant over three components ("whether the well can ever accidentally take a
    // name"), and the discriminated union is the answer that makes it structural rather than a
    // convention. The runtime half: the well branch is taken before any prop is read.
    const { container } = render(<CardPlaceholder variant="loading" />)
    expect(container.firstElementChild!.className).toBe('card-shape card-placeholder-well')
    // The well is NOT `.card-placeholder` — it has no border and no overlay background, per
    // DESIGN.md:389 ("the same shape on {colors.surface-well} with no text").
    expect(container.firstElementChild!.classList.contains('card-placeholder')).toBe(false)
  })
})

/**
 * AC 15 — `useCardEntry`'s FIRST CONSUMER AND FIRST TEST (`deferred-work.md:3295`).
 *
 * The hook has shipped since c4-1 with nothing reading it. Its ledgered reason for being
 * untested — "the testing library is not installed" — was **false**, and c4-2 corrected it:
 * `@testing-library/react@^16.3.2` ships and `App.test.tsx` already uses it.
 *
 * **THE COMPONENT DOES NOT SUBSCRIBE; THE CALLER DOES (Q7).** A listed primitive may hold no
 * hook of any family, and that is a signal rather than a technicality — a component that reads
 * the store is a container, and it belongs in a different list with a different posture. So the
 * subscription lives at the call site, and `Tile` below is what c4-4's real tile will look like
 * where it touches this component: read the entry, branch on `entry.placeholder`, pass plain
 * props. **Nothing re-derives a placeholder from a wire token** (AC 16) — `entryFor` already
 * wrote that field, once, per entry.
 */
describe('consuming the cache without re-deriving it (AC 15, 16, 17, 18; Q7)', () => {
  beforeEach(() => {
    resetCardCache()
  })

  /**
   * c4-4's tile, in miniature: the whole mapping from a cache entry to a placeholder.
   *
   * THE ORDER IS THE CONTRACT (review finding — the first draft of this mapping got it wrong,
   * and the too-weak test beside it could not see that): after the two decided states, every
   * remaining entry carries a `summary` slot, and a STANDING SUMMARY ALWAYS RENDERS. That is
   * `cards.ts:150`'s *"whatever summary exists still stands"* made control flow — it holds for
   * a summary whose re-read is in flight, a summary whose read was refused for a reason that
   * decides nothing (`placeholder: null`, the 503), and a summary whose IMAGE is missing
   * (`placeholder: 'named-card'` — the named placeholder IS the render until c4-4 has an
   * `<img>` to put in front of it). Falling through to the well for any of those drops a name
   * the deck payload already supplied into a silent rectangle.
   */
  function Tile({ cardId }: { cardId: string }) {
    const entry = useCardEntry(cardId)

    if (entry === undefined) return <CardPlaceholder variant="loading" />
    if (entry.status === 'hydrated') {
      return (
        <CardPlaceholder
          variant="named-card"
          name={entry.card.name}
          cost={entry.card.mana_cost}
          typeLine={entry.card.type_line}
        />
      )
    }
    if (entry.status === 'unknown' && entry.placeholder === 'unknown-card') {
      return <CardPlaceholder variant="unknown-card" cardId={cardId} />
    }
    if (entry.summary !== null) {
      return (
        <CardPlaceholder
          variant="named-card"
          name={entry.summary.name}
          cost={entry.summary.mana_cost}
          typeLine={entry.summary.type_line}
        />
      )
    }
    return <CardPlaceholder variant="loading" />
  }

  const summaryOf = (card: typeof NO_IMAGE_CARD) => ({
    card_id: card.id,
    quantity: 1,
    sideboard: false,
    commander: false,
    card: {
      id: card.id,
      name: card.name,
      mana_cost: card.cost,
      cmc: 0,
      type_line: card.typeLine,
      oracle_text: '',
      colors: [] as string[],
      rarity: 'rare',
      set_code: 'tst',
      set_name: 'Test Set',
      collector_number: '1',
      oracle_id: 'oracle-1',
      color_identity: [],
      legalities: {},
      games: [],
    },
  })

  it('an id the cache has never seen renders the WELL, not an unknown card (AC 4 of c4-1)', () => {
    // `undefined` means "never seen", and it is the ONLY thing it means. Rendering "Unknown
    // card" for an id nobody has asked about yet would be the app claiming knowledge it has not
    // got — the distinction c4-1's union exists to make.
    const { container } = render(<Tile cardId={NO_IMAGE_CARD.id} />)
    expect(container.firstElementChild!.className).toContain('card-placeholder-well')
  })

  it('re-renders when the store changes, which is the whole contract of the hook', () => {
    render(<Tile cardId={NO_IMAGE_CARD.id} />)
    expect(screen.queryByText(NO_IMAGE_CARD.name)).toBeNull()

    // The seed is the free tier: `GET /api/deck/{id}` already embedded this summary, so no
    // request is made here or anywhere. The hook is a pure selector — it starts NOTHING — and
    // this is the assertion that it nevertheless notices.
    act(() => {
      seedDeckCards([summaryOf(NO_IMAGE_CARD)])
    })

    expect(screen.getByText(NO_IMAGE_CARD.name)).toBeVisible()
    expect(screen.getByText('Card // Card')).toBeVisible()
  })

  it('draws the unknown placeholder from entry.placeholder, never from the token (AC 16)', async () => {
    // A REAL REFUSAL THROUGH THE REAL PATH: `hydrateCard` with an injected reader, exactly as
    // c4-1 designed it for tests. No `fetch`, no stub of a global, no store write from here.
    render(<Tile cardId={NO_IMAGE_CARD.id} />)

    await act(async () => {
      await hydrateCard(NO_IMAGE_CARD.id, () =>
        Promise.resolve({ kind: 'error', reason: 'card_not_found' } as const),
      )
    })

    expect(screen.getByText(UNKNOWN_CARD_LABEL)).toBeVisible()
    expect(screen.getByText('b3a40e8e')).toBeVisible()
  })

  it('leaves a summary standing when the read fails for a reason that is NOT "unknown"', async () => {
    // `placeholder` is `null` for a 503: the read did not land, and whatever summary exists
    // still stands. Drawing "Unknown card" over a tile whose name the deck payload already
    // supplied would be a lie the summary tier can disprove — which is why the mapping reads
    // `entry.placeholder` rather than switching on `entry.reason`.
    render(<Tile cardId={NO_IMAGE_CARD.id} />)
    act(() => {
      seedDeckCards([summaryOf(NO_IMAGE_CARD)])
    })

    await act(async () => {
      await hydrateCard(NO_IMAGE_CARD.id, () =>
        Promise.resolve({ kind: 'error', reason: 'database_unavailable' } as const),
      )
    })

    // BOTH halves, and the second is the one that matters (review finding): asserting only the
    // label's ABSENCE passed against a mapping that dropped the summary into the silent well —
    // the well also shows no label. "Standing" means the NAME is on screen.
    expect(screen.queryByText(UNKNOWN_CARD_LABEL)).toBeNull()
    expect(screen.getByText(NO_IMAGE_CARD.name)).toBeVisible()
  })

  it('keeps the NAMED placeholder when only the image is missing — both tokens, the real path', async () => {
    // `no_image_data` / `image_fetch_failed` are the two tokens `entryFor` maps to
    // `placeholder: 'named-card'`, and until this test neither was ever driven through the
    // cache (review finding) — the one member of the fixed set with no end-to-end exercise,
    // and exactly the branch the first Tile mapping mishandled. The summary stands; the named
    // placeholder is the render until c4-4 has an <img>.
    render(<Tile cardId={NO_IMAGE_CARD.id} />)
    act(() => {
      seedDeckCards([summaryOf(NO_IMAGE_CARD)])
    })

    for (const reason of ['no_image_data', 'image_fetch_failed'] as const) {
      await act(async () => {
        await hydrateCard(NO_IMAGE_CARD.id, () =>
          Promise.resolve({ kind: 'error', reason } as const),
        )
      })
      expect(screen.queryByText(UNKNOWN_CARD_LABEL)).toBeNull()
      expect(screen.getByText(NO_IMAGE_CARD.name)).toBeVisible()
      expect(screen.getByText('Card // Card')).toBeVisible()
    }
  })
})
