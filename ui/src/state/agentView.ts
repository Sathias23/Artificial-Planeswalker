/**
 * Whether an agent view is on the glass, and what it is showing — the SEVENTH store, and the
 * first whose whole contract is about a thing being *dismissed without being forgotten*
 * (story c6-5, UX-DR34, UX-DR38, AD-12).
 *
 * ================= THE SPINE SENTENCE, AND WHY THIS SLICE NEEDS NO NEW NARROWING =======
 *
 * `deck.ts` quotes the architecture spine: *"its state comes from exactly two inputs — REST
 * responses and WebSocket messages. Nothing else may write the store."* `inspection.ts:14`
 * narrowed that, in the open, to *"nothing outside the store writes **server-derived**
 * state"*, and `faces.ts` inherited the narrowing unchanged. This slice inherits it too, and
 * it is the first one where BOTH halves are live at once:
 *
 *   - **The content is server-derived** — an agent view exists because the agent pushed one,
 *     and since c6-6 the writer IS a WebSocket message ({@link openSuggestionsPush}, called by
 *     `connection.ts` off `socket.ts`'s dispatch), which is the spine sentence's own second
 *     input. Nothing narrowed.
 *   - **The open/closed status is a person** — Esc, the close pill and a scrim click are
 *     three gestures, and no request can answer whether somebody is still reading.
 *
 * The two live in one slice rather than two because AC 5 is a statement about their
 * RELATIONSHIP: *"dismissal never clears content — the view remains re-openable for the rest
 * of the session"*. Split across two stores, that invariant would have no address; here it is
 * {@link closeAgentView} writing one field and provably not the other.
 *
 * ================= IT IS A SCALAR, AND THAT IS AC 6 EXPRESSED IN THE TYPE ==============
 *
 * UX-DR38 fixes the overlay stack at EXACTLY ONE level deep, permanently — it is one of the
 * four confirmed UX rulings (2026-07-25), not a current simplification. So {@link content} is
 * a single nullable slot rather than an array, and *"nothing else can open over an open
 * view"* stops being a rule anybody has to obey: a second view has nowhere to go. Opening
 * while open REPLACES, which is the only thing a scalar can do and exactly what c6-6's
 * replace-in-place needed of it.
 *
 * A stack would also have needed a `--z-*` token family to order its levels against, which
 * `AppShell.css:246-250` and `deferred-work.md:1473-1482` both refuse for the same reason.
 *
 * ================= WHAT THIS MODULE DELIBERATELY DOES NOT DO ==========================
 *
 * - **It renders nothing.** `containers/AgentView` draws; this decides. It imports no React.
 * - **It does not listen to the socket ITSELF.** `socket.ts` owns the one dispatch switch and
 *   `connection.ts` is the seam that calls {@link openSuggestionsPush} from it — this module
 *   still imports neither, so the store has no opinion about how a frame reached it.
 * - **It holds no unread flag and no per-kind retention.** Those are c6-8's (nav pills,
 *   unread markers, kind switching) and they EXTEND this shape rather than reshape it — which
 *   is why {@link AgentViewContent} retains `ts` and `kind` that nothing in c6-6 renders.
 * - **It holds no focus.** Which element focus returns to on dismissal is one container's
 *   private business for the lifetime of one mount, not shared state — `AgentView.tsx` holds
 *   it in a ref, the way `SkipLink` holds `heldFocus`.
 * - **It validates no ITEM.** {@link suggestionsViewOf} is total about the payload's SHAPE —
 *   an absent payload, absent items and a blank title all construct a valid view — and says
 *   nothing about whether a `card_id` resolves. That is c6-7's, at the row that renders it
 *   (FR-13/AD-7: one bad entry degrades, the push never fails wholesale).
 */

import { create } from 'zustand'

import type { SuggestionItem, SuggestionsEvent } from '../api/schema'

