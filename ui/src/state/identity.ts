/**
 * Refresh the backend's confirmed identity, once per trigger (story 17.1, FR-15, AD-4).
 *
 * `connection.ts` fires this on every transition to `'live'` — the first connect and every
 * reconnect alike, because the socket emits on change only, so `'live'` arrives exactly once per
 * (re)connection. This module owns nothing else: it asks the one network door for the id and
 * hands a SUCCESS to the system slice's own verb. It holds no `setState` and names no store,
 * which is what keeps every `store-writes.test.ts` writer-scan answer unchanged — `identity.ts`
 * reports, `systemState.ts` applies, the exact division `poller.ts` and the socket loop both
 * follow.
 *
 * ================= LAST-CONFIRMED SEMANTICS, STATED ONCE ===============================
 *
 * A failed read — non-2xx, malformed 200, rejection, all folded to `null` by `readInstanceId` —
 * writes NOTHING. The field on the slice names the last backend this tab confirmed, and a
 * refresh that failed has confirmed nothing: blanking the stored id would replace a true
 * statement about the past with an absence, and the tooltip's cold-open copy ("not yet
 * confirmed") would then be a lie about a backend the tab has in fact confirmed.
 *
 * ================= THE GENERATION GUARD, AND WHAT IT IS FOR ============================
 *
 * Two refreshes can be in flight at once — a flapping socket goes `live → down → live` inside
 * one `READ_TIMEOUT_MS` — and `fetch` promises settle in whatever order the network pleases. A
 * monotonic issue counter, checked after the await, means the LATEST-ISSUED refresh is the only
 * one that may write: a slow answer from the old process cannot overwrite the id the new process
 * just confirmed. This is `deck.ts`'s and `formatCheck.ts`'s staleness idiom at its smallest —
 * a counter, not a `live` boolean, because "am I still the newest?" is a comparison, not a flag.
 */

import { readInstanceId } from '../api/client'
import { applyInstanceId } from './systemState'

/**
 * The newest refresh ever issued. Module-scoped and monotonic; never reset, because a stale
 * closure comparing against a RESET counter could read as current again — the exact bug a
 * generation guard exists to make unrepresentable.
 */
let generation = 0

/**
 * Read the backend's instance id and, if it answers, store it — latest-issued refresh wins.
 *
 * Args:
 *   read: The health read. Injected for tests (deferred promises are how the out-of-order case
 *     is driven); production callers pass nothing and get the one network door's reader.
 *
 * Returns:
 *   A promise that settles when the refresh has been applied or discarded. **Never rejects** —
 *   `readInstanceId` is total, and the trigger call site fires this `void`, so a rejection here
 *   would be an unhandled rejection in production.
 */
export const refreshInstanceId = async (
  read: () => Promise<string | null> = readInstanceId,
): Promise<void> => {
  generation += 1
  const issued = generation

  const instanceId = await read()

  // Failure first: a read that confirmed nothing writes nothing, whatever its generation.
  if (instanceId === null) return
  // Then staleness: an answer from a superseded refresh is evidence about the wrong moment —
  // a NEWER refresh has been issued, and its answer (or its failure) owns the field now.
  if (issued !== generation) return

  applyInstanceId(instanceId)
}
