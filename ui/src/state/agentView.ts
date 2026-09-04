/**
 * Whether an agent view is on the glass, and what it is showing (UX-DR34, UX-DR38, AD-12).
 *
 * The content is server-derived (a WebSocket push, written via `connection.ts`); the open/closed
 * status is a person's. Both live in one slice because the invariant is about their relationship:
 * *"dismissal never clears content — the view remains re-openable for the rest of the session"*
 * (UX-DR34). `content` is a single slot, not an array, because UX-DR38 fixes the overlay stack at
 * one level: opening while open REPLACES. This module renders nothing, listens to no socket
 * itself, holds no focus, and validates no ITEM — each view degrades a bad entry at the row that
 * renders it (FR-13/AD-7).
 */

import { create } from 'zustand'

import type {
  AgentViewKind,
  GroupItem,
  GroupsEvent,
  SuggestionItem,
  SuggestionsEvent,
  SwapItem,
  SwapsEvent,
  TierItem,
  TierListEvent,
} from '../api/schema'

/**
 * The app's word for each kind of agent view — the nav pill's label and the fallback view title.
 * Authored copy (`copy-rules.test.ts`'s `COPY_MODULES`), homed here because the accessible-name
 * guard belongs where content is constructed and the pill needs the same word. Names, not strings
 * assembled from the wire kind: *"Card groups"* is not derivable from `groups`. `satisfies` makes
 * a fifth kind added on the Python side fail `npm run typecheck` here, naming the missing word.
 */
export const AGENT_VIEW_LABELS = {
  suggestions: 'Suggestions',
  swaps: 'Swaps',
  tier_list: 'Tier list',
  groups: 'Card groups',
} as const satisfies Record<AgentViewKind, string>

/**
 * The word a `suggestions` view is called when the agent supplies no title. Read from
 * {@link AGENT_VIEW_LABELS} so the two cannot disagree; kept as a named export because the
 * fallback in `suggestionsViewOf` and several tests name it.
 */
export const SUGGESTIONS_VIEW_TITLE = AGENT_VIEW_LABELS.suggestions

/**
 * The fields every kind of view carries. NOT a wire shape — nothing downstream holds a frame — but
 * every item type is the generated model through its alias, so it cannot drift from the Python
 * side. `id`, `ts` and `kind` are retained though the shell renders none of them: they key the
 * replace effect, the pill time (UX-DR28) and the kind switch.
 */
interface AgentViewContentBase {
  /** The envelope's `id` — opaque identity, NO ordering. The REPLACE KEY. */
  readonly id: string
  /** The envelope's `ts` — the ordering key, timezone-aware. Rendered as the pill time. */
  readonly ts: string
  /** The view's heading. */
  readonly title: string
  /** The count beside the title, or `null` for a view that counts nothing. `0` is real and renders. */
  readonly count: number | null
}

/**
 * What the shell draws — a per-kind discriminated union, because one flat `items` type is a lie
 * the moment two kinds carry different item shapes. Every view's props derive from its own arm by
 * narrowing, never from wire types, which `wire-contract.test.ts` bans outside `src/api/`.
 */
export type AgentViewContent =
  | (AgentViewContentBase & {
      readonly kind: 'suggestions'
      /**
       * The pushed rows, drawn by `SuggestionsView`, which hydrates each unique `card_id` itself.
       * Empty is legal: *"the view skips an empty push rather than rejecting it"*.
       */
      readonly items: readonly SuggestionItem[]
    })
  | (AgentViewContentBase & {
      readonly kind: 'swaps'
      /** The pushed trades, drawn by `SwapsView`, which hydrates both ids of each pair itself. */
      readonly items: readonly SwapItem[]
    })
  | (AgentViewContentBase & {
      readonly kind: 'tier_list'
      /**
       * The pushed tiers, drawn by `TierListView`. `count` is `items.length` — payload TIERS, raw:
       * the view's empty-tier skipping is render-only and never rewrites the count.
       */
      readonly items: readonly TierItem[]
    })
  | (AgentViewContentBase & {
      readonly kind: 'groups'
      /**
       * The pushed groups, drawn by `GroupsView`. `count` is `items.length` — payload GROUPS,
       * raw: the view's empty-group skipping is render-only and never rewrites it.
       */
      readonly items: readonly GroupItem[]
    })

/**
 * The slice. A flat shape rather than `deck.ts`'s wrapped union because zustand's shallow merge is
 * exactly the semantics wanted: writing `status` must leave `content` alone.
 */
