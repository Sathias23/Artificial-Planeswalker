/**
 * The card-image route, built where it is spent (FR-19, AD-11).
 *
 * ================= WHY IT IS NOT IN `src/api/client.ts` ================================
 *
 * That module is the ONE DOOR TO THE NETWORK, and `posture.test.ts` asserts the door list
 * exhaustively — `['src/api/client.ts']`. A path builder placed there would make that list read
 * as though images opened a second door, which they do not: an `<img src>` is a request the
 * BROWSER makes, through its own HTTP cache, and no code in `ui/src` ever holds the bytes. There
 * is no image cache in the SPA and there should not be one — the caches are the backend's disk
 * cache and `IMAGE_CACHE_CONTROL`'s `max-age=31536000, immutable`.
 *
 * ================= WHY IT IS NOT INSIDE `CardTile.tsx` EITHER ==========================
 *
 * MEASURED, not preferred: `react-refresh/only-export-components` is an ESLint error, and a
 * component module that also exports a helper breaks fast refresh for the whole file. The rule
 * is right, and the split it forces is what lets the detail render (`size=large`) and the flip
 * (`face=1`) extend ONE function rather than each writing a second template string.
 *
 * `imports: []` is the strongest available statement of what this module is: no react, no DOM,
 * no store, no fetch — a string, from a string.
 */

/**
 * The renders `GET /api/card-image/{scryfall_id}` will serve.
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
 * **`size` is OPTIONAL AND UNSPELLED BY DEFAULT**, deliberately. `normal` is the route's own
 * default (`images.py::DEFAULT_IMAGE_SIZE`) and it is the grid's size (FR-19), so spelling it
 * would restate a decision that already has one home — and, the sharper reason, **the URL is the
 * browser's cache key**: `/api/card-image/{id}` and `/api/card-image/{id}?size=normal` are two
 * entries for one picture, in a cache whose whole value here is that it is warm. So the
 * no-argument call is the bare path, and `CardTile.test.tsx` asserts that it contains no
 * `size=`.
 *
 * **The consequence for the detail panel, stated because it is counter-intuitive:** `?size=large`
 * IS a different cache key, so the detail art is COLD on first inspection even when the grid is
 * fully warm. The panel is not re-using the tile's bytes and was never going to; what it gets
 * from the shared route is the backend's disk cache and a year-long `Cache-Control` on the
 * second look at the same card.
 *
 * **ONE FUNCTION, NOT A SECOND TEMPLATE STRING.** `face` sits beside `size` and inherits the
 * encoding below for free, which is the split `react-refresh` forced paying for itself.
 *
 * **`face` IS THE SAME RULE AS `size`, ONE NOTCH SHARPER.** `0` is the
 * route's own default (`images.py`'s `face: integer, minimum 0, default 0`) and it is what every
 * unflipped tile carries — so where an unspelled `size` protects one cache entry, an unspelled
 * `face` protects the WHOLE GRID: every tile passes its index unconditionally, and 2,027 of 2,027
 * deck rows start at zero, so a builder that spelled the default would rewrite every image URL in
 * the app and throw away the warm browser cache on the commit that shipped a flip control. Hence
 * the guard below is `> 0` rather than `!== undefined`, and `CardTile.test.tsx` asserts
 * `cardImageUrl('x', undefined, 0) === cardImageUrl('x')` byte-for-byte.
 *
 * **It is validated rather than trusted, and that is not defensiveness.** Unlike `size`, whose
 * closed union of `[a-z_]` literals is guaranteed by the TYPE, `face` is a `number` that arrives
 * from a STORE — so `NaN`, `-1` and `1.5` are all expressible by arithmetic going wrong upstream,
 * and each of them would ask the route for a `404 no_image_data` in a query string that then
 * poisons a cache entry. `Number.isInteger` plus `> 0` is the whole of it, and it collapses the
 * invalid cases onto the front face, which is the only render that is always available.
 *
 * **`face` indexes the images a card HAS, not its `card_faces` array** (`resolve_face_images`,
 * AD-11). A split or adventure card has two faces and ONE image, so `face=1` on it is
 * `404 no_image_data` — *out of range*, not "the other half". Nothing in the SPA ever asks:
 * `FlipControl` renders only where every face carries its own `image_uris`, which is the same
 * predicate the resolver applies, and it is the reason this parameter can be indexed safely at
 * all.
 *
 * **`encodeURIComponent`, always.** The id comes out of `deck_cards`, a column with no shape
 * constraint, so a stray `/` or `?` in one would silently address a DIFFERENT route rather than
 * producing the refusal a tile can draw. Measured: a malformed id
 * sent to a backend with no database answers `database_not_initialized`, not `invalid_request`,
 * so "it will just 400" was never true either. The `size` value needs no encoding of its own —
 * it is a closed union of `[a-z_]` literals, which the type is what guarantees.
 *
 * Args:
 *   cardId: The Scryfall printing uuid, verbatim, as `DeckCardSummary.card_id` carries it.
 *   size: Which render to ask for. Omitted means the route's default, `normal`, with no query
 *     string at all — see above for why that is not the same as passing `'normal'`.
 *   face: Which of the card's IMAGES to ask for, zero-based. Omitted, `0`, or anything that is not
 *     a positive integer all mean the front face and spell nothing — see above.
 *
 * Returns:
 *   A same-origin, absolute path. Never a CDN host — `tests/no-scryfall-hosts.test.ts` bans the
 *   host family across all of `src/`, and AD-11 is the rule it enforces.
 */
export const cardImageUrl = (cardId: string, size?: CardImageSize, face?: number): string => {
  const path = `/api/card-image/${encodeURIComponent(cardId)}`
  // Built as a list so the two parameters compose without a nested ternary and so their ORDER is
  // stable: `?size=large&face=1` is one cache key and `?face=1&size=large` would be a second for
  // the same picture, which is the failure the unspelled defaults above exist to avoid.
  const query = [
    size === undefined ? null : `size=${size}`,
    face !== undefined && Number.isInteger(face) && face > 0 ? `face=${face}` : null,
  ].filter((parameter) => parameter !== null)

  return query.length === 0 ? path : `${path}?${query.join('&')}`
}
