import { Fragment, isValidElement, type ReactNode } from 'react'

/**
 * Whether a region prop actually renders anything.
 *
 * WHY THIS IS ITS OWN MODULE. `AppShell.tsx` may import from `react` only as a TYPE — a guard
 * in `ui/tests/shell.test.ts` asserts it, which is what closes the hook-aliasing evasion
 * (`import { useState as s }` never matches a name-keyed regex). Deciding whether a Fragment is
 * empty needs `Fragment` and `isValidElement`, which are VALUE imports. Rather than carve an
 * exception into a guard that was made blunt on purpose — this epic's standing lesson is that
 * the one exempted thing is where the next evasion lives — the logic moves here, and the
 * shell's import list grows by one explicit entry that the same guard still pins exhaustively.
 *
 * WHAT COUNTS AS EMPTY, and why each member is in the family. React renders nothing for:
 *
 *   `null` / `undefined` / booleans — `left={hasDeck && <CardGrid />}` passes `false` when
 *   there is no deck, which is the single most idiomatic conditional-render shape there is.
 *
 *   The empty string, and whitespace-only strings — `deckName=" "` renders an `h1` that is
 *   present in the DOM, invisible on screen, and announced as an empty heading: precisely the
 *   heading-less state Q3 exists to prevent, wearing a shape a `!== ''` check waves through.
 *
 *   An empty array, or one whose every element is itself empty — `left={cards.map(...)}` over
 *   an empty list. Empty of OUTPUT, not necessarily of elements.
 *
 *   Any other empty ITERABLE. A `Set`, a `Map`'s values, a generator: all legal React
 *   children, none of them arrays, and `Array.isArray` says no to every one.
 *
 *   An empty Fragment — `<></>`, or `<>{items}</>` over an empty list. This one is the reason
 *   the module exists: an empty Fragment is a React ELEMENT, so every check above says
 *   "filled" while the browser paints nothing.
 *
 * THE LIMIT, stated rather than discovered (the c2-4 ruling: a guard shipped without its limit
 * is worse than one shipped with it). `filled(<SomeComponent />)` is `true`, and
 * `SomeComponent` may still `return null`. Whether an arbitrary component renders anything is
 * not decidable without rendering it, so this function answers for the shapes where the
 * CALLER expresses emptiness — which is the realistic case — and not for the ones where a
 * child decides at render time. The overlay slot, where the consequence is a full-window
 * click-swallower rather than a missing placeholder, closes that residue in CSS instead:
 * `.app-shell-overlay:empty` is `display: none`, so a wrapper whose child rendered nothing
 * cannot intercept a pointer.
 */
export const filled = (content: ReactNode): boolean => {
  if (content == null || typeof content === 'boolean') return false
  if (typeof content === 'string') return content.trim() !== ''
  // `0` renders as "0" — a number is always content, and `!content` would have dropped it.
  if (typeof content === 'number' || typeof content === 'bigint') return true

  if (Array.isArray(content)) return content.some((child) => filled(child as ReactNode))

  if (typeof content === 'object' && Symbol.iterator in content) {
    // ONE-SHOT ITERATORS ARE NOT INSPECTED — they are CONSUMED by inspection, and a value read
    // here is a value React never gets. A generator returns ITSELF from `[Symbol.iterator]()`;
    // an array, a Set or a Map returns a FRESH cursor each time. That identity check is the
    // whole discriminator, and asking for the iterator does not advance either kind.
    //
    // Measured (Greptile, PR #23): spreading a generator here rendered the region EMPTY and
    // dropped its placeholder too — strictly worse than not looking. React already warns that
    // iterators are unsupported as children for exactly this reason, so the honest answer is
    // "assume filled": it preserves whatever the caller passed, and if the generator does turn
    // out to be empty, `.app-shell-overlay:empty` still stops the wrapper intercepting clicks.
    const iterable = content as Iterable<ReactNode>
    if (iterable[Symbol.iterator]() === (content as unknown)) return true
    return [...iterable].some(filled)
  }

  if (isValidElement(content) && content.type === Fragment) {
    return filled((content.props as { children?: ReactNode }).children)
  }

  return true
}
