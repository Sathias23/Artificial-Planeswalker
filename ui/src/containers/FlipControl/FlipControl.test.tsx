import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Card, CardFace, CardSummary } from '../../api/schema'
import { resetCardCache, useCardStore } from '../../state/cards'
import {
  clearFocused,
  clearHovered,
  resetInspection,
  setFocused,
  setHovered,
  togglePin,
  useInspectionStore,
} from '../../state/inspection'
import { resetFaces, useFaceStore } from '../../state/faces'
import { FlipControl } from './FlipControl'
import { FLIP_LABEL } from './copy'

/**
 * The DFC flip control (story c4-6, AC 1–AC 8, AC 11, AC 13, AC 16, AC 17).
 *
 * ================= WHAT THIS SUITE CANNOT CARRY, SAID FIRST (AC 26) ====================
 *
 * jsdom has no layout engine, applies no stylesheet, evaluates no media query and loads no
 * images. Everything this file does NOT assert follows from those four facts, and each of them is
 * a Task 8 eye-check item rather than a coverage gap:
 *
 *   **THE 3D ROTATION IS NOT HERE AND CANNOT BE.** `transform-style: preserve-3d`,
 *   `backface-visibility` and a `rotateY` are all unevaluated in jsdom, and
 *   `getComputedStyle(el).transform` returns the empty string — which would PASS FOR THE WRONG
 *   REASON, the trap this epic has now recorded eight times. The motion is a SOURCE claim in
 *   `tests/token-usage.test.ts` (its selector must be registered `none !important`) plus Task 8.
 *
 *   **THE OPACITY IS NOT HERE.** `0.65` at rest, `1.0` on tile hover or focus, and the
 *   `--accent-bright` glyph tint on the control's own hover are three stylesheet claims about a
 *   property jsdom never computes. What IS asserted here is the CLASS the rules hang on.
 *
 *   **THE HIT BOX IS NOT HERE.** UX-DR47's ≥ 24 × 24 is a MEASUREMENT (AC 17), and
 *   `getBoundingClientRect` reports zeroes for everything in jsdom. The arithmetic is stated in
 *   `FlipControl.css` beside its DESIGN.md citation and measured in a real browser at Task 8.
 *
 *   **THE FLIP AS A SCREEN READER ANNOUNCES IT.** `aria-pressed` is asserted as an attribute
 *   below; how a real reader phrases "Flip card, pressed" is the epic manual-testing checklist's.
 *
 *   **THE WARM/COLD `?face=` RACE.** `?face=1` is a different browser-cache key, so the first
 *   flip of any card is always a cold fetch. jsdom fires no `load` and no `error`, so
 *   `useCardArt`'s re-arm is provable here only as "the `src` changed"; that the well appears and
 *   then clears is Task 8's.
 *
 * ================= THE FIXTURES ARE THE FOUR MEASURED SHAPES ===========================
 *
 * Re-measured read-only at Task 0 against the shipped database (38,261 cards):
 *
 *   A — top-level `image_uris`, no `card_faces`          35,036   ordinary card        no control
 *   B — top-level `image_uris` + faces with NO images        368   split / adventure    no control
 *   C — `image_uris` null, EVERY face carries its own      2,778   transform / MDFC    **control**
 *   D — `image_uris` null, faces present, images nowhere      79   named-placeholder    no control
 *
 * 0 rows carry both, and 0 rows are partially imaged. The predicate is the truthiness of per-face
 * `image_uris`, mirroring `resolve_face_images` — never `'image_uris' in face`, never
 * `card_faces !== null`, and never a layout string, because there is no layout data at any layer
 * (AD-11; the `cards` table has 23 columns and none of them is `layout`).
 */

const PATHWAY = 'clearwater-pathway'

const summary = (id: string): CardSummary => ({
  id,
  name: 'Clearwater Pathway // Murkwater Pathway',
  mana_cost: '',
  cmc: 0,
  type_line: 'Land // Land',
  oracle_text: '',
  colors: [],
  rarity: 'rare',
  set_code: 'znr',
  set_name: 'Test Set',
  collector_number: '1',
  oracle_id: 'oracle-1',
  color_identity: [],
  legalities: {},
  games: [],
})

const record = (id: string, over: Partial<Card> = {}): Card => ({
  ...summary(id),
  oracle_id: `oracle-${id}`,
  set_name: 'Zendikar Rising',
  collector_number: '260',
  color_identity: ['U', 'B'],
  legalities: {},
  games: ['paper'],
  ...over,
})

