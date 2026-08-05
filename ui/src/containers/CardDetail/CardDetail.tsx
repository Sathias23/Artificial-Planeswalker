import { useEffect, useRef, useState } from 'react'

import { CardPlaceholder } from '../../components/CardPlaceholder/CardPlaceholder'
import { ManaCost } from '../../components/ManaCost/ManaCost'
import { Panel } from '../../components/Panel/Panel'
import type { Card, CardFace, CardSummary } from '../../api/schema'
import { hydrateCard, readCardEntry, useCardEntry, type CardEntry } from '../../state/cards'
import type { DeckBoards } from '../../state/deckGroups'
import { useFaceIndex } from '../../state/faces'
import {
  clearPin,
  clearTransientTargets,
  coldOpenTargetOf,
  setDefaultTarget,
  useInspectionTargetId,
  usePinnedId,
} from '../../state/inspection'
import { cardImageUrl } from '../CardTile/imageUrl'
import { FlipControl } from '../FlipControl/FlipControl'
import { useCardArt } from '../useCardArt'
import { useImagedFaceCount } from '../imagedFaces'
import { replacesRememberedDeck } from './deckMemory'
import './CardDetail.css'
import './CardDetailChrome.css'
import { PANEL_TITLE, UNPIN_LABEL, pinnedAnnouncement } from './copy'

