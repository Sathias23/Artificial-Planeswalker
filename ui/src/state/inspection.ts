/**
 * What the companion is currently showing in the card detail panel — the FIRST user-interaction
 * state in this codebase (story c4-5, FR-17, AD-12, UX-DR20, UX-DR22, UX-DR39).
 *
 * ================= THE SPINE SENTENCE, NARROWED IN THE OPEN (Q5, AC 3) =================
 *
 * `deck.ts` quotes the architecture spine verbatim: *"its state comes from exactly two inputs —
 * REST responses and WebSocket messages. Nothing else may write the store."* Four stories of
 * store writes have all come from a REST response or a poll tick, so that sentence has been
 * literally true until now. **A hovered or pinned card is a third kind of input**, and this is
 * the first story to introduce one — so the sentence is narrowed here, deliberately and in
 * writing, rather than quietly violated:
 *
 *   > Nothing outside the store writes **server-derived** state.
 *
 * The distinction is not a word game, and it is what keeps AD-12's guarantee intact. The
 * property AD-12 actually buys is *"the contents of the store are explainable from the network
 * alone"* — which is why `store-writes.test.ts` bans `localStorage`, the URL, a cookie and a
 * timer from the DECK slice by name. None of those is what this slice holds. What it holds is
 * **where the user is pointing**, which no request can answer and no response can contradict:
 * four card ids, all of them chosen by a person, none of them ever sent anywhere. It carries
 * no deck, no card record, no wire token and no error, and it is registered in `STORES` with
 * that reason so the narrowing has one address rather than being re-derived per story.
 *
 * The counterweight, argued rather than dodged: **c4-4's Q8 ruled that per-tile state must not
 * be lifted** — *"99 tiles sharing one loaded-set in the store is a store write this story is
 * not allowed to make"*. That ruling is about NINETY-NINE values, one per tile, each private to
 * the component that owns it. This is ONE value, read by components in two different subtrees
 * (the grid's tiles and the right column's panel) and, from Epic 6, by a third that is not
 * mounted inside either. A value two subtrees must agree on is precisely what a store is for.
 *
 * ================= IT LIVES AT MODULE SCOPE, AND THAT IS FR-17's OWN REQUIREMENT (Q6) ==
 *
 * `EXPERIENCE.md:90`: *"the pinned target survives closing the view"* — an agent view opens over
 * the deck, the user pins a suggestion row's card inside it, dismisses the view, and the detail
 * panel still shows that card. A module-level store satisfies that for free. A React context
 * scoped under the left column would not, and neither would state held by `CardDetail`, because
 * **c6-5**'s agent view is rendered in `AppShell`'s `overlay` slot — a different subtree that
 * mounts and unmounts. Recorded here so c6-7 inherits it rather than re-deciding it — and it
 * did: that story added no code for the survival at all, and pinned the behaviour end to end
 * instead (`App.test.tsx`, "ESC CLOSES THE VIEW AND THE PIN SET FROM A ROW SURVIVES").
 *
 * ================= THE API IS LOCATION-AGNOSTIC, ON PURPOSE (Q8, AC 4) =================
 *
 * Nothing below is named for a tile. **c4-7**'s deck rows, **c4-6**'s flip control (which must
 * touch NONE of this — a flip is not an inspection) and **c6-5..c6-8**'s agent-view thumbnails
 * are all consumers, and a `setHoveredTile` would have made two of the three read as a misuse of
 * something else's API. The verbs are what happens, not where.
 *
 * A consumer attaches {@link setHovered}/{@link clearHovered} (pointer),
 * {@link setFocused}/{@link clearFocused} (keyboard) and {@link togglePin} to its own
 * interactive element. **c4-6's flip control sits INSIDE the tile's `<button>` and suppresses
 * them with `stopPropagation`** — which works because the tile's handlers are on the button
 * itself and `click` bubbles to it. That contract is stated in `CardTile.tsx` too, so neither
 * story has to edit the other's handler.
 *
 * ================= ESC IS LAYERED, AND EPIC 6 WINS (Q12, AC 22) ========================
 *
 * UX-DR39: *"Esc closes the topmost thing (an open agent view first, then an active pin)."* This
 * story registers a document-level `keydown` in `CardDetail`, in the BUBBLE phase, that calls
 * {@link clearPin}. **The contract c6-5 relies on: the agent view registers its own `keydown` on
 * `document` in the CAPTURE phase, closes itself, and calls `stopPropagation()`** — capture at
 * the document runs before the bubble listener for every target, so a single Esc closes the view
 * and leaves the pin alone even when focus sits outside the overlay's subtree. (An
 * element-scoped handler could not hold this contract: a `keydown` targeting `<body>` never
 * passes through the overlay, so nothing scoped to it could pre-empt the document listener —
 * found at review, 2026-08-05.)
 *
 * **c6-5 BUILT THE OVERLAY, AND THE LAYERING IS COVERED.** This read *"no overlay exists yet, so
 * this story cannot test the layering"* until then. `AgentView.tsx` holds the capture half, and
 * `App.test.tsx`'s c6-5 block asserts one Esc closing a view while a real pin survives it —
 * over both live document listeners, in one app. The contract sentence above is unchanged;
 * what changed is that it is now enforced rather than only declared.
 *
 * ================= WHAT THIS MODULE DELIBERATELY DOES NOT DO ===========================
 *
 * - **It renders nothing** and imports no React component. `CardDetail` draws; this decides.
 * - **It fetches nothing.** {@link hydrateCard} is called by the panel when the target changes,
 *   because owning the request is the panel's job and the cache's, not this slice's.
 * - **It holds no deck.** The cold-open resolution takes `boards` as an ARGUMENT
 *   ({@link coldOpenTargetOf}) and the answer is written in, once, by the one consumer that has
 *   one.
 * - **It holds no timer, no storage and no URL parsing** — the three third inputs
 *   `store-writes.test.ts` bans from the deck slice, and the narrowing above is not a licence
 *   for any of them.
 */

