import { useEffect } from 'react'

import { CardPlaceholder } from '../../components/CardPlaceholder/CardPlaceholder'
import type { AgentViewContent } from '../../state/agentView'
import { hydrateCard, useCardEntry, type CardEntry } from '../../state/cards'
import { useDeckCardQuantity } from '../../state/deck'
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
import './GroupsView.css'

/**
 * What a `groups` push puts INSIDE the agent view shell (story 16.3) — the fourth and last view
 * body, built as `TierListView.tsx`'s structural sibling, and every ruling that file carries
 * applies here unless a line below says otherwise.
 *
 * ================= WHAT IS DIFFERENT, AND WHY (DESIGN.md's group-section) ================
 *
 * A group is a SECTION rather than a chip-fronted row: the group's own title in
 * `{typography.heading}` with a bare numeral count in `{typography.numeric}`
 * `{colors.text-tertiary}` beside it, the rationale paragraph in `{typography.body}`
 * `{colors.text-secondary}` at the `components.group-section.measure` (900px), then a wrapping
 * thumbnail strip. Consecutive groups are separated by the cited hairline divider
 * (`components.group-section.divider`). The per-card hooks live on a module-local
 * {@link GroupTile} composed once per card, exactly as `TierTile` composes inside `TierRow`,
 * and each TILE is the `<button>` carrying the five inspection verbs.
 *
 * **The count is a bare numeral, deliberately** — the mock's "N cards" has no copy-cell source,
 * and an authored word would owe a `COPY_MODULES` entry this view exists without. It counts the
 * VALID card-id list the strip actually renders, so it never counts tiles that do not appear.
 *
 * **The quantity badge gates on ≥1, deliberately diverging from `CardTile`'s `> 1`**
 * (EXPERIENCE.md:94). In the deck grid every card is in the deck, so ×1 on ninety-eight of
 * ninety-nine tiles is noise; in a group, IN-DECK-NESS ITSELF is the signal — groups routinely
 * name cards the deck does not run — so ×1 is informative and truthful, and a card the deck
 * does not run carries no badge at all ("rendering '×0' would be a lie"). The badge is STATIC:
 * pushes replace wholesale, so there is no "change" for a flash to mark, and no `data-flashed`
 * exists here.
 *
 * **Empty groups are skipped, not rendered as empty shells** (EXPERIENCE.md:94) — a render-only
 * skip: the store's `count` is the payload's group count, raw, and this view never rewrites it.
 * Groups render in payload order; nothing here sorts, dedupes or merges.
 *
 * ================= THE SAME UNTRUSTED-ITEM DISCIPLINE, FIELD FOR FIELD ==================
 *
 * `groupsViewOf` validates the payload's SHAPE and deliberately no item field, so every field
 * below is read as `unknown` and gated before use. The gate INVERTS the tier item's
 * optionality: `title` and `rationale` are both REQUIRED non-blank on the wire (the title is
 * the only thing distinguishing one group from the next; the rationale is the paragraph the
 * group exists to carry), so a group missing or blanking either is malformed and degrades —
 * that group alone is skipped, its neighbours render (FR-13, AD-7). `card_ids` is optional and
 * an empty one is a DESIGNED case, reached by the same skip; a non-string, empty or
 * whitespace-only entry inside it is filtered per id (see `cardIdsOf`), and a group whose
 * every id fails that ladder skips too. A non-blank id that names no card degrades that
 * thumbnail alone, to the unknown-card placeholder when its hydration settles terminally,
 * while the group's text still renders.
 */
export interface GroupsViewProps {
  /**
   * The push's own `kind`, interpolated into the shared empty-push line. The template is
   * kind-generic (`{kind}`), so this module authors no second sentence — `emptyPushLine` is
   * reached across containers exactly as `imageUrl` is, its fourth reader, and
   * `tests/empty-push-copy.test.ts` keeps pinning the one copy.
   */
  readonly kind: AgentViewContent['kind']
  /** The pushed groups. Empty is legal and renders the artefact's sentence (AD-7, UX-DR33). */
  readonly items: Extract<AgentViewContent, { kind: 'groups' }>['items']
}

/**
 * One pushed group, as the STORE types it. NOT named after the wire's own `GroupItem` —
 * `tests/wire-contract.test.ts` bans any declaration outside `src/api/` whose name matches a
 * backend shape, the same guard that named `TierListView`'s alias.
 */
type PushedGroup = GroupsViewProps['items'][number]

/** The same group as it ACTUALLY arrives — every field `unknown`, because none was checked. */
type UntrustedGroup = { readonly [K in keyof PushedGroup]?: unknown }

/** A non-object array element degrades to the all-fields-absent group (TierListView's itemOf). */
const itemOf = (raw: unknown): UntrustedGroup =>
  typeof raw === 'object' && raw !== null ? raw : {}

/**
 * The group's title, TRIMMED, or `null` when it is missing, not a string, or blank. Blank is
 * malformed rather than absent-by-design — the wire refuses it (`min_length=1` plus the
 * non-blank validator) precisely because the title is the only thing distinguishing one group
 * from the next, so a group that arrives without one has nothing legal to head and degrades
 * whole. Returning the trimmed value keeps this fold symmetric with `groupsViewOf`'s
 * payload-level title, which is trimmed at the store — '  Ramp  ' renders as 'Ramp' at either
 * level rather than only one.
 */