/**
 * The persistent card detail panel — the right column's permanent occupant, and the thing that
 * makes reading a deck one continuous motion (story c4-5, FR-17, UX-DR20, UX-DR36, UX-DR44,
 * UX-DR45).
 *
 * ================= WHAT HYDRATION ACTUALLY BUYS, MEASURED (Q1) =========================
 *
 * The received picture — `EXPERIENCE.md:86`, repeated in four modules' docstrings — is that name
 * and cost come free with the deck payload and *"the rest fills in place"* from
 * `GET /api/cards/{card_id}`. Measured against the shipped database, that is **wrong for
 * single-faced cards and exactly right for multi-faced ones**, and the difference is total
 * rather than statistical:
 *
 *   `CardSummary` already carries `name`, `mana_cost`, `type_line` **and `oracle_text`** — every
 *   text field `DESIGN.md:387` asks this panel to draw. So for a single-faced card `hydrateCard`
 *   adds nothing DRAWABLE at all.
 *
 *   **All 3,225 cards in the corpus that carry `card_faces` have a BLANK top-level
 *   `oracle_text` — 100% of them** — and 2,274 carry the degenerate type line `Card // Card`.
 *   For that population the real name, type line and rules text exist ONLY in `card_faces`,
 *   which only the hydration route returns. Six of the 99 cards in the largest real deck are in
 *   it, all six MDFC Pathways.
 *
 * So the panel hydrates on every target change and the summary tier is what it draws until the
 * record lands: *"the rest fills in place"* is real, it just fills in place for ~6% of a deck.
 * The other things that call buys are not decorative — it warms the cache **c4-6** flips
 * through, it is what gives `deferred-work.md:3372`'s terminal-after-three asymmetry the
 * visibility it was promised, and story 4.1's own criterion (*"the cursor sweeps the whole grid
 * twice → each distinct card is fetched at most once"*) is satisfied by `hydrateCard`'s
 * in-flight dedupe and attempt cap rather than by anything written here.
 *
 * ================= NO SPINNER, AND IT IS STRUCTURAL (AC 12, UX-DR36) ===================
 *
 * There is no loading branch in the text at all. Every deck card is seeded to `'summary'` by
 * `createDeckBoot` → `seedCardSummaries`, so the panel always has something to draw the instant
 * a target is set; and `hydrateCard`'s `'loading'` entry CARRIES the summary it had before, so
 * nothing it was already showing goes blank while a request is in flight (AC 13). The only
 * placeholder-shaped thing here is the silent well behind the ART, which is
 * `EXPERIENCE.md`'s placeholder-then-fill, not a skeleton.
 *
 * ================= THE ART IS COLD EVEN WHEN THE GRID IS WARM ==========================
 *
 * `?size=large` is a different URL and therefore a different browser-cache key from the grid's
 * `normal`, so the first inspection of a card always pays a fetch. That inverts which half of
 * `useCardArt`'s race is the common one here — see that module's header. `cardImageUrl` is
 * EXTENDED rather than duplicated (its own docstring's instruction, and c4-6 adds `face` beside
 * `size`), and no Scryfall host appears anywhere: art goes through this app's origin, always
 * (AD-11, `tests/no-scryfall-hosts.test.ts`).
 *
 * ================= WHAT IT IS NOT: A MODAL, AND NOT A LIVE REGION ======================
 *
 * **Not a modal** (AC 25, UX-DR38 — it *"neither stacks nor traps"*): no focus trap, no
 * return-focus contract, no `aria-modal`. It is a column that is always there.
 *
 * **Not a live region** (AC 24, UX-DR44/45), and that was a found-and-fixed defect at the UX
 * gate (H4/C1) rather than a preference: with `aria-live` on the panel, sweeping a cursor across
 * a 60-card grid would fire one polite announcement per card and flood the queue. So transient
 * changes announce NOTHING, and only a pin speaks — once, through the separate region at the
 * bottom of this file. `CardDetail.test.tsx` asserts the ABSENCE of `aria-live` on the panel, so
 * a later story cannot reintroduce it quietly.
 *
 * ================= ESC IS LAYERED, AND EPIC 6 MUST WIN (Q12, AC 22) ====================
 *
 * UX-DR39: *"Esc closes the topmost thing — an open agent view first, then an active pin."* The
 * `keydown` listener below is registered on `document`, in the BUBBLE phase, and releases the
 * pin. **The contract c6-5 relies on: the agent view registers its own `keydown` on `document`
 * in the CAPTURE phase, closes itself, and calls `stopPropagation()`.** Capture at the document
 * runs before this bubble listener FOR EVERY TARGET, so the layering holds even when focus sits
 * on `<body>` or a grid tile rather than inside the overlay's subtree — which is exactly where
 * an element-scoped handler would fail: a `keydown` targeting `<body>` never passes through the
 * overlay, so a `stopPropagation()` on the overlay's own root could not pre-empt this listener
 * (found at review, 2026-08-05 — the first written form of this contract had that hole). No
 * overlay exists yet, so **this story cannot test the layering** — that half is declared rather
 * than covered.
 *
 * ================= WHAT THIS PANEL DELIBERATELY DOES NOT DO ============================
 *
 * **No price, and the AC is satisfied BY ABSENCE** (AC 14, `deferred-work.md:1993-2003`).
 * `DESIGN.md` puts a price beside the type line and `EXPERIENCE.md` says *"prices render only
 * when present in local data"* — and there is no price field on the wire and never has been
 * (`types.d.ts:325`: *"There is no price data of any kind in this record."*). Brad ruled at
 * c3-2 Q4 that the endpoint ships no price rather than a permanently-null one, so there is
 * nothing to render conditionally: no zero, no placeholder, no empty slot, and no `price` in
 * `Card` for a future edit to reach for. `CardDetail.test.tsx` asserts that at the TYPE, which
 * is the only place an absence can be asserted.
 *
 * **No focus management and no skip-link target** — c4-11's,
 * which moves focus to the `<h2>` this panel already exposes. **No deck list, no format check** —
 * c4-7 and c4-10, which stack beneath this panel in the same column.
 *
 * ================= WHAT c4-11 INHERITS FROM THIS PANEL (Q3, UX-DR40) ===================
 *
 * **The unpin control is a Tab stop UX-DR40's enumerated order does not contain.** That order
 * predates the control (Q3 — UX-DR20 requires it and specifies nothing about it), so c4-11 must
 * add "the unpin control, while pinned" to the enumeration rather than rediscover it: it sits in
 * the panel header between the title and the panel body, exists only while a pin is active, and
 * activating it moves focus to the panel's `<h2>` (the same element c4-11's skip link targets —
 * one focus home, not two). Also c4-11's: the oracle clamp's scroller is keyboard-unreachable
 * (no focusable element inside `overflow-y: auto`), ledgered at review 2026-08-05 — the fix
 * adds a Tab stop AND renegotiates AC 25's `[tabindex]`-absence assertion, both of which are
 * that story's to own.
 */