import { create } from 'zustand'

import { readCardEntry } from './cards'
import type { DeckBoards } from './deckGroups'

/**
 * Four ids and a recency tag, in the order they win. All four ids are nullable and all four are
 * ordinary states.
 *
 * **Why the two transients are TWO SLOTS and not one** (PR #44 review, 2026-08-05 — found
 * independently by the edge-case layer and by Greptile as a P1). Hover and keyboard focus are
 * concurrent input modalities: a tile can hold visible keyboard focus while the pointer sweeps
 * other tiles. With one shared slot, a `mouseleave` erased a still-focused tile's target — the
 * panel and the live ring snapped to the cold-open card while a focus ring was still drawn on a
 * tile, which is UX-DR14's *"hover OR keyboard focus"* parity broken in the one case where both
 * are present at once. Two slots let each modality's clear take only its own target;
 * {@link lastTransient} is what resolves them when both hold one, because "whichever the person
 * used last" is the only answer that matches what the eye is doing in either direction.
 *
 * **Why THERE IS a `defaultId` and it lives here.** `defaultId` is the cold-open resolution, and
 * it has to live here rather than be threaded through the panel because the two consumers ask
 * different questions about the same answer: the panel asks {@link useInspectionTargetId} (no
 * argument, Q8) and a tile asks {@link useIsLiveTarget} without knowing what a deck is. With the
 * default outside the store, a tile could not tell it was the cold-open target, so the card the
 * panel is showing would carry no live ring until somebody touched it — one concept with two
 * resolutions, which is exactly the drift `deckGroups.ts` exists to prevent, one layer up.
 */
export interface InspectionState {
  /** Where the POINTER is. Cleared when it leaves the card (UX-DR14). */
  readonly hoveredId: string | null
  /** Where KEYBOARD FOCUS is — the other half of UX-DR14's parity. Cleared on blur. */
  readonly focusedId: string | null
  /**
   * Which transient wrote last — the recency that resolves mixed input. Written by the two
   * setters, deliberately untouched by the two clears: a clear is a modality LETTING GO, and
   * letting go says nothing about which modality the person is using.
   */
  readonly lastTransient: 'hover' | 'focus' | null
  /** A card fixed by a click or Enter. Outranks both transients until released (UX-DR20). */
  readonly pinnedId: string | null
  /**
   * The cold-open target: what the panel shows when nothing has been touched, so that it is
   * *"never empty while a deck is loaded"* (FR-17, UX-DR20). Written by the panel from
   * {@link coldOpenTargetOf}; `null` for a deck with no cards, which is c4-12's copy.
   */
  readonly defaultId: string | null
}

/** The state before a deck exists. Exported so tests can restore it between renders. */
export const INITIAL_INSPECTION: InspectionState = {
  hoveredId: null,
  focusedId: null,
  lastTransient: null,
  pinnedId: null,
  defaultId: null,
}

