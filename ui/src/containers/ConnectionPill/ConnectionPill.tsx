import { useState } from 'react'

import { useDeckStore } from '../../state/deck'
import type { ConnectionStatus } from '../../state/socket'
import { useConnection } from '../../state/systemState'
import './ConnectionPill.css'
import { CONNECTION_WORDS, DECK_SEPARATOR, pillText } from './copy'

/**
 * The connection pill — the gauge on c5-6's machine (story c5-7, FR-15, UX-DR29, UX-DR40,
 * UX-DR45, UX-DR46, UX-DR47, `DESIGN.md:479`, `EXPERIENCE.md:43`, `:97`, `:112-119`).
 *
 * A static 8px dot, the word for the state, and the active deck's name, bottom-left on **every**
 * surface. c5-6 built the machinery and wrote `SystemState.connection`; three shipped module
 * headers (`socket.ts:160`, `systemState.ts:49`, `connection.ts:24`) named this story as that
 * field's second reader. This is it.
 *
 * ================= IT READS THE DECK SLICE, NEVER `surfaceOf` (AC 6) ===================
 *
 * The single most likely way to get this component wrong, and it fails on exactly one surface —
 * the one it exists for. `surfaceOf`'s FIRST arm returns a PANEL surface whenever
 * `connection === 'down'` (`deck.ts:481-486`), while the deck slice underneath still holds the
 * loaded deck: nothing is cleared, which is what makes AC 9's *"comes back without a reload"* free.
 * So a pill that took its name from the surface would go quiet in the disconnected state, and
 * every other state would still look right.
 *
 * It reads {@link useDeckStore} with a selector instead — the path `deck.ts:527` sanctions by
 * name (*"a future component that needs the deck reads `useDeckStore` directly and lets the root
 * keep the boot"*), because `useDeckState()` also OWNS the boot and every mounted caller of it
 * creates a second one.
 *
 * ================= AND IT NAMES NO DECK IN THE `'down'` STATE (Q3) =====================
 *
 * A deliberate asymmetry, not an oversight. In `'down'` the Disconnected state panel has the left
 * column and owns the guidance; the pill owns the status. A deck name sitting beside the words
 * *"Backend gone"* reads as a claim about a deck the app can no longer answer for. The deck
 * CONTENT stays rendered where it is rendered at all (UX-DR35); what is withheld is the pill's
 * assertion about it.
 *
 * ================= NO TOOLTIP, NO `GET /health`, NO CLIENT COUNT ======================
 *
 * UX-DR29's port/instance-id tooltip clause is **c10-1's** by the FR coverage map (*"Pill shell +
 * reconnect in 5; status detail in 10"*, `epics:727`), and c10-1's own ACs quote it. This is a
 * real `<button>` so that `aria-describedby` can attach to it later without re-doing the element
 * or the Tab-order record — and it ships none of the reveal. It reads no endpoint at all: the
 * backend's `connected_count` is NOT an input here, whatever `state.py` and `agent_events.py` used
 * to predict (both rewritten in this commit, Q6).
 *
 * ================= THE DOT IS DECORATION, AND IT NEVER MOVES ==========================
 *
 * `aria-hidden`, because the text beside it already names the state — that is UX-DR29's *"the dot
 * never carries it alone"*, and it is why the dot can be decoration rather than a second
 * announcement. And it is STATIC under every setting: `tokens.css:305-312` bans a pulse repo-wide
 * and names **this component** as the reason that ban exists. Nothing here transitions, so there is
 * nothing to register in the reduced-motion inventory.
 */

/**
 * The modifier class each status wears. `Record<ConnectionStatus, …>` rather than a lookup with a
 * fallback: a fourth status added to the union arrives here as a `tsc` error instead of as a
 * silently colourless dot, which is the same totality argument `CONNECTION_WORDS` makes for the
 * words. The three classes resolve to `--positive` / `--caution` / `--negative` in the stylesheet.
 */
const DOT_CLASS: Record<ConnectionStatus, string> = {
  live: 'is-live',
  reconnecting: 'is-reconnecting',
  down: 'is-down',
}

