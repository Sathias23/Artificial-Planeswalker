import hero from '../../assets/hero.jpg'
import { StatePanel } from '../StatePanel/StatePanel'
import './Welcome.css'

/**
 * The Welcome surface — what the glass shows when the backend is up and no deck is
 * active: the hero art as a banner ABOVE the unchanged no-active-deck `StatePanel`.
 *
 * The hero is DECORATIVE and nothing else: `alt=""`, no handlers, no `ref`, no load tracking.
 * It is IMPORTED from `src/assets/`, not referenced by a public path: Vite emits it as
 * `assets/hero-<hash>.jpg`, which `spa.py` serves `immutable` for a year, where a `public/` copy
 * lands at the bundle root and is served `no-cache` — a 420 KB revalidation on every open. The
 * committed file is a recompressed 1000x667 (146 KB against the original 1536x1024's 420 KB);
 * `Welcome.css` crops it to a 240px banner, so the extra pixels bought nothing. It is served
 * same-origin by the companion and never hot-linked; app code never fetches it, the browser does.
 * If it 404s, `alt=""` plus a `max-height` rather than a `height` means no 240px hole is reserved
 * (a hairline strip of border remains) and the panel is still the whole message.
 *
 * Nothing fetches it on a cold open with an active deck: `surfaceOf`'s `booting` arm renders no
 * left slot at all until the active-deck read settles, so this component only ever mounts once
 * the answer is genuinely "no active deck".
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
      <img className="welcome-hero" src={hero} alt="" width="1000" height="667" />
      <StatePanel state="no-active-deck" decks={decks} />
    </div>
  )
}
