/**
 * The first `fetch` this repository has ever shipped, and the whole of its wire half (story c3-9).
 *
 * ================= WHERE THIS SITS, AND WHAT c4-1 / c4-2 INHERIT (Q1) ===================
 *
 * Measured at `16976c5`: `ui/src` contained **zero** `fetch(` call sites, zero hooks and zero
 * timers. `ui/README.md`'s *"Not here yet"* assigned the runtime fetch layer to **c4-1** and the
 * deck bootstrap to **c4-2** — and this story's epic AC requires it to transition *"to the
 * no-active-deck state, listing available decks"*, which is `GET /api/decks`. That paragraph is
 * corrected in the same commit as this file (a declared blind spot is still a claim).
 *
 * The ruling: **this module is the seam c4-1 EXTENDS, not a throwaway c4-1 replaces.** One
 * request helper here, one zustand slice in `src/state/`. AD-12 already rules that zustand is the
 * one store and bans a second state mechanism, so a self-contained hook with private state would
 * have been deleted by c4-1 while leaving a second spelling of "fetch JSON" behind it in the
 * meantime. What each story inherits, stated where they will read it:
 *
 *   **c4-1** adds the card cache, the in-flight deduping and every other route to a fetch layer
 *   and a store that already exist. This module's shape — a total outcome union, never a thrown
 *   rejection — is the shape to extend; the deduping goes *around* it.
 *
 *   **c4-2** adds the real deck bootstrap. It inherits a poll that already calls this endpoint,
 *   and its job is to read the DECK rather than the deck NAMES: this story renders the
 *   `no-active-deck` panel for every `200`, because until c4-2 there is no deck view to show.
 *
 * ================= WHY THIS REQUEST IS SAFE TO RETRY, AND c4-1's ARE NOT ================
 *
 * Measured at c3-2 and pinned in `test_routes_cards.py`: a malformed id sent to a backend with no
 * database answers **`database_not_initialized`, not `invalid_request`**, because FastAPI's
 * `solve_dependencies` runs dependencies before it collects parameter-validation errors, so
 * `get_session`'s `CompanionError` propagates first. A client that treats both database tokens as
 * "retry quietly" therefore retries a request whose id can never succeed, forever.
 *
 * **This poll is immune, and the reason is structural rather than careful: `/api/decks` has no
 * path parameter.** There is no id to be malformed, so no `503` it sees can be masking a `400`.
 * **c4-1's per-card fetches are not immune** — `GET /api/cards/{card_id}` and
 * `GET /api/card-image/{scryfall_id}` both take one — and a retry loop built by copying this one
 * needs a bound on attempts per id, or a `400` that arrives late as a `503` becomes an infinite
 * loop. Written here because this is the file c4-1 will open first.
 *
 * ================= A TOTAL UNION, NEVER A REJECTION ====================================
 *
 * `readDecks` does not throw and does not return `null`. Four failure inputs — a `503` with no
 * body, a body that is not JSON, a body with no `reason`, and a network rejection — are four
 * distinct things and every one of them is a value in the union below. The panel decision is
 * NOT made here (see `src/state/panel.ts`): this module reports what came back, including a
 * `reason` string it has deliberately **not** validated, and the one place a wire value becomes a
 * `StateKey` is the boundary that owns `PANEL_FOR_REASON`.
 */

import type { DeckSummary, ErrorResponse } from './schema'

/**
 * The one route this story polls. Read by `tests/copy-tails.test.ts`, which holds
 * `EXPERIENCE.md`'s un-quoted no-active-deck clause (*"the available-deck list from
 * `GET /api/decks`"*) to the endpoint this file actually calls — so the artefact and the code
 * cannot drift apart silently in either direction.
 */
export const DECKS_PATH = '/api/decks'

/**
 * How long one request may take before it is abandoned as `unreachable`.
 *
 * 10 s: the backend's SQLite connection waits up to **5 s** on a locked database
 * (`database.py` sets `timeout=5`), so every answer a healthy backend will ever give arrives
 * inside that; twice it means no true answer is ever cut off. What the clock is FOR is the one
 * failure `fetch` alone has no bound on — a process that accepts the connection and never
 * writes a response. Without it, `await read()` never settles, the poller schedules nothing,
 * and the calm initial panel stands forever with the whole "comes alive on its own" loop
 * silently dead. With it, a wedge becomes `{kind: 'unreachable'}` and rides the ordinary
 * backoff like any other lost backend.
 */
export const READ_TIMEOUT_MS = 10_000

