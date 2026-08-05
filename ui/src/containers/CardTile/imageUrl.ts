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
 * The renders `GET /api/card-image/{scryfall_id}` will serve (story c4-5).
 *
 * The route's own `size` enum, verbatim from the committed `openapi.json` — six values, with
 * `normal` as the default. A LOCAL union rather than a wire alias, and that is the correct
 * spelling rather than a shortcut: `size` is a QUERY PARAMETER with an inline enum, not a named
 * entry in `components.schemas`, so there is nothing in `src/api/schema.ts` to alias and
 * `tests/wire-contract.test.ts` (which derives its ban from the schema keys) has nothing to say
 * about it. The day the backend adds a seventh render, this union is where it lands.
 *
 * Only two members have a caller today — `normal` by omission (the grid) and `large` (the detail
 * panel) — and the other four are here because the route publishes them, not because anything
 * predicts a use for them.
 */
export type CardImageSize = 'small' | 'normal' | 'large' | 'png' | 'art_crop' | 'border_crop'

/**
 * Where the browser should ask for a card's picture.
 *
 * **`size` is OPTIONAL AND STILL UNSPELLED BY DEFAULT** — this story added the parameter and
 * deliberately did not change what the grid emits. `normal` is the route's own default
 * (`images.py::DEFAULT_IMAGE_SIZE`) and it is the grid's size (FR-19), so spelling it would
 * restate a decision that already has one home — and, the sharper reason, **the URL is the
 * browser's cache key**: `/api/card-image/{id}` and `/api/card-image/{id}?size=normal` are two
 * entries for one picture, in a cache whose whole value here is that it is warm. So the
 * no-argument call is byte-identical to what c4-4 shipped, and `CardTile.test.tsx`'s assertion
 * that it contains no `size=` still passes unmodified.
 *
 * **The consequence for c4-5, stated because it is counter-intuitive:** `?size=large` IS a
 * different cache key, so the detail art is COLD on first inspection even when the grid is
 * fully warm. The panel is not re-using the tile's bytes and was never going to; what it gets
 * from the shared route is the backend's disk cache (c3-7) and a year-long `Cache-Control` on
 * the second look at the same card.
 *
 * **ONE FUNCTION, NOT A SECOND TEMPLATE STRING.** This is the split `react-refresh` forced and
 * this module's header predicted: *"the split it forces is the one that lets c4-5 (a larger
 * detail render) and c4-6 (`face=1`) extend ONE builder rather than each writing a second
 * template string."* **c4-6 adds `face` here**, beside `size`, and inherits the encoding below
 * for free.
 *
 * **`encodeURIComponent`, for c4-1's Q5 reason.** The id comes out of `deck_cards`, a column
 * with no shape constraint, so a stray `/` or `?` in one would silently address a DIFFERENT
 * route rather than producing the refusal a tile can draw. Measured at c3-2: a malformed id
 * sent to a backend with no database answers `database_not_initialized`, not `invalid_request`,
 * so "it will just 400" was never true either. The `size` value needs no encoding of its own —
 * it is a closed union of `[a-z_]` literals, which the type is what guarantees.
 *
 * Args:
 *   cardId: The Scryfall printing uuid, verbatim, as `DeckCardSummary.card_id` carries it.
 *   size: Which render to ask for. Omitted means the route's default, `normal`, with no query
 *     string at all — see above for why that is not the same as passing `'normal'`.
 *
 * Returns:
 *   A same-origin, absolute path. Never a CDN host — `tests/no-scryfall-hosts.test.ts` bans the
 *   host family across all of `src/`, and AD-11 is the rule it enforces.
 */
export const cardImageUrl = (cardId: string, size?: CardImageSize): string => {
  const path = `/api/card-image/${encodeURIComponent(cardId)}`
  return size === undefined ? path : `${path}?size=${size}`
}
