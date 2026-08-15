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
 * - **It holds per-kind retention and unread flags, and they EXTENDED this shape rather than
 *   reshaping it** (c6-8, and this bullet is the prediction it discharges). {@link
 *   AgentViewState.status} and {@link AgentViewState.content} are untouched and remain the
 *   single source of *"what is on the glass"*; {@link AgentViewState.retained} and {@link
 *   AgentViewState.unread} are BOOKKEEPING BESIDE them, never a second open-view mechanism.
 *   UX-DR38's one-overlay scalar therefore still holds by construction — there is exactly one
 *   `content`, and `retained` is a map of things that are NOT on the glass.
 * - **It holds no focus.** Which element focus returns to on dismissal is one container's
 *   private business for the lifetime of one mount, not shared state — `AgentView.tsx` holds
 *   it in a ref, the way `SkipLink` holds `heldFocus`. c6-8's *"close returns focus to the
 *   pill"* needed no state here either: re-opening from a pill MOUNTS the shell, whose mount
 *   effect captures `document.activeElement` — which is the pill.
 * - **It validates no ITEM.** {@link suggestionsViewOf} is total about the payload's SHAPE —
 *   an absent payload, absent items and a blank title all construct a valid view — and says
 *   nothing about whether a `card_id` resolves. That was c6-7's, and c6-7 did it AT THE ROW
 *   rather than here: `SuggestionsView.tsx` types every item field `unknown` and gates it with
 *   `typeof` before use, so a non-string `card_id` or a missing `reason` degrades that entry
 *   alone (FR-13/AD-7: one bad entry degrades, the push never fails wholesale). This store is
 *   deliberately unchanged by that story — `deferred-work.md:209` is closed at the row.
 */

import { create } from 'zustand'

import type { AgentViewKind, SuggestionItem, SuggestionsEvent } from '../api/schema'

/**
 * **The app's word for each kind of agent view** — the nav pill's label, and the fallback title
 * a view is called when the agent supplies none of its own (stories c6-6 Q7 and c6-8 Task 2).
 *
 * **Copy, and declared as such** — `copy-rules.test.ts`'s `COPY_MODULES` carries this module
 * with that reason. It is the one AUTHORED copy in the state layer, and it is here rather than
 * in a container's `copy.ts` for three reasons that point the same way: `deferred-work.md`'s
 * dialog-accessible-name entry says the guard belongs *"at the point content is constructed"*,
 * which is {@link suggestionsViewOf} below; the nav pill needs the same word for the same kind,
 * so a constant owned by any single container would be the wrong address for the second reader;
 * and Epic 9's three view stories each need their kind's word for a fallback title BEFORE their
 * container exists. c6-6's review kept `SUGGESTIONS_VIEW_TITLE` here explicitly *as the c6-8
 * precedent*, and this table is that precedent honoured: **one word, one owner, four kinds.**
 *
 * Spellings are `EXPERIENCE.md:39-42`'s canonical sentence case. `{typography.label}` uppercases
 * them at render, which is a STYLE and not a spelling — the string a screen reader speaks and
 * the string in this table are the same string, which is why the casing lives in CSS.
 *
 * Names rather than anything assembled from the wire kind (`'tier_list'` de-underscored and
 * title-cased), which was the rejected alternative twice over: a runtime-assembled user-facing
 * string is exactly the residue `copy-rules.test.ts`'s header warns its detector cannot see, and
 * *"Card groups"* is not derivable from `groups` by any rule at all.
 *
 * `satisfies Record<AgentViewKind, string>` is the exhaustiveness gate: a FIFTH agent-view kind
 * added on the Python side reaches {@link AgentViewKind} through the generator and fails
 * `npm run typecheck` here, naming the kind that has no word yet — the same mechanism
 * `socket.ts`'s total dispatch switch uses, applied to vocabulary. `as const` keeps the literal
 * types so {@link SUGGESTIONS_VIEW_TITLE} stays `'Suggestions'` rather than widening to `string`.
 */
export const AGENT_VIEW_LABELS = {
  suggestions: 'Suggestions',
  swaps: 'Swaps',
  tier_list: 'Tier list',
  groups: 'Card groups',
} as const satisfies Record<AgentViewKind, string>

/**
 * The word a `suggestions` view is called when the agent supplies no title of its own (c6-6, Q7).
 *
 * Now READ FROM {@link AGENT_VIEW_LABELS} rather than declared beside it — c6-8's table made
 * this constant the table's `suggestions` entry, so the two can no longer disagree. Kept as a
 * named export because `suggestionsViewOf`'s fallback and three test files name it, and because
 * *"the word THIS kind falls back to"* is a different claim from *"the word this kind is called
 * in the nav"* even while they are the same string.
 */
