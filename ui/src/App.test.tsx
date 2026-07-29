/**
 * App's own job, now that it has one: composing the shell.
 *
 * The landmark, header and slot assertions moved to
 * `src/components/AppShell/AppShell.test.tsx` in story c2-6, where the element structure
 * actually lives — asserting them twice would mean two files to update when c4-2 changes the
 * heading, and the second one would be the one nobody remembers. What stays here is the part
 * only this file can be wrong about: that the root renders the shell at all, and that it
 * renders exactly one of it.
 *
 * The jsdom environment, the jest-dom matchers and afterEach(cleanup) all come from the `dom`
 * vitest project in vite.config.ts; nothing needs setting up per file.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
  it('renders the application shell', () => {
    render(<App />)

    // By role, not by class name — and ONE landmark, not the full triple: the landmark
    // CONTRACT (exactly one banner/main/contentinfo, Q4's structure) is AppShell.test.tsx's,
    // and re-asserting it here would be exactly the duplication this file's header says was
    // moved — two files to update when Q4's structure changes, and the second one forgotten.
    //
    // What this assertion is and is NOT: `main` alone proves App renders SOMETHING with a
    // main landmark, which a bare `<main/>` impostor would also satisfy. The composition
    // proof is the heading test below — the shell supplies that heading, and an impostor
    // would not. Together they are the pair; neither carries it alone, and an earlier version
    // of this comment claimed the first one did.
    expect(screen.getAllByRole('main')).toHaveLength(1)
  })

  it('gives the document a top-level heading before any deck exists', () => {
    // Q3's ruling, asserted at the root because it is a property of what a fresh install
    // SHOWS, not of the shell in isolation: the no-active-deck state is the state the app
    // starts in, and it must not be heading-less. c4-2 replaces the string via `deckName`.
    render(<App />)

    expect(screen.getByRole('heading', { level: 1, name: 'Artificial Planeswalker' })).toBeVisible()
  })

  it('wires the no-active-deck state panel into the shell — Q1 made this the point', () => {
    // The review of 2026-07-29 measured that reverting App.tsx's `left` prop — the story's
    // headline decision, the cause of the bundle change, the thing a human can finally look
    // at — kept every test green. Landmine 18's "wiring breaks neither file" was permission to
    // wire without fear, not a reason to leave the wiring unasserted. By role and accessible
    // name, because that is what the panel IS to a screen reader; c3-9 replaces the static
    // choice with the wire-driven one and inherits this assertion.
    render(<App />)

    expect(screen.getByRole('region', { name: 'No deck on the glass.' })).toBeVisible()
  })
})
