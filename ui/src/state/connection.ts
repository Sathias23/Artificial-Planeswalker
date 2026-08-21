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
 *    `useConnection()` selector `systemState.ts` grew for it (**shipped at c5-7**). Since 17.1
 *    a transition to `'live'` also fires `identity.ts`'s instance-id refresh — see the wrapper
 *    at the call site for why `'live'` is the trigger and not `reconnected`.
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
 * 3. **a system event** (`deck_changed` / `active_deck_changed`) → the deck store's own verb for
 *    that kind — **the two kinds finally act differently here (c7-3)**, in the branch c6-3's
 *    ruling #2 reserved for exactly this story — and the poll **only if it had stopped**
 *    (`restartPollIfStopped`), for BOTH kinds and both `deck_changed` branches alike. The poll
 *    asymmetry is unchanged and still the ruling: the deck may have changed, so the deck path
 *    always runs; but the poll is already working unless `RETRIES_QUIETLY` said its panel does
 *    not retry, and restarting a working poll would be a second polling mechanism racing the
 *    first.
 *
 * ================= WHAT A REFETCH IS, AND WHAT IT IS NOT (NFR-04, AC 10) ================
 *
 * *"Something changed, refetch."* No diffs, no patches — that half of the doctrine stands
 * untouched. The OTHER half of what this header used to say — *"the `deck_changed` payload's
 * `deck_id` is deliberately never read here"* — is OVERTURNED by c7-3, deliberately and by
 * ledger (c6-3 ruling #2 reserved the branch; `deferred-work.md` named this story): the id is
 * now read, TOTALLY (missing payload, missing key, `null` and a blank string all fold to `null`,
 * "refetch whatever is active"), and handed to `deck.ts`'s `refetchOnDeckChanged`, which
 * refetches only `GET /api/deck/{id}` when the event matches the SETTLED deck — one request per
 * edit instead of two, coalesced latest-wins in the store's own machinery.
 *
 * What did NOT move is the part `contracts.py:902-905` warns about: `active_deck_changed`'s
 * payload is still never read, because *which deck am I looking at* has exactly one correct
 * answer and it is the server's — the full boot asks `GET /api/active-deck` FIRST, so the client
 * structurally cannot refetch the deck it is leaving. And `deck.ts` re-asserts the same humility
 * on the edited-deck path: any window where the settled deck id is not current truth (mid-boot,
 * `'none'`, `'refused'`) falls back to that same full re-drive rather than adjudicating ids
 * client-side. This module still decides nothing about ids — it folds one field and picks a
 * verb; every comparison lives in the deck slice beside the state it compares against.
 */

import { useEffect } from 'react'

import { openGroupsPush, openSuggestionsPush, openSwapsPush, openTierListPush } from './agentView'
import { redriveDeckBoot, refetchOnDeckChanged } from './deck'
import { resetCardAttempts } from './cards'
import { refreshInstanceId } from './identity'
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
      // No longer the bare `applyConnection` reference (story 17.1): the status still writes
      // straight through, and a transition to `'live'` ALSO refreshes the backend's confirmed
      // identity. `'live'` rather than `onReconnected`, deliberately — the first connect needs
      // the id too, and the socket's emit-on-change makes `'live'` fire exactly once per
      // (re)connection, so this one trigger point covers AC-4's reconnect visibility with no
      // second wiring. `void`, because the refresh is total and nothing here awaits it: the
      // tooltip reads the store whenever the answer lands.
      onStatus: (status) => {
        applyConnection(status)
        if (status === 'live') void refreshInstanceId()
      },
      onReconnected: () => {
        // The poll first, then the deck: the poll's answer is asynchronous either way, so the
        // order buys no correctness — but it puts the whole-screen question ahead of the
        // deck-shaped one, which is the order a human reads the screen in.
        restartPoll()
        resetCardAttempts()
        redriveDeckBoot()
      },
      onSystemEvent: (event) => {
        // THE BRANCH c6-3's RULING #2 RESERVED, taken at c7-3. The two system kinds carry
        // different MEANINGS — "the deck you are showing was edited" against "which deck you
        // are looking at changed" — and they now get different verbs:
        //
        //   - `active_deck_changed` re-drives the boot, payload unread, exactly as before: the
        //     boot asks `GET /api/active-deck` FIRST, so the client structurally cannot refetch
        //     the deck it is leaving (`contracts.py:902-905`).
        //   - `deck_changed` hands its `deck_id` — READ TOTALLY, the one payload read this
        //     module makes: `agentEventOf` validates only `kind`, so a payload-less frame, a
        //     missing key, `null`, a non-string and a blank all arrive here, and every one of
        //     them folds to `null`, "refetch whatever is active" — to the deck slice's own
        //     verb, which refetches the single deck when the event matches the settled one and
        //     falls back to the full re-drive in every window where the settled id is not
        //     current truth. The COMPARISON lives there, beside the state it reads; this module
        //     still holds no `setState`, names no store and decides nothing about ids.
        //
        // The poll restart stays OUTSIDE the branch: the deck list may refresh regardless of
        // which deck changed, including on a different-deck event whose deck path does nothing.
        if (event.kind === 'deck_changed') {
          // TRIMMED, not merely blank-checked (review finding): the id is compared verbatim
          // against the settled `detail.id` in `deck.ts`, so a PADDED copy of the right id
          // passed through raw would fail the match and read as a different deck — a silently
          // missed refresh with no recovery signal. The same trim-both-locks reasoning as
          // `createDeckBoot`'s blank-id gate: a fold weaker than the comparison it feeds is
          // the exact second-lock weakness that review closed there.
          const raw: unknown = event.payload?.deck_id
          const deckId = typeof raw === 'string' ? raw.trim() : ''
          refetchOnDeckChanged(deckId === '' ? null : deckId)
        } else {
          redriveDeckBoot()
        }
        restartPollIfStopped()
      },
      // THE PUSH, AND THE WHOLE OF WHAT THIS SEAM DOES WITH IT (c6-6, AC 1). Passed straight
      // through: the verb is what builds content out of the envelope, and it is total about
      // every payload the wire admits, so there is no shape to check here and no branch on
      // whether a view is already open — opening over an open view REPLACES, which is the only
      // thing the scalar store can do. Deliberately NOT `(event) => openSuggestionsPush(event)`:
      // the reference IS the handler, exactly as `applyConnection` is above.
      onSuggestions: openSuggestionsPush,
      // THE SECOND PUSH KIND (story 16.1), in the sibling's exact shape and for its exact
      // reasons: the verb is total about every payload the wire admits, so there is nothing to
      // check here — and the reference IS the handler.
      onSwaps: openSwapsPush,
      // THE THIRD PUSH KIND (story 16.2), same shape, same reasons.
      onTierList: openTierListPush,
      // THE FOURTH AND LAST PUSH KIND (story 16.3), same shape, same reasons — with it every
      // kind the wire admits has a handler, and the socket's dispatch holds no drop arm.
      onGroups: openGroupsPush,
    })
    socket.start()
    return () => socket.stop()
  }, [])
}
