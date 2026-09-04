/**
 * The wire vocabulary mapped onto the panel vocabulary — and they are NOT the same set, in
 * either direction.
 *
 * Measured against `ui/src/api/types.d.ts` and `src/api/schema.test.ts`:
 *
 *   `deck_not_found`            -> the No-active-deck panel  (many-to-one: the SPA clears to it)
 *   `database_not_initialized`  -> the Card-database-not-set-up panel
 *   `database_unavailable`      -> the Card-database-is-updating panel (quiet retry)
 *   `internal_error`            -> the fifth panel, deterministic and NEVER self-retrying
 *   `card_not_found`            -> NO PANEL, but a NAMED NON-PANEL DESTINATION (see below)
 *   `no_image_data`             -> NO PANEL; the NAMED CARD placeholder in one tile
 *   `image_fetch_failed`        -> NO PANEL; the same placeholder, for a different reason
 *   `invalid_request`           -> NO UI RESPONSE AT ALL, by design
 *   `forbidden`                 -> NO UI RESPONSE AT ALL, by design (agent-facing)
 *   `payload_too_large`         -> NO UI RESPONSE AT ALL, by design
 *   (no token at all)           -> Disconnected, and Database-updating-stalled
 *
 * So `Record<ErrorReason, StateKey>` is the wrong shape twice over: six tokens must be allowed
 * to map to *no* panel, and two panels have no token. `Record<ErrorReason, StateKey | null>` is
 * the shape that is total without being one-to-one, and `null` is a NAMED answer here rather
 * than an absence — see the comments below, which are the whole reason those tokens exist.
 *
 * ================= `null` MEANS TWO DIFFERENT THINGS, SO IT IS CLASSIFIED ===============
 *
 * `invalid_request`, `forbidden` and `payload_too_large` are `null` because there is nothing to
 * put on the glass at all — for one the user cannot act, for the other two the audience is the
 * *agent*. `card_not_found` is `null` because its destination is **not a panel**: the view
 * renders normally and one slot becomes the unknown-card placeholder (`EXPERIENCE.md`'s
 * "Unknown card in a view" row).
 *
 * Writing all of them as a bare `null` beside each other would discard exactly the token/UI
 * pairing — "a token ships alone and a comment promises the rest" is how `internal_error` once
 * arrived without a panel. So the distinction is TYPED AND GATED below (`PLACEHOLDER_FOR_REASON`,
 * `NO_UI_RESPONSE` and the three asserts at the bottom), not left to this paragraph: a future
 * `null` that is classified as neither, or as both, fails `npm run typecheck` naming the token.
 *
 * The copy itself is deliberately NOT here. "Unknown card" is prose, and prose may only live in a
 * copy module — `tests/copy-rules.test.ts`'s file half would fail this file for containing it.
 * This file carries the destination's NAME, which is chrome; `tests/unknown-card-copy.test.ts`
 * ties that name to the artefact's label.
 *
 * ================= EXHAUSTIVENESS IS PROVED BY THE TYPE, NOT BY A TEST ==================
 *
 * `satisfies Record<ErrorReason, …>` is what makes a new wire token fail `npm run typecheck`
 * rather than silently lose a state — measured, by deleting a token from the map and running both
 * gates: `npx tsc -b --force` reported FIVE errors (`TS1360` here naming the missing property, plus
 * `TS2344: Type 'false' does not satisfy the constraint 'true'` twice, from the classification
 * asserts at the bottom of this file), while `vitest run` in the same state reported only ONE
 * failure, from a runtime assertion on the value. That ratio is the whole argument: a runtime test
 * that enumerated today's tokens would prove nothing — `src/api/schema.test.ts` says so, with a
 * measured example: `expectTypeOf` assertions erase to an empty test body, so `vitest run` reports
 * green over a wire type that has been mutated out from under it. **`npm run typecheck` is the
 * gate for this file.**
 *
 * `satisfies` rather than a type annotation, deliberately: an annotation would widen the values
 * to `StateKey | null` and throw away the literal types, which is exactly what the completeness
 * proof at the bottom of this file reads.
 */

import type { ErrorReason } from '../../api/schema'
import type { StateKey } from './copy'

/**
 * Which panel a reason token puts on the glass. `null` means **no panel, by design** — not
 * "not decided yet" — and every `null` is further classified below as either a named non-panel
 * destination (`PLACEHOLDER_FOR_REASON`) or no UI response at all (`NO_UI_RESPONSE`).
 */