/** A per-face image map with all six size keys, which is what every real one carries (measured). */
const IMAGES = {
  small: 's',
  normal: 'n',
  large: 'l',
  png: 'p',
  art_crop: 'a',
  border_crop: 'b',
}

const face = (name: string, over: Partial<CardFace> = {}): CardFace => ({
  name,
  mana_cost: '{U}',
  type_line: 'Land',
  oracle_text: '{T}: Add {U}.',
  image_uris: null,
  ...over,
})

/** Put a hydrated record in the cache. `hydrateCard` returns from one of these without asking. */
const hydrate = (id: string, over: Partial<Card>) => {
  useCardStore.setState((state) => ({
    cards: { ...state.cards, [id]: { status: 'hydrated', card: record(id, over) } },
  }))
}

/** Shape C — the only shape that gets a control. */
const hydrateFlippable = (id = PATHWAY) =>
  hydrate(id, {
    image_uris: null,
    card_faces: [
      face('Clearwater Pathway', { image_uris: IMAGES }),
      face('Murkwater Pathway', { image_uris: IMAGES }),
    ],
  })

afterEach(() => {
  resetCardCache()
  resetFaces()
  resetInspection()
})

describe('who gets a control, and who does not (AC 1, AC 2)', () => {
  it('renders one for a card whose every face carries its own images — shape C', () => {
    hydrateFlippable()
    render(<FlipControl cardId={PATHWAY} />)

    const control = screen.getByRole('button', { name: FLIP_LABEL })
    expect(control).toBeVisible()
    // A REAL `<button>` (UX-DR47, unconditional) — not a `tabIndex` on a div, which
    // `jsx-a11y/no-static-element-interactions` makes an ESLint error. It is focusable by BEING a
    // button, so nothing sets `tabindex` and nothing needs to (AC 8's mechanism).
    expect(control.tagName).toBe('BUTTON')
    expect(control.getAttribute('type')).toBe('button')
    expect(control.getAttribute('tabindex')).toBeNull()
  })

  it.each([
    [
      'shape A — an ordinary single-faced card (35,036 rows)',
      { image_uris: IMAGES, card_faces: null },
    ],
    [
      'shape B — a split / adventure / Omen, whose halves SHARE one artwork (368 rows)',
      { image_uris: IMAGES, card_faces: [face('Murderous Rider'), face('Swift End')] },
    ],
    [
      'shape D — faces present and images nowhere (79 rows)',
      { image_uris: null, card_faces: [face('A'), face('B')] },
    ],
  ])('renders NOTHING for %s', (_label, over) => {
    hydrate(PATHWAY, over)
    const { container } = render(<FlipControl cardId={PATHWAY} />)
    expect(container.firstChild).toBeNull()
  })

  it('reads TRUTHINESS of the map and not the presence of the key (AC 2, AC 27)', () => {
    // THE EVASION THIS TEST EXISTS FOR. `CardFace` serialises `"image_uris": null` on an unimaged
    // face — the key is THERE — so `'image_uris' in face` is `true` for all 368 shape-B rows and
    // all 79 shape-D rows, and a predicate written that way would put a flip control on every
    // split card in the corpus. The Python gate for the identical mistake is
    // `test_routes_cards.py:253`'s `any(face["image_uris"] for face in body["card_faces"] or [])`.
    const explicitlyNull = [face('A', { image_uris: null }), face('B', { image_uris: null })]
    expect(explicitlyNull.every((f) => 'image_uris' in f)).toBe(true)

    hydrate(PATHWAY, { image_uris: null, card_faces: explicitlyNull })
    const { container } = render(<FlipControl cardId={PATHWAY} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders NOTHING for a PARTIALLY imaged card — one picture is not a flip (probe (c))', () => {
    // ADDED BECAUSE AN EVASION PROBE PASSED, AND RECORDED RATHER THAN QUIETLY FIXED (AC 27).
    // Probe (c) weakened the predicate from `imagedFaces < 2` to `imagedFaces < 1` and the WHOLE
    // SUITE STAYED GREEN — because no fixture had a card with EXACTLY ONE imaged face, so the
    // difference between "has pictures" and "has pictures to flip BETWEEN" was never exercised.
    // Measured read-only: 0 such rows exist today (a card's faces either all carry images or none
    // do), which is precisely why the gap was invisible — and it is the population
    // `deferred-work.md:2765-2770` already has an open entry for, so it is latent rather than
    // impossible. A control on such a card would render and then flip to a `404 no_image_data`.
    hydrate(PATHWAY, {
      image_uris: null,
      card_faces: [face('Imaged', { image_uris: IMAGES }), face('Unimaged')],
    })
    const { container } = render(<FlipControl cardId={PATHWAY} />)
    expect(container.firstChild).toBeNull()
  })

  it('reads an EMPTY map as unimaged, which is where JS and Python disagree', () => {
    // MEASURED DIVERGENCE, mirrored deliberately. `resolve_face_images` filters on Python
    // truthiness, and `{}` is FALSY in Python and TRUTHY in JavaScript — so a `Boolean(image_uris)`
    // predicate would be a faithful-looking mirror that disagrees with the resolver on exactly
    // this value. The count is therefore keyed on the map having a KEY. No row in the corpus
    // carries an empty map today (all 5,556 carry all six size keys), which is what makes this a
    // guard rather than a fix.
    expect(Boolean({})).toBe(true)
    hydrate(PATHWAY, {
      image_uris: null,
      card_faces: [face('A', { image_uris: {} }), face('B', { image_uris: {} })],
    })
    const { container } = render(<FlipControl cardId={PATHWAY} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing for a card the app has not hydrated yet, and everything once it has', () => {
    // THE DECLARED RESIDUE OF Q1, ASSERTED RATHER THAN HIDDEN. `CardSummary` carries neither
    // `card_faces` nor `image_uris`, so between the grid's first paint and the deck sweep landing
    // there is a window in which a flippable tile has no control. The sweep (`hydrateDeckCards`,
    // fired from `App.tsx` after the DOM commit) is what closes it; the alternative that would
    // close it at render time is a wire-schema change with an MCP blast radius, priced in the
    // story record. The second half of this test is the closing.
    const { container, rerender } = render(<FlipControl cardId={PATHWAY} />)
    expect(container.firstChild).toBeNull()

    hydrateFlippable()
    rerender(<FlipControl cardId={PATHWAY} />)
    expect(screen.getByRole('button', { name: FLIP_LABEL })).toBeVisible()
  })

  it('renders nothing for a card whose read was REFUSED, without touching a wire token', () => {
    // An `unknown` entry has no `card`, so the predicate has no faces to count and answers 0. No
    // `switch (entry.reason)` and no read of `entry.placeholder` is involved — c4-1 AC 13's ban
    // holds here by construction rather than by discipline.
    useCardStore.setState((state) => ({
      cards: {
        ...state.cards,
        [PATHWAY]: {
          status: 'unknown',
          reason: 'card_not_found',
          placeholder: 'unknown-card',
          summary: null,
          retryable: false,
        },
      },
    }))
    const { container } = render(<FlipControl cardId={PATHWAY} />)
    expect(container.firstChild).toBeNull()
  })
})

describe('what it looks like, to the extent jsdom can see it (AC 3, AC 4)', () => {
  it('carries the class its chrome hangs on', () => {
    hydrateFlippable()
    render(<FlipControl cardId={PATHWAY} />)
    // A CLASS, not a computed style — jsdom applies none. The material (scrim, `blur(6px)`,
    // `1px solid var(--border-strong)`, `--radius-pill`, 0.65 → 1.0) is a source claim in
    // FlipControl.css and an eye-check at Task 8.
    expect(screen.getByRole('button', { name: FLIP_LABEL })).toHaveClass('flip-control')
  })

  it('draws a STROKE glyph that is hidden from the accessibility tree (AC 4, UX-DR7)', () => {
    hydrateFlippable()
    const { container } = render(<FlipControl cardId={PATHWAY} />)
    const svg = container.querySelector('svg')!

    // The first inline `<svg>` in `ui/src`. `aria-hidden` because the control's name is the
    // authored one on the button — a named glyph would be the name announced twice.
    expect(svg.getAttribute('aria-hidden')).toBe('true')
    // STROKE-BASED, and asserted rather than described: DESIGN.md asks for "a stroke-based
    // two-arrow rotate glyph … a plain UI glyph, never anything that could read as a mana or set
    // symbol". A FILLED mark is what a mana pip and a set symbol both are, so `fill="none"` is
    // the structural half of "could never read as one" (UX-DR7).
    expect(svg.getAttribute('fill')).toBe('none')
    expect(svg.getAttribute('stroke')).toBe('currentColor')
    // …and it is TWO arrows: two arcs and two arrowheads, four subpaths.
    expect(container.querySelectorAll('svg path')).toHaveLength(4)
    // No `<circle>`, `<rect>` or `<ellipse>`: a closed circle IS the shape of a mana pip, which
    // `ManaPip` already means something else by in this app.
    expect(container.querySelectorAll('svg circle, svg rect, svg ellipse')).toHaveLength(0)
    // The glyph contributes no text, so it cannot join any accessible name.
    expect(svg.textContent).toBe('')
  })

  it('smuggles no authored copy anywhere but the one attribute that owns it (AC 4)', () => {
    hydrateFlippable()
    const control = (render(<FlipControl cardId={PATHWAY} />), screen.getByRole('button'))

    // `copy-rules.test.ts`'s attribute half collects every literal reaching `aria-label`, `title`
    // and eight others. This control writes exactly one of them, from `./copy` — which is why
    // that module joins COPY_MODULES and this one does not.
    expect(control.getAttribute('aria-label')).toBe(FLIP_LABEL)
    expect(control.getAttribute('title')).toBeNull()
    expect(control.getAttribute('aria-description')).toBeNull()
    expect(control.textContent).toBe('')
  })
})

describe('what a click does, and what it must never do (AC 6, AC 7, AC 11)', () => {
  it('advances the face, and a second click brings it back', () => {
    hydrateFlippable()
    render(<FlipControl cardId={PATHWAY} />)
    const control = screen.getByRole('button', { name: FLIP_LABEL })

    fireEvent.click(control)
    expect(useFaceStore.getState().faces[PATHWAY]).toBe(1)

    fireEvent.click(control)
    expect(useFaceStore.getState().faces[PATHWAY]).toBe(0)
  })

  it('is a toggle button, so the face is state rather than an announcement (AC 11, Q11)', () => {
    // UX-DR45 enumerates the live regions — the connection pill, the agent-view heading and the
    // panel's separate polite pin region — and a flip is not among them; c4-5's H4/C1 finding is
    // that transient changes must not flood the queue. `aria-pressed` gives a keyboard user the
    // state with no region and no second string, and the NAME stays static: a name that named the
    // target face would be card DATA in a read-aloud attribute, which rule 16 forbids.
    hydrateFlippable()
    render(<FlipControl cardId={PATHWAY} />)
    const control = screen.getByRole('button', { name: FLIP_LABEL })

    expect(control.getAttribute('aria-pressed')).toBe('false')
    fireEvent.click(control)
    expect(screen.getByRole('button', { name: FLIP_LABEL }).getAttribute('aria-pressed')).toBe(
      'true',
    )
    // The name did not move with the state — asserted, because `getByRole` above would still find
    // the control if it had.
    expect(screen.getByRole('button', { name: FLIP_LABEL })).toBeVisible()
  })

  it('A FLIP IS NOT AN INSPECTION — it touches none of the slice’s verbs (AC 6)', () => {
    // Stated twice in shipped source (`inspection.ts:43-54`, `CardTile.tsx:86-92`) and asserted
    // here against the SLICE rather than against a spy: a spy proves that a function this test
    // knew to watch was not called, while the store proves that NOTHING reached it by any route.
    hydrateFlippable()
    setHovered('some-other-card')
    togglePin('some-other-card')
    const before = useInspectionStore.getState()

    render(<FlipControl cardId={PATHWAY} />)
    fireEvent.click(screen.getByRole('button', { name: FLIP_LABEL }))

    expect(useInspectionStore.getState()).toEqual(before)
    expect(useFaceStore.getState().faces[PATHWAY]).toBe(1)
  })

  it('stops propagation, so a clickable ancestor never sees the click (AC 6)', () => {
    // The contract `CardTile.test.tsx` has asserted since c4-4, now proven on the real control.
    // Under the DOM shape Q2 ruled the control is a SIBLING of the tile's button, so nothing
    // bubbles there anyway — this is the guarantee that survives the control being mounted inside
    // something clickable, which is exactly what Epic 6's agent-view thumbnails will do.
    //
    // A REAL LISTENER ON A REAL ANCESTOR rather than a JSX `onClick` on a `<div>`, which
    // `jsx-a11y/no-static-element-interactions` makes an ESLint error — rightly, and the repair is
    // the honest one: what is being tested is DOM propagation, not a component that would itself
    // be an accessibility defect. This is the same shape `CardTile.test.tsx` uses to plant its
    // opt-out probe.
    //
    // ON `document.body`, AND THE FIRST SPELLING PUT IT ON RTL's `container` AND FAILED —
    // measured, not predicted. React 19 attaches its delegated listeners to the ROOT CONTAINER,
    // which is exactly that element, so a second listener on the SAME node still runs: only
    // `stopImmediatePropagation` stops a same-node sibling, and `stopPropagation` (correctly)
    // stops only ANCESTORS. `document.body` is a genuine ancestor of the React root, so it is the
    // node that actually tests the claim.
    hydrateFlippable()
    const onAncestorClick = vi.fn()
    document.body.addEventListener('click', onAncestorClick)
    try {
      render(<FlipControl cardId={PATHWAY} />)
      fireEvent.click(screen.getByRole('button', { name: FLIP_LABEL }))

      expect(onAncestorClick).not.toHaveBeenCalled()
      expect(useFaceStore.getState().faces[PATHWAY]).toBe(1)
    } finally {
      document.body.removeEventListener('click', onAncestorClick)
    }
  })

  it('…and the same click WITHOUT the control does reach that ancestor (the silent half)', () => {
    // The assertion above is about PROPAGATION rather than about the click never happening, and
    // this is what makes that distinction real: a plain button in the same position, with no
    // `stopPropagation`, does reach `document.body`.
    const onAncestorClick = vi.fn()
    document.body.addEventListener('click', onAncestorClick)
    try {
      render(<button type="button">plain</button>)
      fireEvent.click(screen.getByRole('button'))
      expect(onAncestorClick).toHaveBeenCalledTimes(1)
    } finally {
      document.body.removeEventListener('click', onAncestorClick)
    }
  })

  it('adds NO `onKeyDown` — Enter and Space are the browser’s (AC 7)', () => {
    // A real `<button>` turns both into a `click`, which is why there is no key handler to write
    // and why writing one would be the bug: a `keydown` handler beside the browser's own
    // activation fires the flip TWICE for one Space, landing back on the face it started from.
    // Asserted as SOURCE, because a jsdom `fireEvent.keyDown` does not synthesise the browser's
    // click and would pass whether or not a handler existed.
    hydrateFlippable()
    const { container } = render(<FlipControl cardId={PATHWAY} />)
    const control = container.querySelector('button')!

    fireEvent.keyDown(control, { key: 'Enter' })
    fireEvent.keyDown(control, { key: ' ' })
    expect(useFaceStore.getState().faces[PATHWAY]).toBeUndefined()

    // …and the click the browser WOULD synthesise does flip it, so the assertion above is about
    // the absence of a second handler rather than about the control being inert.
    fireEvent.click(control)
    expect(useFaceStore.getState().faces[PATHWAY]).toBe(1)
  })
})

describe('the same printing shows the same face everywhere it appears (AC 10)', () => {
  it('keeps two mounts of the control in step, because the state is not theirs', () => {
    // UX-DR15's "applies everywhere the printing appears", proven with the two mounts that exist
    // today — the tile's and the panel's — standing in for Epic 6's thumbnails. One store, two
    // readers: a `useState` in the control would make this test unwritable.
    hydrateFlippable()
    const first = render(<FlipControl cardId={PATHWAY} />)
    const second = render(<FlipControl cardId={PATHWAY} />)
    const controlIn = (r: ReturnType<typeof render>) => r.container.querySelector('button')!

    fireEvent.click(controlIn(first))

    expect(controlIn(first).getAttribute('aria-pressed')).toBe('true')
    expect(controlIn(second).getAttribute('aria-pressed')).toBe('true')
  })

  it('keys each printing separately — one card’s flip moves no other card', () => {
    hydrateFlippable(PATHWAY)
    hydrateFlippable('hengegate-pathway')
    const first = render(<FlipControl cardId={PATHWAY} />)
    const second = render(<FlipControl cardId="hengegate-pathway" />)
    const controlIn = (r: ReturnType<typeof render>) => r.container.querySelector('button')!

    fireEvent.click(controlIn(first))

    expect(controlIn(first).getAttribute('aria-pressed')).toBe('true')
    expect(controlIn(second).getAttribute('aria-pressed')).toBe('false')
  })
})

describe('the inspection slice is left entirely alone (AC 6, decide-once rule 15)', () => {
  it('does not clear a hover or a focus the tile around it has set', () => {
    // The mirror of the "flip is not an inspection" test: not only does the control not WRITE the
    // slice, it does not disturb what is already in it. Both transients and the pin survive a
    // flip, which is what makes flipping-then-reading one continuous motion.
    hydrateFlippable()
    setHovered(PATHWAY)
    setFocused(PATHWAY)
    render(<FlipControl cardId={PATHWAY} />)

    fireEvent.click(screen.getByRole('button', { name: FLIP_LABEL }))

    expect(useInspectionStore.getState().hoveredId).toBe(PATHWAY)
    expect(useInspectionStore.getState().focusedId).toBe(PATHWAY)

    clearHovered(PATHWAY)
    clearFocused(PATHWAY)
    expect(useFaceStore.getState().faces[PATHWAY]).toBe(1)
  })
})
