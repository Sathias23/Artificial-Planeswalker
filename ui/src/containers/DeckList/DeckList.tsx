import type { DeckCardSummary } from '../../api/schema'
import { GroupHeader } from '../../components/GroupHeader/GroupHeader'
import { ManaCost } from '../../components/ManaCost/ManaCost'
import { Panel } from '../../components/Panel/Panel'
import { useCardEntry } from '../../state/cards'
import type { DeckBoards, TypeGroup } from '../../state/deckGroups'
import {
  clearFocused,
  clearHovered,
  setFocused,
  setHovered,
  togglePin,
  useIsLiveTarget,
} from '../../state/inspection'
import { COMMANDER_LABEL, DECK_LIST_TITLE, GROUP_LABELS, SIDEBOARD_LABEL } from './copy'
import './DeckList.css'
import { frontFaceCost, frontFaceName } from './frontFaceCost'

/**
 * The deck as a text list, grouped by type — the right column's second panel
 * (story c4-7, FR-05, FR-13, FR-17, UX-DR3, UX-DR12, UX-DR19, UX-DR44, UX-DR47).
 *
 * ================= IT RENDERS THE DERIVATION; IT DOES NOT REPEAT IT (AC 17) ============
 *
 * `boardsOf` partitioned the deck and grouped the mainboard in `TYPE_GROUPS` order **once**, at
 * store write time, and `deckGroups.ts`'s header gives the epic's reason verbatim: *"so the grid
 * and the list panel cannot disagree"*. This file is the second half of that sentence. There is
 * no `sort()`, no `filter()` over cards, and no second grouping here — each would be the drift
 * that module exists to prevent, and AD-12 forbids the second derivation outright.
 *
 * **No `useMemo` over `boards`, either, and that one is not a style preference.** The `boards`
 * REFERENCE IDENTITY is the deck's identity: `deckMemory.ts:8-9` and `CardDetail.tsx:333-336`
 * both detect a deck replacement by comparing that reference. A memo — or any derived copy held
 * in a ref — would hand one of those consumers a reference that changes when the deck did not,
 * or fails to change when it did.
 *
 * ================= WHAT A GROUP-HEADER COUNT MEANS (Q14, AC 18) ========================
 *
 * **The SUMMED QUANTITY, never `cards.length`** — `deckGroups.ts:166-167` already rules it and
 * this header states it so the next reader does not have to derive it from a field name. The
 * visible consequence, stated rather than discovered: the largest real deck's Land group is 37
 * ROWS and renders **38**, because one of those rows is a second copy.
 *
 * It is worth saying why the distinction is load-bearing rather than pedantic. UX-DR16 and
 * UX-DR43 make this count the **non-motion accessible signal that a deck changed** — the quantity
 * badge's accent flash is explicitly garnish, and the count text is what carries the information.
 * A count that reported rows would not move when a quantity changed from 3 to 4, which is exactly
 * the change it exists to report.
 *
 * ================= THE THREE SECTIONS, AND WHY TWO OF THEM ARE HERE AT ALL (Q4) ========
 *
 * Commander first, then the mainboard's type groups in `TYPE_GROUPS` order, then the sideboard.
 * The two board sections are specified in **no artefact**; both were handed here by name —
 * `deckGroups.ts:188` (*"the sideboard, ungrouped — c4-7 decides whether it draws groups
 * there"*), `CardGrid.tsx:27` (*"a labelled commander section is c4-7's, with the rest of the
 * labelling"*) and `CardGrid.test.tsx:98` (*"does NOT render the sideboard … c4-7 owns them"*).
 *
 * **The sideboard draws no type groups.** 5 of 40 real decks have one at all, the richest is 9
 * rows, and splitting 9 rows across five type groups is five headers for nine rows — a structure
 * with more chrome than content. Ungrouped also matches the grid's commander-first order exactly,
 * so the two columns read as one deck rather than two orderings of it.
 *
 * **Conservation is the reason neither may be dropped** (`deckGroups.ts:216-221`):
 * `commanderQuantity + mainboardQuantity === mainboard_count` and
 * `sideboardQuantity === sideboard_count`. A row this panel fails to draw is a number in the deck
 * header that stops summing, and nothing on screen would say why.
 *
 * ================= WHAT THIS PANEL DELIBERATELY DOES NOT DO ============================
 *
 * **It re-derives no inspection state (AC 28).** No `targetIdOf` of its own, no local "current
 * card", and — emphatically — **no second `deckMemory`**. `replacesRememberedDeck` is a
 * module-scope singleton: a second caller would race `CardDetail`'s effect so that exactly one of
 * the two never sees the transition. The deck-transition clear is INHERITED, for free, from the
 * panel above this one. Its accepted cost is on the record: a same-deck edit releases a pin.
 *
 * **It is not a live region and adds no `aria-live` (AC 30).** Rows are 24-30px tall rather than
 * 246, so a cursor crossing this panel generates transient target changes an order of magnitude
 * faster than the grid does — which is precisely the flood UX-DR45 and the H4/C1 gate finding
 * exist to prevent. The only pin announcement in the app remains `CardDetail`'s single polite
 * region.
 *
 * **It renders no empty-state sentence (Q16).** `boardsOf([])` yields three empty boards and this
 * file renders the titled panel with no rows, which is a place for **c4-12** to put its line
 * rather than a state pretending to be one. Inventing copy here would pre-empt that story's own
 * copy AC and put unsourced words on the glass. Noted as an artefact gap: `EXPERIENCE.md:70`,
 * `:113` and Story 4.12's own AC each name exactly three panels to hide until a deck has cards —
 * the curve, the colour distribution and the format check — and **this panel is not among them**,
 * while no artefact says whether it hides or renders empty.
 *
 * **It reads no `strategy` (Q13).** The candidate was checked rather than assumed: `strategy` is
 * deck-level prose and a row list of cards has no place to put it.
 */