/**
 * A string prop that is actually there, or `null`.
 *
 * The identical `typeof` + `trim()` spelling `CardPlaceholder`, `CardTile`, `DeckBadges` and
 * `ManaCost` all use — the decide-once ruling that emptiness is never truthiness. It is
 * DUPLICATED VERBATIM rather than imported, which is what those two files did before it, and the
 * count is now three. Recorded rather than silently repeated: if a fourth consumer appears, the
 * honest move is a shared module beside `src/components/filled.ts`, whose header states the rule
 * for exactly this case (*"a helper shared by two components does not live inside one of them"*).
 *
 * It matters more here than anywhere else in the app, because `CardFace` is the first wire shape
 * whose every field is optional AND nullable: `face.oracle_text` can be `undefined`, `null` or
 * `''` from one response, and all three mean the same thing to a reader.
 */
const given = (value: string | null | undefined): string | null => {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

/** The four text fields the panel draws, each already narrowed. */
interface DetailContent {
  readonly name: string | null
  readonly cost: string | null
  readonly typeLine: string | null
  readonly oracleText: string | null
}

const NOTHING_KNOWN: DetailContent = { name: null, cost: null, typeLine: null, oracleText: null }

const fromSummary = (summary: CardSummary | null): DetailContent =>
  summary === null
    ? NOTHING_KNOWN
    : {
        name: given(summary.name),
        cost: given(summary.mana_cost),
        typeLine: given(summary.type_line),
        oracleText: given(summary.oracle_text),
      }

/**
 * A hydrated record, read at **the face the reader chose** (AC 13, c4-5 Q1; c4-6 AC 11, Q9).
 *
 * `card_faces[faceIndex]` where it has a value, the top-level field otherwise — per field, not per
 * record, because the wire's faces are all-optional and a face carrying a name but no type line
 * is expressible. For the 3,225 faced cards the top-level `oracle_text` is blank in every single
 * one, so the face wins there by being the only thing present; for `name` and `type_line` the
 * face wins on merit, because the top-level values are `'Clearwater Pathway // Murkwater
 * Pathway'` and `'Land // Land'` — or, for 2,274 printings, the useless `'Card // Card'`.
 *
 * **The per-field `??` survives c4-6 and is not replaced by a per-record choice**, and there is a
 * measured population behind that: ten cards that DO get a flip control have a face with a null
 * `type_line` — the Un-set "(cont'd)" minigame cards, e.g.
 * `Roll for Initiative // Roll for Initiative (cont'd)`. A per-record fallback would blank their
 * type line the moment they were flipped.
 *
 * **`card_faces` is indexed DIRECTLY, and the premise is stated** (c4-6 Q9). `resolve_face_images`
 * returns only the IMAGED faces, in face order, so the two arrays differ for a partially imaged
 * card — and this is only sound because the flip control renders exclusively where EVERY face is
 * imaged, which makes the two coincide. Measured read-only: **0 partially imaged rows exist**.
 * Whoever meets the first one owns the entry the ledger already opened
 * (`deferred-work.md:2765-2770`). An out-of-range index falls through to the top-level fields
 * rather than throwing, which is the same totality every other read here has.
 *
 * **This is the one place the panel calls a card by a different name than the tile does**, and it
 * is deliberate rather than an oversight of c4-3's Q5 (*"four surfaces must not call one card by
 * two names"*). That ruling is about surfaces showing the SAME thing; this panel is showing one
 * FACE — the very face whose picture is above the text — and `EXPERIENCE.md` says so directly
 * for c4-6: *"while a DFC tile is showing its back face, hovering or pinning it targets that
 * face: the detail panel shows the back, its name, and its oracle text."* c4-5 established that
 * the panel is face-specific at all; c4-6 makes the choice of face a control.
 */
const fromCard = (card: Card, faceIndex: number): DetailContent => {
  const face: CardFace | undefined = card.card_faces?.[faceIndex]
  return {
    name: given(face?.name) ?? given(card.name),
    cost: given(face?.mana_cost) ?? given(card.mana_cost),
    typeLine: given(face?.type_line) ?? given(card.type_line),
    oracleText: given(face?.oracle_text) ?? given(card.oracle_text),
  }
}

/**
 * What the panel can draw right now, from whichever tier of the cache has arrived.
 *
 * Every non-hydrated arm reads `entry.summary`, which is what makes AC 13's *"does not blank
 * anything it was already showing"* structural: `hydrateCard` carries the summary INTO the
 * `'loading'` entry and re-reads it at settle time, so a request in flight and a request that
 * was refused both still have the free tier behind them.
 */
const contentOf = (entry: CardEntry | undefined, faceIndex = 0): DetailContent => {
  if (entry === undefined) return NOTHING_KNOWN
  if (entry.status === 'hydrated') return fromCard(entry.card, faceIndex)
  return fromSummary(entry.summary)
}

/**
 * Whether the app does not know what this card IS — as opposed to merely lacking its picture.
 *
 * Reads `entry.placeholder`, the field `cards.ts` already classified once per entry, and NEVER
 * `entry.reason`: re-deriving a placeholder from a wire token in a component is the drift that
 * field exists to prevent (c4-1 AC 13, c4-3 AC 16). `panelFor()` is not called on this path and
 * no state panel ever reaches the glass because one card was refused (FR-13).
 */
const isUnknownCard = (entry: CardEntry | undefined): boolean =>
  entry?.status === 'unknown' && entry.placeholder === 'unknown-card'

/** What the panel draws. One prop, and it is the derivation — never the raw payload. */
export interface CardDetailProps {
  /**
   * `surfaceOf`'s answer for a loaded deck, verbatim — the same value `CardGrid` is handed.
   *
   * It is used for exactly one thing: resolving the cold-open target once per deck. The panel
   * does not iterate it, group it, sort it or count it — every one of those would be the second
   * derivation `deckGroups.ts` exists to prevent (AD-12).
   */
  boards: DeckBoards
}

export function CardDetail({ boards }: CardDetailProps) {
  const targetId = useInspectionTargetId()
  const pinnedId = usePinnedId()
  // `''` for "no target": `useCardEntry` is a pure selector over a plain record, so an id that
  // was never seen simply reads `undefined` — and the empty id specifically is one `hydrateCard`
  // refuses terminally with zero requests, so it can never acquire an entry by accident.
  const entry = useCardEntry(targetId ?? '')
  // WHICH FACE THE READER CHOSE (c4-6, AC 10, AC 11). Read from the same module-scope slice the
  // tile reads, keyed by printing — so a card flipped in the grid is already flipped here when it
  // becomes the target, and a card flipped HERE is flipped in the grid behind it. One answer, two
  // readers; `useFaceIndex` returns a number, so this panel re-renders only when its own target's
  // face moves.
  const faceIndex = useFaceIndex(targetId ?? '')
  const imagedFaces = useImagedFaceCount(targetId ?? '')
  const flippable = imagedFaces > 1
  const flipped = flippable && faceIndex !== 0
  const backFace = faceIndex === 0 ? 1 : faceIndex
  // DESTRUCTURED, and that is a lint requirement rather than a habit: `react-hooks/refs` reads a
  // member access during render as reading a ref, so `art.settleIfCached` in the JSX below is an
  // error while a plain identifier is not. See `../useCardArt`'s `CardArt` docstring.
  //
  // TWO CALLS, ONE PER FACE, exactly as the tile makes them (c4-6 Q7, Q10) — and at `size=large`,
  // so these are four distinct browser-cache keys per flippable card across the two surfaces. The
  // back render is only mounted for a flippable card, so an ordinary card still costs the one
  // `?size=large` request c4-5 shipped.
  //
  // BOTH DESTRUCTURED, for `react-hooks/refs`: a member access during render reads as reading a
  // ref, so `front.onLoad` in the JSX below is an ESLint error while a plain identifier is not.
  const {
    state: frontArt,
    settleIfCached: settleFront,
    onLoad: onFrontLoad,
    onError: onFrontError,
  } = useCardArt(targetId ?? '', 0)
  const {
    state: backArt,
    settleIfCached: settleBack,
    onLoad: onBackLoad,
    onError: onBackError,
  } = useCardArt(targetId ?? '', backFace)
  const art = flipped ? backArt : frontArt

  // THE ANNOUNCEMENT IS CAPTURED DURING RENDER, NOT IN AN EFFECT (AC 23, UX-DR45).
  //
  // The first spelling was `useEffect(..., [pinnedId])` and ESLint's
  // `react-hooks/set-state-in-effect` was right to reject it: a `setState` in an effect is a
  // second render pass, so the pinned ring and the announcement would land in two different
  // commits — a frame in which the panel says it is pinned and the live region has not caught
  // up. This is the render-time adjustment React documents for exactly this shape, and it is
  // the identical pattern `useCardArt` uses to reset a verdict when the card changes.
  //
  // KEYED ON THE PINNED ID ALONE, which is the whole of "exactly once". The name is read
  // IMPERATIVELY from the cache at pin time rather than taken from this render's `content` —
  // otherwise a faced card whose name resolves from `card_faces` when hydration lands would
  // change the region's text, and a change is what `aria-live` speaks. Releasing empties it,
  // which is a removal rather than a message.
  //
  // WITH ONE LATE DOOR (review 2026-08-05): a pin of an id whose cache entry carries no name
  // yet — a population Epic 6's thumbnails create, and the slice deliberately does not refuse —
  // would capture `''` and stay silent forever, turning AC 23's "exactly once" into zero. So a
  // capture that got NO name retries while the pin holds, and settles the first time a name
  // exists. Still exactly one spoken announcement per pin: once `text` is non-empty it never
  // recomputes, which is what keeps the MDFC hydration silence above intact.
  //
  // A DECLARED DIVERGENCE, NOT AN OVERSIGHT (AC 37): for the 6%-of-a-deck faced population the
  // name captured here is the summary tier's COMBINED one ("Clearwater Pathway // Murkwater
  // Pathway") while the panel renders the front FACE's once hydration lands — the reader hears
  // one name and reads another. Deliberate, because re-announcing on hydration is the exact
  // flood H4/C1 closed; how it SOUNDS is the epic manual-testing checklist's.
  const [announced, setAnnounced] = useState<{
    readonly id: string | null
    readonly text: string
  }>({ id: null, text: '' })

  if (announced.id !== pinnedId || (announced.text === '' && pinnedId !== null)) {
    const name = pinnedId === null ? null : contentOf(readCardEntry(pinnedId)).name
    const text = name === null ? '' : pinnedAnnouncement(name)
    // Guard the retry arm against a no-op write: a `setState` during render with an unchanged
    // value is a wasted second pass on EVERY render while a name-less pin holds.
    if (announced.id !== pinnedId || announced.text !== text) {
      setAnnounced({ id: pinnedId, text })
    }
  }

  // THE COLD-OPEN TARGET, WRITTEN ONCE PER DECK (AC 8, Q15). In an effect rather than during
  // render because it writes a store, and `boards` is the dependency because it is the deck's
  // identity as far as this panel is concerned — `deck.ts` derives it once at write time, so it
  // changes exactly when the deck does.
  //
  // AND THE DECK TRANSITION IS WHERE AN INSPECTION DIES (review 2026-08-05). The slice survives
  // this panel unmounting on purpose (Q6), which means nothing in it can know a DECK was
  // replaced — a pin or a stale hover from the previous deck would keep outranking the new
  // deck's cold-open target, and the panel would render a card that is not on the glass, with
  // the live ring on no tile. So the one consumer that holds a deck clears both user targets
  // when the deck it holds is no longer the deck it held — see ./deckMemory for why the memory
  // is module-scope and why a remount of the SAME deck clears nothing (FR-17).
  useEffect(() => {
    if (replacesRememberedDeck(boards)) {
      clearPin()
      clearTransientTargets()
    }
    setDefaultTarget(coldOpenTargetOf(boards))
  }, [boards])

  // HYDRATION IS THE PANEL'S CALL TO MAKE, which is what `cards.ts:527` says in as many words:
  // "whoever decides that a full record is actually needed — a hover handler, a detail panel
  // opening — calls `hydrateCard`". `void` because it never rejects and there is nothing to do
  // with its answer: the store is the authority and `useCardEntry` above is already watching it.
  // Sweeping a grid twice costs one request per distinct card, because the cache dedupes
  // in-flight reads and refuses to re-ask a terminal one.
  useEffect(() => {
    if (targetId === null) return
    void hydrateCard(targetId)
  }, [targetId])

  // ESC RELEASES THE PIN (AC 22, Q12, UX-DR39). On `document`, because the pin can be set from a
  // tile in the other column and released from anywhere — a listener on this panel would only
  // work while focus happened to be inside it. See the header for the layering contract c6-5
  // relies on, and for why this story cannot test it.
  useEffect(() => {
    const release = (event: KeyboardEvent) => {
      // `isComposing`: an Esc that cancels an IME composition is not a request to release a pin
      // — reachable the moment Epic 6 puts a text input on the page. `defaultPrevented`: an Esc
      // some other handler has already consumed is not this listener's to act on either; both
      // guards are review 2026-08-05's, ahead of the consumers that make them fire.
      if (event.key !== 'Escape' || event.isComposing || event.defaultPrevented) return
      clearPin()
    }
    document.addEventListener('keydown', release)
    return () => document.removeEventListener('keydown', release)
  }, [])

  // For the unpin control's focus hand-off below — an event-handler read, which is what keeps
  // it clear of the `react-hooks/refs` render-read rule the art hook's destructuring answers.
  const frameRef = useRef<HTMLDivElement>(null)

  // ACTIVATING UNPIN DESTROYS THE ACTIVATED ELEMENT — the button renders only while pinned —
  // and a removed activeElement drops keyboard focus to `<body>`, restarting Tab from the top
  // of the page (review 2026-08-05, ruled: fix here, not in c4-11). Focus moves to the panel's
  // `<h2>` — the one element c4-11's skip link already targets, so the two stories converge on
  // a single focus home. `tabIndex = -1` is set IMPERATIVELY and removed on blur: the panel at
  // rest carries no `[tabindex]`, which is what AC 25's not-a-modal assertion checks.
  const releaseAndRefocus = () => {
    clearPin()
    const title = frameRef.current?.querySelector('h2')
    if (title instanceof HTMLElement) {
      title.tabIndex = -1
      title.addEventListener('blur', () => title.removeAttribute('tabindex'), { once: true })
      title.focus()
    }
  }

  const content = contentOf(entry, faceIndex)
  const pinned = pinnedId !== null

  return (
    /* THE FRAME EXISTS ONLY TO CARRY THE PINNED RING, and that is a constraint rather than a
       preference: `Panel` is a primitive a consumer may not restyle, it takes no `className`,
       and a ring drawn on a wrapper with no radius would be a square outline around a
       `--radius-lg` panel. So the wrapper matches the panel's own radius and the ring is a
       box-shadow on it — see CardDetailChrome.css. */
    <div ref={frameRef} className={pinned ? 'card-detail is-pinned' : 'card-detail'}>
      <Panel
        title={PANEL_TITLE}
        level="overlay"
        badges={
          /* THE UNPIN CONTROL (AC 21, Q3), in `Panel`'s existing badges slot and rendered ONLY
             while pinned — an always-present control that does nothing four fifths of the time
             is a worse answer than one that appears with the state it acts on. A real
             `<button>` with a real word in it; see copy.ts for why it is not a glyph. */
          pinned ? (
            <button type="button" className="card-detail-unpin" onClick={releaseAndRefocus}>
              {UNPIN_LABEL}
            </button>
          ) : undefined
        }
      >
        <div className="card-detail-content">
          {targetId === null ? null : isUnknownCard(entry) ? (
            /* The app does not know what this card is. Reached only if a card BECAME unknown
               after it was already the target — the slice refuses to make one a target in the
               first place (AC 17) — so this is the honest render for a state that should not
               occur rather than a path with a population. */
            <CardPlaceholder variant="unknown-card" cardId={targetId} />
          ) : (
            /* ONE ART BOX FOR BOTH OUTCOMES (c4-6). It used to be two, one per branch; the flip
               control has to sit inside it either way (Q8: a face that failed can still be
               flipped OUT of), and two boxes would have been two places to mount it and two
               chances for one of them to be forgotten. The box is what carries `--shadow-rest`
               and the full-size footprint, so a placeholder and a real face keep the same
               elevation and the same geometry — the interchangeability CardDetail.css claims. */
            <div className="card-shape card-detail-art">
              {art === 'failed' ? (
                /* AD-11: a designed stand-in, never a broken-image glyph. The SAME 79-card
                   population as the grid — measured, `large` and `normal` are missing for exactly
                   the same set — plus whatever the CDN refuses transiently. The `<img>` is
                   REMOVED rather than hidden, because an element with a failed `src` still draws
                   the browser's own glyph. ON THE SHOWN FACE (c4-6 Q8): `?face=1` is a different
                   negative-cache key, so the two faces fail independently and the placeholder
                   follows whichever one is being looked at. */
                <CardPlaceholder
                  variant="named-card"
                  name={content.name}
                  cost={content.cost}
                  typeLine={content.typeLine}
                />
              ) : (
                <>
                  {art === 'loading' ? <CardPlaceholder variant="loading" /> : null}
                  {/* THE SAME TWO STACKED FACES THE TILE DRAWS, from the same shared classes in
                      FlipControl.css (c4-6 Q10). Sharing them rather than writing a second
                      rotation here is what keeps CardDetail.css's own "NO MOTION, DELIBERATELY"
                      claim literally true — this file still declares none — and what keeps the
                      reduced-motion registration a single pair of selectors covering both
                      surfaces rather than four. */}
                  <div
                    className="card-faces"
                    data-flipped={flippable ? String(flipped) : undefined}
                  >
                    <img
                      ref={settleFront}
                      className="card-detail-image card-face is-front"
                      data-loaded={frontArt === 'shown' ? 'true' : 'false'}
                      src={cardImageUrl(targetId, 'large')}
                      /* `alt=""`, DIVERGING FROM UX-DR48'S LITERAL WORDS AND FOLLOWING ITS LOGIC
                         (c4-5 Q13). That rule keeps `alt={name}` on the detail panel "because
                         there the image is the only carrier" — measurably false for this
                         component, exactly as c4-4 found for the tile: the card's name renders in
                         `--type-heading` immediately beneath the art, inside the same panel.
                         c4-4's Q4 ruled the name is announced ONCE. Unchanged by c4-6, whose
                         Q12 re-declares the same divergence for a flipped face: here the heading
                         FOLLOWS the face, so the name a reader hears and the face they see agree
                         — which is the half the tile's caption cannot manage. Epic
                         manual-testing checklist, for a real screen reader. */
                      alt=""
                      decoding="async"
                      onLoad={onFrontLoad}
                      onError={onFrontError}
                    />
                    {flippable ? (
                      <img
                        ref={settleBack}
                        className="card-detail-image card-face is-back"
                        data-loaded={backArt === 'shown' ? 'true' : 'false'}
                        src={cardImageUrl(targetId, 'large', backFace)}
                        alt=""
                        decoding="async"
                        onLoad={onBackLoad}
                        onError={onBackError}
                      />
                    ) : null}
                  </div>
                </>
              )}
              {/* THE PANEL'S OWN COPY OF THE CONTROL (c4-6 AC 12, UX-DR15) — "pinned to its art's
                  top-left", which is this box's top-left because the box IS the card. The SAME
                  component the tile mounts, not a second implementation: it takes a `cardId` and
                  asks the same question about it, so the panel cannot disagree with the grid
                  about which cards are flippable or which face is showing.

                  INSIDE the art box rather than beside it, which is legal here and was not on the
                  tile: this is a `<div>`, so an interactive descendant is ordinary content rather
                  than the `<button>`-in-`<button>` the tile's Q2 had to route around. */}
              <FlipControl cardId={targetId} />
            </div>
          )}

          {/* DESIGN.md:387's order and roles: name in `--type-heading` with the mana cost
              right-aligned, then the type line, then the oracle text — both in `--type-body`
              `--text-secondary`. A `<span>` rather than a heading element, deliberately: the
              panel's ONE heading is its `<h2>` title, which is what c4-11's skip link moves
              focus to and what its `role="region"` is named by. A card name promoted to a
              heading would rename that landmark on every hover. */}
          {content.name === null ? null : (
            <p className="card-detail-headline">
              <span className="card-detail-name">{content.name}</span>
              <ManaCost cost={content.cost} />
            </p>
          )}
          {content.typeLine === null ? null : (
            <p className="card-detail-type">{content.typeLine}</p>
          )}
          {content.oracleText === null ? null : (
            <p className="card-detail-oracle">{content.oracleText}</p>
          )}
        </div>
      </Panel>

      {/* THE PIN ANNOUNCEMENT, IN A REGION OF ITS OWN (AC 23, AC 24, UX-DR45).
          OUTSIDE the panel, which is the whole of the H4/C1 fix: the panel is not a live region
          and must not become one, so the thing that DOES speak is a separate element that
          carries no card content and changes only when a pin does. Empty at rest, and emptied
          on release — removing content is not an announcement. */}
      <p className="card-detail-announcement" aria-live="polite">
        {announced.text}
      </p>
    </div>
  )
}
