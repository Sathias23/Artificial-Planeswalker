import { useEffect } from 'react'

import { CardPlaceholder } from '../../components/CardPlaceholder/CardPlaceholder'
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
import { frontFaceName } from '../frontFaceCost'
import { useCardArt } from '../useCardArt'
import { emptyPushLine } from '../SuggestionsView/copy'
import './TierListView.css'

/**
 * What a `tier_list` push puts INSIDE the agent view shell (story 16.2) — the third view body,
 * built as `SwapsView.tsx`'s structural sibling, and every ruling that file carries applies
 * here unless a line below says otherwise.
 *
 * ================= WHAT IS DIFFERENT, AND WHY (DESIGN.md's tier-row) =====================
 *
 * A tier row renders MANY cards — a chip carrying the tier's letter and name, then a note and a
 * wrapping thumbnail strip — so the per-card hooks live on a module-local {@link TierTile}
 * composed once per card inside a module-local {@link TierRow}, exactly as `SwapTile` composes
 * twice inside `SwapRow`. Each TILE is the `<button>` carrying the five inspection verbs (a
 * row-level button would make one gesture mean up to sixty cards).
 *
 * The tier letter drives DESIGN.md:590's five-stop ramp — `accent-bright` (S) · `accent` (A) ·
 * `text-primary` (B) · `text-secondary` (C) · `text-tertiary` (D) — and the letter is ALWAYS
 * accompanied by its `name` in micro `text-tertiary` beneath, because colour is never the sole
 * carrier of rank (`contracts.py`: the name is "the accessible carrier of rank", which is why
 * the wire refuses a blank one). At 44px the letters are large text, so all five stops clear
 * the contrast floor. NO `--accent-dim` anywhere: this row's background is `surface-overlay`,
 * the one surface where accent-dim fails the 3:1 non-text floor (DESIGN.md:506).
 *
 * **Empty tiers are skipped, not rendered as empty shells** (DESIGN.md:590) — a render-only
 * skip: the store's `count` is the payload's tier count, raw, and this view never rewrites it.
 * Tiers render in payload order; nothing here sorts by letter, dedupes or re-orders, and two
 * tiers sharing a letter under different names both render (`contracts.py`: "the agent's
 * ordering is the agent's argument").
 *
 * ================= THE SAME UNTRUSTED-ITEM DISCIPLINE, FIELD FOR FIELD ==================
 *
 * `tierListViewOf` validates the payload's SHAPE and deliberately no item field, so every field
 * below is read as `unknown` and gated before use. A tier whose `letter` is outside the closed
 * five-value vocabulary or whose `name` is missing or blank degrades — that tier alone is
 * skipped, its neighbours render (FR-13, AD-7: one bad entry degrades, the push never fails
 * wholesale). The letter has no honest fallback stop on a five-stop ramp and the name is the
 * accessible carrier of rank, so a partial row would either invent a colour or break the floor
 * the wire's own `min_length=1` exists to hold. A bad id INSIDE a healthy tier degrades that
 * thumbnail alone, to the unknown-card placeholder through `hydrateCard('')`'s existing
 * terminal refusal, while the tier's text still renders.
 */
export interface TierListViewProps {
  /**
   * The push's own `kind`, which the shared empty-push line maps to its display noun. The
   * template is kind-generic (`{noun}`), so this module authors no second sentence —
   * `emptyPushLine` is reached across containers exactly as `imageUrl` is, and
   * `tests/empty-push-copy.test.ts` keeps pinning the one copy.
   */
  readonly kind: AgentViewContent['kind']
  /** The pushed tiers. Empty is legal and renders the artefact's sentence (AD-7, UX-DR33). */
  readonly items: Extract<AgentViewContent, { kind: 'tier_list' }>['items']
}

/**
 * One pushed tier, as the STORE types it. NOT named after the wire's own `TierItem` —
 * `tests/wire-contract.test.ts` bans any declaration outside `src/api/` whose name matches a
 * backend shape, the same guard that named `SwapsView`'s alias.
 */
