/**
 * The active deck's format check: the one read that fetches it, and the one writer of its slice
 * (AD-12, AD-16, UX-DR21, FR-13).
 *
 * ================= WHY THIS IS A SIXTH STORE AND NOT A FIELD ON THE DECK ================
 *
 * Every other C4 panel derives from `boards`, already in the store. This one needs a request of
 * its own — `GET /api/deck/{deck_id}/format-check` — and there were four places it could have
 * lived. Three were rejected, each for a reason worth keeping:
 *
 *   1. **A third request inside `createDeckBoot`.** It would gate the whole deck view on one
 *      panel's data, turn a duplicated `get_deck_with_cards` into a FIRST-PAINT dependency, and
 *      put a network outcome inside the value whose reference identity IS the deck's identity —
 *      `deckMemory.ts` and `CardDetail`'s effect both read `boards` that way, so a report landing
 *      would look like a deck replacement.
 *   2. **A field on `DeckState`'s `'deck'` arm.** The same objection, plus it makes that union's
 *      exhaustiveness meaningless: `'deck'` would stop meaning "a deck loaded".
 *   3. **The container fetching directly.** Banned — `shell.test.ts:2071-2086` refuses `fetch`,
 *      `zustand` and `.setState` in any container module — and the ban is the entire point of
 *      `posture.test.ts`. `src/App.tsx` may not reach the wire either (`posture.test.ts:344-357`),
 *      so it drives this module and this module makes the request.
 *
 * A sixth store is the honest shape: a value with its own lifetime, its own single writer and its
 * own reset, sitting BESIDE the deck rather than inside it.
 *
 * ================= ONE READ PER SETTLED DETAIL ==========================================
 *
 * `App.tsx` drives {@link loadFormatCheck} from an effect keyed on the **`DeckDetail` object's
 * identity**, not on the deck id STRING: an id string cannot say "the decklist changed", so
 * keying on it would leave the panel stale forever after any agent edit. `deck.ts` settles a
 * fresh `detail` exactly once per completed boot AND once per coalesced `deck_changed` refetch,
 * which makes detail identity precisely the staleness signal this route needs. The pin is a
 * COUNT — one format-check request per settled detail, asserted in `App.test.tsx` — so a
 * render, a poll transition or a socket status change issue nothing, while a re-boot or a
 * refetch of the same deck honestly re-asks a route whose answer may have changed. (Side
 * effect, priced: reconnect and duplicate-`active_deck_changed` re-drives re-ask the ~5 ms
 * route once each.)
 *
 * **There is no refetch IN THIS MODULE, and no timer.** The refetch trigger is the deck
 * slice's, the debounce is the deck slice's supersede-and-restart coalescing (one settle per
 * burst, so one re-ask here), and this module is one read per call with a generation guard.
 * Half-building a trigger here would be a second coalescing rule.
 *
 * **And no retry.** `readFormatCheck` issues one request; nothing here asks again. The trap
 * (a backend with no database answers `database_not_initialized` to an id that can never succeed)
 * applies to every path-parameter route, and this one has a second reason: a refused read draws
 * NOTHING, so a retry would be spending requests to repair a screen nobody can see is broken.
 *
 * ================= A REFUSAL IS SILENT, DELIBERATELY ====================================
 *
 * `ui/README.md:1263-1286` records two precedents that point in opposite directions — *"a card
 * refusal never puts a panel on the glass"* (FR-13: one tile must not take down a view) and *"a
 * DECK refusal ALWAYS does, and that is the same rule rather than its opposite"* (the deck IS the
 * surface). A format-check refusal is **neither**: the deck is still on the glass, so the second
 * rule's premise fails; but this is a P0 panel rather than one tile among a hundred, so the first
 * rule's premise fails too. `surfaceOf` has no arm for it and nothing upstream rules it.
 *
 * **It follows the CARD precedent.** `'refused'` renders `null`, exactly as `ManaCurve` and
 * `ColourDistribution` render `null` for an empty derivation — the right column loses its third
 * panel and keeps its first two. Routing this through `panelFor` would replace a working deck view
 * with *"The companion hit a bug"* because one auxiliary read failed, which is FR-13 inverted.
 * `'loading'` renders nothing too — never a skeleton, and the panel materialising ~5 ms after the
 * deck is below the threshold anything would notice.
 *
 * ⚠️ **The declared cost, stated rather than discovered: the failure is INVISIBLE.** A user whose
 * format check never loads sees a right column with two panels and no way to tell that a third
 * was meant to be there. It is the honest price of not putting a bug panel over a working deck.
 *
 * ================= WHAT THIS MODULE DELIBERATELY DOES NOT DO ============================
 *
 * - **It does not decide a panel.** `panelFor` is not imported. See above.
 * - **It does not read the deck slice.** The id is an ARGUMENT, the way `hydrateCard` takes a
 *   card id — so this module has no opinion about which deck is current and cannot disagree with
 *   `surfaceOf` about it.
 * - **It does not touch `boards`, the card cache or the inspection slice.** This panel draws no
 *   card and starts no hydration.
 * - **It holds no timer, no retry and no backoff.**
 */

