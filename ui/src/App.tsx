import { useEffect } from 'react'

import { AnalysisRow } from './components/AnalysisRow/AnalysisRow'
import { AppShell } from './components/AppShell/AppShell'
import { DeckBadges } from './components/DeckBadges/DeckBadges'
import { Footer } from './components/Footer/Footer'
import { StatePanel } from './components/StatePanel/StatePanel'
import { CardDetail } from './containers/CardDetail/CardDetail'
import { CardGrid } from './containers/CardGrid/CardGrid'
import { DeckList } from './containers/DeckList/DeckList'
import { ManaCurve } from './containers/ManaCurve/ManaCurve'
import { hydrateDeckCards } from './state/cards'
import { surfaceOf, useDeckState } from './state/deck'
import { useSystemState } from './state/systemState'

/**
 * The application root.
 *
 * It composes the shell, the card grid, one state panel, the header badges and the attribution,
 * and nothing else. Every other region the shell holds open — the two analysis panels, the card
 * detail, the deck list, the format check, the agent-view nav and the agent view itself —
 * arrives as a prop from a later story, so this file's job is to stay as close to one line as it
 * honestly can.
 *
 * c4-1 owns the card cache and the in-flight deduping that will feed those props, extending the
 * store and the fetch layer **c3-9** opened; until then the shell renders its own placeholders,
 * each naming the story that replaces it.
 *
 * ================= THE LEFT COLUMN IS NOW WIRE-DRIVEN (c3-9, FR-22) ====================
 *
 * `useSystemState` polls `GET /api/decks` and reports which system panel is true right now. The
 * panel is chosen from the response's `reason` TOKEN through `states.ts`'s `PANEL_FOR_REASON` —
 * never from a bare status code, which is AD-16's rule and the reason two different `503`s put
 * two different panels on the glass. Nothing here decides anything: this file renders whichever
 * panel the boundary picked, and the deck names that one of them carries.
 *
 * WHY THE TERNARY, RATHER THAN `state={panel}`: `StatePanelProps` is a DISCRIMINATED UNION, and
 * only the `no-active-deck` arm accepts `decks` — `EXPERIENCE.md` attaches a deck list to that
 * row and to no other. Spreading one `decks` prop across every state would compile only if that
 * constraint were removed. The two branches are the constraint being honoured, not a special
 * case: it is exactly one `<StatePanel>` on screen either way.
 *
 * THE DISPLACEMENT c2-9 ACCEPTED IS UNCHANGED, AND STILL NOT PAPERED OVER: `AppShell`'s
 * left-column placeholder — the line naming c4-4 and c4-8 — is DISPLACED by this prop, never
 * deleted. It still fires whenever `left` is empty and `AppShell.test.tsx` still asserts it
 * against the component's own props. What c3-9 changed is only that the choice is no longer a
 * constant; **c4-2 / c4-4** replace it again with a deck when there is a deck.
 *
 * THE `decks` PROP IS NOW PASSED, and that is this story's other half. `GET /api/decks` shipped
 * in **c3-1** and nothing called it until now; an empty list is still the ordinary fresh-install
 * answer and still renders nothing extra (StatePanel AC 5). **c4-2** owns reading the deck
 * itself — this story reads the names, which is all the panel's copy promises.
 *
 * ================= AND NOW THERE IS A DECK (c4-2, FR-07, FR-05) ========================
 *
 * `useDeckState` boots once per mount: `GET /api/active-deck`, then — on a non-null id —
 * `GET /api/deck/{deck_id}`. **The precedence between a deck and a system panel is NOT decided
 * here.** `surfaceOf` is the one place it lives (c4-2 Q1), exported from `src/state/deck.ts` so
 * that c4-4's grid, c4-7's deck list and c4-12's empty state read the same answer rather than
 * each re-deriving it from `deck !== null` — which is the epic's *"the grid and the list panel
 * cannot disagree"* clause applied one level up. This file renders the answer and computes none
 * of it; `deck` below is a NARROWING of that answer, not a second rule.
 *
 * BOTH HOOKS ARE CALLED HERE BECAUSE BOTH OWNERSHIPS LIVE HERE. `useSystemState` owns the poll
 * and `useDeckState` owns the boot, and each one's docstring says `App` is its ONE consumer for
 * the same measured reason: a second mounted caller creates a second poller / a second boot and
 * silently doubles the request rate.
 *
 * ================= AND NOW THE DECK IS ON THE GLASS (c4-4, FR-19) ======================
 *
 * The `left` slot finally holds a `CardGrid`. Until this story a loaded deck displaced the system
 * panel and put nothing in its place, so the slot fell back to `AppShell`'s own placeholder —
 * *"The card-art grid lands here — c4-4 …"* — which was the honest displacement rather than a
 * regression, and what made this story's slot findable by searching for its own id. That line is
 * now displaced in turn: **the fourth application of the c2-9 ruling, and the same one.**
 * `AppShell.tsx` is NOT edited, its placeholder still fires whenever `left` is empty, and
 * `AppShell.test.tsx` still asserts it against the component's own props. What changed is only
 * which of the two the running app shows — and `App.test.tsx`'s displacement assertion changed
 * with it, which is the point of that assertion existing.
 *
 * `CardGrid` is the first component in this codebase that is NOT a presentation-only primitive.
 * It lives in `src/containers/`, the category c4-4 ruled into existence (Q1), because a tile that
 * takes `<img onLoad>` and holds a `ref` is banned outright from `src/components/` by four
 * separate guards. `ui/README.md` carries the argument; ~15 later component stories inherit it.
 *
 * Nothing about the precedence moved. `surfaceOf` still decides, this file still renders the
 * answer and computes none of it, and the grid is handed `surface.boards` — the derivation
 * `deckGroups.ts` performed once at write time *"so the grid and the list panel cannot
 * disagree"*. **c4-7**'s deck list reads the same value, including the sideboard this grid
 * deliberately does not draw.
 *
 * ================= AND NOW THE DECK RESPONDS (c4-5, FR-17) =============================
 *
 * The `right` slot holds the card detail panel — the fifth application of the c2-9 displacement
 * ruling, unchanged: `AppShell.tsx` is NOT edited, its placeholder (*"Card detail — c4-5 — the
 * deck list — c4-7 — and the format check — c4-10 — stack here"*) still fires whenever `right`
 * is empty, and `AppShell.test.tsx` still asserts it against the component's own props. What
 * changed is which of the two the running app shows — and only for a deck.
 *
 * ================= WHAT THE RIGHT COLUMN DOES BEHIND A STATE PANEL (c4-5 Q14) ==========
 *
 * **This is a ruling, and it closes a gap in the UX contract rather than one in this story.**
 * `validation-report-2026-07-25.md:78` records it as **L8** — *"Right-column panel visibility is
 * specified for cold-open-no-deck but not for the database-not-initialized or disconnected
 * states, which also put a State panel in the left column"* — and `:146` records the lows as
 * unactioned. The two halves of the contract genuinely disagree: `EXPERIENCE.md:112` says *"Right
 * column panels hidden"* for the one case it covers, while UX-DR30 says *"the right column, nav
 * and footer remain functional around it"*.
 *
 * `surfaceOf` returns `{ kind: 'panel' }` for all six state keys, so this file is where the
 * contradiction becomes code. **Ruled: the detail panel renders only for `kind === 'deck'`.**
 * The reason is not symmetry, it is that UX-DR20's *"never empty while a deck is loaded"* has
 * nothing to be true of otherwise — a persistent card panel with no deck behind it would either
 * be an empty box or would keep showing a card from a deck that is no longer on the glass. The
 * one case the contract DOES specify is honoured exactly, the other five are made to match it,
 * and UX-DR30 stays satisfied because the column is still there with the shell's own line in it.
 * **c4-7 and c4-10 inherit this rather than re-deciding it**, which is what makes it worth
 * writing here instead of in the panel.
 *
 * The `undefined` (rather than `null`) is the same spelling the header props use, and `filled()`
 * makes either safe — see the `deckName` note below.
 *
 * ================= THE `h1` STOPS SAYING WHAT THE KICKER SAYS (C3 retro F2) ============
 *
 * `deckName` is filled with the deck's own name, so the header stops rendering the product name
 * twice — recorded at the C3 retro *"so c4-2 does not treat the swap as cosmetic"*. `AppShell`
 * is NOT edited: the element, its level and its position do not move, which is the whole point
 * of it being a prop, and its `filled()` fallback still fires when there is no deck — which is
 * what keeps a fresh install from being heading-less (c2-6 Q3). `undefined` rather than `''` is
 * deliberate on both header props, though `filled()` makes either safe.
 *
 * ================= WHY THE FOOTER IS NO LONGER A PLACEHOLDER (c2-10) ====================
 *
 * The attribution is a CONDITION OF PUBLIC RELEASE (`DESIGN.md:375`, NFR-08, UX-DR32), not a
 * design choice, so unlike every other slot this one is not waiting for data — it is correct
 * from day one and stays correct forever. There is nothing a later story replaces it with.
 *
 * The same displacement c2-9 performed on the left column applies here, for the same reason and
 * with the same care: `AppShell`'s footer placeholder — the line naming c2-10 — is DISPLACED by
 * this prop, not deleted. It still fires whenever `footer` is empty, and `AppShell.test.tsx`
 * still asserts it against the component's own props. What changed is which of the two the
 * running app shows.
 *
 * ================= "EVERY SURFACE", STRUCTURALLY (Q3, Brad 2026-07-30) ==================
 *
 * The epic asks the attribution to be present on EVERY top-level surface. Today there is exactly
 * one, so an enumerated list of surfaces would be a list its author thought of — this epic's
 * standing finding, three rounds running. The rule is structural instead, and it is already true
 * by construction: **there is one `AppShell`, one `footer` slot and no router, so every surface
 * renders through this file.** `App.test.tsx` asserts the footer is in the `contentinfo`
 * landmark by role and by text, and `ui/README.md` records the rule where the next surface's
 * author will read it.
 *
 * That holds through Epic 6 without amendment: c6-5's agent view is an OVERLAY rendered inside
 * the shell (`AppShell`'s `overlay` slot), not a route that replaces it, so the footer survives
 * it by construction rather than by anyone remembering.
 */
