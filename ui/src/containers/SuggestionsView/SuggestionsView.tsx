import { useEffect } from 'react'

import { Badge } from '../../components/Badge/Badge'
import { CardPlaceholder } from '../../components/CardPlaceholder/CardPlaceholder'
import { ManaCost } from '../../components/ManaCost/ManaCost'
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
  useIsLiveTarget,
  usePinnedId,
} from '../../state/inspection'
import { cardImageUrl } from '../CardTile/imageUrl'
import { frontFaceCost, frontFaceName } from '../frontFaceCost'
import { useCardArt } from '../useCardArt'
import { emptyPushLine } from './copy'
import './SuggestionsView.css'

/**
 * What a `suggestions` push puts INSIDE the agent view shell (stories c6-6 and c6-7).
 *
 * ================= c6-6 SHIPPED HALF OF THIS FILE, AND c6-7 FILLED THE `null` ===========
 *
 * c6-6's Q1 ruling shipped the empty-push state real and returned `null` for a non-empty one,
 * because *"a rendered row is what pulls the image, inspection and alt-text contracts forward a
 * story early"*. This is that story: the rows are here, and the module is still named for the
 * VIEW rather than for the state, which is what let them be added by extending one file instead
 * of creating a second one.
 *
 * ================= IT IS A CONTAINER, AND IT READS THE STORE'S TYPE ONLY ================
 *
 * `src/components/` is closed by a set-equality guard, and this module takes the store's content
 * type. That import is TYPE-ONLY and it reaches the STATE layer rather than `src/api/`: the wire
 * shape is `agentView.ts`'s to translate, and a body that took a `SuggestionsPayload` would be a
 * second reader of the envelope with a second opinion about absent fields.
 *
 * It holds hooks, a ref and handlers — which is what c6-6's header predicted when it declined to
 * put this module under `src/components/`, and which `posture.test.ts` would fail there three
 * times over.
 *
 * ================= WHAT THIS VIEW OWNS THAT NO EARLIER SURFACE DID =====================
 *
 * **It hydrates its own ids.** Every other consumer of the card cache draws ids that came out of
 * a deck payload, which arrive with a `CardSummary` already seeded and a deck-wide sweep already
 * fetching them. A suggested card is usually *not* in the deck: nothing seeds it, nothing sweeps
 * it, and until this component asks, the cache has never heard of the id. AD-12 names agent views
 * as the reason the cache is a shared module rather than the deck's private one, and this is the
 * first surface to spend that.
 *
 * **It cannot trust one field of what it renders.** `agentView.ts:50-53` validates the payload's
 * SHAPE and deliberately no item field — *"nothing about whether a `card_id` resolves. That is
 * c6-7's, at the row that renders it"* (`deferred-work.md:209`, homed here by name). So every
 * item field below is read as `unknown` and gated before use, and a malformed entry degrades to
 * the placeholder **alone**, taking no neighbour with it: FR-13 and AD-7 are one push failing one
 * row, never the push failing wholesale — which is exactly what a `TypeError` in render would do,
 * since React unmounts the whole dialog around it.
 */
export interface SuggestionsViewProps {
  /**
   * The push's own `kind`, interpolated into the empty-push line. Taken from the store's content
   * rather than hard-coded, because the artefact's sentence is a TEMPLATE with a `{noun}` hole in
   * it — writing `'suggestions'` here would be this module deciding what the wire said.
   */
  readonly kind: AgentViewContent['kind']
  /**
   * The pushed rows. Empty is legal and renders the artefact's sentence (AD-7, UX-DR33).
   *
   * Narrowed to the `suggestions` ARM of the store union (16.1 made `AgentViewContent` a
   * per-kind discriminated union), still derived from the store type rather than from a wire
   * type — the derivation just names which arm this view draws.
   */
  readonly items: Extract<AgentViewContent, { kind: 'suggestions' }>['items']
}

/**
 * One pushed suggestion, as the STORE types it.
 *
 * **The alias is NOT called `SuggestionItem`, and that is a guard rather than a preference.**
 * `tests/wire-contract.test.ts` bans any `type`/`interface`/`class` declaration outside
 * `src/api/` whose NAME matches a shape the backend described — measured here, on the first
 * spelling of this line, which the guard caught by name. The wire's `SuggestionItem` is declared
 * once, by `contracts.py`, and reaches this file through `AgentViewContent['items']` rather than
 * through a second declaration of the same word.
 */