export const PANEL_FOR_REASON = {
  // Many-to-one. A deck deleted between a push and a refetch (FR-11) is not an error state of
  // its own — the honest thing on screen is "there is no active deck", which is the panel that
  // already exists and already lists the decks that remain.
  deck_not_found: 'no-active-deck',
  database_not_initialized: 'database-not-initialized',
  database_unavailable: 'database-updating',
  // NO PANEL, BUT NOT "NOTHING". Unlike the two below, this token HAS a UI destination — it is
  // simply not a panel: the surrounding view renders normally and one slot becomes the
  // unknown-card placeholder. A whole-screen panel here would be the FR-13 failure the
  // artefact names outright ("No banner, no apology"): one unresolvable card must never take
  // down a deck view or a push. See `PLACEHOLDER_FOR_REASON` below, which is where that
  // destination is recorded in a form the compiler reads.
  card_not_found: null,
  // NO PANEL, BUT NOT "NOTHING" — the same shape as `card_not_found` above, and the same reason.
  // The card resolved; only its picture did not, so the view renders normally and that one tile
  // draws the NAMED CARD placeholder (name + mana pips + type line) instead of art. A panel here
  // would take a whole deck view down because one image was missing, which is the FR-13 posture
  // read across to FR-19. See `PLACEHOLDER_FOR_REASON`.
  no_image_data: null,
  // …and its twin. THESE TWO RENDER IDENTICALLY AND ARE STILL TWO TOKENS, which is the one thing
  // to understand about this pair: the difference is not what the reader sees, it is whether a
  // retry could ever change it. `no_image_data` is permanent (the row has no artwork); this one
  // is transient (the CDN did not deliver). The image negative cache and backoff act on the
  // difference — and need no wire change at all, because the vocabulary is here.
  image_fetch_failed: null,
  // NO UI RESPONSE AT ALL, BY DESIGN. The SPA never generates a malformed request, so this
  // token means a client bug or a stray caller on the port. There is nothing the user can do
  // about either, and a panel saying so would be the app blaming its own reader; the log is
  // where it is diagnosed (see `types.d.ts`).
  invalid_request: null,
  // NO UI RESPONSE AT ALL, BY DESIGN. An agent-only endpoint was called without a valid
  // credential (PUT /api/active-deck). The browser NEVER holds the agent token and never
  // calls a route that wants one (AD-5), so this token reaching the glass would mean reporting a
  // failure the reader did not cause and cannot fix. Its real audience is the agent, where AD-8's
  // "re-read the discovery file and retry exactly once" lives — which is the whole reason it is a
  // token of its own instead of another `invalid_request`.
  forbidden: null,
  // NO UI RESPONSE AT ALL, BY DESIGN. An agent push over the ingest cap is surfaced to the
  // AGENT, through the MCP tool's outcome vocabulary — the party that can actually send a smaller
  // one. The glass never sees it. The pre-parse 64 KB body cap produces this token; the `null`
  // is deliberate all the same: a reachable failure the reader did not cause and cannot fix is
  // not a reason to grow a panel.
  payload_too_large: null,
  internal_error: 'internal-error',
} satisfies Record<ErrorReason, StateKey | null>

/**
 * The non-panel UI destinations a reason token can have. A SEPARATE VOCABULARY from `StateKey`,
 * deliberately: `StateKey` is the panel vocabulary — every member of it has a row in
 * `EXPERIENCE.md`'s two-field Headline+Body table, a `STATE_COPY` entry and a `RETRIES_QUIETLY`
 * decision. The unknown-card placeholder has none of those and should have none: it is a label
 * in one slot of an otherwise-normal view, and adding it to `StateKey` would make
 * `EveryPanelHasASource` demand a source for a panel nobody renders.
 */
export type PlaceholderKey = 'unknown-card' | 'named-card'

/**
 * Tokens whose destination is a named UI element that is **not a panel**.
 *
 * `card_not_found`'s destination is `EXPERIENCE.md`'s "Unknown card in a view" row — a
 * placeholder label plus a truncated id, in the one slot that could not be hydrated, with the
 * rest of the view untouched. This entry is the machine-readable half of the token/UI pairing,
 * and `tests/unknown-card-copy.test.ts` is what holds the label to the artefact.
 *
 * The image tokens are `named-card`, and the distinction from `unknown-card` is a real one rather than a
 * second name for the same thing. `unknown-card` means **the app does not know what this card is**
 * — there is nothing to draw but an id. `named-card` means **the app knows exactly what this card
 * is and only lacks its picture**, so UX-DR22's named variant draws the real name, the real mana
 * pips and the real type line, all of which the client already holds from `GET /api/cards/{id}`.
 * Two tokens map to it because they differ on the wire (retryable or not) and not on the glass —
 * `EXPERIENCE.md` writes both rows and asks for the same placeholder in each.
 *
 * `Partial<Record<…>>` because most tokens have no such destination — the assert at the bottom
 * of this file is what stops that partiality from becoming a hole.
 */