type PushedTier = TierListViewProps['items'][number]

/** The same tier as it ACTUALLY arrives — every field `unknown`, because none was checked. */
type UntrustedTier = { readonly [K in keyof PushedTier]?: unknown }

/** A non-object array element degrades to the all-fields-absent tier (SuggestionsView's itemOf). */
const itemOf = (raw: unknown): UntrustedTier => (typeof raw === 'object' && raw !== null ? raw : {})

/** The closed letter vocabulary, membership-tested for the confidence tokens' slot-shaped reason:
 * the letter lands in a 44px glyph slot driving a five-stop colour ramp, and an arbitrary wire
 * string there would be a paragraph in a slot sized for one character with no colour to be. */
type LetterToken = PushedTier['letter']

const TIER_LETTERS = ['S', 'A', 'B', 'C', 'D'] as const satisfies readonly LetterToken[]

type Assert<T extends true> = T

export type EveryTierLetterRenders = Assert<
  [Exclude<LetterToken, (typeof TIER_LETTERS)[number]>] extends [never] ? true : false
>

/** The tier's letter, or `null` when absent or outside the closed five-value vocabulary. */
const letterOf = (item: UntrustedTier): LetterToken | null => {
  const value = item.letter
  if (typeof value !== 'string') return null
  return TIER_LETTERS.find((token) => token === value) ?? null
}

/**
 * The tier's name, or `null` when it is missing, not a string, or blank. Blank is malformed
 * rather than absent-by-design — the wire refuses it (`min_length=1` plus the non-blank
 * validator) precisely because the name is the accessible carrier of rank, so a tier that
 * arrives without one has nothing legal to render and degrades whole.
 */
const nameOf = (item: UntrustedTier): string | null => {
  const value = item.name
  if (typeof value !== 'string') return null
  return value.trim() === '' ? null : value
}

/** The note, or `null` — absent is a designed case (the wire's `note` is optional), so no
 * element renders at all rather than an empty line: unlike the swap rationale, a missing note
 * is not malformed, and the row's height is honest either way. Whitespace-only folds to `null`
 * too, and unlike the name this is not a degradation call: `contracts.py` blank-checks `name`
 * but caps `note` by length alone, so a blank note is WIRE-LEGAL and the only question is
 * whether to spend a gap row on an empty element — no (the swap rationale needs no such fold
 * because its field is non-blank-validated on the wire). */
const noteOf = (item: UntrustedTier): string | null => {
  const value = item.note
  if (typeof value !== 'string') return null
  return value.trim() === '' ? null : value
}

/**
 * A tile's card id, or `''` — the app's own value for *"an id the app cannot render"*:
 * `hydrateCard('')` refuses it terminally with the unknown-card placeholder and issues no
 * request. NOT trimmed, for `SuggestionsView`'s recorded reason: the wire caps the id's LENGTH
 * without validating its shape (AD-7), so a padded id is not this component's to rewrite.
 */
const cardIdOf = (value: unknown): string => (typeof value === 'string' ? value : '')

/** The tier's card ids, each gated to a string — a non-array `card_ids` degrades to the empty
 * tier, which the skip below already handles (DESIGN.md:590's rule, reached by a second road). */
const cardIdsOf = (item: UntrustedTier): readonly string[] =>
  Array.isArray(item.card_ids) ? item.card_ids.map(cardIdOf) : []

/** Whatever the cache can render right now, as one shape — `SuggestionsView`'s renderableOf. */
const renderableOf = (entry: CardEntry | undefined) => {
  if (entry === undefined) return null
  return entry.status === 'hydrated' ? entry.card : entry.summary
}

/** The store's own "this id is not a card" predicate — `inspectable()`'s question, unshared. */
const isUnknownCard = (entry: CardEntry | undefined): boolean =>
  entry?.status === 'unknown' && entry.placeholder === 'unknown-card'

