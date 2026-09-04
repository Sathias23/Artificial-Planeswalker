import { ManaCost } from '../ManaCost/ManaCost'
import type { PlaceholderKey } from '../StatePanel/states'
import './CardPlaceholder.css'
import { UNKNOWN_CARD_LABEL } from './copy'

/**
 * The card-shaped stand-in for art that has not arrived or does not exist (FR-13, FR-19,
 * UX-DR4, UX-DR22, UX-DR36).
 *
 * PRESENTATION-ONLY (the `shell.test.ts` posture every primitive in `src/components/` inherits):
 * no state, no hook of any family, no fetch, no store, no handler, no ref, no spread, and no
 * `react` import at all — none of its props is a `ReactNode`, which is the stronger claim.
 *
 * ================= THE SHAPE IS NOT WRITTEN HERE, AND THAT IS THE POINT =================
 *
 * Every variant carries `card-shape`, whose two declarations — `aspect-ratio: 63 / 88` and
 * `border-radius: var(--radius-card)` — live in `src/styles/card-geometry.css` and nowhere else.
 * The tile, the detail art and the flipped face consume the same class, so UX-DR36's
 * *"it occupies exactly the same footprint, so layout never reflows when art arrives"* is
 * structurally true rather than asserted three times. **This component never writes
 * `aspect-ratio` or `border-radius`**, and neither may they.
 *
 * ================= THE VARIANT VOCABULARY IS `states.ts`'s ==============================
 *
 * {@link CardPlaceholderVariant} is built FROM `PlaceholderKey`, not beside it. `PlaceholderKey`
 * is `'unknown-card' | 'named-card'`, with `PLACEHOLDER_FOR_REASON` mapping `card_not_found` to
 * the first and both image tokens to the second, and four type-level asserts holding that
 * classification total and disjoint. A third vocabulary invented here ("missing / absent /
 * pending") is precisely the failure that file exists to prevent.
 *
 * The coupling is enforced in both directions by the two asserts at the bottom of this file: a
 * third key added to `states.ts` fails {@link EveryPlaceholderKeyHasProps}, and a variant union
 * widened to a bare `string` fails {@link NoVariantIsUnknownToStates}. Both are `tsc` failures
 * with `npm test` staying green, which is why `npx tsc -b --force` is a gate of its own.
 *
 * ================= WHICH VARIANT A CARD GETS IS ALREADY DECIDED =========================
 *
 * Nowhere in this file is a placeholder derived from a wire token. `cards.ts`'s `entryFor`
 * already wrote `placeholder: PlaceholderKey | null` once, per entry, so this component draws
 * the right thing without re-deriving it from tokens. A `switch (entry.reason)` in a component
 * is the drift that field exists to prevent.
 *
 * ================= WHAT THE CALLER PASSES, AND WHY THE PROPS ARE A UNION ===============
 *
 * {@link CardPlaceholderProps} is a discriminated union rather than one flat bag of optionals,
 * and it closes two failures that no test could otherwise catch at author time:
 *
 *   **The unknown variant cannot be given a card's real name.** `<CardPlaceholder
 *   variant="unknown-card" name="Black Lotus" />` is a type error, not a plausible-looking
 *   render. That is the copy-paste that would otherwise type-check, and here it does not.
 *
 *   **The loading well cannot be given text of any kind.** Its member of the union has ONE
 *   property. `EXPERIENCE.md` is *"No copy. Wells stay silent"*, and the strongest available
 *   form of that is an API with nothing to say it with.
 *
 * ================= INSPECTABILITY IS A CONTRACT THIS COMPONENT CANNOT IMPLEMENT =========
 *
 * `EXPERIENCE.md`: *"Placeholder tiles behave like normal tiles (inspection contract) except
 * the unknown-card variant, which cannot be inspected — there is nothing to show."* The tile
 * and the inspection contract live in CardTile and the detail panel, and a listed primitive
 * takes no handlers at all (`shell.test.ts` bans `on*` in both positions), so this component
 * structurally cannot make anything inspectable. What it CAN do is give the tile no accidental
 * path to violating the rule: the variant is a value at the call site, so the tile branches on
 * it rather than re-deriving it, and there is no `inspectable` prop for a caller to pass `true`
 * to. The tile's tests prove the refusal; this file's API is what makes it easy to obey.
 */

