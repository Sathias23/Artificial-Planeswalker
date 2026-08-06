import type { CardSummary } from '../../api/schema'
import type { CardEntry } from '../../state/cards'

/**
 * The front face of a double-faced card, as a deck row must show it (story c4-7, Q2, AC 23,
 * UX-DR19, FR-05).
 *
 * UX-DR19 and `EXPERIENCE.md:87` both say a deck row shows *"the front face's name and cost"*.
 * That is one clause, and it resolves **three different ways** depending on the card — which is
 * why this is a module with tests rather than an expression in the row.
 *
 * ================= ITS OWN MODULE, BECAUSE A HELPER IN A `.tsx` BREAKS FAST REFRESH ====
 *
 * `react-refresh/only-export-components` is an ESLint **error**: a non-component value exported
 * from a component file breaks fast refresh. `imageUrl.ts`, `deckMemory.ts`, `imagedFaces.ts` and
 * `useCardArt.ts` are the four precedents, and this is the fifth — its own module, its own
 * `CONTAINERS` entry (decide-once ruling 3).
 *
 * ================= WHY THE NAME HALF LIVES HERE TOO, DESPITE THE FILENAME =============
 *
 * The story's source tree named this module for the cost, because the cost is the hard half. The
 * NAME split landed here anyway rather than reusing `deckGroups.ts`'s exported {@link frontFace},
 * and the reason is a measured defect rather than tidiness — see {@link frontFaceName}. Both
 * halves answer one question ("what does the front face of this card show?"), so they share a
 * module and the filename is the one the story wrote down.
 */

/**
 * The separator, spelled as the LITERAL Scryfall emits — and this is the whole finding.
 *
 * `deckGroups.ts:131`'s {@link frontFace} splits on the loose pattern
 * optional-whitespace-slash-slash-optional-whitespace, and its docstring argues at length that
 * the loose form is *"the strictly-safer reading of the two"*. **That argument is correct for a
 * TYPE LINE and it inverts for a NAME**, which is why this module does not reuse that function:
 *
 *   For a type line, a hypothetical `'Sorcery//Land'` splits to `'Sorcery'` under the loose
 *   pattern and stays whole under the literal — and the whole string matches no group, so a spell
 *   lands silently in `Other`. Loose is safer: it fails toward the right answer.
 *
 *   For a NAME there is no matching step to fail. A loose split simply truncates, and the
 *   truncated string is rendered. Measured against the shipped database at `d51b467`: exactly one
 *   card in 38,261 carries an **unspaced** `//` in its `name` — `'SP//dr, Piloted by Peni'`, a
 *   SINGLE-faced Legendary Artifact Creature — and the loose pattern renders it as **`'SP'`**. A
 *   wrong card name on the glass, from a card that needs no splitting at all.
 *
 * It is in no live deck today. It is in the corpus, so it is one `add_card_to_deck` away, and the
 * literal costs nothing to be right about: all 3,194 faced `name`s and all 338 split `mana_cost`s
 * use the spaced form, and **no single-faced card carries `' // '` in either field** — so the
 * literal splits everything that should split and nothing that should not.
 */
const FACE_SEPARATOR = ' // '

