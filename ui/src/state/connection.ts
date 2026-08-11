/**
 * Where the reconnect loop is mounted, and what its three signals actually do (story c5-6, Q5).
 *
 * `socket.ts` is framework-free and store-free by design — it knows about timers, tickets and
 * frames and about nothing else. This module is the other half: it owns no timing and decides no
 * schedule, it just says what each of the loop's three reports means to the rest of the app.
 * `systemState.ts` is the same split one layer over (`poller.ts` decides *when*, the hook decides
 * *what with*), and this file is written to be read beside it.
 *
 * ================= WHY IT IS A MODULE OF ITS OWN AND NOT PART OF `systemState.ts` =======
 *
 * Because the answer to a reconnect touches THREE slices — the system store's `connection`, the
 * deck boot, and the card cache's attempt counters — and no existing module may reach all three.
 * `systemState.ts` cannot import `deck.ts` (that module already imports it; a cycle), and
 * `deck.ts` may not name `useSystemStore` at all — `store-writes.test.ts:112-113` reports any
 * module holding both `setState` and a store's name as a writer of that store, and `deck.ts` owns
 * a `setState` of its own. So the composition lives above all three, importing each one's own
 * declared seam and reaching no store directly. This module contains no `setState` and names no
 * store, which is what keeps every existing writer-scan answer unchanged.
 *
 * ================= THE THREE SIGNALS, AND Q5's RULING FOR EACH ==========================
 *
 * 1. **status** → written straight through to the system slice. `surfaceOf` reads it for the
 *    Disconnected panel (Q3); the connection pill reads the same field, through the narrow
 *    `useConnection()` selector `systemState.ts` grew for it (**shipped at c5-7**).
 *
 * 2. **reconnected** — a socket opened after at least one failure — re-drives **everything the
 *    outage could have made stale**, because a socket coming back is the strongest evidence the
 *    app ever gets that it is looking at a different backend process than it was a moment ago:
 *
 *      - the **poll**, unconditionally (`poller.ts:293-306`: a restart is a fresh poll by design,
 *        and a stalled clock inherited from a process that no longer exists is not evidence);
 *      - the **deck boot**, which re-reads `GET /api/active-deck` and then the deck. If the
 *        backend restarted, the active-deck slot died with it (`ActiveDeckSlot` is in-memory,
 *        FR-07), so the answer is `{"deck_id": null}` and the app lands on the no-active-deck
 *        state — **no error, no stale deck**, and `deck.ts:339` short-circuits a null id with no
 *        second request (AC 6);
 *      - the **card attempt counters**, so ids the outage burned through their three attempts are
 *        askable again (Q6). Nothing here re-requests them: the boot's fresh `DeckDetail` is a new
 *        object, so `App.tsx`'s sweep effect fires on it and `hydrateDeckCards` re-asks the ids
 *        that are now re-armed. One trigger, one mechanism, no second sweep.
 *
 * 3b. **a `suggestions` push** (story c6-6) → the agent view opens, with no click anywhere in
 *    it (UX-DR34, the confirmed 2026-07-25 arrival ruling). This is the FOURTH signal and the
 *    first that is not about staleness at all: nothing is refetched, nothing is re-driven, and
 *    the frame's payload is READ rather than used as a trigger — which is the exact opposite of
 *    the deck path two paragraphs down, and the reason the two are described separately here.
 *    The call is a one-liner into `agentView.ts`'s exported verb, `redriveDeckBoot`'s shape
 *    exactly, so this module still holds no `setState` and still names no store.
 *
 * 3. **a system event** (`deck_changed` / `active_deck_changed`) → the deck boot **always**, and
 *    the poll **only if it had stopped** (`restartPollIfStopped`). The asymmetry is the ruling:
 *    the deck may have changed, so the boot always runs; but the poll is already working unless
 *    `RETRIES_QUIETLY` said its panel does not retry, and restarting a working poll would be a
 *    second polling mechanism racing the first.
 *
 * ================= WHAT A REFETCH IS, AND WHAT IT IS NOT (NFR-04, AC 10) ================
 *
 * *"Something changed, refetch."* No diffs, no patches, no payload reading on the deck path — the
 * `deck_changed` payload's `deck_id` is deliberately never read here, and neither is
 * `active_deck_changed`'s. Both mean *ask again*, and the app already has one correct way to ask:
 * `createDeckBoot`, which reads which deck is active FIRST. That is also the whole reason the two
 * kinds exist separately on the wire — `contracts.py:902-905` warns that a client conflating them
 * *"refetches the deck it is leaving instead of the one it is switching to"* — and re-driving the
 * boot rather than re-reading the current deck id is what makes that mistake unavailable here.
 */

import { useEffect } from 'react'

import { openSuggestionsPush } from './agentView'
import { redriveDeckBoot } from './deck'
import { resetCardAttempts } from './cards'
import { createAgentSocket } from './socket'
import { applyConnection, restartPoll, restartPollIfStopped } from './systemState'

/**
 * Open the agent socket and keep it reconnecting for as long as the caller is mounted.
 *
 * **`App` is the ONE consumer, and it is the same rule `useSystemState` and `useDeckState` both
 * state, with a sharper consequence here**: every mounted caller creates its OWN loop, and a
 * second loop is a second socket, a second ticket per attempt and a second copy of every frame
 * delivered to the same handlers. AC 1 says *exactly one socket per tab*, and this is where that
 * is true or not.
 *
 * In an effect rather than at module scope, for `systemState.ts`'s reason: a module-level
 * `createAgentSocket().start()` would connect during import — in every test file that touches this
 * module, and twice under React StrictMode with no cleanup between.
 *
 * Returns nothing. The state it produces is read from the system slice, by whoever needs it —
 * `App` already subscribes to that store, so there is no value to hand back and no second
 * subscription to pay for.
 */
export const useAgentConnection = (): void => {
  useEffect(() => {
    const socket = createAgentSocket({
      onStatus: applyConnection,
      onReconnected: () => {
        // The poll first, then the deck: the poll's answer is asynchronous either way, so the
        // order buys no correctness — but it puts the whole-screen question ahead of the
        // deck-shaped one, which is the order a human reads the screen in.
        restartPoll()
        resetCardAttempts()
        redriveDeckBoot()
      },
      onSystemEvent: () => {
        // The KIND is deliberately unread, and that is a ruling rather than laziness. The two
        // system kinds carry different MEANINGS — "the deck you are showing was edited" against
        // "which deck you are looking at changed" — and the reason the wire keeps them apart is
        // that a client acting on the payload must not refetch the deck it is leaving. This
        // client does not act on a payload at all: it re-drives the boot, which asks
        // `GET /api/active-deck` FIRST and therefore fetches whichever deck is active NOW. That
        // is the correct response to both, arrived at structurally rather than by a branch that
        // happens to agree. `socket.ts` still reports them separately, so the day one of them
        // needs a different action there is a parameter here to switch on.
        redriveDeckBoot()
        restartPollIfStopped()
      },
      // THE PUSH, AND THE WHOLE OF WHAT THIS SEAM DOES WITH IT (c6-6, AC 1). Passed straight
      // through: the verb is what builds content out of the envelope, and it is total about
      // every payload the wire admits, so there is no shape to check here and no branch on
      // whether a view is already open — opening over an open view REPLACES, which is the only
      // thing the scalar store can do. Deliberately NOT `(event) => openSuggestionsPush(event)`:
      // the reference IS the handler, exactly as `applyConnection` is above.
      onSuggestions: openSuggestionsPush,
    })
    socket.start()
    return () => socket.stop()
  }, [])
}
