import { AppShell } from './components/AppShell/AppShell'
import { Footer } from './components/Footer/Footer'
import { StatePanel } from './components/StatePanel/StatePanel'

/**
 * The application root.
 *
 * It composes the shell, one state panel and the attribution, and nothing else. Every other
 * region the shell holds open — the card grid, the two analysis panels, the card detail, the
 * deck list, the format check, the badges, the agent-view nav and the agent view itself —
 * arrives as a prop from a later story, so this file's job is to stay as close to one line as it
 * honestly can.
 *
 * c4-1 owns the store that will feed those props and the fetch layer beneath it; c3-1 shipped the
 * endpoints that layer will call, but no client-side code at all.
 * Until then the shell renders its own placeholders, each naming the story that replaces it.
 *
 * ================= WHY THE LEFT COLUMN IS NO LONGER A PLACEHOLDER (c2-9, Q1) ============
 *
 * The no-active-deck panel is rendered into the shell's `left` slot, and this is HONEST rather
 * than a demo: there genuinely is no active deck. There is no fetch layer until c4-1 and no
 * store until c4-1, so "No deck on the glass" with an empty deck list is the application's true
 * state, not a mock of one.
 *
 * It is also what makes the story's visual half checkable. c2-7 and c2-8 both shipped
 * components with no consumer and had to downgrade their appearance ACs to "not dev-verified";
 * a third in a row would have left the shell, `Panel` and the whole token layer unlooked-at
 * into Epic 4.
 *
 * THE CONSEQUENCE, ACCEPTED DELIBERATELY AND NOT PAPERED OVER: `AppShell`'s left-column
 * placeholder — the line naming c4-4 and c4-8 — is DISPLACED by this prop. It is not deleted:
 * it still fires whenever `left` is empty, `AppShell.test.tsx` still asserts it against the
 * component's own props, and the two stories it names are unaffected. What changes is which of
 * the two the running app shows, and the ownership is stated here so nobody has to reconstruct
 * it:
 *
 *   **c4-2 / c4-4** replace this static choice with the real one — a deck when there is a deck,
 *   this panel when there is not — and **c3-9** owns the transition between them (FR-22).
 *   Until then the choice is a constant, and the constant is the truth.
 *
 * NO `decks` PROP IS PASSED, for the same reason: `GET /api/decks` exists as of c3-1, but
 * **c4-2** owns calling it, so this app does not know any deck names yet. The endpoint being
 * live changes nothing here — nothing fetches. An empty list renders nothing extra, the correct
 * day-one render rather than an omission (StatePanel AC 5).
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
  return <AppShell left={<StatePanel state="no-active-deck" />} footer={<Footer />} />
}