export interface AgentViewState {
  /** Whether a view is on the glass. `'closed'` with content is the re-openable state. */
  readonly status: 'open' | 'closed'
  /**
   * The ONE slot (UX-DR38). `null` only before the first push of the session; nothing in this
   * module ever writes it back to `null` (UX-DR34).
   */
  readonly content: AgentViewContent | null
  /**
   * The last view of each kind, so a pill can put it back. `Partial` because *"never pushed"* is
   * an ABSENT key; keys are never deleted (UX-DR34). `content` is the SAME OBJECT as
   * `retained[content.kind]`, so re-opening is an identity. Items ride along unhydrated.
   */
  readonly retained: Partial<Record<AgentViewKind, AgentViewContent>>
  /**
   * Which retained views the person has not seen. `Partial<Record<K, true>>`: *"unread"* is key
   * presence, so there is no `false` to write where `delete` was meant. Exactly ONE setter
   * ({@link openAgentView}): dismissal never marks unread (UX-DR34), so DISPLACEMENT by a push of
   * another kind is the only event that can leave content unseen.
   */
  readonly unread: Partial<Record<AgentViewKind, true>>
  /**
   * The session's last {@link HISTORY_CAP} pushes overall, newest first (FR-18) — the SAME
   * references the other slots hold. Ordered by envelope `ts`, never by `id` (opaque); an
   * unparseable `ts` falls back to arrival position rather than silently reordering. See
   * {@link historyWith}, the one writer of this shape.
   */
  readonly history: readonly AgentViewContent[]
}

/** The retention capacity FR-18 fixes: the last 20 pushes overall. */
export const HISTORY_CAP = 20

/** The state before any agent has pushed anything. Exported so tests can restore it. */
export const INITIAL_AGENT_VIEW: AgentViewState = {
  status: 'closed',
  content: null,
  retained: {},
  unread: {},
  history: [],
}

/** One store, no second state library (AD-12); `store-writes.test.ts` names this module its writer. */
export const useAgentViewStore = create<AgentViewState>(() => INITIAL_AGENT_VIEW)

/**
 * Forget everything, including the retained content. **For tests only** — the store is
 * module-level. This is the ONLY function that clears `content`, and it is unreachable from the
 * app, which is what keeps UX-DR34 true of every production path.
 */
export const resetAgentView = (): void => {
  useAgentViewStore.setState(INITIAL_AGENT_VIEW, true)
}

/**
 * The envelope's `ts` as a comparable instant, or `null` when absent, non-string or unparseable
 * (all reachable: `agentEventOf` validates only `kind`). `typeof`-guarded because `new Date(null)`
 * is EPOCH 0 and a number is milliseconds — either would sort a malformed push as decades old and
 * silently drop it at the cap instead of taking the arrival-position fallback.
 */
const instantOf = (ts: unknown): number | null => {
  if (typeof ts !== 'string') return null
  const at = new Date(ts).getTime()
  return Number.isNaN(at) ? null : at
}

/**
 * `history` with `content` filed into it. The same reference already present returns the ARRAY
 * ITSELF (a re-open is not a new push, and the stable reference spares history subscribers); the
 * same `id` on a different object is REPLACED IN PLACE; a new id is INSERTED newest-first by `ts`,
 * stopping at the first entry it cannot rank, and the oldest drops silently at the cap — the
 * arrival itself included, if it is older than all twenty.
 */
const historyWith = (
  history: readonly AgentViewContent[],
  content: AgentViewContent,
): readonly AgentViewContent[] => {
  const existing = history.findIndex((entry) => entry.id === content.id)
  if (existing !== -1) {
    if (history[existing] === content) return history
    const replaced = [...history]
    replaced[existing] = content
    return replaced
  }
  const at = instantOf(content.ts)
  let index = 0
  if (at !== null) {
    while (index < history.length) {
      const ranked = instantOf(history[index].ts)
      if (ranked === null || ranked <= at) break
      index += 1
    }
  }
  const inserted = [...history.slice(0, index), content, ...history.slice(index)]
  return inserted.length > HISTORY_CAP ? inserted.slice(0, HISTORY_CAP) : inserted
}