export function ConnectionPill() {
  const connection = useConnection()

  // A SELECTOR, so the pill re-renders when the deck's NAME changes and not when its boards do.
  // `status === 'deck'` is the only arm that carries a detail; every other arm is `null`, which is
  // AC 6's *"no placeholder, no 'undefined'"* expressed as the absence of a branch rather than as
  // a string.
  const deckName = useDeckStore((state) =>
    state.deck.status === 'deck' ? state.deck.detail.name : null,
  )

  // `'down'` withholds the name — see the header. Computed once and used for the render, the
  // accessible name and the announcement alike, so the three can never disagree.
  const named = connection === 'down' ? null : deckName
  const text = pillText(connection, named)

  // THE ANNOUNCEMENT IS CAPTURED DURING RENDER, NOT IN AN EFFECT (AC 10, UX-DR45) — the pattern
  // `CardDetail.tsx:292-320` documents, for the reason it documents: `react-hooks/set-state-in-
  // effect` rejects the effect spelling, and a `setState` in an effect is a second render pass, so
  // the dot and the announcement would land in two different commits.
  //
  // KEYED ON THE STATUS ALONE, which is the whole of Q4's ruling in one dependency:
  //
  //   * The INITIAL render never announces. `seen: null` is a state no status can equal, so the
  //     first pass through this branch stores the status with an EMPTY text. That matters because
  //     the cold-open status is `'reconnecting'` (`systemState.ts:78`, and the socket loop's own
  //     `initialStatus` default) — a pill that announced on mount would tell every fresh page load
  //     that the app is reconnecting, before it has failed at anything.
  //   * A DECK-NAME change alone never announces. The name is read at capture time but is not part
  //     of the key, so renaming or switching the active deck leaves this region silent — the
  //     coalesced deck-refetch announcement already owns that channel (UX-DR45's flood rule).
  //   * Every genuine TRANSITION announces exactly once, with the pill's own current text.
  const [announced, setAnnounced] = useState<{
    readonly seen: ConnectionStatus | null
    readonly text: string
  }>({ seen: null, text: '' })

  if (announced.seen !== connection) {
    setAnnounced({ seen: connection, text: announced.seen === null ? '' : text })
  }

  return (
    <>
      {/* A REAL `<button>` (Q2, UX-DR47, and `keyboard-floor.test.ts:400-415` derives the rule
          rather than listing it). The epic requires the pill be focusable NOW and c10-1 requires
          this exact element LATER; shipping a `<div tabindex="0">` today would mean re-doing both
          the element and the Tab-order record in Phase 2.

          NO HANDLER, AND THAT IS THE HONEST SHAPE rather than a stub. Its only action — revealing
          the port and instance id — is c10-1's, so there is nothing for an `onClick` to do and a
          no-op handler would be a lie told to a reviewer rather than to a screen reader. It
          carries no `aria-expanded`, no `aria-pressed` and no `aria-haspopup`: every one of those
          would claim a behaviour that does not exist yet. What it does claim is what it is — a
          focusable control whose accessible name is its own text.

          NO `title` (UX-DR39 bans a hover-only disclosure) and no `aria-describedby` target: the
          attribute is c10-1's to add, and pointing it at nothing today would strip meaning from
          the accname computation for no gain. */}
      <button type="button" className="connection-pill">
        <span className={`connection-pill-dot ${DOT_CLASS[connection]}`} aria-hidden="true" />
        {/* One text wrapper, and the spacing between its parts comes from the LITERAL spaces
            around the separator rather than from a flex `gap` — so `button.textContent` is
            byte-identical to `pillText()`, which is what lets the announcement, the accessible
            name and the glass be asserted as one string. */}
        <span className="connection-pill-text">
          <span className="connection-pill-state">{CONNECTION_WORDS[connection]}</span>
          {named === null ? null : (
            <>
              <span className="connection-pill-separator">{` ${DECK_SEPARATOR} `}</span>
              {/* The deck NAME is data from the wire. It is rendered in a role that preserves its
                  case — see `ConnectionPill.css` for why it may not take the micro role, which
                  is c4-3's lesson and c4-10's repeat of it. */}
              <span className="connection-pill-deck">{deckName}</span>
            </>
          )}
        </span>
      </button>
      {/* THE APP'S SECOND POLITE LIVE REGION (AC 10, AC 11, UX-DR45 — which authorises three:
          this one, the agent-view heading and the pin announcement). OUTSIDE the button, exactly
          as `CardDetail`'s sits outside its panel: the control must not itself become a live
          region, or every focus and hover change would speak. Empty at rest. */}
      <p className="visually-hidden connection-pill-announcement" aria-live="polite">
        {announced.text}
      </p>
    </>
  )
}
