/**
 * The decklist, partitioned by board and grouped by card type — derived ONCE (story c4-2, FR-05).
 *
 * The epic's reason is verbatim and it is the whole point of this module existing rather than a
 * `useMemo` in a component: *"so the grid and the list panel cannot disagree"*. **c4-4**'s
 * card-art grid, **c4-7**'s deck-list panel and **c4-8**'s mana curve all read the same derived
 * value; two consumers each writing `filter(c => !c.sideboard)` slightly differently is exactly
 * the drift this is written to prevent, and it is invisible until someone counts the tiles.
 *
 * Pure, framework-free and store-free on purpose — no React, no zustand, no fetch. `deck.ts`
 * calls it once at write time; every test in `deckGroups.test.ts` runs against a plain function.
 *
 * ================= THE ONLY INPUT IS `type_line`, AND THAT IS A REAL CONSTRAINT ========
 *
 * The deck payload carries a `CardSummary` per card — name, mana cost, cmc, **`type_line`**,
 * oracle text, colours, rarity, set code — and **no `card_faces`**. So *"double-faced cards group
 * by their front face"* (FR-05, UX-DR17) is implementable exactly as the segment before the first
 * ` // `, and the one shape it cannot resolve is the **`'Card // Card'` printing**, whose real
 * front-face type lives only in `card_faces[0].type_line` (2,274 in the 38,261-card corpus).
 * Measured at `2095050` against the live database: **0 of 1,999 live deck rows** are such a
 * printing. **Latent, not live** — declared here rather than closed by fetching 99 card records
 * to fix a case no deck contains.
 *
 * ================= THE REPO HAS TWO LAND POLICIES AND THEY DISAGREE ====================
 *
 * `src/viewer/view_model.py::is_land` classifies on the **front face** (`type_line.split("//")[0]`)
 * *"so a modal/double-faced card whose front is a spell is treated as a nonland"*;
 * `src/logic/assessment/mana_base.py::_is_land` and `src/logic/mana_curve.py` use a **whole-string**
 * `"land" in type_line.lower()` and document that as v1 policy. FR-05 and UX-DR17 both say FRONT
 * FACE, so this module follows `view_model.py`. **84 corpus cards** would be misgrouped by the
 * whole-string policy and **four of them are in real decks today**:
 *
 *   | Agadeem's Awakening // Agadeem, the Undercrypt      | `Sorcery // Land`                            | **Sorcery**     |
 *   | Kazandu Mammoth // Kazandu Valley                   | `Creature — Elephant // Land`                | **Creature**    |
 *   | Dowsing Dagger // Lost Vale                         | `Artifact — Equipment // Land`               | **Artifact**    |
 *   | Journey to Eternity // Atzal, Cave of Eternity      | `Legendary Enchantment — Aura // Legendary Land` | **Enchantment** |
 *
 * **The curve's policy is NOT fixed here.** That is `src/logic/mana_curve.py`, a Python change
 * with MCP blast radius, and it belongs to **c4-8**.
 *
 * ================= WHICH TYPE LINES ACTUALLY DISCRIMINATE THE RULE =====================
 *
 * A measurement worth carrying, because it says where this rule can be tested and the obvious
 * answer is wrong. {@link groupOf} strips everything after the em-dash before matching, so for
 * any DFC whose FRONT face carries a subtype the back face is already gone and the front-face
 * split changes nothing. The four cards above are all of that shape but one, and the exception
 * (`Sorcery // Land`) is saved by `Sorcery` preceding `Land` in {@link TYPE_GROUPS} — so **none
 * of the four discriminates this implementation**, a fact found by a probe that deleted
 * {@link frontFace} from this function and watched every assertion stay green.
 *
 * The discriminating shape is: front face with NO em-dash, and a back face whose group PRECEDES
 * the front's. Measured across the corpus at `2095050`: **29 distinct type lines, 0 of them in
 * any live deck.** `'Land // Legendary Creature — Demon'` (Westvale Abbey) is the sharpest — the
 * broken rule files a LAND under Creatures — and `deckGroups.test.ts` holds this function to six
 * of the 29 by name.
 */

import type { DeckCardSummary, DeckDetail } from '../api/schema'