type PushedItem = SuggestionsViewProps['items'][number]

/**
 * The same item as it ACTUALLY arrives — every field `unknown`, because none of them was checked.
 *
 * **This is the c6-6 review patch's pattern, one layer down.** There the builder defended
 * `payload.title` and `payload.items` by type-guarding them rather than by merely testing for
 * their absence; here the same reasoning reaches the fields inside an item. The generated types
 * are honest about the ENVELOPE and silent about this: `agentEventOf` is kind-only by Brad's c6-6
 * Q6 ruling, so nothing between the socket frame and this row has ever looked at `card_id`.
 *
 * Typing the row's prop this way rather than casting inside the body is what makes the gates
 * below REQUIRED rather than defensive — with `PushedItem` the compiler would call every `typeof`
 * check redundant, which is how a guard gets deleted by a later tidy-up that believes the types.
 */
type UntrustedItem = { readonly [K in keyof PushedItem]?: unknown }

/**
 * The array element as it actually arrives — not just each FIELD untrusted, but each ELEMENT.
 *
 * `suggestionsViewOf` (`agentView.ts:230-231`) only checks `Array.isArray(items)`, never that
 * every element is a non-null object, so a bare `null`/`undefined` array entry reaches here
 * typed as a full `PushedItem` by the generated types — every `typeof item.<field>` gate below
 * assumes `item` itself is dereferenceable, and without this a malformed ELEMENT throws the
 * same `TypeError` FR-13/AD-7 ban for a malformed FIELD, taking the whole dialog with it. An
 * element that is not an object degrades to the all-fields-absent item, which is what every
 * gated read already treats a missing field as.
 */
const itemOf = (raw: unknown): UntrustedItem => (typeof raw === 'object' && raw !== null ? raw : {})

/**
 * The confidence tokens this row will render, and nothing else (`Confidence`, `contracts.py:595`).
 *
 * **A membership test rather than a `typeof` check, and the difference is the SLOT.** `reason` and
 * `category` are free text by specification — a sentence and a caller-chosen label — so a string
 * is a string and the row renders what it was sent. `confidence` is a closed enum rendered as a
 * chrome token in `{typography.micro}`, which uppercases: an arbitrary wire string landing there
 * is not "unexpected content", it is a paragraph in a slot sized for one word, in a type role that
 * would shout it. Membership is the same total-map idiom `cards.ts` uses for `ErrorReason`.
 */
type ConfidenceToken = NonNullable<PushedItem['confidence']>

const CONFIDENCE_TOKENS = ['low', 'medium', 'high'] as const satisfies readonly ConfidenceToken[]

/**
 * A fourth confidence token added on the Python side fails `npx tsc -b --force` NAMING itself,
 * rather than silently rendering nowhere — the mechanism `CardPlaceholder`'s two asserts use, and
 * the reason `CONFIDENCE_TOKENS` is written out rather than derived from a `Record` at runtime.
 */
type Assert<T extends true> = T

export type EveryConfidenceTokenRenders = Assert<
  [Exclude<ConfidenceToken, (typeof CONFIDENCE_TOKENS)[number]>] extends [never] ? true : false
>

/**
 * The id this row will hydrate, inspect and draw — or `''` when the item does not carry one.
 *
 * `''` is not a sentinel invented here: it is the app's own value for *"an id the app cannot
 * render"*. `hydrateCard('')` refuses it terminally with `placeholder: 'unknown-card'` and issues
 * no request at all (`cards.ts:527-543`, Q5's ruling: the empty id addresses the collection route
 * rather than a card, so the uuid gate never sees it), which routes a malformed item into exactly
 * the degradation AC 4 already describes, through machinery that already exists and is tested.
 *
 * NOT trimmed, deliberately. `card_id` has no shape constraint (c4-1) and `contracts.py` caps its
 * LENGTH without validating its shape (AD-7), so a padded id is a real id this component has no
 * standing to rewrite — the backend's refusal is the authority, and it lands on the same
 * placeholder one round trip later.
 */
const cardIdOf = (item: UntrustedItem): string =>
  typeof item.card_id === 'string' ? item.card_id : ''

/** The item's reason, or `''` — the row keeps its line either way (see {@link SuggestionRow}). */
const reasonOf = (item: UntrustedItem): string =>
  typeof item.reason === 'string' ? item.reason : ''

/** The item's badge text, or `null` — `Badge` renders nothing for `null`, so no branch is owed. */
const categoryOf = (item: UntrustedItem): string | null =>
  typeof item.category === 'string' ? item.category : null