const titleOf = (item: UntrustedGroup): string | null => {
  const value = item.title
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

/**
 * The rationale, TRIMMED, or `null` when missing, not a string, or blank — the same
 * degradation call and the same trim symmetry as {@link titleOf}, because the wire
 * non-blank-validates this field too: the paragraph is the group's argument, and a group
 * without one is malformed rather than merely terse.
 */
const rationaleOf = (item: UntrustedGroup): string | null => {
  const value = item.rationale
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

/**
 * The group's card ids, FILTERED per id rather than coerced: a non-string, empty or
 * whitespace-only entry is dropped — there is no honest tile for a number, and a blank id
 * names nothing the app could ever render, so keeping it would spend a permanently-dead
 * placeholder slot AND a real image request (a whitespace id is not `''`, so the synchronous
 * unknown guard cannot catch it before the first paint commits `/api/card-image/%20`). A
 * NON-blank id is NOT trimmed, for `SuggestionsView`'s recorded reason: the wire caps the
 * id's LENGTH without validating its shape (AD-7), so a padded copy of a real id is not this
 * component's to rewrite — it degrades to the unknown-card placeholder, which is a hydration
 * question and not this gate's. The returned list's length IS the section's rendered count —
 * the numeral and the strip read one list, so a dropped id never counts either.
 */
const cardIdsOf = (item: UntrustedGroup): readonly string[] =>
  Array.isArray(item.card_ids)
    ? item.card_ids.filter(
        (value): value is string => typeof value === 'string' && value.trim() !== '',
      )
    : []

/** Whatever the cache can render right now, as one shape — `SuggestionsView`'s renderableOf. */
const renderableOf = (entry: CardEntry | undefined) => {
  if (entry === undefined) return null
  return entry.status === 'hydrated' ? entry.card : entry.summary
}

/** The store's own "this id is not a card" predicate — `inspectable()`'s question, unshared. */
const isUnknownCard = (entry: CardEntry | undefined): boolean =>
  entry?.status === 'unknown' && entry.placeholder === 'unknown-card'

/**
 * The one glyph the badge prefixes — U+00D7 MULTIPLICATION SIGN, never the letter "x"
 * (`CardTile`'s own constant, re-declared rather than exported because a one-character constant
 * is not an API). The numeral beside it is wire-derived deck data, so no `COPY_MODULES` entry
 * is owed.
 */
const MULTIPLICATION_SIGN = '×'

/**
 * One card in one group's strip: a thumbnail inside one `<button>` carrying the standard
 * inspection contract (hover/focus set the detail target, click pins) — `TierTile`'s shape
 * plus the in-deck quantity badge.
 *
 * The badge reads {@link useDeckCardQuantity} — a primitive per-tile subscription, so a deck
 * write re-renders only the tiles whose count changed — and renders `×N` exactly when the
 * active deck runs this card at quantity ≥ 1: unknown-vs-off-deck are two different predicates
 * on the same tile (unknown id → placeholder, a hydration question; off-deck → no badge, a
 * deck-store question), and both legs are documented at the component header. With no deck
 * settled the selector answers `null` and no tile shows a badge.
 *
 * Everything else carries over from `TierTile` verbatim: the accessible name is the card's own
 * front-face name in a visually hidden span (`alt=""` by UX-DR48), every tile is the same
 * button whatever its entry's state, the store's `inspectable()` refuses the verbs on a dead
 * id, and the stale-target release effect is the same Greptile-P1 valve, per tile because
 * targets are per card.
 */
function GroupTile({ cardId }: { cardId: string }) {
  const entry = useCardEntry(cardId)
  const face = useFaceIndex(cardId)
  const { state: art, settleIfCached, onLoad, onError } = useCardArt(cardId, face)
  const quantity = useDeckCardQuantity(cardId)

  const renderable = renderableOf(entry)
  // No `cardId === ''` special case here, unlike `TierTile`: `cardIdsOf` filters blank and
  // whitespace-only ids out before any tile mounts, so this component never receives the
  // app's "an id the app cannot render" sentinel — the cache's terminal `unknown` is the one
  // remaining road to the placeholder.
  const unknown = isUnknownCard(entry)
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
      className="group-tile"
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
          The placeholder ladder is `TierTile`'s, unchanged: unknown → the unknown-card variant
          with the truncated id; picture failed → the named variant drawing what the cache
          knows; otherwise the silent well with the image over it. */}
      <span className="group-tile-thumb">
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
              className="card-shape group-tile-image"
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
        {/* THE QUANTITY BADGE (EXPERIENCE.md:94) — rendered IFF the active deck runs this card
            at ≥ 1 copy, which deliberately diverges from CardTile's `> 1` gate: there every
            card is in the deck and ×1 is noise; here in-deck-ness is the signal, so ×1 is
            informative and not-in-deck renders nothing ("×0 would be a lie"). STATIC — no
            flash, no `data-flashed`: pushes replace wholesale, so there is no change to mark. */}
        {quantity !== null && quantity >= 1 ? (
          <span className="group-tile-quantity">{`${MULTIPLICATION_SIGN}${quantity}`}</span>
        ) : null}
      </span>
    </button>
  )
}