/**
 * The type groups, in the order a decklist shows them — **and, read first-match-wins, the
 * precedence for a card carrying more than one primary type.**
 *
 * ONE list serving both, because two lists are two things to drift (AC 15). The order is the
 * conventional decklist order every Magic tool uses, so **c4-7**'s group headers and **c4-5**'s
 * *"the first card of the first type group"* both have something deterministic to rest on;
 * `deckGroups.test.ts` asserts the order itself, not merely the membership.
 *
 * **What first-match-wins decides, measured on live decks at `2095050`** — 88 rows carry more
 * than one primary type on the front face:
 *
 *   `Artifact Creature — Golem`                       → **Creature**
 *   `Enchantment Creature — Spirit`                   → **Creature**
 *   `Legendary Artifact Planeswalker — Equipment`     → **Planeswalker**
 *
 * `Battle` is in the list with 39 cards in the corpus and **0 in any deck**: a real type with a
 * real group costs one array entry, and discovering it missing later costs a card silently
 * landing in `Other`. `Kindred`/`Tribal` (82 corpus cards, 0 in decks) is deliberately NOT here —
 * a Kindred card always carries a second real type (`Kindred Instant`, `Kindred Enchantment`), so
 * it takes the ordinary path and lands where a player would look for it.
 *
 * **One declared consequence, not a special case:** `Land Creature — Forest Dryad` (Dryad Arbor)
 * groups as a **Creature**, because `Creature` precedes `Land`. 4 in the corpus, **0 in any
 * deck**. Noted so the next reader finds it stated rather than surprising.
 *
 * `Other` is the residual AC 16 demands, and it is what makes conservation possible: a card the
 * scheme does not name is CARRIED, never dropped. 1 live row needs it today — the two copies of
 * "Pym Particles", whose `type_line` is literally `'Card'`.
 */
export const TYPE_GROUPS = [
  'Creature',
  'Planeswalker',
  'Battle',
  'Instant',
  'Sorcery',
  'Artifact',
  'Enchantment',
  'Land',
  'Other',
] as const

export type TypeGroup = (typeof TYPE_GROUPS)[number]

/** The group `frontFaceGroup` falls back to. Named so no consumer spells the string itself. */
const RESIDUAL_GROUP: TypeGroup = 'Other'

/**
 * The front face of a type line — the segment before the first `//`.
 *
 * FR-05 and UX-DR17's rule, and `view_model.py::is_land`'s implementation, in one function.
 *
 * The separator is matched as an optional-whitespace-slash-slash-optional-whitespace pattern
 * rather than as the literal `' // '` Scryfall actually emits. (Spelled out in words because the
 * regex literal for it ends in the two characters that CLOSE a block comment — measured, it
 * truncated this docstring and produced 30 parse errors in one file.) Both spellings appear in
 * this repo — the story text says `' // '`, the Python viewer splits on `'//'` and trims — and
 * the pattern is the strictly-safer reading of the two: a
 * hypothetical `'Sorcery//Land'` yields `'Sorcery'` under it and the whole unsplit string under
 * the literal, which would then match NO group and silently land a spell in `Other`. Measured:
 * every one of the 3,183 corpus type lines containing `//` uses the spaced form, so this costs
 * nothing today and removes a way to be wrong later.
 *
 * Args:
 *   typeLine: The card's `type_line`, verbatim. Measured at `2095050`: **0 of 38,261 corpus rows**
 *     are null or blank, so there is no empty case to design for — and a blank one would answer
 *     `Other`, which is the honest answer for a card whose type is unknown.
 *
 * Returns:
 *   The front face, trimmed.
 */
export const frontFace = (typeLine: string): string => typeLine.split(/\s*\/\/\s*/)[0].trim()

/**
 * Which group one type line belongs to (AC 14, AC 15, AC 16).
 *
 * Two reductions before the match, and each closes a different way of being wrong:
 *
 *   1. **The front face only.** See {@link frontFace} and this module's header — this is the
 *      clause four real cards in real decks depend on.
 *   2. **The supertype/type half only** — everything before the em-dash. `—` is U+2014 and not a
 *      hyphen, measured. Without this, a SUBTYPE containing a type word would decide the group:
 *      the match is against whole words, and a subtype list is exactly where a stray `Creature`
 *      or `Land` can appear without the card being one.
 *
 * The match is against WHOLE WORDS, not a substring: `'land' in type_line` is the whole-string
 * policy this module's header rejects, and a substring test would additionally group anything
 * containing `Landfall`-shaped text wrongly.
 *
 * Args:
 *   typeLine: The card's `type_line`, verbatim.
 *
 * Returns:
 *   The first {@link TYPE_GROUPS} entry the front face names, or `'Other'` if it names none.
 */
export const groupOf = (typeLine: string): TypeGroup => {
  // U+2014 EM DASH, the separator Scryfall writes between types and subtypes.
  const types = frontFace(typeLine).split('—')[0]
  const words = new Set(types.split(/\s+/).filter((word) => word !== ''))
  return TYPE_GROUPS.find((group) => words.has(group)) ?? RESIDUAL_GROUP
}

