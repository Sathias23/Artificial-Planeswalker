/**
 * Which face of a double-faced card the app is showing — the fifth slice, and the SECOND whose
 * input is a person rather than the wire (story c4-6, FR-04, FR-19, UX-DR15, AD-11, AD-12).
 *
 * ================= THE SPINE SENTENCE, ALREADY NARROWED — THIS SLICE INHERITS IT =======
 *
 * `inspection.ts` narrowed AD-12's *"nothing else may write the store"* to *"nothing outside the
 * store writes **server-derived** state"*, in writing, when it became the first slice fed by a
 * hover. This slice is the second, and it needs no further narrowing: what it holds is **which
 * face a person chose to look at**, keyed by printing uuid. No request can answer it and no
 * response can contradict it. It carries no deck, no card record, no wire token and no error —
 * one non-negative integer per id, and nothing is ever sent anywhere.
 *
 * ================= WHY IT IS A STORE AND NOT REACT STATE IN THE TILE (Q4) ==============
 *
 * UX-DR15 asks for five things at once, and only a module-scope store satisfies all five:
 * *keyed by Scryfall printing uuid · per tab · in memory · resets on a page refresh · and applies
 * **everywhere the printing appears***. That last clause is the one a `useState` in `CardTile`
 * fails outright: the same printing is drawn by a grid tile and by the detail panel today, and by
 * Epic 6's agent-view thumbnails from c6-5 — three subtrees, two of which are not mounted inside
 * the first. A value that two subtrees must agree on is exactly what a store is for, which is the
 * argument `inspection.ts` makes for its own four ids.
 *
 * "Resets on a page refresh" is then free rather than implemented: module scope dies with the
 * document. There is no `localStorage`, no URL parameter and no cookie in this file, and
 * `tests/store-writes.test.ts` is the scan that keeps it that way.
 *
 * ================= IT IS **NOT** CLEARED ON A DECK REPLACEMENT, AND `deckMemory` IS =====
 *
 * These two rules sit three lines apart in the epic and point opposite ways, so both are written
 * down rather than one being inferred from the other:
 *
 *   **Inspection dies on a deck replacement** (`CardDetail`'s boards effect, via
 *   `./../containers/CardDetail/deckMemory`). A pin from deck A outranks deck B's cold-open
 *   target, so the panel would render a card that is not on the glass, with the live ring on no
 *   tile. The stale value is actively WRONG the moment the deck changes.
 *
 *   **A face index survives it**, and that is UX-DR15 read literally — *"flip state persists
 *   [across a `deck_changed` re-render], because a snap-back to the front face reads as a bug"*.
 *   The stale value is not wrong: it is keyed by PRINTING, and a printing that is not on the
 *   glass is simply not being drawn. When it comes back — the same card in the next deck, or the
 *   same deck after a refetch — the face the person chose is still the face they chose.
 *
 * The difference is not a preference, it is what each value MEANS: one names a place in a deck,
 * the other names a face of a card. {@link resetFaces} exists for tests, which is the only
 * context that genuinely has to forget.
 *
 * ================= WHAT THIS MODULE DELIBERATELY DOES NOT DO ===========================
 *
 * - **It does not know what a card IS.** The imaged-face count is an ARGUMENT to
 *   {@link flipCard}, computed by the one predicate in `FlipControl`, because a slice that read
 *   the card cache to find it would be a second place the `resolve_face_images` rule lives.
 * - **It publishes no array.** zustand v5 removed `create`'s equality argument and matches
 *   React's referential default, so a selector returning a filtered `CardFace[]` would return a
 *   new array on every call and re-render forever. {@link useFaceIndex} returns a NUMBER.
 * - **It fetches nothing and holds no timer**, and it renders nothing.
 */

import { create } from 'zustand'

/**
 * One non-negative integer per printing: which face is showing.
 *
 * **An ABSENT id means the front face**, and that is load-bearing rather than a convenience: the
 * front-face URL must stay byte-identical to the one c4-4 shipped (AC 13 — `face=0` is never
 * spelled, because a spelled default is a second browser-cache entry for a warm picture). Absent
 * and stored-`0` therefore have to resolve to the same value, which is what {@link useFaceIndex}'s
 * `?? 0` does. `??` and never `||`, for `inspection.ts`'s reason applied to a number: `0` is a
 * real face, not a falsy blank.
 */
export interface FaceState {
  readonly faces: Readonly<Record<string, number>>
}

/** The state before anything is flipped. Exported so tests can restore it. */
export const INITIAL_FACES: FaceState = { faces: {} }