/**
 * The word a view is called when the agent supplies no title of its own (story c6-6, Q7).
 *
 * **Copy, and declared as such** — `copy-rules.test.ts`'s `COPY_MODULES` carries this module
 * with that reason. It is the one AUTHORED string in the state layer, and it is here rather
 * than in a container's `copy.ts` for two reasons that point the same way: `deferred-work.md`'s
 * dialog-accessible-name entry says the guard belongs *"at the point content is constructed"*,
 * which is {@link suggestionsViewOf} three functions down; and c6-8's nav pill needs the same
 * word for the same kind, so a constant owned by any single container would be the wrong
 * address for the second reader. A wire-supplied `payload.title` is DATA and stays data — this
 * is what the app calls the view when nobody named it.
 *
 * Capitalised as a name rather than assembled from the wire kind (`'suggestions'` uppercased),
 * which was the rejected alternative: a runtime-assembled user-facing string is exactly the
 * residue `copy-rules.test.ts`'s header warns its detector cannot see.
 */
export const SUGGESTIONS_VIEW_TITLE = 'Suggestions'

/**
 * What the shell draws, plus what the two stories after this one need in order to draw more.
 *
 * Deliberately NOT a wire shape, and that survives c6-6 rather than being relaxed by it: the
 * envelope arrives at {@link suggestionsViewOf} and leaves as this, so nothing downstream holds
 * a frame. The FIELDS are `schema.ts`-typed — `SuggestionItem` is the generated model through
 * the alias, never a hand-written row — which is the half of the rule that matters, because a
 * hand-written item shape is precisely what would drift from the Python side unnoticed.
 *
 * ==== WHY IT RETAINS THREE FIELDS THIS STORY NEVER RENDERS =============================
 * `id`, `ts` and `kind` are all read by code that does not exist yet, and each has a named
 * reader: `id` keys the shell's replace effect (`AgentView.tsx` — a repeat push is a new
 * envelope, and identity is what tells the shell to re-announce); `ts` is c6-8's pill time
 * (UX-DR28 puts the push time on the pill, and the view header carries none); `kind` is c6-8's
 * kind-switching discriminant and this story's `{kind}` interpolation in the empty-push line.
 * Retaining them costs one object field each and is what makes c6-8's *"re-hydrated against
 * current card data"* possible without a second push — the ids and reasons are here, and the
 * ART is always re-fetched rather than retained.
 */
export interface AgentViewContent {
  /**
   * The envelope's `id` — **opaque, for identity and de-duplication, and carrying NO ordering**
   * (`types.d.ts:1049-1051` is emphatic about it; producers may mint a UUID4). It is the
   * REPLACE KEY: `AgentView.tsx` keys its replace effect on this, so two pushes are the same
   * push exactly when the wire says they are.
   */
  readonly id: string
  /** The envelope's `ts` — the ordering key, timezone-aware. Retained for c6-8's pill time. */
  readonly ts: string
  /**
   * Which view this is. Narrow to `'suggestions'` because that is the only kind with a view in
   * this story — c6-8 widens it when it adds the second, and a wider type now would be a claim
   * this module cannot honour (`swaps`/`tier_list`/`groups` are Epic 9 and still dropped at the
   * dispatch switch).
   */
  readonly kind: SuggestionsEvent['kind']
  /** The view's heading (`DESIGN.md:471` — title in `{typography.heading}`). */
  readonly title: string
  /**
   * The summary count beside the title, or `null` when the view has nothing to count. Nullable
   * rather than defaulting to `0`, because *"0 suggestions"* and *"a view that does not count
   * things"* are different sentences and the header renders them differently. A suggestions
   * push always counts — `0` is a REAL count and renders, which is the empty-push state.
   */
  readonly count: number | null
  /**
   * The pushed rows, retained unrendered by this story. c6-7 draws them; c6-8 re-hydrates them
   * against current card data on re-open. Empty is legal and is not an error
   * (`types.d.ts:1103-1105`: *"the view skips an empty push rather than rejecting it, so 'I
   * looked and found nothing' is expressible"*).
   */
  readonly items: readonly SuggestionItem[]
}