/** The item's confidence, or `null` when it is absent or is not one of the three tokens. */
const confidenceOf = (item: UntrustedItem): ConfidenceToken | null => {
  const value = item.confidence
  if (typeof value !== 'string') return null
  return CONFIDENCE_TOKENS.find((token) => token === value) ?? null
}

/**
 * Whatever the cache can tell this row about the card, as one shape — or `null` while it knows
 * nothing.
 *
 * `cards.ts` keeps a private `summaryOf` that returns `null` for a HYDRATED entry, because its
 * caller is asking *"what did we know before this read"*. This row asks the opposite question —
 * *"what is renderable right now"* — so the hydrated card is the best answer rather than the
 * excluded one. A `Card` carries every field of a `CardSummary`, which is what lets one return
 * type serve both and `frontFaceCost` take either.
 *
 * All four tiers are reachable here, and the one that looks impossible is the interesting one: a
 * suggested card that happens to be IN the open deck was seeded by `seedCardSummaries` before
 * this view opened, so a `summary` entry paints a name and pips at first frame with nothing in
 * flight.
 */
const renderableOf = (entry: CardEntry | undefined) => {
  if (entry === undefined) return null
  return entry.status === 'hydrated' ? entry.card : entry.summary
}

/**
 * Whether the cache has decided this id is not a card at all.
 *
 * `entry.placeholder`, never `entry.reason`: the wire token is the store's business and c4-1's
 * AC 13 bans a `switch` on it anywhere downstream. This is the same predicate `inspection.ts`'s
 * `inspectable()` applies — deliberately, because the row and the store must agree about which
 * entries are dead, and they agree by asking the same question rather than by two similar ones.
 */
const isUnknownCard = (entry: CardEntry | undefined): boolean =>
  entry?.status === 'unknown' && entry.placeholder === 'unknown-card'

/**
 * One suggestion (AC 1-AC 4, AC 6, AC 7, UX-DR24).
 *
 * ================= IT IS A `<button>`, AND SO IS THE UNKNOWN ONE (Q3's ruling) ==========
 *
 * `DeckRow` is the verbatim structural precedent — one real `<button>` carrying all five
 * inspection verbs, no `tabindex`, no `onKeyDown` — and this row copies it rather than the tile's
 * frame/button split, because the tile only split them to keep a flip CONTROL from reading as
 * leaving the card, and this row has no child control at all (Q5: flip state is honoured, the
 * control is not rendered).
 *
 * **Every row is the same button, including a row whose card the app cannot identify.** UX-DR22
 * says the unknown-card variant cannot be inspected, and the refusal that implements it is the
 * STORE's: `inspectable()` early-returns inside `setHovered`, `setFocused` and `togglePin`, and
 * it was written for *"Epic 6's thumbnails, whose ids do not come from a deck at all"* — this
 * surface, named a story and a half before it existed. So an unknown row is focusable and
 * readable, and can never set or pin a target.
 *
 * The alternative — dropping the button on unknown rows — was declined for a mechanical reason
 * rather than a stylistic one: an entry moves `undefined → loading → unknown` **while rendered**,
 * so a focused row's button would vanish underneath the person mid-hydration and drop focus to
 * `<body>` INSIDE the shell's focus trap. Uniform buttons make that state unreachable.
 *
 * ================= NO `onKeyDown`, AND IT WOULD NOT FIRE IF THERE WERE ONE ==============
 *
 * Enter and Space are the button's own click (UX-DR39), which is the reason the element was
 * chosen. A keyboard handler here would also be a trap: while a view is open, `CardDetail`'s
 * document-CAPTURE Escape listener calls `stopPropagation()`, and React 17+ delegates its own
 * synthetic listeners at the root container BELOW `document` in the capture path — so an
 * `onKeyDown` on this row would silently never see Escape (`deferred-work.md:49`).
 */