export const PLACEHOLDER_FOR_REASON = {
  card_not_found: 'unknown-card',
  no_image_data: 'named-card',
  image_fetch_failed: 'named-card',
} satisfies Partial<Record<ErrorReason, PlaceholderKey>>

/**
 * Tokens that deliberately produce **no UI response at all** — the other meaning of `null`.
 *
 * Not "no panel": nothing, anywhere on the glass. `invalid_request` is a client bug or a stray
 * caller (the log is the audience); `payload_too_large` is answered to the *agent* through the
 * MCP tool's outcome vocabulary. Enumerated here rather than inferred from "is not in
 * `PLACEHOLDER_FOR_REASON`", because inferring it would make FORGETTING to classify a new token
 * look exactly like deciding it needs nothing — which is the failure this whole section exists
 * to prevent.
 */
export const NO_UI_RESPONSE = [
  'invalid_request',
  'forbidden',
  'payload_too_large',
] as const satisfies readonly ErrorReason[]

/**
 * Panels with no reason token at all, because their condition is CLIENT-SIDE.
 *
 * `disconnected` is produced by the WebSocket backoff reaching its two-gate announcement
 * threshold (`DISCONNECTED_AFTER_MS` elapsed AND `DISCONNECTED_MIN_FAILURES` observed). There
 * is no response to carry a token, which is the whole point of the state.
 *
 * `database-updating-stalled` is the corrupt-database case. The backend cannot tell 200ms of
 * mid-import from a month of garbage — which is *why* it treats the condition as transient — so
 * it answers `database_unavailable` either way. The distinguisher is ELAPSED TIME, which only
 * the client has; the polling layer owns the threshold and the switch.
 *
 * ================= WHY THIS LIST IS TYPE-LEVEL ONLY ======================================
 *
 * This constant has no runtime consumer, deliberately — the asserts below turn that into
 * something the compiler holds.
 *
 * A runtime consumer would have to be a MEMBERSHIP TEST — *"is this panel client-only?"* — and
 * nothing in the app has that question. The two members are produced by two entirely different
 * mechanisms in two different modules (a poll's elapsed clock; a socket's backoff), each of which
 * names its own panel directly because each knows exactly which one it is producing. Code that
 * asked the list instead would be deriving a panel from a category, which is one level of
 * indirection above anything that would make it more correct.
 *
 * What the list is genuinely FOR is the totality proof: `EveryPanelHasASource` reads it to show
 * that no panel exists without a source, and `PanelSourcesAreDisjoint` reads it to show that no
 * panel has two. Both are erased from the bundle, both fail `npm run typecheck` naming the
 * offender, and neither would be improved by a runtime array.
 *
 * The third reader is still type-level and no longer merely a proof: `src/state/deck.ts` and
 * `src/state/socket.ts` each hold the panel they select from a client-side condition, and both
 * type that constant as `ClientOnlyState` rather than `StateKey`. So the two places in the app
 * that choose a panel from something other than a wire token are compile-checked against this
 * list: retarget either at a wire-sourced panel and `tsc` names it.
 */
export const CLIENT_ONLY_STATES = [
  'disconnected',
  'database-updating-stalled',
] as const satisfies readonly StateKey[]

/**
 * A panel whose condition is client-side — the members of {@link CLIENT_ONLY_STATES} as a union.
 *
 * Exported so the two modules that select a panel from a client-side condition can type their
 * choice with it instead of with the whole of `StateKey`. See {@link CLIENT_ONLY_STATES}'s
 * disposition section: this alias is what makes that list a checked constraint on real code
 * rather than a list two type asserts happen to read.
 */
export type ClientOnlyState = (typeof CLIENT_ONLY_STATES)[number]

/**
 * Whether a state re-tries **on its own**, with no user action.
 *
 * This lives here, in a total map over `StateKey`, because it is a contract the polling layer
 * is held to, and that code is read before any design document. Total, so a new panel cannot
 * arrive without deciding — the way `internal_error` once arrived without a panel.
 *
 * `internal_error` is the load-bearing `false`: `types.d.ts:67-69` states it as a wire
 * contract — the companion hit a deterministic bug, so re-issuing the same request re-hits it,
 * and a quiet retry loop would hammer a broken backend while showing the user a calm panel
 * that never changes. Its next action is a MANUAL restart, which is why the copy says restart
 * and not wait.
 *
 * NOTHING HERE IMPLEMENTS RETRY, and nothing here should grow to: no fetch, no `setTimeout`,
 * no polling, and no hook is permitted in this directory at all. This is a declaration, not a
 * mechanism.
 */