/**
 * The slice. A fourth `create()` and still no second state library (AD-12) — `useSystemStore`,
 * `useDeckStore` and `useCardStore` are the other three, and `store-writes.test.ts`'s table
 * names all four with their owners.
 *
 * A flat shape rather than `deck.ts`'s wrapped-union trick, because the failure that trick
 * closes cannot occur here: this store's shape is independent nullable primitives, so zustand's
 * shallow merge is exactly the semantics wanted — writing one leaves the others alone, which is
 * the whole of {@link togglePin} not disturbing a hover or a focus.
 */
export const useInspectionStore = create<InspectionState>(() => INITIAL_INSPECTION)

/**
 * Forget everything. **For tests**, and for the same reason `resetCardCache` exists: the store
 * is module-level, so a target left behind by one test is what the next one starts from.
 */
export const resetInspection = (): void => {
  useInspectionStore.setState(INITIAL_INSPECTION, true)
}

/**
 * Whether a card can be inspected at all (AC 17, UX-DR22).
 *
 * `EXPERIENCE.md:99`, verbatim: *"Placeholder tiles behave like normal tiles (inspection
 * contract) EXCEPT the unknown-card variant, which cannot be inspected — there is nothing to
 * show."*
 *
 * ==== WHY THE REFUSAL IS HERE AND NOT IN THE TILE ====================================
 * c4-4's grid never renders the unknown-card variant: an image failure draws the NAMED
 * placeholder, and 0 of 2,027 deck rows are dangling references, so a tile-side refusal would
 * have no population to refuse and no honest test. The population that really carries one is
 * **Epic 6's thumbnails**, whose ids do not come from a deck at all — and every one of those
 * reaches a target through the two verbs below. One refusal, at the one door, covering the
 * consumers that do not exist yet.
 *
 * ==== WHAT IT DOES **NOT** REFUSE, WHICH IS THE LOAD-BEARING HALF =====================
 * `undefined` means *"never seen"* and nothing else (c4-1 AC 4), so an unseen id is inspectable
 * — a slice that refused on absence would refuse every card on the first hover of a cold open,
 * before any hydration had run. And a card whose PICTURE failed (`no_image_data`,
 * `image_fetch_failed`, a 503) is inspectable: the app knows its name, cost, type line and
 * oracle text, and `entry.placeholder` is what tells the two apart WITHOUT this module ever
 * touching a wire token (c4-1 AC 13 — no `switch (entry.reason)` anywhere).
 */
const inspectable = (cardId: string): boolean => {
  const entry = readCardEntry(cardId)
  return !(entry?.status === 'unknown' && entry.placeholder === 'unknown-card')
}

/**
 * The transient the person used LAST, falling to the other while the last-used one holds
 * nothing. This is what makes mixed input resolve to what the eye is doing: a pointer that
 * leaves a card mid-Tab-sweep exposes the focused tile, and a focus that blurs mid-mouse-sweep
 * exposes the hovered one — in neither direction does one modality's letting-go erase the
 * other's target (PR #44 P1).
 */
const transientIdOf = (state: InspectionState): string | null =>
  state.lastTransient === 'focus'
    ? (state.focusedId ?? state.hoveredId)
    : (state.hoveredId ?? state.focusedId)

/**
 * Which card the panel is showing: **pin, else the last-used transient (hover/focus), else the
 * cold-open target** (AC 8, AC 19, AC 20).
 *
 * ONE expression, exported, in the manner `surfaceOf` established for the deck/panel precedence
 * — so a tile's *"am I live"* and the panel's *"what am I drawing"* can never disagree, which is
 * the epic's own *"the grid and the list panel cannot disagree"* clause applied to inspection.
 *
 * `??` and never `||`: every value here is a card id, and `''` is a card id the app refuses
 * rather than a falsy blank (`hydrateCard` terminally refuses it with zero requests).
 */
export const targetIdOf = (state: InspectionState): string | null =>
  state.pinnedId ?? transientIdOf(state) ?? state.defaultId

/**
 * A card is being POINTED at (UX-DR14). The pointer half only — keyboard focus is
 * {@link setFocused}, its own slot, so that neither modality's letting-go can erase the other's
 * target (PR #44 P1; the first spelling shared one slot and a `mouseleave` could strand a
 * still-focused tile).
 *
 * Args:
 *   cardId: The printing uuid. There is no `null` arm — leaving a card is {@link clearHovered},
 *     keyed by id for the race below, and leaving the DECK is {@link clearTransientTargets}.
 */
export const setHovered = (cardId: string): void => {
  if (!inspectable(cardId)) return
  useInspectionStore.setState({ hoveredId: cardId, lastTransient: 'hover' })
}

