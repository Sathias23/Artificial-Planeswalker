import { Panel } from '../../components/Panel/Panel'
import { type DeckBoards, deckIsEmpty } from '../../state/deckGroups'
import { CardTile } from '../CardTile/CardTile'
import './CardGrid.css'
import { EMPTY_DECK_LINE } from './copy'

/**
 * The deck as card faces — the left column's primary surface (FR-05, FR-19, UX-DR4, UX-DR8,
 * UX-DR44).
 *
 * ================= IT RENDERS THE DERIVATION; IT DOES NOT REPEAT IT ====================
 *
 * `boardsOf` already partitioned the deck and grouped the mainboard in `TYPE_GROUPS` order, once,
 * at write time, and `deckGroups.ts`'s own header says why: *"so the grid and
 * the list panel cannot disagree"*. There is no `sort()`, no `filter(c => !c.sideboard)` and no
 * second grouping in this file — each of those is the drift that module was written to prevent,
 * and it is the kind of drift that is invisible until somebody counts the tiles.
 *
 * ================= FLAT, COMMANDER FIRST, SIDEBOARD NAMED ==============================
 *
 * Three real populations arrive in `DeckBoards` and all three are accounted for here:
 *
 *   **The mainboard** is flattened in `TYPE_GROUPS` order. Flat rather than headed, because the
 *   composition reference shows ONE grid in ONE panel and UX-DR12 specifies the group header as
 *   *"the text-list unit"*'s divider. Flattening in order keeps the visual grouping anyway —
 *   creatures cluster, then instants, then lands — without inventing headings, and it leaves
 *   `GroupHeader`'s `<h2>` semantics to the deck list, the panel that actually needs them.
 *   EXPERIENCE.md's Flow 1 (*"the new card appears in its type group"*) stays true of this render:
 *   a card added to a type group appears among that group's tiles.
 *
 *   **The commander goes first, unlabelled.** 16 of 40 real decks have one, and filing it into
 *   "Creatures" *"misstates the deck to anyone reading the list"* (`deckGroups.ts`'s own words).
 *   First and unlabelled is the minimum honest treatment for a surface that draws no headers;
 *   the labelled commander section is the deck list's, with the rest of the labelling.
 *
 *   **The sideboard is NOT rendered here; the deck list draws it.** 41 rows across 5 real decks,
 *   carried in `boards.sideboard` and ignored by this component. The art grid is the DECK; a
 *   sideboard silently mixed into it would inflate every count a reader takes off the screen.
 *   Naming the owner rather than saying nothing is the difference between a boundary and a
 *   conservation failure.
 *
 * ================= IT SUBSCRIBES TO NOTHING, AND THAT IS SAID LOUDLY ===================
 *
 * **This container is NOT a consumer of `useCardEntry` or `hydrateCard`.** The grid renders the
 * board it was handed. Say it loudly, because `useCardEntry`'s own docstring names a tile as its
 * expected caller and the next reader will assume it:
 *
 *   `DeckCardSummary.card` already carries the whole card for every tile, free, in the one
 *   request the deck boot already makes, and `seedDeckCards` has already put all of them in the
 *   cache as hydrated entries. A tile reads name, mana cost and type line off the board it was
 *   handed; oracle text is the DETAIL PANEL's, and `image_uris` is never consulted because
 *   the tile asks the image route directly.
 *
 *   The unknown-card variant has **no population reachable from a deck payload** — 0 dangling
 *   card references across 2,027 rows measured — so the one branch that would need a cache read
 *   has nothing to read for. Hydration exists for hover, and hover is the detail panel's.
 *
 * ================= WHAT THIS FILE DELIBERATELY DOES NOT DO =============================
 *
 * No group headers and no deck list (those are `DeckList`'s). No `deck_changed` refetch and no
 * live region.
 *
 * ================= THE EMPTY DECK ======================================================
 *
 * **The line REPLACES the `<ul>`; it does not sit inside or beside it.** Three reasons, and
 * only the first is about validity:
 *
 *   A `<p>` inside a `<ul>` is invalid HTML against UX-DR44's mandated list semantics — a `ul`
 *   admits `li` and nothing else — so "beside the tiles, inside the list" was never available.
 *
 *   An empty `<ul>` LEFT IN PLACE announces *"list, 0 items"* to a screen-reader user **before**
 *   the sentence that explains why there are none. The list semantics exist to say how many cards
 *   there are before someone starts moving through them; on a deck with none, that count is the
 *   least useful thing on the surface and it would arrive first.
 *
 *   And the panel itself stays — **untitled** (a plain unnamed `<section>` inventing no landmark
 *   name). The empty state is a deck, not a system fault: the shell's `left` slot must never fall
 *   through to its own placeholder, which is what returning `undefined` from here would cause.
 *
 * **What this file still does NOT decide.** It does not gate any analysis panel — `ManaCurve` and
 * `ColourDistribution` hide on their own zero totals and `App.tsx` owns the format-check gate —
 * and it does not re-derive emptiness: `deckIsEmpty` is the single expression
 * shared with `hasCards`, and this container reads it rather than writing a fourth board test.
 * See `deckGroups.ts` for why a sideboard-only deck is NOT empty and therefore shows an empty
 * grid with no line — a named residue, unreachable from the 42 real decks.
 */