export const RETRIES_QUIETLY = {
  // The agent sets the deck; nothing to poll for, and a `deck_changed` event delivers it.
  'no-active-deck': false,
  // "this page will come alive on its own when it's ready" — the copy promises this, so the
  // wiring owes it (FR-22's self-transition).
  'database-not-initialized': true,
  // "Reads will resume automatically" — same contract, same owner.
  'database-updating': true,
  // The ESCALATION of the row above: the quiet retry has already been running and has not
  // worked, so continuing to retry silently is the behaviour this state exists to replace.
  'database-updating-stalled': false,
  // The socket backoff is the retry, and the connection pill is where it is announced (UX-DR45).
  // **This entry is READ AT RUNTIME** — `src/state/socket.ts` indexes it to decide whether to
  // keep scheduling behind the panel, so flipping it to `false` really does stop the loop. That
  // is the difference between a declaration and a contract, and `socket.test.ts` flips it in a
  // try/finally to prove the behaviour follows. The pill's `down` copy is the announcement —
  // "Backend gone — retrying quietly" — which is TRUE only while this entry is `true`.
  // `copy-tails.test.ts` holds the two together.
  disconnected: true,
  'internal-error': false,
} satisfies Record<StateKey, boolean>

/**
 * Every panel has a source: a reason token, or a declared client-side condition.
 *
 * TYPE-LEVEL, WITH NO RUNTIME FOOTPRINT — the whole file is erased from the bundle. If a state
 * key is ever added to `copy.ts` (and therefore to `EXPERIENCE.md`) with neither a token
 * mapping nor an entry in `CLIENT_ONLY_STATES`, `Assert` receives `false`, fails its own
 * `extends true` constraint, and `npm run typecheck` names the orphan.
 */
type Assert<T extends true> = T

type MappedState = Extract<(typeof PANEL_FOR_REASON)[ErrorReason], string>
type SourcedState = MappedState | (typeof CLIENT_ONLY_STATES)[number]

export type EveryPanelHasASource = Assert<
  [Exclude<StateKey, SourcedState>] extends [never] ? true : false
>

/**
 * …and the two sources are DISJOINT. `EveryPanelHasASource` proves "at
 * least one source"; nothing proved "not both". A state listed in `CLIENT_ONLY_STATES` that
 * later gains a wire token — or a wire-mapped state added to the client-only list — would
 * make the two vocabularies silently self-contradictory while everything stayed green. This
 * assert makes that a `typecheck` failure naming the overlap.
 */
export type PanelSourcesAreDisjoint = Assert<
  [Extract<MappedState, (typeof CLIENT_ONLY_STATES)[number]>] extends [never] ? true : false
>

/**
 * …and every PANEL-LESS token is classified.
 *
 * The three asserts below are to `null` what `EveryPanelHasASource` is to `StateKey`. `null` in
 * `PANEL_FOR_REASON` carries two different meanings, and a bare `null` written beside the
 * existing ones records neither. So:
 *
 *   1. every token mapped to `null` appears in exactly one of the two classifications,
 *   2. no token appears in both,
 *   3. and nothing is classified that actually HAS a panel — which is the direction a copy-paste
 *      error takes, and which (1) alone would not catch.
 *
 * Together (1) and (3) are a set equality, so a new token added with `null` and no
 * classification fails `npm run typecheck` naming the token, exactly as an unmapped token fails
 * the `satisfies` clause above. Type-level only: this whole file is erased from the bundle.
 */
type PanellessReason = {
  [K in ErrorReason]: [(typeof PANEL_FOR_REASON)[K]] extends [null] ? K : never
}[ErrorReason]

type ClassifiedReason = (typeof NO_UI_RESPONSE)[number] | keyof typeof PLACEHOLDER_FOR_REASON

export type EveryPanellessReasonIsClassified = Assert<
  [Exclude<PanellessReason, ClassifiedReason>] extends [never] ? true : false
>

export type ReasonClassificationsAreDisjoint = Assert<
  [Extract<(typeof NO_UI_RESPONSE)[number], keyof typeof PLACEHOLDER_FOR_REASON>] extends [never]
    ? true
    : false
>

export type NothingWithAPanelIsClassified = Assert<
  [Exclude<ClassifiedReason, PanellessReason>] extends [never] ? true : false
>

/**
 * …and a classified token's destination is a real one — not an explicit `undefined`.
 *
 * `satisfies Partial<Record<ErrorReason, PlaceholderKey>>` permits `some_token: undefined`, which
 * puts the token in `keyof typeof PLACEHOLDER_FOR_REASON` and therefore satisfies all three
 * asserts above while the runtime destination is nothing at all — "classified as having a
 * placeholder that does not exist". `Partial` is still the right shape (most
 * tokens have no entry); this closes the difference between *absent* and *present but undefined*.
 */
export type EveryPlaceholderIsAReal = Assert<
  [
    Extract<(typeof PLACEHOLDER_FOR_REASON)[keyof typeof PLACEHOLDER_FOR_REASON], undefined>,
  ] extends [never]
    ? true
    : false
>