import { create } from 'zustand'

import { readFormatCheck, type FormatCheckOutcome } from '../api/client'
import type { FormatCheckReport } from '../api/schema'

/**
 * What the client knows about the active deck's format check. A discriminated union, in the
 * manner `DeckState` and `CardEntry` established, so no consumer infers a condition from
 * `undefined` and the compiler can exhaust it.
 *
 * Three of the four arms render nothing, and they are still four values rather than
 * `report | null`, because *"we have not asked"*, *"we are asking"* and *"the answer was a
 * refusal"* are three different facts. Only the last is a defect worth ledgering, and folding
 * them together is what would make it unobservable in a test.
 */
export type FormatCheckState =
  /** No deck, or a deck whose read has not started. The cold-open state and the no-deck state. */
  | { readonly status: 'idle' }
  /** A read is in flight. Renders NOTHING — never a skeleton. */
  | { readonly status: 'loading' }
  /** A report arrived. The ONE arm that draws. */
  | { readonly status: 'report'; readonly report: FormatCheckReport }
  /**
   * The read was refused, unreachable, or answered a `200` that is not the contract. All three
   * draw nothing, and they are one arm because nothing downstream distinguishes them: unlike the
   * deck slice, no token here chooses a panel, so carrying the reason would be a field with no
   * reader. `ui/README.md`'s blind-spot map records that as the deliberate absence it is.
   */
  | { readonly status: 'refused' }

/** The state before anything has been asked. Exported so tests can restore it between renders. */
export const INITIAL_FORMAT_CHECK_STATE: FormatCheckState = { status: 'idle' }

/**
 * The slice, holding the union **under a key** rather than as the store's own shape — for
 * `deck.ts`'s reason: zustand's `setState` MERGES by default, so a
 * store whose shape IS the union accepts `setState({ status: 'idle' })` and keeps the `report` of
 * the state before it. A merge of one key replaces that key's value wholesale, so no member's
 * fields can outlive it and no call site has a replace flag to forget.
 */
export interface FormatCheckSlice {
  readonly formatCheck: FormatCheckState
}

export const useFormatCheckStore = create<FormatCheckSlice>(() => ({
  formatCheck: INITIAL_FORMAT_CHECK_STATE,
}))

/** The ONE writer (AD-12). Every input to this slice goes through here. */
const applyFormatCheckState = (formatCheck: FormatCheckState): void =>
  useFormatCheckStore.setState({ formatCheck })

/**
 * How many loads have been started. The staleness discipline, and it is a COUNTER rather than a
 * `live` boolean for `createDeckBoot`'s reason verbatim (`deck.ts:283-296`): a boolean cannot tell
 * *"stopped"* from *"stopped and restarted"*, and a React StrictMode remount lands a clear and a
 * fresh load inside the one `await` this module has.
 *
 * The concrete failure it prevents: the agent switches decks while a read is in flight, and the
 * old deck's report lands on top of the new deck's — a panel confidently describing a deck that is
 * no longer on the glass. Bumped by {@link loadFormatCheck} and by {@link clearFormatCheck}, so a
 * cleared world cannot be resurrected either.
 */