function SuggestionRow({ item }: { item: UntrustedItem }) {
  const cardId = cardIdOf(item)
  const entry = useCardEntry(cardId)
  const live = useIsLiveTarget(cardId)
  // Q5: the flip STATE is honoured, keyed by printing exactly as `EXPERIENCE.md:85` describes
  // ("a flipped tile is flipped everywhere it appears — grid, agent-view thumbnail, and the
  // detail panel — because the state is keyed by printing, not by location"). The flip CONTROL is
  // not rendered: UX-DR15 places it on tiles and the detail panel, and a >=32px hit area does not
  // fit a thumbnail this size. Flipping stays reachable through the panel this row targets.
  const face = useFaceIndex(cardId)
  // DESTRUCTURED AT THE TOP OF RENDER, and that is a lint requirement rather than a style: the
  // `react-hooks/refs` rule reads a member access on this object during render as reading a ref,
  // and `<img ref={art.settleIfCached}>` measured four errors when `useCardArt` was extracted.
  const { state: art, settleIfCached, onLoad, onError } = useCardArt(cardId, face)

  const renderable = renderableOf(entry)
  // `cardId === ''` is known SYNCHRONOUSLY, before the hydration effect ever resolves the cache
  // entry to `status: 'unknown'` — without it, the first paint of a malformed item falls
  // through to the image branch below (`entry` is still `undefined`) and commits a real
  // `<img src="/api/card-image/">` request for one render.
  const unknown = isUnknownCard(entry) || cardId === ''
  const reason = reasonOf(item)
  const pinnedId = usePinnedId()

  // RELEASE A STALE TARGET THE MOMENT HYDRATION SETTLES TO UNKNOWN (code review, 2026-08-11:
  // Greptile P1). `inspectable()` treats an in-flight (`undefined`/`loading`) entry as
  // inspectable — deliberate for deck cards (c4-1: refusing on absence would refuse every card
  // on a cold open, before any hydration had run) — but a suggestion id can settle to a
  // TERMINAL `unknown`, which UX-DR22 says can never be inspected. A real click or hover in the
  // window before that settle lands (real network latency; not reachable in jsdom's near-
  // synchronous promise resolution) races past that guard and leaves a stale hover, focus or
  // pin pointed at a card that just became un-inspectable. This effect is the release valve:
  // once THIS row's own entry is unknown, drop whichever of its own transients or pin it is
  // still holding — `clearHovered`/`clearFocused` are already keyed no-ops otherwise, and the
  // pin is only released when it is THIS card's, never another row's.
  useEffect(() => {
    if (!unknown) return
    clearHovered(cardId)
    clearFocused(cardId)
    if (pinnedId === cardId) clearPin()
  }, [unknown, cardId, pinnedId])

  return (
    <button
      type="button"
      /* `is-live` is the app-wide class every live marker hangs on — the tile's ring, the deck
         row's rule and now this — so one grep finds them all. The rule itself is
         `--shadow-suggestion-row-live` in the stylesheet, because a composite box-shadow cannot
         be written in a component stylesheet at all (stylelint's allowed-list). */
      className={live ? 'suggestion-row is-live' : 'suggestion-row'}
      /* THE FIVE VERBS, UNRENAMED AND UNWRAPPED (AC 2, UX-DR14, UX-DR20). Two transient slots
         rather than one, and both clears keyed by id: leaving one row and reaching the next
         produces two events and the losing row's is free to land second, so an unkeyed clear
         would erase the hover the row being MOVED TO has already set (PR #44's P1, and rows are
         where a pointer crosses the most of them per second).

         What an id MEANS — whether it can be inspected, whether a click pins or releases — is the
         slice's, so this surface gets the tile's behaviour from the tile's verbs rather than from
         a fourth copy of the rule. `onClick` serves mouse and keyboard alike. */
      onMouseEnter={() => setHovered(cardId)}
      onMouseLeave={() => clearHovered(cardId)}
      onFocus={() => setFocused(cardId)}
      onBlur={() => clearFocused(cardId)}
      onClick={() => togglePin(cardId)}
    >
      {/* THE THUMBNAIL SLOT — FULL ROW HEIGHT, FIXED SHAPE, NEVER REFLOWING (AC 7, UX-DR36).
          The slot always contains a card-shaped element, from the first frame: a well before the
          picture exists, the picture over it once it does, a placeholder instead of both when
          there is nothing to draw. Nothing here changes SIZE as bytes arrive — DESIGN.md's
          amended `components.suggestion-row.height` is content-driven precisely so this slot can
          take its height from the two text lines and derive its width from 63:88. */}
      <span className="suggestion-row-thumb">
        {unknown ? (
          /* AC 4, and c6-6's structurally-deferred AC 3 discharged at the row that finally has a
             subject: the id resolves to nothing, so the slot says so — and the REASON still
             renders below, because one dead entry is one dead thumbnail and not a lost row.
             `cardId` is passed so the placeholder can show its 8-character prefix, which is the
             only identifying information left; `''` renders the label alone. */
          <CardPlaceholder variant="unknown-card" cardId={cardId} />
        ) : art === 'failed' ? (
          /* THE PICTURE FAILED, THE CARD DID NOT (AD-11: the backend serves no substitute). The
             card is still inspectable and still nameable, so the named placeholder draws what the
             cache knows. Before hydration lands there is nothing to name — the variant renders
             its slots totally, so an all-`null` named placeholder is an empty card-shaped box
             rather than a crash. */
          <CardPlaceholder
            variant="named-card"
            name={renderable?.name ?? null}
            cost={renderable?.mana_cost ?? null}
            typeLine={renderable?.type_line ?? null}
          />
        ) : (
          <>
            {/* THE SILENT WELL, and it is a SIBLING the image covers rather than a background
                under it — c4-4's Q8 ruling: `--surface-well` painted on the image's own element
                would show through a png face's transparent corners. It is also what gives the
                slot its size, so it stays mounted under a shown image rather than being swapped
                out for one. No text, no spinner (EXPERIENCE.md's skeleton policy). */}
            <CardPlaceholder variant="loading" />
            <img
              ref={settleIfCached}
              className="card-shape suggestion-row-image"
              data-loaded={art === 'shown' ? 'true' : 'false'}
              /* AD-11, AC 7: the backend proxy, never a CDN host (`no-scryfall-hosts.test.ts`
                 bans the family outright). `size` is UNSPELLED — Q4's ruling: `normal` is the
                 route's own default and the grid's key, and `?size=normal` would be a SECOND
                 browser-cache entry for one picture. A suggested card that later joins the deck
                 then finds the grid's bytes already warm. `face` follows the store (Q5) and
                 spells nothing at 0, which is every unflipped row. */
              src={cardImageUrl(cardId, undefined, face)}
              /* `alt=""`, EXACTLY (AC 6, UX-DR48). The rule's own words for this shape: *"use
                 `alt=""` — the name is announced once, from the row text"*. The name is two
                 elements away in the same button, so alt text here would announce it twice. */
              alt=""
              decoding="async"
              onLoad={onLoad}
              onError={onError}
            />
          </>
        )}
      </span>

      {/* THE HEAD LINE (AC 1): badge · name · cost · confidence, in DESIGN.md's order. */}
      <span className="suggestion-row-head">
        {/* Q1's ruling: the "action" badge IS the category badge — there is no `action` field on
            the wire, and DESIGN.md and EXPERIENCE.md were both annotated in this story's first
            commit. NEUTRAL tone, the only one that invents nothing: no mapping from free-text
            categories to the four semantic tones exists, and `Badge` clamps an unknown tone to
            neutral anyway. `null` renders no pill at all — `filled()` is the primitive's own
            check and it already refuses a blank string, so no branch is owed here. */}
        <Badge tone="neutral">{categoryOf(item)}</Badge>
        {/* THE NAME, FRONT FACE ONLY (AC 1). The element is present from the first frame with
            nothing in it, and that is deliberate: these ids carry NO summary seed, so the name
            arrives only when hydration lands, and a name that appeared by INSERTING an element
            would reflow the row under the reader. `frontFaceName` for `DeckRow`'s reason — the
            combined `X // Y` string belongs on the detail panel, not in a row's name column. */}
        <span className="suggestion-row-name">
          {renderable === null ? '' : frontFaceName(renderable.name)}
        </span>
        {/* THE COST (AC 1). `ManaCost` is forgiving by contract — `null` and blank both render
            nothing — so the not-yet-hydrated case needs no branch. `frontFaceCost` resolves the
            three real shapes and, for the 87.8% of faced cards whose top-level `mana_cost` is
            blank, reads `card_faces[0]` off the hydrated record. */}
        <span className="suggestion-row-cost">
          <ManaCost cost={renderable === null ? null : frontFaceCost(renderable, entry)} />
        </span>
        {/* THE CONFIDENCE (AC 1), RIGHT-ALIGNED, AND RENDERED AS THE WIRE TOKEN.
            `{typography.micro}` uppercases it in the stylesheet, which is the type role doing the
            work; the word itself is wire data and not copy, so nothing here is owed a
            `COPY_MODULES` entry. Wrapping it in authored words ("Confidence: high") would be new
            copy no artefact carries. Absent ⇒ no element, because an empty right-aligned slot is
            chrome announcing nothing. */}
        {confidenceOf(item) === null ? null : (
          <span className="suggestion-row-confidence">{confidenceOf(item)}</span>
        )}
      </span>

      {/* THE REASON (AC 1, AC 4) — the row's whole purpose, and the one thing that renders even
          when everything else about the entry has failed.

          THE ELEMENT IS UNCONDITIONAL, which is the one place this file departs from the app's
          `filled()`-style totality, on purpose. A missing `reason` is a malformed item rather
          than an absent feature, and dropping the line would silently change the row's HEIGHT —
          and therefore the width of the thumbnail beside it, which derives from that height. An
          empty `<span>` carries no role and announces nothing, so the cost is layout kept honest
          for zero words spoken. */}
      <span className="suggestion-row-reason">{reason}</span>
    </button>
  )
}