/**
 * The slice. Two fields, and the whole of AC 5 is that one verb writes one of them.
 *
 * A flat shape rather than `deck.ts`'s wrapped-union trick, for `inspection.ts:144-148`'s
 * reason verbatim: zustand's shallow merge is exactly the semantics wanted here — writing
 * `status` must leave `content` alone, which IS {@link closeAgentView}.
 */
export interface AgentViewState {
  /** Whether a view is on the glass. `'closed'` with content is the re-openable state. */
  readonly status: 'open' | 'closed'
  /**
   * The retained view — the ONE slot (see the header on AC 6). `null` only before the first
   * push of the session; after that it stays filled, because nothing in this module ever
   * writes it back to `null` (AC 5, UX-DR34).
   */
  readonly content: AgentViewContent | null
}

/** The state before any agent has pushed anything. Exported so tests can restore it. */
export const INITIAL_AGENT_VIEW: AgentViewState = {
  status: 'closed',
  content: null,
}

/**
 * A seventh `create()` and still no second state library (AD-12). `store-writes.test.ts`'s
 * `STORES` table names this module as the one writer.
 */
export const useAgentViewStore = create<AgentViewState>(() => INITIAL_AGENT_VIEW)

/**
 * Forget everything, including the retained content. **For tests only**, and the docstring
 * says so for the reason `resetInspection` and `resetFaces` say so: the store is module-level,
 * so a view left open by one test is what the next one starts from.
 *
 * This is the ONLY function in this module that clears {@link AgentViewState.content}, and it
 * is unreachable from the app — which is what keeps AC 5 true of every production path.
 */
export const resetAgentView = (): void => {
  useAgentViewStore.setState(INITIAL_AGENT_VIEW, true)
}

/**
 * Show a view (AC 6). Opening while one is already open REPLACES it at the STATE level — the
 * scalar's only possible behaviour, and the half of the replace-in-place contract this store
 * can honestly claim. The other half is `AgentView.tsx`'s: `App.tsx` renders `<AgentView>` with
 * NO `key`, so a content swap reconciles as a prop update on the same instance and the shell
 * stays mounted across it — which is deliberate rather than incidental. A remount would replay
 * the ENTRY BLOOM in place of the crossfade AC 2 specifies, and would re-capture the
 * return-focus target while focus sits inside the view. c6-6 supplies the missing RE-FIRES
 * instead: an effect keyed on {@link AgentViewContent.id} that re-focuses the heading, mutates
 * its live region and drives the crossfade. This store only guarantees the DATA is correct the
 * instant a consumer reads it.
 *
 * Args:
 *   content: What the shell draws. Written together with the status, in ONE `setState`, so no
 *     render can ever observe `status: 'open'` beside stale content.
 */
export const openAgentView = (content: AgentViewContent): void => {
  useAgentViewStore.setState({ status: 'open', content })
}

/**
 * One `suggestions` envelope → one {@link AgentViewContent}. **Total, by construction.**
 *
 * ==== WHY DEFENCE IS MANDATORY HERE AND NOT MERELY PRUDENT (Q6's ruling) ================
 * Two independent reasons, and either one alone would be enough:
 *
 * 1. **The generated type says so.** `SuggestionsPayload.title` and `.items` are BOTH optional
 *    (`types.d.ts:1108-1111`) — for honest, well-formed wires, because an agent that found
 *    nothing sends no items and an agent that named nothing sends no title. So the `?? []` is
 *    the ordinary path, not the malformed one.
 * 2. **`agentEventOf` validates only `kind`** (`client.ts:701-716`). A frame of
 *    `{"kind":"suggestions"}` with no `payload` at all arrives here typed as a full event, and
 *    a `TypeError` thrown on this path would be an uncaught exception inside a socket message
 *    handler: the socket survives it, and the store write behind it does not. Q6 ruled the
 *    narrower stays kind-only (its documented register) and the defence lives HERE.
 *
 * What it does NOT check is any field of any ITEM — see the module header. This function is
 * total about the payload's shape and silent about its contents.
 *
 * The title fallback is the same guard wearing its accessibility hat, and it is applied here
 * because `deferred-work.md`'s dialog-accessible-name entry asks for it *"at the point content
 * is constructed"*: `aria-labelledby` points at the heading, so a blank title is a
 * `role="dialog"` with no discernible name. `.trim()` rather than a truthiness check — `' '` is
 * a title that renders nothing while passing `!== ''`.
 *
 * Args:
 *   event: The frame, exactly as `socket.ts` narrowed it.
 *
 * Returns:
 *   Content the shell can draw, for every input the wire admits.
 */