/**
 * The three things this component can be: `states.ts`'s two placeholders, plus the silent well.
 *
 * `'loading'` is NOT a `PlaceholderKey` and must never become one. A `PlaceholderKey` is the
 * named destination of a REFUSAL — a token crossed the wire and said the card is unknown or its
 * picture is missing. An image in flight is not a refusal; it is the ordinary first paint of
 * every card, every time (`EXPERIENCE.md`'s placeholder-then-fill). Adding it to `states.ts`
 * would break `EveryPanellessReasonIsClassified` by classifying a token that does not exist.
 */
export type CardPlaceholderVariant = PlaceholderKey | 'loading'

/**
 * How many characters of the Scryfall printing uuid the unknown variant shows.
 *
 * **8, and the number carries its arithmetic** — a bare number in this codebase is a defect.
 * Measured over all 38,261 ids in the shipped corpus at `2a64231`: the first **6** characters
 * collide **45** times (38,216 distinct); the first **8** collide **0** times (38,261 distinct).
 * Eight is therefore the shortest prefix that is unique across the whole corpus, and it is also
 * the uuid's own first hyphen-delimited group — a boundary a reader can match against a log line
 * without counting characters. The full id is 36 characters and does not fit a 176px tile (the
 * grid's floor, UX-DR4) at any legible size.
 *
 * ONE LIMIT, DECLARED: the measurement is over the corpus, and the unknown
 * variant renders precisely ids that are NOT in it — `card_not_found` and malformed ids. For
 * that population no uniqueness claim is possible from here; the prefix's job there is weaker
 * and still real (match the same eight characters in a log line), and the full uuid's recovery
 * path is the log, not this element.
 */
export const CARD_ID_PREFIX_LENGTH = 8

/**
 * What each variant is given, and what it is structurally denied.
 *
 * A UNION, not a flat object with everything optional — see the component's header for the two
 * failures that choice closes at compile time.
 */
export type CardPlaceholderProps =
  | {
      /** The app knows exactly what this card is and only lacks its picture (`no_image_data`, `image_fetch_failed`). */
      variant: 'named-card'
      /** `CardSummary.name`, verbatim and UNSPLIT — see the `named` branch for why. */
      name?: string | null
      /** `CardSummary.mana_cost`. Blank for all 79 cards that permanently need this variant. */
      cost?: string | null
      /** `CardSummary.type_line`, verbatim — `'Card // Card'` included. */
      typeLine?: string | null
    }
  | {
      /** The app does not know what this card is at all (`card_not_found`, or a malformed id's `invalid_request`). */
      variant: 'unknown-card'
      /** The Scryfall printing uuid that could not be resolved. Truncated to {@link CARD_ID_PREFIX_LENGTH}. */
      cardId?: string | null
    }
  | {
      /** An `<img>` is in flight. The tile mounts this. No text, ever. */
      variant: 'loading'
    }

/**
 * A string prop that is actually there, or `null`.
 *
 * NOT A SECOND `filled()`. That helper answers *"does this ReactNode render anything"* and
 * returns a boolean; this one answers a STRING question and returns the value, because the id
 * must be narrowed before it can be sliced. It is the identical `typeof` + `trim()` spelling
 * `DeckBadges` and `ManaCost` both use, written once because this component asks it of three
 * props rather than three times in a row.
 *
 * **The `typeof` is a measured repair, not belt-and-braces.** `DeckBadges` once called
 * `format.trim()` behind a `!== null` check and threw `Cannot read properties of undefined` on a
 * partial deck: a presentation primitive that crashes the whole app on one absent prop is the
 * FR-13 posture inverted, and totality here costs one keyword. The wire types cannot produce
 * that today; a test, a future caller or an untyped runtime object can.
 *
 * Truthiness is banned outright and the reason is in `AppShell`: a `??` default fires only on
 * `undefined`, so a whitespace-only name would render a present, invisible, announced-as-empty
 * element — which is the exact shape a placeholder exists to prevent.
 *
 * **It returns the TRIMMED value, and that is load-bearing rather than cosmetic**: the guard
 * inspects the trimmed string, so returning the padded original would render
 * what the check never looked at — and on the id it is not cosmetic at all, because
 * `'  b3a40e8e…'.slice(0, 8)` is six real characters, quietly defeating the measured
 * 8-character uniqueness above.
 */
