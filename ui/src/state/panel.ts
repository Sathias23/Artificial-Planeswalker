/**
 * The one place a wire value becomes a `StateKey` (story c3-9, AC 2, AC 8; Q5).
 *
 * ================= WHY THIS IS A BOUNDARY AND NOT A `switch` ============================
 *
 * `PANEL_FOR_REASON` has existed since **c2-9** and has never had a runtime consumer — the whole
 * of `states.ts` is tree-shaken out of the bundle today. It is a total map over `ErrorReason`,
 * proved total by `satisfies` at typecheck time rather than by a test, and three of its docstrings
 * say *"the wiring that reads this map is c3-9's"*. This file is that wiring. A `switch` here
 * would be a second copy of a decision already made, and the compiler would not notice when the
 * eleventh token arrived.
 *
 * ================= WHY IT IS TOTAL, AND WHAT THAT PREVENTS ==============================
 *
 * `STATE_COPY[state]` at `StatePanel.tsx:104` has **no fallback branch**: an unrecognised key
 * yields `undefined` and `copy.headline` throws — an unhandled render exception, which is
 * precisely the error screen this story exists to ban. TypeScript guarded that until now because
 * `App.tsx` passed a literal; the moment a value arrives from the wire, the type system is
 * looking at `string` and the guarantee is gone.
 *
 * So the totality is proved HERE, at the one place values enter, and `StatePanel` gains **no**
 * fallback branch — it stays presentation-only. Three inputs reach `'internal-error'`:
 *
 *   1. **A token this build does not know.** A backend/frontend version skew is a bug, and
 *      `internal-error`'s copy is true for it (*"The companion hit a bug… Restart the
 *      companion"*). `RETRIES_QUIETLY` already forbids retrying it, so a skewed build is not
 *      hammered behind a calm panel.
 *   2. **A token that maps to `null`.** Six do, and every one of them is classified in
 *      `states.ts` as either a named non-panel destination (**c4-3's**) or no UI response at all.
 *      Neither classification has anywhere to go on a whole-screen poll: `invalid_request` and
 *      `payload_too_large` are both declared on `GET /api/decks`, and either one arriving means
 *      the SPA sent a request it should never have sent. That is a client bug, which is what
 *      `internal-error` means.
 *   3. **No token at all** (`null`) — a body that was absent, unparseable, or carried no
 *      `reason`. The backend is not speaking the contract; same verdict, same reason.
 *
 * `Object.hasOwn` rather than a truthiness check on the index, deliberately: indexing a plain
 * object with `'__proto__'` or `'constructor'` returns an inherited value that is not `undefined`
 * and would sail through `?? 'internal-error'` into `StatePanel`'s `state` prop as an object.
 * A wire string is attacker-adjacent input by construction — the companion is one `fetch` away
 * from any page in the browser — and `hasOwn` costs nothing.
 */

import { PANEL_FOR_REASON } from '../components/StatePanel/states'
import type { StateKey } from '../components/StatePanel/copy'
import type { ErrorReason } from '../api/schema'

/**
 * Whether the wire handed us a token this build knows.
 *
 * The membership test is `PANEL_FOR_REASON`'s own key set, not a second list: `satisfies
 * Record<ErrorReason, …>` makes those keys exactly `ErrorReason` at compile time, so an eleventh
 * token cannot be added to the union without appearing here — which is what stops this predicate
 * from becoming the enumerated list that `states.ts`' header spends four paragraphs arguing
 * against.
 */
const isKnownReason = (reason: string): reason is ErrorReason =>
  Object.hasOwn(PANEL_FOR_REASON, reason)

/**
 * The panel a refused response puts on the glass — total over every string, and over `null`.
 *
 * Args:
 *   reason: The body's `reason` exactly as it crossed the wire, or `null` if it carried none.
 *
 * Returns:
 *   The `StateKey` to render. Never `undefined`; see the header for the three routes to
 *   `'internal-error'`.
 */
export const panelFor = (reason: string | null): StateKey =>
  (reason !== null && isKnownReason(reason) ? PANEL_FOR_REASON[reason] : null) ?? 'internal-error'