/**
 * The pointer has LEFT a specific card — clearing only if that card is still the one holding
 * the hover (Q8's one addition to the proposed API).
 *
 * **Keyed by id because of a real ordering.** Leaving one card and reaching the next produces
 * two events, and the losing tile's is free to land second: an unkeyed clear on `mouseleave`
 * would erase the hover the tile being MOVED TO has already set, and the panel snaps back to
 * the cold-open card in the middle of a sweep — the one motion `EXPERIENCE.md` describes this
 * whole panel as existing to make continuous. `lastTransient` is deliberately NOT touched: a
 * clear is a letting-go, and it says nothing about which modality the person is using.
 */
export const clearHovered = (cardId: string): void => {
  useInspectionStore.setState((state) => (state.hoveredId === cardId ? { hoveredId: null } : state))
}

/**
 * A card has taken KEYBOARD FOCUS (UX-DR14 — *"hover OR keyboard focus"*, full parity). The
 * same contract as {@link setHovered} in the other modality's slot: same refusal, same recency
 * write, same keyed clear in {@link clearFocused} for the same blur-after-focus race.
 */
export const setFocused = (cardId: string): void => {
  if (!inspectable(cardId)) return
  useInspectionStore.setState({ focusedId: cardId, lastTransient: 'focus' })
}

/** Keyboard focus has LEFT a specific card — `clearHovered`'s twin, for `blur`. */
export const clearFocused = (cardId: string): void => {
  useInspectionStore.setState((state) => (state.focusedId === cardId ? { focusedId: null } : state))
}

/**
 * Both transients die at once — the deck-transition clear (`CardDetail`'s boards effect, review
 * 2026-08-05): a hover or a focus pointing into a deck that just left the glass is stale by
 * construction, whichever modality set it.
 */
export const clearTransientTargets = (): void => {
  useInspectionStore.setState({ hoveredId: null, focusedId: null, lastTransient: null })
}

/**
 * A click, or Enter on a focused card: fix this target, or release it if it is already fixed
 * (AC 19, AC 20, UX-DR20).
 *
 * **Release is a SECOND SINGLE CLICK.** `EXPERIENCE.md`'s banned-interactions list names
 * double-click semantics outright, and a toggle keyed on identity is what makes the second click
 * a release rather than a re-pin. The hover is left untouched, which is what lets control return
 * to wherever the cursor actually is.
 */
export const togglePin = (cardId: string): void => {
  if (!inspectable(cardId)) return
  useInspectionStore.setState((state) => ({ pinnedId: state.pinnedId === cardId ? null : cardId }))
}

/** Release the pin: Esc (Q12), or the panel's unpin control (Q3). Idempotent. */
export const clearPin = (): void => {
  useInspectionStore.setState({ pinnedId: null })
}

/**
 * Whether a card is in a deck's LIST — all three boards, by `card_id` (story c7-4, R9).
 *
 * The sideboard is deliberately included, and the asymmetry with {@link coldOpenTargetOf} is the
 * point rather than a drift: a sideboard card is pinnable (`DeckList` renders it a focusable
 * row) and is "in the deck's list" in R9's words, so its DEPARTURE is the rule working — while
 * the fall-back target stays what the grid draws, which excludes the sideboard. `deckIsEmpty`
 * (`deckGroups.ts`) is the all-three-boards precedent.
 */
const inDeckList = (boards: DeckBoards, cardId: string): boolean =>
  boards.commander.some((card) => card.card_id === cardId) ||
  boards.sideboard.some((card) => card.card_id === cardId) ||
  boards.mainboard.some((group) => group.cards.some((card) => card.card_id === cardId))

/**
 * The R9 membership-transition eviction (story c7-4, ruling 2026-08-14): at a boards
 * replacement, release the pin ONLY if its card was in the departing decklist AND is absent
 * from the new one. Everything else survives — a card in both lists (the same-deck refetch
 * this story exists for), a card in neither (a pinned suggestion, the c6-7 debt row: it falls
 * out of the rule with no special-casing), and a first-ever boards (`previous === null`, no
 * departing deck to have been a member of).
 *
 * The rule reads only the TWO DECKLISTS, at replacement time — no pin-time classification of
 * what a pin points at, which is R9's own boundary. The fall-back needs no code here:
 * {@link clearPin} alone IS the fall-back to transient resolution, because `defaultId` is
 * re-set to `coldOpenTargetOf(next)` by the same boards effect that calls this.
 *
 * It takes both boards as ARGUMENTS, exactly as {@link coldOpenTargetOf} does: this module
 * holds no deck (see the header), and the one caller that has both — `CardDetail`'s boards
 * effect, via `deckMemory`'s departing-boards return — passes them in.
 *
 * Args:
 *   previous: The departing deck's boards, or `null` when there is no departing deck (a cold
 *     open, or a remount of the same reference). `null` never evicts.
 *   next: The boards now on the glass.
 */