/** Trimmed, or `null` — the emptiness spelling of decide-once rule 16, never truthiness. */
const trimmedOrNull = (value: string | null | undefined): string | null => {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

/** The cost segment before the first `' // '`, trimmed to `null` — branches 1 and 3 share it. */
const beforeSeparator = (cost: string): string | null =>
  trimmedOrNull(cost.slice(0, cost.indexOf(FACE_SEPARATOR)))

/**
 * The front face's NAME, from the deck payload alone — no hydration, no fetch (AC 23).
 *
 * **This half is free**, and that is the measurement that separates it from the cost: 3,194 of
 * the 3,225 faced cards (99.0%) store the combined `'A // B'` string in the top-level `name`, and
 * **0 store a blank one**. So one split off `DeckCardSummary.card.name` answers UX-DR19 for every
 * double-faced card in every real deck, at first paint, with nothing in flight.
 *
 * It is also a layout argument independent of the AC: the worst front-face name in a live deck is
 * 33 characters (`Captain Marvel, Earth's Protector`), where the worst UNSPLIT name is 56
 * (`Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel`) — a 41% reduction in the worst
 * case the 1fr track has to hold before its ellipsis fires.
 *
 * Args:
 *   name: `CardSummary.name`, verbatim.
 *
 * Returns:
 *   The segment before the first `' // '`, trimmed; the whole string when there is none — also
 *   when the front segment trims to nothing (a `name` beginning `' // '`), because a truncated
 *   blank is worse than the raw string, and inventing a placeholder here would put an authored
 *   word outside `copy.ts`. Measured: 0 of 38,261 corpus rows have a blank `name`.
 */
export const frontFaceName = (name: string): string => {
  const index = name.indexOf(FACE_SEPARATOR)
  if (index === -1) return name
  const front = name.slice(0, index).trim()
  return front === '' ? name : front
}

/**
 * The front face's COST — the clause that resolves three ways (Q2, AC 23).
 *
 * ================= THE THREE SHAPES, MEASURED AT `d51b467` ============================
 *
 * Of the 3,225 cards carrying `card_faces`, **2,830 (87.8%) have a BLANK top-level `mana_cost`**
 * whose real value lives only in `card_faces[0].mana_cost` — which `CardSummary` does not carry.
 * In live decks that is 24 of the 40 distinct DFCs, across 38 rows.
 *
 *   | shape                      | top-level `mana_cost`   | resolved by                       |
 *   |----------------------------|-------------------------|-----------------------------------|
 *   | adventure / omen           | `'{1}{B}{B} // {1}{B}{B}'` | **splitting** — no fetch needed  |
 *   | single-faced, or DFC with one | `'{2}{R}'`           | verbatim                          |
 *   | transform / MDFC / battle  | `''`                    | `card_faces[0]` from **hydration** |
 *   | genuinely costless         | `''`                    | nothing, correctly — `null`       |
 *
 * The split branch comes FIRST and that ordering is load-bearing: an Adventure card's cost is
 * non-blank, so a "non-blank means use it verbatim" test placed first would render
 * `'{1}{B}{B} // {1}{B}{B}'` — both halves, with the separator spoken aloud as "slash slash" by
 * `describeManaCost` (the ledger entry at `deferred-work.md:1429-1445`, re-homed to this story).
 * Splitting first is what closes that deferral **by construction on this surface**: a `' // '`
 * never reaches `ManaCost` from a deck row.
 *
 * ================= THE FIRST-PAINT CONSEQUENCE, STATED PLAINLY ========================
 *
 * The hydration branch is the only one that is not free, and 26 live rows across 18 distinct
 * cards depend on it (plus `Pym Particles`, whose `type_line` is literally `'Card'`). Those rows
 * draw **no pips until the deck-wide sweep reaches them** — c4-6 measured that tail at ~1.2 s on
 * the 99-card deck, with first paint untouched.
 *
 * **c4-6's accepted no-re-drive window applies here and is cited, not re-opened.** c4-2's
 * edge-triggered recovery only re-boots from `refused`/`none`, so a backend blip *during* the
 * sweep, while deck state is already `deck`, leaves those rows permanently pip-less until a
 * reload — with no error state to explain it, while their single-faced neighbours look fine
 * because they never needed the fetch. That is the documented posture (c4-6 review ruling 1); it
 * is not papered over with a retry this story does not own.
 *
 * Args:
 *   summary: The row's `DeckCardSummary.card` — always present, never absent (see AC 15/Q11).
 *   entry: The hydration cache's answer for this id, or `undefined` when it has never been seen.
 *     Read from `useCardEntry`, which starts nothing.
 *
 * Returns:
 *   A Scryfall cost string for the front face, or `null` when there is nothing to draw — which
 *   `ManaCost` already renders as nothing, so `null` needs no special case at the call site.
 */
export const frontFaceCost = (
  summary: CardSummary,
  entry: CardEntry | undefined,
): string | null => {
  const declared = trimmedOrNull(summary.mana_cost)

  // 1. THE SPLIT SHAPE, FIRST — see the ordering note above.
  if (declared !== null && declared.includes(FACE_SEPARATOR)) {
    return beforeSeparator(declared)
  }

  // 2. A REAL TOP-LEVEL COST — the single-faced case, and the 395 faced cards that carry one.
  if (declared !== null) return declared

  // 3. THE HYDRATED FRONT FACE. `status === 'hydrated'` is the ONLY tier carrying `card_faces`;
  //    `summary`, `loading` and `unknown` all hold a `CardSummary` at best, which is where this
  //    function already looked. Optional-chained because `card_faces` is optional on the wire and
  //    a single-faced card's is absent rather than empty. Routed through the SAME split as
  //    branch 1: `card_faces` is untyped on the wire, so a face-level cost carrying `' // '`
  //    would otherwise reach `ManaCost` verbatim and reopen the spoken-separator deferral this
  //    module closes by construction. Measured 0 in the corpus today; the guard costs one branch.
  if (entry?.status === 'hydrated') {
    const face = trimmedOrNull(entry.card.card_faces?.[0]?.mana_cost)
    if (face !== null && face.includes(FACE_SEPARATOR)) return beforeSeparator(face)
    return face
  }

  // 4. NOTHING TO DRAW, and that is a real answer rather than a failure: the six live Pathway
  //    cards are genuinely costless on both faces, and they stay blank after hydration too.
  return null
}