/**
 * One group (DESIGN.md's group-section): the title in heading type with the bare numeral count
 * beside it, the rationale paragraph at the cited measure, and the wrapping thumbnail strip.
 * Callers pass only fields that already survived the gates — a group that could not produce a
 * non-blank title, a non-blank rationale and at least one renderable card id never reaches
 * this component (the degrade-and-skip lives in {@link GroupsView}, where the neighbours keep
 * rendering).
 */
function GroupSection({
  title,
  rationale,
  cardIds,
}: {
  title: string
  rationale: string
  cardIds: readonly string[]
}) {
  return (
    <div className="group-section">
      {/* THE HEAD — title in `{typography.heading}` with the count in `{typography.numeric}`
          `{colors.text-tertiary}` beside it (DESIGN.md:592). The count is a BARE NUMERAL: it
          is the length of the very list the strip below maps, so the two cannot disagree, and
          no authored word rides beside it (the mock's "N cards" has no copy-cell source). */}
      <span className="group-section-head">
        <span className="group-section-title">{title}</span>
        <span className="group-section-count">{cardIds.length}</span>
      </span>
      {/* THE RATIONALE — `{typography.body}` `{colors.text-secondary}` at the cited 900px
          measure (DESIGN.md `components.group-section.measure`). It WRAPS rather than
          truncating: the wire caps it at 600 characters and the artefact calls it a paragraph,
          so the words the agent actually said stay readable. */}
      <span className="group-section-rationale">{rationale}</span>
      {/* THE STRIP — payload order, wrapping (DESIGN.md:592's "wrapped tile row"; the
          flex-wrap precedents are AgentView.css:106 and ColourDistribution.css:173). Keyed by
          id AND position for the suggestion list's duplicate-tolerance reason: nothing
          constrains an agent against grouping the same printing twice. */}
      <span className="group-section-thumbs">
        {cardIds.map((cardId, index) => (
          <GroupTile key={`${cardId}:${index}`} cardId={cardId} />
        ))}
      </span>
    </div>
  )
}

export function GroupsView({ kind, items }: GroupsViewProps) {
  /* HYDRATION IS THIS VIEW'S OWN (AD-12), per `TierListView`'s effect verbatim: each group
     carries MANY ids, and the `Set` collapses duplicates across groups as well as within one —
     a card grouped twice costs one request. Keyed on `items`, not on mount: replace-in-place
     re-fires against a mounted shell. Skipped groups' valid ids hydrate too, deliberately —
     the skip is render-only, and a duplicate id shared with a healthy group must find the
     cache warm either way (the 16.2 pinned behaviour, mirrored). */
  useEffect(() => {
    const ids = new Set<string>()
    for (const raw of items) for (const cardId of cardIdsOf(itemOf(raw))) ids.add(cardId)
    for (const cardId of ids) void hydrateCard(cardId)
  }, [items])

  /* THE GATE AND THE SKIP, IN ONE PASS (EXPERIENCE.md:94, FR-13/AD-7). A group renders exactly
     when it has a non-blank title, a non-blank rationale and at least one renderable card id:
     an EMPTY group is skipped by specification ("Empty groups are skipped" — title and
     rationale included, never an empty shell) and a MALFORMED one — title or rationale
     missing or blank — degrades to the same skip, taking no neighbour with it. A group whose
     every id failed the per-id filter is empty by the time this gate reads it and skips by the
     same road. The original payload index rides along so keys stay stable across the skip. */
  const sections = items.flatMap((raw, index) => {
    const item = itemOf(raw)
    const title = titleOf(item)
    const rationale = rationaleOf(item)
    const cardIds = cardIdsOf(item)
    if (title === null || rationale === null || cardIds.length === 0) return []
    return [{ title, rationale, cardIds, index }]
  })

  if (sections.length !== 0) {
    return (
      /* A REAL `ul`/`li` (UX-DR44) — the list semantics tell a screen-reader user how many
         groups survived to the glass before they start moving through them. The hairline
         divider between consecutive items is the cited `components.group-section.divider`. */
      <ul className="groups-view-sections">
        {sections.map((section) => (
          <li className="groups-view-item" key={`${section.title}:${section.index}`}>
            <GroupSection
              title={section.title}
              rationale={section.rationale}
              cardIds={section.cardIds}
            />
          </li>
        ))}
      </ul>
    )
  }

  // The SHARED empty-push line, `{kind}`-substituted — one template, one owner, fourth reader
  // (the copy module's whole design). A bare `<p>` replacing the `<ul>`, never inside it. It
  // renders for an empty `items` AND for a push whose every group was skipped: an empty `<ul>`
  // would announce "list, 0 items" with nothing to explain why, and the sentence is the closest
  // honest description of a glass with nothing on it — no second sentence is authored.
  return <p className="groups-view-empty">{emptyPushLine(kind)}</p>
}
