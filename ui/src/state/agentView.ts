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
 *     and from c6-6 the writer is a WebSocket message, which is the spine sentence's own
 *     second input. Nothing narrowed.
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
 * replace-in-place wants.
 *
 * A stack would also have needed a `--z-*` token family to order its levels against, which
 * `AppShell.css:246-250` and `deferred-work.md:1473-1482` both refuse for the same reason.
 *
 * ================= WHAT THIS MODULE DELIBERATELY DOES NOT DO ==========================
 *
 * - **It renders nothing.** `containers/AgentView` draws; this decides. It imports no React.
 * - **It does not listen to the socket.** `socket.ts:402-430` still drops the four view kinds
 *   on purpose and `AgentSocketOptions` still has no view callback — c6-6 is the story that
 *   wires a push to {@link openAgentView}, and until it lands the only caller is a test.
 * - **It holds no unread flag and no per-kind retention.** Those are c6-8's (nav pills,
 *   unread markers, kind switching) and they EXTEND this shape rather than reshape it.
 * - **It holds no focus.** Which element focus returns to on dismissal is one container's
 *   private business for the lifetime of one mount, not shared state — `AgentView.tsx` holds
 *   it in a ref, the way `SkipLink` holds `heldFocus`.
 */

import { create } from 'zustand'

/**
 * What the shell needs in order to draw its header — and nothing else.
 *
 * Deliberately NOT a wire shape. `schema.ts` aliases over the generated `types.d.ts` are the
 * only permitted source for envelopes (`SuggestionsEvent` at `:1080-1094`), and this story
 * pushes nothing: c6-6 is what turns a `suggestions` envelope into one of these, and c6-7 is
 * what renders rows from it. Two fields is what c6-5 can honestly hold, so two fields is what
 * it declares — a speculative `envelope` field would be a wire shape hand-written a story
 * early, which is the one thing `schema.ts` exists to prevent.
 */
export interface AgentViewContent {
  /** The view's heading (`DESIGN.md:471` — title in `{typography.heading}`). */
  readonly title: string
  /**
   * The summary count beside the title, or `null` when the view has nothing to count. Nullable
   * rather than defaulting to `0`, because *"0 suggestions"* and *"a view that does not count
   * things"* are different sentences and the header renders them differently.
   */
  readonly count: number | null
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
 * scalar's only possible behaviour, and the half of c6-6's replace-in-place contract this store
 * can honestly claim. The other half is `AgentView.tsx`'s: without a `key`, `App.tsx`'s render
 * of `<AgentView>` reconciles a content swap as a prop update on the same instance, so the
 * mount-only focus-to-heading and entry-bloom effects do not re-fire for it. That remount
 * mechanics is still owed to c6-6 (found at code review, 2026-08-10) — this store only
 * guarantees the DATA is correct the instant a consumer reads it.
 *
 * Args:
 *   content: What the shell draws. Written together with the status, in ONE `setState`, so no
 *     render can ever observe `status: 'open'` beside stale content.
 */
export const openAgentView = (content: AgentViewContent): void => {
  useAgentViewStore.setState({ status: 'open', content })
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
