import { useEffect } from 'react'

import { CardPlaceholder } from '../../components/CardPlaceholder/CardPlaceholder'
import { StatChip } from '../../components/StatChip/StatChip'
import type { AgentViewContent } from '../../state/agentView'
import { hydrateCard, useCardEntry, type CardEntry } from '../../state/cards'
import { useFaceIndex } from '../../state/faces'
import {
  clearFocused,
  clearHovered,
  clearPin,
  setFocused,
  setHovered,
  togglePin,
  usePinnedId,
} from '../../state/inspection'
import { cardImageUrl } from '../CardTile/imageUrl'
import { useCardArt } from '../useCardArt'
import { emptyPushLine } from '../SuggestionsView/copy'
import './SwapsView.css'

/**
 * What a `swaps` push puts INSIDE the agent view shell (story 16.1) — the second view body,
 * built as `SuggestionsView.tsx`'s structural sibling, and every ruling that file carries
 * applies here unless a line below says otherwise.
 *
 * ================= WHAT IS DIFFERENT, AND WHY (DESIGN.md's swap-row) =====================
 *
 * A swap row renders TWO cards — out and in, joined by an accent arrow — so the per-card hooks
 * cannot live on the row: hooks per card means a module-local {@link SwapTile} composed twice
 * inside a module-local {@link SwapRow}. Each TILE is the `<button>` carrying the five
 * inspection verbs (a row-level button would make one gesture mean two cards), which is the one
 * structural departure from the suggestion row's single-button shape — `CardTile`'s
 * one-button-per-card precedent, at thumbnail scale.
 *
 * The out/in tints (`--negative`/`--positive`) sit on the micro LABELS only, never on the art —
 * DESIGN.md's swap-row is emphatic — and the arrow is `var(--accent)`: `accent-dim` measures
 * 2.70:1 on `surface-overlay` and fails the 3:1 non-text floor, the correction the artefact
 * already made for the card-detail ring and the suggestion row's live marker.
 *
 * The artefact's chip row beneath the rationale names price, curve and confidence. Price and
 * curve do NOT ship, deliberately: the wire carries no price by ruling (`types.d.ts` — the card
 * table has no price column and the importer never reads `prices`), and a curve chip would need
 * the same wire field the same ruling declined. What remains is the one datum the wire does
 * carry — confidence — rendered as a real `StatChip` (label "Confidence", value = the wire
 * token, no delta: a confidence is a reading, not a change since a previous one).
 *
 * ================= THE SAME UNTRUSTED-ITEM DISCIPLINE, FIELD FOR FIELD ==================
 *
 * `swapsViewOf` validates the payload's SHAPE and deliberately no item field, so every field
 * below is read as `unknown` and gated before use, and a malformed entry degrades that row
 * ALONE (FR-13, AD-7): a bad id lands one tile on the unknown-card placeholder through
 * `hydrateCard('')`'s existing terminal refusal, a bad quantity drops that label's count, a bad
 * rationale renders an empty line whose element stays for layout honesty. One push failing one
 * row, never the push failing wholesale.
 */
export interface SwapsViewProps {
  /**
   * The push's own `kind`, interpolated into the shared empty-push line. The template is
   * kind-generic (`{noun}`), so this module authors no second sentence — `emptyPushLine` is
   * reached across containers exactly as `imageUrl` is, and `tests/empty-push-copy.test.ts`
   * keeps pinning the one copy.
   */
  readonly kind: AgentViewContent['kind']
  /** The pushed trades. Empty is legal and renders the artefact's sentence (AD-7, UX-DR33). */
  readonly items: Extract<AgentViewContent, { kind: 'swaps' }>['items']
}

/**
 * One pushed swap, as the STORE types it. NOT named after the wire's own `SwapItem` —
 * `tests/wire-contract.test.ts` bans any declaration outside `src/api/` whose name matches a
 * backend shape, the same guard that named `SuggestionsView`'s alias.
 */
type PushedSwap = SwapsViewProps['items'][number]

/** The same item as it ACTUALLY arrives — every field `unknown`, because none was checked. */
type UntrustedSwap = { readonly [K in keyof PushedSwap]?: unknown }

/** A non-object array element degrades to the all-fields-absent item (SuggestionsView's itemOf). */
const itemOf = (raw: unknown): UntrustedSwap => (typeof raw === 'object' && raw !== null ? raw : {})

/** The closed confidence vocabulary, membership-tested for the same slot-shaped reason. */
type ConfidenceToken = NonNullable<PushedSwap['confidence']>

const CONFIDENCE_TOKENS = ['low', 'medium', 'high'] as const satisfies readonly ConfidenceToken[]

type Assert<T extends true> = T

export type EveryConfidenceTokenRenders = Assert<
  [Exclude<ConfidenceToken, (typeof CONFIDENCE_TOKENS)[number]>] extends [never] ? true : false
>

