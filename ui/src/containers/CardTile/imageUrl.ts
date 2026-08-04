/**
 * The card-image route, built where it is spent (story c4-4, FR-19, AD-11).
 *
 * ================= WHY IT IS NOT IN `src/api/client.ts` ================================
 *
 * That module is the ONE DOOR TO THE NETWORK, and `posture.test.ts` asserts the door list
 * exhaustively — `['src/api/client.ts']`, still, with no edit in the first story that puts
 * remote images on the screen. A path builder placed there would make that list read as though
 * this story opened the door, which it does not: an `<img src>` is a request the BROWSER makes,
 * through its own HTTP cache, and no code in `ui/src` ever holds the bytes. There is no image
 * cache in the SPA and there should not be one — the caches are the backend's disk cache (c3-7)
 * and `IMAGE_CACHE_CONTROL`'s `max-age=31536000, immutable` (c3-5).
 *
 * ================= WHY IT IS NOT INSIDE `CardTile.tsx` EITHER ==========================
 *
 * MEASURED, not preferred: `react-refresh/only-export-components` is an ESLint error, and a
 * component module that also exports a helper breaks fast refresh for the whole file. The rule
 * is right, and the split it forces is the one that lets **c4-5** (a larger detail render) and
 * **c4-6** (`face=1`) extend ONE function rather than each writing a second template string.
 *
 * `imports: []` is the strongest available statement of what this module is: no react, no DOM,
 * no store, no fetch — a string, from a string.
 */

/**
 * Where the browser should ask for a card's picture.
 *
 * **`size` is deliberately NOT spelled.** `normal` is the route's own default
 * (`images.py::DEFAULT_IMAGE_SIZE`) and it is the grid's size (FR-19), so spelling it would
 * restate a decision that already has one home — and, the sharper reason, **the URL is the
 * browser's cache key**: two spellings of the same request are two entries in a cache whose
 * whole value here is that it is warm. A caller that genuinely needs another size or another
 * face adds a parameter to THIS function.
 *
 * **`encodeURIComponent`, for c4-1's Q5 reason.** The id comes out of `deck_cards`, a column
 * with no shape constraint, so a stray `/` or `?` in one would silently address a DIFFERENT
 * route rather than producing the refusal a tile can draw. Measured at c3-2: a malformed id
 * sent to a backend with no database answers `database_not_initialized`, not `invalid_request`,
 * so "it will just 400" was never true either.
 *
 * Args:
 *   cardId: The Scryfall printing uuid, verbatim, as `DeckCardSummary.card_id` carries it.
 *
 * Returns:
 *   A same-origin, absolute path. Never a CDN host — `tests/no-scryfall-hosts.test.ts` bans the
 *   host family across all of `src/`, and AD-11 is the rule it enforces.
 */
export const cardImageUrl = (cardId: string): string =>
  `/api/card-image/${encodeURIComponent(cardId)}`