/**
 * What one poll of `GET /api/decks` came back with. Three cases, and they are genuinely three:
 *
 * - `decks` — a `200` whose body was the array the contract promises. The deck NAMES, which is
 *   all the `no-active-deck` panel renders.
 * - `error` — a response arrived and the request was refused. `reason` is the body's token
 *   **exactly as it crossed the wire and unvalidated**, or `null` when the body could not yield
 *   one at all (absent, unparseable, no `reason` key, or a `reason` that is not a string).
 * - `unreachable` — no response at all: `fetch` itself rejected. NOT the same as `error` with a
 *   `null` reason, and the difference is load-bearing — see the poller, which retries this one
 *   without claiming a state, because the panel that describes a lost backend
 *   (`disconnected`) is **c5-6's** by `CLIENT_ONLY_STATES` and this story may not claim it.
 */
export type DecksOutcome =
  | { readonly kind: 'decks'; readonly decks: readonly string[] }
  | { readonly kind: 'error'; readonly reason: string | null }
  | { readonly kind: 'unreachable' }

/** The `reason` a body carries, or `null` if it carries none this code can read. */
const reasonOf = (body: unknown): string | null => {
  if (typeof body !== 'object' || body === null) return null
  // `in` rather than a cast to `ErrorResponse`: the value on the wire is untyped JSON, and the
  // whole point of this function is that it may be anything at all.
  if (!('reason' in body)) return null
  const reason: unknown = (body as Partial<ErrorResponse>).reason
  return typeof reason === 'string' ? reason : null
}

/**
 * The deck names out of a `200` body, or `null` if the body was not the promised array.
 *
 * A `200` that is not an array is a **contract violation**, not an empty deck list, and it is
 * reported as one (the caller turns it into `internal-error`) — answering "no decks" would put a
 * calm, wrong panel on the glass. Within a well-formed array the posture flips: an entry that is
 * not an object with a non-blank string `name` is DROPPED rather than failing the whole read,
 * which is FR-13's *"one unresolvable row must never take down a view"* read across to this list.
 * `StatePanel` already drops blank names for the same reason; doing it here too costs nothing and
 * means the panel is never handed one.
 */
const namesOf = (body: unknown): readonly string[] | null => {
  if (!Array.isArray(body)) return null
  const rows: readonly unknown[] = body
  return rows
    .map((row) =>
      typeof row === 'object' && row !== null && 'name' in row
        ? (row as Partial<DeckSummary>).name
        : undefined,
    )
    .filter((name): name is string => typeof name === 'string' && name.trim() !== '')
}

/**
 * Poll `GET /api/decks` once, and report what happened without ever throwing.
 *
 * `cache: 'no-store'` because the whole point of the poll is to observe the backend CHANGE state
 * under it: `deps.get_session` re-probes readiness on every request and never caches (FR-22), and
 * a client-side cache would be the one place that promise could still be broken. The companion's
 * error responses already carry `Cache-Control: no-store`, but a `200` does not, and the `200` is
 * the response this story most needs to be fresh.
 *
 * Returns:
 *   A `DecksOutcome`. Never rejects — a rejection is `{ kind: 'unreachable' }`.
 */
export const readDecks = async (): Promise<DecksOutcome> => {
  // The clock, where the runtime can build one. `AbortSignal.timeout` is inside the bundle's
  // own browser floor (no `build.target` in vite.config.ts, so Vite's default
  // `baseline-widely-available` — Chrome/Edge 107+, Firefox 104+, Safari 16+ — every one of
  // which postdates the API: Chrome 103, Firefox 100, Safari 15.4), so the `undefined` arm is
  // unreachable in a browser this bundle targets. The guard exists because the failure without
  // it is the worst this module can produce: the constructor throwing INSIDE the `try` below
  // would classify every poll as `unreachable` before `fetch` ever ran — a calm panel retrying
  // forever against a healthy backend it never contacts. An out-of-floor browser degrades to
  // NO timeout instead (the wedge risk returns, on a browser the bundle does not target); it
  // never masquerades as a lost backend.
  const signal =
    typeof AbortSignal.timeout === 'function' ? AbortSignal.timeout(READ_TIMEOUT_MS) : undefined

  let response: Response
  try {
    response = await fetch(DECKS_PATH, {
      cache: 'no-store',
      headers: { Accept: 'application/json' },
      // A timeout abort is a rejection, so it lands in the same `unreachable` as a lost
      // backend — which is what it is. See `READ_TIMEOUT_MS` for the arithmetic.
      signal,
    })
  } catch {
    return { kind: 'unreachable' }
  }

  // `.json()` rejects on an empty body and on anything that is not JSON — the two of the four
  // malformed inputs that arrive one layer earlier than a missing `reason` key.
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }

  if (!response.ok) return { kind: 'error', reason: reasonOf(body) }

  const decks = namesOf(body)
  // A `200` whose body is not the promised array: see `namesOf`. `null` is the reason a
  // contract violation has — there is no token for "the backend answered something else".
  return decks === null ? { kind: 'error', reason: null } : { kind: 'decks', decks }
}
