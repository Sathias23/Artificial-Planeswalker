/**
 * The wire vocabulary mapped onto the panel vocabulary — and they are NOT the same set, in
 * either direction (story c2-9, AC 12).
 *
 * Measured against `ui/src/api/types.d.ts:56-69` and `src/api/schema.test.ts:41`:
 *
 *   `deck_not_found`            -> the No-active-deck panel  (many-to-one: the SPA clears to it)
 *   `database_not_initialized`  -> the Card-database-not-set-up panel
 *   `database_unavailable`      -> the Card-database-is-updating panel (quiet retry)
 *   `internal_error`            -> the fifth panel, deterministic and NEVER self-retrying
 *   `card_not_found`            -> NO PANEL, but a NAMED NON-PANEL DESTINATION (c3-2; see below)
 *   `no_image_data`             -> NO PANEL; the NAMED CARD placeholder in one tile (c3-5)
 *   `image_fetch_failed`        -> NO PANEL; the same placeholder, for a different reason (c3-5)
 *   `invalid_request`           -> NO UI RESPONSE AT ALL, by design
 *   `forbidden`                 -> NO UI RESPONSE AT ALL, by design (c3-4; agent-facing)
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
 * c3-2 added a third `null`, and it does NOT mean what the other two mean. `invalid_request`,
 * `forbidden` and `payload_too_large` are `null` because there is nothing to put on the glass at
 * all — for one the user cannot act, for the other two the audience is the *agent*.
 * `card_not_found` is `null` because its destination is **not a panel**: the view renders normally
 * and one slot becomes the unknown-card placeholder (`EXPERIENCE.md`'s "Unknown card in a view"
 * row, built by **c4-3**).
 *
 * c3-4's `forbidden` joined the first group with no new machinery, which is the mechanism working:
 * the `satisfies` clause forced the decision, `NO_UI_RESPONSE` recorded it, and the three asserts
 * at the bottom of this file proved it was recorded exactly once.
 *
 * Writing all three as a bare `null` beside each other would discard exactly the token/UI pairing
 * that C2 retro ruling R1 exists to force — "a token ships alone and a comment promises the
 * rest" is the `internal_error` mistake that cost c2-9 a repair AC. So the distinction is TYPED
 * AND GATED below (`PLACEHOLDER_FOR_REASON`, `NO_UI_RESPONSE` and the three asserts at the
 * bottom), not left to this paragraph: a future `null` that is classified as neither, or as
 * both, fails `npm run typecheck` naming the token.
 *
 * The copy itself is deliberately NOT here. "Unknown card" is prose, and prose may only live in a
 * copy module — `tests/copy-rules.test.ts`'s file half would fail this file for containing it.
 * This file carries the destination's NAME, which is chrome; `tests/unknown-card-copy.test.ts`
 * ties that name to the artefact's label.
 *
 * **Precisely where c4-3 is named, because the distinction is the whole point of R1**:
 * `copy-rules.test.ts:99` is a PROSE COMMENT above `COPY_MODULES` that lists "c4-3's 'Unknown
 * card'" among the entries later stories will add. It is *not* a `COPY_MODULES` entry — it cannot
 * be, since the module it would name does not exist yet, and that Map is git-checked. So the
 * c4-3 half of this pairing is a comment, not a gate, and saying otherwise (as an earlier draft
 * of this paragraph did) would be exactly the "a comment promises the rest" shape R1 exists to
 * stop. What IS gated today: the token, its classification here, and the artefact's label.
 *
 * ================= EXHAUSTIVENESS IS PROVED BY THE TYPE, NOT BY A TEST ==================
 *
 * `satisfies Record<ErrorReason, …>` is what made c3-2's seventh token (`card_not_found`) fail
 * `npm run typecheck` rather than silently losing a state — measured, and it did:
 * `error TS2345: … Property 'card_not_found' is missing`.
 *
 * **The mechanism held for the eighth, and c3-4 measured it the same way** (2026-08-01) by
 * deleting `forbidden` from the map and running both gates. `npx tsc -b --force` reported FIVE
 * errors — `TS1360` here naming the missing property, plus `TS2344: Type 'false' does not satisfy
 * the constraint 'true'` twice, from the classification asserts at the bottom of this file. In the
 * same state `vitest run` reported only ONE failure, and only because c3-4 added a runtime
 * assertion for the value. That ratio is the whole argument of the paragraph below: a runtime test
 * that enumerated today's tokens would prove nothing —
 * `src/api/schema.test.ts:4` says so in bold, with a measured example: `expectTypeOf` assertions
 * erase to an empty test body, so `vitest run` reports green over a wire type that has been
 * mutated out from under it. **`npm run typecheck` is the gate for this file.**
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
 *
 * The wiring that reads this map is **c3-9**'s; neither c2-9 (which wrote it) nor c3-2 (which
 * added the seventh token) ships a fetch, polling or retry, so nothing selects a state at
 * runtime yet.
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
  // is transient (the CDN did not deliver). c3-8 owns the negative cache and the backoff that act
  // on the difference — and it needs no wire change at all, because the vocabulary is here.
  image_fetch_failed: null,
  // NO UI RESPONSE AT ALL, BY DESIGN. The SPA never generates a malformed request, so this
  // token means a client bug or a stray caller on the port. There is nothing the user can do
  // about either, and a panel saying so would be the app blaming its own reader; the log is
  // where it is diagnosed (types.d.ts:63-65).
  invalid_request: null,
  // NO UI RESPONSE AT ALL, BY DESIGN. An agent-only endpoint was called without a valid
  // credential (c3-4's PUT /api/active-deck). The browser NEVER holds the agent token and never
  // calls a route that wants one (AD-5), so this token reaching the glass would mean reporting a
  // failure the reader did not cause and cannot fix. Its real audience is the agent, where AD-8's
  // "re-read the discovery file and retry exactly once" lives — which is the whole reason it is a
  // token of its own instead of another `invalid_request`.
  forbidden: null,
  // NO UI RESPONSE AT ALL, BY DESIGN. An agent push over the ingest cap (c5-5) is surfaced to
  // the AGENT, through the MCP tool's outcome vocabulary — the party that can actually send a
  // smaller one. The glass never sees it.
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
 * Tokens whose destination is a named UI element that is **not a panel** (story c3-2, retro R1).
 *
 * `card_not_found` is c3-2's. Its destination is `EXPERIENCE.md`'s "Unknown card in a view" row —
 * a placeholder label plus a truncated id, in the one slot that could not be hydrated, with the
 * rest of the view untouched. **c4-3 owns the render**; this entry is the machine-readable half of
 * the token/UI pairing that R1 requires to land in the same commit as the token, and
 * `tests/unknown-card-copy.test.ts` is what holds the label to the artefact.
 *
 * c3-5's two are `named-card`, and the distinction from `unknown-card` is a real one rather than a
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
 * `disconnected` is produced by the WebSocket backoff exhausting its retries (**c5-6**) — there
 * is no response to carry a token, which is the whole point of the state.
 *
 * `database-updating-stalled` is the c1-6 corrupt-database ruling (Q5, Brad 2026-07-29). The
 * backend cannot tell 200ms of mid-import from a month of garbage — that is *why* decide-once
 * #4 ruled the condition transient — so it answers `database_unavailable` either way. The
 * distinguisher is ELAPSED TIME, which only the client has. **c3-9 owns the threshold and the
 * switch**, because c3-9 owns the polling; this story ships the copy and the panel.
 */