/** One type group and the cards in it. Only groups with at least one card are emitted. */
export interface CardGroup {
  readonly group: TypeGroup
  readonly cards: readonly DeckCardSummary[]
  /** The summed `quantity` of {@link cards} — what a group header shows, never `cards.length`. */
  readonly quantity: number
}

/**
 * A deck's cards, partitioned three ways and grouped by type inside the mainboard (Q4).
 *
 * **Why three boards rather than one flat grouping.** `DeckCardSummary` carries `sideboard` and
 * `commander` as first-class flags, 16 of 40 real decks have a commander and 5 have a sideboard
 * (41 rows). A commander filed under "Creatures" misstates the deck to anyone reading the list,
 * and the sideboard is not part of the deck the curve and colour panels describe —
 * `view_model.py` already partitions `sideboard is False` for exactly that reason. Doing it once
 * here means c4-4, c4-7 and c4-8 inherit ONE partition. Measured cost of not doing it: 41
 * sideboard rows and 16 commander rows would join the type groups and inflate every count on
 * screen.
 */
export interface DeckBoards {
  /** The commander(s): `commander && !sideboard`. Empty for the 24 of 40 decks without one. */
  readonly commander: readonly DeckCardSummary[]
  /** Everything else that is not sideboard, grouped by type in {@link TYPE_GROUPS} order. */
  readonly mainboard: readonly CardGroup[]
  /** The sideboard, ungrouped — c4-7 decides whether it draws groups there. */
  readonly sideboard: readonly DeckCardSummary[]
  /** Summed quantities, board by board. See {@link boardsOf} for what these must add up to. */
  readonly commanderQuantity: number
  readonly mainboardQuantity: number
  readonly sideboardQuantity: number
}

const quantityOf = (cards: readonly DeckCardSummary[]): number =>
  cards.reduce((total, card) => total + card.quantity, 0)

/**
 * Partition a deck's cards into boards and type groups (AC 13, AC 14, AC 15, AC 16).
 *
 * ================= THE PARTITION SPLITS ON `sideboard` FIRST, AND THAT IS ARITHMETIC ====
 *
 * The backend computes its counts on that flag ALONE — `deck.py::_counts` is
 * `sum(quantity for dc in deck_cards if not dc.sideboard)` and its complement — so a commander is
 * counted in `mainboard_count`, and a (hypothetical) sideboarded commander in `sideboard_count`.
 * Splitting on `commander` first would put such a row in the commander board while the backend
 * counted it in the sideboard, and the conservation identity below would stop holding for a
 * reason nobody could see. So: `sideboard` decides the board, and `commander` only decides which
 * side of the non-sideboard split a row lands on. Measured at `2095050`: **0 of 1,999 live rows
 * are both**, so this is a latent case made impossible rather than one being fixed.
 *
 * ================= CONSERVATION IS THE INVARIANT (AC 16) ===============================
 *
 * Every `DeckCardSummary` in `cards` appears in **exactly one** of `commander`, one `mainboard`
 * group, or `sideboard` — a card that vanishes from every group is a card the deck view silently
 * loses, and the counts stop summing to the deck. Two identities follow, and `deckGroups.test.ts`
 * asserts both against the payload's own numbers rather than against a hand-written total:
 *
 *     commanderQuantity + mainboardQuantity === detail.mainboard_count
 *     sideboardQuantity                     === detail.sideboard_count
 *
 * Args:
 *   cards: A `DeckDetail`'s `cards`, verbatim. The wire's own docstring warns that its order is
 *     *"not meaningful"* — it falls out of the composite primary key — which is why this function
 *     imposes one rather than preserving one.
 *
 * Returns:
 *   The boards. Groups with no cards are omitted entirely, so `mainboard` is never a list of
 *   mostly-empty headers; the ORDER of the groups that remain is {@link TYPE_GROUPS}'s.
 */
export const boardsOf = (cards: readonly DeckCardSummary[]): DeckBoards => {
  const sideboard = cards.filter((card) => card.sideboard)
  const kept = cards.filter((card) => !card.sideboard)
  const commander = kept.filter((card) => card.commander)
  const main = kept.filter((card) => !card.commander)

  const mainboard = TYPE_GROUPS.map((group) => ({
    group,
    cards: main.filter((card) => groupOf(card.card.type_line) === group),
  }))
    .filter((entry) => entry.cards.length > 0)
    .map((entry) => ({ ...entry, quantity: quantityOf(entry.cards) }))

  return {
    commander,
    mainboard,
    sideboard,
    commanderQuantity: quantityOf(commander),
    mainboardQuantity: quantityOf(main),
    sideboardQuantity: quantityOf(sideboard),
  }
}

/** {@link boardsOf} over a whole payload — the one call `src/state/deck.ts` makes. */
export const boardsOfDeck = (detail: DeckDetail): DeckBoards => boardsOf(detail.cards)