/** What the grid draws. One prop, and it is the derivation — never the raw payload. */
export interface CardGridProps {
  /** `surfaceOf`'s answer for a loaded deck, verbatim. */
  boards: DeckBoards
}

export function CardGrid({ boards }: CardGridProps) {
  const empty = deckIsEmpty(boards)

  // ONE LIST, IN THE ORDER THE STORE DECIDED. `flatMap` over the groups preserves `TYPE_GROUPS`
  // order because `boardsOf` emitted them in it; nothing here re-sorts, and nothing here filters.
  // Not built at all on the empty deck — the branch below would only discard it.
  const tiles = empty
    ? []
    : [...boards.commander, ...boards.mainboard.flatMap((group) => group.cards)]

  return (
    /* AN UNTITLED PANEL. A title carrying "60 cards · 16 distinct" — the mock's shape — would be
       the THIRD statement of the same number on one screen: the `h1` already carries the deck
       name and `DeckBadges` already says "100 maindeck" beside it, which is their job. An
       untitled `Panel` is a plain unnamed `<section>` that INVENTS NO NAME, so it adds no
       duplicate entry to a screen-reader user's landmark list — which a generic invented title
       would.

       The quantity a reader needs per tile is on the tile, in the badge, and announced with it. */
    <Panel>
      {empty ? (
        /* THE EMPTY-DECK LINE. A plain `<p>`, no role, no `aria-live`, no icon and no error
           styling — DESIGN.md's `components.empty-deck-line`. The string is EXPERIENCE.md's own,
           byte for byte, and it lives in `./copy` rather than here: a sentence a user reads needs
           one address, and `tests/empty-deck-copy.test.ts` compares that address against the
           artefact. */
        <p className="card-grid-empty">{EMPTY_DECK_LINE}</p>
      ) : (
        /* A REAL `ul`/`li` (UX-DR44, EXPERIENCE.md:154) — not a div soup, and not a `role`
           attribute painted onto one. The list semantics are what tell a screen-reader user how
           many cards there are before they start moving through them, which is the one structural
           count this surface ships. */
        <ul className="card-grid">
          {tiles.map((entry) => (
            /* `card_id` is the key, and it is unique BY THE DATA rather than by hope: `deck_cards`
             is keyed on (deck_id, card_id), and `boardsOf` puts every row in exactly one board,
             so no id can appear twice in this list. An index key would silently reuse a tile's
             loaded/failed state for a different card the moment a deck changed under it. */
            <li className="card-grid-item" key={entry.card_id}>
              <CardTile
                cardId={entry.card_id}
                name={entry.card.name}
                cost={entry.card.mana_cost}
                typeLine={entry.card.type_line}
                quantity={entry.quantity}
              />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
