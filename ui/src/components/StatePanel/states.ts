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
 *   `invalid_request`           -> NO PANEL, by design
 *   `payload_too_large`         -> NO PANEL, by design
 *   (no token at all)           -> Disconnected, and Database-updating-stalled
 *
 * So `Record<ErrorReason, StateKey>` is the wrong shape twice over: two tokens must be allowed
 * to map to *no* panel, and two panels have no token. `Record<ErrorReason, StateKey | null>` is
 * the shape that is total without being one-to-one, and `null` is a NAMED answer here rather
 * than an absence — see the two comments below, which are the whole reason those tokens exist.
 *
 * ================= EXHAUSTIVENESS IS PROVED BY THE TYPE, NOT BY A TEST ==================
 *
 * `satisfies Record<ErrorReason, …>` is what makes c3-2's seventh token (`card_not_found`)
 * fail `npm run typecheck` rather than silently losing a state. A runtime test that enumerated
 * today's six would prove nothing — `src/api/schema.test.ts:4` says so in bold, with a measured
 * example: `expectTypeOf` assertions erase to an empty test body, so `vitest run` reports green
 * over a wire type that has been mutated out from under it. **`npm run typecheck` is the gate
 * for this file.**
 *
 * `satisfies` rather than a type annotation, deliberately: an annotation would widen the values
 * to `StateKey | null` and throw away the literal types, which is exactly what the completeness
 * proof at the bottom of this file reads.
 */

import type { ErrorReason } from '../../api/schema'
import type { StateKey } from './copy'

/**
 * Which panel a reason token puts on the glass. `null` means **no panel, by design** — not
 * "not decided yet".
 *
 * The wiring that reads this map is **c3-9**'s; this story ships no fetch, no polling and no
 * retry, so nothing selects a state at runtime yet.
 */
export const PANEL_FOR_REASON = {
  // Many-to-one. A deck deleted between a push and a refetch (FR-11) is not an error state of
  // its own — the honest thing on screen is "there is no active deck", which is the panel that
  // already exists and already lists the decks that remain.
  deck_not_found: 'no-active-deck',
  database_not_initialized: 'database-not-initialized',
  database_unavailable: 'database-updating',
  // NO PANEL, BY DESIGN. The SPA never generates a malformed request, so this token means a
  // client bug or a stray caller on the port. There is nothing the user can do about either,
  // and a panel saying so would be the app blaming its own reader; the log is where it is
  // diagnosed (types.d.ts:63-65).
  invalid_request: null,
  // NO PANEL, BY DESIGN. An agent push over the ingest cap (c5-5) is surfaced to the AGENT,
  // through the MCP tool's outcome vocabulary — the party that can actually send a smaller
  // one. The glass never sees it.
  payload_too_large: null,
  internal_error: 'internal-error',
} satisfies Record<ErrorReason, StateKey | null>

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