/**
 * The slice. A **fifth** `create()` and still no second state library (AD-12) —
 * `useSystemStore`, `useDeckStore`, `useCardStore` and `useInspectionStore` are the other four,
 * and `tests/store-writes.test.ts`'s table names all five with their owners.
 *
 * One record rather than a flat map of ids, for `cards.ts`'s reason: a store's state must be an
 * object zustand can shallow-merge, and wrapping the map keeps `setState` replacing exactly one
 * field however many ids it holds.
 */
export const useFaceStore = create<FaceState>(() => INITIAL_FACES)

/**
 * Forget every flip. **For tests**, and for the reason `resetCardCache` and `resetInspection`
 * exist: the store is module-level, so a face left behind by one test is what the next one starts
 * from. `true` is the REPLACE flag — a merge would leave every previously flipped id in place and
 * make the reset a lie.
 *
 * It is deliberately **not** called on a deck transition; see the module header for why that is
 * the opposite of the inspection slice's rule and why both are right.
 */
export const resetFaces = (): void => {
  useFaceStore.setState(INITIAL_FACES, true)
}

/**
 * Show this printing's next face (AC 6, AC 13, Q3).
 *
 * **An INDEX cycled modulo the count, not a boolean toggle**, and the distinction is recorded
 * rather than defended as generality. Measured at Task 0 against the shipped corpus: **all 2,778
 * cards that get a flip control have exactly two imaged faces**, so this modulo is a two-state
 * toggle for every printing that exists today — and the ledger's warning that *"a `[front, back]`
 * destructuring is wrong for three real cards"* (`deferred-work.md:2032`) is corrected on the
 * record, because all three of those cards are split cards with ZERO imaged faces and no control.
 * The index is still the honest spelling: the route's `face` is an unbounded non-negative integer
 * over the list `resolve_face_images` returns, which is a list of IMAGES rather than of faces.
 *
 * **A count that cannot support a flip writes nothing at all.** `Number.isInteger` and an
 * explicit `<= 1` refusal, never `count &&` — the c2-7 decide-once ruling's family, one member
 * stricter: `isInteger` refuses everything `isFinite` refuses PLUS the fraction, which matters
 * here because a modulo by `1.5` is expressible arithmetic (review 2026-08-06 corrected this
 * sentence, which named `Number.isFinite` while the code below said `isInteger`): `x % 0`,
 * `x % NaN` and `x % 1.5` produce `NaN` or a fraction, and either would reach the wire as
 * `?face=NaN`. Refusing is a NO-OP rather than a correction, so a card already showing its back
 * face stays there: a snap to the front arriving from a guard is the same defect UX-DR15 names.
 *
 * Args:
 *   cardId: The Scryfall printing uuid — the same key `deck_cards.card_id`,
 *     `GET /api/cards/{card_id}` and `GET /api/card-image/{scryfall_id}` all carry.
 *   imagedFaceCount: How many of this card's faces carry their own `image_uris`, computed by the
 *     one predicate in `FlipControl` exactly as `resolve_face_images` computes it. Passed in
 *     rather than looked up, so the rule has one home (see the module header).
 */
export const flipCard = (cardId: string, imagedFaceCount: number): void => {
  if (!Number.isInteger(imagedFaceCount) || imagedFaceCount <= 1) return
  useFaceStore.setState((state) => ({
    faces: {
      ...state.faces,
      [cardId]: ((state.faces[cardId] ?? 0) + 1) % imagedFaceCount,
    },
  }))
}

/**
 * Which face this printing is showing — **0 for a card nobody has flipped** (AC 10, AC 13).
 *
 * A PRIMITIVE, so zustand v5's referential comparison re-renders exactly the components whose
 * number changed — the flipped tile and, when it is the inspection target, the detail panel —
 * rather than every tile in the grid on every flip. That is `useIsLiveTarget`'s argument in the
 * other slice, and the arithmetic is the same: a boolean or a number compares by value; an object
 * or an array does not.
 *
 * The same hook serves both mounts of the control and both surfaces that draw a face, which is
 * the whole of *"the same printing shows the same face everywhere it appears"* — there is one
 * answer and three readers, not three answers.
 */
export const useFaceIndex = (cardId: string): number =>
  useFaceStore((state) => state.faces[cardId] ?? 0)

/*
   THERE IS NO IMPERATIVE `readFaceIndex`, AND THAT IS A DECISION RATHER THAN AN OMISSION.
   `cards.ts` exports one because the inspection slice has to answer "is this card inspectable"
   inside an EVENT HANDLER, which is not a render. Nothing needs a face index outside a render:
   the three readers (the control's `aria-pressed`, the tile's `<img>` and the panel's face-first
   read) are all components, and `flipCard` computes the next index from the store itself rather
   than from a value a caller read first — which is what keeps two rapid clicks from both reading
   the same "current" face and advancing it once. Adding the reader before it has a caller would
   also hand a second module the two tokens `tests/store-writes.test.ts` scans for. */
