import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { flipCard, resetFaces, useFaceIndex, useFaceStore } from './faces'

/**
 * The face slice.
 *
 * ================= WHAT THIS SUITE CANNOT CARRY, SAID FIRST ============================
 *
 * Nothing here renders a tile, a panel or a control, so nothing here proves that CLICKING the
 * flip control advances a face — that is `FlipControl.test.tsx`'s wiring claim — and nothing here
 * proves the 3D rotation, which jsdom evaluates no CSS for at all. What this file proves is the
 * arithmetic: what an unflipped card reads as, what the modulo does at its boundary, and what a
 * count that cannot support a flip does.
 *
 * It also cannot prove the per-TAB half of UX-DR15. "Resets on a page refresh" is a property of
 * module scope in a browser, and a test file that imports the module is the one context where a
 * page refresh does not exist. What is asserted instead is the structural cause: the store is a
 * module-level `create()` with no storage, no URL and no cookie behind it — which is
 * `tests/store-writes.test.ts`'s scan, not this file's.
 */

// The store is module-scope, as stores are; without this the face a previous test left behind is
// what the next one starts from.
afterEach(resetFaces)

const PATHWAY = 'clearwater-pathway'

describe('an unflipped card reads as its front face (AC 13)', () => {
  it('answers 0 for an id it has never seen — absence IS the front face', () => {
    // `?? 0` and never `||`: the stored value 0 and the absent value must resolve identically,
    // because "flipped back to the front" and "never flipped" are the same face and the URL they
    // build must be the same byte string (`face=0` is never spelled).
    expect(useFaceStore.getState().faces[PATHWAY]).toBeUndefined()
    const { result } = renderHook(() => useFaceIndex(PATHWAY))
    expect(result.current).toBe(0)
  })

  it('holds nothing at all before anything is flipped', () => {
    expect(useFaceStore.getState().faces).toEqual({})
  })
})

describe('flipping advances the index modulo the IMAGED-face count (AC 13, Q3)', () => {
  it('goes front → back → front for the only shape that exists (2,778 of 2,778)', () => {
    // MEASURED against the corpus: every one of the 2,778 cards that gets a control has exactly
    // TWO imaged faces, so the modulo is a two-state toggle for every printing in the corpus. The
    // index is still the honest spelling — the route's `face` is an unbounded integer and the
    // resolved list is IMAGES, not faces — and the boundary below is what makes the toggle a
    // consequence of the rule rather than the rule itself.
    flipCard(PATHWAY, 2)
    expect(useFaceStore.getState().faces[PATHWAY]).toBe(1)

    flipCard(PATHWAY, 2)
    expect(useFaceStore.getState().faces[PATHWAY]).toBe(0)
  })

  it('wraps at the count rather than growing without bound (the modulo boundary)', () => {
    // Three imaged faces exists nowhere in the corpus today — the only 3- and 5-face cards are
    // split cards with ZERO imaged faces and no control (`Smelt // Herd // Saw`,
    // `There // They're // Their`, `Who // What // When // Where // Why`). The arithmetic is
    // asserted anyway, because the value indexes IMAGES and the route accepts any non-negative
    // integer: an index that ran past the count would ask for a `404 no_image_data`.
    for (const expected of [1, 2, 0, 1]) {
      flipCard(PATHWAY, 3)
      expect(useFaceStore.getState().faces[PATHWAY]).toBe(expected)
    }
  })

  it('keys each printing separately, so one flip never moves another card', () => {
    // UX-DR15: keyed by Scryfall printing uuid. Two Pathways in the same deck are two entries.
    flipCard(PATHWAY, 2)
    flipCard('hengegate-pathway', 2)
    flipCard('hengegate-pathway', 2)

    expect(useFaceStore.getState().faces[PATHWAY]).toBe(1)
    expect(useFaceStore.getState().faces['hengegate-pathway']).toBe(0)
  })
})

describe('a count that cannot support a flip does nothing (rule 10)', () => {
  it.each([
    ['one imaged face — a single-faced card', 1],
    ['zero imaged faces — the 79-card placeholder population', 0],
    ['a negative count', -2],
    ['a fraction', 1.5],
    ['NaN', Number.NaN],
    ['Infinity', Number.POSITIVE_INFINITY],
  ])('refuses %s, and writes nothing at all', (_label, count) => {
    // `Number.isInteger` and an explicit `<= 1` refusal, never `count &&` — one member stricter
    // than a plain finiteness check, because 1.5 is finite and a modulo by it is not.
    // `count && …` treats 0 as absent AND lets `NaN` through as falsy-but-not-absent, and a
    // modulo by 0, by NaN or by a fraction produces `NaN` or a fractional index, either of which
    // would reach a URL as `?face=NaN`. Writing NOTHING (rather than writing 0) is what keeps
    // "the store holds only cards a person actually flipped" true.
    flipCard(PATHWAY, count)
    expect(useFaceStore.getState().faces).toEqual({})
  })

  it('leaves an ALREADY flipped card where it is rather than resetting it', () => {
    // The refusal is a no-op, not a correction. A card that is showing its back face and is then
    // asked to flip with a nonsense count must not silently snap to the front — that is the
    // "snap-back reads as a bug" failure UX-DR15 names, arriving from the guard instead of from a
    // re-render.
    flipCard(PATHWAY, 2)
    flipCard(PATHWAY, 1)
    expect(useFaceStore.getState().faces[PATHWAY]).toBe(1)
  })
})

describe('the state survives what it must and is forgettable when it must be (AC 9)', () => {
  it('keeps every entry when `resetFaces` has NOT been called — including across re-reads', () => {
    // The store is the thing a `deck_changed` re-render does not touch: nothing in this module
    // subscribes to a deck, so there is no path by which a new deck could clear it. See the
    // module header for why that is the OPPOSITE of `deckMemory`'s rule for inspection, and why
    // both are right. The rendered half — a re-render over new boards, and an unmount — is
    // `CardTile.test.tsx`'s "survives a re-render over NEW BOARDS" test.
    flipCard(PATHWAY, 2)
    expect(useFaceStore.getState().faces[PATHWAY]).toBe(1)
    expect(useFaceStore.getState().faces[PATHWAY]).toBe(1)
  })

  it('forgets everything on `resetFaces`, replacing rather than merging', () => {
    // `setState(…, true)` — the replace flag. A merge would leave every previously flipped id in
    // place and make the reset a lie the next test would inherit, which is the exact failure
    // `resetCardCache` and `resetInspection` both exist to prevent.
    flipCard(PATHWAY, 2)
    resetFaces()
    expect(useFaceStore.getState().faces).toEqual({})
  })
})

describe('the selector is a PRIMITIVE, which is what keeps zustand v5 from looping', () => {
  it('returns a number, not a derived object or array', () => {
    // zustand v5 removed `create`'s equality argument and matches React's referential default, so
    // a selector returning a NEW object or array on every call re-renders forever. A number
    // compares by value and is correct by construction — which is why the count is derived at the
    // CALL SITE from the cached record rather than published from here as a `CardFace[]`.
    flipCard(PATHWAY, 2)
    const { result } = renderHook(() => useFaceIndex(PATHWAY))
    expect(result.current).toBe(1)
    expect(typeof result.current).toBe('number')
  })
})