/**
 * Show a view. Opening while one is open REPLACES it (the shell's half of replace-in-place is
 * `AgentView.tsx`'s `id`-keyed effect on a `key`-less instance). Three writes in ONE `setState`,
 * so no render observes `status: 'open'` beside stale content or a pill both unread and open:
 * retain (except on a HISTORY REVISIT of a non-latest entry, which must not corrupt
 * latest-per-kind); clear this kind's unread; and mark the displaced kind unread only if a view of
 * a DIFFERENT kind is currently OPEN (UX-DR34) — without the status check a dismissed view would
 * be marked unread, without the kind check a same-kind replace would mark the thing being looked at.
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
    // Identity here is REFERENCE identity — the latest entry for a kind holds the SAME object as
    // `retained[kind]` (`ts` is unsafe to rank and `id` carries no order). An entry already filed
    // in `history` that is NOT that object is an older envelope being revisited: the view opens
    // it, but the retained slot — and the pills' recency — stays where the newest push left it.
    const revisit = state.history.includes(content) && content !== state.retained[content.kind]
    return {
      status: 'open',
      content,
      retained: revisit ? state.retained : { ...state.retained, [content.kind]: content },
      unread,
      history: historyWith(state.history, content),
    }
  })
}

/**
 * Put a retained view back on the glass from its nav pill. A no-op unless that kind has pushed
 * this session; never re-requests. A pill cannot be clicked while a view is open, so this cannot
 * displace anything and kind switching stays in {@link openAgentView} alone. Remounting the
 * overlay re-runs the view's hydration against the CURRENT card cache, so stale ids degrade to
 * unknown-card placeholders with no code here.
 */
export const reopenAgentView = (kind: AgentViewKind): void => {
  const retained = useAgentViewStore.getState().retained[kind]
  if (retained === undefined) return
  openAgentView(retained)
}

/**
 * Put ONE push from the session history back on the glass, by envelope `id` — the verb a
 * history-popover entry activates. A no-op for an id history does not hold. The entry IS the
 * retained reference, so {@link openAgentView} leaves the history array untouched: a revisit never
 * duplicates and never reorders.
 */
export const reopenPush = (id: string): void => {
  const entry = useAgentViewStore.getState().history.find((held) => held.id === id)
  if (entry === undefined) return
  openAgentView(entry)
}

/**
 * One `suggestions` envelope → one {@link AgentViewContent}. Total by construction: the payload's
 * `title` and `items` are optional for honest wires, and `agentEventOf` validates only `kind`, so a
 * payload-less frame arrives typed as a full event and a `TypeError` here would be an uncaught
 * exception inside a socket handler. The title fallback guards the dialog's accessible name;
 * `.trim()` because `' '` renders nothing while passing `!== ''`. It checks no field of any ITEM.
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
 * One `swaps` envelope → one {@link AgentViewContent}; {@link suggestionsViewOf}'s defence applies
 * verbatim. Item fields are `SwapsView`'s to degrade, at the row that renders them.
 */
export const swapsViewOf = (event: SwapsEvent): AgentViewContent => {
  const rawItems: unknown = event.payload?.items
  const items = Array.isArray(rawItems) ? rawItems : []
  const rawTitle: unknown = event.payload?.title
  const title = typeof rawTitle === 'string' ? rawTitle.trim() : undefined
  return {
    id: event.id,
    ts: event.ts,
    kind: event.kind,
    title: title === undefined || title === '' ? AGENT_VIEW_LABELS.swaps : title,
    count: items.length,
    items,
  }
}

/**
 * One `tier_list` envelope → one {@link AgentViewContent}; {@link suggestionsViewOf}'s defence
 * applies verbatim. `count` is payload TIERS, raw — the view's empty-tier skipping is render-only.
 */
export const tierListViewOf = (event: TierListEvent): AgentViewContent => {
  const rawItems: unknown = event.payload?.items
  const items = Array.isArray(rawItems) ? rawItems : []
  const rawTitle: unknown = event.payload?.title
  const title = typeof rawTitle === 'string' ? rawTitle.trim() : undefined
  return {
    id: event.id,
    ts: event.ts,
    kind: event.kind,
    title: title === undefined || title === '' ? AGENT_VIEW_LABELS.tier_list : title,
    count: items.length,
    items,
  }
}

/**
 * One `groups` envelope → one {@link AgentViewContent}; {@link suggestionsViewOf}'s defence
 * applies verbatim. The fallback title is the PAYLOAD-LEVEL header, distinct from each group's
 * own `title`. `count` is payload GROUPS, raw — the view's skipping is render-only.
 */
export const groupsViewOf = (event: GroupsEvent): AgentViewContent => {
  const rawItems: unknown = event.payload?.items
  const items = Array.isArray(rawItems) ? rawItems : []
  const rawTitle: unknown = event.payload?.title
  const title = typeof rawTitle === 'string' ? rawTitle.trim() : undefined
  return {
    id: event.id,
    ts: event.ts,
    kind: event.kind,
    title: title === undefined || title === '' ? AGENT_VIEW_LABELS.groups : title,
    count: items.length,
    items,
  }
}