/**
 * The label map is coupled to `TypeGroup` **in both directions**, and the assertion lives here
 * rather than in `copy.ts` (AC 19, Q5).
 *
 * `copy.ts` must stay import-free so that `ui/tests/` can import it across the tsconfig project
 * boundary — `tests/` is `nodenext`, `src/` is `bundler`, and `TS2835` is a RESOLUTION error that
 * fires against the specifier whether or not `import type` erases it at emit. So the map is
 * declared there and held to the union here, which is `CardPlaceholder.tsx`'s shape exactly.
 *
 * Both directions are needed and each catches a different mistake:
 *
 *   {@link EveryTypeGroupHasALabel} — a TENTH group added to `TYPE_GROUPS` has no label, and the
 *   render would put `undefined` in an `<h2>`. This is not hypothetical: `Battle` is in the union
 *   today with **zero rows in every real deck**, so a missing label would ship green and appear
 *   the day somebody adds a Siege.
 *
 *   {@link EveryLabelIsATypeGroup} — a label written for a group that does not exist (a typo, or
 *   a group renamed in the store and not here) is dead copy that no render can reach. It also
 *   closes the WIDENING hole: annotate the map `Record<string, string>` and `keyof` becomes
 *   `string`, which this assertion rejects while the first would still pass.
 */
type Assert<T extends true> = T

export type EveryTypeGroupHasALabel = Assert<
  [Exclude<TypeGroup, keyof typeof GROUP_LABELS>] extends [never] ? true : false
>

export type EveryLabelIsATypeGroup = Assert<
  [Exclude<keyof typeof GROUP_LABELS, TypeGroup>] extends [never] ? true : false
>

/**
 * U+00D7 MULTIPLICATION SIGN, written as a genuine escape (AC 9).
 *
 * The same codepoint the quantity badge renders, so the two columns of a deck view cannot drift
 * apart. A keyboard produces the LETTER `x`, which is a different character, renders visibly
 * narrower and lighter beside a tabular digit, and is read aloud as a letter; the escape is what
 * makes a copy-paste or a find-and-replace unable to substitute it silently.
 *
 * Recorded rather than corrected: `CardTile.tsx:178` says of its own constant *"written as an
 * escape so that it cannot be got wrong"* and in fact ships the literal character. Same
 * codepoint, so nothing renders differently and no test moves — but the comment there is not
 * true of the line beneath it, and this story does not edit that file to fix a comment.
 */
const MULTIPLICATION_SIGN = '\u00D7'

/** One labelled block of rows: a board, or one of the mainboard's type groups. */
interface ListSection {
  /** React's key. Prefixed by kind, so a board and a group can never collide. */
  readonly key: string
  readonly label: string
  /** The SUMMED QUANTITY (Q14) — see this module's header. */
  readonly quantity: number
  readonly cards: readonly DeckCardSummary[]
}

