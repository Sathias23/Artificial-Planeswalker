/**
 * The push time, formatted for a nav pill (story c6-8, AC 2, Q4).
 *
 * A module of its own rather than a function beside the component, and the reason is mechanical:
 * `react-refresh/only-export-components` fails a `.tsx` that exports anything but components, and
 * the formatter has to be exported because its TESTS cannot assert bytes (see below). The repo
 * has the same shape three doors down — `frontFaceCost.ts`, `deckMemory.ts`, `imagedFaces.ts` are
 * all one-idea modules extracted from containers for the same class of reason.
 */

/**
 * Hoisted rather than constructed per call — an `Intl.DateTimeFormat` is expensive to build and
 * this one has no per-call configuration.
 *
 * `undefined` locale is the RUNTIME's locale, deliberately: the app is served from localhost to
 * one person, and a hard-coded `'en-GB'` would render a time in a format that is not theirs.
 * `hour: 'numeric'` with `minute: '2-digit'` is the pair that yields `14:32` in a 24-hour locale
 * and `2:32 PM` in a 12-hour one — the same information in the reader's own convention.
 */
const TIME_FORMAT = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' })

/**
 * The last push's time as the pill shows it, or `null` if it cannot be shown.
 *
 * **Absolute local hour and minute, static.** Q4 rejected relative time (*"2m ago"*) rather than
 * overlooking it: a self-updating clock is a timer, a cadence ruling and a new re-render source,
 * and UX-DR43 asks for an update *when a new push replaces it* — which a static render of `ts`
 * already gives, because a new push writes a new `ts`. The unread dot carries recency at a
 * glance; this carries when.
 *
 * ⚠️ **`null` on an unparseable `ts`, and that branch is REACHABLE.** `agentEventOf`
 * (`client.ts:701-716`) validates the `kind` discriminant and nothing else, so a frame whose `ts`
 * is `"not a date"` — or absent, arriving as `undefined` — reaches the store typed as a
 * timezone-aware ISO string. `Intl.DateTimeFormat.format` THROWS a `RangeError` on an Invalid
 * Date, and the nav renders inside the app shell rather than under any error boundary, so an
 * unguarded format call would take the whole header down over one malformed field. The pill stays
 * ACTIVE in that case — retention is what makes a pill active, and a view whose time is
 * unreadable is still a view worth re-opening — it simply renders no time. Same shape as
 * `SuggestionsView`'s per-field degradation: one bad field degrades itself and nothing else
 * (FR-13, AD-7).
 *
 * ⚠️ Tests must not assert BYTES of the return value: jsdom inherits the host's TZ and ICU build,
 * so a literal `'14:32'` expectation is a machine-dependent test. Callers' tests compute their
 * expectations through this function and assert the RELATIONSHIP — that the pill shows what this
 * returns, and that two different instants format differently.
 *
 * Args:
 *   ts: The retained envelope's `ts`, exactly as it arrived.
 *
 * Returns:
 *   The formatted time, or `null` when `ts` is not a date.
 */
export const pushTimeLabel = (ts: string): string | null => {
  const at = new Date(ts)
  return Number.isNaN(at.getTime()) ? null : TIME_FORMAT.format(at)
}
