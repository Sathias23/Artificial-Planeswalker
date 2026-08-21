import { useEffect, useId, useState } from 'react'

import { useDeckStore } from '../../state/deck'
import type { ConnectionStatus } from '../../state/socket'
import { useConnection, useInstanceId } from '../../state/systemState'
import './ConnectionPill.css'
import { CONNECTION_WORDS, DECK_SEPARATOR, pillText, tooltipText } from './copy'
import { pagePort } from './port'

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
 * ================= THE TOOLTIP (story 17.1) — AND STILL NO CLIENT COUNT ================
 *
 * UX-DR29's port/instance-id tooltip clause was reserved for this story by the FR coverage map
 * (*"Pill shell + reconnect in 5; status detail in 10"*, `epics:727`), and c5-7's real `<button>`
 * was shipped so `aria-describedby` could attach without re-doing the element or the Tab-order
 * record. This is that attachment. The tooltip element sits OUTSIDE the button — inside it, its
 * text would join the button's CONTENTS and therefore its accessible NAME, breaking the pinned
 * accname `Connected—Sultai Midrange` (the `AgentViewsNav` hint's argument exactly) — and it is
 * the button's IMMEDIATE next sibling, because the stylesheet's `+` combinator is what reveals
 * it on `:hover`/`:focus-visible`. The nav pill's `title`+hidden-description shape is NOT enough
 * here: the AC requires a VISUAL reveal on keyboard focus, so the description element itself is
 * the visible tooltip, and there is no `title` at all (UX-DR39's hover-only ban).
 *
 * The PORT is `window.location`'s, never a configured number — {@link agentSocketUrl}'s argument
 * one seam over: any number written into this bundle would be wrong for the ephemeral-port case
 * it was written for, and the page's own authority IS the backend's authority (AD-13). The
 * INSTANCE ID is the system slice's last-confirmed value, refreshed through `identity.ts` on
 * every transition to `'live'` — this component still reads no endpoint. The backend's
 * `connected_count` is still NOT an input here, and stays out of the tooltip by ruling.
 *
 * ESCAPE SUPPRESSES THE REVEAL (WCAG 1.4.13 dismissable): a DOCUMENT-level keydown listener —
 * not a button handler, because a hover-only reveal holds no focus and the key would land on
 * `document.body` unheard — sets one state bit, `is-suppressed`, and CSS gates every reveal
 * selector on its absence. Clearing is per-channel: blur always clears; mouse-leave clears only
 * while the pill is unfocused, so a pointer passing over a focus-dismissed pill cannot re-arm
 * the reveal the keyboard user just dismissed. An identity change must NOT announce: the live
 * region below is keyed on the STATUS alone, so the tooltip's data changing never touches it.
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
  // The last-confirmed backend identity — `null` until the first `GET /health` read lands, and
  // retained through `reconnecting`/`down` thereafter (the header's last-confirmed argument).
  const instanceId = useInstanceId()

  // Generated rather than authored (`AgentViewsNav`'s reason verbatim): two mounted pills in one
  // test document would share an authored id, and `aria-describedby` would resolve to whichever
  // rendered first.
  const tooltipId = useId()

  // WCAG 1.4.13's dismissability, as one bit: Escape sets it, blur and mouse-leave clear it, and
  // the stylesheet gates every reveal selector on the class it becomes. State rather than a DOM
  // poke so React owns the class list; visual reveal itself is CSS's job and holds no state.
  const [suppressed, setSuppressed] = useState(false)

  // AT THE DOCUMENT, NOT ON THE BUTTON (review finding): the hover reveal needs no focus, so
  // during a hover-only reveal the key lands on `document.body` and a button-scoped handler
  // would never hear it — Escape could not dismiss exactly the channel 1.4.13's dismissable
  // clause exists for. Registered for the mounted lifetime; the bit it sets is inert while no
  // reveal channel is active and is cleared by the same blur/mouse-leave that would have ended
  // the reveal it dismissed.
  //
  // Deliberately NO `stopPropagation` and NO `preventDefault`: there is no ancestor Escape
  // behaviour to collide with today — the only Escape-consuming surface is the agent view, which
  // is modal with focus trapped and a scrim over this pill — and swallowing the key here would
  // be the exact starvation `deferred-work.md:49` records the agent view's own capture handler
  // causing.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') setSuppressed(true)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

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
          rather than listing it) — shipped at c5-7 precisely so this story's `aria-describedby`
          could attach without re-doing the element or the Tab-order record.

          STILL NO `onClick`, AND THAT IS STILL THE HONEST SHAPE. The tooltip reveals on hover
          and focus — CSS's job — so a click does nothing and a no-op handler would be a lie.
          The two handlers below CLEAR the suppression bit the document-level Escape listener
          sets (see the effect above), and the clearing is per-channel so a dismissal cannot be
          undone by the OTHER channel (review finding): blur always clears, because leaving the
          pill ends the focus reveal the dismissal was about; mouse-leave clears only while the
          pill is NOT the focused element, because a pointer merely passing over a
          focus-dismissed pill must not re-arm the reveal the keyboard user just dismissed.
          It still carries no `aria-expanded`, no `aria-pressed` and no `aria-haspopup` — a
          tooltip is a description, not a popup the button controls — and no `title` (UX-DR39
          bans a hover-only disclosure; the visible tooltip is the one channel, so the two can
          never disagree).

          `aria-describedby` is ALWAYS wired, whatever the reveal state: the description is true
          whether or not it is painted — suppressed included — and jsdom asserts the wiring while
          the eye-check owns the reveal. */}
      <button
        type="button"
        className="connection-pill"
        aria-describedby={tooltipId}
        onBlur={() => setSuppressed(false)}
        onMouseLeave={(event) => {
          if (document.activeElement !== event.currentTarget) setSuppressed(false)
        }}
      >
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
      {/* THE TOOLTIP (story 17.1) — the button's IMMEDIATE next sibling, which the stylesheet's
          `+` combinator depends on, and OUTSIDE the button so its text stays a description and
          never joins the accessible name (see the header). `role="tooltip"` names what it is;
          the id is what `aria-describedby` above resolves. Hidden at rest by CSS alone — jsdom
          resolves no stylesheets, so the tests assert wiring and content and the eye-check owns
          the reveal. The text is ONE builder's sentence, so the glass and the computed
          description cannot disagree. */}
      <p
        role="tooltip"
        id={tooltipId}
        className={`connection-pill-tooltip${suppressed ? ' is-suppressed' : ''}`}
      >
        {tooltipText(pagePort(), instanceId)}
      </p>
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