export const suggestionsViewOf = (event: SuggestionsEvent): AgentViewContent => {
  const rawItems: unknown = event.payload?.items
  const items = Array.isArray(rawItems) ? rawItems : []
  const rawTitle: unknown = event.payload?.title
  const title = typeof rawTitle === 'string' ? rawTitle.trim() : undefined
  return {
    id: event.id,
    ts: event.ts,
    kind: event.kind,
    title: title === undefined || title === '' ? SUGGESTIONS_VIEW_TITLE : title,
    count: items.length,
    items,
  }
}

/**
 * A `suggestions` push arrived: build the content and show it (AC 1, UX-DR34).
 *
 * **The one verb `connection.ts` calls**, and the reason the composition seam needs no
 * `setState` and no store name of its own — `redriveDeckBoot` is the shipped precedent for
 * exactly this shape, and `store-writes.test.ts:112-113` is what would report the alternative.
 *
 * *"Its view opens automatically"* is the confirmed 2026-07-25 ruling, so there is no branch
 * here on whether a view is already open: opening over an open view REPLACES (the scalar), and
 * opening from closed opens. One verb covers both because the store cannot express anything
 * else — and a push arriving while the view is CLOSED with retained content is an open, not a
 * replace, which is what makes it re-run the shell's mount effects (bloom, focus, capture).
 */
export const openSuggestionsPush = (event: SuggestionsEvent): void => {
  openAgentView(suggestionsViewOf(event))
}

/**
 * Dismiss the view — Esc, the close pill, or a click on the scrim (AC 4, AC 5).
 *
 * **It writes `status` and NOTHING ELSE, and that is the whole of UX-DR34.** *"Dismissal never
 * clears content — the view remains re-openable for the rest of the session."* zustand's
 * shallow merge is what makes the omission load-bearing rather than an oversight, so the
 * absence of `content` from this object is the feature; `agentView.test.ts` asserts the
 * retention directly so a later `setState({ status: 'closed', content: null })` cannot pass.
 *
 * Idempotent, like `clearPin`: closing a closed view is a no-op, not an error.
 */
export const closeAgentView = (): void => {
  useAgentViewStore.setState({ status: 'closed' })
}

/**
 * The content of the view that is CURRENTLY SHOWING, or `null` when nothing is.
 *
 * One derivation, exported, so `App.tsx`'s *"is there an overlay"* and any later consumer's
 * *"what am I drawing"* can never disagree — `targetIdOf`'s idiom in `inspection.ts:210`.
 *
 * The returned reference is STABLE: it is either the stored `content` object or `null`, never
 * a fresh object. zustand v5 matches React's referential default, so a selector that built
 * `{ status, content }` here would re-render its consumer on every unrelated store write and,
 * worse, could loop.
 */
export const openViewOf = (state: AgentViewState): AgentViewContent | null =>
  state.status === 'open' ? state.content : null

/**
 * What the overlay slot should show, or `null` for *"render nothing"*.
 *
 * `App.tsx` turns that `null` into an ABSENT `overlay` prop rather than a falsy one —
 * `AppShell.tsx:134-139`'s click-swallower warning is about exactly the difference.
 */
export const useOpenAgentView = (): AgentViewContent | null => useAgentViewStore(openViewOf)