/**
 * A `suggestions` push arrived: build the content and show it (UX-DR34). The one verb
 * `connection.ts` calls for this kind, so the composition seam needs no `setState` of its own. A
 * view opens automatically on arrival, so there is no branch on whether one is already open.
 */
export const openSuggestionsPush = (event: SuggestionsEvent): void => {
  openAgentView(suggestionsViewOf(event))
}

/** A `swaps` push arrived: build the content and show it, in {@link openSuggestionsPush}'s shape. */
export const openSwapsPush = (event: SwapsEvent): void => {
  openAgentView(swapsViewOf(event))
}

/** A `tier_list` push arrived: build the content and show it, in {@link openSuggestionsPush}'s shape. */
export const openTierListPush = (event: TierListEvent): void => {
  openAgentView(tierListViewOf(event))
}

/** A `groups` push arrived: build the content and show it, in {@link openSuggestionsPush}'s shape. */
export const openGroupsPush = (event: GroupsEvent): void => {
  openAgentView(groupsViewOf(event))
}

/**
 * Dismiss the view — Esc, the close pill, or a scrim click. It writes `status` and NOTHING ELSE,
 * which is the whole of UX-DR34: zustand's shallow merge makes the omission load-bearing. It does
 * not clear `retained` and does not SET `unread`; `agentView.test.ts` asserts all three. Idempotent.
 */
export const closeAgentView = (): void => {
  useAgentViewStore.setState({ status: 'closed' })
}

/**
 * The content of the view CURRENTLY SHOWING, or `null`. One derivation, exported, so consumers
 * cannot disagree. The reference is STABLE (the stored object or `null`): zustand v5 compares by
 * reference, so a selector building a fresh object would re-render on every write and could loop.
 */
export const openViewOf = (state: AgentViewState): AgentViewContent | null =>
  state.status === 'open' ? state.content : null

/**
 * What the overlay slot should show, or `null` for *"render nothing"* — which `App.tsx` turns
 * into an ABSENT `overlay` prop rather than a falsy one (see `AppShell.tsx`'s click-swallower).
 */
export const useOpenAgentView = (): AgentViewContent | null => useAgentViewStore(openViewOf)

/**
 * Is a view on the glass right now — a BOOLEAN, so `DeckAnnouncer`'s one bit does not re-render
 * on every push. `status` alone is sound: `status: 'open'` beside a null `content` is unreachable
 * because `openAgentView` writes both in ONE `setState`.
 */
export const useAgentViewIsOpen = (): boolean =>
  useAgentViewStore((state) => state.status === 'open')

/**
 * Whether this kind has ever pushed this session — the pill's quiet-vs-active signal. Key
 * presence, not any field on the entry — least of all `ts`: a malformed frame can retain with
 * `ts` unparseable, and deciding from it would make that view unreachable via its pill after the
 * next dismissal (UX-DR34). A bad `ts` degrades only the time shown.
 */
export const useAgentViewHasPush = (kind: AgentViewKind): boolean =>
  useAgentViewStore((state) => state.retained[kind] !== undefined)

/**
 * When this kind last pushed (the envelope's `ts`), or `null` if it never has or the `ts` was
 * absent. Time only, not activeness — the split keeps a malformed `ts` a display-only degradation.
 * A STRING, not the content object, so a push to `swaps` cannot re-render the `suggestions` pill.
 */
export const useAgentViewPushTime = (kind: AgentViewKind): string | null =>
  useAgentViewStore((state) => state.retained[kind]?.ts ?? null)

/**
 * Whether this kind's retained view has been displaced unseen — the accent dot. `=== true` rather
 * than a truthiness coercion, so a kind with no entry yields a real `false`, not `undefined`.
 */
export const useAgentViewUnread = (kind: AgentViewKind): boolean =>
  useAgentViewStore((state) => state.unread[kind] === true)

/**
 * The session's push history, newest first — what the history popover renders. The STORED ARRAY
 * REFERENCE, never a derivation: a selector that filtered or mapped here would mint a fresh array
 * every read and loop.
 */
export const useAgentViewHistory = (): readonly AgentViewContent[] =>
  useAgentViewStore((state) => state.history)

/**
 * How many pushes the session history holds — the History pill's quiet bit. A PRIMITIVE beside
 * the array hook, because the pill renders no entries and must not re-render on every push.
 */
export const useAgentViewHistoryCount = (): number =>
  useAgentViewStore((state) => state.history.length)