export const evictDepartedPin = (previous: DeckBoards | null, next: DeckBoards): void => {
  if (previous === null) return
  const { pinnedId } = useInspectionStore.getState()
  if (pinnedId === null) return
  if (inDeckList(previous, pinnedId) && !inDeckList(next, pinnedId)) clearPin()
}

/** Record the cold-open target for the deck now on the glass. `null` for a deck with no cards. */
export const setDefaultTarget = (cardId: string | null): void => {
  useInspectionStore.setState({ defaultId: cardId })
}

/**
 * The cold-open target: the first card the GRID DRAWS (AC 8, Q15, AD-12).
 *
 * UX-DR20 says *"the first card of the first type group"*, and the literal reading and the
 * on-screen reading differ: `boards.commander` is a separate board that `CardGrid` draws
 * **before** the type groups, and 16 of 40 real decks have one — measured, the real deck's first
 * tile is `Atraxa, Praetors' Voice`. The panel targets what the eye lands on.
 *
 * **The flattening is `CardGrid.tsx:76`'s, and this is the second WRITING of it, not a second
 * RULE.** The grid is not edited by this story, so the expression is necessarily repeated; what
 * keeps it from drifting is a test in `CardDetail.test.tsx` that renders `CardGrid` over the
 * same boards and asserts this function's answer is the id of the first tile the grid actually
 * produced. A repeated expression checked against its original is a different thing from a
 * second derivation (AD-12), and the check is what makes the difference real.
 *
 * `boardsOf` emits `mainboard` in `TYPE_GROUPS` order **with empty groups omitted**, so
 * `mainboard[0]` is genuinely the first populated group. There is no `sort`, no `filter` and no
 * second grouping here — each of those is the drift `deckGroups.ts` was written to prevent.
 *
 * Args:
 *   boards: `surfaceOf`'s answer for a loaded deck, verbatim.
 *
 * Returns:
 *   The first tile's `card_id`, or `null` — the resolution is **total**, because `boardsOf([])`
 *   returns three empty boards and a deck with no cards is a real state (c4-12 owns its copy).
 */
export const coldOpenTargetOf = (boards: DeckBoards): string | null => {
  const tiles = [...boards.commander, ...boards.mainboard.flatMap((group) => group.cards)]
  return tiles.length === 0 ? null : tiles[0].card_id
}

/**
 * The card the detail panel is showing. **A primitive, so the panel re-renders only when the
 * resolved target actually changes** — not on every write to the slice.
 */
export const useInspectionTargetId = (): string | null => useInspectionStore(targetIdOf)

/**
 * Whether this card is the one under inspection — the tile's `live` state (Q7, DESIGN.md's
 * `components.card-tile.live-ring`).
 *
 * **A per-card selector rather than a prop threaded down from the grid, and the reason is
 * measured arithmetic rather than taste.** zustand v5 removed `create`'s equality-function
 * argument and matches React's referential default, so what a selector RETURNS decides who
 * re-renders. A boolean re-renders exactly the tiles whose value flipped — **two per hover**,
 * the one being left and the one being reached. `CardGrid` computing `live` and passing it down
 * would re-render **all 99** on every cursor movement across the grid, on precisely the sweep
 * the card cache exists to make cheap. It also keeps `CardGrid`'s props at `{ boards }` and lets
 * c4-7's deck rows call the identical hook without going through the grid at all.
 */
export const useIsLiveTarget = (cardId: string): boolean =>
  useInspectionStore((state) => targetIdOf(state) === cardId)

/**
 * Which card is pinned, or `null` — the panel's ring, its unpin control, and the one thing its
 * announcement is keyed on (AC 19, AC 21, AC 23).
 *
 * The ID rather than a boolean, and the reason is the ANNOUNCEMENT rather than the ring.
 * `aria-live` speaks when its content changes, and AC 23 says a pin announces *exactly once* —
 * so the panel's announcement effect has to fire on "the pin MOVED from one card to another",
 * which a boolean cannot express (`true` → `true` is not a change). A primitive either way, so
 * the subscription is still one value and one comparison.
 */
export const usePinnedId = (): string | null => useInspectionStore((state) => state.pinnedId)