export const SUGGESTIONS_VIEW_TITLE = AGENT_VIEW_LABELS.suggestions

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
 * envelope, and identity is what tells the shell to re-announce); `ts` IS the nav pill's time
 * and c6-8 renders it (UX-DR28 puts the push time on the pill, and the view header carries
 * none); `kind` IS c6-8's kind-switching discriminant and this story's `{kind}` interpolation in
 * the empty-push line. Retaining them cost one object field each and is what MADE c6-8's
 * *"re-hydrated against current card data"* possible without a second push — the ids and reasons are here, and the
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
  /** The envelope's `ts` — the ordering key, timezone-aware. Rendered as c6-8's pill time. */
  readonly ts: string
  /**
   * Which view this is — **the full four-kind view enum since c6-8**, which is the widening
   * this field's previous docstring predicted (*"c6-8 widens it when it adds the second"*).
   *
   * It widened for the NAV rather than for a second renderable view, and the distinction is
   * this story's central honesty: the socket still drops `swaps`/`tier_list`/`groups` at its
   * dispatch switch (`socket.test.ts:675` pins it, and Epic 9's own preamble is why — a kind
   * must not become *acceptable* before something can display it). So the only kind that can
   * reach this field from the wire today is still `'suggestions'`. What the wider type buys is
   * that {@link AgentViewState.retained}, {@link AgentViewState.unread} and the nav are keyed
   * by the CLOSED ENUM rather than by the kinds that happen to have a view — which is exactly
   * what Story 9.1's acceptance criterion means by *"the Swaps pill becomes active
   * automatically, because the nav is generic over the closed `kind` enum"*.
   */
  readonly kind: AgentViewKind
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
   * The pushed rows, retained unrendered by THIS story and drawn by c6-7's `SuggestionsView`,
   * which also hydrates each unique `card_id` itself (nothing seeds an agent-supplied id).
   * c6-8 re-hydrates them against current card data on re-open, and does. Empty is legal and is not an error
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
   *
   * Still a SCALAR after c6-8, and that is UX-DR38 expressed in the type rather than in a rule
   * anybody has to obey: {@link retained} beside it is a map, but nothing reads a second entry
   * of it onto the glass — `App.tsx`'s overlay conditional is `content`, singular, unchanged.
   */
  readonly content: AgentViewContent | null
  /**
   * **The last view of each kind, kept so a pill can put it back** (c6-8, AC 4).
   *
   * `Partial` rather than a full `Record` with nulls, because *"this kind has never pushed"* is
   * an ABSENT key and not a present empty one: the nav's quiet state (AC 1) is literally
   * `retained[kind] === undefined`, and a `Record<AgentViewKind, AgentViewContent | null>`
   * would make it a value anybody could forget to check. Keys accumulate and are never deleted
   * — the session-long re-openability UX-DR34 promises is exactly this map not shrinking.
   *
   * {@link content} is not a duplicate of `retained[content.kind]`, it is the SAME OBJECT: one
   * `setState` writes both slots from one reference, so no render can read a view from the map
   * that differs from the one on the glass. Re-opening reads the map back into `content`, which
   * is why *"the same content"* in AC 4 is an object identity rather than a deep comparison.
   *
   * The ITEMS ride along, unhydrated. That is what makes AC 4's *"re-hydrated against current
   * card data"* possible with no second push — the ids and reasons are here, and the ART was
   * never retained by anybody (`cards.ts` owns it, and re-mounting the view re-asks).
   */
  readonly retained: Partial<Record<AgentViewKind, AgentViewContent>>
  /**
   * **Which retained views have something the person has not seen** (c6-8, AC 3).
   *
   * `Partial<Record<K, true>>` rather than `Record<K, boolean>` or a `Set`: `true` is the only
   * inhabited value, so *"unread"* is key presence and *"read"* is key absence — there is no
   * `false` to write, and therefore no way to write `false` where `delete` was meant. A `Set`
   * would have been the other honest spelling and was rejected only because zustand's shallow
   * merge compares by reference either way, and a plain object keeps this slice serialisable
   * beside its three siblings.
   *
   * **It has exactly ONE setter, and that is the whole feature** (see {@link openAgentView}): a
   * push always auto-opens its own view, so its own kind is read on arrival; dismissal is
   * Brad's own act, so UX-DR34 forbids it marking anything unread; which leaves DISPLACEMENT —
   * a push of a different kind arriving while another kind's view is open — as the only event
   * that can leave content unseen. Opening a view (by push or by pill) clears its flag.
   */
  readonly unread: Partial<Record<AgentViewKind, true>>
}