/**
 * One card in one tier's strip: a thumbnail inside one `<button>` carrying the standard
 * inspection contract (hover/focus set the detail target, click pins) — `SwapTile`'s shape
 * minus the direction label, which this row does not have.
 *
 * The button's accessible name is the card's own name, in a visually hidden span (the promoted
 * `.visually-hidden` utility): the image's `alt` is `""` by UX-DR48 — the card's name is the
 * detail panel's to speak on inspection — but a nameless button would leave a screen-reader
 * user tabbing through anonymous stops. The name is WIRE DATA read from the card cache, never
 * an authored word, so no `COPY_MODULES` entry is owed; before hydration lands the span is
 * empty, exactly as the suggestion row's name column is.
 *
 * The unknown-row rulings carry over verbatim from `SwapTile`: every tile is the same button
 * (an entry moves `undefined → loading → unknown` while rendered, and a vanishing button would
 * drop focus to `<body>` inside the shell's focus trap), the store's `inspectable()` is what
 * refuses the verbs on a dead id, and the stale-target release effect below is the same
 * Greptile-P1 valve, per tile because targets are per card.
 */
function TierTile({ cardId }: { cardId: string }) {
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

  return (
    <button
      type="button"
      className="tier-tile"
      /* THE FIVE VERBS, UNRENAMED AND UNWRAPPED (UX-DR14, UX-DR20) — both clears keyed by id,
         for the two-transient-slots reason `SuggestionRow` records: the losing tile's clear is
         free to land second. What an id MEANS is the slice's; `onClick` serves mouse and
         keyboard alike, and the store refuses every verb on an unknown id. */
      onMouseEnter={() => setHovered(cardId)}
      onMouseLeave={() => clearHovered(cardId)}
      onFocus={() => setFocused(cardId)}
      onBlur={() => clearFocused(cardId)}
      onClick={() => togglePin(cardId)}
    >
      {/* THE ACCESSIBLE NAME — wire data from the cache, empty until hydration lands (see the
          component header). Front face only, `DeckRow`'s reason: the combined `X // Y` string
          belongs on the detail panel. */}
      <span className="visually-hidden">
        {renderable === null ? '' : frontFaceName(renderable.name)}
      </span>
      {/* THE THUMBNAIL SLOT — fixed shape from the first frame, never reflowing (UX-DR36).
          The placeholder ladder is `SwapTile`'s, unchanged: unknown → the unknown-card variant
          with the truncated id; picture failed → the named variant drawing what the cache
          knows; otherwise the silent well with the image over it. */}
      <span className="tier-tile-thumb">
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
              className="card-shape tier-tile-image"
              data-loaded={art === 'shown' ? 'true' : 'false'}
              /* AD-11: the backend proxy, never a CDN host; rendition UNSPELLED so the bytes
                 share the grid's browser-cache key (SuggestionsView's Q4). */
              src={cardImageUrl(cardId, undefined, face)}
              /* `alt=""`, EXACTLY (UX-DR48): the tile's accessible name is the hidden span
                 above, and the card's name is the detail panel's to speak. */
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
 * One tier (DESIGN.md's tier-row): the 132px chip on `surface-well` carrying the ramped letter
 * with its name beneath, then the optional note in body `text-secondary` and the wrapping
 * thumbnail strip. Callers pass only fields that already survived the gates — a tier that could
 * not produce a legal letter, name and at least one card never reaches this component (the
 * degrade-and-skip lives in {@link TierListView}, where the neighbours keep rendering).
 */
function TierRow({
  letter,
  name,
  note,
  cardIds,
}: {
  letter: LetterToken
  name: string
  note: string | null
  cardIds: readonly string[]
}) {
  return (
    <div className="tier-row">
      {/* THE CHIP — letter over name, and the LETTER NEVER STANDS ALONE (DESIGN.md:590,
          contracts.py): the name in text is the accessible carrier of rank, so colour is never
          the sole signal. The ramp hangs on `data-letter`, one attribute driving five stops. */}
      <span className="tier-chip">
        <span className="tier-chip-letter" data-letter={letter} aria-hidden="true">
          {letter}
        </span>
        <span className="tier-chip-name">{name}</span>
      </span>
      <span className="tier-row-body">
        {/* THE NOTE — optional on the wire by design, so absent means NO element rather than an
            empty line (see `noteOf`; the swap rationale's unconditional-line rule is about a
            REQUIRED field arriving malformed, which this is not). */}
        {note === null ? null : <span className="tier-row-note">{note}</span>}
        {/* THE STRIP — payload order, wrapping (DESIGN.md:590's "thumbnail row"; the flex-wrap
            precedent is AgentView.css and ColourDistribution.css). Keyed by id AND position for
            the suggestion list's duplicate-tolerance reason: nothing constrains an agent
            against ranking the same printing twice. */}
        <span className="tier-row-thumbs">
          {cardIds.map((cardId, index) => (
            <TierTile key={`${cardId}:${index}`} cardId={cardId} />
          ))}
        </span>
      </span>
    </div>
  )
}

export function TierListView({ kind, items }: TierListViewProps) {
  /* HYDRATION IS THIS VIEW'S OWN (AD-12), per `SuggestionsView`'s effect with `SwapsView`'s
     widening: each tier carries MANY ids, and the `Set` collapses duplicates across tiers as
     well as within one — a card ranked twice costs one request. Keyed on `items`, not on
     mount: replace-in-place re-fires against a mounted shell. Skipped tiers' ids hydrate too,
     deliberately — the skip is render-only, and the same push re-opened from the pill after a
     malformed tier heals (it cannot; but a duplicate id shared with a healthy tier can) must
     find the cache warm either way. */
  useEffect(() => {
    const ids = new Set<string>()
    for (const raw of items) for (const cardId of cardIdsOf(itemOf(raw))) ids.add(cardId)
    for (const cardId of ids) void hydrateCard(cardId)
  }, [items])

  /* THE GATE AND THE SKIP, IN ONE PASS (DESIGN.md:590, FR-13/AD-7). A tier renders exactly when
     it has a legal letter, a non-blank name and at least one card id: an EMPTY tier is skipped
     by specification ("skipped, not rendered as empty shells") and a MALFORMED one — letter
     outside the closed vocabulary, name missing or blank — degrades to the same skip, taking no
     neighbour with it. The original payload index rides along so keys stay stable across the
     skip. */
  const rows = items.flatMap((raw, index) => {
    const item = itemOf(raw)
    const letter = letterOf(item)
    const name = nameOf(item)
    const cardIds = cardIdsOf(item)
    if (letter === null || name === null || cardIds.length === 0) return []
    return [{ letter, name, note: noteOf(item), cardIds, index }]
  })

  if (rows.length !== 0) {
    return (
      /* A REAL `ul`/`li` (UX-DR44) — the list semantics tell a screen-reader user how many
         tiers survived to the glass before they start moving through them. */
      <ul className="tier-list-rows">
        {rows.map((row) => (
          <li className="tier-list-item" key={`${row.letter}:${row.name}:${row.index}`}>
            <TierRow letter={row.letter} name={row.name} note={row.note} cardIds={row.cardIds} />
          </li>
        ))}
      </ul>
    )
  }

  // The SHARED empty-push line, noun-substituted — one template, one owner, third reader
  // (the copy module's whole design). A bare `<p>` replacing the `<ul>`, never inside it. It
  // renders for an empty `items` AND for a push whose every tier was skipped: an empty `<ul>`
  // would announce "list, 0 items" with nothing to explain why, and the sentence is the closest
  // honest description of a glass with nothing on it — no second sentence is authored.
  // In the all-skipped case the shell header keeps showing the RAW store count beside this line
  // (e.g. "5" over "came back empty") — decided at the epic-16 retro (item 4, in passing): the
  // count states what the agent SENT and the sentence states what RENDERS, and
  // count-stays-raw-while-render-skips is a pinned epic invariant (App.test.tsx's "count still
  // says 2" against 1 rendered row), not a contradiction to smooth over.
  return <p className="tier-list-view-empty">{emptyPushLine(kind)}</p>
}
