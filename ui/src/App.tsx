import { useEffect, useRef } from 'react'

import { AnalysisRow } from './components/AnalysisRow/AnalysisRow'
import { AppShell } from './components/AppShell/AppShell'
import { DeckBadges } from './components/DeckBadges/DeckBadges'
import { Footer } from './components/Footer/Footer'
import { StatePanel } from './components/StatePanel/StatePanel'
import { Welcome } from './components/Welcome/Welcome'
import { AgentView } from './containers/AgentView/AgentView'
import { AgentViewsNav } from './containers/AgentViewsNav/AgentViewsNav'
import { GroupsView } from './containers/GroupsView/GroupsView'
import { SuggestionsView } from './containers/SuggestionsView/SuggestionsView'
import { SwapsView } from './containers/SwapsView/SwapsView'
import { TierListView } from './containers/TierListView/TierListView'
import { CardDetail } from './containers/CardDetail/CardDetail'
import { CardGrid } from './containers/CardGrid/CardGrid'
import { ColourDistribution } from './containers/ColourDistribution/ColourDistribution'
import { ConnectionPill } from './containers/ConnectionPill/ConnectionPill'
import { DeckAnnouncer } from './containers/DeckAnnouncer/DeckAnnouncer'
import { DeckList } from './containers/DeckList/DeckList'
import { FormatCheck } from './containers/FormatCheck/FormatCheck'
import { ManaCurve } from './containers/ManaCurve/ManaCurve'
import { SkipLink } from './containers/SkipLink/SkipLink'
// The app's one focus hand-off. The surface-transition rescue below is a caller, not a copy:
// nothing here re-implements the `tabIndex = -1` / focus / remove-on-blur dance, and
// `keyboard-floor.test.ts` still finds exactly one module that writes `.tabIndex`.
import { focusHome } from './containers/focusHome'
import { closeAgentView, useOpenAgentView } from './state/agentView'
import { useAgentConnection } from './state/connection'
import { surfaceOf, useDeckState, useDeckUpdating } from './state/deck'
import { deckIsEmpty } from './state/deckGroups'
import { clearFormatCheck, loadFormatCheck } from './state/formatCheck'
import { useSystemState } from './state/systemState'

/**
 * The application root: it composes the shell and fills its slots, and decides nothing about
 * what the slots say.
 *
 * The left column is wire-driven (FR-22): the panel is chosen from the poll response's `reason`
 * token through `PANEL_FOR_REASON`, never from a bare status code (AD-16). The precedence between
 * a deck and a system panel is NOT decided here: `surfaceOf` (`src/state/deck.ts`) is the one
 * place it lives, so every consumer reads the same answer instead of re-deriving it from
 * `deck !== null`. `useSystemState` owns the poll and `useDeckState` owns the boot, and `App` is
 * the one consumer of each: a second mounted caller silently doubles the request rate.
 *
 * The right column renders only for `kind === 'deck'`. UX-DR20's "never empty while a deck is
 * loaded" has nothing to be true of otherwise: a card panel with no deck behind it is an empty
 * box or a card from a deck no longer on the glass. UX-DR30 holds because the column stays.
 *
 * `deckName` fills the `h1` so the header does not render the product name twice; `AppShell`'s
 * `filled()` fallback keeps a fresh install from being heading-less. The footer attribution is a
 * condition of public release (NFR-08, UX-DR32) and must appear on every top-level surface, which
 * holds structurally: one `AppShell`, one `footer` slot, no router, and the agent view is an
 * overlay inside the shell rather than a route that replaces it.
 */