export function SuggestionsView({ kind, items }: SuggestionsViewProps) {
  /* HYDRATION IS THIS VIEW'S OWN (AC 7, AD-12). Suggested ids come from an agent rather than
     from a deck, so nothing has seeded them and the deck sweep will never reach them: this
     effect is the only thing that will ever ask.

     ONCE PER UNIQUE ID, in an effect, exactly as `hydrateDeckCards` does it — `hydrateCard`
     dedupes in flight and never rejects, so `void` on each is the whole error story, and the
     `Set` collapses the duplicate ids an agent is free to send. Running from an effect rather
     than during render is also what puts the JSON reads AFTER the commit that sets every
     `<img src>`, so the pictures are already queued when the metadata requests start.

     KEYED ON `items`, NOT ON MOUNT. c6-6 ships replace-in-place as a re-fire against a MOUNTED
     shell, so a second push of the same kind reaches this component as new props with the same
     component instance — a mount-only effect would leave every id of the second push unhydrated.

     The hooks rule is why this sits above the empty branch rather than inside the non-empty one:
     an empty push simply iterates nothing. */
  useEffect(() => {
    for (const cardId of new Set(items.map((raw) => cardIdOf(itemOf(raw)))))
      void hydrateCard(cardId)
  }, [items])

  // `length === 0` and never `!items.length` or `items.length ? … : …` — the c2-6 falsy-value
  // family in a numeric test, and `Panel.tsx:73-80`'s idiom. The store's builder guarantees an
  // ARRAY here for every payload the wire admits, so there is no third state to branch on.
  if (items.length !== 0) {
    return (
      /* A REAL `ul`/`li` (AC 5, UX-DR44), with NO `role` override: the list semantics are what
         tell a screen-reader user how many suggestions arrived before they start moving through
         them — and the shell's header already said the same number in words. */
      <ul className="suggestions-view-rows">
        {items.map((raw, index) => {
          // `itemOf` first: `raw` is typed `PushedItem` by the generated types but may be a
          // bare `null`/`undefined` array element at runtime (see `itemOf`'s header) — every
          // read below, including the key, must go through the normalized item.
          const item = itemOf(raw)
          return (
            /* KEYED BY id AND POSITION, WHICH IS THE OPPOSITE OF `CardGrid`'s ARGUMENT, and the
               difference is the data. A deck's `card_id` is unique BY THE DATA — `deck_cards`
               is keyed on (deck_id, card_id) and every row lands in exactly one board — so the
               grid and the deck list key on the id alone. Nothing constrains an AGENT:
               `contracts.py` caps the item count and each field's length and says nothing about
               duplicates, so two rows suggesting the same card in different words are a legal
               push and would collide on a bare id key. Position disambiguates them; the id
               keeps the key stable for the common case where a replace re-sends the same list. */
            <li className="suggestions-view-item" key={`${cardIdOf(item)}:${index}`}>
              <SuggestionRow item={item} />
            </li>
          )
        })}
      </ul>
    )
  }

  // A bare `<p>`, and NOT a `StatePanel`: EXPERIENCE.md files the empty push under *Voice and
  // Tone* as an in-view line, exactly as it files the empty deck as an in-grid one, and c4-12
  // established that a single sentence in a surface's own body is not a panel. It REPLACES the
  // `<ul>` above rather than sitting inside it — a `<p>` in a `<ul>` is invalid, and an empty
  // list announces "list, 0 items" before the sentence explaining why (`DESIGN.md`'s
  // `components.empty-push-line`, added by this story). No `aria-live` anywhere near it either:
  // the view's announcement is the heading's, and a second region inside the same dialog would
  // announce the same arrival twice.
  return <p className="suggestions-view-empty">{emptyPushLine(kind)}</p>
}
