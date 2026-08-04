import { AppShell } from './components/AppShell/AppShell'
import { DeckBadges } from './components/DeckBadges/DeckBadges'
import { Footer } from './components/Footer/Footer'
import { StatePanel } from './components/StatePanel/StatePanel'
import { CardGrid } from './containers/CardGrid/CardGrid'
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
      left={
        surface.kind === 'deck' ? (
          <CardGrid boards={surface.boards} />
        ) : surface.panel === 'no-active-deck' ? (
          <StatePanel state="no-active-deck" decks={system.decks} />
        ) : (
          <StatePanel state={surface.panel} />
        )
      }
      footer={<Footer />}
    />
  )
}