const given = (value: string | null | undefined): string | null => {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

export function CardPlaceholder(props: CardPlaceholderProps) {
  // THE WELL, FIRST AND WITHOUT READING ANYTHING ELSE. Branching on the variant before
  // any text is touched is what makes "wells stay silent" a property of the control flow rather
  // than a promise: there is no path from here to a rendered character.
  //
  // `aria-hidden` on an element that is already empty and unnamed is deliberate rather than
  // redundant — it is the DECLARATION that the silence is intended, and it is safe here in a way
  // it would not be in a component that took children: this one has no `ReactNode` prop at all,
  // so it can never hide a caller's content. The tile's `<img>` and its alt text sit BESIDE the
  // well, never inside it.
  if (props.variant === 'loading') {
    return <div className="card-shape card-placeholder-well" aria-hidden="true" />
  }

  // THE UNKNOWN VARIANT. Two words and eight characters, and nothing else exists to show.
  if (props.variant === 'unknown-card') {
    const cardId = given(props.cardId)
    return (
      <div className="card-shape card-placeholder">
        <span className="card-placeholder-name">{UNKNOWN_CARD_LABEL}</span>
        {cardId === null ? null : (
          <span className="card-placeholder-id">{cardId.slice(0, CARD_ID_PREFIX_LENGTH)}</span>
        )}
      </div>
    )
  }

  // THE NAMED VARIANT — pips above, name centred, type line below (UX-DR22, DESIGN.md).
  //
  // THE NAME IS RENDERED AS THE PAYLOAD CARRIES IT, `X // Y` INCLUDED. `frontFace()` exists
  // in `deckGroups.ts` and splitting would be one line, but `CardSummary` carries one `name` and
  // no `card_faces`, and UX-DR22 asks for *"the card name"* — which is what the client holds.
  // Splitting here would render `Memory Lapse` for a card the deck list, the detail panel and the
  // alt text all call `Memory Lapse // Memory Lapse`: four surfaces, two names. Face-specific
  // rendering belongs to the flip, where `CardFace` is already typed.
  //
  // Note what the fixtures cannot tell you, and why the tests use an `X // Y` card: all 79
  // permanent-population cards are `X // X`, so a split and a non-split produce IDENTICAL output
  // for 2,246 of the 3,194 split-named cards in the corpus — the obvious fixtures do not
  // discriminate the rule they appear to test.
  const name = given(props.name)
  const typeLine = given(props.typeLine)
  return (
    <div className="card-shape card-placeholder">
      {/* NO WRAPPER. `ManaCost` returns `null` for an absent, empty or whitespace-only
          cost — which is how ALL 79 cards that permanently need this variant arrive — so an
          element around it would survive its absence as a collapsed box and a stray gap. It also
          builds its own `role="img"` accessible name from `describeManaCost`, so the cost is
          announced exactly once and this component adds no second label for it. */}
      <ManaCost cost={props.cost} />
      {name === null ? null : <span className="card-placeholder-name">{name}</span>}
      {typeLine === null ? null : <span className="card-placeholder-type">{typeLine}</span>}
    </div>
  )
}

/**
 * The variant union and `states.ts` cannot drift apart — type-level, erased at build.
 *
 * Two asserts because there are two directions and each catches what the other cannot:
 *
 *   {@link EveryPlaceholderKeyHasProps} — a THIRD key added to `PlaceholderKey` has no member in
 *   {@link CardPlaceholderProps}, so `tsc` fails here naming the assert. This is the half that
 *   makes the `states.ts` classification load-bearing rather than decorative.
 *
 *   {@link NoVariantIsUnknownToStates} — the union WIDENED (to `string`, or to a literal
 *   `states.ts` never heard of) is the evasion that would otherwise pass everything: the first
 *   assert stays green because every key still has a member. `Exclude<string, …>` is `string`
 *   rather than `never`, so this one goes red.
 */
type Assert<T extends true> = T

type VariantWithProps = CardPlaceholderProps['variant']

export type EveryPlaceholderKeyHasProps = Assert<
  [Exclude<CardPlaceholderVariant, VariantWithProps>] extends [never] ? true : false
>

export type NoVariantIsUnknownToStates = Assert<
  [Exclude<VariantWithProps, PlaceholderKey | 'loading'>] extends [never] ? true : false
>