/**
 * A tile's card id, or `''` — the app's own value for *"an id the app cannot render"*:
 * `hydrateCard('')` refuses it terminally with the unknown-card placeholder and issues no
 * request, which routes a malformed item into the degradation the matrix already describes.
 * A WHITESPACE-ONLY id folds to `''` too (E16-91, `GroupsView.cardIdsOf`'s gate in the
 * single-id shape): it names nothing the app could ever render, and unlike `''` the
 * synchronous unknown guard cannot catch it before the first paint commits
 * `/api/card-image/%20` — so it takes the same terminal unknown-card arm, never a request.
 * A NON-blank id is NOT trimmed, for `SuggestionsView`'s recorded reason: the wire caps the
 * id's LENGTH without validating its shape (AD-7), so a padded copy of a real id is not this
 * component's to rewrite.
 */
const cardIdOf = (value: unknown): string =>
  typeof value === 'string' && value.trim() !== '' ? value : ''

/** The rationale, or `''` — the row keeps its line either way (see {@link SwapRow}). */
const rationaleOf = (item: UntrustedSwap): string =>
  typeof item.rationale === 'string' ? item.rationale : ''

/**
 * A quantity, or `null` when the wire's `ge=0` integer did not arrive as one. `null` drops the
 * count from that tile's label rather than fabricating a number the agent never sent — the
 * label degrades to the bare direction word, one field costing one slot.
 */
const qtyOf = (value: unknown): number | null =>
  typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : null

/** The confidence, or `null` when absent or outside the three-token vocabulary. */
const confidenceOf = (item: UntrustedSwap): ConfidenceToken | null => {
  const value = item.confidence
  if (typeof value !== 'string') return null
  return CONFIDENCE_TOKENS.find((token) => token === value) ?? null
}

/** Whatever the cache can render right now, as one shape — `SuggestionsView`'s renderableOf. */
const renderableOf = (entry: CardEntry | undefined) => {
  if (entry === undefined) return null
  return entry.status === 'hydrated' ? entry.card : entry.summary
}

/** The store's own "this id is not a card" predicate — `inspectable()`'s question, unshared. */
const isUnknownCard = (entry: CardEntry | undefined): boolean =>
  entry?.status === 'unknown' && entry.placeholder === 'unknown-card'

/**
 * One side of one trade: the tinted micro label above a card thumbnail, inside one `<button>`
 * carrying the standard inspection contract (hover/focus set the detail target, click pins).
 *
 * The label lives INSIDE the button so an image tile (whose `alt` is `""` by UX-DR48 — the
 * card's name is the detail panel's to speak) still has an accessible name: "Out · 2 copies" is
 * what a screen reader calls the control. `contracts.py` fixes the label as the literal
 * `"Out · N copies"` / `"In · N copies"` — plural always, zero included ("0 copies" is a
 * designed case), no singular form specified anywhere and none invented here.
 *
 * The unknown-row rulings carry over verbatim from `SuggestionRow`: every tile is the same
 * button (an entry moves `undefined → loading → unknown` while rendered, and a vanishing button
 * would drop focus to `<body>` inside the shell's focus trap), the store's `inspectable()` is
 * what refuses the verbs on a dead id, and the stale-target release effect below is the same
 * Greptile-P1 valve, per tile because targets are per card.
 */
function SwapTile({
  direction,
  cardId,
  qty,
}: {
  direction: 'out' | 'in'
  cardId: string
  qty: number | null
}) {
  const entry = useCardEntry(cardId)
  const face = useFaceIndex(cardId)
  const { state: art, settleIfCached, onLoad, onError } = useCardArt(cardId, face)

  const renderable = renderableOf(entry)
  // Known synchronously for a malformed id, before hydration settles — without it the first
  // paint would commit a real `<img src="/api/card-image/">` request for one render.
  const unknown = isUnknownCard(entry) || cardId === ''
  const pinnedId = usePinnedId()

  // Release a stale hover, focus or pin the moment hydration settles to a terminal `unknown`
  // (SuggestionRow's effect, verbatim): `inspectable()` treats an in-flight entry as
  // inspectable, so a real interaction can race past it before the settle lands.
  useEffect(() => {
    if (!unknown) return
    clearHovered(cardId)
    clearFocused(cardId)
    if (pinnedId === cardId) clearPin()
  }, [unknown, cardId, pinnedId])

  // The artefact's literal, assembled from wire data: `direction` is this module's own closed
  // two-value discriminant and `qty` is a payload number, so no sentence is authored — and a
  // malformed quantity degrades the label to the bare direction word rather than to "NaN".
  const word = direction === 'out' ? 'Out' : 'In'
  const label = qty === null ? word : `${word} · ${qty} copies`

  return (
    <button
      type="button"
      className="swap-tile"
      /* THE FIVE VERBS, UNRENAMED AND UNWRAPPED (UX-DR14, UX-DR20) — both clears keyed by id,
         for the two-transient-slots reason `SuggestionRow` records: the losing row's clear is
         free to land second. What an id MEANS is the slice's; `onClick` serves mouse and
         keyboard alike, and the store refuses every verb on an unknown id. */
      onMouseEnter={() => setHovered(cardId)}
      onMouseLeave={() => clearHovered(cardId)}
      onFocus={() => setFocused(cardId)}
      onBlur={() => clearFocused(cardId)}
      onClick={() => togglePin(cardId)}
    >
      {/* THE TINTED LABEL — the ONLY element the out/in tints touch, never the art below. */}
      <span className={`swap-tile-label swap-tile-label-${direction}`}>{label}</span>
      {/* THE THUMBNAIL SLOT — fixed shape from the first frame, never reflowing (UX-DR36).
          The placeholder ladder is `SuggestionRow`'s, unchanged: unknown → the unknown-card
          variant with the truncated id; picture failed → the named variant drawing what the
          cache knows; otherwise the silent well with the image over it. */}
      <span className="swap-tile-thumb">
        {unknown ? (
          <CardPlaceholder variant="unknown-card" cardId={cardId} />
        ) : art === 'failed' ? (
          <CardPlaceholder
            variant="named-card"
            name={renderable?.name ?? null}
            cost={renderable?.mana_cost ?? null}
            typeLine={renderable?.type_line ?? null}
          />
        ) : (
          <>
            <CardPlaceholder variant="loading" />
            <img
              ref={settleIfCached}
              className="card-shape swap-tile-image"
              data-loaded={art === 'shown' ? 'true' : 'false'}
              /* AD-11: the backend proxy, never a CDN host; rendition UNSPELLED so the bytes
                 share the grid's browser-cache key (SuggestionsView's Q4). */
              src={cardImageUrl(cardId, undefined, face)}
              /* `alt=""`, EXACTLY (UX-DR48): the tile's accessible name is the label above, and
                 the card's name is the detail panel's to speak. */
              alt=""
              decoding="async"
              onLoad={onLoad}
              onError={onError}
            />
          </>
        )}
      </span>
    </button>
  )
}

