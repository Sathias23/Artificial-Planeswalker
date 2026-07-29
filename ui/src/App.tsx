import { AppShell } from './components/AppShell/AppShell'
import { StatePanel } from './components/StatePanel/StatePanel'

/**
 * The application root.
 *
 * It composes the shell and one state panel, and nothing else. Every other region the shell
 * holds open — the card grid, the two analysis panels, the card detail, the deck list, the
 * format check, the footer attribution, the badges, the agent-view nav and the agent view
 * itself — arrives as a prop from a later story, so this file's job is to stay as close to one
 * line as it honestly can.
 *
 * c4-1 owns the store that will feed those props and c3-1 owns the fetch layer beneath it.
 * Until then the shell renders its own placeholders, each naming the story that replaces it.
 *
 * ================= WHY THE LEFT COLUMN IS NO LONGER A PLACEHOLDER (c2-9, Q1) ============
 *
 * The no-active-deck panel is rendered into the shell's `left` slot, and this is HONEST rather
 * than a demo: there genuinely is no active deck. There is no fetch layer until c3-1 and no
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
 * NO `decks` PROP IS PASSED, for the same reason: `GET /api/decks` is c3-1's, so this app does
 * not know any deck names yet. An empty list renders nothing extra, which is the correct
 * day-one render rather than an omission (StatePanel AC 5).
 */
export default function App() {
  return <AppShell left={<StatePanel state="no-active-deck" />} />
}
