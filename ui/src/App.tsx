import { AppShell } from './components/AppShell/AppShell'

/**
 * The application root.
 *
 * It composes the shell and nothing else. Every region the shell holds open — the card grid,
 * the two analysis panels, the card detail, the deck list, the format check, the footer
 * attribution, the badges, the agent-view nav and the agent view itself — arrives as a prop
 * from a later story, so this file's job is to stay one line long for as long as possible.
 *
 * c4-1 owns the store that will feed those props and c3-1 owns the fetch layer beneath it.
 * Until then the shell renders its own placeholders, each naming the story that replaces it.
 */
export default function App() {
  return <AppShell />
}