/**
 * One row: a real `<button>`, carrying the whole inspection contract (AC 6, AC 25, UX-DR47).
 *
 * ================= A BUTTON, NOT AN `<li>` WITH A HANDLER (Q8, AC 6) ===================
 *
 * UX-DR47 requires *"a real `<button>` or `<a>`, never a `<div>` with a click handler"*, ESLint's
 * a11y gate errors on `onClick` on an `<li>`, and `CardTile.test.tsx:788-797` pins the same
 * choice for the tile — *"A REAL `<button>` … not a `tabIndex` on a div"*. **Nothing here
 * carries a `tabindex`**: a `<button>` is already in the Tab order, and adding one would be the
 * bug that pin exists to catch.
 *
 * ================= THE FIVE VERBS, EXACTLY AS A TILE ATTACHES THEM (AC 25) =============
 *
 * `inspection.ts:41-54` wrote its API location-agnostic **for this component by name**, and this
 * is what discharges that claim: the verbs below are the tile's verbs, unrenamed and unwrapped.
 *
 * **Two transient slots, not one** (`inspection.ts:91-99`, PR #44's P1): pointer writes
 * `setHovered`/`clearHovered`, keyboard writes `setFocused`/`clearFocused`, and `lastTransient`
 * resolves them when both hold a target. With one shared slot a `mouseleave` erased a
 * still-focused row.
 *
 * **The clears are keyed by id, and that matters MORE here than on the grid.** Leaving one card
 * and reaching the next produces two events and the losing row's is free to land second; an
 * unkeyed clear would erase the hover the row being MOVED TO has already set, and the detail
 * panel would snap back to the cold-open card in the middle of a sweep. Rows are 24-30px tall
 * against a tile's 246, so a pointer crosses an order of magnitude more of them per second.
 *
 * `onClick` carries `togglePin` for both mouse and keyboard: a `<button>` fires it on Enter and
 * on Space with no keydown handler, which is the reason the element was chosen.
 *
 * ================= WHY IT SUBSCRIBES TO THE CACHE AT ALL (Q2) =========================
 *
 * `useCardEntry` is called **unconditionally**, as the hooks rule requires, and its value is read
 * only on the blank-cost branch inside {@link frontFaceCost}. It is a stored reference rather
 * than a fresh object, so the subscription re-renders exactly the row whose hydration landed and
 * not the other ninety-eight. It starts nothing — the deck-wide sweep in `App.tsx` is what
 * fetches, and this row only watches.
 *
 * A row whose card is unknown or imageless renders **identically to any other row** (AC 15,
 * FR-13, UX-DR19): the list is text-first and draws no card face, so there is no image to fail.
 * The summary is always present — `DeckDetail.from_deck` validates a `CardSummary` per row inside
 * the response constructor, so a card-less entry cannot cross the wire at all (Q11).
 */
function DeckRow({ entry }: { entry: DeckCardSummary }) {
  const cardId = entry.card_id
  const live = useIsLiveTarget(cardId)
  const cached = useCardEntry(cardId)

  return (
    <button
      type="button"
      /* `is-live` is the class DESIGN.md's `components.deck-row.live-background` and
         `.live-rule` hang on — the same naming the tile's live ring uses, so one grep finds
         every live marker in the app. */
      className={live ? 'deck-row is-live' : 'deck-row'}
      onMouseEnter={() => setHovered(cardId)}
      onMouseLeave={() => clearHovered(cardId)}
      onFocus={() => setFocused(cardId)}
      onBlur={() => clearFocused(cardId)}
      onClick={() => togglePin(cardId)}
    >
      {/* THE QUANTITY (AC 9, UX-DR3, UX-DR19). It renders for EVERY row including quantity 1 —
          unlike the tile badge, which suppresses ×1 — because a column that disappears on 1,620
          of 1,999 real rows is not a column, it is a ragged left edge. 379 live rows (19.0%)
          exceed 1 and the largest anywhere is 34, so the track holds two digits and the sign. */}
      <span className="deck-row-quantity">{`${MULTIPLICATION_SIGN}${entry.quantity}`}</span>
      {/* THE NAME, FRONT FACE ONLY (AC 10, AC 23, UX-DR19). Free from the summary — 99.0% of
          faced cards store the combined string in `name` — so it is correct at first paint with
          nothing in flight. See `frontFaceCost.ts` for why this is not `deckGroups.ts`'s
          `frontFace`: that function's loose separator would render `SP//dr, Piloted by Peni` as
          `SP`. */}
      <span className="deck-row-name">{frontFaceName(entry.card.name)}</span>
      {/* THE COST, FRONT FACE ONLY (AC 11, AC 23). `ManaCost` unmodified and unresized — one
          prop, no size option, by its own ruling. `null` renders nothing, so the blank-cost and
          not-yet-hydrated cases need no branch here. */}
      <span className="deck-row-cost">
        <ManaCost cost={frontFaceCost(entry.card, cached)} />
      </span>
    </button>
  )
}

