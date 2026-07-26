import './App.css'

/**
 * Placeholder application shell.
 *
 * Deliberately minimal: this story builds the quality gate, not the UI. c2-6 replaces
 * this with the real two-column application shell, c2-7 adds the presentation-only
 * primitives, and c2-9 owns the shared state panel and its copy. What is here exists so
 * the scaffold has something to type-check, lint and render in a test.
 */
export default function App() {
  return (
    <main className="app-shell">
      <h1>Artificial Planeswalker</h1>
      <p>Companion is running.</p>
    </main>
  )
}