export default function App() {
  const system = useSystemState()
  const surface = surfaceOf(useDeckState(), system)
  // The one narrowing of the one rule. Not a second precedence decision: `surfaceOf` has already
  // said which of the two is true, and this line only gives the deck arm a name so that the
  // three slots below can read its fields without repeating the discriminant check.
  const deck = surface.kind === 'deck' ? surface : null
  const detail = deck?.detail ?? null

  // THE DECK-WIDE HYDRATION SWEEP (c4-6, Q1, AC 23), AND ITS PLACEMENT IS THE DECISION.
  //
  // c4-6's flip control must render "when its tile renders", and whether a card HAS a back face
  // lives only in the hydrated record — `CardSummary` carries neither `card_faces` nor
  // `image_uris`. So something has to hydrate the deck rather than one card at a time. The two
  // alternatives were priced and declined in that story's Q1: a derived field on `CardSummary` is
  // an MCP-visible schema change, and a control that appears only once a card happens to be
  // inspected would materialise a Tab stop mid-traverse (UX-DR40 puts it "immediately after its
  // own tile").
  //
  // ==== WHY HERE, AND NOT IN `createDeckBoot` BESIDE `seedCardSummaries` ================
  // React runs effects AFTER the DOM commit, so the sweep is off the render's critical path: the
  // grid draws from the summary tier and never waits for a card record. Called from the boot
  // instead, the same 99 reads would be issued before React had rendered a single tile.
  //
  // **AND THE STRONGER CLAIM THIS COMMENT USED TO MAKE IS FALSE — MEASURED, AND CORRECTED
  // RATHER THAN SMOOTHED OVER.** It read "by the time this line runs the browser has already
  // queued all ~99 image requests, so the sweep takes the connection pool BEHIND the pictures".
  // Measured over four cold-cache Chrome runs against the real 99-card Atraxa deck, the first
  // card-record request starts **6–10 ms BEFORE** the first image request every time
  // (108/114, 757/765, 583/593, 105/113 ms). The commit sets the `src` attributes; the browser
  // dispatches those loads asynchronously, and this effect gets there first. React's ordering
  // buys "not on the render path", not "behind the pictures".
  //
  // ==== WHAT IT COSTS, AS A NUMBER (AC 23) ==============================================
  // At most one request per DISTINCT card id, once per deck per tab: **99** for the largest of the
  // 40 real decks, fewer for all the others. `hydrateCard` dedupes in flight, refuses a hydrated
  // id and never re-asks a terminal refusal, so a re-render costs nothing and the ceiling holds.
  // `App.test.tsx` pins the count for its own fixture rather than trusting this comment.
  //
  // The wall-clock price, measured the only way that means anything — the same deck, the same
  // machine, a fresh browser profile each time, with this line and without it. Time from
  // navigation to the LAST of the deck's images:
  //
  //   with the sweep    1,594 · 1,793 · 1,795 · 847 ms      (99 card reads, all settled by ~1.0 s)
  //   without it          343 ·   753 ·   538 · 352 ms      (1 card read)
  //
  // So the tail of the cold open roughly TRIPLES — about **+1.2 s** on the largest real deck —
  // while first paint is untouched (32–128 ms either way, because the grid never waits for this).
  // That is the price of AC 1 being true at all: `CardSummary` carries neither `card_faces` nor
  // `image_uris`, so without these reads no tile can know it has a back face and no flip control
  // exists. It is a COLD-OPEN cost, once per deck per tab, and it is stated here rather than
  // discovered later.
  //
  // `detail` is the dependency because it is the DECK's identity as far as this file is
  // concerned: `deck.ts` writes it once per boot, so it changes exactly when the deck does. This
  // reads the payload's own `cards` array verbatim — not `boards` — so it is not a second
  // flattening of the derivation `deckGroups.ts` owns (AD-12), and it therefore also covers the
  // sideboard rows c4-7 will draw.
  useEffect(() => {
    if (detail === null) return
    hydrateDeckCards(detail.cards.map((row) => row.card_id))
  }, [detail])

  return (
    <AppShell
      deckName={deck?.detail.name}
      badges={
        deck === null ? undefined : (
          <DeckBadges
            format={deck.detail.format}
            mainboardCount={deck.detail.mainboard_count}
            sideboardCount={deck.detail.sideboard_count}
          />
        )
      }
      /* THE LEFT COLUMN NOW STACKS THE GRID AND THE ANALYSIS ROW (c4-8, AC 1, AC 2, AC 3).
         A Fragment, exactly as the right column took one at c4-7, and for the same reason:
         `.app-shell-column` is already `display:flex; flex-direction:column; gap:
         var(--space-panel-gap)` (AppShell.css:151-156), so a second child stacks 24px beneath
         the grid with no shell edit. `AppShell.tsx` is NOT touched — the SEVENTH application of
         c2-9's displacement ruling, and the first on the LEFT slot since c4-4. Its placeholder
         (the line naming c4-4, c4-8 and c4-9) still fires whenever `left` is empty, which
         `AppShell.test.tsx:115` asserts against the component's own props.

         `AnalysisRow` rather than the panel directly, because `AppShell.tsx:127` assigns the
         1:1 pair to THIS story by name and c4-9 supplies the second panel: the row renders one
         child at full width today and two at exactly 1:1 the day that story lands, by adding a
         sibling inside this element and editing nothing else (Q6).

         Gated on the SAME `kind === 'deck'` test as the grid beside it, inherited from the
         c4-5 Q14 ruling rather than re-decided here (AC 2) — and note this is a DIFFERENT gate
         from the right column's: the left slot renders a `StatePanel` in the other five cases,
         not a placeholder. `ManaCurve` itself renders nothing when the curve is empty (Q12).
         On a land-only deck that leaves the row's EMPTY div in the DOM, with the column gap
         still applied beneath the grid — accepted posture (review, 2026-08-06), pinned by
         App.test.tsx's land-only test rather than papered over: gating the row here would need
         the curve's total, a second derivation of what curve.ts owns, for a state no corpus
         deck can produce. c4-9, which gives the row its second child, is named to revisit it. */
      left={
        surface.kind === 'deck' ? (
          <>
            <CardGrid boards={surface.boards} />
            <AnalysisRow>
              <ManaCurve boards={surface.boards} />
            </AnalysisRow>
          </>
        ) : surface.panel === 'no-active-deck' ? (
          <StatePanel state="no-active-deck" decks={system.decks} />
        ) : (
          <StatePanel state={surface.panel} />
        )
      }
      /* THE RIGHT COLUMN NOW STACKS TWO PANELS (c4-7, AC 1, AC 2, AC 3).
         A Fragment, and nothing else is needed: `.app-shell-column` is already
         `display:flex; flex-direction:column; gap: var(--space-panel-gap)` (AppShell.css:151-156),
         so a second child stacks 24px beneath the first with no shell edit. `AppShell.tsx` is NOT
         touched — the sixth application of c2-9's displacement ruling, and its `/c4-7/`
         placeholder still fires whenever `right` is empty, which `AppShell.test.tsx:161`/`:171`
         assert against the component's own props.

         BOTH panels are gated on the SAME `kind === 'deck'` test, inherited from the c4-5 Q14
         ruling above rather than re-decided here (AC 2). The deck list is permanently present
         beside the grid — never a toggled alternate view (FR-05, UX-DR19) — so there is no
         view-mode state anywhere in this file. */
      right={
        surface.kind === 'deck' ? (
          <>
            <CardDetail boards={surface.boards} />
            <DeckList boards={surface.boards} />
          </>
        ) : undefined
      }
      footer={<Footer />}
    />
  )
}
