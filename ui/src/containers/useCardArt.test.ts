import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useCardArt } from './useCardArt'

/**
 * The art state machine's re-arming, at the hook (stories c4-4, c4-5, c4-6 Q7).
 *
 * ================= WHY THIS FILE EXISTS, AND IT IS AN EVASION PROBE'S DOING ============
 *
 * This module had no test of its own: its three states are exercised through `CardTile` and
 * `CardDetail`, which is the honest place for "the well shows before load" and "a failed image
 * becomes a placeholder". **c4-6's probe (g) proved that is not enough.** Reverting the hook's key
 * from `(cardId, face)` back to `cardId` alone — undoing Q7's whole repair — left the ENTIRE
 * SUITE GREEN, and the reason is a real interaction between two of this story's own rulings:
 *
 *   Q10 ruled the flip is TWO STACKED `<img>` ELEMENTS, so the tile and the panel each call this
 *   hook twice — once per face — and each call keeps its own state. The FRONT call's face is
 *   always `0` and the BACK call's face is always `1` for every printing that exists (all 2,778
 *   flip-control cards have exactly two imaged faces, measured). So neither consumer ever hands
 *   ONE hook instance a changed face, and the component tests could not see the key at all.
 *
 * The repair is still correct and still needed — the key is what makes the hook right for a card
 * with three imaged faces (where the back element's `face` really does move), and for any later
 * consumer that swaps faces in a single element rather than stacking them. But a guard whose
 * subject is invisible is not a guard, so the claim is asserted HERE, where the face can actually
 * be changed. Recorded rather than quietly fixed, per AC 27.
 *
 * ================= WHAT THIS CANNOT CARRY =============================================
 *
 * jsdom loads no images, fires no `load`/`error` and reports `naturalWidth: 0` always, so
 * `settleIfCached` is INERT here in both directions — the warm-cache race this module exists for
 * is a browser fact and is checked by eye at each story's Task 8. Events below are DISPATCHED
 * through the returned handlers, never awaited.
 */

describe('the verdict belongs to the PICTURE, which is a card AND a face (c4-6 Q7)', () => {
  it('starts in `loading` and settles on the handler it is given', () => {
    const { result } = renderHook(() => useCardArt('a-card'))
    expect(result.current.state).toBe('loading')

    act(() => result.current.onLoad())
    expect(result.current.state).toBe('shown')
  })

  it('re-arms when the CARD changes — c4-4’s repair, unchanged', () => {
    // A consumer handed a different card on the same mount would otherwise keep the old card's
    // `'shown'` (opacity 1 over pixels that have not arrived) or its `'failed'` (a placeholder for
    // a card whose picture is fine). That is the ordinary case in the detail panel, where ONE
    // mounted component shows a different card on every hover.
    const { result, rerender } = renderHook(({ id }) => useCardArt(id), {
      initialProps: { id: 'first-card' },
    })
    act(() => result.current.onError())
    expect(result.current.state).toBe('failed')

    rerender({ id: 'second-card' })
    expect(result.current.state).toBe('loading')
  })

  it('re-arms when the FACE changes and the card does NOT — c4-6’s repair (Q7)', () => {
    // THE ASSERTION PROBE (g) FOUND MISSING. `?face=1` is a different URL and therefore a
    // different browser-cache entry, so a face change is a new picture even though it is the same
    // card. Without it a consumer that swapped faces in ONE element would sit at `'shown'` over an
    // `<img>` whose new `src` had not arrived — the old face at full opacity, with no silent well.
    const { result, rerender } = renderHook(({ face }) => useCardArt('one-card', face), {
      initialProps: { face: 0 },
    })
    act(() => result.current.onLoad())
    expect(result.current.state).toBe('shown')

    rerender({ face: 1 })
    expect(result.current.state).toBe('loading')

    // …and the FAILED arm too, which is the half that matters most: a tile whose front art failed
    // renders a placeholder INSTEAD of the `<img>`, so a face change that did not re-arm would
    // leave a card whose other face is perfectly servable permanently unreachable.
    act(() => result.current.onError())
    expect(result.current.state).toBe('failed')
    rerender({ face: 2 })
    expect(result.current.state).toBe('loading')
  })

  it('does NOT re-arm when neither moved — a re-render is not a new picture', () => {
    // The silent half. `onError` fires once per `src`, and the backend answers a remembered
    // failure from memory for up to 300 s (c3-8): "a tile that retries in a loop will be answered
    // from memory and change nothing". A hook that re-armed on every render would restart that
    // loop on every parent update.
    const { result, rerender } = renderHook(({ face }) => useCardArt('one-card', face), {
      initialProps: { face: 1 },
    })
    act(() => result.current.onError())
    rerender({ face: 1 })
    expect(result.current.state).toBe('failed')
  })

  it('treats an omitted face as face 0, so every c4-4/c4-5 caller is unchanged', () => {
    // The default is what made this a one-line change for two existing consumers rather than an
    // edit to both. `useCardArt(id)` and `useCardArt(id, 0)` must be the same picture.
    const { result, rerender } = renderHook(
      ({ face }: { face?: number }) => useCardArt('one-card', face),
      { initialProps: {} },
    )
    act(() => result.current.onLoad())
    rerender({ face: 0 })
    expect(result.current.state).toBe('shown')
  })
})