let generation = 0

/**
 * Forget the format check, and abandon anything in flight.
 *
 * Called by `App.tsx` when there is no deck — a state panel, a cold open, a deck that went away.
 * **This is production behaviour, not a test hook** (unlike `resetDeckState`), and it is what
 * stops a report outliving its deck: without it, a deck deleted between two polls would leave its
 * legality verdict on the glass beside nothing.
 */
export const clearFormatCheck = (): void => {
  generation += 1
  applyFormatCheckState(INITIAL_FORMAT_CHECK_STATE)
}

/** Restore the initial state. **For tests** — production clears through {@link clearFormatCheck}. */
export const resetFormatCheckState = (): void => {
  clearFormatCheck()
}

/** What one settled outcome becomes. Total over the union — every outcome is a value. */
const stateFor = (outcome: FormatCheckOutcome): FormatCheckState =>
  outcome.kind === 'report' ? { status: 'report', report: outcome.report } : { status: 'refused' }

/**
 * Read one deck's format check, once, and write whatever came back.
 *
 * Args:
 *   deckId: The deck id, as the agent set it. Untrusted — encoded by `formatCheckPath`, and the
 *     EMPTY one is refused here with no request, because `formatCheckPath('')` is
 *     `/api/deck//format-check`, which addresses nothing. That is the same layering `hydrateCard`
 *     and `createDeckBoot` both use: a route-shape fact answered above the route.
 *   read: Injected so tests need no global `fetch` stub, exactly as `createPoller`'s `read?:` and
 *     `hydrateCard`'s are. **Production passes nothing.**
 *
 * Returns:
 *   Nothing. The store is the authority and every consumer is already watching it — a returned
 *   value would be a second copy of the truth, free to be read after it stopped being true.
 *   Never rejects: `readFormatCheck` is total, and an injected reader that throws is read as a
 *   refusal.
 */
export const loadFormatCheck = async (
  deckId: string,
  read: (id: string) => Promise<FormatCheckOutcome> = readFormatCheck,
): Promise<void> => {
  generation += 1
  const startedIn = generation

  if (deckId.trim() === '') {
    // No request, and `'refused'` rather than `'idle'`: the panel draws nothing either way, but
    // "we asked about an id that cannot be addressed" is a settled answer and `'idle'` would say
    // the read never happened. `trim()` and not `=== ''` — `deckPath('  ')` is
    // `/api/deck/%20%20/format-check`, a request guaranteed to 404 — a second-lock weakness.
    applyFormatCheckState({ status: 'refused' })
    return
  }

  applyFormatCheckState({ status: 'loading' })

  let outcome: FormatCheckOutcome
  try {
    outcome = await read(deckId)
  } catch {
    // `readFormatCheck` is total and cannot reject; an injected reader might. Swallowing it here
    // keeps the "never rejects" contract true for every caller.
    outcome = { kind: 'unreachable' }
  }

  // The one place staleness is stopped. A load superseded by another load, or by a clear, writes
  // nothing at all — see `generation`.
  if (startedIn !== generation) return
  applyFormatCheckState(stateFor(outcome))
}

/**
 * Subscribe to the format-check state. **Starts nothing** — `useCardEntry`'s posture exactly.
 *
 * A pure selector returning the STORED reference, which is what makes it safe under zustand v5:
 * that version dropped the equality argument on `create`, so a selector building a new object or
 * array each call re-renders forever.
 *
 * Returns:
 *   The current state. Re-renders the caller whenever {@link loadFormatCheck} changes it.
 */
export const useFormatCheck = (): FormatCheckState =>
  useFormatCheckStore((slice) => slice.formatCheck)