export const CLIENT_ONLY_STATES = [
  'disconnected',
  'database-updating-stalled',
] as const satisfies readonly StateKey[]

/**
 * Whether a state re-tries **on its own**, with no user action (AC 16, AC 22).
 *
 * This lives here, in a total map over `StateKey`, rather than only in a story record, because
 * it is a contract **c3-9** is held to and c3-9 will read code before it reads a story file.
 * Total, so a seventh panel cannot arrive without deciding — the way `internal_error` arrived
 * in c1-4 without a panel and cost this story an AC to repair.
 *
 * `internal_error` is the load-bearing `false`: `types.d.ts:67-69` states it as a wire
 * contract — the companion hit a deterministic bug, so re-issuing the same request re-hits it,
 * and a quiet retry loop would hammer a broken backend while showing the user a calm panel
 * that never changes. Its next action is a MANUAL restart, which is why the copy says restart
 * and not wait.
 *
 * NOTHING IN THIS STORY IMPLEMENTS RETRY, and nothing here should grow to: there is no fetch
 * layer until c3-1, no `setTimeout`, no polling, and no hook is permitted in this directory at
 * all. This is a declaration, not a mechanism.
 */
export const RETRIES_QUIETLY = {
  // The agent sets the deck; nothing to poll for, and a `deck_changed` event delivers it.
  'no-active-deck': false,
  // "this page will come alive on its own when it's ready" — the copy promises this, so the
  // wiring owes it (FR-22's self-transition, c3-9).
  'database-not-initialized': true,
  // "Reads will resume automatically" — same contract, same owner.
  'database-updating': true,
  // The ESCALATION of the row above: the quiet retry has already been running and has not
  // worked, so continuing to retry silently is the behaviour this state exists to replace.
  'database-updating-stalled': false,
  // c5-6's backoff is the retry, and the connection pill is where it is announced (UX-DR45).
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
 * …and the two sources are DISJOINT (review 2026-07-29). `EveryPanelHasASource` proves "at
 * least one source"; nothing proved "not both". A state listed in `CLIENT_ONLY_STATES` that
 * later gains a wire token — or a wire-mapped state added to the client-only list — would
 * make the two vocabularies silently self-contradictory while everything stayed green. This
 * assert makes that a `typecheck` failure naming the overlap.
 */
export type PanelSourcesAreDisjoint = Assert<
  [Extract<MappedState, (typeof CLIENT_ONLY_STATES)[number]>] extends [never] ? true : false
>

/**
 * …and every PANEL-LESS token is classified — the c3-2 half (retro R1, Q3 ruling 2026-07-31).
 *
 * The three asserts below are to `null` what `EveryPanelHasASource` is to `StateKey`. `null` in
 * `PANEL_FOR_REASON` now carries two different meanings, and a bare `null` written beside the
 * existing ones records neither. So:
 *
 *   1. every token mapped to `null` appears in exactly one of the two classifications,
 *   2. no token appears in both,
 *   3. and nothing is classified that actually HAS a panel — which is the direction a copy-paste
 *      error takes, and which (1) alone would not catch.
 *
 * Together (1) and (3) are a set equality, so an eighth token added with `null` and no
 * classification fails `npm run typecheck` naming the token, exactly as the seventh token failed
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
 * placeholder that does not exist" (review, 2026-07-31). `Partial` is still the right shape (most
 * tokens have no entry); this closes the difference between *absent* and *present but undefined*.
 */
export type EveryPlaceholderIsAReal = Assert<
  [
    Extract<(typeof PLACEHOLDER_FOR_REASON)[keyof typeof PLACEHOLDER_FOR_REASON], undefined>,
  ] extends [never]
    ? true
    : false
>