/** What the deck list draws. One prop, and it is the derivation — never the raw payload. */
export interface DeckListProps {
  /** `surfaceOf`'s answer for a loaded deck, verbatim. The SAME value `CardGrid` receives. */
  boards: DeckBoards
}

export function DeckList({ boards }: DeckListProps) {
  /* THE SECTIONS, IN THE ORDER THE STORE DECIDED (AC 17, AC 20, AC 21, AC 24).
     This is composition of an already-derived value, not a second derivation: no card is
     filtered, sorted or regrouped: `boards.mainboard` is spread in the order `boardsOf` emitted
     it, which is `TYPE_GROUPS`'s. The two `length > 0` tests are PRESENCE checks on a board, not
     filters over cards — 24 of 40 real decks have no commander and 35 have no sideboard, and a
     header over nothing is a hairline rule under blank space.

     Empty type groups need no such test: `boardsOf` already omits them (`deckGroups.ts:241`), so
     a deck with five groups renders five and a deck with eight renders eight. Nothing here
     assumes a fixed set, and `Battle` — zero rows in every real deck — is not special-cased. */
  const sections: ListSection[] = []

  if (boards.commander.length > 0) {
    sections.push({
      key: 'board:commander',
      label: COMMANDER_LABEL,
      quantity: boards.commanderQuantity,
      cards: boards.commander,
    })
  }

  for (const group of boards.mainboard) {
    sections.push({
      key: `group:${group.group}`,
      label: GROUP_LABELS[group.group],
      quantity: group.quantity,
      cards: group.cards,
    })
  }

  if (boards.sideboard.length > 0) {
    sections.push({
      key: 'board:sideboard',
      label: SIDEBOARD_LABEL,
      quantity: boards.sideboardQuantity,
      cards: boards.sideboard,
    })
  }

  return (
    /* A TITLED PANEL AT level="default" (AC 4, AC 33) — the first shipped consumer of that level,
       and of `GroupHeader`, which has had none since the day it shipped at c2-7.

       Titled, where `CardGrid`'s panel is deliberately not: a title here is not a duplicate
       count but a NAME, and this panel needs one for the same reason the grid does not. The grid
       is the page's obvious subject; this is one of three stacked panels in a 452px column, and
       `<section aria-label>` is what puts "Deck list" in a screen-reader user's landmark list so
       the column can be navigated at all.

       No `count` prop. The deck's totals are already on screen twice — the `h1` carries the deck
       name and `DeckBadges` carries "100 maindeck" beside it — and a third statement of the same
       number is the noise c4-4 declined for the same reason. The per-group counts below are the
       numbers this panel adds. */
    <Panel title={DECK_LIST_TITLE}>
      <div className="deck-list">
        {sections.map((section) => (
          /* The container owns the horizontal inset, NOT the header — `GroupHeader.css:13-15`
             ships no horizontal padding deliberately: *"a group header aligns with the rows it
             divides, and whatever container holds them owns that inset."* */
          <div className="deck-list-section" key={section.key}>
            <GroupHeader label={section.label} count={section.quantity} />
            {/* A REAL `ul`/`li` (AC 5, UX-DR44), with NO `role` override. The list semantics are
                what tell a screen-reader user how many rows a group holds before they start
                moving through it. */}
            <ul className="deck-list-rows">
              {section.cards.map((entry) => (
                /* `card_id` is unique BY THE DATA rather than by hope: `deck_cards` is keyed on
                   (deck_id, card_id) and `boardsOf` puts every row in exactly one board, so no
                   id appears twice across the whole list. */
                <li className="deck-list-item" key={entry.card_id}>
                  <DeckRow entry={entry} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Panel>
  )
}