/** The state before any agent has pushed anything. Exported so tests can restore it. */
export const INITIAL_AGENT_VIEW: AgentViewState = {
  status: 'closed',
  content: null,
  retained: {},
  unread: {},
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
 * ==== AND SINCE c6-8 IT IS ALSO THE WHOLE KIND-SWITCHING STATE MACHINE (AC 5) ==========
 *
 * Three writes in one `setState`, and the third is the only place in the app that can mark
 * anything unread:
 *
 *   1. **Retain.** `retained[content.kind] = content` — the pill's re-open path (AC 4).
 *   2. **Read.** `unread[content.kind]` is cleared, because this push is ON THE GLASS the
 *      instant this write lands. A push is never unread against itself.
 *   3. **Displace.** If a view of a DIFFERENT kind is currently open, that kind is marked
 *      unread — *"the view switches to the new kind and the previous kind's pill is marked
 *      unread"* (UX-DR34, AC 5). This is what makes *"a push is never silently swallowed"*
 *      true: the displaced view is not lost, it is not on the glass, and the person is told
 *      where it went.
 *
 * The displacement test is `status === 'open' && content.kind !== previous.kind`, and BOTH
 * halves are load-bearing. Without the status check, a push arriving while the view is CLOSED
 * would mark the closed kind unread — but a closed view was dismissed by Brad, and UX-DR34 is
 * explicit that dismissal is never unread. Without the kind check, c6-6's same-kind replace
 * would mark the kind it is replacing *in place* as unread, which is a pill saying *"you
 * haven't seen this"* about the thing being looked at.
 *
 * A same-kind push is therefore untouched by all of this: steps 1 and 2 rewrite the same key,
 * step 3 does not fire, and c6-6's replace-in-place behaves exactly as it shipped.
 *
 * Args:
 *   content: What the shell draws. Written together with the status, the retention and the
 *     unread bookkeeping in ONE `setState`, so no render can ever observe `status: 'open'`
 *     beside stale content — or a pill that is unread and open at the same time.
 */
export const openAgentView = (content: AgentViewContent): void => {
  useAgentViewStore.setState((state) => {
    const displaced =
      state.status === 'open' && state.content !== null && state.content.kind !== content.kind
        ? state.content.kind
        : null
    // Rebuilt rather than mutated: zustand compares slices by reference, so a pill subscribed
    // to `unread` must see a NEW object or it will not re-render. Same for `retained`.
    const unread = { ...state.unread }
    delete unread[content.kind]
    if (displaced !== null) unread[displaced] = true
    return {
      status: 'open',
      content,
      retained: { ...state.retained, [content.kind]: content },
      unread,
    }
  })
}

/**
 * Put a retained view back on the glass from its nav pill (c6-8, AC 4).
 *
 * **A no-op unless that kind has pushed this session**, which is the store half of AC 1's quiet
 * pill: the container disables a pill with no retained content, and this refuses the same call
 * again here, so *"nothing happens"* is true whether a caller respects the disabled attribute
 * or not. It never invents content and never re-requests: everything it needs was retained by
 * {@link openAgentView} when the push arrived, which is what *"nothing is re-requested from the
 * agent"* means in AC 4.
 *
 * ==== WHAT IT DELIBERATELY DOES NOT DO ================================================
 *
 * **It does not displace anything.** Re-opening cannot be a kind switch, because a pill cannot
 * be clicked while a view is open — the scrim covers the header and the focus trap holds Tab
 * inside the dialog (UX-DR38's one-level stack). So there is no *"previous kind"* to mark
 * unread here, and writing the displacement branch twice would be encoding a state the UI
 * cannot reach. Kind switching while open is push-driven ONLY, and it lives in
 * {@link openAgentView} alone.
 *
 * **It re-uses {@link openAgentView} rather than re-implementing it** — same three writes,
 * with `retained[kind]` supplying the content instead of the wire. The retention rewrite is a
 * self-assignment and the unread clear is the point: *"the accent unread dot until its view is
 * opened"* (AC 3) is discharged by opening, by either route.
 *
 * **It re-opens by MOUNTING.** `App.tsx` renders the overlay only while a view is open, so this
 * write remounts `AgentView` — entry bloom, focus-to-heading and the return-focus capture (which
 * grabs the pill, since the pill is what was just clicked) all re-fire with no code of their own,
 * and `SuggestionsView`'s `items`-keyed hydration effect re-runs against the CURRENT card cache,
 * which is where AC 4's *"stale ids degrade to unknown-card placeholders"* comes from. None of
 * that is this function's doing; all of it is why this function can be four lines.
 *
 * Args:
 *   kind: Which pill was activated.
 */
export const reopenAgentView = (kind: AgentViewKind): void => {
  const retained = useAgentViewStore.getState().retained[kind]
  if (retained === undefined) return
  openAgentView(retained)
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
 *
 * **c6-8 added two fields and this verb still writes neither**, which is the same omission
 * doing twice the work. It does not clear `retained` — that would delete the thing the nav pill
 * exists to put back, and UX-DR34's *"re-openable for the rest of the session"* would survive
 * only until the first dismissal. And it does not SET `unread` — dismissal is Brad's own act, so
 * a pill that grew an unread dot the moment he closed the view would be telling him he has not
 * seen the thing he just closed. Both are asserted directly in `agentView.test.ts`, so a later
 * `setState({ status: 'closed', content: null, retained: {} })` cannot pass.
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

/**
 * **Is a view on the glass right now** — a BOOLEAN, and the distinction from
 * {@link useOpenAgentView} beside it is the whole reason this exists (story c7-6).
 *
 * `DeckAnnouncer` needs one bit: *"is something modal covering the deck"*, so that a coalesced
 * refetch settling behind an open view is dropped rather than spoken over a person reading a
 * dialog about something else. Reading that bit through `useOpenAgentView` would subscribe the
 * announcer to the CONTENT OBJECT — a fresh reference on every push, carrying items, title and
 * count — and break the *"NARROWED TO PRIMITIVES, one field per subscription"* discipline that
 * component's own selectors are written under. A primitive compares by value, so a second
 * `suggestions` push while a view is already open re-renders the announcer not at all.
 *
 * **`status` alone is a sound reading of "a view is showing".** All four writers move it —
 * {@link openAgentView} to `'open'`, {@link reopenAgentView} and {@link openSuggestionsPush}
 * through it, {@link closeAgentView} to `'closed'` — and `status: 'open'` beside a null
 * `content` is unreachable: `openAgentView` writes both in ONE `setState`, which is the
 * invariant {@link openViewOf} already leans on for its own narrowing. So this hook and that
 * one can never disagree about whether something is showing; they disagree only about how much
 * of it a subscriber has to look at.
 */
export const useAgentViewIsOpen = (): boolean =>
  useAgentViewStore((state) => state.status === 'open')

/**
 * Whether this kind has ever pushed this session (c6-8, AC 1/AC 2) — the pill's quiet-vs-active
 * signal, kept independent of whether that push's `ts` happened to be well-formed.
 *
 * **`retained[kind] !== undefined`, not any field on it — least of all `ts`.** `agentEventOf`
 * validates only the `kind` discriminant (`client.ts:701-716`), so a malformed frame can retain
 * with `ts` absent or unparseable; the pill must still read as *pushed* in that case, because the
 * content is real and was already shown once. Deciding activeness from `.ts` presence instead
 * (as {@link useAgentViewPushTime} alone once did) collapses "pushed, timestamp unreadable" into
 * "never pushed" — a malformed `ts` would then make a session's retained view permanently
 * unreachable via its pill after the next dismissal, which is exactly what UX-DR34's *"the view
 * remains re-openable for the rest of the session"* forbids. A bad `ts` degrades only the time
 * this pill shows, via {@link useAgentViewPushTime} and `pushTimeLabel` — never the pill's own
 * reachability.
 *
 * Args:
 *   kind: Which pill is asking.
 */
export const useAgentViewHasPush = (kind: AgentViewKind): boolean =>
  useAgentViewStore((state) => state.retained[kind] !== undefined)

/**
 * When this kind last pushed (the envelope's `ts`), or `null` if it never has or that push's
 * `ts` was absent (c6-8, AC 2).
 *
 * **Time only, not activeness** — {@link useAgentViewHasPush} answers "quiet or active", this
 * answers "what time to show on an active pill", and the two can disagree: a retained push with
 * no readable `ts` is active (per `useAgentViewHasPush`) with no time (per this hook). Splitting
 * them is what keeps a malformed `ts` a display-only degradation instead of a reachability bug.
 *
 * A STRING, not the content object, for `usePinnedId`'s reason: the pill renders the time and
 * nothing else from the retained view, and a selector returning the object would re-render every
 * pill whenever any view's ITEMS changed. Primitives compare by value, so a push to `swaps`
 * cannot re-render the `suggestions` pill — which is the *"a push re-renders only the affected
 * pill"* property this story asked the selectors for.
 *
 * Args:
 *   kind: Which pill is asking.
 */
export const useAgentViewPushTime = (kind: AgentViewKind): string | null =>
  useAgentViewStore((state) => state.retained[kind]?.ts ?? null)

/**
 * Whether this kind's retained view has been displaced unseen (c6-8, AC 3) — the accent dot.
 *
 * `=== true` rather than a truthiness coercion, so the boolean this returns is a real boolean
 * for every input including a kind with no entry: `undefined` would otherwise leak out of a
 * function typed `boolean` on the one path that matters most (a kind that never pushed).
 *
 * Args:
 *   kind: Which pill is asking.
 */
export const useAgentViewUnread = (kind: AgentViewKind): boolean =>
  useAgentViewStore((state) => state.unread[kind] === true)
