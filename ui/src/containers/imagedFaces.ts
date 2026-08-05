import { useCardEntry } from '../state/cards'

/**
 * How many of a card's faces carry their own picture — the ONE predicate that decides whether a
 * printing can be flipped at all (story c4-6, AC 2, AC 13, Q9, AD-11).
 *
 * ================= WHY IT IS A MODULE OF ITS OWN AND NOT A LOCAL IN THE CONTROL ========
 *
 * Q5 rules that the *"does this card get a control?"* question is asked once, in `FlipControl`,
 * which returns `null` when the answer is no. That is still true of the QUESTION — but two
 * components need the ANSWER: the control, to decide whether to exist, and `CardTile`, to decide
 * whether to render a second stacked `<img>` for the back face (Q10). Two copies of a predicate
 * that mirrors a Python function is one copy that will be repaired and one that will not, which is
 * `useCardArt`'s own reason for existing.
 *
 * The precedent for a shared helper living at the ROOT of this tree rather than inside one member
 * is `src/components/filled.ts`, whose header states the rule: *"a helper shared by two components
 * does not live inside one of them"*. `useCardArt.ts` and `CardTile/imageUrl.ts` are the two
 * shipped instances; this is the third.
 *
 * ================= IT MIRRORS `resolve_face_images`, AND THE MIRROR IS EXACT ===========
 *
 * `src/companion/app/images.py:463`, verbatim:
 *
 * ```python
 * faces = list(card_faces or ())
 * per_face = [dict(face.image_uris) for face in faces if face.image_uris]
 * if per_face:
 *     return per_face
 * return [dict(image_uris)] if image_uris else []
 * ```
 *
 * Three things follow, and every one of them is a way to get this wrong:
 *
 *   **The discriminator is the TRUTHINESS of a per-face `image_uris`, never key presence.**
 *   `CardFace` serialises `"image_uris": null` on an unimaged face, so `'image_uris' in face` is
 *   `true` for all 368 split/adventure rows and all 79 placeholder rows — a predicate written that
 *   way puts a flip control on every split card in the corpus. The Python gate for the identical
 *   mistake is `test_routes_cards.py:253`.
 *
 *   **Python truthiness and JavaScript truthiness DISAGREE on `{}`**, and this is where a
 *   faithful-looking mirror stops being one: an empty dict is falsy in Python and an empty object
 *   is truthy in JavaScript. So the count below is keyed on the map having at least one KEY, which
 *   is what Python's `if face.image_uris` actually means. No row in the corpus carries an empty
 *   map today — all 5,556 per-face maps carry all six size keys — which makes this a guard against
 *   a future response rather than a fix for a present one.
 *
 *   **There is no `layout` anywhere, at any layer** (AD-11). The `cards` table has 23 columns and
 *   none of them is `layout`; `Card` has no such field; only 66 of 6,455 stored face objects carry
 *   one inside `CardFace`'s `extra="allow"` bag, and `test_images.py:156` proves the resolver
 *   ignores it. FR-04's PRD text still says "layout" and that is a PRD amendment owed
 *   (`epics-companion-app.md:323`), not a licence to switch on a string that is absent.
 *
 * ================= WHAT IT COUNTS, AND WHY THAT IS THE HONEST NUMBER (Q3, Q9) ==========
 *
 * It counts IMAGES, not faces, because `face=` on the image route indexes the list
 * `resolve_face_images` returns — a split card has two faces and ONE image, so `face=1` on it is
 * `404 no_image_data`, *out of range* rather than "the other half".
 *
 * Measured read-only at Task 0 against the shipped database: **0 partially imaged rows exist** —
 * a card's faces either all carry images or none do — so for every card that gets a control the
 * imaged count and `card_faces.length` coincide, which is the premise that lets `CardDetail` index
 * `card_faces` with the same integer it passes as `face=`. Whoever meets the first partially imaged
 * printing owns the ledger entry that is already open for it (`deferred-work.md:2765-2770`).
 *
 * Measured too, and it is the number that corrects the ledger: **every one of the 2,778 cards that
 * gets a control has exactly TWO imaged faces.** The 3- and 5-face cards `deferred-work.md:2032`
 * warns about are all split cards with ZERO imaged faces and no control.
 */

/**
 * How many pictures this printing has, as `GET /api/card-image/{id}?face=` would index them.
 *
 * **A NUMBER, derived AFTER the subscription.** The store subscription is `useCardEntry`'s
 * per-id entry selector; this hook filters and counts on the way out, so the derived value never
 * enters a zustand comparison at all (review 2026-08-06 corrected this paragraph, which first
 * claimed a returned array would "re-render its consumer forever" — that loop belongs to derived
 * objects returned from a SELECTOR, which is exactly why the derivation lives here, outside one).
 * The count stays a number anyway: it is the cheapest honest answer to the one question both
 * consumers ask, and the array never leaves.
 *
 * **It subscribes and starts nothing.** `useCardEntry` is a pure selector over a plain record
 * (c4-1 Q3): no effect, no request, no cleanup. A card nobody has hydrated yet reads `undefined`
 * and answers `0`, which is why a flip control materialises when the deck sweep lands rather than
 * at first paint — the residue Q1 declares, and the reason the sweep exists at all.
 *
 * Args:
 *   cardId: The Scryfall printing uuid.
 *
 * Returns:
 *   `0` for a card with no per-face pictures — which is 35,483 of the corpus's 38,261 rows, and
 *   every card that must NOT get a control (AC 2). `>= 2` is the flippable population.
 */
export const useImagedFaceCount = (cardId: string): number => {
  const entry = useCardEntry(cardId)
  // Only a HYDRATED entry can answer: `CardSummary` carries neither `card_faces` nor `image_uris`,
  // so the summary tier is silent here by construction rather than by omission. No `entry.reason`
  // and no `entry.placeholder` is read — an `unknown` entry simply has no card (c4-1 AC 13).
  const faces = entry?.status === 'hydrated' ? entry.card.card_faces : null
  if (!Array.isArray(faces)) return 0
  return faces.filter((face) => Object.keys(face.image_uris ?? {}).length > 0).length
}
