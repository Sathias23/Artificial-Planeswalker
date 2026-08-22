import { StatePanel } from '../StatePanel/StatePanel'
import './Welcome.css'

/**
 * The Welcome surface (story 17.5) — what the glass shows when the backend is up and no deck is
 * active: the hero art as a banner ABOVE the unchanged no-active-deck `StatePanel`.
 *
 * The hero is DECORATIVE and nothing else: `alt=""`, no handlers, no `ref`, no load tracking.
 * `/hero.jpg` is `ui/public/hero.jpg`, which Vite copies to the bundle root unhashed (the
 * favicon's mechanism) — it is served same-origin by the companion and never hot-linked; app
 * code never fetches it, the browser does. If it 404s, `alt=""` plus a `max-height` rather than
 * a `height` means no 240px hole is reserved (a hairline strip of border remains) and the panel
 * is still the whole message.
 *
 * The panel's copy, semantics and the no-illustration ban INSIDE it are exactly as before —
 * the hero sits above the panel, not in it (DESIGN.md's State panel bullet, amended 17.5).
 * Only the `no-active-deck` arm of `App.tsx` renders this; the other five system panels never
 * get a hero.
 */
export interface WelcomeProps {
  /** The available deck names, rendered by the panel as quiet chips. */
  decks?: readonly string[]
}

export function Welcome({ decks }: WelcomeProps) {
  return (
    <div className="welcome">
      {/* Intrinsic size attributes: the browser reserves the box before the bytes arrive, so the
          first screen does not shift when the art lands. Pure HTML, no measurement by app code. */}
      <img className="welcome-hero" src="/hero.jpg" alt="" width="1536" height="1024" />
      <StatePanel state="no-active-deck" decks={decks} />
    </div>
  )
}
