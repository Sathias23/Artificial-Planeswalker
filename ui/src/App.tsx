import { AppShell } from './components/AppShell/AppShell'
import { Footer } from './components/Footer/Footer'
import { StatePanel } from './components/StatePanel/StatePanel'
import { useSystemState } from './state/systemState'

/**
 * The application root.
 *
 * It composes the shell, one state panel and the attribution, and nothing else. Every other
 * region the shell holds open — the card grid, the two analysis panels, the card detail, the
 * deck list, the format check, the badges, the agent-view nav and the agent view itself —
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
  const { panel, decks } = useSystemState()

  return (
    <AppShell
      left={
        panel === 'no-active-deck' ? (
          <StatePanel state="no-active-deck" decks={decks} />
        ) : (
          <StatePanel state={panel} />
        )
      }
      footer={<Footer />}
    />
  )
}