export default function App() {
  const system = useSystemState()
  const surface = surfaceOf(useDeckState(), system)
  // A content object or `null`, never a boolean: the store's selector (`openViewOf`) resolves
  // "is one showing, and what is it" once, so this file cannot disagree with it.
  const agentView = useOpenAgentView()
  // The socket, mounted once; `App` is its one consumer because a second mounted caller is a
  // second socket per tab. It produces `system.connection`, which `surfaceOf` already reads. Hooks
  // run their effects in declaration order, ahead of this component's own `useEffect` blocks, so
  // keep it here: the session mint then precedes the deck detail and the format check.
  useAgentConnection()
  // A primitive subscription (UX-DR35, UX-DR42): this file re-renders on the flag flipping and
  // on nothing else the deck slice writes.
  const deckUpdating = useDeckUpdating()
  // Not a second precedence decision: `surfaceOf` has already said which arm is true; this only
  // names the deck arm so the slots below can read its fields without repeating the check.
  const deck = surface.kind === 'deck' ? surface : null
  const detail = deck?.detail ?? null

  // A deck with zero cards on every board is a `{kind:'deck'}` surface exactly like a full one,
  // so there is no extra `Surface` arm. The predicate lives beside `DeckBoards` in
  // `deckGroups.ts`; it is read once, above both effects, because the request and the render
  // both need it.
  const emptyDeck = deck !== null && deckIsEmpty(deck.boards)

  // The format check's one read, driven from here because a container may not reach the network
  // (`shell.test.ts`) and neither may this file (`posture.test.ts`): `formatCheck.ts` owns the
  // request, this line owns the decision. Not inside `createDeckBoot` either — that would make a
  // panel's data a first-paint dependency and put a network outcome inside the value whose
  // identity IS the deck's, so a report landing would read as a deck replacement and release the
  // user's pin.
  //
  // Keyed on `detail` itself, not the id string: `detail`'s identity changes exactly when a
  // settled boot or a settled refetch writes the store, which is the staleness signal the panel
  // needs after an agent edit. The pin is a count — one request per settled detail
  // (App.test.tsx) — so a render, a poll transition or a socket status change issue nothing.
  //
  // Every path clears, or a deck deleted between two polls would leave a legality verdict about
  // a deck no longer on the glass. `clearFormatCheck` bumps the slice's generation, so an
  // in-flight read writes nothing; as the cleanup it also covers unmount and a StrictMode remount.
  // The empty/null arm clears eagerly instead: it has no in-flight read, and what it must kill is
  // the previous deck's report, now. An empty deck does not ask at all, for the reason no request
  // is made behind a state panel: an unseen panel must not be a round trip on the path NFR-05
  // measures. `emptyDeck` stays in the deps because the lint contract wants every read named.
  useEffect(() => {
    if (detail === null || emptyDeck) {
      clearFormatCheck()
      return
    }
    void loadFormatCheck(detail.id)
    return clearFormatCheck
  }, [detail, emptyDeck])

  /**
   * What `surface.kind` was on the previous commit — the surface transition's only input. A ref
   * rather than state because nothing renders differently; written inside the effect below and
   * never during render (`react-hooks/refs` is an error).
   */
  const previousSurfaceKind = useRef(surface.kind)

  // The surface transition's focus rescue (UX-DR46). React unmounting the focused node drops
  // focus to `<body>`, which restarts Tab from the top of the document; a tile or a deck row
  // holding focus when the deck is deleted or refetched hits that at the scale of a whole surface.
  // One effect rather than a copy of `SkipLink`'s ref idiom per focusable: the grid, the analysis
  // row and the right column all hang off the same `kind === 'deck'` gate, so they depart in one
  // commit, and anything outside it still holds focus afterwards — focus on `<body>` across a
  // deck → panel transition therefore means the departing surface held it. If something else
  // already took focus, moving it again would override a decision this effect did not make. The
  // target is the state panel's headline if one is showing, else the `<h1>` (`AppShell.test.tsx`
  // pins exactly one); the `??` arm is unreachable today and costs one expression to be right if
  // that changes.
  useEffect(() => {
    const departed = previousSurfaceKind.current
    previousSurfaceKind.current = surface.kind
    if (departed !== 'deck' || surface.kind === 'deck') return
    // An open agent view makes body-focus unreadable: its title usually holds focus, but a
    // pointer click on the dialog's non-focusable content blurs to `<body>` (jsdom does not model
    // this), and rescuing then would park focus on the headline BEHIND the still-open modal.
    // Focus inside the view is the view's own restore-on-close to handle.
    if (agentView !== null) return
    if (document.activeElement !== null && document.activeElement !== document.body) return
    focusHome(document.querySelector('.state-panel-headline') ?? document.querySelector('h1'))
  }, [surface.kind, agentView])

  // The skip link is present iff a deck is on the glass AND it has at least one card (UX-DR31).
  // An empty deck has nothing to skip — zero tiles and zero rows before the right column — not a
  // missing target: `CardDetail` renders its frame (carrying `SKIP_TARGET_ID`) unconditionally.
  // The sideboard counts because the deck list renders a focusable row per sideboard card, so a
  // sideboard-only deck still has a corridor. Spelled as `deckIsEmpty`'s exact negation so a
  // change to the sideboard clause is structurally a change to both.
  const hasCards = deck !== null && !emptyDeck

  return (
    <AppShell
      skipLink={hasCards ? <SkipLink /> : undefined}
      deckName={deck?.detail.name}
      /* Both halves are load-bearing: the flag alone is also true during a cold boot (the store
         cannot know what is on the glass), and `deck !== null` — `surfaceOf`'s own answer — keeps
         a cold open, a state panel and the booting frame unmarked, so the marker covers exactly
         the UX-DR35 windows: a refetch or a full re-drive behind a still-rendered deck. */
      updating={deck !== null && deckUpdating}
      badges={
        deck === null ? undefined : (
          <DeckBadges
            format={deck.detail.format}
            mainboardCount={deck.detail.mainboard_count}
            sideboardCount={deck.detail.sideboard_count}
          />
        )
      }
      /* A Fragment: `.app-shell-column` is already `display:flex; flex-direction:column; gap:
         var(--space-panel-gap)`, so the analysis row stacks beneath the grid with no shell edit.
         Document order is the contract — the curve first, the colour bar second (DESIGN.md's
         "mana-curve and color-distribution panels below it as a 1:1 pair"). Each panel owns its
         own emptiness and `.analysis-row:empty` collapses the row, so no total is derived here.
         Same `kind === 'deck'` gate as the grid; unlike the right column, the other five cases
         render a `StatePanel` rather than nothing. */
      left={
        surface.kind === 'deck' ? (
          <>
            <CardGrid boards={surface.boards} />
            <AnalysisRow>
              <ManaCurve boards={surface.boards} />
              <ColourDistribution boards={surface.boards} />
            </AnalysisRow>
          </>
        ) : surface.kind ===
          'booting' /* NOTHING, DELIBERATELY, until the active-deck read settles. `INITIAL_SYSTEM_STATE`'s
             panel is `no-active-deck`, so without this arm the first frame of every cold open
             drew the Welcome surface — hero art and all — on the way to a deck view. No image, no
             copy, no reserved box: an `aria-busy` region would announce a wait that is one
             localhost round trip long. `surfaceOf` cannot latch here; every settle path leaves
             `booting`. */ ? null : surface.panel === 'no-active-deck' ? (
          /* The same no-active-deck panel, with the hero art above it. The other five system
             panels stay bare. The shell renders a single track here because `right` is empty. */
          <Welcome decks={system.decks} />
        ) : (
          <StatePanel state={surface.panel} />
        )
      }
      /* Detail, list, format check — document order is the contract (DESIGN.md: "card detail,
         deck list, format check, stacked"). All three share the grid's `kind === 'deck'` gate.
         The deck list is permanently present beside the grid, never a toggled alternate view
         (FR-05, UX-DR19), so there is no view-mode state in this file. `FormatCheck` takes no
         prop: it reads its own slice.

         The empty-deck gate on `FormatCheck` lives here, not in the panel: its data is never
         empty (six rows, always), so unlike `ManaCurve` and `ColourDistribution` it has no
         self-gate, and keeping this one here leaves the panel exactly one self-owned `null` arm
         (`state.status !== 'report'`), so a hidden panel and a failed one live in different
         files. `emptyDeck` rather than `!hasCards` is legibility only — inside this branch they
         reduce identically — so a future clause on `hasCards` cannot silently move this gate. */
      right={
        surface.kind === 'deck' ? (
          <>
            <CardDetail boards={surface.boards} />
            <DeckList boards={surface.boards} />
            {emptyDeck ? null : <FormatCheck />}
          </>
        ) : undefined
      }
      /* Unconditional: the pill renders on every surface, which is what "always visible" means
         (FR-15). It takes no prop, reading the slices through their own hooks rather than off
         `surface` here, because `surfaceOf` returns a PANEL surface in exactly the `'down'` state
         where the pill must still know a deck is loaded. The deck announcer rides in the same
         slot (UX-DR45): one visually-hidden polite `<p>`, no landmark, no Tab stop, also
         props-free, and also on every surface — gating it on a loaded deck would tear the live
         region out of the accessibility tree mid-session for no gain. */
      connectionPill={
        <>
          <ConnectionPill />
          <DeckAnnouncer />
        </>
      }
      /* Props-free: the nav reads the agent-view store itself. Handing it `agentView` would give
         the root an opinion about which pill is active; the root's job is where things go. */
      nav={<AgentViewsNav />}
      footer={<Footer />}
      /* Absent when closed: an always-mounted transparent element in this slot is a
         click-swallower ("the app stopped responding to clicks"), and `filled()` gates the
         wrapper, so this passes `undefined`, not `false`, `null` or an element that returns
         nothing. Every dismissal gesture calls `closeAgentView`, which writes `status` and not
         `content`, so the view remains re-openable for the rest of the session (UX-DR34). */
      overlay={
        agentView === null ? undefined : (
          /* No `key` on this element, deliberately. A second push while the view is open must
             replace the content in place — a prop update on a shell that stays mounted. A
             `key={agentView.id}` would remount it: replay the entry bloom instead of the
             crossfade, re-capture the return-focus target while focus sits inside the view, and
             run the restore cleanup mid-open. See `AgentView.tsx`'s replace effect. */
          <AgentView
            pushId={agentView.id}
            title={agentView.title}
            count={agentView.count}
            onClose={closeAgentView}
          >
            {/* The shell takes `children` and asks nothing about them, so the kind-specific view
                rides inside rather than being branched on in there. The ternary is total over
                the `kind` union — a fifth kind fails `npm run typecheck` here rather than
                rendering nothing — and the narrowing on `kind` is what types `items` per arm. */}
            {agentView.kind === 'suggestions' ? (
              <SuggestionsView kind={agentView.kind} items={agentView.items} />
            ) : agentView.kind === 'swaps' ? (
              <SwapsView kind={agentView.kind} items={agentView.items} />
            ) : agentView.kind === 'tier_list' ? (
              <TierListView kind={agentView.kind} items={agentView.items} />
            ) : (
              <GroupsView kind={agentView.kind} items={agentView.items} />
            )}
          </AgentView>
        )
      }
    />
  )
}