/**
 * One trade (DESIGN.md's swap-row): out tile → accent arrow → in tile, with the rationale in
 * body `text-secondary` right of the pair and the confidence token beneath it. The rationale
 * element is UNCONDITIONAL for the suggestion-reason's layout-honesty reason — a missing field
 * is a malformed item, and dropping the line would change the row's height silently.
 */
function SwapRow({ item }: { item: UntrustedSwap }) {
  const confidence = confidenceOf(item)
  return (
    <div className="swap-row">
      <SwapTile direction="out" cardId={cardIdOf(item.out_card_id)} qty={qtyOf(item.out_qty)} />
      {/* The joining glyph is decorative — the labels already say which side is which — so it is
          hidden from the accessibility tree rather than read as "rightwards arrow". */}
      <span className="swap-row-arrow" aria-hidden="true">
        →
      </span>
      <SwapTile direction="in" cardId={cardIdOf(item.in_card_id)} qty={qtyOf(item.in_qty)} />
      <span className="swap-row-text">
        <span className="swap-row-rationale">{rationaleOf(item)}</span>
        {/* THE ONE CHIP OF DESIGN.md's chip row (see the module header for the two that do not
            ship). The label is this module's authored word — declared in COPY_MODULES — and the
            value is the wire token verbatim. No `delta`: a confidence is a reading, not a change.
            Absent ⇒ no chip at all: a chip is only mounted to show a stat (StatChip's own
            contract), and an empty one would be chrome announcing nothing. */}
        {confidence === null ? null : <StatChip label="Confidence" value={confidence} />}
      </span>
    </div>
  )
}

export function SwapsView({ kind, items }: SwapsViewProps) {
  /* HYDRATION IS THIS VIEW'S OWN (AD-12), per `SuggestionsView`'s effect with one widening:
     each item carries TWO ids, and the `Set` collapses duplicates across sides as well as
     across rows — a swap list that trades one staple in and out costs one request. Keyed on
     `items`, not on mount: replace-in-place re-fires against a mounted shell. */
  useEffect(() => {
    const ids = new Set<string>()
    for (const raw of items) {
      const item = itemOf(raw)
      ids.add(cardIdOf(item.out_card_id))
      ids.add(cardIdOf(item.in_card_id))
    }
    for (const cardId of ids) void hydrateCard(cardId)
  }, [items])

  if (items.length !== 0) {
    return (
      /* A REAL `ul`/`li` (UX-DR44) — the list semantics tell a screen-reader user how many
         trades arrived before they start moving through them. */
      <ul className="swaps-view-rows">
        {items.map((raw, index) => {
          const item = itemOf(raw)
          /* Keyed by BOTH ids and position, for the suggestion list's duplicate-tolerance
             reason: nothing constrains an agent against proposing the same trade twice. */
          return (
            <li
              className="swaps-view-item"
              key={`${cardIdOf(item.out_card_id)}:${cardIdOf(item.in_card_id)}:${index}`}
            >
              <SwapRow item={item} />
            </li>
          )
        })}
      </ul>
    )
  }

  // The SHARED empty-push line, noun-substituted — one template, one owner, second reader
  // (the copy module's whole design). A bare `<p>` replacing the `<ul>`, never inside it.
  return <p className="swaps-view-empty">{emptyPushLine(kind)}</p>
}
